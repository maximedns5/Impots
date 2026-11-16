/* La cascade d'une mesure (but 26, D-484) : l'effet papillon, en graphe.
 *
 * Ce script ne calcule rien tant que le lecteur ne bouge pas θ : il dessine le graphe que
 * `jumeau.cascade.calculer` a rendu à θ½ (en JSON dans la page), en couches de gauche à
 * droite, l'épaisseur des flèches selon leur montant, une année à la fois. Quand θ bouge,
 * il charge Pyodide comme la page du jumeau (`pyodide.js` vérifié par son empreinte, un
 * Worker né d'un Blob, `jumeau-paquet.json`, `jumeau-donnees.json`) et demande au Worker
 * `cascade.calculer_json` : le même code, aucun portage.
 *
 * Au téléphone, la même chose en liste dépliable. Un nœud gris n'a pas de nombre : le
 * canal n'est pas encore modélisé.
 */
"use strict";
(function () {
  const ici = document.currentScript;
  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const fr = (x, d) => x.toLocaleString("fr-FR", { minimumFractionDigits: d, maximumFractionDigits: d });
  const DEC = { "Md€": 1, "% du PIB": 2, "points de PIB": 2, milliers: 0, "€": 0, "% du Smic": 1 };
  const UNITE = { "Md€": "Md€", "% du PIB": "% du PIB", "points de PIB": "pt de PIB", milliers: "milliers", "€": "€", "% du Smic": "% du Smic" };
  function nombre(x, unite) {
    if (x == null) return "—";
    const d = DEC[unite] != null ? DEC[unite] : 2;
    const s = Math.abs(x) < 0.5 * Math.pow(10, -d) ? fr(0, d) : (x > 0 ? "+" : "−") + fr(Math.abs(x), d);
    return s + (unite ? " " + (UNITE[unite] || unite) : "");
  }
  const SVGNS = "http://www.w3.org/2000/svg";
  const W = 150, H = 56, GAPY = 16, HAUT = 34;
  const ETATS = { non_modelise: "pas encore modélisé", reduit: "dans les multiplicateurs, sans détail", sans_effet: "sans effet ici" };

  let g = JSON.parse($("cascade-graphe").textContent);
  const st = JSON.parse($("cascade-statique").textContent);
  let k = Math.max(0, g.annees.indexOf(g.calculees[0]));
  let choisi = null, theta = 0.5, minuterie = null;
  window.cascade = { graphe: () => g, annee: () => g.annees[k], calculs: 0, pret: false };

  const noeuds = () => g.noeuds;
  const parId = () => Object.fromEntries(g.noeuds.map((n) => [n.id, n]));
  const gris = (n) => n.statut === "non_modelise" || n.statut === "reduit";
  const visibles = () => g.noeuds.filter((n) => n.statut !== "sans_effet");

  /* ------------------------------------------------------------ la mise en page */
  function colonnes() {
    const prof = {};
    const canaux = g.noeuds.filter((n) => n.type === "canal" && n.statut === "calcule");
    for (const n of canaux) prof[n.id] = 0;
    for (let i = 0; i < canaux.length; i++) {
      for (const a of g.aretes) {
        if (a.sorte === "canal" && prof[a.de] != null && prof[a.vers] != null) prof[a.vers] = Math.max(prof[a.vers], prof[a.de] + 1);
      }
    }
    const pmax = Math.min(2, Math.max(0, ...Object.values(prof)));
    const col = {};
    for (const n of visibles()) {
      if (n.type === "mesure") col[n.id] = 0;
      else if (n.type === "payeur") col[n.id] = 1;
      else if (n.type === "canal") col[n.id] = 2 + (gris(n) ? 0 : Math.min(pmax, prof[n.id] || 0));
      else col[n.id] = 3 + pmax;
    }
    return { col, n: 4 + pmax, pmax };
  }

  function placer() {
    const { col, n, pmax } = colonnes();
    const largeur = Math.max(900, n * (W + 50));
    const pas = (largeur - 2 * 12 - W) / (n - 1);
    const pos = {};
    const parCol = Array.from({ length: n }, () => []);
    for (const nd of visibles()) parCol[col[nd.id]].push(nd);
    for (let c = 0; c < n; c++) {
      const liste = parCol[c];
      if (c > 0) {
        const bary = (nd) => {
          const ys = g.aretes.filter((a) => a.vers === nd.id && pos[a.de]).map((a) => pos[a.de].y);
          return ys.length ? ys.reduce((s, y) => s + y, 0) / ys.length : 1e6;
        };
        liste.sort((a, b) => (gris(a) - gris(b)) || (bary(a) - bary(b)));
      }
      liste.forEach((nd, i) => { pos[nd.id] = { x: 12 + c * pas, y: HAUT + i * (H + GAPY), c }; });
    }
    const hauteur = HAUT + Math.max(...parCol.map((l) => l.length)) * (H + GAPY) + 10;
    const titres = [g.couches[0], g.couches[1]];
    for (let p = 0; p <= pmax; p++) titres.push(p === 0 ? g.couches[2] : "");
    titres.push(g.couches[3]);
    return { pos, largeur, hauteur, pas, titres, n };
  }

  function echelles() {
    const m = {};
    for (const a of g.aretes) for (const v of a.valeurs) if (v != null) m[a.unite] = Math.max(m[a.unite] || 0, Math.abs(v));
    return m;
  }

  function lignes(texte, max) {
    const mots = String(texte).split(/\s+/), out = [];
    let l = "";
    for (const m of mots) {
      if ((l + " " + m).trim().length > max && l) { out.push(l); l = m; } else l = (l + " " + m).trim();
    }
    if (l) out.push(l);
    if (out.length > 2) { out.length = 2; out[1] = out[1].replace(/.{0,2}$/, "…"); }
    return out;
  }

  /* ------------------------------------------------------------ le graphe */
  function el(nom, attrs, parent) {
    const e = document.createElementNS(SVGNS, nom);
    for (const [cle, v] of Object.entries(attrs || {})) e.setAttribute(cle, v);
    if (parent) parent.appendChild(e);
    return e;
  }

  function dessiner() {
    const fig = $("graphe");
    const { pos, largeur, hauteur, pas, titres } = placer();
    const ech = echelles();
    const svg = el("svg", { viewBox: `0 0 ${largeur} ${hauteur}`, role: "img",
      "aria-label": `La cascade en ${g.annees[k]} : ${visibles().length} cases, ${g.aretes.length} flèches` });
    titres.forEach((t, c) => { if (t) { const x = el("text", { x: 12 + c * pas, y: 16, class: "c-col-titre" }, svg); x.textContent = t; } });
    const couche = el("g", {}, svg);
    const montrerBoucles = $("boucles").checked;
    const parN = parId();
    const etiquettes = [];
    for (const [i, a] of g.aretes.entries()) {
      const s = pos[a.de], t = pos[a.vers];
      if (!s || !t) continue;
      const boucle = a.sorte === "boucle" || t.c <= s.c;
      if (boucle && !montrerBoucles) continue;
      const v = a.valeurs[k];
      if (v == null || Math.abs(v) < 1e-9) continue;
      const w = 1 + 13 * Math.sqrt(Math.abs(v) / (ech[a.unite] || 1));
      let d, mx, my;
      if (!boucle) {
        const x1 = s.x + W, y1 = s.y + H / 2, x2 = t.x, y2 = t.y + H / 2, dx = (x2 - x1) / 2;
        d = `M${x1},${y1} C${x1 + dx},${y1} ${x2 - dx},${y2} ${x2},${y2}`;
        mx = (x1 + x2) / 2; my = (y1 + y2) / 2;
      } else {
        const x1 = s.x + W / 2, y1 = s.y, x2 = t.x + W / 2, y2 = t.y, h = 26 + Math.abs(x1 - x2) / 6;
        d = `M${x1},${y1} C${x1},${y1 - h} ${x2},${y2 - h} ${x2},${y2}`;
        mx = (x1 + x2) / 2; my = Math.min(y1, y2) - h * 0.75;
      }
      const p = el("path", { d, "stroke-width": w.toFixed(2), "data-i": i,
        class: `c-arete ${v >= 0 ? "plus" : "moins"}${boucle ? " boucle" : ""}${choisi && choisi.arete === i ? " choisie" : ""}` }, couche);
      const titre = el("title", {}, p);
      titre.textContent = `${parN[a.de].libelle} → ${parN[a.vers].libelle} : ${nombre(v, a.unite)} — ${a.raison}`;
      p.addEventListener("click", () => choisir({ arete: i }));
      if (!boucle && a.sorte !== "agregat" && (w > 3 || a.sorte === "choc")) {
        // Le nombre près du départ de la flèche, là où elles se croisent le moins.
        const lx = s.x + W + 0.3 * (t.x - s.x - W), ly = s.y + H / 2 + 0.3 * (t.y - s.y);
        etiquettes.push([lx, ly - w / 2 - 3, nombre(v, a.unite)]);
      }
    }
    if (choisi && choisi.noeud) {
      for (const p of couche.querySelectorAll("path")) {
        const a = g.aretes[+p.dataset.i];
        if (a.de !== choisi.noeud && a.vers !== choisi.noeud) p.classList.add("estompee");
      }
    }
    const textes = el("g", {});
    // Un nombre qui tomberait sur une case ou sur un autre nombre n'est pas écrit : il se
    // lit au clic, dans le panneau.
    const poses = visibles().map((nd) => [pos[nd.id].x - 2, pos[nd.id].y - 2, pos[nd.id].x + W + 2, pos[nd.id].y + H + 2]);
    for (const [x, y, s] of etiquettes) {
      const l = 6.2 * s.length, r = [x - l / 2, y - 11, x + l / 2, y + 2];
      if (poses.some((q) => r[0] < q[2] && q[0] < r[2] && r[1] < q[3] && q[1] < r[3])) continue;
      poses.push(r);
      const t = el("text", { x, y, class: "c-nb", "text-anchor": "middle" }, textes);
      t.textContent = s;
    }
    for (const nd of visibles()) {
      const p = pos[nd.id];
      const grp = el("g", { class: `c-noeud ${nd.type}${gris(nd) ? " gris" : ""}${choisi && choisi.noeud === nd.id ? " choisi" : ""}`,
        transform: `translate(${p.x},${p.y})`, tabindex: "0", role: "button",
        "aria-label": `${nd.libelle} : ${gris(nd) ? ETATS[nd.statut] : nombre(nd.valeurs[k], nd.unite)}` }, svg);
      el("rect", { width: W, height: H, rx: 6 }, grp);
      const lib = nd.type === "mesure" ? ["La mesure", "coût statique"] : lignes(nd.libelle, 22);
      lib.forEach((l, j) => { const t = el("text", { x: 8, y: 15 + j * 13, class: "c-lib" }, grp); t.textContent = l; });
      const t = el("text", { x: 8, y: H - 8, class: gris(nd) ? "c-unite" : "c-val" }, grp);
      t.textContent = gris(nd) ? ETATS[nd.statut] : nombre(nd.valeurs[k], nd.unite);
      grp.addEventListener("click", () => choisir({ noeud: nd.id }));
      grp.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); choisir({ noeud: nd.id }); } });
    }
    svg.appendChild(textes);
    const sans = g.noeuds.filter((n) => n.statut === "sans_effet");
    fig.replaceChildren(svg);
    if (sans.length) {
      const c = document.createElement("figcaption");
      c.className = "cascade-aide";
      c.textContent = "Ouverts dans le modèle, sans effet pour cette mesure : " + sans.map((n) => n.libelle.toLowerCase()).join(", ") + ".";
      fig.appendChild(c);
    }
  }

  /* ------------------------------------------------------------ le panneau */
  function tableau(rangs) {
    const ans = g.annees.filter((_, i) => g.calculees.includes(g.annees[i]));
    const idx = ans.map((a) => g.annees.indexOf(a));
    return '<div class="defile"><table><thead><tr><th></th>' + ans.map((a) => `<th>${a}</th>`).join("") + "</tr></thead><tbody>" +
      rangs.map((r) => `<tr><td>${esc(r.libelle)}</td>` + idx.map((i) => `<td>${r.valeurs[i] == null ? "" : nombre(r.valeurs[i], "").trim()}</td>`).join("") + "</tr>").join("") +
      "</tbody></table></div>";
  }
  function premiers(qui) {
    const l = (st.premiere || []).filter((p) => !qui || p.qui === qui);
    if (!l.length) return "";
    return `<h3>La première année, la passe sur la population</h3><ul>` +
      l.map((p) => `<li>${esc(p.libelle)} : <b>${nombre(p.md, "Md€")}</b></li>`).join("") +
      `</ul><p class="source">${esc(l[0].source.split(",")[0])}, champ <code>response.deltas</code> (commit ${esc((l[0].commit || "").slice(0, 7))})</p>`;
  }
  function fiche() {
    const f = st.fiche;
    if (!f) return '<p class="source">Fiche de transmission (D-471) : pas encore écrite pour cette mesure.</p>';
    const ligne = (cle, lib) => (f[cle] == null ? "" : `<li><b>${lib}</b> : ${esc(typeof f[cle] === "string" ? f[cle] : JSON.stringify(f[cle]))}</li>`);
    return "<h3>La fiche de transmission</h3><ul>" + ligne("levier", "levier") + ligne("assiette", "assiette") + ligne("payeurs", "payeurs") + ligne("incidence", "incidence") +
      ligne("financement", "financement") + ligne("calendrier", "calendrier") + ligne("hypotheses", "hypothèses") + ligne("montant", "montant") + `</ul><p class="source">${esc(f._chemin)}</p>`;
  }
  function flux(nd) {
    const parN = parId();
    const lig = (a, autre) => `<li><button type="button" class="lien" data-arete="${g.aretes.indexOf(a)}">${esc(parN[autre].libelle)}</button> : <b>${nombre(a.valeurs[k], a.unite)}</b><br><small>${esc(a.raison)}</small></li>`;
    const entre = g.aretes.filter((a) => a.vers === nd.id && a.valeurs[k] != null && Math.abs(a.valeurs[k]) > 1e-9);
    const sort = g.aretes.filter((a) => a.de === nd.id && a.valeurs[k] != null && Math.abs(a.valeurs[k]) > 1e-9);
    return (entre.length ? `<h3>Reçoit de</h3><ul>${entre.map((a) => lig(a, a.de)).join("")}</ul>` : "") +
      (sort.length ? `<h3>Envoie vers</h3><ul>${sort.map((a) => lig(a, a.vers)).join("")}</ul>` : "");
  }
  function panneauNoeud(nd) {
    let h = `<h2>${esc(nd.libelle)}</h2>`;
    h += gris(nd) ? `<p class="gros absent">${ETATS[nd.statut]}</p>` : `<p class="gros">${nombre(nd.valeurs[k], nd.unite)}</p><p class="cascade-aide">en ${g.annees[k]}${nd.libelle_champ ? " — " + esc(nd.libelle_champ) : ""}</p>`;
    h += `<p>${esc(nd.pourquoi)}</p>`;
    if (nd.type === "mesure") {
      const m = st.mesure_texte;
      if (m) {
        h += `<p><b>Le texte :</b> ${esc(m.parametre)}</p>`;
        if (m.levier) h += `<p><b>Le levier dans le moteur :</b> ${Object.entries(m.levier).map(([p, v]) => `<code>${esc(p)}</code> = ${esc(v)}`).join(", ")}</p>`;
        if (m.note) h += `<details><summary>La note du chiffrage</summary><p>${esc(m.note)}</p></details>`;
        h += (m.sources || []).map((s) => `<p class="source">« ${esc(s.citation)} » — <a href="${esc(s.url)}">${esc(s.date || "source")}</a></p>`).join("");
      }
      if (st.mesures_texte && st.mesures_texte.length) h += "<h3>Ses mesures chiffrées</h3><ul>" + st.mesures_texte.map((m) => `<li>${esc(m.libelle)}</li>`).join("") + "</ul>";
      h += fiche() + premiers(null);
    }
    if (nd.id === "payeur:menages") h += premiers("menages");
    if (nd.id === "payeur:entreprises") h += premiers("entreprises");
    if (nd.canaux && nd.canaux.length) h += "<h3>Les canaux qu'il porte</h3><ul>" + nd.canaux.map((c) => `<li><code>${esc(c.nom)}</code> : ${esc(c.description)}</li>`).join("") + "</ul>";
    if (nd.thetas && nd.thetas.length) h += "<h3>Ses paramètres incertains (θ)</h3><ul>" + nd.thetas.map((t) => `<li><code>${esc(t.cle)}</code> à θ = ${t.theta == null ? "—" : fr(t.theta, 2)} : ${esc(t.direction)}<br><small>${esc(t.source)}${t.verifiee === false ? " (non vérifiée)" : ""}</small></li>`).join("") + "</ul>";
    h += flux(nd);
    if (nd.detail && nd.detail.length) h += "<h3>Ce qu'il écrit, année par année</h3>" + tableau(nd.detail.map((d) => ({ libelle: `${d.libelle} (${d.unite})`, valeurs: d.valeurs })));
    else if (!gris(nd)) h += tableau([{ libelle: nd.unite, valeurs: nd.valeurs }]);
    h += `<p class="source">Source : ${esc(nd.source)}</p>`;
    return h;
  }
  function panneauArete(a) {
    const parN = parId();
    return `<h2>${esc(parN[a.de].libelle)} → ${esc(parN[a.vers].libelle)}</h2><p class="gros">${nombre(a.valeurs[k], a.unite)}</p>` +
      `<p class="cascade-aide">en ${g.annees[k]}${a.sorte === "boucle" ? " — une boucle" : ""}</p><p>${esc(a.raison)}</p>` +
      tableau([{ libelle: a.unite, valeurs: a.valeurs }]) + `<p class="source">Source : ${esc(a.source)}${a.champ ? ` ; champ <code>${esc(a.champ)}</code>` : ""}</p>`;
  }
  function panneau() {
    const p = $("panneau");
    if (!choisi) return;
    const parN = parId();
    if (choisi.noeud && parN[choisi.noeud]) p.innerHTML = panneauNoeud(parN[choisi.noeud]);
    else if (choisi.arete != null && g.aretes[choisi.arete]) p.innerHTML = panneauArete(g.aretes[choisi.arete]);
    for (const b of p.querySelectorAll("button[data-arete]")) b.addEventListener("click", () => choisir({ arete: +b.dataset.arete }));
  }
  function choisir(c, defiler = true) {
    choisi = c; dessiner(); panneau();
    const p = $("panneau"), r = p.getBoundingClientRect();
    if (defiler && r.top > window.innerHeight - 80) p.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  /* ------------------------------------------------------------ la liste (téléphone) */
  function liste() {
    const parN = parId();
    const couches = [["mesure", g.couches[0]], ["payeur", g.couches[1]], ["canal", g.couches[2]], ["agregat", g.couches[3]]];
    let h = "";
    for (const [type, titre] of couches) {
      const ns = g.noeuds.filter((n) => n.type === type && n.statut !== "sans_effet").sort((a, b) => gris(a) - gris(b));
      if (!ns.length) continue;
      h += `<h2>${esc(titre)}</h2>`;
      for (const nd of ns) {
        const sort = g.aretes.filter((a) => a.de === nd.id && a.sorte !== "boucle" && a.valeurs[k] != null && Math.abs(a.valeurs[k]) > 1e-9);
        h += `<details class="${gris(nd) ? "gris" : ""}"><summary><span>${esc(nd.type === "mesure" ? "La mesure : coût statique" : nd.libelle)}</span><b>${gris(nd) ? ETATS[nd.statut] : nombre(nd.valeurs[k], nd.unite)}</b></summary><div>` +
          `<p>${esc(nd.pourquoi)}</p>` +
          sort.map((a) => `<div class="fl"><span>→ ${esc(parN[a.vers].libelle)}<br><small>${esc(a.raison)}</small></span><span>${nombre(a.valeurs[k], a.unite)}</span></div>`).join("") +
          (nd.id === "payeur:menages" ? premiers("menages") : nd.type === "mesure" ? premiers(null) : "") +
          `<p class="cascade-aide">Source : ${esc(nd.source)}</p></div></details>`;
      }
    }
    const sans = g.noeuds.filter((n) => n.statut === "sans_effet");
    if (sans.length) h += `<p class="cascade-aide">Sans effet pour cette mesure : ${sans.map((n) => esc(n.libelle.toLowerCase())).join(", ")}.</p>`;
    const ouverts = new Set([...$("liste").querySelectorAll("details[open] summary span")].map((s) => s.textContent));
    $("liste").innerHTML = h;
    for (const d of $("liste").querySelectorAll("details")) if (ouverts.has(d.querySelector("summary span").textContent)) d.open = true;
  }

  /* ------------------------------------------------------------ les années */
  function frise() {
    $("frise").innerHTML = g.annees.map((a, i) => `<button type="button" data-k="${i}" aria-pressed="${i === k}"${g.calculees.includes(a) ? "" : " disabled"}>${a}</button>`).join("");
    for (const b of $("frise").querySelectorAll("button")) b.addEventListener("click", () => { arreter(); aller(+b.dataset.k); });
  }
  function aller(i) {
    k = i;
    for (const b of $("frise").querySelectorAll("button")) b.setAttribute("aria-pressed", String(+b.dataset.k === k));
    tout();
  }
  function arreter() { if (minuterie) { clearInterval(minuterie); minuterie = null; $("jouer").textContent = "▶"; $("jouer").setAttribute("aria-label", "Faire défiler les années"); } }
  $("jouer").addEventListener("click", () => {
    if (minuterie) return arreter();
    const ks = g.calculees.map((a) => g.annees.indexOf(a));
    if (k >= ks[ks.length - 1]) aller(ks[0]);
    $("jouer").textContent = "❚❚";
    $("jouer").setAttribute("aria-label", "Arrêter");
    minuterie = setInterval(() => {
      const j = ks.indexOf(k);
      if (j < 0 || j >= ks.length - 1) return arreter();
      aller(ks[j + 1]);
    }, 1100);
  });
  function tout() { dessiner(); liste(); panneau(); }

  /* ------------------------------------------------------------ θ : le jumeau dans la page */
  let worker = null, numero = 0, enCours = false, aFaire = false;
  const attentes = new Map();
  async function charger() {
    const base = ici.dataset.pyodide;
    const texte = (r) => { if (!r.ok) throw new Error(`${r.url} : ${r.status}`); return r.text(); };
    $("etat").textContent = "Chargement du jumeau dans la page (Pyodide, une fois)…";
    const [pyodide, calcul, paquet, donnees] = await Promise.all([
      fetch(base + "pyodide.js", { integrity: ici.dataset.sri, mode: "cors", credentials: "omit" }).then(texte),
      fetch(ici.dataset.calcul).then(texte),
      fetch("jumeau-paquet.json").then((r) => r.json()),
      fetch("jumeau-donnees.json").then(texte)]);
    const url = URL.createObjectURL(new Blob([pyodide, "\n;\n", calcul], { type: "text/javascript" }));
    worker = new Worker(url);
    URL.revokeObjectURL(url);
    await new Promise((resolve, reject) => {
      worker.onmessage = (ev) => {
        const m = ev.data;
        if (m.type === "pret") resolve(m);
        else if (m.type === "erreur" && m.id === undefined) reject(new Error(m.message));
        else if (attentes.has(m.id)) {
          const a = attentes.get(m.id);
          attentes.delete(m.id);
          if (m.type === "resultat") a.resolve(m.texte); else a.reject(new Error(m.message));
        }
      };
      worker.onerror = (e) => reject(new Error(e.message || "le calcul n'a pas démarré"));
      worker.postMessage({ type: "charger", indexURL: base, paquets: ici.dataset.paquets.split(" "), paquet, donnees });
    });
    window.cascade.pret = true;
  }
  function appel(reglage) {
    return new Promise((resolve, reject) => {
      const id = ++numero;
      attentes.set(id, { resolve, reject });
      worker.postMessage({ type: "cascade", id, reglage: JSON.stringify(reglage) });
    });
  }
  async function recalculer() {
    if (enCours) { aFaire = true; return; }
    enCours = true;
    try {
      if (!worker) await charger();
      do {
        aFaire = false;
        const t = theta;
        $("etat").textContent = `Calcul à θ = ${fr(t, 2)}…`;
        const t0 = performance.now();
        const r = JSON.parse(await appel({ ...st.choix, theta_commun: t, attendus: st.attendus }));
        if (!r.noeuds.length) { $("etat").textContent = `θ = ${fr(t, 2)} : le jumeau ne calcule aucune année (${r.refus || "refus"}).`; continue; }
        g = r;
        window.cascade.calculs += 1;
        if (!g.calculees.includes(g.annees[k])) k = g.annees.indexOf(g.calculees[0]);
        frise();
        tout();
        $("etat").textContent = `Calculé à θ = ${fr(t, 2)} par le jumeau, dans la page, en ${fr((performance.now() - t0) / 1000, 1)} s.`;
      } while (aFaire);
    } catch (e) {
      $("etat").textContent = "Le calcul dans la page n'a pas abouti : " + e.message + ". Le graphe reste celui de θ½.";
    } finally { enCours = false; }
  }
  $("theta").addEventListener("input", () => { theta = Number($("theta").value); $("theta-v").textContent = theta === 0.5 ? "½" : fr(theta, 2); });
  $("theta").addEventListener("change", recalculer);
  $("boucles").addEventListener("change", dessiner);

  $("commandes").hidden = false;
  frise();
  tout();
  const premier = g.noeuds.find((n) => n.type === "mesure");
  if (premier) choisir({ noeud: premier.id }, false);
})();
