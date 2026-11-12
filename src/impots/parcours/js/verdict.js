// Le Monte-Carlo rejoué dans le navigateur (parcours, page 7 ; D-375) : la même
// arithmétique que `src/impots/predictif/montecarlo.py`, sur la dette de `dette.js`.
//
// LES TIRAGES. Le Python tire ses normales centrées réduites du générateur de numpy
// (PCG64) à la graine que le rapport porte ; le navigateur n'a pas ce générateur. La page
// porte donc ces normales brutes, tirées à sa construction par numpy à la même graine et
// dans le même ordre que `montecarlo._draw` (l'échantillon A, puis B ; dans chacun, les
// groupes dans l'ordre du rapport). Tout le reste se refait ici : la copule de corrélation
// ρ (Cholesky), la fonction de répartition normale (erf de fdlibm), la loi de chaque ligne
// inversée, le multiplicateur Mésange + z × σ censuré à zéro, la dette, la part des
// tirages où elle monte, les quantiles (ceux de numpy, « linear ») et les indices de Sobol
// (Saltelli, Jansen). Un test tient cette page égale au rapport et à `montecarlo.run` :
// `tests/test_parcours_verdict.py`.
(function (root) {
  "use strict";
  const D = typeof module !== "undefined" && module.exports ? require("./dette.js") : root.Dette;
  const MACRO_ROW = D.MACRO_ROW;

  // --- erf, la version de fdlibm (s_erf.c), que la bibliothèque C de Python suit --------
  const erx = 8.45062911510467529297e-01;
  const efx = 1.28379167095512586316e-01, efx8 = 1.02703333676410069053e+00;
  const pp = [1.28379167095512558561e-01, -3.25042107247001499370e-01, -2.84817495755985104766e-02,
    -5.77027029648944159157e-03, -2.37630166566501626084e-05];
  const qq = [3.97917223959155352819e-01, 6.50222499887672944485e-02, 5.08130628187576562776e-03,
    1.32494738004321644526e-04, -3.96022827877536812320e-06];
  const pa = [-2.36211856075265944077e-03, 4.14856118683748331666e-01, -3.72207876035701323847e-01,
    3.18346619901161753674e-01, -1.10894694282396677476e-01, 3.54783043256182359371e-02,
    -2.16637559486879084300e-03];
  const qa = [1.06420880400844228286e-01, 5.40397917702171048937e-01, 7.18286544141962662868e-02,
    1.26171219808761642112e-01, 1.36370839120290507362e-02, 1.19844998467991074170e-02];
  const ra = [-9.86494403484714822705e-03, -6.93858572707181764372e-01, -1.05586262253232909814e+01,
    -6.23753324503260060396e+01, -1.62396669462573470355e+02, -1.84605092906711035994e+02,
    -8.12874355063065934246e+01, -9.81432934416914548592e+00];
  const sa = [1.96512716674392571292e+01, 1.37657754143519042600e+02, 4.34565877475229228821e+02,
    6.45387271733267880336e+02, 4.29008140027567833386e+02, 1.08635005541779435134e+02,
    6.57024977031928170135e+00, -6.04244152148580987438e-02];
  const rb = [-9.86494292470009928597e-03, -7.99283237680523006574e-01, -1.77579549177547519889e+01,
    -1.60636384855821916062e+02, -6.37566443368389627722e+02, -1.02509513161107724954e+03,
    -4.83519191608651397019e+02];
  const sb = [3.03380607434824582924e+01, 3.25792512996573918826e+02, 1.53672958608443695994e+03,
    3.19985821950859553908e+03, 2.55305040643316442583e+03, 4.74528541206955367215e+02,
    -2.24409524465858183362e+01];
  const buffer = new DataView(new ArrayBuffer(8));

  function erf(x) {
    if (Number.isNaN(x)) return NaN;
    if (x === Infinity) return 1;
    if (x === -Infinity) return -1;
    let sign = false;
    if (x < 0) { x = -x; sign = true; }
    if (x < 0.84375) {
      let temp;
      if (x < 1.0 / (1 << 28)) {
        temp = x < 2.848094538889218e-306 ? 0.125 * (8.0 * x + efx8 * x) : x + efx * x;
      } else {
        const z = x * x;
        const r = pp[0] + z * (pp[1] + z * (pp[2] + z * (pp[3] + z * pp[4])));
        const s = 1 + z * (qq[0] + z * (qq[1] + z * (qq[2] + z * (qq[3] + z * qq[4]))));
        temp = x + x * (r / s);
      }
      return sign ? -temp : temp;
    }
    if (x < 1.25) {
      const s = x - 1;
      const P = pa[0] + s * (pa[1] + s * (pa[2] + s * (pa[3] + s * (pa[4] + s * (pa[5] + s * pa[6])))));
      const Q = 1 + s * (qa[0] + s * (qa[1] + s * (qa[2] + s * (qa[3] + s * (qa[4] + s * qa[5])))));
      return sign ? -erx - P / Q : erx + P / Q;
    }
    if (x >= 6) return sign ? -1 : 1;
    const s = 1 / (x * x);
    let R, S;
    if (x < 1 / 0.35) {
      R = ra[0] + s * (ra[1] + s * (ra[2] + s * (ra[3] + s * (ra[4] + s * (ra[5] + s * (ra[6] + s * ra[7]))))));
      S = 1 + s * (sa[0] + s * (sa[1] + s * (sa[2] + s * (sa[3] + s * (sa[4] + s * (sa[5] + s * (sa[6] + s * sa[7])))))));
    } else {
      R = rb[0] + s * (rb[1] + s * (rb[2] + s * (rb[3] + s * (rb[4] + s * (rb[5] + s * rb[6])))));
      S = 1 + s * (sb[0] + s * (sb[1] + s * (sb[2] + s * (sb[3] + s * (sb[4] + s * (sb[5] + s * sb[6]))))));
    }
    // x en simple précision approchée : les 32 bits bas de sa représentation à zéro.
    buffer.setFloat64(0, x);
    buffer.setUint32(4, 0);
    const z = buffer.getFloat64(0);
    const r = Math.exp(-z * z - 0.5625) * Math.exp((z - x) * (z + x) + R / S);
    return sign ? r / x - 1 : 1 - r / x;
  }

  // Φ, comme `statistics.NormalDist().cdf` ; Φ⁻¹, comme son `inv_cdf` (Wichura, AS241).
  function cdf(x) { return 0.5 * (1.0 + erf(x / Math.SQRT2)); }

  // Horner dans l'ordre même du Python : (((c0 r + c1) r + c2) … ) + c7.
  function horner(cs, r) {
    let v = cs[0] * r + cs[1];
    for (let i = 2; i < cs.length; i++) v = v * r + cs[i];
    return v;
  }
  const A_NUM = [2.5090809287301226727e+3, 3.3430575583588128105e+4, 6.7265770927008700853e+4,
    4.5921953931549871457e+4, 1.3731693765509461125e+4, 1.9715909503065514427e+3,
    1.3314166789178437745e+2, 3.3871328727963666080e+0];
  const A_DEN = [5.2264952788528545610e+3, 2.8729085735721942674e+4, 3.9307895800092710610e+4,
    2.1213794301586595867e+4, 5.3941960214247511077e+3, 6.8718700749205790830e+2,
    4.2313330701600911252e+1, 1.0];
  const B_NUM = [7.74545014278341407640e-4, 2.27238449892691845833e-2, 2.41780725177450611770e-1,
    1.27045825245236838258e+0, 3.64784832476320460504e+0, 5.76949722146069140550e+0,
    4.63033784615654529590e+0, 1.42343711074968357734e+0];
  const B_DEN = [1.05075007164441684324e-9, 5.47593808499534494600e-4, 1.51986665636164571966e-2,
    1.48103976427480074590e-1, 6.89767334985100004550e-1, 1.67638483018380384940e+0,
    2.05319162663775882187e+0, 1.0];
  const C_NUM = [2.01033439929228813265e-7, 2.71155556874348757815e-5, 1.24266094738807843860e-3,
    2.65321895265761230930e-2, 2.96560571828504891230e-1, 1.78482653991729133580e+0,
    5.46378491116411436990e+0, 6.65790464350110377720e+0];
  const C_DEN = [2.04426310338993978564e-15, 1.42151175831644588870e-7, 1.84631831751005468180e-5,
    7.86869131145613259100e-4, 1.48753612908506148525e-2, 1.36929880922735805310e-1,
    5.99832206555887937690e-1, 1.0];

  function invCdf(p) {
    const q = p - 0.5;
    if (Math.abs(q) <= 0.425) {
      const r = 0.180625 - q * q;
      return (horner(A_NUM, r) * q) / horner(A_DEN, r);
    }
    let r = q <= 0.0 ? p : 1.0 - p;
    r = Math.sqrt(-Math.log(r));
    let num, den;
    if (r <= 5.0) {
      r = r - 1.6;
      num = horner(B_NUM, r);
      den = horner(B_DEN, r);
    } else {
      r = r - 5.0;
      num = horner(C_NUM, r);
      den = horner(C_DEN, r);
    }
    const x = num / den;
    return q < 0.0 ? -x : x;
  }

  // La loi d'une ligne, inversée — `montecarlo.quantile_function`.
  function quantile(row, u) {
    const low = +row.low, mode = +row.central, high = +row.high;
    if (low === high) return mode;
    const law = row.loi || "triangular";
    if (law === "uniform") return low + u * (high - low);
    if (law === "normal") {
      return mode + (high - low) / (2 * 1.645) * invCdf(Math.min(Math.max(u, 1e-12), 1 - 1e-12));
    }
    const cut = (mode - low) / (high - low);
    if (u < cut) return low + Math.sqrt(u * (high - low) * (mode - low));
    return high - Math.sqrt((1.0 - u) * (high - low) * (high - mode));
  }

  // La matrice de corrélation ρ entre k lignes d'un article, et son facteur de Cholesky.
  function cholesky(k, rho) {
    const a = [];
    for (let i = 0; i < k; i++) { a.push([]); for (let j = 0; j < k; j++) a[i].push(i === j ? rho + (1.0 - rho) : rho); }
    const L = a.map(() => new Array(k).fill(0.0));
    for (let i = 0; i < k; i++) {
      for (let j = 0; j <= i; j++) {
        let s = a[i][j];
        for (let m = 0; m < j; m++) s -= L[i][m] * L[j][m];
        if (i === j) {
          if (!(s > 0)) throw new Error("ρ rend la corrélation singulière");
          L[i][j] = Math.sqrt(s);
        } else L[i][j] = s / L[j][j];
      }
    }
    return L;
  }

  function decode(text) {
    const bytes = Uint8Array.from(atob(text), (c) => c.charCodeAt(0));
    const view = new DataView(bytes.buffer);
    const out = new Float64Array(bytes.length / 8);
    for (let i = 0; i < out.length; i++) out[i] = view.getFloat64(8 * i, true);
    return out;
  }

  // Les colonnes d'un échantillon : une par ligne, et le décalage z — `montecarlo._draw`.
  function columns(lignes, groupes, raw, n, rho) {
    const out = {};
    for (const [name, keys] of groupes) {
      const normals = raw[name];
      if (name === MACRO_ROW) { out[name] = normals; continue; }
      const k = keys.length;
      const L = cholesky(k, rho);
      keys.forEach((key) => { out[key] = new Float64Array(n); });
      for (let i = 0; i < n; i++) {
        for (let r = 0; r < k; r++) {
          let x = 0.0;
          for (let j = 0; j < k; j++) x += normals[i * k + j] * L[r][j];
          out[keys[r]][i] = quantile(lignes[keys[r]], cdf(x));
        }
      }
    }
    for (const [key, row] of Object.entries(lignes)) {
      if (!(key in out)) out[key] = new Float64Array(n).fill(+row.central);
    }
    return out;
  }

  function last(payload, cols, n, o) {
    const rows = Object.keys(payload.rejeu.lignes);
    const f = new Float64Array(n);
    for (let i = 0; i < n; i++) {
      const values = {};
      for (const key of rows) values[key] = cols[key][i];
      const z = MACRO_ROW in cols ? cols[MACRO_ROW][i] : 0.0;
      const d = D.chemin(payload, { ...o, values, z }).delta;
      f[i] = d[d.length - 1];
    }
    return f;
  }

  function mean(xs) { let s = 0.0; for (const x of xs) s += x; return s / xs.length; }

  // Le quantile de numpy, méthode « linear », y compris sa façon d'interpoler.
  function quantileOf(sorted, q) {
    const n = sorted.length;
    const virtual = (n - 1) * q;
    const lo = Math.floor(virtual), hi = Math.min(lo + 1, n - 1);
    const t = virtual - lo;
    const a = sorted[lo], b = sorted[hi];
    const diff = b - a;
    return t >= 0.5 ? b - diff * (1.0 - t) : a + diff * t;
  }

  // La distribution de Δb à la dernière année, par vue, et ses indices de Sobol —
  // `montecarlo.run`. `tirages` : {n, groupes: [[nom, lignes]], a: {nom: base64}, b: …}.
  // `o` : rho, sdScale, views, sobol (faux pour s'en passer).
  function run(payload, tirages, o) {
    const n = tirages.n;
    const rho = o.rho;
    const persistence = payload.rejeu.looped ? D.READ : null;
    const groupes = tirages.groupes;
    const rawA = {}, rawB = {};
    for (const [name] of groupes) { rawA[name] = tirages.decoded_a[name]; rawB[name] = tirages.decoded_b[name]; }
    const lignes = payload.rejeu.lignes;
    const A = columns(lignes, groupes, rawA, n, rho), B = columns(lignes, groupes, rawB, n, rho);
    const chain = { persistence, sdScale: o.sdScale };
    const out = {};
    for (const view of o.views || ["vieillie", "figee"]) {
      const c = { ...chain, view };
      const fa = last(payload, A, n, c);
      const fb = o.sobol === false ? null : last(payload, B, n, c);
      let positive = 0;
      for (const x of fa) if (x > 0.0) positive += 1;
      const sorted = Float64Array.from(fa).sort();
      const result = { p_hausse: positive / n,
        quantiles: { q05: quantileOf(sorted, 0.05), q50: quantileOf(sorted, 0.50), q95: quantileOf(sorted, 0.95) } };
      if (fb) {
        const both = Float64Array.from([...fa, ...fb]);
        const m = mean(both);
        let v = 0.0; for (const x of both) v += (x - m) * (x - m);
        const variance = v / both.length;
        // Une variance nulle ou presque (σ = 0 sans élasticité tirée : il ne reste que
        // l'arrondi) ne se partage pas : l'indice est « sans objet », pas un nombre.
        // Le seuil : un écart-type sous un milliardième de la moyenne (ou de 1e-15).
        const nulle = !(variance > 0) || Math.sqrt(variance) <= 1e-9 * Math.max(Math.abs(m), 1e-6);
        const sobol = {};
        for (const [name, keys] of groupes) {
          const mixed = { ...A };
          for (const key of keys) mixed[key] = B[key];
          const fab = last(payload, mixed, n, c);
          if (!nulle) {
            let first = 0.0, total = 0.0;
            for (let i = 0; i < n; i++) { first += fb[i] * (fab[i] - fa[i]); total += (fa[i] - fab[i]) ** 2; }
            sobol[name] = { premier_ordre: first / n / variance, total: 0.5 * (total / n) / variance };
          } else sobol[name] = null;
        }
        result.sobol = sobol;
      }
      out[view] = result;
    }
    return out;
  }

  // Le verdict (D-345) — `montecarlo.verdict`.
  function verdict(share, threshold) {
    if (share >= threshold) return "hausse";
    if (share <= 1.0 - threshold + 1e-12) return "baisse";
    return "dépend";
  }

  function prepare(tirages) {
    tirages.decoded_a = {}; tirages.decoded_b = {};
    for (const [name] of tirages.groupes) {
      tirages.decoded_a[name] = decode(tirages.a[name]);
      tirages.decoded_b[name] = decode(tirages.b[name]);
    }
    return tirages;
  }

  // --- la page ----------------------------------------------------------------------------
  function page(doc, donnees) {
    const $ = (id) => doc.getElementById(id);
    const fr = D.fr;
    const pct = (x, d) => fr(100 * x, d) + " %";
    const pt = (x) => fr(100 * x, 2, true) + " pt";
    const depart = { "v-etude": $("v-etude").value, "v-seuil": $("v-seuil").value,
      "v-rho": $("v-rho").value, "v-sigma": $("v-sigma").value };
    for (const e of donnees.etudes) prepare(e.tirages);
    let cache = { key: null, out: null };

    function ligne(tbody, cells) {
      const tr = doc.createElement("tr");
      cells.forEach((c, i) => {
        const td = doc.createElement("td");
        td.textContent = c;
        if (i > 0) td.className = "num";
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    }

    function nom(groupe) {
      return groupe === MACRO_ROW ? "le multiplicateur" : `les lignes de ${groupe}.yaml`;
    }

    function calcule(recalcul) {
      const i = +$("v-etude").value;
      const etude = donnees.etudes[i];
      const seuil = +$("v-seuil").value, rho = +$("v-rho").value, sigma = +$("v-sigma").value;
      const articles = etude.tirages.groupes.filter(([g]) => g !== MACRO_ROW).length;
      $("v-rho").disabled = articles === 0;
      $("v-seuil-v").textContent = pct(seuil, 0);
      $("v-rho-v").textContent = fr(rho, 2);
      $("v-sigma-v").textContent = "× " + fr(sigma, 2);
      const key = `${i}|${rho}|${sigma}`;
      if (recalcul || cache.key !== key) {
        cache = { key, out: run(etude.payload, etude.tirages, { rho, sdScale: sigma }) };
      }
      const out = cache.out;
      const p = out.vieillie.p_hausse;
      const mot = verdict(p, seuil);
      const p0 = etude.rapport.vieillie.p_hausse;
      $("v-verdict").textContent = `${etude.candidat} : la dette de ${etude.annee} monte dans `
        + `${pct(p, 2)} des tirages, vue vieillie. Verdict : « ${mot} ».`;
      let pourquoi;
      if (mot === "hausse") pourquoi = `${pct(p, 2)} atteint le seuil de ${pct(seuil, 0)}.`;
      else if (mot === "baisse") pourquoi = `${pct(p, 2)} est sous ${pct(1 - seuil, 0)} : au moins ${pct(seuil, 0)} des tirages font baisser la dette.`;
      else pourquoi = `${pct(p, 2)} est sous le seuil de ${pct(seuil, 0)} et au-dessus de ${pct(1 - seuil, 0)} : les tirages ne s'accordent pas assez sur le signe.`;
      if (rho === etude.rho && sigma === 1) {
        pourquoi += ` Ce sont les lois du rapport : il donne ${pct(p0, 2)}, et le verdict « ${verdict(p0, donnees.seuil)} » au seuil déclaré.`;
      } else {
        pourquoi += ` Aux lois du rapport (ρ = ${fr(etude.rho, 1)}, σ inchangé), la part est de ${pct(p0, 2)}.`;
        if (articles === 0 && sigma === 1) pourquoi += " ρ ne joue pas ici : aucune ligne d'article n'est tirée.";
        else if (sigma !== 1) {
          pourquoi += sigma < 1
            ? " Un σ plus petit resserre le multiplicateur autour du centre de Mésange : moins de tirages tombent loin du milieu."
            : " Un σ plus grand élargit le multiplicateur : plus de tirages tombent loin du milieu, d'un côté comme de l'autre.";
        }
        if (articles > 0 && rho !== etude.rho) {
          let part = 0.0;
          for (const [g] of etude.tirages.groupes) if (g !== MACRO_ROW && out.vieillie.sobol[g]) part += out.vieillie.sobol[g].total;
          pourquoi += ` ρ change la façon dont les lignes d'un même article bougent ensemble ; ces lignes portent ${pct(part, 1)} de la variance (indices de Sobol totaux, ci-dessous), le multiplicateur le reste.`;
        }
      }
      $("v-pourquoi").textContent = pourquoi;
      const vues = $("v-vues");
      vues.textContent = "";
      for (const [v, label] of [["vieillie", "vue vieillie"], ["figee", "vue figée"]]) {
        const q = out[v].quantiles;
        ligne(vues, [label, pct(out[v].p_hausse, 2), `${pt(q.q05)} · ${pt(q.q50)} · ${pt(q.q95)}`]);
      }
      const sobol = $("v-sobol");
      sobol.textContent = "";
      for (const [g] of etude.tirages.groupes) {
        const s = out.vieillie.sobol[g];
        ligne(sobol, [nom(g), s ? fr(s.premier_ordre, 3) : "sans objet", s ? fr(s.total, 3) : "sans objet"]);
      }
    }

    // Le seuil se relit sans recalcul ; ρ, σ et l'étude refont les tirages au lâcher.
    $("v-seuil").addEventListener("input", () => calcule(false));
    for (const id of ["v-rho", "v-sigma"]) {
      $(id).addEventListener("input", () => {
        $(id + "-v").textContent = id === "v-rho" ? fr(+$(id).value, 2) : "× " + fr(+$(id).value, 2);
      });
      $(id).addEventListener("change", () => calcule(false));
    }
    $("v-etude").addEventListener("change", () => calcule(false));
    $("v-retour").addEventListener("click", () => {
      for (const [id, v] of Object.entries(depart)) $(id).value = v;
      calcule(false);
    });
    calcule(true);
  }

  const api = { erf, cdf, invCdf, quantile, cholesky, decode, columns, run, verdict, prepare, quantileOf };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else {
    root.Verdict = api;
    if (root.PARCOURS_VERDICT && typeof document !== "undefined") {
      const go = () => page(document, root.PARCOURS_VERDICT);
      if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", go);
      else go();
    }
  }
})(typeof window !== "undefined" ? window : globalThis);
