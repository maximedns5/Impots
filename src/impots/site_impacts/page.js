/* La page « Ce que ça change » (but 29, volet `tableau`, D-607).
 *
 * Elle ne calcule rien elle-même. Un programme est déjà calculé dans la page (le JSON
 * `impacts-donnees`, fait par `navigateur.impacts_json` à la construction). Une mesure
 * seule ou une proposition composée : la page charge Pyodide comme celle du jumeau
 * (`pyodide.js` vérifié par son empreinte, un Worker né d'un Blob, `jumeau-paquet.json`,
 * `jumeau-donnees.json`) et demande au Worker `impacts_json`, le même code.
 *
 * Elle ne connaît aucune dimension par son nom : chaque fiche vient de ce que rend
 * `jumeau.impacts.tableau` (question, indicateurs, bande, groupes, statut, sources,
 * limites). La vue d'ensemble ne somme rien.
 */
"use strict";
(() => {
  const $ = (id) => document.getElementById(id);
  const ici = document.currentScript;
  const D = JSON.parse($("impacts-donnees").textContent);
  const B = D.bibliotheque;
  window.impacts = { calculs: 0, erreur: null, pret: false, resultat: null };

  /* ------------------------------------------------------------ nombres */
  const nf = (d) => new Intl.NumberFormat("fr-FR", { minimumFractionDigits: d, maximumFractionDigits: d });
  function decimales(x) { const a = Math.abs(x); return a >= 100 ? 0 : a >= 10 ? 1 : 2; }
  function fr(x, d) {
    if (x === null || x === undefined || !isFinite(x)) return "—";
    const k = d === undefined ? decimales(x) : d;
    const t = nf(k).format(x);
    const zero = nf(k).format(0);
    return (x > 0 && t !== zero ? "+" : "") + (t === "-" + zero ? zero : t.replace("-", "−"));
  }
  function unite(u) { return u === "%" ? " %" : " " + u; }
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  const STATUTS = {
    "jugé": ["juge", "✓ jugé", "Un chiffrage officiel fait après coup, préenregistré, l'a confrontée"],
    "sourcé, non jugé": ["source", "◐ sourcé, non jugé", "Chaque coefficient a sa source publiée ; aucun chiffrage officiel ne l'a confrontée après coup. Ce n'est pas une prévision vérifiée."],
    "illustratif": ["illustratif", "◌ illustratif", "Un ordre de grandeur : une partie de la chaîne est déclarée (une loi simple, une mesure mise à l'échelle ou décalée), pas chiffrée par une passe."],
  };
  function statut(d) {
    const [c, lib] = STATUTS[d.statut] || ["", d.statut];
    return `<span class="i-statut ${c}">${esc(lib)}${d.juge ? " · " + esc(d.juge) : ""}</span>`;
  }
  function signe(p, sens) {
    if (!p || p.signe === null) return "";
    if (p.signe === "mieux") return '<span class="i-signe mieux">▲ mieux</span>';
    if (p.signe === "moins bien") return '<span class="i-signe moins">▼ moins bien</span>';
    if (p.signe === "nul") return '<span class="i-signe">● sans effet</span>';
    return `<span class="i-signe">${p.valeur > 0 ? "↑" : "↓"} ni mieux ni moins bien</span>`;
  }

  /* ------------------------------------------------------------ le choix */
  const onglets = ["programme", "mesure", "composer"];
  let onglet = "programme";
  function montrer(o) {
    onglet = o;
    for (const x of onglets) {
      $("o-" + x).setAttribute("aria-selected", String(x === o));
      $("p-" + x).hidden = x !== o;
    }
  }
  for (const x of onglets) $("o-" + x).addEventListener("click", () => {
    montrer(x);
    if (x === "programme") choisir({ candidat: $("programme").value });
    if (x === "mesure") choisir({ candidat: $("mesure").value });
    if (x === "composer" && !$("composition").children.length) ajouterMesure();
  });
  $("programme").addEventListener("change", () => choisir({ candidat: $("programme").value }));
  $("mesure").addEventListener("change", () => choisir({ candidat: $("mesure").value }));

  function optionsMesures(choisie) {
    return B.groupes.map((g) => {
      const items = [];
      if (g.programme) items.push(`<option value="${esc(g.programme)}"${g.programme === choisie ? " selected" : ""}>le programme entier</option>`);
      for (const m of g.mesures) items.push(`<option value="${esc(m.cle)}"${m.cle === choisie ? " selected" : ""}>${esc(m.libelle)}</option>`);
      return `<optgroup label="${esc(g.groupe)}">${items.join("")}</optgroup>`;
    }).join("");
  }
  let numeroLigne = 0;
  function ajouterMesure(cle) {
    const li = document.createElement("li");
    const n = ++numeroLigne;
    li.dataset.sorte = "mesure";
    const premiere = cle || (B.groupes.find((g) => g.mesures.length) || B.groupes[0]).mesures[0]?.cle;
    const dec = Array.from({ length: B.decalage_max + 1 }, (_, i) => `<option value="${i}">${i === 0 ? "dès son année" : "+" + i + " an" + (i > 1 ? "s" : "")}</option>`).join("");
    li.innerHTML = `<div class="i-quoi"><label class="i-cache" for="m${n}">Mesure</label><select id="m${n}" data-r="cle">${optionsMesures(premiere)}</select>
      <button type="button" class="i-retirer" aria-label="Retirer cette mesure">×</button></div>
      <div class="i-reglages"><label>intensité <input type="range" data-r="echelle" min="0.1" max="${B.echelle_max}" step="0.1" value="1"> <output>×1</output></label>
      <label>entrée <select data-r="decalage">${dec}</select></label></div>`;
    const out = li.querySelector("output"), r = li.querySelector("input[type=range]");
    r.addEventListener("input", () => { out.textContent = "×" + nf(Number(r.value) % 1 ? 1 : 0).format(Number(r.value)); });
    li.querySelector(".i-retirer").addEventListener("click", () => li.remove());
    $("composition").appendChild(li);
  }
  function ajouterLoi() {
    const li = document.createElement("li");
    const n = ++numeroLigne;
    li.dataset.sorte = "loi";
    const ann = (v) => B.annees.map((a) => `<option${a === v ? " selected" : ""}>${a}</option>`).join("");
    const inst = Object.entries(B.hypotheses).map(([k, v]) => `<option value="${esc(k)}">${esc(v)}</option>`).join("");
    li.innerHTML = `<div class="i-quoi"><label class="i-cache" for="h${n}">Loi simple</label><select id="h${n}" data-r="instrument">${inst}</select>
      <button type="button" class="i-retirer" aria-label="Retirer cette loi">×</button></div>
      <div class="i-reglages"><label>coût pour l'État <input type="number" data-r="montant" value="10" step="1"> Md€ par an</label>
      <label>de <select data-r="debut">${ann(B.annees[1])}</select></label><label>à <select data-r="fin">${ann(B.annees[B.annees.length - 1])}</select></label></div>
      <p class="i-aide">Positif : une baisse d'impôt ou une dépense en plus ; négatif : une hausse d'impôt ou une économie. Une loi simple n'a pas de passe sur la population : tout ce qu'elle touche est illustratif.</p>`;
    li.querySelector(".i-retirer").addEventListener("click", () => li.remove());
    $("composition").appendChild(li);
  }
  $("ajouter-mesure").addEventListener("click", () => ajouterMesure());
  $("ajouter-loi").addEventListener("click", ajouterLoi);
  function composition() {
    return [...$("composition").children].map((li) => {
      const v = (k) => li.querySelector(`[data-r="${k}"]`).value;
      if (li.dataset.sorte === "loi") return { hypothese: { instrument: v("instrument"), montant: Number(v("montant")), debut: Number(v("debut")), fin: Number(v("fin")) } };
      return { candidat: v("cle"), echelle: Number(v("echelle")), decalage: Number(v("decalage")) };
    });
  }
  $("calculer").addEventListener("click", () => {
    const c = composition();
    if (!c.length) { $("etat").textContent = "Ajoutez au moins une mesure ou une loi."; return; }
    choisir({ composition: c });
  });

  /* ------------------------------------------------------------ le calcul */
  let worker = null, numero = 0, chargement = null;
  const attentes = new Map();
  function charger() {
    if (chargement) return chargement;
    chargement = (async () => {
      const base = ici.dataset.pyodide;
      const texte = (r) => { if (!r.ok) throw new Error(`${r.url} : ${r.status}`); return r.text(); };
      $("etat").textContent = "Chargement du jumeau dans la page (une fois, quelques secondes)…";
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
      window.impacts.pret = true;
    })();
    chargement.catch(() => { chargement = null; });
    return chargement;
  }
  function appel(reglage) {
    return new Promise((resolve, reject) => {
      const id = ++numero;
      attentes.set(id, { resolve, reject });
      worker.postMessage({ type: "impacts", id, reglage: JSON.stringify(reglage) });
    });
  }
  let demande = 0;
  async function choisir(reglage) {
    const ma = ++demande;
    if (reglage.candidat && D.precalcul[reglage.candidat]) {
      $("etat").textContent = "";
      dessiner(D.precalcul[reglage.candidat]);
      try { history.replaceState(null, "", "#" + reglage.candidat); } catch (e) { /* page locale */ }
      return;
    }
    try {
      await charger();
      if (ma !== demande) return;
      $("etat").textContent = "Le jumeau calcule…";
      const t0 = performance.now();
      const r = JSON.parse(await appel(reglage));
      if (ma !== demande) return;
      dessiner(r);
      $("etat").textContent = `Calculé dans la page en ${fr((performance.now() - t0) / 1000, 1).replace("+", "")} s.`;
      if (reglage.candidat) try { history.replaceState(null, "", "#" + reglage.candidat); } catch (e) { /* page locale */ }
    } catch (e) {
      // Une erreur de Python arrive avec sa pile : la page n'en dit que la raison.
      const brut = String(e.message || e).trim().split("\n").filter((l) => l.trim()).pop() || "";
      window.impacts.erreur = brut.replace(/^[\w.]*(Error|Exception) : |^[\w.]*(Error|Exception): /, "");
      $("etat").textContent = "Le calcul n'a pas abouti : " + window.impacts.erreur;
    }
  }

  /* ------------------------------------------------------------ le dessin */
  function ligneReglage(r) {
    const g = r.reglage || {};
    const mode = r.mode === "structurel"
      ? `le jumeau complet, population ${r.vue === "figee" ? "figée de 2026" : "vieillie"}`
      : "la chaîne des études (sans les ménages ni les entreprises)";
    const n = g.tirages ? `, bande sur ${g.tirages} tirages` : "";
    return `Calculé par ${mode}, chaque paramètre incertain au centre (θ = ½)${n}.` +
      (r.pourquoi_mode ? ` <b>Pourquoi pas le jumeau complet :</b> ${esc(r.pourquoi_mode)}.` : "");
  }
  function dessiner(r) {
    window.impacts.resultat = r;
    window.impacts.calculs += 1;
    $("titre-resultat").textContent = r.mesure ? r.mesure.libelle : "";
    $("reglage").innerHTML = ligneReglage(r);
    const av = [];
    if (r.refus) av.push(`<div class="i-avert i-refus"><b>Le jumeau ne calcule ${r.calculees && r.calculees.length ? "que jusqu'en " + r.calculees[r.calculees.length - 1] : "aucune année"} :</b> ${esc(r.refus)}</div>`);
    if (r.composition) av.push(`<div class="i-avert"><b>La proposition :</b><ul>${r.composition.map((m) => `<li>${esc(m.libelle)}${m.transformee ? " — <i>" + esc(m.transformee) + "</i>" : ""}</li>`).join("")}</ul></div>`);
    if (r.avertissements && r.avertissements.length) av.push(`<div class="i-avert"><ul>${r.avertissements.map((a) => `<li>${esc(a)}</li>`).join("")}</ul></div>`);
    const mods = Object.entries(r.modules_en_erreur || {});
    if (mods.length) av.push(`<div class="i-avert i-refus"><b>Dimensions qui ne se chargent pas :</b><ul>${mods.map(([m, e]) => `<li>${esc(m)} : ${esc(e)}</li>`).join("")}</ul></div>`);
    $("avertissements").innerHTML = av.join("");
    $("ensemble").innerHTML = (r.ensemble || []).map(carte).join("") ||
      '<p class="i-aide">Aucune dimension calculée.</p>';
    $("fiches").innerHTML = "";
    for (const d of r.dimensions || []) $("fiches").appendChild(fiche(d));
  }
  function carte(e) {
    if (e.erreur) return `<a class="i-carte i-erreur" href="#f-${esc(e.cle)}"><h3>${esc(e.cle)}</h3><p class="i-q">Non calculée : ${esc(e.erreur)}</p></a>`;
    const t = e.tete;
    if (!t) return `<a class="i-carte" href="#f-${esc(e.cle)}"><h3>${esc(e.titre)}</h3><p class="i-q">${esc(e.question)}</p><p class="i-lib">Aucun indicateur calculé ici.</p>${statut(e)}</a>`;
    const h = t.horizon;
    const bande = h.bas !== null && h.bas !== undefined ? `<p class="i-bande">entre ${fr(h.bas)} et ${fr(h.haut)}${unite(t.unite)}</p>` : "";
    return `<a class="i-carte" href="#f-${esc(e.cle)}" data-cle="${esc(e.cle)}"><h3>${esc(e.titre)}</h3><p class="i-q">${esc(e.question)}</p>
      <p class="i-lib">${esc(t.libelle)}, en ${h.annee}</p>
      <p class="i-gros" data-v="${h.valeur}">${fr(h.valeur)}<small>${esc(unite(t.unite))}</small></p>${bande}
      <p class="i-bande">${t.debut.annee} : ${fr(t.debut.valeur)}${esc(unite(t.unite))}</p>
      <div>${signe(h, t.sens)} ${statut(e)}</div></a>`;
  }

  function fiche(d) {
    const s = document.createElement("section");
    s.className = "i-fiche";
    s.id = "f-" + d.cle;
    s.dataset.cle = d.cle;
    if (d.erreur) {
      s.innerHTML = `<h3>${esc(d.cle)}</h3><div class="i-avert i-refus"><b>Non calculée :</b> ${esc(d.erreur)}</div>`;
      return s;
    }
    const [, , explication] = STATUTS[d.statut] || ["", "", ""];
    const inds = d.indicateurs || [];
    s.innerHTML = `<h3>${esc(d.titre)}</h3><p class="i-question">${esc(d.question)}</p>
      <div>${statut(d)}</div><p class="i-statut-texte">${esc(explication)}</p>
      ${inds.length > 1 ? `<div class="i-indics" role="group" aria-label="L'indicateur">${inds.map((i, k) => `<button type="button" aria-pressed="${k === 0}" data-k="${k}">${esc(i.libelle)}</button>`).join("")}</div>` : ""}
      <div class="i-corps"><div class="i-vue"></div><div class="i-cote">
        <h4>Ce qu'il faut savoir</h4><ul>${(d.limites || []).map((l) => `<li>${esc(l)}</li>`).join("")}</ul>
        <h4>Sources</h4><ul>${(d.sources || []).map((x) => `<li>${esc(x.document)}<br><span class="i-source">${esc(x.lieu)} — ${esc(x.valeur)}</span></li>`).join("")}</ul>
      </div></div>`;
    const vue = s.querySelector(".i-vue");
    const montrerIndic = (k) => {
      for (const b of s.querySelectorAll(".i-indics button")) b.setAttribute("aria-pressed", String(+b.dataset.k === k));
      vue.innerHTML = "";
      if (inds[k]) vue.appendChild(indicateur(inds[k], d.annees));
      else vue.innerHTML = '<p class="i-aide">Aucun indicateur calculé ici.</p>';
    };
    for (const b of s.querySelectorAll(".i-indics button")) b.addEventListener("click", () => montrerIndic(+b.dataset.k));
    montrerIndic(0);
    return s;
  }

  function indicateur(ind, annees) {
    const div = document.createElement("div");
    const v = ind.valeurs || [];
    const k = v.map((x, i) => (x === null ? -1 : i)).filter((i) => i >= 0);
    const fin = k.length ? k[k.length - 1] : -1;
    const tete = fin >= 0 ? `<p class="i-gros" data-v="${v[fin]}">${fr(v[fin])}<small>${esc(unite(ind.unite))} en ${annees[fin]}</small></p>` +
      (ind.bas ? `<p class="i-bande">bande : de ${fr(ind.bas[fin])} à ${fr(ind.haut[fin])}${esc(unite(ind.unite))}</p>` : "") : "";
    div.innerHTML = tete;
    div.appendChild(courbe(ind, annees));
    if (ind.par_groupe && Object.keys(ind.par_groupe).length) div.appendChild(groupes(ind, annees, fin));
    const lignes = annees.map((a, i) => `<tr><td>${a}</td><td data-v="${v[i]}">${fr(v[i])}</td>${ind.bas ? `<td>${fr(ind.bas[i])}</td><td>${fr(ind.haut[i])}</td>` : ""}</tr>`).join("");
    const det = document.createElement("details");
    det.innerHTML = `<summary>Les nombres, année par année</summary><div class="i-defile"><table class="i-table"><thead><tr><th>année</th><th>${esc(ind.unite)}</th>${ind.bas ? "<th>bas (5 %)</th><th>haut (95 %)</th>" : ""}</tr></thead><tbody>${lignes}</tbody></table></div>`;
    div.appendChild(det);
    return div;
  }

  function graduations(lo, hi, n) {
    const pas0 = (hi - lo) / n || 1;
    const p = Math.pow(10, Math.floor(Math.log10(pas0)));
    const pas = [1, 2, 2.5, 5, 10].map((m) => m * p).find((x) => x >= pas0) || pas0;
    const out = [];
    for (let x = Math.ceil(lo / pas) * pas; x <= hi + 1e-9 * pas; x += pas) out.push(Math.abs(x) < pas * 1e-9 ? 0 : x);
    return out;
  }
  const NS = "http://www.w3.org/2000/svg";
  function courbe(ind, annees) {
    const fig = document.createElement("figure");
    fig.className = "i-graphe";
    const W = 560, H = 240, g = 46, dr = 12, h = 14, bs = 26;
    const v = ind.valeurs || [], lo0 = [], hi0 = [];
    v.forEach((x, i) => {
      if (x === null) return;
      lo0.push(x, ind.bas ? ind.bas[i] ?? x : x); hi0.push(x, ind.haut ? ind.haut[i] ?? x : x);
    });
    let lo = Math.min(0, ...lo0), hi = Math.max(0, ...hi0);
    if (hi - lo < 1e-12) { hi += 1; lo -= 1; }
    const marge = (hi - lo) * 0.06; lo -= marge; hi += marge;
    const X = (i) => g + (annees.length > 1 ? i * (W - g - dr) / (annees.length - 1) : (W - g - dr) / 2);
    const Y = (y) => h + (hi - y) * (H - h - bs) / (hi - lo);
    const parts = [];
    for (const t of graduations(lo, hi, 4)) {
      parts.push(`<line class="${t === 0 ? "g-zero" : "g-grille"}" x1="${g}" x2="${W - dr}" y1="${Y(t)}" y2="${Y(t)}"/>`);
      parts.push(`<text class="g-texte" x="${g - 6}" y="${Y(t) + 4}" text-anchor="end">${fr(t, decimales(Math.max(Math.abs(lo), Math.abs(hi))) )}</text>`);
    }
    if (!graduations(lo, hi, 4).includes(0)) parts.push(`<line class="g-zero" x1="${g}" x2="${W - dr}" y1="${Y(0)}" y2="${Y(0)}"/>`);
    const pasA = annees.length > 6 ? 2 : 1;
    annees.forEach((a, i) => { if (i % pasA === 0 || i === annees.length - 1) parts.push(`<text class="g-texte" x="${X(i)}" y="${H - 8}" text-anchor="middle">${a}</text>`); });
    if (ind.bas && ind.haut) {
      const idx = v.map((x, i) => i).filter((i) => ind.bas[i] !== null && ind.haut[i] !== null && v[i] !== null);
      if (idx.length > 1) {
        const haut = idx.map((i) => `${X(i)},${Y(ind.haut[i])}`), bas = idx.slice().reverse().map((i) => `${X(i)},${Y(ind.bas[i])}`);
        parts.push(`<polygon class="g-bande" points="${haut.concat(bas).join(" ")}"/>`);
      }
    }
    let chemin = "", debut = true;
    v.forEach((x, i) => { if (x === null) { debut = true; return; } chemin += `${debut ? "M" : "L"}${X(i)},${Y(x)}`; debut = false; });
    parts.push(`<path class="g-ligne" d="${chemin}"/>`);
    const k = v.map((x, i) => (x === null ? -1 : i)).filter((i) => i >= 0);
    if (k.length) { const f = k[k.length - 1]; parts.push(`<circle class="g-point" cx="${X(f)}" cy="${Y(v[f])}" r="4"/>`); }
    parts.push(`<line class="g-curseur" x1="0" x2="0" y1="${h}" y2="${H - bs}" visibility="hidden"/><rect x="${g}" y="0" width="${W - g - dr}" height="${H}" fill="transparent"/>`);
    fig.innerHTML = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(ind.libelle)}, écart à la trajectoire sans la mesure, ${esc(ind.unite)}, de ${annees[0]} à ${annees[annees.length - 1]}">${parts.join("")}</svg>
      <figcaption>${esc(ind.libelle)} : écart à la trajectoire sans la mesure (${esc(ind.unite)})${ind.bas ? " ; en clair, la bande de 5 à 95 %" : ""}.</figcaption>`;
    const svg = fig.querySelector("svg"), cur = svg.querySelector(".g-curseur");
    const bulle = document.createElement("div");
    bulle.className = "i-bulle"; bulle.hidden = true; fig.appendChild(bulle);
    const bouger = (ev) => {
      const r = svg.getBoundingClientRect();
      const x = (ev.clientX - r.left) * W / r.width;
      let i = 0, best = Infinity;
      annees.forEach((_, j) => { const dd = Math.abs(X(j) - x); if (dd < best) { best = dd; i = j; } });
      if (v[i] === null) { bulle.hidden = true; cur.setAttribute("visibility", "hidden"); return; }
      cur.setAttribute("x1", X(i)); cur.setAttribute("x2", X(i)); cur.setAttribute("visibility", "visible");
      bulle.innerHTML = `<b>${annees[i]}</b> : ${fr(v[i])}${esc(unite(ind.unite))}` + (ind.bas ? `<br>de ${fr(ind.bas[i])} à ${fr(ind.haut[i])}` : "");
      bulle.hidden = false;
      const px = X(i) * r.width / W;
      bulle.style.left = Math.min(Math.max(0, px - 60), r.width - 140) + "px";
      bulle.style.top = (Y(v[i]) * r.height / H - 48) + "px";
    };
    svg.addEventListener("pointermove", bouger);
    svg.addEventListener("pointerdown", bouger);
    svg.addEventListener("pointerleave", () => { bulle.hidden = true; cur.setAttribute("visibility", "hidden"); });
    return fig;
  }

  function groupes(ind, annees, fin) {
    const box = document.createElement("div");
    box.className = "i-groupes";
    const opts = annees.map((a, i) => (ind.valeurs[i] === null ? "" : `<option value="${i}"${i === fin ? " selected" : ""}>${a}</option>`)).join("");
    box.innerHTML = `<label>Par groupe, en <select>${opts}</select></label><figure class="i-graphe"></figure>`;
    const fig = box.querySelector("figure"), sel = box.querySelector("select");
    const barres = () => {
      const i = Number(sel.value);
      const noms = Object.keys(ind.par_groupe), vals = noms.map((n) => ind.par_groupe[n][i]);
      const W = 560, gl = 120, gr = 70, hb = 20, esp = 4, H = noms.length * (hb + esp) + 8;
      const m = Math.max(1e-12, ...vals.map((x) => Math.abs(x ?? 0)));
      const neg = vals.some((x) => x < 0), pos = vals.some((x) => x > 0);
      const zero = neg && pos ? gl + (W - gl - gr) / 2 : neg ? W - gr : gl;
      const echelle = (neg && pos ? (W - gl - gr) / 2 : W - gl - gr) / m;
      const parts = [`<line class="g-zero" x1="${zero}" x2="${zero}" y1="0" y2="${H}"/>`];
      noms.forEach((n, j) => {
        const x = vals[j], y = 4 + j * (hb + esp);
        parts.push(`<text class="g-texte" x="${gl - 8}" y="${y + hb / 2 + 4}" text-anchor="end">${esc(n)}</text>`);
        if (x === null || x === undefined) { parts.push(`<text class="g-texte" x="${zero + 6}" y="${y + hb / 2 + 4}">absent</text>`); return; }
        const w = Math.abs(x) * echelle, x0 = x >= 0 ? zero : zero - w;
        const c = ind.sens === 0 ? "neutre" : x * ind.sens >= 0 ? "gain" : "perte";
        parts.push(`<rect class="g-barre ${c}" x="${x0}" y="${y}" width="${Math.max(w, 1)}" height="${hb}" rx="3"><title>${esc(n)} : ${fr(x)}${esc(unite(ind.unite))}</title></rect>`);
        parts.push(`<text class="g-texte" x="${x >= 0 ? x0 + w + 4 : x0 - 4}" y="${y + hb / 2 + 4}" text-anchor="${x >= 0 ? "start" : "end"}">${fr(x)}</text>`);
      });
      fig.innerHTML = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(ind.libelle)} par groupe en ${annees[i]}">${parts.join("")}</svg>`;
    };
    sel.addEventListener("change", barres);
    barres();
    return box;
  }

  /* ------------------------------------------------------------ au départ */
  const voulu = decodeURIComponent((location.hash || "").slice(1));
  const estProgramme = B.groupes.some((g) => g.programme === voulu);
  const estMesure = !estProgramme && B.groupes.some((g) => g.mesures.some((m) => m.cle === voulu));
  if (estMesure) { montrer("mesure"); $("mesure").value = voulu; choisir({ candidat: voulu }); }
  else {
    const p = estProgramme ? voulu : D.defaut;
    if (p) { $("programme").value = p; choisir({ candidat: p }); }
  }
})();
