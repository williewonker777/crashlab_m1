#!/usr/bin/env python3
"""Validate lecture 4's VLA theory and robot-description chapters without third-party packages."""

from __future__ import annotations

import argparse
from collections import defaultdict
from decimal import Decimal
from html import escape, unescape
from html.parser import HTMLParser
import math
from pathlib import Path
import re
import sys
import tempfile
import zipfile
from urllib.parse import unquote, urlsplit
import xml.etree.ElementTree as ET


EXPECTED_SLIDES = 75
MODEL_OFFSET = 37
ORIGINAL_MODEL_START = 15
ORIGINAL_MODEL_END = 38
REMOVED_ORIGINAL_MODEL_SLIDE = 36
# Original slide 36 (formerly deck slide 73) alone is intentionally omitted.
MODEL_SLIDE_NUMBERS = {
    **{number: number + MODEL_OFFSET for number in range(15, 36)},
    37: 74,  # Replaced by the gripper hands-on exercise, checked separately.
    38: 73,  # Unchanged recap precedes the two hands-on exercises.
}
PRACTICE_ZIP = "assets/data/lecture4/crashlab-urdf.zip"
PRACTICE_IMAGES = ("assets/img/lecture4/gripper-data-slide-2.png",)
TELEOP_IMAGE = "assets/img/lecture4/m1-teleoperation-box.png"

VLA_SLIDES = ORIGINAL_MODEL_START + MODEL_OFFSET - 1
QUESTION_STEPS = {2: "01", 10: "02", 26: "03", 36: "04", 42: "05"}
# Existing layouts retained from the original introductory material.
LEGACY_VLA_CLASSES = {
    3: {"visual-full", "layout-diagram"}, 5: {"layout-split"},
    7: {"layout-compare"}, 8: {"layout-compare"},
    11: {"visual-full", "layout-diagram"},
    12: {"vla-slide", "layout-compare", "layout-guide", "vla-term-guide"},
    27: {"photo-timeline", "layout-diagram"},
    28: {"photo-timeline", "layout-split"},
    29: {"photo-timeline", "layout-diagram"},
    30: {"photo-timeline", "layout-split"},
    33: {"visual-wide", "layout-diagram"}, 35: {"layout-split"},
    37: {"vla-slide"}, 39: {"layout-split"},
    40: {"layout-compare", "layout-guide"},
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
        self.downloads: list[tuple[str, str | None, str | None]] = []
        self.practice_selectors: list[str] = []
        self.teleop_images: list[dict[str, str | None]] = []
        self.teleop_parts: dict[str, list[str]] = defaultdict(list)
        self._teleop_stack: list[tuple[str, set[str]]] = []
        self._teleop_body_count = 0
        self.snippets: list[dict[str, object]] = []
        self._pre_stack: list[dict[str, object]] = []
        self._code_stack: list[dict[str, object]] = []
        self.labels: list[tuple[str, str, str]] = []
        self._label_stack: list[dict[str, object]] = []
        # Only the two definition slides need row/card-local teaching contracts.
        self.term_rows: list[dict[str, list[str]]] = []
        self.action_cards: list[dict[str, object]] = []
        self._term_row = None
        self._action_card = None
        self._guide_part = None
        self._in_guide_figure = False

    def handle_starttag(self, tag: str, attrs_list) -> None:
        attrs = dict(attrs_list)
        element_id = attrs.get("id")
        if tag == "section" and element_id and re.fullmatch(r"slide-\d+", element_id):
            self.current_slide = element_id
            self.sections[element_id] = attrs
        if self.current_slide == "slide-75":
            if tag == "img":
                self.teleop_images.append(attrs)
            regions = set(self._teleop_stack[-1][1]) if self._teleop_stack else set()
            classes = (attrs.get("class") or "").split()
            if tag == "ol" and "model-steps" in classes:
                regions.add("steps")
            # Keep ordered actions inside one step paragraph; headings and adjacent
            # steps must not supply a missing spatial or temporal relationship.
            if tag == "p" and "steps" in regions and any(
                parent_tag == "li" for parent_tag, _ in self._teleop_stack
            ):
                self._teleop_body_count += 1
                regions.add(f"step-body-{self._teleop_body_count}")
            if "vr-practice-note" in classes:
                regions.add("safety")
            if tag == "figcaption":
                regions.add("caption")
            if tag not in {"img", "br", "hr", "input", "source", "meta", "link", "wbr"}:
                self._teleop_stack.append((tag, regions))
        if self.current_slide == "slide-74" and (
            (tag == "input" and (attrs.get("type") or "").lower() == "radio") or tag == "select"
        ):
            self.practice_selectors.append(tag)
        if self.current_slide == "slide-12":
            if tag == "tr":
                self._term_row = {"th": [], "td": []}
                self.term_rows.append(self._term_row)
            elif tag in {"th", "td"} and self._term_row is not None:
                self._guide_part = (tag, self._term_row[tag])
        if self.current_slide == "slide-15":
            if tag == "article" and "vla-card" in (attrs.get("class") or "").split():
                self._action_card = {"heading": [], "paragraphs": []}
                self.action_cards.append(self._action_card)
            elif self._action_card is not None:
                if tag == "figure":
                    self._in_guide_figure = True
                elif tag == "h3":
                    self._guide_part = (tag, self._action_card["heading"])
                elif tag == "p" and not self._in_guide_figure and not attrs.get("class"):
                    paragraph = []
                    self._action_card["paragraphs"].append(paragraph)
                    self._guide_part = (tag, paragraph)
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
            self.downloads.append((href, attrs.get("download"), self.current_slide))

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
        if self._teleop_stack and self._teleop_stack[-1][0] == tag:
            self._teleop_stack.pop()
        if self._guide_part is not None and self._guide_part[0] == tag:
            self._guide_part = None
        if tag == "tr":
            self._term_row = None
        elif tag == "figure":
            self._in_guide_figure = False
        elif tag == "article":
            self._action_card = None
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
        if self._teleop_stack:
            for region in self._teleop_stack[-1][1]:
                self.teleop_parts[region].append(data)
        if self._guide_part is not None:
            self._guide_part[1].append(data)
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


# Approved prose edits only: no numeric, markup or whitespace normalization.
MODEL_TEXT_EDITS = {
    52: (("부품의 형상·좌표·질량 확인", "구성 요소의 형상·좌표·질량 확인"),),
    53: (("STL · 부품의 형상", "STL · 구성 요소의 형상"),),
    57: (("WRIST2는 손목에 고정된 부품이다.", "WRIST2는 손목에 고정된 구성 요소다."),),
    61: (("미러 부품의 좌표·관성 부호", "미러 손가락의 좌표·관성 부호"),),
    62: (("여러 손가락 부품의 움직임과 독립 구동 관절의 구분",
          "그리퍼 구성 요소의 움직임과 독립 구동 관절의 구분"),),
    58: (
        ('실제 +90° 손목 조립 후에는 부모 손목 기준 축도 달라진다.',
         '실제로는 손목을 +90° 돌려 조립하므로, 부모 손목 기준으로 보면 축 방향이 달라진다.'),
    ),
    59: (
        ('STL은 표면 형상 · 관절축·질량·조립 관계는 별도 정의',
         'STL에는 표면 형상만 · 관절축·질량·조립 관계는 따로 정의'),
        ('두 링크 완성 URDF',
         '두 링크를 채운 완성 URDF'),
        ('는 원본 URDF 옆에 놓고',
         '는 원본 URDF 옆에 두고'),
    ),
    60: (
        ('메시와 함께 0.001을 다시 곱하지 않는다.',
         '메시처럼 0.001을 곱하지 않는다.'),
        ('표의 COM은 WCS로 표기돼 있다.',
         '표의 COM은 WCS(설계 프로그램의 전체 좌표계) 기준이다.'),
        ('질량만 같아도 질량의 분포가 다르면 회전 운동은 달라진다.',
         '질량이 같아도 분포가 다르면 회전 운동이 달라진다.'),
        ('내보낸 부품 좌표계와 링크 좌표계', '내보낸 구성 요소의 좌표계와 링크 좌표계'),
    ),
    65: (
        ('이 사례의 MJCF는 시뮬레이션 설정을 별도 작성한 모델이다. 자동 변환 결과라고 가정하지 않는다.',
         '이 사례의 MJCF는 시뮬레이션 설정을 따로 작성한 모델이며, URDF를 자동 변환한 결과로 보면 안 된다.'),
        ('body · 부품의 위치와 방향', 'body · 구성 요소의 위치와 방향'),
    ),
    67: (
        ('비볼록 메시 하나로 구멍·오목한 형상이 그대로 충돌한다고 가정하지 않는다.',
         'MuJoCo는 메시 충돌을 볼록 껍질로 계산하므로, 구멍·오목한 부분이 그대로 충돌한다고 보면 안 된다.'),
    ),
    54: (("URDF의 역할: 제어 프로그램이 아닌 로봇 구조와 물성의 기술",
          "URDF의 역할: 제어 프로그램이 아니라 TF·IK·시뮬레이터가 읽는 로봇 구조와 물성의 기술"),
         ("몸통·팔·손가락처럼 함께 움직이는 부품 단위다.",
          "몸통·팔·손가락처럼 함께 움직이는 강체 단위다."),),
    66: (("이 모델은 motor를 사용한다. 위치 목표 추종은 별도의 제어기가 필요하다.",
          "이 모델의 motor는 ctrl에 gear를 곱한 값을 관절 토크로 바로 쓴다. 관절 목표각을 따라가려면 PD로 토크를 계산하는 제어기를 붙이거나, 목표와의 차이로 힘을 내는 position actuator를 쓴다."),),
    70: (("drive: stiffness·damping·힘 제한이 목적에 맞는가?",
          "drive: 관절 목표를 따라가는 stiffness(kp)·damping(kd)과 힘 제한이 목적에 맞는가?"),),
    68: (('<li><strong>씬별 로봇 참조 확인</strong><p>현재 scene_alice_m1.xml은 rohand 모델을 참조한다. 그리퍼 실습에는 위의 새 씬을 사용한다.</p></li>',
          '<li><strong>씬별 로봇 참조 확인</strong><p>현재 scene_alice_m1.xml은 rohand 모델을 참조한다. 그리퍼 실습에는 위의 새 씬을 사용한다.</p></li><li><strong>option · 물리 계산 주기</strong><p>timestep 0.002 s는 1초에 물리 계산 500번이다. 행동을 50 Hz로 보내면 물리 계산 10번마다 행동이 한 번 바뀐다.</p></li>'),),
}


# Mandatory, exact CAD-image replacements and slide-53 description removals.
# SVG viewBox and clip rectangles preserve the original page-2 raster pixels.
MODEL_SOURCE_EDITS = {53: (('<img class="model-image" src="assets/img/lecture4/assignment-arm.png" alt="설계자료의 PPTX에 포함된 ALICE M1 팔과 '
       '리비전 그리퍼 CAD 조립도">',
       '<svg class="model-image model-source-crop" viewBox="90 0 600 1080" role="img" aria-label="PPTX 2페이지의 '
       '팔·그리퍼 조립도: SHOULDER·ELBOW·WRIST1·WRIST2·INPUT·COUPLER·OUTPUT" data-source-crop="arm" '
       'overflow="hidden"><title>PPTX 2페이지의 팔·그리퍼 조립도: '
       'SHOULDER·ELBOW·WRIST1·WRIST2·INPUT·COUPLER·OUTPUT</title><defs><clipPath id="model-source-53-clip"><rect '
       'x="90" y="0" width="600" height="1080"/></clipPath></defs><image '
       'href="assets/img/lecture4/gripper-data-slide-2.png" x="0" y="0" width="1920" height="1080" '
       'clip-path="url(#model-source-53-clip)"/></svg>'),
      ('<p><span class="model-file">DD_GRP_DATA.pptx</span>의 조립도에서 73 mm·93.5 mm 간격과 손목의 90° 회전을 읽는다.</p>', ''),
      ('<p><span class="model-file">DD_STL/</span>의 WRIST1·WRIST2·INPUT·COUPLER·OUTPUT을 사용한다.</p>', ''),
      ('<p><span class="model-file">DD_REVISION-GRIPPER_MASS_PROPERTIES.xlsx</span>에서 질량·질량중심·관성을 읽는다.</p>', ''),
      ('제공 PPTX의 원본 그림.', '제공 PPTX 2페이지에서 잘라낸 팔·그리퍼 조립도.')),
 62: (('<img class="model-image" src="assets/img/lecture4/assignment-gripper.png" alt="INPUT, COUPLER, OUTPUT으로 '
       '구성된 리비전 그리퍼의 원본 CAD 형상">',
       '<svg class="model-image model-source-crop" viewBox="1050 500 670 480" role="img" aria-label="PPTX 2페이지의 '
       '그리퍼 연결부: INPUT·COUPLER·OUTPUT과 조인트 중심 위치" data-source-crop="linkage" overflow="hidden"><title>PPTX 2페이지의 '
       '그리퍼 연결부: INPUT·COUPLER·OUTPUT과 조인트 중심 위치</title><defs><clipPath id="model-source-62-clip"><rect x="1050" '
       'y="500" width="670" height="480"/></clipPath></defs><image '
       'href="assets/img/lecture4/gripper-data-slide-2.png" x="0" y="0" width="1920" height="1080" '
       'clip-path="url(#model-source-62-clip)"/></svg>'),
      ('설계자료의 PPTX 원본 형상과 실제 URDF mimic 발췌.', 'PPTX 2페이지에서 잘라낸 그리퍼 연결부와 실제 URDF mimic 발췌.')),
 67: (('<img class="model-image" src="assets/img/lecture4/assignment-wrist-rp.png" alt="설계자료의 PPTX에 포함된 손목 RP와 '
       '회전축 CAD 그림">',
       '<svg class="model-image model-source-crop" viewBox="1050 90 680 890" role="img" aria-label="PPTX 2페이지의 '
       '손목·그리퍼 조립도: WRIST1·WRIST2와 73 mm·93.5 mm 간격" data-source-crop="wrist-gripper" '
       'overflow="hidden"><title>PPTX 2페이지의 손목·그리퍼 조립도: WRIST1·WRIST2와 73 mm·93.5 mm 간격</title><defs><clipPath '
       'id="model-source-67-clip"><rect x="1050" y="90" width="680" height="890"/></clipPath></defs><image '
       'href="assets/img/lecture4/gripper-data-slide-2.png" x="0" y="0" width="1920" height="1080" '
       'clip-path="url(#model-source-67-clip)"/></svg>'),)}
SOURCE_HEADINGS = ("PPTX · 조립 관계와 치수", "STL · 구성 요소의 형상", "XLSX · 질량과 물성")


def visible_text(parser: DeckParser, slide: str) -> str:
    return " ".join(" ".join(parser.text.get(slide, [])).split())


# Whitespace is ignored because SVG text and inline HTML split visible phrases.
TERM_GUIDE_PATTERNS = {
    11: {
        "tokenizer stage": r"Tokenizer.*?문장→조각[·ㆍ,]번호",
        "embedding stage": r"Embedding.*?번호→Vector",
        "image token count": r"(?<![\d.])256개",
        "text token count": r"(?<![\d.])7개",
        "state token count": r"(?<![\d.])1개",
    },
    12: {term: re.escape(term) for term in (
        "Token", "Vector", "Tokenizer", "Embedding", "VisionEncoder", "Transformer",
    )},
    13: {
        **{f"example {value}": rf"(?<![\d.−-]){re.escape(value)}(?![\d.])"
           for value in ("0.5", "-0.2", "1.0", "0.48", "-0.10")},
        **{f"dimension {value}": rf"(?<![\d.,]){value}(?![\d.,])"
           for value in ("1152", "2048")},
        "weight count": r"(?<![\d.,])8,?192(?![\d.,])",
        "educational example label": "교육용예시",
    },
    14: {"original action-expert name": r"(?<![A-Za-z])ActionExpert(?![A-Za-z])"},
    15: {term: re.escape(term) for term in ("행동생성모듈", "ActionExpert", "DiffusionTransformer")},
}
TERM_GUIDE_FIXTURES = {
    11: " Tokenizer 문장 → 조각 · 번호 Embedding 번호 → Vector 영상 256개 문장 7개 상태 1개",
    12: " Token Vector Tokenizer Embedding Vision Encoder Transformer",
    13: " 교육용 예시 입력 0.5 · −0.2 · 1.0 출력 0.48 · −0.10 연결 1152 → 2048 가중치 8,192개",
    14: " Action Expert ·",
    15: " 행동 생성 모듈 Action Expert Diffusion Transformer",
}

# Standalone difficult terms retain short Korean meanings. Repeated card/table
# terms are checked through nearby role explanations below, not parentheses.
GLOSSARY_TERMS = {
    4: ('Policy', 'Episode', '신경망'),
    6: ('Pretraining',),
    7: ('Fine-tuning', 'Parameter'),
    9: ('지도학습',),
    14: ('VLM', 'Backbone', 'Action Head'),
    15: ('Noise',),
    17: ('Action Space', 'IK', '정규화', 'Percentile'),
    22: ('Flow Matching',),
    23: ('Action Chunking', 'Chunk', 'Inference'),
    24: ('Cross Entropy', '제곱 오차', 'L1 오차', 'Post-training'),
    25: ('Dual System', 'Latent Representation'),
    35: ('Checkpoint',),
    38: ('동기 실행', '비동기 실행'),
    39: ('Sim-to-Real',),
    41: ('신뢰구간', 'Benchmark'),
    46: ('Reasoning',),
    47: ('Advantage', 'RECAP'),
    48: ('WAM',),
    49: ('Mobile Manipulator',),
}
ACTION_SPACE_G = "g · 그리퍼 개폐 명령값"


# Definitions may live in adjacent prose rather than repeated term parentheses.
TERM_ROLE_CONTRACTS = {
    8: {
        'imitation role': ('모방학습.*?시연', '모방학습은 시연을 따라 배운다.'),
        'reinforcement role': ('강화학습.*?보상', '강화학습은 보상을 높인다.'),
        'behavior cloning role': ('BehaviorCloning.*?시연|시연.*?BehaviorCloning', 'Behavior Cloning은 시연을 모사한다.'),
    },
    9: {
        'distribution shift role': ('DistributionShift.*?(?:학습.*?다른|배운적없는상황.*?학습데이터에없)', 'Distribution Shift는 학습 때와 다른 상황이다.'),
        'drift role': ('Drift.*?오차.*?쌓|오차.*?쌓.*?Drift', 'Drift는 오차가 쌓인다.'),
    },
    12: {
        'token role': ('Token.*?입력조각', 'Token 모델이 읽는 입력 조각이다.'),
        'vector role': ('Vector.*?숫자목록', 'Vector 순서가 정해진 숫자 목록이다.'),
        'tokenizer role': ('Tokenizer.*?문장.*?조각.*?번호', 'Tokenizer 문장을 조각으로 잘라 번호를 붙인다.'),
        'embedding role': ('Embedding.*?번호.*?Vector', 'Embedding 번호를 Vector로 바꾼다.'),
        'vision encoder role': ('VisionEncoder.*?영상.*?조각.*?Vector', 'Vision Encoder 영상을 조각으로 나눠 Vector를 만든다.'),
        'transformer role': ('Transformer.*?Token.*?참고.*?정보', 'Transformer Token이 참고할 정보를 계산한다.'),
    },
    13: {
        'linear role': ('길이가다른숫자목록을모델이쓰는길이로바꾸는가장단순한계산이다', '길이가 다른 숫자 목록을 모델이 쓰는 길이로 바꾸는 가장 단순한 계산이다.'),
    },
    15: {
        'action expert role': ('상태[·ㆍ]행동Token만.*?작은가중치', '상태·행동 Token만 맡는 작은 가중치 묶음이다.'),
        'layerwise VLM reference': ('층마다.*?VLM.*?참고|VLM.*?층마다.*?참고', '층마다 VLM을 참고한다.'),
        'MoE expansion': ('MoE\\(MixtureofExperts\\)', 'MoE(Mixture of Experts)'),
        'DiT role': ('무작위값.*?다듬.*?Transformer.*?계산', '무작위 값을 다듬는 과정을 Transformer로 계산하는 구조다.'),
        'DiT expansion': ('DiT\\(DiffusionTransformer\\)', 'DiT(Diffusion Transformer)'),
    },
    18: {
        'discrete token role': ('DiscreteToken.*?구간.*?번호', 'Discrete Token은 구간 번호로 행동을 나타낸다.'),
        'regression role': ('Regression.*?한번.*?연속값|Regression.*?연속값.*?한번', 'Regression은 한 번에 연속값을 출력한다.'),
    },
    20: {
        'multimodal meaning': ('여기서Multimodal은입력종류\\(영상·문장\\)가아니라정답이여러갈래라는뜻이다', '여기서 Multimodal은 입력 종류(영상·문장)가 아니라 정답이 여러 갈래라는 뜻이다.'),
    },
    34: {
        'LoRA expansion': ('LoRA\\(Low-RankAdaptation\\)', 'LoRA(Low-Rank Adaptation)'),
        'consumer fine-tuning': ('소비자용GPU.*?Fine-tuning|Fine-tuning.*?소비자용GPU', '소비자용 GPU에서 Fine-tuning이 가능하다.'),
    },
    35: {
        'pipeline role': ('TrainingPipeline.*?데이터(?:수집|를모으고).*?시간축', 'Training Pipeline은 데이터 수집과 시간축 맞춤으로 시작한다.'),
    },
    38: {
        'RTC expansion': ('RTC\\(Real-TimeChunking\\)', 'RTC(Real-Time Chunking)'),
    },
    40: {
        'co-training name': ('Co-training', 'Co-training'),
    },
    47: {
        'value function role': ('가치함수\\(앞으로받을보상을예측하는함수\\)', '가치 함수(앞으로 받을 보상을 예측하는 함수)'),
    },
}


ACTION_PIPELINE_FIXTURES = {
    11: '<svg role="img" aria-label="구조" viewBox="0 0 10 10"><text>Action Head</text></svg>',
    14: '<svg role="img" aria-label="실행과 학습" viewBox="0 0 10 10"><text>Action Head 제어기 실선 실행 때 흐름 점선 학습 때만 쓰는 데이터</text><path stroke-dasharray="4 2"/></svg>',
    16: '<svg role="img" aria-label="수집 학습 실행" viewBox="0 0 10 10"><text>수집 사람 리더 팔 관절 목표 제어기 학습 저장된 관측 기록된 행동 정답 로봇 없음 실행 VLA Action Head</text></svg>',
    31: '<table><tbody>'
        '<tr><th scope="row">시각</th><td>기록 시각</td><td><code>frame_index</code> 62 · <code>timestamp</code> 1.24 s</td></tr>'
        '<tr><th scope="row">영상</th><td>이미지</td><td><code>observation.images.*</code></td></tr>'
        '<tr><th scope="row">관절 상태</th><td>측정한 관절각</td><td><code>observation.state</code> · 숫자 8개</td></tr>'
        '<tr><th scope="row">행동</th><td>제어기로 보낸 목표</td><td><code>action</code> · 숫자 8개</td></tr>'
        '<tr><th scope="row">명령</th><td>작업 문장</td><td><code>task</code></td></tr></tbody></table>',
    37: '<svg role="img" aria-label="실행" viewBox="0 0 10 10"><text>원래 단위 Chunk 하나씩 보내기 관절 제어기 드라이버 모터</text></svg>',
    48: '<svg role="img" aria-label="비교" viewBox="0 0 10 10"><text>Action Head</text></svg>',
}


# Prose and diagrams are independently required: SVG labels cannot replace the
# explanation of what is recorded, learned, dispatched, or controlled.
ACTION_PIPELINE_PROSE = {
    16: {
        "collection": (r"리더팔.*?관절각.*?목표.*?행동.*?관측.*?저장", "리더 팔의 관절각이 목표가 되고 행동과 관측을 저장한다."),
        "training": (r"로봇없이.*?ActionHead.*?기록된행동.*?차이.*?가중치", "로봇 없이 Action Head와 기록된 행동의 차이로 가중치를 고친다."),
        "deployment": (r"사람.*?VLA.*?같은형식.*?같은제어기", "사람 대신 VLA가 같은 형식의 목표를 같은 제어기로 보낸다."),
    },
    37: {
        "output units": (r"ActionHead.*?정규화.*?통계.*?원래단위.*?현재관절각.*?목표각", "Action Head의 정규화된 출력을 통계로 원래 단위로 되돌리고 현재 관절각을 더해 목표각을 만든다."),
        "chunk dispatch": (r"Chunk.*?제어주기.*?하나씩.*?50Hz.*?25개", "Chunk를 제어 주기마다 하나씩 보내며 50 Hz로 25개를 실행한다."),
        "controller": (r"제어기.*?목표.*?현재각도.*?차이.*?토크.*?드라이버.*?전류", "제어기가 목표와 현재 각도의 차이로 토크를 정하고 드라이버가 전류를 맞춘다."),
    },
}


def action_pipeline_errors(raw_slides: dict[str, str]) -> list[str]:
    errors = []

    def text(source: str) -> str:
        fragment = DeckParser()
        fragment.current_slide = "fragment"
        fragment.feed(source)
        return re.sub(r"\s+", "", " ".join(part for parts in fragment.text.values() for part in parts))

    def svg(number: int) -> str:
        return " ".join(re.findall(r"<svg\b.*?</svg>", raw_slides.get(f"slide-{number}", ""), re.S))

    for number in (11, 14, 48):
        labels = text(svg(number))
        if "ActionHead" not in labels or "행동출력" in labels:
            errors.append(f"Action Head diagram node required without old output label: slide-{number}")
    source = svg(14)
    labels = text(source)
    legend = text(raw_slides.get("slide-14", ""))
    if "제어기" not in labels or not all(term in legend for term in ("실선", "점선")) or not re.search(r'stroke-dasharray=["\']', source):
        errors.append("Action Head diagram must distinguish controller execution and training: slide-14")
    labels = text(svg(16))
    if not all(term in labels for term in ("수집", "학습", "실행", "리더팔", "관절목표", "기록된행동", "정답", "로봇없음", "제어기", "ActionHead")):
        errors.append("Action Head requires collection, training and deployment rows: slide-16")
    rows = re.findall(r"<tr\b[^>]*>(.*?)</tr>", raw_slides.get("slide-31", ""), re.S)
    row_data = {}
    scoped_row_count = 0
    for row in rows:
        heading = re.search(r'<th\b[^>]*scope="row"[^>]*>(.*?)</th>', row, re.S)
        if heading:
            scoped_row_count += 1
            row_data[text(heading[1])] = row
    expected = {"시각": ("frame_index", "timestamp"), "영상": ("observation.images.*",),
                "관절상태": ("observation.state",), "행동": ("action",), "명령": ("task",)}
    if len(row_data) != 5 or scoped_row_count != 5:
        errors.append("Frame table requires five scoped data rows: slide-31")
    for label, names in expected.items():
        codes = [text(code) for code in re.findall(r"<code\b[^>]*>(.*?)</code>", row_data.get(label, ""), re.S)]
        if not all(name in codes for name in names):
            errors.append(f"Frame row requires exact LeRobot code: slide-31: {label}")
    for label, required in (("관절상태", "측정"), ("행동", "목표")):
        if required not in text(row_data.get(label, "")):
            errors.append(f"Frame row must distinguish measured state and sent target: slide-31: {label}")
    if not all(value in text(row_data.get("시각", "")) for value in ("frame_index62", "timestamp1.24s")):
        errors.append("Frame example must retain frame 62 at 1.24 s: slide-31")
    for label in ("관절상태", "행동"):
        if "숫자8개" not in text(row_data.get(label, "")):
            errors.append(f"Frame example must retain eight values: slide-31: {label}")
    labels = text(svg(37))
    if not all(term in labels for term in ("원래단위", "Chunk", "하나씩", "제어기", "모터")):
        errors.append("Inference diagram requires units, chunk dispatch and controller stages: slide-37")
    for number, contracts in ACTION_PIPELINE_PROSE.items():
        # Scope to individual body paragraphs, independent of current cards/steps layout.
        paragraphs = [text(body) for body in re.findall(
            r"<p\b[^>]*>(.*?)</p>", raw_slides.get(f"slide-{number}", ""), re.S)]
        for label, (pattern, _) in contracts.items():
            if not any(re.search(pattern, paragraph) for paragraph in paragraphs):
                errors.append(f"Action pipeline prose explanation required: slide-{number}: {label}")
    return errors


# Body explanations and SVG examples are independent teaching contracts. An
# accessible name or a duplicate value elsewhere must not mask a missing label.
# Slide 20 derives the squared-error mean; slide 21 reuses its two answers.
NOISE_PROSE = {
    15: {
        "learning note": (r"학습때는시연행동에Noise를섞어놓고원래행동쪽으로돌아가는방향을맞히게한다", "학습 때는 시연 행동에 Noise를 섞어 놓고 원래 행동 쪽으로 돌아가는 방향을 맞히게 한다."),
        "execution counts": (r"실행때는무작위값에서시작해π0는10번,GR00TN1은4번다듬는다", "실행 때는 무작위 값에서 시작해 π0는 10번, GR00T N1은 4번 다듬는다."),
        "prediction targets": (r"Diffusion.*?모델은섞은Noise를,FlowMatching은행동쪽방향을맞힌다", "Diffusion(‘확산’) 모델은 섞은 Noise를, Flow Matching은 행동 쪽 방향을 맞힌다."),
        "random input": (r"입력의Noise섞인행동은처음엔무작위값이고,다듬을때마다행동에가까워진다", "입력의 Noise 섞인 행동은 처음엔 무작위 값이고, 다듬을 때마다 행동에 가까워진다."),
    },
    18: {
        "B learning target": (r"학습때는시연행동에Noise를섞고원래행동쪽방향이나섞은Noise를맞힌다", "학습 때는 시연 행동에 Noise를 섞고 원래 행동 쪽 방향이나 섞은 Noise를 맞힌다."),
    },
    20: {
        "two answers": (r"같은관측·명령에서시연절반은왼쪽\(a=-1\),절반은오른쪽\(a=\+1\)", "같은 관측·명령에서 시연 절반은 왼쪽(a = −1), 절반은 오른쪽(a = +1)으로 피했다."),
        "single output": (r"Regression은이관측에출력â하나를낸다", "Regression은 이 관측에 출력 â 하나를 낸다."),
        "loss expansion": (r"½\(â\+1\)²\+½\(â-1\)²=â²\+1", "두 시연과의 오차 제곱 평균은 ½(â + 1)² + ½(â − 1)² = â² + 1이다."),
        "minimum": (r"dL/dâ=2â=0에서â=0", "dL/dâ = 2â = 0에서 â = 0이다."),
        "mean beats answers": (r"정답±1의손실2보다평균의손실1이작다", "정답 ±1의 손실 2보다 평균의 손실 1이 작다."),
        "general mean": (r"제곱오차를가장작게하는출력은정답의평균E\[a\]다", "일반적으로 제곱 오차를 가장 작게 하는 출력은 정답의 평균 E[a]다."),
    },
    21: {
        "mixing formula": (r"x=\(1-τ\)ε\+τa", "섞기 · x = (1 − τ)ε + τa"),
        "mixing endpoints": (r"τ=0이면무작위Noiseε,1이면시연행동a", "τ = 0이면 무작위 Noise ε, 1이면 시연 행동 a이고 그 사이는 두 점을 잇는 직선 위다."),
        "mixing example": (r"0\.75×\(-0\.6\)\+0\.25×1=-0\.20", "예: 0.75 × (−0.6) + 0.25 × 1 = −0.20"),
        "slope derivation": (r"τ가0에서1로갈때x는a-ε만큼변하므로dx/dτ=a-ε=1\.6", "τ가 0에서 1로 갈 때 x는 a − ε만큼 변하므로 dx/dτ = a − ε = 1.6이다."),
        "model inputs": (r"a·ε를모른채x·τ와관측·명령만보고이기울기를맞힌다", "모델은 a·ε를 모른 채 x·τ와 관측·명령만 보고 이 기울기를 맞힌다."),
        "diffusion target": (r"Diffusion모델은기울기대신섞은Noise자체를맞힌다", "Diffusion 모델은 기울기 대신 섞은 Noise 자체를 맞힌다."),
        "loss example": (r"예측1\.2면\(1\.2-1\.6\)²=0\.16", "예측 1.2면 (1.2 − 1.6)² = 0.16이다."),
        "mean slope": (r"학습마다시연·Noise·τ를새로뽑으므로모델은한점을지나는여러직선의평균기울기를배운다", "학습마다 시연·Noise·τ를 새로 뽑으므로 모델은 한 점을 지나는 여러 직선의 평균 기울기를 배운다."),
        "execution": (r"x←x\+0\.1×예측을반복한다\(π0\)", "Noise에서 x ← x + 0.1 × 예측을 반복한다(π0)."),
        "start mean": (r"기울기-1-x와1-x의평균-x가0을가리켜", "출발점에서는 기울기 −1 − x와 1 − x의 평균 −x가 0을 가리켜,"),
        "one step mean": (r"한번에가면x\+\(-x\)=0에멈춘다", "한 번에 가면 x + (−x) = 0에 멈춘다."),
        "split steps": (r"나눠가며다시계산하면치우친쪽정답으로간다", "나눠 가며 다시 계산하면 치우친 쪽 정답으로 간다."),
        "educational scope": (r"교육용예시.*?정규분포Noise.*?50시점×8개", "교육용 예시. 왼쪽 −1·오른쪽 +1 두 시연, 정규분포 Noise, 학습이 잘 된 예측(평균 기울기)을 가정했다. 실제로는 행동 묶음 전체(예: 50시점 × 8개)에 같은 계산을 한다."),
    },
}
NOISE_OUTPUT_LABELS = ("행동 묶음 50개 · 다듬기 10번", "행동 묶음 · 다듬기 4번")
# Each label is one SVG <text>; no label may contain another one.
NOISE_SVG_LABELS = {
    18: ("Noise → 여러 번 다듬기 → 행동 묶음",),
    20: ("시연 A", "a = −1", "시연 B", "a = +1", "충돌", "출발",
         "L(â) = ½(â + 1)² + ½(â − 1)²", "= â² + 1", "정답 L = 2", "â = 0 · L = 1 최소"),
    21: ("학습 한 번", "손실 (1.2 − 1.6)² = 0.16", "ε = −0.6", "a = +1", "x = −0.20",
         "예측 1.2", "a − ε = 1.6", "τ = 0.25", "실행 10번", "Noise 0.5", "Noise −0.5",
         "+1 오른쪽", "−1 왼쪽", "평균 0·충돌", "0.1씩 10번", "한 번에 이동 → 0",
         "τ: 0 → 1 · 한 칸 0.1"),
}
# SVG coordinates are written with one decimal place.
PLOT_TOLERANCE = 0.06


def mean_loss(output: float) -> float:
    """Squared error against the two equally likely answers −1 and +1."""
    return 0.5 * (output + 1) ** 2 + 0.5 * (output - 1) ** 2


def ideal_flow(start: float, steps: int = 10) -> list[float]:
    """Euler steps along the mean slope of all training lines through (x, τ).

    With answers ±1 (each 1/2) and Noise ε ~ N(0, 1), the squared-error optimum is
    v*(x, τ) = (E[a | x] − x) / (1 − τ) with E[a | x] = tanh(x τ / (1 − τ)²).
    """
    delta, x, path = 1 / steps, start, [start]
    for k in range(steps):
        tau = k * delta
        expected = 0.0 if tau == 0 else math.tanh(x * tau / (1 - tau) ** 2)
        x += delta * (expected - x) / (1 - tau)
        path.append(x)
    return path


def svg_attributes(tag: str) -> dict[str, str]:
    return dict(re.findall(r'([\w:-]+)="([^"]*)"', tag))


def svg_points(value: str) -> list[tuple[float, float]]:
    return [tuple(float(part) for part in pair.split(",")) for pair in value.split()]


def plot_errors(number: int, source: str) -> list[str]:
    """Recompute plotted teaching curves instead of trusting their labels."""
    errors = []
    if number == 20:
        curves = [svg_attributes(tag) for tag in re.findall(r"<polyline\b[^>]*\bdata-loss-map=[^>]*>", source)]
        if len(curves) != 1:
            return ["Mean-action loss curve requires one mapped polyline: slide-20"]
        x0, xs, y0, ys = map(float, curves[0]["data-loss-map"].split())
        points = svg_points(curves[0].get("points", ""))
        outputs = [(x - x0) / xs for x, _ in points]
        if (len(points) < 20 or min(outputs) > -1.2 or max(outputs) < 1.2
                or any(abs(y - (y0 - ys * mean_loss(a))) > PLOT_TOLERANCE for a, (_, y) in zip(outputs, points))):
            errors.append("Mean-action loss curve must match L(â) = â² + 1: slide-20")
        circles = {(round(float(cx), 1), round(float(cy), 1)) for cx, cy in re.findall(
            r'<circle\b[^>]*\bcx="([^"]+)"[^>]*\bcy="([^"]+)"', source)}
        for output in (-1, 0, 1):
            marker = (round(x0 + xs * output, 1), round(y0 - ys * mean_loss(output), 1))
            if marker not in circles:
                errors.append(f"Mean-action loss markers must sit on L(±1) = 2 and L(0) = 1: slide-20")
                break
    if number == 21:
        flows = [svg_attributes(tag) for tag in re.findall(r"<polyline\b[^>]*\bdata-flow-start=[^>]*>", source)]
        starts = sorted(float(flow["data-flow-start"]) for flow in flows)
        if len(flows) != 2 or not (starts[0] < 0 < starts[1]):
            return ["Noise execution requires one flow from each Noise sign: slide-21"]
        lines = [svg_attributes(tag) for tag in re.findall(r"<line\b[^>]*\bstroke-dasharray=[^>]*>", source)]
        for flow in flows:
            start = float(flow["data-flow-start"])
            x0, xs, y0, ys = map(float, flow["data-flow-map"].split())
            points, expected = svg_points(flow.get("points", "")), ideal_flow(start)
            if (len(points) != len(expected) or abs(expected[-1] - math.copysign(1, start)) > 1e-9
                    or any(abs(px - (x0 + xs * k / 10)) > PLOT_TOLERANCE or abs(py - (y0 - ys * value)) > PLOT_TOLERANCE
                           for k, ((px, py), value) in enumerate(zip(points, expected)))):
                errors.append("Noise execution flow must match the ideal mean slope: slide-21")
            # One step of size 1 from x along the τ = 0 mean slope −x lands on 0.
            one_step = start + 1.0 * (0.0 - start)
            if not any(abs(float(line.get("x1", "nan")) - x0) <= PLOT_TOLERANCE
                       and abs(float(line.get("y1", "nan")) - (y0 - ys * start)) <= PLOT_TOLERANCE
                       and abs(float(line.get("x2", "nan")) - (x0 + xs)) <= PLOT_TOLERANCE
                       and abs(float(line.get("y2", "nan")) - (y0 - ys * one_step)) <= PLOT_TOLERANCE
                       for line in lines):
                errors.append("Noise one-step line must end at the mean 0: slide-21")
    return errors


def noise_training_errors(raw_slides: dict[str, str]) -> list[str]:
    errors = []

    def compact(source: str) -> str:
        parser = DeckParser()
        parser.current_slide = "fragment"
        parser.feed(source)
        return re.sub(r"\s+", "", "".join(part for parts in parser.text.values() for part in parts)).replace("−", "-")

    for number, contracts in NOISE_PROSE.items():
        source = raw_slides.get(f"slide-{number}", "")
        prose_source = source
        if number == 18:
            prose_source = " ".join(article for article in re.findall(r"<article\b.*?</article>", source, re.S)
                                    if re.search(r"<h3\b[^>]*>Diffusion\s*·\s*Flow Matching</h3>", article))
        body = compact(re.sub(r"<svg\b.*?</svg>", "", prose_source, flags=re.S))
        for label, (pattern, _) in contracts.items():
            if not re.search(pattern, body):
                errors.append(f"Noise prose contract missing: slide-{number}: {label}")
        svgs = " ".join(re.findall(r"<svg\b.*?</svg>", source, re.S))
        # <title> is an accessible description, not a visible numeric label. Each
        # <text> stays separate so adjacent badges cannot extend a number.
        labels = "|".join(compact(text) for text in re.findall(
            r"<text\b[^>]*>(.*?)</text>", re.sub(r"<(title|desc)\b.*?</\1>", "", svgs, flags=re.S), re.S))
        for label in NOISE_SVG_LABELS.get(number, ()):
            if compact(label) not in labels:
                errors.append(f"Noise SVG contract missing: slide-{number}: {label}")
        if number == 15:
            figures = re.findall(r'<figure\b[^>]*class="[^"]*\bvla-module-figure\b[^"]*"[^>]*>(.*?)</figure>', source, re.S)
            outputs = [re.findall(r'<p\b[^>]*class="[^"]*\bvla-module-output\b[^"]*"[^>]*>(.*?)</p>',
                                  re.sub(r"<svg\b.*?</svg>", "", figure, flags=re.S), re.S)
                       for figure in figures]
            for index, label in enumerate(NOISE_OUTPUT_LABELS):
                if index >= len(outputs) or len(outputs[index]) != 1 or compact(outputs[index][0]) != compact(label):
                    errors.append(f"Noise module output contract missing: slide-15: {label}")
        if number == 20:
            values = [re.search(pattern, labels) for pattern in (r"정답L=(\d+)", r"â=0·L=(\d+)최소")]
            if not all(values) or (Decimal(values[0][1]), Decimal(values[1][1])) != (
                    Decimal(str(mean_loss(1))), Decimal(str(mean_loss(0)))) or mean_loss(-1) != mean_loss(1):
                errors.append("Mean-action loss labels must equal L(±1) = 2 and L(0) = 1: slide-20")
            errors.extend(plot_errors(number, source))
        if number == 21:
            if 'vla-noise-slide' not in source or 'model-columns' not in source or 'vla-noise-diagram' not in svgs:
                errors.append("Noise example requires its scoped two-column diagram: slide-21")
            # Parse the displayed equations, then independently recompute them. This
            # catches internally inconsistent teaching arithmetic, not just tokens.
            found = {
                "mixing": re.search(r"(\d+\.\d+)×\((-\d+\.\d+)\)\+(\d+\.\d+)×(\d+(?:\.\d+)?)=(-\d+\.\d+)", body),
                "slope prose": re.search(r"dx/dτ=a-ε=(\d+(?:\.\d+)?)", body),
                "loss": re.search(r"손실\((\d+\.\d+)-(\d+\.\d+)\)²=(\d+\.\d+)", labels),
                "noise": re.search(r"(?:^|\|)ε=(-\d+(?:\.\d+)?)(?:\||$)", labels),
                "action": re.search(r"(?:^|\|)a=\+?(\d+(?:\.\d+)?)(?:\||$)", labels),
                "mixed": re.search(r"(?:^|\|)x=(-\d+\.\d+)(?:\||$)", labels),
                "slope": re.search(r"(?:^|\|)a-ε=(\d+(?:\.\d+)?)(?:\||$)", labels),
                "prediction": re.search(r"(?:^|\|)예측(\d+\.\d+)(?:\||$)", labels),
            }
            if not all(found.values()):
                errors.append("Noise arithmetic equation missing: slide-21")
            else:
                weight, epsilon, tau, action, mixed = map(Decimal, found["mixing"].groups())
                prediction, direction, squared_error = map(Decimal, found["loss"].groups())
                if not (weight + tau == 1 and weight * epsilon + tau * action == mixed
                        and Decimal(found["noise"][1]) == epsilon and Decimal(found["action"][1]) == action
                        and Decimal(found["mixed"][1]) == mixed
                        and action - epsilon == direction == Decimal(found["slope"][1]) == Decimal(found["slope prose"][1])
                        and Decimal(found["prediction"][1]) == prediction
                        and (prediction - direction) ** 2 == squared_error):
                    errors.append("Noise example arithmetic invariant failed: slide-21")
            errors.extend(plot_errors(number, source))
    return errors


# Compact spellings also catch terms split across inline HTML nodes.
OUTDATED_VLA_TERMS = (
    '행동전문가', '잡음', '확산트랜스포머', '잠재표현', '미세조정', '사전학습', '후학습', '행동복제', '이산토큰', '전문가혼합',
    '교차엔트로피', '다봉분포', '분위수', '행동공간', '분포이동', '이중시스템', '폴리시', '노이즈', '액션익스퍼트', '디퓨전트랜스포머',
    '디퓨전', '레이턴트표현', '파인튜닝', '프리트레이닝', '포스트트레이닝', '비헤이비어클로닝', '디스크리트토큰', '리그레션', '크로스엔트로피',
    '멀티모달분포', '퍼센타일', '플로매칭', '액션스페이스', '디스트리뷰션시프트', '듀얼시스템', '인퍼런스', '리즈닝', '액션청킹', '월드액션모델',
    '청킹', '청크', '행동토큰화', '토큰화', '토크나이저', '임베딩', '비전인코더', '트랜스포머', '토큰', '벡터', '백본', '에피소드',
    '파라미터', '어드밴티지', '학습파이프라인', '파이프라인', '체크포인트', '벤치마크', '모바일매니퓰레이터', '도메인랜덤화', '플래너', '디코딩',
    '메타데이터', '모델카드', '리더–팔로워', '라이선스', '드리프트',
)


def term_guide_errors(parser: DeckParser) -> list[str]:
    errors = []
    vla_text = "".join(visible_text(parser, f"slide-{n}") for n in range(1, VLA_SLIDES + 1))
    compact = re.sub(r"\s+", "", vla_text)
    if re.search(r"\b([A-Za-z][A-Za-z -]*?)\(\s*\1\s*\)", vla_text, re.IGNORECASE):
        errors.append("Repeated English term expansion must be removed")
    for term in OUTDATED_VLA_TERMS:
        if term in compact:
            errors.append(f"Outdated VLA term must use English spelling: {term}")
    for number, terms in GLOSSARY_TERMS.items():
        text = re.sub(r"\s+", "", visible_text(parser, f"slide-{number}"))
        for term in terms:
            if not re.search(re.escape(term.replace(" ", "")) + r"\([^()]*[가-힣][^()]*\)", text):
                errors.append(f"Missing short Korean explanation: slide-{number}: {term}")
    action_space_text = re.sub(r"\s+", "", visible_text(parser, "slide-17"))
    if ACTION_SPACE_G.replace(" ", "") not in action_space_text:
        errors.append("Action Space must explain g as the gripper open/close command value")
    for number, contracts in TERM_ROLE_CONTRACTS.items():
        text = re.sub(r"\s+", "", visible_text(parser, f"slide-{number}"))
        for label, (pattern, _) in contracts.items():
            candidates = [text]
            if number == 12:
                term = dict(zip(contracts, ("Token", "Vector", "Tokenizer", "Embedding", "VisionEncoder", "Transformer")))[label]
                candidates = [term + re.sub(r"\s+", "", " ".join(row["td"]))
                              for row in parser.term_rows
                              if re.sub(r"\s+", "", " ".join(row["th"])) == term]
            elif number == 15:
                name = "DiffusionTransformer" if label.startswith("DiT") else "ActionExpert"
                candidates = [re.sub(r"\s+", "", " ".join(paragraph))
                              for card in parser.action_cards
                              if name in re.sub(r"\s+", "", " ".join(card["heading"]))
                              for paragraph in card["paragraphs"]]
            if not any(re.search(pattern, candidate) for candidate in candidates):
                errors.append(f"Missing term role explanation: slide-{number}: {label}")
    if "Inference" in visible_text(parser, "slide-46"):
        errors.append("Reasoning must not be labelled model inference: slide-46")
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
        if number == 11 and "단어조각→Vector" in text:
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


def check_course_wording(html: str, html_path: Path) -> list[str]:
    """Check source text too, so ARIA labels and data-title cannot retain old wording."""
    root = html_path.resolve().parent
    sources = {html_path.resolve(): html}
    paths = set(root.glob("*.html")) | {
        root / name for name in ("DESIGN.md", "DESIGN-SVG.md", "VLA_THEORY.md")
    }
    for path in sorted(paths):
        if path.resolve() != html_path.resolve() and path.is_file():
            sources[path] = path.read_text(encoding="utf-8")
    return [f"Outdated course wording '부품': {path.name}"
            for path, source in sources.items() if "부품" in unescape(source)]


def check_practices(parser: DeckParser, root: Path) -> list[str]:
    errors = []
    for number, kind in ((74, "gripper-practice"), (75, "vr-practice")):
        matches = [name for name, attrs in parser.sections.items()
                   if kind in (attrs.get("class") or "").split()]
        if matches != [f"slide-{number}"]:
            errors.append(f"Practice placement requires {kind} only on slide-{number}")
    if list(parser.sections)[-1:] != ["slide-75"]:
        errors.append("VR practice must be the final slide-75")
    if (PRACTICE_ZIP, "크래쉬랩_urdf.zip", "slide-74") not in parser.downloads:
        errors.append("Gripper practice requires the exact ZIP download link and filename")
    for path in PRACTICE_IMAGES:
        if ("img", path, "slide-74") not in parser.local_urls:
            errors.append(f"Gripper practice requires source image: {path}")
    if any(slide == "slide-74" and "gripper-data-slide-3.png" in unquote(url)
           for _, url, slide in parser.local_urls):
        errors.append("Gripper practice must not reference the removed PPTX page 3 image")
    gripper = visible_text(parser, "slide-74")
    if re.search(r"(?<!\d)3\s*(?:p\b|페이지)|PPTX.{0,12}(?:page\s*3|3[- ]*page)", gripper, re.I):
        errors.append("Gripper practice must not include removed PPTX page 3 instructions")
    if parser.practice_selectors:
        errors.append("Gripper practice page 2 must be static without page selectors")
    contracts = {
        74: ("실습", "DD_GRP_DATA.pptx", "2p", "73 mm", "93.5 mm",
             "WRIST1", "WRIST2", "INPUT", "COUPLER", "OUTPUT", "URDF", "RViz", "meshes/", "결과물|제출", "자료 받기"),
        75: ("M1", "VR", "텔레오퍼레이션", "비상정지", "결과 영상|결과영상",
             "LeRobot v2.0", "Data Studio", "info.json", "modality.json", "episodes.jsonl",
             "tasks.jsonl", "stats.json", "episode_000000.parquet",
             "observation.images.left_view", "raw 데이터", "같은 규격", "100개"),
    }
    for number, terms in contracts.items():
        text = visible_text(parser, f"slide-{number}")
        for term in terms:
            if not any(option in text for option in term.split("|")):
                errors.append(f"Missing practice instruction on slide-{number}: {term}")
    images = [attrs for attrs in parser.teleop_images if attrs.get("src") == TELEOP_IMAGE]
    if not images:
        errors.append("M1 practice requires supplied image on slide-75")
    elif not all(all(term in (attrs.get("alt") or "") for term in ("M1", "박스"))
                 for attrs in images):
        errors.append("M1 practice image requires descriptive alt text")
    regions = {name: re.sub(r"\s+", " ", " ".join(parts))
               for name, parts in parser.teleop_parts.items()}
    caption = regions.get("caption", "")
    if not all(term in caption for term in ("사용자 제공", "시뮬레이션 화면")):
        errors.append("M1 practice caption must identify the supplied simulation screen")
    steps = regions.get("steps", "")
    for term in ("담당자", "M1", "VR", "기준 자세", "작업 공간", "저속"):
        if term not in steps:
            errors.append(f"Missing M1 procedural instruction: {term}")
    bodies = [text for name, text in regions.items() if name.startswith("step-body-")]
    for label, pattern in (
        ("pick object", r"(?:물체.{0,30}집|그리퍼.{0,20}닫고.{0,20}들어 올)"),
        ("place inside box", r"(?:박스 안|안쪽)[^.:]{0,30}(?:낮추고|내린 뒤).{0,40}(?:놓|넣)"),
        ("lower before release", r"(?:박스 안|안쪽)[^.:]{0,30}(?:낮추고|내린 뒤).{0,20}그리퍼.{0,20}(?:열|연)"),
        ("check after hand withdrawal", r"손.{0,20}(?:뺀|빼).{0,40}물체.{0,20}박스 안.{0,20}남.{0,20}확인"),
    ):
        if not any(re.search(pattern, text) for text in bodies):
            errors.append(f"M1 practice steps require {label}")
    safety = regions.get("safety", "")
    for label, pattern in (
        ("emergency stop", r"비상정지"),
        ("connection and tracking loss stop", r"연결[^.]{0,12}추적[^.]{0,20}끊김[^.]{0,30}정지"),
        ("no assumed automatic stop", r"자동 정지.{0,10}가정하지 않"),
        ("two-person physical operation", r"실물.{0,100}(?:2인 1조|두 명)"),
        ("outside motion zone", r"동작 구역 밖"),
    ):
        if not re.search(pattern, safety):
            errors.append(f"M1 practice safety requires {label}")
    try:
        with zipfile.ZipFile(root / PRACTICE_ZIP) as archive:
            names = archive.namelist()
            if archive.testzip() is not None:
                errors.append("Practice ZIP has corrupt members")
            if not any(Path(name).name == "DD_GRP_DATA.pptx" for name in names):
                errors.append("Practice ZIP is missing DD_GRP_DATA.pptx")
            if not any("meshes" in Path(name).parts and name.lower().endswith(".stl") for name in names):
                errors.append("Practice ZIP is missing mesh files")
            if not any(Path(name).name == "alice_m1.urdf" for name in names):
                errors.append("Practice ZIP is missing alice_m1.urdf")
    except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
        errors.append(f"Practice ZIP is missing or invalid: {exc}")
    return errors


def check_model_sources(slides: dict[str, str]) -> list[str]:
    errors = []
    for number, pairs in MODEL_SOURCE_EDITS.items():
        source = slides.get(f"slide-{number}", "")
        old_image, approved_crop = pairs[0]
        old_path = re.search(r'src="([^"]+)"', old_image).group(1)
        if source.count(approved_crop) != 1 or old_path in unquote(source):
            errors.append(f"Model source crop must match approved PPTX page-2 SVG: slide-{number}")
    source = slides.get("slide-53", "")
    steps = re.findall(r'<ol class="model-steps">(.*?)</ol>', source, re.S)
    expected = "".join(f"<li><strong>{heading}</strong></li>" for heading in SOURCE_HEADINGS)
    if len(steps) != 1 or re.sub(r">\s+<", "><", steps[0].strip()) != expected:
        errors.append("Slide-53 source list requires exactly three headings without descriptions")
    return errors


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
        ("slide-29", "관절 상태·행동과 영상은 같은 시각에 맞춰야 한다."),
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
    for number, hook in ((19, "data-token-demo"), (38, "data-chunk-demo")):
        expect(bool(re.search(rf'<[^>]+\s{hook}(?:\s|=|>)', raw_slides.get(f"slide-{number}", ""))),
               f"Missing VLA demo hook {hook}: slide-{number}")
    links = [href for href, slide in parser.anchors if slide == "slide-51"]
    expect(len(links) >= 21 and all(urlsplit(href).scheme == "https"
                                  and urlsplit(href).netloc for href in links),
           "VLA references require at least 21 HTTPS links: slide-51")
    for label, start, end, terms in (
        ("VLA concept", 3, 9, ("Policy", "모방", "강화학습", "Behavior Cloning")),
        ("VLA architecture", 11, 25, ("Token", "VLM", "Flow Matching", "Action Chunking")),
        ("VLA training", 27, 35, ("Episode", "Pretraining", "Fine-tuning", "LoRA")),
        ("VLA execution", 37, 41, ("Inference", "Chunk", "Sim-to-Real", "신뢰구간")),
        ("VLA trends", 43, 51, ("RECAP", "WAM", "DreamZero", "기억")),
    ):
        require_terms(label, range_text(start, end), tuple((term,) for term in terms))

    errors.extend(term_guide_errors(parser))
    errors.extend(action_pipeline_errors(raw_slides))
    errors.extend(noise_training_errors(raw_slides))

    def model_text(start: int, end: int) -> str:
        return range_text(MODEL_SLIDE_NUMBERS[start], MODEL_SLIDE_NUMBERS[end])

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
    errors.extend(check_practices(parser, root))
    errors.extend(check_model_sources(raw_slides))
    require_terms("slide 73 references", model_text(38, 38), (("공식",), ("문서", "documentation")))

    expect("이번학기일정" not in re.sub(r"\s+", "", visible_text(parser, "slide-50")),
           "Deleted semester schedule must not remain on slide-50")
    expect("수치를인용할때함께확인할출처와조건" not in
           re.sub(r"\s+", "", visible_text(parser, "slide-51")),
           "Deleted reference takeaway must not remain on slide-51")
    for name in slide_names:
        text = visible_text(parser, name)
        expect("로봇 모델 리비전 비교" not in text and
               not ("116.6007" in text and "117.4993" in text),
               f"Deleted model revision comparison must not remain: {name}")
    require_terms("slide 50 project checklist", range_text(50, 50),
                  (("행동 정의",), ("데이터",), ("모델",), ("실행",), ("평가",)))

    errors.extend(check_index(root, total))
    errors.extend(check_course_wording(html, html_path))

    if baseline is not None:
        original = slide_source(baseline)
        updated = slide_source(html)
        for number in range(ORIGINAL_MODEL_START, ORIGINAL_MODEL_END + 1):
            old_name = f"slide-{number}"
            expect(old_name in original, f"Baseline must contain {old_name}")
            if number == REMOVED_ORIGINAL_MODEL_SLIDE:
                continue
            emitted_number = MODEL_SLIDE_NUMBERS[number]
            new_name = f"slide-{emitted_number}"
            expect(new_name in updated, f"Updated deck must contain {new_name}")
            # Original practice 37 is intentionally replaced; check_practices owns its contract.
            if number == 37:
                continue
            if old_name in original and new_name in updated:
                approved = original[old_name]
                # Terminology is mandatory; earlier exact prose improvements remain optional.
                required_wording = original[old_name]
                for old, new in MODEL_TEXT_EDITS.get(emitted_number, ()):
                    approved = approved.replace(old, new)
                    if "부품" in old:
                        required_wording = required_wording.replace(old, new)
                for old, new in MODEL_SOURCE_EDITS.get(emitted_number, ()):
                    approved = approved.replace(old, new)
                    required_wording = required_wording.replace(old, new)
                allowed = {
                    normalized_model_slide(required_wording, number),
                    normalized_model_slide(approved, number),
                }
                expect(
                    normalized_model_slide(updated[new_name], emitted_number) in allowed,
                    f"Robot model slide contains an unapproved change: {new_name}",
                )
    return errors


def plot_fixture(number: int) -> str:
    """Valid mapped curves for slides 20 and 21, generated from the same models."""
    if number == 20:
        points = " ".join(f"{360 + 200 * a:.1f},{590 - 70 * mean_loss(a):.1f}"
                          for a in (i / 20 for i in range(-26, 27)))
        markers = "".join(f'<circle cx="{360 + 200 * a:.1f}" cy="{590 - 70 * mean_loss(a):.1f}" r="10"/>'
                          for a in (-1, 0, 1))
        return f'<polyline points="{points}" data-loss-map="360 200 590 70"/>' + markers
    if number == 21:
        markup = ""
        for start in (0.5, -0.5):
            points = " ".join(f"{190 + 52 * k:.1f},{482 - 105 * value:.1f}"
                              for k, value in enumerate(ideal_flow(start)))
            markup += f'<polyline points="{points}" data-flow-start="{start}" data-flow-map="190 520 482 105"/>'
            markup += (f'<line x1="190" y1="{482 - 105 * start:.1f}" x2="710" y2="482" '
                       'stroke-dasharray="12 10"/>')
        return markup
    return ""


def vla_fixture(number: int) -> tuple[str, str]:
    content = "Policy 모방 강화학습 Behavior Cloning Token VLM Flow Matching Action Chunking Episode Pretraining Fine-tuning LoRA Inference Chunk Sim-to-Real 신뢰구간 RECAP WAM DreamZero 기억"
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
    if number == 19:
        content += '<div data-token-demo></div>'
    if number == 38:
        content += '<div data-chunk-demo></div>'
    if number == 51:
        content += ''.join(f'<a href="https://example.org/{n}">논문</a>' for n in range(21))
    if number == 46:
        content = content.replace("Inference", "생각")
    content += TERM_GUIDE_FIXTURES.get(number, "")
    content += ACTION_PIPELINE_FIXTURES.get(number, "")
    content += "".join(f"<p>{sample}</p>" for _, sample in ACTION_PIPELINE_PROSE.get(number, {}).values())
    if number in NOISE_PROSE:
        noise_body = "".join(f"<p>{sample}</p>" for _, sample in NOISE_PROSE[number].values())
        if number == 18:
            noise_body = '<article class="vla-card"><h3>Diffusion · Flow Matching</h3>' + noise_body + '</article>'
        content += noise_body
        content += '<svg class="vla-noise-diagram" role="img" aria-label="Noise 학습" viewBox="0 0 100 100">'
        content += "".join(f"<text>{label}</text>" for label in NOISE_SVG_LABELS.get(number, ()))
        content += plot_fixture(number) + '</svg>'
        if number == 15:
            content += "".join(f'<figure class="vla-module-figure"><p class="vla-module-output">{label}</p></figure>'
                               for label in NOISE_OUTPUT_LABELS)
        if number == 21:
            classes = classes | {"vla-noise-slide"}
            content = '<div class="model-columns">' + content + '</div>'
    roles = TERM_ROLE_CONTRACTS.get(number, {})
    if number == 12:
        content += "<table>" + "".join(
            f"<tr><th>{term}</th><td>{sample}</td></tr>"
            for term, (_, sample) in zip(
                ("Token", "Vector", "Tokenizer", "Embedding", "Vision Encoder", "Transformer"), roles.values())
        ) + "</table>"
    elif number == 15:
        for name, dit in (("Action Expert", False), ("Diffusion Transformer", True)):
            content += f'<article class="vla-card"><h3>{name}</h3>'
            content += "".join(f"<p>{sample}</p>" for label, (_, sample) in roles.items()
                               if label.startswith("DiT") == dit)
            content += "</article>"
    else:
        content += "".join(" " + sample for _, sample in roles.values())
    if number == 50:
        content += " 행동 정의 데이터 모델 실행 평가"
    content += "".join(f" {term}(쉬운 역할 설명)" for term in GLOSSARY_TERMS.get(number, ()))
    if number == 17:
        content += " " + ACTION_SPACE_G
    return " " + " ".join(sorted(classes)), content


def fixture(root: Path, *, total: int = EXPECTED_SLIDES) -> tuple[Path, Path]:
    """Create a compact valid deck and baseline for mutation-based self-tests."""
    (root / "asset.svg").write_text("<svg/>", encoding="utf-8")
    slides = []
    zip_path = root / PRACTICE_ZIP
    zip_path.parent.mkdir(parents=True)
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr("DD_GRP_DATA.pptx", "fixture presentation")
        archive.writestr("meshes/WRIST1.stl", "fixture mesh")
        archive.writestr("alice_m1_urdf/alice_m1.urdf", "<robot/>")
    for name in (*PRACTICE_IMAGES, TELEOP_IMAGE):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"fixture image")
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
        number = {73: 38, 74: 37, 75: 39}.get(emitted_number, emitted_number - MODEL_OFFSET)
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
            content += (
                '<svg role="img" aria-label="검증 흐름" viewBox="0 0 10 10">'
                '<defs><marker id="arrow-28"></marker></defs>'
                '<path marker-end="url(#arrow-28)"></path></svg>'
            )
        for _, approved in MODEL_TEXT_EDITS.get(emitted_number, ()):
            content += f"<ol>{approved}</ol>" if approved.startswith("<li>") else f"<p>{approved}</p>"
        if emitted_number <= VLA_SLIDES:
            extra_class, content = vla_fixture(emitted_number)
        if emitted_number in MODEL_SOURCE_EDITS:
            pairs = MODEL_SOURCE_EDITS[emitted_number]
            content += pairs[0][0]
            if emitted_number == 53:
                content += '<ol class="model-steps">' + "".join(
                    f"<li><strong>{heading}</strong>{pair[0]}</li>"
                    for heading, pair in zip(SOURCE_HEADINGS, pairs[1:4])
                ) + '</ol>'
                content += pairs[4][0]
            elif emitted_number == 62:
                content += pairs[1][0]
        if emitted_number == 74:
            extra_class += " gripper-practice"
            content = (
                '실습 결과물 제출 DD_GRP_DATA.pptx 2p 73 mm 93.5 mm '
                'WRIST1 WRIST2 INPUT COUPLER OUTPUT URDF RViz meshes/ '
                f'<a href="{PRACTICE_ZIP}" download="크래쉬랩_urdf.zip">자료 받기</a>'
                + "".join(f'<img src="{name}" alt="원본 자료">' for name in PRACTICE_IMAGES)
            )
        elif emitted_number == 75:
            extra_class += " vr-practice"
            content = (
                '<h2>실습 2 · M1 텔레오퍼레이션</h2>'
                '<p>책상 위 물체를 집어 박스 안에 넣기</p>'
                '<ol class="model-steps"><li><strong>입력 확인</strong><p>담당자와 M1·VR 기준 자세·입력 방향·작업 공간을 확인한다.</p></li>'
                '<li><strong>물체 집기</strong><p>캔이나 그릇 하나에 저속 접근해 그리퍼를 닫고 들어 올린다.</p></li>'
                '<li><strong>박스에 놓고 확인</strong><p>박스 안쪽으로 낮추고 그리퍼를 열어 놓는다. 손을 뺀 뒤 물체가 박스 안에 남는지 확인하고 결과 영상을 기록한다.</p></li></ol>'
                f'<figure><img src="{TELEOP_IMAGE}" alt="M1 앞 물체와 박스">'
                '<figcaption>사용자 제공 시뮬레이션 화면</figcaption></figure>'
                '<div class="vr-practice-dataset" role="group"><h3>Data Studio 전처리 결과 · LeRobot v2.0 + GR00T</h3>'
                '<div><code>meta/ info.json · modality.json · episodes.jsonl · tasks.jsonl · stats.json ← GR00T가 학습 때 계산 '
                'data/chunk-000/episode_000000.parquet '
                'videos/chunk-000/observation.images.left_view/episode_000000.mp4</code></div>'
                '<p>info.json 버전·프레임·열, episodes/tasks.jsonl 회차·길이·태스크 문장, modality.json GR00T 상태·행동 구간.</p>'
                '<p>episode마다 한 쌍, 설정한 묶음(예: 100개)마다 chunk-001, 002로 이동. Data Studio를 쓰지 않으면 raw 데이터도 같은 규격으로 전처리한다.</p></div>'
                '<p class="vr-practice-note">실물 M1은 2인 1조로 동작 구역 밖에서 조작. '
                '비상정지 확인. 연결·추적 끊김 때 정지. 자동 정지를 가정하지 않는다.</p>'
                '<p>결과 영상</p>'
            )
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
        slides[emitted - 1].replace(f'id="slide-{emitted}"', f'id="slide-{original}"', 1)
        .replace(f'슬라이드 {emitted} / {total}:', f'슬라이드 {original} / 38:', 1)
        for original, emitted in MODEL_SLIDE_NUMBERS.items() if original != 37
    )
    baseline += '<section id="slide-37">실습 결과물 제출</section>'
    baseline += '<section id="slide-36">' + topics[36] + '</section>'
    for pairs in MODEL_TEXT_EDITS.values():
        for old, approved in pairs:
            baseline = baseline.replace(approved, old)
    for pairs in MODEL_SOURCE_EDITS.values():
        for old, approved in pairs:
            html = html.replace(old, approved)
    html_path = root / "lecture-4.html"
    baseline_path = root / "baseline.txt"
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
                'aria-label="슬라이드 10 / 75: 제목 10">',
                'aria-label="슬라이드 10 / 75: 제목 10"><p class="key-line">행동을 만든다</p>',
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
            "missing g explanation": valid.replace(ACTION_SPACE_G, "g"),
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
            "baseline mutation": "Robot model slide contains an unapproved change",
            "required term": "Missing required learning element in slides 54-63 URDF: mimic",
            "missing g explanation": "Action Space must explain g as the gripper open/close command value",
            "fixed origin value": "XML teaching value changed .//joint[@name='l_wrist2']/origin@xyz",
            "inertial mass value": "XML teaching value changed .//inertial/mass@value",
            "equality polynomial": "XML teaching value changed .//equality/joint@polycoef",
            "malformed XML fragment": "XML fragment is not well-formed on slide-57",
            "internal source label": "Internal source label must not appear",
            "sentence stage label": "Heading/stage label must use nominal phrasing",
        }
        for label, markup in {
            "visible wording": "<p>부품</p>",
            "ARIA wording": '<span aria-label="부품"></span>',
            "data-title wording": '<span data-title="부품"></span>',
            "encoded wording": "<p>&#48512;&#54408;</p>",
        }.items():
            mutations[label] = valid.replace("</main>", markup + "</main>", 1)
            expected_messages[label] = "Outdated course wording '부품': lecture-4.html"
        for name in ("lecture-1.html", "orientation.html", "DESIGN.md", "DESIGN-SVG.md", "VLA_THEORY.md"):
            path = root / name
            path.write_text("구성 요소", encoding="utf-8")
            if check(valid, html_path, baseline):
                failures.append(f"clean sibling course file was rejected: {name}")
            path.write_text("부품", encoding="utf-8")
            messages = check(valid, html_path, baseline)
            if f"Outdated course wording '부품': {name}" not in messages:
                failures.append(f"sibling course wording mutation was not detected: {name}")
            path.unlink()
        practice_mutations = {
            "missing download": (valid.replace(f'<a href="{PRACTICE_ZIP}" download="크래쉬랩_urdf.zip">자료 받기</a>', "자료 받기"),
                                 "Gripper practice requires the exact ZIP download"),
            "wrong download path": (valid.replace(PRACTICE_ZIP, "assets/data/other.zip"),
                                    "Gripper practice requires the exact ZIP download"),
            "missing download attribute": (valid.replace(' download="크래쉬랩_urdf.zip"', ""),
                                           "Gripper practice requires the exact ZIP download"),
            "wrong download filename": (valid.replace('download="크래쉬랩_urdf.zip"', 'download="other.zip"'),
                                        "Gripper practice requires the exact ZIP download"),
            "missing source image": (valid.replace(PRACTICE_IMAGES[0], "asset.svg"),
                                     "Gripper practice requires source image"),
            "missing gripper recipe": (valid.replace("2p 73 mm", "2p"),
                                       "Missing practice instruction on slide-74: 73 mm"),
            "missing VR safety": (valid.replace("비상정지", "비상"),
                                  "Missing practice instruction on slide-75: 비상정지"),
            "missing tracking stop": (valid.replace("연결·추적 끊김 때 정지", "연결·추적 끊김 때 계속"),
                                      "M1 practice safety requires connection and tracking loss stop"),
            "VR not last": (valid.replace("model-slide vr-practice", "model-slide")
                            .replace("model-slide gripper-practice", "model-slide gripper-practice vr-practice"),
                            "Practice placement requires vr-practice only on slide-75"),
        }
        for label, old, new, expected in (
            ("missing box objective", "박스 안쪽으로 낮추고 그리퍼를 열어 놓는다.",
             "박스 밖으로 물체를 옮겨 놓는다.", "M1 practice steps require place inside box"),
            ("missing object grasp", "그리퍼를 닫고 들어 올린다.", "팔을 움직인다.",
             "M1 practice steps require pick object"),
            ("release without lowering", "낮추고 그리퍼를 열어", "그리퍼를 열어",
             "M1 practice steps require lower before release"),
            ("release outside box", "박스 안쪽으로 낮추고", "박스 밖으로 낮추고",
             "M1 practice steps require lower before release"),
            ("release relation split across steps", "박스 안쪽으로 낮추고 그리퍼를 열어 놓는다.",
             "박스 안쪽으로 낮추고</p></li><li><p>그리퍼를 열어 놓는다.",
             "M1 practice steps require lower before release"),
            ("release relation only in heading", "박스 안쪽으로 낮추고 그리퍼를 열어 놓는다.",
             "</p><strong>박스 안쪽으로 낮추고 그리퍼를 열어 놓는다.</strong><p>박스 밖으로 놓는다.",
             "M1 practice steps require lower before release"),
            ("success relation split across steps", "손을 뺀 뒤 물체가 박스 안에 남는지", "손을 뺀 뒤</p></li><li><p>물체가 박스 안에 남는지",
             "M1 practice steps require check after hand withdrawal"),
            ("grasp relation split across steps", "그리퍼를 닫고 들어 올린다.",
             "그리퍼를 닫고</p></li><li><p>들어 올린다.",
             "M1 practice steps require pick object"),
            ("placement body removed", "박스 안쪽으로 낮추고 그리퍼를 열어 놓는다.",
             "물체를 옮긴다.", "M1 practice steps require place inside box"),
            ("success relation only in heading", "손을 뺀 뒤 물체가 박스 안에 남는지 확인하고 결과 영상을 기록한다.",
             "</p><strong>손을 뺀 뒤 물체가 박스 안에 남는지 확인한다.</strong><p>결과 기록",
             "M1 practice steps require check after hand withdrawal"),
            ("missing success check", "손을 뺀 뒤 물체가 박스 안에 남는지", "결과 기록",
             "M1 practice steps require check after hand withdrawal"),
            ("wrong teleop image", TELEOP_IMAGE, "asset.svg", "M1 practice requires supplied image on slide-75"),
            ("missing image alt", 'alt="M1 앞 물체와 박스"', 'alt="이미지"',
             "M1 practice image requires descriptive alt text"),
            ("missing simulation provenance", "사용자 제공 시뮬레이션 화면", "완료 화면",
             "M1 practice caption must identify the supplied simulation screen"),
            ("assumed automatic stop", "자동 정지를 가정하지 않는다", "자동 정지된다",
             "M1 practice safety requires no assumed automatic stop"),
            ("missing observer", "2인 1조", "혼자", "M1 practice safety requires two-person physical operation"),
            ("inside motion zone", "동작 구역 밖", "동작 구역 안", "M1 practice safety requires outside motion zone"),
            ("steps only in heading", '<ol class="model-steps">',
             '<ol>', "Missing M1 procedural instruction: 담당자"),
            ("safety only elsewhere", 'class="vr-practice-note"', 'class="model-caption"',
             "M1 practice safety requires emergency stop"),
        ):
            practice_mutations[label] = (valid.replace(old, new), expected)
        for label, old, new, expected in (
            ("missing dataset version", "LeRobot v2.0", "LeRobot", "Missing practice instruction on slide-75: LeRobot v2.0"),
            ("missing GR00T modality map", "modality.json", "modality file", "Missing practice instruction on slide-75: modality.json"),
            ("missing raw-data path", "Data Studio를 쓰지 않으면 raw 데이터도 같은 규격으로 전처리한다.", "Data Studio만 사용한다.", "Missing practice instruction on slide-75: raw 데이터"),
            ("missing camera video path", "observation.images.left_view", "observation.images", "Missing practice instruction on slide-75: observation.images.left_view"),
        ):
            practice_mutations[label] = (valid.replace(old, new), expected)
        teleop_img = f'<img src="{TELEOP_IMAGE}" alt="M1 앞 물체와 박스">'
        for label, markup in (
            ("missing teleop image", valid.replace(teleop_img, "")),
            ("image on wrong slide", valid.replace(teleop_img, "").replace(
                f'<a href="{PRACTICE_ZIP}"', teleop_img + f'<a href="{PRACTICE_ZIP}"')),
            ("image as link only", valid.replace(teleop_img, f'<a href="{TELEOP_IMAGE}">화면</a>')),
        ):
            practice_mutations[label] = (markup, "M1 practice requires supplied image on slide-75")
        for label, markup, message in (
            ("removed page 3 image", '<img src="assets/img/lecture4/gripper-data-slide-3.png">',
             "Gripper practice must not reference the removed PPTX page 3 image"),
            ("removed page 3 link", '<a href="assets/img/lecture4/gripper-data-slide-3.png">원본</a>',
             "Gripper practice must not reference the removed PPTX page 3 image"),
            ("removed page 3 caption", '<p>3p · 조립 방향</p>',
             "Gripper practice must not include removed PPTX page 3 instructions"),
            ("removed page 3 lead", '<p>PPTX 3페이지 조립 방향</p>',
             "Gripper practice must not include removed PPTX page 3 instructions"),
            ("removed page selector", '<input name="gripper-reference" type="radio">',
             "Gripper practice page 2 must be static without page selectors"),
        ):
            practice_mutations[label] = (
                valid.replace('제목 74">', '제목 74">' + markup, 1), message)
        for label, (mutated, message) in practice_mutations.items():
            mutations[label] = mutated
            expected_messages[label] = message
        other_page_reference = valid.replace('제목 1">', '제목 1"><p>PPTX 3페이지 참고</p>', 1)
        if check(other_page_reference, html_path, baseline):
            failures.append("page 3 wording outside slide-74 was incorrectly rejected")
        archive_path = root / PRACTICE_ZIP
        archive_bytes = archive_path.read_bytes()
        for label in ("missing", "corrupt", "manifest"):
            if label == "missing":
                archive_path.unlink()
            elif label == "corrupt":
                archive_path.write_bytes(b"not a ZIP")
            else:
                with zipfile.ZipFile(archive_path, "w") as archive:
                    archive.writestr("unrelated.txt", "not the practice materials")
            messages = check(valid, html_path, baseline)
            expected_zip_messages = (["Practice ZIP is missing or invalid"] if label != "manifest" else
                                     ["Practice ZIP is missing DD_GRP_DATA.pptx",
                                      "Practice ZIP is missing mesh files", "Practice ZIP is missing alice_m1.urdf"])
            if not all(any(expected in message for message in messages) for expected in expected_zip_messages):
                failures.append(f"{label} practice ZIP mutation was not detected")
            archive_path.write_bytes(archive_bytes)
        image_path = root / PRACTICE_IMAGES[0]
        image_bytes = image_path.read_bytes()
        image_path.unlink()
        if not any("Missing local asset" in message for message in check(valid, html_path, baseline)):
            failures.append("missing practice image file was not detected")
        image_path.write_bytes(image_bytes)
        teleop_path = root / TELEOP_IMAGE
        teleop_bytes = teleop_path.read_bytes()
        teleop_path.unlink()
        if not any("Missing local asset" in message and TELEOP_IMAGE in message
                   for message in check(valid, html_path, baseline)):
            failures.append("missing supplied teleoperation image file was not detected")
        teleop_path.write_bytes(teleop_bytes)
        missing_practice_baseline = baseline.replace('id="slide-37"', 'id="omitted-37"')
        if "Baseline must contain slide-37" not in check(valid, html_path, missing_practice_baseline):
            failures.append("missing original practice baseline was not detected")
        for number, pairs in MODEL_SOURCE_EDITS.items():
            old_image, crop = pairs[0]
            for label, changed in {
                "wrong crop viewport": crop.replace('viewBox="', 'viewBox="1 ', 1),
                "wrong crop clip": crop.replace('<rect x="', '<rect x="1', 1),
                "wrong crop source": crop.replace("gripper-data-slide-2.png", "gripper-data-slide-3.png"),
                "old CAD image": old_image,
                "wrong clip ID": crop.replace(f'model-source-{number}-clip', 'other-clip'),
            }.items():
                key = f"source crop {number} {label}"
                mutations[key] = valid.replace(crop, changed, 1)
                expected_messages[key] = f"Model source crop must match approved PPTX page-2 SVG: slide-{number}"
        old_path = re.search(r'src="([^"]+)"', MODEL_SOURCE_EDITS[53][0][0]).group(1)
        crop = MODEL_SOURCE_EDITS[53][0][1]
        appended_old_image = valid.replace(crop, crop + f'<img src="{old_path}" alt="different">', 1)
        mutations["appended old CAD image with different alt"] = appended_old_image
        expected_messages["appended old CAD image with different alt"] = (
            "Model source crop must match approved PPTX page-2 SVG: slide-53")
        if expected_messages["appended old CAD image with different alt"] not in check(
            appended_old_image, html_path
        ):
            failures.append("appended old CAD image escaped standalone source guard")
        for label, old, new in (
            ("source heading removed", '<li><strong>PPTX · 조립 관계와 치수</strong></li>', ""),
            ("source description restored", '<strong>PPTX · 조립 관계와 치수</strong>',
             '<strong>PPTX · 조립 관계와 치수</strong>' + MODEL_SOURCE_EDITS[53][1][0]),
        ):
            mutations[label] = valid.replace(old, new, 1)
            expected_messages[label] = "Slide-53 source list requires exactly three headings without descriptions"
        deletion_mutations = {
            "deleted schedule": (
                valid.replace(" 행동 정의 데이터 모델 실행 평가",
                              " 행동 정의 데이터 모델 실행 평가<h3>이번 학기 일정</h3>", 1),
                "Deleted semester schedule must not remain on slide-50",
            ),
            "deleted reference takeaway": (
                valid.replace(
                    '제목 51">',
                    '제목 51"><p>수치를 인용할 때 함께 확인할 출처와 조건</p>', 1),
                "Deleted reference takeaway must not remain on slide-51",
            ),
            "deleted revision section": (
                valid.replace("실습 결과물 제출", "로봇 모델 리비전 비교 " +
                              "USD 116.6007 URDF MJCF 117.4993 실습 결과물 제출", 1),
                "Deleted model revision comparison must not remain: slide-74",
            ),
            "extra slide": (
                valid.replace("</main>", '<section id="slide-76"></section></main>', 1),
                "Deck must contain exactly 75 slides",
            ),
            "tail slide ID": (
                valid.replace('id="slide-75"', 'id="slide-76"', 1),
                "Slides must be consecutively ordered",
            ),
            "tail ARIA count": (
                valid.replace("슬라이드 75 / 75:", "슬라이드 75 / 74:", 1),
                "Invalid slide aria-label: slide-75",
            ),
            "project checklist preservation": (
                valid.replace(" 행동 정의 데이터 모델 실행 평가", " 데이터 모델 실행 평가", 1),
                "Missing required learning element in slide 50 project checklist: 행동 정의",
            ),
            "practice preservation": (
                valid.replace("실습 결과물 제출", "결과물 제출", 1),
                "Missing practice instruction on slide-74: 실습",
            ),
            "recap preservation": (
                valid.replace("공식 문서 documentation 링크", "공식 문서 documentation 링크 변경", 1),
                "Robot model slide contains an unapproved change: slide-73",
            ),
        }
        for label, (mutated, message) in deletion_mutations.items():
            mutations[label] = mutated
            expected_messages[label] = message
        missing_baseline = baseline.replace('<section id="slide-36">', '<section id="omitted-36">', 1)
        if "Baseline must contain slide-36" not in check(valid, html_path, missing_baseline):
            failures.append("incomplete original baseline was not detected")
        guide_mutations = {
            11: {"tokenizer stage": ("문장 → 조각 · 번호", "문장 → Vector"),
                 "embedding stage": ("Embedding 번호 → Vector", "Embedding 번호 → 목록"),
                 "image token count": ("256개", "255개"),
                 "text token count": ("7개", "5개"),
                 "state token count": ("1개", "2개")},
            12: {term: (term.replace("VisionEncoder", "Vision Encoder"), "삭제")
                 for term in TERM_GUIDE_PATTERNS[12]},
            13: {**{f"example {value}": (value.replace("-", "−"), "9.99")
                    for value in ("0.5", "-0.2", "1.0", "0.48", "-0.10")},
                 "dimension 1152": ("1152", "1153"),
                 "dimension 2048": ("2048", "2049"),
                 "weight count": ("8,192", "8,193"),
                 "educational example label": ("교육용 예시", "실제 모델")},
            14: {"original action-expert name": ("Action Expert", "Action Head")},
            15: {"행동생성모듈": ("행동 생성 모듈", "행동 모듈"),
                 "ActionExpert": ("Action Expert", "액션 모듈"),
                 "DiffusionTransformer": ("Diffusion Transformer", "Diffusion 모듈")},
        }
        sections = slide_source(valid)
        for number, replacements in guide_mutations.items():
            section = sections[f"slide-{number}"]
            for label, (old, new) in replacements.items():
                key = f"guide {number} {label}"
                # Replace throughout this slide so generic fixture terms cannot mask deletion.
                mutations[key] = valid.replace(section, section.replace(old, new))
                expected_messages[key] = f"Missing term guide contract: slide-{number}: {label}"
        mutations["literal expert label"] = valid.replace("행동 생성 모듈", "행동 생성 모듈 · 행동 전문가", 1)
        expected_messages["literal expert label"] = "Outdated VLA term must use English spelling: 행동전문가"
        mutations["literal noise label"] = valid.replace("Noise(쉬운 역할 설명)", "잡음(쉬운 역할 설명)", 1)
        expected_messages["literal noise label"] = "Outdated VLA term must use English spelling: 잡음"
        mutations["short term explanation"] = valid.replace("Noise(쉬운 역할 설명)", "Noise", 1)
        expected_messages["short term explanation"] = "Missing short Korean explanation: slide-15: Noise"
        mutations["reasoning as inference"] = valid.replace("Reasoning(쉬운 역할 설명)", "Inference(쉬운 역할 설명)", 1)
        expected_messages["reasoning as inference"] = "Reasoning must not be labelled model inference: slide-46"
        mutations["transliterated policy"] = valid.replace("Policy(쉬운 역할 설명)", "폴리시(쉬운 역할 설명)", 1)
        expected_messages["transliterated policy"] = "Outdated VLA term must use English spelling: 폴리시"
        mutations["policy explanation omitted"] = valid.replace("Policy(쉬운 역할 설명)", "Policy", 1)
        expected_messages["policy explanation omitted"] = "Missing short Korean explanation: slide-4: Policy"
        mutations["transliterated noise"] = valid.replace("Noise(쉬운 역할 설명)", "노이즈(쉬운 역할 설명)", 1)
        expected_messages["transliterated noise"] = "Outdated VLA term must use English spelling: 노이즈"
        mutations["duplicate English expansion"] = valid.replace(" Token Vector", " Token(Token) Vector", 1)
        expected_messages["duplicate English expansion"] = "Repeated English term expansion must be removed"
        mutations["conflated tokenizer"] = valid.replace(
            "Tokenizer 문장 → 조각 · 번호", "Tokenizer 문장 → 조각 · 번호 단어 조각 → Vector", 1)
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
        # Every approved robot edit passes in the valid fixture, while extra prose
        # or a typo on the very same slide must still fail byte preservation.
        for number, pairs in MODEL_TEXT_EDITS.items():
            section = sections[f"slide-{number}"]
            for kind, changed in (
                ("extra", section.replace("</section>", " 추가 문구</section>")),
                ("wrong", section.replace(pairs[0][1], pairs[0][1] + "오타", 1)),
            ):
                label = f"model approved page {number} {kind}"
                mutations[label] = valid.replace(section, changed)
                expected_messages[label] = f"Robot model slide contains an unapproved change: slide-{number}"
        unchanged_model = valid
        for pairs in MODEL_TEXT_EDITS.values():
            for old, approved in pairs:
                if "부품" not in old:
                    unchanged_model = unchanged_model.replace(approved, old)
        if check(unchanged_model, html_path, baseline):
            failures.append("unchanged robot prose fixture was rejected")
        for number, label in ((20, "multimodal meaning"), (47, "value function role"), (15, "MoE expansion")):
            sample = TERM_ROLE_CONTRACTS[number][label][1]
            section = sections[f"slide-{number}"]
            key = f"term role {number} {label}"
            mutations[key] = valid.replace(section, section.replace(sample, "삭제"))
            expected_messages[key] = f"Missing term role explanation: slide-{number}: {label}"
        # Keep duplicate terms in other rows/SVG/notes so only the local
        # definition can satisfy the contract being removed.
        for label, (_, sample) in TERM_ROLE_CONTRACTS[12].items():
            section = sections["slide-12"]
            changed = section.replace(f"<td>{sample}</td>", "<td>설명 삭제</td>")
            changed = changed.replace("</section>", f"<p>{sample}</p></section>")
            key = f"row-local {label}"
            mutations[key] = valid.replace(section, changed)
            expected_messages[key] = f"Missing term role explanation: slide-12: {label}"
        for label, (_, sample) in TERM_ROLE_CONTRACTS[15].items():
            section = sections["slide-15"]
            changed = section.replace(f"<p>{sample}</p>", "<p>설명 삭제</p>")
            changed = changed.replace("</section>",
                f'<svg role="img" aria-label="중복 문구" viewBox="0 0 10 10"><text>{sample}</text></svg></section>')
            key = f"card-local {label}"
            mutations[key] = valid.replace(section, changed)
            expected_messages[key] = f"Missing term role explanation: slide-15: {label}"
        mutations["supervised definition omitted"] = valid.replace("지도학습(쉬운 역할 설명)", "지도학습", 1)
        expected_messages["supervised definition omitted"] = "Missing short Korean explanation: slide-9: 지도학습"
        for number, label, old, new, diagnostic in (
            (14, "controller", "제어기", "처리기", "Action Head diagram must distinguish"),
            (16, "training row", "로봇 없음", "온라인", "Action Head requires collection"),
            (31, "state code", "<code>observation.state</code>", "<code>action</code>", "Frame row requires exact LeRobot code: slide-31: 관절상태"),
            (31, "action code", "<code>action</code>", "<code>observation.state</code>", "Frame row requires exact LeRobot code: slide-31: 행동"),
            (31, "frame time", "1.24 s", "1.25 s", "Frame example must retain frame 62"),
            (37, "controller stage", "관절 제어기", "관절 처리기", "Inference diagram requires"),
            (48, "old output node", "Action Head", "행동 출력", "Action Head diagram node required"),
        ):
            section = sections[f"slide-{number}"]
            key = f"action pipeline {number} {label}"
            mutations[key] = valid.replace(section, section.replace(old, new))
            expected_messages[key] = diagnostic
        for number, label in ((16, "training"), (37, "output units")):
            sample = ACTION_PIPELINE_PROSE[number][label][1]
            section = sections[f"slide-{number}"]
            changed = section.replace(f"<p>{sample}</p>", "<p>설명 삭제</p>")
            changed = changed.replace("</section>",
                f'<svg role="img" aria-label="중복 문구" viewBox="0 0 10 10"><text>{sample}</text></svg></section>')
            key = f"pipeline prose separate from SVG {number}"
            mutations[key] = valid.replace(section, changed)
            expected_messages[key] = f"Action pipeline prose explanation required: slide-{number}: {label}"
        for number, contracts in NOISE_PROSE.items():
            section = sections[f"slide-{number}"]
            for label, (_, sample) in contracts.items():
                changed = section.replace(f"<p>{sample}</p>", "<p>설명 삭제</p>")
                changed = changed.replace("</section>", f'<svg role="img" aria-label="중복 설명" viewBox="0 0 10 10"><text>{sample}</text></svg></section>')
                key = f"noise body independent {number} {label}"
                mutations[key] = valid.replace(section, changed)
                expected_messages[key] = f"Noise prose contract missing: slide-{number}: {label}"
        for number, labels in NOISE_SVG_LABELS.items():
            section = sections[f"slide-{number}"]
            for label in labels:
                changed = section.replace(f"<text>{label}</text>", "<text>삭제</text>")
                changed = changed.replace("</section>", f'<p>{label}</p></section>')
                key = f"noise SVG independent {number} {label}"
                mutations[key] = valid.replace(section, changed)
                expected_messages[key] = f"Noise SVG contract missing: slide-{number}: {label}"
        section = sections["slide-15"]
        for label in NOISE_OUTPUT_LABELS:
            changed = section.replace(f'<p class="vla-module-output">{label}</p>', '<p class="vla-module-output">삭제</p>')
            changed = changed.replace("</section>", f'<svg role="img" aria-label="{label}" viewBox="0 0 10 10"><title>{label}</title><text>{label}</text></svg><p>{label}</p></section>')
            key = f"noise figure output independent {label}"
            mutations[key] = valid.replace(section, changed)
            expected_messages[key] = f"Noise module output contract missing: slide-15: {label}"
        section = sections["slide-21"]
        mutations["noise arithmetic"] = valid.replace(section, section.replace("² = 0.16", "² = 0.17"))
        expected_messages["noise arithmetic"] = "Noise example arithmetic invariant failed"
        mutations["noise mixing arithmetic"] = valid.replace(section, section.replace("= −0.20</p>", "= −0.30</p>"))
        expected_messages["noise mixing arithmetic"] = "Noise example arithmetic invariant failed"
        mutations["noise slope label"] = valid.replace(section, section.replace("<text>a − ε = 1.6</text>", "<text>a − ε = 1.7</text>"))
        expected_messages["noise slope label"] = "Noise example arithmetic invariant failed"
        flow = re.search(r'points="([^"]+)" data-flow-start="0.5"', section)
        moved = flow[1].split()
        moved[5] = moved[5].split(",")[0] + "," + f"{float(moved[5].split(',')[1]) + 1:.1f}"
        mutations["noise flow trajectory"] = valid.replace(section, section.replace(flow[1], " ".join(moved)))
        expected_messages["noise flow trajectory"] = "Noise execution flow must match the ideal mean slope: slide-21"
        mutations["noise flow one sign"] = valid.replace(section, section.replace('data-flow-start="-0.5"', 'data-flow-start="0.5"'))
        expected_messages["noise flow one sign"] = "Noise execution requires one flow from each Noise sign: slide-21"
        mutations["noise one-step line"] = valid.replace(section, section.replace('x2="710" y2="482"', 'x2="710" y2="377"'))
        expected_messages["noise one-step line"] = "Noise one-step line must end at the mean 0: slide-21"
        section = sections["slide-20"]
        curve = re.search(r'points="([^"]+)" data-loss-map', section)
        bent = curve[1].split()
        bent[10] = bent[10].split(",")[0] + "," + f"{float(bent[10].split(',')[1]) - 2:.1f}"
        mutations["mean loss curve"] = valid.replace(section, section.replace(curve[1], " ".join(bent)))
        expected_messages["mean loss curve"] = "Mean-action loss curve must match L(â) = â² + 1: slide-20"
        mutations["mean loss marker"] = valid.replace(section, section.replace('cy="520.0"', 'cy="510.0"'))
        expected_messages["mean loss marker"] = "Mean-action loss markers must sit on L(±1) = 2 and L(0) = 1: slide-20"
        mutations["mean loss label"] = valid.replace(section, section.replace("<text>정답 L = 2</text>", "<text>정답 L = 3</text>"))
        expected_messages["mean loss label"] = "Mean-action loss labels must equal L(±1) = 2 and L(0) = 1: slide-20"
        mutations["noise layout"] = valid.replace('class="model-columns"', 'class="other-layout"', 1)
        expected_messages["noise layout"] = "Noise example requires its scoped two-column diagram"
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
    if not failures:
        print(f"PASS: lecture 4 checker self-test ({len(mutations)} negative mutations, {len(practice_mutations)} practice mutations, 5 sibling-file wording mutations and practice asset mutations detected)")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "html",
        nargs="?",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "lecture-4.html",
    )
    parser.add_argument("--baseline", type=Path, help="Original 38-slide lecture-4 HTML (robot slides 15-38; slide 36 omitted, slide 37 replaced)")
    parser.add_argument("--self-test", action="store_true", help="Run isolated negative tests")
    args = parser.parse_args()

    if args.self_test:
        failures = self_test()
        if failures:
            print("\n".join(f"FAIL: self-test: {message}" for message in failures), file=sys.stderr)
            return 1
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
        print("PASS: robot slides 15-35 → 52-72 and 38 → 73 preserve bytes except section ID/ARIA numbers and exact approved prose/source edits; original slide 36 omitted; original slide 37 replaced by validated practice 74 and VR practice 75 added")
    return 0


def parsed_sections(html: str) -> dict[str, dict[str, str | None]]:
    """Small reporting helper kept separate from validation state."""
    parser = DeckParser()
    parser.feed(html)
    return parser.sections


if __name__ == "__main__":
    sys.exit(main())
