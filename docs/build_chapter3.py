"""Builds docs/Chapter3_Research_Methodology.docx following the CUT formatting rules,
and lints the text against the CUT writing rules. Run:  python docs/build_chapter3.py"""
import re
import sys
from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_COLOR_INDEX
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from chapter3_content import C  # noqa: E402

PH = re.compile(r"(\[[^\]]*REQUIRED[^\]]*\])")


# ---------------- linter ----------------
def lint():
    problems = []
    for item in C:
        if item[0] != "p":
            continue
        t = item[1]
        plain = PH.sub("X", t)
        if "—" in t or "–" in t: problems.append(("dash", t[:60]))
        if re.search(r"\b\w+n't\b|\b(it|that|there|he|she)'s\b|\b\w+'(ll|re|ve|d)\b", plain, re.I): problems.append(("contraction", t[:60]))
        if re.search(r"\b(I|we|our|my|us|We|Our)\b", plain): problems.append(("first person", t[:60]))
        if re.search(r"\bwill\b|\bshall\b|\bgoing to\b", plain): problems.append(("future tense", t[:60]))
        if re.search(r",\s+(and|or)\s", plain): problems.append(("comma before and/or (check)", re.search(r".{30},\s+(and|or)\s.{20}", plain).group(0) if re.search(r".{30},\s+(and|or)\s.{20}", plain) else t[:60]))
        if re.search(r"\bnot only\b|\bnot merely\b|\bnot just\b", plain, re.I): problems.append(("negative parallelism", t[:60]))
        if re.search(r"(Furthermore|Moreover|Additionally|In summary|Overall|In conclusion|In addition),", plain): problems.append(("stock transition", t[:60]))
        if re.search(r"\b(delve|leverage|robust|holistic|seamless|pivotal|foster|harness|myriad|tapestry|landscape|crucial|underscore)", plain, re.I): problems.append(("AI vocabulary", t[:60]))
        if "&" in plain: problems.append(("ampersand", t[:60]))
        sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", plain) if s.strip()]
        if len(sents) < 3: problems.append((f"paragraph has {len(sents)} sentences", t[:60]))
        for s in sents:
            if re.match(r"\d", s): problems.append(("sentence starts with numeral", s[:60]))
    return problems


# ---------------- docx helpers ----------------
def set_cell_bg(cell, hexcol):
    tcPr = cell._tc.get_or_add_tcPr(); shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear"); shd.set(qn("w:color"), "auto"); shd.set(qn("w:fill"), hexcol); tcPr.append(shd)


def runs(par, text, bold=False, italic=False, size=12):
    for chunk in PH.split(text):
        if not chunk:
            continue
        r = par.add_run(chunk); r.bold, r.italic = bold, italic
        r.font.size = Pt(size); r.font.name = "Times New Roman"
        r._element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")
        if PH.fullmatch(chunk):
            r.font.highlight_color = WD_COLOR_INDEX.YELLOW


def para(doc, text, align=WD_ALIGN_PARAGRAPH.JUSTIFY, bold=False, italic=False, size=12, before=0, after=6, keep=False):
    par = doc.add_paragraph(); par.alignment = align
    f = par.paragraph_format; f.line_spacing = 1.5; f.space_before = Pt(before); f.space_after = Pt(after); f.keep_with_next = keep
    runs(par, text, bold, italic, size); return par


def page_number(section):
    p = section.footer.paragraphs[0]; p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(); r.font.name = "Times New Roman"; r.font.size = Pt(12)
    for kind, txt in (("begin", None), (None, "PAGE"), ("end", None)):
        if kind:
            e = OxmlElement("w:fldChar"); e.set(qn("w:fldCharType"), kind)
        else:
            e = OxmlElement("w:instrText"); e.set(qn("xml:space"), "preserve"); e.text = txt
        r._r.append(e)


def build(out):
    doc = Document()
    st = doc.styles["Normal"]; st.font.name = "Times New Roman"; st.font.size = Pt(12)
    st.element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")
    s = doc.sections[0]
    s.page_width, s.page_height = Inches(8.27), Inches(11.69)  # A4
    s.left_margin, s.right_margin, s.top_margin, s.bottom_margin = Inches(1.25), Inches(1), Inches(1), Inches(1)
    page_number(s)
    usable = 8.27 - 2.25
    for item in C:
        k = item[0]
        if k == "h1":
            para(doc, item[1], WD_ALIGN_PARAGRAPH.LEFT, bold=True, size=14, after=10, keep=True)
        elif k == "h2":
            deep = re.match(r"^\d+\.\d+\.\d+", item[1])
            para(doc, item[1], WD_ALIGN_PARAGRAPH.LEFT, bold=True, italic=bool(deep), before=8, after=4, keep=True)
        elif k == "p":
            para(doc, item[1])
        elif k == "table":
            _, cap, head, rows, widths = item
            para(doc, cap, WD_ALIGN_PARAGRAPH.CENTER, bold=True, before=6, after=3, keep=True)
            t = doc.add_table(rows=1, cols=len(head)); t.style = "Table Grid"; t.alignment = WD_TABLE_ALIGNMENT.CENTER
            scale = usable / sum(widths) if widths else None
            for i, h in enumerate(head):
                c = t.rows[0].cells[i]; c.text = ""; runs(c.paragraphs[0], h, bold=True, size=11); set_cell_bg(c, "DBEAFE")
            for row in rows:
                cells = t.add_row().cells
                for i, v in enumerate(row):
                    cells[i].text = ""; runs(cells[i].paragraphs[0], v, size=11)
            if widths:
                for row in t.rows:
                    for i, w in enumerate(widths): row.cells[i].width = Inches(w * scale)
            doc.add_paragraph().paragraph_format.space_after = Pt(2)
        elif k == "fig":
            _, cap, path = item
            pic = doc.add_paragraph(); pic.alignment = WD_ALIGN_PARAGRAPH.CENTER; pic.paragraph_format.keep_with_next = True
            pic.add_run().add_picture(str(HERE / path), width=Inches(usable))
            para(doc, cap, WD_ALIGN_PARAGRAPH.CENTER, bold=True, after=10)
        elif k == "slot":
            _, cap, how = item
            t = doc.add_table(rows=1, cols=1); t.style = "Table Grid"; t.alignment = WD_TABLE_ALIGNMENT.CENTER
            c = t.rows[0].cells[0]; set_cell_bg(c, "F1F5F9"); c.text = ""
            runs(c.paragraphs[0], "[FIGURE REQUIRED] ", bold=True, size=11)
            runs(c.paragraphs[0], how, size=11)
            para(doc, cap, WD_ALIGN_PARAGRAPH.CENTER, bold=True, before=4, after=10)
    doc.save(out)


if __name__ == "__main__":
    issues = lint()
    for i in issues: print("LINT", i)
    print(f"{len(issues)} lint findings")
    out = HERE / "Chapter3_Research_Methodology.docx"
    build(out); print("wrote", out)
