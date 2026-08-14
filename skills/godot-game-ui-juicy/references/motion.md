# Motion reference

Timing, curves, and how to add a juice verb that does not break the headless path.

- [Curve selection](#curve-selection)
- [Duration table](#duration-table)
- [Adding a juice verb](#adding-a-juice-verb)
- [Diagnosing a tween that "did not run"](#diagnosing-a-tween-that-did-not-run)

## Curve selection

Godot's `TRANS_` families are easy to pick by vibe and wrong surprisingly often. The useful
mapping for UI:

| Curve | Ease | Reads as | Use for |
|---|---|---|---|
| `TRANS_BACK` | `EASE_OUT` | arriving with weight, settling | every entrance |
| `TRANS_QUAD` | `EASE_IN` | leaving, gathering speed | every exit |
| `TRANS_ELASTIC` | `EASE_OUT` | absorbing an impact | punches, counters, slot selection |
| `TRANS_SINE` | `EASE_IN_OUT` | breathing, drifting | idle loops, ambient motion |
| `TRANS_CUBIC` | `EASE_OUT` | smooth and neutral | progress bars, value bars |
| `TRANS_LINEAR` | — | mechanical | colour fades, alpha, almost nothing else |

Two rules that matter more than the table:

**`EASE_OUT` for anything the player is waiting on.** `EASE_IN` on an entrance means the
element spends its first frames barely moving, which is indistinguishable from lag. Save
`EASE_IN` for exits, where the element is leaving and the player has already moved on.

**`TRANS_ELASTIC` and `TRANS_BACK` overshoot, so they need headroom.** An element already
touching a screen edge that overshoots by 10% will clip. Either inset it or use `TRANS_CUBIC`
for that one case.

## Duration table

Numbers that feel right for game UI at 60fps. Every one of these scales with
`UiJuice.speed`.

| Motion | Duration | Notes |
|---|---|---|
| Entrance (panel, screen) | 0.30 – 0.40s | `IN_TIME` is 0.34 |
| Exit | 0.10 – 0.16s | roughly a third of the entrance |
| Stagger step between siblings | 0.04 – 0.06s | past 0.08 it reads as slow, not sequenced |
| Punch / squash | 0.20 – 0.30s | elastic needs the length to show the settle |
| Shake | 0.15 – 0.35s | shorter than feels right when you write it |
| Screen flash | 0.15 – 0.25s | any longer and it obscures the thing it announces |
| Number roll-up | scales with distance | +1 is a tick, +5000 is an event |
| Idle breathe | 2.0 – 3.0s per cycle | must be slow enough to be felt, not watched |

The single most common tuning error is making everything too slow. When in doubt, cut every
duration by a third and see whether anything is actually lost.

## Adding a juice verb

Every function in `ui_juice.gd` has the same five-part shape, and following it is what keeps
the kit assertable headlessly:

```gdscript
static func my_verb(host: Node, target: Control, amount: float = 0.2) -> void:
    # 1. Refuse the cases that cannot work, loudly enough to debug.
    if target == null or not can_transform(target):
        return

    # 2. Capture the resting state BEFORE touching anything. Resting scale is often not 1.0 —
    #    screens are scaled for display resolution.
    center_pivot(target)
    var rest: Vector2 = target.scale

    # 3. Ask for the tween. This is the single choke point for "motion disabled" and
    #    "headless, no frames will pass".
    var t: Tween = tween(host, true)
    if t == null:
        return          # already at rest; nothing to undo because nothing was armed yet

    # 4. Only NOW arm the start state. Arming before step 3 is how a headless run ends up
    #    with an invisible UI and no error to explain it.
    target.scale = rest * (1.0 + amount)

    # 5. Animate back to the captured rest, never to a literal.
    t.tween_property(target, "scale", rest, _t(PUNCH_TIME)) \
        .set_trans(Tween.TRANS_ELASTIC).set_ease(Tween.EASE_OUT)
```

The ordering of 3 and 4 is the whole discipline. If a verb sets its start state first and
then discovers it cannot animate, the element is stuck at the start state permanently — and
because the start state is usually "invisible", the failure looks like the UI was never
built rather than like an animation problem.

For verbs that end by doing something (freeing a node, firing a callback), the callback must
run immediately on the `t == null` path too. That is what makes exits testable as "it is
gone" rather than "it is gone eventually".

## Diagnosing a tween that "did not run"

In rough order of likelihood:

1. **The target is a Container child and you animated a transform.** `Container.fit_child_in_rect`
   resets position, size, rotation and scale every layout pass. Check
   `UiJuice.can_transform(node)`. Symptom: alpha animates, transform does not.
2. **The tree is paused and the tween's pause mode is `BOUND`.** Symptom: the animation
   freezes at frame one and stays there. Fix: `tween.set_pause_mode(Tween.TWEEN_PAUSE_PROCESS)`,
   or `UiJuice.tween(host, true)`.
3. **No frames are being pumped** (headless, or the node is not in the tree). This is not a
   bug — but check the element ended at its *final* state, not its start state.
4. **`pivot_offset` is stale**, so the scale is happening but swinging from a corner and does
   not look like the animation you wrote. Fix: `UiJuice.center_pivot`, which tracks `resized`.
5. **Two tweens on the same property.** The last one created wins, intermittently. One
   property, one animation — or route through `UiMotion.replace()` to kill the previous.
6. **The node was freed mid-tween.** Godot handles this safely, but any callback chained after
   it never fires. If an exit sometimes fails to free its node, look for an earlier tween on
   the same node being killed.

`juice_test.gd` covers 1, 2, 3 and the callback half of 6 directly, which is why it is worth
running after a Godot version bump rather than only at install time.
