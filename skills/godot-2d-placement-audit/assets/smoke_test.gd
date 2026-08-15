extends SceneTree

## Smoke test for scripts/placement_audit_2d.gd.
##
## Copy both this file and the script into a Godot 4 project, then:
##   godot --headless --path . --import
##   godot --headless --path . --script res://smoke_test.gd
## It prints `SMOKE: ALL PASS` and exits 0, or names the failure and exits 1.
##
## Every scene here is hosted at a deliberate non-zero offset, which is the whole
## point of the skill: at the origin `position` and `global_position` agree and
## the bugs these checks exist for cannot be reproduced.

const HOST_OFFSET := Vector2(37, 113)

var _failures: Array[String] = []


func _initialize() -> void:
	var host := Node2D.new()
	host.name = "Host"
	host.position = HOST_OFFSET
	root.add_child(host)

	_test_spawn_space(host)
	_test_reach()
	_test_table_covers()
	_test_grid_aligned(host)
	_test_rects(host)

	if _failures.is_empty():
		print("SMOKE: ALL PASS")
		quit(0)
	else:
		for line: String in _failures:
			print("SMOKE FAIL: %s" % line)
		quit(1)


func _check(ok: bool, what: String) -> void:
	if not ok:
		_failures.append(what)


## Every check must come back with a readable message. GDScript's `%` supports a
## smaller set of specifiers than C's — `%g` is not among them — and a bad one
## yields an empty string plus a stderr line, not an exception. The checks then
## "pass" while reporting nothing, which is the exact failure mode this whole
## skill is about, so it is worth asserting on rather than eyeballing.
func _check_reports(r: Dictionary, what: String) -> Dictionary:
	_check(String(r.message).length() > 0, "%s should produce a message, got an empty string" % what)
	return r


func _test_spawn_space(host: Node2D) -> void:
	var spawner := Node2D.new()
	spawner.name = "Spawner"
	spawner.position = Vector2(160, 160)
	host.add_child(spawner)

	var good := Node2D.new()
	good.name = "GoodBullet"
	good.position = spawner.position
	host.add_child(good)
	_check(Placement2D.check_spawn_space(spawner, good).ok, "a correctly seeded spawn should pass")

	# The real bug: seeded from global_position into a sibling's space.
	var bad := Node2D.new()
	bad.name = "BadBullet"
	bad.position = spawner.global_position
	host.add_child(bad)
	var r: Dictionary = Placement2D.check_spawn_space(spawner, bad)
	_check(not r.ok, "a spawn seeded from global_position should fail")
	_check(String(r.message).contains("global_position"),
		"the failure should name global_position, not just print a number")


func _test_reach() -> void:
	_check(not _check_reports(Placement2D.check_reach(62.0, 64.0), "short reach").ok,
		"reach below the pitch can never act")
	_check(not Placement2D.check_reach(64.0, 64.0).ok, "reach exactly at the pitch is still short")
	_check(_check_reports(Placement2D.check_reach(72.0, 64.0), "adequate reach").ok,
		"reach above the pitch is fine")
	_check(not Placement2D.check_reach(72.0, 64.0, 2.0).ok, "one cell of reach does not cover two")


func _test_table_covers() -> void:
	var table := {0: "a", 1: "b", 4: "c"}
	_check(Placement2D.check_table_covers([0, 1, 4], table).ok, "a covering table passes")
	var r: Dictionary = Placement2D.check_table_covers([0, 1, 4, 5, 5, 10], table)
	_check(not r.ok, "a table missing a produced key fails")
	_check((r.missing as Array).size() == 2, "each missing key is reported once, got %s" % [r.missing])


func _test_grid_aligned(host: Node2D) -> void:
	var on_grid := Node2D.new()
	on_grid.name = "OnGrid"
	on_grid.position = Vector2(3 * 64 + 32, 2 * 64 + 32)
	host.add_child(on_grid)
	_check(_check_reports(Placement2D.check_grid_aligned(on_grid, 64.0), "grid aligned").ok,
		"a cell centre is on the grid")

	var half_off := Node2D.new()
	half_off.name = "HalfOff"
	half_off.position = Vector2(3 * 64, 2 * 64)
	host.add_child(half_off)
	_check(not _check_reports(Placement2D.check_grid_aligned(half_off, 64.0), "grid misaligned").ok,
		"a cell CORNER fails a centred grid check — the half-cell shift is the bug")


func _test_rects(host: Node2D) -> void:
	var panel := ColorRect.new()
	panel.name = "Panel"
	panel.position = Vector2(10, 10)
	panel.size = Vector2(100, 50)
	host.add_child(panel)

	var rect: Rect2 = Placement2D.canvas_rect(panel)
	_check(rect.size == Vector2(100, 50), "canvas_rect returns the drawn size, got %s" % rect.size)
	_check(rect.position == HOST_OFFSET + Vector2(10, 10),
		"canvas_rect is in screen space including ancestor offsets, got %s" % rect.position)

	_check(Placement2D.check_within(panel, Rect2(Vector2.ZERO, Vector2(1152, 648))).ok,
		"a panel inside the viewport passes containment")
	_check(not Placement2D.check_within(panel, Rect2(Vector2.ZERO, Vector2(100, 100))).ok,
		"a panel escaping its region fails containment")

	var other := ColorRect.new()
	other.name = "Other"
	other.position = Vector2(60, 20)
	other.size = Vector2(100, 50)
	host.add_child(other)
	var pairs: Array[Dictionary] = Placement2D.check_overlap([panel, other])
	_check(pairs.size() == 1, "two overlapping panels report one pair, got %d" % pairs.size())
