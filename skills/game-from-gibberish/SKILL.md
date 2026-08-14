---
name: game-from-gibberish
description: Turn keyboard mash, random noise, or a blank page into an actual finished small game — a divergent design method that reads nonsense as a design brief, resolves it into hard mechanical constraints with a dice roll, and builds the thing for real. Use this whenever the user hands over gibberish and wants a game out of it ("skfjhsd", "my cat walked on the keyboard", "make a game out of this"), whenever they want a game but cannot say which one ("just make me something", "surprise me", "I don't know what to build", "give me a weird idea", "something for the game jam"), whenever they ask for a random or seeded game concept, and whenever they complain that the ideas coming back are generic, samey, or boring. Also use it when continuing a game that was started this way and the user sends another burst of nonsense — that is an update request, not a new project.
---

# Games out of gibberish

This is a divergence method. It exists because a model asked for "a game idea" reliably
lands in the same small neighbourhood — endless runner, wave survival, collect-the-coins,
a roguelike about a dungeon — not through lack of imagination but because those are the
centre of the distribution, and the centre is where an unconstrained sample goes.

The method's origin is a dog walking on a keyboard, and that detail is load-bearing. The
dog is a genuine external entropy source with no taste, no genre knowledge, and no sense
of what would be reasonable. Everything below is an attempt to keep that property while
using dice instead of a dog.

## The failure this is built to prevent

Hand a model `skfjhsd#$%` and ask it to read meaning into it, and it will privately
generate five or six candidate interpretations and return the most defensible one.
That step feels like interpretation. It is actually a filter, and what it filters *for*
is ordinariness — so the randomness goes in and a space roguelike comes out, every time.
The entropy gets laundered.

Two things stop this, and both matter more than any single instruction in this file:

**The constraints get resolved by dice, not by reading.** `scripts/seed.py` draws them
from wordlists before any design thinking happens. Dice have no preferences to collapse
toward.

**The commitment is written down before the design starts.** You record what you drew
and what you're going to build in a file, and only then work out how. Committing on
paper first is what makes the constraint real rather than a thing you drift away from
over the next twenty minutes of implementation.

## 1. Draw the casting

```bash
python <skill dir>/scripts/seed.py                      # generate a mash and draw
python <skill dir>/scripts/seed.py --mash "skfjhsd#$%"  # decode a real one
python <skill dir>/scripts/seed.py --seed 41521         # reproduce a past casting
```

If the user supplied gibberish, pass it with `--mash` — a real mash from a real animal
or a real frustrated human is better entropy than the generator, and it belongs to them.
If they just want a game, let the script produce one.

Standard library only, writes nothing. The wordlists live in `references/axes.md` and are
meant to be edited; read that file if you want to know what the draw space looks like or
if the user asks to tune it.

**Roll once.** If you draw a casting, look at it, and roll again because the first one
looked hard to build, you have re-introduced exactly the taste filter this whole method
exists to defeat — and you'll do it in the direction of whatever is easiest, which is the
direction of generic. A casting that seems unbuildable is the good case. The interesting
move is almost always to take the awkward constraint literally rather than to soften it.

The one legitimate reason to re-roll is that the user asks for one, having seen it.

## 2. Read the mash

The dice give you mechanics. The mash gives you texture, and it's the half that belongs
to whoever typed it, so read it out loud before you design anything.

| What's in the string | What it means |
|---|---|
| The working title the script printed | This is the game's name. Use it. A game called *Nvavvovnohma* is already committed to being itself in a way that *Shadow Depths* is not. |
| A held key (`mmmmmmm`) | There is far more of one thing than is reasonable. Whatever the game has most of, multiply it until it is a bit alarming. |
| Loud marks (`#$%!`) | The game's loud moments. Punctuation-heavy means it has a mode that shouts; a quiet mash means it never raises its voice. |
| A short string | Small. Do not pad it out into something with a menu system. |
| Isolated system keys — a lone Escape, Tab, arrow keys | The user being dramatic. Ignore these rather than straining to read them; nothing is gained by decoding a stray keypress. |

Don't ask the user what their gibberish meant. Being asked to explain the joke is the one
outcome the method has to avoid — the input is theirs, the reading is yours, and handing
the interpretive work back to them defeats the point of the exercise.

## 3. Commit before you design

Write `SEED.md` at the root of the game project, before writing any code:

```markdown
# Seed

    seed=41521  mash="nvvvvnhm..jjjjjj"  (python seed.py --seed 41521)

**Title:** <the pronounced mash>

| Axis | Drawn | How it shows up in the game |
|---|---|---|
| verb | tow | ... |
| subject | a river the town keeps redirecting | ... |
| resource | water that finds the low ground | ... |
| constraint | the camera belongs to someone else | ... |
| perspective | the last working machine on the floor | ... |

**Tone:** funereal but upbeat
**Scope:** a 90-second loop that escalates, then resets visibly changed

**What you do, in one sentence:** ...
```

That right-hand column is the whole exercise. Fill it in for all five before opening a
single script file. If you can't say concretely how *perspective: a habit* shows up on
screen, you don't yet have a game — and discovering that now costs a paragraph, whereas
discovering it after you've built a player controller costs the afternoon.

Every one of the five must be legible in the finished thing. A drawn axis you quietly
dropped is entropy you laundered, just later in the process. If two of them fight, the
collision is the design — a resource that decays while observed plus a camera you don't
control is not a problem to be resolved, it's the game.

## 4. Build it for real

Hand the actual construction to whatever is available:

- **`godot-selftest-harness`** (`/scaffold-godot-harness`, then `/verify`) — project setup
  and the validation loop. If it's installed, use it; a game you can't screenshot from the
  command line can't be criticised, and step 5 depends on being able to look at it.
- **`godot-game-ui-juicy`** or **`godot-game-ui`** — every screen and menu.
- **`kenney-asset-kit`** — if you're reaching for prefab 3D art.

Nothing in this skill knows about engines. If none of the above are present, build with
whatever the project already uses.

## 5. Finish it

The method produces a genuinely strange brief, and a strange brief rendered in grey
capsules on a grey plane reads as an unfinished experiment rather than a game. The
strangeness only lands if the execution is committed. So:

**No placeholder art in the delivered build.** Not "grey box for now". Every object gets
a silhouette that reads at a glance and a palette that was chosen. Shapes are allowed to
be simple; they are not allowed to be anonymous.

**Refuse the attractors by name.** If what you're building has become an endless runner,
a wave-survival arena, a match-3, a "collect ten things" fetch loop, or a generic
top-down roguelike, the casting stopped steering somewhere back there. Return to `SEED.md`
and find where — usually it's an axis you translated into a familiar mechanic instead of
taking literally.

**Screenshot it and be hard on it.** Take a real screenshot, look at it, and say what is
wrong with it before the user has to. "Readable" is not the bar — the bar is that a
stranger seeing the screenshot understands what they'd be doing. Iterate on the picture,
not on your mental model of the picture.

**Ship the controls on screen.** A game built from a nonsense brief has a nonsense verb
set, and nobody can guess it. Put the controls somewhere visible, styled like part of the
game. Target 1080p.

## 6. The next burst of nonsense

More gibberish after the first is **an update to the existing game, never a new one.**
This is what makes the method a loop rather than a novelty generator: the game accretes,
gets stranger, and starts to have history.

Draw a fresh casting for the update, but treat it as pressure applied to what already
exists — a new drawn `constraint` is a rule now imposed on the current game; a new
`resource` is something the existing verbs must now also spend. Append the new casting to
`SEED.md` under a dated heading rather than replacing it, so the game's whole strange
lineage stays readable.

Start over only if the user says outright that they want a different game.
