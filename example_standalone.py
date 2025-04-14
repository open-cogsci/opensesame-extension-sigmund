import sys
from qtpy.QtWidgets import QApplication, QHBoxLayout, QWidget
from sigmund_qtwidget.sigmund_widget import SigmundWidget
from pyqt_code_editor.code_editors import create_editor
from pyqt_code_editor import watchdog
import logging
logging.basicConfig(level=logging.debug)


class EditorWorkspace:
    
    def __init__(self, editor):
        self._editor = editor

    @property
    def content(self):
        text_cursor = self._editor.textCursor()
        if text_cursor.hasSelection():
            return text_cursor.selectedText()
        return self._editor.toPlainText()

    @property        
    def language(self):
        return self._editor.code_editor_language
    
    def get(self):
        text_cursor = self._editor.textCursor()
        if text_cursor.hasSelection():
            return text_cursor.selectedText(), self._editor.code_editor_language
        return self._editor.toPlainText(), self._editor.code_editor_language

    def set(self, content, language):
        text_cursor = self._editor.textCursor()
        print(content)
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

        if not editor_content:
            return False
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
