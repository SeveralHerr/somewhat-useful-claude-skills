class_name UiMotion
extends RefCounted

## Headless-safe UI animation helpers.
##
## Every function here answers the same question: how do I animate a Control without the
## animation becoming the reason a test fails? Godot's headless mode pumps no frames, so a
## tween created there never advances and never completes. Code that sets a label's text
## inside a tween callback therefore leaves the label empty forever — and the test that
## asserts on that text fails for a reason that has nothing to do with the logic it meant
## to check.
##
## The fix throughout is the same shape: try to animate, and if you cannot, apply the
## final value immediately. A headless run then ends in exactly the state a finished
## animation would have reached, just without the motion. That property is what makes a
## HUD testable at all.
##
## Everything is static and takes the host node, because these are used from CanvasLayers,
## Controls and RefCounted helpers alike.


## Master switch for ALL motion in the kit, this file included.
##
## It lives here rather than in the juice layer because this is the file every animated
## element already goes through — a switch that only covered the character layer would leave
## counters rolling and bars sliding with motion "off", and a headless assertion taken two
## frames after set_counter() would read a mid-roll number rather than the final one. Turning
## this off makes every function below apply its end state immediately, which is the same path
## a frameless run takes, so the disabled path is exercised by the tests rather than rotting.
static var enabled: bool = true

## Global multiplier on every duration here. 0.7 for snappy, 1.3 for languid.
static var speed: float = 1.0

## Where a punched Control's resting scale is remembered. See _rest_scale.
const REST_SCALE_META: StringName = &"ui_motion_rest_scale"
const WARNED_META: StringName = &"ui_motion_warned"


static func _t(seconds: float) -> float:
	return seconds * maxf(speed, 0.01)


## A tween, or null when the host cannot own one. Callers must handle null by snapping.
##
## `create_tween()` on a node outside the tree pushes an error and returns a dead tween, so
## the check has to happen here rather than at every call site.
static func tween(host: Node) -> Tween:
	if not enabled:
		return null
	if host == null or not is_instance_valid(host) or not host.is_inside_tree():
		return null
	return host.create_tween()


## True when motion is possible at all. Use it to skip building particles or timers that
## would otherwise leak in a frameless run.
static func can_animate(host: Node) -> bool:
	return enabled and host != null and is_instance_valid(host) and host.is_inside_tree()


## True when `c` owns its own transform — that is, when it is NOT a direct child of a
## Container.
##
## Container.fit_child_in_rect assigns its children's position, size, rotation AND scale on
## every layout pass, so a tween on any of those is silently overwritten before the frame is
## drawn. Nothing errors and the tween reports itself as running; the element simply never
## moves. Alpha is the exception — modulate is not a transform, so fading works anywhere.
##
## Anything you intend to scale, rotate or slide inside a Container layout has to be wrapped
## in a plain Control first: see transform_shell.
static func can_transform(c: Control) -> bool:
	return c != null and not (c.get_parent() is Container)


## Wrap `c` in a plain Control so it can be scaled inside a Container's layout, and return the
## wrapper to add to the container in its place.
##
## This is the escape hatch for the rule above, and it is worth using rather than accepting a
## dead punch: the shell is what the Container lays out (and resets), while `c` sits inside it
## at its own minimum size with its transform left alone. The shell's minimum size tracks the
## child's, so a row that grows — a counter reaching four digits — still reserves the space it
## needs.
##
## Call this BEFORE adding either node to the tree:
##     var row := PanelContainer.new()
##     ...
##     vbox.add_child(UiMotion.transform_shell(row))
static func transform_shell(c: Control) -> Control:
	var shell: Control = Control.new()
	shell.name = "%sShell" % c.name
	shell.mouse_filter = Control.MOUSE_FILTER_IGNORE
	shell.size_flags_horizontal = Control.SIZE_SHRINK_BEGIN
	shell.size_flags_vertical = Control.SIZE_SHRINK_BEGIN
	shell.add_child(c)
	shell.custom_minimum_size = c.get_combined_minimum_size()
	c.resized.connect(func() -> void:
		if is_instance_valid(shell) and is_instance_valid(c):
			shell.custom_minimum_size = c.size)
	return shell


## The scale a Control returns to after a punch, remembered on first use.
##
## Reading `scale` at punch time instead would compound: a second punch landing while the
## first is still settling would treat the inflated scale as the resting one and the element
## would creep. Snapping back to Vector2.ONE — the obvious alternative — is wrong for anything
## whose resting scale is not 1, which includes every element on a screen that UiTheme.fit has
## scaled for the display resolution.
static func _rest_scale(c: Control) -> Vector2:
	if c.has_meta(REST_SCALE_META):
		return c.get_meta(REST_SCALE_META) as Vector2
	c.set_meta(REST_SCALE_META, c.scale)
	return c.scale


## Complain once per node, so a refusal inside a per-frame call does not flood the log.
static func warn_once(c: Control, message: String) -> void:
	if c.has_meta(WARNED_META):
		return
	c.set_meta(WARNED_META, true)
	push_warning(message)


## Scale a Control up and let it settle back — the "something just happened here" beat.
## `amount` is a multiplier of the RESTING scale, not an absolute one.
##
## Sets pivot_offset from the current size every call rather than caching it, because a
## Control inside a container is resized after _ready and a stale pivot makes the punch
## visibly swing from a corner.
static func punch(node: Control, amount: float = 1.12, dur: float = 0.22) -> void:
	if node == null or not is_instance_valid(node):
		return
	var rest: Vector2 = _rest_scale(node)
	if not can_transform(node):
		# Refusing loudly rather than silently: the tint or text change that usually accompanies
		# a punch still lands, so a dead punch reads as "the animation is too subtle" and can
		# survive review for a long time. Wrap the node in transform_shell() to fix it.
		warn_once(node, "UiMotion.punch: %s is a Container child, so its scale is reset on " % node.name
			+ "every layout pass. Wrap it with UiMotion.transform_shell() to punch it.")
		return
	node.pivot_offset = node.size * 0.5
	var t: Tween = tween(node)
	if t == null:
		node.scale = rest
		return
	node.scale = rest * amount
	t.set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	t.tween_property(node, "scale", rest, _t(dur))


## Grow in from small with an overshoot. For anything that should feel like it arrived
## rather than appeared: reward cards, shouts, modal panels.
static func pop_in(node: Control, from_scale: float = 0.7, dur: float = 0.34) -> void:
	if node == null or not is_instance_valid(node):
		return
	var rest: Vector2 = _rest_scale(node)
	node.pivot_offset = node.size * 0.5
	node.visible = true
	var t: Tween = tween(node)
	if t == null:
		node.scale = rest
		node.modulate.a = 1.0
		return
	node.scale = rest * from_scale
	node.modulate.a = 0.0
	t.set_parallel(true)
	t.tween_property(node, "scale", rest, _t(dur)) \
		.set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	t.tween_property(node, "modulate:a", 1.0, _t(dur) * 0.55)


## Fade out and hide. `rise` lifts the node as it goes, which reads as "leaving" rather
## than "switching off".
static func fade_out(node: Control, dur: float = 0.28, rise: float = 0.0) -> void:
	if node == null or not is_instance_valid(node):
		return
	var t: Tween = tween(node)
	if t == null:
		node.modulate.a = 0.0
		node.visible = false
		return
	t.set_parallel(true)
	t.tween_property(node, "modulate:a", 0.0, _t(dur))
	if not is_zero_approx(rise):
		t.tween_property(node, "position:y", node.position.y - rise, _t(dur)) \
			.set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_OUT)
	t.chain().tween_callback(func() -> void:
		if is_instance_valid(node):
			node.visible = false)


## Count a number up (or down) instead of snapping it.
##
## Two details carry most of the value. First, duration scales with the distance travelled,
## so +1 is a tick and +5000 is an event — a fixed duration makes small changes feel sluggish
## and large ones feel instant. Second, the caller passes `from` explicitly: it should be the
## value currently DISPLAYED, not the model's previous value. Those diverge whenever two
## changes land inside one roll-up, and starting from the model makes the number visibly jump
## backwards before counting up again.
##
## `formatter` receives the in-flight float and returns the string to show, so thousands
## separators, currency symbols and "x12" all work without a second function.
static func count_to(
	host: Node,
	label: Label,
	from: float,
	to: float,
	formatter: Callable = Callable(),
	punch_at_end: bool = true
) -> Tween:
	if label == null or not is_instance_valid(label):
		return null
	var fmt: Callable = formatter if formatter.is_valid() else func(v: float) -> String:
		return str(int(round(v)))
	if is_equal_approx(from, to) or not can_animate(host):
		label.text = str(fmt.call(to))
		return null
	var t: Tween = tween(host)
	if t == null:
		label.text = str(fmt.call(to))
		return null
	var dur: float = _t(clampf(0.14 + absf(to - from) * 0.012, 0.18, 0.7))
	t.set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_OUT)
	t.tween_method(func(v: float) -> void:
		if is_instance_valid(label):
			label.text = str(fmt.call(v)), from, to, dur)
	if punch_at_end:
		t.tween_callback(func() -> void: punch(label, 1.08))
	return t


## Briefly tint a Control and return it to `base`. The generic "that was right / that was
## wrong" acknowledgement — pass a green or a red.
static func flash(node: Control, color: Color, base: Color = Color.WHITE, dur: float = 0.32) -> void:
	if node == null or not is_instance_valid(node):
		return
	var t: Tween = tween(node)
	if t == null:
		node.modulate = base
		return
	node.modulate = color
	t.tween_property(node, "modulate", base, _t(dur)).set_trans(Tween.TRANS_CUBIC)


## Drive a fill Control's anchor_right between 0 and 1. Anchors rather than size, so the bar
## keeps working when its track is resized by a container or a resolution change.
static func progress_to(host: Node, fill: Control, ratio: float, dur: float = 0.35) -> void:
	if fill == null or not is_instance_valid(fill):
		return
	var target: float = clampf(ratio, 0.0, 1.0)
	var t: Tween = tween(host)
	if t == null:
		fill.anchor_right = target
		return
	t.set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_OUT)
	t.tween_property(fill, "anchor_right", target, _t(dur))


## Kill a tween stored per-node so a new one can start cleanly.
##
## Without this, two rapid changes leave two tweens writing the same property and the value
## visibly stutters between them. Keyed by instance id rather than by the node so a freed
## node cannot keep a dictionary entry alive.
static func replace(store: Dictionary, node: Node, fresh: Tween) -> void:
	if node == null:
		return
	var key: int = node.get_instance_id()
	var previous: Tween = store.get(key, null) as Tween
	if previous != null and previous.is_valid():
		previous.kill()
	if fresh == null:
		store.erase(key)
	else:
		store[key] = fresh


## Thousands separators. "12,480" reads as a quantity; "12480.0" reads as a debug print.
static func group_digits(value: int) -> String:
	var negative: bool = value < 0
	var digits: String = str(absi(value))
	var out: String = ""
	var count: int = 0
	for i: int in range(digits.length() - 1, -1, -1):
		out = digits[i] + out
		count += 1
		if count % 3 == 0 and i > 0:
			out = "," + out
	return ("-" + out) if negative else out
