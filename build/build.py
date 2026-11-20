#!/usr/bin/env python3
"""Build the static GTA 6 fan guide from data/facts.json and content/pages.json."""

from __future__ import annotations

import argparse
import html
import json
import os
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FACTS_PATH = ROOT / "data" / "facts.json"
PAGES_PATH = ROOT / "content" / "pages.json"
SRC = ROOT / "src"
MANIFEST = ROOT / "build" / "manifest.txt"

DEFAULT_BASE = "https://e13ctr0n1c.github.io/gta6-guide/"

MONTHS = (
    None,
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)

ACTIVITY_URLS = {
    "PC Gamer": [
        "https://www.pcgamer.com/games/grand-theft-auto/gta-6-how-to-make-money/"
    ],
    "Polygon": [
        "https://www.polygon.com/gta-6-how-to-make-money-become-rich-fast-grand-theft-auto/"
    ],
    "PC Gamer / Polygon": [
        "https://www.pcgamer.com/games/grand-theft-auto/gta-6-how-to-make-money/",
        "https://www.polygon.com/gta-6-how-to-make-money-become-rich-fast-grand-theft-auto/",
    ],
}

STATUS_PLAIN = {
    "sources differ": "Sources differ on this, so I am showing the disagreement instead of picking a winner.",
    "reported": "This is reported. I have not treated it as confirmed.",
    "reported/unconfirmed": "This is reported and unconfirmed.",
    "speculation": "This is speculation. I am not treating it as a feature that exists.",
    "partly unknown": "Part of this is still unknown in the sources I checked.",
    "unknown (reputable)": "I could not find this in a reputable outlet.",
    "confirmed (single source)": "I only have this from one source, so I am treating it as thinner than the rest.",
    "confirmed (mechanic); 'no dealers' inferred from guides' silence, treat carefully": (
        "The registration mechanic is confirmed. The line that there are no dealers is inferred "
        "from the guides staying silent, so I am treating that part carefully."
    ),
}

REQUIRED_SLUGS = [
    "how-to-make-money-fast",
    "can-you-buy-cars",
    "garage-prices-locations",
    "can-you-buy-a-house",
    "how-to-save",
    "how-to-switch-characters",
    "how-to-lose-wanted-level",
    "cheats",
    "price-and-editions",
    "file-size",
    "is-gta-6-online",
    "is-gta-6-on-pc",
    "bank-family-savings",
    "where-to-find-a-tank",
    "how-long-to-beat",
    "release-time-uk",
]


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def long_date(iso: str) -> str:
    year, month, day = iso.split("-")
    return f"{int(day)} {MONTHS[int(month)]} {year}"


def pretty_published(value: str) -> str:
    if len(value) == 10 and value[4] == "-" and value[7] == "-":
        try:
            return long_date(value)
        except (ValueError, IndexError):
            return value
    return value


def dollars(amount: int) -> str:
    return f"${amount:,}"


def jsonld(obj: object) -> str:
    raw = json.dumps(obj, ensure_ascii=False, indent=2)
    return raw.replace("<", "\\u003c")


def rel_href(from_slug: str, to_slug: str) -> str:
    """Link to index.html so the same files work on GitHub Pages and raw.githack."""
    from_dir = from_slug.strip("/")
    to = to_slug.strip("/")
    target = "index.html" if not to else f"{to}/index.html"
    start = from_dir if from_dir else "."
    return os.path.relpath(target, start).replace("\\", "/")


def rel_asset(from_slug: str, asset: str) -> str:
    start = from_slug.strip("/") or "."
    return os.path.relpath(asset, start).replace("\\", "/")


def abs_url(base: str, slug: str) -> str:
    root = base.rstrip("/") + "/"
    cleaned = slug.strip("/")
    if not cleaned:
        return root
    return root + cleaned + "/"


def fill(text: str, env: dict[str, str]) -> str:
    for key, value in env.items():
        text = text.replace("{{" + key + "}}", value)
    if "{{" in text:
        raise SystemExit(f"Unfilled placeholder in: {text}")
    return text


def reject_dash_punctuation(label: str, text: str) -> None:
    if "\u2014" in text or "\u2013" in text or " - " in text:
        raise SystemExit(f"Dash used as punctuation in {label}")


def load() -> tuple[dict, str, dict]:
    raw = FACTS_PATH.read_text(encoding="utf-8")
    facts = json.loads(raw)
    pages = json.loads(PAGES_PATH.read_text(encoding="utf-8"))
    return facts, raw, pages


def facts_by_id(facts: dict) -> dict[str, dict]:
    return {item["id"]: item for item in facts["facts"]}


def assert_known_urls(raw: str) -> None:
    for urls in ACTIVITY_URLS.values():
        for url in urls:
            if url not in raw:
                raise SystemExit(f"Activity source URL is not in the fact file: {url}")


def cash_limits(by_id: dict[str, dict]) -> tuple[int, int]:
    claim = by_id["F027"]["claim"]
    if "$20,000" not in claim or "$1,000" not in claim:
        raise SystemExit("F027 no longer states the cash limits I planned around")
    return 20000, 1000


def cheat_record(by_id: dict[str, dict]) -> dict:
    claim = by_id["F068"]["claim"]
    code = "Up, Right, Down, Left, Up, Left, Down, Right"
    if code not in claim or "$250,000" not in claim:
        raise SystemExit("F068 no longer contains the one published cheat")
    save = by_id["F052"]["claim"]
    return {
        "name": "$250,000",
        "code": code,
        "unlock": "Finish the story",
        "notes": "Using any cheat disables saving for that session. Many codes are still unknown.",
        "save_claim": save,
    }


def validate_pages(facts: dict, pages: dict) -> dict[str, dict]:
    ranked = {item["slug"]: item for item in facts["ranked_pages"]}
    by_slug: dict[str, dict] = {}
    grouped: set[str] = set()
    for group in pages["groups"]:
        for slug in group["slugs"]:
            if slug in grouped:
                raise SystemExit(f"Slug grouped twice: {slug}")
            grouped.add(slug)
    for page in pages["pages"]:
        slug = page["slug"]
        if slug in by_slug:
            raise SystemExit(f"Duplicate slug: {slug}")
        by_slug[slug] = page
        for field in ("h1", "description", "lead"):
            reject_dash_punctuation(f"{slug} {field}", page[field])
        if not page["description"] or len(page["description"]) > 160:
            raise SystemExit(f"Description length for {slug}: {len(page['description'])}")
        if page["kind"] == "question":
            ranked_page = ranked.get(slug)
            if not ranked_page:
                raise SystemExit(f"Question page is not in the ranked plan: {slug}")
            if page["h1"] != ranked_page["h1"]:
                raise SystemExit(f"H1 does not match the plan for {slug}")
            if slug not in grouped:
                raise SystemExit(f"Question page is not grouped: {slug}")
        for section in page.get("sections", []):
            for paragraph in section.get("paragraphs", []):
                reject_dash_punctuation(slug, paragraph)
            if section.get("h2"):
                reject_dash_punctuation(slug, section["h2"])
    missing = [slug for slug in REQUIRED_SLUGS if slug not in by_slug]
    if missing:
        raise SystemExit(f"Missing required pages: {', '.join(missing)}")
    missing_ranked = [slug for slug in ranked if slug not in by_slug]
    if missing_ranked:
        raise SystemExit(f"Ranked pages not built: {', '.join(missing_ranked)}")
    for page in pages["pages"]:
        if page["kind"] == "info" and page["slug"] == "404":
            continue
        count = len(page.get("related", []))
        if page["kind"] in {"question", "tool"} and count not in {3, 4}:
            raise SystemExit(f"{page['slug']} needs 3 or 4 related links, has {count}")
        for related in page.get("related", []):
            if related not in by_slug:
                raise SystemExit(f"{page['slug']} related link missing: {related}")
            if related == page["slug"]:
                raise SystemExit(f"{page['slug']} links to itself")
    return by_slug


def clean_previous() -> None:
    if not MANIFEST.exists():
        return
    for line in MANIFEST.read_text(encoding="utf-8").splitlines():
        rel = line.strip()
        if not rel or rel.startswith("build/"):
            continue
        path = (ROOT / rel).resolve()
        if ROOT not in path.parents and path != ROOT:
            continue
        if path.is_file():
            path.unlink()
            parent = path.parent
            while parent != ROOT:
                try:
                    parent.rmdir()
                except OSError:
                    break
                parent = parent.parent


def source_entries(by_id: dict[str, dict], fact_ids: list[str], extras: list[dict]) -> list[dict]:
    found: list[dict] = []
    seen: set[str] = set()

    def add(url: str, outlet: str, published: str) -> None:
        if not url or url in seen:
            return
        seen.add(url)
        found.append({"url": url, "outlet": outlet, "published": published})

    for fact_id in fact_ids:
        fact = by_id.get(fact_id)
        if not fact:
            raise SystemExit(f"Unknown fact id {fact_id}")
        for source in fact.get("sources", []):
            add(source["url"], source["outlet"], source.get("published", ""))
    for extra in extras:
        add(extra["url"], extra["outlet"], extra.get("published", ""))
    found.sort(key=lambda item: (item["outlet"].lower(), item["url"]))
    return found


def render_fact(fact: dict) -> str:
    parts = ['<article class="fact">', f"<p>{esc(fact['claim'])}</p>"]
    if fact["status"] != "confirmed" and fact["status"] not in STATUS_PLAIN:
        raise SystemExit(f"No plain status line for {fact['id']}: {fact['status']}")
    plain = STATUS_PLAIN.get(fact["status"])
    if plain:
        parts.append(f'<p class="flag">{esc(plain)}</p>')
    if fact.get("note"):
        parts.append(f'<p class="note">Note from the fact file: {esc(fact["note"])}</p>')
    if fact.get("sources"):
        items = []
        for source in fact["sources"]:
            published = pretty_published(source.get("published", ""))
            items.append(
                f'<li><a href="{esc(source["url"])}" rel="noreferrer">{esc(source["outlet"])}</a>'
                f" ({esc(published)})</li>"
            )
        parts.append('<ul class="citations">' + "".join(items) + "</ul>")
    else:
        parts.append("<p>No reputable source is listed for this line.</p>")
    parts.append("</article>")
    return "".join(parts)


def render_garage_list(facts: dict) -> str:
    items = []
    for garage in facts["prices"]["garages"]:
        price = "Free" if garage["price_usd"] == 0 else dollars(garage["price_usd"])
        items.append(
            "<li class=\"card\">"
            f"<h3>{esc(garage['name'])}</h3>"
            f'<p class="price">{esc(price)}</p>'
            f"<p>{esc(garage['where'])}</p>"
            f"<p>{esc(garage['bought_via'])}</p>"
            "</li>"
        )
    return '<ul class="cards">' + "".join(items) + "</ul>"


def render_activity_list(facts: dict) -> str:
    items = []
    for activity in facts["prices"]["money_activities"]:
        urls = ACTIVITY_URLS.get(activity["outlet"])
        if not urls:
            raise SystemExit(f"No source URL mapped for {activity['outlet']}")
        links = "".join(
            f'<li><a href="{esc(url)}" rel="noreferrer">{esc(activity["outlet"])}</a></li>'
            for url in urls
        )
        items.append(
            "<li class=\"card\">"
            f"<h3>{esc(activity['activity'])}</h3>"
            f"<p>Published wording: {esc(activity['payout'])}</p>"
            f"<p class=\"when\">When the guides place it: {esc(activity['when'])}</p>"
            f'<ul class="citations">{links}</ul>'
            "</li>"
        )
    return '<ul class="cards">' + "".join(items) + "</ul>"


def render_sections(page: dict, facts: dict, by_id: dict[str, dict], env: dict[str, str]) -> tuple[str, list[str], list[dict]]:
    html_parts: list[str] = []
    fact_ids: list[str] = []
    extras: list[dict] = []
    for section in page.get("sections", []):
        html_parts.append("<section>")
        if section.get("h2"):
            html_parts.append(f"<h2>{esc(fill(section['h2'], env))}</h2>")
        for paragraph in section.get("paragraphs", []):
            html_parts.append(f"<p>{esc(fill(paragraph, env))}</p>")
        if section.get("external_links"):
            items = []
            for link in section["external_links"]:
                reject_dash_punctuation(page["slug"], link["label"])
                items.append(
                    f'<li><a href="{esc(link["href"])}" rel="noopener">{esc(link["label"])}</a></li>'
                )
                extras.append(
                    {
                        "url": link["href"],
                        "outlet": link.get("outlet", "Gumroad"),
                        "published": link.get("published", ""),
                    }
                )
            html_parts.append("<ul>" + "".join(items) + "</ul>")
        if section.get("garage_list"):
            html_parts.append(render_garage_list(facts))
            source = facts["prices"]["garages"][0]["source"]
            extras.append(source)
        if section.get("activity_list"):
            html_parts.append(render_activity_list(facts))
            for urls in ACTIVITY_URLS.values():
                for url in urls:
                    extras.append({"url": url, "outlet": "Published money guide", "published": "2026-11-18"})
        if section.get("unsupported_tools"):
            html_parts.append(render_unsupported(facts))
        if section.get("price_note"):
            note = facts["prices"][section["price_note"]]
            reject_dash_punctuation(page["slug"], note)
            html_parts.append(f"<p>{esc(note)}</p>")
        for fact_id in section.get("facts", []):
            fact_ids.append(fact_id)
            html_parts.append(render_fact(by_id[fact_id]))
        html_parts.append("</section>")
    # Activity extras use a generic outlet label. Replace with real outlet names via the URLs already
    # attached in render, and dedupe in source_entries. Refine outlet labels here.
    labelled: list[dict] = []
    for extra in extras:
        if extra["url"].startswith("https://www.pcgamer.com/"):
            labelled.append({**extra, "outlet": "PC Gamer", "published": "2026-11-18"})
        elif extra["url"].startswith("https://www.polygon.com/gta-6-how-to-make-money"):
            labelled.append({**extra, "outlet": "Polygon", "published": "2026-11-19"})
        else:
            labelled.append(extra)
    return "".join(html_parts), fact_ids, labelled


def render_unsupported(facts: dict) -> str:
    items = []
    for tool in facts["tools"]:
        if tool.get("honest") is False:
            reject_dash_punctuation(tool["tool"], tool["data"])
            items.append(f"<li><strong>{esc(tool['tool'])}.</strong> {esc(tool['data'])}</li>")
    if not items:
        raise SystemExit("Expected the fact file to mark vehicle and weapon lookups as not supportable")
    return "<ul>" + "".join(items) + "</ul>"


def tool_widget(page: dict, facts: dict, by_id: dict[str, dict], link_slug: str) -> str:
    kind = page.get("tool")
    if not kind:
        return ""
    if kind == "garage":
        return garage_widget(facts, by_id)
    if kind == "money":
        return money_widget(facts, by_id)
    if kind == "cheats":
        return cheat_widget(by_id, link_slug)
    raise SystemExit(f"Unknown tool {kind}")


def garage_widget(facts: dict, by_id: dict[str, dict]) -> str:
    claim = by_id["F042"]["claim"]
    if "four owned vehicle slots" not in claim or "two slots" not in claim or "12+" not in claim:
        raise SystemExit("F042 slot figures changed")
    boxes = []
    for index, garage in enumerate(facts["prices"]["garages"]):
        price = "Free" if garage["price_usd"] == 0 else dollars(garage["price_usd"])
        boxes.append(
            f'<label class="choice"><input type="checkbox" data-kind="list" data-price="{garage["price_usd"]}">'
            f"<span><strong>{esc(garage['name'])}</strong>, {esc(price)}. {esc(garage['where'])}</span></label>"
        )
    data = jsonld({"tool": "garage", "startSlots": 4, "valentinaSlots": 2})
    return f"""
<div class="tool" data-tool="garage">
<form id="garage-form">
<fieldset>
<legend>Tick the garages you want from the list of 10</legend>
{''.join(boxes)}
</fieldset>
<fieldset>
<legend>A garage GameSpot describes separately</legend>
<label class="choice"><input type="checkbox" data-kind="valentina" data-price="0">
<span><strong>Valentina's Ocean Beach garage</strong>, Free. GameSpot gives this one two slots. It is not one of the 10 priced garages.</span></label>
</fieldset>
<p><button type="button" id="garage-clear">Clear ticks</button></p>
</form>
<div class="result" aria-live="polite">
<p>Total of the published prices I ticked: <strong class="total" id="garage-cost">$0</strong></p>
<p id="garage-count">Garages ticked from the list of 10: 0.</p>
<h2>Two readings of capacity</h2>
<p id="slots-pc">PC Gamer says each garage holds a single car. I have not ticked a list garage, so that reading adds 0 slots. With the 4 starting slots, that reading is 4. I am not folding Valentina's garage into this number, because GameSpot gives that garage its own slot count.</p>
<p id="slots-gs">GameSpot says the list garages hold one or a couple of vehicles, so I will not turn those 0 garages into one slot total. GameSpot's exact figures on this form are the 4 starting slots. Valentina's Ocean Beach garage is 2 slots in GameSpot's account, and I have not ticked it. GameSpot also says 12 or more slots are possible. That line is theirs, not a total I calculated from the ticks.</p>
</div>
<script type="application/json" id="tool-data">{data}</script>
</div>
"""


def money_widget(facts: dict, by_id: dict[str, dict]) -> str:
    cap, limit = cash_limits(by_id)
    activities = []
    boxes = []
    for index, activity in enumerate(facts["prices"]["money_activities"]):
        activities.append(
            {
                "activity": activity["activity"],
                "payout": activity["payout"],
                "when": activity["when"],
                "outlet": activity["outlet"],
            }
        )
        boxes.append(
            f'<label class="choice"><input type="checkbox" name="activity" value="{index}">'
            f"<span><strong>{esc(activity['activity'])}</strong>. Published wording: {esc(activity['payout'])}. "
            f"{esc(activity['when'])}.</span></label>"
        )
    radios = [
        '<label class="choice"><input type="radio" name="target" value="" checked>'
        "<span>No garage selected</span></label>"
    ]
    for garage in facts["prices"]["garages"]:
        price = "Free" if garage["price_usd"] == 0 else dollars(garage["price_usd"])
        radios.append(
            f'<label class="choice"><input type="radio" name="target" value="{esc(garage["name"])}" '
            f'data-price="{garage["price_usd"]}" data-name="{esc(garage["name"])}">'
            f"<span>{esc(garage['name'])}, {esc(price)}</span></label>"
        )
    data = jsonld(
        {
            "tool": "money",
            "activities": activities,
            "cashCap": cap,
            "cashPurchaseLimit": limit,
        }
    )
    return f"""
<div class="tool" data-tool="money">
<p class="estimate">estimates from published guides</p>
<form id="money-form">
<fieldset>
<legend>Tick activities to see the published ranges</legend>
{''.join(boxes)}
</fieldset>
<fieldset>
<legend>A garage price I might compare, without turning ranges into a sum</legend>
{''.join(radios)}
</fieldset>
<p><button type="button" id="money-clear">Clear ticks</button></p>
</form>
<div class="result" aria-live="polite">
<p>I show the published wording only. I do not add ranges into an exact sum.</p>
<ul id="money-list"><li>No activities ticked yet. The ranges stay as published wording. I will not add them into a sum.</li></ul>
<p id="money-garage">No garage selected. Pocket cash still stops at $20,000, and a purchase over $1,000 goes through BuckMe.</p>
</div>
<script type="application/json" id="tool-data">{data}</script>
</div>
"""


def cheat_widget(by_id: dict[str, dict], link_slug: str) -> str:
    cheat = cheat_record(by_id)
    data = jsonld({"tool": "cheats", "cheats": [{key: cheat[key] for key in ("name", "code", "unlock", "notes")}]})
    script = rel_asset(link_slug, "assets/tools.js")
    # script tag is added by the layout when tool data exists. Include the finder markup only.
    del script
    return f"""
<div class="tool" data-tool="cheats">
<form id="cheat-form" role="search">
<label for="cheat-q">Search the published cheats</label>
<input id="cheat-q" type="search" name="q" autocomplete="off">
</form>
<div id="cheat-result" aria-live="polite">
<article class="card">
<p><strong>{esc(cheat['name'])}</strong></p>
<p>Code: {esc(cheat['code'])}</p>
<p>Unlock: {esc(cheat['unlock'])}</p>
<p>{esc(cheat['notes'])}</p>
</article>
</div>
<p>Many codes are still unknown.</p>
<script type="application/json" id="tool-data">{data}</script>
</div>
"""


def crumb_html(link_slug: str, crumbs: list[tuple[str, str | None]]) -> str:
    items = []
    for name, target in crumbs:
        if target is None:
            items.append(f'<li><span aria-current="page">{esc(name)}</span></li>')
        elif target.startswith("#"):
            href = rel_href(link_slug, "") + target
            items.append(f'<li><a href="{esc(href)}">{esc(name)}</a></li>')
        else:
            href = rel_href(link_slug, target)
            items.append(f'<li><a href="{esc(href)}">{esc(name)}</a></li>')
    return '<nav class="crumbs" aria-label="Breadcrumb"><ol>' + "".join(items) + "</ol></nav>"


def crumb_json(base: str, crumbs: list[tuple[str, str | None]]) -> dict:
    elements = []
    for index, (name, target) in enumerate(crumbs, start=1):
        slug = "" if target is None else target
        # The current page passes target None. Caller replaces the last URL.
        item = {
            "@type": "ListItem",
            "position": index,
            "name": name,
        }
        elements.append(item)
    return elements


def mark_svg() -> str:
    return (
        '<svg class="mark" viewBox="0 0 48 48" width="36" height="36" aria-hidden="true" focusable="false">'
        '<circle cx="22" cy="26" r="12" fill="#e07a5f"></circle>'
        '<circle cx="30" cy="20" r="8" fill="#f6c7a1"></circle>'
        '<rect x="8" y="36" width="32" height="3" rx="1.5" fill="#6d2e46"></rect>'
        "</svg>"
    )


def layout(page: dict) -> str:
    robots = "noindex" if page["slug"] == "404" else "index,follow"
    scripts = ""
    if page.get("needs_tools"):
        src = rel_asset(page["link_slug"], "assets/tools.js")
        scripts = f'<script src="{esc(src)}" defer></script>'
    ld = "\n".join(
        f'<script type="application/ld+json">\n{block}\n</script>' for block in page["jsonld"]
    )
    nav = []
    for key, label, target in (
        ("home", "Questions", ""),
        ("tools", "Tools", "tools"),
        ("about", "About", "about"),
    ):
        current = ""
        slug = page["slug"]
        if key == "home" and slug == "":
            current = ' aria-current="page"'
        elif key == "tools" and (slug == "tools" or slug.startswith("tools/")):
            current = ' aria-current="page"'
        elif key == "about" and slug == "about":
            current = ' aria-current="page"'
        href = rel_href(page["link_slug"], target)
        nav.append(f'<a href="{esc(href)}"{current}>{label}</a>')
    footer_links = []
    for label, target in (("About", "about"), ("Privacy", "privacy"), ("Cookies", "cookies")):
        href = rel_href(page["link_slug"], target)
        footer_links.append(f'<a href="{esc(href)}">{label}</a>')
    css = rel_asset(page["link_slug"], "assets/site.css")
    icon = rel_asset(page["link_slug"], "assets/favicon.svg")
    home = rel_href(page["link_slug"], "")
    return f"""<!DOCTYPE html>
<html lang="en-GB">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(page["title"])}</title>
<meta name="description" content="{esc(page["description"])}">
<link rel="canonical" href="{esc(page["canonical"])}">
<meta name="robots" content="{robots}">
<meta name="referrer" content="no-referrer">
<meta name="theme-color" content="#2a1a16">
<meta property="og:title" content="{esc(page["title"])}">
<meta property="og:description" content="{esc(page["description"])}">
<meta property="og:url" content="{esc(page["canonical"])}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="GTA 6 fan guide">
<meta property="og:locale" content="en_GB">
<link rel="icon" href="{esc(icon)}" type="image/svg+xml">
<link rel="stylesheet" href="{esc(css)}">
{ld}
</head>
<body>
<a class="skip" href="#content">Skip to content</a>
<div class="sunset" aria-hidden="true"></div>
<header class="site-header">
<div class="wrap">
<a class="brand" href="{esc(home)}">{mark_svg()}<span>GTA 6 fan guide</span></a>
<nav class="nav-primary" aria-label="Primary">{''.join(nav)}</nav>
</div>
</header>
<main id="content">
{page["main"]}
</main>
<footer class="site-footer">
<div class="wrap">
<nav aria-label="Footer">{''.join(footer_links)}</nav>
<p>Unofficial fan guide, not affiliated with Rockstar Games or Take-Two.</p>
<p data-gift><a href="https://arthurverse67.gumroad.com/l/gamergiftkitlite" rel="noopener">Gifting a gamer this Christmas? Try my free Gamer Gift Kit Lite</a></p>
</div>
</footer>
{scripts}
<script>
(function () {{
  var now = new Date();
  var year = now.getFullYear();
  var month = now.getMonth();
  var day = now.getDate();
  var ended = year > 2026 || (year === 2026 && month === 11 && day > 26);
  if (!ended) {{
    return;
  }}
  document.querySelectorAll("[data-gift]").forEach(function (node) {{
    node.remove();
  }});
}})();
</script>
</body>
</html>
"""


def sources_block(sources: list[dict], note: str) -> str:
    items = []
    for source in sources:
        published = pretty_published(source.get("published", ""))
        extra = f" ({esc(published)})" if published else ""
        items.append(
            f'<li><a href="{esc(source["url"])}" rel="noreferrer">{esc(source["outlet"])}</a>{extra}</li>'
        )
    body = f"<p>{esc(note)}</p>" if note else ""
    listing = "<ul>" + "".join(items) + "</ul>" if items else ""
    return f'<section class="sources" id="sources"><h2>Sources</h2>{body}{listing}</section>'


def related_block(link_slug: str, related: list[str], by_slug: dict[str, dict]) -> str:
    if not related:
        return ""
    items = []
    for slug in related:
        href = rel_href(link_slug, slug)
        items.append(f'<li><a href="{esc(href)}">{esc(by_slug[slug]["h1"])}</a></li>')
    return "<section><h2>Related</h2><ul>" + "".join(items) + "</ul></section>"


def breadcrumb_data(base: str, crumbs: list[tuple[str, str]]) -> dict:
    items = []
    for index, (name, url) in enumerate(crumbs, start=1):
        items.append({"@type": "ListItem", "position": index, "name": name, "item": url})
    return {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": items}


def group_for(pages: dict, slug: str) -> dict | None:
    for group in pages["groups"]:
        if slug in group["slugs"]:
            return group
    return None


def visible_crumbs(page: dict, pages: dict) -> list[tuple[str, str | None]]:
    slug = page["slug"]
    if slug == "":
        return [("Home", None)]
    crumbs: list[tuple[str, str | None]] = [("Home", "")]
    if slug == "404":
        crumbs.append(("Missing page", None))
        return crumbs
    group = group_for(pages, slug)
    if group:
        crumbs.append((group["title"], f"#{group['id']}"))
    elif slug == "tools" or slug.startswith("tools/"):
        if slug != "tools":
            crumbs.append(("Tools", "tools"))
    crumbs.append((page["h1"], None))
    return crumbs


def crumb_target_to_url(base: str, target: str) -> str:
    if target.startswith("#"):
        return abs_url(base, "") + target
    return abs_url(base, target)


def build_main(page: dict, pages: dict, facts: dict, by_id: dict[str, dict], by_slug: dict[str, dict], env: dict[str, str], link_slug: str) -> tuple[str, list[str], list[dict]]:
    sections, fact_ids, extras = render_sections(page, facts, by_id, env)
    widget = tool_widget(page, facts, by_id, link_slug)
    crumbs = crumb_html(link_slug, visible_crumbs(page, pages))
    note = fill(page.get("sources_note", ""), env)
    answer = f'<p class="answer">{esc(fill(page["lead"], env))}</p>'
    checked = f'<p class="checked">Last checked: {esc(env["checked"])}</p>'
    heading = crumbs + f"<h1>{esc(page['h1'])}</h1>"
    if page.get("seasonal") == "gift":
        main_top = heading + f'<div data-gift>{answer}{widget}{sections}</div>' + checked
    else:
        main_top = heading + answer + checked + widget + sections
    return main_top, fact_ids, extras


def home_main(pages: dict, by_slug: dict[str, dict], facts: dict, by_id: dict[str, dict], env: dict[str, str]) -> tuple[str, list[str]]:
    link_slug = ""
    crumbs = crumb_html(link_slug, [("Home", None)])
    groups_html = []
    for group in pages["groups"]:
        cards = []
        for slug in group["slugs"]:
            page = by_slug[slug]
            href = rel_href(link_slug, slug)
            cards.append(
                f'<li><a href="{esc(href)}"><span class="q">{esc(page["h1"])}</span>'
                f'<span class="a">{esc(page["lead"])}</span></a></li>'
            )
        groups_html.append(
            f'<section id="{esc(group["id"])}"><h2>{esc(group["title"])}</h2>'
            f'<ul class="questions">{"".join(cards)}</ul></section>'
        )
    tool_links = []
    for slug in ("tools/garage-cost-planner", "tools/money-planner", "tools/cheat-finder"):
        href = rel_href(link_slug, slug)
        tool_links.append(f'<li><a href="{esc(href)}">{esc(by_slug[slug]["h1"])}</a></li>')
    facts_html = render_fact(by_id["F001"]) + render_fact(by_id["F003"])
    lead = (
        "I have written one page per question for a new player. The short answer is the first paragraph, "
        "then I show the sourced detail. If the outlets disagree, or if they never say, I tell you."
    )
    main = (
        crumbs
        + "<h1>What does this GTA 6 new player guide cover?</h1>"
        + f'<p class="answer">{esc(lead)}</p>'
        + f'<p class="checked">Last checked: {esc(env["checked"])}</p>'
        + "<section><h2>The UK launch, written as history</h2>"
        + "<p>I checked this on "
        + esc(env["checked"])
        + ", the day after the UK unlock, so the release page is a record rather than a countdown.</p>"
        + facts_html
        + "</section>"
        + "".join(groups_html)
        + "<section><h2>Tools</h2>"
        + "<p>I have three planners. I do not have a vehicle price lookup or a weapon price lookup, because no reputable list is in the fact file.</p>"
        + "<ul>"
        + "".join(tool_links)
        + "</ul></section>"
        + '<p class="gift-note" data-gift><a href="'
        + esc(rel_href("", "gift-ideas"))
        + '">Gift ideas for a GTA 6 fan this Christmas</a></p>'
    )
    return main, ["F001", "F003"]


def faq_for(h1: str, lead: str, canonical: str) -> dict:
    return {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "inLanguage": "en-GB",
        "url": canonical,
        "mainEntity": [
            {
                "@type": "Question",
                "name": h1,
                "acceptedAnswer": {"@type": "Answer", "text": lead},
            }
        ],
    }


def write_text(rel: str, text: str, written: list[str]) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    written.append(rel)


def copy_asset(name: str, written: list[str]) -> None:
    target = ROOT / "assets" / name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SRC / name, target)
    written.append(f"assets/{name}")


def build_sitemap(base: str, slugs: list[str], checked_iso: str) -> str:
    urls = []
    for slug in slugs:
        loc = abs_url(base, slug)
        urls.append(f"  <url><loc>{esc(loc)}</loc><lastmod>{esc(checked_iso)}</lastmod></url>")
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(urls)
        + "\n</urlset>\n"
    )


def build_llms(base: str, pages: dict, by_slug: dict[str, dict], checked: str) -> str:
    lines = [
        "# GTA 6 new player fan guide",
        "",
        "> Unofficial fan guide for new players. Not affiliated with Rockstar Games or Take-Two. "
        f"I checked the facts on {checked}. I do not invent figures.",
        "",
        "## Questions",
    ]
    for group in pages["groups"]:
        for slug in group["slugs"]:
            page = by_slug[slug]
            lines.append(f"- [{page['h1']}]({abs_url(base, slug)}): {page['description']}")
    lines.append("")
    lines.append("## Tools")
    for slug in ("tools", "tools/garage-cost-planner", "tools/money-planner", "tools/cheat-finder"):
        page = by_slug[slug]
        lines.append(f"- [{page['h1']}]({abs_url(base, slug)}): {page['description']}")
    lines.append("")
    lines.append("## Site")
    for slug in ("about", "privacy", "cookies", "gift-ideas"):
        page = by_slug[slug]
        lines.append(f"- [{page['h1']}]({abs_url(base, slug)}): {page['description']}")
    lines.append("")
    return "\n".join(lines)


def output_rel(slug: str) -> str:
    if slug == "":
        return "index.html"
    if slug == "404":
        return "404.html"
    return f"{slug}/index.html"


def link_slug_for(slug: str) -> str:
    if slug in {"", "404"}:
        return ""
    return slug


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the GTA 6 fan guide")
    parser.add_argument("--base-url", default=os.environ.get("SITE_BASE_URL", DEFAULT_BASE))
    args = parser.parse_args()
    base = args.base_url.strip()
    if not base.startswith("https://"):
        raise SystemExit("Base URL must start with https://")
    facts, raw, pages = load()
    assert_known_urls(raw)
    by_id = facts_by_id(facts)
    by_slug = validate_pages(facts, pages)
    checked_iso = facts["checked_on"]
    checked = long_date(checked_iso)
    if checked != "20 November 2026":
        raise SystemExit(f"Unexpected checked date: {checked}")
    env = {"scope_note": facts["scope_note"], "checked": checked}
    reject_dash_punctuation("scope", facts["scope_note"])

    clean_previous()
    written: list[str] = []

    home_lead = (
        "I have written one page per question for a new player. The short answer is the first paragraph, "
        "then I show the sourced detail. If the outlets disagree, or if they never say, I tell you."
    )
    home_description = (
        "I answer new player questions about GTA 6, one page each, with the outlet and link kept on the fact."
    )
    if len(home_description) > 160:
        raise SystemExit("Home description is too long")

    # Content pages from the file, plus the generated home page.
    content_pages = list(pages["pages"])
    for page in content_pages:
        slug = page["slug"]
        link_slug = link_slug_for(slug)
        main_top, fact_ids, extras = build_main(page, pages, facts, by_id, by_slug, env, link_slug)
        if page.get("example_outlets"):
            seen_outlets: set[str] = set()
            for fact in facts["facts"]:
                for source in fact.get("sources", []):
                    if source["outlet"] not in seen_outlets:
                        seen_outlets.add(source["outlet"])
                        extras.append(source)
        sources = source_entries(by_id, fact_ids, extras)
        if page["kind"] in {"question", "tool"} and not sources:
            raise SystemExit(f"{slug} has no sources")
        note = fill(page.get("sources_note", ""), env)
        if page["kind"] == "info" and not note:
            note = "This page does not state a game fact, so there is no outlet list."
        main = main_top + sources_block(sources, note) + related_block(link_slug, page.get("related", []), by_slug)
        canonical = abs_url(base, "" if slug == "404" else slug) if slug != "404" else base.rstrip("/") + "/404.html"
        if slug == "404":
            canonical = base.rstrip("/") + "/404.html"
        title = f"{page['h1']} | GTA 6 fan guide"
        lead = fill(page["lead"], env)
        blocks = []
        if page["kind"] in {"question", "tool"}:
            blocks.append(jsonld(faq_for(page["h1"], lead, canonical)))
        else:
            blocks.append(
                jsonld(
                    {
                        "@context": "https://schema.org",
                        "@type": "WebPage",
                        "name": page["h1"],
                        "description": fill(page["description"], env),
                        "url": canonical,
                        "inLanguage": "en-GB",
                        "dateModified": checked_iso,
                    }
                )
            )
        crumb_pairs = []
        for name, target in visible_crumbs(page, pages):
            if target is None:
                crumb_pairs.append((name, canonical))
            else:
                crumb_pairs.append((name, crumb_target_to_url(base, target)))
        blocks.append(jsonld(breadcrumb_data(base, crumb_pairs)))
        document = layout(
            {
                "slug": slug,
                "link_slug": link_slug,
                "title": title,
                "description": fill(page["description"], env),
                "canonical": canonical,
                "main": main,
                "jsonld": blocks,
                "needs_tools": bool(page.get("tool")),
            }
        )
        reject_dash_punctuation(slug, document)
        write_text(output_rel(slug), document, written)

    home_main_html, home_ids = home_main(pages, by_slug, facts, by_id, env)
    home_sources = source_entries(by_id, home_ids, [])
    home_main_html += sources_block(
        home_sources,
        "Each question page has its own source list. The two lines above are the launch facts I repeat on the home page.",
    )
    home_canonical = abs_url(base, "")
    home_faq_entities = []
    for group in pages["groups"]:
        for slug in group["slugs"]:
            item = by_slug[slug]
            home_faq_entities.append(
                {
                    "@type": "Question",
                    "name": item["h1"],
                    "acceptedAnswer": {"@type": "Answer", "text": item["lead"]},
                }
            )
    home_blocks = [
        jsonld(
            {
                "@context": "https://schema.org",
                "@type": "FAQPage",
                "inLanguage": "en-GB",
                "url": home_canonical,
                "mainEntity": home_faq_entities,
            }
        ),
        jsonld(breadcrumb_data(base, [("Home", home_canonical)])),
    ]
    home_doc = layout(
        {
            "slug": "",
            "link_slug": "",
            "title": "GTA 6 new player fan guide",
            "description": home_description,
            "canonical": home_canonical,
            "main": home_main_html,
            "jsonld": home_blocks,
            "needs_tools": False,
        }
    )
    reject_dash_punctuation("home", home_doc)
    write_text("index.html", home_doc, written)

    indexable = [""] + [page["slug"] for page in content_pages if page["slug"] != "404"]
    write_text("sitemap.xml", build_sitemap(base, indexable, checked_iso), written)
    sitemap_url = base.rstrip("/") + "/sitemap.xml"
    write_text("robots.txt", f"User-agent: *\nAllow: /\n\nSitemap: {sitemap_url}\n", written)
    write_text("llms.txt", build_llms(base, pages, by_slug, checked), written)
    write_text(".nojekyll", "", written)
    for name in ("site.css", "favicon.svg", "tools.js"):
        copy_asset(name, written)

    # The first robots write is overwritten. Manifest should list robots once.
    unique: list[str] = []
    seen: set[str] = set()
    for rel in written:
        if rel not in seen:
            seen.add(rel)
            unique.append(rel)
    MANIFEST.write_text("\n".join(unique) + "\n", encoding="utf-8")
    print(f"Wrote {len(unique)} files for {base.rstrip('/')}/")


if __name__ == "__main__":
    main()
