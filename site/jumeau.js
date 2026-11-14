/* La page « Le jumeau » (D-415, D-419) : Pyodide fait tourner `impots.jumeau` tel quel,
 * dans un Web Worker.
 *
 * Ce script ne calcule rien : il télécharge `pyodide.js` en vérifiant son empreinte
 * (sha384, `fetch` avec `integrity`), crée le Worker depuis un Blob qui porte ce fichier
 * vérifié suivi du script de calcul servi avec le site (jumeau-calcul.js), lui passe le
 * paquet (jumeau-paquet.json) et les entrées (jumeau-donnees.json), puis, à chaque réglage,
 * lui demande `navigateur.calculer_json` et dessine ce qu'il rend. La page ne fige pas
 * pendant un calcul. Chaque nombre affiché porte sa valeur exacte (data-v), celle que
 * Python a rendue ; chaque année qu'une convention a ventilée porte sa marque.
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
  /* Les θ, regroupés par famille de blocs ; un bloc inconnu fait sa propre famille. */
  const FAMILLES = [
    ["macro", "Macro (Mésange, investissement)", ["mesange", "investissement"]],
    ["entreprises", "Entreprises", ["naissances", "creations", "fermetures", "productivite", "implantation"]],
    ["commerce", "Commerce extérieur", ["commerce"]],
    ["menages", "Ménages et travail", ["emploi", "salaires", "consommation"]],
  ];
  const famille = (bloc) => (FAMILLES.find(([, , blocs]) => blocs.includes(bloc)) || [bloc])[0];
  const LARGE = window.matchMedia("(min-width: 64rem)");

  let worker = null, thetaValeurs = {}, enCours = false, aFaire = false, numero = 0;
  const attentes = new Map();
  window.jumeau = { pret: false, calculs: 0, dernier: null, temps: [], chargement: null };

  function choix() {
    const mode = document.querySelector('input[name="mode"]:checked').value;
    const c = { mode, vue: $("vue").value, theta: { ...thetaValeurs } };
    if ($("entree-hypothese").checked) {
      c.hypothese = { instrument: $("h-instrument").value, montant: Number($("h-montant").value),
        debut: Number($("h-debut").value), fin: Number($("h-fin").value) };
    } else {
      c.candidat = $("candidat").value;
      if (mode === "structurel" && $("convention").checked) c.convention = $("convention").value;
    }
    return c;
  }

  function appel(c) {
    return new Promise((resolve, reject) => {
      const id = ++numero;
      attentes.set(id, { resolve, reject });
      worker.postMessage({ type: "calculer", id, reglage: JSON.stringify(c) });
    });
  }

  async function calculer() {
    if (!worker) return;
    if (enCours) { aFaire = true; return; }
    enCours = true;
    etat.textContent = "Calcul…";
    document.body.classList.add("calcule");
    try {
      let c = choix();
      const t0 = performance.now();
      let r = JSON.parse(await appel(c));
      // Les θ d'une autre mesure ou d'un autre mode : chaque curseur nouveau part de ½,
      // affiché, et le calcul se refait avec lui.
      const manquants = r.thetas.filter((t) => !(t.cle in thetaValeurs));
      if (manquants.length) {
        for (const t of manquants) thetaValeurs[t.cle] = 0.5;
        c = choix();
        r = JSON.parse(await appel(c));
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
    document.body.classList.remove("calcule");
    enCours = false;
    if (aFaire) { aFaire = false; calculer(); }
  }

  /* ------------------------------------------------------------ la convention */
  let conv = null;          // {annees: Set, noms, titre} du dernier résultat, ou null
  let ident = null;         // l'identifiant de la mesure du dernier résultat
  const touche = (a) => conv !== null && conv.annees.has(Number(a));
  const marque = () => `<sup><a class="conv" href="#def-convention" title="${esc(conv.titre)}">c</a></sup>`;
  const attr = () => ` data-convention="${esc(conv.noms)}"`;

  /* ------------------------------------------------------------------ les θ */
  function court(t) {
    let p = t.definition.includes(" : ") ? t.definition.split(" : ").slice(1).join(" : ") : t.definition;
    for (const sep of [" ; ", " (", ", "]) { const i = p.indexOf(sep); if (i >= 20) p = p.slice(0, i); }
    if (p.length > 110) p = p.slice(0, 107).replace(/\s+\S*$/, "") + "…";
    return p.charAt(0).toUpperCase() + p.slice(1);
  }

  function groupe(fam) {
    let g = document.getElementById("g-" + fam);
    if (g) return g;
    g = document.createElement("details");
    g.id = "g-" + fam;
    g.className = "groupe";
    g.dataset.famille = fam;
    const nom = (FAMILLES.find(([f]) => f === fam) || [fam, fam])[1];
    g.innerHTML = `<summary>${esc(nom)} <span class="compte"></span></summary><div class="liste"></div>`;
    const ordre = FAMILLES.map(([f]) => f), rang = (f) => (ordre.includes(f) ? ordre.indexOf(f) : ordre.length);
    const apres = [...$("thetas").children].find((x) => rang(x.dataset.famille) > rang(fam));
    $("thetas").insertBefore(g, apres || null);
    return g;
  }

  function dessinerThetas(liste) {
    const vus = new Set();
    for (const t of liste) {
      vus.add(t.cle);
      let div = document.getElementById("t-" + t.cle);
      if (!div) {
        div = document.createElement("div");
        div.id = "t-" + t.cle;
        div.className = "theta";
        div.innerHTML = `<label for="r-${esc(t.cle)}">${esc(court(t))}</label>` +
          `<div class="curseur"><input type="range" id="r-${esc(t.cle)}" min="0" max="1" step="0.01" value="${thetaValeurs[t.cle] ?? 0.5}">` +
          `<output id="o-${esc(t.cle)}"></output></div>` +
          `<details class="detail"><summary>détail · <code>${esc(t.cle)}</code></summary>` +
          `<small class="def"></small><small class="src"></small><small class="val"></small></details>`;
        groupe(famille(t.bloc)).querySelector(".liste").appendChild(div);
        div.querySelector("input").addEventListener("input", (ev) => {
          thetaValeurs[t.cle] = Number(ev.target.value);
          $("o-" + t.cle).textContent = "θ = " + fr(thetaValeurs[t.cle], 2);
          calculer();
        });
      }
      div.classList.toggle("non-lu", !t.lu);
      div.dataset.lu = t.lu ? "1" : "0";
      div.dataset.bloc = t.bloc;
      $("o-" + t.cle).textContent = "θ = " + fr(t.theta ?? thetaValeurs[t.cle] ?? 0.5, 2);
      div.querySelector(".def").textContent = `Bloc ${t.bloc}. ${t.definition} (${t.unite}).`;
      div.querySelector(".src").textContent = `Source : ${t.source}${t.verifiee ? "" : " — choisie, non vérifiée"}. ${t.direction}.`;
      const v = t.valeur == null ? "" : ` Valeur au réglage : ${fr(t.valeur, 4)}.`;
      div.querySelector(".val").textContent = `À θ = 0 : ${t.a_zero} ; ½ : ${t.a_demi} ; 1 : ${t.a_un}.${v}${t.lu ? "" : " Ce mode ne le lit pas."}`;
    }
    for (const g of $("thetas").children) {
      const items = [...g.querySelectorAll(".theta")];
      for (const div of items) div.hidden = !vus.has(div.id.slice(2));
      const montres = items.filter((d) => !d.hidden), lus = montres.filter((d) => d.dataset.lu === "1");
      g.hidden = !montres.length;
      g.querySelector(".compte").textContent = `${lus.length} lu${lus.length > 1 ? "s" : ""} sur ${montres.length}`;
      if (!("vu" in g.dataset)) { g.open = lus.length > 0; g.dataset.vu = ""; }
    }
  }

  /* ------------------------------------------------------------- les séries */
  const ABSENT = '<td class="abs" data-v="absent">absent</td>';
  function cellule(x, d, a) {
    if (x === null || x === undefined) return ABSENT;
    const c = touche(a);
    return `<td class="v" data-v="${String(x)}"${c ? attr() : ""}>${signe(x, d)}${c ? marque() : ""}</td>`;
  }
  function niveau(x, d, a, variante) {
    if (x === null || x === undefined) return ABSENT;
    const c = variante && touche(a);
    return `<td class="v" data-v="${String(x)}"${c ? attr() : ""}>${fr(x, d)}${c ? marque() : ""}</td>`;
  }

  function graphique(s, annees, calculees) {
    const W = 440, H = 220, g = 50, d = 8, h = 16, b = 24;
    const parts = Object.entries(s.decomposition || {});
    parts.sort((a, b2) => Math.max(...b2[1].map((x) => Math.abs(x || 0))) - Math.max(...a[1].map((x) => Math.abs(x || 0))));
    let gardees = parts.slice(0, 7);
    if (parts.length > 7) {
      const autres = annees.map((_, k) => parts.slice(7).reduce((t, [, v]) => (v[k] == null ? t : t + v[k]), 0));
      gardees = [...gardees, ["autres", autres]];
    }
    const hautes = [0], basses = [0];
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
    const marquees = annees.map((a, k) => (touche(a) && calculees.includes(a) ? k : null)).filter((k) => k !== null);
    if (marquees.length) {
      const k0 = marquees[0], k1 = marquees[marquees.length - 1];
      svg += `<rect class="bande-conv" x="${g + pas * k0}" width="${pas * (k1 - k0 + 1)}" y="0" height="${H - b}" fill="currentColor" fill-opacity=".07"/>`;
      svg += `<text x="${g + pas * k0 + 3}" y="11" font-size="10" fill="currentColor" fill-opacity=".8">c : convention</text>`;
    }
    for (const v of [max, 0, min]) {
      svg += `<line x1="${g}" x2="${W - d}" y1="${y(v)}" y2="${y(v)}" stroke="currentColor" stroke-opacity="${v === 0 ? 0.6 : 0.15}"/>`;
      svg += `<text x="${g - 4}" y="${y(v) + 4}" font-size="11" text-anchor="end" fill="currentColor">${signe(v, Math.abs(max - min) < 1 ? 3 : 1)}</text>`;
    }
    annees.forEach((a, k) => {
      if (k % 2 === 0 || annees.length < 6) svg += `<text x="${x(k)}" y="${H - 7}" font-size="11" text-anchor="middle" fill="currentColor">${a}</text>`;
      if (!calculees.includes(a)) {
        svg += `<text x="${x(k)}" y="${y(0) - 4}" font-size="9" text-anchor="start" fill="currentColor" fill-opacity=".6" transform="rotate(-90 ${x(k)} ${y(0) - 4})">absent</text>`;
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
    for (const p of points) { const [px, pyy] = p.split(","); svg += `<circle cx="${px}" cy="${pyy}" r="2.4" fill="currentColor"/>`; }
    svg += "</svg>";
    // Une seule mesure : la légende dit le bloc, sans répéter son identifiant.
    const nomBloc = (nom) => (ident && nom.endsWith(" · " + ident) ? nom.slice(0, -ident.length - 3) : nom);
    const legende = gardees.map(([nom], i) => `<li><i style="background:${COULEURS[i % COULEURS.length]}"></i>${esc(nomBloc(nom))}</li>`).join("") +
      '<li><i class="trait"></i>l\'écart total</li>';
    return svg + `<ul class="legende">${legende}</ul>`;
  }

  function dessinerSerie(champ, s, annees, calculees) {
    const d = DECIMALES[champ] ?? 2;
    const k = calculees.length ? annees.indexOf(calculees[calculees.length - 1]) : -1;
    const fin = k >= 0 && !s.absent && s.ecart[k] != null
      ? ` <span class="fin">${annees[k]} : <b>${signe(s.ecart[k], d)}</b>${touche(annees[k]) ? marque() : ""}</span>` : "";
    let html = `<section class="serie" id="s-${champ}"><h3>${esc(s.libelle)}${fin}<small>écart à la référence, ${esc(s.unite)}</small></h3>`;
    if (s.absent || !calculees.length) {
      html += `<p class="absent" data-absent="${esc(champ)}">Absent : ${esc(s.absent || "rien n'est calculé pour ce réglage")}.</p></section>`;
      return html;
    }
    html += graphique(s, annees, calculees);
    if (!Object.keys(s.decomposition || {}).length)
      html += '<p class="note">Aucun bloc de ce mode ne fait bouger ce champ : l\'écart est calculé, et nul.</p>';
    const ligne = (nom, valeurs, f, attrs) => `<tr ${attrs}><th scope="row">${esc(nom)}</th>` +
      annees.map((a, j) => (calculees.includes(a) ? f(valeurs[j], d, a) : ABSENT)).join("") + "</tr>";
    const tete = annees.map((a) => (touche(a) && calculees.includes(a)
      ? `<th data-annee="${a}"${attr()}>${a}${marque()}</th>` : `<th data-annee="${a}">${a}</th>`)).join("");
    html += `<details><summary>Les nombres</summary><table><thead><tr><th></th>${tete}</tr></thead><tbody>`;
    html += ligne("écart", s.ecart, cellule, 'data-ligne="ecart"');
    for (const [nom, v] of Object.entries(s.decomposition || {})) html += ligne("dont " + nom, v, cellule, `data-ligne="part" data-part="${esc(nom)}"`);
    html += ligne(`référence (${s.niveaux})`, s.reference, (x, dd, a) => niveau(x, dd, a, false), 'data-ligne="reference"');
    html += ligne(`variante (${s.niveaux})`, s.variante, (x, dd, a) => niveau(x, dd, a, true), 'data-ligne="variante"');
    html += "</tbody></table></details></section>";
    return html;
  }

  function dessinerDeciles(dec) {
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
      svg += `<circle cx="${xx + w / 2}" cy="${y(a.euros_par_menage[i])}" r="3" fill="currentColor"/>`;
      svg += `<text x="${xx + w / 2}" y="${H - 6}" font-size="11" text-anchor="middle" fill="currentColor">D${i + 1}</text>`;
    }
    svg += "</svg>";
    const options = annees.map((x) => `<option${x === choisie ? " selected" : ""}>${x}</option>`).join("");
    const c = touche(choisie);
    const td = (x, dd) => cellule(x, dd, choisie);
    const pc = (x) => `<td class="v" data-v="${String(x)}"${c ? attr() : ""}>${fr(100 * x, 0)} %${c ? marque() : ""}</td>`;
    let html = `<p class="choix-annee"><label for="annee-deciles">Année</label> <select id="annee-deciles">${options}</select>` +
      (c ? ` <span class="note">${marque()} ventilée par la convention</span>` : "") + "</p>" + svg +
      `<ul class="legende"><li><i style="background:${COULEURS[0]}"></i>le choc statique de la mesure</li><li><i style="background:${COULEURS[1]}"></i>la dynamique : emploi, salaires, chômage</li><li><i class="point"></i>le total, € par ménage et par an</li></ul>` +
      `<details><summary>Les nombres, ${choisie}</summary><p class="note">Une cellule (décile × type de ménage) n'a pas de distribution interne : un ménage y gagne ou y perd autant que les autres. Gagnant : plus de ${fr(dec.seuil, 0)} € par an.</p><table><thead><tr><th>décile</th><th>€ par ménage</th><th>dont statique</th><th>dont dynamique</th><th>gagnants</th><th>perdants</th></tr></thead><tbody>`;
    for (let i = 0; i < 10; i++) html += `<tr data-decile="${i + 1}"><th scope="row">D${i + 1}</th>${td(a.euros_par_menage[i], 0)}${td(a.statique[i], 0)}${td(a.dynamique[i], 0)}${pc(a.part_gagnants[i])}${pc(a.part_perdants[i])}</tr>`;
    html += "</tbody></table></details>";
    zone.innerHTML = html;
    $("annee-deciles").addEventListener("change", (ev) => { zone.dataset.annee = ev.target.value; dessinerDeciles(dec); });
  }

  function dessiner(r) {
    const cv = r.conventions;
    conv = cv ? { annees: new Set(cv.annees), noms: cv.noms.join(" "),
      titre: `ventilé par la convention « ${cv.noms.join(", ")} » (D-414)` } : null;
    ident = r.mesure.identifiant;
    dessinerThetas(r.thetas);
    const m = r.mesure, msgs = [], reserves = [];
    msgs.push(`<p class="note">${esc(m.libelle)}${m.rapport ? ` — rapport <code>${esc(m.rapport)}</code>, commit <code>${esc((m.commit || "").slice(0, 7))}</code>` : ""}.</p>`);
    if (r.refus) msgs.push(`<p class="refus" data-refus>Refusé${r.calculees.length ? ` au-delà de ${r.calculees[r.calculees.length - 1]}` : ""} : ${esc(r.refus)}</p>`);
    if (cv) {
      const axes = Object.entries(cv.axes).map(([axe, an]) => `${axe === "menages" ? "les ménages" : "les " + axe} (${an[0]} à ${an[an.length - 1]})`).join(" et ");
      msgs.push(`<p class="convention" id="def-convention"><span class="conv">c</span> Les nombres marqués <span class="conv">c</span> : ${esc(cv.definition)}. La convention ventile ${esc(axes)} ; ce n'est pas un chiffrage (D-414).</p>`);
    }
    for (const [k, v] of Object.entries(m.non_portes || {})) reserves.push(`<p data-non-porte="${esc(k)}">Non porté (${esc(k)}) : ${esc(v)}</p>`);
    for (const a of r.avertissements || []) reserves.push(`<p>${esc(a)}</p>`);
    // Quand des années manquent, la raison se lit sans cliquer.
    if (reserves.length) msgs.push(r.refus ? reserves.join("") : `<details class="reserves"><summary>Ce que le calcul ne porte pas (${reserves.length})</summary>${reserves.join("")}</details>`);
    $("messages").innerHTML = msgs.join("");
    $("series").innerHTML = Object.entries(r.series).map(([c, s]) => dessinerSerie(c, s, r.annees, r.calculees)).join("") ||
      `<p class="absent" data-absent="series">Rien n'est calculé pour ce réglage.</p>`;
    dessinerDeciles(r.deciles);
  }

  /* ---------------------------------------------------------- le chargement */
  function montrer() {
    const hyp = $("entree-hypothese").checked;
    $("bloc-hypothese").hidden = !hyp;
    $("bloc-candidat").hidden = hyp;
    $("bloc-convention").hidden = hyp || !$("mode-structurel").checked;
  }

  async function charger() {
    const t0 = performance.now();
    if (LARGE.matches) $("panneau-thetas").open = true;
    montrer();
    const base = ici.dataset.pyodide;
    const texte = (r) => { if (!r.ok) throw new Error(`${r.url} : ${r.status}`); return r.text(); };
    const [pyodide, calcul, paquet, donnees] = await Promise.all([
      fetch(base + "pyodide.js", { integrity: ici.dataset.sri, mode: "cors", credentials: "omit" }).then(texte),
      fetch(ici.dataset.calcul).then(texte),
      fetch("jumeau-paquet.json").then((r) => r.json()),
      fetch("jumeau-donnees.json").then(texte)]);
    const url = URL.createObjectURL(new Blob([pyodide, "\n;\n", calcul], { type: "text/javascript" }));
    worker = new Worker(url);
    URL.revokeObjectURL(url);
    const pret = await new Promise((resolve, reject) => {
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
      worker.postMessage({ type: "charger", indexURL: base, paquets: ici.dataset.paquets.split(" "),
        paquet, donnees });
    });
    window.jumeau.chargement = { pyodide_ms: pret.pyodide_ms, paquet_ms: pret.paquet_ms,
      total_ms: performance.now() - t0 };
    window.jumeau.pret = true;
    for (const id of ["candidat", "vue", "h-instrument", "h-montant", "h-debut", "h-fin", "convention"]) $(id).addEventListener("change", calculer);
    for (const el of document.querySelectorAll('input[name="mode"], input[name="entree"]')) el.addEventListener("change", () => {
      montrer();
      calculer();
    });
    $("reglages").addEventListener("submit", (ev) => ev.preventDefault());
    calculer();
  }
  charger().catch((e) => { etat.textContent = "Python n'a pas pu se charger dans ce navigateur : " + e.message; window.jumeau.erreur = String(e); });
})();
