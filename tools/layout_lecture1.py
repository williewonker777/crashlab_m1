"""Reflow selected slides while retaining the imported text, images and arrows."""

import xml.etree.ElementTree as ET


def styles(element):
    return dict(item.split(":", 1) for item in element.get("style", "").split(";") if ":" in item)


def set_styles(element, values):
    element.set("style", ";".join(f"{key}:{value}" for key, value in values.items()))


def group(class_name, *children):
    element = ET.Element("div", {"class": class_name})
    element.extend(children)
    return element


def reflow_slide(slide):
    number = int(slide.get("id", "slide-0").removeprefix("slide-"))
    if number not in {19, 27, 37, 41, 44, 53, 54, 55, 57} or slide.get("data-reflow"):
        return
    canvas = slide.find(".//div[@class='ppt-canvas']")
    elements = list(canvas)
    shapes = {int(el.get("data-name").split(";")[1]): el for el in elements if el.get("data-name")}
    pictures = [el for el in elements if el.tag == "figure"]
    connections = [el for el in elements if el.get("class") == "ppt-connection"]
    used = set()

    def take(element):
        if element in used:
            raise ValueError(f"Repeated element on slide {number}: {element.attrib}")
        used.add(element)
        return element

    def block(index, role="", join_lines=False):
        element = take(shapes[index])
        classes = [c for c in element.get("class", "").split() if c != "ppt-short-label"]
        element.set("class", " ".join(classes + ["ppt-block", role]))
        element.attrib.pop("style", None)
        for node in element.iter():
            if "ppt-text" in node.get("class", "").split():
                node.attrib.pop("style", None)
                if join_lines:
                    node.set("class", node.get("class") + " ppt-prose-lines")
        return element

    def heading(index):
        return block(index, "ppt-block--heading")

    def code(index):
        return block(index, "ppt-block--code")

    def card(title, *indices, class_name=""):
        return group("ppt-card " + class_name, heading(title), *(block(i) for i in indices))

    def picture(index):
        element = take(pictures[index])
        values = styles(element)
        set_styles(element, {"aspect-ratio": values["aspect-ratio"]})
        return element

    def diagram(indices, class_name):
        nodes = [take(shapes[i]) for i in indices] + [take(el) for el in connections]
        coordinates = [(el, *(list(map(int, styles(el)[key].split("/"))) for key in ("grid-column", "grid-row"))) for el in nodes]
        left, top = min(c[0] for _, c, r in coordinates), min(r[0] for _, c, r in coordinates)
        right, bottom = max(c[1] for _, c, r in coordinates), max(r[1] for _, c, r in coordinates)
        result = group("ppt-diagram " + class_name, *nodes)
        set_styles(result, {"--diagram-columns": right-left, "--diagram-rows": bottom-top})
        for el, columns, rows in coordinates:
            values = styles(el)
            values["grid-column"] = f"{columns[0]-left+1}/{columns[1]-left+1}"
            values["grid-row"] = f"{rows[0]-top+1}/{rows[1]-top+1}"
            set_styles(el, values)
            for node in el.iter():
                if node.get("class") == "ppt-text":
                    node.set("style", "justify-content:center;text-align:center")
        return result

    def flow(indices):
        nodes = []
        for index, shape in enumerate(indices):
            colors = {k: v for k, v in styles(shapes[shape]).items() if k in {"background", "border"}}
            element = block(shape, "ppt-flow__node")
            set_styles(element, colors)
            nodes.append(element)
            if index < len(connections):
                connection = take(connections[index])
                connection.attrib.pop("style", None)
                nodes.append(connection)
        return group("ppt-flow", *nodes)

    if number == 19:
        for index, rows in {526: "8/15", 528: "21/28", 530: "32/39", 532: "44/51"}.items():
            values = styles(shapes[index])
            values.update({"grid-column": "215/301", "grid-row": rows})
            set_styles(shapes[index], values)
        content = group("ppt-layout-action",
            group("ppt-card ppt-action-features", heading(515), *(block(i, join_lines=True) for i in range(516, 521))),
            group("ppt-stack", diagram([521, 522, 523, 524, 526, 528, 530, 532], "ppt-diagram--action"),
                  block(533, join_lines=True), code(535)))
    elif number == 27:
        content = group("ppt-stack ppt-layout-cli",
            group("ppt-card ppt-cli-row", heading(770), code(771), picture(1)),
            group("ppt-card ppt-cli-row", heading(774), code(775), picture(2)),
            group("ppt-cli-bottom",
                  group("ppt-stack", group("ppt-card", heading(778), code(779)), group("ppt-card", heading(782), code(783))),
                  picture(0), group("ppt-card ppt-cli-notes", *(block(i) for i in [789, 790, 793, 792]))))
    elif number == 37:
        content = group("ppt-stack ppt-layout-bashrc",
            group("ppt-bashrc-main", card(119, 120), group("ppt-stack", heading(121), code(134))),
            group("ppt-columns-3", card(123, 124, 125), card(127, 128, 129), card(131, 132, 133)))
    elif number == 41:
        content = group("ppt-stack ppt-layout-package",
            group("ppt-package-main", group("ppt-stack", heading(240), code(239)),
                  group("ppt-stack", heading(242), group("ppt-package-cards", card(244, 245), card(247, 248), card(250, 251), card(253, 254), card(256, 257, class_name="ppt-wide")))),
            block(259, "ppt-keyline"))
    elif number == 44:
        content = group("ppt-stack ppt-layout-message",
            group("ppt-message-main", card(332, 333),
                  group("ppt-card", heading(338), block(340, "ppt-type-name"), code(341)),
                  group("ppt-card ppt-message-fields", block(342))),
            block(335, "ppt-keyline"), block(345, "ppt-keyline"))
    elif number == 53:
        content = group("ppt-stack ppt-layout-physics", group("ppt-columns-3", card(573, 574), card(576, 577), card(579, 580)),
                        heading(581), flow([582, 584, 586, 588, 590]),
                        group("ppt-columns-2", card(592, 593), card(595, 596)), block(598, "ppt-keyline"))
    elif number == 54:
        content = group("ppt-layout-formats",
            group("ppt-card ppt-stack", heading(614), diagram([615, 616, 617], "ppt-diagram--formats"), block(620)),
            group("ppt-card ppt-format-card", block(622, "ppt-badge"), heading(623), block(624, "ppt-format-name"), block(625), code(626)),
            group("ppt-card ppt-format-card", block(628, "ppt-badge"), heading(629), block(630, "ppt-format-name"), block(631), code(632)))
    elif number == 55:
        # Allocate enough height to the two-line wheel labels within the tree.
        for index, rows in {647: "28/43", 648: "54/77", 649: "54/77", 650: "87/102"}.items():
            values = styles(shapes[index])
            values["grid-row"] = rows
            set_styles(shapes[index], values)
        for connection, rows in zip(connections, ["43/54", "43/54", "43/87"]):
            values = styles(connection)
            values["grid-row"] = rows
            set_styles(connection, values)
        content = group("ppt-stack ppt-layout-urdf",
            group("ppt-columns-3", card(656, 657, 658), card(660, 661, 662), card(664, 665, 666)),
            group("ppt-urdf-main", group("ppt-card", heading(646), diagram([647, 648, 649, 650], "ppt-diagram--urdf"), block(654)),
                  group("ppt-stack", heading(667), code(668)), card(670, 671)), block(672, "ppt-keyline"))
    else:
        content = group("ppt-stack ppt-layout-control", heading(704), flow([705, 707, 709, 711, 713, 715]),
                        group("ppt-columns-3", card(717, 718), card(720, 721), card(723, 724)), block(726, "ppt-keyline"))

    required = {el for el in elements if "".join(el.itertext()).strip() or el.tag == "figure" or el in connections}
    if required - used:
        raise ValueError(f"Unplaced content on slide {number}: {[el.attrib for el in required-used]}")
    canvas.clear()
    canvas.set("class", "ppt-canvas ppt-reflow")
    canvas.append(content)
    slide.set("class", slide.get("class") + " ppt-slide--reflow")
    slide.set("data-reflow", "1")
