import re
from qtpy.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QPlainTextEdit,
    QSizePolicy,
)
# QtAwesome is optional, but it makes the UI look better.
try:
    import qtawesome as qta
except ImportError:
    pass
from qtpy.QtCore import Signal, Qt
from .chat_browser import ChatBrowser


class MultiLineInput(QPlainTextEdit):
    """
    A custom multiline text edit:
     - Pressing Enter sends the message (via enterPressed signal).
     - Pressing Shift+Space inserts a newline.
    """
    enterPressed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setPlaceholderText("Enter your message")

    def keyPressEvent(self, event):
        # Pressing Enter → send message (unless Shift is pressed).
        if event.key() == Qt.Key_Return and not (event.modifiers() & Qt.ShiftModifier):
            self.enterPressed.emit()
            return  # Don't add a newline.
        # Pressing Shift+Space → insert newline
        if event.key() == Qt.Key_Space and (event.modifiers() & Qt.ShiftModifier):
            self.insertPlainText("\n")
            return
        super().keyPressEvent(event)


class ChatWidget(QWidget):
    """
    A chat interface with:
      - A ChatBrowser for messages (with HTML/CSS styling).
      - A multiline input (MultiLineInput).
      - A "Send" button.
      - A "Maximize/Minimize" button.

    The Sigmund extension connects to user_message_sent to handle server logic.
    """

    user_message_sent = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_maximized = False
        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)

        # ChatBrowser for chat messages
        self._chat_browser = ChatBrowser()
        main_layout.addWidget(self._chat_browser)

        # Input container with max height 100 (when not maximized)
        self._input_container = QWidget()
        self._input_container.setMaximumHeight(100)
        input_layout = QHBoxLayout(self._input_container)
        input_layout.setContentsMargins(0, 0, 0, 0)

        self._chat_input = MultiLineInput()
        self._chat_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._chat_input.textChanged.connect(self._on_text_changed)
        self._chat_input.enterPressed.connect(self._on_send)
        input_layout.addWidget(self._chat_input)

        # Button container for send and maximize buttons
        button_container = QWidget()
        button_layout = QVBoxLayout(button_container)
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(2)

        self._send_button = QPushButton()
        try:
            self._send_button.setIcon(qta.icon('mdi6.send'))
        except Exception:
            self._send_button.setText('➤')
        # Make the button as tall as possible
        self._send_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self._send_button.clicked.connect(self._on_send)
        # Initially disabled until input >= 3 chars
        self._send_button.setEnabled(False)
        button_layout.addWidget(self._send_button)

        # Maximize/Minimize button
        self._maximize_button = QPushButton()
        self._update_maximize_button_icon()
        self._maximize_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self._maximize_button.clicked.connect(self._toggle_maximize)
        button_layout.addWidget(self._maximize_button)
        button_layout.addStretch()

        input_layout.addWidget(button_container)

        main_layout.addWidget(self._input_container)
        self.setLayout(main_layout)

    def _update_maximize_button_icon(self):
        """Update the maximize button icon based on current state."""
        try:
            if self._is_maximized:
                self._maximize_button.setIcon(qta.icon('mdi6.arrow-collapse'))
                self._maximize_button.setToolTip("Minimize input")
            else:
                self._maximize_button.setIcon(qta.icon('mdi6.arrow-expand'))
                self._maximize_button.setToolTip("Maximize input")
        except Exception:
            if self._is_maximized:
                self._maximize_button.setText('▼')
            else:
                self._maximize_button.setText('▲')

    def _toggle_maximize(self):
        """Toggle between maximized and minimized input states."""
        if self._is_maximized:
            self._minimize_input()
        else:
            self._maximize_input()

    def _maximize_input(self):
        """Expand the input to fill the entire widget."""
        self._is_maximized = True
        self._chat_browser.setVisible(False)
        self._input_container.setMaximumHeight(16777215)  # Remove height restriction
        self._update_maximize_button_icon()
        # Give focus back to the input
        self._chat_input.setFocus()

    def _minimize_input(self):
        """Restore the input to its original size."""
        self._is_maximized = False
        self._chat_browser.setVisible(True)
        self._input_container.setMaximumHeight(100)
        self._update_maximize_button_icon()
        # Give focus back to the input
        self._chat_input.setFocus()

    def _on_text_changed(self):
        """Enable the send button when >= 3 chars in the input."""
        text = self._chat_input.toPlainText().strip()
        self._send_button.setEnabled(len(text) >= 3)

    def _on_send(self):
        text = self._chat_input.toPlainText().strip()
        # Additional check—just in case users hack around the button
        if len(text) < 3:
            return
        # Clear the input
        self._chat_input.clear()
        # If maximized, minimize before sending
        if self._is_maximized:
            self._minimize_input()
        # Add user message to chat
        self.append_message("user", f'You: {text}')
        # Emit signal so the extension can handle server logic
        self.user_message_sent.emit(text)

    def append_message(self, msg_type, text, scroll=True):
        self._chat_browser.append_message(msg_type, text, scroll)

    def clear_messages(self):
        self._chat_browser.clear_messages()
    
