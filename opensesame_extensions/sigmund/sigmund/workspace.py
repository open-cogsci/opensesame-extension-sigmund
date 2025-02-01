import textwrap
import re
from libqtopensesame.widgets.base_widget import BaseWidget


class WorkspaceManager(BaseWidget):
    
    def get(self, item_name):
        if item_name not in self.item_store:
            self._item = None
            self._content = self.experiment.to_string()
            self._language = 'opensesame'
        else:
            self._item = self.item_store[item_name]
            if self._item.item_type == 'inline_script':
                self._content, self._language = self._prepare_inline_script()
            else:
                self._content, self._language = self._prepare_item_script()
        return self._content, self._language

    def set(self, content, language):
        # If there is no workspace content, or it hasn't changed since the
        # previous message, don't do anything
        if not content or content == self._content:
            return
        # If the workspace content isn't tied to an item, show the general
        # script
        if self._item is None:
            self.main_window.regenerate(content)
            return
        # Otherwise open the item in script view
        if self._item.item_type == 'inline_script':
            self._parse_inline_script(content)
        else:
            self._parse_item_script(content)
            
    def _parse_item_script(self, content):
        self._item.from_string(content)
        self._item.update()
        self._item.open_tab()

    def _prepare_item_script(self):
        script = self._item.to_string()
        # Normally, the script starts with a 'define' line and is indented by
        # a tab. We want to undo this, and present only unindented content.
        script = script[script.find(u'\t'):]
        return textwrap.dedent(script), 'opensesame'
        
    def _parse_inline_script(self, content):
        pattern = r"# START_PREPARE_PHASE\s*(.*?)\s*# START_RUN_PHASE\s*(.*)"
        match = re.search(pattern, content, re.DOTALL)
        if not match:
            return
        prepare = match.group(1).strip()
        run = match.group(2).strip()
        self._item.var._prepare = prepare
        self._item.var._run = run
        self._item.update()
        self._item.open_tab()

    def _prepare_inline_script(self):
        return f'''# Important: Preserve the START_PREPARE_PHASE and START_RUN_PHASE markers in your reply.
# START_PREPARE_PHASE
{self._item.var._prepare}
# START_RUN_PHASE
{self._item.var._run}
''', 'python'
