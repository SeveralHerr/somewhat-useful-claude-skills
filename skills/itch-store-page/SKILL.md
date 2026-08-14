---
name: itch-store-page
description: Set up or update an itch.io game page — theme colours, description, tagline, tags, cover image, banner and screenshots — by driving the user's logged-in Chrome, plus generate store art and a palette from gameplay screenshots. Use this whenever the user mentions itch.io, their game page, store page, game cover, banner art, page theme or colours, store screenshots, or publishing/refreshing how a game build is presented — even if they never say "itch.io" outright. Also use it when they ask what an itch.io API key or butler can do, since the answer is counterintuitive and this skill has it.
---

# itch.io store pages

## Start here: the API key cannot do this

Anyone asked to "set up the itch.io page with my API key" will reach for the API first.
It is a dead end and worth stating up front so no one spends a turn discovering it:

| Capability | How | Write? |
|---|---|---|
| Upload/patch a build | `butler push dir user/game:channel` | yes — the **only** write |
| Channel + build status | `butler status`, `/wharf/latest` | read |
| Key owner, profile, game ids | `/credentials/info`, `/profile`, `/profile/games` | read |
| Download keys, purchases | `/games/ID/{download_keys,purchases}` | read |

Nothing in the API touches title, tagline, description, cover, banner, screenshots,
tags, pricing, embed settings or visibility. Those exist only in the web forms. So the
work is browser automation against the user's logged-in session — load the
`claude-in-chrome` skill and drive it there.

Say this plainly before starting, so the user knows why you're opening a browser.

## Where each thing lives

Two separate editors, and people conflate them:

- **`itch.io/game/edit/<id>`** — title, tagline, description, genre, tags, pricing,
  uploads, embed options, cover image, screenshots, visibility.
- **The game page itself, `<user>.itch.io/<slug>`** → the **Edit theme** bar → colours,
  fonts, screenshot placement, banner / background / embed-bg images.

Find `<id>` from `itch.io/dashboard`: each project's Edit link is `/game/edit/<id>`.

## Workflow

1. Get the game id from the dashboard.
2. Read the whole edit form first (`get_page_text`) before typing anything — it tells you
   what is already filled in, which matters because some fields are the user's own prior
   decisions and are not yours to change (see Boundaries).
3. Fill copy, genre, tags. Save. Verify by reload, not by the absence of an error.
4. Generate art from real gameplay screenshots (see below), upload it.
5. Open the theme editor, set colours from the game's own palette, set screenshot
   placement, save. Verify by reload.

Verify by reloading rather than trusting the in-page state: several of these widgets
render an optimistic result that a failed save never undoes.

## Uploading images — the part that looks impossible

Every image slot (cover, screenshots, banner, background, embed BG) uses the same
widget. It has **no `<input type=file>` in the DOM and no working drop handler**, so the
obvious approaches all fail silently:

- synthetic `DragEvent` on the drop container — no effect
- jQuery `.trigger('drop', {dataTransfer})` — no effect
- clicking the button — opens a native OS picker you cannot drive, and may hang the session

What does work: the widget **creates** a real file input on demand and calls `.click()`
on it. Swallow that one call and you get the input, with itch's own listeners attached,
and no dialog:

```js
// 1. Neutralise the picker BEFORE anything can open it.
window.__cap = [];
window.__origClick = HTMLInputElement.prototype.click;
HTMLInputElement.prototype.click = function () {
  if (this.type === 'file') { window.__cap.push(this); return; }   // swallow
  return window.__origClick.apply(this, arguments);
};
// Prove it is a no-op before you trust it:
(() => { const i = document.createElement('input'); i.type = 'file'; i.click();
         return window.__cap.length === 1; })();
```

Then click the widget's button *in JS* and keep the input it made:

```js
window.__cap = [];
document.querySelector('.add_screenshot_btn').click();       // or the cover/banner button
await new Promise(r => setTimeout(r, 800));
window.__target = window.__cap[0];                            // itch's real input
```

Now get the bytes in. `file_upload` needs a ref that `find` can see, and it cannot see
itch's input — so upload into your own shim and hand the `File`s across:

```js
// shim, created beforehand, with an aria-label find can match
const dt = new DataTransfer();
[...document.getElementById('claude-shim').files].forEach(f => dt.items.add(f));
window.__target.files = dt.files;                             // assignable in Chrome
window.__target.dispatchEvent(new Event('change', { bubbles: true }));
```

Wait ~5s, then confirm the hidden id field is populated. **Restore
`HTMLInputElement.prototype.click` and remove the shim before saving**, or a later real
click silently does nothing.

Screenshots accept all files in one go; cover and banner are single.

## Field reference

Edit form:

| Field | Selector |
|---|---|
| Tagline | `input[name="game[short_text]"]` — **max 120 chars**, save rejects 121 |
| Cover id | `input[name="game[cover_image_id]"]` |
| Screenshots | `input[name^="screenshot["]` → `screenshot[<id>][position]` |
| Description | `.redactor` contenteditable — click into it and type |

Theme editor:

| Field | Selector |
|---|---|
| Page bg / content bg | `layout[bg_color]`, `layout[bg2_color]` |
| Text / links | `layout[text_color]`, `layout[link_color]` |
| Headers / buttons | `layout[header_text_color]`, `layout[button_color]` |
| Screenshot placement | `layout[screenshots_loc]` — `""` \| `sidebar` \| `hidden` |
| Banner image id | `layout[banner_image][image_id]` |

Set text inputs through the native setter, then fire `input` + `change`, or the live
preview and the save both ignore you:

```js
Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(el, v);
el.dispatchEvent(new Event('input',  { bubbles: true }));
el.dispatchEvent(new Event('change', { bubbles: true }));
```

## Art and colours

`scripts/store_art.py` (needs Pillow) does the two things that are easy to botch —
integer downscaling so pixel art stays crisp, and supersampled titles that sit on the
art's own pixel grid rather than looking pasted on:

```bash
python scripts/store_art.py palette --src shot.png
python scripts/store_art.py cover  --src shot.png --out cover.png  --title "GAME" --subtitle "verb · verb · verb"
python scripts/store_art.py banner --src shot.png --out banner.png --title "GAME"
```

`--focus x,y` recentres the crop; `--scrim bottom|left|none` controls the text backing.

Source the screenshots from the game itself, driven to a scene worth showing — a fresh
save is usually sparse and photographs as an empty field. If the project has a devtools
bridge, use it to grant resources, unlock areas and move the player somewhere dense
before grabbing frames, and hide the HUD for the cover (a store cover wants game pixels,
not UI) while leaving it visible for the gallery shots, which should show the real
interface.

Build the theme from `palette` output rather than taste: colours lifted from the game's
own art make the page read as an extension of it, and they will not clash with the
screenshots sitting beside them. Check body text lands at 4.5:1 or better against the
background — palette mid-tones are usually too dim and need lightening.

## Gotchas

- **`screenshots_loc` defaults to `""` = "Auto (hidden)"**, and with an embedded game
  Auto resolves to *hidden*. Screenshots upload fine, sit in the DOM, and render at zero
  size in a collapsed column. Set it to `sidebar` explicitly or the user's uploads are
  invisible and everything looks broken for no visible reason.
- **The page scrolls between actions**, so coordinates captured in one batch are stale by
  the next. Prefer JS and element refs over pixel clicks; when you must click, screenshot
  immediately beforehand in the same call.
- **The description toolbar's list button opens a submenu** (Unordered / Ordered) rather
  than toggling. Type the lines first, select them, then apply.
- **An optimistic widget is not a save.** A drop or a click can leave the UI showing your
  image while the hidden id stays empty. Read the id field, then reload.
- **Do not infer success from something appearing.** If a cover shows up that you did not
  put there, check what it actually depicts before claiming your upload worked.

## Boundaries

Some fields on this form are declarations by the user, not styling:

- **Visibility (Draft / Restricted / Public)** — flipping this publishes to the world.
  Leave it alone and ask; it is rarely the thing they meant by "set up the page".
- **AI generation disclosure** — a required statement about how the game was made, with
  policy weight. If it is already answered, do not touch it. If it is blank, ask; do not
  answer on the user's behalf.
- **Pricing** and **deleting existing uploads or images** — confirm first.

Everything else (copy, tags, theme, adding art) is ordinary work; just report what you
changed and verify it after a reload.
