"""Build a one-slide .pptx from a JSON spec on the user's own template deck.

    python build_slide.py --template TEAM.pptx --spec slide.json --out OUT.pptx
                          [--preview OUT.png]

The template supplies the master, layout, theme colours and fonts; every
shape this script draws uses theme colours, so the slide looks like the rest
of the deck. The template's own slides are dropped. The spec format is in
references/slide-spec.md.

Exit codes: 0 built, 1 the spec does not fit or is invalid (every problem is
printed, fix the spec and run again), 2 python-pptx is missing, 3 the
template cannot be read.
"""
import argparse
import copy
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    from lxml import etree
    from pptx import Presentation
    from pptx.dml.color import RGBColor
    from pptx.enum.dml import MSO_THEME_COLOR, MSO_LINE_DASH_STYLE
    from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE, PP_PLACEHOLDER
    from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
    from pptx.opc.constants import RELATIONSHIP_TYPE as RT
    from pptx.oxml.ns import qn
    from pptx.util import Emu, Pt
except ImportError:
    print("python-pptx is not installed. Install it once with:\n"
          "  python -m pip install --user python-pptx", file=sys.stderr)
    sys.exit(2)

EMU_PER_PT = 12700
RED = RGBColor(0xFF, 0x00, 0x00)  # the Before/After labels and "Removed"
# Chip fills, in order of first appearance. The same text gets the same
# colour on both sides, so a component is recognisable across the divider.
PALETTE = [
    (MSO_THEME_COLOR.TEXT_2, 0),
    (MSO_THEME_COLOR.ACCENT_1, 0.6),
    (MSO_THEME_COLOR.ACCENT_3, -0.25),
    (MSO_THEME_COLOR.ACCENT_2, 0),
    (MSO_THEME_COLOR.ACCENT_4, 0),
    (MSO_THEME_COLOR.ACCENT_5, 0),
    (MSO_THEME_COLOR.ACCENT_6, 0),
]
# The look of a shape drawn in PowerPoint with the theme's default style,
# minus the shadow: a 2nd-weight accent1 outline and light text.
SHAPE_STYLE = (
    '<p:style xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"'
    ' xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
    '<a:lnRef idx="2"><a:schemeClr val="accent1"/></a:lnRef>'
    '<a:fillRef idx="1"><a:schemeClr val="accent1"/></a:fillRef>'
    '<a:effectRef idx="0"><a:schemeClr val="accent1"/></a:effectRef>'
    '<a:fontRef idx="minor"><a:schemeClr val="{font}"/></a:fontRef>'
    '</p:style>')
# Left plus right text inset of a placeholder or shape that sets none.
DEFAULT_INSETS = 182880

PROBLEMS = []
THEME_RGB = {}  # filled from the template's theme by read_theme()


def problem(msg):
    if msg not in PROBLEMS:
        PROBLEMS.append(msg)


# Helvetica/Arial advance widths per 1000 em for printable ASCII (32-126),
# close enough for the sans-serif fonts corporate templates use.
_WIDTHS = [
    278, 278, 355, 556, 556, 889, 667, 191, 333, 333, 389, 584, 278, 333,
    278, 278, 556, 556, 556, 556, 556, 556, 556, 556, 556, 556, 278, 278,
    584, 584, 584, 556, 1015, 667, 667, 722, 722, 667, 611, 778, 722, 278,
    500, 667, 556, 833, 722, 778, 667, 778, 722, 667, 611, 722, 667, 944,
    667, 667, 611, 278, 278, 278, 469, 556, 333, 556, 556, 500, 556, 556,
    278, 556, 556, 222, 222, 500, 222, 833, 556, 556, 556, 556, 333, 500,
    278, 556, 500, 722, 500, 500, 500, 334, 260, 334, 584]


def text_width(text, pt, bold=False, mono=False):
    """Rendered width in EMU, a few percent wide so the check errs safe."""
    if mono:
        em = 550 * len(text)
    else:
        em = sum(_WIDTHS[ord(c) - 32] if 32 <= ord(c) < 127 else 600
                 for c in text)
        em *= 1.08 if bold else 1.0
    return int(em / 1000 * pt * EMU_PER_PT * 1.04)


def line_count(text, pt, width, bold=False):
    width = max(width, 1)
    words, lines, cur = text.split(), 1, 0
    space = text_width(" ", pt, bold)
    for w in words:
        ww = text_width(w, pt, bold)
        if cur and cur + space + ww <= width:
            cur += space + ww
            continue
        if cur:
            lines += 1
        # A word wider than the line breaks across lines.
        spill = (ww - 1) // width
        lines += spill
        cur = ww - spill * width
    return lines


# -------------------------------------------------------------- spec shape

# Characters XML cannot hold, such as a vertical tab pasted from Word.
NOT_XML_TEXT = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f\ud800-\udfff\ufffe\uffff]")


def check_characters(value):
    if isinstance(value, str):
        if NOT_XML_TEXT.search(value):
            problem(f"{value!r} has a control character; retype that text")
    elif isinstance(value, dict):
        for child in value.values():
            check_characters(child)
    elif isinstance(value, list):
        for child in value:
            check_characters(child)


def is_text(value):
    return isinstance(value, str) and bool(value.strip())


def line_text(line):
    """An item or a note line: a string, or a dict with its text."""
    return line.get("text") if isinstance(line, dict) else line


def check_side(key, side):
    where = f"body.{key}"
    if (not isinstance(side, dict) or not isinstance(side.get("stages"), list)
            or not side["stages"]):
        problem(f"{where}.stages is required for before_after")
        return
    for n, stage in enumerate(side["stages"]):
        boxes = stage if isinstance(stage, list) else [stage]
        if not boxes:
            problem(f"{where}.stages[{n}] has no boxes")
        for box in boxes:
            if not isinstance(box, dict):
                problem(f"{where}.stages[{n}]: a box is {{caption, items}}")
                continue
            caption, items = box.get("caption", ""), box.get("items", [])
            if not isinstance(caption, str):
                problem(f"{where}.stages[{n}]: a caption must be text")
            if not isinstance(items, list):
                problem(f"{where}.stages[{n}]: items must be a list")
                continue
            if not caption and not items:
                problem(f"{where}.stages[{n}]: a box needs a caption or items")
            if not all(is_text(line_text(it)) for it in items):
                problem(f"{where}.stages[{n}]: an item is text or "
                        "{\"text\": ...}")
    note = side.get("note")
    if note is not None and not (isinstance(note, list) and all(
            is_text(line_text(l)) for l in note)):
        problem(f"{where}.note must be a list of lines")
    elif note and not all(isinstance(l.get("bold", False), bool)
                          for l in note if isinstance(l, dict)):
        problem(f"{where}.note: bold must be true or false")


def check_sections(body):
    sections = body.get("sections", [])
    if not isinstance(sections, list):
        problem("body.sections must be a list")
        sections = []
    for n, sec in enumerate(sections):
        if not isinstance(sec, dict) or not is_text(sec.get("heading")):
            problem(f"body.sections[{n}] needs a heading")
            continue
        points = sec.get("points")
        if not (is_text(points) or (isinstance(points, list) and points
                                    and all(is_text(p) for p in points))):
            problem(f"body.sections[{n}].points must be text or a list of text")
    flow = body.get("flow")
    if flow is not None and not isinstance(flow, list):
        problem("body.flow must be a list of steps")
        flow = []
    for n, step in enumerate(flow or []):
        if not isinstance(step, dict) or not is_text(step.get("title")):
            problem(f"body.flow[{n}] needs a title")
            continue
        points = step.get("points", [])
        if not (isinstance(points, list) and all(is_text(p) for p in points)):
            problem(f"body.flow[{n}].points must be a list of text")
    if body.get("image") is not None and not is_text(body["image"]):
        problem("body.image must be a file path")


def check_spec(spec):
    """Everything drawing relies on, checked once before anything is drawn."""
    if not isinstance(spec, dict):
        problem("the spec must be one JSON object")
        return
    check_characters(spec)
    if not is_text(spec.get("title")):
        problem("title is required")
    for field in ("key", "link", "presenter", "date", "layout"):
        if spec.get(field) is not None and not isinstance(spec[field], str):
            problem(f"{field} must be text")
    body = spec.get("body")
    if not isinstance(body, dict):
        problem("body is required")
        return
    if not is_text(body.get("goal")):
        problem("body.goal is required: one sentence, the why of the story")
    if body.get("kind") == "before_after":
        for key in ("before", "after"):
            check_side(key, body.get(key))
    elif body.get("kind") == "sections":
        check_sections(body)
    else:
        problem("body.kind must be 'before_after' or 'sections'")


# ---------------------------------------------------------------- template

def load_template(path):
    try:
        return Presentation(str(path))
    except Exception as exc:  # noqa: BLE001 - any read failure is fatal
        print(f"Cannot read template {path}: {exc}\n"
              "It must be a .pptx (save a .potx as .pptx first).",
              file=sys.stderr)
        sys.exit(3)


def read_theme(layout):
    """The theme's colour scheme, so chip text can pick a readable colour."""
    master = layout.slide_master
    try:
        theme = master.part.part_related_by(RT.THEME)
        scheme = etree.fromstring(theme.blob).find(".//" + qn("a:clrScheme"))
    except (KeyError, etree.XMLSyntaxError):
        return
    if scheme is None:
        return
    # The master's colour map decides what tx2 means: dk2, or lt2 on a
    # dark-background master.
    clr_map = master._element.find(qn("p:clrMap"))
    mapping = {"tx2": "dk2", **({} if clr_map is None else clr_map.attrib)}
    colours = {etree.QName(child).localname: child for child in scheme}
    slots = {MSO_THEME_COLOR.TEXT_2: "tx2", **{
        getattr(MSO_THEME_COLOR, f"ACCENT_{i}"): f"accent{i}"
        for i in range(1, 7)}}
    for slot, name in slots.items():
        child = colours.get(mapping.get(name, name))
        if child is None or not len(child):
            continue
        hexval = child[0].get("val") if child[0].tag == qn("a:srgbClr") \
            else child[0].get("lastClr")
        if hexval:
            THEME_RGB[slot] = tuple(int(hexval[i:i + 2], 16) / 255
                                    for i in (0, 2, 4))


def is_light(theme, brightness=0):
    """True when white text on this fill would be hard to read."""
    import colorsys
    rgb = THEME_RGB.get(theme)
    if rgb is None:
        return False
    h, l, s = colorsys.rgb_to_hls(*rgb)
    l = l * (1 - brightness) + brightness if brightness > 0 else l * (1 + brightness)
    rgb = colorsys.hls_to_rgb(h, l, s)
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
           for c in rgb]
    lum = 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]
    # White text stays, as in hand-drawn slides, until it drops below a
    # 2.5:1 contrast with the fill (yellows, light greys).
    return 1.05 / (lum + 0.05) < 2.5


def has_title_and_content(layout):
    kinds = {ph.placeholder_format.type for ph in layout.placeholders}
    return bool(kinds & {PP_PLACEHOLDER.TITLE, PP_PLACEHOLDER.CENTER_TITLE}
                and kinds & {PP_PLACEHOLDER.OBJECT, PP_PLACEHOLDER.BODY})


def all_layouts(prs):
    return [lay for master in prs.slide_masters for lay in master.slide_layouts]


def body_region_top(layout, slide_height):
    """Where content starts under the layout's title; None when the layout
    has no title, or its title sits on the body or low on the slide."""
    title = layout_placeholder(layout, PP_PLACEHOLDER.TITLE,
                               PP_PLACEHOLDER.CENTER_TITLE)
    if title is None:
        return None
    bottom = title.top + title.height
    body = layout_placeholder(layout, PP_PLACEHOLDER.OBJECT,
                              PP_PLACEHOLDER.BODY)
    if body is not None:
        return body.top if bottom <= body.top else None
    if bottom > slide_height // 3:
        return None
    return max(bottom, int(slide_height * 0.2))


def layout_hint(prs, kind):
    """What to do about a refused layout, naming only layouts that fit."""
    fits = [" ".join(lay.name.split()) for lay in all_layouts(prs)
            if body_region_top(lay, prs.slide_height) is not None
            and (kind != "sections" or has_title_and_content(lay))]
    if not fits:
        return "no layout in this template fits; use another template"
    return "set layout to one of: " + ", ".join(repr(n) for n in fits)


def pick_layout(prs, name, kind):
    layouts = all_layouts(prs)
    if name:
        for lay in layouts:
            if " ".join(lay.name.split()) == " ".join(name.split()):
                return lay
        problem(f"layout {name!r} not in the template; "
                + layout_hint(prs, kind))
        return None
    # A deck the team presents from often opens with a title slide; the
    # first slide with a title and content is the one stories are told on.
    candidates = [s.slide_layout for s in prs.slides] or layouts
    for lay in candidates:
        if has_title_and_content(lay):
            return lay
    return candidates[0]


def drop_custom_shows(prs):
    """A custom show is a second reference to its slides, which would keep
    them in the package beside the new slide."""
    pres = prs.part._element
    shows = pres.find(qn("p:custShowLst"))
    if shows is not None:
        pres.remove(shows)
    try:
        props = prs.part.part_related_by(RT.PRES_PROPS)
    except KeyError:
        return
    root = etree.fromstring(props.blob)
    show_pr = root.find(qn("p:showPr"))
    chosen = show_pr.find(qn("p:custShow")) if show_pr is not None else None
    if chosen is not None:
        show_pr.remove(chosen)
        props._blob = etree.tostring(root, xml_declaration=True,
                                     encoding="UTF-8", standalone=True)


def drop_slides(prs):
    drop_custom_shows(prs)
    sld_ids = prs.slides._sldIdLst
    for sld_id in list(sld_ids):
        prs.part.drop_rel(sld_id.rId)
        sld_ids.remove(sld_id)
    # Sections name slide ids that no longer exist; PowerPoint then asks to
    # repair the file.
    ext_lst = prs.part._element.find(qn("p:extLst"))
    if ext_lst is not None:
        for ext in list(ext_lst):
            if ext.find(
                    "{http://schemas.microsoft.com/office/powerpoint/2010/main}"
                    "sectionLst") is not None:
                ext_lst.remove(ext)


def layout_placeholder(layout, *types):
    for ph in layout.placeholders:
        if ph.placeholder_format.type in types:
            return ph
    return None


def body_font_pt(layout):
    """The size level-1 body text renders at, following PowerPoint's
    inheritance: layout placeholder, master placeholder, master body style."""
    path = "./p:txBody/a:lstStyle/a:lvl1pPr/a:defRPr"
    master = layout.slide_master
    candidates = [
        layout_placeholder(layout, PP_PLACEHOLDER.OBJECT, PP_PLACEHOLDER.BODY),
        layout_placeholder(master, PP_PLACEHOLDER.BODY)]
    nodes = [ph._element.find(path, ph._element.nsmap) for ph in candidates
             if ph is not None]
    nodes.append(master._element.find(
        "./p:txStyles/p:bodyStyle/a:lvl1pPr/a:defRPr", master._element.nsmap))
    for node in nodes:
        if node is not None and node.get("sz"):
            return int(node.get("sz")) / 100
    return 18


def set_fixed_date(el, date_text):
    """A plain run, because PowerPoint refreshes the layout's date field to
    the day the deck is opened."""
    tx_body = el.get_or_add_txBody()
    para, *rest = tx_body.p_lst
    for extra in rest:
        tx_body.remove(extra)
    r_pr = next(para.iter(qn("a:rPr")), None)
    for child in para.content_children:
        para.remove(child)
    run = para.add_r()
    run.text = date_text
    if r_pr is not None:
        run.insert(0, r_pr)


def clone_footer_placeholders(slide, layout, date_text):
    """add_slide skips date, footer and slide number; copy them from the
    layout so the slide keeps the deck's footer line."""
    wanted = {PP_PLACEHOLDER.DATE, PP_PLACEHOLDER.FOOTER,
              PP_PLACEHOLDER.SLIDE_NUMBER}
    tree = slide.shapes._spTree
    for ph in layout.placeholders:
        kind = ph.placeholder_format.type
        if kind not in wanted:
            continue
        el = copy.deepcopy(ph._element)
        el.nvSpPr.cNvPr.id = slide.shapes._next_shape_id
        sp_pr = el.find(qn("p:spPr"))
        for child in list(sp_pr):
            sp_pr.remove(child)  # inherit the layout's position
        if kind == PP_PLACEHOLDER.DATE:
            set_fixed_date(el, date_text)
        elif kind == PP_PLACEHOLDER.SLIDE_NUMBER:
            for t in el.iter(qn("a:t")):
                if t.getparent().tag == qn("a:fld"):
                    t.text = "1"
        tree.append(el)


# ----------------------------------------------------------------- drawing

def style(shape, font="lt1"):
    el = shape._element
    old = el.find(qn("p:style"))
    if old is not None:
        el.remove(old)
    # The schema puts p:style straight after p:spPr; out of order, PowerPoint
    # offers to repair the file.
    el.spPr.addnext(etree.fromstring(SHAPE_STYLE.replace("{font}", font)))


def fill_theme(fill, theme, brightness=0):
    fill.solid()
    fill.fore_color.theme_color = theme
    if brightness:
        fill.fore_color.brightness = brightness


def textbox(shapes, name, x, y, w, h, runs, size, align=PP_ALIGN.LEFT,
            anchor=MSO_ANCHOR.TOP, wrap=True):
    """runs: list of paragraphs, each a list of (text, opts) tuples."""
    box = shapes.add_textbox(Emu(x), Emu(y), Emu(w), Emu(h))
    box.name = name
    tf = box.text_frame
    tf.word_wrap = wrap
    tf.vertical_anchor = anchor
    for side in ("margin_left", "margin_right", "margin_top", "margin_bottom"):
        setattr(tf, side, 0)
    for i, para in enumerate(runs):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        for text, opts in para:
            r = p.add_run()
            r.text = text
            r.font.size = Pt(opts.get("size", size))
            r.font.bold = opts.get("bold", False)
            r.font.italic = opts.get("italic", False)
            if "rgb" in opts:
                r.font.color.rgb = opts["rgb"]
            elif "theme" in opts:
                r.font.color.theme_color = opts["theme"]
    return box


def rounded_box(shapes, name, x, y, w, h, caption="", size=10, top=None):
    """An outlined box; its caption is the box's own text, at the top, so
    it moves and resizes with the box."""
    shp = shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,
                           Emu(x), Emu(y), Emu(w), Emu(h))
    shp.name = name
    style(shp)
    fill_theme(shp.fill, MSO_THEME_COLOR.BACKGROUND_1)
    shp.adjustments[0] = min(0.16, 0.16 * 914400 / max(h, 1))
    tf = shp.text_frame
    tf.vertical_anchor = MSO_ANCHOR.TOP
    tf.word_wrap = True
    tf.margin_top, tf.margin_bottom = Emu(PAD if top is None else top), Emu(0)
    tf.margin_left = tf.margin_right = Emu(CAPTION_INSET)
    if caption:
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        r = p.add_run()
        r.text = caption
        r.font.size = Pt(size)
        r.font.color.theme_color = MSO_THEME_COLOR.TEXT_1
    return shp


def chip(shapes, x, y, w, h, item, colour):
    text, mono = item["text"], item.get("mono", False)
    size = 12
    while size > 9 and text_width(text, size, True, mono) > w - DEFAULT_INSETS:
        size -= 1
    if text_width(text, size, True, mono) > w - DEFAULT_INSETS:
        problem(f"chip {text!r} is too long for its box; shorten it")
    shp = shapes.add_shape(MSO_SHAPE.RECTANGLE,
                           Emu(x), Emu(y), Emu(w), Emu(h))
    shp.name = f"Item {text}"
    style(shp)
    fill_theme(shp.fill, *colour)
    shp.line.fill.background()
    tf = shp.text_frame
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    tf.word_wrap = False
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    r.text = text
    r.font.size = Pt(size)
    r.font.bold = not mono
    if is_light(*colour):
        r.font.color.theme_color = MSO_THEME_COLOR.DARK_1
    if mono:
        r.font.name = "Consolas"
    if item.get("state") == "removed":
        r.font._rPr.set("strike", "sngStrike")
    return shp


# Connection sites PowerPoint numbers on a rectangle.
TOP, LEFT, BOTTOM, RIGHT = 0, 1, 2, 3


def arrow(slide, src, dst, src_site=BOTTOM, dst_site=TOP):
    """A connector glued to both shapes, so it follows them when moved."""
    con = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, 0, 0, 0, 0)
    con.begin_connect(src, src_site)
    con.end_connect(dst, dst_site)
    con.name = f"Arrow to {dst.name}"
    style(con, "tx1")
    etree.SubElement(con.line._get_or_add_ln(), qn("a:tailEnd"),
                     type="triangle")
    return con


# ------------------------------------------------------------------- title

def set_title(slide, title, spec):
    tf = title.text_frame
    p = tf.paragraphs[0]
    key, summary = (spec.get("key") or "").strip(), spec["title"].strip()
    if key:
        r = p.add_run()
        r.text = key
        if spec.get("link"):
            r.hyperlink.address = spec["link"]
        p.add_run().text = "\u00a0"
    p.add_run().text = summary
    full = f"{key} {summary}".strip()
    if line_count(full, title_font_pt(slide), title.width - DEFAULT_INSETS,
                  bold=True) > 2:
        problem(f"the title wraps past two lines ({len(full)} characters); "
                "shorten the summary")


def title_font_pt(slide):
    """Title size: layout title placeholder, then the master title style."""
    layout, master = slide.slide_layout, slide.slide_layout.slide_master
    nodes = []
    ph = layout_placeholder(layout, PP_PLACEHOLDER.TITLE,
                            PP_PLACEHOLDER.CENTER_TITLE)
    if ph is not None:
        nodes.append(ph._element.find(
            "./p:txBody/a:lstStyle/a:lvl1pPr/a:defRPr", ph._element.nsmap))
    nodes.append(master._element.find(
        "./p:txStyles/p:titleStyle/a:lvl1pPr/a:defRPr", master._element.nsmap))
    for node in nodes:
        if node is not None and node.get("sz"):
            return int(node.get("sz")) / 100
    return 28


def goal_runs(goal):
    return [("Goal:", {"bold": True, "theme": MSO_THEME_COLOR.ACCENT_1}),
            ("\u00a0" + goal, {})]


# ------------------------------------------------------------ before/after

def normalise_stage(stage):
    """A stage is a list of boxes; a box is {caption, items}."""
    boxes = stage if isinstance(stage, list) else [stage]
    out = []
    for b in boxes:
        items = [i if isinstance(i, dict) else {"text": i}
                 for i in b.get("items", [])]
        out.append({"caption": b.get("caption", ""), "items": items})
    return out


def colour_map(sides):
    colours = {}
    for side in sides:
        for stage in side["stages"]:
            for box in stage:
                for it in box["items"]:
                    if it["text"] not in colours:
                        colours[it["text"]] = PALETTE[len(colours) % len(PALETTE)]
    return colours


CHIP_H, CHIP_GAP, CAPTION_H, PAD = 310896, 128016, 228600, 91440
CAPTION_INSET = 45720
ARROW_GAP = 256032
NOTE_GAP, NOTE_MIN_W = 73152, 900000
MIN_BOX_W = 600000


def stage_height(stage, scale):
    bare = len(stage) >= 1 and all(not b["caption"] and len(b["items"]) == 1
                                   for b in stage)
    if bare:
        return int(CHIP_H * scale)
    n = max(len(b["items"]) for b in stage)
    cap = CAPTION_H if any(b["caption"] for b in stage) else 0
    return int((cap + PAD + n * CHIP_H + (n - 1) * CHIP_GAP + 2 * PAD) * scale)


def fit_rows(sides, top, bottom):
    """Shared row heights, so stage n sits level on both sides, plus the
    scale and the extra arrow gap that fill the space between."""
    n = max(len(s["stages"]) for s in sides)
    rows = [max(stage_height(s["stages"][i], 1) for s in sides
                if i < len(s["stages"])) for i in range(n)]
    avail = bottom - (top + 240000)
    gaps = (n - 1) * ARROW_GAP
    natural = sum(rows) + gaps
    scale, extra = 1.0, 0
    if natural > avail:
        scale = (avail - gaps) / (natural - gaps)
        if scale < 0.75:
            problem(f"{n} stages do not fit above the footer; merge stages "
                    "or drop items")
            scale = 0.75
    elif n > 1:
        extra = min((avail - natural) // (n - 1), 90000)
    return [int(r * scale) for r in rows], scale, extra


def draw_side(slide, side, x, w, top, bottom, colours, removed_style, fit):
    rows, scale, extra = fit
    label = side["label"]
    textbox(slide.shapes, f"Label {label}", x, top, 1100000, 300000,
            [[(label, {"bold": True, "rgb": RED})]], 18)
    y, prev, shift = top + 240000, [], 0
    for si, stage in enumerate(side["stages"]):
        k = len(stage)
        gap = 274320
        note_room = NOTE_GAP + NOTE_MIN_W if si == 0 and side.get("note") else 0
        bw = min((w - note_room - (k - 1) * gap) // k,
                 2743200 if k == 1 else 2606040)
        if bw < MIN_BOX_W:
            problem(f"{label}: stage {si + 1} has too many boxes side by side; "
                    "merge them")
            return y
        group_w = k * bw + (k - 1) * gap
        gx = max(x, x + (w - group_w) // 2 - shift)
        if note_room:
            # Centred, moved left only as far as the note beside it needs,
            # and the stages below follow so their arrows stay straight.
            shift = max(0, gx + group_w + note_room - (x + w))
            gx -= shift
        h = rows[si]
        cur = []
        bare = all(not b["caption"] and len(b["items"]) == 1 for b in stage)
        for bi, box in enumerate(stage):
            bx = gx + bi * (bw + gap)
            cw = int(bw * 0.8)
            cx = bx + (bw - cw) // 2
            ch = int(CHIP_H * scale)
            if bare:
                item = box["items"][0]
                cur.append(chip(slide.shapes, cx, y, cw, ch, item,
                                colours[item["text"]]))
                continue
            # One group per box: the box with its caption plus its items,
            # so the whole box moves as one and an arrow stays glued to it.
            group = slide.shapes.add_group_shape()
            group.name = f"{label} {box['caption'] or 'box'}"
            size = 10
            inner = bw - 2 * CAPTION_INSET
            while size > 8 and text_width(box["caption"], size) > inner:
                size -= 1
            if text_width(box["caption"], size) > inner:
                problem(f"caption {box['caption']!r} is too long for its box")
            outline = rounded_box(group.shapes, f"Box {box['caption']}",
                                  bx, y, bw, h, box["caption"], size,
                                  int(PAD * scale))
            cy = y + int(PAD * scale)
            if box["caption"]:
                cy += int(CAPTION_H * scale)
            n = len(box["items"])
            block = n * ch + (n - 1) * int(CHIP_GAP * scale)
            cy += (y + h - cy - block) // 2
            for it in box["items"]:
                chip(group.shapes, cx, cy, cw, ch, it, colours[it["text"]])
                cy += ch + int(CHIP_GAP * scale)
            cur.append(outline)
        if si == 0 and side.get("note"):
            draw_note(slide, label, side["note"], gx + group_w, y, x + w, h,
                      removed_style)
        if prev:
            pairs = (zip(prev, cur) if len(prev) == len(cur) and len(cur) > 1
                     else [(a, b) for a in prev for b in cur])
            for a, b in pairs:
                arrow(slide, a, b)
        prev = cur
        y += h + ARROW_GAP + extra
    if y - ARROW_GAP - extra > bottom + 1:
        problem(f"{label}: the diagram runs past the footer")
    return y - ARROW_GAP - extra


def draw_note(slide, label, note, left, y, right, h, removed_style):
    lines = [l if isinstance(l, dict) else {"text": l} for l in note]
    x, w = left + NOTE_GAP, right - left - NOTE_GAP
    paras = []
    for i, l in enumerate(lines):
        if removed_style:
            opts = ({"bold": True, "rgb": RED, "size": 10} if i == 0
                    else {"size": 9})
        else:
            opts = {"italic": True, "theme": MSO_THEME_COLOR.ACCENT_1,
                    "size": 9, "bold": l.get("bold", False)}
        paras.append([(l["text"], opts)])
    box = textbox(slide.shapes, f"Note {label}", x, y, w, h, paras, 9,
                  PP_ALIGN.CENTER, MSO_ANCHOR.MIDDLE)
    for side in ("margin_left", "margin_right", "margin_top", "margin_bottom"):
        setattr(box.text_frame, side, 27432)
    if removed_style:
        shp = box
        shp._element.spPr.find(qn("a:prstGeom")).set("prst", "roundRect")
        shp.line.width = Pt(1)
        shp.line.color.theme_color = MSO_THEME_COLOR.TEXT_1
        shp.line.color.brightness = 0.5
        shp.line.dash_style = MSO_LINE_DASH_STYLE.DASH
    total = sum(line_count(l["text"], 10, w - 54864,
                           bold=(removed_style and i == 0) or l.get("bold", False))
                for i, l in enumerate(lines))
    if total * 10 * 1.25 * EMU_PER_PT > h:
        problem("the note has too much text for its box; keep it to "
                "three short lines")


def build_before_after(slide, prs, body, frame, footer_top):
    left, top, width = frame
    goal_h = 409343
    textbox(slide.shapes, "Goal", left, top, width, goal_h,
            [goal_runs(body["goal"])], 14)
    if line_count("Goal: " + body["goal"], 14, width) > 1:
        problem("goal is longer than one line; cut it to one sentence "
                "of about 15 words")
    region_top = top + goal_h + 100000
    region_bottom = footer_top - 390000
    sides = []
    for key, label in (("before", "Before"), ("after", "After")):
        side = body[key]
        sides.append({"label": label,
                      "stages": [normalise_stage(s) for s in side["stages"]],
                      "note": side.get("note")})
    colours = colour_map(sides)
    # The diagram uses the slide's full width inside the title margin, as
    # hand-drawn before/after slides do; the text column is narrower.
    dleft = max(left - 66000, 0)
    half = (prs.slide_width - 2 * dleft) // 2
    fit = fit_rows(sides, region_top, region_bottom)
    ends = [draw_side(slide, side, dleft + i * (half + 120000),
                      half - 120000, region_top, region_bottom, colours,
                      i == 0, fit) for i, side in enumerate(sides)]
    mid = dleft + half
    con = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Emu(mid),
                                     Emu(region_top), Emu(mid),
                                     Emu(min(max(ends), region_bottom)))
    con.name = "Divider"
    style(con, "tx1")


# ---------------------------------------------------------------- sections

def build_sections(slide, layout, body, frame, footer_top):
    left, top, width = frame
    ph = next(shape for shape in slide.placeholders
              if shape.placeholder_format.type in (PP_PLACEHOLDER.OBJECT,
                                                   PP_PLACEHOLDER.BODY))
    size = body_font_pt(layout)
    text_w = width - DEFAULT_INSETS
    tf = ph.text_frame
    paras = [("goal", body["goal"])]
    for sec in body.get("sections", []):
        if isinstance(sec.get("points"), list):
            paras.append(("head", sec["heading"]))
            paras += [("point", p) for p in sec["points"]]
        else:
            paras.append(("inline", (sec["heading"], sec.get("points", ""))))
    lines = 0
    first = True
    for kind, value in paras:
        p = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        if kind != "point":
            # Plain lines, even where the template bullets level 1.
            ppr = p._p.get_or_add_pPr()
            ppr.set("marL", "0")
            ppr.set("indent", "0")
            etree.SubElement(ppr, qn("a:buNone"))
        if kind == "goal":
            r = p.add_run(); r.text = "Goal:"; r.font.bold = True
            p.add_run().text = "\u00a0" + value
            lines += line_count("Goal: " + value, size, text_w)
        elif kind == "head":
            p.add_run().text = value.rstrip(":") + ":"
            lines += line_count(value.rstrip(":") + ":", size, text_w)
        elif kind == "inline":
            head, text = value
            line = f"{head.rstrip(':')}: {text}"
            p.add_run().text = line
            lines += line_count(line, size, text_w)
        else:
            ppr = p._p.get_or_add_pPr()
            ppr.set("marL", "285750")
            ppr.set("indent", "-285750")
            etree.SubElement(ppr, qn("a:buFontTx"))
            etree.SubElement(ppr, qn("a:buChar"), char="-")
            p.add_run().text = value
            lines += line_count(value, size, text_w - 285750)
    # line height plus the template's ~6pt after each paragraph
    text_h = int(lines * size * 1.2 * EMU_PER_PT + len(paras) * 6 * EMU_PER_PT)
    has_visual = body.get("flow") or body.get("image")
    region_bottom = footer_top - 300000
    # Taller than the layout's box, text set to the bottom would grow up over
    # the title; the box grows down instead, towards the footer check.
    if has_visual or text_h > ph.height:
        ph.left, ph.top, ph.width, ph.height = (Emu(left), Emu(top), Emu(width),
                                                Emu(text_h))
    if not has_visual:
        if top + text_h > region_bottom:
            problem(f"sections run about {lines} lines; cut points until "
                    "they fit above the footer")
        return
    vis_top = top + text_h + 200000
    vis_h = region_bottom - vis_top
    if vis_h < 1600000:
        problem("not enough room under the text for the flow or image; "
                "cut points or drop one visual")
        return
    flow_w = width
    if body.get("image"):
        img_w = width if not body.get("flow") else int(width * 0.4)
        place_image(slide, body["image"], left + width - img_w, vis_top,
                    img_w, vis_h)
        flow_w = width - img_w - 300000
    if body.get("flow"):
        draw_flow(slide, body["flow"], left, vis_top, flow_w, vis_h)


def place_image(slide, path, x, y, w, h):
    p = Path(path)
    if not p.is_file():
        problem(f"image {path} not found")
        return
    try:
        pic = slide.shapes.add_picture(str(p), Emu(x), Emu(y))
    except (OSError, ValueError) as exc:
        problem(f"image {path} cannot be placed: {exc}")
        return
    pic.name = f"Picture {p.name}"
    ratio = min(w / pic.width, h / pic.height)
    pic.width, pic.height = int(pic.width * ratio), int(pic.height * ratio)
    pic.left = Emu(x + (w - pic.width) // 2)
    pic.top = Emu(y)
    pic.line.width = Pt(0.75)
    pic.line.color.theme_color = MSO_THEME_COLOR.TEXT_1
    pic.line.color.brightness = 0.75


def draw_flow(slide, steps, x, y, w, h):
    n = len(steps)
    if not 2 <= n <= 5:
        problem("flow takes 2 to 5 steps")
        return
    gap = 320000
    sw = min((w - (n - 1) * gap) // n, 3200400)
    if sw < MIN_BOX_W:
        problem("the flow steps are too narrow; drop a step or the image")
        return
    x += (w - n * sw - (n - 1) * gap) // 2
    head_h = 420000
    size = 14
    # Box width less its 91440 side margins and the bullet's 171450 indent.
    text_w = sw - 2 * 91440 - 171450
    # Size every box to the fullest step, then centre the row in the space.
    text_h = max(
        sum(line_count(pt, 12, text_w) * 12 * 1.2 + 6
            for pt in step.get("points", [])) for step in steps)
    box_h = head_h // 2 + 80000 + int(text_h * EMU_PER_PT) + 140000
    if head_h // 2 + box_h > h:
        problem("the flow steps have too many points for the space left; "
                "cut points or drop a step")
        box_h = h - head_h // 2
    prev = None
    for i, step in enumerate(steps):
        sx = x + i * (sw + gap)
        box_top = y + head_h // 2
        # One group per step: the title bar and the box of points.
        group = slide.shapes.add_group_shape()
        group.name = f"Step {step['title']}"
        box = rounded_box(group.shapes, f"Step box {step['title']}", sx,
                          box_top, sw, box_h, top=head_h // 2 + 80000)
        tf = box.text_frame
        tf.margin_left = tf.margin_right = Emu(91440)
        for j, pt in enumerate(step.get("points", [])):
            p = tf.paragraphs[0] if j == 0 else tf.add_paragraph()
            p.alignment = PP_ALIGN.LEFT
            # A real bullet, so Enter in PowerPoint starts the next point.
            ppr = p._p.get_or_add_pPr()
            ppr.set("marL", "171450")
            ppr.set("indent", "-171450")
            etree.SubElement(ppr, qn("a:buFont"), typeface="Arial")
            etree.SubElement(ppr, qn("a:buChar"), char="\u2022")
            r = p.add_run()
            r.text = pt
            r.font.size = Pt(12)
            r.font.color.theme_color = MSO_THEME_COLOR.TEXT_1
        head = group.shapes.add_shape(MSO_SHAPE.RECTANGLE, Emu(sx + 90000),
                                      Emu(y), Emu(sw - 180000), Emu(head_h))
        head.name = f"Step title {step['title']}"
        style(head)
        fill_theme(head.fill, MSO_THEME_COLOR.ACCENT_1)
        head.line.fill.background()
        p = head.text_frame.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        head.text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
        r = p.add_run()
        r.text = step["title"]
        r.font.size = Pt(size)
        r.font.bold = True
        if is_light(MSO_THEME_COLOR.ACCENT_1):
            r.font.color.theme_color = MSO_THEME_COLOR.DARK_1
        if text_width(step["title"], size, True) > sw - 180000 - DEFAULT_INSETS:
            problem(f"flow step title {step['title']!r} is too long")
        if prev is not None:
            arrow(slide, prev, box, RIGHT, LEFT)
        prev = box


# -------------------------------------------------------------------- main

def presenter_box(slide, prs, footer_top, name, above_footer):
    """Centred on the footer line, or just above a footer with its own text."""
    w, h = 3608962, 139926
    if text_width("Presented by: " + name, 10) > w:
        problem(f"presenter {name!r} is too long for the footer line")
    y = footer_top - h - 40000 if above_footer else footer_top + 106966
    textbox(slide.shapes, "Presented by", (prs.slide_width - w) // 2, y, w, h,
            [[("Presented by:\u00a0" + name,
               {"theme": MSO_THEME_COLOR.ACCENT_1})]], 10, PP_ALIGN.CENTER,
            MSO_ANCHOR.BOTTOM)


def remove_unused_placeholders(slide, keep_body):
    for shape in list(slide.placeholders):
        kind = shape.placeholder_format.type
        if kind in (PP_PLACEHOLDER.TITLE, PP_PLACEHOLDER.CENTER_TITLE,
                    PP_PLACEHOLDER.DATE, PP_PLACEHOLDER.FOOTER,
                    PP_PLACEHOLDER.SLIDE_NUMBER):
            continue
        if keep_body and kind in (PP_PLACEHOLDER.OBJECT, PP_PLACEHOLDER.BODY) \
                and keep_body == shape.placeholder_format.idx:
            continue
        shape._element.getparent().remove(shape._element)


def build(template, spec, out):
    prs = load_template(template)
    body = spec["body"]
    kind = body["kind"]
    layout = pick_layout(prs, spec.get("layout"), kind)
    if layout is None:
        return False
    name = " ".join(layout.name.split())
    read_theme(layout)
    drop_slides(prs)
    slide = prs.slides.add_slide(layout)
    title = slide.shapes.title
    if title is None:
        problem(f"layout {name!r} has no title placeholder; "
                + layout_hint(prs, kind))
        return False
    top = body_region_top(layout, prs.slide_height)
    if top is None:
        problem(f"the title of layout {name!r} overlaps the body region; "
                + layout_hint(prs, kind))
        return False

    body_ph = layout_placeholder(layout, PP_PLACEHOLDER.OBJECT,
                                 PP_PLACEHOLDER.BODY)
    date_ph = layout_placeholder(layout, PP_PLACEHOLDER.DATE)
    footer_ph = layout_placeholder(layout, PP_PLACEHOLDER.FOOTER)
    left = body_ph.left if body_ph is not None else title.left
    width = body_ph.width if body_ph is not None else title.width
    footer_top = date_ph.top if date_ph is not None else int(
        prs.slide_height * 0.95)
    if kind == "sections" and body_ph is None:
        problem(f"layout {name!r} has no content placeholder for sections; "
                + layout_hint(prs, kind))
        return False

    date = spec.get("date") or datetime.date.today().isoformat()
    try:
        d = datetime.date.fromisoformat(date)
        date_text = f"{d:%B} {d.day}, {d.year}"
    except ValueError:
        problem(f"date {date!r} is not YYYY-MM-DD")
        date_text = date
    clone_footer_placeholders(slide, layout, date_text)
    set_title(slide, title, spec)

    keep = body_ph.placeholder_format.idx if kind == "sections" else None
    remove_unused_placeholders(slide, keep)
    if kind == "before_after":
        build_before_after(slide, prs, body, (left, top, width), footer_top)
    else:
        build_sections(slide, layout, body, (left, top, width), footer_top)
    if spec.get("presenter"):
        presenter_box(slide, prs, footer_top, spec["presenter"],
                      footer_ph is not None
                      and bool(footer_ph.text_frame.text.strip()))

    if PROBLEMS:
        return False
    try:
        prs.save(str(out))
    except OSError as exc:
        problem(f"cannot write {out}: {exc}")
        return False
    return True


def find_soffice():
    for name in ("soffice", "libreoffice"):
        if shutil.which(name):
            return shutil.which(name)
    for path in ("/Applications/LibreOffice.app/Contents/MacOS/soffice",
                 r"C:\Program Files\LibreOffice\program\soffice.exe",
                 r"C:\Program Files (x86)\LibreOffice\program\soffice.exe"):
        if os.path.isfile(path):
            return path
    return None


def preview(pptx, png):
    soffice = find_soffice()
    if not soffice:
        print("preview skipped: LibreOffice (soffice) not found")
        return False
    with tempfile.TemporaryDirectory() as tmp:
        # A private profile, so a running LibreOffice does not block this.
        profile = Path(tmp, "profile").as_uri()
        try:
            subprocess.run([soffice, f"-env:UserInstallation={profile}",
                            "--headless", "--convert-to", "png", "--outdir",
                            tmp, str(pptx)], capture_output=True, timeout=180)
        except (OSError, subprocess.SubprocessError) as exc:
            print(f"preview skipped: LibreOffice failed: {exc}")
            return False
        made = Path(tmp, Path(pptx).stem + ".png")
        if not made.is_file():
            print("preview skipped: LibreOffice did not produce a PNG")
            return False
        shutil.move(str(made), str(png))
    print(f"preview: {png}")
    return True


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--template", required=True, type=Path)
    ap.add_argument("--spec", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--preview", type=Path,
                    help="also render the slide to this PNG (needs LibreOffice)")
    args = ap.parse_args(argv)
    try:
        spec = json.loads(args.spec.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        problem(f"cannot read the spec {args.spec}: {exc}")
    else:
        check_spec(spec)
    if not PROBLEMS and build(args.template, spec, args.out):
        print(f"built: {args.out}")
        if args.preview:
            preview(args.out, args.preview)
        return 0
    print("The slide was not written. Fix the spec and run again:",
          file=sys.stderr)
    for p in PROBLEMS:
        print(f"- {p}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
