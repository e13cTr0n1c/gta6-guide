#!/usr/bin/env python3
"""Check the generated fan guide: structure, sources, links, and branding."""

from __future__ import annotations

import html
import json
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

import build  # noqa: E402

DISCLAIMER = "Unofficial fan guide, not affiliated with Rockstar Games or Take-Two."
CHECKED = "Last checked: 20 November 2026"
FORBIDDEN = ("rockstar logo", "take-two logo", "screenshot")
IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".avif")


class Parser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.h1: list[str] = []
        self.links: list[str] = []
        self.srcs: list[str] = []
        self.jsonld: list[str] = []
        self.ids: list[str] = []
        self.metas: list[tuple[str, str, str]] = []
        self.canonical = ""
        self.title = ""
        self.answer = ""
        self._capture: str | None = None
        self._buf: list[str] = []
        self._script_type = ""
        self._in_script = False
        self.text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        data = {key: value or "" for key, value in attrs}
        if "id" in data and data["id"]:
            self.ids.append(data["id"])
        if tag == "a" and data.get("href"):
            self.links.append(data["href"])
        if tag in {"img", "script", "link", "source"} and data.get("src"):
            self.srcs.append(data["src"])
        if tag == "link" and data.get("href"):
            self.srcs.append(data["href"])
            if data.get("rel") == "canonical":
                self.canonical = data["href"]
        if tag == "meta":
            self.metas.append((data.get("name", ""), data.get("property", ""), data.get("content", "")))
        if tag == "h1":
            self._capture = "h1"
            self._buf = []
        elif tag == "p" and "answer" in data.get("class", "").split():
            self._capture = "answer"
            self._buf = []
        elif tag == "title":
            self._capture = "title"
            self._buf = []
        elif tag == "script" and data.get("type") == "application/ld+json":
            self._in_script = True
            self._script_type = data.get("type", "")
            self._buf = []

    def handle_endtag(self, tag: str) -> None:
        if self._capture and tag in {"h1", "p", "title"}:
            text = " ".join("".join(self._buf).split())
            if self._capture == "h1":
                self.h1.append(text)
            elif self._capture == "answer":
                self.answer = text
            elif self._capture == "title":
                self.title = text
            self._capture = None
            self._buf = []
        if tag == "script" and self._in_script:
            self.jsonld.append("".join(self._buf))
            self._in_script = False
            self._buf = []

    def handle_data(self, data: str) -> None:
        self.text.append(data)
        if self._capture or self._in_script:
            self._buf.append(data)


def html_files() -> list[Path]:
    manifest = (ROOT / "build" / "manifest.txt").read_text(encoding="utf-8").splitlines()
    files = []
    for line in manifest:
        if line.endswith(".html"):
            files.append(ROOT / line)
    if not files:
        raise SystemExit("No HTML files in the manifest. Run build/build.py first.")
    return files


def resolve_link(page: Path, href: str) -> Path | None:
    if href.startswith(("http://", "https://", "mailto:", "tel:")):
        return None
    path = href.split("#", 1)[0].split("?", 1)[0]
    if path == "":
        return page
    target = (page.parent / path).resolve()
    if not (target == ROOT or ROOT in target.parents):
        raise SystemExit(f"Link escapes the site: {href} from {page}")
    if target.is_dir():
        target = target / "index.html"
    return target


def main() -> None:
    facts = json.loads((ROOT / "data" / "facts.json").read_text(encoding="utf-8"))
    failures: list[str] = []

    def check(condition: bool, message: str) -> None:
        if not condition:
            failures.append(message)

    samples = {
        "": "how-to-save/index.html",
        "how-to-save": "../index.html",
        "how-to-save:price": "../price-and-editions/index.html",
        "tools/garage-cost-planner": "../../index.html",
        "tools": "garage-cost-planner/index.html",
        "home-tool": "tools/garage-cost-planner/index.html",
    }
    check(build.rel_href("", "how-to-save") == samples[""], "rel home to question")
    check(build.rel_href("how-to-save", "") == samples["how-to-save"], "rel question to home")
    check(
        build.rel_href("how-to-save", "price-and-editions") == samples["how-to-save:price"],
        "rel question to question",
    )
    check(
        build.rel_href("tools/garage-cost-planner", "") == samples["tools/garage-cost-planner"],
        "rel nested tool to home",
    )
    check(build.rel_href("tools", "tools/garage-cost-planner") == samples["tools"], "rel tools to child")
    check(build.rel_href("", "tools/garage-cost-planner") == samples["home-tool"], "rel home to tool")

    pages = html_files()
    seen_titles: set[str] = set()
    for page in pages:
        parser = Parser()
        text = page.read_text(encoding="utf-8")
        parser.feed(text)
        visible = " ".join("".join(parser.text).split())
        rel = page.relative_to(ROOT).as_posix()
        check(len(parser.h1) == 1, f"{rel} should have one H1, found {parser.h1}")
        check(bool(parser.title), f"{rel} missing title")
        check(parser.title not in seen_titles, f"Duplicate title {parser.title}")
        seen_titles.add(parser.title)
        check(CHECKED in visible, f"{rel} missing last checked date")
        check(DISCLAIMER in visible, f"{rel} missing disclaimer")
        check("Sources" in visible, f"{rel} missing Sources")
        check(parser.canonical.startswith("https://e13ctr0n1c.github.io/gta6-guide/"), f"{rel} canonical")
        descriptions = [content for name, _prop, content in parser.metas if name == "description"]
        check(len(descriptions) == 1 and bool(descriptions[0]), f"{rel} meta description")
        og = {prop: content for _name, prop, content in parser.metas if prop.startswith("og:")}
        for key in ("og:title", "og:description", "og:url", "og:type"):
            check(bool(og.get(key)), f"{rel} missing {key}")
        check(og.get("og:url") == parser.canonical, f"{rel} og:url should match canonical")
        check(parser.jsonld, f"{rel} missing JSON-LD")
        for block in parser.jsonld:
            try:
                data = json.loads(block)
            except json.JSONDecodeError as exc:
                failures.append(f"{rel} invalid JSON-LD: {exc}")
                continue
            check(data.get("@context") == "https://schema.org", f"{rel} JSON-LD context")
            check(bool(data.get("@type")), f"{rel} JSON-LD type")
            if data.get("@type") == "FAQPage" and rel not in {"index.html"}:
                entity = data["mainEntity"][0]
                check(entity["name"] == parser.h1[0], f"{rel} FAQ question should match H1")
                check(entity["acceptedAnswer"]["text"] == parser.answer, f"{rel} FAQ answer should match the first paragraph")
        check(len(parser.ids) == len(set(parser.ids)), f"{rel} duplicate ids {parser.ids}")
        lowered = text.lower()
        for word in FORBIDDEN:
            check(word not in lowered, f"{rel} contains forbidden text {word}")
        check("\u2014" not in text and "\u2013" not in text and " - " not in text, f"{rel} uses a dash as punctuation")
        for href in parser.links:
            check(not href.startswith("/"), f"{rel} root-relative link {href}")
            check(not href.lower().startswith("javascript:"), f"{rel} script link")
            target = resolve_link(page, href)
            if target is not None:
                check(target.is_file(), f"{rel} broken internal link {href} -> {target}")
        for src in parser.srcs:
            if src.startswith(("http://", "https://")):
                continue
            check("screenshot" not in src.lower(), f"{rel} screenshot asset {src}")
            target = resolve_link(page, src)
            if target is not None and not src.startswith("#"):
                check(target.is_file(), f"{rel} missing asset {src}")

    index = (ROOT / "index.html").read_text(encoding="utf-8")
    for slug in build.REQUIRED_SLUGS:
        check(f"{slug}/index.html" in index or f'href="{slug}/index.html"' in index, f"Home should link to {slug}")
        check((ROOT / slug / "index.html").is_file(), f"Missing page {slug}")

    money = (ROOT / "tools" / "money-planner" / "index.html").read_text(encoding="utf-8")
    check("estimates from published guides" in money, "Money planner phrase")
    check("I do not add ranges into an exact sum." in money, "Money planner refuses a sum")
    garage = html.unescape((ROOT / "tools" / "garage-cost-planner" / "index.html").read_text(encoding="utf-8"))
    check("one or a couple" in garage, "Garage planner should show the GameSpot capacity line")
    check("single car" in garage, "Garage planner should show the PC Gamer capacity line")
    for item in facts["prices"]["garages"]:
        check(item["name"] in garage, f"Missing garage {item['name']}")
        if item["price_usd"]:
            check(f"${item['price_usd']:,}" in garage, f"Missing price for {item['name']}")
    tools = (ROOT / "tools" / "index.html").read_text(encoding="utf-8")
    check("Vehicle price lookup" in tools, "Tools page should refuse vehicle prices")
    check("Weapon/Ammu-Nation price lookup" in tools, "Tools page should refuse weapon prices")
    check("32,750" not in tools and "32750" not in index, "Excluded fan wiki price leaked")
    cheats = (ROOT / "tools" / "cheat-finder" / "index.html").read_text(encoding="utf-8")
    check("Up, Right, Down, Left, Up, Left, Down, Right" in cheats, "Published cheat missing")
    check("Many codes are still unknown." in cheats, "Unknown cheats should be stated")
    js = (ROOT / "assets" / "tools.js").read_text(encoding="utf-8")
    for banned in ("localStorage", "sessionStorage", "document.cookie", "indexedDB", "fetch(", "XMLHttpRequest"):
        check(banned not in js, f"tools.js uses {banned}")
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if "node_modules" in path.parts or ".git" in path.parts:
            continue
        check(path.suffix.lower() not in IMAGE_SUFFIXES, f"Unexpected image file {path}")
        if path.suffix.lower() == ".svg":
            check("screenshot" not in path.name.lower(), path.name)

    gift_line = "Gifting a gamer this Christmas? Try my free Gamer Gift Kit Lite"
    gift_href = "https://arthurverse67.gumroad.com/l/gamergiftkitlite"
    for page in pages:
        text = page.read_text(encoding="utf-8")
        check(gift_line in text, f"{page.name} missing the footer gift line")
        check(f'href="{gift_href}" rel="noopener"' in text, f"{page.name} gift link rel")
        check('data-gift' in text, f"{page.name} missing the gift wrapper")
        check("day > 26" in text, f"{page.name} missing the 26 December hide rule")
    gift_page = (ROOT / "gift-ideas" / "index.html").read_text(encoding="utf-8")
    check("https://arthurverse67.gumroad.com/l/gamergiftkit" in gift_page, "Full kit link")
    check("£2.49" in gift_page, "Full kit price in pounds")
    check("3.26" not in gift_page and "5.23" not in gift_page, "Converted dollar prices should stay off the page")
    gift_main = gift_page.split("<footer", 1)[0]
    gift_start = gift_main.find('<div data-gift>')
    gift_end = gift_main.find("</div>", gift_start)
    check(gift_start != -1 and gift_end != -1, "Gift pitch wrapper")
    check("openworldtracker" not in gift_main[gift_start:gift_end], "Progress sheet should stay outside the Christmas hide block")
    check("openworldtrackerlite" in gift_main[gift_end:], "Gift page progress sheet line")
    length_page = (ROOT / "how-long-to-beat" / "index.html").read_text(encoding="utf-8")
    check('href="https://arthurverse67.gumroad.com/l/openworldtrackerlite"' in length_page, "Length page free sheet")
    check('href="https://arthurverse67.gumroad.com/l/openworldtracker"' in length_page, "Length page full sheet")
    check("£3.99" in length_page, "Full sheet price")
    check('rel="noopener"' in length_page, "Progress sheet rel")
    for page in pages:
        footer = page.read_text(encoding="utf-8").split("<footer", 1)[-1]
        check("openworldtracker" not in footer, f"{page.name} footer should not advertise the progress sheet")
    check("gift-ideas/" in (ROOT / "sitemap.xml").read_text(encoding="utf-8"), "Sitemap gift page")
    check("gift-ideas/index.html" in index, "Home links to gift ideas")

    robots = (ROOT / "robots.txt").read_text(encoding="utf-8")
    check("Sitemap: https://e13ctr0n1c.github.io/gta6-guide/sitemap.xml" in robots, "robots sitemap")
    sitemap = (ROOT / "sitemap.xml").read_text(encoding="utf-8")
    check("404.html" not in sitemap, "404 should stay out of the sitemap")
    check((ROOT / "llms.txt").is_file(), "llms.txt")
    check((ROOT / "404.html").is_file(), "404.html")

    if failures:
        print("\n".join(failures))
        raise SystemExit(f"{len(failures)} checks failed")
    print(f"OK {len(pages)} pages")


if __name__ == "__main__":
    main()
