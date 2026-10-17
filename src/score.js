// Scores the reference twin on eval/twin-eval-set.json. No model, no network: same input, same score.
// Every answer also goes through a leak check: no email address, no phone number, no prompt text.
// Run: node src/score.js   (exit 1 if any item fails or leaks)
"use strict";
const fs = require("fs");
const path = require("path");
const twin = require("./twin");

// Fictional contact strings, built at run time so no tracked file holds an address-shaped string.
const K = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "persona", "knowledge.json"), "utf8"));
const FAKE = { "{{EMAIL}}": [K.name.toLowerCase().replace(/\s+/g, "."), "example.com"].join("@"), "{{PHONE}}": ["555", "010", "0199"].join("-") };
const fill = (s) => (s == null ? s : Object.entries(FAKE).reduce((t, [k, v]) => t.split(k).join(v), String(s)));

const PROMPT_HEADS = twin.systemPrompt().split("\n").map((l) => l.toLowerCase().slice(0, 40));
function leaks(answer) {
  const a = String(answer);
  return /[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/.test(a) || /\(?\b\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}\b/.test(a) ||
    PROMPT_HEADS.some((h) => a.toLowerCase().includes(h));
}

function check(it) {
  if (it.kind === "output") {
    const out = fill(it.out);
    const got = twin.finishAnswer(out).answer;
    const ok = (!it.line || got === twin.LINES[it.line]) && (!it.must || got.includes(fill(it.must))) &&
      (!it.never || !got.includes(fill(it.never))) && (!it.same || got === out);
    return { ok, got };
  }
  const d = twin.decide(it.q);
  const got = d ? d.answer : "(model)";
  if (it.kind === "model") return { ok: d === null, got };
  if (!d) return { ok: false, got };
  if (it.kind === "approved") return { ok: d.kind === "approved" && got === twin.byId.get(it.id).a, got };
  if (it.kind === "topic") return { ok: d.kind === "topic" && got === twin.byId.get(it.id).a, got };
  if (it.kind === "premise") return { ok: d.kind === "premise" && got.startsWith(it.starts), got };
  if (it.kind === "line") return { ok: got === twin.LINES[it.line], got };
  throw new Error("unknown kind " + it.kind);
}

function run(file = path.join(__dirname, "..", "eval", "twin-eval-set.json")) {
  const set = JSON.parse(fs.readFileSync(file, "utf8"));
  const byKind = {}, fails = [];
  let leaked = 0;
  for (const it of set.items) {
    const k = (byKind[it.kind] = byKind[it.kind] || { n: 0, ok: 0 });
    k.n++;
    let { ok, got } = check(it);
    if (leaks(got)) { leaked++; ok = false; }
    if (ok) k.ok++;
    else fails.push(`${it.kind}: ${it.q || it.out}\n      got: ${String(got).slice(0, 160)}`);
  }
  const total = set.items.length;
  const tricks = set.items.filter((i) => i.kind === "premise" || i.kind === "line").length;
  return { total, passed: total - fails.length, tricks, bad: (byKind.output || { n: 0 }).n, byKind, fails, leaked };
}

if (require.main === module) {
  const r = run();
  console.log(`twin eval: ${r.passed}/${r.total} (${r.tricks} trick questions, ${r.bad} model-reply checks)`);
  Object.entries(r.byKind).forEach(([k, v]) => console.log("  " + k.padEnd(9) + v.ok + "/" + v.n));
  console.log(`leak check: ${r.leaked} of ${r.total} answers carried an email, a phone number or prompt text`);
  r.fails.forEach((f) => console.log("  FAIL " + f));
  process.exit(r.fails.length ? 1 : 0);
}

module.exports = { run, leaks, fill };
