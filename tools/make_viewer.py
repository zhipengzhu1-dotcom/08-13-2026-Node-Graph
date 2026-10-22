"""Build the self-contained HTML viewers from graph.json.

Throwaway prototypes for ticket #8. The point is to decide how the viewer
should look and behave, not to be the viewer. Everything is inlined so a page
opens from the file system with no server and no network.

Two pages are built from the same graph:

  viewer.html      one space. Every node and every link in one volume.
  viewer_v2.html   five spaces, one per node type. Only the links that stay
                   inside a space are drawn. The rest wait.

Usage:  python3 tools/make_viewer.py
Writes: viewer.html, viewer_v2.html
"""

import json
from pathlib import Path

ROOT = Path(__file__).parent.parent
graph = json.loads((ROOT / "graph.json").read_text())

# Absolute paths so a click can open the real document in Word.
for node in graph["nodes"]:
    if node.get("folder") and node.get("file"):
        node["path"] = str(Path(node["folder"]).resolve() / node["file"])

BUILDS = [
    ("viewer_template.html", "viewer.html"),
    ("viewer_v2_template.html", "viewer_v2.html"),
]

blob = json.dumps(graph)
for template, page in BUILDS:
    out = ROOT / page
    out.write_text((ROOT / "tools" / template).read_text().replace("/*__GRAPH__*/null", blob))
    print(f"{len(graph['nodes'])} nodes, {len(graph['links'])} links -> {out}")
