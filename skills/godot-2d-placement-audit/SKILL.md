---
name: godot-2d-placement-audit
description: >
  Assert a Godot 4 2D layout numerically instead of trusting a screenshot or a
  green test suite — whether a spawned projectile actually leaves its spawner,
  whether a tower's range reaches the tile beside it, whether every tile mask
  the level produces has an entry in the lookup table, and whether sprites stay
  on their grid and inside their playfield. Use this whenever code positions 2D
  nodes: building a tile grid or playfield, placing towers/units/props on cells,
  spawning bullets or particles from an emitter, laying out a HUD over a
  CanvasLayer, or writing a level-builder. Reach especially hard for it at the
  symptoms, which never say "placement": "the tower doesn't shoot", "my bullets
  do nothing", "nothing happens when the enemy walks past", "the sprite is off
  by a bit", "the HUD is in the wrong place", "this only breaks in the real
  game, not in tests", "the tiles have a hole in them", "it looks fine but
  doesn't work". Those are what a 2D placement bug sounds like from the outside,
  because a misplaced node renders as a perfectly plausible picture and the
  usual unit test hosts everything at the origin, where the bug does not exist.
  For 3D scenes use godot-3d-placement-audit instead; for a kit's real grid
  pitch and pivot conventions, measure them with kenney-asset-kit first.
---

# Auditing 2D placement in Godot 4

A 2D placement bug does not look like a bug. It looks like a game where one
thing quietly does nothing: a plant that never fires, a pickup nobody can
collect, a hitbox that never lands. Nothing errors, because "found no target"
and "there is no target" are the same observation, and neither is exceptional.

The only reliable check is numeric — compute what nodes actually occupy on
screen and assert the relationships you meant.

## Why the tests do not catch this

This is the part worth internalising, because it is what makes the whole class
of bug survive a green suite.

A unit test builds a small scene: a parent node, a couple of actors, assert.
Almost always that parent sits at the origin, so **`position` and
`global_position` are the same number**, and every coordinate-space mistake
evaporates. The test passes, honestly, and proves nothing about the game, where
the same nodes hang under a HUD offset, a camera, or a scaled `CanvasLayer`.

So the first rule of auditing 2D placement: **run the audit under a deliberate
non-zero offset.** Give the host parent a `position` of something ugly like
`(0, 72)` or `(37, 113)`. A check that only passes at the origin is not a check.

```gdscript
var host := Node2D.new()
host.position = Vector2(0, 72)   # never (0, 0) — that is where the bug hides
```

## Measure in one declared space

`scripts/placement_audit_2d.gd` implements the primitive. Drop it into the
project and call it; do not re-derive it inline.

```gdscript
var rect := Placement2D.canvas_rect(node)                 # screen space, whole subtree
var r := Placement2D.check_spawn_space(cannon, bullet)
if not r.ok:
    push_error(r.message)
```

`assets/smoke_test.gd` proves the script works in the project you dropped it
into — copy both files in, `godot --headless --path . --import`, then
`godot --headless --path . --script res://smoke_test.gd`. It prints
`SMOKE: ALL PASS`. Run it once before trusting a report from a fresh install.

Three ways the space goes wrong, all of which report confident numbers:

- **`global_position` is not the space a sibling lives in.** A node added to
  `get_parent()` shares that parent's local space. Seeding it from
  `global_position` puts it exactly one ancestor-offset away — so a projectile
  spawns a whole HUD-bar-height below the gun and hits nothing.
- **`global_position` ignores `CanvasLayer`.** A layer's transform is not part
  of the node hierarchy's global transform. Anything on a HUD layer must be
  measured with `get_global_transform_with_canvas()`, which is what
  `canvas_rect()` uses.
- **Containers hide their children's transforms.** Godot overwrites
  `position`/`scale` on a `Container`'s children every layout pass, so a
  property read on a `VBoxContainer` child tells you nothing about where it
  draws or what it is mid-tween. Read `get_global_rect()` — or `data.transform`
  if you are reading over a debug bridge.

## The checks

Run whichever the scene warrants; they compose.

| Check | Asserts | Catches |
|---|---|---|
| `check_spawn_space(spawner, spawned)` | spawned lands on its spawner, in the shared space | projectiles/effects born one offset away, doing nothing |
| `check_reach(radius, pitch, cells)` | a radius exceeds the grid distance it must cover | towers, pickups and triggers that can never fire |
| `check_table_covers(keys_used, table)` | every key the level produces has an entry | tile-mask holes, missing state art, silent fallbacks |
| `check_within(item, rect)` | drawn rect inside a region | sprites off the playfield, HUD off screen |
| `check_overlap(items)` | no two drawn rects intersect | units stacked on one cell, overlapping panels |
| `check_grid_aligned(item, pitch)` | position sits on the grid | the half-cell shift from mixing corner and centre |

`check_reach` is the one people do not think to write, and it is a one-line
arithmetic fact with a brutal failure mode: an actor on a grid cell and a target
on the neighbouring cell are **exactly `pitch` apart at their closest**. A
radius of `pitch - 2` is not "slightly short", it is *never* — and it looks
identical to an empty lane. Any radius that must cover an adjacent cell has to
exceed the pitch, so assert it against the pitch rather than eyeballing whether
the number seems big enough.

`check_table_covers` generalises past tiles. Any `Dictionary.get(key, fallback)`
that feeds a visual — mask → tile, state → animation, rarity → colour — fails by
*drawing something else*, which no exception and no assertion will ever see.
Enumerate the keys the generator can actually produce and check them against the
table, rather than trusting that the table was written for the level it got.

## Reporting

Report the **margin**, not a boolean. "Reaches" and "reaches by 2 px" are
different facts: the second says the next tweak to cell size breaks it. Every
`check_*` returns `{ok, margin, message}` for exactly this reason.

```
kernel spawned 72.0 px from CornCobbler (drift (0, 72)) — which is exactly the
  ancestor offset, so it was seeded from global_position instead of position
reach 62.0 px falls 2.0 px short of the 64.0 px needed to touch the cell 1 away
  — it can never act
3 key(s) the scene produces have no table entry and will silently draw the
  fallback: [5, 10, 13]
```

When you fix one of these, **write the regression test with the offset host**,
and prove it fails when reverted. A test that passes both before and after the
fix is the same test that let the bug through in the first place.

## Gotchas

- **Audit after the tree is built.** `@onready`, container layout and any
  builder in `_ready()` have not run during `_init`, and headless pumps no
  frames on its own. Await a frame first, or a `Control`'s `size` is `(0, 0)`
  and every rect check passes vacuously.
- **A zero-size rect means "nothing to measure", not "a point at the origin".**
  `canvas_rect` returns the node's screen position with zero size when it finds
  no visible sprite or sized `Control` underneath — do not feed that to an
  overlap check and read the pass as meaningful.
- **Rotation measures large.** The enclosing axis-aligned rect of a rotated
  sprite is bigger than what it draws, so an overhang report on a rotated node
  is a suspicion, not a proof. Say which it is.
- **`texture.get_size()` is not the drawn size.** `scale`, `region_rect` and a
  `Sprite2D`'s `centered`/`offset` all move it. Measure the rect.
- **Grid pitch is a measured fact, not a guess.** If the art came from an asset
  kit, get the real cell size out of the kit with `kenney-asset-kit` before
  asserting anything against it — a check against the wrong pitch is worse than
  no check, because it passes.
