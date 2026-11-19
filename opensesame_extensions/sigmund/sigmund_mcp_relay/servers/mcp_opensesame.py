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
import re
import traceback

from qtpy.QtWidgets import QMessageBox

from mcp_relay.agent import MCPServer, call_on_gui_thread
from libqtopensesame.misc.config import cfg
from libqtopensesame.misc.translate import translation_context

_ = translation_context('sigmund_mcp_relay', category='extension')
logger = logging.getLogger(__name__)

ACTION_CANCELLED = 'I do not approve this action.'

_INLINE_SCRIPT_PATTERN = re.compile(
    r'# START_PREPARE_PHASE\s*(.*?)\s*# START_RUN_PHASE\s*(.*)', re.DOTALL)
_INLINE_JAVASCRIPT_PATTERN = re.compile(
    r'// START_PREPARE_PHASE\s*(.*?)\s*// START_RUN_PHASE\s*(.*)', re.DOTALL)


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


def _parse_inline_script(item, content):
    """Applies Python code to an inline_script item, based on the
    START_PREPARE_PHASE / START_RUN_PHASE markers.
    """
    match = _INLINE_SCRIPT_PATTERN.search(content)
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


def _parse_inline_javascript(item, content):
    """Applies JavaScript code to an inline_javascript item, based on the
    START_PREPARE_PHASE / START_RUN_PHASE markers.
    """
    match = _INLINE_JAVASCRIPT_PATTERN.search(content)
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


def _apply_script(item, script):
    """Applies a script to an item, dispatching on the item type."""
    if item.item_type == 'inline_script':
        _parse_inline_script(item, script)
    elif item.item_type == 'inline_javascript':
        _parse_inline_javascript(item, script)
    else:
        item.from_string(script)
        item.update()
        item.open_tab()


def _script_error(exc_info):
    return f'''The following error occurred when parsing the updated script:

```
{exc_info}
```
'''


# ----------------------------------------------------------------------
# Tool implementations (GUI thread)
# ----------------------------------------------------------------------

def _new_item(extension, item_name, item_type, parent_item_name, index):
    items = extension.item_store
    if item_name in items:
        return f'Item {item_name} already exists, please choose a different name.'
    if parent_item_name not in items:
        return f'Parent item {parent_item_name} does not exist.'
    if not items.valid_type(item_type):
        return f'Item type {item_type} does not exist.'
    if not _confirm_action(extension, _(
            'Create new item {} of type {} in {}?').format(
            item_name, item_type, parent_item_name)):
        return ACTION_CANCELLED
    item = items.new(item_type, item_name)
    items[parent_item_name].insert_child_item(item.name, index)
    item.open_tab()
    return f'Item {item.name} has been created and is now selected.'


def _remove_item_from_parent(extension, parent_item_name, index):
    items = extension.item_store
    if parent_item_name not in items:
        return f'Parent item {parent_item_name} does not exist.'
    parent = items[parent_item_name]
    children = parent.direct_children()
    if not children:
        return f'Item {parent_item_name} has no children.'
    if index < 0:
        index += len(children)
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


def _rename_item(extension, from_item_name, to_item_name, script):
    items = extension.item_store
    if from_item_name not in items:
        return f'Item {from_item_name} does not exist.'
    if to_item_name in items:
        return (f'Item {to_item_name} already exists, '
                'please choose a different name.')
    msg = _('Rename item {} to {}').format(from_item_name, to_item_name)
    if script is not None:
        msg += _(' and initialize its script with the provided script')
    if not _confirm_action(extension, msg + '?'):
        return ACTION_CANCELLED
    new_name = items.rename(from_item_name, to_item_name)
    if new_name is None:
        return f'Item {from_item_name} could not be renamed to {to_item_name}.'
    if script is not None:
        try:
            _apply_script(items[new_name], script)
        except Exception:
            return _script_error(traceback.format_exc())
    items[new_name].open_tab()
    return f'{from_item_name} has been renamed to {new_name}.'


def _add_existing_item_to_parent(extension, item_name, parent_item_name,
                                 index):
    items = extension.item_store
    if item_name not in items:
        return f'Item {item_name} does not exist.'
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
    items = extension.item_store
    if item_name not in items:
        return f'Item {item_name} does not exist.'
    item = items[item_name]
    if not _confirm_action(extension, _(
            'Sigmund wants to change the script of {}.').format(item_name)
            + '\n\n' + script):
        return ACTION_CANCELLED
    try:
        _apply_script(item, script)
    except Exception:
        return _script_error(traceback.format_exc())
    return f'{item_name} has been updated.'


def _update_loop_table(extension, item_name, columns):
    items = extension.item_store
    if item_name not in items:
        return f'Item {item_name} does not exist.'
    loop_item = items[item_name]
    if loop_item.item_type != 'loop':
        return f'Item {item_name} is not a loop item.'
    if not columns:
        return 'No columns were provided.'
    # Validate that all columns have the same length
    lengths = [len(values) for values in columns.values()]
    if len(set(lengths)) > 1:
        return f'All columns must have the same length, but got: {lengths}.'
    from datamatrix import DataMatrix
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
    if index < 0:
        index += n_children
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


def _get_general_script(extension):
    return extension.experiment.to_string()


def _update_general_script(extension, script):
    err_msg = extension.main_window.regenerate(script)
    if err_msg is None:
        return ('The general script has been updated. '
                'Please ask the user to review the experiment.')
    return f'An error occurred while updating the general script:\n\n{err_msg}'


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
        server = MCPServer('opensesame')

        @server.tool()
        async def new_item(item_name: str, item_type: str,
                           parent_item_name: str, index: int = 0) -> str:
            """Create a new item of the given type (e.g. 'sequence', 'loop',
            'sketchpad', 'inline_script', 'logger', 'keyboard_response',
            'feedback'), insert it into a parent item (usually a sequence)
            at the given index, and open its tab.
            """
            return await run_on_gui_thread(
                _new_item, item_name, item_type, parent_item_name, index)

        @server.tool()
        async def remove_item_from_parent(parent_item_name: str,
                                          index: int = 0) -> str:
            """Remove the child item at the given index from a parent item
            (usually a sequence), and open the parent's tab.
            """
            return await run_on_gui_thread(
                _remove_item_from_parent, parent_item_name, index)

        @server.tool()
        async def rename_item(from_item_name: str, to_item_name: str,
                              script: str | None = None) -> str:
            """Rename an item. Optionally pass a script to immediately
            initialize the item's content after renaming (same format as
            update_item_script).
            """
            return await run_on_gui_thread(
                _rename_item, from_item_name, to_item_name, script)

        @server.tool()
        async def add_existing_item_to_parent(item_name: str,
                                              parent_item_name: str,
                                              index: int = 0) -> str:
            """Insert an existing item into a parent item (usually a
            sequence) at the given index, and open the item's tab.
            """
            return await run_on_gui_thread(
                _add_existing_item_to_parent, item_name, parent_item_name,
                index)

        @server.tool()
        async def update_item_script(item_name: str, script: str) -> str:
            """Update the script of an item. For 'inline_script' items,
            include '# START_PREPARE_PHASE' and '# START_RUN_PHASE' markers
            around the Python code. For 'inline_javascript' items, use
            '// START_PREPARE_PHASE' and '// START_RUN_PHASE'. For all other
            items, provide OpenSesame script.
            """
            return await run_on_gui_thread(
                _update_item_script, item_name, script)

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
            sequence item. The default 'True' means the child always runs.
            """
            return await run_on_gui_thread(
                _update_run_if_expression, parent_sequence_name, index,
                run_if)

        @server.tool()
        async def set_global_var(var_name: str, value: str) -> str:
            """Set a global experiment variable, e.g. var_name='subject_nr',
            value='1'.
            """
            return await run_on_gui_thread(_set_global_var, var_name, value)

        @server.tool()
        async def get_general_script() -> str:
            """Return the general script: the full experiment as OpenSesame
            script.
            """
            return await run_on_gui_thread(_get_general_script)

        @server.tool()
        async def update_general_script(script: str) -> str:
            """Replace the entire experiment with the given general script
            (OpenSesame script). Returns an error message if the script could
            not be parsed.
            """
            return await run_on_gui_thread(_update_general_script, script)

        return server

    return inner
