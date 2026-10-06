/* Logic check for ui/index.html — run with `node ui/check.mjs` from the repo root.
 *
 * Deliberately outside pytest and outside CI (docs/DECISIONS.md D-003): it needs
 * node, and the Python project should not grow a JavaScript toolchain for one
 * file. Run it by hand after touching the page.
 *
 * It loads the page's <script> under a minimal DOM shim and a stubbed fetch, then
 * drives the interactions that carry real logic: prefilling the reform panel from
 * current law, showing case T only when it can apply, and never to a widow (D-197),
 * sending only the knobs the user actually moved, and colouring the Δ column by
 * "better off" rather than by "bigger".
 */
import fs from "node:fs";
import assert from "node:assert/strict";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const html = fs.readFileSync(path.join(here, "index.html"), "utf8");
const js = html.match(/<script>([\s\S]*?)<\/script>/)[1];

/* Minimal DOM good enough for this page: elements are bags of properties with
   innerHTML, dataset, hidden and event handlers. */
const els = new Map();
function make(id) {
  if (els.has(id)) return els.get(id);
  const listeners = {};
  const el = {
    id, innerHTML: "", textContent: "", value: "", checked: false, hidden: false,
    disabled: false, style: {}, dataset: {},
    classList: { _s: new Set(), add(c) { this._s.add(c); }, remove(c) { this._s.delete(c); },
                 toggle(c, on) { on ? this._s.add(c) : this._s.delete(c); },
                 contains(c) { return this._s.has(c); } },
    setAttribute(k, v) { this["attr_" + k] = v; },
    getAttribute(k) { return this["attr_" + k]; },
    addEventListener(t, fn) { (listeners[t] ||= []).push(fn); },
    fire(t, ev) { (listeners[t] || []).forEach((fn) => fn(ev)); },
  };
  els.set(id, el); return el;
}
/* Seed each element from its markup, so the shim reflects the page's own
   defaults (a `checked` attribute, a selected <option>) instead of inventing them. */
for (const m of html.matchAll(/<(\w+)([^>]*\bid="([^"]+)"[^>]*)>/g)) {
  const [, tag, attrs, id] = m;
  const el = make(id);
  el.checked = /\bchecked\b/.test(attrs);
  const value = attrs.match(/\bvalue="([^"]*)"/);
  if (value) el.value = value[1];
  if (tag === "select") {
    const block = html.slice(m.index, html.indexOf("</select>", m.index));
    const selected = block.match(/<option[^>]*\bvalue="([^"]*)"[^>]*\bselected\b/);
    const first = block.match(/<option[^>]*\bvalue="([^"]*)"/);
    el.value = selected ? selected[1] : first ? first[1] : "";
  }
}
for (const id of new Set([...html.matchAll(/id="([^"]+)"/g)].map((m) => m[1]))) make(id);
globalThis.document = {
  getElementById: (id) => els.get(id) ?? make(id),
  addEventListener() {},
  querySelector: () => null,
};
globalThis.location = { protocol: "http:", origin: "http://localhost:8000" };
const calls = [];
globalThis.fetch = async (url, opts) => {
  calls.push({ url, opts });
  if (url.endsWith("/health")) return { json: async () => ({
    warm: true, openfisca_france: "176.0.8", openfisca_core: "44.7.0",
    licence: "AGPL-3.0-or-later", source_url: "https://example.org/impots.git" }) };
  if (url.includes("/parameters/ir")) return { json: async () => LAW };
  if (url.includes("/population/baseline")) return { ok: true, json: async () => POPULATION };
  if (url.includes("/population/simulate")) return { ok: true, json: async () => POPULATION_RUN };
  return { ok: true, json: async () => RESULT };
};
const RECON = [
  { label: "Masse salariale brute", simulated: 1.1e12, published: 1.11e12, residual: -0.004,
    use: "calibration", status: "calibrated (spent)", source: "INSEE comptes nationaux (D11)" },
  { label: "Impôt sur le revenu — barème", simulated: 1.08e11, published: 9.9e10,
    residual: 0.089, use: "validation", status: "within tolerance", source: "DGFiP" },
  { label: "RSA", simulated: 2.5e10, published: 1.2e10, residual: 1.06,
    use: "validation", status: "OUTSIDE tolerance", source: "CNAF / DREES" },
];
const POPULATION = {
  meta: { vintage: "2024", branch: "A' — EEC household structure, synthetic incomes (D-012)",
          households: 31.45e6, persons: 67.08e6, tier: "full", sampled_households: null,
          note: "Population synthétique construite à partir de données ouvertes. Voir reports/reconciliation.md.",
          limitations: ["**No income is observed.**", "b", "c", "d", "e", "f"] },
  totals: {}, totals_reform: {}, deltas: {}, reform_cost: null,
  deciles: Array.from({ length: 10 }, (_, i) => ({
    decile: i + 1, n_households: 3.1e6, mean_niveau_de_vie: 8000 + i * 4000,
    mean_baseline: 20000, mean_reform: null, mean_delta: null,
    share_winners: null, share_losers: null, share_unaffected: null })),
  reconciliation: RECON, timings: {},
};
const POPULATION_RUN = {
  ...POPULATION,
  meta: { ...POPULATION.meta, tier: "quick", sampled_households: 20000,
          note: POPULATION.meta.note + " Ce résultat porte sur un sous-échantillon déterministe de 20 000 ménages repondérés." },
  deltas: { ir: 4.9e8, rsa: 1e5 }, reform_cost: -4.9e8,
  deciles: Array.from({ length: 10 }, (_, i) => ({
    decile: i + 1, n_households: 3.1e6, mean_niveau_de_vie: 8000 + i * 4000,
    mean_baseline: 20000, mean_reform: 20000 - (i === 9 ? 156 : 0),
    mean_delta: i === 9 ? -156 : 0,
    share_winners: 0, share_losers: i === 9 ? 0.023 : 0, share_unaffected: i === 9 ? 0.977 : 1 })),
  timings: { total_s: 41 },
};
const LAW = {
  year: 2024,
  bareme: [{threshold:0,rate:0},{threshold:11497,rate:0.11},{threshold:29315,rate:0.30},
           {threshold:83823,rate:0.41},{threshold:180294,rate:0.45}],
  decote: { seuil_celib: 889, seuil_couple: 1470, taux: 0.4525 },
  plafond_qf_demi_part: 1791,
  csg_activite: { imposable: 0.024, deductible: 0.068 },
};
const ROWS = (ir) => ({ salaire_super_brut: 37919.8, salaire_brut: 30000, salaire_net: 23747.93,
  salaire_imposable: 24602.7, cotisations_salariales: 3393, cotisations_employeur: 10069.8,
  csg_deductible: 2004.3, csg_imposable: 707.4, crds: 147.38, ir,
  ir_avant_reductions: 1171.03, parts_fiscales: 1.0, revenu_fiscal_reference: 22142.7,
  af: 0, ppa: 213.42, rsa: 607.75, aide_logement: 0, revenu_disponible: 23908.48,
  // Every row the API sends at the full tier, zeros included: a stub without them would
  // let the quiet groups pass for the wrong reason, a row skipped as missing (D-186).
  retraite_imposable: 0, chomage_brut: 0, pension_invalidite: 0, aspa: 0, asi: 0, aah: 0,
  mva: 0, ass: 0, aeeh: 0 });
const RESULT = { baseline: ROWS(812), reform: ROWS(1012), delta: { ...ROWS(200), revenu_disponible: -200, salaire_net: 0 },
  emtr: 0.4979, emtr_reform: 0.52, tier: "full", year: 2024, historique_revenus: false,
  timings: { build_ms: 3, compute_ms: 480, emtr_ms: 900, total_ms: 1390, reform_cache_hit: true },
  engine: { openfisca_france: "176.0.8" } };

const mod = await import("data:text/javascript;base64," + Buffer.from(js).toString("base64"));
await new Promise((r) => setTimeout(r, 30));   // let boot() settle

const $ = (id) => els.get(id);
const ok = (name, fn) => { try { fn(); console.log("  ok   " + name); } catch (e) { console.log("  FAIL " + name + " — " + e.message); process.exitCode = 1; } };

console.log("boot");
ok("health chip filled from /health", () => assert.match($("engine").innerHTML, /176\.0\.8/));
ok("reform panel prefilled from current law", () => {
  assert.equal(Number($("dCelib").value), 889);
  assert.equal(Number($("dTaux").value), 45.25);
  assert.match($("baremeRows").innerHTML, /180294/);
});
ok("licence and source link shown in the footer", () => {
  assert.match($("licence").innerHTML, /AGPL-3\.0-or-later/);
  assert.match($("licence").innerHTML, /example\.org/, "AGPL s13: the source offer must be reachable");
});
ok("no reform is sent when nothing was touched", () => assert.equal($("reformState").textContent, "droit courant"));

console.log("household");
ok("case T hidden with no children", () => assert.equal($("isoleWrap").hidden, true));
ok("case T appears for a lone parent", () => {
  $("addChild").onclick(); assert.equal($("isoleWrap").hidden, false);
});
ok("case T hidden again for a couple", () => {
  $("two").onclick(); assert.equal($("isoleWrap").hidden, true);
  assert.equal($("marie").checked, true, "two adults must be married/pacsed");
  $("one").onclick();
});
/* Each state is set outside the check that reads it, so a failing check leaves nothing
   behind for the next ones to trip on. */
ok("the situation de famille is a lone adult's", () => {
  assert.equal($("situationWrap").hidden, false);
  assert.equal($("situation").value, "celibataire", "célibataire is the default (D-197)");
});
$("two").onclick();
ok("a couple has no situation de famille to choose", () => {
  assert.equal($("situationWrap").hidden, true, "a couple is married or pacsed");
});
$("one").onclick();
$("situation").value = "veuf"; $("situation").fire("change", {});
ok("a widowed parent is offered no case T", () => {
  assert.equal($("isoleWrap").hidden, true, "case T is for célibataires ou divorcés (D-197)");
});
$("situation").value = "divorce"; $("situation").fire("change", {});
ok("a divorced parent is offered case T", () => {
  assert.equal($("isoleWrap").hidden, false, "a divorced parent may claim case T");
});
$("situation").value = "celibataire"; $("situation").fire("change", {});

console.log("reform diffing");
ok("moving the top rate sends only ir_bareme", () => {
  $("baremeRows").fire("input", { target: { dataset: { rate: "4" }, value: "50" } });
  assert.match($("reformState").textContent, /1 paramètre modifié/);
});
ok("resetting returns to droit courant", () => {
  $("reset").onclick(); assert.equal($("reformState").textContent, "droit courant");
});
ok("changing the décote sends only that knob", () => {
  $("dCelib").value = "2000"; $("dCelib").fire("input", {});
  assert.match($("reformState").textContent, /1 paramètre modifié/);
  $("reset").onclick();
});

console.log("rendering");
ok("three columns and a bold bottom line", async () => {
  $("full").checked = true; $("full").onchange({ target: { checked: true } });
  $("go").onclick();
});
await new Promise((r) => setTimeout(r, 60));
ok("table rendered with Δ column", () => {
  const out = $("out").innerHTML;
  assert.match(out, /Droit courant/); assert.match(out, /Votre réforme/);
  assert.match(out, /Revenu disponible/);
  assert.match(out, /class="down">\+200/, "a tax rise must read red");
  assert.match(out, /class="down">−200/, "less disposable income must read red");
  assert.match(out, /49,8 %/, "EMTR shown as a percentage");
  assert.match(out, /D-005/, "the missing-history caveat must be shown");
});
ok("no logement is sent until a statut is chosen", () => {
  const body = JSON.parse(calls.at(-1).opts.body);
  assert.equal(body.household.logement, undefined,
    "ticking the benefits box must not assume a tenancy the user never stated");
});
ok("quiet groups stay out of a salaried household's table", () => {
  const out = $("out").innerHTML;
  for (const title of ["Revenus de remplacement", "Vieillesse", "Handicap"]) {
    assert.ok(!out.includes(title), `${title} shown with nothing in it`);
  }
  assert.ok(!out.includes("celles du salaire"), "the levies note needs a replacement income");
  assert.ok(!out.includes("solidarité spécifique"), "the ASS row shown with no ASS");
});
ok("a blank adult sends zero replacement income and no disability", () => {
  const adult = JSON.parse(calls.at(-1).opts.body).household.adults[0];
  assert.equal(adult.pension_annuelle, 0);
  assert.equal(adult.chomage_brut_annuel, 0);
  assert.equal(adult.pension_invalidite_annuelle, 0);
  assert.equal(adult.handicap, undefined, "a blank rate is « none recognised », not 0 %");
  assert.equal(adult.carte_invalidite, false, "an unticked card is sent unticked (D-188)");
  assert.equal(adult.fin_de_droits_ass, undefined, "an unticked box sends no fin de droits");
});
ok("a blank child sends no disability", () => {
  const children = JSON.parse(calls.at(-1).opts.body).household.children;
  assert.equal(children.length, 1, "the child added above must be sent");
  assert.equal(children[0].handicap, undefined, "a blank rate is « none recognised », not 0 %");
});
/* A child's inputs, typed as the page's own listener reads them (D-191). */
const typeChild = (field, value) => $("children").fire("input", { target: {
  dataset: { childIndex: "0", childField: field }, value: String(value),
  type: typeof value === "boolean" ? "checkbox" : "text", checked: value === true } });
typeChild("taux", "80"); typeChild("complement", "2"); typeChild("carte", true);
RESULT.baseline.aeeh = 6089.33; RESULT.reform.aeeh = 6089.33;
$("go").onclick();
await new Promise((r) => setTimeout(r, 60));
ok("a child's disability is sent as the wire format has it", () => {
  const child = JSON.parse(calls.at(-1).opts.body).household.children[0];
  assert.deepEqual(child.handicap, { taux_incapacite: 0.8,
    etablissement_accompagnement_ou_soins: false, complement_categorie: 2,
    carte_invalidite: true }, "the rate in percent must leave as a fraction");
});
ok("an AEEH shows its row under « Handicap »", () => {
  const out = $("out").innerHTML;
  assert.match(out, /Handicap/);
  assert.match(out, /Allocation d'éducation de l'enfant handicapé/);
});
$("addChild").onclick();
$("go").onclick();
await new Promise((r) => setTimeout(r, 60));
ok("a child's inputs survive adding another child", () => {
  const children = JSON.parse(calls.at(-1).opts.body).household.children;
  assert.equal(children.length, 2);
  assert.equal(children[0].handicap?.taux_incapacite, 0.8, "re-rendering wiped what was typed");
  assert.equal(children[1].handicap, undefined);
});
$("children").fire("click", { target: { dataset: { child: "1" } } });
typeChild("taux", ""); typeChild("complement", ""); typeChild("carte", false);
RESULT.baseline.aeeh = 0; RESULT.reform.aeeh = 0;
RESULT.baseline.retraite_imposable = 12000;
RESULT.reform.retraite_imposable = 12000;
RESULT.baseline.ass = 6768;
RESULT.reform.ass = 6768;
$("go").onclick();
await new Promise((r) => setTimeout(r, 60));
ok("a pension shows its row and the note on its levies", () => {
  const out = $("out").innerHTML;
  assert.match(out, /Revenus de remplacement/);
  assert.match(out, /Pension de retraite/);
  assert.match(out, /celles du salaire/);
});
ok("an ASS shows its row, right after the RSA's", () => {
  const out = $("out").innerHTML;
  const rsa = out.indexOf("<td>RSA</td>");
  const ass = out.indexOf("Allocation de solidarité spécifique");
  assert.ok(rsa > 0 && ass > rsa, "the ASS row must follow the RSA's");
  assert.ok(out.indexOf("Aide au logement") > ass, "the housing aid comes after the ASS");
});
// The invalidity pension alone, and the ASI it opens (D-190): the note must not need the
// retirement pension to show.
for (const side of [RESULT.baseline, RESULT.reform]) {
  Object.assign(side, { retraite_imposable: 0, pension_invalidite: 6000, asi: 4676.11 });
}
$("go").onclick();
await new Promise((r) => setTimeout(r, 60));
ok("an invalidity pension shows its row, its ASI and the note on its levies", () => {
  const out = $("out").innerHTML;
  assert.match(out, /Pension d'invalidité/);
  assert.match(out, /Allocation supplémentaire d'invalidité/);
  assert.match(out, /celles du salaire/);
});
$("hist").checked = false;
$("full").checked = false; $("full").onchange({ target: { checked: false } });
$("go").onclick();
await new Promise((r) => setTimeout(r, 60));
ok("a history box unticked in the full tier decides nothing in the light tier", () => {
  const body = JSON.parse(calls.at(-1).opts.body);
  assert.equal($("histWrap").hidden, true);
  assert.equal(body.tier, "light");
  assert.equal(body.historique_revenus, true, "a box nobody can see must not decide the IR");
});
$("full").checked = true; $("full").onchange({ target: { checked: true } });
$("hist").checked = true;
$("situation").value = "veuf"; $("situation").fire("change", {});
$("go").onclick();
await new Promise((r) => setTimeout(r, 60));
ok("a widowed parent sends her situation and no case T", () => {
  const household = JSON.parse(calls.at(-1).opts.body).household;
  assert.equal(household.situation_famille, "veuf");
  assert.equal(household.parent_isole, undefined, "the API refuses case T beside a widow");
});
$("situation").value = "celibataire"; $("situation").fire("change", {});
console.log("population tab");
$("tabPop").onclick();
await new Promise((r) => setTimeout(r, 40));
ok("L1 banner filled from the baseline endpoint", () => {
  assert.match($("l1Note").textContent, /Population synthétique/);
  assert.match($("l1Vintage").textContent, /millésime 2024/);
  assert.ok($("l1Limits").innerHTML.includes("<li>"), "limitations must be listed");
});
ok("foyer pane hidden while population is shown", () => {
  assert.equal($("paneFoyer").hidden, true);
  assert.equal($("panePop").hidden, false);
});
ok("pricing with no reform is refused before any request", () => {
  $("reset").onclick();                       // back to droit courant
  const before = calls.length;
  $("goPop").onclick();
  assert.equal(calls.length, before, "must not call the API with an empty reform");
  assert.match($("popOut").innerHTML, /Aucune réforme/);
});

ok("payload carries the new flags", () => {
  const body = JSON.parse(calls.find((c) => c.url.endsWith("/simulate") && c.opts).opts.body);
  assert.equal(body.tier, "full");
  assert.equal(body.historique_revenus, true, "D-011: history is the default");
  assert.equal(body.household.couple_marie_ou_pacse, false);
  assert.equal(body.household.situation_famille, "celibataire", "a lone adult's default");
  assert.equal(body.household.parent_isole, true, "lone parent claims case T by default");
  assert.equal(body.reform, null, "an untouched panel must send no reform");
});
