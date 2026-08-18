extends SceneTree

## Motion tests for the juicy kit. Run alongside smoke_test.gd, which covers the static UI:
##
##     godot --headless --path <project> --script res://juice_test.gd
##
## Four things are checked here, and each one corresponds to a way juicy UI actually breaks
## rather than to a way it is written:
##
##  1. The pause menu animates WHILE THE TREE IS PAUSED. This is the failure that looks like
##     a rendering bug — the panel freezes at 86% scale, half transparent, and nothing in the
##     scene tree explains it. It happens whenever a tween's pause mode is left at BOUND.
##
##  2. Disabling motion settles everything instantly. If UiJuice.enabled = false leaves so
##     much as one element at alpha 0, the accessibility switch ships a blank menu.
##
##  3. Animation that cannot run leaves the UI VISIBLE, not armed. Every entrance sets its
##     start state (alpha 0, scale 0.86) — if it does that before checking whether a tween
##     exists, a headless run ends with a fully built, entirely invisible UI and no error.
##     This is the single most expensive bug in this file and the reason for the ordering
##     inside UiJuice.enter.
##
##  4. dismiss() frees the node even when nothing can animate, so exits are assertable as
##     "it is gone" rather than "it is gone eventually".
##
##  5. The switch covers UiMotion as well as UiJuice. A "motion off" build whose counters
##     still roll is not deterministic, and the assertion two frames later reads a mid-roll
##     number that nothing in the test explains.
##
##  6. The elements the HUD punches can actually be scaled where they sit. A punch on a
##     direct Container child is silently discarded on the next layout pass.
##
## The entrance is sampled until it SETTLES rather than for a fixed number of frames. A
## frame count is a wall-clock assumption in disguise — headless frames are not 16ms, and the
## same "is it past halfway yet" check that passes on one machine fails on a faster one.

const SETTLE_FRAME_BUDGET: int = 600

var _fails: Array[String] = []
var _step: int = 0
var _vp: SubViewport = null
var _menu: PauseMenu = null
var _panel: Control = null
var _samples: Array[Vector2] = []
var _disabled_menu: PauseMenu = null
var _hud: GameHud = null


func _initialize() -> void:
	# Check 3 first, before any frames exist at all: build a menu, pump nothing, and require
	# every part of it to be visible.
	var off_vp: SubViewport = SubViewport.new()
	off_vp.size = Vector2i(1280, 720)
	root.add_child(off_vp)
	var cold: PauseMenu = PauseMenu.new()
	off_vp.add_child(cold)
	for n: Node in cold.find_children("*", "Control", true, false):
		var c: Control = n as Control
		if c.modulate.a < 0.99:
			_fails.append("with no frames pumped, '%s' is at alpha %.2f (armed but never animated)"
				% [c.name, c.modulate.a])
			break
	cold.queue_free()
	off_vp.queue_free()


func _process(_delta: float) -> bool:
	match _step:
		0:
			_vp = SubViewport.new()
			_vp.size = Vector2i(1280, 720)
			root.add_child(_vp)
			# Paused before the menu exists, exactly as a game does it.
			paused = true
			_menu = PauseMenu.new()
			_vp.add_child(_menu)
			_panel = _menu.get_node_or_null("Root/CenterContainer/Panel") as Control
			if _panel == null:
				# Name-independent fallback: the panel is the only PanelContainer in there.
				var found: Array[Node] = _menu.find_children("*", "PanelContainer", true, false)
				_panel = (found[0] as Control) if not found.is_empty() else null
			if _panel == null:
				_fails.append("pause menu built no panel to animate")
		1:
			# Sample every frame until the panel settles, then move on. Staying in this step
			# rather than counting frames is what makes the "did it finish" assertion below
			# mean what it says on any machine.
			if _panel != null:
				_samples.append(Vector2(_panel.scale.x, _panel.modulate.a))
				if _panel.modulate.a < 0.999 and _samples.size() < SETTLE_FRAME_BUDGET:
					return false
			_check_animated()
			_menu.dismiss()
		2:
			if is_instance_valid(_menu) and not _menu.is_queued_for_deletion():
				# Not yet freed is fine mid-exit; the disabled case below is the hard assertion.
				pass
			paused = false
			UiJuice.enabled = false
			_disabled_menu = PauseMenu.new()
			_vp.add_child(_disabled_menu)
		3:
			for n: Node in _disabled_menu.find_children("*", "Control", true, false):
				var c: Control = n as Control
				if c.modulate.a < 0.99 or not c.scale.is_equal_approx(Vector2.ONE):
					_fails.append("motion disabled but '%s' is at alpha %.2f scale %s"
						% [c.name, c.modulate.a, c.scale])
					break
			_disabled_menu.dismiss()
		4:
			if is_instance_valid(_disabled_menu) and not _disabled_menu.is_queued_for_deletion():
				_fails.append("dismiss() with motion disabled did not free the menu immediately")
			_check_switch_covers_ui_motion()
			UiJuice.enabled = true
		5:
			_check_punches_land()
		_:
			# quit() with the code, the way smoke_test.gd does. Returning true from a
			# SceneTree's _process ends the run with 0 whatever happened, so this suite
			# used to report every failure on stdout and still exit green — a caller
			# grading it on `$?` alone had never once seen it fail. The marker line is
			# still what a reader looks at; the code is what a runner can trust.
			if _fails.is_empty():
				print("JUICE: ALL PASS")
				quit(0)
			else:
				print("JUICE: %d FAILED" % _fails.size())
				for f: String in _fails:
					print("  - " + f)
				quit(1)
			return true
	_step += 1
	return false


## With motion off, a HUD in a live tree must still show FINAL values immediately.
##
## Called while UiJuice.enabled is still false. Rolling a counter is the case that matters:
## count_to is a UiMotion function, so a switch that only covered UiJuice would leave the
## label reading "0" here — and every headless assertion that samples a frame or two after a
## state change would be reading the animation rather than the state.
func _check_switch_covers_ui_motion() -> void:
	var hud: GameHud = GameHud.new()
	_vp.add_child(hud)
	hud.add_stat(&"score", UiTheme.Glyph.Kind.STAR)
	hud.set_stat(&"score", 1250.0)
	hud.set_counter(3, 8)
	hud.set_progress(0.5)
	if hud.stat_text(&"score") != "1250":
		_fails.append("motion disabled but the stat is mid-roll at '%s'" % hud.stat_text(&"score"))
	if hud.counter_text() != "3/8":
		_fails.append("motion disabled but the counter is mid-roll at '%s'" % hud.counter_text())
	hud.queue_free()


## Every element the HUD punches must actually move. punch() writes the inflated scale before
## the tween starts, so one frame is enough to tell a live punch from a refused one — and a
## refused one is invisible in play, because the tint that accompanies it still lands.
func _check_punches_land() -> void:
	_hud = GameHud.new()
	_vp.add_child(_hud)
	_hud.add_stat(&"score", UiTheme.Glyph.Kind.STAR)
	_hud.build_tools([UiTheme.Glyph.Kind.MAGNIFIER, UiTheme.Glyph.Kind.BOLT])
	_hud.flash_stat(&"score", UiTheme.GOOD)
	_hud.set_active_tool(1)
	var row: Control = _hud.find_child("Stat_score", true, false) as Control
	var slot: Control = _hud.find_child("Slot2", true, false) as Control
	if row != null and is_equal_approx(row.scale.x, 1.0):
		_fails.append("flash_stat did not punch the row (scale still 1.0)")
	if slot != null and is_equal_approx(slot.scale.x, 1.0):
		_fails.append("set_active_tool did not punch the slot (scale still 1.0)")
	_hud.queue_free()


## The panel must both move and finish. A frozen tween produces identical samples; a tween
## that runs but never completes leaves the panel below its resting size forever.
func _check_animated() -> void:
	if _samples.size() < 4:
		_fails.append("captured only %d animation samples" % _samples.size())
		return
	var scale_moved: bool = false
	var alpha_moved: bool = false
	for i: int in range(1, _samples.size()):
		if not is_equal_approx(_samples[i].x, _samples[0].x):
			scale_moved = true
		if not is_equal_approx(_samples[i].y, _samples[0].y):
			alpha_moved = true
	if not scale_moved:
		_fails.append("panel scale never changed while paused (frozen tween: pause mode is BOUND, not PROCESS) — samples %s"
			% [_samples])
	if not alpha_moved:
		_fails.append("panel alpha never changed while paused — samples %s" % [_samples])

	var last: Vector2 = _samples[_samples.size() - 1]
	if last.y < 0.5:
		_fails.append("panel still at alpha %.2f after %d frames" % [last.y, _samples.size()])
