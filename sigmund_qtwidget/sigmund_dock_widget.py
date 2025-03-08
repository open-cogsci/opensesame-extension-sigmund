from qtpy.QtCore import Signal
from qtpy.QtWidgets import QDockWidget
from .sigmund_widget import SigmundWidget


class SigmundDockWidget(QDockWidget):
    """
    A very minimal QDockWidget that hosts SigmundWidget and doesn't handle
    functionality itself. It just overrides the close event.
    """

    close_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Sigmund")
        self.setObjectName("sigmund_dock_widget")
        # Create our SigmundWidget and place it inside this dock
        self.sigmund_widget = SigmundWidget(self)
        self.setWidget(self.sigmund_widget)
        self.visibilityChanged.connect(self._on_visibility_changed)

        # Override close event and emit a signal for the extension to handle
        def _close_event_override(event):
            event.ignore()
            self.hide()
            self.close_requested.emit()

        self.closeEvent = _close_event_override

    def _on_visibility_changed(self, visible):
        print(f'visibility changed to {visible}')
        if visible:
            self.sigmund_widget.start_server()
        else:
            self.sigmund_widget.stop_server()
