/* Smoke test for viewer_v2.html. No browser, no dependency.
 *
 * The page is one script with no exports, so it is run here against a stub of
 * the few browser objects it touches. That is enough to answer the questions
 * that matter, and one of them can only be answered this way:
 *
 *   A branch that runs in ONE style is not exercised by opening the page in
 *   the other. `lit` was left behind in the Obsidian bloom after selection
 *   stopped dimming anything, and the labelled style never evaluated it. The
 *   page looked correct until the style was switched, and then every node
 *   disappeared, because draw() threw before it painted the first one.
 *
 * So draw() is run in every style, in every view state.
 *
 * Usage: node tools/check_viewer.js        (from the repository root)
 */

const fs = require("fs");
const path = require("path");

const PAGE = path.join(__dirname, "..", "viewer_v2.html");
const js = fs.readFileSync(PAGE, "utf8").split("<script>")[1].split("</script>")[0];

/* ---------- the smallest browser that will run the page ---------- */
const ctx = new Proxy({}, {
  get: (t, p) => (p === "measureText" ? () => ({ width: 40 }) : () => undefined),
  set: () => true,
});
const el = () => ({
  dataset: {}, style: {}, value: "20", checked: true, children: [],
  clientWidth: 1200, clientHeight: 800, tagName: "DIV",
  innerHTML: "", textContent: "", title: "", className: "",
  classList: { add() {}, remove() {}, toggle() {}, contains: () => false },
  addEventListener() {}, appendChild() {}, getContext: () => ctx,
  getBoundingClientRect: () => ({ left: 0, top: 0, width: 1200, height: 800 }),
  querySelector: () => el(), querySelectorAll: () => [], closest: () => null,
});
const byIdCache = {};
global.document = {
  documentElement: { dataset: {}, style: {} },
  getElementById: id => (byIdCache[id] || (byIdCache[id] = el())),
  createElement: el, addEventListener() {},
};
global.window = { addEventListener() {}, devicePixelRatio: 1, open() {} };
global.matchMedia = () => ({ addEventListener() {} });
global.getComputedStyle = () => ({ getPropertyValue: () => "#888888" });
global.requestAnimationFrame = () => 0;   // one frame, never a loop

new Function(js + `
  ;globalThis.P = {
    nodes, SPACES, SPACE_ORDER, byId, spaceNbrs, ringR, SPREAD,
    draw, resolve, settle, select, openSpace, openNode, leaveStage, easeCamera, pickSpace, readColors,
    setStyle(s) { style = s; readColors(); },
    get stage() { return stage; }, get zoom() { return zoom; },
    get look() { return look; }, get spin() { return spin; }, get selected() { return selected; },
    get VE() { return VE; },
  };`)();

const P = globalThis.P;
let failed = 0;
const ok = (pass, label, detail = "") => {
  if (!pass) failed++;
  console.log(`  ${pass ? "ok  " : "FAIL"}  ${label}${detail ? "  — " + detail : ""}`);
};
const settleCam = () => { let i = 0; while (P.easeCamera() && i++ < 4000); };

/* ---------- 1. the spaces hold ---------- */
console.log("\nspaces");
let outside = 0, stray = 0;
for (const n of P.nodes) {
  const own = P.SPACES[n.type];
  const d = Math.hypot(n.x - own.cx, n.y - own.cy, n.z - own.cz);
  if (d / own.r > 1.0001) outside++;
  for (const t of P.SPACE_ORDER) {
    if (t === n.type) continue;
    const s = P.SPACES[t];
    if (Math.hypot(n.x - s.cx, n.y - s.cy, n.z - s.cz) < d) { stray++; break; }
  }
}
ok(outside === 0, "every node is inside its own shell", `${outside} outside`);
ok(stray === 0, "no node sits closer to a foreign space", `${stray} strays`);
ok(P.VE.every(e => e.s.type === e.t.type), "no drawn link crosses a space");

/* ---------- 2. draw() survives every style in every state ---------- */
console.log("\ndraw()");
const states = [
  ["five spaces", () => P.leaveStage()],
  ["space open", () => P.openSpace("standard operating procedure")],
  ["node selected", () => { P.openSpace("form"); P.select("EXL-FM39"); }],
  ["space hidden", () => { P.leaveStage(); P.select(null); }],
];
for (const style of ["labelled", "obsidian"]) {
  P.setStyle(style);
  for (const [what, setup] of states) {
    let err = "";
    try { setup(); P.draw(); } catch (e) { err = `${e.constructor.name}: ${e.message}`; }
    ok(!err, `${style.padEnd(9)} ${what}`, err);
  }
  let err = "";
  try { P.resolve(120); } catch (e) { err = `${e.constructor.name}: ${e.message}`; }
  ok(!err, `${style.padEnd(9)} resolve() — the spring rules`, err);
}
P.setStyle("labelled");

/* ---------- 3. a node click is a space click ---------- */
console.log("\nclicks");
P.leaveStage(); settleCam();
P.openSpace("standard operating procedure"); settleCam();
const viaShell = { z: P.zoom, look: { ...P.look }, spin: P.spin, stage: P.stage };
P.leaveStage(); settleCam();
P.openNode(P.byId.get("EXL-SOP41")); settleCam();
const viaNode = { z: P.zoom, look: { ...P.look }, spin: P.spin, stage: P.stage };
ok(Math.abs(viaShell.z - viaNode.z) < 1e-9
   && ["x", "y", "z"].every(k => Math.abs(viaShell.look[k] - viaNode.look[k]) < 1e-9)
   && viaShell.spin === viaNode.spin && viaShell.stage === viaNode.stage,
   "a node click leaves the view where a shell click leaves it");
ok(P.selected === "EXL-SOP41", "the clicked document is still in the panel");

const s = P.SPACES[P.stage];
const p = { sx: 600, sy: 400 };   // the open space sits in the middle of the canvas
ok(P.pickSpace({ clientX: p.sx, clientY: p.sy }) === s, "a click inside the shell finds the space");

P.leaveStage(); settleCam();
ok(P.stage === null, "the background takes you back out");
ok(Math.abs(Math.hypot(s.cx, s.cy, s.cz) - P.ringR) < 1,
   "the space returns to the ring", `${Math.hypot(s.cx, s.cy, s.cz).toFixed(0)} vs ${P.ringR}`);

console.log(failed ? `\n${failed} failed\n` : "\nall passed\n");
process.exit(failed ? 1 : 0);
