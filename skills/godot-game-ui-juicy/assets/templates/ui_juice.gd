class_name UiJuice
extends RefCounted

## The motion layer: entrances, exits, staggers, punches, shakes and flashes.
##
## UiMotion (unchanged from the plain kit) owns the *safety* rules — tween-or-snap, roll-up
## numbers, replace-don't-stack. UiJuice sits on top and owns the *character*: how a panel
## arrives, how fast it leaves, in what order its children appear. Keeping them apart matters
## because they change for different reasons. You retune juice constantly while a game finds
## its feel; you touch the safety rules almost never.
##
## ============================================================================
## TUNING: the FEEL block below is the whole personality. Start there.
## ============================================================================
##
## Three ideas run through everything here, and they are worth understanding rather than
## copying:
##
## 1. ENTRANCES OVERSHOOT, EXITS DO NOT. An element that arrives past its resting size and
##    settles back reads as physical. The same curve on the way out reads as hesitation —
##    the player has already decided, and anything that delays the decision feels like lag.
##    So exits are roughly a third the duration of entrances and use a plain accelerating
##    curve. This asymmetry is most of what separates "animated" from "juicy".
##
## 2. THINGS ARRIVE IN SEQUENCE, NOT TOGETHER. Four buttons fading in together is one event.
##    The same four at 45ms apart is a menu assembling itself, and it costs one delay
##    parameter. Keep the step small — past ~80ms it stops reading as one motion and starts
##    reading as a slow interface.
##
## 3. MOTION MUST BE OPTIONAL. `UiJuice.enabled = false` makes every function here apply its
##    final state instantly. Some players need that, some builds need deterministic frames,
##    and a codebase where motion cannot be turned off has to be edited in a hundred places
##    the first time someone asks.

# ------------------------------------------------------------------- FEEL (tune here)

## Master switch. False makes every animation below resolve instantly to its end state —
## the same path a headless run takes, so it is exercised by the tests rather than rotting.
static var enabled: bool = true

## Global multiplier on every duration. 0.7 for a snappy arcade feel, 1.3 for a languid one.
static var speed: float = 1.0

const IN_TIME: float = 0.34
## Deliberately about a third of IN_TIME. See idea 1 above.
const OUT_TIME: float = 0.13
const STAGGER_STEP: float = 0.045
const PUNCH_TIME: float = 0.26
const SHAKE_TIME: float = 0.32

## How far below its resting place a rising element starts, and how small a popping one does.
const RISE_DISTANCE: float = 34.0
const POP_FROM: float = 0.86
## Exits shrink rather than grow: growing on the way out reads as an accident.
const POP_TO: float = 0.94

enum Enter { POP, RISE, DROP }


static func _t(seconds: float) -> float:
	return seconds * maxf(speed, 0.01)


## Every animation here starts by asking for a tween through this, so the disabled path and
## the headless path are the same path.
##
## `unpausable` is the one that will bite you. A Tween's default pause mode is BOUND, meaning
## it follows the process mode of the node it was created on — so a pause menu animating
## itself in while `get_tree().paused` is true freezes on its first frame unless every node
## involved is PROCESS_MODE_ALWAYS. Passing true here sets TWEEN_PAUSE_PROCESS and the
## animation runs regardless, which is what you want for anything that is *part of* the
## pause UI rather than part of the paused game.
static func tween(host: Node, unpausable: bool = false) -> Tween:
	if not enabled:
		return null
	var t: Tween = UiMotion.tween(host)
	if t == null:
		return null
	if unpausable:
		t.set_pause_mode(Tween.TWEEN_PAUSE_PROCESS)
	return t


## Keep a Control's scale pivot at its centre, permanently.
##
## Setting pivot_offset once is the classic scale-animation bug: a Control inside a Container
## is laid out *after* _ready, so the pivot you set was computed against a size of zero and
## the element visibly swings out from its top-left corner. Connecting to `resized` instead
## means the pivot is right on every frame the layout changes, including the very first one
## and including a window resize mid-animation.
static func center_pivot(c: Control) -> void:
	if c == null:
		return
	c.pivot_offset = c.size * 0.5
	if c.has_meta(&"ui_juice_pivot"):
		return
	c.set_meta(&"ui_juice_pivot", true)
	c.resized.connect(func() -> void:
		if is_instance_valid(c):
			c.pivot_offset = c.size * 0.5)


# ------------------------------------------------------------------------ entrances

## Animate `target` in. Safe to call in _ready — the pivot tracking above handles the fact
## that the layout has not happened yet.
static func enter(host: Node, target: Control, style: Enter = Enter.POP, delay: float = 0.0) -> void:
	if target == null:
		return
	if style == Enter.POP and not can_transform(target):
		# Fall back rather than animate a property that will be overwritten before it is
		# drawn — a silent no-op here looks like the tween never ran.
		push_warning("UiJuice.enter: %s is a Container child, so its scale is reset every " % target.name
			+ "layout pass. Anchor it instead, or it will only fade.")
	center_pivot(target)
	var rest: Vector2 = target.position
	var rest_scale: Vector2 = target.scale

	var t: Tween = tween(host, true)
	if t == null:
		_settle(target, rest, rest_scale)
		return

	# The start state is applied only now that a tween definitely exists. Arming first and
	# discovering afterwards that nothing can animate is how a headless run ends up with an
	# invisible UI that no assertion explains.
	target.modulate.a = 0.0
	match style:
		Enter.POP:
			target.scale = rest_scale * POP_FROM
		Enter.RISE:
			target.position = rest + Vector2(0.0, RISE_DISTANCE)
		Enter.DROP:
			target.position = rest - Vector2(0.0, RISE_DISTANCE)

	t.set_parallel(true)
	t.tween_property(target, "modulate:a", 1.0, _t(IN_TIME) * 0.7).set_delay(delay)
	if style == Enter.POP:
		t.tween_property(target, "scale", rest_scale, _t(IN_TIME)) \
			.set_delay(delay).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	else:
		t.tween_property(target, "position", rest, _t(IN_TIME)) \
			.set_delay(delay).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)


## True when `c`'s transform is its own — that is, when it is NOT a direct child of a
## Container.
##
## This is the single most surprising rule in Godot UI animation. Container.fit_child_in_rect
## sets its children's position, size, rotation AND scale every time it lays out, so a tween
## on any of those properties is silently overwritten before the frame is drawn. Nothing
## errors. The tween reports itself as running. The element simply never moves, and you go
## looking for the bug in your easing curves.
##
## Anything you intend to scale, rotate or slide therefore has to be anchored rather than
## parented to a Container — or wrapped in a plain Control that the Container lays out while
## the wrapped child moves freely inside it. Alpha is the exception: modulate is not a
## transform, so fading works anywhere.
static func can_transform(c: Control) -> bool:
	return c != null and not (c.get_parent() is Container)


## Animate a list of Controls in one after another.
##
## Container children get a fade only, everything else gets fade plus pop. That split is not
## a compromise — it is the only correct behaviour given the rule above, and doing it here
## means callers can pass `some_vbox.get_children()` without first knowing which of these
## cases they are in. A staggered fade still reads as a sequence; it is the timing that
## carries the effect, not the scale.
static func stagger(
	host: Node, nodes: Array, step: float = STAGGER_STEP, delay: float = 0.0
) -> void:
	var controls: Array[Control] = []
	for n: Variant in nodes:
		var c: Control = n as Control
		if c != null:
			controls.append(c)
	if controls.is_empty():
		return

	var t: Tween = tween(host, true)
	if t == null:
		for c: Control in controls:
			_settle(c, c.position, c.scale)
		return

	t.set_parallel(true)
	var i: int = 0
	for c: Control in controls:
		var d: float = delay + step * float(i)
		i += 1
		c.modulate.a = 0.0
		t.tween_property(c, "modulate:a", 1.0, _t(IN_TIME) * 0.6).set_delay(d)
		if not can_transform(c):
			continue
		center_pivot(c)
		var rest_scale: Vector2 = c.scale
		c.scale = rest_scale * POP_FROM
		t.tween_property(c, "scale", rest_scale, _t(IN_TIME)) \
			.set_delay(d).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)


# ---------------------------------------------------------------------------- exits

## Animate `target` out, then call `done`. Fast, shrinking, no overshoot — see idea 1.
##
## `done` runs immediately when there is nothing to animate, so a caller that frees itself in
## the callback behaves identically headless. That property is what makes exits testable:
## the assertion is "the node is gone", not "the node is gone eventually".
static func exit_then(host: Node, target: Control, done: Callable = Callable()) -> void:
	if target == null:
		if done.is_valid():
			done.call()
		return
	center_pivot(target)

	var t: Tween = tween(host, true)
	if t == null:
		if done.is_valid():
			done.call()
		return

	# Relative to the resting scale, never to 1.0. A screen that scales itself for the display
	# resolution is already at, say, 0.6 — snapping it to 1.0 to "shrink" it would make it
	# lurch to full size first, which is the opposite of the intended motion.
	t.set_parallel(true)
	t.tween_property(target, "modulate:a", 0.0, _t(OUT_TIME))
	t.tween_property(target, "scale", target.scale * POP_TO, _t(OUT_TIME)) \
		.set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_IN)
	if done.is_valid():
		t.set_parallel(false)
		t.tween_callback(done)


# --------------------------------------------------------------------------- accents

## Squash-and-stretch punch: wider than it is tall on the way out, then settle.
##
## The non-uniform scale is the entire point. A uniform punch reads as "this got bigger";
## an anisotropic one reads as something absorbing an impact, which is what you actually want
## when a counter ticks or a slot is selected.
static func punch(host: Node, target: Control, amount: float = 0.16) -> void:
	if target == null or not can_transform(target):
		return
	center_pivot(target)
	var rest: Vector2 = target.scale
	var t: Tween = tween(host, true)
	if t == null:
		return
	target.scale = Vector2(rest.x * (1.0 + amount), rest.y * (1.0 - amount * 0.6))
	t.tween_property(target, "scale", rest, _t(PUNCH_TIME)) \
		.set_trans(Tween.TRANS_ELASTIC).set_ease(Tween.EASE_OUT)


## Decaying positional shake. Use sparingly and briefly — a shake that outlasts the event it
## describes stops meaning "impact" and starts meaning "the UI is broken".
static func shake(host: Node, target: Control, strength: float = 9.0, time: float = SHAKE_TIME) -> void:
	if target == null:
		return
	var rest: Vector2 = target.position
	var t: Tween = tween(host, true)
	if t == null:
		target.position = rest
		return
	var steps: int = 6
	for i: int in range(steps):
		var falloff: float = 1.0 - (float(i) / float(steps))
		var offset: Vector2 = Vector2(
			randf_range(-strength, strength) * falloff,
			randf_range(-strength, strength) * falloff * 0.6
		)
		t.tween_property(target, "position", rest + offset, _t(time) / float(steps))
	t.tween_property(target, "position", rest, _t(time) / float(steps))


## Full-screen colour pulse on its own layer. Returns the layer so a caller can keep it for
## repeated hits instead of building one per flash.
static func flash(host: Node, color: Color = Color(1, 1, 1, 0.5), time: float = 0.22) -> CanvasLayer:
	var layer: CanvasLayer = CanvasLayer.new()
	layer.layer = 128
	layer.process_mode = Node.PROCESS_MODE_ALWAYS
	var rect: ColorRect = ColorRect.new()
	rect.color = color
	rect.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	rect.mouse_filter = Control.MOUSE_FILTER_IGNORE
	layer.add_child(rect)
	host.add_child(layer)

	var t: Tween = tween(host, true)
	if t == null:
		layer.queue_free()
		return layer
	t.tween_property(rect, "color:a", 0.0, _t(time))
	t.tween_callback(layer.queue_free)
	return layer


## Slow looping scale, for a screen that would otherwise sit perfectly still. A title that
## never moves reads as a frozen build; this is the cheapest possible signal of life.
static func breathe(host: Node, target: Control, amount: float = 0.02, period: float = 2.6) -> void:
	if target == null or not can_transform(target):
		return
	center_pivot(target)
	var rest: Vector2 = target.scale
	var t: Tween = tween(host, true)
	if t == null:
		return
	t.set_loops()
	t.tween_property(target, "scale", rest * (1.0 + amount), period * 0.5) \
		.set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
	t.tween_property(target, "scale", rest, period * 0.5) \
		.set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)


## The state every animation above is required to reach when it cannot run.
static func _settle(c: Control, rest: Vector2, rest_scale: Vector2 = Vector2.ONE) -> void:
	c.modulate.a = 1.0
	c.scale = rest_scale
	c.position = rest
