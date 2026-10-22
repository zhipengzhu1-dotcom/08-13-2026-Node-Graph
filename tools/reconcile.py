"""Reconcile the document folders: inventory, numbering faults, and stale headers.

Two jobs.

1. Inventory every live document across the three folders. Report numbers used
   twice, numbers missing from a run, and revisions that disagree.

2. Scan the page headers and footers of every document and compare the document
   number written inside against the number in the file name. A file made by
   copying another form keeps the original number in the header used on page two
   onward. The file name gives no sign of it, so only this scan finds it.

Usage:  python3 tools/reconcile.py <folder> [<folder> ...]
"""

import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import docx

# EXL-SOP10-03, EXL-FM06-00, EXL-AP03-07. The separator before the revision is
# sometimes a space, and the class is sometimes followed by a space.
DOC = re.compile(r"EXL[-\s]*(SOP|FM|AP)[-\s]*(\d{1,3})(?:\s*-\s*(\d{2}))?", re.I)

CLASS_NAME = {"SOP": "SOP", "FM": "form", "AP": "analytical procedure"}


def parse(text):
    """Every document reference in some text, as (class, number, revision)."""
    out = []
    for cls, num, rev in DOC.findall(text):
        out.append((cls.upper(), f"{int(num):02d}", rev or None))
    return out


def from_filename(path):
    """The document this file claims to be, from its name."""
    found = parse(path.name)
    return found[0] if found else None


def inventory(folders):
    """Map every live file to the document number its name claims."""
    docs = defaultdict(list)
    unparsed = []
    for folder in folders:
        for path in sorted(Path(folder).glob("*")):
            if path.name.startswith("~$") or path.is_dir():
                continue
            if path.suffix.lower() not in (".docx", ".doc", ".xlsx", ".xls"):
                continue
            claim = from_filename(path)
            if claim is None:
                unparsed.append(path)
                continue
            docs[(claim[0], claim[1])].append((claim[2], path))
    return docs, unparsed


def numbering_faults(docs):
    """Numbers used twice, and gaps in each class's run."""
    duplicates, gaps = [], {}
    for key, entries in sorted(docs.items()):
        if len(entries) > 1:
            duplicates.append((key, entries))
    for cls in ("SOP", "FM", "AP"):
        used = sorted(int(n) for c, n in docs if c == cls)
        if not used:
            continue
        missing = [n for n in range(1, max(used) + 1) if n not in used]
        gaps[cls] = (min(used), max(used), missing)
    return duplicates, gaps


def classify(owner_cls, other_cls, text, position, visible):
    """Why does this header name a different document?

    Not every mismatch is a fault. Three cases look alike in the raw text and
    mean completely different things.
    """
    before = text[max(0, position - 40):position].lower()
    if "supersede" in before:
        return "supersedes"
    # An SOP often carries its own form as an attachment. The attachment keeps
    # its own header, which correctly names the form. That is not a fault.
    if owner_cls == "SOP" and other_cls == "FM" and "form" in text[:200].lower():
        return "attached form"
    # The stale text is real either way. But if the part never prints, no
    # record ever carries it. That is a latent fault, not a live one.
    return "contamination" if visible else "dormant"


def stale_headers(docs):
    """Documents whose header or footer names a different document."""
    findings, unreadable = [], []
    for (cls, num), entries in sorted(docs.items()):
        for rev, path in entries:
            if path.suffix.lower() not in (".docx", ".doc"):
                continue  # spreadsheets have no Word headers
            if path.stat().st_size == 0:
                unreadable.append((path, "file is empty — zero bytes"))
                continue
            try:
                parts = docx.headers_and_footers(path)
                pages = docx.page_count(path)
            except Exception as exc:
                unreadable.append((path, str(exc)))
                continue
            for part_kind, role, text in parts:
                where = docx.prints_on(role, pages)
                for m in DOC.finditer(text):
                    ocls = m.group(1).upper()
                    onum = f"{int(m.group(2)):02d}"
                    if (ocls, onum) == (cls, num):
                        continue
                    kind = classify(cls, ocls, text, m.start(), visible=bool(where))
                    label = f"EXL-{ocls}{onum}" + (f"-{m.group(3)}" if m.group(3) else "")
                    place = f"{part_kind}, {role}, prints on {where}" if where else f"{part_kind}, {role}, never prints ({pages} page)"
                    findings.append((kind, path, place, label, text[:150]))
    return findings, unreadable


def main(folders):
    docs, unparsed = inventory(folders)
    duplicates, gaps = numbering_faults(docs)
    stale, unreadable = stale_headers(docs)

    total_files = sum(len(v) for v in docs.values())
    print(f"# Reconciliation\n")
    print(f"Folders scanned: {len(folders)}")
    print(f"Files read: {total_files}")
    print(f"Distinct document numbers: {len(docs)}\n")

    print("## Count by class\n")
    for cls in ("SOP", "FM", "AP"):
        n = sum(1 for c, _ in docs if c == cls)
        print(f"- {CLASS_NAME[cls]}: {n}")

    print("\n## Numbering\n")
    for cls, (lo, hi, missing) in gaps.items():
        run = f"{lo:02d}-{hi:02d}"
        miss = ", ".join(f"{m:02d}" for m in missing) or "none"
        print(f"- {CLASS_NAME[cls]}: run {run}, missing {miss}")

    print("\n## One number, more than one file\n")
    if not duplicates:
        print("None.")
    for (cls, num), entries in duplicates:
        print(f"- **EXL-{cls}{num}**")
        for rev, path in entries:
            print(f"  - rev {rev or '??'} — `{path.name}`")

    print("\n## Files that cannot be read\n")
    if not unreadable:
        print("None.")
    for path, why in unreadable:
        print(f"- `{path.name}` — {why}")

    headings = {
        "contamination": (
            "## Stale headers and footers that print\n\n"
            "The page header or footer names a different document, AND that part\n"
            "reaches a reader. A completed record from this file disagrees with\n"
            "itself about what it is. These are the live defects."
        ),
        "dormant": (
            "## Stale text that never prints\n\n"
            "The same fault, but in a part that no reader sees. A `default` header\n"
            "prints from page 2 onward, so in a one-page form it never prints. The\n"
            "stale text is still in the file. It becomes a live defect only if the\n"
            "form ever grows to a second page. Worth cleaning at the next revision.\n"
            "Not worth a deviation."
        ),
        "supersedes": (
            "## Supersedes references\n\n"
            "The header names another document after the word 'Supersedes'. This is\n"
            "intended, not a fault. Check only that the named document is correct."
        ),
        "attached form": (
            "## Forms attached inside an SOP\n\n"
            "The SOP carries a form as an attachment. The attachment keeps its own\n"
            "header, which correctly names the form. Not a fault. These are real\n"
            "links between an SOP and a form, so the extractor should keep them."
        ),
    }
    for kind in ("contamination", "dormant", "supersedes", "attached form"):
        rows = [f for f in stale if f[0] == kind]
        print(f"\n{headings[kind]}\n")
        if not rows:
            print("None.")
        for _, path, place, wrong, sample in rows:
            print(f"- `{path.name}` — names **{wrong}** ({place})")
            if kind == "contamination" and sample:
                print(f"  - text: {sample}")

    if unparsed:
        print("\n## Files with no document number in the name\n")
        for path in unparsed:
            print(f"- `{path.name}`")


if __name__ == "__main__":
    main(sys.argv[1:] or ["."])
