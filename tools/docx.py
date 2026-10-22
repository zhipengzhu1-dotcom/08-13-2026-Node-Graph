"""Read text, tables, and page headers/footers out of .docx and .xlsx files.

Shared by every tool in this repository. No third-party dependencies: an
Office file is a zip of XML, and the standard library opens both.
"""

import re
import zipfile
import xml.etree.ElementTree as ET

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
S = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


def _squash(text):
    return " ".join(text.split())


def _cell_text(el):
    """Word puts a run of text in many <w:t> nodes. Join them back together."""
    return _squash("".join(t.text or "" for t in el.iter(W + "t")))


def paragraphs(path):
    """Body paragraphs of a .docx, in order, blanks dropped."""
    with zipfile.ZipFile(path) as z:
        root = ET.fromstring(z.read("word/document.xml"))
    out = [_cell_text(p) for p in root.iter(W + "p")]
    return [p for p in out if p]


def tables(path):
    """Every table in a .docx body, as a list of rows, each row a list of cells."""
    with zipfile.ZipFile(path) as z:
        root = ET.fromstring(z.read("word/document.xml"))
    return [
        [[_cell_text(tc) for tc in tr.findall(W + "tc")] for tr in tbl.findall(W + "tr")]
        for tbl in root.iter(W + "tbl")
    ]


REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
PKG = "{http://schemas.openxmlformats.org/package/2006/relationships}"
APP = "{http://schemas.openxmlformats.org/officeDocument/2006/extended-properties}"


def page_count(path):
    """Pages, as Word recorded them at the last save. None if not recorded.

    This decides whether a header ever reaches a reader. A `default` header
    prints from page two onward, so in a one-page form it never prints at all.
    """
    with zipfile.ZipFile(path) as z:
        if "docProps/app.xml" not in z.namelist():
            return None
        root = ET.fromstring(z.read("docProps/app.xml"))
        el = root.find(APP + "Pages")
        return int(el.text) if el is not None and el.text and el.text.isdigit() else None


def headers_and_footers(path):
    """Header and footer parts the document actually uses.

    Returns a list of (kind, role, text). `kind` is "header" or "footer".
    `role` is "first", "default", or "even" — which pages the part prints on.

    Reading every part in the zip is not enough. A part must be referenced by a
    section to print, and its role decides which pages show it. Reporting an
    unprinted part as a defect is a false alarm.
    """
    out = []
    with zipfile.ZipFile(path) as z:
        rels = {
            r.get("Id"): r.get("Target")
            for r in ET.fromstring(z.read("word/_rels/document.xml.rels")).iter(PKG + "Relationship")
        }
        for sect in ET.fromstring(z.read("word/document.xml")).iter(W + "sectPr"):
            for ref in list(sect):
                if ref.tag not in (W + "headerReference", W + "footerReference"):
                    continue
                target = rels.get(ref.get(REL + "id"))
                if not target:
                    continue
                kind = "header" if ref.tag == W + "headerReference" else "footer"
                out.append((kind, ref.get(W + "type") or "default", _cell_text(ET.fromstring(z.read("word/" + target)))))
    return out


def prints_on(role, pages):
    """Does a part with this role reach a reader, in a document of this length?"""
    if role == "first":
        return "page 1"
    if role == "default":
        if pages is None:
            return "pages 2+ (page count unknown)"
        return f"pages 2-{pages}" if pages > 1 else None
    return None  # "even" only prints when even/odd headers are switched on


def body_only_text(path):
    """Text of the document body, with headers and footers excluded.

    Links must come from here. A stale header carries another document's
    number, and reading it as a reference invents a link that the document
    never made. EXL-FM74's footer names EXL-FM20; its body never does.
    """
    if str(path).lower().endswith((".xlsx", ".xls")):
        return _xlsx_text(path)
    with zipfile.ZipFile(path) as z:
        return _cell_text(ET.fromstring(z.read("word/document.xml")))


def body_text(path):
    """All readable text of a document, whatever its format."""
    if str(path).lower().endswith((".xlsx", ".xls")):
        return _xlsx_text(path)
    with zipfile.ZipFile(path) as z:
        parts = [n for n in z.namelist() if re.fullmatch(r"word/(document|header\d+|footer\d+)\.xml", n)]
        return _squash(" ".join(_cell_text(ET.fromstring(z.read(n))) for n in sorted(parts)))


def _xlsx_text(path):
    """Cell text of a spreadsheet, shared-strings resolved."""
    with zipfile.ZipFile(path) as z:
        strings = []
        if "xl/sharedStrings.xml" in z.namelist():
            root = ET.fromstring(z.read("xl/sharedStrings.xml"))
            strings = [_squash("".join(t.text or "" for t in si.iter(S + "t"))) for si in root.iter(S + "si")]
        words = []
        for name in z.namelist():
            if not re.fullmatch(r"xl/worksheets/sheet\d+\.xml", name):
                continue
            for c in ET.fromstring(z.read(name)).iter(S + "c"):
                v = c.find(S + "v")
                if v is None or v.text is None:
                    continue
                if c.get("t") == "s":
                    idx = int(v.text)
                    words.append(strings[idx] if idx < len(strings) else "")
                else:
                    words.append(v.text)
        return _squash(" ".join(words))
