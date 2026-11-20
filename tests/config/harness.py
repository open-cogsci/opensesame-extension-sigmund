#-*- coding:utf-8 -*-
"""Boots OpenSesame with the extension offscreen, once per test session.

The boot procedure roughly follows the graphical-user-interface test in the
main OpenSesame repository (tests/gui/test_gui.py): offscreen Qt platform, the
application arguments of the regular entry point (--start-clean so that no
window state is restored), and no saving of state on close. The differences:

- The extensions that phone home or spawn auxiliary processes during startup
  are disabled: analytics (pings a server through a hidden web view), the old
  SigmundAI copilot (dials sigmundai.eu), jupyter_console (spawns an
  in-process kernel), and automatic_backup (touches the user's backup
  folder).
- The relay credentials of mcp_relay.agent.widget.load_state are neutralized
  (conftest.py does this too, but the harness repeats it so that the
  guarantee holds even when the harness is used outside of pytest), so that
  the relay widget can never dial out to the production relay from a test.

The harness also provides call_tool(), which invokes an MCP tool on a worker
thread while keeping the GUI event loop turning. This is the exact path that
a tool call takes in a real relay session: the relay agent thread runs the
asyncio code, and the tools themselves are marshalled to the GUI thread
through mcp_relay.agent.call_on_gui_thread. Calling a tool without a
responsive GUI thread would therefore deadlock rather than test the tool.
"""
import asyncio
import sys
import threading
from pathlib import Path

from libopensesame import misc  # noqa: F401
from openexp import resources
import libqtopensesame

resources.add_resource_folder(
    Path(libqtopensesame.__file__).parent / 'resources')
try:
    from qtpy import QtWebEngineWidgets  # noqa: F401,F403
except ImportError:
    pass

from libqtopensesame.misc.config import cfg

# Extensions that should not be built during the tests, see the module
# docstring.
DISABLED_EXTENSIONS = (
    'analytics',
    'sigmund',        # the old SigmundAI copilot, not the MCP relay
    'jupyter_console',
    'automatic_backup',
)

_instance = None


def harness():

    """
    desc:
        Returns the singleton harness instance, booting OpenSesame on first
        use. (An explicit function instead of an import-time boot, so that
        simply collecting the tests doesn't start the application.)
    """

    global _instance
    if _instance is None:
        _instance = _OpenSesameHarness()
    return _instance


class _OpenSesameHarness:

    """The offscreen OpenSesame application and its relay extension."""

    def __init__(self):

        # Typically already done by conftest.py, but repeated here so that
        # the no-dial-out guarantee holds in any context.
        import mcp_relay.agent.widget as agent_widget
        agent_widget.load_state = lambda state_file: None
        # QtOpenSesame parses the command line during construction. We want to
        # start clean, but also not save the cleaned settings to avoid 
        # interfering with the user config.
        old_argv = sys.argv[:]
        sys.argv = ['opensesame', '--start-clean']
        object.__setattr__(cfg, 'save' , lambda: None)
        try:
            for name in DISABLED_EXTENSIONS:
                cfg_key = f'plugin_enabled_{name}'
                cfg.register(cfg_key, True)
                setattr(cfg, cfg_key, False)
            from qtpy.QtWidgets import QApplication
            from libqtopensesame.qtopensesame import QtOpenSesame
            self.app = QApplication.instance() or QApplication(sys.argv)
            self.win = QtOpenSesame(self.app)
            self.win.resume_init()
            self.win.restore_window_state()
            self.win.show()
            self.app.processEvents()
            # Don't pop up the modal action-review dialogs during the tests;
            # individual tests enable them and patch QMessageBox.question.
            cfg.sigmund_mcp_relay_review_actions = False
        finally:
            sys.argv = old_argv
        # The window is intentionally not closed on teardown: the process
        # exits right after the tests anyway, and closing would trigger noisy
        # tear-down code of core extensions on some systems.

    @property
    def ext(self):
        return self.win.extension_manager['SigmundMcpRelay']

    @property
    def items(self):
        return self.win.experiment.items

    def server(self):
        from opensesame_extensions.sigmund.sigmund_mcp_relay.servers \
            import mcp_opensesame
        # A fresh server, as the relay creates one per session.
        return mcp_opensesame.make_mcp(self.ext)()

    def pump(self, target):

        """
        desc:
            Runs target() on a worker thread while processing GUI events, as
            required for the GUI-thread marshalling of the tools, and returns
            the result (re-raising any exception).
        """

        box = {}

        def worker():
            try:
                box['res'] = target()
            except BaseException as e:
                box['exc'] = e

        thread = threading.Thread(target=worker)
        thread.start()
        while thread.is_alive():
            self.app.processEvents()
            thread.join(0.005)
        if 'exc' in box:
            raise box['exc']
        return box['res']

    def call_tool(self, name, **arguments):

        """
        desc:
            Calls an MCP tool the way the MCP server does, on a worker
            thread, and returns the CallToolResult.
        """

        server = self.server()
        return self.pump(
            lambda: asyncio.run(server.call_tool(name, arguments)))

    def run_session(self, async_fnc):

        """
        desc:
            Runs an async function that receives an mcp ClientSession, on a
            worker thread while processing GUI events.
        """

        import anyio
        from mcp.client.session import ClientSession

        async def main():

            server = self.server()
            lowlevel = getattr(server, '_lowlevel_server', server)
            client_send, server_recv = anyio.create_memory_object_stream(100)
            server_send, client_recv = anyio.create_memory_object_stream(100)
            task = asyncio.create_task(lowlevel.run(
                server_recv, server_send,
                lowlevel.create_initialization_options()))
            try:
                async with ClientSession(client_recv, client_send) as session:
                    await session.initialize()
                    await async_fnc(session)
            finally:
                await client_send.aclose()
                await asyncio.wait_for(task, 5)

        return self.pump(lambda: asyncio.run(main()))
