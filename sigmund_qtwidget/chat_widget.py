import re
from qtpy.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QTextBrowser,
    QPlainTextEdit,
    QSizePolicy,
    QApplication
)
# QtAwesome is optional, but it makes the UI look better.
try:
    import qtawesome as qta
except ImportError:
    pass
from qtpy.QtCore import Signal, Qt
from qtpy.QtGui import QFont


DEFAULT_STYLESHEET = '''
.user-message {
    color: #00796b;    
}

.ai-message {
    color: #333;    
}

.bubble {
    margin: 10px;
}


/* Code blocks */
pre {
    background-color: #f5f5f5;
    border: 1px solid #ddd;
    border-radius: 4px;
    padding: 8px;
    margin: 8px 0;
    overflow-x: auto;
    font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
    font-size: 13px;
}

code {
    background-color: #f5f5f5;
    padding: 2px 4px;
    border-radius: 3px;
    font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
    font-size: 13px;
}

/* Links */
a {
    color: #0066cc;
    text-decoration: none;
}

a:hover {
    text-decoration: underline;
}

/* Lists */
ul, ol {
    margin: 8px 0;
    padding-left: 20px;
}

/* Headers */
h1, h2, h3, h4, h5, h6 {
    margin: 12px 0 8px 0;
    font-weight: 600;
}

h1 { font-size: 24px; }
h2 { font-size: 20px; }
h3 { font-size: 18px; }
h4 { font-size: 16px; }
h5 { font-size: 14px; }
h6 { font-size: 13px; }
'''


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
      - A QTextBrowser for messages (with HTML/CSS styling).
      - A multiline input (MultiLineInput).
      - A "Send" button.
      - A "Maximize/Minimize" button.

    The Sigmund extension connects to user_message_sent to handle server logic.
    """

    user_message_sent = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_maximized = False
        self._messages = []  # Store messages as a list
        self._init_ui()
        self._init_chat_browser_style()

    def _init_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)

        # QTextBrowser for chat messages
        self._chat_browser = QTextBrowser()
        self._chat_browser.setOpenExternalLinks(True)
        # Allow text selection but not editing
        self._chat_browser.setReadOnly(True)
        
        # Set a font that supports emojis
        font = QFont()
        # Use a font stack that includes emoji support
        # The exact fonts depend on the OS
        import sys
        if sys.platform == "win32":
            # Windows: Segoe UI Emoji for emojis, fallback to default fonts
            font.setFamily("Segoe UI, Segoe UI Emoji, Arial, sans-serif")
        elif sys.platform == "darwin":
            # macOS: Apple Color Emoji for emojis
            font.setFamily("SF Pro Display, Apple Color Emoji, Helvetica Neue, sans-serif")
        else:
            # Linux: Noto Color Emoji or DejaVu
            font.setFamily("Noto Sans, Noto Color Emoji, DejaVu Sans, sans-serif")
        
        font.setPointSize(10)  # Set a reasonable default size
        self._chat_browser.setFont(font)
        
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

    def _init_chat_browser_style(self):
        """Initialize the chat browser with proper styling."""
        # Set the stylesheet on the document - this is the proper way for QTextBrowser
        self._chat_browser.document().setDefaultStyleSheet(DEFAULT_STYLESHEET)
        # Set base HTML structure
        self._render_messages()

    def _render_messages(self):
        """Render all messages with the current stylesheet."""
        html_parts = []
        
        for msg_type, text in self._messages:
            if html_parts:
                html_parts.append('<hr>')
            if msg_type == "user":
                # Escape HTML for user messages
                escaped_text = self._escape_html(text)
                html_parts.append(f'<div class="user-message bubble">{escaped_text}</div>')
            else:
                # AI messages can contain HTML
                html_parts.append(f'<div class="ai-message bubble">{text}</div>')
        
        html_parts.append('')
        
        # Set the HTML content
        self._chat_browser.setHtml(''.join(html_parts))

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

    def scroll_to_bottom(self):
        """Scroll to the bottom of the chat."""
        QApplication.processEvents()
        scrollbar = self._chat_browser.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

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
        self._add_message(text, "user")
        # Emit signal so the extension can handle server logic
        self.user_message_sent.emit(text)

    def _escape_html(self, text):
        """Escape HTML special characters."""
        return (text
                .replace('&', '&')
                .replace('<', '<')
                .replace('>', '>')
                .replace('"', '"')
                .replace("'", '\''))

    def _add_message(self, text, msg_type):
        """
        Adds a message to the chat browser.
        - msg_type: 'user' or 'ai'
        - text: For user messages, plain text. For AI messages, can contain HTML.
        """
        # Store the message
        self._messages.append((msg_type, text))
        # Re-render all messages
        self._render_messages()
        # Scroll to bottom
        self.scroll_to_bottom()

    def append_message(self, msg_type, text, scroll=True):
        """
        Public method for the extension to add a message from outside,
        e.g. for an AI reply.
        - msg_type: 'user_message' or 'ai_message' (for compatibility)
        """
        # Map old message types to new ones
        if msg_type == 'user_message':
            self._add_message(text, 'user')
        else:
            self._add_message(self.clean_ai_message(text), 'ai')
        
        if scroll:
            self.scroll_to_bottom()

    def clear_messages(self):
        """
        Clears all messages from the chat browser.
        """
        self._messages.clear()
        self._render_messages()
        
    def clean_ai_message(self, content):
        """
        Removes Anthropic-style thinking blocks from the message
        """
        sig_pattern = r'<div\s+class="thinking_block_signature">(.*?)</div>'
        cont_pattern = r'<div\s+class="thinking_block_content">(.*?)</div>'    
        sig_match = re.search(sig_pattern, content)
        if sig_match:
            content = re.sub(sig_pattern, '', content, count=1)    
        cont_match = re.search(cont_pattern, content, re.MULTILINE | re.DOTALL)
        if cont_match:
            content = re.sub(cont_pattern, '', content, count=1,
                             flags=re.MULTILINE | re.DOTALL)
        return content.strip()
