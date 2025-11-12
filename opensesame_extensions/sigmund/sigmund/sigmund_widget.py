import json
import traceback
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
MAX_UNIQUE_VALUES = 5
N_MAX_RESUMES = 3
ACTION_CANCELLED = 'I do not approve this action.'
MISSING_TOOL_CALL = 'It looks like you are trying use a tool, but you did not actually call the tool function. Please try again. Remember to call the tool function!'


class OpenSesameSigmundWidget(SigmundWidget):
    """Extends the default Sigmund widget with OpenSesame-specific commands
    and settings.
    """
    chat_widget_cls = OpenSesameChatWidget

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._n_resumes_left = 0
        self._transient_settings = {  
            'tool_opensesame_select_item': 'true',
            'tool_opensesame_new_item': 'true',
            'tool_opensesame_remove_item_from_parent': 'true',
            'tool_opensesame_rename_item': 'true',
            'tool_opensesame_add_existing_item_to_parent': 'true',
            'tool_opensesame_update_item_script': 'true',
            'tool_opensesame_set_global_var': 'true'
        }
        
    @property
    def items(self):
        return self.sigmund_extension.item_store
        
    @property
    def current_item_name(self):        
        item_name = self.sigmund_extension._workspace_manager.item_name
        if item_name in self.items:
            return item_name
        return None
        
    @property
    def current_item_type(self):
        item_name = self.current_item_name
        if item_name is None:
            return None
        return self.items[item_name].item_type
        
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
        if not is_command and \
                '(suggesting opensesame action)' in message_text.lower():
            self.send_user_message(MISSING_TOOL_CALL)
            return True  # To avoid the message from being processed further
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
        
    def run_command_add_existing_item_to_parent(self, item_name,
                                                parent_item_name, index=0):
        if item_name not in self.items:
            return f'Item {item_name} does not exist.'
        if parent_item_name not in self.items:
            return f'Parent item {parent_item_name} does not exist.'
        if not self._confirm_action(_('Create new item {}').format(item_name)):
            return ACTION_CANCELLED
        self.items[parent_item_name].insert_child_item(item_name, index)
        self.items[item_name].open_tab()
        return f'Item {item_name} has been added and is now selected.'
        
    def run_command_remove_item_from_parent(self, parent_item_name, index=0):
        if parent_item_name not in self.items:
            return f'Parent item {parent_item_name} does not exist.'
        if not self._confirm_action(
                _('Remove item from parent {}').format(parent_item_name)):
            return ACTION_CANCELLED
        item_name = self.items[parent_item_name].direct_children()[index]
        self.items[parent_item_name].remove_child_item(item_name, index)
        self.items[parent_item_name].open_tab()
        return f'Item has been removed from {parent_item_name}.'
        
    def run_command_rename_item(self, from_item_name, to_item_name):
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
        
    def run_command_update_item_script(self, item_name, script):
        if item_name not in self.items:
            return f'Item {item_name} does not exist.'
        self.items[item_name].open_tab()
        item_type = self.current_item_type
        if item_type == 'inline_script':
            workspace_language = 'python'
        elif item_type == 'inline_javascript':
            workspace_language = 'javascript'
        else:
            workspace_language = 'opensesame'
        if not self.confirm_change('Sigmund wants to change the item.', script):
            return ACTION_CANCELLED
        try:
            self._workspace_manager.set(script, workspace_language)
        except Exception:
            return f'''The following error occurred when parsing the updated script:
            
```
{traceback.format_exc()}
```
'''
        return f'{item_name} has been updated.'
        
    def run_command_set_global_var(self, var_name, value):
        # To make sure that the UI reflects the global variable update, we
        # rebuld the overview area, and make sure that the general properties
        # are shown and refreshed.
        self.sigmund_extension.experiment.var.set(var_name, value)
        self.sigmund_extension.experiment.build_item_tree()
        self.sigmund_extension.tabwidget.open_general()
        self.sigmund_extension.tabwidget.currentWidget().refresh()
        return f'Global experiment variable {var_name} has been set to {value}.'

    def _item_struct(self, item):
        d = {'item_name': item.name, 'item_type': item.item_type}
        if item.item_type == 'loop':
            d['variables'] = {}
            for varname in item.dm.column_names:
                unique_values = item.dm[varname].unique
                if len(unique_values) > MAX_UNIQUE_VALUES:
                    unique_values = unique_values[:MAX_UNIQUE_VALUES] + \
                        [_('(… {} more unique values not shown)').format(
                            len(unique_values) - MAX_UNIQUE_VALUES)]
                d['variables'][varname] = unique_values
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
        exp_struct['global_vars'] = {
            key: val for key, val in
            self.sigmund_extension.experiment.var.items()
        }
        return exp_struct

    def send_user_message(self, text, *args, **kwargs):        
        system_prompt = f'''## OpenSesame context

You're working on an OpenSesame experiment with the following structure:

<experiment_structure>
{json.dumps(self._experiment_struct(), indent=2)}
</experiment_structure>

## Modifying and creating items

To create a new item:
        
1. Call `tool_opensesame_new_item` to create a new item and insert it into a parent item
2. Call `tool_opensesame_update_item_script` to define script of the newly created item

To modify an existing item:
        
1. Call `tool_opensesame_select_item` to select an existing item
2. Call `tool_opensesame_update_item_script` to update the script of the selected item
'''
        self._transient_system_prompt = system_prompt
        self._foundation_document_topics = ['opensesame']
        if self.current_item_type is not None:
            self._foundation_document_topics += [self.current_item_type]
        self._transient_settings['collection_opensesame'] = \
            'true' if cfg.sigmund_search_docs else 'false'
        super().send_user_message(text, *args, **kwargs)
        
    def send_user_triggered_message(self, *args, **kwargs):
        self._n_resumes_left = N_MAX_RESUMES
        super().send_user_triggered_message(*args, **kwargs)
        
    def confirm_change(self, message_text, workspace_content):
        if not cfg.sigmund_review_actions:
            return True
        return super().confirm_change(message_text, workspace_content)
