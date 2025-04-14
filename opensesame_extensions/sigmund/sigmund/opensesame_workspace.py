import textwrap
import re


class WorkspaceManager:
    
    
    def __init__(self, sigmund):
        self._sigmund = sigmund
        self.content = None
        self.language = None
        self.item_name = None

    def prepare(self, content):
        return content
        
    def get(self):
        if self.item_name not in self._sigmund.item_store:
            self._item = None
            self.content, self.language = self._prepare_general_script()
        else:
            self._item = self._sigmund.item_store[self.item_name]
            if self._item.item_type == 'inline_script':
                self.content, self.language = self._prepare_inline_script()
            elif self._item.item_type == 'inline_javascript':
                self.content, self.language = \
                    self._prepare_inline_javascript()
            else:
                self.content, self.language = self._prepare_item_script()
        return self.content, self.language

    def set(self, content, language):
        if self._item is None:
            self._parse_general_script(content)
            return
        if self._item.item_type == 'inline_script':
            self._parse_inline_script(content)
            return
        if self._item.item_type == 'inline_javascript':
            self._parse_inline_javascript(content)
            return
        self._parse_item_script(content)
        
    def has_changed(self, content, language):
        if not content:
            return False
        if content == self.content \
                or content == self.strip_content(self.content):
            return False
        return True
    
    def strip_content(self, content):
        if content is None:
            return ''
        return '\n'.join(
            line for line in content.splitlines()
            if not line.startswith('# Important instructions:'))
        
    def _parse_general_script(self, content):
        self._sigmund.main_window.regenerate(content)
            
    def _prepare_general_script(self):
        script = f'''# Important instructions: You are now editing the script of an OpenSesame experiment. The scripting language is OpenSesame script, a domain-specific language, and not Python or JavaScript (although Python and JavaScript may be embedded). You can use f-string syntax to include variables and Python expressions, like this: some_keyword="Some value with a {{variable_or_expression}}". Only update the workspace with modifications of this script. Do not put any other content into the workspace. Do not include this instruction comment in your reply.
{self._sigmund.experiment.to_string()}
'''
        return script, 'opensesame'
        
    def _parse_item_script(self, content):
        self._item.from_string(content)
        self._item.update()
        self._item.open_tab()

    def _prepare_item_script(self):
        # Normally, the script starts with a 'define' line and is indented by
        # a tab. We want to undo this, and present only unindented content.
        script = self._item.to_string()
        script = textwrap.dedent(script[script.find(u'\t'):])
        script = f'''# Important instructions: You are now editing the script of an OpenSesame item called {self._item.name} of type {self._item.item_type}. The scripting language is OpenSesame script (and not Python or JavaScript), a domain-specific language. You can use f-string syntax to include variables and Python expressions, like this: some_keyword="Some value with a {{variable_or_expression}}". Only update the workspace with modifications of this script. Do not put any other content into the workspace. Do not include this instruction comment in your reply.
{script}
'''
        return script, 'opensesame'
        
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
        return f'''# Important instructions: You are now editing a Python inline_script item called {self._item.name}. Only update the workspace with modifications of this script. Do not put any other content into the workspace. Do not include this instruction comment in your reply. Do include the START_PREPARE_PHASE and START_RUN_PHASE markers in your reply.
# START_PREPARE_PHASE
{self._item.var._prepare}
# START_RUN_PHASE
{self._item.var._run}
''', 'python'

    def _parse_inline_javascript(self, content):
        pattern = r"// START_PREPARE_PHASE\s*(.*?)\s*// START_RUN_PHASE\s*(.*)"
        match = re.search(pattern, content, re.DOTALL)
        if not match:
            return
        prepare = match.group(1).strip()
        run = match.group(2).strip()
        self._item.var._prepare = prepare
        self._item.var._run = run
        self._item.update()
        self._item.open_tab()

    def _prepare_inline_javascript(self):
        return f'''// Important instructions: You are now editing a JavaScript inline_javascript item called {self._item.name}. Only update the workspace with modifications of this script. Do not put any other content into the workspace. Do not include this instruction comment in your reply. Do include the START_PREPARE_PHASE and START_RUN_PHASE markers in your reply.
// START_PREPARE_PHASE
{self._item.var._prepare}
// START_RUN_PHASE
{self._item.var._run}
''', 'javascript'
