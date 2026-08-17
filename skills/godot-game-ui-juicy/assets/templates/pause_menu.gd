class_name PauseMenu
extends CanvasLayer

## Pause overlay, built in code, on its own high CanvasLayer.
##
## Two things make a pause menu in Godot specifically annoying, and both are handled here:
##
## 1. PROCESS_MODE_ALWAYS on EVERY node in the overlay, not just the root. `get_tree().paused`
##    stops processing for everything inheriting PAUSABLE, and a button whose parent chain
##    inherits the default will not respond to clicks — the menu appears and does nothing,
##    which looks like a broken UI rather than a paused tree.
##
## 2. It emits signals instead of calling a scene-flow singleton. A pause menu that hard-codes
##    `SceneFlow.goto_menu()` only works in the project it was written for; connecting three
##    signals is the entire integration cost of reusing it.
##
## Note for anyone driving this from an automation/debug bridge: most such bridges poll from
## a pausable callback, so pausing the tree also freezes the bridge and the pause menu becomes
## unreachable. If yours does, set the bridge autoload's process_mode to ALWAYS too.
##
## 3. ANIMATING WHILE PAUSED. The same rule that stops the buttons responding stops the
##    entrance animation: a Tween's pause mode defaults to BOUND, so it inherits the process
##    mode of the node that created it and freezes on frame one of a paused tree. Everything
##    here goes through UiJuice, which sets TWEEN_PAUSE_PROCESS. The failure is unusually
##    confusing when it happens — the panel is stuck at 86% scale and half-transparent, which
##    reads as a rendering bug rather than a paused tree.
##
## The menu grows in from slightly small with an overshoot and its rows arrive in sequence;
## on the way out it shrinks and fades in about a third the time. Call dismiss() rather than
## queue_free() to get the exit — see the comment there for why both exist.

signal resume_requested()
signal restart_requested()
## "Quit to menu" — leave the run, not the game. Named to match ResultsScreen.menu_requested,
## because the two screens offer the same choice and an integrator will wire them to the same
## handler. It used to be called quit_requested here and menu_requested there, and the obvious
## reading of a signal named quit_requested is get_tree().quit() — so the button labelled
## "Quit to menu" closed the application. TitleScreen.quit_requested is the one that means it.
signal menu_requested()
## Only emitted by the optional "Quit to desktop" button below. Really quits.
signal quit_requested()
signal sensitivity_changed(value: float)
signal volume_changed(value: float)

@export var title_text: String = "Paused"
@export var subtitle_text: String = ""

## One caption per button, named after the signal it emits rather than after the default text.
## Changing what a button SAYS and changing what it MEANS are separate edits — that is already
## why the signals are named the way they are above, and a frozen caption is the same coupling
## from the other side. Defaults are the previous hard-coded strings, so existing scenes are
## unaffected. Note that menu_label captions menu_requested ("leave the run") and quit_label
## captions quit_requested ("leave the game"); see the signal comments before swapping them.
@export var resume_label: String = "Resume"
@export var restart_label: String = "Restart"
@export var menu_label: String = "Quit to menu"
@export var quit_label: String = "Quit to desktop"
@export var show_restart: bool = true
## Off by default: in most games the pause menu returns you to a title screen that has its own
## Quit, and two adjacent buttons whose labels both start with "Quit" is how a player loses a
## run by misreading one of them.
@export var show_quit_to_desktop: bool = false

## Same idea for the two sliders. A game with no camera-look system and no audio bus used to
## ship both of them anyway — visible, draggable, and connected to signals nobody wired — and
## a control that does nothing reads to a player as a broken menu rather than as a feature
## this game does not have. Both default to on, so existing projects are unaffected. Turning
## one off leaves its field null, which is what the null checks in set_values() are for; the
## stagger below walks whatever rows were actually built, so it needs no matching edit.
@export var show_sensitivity: bool = true
@export var show_volume: bool = true

var _sensitivity: HSlider = null
var _volume: HSlider = null
var _root: Control = null
var _panel: PanelContainer = null
var _dismissing: bool = false


func _ready() -> void:
	layer = 50
	process_mode = Node.PROCESS_MODE_ALWAYS
	_build()
	_fit()
	var vp: Viewport = get_viewport()
	if vp != null and not vp.size_changed.is_connected(_fit):
		vp.size_changed.connect(_fit)


func _fit() -> void:
	UiTheme.fit(self, _root)


## Seed the sliders from the game's current values so the menu opens showing the truth.
func set_values(sensitivity: float, volume: float) -> void:
	if _sensitivity != null:
		_sensitivity.set_value_no_signal(sensitivity)
	if _volume != null:
		_volume.set_value_no_signal(volume)


func _build() -> void:
	var root: Control = _always(Control.new())
	root.name = "Root"
	root.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(root)
	_root = root
	root.add_child(UiTheme.backdrop())

	# Anchored to the centre rather than parented to a CenterContainer, and that is a motion
	# requirement rather than a style preference: Container.fit_child_in_rect resets its
	# children's scale AND rotation on every layout pass, so a panel inside a CenterContainer
	# cannot be scale-animated at all. The tween runs, the property is overwritten before it
	# is drawn, and the panel just fades without ever growing. Anchors centre it just as well
	# and leave the transform alone.
	var panel: PanelContainer = _always(PanelContainer.new())
	panel.name = "Panel"
	panel.set_anchors_preset(Control.PRESET_CENTER)
	panel.grow_horizontal = Control.GROW_DIRECTION_BOTH
	panel.grow_vertical = Control.GROW_DIRECTION_BOTH
	panel.add_theme_stylebox_override("panel", UiTheme.panel_box())
	root.add_child(panel)
	_panel = panel

	var col: VBoxContainer = _always(VBoxContainer.new())
	col.add_theme_constant_override("separation", 12)
	panel.add_child(col)

	col.add_child(UiTheme.make_label(title_text, UiTheme.FS_TITLE, UiTheme.ACCENT))
	if not subtitle_text.is_empty():
		col.add_child(UiTheme.make_label(subtitle_text, UiTheme.FS_SMALL, UiTheme.TEXT_DIM))

	col.add_child(_gap(18.0))
	if show_sensitivity:
		_sensitivity = _slider(col, "Mouse sensitivity", 0.2, 3.0, 1.0, sensitivity_changed)
	if show_volume:
		_volume = _slider(col, "Volume", 0.0, 1.0, 0.8, volume_changed)
	# Only the leading gap is unconditional. With no sliders between them the two gaps stack
	# into 36px of nothing under the title, which looks like a layout bug rather than a menu
	# with fewer options.
	if show_sensitivity or show_volume:
		col.add_child(_gap(18.0))

	col.add_child(_button(resume_label, resume_requested, true))
	if show_restart:
		col.add_child(_button(restart_label, restart_requested, false))
	col.add_child(_button(menu_label, menu_requested, false))
	if show_quit_to_desktop:
		col.add_child(_button(quit_label, quit_requested, false))

	# The panel grows in as one object; its rows then arrive in sequence just behind it. The
	# small head start on the stagger is what makes it read as "the panel brought them" rather
	# than as two unrelated animations that happen to overlap.
	UiJuice.enter(self, panel, UiJuice.Enter.POP)
	UiJuice.stagger(self, col.get_children(), UiJuice.STAGGER_STEP, UiJuice.IN_TIME * 0.35)


## Play the exit animation, then free. Emit your own signal first — the game should resume
## on the click, not when the animation finishes, or the menu feels laggy rather than juicy.
##
## queue_free() still works and simply skips the animation. That matters more than it looks:
## it keeps this a drop-in replacement for the plain kit, and it means an error path that
## tears the menu down in a hurry cannot deadlock waiting on a tween that will never run.
func dismiss() -> void:
	if _dismissing:
		return
	_dismissing = true
	UiJuice.exit_then(self, _root, queue_free)


## Every node in a pause overlay needs this, so it is one call rather than a line to forget.
func _always(n: Node) -> Variant:
	n.process_mode = Node.PROCESS_MODE_ALWAYS
	return n


func _gap(h: float) -> Control:
	var c: Control = _always(Control.new())
	c.custom_minimum_size = Vector2(0.0, h)
	return c


func _slider(
	parent: VBoxContainer, label: String, lo: float, hi: float, value: float, out: Signal
) -> HSlider:
	var caption: Label = UiTheme.make_label(label, UiTheme.FS_SMALL, UiTheme.TEXT)
	parent.add_child(_always(caption))
	var s: HSlider = _always(HSlider.new())
	s.min_value = lo
	s.max_value = hi
	s.step = 0.01
	s.value = value
	s.custom_minimum_size = Vector2(320.0, 0.0)
	parent.add_child(s)
	s.value_changed.connect(func(v: float) -> void: out.emit(v))
	return s


func _button(text: String, out: Signal, primary: bool) -> Button:
	var b: Button = _always(Button.new())
	b.text = text
	UiTheme.style_button(b, primary)
	b.pressed.connect(func() -> void: out.emit())
	return b
