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

signal resume_requested()
signal restart_requested()
signal quit_requested()
signal sensitivity_changed(value: float)
signal volume_changed(value: float)

@export var title_text: String = "Paused"
@export var subtitle_text: String = ""
@export var show_restart: bool = true

var _sensitivity: HSlider = null
var _volume: HSlider = null
var _root: Control = null


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

	var center: CenterContainer = _always(CenterContainer.new())
	center.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	root.add_child(center)

	var panel: PanelContainer = _always(PanelContainer.new())
	panel.name = "Panel"
	panel.add_theme_stylebox_override("panel", UiTheme.panel_box())
	center.add_child(panel)

	var col: VBoxContainer = _always(VBoxContainer.new())
	col.add_theme_constant_override("separation", 12)
	panel.add_child(col)

	col.add_child(UiTheme.make_label(title_text, UiTheme.FS_TITLE, UiTheme.ACCENT))
	if not subtitle_text.is_empty():
		col.add_child(UiTheme.make_label(subtitle_text, UiTheme.FS_SMALL, UiTheme.TEXT_DIM))

	col.add_child(_gap(18.0))
	_sensitivity = _slider(col, "Mouse sensitivity", 0.2, 3.0, 1.0, sensitivity_changed)
	_volume = _slider(col, "Volume", 0.0, 1.0, 0.8, volume_changed)
	col.add_child(_gap(18.0))

	col.add_child(_button("Resume", resume_requested, true))
	if show_restart:
		col.add_child(_button("Restart", restart_requested, false))
	col.add_child(_button("Quit to menu", quit_requested, false))

	UiMotion.pop_in(panel, 0.9, 0.22)


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
