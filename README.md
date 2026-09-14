# portfolio

My site. One generated HTML file, no framework and no build step to install.

```
py -3 build.py            read the GitHub API, write index.html
py -3 build.py --check    13 self-checks
py -3 build.py --offline  build from the cached payload
```

## Why it is generated

Because of the rule in `CLAUDE.md`: **never type a number that can be read.**
The last version of this site said "four tools, which is every public repo I
have" while I had thirteen. It had been wrong for a week and nothing told me.

Every count, span, rate and language on the page is computed from what the API
returns, and the footer stamps when it was read and whether it came from the
network or the cache. If GitHub cannot be reached, the build **refuses to write
a page** rather than quietly shipping yesterday's numbers.

## The states are editorial, and say so

`has_pages` is derived. Whether a project is shipped, still being built, or
paused is not, so it lives in the `STATE` table in `build.py`. A repo missing
from that table renders as **NOT RECORDED** — never as a guess, and never as
SHIPPED by default.

`NOT RECORDED` is deliberately the loudest label on the board, and a check
enforces it at 10:1 or better. A zero means two things, and the one that means
*I have not written this down* should not be the one you cannot see.

## Where the design came from

**Palette and type are Out Baby Out's**, read out of that repo rather than
chosen again: `--field` `--panel` `--line` `--chalk` `--dim`, plus the two
colours the game already uses to mean something — `vish` for out, `amrit` for
the revive. They keep those jobs here. Anton, Instrument Sans and JetBrains
Mono are the game's faces too.

One exception, measured: `vish` at `#E0523B` is 4.39:1 on the panel, which
fails WCAG AA at the 10px a state label is set in. `--vish-text` is `#E46955` —
same hue, same saturation, lightness up 0.06, 5.20:1. The game keeps its
colour; small text gets the one you can read.

**The shape is learned from [matthewnpark.com](https://matthewnpark.com) and
deliberately not copied from it.** What is learned: a reverse-chronological
dated ledger instead of project cards, and one small type size doing nearly all
the work — his 12px/−0.4px appears 107 times on a single page. What is not
copied: his is light, set in IBM Plex Mono and Inter, and lists things that
happened to him. This is dark, set in the game's own faces, and lists things
that were built, with an honest state on each.

## A note on the checks

Two of the contrast checks originally asserted that an exact CSS string
appeared in the output. Because the assertion text was identical to the
template text, one search-and-replace edited both, and the check kept passing
with the bug restored. It was a test that could not fail.

They now read the colours back out of the rendered page, resolve the `var()`
indirection and compute the real ratio. Both were then broken on purpose and
watched go red:

```
AssertionError: s-none is 1.33:1, below AA for 10px text
AssertionError: s-pause is 4.39:1, below AA for 10px text
```

## Previous version

`archive/v1-resend-system.html` — the cream and serif site built on the system
measured from resend.com. Kept because it is not wrong, just not this.
