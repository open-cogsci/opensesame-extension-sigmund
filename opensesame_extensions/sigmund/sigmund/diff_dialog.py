import sys
import difflib
from qtpy.QtWidgets import QVBoxLayout, QDialogButtonBox, QLabel, \
    QSizePolicy, QScrollArea, QWidget
from qtpy.QtCore import Qt
from libqtopensesame.dialogs.base_dialog import BaseDialog
from libqtopensesame.pyqode_extras.widgets import FallbackCodeEdit
from libqtopensesame.misc.translate import translation_context

_ = translation_context('sigmund', category='extension')
MAX_MESSAGE_HEIGHT = 200


class DiffDialog(BaseDialog):
    """
    A modal dialog that displays a unified diff (one pane) with syntax highlighting
    between old_content and new_content. Asks user to confirm or cancel.
    """

    def __init__(self, main_window, message: str, old_content: str,
                 new_content: str):
        super().__init__(main_window)

        self.setWindowTitle(_("Sigmund suggests changes"))

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
        self.diff_view = FallbackCodeEdit(self.main_window)
        self.diff_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.diff_view.panels.remove('ReadOnlyPanel')
        self.extension_manager.fire(
            'register_editor',
            editor=self.diff_view
        )
        self.diff_view.setReadOnly(True)
        # If no changes, say so; otherwise, display the diff
        if diff_text.strip():
            self.diff_view.setPlainText(diff_text, mime_type='text/x-diff')
        else:
            self.diff_view.setPlainText(_("No changes suggested."))

        layout.addWidget(self.diff_view)
        # The disclaimer label 
        disclaimer_label = QLabel(
            _("Carefully review suggested changes before applying them. Sigmund sometimes makes mistakes.")
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
        self.extension_manager.fire(
            'unregister_editor',
            editor=self.diff_view
        )
        super().done(r)
