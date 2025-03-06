"""Integrates with SigmundAI.eu for copilot functionality"""

icon = 'help-faq'
label = "SigmundAI Copilot"
tooltip = "Activate SigmundAI Copilot"
checkable = True
toolbar = {
    "index": 7,
    "separator_before": False,
    "separator_after": True
}
menu = {
    "index": 4,
    "submenu": "Tools"
}
settings = {
    "sigmund_token": ""
}
modes = ["default", "ide"]
priority = 1000
