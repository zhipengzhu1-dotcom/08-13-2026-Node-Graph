"""Build the document graph from the three folders.

Nodes are documents and instruments. Links are the connections between them,
each recorded with the kind of evidence that produced it, because the viewer
draws them differently and because a person must be able to check any one of
them against the document.

Node identity is the document number WITHOUT the revision. `EXL-SOP10-02` and
`EXL-SOP10-03` are one node, `EXL-SOP10`, with the revision held as a property.
The revision sits inside the document number in this scheme, so the full number
is not a stable identifier.

Usage:  python3 tools/extract_graph.py <sop-folder> <forms-folder> <methods-folder>
Writes: graph.json
"""

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import docx

# The four real document classes. They are the ones the laboratory's own
# tracking logs cover: FM11 for SOPs, FM12/FM13 for methods, FM14 for forms.
CLASSES = {
    "SOP": "standard operating procedure",
    "FM": "form",
    "AP": "analytical procedure",
    "TM": "test method",
}

DOC = re.compile(r"EXL[-\s]*(SOP|FM|AP|TM)[-\s]*(\d{1,3})(?:\s*-\s*(\d{2}))?", re.I)

# EXL-SOP20 defines the document numbering scheme. It names document classes
# and sample numbers as illustrations, not as references to real documents.
SCHEME_EXAMPLE = re.compile(r"sequential|e\.g\.|i\.e\.|such as|##|is issued for each", re.I)

RELATED_HEAD = re.compile(r"^\s*\d*[\.\)]?\s*RELATED\s+PROCEDURE", re.I)
EQUIPMENT_HEAD = re.compile(r"^\s*\d*[\.\)]?\s*(MATERIAL|EQUIPMENT|APPARATUS)", re.I)
SECTION_END = re.compile(
    r"^\s*\d*[\.\)]?\s*(ATTACHMENT|ATTACHEMENT|DEFINITION|PROCEDURE|MATERIAL|REFERENCE"
    r"|HEALTH|RESPONSIB|SCOPE|PURPOSE|CHANGE HISTORY|DOCUMENT|EQUIPMENT|RELATED)",
    re.I,
)
# A table-of-contents line, not a real heading.
TOC_LINE = re.compile(r"-{5,}|\.{5,}|…{2,}")

# Instrument vocabulary. Derived by hand from the equipment SOPs and their log
# forms, then checked against the corpus. Ticket #6 decides the canonical names
# and whether the equipment number from EXL-FM34 should be the identity instead.
# Each entry is: canonical name -> patterns that mean it.
INSTRUMENTS = {
    "Autoclave": r"autoclave|sterilizer",
    "Incubator": r"incubator",
    "Colony counter": r"colony counter",
    "Biosafety cabinet": r"biosafety cabinet|bsc\b",
    "Bead beater": r"bead beater",
    "Electronic pipette": r"electronic pipette",
    "Moisture balance": r"moisture balance",
    "Analytical balance": r"analytical balance|laboratory balance|lab balance|weighing",
    "Water purification unit": r"water purification",
    "pH meter": r"ph meter",
    "Micropipettor": r"micropipettor|micropipette|pipettor",
    "Refrigerator": r"refrigerator",
    "Freezer": r"freezer",
    "GC-MS": r"gc[-\s]?ms|gas chromatograph",
    "ICP-MS": r"icp[-\s]?ms",
    "Karl Fischer titrator": r"karl fischer|karl fisher",
    "TOC analyser": r"toc analyzer|total organic carbon",
    "Water activity meter": r"water activity",
    "qPCR": r"qpcr|real[-\s]?time pcr",
    "UPLC-PDA": r"uplc|hplc|lc[-\s]?pda",
    "Centrifuge": r"centrifuge",
    "Water bath": r"water bath",
    "UV lamp": r"uv lamp",
    "Thermometer": r"thermometer",
    "Hygrometer": r"hygrometer|humidity monitor",
}

# Titles too generic to match on. A title match needs to identify one document.
GENERIC = re.compile(r"^(general practices|procedure|form|log|record|reference|test)$", re.I)


def node_id(cls, num):
    return f"EXL-{cls}{int(num):02d}"


def parse_refs(text):
    """Every document reference in some text, as (id, revision, position)."""
    out = []
    for m in DOC.finditer(text):
        out.append((node_id(m.group(1).upper(), m.group(2)), m.group(3), m.start()))
    return out


def title_from_filename(name):
    """The document's title, as its file name gives it."""
    stem = Path(name).stem
    stem = DOC.sub("", stem)
    stem = re.sub(r"^[\s\-_]+|[\s\-_]+$", "", stem)
    return re.sub(r"\s{2,}", " ", stem).strip(" -_")


def section(paragraphs, head_pattern):
    """Paragraphs under a heading, up to the next heading.

    Takes the LAST match. The same heading appears in the table of contents
    first, where it is followed by dot leaders and a page number, not content.
    """
    body = []
    for i, para in enumerate(paragraphs):
        if not head_pattern.match(para) or TOC_LINE.search(para):
            continue
        found = []
        for nxt in paragraphs[i + 1:]:
            if SECTION_END.match(nxt) or TOC_LINE.search(nxt):
                break
            if nxt.strip():
                found.append(nxt.strip())
            if len(found) > 12:
                break
        if found:
            body = found
    return body


def load(folders):
    """Every live document, keyed by node id."""
    docs = {}
    skipped = []
    for folder in folders:
        for path in sorted(Path(folder).glob("*")):
            if path.is_dir() or path.name.startswith("~$"):
                continue
            if path.suffix.lower() not in (".docx", ".doc", ".xlsx", ".xls"):
                continue
            if path.stat().st_size == 0:
                skipped.append((path.name, "zero bytes"))
                continue
            refs = parse_refs(path.name)
            if not refs:
                skipped.append((path.name, "no document number in the name"))
                continue
            nid, rev, _ = refs[0]
            cls = re.match(r"EXL-([A-Z]+)", nid).group(1)
            docs[nid] = {
                "id": nid,
                "type": CLASSES[cls],
                "cls": cls,
                "title": title_from_filename(path.name),
                "revision": rev,
                "file": path.name,
                "folder": str(path.parent),
                "present": True,
            }
    return docs, skipped


def extract(folders):
    docs, skipped = load(folders)
    links = []
    instruments_seen = defaultdict(set)
    missing = {}

    def add(src, dst, kind, evidence):
        links.append({"source": src, "target": dst, "kind": kind, "evidence": evidence[:120]})

    for nid, meta in docs.items():
        path = Path(meta["folder"]) / meta["file"]
        is_word = path.suffix.lower() in (".docx", ".doc")

        try:
            # Body only. A stale header names another document, and reading it
            # as a reference invents a link the document never made.
            text = docx.body_only_text(path)
        except Exception:
            continue
        paragraphs = docx.paragraphs(path) if is_word else []

        related = section(paragraphs, RELATED_HEAD)
        related_text = " ".join(related)
        equipment_text = " ".join(section(paragraphs, EQUIPMENT_HEAD))

        # 1. Declared links: named in the RELATED PROCEDURES / FORMS section.
        declared = set()
        for ref, _, _ in parse_refs(related_text):
            if ref != nid:
                declared.add(ref)
                add(nid, ref, "declared", related_text)

        # 2. Attached forms: an SOP that carries a form as an attachment keeps
        #    the form's own header. Ticket #2 established these are real links.
        header_refs = set()
        if is_word:
            for kind, role, htext in docx.headers_and_footers(path):
                for ref, _, _ in parse_refs(htext):
                    if ref != nid and ref.startswith("EXL-FM") and meta["cls"] == "SOP":
                        header_refs.add(ref)
        for ref in header_refs - declared:
            add(nid, ref, "attached form", "carried as an attachment")

        # 3. Mentioned links: a document number anywhere else in the text.
        for ref, _, pos in parse_refs(text):
            if ref == nid or ref in declared or ref in header_refs:
                continue
            window = text[max(0, pos - 60):pos + 90]
            # The scheme text explains itself at length, so look further back.
            if nid == "EXL-SOP20" and SCHEME_EXAMPLE.search(text[max(0, pos - 260):pos + 40]):
                continue  # the numbering scheme's own illustrations
            add(nid, ref, "mentioned", window)
            declared.add(ref)  # one link per pair per kind

        # 4. Instruments.
        #    The title counts as evidence. A blank form holds almost no body
        #    text — its content is empty boxes — and its subject is stated in
        #    its name. a "UV lamp ... count" log is about the UV lamp even though
        #    the word appears nowhere in the body.
        haystack = (meta["title"] + " " + equipment_text + " " + text).lower()
        for name, pattern in INSTRUMENTS.items():
            m = re.search(pattern, haystack)
            if m:
                instruments_seen[name].add(nid)
                if re.search(pattern, meta["title"].lower()):
                    where = "the document's own title"
                elif re.search(pattern, equipment_text.lower()):
                    where = "equipment section"
                else:
                    where = "body text"
                add(nid, f"INSTRUMENT:{name}", "equipment", where)

    # 5. Title links: another document's title appears in the text, with no number.
    titles = {
        nid: meta["title"].lower()
        for nid, meta in docs.items()
        if len(meta["title"]) >= 14 and not GENERIC.match(meta["title"])
    }
    numbered = {(l["source"], l["target"]) for l in links}
    for nid, meta in docs.items():
        path = Path(meta["folder"]) / meta["file"]
        try:
            text = docx.body_only_text(path).lower()
        except Exception:
            continue
        for other, title in titles.items():
            if other == nid or (nid, other) in numbered:
                continue
            if title in text:
                add(nid, other, "title", f"names '{titles[other]}' without a number")

    # Referenced documents that are not in any folder.
    for link in links:
        tgt = link["target"]
        if tgt.startswith("INSTRUMENT:") or tgt in docs:
            continue
        cls = re.match(r"EXL-([A-Z]+)", tgt).group(1)
        missing.setdefault(tgt, {
            "id": tgt, "cls": cls, "type": CLASSES.get(cls, "unknown"),
            "title": None, "revision": None, "file": None, "present": False,
        })

    nodes = list(docs.values()) + list(missing.values())
    nodes += [
        {"id": f"INSTRUMENT:{n}", "cls": "INSTRUMENT", "type": "instrument",
         "title": n, "present": True, "used_by": sorted(srcs)}
        for n, srcs in sorted(instruments_seen.items())
    ]
    return {"nodes": nodes, "links": links, "skipped": skipped}


if __name__ == "__main__":
    graph = extract(sys.argv[1:])
    out = Path(__file__).parent.parent / "graph.json"
    out.write_text(json.dumps(graph, indent=1))
    print(f"nodes {len(graph['nodes'])}  links {len(graph['links'])}  -> {out}")
