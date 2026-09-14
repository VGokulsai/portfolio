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

USER = "VGokulsai"
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
    "portfolio":        ("SHIPPED", "This page. Every number on it is read from the GitHub API."),
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
# The 2025 dates on the laptop, both football entries and the MUN are
# approximate: he confirmed on 14 Sept 2026 that all four happened in 2025 and
# chose placeholder dates because he does not remember the exact days. Replace
# any of them with the real date when it turns up. The GitHub date is exact.
MILESTONES = [
    ("2025-11-22", "Wins an MUN"),
    ("2025-08-08", "Opens a GitHub account"),
    ("2025-07-12", "Represents Hyderabad in a football match"),
    ("2025-04-19", "Plays his first football match"),
    ("2025-03-09", "Gets his first laptop"),
]

# One table so a handle is added in one place. url of None means "I do not
# have this yet" and it is left off the page rather than shipped dead.
LINKS = [
    ("GitHub",       "https://github.com/%s" % USER),
    ("Journal",      "https://%s.github.io/journal/" % USER.lower()),
    ("Out Baby Out", "https://%s.github.io/outbabyout/" % USER.lower()),
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
            "live": "https://%s.github.io/%s/" % (USER.lower(), r["name"]) if r.get("has_pages") else None,
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
    # Rows sit straight on the page ground now, not on a panel, so that is
    # the surface measured. Measuring against a colour the label never
    # touches would be the string-assert mistake again in a new form.
    panel = tokens.get("field")
    if not panel:
        raise AssertionError("no --field token in the page to measure against")
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


def render(ps, source, avatar=None):
    r = rate(ps)
    # What Linktree, WhatsApp and Instagram show when this page's link is
    # pasted: a title, one line, and a picture. None of them read the page
    # itself, only these tags. The picture is the GitHub avatar from the API
    # payload, so it follows the avatar. No avatar means no og:image tag at
    # all, rather than a preview pointing at nothing.
    og = ('<meta property="og:type" content="website">\n'
          '<meta property="og:title" content="Gokul Sai">\n'
          '<meta property="og:description" content="%s">\n'
          '<meta property="og:url" content="https://%s.github.io/portfolio/">'
          % (esc(TAGLINE), USER.lower()))
    if avatar:
        og += ('\n<meta property="og:image" content="%s">\n'
               '<meta name="twitter:card" content="summary">' % esc(avatar))
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    live = [p for p in ps if p["live"]]
    # Short codes in the bar, the way matthewnpark.com sets X IN IG TT YT. The
    # full name stays on the page as title and aria-label, so a screen reader
    # and a hover both get "Out Baby Out" rather than "OBO".
    codes = {"GitHub": "GH", "Journal": "JR", "Out Baby Out": "OBO",
             "Instagram": "IG", "LinkedIn": "IN", "Email": "@"}
    linkrow = "".join(
        '<a href="%s" title="%s" aria-label="%s">%s</a>'
        % (esc(u), esc(n), esc(n), esc(codes.get(n, n)))
        for n, u in LINKS if u)
    unrecorded = [p for p in ps if not p["state"]]

    entries = [dict(p, kind="build") for p in ps]
    entries += [{"kind": "mark", "created": d, "name": t, "desc": "",
                 "note": None, "state": None, "live": None, "url": None}
                for d, t in MILESTONES]
    entries.sort(key=lambda e: e["created"], reverse=True)

    rows = []
    for i, p in enumerate(entries):
        when = '<time datetime="%s">%s</time>' % (p["created"], short_date(p["created"]))
        if p["kind"] == "mark":
            rows.append('<li class="row mark" style="--i:%d">%s<p class="what">%s</p></li>'
                        % (i, when, esc(p["name"])))
            continue
        st = p["state"] or "NOT RECORDED"
        cls = {"SHIPPED": "s-ship", "BUILDING": "s-build",
               "PAUSED": "s-pause"}.get(p["state"], "s-none")
        live_a = (' <a class="live" href="%s">live</a>' % esc(p["live"])) if p["live"] else ""
        desc = ('<span class="desc">%s</span>' % esc(p["desc"])) if p["desc"] else ""
        # "Starts" because the date on the row is the day the repo was
        # created - it is the one verb the data can actually vouch for.
        rows.append(
            '<li class="row" style="--i:%d">%s<p class="what" title="%s">'
            'Starts <a href="%s">%s</a>%s<span class="state %s">%s</span>%s</p></li>'
            % (i, when, esc(p["note"] or p["desc"] or ""), esc(p["url"]),
               esc(p["name"]), live_a, cls, st, desc))

    rules = "".join(
        '<div class="rule"><h3>%s</h3><p>%s</p></div>' % (esc(t), esc(b))
        for t, b in RULES)

    ratebit = ("%d projects in %d days" % (r["n"], r["days"])) if r else "not enough to measure"
    unrec = (" &middot; %d with no state recorded" % len(unrecorded)) if unrecorded else ""

    return TEMPLATE % {
        "rows": "\n".join(rows),
        "rules": rules,
        "rate": ratebit,
        "unrec": unrec,
        "stamp": stamp,
        "source": source,
        "year": stamp[:4],
        "links": linkrow,
        "tagline": esc(TAGLINE),
        "og": og,
    }


TAGLINE = "I build tools that check whether something is true before you act on it. Hyderabad."

TEMPLATE = """<title>Gokul Sai</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="%(tagline)s">
%(og)s
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Anton&family=Instrument+Sans:wght@400;500&family=JetBrains+Mono:wght@400;700&display=swap">
<style>
/* ----------------------------------------------------------------------------
   Palette and faces are Out Baby Out's, read out of that repo: the field, the
   chalk, the hot accent, and vish / amrit, which keep the jobs the game gives
   them.

   The layout follows matthewnpark.com, measured at 1280x800 on 14 Sept 2026:
   a wordmark top left and short text links top right at a 32px margin; a list
   with no rules or panels where every row is a grey mono date and one 12px
   line, 16px tall, rows 32px apart, 104px from date to text; the key word in
   each line underlined as a link; a large thin outline monogram behind it all;
   a footer bar with the year on the left and a live clock on the right. What
   stays ours: the dark ground, the game's faces, "Starts <repo>" rows with an
   honest state on each, and a footer that says when the numbers were read.
   ------------------------------------------------------------------------- */
:root{
  --field:#0F1310; --panel:#191E17; --line:#2C352A;
  --chalk:#F2F4E9; --dim:#8C9682;
  --hot:#E8FF3F; --vish:#E0523B; --amrit:#5FD08A;
  /* vish as the game paints it measures under AA at 10px; same hue, a touch
     lighter, so the paused label can actually be read. */
  --vish-text:#E46955;

  --display:Anton,"Arial Narrow",sans-serif;
  --ui:"Instrument Sans",system-ui,sans-serif;
  --mono:"JetBrains Mono",ui-monospace,Consolas,monospace;

  --ease:cubic-bezier(.2,.8,.2,1);
  --r:6px;
}
*{box-sizing:border-box}
body{margin:0;background:var(--field);color:var(--chalk);font-family:var(--ui);
  font-size:12px;line-height:16px;letter-spacing:-.01em;
  -webkit-font-smoothing:antialiased}
a{color:inherit}
::selection{background:var(--hot);color:var(--field)}
:focus-visible{outline:2px solid var(--hot);outline-offset:3px}

/* ---- the monogram: thin outline, behind everything, never in the way ---- */
.monogram{position:fixed;right:7vw;top:50%%;transform:translateY(-52%%);
  font-family:var(--display);font-size:min(52vh,36vw);line-height:.8;
  letter-spacing:.02em;color:transparent;-webkit-text-stroke:1px var(--hot);
  opacity:.28;pointer-events:none;user-select:none;z-index:0}

.page{position:relative;z-index:1;min-height:100vh;display:flex;
  flex-direction:column;padding:32px}
.bar{display:flex;align-items:center;justify-content:space-between;gap:16px}

.word{font-family:var(--display);font-size:24px;line-height:24px;
  text-transform:uppercase;letter-spacing:.01em;text-decoration:none}
.word .dot{color:var(--hot)}
.links{display:flex;gap:22px;font-family:var(--mono);font-size:12px}
/* The codes are 16px tall, which is a missed tap on a phone. Padding with an
   equal negative margin gives each one a 44px hit area without moving a pixel
   of the layout. */
.links a{text-decoration:none;color:var(--chalk);transition:color 120ms ease;
  display:inline-block;padding:14px 4px;margin:-14px -4px}
@media (hover:hover){.links a:hover{color:var(--hot)}}

main{flex:1;padding:40px 0 32px}

/* The one line of introduction, which opens into the three rules. */
.about{margin:0 0 32px;max-width:600px}
.about summary{cursor:pointer;color:var(--dim);list-style:none;width:fit-content}
.about summary::-webkit-details-marker{display:none}
.about summary::after{content:" +";color:var(--hot)}
.about[open] summary::after{content:" \\2212"}
.rules{display:grid;gap:12px;margin-top:16px}
.rule h3{font:700 12px/16px var(--mono);margin:0;color:var(--chalk)}
.rule p{margin:2px 0 0;color:var(--dim);max-width:60ch}

/* ---- the ledger ---------------------------------------------------------- */
ul{list-style:none;margin:0;padding:0}
.ledger{display:flex;flex-direction:column;gap:16px}
.row{display:flex;align-items:baseline;gap:104px;min-width:0;
  animation:rise .5s var(--ease) both;animation-delay:calc(var(--i) * 35ms)}
time{flex:none;font-family:var(--mono);color:var(--dim);white-space:nowrap;
  font-variant-numeric:tabular-nums}
.what{margin:0;min-width:0;max-width:min(78ch,58vw);white-space:nowrap;
  overflow:hidden;text-overflow:ellipsis;color:var(--chalk)}
.what > a:not(.live){text-decoration:underline;text-decoration-color:var(--dim);
  text-underline-offset:3px;transition:color 120ms ease;
  padding:8px 0;margin:-8px 0}  /* 32px tap height: the most rows 32px apart allow without overlap */
@media (hover:hover){.what > a:not(.live):hover{color:var(--hot);
  text-decoration-color:var(--hot)}}
.live{font-family:var(--mono);font-size:10px;letter-spacing:.1em;
  text-transform:uppercase;color:var(--field);background:var(--amrit);
  border-radius:3px;padding:1px 5px;margin-left:6px;text-decoration:none;line-height:1}
/* line-height:1 on the small inline labels, or their own line box stretches
   the 16px row to 17 and the 32px rhythm drifts to 33. Measured, not assumed. */
.state{font-family:var(--mono);font-size:10px;line-height:1;letter-spacing:.12em;margin-left:12px}
.s-ship{color:var(--dim)}
.s-build{color:var(--hot)}
.s-pause{color:var(--vish-text)}
/* The honest 'I have not written this down' is the brightest state, not the
   faintest. Hiding it would be the opposite of the point. */
.s-none{color:var(--chalk)}
.desc{color:var(--dim);margin-left:12px}

/* ---- footer bar ---------------------------------------------------------- */
.foot{color:var(--dim);flex-wrap:wrap}
.foot .mid{text-align:center}
.foot b{color:var(--chalk);font-weight:400;font-variant-numeric:tabular-nums}

@keyframes rise{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:none}}
@media (prefers-reduced-motion:reduce){.row{animation:none}}

@media (max-width:640px){
  .page{padding:20px}
  .row{gap:20px}
  .what{max-width:none}
  .desc{display:none}
  .links{gap:14px}
  .foot{flex-direction:column;align-items:flex-start;gap:6px}
  .foot .mid{text-align:left}
  .monogram{right:-6vw;font-size:58vw;opacity:.18}
}
</style>

<div class="monogram" aria-hidden="true">GS</div>
<div class="page">
<header class="bar">
  <a class="word" href="./">Gokul<span class="dot">.</span></a>
  <nav class="links">%(links)s</nav>
</header>

<main>
<details class="about">
  <summary>%(tagline)s</summary>
  <div class="rules">
%(rules)s
  </div>
</details>

<ul class="ledger">
%(rows)s
</ul>
</main>

<footer class="bar foot">
  <span>&copy; %(year)s Gokul Sai</span>
  <span class="mid">%(rate)s &middot; Read from the GitHub API %(stamp)s (%(source)s)%(unrec)s</span>
  <span id="clock-wrap" hidden>Hyderabad <b id="clock"></b></span>
</footer>
</div>

<script>
/* A live Hyderabad clock, bottom right. Hidden without JavaScript rather than
   showing a time that never moves. */
(function () {
  var wrap = document.getElementById("clock-wrap");
  var el = document.getElementById("clock");
  if (!wrap || !el || !window.Intl) return;
  var fmt = new Intl.DateTimeFormat("en-GB", {timeZone: "Asia/Kolkata",
    hour: "2-digit", minute: "2-digit", hour12: false});
  function tick() { el.textContent = fmt.format(new Date()); }
  tick();
  wrap.hidden = false;
  setInterval(tick, 15000);
})();
</script>
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

    # Link previews. Linktree builds the thumbnail and title from these tags.
    withpic = render(ps, "test", "https://avatars.example/u/1?v=4")
    assert '<meta property="og:image" content="https://avatars.example/u/1?v=4">' in withpic, \
        "the avatar becomes the preview picture"
    assert 'property="og:title"' in withpic and 'property="og:description"' in withpic, \
        "a preview needs a title and a line, not just a picture"
    # No avatar, no og:image tag at all - never a preview pointing nowhere.
    assert "og:image" not in html, "no avatar means no preview picture tag"

    # Repo rows use the one verb the created date can vouch for.
    assert re.search(r'Starts <a href="u/a">a</a>', html), "build rows read 'Starts <repo>'"
    # The monogram is decoration and must never be announced or clicked.
    assert '<div class="monogram" aria-hidden="true">' in html, "monogram is aria-hidden"
    # The clock starts hidden, so a page without JavaScript never shows a
    # frozen time.
    assert '<span id="clock-wrap" hidden>' in html, "clock is hidden until JS runs"

    print("  25 checks pass")


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
    avatar = next((r["owner"]["avatar_url"] for r in repos
                   if (r.get("owner") or {}).get("avatar_url")), None)
    with io.open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write(render(ps, source, avatar))
    miss = [p["name"] for p in ps if not p["state"]]
    print("wrote %s from %s: %d projects, %d live"
          % (OUT, source, len(ps), len([p for p in ps if p["live"]])))
    if miss:
        print("  no state recorded for: %s" % ", ".join(miss))
