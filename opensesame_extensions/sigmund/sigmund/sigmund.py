import sys
import json
import traceback
from pathlib import Path
from multiprocessing import Process, Queue
from qtpy.QtWidgets import QDockWidget, QWidget, QVBoxLayout, QLabel, \
    QApplication
from qtpy.QtCore import Qt, QTimer, Signal
from libopensesame.py3compat import *
from libopensesame.oslogging import oslogger
from libqtopensesame.extensions import BaseExtension
from . import websocket_server, chat_widget, workspace
from libqtopensesame.misc.translate import translation_context
_ = translation_context('Sigmund', category='extension')


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
        self._workspace_manager = workspace.WorkspaceManager(self.main_window)
        
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
    
    def activate(self):
        """
        Called when the extension is activated. Sets up a dockwidget.
        If we're not already listening or connected, we immediately try to start listening.
        """
        oslogger.debug('Activating Sigmund')
        if self._state not in ['listening', 'connected']:
            self.start_listening()

        self.docktab = QDockWidget(_('Sigmund'), self.main_window)
        self.docktab.setObjectName('opensesame-extension-sigmund')
        self.main_window.addDockWidget(Qt.RightDockWidgetArea, self.docktab)

        # Set up a timer to poll for server messages
        self._poll_timer = QTimer(self.main_window)
        self._poll_timer.timeout.connect(self.poll_server_queue)
        self._poll_timer.start(100)  # check every 100ms

        self.refresh_dockwidget_ui()

    def refresh_dockwidget_ui(self):
        """Update the UI based on the current state."""
        dock_content = QWidget()
        self.docktab.setWidget(dock_content)
        layout = QVBoxLayout()
        layout.setSpacing(10)

        if self._state == 'failed':
            # Show message that listening failed
            fail_label = QLabel(_("Failed to listen to Sigmund.\nMaybe another application is already listening?"))
            layout.addWidget(fail_label)

        elif self._state == 'not_listening':
            # The user won't see this often, but could if we forcibly stopped the server
            # Show a fail label or an idle label
            idle_label = QLabel(_("Failed to listen to Sigmund.\nPlease restart the application."))
            layout.addWidget(idle_label)

        elif self._state == 'listening':
            # Show a hint to open the browser
            browser_hint = QLabel(_("Please open sigmundai.eu in a webbrowser"))
            layout.addWidget(browser_hint)

        elif self._state == 'connected':
            # Show chat interface
            if self._chat_widget is None:
                self._chat_widget = chat_widget.ChatWidget(self.main_window)
                self._chat_widget.user_message_sent.connect(self.on_user_message_sent)
            layout.addWidget(self._chat_widget)

        dock_content.setLayout(layout)

    def start_listening(self):
        """
        Start the WebSocket server in a separate process and
        create queues for two-way communication.
        """
        oslogger.debug('Starting Sigmund WebSocket server')
        try:
            self._to_main_queue = Queue()
            self._to_server_queue = Queue()
            self._server_process = Process(
                target=websocket_server.start_server,
                args=(self._to_main_queue, self._to_server_queue),
                daemon=True
            )
            self._server_process.start()
            self._state = 'listening'
        except Exception as e:
            # For any error, we move to 'failed'
            oslogger.error(f"Failed to start Sigmund server: {e}")
            self._state = 'failed'

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
        elif action == 'user_message':
            message_text = data.get("message", "")
            self._chat_widget.append_message("user_message", message_text)            
        elif action == "ai_message":
            message_text = data.get("message", "")
            workspace_content = data.get("workspace_content", "")
            workspace_language = data.get("workspace_language", "markdown")
            self._chat_widget.append_message("ai_message", message_text)
            self._chat_widget.setEnabled(True)
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
