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

var _fails: Array[String] = []
var _step: int = 0
var _vp: SubViewport = null
var _menu: PauseMenu = null
var _panel: Control = null
var _samples: Array[Vector2] = []
var _disabled_menu: PauseMenu = null


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
		1, 2, 3, 4, 5, 6, 7, 8:
			if _panel != null:
				_samples.append(Vector2(_panel.scale.x, _panel.modulate.a))
		9:
			_check_animated()
			_menu.dismiss()
		10:
			if is_instance_valid(_menu) and not _menu.is_queued_for_deletion():
				# Not yet freed is fine mid-exit; the disabled case below is the hard assertion.
				pass
			paused = false
			UiJuice.enabled = false
			_disabled_menu = PauseMenu.new()
			_vp.add_child(_disabled_menu)
		11:
			for n: Node in _disabled_menu.find_children("*", "Control", true, false):
				var c: Control = n as Control
				if c.modulate.a < 0.99 or not c.scale.is_equal_approx(Vector2.ONE):
					_fails.append("motion disabled but '%s' is at alpha %.2f scale %s"
						% [c.name, c.modulate.a, c.scale])
					break
			_disabled_menu.dismiss()
		12:
			if is_instance_valid(_disabled_menu) and not _disabled_menu.is_queued_for_deletion():
				_fails.append("dismiss() with motion disabled did not free the menu immediately")
			UiJuice.enabled = true
		_:
			if _fails.is_empty():
				print("JUICE: ALL PASS")
			else:
				print("JUICE: %d FAILED" % _fails.size())
				for f: String in _fails:
					print("  - " + f)
			return true
	_step += 1
	return false


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
