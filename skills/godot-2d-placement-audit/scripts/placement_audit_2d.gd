class_name Placement2D
extends RefCounted

## Numeric assertions for 2D layouts, grids and spawns.
##
## A misplaced 2D node renders as a plausible picture — a tower that never fires
## looks exactly like a tower with nothing in range — so screenshots confirm
## nothing and unit tests usually confirm less, because they host every actor
## under one parent at the origin, which is precisely the condition under which
## coordinate-space bugs disappear.
##
## Every check reports a **margin**, not a boolean. "Reaches" and "reaches by
## 2 px" are different facts, and anything laid out on a grid drifts into the
## second one.
##
## The measuring primitive is `canvas_rect()`, which uses
## `get_global_transform_with_canvas()` rather than `global_position`. That
## distinction is the whole correctness story in 2D: `global_position` ignores
## the transform of any ancestor `CanvasLayer`, so a HUD on a scaled layer
## reports coordinates that exist nowhere on screen — and it reports them
## confidently, as plain numbers, with nothing to suggest they are wrong.

## Default slack in pixels. Loose enough to survive float error and a one-pixel
## rounding in layout, tight enough that a whole-cell mistake still fails.
const TOLERANCE := 1.0


# -- measuring ---------------------------------------------------------------


## Screen-space rect enclosing `root` and every visible CanvasItem under it.
## Returns a zero-size rect at the node's screen position when there is nothing
## measurable — treat that as "nothing to measure", not as a point at the origin.
static func canvas_rect(root: CanvasItem) -> Rect2:
	var out := Rect2()
	var found := false
	var stack: Array[Node] = [root]
	while not stack.is_empty():
		var node: Node = stack.pop_back()
		var item := node as CanvasItem
		if item != null:
			var own := _own_rect(item)
			if own.size != Vector2.ZERO:
				out = own if not found else out.merge(own)
				found = true
		for child: Node in node.get_children():
			stack.push_back(child)
	if not found:
		return Rect2(root.get_global_transform_with_canvas().origin, Vector2.ZERO)
	return out


static func _own_rect(item: CanvasItem) -> Rect2:
	if not item.visible:
		return Rect2()
	var control := item as Control
	if control != null:
		return _transformed(control.get_global_transform_with_canvas(), Rect2(Vector2.ZERO, control.size))
	var sprite := item as Sprite2D
	if sprite != null and sprite.texture != null:
		var size: Vector2 = sprite.texture.get_size()
		var origin: Vector2 = sprite.offset - (size * 0.5 if sprite.centered else Vector2.ZERO)
		return _transformed(sprite.get_global_transform_with_canvas(), Rect2(origin, size))
	return Rect2()


## Axis-aligned rect enclosing a transformed one. Conservative under rotation:
## a rotated sprite measures larger than it draws, so an overhang report on a
## rotated node is a suspicion, not a proof. Say so when reporting it.
static func _transformed(xform: Transform2D, local: Rect2) -> Rect2:
	var out := Rect2(xform * local.position, Vector2.ZERO)
	out = out.expand(xform * (local.position + Vector2(local.size.x, 0.0)))
	out = out.expand(xform * (local.position + Vector2(0.0, local.size.y)))
	return out.expand(xform * local.end)


# -- checks ------------------------------------------------------------------


## A node spawned by another must land where its spawner is, in the space they
## share. Passing `global_position` to a node you added to `get_parent()` is the
## single most common 2D placement bug, and it is invisible until some ancestor
## carries an offset — a HUD bar, a camera parent, a scaled CanvasLayer.
static func check_spawn_space(spawner: Node2D, spawned: Node2D, tolerance: float = TOLERANCE) -> Dictionary:
	var shared: bool = spawner.get_parent() == spawned.get_parent()
	var drift: Vector2 = spawned.position - spawner.position
	var ancestor_offset: Vector2 = spawner.global_position - spawner.position
	if not shared:
		return {
			"ok": false,
			"margin": INF,
			"message": "%s and %s do not share a parent, so their `position` values are not comparable — compare canvas_rect() instead" % [spawner.name, spawned.name],
		}
	var ok: bool = drift.length() <= tolerance
	var message := "%s spawned at its owner's position" % spawned.name
	if not ok:
		message = "%s spawned %.1f px from %s (drift %s)" % [spawned.name, drift.length(), spawner.name, drift]
		# The diagnosis worth printing: a drift that IS the ancestor offset names
		# the bug outright rather than leaving it to be inferred from a number.
		if ancestor_offset != Vector2.ZERO and (drift - ancestor_offset).length() <= tolerance:
			message += " — which is exactly the ancestor offset, so it was seeded from global_position instead of position"
	return {"ok": ok, "margin": drift.length(), "drift": drift, "message": message}


## Any radius that has to cover the cell `cells` away must EXCEED the grid pitch,
## not approach it: an actor on one cell and a target on the next are exactly
## `pitch` apart at their closest. A radius equal to or just under the pitch
## produces a thing that never acts and never errors, because "found no target"
## and "there is no target" are the same observation.
static func check_reach(radius: float, pitch: float, cells: float = 1.0) -> Dictionary:
	var needed: float = pitch * cells
	var margin: float = radius - needed
	var ok: bool = margin > 0.0
	var message := "reach %.1f px clears the %.1f px to the cell %s away by %.1f" % [radius, needed, cells, margin]
	if not ok:
		message = "reach %.1f px falls %.1f px short of the %.1f px needed to touch the cell %s away — it can never act" % [
			radius, -margin, needed, cells,
		]
	return {"ok": ok, "margin": margin, "needed": needed, "message": message}


## Every key the scene actually produces must exist in the lookup table. A
## `table.get(key, fallback)` miss does not raise: it renders. A tile mask with
## no entry draws the fallback tile and leaves a square hole in the art that
## only a screenshot shows, so enumerate the keys the level generates and assert
## the table covers them instead.
static func check_table_covers(keys_used: Array, table: Dictionary) -> Dictionary:
	var missing: Array = []
	for key: Variant in keys_used:
		if not table.has(key) and not missing.has(key):
			missing.append(key)
	var ok: bool = missing.is_empty()
	var message := "the table covers all %d key(s) the scene produces" % keys_used.size()
	if not ok:
		message = "%d key(s) the scene produces have no table entry and will silently draw the fallback: %s" % [
			missing.size(), missing,
		]
	return {"ok": ok, "margin": float(-missing.size()), "missing": missing, "message": message}


## A node's drawn rect must stay inside a region — a playfield, a panel, the
## viewport. Reports the worst edge and by how much.
static func check_within(item: CanvasItem, region: Rect2) -> Dictionary:
	var rect: Rect2 = canvas_rect(item)
	var slack := {
		"left": rect.position.x - region.position.x,
		"top": rect.position.y - region.position.y,
		"right": region.end.x - rect.end.x,
		"bottom": region.end.y - rect.end.y,
	}
	var worst: float = INF
	var worst_edge := ""
	for edge: String in slack:
		if float(slack[edge]) < worst:
			worst = float(slack[edge])
			worst_edge = edge
	var ok: bool = worst >= 0.0
	var message := "%s sits inside the region, %.1f px clear on its tightest edge (%s)" % [item.name, worst, worst_edge]
	if not ok:
		message = "%s escapes the region by %.1f px on the %s" % [item.name, -worst, worst_edge]
	return {"ok": ok, "margin": worst, "edge": worst_edge, "message": message}


## No two drawn rects may intersect. Returns one entry per offending pair, so an
## empty array is the pass. Feed it only the things that genuinely must not
## overlap — anything deliberately stacked (a plant on its plot, a badge on a
## card) belongs in check_within against its holder instead.
static func check_overlap(items: Array) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	var rects: Array[Rect2] = []
	for item: Variant in items:
		rects.append(canvas_rect(item as CanvasItem))
	for i: int in range(items.size()):
		for j: int in range(i + 1, items.size()):
			var shared: Rect2 = rects[i].intersection(rects[j])
			if shared.size.x > 0.0 and shared.size.y > 0.0:
				out.append({
					"ok": false,
					"margin": -minf(shared.size.x, shared.size.y),
					"message": "%s overlaps %s by %.1f x %.1f px" % [
						(items[i] as CanvasItem).name, (items[j] as CanvasItem).name,
						shared.size.x, shared.size.y,
					],
				})
	return out


## A node meant to sit on a grid must sit on it. Catches the off-by-half-a-cell
## that comes from mixing a cell's corner with its centre.
static func check_grid_aligned(item: Node2D, pitch: float, origin: Vector2 = Vector2.ZERO,
		centred: bool = true, tolerance: float = TOLERANCE) -> Dictionary:
	var expected_offset: Vector2 = Vector2(pitch, pitch) * 0.5 if centred else Vector2.ZERO
	var local: Vector2 = item.position - origin - expected_offset
	var drift := Vector2(fposmod(local.x, pitch), fposmod(local.y, pitch))
	if drift.x > pitch * 0.5:
		drift.x -= pitch
	if drift.y > pitch * 0.5:
		drift.y -= pitch
	var ok: bool = drift.length() <= tolerance
	var message := "%s is on the %.1f px grid" % [item.name, pitch]
	if not ok:
		message = "%s is %s off the %.1f px grid — check whether the caller means a cell corner or its centre" % [
			item.name, drift, pitch,
		]
	return {"ok": ok, "margin": drift.length(), "drift": drift, "message": message}
