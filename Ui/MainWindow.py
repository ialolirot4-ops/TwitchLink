from Core.Ui import *
from Services.Messages import Messages
from Services.Document import DocumentData, DocumentButtonData
from Ui.Components.Operators.NavigationBar import NavigationBar
from Ui.Components.Pages.SearchPage import SearchPage
from Ui.Components.Pages.DownloadsPage import DownloadsPage
from Ui.Components.Pages.ScheduledDownloadsPage import ScheduledDownloadsPage
from Ui.Components.Pages.AccountPage import AccountPage
from Ui.Components.Pages.InformationPage import InformationPage
from Ui.Favorites.FavoritesPage import FavoritesPage
from Ui.SocialMedia.SocialMediaDownload import SocialMediaDownload

from PyQt6.QtWebEngineWidgets import QWebEngineView


class MainWindow(QtWidgets.QMainWindow, WindowGeometryManager):
    def __init__(self, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent=parent)
        self._ui = UiLoader.load("mainWindow", self)
        self._webViewEnabled = False
        App.Instance.appStarted.connect(self.start, QtCore.Qt.ConnectionType.QueuedConnection)

    def start(self) -> None:
        if App.Preferences.setup.needSetup():
            if Ui.Setup().exec():
                App.Instance.restart()
            else:
                App.Instance.exit()
        else:
            loading = Ui.Loading()
            loading.completeSignal.connect(self.onLoadingComplete)
            loading.exec()
            self.show()

    def onLoadingComplete(self) -> None:
        self.loadWindowGeometry()
        self.loadComponents()
        self.setupSystemTray()
        self.setup()

    def loadComponents(self) -> None:
        self.setWindowIcon(Icons.APP_LOGO.icon)
        self._ui.actionGettingStarted.triggered.connect(self.gettingStarted)
        self._ui.actionAbout.triggered.connect(self.openAbout)
        self._ui.actionTermsOfService.triggered.connect(self.openTermsOfService)
        self._ui.actionSponsor.triggered.connect(self.sponsor)
        self.navigationBar = NavigationBar(self._ui.navigationBar, self._ui.navigationArea, parent=self)
        self.navigationBar.focusChanged.connect(self.onFocusChange)
        self.searchPageObject = self.navigationBar.addPage(self._ui.searchPageButton, self._ui.searchPage, icon=Icons.SEARCH)
        self.downloadsPageObject = self.navigationBar.addPage(self._ui.downloadsPageButton, self._ui.downloadsPage, icon=Icons.DOWNLOAD)
        self.scheduledDownloadsPageObject = self.navigationBar.addPage(self._ui.scheduledDownloadsPageButton, self._ui.scheduledDownloadsPage, icon=Icons.SCHEDULED)
        self.accountPageObject = self.navigationBar.addPage(self._ui.accountPageButton, self._ui.accountPage, icon=Icons.ACCOUNT)
        self.settingsPageObject = self.navigationBar.addPage(self._ui.settingsPageButton, self._ui.settingsPage, icon=Icons.SETTINGS)
        self.informationPageObject = self.navigationBar.addPage(self._ui.informationPageButton, self._ui.informationPage, icon=Icons.INFO)
        self.search = SearchPage(self.searchPageObject, parent=self)
        self.search.accountPageShowRequested.connect(self.accountPageObject.show)
        self._ui.searchPage.layout().addWidget(self.search)
        self.downloads = DownloadsPage(self.downloadsPageObject, parent=self)
        self.downloads.accountPageShowRequested.connect(self.accountPageObject.show)
        self.downloads.appShutdownRequested.connect(self.shutdown)
        self.downloads.systemShutdownRequested.connect(self.shutdownSystem)
        self._ui.downloadsPage.layout().addWidget(self.downloads)

        # ── Batch Download button — corner widget inside the Downloads tab bar ─
        batchBtn = QtWidgets.QToolButton(parent=self)
        batchBtn.setText("Batch Download…")
        batchBtn.setToolTip("Queue multiple downloads from a URL list")
        batchBtn.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonTextOnly)
        batchBtn.setMinimumHeight(28)
        batchBtn.clicked.connect(self.openBatchDownload)
        self.downloads.setCornerWidget(batchBtn, QtCore.Qt.Corner.TopRightCorner)
        # ──────────────────────────────────────────────────────────────────────
        self.scheduledDownloads = ScheduledDownloadsPage(self.scheduledDownloadsPageObject, parent=self)
        self._ui.scheduledDownloadsPage.layout().addWidget(self.scheduledDownloads)
        self.account = AccountPage(self.accountPageObject, parent=self)
        self._ui.accountPage.layout().addWidget(self.account)
        self.settings = Ui.Settings(parent=self)
        self.settings.restartRequired.connect(self.restart)
        self._ui.settingsPage.layout().addWidget(self.settings)
        self.information = InformationPage(self.informationPageObject, parent=self)
        self.information.termsOfServiceAccepted.connect(self._termsOfServiceAccepted)
        self.information.appShutdownRequested.connect(self.shutdown)
        self._ui.informationPage.layout().addWidget(self.information)

        # ── Página de Favoritos ♥ — usa widgets definidos en mainWindow.ui ────
        self.favoritesPageObject = self.navigationBar.addPage(
            self._ui.favoritesPageButton,
            self._ui.favoritesPage,
            icon=Icons.FAVORITES,
        )
        self.favoritesPageObject.button.setToolTip("Canales Favoritos ♥")

        self.favoritesPanel = FavoritesPage(
            manager=App.FavoritesManager,
            page_object=self.favoritesPageObject,
            parent=self,
        )
        self.favoritesPanel.openChannelRequested.connect(self._open_favorite_channel)
        self.favoritesPanel.openBrowserRequested.connect(self._open_favorite_browser)
        self._ui.favoritesPage.layout().addWidget(self.favoritesPanel)

        # ── Descarga Multi-Plataforma — usa widgets definidos en mainWindow.ui ─
        self.socialPageObject = self.navigationBar.addPage(
            self._ui.socialPageButton,
            self._ui.socialPage,
            icon=Icons.DOWNLOAD,
        )
        self.socialPageObject.button.setToolTip("Descarga Multi-Plataforma")

        self.socialPanel = SocialMediaDownload(
            manager=App.SocialDownloadManager,
            parent=self,
        )
        self._ui.socialPage.layout().addWidget(self.socialPanel)

    def setupSystemTray(self) -> None:
        contextMenu = App.Instance.systemTrayIcon.contextMenu()
        self.openAppAction = QtGui.QAction(T("open"), parent=contextMenu)
        self.closeAppAction = QtGui.QAction(T("exit"), parent=contextMenu)
        self.openAppAction.triggered.connect(self.activate)
        self.closeAppAction.triggered.connect(self.close)
        contextMenu.addAction(self.openAppAction)
        contextMenu.addAction(self.closeAppAction)
        if Utils.isWindows():
            App.Instance.systemTrayIcon.clicked.connect(self.activate)

    def setup(self) -> None:
        self.statusUpdated(isInSetup=True)
        if App.Updater.status.isOperational():
            if App.Preferences.setup.getTermsOfServiceAgreement() == None:
                self.openTermsOfService()
            else:
                self._termsOfServiceAccepted()
            App.Updater.statusUpdated.connect(self.statusUpdated)
            App.Updater.startAutoUpdate()
            App.GlobalDownloadManager.statsUpdated.connect(self.showContributeInfo, QtCore.Qt.ConnectionType.QueuedConnection)
        App.Instance.newInstanceStarted.connect(self.activate)
        if Utils.isFile(Config.TRACEBACK_FILE):
            file = QtCore.QFile(Config.TRACEBACK_FILE, self)
            if file.open(QtCore.QIODevice.OpenModeFlag.ReadOnly):
                fileName = file.readAll().data().decode(errors="ignore")
                url = Utils.joinUrl(Config.HOMEPAGE_URL, "report", params={"lang": App.Translator.getCurrentLanguageCode()})
                self.information.showAppInfo(
                    DocumentData(
                        contentId="CRASH_REPORT",
                        title=T("#{appName} has crashed.", appName=Config.APP_NAME),
                        content=T("#{appName} has crashed due to an unexpected error.\nIf you see this message, please attach the following log file and report it to us.\n\nFile: {fileName}", appName=Config.APP_NAME, fileName=fileName),
                        contentType="text",
                        modal=True,
                        buttons=[
                            DocumentButtonData(text=T("close"), role="accept", default=False),
                            DocumentButtonData(text=T("open-file"), action=f"file:{fileName}", role="action", default=False),
                            DocumentButtonData(text=T("report-error"), action=f"url:{url}", role="action", default=True)
                        ]
                    )
                )
            file.remove()
            file.deleteLater()

    def _termsOfServiceAccepted(self) -> None:
        self.account.refreshAccount()
        App.Account.updateIntegrityToken()

    def _open_favorite_browser(self, login: str) -> None:
        """Abre el canal directamente en el navegador del sistema."""
        from Services.Favorites.FavoritesManager import FavoriteChannel
        ch = App.FavoritesManager.get(login)
        url = ch.twitch_url if ch else f"https://www.twitch.tv/{login}"
        Utils.openUrl(url)

    def _open_favorite_channel(self, login: str) -> None:
        """
        Abre el canal en la pestaña de busqueda al hacer clic en 'Ver'.
        NOTA: TwitchGQLResponse.finished emite el objeto response entero (self),
        no el dato parseado. El dato real esta en response._data.
        """
        from Services.Twitch.GQL import TwitchGQLModels
        response = App.TwitchGQL.getChannel(login=login)

        def on_done(resp):
            # resp es el TwitchGQLResponse; el Channel esta en resp._data
            channel = getattr(resp, "_data", resp)
            if not isinstance(channel, TwitchGQLModels.Channel):
                return
            if hasattr(self, "search"):
                self.search.openSearchResultTab(channel)
                self.searchPageObject.show()

        response.finished.connect(on_done)

    def show(self) -> None:
        if self._webViewEnabled:
            super().show()
        else:
            webView = QWebEngineView(parent=self)
            webView.load(QtCore.QUrl())
            webView.deleteLater()
            self._webViewEnabled = True
            super().show()

    def statusUpdated(self, isInSetup: bool = False) -> None:
        isOperational = App.Updater.status.isOperational()
        allowPageView = not isInSetup
        self.menuBar().setEnabled(isOperational or allowPageView)
        if not isOperational and allowPageView:
            self.downloadsPageObject.focus()
            self.scheduledDownloadsPageObject.focus()
            self.settingsPageObject.focus()
        else:
            self.downloadsPageObject.unfocus()
            self.scheduledDownloadsPageObject.unfocus()
            self.settingsPageObject.unfocus()
        App.GlobalDownloadManager.setDownloaderCreationEnabled(isOperational)
        if isInSetup:
            App.ScheduledDownloadManager.setBlocked(not isOperational)
        contentId = "APP_STATUS"
        self.information.removeAppInfo(contentId)
        status = App.Updater.status.getStatus()
        if status == App.Updater.status.Types.CONNECTION_FAILURE:
            if isInSetup:
                content = T("#Please try again later.")
                buttons = [
                    DocumentButtonData(text=T("ok"), action=self.shutdown, role="action", default=True)
                ]
            else:
                content = T("#Some features will be temporarily disabled.\nPlease wait.\nWhen the connection is restored, those features will be activated.")
                buttons = []
            self.information.showAppInfo(
                DocumentData(
                    contentId=contentId,
                    title=T("network-error"),
                    content=f"{T('#A network error occurred while connecting to the server.')}\n{content}",
                    contentType="text",
                    modal=True,
                    buttons=buttons
                )
            )
        elif status == App.Updater.status.Types.UNEXPECTED_ERROR:
            App.Updater.stopAutoUpdate()
            if isInSetup:
                content = T("#Please try again later.")
                buttons = [
                    DocumentButtonData(text=T("ok"), action=self.shutdown, role="action", default=True)
                ]
            else:
                content = f"{T('#Some features will be disabled.')}\n{T('#Please restart the app.')}"
                buttons = []
            self.information.showAppInfo(
                DocumentData(
                    contentId=contentId,
                    title=T("error"),
                    content=f"{T('#An unexpected error occurred while connecting to the server.')}\n{content}",
                    contentType="text",
                    modal=True,
                    buttons=buttons
                )
            )
        elif status == App.Updater.status.Types.SESSION_EXPIRED:
            App.Updater.stopAutoUpdate()
            self.information.showAppInfo(
                DocumentData(
                    contentId=contentId,
                    title=T("session-expired"),
                    content=f"{T('#Your session has expired.')}\n{T('#Some features will be disabled.')}\n{T('#Please restart the app.')}",
                    contentType="text",
                    modal=True,
                    buttons=[]
                )
            )
        elif status == App.Updater.status.Types.UNAVAILABLE:
            self.information.showAppInfo(
                DocumentData(
                    contentId=contentId,
                    title=T("service-unavailable"),
                    content=App.Updater.status.operationalInfo or T("#{appName} is currently unavailable.", appName=Config.APP_NAME),
                    contentType=App.Updater.status.operationalInfoType or "text",
                    modal=True,
                    buttons=[DocumentButtonData(text=T("ok"), action=self.shutdown, role="action", default=True)] if isInSetup else []
                )
            )
            if not isInSetup:
                self.restart()
        elif status == App.Updater.status.Types.UPDATE_REQUIRED or status == App.Updater.status.Types.UPDATE_FOUND:
            if status == App.Updater.status.Types.UPDATE_REQUIRED:
                App.Updater.stopAutoUpdate()
            self.information.showAppInfo(
                DocumentData(
                    contentId=contentId,
                    title=T("recommended-update" if status == App.Updater.status.Types.UPDATE_FOUND else "required-update"),
                    content=App.Updater.status.versionInfo.updateNote or f"{T('#A new version of {appName} has been released!', appName=Config.APP_NAME)}\n\n[{Config.APP_NAME} {App.Updater.status.versionInfo.latestVersion if App.Updater.status.versionInfo.hasUpdate() else T('unknown')}]",
                    contentType=App.Updater.status.versionInfo.updateNoteType if App.Updater.status.versionInfo.updateNote else "text",
                    modal=status == App.Updater.status.Types.UPDATE_REQUIRED,
                    buttons=[
                        DocumentButtonData(text=T("update"), action=self.confirmUpdateShutdown, role="action", default=True),
                        DocumentButtonData(text=T("cancel"), action=(self.shutdown if isInSetup else self.confirmShutdown) if status == App.Updater.status.Types.UPDATE_REQUIRED else None, role="reject", default=False)
                    ]
                ),
                icon=Icons.UPDATE_FOUND
            )

    def onFocusChange(self, focus: bool) -> None:
        enabled = not focus
        self._ui.actionAbout.setEnabled(enabled)
        self._ui.actionTermsOfService.setEnabled(enabled)
        if focus:
            self.activate()

    def showContributeInfo(self, totalFiles: int, totalByteSize: int) -> None:
        if Utils.ask("contribute", T("#You have downloaded a total of {totalFiles}({totalSize}) videos so far.\nPlease become a patron of {appName} for better functionality and service.", totalFiles=totalFiles, totalSize=Utils.formatByteSize(totalByteSize), appName=Config.APP_NAME), contentTranslate=False, defaultOk=True, parent=self):
            Utils.openUrl(Utils.joinUrl(Config.HOMEPAGE_URL, "donate", params={"lang": App.Translator.getCurrentLanguageCode()}))

    def confirmShutdown(self) -> None:
        if App.GlobalDownloadManager.isDownloaderRunning() and not App.GlobalDownloadManager.isShuttingDown():
            if Utils.ask(*Messages.ASK.STOP_CANCEL_ALL_DOWNLOADS, parent=self):
                self.shutdown()
        else:
            self.shutdown()

    def confirmUpdateShutdown(self) -> None:
        if App.GlobalDownloadManager.isDownloaderRunning() and not App.GlobalDownloadManager.isShuttingDown():
            if not Utils.ask(*Messages.ASK.STOP_CANCEL_ALL_DOWNLOADS, parent=self):
                return
        Utils.openUrl(Utils.joinUrl(App.Updater.status.versionInfo.updateUrl, params={"lang": App.Translator.getCurrentLanguageCode()}))
        self.shutdown()

    def _askCloseAction(self) -> str:
        """
        Muestra un diálogo preguntando qué hacer al cerrar.
        Devuelve: 'tray' | 'exit' | 'cancel'
        """
        from Core import App as _App
        pal  = _App.Instance.palette()
        R    = QtGui.QPalette.ColorRole
        G    = QtGui.QPalette.ColorGroup
        win  = pal.color(G.Active, R.Window)
        is_dark = win.lightness() < 128

        PURPLE   = "#9147ff"
        PURPLE_D = "#7b3fe4"
        RED      = "#e84040"
        RED_D    = "#c0392b"
        BG       = win.name()
        base     = pal.color(G.Active, R.Base)
        d = 12 if is_dark else -8
        CARD  = QtGui.QColor(
            max(0, min(255, base.red()   + d)),
            max(0, min(255, base.green() + d)),
            max(0, min(255, base.blue()  + d)),
        ).name()
        CARD_H = QtGui.QColor(
            max(0, min(255, base.red()   + d * 2)),
            max(0, min(255, base.green() + d * 2)),
            max(0, min(255, base.blue()  + d * 2)),
        ).name()
        SEP  = pal.color(G.Active, R.Mid).name()
        TEXT = pal.color(G.Active, R.WindowText).name()
        DIM  = f"rgba({pal.color(G.Active, R.WindowText).red()}," \
               f"{pal.color(G.Active, R.WindowText).green()}," \
               f"{pal.color(G.Active, R.WindowText).blue()},0.55)"

        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("Exit")
        dlg.setFixedWidth(360)
        dlg.setWindowFlags(
            QtCore.Qt.WindowType.Dialog |
            QtCore.Qt.WindowType.FramelessWindowHint
        )
        dlg.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground)

        # ── Outer shadow card ────────────────────────────────────────────────
        outer = QtWidgets.QVBoxLayout(dlg)
        outer.setContentsMargins(12, 12, 12, 12)

        card = QtWidgets.QWidget()
        card.setObjectName("exitCard")
        card.setStyleSheet(
            f"#exitCard{{background:{BG};border-radius:14px;"
            f"border:1px solid {SEP};}}"
        )
        shadow = QtWidgets.QGraphicsDropShadowEffect(card)
        shadow.setBlurRadius(32)
        shadow.setOffset(0, 6)
        shadow.setColor(QtGui.QColor(0, 0, 0, 120))
        card.setGraphicsEffect(shadow)

        outer.addWidget(card)

        root = QtWidgets.QVBoxLayout(card)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Header ───────────────────────────────────────────────────────────
        hdr = QtWidgets.QWidget()
        hdr.setStyleSheet(
            f"background:{PURPLE};border-top-left-radius:13px;"
            "border-top-right-radius:13px;"
        )
        hdr.setFixedHeight(52)
        hdr_lay = QtWidgets.QHBoxLayout(hdr)
        hdr_lay.setContentsMargins(18, 0, 14, 0)

        hdr_icon = QtWidgets.QLabel("⏻")
        hdr_icon.setStyleSheet("font-size:22px;color:#fff;background:transparent;")
        hdr_lay.addWidget(hdr_icon)

        hdr_lay.addSpacing(10)
        hdr_title = QtWidgets.QLabel(f"Salir de {Config.APP_NAME}")
        hdr_title.setStyleSheet(
            "font-size:14px;font-weight:700;color:#fff;background:transparent;"
        )
        hdr_lay.addWidget(hdr_title, 1)

        btn_x = QtWidgets.QToolButton()
        btn_x.setText("✕")
        btn_x.setFixedSize(28, 28)
        btn_x.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
        btn_x.setStyleSheet(
            "QToolButton{background:rgba(255,255,255,0.15);color:#fff;"
            "border:none;border-radius:6px;font-size:13px;font-weight:700;}"
            "QToolButton:hover{background:rgba(255,255,255,0.30);}"
        )
        btn_x.clicked.connect(dlg.reject)
        hdr_lay.addWidget(btn_x)

        root.addWidget(hdr)

        # ── Body ─────────────────────────────────────────────────────────────
        body = QtWidgets.QWidget()
        body.setStyleSheet("background:transparent;")
        body_lay = QtWidgets.QVBoxLayout(body)
        body_lay.setContentsMargins(16, 18, 16, 18)
        body_lay.setSpacing(10)

        result = ["cancel"]

        def _option(icon, label, desc, hover_color, val):
            btn = QtWidgets.QPushButton()
            btn.setFixedHeight(62)
            btn.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
            btn.setStyleSheet(
                f"QPushButton{{background:{CARD};border:1px solid {SEP};"
                "border-radius:10px;text-align:left;padding:0 14px;}"
                f"QPushButton:hover{{background:{hover_color};border-color:{hover_color};}}"
            )

            lay = QtWidgets.QHBoxLayout(btn)
            lay.setContentsMargins(14, 0, 14, 0)
            lay.setSpacing(14)

            ico_lbl = QtWidgets.QLabel(icon)
            ico_lbl.setFixedSize(36, 36)
            ico_lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            ico_lbl.setStyleSheet(
                f"font-size:18px;background:rgba(128,128,128,0.12);"
                "border-radius:8px;"
            )
            ico_lbl.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            lay.addWidget(ico_lbl)

            txt_col = QtWidgets.QVBoxLayout()
            txt_col.setSpacing(2)
            txt_col.setContentsMargins(0, 0, 0, 0)

            lbl_main = QtWidgets.QLabel(label)
            lbl_main.setStyleSheet(
                f"font-size:12px;font-weight:600;color:{TEXT};background:transparent;"
            )
            lbl_main.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents)

            lbl_sub = QtWidgets.QLabel(desc)
            lbl_sub.setStyleSheet(
                f"font-size:10px;color:{DIM};background:transparent;"
            )
            lbl_sub.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents)

            txt_col.addWidget(lbl_main)
            txt_col.addWidget(lbl_sub)
            lay.addLayout(txt_col, 1)

            arrow = QtWidgets.QLabel("›")
            arrow.setStyleSheet(
                f"font-size:20px;color:{DIM};background:transparent;"
            )
            arrow.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            lay.addWidget(arrow)

            def _handler():
                result[0] = val
                dlg.accept()

            btn.clicked.connect(_handler)
            return btn

        btn_tray = _option(
            "󰆦" if False else "⊟",
            "Minimizar al system tray",
            "La aplicación seguirá corriendo en segundo plano.",
            PURPLE,
            "tray",
        )
        btn_exit = _option(
            "⏻",
            "Cerrar completamente",
            "Detiene todos los procesos y cierra la app.",
            RED_D,
            "exit",
        )

        body_lay.addWidget(btn_tray)
        body_lay.addWidget(btn_exit)

        # ── Footer ───────────────────────────────────────────────────────────
        sep = QtWidgets.QFrame()
        sep.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        sep.setStyleSheet(f"color:{SEP};")
        body_lay.addSpacing(4)
        body_lay.addWidget(sep)
        body_lay.addSpacing(2)

        cancel_row = QtWidgets.QHBoxLayout()
        cancel_row.addStretch()
        btn_cancel = QtWidgets.QPushButton("Cancelar")
        btn_cancel.setFixedHeight(32)
        btn_cancel.setFixedWidth(90)
        btn_cancel.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
        btn_cancel.setStyleSheet(
            f"QPushButton{{border:1px solid {SEP};border-radius:7px;"
            f"font-size:12px;color:{TEXT};background:transparent;}}"
            f"QPushButton:hover{{background:{CARD_H};}}"
        )
        btn_cancel.clicked.connect(dlg.reject)
        cancel_row.addWidget(btn_cancel)
        body_lay.addLayout(cancel_row)

        root.addWidget(body)

        dlg.exec()
        return result[0]

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        super().closeEvent(event)
        event.ignore()
        if not event.spontaneous():
            self.confirmShutdown()
            return
        tray_available = (
            App.Updater.status.isOperational()
            and self.isVisible()
            and Utils.isMinimizeToSystemTraySupported()
            and App.Preferences.general.isSystemTrayEnabled()
        )
        if tray_available:
            action = self._askCloseAction()
            if action == "tray":
                self.moveToSystemTray()
            elif action == "exit":
                self.confirmShutdown()
            # "cancel" → no hacer nada, la ventana sigue abierta
        else:
            self.confirmShutdown()

    def gettingStarted(self) -> None:
        Utils.openUrl(Utils.joinUrl(Config.HOMEPAGE_URL, "help", params={"lang": App.Translator.getCurrentLanguageCode()}))

    def openAbout(self) -> None:
        self.information.openAbout()

    def openBatchDownload(self) -> None:
        Ui.BatchDownload(parent=self).exec()

    def openTermsOfService(self) -> None:
        self.information.openTermsOfService()

    def sponsor(self) -> None:
        Utils.openUrl(Utils.joinUrl(Config.HOMEPAGE_URL, "donate", params={"lang": App.Translator.getCurrentLanguageCode()}))

    def waitForCleanup(self) -> None:
        if App.GlobalDownloadManager.isDownloaderRunning():
            msg = QtWidgets.QProgressDialog(parent=self)
            msg.setWindowTitle(T("shutting-down"))
            msg.setLabelText(T("#Shutting down all downloads" if App.GlobalDownloadManager.isDownloaderRunning() else "shutting-down", ellipsis=True))
            msg.setRange(0, 0)
            msg.setCancelButton(None)
            App.GlobalDownloadManager.cancelAll()
            App.GlobalDownloadManager.allCompletedSignal.connect(msg.close)
            msg.exec()

    def restart(self) -> None:
        self.shutdown(restart=True)

    def shutdown(self, restart: bool = False) -> None:
        App.Updater.stopAutoUpdate()
        App.Updater.status.setStatus(App.Updater.status.Types.NONE)
        App.Notifications.clearAll()
        App.GlobalDownloadManager.setDownloaderCreationEnabled(False)
        App.ScheduledDownloadManager.setBlocked(True)
        self.downloads.setScheduledShutdown(None)
        self.waitForCleanup()
        self.saveWindowGeometry()
        if restart:
            App.Instance.restart()
        else:
            App.Instance.exit()

    def shutdownSystem(self) -> None:
        self.shutdown()
        Utils.shutdownSystem(message=T("#Shutdown by {appName}'s scheduled task.", appName=Config.APP_NAME))

    def moveToSystemTray(self) -> None:
        if not self.isHidden():
            self.hide()
            App.Instance.notification.toastMessage(
                title=T("#Minimized to system tray"),
                message=T("#{appName} is running in the background.", appName=Config.APP_NAME),
                icon=App.Instance.notification.Icons.Information
            )

    def activate(self) -> None:
        if self.isHidden():
            self.show()
        self.setWindowState((self.windowState() & ~QtCore.Qt.WindowState.WindowMinimized) | QtCore.Qt.WindowState.WindowActive)
        self.raise_()
        self.activateWindow()