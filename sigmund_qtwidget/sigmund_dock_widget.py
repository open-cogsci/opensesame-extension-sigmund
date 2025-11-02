from qtpy.QtCore import Signal, QTimer
from qtpy.QtWidgets import QDockWidget
from .sigmund_widget import SigmundWidget
import logging
logging.basicConfig(level=logging.INFO, force=True)
logger = logging.getLogger(__name__)


class SigmundDockWidget(QDockWidget):
    """
    A very minimal QDockWidget that hosts SigmundWidget and doesn't handle
    functionality itself. It just overrides the close event and debounces
    visibility-driven server start/stop.
    """

    close_requested = Signal()

    def __init__(self, parent=None, application='Unknown',
                 sigmund_widget_cls=None):
        super().__init__(parent)
        self.setWindowTitle("Sigmund")
        self.setObjectName("sigmund_dock_widget")

        # Create our SigmundWidget and place it inside this dock
        if sigmund_widget_cls is None:
            self.sigmund_widget_cls = SigmundWidget
        self.sigmund_widget = sigmund_widget_cls(self, application)
        self.setWidget(self.sigmund_widget)

        # Track desired visibility and server running state
        self._desired_visible = False
        self._server_running = False

        # Debounce timer for visibility changes
        self._visibility_timer = QTimer(self)
        self._visibility_timer.setInterval(500)
        self._visibility_timer.setSingleShot(True)
        self._visibility_timer.timeout.connect(self._apply_visibility_effects)

        # Override close event and emit a signal for the extension to handle
        def _close_event_override(event):
            event.ignore()
            self.hide()
            self.close_requested.emit()
        self.closeEvent = _close_event_override

    def setVisible(self, visible):
        self._desired_visible = visible
        self._visibility_timer.start()
        super().setVisible(visible)

    def _apply_visibility_effects(self):
        """
        Called after debounce period. Starts or stops the server only if
        the desired visibility implies a change from current server state.
        """
        if self._desired_visible and not self._server_running:
            logger.info('starting sigmund connector (debounced)')
            self.sigmund_widget.start_server()
            self._server_running = True
            parent = self.parent()
            if parent is not None and hasattr(parent, "extension_manager"):
                parent.extension_manager.fire(
                    'register_subprocess',
                    pid=self.sigmund_widget.server_pid,
                    description='sigmund server'
                )
        elif not self._desired_visible and self._server_running:
            logger.info('stopping sigmund connector (debounced)')
            self.sigmund_widget.stop_server()
            self._server_running = False