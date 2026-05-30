"""
Services/Twitch/EventSub/TwitchEventSub.py

Reemplaza TwitchPubSub. Mantiene una conexión WebSocket a EventSub de Twitch
y gestiona suscripciones via HTTP (Helix API), tal como exige el protocolo
EventSub post-deprecación de PubSub (abril 2025).

Flujo:
  1. open() → conecta el WebSocket
  2. session_welcome → guarda session_id, emite sessionReady
  3. Suscriptores llaman createSubscription() (HTTP POST)
  4. Twitch envía eventos → newEventReceived
  5. session_reconnect → cierra WebSocket, reconecta tras RECONNECT_INTERVAL
  6. Suscriptores escuchan sessionLost/sessionReady para re-suscribirse
  7. close() → cierra WebSocket y para timers
"""
from .TwitchEventSubConfig import Config

from Services.Logging.Logger import Logger

from PyQt6 import QtCore, QtNetwork, QtWebSockets

import json


# ─────────────────────────────────────────────────────────────────────────────
# Modelos de datos
# ─────────────────────────────────────────────────────────────────────────────

class EventSubEvent:
    """Evento de notificación recibido del WebSocket."""
    def __init__(self, subscription_type: str, broadcaster_user_id: str, data: dict):
        self.subscription_type   = subscription_type
        self.broadcaster_user_id = broadcaster_user_id
        self.data                = data

    def __repr__(self):
        return f"<EventSubEvent type={self.subscription_type} channel={self.broadcaster_user_id}>"


class EventSubSubscription:
    """Suscripción confirmada por Twitch via HTTP."""
    def __init__(self, subscription_id: str, subscription_type: str, broadcaster_user_id: str):
        self.id                  = subscription_id
        self.subscription_type   = subscription_type
        self.broadcaster_user_id = broadcaster_user_id

    def __repr__(self):
        return f"<EventSubSubscription id={self.id} type={self.subscription_type}>"


# ─────────────────────────────────────────────────────────────────────────────
# TwitchEventSub
# ─────────────────────────────────────────────────────────────────────────────

class TwitchEventSub(QtCore.QObject):
    """
    Gestiona la conexión EventSub WebSocket y las suscripciones via HTTP.

    Señales:
        sessionReady        — WebSocket conectado y session_id disponible.
                              Los suscriptores deben llamar createSubscription aquí.
        sessionLost         — WebSocket desconectado. Los suscriptores deben
                              limpiar su estado de suscripción.
        subscriptionAdded   — HTTP POST exitoso; arg: EventSubSubscription
        subscriptionFailed  — HTTP POST fallido; arg: (sub_type, broadcaster_id)
        subscriptionRevoked — Twitch revocó una suscripción; arg: subscription_id
        newEventReceived    — Evento de notificación recibido; arg: EventSubEvent
    """

    sessionReady        = QtCore.pyqtSignal()
    sessionLost         = QtCore.pyqtSignal()
    subscriptionAdded   = QtCore.pyqtSignal(object)  # EventSubSubscription
    subscriptionFailed  = QtCore.pyqtSignal(object)  # (sub_type, broadcaster_id)
    subscriptionRevoked = QtCore.pyqtSignal(str)       # subscription_id
    newEventReceived    = QtCore.pyqtSignal(object)   # EventSubEvent

    def __init__(self, logger: Logger, parent: QtCore.QObject | None = None):
        super().__init__(parent=parent)
        self.logger = logger

        self._opened          = False
        self._session_id: str | None = None
        self._reconnect_url: str | None = None
        self._session_gen     = 0   # incrementa en cada session nueva; invalida respuestas HTTP viejas

        # WebSocket
        self._ws: QtWebSockets.QWebSocket | None = None

        # Keepalive: si no llega mensaje en keepalive_timeout + margen → reconectar
        self._keepalive_timer = QtCore.QTimer(self)
        self._keepalive_timer.setSingleShot(True)
        self._keepalive_timer.timeout.connect(self._onKeepaliveTimeout)

        # Reconexión automática tras desconexión
        self._reconnect_timer = QtCore.QTimer(self)
        self._reconnect_timer.setSingleShot(True)
        self._reconnect_timer.setInterval(Config.RECONNECT_INTERVAL)
        self._reconnect_timer.timeout.connect(self._reconnectTimerFired)

    # ── API pública ────────────────────────────────────────────────────────────

    def open(self) -> None:
        self._opened = True
        self.logger.info("[EventSub] open()")
        self._connectWs(Config.HOST)

    def close(self) -> None:
        self._opened = False
        self.logger.info("[EventSub] close()")
        self._reconnect_timer.stop()
        self._keepalive_timer.stop()
        self._reconnect_url = None
        if self._ws is not None:
            self._detachWs()
            self._ws.close()
            self._ws = None
        if self._session_id is not None:
            self._session_id = None
            self.sessionLost.emit()

    def isOpened(self) -> bool:
        return self._opened

    def isConnected(self) -> bool:
        return self._session_id is not None

    def getSessionId(self) -> str | None:
        return self._session_id

    def createSubscription(self, subscription_type: str, broadcaster_user_id: str) -> None:
        """
        Crea una suscripción EventSub via HTTP POST a Helix.
        Solo debe llamarse cuando isConnected() es True.
        Resultado llega como subscriptionAdded o subscriptionFailed.
        """
        if not self._session_id:
            self.logger.warning(f"[EventSub] createSubscription sin session_id — ignorado")
            return

        from Core import App
        from Services.Twitch.GQL.TwitchGQLConfig import Config as GQLConfig
        from Services.Twitch.EventSub.TwitchEventSubEvents import SubscriptionTypes

        payload = json.dumps({
            "type":      subscription_type,
            "version":   SubscriptionTypes.version(subscription_type),
            "condition": {"broadcaster_user_id": broadcaster_user_id},
            "transport": {"method": "websocket", "session_id": self._session_id},
        }).encode()

        request = QtNetwork.QNetworkRequest(QtCore.QUrl(Config.HELIX_SUBSCRIPTIONS))
        request.setHeader(
            QtNetwork.QNetworkRequest.KnownHeaders.ContentTypeHeader,
            "application/json"
        )
        request.setRawHeader(b"Client-Id",     GQLConfig.CLIENT_ID.encode())
        request.setRawHeader(b"Authorization", f"Bearer {App.Account.getOAuthToken()}".encode())

        gen = self._session_gen  # capturar generación actual
        reply = App.NetworkAccessManager.post(request, payload)
        reply.finished.connect(
            lambda r=reply, st=subscription_type, bid=broadcaster_user_id, g=gen:
                self._onCreateReply(r, st, bid, g)
        )

        self.logger.info(f"[EventSub] createSubscription → {subscription_type} for {broadcaster_user_id}")

    def deleteSubscription(self, subscription_id: str) -> None:
        """Elimina una suscripción EventSub via HTTP DELETE (best-effort)."""
        from Core import App
        from Services.Twitch.GQL.TwitchGQLConfig import Config as GQLConfig

        url = QtCore.QUrl(f"{Config.HELIX_SUBSCRIPTIONS}?id={subscription_id}")
        request = QtNetwork.QNetworkRequest(url)
        request.setRawHeader(b"Client-Id",     GQLConfig.CLIENT_ID.encode())
        request.setRawHeader(b"Authorization", f"Bearer {App.Account.getOAuthToken()}".encode())

        reply = App.NetworkAccessManager.deleteResource(request)
        reply.finished.connect(lambda r=reply: r.deleteLater())

        self.logger.debug(f"[EventSub] deleteSubscription {subscription_id}")

    # ── WebSocket interno ──────────────────────────────────────────────────────

    def _connectWs(self, url: str) -> None:
        ws = QtWebSockets.QWebSocket(parent=self)
        self._ws = ws
        ws.connected.connect(self._onWsConnected)
        ws.disconnected.connect(self._onWsDisconnected)
        ws.textMessageReceived.connect(self._onWsMessage)
        ws.errorOccurred.connect(self._onWsError)
        ws.open(QtNetwork.QNetworkRequest(QtCore.QUrl(url)))
        self.logger.info(f"[EventSub] Conectando a {url}")

    def _detachWs(self) -> None:
        """Desconecta todas las señales del WebSocket actual."""
        if self._ws is not None:
            try:
                self._ws.connected.disconnect(self._onWsConnected)
                self._ws.disconnected.disconnect(self._onWsDisconnected)
                self._ws.textMessageReceived.disconnect(self._onWsMessage)
                self._ws.errorOccurred.disconnect(self._onWsError)
            except Exception:
                pass

    def _onWsConnected(self) -> None:
        self.logger.info("[EventSub] WebSocket conectado — esperando session_welcome")

    def _onWsDisconnected(self) -> None:
        self.logger.info("[EventSub] WebSocket desconectado")
        self._keepalive_timer.stop()

        had_session = self._session_id is not None
        self._session_id = None

        if had_session:
            self.sessionLost.emit()

        if self._opened and not self._reconnect_timer.isActive():
            self._reconnect_timer.start()

    def _onWsError(self, error: QtNetwork.QAbstractSocket.SocketError) -> None:
        self.logger.error(f"[EventSub] Error WebSocket: {error}")

    def _onWsMessage(self, message: str) -> None:
        try:
            data      = json.loads(message)
            meta      = data.get("metadata", {})
            payload   = data.get("payload", {})
            msg_type  = meta.get("message_type", "")

            if msg_type == "session_welcome":
                self._session_gen   += 1
                self._session_id     = payload["session"]["id"]
                keepalive_secs       = payload["session"].get("keepalive_timeout_seconds", 10)
                self._keepalive_timer.setInterval(
                    keepalive_secs * 1_000 + Config.KEEPALIVE_MARGIN_MS
                )
                self._keepalive_timer.start()
                self.logger.info(f"[EventSub] session_welcome — id={self._session_id}")
                self.sessionReady.emit()

            elif msg_type == "session_keepalive":
                self._keepalive_timer.start()   # restart
                self.logger.debug("[EventSub] keepalive")

            elif msg_type == "notification":
                self._keepalive_timer.start()   # restart (las notificaciones también cuentan)
                sub_type     = meta.get("subscription_type", "")
                event_data   = payload.get("event", {})
                broadcaster_id = event_data.get("broadcaster_user_id", "")
                self.newEventReceived.emit(
                    EventSubEvent(sub_type, broadcaster_id, event_data)
                )
                self.logger.debug(f"[EventSub] notificación: {sub_type} channel={broadcaster_id}")

            elif msg_type == "session_reconnect":
                self._reconnect_url = payload["session"].get("reconnect_url")
                self.logger.info(f"[EventSub] session_reconnect → {self._reconnect_url}")
                # Cerrar el WS actual; _onWsDisconnected arrancará el timer de reconexión
                self._ws.close()

            elif msg_type == "revocation":
                sub_id = payload.get("subscription", {}).get("id", "")
                self.logger.info(f"[EventSub] suscripción revocada: {sub_id}")
                self.subscriptionRevoked.emit(sub_id)

            else:
                self.logger.debug(f"[EventSub] mensaje desconocido: {msg_type}")

        except Exception as e:
            self.logger.error(f"[EventSub] Error parseando mensaje: {e}\n{message[:200]}")

    def _onKeepaliveTimeout(self) -> None:
        self.logger.warning("[EventSub] Keepalive timeout — reconectando")
        if self._ws is not None:
            self._ws.close()

    def _reconnectTimerFired(self) -> None:
        if not self._opened:
            return
        url = self._reconnect_url or Config.HOST
        self._reconnect_url = None
        self.logger.info(f"[EventSub] Reconectando a {url}")
        # Reemplazar WebSocket (el anterior ya está cerrado/cerrandose)
        old_ws = self._ws
        self._connectWs(url)
        if old_ws is not None:
            old_ws.deleteLater()

    # ── Respuesta HTTP de createSubscription ──────────────────────────────────

    def _onCreateReply(
        self,
        reply: QtNetwork.QNetworkReply,
        subscription_type: str,
        broadcaster_user_id: str,
        gen: int,
    ) -> None:
        try:
            status = reply.attribute(
                QtNetwork.QNetworkRequest.Attribute.HttpStatusCodeAttribute
            )
            body = reply.readAll().data().decode(errors="ignore")

            # Ignorar respuesta si la sesión ya cambió
            if gen != self._session_gen:
                self.logger.debug(
                    f"[EventSub] respuesta HTTP de generación anterior (g={gen}) — ignorada"
                )
                return

            if status == 202:
                sub_data = json.loads(body)
                sub_id   = sub_data["data"][0]["id"]
                sub      = EventSubSubscription(sub_id, subscription_type, broadcaster_user_id)
                self.logger.info(f"[EventSub] suscripción OK: {subscription_type} → {sub_id}")
                self.subscriptionAdded.emit(sub)
            else:
                self.logger.error(
                    f"[EventSub] suscripción fallida ({status}): {subscription_type} "
                    f"channel={broadcaster_user_id}\n{body[:300]}"
                )
                self.subscriptionFailed.emit((subscription_type, broadcaster_user_id))

        except Exception as e:
            self.logger.error(f"[EventSub] Error procesando respuesta HTTP: {e}")
            self.subscriptionFailed.emit((subscription_type, broadcaster_user_id))
        finally:
            reply.deleteLater()
