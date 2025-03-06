import difflib
from qtpy.QtWidgets import QVBoxLayout, QDialogButtonBox, QLabel, \
    QSizePolicy, QScrollArea, QWidget, QDialog
from qtpy.QtCore import Qt
import logging
logger = logging.getLogger(__name__)
try:
    from pyqt_code_editor.editors import create_editor
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
        # The info label contains the AI message
        info_label = QLabel(message)
        info_label.setTextFormat(Qt.RichText)
        info_label.setWordWrap(True)
        info_label.setAlignment(Qt.AlignTop)
        info_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        # Check height of info_label
        if info_label.sizeHint().height() > MAX_MESSAGE_HEIGHT:
            # Use QScrollArea if the label is too large
            scroll_area = QScrollArea(self)
            scroll_area.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)
            scroll_area.setWidgetResizable(True)

            message_widget = QWidget(self)
            message_layout = QVBoxLayout(message_widget)
            message_layout.addWidget(info_label)
            scroll_area.setWidget(message_widget)
            layout.addWidget(scroll_area)
            scroll_area.setMaximumHeight(MAX_MESSAGE_HEIGHT)
        else:
            # If the label fits, add directly
            layout.addWidget(info_label)
            
        if create_editor:
            self.diff_view = create_editor()
        else:            
            self.diff_view = FallbackCodeEdit(self)
            self.diff_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            self.diff_view.panels.remove('ReadOnlyPanel')
            self.parent().parent().extension_manager.fire(
                'register_editor',
                editor=self.diff_view
            )
        self.diff_view.setReadOnly(True)
        # If no changes, say so; otherwise, display the diff
        if diff_text.strip():
            self.diff_view.setPlainText(diff_text, mime_type='text/x-diff')
        else:
            self.diff_view.setPlainText("No changes suggested.")

        layout.addWidget(self.diff_view)
        # The disclaimer label 
        disclaimer_label = QLabel(
            "Carefully review suggested changes before applying them. Sigmund sometimes makes mistakes."
            , self)
        disclaimer_label.setWordWrap(True)
        disclaimer_label.setObjectName('control-info')
        disclaimer_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout.addWidget(disclaimer_label)
        # Dialog buttons
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

        self.setLayout(layout)
        self.resize(800, 600)

    def done(self, r):
        """
        Called whenever the dialog finishes, whether via accept(), reject(),
        or the close button.
        """
        if create_editor is None:
            self.parent().parent().extension_manager.fire(
                'unregister_editor',
                editor=self.diff_view
            )
        super().done(r)
