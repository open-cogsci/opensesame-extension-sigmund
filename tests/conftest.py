#-*- coding:utf-8 -*-
"""Shared pytest configuration for the extension test suite."""
import os
import sys

TESTS_PATH = os.path.dirname(os.path.abspath(__file__))
PROJECT_PATH = os.path.dirname(TESTS_PATH)

# These settings must be in place before qtpy imports Qt, so they are
# configured here rather than inside the tests.
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('QTWEBENGINE_DISABLE_SANDBOX', '1')

# IMPORTANT: neutralize stored relay credentials before any RelayWidget is
# constructed (i.e. before the extension is activated). Without this, tests
# running on a machine that is paired with the production relay would dial
# out to the relay as soon as OpenSesame starts up.
import mcp_relay.agent.widget as _agent_widget
_agent_widget.load_state = lambda state_file: None
