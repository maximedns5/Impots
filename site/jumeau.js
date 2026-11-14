/* La page « Le jumeau » (D-415) : Pyodide fait tourner `impots.jumeau` tel quel.
 *
 * Le script ne calcule rien lui-même : il charge Pyodide et numpy depuis le CDN nommé
 * dans la page, écrit le paquet servi avec le site (jumeau-paquet.json) dans le système de
 * fichiers du navigateur, lit les entrées (jumeau-donnees.json), puis, à chaque réglage,
 * appelle `navigateur.calculer_json` et dessine ce qu'il rend. Chaque nombre affiché porte
 * sa valeur exacte (data-v), celle que Python a rendue.
 */
"use strict";
(function () {
  const ici = document.currentScript;
  const $ = (id) => document.getElementById(id);
  const etat = $("etat");
  const fr = (x, d) => x.toLocaleString("fr-FR", { minimumFractionDigits: d, maximumFractionDigits: d });
  const signe = (x, d) => (x > 0 ? "+" : x < 0 ? "−" : "") + fr(Math.abs(x), d);
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const COULEURS = ["#2a6fb0", "#c0632b", "#3d8f5a", "#8a5cb8", "#b8475d", "#6b7f2a", "#4a9aa8", "#8c7a5b"];
  const DECIMALES = { dette: 3, solde: 2, pib: 3, emploi_total: 1, creations_societes: 0,
    fermetures_societes: 0, exportations: 2, importations: 2 };

  let py = null, donnees = null, thetaValeurs = {}, enCours = false, aFaire = false;
  window.jumeau = { pret: false, calculs: 0, dernier: null, temps: [], chargement: null };

  function choix() {
    const c = { mode: document.querySelector('input[name="mode"]:checked').value, vue: $("vue").value,
      theta: { ...thetaValeurs } };
    if ($("entree-hypothese").checked) {
      c.hypothese = { instrument: $("h-instrument").value, montant: Number($("h-montant").value),
        debut: Number($("h-debut").value), fin: Number($("h-fin").value) };
    } else c.candidat = $("candidat").value;
    return c;
  }

  function calculer() {
    if (!py) return;
    if (enCours) { aFaire = true; return; }
    enCours = true;
    etat.textContent = "Calcul…";
    setTimeout(() => {
      try {
        let c = choix();
        const t0 = performance.now();
        py.globals.set("reglage", JSON.stringify(c));
        let r = JSON.parse(py.runPython("calculer_json(S, reglage)"));
        // Les θ d'une autre mesure ou d'un autre mode : chaque curseur nouveau part de ½,
        // affiché, et le calcul se refait avec lui.
        const manquants = r.thetas.filter((t) => !(t.cle in thetaValeurs));
        if (manquants.length) {
          for (const t of manquants) thetaValeurs[t.cle] = 0.5;
          c = choix();
          py.globals.set("reglage", JSON.stringify(c));
          r = JSON.parse(py.runPython("calculer_json(S, reglage)"));
        }
        const dt = performance.now() - t0;
        window.jumeau.temps.push(dt);
        window.jumeau.calculs += 1;
        window.jumeau.dernier = { choix: c, resultat: r };
        dessiner(r);
        etat.textContent = `Calculé dans ce navigateur en ${fr(dt, 0)} ms (${r.calculees.length} année${r.calculees.length > 1 ? "s" : ""}).`;
      } catch (e) {
        etat.textContent = "Le calcul a échoué : " + e.message;
        window.jumeau.erreur = String(e);
      }
      enCours = false;
      if (aFaire) { aFaire = false; calculer(); }
    }, 0);
  }

  /* ------------------------------------------------------------------ les θ */
  function dessinerThetas(liste) {
    const zone = $("thetas");
    const vus = new Set();
    for (const t of liste) {
      vus.add(t.cle);
      let div = document.getElementById("t-" + t.cle);
      if (!div) {
        div = document.createElement("div");
        div.id = "t-" + t.cle;
        div.className = "theta";
        div.innerHTML = `<div class="ligne"><label for="r-${esc(t.cle)}">${esc(t.cle)}</label>` +
          `<input type="range" id="r-${esc(t.cle)}" min="0" max="1" step="0.01" value="${thetaValeurs[t.cle] ?? 0.5}">` +
          `<output id="o-${esc(t.cle)}"></output></div><small class="def"></small><small class="src"></small><small class="val"></small>`;
        zone.appendChild(div);
        div.querySelector("input").addEventListener("input", (ev) => {
          thetaValeurs[t.cle] = Number(ev.target.value);
          $("o-" + t.cle).textContent = "θ = " + fr(thetaValeurs[t.cle], 2);
          calculer();
        });
      }
      div.classList.toggle("non-lu", !t.lu);
      div.dataset.lu = t.lu ? "1" : "0";
      $("o-" + t.cle).textContent = "θ = " + fr(t.theta ?? thetaValeurs[t.cle] ?? 0.5, 2);
      div.querySelector(".def").textContent = `${t.bloc} — ${t.definition} (${t.unite}).`;
      div.querySelector(".src").textContent = `Source : ${t.source}${t.verifiee ? "" : " — choisie, non vérifiée"}. ${t.direction}.`;
      const v = t.valeur == null ? "" : ` Valeur au réglage : ${fr(t.valeur, 4)}.`;
      div.querySelector(".val").textContent = `À θ = 0 : ${t.a_zero} ; ½ : ${t.a_demi} ; 1 : ${t.a_un}.${v}${t.lu ? "" : " Ce mode ne le lit pas."}`;
    }
    for (const div of [...zone.children]) div.hidden = !vus.has(div.id.slice(2));
  }

  /* ------------------------------------------------------------- les séries */
  function cellule(x, d) {
    if (x === null || x === undefined) return '<td class="abs" data-v="absent">absent</td>';
    return `<td class="v" data-v="${String(x)}">${signe(x, d)}</td>`;
  }
  function niveau(x, d) {
    if (x === null || x === undefined) return '<td class="abs" data-v="absent">absent</td>';
    return `<td class="v" data-v="${String(x)}">${fr(x, d)}</td>`;
  }

  function graphique(s, annees, calculees) {
    const W = 640, H = 240, g = 46, d = 10, h = 16, b = 26;
    const parts = Object.entries(s.decomposition || {});
    parts.sort((a, b2) => Math.max(...b2[1].map((x) => Math.abs(x || 0))) - Math.max(...a[1].map((x) => Math.abs(x || 0))));
    let gardees = parts.slice(0, 7);
    if (parts.length > 7) {
      const autres = annees.map((_, k) => parts.slice(7).reduce((t, [, v]) => (v[k] == null ? t : t + v[k]), 0));
      gardees = [...gardees, ["autres", autres]];
    }
    let hautes = [0], basses = [0];
    annees.forEach((_, k) => {
      let p = 0, n = 0;
      for (const [, v] of gardees) { const x = v[k] || 0; if (x > 0) p += x; else n += x; }
      hautes.push(p, s.ecart[k] || 0); basses.push(n, s.ecart[k] || 0);
    });
    let max = Math.max(...hautes), min = Math.min(...basses);
    if (max === min) { max += 1; min -= 1; }
    const y = (v) => h + (max - v) / (max - min) * (H - h - b);
    const pas = (W - g - d) / annees.length;
    const x = (k) => g + pas * (k + 0.5);
    let svg = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(s.libelle)} : écart à la référence, par année">`;
    for (const v of [max, 0, min]) {
      svg += `<line x1="${g}" x2="${W - d}" y1="${y(v)}" y2="${y(v)}" stroke="currentColor" stroke-opacity="${v === 0 ? 0.6 : 0.15}"/>`;
      svg += `<text x="${g - 4}" y="${y(v) + 4}" font-size="11" text-anchor="end" fill="currentColor">${signe(v, Math.abs(max - min) < 1 ? 3 : 1)}</text>`;
    }
    annees.forEach((a, k) => {
      if (k % 2 === 0 || annees.length < 6) svg += `<text x="${x(k)}" y="${H - 8}" font-size="11" text-anchor="middle" fill="currentColor">${a}</text>`;
      if (!calculees.includes(a)) {
        svg += `<text x="${x(k)}" y="${y(0) - 4}" font-size="9" text-anchor="middle" fill="currentColor" fill-opacity=".6">absent</text>`;
        return;
      }
      let p = 0, n = 0;
      gardees.forEach(([, v], i) => {
        const val = v[k];
        if (!val) return;
        const base = val > 0 ? p : n;
        const haut = base + val;
        svg += `<rect x="${x(k) - pas * 0.32}" width="${pas * 0.64}" y="${Math.min(y(base), y(haut))}" height="${Math.abs(y(base) - y(haut))}" fill="${COULEURS[i % COULEURS.length]}"/>`;
        if (val > 0) p = haut; else n = haut;
      });
    });
    const points = annees.map((a, k) => (s.ecart[k] == null ? null : `${x(k)},${y(s.ecart[k])}`)).filter(Boolean);
    if (points.length > 1) svg += `<polyline points="${points.join(" ")}" fill="none" stroke="currentColor" stroke-width="1.6"/>`;
    for (const p of points) { const [px, pyy] = p.split(","); svg += `<circle cx="${px}" cy="${pyy}" r="2.6" fill="currentColor"/>`; }
    svg += "</svg>";
    const legende = gardees.map(([nom], i) => `<li><i style="background:${COULEURS[i % COULEURS.length]}"></i>${esc(nom)}</li>`).join("") +
      "<li><i style=\"background:currentColor;height:.15rem\"></i>l'écart total</li>";
    return svg + `<ul class="legende">${legende}</ul>`;
  }

  function dessinerSerie(champ, s, annees, calculees) {
    const d = DECIMALES[champ] ?? 2;
    let html = `<section class="serie" id="s-${champ}"><h3>${esc(s.libelle)} <small>(écart, ${esc(s.unite)})</small></h3>`;
    if (s.absent || !calculees.length) {
      html += `<p class="absent" data-absent="${esc(champ)}">Absent : ${esc(s.absent || "rien n'est calculé pour ce réglage")}.</p></section>`;
      return html;
    }
    html += graphique(s, annees, calculees);
    if (!Object.keys(s.decomposition || {}).length)
      html += '<p class="note">Aucun bloc de ce mode ne fait bouger ce champ : l\'écart est calculé, et nul.</p>';
    const ligne = (nom, valeurs, f, attr) => `<tr ${attr}><th scope="row">${esc(nom)}</th>` +
      annees.map((a, k) => (calculees.includes(a) ? f(valeurs[k], d) : '<td class="abs" data-v="absent">absent</td>')).join("") + "</tr>";
    html += `<details><summary>Les nombres</summary><table><thead><tr><th></th>${annees.map((a) => `<th>${a}</th>`).join("")}</tr></thead><tbody>`;
    html += ligne("écart", s.ecart, cellule, 'data-ligne="ecart"');
    for (const [nom, v] of Object.entries(s.decomposition || {})) html += ligne("dont " + nom, v, cellule, `data-ligne="part" data-part="${esc(nom)}"`);
    html += ligne(`référence (${s.niveaux})`, s.reference, niveau, 'data-ligne="reference"');
    html += ligne(`variante (${s.niveaux})`, s.variante, niveau, 'data-ligne="variante"');
    html += "</tbody></table></details></section>";
    return html;
  }

  function dessinerDeciles(dec, calculees) {
    const zone = $("deciles");
    if (dec.absent) { zone.innerHTML = `<p class="absent" data-absent="deciles">Absent : ${esc(dec.absent)}.</p>`; return; }
    const annees = Object.keys(dec.annees);
    const choisie = zone.dataset.annee && annees.includes(zone.dataset.annee) ? zone.dataset.annee : annees[0];
    const a = dec.annees[choisie];
    const W = 640, H = 220, g = 56, b = 24, h = 12;
    const vals = [0, ...a.statique, ...a.dynamique, ...a.euros_par_menage, ...a.statique.map((s, i) => s + a.dynamique[i])];
    let max = Math.max(...vals), min = Math.min(...vals);
    if (max === min) { max += 1; min -= 1; }
    const y = (v) => h + (max - v) / (max - min) * (H - h - b);
    const pas = (W - g - 10) / 10;
    let svg = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Écart du revenu disponible par ménage et par décile, ${choisie}">`;
    for (const v of [max, 0, min]) svg += `<line x1="${g}" x2="${W - 10}" y1="${y(v)}" y2="${y(v)}" stroke="currentColor" stroke-opacity="${v === 0 ? .6 : .15}"/><text x="${g - 4}" y="${y(v) + 4}" font-size="11" text-anchor="end" fill="currentColor">${signe(v, 0)} €</text>`;
    for (let i = 0; i < 10; i++) {
      const xx = g + pas * i + pas * 0.18, w = pas * 0.64;
      let p = 0, n = 0;
      [[a.statique[i], COULEURS[0]], [a.dynamique[i], COULEURS[1]]].forEach(([v, c]) => {
        if (!v) return;
        const base = v > 0 ? p : n, haut = base + v;
        svg += `<rect x="${xx}" width="${w}" y="${Math.min(y(base), y(haut))}" height="${Math.abs(y(base) - y(haut))}" fill="${c}"/>`;
        if (v > 0) p = haut; else n = haut;
      });
      svg += `<text x="${xx + w / 2}" y="${H - 6}" font-size="11" text-anchor="middle" fill="currentColor">D${i + 1}</text>`;
    }
    svg += "</svg>";
    const options = annees.map((x) => `<option${x === choisie ? " selected" : ""}>${x}</option>`).join("");
    const td = (x, dd) => cellule(x, dd);
    const pc = (x) => `<td class="v" data-v="${String(x)}">${fr(100 * x, 0)} %</td>`;
    let html = `<p><label for="annee-deciles">Année</label> <select id="annee-deciles">${options}</select></p>` + svg +
      `<ul class="legende"><li><i style="background:${COULEURS[0]}"></i>le choc statique de la mesure</li><li><i style="background:${COULEURS[1]}"></i>la dynamique : emploi, salaires, chômage</li></ul>` +
      `<p class="note">Une cellule (décile × type de ménage) n'a pas de distribution interne : un ménage y gagne ou y perd autant que les autres. Gagnant : plus de ${fr(dec.seuil, 0)} € par an.</p>` +
      `<details><summary>Les nombres, ${choisie}</summary><table><thead><tr><th>décile</th><th>€ par ménage</th><th>dont statique</th><th>dont dynamique</th><th>gagnants</th><th>perdants</th></tr></thead><tbody>`;
    for (let i = 0; i < 10; i++) html += `<tr data-decile="${i + 1}"><th scope="row">D${i + 1}</th>${td(a.euros_par_menage[i], 0)}${td(a.statique[i], 0)}${td(a.dynamique[i], 0)}${pc(a.part_gagnants[i])}${pc(a.part_perdants[i])}</tr>`;
    html += "</tbody></table></details>";
    zone.innerHTML = html;
    $("annee-deciles").addEventListener("change", (ev) => { zone.dataset.annee = ev.target.value; dessinerDeciles(dec, calculees); });
  }

  function dessiner(r) {
    dessinerThetas(r.thetas);
    const msgs = [];
    if (r.refus) msgs.push(`<p data-refus>Refusé${r.calculees.length ? ` au-delà de ${r.calculees[r.calculees.length - 1]}` : ""} : ${esc(r.refus)}</p>`);
    for (const [k, v] of Object.entries(r.mesure.non_portes || {})) msgs.push(`<p>Non porté (${esc(k)}) : ${esc(v)}</p>`);
    for (const a of r.avertissements || []) msgs.push(`<p>${esc(a)}</p>`);
    const m = r.mesure;
    msgs.unshift(`<p class="note">${esc(m.libelle)}${m.rapport ? ` — rapport <code>${esc(m.rapport)}</code>, commit <code>${esc((m.commit || "").slice(0, 7))}</code>` : ""}.</p>`);
    $("messages").innerHTML = msgs.join("");
    $("messages").className = "messages";
    $("series").innerHTML = Object.entries(r.series).map(([c, s]) => dessinerSerie(c, s, r.annees, r.calculees)).join("") ||
      `<p class="absent" data-absent="series">Rien n'est calculé pour ce réglage.</p>`;
    dessinerDeciles(r.deciles, r.calculees);
  }

  /* ---------------------------------------------------------- le chargement */
  async function charger() {
    const t0 = performance.now();
    py = await loadPyodide({ indexURL: ici.dataset.pyodide });
    await py.loadPackage(ici.dataset.paquets.split(" "), { messageCallback: () => {} });
    const t1 = performance.now();
    const [paquet, texte] = await Promise.all([
      fetch("jumeau-paquet.json").then((r) => r.json()),
      fetch("jumeau-donnees.json").then((r) => r.text())]);
    for (const [chemin, source] of Object.entries(paquet.fichiers)) {
      const dossier = "/jumeau/" + chemin.split("/").slice(0, -1).join("/");
      py.FS.mkdirTree(dossier);
      py.FS.writeFile("/jumeau/" + chemin, source);
    }
    donnees = JSON.parse(texte);
    py.globals.set("texte", texte);
    py.runPython("import sys, json\nsys.path.insert(0, '/jumeau')\n" +
      "from impots.jumeau.navigateur import Session, calculer_json\nS = Session(json.loads(texte))\ndel texte");
    const t2 = performance.now();
    window.jumeau.chargement = { pyodide_ms: t1 - t0, paquet_ms: t2 - t1, total_ms: t2 - t0 };
    window.jumeau.pret = true;
    for (const id of ["candidat", "vue", "h-instrument", "h-montant", "h-debut", "h-fin"]) $(id).addEventListener("change", calculer);
    for (const el of document.querySelectorAll('input[name="mode"], input[name="entree"]')) el.addEventListener("change", () => {
      $("bloc-hypothese").hidden = !$("entree-hypothese").checked;
      $("bloc-candidat").hidden = $("entree-hypothese").checked;
      calculer();
    });
    $("reglages").addEventListener("submit", (ev) => ev.preventDefault());
    calculer();
  }
  charger().catch((e) => { etat.textContent = "Python n'a pas pu se charger dans ce navigateur : " + e.message; window.jumeau.erreur = String(e); });
})();
