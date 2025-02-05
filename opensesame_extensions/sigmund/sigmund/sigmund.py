import sys
import os
import json
import traceback
from pathlib import Path
from multiprocessing import Process, Queue
from qtpy.QtWidgets import QDockWidget, QWidget, QVBoxLayout, QLabel, \
    QApplication
from qtpy.QtGui import QPixmap
from qtpy.QtCore import Qt, QTimer, Signal
from libopensesame.exceptions import UserAborted
from libopensesame.py3compat import *
from libopensesame.oslogging import oslogger
from libqtopensesame.extensions import BaseExtension
from . import websocket_server, chat_widget, workspace
from .diff_dialog import DiffDialog
from libqtopensesame.misc.translate import translation_context
_ = translation_context('sigmund', category='extension')


class Sigmund(BaseExtension):
    
    def event_startup(self):
        """
        Is called once when the extension is initialized.
        We'll manage a state machine with these states:
          - 'not_listening' (hasn't tried to start yet, or was manually stopped)
          - 'listening' (server active, no clients)
          - 'connected' (server active, at least one client connected)
          - 'failed' (server failed to start)
        """
        self._state = 'not_listening'
        self._server_process = None
        self._to_main_queue = None
        self._to_server_queue = None
        self._item = None
        self._chat_widget = None
        self._visible = False
        self._current_exception = None
        self._workspace_manager = workspace.WorkspaceManager(self.main_window)
        
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
            self.activate()
            self.extension_manager.fire(
                'notify',
                message=_("Connect to Sigmund and try again!"),
                category='info',
                timeout=5000
            )            
            return
        self._item = self._current_exception.item
        self.on_user_message_sent(str(self._current_exception))
        
    def event_open_item(self, name):
        self._item = name
        if self._chat_widget is not None:
            if name is None:
                self._chat_widget.append_message('ai_message',
                    _('We are now talking about the entire experiment. To ask questions about a specific item, please select it first.'))
            else:
                self._chat_widget.append_message('ai_message',
                    _('We are now talking about item {}').format(name))
                
    def event_open_general_properties(self):
        self.event_open_item(None)
        
    def event_open_general_script(self):
        self.event_open_item(None)
        
    def event_rename_item(self, from_name, to_name):
        if self._item == from_name:
            self._item = to_name
    
    def activate(self, *dummy):
        """
        Called when the extension is activated. Sets up a dockwidget.
        If we're not already listening or connected, we immediately try to start listening.
        """
        if self._visible:
            self._visible = False
            self.set_checked(False)
            self._dock_widget.hide()
            return
        oslogger.debug('Activating Sigmund')
        self._visible = True
        self.set_checked(True)
        if self._state not in ['listening', 'connected']:
            self.start_listening()
            self._dock_widget = QDockWidget(_('Sigmund'), self.main_window)
            self._dock_widget.setObjectName('opensesame-extension-sigmund')
            self._dock_widget.closeEvent = self.activate
            self.main_window.addDockWidget(Qt.RightDockWidgetArea,
                                           self._dock_widget)
            # Set up a timer to poll for server messages
            self._poll_timer = QTimer(self.main_window)
            self._poll_timer.timeout.connect(self.poll_server_queue)
            self._poll_timer.start(100)
        self.refresh_dockwidget_ui()
        self._dock_widget.show()

    def refresh_dockwidget_ui(self):
        """Update the UI based on the current state."""
        dock_content = QWidget()
        self._dock_widget.setWidget(dock_content)
        layout = QVBoxLayout()
        layout.setSpacing(10)
        
        if self._state == 'connected':
            if self._chat_widget is None:
                self._chat_widget = chat_widget.ChatWidget(self.main_window)
                self._chat_widget.user_message_sent.connect(self.on_user_message_sent)
            layout.addWidget(self._chat_widget)        
        else: 
            if self._state == 'failed':
                label = QLabel(_("Failed to listen to Sigmund.\nMaybe another application is already listening?"))
            elif self._state == 'not_listening':
                label = QLabel(_("Failed to listen to Sigmund.\nServer failed to start."))
            else:
                label = QLabel(
                    _('Open <a href="https://sigmundai.eu" style="text-decoration: none;">https://sigmundai.eu</a> in a browser and log in. OpenSesame will automatically connect.'))
            label.setTextFormat(Qt.RichText)
            label.setTextInteractionFlags(Qt.TextBrowserInteraction)
            label.setWordWrap(True)
            label.setOpenExternalLinks(True)
            label.setAlignment(Qt.AlignCenter)
            pix_label = QLabel()
            pixmap = QPixmap(os.path.join(os.path.dirname(__file__), 'sigmund-full.png'))
            pix_label.setPixmap(pixmap)
            pix_label.setAlignment(Qt.AlignCenter)
            layout.addWidget(pix_label)
            layout.addWidget(label)
            layout.addStretch()
        dock_content.setLayout(layout)
        dock_content.resize(300, dock_content.sizeHint().height())

    def start_listening(self):
        """
        Start the WebSocket server in a separate process and
        create queues for two-way communication.
        """
        oslogger.debug('Starting Sigmund WebSocket server')
        self._to_main_queue = Queue()
        self._to_server_queue = Queue()
        try:
            self._server_process = Process(
                target=websocket_server.start_server,
                args=(self._to_main_queue, self._to_server_queue),
                daemon=True
            )
            self._server_process.start()
        except Exception as e:
            # For any error, we move to 'failed'
            oslogger.error(f"Failed to start Sigmund server: {e}")
            self._state = 'failed'
        else:
            # If we're successfull, we move to 'listening' and register the
            # process so that it's cleaned up on shutdown.
            self._state = 'listening'
            self.extension_manager.fire('register_subprocess',
                                        pid=self._server_process.pid,
                                        description='sigmund websocket server')

    def on_user_message_sent(self, text, workspace_content=None,
                             workspace_language=None, retry=1):
        """
        Called when ChatWidget tells us the user has sent a message.
        We package it as JSON and send it to the server. We also disable the
        chat widget until we receive the AI response.
        """
        if not text or not self._to_server_queue:
            return
        self._retry = retry
        if workspace_content is None:
            workspace_content, workspace_language = \
                self._workspace_manager.get(self._item)
        user_json = {
            "action": "user_message",
            "message": text,
            "workspace_content": workspace_content,
            "workspace_language": workspace_language
        }
        self._chat_widget.setEnabled(False)
        send_str = json.dumps(user_json)
        self._to_server_queue.put(send_str)

    def poll_server_queue(self):
        """
        Called periodically by a QTimer to see if there are new messages
        from the WebSocket server.
        """
        if self._to_main_queue is None:
            return
        while not self._to_main_queue.empty():
            msg = self._to_main_queue.get()
            if not isinstance(msg, str):
                continue
            if msg.startswith('[DEBUG]'):
                oslogger.info(msg)
            elif msg.startswith('FAILED_TO_START'):
                self._state = 'failed'
                self.refresh_dockwidget_ui()
            elif msg == "CLIENT_CONNECTED":
                self._state = 'connected'
                self.refresh_dockwidget_ui()
                self._chat_widget.clear_messages()
                self.extension_manager.fire(
                    'notify',
                    message=_("A client has connected to Sigmund!"),
                    category='info',
                    timeout=5000
                )
            elif msg == "CLIENT_DISCONNECTED":
                if self._server_process is not None:
                    self._state = 'listening'
                    self.refresh_dockwidget_ui()
                    self.extension_manager.fire(
                        'notify',
                        message=_("A client has disconnected from Sigmund."),
                        category='info',
                        timeout=5000
                    )
            else:
                self._handle_incoming_message(msg)

    def _handle_incoming_message(self, raw_msg):
        """
        Parses incoming data from the client. If it's valid JSON with
        action = "ai_message", we treat it as an AI response.
        """
        try:
            data = json.loads(raw_msg)
        except json.JSONDecodeError:
            action = None
        else:
            if isinstance(data, dict):
                action = data.get("action", None)
            else:
                action = None
        if action == 'clear_messages':
            self._chat_widget.clear_messages()
        elif action == 'cancel_message':
            self._chat_widget.setEnabled(True)
        elif action == 'user_message':
            message_text = data.get("message", "")
            self._chat_widget.append_message("user_message", message_text)            
        elif action == "ai_message":
            message_text = data.get("message", "")
            workspace_content = data.get("workspace_content", "")
            workspace_language = data.get("workspace_language", "markdown")
            self._chat_widget.append_message("ai_message", message_text)
            self._chat_widget.setEnabled(True)
            
            if not self._workspace_manager.has_changed(workspace_content,
                                                       workspace_language):
                return
            result = DiffDialog(
                self.main_window,
                message_text,
                self._workspace_manager.strip_content(
                    self._workspace_manager._content),
                self._workspace_manager.strip_content(
                    workspace_content)
            ).exec()
            if result != DiffDialog.Accepted:
                return
            try:
                self._workspace_manager.set(workspace_content,
                                            workspace_language)
            except Exception as e:
                # When an error occurs, we pass this back to Sigmund as a
                # user message to give Sigmund a chance to try again.
                msg = f'''The following error occurred when I tried to use the workspace content:
                
```
{traceback.format_exc()}
```
'''
                    
                self._chat_widget.append_message('user_message', msg)
                if not self._retry:
                    self._chat_widget.append_message('ai_message',
                        _('Maximum number of attempts exceeded.'))
                else:
                    self.on_user_message_sent(msg, workspace_content,
                                              workspace_language,
                                          retry=self._retry - 1)
        else:
            oslogger.error(f'invalid incoming message: {raw_msg}')
    
    def icon(self):
        return str(Path(__file__).parent / 'sigmund.png')
