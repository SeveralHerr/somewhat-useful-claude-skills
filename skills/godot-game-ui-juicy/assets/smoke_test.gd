extends SceneTree

var _fails: Array[String] = []
var _frames: int = 0
var _hud: GameHud
var _pause: PauseMenu
var _res: ResultsScreen

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
			"CarryCounter", "ComboShout", "ToolBar", "RewardCard"]:
		if _hud.find_child(n, true, false) == null:
			_fails.append("missing contract node %s" % n)

func _process(_d: float) -> bool:
	_frames += 1
	if _frames < 3:
		return false

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

	_res.present(
		[{"label": "Score", "value": "1250"}, {"label": "Time", "value": "2:04"}],
		[{"name": "Key", "found": true, "color": Color.GOLD, "tint": Color.GOLD, "tooltip": "Key"},
		 {"name": "Gem", "found": false, "color": Color.RED, "tint": Color.RED, "tooltip": "Gem"}],
		"Nearly there.")
	if _res.find_children("*", "PanelContainer", true, false).size() < 3:
		_fails.append("results screen did not build its panels/chips")

	if _fails.is_empty():
		print("SMOKE: ALL PASS")
		quit(0)
	else:
		for f: String in _fails:
			print("SMOKE FAIL: ", f)
		quit(1)
	return true
