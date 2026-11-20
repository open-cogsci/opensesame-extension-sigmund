"""Tests for the MCP tool registry that don't require the GUI.

Runs against a fresh per-call server, without a QApplication. (The tools
themselves marshal to the GUI thread and are tested in tests/gui.)
"""
import asyncio
import unittest

from opensesame_extensions.sigmund.sigmund_mcp_relay.servers \
    import mcp_opensesame
from mcp.server.mcpserver.exceptions import ToolError

EXPECTED_TOOLS = {
    'add_existing_item_to_parent',
    'get_general_script',
    'new_item',
    'new_inline_script',
    'new_inline_javascript',
    'remove_item_from_parent',
    'rename_item',
    'set_global_var',
    'update_general_script',
    'update_item_script',
    'update_inline_script',
    'update_inline_javascript',
    'update_loop_table',
    'update_run_if_expression',
    'get_item_example',
    'get_general_script_example',
    'get_item_script',
    'get_inline_script',
    'get_inline_javascript',
    'get_current_experiment_structure'
}


def call(server, name, arguments={}):

    with_is = {}

    def worker():
        with_is['res'] = asyncio.run(server.call_tool(name, arguments))

    worker()
    return with_is['res']


class check_registry(unittest.TestCase):

    """
    desc:
        Checks the tools that the MCP server registers, and their schemas.
    """
    def runTest(self):

        server = mcp_opensesame.make_mcp(None)()  # no extension needed here
        print('Checking the registered tools ...')
        tools = asyncio.run(server.list_tools())
        names = {t.name for t in tools}
        self.assertEqual(names, EXPECTED_TOOLS)
        for tool in tools:
            print('- %s: %s' % (tool.name, tool.description))
            self.assertIsNotNone(tool.description)
        tools = {t.name: t for t in tools}
        self.assertEqual(
            tools['new_item'].input_schema['required'],
            ['item_name', 'item_type', 'parent_item_name'])
        self.assertEqual(
            tools['update_loop_table'].input_schema['required'],
            ['item_name', 'columns'])
        self.assertEqual(
            tools['update_run_if_expression'].input_schema['required'],
            ['parent_sequence_name'])
        self.assertNotIn('required',
            tools['get_general_script'].input_schema)
        # Unknown tools and invalid arguments raise clean ToolErrors, rather
        # than crashing the server.
        with self.assertRaises(ToolError):
            call(server, 'no_such_tool')
        with self.assertRaises(ToolError) as cm:
            call(server, 'new_item', {'item_name': 'x'})
        self.assertIn('item_type', str(cm.exception))
        # Each factory call yields a fresh server, one per relay session.
        server2 = mcp_opensesame.make_mcp(None)()
        self.assertIsNot(server, server2)


if __name__ == '__main__':
    unittest.main()
