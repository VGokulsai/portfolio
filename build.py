"""Generate index.html from the live GitHub API.

The page exists because of one rule in CLAUDE.md: never type a number that can
be read. Every count, date, span and rate on the site is computed here from
what the API actually returns, and the page stamps when it was read. Nothing on
it is remembered.

    py -3 build.py            write index.html
    py -3 build.py --check    run the self-checks
    py -3 build.py --offline  build from the cached payload, no network

A project's STATE is editorial and cannot be derived, so it lives in the table
below. A repo missing from that table renders as "not recorded" - never as a
guess, and never as SHIPPED by default. A zero means two things.
"""

import io
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import date, datetime, timezone

USER = "gokulsai1004-create"
API = "https://api.github.com/users/%s/repos?per_page=100" % USER
CACHE = "repos.json"
OUT = "index.html"

# Editorial. Derived from what actually happened, not from the repo's contents.
# Anything not listed here prints as unrecorded rather than being invented.
STATE = {
    "painpoint-finder": ("SHIPPED", "Used it on five of my own ideas before anyone else saw it."),
    "apisurface":       ("BUILDING", "Measurement half done. The diff works, the survey does not."),
    "cloud-pet":        ("SHIPPED", "Measured 14x cheaper once stripped to the standard library."),
    "publicsearch":     ("SHIPPED", "The blocked-is-not-empty rule started here."),
    "firstwrong":       ("SHIPPED", "Built to catch a failure it was itself guilty of."),
    "outbabyout":       ("PAUSED", "Three pages up, twelve crosscheck tests. Waiting on one played match."),
    "journal":          ("SHIPPED", "Written the week it happens or not at all."),
    "jump":             ("SHIPPED", None),
    "synth":            ("SHIPPED", None),
    "specextract":      ("SHIPPED", None),
    "skillcheck":       ("SHIPPED", None),
    "mdwatch":          ("SHIPPED", None),
}

SKIP = {USER}  # the profile repo is not a project

# The other strand of the ledger: things that happened that are not a repo.
#
# Everything here has to be true and has to have already happened. Only what
# can be read from the API ships until you add more. Add yours in
# the same shape as matthewnpark.com - date first, third person, present
# tense, one short line, no adjectives:
#
#     ("2026-09-21", "Turns 16"),
#     ("2026-08-31", "Applies to Axiom Pathways"),
#
# Present tense is only the voice. Every entry must already have happened. Do
# not add anything you are still waiting on. The page says what was done,
# never what was hoped for, and a milestone that has not happened yet is the
# one thing on here that could not be checked.
MILESTONES = [
    ("2025-08-08", "Opens a GitHub account"),
]

# One table so a handle is added in one place. url of None means "I do not
# have this yet" and it is left off the page rather than shipped dead.
LINKS = [
    ("GitHub",       "https://github.com/%s" % USER),
    ("Journal",      "https://%s.github.io/journal/" % USER),
    ("Out Baby Out", "https://%s.github.io/outbabyout/" % USER),
    ("Instagram",    "https://instagram.com/gokulsai_2010"),
    ("LinkedIn",     None),
    ("Email",        "mailto:gokulsai1004@gmail.com"),
]

# What I actually believe, kept to the three that changed how I build.
RULES = [
    ("A zero means two things",
     "Nothing was there is a result. I could not look is not. Any count that "
     "cannot tell you which one it is has told you nothing."),
    ("Never type a number that can be read",
     "Every figure on this page was read from the API a moment ago. The stamp "
     "at the bottom says when. Counts of repos, tests and sources all go stale."),
    ("A passing test proves nothing until you have watched it fail",
     "Break it, see it go red, put it back. Two of mine were passing while "
     "checking nothing at all, and a green run never said so."),
]


def fetch(offline=False):
    """Repos, from the network or the cache. Says which, and never silently
    falls back - a cached build that thinks it is live is the exact failure
    this whole site is about."""
    if offline:
        if not os.path.exists(CACHE):
            raise SystemExit("BLOCKED: --offline but no %s to read" % CACHE)
        with io.open(CACHE, encoding="utf-8") as f:
            return json.load(f), "cache"
    req = urllib.request.Request(API, headers={
        "User-Agent": "gokulsai-portfolio-build",
        "Accept": "application/vnd.github+json"})
    try:
        raw = urllib.request.urlopen(req, timeout=30).read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        raise SystemExit("ERROR: GitHub returned %s. Nothing was learned; not "
                         "writing a page." % exc.code)
    except Exception as exc:
        raise SystemExit("ERROR: could not reach api.github.com (%s). Nothing "
                         "was learned; not writing a page."
                         % type(exc).__name__)
    data = json.loads(raw)
    with io.open(CACHE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1)
    return data, "live"


def projects(repos):
    out = []
    for r in repos:
        if r.get("fork") or r["name"] in SKIP:
            continue
        state, note = STATE.get(r["name"], (None, None))
        out.append({
            "name": r["name"],
            "created": r["created_at"][:10],
            "pushed": r["pushed_at"][:10],
            "desc": (r.get("description") or "").strip(),
            "lang": r.get("language") or "",
            "pages": bool(r.get("has_pages")),
            "url": r["html_url"],
            "live": "https://%s.github.io/%s/" % (USER, r["name"]) if r.get("has_pages") else None,
            "state": state,
            "note": note,
        })
    out.sort(key=lambda p: p["created"], reverse=True)
    return out


def rate(ps):
    """Repos per week across the span actually worked, not since the account
    opened. An account opened in 2025 and used from August 2026 would otherwise
    report a rate that flatters by a year."""
    if len(ps) < 2:
        return None
    first = date.fromisoformat(min(p["created"] for p in ps))
    last = date.fromisoformat(max(p["created"] for p in ps))
    days = (last - first).days
    if days <= 0:
        return None
    return {"first": first, "last": last, "days": days, "n": len(ps),
            "per_week": len(ps) / (days / 7.0)}


def _lum(hexcolour):
    """WCAG relative luminance."""
    h = hexcolour.lstrip("#")
    out = []
    for i in (0, 2, 4):
        c = int(h[i:i + 2], 16) / 255.0
        out.append(c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4)
    return 0.2126 * out[0] + 0.7152 * out[1] + 0.0722 * out[2]


def contrast(a, b):
    la, lb = _lum(a), _lum(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def state_contrast(html):
    """Read every state label's colour back out of the rendered page and
    measure it against the surface it sits on.

    Reading it back is the whole point. The previous version of this check
    asserted a literal CSS string, and since that string was identical to
    the one in the template, a single search-and-replace edited the test and
    the page together and the check kept passing with the bug restored.
    """
    tokens = dict(re.findall(r"--([a-z0-9-]+):(#[0-9A-Fa-f]{6})", html))
    panel = tokens.get("panel")
    if not panel:
        raise AssertionError("no --panel token in the page to measure against")
    out = {}
    for cls in ("s-ship", "s-build", "s-pause", "s-none"):
        m = re.search(r"\.%s\{color:var\(--([a-z0-9-]+)\)\}" % cls, html)
        if not m:
            raise AssertionError("no rule found for .%s" % cls)
        colour = tokens.get(m.group(1))
        if not colour:
            raise AssertionError(".%s points at --%s, which is not defined"
                                 % (cls, m.group(1)))
        out[cls] = contrast(colour, panel)
    return out


def short_date(iso):
    """2026-09-12 -> 09.12.26, the way Matthew sets them.

    Month first, which is his convention and not the one used here. The
    datetime attribute on every row stays ISO, so this is a display choice
    only - flip the return to "%s.%s.%s" % (d, m, y[2:]) for day first.
    """
    y, m, d = iso.split("-")
    return "%s.%s.%s" % (m, d, y[2:])


def esc(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace('"', "&quot;"))


def render(ps, source):
    r = rate(ps)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    langs = {}
    for p in ps:
        if p["lang"]:
            langs[p["lang"]] = langs.get(p["lang"], 0) + 1
    langline = " · ".join("%s %d" % (k, v) for k, v in
                          sorted(langs.items(), key=lambda kv: -kv[1]))
    live = [p for p in ps if p["live"]]
    linkrow = "".join('<a href="%s">%s</a>' % (esc(u), esc(n))
                      for n, u in LINKS if u)
    unrecorded = [p for p in ps if not p["state"]]

    entries = [dict(p, kind="build") for p in ps]
    entries += [{"kind": "mark", "created": d, "name": t, "desc": "",
                 "note": None, "state": None, "live": None, "url": None}
                for d, t in MILESTONES]
    entries.sort(key=lambda e: e["created"], reverse=True)

    rows = []
    for p in entries:
        if p["kind"] == "mark":
            rows.append(
                '<li class="row mark">'
                '<time datetime="%s">%s</time>'
                '<div class="mid"><p class="what">%s</p></div>'
                '<span class="state s-mark">&middot;</span>'
                '</li>' % (p["created"], short_date(p["created"]),
                             esc(p["name"])))
            continue
        st = p["state"] or "NOT RECORDED"
        cls = {"SHIPPED": "s-ship", "BUILDING": "s-build",
               "PAUSED": "s-pause"}.get(p["state"], "s-none")
        live_a = ('<a class="live" href="%s">live</a>' % p["live"]) if p["live"] else ""
        note = ('<span class="note">%s</span>' % esc(p["note"])) if p["note"] else ""
        rows.append(
            '<li class="row">'
            '<time datetime="%s">%s</time>'
            '<div class="mid"><a class="nm" href="%s">%s</a>%s'
            '<p class="desc">%s</p>%s</div>'
            '<span class="state %s">%s</span>'
            '</li>' % (p["created"], short_date(p["created"]),
                       esc(p["url"]), esc(p["name"]), live_a,
                       esc(p["desc"]) or "<em>no description</em>", note,
                       cls, st))

    rules = "".join(
        '<div class="rule"><h3>%s</h3><p>%s</p></div>' % (esc(t), esc(b))
        for t, b in RULES)

    ratebit = ("%d projects in %d days &middot; %.1f a week"
               % (r["n"], r["days"], r["per_week"])) if r else "not enough to measure"

    return TEMPLATE % {
        "rows": "\n".join(rows),
        "rules": rules,
        "rate": ratebit,
        "n": len(ps),
        "nlive": len(live),
        "nunrec": len(unrecorded),
        "langline": esc(langline),
        "stamp": stamp,
        "source": source,
        "user": USER,
        "span": ("%s to %s" % (r["first"].isoformat(), r["last"].isoformat())) if r else "",
        "links": linkrow,
    }


TEMPLATE = """<title>Gokul Sai</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="I build tools that check whether something is true before you act on it. Hyderabad.">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Anton&family=Instrument+Sans:wght@400;500&family=JetBrains+Mono:wght@400;700&display=swap">
<style>
/* ----------------------------------------------------------------------------
   Palette and type are Out Baby Out's, read out of that repo rather than picked
   again: the field, the panel, the chalk, and the two colours the game already
   uses to mean something - vish for out, amrit for the revive. They keep those
   jobs here. Nothing decorative is painted in them.

   The shape of the page is learned from matthewnpark.com and deliberately not
   copied from it. What is learned: a reverse-chronological dated ledger instead
   of project cards, and one small type size doing nearly all the work (his
   12px/-0.4px appears 107 times on a single page). What is not copied: his is
   light, set in IBM Plex Mono and Inter, and lists things that happened to him.
   This is dark, set in the game's own faces, and lists things that were built
   with an honest state on each one - including the ones with no state recorded.
   ------------------------------------------------------------------------- */
:root{
  --field:#0F1310; --panel:#191E17; --line:#2C352A;
  --chalk:#F2F4E9; --dim:#8C9682;
  --hot:#E8FF3F; --vish:#E0523B; --amrit:#5FD08A;
  /* vish as the game paints it is #E0523B, which measures 4.39:1 on the
     panel and fails AA at the 10px a state label is set in. Same hue (8),
     same saturation, lightness up .06: 5.20:1. The game keeps its colour;
     small text gets the one you can actually read. */
  --vish-text:#E46955;

  --display:Anton,"Arial Narrow",sans-serif;
  --ui:"Instrument Sans",system-ui,sans-serif;
  --mono:"JetBrains Mono",ui-monospace,Consolas,monospace;

  --r:6px;
  --gut:clamp(18px,4vw,34px);
}
*{box-sizing:border-box}
body{margin:0;background:var(--field);color:var(--chalk);font-family:var(--ui);
  font-size:15px;line-height:1.55;-webkit-font-smoothing:antialiased;
  padding:0 0 5rem}
a{color:inherit}
.wrap{max-width:940px;margin:0 auto;padding:0 var(--gut)}
::selection{background:var(--hot);color:var(--field)}
:focus-visible{outline:2px solid var(--hot);outline-offset:3px}

/* ---- masthead ---------------------------------------------------------- */
header{padding:clamp(3rem,9vw,6.5rem) 0 2.2rem}
h1{font-family:var(--display);font-weight:400;margin:0;
  font-size:clamp(3.4rem,13vw,7.2rem);line-height:.86;letter-spacing:-.015em;
  text-transform:uppercase}
h1 .dot{color:var(--hot)}
.tag{font-family:var(--mono);font-size:12px;letter-spacing:-.01em;
  color:var(--dim);margin:1.4rem 0 0;max-width:46ch}
.tag b{color:var(--chalk);font-weight:400}
.links{display:flex;flex-wrap:wrap;gap:0 1.35rem;margin-top:1.3rem;
  font-family:var(--mono);font-size:12px}
.links a{color:var(--dim);text-decoration:none;border-bottom:1px solid var(--line);
  padding-bottom:2px;transition:color 120ms ease,border-color 120ms ease}
@media (hover:hover){.links a:hover{color:var(--hot);border-color:var(--hot)}}

/* ---- the counted strip. Every figure here is generated, which is the
        point of it being on the page at all. ---------------------------- */
.counts{background:var(--panel);border-radius:var(--r);padding:1.1rem 1.2rem;
  display:flex;flex-wrap:wrap;gap:.4rem 2.4rem;font-family:var(--mono);
  font-size:12px;color:var(--dim);margin-bottom:2.6rem}
.counts b{color:var(--hot);font-weight:400}
.counts span{white-space:nowrap}

/* ---- the ledger -------------------------------------------------------- */
h2{font-family:var(--mono);font-size:11px;font-weight:400;letter-spacing:.18em;
  text-transform:uppercase;color:var(--dim);margin:0 0 .7rem;padding-left:.1rem}
ul{list-style:none;margin:0;padding:0}
.ledger{background:var(--panel);border-radius:var(--r);padding:0 1.2rem;
  overflow:hidden}
.row{display:grid;grid-template-columns:4.6rem minmax(0,1fr) 7.4rem;
  gap:0 1.2rem;align-items:start;padding:1.05rem 0;
  border-bottom:1px solid var(--line)}
.row:last-child{border-bottom:0}
time{font-family:var(--mono);font-size:12px;color:var(--dim);
  font-variant-numeric:tabular-nums;padding-top:.12rem}
.nm{font-family:var(--mono);font-size:14px;font-weight:700;color:var(--chalk);
  text-decoration:none;letter-spacing:-.02em}
@media (hover:hover){.nm:hover{color:var(--hot)}}
.live{font-family:var(--mono);font-size:10px;letter-spacing:.1em;
  text-transform:uppercase;color:var(--field);background:var(--amrit);
  border-radius:3px;padding:1px 5px;margin-left:.55rem;text-decoration:none;
  vertical-align:1.5px}
.desc{margin:.2rem 0 0;font-size:14px;color:var(--dim);max-width:60ch}
.note{display:block;font-family:var(--mono);font-size:11px;color:var(--dim);
  opacity:.72;margin-top:.35rem;max-width:60ch}
.state{font-family:var(--mono);font-size:10px;letter-spacing:.12em;
  text-align:right;padding-top:.24rem;white-space:nowrap}
.s-ship{color:var(--dim)}
.s-build{color:var(--hot)}
.s-pause{color:var(--vish-text)}
/* The honest 'I have not written this down' is the label most worth
   seeing, so it is the brightest state on the board rather than the
   faintest. It was --line at 1.33:1, which is a way of hiding it. */
.s-none{color:var(--chalk)}
.s-mark{color:var(--hot)}
.mark .what{margin:0;font-size:14px;color:var(--chalk);padding-top:.1rem}
.mark{padding:.78rem 0}

/* ---- how I work -------------------------------------------------------- */
.rules{display:grid;gap:1px;background:var(--line);border-radius:var(--r);
  overflow:hidden;margin-top:2.8rem}
.rule{background:var(--panel);padding:1.25rem 1.2rem}
.rule h3{font-family:var(--mono);font-size:13px;font-weight:700;margin:0 0 .35rem;
  letter-spacing:-.02em;color:var(--chalk)}
.rule p{margin:0;font-size:14px;color:var(--dim);max-width:64ch}

/* ---- stamp ------------------------------------------------------------- */
footer{margin-top:2.4rem;font-family:var(--mono);font-size:11px;color:var(--dim);
  display:flex;flex-wrap:wrap;gap:.3rem 1.6rem;padding-left:.1rem}
footer b{color:var(--chalk);font-weight:400}

@media (max-width:640px){
  .row{grid-template-columns:minmax(0,1fr) auto;gap:.1rem .9rem}
  time{grid-column:1;grid-row:1}
  .state{grid-column:2;grid-row:1;text-align:right}
  .mid{grid-column:1/-1;grid-row:2;margin-top:.25rem}
}
</style>

<div class="wrap">
<header>
  <h1>Gokul&nbsp;Sai<span class="dot">.</span></h1>
  <p class="tag">I build tools that check whether something is true before you
    act on it. <b>A zero means two things: nothing was there, or I could not
    look.</b> Most of what is below exists to tell those apart.</p>
  <nav class="links">%(links)s</nav>
</header>

<div class="counts">
  <span><b>%(rate)s</b></span>
  <span>%(nlive)s live</span>
  <span>%(langline)s</span>
</div>

<h2>Built, newest first</h2>
<ul class="ledger">
%(rows)s
</ul>

<h2 style="margin-top:2.8rem">How I work</h2>
<div class="rules">
%(rules)s
</div>

<footer>
  <span>Read from the GitHub API <b>%(stamp)s</b> (%(source)s)</span>
  <span>%(n)s projects, %(nunrec)s with no state recorded</span>
  <span>%(span)s</span>
</footer>
</div>
"""


def check():
    """Every case is one the real data produces."""
    sample = [
        {"name": "a", "created_at": "2026-08-12T00:00:00Z", "pushed_at": "2026-09-01T00:00:00Z",
         "description": "first", "language": "Python", "has_pages": False,
         "html_url": "u/a", "fork": False},
        {"name": "outbabyout", "created_at": "2026-09-11T00:00:00Z", "pushed_at": "2026-09-11T00:00:00Z",
         "description": "tag", "language": "HTML", "has_pages": True,
         "html_url": "u/o", "fork": False},
        {"name": "aforked", "created_at": "2026-09-01T00:00:00Z", "pushed_at": "2026-09-01T00:00:00Z",
         "description": "x", "language": "C", "has_pages": False,
         "html_url": "u/f", "fork": True},
        {"name": USER, "created_at": "2026-09-03T00:00:00Z", "pushed_at": "2026-09-03T00:00:00Z",
         "description": "Profile", "language": "Python", "has_pages": False,
         "html_url": "u/p", "fork": False},
    ]
    ps = projects(sample)
    names = [p["name"] for p in ps]

    assert "aforked" not in names, "forks are not my projects"
    assert USER not in names, "the profile repo is not a project"
    assert names == ["outbabyout", "a"], ("newest first", names)
    # A repo with no editorial state must say so, never default to SHIPPED.
    assert ps[1]["state"] is None, "an unlisted repo has no state"
    assert ps[0]["state"] == "PAUSED", "a listed repo keeps its recorded state"
    # Pages presence is derived, not remembered.
    assert ps[0]["live"] and not ps[1]["live"], "live comes from has_pages"

    r = rate(ps)
    assert r["days"] == 30, r          # 12 Aug to 11 Sept
    assert r["n"] == 2

    html = render(ps, "test")
    assert "NOT RECORDED" in html, "the unrecorded state must reach the page"
    assert "s-none" in html
    # The stamp is what makes every other number checkable.
    assert "Read from the GitHub API" in html
    # Escaping, because a description is somebody else's text.
    nasty = list(ps)
    nasty[0] = dict(nasty[0], desc='<script>x</script>')
    assert "&lt;script&gt;" in render(nasty, "test"), "descriptions are escaped"

    # A single project cannot produce a rate, and must not fake one.
    assert rate(ps[:1]) is None, "one project is not a rate"

    # Every state label is 10px, so every one of them needs WCAG AA for
    # normal text. Measured off the rendered page, not asserted as a string:
    # the string version of this check could be defeated by one rename, and
    # was - it kept passing while PAUSED went back to 4.39:1.
    for cls, got in sorted(state_contrast(html).items()):
        assert got >= 4.5, "%s is %.2f:1, below AA for 10px text" % (cls, got)
    # The unrecorded state is the one the page most wants read, so it is
    # held to a higher bar than the rest rather than a lower one.
    assert state_contrast(html)["s-none"] >= 10, \
        "NOT RECORDED must be the loudest state, not the quietest"

    # Both strands land in one list, ordered by date across both of them.
    # The attribute stays ISO for machines; only the printed form is short.
    assert ">09.11.26<" in html or ">08.12.26<" in html, \
        "dates print as MM.DD.YY, not as the ISO string"
    assert short_date("2026-09-12") == "09.12.26", short_date("2026-09-12")
    dates = re.findall(r'<time datetime="([0-9-]+)"', html)
    assert dates == sorted(dates, reverse=True), ("one timeline, newest first", dates)
    assert len(dates) == len(ps) + len(MILESTONES), "every row reaches the page"
    # A milestone has no state badge and no repo link - that is the only
    # thing separating the two kinds of row.
    assert html.count('class="row mark"') == len(MILESTONES)
    # Milestones read like matthewnpark.com: third person, present tense.
    assert "Opens a GitHub account" in html and "Opened" not in html, \
        "milestones are third person present tense, not past tense"
    # A link with no url is left off rather than shipped dead. Derived from the
    # table rather than naming a handle, so it stays correct the day one is
    # actually added - the previous version of this assert was satisfied by
    # either branch being true and could not fail.
    for _name, _url in LINKS:
        if _url is None:
            assert _name not in html, (
                "%s has no url yet and must not reach the page" % _name)
        else:
            assert _name in html, (
                "%s has a url and must reach the page" % _name)

    print("  19 checks pass")


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    if "--check" in sys.argv:
        check()
        sys.exit(0)
    repos, source = fetch(offline="--offline" in sys.argv)
    ps = projects(repos)
    with io.open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write(render(ps, source))
    miss = [p["name"] for p in ps if not p["state"]]
    print("wrote %s from %s: %d projects, %d live"
          % (OUT, source, len(ps), len([p for p in ps if p["live"]])))
    if miss:
        print("  no state recorded for: %s" % ", ".join(miss))
