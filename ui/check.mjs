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
  if (url.includes("/predictif/simulate")) {
    const body = JSON.parse(opts.body);
    const both = body.macro && body.horizon > 3 && !body.persistence;
    return { ok: true, json: async () => (both ? PRED_SIDE : PRED_RESULT) };
  }
  if (url.endsWith("/explorations")) return { ok: true, json: async () => ({ explorations: ["csg", "illisible"] }) };
  if (url.includes("/explorations/illisible")) return { ok: false, status: 500, json: async () => ({
    detail: "exploration « illisible » illisible, refusée plutôt que montrée en partie : candidat sans verdict θ" }) };
  if (url.includes("/explorations/")) return { ok: true, json: async () => EXPL_REPORT };
  if (url.endsWith("/predictif")) return { ok: true, json: async () => ({ rapports: ["plf2027_art_3"] }) };
  if (url.includes("/predictif/")) return { ok: true, json: async () => PRED_REPORT };
  return { ok: true, json: async () => RESULT };
};
/* Phase 9 · the debt path, fast and precomputed. Three years, the last two carried. */
const PRED_NAMES = { spending_name: "Dépenses gelées en volume",
  growth_name: "Croissance réelle 1 %, prix 2 %",
  rate_name: "Taux implicite tenu à son niveau de 2025" };
const PRED_RESULT = { ...PRED_NAMES, years: [2026, 2027, 2028],
  reference: [1.1686, 1.1747, 1.1754], reform: [1.1669, 1.1713, 1.1703],
  delta: [-0.0017, -0.0034, -0.0050], priced_years: [2026], carried_years: [2027, 2028],
  conventions: ["Prélèvements constants en % du PIB",
                "Δ tenu en part de PIB constante au-delà de la dernière année chiffrée (convention, pas un chiffrage)"],
  absent: { "rétroaction": "Retour du PIB sur les recettes non demandé. Absent, pas nul." },
  delta_mechanical: [-0.0018, -0.0036, -0.0053],
  theta: { eti_all: 0.5, employment_elasticity_smic: 0.5 }, theta_applied: true,
  closed: { dividendes: "la population ne porte aucun revenu du capital (§6.5)." },
  slices: [{ source: "bande", computed: true, reason: "",
             label: "Boîte θ du comportement : chaque effet revendiqué n'importe où",
             low: [1.1665, 1.1705, 1.1690], high: [1.1672, 1.1719, 1.1712] },
           { source: "eventail", computed: true, reason: "",
             label: "Éventail macro : θ du multiplicateur de 0 à 1",
             low: [1.1664, 1.1700, 1.1680], high: [1.1675, 1.1725, 1.1720] }],
  gdp_gap: [0.0007, 0.0014, 0.0015], persistence: null,
  indices: [
    { key: "emploi_smic", pour: "Les gens", label: "Emploi au voisinage du SMIC",
      unit: "emplois", stage: "comportement", source: "C2",
      theta: ["employment_elasticity_smic"], available: true, values: { 2026: 12000 },
      box: { 2026: [8000, 15000] }, reason: "", conventions: [], uncovered: {},
      note: "Des personnes. Ne s'additionne pas à l'emploi de Mésange." },
    { key: "emploi_marchand", pour: "Les gens", label: "Emploi salarié marchand",
      unit: "milliers d'ETP", stage: "macro", source: "Mésange",
      theta: ["multiplicateur_macro"], available: true, values: { 1: 3.9, 2: 17.6 },
      box: { 1: [2.1, 5.6], 2: [9.5, 25.7] }, reason: "", conventions: [], uncovered: {},
      note: "Des équivalents temps plein. Ne s'additionne pas à l'emploi de C2." },
    { key: "revenu_disponible_reel", pour: "Les gens", label: "Revenu disponible brut réel",
      unit: "% d'écart", stage: "macro", source: "Mésange, au centre", theta: [],
      available: true, values: { 1: 0.275 }, box: null, reason: "", conventions: [],
      uncovered: {}, note: "" },
    { key: "depense_rd", pour: "Les entreprises", label: "Dépense de R&D",
      unit: "EUR de R&D", stage: "couche entreprises", source: "C9", theta: [],
      available: false, values: {}, box: null, conventions: [], uncovered: {}, note: "",
      reason: "Couche entreprises (`/entreprises/simulate`) : la trajectoire chiffre les réformes de la population." },
    { key: "dette", pour: "L'État", label: "Dette, écart de la réforme", unit: "pts de PIB",
      stage: "chaîne", source: "chaîne de §3", theta: [], available: true,
      values: { 2026: -0.0017 }, box: null, reason: "", conventions: [], uncovered: {},
      note: "" }],
  population_view: "vieillie",
  population_note: "Sous-échantillon de 20 000 ménages repondérés. Vue « vieillie » : l'année "
    + "2026 est chiffrée avec sa législation sur la population 2024 vieillie jusqu'à elle, "
    + "la vue de tête de la commande `impots predictif` (D-216, D-226) ; la vue « figée », "
    + "que la commande donne à côté, n'est pas chiffrée ici. Population vieillie "
    + "mécaniquement de 2024 à 2026 — salaires 3,0 % par an, prix 2,0 % par an, hypothèses "
    + "DÉCLARÉES et non prévues (INSEE & DARES, 3 % ronds). **Cette population n'est plus "
    + "calibrée** : les totaux dépensés au registre le sont sur l'année de base.",
  banner: "Prédictif conditionnel : ce n'est pas une prévision.",
  debt_banner: "Les dépenses publiques (~57 % du PIB) ne sont PAS microsimulées ici." };
/* D-230 · past three years with the loop and no persistence named, both scenarios side
   by side and no path of the response's own. */
const PRED_PATH = (persistence, label, delta, gap, convention) => ({
  persistence, label, reform: delta.map((v, i) => 1.17 + v), delta,
  delta_primary: delta.map(() => -0.0015),
  slices: [{ source: "eventail", computed: true, reason: "",
             label: "Éventail macro : θ du multiplicateur de 0 à 1",
             low: delta.map((v) => 1.169 + v), high: delta.map((v) => 1.171 + v) }],
  conventions: ["Prélèvements constants en % du PIB", convention], gdp_gap: gap,
  feedback_primary: gap.map((g) => g / 2),
  indices: [{ key: "dette", pour: "L'État", label: "Dette, écart de la réforme",
              unit: "pts de PIB", stage: "chaîne", source: "chaîne de §3", theta: [],
              available: true, values: { 2030: delta[4] }, box: null, reason: "",
              conventions: [], uncovered: {}, note: "" }] });
const PRED_SIDE = { ...PRED_RESULT, years: [2026, 2027, 2028, 2029, 2030],
  reference: [1.1686, 1.1747, 1.1754, 1.1708, 1.1610], reform: null, delta: null,
  delta_primary: null, delta_mechanical: [0.0016, 0.0031, 0.0047, 0.0062, 0.0077],
  priced_years: [2026], carried_years: [2027, 2028, 2029, 2030], slices: [],
  gdp_gap: null, feedback_primary: null, persistence: null,
  conventions: ["Prélèvements constants en % du PIB"],
  theta: { eti_all: 0.5, multiplicateur_macro: 0.5 },
  indices: [{ key: "dette", pour: "L'État", label: "Dette, écart de la réforme",
              unit: "pts de PIB", stage: "chaîne", source: "chaîne de §3", theta: [],
              available: false, values: {}, box: null, conventions: [], uncovered: {},
              note: "", reason: "une valeur par scénario de persistance, donnée avec chacun des deux, côte à côte" }],
  side_by_side: [
    PRED_PATH("eteint", "Effet macro éteint après trois ans",
              [0.0005, 0.0005, 0.0010, 0.0042, 0.0057], [0.0006, 0.0013, 0.0014, 0, 0],
              "Au-delà de trois ans : Effet macro éteint après trois ans."),
    PRED_PATH("tenu", "Effet macro tenu au niveau de la troisième année",
              [0.0005, 0.0005, 0.0010, 0.0016, 0.0023],
              [0.0006, 0.0013, 0.0014, 0.0014, 0.0014],
              "Au-delà de trois ans : Effet macro tenu au niveau de la troisième année.")] };
const PRED_REPORT = { ...PRED_NAMES, scenario: "plf2027_art_3", titre: "PLF 2027, art. 3",
  reference: "reconduit", source: "PLF 2027", computed: "2026-10-16",
  years: [{ year: 2026, basis: "legislated", mechanical_frozen_eur: -1.2e9,
            mechanical_aged_eur: -1.3e9, reference: 1.1686, reform_aged: 1.1682,
            delta_aged: -0.0004, reform_frozen: 1.1683, delta_frozen: -0.0003 }],
  conventions: ["Prélèvements constants en % du PIB"],
  absent: { "rétroaction": "non demandé" }, uprating_note: "Population vieillie.",
  theta: { eti_all: 0.3 }, theta_applied: false,
  closed: { dividendes: "la population ne porte aucun revenu du capital (§6.5)." },
  banner: "Prédictif conditionnel : ce n'est pas une prévision.",
  debt_banner: "Les dépenses publiques ne sont PAS microsimulées ici." };
/* Phase 10 · a search, as `impots exploration` writes it (D-235): under « éteint » no bundle
   meets the target, under « tenu » one is robust, one depends on θ, one holds only on the
   frozen population. */
const EXPL_EVAL = (rate, cost, aged, frozen, low, high) => ({
  knobs: { csg_activite_deductible: rate }, cost_aged_eur: cost, cost_frozen_eur: cost * 0.95,
  delta_aged: aged, delta_frozen: frozen, corner_low: low, corner_high: high,
  corners: [["multiplicateur_macro = 0", high], ["multiplicateur_macro = 1", low]],
  meets_target: aged <= 0 });
const EXPL_EXTINCT = [EXPL_EVAL(0.058, 9.9e9, 0.0226, 0.0214, 0.0184, 0.0266),
                      EXPL_EVAL(0.063, 4.95e9, 0.0113, 0.0107, 0.0092, 0.0133)];
const EXPL_HELD = [EXPL_EVAL(0.050, 1.8e10, -0.003, -0.0025, -0.006, -0.001),
                   EXPL_EVAL(0.055, 1.3e10, -0.001, -0.0005, -0.004, 0.002),
                   EXPL_EVAL(0.060, 0.8e10, 0.0005, -0.0002, -0.002, 0.003)];
const EXPL_REPORT = { name: "csg", titre: "Baisse de la CSG déductible",
  question: "Une baisse de la CSG déductible fait-elle baisser la dette en 2035 ?",
  computed: "2026-10-21", commit: "b8093f4f11ac2222", request: {},
  hypotheses: { ...PRED_NAMES, horizon: 10, target_year: 2035, target_points: 0,
                target_share: 0, theta: { common: 0.5, rows: {} }, uprating: {},
                behavioural: true, macro: true, looped: true },
  start: { year: 2025, debt_ratio: 1.157, primary_balance: -0.03, implicit_rate: 0.0188,
           gdp_eur: 2.99e12 },
  unit: "part du PIB", views: { vieillie: "la population de 2024 vieillie",
                                figee: "la population de 2024 telle quelle" },
  conventions: ["Δ tenu en part de PIB constante au-delà de la dernière année chiffrée"],
  banner: "Prédictif conditionnel : ce n'est pas une prévision.",
  debt_banner: "Les dépenses publiques ne sont PAS microsimulées ici.",
  bundles: 3, passes: 6,
  searches: [
    { persistence: "eteint", persistence_label: "Effet macro éteint après trois ans",
      digest: "fbedd821aaaabbbb", log: {}, evaluations: EXPL_EXTINCT, candidates: [],
      excluded: [], closest: EXPL_EXTINCT[1] },
    { persistence: "tenu", persistence_label: "Effet macro tenu au niveau de la troisième année",
      digest: "30369c5caaaabbbb", log: {}, evaluations: EXPL_HELD, excluded: [], closest: null,
      candidates: [
        { knobs: { csg_activite_deductible: 0.050 }, delta_aged: -0.003, delta_frozen: -0.0025,
          meets_target: true, frozen_only: false, robust: true,
          verdict: "robuste : la cible tient aux 2 coins de la boîte θ." },
        { knobs: { csg_activite_deductible: 0.055 }, delta_aged: -0.001, delta_frozen: -0.0005,
          meets_target: true, frozen_only: false, robust: false,
          verdict: "dépend de θ : au coin multiplicateur_macro = 0, l'écart vaut +0.200 pt de PIB et la cible de +0.000 pt de PIB tombe." },
        { knobs: { csg_activite_deductible: 0.060 }, delta_aged: 0.0005, delta_frozen: -0.0002,
          meets_target: false, frozen_only: true, robust: false,
          verdict: "dépend de θ : au coin multiplicateur_macro = 0, l'écart vaut +0.300 pt de PIB et la cible de +0.000 pt de PIB tombe." }] }] };
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
$("invalides").value = "1"; $("invalides").fire("input", {});
ok("case T appears for a lone adult with a person in case R", () => {
  assert.equal($("isoleWrap").hidden, false,
    "the 2042 names « des personnes invalides recueillies » beside the children (D-202)");
});
$("invalides").value = "0"; $("invalides").fire("input", {});
ok("case T hidden again without one", () => assert.equal($("isoleWrap").hidden, true));
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
  assert.equal(children[0].residence_alternee, undefined, "an unticked box sends no case H");
});
ok("each child's row has its alternating-residence box", () => {
  assert.match($("children").innerHTML, /data-child-field="residence_alternee"/);
  assert.match($("children").innerHTML, /Résidence alternée/);
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
/* A child in alternating residence, case H (D-201): the box goes as the wire format has it. */
typeChild("residence_alternee", true);
$("go").onclick();
await new Promise((r) => setTimeout(r, 60));
ok("a child in alternating residence is sent as the wire format has it", () => {
  const child = JSON.parse(calls.at(-1).opts.body).household.children[0];
  assert.equal(child.residence_alternee, true);
  assert.equal(child.handicap, undefined, "the box sends no disability");
});
typeChild("residence_alternee", false);
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
  assert.equal(body.household.personnes_invalides_recueillies, 0, "case R is a count, none by default (D-202)");
  assert.equal(body.reform, null, "an untouched panel must send no reform");
});

/* Phase 9 · the conditional debt path (D-216). Nothing is chosen for the reader: an empty
   list refuses, it does not pick. The three names reach the title, and a carried year
   says « report » on its own row. */
console.log("debt path");
ok("the precomputed report renders with its three scenario names", () => {
  assert.equal($("predHost").hidden, false, "a listed report must be shown");
  assert.match($("predHost").innerHTML, /Dépenses gelées en volume/);
  assert.match($("predHost").innerHTML, /Taux implicite tenu/);
  assert.match($("predHost").innerHTML, /population vieillie/);
});
await (async () => {
  $("reset").onclick();
  const before = calls.length;
  await $("goPred").onclick();
  ok("with no reform and no scenario, nothing is sent and the gaps are listed", () => {
    assert.equal(calls.length, before, "must not call the API");
    assert.match($("predOut").innerHTML, /scénario de dépense/);
    assert.match($("predOut").innerHTML, /scénario de taux/);
    assert.match($("predOut").innerHTML, /une réforme/);
    assert.match($("predOut").innerHTML, /salaires, avec sa source/);
  });
  $("dCelib").value = "2000"; $("dCelib").fire("input", {});
  $("predSpending").value = "gele_en_volume";
  $("predGrowthName").value = "Croissance réelle 1 %, prix 2 %";
  $("predReal").value = "1"; $("predPrices").value = "2";
  $("predWage").value = "3"; $("predWageSource").value = "3 % ronds, le rythme du PIB nominal";
  $("predRateKind").value = "marche"; $("predMarket").value = "";
  $("predHorizon").value = "3";
  $("predTheta").value = "";
  $("predRateKind").value = "implicite_tenu";
  await $("goPred").onclick();
  ok("without a θ nothing is sent: the page has no default θ either (D-217)", () => {
    assert.equal(calls.length, before, "must not call the API");
    assert.match($("predOut").innerHTML, /un θ, de 0 à 1/);
  });
  $("predTheta").value = "0.5";
  $("predRateKind").value = "marche";
  await $("goPred").onclick();
  ok("a market rate scenario without its rate is refused, not defaulted", () => {
    assert.equal(calls.length, before, "must not call the API");
    assert.match($("predOut").innerHTML, /taux de marché/);
  });
  $("predRateKind").value = "implicite_tenu";
  $("predWageSource").value = "  ";
  await $("goPred").onclick();
  ok("a wage index without its source is refused, not sent (D-226)", () => {
    assert.equal(calls.length, before, "must not call the API");
    assert.match($("predOut").innerHTML, /salaires, avec sa source/);
  });
  $("predWageSource").value = "3 % ronds, le rythme du PIB nominal";
  await $("goPred").onclick();
  await new Promise((r) => setTimeout(r, 10));
  ok("the fast path sends the three named scenarios and the horizon", () => {
    const call = calls.find((c) => c.url.endsWith("/predictif/simulate"));
    assert.ok(call, "the request must be sent once every hypothesis is named");
    const body = JSON.parse(call.opts.body);
    assert.deepEqual(body.spending, { rule: "gele_en_volume" });
    assert.equal(body.growth.real, 0.01); assert.equal(body.growth.prices, 0.02);
    assert.equal(body.rate.name, "Taux implicite tenu à son niveau de 2025");
    assert.equal(body.horizon, 3);
    assert.deepEqual(body.theta, { common: 0.5 });
    assert.deepEqual(body.uprating,
                     { wage: 0.03, source: "3 % ronds, le rythme du PIB nominal" });
    assert.ok(body.reform, "the reform panel's change must travel");
  });
  ok("the carried years say « report » and the names sit above the table", () => {
    const html = $("predOut").innerHTML;
    assert.match(html, /Croissance réelle 1 %, prix 2 %/);
    assert.equal((html.match(/>report</g) || []).length, 2, "two carried years");
    assert.match(html, /non demandé\. Absent, pas nul/);
  });
  ok("the fast path names its population view and carries its note, escaped (D-225)", () => {
    const html = $("predOut").innerHTML;
    assert.match(html, /Population : <b>vieillie<\/b>/, "the view must sit above the table");
    assert.match(html, /<p class="tnote">[^<]*Vue « vieillie » : l'année 2026[^<]*« figée »/,
                 "the population note must be shown, and name the view it does not price");
    assert.match(html, /INSEE &amp; DARES[^<]*n'est plus calibrée/,
                 "the note echoes the reader's source: escaped, and the caveat kept");
  });
  ok("the θ of the result, the θ box and the closed channels are shown", () => {
    const html = $("predOut").innerHTML;
    assert.match(html, /emploi au SMIC \(C2\) : θ = 0,5/);
    assert.match(html, /Boîte θ \(écart\)/);
    assert.match(html, /Écart mécanique/);
    assert.match(html, /dividendes/);
    assert.doesNotMatch(html, /non lus : vue mécanique/);
    assert.match($("predHost").innerHTML, /non lus : vue mécanique/,
                 "the report prices no behaviour and says its θ are not read");
  });
  ok("the indices are grouped, each in its unit, fixed or with its θ box, none summed", () => {
    const html = $("predOut").innerHTML;
    assert.match(html, /aucun additionné/);
    assert.match(html, /<b>Les gens<\/b>[\s\S]*<b>Les entreprises<\/b>[\s\S]*<b>L'État<\/b>/);
    assert.match(html, /boîte θ 8\s000 à 15\s000/);
    assert.match(html, /Des personnes\. Ne s'additionne pas/);
    assert.match(html, /Des équivalents temps plein\. Ne s'additionne pas/);
    assert.match(html, /1 an : 0,275/);
    assert.match(html, /fixe, aucun θ/);
    assert.match(html, /Dépense de R&amp;D<\/b> — non calculé : Couche entreprises/);
    assert.match(html, /2026 : −0,17 pt/);
    assert.doesNotMatch(html, /Emploi total/);
  });
  ok("with the loop, the reform's GDP and the macro fan get their own columns", () => {
    const html = $("predOut").innerHTML;
    assert.match(html, /PIB, écart à la référence/);
    assert.match(html, /\+0,07 %/);
    assert.match(html, /Éventail macro \(écart\)/);
  });
  const sent = calls.length;
  $("predMacro").checked = true;
  $("predHorizon").value = "10";
  $("predPersistence").value = "";
  await $("goPred").onclick();
  await new Promise((r) => setTimeout(r, 10));
  ok("past three years without a persistence, the request goes without one (D-230)", () => {
    assert.equal(calls.length, sent + 1, "the API computes both: nothing is asked first");
    const body = JSON.parse(calls.at(-1).opts.body);
    assert.equal(body.macro, true);
    assert.equal(body.horizon, 10);
    assert.equal("persistence" in body, false);
  });
  ok("both persistence scenarios stand side by side, neither in the lead (D-230)", () => {
    const html = $("predOut").innerHTML;
    assert.match(html, /Deux scénarios de persistance, côte à côte/);
    assert.match(html, /aucun n'est le défaut/);
    assert.match(html, /\+0,57 pt sous « effet macro éteint après trois ans » et \+0,23 pt sous « effet macro tenu au niveau de la troisième année »/);
    const first = html.indexOf("<h4>Effet macro éteint après trois ans</h4>");
    const second = html.indexOf("<h4>Effet macro tenu au niveau de la troisième année</h4>");
    assert.ok(first > 0 && second > first, "each scenario its own table, in the API's order");
    assert.equal((html.match(/<table>/g) || []).length, 2, "one table per scenario");
    assert.match(html, /Convention : Au-delà de trois ans : Effet macro éteint/);
    assert.match(html, /Convention : Au-delà de trois ans : Effet macro tenu/);
    assert.match(html, /2030 : \+0,57 pt/, "each scenario carries its own debt index");
    assert.match(html, /une valeur par scénario de persistance/);
  });
  $("predPersistence").value = "tenu";
  await $("goPred").onclick();
  await new Promise((r) => setTimeout(r, 10));
  ok("the loop and its persistence travel when both are named", () => {
    const call = calls.filter((c) => c.url.endsWith("/predictif/simulate")).at(-1);
    const body = JSON.parse(call.opts.body);
    assert.equal(body.macro, true);
    assert.equal(body.persistence, "tenu");
    assert.equal(body.horizon, 10);
  });
})();

/* Phase 10 · the searches precomputed by `impots exploration` (D-235). */
console.log("explorations");
ok("a precomputed exploration is shown, its question first", () => {
  assert.equal($("explHost").hidden, false, "a listed exploration must be shown");
  const html = $("explOut").innerHTML;
  assert.match(html, /Question :<\/b> Une baisse de la CSG déductible/);
  assert.ok(html.indexOf("Question :") < html.indexOf("<table>"), "the question leads");
  assert.match($("explPick").innerHTML, /value="illisible"/, "every exploration is listed");
});
ok("both persistence searches are drawn, neither in the lead (D-230)", () => {
  const html = $("explOut").innerHTML;
  assert.match(html, /Deux scénarios de persistance, côte à côte : aucun n'est le/);
  const first = html.indexOf("<h4>Effet macro éteint après trois ans</h4>");
  const second = html.indexOf("<h4>Effet macro tenu au niveau de la troisième année</h4>");
  assert.ok(first > 0 && second > first, "each search its own table, in the report's order");
  assert.equal((html.match(/<table>/g) || []).length, 2, "one table per search");
});
ok("every bundle shows its cost, its gap in both views, its θ box and its verdict", () => {
  const html = $("explOut").innerHTML;
  assert.match(html, /<td>csg_activite_deductible = 0,058<\/td><td>9,90 Md €<\/td>\s*<td>\+2,26 pt<\/td><td>\+2,14 pt<\/td>\s*<td>\+1,84 pt ; \+2,66 pt<\/td>/);
  assert.match(html, /tient la cible — robuste : la cible tient aux 2 coins/);
  assert.match(html, /tient la cible — dépend de θ : au coin multiplicateur_macro = 0/);
  assert.match(html, /ne tient qu'en vue figée : pas un plan/);
  assert.equal((html.match(/ne tient pas la cible/g) || []).length, 2,
               "under « éteint » both bundles miss the target");
});
ok("with no candidate, the closest bundle is named, with its gap", () => {
  assert.match($("explOut").innerHTML,
               /Aucun paquet ne tient la cible\.<\/b>\s+Le plus proche : csg_activite_deductible = 0,063, \+1,13 pt à θ/);
});
ok("the hypotheses, the target and the commit it ran on ride along", () => {
  const html = $("explOut").innerHTML;
  assert.match(html, /Dépenses gelées en volume/);
  assert.match(html, /écart de dette 2035\s+au plus \+0,00 pt/);
  assert.match(html, /θ = 0,5\s+pour chaque ligne/);
  assert.match(html, /sur le commit\s+<code>b8093f4f<\/code>/);
  assert.match(html, /Prédictif conditionnel/);
});
await (async () => {
  $("explPick").value = "illisible";
  $("explPick").fire("change", {});
  await new Promise((r) => setTimeout(r, 10));
  ok("a report the API refuses is said refused, never left blank", () => {
    const html = $("explOut").innerHTML;
    assert.match(html, /Exploration « illisible » refusée\s+par l'API/);
    assert.match(html, /sans verdict θ/);
  });
})();
