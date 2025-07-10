import re
import sys
from qtpy.QtWidgets import QTextBrowser, QApplication
from qtpy.QtGui import QFont
from .stylesheet import DEFAULT_STYLESHEET


class ChatBrowser(QTextBrowser):
    """
    A custom QTextBrowser for displaying chat messages with proper styling.
    Handles message storage, rendering, and emoji support.
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._messages = []  # Store messages as a list of (msg_type, text) tuples
        self._init_browser()
        
    def _init_browser(self):
        """Initialize the browser with proper settings and styling."""
        self.setOpenExternalLinks(True)
        self.setReadOnly(True)
        
        # Set up emoji-supporting font
        font = QFont()
        if sys.platform == "win32":
            font.setFamily("Segoe UI, Segoe UI Emoji, Arial, sans-serif")
        elif sys.platform == "darwin":
            font.setFamily("SF Pro Display, Apple Color Emoji, Helvetica Neue, sans-serif")
        else:
            font.setFamily("Noto Sans, Noto Color Emoji, DejaVu Sans, sans-serif")
        font.setPointSize(10)
        self.setFont(font)
        
        # Set the stylesheet on the document
        self.document().setDefaultStyleSheet(DEFAULT_STYLESHEET)
        
        # Initialize with empty content
        self._render_messages()
    
    def _escape_html(self, text):
        """Escape HTML special characters."""
        return (text
                .replace('&', '&amp;')
                .replace('<', '&lt;')
                .replace('>', '&gt;')
                .replace('"', '&quot;')
                .replace("'", '&#39;'))
    
    def _render_messages(self):
        """Render all messages with the current stylesheet."""
        html_parts = ['<html><head><meta charset="utf-8"></head><body>']
        
        for msg_type, text in self._messages:
            if len(html_parts) > 1:  # Not the first message
                html_parts.append('<hr>')
            
            if msg_type == "user":
                # Escape HTML for user messages, but add br tags instead of
                # newlines, which are ignored by the text browser
                escaped_text = self._escape_html(text).replace('\n', '<br>')
                html_parts.append(f'<div class="user-message bubble">{escaped_text}</div>')
            else:
                # AI messages can contain HTML
                html_parts.append(f'<div class="ai-message bubble">{text}</div>')
        
        html_parts.append('</body></html>')
        
        # Set the HTML content
        self.setHtml(''.join(html_parts))
        
    def append_message(self, msg_type, text, scroll=True):
        """
        Public method for the extension to add a message from outside,
        e.g. for an AI reply.
        - msg_type: 'user' or 'ai' (for compatibility)
        """
        if msg_type == 'ai':
            text = self._clean_ai_message(text)
        self._messages.append((msg_type, text))
        self._render_messages()
        if scroll:
            self.scroll_to_bottom()
    
    def clear_messages(self):
        """Clear all messages from the chat."""
        self._messages.clear()
        self._render_messages()
    
    def scroll_to_bottom(self):
        """Scroll to the bottom of the chat."""
        QApplication.processEvents()
        scrollbar = self.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
        
    def _clean_ai_message(self, content):
        """Removes Anthropic-style thinking blocks from the message."""
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
