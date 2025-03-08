import os
import json
import traceback
from multiprocessing import Process, Queue
from qtpy.QtWidgets import QWidget, QVBoxLayout, QLabel
from qtpy.QtGui import QPixmap
from qtpy.QtCore import Qt, QTimer, Signal
from . import websocket_server, chat_widget
from .diff_dialog import DiffDialog
import logging
logging.basicConfig(level=logging.INFO, force=True)
logger = logging.getLogger(__name__)


class SigmundWidget(QWidget):
    """
    A QWidget that encapsulates Sigmund's server, chat logic, and references to
    OpenSesame-specific elements (workspace_manager, etc.).
    """

    server_state_changed = Signal(str)  # Emitted when server state changes
    token_received = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        # State
        self._state = 'not_listening'
        self._server_process = None
        self._to_main_queue = None
        self._to_server_queue = None
        self._retry = 1

        # References to OS-specific things (injected/set by extension)
        self._workspace_manager = None

        # Chat widget
        self.chat_widget = None

        # Polling timer for the server queue
        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._poll_server_queue)

        # Initial UI build
        self.refresh_ui()

    def set_workspace_manager(self, manager):
        self._workspace_manager = manager

    def start_server(self):
        """
        Start the WebSocket server in a separate process and
        create queues for two-way communication. If already started, do nothing.
        """
        if self._state in ('listening', 'connected'):
            return
        logger.debug('Starting Sigmund WebSocket server')
        self._to_main_queue = Queue()
        self._to_server_queue = Queue()
    
        try:
            self._server_process = Process(
                target=websocket_server.start_server,
                args=(self._to_main_queue, self._to_server_queue),
                daemon=True  # Daemon mode helps if main process ends normally.
            )
            self._server_process.start()
        except Exception as e:
            # For any error, we move to 'failed'
            logger.error(f"Failed to start Sigmund server: {e}")
            self._update_state('failed')
        else:
            # If we're successful, we move to 'listening'
            self._update_state('listening')
            # Start polling
            self._poll_timer.start(100)
            
    def stop_server(self):
        """
        Stop the WebSocket server and clean up.
        """
        if self._state == 'not_listening':
            return
        logger.info('Stopping Sigmund WebSocket server')
        self._poll_timer.stop()
        if self._server_process is not None:
            self._server_process.terminate()
            self._server_process.join()
            self._server_process = None
        self._to_main_queue = None
        self._to_server_queue = None
        self._update_state('not_listening')
            
    @property
    def server_pid(self):
        """Return server process pid. If there is no process, or if it is not
        # alive, return None.
        """
        if self._server_process is not None and self._server_process.is_alive():
            return self._server_process.pid
        return None

    def send_user_message(self, text, workspace_content=None,
                          workspace_language=None, retry=1):
        """
        A method to send user messages, optionally including workspace contents.
        Disables the chat until we receive the AI response.
        """
        if not text or not self._to_server_queue:
            return

        # Optionally retrieve workspace content
        if workspace_content is None and self._workspace_manager is not None:
            workspace_content, workspace_language = self._workspace_manager.get()

        self._retry = retry
        if self.chat_widget:
            self.chat_widget.setEnabled(False)

        user_json = {
            "action": "user_message",
            "message": text,
            "workspace_content": workspace_content,
            "workspace_language": workspace_language
        }
        self._to_server_queue.put(json.dumps(user_json))

    def refresh_ui(self):
        layout = self.layout()
        if layout is not None:
            # Remove widgets from the old layout, but do not destroy self.chat_widget.
            while layout.count():
                item = layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()
        else:
            # Create and configure the new layout
            layout = QVBoxLayout()
            layout.setSpacing(10)
    
        if self._state == 'connected':
            self.chat_widget = chat_widget.ChatWidget(self)
            self.chat_widget.user_message_sent.connect(self.send_user_message)
            layout.addWidget(self.chat_widget)
        else:
            pix_label = QLabel()
            pix_label.setAlignment(Qt.AlignCenter)
            pixmap = QPixmap(os.path.join(os.path.dirname(__file__), 'sigmund-full.png'))
            pix_label.setPixmap(pixmap)
            layout.addWidget(pix_label)
    
            state_label = QLabel()
            state_label.setTextFormat(Qt.RichText)
            state_label.setTextInteractionFlags(Qt.TextBrowserInteraction)
            state_label.setWordWrap(True)
            state_label.setOpenExternalLinks(True)
            state_label.setAlignment(Qt.AlignCenter)
    
            if self._state == 'failed':
                state_label.setText(
                    "Failed to listen to Sigmund.\nMaybe another application is already listening?"
                )
            elif self._state == 'not_listening':
                state_label.setText(
                    "Failed to listen to Sigmund.\nServer failed to start."
                )
            else:
                state_label.setText(
                    "Open https://sigmundai.eu in a browser and log in. "
                    "OpenSesame will automatically connect."
                )
            layout.addWidget(state_label)
            layout.addStretch()
    
        # Assign the new layout
        self.setLayout(layout)

    # ----------
    # Internals
    # ----------

    def _poll_server_queue(self):
        """
        Called periodically by a QTimer to see if there are new messages
        from the WebSocket server. If so, parse them.
        """
        if not self._to_main_queue:
            return
        while not self._to_main_queue.empty():
            msg = self._to_main_queue.get()
            if not isinstance(msg, str):
                continue
            self._handle_incoming_raw(msg)

    def _handle_incoming_raw(self, raw_msg):
        """ Parse raw messages from the server into actions/data. """
        if raw_msg.startswith('[DEBUG]'):
            logger.info(raw_msg)
            return
        elif raw_msg.startswith('FAILED_TO_START'):
            self._update_state('failed')
            return
        elif raw_msg == "CLIENT_CONNECTED":
            self._update_state('connected')
            if self.chat_widget:
                self.chat_widget.clear_messages()
            # Optionally request an auth token
            self._request_token()
        elif raw_msg == "CLIENT_DISCONNECTED":
            # Return to 'listening' if server still active
            if self._server_process is not None:
                self._update_state('listening')
        else:
            # Likely JSON
            try:
                data = json.loads(raw_msg)
            except json.JSONDecodeError:
                logger.error(f'invalid incoming JSON: {raw_msg}')
                return
            # Directly handle messages here
            self._on_message_received(data)

    def _on_message_received(self, data):
        """
        Handle parsed messages from the server. We do OS-specific actions here—
        for example, we store tokens, manage workspace content, etc.
        """
        action = data.get("action", None)

        if not self.chat_widget:
            return

        if action == 'token':
            token = data.get('message', '')
            if token:
                self.token_received.emit(token)
        elif action == 'clear_messages':
            self.chat_widget.clear_messages()

        elif action == 'cancel_message':
            self.chat_widget.setEnabled(True)

        elif action == 'user_message':
            message_text = data.get("message", "")
            self.chat_widget.append_message("user_message", message_text)

        elif action == "ai_message":
            # Show the AI message
            message_text = data.get("message", "")
            self.chat_widget.append_message("ai_message", message_text)
            self.chat_widget.setEnabled(True)
    
            # Attempt to apply workspace changes, if any
            workspace_content = data.get("workspace_content", "")
            workspace_language = data.get("workspace_language", "markdown")            
            on_connect = data.get("on_connect", False)
            if (
                not on_connect and self._workspace_manager
                and self._workspace_manager.has_changed(workspace_content,
                                                        workspace_language)
            ):
                # Show diff, and if accepted, update
                result = DiffDialog(
                    self,
                    message_text,
                    self._workspace_manager.strip_content(self._workspace_manager.content),
                    self._workspace_manager.strip_content(workspace_content)
                ).exec()
                if result == DiffDialog.Accepted:
                    try:
                        self._workspace_manager.set(workspace_content, workspace_language)
                    except Exception:
                        err_msg = f'''The following error occurred when I tried to use the workspace content:
                        
```
{traceback.format_exc()}
```
'''
                        self.chat_widget.append_message('user_message', err_msg)
                        if not self._retry:
                            self.chat_widget.append_message('ai_message',
                                'Maximum number of attempts exceeded.')
                        else:
                            self.send_user_message(err_msg, workspace_content,
                                                   workspace_language,
                                                   retry=self._retry - 1)
    
        else:
            logger.error(f'invalid or unhandled incoming message: {data}')

    def _request_token(self):
        if self._to_server_queue:
            self._to_server_queue.put(json.dumps({"action": "get_token"}))

    def _update_state(self, new_state):
        """Set the state and emit a signal so that the extension can pick it up."""
        if new_state == self._state:
            return
        self._state = new_state
        self.refresh_ui()
        self.server_state_changed.emit(new_state)
