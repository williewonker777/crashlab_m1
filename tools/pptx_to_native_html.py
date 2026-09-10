#!/usr/bin/env python3
"""Convert this course's PPTX into a dependency-free, native HTML slide deck.

The converter deliberately keeps text as HTML and geometry as CSS/SVG. Pictures
are extracted as assets; slides are never flattened to screenshots.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import math
import posixpath
import re
import shutil
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path


NS = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "pr": "http://schemas.openxmlformats.org/package/2006/relationships",
}
R_EMBED = f"{{{NS['r']}}}embed"
R_ID = f"{{{NS['r']}}}id"


def qname(tag: str) -> str:
    prefix, local = tag.split(":", 1)
    return f"{{{NS[prefix]}}}{local}"


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def pct(value: int | float, total: int | float) -> str:
    return f"{100 * float(value) / float(total):.5f}%"


def parse_rels(zf: zipfile.ZipFile, path: str) -> dict[str, str]:
    root = ET.fromstring(zf.read(path))
    return {rel.get("Id", ""): rel.get("Target", "") for rel in root.findall("pr:Relationship", NS)}


def color_from(node: ET.Element | None, scheme: dict[str, str], default: str = "transparent") -> str:
    if node is None:
        return default
    color = None
    child = next(iter(node), None)
    if child is None:
        return default
    kind = child.tag.rsplit("}", 1)[-1]
    val = child.get("val", "")
    if kind == "srgbClr":
        color = f"#{val}"
    elif kind == "schemeClr":
        color = scheme.get(val, default)
    elif kind == "sysClr":
        color = f"#{child.get('lastClr', '000000')}"
    elif kind == "prstClr":
        basic = {"white": "#fff", "black": "#000", "red": "#f00", "blue": "#00f", "gray": "#808080"}
        color = basic.get(val, default)
    if not color or not color.startswith("#"):
        return color or default
    raw = color.lstrip("#")
    if len(raw) == 3:
        raw = "".join(c * 2 for c in raw)
    try:
        rgb = [int(raw[i:i + 2], 16) for i in (0, 2, 4)]
    except ValueError:
        return color
    lum_mod = 100000
    lum_off = 0
    alpha = 100000
    for transform in child:
        name = transform.tag.rsplit("}", 1)[-1]
        if name == "lumMod": lum_mod = int(transform.get("val", "100000"))
        elif name == "lumOff": lum_off = int(transform.get("val", "0"))
        elif name == "tint":
            amount = int(transform.get("val", "0")) / 100000
            rgb = [round(v + (255 - v) * amount) for v in rgb]
        elif name == "shade":
            amount = int(transform.get("val", "100000")) / 100000
            rgb = [round(v * amount) for v in rgb]
        elif name == "alpha": alpha = int(transform.get("val", "100000"))
    rgb = [max(0, min(255, round(v * lum_mod / 100000 + 255 * lum_off / 100000))) for v in rgb]
    if alpha < 100000:
        return f"rgba({rgb[0]},{rgb[1]},{rgb[2]},{alpha / 100000:.3f})"
    return "#" + "".join(f"{v:02X}" for v in rgb)


def load_scheme(zf: zipfile.ZipFile) -> dict[str, str]:
    root = ET.fromstring(zf.read("ppt/theme/theme1.xml"))
    scheme: dict[str, str] = {}
    clr_scheme = root.find(".//a:clrScheme", NS)
    if clr_scheme is not None:
        for item in clr_scheme:
            child = next(iter(item), None)
            if child is not None:
                value = child.get("lastClr") or child.get("val")
                if value:
                    scheme[item.tag.rsplit("}", 1)[-1]] = f"#{value}"
    scheme.update({"tx1": scheme.get("dk1", "#000000"), "tx2": scheme.get("dk2", "#333333"),
                   "bg1": scheme.get("lt1", "#FFFFFF"), "bg2": scheme.get("lt2", "#F4F4F4")})
    return scheme


def xfrm(node: ET.Element, cx: int, cy: int) -> tuple[str, float, float, float, float]:
    xf = node.find(".//a:xfrm", NS)
    if xf is None:
        return "", 0, 0, 0, 0
    off, ext = xf.find("a:off", NS), xf.find("a:ext", NS)
    if off is None or ext is None:
        return "", 0, 0, 0, 0
    x, y = int(off.get("x", "0")), int(off.get("y", "0"))
    w, h = int(ext.get("cx", "0")), int(ext.get("cy", "0"))
    styles = [f"left:{pct(x,cx)}", f"top:{pct(y,cy)}", f"width:{pct(w,cx)}", f"height:{pct(h,cy)}"]
    transforms = []
    rotation = int(xf.get("rot", "0")) / 60000
    if rotation: transforms.append(f"rotate({rotation:.3f}deg)")
    if xf.get("flipH") == "1": transforms.append("scaleX(-1)")
    if xf.get("flipV") == "1": transforms.append("scaleY(-1)")
    if transforms: styles.append("transform:" + " ".join(transforms))
    return ";".join(styles), x, y, w, h


def shape_geometry(sp: ET.Element) -> tuple[str, str]:
    prst = sp.find("p:spPr/a:prstGeom", NS)
    kind = prst.get("prst", "rect") if prst is not None else "rect"
    radius = "0"
    clip = "none"
    if kind in {"roundRect", "round1Rect", "round2SameRect", "round2DiagRect"}: radius = "12px"
    elif kind in {"ellipse", "pie", "wedgeEllipseCallout"}: radius = "50%"
    elif kind in {"triangle", "rtTriangle"}: clip = "polygon(50% 0,100% 100%,0 100%)"
    elif kind in {"diamond"}: clip = "polygon(50% 0,100% 50%,50% 100%,0 50%)"
    elif kind in {"chevron"}: clip = "polygon(0 0,75% 0,100% 50%,75% 100%,0 100%,25% 50%)"
    elif kind in {"pentagon"}: clip = "polygon(50% 0,100% 38%,82% 100%,18% 100%,0 38%)"
    elif kind in {"hexagon"}: clip = "polygon(25% 0,75% 0,100% 50%,75% 100%,25% 100%,0 50%)"
    return radius, clip


def text_html(sp: ET.Element, scheme: dict[str, str], slide_w: int, slide_h: int) -> str:
    tx = sp.find("p:txBody", NS)
    if tx is None:
        return ""
    body_pr = tx.find("a:bodyPr", NS)
    valign = (body_pr.get("anchor", "t") if body_pr is not None else "t")
    justify = {"t": "flex-start", "ctr": "center", "b": "flex-end"}.get(valign, "flex-start")
    inset = []
    for key, css in (("tIns", "padding-top"), ("rIns", "padding-right"), ("bIns", "padding-bottom"), ("lIns", "padding-left")):
        if body_pr is not None and body_pr.get(key): inset.append(f"{css}:{pct(int(body_pr.get(key)), slide_h)}")
    paragraphs = []
    for p in tx.findall("a:p", NS):
        ppr = p.find("a:pPr", NS)
        align = (ppr.get("algn", "l") if ppr is not None else "l")
        align = {"l": "left", "ctr": "center", "r": "right", "just": "justify"}.get(align, "left")
        margin = []
        if ppr is not None:
            if ppr.get("marL"): margin.append(f"padding-left:{pct(int(ppr.get('marL')), 12191675)}")
            if ppr.get("indent") and int(ppr.get("indent")) < 0: margin.append("text-indent:-0.7em")
        runs = []
        nodes = list(p)
        for run in nodes:
            local = run.tag.rsplit("}", 1)[-1]
            if local not in {"r", "fld", "br"}: continue
            if local == "br":
                runs.append("<br>")
                continue
            text = run.find("a:t", NS)
            if text is None: continue
            rpr = run.find("a:rPr", NS)
            if rpr is None: rpr = run.find("a:endParaRPr", NS)
            styles = []
            if rpr is not None:
                if rpr.get("sz"):
                    # CSS pt does not scale with the responsive slide canvas. cqw does.
                    point_size = int(rpr.get("sz")) / 100
                    css_px = point_size * 96 / 72
                    styles.append(f"font-size:{100 * css_px / 1920:.5f}cqw")
                if rpr.get("b") == "1": styles.append("font-weight:700")
                if rpr.get("i") == "1": styles.append("font-style:italic")
                if rpr.get("u") not in (None, "none"): styles.append("text-decoration:underline")
                fill = rpr.find("a:solidFill", NS)
                if fill is not None: styles.append(f"color:{color_from(fill, scheme, '#222')}")
                highlight = rpr.find("a:highlight", NS)
                if highlight is not None:
                    styles.append(f"background-color:{color_from(highlight, scheme, '#FFFF00')}")
                latin = rpr.find("a:latin", NS)
                ea = rpr.find("a:ea", NS)
                face = (ea.get("typeface") if ea is not None else None) or (latin.get("typeface") if latin is not None else None)
                if face and not face.startswith("+"): styles.append(f"font-family:{esc(face)},sans-serif")
                if rpr.get("baseline"): styles.append(f"vertical-align:{int(rpr.get('baseline')) / 1000:.1f}%")
            runs.append(f'<span style="{";".join(styles)}">{esc(text.text or "")}</span>')
        if not runs:
            continue
        bullet = ""
        if ppr is not None and ppr.find("a:buChar", NS) is not None:
            bullet = esc(ppr.find("a:buChar", NS).get("char", "•")) + "&nbsp;"
        pstyle = f"text-align:{align};" + ";".join(margin)
        paragraphs.append(f'<div class="ppt-paragraph" style="{pstyle}">{bullet}{"".join(runs)}</div>')
    return f'<div class="ppt-text" style="justify-content:{justify};{";".join(inset)}">{"".join(paragraphs)}</div>'


def shape_html(sp: ET.Element, scheme: dict[str, str], cx: int, cy: int) -> str:
    style, *_ = xfrm(sp, cx, cy)
    sppr = sp.find("p:spPr", NS)
    fill = color_from(sppr.find("a:solidFill", NS) if sppr is not None else None, scheme)
    if sppr is not None and sppr.find("a:noFill", NS) is not None: fill = "transparent"
    line = sppr.find("a:ln", NS) if sppr is not None else None
    stroke = color_from(line.find("a:solidFill", NS) if line is not None else None, scheme, "transparent")
    stroke_w = max(0.5, int(line.get("w", "0")) / 12700) if line is not None else 0
    radius, clip = shape_geometry(sp)
    extra = f"background:{fill};border:{stroke_w:.2f}px solid {stroke};border-radius:{radius};clip-path:{clip}"
    name_el = sp.find("p:nvSpPr/p:cNvPr", NS)
    name = name_el.get("name", "shape") if name_el is not None else "shape"
    text = text_html(sp, scheme, cx, cy)
    text_only = fill == "transparent" and stroke == "transparent"
    classes = "ppt-shape ppt-shape--text" if text_only else "ppt-shape"
    return f'<div class="{classes}" data-name="{esc(name)}" style="{style};{extra}">{text}</div>'


def connector_html(sp: ET.Element, scheme: dict[str, str], cx: int, cy: int) -> str:
    style, _x, _y, _w, _h = xfrm(sp, cx, cy)
    sppr = sp.find("p:spPr", NS)
    line = sppr.find("a:ln", NS) if sppr is not None else None
    stroke = color_from(line.find("a:solidFill", NS) if line is not None else None, scheme, "#555")
    width = max(1, int(line.get("w", "12700")) / 12700) if line is not None else 1
    dash = line.find("a:prstDash", NS).get("val", "solid") if line is not None and line.find("a:prstDash", NS) is not None else "solid"
    head = line.find("a:headEnd", NS).get("type", "none") if line is not None and line.find("a:headEnd", NS) is not None else "none"
    tail = line.find("a:tailEnd", NS).get("type", "none") if line is not None and line.find("a:tailEnd", NS) is not None else "none"
    dash_attr = ' stroke-dasharray="8 6"' if dash != "solid" else ""
    ends = []
    if head == "oval": ends.append(f'<circle cx="0" cy="0" r="2.2" fill="{esc(stroke)}" vector-effect="non-scaling-stroke"/>')
    if tail == "oval": ends.append(f'<circle cx="100" cy="100" r="2.2" fill="{esc(stroke)}" vector-effect="non-scaling-stroke"/>')
    return f'<svg class="ppt-connector" style="{style}" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true"><line x1="0" y1="0" x2="100" y2="100" stroke="{esc(stroke)}" stroke-width="{width}" vector-effect="non-scaling-stroke"{dash_attr}/>{"".join(ends)}</svg>'


def picture_html(pic: ET.Element, rels: dict[str, str], cx: int, cy: int, slide_no: int,
                 zf: zipfile.ZipFile, asset_dir: Path) -> str:
    style, *_ = xfrm(pic, cx, cy)
    blip = pic.find(".//a:blip", NS)
    if blip is None or not blip.get(R_EMBED): return ""
    target = rels.get(blip.get(R_EMBED), "")
    member = posixpath.normpath(posixpath.join(f"ppt/slides", target))
    if member.startswith("ppt/slides/"): member = member.replace("ppt/slides/../", "ppt/", 1)
    suffix = Path(member).suffix.lower() or ".bin"
    output_name = f"slide-{slide_no:02d}-{Path(member).stem}{suffix}"
    output = asset_dir / output_name
    image_bytes = zf.read(member)
    output.write_bytes(image_bytes)
    revision = hashlib.sha256(image_bytes).hexdigest()[:10]
    src_rect = pic.find("p:blipFill/a:srcRect", NS)
    image_style = "inset:0;width:100%;height:100%;object-fit:fill"
    if src_rect is not None:
        left = int(src_rect.get("l", "0")) / 1000
        top = int(src_rect.get("t", "0")) / 1000
        right = int(src_rect.get("r", "0")) / 1000
        bottom = int(src_rect.get("b", "0")) / 1000
        visible_w = max(0.01, 100 - left - right)
        visible_h = max(0.01, 100 - top - bottom)
        image_style = (f"left:{-left / visible_w * 100:.5f}%;top:{-top / visible_h * 100:.5f}%;"
                       f"width:{10000 / visible_w:.5f}%;height:{10000 / visible_h:.5f}%;object-fit:fill")
    return f'<figure class="ppt-picture" style="{style}"><img src="assets/img/lecture-1/{esc(output_name)}?v={revision}" alt="" style="{image_style}"></figure>'


def slide_title(slide: ET.Element, number: int) -> str:
    candidates = []
    for sp in slide.findall(".//p:spTree/p:sp", NS):
        text = " ".join((t.text or "") for t in sp.findall(".//a:t", NS)).strip()
        if not text or text in {str(number), f"{number:02d}", "ROS2 로봇 프로그래밍 기초"}: continue
        xf = sp.find(".//a:xfrm", NS)
        off = xf.find("a:off", NS) if xf is not None else None
        y = int(off.get("y", "99999999")) if off is not None else 99999999
        sizes = [int(node.get("sz", "0")) for node in sp.findall(".//a:rPr", NS)]
        largest = max(sizes, default=0)
        candidates.append((-largest, y, -len(text), text))
    candidates.sort()
    return candidates[0][3] if candidates else f"슬라이드 {number}"


def deck_chrome(count: int) -> str:
    return f'''<a class="skip-link" href="#slide-1">첫 슬라이드로</a>
<div class="deck-progress" aria-hidden="true"><span class="deck-progress__bar" data-progress></span></div>
<a class="deck-wordmark" href="index.html">크래쉬랩 M1</a>
<nav class="lecture-nav" aria-label="강의 이동"><a href="orientation.html">OT</a><a href="lecture-1.html" aria-current="page">01</a><a href="lecture-2.html">02</a><a href="lecture-3.html">03</a><a href="lecture-4.html">04</a></nav>
<div class="deck-tools"><button class="deck-tool" type="button" data-help-open aria-label="단축키 도움말">?</button><button class="deck-tool" type="button" data-fullscreen aria-label="전체화면" aria-pressed="false">F</button></div>
<div class="deck-counter" data-counter aria-live="polite">1 / {count}</div>
<dialog class="shortcut-help" id="shortcut-help" aria-labelledby="shortcut-title"><div class="shortcut-help__inner"><h2 id="shortcut-title">슬라이드 단축키</h2><dl><dt>→ ↓ Space PageDown</dt><dd>다음 슬라이드</dd><dt>← ↑ PageUp</dt><dd>이전 슬라이드</dd><dt>Home / End</dt><dd>처음 / 마지막</dd><dt>F</dt><dd>전체화면 전환</dd><dt>?</dt><dd>도움말 열기 / 닫기</dd></dl><button class="shortcut-help__close" type="button" data-help-close>닫기</button></div></dialog>'''


def convert(source: Path, repo: Path) -> None:
    asset_dir = repo / "assets/img/lecture-1"
    if asset_dir.exists(): shutil.rmtree(asset_dir)
    asset_dir.mkdir(parents=True)
    with zipfile.ZipFile(source) as zf:
        presentation = ET.fromstring(zf.read("ppt/presentation.xml"))
        size = presentation.find("p:sldSz", NS)
        cx, cy = int(size.get("cx")), int(size.get("cy"))
        scheme = load_scheme(zf)
        presentation_rels = parse_rels(zf, "ppt/_rels/presentation.xml.rels")
        slide_names = []
        for slide_id in presentation.findall("p:sldIdLst/p:sldId", NS):
            target = presentation_rels.get(slide_id.get(R_ID), "")
            member = posixpath.normpath(posixpath.join("ppt", target))
            if member in zf.namelist():
                slide_names.append(member)
        slides = []
        for number, member in enumerate(slide_names, 1):
            root = ET.fromstring(zf.read(member))
            source_name = Path(member).name
            rel_path = f"ppt/slides/_rels/{source_name}.rels"
            rels = parse_rels(zf, rel_path)
            title = slide_title(root, number)
            elements = []
            tree = root.find(".//p:spTree", NS)
            for child in list(tree)[2:]:
                local = child.tag.rsplit("}", 1)[-1]
                if local == "sp": elements.append(shape_html(child, scheme, cx, cy))
                elif local == "cxnSp": elements.append(connector_html(child, scheme, cx, cy))
                elif local == "pic": elements.append(picture_html(child, rels, cx, cy, number, zf, asset_dir))
            slides.append(f'<section class="slide ppt-slide" id="slide-{number}" aria-label="슬라이드 {number} / {len(slide_names)}: {esc(title)}"><div class="ppt-canvas">{"".join(elements)}</div></section>')
    document = f'''<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="description" content="ROS2 로봇 프로그래밍 기초"><title>ROS2 로봇 프로그래밍 기초 | 크래쉬랩 M1</title><link rel="icon" href="data:"><link rel="stylesheet" href="assets/css/deck.css?v=5"><link rel="stylesheet" href="assets/css/lecture-1-ppt.css?v=3"><script src="assets/js/deck.js?v=3" defer></script></head>
<body class="deck-page lecture-1">{deck_chrome(len(slides))}<main class="deck" data-deck data-slide-count="{len(slides)}" data-prev-deck="orientation.html#slide-last" data-next-deck="lecture-2.html">{"".join(slides)}</main></body></html>'''
    (repo / "lecture-1.html").write_text(document, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("pptx", type=Path)
    parser.add_argument("repo", type=Path)
    args = parser.parse_args()
    convert(args.pptx.resolve(), args.repo.resolve())


if __name__ == "__main__":
    main()
