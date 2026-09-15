"""Generate index.html: a dated list of things that happened, like
matthewnpark.com, set in Out Baby Out's colours.

    py -3 build.py            write index.html
    py -3 build.py --check    run the self-checks
    py -3 build.py --offline  build from the cached payload, no network

The rows are MILESTONES, written by hand. The GitHub API supplies only what it
can vouch for: the project count in the footer and the preview picture, and
the footer stamps when that was read. Repos are not rows any more - one line
per repo was too small to say anything, and the GH link covers them.
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

SKIP = {USER}  # the profile repo is not a project

# The page. Oldest first, third person, present tense, one short line, no
# adjectives - the way matthewnpark.com writes them:
#
#     ("2026-09-21", "Turns 16"),
#
# Present tense is only the voice. Every entry must already have happened.
# Every date except the GitHub one is approximate. He confirmed each of these
# happened but does not remember the exact days, so he chose placeholder dates
# (14-15 Sept 2026): representing Hyderabad, the laptop and the MUN in 2025 -
# the laptop placed just before the GitHub account because one led to the other -
# his first football match and starting guitar on the same day in 2023.
# Replace any of them with the real date when it turns up.
MILESTONES = [
    ("2025-11-22", "Wins an MUN"),
    ("2025-08-08", "Opens a GitHub account"),
    ("2025-07-12", "Represents Hyderabad in a football match"),
    ("2023-04-19", "Plays his first football match"),
    ("2023-04-19", "Starts learning guitar"),
    ("2025-07-26", "Gets his first laptop"),
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

# Three things to show a stranger first, in plain words. Picked 15 Sept 2026 as
# his most finished public work: the live game, the main tool, the journal.
# (kind, name, url, one plain line)
WORK = [
    ("Game", "Out Baby Out", "https://%s.github.io/outbabyout/" % USER.lower(),
     "Real-life tag with a revive. Twenty minutes, two sides, nobody is out for good."),
    ("Tool", "painpoint-finder", "https://github.com/%s/painpoint-finder" % USER,
     "Searches six public sources for people who already have the problem you want "
     "to solve, and drafts a first message you edit and send yourself."),
    ("Writing", "Journal", "https://%s.github.io/journal/" % USER.lower(),
     "What broke, what it cost, and what I would do differently."),
]

# What I actually believe, kept to the three that changed how I build.
RULES = [
    ("A zero means two things",
     "Nothing was there is a result. I could not look is not. Any count that "
     "cannot tell you which one it is has told you nothing."),
    ("Never type a number that can be read",
     "The project count on this page was read from GitHub, and the stamp at the "
     "bottom says when. Counts of repos, tests and sources all go stale."),
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
    """Own repos only, newest first. Only the name and creation day are kept,
    because that is all the footer count uses."""
    out = [{"name": r["name"], "created": r["created_at"][:10]}
           for r in repos if not r.get("fork") and r["name"] not in SKIP]
    out.sort(key=lambda p: p["created"], reverse=True)
    return out


def rate(ps):
    """Repos across the span actually worked, not since the account opened. An
    account opened in 2025 and used from August 2026 would otherwise report a
    span that flatters by a year."""
    if len(ps) < 2:
        return None
    first = date.fromisoformat(min(p["created"] for p in ps))
    last = date.fromisoformat(max(p["created"] for p in ps))
    days = (last - first).days
    if days <= 0:
        return None
    return {"days": days, "n": len(ps)}


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

    # Spelled out, not coded. GH and IG are guessable; JR and OBO mean nothing
    # to someone who has never met him, and that is exactly who this is for.
    linkrow = "".join('<a href="%s">%s</a>' % (esc(u), esc(n)) for n, u in LINKS if u)

    work = "\n".join(
        '<li class="row job"><span class="kind">%s</span><p class="what">'
        '<a href="%s">%s</a> <span class="line">%s</span></p></li>'
        % (esc(k), esc(u), esc(n), esc(line)) for k, n, u, line in WORK)

    rows = "\n".join(
        '<li class="row" style="--i:%d"><time datetime="%s">%s</time>'
        '<p class="what">%s</p></li>' % (i, d, short_date(d), esc(t))
        for i, (d, t) in enumerate(sorted(MILESTONES)))  # oldest first: dates climb down the page

    rules = "".join(
        '<div class="rule"><h3>%s</h3><p>%s</p></div>' % (esc(t), esc(b))
        for t, b in RULES)

    ratebit = ("%d projects in %d days" % (r["n"], r["days"])) if r else ""
    # The one number a client cares about, said plainly at the top. With no
    # rate to report the sentence is left out rather than filled with filler.
    hire = ("<b>%s.</b> " % ratebit) if ratebit else ""
    cache_note = " (from a saved copy, not live)" if source == "cache" else ""

    return TEMPLATE % {
        "rows": rows,
        "work": work,
        "hire": hire,
        "cache_note": cache_note,
        "rules": rules,
        "rate": ratebit,
        "stamp": stamp,
        "source": source,
        "year": stamp[:4],
        "links": linkrow,
        "tagline": esc(TAGLINE),
        "og": og,
        "user": USER,
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
   Palette and faces are Out Baby Out's, read out of that repo.

   The layout follows matthewnpark.com, measured at 1280x800 on 14 Sept 2026:
   a wordmark top left and short text links top right at a 32px margin; a list
   with no rules or panels where every row is a grey mono date and one 12px
   line, 16px tall, rows 32px apart, 104px from date to text; a large thin
   outline monogram behind it all; a footer bar with the year on the left and a
   live clock on the right. What stays ours: the dark ground, the game's faces,
   and a footer that says when its one number was read.
   ------------------------------------------------------------------------- */
:root{
  --field:#0F1310; --panel:#191E17; --line:#2C352A;
  --chalk:#F2F4E9; --dim:#8C9682;
  --hot:#E8FF3F; --vish:#E0523B; --amrit:#5FD08A;

  --display:Anton,"Arial Narrow",sans-serif;
  --ui:"Instrument Sans",system-ui,sans-serif;
  --mono:"JetBrains Mono",ui-monospace,Consolas,monospace;

  --ease:cubic-bezier(.2,.8,.2,1);
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

/* The intro paragraph and the three rules, kept from the first version of
   this page and shown in full rather than folded behind a click. */
.tag{margin:0 0 12px;max-width:56ch;color:var(--dim)}
.hire{margin:0 0 8px;color:var(--chalk)}
.hire b{font-weight:500}
.hire a,.what a{text-decoration:underline;text-decoration-color:var(--dim);
  text-underline-offset:3px;transition:color 120ms ease,text-decoration-color 120ms ease}
@media (hover:hover){.hire a:hover,.what a:hover{color:var(--hot);text-decoration-color:var(--hot)}}
.tag b{color:var(--chalk);font-weight:500}
.sec{margin-top:32px}
.how{max-width:600px}
.sec h2{font:400 10px/16px var(--mono);letter-spacing:.14em;
  text-transform:uppercase;color:var(--dim);margin:0 0 12px}
.work{display:flex;flex-direction:column;gap:16px}
/* The kind column is as wide as a date, so Work and Timeline share one edge. */
time,.kind{min-width:58px}
.kind{flex:none;font-family:var(--mono);color:var(--dim)}
.line{color:var(--dim)}
.rules{display:grid;gap:12px}
.rule h3{font:700 12px/16px var(--mono);margin:0;color:var(--chalk)}
.rule p{margin:2px 0 0;color:var(--dim);max-width:60ch}

/* ---- the list ------------------------------------------------------------ */
ul{list-style:none;margin:0;padding:0}
.ledger{display:flex;flex-direction:column;gap:16px}
.row{display:flex;align-items:baseline;gap:104px;min-width:0;
  animation:rise .5s var(--ease) both;animation-delay:calc(var(--i) * 35ms)}
time{flex:none;font-family:var(--mono);color:var(--dim);white-space:nowrap;
  font-variant-numeric:tabular-nums}
.what{margin:0;min-width:0;max-width:min(78ch,58vw);color:var(--chalk)}

/* ---- footer bar ---------------------------------------------------------- */
.foot{color:var(--dim);flex-wrap:wrap}
.foot .mid{text-align:center}
.foot a{text-decoration-color:var(--dim);text-underline-offset:3px}
.foot b{color:var(--chalk);font-weight:400;font-variant-numeric:tabular-nums}

@keyframes rise{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:none}}
@media (prefers-reduced-motion:reduce){.row{animation:none}}

@media (max-width:640px){
  .page{padding:20px}
  .row{gap:20px}
  .what{max-width:none}
  header.bar{flex-wrap:wrap;row-gap:14px}
  /* 28px between wrapped rows: each link has a 44px tap area on a 16px line,
     so anything tighter lets a tap between rows land on the wrong link. */
  .links{gap:28px 18px;flex-wrap:wrap}
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
<p class="tag">I build tools that check whether something is true before you
  act on it. <b>A zero means two things: nothing was there, or I could not
  look.</b> Most of what I build exists to tell those apart.</p>
<p class="hire">%(hire)sWant something built? <a href="mailto:gokulsai1004@gmail.com">gokulsai1004@gmail.com</a></p>

<section class="sec">
  <h2>Work</h2>
  <ul class="work">
%(work)s
  </ul>
</section>

<section class="sec">
  <h2>Timeline</h2>
  <ul class="ledger">
%(rows)s
  </ul>
</section>

<section class="sec how">
  <h2>How I work</h2>
  <div class="rules">
%(rules)s
  </div>
</section>
</main>

<footer class="bar foot">
  <span>&copy; %(year)s Gokul Sai</span>
  <span class="mid">Project count read from GitHub %(stamp)s%(cache_note)s</span>
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
    global MILESTONES
    sample = [
        {"name": "a", "created_at": "2026-08-12T00:00:00Z", "fork": False},
        {"name": "outbabyout", "created_at": "2026-09-11T00:00:00Z", "fork": False},
        {"name": "aforked", "created_at": "2026-09-01T00:00:00Z", "fork": True},
        {"name": USER, "created_at": "2026-09-03T00:00:00Z", "fork": False},
    ]
    ps = projects(sample)
    names = [p["name"] for p in ps]

    assert "aforked" not in names, "forks are not my projects"
    assert USER not in names, "the profile repo is not a project"
    assert names == ["outbabyout", "a"], ("newest first", names)

    r = rate(ps)
    assert r == {"days": 30, "n": 2}, r          # 12 Aug to 11 Sept
    # A single project cannot produce a rate, and must not fake one.
    assert rate(ps[:1]) is None, "one project is not a rate"

    html = render(ps, "test")
    # The stamp is what makes the one number on the page checkable.
    assert "read from GitHub" in html
    assert "2 projects in 30 days" in html, "the footer count comes from the API data"

    # Repos are not rows any more. Nothing from a repo reaches the list.
    ledger = html[html.index('<ul class="ledger">'):html.index("</ul>", html.index('<ul class="ledger">'))]
    assert "outbabyout" not in ledger and "Starts <a" not in ledger, "no repo rows"
    assert ledger.count('<li class="row"') == len(MILESTONES), "every milestone is a row"

    # Oldest first, so the story reads in order and the month-first dates
    # visibly climb. Dates print MM.DD.YY with ISO kept for machines.
    assert short_date("2026-09-12") == "09.12.26", short_date("2026-09-12")
    dates = re.findall(r'<time datetime="([0-9-]+)"', ledger)
    assert dates == sorted(dates), ("oldest first", dates)
    assert ">%s<" % short_date(dates[0]) in ledger, "dates print as MM.DD.YY"
    # Milestones read like matthewnpark.com: third person, present tense.
    assert "Opens a GitHub account" in ledger and "Opened" not in ledger, \
        "milestones are third person present tense, not past tense"

    # A milestone is typed by hand, so it is escaped like anyone's text.
    saved = MILESTONES
    try:
        MILESTONES = [("2026-01-01", "<script>x</script>")]
        assert "&lt;script&gt;" in render(ps, "test"), "milestones are escaped"
    finally:
        MILESTONES = saved

    # A link with no url is left off rather than shipped dead; one with a url
    # reaches the page. Derived from the table so it stays right when a handle
    # is added.
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

    # The monogram is decoration and must never be announced or clicked.
    assert '<div class="monogram" aria-hidden="true">' in html, "monogram is aria-hidden"
    # The clock starts hidden, so a page without JavaScript never shows a
    # frozen time.
    assert '<span id="clock-wrap" hidden>' in html, "clock is hidden until JS runs"

    # The intro paragraph and the rules are on the page, not folded away.
    assert '<p class="tag">' in html and "<details" not in html, "intro and rules are visible"
    assert html.count('<div class="rule">') == len(RULES), "every rule reaches the page"

    # Work: every item reaches the page and links where it says it does.
    wstart = html.index('<ul class="work">')
    workhtml = html[wstart:html.index("</ul>", wstart)]
    assert workhtml.count('<li class="row job"') == len(WORK), "every work item is shown"
    assert all('href="%s"' % u in workhtml for _k, _n, u, _l in WORK), "work links go where they say"
    # A stranger can reach him without decoding anything.
    assert 'href="mailto:gokulsai1004@gmail.com">gokulsai1004@gmail.com</a>' in html, \
        "the email is written out on the page"
    assert ">OBO<" not in html and ">JR<" not in html and ">@<" not in html, "links are spelled out"
    # A build from the saved copy says so on the page.
    assert "saved copy" in render(ps, "cache") and "saved copy" not in html, "cache builds are labelled"

    print("  28 checks pass")


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
    print("wrote %s from %s: %d milestones, %d projects counted"
          % (OUT, source, len(MILESTONES), len(ps)))
