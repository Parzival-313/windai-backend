// Generates tests/fixtures/turbine_classes_js.json from the frontend's own JavaScript.
//
// It cuts the `MODELS` + `powerKW` source out of frontend/AeolusAi.html, runs it in Node,
// and records MODELS plus powerKW at many speeds. The Python tests compare the API and
// app/physics/power.py against this file (design §12: "parity against fixtures produced
// by the frontend's JS"). The SHA-256 of the cut-out source is stored too, so a test fails
// if the frontend changes and this fixture is stale.
//
// Run from the repo root on the host (Node 18+), only when the frontend's turbine code changes:
//   node tests/fixtures/make_turbine_fixture.mjs
import { createHash } from "node:crypto";
import { readFileSync, writeFileSync } from "node:fs";

const START = "const MODELS = {";
const END = "function rotorRPM(";

const html = readFileSync("frontend/AeolusAi.html", "utf8").replace(/\r\n/g, "\n");
const i = html.indexOf(START);
const j = html.indexOf(END, i);
if (i < 0 || j < 0) throw new Error("MODELS / powerKW block not found in frontend/AeolusAi.html");
const source = html.slice(i, j);

const { MODELS, powerKW } = new Function(`${source}\nreturn { MODELS, powerKW };`)();

// 0–30 m/s every 0.25, plus values just around each threshold.
const speeds = new Set();
for (let k = 0; k <= 120; k++) speeds.add(k * 0.25);
for (const m of Object.values(MODELS)) {
  for (const t of [m.vin, m.vr, m.vout]) for (const d of [-1e-6, 0, 1e-6]) speeds.add(t + d);
}
speeds.add(-1);
const sorted = [...speeds].sort((a, b) => a - b);

const powerKw = {};
for (const [id, m] of Object.entries(MODELS)) {
  powerKw[id] = sorted.map((speed) => ({ speed, powerKw: powerKW(m, speed) }));
}

const fixture = {
  generatedBy: "tests/fixtures/make_turbine_fixture.mjs",
  source: "frontend/AeolusAi.html",
  sourceSha256: createHash("sha256").update(source, "utf8").digest("hex"),
  models: MODELS,
  powerKw,
};
writeFileSync("tests/fixtures/turbine_classes_js.json", JSON.stringify(fixture, null, 2) + "\n");
console.log(`wrote tests/fixtures/turbine_classes_js.json (${sorted.length} speeds × ${Object.keys(MODELS).length} classes)`);
