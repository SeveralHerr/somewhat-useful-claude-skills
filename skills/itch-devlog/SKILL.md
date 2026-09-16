---
name: itch-devlog
description: Write and post a short end-of-day devlog to an itch.io project — pull the day's work from git, translate it into player-facing bullets, grab a fresh screenshot from the running game, and file it as a draft in the user's logged-in Chrome. Use this whenever the user mentions a devlog, an end-of-day or daily update, "post what I did today", wrapping up a dev session, or telling players about new features — even if they never say "itch.io" outright. For the store page itself (cover, tagline, tags, theme colours) use the itch-store-page skill instead.
---

# End-of-day itch.io devlog

## The one thing that matters: keep it short

A devlog is read in a feed, next to a hundred others, by someone deciding in two
seconds whether to care. The failure mode is not a bad sentence — it is a wall of
twelve bullets where three of them say "refactored the state machine". That reads as
noise, and the reader learns the log is not worth opening tomorrow.

So the target is deliberately, uncomfortably small:

- **Title** — names the single most interesting thing. Not "Devlog #7", not the date.
- **One lead sentence**, optional. Skip it if the bullets speak for themselves.
- **3–6 bullets**, each under ~10 words, each something a *player* would notice.
- **One screenshot.**

Under ~80 words total. If today produced ten changes, the job is choosing the four
worth mentioning, not compressing all ten. The rest of the day still happened; it just
does not go here.

## Workflow

0. Check that JavaScript runs on itch.io — one trivial `javascript_tool` call on the
   dashboard. Every step below depends on it; if the extension refuses, stop and ask the
   user to allow the site *before* typing anything into a form you cannot finish.
1. Pick the project and get its id (below).
2. Read the day's work from git and translate it (below).
3. Capture a screenshot that shows one of the things you just listed.
4. Fill the form, upload the image, **strip every file/build attachment**, **save as a draft**.
5. Reload the saved post and confirm the image actually *loads* (below).
6. Show the user the draft URL and the text. On their go-ahead, tick Published and save.

Step 6 is not optional politeness. A devlog is public, it notifies followers, and the
`post[published]` checkbox is **unchecked by default** — itch already treats a first
save as a draft, so drafting costs nothing and publishing early cannot be undone
quietly.

## Finding the game

`itch.io/dashboard` lists every project. Map titles to ids in one read:

```js
[...document.querySelectorAll('.game_row')].map(r => {
  const e = r.querySelector('a[href^="/game/edit/"]');
  const t = r.querySelector('.game_title');
  return e && t ? e.href.split('/').pop() + ' :: ' + t.textContent.trim() : null;
}).filter(Boolean)
```

The new-post form is `itch.io/dashboard/game/<id>/new-devlog`.

If the user has several projects, match on the repo name or the game's title rather
than assuming — a wrong id posts a real devlog to the wrong game's followers.

## What shipped today

```bash
git log --since="6am" --pretty=format:"%s" --no-merges
```

Widen to `--since="yesterday"` if that comes back thin — people commit at odd hours,
and an empty log more often means an early morning than a day with no work.

Then **translate, don't transcribe.** Commit subjects are written for the person who
will `git bisect` next month; they name files, systems and internal decisions. A player
knows none of those words. Ask of each commit: *what can someone now do, see, or stop
suffering that they couldn't yesterday?* If there is no answer, it does not go in.

| Commit | Devlog bullet |
|---|---|
| `fix(save): restore work in progress, not just configuration` | Furnaces keep smelting across a save |
| `feat(crafting): the tier-2 set -- swords, bandage, cooked food, brick` | New tier-2 recipes: swords, bandages, cooked food, bricks |
| `fix(enemies): attack a player who is already inside the attack range` | Enemies no longer freeze when you stand on them |
| `refactor(ui): make the scale factor the currency UiTheme trades in` | *(dropped — invisible to players)* |

Refactors, chores, docs, test and harness commits almost always drop out. That is
correct, not lossy. Two bullets that land beat six that include "cleaned up the enemy
registry".

Never invent a feature to pad the list, and never soften a fix into a feature. If the
day was genuinely one bug fix, the devlog is one bullet — that is an honest post and
readers trust it more than a padded one.

## The screenshot

Shoot it for the bullets you just wrote. A generic title-screen grab attached to a post
about new recipes tells the reader nothing, and they can tell.

If the project can be driven programmatically, use that — launch it, put the world in a
state that shows the thing off, then capture. Godot projects using the selftest harness:

```bash
python tools/devtools.py launch
python tools/devtools.py screenshot
```

Use whatever setup verbs the project exposes (granting items, teleporting, spawning) so
the frame is dense rather than an empty starting field, and prefer a shot where the new
thing is actually visible on screen. If there is no way to drive the game, ask the user
for a PNG rather than attaching something stale.

**A browser game: shoot it headless, not in the extension's tab.** The Claude in Chrome
tab is a background tab — `document.hidden` is true, `requestAnimationFrame` stops, and a
game loop that suspends on visibility renders a black frame. Drive the local dev server
with `puppeteer-core` (headless Chrome is always "visible") and `page.screenshot()` to a
file. Wait out any banner or toast before capturing ("Map Found", "Level 3") — they sit
dead centre for a few seconds and ruin the frame.

**Save the PNG where the extension may read it** — inside the project or a folder the user
has shared with the session. The upload below reads it from disk; nothing else will.

Two places the day's screenshot goes — set both, from the same file:

- **Attachment** (`attachment[N][object_type]=image`) — shows in the post body. Uploaded
  from the attachment picker's **Upload image** tab, whose button reads **Select images**.
- **Cover** (`post[cover_image_id]`) — the thumbnail in feeds and the devlog list; it is
  what most people actually see. Uploaded from the widget under the **Cover image** label
  (`.forms_image_uploader_widget`), whose button reads **Upload image**.

Mind the labels: the attachment *tab* is called "Upload image", and so is the cover
widget's *button*. A query for a button reading "Upload image" finds the tab and the
cover, never the attachment uploader.

The **Images** tab offers existing project screenshots with no upload. Do not use it for a
devlog: a store screenshot says nothing about what changed today.

### Uploading an image: real file bytes only

Neither uploader has an `<input type=file>` in the DOM — the widget creates one on demand
and calls `.click()` on it, which opens a native OS dialog you cannot drive. Capture that
input, **move it into the document** so `find` can see it, and fill it with the
extension's `file_upload` tool, which reads the PNG from disk:

```js
window.__origClick = HTMLInputElement.prototype.click;
window.__cap = [];
HTMLInputElement.prototype.click = function () {
  if (this.type === 'file') { window.__cap.push(this); return; }
  return window.__origClick.apply(this, arguments);
};
// attachment: click the "Upload image" tab_btn, then the "Select images" button
// cover:      document.querySelector('.forms_image_uploader_widget button').click()
await new Promise(r => setTimeout(r, 300));
HTMLInputElement.prototype.click = window.__origClick;       // restore immediately
const inp = window.__cap[0];
inp.setAttribute('aria-label', 'claude upload target');
inp.style.cssText = 'position:fixed;top:0;left:0;width:200px;height:40px;z-index:99999';
document.body.appendChild(inp);                               // still wired to the widget
```

Then `find` "file input claude upload target" → `file_upload` with that ref and the PNG's
absolute path. Wait ~6 s, remove the input from `document.body`, and read the id back
(`input[name$="[object_id]"]` for the attachment, `post[cover_image_id]` for the cover).
The captured input keeps its change listener after being moved, so the upload proceeds
exactly as if the dialog had been used. Do the attachment and the cover as two separate
captures.

**Never hand-carry image bytes through a JS string.** Pasting a base64 PNG into
`javascript_tool` and building a `File` from it *looks* like it works: the upload
succeeds, itch returns an image id, and the byte count can even match — but one wrong
character in 20 kB of base64 breaks a PNG CRC, and itch stores the corrupt file without
complaint. Both the body image and the cover then render as broken images on the post.
The same goes for fetching the file from a local server: a `fetch` from the itch page to
`http://localhost` hangs on Chrome's local-network permission prompt, which you must not
accept for the user. `file_upload` from disk is the only route that carries the real
bytes.

**An image id is not proof.** Verify that each uploaded image *loads*:

```js
const test = src => new Promise(r => { const i = new Image(); i.onload = () => r(true); i.onerror = () => r(false); i.src = src; });
const urls = [...new Set(document.body.innerHTML.match(/https:\/\/img\.itch\.zone\/[^"')\s&]+/g) || [])];
const out = [];
for (const u of urls) out.push({ id: atob(u.split('/')[3]), ok: await test(u) });   // e.g. img/30042302.png
out
```

Return decoded ids and booleans, not raw URLs — the extension redacts image URLs in tool
output. Any `ok: false` for one of today's ids means the upload is corrupt: remove that
attachment (its **Remove** button), clear the cover (**Remove image**), and upload again
from disk.

Note itch's own warning on the tab: an uploaded image belongs to the post only, and does
**not** join the project's screenshots.

## Field reference

Form at `itch.io/dashboard/game/<id>/new-devlog`:

| Field | Selector / value |
|---|---|
| Title | `input[name="post[title]"]` |
| Body | `textarea[name="post[body]"]` — a Redactor editor writes into it; do **not** type at it directly, see below |
| Category | `input[name="post[user_classification]"]` — `general_update`, `major_update`, `postmortem`, `tech_discussion`, `culture`, `tutorial`, `game_design`, `marketing`. **Nothing is preselected**; pick `general_update` for a daily, `major_update` for a release |
| Tags | `input[name="post[tags]"]` |
| Cover | `input[name="post[cover_image_id]"]` (hidden; set by the widget) |
| Attachments | `input[name^="attachment"]` — `[N][object_type]` + `[N][object_id]` |
| Comments | `input[name="post[enable_comments]"]` |
| Publish | `input[name="post[published]"]` — unchecked on a new post, **but pre-ticked when you reopen a draft to edit it**; read it before every save |
| Submit | the `form button.button` reading "Save" — it has no `type=submit`, so a `button[type=submit]` query returns nothing |

Write the bullets as a real list in the editor rather than lines starting with `-`;
the feed renders the markup, not the dashes.

### The body is a Redactor editor, and a devlog can save empty

What gets posted is the hidden `textarea[name="post[body]"]`. The visible editor is
Redactor, which fills that textarea from its *own* key handling — so synthetic input into
the contenteditable can leave the textarea at length 0 while the text sits there plainly
visible. Save then posts the empty string, and the devlog goes up with a title, a
screenshot and **no body**.

That is exactly the failure the store page's description field produced (see
`itch-store-page`, "My description vanished when I saved"), where setting `innerHTML`,
dispatching `input`/`keyup`, and a real driven keypress all left the textarea empty. The
same form technology is behind both fields, so use the same defence here: write both
halves, and read the textarea back before you press Save.

```js
const ta = document.querySelector('textarea[name="post[body]"]');
const ed = document.querySelector('.redactor-in')
        || document.querySelector('.redactor-layer')
        || ta.parentElement.querySelector('[contenteditable="true"]');
ed.innerHTML = html;
ta.value = ed.innerHTML;      // the half that is actually submitted
ta.value.length               // must be non-zero, or Save posts an empty devlog
```

**Resolve the element; do not hard-code the class.** The two forms have been observed
disagreeing — a live read of the store edit form returned `.redactor-in` on 2026-08-17,
while this devlog form was recorded using `.redactor-layer`. Do not go and settle which
one is "really" right: the chain above is the answer either way, and the answer expires.
These class names belong to itch, not to us; a name read today can change on their next
deploy, and two forms on the same site already disagree, which is the strongest evidence
you will get that pinning one is the wrong move. So the chain is the design, not a
workaround waiting on a measurement — whichever class is live it finds it, and the
`[contenteditable="true"]` fallback catches a third nobody has seen yet.

What that buys you is a **failure you can detect**. Treat a `null` at `ed`, or a
zero-length `ta.value`, as the bug and stop — those are the two states that produce an
empty post, and they are cheap to check. A hard-coded selector turns the same breakage
into a silent one, because `querySelector` returning `null` reads exactly like a page
that has not finished loading.

## Gotchas

- **`Attach` does not touch the body.** It appends hidden `attachment[N]` inputs. So
  verifying by looking for an `<img>` in the editor reports failure on a working
  attach — read `input[name^="attachment"]` instead.
- **itch pre-attaches things you did not choose.** A fresh form can arrive with the
  latest file (`object_type=upload`), the latest build (`object_type=build`) and every
  recently added project screenshot (`object_type=image`) already attached. **Remove all
  of them** with each row's **Remove** button before adding today's screenshot — a devlog
  carries no file or build attachments (see Boundaries), and a store screenshot
  dilutes "one screenshot of what changed". Read `input[name^="attachment"]` after
  removing: the only attachment left should be the image you uploaded.
- **Serializing large chunks of this page can wedge the renderer** — an `outerHTML` dump
  or a full-page screenshot has hung the tab outright. Read narrow: specific selectors,
  short slices. The store page's edit form fails next door to this one: screenshots there
  come back blank or time out at 30s (`itch-store-page`, Gotchas), and a blank frame reads
  as an empty form and invites you to redo work that already landed. Same rule for both —
  verify with narrow JS reads of the actual field values and a reload, and keep
  screenshots for the rendered public page.
- **Verify by reloading the saved post**, not by the form looking right. The editor
  shows optimistic state that a rejected save never rolls back.
- A devlog **notifies followers on publish**. There is no quiet edit window worth
  relying on — get it right in the draft.

## Boundaries

- **Publishing is the user's call**, every time. Draft, show, wait. Approval yesterday
  is not approval today.
- **Don't edit or delete existing devlogs** unless asked — they may have comments.
- **Never attach files or builds to a devlog** — not even ones itch pre-attaches, and not
  when the user pushed a build today. The game page is where downloads live; a devlog
  carries text and one screenshot. Remove any `upload`/`build` attachment you find.
- **Don't flip the project's visibility.** If today's work isn't deployed, say so rather
  than implying it is live.
