"""
Download/ScheduledDownloadEventSubManager.py

Reemplaza ScheduledDownloadPubSubManager. En vez de LISTEN/UNLISTEN via PubSub
WebSocket, crea y elimina suscripciones EventSub via HTTP, y recibe los eventos
a través del WebSocket de TwitchEventSub.

Cada canal monitoreado obtiene tres suscripciones:
  - stream.online   (reemplaza video-playback-by-id → stream-up)
  - stream.offline  (reemplaza video-playback-by-id → stream-down)
  - channel.update  (reemplaza broadcast-settings-update)

Estado del suscriptor:
  - connecting  → _pending_count > 0  (HTTP requests en vuelo)
  - subscribed  → todos los sub IDs confirmados y _pending_count == 0
  - not-connected → sin sesión EventSub activa
"""
from Services.Logging.Logger import Logger
from Services.Twitch.EventSub.TwitchEventSub import TwitchEventSub, EventSubEvent, EventSubSubscription
from Services.Twitch.EventSub.TwitchEventSubEvents import SubscriptionTypes

from PyQt6 import QtCore

import uuid


class ScheduledDownloadEventSubSubscriber(QtCore.QObject):
    stateChanged    = QtCore.pyqtSignal()
    eventReceived   = QtCore.pyqtSignal(object)   # EventSubEvent
    removeRequested = QtCore.pyqtSignal(object)   # self

    SUBSCRIPTION_TYPES = [
        SubscriptionTypes.StreamOnline,
        SubscriptionTypes.StreamOffline,
        SubscriptionTypes.ChannelUpdate,
    ]

    def __init__(
        self,
        broadcaster_id: str,
        eventSub: TwitchEventSub,
        parent: QtCore.QObject | None = None,
    ):
        super().__init__(parent=parent)
        self.broadcaster_id = broadcaster_id
        self.eventSub       = eventSub

        # {subscription_id: subscription_type}
        self._subscriptions: dict[str, str] = {}
        self._pending_count  = 0
        self._clients: list[uuid.UUID] = []

        eventSub.sessionReady.connect(self._onSessionReady)
        eventSub.sessionLost.connect(self._onSessionLost)
        eventSub.subscriptionAdded.connect(self._onSubscriptionAdded)
        eventSub.subscriptionFailed.connect(self._onSubscriptionFailed)
        eventSub.subscriptionRevoked.connect(self._onSubscriptionRevoked)
        eventSub.newEventReceived.connect(self._onEventReceived)

        # Si ya hay sesión activa al momento de crearse, suscribirse de inmediato
        if eventSub.isConnected():
            self._subscribeAll()

    # ── API pública ────────────────────────────────────────────────────────────

    def hasClients(self) -> bool:
        return len(self._clients) != 0

    def addClient(self, client: uuid.UUID) -> None:
        self._clients.append(client)
        self._update()

    def removeClient(self, client: uuid.UUID) -> None:
        self._clients.remove(client)
        self._update()

    def isSubscribed(self) -> bool:
        return (
            len(self._subscriptions) == len(self.SUBSCRIPTION_TYPES)
            and self._pending_count == 0
        )

    def hasPendingRequest(self) -> bool:
        return self._pending_count > 0

    # ── Señales de TwitchEventSub ──────────────────────────────────────────────

    def _onSessionReady(self) -> None:
        """Nueva sesión disponible: limpiar estado anterior y re-suscribirse."""
        self._subscriptions.clear()
        self._pending_count = 0
        if self.hasClients():
            self._subscribeAll()
        self.stateChanged.emit()

    def _onSessionLost(self) -> None:
        """Sesión perdida: marcar como no suscrito."""
        self._subscriptions.clear()
        self._pending_count = 0
        self.stateChanged.emit()

    def _onSubscriptionAdded(self, sub: EventSubSubscription) -> None:
        if sub.broadcaster_user_id != self.broadcaster_id:
            return
        self._pending_count = max(0, self._pending_count - 1)
        self._subscriptions[sub.id] = sub.subscription_type
        self.stateChanged.emit()

    def _onSubscriptionFailed(self, info: tuple) -> None:
        sub_type, broadcaster_id = info
        if broadcaster_id != self.broadcaster_id:
            return
        self._pending_count = max(0, self._pending_count - 1)
        self.stateChanged.emit()

    def _onSubscriptionRevoked(self, subscription_id: str) -> None:
        if subscription_id not in self._subscriptions:
            return
        self._subscriptions.pop(subscription_id)
        self.stateChanged.emit()
        # Re-suscribir el tipo revocado si todavía hay clientes y hay sesión
        if self.hasClients() and self.eventSub.isConnected():
            # Re-suscribir todos los que falten
            confirmed_types = set(self._subscriptions.values())
            for sub_type in self.SUBSCRIPTION_TYPES:
                if sub_type not in confirmed_types:
                    self._pending_count += 1
                    self.eventSub.createSubscription(sub_type, self.broadcaster_id)
            self.stateChanged.emit()

    def _onEventReceived(self, event: EventSubEvent) -> None:
        if event.broadcaster_user_id == self.broadcaster_id:
            self.eventReceived.emit(event)

    # ── Helpers internos ───────────────────────────────────────────────────────

    def _subscribeAll(self) -> None:
        """Lanza HTTP POST para los tipos que todavía no están confirmados."""
        confirmed_types = set(self._subscriptions.values())
        for sub_type in self.SUBSCRIPTION_TYPES:
            if sub_type not in confirmed_types:
                self._pending_count += 1
                self.eventSub.createSubscription(sub_type, self.broadcaster_id)
        self.stateChanged.emit()

    def _unsubscribeAll(self) -> None:
        """Elimina todas las suscripciones confirmadas via HTTP DELETE."""
        for sub_id in list(self._subscriptions.keys()):
            self.eventSub.deleteSubscription(sub_id)
        self._subscriptions.clear()
        self._pending_count = 0
        self.stateChanged.emit()

    def _update(self) -> None:
        """Ajusta el estado según si hay clientes o no."""
        if not self.hasClients():
            if self._subscriptions or self._pending_count > 0:
                self._unsubscribeAll()
            # Pedir al manager que nos elimine
            self.removeRequested.emit(self)


class ScheduledDownloadEventSubManager(QtCore.QObject):
    """
    Equivalente a ScheduledDownloadPubSubManager.
    Gestiona un TwitchEventSub compartido y un suscriptor por canal.
    """

    def __init__(self, logger: Logger, parent: QtCore.QObject | None = None):
        super().__init__(parent=parent)
        self.eventSub    = TwitchEventSub(logger, parent=self)
        self.subscribers: dict[str, ScheduledDownloadEventSubSubscriber] = {}

    def open(self) -> None:
        self.eventSub.open()

    def close(self) -> None:
        self.eventSub.close()

    def isOpened(self) -> bool:
        return self.eventSub.isOpened()

    def isConnected(self) -> bool:
        return self.eventSub.isConnected()

    def subscribe(
        self, broadcaster_id: str, key: uuid.UUID
    ) -> ScheduledDownloadEventSubSubscriber:
        if broadcaster_id not in self.subscribers:
            subscriber = ScheduledDownloadEventSubSubscriber(
                broadcaster_id, self.eventSub, parent=self
            )
            subscriber.removeRequested.connect(self._onRemoveRequested)
            self.subscribers[broadcaster_id] = subscriber
        else:
            subscriber = self.subscribers[broadcaster_id]
        subscriber.addClient(key)
        return subscriber

    def unsubscribe(self, broadcaster_id: str, key: uuid.UUID) -> None:
        if broadcaster_id in self.subscribers:
            self.subscribers[broadcaster_id].removeClient(key)

    def _onRemoveRequested(self, subscriber: ScheduledDownloadEventSubSubscriber) -> None:
        self.subscribers.pop(subscriber.broadcaster_id, None)
        subscriber.deleteLater()
