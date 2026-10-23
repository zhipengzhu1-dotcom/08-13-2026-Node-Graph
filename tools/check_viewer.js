/* Smoke test for viewer_v2.html (and viewer.html). No browser, no dependency.
 *
 * The page is one script with no exports, so it is run here against a stub of
 * the few browser objects it touches. That is enough to answer the questions
 * that matter, and one of them can only be answered this way:
 *
 *   A branch that runs in ONE style is not exercised by opening the page in
 *   the other. `lit` was left behind in the Obsidian bloom after selection
 *   stopped dimming anything, and the light style (then "labelled", now
 *   "paper") never evaluated it. The page looked correct until the style was
 *   switched, and then every node disappeared, because draw() threw before it
 *   painted the first one.
 *
 * So draw() is run in every style, in every view state, including the
 * states that only exist mid-animation: a camera in flight, a selection ring
 * still closing in, a hovered node, and reduced motion.
 *
 * Motion is checked too: a second click mid-flight must bend the move
 * towards the new space without a jump, and reduced motion must arrive at
 * once.
 *
 * viewer.html, the single-space page, is run the same way at the end.
 *
 * Usage: node tools/check_viewer.js        (from the repository root)
 */

const fs = require("fs");
const path = require("path");

const PAGE = path.join(__dirname, "..", "viewer_v2.html");
const js = fs.readFileSync(PAGE, "utf8").split("<script>")[1].split("</script>")[0];

/* ---------- the smallest browser that will run the page ---------- */
const gradient = { addColorStop() {} };
const ctx = new Proxy({}, {
  get: (t, p) => (p === "measureText" ? () => ({ width: 40 })
                : p === "createRadialGradient" || p === "createLinearGradient" ? () => gradient
                : () => undefined),
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
  documentElement: { dataset: {}, style: {} }, body: el(),
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
    setHover(id) { hovered = id; }, setReduced(on) { reduced = on; },
    get SPIN_ON() { return spin; },
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
  ["camera in flight", () => { P.leaveStage(); for (let i = 0; i < 8; i++) P.easeCamera(); P.openSpace("form"); P.easeCamera(); }],
  ["node selected", () => { P.openSpace("form"); P.select("EXL-FM39"); }],
  ["node hovered", () => { P.setHover("EXL-FM39"); }],
  ["space hidden", () => { P.setHover(null); P.leaveStage(); P.select(null); }],
  ["reduced motion", () => { P.setReduced(true); P.openSpace("instrument"); P.select(P.SPACES.instrument.members[0].id); }],
  ["keyboard escape", () => { P.setReduced(false); P.leaveStage("key"); }],
];
for (const style of ["paper", "obsidian"]) {
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
P.setStyle("paper");

/* ---------- 3. motion ---------- */
console.log("\nmotion");
P.leaveStage("key");
ok(!P.easeCamera(), "a keyboard action arrives at once");
const sop = P.SPACES["standard operating procedure"], form = P.SPACES.form;
const at = s => ({ x: s.cx, y: s.cy, z: s.cz });
P.openSpace("standard operating procedure");
let prev = at(sop);
for (let i = 0; i < 6; i++) { prev = at(sop); P.easeCamera(); }
const mid = at(sop);
ok(Math.hypot(mid.x, mid.y, mid.z) > 1 && Math.hypot(mid.x, mid.y, mid.z) < P.ringR - 1,
   "a space is caught mid-flight");
// Interrupt: open another space before the first one has arrived. The SOP
// space now has to go back out, but it carries its speed into the turn: the
// first step after the click still points the way it was going and is no
// bigger than the last step before it. An easing that restarts from the
// current position would reverse at once, which reads as a jolt.
const vb = { x: mid.x - prev.x, y: mid.y - prev.y, z: mid.z - prev.z };
P.openSpace("form");
P.easeCamera();
const cur = at(sop);
const va = { x: cur.x - mid.x, y: cur.y - mid.y, z: cur.z - mid.z };
const len = v => Math.hypot(v.x, v.y, v.z);
const cos = (va.x * vb.x + va.y * vb.y + va.z * vb.z) / (len(va) * len(vb) || 1);
ok(cos > 0.9 && len(va) <= len(vb) * 1.05, "a second click bends the move without a jump",
   `step ${len(vb).toFixed(1)} before, ${len(va).toFixed(1)} after, same heading ${cos.toFixed(2)}`);
settleCam();
ok(P.stage === "form" && Math.hypot(form.cx, form.cy, form.cz) < 1e-9, "the second space ends in the middle");
ok(Math.abs(Math.hypot(sop.cx, sop.cy, sop.cz) - P.ringR * P.SPREAD) < 1,
   "the first space ends out of the way");
P.setReduced(true);
P.leaveStage();
ok(!P.easeCamera(), "reduced motion arrives at once");
P.setReduced(false);

/* ---------- 4. a node click is a space click ---------- */
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

/* ---------- 5. the single-space viewer draws in both styles ---------- */
console.log("\nviewer.html");
const js1 = fs.readFileSync(path.join(__dirname, "..", "viewer.html"), "utf8")
  .split("<script>")[1].split("</script>")[0];
new Function(js1 + `
  ;globalThis.P1 = { draw, select, nodes, readColors, setStyle(s) { style = s; readColors(); },
    setHover(id) { hovered = id; }, setReduced(on) { reduced = on; } };`)();
const P1 = globalThis.P1;
for (const style of ["paper", "obsidian"]) {
  P1.setStyle(style);
  for (const [what, setup] of [
    ["nothing selected", () => P1.select(null)],
    ["node selected", () => P1.select("EXL-SOP41")],
    ["node hovered", () => P1.setHover("EXL-FM39")],
    ["selection fading out", () => { P1.setHover(null); P1.select(null); }],
    ["reduced motion", () => { P1.setReduced(true); P1.select("EXL-SOP41"); P1.setReduced(false); }],
  ]) {
    let err = "";
    try { setup(); P1.draw(); } catch (e) { err = `${e.constructor.name}: ${e.message}`; }
    ok(!err, `${style.padEnd(9)} ${what}`, err);
  }
}

console.log(failed ? `\n${failed} failed\n` : "\nall passed\n");
process.exit(failed ? 1 : 0);
