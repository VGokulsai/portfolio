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

# The page. Newest first, third person, present tense, one short line, no
# adjectives - the way matthewnpark.com writes them:
#
#     ("2026-09-21", "Turns 16"),
#
# Present tense is only the voice. Every entry must already have happened.
# Every date except the GitHub one is approximate. He confirmed each of these
# happened but does not remember the exact days, so he chose placeholder dates
# (14-15 Sept 2026): starting guitar, representing Hyderabad, the laptop and
# the MUN in 2025 - the laptop placed just before the GitHub account because one
# led to the other - and his first football match in 2023.
# Replace any of them with the real date when it turns up.
MILESTONES = [
    ("2026-09-28", "Publishes a reproduction of an IIIT-Hyderabad paper"),
    ("2026-09-25", "Starts Banyan"),
    ("2026-09-18", "Publishes his first paper"),
    ("2025-11-22", "Wins an MUN"),
    ("2025-08-08", "Opens a GitHub account"),
    ("2025-07-12", "Represents Hyderabad in a football match"),
    ("2023-04-19", "Plays his first football match"),
    ("2025-04-19", "Starts learning guitar"),
    ("2025-07-26", "Gets his first laptop"),
]

# One table so a handle is added in one place. url of None means "I do not
# have this yet" and it is left off the page rather than shipped dead.
LINKS = [
    ("GitHub",       "https://github.com/%s" % USER),
    ("Banyan",       "https://banyanmakers.pages.dev"),
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
    ("Community", "Banyan", "https://banyanmakers.pages.dev",
     "A free page where young makers in India are seen for what they have shipped. "
     "Every maker is checked by hand."),
    ("Game", "Out Baby Out", "https://%s.github.io/outbabyout/" % USER.lower(),
     "Real-life tag with a revive, made so children in orphanages and children's homes "
     "can have fun together. Twenty minutes, two sides, nobody is out for good."),
    ("Paper", "Reproducing an IIIT-Hyderabad paper",
     "https://github.com/VGokulsai/nllb-entity-mt/blob/master/paper/report-v1.pdf",
     "Fine-tuned a translation model to get names right, as a SemEval-2025 paper did: "
     "+5 BLEU on 5,338 sentences. Written up with a DOI."),
    ("Tool", "painpoint-finder", "https://github.com/%s/painpoint-finder" % USER,
     "Searches six public sources for people who already have the problem you want "
     "to solve, and drafts a first message you edit and send yourself."),
    ("Writing", "Journal", "https://%s.github.io/journal/" % USER.lower(),
     "What broke, what it cost, and what I would do differently."),
    ("Paper", "Empty Is Not Unreachable", "https://github.com/VGokulsai/falsezero/blob/master/PAPER.md",
     "Forty public sources measured: the four ways a program reports nothing found "
     "when it simply failed to look. Published, with a DOI."),
]

# His real sketchbook pages (25 Oct 2026), cleaned from phone photos by
# ~/sketchbook/clean.py: light and colour cast fixed, his lines untouched.
# Opens as a page-flip book over the page. Songs join this section later.
with io.open("sketchbook/pages.json", encoding="utf-8") as _f:
    SKETCH = json.load(_f)
SKETCH_LINE = "My new sketchbook: a cast of characters with their own bios, and some fashion sketches."
SKETCH_COVER = 2  # The Fool, taped on the cover like a sticker

# Records in the crate: his list of 25 Oct 2026 (DEMO until real players are in).
# (title, artist, sleeve, ink)
RECORDS = [
    ("Shape of You", "Ed Sheeran", "#E8FF3F", "#0F1310"),
    ("Kala Chashma", "Amar Arshi, Badshah, Neha Kakkar", "#E0523B", "#F2F4E9"),
    ("Red Red", "", "#5FD08A", "#0F1310"),
    ("Gangnam Style", "PSY", "#F2F4E9", "#0F1310"),
    ("Love Nwantiti", "CKay", "#1F55C6", "#F2F4E9"),
    ("Mi Gente", "J Balvin, Willy William", "#0F1310", "#E8FF3F"),
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

    # The sketchbook lives on its own page (art/); here it is one row like the rest.
    # His name for it (25 Oct 2026). The counts come from the files.
    art = ('<li class="row job"><span class="kind">Art</span><p class="what">'
           '<a href="art/">the artistic side of meeee</a> <span class="line">%d sketches and %d songs on repeat.</span></p></li>'
           % (len(SKETCH), len(RECORDS)))

    rows = "\n".join(
        '<li class="row" style="--i:%d"><time datetime="%s">%s</time>'
        '<p class="what">%s</p></li>' % (i, d, short_date(d), esc(t))
        for i, (d, t) in enumerate(sorted(MILESTONES, reverse=True)))  # newest first, 2025 at the top

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
        "art": art,
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

TEMPLATE = """<meta charset="utf-8">
<title>Gokul Sai</title>
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
  <h2>Art</h2>
  <ul class="work">
%(art)s
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
</script>
"""


# ---- art/: his own page for the things he makes that aren't code ------------
ART_OUT = "art/index.html"


def closed_book(pre):
    """The closed spiral sketchbook. `pre` reaches the site root from the page.
    book.js copies this cover onto the open book, so there is one cover."""
    stick = lambda i: '<span class="cv-st s%d"><img src="%s%s" alt="" loading="lazy"></span>' % (
        i + 1, pre, esc(SKETCH[(SKETCH_COVER, 1)[i]]["src"]))
    return ('<button class="sketch3d" type="button" data-page="1" aria-label="Open the sketchbook">'
            '<span class="b3"><span class="b3-back"></span><span class="b3-edge b3-right"></span>'
            '<span class="b3-edge b3-top"></span><span class="b3-edge b3-bottom"></span>'
            '<span class="b3-first"><img src="%s%s" alt="" loading="lazy"></span>'
            '<span class="b3-cover cv"><span class="cv-t">Sketch<br>book<b>.</b></span>%s%s'
            '<span class="cv-dot">%d<br>pages</span>'
            '<span class="cv-m">Gokul Sai &middot; vol. 01</span><span class="cv-band"></span></span>'
            '<span class="b3-rings" aria-hidden="true">%s</span></span>'
            '<span class="b3-shadow" aria-hidden="true"></span></button>'
            % (pre, esc(SKETCH[0]["src"]), stick(1), stick(0), len(SKETCH), "<i></i>" * 11))


def sleeves():
    tilt = ("-3deg", "2deg", "-1deg", "3deg", "-2deg", "1deg")
    return "".join(
        '<button class="sleeve" type="button" style="--i:%d;--tilt:%s;--c:%s;--ink:%s" data-title="%s" data-artist="%s"'
        ' aria-label="Play %s"><span class="sleeve-face"><b>%s</b><i>%s</i></span></button>'
        % (i, tilt[i % len(tilt)], c, ink, esc(t), esc(a), esc(t), esc(t), esc(a.split(",")[0]) if a else "&nbsp;")
        for i, (t, a, c, ink) in enumerate(RECORDS))


def render_art():
    # The page shares the home page's stylesheet and clock, lifted out of TEMPLATE
    # (whose % signs are doubled for formatting) so the two can never drift apart.
    style = TEMPLATE[TEMPLATE.index("<style>") + 7:TEMPLATE.index("</style>")].replace("%%", "%")
    clock = TEMPLATE[TEMPLATE.index("<script>"):TEMPLATE.index("</script>") + 9]
    links = "".join('<a href="%s">%s</a>' % (esc(u), esc(n)) for n, u in LINKS if u)
    pages = json.dumps([{"src": "../" + p["src"], "alt": p["alt"], "w": p["w"], "h": p["h"], "nobind": p.get("nobind", False)} for p in SKETCH]).replace("</", "<\\/")
    page = ART_TEMPLATE
    for key, val in (("style", style), ("clock", clock), ("links", links), ("book", closed_book("../")),
                     ("line", esc(SKETCH_LINE)), ("n", str(len(SKETCH))), ("pages", pages), ("sleeves", sleeves()), ("nrec", str(len(RECORDS))),
                     ("year", str(date.today().year))):
        page = page.replace("{{%s}}" % key, val)
    return page


ART_TEMPLATE = """<meta charset="utf-8">
<title>Art · Gokul Sai</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="Gokul Sai's sketchbook: open it and turn the pages.">
<meta property="og:title" content="Art · Gokul Sai">
<meta property="og:description" content="His sketchbook: open it and turn the pages.">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Anton&family=Instrument+Sans:wght@400;500&family=JetBrains+Mono:wght@400;700&display=swap">
<link rel="stylesheet" href="../sketchbook/book.css">
<link rel="stylesheet" href="../records/records.css">
<style>{{style}}
/* ---- the art page: his loud side. Two full-bleed colour bands (lime for the
   sketches, his crayon pink for the songs), his own lines as the headlines,
   a black sticker for the aside, and hand-drawn sparkles in the margins. ---- */
.page{overflow-x:clip}  /* the tilted sheets must not scroll the page sideways */
.art{--band:var(--hot);position:relative;display:grid;grid-template-columns:minmax(0,1fr) auto;gap:clamp(32px,6vw,96px);
  align-items:center;margin:0 -32px;padding:clamp(56px,7vw,104px) 32px;
  background:radial-gradient(var(--dots) 1.1px,transparent 1.5px) 0 0/13px 13px,var(--band)}
.art.sketches{--band:var(--hot);--dots:rgba(15,19,16,.09);color:#0F1310;min-height:calc(100dvh - 120px);
  margin-top:28px;transform:rotate(-.6deg);z-index:1}
.art.sketches > *{transform:rotate(.6deg)}
.art.records{--band:#C2255C;--dots:rgba(0,0,0,.12);color:var(--chalk);grid-template-columns:1fr;gap:28px;
  margin-top:2px;margin-bottom:40px;transform:rotate(.5deg);z-index:2}
.art.records > *{transform:rotate(-.5deg)}
.art > .torn,.art > .tape{transform:none}
/* torn paper along the top and bottom of each band */
.torn{position:absolute;left:0;width:100%;height:30px;fill:var(--band);pointer-events:none}
.torn.top{top:-29px}
.torn.bottom{bottom:-29px;scale:1 -1}
/* masking tape holding the sheets down */
.tape{position:absolute;width:118px;height:30px;background:rgba(239,237,227,.82);z-index:3;pointer-events:none;
  box-shadow:0 2px 4px rgba(0,0,0,.18);
  -webkit-mask:linear-gradient(90deg,transparent 0 3px,#000 3px calc(100% - 3px),transparent calc(100% - 3px)),
    repeating-linear-gradient(0deg,#000 0 3px,transparent 3px 5px);-webkit-mask-composite:source-over}
.tape.t1{top:-40px;left:9%;rotate:-7deg}
.tape.t2{top:-44px;right:14%;rotate:5deg}
.tape.t3{bottom:-42px;left:22%;rotate:-4deg}
.art.records h2{max-width:none}
.art.records .rec-stage{justify-content:start}
.art .label{margin:0 0 14px;font:700 11px/16px var(--mono);letter-spacing:.14em;text-transform:uppercase}
.art h1,.art h2{font:400 clamp(52px,8vw,124px)/.86 var(--display);text-transform:uppercase;letter-spacing:.01em;
  margin:0 0 22px;max-width:10ch}
.art .aside{display:inline-block;margin:0 0 22px;padding:9px 13px;background:#0F1310;color:var(--hot);
  font:700 14px/18px var(--mono);transform:rotate(-2deg);box-shadow:0 6px 14px rgba(0,0,0,.25)}
.art.records .aside{color:var(--chalk)}
.art .tag{margin:0 0 6px;max-width:44ch;color:inherit;font-size:14px;line-height:20px}
.art .meta{margin:0;font-family:var(--mono);opacity:.78}
.art .home{display:inline-block;margin-top:26px;font-family:var(--mono);color:inherit;
  text-decoration:underline;text-decoration-thickness:2px;text-underline-offset:4px}
.art.sketches :focus-visible{outline-color:#0F1310}
@media (hover:hover){.art .home:hover{text-decoration-style:wavy}}
.art .now{color:inherit;opacity:.9}.art .now b{color:inherit;font-weight:700}
.art .sketch3d{--bw:clamp(240px,26vw,340px)}
.art .stage{padding:20px 48px 56px 24px}
/* hand-drawn sparkles and squiggles in the margins */
.doodle{position:absolute;fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round;stroke-linejoin:round;pointer-events:none;opacity:.85}
.doodle.a{width:34px;left:46%;top:14%;transform:rotate(12deg)}
.doodle.b{width:22px;left:4%;bottom:12%;transform:rotate(-8deg)}
.doodle.c{width:70px;right:6%;top:9%;transform:rotate(-6deg)}
.doodle.d{width:28px;right:38%;bottom:10%;transform:rotate(18deg)}
.doodle.e{width:80px;left:34%;bottom:16%;transform:rotate(4deg)}
@media (prefers-reduced-motion:no-preference){
  .doodle.a,.doodle.d{animation:twinkle 2.6s ease-in-out infinite alternate}
  @keyframes twinkle{to{scale:.8;opacity:.55}}
}
@media (max-width:640px){
  .art{grid-template-columns:1fr;gap:12px;margin-left:-20px;margin-right:-20px;padding:52px 20px}
  .tape{width:86px;height:24px}
  .art.sketches{min-height:0}
  .art .stage{justify-self:center;padding:24px 18px 56px 18px}
  .art .sketch3d{--bw:min(72vw,280px)}
  .doodle.a,.doodle.c,.doodle.e{display:none}
}
</style>

<div class="monogram" aria-hidden="true">GS</div>
<div class="page">
<header class="bar">
  <a class="word" href="../">Gokul<span class="dot">.</span></a>
  <nav class="links">{{links}}</nav>
</header>

<main>
<section class="art sketches">
  <svg class="torn top" viewBox="0 0 1200 40" preserveAspectRatio="none" aria-hidden="true"><path d="M0 40 L0 18 L34 10 L73 26 L90 8 L110 17 L127 22 L154 7 L173 19 L213 8 L242 8 L283 7 L304 13 L321 24 L360 7 L388 7 L410 15 L450 10 L471 24 L504 23 L529 9 L555 17 L575 23 L593 24 L610 25 L637 21 L678 30 L712 20 L755 17 L788 13 L813 28 L842 8 L875 22 L920 16 L962 15 L980 9 L1026 19 L1050 30 L1085 10 L1130 19 L1146 27 L1164 30 L1198 16 L1200 25 L1200 40 Z"/></svg><svg class="torn bottom" viewBox="0 0 1200 40" preserveAspectRatio="none" aria-hidden="true"><path d="M0 40 L0 18 L34 10 L73 26 L90 8 L110 17 L127 22 L154 7 L173 19 L213 8 L242 8 L283 7 L304 13 L321 24 L360 7 L388 7 L410 15 L450 10 L471 24 L504 23 L529 9 L555 17 L575 23 L593 24 L610 25 L637 21 L678 30 L712 20 L755 17 L788 13 L813 28 L842 8 L875 22 L920 16 L962 15 L980 9 L1026 19 L1050 30 L1085 10 L1130 19 L1146 27 L1164 30 L1198 16 L1200 25 L1200 40 Z"/></svg><span class="tape t1" aria-hidden="true"></span>
  <svg class="doodle a" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 1c1 7 4 10 11 11-7 1-10 4-11 11-1-7-4-10-11-11 7-1 10-4 11-11z"/></svg><svg class="doodle b" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 1c1 7 4 10 11 11-7 1-10 4-11 11-1-7-4-10-11-11 7-1 10-4 11-11z"/></svg><svg class="doodle c" viewBox="0 0 60 16" aria-hidden="true"><path d="M2 9q6-8 12 0t12 0 12 0 12 0 8-2"/></svg>
  <div>
    <p class="label">Art &middot; sketchbook vol. 01</p>
    <h1>Check out these sketches.</h1>
    <p class="aside">not the best, but he's at least trying.</p>
    <p class="tag">{{line}}</p>
    <p class="meta">{{n}} pages so far. Tap the book to open it, then drag the pages to turn them.</p>
    <a class="home" href="../">Back to the home page</a>
  </div>
  <div class="stage">{{book}}</div>
</section>

<section class="art records">
  <svg class="torn top" viewBox="0 0 1200 40" preserveAspectRatio="none" aria-hidden="true"><path d="M0 40 L0 18 L34 10 L73 26 L90 8 L110 17 L127 22 L154 7 L173 19 L213 8 L242 8 L283 7 L304 13 L321 24 L360 7 L388 7 L410 15 L450 10 L471 24 L504 23 L529 9 L555 17 L575 23 L593 24 L610 25 L637 21 L678 30 L712 20 L755 17 L788 13 L813 28 L842 8 L875 22 L920 16 L962 15 L980 9 L1026 19 L1050 30 L1085 10 L1130 19 L1146 27 L1164 30 L1198 16 L1200 25 L1200 40 Z"/></svg><svg class="torn bottom" viewBox="0 0 1200 40" preserveAspectRatio="none" aria-hidden="true"><path d="M0 40 L0 18 L34 10 L73 26 L90 8 L110 17 L127 22 L154 7 L173 19 L213 8 L242 8 L283 7 L304 13 L321 24 L360 7 L388 7 L410 15 L450 10 L471 24 L504 23 L529 9 L555 17 L575 23 L593 24 L610 25 L637 21 L678 30 L712 20 L755 17 L788 13 L813 28 L842 8 L875 22 L920 16 L962 15 L980 9 L1026 19 L1050 30 L1085 10 L1130 19 L1146 27 L1164 30 L1198 16 L1200 25 L1200 40 Z"/></svg><span class="tape t2" aria-hidden="true"></span><span class="tape t3" aria-hidden="true"></span>
  <svg class="staff" viewBox="0 0 600 200" aria-hidden="true"><path class="ln" d="M0 62 C120 53 230 70 340 60 S520 68 600 59"/><path class="ln" d="M0 80 C120 71 230 88 340 78 S520 86 600 77"/><path class="ln" d="M0 98 C120 89 230 106 340 96 S520 104 600 95"/><path class="ln" d="M0 116 C120 107 230 124 340 114 S520 122 600 113"/><path class="ln" d="M0 134 C120 125 230 142 340 132 S520 140 600 131"/><g class="n" style="--d:0.84s;--k:var(--chalk)"><ellipse cx="46" cy="108" rx="8" ry="5.6" transform="rotate(-22 46 108)"/><path class="st" d="M52.6 107.0 V64.0"/><path class="fl" d="M52.6 64.0 c3 8 12 10 9 22"/></g><g class="n" style="--d:0.54s;--k:#E8FF3F"><ellipse cx="112" cy="96" rx="8" ry="5.6" transform="rotate(-22 112 96)"/><ellipse cx="146" cy="80" rx="8" ry="5.6" transform="rotate(-22 146 80)"/><path class="st" d="M118.6 95.0 V50.0 M152.6 79.0 V34.0"/><path class="bm" d="M117.6 50.0 L153.6 34.0"/></g><g class="n" style="--d:0.63s;--k:var(--chalk)"><ellipse cx="206" cy="126" rx="8" ry="5.6" transform="rotate(-22 206 126)"/><path class="st" d="M212.6 125.0 V82.0"/></g><g class="n" style="--d:0.63s;--k:#5FD08A"><ellipse cx="262" cy="88" rx="8" ry="5.6" transform="rotate(-22 262 88)"/><path class="st" d="M268.6 87.0 V44.0"/><path class="fl" d="M268.6 44.0 c3 8 12 10 9 22"/></g><g class="n" style="--d:0.0s;--k:var(--chalk)"><ellipse cx="330" cy="112" rx="8" ry="5.6" transform="rotate(-22 330 112)"/><ellipse cx="364" cy="98" rx="8" ry="5.6" transform="rotate(-22 364 98)"/><path class="st" d="M336.6 111.0 V66.0 M370.6 97.0 V52.0"/><path class="bm" d="M335.6 66.0 L371.6 52.0"/></g><g class="n" style="--d:0.63s;--k:#1F55C6"><ellipse cx="430" cy="72" rx="8" ry="5.6" transform="rotate(-22 430 72)"/><path class="st" d="M436.6 71.0 V28.0"/><path class="fl" d="M436.6 28.0 c3 8 12 10 9 22"/></g><g class="n" style="--d:1.05s;--k:var(--chalk)"><ellipse cx="488" cy="116" rx="8" ry="5.6" transform="rotate(-22 488 116)"/><path class="st" d="M494.6 115.0 V72.0"/></g><g class="n" style="--d:0.27s;--k:#E8FF3F"><ellipse cx="536" cy="90" rx="8" ry="5.6" transform="rotate(-22 536 90)"/><ellipse cx="570" cy="104" rx="8" ry="5.6" transform="rotate(-22 570 104)"/><path class="st" d="M542.6 89.0 V44.0 M576.6 103.0 V58.0"/><path class="bm" d="M541.6 44.0 L577.6 58.0"/></g></svg><svg class="bignote" viewBox="0 0 60 80" aria-hidden="true"><ellipse cx="18" cy="64" rx="15" ry="10.5" transform="rotate(-22 18 64)"/><path d="M30 60 V8 c10 14 26 18 22 40" fill="none" stroke-width="5" stroke-linecap="round"/></svg>
  <svg class="doodle d" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 1c1 7 4 10 11 11-7 1-10 4-11 11-1-7-4-10-11-11 7-1 10-4 11-11z"/></svg><svg class="doodle e" viewBox="0 0 60 16" aria-hidden="true"><path d="M2 9q6-8 12 0t12 0 12 0 12 0 8-2"/></svg>
  <div>
    <p class="label">Records &middot; on repeat</p>
    <h2>Check out these songs, baby.</h2>
    <p class="now"></p>
  </div>
  <div class="rec-stage">
    <div class="crate">
      <div class="crate-back"></div>
      <div class="sleeves" style="--n:{{nrec}}">{{sleeves}}</div>
      <div class="crate-front"><span>On repeat</span></div>
    </div>
    <div class="deck-wrap" aria-hidden="true">
      <div class="deck">
        <span class="deck-shadow"></span><span class="deck-side front"></span><span class="deck-side right"></span>
        <div class="platter"><div class="disc"><span class="hole"></span></div></div>
        <div class="arm"><i></i><b></b></div>
        <span class="knob"></span><span class="led"></span>
      </div>
      <div class="notes"></div>
    </div>
  </div>
</section>
</main>

<footer class="bar foot">
  <span>&copy; {{year}} Gokul Sai</span>
  <span id="clock-wrap" hidden>Hyderabad <b id="clock"></b></span>
</footer>
</div>

{{clock}}
<script type="application/json" id="sketch-pages">{{pages}}</script>
<script src="../sketchbook/book.js" defer></script>
<script src="../records/records.js" defer></script>
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

    # Newest first, the way he asked (15 Sept 2026): 2025 at the top, going
    # down. Dates print MM.DD.YY with ISO kept for machines.
    assert short_date("2026-09-12") == "09.12.26", short_date("2026-09-12")
    dates = re.findall(r'<time datetime="([0-9-]+)"', ledger)
    assert dates == sorted(dates, reverse=True), ("newest first", dates)
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
    # Art: the home page row links to the art page, which holds the book. Every
    # page is in the book, on disk (seen from art/), described, and counted from the files.
    assert '<a href="art/">the artistic side of meeee</a>' in html and         "%d sketches and %d songs" % (len(SKETCH), len(RECORDS)) in html, "the Art row"
    art = render_art()
    m = re.search(r'<script type="application/json" id="sketch-pages">(.*?)</script>', art, re.S)
    book = json.loads(m.group(1)) if m else []
    assert len(book) == len(SKETCH) >= 1, "every page is in the book's data"
    assert all(os.path.exists(os.path.normpath(os.path.join("art", p["src"]))) and p["alt"] for p in book), \
        "each page has its file and alt text"
    assert all(os.path.exists(f) and ('"../%s"' % f) in art for f in ("sketchbook/book.css", "sketchbook/book.js")), \
        "the book's code ships and is linked"
    assert art.count('class="sketch3d"') == 1 and "{{" not in art and "%%" not in art, "the art page is filled in"
    assert "%d<br>pages" % len(SKETCH) in art, "the cover's page count comes from the files"
    # A stranger can reach him without decoding anything.
    assert 'href="mailto:gokulsai1004@gmail.com">gokulsai1004@gmail.com</a>' in html, \
        "the email is written out on the page"
    assert ">OBO<" not in html and ">JR<" not in html and ">@<" not in html, "links are spelled out"
    # A build from the saved copy says so on the page.
    assert "saved copy" in render(ps, "cache") and "saved copy" not in html, "cache builds are labelled"

    print("  all checks pass")


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
    os.makedirs(os.path.dirname(ART_OUT), exist_ok=True)
    with io.open(ART_OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write(render_art())
    print("wrote %s from %s: %d milestones, %d projects counted"
          % (OUT, source, len(MILESTONES), len(ps)))
