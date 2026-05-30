"""
SocialMediaDownload.py — Panel de descarga multi-plataforma
Integra TikTok, Instagram, YouTube, Twitter/X y más dentro de TwitchLink.

Agrega este widget como una nueva pestaña en Ui/MainWindow.py:
    self._ui.tabWidget.addTab(SocialMediaDownload(), "📥 Redes")
"""

from PyQt6 import QtCore, QtWidgets, QtGui
import os

from Services.SocialMedia.YtDlpService import (
    Platform, SocialMediaInfo, DownloadConfig,
    InfoExtractorWorker, SocialMediaDownloadWorker,
    SocialMediaDownloadManager,
)


# ---------------------------------------------------------------------------
# Colores y estilos por plataforma
# ---------------------------------------------------------------------------

PLATFORM_COLORS = {
    Platform.YOUTUBE:   "#FF0000",
    Platform.TIKTOK:    "#010101",
    Platform.INSTAGRAM: "#C13584",
    Platform.TWITTER:   "#1DA1F2",
    Platform.FACEBOOK:  "#1877F2",
    Platform.TWITCH:    "#9146FF",
    Platform.UNKNOWN:   "#555555",
}

PLATFORM_ICONS = {
    Platform.YOUTUBE:   "▶",
    Platform.TIKTOK:    "♪",
    Platform.INSTAGRAM: "📷",
    Platform.TWITTER:   "🐦",
    Platform.FACEBOOK:  "f",
    Platform.TWITCH:    "📡",
    Platform.UNKNOWN:   "🌐",
}


# ---------------------------------------------------------------------------
# Widget de progreso por descarga activa
# ---------------------------------------------------------------------------

class ActiveDownloadItem(QtWidgets.QFrame):
    cancelRequested = QtCore.pyqtSignal()

    def __init__(self, title: str, platform: str, parent=None):
        super().__init__(parent=parent)
        self.setFrameStyle(QtWidgets.QFrame.Shape.StyledPanel)
        color = PLATFORM_COLORS.get(platform, "#555")

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)

        # Cabecera
        header = QtWidgets.QHBoxLayout()
        icon_lbl = QtWidgets.QLabel(PLATFORM_ICONS.get(platform, "🌐"))
        icon_lbl.setStyleSheet(f"color: {color}; font-size: 16px;")
        self.title_lbl = QtWidgets.QLabel(title[:60] + "…" if len(title) > 60 else title)
        self.title_lbl.setStyleSheet("font-weight: bold; font-size: 12px;")
        self.cancel_btn = QtWidgets.QPushButton("✕")
        self.cancel_btn.setFixedSize(24, 24)
        self.cancel_btn.setToolTip("Cancelar descarga")
        self.cancel_btn.clicked.connect(self.cancelRequested)
        header.addWidget(icon_lbl)
        header.addWidget(self.title_lbl, 1)
        header.addWidget(self.cancel_btn)

        # Barra de progreso
        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setRange(0, 1000)
        self.progress_bar.setValue(0)
        self.progress_bar.setStyleSheet(
            f"QProgressBar::chunk {{ background-color: {color}; border-radius: 3px; }}"
        )

        # Estado
        self.status_lbl = QtWidgets.QLabel("Iniciando…")
        self.status_lbl.setStyleSheet("font-size: 10px; color: gray;")

        layout.addLayout(header)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.status_lbl)

    def updateProgress(self, d: dict):
        status = d.get("status", "")
        if status == "downloading":
            downloaded = d.get("downloaded_bytes", 0) or 0
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            speed = d.get("speed") or 0
            eta   = d.get("eta")

            if total > 0:
                pct = int(downloaded / total * 1000)
                self.progress_bar.setValue(pct)
            else:
                self.progress_bar.setRange(0, 0)  # indeterminado

            speed_str = self._fmt_speed(speed)
            eta_str   = f" | ETA: {eta}s" if eta else ""
            self.status_lbl.setText(
                f"Descargando… {self._fmt_bytes(downloaded)} / {self._fmt_bytes(total)}"
                f"  [{speed_str}{eta_str}]"
            )
        elif status == "finished":
            self.progress_bar.setRange(0, 1000)
            self.progress_bar.setValue(1000)
            self.status_lbl.setText("Procesando con FFmpeg…")

    @staticmethod
    def _fmt_bytes(b: int) -> str:
        if b == 0:
            return "—"
        for unit in ("B", "KB", "MB", "GB"):
            if b < 1024:
                return f"{b:.1f} {unit}"
            b /= 1024
        return f"{b:.1f} TB"

    @staticmethod
    def _fmt_speed(bps: float) -> str:
        if not bps:
            return "—/s"
        return ActiveDownloadItem._fmt_bytes(int(bps)) + "/s"


# ---------------------------------------------------------------------------
# Panel principal
# ---------------------------------------------------------------------------

class SocialMediaDownload(QtWidgets.QWidget):
    def __init__(self, manager: SocialMediaDownloadManager, parent=None):
        super().__init__(parent=parent)
        self._manager = manager
        self._info: SocialMediaInfo | None = None
        self._extract_worker: InfoExtractorWorker | None = None
        self._active_items: dict[SocialMediaDownloadWorker, ActiveDownloadItem] = {}

        self._build_ui()
        self._connect_manager()

    # ------------------------------------------------------------------
    # Construcción de UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        # ── Título ──────────────────────────────────────────────────────
        title_lbl = QtWidgets.QLabel("📥  Descarga Multi-Plataforma")
        title_lbl.setStyleSheet("font-size: 18px; font-weight: bold;")
        subtitle = QtWidgets.QLabel(
            "YouTube · TikTok · Instagram · Twitter/X · Facebook · y +1800 sitios"
        )
        subtitle.setStyleSheet("color: gray; font-size: 11px;")
        root.addWidget(title_lbl)
        root.addWidget(subtitle)

        # ── URL Input ───────────────────────────────────────────────────
        url_group = QtWidgets.QGroupBox("URL del contenido")
        url_layout = QtWidgets.QVBoxLayout(url_group)

        url_row = QtWidgets.QHBoxLayout()
        self._url_edit = QtWidgets.QLineEdit()
        self._url_edit.setPlaceholderText(
            "Pega aquí el enlace: video, reel, historia, short, clip, playlist…"
        )
        self._url_edit.returnPressed.connect(self._on_fetch_info)
        self._fetch_btn = QtWidgets.QPushButton("🔍  Obtener info")
        self._fetch_btn.setFixedWidth(130)
        self._fetch_btn.clicked.connect(self._on_fetch_info)
        url_row.addWidget(self._url_edit, 1)
        url_row.addWidget(self._fetch_btn)
        url_layout.addLayout(url_row)

        # Plataforma detectada
        self._platform_lbl = QtWidgets.QLabel("")
        self._platform_lbl.setStyleSheet("font-size: 11px; color: gray;")
        url_layout.addWidget(self._platform_lbl)
        root.addWidget(url_group)

        # ── Info del contenido ─────────────────────────────────────────
        self._info_group = QtWidgets.QGroupBox("Información del contenido")
        self._info_group.setVisible(False)
        info_layout = QtWidgets.QFormLayout(self._info_group)
        self._lbl_title    = QtWidgets.QLabel()
        self._lbl_title.setWordWrap(True)
        self._lbl_uploader = QtWidgets.QLabel()
        self._lbl_duration = QtWidgets.QLabel()
        self._lbl_platform = QtWidgets.QLabel()
        self._lbl_playlist = QtWidgets.QLabel()
        info_layout.addRow("Título:",     self._lbl_title)
        info_layout.addRow("Autor:",      self._lbl_uploader)
        info_layout.addRow("Duración:",   self._lbl_duration)
        info_layout.addRow("Plataforma:", self._lbl_platform)
        info_layout.addRow("Playlist:",   self._lbl_playlist)
        root.addWidget(self._info_group)

        # ── Opciones de descarga ───────────────────────────────────────
        opts_group = QtWidgets.QGroupBox("Opciones de descarga")
        opts_layout = QtWidgets.QGridLayout(opts_group)
        opts_layout.setColumnStretch(1, 1)
        opts_layout.setColumnStretch(3, 1)

        # Tipo: video / solo audio
        opts_layout.addWidget(QtWidgets.QLabel("Tipo:"), 0, 0)
        self._type_combo = QtWidgets.QComboBox()
        self._type_combo.addItems(["🎬  Video + Audio", "🎵  Solo Audio"])
        self._type_combo.currentIndexChanged.connect(self._on_type_changed)
        opts_layout.addWidget(self._type_combo, 0, 1)

        # Calidad / resolución
        opts_layout.addWidget(QtWidgets.QLabel("Calidad:"), 0, 2)
        self._quality_combo = QtWidgets.QComboBox()
        self._quality_combo.addItems([
            "Mejor calidad", "2160p (4K)", "1440p (2K)",
            "1080p (Full HD)", "720p (HD)", "480p", "360p", "Menor calidad"
        ])
        opts_layout.addWidget(self._quality_combo, 0, 3)

        # Formato video
        opts_layout.addWidget(QtWidgets.QLabel("Formato video:"), 1, 0)
        self._vfmt_combo = QtWidgets.QComboBox()
        self._vfmt_combo.addItems(DownloadConfig.VIDEO_FORMATS)
        opts_layout.addWidget(self._vfmt_combo, 1, 1)

        # Formato audio
        opts_layout.addWidget(QtWidgets.QLabel("Formato audio:"), 1, 2)
        self._afmt_combo = QtWidgets.QComboBox()
        self._afmt_combo.addItems(DownloadConfig.AUDIO_FORMATS)
        opts_layout.addWidget(self._afmt_combo, 1, 3)

        # Carpeta destino
        opts_layout.addWidget(QtWidgets.QLabel("Guardar en:"), 2, 0)
        dir_row = QtWidgets.QHBoxLayout()
        self._dir_edit = QtWidgets.QLineEdit(os.path.expanduser("~/Downloads"))
        self._dir_btn  = QtWidgets.QPushButton("📂")
        self._dir_btn.setFixedWidth(32)
        self._dir_btn.clicked.connect(self._choose_dir)
        dir_row.addWidget(self._dir_edit)
        dir_row.addWidget(self._dir_btn)
        dir_widget = QtWidgets.QWidget()
        dir_widget.setLayout(dir_row)
        opts_layout.addWidget(dir_widget, 2, 1, 1, 3)

        # Plantilla de nombre
        opts_layout.addWidget(QtWidgets.QLabel("Nombre archivo:"), 3, 0)
        self._template_edit = QtWidgets.QLineEdit("%(uploader)s - %(title)s.%(ext)s")
        self._template_edit.setToolTip(
            "Variables: %(title)s  %(uploader)s  %(upload_date)s  "
            "%(id)s  %(ext)s  %(resolution)s"
        )
        opts_layout.addWidget(self._template_edit, 3, 1, 1, 3)

        # Opciones extra (checkboxes)
        extra_row = QtWidgets.QHBoxLayout()
        self._chk_thumb    = QtWidgets.QCheckBox("Incrustar miniatura")
        self._chk_thumb.setChecked(True)
        self._chk_subs     = QtWidgets.QCheckBox("Incrustar subtítulos")
        self._chk_metadata = QtWidgets.QCheckBox("Metadatos")
        self._chk_metadata.setChecked(True)
        self._chk_chapters = QtWidgets.QCheckBox("Capítulos (YT)")
        self._chk_chapters.setChecked(True)
        self._chk_playlist = QtWidgets.QCheckBox("Descargar playlist completa")
        extra_row.addWidget(self._chk_thumb)
        extra_row.addWidget(self._chk_subs)
        extra_row.addWidget(self._chk_metadata)
        extra_row.addWidget(self._chk_chapters)
        extra_row.addWidget(self._chk_playlist)
        extra_row.addStretch()
        opts_layout.addLayout(extra_row, 4, 0, 1, 4)

        # Opciones avanzadas (colapsable)
        adv_group = QtWidgets.QGroupBox("⚙ Opciones avanzadas")
        adv_group.setCheckable(True)
        adv_group.setChecked(False)
        adv_layout = QtWidgets.QGridLayout(adv_group)

        adv_layout.addWidget(QtWidgets.QLabel("Límite de velocidad:"), 0, 0)
        self._rate_edit = QtWidgets.QLineEdit()
        self._rate_edit.setPlaceholderText("Ej: 5M, 500K  (vacío = sin límite)")
        adv_layout.addWidget(self._rate_edit, 0, 1)

        adv_layout.addWidget(QtWidgets.QLabel("Proxy:"), 0, 2)
        self._proxy_edit = QtWidgets.QLineEdit()
        self._proxy_edit.setPlaceholderText("http://user:pass@host:port")
        adv_layout.addWidget(self._proxy_edit, 0, 3)

        adv_layout.addWidget(QtWidgets.QLabel("Cookies desde:"), 1, 0)
        self._cookies_combo = QtWidgets.QComboBox()
        self._cookies_combo.addItems([
            "No usar cookies", "Chrome", "Firefox", "Edge", "Safari", "Opera"
        ])
        adv_layout.addWidget(self._cookies_combo, 1, 1)

        adv_layout.addWidget(QtWidgets.QLabel("Rango playlist:"), 1, 2)
        range_row = QtWidgets.QHBoxLayout()
        self._pl_start = QtWidgets.QSpinBox()
        self._pl_start.setRange(1, 99999)
        self._pl_start.setValue(1)
        self._pl_end   = QtWidgets.QSpinBox()
        self._pl_end.setRange(0, 99999)
        self._pl_end.setValue(0)
        self._pl_end.setSpecialValueText("Fin")
        range_row.addWidget(QtWidgets.QLabel("de"))
        range_row.addWidget(self._pl_start)
        range_row.addWidget(QtWidgets.QLabel("a"))
        range_row.addWidget(self._pl_end)
        pl_widget = QtWidgets.QWidget()
        pl_widget.setLayout(range_row)
        adv_layout.addWidget(pl_widget, 1, 3)

        opts_layout.addWidget(adv_group, 5, 0, 1, 4)
        root.addWidget(opts_group)

        # ── Botón descargar ─────────────────────────────────────────────
        btn_row = QtWidgets.QHBoxLayout()
        self._download_btn = QtWidgets.QPushButton("⬇  Iniciar Descarga")
        self._download_btn.setFixedHeight(38)
        self._download_btn.setStyleSheet(
            "QPushButton { background-color: #5c1de0; color: white; "
            "font-size: 14px; font-weight: bold; border-radius: 6px; }"
            "QPushButton:hover { background-color: #7b3fe4; }"
            "QPushButton:disabled { background-color: #888; }"
        )
        self._download_btn.clicked.connect(self._on_download)
        btn_row.addStretch()
        btn_row.addWidget(self._download_btn)
        root.addLayout(btn_row)

        # ── Descargas activas ───────────────────────────────────────────
        self._active_group = QtWidgets.QGroupBox("Descargas activas")
        self._active_group.setVisible(False)
        self._active_layout = QtWidgets.QVBoxLayout(self._active_group)
        root.addWidget(self._active_group)

        root.addStretch()
        self._on_type_changed()

    # ------------------------------------------------------------------
    # Slots internos
    # ------------------------------------------------------------------

    def _on_type_changed(self):
        is_audio = self._type_combo.currentIndex() == 1
        self._quality_combo.setEnabled(not is_audio)
        self._vfmt_combo.setEnabled(not is_audio)
        self._afmt_combo.setEnabled(is_audio)
        self._chk_subs.setEnabled(not is_audio)
        self._chk_chapters.setEnabled(not is_audio)

    def _choose_dir(self):
        path = QtWidgets.QFileDialog.getExistingDirectory(
            self, "Seleccionar carpeta de descarga", self._dir_edit.text()
        )
        if path:
            self._dir_edit.setText(path)

    def _on_fetch_info(self):
        url = self._url_edit.text().strip()
        if not url:
            return
        platform = Platform.detect(url)
        color    = PLATFORM_COLORS.get(platform, "#555")
        name     = Platform.displayName(platform)
        self._platform_lbl.setText(f"Plataforma detectada: {name}")
        self._platform_lbl.setStyleSheet(f"font-size: 11px; color: {color}; font-weight: bold;")

        self._fetch_btn.setEnabled(False)
        self._fetch_btn.setText("Analizando…")
        self._info_group.setVisible(False)

        cookies = self._get_cookies()
        self._extract_worker = InfoExtractorWorker(url, cookies_browser=cookies, parent=self)
        self._extract_worker.finished.connect(self._on_info_ready)
        self._extract_worker.error.connect(self._on_info_error)
        self._extract_worker.start()

    def _on_info_ready(self, info: SocialMediaInfo):
        self._info = info
        self._lbl_title.setText(info.title)
        self._lbl_uploader.setText(info.uploader)
        self._lbl_duration.setText(info.duration_str)
        self._lbl_platform.setText(Platform.displayName(info.platform))
        playlist_txt = f"Sí ({len(info.entries)} elementos)" if info.is_playlist else "No"
        self._lbl_playlist.setText(playlist_txt)
        if info.is_playlist:
            self._chk_playlist.setEnabled(True)

        # Poblar calidades reales
        self._quality_combo.clear()
        self._quality_combo.addItem("Mejor calidad")
        for res in info.available_resolutions:
            self._quality_combo.addItem(res)
        self._quality_combo.addItem("Menor calidad")

        self._info_group.setVisible(True)
        self._fetch_btn.setEnabled(True)
        self._fetch_btn.setText("🔍  Obtener info")

    def _on_info_error(self, msg: str):
        QtWidgets.QMessageBox.warning(self, "Error al analizar URL", msg)
        self._fetch_btn.setEnabled(True)
        self._fetch_btn.setText("🔍  Obtener info")

    def _on_download(self):
        url = self._url_edit.text().strip()
        if not url:
            QtWidgets.QMessageBox.warning(self, "URL vacía", "Por favor ingresa una URL.")
            return

        config = self._build_config(url)
        worker = self._manager.startDownload(config)

        title    = self._info.title if self._info else url[:50]
        platform = Platform.detect(url)
        item     = ActiveDownloadItem(title, platform, parent=self)
        item.cancelRequested.connect(lambda: self._cancel_worker(worker, item))
        worker.progressUpdated.connect(item.updateProgress)
        worker.finished.connect(lambda ok, msg: self._on_worker_done(worker, item, ok, msg))

        self._active_layout.addWidget(item)
        self._active_items[worker] = item
        self._active_group.setVisible(True)

    def _cancel_worker(self, worker: SocialMediaDownloadWorker, item: ActiveDownloadItem):
        worker.cancel()
        item.status_lbl.setText("Cancelando…")
        item.cancel_btn.setEnabled(False)

    def _on_worker_done(
        self,
        worker: SocialMediaDownloadWorker,
        item: ActiveDownloadItem,
        ok: bool,
        msg: str,
    ):
        if ok:
            item.status_lbl.setText(f"✅  {msg}")
            item.progress_bar.setValue(1000)
        else:
            item.status_lbl.setText(f"❌  {msg}")
        item.cancel_btn.setEnabled(False)
        if worker in self._active_items:
            del self._active_items[worker]
        if not self._active_items:
            self._active_group.setVisible(False)

    def _connect_manager(self):
        pass  # hooks opcionales para historial global

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_config(self, url: str) -> DownloadConfig:
        cfg = DownloadConfig()
        cfg.url        = url
        cfg.output_dir = self._dir_edit.text().strip() or os.path.expanduser("~/Downloads")
        cfg.audio_only = self._type_combo.currentIndex() == 1
        cfg.format_pref   = self._vfmt_combo.currentText()
        cfg.audio_format  = self._afmt_combo.currentText()
        cfg.embed_thumb   = self._chk_thumb.isChecked()
        cfg.embed_subs    = self._chk_subs.isChecked()
        cfg.metadata      = self._chk_metadata.isChecked()
        cfg.chapters      = self._chk_chapters.isChecked()
        cfg.playlist      = self._chk_playlist.isChecked()
        cfg.filename_template = self._template_edit.text().strip() or "%(title)s.%(ext)s"

        # Calidad
        q_map = {
            "Mejor calidad": "best", "2160p (4K)": "2160p",
            "1440p (2K)": "1440p",   "1080p (Full HD)": "1080p",
            "720p (HD)": "720p",     "480p": "480p",
            "360p": "360p",          "Menor calidad": "worst",
        }
        q_text = self._quality_combo.currentText()
        # Si es una resolución real detectada (ej. "1080p")
        cfg.quality = q_map.get(q_text, q_text.replace("p", "") + "p" if q_text[:-1].isdigit() else "best")

        # Avanzadas
        rate = self._rate_edit.text().strip()
        if rate:
            cfg.rate_limit = rate
        proxy = self._proxy_edit.text().strip()
        if proxy:
            cfg.proxy = proxy
        cfg.cookies_from_browser = self._get_cookies()
        start = self._pl_start.value()
        end   = self._pl_end.value()
        cfg.playlist_start = start
        cfg.playlist_end   = end if end > 0 else None

        return cfg

    def _get_cookies(self) -> str | None:
        browser_map = {
            "Chrome": "chrome", "Firefox": "firefox",
            "Edge": "edge", "Safari": "safari", "Opera": "opera",
        }
        text = self._cookies_combo.currentText()
        return browser_map.get(text)
