import json
from qtpy.QtWidgets import QMessageBox
from .chat_widget import OpenSesameChatWidget
from sigmund_qtwidget.sigmund_widget import SigmundWidget
from libqtopensesame.misc.config import cfg
from libqtopensesame.misc.translate import translation_context
try:
    from pyqt_code_editor import settings
except ImportError:
    settings = None
_ = translation_context('sigmund', category='extension')

MAX_POOL_FILES = 20
ACTION_CANCELLED = 'I do not approve this action.'
MISSING_TOOL_CALL = 'It looks like you are trying use a tool, but you did not actually call the tool function. Please try again. Remember to call the tool function!'


class OpenSesameSigmundWidget(SigmundWidget):
    """Extends the default Sigmund widget with OpenSesame-specific commands
    and settings.
    """
    chat_widget_cls = OpenSesameChatWidget

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._transient_settings = {
            # 'collection_opensesame': 'true',
            'tool_opensesame_select_item': 'true',
            'tool_opensesame_new_item': 'true',
            'tool_openseame_remove_item_from_parent': 'true',
            'tool_openseame_rename_item': 'true'
        }
        
    @property
    def items(self):
        return self.sigmund_extension.item_store
        
    def _confirm_action(self, msg):
        if not cfg.sigmund_review_actions:
            return True
        reply = QMessageBox.question(self, _('Review Sigmund\'s action'),
                                     msg, QMessageBox.Yes | QMessageBox.No,
                                     QMessageBox.Yes)        
        return reply == QMessageBox.Yes
        
    def run_command(self, message_text, workspace_content):
        is_command = super().run_command(message_text, workspace_content)
        # Sigmund sometimes forgets to call the tool function, and instead 
        # requests the tool use in the reply based on previous messages. If this
        # happens, send a kind reminder.
        if not is_command and 'using tool:' in message_text.lower():
            self.send_user_message(MISSING_TOOL_CALL)
        return is_command
            
    def run_command_select_item(self, item_name):
        if item_name not in self.items:
            return f'Item {item_name} does not exist.'        
        
        if not self._confirm_action(_('Select item {}').format(item_name)):
            return ACTION_CANCELLED
        self.items[item_name].open_tab()
        return f'Item {item_name} is now selected.'
        
    def run_command_new_item(self, item_name, item_type, parent_item_name,
                             index=0):
        if item_name in self.items:
            return f'Item {item_name} already exists, please choose a different name.'
        if parent_item_name not in self.items:
            return f'Parent item {parent_item_name} does not exist.'
        if not self._confirm_action(_('Create new item {}').format(item_name)):
            return ACTION_CANCELLED
        self.items.new(item_type, item_name)
        self.items[parent_item_name].insert_child_item(item_name, index)
        self.items[item_name].open_tab()
        return f'Item {item_name} has been created and is now selected.'
        
    def run_remove_item_from_parent(self, parent_item_name, index=0):
        if parent_item_name not in self.items:
            return f'Parent item {parent_item_name} does not exist.'
        if not self._confirm_action(
                _('Remove item from parent {}').format(parent_item_name)):
            return ACTION_CANCELLED
        item_name = self.items[parent_item_name].direct_children()[index].name
        self.items[parent_item_name].remove_child_item(item_name, index)
        self.items[parent_item_name].open_tab()
        return f'Item has been removed from {parent_item_name}.'
        
    def run_rename_item(self, from_item_name, to_item_name):
        if from_item_name not in self.items:
            return f'Item {from_item_name} does not exist.'
        if to_item_name in self.items:
            return f'Item {to_item_name} already exists, please choose a different name.'
        if not self._confirm_action(
                _('Rename item {} to {}').format(from_item_name, to_item_name)):
            return ACTION_CANCELLED
        self.items.rename(from_item_name, to_item_name)
        self.items[to_item_name].open_tab()
        return f'{from_item_name} has been renamed to {to_item_name}.'

    def _item_struct(self, item):
        d = {'item_name': item.name, 'item_type': item.item_type}
        if item.item_type == 'loop':
            d['variables'] = item.dm.column_names
        if item.direct_children():
            d['children'] = [
                self._item_struct(self.items[child])
                for child in item.direct_children()
            ]
        return d

    def _experiment_struct(self):
        """Recursively builds the experiment structure from items. Right now,
        item_name and item_type are included for all items. Children are
        included if available. Variables are only included for loop items. Files
        from the file pool are also included.
        """
        exp_struct = self._item_struct(
            self.items[
                self.sigmund_extension.experiment.var.start
            ]
        )
        pool_files = self.sigmund_extension.pool.files()
        if len(pool_files) > MAX_POOL_FILES:
            n_hidden = len(pool_files) - MAX_POOL_FILES
            pool_files = pool_files[:MAX_POOL_FILES] + \
                [_('(… {} more files not shown)').format(n_hidden)]
        exp_struct['file_pool'] = pool_files
        return exp_struct

    def send_user_message(self, text, *args, **kwargs):        
        text = f'''We're working on an OpenSesame experiment with the following structure:

<experiment_structure>
{json.dumps(self._experiment_struct(), indent=2)}
</experiment_structure>

''' + text
        super().send_user_message(text, *args, **kwargs)

    def _on_message_received(self, data):
        action = data.get("action", None)
        # Strip the experiment structure message if present
        if action == 'user_message':
            message_text = data.get("message", "")
            needle = '</experiment_structure>'
            message_text = message_text[message_text.find(needle) + len(needle):]
            data['message'] = message_text
        super()._on_message_received(data)
        
    def confirm_change(self, message_text, workspace_content):
        if not cfg.sigmund_review_actions:
            return True
        return super().confirm_change(message_text, workspace_content)
        