loop = '''
set description "Repeatedly runs another item"
# The name of the child item, which is typically a sequence
run child_sequence
# The number of times that each cycle should be repeated. This can be a float.
set repeat 1
# Indicates whether or not the loop should be randomized [random, sequential]
set order random
# Optional: a Python expression to indicate a stop criterion for the loop. 
set break_if "acc > .75"
# Optional: if yes, then the break-if expression is evaluated also before the first cycle. [yes, no]
set break_if_on_first yes
# The loop table is defined through setcycle commands
# syntax: setcycle [cycle_nr] [column_name] [value]
setcycle 0 cue_direction left
setcycle 0 cue_validity valid
setcycle 1 cue_direction right
setcycle 1 cue_validity valid
setcycle 2 cue_direction left
setcycle 2 cue_validity valid
setcycle 3 cue_direction right
setcycle 3 cue_validity valid
setcycle 4 cue_direction left
setcycle 4 cue_validity invalid
setcycle 5 cue_direction right
setcycle 5 cue_validity invalid
'''

logger = '''
set description "Logs experimental data"
# Indicates whether all detected variables should be automatically logged [yes, no]
set auto_log yes
# Variables that should be explicitly included. This is mainly useful when auto-logging is disabled.
log condition
log response_time
log response
log correct
# Variables that should be excluded when auto-logging is enabled. This keeps the logfile clean.
exclude "*_backend"
exclude PERSISTENT
exclude TEMPORARY
exclude acc
exclude accuracy
exclude average_response_time
exclude avg_rt
exclude background
exclude closed
exclude "count_*"
exclude credentialless
exclude crossOriginIsolated
exclude datetime
exclude description
exclude devicePixelRatio
exclude disable_garbage_collection
exclude experiment_file
exclude experiment_path
exclude "font_*"
exclude foreground
exclude form_clicks
exclude fullscreen
exclude height
exclude innerHeight
exclude innerWidth
exclude isSecureContext
exclude length
exclude logfile
exclude opensesame_codename
exclude origin
exclude originAgentCluster
exclude outerHeight
exclude outerWidth
exclude "page?Offset"
exclude round_decimals
exclude "screen*"
exclude "scroll?"
exclude "sound_*"
exclude start
exclude status
exclude "time_*"
exclude total_correct
exclude total_response_time
exclude total_responses
exclude width
'''

sketchpad = '''
set description "Displays visual stimuli"
# Duration in milliseconds, "keypress", or "mouseclick"
# Important: when the sketchpad is followed by a response item, such as a keyboard response, the duration is usually set to 0, so that response collection starts immediately after the sketchpad is shown.
set duration 0

# Common style keywords applicable to most drawing commands:
# - color: Color name (e.g., 'red', 'blue') or hex value (e.g., '#FF0000')
# - penwidth: Line thickness in pixels (default: 1)
# - fill: 0 for outline only, 1 for filled shape (applies to shapes)
# - font_size: Text size in pixels (applies to text elements)
# - font_bold: yes/no for bold text (applies to text elements)
# - font_italic: yes/no for italic text (applies to text elements)
# - font_family: Font name (e.g., 'arial', 'mono') (applies to text elements)

# Syntax: draw line [sx] [sy] [ex] [ey] [**style_keywords]
draw line -200 200 0 0 color=red penwidth=3
draw line 0 0 -200 200 color=blue penwidth=3

# Syntax: draw ellipse [x] [y] [w] [h] [**style_keywords]
draw ellipse -150 -150 80 60 fill=1 color=purple

# Syntax: draw rect [x] [y] [w] [h] [**style_keywords]
draw rect 160 50 40 30 fill=0 color=darkred penwidth=3

# Syntax: draw image [x] [y] [filename] [center=yes] [scale=1] [rotation=0]
# Image file should exist in file pool
draw image 0 0 "image.png" scale=1.0 rotation=0

# Syntax: draw circle [x] [y] [r] [**style_keywords]
draw circle 100 -100 30 fill=1 color=orange

# Syntax: draw line [sx] [sy] [ex] [ey] [**style_keywords]
draw line -100 50 100 50 color=green penwidth=4

# Syntax: draw arrow [sx] [sy] [ex] [ey] [arrow_body_length=0.8] [arrow_body_width=0.5] [arrow_head_width=30] [**style_keywords]
draw arrow -150 150 -50 100 color=red penwidth=2 arrow_head_width=25

# Syntax: draw textline [x] [y] [text] [center=yes] [**style_keywords]
# Note: In sketchpad syntax, 'textline' is used instead of 'text'
draw textline -100 200 "All Visual Elements" color=darkblue font_size=18

# Syntax: draw fixdot [x] [y] [style=default] [**style_keywords]
# Styles: default, large-filled, medium-filled, small-filled, large-open, medium-open, small-open, large-cross, medium-cross, small-cross
draw fixdot 0 0 style=default color=black

# Syntax: draw gabor [x] [y] [orient] [freq] [env=gaussian] [size=96] [stdev=12] [phase=0] [color1=white] [color2=black] [bgmode=avg] [**style_keywords]
# env options: gaussian, linear, circular, rectangular
draw gabor 150 -50 orient=45 freq=0.1 size=60 env=gaussian color1=green color2=black

# Syntax: draw noise [x] [y] [env=gaussian] [size=96] [stdev=12] [color1=white] [color2='black'] [bgmode=avg] [**style_keywords]
draw noise -50 100 env=gaussian size=40 color1=white color2=black
'''

notepad = '''
set description "A simple notepad to document your experiment"
__note__
The note text goes here
__end__
'''

sequence = '''
set description "Runs a number of items in sequence"
# Important: to add new items to a sequence, do not edit the script of the sequence, but use the opensesame_new_item tool function.
# Child items are run in the order in which they are defined
# Run-if expressions are Python expressions that indicate whether an item should be run or not. To always run an item, use True.
# syntax: run [item_name] [run_if]
run target_display True
run keyboard_response True
run incorrect_feedback "correct == 0"
'''

synth_sampler = '''
# 0.0 = silent, 1.0 = maximum volume
set volume 1.0
# 0 = center, positive values toward the right, "left" or "right" for full panning
set pan 0
# Important: the duration does not relate to the duration of the sound. Instead, it indicates when the experiment should advance to the next item. A value of 0 indicates that the experiment advances immediately to the next item while the sample keeps playing in the background. A value of "sound" indicates that the experiment only advances to the next item when the sample is finished playing.
set duration 0
'''

synth = '''
set description "A basic sound synthesizer"
# sine, square, saw, white_noise
set osc sine
# Length of the sound in ms
set length 100
# Sound frequency in Hertz
set freq 440
# Sound decay in milliseconds
set decay 5
# Sound attack in milliseconds
set attack 0
''' + synth_sampler

sampler = '''
set description "Plays a sound file in .wav or .ogg format"
# Stop playback after [stop_after] ms, or 0 to play entire sample
set stop_after 0
# Sound file should exist in file pool
set sample "my_sound.ogg"
# 1.0 = original pitch
set pitch 1
# Fade-in time in ms, or 0 for no fade-in
set fade_in 0
''' + synth_sampler

keyboard_response = '''
set description "Collects keyboard responses"
# Optional: a Python expression indicating which key will be considered correct. If no correct_response is defined here, the global variable correct_response, typically defined in a loop table, is used.
set correct_response "{my_correct_response}"
# A semi-colon separated list of allowed keys. All other keys are ignored.
set allowed_responses "z;/"
# Response time out in milliseconds, or "infinite" for no timeout
set timeout infinite
# [keypress, keyrelease]
set event_type keypress
'''

mouse_response = '''
set description "Collects mouse responses"
# Response time out in milliseconds, or "infinite" for no timeout
set timeout infinite
# Indicates whether the mouse cursor should become visible during responding [yes, no]
set show_cursor yes
# Optional: a linked sketchpad can be provided to do an automatic region-of-interest analysis. The names of all elements under the clicked position are then logged as the `cursor_roi` variable.
set linked_sketchpad sketchpad_with_named_elements
# [mouseclick, mouserelease]
set event_type mouseclick
# Optional: a Python expression indicating which mouse button will be considered correct. If no correct_response is defined here, the global variable correct_response, typically defined in a loop table, is used. This does not relate to the linked sketchpad.
set correct_response "{my_correct_response}"
# A semi-colon separated list of allowed mouse buttons. All other mouse buttons are ignored.
set allowed_responses "left_button;right_button"
'''

form_multiple_choice = '''
set description "A simple multiple choice item"
# Response time out in milliseconds, or "infinite" for no timeout
set timeout infinite
set spacing 10
# The question can be a literal or defined in a {variable}
__question__
{question_text}
__end__
# The options can be literal or defined in {variables}
__options__
{question_option1}
{question_option2}
{question_option3}
__end__
# Indicates whether multiple options can be selected. If not, the participant has to select exactly one option. [yes, no]
set allow_multiple no
# Indicates whether the experiment should advance immediately when participant selects an option. If not, the participant needs to press Ok first. Only applicable when allow_multiple is no. [yes, no]
set advance_immediately yes
# The name of the response variable, which will contain a semicolon-separated list of all selected options 'no' if no option has been selected
set form_var response
set form_title "Multiple-choice question"
set button_text Ok
'''

form_text_display = '''
set description "A simple text display form"
# Response time out in milliseconds, or "infinite" for no timeout
set timeout infinite
set ok_text Start
set form_title "<b>Instructions</b>"
__form_text__
Some text, possibly including {variables}.
__end__
widget 0 0 3 1 label text="{form_title}"
widget 0 1 3 1 label center=no text="{form_text}"
widget 1 2 1 1 button text="{ok_text}"
'''

form_text_input = '''
set description "A simple text input form"
# Response time out in milliseconds, or "infinite" for no timeout
set timeout infinite
# Response variable that will contain the entered text
set form_var response
set form_title "Open question"
# The question can be a literal or defined in a {variable}
__form_question__
{question_text}
__end__
widget 0 0 1 1 label text="{form_title}"
widget 0 1 1 1 label center=no text="{form_question}"
widget 0 2 1 1 text_input focus=yes return_accepts=yes stub="" var="{form_var}"
'''
reset_feedback = '''
set description "Optionally repeat a cycle from a loop"
# A Python expression that indicates whether the cycle should be repeated. Set to True to always repeat.
set condition "acc > .7"
'''
