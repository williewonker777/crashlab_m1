#!/usr/bin/env python3
"""Check lecture 3 content, deck structure and optional slide-level scope."""

import argparse
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
import re
import sys


class DeckParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []
        self.sections = {}
        self.text = {}
        self.current = None
        self.count = None
        self.refs = []
        self.svgs = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        element_id = attrs.get("id", "")
        if element_id:
            self.ids.append(element_id)
        if tag == "main" and "data-deck" in attrs:
            self.count = attrs.get("data-slide-count")
        if tag == "section" and element_id.startswith("slide-"):
            self.current = element_id
            self.sections[element_id] = attrs
            self.text[element_id] = []
        if tag == "svg" and self.current:
            self.svgs.append((self.current, attrs))
        for value in attrs.values():
            if value:
                self.refs.extend(re.findall(r"url\(#([^\)]+)\)", value))
        if attrs.get("href", "").startswith("#"):
            self.refs.append(attrs["href"][1:])

    handle_startendtag = handle_starttag

    def handle_endtag(self, tag):
        if tag == "section":
            self.current = None

    def handle_data(self, data):
        if self.current:
            self.text[self.current].append(data)


def slide_source(html):
    result = {}
    for section in re.findall(r"<section\b.*?</section>", html, re.DOTALL):
        match = re.search(r'\bid="(slide-\d+)"', section)
        if match:
            result[match[1]] = section
    return result


def check(html, baseline=None, structure_only=False):
    deck = DeckParser()
    deck.feed(html)
    errors = []

    def expect(condition, message):
        if not condition:
            errors.append(message)

    expected = [f"slide-{number}" for number in range(1, 67)]
    expect(list(deck.sections) == expected, "Deck must retain 66 ordered slides")
    expect(deck.count == "66", "data-slide-count must be 66")
    expect(deck.sections.get("slide-23", {}).get("data-title") == "카메라 투영 모델",
           "Slide 23 must remain the projection lesson")
    expect(deck.sections.get("slide-27", {}).get("data-title") == "삼각측량",
           "Slide 27 must remain the triangulation lesson")
    duplicates = [name for name, count in Counter(deck.ids).items() if count > 1]
    expect(not duplicates, f"Duplicate IDs: {duplicates}")
    expect(set(deck.refs) <= set(deck.ids),
           f"Missing fragment/marker targets: {set(deck.refs) - set(deck.ids)}")
    for number, (name, attrs) in enumerate(deck.sections.items(), 1):
        expect(attrs.get("aria-label", "").startswith(f"슬라이드 {number} / 66:"),
               f"Invalid slide aria-label: {name}")
    for name, attrs in deck.svgs:
        if name in {"slide-23", "slide-27"}:
            expect(attrs.get("role") == "img" and bool(attrs.get("aria-label")),
                   f"Diagram requires an accessible label: {name}")
            expect(bool(attrs.get("viewbox")), f"Diagram requires a viewBox: {name}")

    if not structure_only:
        projection = " ".join(deck.text.get("slide-23", []))
        triangulation = " ".join(deck.text.get("slide-27", []))
        expect(not re.search(r"ᵀ|Σ|‖|\[R\|t\]|s\s*\[u|fₓ|f_y", projection),
               "Slide 23 must not retain the projection formula/symbol definitions")
        for term in ["3차원", "픽셀", "모서리", "렌즈", "뎁스"]:
            expect(term in projection, f"Slide 23 missing intuitive explanation: {term}")
        for term in ["시차", "관측값", "계산", "결과", "스테레오", "단안",
                     "시선", "위치·방향", "순수 회전", "교차각", "스케일"]:
            expect(term in triangulation, f"Slide 27 missing concept distinction: {term}")

    if baseline is not None:
        original, updated = slide_source(baseline), slide_source(html)
        expect(set(original) == set(updated), "Slide IDs changed from baseline")
        changed = {name for name in set(original) & set(updated)
                   if original[name] != updated[name]}
        expect(changed <= {"slide-23", "slide-27"},
               f"Unrelated slides changed: {sorted(changed - {'slide-23', 'slide-27'})}")
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("html", nargs="?", type=Path,
                        default=Path(__file__).resolve().parents[1] / "lecture-3.html")
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--structure-only", action="store_true")
    args = parser.parse_args()
    baseline = args.baseline.read_text(encoding="utf-8") if args.baseline else None
    errors = check(args.html.read_text(encoding="utf-8"), baseline, args.structure_only)
    if errors:
        print("\n".join(f"FAIL: {error}" for error in errors), file=sys.stderr)
        return 1
    print("PASS: lecture 3 — 66 slides, content, accessibility and references")
    if baseline is not None:
        print("PASS: only slides 23 and 27 differ from baseline")
    return 0


if __name__ == "__main__":
    sys.exit(main())
