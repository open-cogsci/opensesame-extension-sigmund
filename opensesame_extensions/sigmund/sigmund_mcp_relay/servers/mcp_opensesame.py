"""In-process MCP server that lets a remote MCP client (e.g. LibreChat,
through the Sigmund MCP relay) build and edit the OpenSesame experiment.

This reimplements a subset of the ``run_command_*`` functions of the original
Sigmund extension (``sigmund/sigmund_widget.py``) as MCP server tools.

Threading: the in-process MCP server runs on the relay agent's thread, while
the item store, the tab widget and the confirmation dialogs live on the GUI
thread. Every tool therefore marshals its entire implementation to the GUI
thread with ``call_on_gui_thread`` (from ``mcp_relay.agent``), wrapped in
``asyncio.to_thread`` so the agent's event loop stays responsive; the tool
call blocks until the GUI thread has produced a result.
"""

import asyncio
import functools
import logging
import traceback
from pathlib import Path
from jinja2 import Template
from qtpy.QtWidgets import QMessageBox
from datamatrix import DataMatrix
from mcp.server import MCPServer
from mcp_relay.agent import call_on_gui_thread
from libqtopensesame.misc.config import cfg
from libqtopensesame.misc.translate import translation_context

_ = translation_context('sigmund_mcp_relay', category='extension')
logger = logging.getLogger(__name__)

ACTION_CANCELLED = 'I do not approve this action.'
MAX_POOL_FILES = 20
MAX_UNIQUE_VALUES = 5

# ----------------------------------------------------------------------
# Helpers. All _tool functions below MUST run on the GUI thread (they are
# always invoked through call_on_gui_thread), because they touch the item
# store, the tab widget, or show dialogs.
# ----------------------------------------------------------------------

def _confirm_action(extension, msg):
    """Ask the user for confirmation. Returns True if action review is
    disabled in the settings.
    """
    if not cfg.sigmund_mcp_relay_review_actions:
        return True
    reply = QMessageBox.question(
        extension.main_window,
        _('Review Sigmund\'s action'),
        msg,
        QMessageBox.Yes | QMessageBox.No,
        QMessageBox.Yes,
    )
    return reply == QMessageBox.Yes


def _apply_script(item, script):
    """Applies a script to an item, dispatching on the item type."""
    item.from_string(script)
    item.update()
    item.open_tab()


def _script_error(exc_info):
    return f'''The following error occurred when parsing the updated script:

```
{exc_info}
```
'''


def _get_existing_item(extension, item_name):
    """Returns (item, None) if item_name exists, else (None, error message)."""
    items = extension.item_store
    if item_name not in items:
        return None, f'Item {item_name} does not exist.'
    return items[item_name], None


def _adjust_index(index, length):
    """Converts a negative index into its positive equivalent."""
    return index + length if index < 0 else index


def _create_item(extension, item_name, item_type, parent_item_name, index):
    """Validates the request, asks for confirmation, creates the new item and
    inserts it into the parent item. Returns (item, None) on success, or
    (None, error message) on failure.
    """
    items = extension.item_store
    if item_name in items:
        return None, (f'Item {item_name} already exists, '
                       'please choose a different name.')
    if parent_item_name not in items:
        return None, f'Parent item {parent_item_name} does not exist.'
    if not items.valid_type(item_type):
        return None, f'Item type {item_type} does not exist.'
    if not _confirm_action(extension, _(
            'Create new item {} of type {} in {}?').format(
            item_name, item_type, parent_item_name)):
        return None, ACTION_CANCELLED
    item = items.new(item_type, item_name)
    items[parent_item_name].insert_child_item(item.name, index)
    return item, None


def _confirm_script_change(extension, item_name, script):
    """Asks the user to review a script change for item_name."""
    return _confirm_action(extension, _(
        'Sigmund wants to change the script of {}.').format(item_name)
        + '\n\n' + script)


def _apply_script_safely(item, script):
    """Applies script to item. Returns None on success, else an error message.
    """
    try:
        _apply_script(item, script)
    except Exception:
        return _script_error(traceback.format_exc())
    return None


def _set_prepare_run_scripts(item, prepare_script, run_script):
    """Sets the prepare/ run scripts of an inline_script or
    inline_javascript item and refreshes the UI.
    """
    item.var._prepare = prepare_script or ''
    item.var._run = run_script or ''
    item.update()
    item.open_tab()


# ----------------------------------------------------------------------
# Tool implementations (GUI thread)
# ----------------------------------------------------------------------

def _new_item(extension, item_name, item_type, parent_item_name, index, script):
    item, error = _create_item(extension, item_name, item_type,
                               parent_item_name, index)
    if error is not None:
        return error
    item.open_tab()
    if script is not None:
        error = _apply_script_safely(item, script)
        if error is not None:
            return error
    return f'Item {item.name} has been created and is now selected.'


def _new_prepare_run_item(extension, item_name, item_type, parent_item_name,
                          index, prepare_script, run_script):
    item, error = _create_item(extension, item_name, item_type,
                               parent_item_name, index)
    if error is not None:
        return error
    _set_prepare_run_scripts(item, prepare_script, run_script)
    return f'Item {item.name} has been created and is now selected.'


def _remove_item_from_parent(extension, parent_item_name, index):
    items = extension.item_store
    if parent_item_name not in items:
        return f'Parent item {parent_item_name} does not exist.'
    parent = items[parent_item_name]
    children = parent.direct_children()
    if not children:
        return f'Item {parent_item_name} has no children.'
    index = _adjust_index(index, len(children))
    if index < 0 or index >= len(children):
        return (f'Index {index} is out of range: {parent_item_name} has '
                f'{len(children)} children.')
    item_name = children[index]
    if not _confirm_action(extension, _(
            'Remove item {} from parent {}?').format(
            item_name, parent_item_name)):
        return ACTION_CANCELLED
    parent.remove_child_item(item_name, index)
    parent.open_tab()
    return f'Item {item_name} has been removed from {parent_item_name}.'


def _rename_item(extension, from_item_name, to_item_name):
    items = extension.item_store
    item, error = _get_existing_item(extension, from_item_name)
    if error is not None:
        return error
    if to_item_name in items:
        return (f'Item {to_item_name} already exists, '
                'please choose a different name.')
    msg = _('Rename item {} to {}').format(from_item_name, to_item_name)
    if not _confirm_action(extension, msg + '?'):
        return ACTION_CANCELLED
    new_name = items.rename(from_item_name, to_item_name)
    if new_name is None:
        return f'Item {from_item_name} could not be renamed to {to_item_name}.'
    items[new_name].open_tab()
    return f'{from_item_name} has been renamed to {new_name}.'


def _add_existing_item_to_parent(extension, item_name, parent_item_name,
                                 index):
    items = extension.item_store
    item, error = _get_existing_item(extension, item_name)
    if error is not None:
        return error
    if parent_item_name not in items:
        return f'Parent item {parent_item_name} does not exist.'
    if not _confirm_action(extension, _(
            'Add existing item {} to parent {}?').format(
            item_name, parent_item_name)):
        return ACTION_CANCELLED
    items[parent_item_name].insert_child_item(item_name, index)
    items[item_name].open_tab()
    return f'Item {item_name} has been added to {parent_item_name} and is now selected.'


def _update_item_script(extension, item_name, script):
    item, error = _get_existing_item(extension, item_name)
    if error is not None:
        return error
    if not _confirm_script_change(extension, item_name, script):
        return ACTION_CANCELLED
    error = _apply_script_safely(item, script)
    if error is not None:
        return error
    return f'{item_name} has been updated.'


def _update_prepare_run_item(extension, item_name, prepare_script, run_script):
    item, error = _get_existing_item(extension, item_name)
    if error is not None:
        return error
    if '_prepare' not in item.var or '_run' not in item.var:
        return f'{item_name} is not a valid item type for this action'
    if not _confirm_script_change(extension, item_name,
                                  prepare_script + '\n\n' + run_script):
        return ACTION_CANCELLED
    _set_prepare_run_scripts(item, prepare_script, run_script)
    return f'{item_name} has been updated.'


def _update_loop_table(extension, item_name, columns):
    loop_item, error = _get_existing_item(extension, item_name)
    if error is not None:
        return error
    if loop_item.item_type != 'loop':
        return f'Item {item_name} is not a loop item.'
    if not columns:
        return 'No columns were provided.'
    # Validate that all columns have the same length
    lengths = [len(values) for values in columns.values()]
    if len(set(lengths)) > 1:
        return f'All columns must have the same length, but got: {lengths}.'
    # Build a new DataMatrix with the provided columns
    dm = DataMatrix(length=lengths[0])
    for col_name, values in columns.items():
        dm[col_name] = values
    if not _confirm_action(extension, _(
            'Update loop table of {}?').format(item_name) + f'\n\n{dm}'):
        return ACTION_CANCELLED
    # Assign the new DataMatrix to the loop item and update the UI
    loop_item.dm = dm
    loop_item.update()
    loop_item.open_tab()
    return (f'Loop table of {item_name} has been updated with {lengths[0]} '
            f'cycles and {len(columns)} columns.')


def _update_run_if_expression(extension, parent_sequence_name, index, run_if):
    items = extension.item_store
    if parent_sequence_name not in items:
        return f'Parent sequence item {parent_sequence_name} does not exist.'
    sequence = items[parent_sequence_name]
    if not hasattr(sequence, 'set_run_if'):
        return f'Item {parent_sequence_name} is not a sequence item.'
    n_children = len(sequence.items)
    index = _adjust_index(index, n_children)
    if index < 0 or index >= n_children:
        return (f'Index {index} is out of range: {parent_sequence_name} has '
                f'{n_children} children.')
    if not _confirm_action(extension, _(
            'Update run-if expression of child {} in {} to "{}"?').format(
            sequence.items[index][0], parent_sequence_name, run_if)):
        return ACTION_CANCELLED
    sequence.set_run_if(index, run_if)
    sequence.open_tab()
    return f'Run-if expression has been updated in {parent_sequence_name}.'


def _set_global_var(extension, var_name, value):
    exp = extension.experiment
    exp.var.set(var_name, value)
    # Rebuild the overview area and show/ refresh the general properties, so
    # that the UI reflects the updated global variable.
    exp.build_item_tree()
    extension.tabwidget.open_general()
    widget = extension.tabwidget.currentWidget()
    if widget is not None and hasattr(widget, 'refresh'):
        widget.refresh()
    return f'Global experiment variable {var_name} has been set to {value}.'


def _get_item_script(extension, item_name):
    item, error = _get_existing_item(extension, item_name)
    if error is not None:
        return error
    return item.to_string()
    
    
def _get_prepare_run_script(extension, item_name):
    item, error = _get_existing_item(extension, item_name)
    if error is not None:
        return error
    if '_prepare' not in item.var or '_run' not in item.var:
        return f'Item {item_name} does not have prepare and/or run scripts.'
    return {'prepare': item.var._prepare, 'run': item.var._run}


def _get_general_script(extension):
    return extension.experiment.to_string()


def _update_general_script(extension, script):
    err_msg = extension.main_window.regenerate(script)
    if err_msg is None:
        return ('The general script has been updated. '
                'Please ask the user to review the experiment.')
    return f'An error occurred while updating the general script:\n\n{err_msg}'
    
    
def _get_experiment_structure(extension):
    """Recursively builds the experiment structure from items. Right now,
    item_name and item_type are included for all items. Children are
    included if available. Variables are only included for loop items. Files
    from the file pool are also included.
    """    
    def _item_struct(item):
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
                _item_struct(extension.item_store[child])
                for child in item.direct_children()
            ]
        return d

    exp_struct = _item_struct(
        extension.item_store[extension.experiment.var.start]
    )
    pool_files = extension.pool.files()
    if len(pool_files) > MAX_POOL_FILES:
        n_hidden = len(pool_files) - MAX_POOL_FILES
        pool_files = pool_files[:MAX_POOL_FILES] + \
            [_('(… {} more files not shown)').format(n_hidden)]
    exp_struct['file_pool'] = pool_files
    exp_struct['global_vars'] = {
        key: val for key, val in extension.experiment.var.items()
    }
    return exp_struct    


def _get_doc(path, **kwargs):
    return Template((Path(__file__).parent / 'docs' / path).read_text()).render(kwargs)
    

def _available_item_types(ext):
    if ext is None:
        return []
    return (
        ext.item_store.built_in_types + list(ext.plugin_manager._plugins.keys())
    )


# ----------------------------------------------------------------------
# Server factory
# ----------------------------------------------------------------------

def make_mcp(extension):
    """An MCP server that manipulates the OpenSesame experiment.

    Returns a factory (called once per relay session by
    ``InProcessServerProvider``) that builds a fresh ``MCPServer``.
    ``extension`` is the SigmundMcpRelay extension object; ``experiment``,
    ``item_store`` etc. are accessed lazily inside each tool so that a newly
    opened experiment is picked up automatically.
    """

    def run_on_gui_thread(fnc, *args):
        return asyncio.to_thread(
            call_on_gui_thread, functools.partial(fnc, extension, *args))

    def inner():
        instructions = _get_doc('instructions.md',
                available_item_types=_available_item_types(extension))
        server = MCPServer('opensesame', instructions=instructions)
    
        @server.tool()
        async def new_item(item_name: str, item_type: str,
                           parent_item_name: str, index: int = 0,
                           script: str | None = None) -> str:
            """Create a new item of the given type and and insert it into a parent
            item at the given index.
            
            Important:
        
            - To create inline_script/ inline_javascript items, use the
              `new_inline_script` / `new_inline_javascript tools.
            - Do not guess script syntax, but use `get_item_example` to get
              a documented example.
            """
            return await run_on_gui_thread(
                _new_item, item_name, item_type, parent_item_name, index,
                script)
            
        @server.tool()
        async def new_inline_script(item_name: str, parent_item_name: str,
                                    index: int = 0,
                                    prepare_script: str | None = None,
                                    run_script: str | None = None) -> str:
            """Create a new inline_script item and insert it into a parent item
            at the given index.
            
            Important: 
        
            - Do not guess script syntax, but use
              `get_item_example(inline_script)` to get a documented example.
            """
            return await run_on_gui_thread(
                _new_prepare_run_item, item_name, 'inline_script',
                parent_item_name, index, prepare_script, run_script)
            
        @server.tool()
        async def new_inline_javascript(item_name: str, parent_item_name: str,
                                        index: int = 0,
                                        prepare_script: str | None = None,
                                        run_script: str | None = None) -> str:
            """Create a new inline_javascript item and insert it into a parent
            item at the given index.
            
            Important: 
        
            - Do not guess script syntax, but use
              `get_item_example(inline_javascript)` to get a documented example.
            """
            return await run_on_gui_thread(
                _new_prepare_run_item, item_name, 'inline_javascript',
                parent_item_name, index, prepare_script, run_script)

        @server.tool()
        async def remove_item_from_parent(parent_item_name: str,
                                          index: int = 0) -> str:
            """Remove the child item at the given index from a parent item.
            """
            return await run_on_gui_thread(
                _remove_item_from_parent, parent_item_name, index)

        @server.tool()
        async def rename_item(from_item_name: str, to_item_name: str) -> str:
            """Rename an item."""
            return await run_on_gui_thread(
                _rename_item, from_item_name, to_item_name)

        @server.tool()
        async def add_existing_item_to_parent(item_name: str,
                                              parent_item_name: str,
                                              index: int = 0) -> str:
            """Insert an existing item into a parent item at the given index.
            """
            return await run_on_gui_thread(
                _add_existing_item_to_parent, item_name, parent_item_name,
                index)

        @server.tool()
        async def update_item_script(item_name: str, script: str) -> str:
            """Update the script of an item."""
            return await run_on_gui_thread(
                _update_item_script, item_name, script)
                
        @server.tool()
        async def update_inline_script(item_name: str, prepare_script: str,
                                       run_script: str) -> str:
            """Update the Python script for the prepare and run phases of an
            inline_script item.
            """
            return await run_on_gui_thread(
                _update_prepare_run_item, item_name, prepare_script, run_script)
            
        @server.tool()
        async def update_inline_javascript(item_name: str, prepare_script: str,
                                           run_script: str) -> str:
            """Update the JavaScript for the prepare and run phases of an
            inline_javascript item.
            """
            return await run_on_gui_thread(
                _update_prepare_run_item, item_name, prepare_script, run_script)

        @server.tool()
        async def update_loop_table(item_name: str,
                                    columns: dict[str, list]) -> str:
            """Replace the loop table of a loop item with a dictionary of
            columns, where each key is a variable name and each value is a
            list of cell values. All lists must have the same length.
            """
            return await run_on_gui_thread(
                _update_loop_table, item_name, columns)

        @server.tool()
        async def update_run_if_expression(parent_sequence_name: str,
                                           index: int = 0,
                                           run_if: str = 'True') -> str:
            """Set the run-if expression of the child at the given index of a
            sequence item. The run-if statement must be a str containing a valid
            Python expression. The default 'True' means the child always runs.
            """
            return await run_on_gui_thread(
                _update_run_if_expression, parent_sequence_name, index,
                run_if)

        @server.tool()
        async def set_global_var(var_name: str, value: str) -> str:
            """Set a global experiment variable, e.g. var_name='subject_nr',
            value=1.
            """
            return await run_on_gui_thread(_set_global_var, var_name, value)
            
        @server.tool()
        async def update_general_script(script: str) -> str:
            """Replace the entire experiment with the given general script
            (OpenSesame script). Returns an error message if the script could
            not be parsed.
            """
            return await run_on_gui_thread(_update_general_script, script)            
            
        # The tools below are not run on the GUI thread

        @server.tool()
        def get_item_script(item_name: str) -> str:
            """Return the script for a given item."""
            return _get_item_script(extension, item_name)
            
        @server.tool()
        def get_inline_script(item_name: str) -> dict:
            """Return a dict with prepare and run keys containing the script for
            a given inline_script item.
            """
            return _get_prepare_run_script(extension, item_name)

        @server.tool()
        def get_inline_javascript(item_name: str) -> dict:
            """Return a dict with prepare and run keys containing the script for
            a given inline_javascript item.
            """
            return _get_prepare_run_script(extension, item_name)
            
        @server.tool()
        def get_general_script() -> str:
            """Return the general script: the full experiment as OpenSesame
            script.
            """
            return _get_general_script(extension)
            
        @server.tool()
        def get_item_example(item_type: str) -> str:
            """Get example syntax documentation for an item type."""
            if item_type == 'inline_script':
                ext = 'py'
            elif item_type == 'inline_javascript':
                ext = 'js'
            else:
                ext = 'osexp'
            try:
                return _get_doc(f'{item_type}.{ext}')
            except FileNotFoundError:
                return f'Error: no example syntax documentation for {item_type}'
                
        @server.tool()
        def get_general_script_example() -> str:
            """Get example syntax documentation for the general script."""
            return _get_doc('osexp_syntax.osexp')
        
        @server.tool()
        def get_current_experiment_structure() -> dict:
            """Get an overview of the experiment is at it currently is: item
            names and types, and variables defined by loop items. Call this tool
            whenever you're unsure about the current state.
            """
            return _get_experiment_structure(extension)
            
        return server

    return inner
