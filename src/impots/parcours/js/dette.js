// La dette rejouée dans le navigateur (parcours, page 6 ; D-375) : la même arithmétique que
// `src/impots/predictif/rejouer.py`, ligne pour ligne, sur les champs `rejeu` et `years`
// d'un rapport prédictif commité. Un test la tient égale à `rejouer` (et au rapport, au
// cadre central) : `tests/test_parcours_dette.py`. Aucun appel réseau, aucun état.
//
// Ce qui diffère de `rejouer.chemin`, et seulement en option : le cadre (croissance, prix,
// règle de dépense) peut être remplacé, comme `rejouer` le lirait dans un `rejeu.cadre`
// réécrit ; le taux de la dette ajoutée peut être donné (`marginal`, D-349) ; l'écart-type
// du multiplicateur peut être multiplié par un facteur (`sdScale`, page 7). Le coût de
// chaque année, lui, est celui de la passe : changer la croissance ici ne refait pas le
// vieillissement des revenus.
(function (root) {
  "use strict";
  const MACRO_ROW = "multiplicateur_macro";
  const READ = "lue";
  const VIEWS = { vieillie: "mechanical_aged_eur", figee: "mechanical_frozen_eur" };
  const BOUCLES = ["complete", "denominateur", "aucune"];

  // --- les lignes : une valeur à θ, par son centre publié, dans son sens -----------------
  function valueAt(row, theta) {
    const low = +row.low, centre = +row.central, high = +row.high;
    if (low === high) return centre;
    let t = +theta;
    if (row.un === "low") t = 1.0 - t;
    const lower = centre - (1.0 - 2.0 * t) * (centre - low);
    const upper = centre + (2.0 * t - 1.0) * (high - centre);
    return t <= 0.5 ? lower : upper;
  }

  // --- les recettes, depuis les statistiques des canaux (C1, C7, C10, C11) -------------
  function receipts(mechanical, channels, values) {
    if (!channels) return mechanical;
    const parts = [];
    if ("c1_eti" in channels) {
      const c1 = channels.c1_eti;
      parts.push(values.eti_all * c1.A_bas + values.eti_top_decile * c1.A_haut);
    }
    if ("c7_labour_supply" in channels) {
      let total = 0.0;
      for (const [key, s] of Object.entries(channels.c7_labour_supply.S)) total = total + values[key] * s;
      parts.push(total);
    }
    if ("c10_dividendes" in channels) {
      const c10 = channels.c10_dividendes;
      const share = values.dividend_share_firm_owners;
      const owners = values.dividend_elasticity_firm_owners;
      const others = values.dividend_elasticity_other_holders;
      const elasticity = share * owners + (1.0 - share) * others;
      const induced = elasticity * c10.delta_log * c10.B;
      const shifted = values.dividend_wage_shift_firm_owners * share * owners
        * c10.delta_log * c10.B;
      parts.push(c10.tau1 * induced - shifted * c10.lost_per_eur);
    }
    if ("c11_autofinancement" in channels) {
      const c11 = channels.c11_autofinancement, c2 = channels.c2_employment;
      const jobs = values.employment_elasticity_smic * c2.anchor + c2.tail + 0.0;
      const reading = jobs * c11.value_per_job / c11.cut;
      const weight = values.autofinancement_poids_tresor_eco;
      parts.push(((1.0 - weight) * reading + weight * c11.tresor_eco) * c11.cut);
    }
    if (!parts.length) return mechanical;
    let total = parts[0];
    for (const part of parts.slice(1)) total = total + part;
    return total + mechanical;
  }

  // --- la boucle --------------------------------------------------------------------------
  function interpolated(row, horizon, read) {
    if (read.includes(horizon)) return +row[String(horizon)];
    const below = Math.max(...read.filter((h) => h < horizon));
    const above = Math.min(...read.filter((h) => h > horizon));
    const low = +row[String(below)], high = +row[String(above)];
    return low + (horizon - below) / (above - below) * (high - low);
  }

  function readHorizon(horizon, persistence, read, short) {
    if (persistence === READ) {
      if (horizon > read[read.length - 1]) throw new Error(`horizon de ${horizon} ans au-delà de ${read[read.length - 1]} : refusé`);
      return horizon;
    }
    if (horizon <= short) return horizon;
    if (persistence == null) throw new Error(`au-delà de ${short} ans sans persistance nommée`);
    return persistence === "eteint" ? null : short;
  }

  // (y_t, φ_t) année par année au décalage z du multiplicateur — `rejouer.loop`, sans la
  // variante salariale. `sdScale` multiplie l'écart-type d'IMK (1 : celui du rapport).
  function loop(impulses, gdp, macro, z, persistence, sdScale) {
    const scale = sdScale == null ? 1.0 : sdScale;
    const read = macro.horizons.map((h) => +h);
    const short = +macro.court;
    const tables = macro.instruments;
    const seen = new Set();
    for (const year of impulses) for (const [i, v] of Object.entries(year || {})) if (v) seen.add(i);
    const covered = [...seen].filter((i) => i in tables).sort();
    const units = {};
    for (const i of covered) {
      units[i] = impulses.map((year, k) => ((year || {})[i] || 0.0) * 100.0 / (tables[i].brut * gdp[k]));
    }
    const gap = [], balance = [];
    for (let k = 0; k < impulses.length; k++) {
      let yk = 0.0, phik = 0.0;
      for (const instrument of covered) {
        const table = tables[instrument];
        const path = units[instrument];
        const sd = scale === 1.0 ? table.sd : table.sd * scale;
        for (let j = 0; j <= k; j++) {
          const step = path[j] - (j ? path[j - 1] : 0.0);
          if (!step) continue;
          const at = readHorizon(k - j + 1, persistence, read, short);
          if (at === null) continue;
          const centre = interpolated(table.pib, at, read);
          const m = Math.max(0.0, centre + z * sd);
          const gross = table.brut;
          const f = Math.min((interpolated(table.solde, at, read) + gross) * m / centre, gross);
          yk = yk + step * m / 100.0;
          phik = phik + step * f / 100.0;
        }
      }
      gap.push(yk);
      balance.push(phik);
    }
    return [gap, balance];
  }

  // --- la dette ---------------------------------------------------------------------------
  // (PIB Y_t, ratio de référence b_t, croissance nominale) — `rejouer.reference_path`.
  function referencePath(cadre, start, horizon) {
    const real = cadre.growth.real, prices = cadre.growth.prices;
    const nominal = (1.0 + real) * (1.0 + prices) - 1.0;
    const rule = cadre.spending.rule;
    let factor;
    if (rule === "part_pib_constante") factor = 1.0;
    else if (rule === "gele_en_volume") factor = (1.0 + prices) / (1.0 + nominal);
    else if (rule === "personnalise") factor = (1.0 + cadre.spending.growth) / (1.0 + nominal);
    else throw new Error(`règle de dépense inconnue : ${rule}`);
    const rates = cadre.taux.reference;
    let product = start.gdp_eur, share = start.spending_ratio, ratio = start.debt_ratio;
    const gdp = [], refs = [];
    for (let k = 0; k < horizon; k++) {
      product *= 1.0 + nominal;
      share *= factor;
      ratio = ratio * (1.0 + rates[k]) / (1.0 + nominal) - (start.receipts_ratio - share);
      gdp.push(product);
      refs.push(ratio);
    }
    return [gdp, refs, nominal];
  }

  // Le chemin d'une vue — `rejouer.chemin`. `o` : view, values, z, persistence, boucle,
  // marginal, cadre (remplace `rejeu.cadre`), sdScale.
  function chemin(payload, o) {
    const boucle = o.boucle || "complete";
    if (!BOUCLES.includes(boucle)) throw new Error(`boucle « ${boucle} » inconnue`);
    const rejeu = payload.rejeu;
    if (payload.carry != null) throw new Error("un rapport reporté ne se rejoue pas ici");
    const rows = payload.years;
    const horizon = rows.length;
    const cadre = o.cadre || rejeu.cadre;
    const [gdp, refs, nominal] = referencePath(cadre, rejeu.start, horizon);
    const marginal = o.marginal == null ? cadre.taux.marginal : o.marginal;
    const stats = rows.map((r) => r.statistiques[o.view]);
    const cost = rows.map((r) => +r[VIEWS[o.view]]);
    let primary;
    if (rejeu.behavioural && stats.every((s) => s.canaux != null)) {
      primary = cost.map((c, k) => receipts(-c, stats[k].canaux, o.values) / gdp[k]);
    } else {
      primary = cost.map((c, k) => -c / gdp[k]);
    }
    const impulses = stats.map((s) => s.impulses);
    let gap, phi;
    if (rejeu.looped && boucle !== "aucune") {
      [gap, phi] = loop(impulses, gdp, rejeu.macro, o.z, o.persistence, o.sdScale);
      if (boucle === "denominateur") phi = new Array(horizon).fill(0.0);
    } else {
      gap = new Array(horizon).fill(0.0);
      phi = gap;
    }
    let debt = 0.0;
    const delta = [];
    for (let k = 0; k < horizon; k++) {
      debt = debt * (1.0 + marginal) / (1.0 + nominal) - (primary[k] + phi[k]);
      delta.push((refs[k] + debt) / (1.0 + gap[k]) - refs[k]);
    }
    return { years: rows.map((r) => +r.year), reference: refs, delta, gdp, gap, phi };
  }

  // (valeurs des lignes, décalage z) à un θ par ligne — `rejouer.theta_values`.
  function thetaValues(payload, theta) {
    const values = {};
    for (const [key, row] of Object.entries(payload.rejeu.lignes)) values[key] = valueAt(row, theta[key]);
    const z = MACRO_ROW in theta ? 2.0 * +theta[MACRO_ROW] - 1.0 : 0.0;
    return [values, z];
  }

  // Δb de la dernière année en trois marches — `rejouer.decomposition`.
  function decomposition(payload, theta, o) {
    const [values, z] = thetaValues(payload, theta);
    const last = (boucle) => {
      const d = chemin(payload, { ...o, values, z, boucle }).delta;
      return d[d.length - 1];
    };
    const aucune = last("aucune"), denominateur = last("denominateur"), complete = last("complete");
    return { cout: aucune, denominateur: denominateur - aucune,
      retroaction: complete - denominateur, total: complete };
  }

  // --- les nombres, à la française --------------------------------------------------------
  function fr(x, d, signe) {
    const texte = Math.abs(x).toFixed(d).replace(".", ",").replace(/\B(?=(\d{3})+(?!\d))/g, " ");
    if (Number(Math.abs(x).toFixed(d)) === 0) return texte;
    if (x < 0) return "−" + texte;
    return signe ? "+" + texte : texte;
  }
  const pct = (x, d) => fr(100 * x, d) + " %";
  const pt = (x) => fr(100 * x, 2, true) + " pt";

  // θ½ pour chaque ligne revendiquée et pour le multiplicateur : le cadre des études.
  function milieu(payload) {
    const theta = { [MACRO_ROW]: 0.5 };
    for (const key of Object.keys(payload.rejeu.lignes)) theta[key] = 0.5;
    return theta;
  }

  // --- la page ----------------------------------------------------------------------------
  function page(doc, donnees) {
    const $ = (id) => doc.getElementById(id);
    const ids = ["d-etude", "d-croissance", "d-prix", "d-taux", "d-regle", "d-depense"];
    const depart = {};
    for (const id of ids) depart[id] = $(id).value;

    function cellule(tr, texte, num) {
      const td = doc.createElement("td");
      td.textContent = texte;
      if (num) td.className = "num";
      tr.appendChild(td);
    }
    function ligne(tbody, cells) {
      const tr = doc.createElement("tr");
      cells.forEach((c, i) => cellule(tr, c, i > 0));
      tbody.appendChild(tr);
    }

    function calcule() {
      const etude = donnees.etudes[+$("d-etude").value];
      const payload = etude.payload;
      const base = payload.rejeu.cadre;
      const real = +$("d-croissance").value / 100, prices = +$("d-prix").value / 100;
      const rule = $("d-regle").value;
      const cadre = { ...base, growth: { real, prices },
        spending: { rule, growth: rule === "personnalise" ? +$("d-depense").value / 100 : null } };
      const marginal = $("d-taux").value === "marche" ? donnees.taux_marche : undefined;
      $("d-depense").disabled = rule !== "personnalise";
      $("d-croissance-v").textContent = pct(real, 1);
      $("d-prix-v").textContent = pct(prices, 1);
      $("d-depense-v").textContent = rule === "personnalise" ? pct(+$("d-depense").value / 100, 1) : "—";
      const theta = milieu(payload);
      const [values, z] = thetaValues(payload, theta);
      const o = { values, z, persistence: READ, cadre, marginal };
      const vieillie = chemin(payload, { ...o, view: "vieillie" });
      const figee = chemin(payload, { ...o, view: "figee" });
      const marches = decomposition(payload, theta, { view: "vieillie", persistence: READ, cadre, marginal });
      const rapport = etude.rapport;
      const n = vieillie.delta.length;
      const fin = vieillie.years[n - 1];
      const ref = rapport.delta.vieillie[n - 1];
      const ici = vieillie.delta[n - 1];
      $("d-tete").textContent = `${etude.candidat}, dette de ${fin} (vue vieillie) : sans boucle, `
        + `${pt(marches.cout)} de PIB ; avec la boucle à θ½, ${pt(ici)}. Au cadre des études : `
        + `${pt(rapport.decomposition.vieillie.cout)} et ${pt(ref)}`
        + (Math.abs(ici - ref) < 5e-5 ? "." : `, soit ${pt(ici - ref)} de différence avec la boucle.`);
      // Hors des plages que le gouvernement publie, la page le dit : le rejeu change le PIB et
      // la dette de référence, pas les revenus de la passe.
      const pl = donnees.plages;
      const hors = [];
      if (pl && (real < pl.croissance[0] - 1e-9 || real > pl.croissance[1] + 1e-9)) {
        hors.push(`la croissance réelle (${pct(real, 1)}, publiée de ${pct(pl.croissance[0], 1)} à ${pct(pl.croissance[1], 1)})`);
      }
      if (pl && (prices < pl.prix[0] - 1e-9 || prices > pl.prix[1] + 1e-9)) {
        hors.push(`les prix (${pct(prices, 1)}, déflateur publié de ${pct(pl.prix[0], 1)} à ${pct(pl.prix[1], 1)})`);
      }
      $("d-alerte").textContent = hors.length
        ? `Attention : ${hors.join(" et ")} sortent des plages du PLF 2026 pour ${pl.annees[0]} à ${pl.annees[1]}. `
          + `La dette de référence de ${fin} est ici de ${pct(vieillie.reference[n - 1], 1)} du PIB. Le rejeu ne refait pas `
          + "le vieillissement des revenus : le coût de chaque année reste celui de la passe, et le nombre n'est qu'un ordre de grandeur."
        : "";
      const tbody = $("d-marches");
      tbody.textContent = "";
      const r = rapport.decomposition.vieillie;
      ligne(tbody, ["le coût, sans effet sur l'activité", pt(marches.cout), pt(r.cout)]);
      ligne(tbody, ["le dénominateur", pt(marches.denominateur), pt(r.denominateur)]);
      ligne(tbody, ["les recettes induites", pt(marches.retroaction), pt(r.retroaction)]);
      ligne(tbody, ["Δb en " + fin, pt(marches.total), pt(r.total)]);
      const annees = $("d-annees");
      annees.textContent = "";
      for (let k = 0; k < n; k++) {
        ligne(annees, [String(vieillie.years[k]), fr(vieillie.gdp[k] / 1e9, 0) + " Md€",
          pct(vieillie.reference[k], 2), pt(vieillie.delta[k]), pt(figee.delta[k])]);
      }
    }

    for (const id of ids) {
      $(id).addEventListener("input", calcule);
      $(id).addEventListener("change", calcule);
    }
    $("d-retour").addEventListener("click", () => {
      for (const id of ids) $(id).value = depart[id];
      calcule();
    });
    calcule();
  }

  const api = { MACRO_ROW, READ, VIEWS, BOUCLES, valueAt, receipts, interpolated, readHorizon,
    loop, referencePath, chemin, thetaValues, decomposition, milieu, fr };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else {
    root.Dette = api;
    if (root.PARCOURS_DETTE && typeof document !== "undefined") {
      const go = () => page(document, root.PARCOURS_DETTE);
      if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", go);
      else go();
    }
  }
})(typeof window !== "undefined" ? window : globalThis);
