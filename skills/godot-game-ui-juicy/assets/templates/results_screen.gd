class_name ResultsScreen
extends Control

## End-of-run summary: a row of headline stats, an optional collection grid, two buttons.
##
## The collection grid is the part worth keeping even in games that seem not to need one.
## Showing every item in the catalogue with the un-found ones present but blanked is what
## turns a finite level into a reason to play again — the gaps are the hook, so they have to
## be visible rather than omitted. A grid of only what you found says "you are done".
##
## `present()` is separate from `_ready()` because a results screen is usually instantiated
## and handed its data in the same frame, which can happen before it enters the tree.

signal again_requested()
signal menu_requested()

const COLUMNS: int = 15

@export var heading: String = "Run Complete"

var _stats: Dictionary = {}
var _entries: Array[Dictionary] = []
var _verdict: String = ""
var _built: bool = false
var _chips: Array[Control] = []
var _dismissing: bool = false


func _ready() -> void:
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	if not _built:
		_build()
	# Host and root are the same node here: a screen Control scales itself. See UiTheme.fit.
	_fit()
	var vp: Viewport = get_viewport()
	if vp != null and not vp.size_changed.is_connected(_fit):
		vp.size_changed.connect(_fit)


func _fit() -> void:
	UiTheme.fit(self, self)


## `stats` is an ordered list of {"label": String, "value": String} shown as the headline row.
## `entries` is the optional collection grid: {"name", "found": bool, "color": Color,
## "tint": Color (border), "tooltip": String}.
func present(stats: Array, entries: Array = [], verdict: String = "") -> void:
	_stats = {"rows": stats}
	_entries.clear()
	for e: Variant in entries:
		_entries.append(e as Dictionary)
	_verdict = verdict
	if is_inside_tree():
		_rebuild()


func _rebuild() -> void:
	for c: Node in get_children():
		remove_child(c)
		c.queue_free()
	_build()


func _build() -> void:
	_built = true
	# Cleared here as well as in _collection(): a rebuild with no entries would otherwise
	# leave freed chips in the list for the next stagger to walk over.
	_chips.clear()
	add_child(UiTheme.backdrop(Color(0.06, 0.05, 0.07, 1.0)))

	var margin: MarginContainer = MarginContainer.new()
	margin.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	for side: String in ["left", "right"]:
		margin.add_theme_constant_override("margin_" + side, 60)
	for side: String in ["top", "bottom"]:
		margin.add_theme_constant_override("margin_" + side, 40)
	add_child(margin)

	var col: VBoxContainer = VBoxContainer.new()
	col.add_theme_constant_override("separation", 10)
	# Centred vertically, which is a no-op when the collection grid is present (it expands and
	# takes the slack) and the whole fix when it is not: heading, verdict, one stat row and two
	# buttons otherwise stack in the top third above a screen-height of empty backdrop, which
	# reads as a screen that failed to finish loading.
	col.alignment = BoxContainer.ALIGNMENT_CENTER
	margin.add_child(col)

	col.add_child(UiTheme.make_label(heading, 62, UiTheme.ACCENT))
	if not _verdict.is_empty():
		col.add_child(UiTheme.make_label(_verdict, UiTheme.FS_BODY, UiTheme.TEXT))

	col.add_child(_stat_row())
	if not _entries.is_empty():
		col.add_child(_collection())

	var buttons: HBoxContainer = HBoxContainer.new()
	buttons.alignment = BoxContainer.ALIGNMENT_CENTER
	buttons.add_theme_constant_override("separation", 16)
	col.add_child(buttons)
	buttons.add_child(_button("Play again", again_requested, true))
	buttons.add_child(_button("Main menu", menu_requested, false))

	# Sections arrive top to bottom, and the collection chips ripple in behind them. The grid
	# is the reason a results screen is worth animating at all: a wave across the chips makes
	# the player's eye travel the whole collection, including the gaps, which is exactly the
	# thing the screen exists to show them. A grid that simply appears gets skimmed.
	UiJuice.stagger(self, col.get_children(), UiJuice.STAGGER_STEP * 2.0)
	if not _chips.is_empty():
		UiJuice.stagger(self, _chips, UiJuice.STAGGER_STEP * 0.5, UiJuice.IN_TIME)


## Play the exit animation, then free. See PauseMenu.dismiss for why this is separate from
## queue_free rather than replacing it.
func dismiss() -> void:
	if _dismissing:
		return
	_dismissing = true
	UiJuice.exit_then(self, self, queue_free)


func _stat_row() -> Control:
	var panel: PanelContainer = PanelContainer.new()
	panel.add_theme_stylebox_override("panel", UiTheme.panel_box(14))
	var row: HBoxContainer = HBoxContainer.new()
	row.alignment = BoxContainer.ALIGNMENT_CENTER
	row.add_theme_constant_override("separation", 46)
	panel.add_child(row)
	for entry: Variant in (_stats.get("rows", []) as Array):
		var d: Dictionary = entry as Dictionary
		var v: VBoxContainer = VBoxContainer.new()
		v.alignment = BoxContainer.ALIGNMENT_CENTER
		v.add_child(UiTheme.make_label(
			str(d.get("label", "")), UiTheme.FS_TINY, UiTheme.TEXT_FAINT
		))
		v.add_child(UiTheme.make_label(
			str(d.get("value", "")), UiTheme.FS_HEADING, UiTheme.TEXT
		))
		row.add_child(v)
	return panel


func _collection() -> Control:
	var panel: PanelContainer = PanelContainer.new()
	panel.add_theme_stylebox_override("panel", UiTheme.panel_box(14))
	panel.size_flags_vertical = Control.SIZE_EXPAND_FILL

	var v: VBoxContainer = VBoxContainer.new()
	v.add_theme_constant_override("separation", 10)
	panel.add_child(v)

	var found: int = 0
	for e: Dictionary in _entries:
		if bool(e.get("found", false)):
			found += 1
	var header: Label = UiTheme.make_label(
		"Collection   %d / %d" % [found, _entries.size()], UiTheme.FS_SMALL, UiTheme.ACCENT, false
	)
	v.add_child(header)

	var scroll: ScrollContainer = ScrollContainer.new()
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	v.add_child(scroll)

	var grid: GridContainer = GridContainer.new()
	grid.columns = COLUMNS
	grid.add_theme_constant_override("h_separation", 8)
	grid.add_theme_constant_override("v_separation", 8)
	grid.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroll.add_child(grid)

	_chips.clear()
	for e: Dictionary in _entries:
		var c: Control = _chip(e)
		grid.add_child(c)
		_chips.append(c)
	return panel


## An un-found chip keeps its cell as a dim disc rather than disappearing, because the empty
## slots are the whole point of showing a collection at all.
func _chip(e: Dictionary) -> Control:
	var found: bool = bool(e.get("found", false))
	var fill: Color = e.get("color", UiTheme.TEXT) as Color
	var chip: PanelContainer = PanelContainer.new()
	chip.custom_minimum_size = Vector2(64.0, 64.0)
	chip.tooltip_text = str(e.get("tooltip", "")) if found else "???"

	var box: StyleBoxFlat = StyleBoxFlat.new()
	box.set_corner_radius_all(32)
	if found:
		box.bg_color = fill
		box.set_border_width_all(3)
		box.border_color = e.get("tint", UiTheme.ACCENT) as Color
	else:
		box.bg_color = Color(0.16, 0.15, 0.17)
		box.set_border_width_all(1)
		box.border_color = UiTheme.PANEL_BORDER
	chip.add_theme_stylebox_override("panel", box)

	var l: Label = Label.new()
	l.text = str(e.get("name", "")) if found else "?"
	# Ink is chosen against the chip's own fill, otherwise half the collection is unreadable
	# the moment the palette includes pale items.
	var ink: Color = Color(0, 0, 0, 0.82) if (found and fill.v > 0.5) else Color(1, 1, 1, 0.85)
	UiTheme.style_label(l, 11 if found else 20, ink, false)
	l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	l.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	l.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	chip.add_child(l)
	return chip


func _button(text: String, out: Signal, primary: bool) -> Button:
	var b: Button = Button.new()
	b.text = text
	UiTheme.style_button(b, primary, 220.0)
	b.pressed.connect(func() -> void: out.emit())
	return b
