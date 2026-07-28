import json
import re
import textwrap
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
        self._current_item_name = None
        self._transient_settings = {
            # These are interactive tools that result in a command function being
            # called.
            'tool_opensesame_select_item': 'true',
            'tool_opensesame_new_item': 'true',
            'tool_opensesame_remove_item_from_parent': 'true',
            'tool_opensesame_rename_item': 'true',
            'tool_opensesame_add_existing_item_to_parent': 'true',
            'tool_opensesame_update_item_script': 'true',
            'tool_opensesame_update_loop_table': 'true',
            'tool_opensesame_update_run_if_expression': 'true',
            'tool_opensesame_set_global_var': 'true',
            'tool_opensesame_get_general_script': 'true',
            'tool_opensesame_update_general_script': 'true',
            # These are non-interactive tools that are handled by the server.
            'tool_opensesame_get_syntax_documentation': 'true',
            # We don't use the workspace, so disable it
            'tool_update_workspace_content': 'false',
            'tool_save_workspace_as_note': 'false'
        }
        
    @property
    def items(self):
        return self.sigmund_extension.item_store
        
    @property
    def current_item_name(self):        
        item_name = self._current_item_name
        if item_name in self.items:
            return item_name
        return None
        
    @property
    def current_item(self):
        item_name = self.current_item_name
        if item_name is None:
            return None
        return self.items[item_name]
        
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
        
    def run_command_update_run_if_expression(self, parent_sequence_name, index=0,
                                             run_if=True):
        if parent_sequence_name not in self.items:
            return f'Parent sequence item {parent_sequence_name} does not exist.'
        if not self._confirm_action(
                _('Update run-if expression in {}').format(parent_sequence_name)):
            return ACTION_CANCELLED
        self.items[parent_sequence_name].set_run_if(index, run_if)
        self.items[parent_sequence_name].open_tab()
        return f'Run-if expression has been updated in {parent_sequence_name}.'
        
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
        self._current_item_name = item_name
        if not self.confirm_change(f'Sigmund wants to change {item_name}.',
                                   script, self._get_item_script()):
            return ACTION_CANCELLED
        item_type = self.current_item_type
        try:
            if item_type == 'inline_script':
                self._parse_inline_script(script)
            elif item_type == 'inline_javascript':
                self._parse_inline_javascript(script)
            else:
                self._parse_item_script(script)
        except Exception:
            return f'''The following error occurred when parsing the updated script:
            
```
{traceback.format_exc()}
```
'''
        return f'{item_name} has been updated.'

    def run_command_update_loop_table(self, item_name, columns):
        """Updates the loop table of a loop item based on a dictionary of
        columns, similar to a DataFrame.
        """
        if item_name not in self.items:
            return f'Item {item_name} does not exist.'
        loop_item = self.items[item_name]
        if loop_item.item_type != 'loop':
            return f'Item {item_name} is not a loop item.'
        # Validate that all columns have the same length
        lengths = [len(values) for values in columns.values()]
        if len(set(lengths)) > 1:
            return f'All columns must have the same length, but got: {lengths}.'
        # Validate that there is at least one column
        if not columns:
            return 'No columns were provided.'
        from datamatrix import DataMatrix
        # Build a new DataMatrix with the provided columns
        dm = DataMatrix(length=lengths[0])
        for col_name, values in columns.items():
            dm[col_name] = values
        # Convert to a readable representation for the confirmation dialog
        if not self._confirm_action(
                _('Update loop table of {}').format(item_name) +
                f'\n\n{str(dm)}'):
            return ACTION_CANCELLED
        # Assign the new DataMatrix to the loop item and update the UI
        loop_item.dm = dm
        loop_item.update()
        self.items[item_name].open_tab()
        return f'Loop table of {item_name} has been updated with {lengths[0]} cycles and {len(columns)} columns.'

    @staticmethod
    def _format_table_preview(columns):
        """Formats a dictionary of columns into a readable table preview."""
        col_names = list(columns.keys())
        n_rows = len(next(iter(columns.values()))) if columns else 0
        lines = []
        # Header
        header = '| ' + ' | '.join(col_names) + ' |'
        separator = '| ' + ' | '.join(['---'] * len(col_names)) + ' |'
        lines.append(header)
        lines.append(separator)
        # Rows
        for i in range(n_rows):
            row = '| ' + ' | '.join(
                str(columns[col][i]) for col in col_names
            ) + ' |'
            lines.append(row)
        return '\n'.join(lines)

    def run_command_set_global_var(self, var_name, value):
        # To make sure that the UI reflects the global variable update, we
        # rebuld the overview area, and make sure that the general properties
        # are shown and refreshed.
        self.sigmund_extension.experiment.var.set(var_name, value)
        self.sigmund_extension.experiment.build_item_tree()
        self.sigmund_extension.experiment.build_item_tree()
        self.sigmund_extension.tabwidget.open_general()
        self.sigmund_extension.tabwidget.currentWidget().refresh()
        return f'Global experiment variable {var_name} has been set to {value}.'
        
    def run_command_get_general_script(self):
        return self.sigmund_extension.experiment.to_string()
        
    def run_command_update_general_script(self, script):
        err_msg = self.sigmund_extension.main_window.regenerate(script)
        if err_msg is None:
            return 'The general script has been updated. Please ask the user the review the experiment.'
        return f'An error occurred while updating the general script:\n\n{err_msg}'

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
        item_name = self.current_item_name
        item_type = self.current_item_type
        if item_name is None:
            current_item_hint = 'No item is currently selected.'
        else:
            if item_type == 'inline_script':
                scripting_hint = 'Include `# START_PREPARE_PHASE` and `# START_RUN_PHASE` markers in your script. The documentation describe the OpenSesame Python API. Please follow this API closely.'
            elif item_type == 'inline_javascript':
                scripting_hint = 'Include `// START_PREPARE_PHASE` and `// START_RUN_PHASE` markers in your script. The documentation describe the OpenSesame JavaScript API. Please follow this API closely.'
            else:
                scripting_hint = 'The scripting language is OpenSesame script (and not Python or JavaScript), a domain-specific language. The documentation contains reference syntax for items of type {item_type}. Please follow this reference syntax closely.'
            current_item_hint = '''- The currently selected item is {item_name} of type {item_type}).
- You do not need to select {item_name} again, because it is already selected.
- To modify the script of {item_name}, call `opensesame_update_item_script`.
- {scripting_hint}'''                
        system_prompt = f'''## OpenSesame context

You're working on an OpenSesame experiment with the following structure:

<experiment_structure>
{json.dumps(self._experiment_struct(), indent=2)}
</experiment_structure>

## Current item

{current_item_hint}

<current_item_script>
{self._get_item_script()}
</current_item_script>

## Modifying and creating items

To create a new item:
        
1. Call `opensesame_new_item` to create a new item and insert it into a parent item
2. Call `opensesame_update_item_script` to define script of the newly created item

To modify an existing item:
        
1. Call `opensesame_select_item` to select an existing item
2. Call `opensesame_update_item_script` to update the script of the selected item

To update a loop table:

1. Call `opensesame_update_loop_table` with a dictionary of columns, where each key is a variable name and each value is a list of cell values
'''
        self._transient_system_prompt = system_prompt
        self._foundation_document_topics = ['opensesame']
        if self.current_item_type is not None:
            self._foundation_document_topics += [self.current_item_type]
        self._transient_settings['collection_opensesame'] = \
            'true' if cfg.sigmund_search_docs else 'false'        
        super().send_user_message(text, *args, **kwargs)
        
    def confirm_change(self, message_text, workspace_content,
                       original_workspace_content=None):
        if not cfg.sigmund_review_actions:
            return True
        return super().confirm_change(message_text, workspace_content,
                                      original_workspace_content)

    def _get_item_script(self):
        item = self.current_item
        if item is None:
            return
        if item.item_type == 'inline_script':
            return self._prepare_inline_script()
        if item.item_type == 'inline_javascript':
            return self._prepare_inline_javascript()
        return self._prepare_item_script()
        
    def _parse_item_script(self, content):
        item = self.current_item
        if item is None:
            return
        item.from_string(content)
        item.update()
        item.open_tab()

    def _prepare_item_script(self):
        item = self.current_item
        if item is None:
            return ''
        # Normally, the script starts with a 'define' line and is indented by
        # a tab. We want to undo this, and present only unindented content.
        script = item.to_string()
        script = textwrap.dedent(script[script.find(u'\t'):])
        return script.strip()
        
    def _parse_inline_script(self, content):
        item = self.current_item
        if item is None:
            return        
        pattern = r"# START_PREPARE_PHASE\s*(.*?)\s*# START_RUN_PHASE\s*(.*)"
        match = re.search(pattern, content, re.DOTALL)
        if match:
            prepare = match.group(1).strip()
            run = match.group(2).strip()
        else:
            prepare = ''
            run = content
        item.var._prepare = prepare
        item.var._run = run
        item.update()
        item.open_tab()

    def _prepare_inline_script(self):
        item = self.current_item
        if item is None:
            return ''
        return f'''# START_PREPARE_PHASE
{item.var._prepare}
# START_RUN_PHASE
{item.var._run}'''

    def _parse_inline_javascript(self, content):
        item = self.current_item
        if item is None:
            return
        pattern = r"// START_PREPARE_PHASE\s*(.*?)\s*// START_RUN_PHASE\s*(.*)"
        match = re.search(pattern, content, re.DOTALL)
        if match:
            prepare = match.group(1).strip()
            run = match.group(2).strip()
        else:
            prepare = ''
            run = content
        item.var._prepare = prepare
        item.var._run = run
        item.update()
        item.open_tab()

    def _prepare_inline_javascript(self):
        item = self.current_item
        if item is None:
            return ''
        return f'''// START_PREPARE_PHASE
{item.var._prepare}
// START_RUN_PHASE
{item.var._run}'''
