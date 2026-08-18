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

1. Pick the project and get its id (below).
2. Read the day's work from git and translate it (below).
3. Capture a screenshot that shows one of the things you just listed.
4. Fill the form, upload/attach the image, **save as a draft**.
5. Show the user the draft URL and the text. On their go-ahead, tick Published and save.

Step 5 is not optional politeness. A devlog is public, it notifies followers, and the
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

Three separate places an image can live on a devlog — pick deliberately:

- **Attachment** (`attachment[N][object_type]=image`) — shows in the post body area.
  This is the normal home for the day's screenshot.
- **Cover** (`post[cover_image_id]`) — the thumbnail in feeds and the devlog list.
  Worth setting too; it is what most people actually see.
- Existing project screenshots can be attached with no upload at all, from the
  **Images** tab — one `.click()` on an `Attach` button. Good for a filler shot, wrong
  for "here is what changed today".

### Uploading a new image

The **Upload image** tab's picker has **no `<input type=file>` in the DOM** — the widget
creates one on demand and calls `.click()` on it, which opens a native OS dialog you
cannot drive. Swallow that call to capture the real input, then feed it files through a
shim input of your own:

```js
window.__cap = [];
window.__origClick = HTMLInputElement.prototype.click;
HTMLInputElement.prototype.click = function () {
  if (this.type === 'file') { window.__cap.push(this); return; }
  return window.__origClick.apply(this, arguments);
};
// then click the widget's own button in JS, take window.__cap[0],
// assign it a DataTransfer built from your shim's files, dispatch 'change'
```

**Restore `HTMLInputElement.prototype.click` and remove the shim before saving**, or the
Save button's own click does nothing. The `itch-store-page` skill documents this dance
in full, including the shim markup — read it if the short version above is not enough.

Note itch's own warning on that tab: an uploaded image belongs to the post only, and
does **not** join the project's screenshots.

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
| Publish | `input[name="post[published]"]` — **unchecked by default** |
| Submit | the `button[type=submit]` reading "Save" |

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
- **A build may already be attached** as `attachment[1][object_type]=build`. That is
  itch offering the latest upload; leave it if the user pushed a build today, remove it
  if they did not, since it implies a release that never happened.
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
- **Don't attach builds or flip the project's visibility.** Shipping a build is a
  separate decision from writing about it; if today's work isn't uploaded, say so
  rather than implying it is live.
