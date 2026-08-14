# Patterns worth copying by hand

For when you are adapting rather than scaffolding — a project with its own theme system, or
a piece that needs to behave differently from the template. Each section is self-contained.

- [The roll-up counter](#the-roll-up-counter)
- [The headless-safe tween](#the-headless-safe-tween)
- [The queued reward card](#the-queued-reward-card)
- [The escalating shout](#the-escalating-shout)
- [The two-shape prompt](#the-two-shape-prompt)
- [The vector glyph](#the-vector-glyph)
- [Circles, bars and pips without textures](#circles-bars-and-pips-without-textures)
- [Wiring a HUD to game state](#wiring-a-hud-to-game-state)

---

## The headless-safe tween

Everything else here depends on this. The rule: **try to animate, and if you cannot, apply
the final value immediately.**

```gdscript
static func tween(host: Node) -> Tween:
    if host == null or not is_instance_valid(host) or not host.is_inside_tree():
        return null
    return host.create_tween()
```

`create_tween()` on a node outside the tree pushes an error and hands back a dead tween, so
the check belongs here rather than at twenty call sites. Every caller then looks like:

```gdscript
var t: Tween = UiMotion.tween(self)
if t == null:
    node.modulate.a = 0.0        # the state the animation would have ended in
    node.visible = false
    return
t.tween_property(node, "modulate:a", 0.0, 0.3)
```

Why it matters: headless Godot pumps no frames. A tween created there never advances, so
anything set inside a tween callback never happens. A test asserting on that text fails for
a reason that has nothing to do with the code under test — which is worse than no test,
because it trains you to distrust the suite.

---

## The roll-up counter

```gdscript
static func count_to(
    host: Node, label: Label, from: float, to: float,
    formatter: Callable = Callable(), punch_at_end: bool = true
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
    # Duration scales with distance: +1 is a tick, +5000 is an event. A fixed duration
    # makes small changes feel sluggish and large ones feel instant.
    var dur: float = clampf(0.14 + absf(to - from) * 0.012, 0.18, 0.7)
    t.set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_OUT)
    t.tween_method(func(v: float) -> void:
        if is_instance_valid(label):
            label.text = str(fmt.call(v)), from, to, dur)
    if punch_at_end:
        t.tween_callback(func() -> void: punch(label, 1.08))
    return t
```

**The `from` argument is the whole trick.** Pass the value currently *displayed*, not the
model's previous value. Keep a `_shown` field per counter:

```gdscript
func set_stat(id: StringName, value: float) -> void:
    var entry: Dictionary = _stats[id]
    var from: float = entry["shown"]
    entry["shown"] = value
    UiMotion.replace(_tweens, entry["value"], UiMotion.count_to(self, entry["value"], from, value))
```

Without it, two changes landing inside one animation make the number jump backwards to the
model's old value and count up again — a visible stutter that looks like a bug.

`replace()` kills any in-flight tween on the same label first; otherwise two tweens write
the same property and the digits flicker between them. Key the store by
`node.get_instance_id()` rather than by the node, so a freed node cannot keep an entry
alive.

Formatters cover the rest without a second function:

```gdscript
hud.set_stat(&"cash",  v, func(x: float) -> String: return "$" + UiMotion.group_digits(int(x)))
hud.set_stat(&"combo", v, func(x: float) -> String: return "x%d" % int(x))
hud.set_stat(&"items", v, func(x: float) -> String: return "%d/%d" % [int(x), total])
```

---

## The queued reward card

The payoff moment of a collection game. Two rules: it is a *card*, not a line of text; and
cards queue rather than interrupt.

```gdscript
func show_card(kicker: String, title: String, subtitle: String, body: String, accent: Color) -> void:
    _card_queue.append({...})
    if not _card_busy:
        _drain_cards()

func _drain_cards() -> void:
    if _card_queue.is_empty():
        _card_busy = false
        return
    _card_busy = true
    var d: Dictionary = _card_queue.pop_front()
    # ... fill labels, tint the border with the accent ...
    _card.position.y = CARD_Y + 24.0
    UiMotion.pop_in(_card, 0.72, 0.34)
    var t: Tween = UiMotion.tween(self)
    if t == null:
        _card.visible = false
        _drain_cards()          # still drain, or a headless run wedges the queue forever
        return
    t.tween_property(_card, "position:y", CARD_Y, 0.34) \
        .set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
    t.tween_interval(CARD_HOLD)
    t.tween_callback(func() -> void: UiMotion.fade_out(_card, 0.3, 30.0))
    t.tween_interval(0.32)
    t.tween_callback(_drain_cards)
```

The null branch still calls `_drain_cards()`. Skipping it leaves `_card_busy` true forever
and every later card is silently swallowed — a bug that only appears headless, i.e. only in
tests, i.e. exactly where it is hardest to read.

Card anatomy, in order of type size: **kicker** (tiny, uppercase, faint — "ITEM FOUND"),
**title** (large — the name), **subtitle** (accent-coloured — rarity or category), **body**
(small, dim — one line of flavour). The accent tints the border as well as the subtitle, so
rarity is legible peripherally before any text is read.

---

## The escalating shout

Combo and streak feedback. The point is that a big moment cannot be mistaken for a small
one, so emphasis drives size, tilt and overshoot together:

```gdscript
func shout(text: String, color: Color, emphasis: float = 0.5) -> void:
    var e: float = clampf(emphasis, 0.0, 1.0)
    _shout.text = text
    UiTheme.style_label(_shout, int(UiTheme.FS_SHOUT * (0.72 + e * 0.5)), color)
    _shout.rotation = randf_range(-0.05, 0.05) * e
    UiMotion.pop_in(_shout, 0.55 - e * 0.2, 0.26)
    var t: Tween = UiMotion.tween(self)
    if t == null:
        _shout.visible = false
        return
    t.tween_interval(0.45 + e * 0.35)
    t.tween_callback(func() -> void: UiMotion.fade_out(_shout, 0.3, 40.0))
```

Keep the ladder of shout strings in game state, not in the HUD — the HUD should not know
what a combo is. Have the game return `""` when there is nothing to shout, and make
`shout("")` a no-op, so the caller never needs a conditional.

A small random tilt per shout is worth more than it sounds: identical repeated feedback
starts reading as a static overlay, and a couple of degrees of variance keeps it alive.

---

## The two-shape prompt

```gdscript
func set_prompt(text: String) -> void:
    if text.strip_edges().is_empty():
        _prompt_box.visible = false
        return
    _prompt_box.visible = true
    var key: String = ""
    var body: String = text
    var open: int = text.find("[")
    var close: int = text.find("]")
    if open >= 0 and close > open + 1:
        key = text.substr(open + 1, close - open - 1)
        body = text.substr(close + 1).strip_edges()
        _prompt_prefix.text = text.substr(0, open).strip_edges()
    _key_chip.visible = not key.is_empty()
    _prompt_prefix.visible = not key.is_empty() and not _prompt_prefix.text.is_empty()
    _key_label.text = key
    _prompt_label.text = body
    _prompt_label.add_theme_color_override(
        "font_color", UiTheme.TEXT if not key.is_empty() else UiTheme.TEXT_DIM)
```

`"Press [E] to open"` renders as prefix + keycap + body. `"It's locked"` renders as a dimmed
status line with no keycap. One function, and the caller passes whichever it has.

The reason to bother: a keycap in front of a refusal message is an instruction to press the
key that just failed. Players do press it, repeatedly, and conclude the game is broken.

---

## The vector glyph

```gdscript
class Glyph extends Control:
    enum Kind { CIRCLE, STAR, COIN, HEART, SHIELD, BOLT, CLOCK, KEY }

    var kind: Kind = Kind.CIRCLE
    var color: Color = Color.WHITE

    func _init(kind_in: Kind, color_in: Color, size_in: float = 24.0) -> void:
        kind = kind_in
        color = color_in
        custom_minimum_size = Vector2(size_in, size_in)
        mouse_filter = Control.MOUSE_FILTER_IGNORE
        size_flags_vertical = Control.SIZE_SHRINK_CENTER

    func set_color(c: Color) -> void:
        color = c
        queue_redraw()

    ## Author in normalised 0..1 space so one glyph works at any size.
    func _p(x: float, y: float) -> Vector2:
        return Vector2(x * size.x, y * size.y)

    func _draw() -> void:
        # A Control that has not been laid out yet has zero size, and drawing into it
        # produces NaNs rather than an empty icon.
        if size.x <= 1.0 or size.y <= 1.0:
            return
        var u: float = minf(size.x, size.y)
        match kind:
            Kind.STAR:
                draw_colored_polygon(PackedVector2Array([
                    _p(0.50, 0.02), _p(0.61, 0.39), _p(0.98, 0.50), _p(0.61, 0.61),
                    _p(0.50, 0.98), _p(0.39, 0.61), _p(0.02, 0.50), _p(0.39, 0.39),
                ]), color)
            Kind.HEART:
                draw_circle(_p(0.32, 0.36), u * 0.22, color)
                draw_circle(_p(0.68, 0.36), u * 0.22, color)
                draw_colored_polygon(PackedVector2Array([
                    _p(0.10, 0.44), _p(0.90, 0.44), _p(0.50, 0.95)]), color)
```

Three or four primitives is the budget. Past that the glyph stops reading at small sizes
anyway and wants to be a real asset.

`set_color()` + `queue_redraw()` means one node can express changing state — a combo icon
that heats from white through gold to red — with no extra assets and no swap logic.

To draw text inside a glyph (a `$`, a `%`), use `ThemeDB.fallback_font`; it always exists,
so the icon never depends on a font file:

```gdscript
var font: Font = ThemeDB.fallback_font
if font != null:
    var fs: int = int(u * 0.66)
    var w: float = font.get_string_size("$", HORIZONTAL_ALIGNMENT_LEFT, -1, fs).x
    draw_string(font, Vector2(size.x * 0.5 - w * 0.5, size.y * 0.5 + float(fs) * 0.36),
        "$", HORIZONTAL_ALIGNMENT_LEFT, -1, fs, color)
```

---

## Circles, bars and pips without textures

A perfect circle is a square `StyleBoxFlat` with an absurd corner radius:

```gdscript
static func circle_box(fill: Color, border: Color = Color(0,0,0,0), border_width: int = 0) -> StyleBoxFlat:
    var box: StyleBoxFlat = StyleBoxFlat.new()
    box.bg_color = fill
    box.set_corner_radius_all(64)      # any value >= half the node's size
    box.set_border_width_all(border_width)
    box.border_color = border
    box.anti_aliasing = true
    return box
```

That single function covers crosshair rings, crosshair dots, status pips, collection chips
and ability cooldown discs — every round element in a HUD, with no art.

Progress bars: nest a fill `Panel` in a track `Panel` and tween the fill's **`anchor_right`**
between 0 and 1, not its `size`. Anchors keep working when a container or a resolution
change resizes the track; a tweened size silently desynchronises.

---

## Wiring a HUD to game state

Push, never pull. The HUD exposes setters; the game calls them when something changes. A
HUD that reaches into game state each frame couples the two permanently and re-renders
constantly for no reason.

```gdscript
GameState.score_changed.connect(func(v: int) -> void: hud.set_stat(&"score", v))
GameState.carry_changed.connect(hud.set_counter)
GameState.item_found.connect(func(item: ItemType) -> void:
    hud.show_card("item found", item.display_name, item.rarity_name(), item.flavour, item.rarity_color()))
```

Resolve the game-state singleton defensively inside the HUD if it reads anything on its own:

```gdscript
var _state: Node = get_node_or_null("/root/GameState")
```

Using the autoload identifier directly makes a missing autoload a hard runtime error; a
`null` you can guard makes it a failing assertion with a readable message instead. That is
the difference between a test that tells you what broke and one that just breaks.
