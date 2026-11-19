"""Extension that hosts an in-process MCP server (connected to the Sigmund
relay) inside the OpenSesame GUI process.
"""
import logging
from qtpy.QtCore import Qt
from qtpy.QtWidgets import QDockWidget
from libopensesame.oslogging import oslogger
from libqtopensesame.extensions import BaseExtension
from libqtopensesame.misc.config import cfg
from libqtopensesame.misc.translate import translation_context
from .sigmund_mcp_relay_widget import SigmundMCPRelayWidget

_ = translation_context('sigmund_mcp_relay', category='extension')
logger = logging.getLogger(__name__)


class SigmundMcpRelay(BaseExtension):
    """Checkable extension that shows/ hides a dock widget with the relay
    connection UI (pair/ connect/ server toggles). The actual MCP server runs
    in this process, bridged to the remote relay by the dock widget.
    """
    def event_startup(self):
        self._dock_widget = None
        self._relay_widget = None
        self._visible = False
        if cfg.sigmund_mcp_relay_enabled and cfg.sigmund_mcp_relay_visible:
            self.activate()

    def event_close(self):
        """Stop the relay agent thread when OpenSesame closes."""
        if self._relay_widget is not None:
            try:
                self._relay_widget.disconnect_agent()
            except Exception:
                logger.exception('failed to stop the MCP relay agent')

    def activate(self, *dummy):
        """Called when the extension is activated (toolbar/ menu). Toggles
        the dock widget's visibility.
        """
        # Toggle off
        if self._visible:
            cfg.sigmund_mcp_relay_visible = self._visible = False
            self.set_checked(False)
            if self._dock_widget is not None:
                self._dock_widget.hide()
            return
        # Toggle on
        cfg.sigmund_mcp_relay_visible = self._visible = True
        self.set_checked(True)
        # Create the dock widget if it doesn't exist yet
        if self._dock_widget is None:
            self._dock_widget = QDockWidget(_('Sigmund'), self.main_window)
            self._dock_widget.setObjectName('sigmund_mcp_relay')
            self._relay_widget = SigmundMCPRelayWidget(self._dock_widget, self)
            self._dock_widget.setWidget(self._relay_widget)
            self.main_window.addDockWidget(Qt.RightDockWidgetArea,
                                           self._dock_widget)
            self._dock_widget.visibilityChanged.connect(
                self._on_visibility_changed)
        # Show
        self._dock_widget.show()
        self._dock_widget.raise_()

    def _on_visibility_changed(self, visible):
        """Keep the toolbar button and the setting in sync when the user
        closes/ opens the dock widget directly.
        """
        if visible == self._visible:
            return
        self._visible = visible
        cfg.sigmund_mcp_relay_visible = visible
        self.set_checked(visible)
