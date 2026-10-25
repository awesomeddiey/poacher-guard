"""Small python-docx layer that applies the CUT dissertation formatting (A4, Times New Roman 12, 1.5 spacing, justified,
margins 1.25/1/1/1 in, centred page numbers) and renders chapter items. Yellow highlight marks every placeholder."""
import re
from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_COLOR_INDEX
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt

PH = re.compile(r"(\[[^\]]*REQUIRED[^\]]*\])")
USABLE = 8.27 - 2.25


def _bg(cell, hexcol):
    tcPr = cell._tc.get_or_add_tcPr(); shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear"); shd.set(qn("w:color"), "auto"); shd.set(qn("w:fill"), hexcol); tcPr.append(shd)


def runs(par, text, bold=False, italic=False, size=12):
    for chunk in PH.split(text):
        if not chunk: continue
        r = par.add_run(chunk); r.bold, r.italic = bold, italic; r.font.size = Pt(size); r.font.name = "Times New Roman"
        r._element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")
        if PH.fullmatch(chunk): r.font.highlight_color = WD_COLOR_INDEX.YELLOW


def para(doc, text, align=WD_ALIGN_PARAGRAPH.JUSTIFY, bold=False, italic=False, size=12, before=0, after=6, keep=False, hang=None):
    p = doc.add_paragraph(); p.alignment = align; f = p.paragraph_format
    f.line_spacing = 1.5 if size >= 12 else 1.15; f.space_before = Pt(before); f.space_after = Pt(after); f.keep_with_next = keep
    if hang: f.left_indent = Inches(hang); f.first_line_indent = Inches(-hang)
    runs(p, text, bold, italic, size); return p


def _page_number(section):
    p = section.footer.paragraphs[0]; p.alignment = WD_ALIGN_PARAGRAPH.CENTER; r = p.add_run(); r.font.name = "Times New Roman"; r.font.size = Pt(12)
    for kind, txt in (("begin", None), (None, "PAGE"), ("end", None)):
        if kind: e = OxmlElement("w:fldChar"); e.set(qn("w:fldCharType"), kind)
        else: e = OxmlElement("w:instrText"); e.set(qn("xml:space"), "preserve"); e.text = txt
        r._r.append(e)


def _table(doc, head, rows, widths, size=10):
    t = doc.add_table(rows=1, cols=len(head)); t.style = "Table Grid"; t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, h in enumerate(head):
        c = t.rows[0].cells[i]; c.text = ""; runs(c.paragraphs[0], h, bold=True, size=size); _bg(c, "DBEAFE")
    for row in rows:
        cells = t.add_row().cells
        for i, v in enumerate(row):
            cells[i].text = ""; runs(cells[i].paragraphs[0], str(v), size=size, bold=(i == 0 and str(row[0]).lower().startswith("total")))
    if widths:
        k = USABLE / sum(widths); t.autofit = False
        for i, w in enumerate(widths): t.columns[i].width = Inches(w * k)
        for row in t.rows:
            for i, w in enumerate(widths): row.cells[i].width = Inches(w * k)
    tr = t.rows[0]._tr; trPr = tr.get_or_add_trPr(); h = OxmlElement("w:tblHeader"); h.set(qn("w:val"), "true"); trPr.append(h)
    return t


def build(items, out, base: Path):
    doc = Document(); st = doc.styles["Normal"]; st.font.name = "Times New Roman"; st.font.size = Pt(12); st.element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")
    s = doc.sections[0]; s.page_width, s.page_height = Inches(8.27), Inches(11.69)
    s.left_margin, s.right_margin, s.top_margin, s.bottom_margin = Inches(1.25), Inches(1), Inches(1), Inches(1); _page_number(s)
    for it in items:
        k = it[0]
        if k == "h1": para(doc, it[1], WD_ALIGN_PARAGRAPH.LEFT, bold=True, size=14, after=10, keep=True)
        elif k == "h2": para(doc, it[1], WD_ALIGN_PARAGRAPH.LEFT, bold=True, before=8, after=4, keep=True)
        elif k == "h3": para(doc, it[1], WD_ALIGN_PARAGRAPH.LEFT, bold=True, italic=True, before=6, after=4, keep=True)
        elif k == "p": para(doc, it[1])
        elif k == "ref": para(doc, it[1], WD_ALIGN_PARAGRAPH.LEFT, size=12, after=4, hang=0.4)
        elif k == "table":
            _, cap, head, rows, widths = it[:5]; size = it[5] if len(it) > 5 else 10
            para(doc, cap, WD_ALIGN_PARAGRAPH.CENTER, bold=True, before=6, after=3, keep=True)
            _table(doc, head, rows, widths, size); doc.add_paragraph().paragraph_format.space_after = Pt(2)
        elif k == "eq":
            t = doc.add_table(rows=1, cols=2); t.alignment = WD_TABLE_ALIGNMENT.CENTER
            for c, txt, al in ((t.rows[0].cells[0], it[1], WD_ALIGN_PARAGRAPH.CENTER), (t.rows[0].cells[1], it[2], WD_ALIGN_PARAGRAPH.RIGHT)):
                c.text = ""; c.paragraphs[0].alignment = al; runs(c.paragraphs[0], txt, size=12)
            t.rows[0].cells[0].width, t.rows[0].cells[1].width = Inches(USABLE - 0.8), Inches(0.8)
        elif k == "fig":
            _, cap, paths, width = it
            paths = [paths] if isinstance(paths, str) else paths
            pic = doc.add_paragraph(); pic.alignment = WD_ALIGN_PARAGRAPH.CENTER; pic.paragraph_format.keep_with_next = True
            for pth in paths: pic.add_run().add_picture(str(base / pth), width=Inches(width or USABLE))
            para(doc, cap, WD_ALIGN_PARAGRAPH.CENTER, bold=True, size=11, after=10)
        elif k == "slot":
            _, cap, how = it
            t = doc.add_table(rows=1, cols=1); t.style = "Table Grid"; t.alignment = WD_TABLE_ALIGNMENT.CENTER; c = t.rows[0].cells[0]; _bg(c, "F1F5F9"); c.text = ""
            runs(c.paragraphs[0], "[FIGURE REQUIRED] ", bold=True, size=11); runs(c.paragraphs[0], how, size=11)
            para(doc, cap, WD_ALIGN_PARAGRAPH.CENTER, bold=True, size=11, before=4, after=10)
    doc.save(out)
