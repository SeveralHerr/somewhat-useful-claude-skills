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
var _column: VBoxContainer = null
var _dismissing: bool = false


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
	add_child(UiTheme.backdrop(UiTheme.BACKDROP_OPAQUE))

	var center: CenterContainer = CenterContainer.new()
	center.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(center)

	var col: VBoxContainer = VBoxContainer.new()
	col.add_theme_constant_override("separation", 14)
	col.alignment = BoxContainer.ALIGNMENT_CENTER
	center.add_child(col)
	_column = col

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


## Play the exit animation, then free. See PauseMenu.dismiss for why this is separate from
## queue_free rather than replacing it.
func dismiss() -> void:
	if _dismissing:
		return
	_dismissing = true
	UiJuice.exit_then(self, self, queue_free)


func _animate() -> void:
	if _title_label == null:
		return
	UiMotion.pop_in(_title_label, 0.86, 0.6)
	# The title lands first and the rest of the column assembles under it. Everything below
	# the title is a child of a container, which is why the stagger animates scale and alpha
	# rather than position — see UiJuice.stagger.
	# Note the title itself is NOT staggered and not breathed: pop_in already owns its scale,
	# and a second tween writing the same property is a stutter, not extra juice. One property,
	# one animation — the rotation wobble below is on a different property, which is why it can
	# coexist.
	if _column != null:
		UiJuice.stagger(self, _column.get_children().slice(1), UiJuice.STAGGER_STEP, 0.12)
	var wobble: Tween = UiMotion.tween(self)
	if wobble == null:
		return
	wobble.set_loops()
	wobble.tween_property(_title_label, "rotation", 0.018, 2.4) \
		.set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
	wobble.tween_property(_title_label, "rotation", -0.018, 2.4) \
		.set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
