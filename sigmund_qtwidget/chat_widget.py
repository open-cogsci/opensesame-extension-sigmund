from qtpy.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QScrollArea,
    QPlainTextEdit,
    QSizePolicy,
    QApplication
)
from qtpy.QtCore import Signal, Qt, QPoint


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
            return  # Don’t add a newline.
        # Pressing Shift+Space → insert newline
        if event.key() == Qt.Key_Space and (event.modifiers() & Qt.ShiftModifier):
            self.insertPlainText("\n")
            return
        super().keyPressEvent(event)


class ChatWidget(QWidget):
    """
    A chat interface with:
      - A scrollable area for messages (bubbles).
      - A multiline input (MultiLineInput).
      - A "Send" button.

    The Sigmund extension connects to user_message_sent to handle server logic.
    """

    user_message_sent = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Scrollable area for message bubbles
        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(True)
        # Turn off horizontal scrolling
        self._scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        main_layout.addWidget(self._scroll_area)

        # A container for all message bubbles
        self._chat_container = QWidget()
        self._chat_layout = QVBoxLayout(self._chat_container)
        self._chat_layout.setAlignment(Qt.AlignTop)

        self._scroll_area.setWidget(self._chat_container)

        # Input container with max height 100
        input_container = QWidget()
        input_container.setMaximumHeight(100)
        input_row = QHBoxLayout(input_container)
        input_row.setContentsMargins(0, 0, 0, 0)

        self._chat_input = MultiLineInput()
        self._chat_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._chat_input.textChanged.connect(self._on_text_changed)
        self._chat_input.enterPressed.connect(self._on_send)
        input_row.addWidget(self._chat_input)

        self._send_button = QPushButton('➤')
        # Make the button as tall as the text input
        self._send_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        self._send_button.clicked.connect(self._on_send)
        # Initially disabled until input >= 3 chars
        self._send_button.setEnabled(False)
        input_row.addWidget(self._send_button)

        main_layout.addWidget(input_container)
        self.setLayout(main_layout)

    def resizeEvent(self, event):
        """
        Ensure the chat container matches the scroll area's viewport,
        so the message bubbles never exceed the available width.
        """
        super().resizeEvent(event)
        # Match the chat container width to the available viewport
        self._chat_container.setFixedWidth(self._scroll_area.viewport().width())

    def _on_text_changed(self):
        """Enable the send button when >= 3 chars in the input."""
        text = self._chat_input.toPlainText().strip()
        self._send_button.setEnabled(len(text) >= 3)

    def scroll_to_bottom(self):        
        # Ensure the layout is updated with any new widgets.
        QApplication.processEvents()
        
        if self._chat_layout.count() == 0:
            return
        
        # Get the last widget in the chat layout.
        last_index = self._chat_layout.count() - 1
        last_item = self._chat_layout.itemAt(last_index)
        last_widget = last_item.widget()
        
        # If there's no widget, do nothing.
        if not last_widget:
            return
        
        # Convert the widget's top-left corner to the chat_container's coordinate system.
        widget_pos_in_container = last_widget.mapTo(self._chat_container, QPoint(0, 0))
        # The y-position of the bottom edge of the last widget.
        bottom_edge = widget_pos_in_container.y() + last_widget.height()
        
        # The height of the viewport we can see.
        viewport_height = self._scroll_area.viewport().height()
        
        # Calculate how far we need to scroll so that the bottom edge is fully visible.
        scroll_value = bottom_edge - viewport_height
        
        # Make sure we don't scroll past the top.
        self._scroll_area.verticalScrollBar().setValue(max(scroll_value, 0))

    def _on_send(self):
        text = self._chat_input.toPlainText().strip()
        # Additional check—just in case users hack around the button
        if len(text) < 3:
            return
        # Clear the input
        self._chat_input.clear()
        self._add_message_bubble(text, "user_message")
        # Emit signal so the extension can handle server logic
        self.user_message_sent.emit(text)

    def _add_message_bubble(self, text, msg_type):
        """
        Adds a message bubble to the chat layout.
        - msg_type: 'user_message' or 'ai_message'
        """
        bubble_widget = QWidget()
        bubble_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        
        h_layout = QHBoxLayout()
        bubble_widget.setLayout(h_layout)
        
        label = QLabel()
        label.setWordWrap(True)
        label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.MinimumExpanding)
        # Make text selectable with mouse
        label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        
        if msg_type == "user_message":
            # Plain text for user
            # Use CSS to ensure wrapping
            label.setText(text)
            label.setStyleSheet("""
                QLabel {
                    background-color: #FFFDE7;
                    border-radius: 8px;
                    padding: 8px;
                    white-space: pre-wrap;
                }
            """)
            # Right align
            h_layout.addStretch()
            h_layout.addWidget(label)
        else:
            # HTML for AI, ensuring <pre> wraps
            label.setTextFormat(Qt.RichText)
            label.setText(text)
            label.setStyleSheet("""
                QLabel {
                    background-color: #ffffff;
                    border-radius: 8px;
                    padding: 8px;
                    white-space: pre-wrap;
                }
                QLabel pre {
                    white-space: pre-wrap !important;
                }
            """)
            h_layout.addWidget(label)
            h_layout.addStretch()
        
        self._chat_layout.addWidget(bubble_widget)
        self._chat_container.setFixedWidth(self._scroll_area.viewport().width())

    def append_message(self, msg_type, text, scroll=True):
        """
        Public method for the extension to add a message from outside,
        e.g. for an AI reply.
        """
        self._add_message_bubble(text, msg_type)
        if scroll:
            self.scroll_to_bottom()

    def clear_messages(self):
        """
        Removes every message bubble from the chat layout.
        """
        while self._chat_layout.count():
            item = self._chat_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
