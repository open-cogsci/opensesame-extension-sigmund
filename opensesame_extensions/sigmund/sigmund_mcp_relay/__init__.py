"""Connects MCP servers to the Sigmund 3 relay server"""

icon = 'help-faq'
label = "Sigmund 3"
tooltip = "Connect to Sigmund 3"
checkable = True
settings = {
    "sigmund_mcp_relay_enabled": False,
    "sigmund_mcp_relay_visible": True,
    "sigmund_mcp_relay_review_actions": False,
    "sigmund_mcp_relay_url": "https://chat.sigmundai.eu:8080",
}
modes = ["default", "ide"]
priority = 1001
