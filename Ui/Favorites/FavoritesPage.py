"""
Ui/Favorites/FavoritesPage.py

Paleta unificada con la app via App.Instance.palette().
Botones nativos via Icons + ThemedIconViewer.
Secciones "EN VIVO" / "OFFLINE" con headers dinámicos.
"""
from __future__ import annotations
from Services.Favorites.FavoritesManager import (
    FavoritesManager, FavoriteChannel, SortCriteria,
)
from Services.Image.Presets import Icons
from Services.Theme.ThemedIconViewer import ThemedIconViewer
from PyQt6 import QtCore, QtGui, QtWidgets, QtNetwork
import time as _time

# ─── Paleta dinámica ──────────────────────────────────────────────────────────
_P: dict = {}

def _build_palette() -> None:
    from Core import App
    pal = App.Instance.palette()
    R   = QtGui.QPalette.ColorRole
    G   = QtGui.QPalette.ColorGroup

    def h(role: R, group: G = G.Active) -> str:
        return pal.color(group, role).name()

    def rgba(role: R, alpha: float, group: G = G.Active) -> str:
        c = pal.color(group, role)
        return f"rgba({c.red()},{c.green()},{c.blue()},{alpha})"

    win  = pal.color(G.Active, R.Window)
    base = pal.color(G.Active, R.Base)
    text = pal.color(G.Active, R.WindowText)
    mid  = pal.color(G.Active, R.Mid)
    is_dark = win.lightness() < 128

    d = 14 if is_dark else -10
    card_h = QtGui.QColor(
        max(0, min(255, base.red()   + d)),
        max(0, min(255, base.green() + d)),
        max(0, min(255, base.blue()  + d)),
    ).name()
    aff = "#454560" if is_dark else "#9898c8"

    _P.update({
        "bg":        win.name(),
        "card":      base.name(),
        "card_h":    card_h,
        "sep":       mid.name(),
        "purple":    "#9147ff",
        "purple_d":  "#7b3fe4",
        "purple_bg": "rgba(145,71,255,0.15)",
        "red":       "#e91916",
        "text":      text.name(),
        "dim":       rgba(R.WindowText, 0.65),
        "mute":      rgba(R.WindowText, 0.38),
        "partner":   "#9147ff",
        "affiliate": aff,
    })

# ─── Caché de imágenes LRU (máx 120) ─────────────────────────────────────────
from collections import OrderedDict
_CACHE: OrderedDict[str, QtGui.QPixmap] = OrderedDict()
_CACHE_MAX = 120

def _cache_put(key: str, pm: QtGui.QPixmap) -> None:
    if key in _CACHE:
        _CACHE.move_to_end(key)
    else:
        _CACHE[key] = pm
        if len(_CACHE) > _CACHE_MAX:
            _CACHE.popitem(last=False)
        return
    _CACHE[key] = pm

def _load(label: QtWidgets.QLabel, url: str, w: int, h: int, circle=False) -> None:
    if not url:
        return
    key = f"{url}|{w}x{h}|{'c' if circle else 'r'}"
    if key in _CACHE:
        _CACHE.move_to_end(key)
        label.setPixmap(_CACHE[key])
        return
    from Core import App
    req   = QtNetwork.QNetworkRequest(QtCore.QUrl(url))
    reply = App.NetworkAccessManager.get(req)
    def _done():
        if reply.error() == QtNetwork.QNetworkReply.NetworkError.NoError:
            data = reply.readAll()
            pm   = QtGui.QPixmap()
            pm.loadFromData(data)
            if not pm.isNull():
                pm = _scale(pm, w, h, circle)
                _cache_put(key, pm)
                label.setPixmap(pm)
        reply.deleteLater()
    reply.finished.connect(_done)

def _scale(src: QtGui.QPixmap, w: int, h: int, circle: bool) -> QtGui.QPixmap:
    sc = src.scaled(w, h,
                    QtCore.Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    QtCore.Qt.TransformationMode.SmoothTransformation)
    x, y = (sc.width()-w)//2, (sc.height()-h)//2
    cr   = sc.copy(x, y, w, h)
    if not circle:
        return cr
    out = QtGui.QPixmap(w, h)
    out.fill(QtCore.Qt.GlobalColor.transparent)
    p = QtGui.QPainter(out)
    p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
    path = QtGui.QPainterPath()
    path.addEllipse(0, 0, w, h)
    p.setClipPath(path)
    p.drawPixmap(0, 0, cr)
    p.end()
    return out

def _avatar_ph(size: int) -> QtGui.QPixmap:
    pm = QtGui.QPixmap(size, size)
    pm.fill(QtCore.Qt.GlobalColor.transparent)
    p  = QtGui.QPainter(pm)
    p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
    p.setBrush(QtGui.QColor(_P.get("sep", "#3d3d56")))
    p.setPen(QtCore.Qt.PenStyle.NoPen)
    p.drawEllipse(0, 0, size, size)
    p.end()
    return pm

def _thumb_ph(w: int, h: int, offline=False) -> QtGui.QPixmap:
    pm = QtGui.QPixmap(w, h)
    pm.fill(QtGui.QColor(_P.get("bg", "#1f1f23")))
    if offline:
        p = QtGui.QPainter(pm)
        p.setPen(QtGui.QColor(_P.get("mute", "#727278")))
        f = p.font(); f.setPointSize(10); p.setFont(f)
        p.drawText(pm.rect(), QtCore.Qt.AlignmentFlag.AlignCenter, "OFFLINE")
        p.end()
    return pm


# ─── Header de sección ────────────────────────────────────────────────────────
class _SectionHeader(QtWidgets.QWidget):
    """
    Separador visual entre secciones EN VIVO / OFFLINE.
    Muestra un punto de color, el label, una línea separadora y el contador.
    Si collapsible=True, se puede colapsar/expandir haciendo clic.
    """
    toggled = QtCore.pyqtSignal(bool)   # emite True cuando se colapsa

    def __init__(self, label: str, live: bool, collapsible: bool = False, parent=None):
        super().__init__(parent=parent)
        if not _P:
            _build_palette()
        self._live        = live
        self._count       = 0
        self._collapsible = collapsible
        self._collapsed   = False
        self.setFixedHeight(32)
        self.setStyleSheet("background:transparent;")

        if collapsible:
            self.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))

        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(12, 0, 16, 0)
        lay.setSpacing(8)

        # Punto de estado
        dot = QtWidgets.QLabel("●")
        dot.setFixedWidth(10)
        dot_color = _P["purple"] if live else _P["sep"]
        dot.setStyleSheet(f"font-size:8px;color:{dot_color};")
        lay.addWidget(dot)

        # Texto de sección
        lbl = QtWidgets.QLabel(label)
        lbl.setStyleSheet(
            f"font-size:10px;font-weight:700;letter-spacing:1px;color:{_P['dim']};"
        )
        lay.addWidget(lbl)

        # Línea separadora
        line = QtWidgets.QFrame()
        line.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        line.setStyleSheet(f"color:{_P['sep']};")
        lay.addWidget(line, 1)

        # Contador
        self._count_lbl = QtWidgets.QLabel("0")
        self._count_lbl.setFixedWidth(24)
        self._count_lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight |
                                     QtCore.Qt.AlignmentFlag.AlignVCenter)
        self._count_lbl.setStyleSheet(f"font-size:10px;color:{_P['mute']};")
        lay.addWidget(self._count_lbl)

        # Chevron al final, lado derecho (solo en secciones colapsables)
        if collapsible:
            self._chevron = QtWidgets.QLabel("▼")
            self._chevron.setFixedWidth(14)
            self._chevron.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            self._chevron.setStyleSheet(f"font-size:9px;color:{_P['dim']};")
            lay.addWidget(self._chevron)

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        if self._collapsible and event.button() == QtCore.Qt.MouseButton.LeftButton:
            self._collapsed = not self._collapsed
            self._chevron.setText("▶" if self._collapsed else "▼")
            self.toggled.emit(self._collapsed)
        super().mousePressEvent(event)

    def is_collapsed(self) -> bool:
        return self._collapsed

    def set_count(self, n: int) -> None:
        self._count = n
        self._count_lbl.setText(str(n))
        self.setVisible(n > 0)


# ─── Uptime ───────────────────────────────────────────────────────────────────
class _Uptime(QtWidgets.QLabel):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self._start: QtCore.QDateTime | None = None
        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._tick)
        self.setStyleSheet(
            "background:rgba(0,0,0,0.72);color:#efeff1;"
            "font-size:10px;font-weight:700;padding:2px 6px;border-radius:3px;"
        )
        self.hide()

    def set_start(self, dt):
        self._start = dt
        if dt and dt.isValid():
            self._tick(); self._timer.start(); self.show()
        else:
            self._timer.stop(); self.hide()

    def _tick(self):
        if not self._start: return
        s = max(0, self._start.secsTo(QtCore.QDateTime.currentDateTimeUtc()))
        h, r = divmod(s, 3600); m, sec = divmod(r, 60)
        self.setText(f" {h:02d}:{m:02d}:{sec:02d} ")
        self.adjustSize()

    def stop(self):
        self._timer.stop(); self.hide()


# ─── Card ─────────────────────────────────────────────────────────────────────
class ChannelCard(QtWidgets.QWidget):
    openInApp     = QtCore.pyqtSignal(str)
    openInBrowser = QtCore.pyqtSignal(str)
    removeFav     = QtCore.pyqtSignal(str)

    TW, TH, AV = 210, 118, 52

    def __init__(self, ch: FavoriteChannel, parent=None):
        super().__init__(parent=parent)
        if not _P:
            _build_palette()
        self._login    = ch.login
        self._last_url = ""
        self._is_live  = False
        from Core import App
        self._notif_on      = App.Preferences.favorites.get_notif_pref(ch.login)
        self._tc            = None
        self._ref_btn       = None
        self._notif_btn     = None
        self._del_btn       = None
        self._bell_viewer: ThemedIconViewer | None = None
        self.setFixedHeight(self.TH + 24)
        self.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
        self._build()
        self.update_state(ch)

    # ── Borde izquierdo de estado ─────────────────────────────────────────────
    def paintEvent(self, event):
        super().paintEvent(event)
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        p.setBrush(QtGui.QColor(_P["purple"] if self._is_live else _P["sep"]))
        p.setPen(QtCore.Qt.PenStyle.NoPen)
        p.drawRoundedRect(0, 6, 3, self.height() - 12, 2, 2)
        p.end()

    # ── Eventos ──────────────────────────────────────────────────────────────
    def mousePressEvent(self, ev):
        if ev.button() == QtCore.Qt.MouseButton.LeftButton:
            self.openInBrowser.emit(self._login)

    def contextMenuEvent(self, ev):
        menu = QtWidgets.QMenu(self)
        menu.addAction("🌐  Abrir en Twitch.tv",
                       lambda: self.openInBrowser.emit(self._login))
        menu.addAction("▶  Buscar en TwitchLink",
                       lambda: self.openInApp.emit(self._login))
        menu.addSeparator()
        menu.addAction("✕  Quitar de favoritos",
                       lambda: self.removeFav.emit(self._login))
        menu.exec(ev.globalPos())

    def eventFilter(self, obj, ev):
        tc = getattr(self, "_tc", None)
        if tc and obj == tc:
            if ev.type() == QtCore.QEvent.Type.Enter:
                ref = getattr(self, "_ref_btn", None)
                if ref: ref.show()
            elif ev.type() == QtCore.QEvent.Type.Leave:
                ref = getattr(self, "_ref_btn", None)
                if ref: ref.hide()
        return super().eventFilter(obj, ev)

    # ── Construcción ─────────────────────────────────────────────────────────
    def _build(self):
        root = QtWidgets.QHBoxLayout(self)
        root.setContentsMargins(8, 9, 4, 9)
        root.setSpacing(0)

        # Thumbnail
        tc = QtWidgets.QWidget()
        tc.setFixedSize(self.TW, self.TH)
        tc.setStyleSheet(f"background:{_P['bg']};border-radius:4px;")
        tc.installEventFilter(self)
        self._tc = tc

        self._thumb = QtWidgets.QLabel(tc)
        self._thumb.setFixedSize(self.TW, self.TH)
        self._thumb.setPixmap(_thumb_ph(self.TW, self.TH))
        self._thumb.setStyleSheet("border-radius:4px;")

        self._overlay = QtWidgets.QLabel(tc)
        self._overlay.setFixedSize(self.TW, self.TH)
        self._overlay.setStyleSheet("background:rgba(0,0,0,0.42);border-radius:4px;")
        self._overlay.hide()

        self._thumb_badge = QtWidgets.QLabel(tc)
        self._thumb_badge.setStyleSheet(
            "background:rgba(0,0,0,0.72);color:#fff;"
            "font-size:9px;font-weight:700;padding:2px 6px;border-radius:3px;"
        )
        self._thumb_badge.hide()

        self._uptime = _Uptime(tc)

        self._ref_btn = QtWidgets.QToolButton(tc)
        self._ref_btn.setText("↺")
        self._ref_btn.setFixedSize(20, 20)
        self._ref_btn.move(self.TW - 24, 4)
        self._ref_btn.setStyleSheet(
            "QToolButton{background:rgba(0,0,0,0.65);color:#fff;"
            "font-size:12px;border:none;border-radius:3px;}"
            f"QToolButton:hover{{background:{_P['purple']};}}"
        )
        self._ref_btn.setToolTip("Actualizar imagen")
        self._ref_btn.hide()
        self._ref_btn.clicked.connect(self._force_refresh)

        root.addWidget(tc)
        root.addSpacing(12)

        # Info
        info_w = QtWidgets.QWidget()
        info_w.setStyleSheet("background:transparent;")
        info = QtWidgets.QVBoxLayout(info_w)
        info.setContentsMargins(0, 0, 4, 0)
        info.setSpacing(3)

        r1 = QtWidgets.QHBoxLayout()
        r1.setSpacing(8); r1.setContentsMargins(0, 0, 0, 0)

        self._avatar = QtWidgets.QLabel()
        self._avatar.setFixedSize(self.AV, self.AV)
        self._avatar.setPixmap(_avatar_ph(self.AV))
        self._avatar.setStyleSheet(
            f"border-radius:{self.AV//2}px;border:2px solid {_P['sep']};"
        )
        r1.addWidget(self._avatar, 0, QtCore.Qt.AlignmentFlag.AlignVCenter)

        name_col = QtWidgets.QVBoxLayout()
        name_col.setSpacing(1); name_col.setContentsMargins(0, 0, 0, 0)

        name_row = QtWidgets.QHBoxLayout()
        name_row.setSpacing(5)
        self._name = QtWidgets.QLabel()
        self._name.setStyleSheet(
            f"font-weight:700;font-size:14px;color:{_P['text']};"
        )
        name_row.addWidget(self._name)

        self._role_badge = QtWidgets.QLabel()
        self._role_badge.setFixedSize(16, 16)
        self._role_badge.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._role_badge.hide()
        name_row.addWidget(self._role_badge)
        name_row.addStretch()
        name_col.addLayout(name_row)

        self._viewers = QtWidgets.QLabel()
        self._viewers.setStyleSheet(f"font-size:11px;color:{_P['dim']};")
        name_col.addWidget(self._viewers)

        r1.addLayout(name_col, 1)
        info.addLayout(r1)

        self._title = QtWidgets.QLabel()
        self._title.setStyleSheet(
            f"font-size:12px;color:{_P['text']};font-weight:500;"
        )
        self._title.setWordWrap(True)
        self._title.setMaximumHeight(34)
        info.addWidget(self._title)

        self._sub_info = QtWidgets.QLabel()
        self._sub_info.setStyleSheet(f"font-size:11px;color:{_P['dim']};")
        info.addWidget(self._sub_info)

        self._partner_pill = QtWidgets.QLabel()
        self._partner_pill.setFixedHeight(18)
        self._partner_pill.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._partner_pill.hide()
        info.addWidget(self._partner_pill, 0, QtCore.Qt.AlignmentFlag.AlignLeft)

        info.addStretch()
        root.addWidget(info_w, 1)

        # Acciones — botones nativos
        act_w = QtWidgets.QWidget()
        act_w.setFixedWidth(44)
        act_w.setStyleSheet("background:transparent;")
        ac = QtWidgets.QVBoxLayout(act_w)
        ac.setContentsMargins(0, 0, 8, 0)
        ac.setSpacing(4)
        ac.setAlignment(QtCore.Qt.AlignmentFlag.AlignVCenter)

        # Abrir en TwitchLink (buscar canal en la app)
        self._app_btn = QtWidgets.QPushButton()
        self._app_btn.setFixedSize(28, 28)
        self._app_btn.setFlat(True)
        self._app_btn.setToolTip("Buscar en TwitchLink")
        self._app_btn.setIconSize(QtCore.QSize(18, 18))
        self._app_btn.clicked.connect(
            lambda: self.openInApp.emit(self._login)
        )
        ThemedIconViewer(self._app_btn, Icons.LAUNCH)
        ac.addWidget(self._app_btn, 0, QtCore.Qt.AlignmentFlag.AlignHCenter)

        # Notificaciones
        self._notif_btn = QtWidgets.QPushButton()
        self._notif_btn.setFixedSize(28, 28)
        self._notif_btn.setFlat(True)
        self._notif_btn.setToolTip("Activar/desactivar notificaciones")
        self._notif_btn.setIconSize(QtCore.QSize(18, 18))
        self._notif_btn.clicked.connect(self._toggle_notif)
        self._bell_viewer = ThemedIconViewer(
            self._notif_btn,
            Icons.BELL if self._notif_on else Icons.BELL_OFF
        )
        self._update_notif_style()
        ac.addWidget(self._notif_btn, 0, QtCore.Qt.AlignmentFlag.AlignHCenter)

        # Eliminar
        self._del_btn = QtWidgets.QPushButton()
        self._del_btn.setFixedSize(28, 28)
        self._del_btn.setFlat(True)
        self._del_btn.setToolTip("Quitar de favoritos")
        self._del_btn.setIconSize(QtCore.QSize(18, 18))
        self._del_btn.clicked.connect(lambda: self.removeFav.emit(self._login))
        ThemedIconViewer(self._del_btn, Icons.TRASH)
        ac.addWidget(self._del_btn, 0, QtCore.Qt.AlignmentFlag.AlignHCenter)

        root.addWidget(act_w)

    def _update_notif_style(self):
        if self._notif_on:
            self._notif_btn.setStyleSheet(
                f"QPushButton{{border-radius:5px;color:{_P['purple']};}}"
                f"QPushButton:hover{{background:{_P['purple_bg']};}}"
            )
        else:
            self._notif_btn.setStyleSheet(
                "QPushButton{border-radius:5px;}"
                "QPushButton:hover{background:rgba(128,128,128,0.15);}"
            )

    def _toggle_notif(self):
        self._notif_on = not self._notif_on
        self._bell_viewer.setIcon(Icons.BELL if self._notif_on else Icons.BELL_OFF)
        self._update_notif_style()
        from Core import App
        App.Preferences.favorites.set_notif_pref(self._login, self._notif_on)

    # ── Hover ─────────────────────────────────────────────────────────────────
    def enterEvent(self, ev):
        self.setStyleSheet(f"background:{_P['card_h']};border-radius:8px;")
        super().enterEvent(ev)

    def leaveEvent(self, ev):
        self.setStyleSheet(f"background:{_P['card']};border-radius:8px;")
        super().leaveEvent(ev)

    # ── Actualización ─────────────────────────────────────────────────────────
    def update_state(self, ch: FavoriteChannel):
        self._is_live = ch.is_live
        self._name.setText(ch.display_name)
        self.setStyleSheet(f"background:{_P['card']};border-radius:8px;")
        self.update()

        _PARTNER_BADGE = (
            "https://static-cdn.jtvnw.net/badges/v1/"
            "d12a2e27-16f6-41d0-ab77-b780518f00a3/1"
        )
        _STAFF_BADGE = (
            "https://static-cdn.jtvnw.net/badges/v1/"
            "d97c37a7-0191-47ef-9dc5-30c7d65e0ffd/1"
        )
        if ch.is_staff:
            self._role_badge.setText("")
            self._role_badge.setStyleSheet("")
            _load(self._role_badge, _STAFF_BADGE, 16, 16)
            self._role_badge.setToolTip("Staff de Twitch")
            self._role_badge.show()
        elif ch.is_partner:
            self._role_badge.setText("")
            self._role_badge.setStyleSheet("")
            _load(self._role_badge, _PARTNER_BADGE, 16, 16)
            self._role_badge.setToolTip("Partner de Twitch")
            self._role_badge.show()
        elif ch.is_affiliate:
            self._role_badge.setText("◈")
            self._role_badge.setFixedSize(16, 16)
            self._role_badge.setStyleSheet(
                f"background:{_P['affiliate']};color:{_P['dim']};"
                "font-size:9px;font-weight:700;border-radius:3px;"
            )
            self._role_badge.setToolTip("Afiliado de Twitch")
            self._role_badge.show()
        else:
            self._role_badge.hide()

        border_color = _P["purple"] if ch.is_live else _P["sep"]
        self._avatar.setStyleSheet(
            f"border-radius:{self.AV//2}px;border:2px solid {border_color};"
        )

        if ch.is_live:
            self._thumb_badge.setText("  🔴 Live  ")
            self._thumb_badge.adjustSize()
            self._thumb_badge.show()
            self._overlay.hide()

            v = ch.viewers
            self._viewers.setText(f"👁  {v:,}" if v else "En vivo")
            self._viewers.show()

            title = ch.stream_title or ""
            if len(title) > 80: title = title[:80] + "…"
            self._title.setText(title)
            self._title.setStyleSheet(
                f"font-size:12px;color:{_P['text']};font-weight:500;"
            )

            game = ch.game_name
            if game:
                self._sub_info.setText(f"🎮  {game}")
                if ch.box_art_url:
                    art = ch.box_art_url.replace("{width}", "40").replace("{height}", "53")
                    self._sub_info.setToolTip(
                        f"<img src='{art}' width=40 height=53><br>{game}"
                    )
            else:
                self._sub_info.setText("")
            self._sub_info.show()
            self._partner_pill.hide()

            start = (
                ch.stream.createdAt
                if ch.stream and ch.stream.createdAt
                   and ch.stream.createdAt.isValid()
                else None
            )
            self._uptime.set_start(start)
            QtCore.QTimer.singleShot(50, self._fix_overlays)

            raw = ch.stream.previewImageURL if ch.stream else ""
            if raw:
                ts  = int(_time.time()) // 60
                url = (raw.replace("{width}", str(self.TW * 2))
                          .replace("{height}", str(self.TH * 2))
                       + f"?t={ts}")
                if url != self._last_url:
                    self._last_url = url
                    _load(self._thumb, url, self.TW, self.TH)
        else:
            self._thumb_badge.hide()
            self._overlay.show()
            self._uptime.stop()
            self._last_url = ""
            self._viewers.hide()

            desc = ""
            if ch.last_broadcast:
                desc = getattr(ch.last_broadcast, "title", "") or ""
            if len(desc) > 80: desc = desc[:80] + "…"
            self._title.setText(desc)
            self._title.setStyleSheet(f"font-size:12px;color:{_P['dim']};")

            parts = [ch.followers_str, ch.last_broadcast_str]
            self._sub_info.setText("  ·  ".join(p for p in parts if p))
            self._sub_info.setToolTip("")
            self._sub_info.show()

            if ch.is_partner:
                self._partner_pill.setText("  Partner Streamer  ")
                self._partner_pill.setStyleSheet(
                    f"background:{_P['partner']};color:#fff;"
                    "border-radius:4px;font-size:8px;font-weight:700;padding:0 7px;"
                )
                self._partner_pill.show()
            elif ch.is_affiliate:
                self._partner_pill.setText("  Afiliado  ")
                self._partner_pill.setStyleSheet(
                    f"background:{_P['affiliate']};color:{_P['dim']};"
                    "border-radius:4px;font-size:8px;font-weight:700;padding:0 7px;"
                )
                self._partner_pill.show()
            else:
                self._partner_pill.hide()

            off = ch.offline_image
            if off and off != self._last_url:
                self._last_url = off
                _load(self._thumb, off, self.TW, self.TH)
            elif not off:
                self._thumb.setPixmap(_thumb_ph(self.TW, self.TH, offline=True))

        if ch.profile_image_url:
            _load(self._avatar, ch.profile_image_url, self.AV, self.AV, circle=True)

    def _fix_overlays(self):
        self._uptime.adjustSize()
        self._uptime.move(4, self.TH - self._uptime.height() - 3)
        if self._thumb_badge.isVisible():
            self._thumb_badge.adjustSize()
            bw = self._thumb_badge.width()
            self._thumb_badge.move(
                self.TW - bw - 4,
                self.TH - self._thumb_badge.height() - 3
            )

    def _force_refresh(self):
        base = self._last_url.split("?")[0]
        for k in [k for k in list(_CACHE) if base in k]:
            del _CACHE[k]
        ts = int(_time.time())
        self._last_url = f"{base}?t={ts}"
        _load(self._thumb, self._last_url, self.TW, self.TH)

    def closeEvent(self, e):
        self._uptime.stop()
        super().closeEvent(e)


# ─── Diálogo añadir ───────────────────────────────────────────────────────────
class _AddDialog(QtWidgets.QDialog):
    confirmed = QtCore.pyqtSignal(str)
    _RE = QtCore.QRegularExpression(r"^[a-zA-Z0-9_]{1,25}$")

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        if not _P:
            _build_palette()
        self.setWindowTitle("Agregar canal favorito")
        self.setFixedSize(440, 145)
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 14); lay.setSpacing(10)

        lay.addWidget(QtWidgets.QLabel("Nombre de usuario o URL de Twitch:"))

        self._edit = QtWidgets.QLineEdit()
        self._edit.setPlaceholderText("maryblog   ·   https://www.twitch.tv/maryblog")
        self._edit.setMinimumHeight(30)
        self._edit.textChanged.connect(self._on_change)
        self._edit.returnPressed.connect(self._confirm)
        lay.addWidget(self._edit)

        self._preview = QtWidgets.QLabel("")
        self._preview.setStyleSheet(f"font-size:10px;color:{_P['purple']};")
        lay.addWidget(self._preview)

        br = QtWidgets.QHBoxLayout(); br.addStretch()
        c  = QtWidgets.QPushButton("Cancelar")
        c.clicked.connect(self.reject)
        self._ok = QtWidgets.QPushButton("Agregar")
        self._ok.setDefault(True); self._ok.setEnabled(False)
        self._ok.setStyleSheet(
            f"QPushButton{{background:{_P['purple']};color:#fff;"
            "border:none;border-radius:5px;padding:4px 18px;font-weight:600;}}"
            f"QPushButton:hover{{background:{_P['purple_d']};}}"
            "QPushButton:disabled{opacity:0.4;}"
        )
        self._ok.clicked.connect(self._confirm)
        br.addWidget(c); br.addWidget(self._ok)
        lay.addLayout(br)

    @staticmethod
    def _parse(raw: str) -> str:
        import re
        t = raw.strip()
        if not t: return ""
        if re.match(r"^(?:https?://)?(?:www\.)?twitch\.tv/", t, re.IGNORECASE):
            if not t.lower().startswith("http"): t = "https://" + t
            from urllib.parse import urlparse
            parts = [p for p in urlparse(t).path.split("/") if p]
            return parts[0].lower() if parts else ""
        return t.lower().split("/")[-1].split("?")[0] if "/" in t else t.lower()

    def _on_change(self, text):
        login = self._parse(text)
        if not login:
            self._preview.setText(""); self._ok.setEnabled(False); return
        if self._RE.match(login).hasMatch():
            self._preview.setText(f"✓  twitch.tv/{login}")
            self._preview.setStyleSheet(
                f"font-size:10px;color:{_P['purple']};font-weight:600;"
            )
            self._ok.setEnabled(True)
        else:
            self._preview.setText(f'✗  "{login}" no es válido')
            self._preview.setStyleSheet(f"font-size:10px;color:{_P['red']};")
            self._ok.setEnabled(False)

    def _confirm(self):
        login = self._parse(self._edit.text())
        if not login or not self._RE.match(login).hasMatch():
            return
        self.confirmed.emit(login); self.accept()


# ─── Página ───────────────────────────────────────────────────────────────────
class FavoritesPage(QtWidgets.QWidget):
    openChannelRequested = QtCore.pyqtSignal(str)
    openBrowserRequested = QtCore.pyqtSignal(str)

    def __init__(self, manager: FavoritesManager, page_object, parent=None):
        super().__init__(parent=parent)
        if not _P:
            _build_palette()
        self._mgr      = manager
        self._page_obj = page_object
        self._cards: dict[str, ChannelCard] = {}
        self._build()
        self._connect()
        self._reload_all()

    def _build(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0); root.setSpacing(0)
        self.setStyleSheet(f"background:{_P['bg']};")

        # Header
        hdr = QtWidgets.QWidget()
        hdr.setFixedHeight(46)
        hdr.setStyleSheet(
            f"background:{_P['bg']};border-bottom:1px solid {_P['sep']};"
        )
        hl = QtWidgets.QHBoxLayout(hdr)
        hl.setContentsMargins(16, 0, 10, 0); hl.setSpacing(8)

        title_lbl = QtWidgets.QLabel("Favoritos")
        title_lbl.setStyleSheet(
            f"font-size:15px;font-weight:700;color:{_P['text']};"
        )
        hl.addWidget(title_lbl)
        hl.addStretch()

        self._spin = QtWidgets.QLabel("")
        self._spin.setStyleSheet(f"font-size:14px;color:{_P['purple']};")
        self._spin.setFixedWidth(18)
        hl.addWidget(self._spin)

        for icon, tip, slot in [
            ("☰",  "Ordenar",      self._show_sort_menu),
            ("↺",  "Actualizar",   self._mgr.poll_now),
            ("＋", "Añadir canal", self._on_add),
        ]:
            btn = QtWidgets.QToolButton()
            btn.setText(icon)
            btn.setFixedSize(30, 30)
            btn.setToolTip(tip)
            btn.setStyleSheet(
                f"QToolButton{{font-size:14px;border:none;border-radius:5px;"
                f"color:{_P['dim']};}}"
                f"QToolButton:hover{{background:rgba(128,128,128,0.15);"
                f"color:{_P['text']};}}"
            )
            btn.clicked.connect(slot)
            hl.addWidget(btn)

        root.addWidget(hdr)

        # Lista scrollable
        self._scroll = QtWidgets.QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(
            QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._scroll.setStyleSheet(f"background:{_P['bg']};")

        self._list_w = QtWidgets.QWidget()
        self._list_w.setStyleSheet(f"background:{_P['bg']};")
        self._list_l = QtWidgets.QVBoxLayout(self._list_w)
        self._list_l.setContentsMargins(8, 6, 8, 6)
        self._list_l.setSpacing(2)
        self._list_l.addStretch()
        self._scroll.setWidget(self._list_w)
        root.addWidget(self._scroll, 1)

        # Sección headers — se insertan/remueven en _rebuild_layout
        self._hdr_live    = _SectionHeader("EN VIVO", live=True,  collapsible=False, parent=self._list_w)
        self._hdr_offline = _SectionHeader("OFFLINE", live=False, collapsible=True,  parent=self._list_w)

        # Placeholder vacío
        self._empty = QtWidgets.QWidget()
        self._empty.setStyleSheet(f"background:{_P['bg']};")
        el = QtWidgets.QVBoxLayout(self._empty)
        el.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        for txt, ss in [
            ("♡", f"font-size:48px;color:{_P['purple']};"),
            ("Sin canales favoritos",
             f"font-size:14px;color:{_P['dim']};font-weight:600;"),
            ("Haz clic en  ＋  para añadir tu primer canal",
             f"font-size:11px;color:{_P['mute']};"),
        ]:
            lbl = QtWidgets.QLabel(txt)
            lbl.setStyleSheet(ss)
            lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            el.addWidget(lbl)
        be = QtWidgets.QPushButton("＋  Añadir canal")
        be.setFixedHeight(34)
        be.setStyleSheet(
            f"QPushButton{{background:{_P['purple']};color:#fff;"
            "border:none;border-radius:8px;font-size:12px;padding:0 24px;margin-top:8px;}}"
            f"QPushButton:hover{{background:{_P['purple_d']};}}"
        )
        be.clicked.connect(self._on_add)
        el.addWidget(be, 0, QtCore.Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self._empty, 1)

    def _connect(self):
        m = self._mgr
        m.channelAdded.connect(self._on_added)
        m.channelRemoved.connect(self._on_removed)
        m.channelUpdated.connect(self._on_updated)
        m.liveCountChanged.connect(self._on_live_count)
        m.sortCriteriaChanged.connect(lambda _: self._reload_all())
        m.listReordered.connect(self._reload_all)
        m.pollStarted.connect(self._on_poll_start)
        m.pollFinished.connect(lambda: self._spin.setText(""))
        self._hdr_offline.toggled.connect(lambda _: self._rebuild_layout())

    # ── Reconstrucción del layout con secciones ───────────────────────────────
    def _rebuild_layout(self):
        """Reordena todos los widgets en el layout respetando secciones."""
        lay = self._list_l

        # Sacar todos los widgets del layout (sin destruirlos)
        while lay.count() > 0:
            item = lay.takeAt(0)
            if item.widget():
                item.widget().setParent(None)

        channels   = self._mgr.channels()
        live_logins = [ch.login for ch in channels if ch.is_live]
        off_logins  = [ch.login for ch in channels if not ch.is_live]

        # Sección EN VIVO
        self._hdr_live.set_count(len(live_logins))
        if live_logins:
            self._hdr_live.setParent(self._list_w)
            lay.addWidget(self._hdr_live)
            for login in live_logins:
                card = self._cards.get(login)
                if card:
                    card.setParent(self._list_w)
                    lay.addWidget(card)

        # Sección OFFLINE
        self._hdr_offline.set_count(len(off_logins))
        if off_logins:
            self._hdr_offline.setParent(self._list_w)
            lay.addWidget(self._hdr_offline)
            if not self._hdr_offline.is_collapsed():
                for login in off_logins:
                    card = self._cards.get(login)
                    if card:
                        card.setParent(self._list_w)
                        lay.addWidget(card)

        lay.addStretch()

    # ── Slots ─────────────────────────────────────────────────────────────────
    def _on_add(self):
        d = _AddDialog(self); d.confirmed.connect(self._mgr.add); d.exec()

    def _show_sort_menu(self):
        menu = QtWidgets.QMenu(self)
        for c in SortCriteria:
            act = menu.addAction(c.label)
            act.setCheckable(True)
            act.setChecked(self._mgr.sort_criteria() == c)
            act.triggered.connect(lambda checked, _c=c: self._mgr.set_sort(_c))
        menu.exec(QtGui.QCursor.pos())

    def _on_added(self, ch):
        if ch.login not in self._cards:
            card = ChannelCard(ch, self._list_w)
            card.openInApp.connect(self.openChannelRequested)
            card.openInBrowser.connect(self.openBrowserRequested)
            card.removeFav.connect(self._mgr.remove)
            self._cards[ch.login] = card
        self._rebuild_layout()
        self._update_empty()

    def _on_removed(self, login):
        card = self._cards.pop(login, None)
        if card:
            card.deleteLater()
        self._rebuild_layout()
        self._update_empty()

    def _on_updated(self, ch):
        card = self._cards.get(ch.login)
        if card:
            was_live = card._is_live
            card.update_state(ch)
            # Si cambió el estado live/offline → reordenar secciones
            if was_live != ch.is_live:
                self._rebuild_layout()
            elif self._mgr.sort_criteria() in (
                SortCriteria.STATUS_THEN_VIEWERS, SortCriteria.VIEWERS_DESC
            ):
                self._rebuild_layout()

    def _on_live_count(self, count):
        self._page_obj.setPageName("" if count == 0 else str(count))
        try:
            self._page_obj.button.setToolTip(
                f"Favoritos — {count} en vivo" if count else "Favoritos"
            )
        except Exception:
            pass

    def _on_poll_start(self):
        self._spin.setText("⟳")
        frames = ["⟳","↻","↺"]; idx = [0]
        def tick():
            if self._spin.text():
                idx[0] = (idx[0]+1) % len(frames)
                self._spin.setText(frames[idx[0]])
                QtCore.QTimer.singleShot(160, tick)
        QtCore.QTimer.singleShot(160, tick)

    def _reload_all(self):
        for card in list(self._cards.values()):
            card.deleteLater()
        self._cards.clear()
        for ch in self._mgr.channels():
            card = ChannelCard(ch, self._list_w)
            card.openInApp.connect(self.openChannelRequested)
            card.openInBrowser.connect(self.openBrowserRequested)
            card.removeFav.connect(self._mgr.remove)
            self._cards[ch.login] = card
        self._rebuild_layout()
        self._update_empty()

    def _update_empty(self):
        has = bool(self._cards)
        self._empty.setVisible(not has)
        self._scroll.setVisible(has)