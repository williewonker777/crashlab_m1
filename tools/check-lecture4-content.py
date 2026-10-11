#!/usr/bin/env python3
"""Validate lecture 4's VLA theory and robot-description chapters without third-party packages."""

from __future__ import annotations

import argparse
from collections import defaultdict
from html import escape, unescape
from html.parser import HTMLParser
from pathlib import Path
import re
import sys
import tempfile
from urllib.parse import unquote, urlsplit
import xml.etree.ElementTree as ET


EXPECTED_SLIDES = 72
MODEL_OFFSET = 34
ORIGINAL_MODEL_START = 15
ORIGINAL_MODEL_END = 38
VLA_SLIDES = ORIGINAL_MODEL_START + MODEL_OFFSET - 1
QUESTION_STEPS = {2: "01", 10: "02", 24: "03", 33: "04", 39: "05"}
# Existing layouts retained from the original introductory material.
LEGACY_VLA_CLASSES = {
    3: {"visual-full", "layout-diagram"}, 5: {"layout-split"},
    7: {"layout-compare"}, 8: {"layout-compare"},
    11: {"visual-full", "layout-diagram"},
    12: {"vla-slide", "layout-compare", "layout-guide", "vla-term-guide"},
    25: {"photo-timeline", "layout-diagram"},
    26: {"photo-timeline", "layout-split"},
    27: {"photo-timeline", "layout-diagram"},
    28: {"photo-timeline", "layout-split"},
    30: {"visual-wide", "layout-diagram"}, 32: {"layout-split"},
    34: {"visual-full", "layout-diagram"}, 36: {"layout-split"},
    37: {"layout-compare", "layout-guide"},
}
SNIPPET_KINDS = {"fragment", "document", "command"}
SNIPPET_LANGUAGES = {"language-xml", "language-python", "language-bash", "language-usda"}

# Small, lecture-facing contracts: enough to catch changed teaching values without
# tying the checker to a workstation path or to the complete production models.
XML_SNIPPET_CONTRACTS = {
    "slide-20": (
        (".//joint[@name='l_wrist2']", {"type": "fixed"}),
        (".//joint[@name='l_wrist2']/origin", {
            "xyz": (0.0, 0.0, -0.073), "rpy": (0.0, 0.0, 1.57079632679),
        }),
        (".//joint[@name='l_wrist2']/parent", {"link": "left_arm_link_7"}),
        (".//joint[@name='l_wrist2']/child", {"link": "left_wrist2_link"}),
    ),
    "slide-21": (
        (".//joint[@name='l_gripper_input']", {"type": "revolute"}),
        (".//joint[@name='l_gripper_input']/origin", {"xyz": (0.0, 0.0, -0.0935)}),
        (".//joint[@name='l_gripper_input']/axis", {"xyz": (1.0, 0.0, 0.0)}),
        (".//joint[@name='l_gripper_input']/limit", {
            "lower": 0.0, "upper": 1.3125, "effort": 1000.0, "velocity": 3.0,
        }),
    ),
    "slide-22": (
        (".//link", {}),
        (".//visual/geometry/mesh", {
            "filename": None, "scale": (0.001, 0.001, 0.001),
        }),
        (".//collision/geometry/mesh", {
            "filename": None, "scale": (0.001, 0.001, 0.001),
        }),
    ),
    "slide-23": (
        (".//inertial/origin", {
            "xyz": (-0.00032333365841, -2.136268376e-09, -0.030713841795),
        }),
        (".//inertial/mass", {"value": 0.18059836361}),
        (".//inertial/inertia", {
            "ixx": 0.00018559729196,
            "iyy": 0.0003965177481,
            "izz": 0.00032950360851,
        }),
    ),
    "slide-25": (
        (".//mimic", {
            "joint": "l_gripper_input", "multiplier": -1.0, "offset": 0.0,
        }),
    ),
    "slide-28": (
        (".//compiler", {"angle": "degree", "meshdir": "meshes"}),
        (".//body[@name='left_wrist2']", {
            "pos": (0.0, 0.0, -0.073), "euler": (0.0, 0.0, 90.0),
        }),
    ),
    "slide-29": (
        (".//equality/joint", {
            "joint1": "l_gripper_output", "joint2": "l_gripper_input",
            "polycoef": (0.0, -1.0, 0.0, 0.0, 0.0),
        }),
        (".//actuator/motor", {
            "name": "l_gripper_input", "joint": "l_gripper_input",
            "ctrllimited": "false",
        }),
    ),
}

XML_SNIPPET_CONTRACTS = {
    f"slide-{int(name.split('-')[1]) + MODEL_OFFSET}": rules
    for name, rules in XML_SNIPPET_CONTRACTS.items()
}


class DeckParser(HTMLParser):
    """Collect only the HTML facts needed by the checker."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.ids: list[tuple[str, str | None]] = []
        self.sections: dict[str, dict[str, str | None]] = {}
        self.text: dict[str, list[str]] = defaultdict(list)
        self.current_slide: str | None = None
        self.deck_count: str | None = None
        self.counter_text: list[str] = []
        self._in_counter = 0
        self.svgs: list[tuple[str | None, dict[str, str | None]]] = []
        self.references: list[tuple[str, str | None]] = []
        self.local_urls: list[tuple[str, str, str | None]] = []
        self.anchors: list[tuple[str, str | None]] = []
        self.snippets: list[dict[str, object]] = []
        self._pre_stack: list[dict[str, object]] = []
        self._code_stack: list[dict[str, object]] = []
        self.labels: list[tuple[str, str, str]] = []
        self._label_stack: list[dict[str, object]] = []

    def handle_starttag(self, tag: str, attrs_list) -> None:
        attrs = dict(attrs_list)
        element_id = attrs.get("id")
        if tag == "section" and element_id and re.fullmatch(r"slide-\d+", element_id):
            self.current_slide = element_id
            self.sections[element_id] = attrs
        if element_id:
            self.ids.append((element_id, self.current_slide))
        is_summary = tag == "p" and bool(
            {"key-line", "model-takeaway"} & set((attrs.get("class") or "").split())
        )
        if (tag in {"h2", "h3", "strong"} or is_summary) and self.current_slide:
            self._label_stack.append({"tag": tag, "slide": self.current_slide, "text": []})

        if tag == "main" and "data-deck" in attrs:
            self.deck_count = attrs.get("data-slide-count")
        if tag == "svg":
            self.svgs.append((self.current_slide, attrs))
        if "data-counter" in attrs:
            self._in_counter += 1

        for value in attrs.values():
            if value:
                for target in re.findall(r"url\(\s*#([^\s\)]+)\s*\)", value):
                    self.references.append((target, self.current_slide))
        for attr_name in ("href", "xlink:href"):
            value = attrs.get(attr_name, "") or ""
            if value.startswith("#") and len(value) > 1:
                self.references.append((value[1:], self.current_slide))

        if tag == "a":
            href = attrs.get("href", "") or ""
            self.anchors.append((href, self.current_slide))

        url_attrs = {
            "a": ("href",),
            "img": ("src", "srcset"),
            "script": ("src",),
            "link": ("href",),
            "source": ("src", "srcset"),
            "video": ("src", "poster"),
            "audio": ("src",),
            "image": ("href", "xlink:href"),
            "use": ("href", "xlink:href"),
        }
        for attr_name in url_attrs.get(tag, ()):
            value = attrs.get(attr_name)
            if value:
                if value.startswith("data:"):
                    continue
                values = []
                for part in value.split(","):
                    fields = part.strip().split()
                    if fields:
                        values.append(fields[0])
                self.local_urls.extend((tag, item, self.current_slide) for item in values if item)

        if tag == "pre":
            self._pre_stack.append({"attrs": attrs, "codes": []})
        elif tag == "code" and self._pre_stack:
            code = {"attrs": attrs, "text": []}
            self._pre_stack[-1]["codes"].append(code)
            self._code_stack.append(code)

    handle_startendtag = handle_starttag

    def handle_endtag(self, tag: str) -> None:
        if self._label_stack and self._label_stack[-1]["tag"] == tag:
            label = self._label_stack.pop()
            self.labels.append((str(label["slide"]), str(label["tag"]), "".join(label["text"])))
        if tag == "code" and self._code_stack:
            self._code_stack.pop()
        elif tag == "pre" and self._pre_stack:
            pre = self._pre_stack.pop()
            pre["slide"] = self.current_slide
            self.snippets.append(pre)
        elif tag == "section":
            self.current_slide = None
        if self._in_counter and tag == "div":
            self._in_counter -= 1

    def handle_data(self, data: str) -> None:
        for label in self._label_stack:
            label["text"].append(data)
        if self.current_slide:
            self.text[self.current_slide].append(data)
        if self._in_counter:
            self.counter_text.append(data)
        if self._code_stack:
            self._code_stack[-1]["text"].append(data)


def slide_source(html: str) -> dict[str, str]:
    """Return raw top-level slide sections, preserving bytes within each section."""
    result: dict[str, str] = {}
    for section in re.findall(r"<section\b.*?</section\s*>", html, re.DOTALL | re.IGNORECASE):
        match = re.search(r'\bid\s*=\s*["\'](slide-\d+)["\']', section, re.IGNORECASE)
        if match:
            result[match.group(1)] = section
    return result


def normalized_model_slide(source: str, number: int) -> str:
    """Normalize only the section ID and its ARIA number/total, not body bytes."""
    opening, remainder = source.split(">", 1)
    opening = re.sub(rf'(\bid=["\'])slide-{number}(["\'])',
                     r"\1{SLIDE}\2", opening, count=1)
    opening = re.sub(
        rf'(aria-label=["\']슬라이드\s+){number}(\s*/\s*)\d+(\s*:)',
        r"\1{NUMBER}\2{TOTAL}\3", opening, count=1,
    )
    return opening + ">" + remainder


def visible_text(parser: DeckParser, slide: str) -> str:
    return " ".join(" ".join(parser.text.get(slide, [])).split())


# Whitespace is ignored because SVG text and inline HTML split visible phrases.
TERM_GUIDE_PATTERNS = {
    11: {
        "tokenizer stage": r"토크나이저.*?문장→조각[·ㆍ,]번호",
        "embedding stage": r"임베딩.*?번호→벡터",
        "image token count": r"(?<![\d.])256개",
        "text token count": r"(?<![\d.])7개",
        "state token count": r"(?<![\d.])1개",
    },
    12: {term: re.escape(term) for term in (
        "토큰", "벡터", "토크나이저", "임베딩", "비전인코더", "트랜스포머",
    )},
    13: {
        **{f"example {value}": rf"(?<![\d.−-]){re.escape(value)}(?![\d.])"
           for value in ("0.5", "-0.2", "1.0", "0.48", "-0.10")},
        **{f"dimension {value}": rf"(?<![\d.,]){value}(?![\d.,])"
           for value in ("1152", "2048")},
        "weight count": r"(?<![\d.,])8,?192(?![\d.,])",
        "educational example label": "교육용예시",
    },
    15: {term: re.escape(term) for term in ("행동전문가", "확산트랜스포머")},
}
TERM_GUIDE_FIXTURES = {
    11: " 토크나이저 문장 → 조각 · 번호 임베딩 번호 → 벡터 영상 256개 문장 7개 상태 1개",
    12: " 토큰 벡터 토크나이저 임베딩 비전 인코더 트랜스포머",
    13: " 교육용 예시 입력 0.5 · −0.2 · 1.0 출력 0.48 · −0.10 연결 1152 → 2048 가중치 8,192개",
    15: " 행동 전문가 확산 트랜스포머",
}


def term_guide_errors(parser: DeckParser) -> list[str]:
    errors = []
    for number, patterns in TERM_GUIDE_PATTERNS.items():
        visible = visible_text(parser, f"slide-{number}").replace("−", "-")
        text = re.sub(r"\s+", "", visible)
        # Preserve separators between adjacent SVG numeric labels (0.48 −0.10).
        # Only join decimal/grouping punctuation split across inline text nodes.
        numeric_text = re.sub(r"(?<=\d[.,])\s+(?=\d)", "", visible)
        numeric_text = re.sub(r"(-)\s+(?=\d)", r"\1", numeric_text)
        for label, pattern in patterns.items():
            candidate = numeric_text if number == 13 and label != "educational example label" else text
            if not re.search(pattern, candidate):
                errors.append(f"Missing term guide contract: slide-{number}: {label}")
        if number == 11 and "단어조각→벡터" in text:
            errors.append("Tokenizer must not conflate pieces with embedding vectors: slide-11")
    return errors


def parse_xml_snippet(source: str, kind: str) -> ET.Element:
    """Parse documents directly and fragments beneath a neutral synthetic root."""
    return ET.fromstring(source if kind == "document" else f"<root>{source}</root>")


def numeric_values(value: str) -> tuple[float, ...] | None:
    try:
        return tuple(float(part) for part in value.split())
    except ValueError:
        return None


def contract_errors(xml_roots: dict[str, ET.Element]) -> list[str]:
    errors = []
    for slide, rules in XML_SNIPPET_CONTRACTS.items():
        root = xml_roots.get(slide)
        if root is None:
            errors.append(f"Missing parseable XML teaching snippet: {slide}")
            continue
        for xpath, attributes in rules:
            element = root.find(xpath)
            if element is None:
                errors.append(f"XML teaching contract missing {xpath}: {slide}")
                continue
            for name, expected in attributes.items():
                actual = element.get(name)
                if expected is None:
                    if not actual:
                        errors.append(f"XML teaching contract needs non-empty {xpath}@{name}: {slide}")
                elif isinstance(expected, str):
                    if actual != expected:
                        errors.append(
                            f"XML teaching value changed {xpath}@{name}: "
                            f"expected {expected!r}, found {actual!r} ({slide})"
                        )
                else:
                    expected_values = expected if isinstance(expected, tuple) else (expected,)
                    actual_values = numeric_values(actual or "")
                    matches = actual_values is not None and len(actual_values) == len(expected_values)
                    if matches:
                        matches = all(
                            abs(actual_value - expected_value)
                            <= max(1e-12, abs(expected_value) * 1e-9)
                            for actual_value, expected_value in zip(actual_values, expected_values)
                        )
                    if not matches:
                        wanted = " ".join(str(value) for value in expected_values)
                        errors.append(
                            f"XML teaching value changed {xpath}@{name}: "
                            f"expected {wanted!r}, found {actual!r} ({slide})"
                        )
    return errors


def local_target(root: Path, raw_url: str) -> tuple[Path, str] | None:
    if not raw_url or raw_url.startswith(("#", "data:", "mailto:", "tel:", "javascript:")):
        return None
    parsed = urlsplit(raw_url)
    if parsed.scheme or parsed.netloc or raw_url.startswith("//"):
        return None
    relative = unquote(parsed.path)
    if not relative:
        return None
    return (root / relative).resolve(), unquote(parsed.fragment)


def page_ids(path: Path) -> tuple[set[str], bool]:
    try:
        source = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return set(), False
    parser = DeckParser()
    parser.feed(source)
    return {name for name, _ in parser.ids}, bool(parser.sections)


def check_index(root: Path, total: int) -> list[str]:
    index_path = root / "index.html"
    if not index_path.is_file():
        return ["index.html is missing"]
    source = index_path.read_text(encoding="utf-8")
    card = re.search(
        r'<a\b[^>]*href=["\']lecture-4\.html(?:#[^"\']*)?["\'][^>]*>(.*?)</a\s*>',
        source,
        re.DOTALL | re.IGNORECASE,
    )
    if not card:
        return ["index.html must contain a lecture-4.html card"]
    count = re.search(r"\b(\d+)\s+slides\b", unescape(re.sub(r"<[^>]+>", " ", card.group(1))), re.I)
    if not count or int(count.group(1)) != total:
        return [f"index.html lecture 4 count must be {total} slides"]
    return []


def check(html: str, html_path: Path, baseline: str | None = None) -> list[str]:
    parser = DeckParser()
    parser.feed(html)
    errors: list[str] = []

    def expect(condition: bool, message: str) -> None:
        if not condition:
            errors.append(message)

    slide_names = list(parser.sections)
    total = len(slide_names)
    expected = [f"slide-{number}" for number in range(1, total + 1)]
    expect(total == EXPECTED_SLIDES,
           f"Deck must contain exactly {EXPECTED_SLIDES} slides (found {total})")
    expect(slide_names == expected, "Slides must be consecutively ordered from slide-1")
    expect(parser.deck_count == str(total), f"data-slide-count must match actual count {total}")
    counter = " ".join(" ".join(parser.counter_text).split())
    expect(bool(re.search(rf"\b1\s*/\s*{total}\b", counter)),
           f"Visible deck counter must start at 1 / {total}")

    model_chapters = [name for name, attrs in parser.sections.items()
                      if "model-chapter" in (attrs.get("class") or "").split()]
    expect(model_chapters == [f"slide-{VLA_SLIDES + 1}"],
           f"Robot model chapter must begin at slide-{ORIGINAL_MODEL_START + MODEL_OFFSET}")
    model_start = int(model_chapters[0].split("-")[1]) if model_chapters else total + 1

    for number, name in enumerate(slide_names, 1):
        attrs = parser.sections[name]
        label = attrs.get("aria-label", "") or ""
        expect(bool(re.match(rf"^슬라이드\s+{number}\s*/\s*{total}\s*:", label)),
               f"Invalid slide aria-label: {name}")
        if number >= model_start:
            classes = set((attrs.get("class", "") or "").split())
            expect(bool(classes & {"model-slide", "model-chapter"}),
                   f"New slide requires model-slide or model-chapter class: {name}")

    id_locations: dict[str, list[str | None]] = defaultdict(list)
    for element_id, slide in parser.ids:
        id_locations[element_id].append(slide)
    for element_id, locations in id_locations.items():
        if len(locations) < 2:
            continue
        expect(False, f"Duplicate ID: {element_id}")

    ids = set(id_locations)
    raw_url_refs = set(re.findall(r"url\(\s*#([^\s\)]+)\s*\)", html))
    missing_refs = sorted(
        {target for target, _ in parser.references if target not in ids}
        | {target for target in raw_url_refs if target not in ids}
    )
    expect(not missing_refs, f"Missing fragment/marker targets: {missing_refs}")

    for slide, attrs in parser.svgs:
        label = attrs.get("aria-label") or attrs.get("aria-labelledby")
        expect(attrs.get("role") == "img" and bool(label),
               f"SVG requires role=img and an accessible label: {slide or 'page chrome'}")
        expect(bool(attrs.get("viewbox")), f"SVG requires a viewBox: {slide or 'page chrome'}")

    root = html_path.resolve().parent
    checked_pages: dict[Path, tuple[set[str], bool]] = {}
    for tag, raw_url, slide in parser.local_urls:
        target = local_target(root, raw_url)
        if target is None:
            continue
        path, fragment = target
        try:
            path.relative_to(root)
        except ValueError:
            errors.append(f"Local URL escapes repository: {raw_url}")
            continue
        expect(path.is_file(), f"Missing local asset/link target: {raw_url}")
        if fragment and path.is_file() and path.suffix.lower() in {".html", ".htm"}:
            if path not in checked_pages:
                checked_pages[path] = page_ids(path)
            target_ids, is_deck = checked_pages[path]
            expect(fragment in target_ids or (fragment == "slide-last" and is_deck),
                   f"Missing local anchor target: {raw_url}")
    for href, _ in parser.anchors:
        expect(bool(href.strip()), "Every <a> element requires a non-empty href")

    expect(bool(parser.snippets), "At least one code example is required")
    raw_pre_bodies = re.findall(r"<pre\b[^>]*>(.*?)</pre\s*>", html, re.DOTALL | re.IGNORECASE)
    for number, body in enumerate(raw_pre_bodies, 1):
        expect(bool(re.fullmatch(r"\s*<code\b[^>]*>.*?</code\s*>\s*", body,
                                 re.DOTALL | re.IGNORECASE)),
               f"Code example {number} must use a direct <pre><code> wrapper")
    xml_roots: dict[str, ET.Element] = {}
    for pre in parser.snippets:
        codes = pre["codes"]
        slide = pre.get("slide") or "unknown slide"
        expect(len(codes) == 1, f"<pre> must contain exactly one <code>: {slide}")
        if len(codes) != 1:
            continue
        code = codes[0]
        classes = set((code["attrs"].get("class", "") or "").split())
        languages = classes & SNIPPET_LANGUAGES
        expect(len(languages) == 1,
               f"Code example needs one supported language class: {slide}")
        kind = code["attrs"].get("data-snippet") or pre["attrs"].get("data-snippet")
        expect(kind in SNIPPET_KINDS,
               f"Code example needs data-snippet=fragment|document|command: {slide}")
        source = "".join(code["text"]).strip()
        expect(bool(source), f"Code example must not be empty: {slide}")
        if kind in {"fragment", "document"} and source and "language-xml" in languages:
            try:
                xml_roots[str(slide)] = parse_xml_snippet(source, str(kind))
            except ET.ParseError as exc:
                errors.append(f"XML {kind} is not well-formed on {slide}: {exc}")
        elif kind == "document" and source and "language-python" in languages:
            try:
                compile(source, f"<{slide} python snippet>", "exec")
            except SyntaxError as exc:
                errors.append(f"Runnable Python document has invalid syntax on {slide}: {exc.msg}")
    errors.extend(contract_errors(xml_roots))

    def range_text(start: int, end: int) -> str:
        return " ".join(visible_text(parser, f"slide-{number}") for number in range(start, end + 1))

    for name, source in slide_source(html).items():
        if int(name.split("-")[1]) >= model_start:
            expect(not any(term in source for term in ("연심실", "과제")),
                   f"Internal source label must not appear in lecture content: {name}")
    sentence_ending = re.compile(
        r"(?:한다|된다|는다|인다|있다|없다|아니다|정도다|쓴다|옮긴다|맞춘다|시킨다|만든다)[.!?]?$"
    )
    # Exact legacy sentence retained from original slide 9; new sentences are checked.
    legacy_label_exceptions = {
        ("slide-27", "관절 값과 영상은 같은 시각에 맞춰야 한다."),
    }
    for name, tag, label in parser.labels:
        if (name, label.strip()) in legacy_label_exceptions:
            continue
        # Only the question heading is exempt, not its index or summary labels.
        if tag == "h2" and name in {f"slide-{n}" for n in QUESTION_STEPS}:
            continue
        expect(not sentence_ending.search(label.strip()),
               f"Heading/stage label must use nominal phrasing: {name}: {label.strip()}")

    def require_terms(label: str, text: str, terms: tuple[tuple[str, ...], ...]) -> None:
        folded = text.casefold()
        for alternatives in terms:
            expect(any(term.casefold() in folded for term in alternatives),
                   f"Missing required learning element in {label}: {' / '.join(alternatives)}")

    raw_slides = slide_source(html)
    for number in range(1, VLA_SLIDES + 1):
        name = f"slide-{number}"
        classes = set((parser.sections.get(name, {}).get("class") or "").split())
        required = ({"slide--title", "layout-title"} if number == 1 else
                    {"slide--question", "layout-question"} if number in QUESTION_STEPS else
                    LEGACY_VLA_CLASSES.get(number, {"vla-slide"}))
        expect({"slide"} | required <= classes and not classes & {"model-chapter", "model-slide"},
               f"Invalid VLA slide class composition: {name}")
    for number, step in QUESTION_STEPS.items():
        source = raw_slides.get(f"slide-{number}", "")
        menu = re.search(r'<ol\b[^>]*class="question-index"[^>]*>(.*?)</ol>', source, re.S)
        items = re.findall(r'<li\b([^>]*)>(.*?)</li>', menu[1], re.S) if menu else []
        current = [body for attrs, body in items if re.search(r'aria-current="step"', attrs)]
        expect(len(items) == 6 and len(current) == 1
               and bool(re.search(rf'<span>\s*{step}\s*</span>', current[0])),
               f"Question index must select step {step}: slide-{number}")
    title_menu = re.search(r'<ol\b[^>]*class="title-index"[^>]*>(.*?)</ol>',
                           raw_slides.get("slide-1", ""), re.S)
    expect(bool(title_menu) and len(re.findall(r'<li\b', title_menu[1])) == 6,
           "Title index must contain six items: slide-1")
    for number, hook in ((18, "data-token-demo"), (35, "data-chunk-demo")):
        expect(bool(re.search(rf'<[^>]+\s{hook}(?:\s|=|>)', raw_slides.get(f"slide-{number}", ""))),
               f"Missing VLA demo hook {hook}: slide-{number}")
    links = [href for href, slide in parser.anchors if slide == "slide-48"]
    expect(len(links) >= 21 and all(urlsplit(href).scheme == "https"
                                  and urlsplit(href).netloc for href in links),
           "VLA references require at least 21 HTTPS links: slide-48")
    for label, start, end, terms in (
        ("VLA concept", 3, 9, ("정책", "모방", "강화학습", "행동 복제")),
        ("VLA architecture", 11, 23, ("토큰", "VLM", "플로 매칭", "액션 청킹")),
        ("VLA training", 25, 32, ("에피소드", "사전학습", "미세조정", "LoRA")),
        ("VLA execution", 34, 38, ("추론", "청크", "Sim-to-Real", "신뢰구간")),
        ("VLA trends", 40, 48, ("RECAP", "WAM", "DreamZero", "기억")),
    ):
        require_terms(label, range_text(start, end), tuple((term,) for term in terms))

    errors.extend(term_guide_errors(parser))

    def model_text(start: int, end: int) -> str:
        return range_text(start + MODEL_OFFSET, end + MODEL_OFFSET)

    require_terms(f"slide {15 + MODEL_OFFSET} chapter", model_text(15, 15), (("URDF",), ("MJCF",), ("USD",)))
    require_terms(f"slide {16 + MODEL_OFFSET} sources", model_text(16, 16), (("PPTX",), ("XLSX",), ("STL",)))
    require_terms(
        f"slides {17 + MODEL_OFFSET}-{26 + MODEL_OFFSET} URDF",
        model_text(17, 26),
        (
            ("URDF",), ("link", "링크"), ("joint", "조인트", "관절"),
            ("visual", "시각 형상"), ("collision", "충돌"), ("inertial", "관성"),
            ("origin", "원점"), ("axis", "축"), ("limit", "한계"),
            ("mimic",), ("폐루프", "closed loop", "closed-loop"),
            ("단위", "mm", "m 단위"), ("좌표", "좌표계"),
        ),
    )
    require_terms(f"slide {27 + MODEL_OFFSET} formats", model_text(27, 27), (("URDF",), ("MJCF",), ("USD",)))
    require_terms(
        f"slides {28 + MODEL_OFFSET}-{32 + MODEL_OFFSET} MJCF",
        model_text(28, 32),
        (("MJCF",), ("actuator", "액추에이터", "drive", "드라이브"), ("collision", "충돌")),
    )
    require_terms(
        f"slides {33 + MODEL_OFFSET}-{35 + MODEL_OFFSET} USD",
        model_text(33, 35),
        (("USD", "USDA"), ("stage", "스테이지", "scene", "씬", "시뮬레이션 환경")),
    )
    require_terms(
        f"slide {36 + MODEL_OFFSET} revision validation",
        model_text(36, 36),
        (
            ("이전 리비전", "revision", "리비전"), ("USD",), ("URDF",), ("MJCF",),
            ("wrist2",),
            ("116.6007",), ("117.4993",), ("검증", "validation"),
        ),
    )
    revision_text = model_text(36, 36)
    wrist2_absence = re.search(
        r"(?:wrist2.{0,32}(?:없|미포함|제외)|(?:없|미포함|제외).{0,32}wrist2)",
        revision_text,
        re.IGNORECASE,
    )
    expect(bool(wrist2_absence), f"Slide {36 + MODEL_OFFSET} must state that wrist2 is absent from the older USD revision")
    require_terms(f"slide {37 + MODEL_OFFSET} practice", model_text(37, 37), (("실습",), ("결과물", "제출")))
    require_terms(f"slide {38 + MODEL_OFFSET} references", model_text(38, 38), (("공식",), ("문서", "documentation")))

    errors.extend(check_index(root, total))

    if baseline is not None:
        original = slide_source(baseline)
        updated = slide_source(html)
        for number in range(ORIGINAL_MODEL_START, ORIGINAL_MODEL_END + 1):
            old_name, new_name = f"slide-{number}", f"slide-{number + MODEL_OFFSET}"
            expect(old_name in original, f"Baseline must contain {old_name}")
            expect(new_name in updated, f"Updated deck must contain {new_name}")
            if old_name in original and new_name in updated:
                expect(
                    normalized_model_slide(original[old_name], number)
                    == normalized_model_slide(updated[new_name], number + MODEL_OFFSET),
                    f"Robot model slide changed beyond section ID/ARIA numbers: {new_name}",
                )
    return errors


def vla_fixture(number: int) -> tuple[str, str]:
    content = "정책 모방 강화학습 행동 복제 토큰 VLM 플로 매칭 액션 청킹 에피소드 사전학습 미세조정 LoRA 추론 청크 Sim-to-Real 신뢰구간 RECAP WAM DreamZero 기억"
    if number == 1 or number in QUESTION_STEPS:
        kind = "title" if number == 1 else "question"
        content += f'<ol class="{kind}-index">'
        for step in range(1, 7):
            selected = ' aria-current="step"' if QUESTION_STEPS.get(number) == f"{step:02}" else ""
            content += f'<li{selected}><span>{step:02}</span>단원</li>'
        content += "</ol>"
        classes = {f"slide--{kind}", f"layout-{kind}"}
    else:
        classes = LEGACY_VLA_CLASSES.get(number, {"vla-slide"})
    if number == 18:
        content += '<div data-token-demo></div>'
    if number == 35:
        content += '<div data-chunk-demo></div>'
    if number == 48:
        content += ''.join(f'<a href="https://example.org/{n}">논문</a>' for n in range(21))
    content += TERM_GUIDE_FIXTURES.get(number, "")
    return " " + " ".join(sorted(classes)), content


def fixture(root: Path, *, total: int = EXPECTED_SLIDES) -> tuple[Path, Path]:
    """Create a compact valid deck and baseline for mutation-based self-tests."""
    (root / "asset.svg").write_text("<svg/>", encoding="utf-8")
    slides = []
    topics = {
        15: "URDF MJCF USD 로봇 모델 강의",
        16: "PPTX XLSX STL 설계자료",
        17: "URDF robot link joint visual collision inertial origin axis limit 좌표계 단위 mm",
        20: "mimic 폐루프",
        27: "URDF MJCF USD 포맷 비교",
        28: "MJCF actuator 드라이브 collision 충돌 시뮬레이션 환경",
        33: "USD USDA stage 씬",
        36: "이전 리비전 검증: wrist2 없음, USD mass 116.6007, URDF MJCF 117.4993",
        37: "실습 결과물 제출",
        38: "공식 문서 documentation 링크",
    }
    xml_samples = {
        20: '<joint name="l_wrist2" type="fixed"><origin xyz="0 0 -0.073" '
            'rpy="0 0 1.57079632679"/><parent link="left_arm_link_7"/>'
            '<child link="left_wrist2_link"/></joint>',
        21: '<joint name="l_gripper_input" type="revolute"><origin xyz="0 0 -0.0935"/>'
            '<axis xyz="1 0 0"/><limit lower="0" upper="1.3125" effort="1000" '
            'velocity="3.0"/></joint>',
        22: '<link name="left_wrist1_link"><visual><geometry><mesh filename="WRIST1.stl" '
            'scale="0.001 0.001 0.001"/></geometry></visual><collision><geometry>'
            '<mesh filename="WRIST1.stl" scale="0.001 0.001 0.001"/>'
            '</geometry></collision></link>',
        23: '<inertial><origin xyz="-0.00032333365841 -2.136268376e-09 -0.030713841795"/>'
            '<mass value="0.18059836361"/><inertia ixx="0.00018559729196" '
            'iyy="0.0003965177481" izz="0.00032950360851"/></inertial>',
        25: '<mimic joint="l_gripper_input" multiplier="-1.0" offset="0.0"/>',
        28: '<compiler angle="degree" meshdir="meshes"/>'
            '<body name="left_wrist2" pos="0 0 -0.073" euler="0 0 90"/>',
        29: '<equality><joint joint1="l_gripper_output" joint2="l_gripper_input" '
            'polycoef="0 -1 0 0 0"/></equality><actuator><motor name="l_gripper_input" '
            'joint="l_gripper_input" ctrllimited="false"/></actuator>',
    }
    for emitted_number in range(1, total + 1):
        number = emitted_number - MODEL_OFFSET
        extra_class = " model-chapter" if number == 15 else " model-slide"
        content = topics.get(number, f"내용 {number}")
        if number == 17:
            content += (
                '<pre data-snippet="fragment"><code class="language-xml">'
                '&lt;link name="base"/&gt;</code></pre>'
            )
        if number in xml_samples:
            content += (
                '<pre data-snippet="fragment"><code class="language-xml">'
                f'{escape(xml_samples[number])}</code></pre>'
            )
        if number == 33:
            content += '<img src="asset.svg" alt="fixture">'
        if number == 36:
            content += (
                '<svg role="img" aria-label="검증 흐름" viewBox="0 0 10 10">'
                '<defs><marker id="arrow-28"></marker></defs>'
                '<path marker-end="url(#arrow-28)"></path></svg>'
            )
        if emitted_number <= VLA_SLIDES:
            extra_class, content = vla_fixture(emitted_number)
        number = emitted_number
        slides.append(
            f'<section class="slide{extra_class}" id="slide-{number}" '
            f'aria-label="슬라이드 {number} / {total}: 제목 {number}">{content}</section>'
        )
    html = (
        '<!doctype html><html><body><a href="#slide-1">처음</a>'
        f'<div data-counter>1 / {total}</div><main data-deck data-slide-count="{total}">'
        + "".join(slides) + "</main></body></html>"
    )
    baseline = "".join(
        slide.replace(f'id="slide-{n}"', f'id="slide-{n - MODEL_OFFSET}"', 1)
        .replace(f'슬라이드 {n} / {total}:', f'슬라이드 {n - MODEL_OFFSET} / 38:', 1)
        for n, slide in enumerate(slides, 1) if n > VLA_SLIDES
    )
    html_path = root / "lecture-4.html"
    baseline_path = root / "baseline.html"
    html_path.write_text(html, encoding="utf-8")
    baseline_path.write_text(baseline, encoding="utf-8")
    (root / "index.html").write_text(
        f'<a href="lecture-4.html"><span>{total} slides</span></a>', encoding="utf-8"
    )
    return html_path, baseline_path


def self_test() -> list[str]:
    failures: list[str] = []
    with tempfile.TemporaryDirectory(prefix="lecture4-check-") as directory:
        root = Path(directory)
        html_path, baseline_path = fixture(root)
        valid = html_path.read_text(encoding="utf-8")
        baseline = baseline_path.read_text(encoding="utf-8")
        valid_errors = check(valid, html_path, baseline)
        if valid_errors:
            failures.append("valid fixture was rejected: " + "; ".join(valid_errors))

        mutations = {
            "VLA class": valid.replace('class="slide vla-slide"', 'class="slide"', 1),
            "question step": valid.replace('<li aria-current="step"><span>01</span>', '<li><span>01</span>', 1),
            "demo hook": valid.replace("data-token-demo", "data-missing-demo", 1),
            "reference protocol": valid.replace("https://example.org/0", "http://example.org/0", 1),
            "VLA nominal summary": valid.replace('<div data-token-demo>', '<p class="model-takeaway">행동을 만든다</p><div data-token-demo>', 1),
            "question nominal summary": valid.replace(
                'aria-label="슬라이드 10 / 72: 제목 10">',
                'aria-label="슬라이드 10 / 72: 제목 10"><p class="key-line">행동을 만든다</p>',
                1,
            ),
            "question nominal index": valid.replace(
                '<li aria-current="step"><span>02</span>단원',
                '<li aria-current="step"><span>02</span><strong>행동을 만든다</strong>',
                1,
            ),
            "count mismatch": valid.replace(f'data-slide-count="{EXPECTED_SLIDES}"', 'data-slide-count="99"'),
            "new duplicate id": valid.replace(
                f'id="slide-{EXPECTED_SLIDES}"', f'id="slide-{EXPECTED_SLIDES}" data-test-id="x"'
            ).replace(
                "공식 문서 documentation 링크</section>",
                '공식 문서 documentation 링크<span id="arrow-28"></span></section>',
            ),
            "missing asset": valid.replace('src="asset.svg"', 'src="missing.svg"'),
            "missing fragment": valid.replace('url(#arrow-28)', 'url(#missing-arrow)'),
            "baseline mutation": valid.replace("내용 18", "변경된 내용 18"),
            "required term": valid.replace("mimic", "coupling"),
            "fixed origin value": valid.replace("-0.073", "-0.730", 1),
            "inertial mass value": valid.replace("0.18059836361", "18.059836361", 1),
            "equality polynomial": valid.replace("0 -1 0 0 0", "0 1 0 0 0", 1),
            "malformed XML fragment": valid.replace("&lt;/joint&gt;", "&lt;/jont&gt;", 1),
            "internal source label": valid.replace("설계자료", "연심실_과제1 자료", 1),
            "sentence stage label": valid.replace(
                "URDF MJCF USD 로봇 모델 강의",
                "<strong>URDF를 작성한다</strong> URDF MJCF USD 로봇 모델 강의", 1,
            ),
        }
        expected_messages = {
            "VLA class": "Invalid VLA slide class composition",
            "question step": "Question index must select step 01",
            "demo hook": "Missing VLA demo hook",
            "reference protocol": "VLA references require at least 21 HTTPS",
            "VLA nominal summary": "Heading/stage label must use nominal phrasing",
            "question nominal summary": "Heading/stage label must use nominal phrasing: slide-10",
            "question nominal index": "Heading/stage label must use nominal phrasing: slide-10",
            "count mismatch": "data-slide-count",
            "new duplicate id": "Duplicate ID",
            "missing asset": "Missing local asset",
            "missing fragment": "Missing fragment",
            "baseline mutation": "Robot model slide changed",
            "required term": "Missing required learning element in slides 51-60 URDF: mimic",
            "fixed origin value": "XML teaching value changed .//joint[@name='l_wrist2']/origin@xyz",
            "inertial mass value": "XML teaching value changed .//inertial/mass@value",
            "equality polynomial": "XML teaching value changed .//equality/joint@polycoef",
            "malformed XML fragment": "XML fragment is not well-formed on slide-54",
            "internal source label": "Internal source label must not appear",
            "sentence stage label": "Heading/stage label must use nominal phrasing",
        }
        guide_mutations = {
            11: {"tokenizer stage": ("문장 → 조각 · 번호", "문장 → 벡터"),
                 "embedding stage": ("임베딩 번호 → 벡터", "임베딩 번호 → 목록"),
                 "image token count": ("256개", "255개"),
                 "text token count": ("7개", "5개"),
                 "state token count": ("1개", "2개")},
            12: {term: (term.replace("비전인코더", "비전 인코더"), "삭제")
                 for term in TERM_GUIDE_PATTERNS[12]},
            13: {**{f"example {value}": (value.replace("-", "−"), "9.99")
                    for value in ("0.5", "-0.2", "1.0", "0.48", "-0.10")},
                 "dimension 1152": ("1152", "1153"),
                 "dimension 2048": ("2048", "2049"),
                 "weight count": ("8,192", "8,193"),
                 "educational example label": ("교육용 예시", "실제 모델")},
            15: {"행동전문가": ("행동 전문가", "행동 모듈"),
                 "확산트랜스포머": ("확산 트랜스포머", "확산 모듈")},
        }
        sections = slide_source(valid)
        for number, replacements in guide_mutations.items():
            section = sections[f"slide-{number}"]
            for label, (old, new) in replacements.items():
                key = f"guide {number} {label}"
                # Replace throughout this slide so generic fixture terms cannot mask deletion.
                mutations[key] = valid.replace(section, section.replace(old, new))
                expected_messages[key] = f"Missing term guide contract: slide-{number}: {label}"
        mutations["conflated tokenizer"] = valid.replace(
            "토크나이저 문장 → 조각 · 번호", "토크나이저 문장 → 조각 · 번호 단어 조각 → 벡터", 1)
        expected_messages["conflated tokenizer"] = "Tokenizer must not conflate"
        mutations["guide layout"] = valid.replace("layout-guide vla-slide vla-term-guide", "vla-slide vla-term-guide", 1)
        expected_messages["guide layout"] = "Invalid VLA slide class composition: slide-12"
        for label, old, new in (
            ("numeric prefix boundary", "0.48", "10.48"),
            ("numeric suffix boundary", "−0.10", "−0.100"),
        ):
            section = sections["slide-13"]
            mutations[label] = valid.replace(section, section.replace(old, new))
            expected_messages[label] = "Missing term guide contract: slide-13: example " + old.replace("−", "-")
        adjacent = valid.replace(
            "입력 0.5 · −0.2 · 1.0 출력 0.48 · −0.10",
            "입력 <svg><text>0.5</text><text>−0.2</text><text>1.0</text>"
            "<text>0.48</text><text>−0.10</text></svg>",
        ).replace("<svg><text>", '<svg role="img" aria-label="계산 예시" viewBox="0 0 10 10"><text>')
        if check(adjacent, html_path, baseline):
            failures.append("adjacent SVG numeric labels were rejected")
        # Inline splits, ASCII minus and an ungrouped count are equivalent visible values.
        spaced = valid.replace("0.48", "<span>0.</span><span>48</span>").replace("−", "-").replace("8,192", "8192")
        if check(spaced, html_path, baseline):
            failures.append("inline-split numeric fixture was rejected")
        for label, mutated in mutations.items():
            messages = check(mutated, html_path, baseline)
            if not any(expected_messages[label] in message for message in messages):
                failures.append(f"{label} mutation was not detected as expected")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "html",
        nargs="?",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "lecture-4.html",
    )
    parser.add_argument("--baseline", type=Path, help="Original 38-slide lecture-4 HTML (robot slides 15-38)")
    parser.add_argument("--self-test", action="store_true", help="Run isolated negative tests")
    args = parser.parse_args()

    if args.self_test:
        failures = self_test()
        if failures:
            print("\n".join(f"FAIL: self-test: {message}" for message in failures), file=sys.stderr)
            return 1
        print("PASS: lecture 4 checker self-test (45 negative mutations detected)")
        return 0

    try:
        html = args.html.read_bytes().decode("utf-8")
        baseline = args.baseline.read_bytes().decode("utf-8") if args.baseline else None
    except (OSError, UnicodeError) as exc:
        print(f"FAIL: cannot read input: {exc}", file=sys.stderr)
        return 2
    errors = check(html, args.html, baseline)
    if errors:
        print("\n".join(f"FAIL: {error}" for error in errors), file=sys.stderr)
        return 1
    slide_count = len(parsed_sections(html))
    print(f"PASS: lecture 4 — {slide_count} slides, content, accessibility and references")
    if baseline is not None:
        print("PASS: robot slides 15-38 → 49-72 differ only in section ID/ARIA numbers")
    return 0


def parsed_sections(html: str) -> dict[str, dict[str, str | None]]:
    """Small reporting helper kept separate from validation state."""
    parser = DeckParser()
    parser.feed(html)
    return parser.sections


if __name__ == "__main__":
    sys.exit(main())
