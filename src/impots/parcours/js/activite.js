// L'activité (parcours, page 5) : la chaîne d'un rapport d'étude rejouée dans le
// navigateur. La même arithmétique que `src/impots/predictif/rejouer.py`, ligne pour ligne,
// sur la même charge (`rejeu` et `years` du rapport) : les lignes à θ, les recettes des
// canaux, la boucle de Mésange sous ses trois persistances et sa variante salariale, la
// dette. `site_explorer/rejeu.js` porte la boucle sans persistance nommée ni variante, sur
// une part reportée ; celle-ci porte le chemin annuel d'un rapport. Un test la tient égale
// à `rejouer` (tests/test_parcours_activite.py, par node). Aucun appel réseau.
(function (root) {
  "use strict";
  const MACRO_ROW = "multiplicateur_macro";
  const READ = "lue";
  const SALARIALE = "salariale";
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

  // --- les recettes de chaque canal, depuis ses statistiques (`rejouer.receipts`) --------
  // Rend chaque part à part, recettes positives : c1, c7, c10, c11 ; plus les emplois que
  // C2 lit (un indice, en personnes, qui n'entre dans la recette que par C11).
  function canaux(channels, values) {
    const out = {};
    if (!channels) return out;
    if ("c1_eti" in channels) {
      const c1 = channels.c1_eti;
      out.c1_eti = values.eti_all * c1.A_bas + values.eti_top_decile * c1.A_haut;
    }
    if ("c7_labour_supply" in channels) {
      let total = 0.0;
      for (const [key, s] of Object.entries(channels.c7_labour_supply.S)) total = total + values[key] * s;
      out.c7_labour_supply = total;
    }
    if ("c10_dividendes" in channels) {
      const c10 = channels.c10_dividendes;
      const share = values.dividend_share_firm_owners;
      const owners = values.dividend_elasticity_firm_owners;
      const others = values.dividend_elasticity_other_holders;
      const elasticity = share * owners + (1.0 - share) * others;
      const induced = elasticity * c10.delta_log * c10.B;
      const shifted = values.dividend_wage_shift_firm_owners * share * owners * c10.delta_log * c10.B;
      out.c10_dividendes = c10.tau1 * induced - shifted * c10.lost_per_eur;
    }
    if ("c2_employment" in channels) {
      const c2 = channels.c2_employment;
      out.emplois_c2 = values.employment_elasticity_smic * c2.anchor + c2.tail + 0.0;
    }
    if ("c11_autofinancement" in channels) {
      const c11 = channels.c11_autofinancement;
      const reading = out.emplois_c2 * c11.value_per_job / c11.cut;
      const weight = values.autofinancement_poids_tresor_eco;
      out.c11_autofinancement = ((1.0 - weight) * reading + weight * c11.tresor_eco) * c11.cut;
    }
    return out;
  }

  const RECETTES = ["c1_eti", "c7_labour_supply", "c10_dividendes", "c11_autofinancement"];

  function receipts(mechanical, channels, values) {
    if (!channels) return mechanical;
    const parts = canaux(channels, values);
    const present = RECETTES.filter((k) => k in parts);
    if (!present.length) return mechanical;
    let total = parts[present[0]];
    for (const k of present.slice(1)) total = total + parts[k];
    return total + mechanical;
  }

  // --- la boucle (`rejouer.loop`) ---------------------------------------------------------
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

  function loop(impulses, gdp, macro, z, persistence, variante) {
    if (variante != null && variante !== SALARIALE) throw new Error(`variante « ${variante} » inconnue`);
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
        for (let j = 0; j <= k; j++) {
          const step = path[j] - (j ? path[j - 1] : 0.0);
          if (!step) continue;
          const at = readHorizon(k - j + 1, persistence, read, short);
          if (at === null) continue;
          const centre = interpolated(table.pib, at, read);
          const shifted = variante === SALARIALE && "pib_salariale" in table
            ? interpolated(table.pib_salariale, at, read) : centre;
          const m = Math.max(0.0, shifted + z * table.sd);
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

  // --- la dette (`rejouer.reference_path`, `rejouer.chemin`) -----------------------------
  function referencePath(rejeu, start, horizon) {
    const cadre = rejeu.cadre;
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

  // Le chemin annuel d'un rapport, à des valeurs de lignes et un décalage z du
  // multiplicateur. `opts` : view, persistence, variante (null ou « salariale »), boucle
  // (« complete », « denominateur », « aucune »). Un rapport reporté (`carry`) est refusé :
  // la page ne lit que les rapports d'étude, annuels.
  function chemin(payload, values, z, opts) {
    const view = opts.view || "vieillie";
    const boucle = opts.boucle || "complete";
    if (!BOUCLES.includes(boucle)) throw new Error(`boucle « ${boucle} » inconnue`);
    if (payload.carry != null) throw new Error("un rapport reporté n'est pas lu ici");
    const rejeu = payload.rejeu;
    const rows = payload.years;
    const horizon = rows.length;
    const years = rows.map((r) => +r.year);
    const [gdp, refs, nominal] = referencePath(rejeu, rejeu.start, horizon);
    const marginal = rejeu.cadre.taux.marginal;
    const stats = rows.map((r) => r.statistiques[view]);
    const cost = rows.map((r) => +r[VIEWS[view]]);
    let primary;
    if (rejeu.behavioural && stats.every((s) => s.canaux != null)) {
      primary = cost.map((c, k) => receipts(-c, stats[k].canaux, values) / gdp[k]);
    } else {
      primary = cost.map((c, k) => -c / gdp[k]);
    }
    const impulses = stats.map((s) => s.impulses);
    let gap, phi;
    if (rejeu.looped && boucle !== "aucune") {
      [gap, phi] = loop(impulses, gdp, rejeu.macro, z, opts.persistence, opts.variante);
      if (boucle === "denominateur") phi = new Array(horizon).fill(0.0);
    } else {
      gap = new Array(horizon).fill(0.0);
      phi = new Array(horizon).fill(0.0);
    }
    let debt = 0.0;
    const delta = [];
    for (let k = 0; k < horizon; k++) {
      debt = debt * (1.0 + marginal) / (1.0 + nominal) - (primary[k] + phi[k]);
      delta.push((refs[k] + debt) / (1.0 + gap[k]) - refs[k]);
    }
    return { years, reference: refs, delta, gap, feedback: phi, gdp };
  }

  function thetaValues(lignes, theta) {
    const values = {};
    for (const [key, row] of Object.entries(lignes)) values[key] = valueAt(row, theta[key]);
    const z = MACRO_ROW in theta ? 2.0 * +theta[MACRO_ROW] - 1.0 : 0.0;
    return [values, z];
  }

  function atTheta(payload, theta, opts) {
    const [values, z] = thetaValues(payload.rejeu.lignes, theta);
    return chemin(payload, values, z, opts);
  }

  // Δb de la dernière année en trois marches (`rejouer.decomposition`).
  function decomposition(payload, theta, opts) {
    const last = (b) => { const d = atTheta(payload, theta, { ...opts, boucle: b }).delta; return d[d.length - 1]; };
    const aucune = last("aucune"), denominateur = last("denominateur"), complete = last("complete");
    return { cout: aucune, denominateur: denominateur - aucune, retroaction: complete - denominateur, total: complete };
  }

  // --- l'affichage ---------------------------------------------------------------------
  const nombre = (v, d) => v.toLocaleString("fr-FR", { minimumFractionDigits: d, maximumFractionDigits: d });
  const signe = (v, d) => (v > 0 ? "+" : v < 0 ? "−" : "") + nombre(Math.abs(v), d);
  const md = (v) => signe(v / 1e9, 2) + " Md€";
  const pt = (v) => signe(v * 100, 2) + " pt";

  const api = { MACRO_ROW, READ, SALARIALE, VIEWS, BOUCLES, RECETTES, valueAt, canaux, receipts,
    interpolated, readHorizon, loop, referencePath, chemin, thetaValues, atTheta, decomposition,
    nombre, signe, md, pt };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.ParcoursActivite = api;

  // --- la page 5 : ses curseurs ---------------------------------------------------------
  if (typeof document === "undefined") return;
  const ici = document.getElementById("a-curseurs");
  if (!ici) return;
  const D = root.PARCOURS_ACTIVITE;
  const choix = document.getElementById("a-etude");
  const theta = document.getElementById("a-theta");
  const thetaV = document.getElementById("a-theta-v");
  const persistance = document.getElementById("a-persistance");
  const variante = document.getElementById("a-variante");
  const sortie = document.getElementById("a-resultat");

  function rendre() {
    const e = D.etudes[+choix.value];
    const t = +theta.value;
    thetaV.textContent = nombre(t, 2);
    const th = { [MACRO_ROW]: t };
    for (const k of Object.keys(e.payload.rejeu.lignes)) th[k] = 0.5;
    const opts = { view: "vieillie", persistence: persistance.value,
      variante: variante.value === SALARIALE ? SALARIALE : null };
    const c = atTheta(e.payload, th, opts);
    const dec = decomposition(e.payload, th, opts);
    const n = c.years.length;
    const lignes = c.years.map((y, k) => {
      const imp = Object.values(e.payload.years[k].statistiques.vieillie.impulses || {})
        .reduce((a, b) => a + b, 0.0);
      return `<tr><td>${y}</td><td class="num">${md(imp)}</td><td class="num">${signe(c.gap[k] * 100, 2)} %</td>`
        + `<td class="num">${md(c.feedback[k] * c.gdp[k])}</td><td class="num">${pt(c.delta[k])}</td></tr>`;
    }).join("");
    sortie.innerHTML = `<p>Dette en ${c.years[n - 1]}, avec la mesure moins sans elle : <strong>${pt(dec.total)}</strong> `
      + `(le coût sans boucle ${pt(dec.cout)} ; le PIB, dénominateur, ${pt(dec.denominateur)} ; `
      + `les recettes induites ${pt(dec.retroaction)}).</p>`
      + `<table><thead><tr><th>année</th><th>impulsion lue</th><th>écart de PIB</th>`
      + `<th>recette induite</th><th>Δ dette</th></tr></thead><tbody>${lignes}</tbody></table>`
      + `<p class="note">Rejoué ici, vue vieillie, comportements à θ½. Au réglage du rapport `
      + `(θ½, lue, centrale), la page redonne ${pt(e.temoin)}, le nombre de la page de l'étude.</p>`;
  }
  for (const el of [choix, theta, persistance, variante]) el.addEventListener("input", rendre);
  rendre();
})(typeof window !== "undefined" ? window : globalThis);
