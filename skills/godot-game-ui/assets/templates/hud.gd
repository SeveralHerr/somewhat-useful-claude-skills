class_name GameHud
extends CanvasLayer

## A game HUD with the regions almost every action/collection game needs, built entirely in
## code so it drops into any project without a .tscn, a uid, or an import step.
##
## The whole thing is game-agnostic on purpose. It knows about *shapes* of information —
## a stack of counters, a contextual prompt, a reward announcement, a carried-item readout —
## and nothing about what those counters mean. Wire it to your game by calling the methods
## below from wherever your state changes; the HUD never reaches into your game to pull.
##
## LAYOUT (matches the convention players already know from tidying/collection games):
##   top-left      stat pill stack + progress bar + hint breadcrumb
##   top-right     toast (transient, corner-sized)
##   centre        crosshair, and a contextual prompt just below it
##   centre-upper  reward card (transient, queued)
##   centre        shout (transient, escalating)
##   bottom-centre held-item strip
##   bottom-right  big counter, e.g. carried/capacity
##   bottom-left   numbered tool/ability slots
##
## CLICK-THROUGH. Nothing in this HUD is clickable, and every Control in it is therefore
## forced to MOUSE_FILTER_IGNORE after the build (see _make_click_through). This is not
## tidiness: Panel and PanelContainer default to MOUSE_FILTER_STOP, and in a captured-cursor
## first-person game every mouse motion event carries the viewport centre — which is exactly
## where the crosshair sits. GUI picking consumes it and marks it handled, _unhandled_input
## never runs, and the player can walk and interact but cannot turn their head. The camera
## code looks correct because it is; this file was the bug.
##
## HEADLESS SAFETY. Everything animated goes through UiMotion, which snaps to the final
## value when it cannot tween. A headless test that pumps no frames therefore still ends up
## with correct text — the HUD is assertable. Position comes from anchors, which resolve
## identically on screen and under a test harness's offscreen viewport.
##
## RESOLUTION. The one thing that does read the viewport is _fit(), which scales the layer by
## viewport height / UiTheme.REFERENCE_HEIGHT so the HUD is the same size relative to the
## screen at 720p and at 4K. It is null-safe: with no viewport it changes nothing and the
## layout stays plainly anchored, so building a HUD outside the tree still works.

## How long a reward card holds at full size before it starts to leave.
const CARD_HOLD: float = 2.2
const CARD_Y: float = -300.0
const SHOUT_Y: float = -170.0
## How long a toast stays before it leaves on its own.
const TOAST_HOLD: float = 2.4

## Crosshair states. BLOCKED is the one people leave out and then need: a first-person game
## that lets you place, stack or hand over objects has to say "not there" as clearly as it
## says "here", and doing it by simply not turning the crosshair hot is indistinguishable
## from pointing at nothing.
enum Cross { NEUTRAL, HOT, BLOCKED }

var _root: Control = null
var _stat_stack: VBoxContainer = null
var _progress_fill: Control = null
var _hint: Label = null
var _crosshair: Control = null
var _cross_ring: Panel = null
var _prompt_box: PanelContainer = null
var _prompt_prefix: Label = null
var _key_chip: PanelContainer = null
var _key_label: Label = null
var _prompt_label: Label = null
var _held_box: PanelContainer = null
var _held_label: Label = null
var _counter: Label = null
var _counter_shell: Control = null
var _toolbar: HBoxContainer = null
var _shout: Label = null
var _toast_box: PanelContainer = null
var _toast_label: Label = null
var _card: PanelContainer = null
var _card_kicker: Label = null
var _card_title: Label = null
var _card_subtitle: Label = null
var _card_body: Label = null

## id -> {"row": PanelContainer, "value": Label, "icon": Glyph, "shown": float}
var _stats: Dictionary = {}
var _tool_slots: Array[PanelContainer] = []
var _card_queue: Array[Dictionary] = []
var _card_busy: bool = false
var _shown_counter: float = 0.0
var _cross_state: Cross = Cross.NEUTRAL
var _tweens: Dictionary = {}
var _ui_scale: float = 1.0


var _built: bool = false


func _ready() -> void:
	layer = 5
	_ensure_built()
	_fit()
	var vp: Viewport = get_viewport()
	if vp != null and not vp.size_changed.is_connected(_fit):
		vp.size_changed.connect(_fit)


## Re-fit the whole layer to the current viewport. Cheap, and idempotent — safe to call as
## often as the window changes size.
func _fit() -> void:
	_ui_scale = UiTheme.fit(self, _root)


## Builds on first use rather than only in _ready().
##
## Configuring a HUD in the same frame you create it is the normal way to use one, and
## _ready() has not fired at that point — the node is in the tree but the engine has not
## reached it yet. Without this guard every setter silently no-ops and the HUD comes up
## blank, which looks like a wiring mistake in the game rather than a lifecycle one here.
func _ensure_built() -> void:
	if _built:
		return
	_built = true
	layer = 5
	_build()


# ------------------------------------------------------------------------------- public

## Register a counter in the top-left stack. Call once per stat during setup.
##
## Stats are added rather than declared as a fixed list because the set differs per game and
## sometimes per level — an id keyed dictionary means the wiring code names what it means
## ("coins", "keys") instead of indexing into row 3.
func add_stat(id: StringName, glyph: UiTheme.Glyph.Kind, initial: String = "0") -> void:
	_ensure_built()
	if _stat_stack == null or _stats.has(id):
		return
	var row: PanelContainer = PanelContainer.new()
	row.name = "Stat_%s" % id
	row.add_theme_stylebox_override("panel", UiTheme.pill_box())
	row.mouse_filter = Control.MOUSE_FILTER_IGNORE

	var line: HBoxContainer = HBoxContainer.new()
	line.add_theme_constant_override("separation", 10)
	row.add_child(line)

	var icon: UiTheme.Glyph = UiTheme.Glyph.new(glyph, UiTheme.TEXT, UiTheme.ICON_SIZE)
	line.add_child(icon)

	var value: Label = UiTheme.make_label(initial, UiTheme.FS_BODY, UiTheme.TEXT, false)
	value.custom_minimum_size = Vector2(110.0, 0.0)
	line.add_child(value)

	# Shelled, not added directly. _stat_stack is a VBoxContainer, and a Container rewrites its
	# children's scale on every layout pass — so a row added straight to it can never be
	# scaled, and a punch on it would be dead code that nobody notices because the tint still
	# lands. The shell is what the VBox lays out; the row inside it moves freely.
	var shell: Control = UiMotion.transform_shell(row)
	_stat_stack.add_child(shell)
	_make_click_through(shell)
	_stats[id] = {"row": row, "value": value, "icon": icon, "shown": 0.0}


## Roll a stat to a new value. Pass a formatter for "12/40", "$1,280", "x7" and so on.
##
## The roll starts from the value currently DISPLAYED, not from the model's previous value,
## so two changes landing inside one animation continue the count rather than snapping back.
func set_stat(id: StringName, value: float, formatter: Callable = Callable()) -> void:
	_ensure_built()
	var entry: Dictionary = _stats.get(id, {}) as Dictionary
	if entry.is_empty():
		return
	var label: Label = entry["value"] as Label
	var from: float = entry["shown"] as float
	entry["shown"] = value
	UiMotion.replace(_tweens, label, UiMotion.count_to(self, label, from, value, formatter))


## Set a stat's text directly, for values that are not numbers.
func set_stat_text(id: StringName, text: String) -> void:
	_ensure_built()
	var entry: Dictionary = _stats.get(id, {}) as Dictionary
	if entry.is_empty():
		return
	(entry["value"] as Label).text = text


## Acknowledge something happening to a stat — green for earned, red for lost or refused.
func flash_stat(id: StringName, color: Color) -> void:
	_ensure_built()
	var entry: Dictionary = _stats.get(id, {}) as Dictionary
	if entry.is_empty():
		return
	UiMotion.flash(entry["row"] as Control, color)


func set_stat_icon_color(id: StringName, color: Color) -> void:
	_ensure_built()
	var entry: Dictionary = _stats.get(id, {}) as Dictionary
	if not entry.is_empty():
		(entry["icon"] as UiTheme.Glyph).set_color(color)


## Contextual prompt under the crosshair. "" hides it.
##
## Two shapes, chosen from the text itself so callers never have to think about the keycap:
##   "Press [E] to open"   -> Press [E] to open   (an action you can take)
##   "It's locked"         ->     It's locked     (a status you cannot act on)
## The distinction matters more than it looks. A keycap in front of a refusal tells the
## player to press the key that just failed, which is actively misleading feedback.
func set_prompt(text: String) -> void:
	_ensure_built()
	if _prompt_box == null:
		return
	if text.strip_edges().is_empty():
		_prompt_box.visible = false
		return
	_prompt_box.visible = true
	var key: String = ""
	var body: String = text
	var open: int = text.find("[")
	var close: int = text.find("]")
	if open >= 0 and close > open + 1:
		key = text.substr(open + 1, close - open - 1)
		body = text.substr(close + 1).strip_edges()
		_prompt_prefix.text = text.substr(0, open).strip_edges()
	_key_chip.visible = not key.is_empty()
	_prompt_prefix.visible = not key.is_empty() and not _prompt_prefix.text.is_empty()
	_key_label.text = key
	_prompt_label.text = body
	_prompt_label.add_theme_color_override(
		"font_color", UiTheme.TEXT if not key.is_empty() else UiTheme.TEXT_DIM
	)


## Bottom-centre strip naming what the player is currently holding. "" hides it.
func set_held(text: String, color: Color = UiTheme.TEXT) -> void:
	_ensure_built()
	if _held_box == null:
		return
	if text.strip_edges().is_empty():
		_held_box.visible = false
		return
	_held_box.visible = true
	_held_label.text = text
	# Tints get brightened rather than used raw: an item's own colour is chosen to look good
	# in the world, and dark ones are unreadable as type over a dark pill.
	_held_label.add_theme_color_override("font_color", color.lightened(0.35) if color.v < 0.6 else color)


## Big bottom-right readout, e.g. carried/capacity. Turns accent-coloured at capacity so
## "you cannot pick anything else up" is visible without reading the number.
func set_counter(current: int, capacity: int) -> void:
	_ensure_built()
	if _counter == null:
		return
	var full: bool = capacity > 0 and current >= capacity
	_counter.add_theme_color_override("font_color", UiTheme.ACCENT if full else UiTheme.TEXT)
	var cap: int = capacity
	UiMotion.replace(_tweens, _counter, UiMotion.count_to(
		self, _counter, _shown_counter, float(current),
		func(v: float) -> String: return "%d/%d" % [int(round(v)), cap]
	))
	_shown_counter = float(current)


func set_hint(text: String) -> void:
	_ensure_built()
	if _hint == null:
		return
	_hint.text = ("▸  " + text) if not text.strip_edges().is_empty() else ""
	_hint.visible = not text.strip_edges().is_empty()


func set_progress(ratio: float) -> void:
	_ensure_built()
	UiMotion.progress_to(self, _progress_fill, ratio)


## Grow and gold the crosshair over anything interactable. Cheap to call every frame — it
## early-outs when the state has not changed.
func set_crosshair_hot(hot: bool) -> void:
	set_crosshair_state(Cross.HOT if hot else Cross.NEUTRAL)


## The three-state version. BLOCKED shrinks and reddens instead of growing and goldening, so
## "you cannot put it there" is a different shape as well as a different colour — the two
## states have to be distinguishable in peripheral vision, which is where the crosshair
## actually lives while the player is aiming at something else.
func set_crosshair_state(state: Cross) -> void:
	_ensure_built()
	if _crosshair == null or state == _cross_state:
		return
	_cross_state = state
	var tint: Color = UiTheme.with_alpha(UiTheme.TEXT, 0.72)
	var target: Vector2 = Vector2.ONE
	match state:
		Cross.HOT:
			tint = UiTheme.ACCENT
			target = Vector2(1.35, 1.35)
		Cross.BLOCKED:
			tint = UiTheme.BAD
			target = Vector2(0.78, 0.78)
		_:
			pass
	_cross_ring.add_theme_stylebox_override(
		"panel", UiTheme.circle_box(Color(0, 0, 0, 0), tint, 2))
	var t: Tween = UiMotion.tween(self)
	if t == null:
		_crosshair.scale = target
		return
	_crosshair.pivot_offset = _crosshair.size * 0.5
	t.set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	t.tween_property(_crosshair, "scale", target, 0.16)


## Transient centre shout — combos, streaks, warnings. `emphasis` (0..1) scales the type and
## the overshoot, so a big moment cannot be mistaken for a small one.
func shout(text: String, color: Color = UiTheme.ACCENT, emphasis: float = 0.5) -> void:
	_ensure_built()
	if _shout == null or text.strip_edges().is_empty():
		return
	var e: float = clampf(emphasis, 0.0, 1.0)
	_shout.text = text
	UiTheme.style_label(_shout, int(UiTheme.FS_SHOUT * (0.72 + e * 0.5)), color)
	_shout.rotation = randf_range(-0.05, 0.05) * e
	UiMotion.pop_in(_shout, 0.55 - e * 0.2, 0.26)
	var t: Tween = UiMotion.tween(self)
	if t == null:
		_shout.visible = false
		return
	t.tween_interval(0.45 + e * 0.35)
	t.tween_callback(func() -> void: UiMotion.fade_out(_shout, 0.3, 40.0))


## Quiet corner announcement: "Kitchen complete", "Autosaved", "New tool unlocked".
##
## The middle rung between a prompt and a shout, and the one most kits leave out. A shout
## takes the centre of the screen and interrupts what the player is looking at, which is right
## for a combo and wrong for a milestone they should notice without being stopped. A toast
## replaces whatever is already showing rather than queueing — by the time a second milestone
## lands, the first is no longer news.
func toast(text: String, color: Color = UiTheme.ACCENT) -> void:
	_ensure_built()
	if _toast_box == null or text.strip_edges().is_empty():
		return
	_toast_label.text = text
	_toast_label.add_theme_color_override("font_color", color)
	# Scale and alpha only, never position. The toast is anchored to a corner and re-shown many
	# times per session; an entrance that moved it would have to restore the resting place
	# exactly, and a rounding error there walks the toast across the screen over a long game.
	UiMotion.replace(_tweens, _toast_box, null)
	UiMotion.pop_in(_toast_box, 0.88, 0.26)
	var t: Tween = UiMotion.tween(self)
	if t == null:
		# No frames will pass, so the toast stays up. A test asserting on toast_text() then
		# reads what the player would have seen, rather than an empty string it cannot explain.
		_toast_box.visible = true
		return
	t.tween_interval(TOAST_HOLD)
	t.tween_callback(func() -> void: UiMotion.fade_out(_toast_box, 0.3))
	UiMotion.replace(_tweens, _toast_box, t)


## Announce a reward. This is the payoff moment of a collection game, so it gets a real
## card rather than a line of text: kicker, big name, tinted subtitle, flavour body.
##
## Cards QUEUE. Two rewards landing inside a second is exactly when the player most wants to
## read both, and a card that cuts off its predecessor shows neither.
func show_card(
	kicker: String, title: String, subtitle: String = "", body: String = "",
	accent: Color = UiTheme.ACCENT
) -> void:
	_ensure_built()
	_card_queue.append({
		"kicker": kicker, "title": title, "subtitle": subtitle,
		"body": body, "accent": accent,
	})
	if not _card_busy:
		_drain_cards()


## Build N numbered tool/ability slots in the bottom-left corner.
func build_tools(icons: Array[UiTheme.Glyph.Kind]) -> void:
	_ensure_built()
	if _toolbar == null:
		return
	for c: Node in _toolbar.get_children():
		c.queue_free()
	_tool_slots.clear()
	for i: int in range(icons.size()):
		var slot: PanelContainer = PanelContainer.new()
		slot.name = "Slot%d" % (i + 1)
		slot.custom_minimum_size = Vector2(UiTheme.SLOT_SIZE, UiTheme.SLOT_SIZE)
		slot.add_theme_stylebox_override("panel", UiTheme.slot_box(i == 0))
		slot.add_child(UiTheme.Glyph.new(icons[i], UiTheme.TEXT_DIM, UiTheme.ICON_SIZE + 4.0))

		var badge: PanelContainer = PanelContainer.new()
		badge.add_theme_stylebox_override("panel", UiTheme.badge_box(i == 0))
		var num: Label = UiTheme.make_label(str(i + 1), UiTheme.FS_TINY, UiTheme.TEXT, true)
		badge.add_child(num)

		var column: VBoxContainer = VBoxContainer.new()
		column.add_theme_constant_override("separation", 4)
		column.alignment = BoxContainer.ALIGNMENT_CENTER
		# Shelled for the same reason as a stat row: a slot parented straight to this VBox
		# cannot be scaled, so any acknowledgement of selecting it has to be colour alone.
		column.add_child(UiMotion.transform_shell(slot))
		column.add_child(badge)
		_toolbar.add_child(column)
		_make_click_through(column)
		_tool_slots.append(slot)


func set_active_tool(index: int) -> void:
	_ensure_built()
	for i: int in range(_tool_slots.size()):
		_tool_slots[i].add_theme_stylebox_override("panel", UiTheme.slot_box(i == index))


# ------------------------------------------------------------------------------ read-back

## Everything the HUD is currently showing, as strings.
##
## These exist so a test can assert `hud.prompt_text() == "to open"` instead of
## `hud.find_child("PromptLabel", true, false).text`. The find_child version couples every
## test to this file's private build order — rename a node here and a dozen assertions
## elsewhere fail with a null dereference rather than a message. A write-only UI is a UI that
## can only be checked by screenshot, which is exactly the kind of check that stops running.

## What the stat currently reads, or "" for an unknown id.
func stat_text(id: StringName) -> String:
	_ensure_built()
	var entry: Dictionary = _stats.get(id, {}) as Dictionary
	return "" if entry.is_empty() else (entry["value"] as Label).text


## The BODY of the prompt, without the keycap — "to open" for "Press [E] to open". "" when the
## prompt is hidden, so this doubles as the visibility check.
func prompt_text() -> String:
	_ensure_built()
	if _prompt_box == null or not _prompt_box.visible:
		return ""
	return _prompt_label.text


## The key inside the prompt's chip ("E"), or "" when the prompt is a status rather than an
## action. Distinguishing those two is the whole point of set_prompt's parsing.
func prompt_key() -> String:
	_ensure_built()
	if _key_chip == null or not _key_chip.visible or not _prompt_box.visible:
		return ""
	return _key_label.text


func held_text() -> String:
	_ensure_built()
	return "" if _held_box == null or not _held_box.visible else _held_label.text


func hint_text() -> String:
	_ensure_built()
	return "" if _hint == null or not _hint.visible else _hint.text


## The counter as displayed, mid-roll included — "3/8". Assert against this only with motion
## disabled or after the roll has finished; that is a property of counting up, not a flaw.
func counter_text() -> String:
	_ensure_built()
	return "" if _counter == null else _counter.text


## The title on the reward card currently showing, or "" when none is.
func card_title() -> String:
	_ensure_built()
	return "" if _card == null or not _card.visible else _card_title.text


func toast_text() -> String:
	_ensure_built()
	return "" if _toast_box == null or not _toast_box.visible else _toast_label.text


func crosshair_state() -> Cross:
	_ensure_built()
	return _cross_state


## A CanvasLayer has no rect of its own, so `hud.size` does not exist. Anything asserting
## that the HUD filled the viewport has to ask the Control that actually owns the rectangle.
## Returns ZERO when the skeleton is missing, which is itself the assertion you want to fail.
##
## This is SCREEN space, deliberately. The root's own size is viewport/ui_scale, and a test
## that wants to know "did the HUD cover the viewport" means the on-screen rectangle, not the
## pre-scale one. Use layout_scale() when you specifically want the factor.
func layout_size() -> Vector2:
	_ensure_built()
	return (_root.size * _ui_scale) if _root != null else Vector2.ZERO


## The factor the whole layer is scaled by: viewport height / UiTheme.REFERENCE_HEIGHT,
## clamped. 1.0 before the HUD has a viewport to measure.
func layout_scale() -> float:
	return _ui_scale


# -------------------------------------------------------------------------------- cards

func _drain_cards() -> void:
	if _card_queue.is_empty():
		_card_busy = false
		return
	if _card == null:
		_card_queue.clear()
		_card_busy = false
		return
	_card_busy = true
	var d: Dictionary = _card_queue.pop_front()
	var accent: Color = d["accent"] as Color

	_card.add_theme_stylebox_override("panel", UiTheme.card_box(accent))
	_card_kicker.text = (d["kicker"] as String).to_upper()
	_card_title.text = d["title"] as String
	_card_subtitle.text = d["subtitle"] as String
	_card_subtitle.add_theme_color_override("font_color", accent)
	_card_subtitle.visible = not _card_subtitle.text.is_empty()
	_card_body.text = d["body"] as String
	_card_body.visible = not _card_body.text.is_empty()

	_card.position.y = CARD_Y + 24.0
	UiMotion.pop_in(_card, 0.72, 0.34)
	var t: Tween = UiMotion.tween(self)
	if t == null:
		# No frames will ever pass, so there is no way to *sequence* the queue. Showing the
		# first card and dropping the rest is the honest degradation; draining recursively
		# would leave only the LAST card's text on screen, which is the one nobody asked
		# about and the one a test would then assert against.
		# _card_busy deliberately STAYS true: the slot is occupied and nothing will ever
		# free it, so later cards queue and are never shown. That keeps the FIRST card on
		# screen, which is the one a test asserts against and the one the player would
		# actually have seen first.
		_card.visible = true
		return
	t.tween_property(_card, "position:y", CARD_Y, 0.34) \
		.set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	t.tween_interval(CARD_HOLD)
	t.tween_callback(func() -> void: UiMotion.fade_out(_card, 0.3, 30.0))
	t.tween_interval(0.32)
	t.tween_callback(_drain_cards)


# -------------------------------------------------------------------------------- build

func _build() -> void:
	_root = Control.new()
	_root.name = "Root"
	_root.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(_root)

	_build_top_left()
	_build_top_right()
	_build_centre()
	_build_bottom()
	_make_click_through(_root)


## Force every Control under `n` to MOUSE_FILTER_IGNORE.
##
## Done as a sweep rather than a line per node because the defect it prevents is a class, not
## an instance: Panel, PanelContainer and Button default to STOP, so every future addition to
## this file is one forgotten line away from eating the mouse. In a captured-cursor game the
## symptom is that the player cannot look around, and the cost of finding that is an hour with
## a camera controller that turns out to be correct.
##
## If you add something the player must actually click — a HUD-embedded button — give it
## MOUSE_FILTER_STOP after this runs, and be deliberate about it.
func _make_click_through(n: Node) -> void:
	var c: Control = n as Control
	if c != null:
		c.mouse_filter = Control.MOUSE_FILTER_IGNORE
	for child: Node in n.get_children():
		_make_click_through(child)


func _build_top_left() -> void:
	var col: VBoxContainer = VBoxContainer.new()
	col.name = "TopLeft"
	col.position = Vector2(UiTheme.MARGIN, UiTheme.MARGIN)
	col.add_theme_constant_override("separation", 8)
	col.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_root.add_child(col)

	_stat_stack = VBoxContainer.new()
	_stat_stack.name = "StatStack"
	_stat_stack.add_theme_constant_override("separation", 6)
	# Shrink, or the pills inherit the column's width — and a VBox is as wide as its widest
	# child, which is the hint. Without this a long hint silently stretches every stat pill.
	_stat_stack.size_flags_horizontal = Control.SIZE_SHRINK_BEGIN
	col.add_child(_stat_stack)

	var track: Panel = Panel.new()
	track.name = "ProgressTrack"
	track.custom_minimum_size = Vector2(250.0, 6.0)
	track.add_theme_stylebox_override("panel", UiTheme.bar_box(UiTheme.with_alpha(UiTheme.TEXT, 0.14)))
	col.add_child(track)

	_progress_fill = Panel.new()
	_progress_fill.name = "ProgressFill"
	_progress_fill.set_anchors_preset(Control.PRESET_LEFT_WIDE)
	_progress_fill.anchor_right = 0.0
	_progress_fill.add_theme_stylebox_override("panel", UiTheme.bar_box(UiTheme.ACCENT))
	track.add_child(_progress_fill)

	_hint = UiTheme.make_label("", UiTheme.FS_SMALL, UiTheme.TEXT_DIM, false)
	_hint.name = "HintLabel"
	_hint.visible = false
	col.add_child(_hint)


## The toast lives opposite the stat stack, on the diagonal from it: the top-right corner is
## the one place a transient line can appear without covering the crosshair, the prompt, the
## held item or the counter, all of which the player may be reading at the time.
func _build_top_right() -> void:
	_toast_box = PanelContainer.new()
	_toast_box.name = "ToastBox"
	_toast_box.set_anchors_and_offsets_preset(
		Control.PRESET_TOP_RIGHT, Control.PRESET_MODE_MINSIZE, int(UiTheme.MARGIN))
	# Grows leftward as the text gets longer, so the right edge stays put against the margin.
	_toast_box.grow_horizontal = Control.GROW_DIRECTION_BEGIN
	_toast_box.add_theme_stylebox_override("panel", UiTheme.pill_box())
	_toast_box.visible = false
	_root.add_child(_toast_box)

	_toast_label = UiTheme.make_label("", UiTheme.FS_BODY, UiTheme.ACCENT, false)
	_toast_label.name = "ToastLabel"
	_toast_box.add_child(_toast_label)


func _build_centre() -> void:
	_crosshair = Control.new()
	_crosshair.name = "Crosshair"
	_crosshair.set_anchors_preset(Control.PRESET_CENTER)
	_crosshair.custom_minimum_size = Vector2(26.0, 26.0)
	_crosshair.size = Vector2(26.0, 26.0)
	_crosshair.position = Vector2(-13.0, -13.0)
	_crosshair.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_root.add_child(_crosshair)

	_cross_ring = Panel.new()
	_cross_ring.name = "Ring"
	_cross_ring.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_cross_ring.add_theme_stylebox_override("panel", UiTheme.circle_box(
		Color(0, 0, 0, 0), UiTheme.with_alpha(UiTheme.TEXT, 0.72), 2
	))
	_crosshair.add_child(_cross_ring)

	var dot: Panel = Panel.new()
	dot.name = "Dot"
	dot.set_anchors_preset(Control.PRESET_CENTER)
	dot.size = Vector2(4.0, 4.0)
	dot.position = Vector2(-2.0, -2.0)
	dot.add_theme_stylebox_override("panel", UiTheme.circle_box(UiTheme.with_alpha(UiTheme.TEXT, 0.8)))
	_crosshair.add_child(dot)

	_prompt_box = PanelContainer.new()
	_prompt_box.name = "PromptBox"
	_prompt_box.set_anchors_preset(Control.PRESET_CENTER)
	_prompt_box.position = Vector2(0.0, 54.0)
	_prompt_box.grow_horizontal = Control.GROW_DIRECTION_BOTH
	_prompt_box.add_theme_stylebox_override("panel", UiTheme.pill_box())
	_prompt_box.visible = false
	_prompt_box.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_root.add_child(_prompt_box)

	var row: HBoxContainer = HBoxContainer.new()
	row.add_theme_constant_override("separation", 10)
	row.alignment = BoxContainer.ALIGNMENT_CENTER
	_prompt_box.add_child(row)

	_prompt_prefix = UiTheme.make_label("Press", UiTheme.FS_BODY, UiTheme.TEXT_DIM, false)
	row.add_child(_prompt_prefix)

	_key_chip = PanelContainer.new()
	_key_chip.name = "KeyChip"
	_key_chip.add_theme_stylebox_override("panel", UiTheme.key_chip_box())
	row.add_child(_key_chip)

	_key_label = UiTheme.make_label("E", UiTheme.FS_SMALL, Color(0.08, 0.07, 0.06), true)
	UiTheme.style_label(_key_label, UiTheme.FS_SMALL, Color(0.08, 0.07, 0.06), false)
	_key_chip.add_child(_key_label)

	_prompt_label = UiTheme.make_label("", UiTheme.FS_BODY, UiTheme.TEXT, false)
	_prompt_label.name = "PromptLabel"
	row.add_child(_prompt_label)

	_shout = UiTheme.make_label("", UiTheme.FS_SHOUT, UiTheme.ACCENT, true)
	_shout.name = "ComboShout"
	_shout.set_anchors_preset(Control.PRESET_CENTER)
	_shout.grow_horizontal = Control.GROW_DIRECTION_BOTH
	_shout.position = Vector2(0.0, SHOUT_Y)
	_shout.visible = false
	_root.add_child(_shout)

	_build_card()


func _build_card() -> void:
	_card = PanelContainer.new()
	_card.name = "RewardCard"
	_card.set_anchors_preset(Control.PRESET_CENTER)
	_card.grow_horizontal = Control.GROW_DIRECTION_BOTH
	_card.grow_vertical = Control.GROW_DIRECTION_BOTH
	_card.position = Vector2(0.0, CARD_Y)
	_card.custom_minimum_size = Vector2(560.0, 0.0)
	_card.add_theme_stylebox_override("panel", UiTheme.card_box())
	_card.visible = false
	_card.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_root.add_child(_card)

	var margin: MarginContainer = MarginContainer.new()
	for side: String in ["left", "right"]:
		margin.add_theme_constant_override("margin_" + side, 34)
	for side: String in ["top", "bottom"]:
		margin.add_theme_constant_override("margin_" + side, 22)
	_card.add_child(margin)

	var col: VBoxContainer = VBoxContainer.new()
	col.add_theme_constant_override("separation", 6)
	margin.add_child(col)

	_card_kicker = UiTheme.make_label("", UiTheme.FS_TINY, UiTheme.TEXT_FAINT, true)
	_card_kicker.name = "CardKicker"
	col.add_child(_card_kicker)

	_card_title = UiTheme.make_label("", UiTheme.FS_TITLE, UiTheme.TEXT, true)
	_card_title.name = "CardTitle"
	col.add_child(_card_title)

	_card_subtitle = UiTheme.make_label("", UiTheme.FS_BODY, UiTheme.ACCENT, true)
	_card_subtitle.name = "CardSubtitle"
	col.add_child(_card_subtitle)

	_card_body = UiTheme.make_label("", UiTheme.FS_SMALL, UiTheme.TEXT_DIM, true)
	_card_body.name = "CardBody"
	_card_body.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	col.add_child(_card_body)


## The bottom third is one container, not three separately-anchored controls.
##
## Anchoring each region on its own means picking a Y offset per region, and because those
## offsets position the TOP edge, three regions of different heights end up with three
## different bottom edges. It looks almost right, which is worse than looking wrong — nobody
## can say what is off, only that the UI feels sloppy. A bottom-anchored stack that grows
## upward fixes the baseline once, and SHRINK_END makes every cell hang from it.
##
## The held strip sits on its own row above the bar so a long item name has the full width,
## and because the stack grows upward, showing or hiding it never moves the bar.
func _build_bottom() -> void:
	var stack: VBoxContainer = VBoxContainer.new()
	stack.name = "BottomStack"
	stack.set_anchors_preset(Control.PRESET_BOTTOM_WIDE)
	stack.grow_vertical = Control.GROW_DIRECTION_BEGIN
	stack.offset_left = UiTheme.MARGIN
	stack.offset_right = -UiTheme.MARGIN
	stack.offset_bottom = -UiTheme.MARGIN
	stack.add_theme_constant_override("separation", 14)
	stack.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_root.add_child(stack)

	var held_row: HBoxContainer = HBoxContainer.new()
	held_row.name = "HeldRow"
	held_row.alignment = BoxContainer.ALIGNMENT_CENTER
	held_row.mouse_filter = Control.MOUSE_FILTER_IGNORE
	stack.add_child(held_row)

	_held_box = PanelContainer.new()
	_held_box.name = "HeldBox"
	_held_box.add_theme_stylebox_override("panel", UiTheme.pill_box())
	_held_box.visible = false
	_held_box.mouse_filter = Control.MOUSE_FILTER_IGNORE
	held_row.add_child(_held_box)

	_held_label = UiTheme.make_label("", UiTheme.FS_HEADING, UiTheme.TEXT, true)
	_held_label.name = "HeldLabel"
	_held_box.add_child(_held_label)

	var bar: HBoxContainer = HBoxContainer.new()
	bar.name = "BottomBar"
	bar.add_theme_constant_override("separation", 16)
	bar.mouse_filter = Control.MOUSE_FILTER_IGNORE
	stack.add_child(bar)

	_toolbar = HBoxContainer.new()
	_toolbar.name = "ToolBar"
	_toolbar.add_theme_constant_override("separation", 12)
	_toolbar.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_toolbar.size_flags_vertical = Control.SIZE_SHRINK_END
	_toolbar.alignment = BoxContainer.ALIGNMENT_BEGIN
	_toolbar.mouse_filter = Control.MOUSE_FILTER_IGNORE
	bar.add_child(_toolbar)

	_counter = UiTheme.make_label("0/0", UiTheme.FS_HUGE, UiTheme.TEXT, false)
	_counter.name = "CarryCounter"
	_counter.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	# Shelled so count_to's end-of-roll punch has something it is allowed to scale, and hung at
	# the END of the bar rather than expanding: the toolbar already takes all the slack, so
	# shrink-end puts the counter hard against the right margin and a number that grows a digit
	# extends leftward instead of shifting the whole readout.
	_counter_shell = UiMotion.transform_shell(_counter)
	_counter_shell.size_flags_horizontal = Control.SIZE_SHRINK_END
	_counter_shell.size_flags_vertical = Control.SIZE_SHRINK_END
	bar.add_child(_counter_shell)
