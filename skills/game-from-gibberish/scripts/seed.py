#!/usr/bin/env python3
"""Draw a casting: a keyboard mash plus the design constraints it decodes to.

Standard library only. Nothing is written to disk; the casting is printed for you
to paste into the game repo's SEED.md.

    python seed.py                          # generate a mash, draw from it
    python seed.py --mash "skfjhsd#$%"      # decode a real one (a paw, a friend, you)
    python seed.py --seed 41521             # reproduce an earlier casting exactly

The point of resolving the axes here rather than in the model's head is that a model
handed a raw mash will quietly generate several readings and pick the most defensible
one, which is how you get a space roguelike every single time. Dice do not have taste.
"""

import argparse
import random
import re
import sys
from pathlib import Path

DEFAULT_AXES = Path(__file__).resolve().parent.parent / "references" / "axes.md"

# The casting is printed for a human to paste into SEED.md, but it is just as often read
# through a pipe, a redirect, or an agent capturing stdout — all of which expect UTF-8. On
# a Windows console Python would otherwise encode to the active codepage, so an em dash
# lands as the single byte 0x97 and every UTF-8 consumer downstream sees a corrupted
# character in the artefact the whole method is built on. Pinning the encoding here rather
# than spelling the dashes in ASCII is deliberate: most of what gets printed comes out of
# references/axes.md, which is prose this script does not control and cannot keep ASCII.
# errors="replace" keeps the other half of the promise — a console that genuinely cannot
# render a character degrades it to "?" instead of raising UnicodeEncodeError mid-casting.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

# The physical layout is what makes a generated mash look like a real one: a paw lands
# somewhere and smears, so the string carries runs and neighbours rather than the flat
# uniform noise you get from random.choice over the alphabet.
ROWS = [
    "1234567890-=",
    "qwertyuiop[]",
    "asdfghjkl;'",
    "zxcvbnm,./",
]
SHIFTED = dict(zip(
    "1234567890-=[];',./",
    '!@#$%^&*()_+{}:"<>?',
))


def generate_mash(rng):
    """Simulate something heavy landing on a keyboard and dragging."""
    row = rng.randrange(len(ROWS))
    col = rng.randrange(len(ROWS[row]))
    out = []
    presses = rng.randint(4, 9)
    for _ in range(presses):
        row = max(0, min(len(ROWS) - 1, row + rng.choice((-1, 0, 0, 0, 1))))
        col = max(0, min(len(ROWS[row]) - 1, col + rng.randint(-2, 2)))
        ch = ROWS[row][col]
        if rng.random() < 0.12 and ch in SHIFTED:
            ch = SHIFTED[ch]
        # A held key is the single most legible thing in a mash, so let it happen often.
        out.append(ch * (rng.randint(2, 5) if rng.random() < 0.22 else 1))
    return "".join(out)


def parse_axes(path):
    """Read `## heading` sections and their `- item` lines out of axes.md."""
    axes, current = {}, None
    for line in path.read_text(encoding="utf-8").splitlines():
        heading = re.match(r"^##\s+(\S+)", line)
        if heading:
            current = heading.group(1).lower()
            axes[current] = []
        elif current and line.startswith("- "):
            axes[current].append(line[2:].strip())
    return {k: v for k, v in axes.items() if v}


def longest_run(mash):
    """The held key, if there is one: (character, length)."""
    best_ch, best_n, ch_prev, n = "", 1, "", 0
    for ch in mash:
        n = n + 1 if ch == ch_prev else 1
        if n > best_n:
            best_ch, best_n = ch, n
        ch_prev = ch
    return best_ch, best_n


def pronounce(mash):
    """A sayable working title. Vowels get inserted between consonant pairs."""
    letters = [c for c in mash.lower() if c.isalpha()]
    if not letters:
        return "Untitled"
    vowels, out, since = "aeiou", [], 0
    for ch in letters:
        out.append(ch)
        if ch in vowels:
            since = 0
            continue
        since += 1
        if since >= 2:
            out.append(vowels[(ord(ch) + len(out)) % len(vowels)])
            since = 0
    return "".join(out).capitalize()


def scope_for(mash):
    n = len(mash)
    if n <= 6:
        return "one screen, one verb, no menus beyond start and quit"
    if n <= 11:
        return "one room you return to, three or four interacting parts"
    if n <= 18:
        return "a 90-second loop that escalates, then resets visibly changed"
    return "three connected spaces, each teaching one thing the next needs"


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mash", help="decode this string instead of generating one")
    ap.add_argument("--seed", type=int, help="reproduce a previous casting")
    ap.add_argument("--axes", type=Path, default=DEFAULT_AXES)
    args = ap.parse_args()

    seed = args.seed if args.seed is not None else random.randrange(10**9)
    rng = random.Random(seed)

    if not args.axes.exists():
        sys.exit(f"axes file not found: {args.axes}")
    axes = parse_axes(args.axes)
    missing = {"verb", "subject", "resource", "constraint", "perspective", "tone"} - set(axes)
    if missing:
        sys.exit(f"axes file is missing sections: {', '.join(sorted(missing))}")

    # Generate before drawing so that a given --seed reproduces the mash too.
    mash = args.mash if args.mash else generate_mash(rng)
    draw = {k: rng.choice(v) for k, v in axes.items()}
    run_ch, run_n = longest_run(mash)
    loud = [c for c in mash if not c.isalnum()]

    print(f"""
CASTING  seed={seed}   (reproduce with: seed.py --seed {seed} --mash "{mash}")

  mash          {mash}
  working title {pronounce(mash)}
  held key      {f"{run_ch!r} x{run_n} — more of one thing than is reasonable" if run_n > 1 else "none — nothing is emphasised, so nothing is exaggerated"}
  loud marks    {"".join(loud) if loud else "none — this one is quiet throughout"}
  scope         {scope_for(mash)}

THE FIVE  every one of these has to be legible in the finished game

  verb          {draw['verb']}
  subject       {draw['subject']}
  resource      {draw['resource']}
  constraint    {draw['constraint']}
  perspective   {draw['perspective']}

  tone          {draw['tone']}

Rolled once. Do not roll again — see SKILL.md.
""")


if __name__ == "__main__":
    main()
