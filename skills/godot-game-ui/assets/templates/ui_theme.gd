class_name UiTheme
extends RefCounted

## Every colour, font size and StyleBox the UI uses, built in code.
##
## Why code rather than a .tres Theme resource: the whole art direction of a UI like this is
## a few dozen numbers. Keeping them in one script means a palette change is a diff a human
## can read and a reviewer can argue with, and it removes a binary resource that everyone
## touching the UI would otherwise have to merge. It also means no part of the UI depends on
## an asset pipeline — useful early, when there is no art yet, and still useful later.
##
## ============================================================================
## RE-SKINNING: change the PALETTE and TYPE blocks below. Nothing else.
## ============================================================================
## Every function derives from those constants, so a horror game and a candy-coloured
## puzzler differ by one block. Resist scattering literal colours into screen scripts — the
## moment two places know the accent colour, they drift.

# ------------------------------------------------------------------ PALETTE (re-skin here)

## The one colour the eye should track: selected states, primary buttons, the rarest reward.
const ACCENT: Color = Color(1.0, 0.76, 0.24)
const ACCENT_DEEP: Color = Color(0.72, 0.51, 0.16)

const TEXT: Color = Color(0.96, 0.93, 0.88)
const TEXT_DIM: Color = Color(0.76, 0.72, 0.68)
const TEXT_FAINT: Color = Color(0.62, 0.58, 0.55)

## Panels are translucent so the game stays visible behind the UI. Fully opaque chrome makes
## a HUD feel like a separate application bolted on top of the game.
const PANEL_FILL: Color = Color(0.05, 0.04, 0.06, 0.68)
const PANEL_FILL_DEEP: Color = Color(0.06, 0.05, 0.07, 0.88)
const PANEL_BORDER: Color = Color(1.0, 0.93, 0.84, 0.11)
const BACKDROP: Color = Color(0.06, 0.05, 0.07, 0.86)

## High-contrast light chip, for keycaps and anything that must read as physical.
const CHIP_FILL: Color = Color(0.93, 0.90, 0.86, 0.92)

const GOOD: Color = Color(0.44, 0.83, 0.45)
const BAD: Color = Color(0.96, 0.36, 0.33)

const SHADOW: Color = Color(0.0, 0.0, 0.0, 0.45)
const OUTLINE: Color = Color(0.03, 0.02, 0.04, 0.85)

# --------------------------------------------------------------------- TYPE (re-skin here)

## Sizes are named by importance, not by role. A HUD has one visual hierarchy, and tying
## sizes to roles ("stat font", "label font") is how six near-identical sizes appear.
const FS_HUGE: int = 62
const FS_SHOUT: int = 60
const FS_TITLE: int = 48
const FS_HEADING: int = 30
const FS_BODY: int = 24
const FS_SMALL: int = 20
const FS_TINY: int = 15

# ------------------------------------------------------------------ METRICS (re-skin here)

const PILL_RADIUS: int = 12
const CARD_RADIUS: int = 20
const SLOT_SIZE: float = 62.0
const ICON_SIZE: float = 24.0

## One safe-area inset for every screen edge. Shared so the top-left stack, the bottom bar
## and the counter cannot drift apart — inconsistent edge margins are the most visible way
## a HUD looks unfinished, and they happen when each region picks its own number.
const MARGIN: float = 32.0

# --------------------------------------------------------------- RESOLUTION (re-skin here)

## The design resolution every pixel metric above is authored against. The UI is scaled by
## viewport_height / REFERENCE_HEIGHT, so it occupies the same fraction of the screen at
## 720p, 1080p and 4K instead of shrinking into a corner on big displays.
##
## Height, not width, and not a diagonal: on a 21:9 ultrawide you want the UI the same size
## it is on 16:9 and merely spread further apart, not inflated. Driving off height gives
## that for free — the extra width just moves the anchored edges outward.
const REFERENCE_HEIGHT: float = 1080.0
const MIN_UI_SCALE: float = 0.5
const MAX_UI_SCALE: float = 2.5


static func ui_scale(viewport_height: float) -> float:
	if viewport_height <= 0.0:
		return 1.0
	return clampf(viewport_height / REFERENCE_HEIGHT, MIN_UI_SCALE, MAX_UI_SCALE)


## Scale `host` and resize `root` so the UI covers the viewport at the right apparent size.
##
## `host` is whatever carries the scale — a CanvasLayer for the HUD and pause overlay, or the
## screen Control itself for title/results. `root` is the full-rect Control that owns the
## rectangle everything else anchors inside; it is sized to viewport/scale so that after the
## scale is applied its edges land exactly on the real viewport edges.
##
## Works under either stretch mode, which is the point. With stretch disabled the visible
## rect is real pixels and this does all the adapting. With stretch/canvas_items the visible
## rect is the constant base size, so this contributes a constant factor and the engine
## supplies the rest — the two compose to the same on-screen result either way.
##
## Returns 1.0 and touches nothing when there is no viewport yet, so a HUD built before it
## enters the tree — or asserted against in a headless test — keeps its plain anchored layout.
static func fit(host: Node, root: Control) -> float:
	if root == null:
		return 1.0
	var vp: Viewport = root.get_viewport()
	if vp == null:
		return 1.0
	var rect: Vector2 = vp.get_visible_rect().size
	if rect.x <= 0.0 or rect.y <= 0.0:
		return 1.0

	var s: float = ui_scale(rect.y)
	# Anchors have to be released first: a FULL_RECT control recomputes its own size from the
	# parent every layout pass and would immediately overwrite the size set below.
	root.set_anchors_preset(Control.PRESET_TOP_LEFT)
	root.pivot_offset = Vector2.ZERO
	root.position = Vector2.ZERO
	root.size = rect / s

	if host is CanvasLayer:
		(host as CanvasLayer).scale = Vector2(s, s)
	elif host is Control:
		var c: Control = host as Control
		c.pivot_offset = Vector2.ZERO
		c.scale = Vector2(s, s)
	return s

# ------------------------------------------------------------------------------ styleboxes

## The workhorse pill: stat rows, prompts, held-item strips, anything that is a small
## floating readout rather than a modal surface.
static func pill_box(
	fill: Color = PANEL_FILL,
	radius: int = PILL_RADIUS,
	border: Color = PANEL_BORDER,
	border_width: int = 1
) -> StyleBoxFlat:
	var box: StyleBoxFlat = StyleBoxFlat.new()
	box.bg_color = fill
	box.set_corner_radius_all(radius)
	box.set_border_width_all(border_width)
	box.border_color = border
	box.set_content_margin_all(8.0)
	box.content_margin_left = 12.0
	box.content_margin_right = 14.0
	box.shadow_color = Color(0.0, 0.0, 0.0, 0.28)
	box.shadow_size = 6
	box.shadow_offset = Vector2(0.0, 2.0)
	return box


## Keycap. Light fill and a dark hairline so it reads as a physical key even at 20px.
static func key_chip_box() -> StyleBoxFlat:
	var box: StyleBoxFlat = StyleBoxFlat.new()
	box.bg_color = CHIP_FILL
	box.set_corner_radius_all(6)
	box.set_content_margin_all(4.0)
	box.content_margin_left = 10.0
	box.content_margin_right = 10.0
	box.set_border_width_all(1)
	box.border_color = Color(0.0, 0.0, 0.0, 0.25)
	return box


## Reward/announcement card: heavier fill, accent-tinted border, a real drop shadow. It has
## to read as an object sitting in front of the game rather than as another HUD pill, and
## the shadow is what does that.
static func card_box(accent: Color = ACCENT) -> StyleBoxFlat:
	var box: StyleBoxFlat = StyleBoxFlat.new()
	box.bg_color = PANEL_FILL_DEEP
	box.set_corner_radius_all(CARD_RADIUS)
	box.set_border_width_all(2)
	box.border_color = Color(accent.r, accent.g, accent.b, 0.85)
	box.set_content_margin_all(0.0)
	box.shadow_color = Color(0.0, 0.0, 0.0, 0.55)
	box.shadow_size = 22
	box.shadow_offset = Vector2(0.0, 8.0)
	return box


## Modal surface for shell screens (pause, settings, results).
static func panel_box(radius: int = 18) -> StyleBoxFlat:
	var box: StyleBoxFlat = StyleBoxFlat.new()
	box.bg_color = PANEL_FILL_DEEP
	box.set_corner_radius_all(radius)
	box.set_border_width_all(1)
	box.border_color = PANEL_BORDER
	box.set_content_margin_all(22.0)
	box.content_margin_left = 28.0
	box.content_margin_right = 28.0
	return box


## Flat rule; also the progress track and its fill.
static func bar_box(fill: Color, radius: int = 3) -> StyleBoxFlat:
	var box: StyleBoxFlat = StyleBoxFlat.new()
	box.bg_color = fill
	box.set_corner_radius_all(radius)
	box.set_content_margin_all(0.0)
	return box


## A perfect circle is a square box with an absurd corner radius. Crosshair rings, dots and
## status pips all come from this, so none of them need a texture.
static func circle_box(
	fill: Color, border: Color = Color(0, 0, 0, 0), border_width: int = 0
) -> StyleBoxFlat:
	var box: StyleBoxFlat = StyleBoxFlat.new()
	box.bg_color = fill
	box.set_corner_radius_all(64)
	box.set_border_width_all(border_width)
	box.border_color = border
	box.set_content_margin_all(0.0)
	box.anti_aliasing = true
	return box


## Inventory/tool slot. The active state changes BOTH border and fill, because the
## difference has to survive being glanced at in peripheral vision — a border-only
## highlight disappears the moment the player is looking at the middle of the screen.
static func slot_box(active: bool) -> StyleBoxFlat:
	var box: StyleBoxFlat = StyleBoxFlat.new()
	box.bg_color = Color(0.09, 0.07, 0.09, 0.80) if active else Color(0.05, 0.04, 0.06, 0.62)
	box.set_corner_radius_all(14)
	box.set_border_width_all(2 if active else 1)
	box.border_color = ACCENT if active else PANEL_BORDER
	box.set_content_margin_all(6.0)
	box.shadow_color = Color(0.0, 0.0, 0.0, 0.30)
	box.shadow_size = 5
	box.shadow_offset = Vector2(0.0, 2.0)
	return box


static func badge_box(active: bool) -> StyleBoxFlat:
	var box: StyleBoxFlat = StyleBoxFlat.new()
	box.bg_color = ACCENT if active else Color(0.10, 0.09, 0.11, 0.88)
	box.set_corner_radius_all(5)
	box.set_content_margin_all(1.0)
	box.content_margin_left = 6.0
	box.content_margin_right = 6.0
	box.set_border_width_all(1)
	box.border_color = Color(0.0, 0.0, 0.0, 0.35) if active else PANEL_BORDER
	return box


static func button_box(fill: Color, radius: int = 12) -> StyleBoxFlat:
	var box: StyleBoxFlat = StyleBoxFlat.new()
	box.bg_color = fill
	box.set_corner_radius_all(radius)
	box.content_margin_left = 26.0
	box.content_margin_right = 26.0
	box.content_margin_top = 14.0
	box.content_margin_bottom = 14.0
	return box

# ---------------------------------------------------------------------------------- text

## One call so no label anywhere forgets its outline.
##
## Game UI sits over an unpredictable, often bright, often moving background. That is the
## single most common way a good-looking HUD becomes unreadable in play but not in a
## mockup. A drop shadow alone fails against a bright background; an outline alone looks
## flat. Both together survive anything, which is why this is one function rather than a
## style guideline nobody applies consistently.
static func style_label(
	label: Label, font_size: int, color: Color = TEXT, outlined: bool = true
) -> void:
	if label == null:
		return
	label.add_theme_font_size_override("font_size", font_size)
	label.add_theme_color_override("font_color", color)
	label.add_theme_color_override("font_shadow_color", SHADOW)
	# The drop scales with the type, because it is a fixed pixel offset and the small sizes
	# cannot absorb it: a 2px shadow under a 9px glyph fills the counter of every letter and
	# the word reads as struck through. The shadow never goes away though — see the comment
	# above about outline AND shadow both being needed over live gameplay.
	var small: bool = font_size < 14
	label.add_theme_constant_override("shadow_offset_x", 0 if small else 1)
	label.add_theme_constant_override("shadow_offset_y", 1 if small else 2)
	label.add_theme_constant_override("shadow_outline_size", 1)
	if outlined:
		label.add_theme_color_override("font_outline_color", OUTLINE)
		label.add_theme_constant_override("outline_size", maxi(4, int(font_size / 7)))
	else:
		label.add_theme_constant_override("outline_size", 0)


## Buttons carry their own styleboxes rather than inheriting a shared Theme, so one screen
## can mix an accent primary action with muted secondaries without fighting inheritance.
static func style_button(b: Button, primary: bool = false, min_width: float = 320.0) -> void:
	if b == null:
		return
	var base: Color = Color(0.20, 0.19, 0.22, 0.95)
	var hover: Color = Color(0.28, 0.26, 0.30, 1.0)
	var press: Color = Color(0.16, 0.15, 0.18, 1.0)
	var ink: Color = TEXT
	if primary:
		base = ACCENT
		hover = ACCENT.lightened(0.14)
		press = ACCENT.darkened(0.14)
		ink = Color(0.14, 0.10, 0.04)
	b.add_theme_stylebox_override("normal", button_box(base))
	b.add_theme_stylebox_override("hover", button_box(hover))
	b.add_theme_stylebox_override("pressed", button_box(press))
	b.add_theme_stylebox_override("focus", button_box(hover))
	for state: String in ["font_color", "font_hover_color", "font_pressed_color", "font_focus_color"]:
		b.add_theme_color_override(state, ink)
	b.add_theme_font_size_override("font_size", 22)
	b.custom_minimum_size = Vector2(min_width, 0.0)


static func make_label(
	text: String, font_size: int, color: Color = TEXT, centered: bool = true
) -> Label:
	var l: Label = Label.new()
	l.text = text
	style_label(l, font_size, color)
	if centered:
		l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	l.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return l


## Full-rect dimmer. Sits behind a modal so the game reads as suspended, not replaced.
static func backdrop(color: Color = BACKDROP) -> ColorRect:
	var r: ColorRect = ColorRect.new()
	r.color = color
	r.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	r.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return r


static func with_alpha(c: Color, a: float) -> Color:
	return Color(c.r, c.g, c.b, a)

# --------------------------------------------------------------------------------- icons

## A UI icon drawn with primitives instead of loaded from a file.
##
## Vector-drawing icons removes the entire "where do the icons come from" problem at the
## stage where it would otherwise block the UI from existing. They scale to any size, they
## re-tint in one call (no per-colour asset), they cost no import, and they are legible at
## 16px because they are built from circles and polygons rather than downsampled art.
##
## The normalised _p() helper means every glyph is authored in 0..1 space and works at any
## size. Add cases to Kind for your game; keep them to a handful of primitives each — an
## icon that needs twenty draw calls wants to be a real asset.
class Glyph extends Control:
	enum Kind {
		CIRCLE, STAR, COIN, HEART, SHIELD, BOLT, CLOCK, KEY,
		MAGNIFIER, SORT, BAG, DROP,
	}

	var kind: Kind = Kind.CIRCLE
	var color: Color = TEXT
	var thickness: float = 2.0

	func _init(
		kind_in: Kind = Kind.CIRCLE, color_in: Color = TEXT, size_in: float = ICON_SIZE
	) -> void:
		kind = kind_in
		color = color_in
		custom_minimum_size = Vector2(size_in, size_in)
		mouse_filter = Control.MOUSE_FILTER_IGNORE
		size_flags_vertical = Control.SIZE_SHRINK_CENTER

	## Re-tint without rebuilding the node — e.g. a combo icon that heats up as it climbs.
	func set_color(c: Color) -> void:
		color = c
		queue_redraw()

	func _p(x: float, y: float) -> Vector2:
		return Vector2(x * size.x, y * size.y)

	func _draw() -> void:
		# Guard: a Control that has not been laid out yet has zero size, and drawing into
		# it produces NaNs rather than an empty icon.
		if size.x <= 1.0 or size.y <= 1.0:
			return
		var u: float = minf(size.x, size.y)
		match kind:
			Kind.CIRCLE:
				draw_circle(_p(0.5, 0.5), u * 0.36, color)
				draw_circle(_p(0.37, 0.36), u * 0.09, Color(1, 1, 1, 0.6))
			Kind.STAR:
				draw_colored_polygon(PackedVector2Array([
					_p(0.50, 0.02), _p(0.61, 0.39), _p(0.98, 0.50), _p(0.61, 0.61),
					_p(0.50, 0.98), _p(0.39, 0.61), _p(0.02, 0.50), _p(0.39, 0.39),
				]), color)
			Kind.COIN:
				draw_arc(_p(0.5, 0.5), u * 0.38, 0.0, TAU, 28, color, thickness, true)
				_glyph_text("$", u * 0.66)
			Kind.HEART:
				draw_circle(_p(0.32, 0.36), u * 0.22, color)
				draw_circle(_p(0.68, 0.36), u * 0.22, color)
				draw_colored_polygon(PackedVector2Array([
					_p(0.10, 0.44), _p(0.90, 0.44), _p(0.50, 0.95),
				]), color)
			Kind.SHIELD:
				draw_colored_polygon(PackedVector2Array([
					_p(0.5, 0.04), _p(0.92, 0.22), _p(0.82, 0.70),
					_p(0.5, 0.96), _p(0.18, 0.70), _p(0.08, 0.22),
				]), color)
			Kind.BOLT:
				draw_colored_polygon(PackedVector2Array([
					_p(0.58, 0.02), _p(0.22, 0.55), _p(0.46, 0.55),
					_p(0.40, 0.98), _p(0.80, 0.42), _p(0.54, 0.42),
				]), color)
			Kind.CLOCK:
				draw_arc(_p(0.5, 0.5), u * 0.38, 0.0, TAU, 28, color, thickness, true)
				draw_line(_p(0.5, 0.5), _p(0.5, 0.24), color, thickness, true)
				draw_line(_p(0.5, 0.5), _p(0.70, 0.58), color, thickness, true)
			Kind.KEY:
				draw_arc(_p(0.32, 0.34), u * 0.20, 0.0, TAU, 20, color, thickness, true)
				draw_line(_p(0.44, 0.46), _p(0.92, 0.92), color, thickness, true)
				draw_line(_p(0.74, 0.74), _p(0.88, 0.60), color, thickness, true)
			Kind.MAGNIFIER:
				draw_arc(_p(0.42, 0.42), u * 0.30, 0.0, TAU, 24, color, thickness, true)
				draw_line(_p(0.63, 0.63), _p(0.92, 0.92), color, thickness + 1.0, true)
			Kind.SORT:
				draw_line(_p(0.10, 0.24), _p(0.90, 0.24), color, thickness, true)
				draw_line(_p(0.10, 0.50), _p(0.68, 0.50), color, thickness, true)
				draw_line(_p(0.10, 0.76), _p(0.44, 0.76), color, thickness, true)
			Kind.BAG:
				draw_colored_polygon(PackedVector2Array([
					_p(0.16, 0.44), _p(0.84, 0.44), _p(0.96, 0.96), _p(0.04, 0.96),
				]), color)
				draw_arc(_p(0.5, 0.46), u * 0.26, PI, TAU, 20, color, thickness, true)
			Kind.DROP:
				draw_circle(_p(0.5, 0.62), u * 0.30, color)
				draw_colored_polygon(PackedVector2Array([
					_p(0.5, 0.06), _p(0.78, 0.62), _p(0.22, 0.62),
				]), color)

	func _glyph_text(s: String, px: float) -> void:
		var font: Font = ThemeDB.fallback_font
		if font == null:
			return
		var fs: int = int(px)
		var w: float = font.get_string_size(s, HORIZONTAL_ALIGNMENT_LEFT, -1, fs).x
		draw_string(
			font,
			Vector2(size.x * 0.5 - w * 0.5, size.y * 0.5 + float(fs) * 0.36),
			s, HORIZONTAL_ALIGNMENT_LEFT, -1, fs, color
		)
