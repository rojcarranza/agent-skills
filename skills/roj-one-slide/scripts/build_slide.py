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
THEME_NAMES = {
    "accent1": MSO_THEME_COLOR.ACCENT_1, "accent2": MSO_THEME_COLOR.ACCENT_2,
    "accent3": MSO_THEME_COLOR.ACCENT_3, "accent4": MSO_THEME_COLOR.ACCENT_4,
    "accent5": MSO_THEME_COLOR.ACCENT_5, "accent6": MSO_THEME_COLOR.ACCENT_6,
    "tx2": MSO_THEME_COLOR.TEXT_2,
}
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
    words, lines, cur = text.split(), 1, 0
    space = text_width(" ", pt, bold)
    for w in words:
        ww = text_width(w, pt, bold)
        if cur and cur + space + ww > width:
            lines, cur = lines + 1, ww
        else:
            cur += (space if cur else 0) + ww
    return lines


# ---------------------------------------------------------------- template

def load_template(path):
    try:
        return Presentation(str(path))
    except Exception as exc:  # noqa: BLE001 - any read failure is fatal
        print(f"Cannot read template {path}: {exc}\n"
              "It must be a .pptx (save a .potx as .pptx first).",
              file=sys.stderr)
        sys.exit(3)


def read_theme(prs):
    """The theme's colour scheme, so chip text can pick a readable colour."""
    from pptx.opc.constants import RELATIONSHIP_TYPE as RT
    try:
        theme = prs.slide_master.part.part_related_by(RT.THEME)
        scheme = etree.fromstring(theme.blob).find(".//" + qn("a:clrScheme"))
    except (KeyError, etree.XMLSyntaxError):
        return
    slots = {"dk1": MSO_THEME_COLOR.TEXT_1, "dk2": MSO_THEME_COLOR.TEXT_2,
             "lt1": MSO_THEME_COLOR.BACKGROUND_1, **{
                 f"accent{i}": getattr(MSO_THEME_COLOR, f"ACCENT_{i}")
                 for i in range(1, 7)}}
    for child in scheme if scheme is not None else []:
        slot = slots.get(etree.QName(child).localname)
        if slot is None or not len(child):
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


def pick_layout(prs, name):
    layouts = list(prs.slide_layouts)
    if name:
        for lay in layouts:
            if " ".join(lay.name.split()) == " ".join(name.split()):
                return lay
        problem(f"layout {name!r} not in the template; it has: "
                + ", ".join(repr(" ".join(l.name.split())) for l in layouts))
        return layouts[0]
    # The layout the template's own first slide uses is the one the team
    # presents stories on.
    if len(prs.slides):
        return prs.slides[0].slide_layout
    for lay in layouts:
        kinds = {ph.placeholder_format.type for ph in lay.placeholders}
        if kinds & {PP_PLACEHOLDER.TITLE} and kinds & {
                PP_PLACEHOLDER.OBJECT, PP_PLACEHOLDER.BODY}:
            return lay
    return layouts[0]


def drop_slides(prs):
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


def body_font_pt(prs, layout):
    """The size level-1 body text renders at, following PowerPoint's
    inheritance: layout placeholder, master placeholder, master body style."""
    path = "./p:txBody/a:lstStyle/a:lvl1pPr/a:defRPr"
    master = prs.slide_master
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
        sp_pr = el.find(qn("p:spPr"))
        for child in list(sp_pr):
            sp_pr.remove(child)  # inherit the layout's position
        for t in el.iter(qn("a:t")):
            if kind == PP_PLACEHOLDER.DATE:
                t.text = date_text
            elif kind == PP_PLACEHOLDER.SLIDE_NUMBER and t.getparent().tag == qn("a:fld"):
                t.text = "1"
            elif kind == PP_PLACEHOLDER.FOOTER:
                t.text = " "
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


def textbox(slide, x, y, w, h, runs, size, align=PP_ALIGN.LEFT,
            anchor=MSO_ANCHOR.TOP, wrap=True):
    """runs: list of paragraphs, each a list of (text, opts) tuples."""
    box = slide.shapes.add_textbox(Emu(x), Emu(y), Emu(w), Emu(h))
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


def rounded_box(slide, x, y, w, h):
    shp = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,
                                 Emu(x), Emu(y), Emu(w), Emu(h))
    style(shp)
    fill_theme(shp.fill, MSO_THEME_COLOR.BACKGROUND_1)
    shp.adjustments[0] = min(0.16, 0.16 * 914400 / max(h, 1))
    return shp


def chip(slide, x, y, w, h, item, colour):
    text, mono = item["text"], item.get("mono", False)
    size = 12
    while size > 9 and text_width(text, size, True, mono) > w - 180000:
        size -= 1
    if text_width(text, size, True, mono) > w - 180000:
        problem(f"chip {text!r} is too long for its box; shorten it")
    shp = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE,
                                 Emu(x), Emu(y), Emu(w), Emu(h))
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
        r.font.color.theme_color = MSO_THEME_COLOR.TEXT_1
    if mono:
        r.font.name = "Consolas"
    if item.get("state") == "removed":
        r.font._rPr.set("strike", "sngStrike")
    return shp


def arrow(slide, x1, y1, x2, y2):
    con = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT,
                                     Emu(x1), Emu(y1), Emu(x2), Emu(y2))
    style(con, "tx1")
    etree.SubElement(con.line._get_or_add_ln(), qn("a:tailEnd"),
                     type="triangle")
    return con


# ------------------------------------------------------------------- title

def set_title(slide, spec):
    title = slide.shapes.title
    if title is None:
        problem("the layout has no title placeholder; pick another layout")
        return
    tf = title.text_frame
    p = tf.paragraphs[0]
    key, summary = spec.get("key", "").strip(), spec["title"].strip()
    if key:
        r = p.add_run()
        r.text = key
        if spec.get("link"):
            r.hyperlink.address = spec["link"]
        p.add_run().text = "\u00a0"
    p.add_run().text = summary
    full = f"{key} {summary}".strip()
    if line_count(full, title_font_pt(slide), title.width, bold=True) > 2:
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
    colours, explicit = {}, {}
    for side in sides:
        for stage in side["stages"]:
            for box in stage:
                for it in box["items"]:
                    if it.get("color"):
                        name = it["color"]
                        if name not in THEME_NAMES:
                            problem(f"color {name!r} unknown; use one of "
                                    + ", ".join(sorted(THEME_NAMES)))
                            continue
                        explicit[it["text"]] = (THEME_NAMES[name], 0)
                    elif it["text"] not in colours:
                        colours[it["text"]] = PALETTE[len(colours) % len(PALETTE)]
    colours.update(explicit)
    return colours


CHIP_H, CHIP_GAP, CAPTION_H, PAD = 310896, 128016, 228600, 91440
CAPTION_INSET = 45720
ARROW_GAP = 256032


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
    label_w = 1100000
    textbox(slide, x, top, label_w, 300000,
            [[(side["label"], {"bold": True, "rgb": RED})]], 18)
    stages = side["stages"]
    y0 = top + 240000

    y, prev = y0, []
    for si, stage in enumerate(stages):
        k = len(stage)
        gap = 274320
        bw = min((w - (k - 1) * gap) // k, 2743200 if k == 1 else 2606040)
        group_w = k * bw + (k - 1) * gap
        gx = x + (w - group_w) // 2
        h = rows[si]
        cur = []
        bare = all(not b["caption"] and len(b["items"]) == 1 for b in stage)
        for bi, box in enumerate(stage):
            bx = gx + bi * (bw + gap)
            cw = int(bw * 0.8)
            cx = bx + (bw - cw) // 2
            ch = int(CHIP_H * scale)
            if bare:
                chip(slide, cx, y, cw, ch, box["items"][0],
                     colours[box["items"][0]["text"]])
                cur.append((cx, y, cw, ch))
                continue
            rounded_box(slide, bx, y, bw, h)
            cy = y + int(PAD * scale)
            if box["caption"]:
                inner = bw - 2 * CAPTION_INSET
                size = 10
                while size > 8 and text_width(box["caption"], size) > inner:
                    size -= 1
                if text_width(box["caption"], size) > inner:
                    problem(f"caption {box['caption']!r} is too long for "
                            "its box")
                textbox(slide, bx + CAPTION_INSET, cy, inner, CAPTION_H,
                        [[(box["caption"], {})]], size, PP_ALIGN.CENTER)
                cy += int(CAPTION_H * scale)
            n = len(box["items"])
            block = n * ch + (n - 1) * int(CHIP_GAP * scale)
            cy += (y + h - cy - block) // 2
            for it in box["items"]:
                chip(slide, cx, cy, cw, ch, it, colours[it["text"]])
                cy += ch + int(CHIP_GAP * scale)
            cur.append((bx, y, bw, h))
        if si == 0 and side.get("note"):
            draw_note(slide, side["note"], gx + group_w, y, x + w, h,
                      removed_style)
        if prev:
            pairs = (zip(prev, cur) if len(prev) == len(cur) and len(cur) > 1
                     else [(a, b) for a in prev for b in cur])
            for a, b in pairs:
                arrow(slide, a[0] + a[2] // 2, a[1] + a[3],
                      b[0] + b[2] // 2, b[1])
        prev = cur
        y += h + ARROW_GAP + extra
    if y - ARROW_GAP - extra > bottom + 1:
        problem(f"{side['label']}: the diagram runs past the footer")
    return y - ARROW_GAP - extra


def draw_note(slide, note, left, y, right, h, removed_style):
    lines = [l if isinstance(l, dict) else {"text": l} for l in note]
    x, w = left + 73152, right - left - 73152
    if w < 900000:
        problem("no room for the note beside the first stage; make that "
                "stage a single box, or drop the note")
        return
    paras = []
    for i, l in enumerate(lines):
        if removed_style:
            opts = ({"bold": True, "rgb": RED, "size": 10} if i == 0
                    else {"size": 9})
        else:
            opts = {"italic": True, "theme": MSO_THEME_COLOR.ACCENT_1,
                    "size": 9, "bold": l.get("bold", False)}
        paras.append([(l["text"], opts)])
    box = textbox(slide, x, y, w, h, paras, 9, PP_ALIGN.CENTER,
                  MSO_ANCHOR.MIDDLE)
    for side in ("margin_left", "margin_right", "margin_top", "margin_bottom"):
        setattr(box.text_frame, side, 27432)
    if removed_style:
        shp = box
        shp._element.spPr.find(qn("a:prstGeom")).set("prst", "roundRect")
        shp.line.width = Pt(1)
        shp.line.color.theme_color = MSO_THEME_COLOR.TEXT_1
        shp.line.color.brightness = 0.5
        shp.line.dash_style = MSO_LINE_DASH_STYLE.DASH
    total = sum(line_count(l["text"], 10, w - 54864) for l in lines)
    if total * 10 * 1.25 * EMU_PER_PT > h:
        problem("the note has too much text for its box; keep it to "
                "three short lines")


def build_before_after(slide, prs, layout, body, frame, footer_top):
    left, top, width = frame
    goal_h = 409343
    textbox(slide, left, top, width, goal_h,
            [goal_runs(body["goal"])], 14)
    if line_count("Goal: " + body["goal"], 14, width) > 1:
        problem("goal is longer than one line; cut it to one sentence "
                "of about 15 words")
    region_top = top + goal_h + 100000
    region_bottom = footer_top - 390000
    sides = []
    for key, default in (("before", "Before"), ("after", "After")):
        side = body.get(key)
        if not side or not side.get("stages"):
            problem(f"body.{key}.stages is required for before_after")
            return
        sides.append({"label": side.get("label", default),
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
    style(con, "tx1")


# ---------------------------------------------------------------- sections

def build_sections(slide, prs, layout, body, frame, footer_top):
    left, top, width = frame
    ph = None
    for shape in slide.placeholders:
        if shape.placeholder_format.type in (PP_PLACEHOLDER.OBJECT,
                                             PP_PLACEHOLDER.BODY):
            ph = shape
            break
    if ph is None:
        problem("the layout has no content placeholder for sections; "
                "pick a 'Title Content' style layout")
        return
    size = body_font_pt(prs, layout)
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
            lines += line_count("Goal: " + value, size, width)
        elif kind == "head":
            p.add_run().text = value.rstrip(":") + ":"
            lines += 1
        elif kind == "inline":
            head, text = value
            p.add_run().text = f"{head.rstrip(':')}: {text}"
            lines += line_count(f"{head}: {text}", size, width)
        else:
            ppr = p._p.get_or_add_pPr()
            ppr.set("marL", "285750")
            ppr.set("indent", "-285750")
            etree.SubElement(ppr, qn("a:buFontTx"))
            etree.SubElement(ppr, qn("a:buChar"), char="-")
            p.add_run().text = value
            lines += line_count(value, size, width - 285750)
    # line height plus the template's ~6pt after each paragraph
    text_h = int(lines * size * 1.2 * EMU_PER_PT + len(paras) * 6 * EMU_PER_PT)
    has_visual = body.get("flow") or body.get("image")
    region_bottom = footer_top - 300000
    if not has_visual:
        if top + text_h > region_bottom:
            problem(f"sections run about {lines} lines; cut points until "
                    "they fit above the footer")
        return
    ph.left, ph.top, ph.width, ph.height = (Emu(left), Emu(top), Emu(width),
                                            Emu(text_h))
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
    pic = slide.shapes.add_picture(str(p), Emu(x), Emu(y))
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
    x += (w - n * sw - (n - 1) * gap) // 2
    head_h = 420000
    size = 14
    # Size every box to the fullest step, then centre the row in the space.
    text_h = max(
        sum(line_count(pt, 12, sw - 200000) * 12 * 1.2 + 6
            for pt in step.get("points", [])) for step in steps)
    box_h = head_h // 2 + 80000 + int(text_h * EMU_PER_PT) + 140000
    if head_h // 2 + box_h > h:
        problem("the flow steps have too many points for the space left; "
                "cut points or drop a step")
        box_h = h - head_h // 2
    for i, step in enumerate(steps):
        sx = x + i * (sw + gap)
        box_top = y + head_h // 2
        box = rounded_box(slide, sx, box_top, sw, box_h)
        tf = box.text_frame
        tf.vertical_anchor = MSO_ANCHOR.TOP
        tf.margin_top = Emu(head_h // 2 + 80000)
        tf.word_wrap = True
        for j, pt in enumerate(step.get("points", [])):
            p = tf.paragraphs[0] if j == 0 else tf.add_paragraph()
            p.alignment = PP_ALIGN.LEFT
            r = p.add_run()
            r.text = "\u2022 " + pt
            r.font.size = Pt(12)
            r.font.color.theme_color = MSO_THEME_COLOR.TEXT_1
        head = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Emu(sx + 90000),
                                      Emu(y), Emu(sw - 180000), Emu(head_h))
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
        if text_width(step["title"], size, True) > sw - 300000:
            problem(f"flow step title {step['title']!r} is too long")
        if i:
            mid = box_top + box_h // 2
            arrow(slide, sx - gap + 40000, mid, sx - 40000, mid)


# -------------------------------------------------------------------- main

def presenter_box(slide, prs, footer_top, name):
    w = 3608962
    textbox(slide, (prs.slide_width - w) // 2, footer_top + 106966, w, 139926,
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
    read_theme(prs)
    layout = pick_layout(prs, spec.get("layout"))
    drop_slides(prs)
    slide = prs.slides.add_slide(layout)

    date = spec.get("date") or datetime.date.today().isoformat()
    try:
        d = datetime.date.fromisoformat(date)
        date_text = f"{d:%B} {d.day}, {d.year}"
    except ValueError:
        problem(f"date {date!r} is not YYYY-MM-DD")
        date_text = date
    clone_footer_placeholders(slide, layout, date_text)
    set_title(slide, spec)

    title_ph = layout_placeholder(layout, PP_PLACEHOLDER.TITLE,
                                  PP_PLACEHOLDER.CENTER_TITLE)
    body_ph = layout_placeholder(layout, PP_PLACEHOLDER.OBJECT,
                                 PP_PLACEHOLDER.BODY)
    date_ph = layout_placeholder(layout, PP_PLACEHOLDER.DATE)
    left = body_ph.left if body_ph is not None else title_ph.left
    width = body_ph.width if body_ph is not None else title_ph.width
    top = body_ph.top if body_ph is not None else int(prs.slide_height * 0.2)
    footer_top = date_ph.top if date_ph is not None else int(
        prs.slide_height * 0.95)

    body = spec.get("body") or {}
    body.setdefault("goal", spec.get("goal", ""))
    if not body["goal"]:
        problem("goal is required: one sentence, the why of the story")
    kind = body.get("kind")
    keep = None
    if kind == "sections":
        keep = body_ph.placeholder_format.idx if body_ph is not None else None
    remove_unused_placeholders(slide, keep)
    if kind == "before_after":
        build_before_after(slide, prs, layout, body, (left, top, width),
                           footer_top)
    elif kind == "sections":
        build_sections(slide, prs, layout, body, (left, top, width),
                       footer_top)
    else:
        problem("body.kind must be 'before_after' or 'sections'")
    if spec.get("presenter"):
        presenter_box(slide, prs, footer_top, spec["presenter"])

    if PROBLEMS:
        return False
    prs.save(str(out))
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
        subprocess.run([soffice, f"-env:UserInstallation={profile}",
                        "--headless", "--convert-to", "png", "--outdir", tmp,
                        str(pptx)], capture_output=True, timeout=180)
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
    spec = json.loads(args.spec.read_text(encoding="utf-8"))
    for field in ("title",):
        if not spec.get(field):
            problem(f"{field} is required")
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
