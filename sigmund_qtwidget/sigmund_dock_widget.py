from qtpy.QtCore import Signal
from qtpy.QtWidgets import QDockWidget
from .sigmund_widget import SigmundWidget
import logging
logging.basicConfig(level=logging.INFO, force=True)
logger = logging.getLogger(__name__)


class SigmundDockWidget(QDockWidget):
    """
    A very minimal QDockWidget that hosts SigmundWidget and doesn't handle
    functionality itself. It just overrides the close event.
    """

    close_requested = Signal()

    def __init__(self, parent=None, application='Unknown'):
        super().__init__(parent)
        self.setWindowTitle("Sigmund")
        self.setObjectName("sigmund_dock_widget")
        # Create our SigmundWidget and place it inside this dock
        self.sigmund_widget = SigmundWidget(self, application)
        self.setWidget(self.sigmund_widget)
        # Override close event and emit a signal for the extension to handle
        def _close_event_override(event):
            event.ignore()
            self.hide()
            self.close_requested.emit()
        self.closeEvent = _close_event_override

    def setVisible(self, visible):
        if visible:
            logger.info('starting sigmund connector')
            self.sigmund_widget.start_server()
            self.parent().extension_manager.fire(
                'register_subprocess', pid=self.sigmund_widget.server_pid,
                description='sigmund server')
        else:
            logger.info('stopping sigmund connector')
            self.sigmund_widget.stop_server()
        super().setVisible(visible)
