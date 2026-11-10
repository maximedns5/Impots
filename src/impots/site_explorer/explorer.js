// La page « explorer » (but 15, D-343) : des curseurs sur la grille commitée, et la chaîne
// rejouée dans le navigateur par `rejeu.js`. Elle ne calcule que ce que la grille porte ;
// tout nombre dit d'où il vient : calculé (le curseur est sur un point de la grille),
// interpolé (avec l'écart mesuré au témoin), ou le rapport d'une étude (à un cran).
(function () {
  "use strict";
  const R = window.Rejeu;
  const G = JSON.parse(document.getElementById("grille").textContent);
  const byId = Object.fromEntries(G.curseurs.map((c) => [c.id, c]));
  const state = Object.fromEntries(G.curseurs.map((c) => [c.id, c.loi]));
  let theta = 0.5, thetaMacro = 0.5;

  const eur = (v) => {
    const a = Math.abs(v);
    const s = a >= 1e9 ? (v / 1e9).toLocaleString("fr-FR", { maximumFractionDigits: 2 }) + " Md€"
      : (v / 1e6).toLocaleString("fr-FR", { maximumFractionDigits: 0 }) + " M€";
    return (v > 0 ? "+" : "") + s;
  };
  const pt = (v) => (v > 0 ? "+" : "") + (v * 100).toLocaleString("fr-FR", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + " pt";
  // L'étage de chaque nombre, comme sur les pages d'étude : le badge et son lien à la légende.
  const etage = (e, sous) => `<a class="etage e-${e.toLowerCase()}" href="#etage-${e.toLowerCase()}">${e}${sous ? ", sous hypothèses" : ""}</a>`;
  const val = (c, x) => (c.forme === "lambda" ? "λ = " + x.toLocaleString("fr-FR", { maximumFractionDigits: 2 })
    : x.toLocaleString("fr-FR", { maximumFractionDigits: x < 1 ? 4 : 0 }));

  // --- une part par curseur, interpolée -----------------------------------------------
  const coord = (c, x) => (c.geometrique ? Math.log(x) : x);
  const near = (a, b) => Math.abs(a - b) <= 1e-12 * Math.max(1, Math.abs(a));

  function leaves(tree, prefix = "", out = {}) {
    if (tree == null) return out;
    if (typeof tree === "object") for (const [k, v] of Object.entries(tree)) leaves(v, prefix + k + ".", out);
    else out[prefix.slice(0, -1)] = +tree;
    return out;
  }
  function tree(flat) {
    const out = {};
    for (const [path, v] of Object.entries(flat)) {
      const keys = path.split("."); let node = out;
      keys.slice(0, -1).forEach((k) => { node = node[k] = node[k] || {}; });
      node[keys[keys.length - 1]] = v;
    }
    return out;
  }
  function interpolatedLeaves(c, x, pick) {
    const xs = c.points.map((p) => coord(c, p.x));
    const ls = c.points.map((p) => leaves(pick(p)));
    const keys = [...new Set(ls.flatMap((l) => Object.keys(l)))].sort();
    const out = {};
    for (const k of keys) out[k] = R.interpoler(xs, ls.map((l) => l[k] || 0.0), coord(c, x), c.interpolation);
    return out;
  }

  function lire(c, x) {
    const exact = c.points.find((p) => near(p.x, x));
    const absent = c.points.find((p) => p.dette_absente);
    const cout = exact ? exact.cout : tree(interpolatedLeaves(c, x, (p) => p.cout));
    const deciles = c.points[0].deciles.length
      ? c.points[0].deciles.map((d, i) => ({ decile: d.decile, mean_delta: exact ? exact.deciles[i].mean_delta
        : R.interpoler(c.points.map((p) => coord(c, p.x)), c.points.map((p) => p.deciles[i].mean_delta), coord(c, x), c.interpolation) }))
      : [];
    const part = absent ? null : exact ? exact.part : tree(interpolatedLeaves(c, x, (p) => p.part));
    const rows = new Set(); c.points.forEach((p) => p.box_rows.forEach((r) => rows.add(r)));
    return { cout, deciles, part, rows: [...rows], exact: !!exact, absent: absent ? absent.dette_absente : null };
  }

  // --- la combinaison des curseurs bougés, et les paires mesurées -----------------------
  function combinaison() {
    const moved = G.curseurs.filter((c) => !near(state[c.id], c.loi));
    const lus = moved.map((c) => ({ c, ...lire(c, state[c.id]) }));
    let cout = { total: 0, menages: 0, entreprises: 0 };
    const deciles = new Array(10).fill(0);
    const parts = [], absents = [], rows = new Set();
    for (const l of lus) {
      for (const k of Object.keys(cout)) cout[k] += l.cout[k] || 0;
      l.deciles.forEach((d, i) => { deciles[i] += d.mean_delta; });
      if (l.absent) absents.push([l.c, l.absent]); else if (l.part) parts.push(l.part);
      l.rows.forEach((r) => rows.add(r));
    }
    const paires = [];
    for (const p of G.paires) {
      if (!moved.some((c) => c.id === p.a) || !moved.some((c) => c.id === p.b)) continue;
      const s = (id, far) => (state[id] - byId[id].loi) / (far - byId[id].loi);
      const w = s(p.a, p.xa) * s(p.b, p.xb);
      for (const k of Object.keys(cout)) cout[k] += w * (p.cout[k] || 0);
      p.deciles.forEach((d, i) => { deciles[i] += w * d.mean_delta; });
      if (p.part) parts.push(tree(Object.fromEntries(Object.entries(leaves(p.part)).map(([k, v]) => [k, w * v]))));
      paires.push(p);
    }
    const nonMesurees = [];
    for (let i = 0; i < moved.length; i++) for (let j = i + 1; j < moved.length; j++) {
      const a = moved[i].id, b = moved[j].id;
      if (!G.paires.some((p) => (p.a === a && p.b === b) || (p.a === b && p.b === a))) nonMesurees.push([a, b]);
    }
    return { moved, lus, cout, deciles, parts, absents, rows: [...rows], paires, nonMesurees };
  }

  // --- le rendu -------------------------------------------------------------------------
  const $ = (id) => document.getElementById(id);
  function provenance(c) {
    const x = state[c.id];
    if (near(x, c.loi)) return "la loi";
    if (c.points.some((p) => near(p.x, x))) return "calculé (point de la grille)";
    const t = c.temoin;
    const share = (Math.abs(t.ecart_cout) / Math.max(...c.points.map((p) => Math.abs(p.cout.total)))) * 100;
    return `interpolé ; au témoin, écart de ${eur(t.ecart_cout)} (${share.toLocaleString("fr-FR", { maximumFractionDigits: 2 })} % de l'amplitude)`;
  }

  // « Selon θ », comme la colonne des pages : le signe de Δb à θ et à chaque coin de la
  // boîte. Pas le « verdict » des pages, qui lit le Monte-Carlo (D-345, but 19).
  function selonTheta(box) {
    const vs = [box.theta, ...box.corners.map((c) => c[1])];
    if (vs.every((v) => v > 0)) return "hausse";
    if (vs.every((v) => v < 0)) return "baisse";
    return "dépend de θ";
  }

  function render() {
    for (const c of G.curseurs) {
      $(`v-${c.id}`).textContent = val(c, state[c.id]);
      $(`p-${c.id}`).textContent = provenance(c);
    }
    const k = combinaison();
    const cran = G.crans.find((cr) => G.curseurs.every((c) => near(state[c.id], cr.valeurs[c.id] ?? c.loi)));
    if (!k.moved.length) {
      $("resultat").innerHTML = "<p>Tous les curseurs sont sur la loi : la réforme est vide, elle ne coûte rien.</p>";
      return;
    }
    let html = "";
    if (cran) {
      html += `<p class="cran"><strong>Un cran de l'étude</strong> (${cran.titre}) : ${eur(cran.cout)} la première année`
        + (cran.dette != null ? `, ${pt(cran.dette)} de dette en ${G.rejeu.start.year + G.horizon}` : ", dette absente")
        + ` — ${cran.convention}, commit <code>${cran.commit.slice(0, 7)}</code>. La grille, ci-dessous, chiffre ces seuls boutons.</p>`;
    }
    html += `<p class="cout">Coût de la première année : <strong>${eur(k.cout.total)}</strong>${etage("L2")}`
      + ` (ménages ${eur(k.cout.menages)}, entreprises ${eur(k.cout.entreprises)}). Un coût positif coûte au budget.</p>`;
    if (k.parts.length) {
      const lignes = G.rejeu.lignes;
      const rows = [...k.rows.filter((r) => r !== R.MACRO_ROW).sort(), ...(G.rejeu.looped ? [R.MACRO_ROW] : [])];
      const th = Object.fromEntries(rows.map((r) => [r, r === R.MACRO_ROW ? thetaMacro : theta]));
      const box = R.box(G.rejeu, G.horizon, k.parts, lignes, rows, th, R.READ);
      const lo = Math.min(...box.corners.map((c) => c[1])), hi = Math.max(...box.corners.map((c) => c[1]));
      const sens = R.sensibilites(G.rejeu, G.horizon, k.parts, lignes, rows, th, R.READ);
      html += `<p class="dette">Dette en ${G.rejeu.start.year + G.horizon} : <strong>${pt(box.theta)}</strong>${etage("L4", true)} à θ,`
        + ` de ${pt(lo)} à ${pt(hi)} aux ${box.corners.length} coins de la boîte ; selon θ, <strong>${selonTheta(box)}</strong>`
        + " (la boîte seule, sans probabilité ; le verdict des pages d'étude lit le Monte-Carlo).</p>";
      html += "<table><thead><tr><th>paramètre</th><th>∂Δb / ∂θ, à θ</th></tr></thead><tbody>"
        + rows.map((r) => `<tr><td>${r}</td><td class="num">${pt(sens[r])} par unité de θ</td></tr>`).join("")
        + "</tbody></table>";
    }
    for (const [c, why] of k.absents) html += `<p class="absent">La dette de « ${c.titre} » est absente : ${why}</p>`;
    if (k.paires.length) html += `<p class="note">Interaction mesurée sur ${k.paires.map((p) => `${byId[p.a].titre} × ${byId[p.b].titre}`).join(" ; ")}.</p>`;
    if (k.nonMesurees.length) html += `<p class="note">Supposées additives, sans terme croisé mesuré : ${k.nonMesurees.map(([a, b]) => `${byId[a].titre} × ${byId[b].titre}`).join(" ; ")}.</p>`;
    if (k.lus.some((l) => l.deciles.length)) {
      const max = Math.max(1e-9, ...k.deciles.map(Math.abs));
      html += `<h3>Par décile de niveau de vie, variation moyenne du revenu disponible ${etage("L2")}</h3>`
        + "<ol class=\"deciles\">"
        + k.deciles.map((d, i) => `<li><span class="lab">D${i + 1}</span><span class="barre ${d >= 0 ? "plus" : "moins"}" style="width:${(Math.abs(d) / max * 100).toFixed(1)}%"></span><span class="num">${d.toLocaleString("fr-FR", { maximumFractionDigits: 0 })} €</span></li>`).join("")
        + "</ol>";
    }
    $("resultat").innerHTML = html;
  }

  // --- les contrôles --------------------------------------------------------------------
  for (const c of G.curseurs) {
    const input = $(`r-${c.id}`);
    const [lo, hi] = c.bornes;
    const toX = (u) => (c.geometrique ? lo * (hi / lo) ** u : lo + (hi - lo) * u);
    const toU = (x) => (c.geometrique ? Math.log(x / lo) / Math.log(hi / lo) : (x - lo) / (hi - lo));
    input.value = String(toU(state[c.id]));
    input.addEventListener("input", () => {
      let x = toX(+input.value);
      const snap = [...c.points.map((p) => p.x), ...G.crans.map((cr) => cr.valeurs[c.id]).filter((v) => v != null)]
        .find((p) => Math.abs(toU(p) - +input.value) < 0.004);
      if (snap != null) x = snap;
      state[c.id] = x;
      render();
    });
    c._toU = toU;
  }
  $("theta").addEventListener("input", (e) => { theta = +e.target.value; $("theta-v").textContent = theta.toFixed(2); render(); });
  $("theta-macro").addEventListener("input", (e) => { thetaMacro = +e.target.value; $("theta-macro-v").textContent = thetaMacro.toFixed(2); render(); });
  $("cran").addEventListener("change", (e) => {
    const cr = G.crans[+e.target.value];
    for (const c of G.curseurs) {
      state[c.id] = cr ? (cr.valeurs[c.id] ?? c.loi) : c.loi;
      $(`r-${c.id}`).value = String(c._toU(state[c.id]));
    }
    render();
  });
  render();
})();
