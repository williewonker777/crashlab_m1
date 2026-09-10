#!/usr/bin/env python3
"""Apply the shared deck template to native PPT HTML without rewriting content."""

import argparse
from html.entities import name2codepoint
from pathlib import Path
import re
import xml.etree.ElementTree as ET

PALETTE = {
    "#0B1F33": "var(--hy-blue)", "#14233B": "var(--ink)",
    "#1F78D1": "var(--hy-blue)", "#00A5A5": "var(--accent-ink)",
    "#F7F9FC": "var(--bg)", "#D5DEE8": "var(--line)",
    "#E7F1FB": "var(--bg-tint)", "#E6F7F7": "var(--accent-tint)",
    "#5B6770": "var(--hy-gray)", "#8A96A3": "var(--muted)",
    "#F59E0B": "var(--warn)", "#FFF3DA": "#FFF6E8",
    "#E8F4FF": "var(--bg-tint)", "#E2F2FF": "var(--bg-tint)",
    "#EFF5FF": "var(--bg-tint)", "#E1FAF7": "var(--accent-tint)",
    "#CFDDEC": "var(--line)", "#1E293B": "var(--hy-gray)",
    "#000000": "var(--ink)",
}


def style(element):
    return dict(item.split(":", 1) for item in element.get("style", "").split(";") if ":" in item)


def set_style(element, values):
    element.set("style", ";".join(f"{key}:{value}" for key, value in values.items()))


def percent(values, key):
    return float(values.get(key, "0%").rstrip("%"))


def text(element):
    return "".join(element.itertext()).strip()


def recolor(element):
    for node in element.iter():
        for key in ("style", "fill", "stroke"):
            value = node.get(key)
            if value:
                for original, replacement in PALETTE.items():
                    value = value.replace(original, replacement)
                node.set(key, value)


def text_block(element, tag, class_name):
    """Move the original paragraphs and runs into a semantic template element."""
    result = ET.Element(tag, {"class": class_name})
    paragraphs = element.findall(".//div[@class='ppt-paragraph']")
    for index, paragraph in enumerate(paragraphs):
        if index:
            ET.SubElement(result, "br")
        for child in list(paragraph):
            for run in child.iter():
                values = style(run)
                for key in ("font-size", "font-family", "color"):
                    values.pop(key, None)
                set_style(run, values)
            result.append(child)
    return result


def shared_slide(source):
    # The converter emits HTML void elements and named entities, not XML.
    source = re.sub(r"<(img|br)\b([^>]*?)(?<!/)>", r"<\1\2/>", source)
    source = re.sub(r"&([a-zA-Z]+);", lambda m: f"&#{name2codepoint[m[1]]};", source)
    slide = ET.fromstring(source)
    if slide.get("data-template") == "shared":
        return ET.tostring(slide, encoding="unicode", method="html")
    canvas = slide.find("div")
    elements = list(canvas)
    title_shapes = [el for el in elements if text(el) and any(
        float(style(span).get("font-size", "0cqw").removesuffix("cqw")) >= 1.6
        for span in el.iter("span")
    ) and percent(style(el), "top") < 65]
    title = title_shapes[0]
    cover = percent(style(title), "top") > 30
    slide.set("class", "slide ppt-slide" + (" slide--title layout-title" if cover else " layout-native"))
    if not cover and (len(text(slide)) > 520 or slide.get("id") == "slide-27"):
        slide.set("class", slide.get("class") + " ppt-slide--dense")
    slide.set("data-template", "shared")
    slide.set("data-title", text(title))
    slide.remove(canvas)
    inner = ET.SubElement(slide, "div", {"class": "slide__inner"})

    if cover:
        content = ET.SubElement(inner, "div", {"class": "ppt-cover"})
        content.append(text_block(title, "h1", "ppt-cover__title"))
        footer = ET.Element("footer", {"class": "ppt-footer"})
        for el in elements:
            if el is not title and text(el):
                if percent(style(el), "top") > 90:
                    footer.append(text_block(el, "span", "ppt-footer__item"))
                else:
                    content.append(text_block(el, "p", "title-meta"))
        inner.append(footer)
        return ET.tostring(slide, encoding="unicode", method="html")

    header = ET.SubElement(inner, "header", {"class": "slide__header"})
    body = ET.Element("div", {"class": "ppt-canvas"})
    footer = ET.Element("footer", {"class": "ppt-footer"})
    for el in elements:
        values = style(el)
        x, y, w, h = (percent(values, key) for key in ("left", "top", "width", "height"))
        if el is title:
            header.append(text_block(el, "h2", "ppt-heading"))
            continue
        if text(el) and y < 9:
            header.insert(0, text_block(el, "p", "slide__eyebrow"))
            continue
        if text(el) and y >= 93:
            footer.append(text_block(el, "span", "ppt-footer__item"))
            continue
        if text(el) and y < 24 and w > 55:
            header.append(text_block(el, "p", "ppt-subtitle"))
            continue
        # Discard only the empty full-slide backdrop and decorative edge strips.
        if not text(el) and el.tag != "figure" and (h > 95 or w < 2 and y == 0 or y > 100):
            continue
        # Give the CLI screenshots and their annotations separate text columns.
        name = el.get("data-name", "")
        if name in {"Google Shape;771;p29", "Google Shape;775;p29", "Google Shape;779;p29", "Google Shape;783;p29"}:
            w = 25
        if name == "Google Shape;790;p29":
            h = 2.5
        if name == "Google Shape;793;p29":
            y, h = 75.5, 3
        if name in {"Google Shape;789;p29", "Google Shape;790;p29", "Google Shape;792;p29", "Google Shape;793;p29"}:
            x, w = 79, 21
        image_ratio = w / h * 1.77719 if el.tag == "figure" else None
        if el.tag == "figure" and slide.get("id") == "slide-27" and y > 50:
            x, w = 49, 28
        if name == "Google Shape;168;p9":
            x, w = 79.9, 2.2
        # The package-structure slide has unused space to the right of its cards.
        if slide.get("id") == "slide-41":
            if x >= 32:
                x, w = 32 + (x - 32) * 1.14, w * 1.14
            elif y >= 80 and w > 70:
                w += 7.5
        # Grid rows grow with larger text instead of clipping fixed PPT boxes.
        column = max(1, round((x - 4) * 4) + 1)
        end_column = max(column + 1, round((x + w - 4) * 4) + 1)
        row = max(1, round((y - 24) * 2) + 1)
        end_row = max(row + 1, round((y + h - 24) * 2) + 1)
        for key in ("left", "top", "width", "height"):
            values.pop(key, None)
        values.update({"grid-column": f"{column}/{end_column}", "grid-row": f"{row}/{end_row}"})
        if image_ratio:
            values["aspect-ratio"] = f"{image_ratio:.5f}"
        if not text(el) and el.tag == "div" and values.get("background") == "#FFFFFF" and w > 25 and h > 20:
            values["background"] = "var(--accent-tint)" if x > 45 else "var(--bg-tint)"
            values["border"] = "0"
            values["border-radius"] = "24px"
        set_style(el, values)
        recolor(el)
        if text(el):
            code = any("Consolas" in span.get("style", "") or "Courier" in span.get("style", "")
                       for span in el.iter("span"))
            sizes = [float(style(span).get("font-size", "0cqw").removesuffix("cqw")) for span in el.iter("span")]
            size = max(sizes, default=0)
            role = "code" if code else "label" if size < 0.8 and len(text(el)) < 50 else "detail" if size < 0.95 else "body"
            el.set("class", el.get("class", "") + f" ppt-type-{role}")
            if text(el) in {"→", "←"}:
                el.set("class", el.get("class") + " ppt-arrow")
            elif w < 8 and len(text(el)) < 12:
                el.set("class", el.get("class") + " ppt-short-label")
            for node in el.iter():
                values = style(node)
                values.pop("font-size", None)
                values.pop("font-family", None)
                if "text-indent" in values:
                    values["padding-left"] = "0.8em"
                set_style(node, values)
        if el.tag == "svg":
            # SVG's intrinsic aspect ratio must not set the grid row heights.
            wrapper = ET.SubElement(body, "div", {"class": "ppt-connection", "style": el.get("style", "")})
            el.attrib.pop("style", None)
            wrapper.append(el)
        else:
            body.append(el)
    viewport = ET.SubElement(inner, "div", {"class": "ppt-viewport", "tabindex": "0", "role": "region", "aria-label": text(title)})
    viewport.append(body)
    inner.append(footer)
    return ET.tostring(slide, encoding="unicode", method="html")


def apply_template(document):
    document = re.sub(r"<section\b.*?</section>\n?", lambda match: shared_slide(match[0]) + "\n", document, flags=re.S)
    return document.replace("lecture-1-ppt.css?v=3", "lecture-1-ppt.css?v=4").replace("deck.js?v=3", "deck.js?v=4")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("html", type=Path)
    args = parser.parse_args()
    args.html.write_text(apply_template(args.html.read_text(encoding="utf-8")), encoding="utf-8")
