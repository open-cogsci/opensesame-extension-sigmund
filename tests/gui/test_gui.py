"""Tests for the relay extension running inside the offscreen PyQt GUI.

These tests boot the full OpenSesame application offscreen, following the
pattern of the gui test group in the main OpenSesame repository. The GUI
event loop is pumped while every MCP tool call runs on a worker thread, so
that the tools are marshalled to the GUI thread exactly as they are during a
real relay session.

The tests never connect to the relay: the credentials of
mcp_relay.agent.widget.load_state are neutralized (see conftest.py), so the
agent stays disconnected even on machines that are paired with the
production relay.
"""
import unittest
# The tests in this group run the graphical user interface on a virtual
# (offscreen) display, so that no real X server or Wayland session is
# required. This must be configured before qtpy imports Qt.
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('QTWEBENGINE_DISABLE_SANDBOX', '1')
from config.harness import harness


def call(name, **arguments):
    """Calls a tool through the harness and returns the plain text result."""
    res = harness().call_tool(name, **arguments)
    harness().app.processEvents()
    return res.content[0].text


class check_extension(unittest.TestCase):
    """Checks the state of the extension after OpenSesame has started.""" 
    def runTest(self):

        h = harness()
        ext = h.ext
        ext.activate()
        print('Checking the extension state after startup ...')
        self.assertGreater(len(h.items), 0)
        self.assertTrue(ext._dock_widget.isVisible())
        widget = ext._relay_widget
        self.assertEqual(sorted(widget._providers), ['files', 'opensesame'])
        self.assertEqual(widget.enabled_servers(), ['opensesame'])
        # The agent must not have connected to the relay. (On a machine with
        # real pairing credentials this would otherwise happen here!)
        self.assertEqual(widget.state, 'disconnected')
        self.assertIsNone(widget._thread)


class check_tools(unittest.TestCase):
    """Exercises all ten MCP tools through the same cross-thread path that a
    real relay session uses, including the error handling.
    """   
    def runTest(self):

        h = harness()
        print('Checking the MCP tools ...')
        # --- new_item ---
        res = call('new_item', item_name='my_sketchpad',
                   item_type='sketchpad', parent_item_name='experiment',
                   index=0)
        self.assertIn('created and is now selected', res)
        self.assertIn('my_sketchpad', h.items)
        self.assertEqual(h.win.tabwidget.current_item(), 'my_sketchpad')
        self.assertEqual(
            h.items['experiment'].direct_children()[0], 'my_sketchpad')
        res = call('new_item', item_name='my_sketchpad',
                   item_type='sketchpad', parent_item_name='experiment')
        self.assertIn('already exists', res)
        res = call('new_item', item_name='orphan', item_type='sketchpad',
                   parent_item_name='nosuchparent')
        self.assertIn('does not exist', res)
        res = call('new_item', item_name='bogus', item_type='not_a_type',
                   parent_item_name='experiment')
        self.assertIn('does not exist', res)
        self.assertIn('not_a_type', res)
        self.assertNotIn('orphan', h.items)
        self.assertNotIn('bogus', h.items)
        # --- edit item scripts ---
        res = call('new_item', item_name='my_sketchpad2',
                   item_type='sketchpad', parent_item_name='experiment',
                   index=0, script='draw textline x=0 y=0 text="before"')
        self.assertIn('before', h.items['my_sketchpad2'].to_string())
        res = call('update_item_script', item_name='my_sketchpad2',
                   script='draw textline x=0 y=0 text="after"')
        self.assertIn('after', h.items['my_sketchpad2'].to_string())
        # --- new inline_script ---
        res = call('new_inline_script', item_name='my_inline_script',
                   parent_item_name='experiment',
                   index=0, prepare_script='x = 0', run_script='print(x)')
        self.assertIn('my_inline_script', h.items)
        self.assertIn('x = 0', h.items['my_inline_script'].var._prepare)
        self.assertIn('print(x)', h.items['my_inline_script'].var._run)
        # --- edit inline_script ---
        res = call('update_inline_script', item_name='my_inline_script',
                   prepare_script='y = 0', run_script='print(y)')
        self.assertIn('y = 0', h.items['my_inline_script'].var._prepare)
        self.assertIn('print(y)', h.items['my_inline_script'].var._run)
        res = call('update_inline_script', item_name='my_sketchpad',
                   prepare_script='y = 0', run_script='print(y)')
        self.assertIn('not a valid item type', res)
        # --- new inline_javascript ---
        res = call('new_inline_javascript', item_name='my_inline_javascript',
                   parent_item_name='experiment',
                   index=0, prepare_script='x = 0', run_script='console.log(x)')
        self.assertIn('my_inline_javascript', h.items)
        self.assertIn('x = 0', h.items['my_inline_javascript'].var._prepare)
        self.assertIn('console.log(x)', h.items['my_inline_javascript'].var._run)
        # --- edit inline_javascript ---
        res = call('update_inline_javascript', item_name='my_inline_javascript',
                   prepare_script='y = 0', run_script='console.log(y)')
        self.assertIn('y = 0', h.items['my_inline_javascript'].var._prepare)
        self.assertIn('console.log(y)', h.items['my_inline_javascript'].var._run)
        # --- rename_item, optionally with an initializing script ---
        result = call('rename_item', from_item_name='my_sketchpad2',
                      to_item_name='my_renamed')
        self.assertIn('has been renamed to', result)
        self.assertIn('my_renamed', h.items)
        self.assertNotIn('my_sketchpad2', h.items)
        self.assertIn('already exists',
            call('rename_item', from_item_name='my_renamed',
                 to_item_name='my_sketchpad'))
        self.assertIn('does not exist',
            call('rename_item', from_item_name='nothere', to_item_name='x'))
        self.assertIn('my_sketchpad', h.items)
        # --- update_loop_table ---
        call('new_item', item_name='my_loop', item_type='loop',
             parent_item_name='experiment')
        result = call('update_loop_table', item_name='my_loop',
                     columns={'c1': [1, 2, 3], 'c2': ['a', 'b', 'c']})
        self.assertIn('3 cycles', result)
        dm = h.items['my_loop'].dm
        self.assertEqual(len(dm), 3)
        self.assertIn('c1', dm.column_names)
        self.assertEqual(dm['c1'][0], 1)
        self.assertIn('same length',
            call('update_loop_table', item_name='my_loop',
                 columns={'c1': [1, 2], 'c2': [1, 2, 3]}))
        self.assertIn('not a loop',
            call('update_loop_table', item_name='my_sketchpad',
                 columns={'x': [1]}))
        self.assertIn('does not exist',
            call('update_loop_table', item_name='nothere',
                 columns={'x': [1]}))
        # --- update_run_if_expression ---
        sequence = h.items['experiment']
        result = call('update_run_if_expression',
                      parent_sequence_name='experiment', index=0,
                      run_if='[width] > 100')
        self.assertIn('updated', result)
        self.assertEqual(sequence.items[0][1], '[width] > 100')
        self.assertIn('out of range',
            call('update_run_if_expression',
                 parent_sequence_name='experiment', index=999))
        self.assertIn('not a sequence',
            call('update_run_if_expression',
                 parent_sequence_name='my_sketchpad', index=0))
        self.assertIn('does not exist',
            call('update_run_if_expression',
                 parent_sequence_name='nosuch', index=0))
        # --- set_global_var, and the general script ---
        result = call('set_global_var', var_name='my_global', value='42')
        self.assertIn('has been set', result)
        # OpenSesame auto-types variable values, so '42' becomes int 42.
        self.assertEqual(h.win.experiment.var.my_global, 42)
        doc = call('get_general_script')
        self.assertIn('my_global', doc)
        # --- update_general_script ---
        result = call('update_general_script', script=doc)
        self.assertIn('has been updated', result)
        self.assertEqual(h.win.experiment.var.my_global, 42)
        result = call('update_general_script',
                      script='---\nAPI: 3.0\n---\n\nset invalid_command')
        self.assertIn('error', result.lower())
        # After a garbage update, the experiment must still be intact.
        self.assertIn('my_sketchpad', h.items)
        # --- remove_item_from_parent ---
        sequence = h.items['experiment']
        n_children = len(sequence.direct_children())
        # A negative index selects from the end.
        result = call('remove_item_from_parent',
                      parent_item_name='experiment', index=-1)
        self.assertIn('has been removed', result)
        self.assertEqual(len(sequence.direct_children()), n_children - 1)
        self.assertEqual(h.win.tabwidget.current_item(), 'experiment')
        self.assertIn('out of range',
            call('remove_item_from_parent',
                 parent_item_name='experiment', index=999))
        self.assertIn('does not exist',
            call('remove_item_from_parent', parent_item_name='nothere'))
        # --- add_existing_item_to_parent ---
        result = call('add_existing_item_to_parent',
                      item_name='my_sketchpad',
                      parent_item_name='experiment', index=1)
        self.assertIn('has been added to', result)
        self.assertIn('my_sketchpad',
            h.items['experiment'].direct_children())
        self.assertIn('does not exist',
            call('add_existing_item_to_parent', item_name='nothere',
                 parent_item_name='experiment'))
        self.assertIn('does not exist',
            call('add_existing_item_to_parent', item_name='my_sketchpad',
                 parent_item_name='nothere'))
        # -- check documentation helpers ---
        self.assertIn('sketchpad',
                      call('get_item_example', item_type='sketchpad'))
        self.assertIn('Error:',
                      call('get_item_example', item_type='fake_item_type'))
        self.assertIn('define', call('get_general_script_example'))


class check_action_review(unittest.TestCase):
    """Checks the confirmation dialogs that review each tool action when
    sigmund_mcp_relay_review_actions is enabled. The modal dialog is patched with
    fixed responses, because it cannot be clicked from a unit test.
    """
    def runTest(self):

        from libqtopensesame.misc.config import cfg
        from opensesame_extensions.sigmund.sigmund_mcp_relay.servers \
            import mcp_opensesame
        from qtpy.QtWidgets import QMessageBox
        print('Checking the action-review dialogs ...')
        cfg.sigmund_mcp_relay_review_actions = True
        answers = [QMessageBox.No]
        old_question = mcp_opensesame.QMessageBox.question
        mcp_opensesame.QMessageBox.question = \
            lambda *args, **kwds: answers[-1]
        try:
            # Refused: the tool reports that the action was cancelled, and
            # the item is not created.
            result = call('new_item', item_name='reviewed',
                          item_type='logger', parent_item_name='experiment')
            self.assertEqual(result, mcp_opensesame.ACTION_CANCELLED)
            self.assertNotIn('reviewed', harness().items)
            # Approved: the item is created as usual.
            answers.append(QMessageBox.Yes)
            result = call('new_item', item_name='reviewed',
                          item_type='logger', parent_item_name='experiment')
            self.assertIn('created and is now selected', result)
            self.assertIn('reviewed', harness().items)
        finally:
            mcp_opensesame.QMessageBox.question = old_question
            cfg.sigmund_mcp_relay_review_actions = False


class check_extension_lifecycle(unittest.TestCase):
    """Checks activating/ deactivating the extension and its close behavior."""
    def runTest(self):

        from libqtopensesame.misc.config import cfg
        h = harness()
        ext = h.ext
        print('Checking the extension lifecycle ...')
        # The extension is checkable and toggles its dock widget.
        ext.activate()
        self.assertFalse(ext._visible)
        self.assertFalse(cfg.sigmund_mcp_relay_visible)
        self.assertFalse(ext._dock_widget.isVisible())
        ext.activate()
        self.assertTrue(ext._visible)
        self.assertTrue(cfg.sigmund_mcp_relay_visible)
        self.assertTrue(ext._dock_widget.isVisible())
        # Closing the application must stop the relay agent thread. Since
        # the agent is never connected during the tests, this just checks
        # that event_close() is safe to call.
        ext.event_close()
        self.assertIsNone(ext._relay_widget._thread)
        # We assume that this test is run last, and we shut down the app without
        # askign for confirmation
        h.win.unsaved_changes = False
        h.win.close()


class check_mcp_session(unittest.TestCase):
    """Runs the server over in-memory streams with a real mcp ClientSession, the
    same setup that mcp_relay.agent.InProcessServerProvider uses in production.
    """
    def runTest(self):

        print('Checking a full MCP session over memory streams ...')

        async def main(session):

            tools = await session.list_tools()
            result = await session.call_tool(
                'set_global_var',
                {'var_name': 'session_var', 'value': 'ok'})
            self.assertFalse(result.is_error)
            self.assertEqual(harness().win.experiment.var.session_var, 'ok')

        harness().run_session(main)


if __name__ == '__main__':
    unittest.main()
