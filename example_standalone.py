import sys
from qtpy.QtWidgets import QApplication, QHBoxLayout, QWidget
from sigmund_qtwidget.sigmund_widget import SigmundWidget
from pyqt_code_editor.code_editors import create_editor
from pyqt_code_editor import watchdog
import logging
import textwrap
logging.basicConfig(level=logging.INFO, force=True)
logger = logging.getLogger(__name__)


class EditorWorkspace:
    
    def __init__(self, editor):
        self._editor = editor
        self._indentation = ''
        
    def _get_indentation(self, content):
        dedented = textwrap.dedent(content)
        lines = content.splitlines()
        dedented_lines = dedented.splitlines()
    
        for original_line, dedented_line in zip(lines, dedented_lines):
            # Skip empty lines
            if original_line.strip():
                # Count leading whitespace
                orig_leading = len(original_line) - len(original_line.lstrip(' \t'))
                ded_leading = len(dedented_line) - len(dedented_line.lstrip(' \t'))
                # The difference should be the indentation sequence
                indentation_length = orig_leading - ded_leading
                if indentation_length > 0:
                    return original_line[:indentation_length]
                return ""
        # If no non-empty lines, return no indentation
        return ""
        
    def prepare(self, content):
        if content is None:
            return content
        return textwrap.indent(content, self._indentation)             

    @property
    def content(self):
        text_cursor = self._editor.textCursor()
        if text_cursor.hasSelection():
            return text_cursor.selectedText()
        return self._editor.toPlainText()

    @property        
    def language(self):
        return self._editor.code_editor_language
        
    def _normalize_line_breaks(self, text):
        """Convert paragraph separators (U+2029) to standard newlines."""
        if text:
            return text.replace(u'\u2029', '\n')
        return text        
        
    def get(self):
        text_cursor = self._editor.textCursor()
        if text_cursor.hasSelection():
            content = self._normalize_line_breaks(text_cursor.selectedText())
        else:
            content = self._editor.toPlainText()
        self._indentation = self._get_indentation(content)
        logger.info(f'content was indented by "{self._indentation}"')        
        return content, self._editor.code_editor_language

    def set(self, content, language):
        text_cursor = self._editor.textCursor()
        if text_cursor.hasSelection():
            text_cursor.insertText(content)
            self._editor.setTextCursor(text_cursor)
        else:
            self._editor.setPlainText(content)

    def has_changed(self, content, language):
        text_cursor = self._editor.textCursor()
        if text_cursor.hasSelection():
            editor_content = text_cursor.selectedText()
        else:
            editor_content = self._editor.toPlainText()

        if content in (editor_content, self.strip_content(editor_content)):
            return False
        return True
    
    def strip_content(self, content):
        if content is None:
            return ''
        return content


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Sigmund")
        layout = QHBoxLayout()
        editor = create_editor(language='python', parent=self)
        workspace = EditorWorkspace(editor)
        sigmund_widget = SigmundWidget(self)
        sigmund_widget.set_workspace_manager(workspace)
        sigmund_widget.start_server()
        layout.addWidget(sigmund_widget)
        layout.addWidget(editor)
        self.setLayout(layout)
        
    def closeEvent(self, event):
        watchdog.shutdown()
        super().closeEvent(event)        


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MainWindow()    
    win.resize(1200, 800)
    win.show()
    sys.exit(app.exec_())
