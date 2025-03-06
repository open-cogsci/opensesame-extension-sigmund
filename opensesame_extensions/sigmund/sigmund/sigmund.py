from pathlib import Path
from qtpy.QtCore import Qt
from libopensesame.exceptions import UserAborted
from libopensesame.py3compat import *
from libopensesame.oslogging import oslogger
from libqtopensesame.extensions import BaseExtension
from libqtopensesame.misc.config import cfg
from . import opensesame_workspace as workspace
from sigmund_qtwidget.sigmund_dock_widget import SigmundDockWidget
from libqtopensesame.misc.translate import translation_context
_ = translation_context('sigmund', category='extension')


class Sigmund(BaseExtension):

    def event_startup(self):
        """
        Initialize the extension state.
        """
        self._state = 'not_listening'
        self._sigmund_widget = None
        self._visible = False
        self._current_exception = None
        self._workspace_manager = workspace.WorkspaceManager(self)
        self._item = None

    def event_end_experiment(self, ret_val):
        if ret_val is None or isinstance(ret_val, UserAborted):
            self._current_exception = None
            return
        self._current_exception = ret_val
        ret_val._read_more += '''
    
<a id="read-more" class="important-button" href="opensesame://event.sigmund_fix_exception">
Ask Sigmund to fix this
</a>'''


    def event_sigmund_fix_exception(self):
        if self._current_exception is None:
            return
        if self._state != 'connected':
            self.activate()  # Show dock and connect
            self.extension_manager.fire(
                'notify',
                message=_("Connect to Sigmund and try again!"),
                category='info',
                timeout=5000
            )
            return
        self._item = self._current_exception.item
        self._workspace_manager.item_name = self._current_exception.item
        if self._sigmund_widget:
            self._sigmund_widget.send_user_message(str(self._current_exception))
        self.extension_manager.fire(
            'notify',
            message=_("Sigmund is trying to fix your error. Please wait …"),
            category='info',
            timeout=5000,
            always_show=True
        )

    def event_open_item(self, name):
        self._item = name
        self._workspace_manager.item_name = name
        if self._sigmund_widget and self._sigmund_widget.chat_widget is not None:
            if name is None:
                self._sigmund_widget.chat_widget.append_message('ai_message',
                    _('We are now talking about the entire experiment. '
                      'To ask questions about a specific item, please select it first.'))
            else:
                self._sigmund_widget.chat_widget.append_message('ai_message',
                    _('We are now talking about item {}').format(name))

    def event_open_general_properties(self):
        self.event_open_item(None)

    def event_open_general_script(self):
        self.event_open_item(None)

    def event_rename_item(self, from_name, to_name):
        if self._item == from_name:
            self._item = to_name
            self._workspace_manager.item_name = to_name

    def activate(self, *dummy):
        """
        Called when the extension is activated. Toggles the dock’s visibility
        and starts the server if needed.
        """
        # Toggle
        if self._visible:
            self._visible = False
            self.set_checked(False)
            if self._sigmund_widget:
                self._sigmund_widget.hide()
            return

        # Show
        self._visible = True
        self.set_checked(True)

        # Create the dock widget if it doesn't exist
        if self._sigmund_widget is None:
            self._dock_widget = SigmundDockWidget(self.main_window)
            self._sigmund_widget = self._dock_widget.sigmund_widget
            self._sigmund_widget.set_workspace_manager(self._workspace_manager)
            self.main_window.addDockWidget(Qt.RightDockWidgetArea,
                                           self._dock_widget)
            self._dock_widget.close_requested.connect(self.activate)

            # Dock widget signals
            self._sigmund_widget.server_state_changed.connect(
                self._on_server_state_changed)

            # Attempt to start the server
            self._sigmund_widget.start_server()

        # Refresh and show
        self._sigmund_widget.show()

    def refresh_dockwidget_ui(self):
        """Ask the dock widget to update its UI based on the current state."""
        if self._sigmund_widget:
            self._sigmund_widget.refresh_ui()

    def _on_server_state_changed(self, new_state):
        """
        React to the dock widget's server-state changes with OS-specific logic
        (e.g. notifications).
        """
        self._state = new_state
        if new_state == 'failed':
            self.extension_manager.fire(
                'notify',
                message=_("Sigmund server failed to start."),
                category='error',
                timeout=5000
            )
        elif new_state == 'connected':
            # Possibly notify the user that a client connected
            self.extension_manager.fire(
                'notify',
                message=_("A client has connected to Sigmund!"),
                category='info',
                timeout=5000
            )

    def icon(self):
        """Return the icon for the extension."""
        return str(Path(__file__).parent / 'sigmund.png')