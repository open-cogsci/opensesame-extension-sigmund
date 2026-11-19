# Unit tests

The unit tests roughly follow the structure of the tests in the main
OpenSesame repository: they are organized into groups of sub-tests that
correspond to sub-folders of this `tests` folder, and the gui group runs the
full PyQt application offscreen on a virtual display.

- `basic/` — Tests that don't require the graphical user interface: the MCP
  tool registry and schemas, and the parsing of the inline-script phase
  markers.
- `gui/` — Tests that boot the full OpenSesame application offscreen
  (`QT_QPA_PLATFORM=offscreen`), following the pattern of the gui test group
  in the main OpenSesame repository. These check the extension's state after
  startup, exercise all ten MCP tools through the same cross-thread path
  that a real relay session uses (GUI-thread marshalling), the
  action-review dialogs, the extension's lifecycle, and a full MCP session
  over in-memory streams.

This extension has no meaningful headless group, because it doesn't run
experiments by itself; that group exists in the main OpenSesame repository.

Shared infrastructure lives in `config/`, most importantly `harness.py`,
which boots OpenSesame once per test session.

**Important for test isolation**: the tests must never connect to the
(production) relay. `conftest.py` therefore neutralizes any stored pairing
credentials via `mcp_relay.agent.widget.load_state`, so that the relay agent
stays disconnected even on machines that are paired with the real relay. In
addition, the boot procedure disables the extensions that phone home or
spawn processes on startup (`analytics`, the old `sigmund` copilot,
`jupyter_console`, and `automatic_backup`).

## Running the tests

The tests run against the local OpenSesame source tree and the local
pyqt_code_editor checkout (which provides
`pyqt_code_editor.components.sigmund_mcp_relay`), mirroring the PYTHON_PATH
entries of OpenSesame's environment.yaml. When the repos are siblings of
this repository, `conftest.py` adds them automatically; otherwise, activate
the uv venv that has the dependencies installed. From the repository root:

~~~
# using the OpenSesame development environment
source ../OpenSesame/.venv/bin/activate
pytest tests                    # all groups
pytest tests/basic              # basic functionality only
pytest tests/gui                # offscreen gui tests
~~~
