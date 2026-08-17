extends SceneTree

var _fails: Array[String] = []
var _frames: int = 0
var _main_done: bool = false
var _hud: GameHud
var _pause: PauseMenu
var _res: ResultsScreen
var _bare: ResultsScreen

func _initialize() -> void:
	root.size = Vector2i(1280, 720)

	_hud = GameHud.new()
	root.add_child(_hud)

	# Deliberately configured in the SAME frame the node was created, before _ready can
	# have fired. This is the normal way a game wires a HUD and it must work.
	_hud.add_stat(&"score", UiTheme.Glyph.Kind.STAR)
	_hud.add_stat(&"coins", UiTheme.Glyph.Kind.COIN)
	_hud.build_tools([UiTheme.Glyph.Kind.MAGNIFIER, UiTheme.Glyph.Kind.BOLT])
	_hud.set_stat(&"score", 1250.0)
	_hud.set_stat(&"coins", 42.0, func(v: float) -> String: return "$" + UiMotion.group_digits(int(round(v))))
	_hud.set_counter(3, 8)
	_hud.set_progress(0.5)
	_hud.set_prompt("Press [E] to open")
	_hud.set_crosshair_hot(true)
	_hud.set_held("Brass Lantern", Color(0.2, 0.2, 0.9))
	_hud.set_hint("something rattles nearby")
	_hud.toast("Kitchen complete")
	_hud.shout("NICE!", UiTheme.ACCENT, 0.9)
	_hud.show_card("item found", "Golden Key", "Rare", "It opens something.", UiTheme.ACCENT)
	_hud.show_card("item found", "Second Card", "Common", "Queued behind the first.", UiTheme.TEXT)
	_hud.set_active_tool(1)

	_check_zero_frame()

	_pause = PauseMenu.new()
	root.add_child(_pause)
	_res = ResultsScreen.new()
	root.add_child(_res)
	var title: TitleScreen = TitleScreen.new()
	title.title = "TEST GAME"
	root.add_child(title)

func _label(owner: Node, n: String) -> Label:
	return owner.find_child(n, true, false) as Label

## Values that must be right with ZERO frames pumped — the headless-safety claim.
func _check_zero_frame() -> void:
	var cases: Array = [
		["score", _label(_hud.find_child("Stat_score", true, false), "*"), ""],
	]
	var score: Label = _hud.find_child("Stat_score", true, false).find_children("*", "Label", true, false)[0]
	if score.text != "1250":
		_fails.append("score label = '%s', expected '1250'" % score.text)
	var coins: Label = _hud.find_child("Stat_coins", true, false).find_children("*", "Label", true, false)[0]
	if coins.text != "$42":
		_fails.append("coins label = '%s', expected '$42'" % coins.text)
	if _label(_hud, "CarryCounter").text != "3/8":
		_fails.append("counter = '%s', expected '3/8'" % _label(_hud, "CarryCounter").text)
	if _label(_hud, "PromptLabel").text != "to open":
		_fails.append("prompt body = '%s', expected 'to open'" % _label(_hud, "PromptLabel").text)
	if _label(_hud, "CardTitle").text != "Golden Key":
		_fails.append("card title = '%s', expected 'Golden Key'" % _label(_hud, "CardTitle").text)
	if _label(_hud, "HeldLabel").text != "Brass Lantern":
		_fails.append("held = '%s'" % _label(_hud, "HeldLabel").text)
	_hud.set_prompt("It's locked")
	if (_hud.find_child("KeyChip", true, false) as Control).visible:
		_fails.append("keycap still visible on a status prompt")
	for n: String in ["StatStack", "HintLabel", "Crosshair", "PromptLabel", "HeldLabel",
			"CarryCounter", "ComboShout", "ToolBar", "RewardCard", "ToastBox"]:
		if _hud.find_child(n, true, false) == null:
			_fails.append("missing contract node %s" % n)

	# The same values again, this time through the public read-back API rather than by walking
	# to private node names. If these two ever disagree, the getters are lying.
	_hud.set_prompt("Press [E] to open")
	var reads: Array = [
		["stat_text(score)", _hud.stat_text(&"score"), "1250"],
		["stat_text(coins)", _hud.stat_text(&"coins"), "$42"],
		["counter_text", _hud.counter_text(), "3/8"],
		["prompt_text", _hud.prompt_text(), "to open"],
		["prompt_key", _hud.prompt_key(), "E"],
		["held_text", _hud.held_text(), "Brass Lantern"],
		["card_title", _hud.card_title(), "Golden Key"],
		["toast_text", _hud.toast_text(), "Kitchen complete"],
	]
	for r: Array in reads:
		if str(r[1]) != str(r[2]):
			_fails.append("%s = '%s', expected '%s'" % [r[0], r[1], r[2]])
	if _hud.crosshair_state() != GameHud.Cross.HOT:
		_fails.append("crosshair_state = %d, expected HOT" % _hud.crosshair_state())
	_hud.set_crosshair_state(GameHud.Cross.BLOCKED)
	if _hud.crosshair_state() != GameHud.Cross.BLOCKED:
		_fails.append("crosshair refused the BLOCKED state")
	_hud.set_crosshair_hot(true)

	# CLICK-THROUGH. A single Control left at the default MOUSE_FILTER_STOP is enough to eat
	# every mouse-motion event at the centre of the screen and silently kill first-person
	# mouse look, so this is asserted over the whole subtree rather than on the crosshair.
	for n: Node in _hud.find_children("*", "Control", true, false):
		var c: Control = n as Control
		if c.mouse_filter != Control.MOUSE_FILTER_IGNORE:
			_fails.append("'%s' is mouse_filter=%d; a HUD Control that is not IGNORE steals "
				% [c.name, c.mouse_filter] + "mouse look in a captured-cursor game")
			break

	# Every element the kit punches must be scalable where it sits, or the punch is dead code
	# that nobody notices because the accompanying tint still lands.
	for n: String in ["Stat_score", "Slot1", "CarryCounter"]:
		var c: Control = _hud.find_child(n, true, false) as Control
		if c != null and not UiMotion.can_transform(c):
			_fails.append("%s is a direct Container child, so it can never be punched" % n)

func _process(_d: float) -> bool:
	_frames += 1
	if _frames < 3:
		return false
	if not _main_done:
		_main_done = true
		_run_main_checks()
		return false

	_check_centred()
	if _fails.is_empty():
		print("SMOKE: ALL PASS")
		quit(0)
	else:
		for f: String in _fails:
			print("SMOKE FAIL: ", f)
		quit(1)
	return true


func _run_main_checks() -> void:
	# Headless clamps the window to 64x64, so assert against the ACTUAL viewport rect
	# rather than a requested size - the claim is "the HUD fills the viewport".
	var vp: Vector2 = root.get_visible_rect().size
	if _hud.layout_size() != vp:
		_fails.append("layout_size = %s, expected viewport %s" % [_hud.layout_size(), vp])

	# Resolution independence, checked in a SubViewport because it is not clamped like the
	# headless main window. The two claims are that the scale tracks viewport height and that
	# the HUD still covers the whole rect afterwards - a scaled layer whose root was not
	# resized to compensate passes the first check and fails the second.
	for probe: Vector2i in [Vector2i(1280, 720), Vector2i(3840, 2160), Vector2i(2560, 1080)]:
		var sub: SubViewport = SubViewport.new()
		sub.size = probe
		root.add_child(sub)
		var probe_hud: GameHud = GameHud.new()
		sub.add_child(probe_hud)
		var want: float = UiTheme.ui_scale(float(probe.y))
		if not is_equal_approx(probe_hud.layout_scale(), want):
			_fails.append("at %s ui_scale = %f, expected %f" % [probe, probe_hud.layout_scale(), want])
		if probe_hud.layout_size() != Vector2(probe):
			_fails.append("at %s layout_size = %s, expected full coverage" % [probe, probe_hud.layout_size()])
		sub.queue_free()

	var btns: Array[Node] = _pause.find_children("*", "Button", true, false)
	if btns.is_empty():
		_fails.append("pause menu built no buttons")
	else:
		var resumed: Array[bool] = [false]
		_pause.resume_requested.connect(func() -> void: resumed[0] = true)
		(btns[0] as Button).emit_signal("pressed")
		if not resumed[0]:
			_fails.append("resume_requested did not fire")
		for b: Node in btns:
			if b.process_mode != Node.PROCESS_MODE_ALWAYS:
				_fails.append("pause button '%s' is not PROCESS_MODE_ALWAYS" % b.name)
				break

		# "Quit to menu" must mean the menu. It used to emit quit_requested, which an
		# integrator quite reasonably wires to get_tree().quit() — and the button then closes
		# the game. The assertion is on the signal a labelled button actually fires, because
		# that is the thing that was wrong; the name alone reads fine either way.
		var to_menu: Button = null
		for b: Node in btns:
			if (b as Button).text == "Quit to menu":
				to_menu = b as Button
		if to_menu == null:
			_fails.append("pause menu has no 'Quit to menu' button")
		else:
			var fired: Array[String] = []
			_pause.menu_requested.connect(func() -> void: fired.append("menu"))
			_pause.quit_requested.connect(func() -> void: fired.append("quit"))
			to_menu.emit_signal("pressed")
			if fired.size() != 1 or fired[0] != "menu":
				_fails.append("'Quit to menu' fired %s, expected only menu_requested" % [fired])

	# The two sliders are optional the same way the two extra buttons are. A game with no
	# camera-look system and no audio bus used to ship both of them anyway, visible and inert,
	# which a player reads as a broken menu rather than as a feature this game does not have.
	# Asserted in BOTH directions: with the defaults left alone the sliders must still be
	# there, or "fixing" this by deleting them outright would pass just as happily.
	var default_sliders: Array[Node] = _pause.find_children("*", "HSlider", true, false)
	if default_sliders.size() != 2:
		_fails.append("default pause menu built %d HSlider(s), expected 2 (sensitivity, volume)"
			% default_sliders.size())
	var quiet: PauseMenu = PauseMenu.new()
	quiet.show_sensitivity = false
	quiet.show_volume = false
	root.add_child(quiet)
	var quiet_sliders: Array[Node] = quiet.find_children("*", "HSlider", true, false)
	if not quiet_sliders.is_empty():
		_fails.append("pause menu with show_sensitivity/show_volume off still built %d HSlider(s)"
			% quiet_sliders.size())
	for n: Node in quiet.find_children("*", "Label", true, false):
		var caption: String = (n as Label).text
		if caption == "Mouse sensitivity" or caption == "Volume":
			_fails.append("pause menu with the sliders off kept the '%s' caption" % caption)
	# set_values() is the call a game makes as the menu opens, so a slider that was never
	# built must not be dereferenced there — that regression would be worse than a dead control.
	quiet.set_values(1.0, 0.5)
	quiet.queue_free()

	_res.present(
		[{"label": "Score", "value": "1250"}, {"label": "Time", "value": "2:04"}],
		[{"name": "Key", "found": true, "color": Color.GOLD, "tint": Color.GOLD, "tooltip": "Key"},
		 {"name": "Gem", "found": false, "color": Color.RED, "tint": Color.RED, "tooltip": "Gem"}],
		"Nearly there.")
	if _res.find_children("*", "PanelContainer", true, false).size() < 3:
		_fails.append("results screen did not build its panels/chips")

	# A results screen with no collection grid has nothing that expands, so its content used to
	# stack in the top third above a screen-height of empty backdrop. Built in a SubViewport of
	# a real size — the headless main window is clamped to 64x64, which is smaller than the
	# content and would make any centring assertion meaningless.
	var sub: SubViewport = SubViewport.new()
	sub.size = Vector2i(1280, 720)
	root.add_child(sub)
	_bare = ResultsScreen.new()
	sub.add_child(_bare)
	_bare.present([{"label": "Score", "value": "1250"}], [], "Nearly there.")


## Measured a frame after the screen is built, because present() rebuilds the tree and a
## Container's children have no rect until the next layout pass — measuring in the same frame
## reads zeroes and "passes" for the wrong reason.
func _check_centred() -> void:
	var cols: Array[Node] = _bare.find_children("*", "VBoxContainer", true, false)
	if cols.is_empty():
		_fails.append("bare results screen built no content column")
		return
	# Measured on the column's CHILDREN, not on the column. The column is stretched to fill its
	# MarginContainer whatever the alignment is, so a check on its own rect passes identically
	# with the content jammed against the top — which is the bug this is here to catch.
	var col: Control = cols[0] as Control
	var rows: Array[Node] = col.get_children()
	if rows.is_empty():
		_fails.append("bare results screen built an empty content column")
		return
	var first: Control = rows[0] as Control
	var last: Control = rows[rows.size() - 1] as Control
	var above: float = first.position.y
	var below: float = col.size.y - (last.position.y + last.size.y)
	if absf(above - below) > maxf(8.0, col.size.y * 0.05):
		_fails.append("results content is not vertically centred: %.0fpx above, %.0fpx below"
			% [above, below])
