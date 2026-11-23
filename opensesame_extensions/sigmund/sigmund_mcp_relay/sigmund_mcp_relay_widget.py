from mcp_relay.agent import InProcessServerProvider, RelayWidget
from pyqt_code_editor.components.sigmund_mcp_relay.sigmund_mcp_relay_widget \
    import pick_fs_root
from pyqt_code_editor.components.sigmund_mcp_relay.servers.mcp_filesystem  \
    import make_mcp as make_mcp_filesystem
from pyqt_code_editor.components.sigmund_mcp_relay.servers.mcp_jasp \
    import make_mcp as make_mcp_jasp
from libqtopensesame.misc.config import cfg
from pyqt_code_editor import settings
from .servers.mcp_opensesame import make_mcp as make_mcp_opensesame
import logging
from qtpy.QtWidgets import QPushButton
logger = logging.getLogger(__name__)


class SigmundMCPRelayWidget(RelayWidget):
    """Relay widget exposing in-process MCP servers.
    """

    def __init__(self, parent, extension):
        self._extension = extension
        super().__init__(
            parent,
            relay_url=cfg.sigmund_mcp_relay_url,
            providers=self.providers()
        )        
        
    def _build_ui(self) -> None:
        super()._build_ui()
        self.setStyleSheet(f"font-size: {settings.font_size}pt;")
        
    def providers(self):
        providers = {
            'opensesame': InProcessServerProvider(
                'opensesame',
                make_mcp_opensesame(self._extension),
                display_name='Edit your experiment',
                enabled=True,
            ),
            "files": InProcessServerProvider(
                "files",
                make_mcp_filesystem,
                args_provider=pick_fs_root,
                display_name="Access files and folders",
                enabled=False
            ),
            "jasp": InProcessServerProvider(
                "jasp",
                make_mcp_jasp,
                args_provider=lambda: settings.sigmund_mcp_jasp_rpc_url,
                display_name="Perform statistics with JASP",
                enabled=False
            )            
        }
        return providers
