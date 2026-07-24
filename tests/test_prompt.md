# Autonomous OpenSesame Tool Unit Test Suite

## Objective

You are tasked with autonomously running a comprehensive unit test suite for **all** available OpenSesame and note/workspace tools. There are 12 tools to test. Each tool must be covered by at least one test case consisting of: setup, execution, verification, and todo-list update. Work through the tests **step by step**, waiting for each tool call to complete before proceeding to the next.

## Phase 0: Setup

### Step 0.1 — Store Default Template

Store the following default template script as a persistent note with label **"default_template"**. This will be used to reset the experiment between tests.

```
---
API: 3
OpenSesame: 4.1.17
Platform: posix
---
set width 1024
set title "New experiment"
set subject_parity even
set subject_nr 0
set start experiment
set sound_sample_size -16
set sound_freq 48000
set sound_channels 2
set sound_buf_size 1024
set round_decimals 2
set height 768
set fullscreen no
set form_clicks no
set foreground white
set font_underline no
set font_size 18
set font_italic no
set font_family mono
set font_bold no
set experiment_path None
set disable_garbage_collection yes
set description "The main experiment item"
set canvas_backend psycho
set background "#3d3846"

define sequence experiment
	set flush_keyboard yes
	set description "Runs a number of items in sequence"
	run getting_started True
	run welcome True

define notepad getting_started
	__note__
	Welcome to OpenSesame 4.1 "Neonatal Nightingale"!
	If you are new to OpenSesame, it is a good idea to follow one of the tutorials,
	which can be found on the documentation site:
	- <http://osdoc.cogsci.nl/>
	You can also check out the examples. These can be opened via:
	- Menu -> Tools -> Example experiments.
	And feel free to ask for help on the forum:
	- <http://forum.cogsci.nl/>
	Have fun with OpenSesame!
	__end__
	set description "A simple notepad to document your experiment. This plug-in does nothing."

define sketchpad welcome
	set start_response_interval no
	set reset_variables no
	set duration keypress
	set description "Displays stimuli"
	draw textline center=1 color=white font_bold=no font_family=serif font_italic=no font_size=32 html=yes show_if=True text="OpenSesame 4.1 <i>Neonatal Nightingale</i>" x=0 y=0 z_index=0
```

### Step 0.2 — Store Test Instructions

Store a description of all 12 test cases (listed below in the "Test Cases" section) as a persistent note with label **"test_instructions"**. The content should describe each test's tool, arguments, and verification criteria in sufficient detail for the test to be performed.

### Step 0.3 — Store Todo List

Store the following todo list as a persistent note with label **"todo_list"**. As each test completes, update this note to mark the corresponding item as checked (`[x]`).

```
- [ ] Test 1: opensesame_get_general_script
- [ ] Test 2: opensesame_get_syntax_documentation
- [ ] Test 3: opensesame_set_global_var
- [ ] Test 4: opensesame_new_item
- [ ] Test 5: opensesame_select_item
- [ ] Test 6: opensesame_update_item_script
- [ ] Test 7: opensesame_rename_item
- [ ] Test 8: opensesame_add_existing_item_to_parent
- [ ] Test 9: opensesame_remove_item_from_parent
- [ ] Test 10: opensesame_update_loop_table
- [ ] Test 11: opensesame_update_run_if_expression
- [ ] Test 12: opensesame_update_general_script
```

## Reset Procedure

Before **each** test that modifies experiment state (Tests 3–12), reset the experiment to the default template:

1. Retrieve the default template from the **"default_template"** note.
2. Call `opensesame_update_general_script` with the default template script.

Tests 1 and 2 do **not** require resets (they are read-only or operate on notes/workspace).

## Test Cases

### Test 1: opensesame_get_general_script

- **Tool:** `opensesame_get_general_script`
- **Arguments:** none
- **Steps:**
  1. Call `opensesame_get_general_script()`.
- **Verification:**
  - The returned script contains `define sequence experiment`.
  - The returned script contains `define sketchpad welcome`.
  - The returned script contains `define notepad getting_started`.
- **After:** Update the "todo_list" note to mark Test 1 as `[x]`.

### Test 2: opensesame_get_syntax_documentation

- **Tool:** `opensesame_get_syntax_documentation`
- **Arguments:** `item_types=["loop", "sketchpad"]`, `save_as="note"`
- **Steps:**
  1. Call `opensesame_get_syntax_documentation(item_types=["loop", "sketchpad"], save_as="note")`.
- **Verification:**
  - The tool call completed without error.
  - A note was created (or updated) containing syntax documentation for `loop` and `sketchpad` item types.
- **After:** Update the "todo_list" note to mark Test 2 as `[x]`.

### Test 3: opensesame_set_global_var

- **Tool:** `opensesame_set_global_var`
- **Arguments:** `var_name="test_variable"`, `value=42`
- **Steps:**
  1. Reset general script to default template.
  2. Call `opensesame_set_global_var(var_name="test_variable", value=42)`.
  3. Call `opensesame_get_general_script()`.
- **Verification:**
  - The script contains `set test_variable 42`.
- **After:** Update the "todo_list" note to mark Test 3 as `[x]`.

### Test 4: opensesame_new_item

- **Tool:** `opensesame_new_item`
- **Arguments:** `item_name="test_sketchpad"`, `item_type="sketchpad"`, `parent_item_name="experiment"`, `index=1`
- **Steps:**
  1. Reset general script to default template.
  2. Call `opensesame_new_item(item_name="test_sketchpad", item_type="sketchpad", parent_item_name="experiment", index=1)`.
  3. Call `opensesame_get_general_script()`.
- **Verification:**
  - The script contains `define sketchpad test_sketchpad`.
  - The experiment sequence contains `run test_sketchpad` (at index 1, between `getting_started` and `welcome`).
- **After:** Update the "todo_list" note to mark Test 4 as `[x]`.

### Test 5: opensesame_select_item

- **Tool:** `opensesame_select_item`
- **Arguments:** `item_name="welcome"`
- **Steps:**
  1. Reset general script to default template.
  2. Call `opensesame_select_item(item_name="welcome")`.
- **Verification:**
  - The current item context (shown in the conversation after the tool call) indicates that `welcome` is the selected item.
  - The current item script contains `draw textline`.
- **After:** Update the "todo_list" note to mark Test 5 as `[x]`.

### Test 6: opensesame_update_item_script

- **Tool:** `opensesame_update_item_script`
- **Arguments:** `item_name="test_sketchpad"`, `script` = the updated script below
- **Updated script to pass:**

```
set start_response_interval no
set reset_variables no
set duration keypress
set description "Displays stimuli"
draw textline center=1 color=white font_bold=no font_family=mono font_italic=no font_size=18 html=yes show_if=True text="Test stimulus" x=0 y=0 z_index=0
```

- **Steps:**
  1. Reset general script to default template.
  2. Call `opensesame_new_item(item_name="test_sketchpad", item_type="sketchpad", parent_item_name="experiment", index=1)`.
  3. Call `opensesame_select_item(item_name="test_sketchpad")`.
  4. Call `opensesame_update_item_script(item_name="test_sketchpad", script=<updated script above>)`.
  5. Call `opensesame_get_general_script()`.
- **Verification:**
  - The script contains `text="Test stimulus"` inside the `test_sketchpad` definition.
  - The script contains `draw textline` inside the `test_sketchpad` definition.
- **After:** Update the "todo_list" note to mark Test 6 as `[x]`.

### Test 7: opensesame_rename_item

- **Tool:** `opensesame_rename_item`
- **Arguments:** `from_item_name="test_sketchpad"`, `to_item_name="renamed_sketchpad"`
- **Steps:**
  1. Reset general script to default template.
  2. Call `opensesame_new_item(item_name="test_sketchpad", item_type="sketchpad", parent_item_name="experiment", index=1)`.
  3. Call `opensesame_rename_item(from_item_name="test_sketchpad", to_item_name="renamed_sketchpad")`.
  4. Call `opensesame_get_general_script()`.
- **Verification:**
  - The script contains `define sketchpad renamed_sketchpad`.
  - The script does **not** contain `define sketchpad test_sketchpad` (old name is gone).
  - The experiment sequence contains `run renamed_sketchpad` (not `run test_sketchpad`).
- **After:** Update the "todo_list" note to mark Test 7 as `[x]`.

### Test 8: opensesame_add_existing_item_to_parent

- **Tool:** `opensesame_add_existing_item_to_parent`
- **Arguments:** `item_name="welcome"`, `parent_item_name="test_sequence"`, `index=0`
- **Steps:**
  1. Reset general script to default template.
  2. Call `opensesame_new_item(item_name="test_loop", item_type="loop", parent_item_name="experiment", index=1)`.
  3. Call `opensesame_new_item(item_name="test_sequence", item_type="sequence", parent_item_name="test_loop", index=0)`.
  4. Call `opensesame_add_existing_item_to_parent(item_name="welcome", parent_item_name="test_sequence", index=0)`.
  5. Call `opensesame_get_general_script()`.
- **Verification:**
  - The script contains `run welcome` inside the `define sequence test_sequence` block.
  - The `welcome` item definition still exists (it was linked, not moved).
- **After:** Update the "todo_list" note to mark Test 8 as `[x]`.

### Test 9: opensesame_remove_item_from_parent

- **Tool:** `opensesame_remove_item_from_parent`
- **Arguments:** `parent_item_name="test_sequence"`, `index=0`
- **Steps:**
  1. Reset general script to default template.
  2. Call `opensesame_new_item(item_name="test_loop", item_type="loop", parent_item_name="experiment", index=1)`.
  3. Call `opensesame_new_item(item_name="test_sequence", item_type="sequence", parent_item_name="test_loop", index=0)`.
  4. Call `opensesame_add_existing_item_to_parent(item_name="welcome", parent_item_name="test_sequence", index=0)`.
  5. Call `opensesame_remove_item_from_parent(parent_item_name="test_sequence", index=0)`.
  6. Call `opensesame_get_general_script()`.
- **Verification:**
  - The `define sequence test_sequence` block does **not** contain `run welcome`.
  - The `define sketchpad welcome` item definition still exists in the script (it was only removed from the parent, not deleted).
- **After:** Update the "todo_list" note to mark Test 9 as `[x]`.

### Test 10: opensesame_update_loop_table

- **Tool:** `opensesame_update_loop_table`
- **Arguments:** `item_name="test_loop"`, `columns` = dictionary below
- **Columns:**

```json
{
	"condition": ["congruent", "incongruent", "neutral"],
	"target_side": ["left", "right", "center"],
	"correct_response": ["z", "m", "space"]
}
```

- **Steps:**
  1. Reset general script to default template.
  2. Call `opensesame_new_item(item_name="test_loop", item_type="loop", parent_item_name="experiment", index=1)`.
  3. Call `opensesame_update_loop_table(item_name="test_loop", columns={"condition": ["congruent", "incongruent", "neutral"], "target_side": ["left", "right", "center"], "correct_response": ["z", "m", "space"]})`.
  4. Call `opensesame_get_general_script()`.
- **Verification:**
  - The `define loop test_loop` block contains `set cycles 3`.
  - The loop table contains a column named `condition`.
  - The loop table contains a column named `target_side`.
  - The loop table contains a column named `correct_response`.
  - The loop table contains the value `congruent` somewhere.
- **After:** Update the "todo_list" note to mark Test 10 as `[x]`.

### Test 11: opensesame_update_run_if_expression

- **Tool:** `opensesame_update_run_if_expression`
- **Arguments:** `parent_sequence_name="experiment"`, `index=1`, `run_if="correct == 1"`
- **Steps:**
  1. Reset general script to default template.
  2. Call `opensesame_new_item(item_name="test_sketchpad", item_type="sketchpad", parent_item_name="experiment", index=1)`.
  3. Call `opensesame_update_run_if_expression(parent_sequence_name="experiment", index=1, run_if="correct == 1")`.
  4. Call `opensesame_get_general_script()`.
- **Verification:**
  - The experiment sequence contains `run test_sketchpad correct == 1` (i.e., the run-if expression `correct == 1` is associated with the item at index 1).
  - The item at index 0 (`getting_started`) still has `run getting_started True` (unaffected).
- **After:** Update the "todo_list" note to mark Test 11 as `[x]`.

### Test 12: opensesame_update_general_script

- **Tool:** `opensesame_update_general_script`
- **Arguments:** `script` = the default template with the title changed from `"New experiment"` to `"Test Experiment"`
- **Steps:**
  1. Reset general script to default template (to ensure a clean starting point).
  2. Call `opensesame_get_general_script()` to retrieve the current script.
  3. Modify the retrieved script: replace `set title "New experiment"` with `set title "Test Experiment"`.
  4. Call `opensesame_update_general_script(script=<modified script>)`.
  5. Call `opensesame_get_general_script()`.
- **Verification:**
  - The returned script contains `set title "Test Experiment"`.
  - The returned script does **not** contain `set title "New experiment"`.
  - The rest of the script is unchanged (still contains `define sequence experiment`, `define sketchpad welcome`, etc.).
- **After:** Update the "todo_list" note to mark Test 12 as `[x]`.

## Final Steps

After all 12 tests are completed:

1. **Update the "todo_list" note** to show all 12 items as checked (`[x]`).
2. **Reset the general script** to the default template one final time (clean up).
3. **Clean up temporary notes:** Remove any notes created during testing that are not part of the persistent infrastructure (e.g., "workspace_backup", syntax documentation notes if temporary). Keep the "default_template", "test_instructions", and "todo_list" notes.
4. **Provide a summary** of all test results in your response, listing each test number, tool name, and whether it passed ✅ or failed ❌. If any test failed, briefly explain what went wrong.

## Important Notes

- **Work step by step.** Do not try to batch independent calls unless they truly have no dependencies. Wait for each tool call to return before proceeding.
- **Always use the exact default template script** (stored in the "default_template" note) for resets.
- **For resets:** You do **not** need to call `opensesame_get_syntax_documentation` before each reset.
- **Update the "todo_list" note after EACH test**, not just at the end.
- **If a test fails**, note the failure, continue with the next test, and report all failures in the final summary.
- **For tests that require setup** (e.g., creating items before testing a tool), perform the setup steps as part of that test case.
- **Do not select an item that is already selected.** If an item is already selected, skip the select call or select a different item first.
