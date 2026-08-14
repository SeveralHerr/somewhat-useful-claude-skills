class_name TitleScreen
extends Control

## Title screen. Configure it with exports, connect two signals, done.
##
## The one non-obvious choice here is that the title never sits perfectly still — it drifts
## through a degree of rotation on a long loop. A completely static title screen reads as a
## mockup or a frozen build; a very slow motion reads as "this is running". It costs one
## tween and it is the cheapest possible signal of life.

signal play_requested()
signal quit_requested()

@export var title: String = "GAME TITLE"
@export_multiline var taglines: PackedStringArray = PackedStringArray(["A game about something."])
@export var play_label: String = "Play"
@export var controls_hint: String = ""

var _title_label: Label = null


func _ready() -> void:
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_build()
	_animate()
	# Host and root are the same node here: a screen Control scales itself. See UiTheme.fit.
	_fit()
	var vp: Viewport = get_viewport()
	if vp != null and not vp.size_changed.is_connected(_fit):
		vp.size_changed.connect(_fit)


func _fit() -> void:
	UiTheme.fit(self, self)


func _build() -> void:
	add_child(UiTheme.backdrop(Color(0.06, 0.05, 0.07, 1.0)))

	var center: CenterContainer = CenterContainer.new()
	center.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(center)

	var col: VBoxContainer = VBoxContainer.new()
	col.add_theme_constant_override("separation", 14)
	col.alignment = BoxContainer.ALIGNMENT_CENTER
	center.add_child(col)

	_title_label = UiTheme.make_label(title, 96, UiTheme.ACCENT)
	_title_label.name = "Title"
	col.add_child(_title_label)

	if not taglines.is_empty():
		col.add_child(UiTheme.make_label(
			taglines[randi() % taglines.size()], UiTheme.FS_BODY, UiTheme.TEXT
		))

	col.add_child(_gap(34.0))
	col.add_child(_button(play_label, play_requested, true))
	col.add_child(_button("Quit", quit_requested, false))

	if not controls_hint.is_empty():
		col.add_child(_gap(26.0))
		col.add_child(UiTheme.make_label(controls_hint, UiTheme.FS_TINY, UiTheme.TEXT_FAINT))


func _gap(h: float) -> Control:
	var c: Control = Control.new()
	c.custom_minimum_size = Vector2(0.0, h)
	return c


func _button(text: String, out: Signal, primary: bool) -> Button:
	var b: Button = Button.new()
	b.text = text
	UiTheme.style_button(b, primary)
	b.pressed.connect(func() -> void: out.emit())
	return b


func _animate() -> void:
	if _title_label == null:
		return
	UiMotion.pop_in(_title_label, 0.86, 0.6)
	var wobble: Tween = UiMotion.tween(self)
	if wobble == null:
		return
	wobble.set_loops()
	wobble.tween_property(_title_label, "rotation", 0.018, 2.4) \
		.set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
	wobble.tween_property(_title_label, "rotation", -0.018, 2.4) \
		.set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
