// La chaîne rejouée dans le navigateur (but 15, D-343, D-344) : la même arithmétique que
// `src/impots/predictif/rejouer.py`, ligne pour ligne, sur la même charge. Un test la tient
// égale à `rejouer` à 1e-9 près sur chaque point de la grille (`tests/test_explorer.py`).
// Aucun appel réseau, aucun état : des fonctions de nombres.
(function (root) {
  "use strict";
  const MACRO_ROW = "multiplicateur_macro";
  const READ = "lue";
  const CARRY = "part_pib_constante";

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
      for (const [key, s] of Object.entries(channels.c7_labour_supply.S)) total += values[key] * s;
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

  // La même chose sur la FORME LINÉAIRE des canaux (`grille.lineaire`) : des sommes de
  // produits, qui s'additionnent d'un curseur à l'autre et s'interpolent entre deux points.
  function receiptsLin(mechanical, lin, values) {
    if (!lin) return mechanical;
    let total = mechanical;
    if (lin.c1) total += values.eti_all * lin.c1.A_bas + values.eti_top_decile * lin.c1.A_haut;
    if (lin.c7) for (const [key, s] of Object.entries(lin.c7)) total += values[key] * s;
    if (lin.c10) {
      const share = values.dividend_share_firm_owners;
      const owners = values.dividend_elasticity_firm_owners;
      const elasticity = share * owners + (1.0 - share) * values.dividend_elasticity_other_holders;
      total += elasticity * lin.c10.induit
        - values.dividend_wage_shift_firm_owners * share * owners * lin.c10.deplace;
    }
    if (lin.c11) {
      const weight = values.autofinancement_poids_tresor_eco;
      total += (1.0 - weight) * (values.employment_elasticity_smic * lin.c11.ancre + lin.c11.queue)
        + weight * lin.c11.tresor;
    }
    return total;
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
      if (horizon > read[read.length - 1]) throw new Error(`horizon de ${horizon} ans au-delà de ${read[read.length - 1]}`);
      return horizon;
    }
    if (horizon <= short) return horizon;
    if (persistence == null) throw new Error(`au-delà de ${short} ans sans persistance nommée`);
    return persistence === "eteint" ? null : short;
  }

  function loop(impulses, gdp, macro, z, persistence) {
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
          const m = Math.max(0.0, centre + z * table.sd);
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

  // Une passe reportée, ou une COMBINAISON de passes reportées (D-344) : `parts` est une
  // liste de {cost, canaux, impulses} de la première année ; les recettes de chaque part à
  // θ sont sommées, les impulsions aussi, puis la chaîne tourne une fois. Une seule part,
  // c'est `rejouer.chemin` sur un rapport reporté.
  function chemin(rejeu, horizon, parts, values, z, persistence) {
    const [gdp, refs, nominal] = referencePath(rejeu, rejeu.start, horizon);
    const marginal = rejeu.cadre.taux.marginal;
    let first = 0.0;
    const impulse = {};
    for (const p of parts) {
      const r = rejeu.behavioural && p.canaux != null ? receiptsLin(-p.cost, p.canaux, values) : -p.cost;
      first += r / gdp[0];
      for (const [i, v] of Object.entries(p.impulses || {})) impulse[i] = (impulse[i] || 0.0) + v;
    }
    const primary = new Array(horizon).fill(first);
    const impulses = gdp.map((y) => {
      const out = {};
      for (const [i, v] of Object.entries(impulse)) out[i] = v / gdp[0] * y;
      return out;
    });
    let gap, phi;
    if (rejeu.looped) [gap, phi] = loop(impulses, gdp, rejeu.macro, z, persistence);
    else gap = phi = new Array(horizon).fill(0.0);
    let debt = 0.0;
    const delta = [];
    for (let k = 0; k < horizon; k++) {
      debt = debt * (1.0 + marginal) / (1.0 + nominal) - (primary[k] + phi[k]);
      delta.push((refs[k] + debt) / (1.0 + gap[k]) - refs[k]);
    }
    return { delta, gap, phi, reference: refs };
  }

  function thetaValues(lignes, theta) {
    const values = {};
    for (const [key, row] of Object.entries(lignes)) values[key] = valueAt(row, theta[key]);
    const z = MACRO_ROW in theta ? 2.0 * +theta[MACRO_ROW] - 1.0 : 0.0;
    return [values, z];
  }

  // Δb à la dernière année, à θ et à chaque coin de la boîte — `rejouer.box`.
  function box(rejeu, horizon, parts, lignes, rows, theta, persistence) {
    const at = (t) => { const [v, z] = thetaValues(lignes, t); return chemin(rejeu, horizon, parts, v, z, persistence); };
    const corners = [];
    const n = rows.length;
    for (let mask = 0; mask < (1 << n); mask++) {
      const corner = { ...theta };
      // Le même ordre que `itertools.product((0.0, 1.0), repeat=n)`.
      rows.forEach((key, i) => { corner[key] = (mask >> (n - 1 - i)) & 1 ? 1.0 : 0.0; });
      const label = rows.map((key) => `${key} = ${corner[key] === 1 ? 1 : 0}`).join(", ");
      const d = at(corner).delta;
      corners.push([label, d[d.length - 1]]);
    }
    const d = at(theta).delta;
    return { theta: d[d.length - 1], corners };
  }

  // La sensibilité de Δb à la dernière année à chaque ligne, à θ : dérivée à droite et à
  // gauche par pas de 1e-6 sur θ (chaque ligne est linéaire par morceaux autour de ½).
  function sensibilites(rejeu, horizon, parts, lignes, rows, theta, persistence) {
    const last = (t) => { const [v, z] = thetaValues(lignes, t); const d = chemin(rejeu, horizon, parts, v, z, persistence).delta; return d[d.length - 1]; };
    const h = 1e-6, out = {};
    for (const key of rows) {
      const t0 = +theta[key];
      const up = Math.min(1, t0 + h), down = Math.max(0, t0 - h);
      out[key] = (last({ ...theta, [key]: up }) - last({ ...theta, [key]: down })) / (up - down);
    }
    return out;
  }

  // --- l'interpolation entre les points d'un curseur --------------------------------------
  // Linéaire pour un taux ; PCHIP de Fritsch et Carlson pour un seuil, une part, un plafond
  // ou un λ, sur le logarithme de la valeur pour une grille géométrique. `interpolation.py`
  // fait la même chose en Python.
  function pchipSlopes(x, y) {
    const n = x.length, h = [], d = [];
    for (let k = 0; k < n - 1; k++) { h.push(x[k + 1] - x[k]); d.push((y[k + 1] - y[k]) / h[k]); }
    const m = new Array(n).fill(0.0);
    if (n === 2) { m[0] = m[1] = d[0]; return m; }
    for (let k = 1; k < n - 1; k++) {
      if (d[k - 1] * d[k] > 0) {
        const w1 = 2 * h[k] + h[k - 1], w2 = h[k] + 2 * h[k - 1];
        m[k] = (w1 + w2) / (w1 / d[k - 1] + w2 / d[k]);
      }
    }
    const end = (h0, h1, d0, d1) => {
      let s = ((2 * h0 + h1) * d0 - h0 * d1) / (h0 + h1);
      if (Math.sign(s) !== Math.sign(d0)) s = 0.0;
      else if (Math.sign(d0) !== Math.sign(d1) && Math.abs(s) > Math.abs(3 * d0)) s = 3 * d0;
      return s;
    };
    m[0] = end(h[0], h[1], d[0], d[1]);
    m[n - 1] = end(h[n - 2], h[n - 3], d[n - 2], d[n - 3]);
    return m;
  }

  function interpoler(xs, ys, x, methode) {
    const n = xs.length;
    if (x <= xs[0]) return ys[0];
    if (x >= xs[n - 1]) return ys[n - 1];
    let k = 0;
    while (x > xs[k + 1]) k++;
    if (x === xs[k]) return ys[k];
    const t = (x - xs[k]) / (xs[k + 1] - xs[k]);
    if (methode === "lineaire") return ys[k] + t * (ys[k + 1] - ys[k]);
    const m = pchipSlopes(xs, ys), h = xs[k + 1] - xs[k];
    const h00 = 2 * t ** 3 - 3 * t ** 2 + 1, h10 = t ** 3 - 2 * t ** 2 + t;
    const h01 = -2 * t ** 3 + 3 * t ** 2, h11 = t ** 3 - t ** 2;
    return h00 * ys[k] + h10 * h * m[k] + h01 * ys[k + 1] + h11 * h * m[k + 1];
  }

  const api = { MACRO_ROW, READ, CARRY, valueAt, receipts, receiptsLin, loop, referencePath, chemin,
    thetaValues, box, sensibilites, pchipSlopes, interpoler };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.Rejeu = api;
})(typeof window !== "undefined" ? window : globalThis);
