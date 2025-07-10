import difflib
from qtpy.QtWidgets import QVBoxLayout, QDialogButtonBox, QLabel, \
    QSizePolicy, QDialog, QSplitter
from qtpy.QtCore import Qt
import logging
from .chat_browser import ChatBrowser
logger = logging.getLogger(__name__)
try:
    from pyqt_code_editor.code_editors import create_editor
    logger.info('using pyqt_code_editor')
except ImportError:
    logger.info('using pyqode')
    create_editor = None
    from libqtopensesame.pyqode_extras.widgets import FallbackCodeEdit

MAX_MESSAGE_HEIGHT = 200


class DiffDialog(QDialog):
    """
    A modal dialog that displays a unified diff (one pane) with syntax highlighting
    between old_content and new_content. Asks user to confirm or cancel.
    """

    def __init__(self, parent, message: str, old_content: str,
                 new_content: str):
        super().__init__(parent)

        self.setWindowTitle("Sigmund suggests changes")

        # Use difflib.unified_diff to produce a single diff
        diff_lines = list(difflib.unified_diff(
            old_content.splitlines(),
            new_content.splitlines(),
            fromfile="Original",
            tofile="Updated",
            lineterm=''
        ))

        # Skip lines that are just the file headers (---, +++)
        diff_text = "\n".join(
            line for line in diff_lines
            if not line.startswith('---') and not line.startswith('+++')
        )

        layout = QVBoxLayout()
        self.setLayout(layout)

        # Use ChatBrowser to display the AI message
        self.message_browser = ChatBrowser(self)
        self.message_browser.append_message('ai', message)
        self.message_browser.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.message_browser.setMaximumHeight(MAX_MESSAGE_HEIGHT)
        
        # Create the diff view
        if create_editor:
            self.diff_view = create_editor(language='diff')
            # If no changes, say so; otherwise, display the diff
            if diff_text.strip():
                self.diff_view.setPlainText(diff_text)
            else:
                self.diff_view.setPlainText("No changes suggested.")
        else:
            self.diff_view = FallbackCodeEdit(self)
            self.diff_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            self.diff_view.panels.remove('ReadOnlyPanel')
            self.parent().parent().parent().extension_manager.fire(
                'register_editor',
                editor=self.diff_view
            )
            if diff_text.strip():
                self.diff_view.setPlainText(diff_text, mime_type='text/x-diff')
            else:
                self.diff_view.setPlainText("No changes suggested.")
        self.diff_view.setReadOnly(True)

        # Create a vertical splitter to hold the message browser and the diff
        splitter = QSplitter(Qt.Vertical)
        splitter.addWidget(self.message_browser)
        splitter.addWidget(self.diff_view)
        layout.addWidget(splitter)

        # The disclaimer label 
        disclaimer_label = QLabel(
            "Carefully review suggested changes before applying them. Sigmund sometimes makes mistakes.",
            self
        )
        disclaimer_label.setWordWrap(True)
        disclaimer_label.setObjectName('control-info')
        disclaimer_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout.addWidget(disclaimer_label)

        # Dialog buttons
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

        self.resize(800, 600)

    def done(self, r):
        """
        Called whenever the dialog finishes, whether via accept(), reject(),
        or the close button.
        """
        if create_editor is None:
            self.parent().parent().parent().extension_manager.fire(
                'unregister_editor',
                editor=self.diff_view
            )
        super().done(r)