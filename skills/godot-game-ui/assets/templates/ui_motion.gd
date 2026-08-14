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


## A tween, or null when the host cannot own one. Callers must handle null by snapping.
##
## `create_tween()` on a node outside the tree pushes an error and returns a dead tween, so
## the check has to happen here rather than at every call site.
static func tween(host: Node) -> Tween:
	if host == null or not is_instance_valid(host) or not host.is_inside_tree():
		return null
	return host.create_tween()


## True when motion is possible at all. Use it to skip building particles or timers that
## would otherwise leak in a frameless run.
static func can_animate(host: Node) -> bool:
	return host != null and is_instance_valid(host) and host.is_inside_tree()


## Scale a Control up and let it settle back — the "something just happened here" beat.
##
## Sets pivot_offset from the current size every call rather than caching it, because a
## Control inside a container is resized after _ready and a stale pivot makes the punch
## visibly swing from a corner.
static func punch(node: Control, amount: float = 1.12, dur: float = 0.22) -> void:
	if node == null or not is_instance_valid(node):
		return
	node.pivot_offset = node.size * 0.5
	var t: Tween = tween(node)
	if t == null:
		node.scale = Vector2.ONE
		return
	node.scale = Vector2(amount, amount)
	t.set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	t.tween_property(node, "scale", Vector2.ONE, dur)


## Grow in from small with an overshoot. For anything that should feel like it arrived
## rather than appeared: reward cards, shouts, modal panels.
static func pop_in(node: Control, from_scale: float = 0.7, dur: float = 0.34) -> void:
	if node == null or not is_instance_valid(node):
		return
	node.pivot_offset = node.size * 0.5
	node.visible = true
	var t: Tween = tween(node)
	if t == null:
		node.scale = Vector2.ONE
		node.modulate.a = 1.0
		return
	node.scale = Vector2(from_scale, from_scale)
	node.modulate.a = 0.0
	t.set_parallel(true)
	t.tween_property(node, "scale", Vector2.ONE, dur) \
		.set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	t.tween_property(node, "modulate:a", 1.0, dur * 0.55)


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
	t.tween_property(node, "modulate:a", 0.0, dur)
	if not is_zero_approx(rise):
		t.tween_property(node, "position:y", node.position.y - rise, dur) \
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
	var dur: float = clampf(0.14 + absf(to - from) * 0.012, 0.18, 0.7)
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
	t.tween_property(node, "modulate", base, dur).set_trans(Tween.TRANS_CUBIC)


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
	t.tween_property(fill, "anchor_right", target, dur)


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
