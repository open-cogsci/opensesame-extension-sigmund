"""Exposes the OpenSesame experiment as MCP tools through the Sigmund MCP relay.

A remote AI client (e.g. LibreChat) connects to the relay, which in turn
connects to an in-process MCP server inside the OpenSesame GUI.
"""

icon = 'help-faq'
label = "Sigmund 3"
tooltip = "Connect to Sigmund 3"
checkable = True
settings = {
    "sigmund_mcp_relay_enabled": False,
    "sigmund_mcp_relay_visible": True,
    "sigmund_mcp_relay_review_actions": True,
    "sigmund_mcp_relay_url": "https://chat.sigmundai.eu:8080",
}
modes = ["default", "ide"]
priority = 1001
