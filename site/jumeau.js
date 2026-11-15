/* La page « Le jumeau » (D-415, D-419, D-459) : Pyodide fait tourner `impots.jumeau` tel
 * quel, dans un Web Worker.
 *
 * Ce script ne calcule rien : il télécharge `pyodide.js` en vérifiant son empreinte
 * (sha384, `fetch` avec `integrity`), crée le Worker depuis un Blob qui porte ce fichier
 * vérifié suivi du script de calcul servi avec le site (jumeau-calcul.js), lui passe le
 * paquet (jumeau-paquet.json) et les entrées (jumeau-donnees.json), puis, à chaque réglage,
 * lui demande `navigateur.calculer_json` et dessine ce qu'il rend. Pour chaque entrée (une
 * mesure, un modèle, une vue), il lui demande aussi, une fois, le réglage par défaut (chaque
 * θ à ½), la chaîne des études quand on regarde le jumeau (pour dire l'écart des deux), et
 * `navigateur.portee_json` : la portée de chaque curseur et la plage des résultats, une
 * trajectoire vectorisée sur les tirages des lois des θ (D-459).
 *
 * Chaque nombre affiché porte sa valeur exacte (data-v), celle que Python a rendue ; chaque
 * année qu'une convention a ventilée porte sa marque. Les échelles d'une entrée ne font que
 * s'élargir : bouger un curseur dans sa plage ne fait pas sauter l'axe. Chaque bloc a sa
 * couleur, la même sur tous les graphiques.
 */
"use strict";
(function () {
  const ici = document.currentScript;
  const $ = (id) => document.getElementById(id);
  const etat = $("etat");
  const fr = (x, d) => x.toLocaleString("fr-FR", { minimumFractionDigits: d, maximumFractionDigits: d });
  const signe = (x, d) => (Math.abs(x) < 0.5 * Math.pow(10, -d) ? fr(0, d) : (x > 0 ? "+" : "−") + fr(Math.abs(x), d));
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const DECIMALES = { dette: 2, solde: 1, pib: 2, emploi_total: 0, creations_societes: 0,
    fermetures_societes: 0, exportations: 1, importations: 1 };
  const PRINCIPALES = ["dette", "solde", "pib", "emploi_total"];
  const TRACE = {
    dette: "La dette des administrations publiques (État, collectivités, Sécurité sociale), en points de PIB : avec la mesure, moins sans elle.",
    solde: "Le solde des administrations publiques (leurs recettes moins leurs dépenses, « B9 » en comptabilité nationale), en milliards d'euros ; négatif : la mesure creuse le déficit.",
    pib: "Le PIB, la richesse produite dans l'année, avec la mesure, en % de celui sans elle.",
    emploi_total: "Le nombre de personnes en emploi, en milliers : avec la mesure, moins sans elle.",
  };
  const ORIGINE = { litterature: "loi : littérature", donnees_fines: "loi : données fines",
    construction: "loi : par construction", large: "sans source : loi large",
    magasin: "loi large (plage du magasin)" };
  const LARGE = window.matchMedia("(min-width: 40rem)");
  /* Les blocs, en français, chacun sa couleur fixe sur tous les graphiques (J4). */
  const BLOC_NOM = { mesures: "le choc de la mesure", mesange: "multiplicateurs (Mésange)",
    creations: "créations d'entreprises (canal des études)", recettes_induites: "recettes induites",
    demande_publique: "demande publique", consommation: "consommation des ménages",
    investissement: "investissement", commerce: "commerce extérieur", emploi: "emploi",
    emploi_public: "emploi public", salaires: "salaires", naissances: "naissances d'entreprises",
    fermetures: "fermetures d'entreprises", productivite: "productivité des entrantes",
    implantation: "implantation des multinationales", tendance: "tendance", autres: "autres blocs" };
  const BLOC_COULEUR = { mesures: "#b5532a", mesange: "#2a6fb0", creations: "#8a5cb8",
    recettes_induites: "#4a9aa8", demande_publique: "#6b7f2a", consommation: "#3d8f5a",
    investissement: "#8c7a5b", commerce: "#c79a2a", emploi: "#b8475d", emploi_public: "#d17fa0",
    salaires: "#5e6fb8", naissances: "#9b6bcf", fermetures: "#6d4c8f", productivite: "#a28bd4",
    implantation: "#3b7c6e", autres: "#999999" };
  const blocDe = (n) => n.split(" · ")[0];
  const nomBloc = (n) => BLOC_NOM[blocDe(n)] || blocDe(n);
  const couleurBloc = (n) => BLOC_COULEUR[blocDe(n)] || "#888888";
  /* Les curseurs, en mots de tous les jours (J6) ; la définition exacte reste dans le détail. */
  const THETA_NOM = {
    multiplicateur_macro: "Combien l'activité répond à la mesure (multiplicateurs)",
    productivite_creations: "Productivité des entreprises nouvelles",
    commerce_elasticite_prix_exportations: "Sensibilité des exportations aux prix",
    commerce_elasticite_prix_importations: "Sensibilité des importations aux prix",
    commerce_prix_diffusion: "Vitesse à laquelle les coûts passent dans les prix",
    jumeau_emploi_elasticite_cout: "Sensibilité de l'emploi à son coût",
    jumeau_salaires_chomage: "Réponse des salaires au chômage (b)",
    jumeau_consommation_profil: "Vitesse à laquelle la consommation suit le revenu",
    jumeau_consommation_pente_deciles: "Les modestes consomment-ils plus de leur surcroît de revenu",
    labour_supply_married_women: "Offre de travail des femmes en couple",
    labour_supply_married_men: "Offre de travail des hommes en couple",
    labour_supply_single_women: "Offre de travail des femmes seules",
    labour_supply_single_men: "Offre de travail des hommes seuls",
    jumeau_emploi_public_part: "Part des dépenses de personnel qui crée des postes",
    idees_creations: "Créations d'entreprises hors impôts (idées, start-up)",
    elasticite_creations: "Créations d'entreprises selon l'impôt sur les profits",
    fermetures_marges: "Fermetures d'entreprises selon leurs marges",
    survie_creations: "Survie des jeunes entreprises",
    montee_en_charge_creations: "Années pour qu'une entreprise nouvelle atteigne sa taille",
    taille_creations: "Taille d'une entreprise nouvelle face à la moyenne",
    investissement_cout_capital: "Sensibilité de l'investissement au coût du capital",
    investissement_accelerateur: "L'investissement suit l'activité (accélérateur)",
    implantation_tmee: "Implantation des multinationales selon l'impôt",
  };
  /* Ce qui ouvre le canal d'un bloc : un curseur sans effet le dit (J7). */
  const OUVRE = { mesange: "passe par la chaîne des études (réduit) seulement",
    creations: "s'ouvre pour une mesure qui change les prélèvements des entreprises",
    naissances: "s'ouvre pour une mesure qui change les impôts et cotisations des entreprises",
    fermetures: "s'ouvre pour une mesure qui change les marges des entreprises",
    productivite: "s'ouvre quand des entreprises naissent ou ferment à cause de la mesure",
    investissement: "s'ouvre pour une mesure qui change le coût du capital (l'impôt sur les sociétés) ou l'activité",
    implantation: "s'ouvre pour une mesure qui change le taux effectif de l'impôt sur les profits",
    emploi_public: "s'ouvre pour une mesure qui paie des rémunérations publiques",
    commerce: "s'ouvre quand les prix ou la demande bougent",
    emploi: "s'ouvre quand le coût du travail, l'activité ou les salaires bougent",
    salaires: "s'ouvre quand le chômage bouge", consommation: "s'ouvre quand le revenu des ménages bouge",
    mesures: "s'ouvre pour une mesure dont le rapport porte des comportements" };

  let worker = null, thetaValeurs = {}, enCours = false, aFaire = false, numero = 0;
  let dernier = null;                         // le dernier résultat dessiné
  const defauts = new Map(), reduits = new Map(), portees = new Map(), echelles = new Map(), enAttente = new Set();
  const attentes = new Map();
  let anneeK = 0, lecture = null;
  window.jumeau = { pret: false, calculs: 0, dernier: null, temps: [], chargement: null, portee: null };

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
  const entree = (c) => JSON.stringify({ ...c, theta: undefined });
  const auDefaut = (c, liste) => ({ ...c, theta: Object.fromEntries(liste.map((t) => [t.cle, 0.5])) });
  const estDefaut = (c) => Object.values(c.theta).every((v) => v === 0.5);

  function appel(type, c) {
    return new Promise((resolve, reject) => {
      const id = ++numero;
      attentes.set(id, { resolve, reject });
      worker.postMessage({ type, id, reglage: JSON.stringify(c) });
    });
  }
  async function calculAuDefaut(c) {
    const r0 = JSON.parse(await appel("calculer", { ...c, theta: {} }));
    return JSON.parse(await appel("calculer", auDefaut(c, r0.thetas)));
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
      let r = JSON.parse(await appel("calculer", c));
      // Les θ d'une autre mesure ou d'un autre mode : chaque curseur nouveau part de ½,
      // affiché, et le calcul se refait avec lui.
      const manquants = r.thetas.filter((t) => !(t.cle in thetaValeurs));
      if (manquants.length) {
        for (const t of manquants) thetaValeurs[t.cle] = 0.5;
        c = choix();
        r = JSON.parse(await appel("calculer", c));
      }
      const dt = performance.now() - t0;
      const cle = entree(c);
      if (estDefaut(c)) defauts.set(cle, r);
      else if (!defauts.has(cle)) defauts.set(cle, JSON.parse(await appel("calculer", auDefaut(c, r.thetas))));
      // Le jumeau sur une mesure d'étude : la chaîne des études à côté, pour dire l'écart.
      if (c.mode === "structurel" && c.candidat && !reduits.has(c.candidat))
        reduits.set(c.candidat, await calculAuDefaut({ mode: "reduit", vue: "vieillie", candidat: c.candidat }));
      window.jumeau.temps.push(dt);
      window.jumeau.calculs += 1;
      window.jumeau.dernier = { choix: c, resultat: r };
      dernier = { cle, choix: c, r };
      dessiner(r);
      etat.textContent = `Calculé dans ce navigateur en ${fr(dt, 0)} ms (${r.calculees.length} année${r.calculees.length > 1 ? "s" : ""}).`;
      demanderPortee(cle, auDefaut(c, r.thetas), r);
    } catch (e) {
      etat.textContent = "Le calcul a échoué : " + e.message;
      window.jumeau.erreur = String(e);
    }
    document.body.classList.remove("calcule");
    enCours = false;
    if (aFaire) { aFaire = false; calculer(); }
  }

  async function demanderPortee(cle, c, r) {
    if (portees.has(cle) || enAttente.has(cle) || !r.calculees.length) return;
    enAttente.add(cle);
    $("portee-etat").textContent = "calcul de la portée des curseurs et de la plage des courbes…";
    try {
      const t0 = performance.now();
      const p = JSON.parse(await appel("portee", c));
      p.ms = performance.now() - t0;
      portees.set(cle, p);
      window.jumeau.portee = { cle, ms: p.ms, tirages: p.tirages };
      if (dernier && dernier.cle === cle) dessiner(dernier.r);
    } catch (e) {
      $("portee-etat").textContent = "la portée n'a pas pu se calculer : " + e.message;
    }
    enAttente.delete(cle);
  }

  /* ------------------------------------------------------------ la convention */
  let conv = null;          // {annees: Set, noms, titre} du dernier résultat, ou null
  const touche = (a) => conv !== null && conv.annees.has(Number(a));
  const marque = () => `<sup><a class="conv" href="#def-convention" title="${esc(conv.titre)}">c</a></sup>`;
  const attr = () => ` data-convention="${esc(conv.noms)}"`;

  /* ------------------------------------------------------------- les échelles */
  function pasNet(etendue) {
    const brut = etendue / 4, p = Math.pow(10, Math.floor(Math.log10(brut || 1)));
    return [1, 2, 2.5, 5, 10].map((m) => m * p).find((x) => x >= brut) || 10 * p;
  }
  function graduations(min, max) {
    const pas = pasNet(max - min), out = [];
    for (let v = Math.ceil(min / pas - 1e-9) * pas; v <= max + 1e-9 * pas; v += pas) out.push(Math.abs(v) < pas * 1e-9 ? 0 : v);
    return { pas, valeurs: out };
  }
  /* L'échelle d'une série pour une entrée : elle ne fait que s'élargir, et tient zéro. */
  function echelle(cleEntree, champ, valeurs) {
    const k = cleEntree + "|" + champ, vus = valeurs.filter((x) => x !== null && x !== undefined && isFinite(x));
    const e = echelles.get(k) || { min: 0, max: 0 };
    for (const v of vus) { e.min = Math.min(e.min, v); e.max = Math.max(e.max, v); }
    echelles.set(k, e);
    let { min, max } = e;
    if (max - min < 1e-12) { max += 1; min -= 1; }
    const marge = (max - min) * 0.08;
    const g = graduations(min - (min < 0 ? marge : 0), max + (max > 0 ? marge : 0));
    return { min: Math.min(g.valeurs[0], min), max: Math.max(g.valeurs[g.valeurs.length - 1], max), ticks: g.valeurs, pas: g.pas };
  }
  const decTicks = (pas) => { for (let d = 0; d < 4; d++) if (Math.abs(Math.round(pas * 10 ** d) - pas * 10 ** d) < 1e-9) return d; return 4; };

  /* ------------------------------------------------------------- le schéma */
  const DISPOSITIONS = {
    large: { W: 820, H: 420, b: { mesure: [10, 18], apu: [325, 18], dette: [640, 18], pib: [325, 176],
      menages: [10, 332], entreprises: [325, 332], ext: [640, 332] }, w: 170, h: 70 },
    etroit: { W: 360, H: 590, b: { mesure: [5, 10], dette: [195, 10], apu: [100, 160], pib: [5, 340],
      ext: [195, 340], menages: [5, 510], entreprises: [195, 510] }, w: 160, h: 70 },
  };
  const BLOCS = {
    mesure: ["La mesure", "var(--j-mesure)"], apu: ["Administrations publiques", "var(--j-apu)"],
    dette: ["Dette publique", "var(--j-dette)"], pib: ["Activité : le PIB", "currentColor"],
    menages: ["Ménages", "var(--j-men)"], entreprises: ["Entreprises", "var(--j-ent)"],
    ext: ["Reste du monde", "var(--j-ext)"],
  };
  function partMesure(r, k) {
    const s = r.series.solde;
    if (!s || s.absent) return null;
    let t = 0;
    for (const [n, v] of Object.entries(s.decomposition || {})) if (blocDe(n) === "mesures" && v[k] != null) t += v[k];
    return s.ecart[k] == null ? null : t;
  }
  function canaux(r, k) {
    const p = (r.comptes || {}).postes || {}, c = (r.comptes || {}).comptes || {};
    const v = (x) => (x ? x[k] : null);
    const add = (...xs) => (xs.some((x) => x != null) ? xs.reduce((t, x) => t + (x || 0), 0) : null);
    const m = partMesure(r, k), sol = r.series.solde && !r.series.solde.absent ? r.series.solde.ecart[k] : null;
    return [
      ["mesure", "apu", "la mesure", m, "Md€ au solde"],
      ["apu", "dette", "déficit", v(c.b9) == null ? null : -v(c.b9), "Md€ de dette"],
      ["dette", "apu", "intérêts", v(c.interets_nets), "Md€"],
      ["apu", "pib", r.mode === "reduit" ? "multiplicateurs (Mésange)" : "demande publique", add(v(p.c_apu), v(p.non_ventile)), "Md€"],
      ["menages", "pib", "consommation", v(p.c_menages), "Md€"],
      ["entreprises", "pib", "investissement", v(p.fbcf), "Md€"],
      ["ext", "pib", "X − M", add(v(p.exportations), v(p.importations)), "Md€"],
      ["pib", "menages", "emploi, salaires", v(c.remunerations), "Md€ de rémunérations"],
      ["pib", "apu", "recettes induites", sol == null || m == null ? null : sol - m, "Md€ au solde"],
    ];
  }
  function lignesBloc(r, k, nom) {
    const p = (r.comptes || {}).postes || {}, c = (r.comptes || {}).comptes || {}, s = r.series;
    const md = (x, lib) => (x == null ? null : `${lib} ${signe(x, 1)} Md€`);
    const g = (x) => (x ? x[k] : null);
    const ser = (ch, lib, unite, d) => (s[ch] && !s[ch].absent && s[ch].ecart[k] != null ? `${lib} ${signe(s[ch].ecart[k], d)} ${unite}` : null);
    const m = partMesure(r, k);
    const L = {
      mesure: [r.mesure.identifiant === "hypothese" ? "une loi simple" : (r.mesure.auteur || ""), md(m == null ? null : -m, "coût")],
      apu: [md(g(c.apu_recettes), "recettes"), md(g(c.apu_depenses_primaires), "dépenses"), md(g(c.b9), "solde")],
      dette: [md(g(c.dette), "dette"), ser("dette", "soit", "pt de PIB", 2)],
      pib: [md(g(c.pib), "PIB"), ser("pib", "soit", "%", 2)],
      menages: [md(g(p.c_menages), "consommation"), ser("emploi_total", "emploi", "milliers", 0)],
      entreprises: [md(g(p.fbcf), "investissement"), ser("creations_societes", "créations", "", 0)],
      ext: [md(g(p.exportations), "exportations"), md(g(p.importations) == null ? null : -g(p.importations), "importations")],
    };
    return L[nom].filter(Boolean);
  }
  function dessinerSchema(r) {
    const zone = $("schema");
    if (!r.calculees.length) { zone.innerHTML = '<p class="absent">Rien n\'est calculé pour ce réglage : le schéma attend une année calculée (voir l\'encadré plus haut).</p>'; $("comptes").innerHTML = ""; return; }
    const k = Math.min(anneeK, r.calculees.length - 1);
    const D = DISPOSITIONS[LARGE.matches ? "large" : "etroit"], { w, h } = D;
    const centre = (n) => [D.b[n][0] + w / 2, D.b[n][1] + h / 2];
    // L'épaisseur d'une flèche : sa valeur rapportée à la plus grande de l'entrée, toutes
    // années confondues, pour qu'elle se compare d'une année à l'autre.
    let maxi = 1e-9;
    r.calculees.forEach((_, j) => canaux(r, j).forEach((x) => { if (x[3] != null) maxi = Math.max(maxi, Math.abs(x[3])); }));
    const liste = canaux(r, k);
    const vifs = new Set(["mesure"]);
    let svg = `<svg viewBox="0 0 ${D.W} ${D.H}" role="img" aria-label="Le pas annuel du jumeau en ${r.calculees[k]} : les blocs et les canaux, avec l'écart de chaque flux">`;
    svg += `<defs><marker id="pointe" viewBox="0 0 10 10" refX="9" refY="5" markerUnits="userSpaceOnUse" markerWidth="11" markerHeight="11" orient="auto-start-reverse"><path d="M0,0L10,5L0,10z" fill="context-stroke"/></marker></defs>`;
    for (const [de, a, lib, val, unite] of liste) {
      const vif = val != null && Math.abs(val) > 1e-6 * maxi;
      if (vif) { vifs.add(de); vifs.add(a); }
      const [x1, y1] = centre(de), [x2, y2] = centre(a);
      // Deux sens entre deux blocs : deux arcs, de part et d'autre.
      const retour = liste.some((y) => y[0] === a && y[1] === de);
      const dx = x2 - x1, dy = y2 - y1, l = Math.hypot(dx, dy), nx = -dy / l, ny = dx / l;
      const bombe = retour ? 30 : 0;
      const t = (cx, cy, sx, sy) => { const f = Math.min((w / 2 + 4) / Math.abs(sx || 1e-9), (h / 2 + 4) / Math.abs(sy || 1e-9)); return [cx + sx * f, cy + sy * f]; };
      const [ax, ay] = t(x1, y1, dx / l, dy / l), [bx, by] = t(x2, y2, -dx / l, -dy / l);
      const mx = (ax + bx) / 2 + nx * bombe, my = (ay + by) / 2 + ny * bombe;
      const ep = vif ? 1.5 + 7 * Math.abs(val) / maxi : 1.2;
      const chemin = `M${ax},${ay} Q${mx},${my} ${bx},${by}`;
      svg += `<g class="canal ${vif ? "vif" : "inerte"}" data-canal="${de}-${a}" stroke="${BLOCS[de][1]}"><path d="${chemin}" stroke-width="${ep}" stroke-opacity=".35" marker-end="url(#pointe)"/>`;
      if (vif) svg += `<path class="flux" d="${chemin}" stroke-width="${Math.max(1.2, ep / 2)}"/>`;
      // L'étiquette, du côté de son arc : à gauche d'un arc vertical, au-dessus d'un arc
      // horizontal, pour que deux sens entre deux blocs ne se chevauchent pas.
      let tx = (ax + 2 * mx + bx) / 4, ty = (ay + 2 * my + by) / 4, ancre = "middle";
      const ox = nx * bombe, oy = ny * bombe;
      if (Math.abs(dy) > Math.abs(dx)) { ancre = ox < -1 ? "end" : ox > 1 ? "start" : (dx < 0 ? "end" : "start"); tx += ancre === "end" ? -6 : 6; }
      else ty += oy > 1 ? 14 : -6;
      const texte = val == null ? `${lib} : absent` : `${lib} ${signe(val, 1)}`;
      svg += `<text x="${tx}" y="${ty}" font-size="11" text-anchor="${ancre}" fill="currentColor" stroke="var(--fond)" stroke-width="3.5" paint-order="stroke"${val == null ? "" : ` data-v="${val}"`}><title>${esc(lib)} : ${val == null ? "absent dans ce modèle" : signe(val, 2) + " " + esc(unite)}</title>${esc(texte)}</text></g>`;
    }
    for (const [nom, [titre, couleur]] of Object.entries(BLOCS)) {
      const [x, y] = D.b[nom], lignes = lignesBloc(r, k, nom);
      svg += `<g class="bloc ${vifs.has(nom) ? "vif" : "inerte"}" data-bloc="${nom}"><rect x="${x}" y="${y}" width="${w}" height="${h}" rx="8" stroke="${couleur}"/>`;
      svg += `<text x="${x + 9}" y="${y + 18}" font-size="12.5" font-weight="700" fill="${couleur}">${esc(titre)}</text>`;
      lignes.slice(0, 3).forEach((tt, i) => { svg += `<text x="${x + 9}" y="${y + 35 + i * 14}" font-size="11" fill="currentColor">${esc(tt.length > 30 ? tt.slice(0, 29) + "…" : tt)}</text>`; });
      svg += "</g>";
    }
    svg += "</svg>";
    zone.innerHTML = svg + `<p class="schema-legende">Écarts de ${r.calculees[k]}, avec la mesure moins sans elle, en milliards d'euros sauf mention. L'épaisseur d'une flèche suit son montant. Une flèche pâle : un canal que ce modèle ne porte pas, ou que cette mesure ne fait pas bouger${r.mode === "reduit" ? ". La chaîne des études ne sépare pas les ménages, les entreprises et le reste du monde : son effet sur l'activité passe en bloc par les multiplicateurs de Mésange, le modèle de l'Insee et de la DG Trésor" : ""}.</p>`;
    dessinerComptes(r, k);
  }

  function dessinerComptes(r, k) {
    const cp = r.comptes;
    if (!cp) { $("comptes").innerHTML = ""; return; }
    const a = r.calculees[k], p = cp.postes, c = cp.comptes;
    const L = (lib, x, cls) => `<tr${cls ? ` class="${cls}"` : ""}><td>${esc(lib)}</td>${x == null ? '<td class="v abs">absent</td>' : `<td class="v" data-v="${x}">${signe(x, 2)}</td>`}</tr>`;
    const g = (x) => (x == null ? null : x[k]);
    const tol = 1e-6 * Math.abs(g(c.pib) || 1) + 1e-6;
    const ok = (x) => (x != null && Math.abs(x) <= tol ? "tient" : "ne tient pas");
    let emplois = "";
    for (const [cle, lib] of Object.entries(cp.libelles_postes)) if (p[cle][k] != null && Math.abs(p[cle][k]) > 5e-4) emplois += L(lib, p[cle][k]);
    const resE = cp.residu_emplois[k];
    const b9 = g(c.b9), rec = g(c.apu_recettes), dep = g(c.apu_depenses_primaires), int = g(c.interets_nets);
    const resA = [b9, rec, dep, int].some((x) => x == null) ? null : rec - dep - int - b9;
    const d0 = g(c.dette_ouverture), d1 = g(c.dette), sfa = g(c.sfa);
    const resD = [d0, d1, b9, sfa].some((x) => x == null) ? null : d0 - b9 + sfa - d1;
    const e = r.series.dette && r.series.dette.effets;
    $("comptes").innerHTML =
      `<div class="compte"><h3>Le PIB par ses emplois, ${a}</h3><table>${emplois || L("aucun emploi ne bouge", 0)}${L("= écart du PIB", g(c.pib), "total")}</table>` +
      `<p class="verif">Ce qui est produit est consommé, investi ou exporté : l'identité ${ok(resE)}.</p></div>` +
      `<div class="compte"><h3>Le compte des administrations, ${a}</h3><table>${L("recettes", rec)}${L("− dépenses (hors intérêts)", dep == null ? null : -dep)}${L("− intérêts", int == null ? null : -int)}${L("= solde", b9, "total")}</table>` +
      `<p class="verif">Solde = recettes − dépenses : l'identité ${ok(resA)}.</p></div>` +
      `<div class="compte"><h3>La dette, ${a}</h3><table>${L("dette en début d'année", d0)}${L("− solde", b9 == null ? null : -b9)}${L("+ ajustement stock-flux", sfa)}${L("= dette en fin d'année", d1, "total")}</table>` +
      `<p class="verif">La dette d'une année est celle de la précédente plus le déficit : l'identité ${ok(resD)}.` +
      (e && e.dette_ajoutee[k] != null ? ` En points de PIB : ${signe(e.dette_ajoutee[k], 2)} de dette ajoutée, ${signe(e.denominateur[k], 2)} par le PIB au dénominateur, soit ${signe(r.series.dette.ecart[k], 2)}.` : "") + `</p></div>`;
  }

  /* ------------------------------------------------- les courbes principales */
  function courbe(champ, s, r, p, d) {
    const annees = r.annees, calc = r.calculees, ind = p && p.indicateurs[champ];
    const bande = ind ? ind.bande : null, ref = d && d.series[champ] && !d.series[champ].absent ? d.series[champ].ecart : null;
    const tous = [...s.ecart, ...(ref || []), ...(bande ? bande.flatMap((q) => [q[0], q[4]]) : [])];
    const E = echelle(dernier.cle, champ, tous);
    const W = 440, H = 210, g = 52, dd = 18, hh = 12, b = 24;
    const y = (v) => hh + (E.max - v) / (E.max - E.min) * (H - hh - b);
    const pas = (W - g - dd) / (annees.length - 1);
    const x = (k) => g + pas * k;
    const dec = decTicks(E.pas);
    let svg = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(s.libelle)} : écart à la référence, ${esc(s.unite)}, de ${annees[0]} à ${annees[annees.length - 1]}">`;
    for (const v of E.ticks) svg += `<line x1="${g}" x2="${W - dd}" y1="${y(v)}" y2="${y(v)}" stroke="currentColor" stroke-opacity="${v === 0 ? 0.7 : 0.12}"/><text x="${g - 5}" y="${y(v) + 4}" font-size="11" text-anchor="end" fill="currentColor">${signe(v, dec)}</text>`;
    const marquees = annees.map((a, k) => (touche(a) && calc.includes(a) ? k : null)).filter((k) => k !== null);
    if (marquees.length) svg += `<rect x="${x(marquees[0]) - pas / 2}" width="${pas * marquees.length}" y="${hh}" height="${H - hh - b}" fill="var(--l1)" fill-opacity=".55"/><text x="${x(marquees[0]) - pas / 2 + 3}" y="${hh + 10}" font-size="9.5" fill="currentColor" fill-opacity=".8">c : années réparties par convention</text>`;
    const k0 = Math.min(anneeK, calc.length - 1);
    if (calc.length) svg += `<line class="annee-vue" x1="${x(k0)}" x2="${x(k0)}" y1="${hh}" y2="${H - b}" stroke="currentColor" stroke-opacity=".25" stroke-dasharray="2 3"/>`;
    annees.forEach((a, k) => { if (k % 3 === 0 || k === annees.length - 1) svg += `<text x="${x(k)}" y="${H - 7}" font-size="11" text-anchor="middle" fill="currentColor">${a}</text>`; });
    const poly = (vals) => vals.map((v, k) => (v == null ? null : `${x(k)},${y(v)}`)).filter(Boolean).join(" ");
    if (bande) {
      for (const [i, j] of [[0, 4], [1, 3]]) {
        const haut = bande.map((q, k) => `${x(k)},${y(q[j])}`), bas = bande.map((q, k) => `${x(k)},${y(q[i])}`).reverse();
        svg += `<polygon points="${[...haut, ...bas].join(" ")}" fill="var(--j-bande)"/>`;
      }
    }
    if (ref) svg += `<polyline points="${poly(ref)}" fill="none" stroke="currentColor" stroke-width="1.4" stroke-dasharray="4 3" stroke-opacity=".7"/>`;
    const pts = poly(s.ecart);
    if (pts) svg += `<polyline points="${pts}" fill="none" stroke="var(--j-apu)" stroke-width="2.4"/>`;
    s.ecart.forEach((v, k) => { if (v != null) svg += `<circle cx="${x(k)}" cy="${y(v)}" r="${k === k0 ? 4 : 2.4}" fill="var(--j-apu)"/>`; });
    annees.forEach((a, k) => { if (!calc.includes(a)) svg += `<text x="${x(k)}" y="${y(0) - 4}" font-size="9" fill="currentColor" fill-opacity=".6" transform="rotate(-90 ${x(k)} ${y(0) - 4})">absent</text>`; });
    return svg + "</svg>";
  }

  /* Le réglage hors de sa propre plage (R13, D-469) : pas une erreur. La plage tire
     chaque curseur selon sa loi publiée, dont le centre n'est pas toujours ½, et la
     réponse n'est pas en ligne droite ; le défaut, lui, met chaque curseur au milieu de
     sa boîte. Le milieu des tirages est dit. */
  function horsPlage(v, q, dc, r) {
    if (v == null || (v >= q[0] && v <= q[4])) return "";
    const decentres = (r.thetas || []).filter((t) => t.lu && t.loi && Math.abs(t.loi.moyenne - 0.5) > 0.02)
      .map((t) => `${esc(court(t).toLowerCase())} (centre ${fr(t.loi.moyenne, 2)})`);
    return `<p class="note hors-plage" data-hors-plage><strong>Ce nombre est hors de sa plage, et ce n'est pas une erreur.</strong> ` +
      `Le trait met chaque curseur à sa position choisie (au défaut, le milieu de sa boîte, ½) ; la plage, elle, tire chaque curseur selon sa loi publiée, ` +
      `et le centre de cette loi n'est pas toujours ½` + (decentres.length ? ` : ${decentres.slice(0, 4).join(", ")}${decentres.length > 4 ? ", etc." : ""}` : "") +
      `. Comme la réponse du modèle n'est pas en ligne droite, le milieu des tirages (${signe(q[2], dc)}) n'est pas le nombre de ce réglage (${signe(v, dc)}).</p>`;
  }

  function pourquoi(champ, s, r, k) {
    const a = r.calculees[k];
    if (champ === "dette" && s.effets && s.effets.dette_ajoutee[k] != null)
      return `Pourquoi elle bouge : en ${a}, ${signe(s.effets.dette_ajoutee[k], 2)} pt de dette ajoutée (le coût de la mesure, ses intérêts, moins les recettes que l'activité rapporte) et ${signe(s.effets.denominateur[k], 2)} pt parce que le PIB, au dénominateur du ratio, ${s.effets.denominateur[k] <= 0 ? "est plus haut" : "est plus bas"}.`;
    const parts = Object.entries(s.decomposition || {}).map(([n, v]) => [n, v[k]]).filter(([, v]) => v != null && Math.abs(v) > 1e-9);
    if (!parts.length) return "";
    parts.sort((u, v) => Math.abs(v[1]) - Math.abs(u[1]));
    const d = DECIMALES[champ] ?? 2;
    return `D'où vient l'écart en ${a} : ` + parts.slice(0, 4).map(([n, v]) => `<span class="pastille" style="background:${couleurBloc(n)}"></span>${esc(nomBloc(n))} ${signe(v, d)}`).join(" ; ") + (parts.length > 4 ? " ; etc." : ".");
  }

  function dessinerPrincipales(r) {
    const p = portees.get(dernier.cle), d = defauts.get(dernier.cle);
    const k = Math.max(0, Math.min(anneeK, r.calculees.length - 1));
    const kf = r.calculees.length - 1;
    let html = "";
    for (const champ of PRINCIPALES) {
      const s = r.series[champ];
      if (!s) continue;
      html += `<article class="serie principale" data-champ="${champ}"><h3>${esc(s.libelle.replace(" (B9)", "").replace("APU", "administrations publiques"))}</h3><p class="trace">${esc(TRACE[champ])}</p>`;
      if (s.absent || !r.calculees.length) {
        const pq = s.absent && r.mode === "reduit" ? "la chaîne des études ne calcule pas l'emploi : passez au jumeau (structurel) pour le voir" : (s.absent || "rien n'est calculé pour ce réglage");
        html += `<p class="absent">Absent : ${esc(pq)}.</p></article>`; continue;
      }
      const dc = DECIMALES[champ] ?? 2, af = r.calculees[kf], v = s.ecart[kf];
      const ind = p && p.indicateurs[champ];
      const plage = ind ? ` <span class="note">plage de 90 % : ${signe(ind.bande[kf][0], dc)} à ${signe(ind.bande[kf][4], dc)}</span>` : (p ? "" : ' <span class="note">plage en calcul…</span>');
      const ds = d && d.series[champ] && d.series[champ].ecart[kf];
      const vsDef = ds != null && Math.abs(v - ds) > 0.5 * Math.pow(10, -dc - 1) ? ` <span class="note">(défaut ${signe(ds, dc)})</span>` : "";
      html += `<p class="fin">${af} : <b data-v="${v}">${signe(v, dc)}</b> ${esc(s.unite)}${touche(af) ? marque() : ""}${vsDef}${plage}</p>`;
      html += courbe(champ, s, r, p, d);
      html += `<ul class="legende"><li><i class="trait" style="color:var(--j-apu)"></i>le réglage choisi</li><li><i class="tirets"></i>le défaut (chaque curseur à ½)</li>${ind ? `<li><i class="bande"></i>50 % et 90 % des tirages, chaque curseur selon sa loi publiée</li>` : ""}</ul>`;
      if (ind) html += horsPlage(v, ind.bande[kf], dc, r);
      const q = pourquoi(champ, s, r, k);
      if (q) html += `<p class="pourquoi">${q}</p>`;
      html += "</article>";
    }
    $("series-principales").innerHTML = html;
  }

  /* ------------------------------------------------------------------ les θ */
  function court(t) {
    if (THETA_NOM[t.cle]) return THETA_NOM[t.cle];
    let p = t.definition.includes(" : ") ? t.definition.split(" : ").slice(1).join(" : ") : t.definition;
    for (const sep of [" ; ", " (", ", "]) { const i = p.indexOf(sep); if (i >= 20) p = p.slice(0, i); }
    if (p.length > 90) p = p.slice(0, 87).replace(/\s+\S*$/, "") + "…";
    return "Comportement : " + p.charAt(0).toLowerCase() + p.slice(1);
  }
  const indicateurChoisi = () => $("indicateur").value || "dette";

  function badges(t) {
    let b = `<span class="badge b-${esc(t.loi.origine)}">${esc(ORIGINE[t.loi.origine] || t.loi.origine)}</span>`;
    if (t.histoire) b += t.histoire.identifie
      ? `<span class="badge b-identifie" title="${esc(t.histoire.par || "")}">identifié par les données</span>`
      : `<span class="badge b-non-identifie" title="${esc(t.histoire.note || "l'histoire ne le déplace pas de sa loi (D-439)")}">non identifié par l'histoire</span>`;
    else b += `<span class="badge b-non-identifie">non estimé sur l'histoire</span>`;
    if (!t.monotone) b += `<span class="badge b-large" title="sa portée se lit sur neuf points, D-427">effet non monotone</span>`;
    return b;
  }
  const valeurTexte = (t) => (t.valeur == null ? "" : ` · valeur ${fr(t.valeur, Math.abs(t.valeur) >= 10 ? 1 : 3)}`);

  function ligneTheta(t) {
    const div = document.createElement("div");
    div.id = "t-" + t.cle;
    div.className = "theta";
    const loi = t.loi;
    div.innerHTML = `<div><label class="nom" for="r-${esc(t.cle)}">${esc(court(t))}</label><div class="badges">${badges(t)}</div>` +
      `<p class="plage">Le paramètre à θ = 0 : ${esc(t.a_zero)} · à ½ : ${esc(t.a_demi)} · à 1 : ${esc(t.a_un)}</p></div>` +
      `<div><div class="barre"></div><p class="effet"></p>` +
      `<div class="curseur"><input type="range" id="r-${esc(t.cle)}" min="0" max="1" step="0.01" value="${thetaValeurs[t.cle] ?? 0.5}" aria-describedby="e-${esc(t.cle)}">` +
      `<output id="o-${esc(t.cle)}"></output></div>` +
      `<details class="detail"><summary>définition, source, loi · <code>${esc(t.cle)}</code></summary>` +
      `<small class="def"></small><small class="src"></small><small class="loi">Loi sur θ : moyenne ${fr(loi.moyenne, 3)}, écart ${fr(loi.ecart_bas, 3)} dessous, ${fr(loi.ecart_haut, 3)} dessus (tronquée à [0 ; 1] pour les tirages).</small>` +
      (t.histoire ? `<small>Sur l'histoire (D-439) : θ estimé ${fr(t.histoire.theta, 3)}, écart-type ${fr(t.histoire.ecart_type, 3)}${t.histoire.par ? " ; " + esc(t.histoire.par) : ""}${t.histoire.note ? " ; " + esc(t.histoire.note) : ""}.</small>` : "") +
      `</details></div>`;
    div.querySelector(".effet").id = "e-" + t.cle;
    div.querySelector("input").addEventListener("input", (ev) => {
      thetaValeurs[t.cle] = Number(ev.target.value);
      $("o-" + t.cle).textContent = "θ = " + fr(thetaValeurs[t.cle], 2);
      div.classList.toggle("change", thetaValeurs[t.cle] !== 0.5);
      calculer();
    });
    return div;
  }

  function dessinerThetas(liste) {
    const p = dernier && portees.get(dernier.cle), ind = indicateurChoisi();
    const effets = new Map((p ? p.thetas : []).map((x) => [x.cle, x.effets[ind]]));
    let maxi = 0;
    for (const e of effets.values()) if (e) maxi = Math.max(maxi, Math.abs(e.bas), Math.abs(e.haut));
    const lus = liste.filter((t) => t.lu), autres = liste.filter((t) => !t.lu);
    if (p) lus.sort((a, b) => { const ea = effets.get(a.cle), eb = effets.get(b.cle); return (eb ? eb.haut - eb.bas : -1) - (ea ? ea.haut - ea.bas : -1); });
    const d = DECIMALES[ind] ?? 2, unite = p && p.indicateurs[ind] ? p.indicateurs[ind].unite : "";
    const seuil = Math.max(maxi * 0.02, 0.5 * Math.pow(10, -d - 1));
    for (const [zone, groupe] of [[$("thetas"), lus], [$("thetas-non-lus"), autres]]) {
      const vus = new Set(groupe.map((t) => t.cle));
      for (const div of [...zone.querySelectorAll(".theta")]) if (!vus.has(div.id.slice(2))) div.remove();
      for (const t of groupe) {
        let div = $("t-" + t.cle);
        if (!div) div = ligneTheta(t);
        zone.appendChild(div);          // l'ordre de la portée
        div.dataset.lu = t.lu ? "1" : "0";
        div.dataset.bloc = t.bloc;
        const v = thetaValeurs[t.cle] ?? 0.5;
        $("o-" + t.cle).textContent = "θ = " + fr(v, 2) + valeurTexte(t);
        div.querySelector("input").value = v;
        div.classList.toggle("change", t.lu && v !== 0.5);
        div.querySelector(".def").textContent = `Bloc « ${BLOC_NOM[t.bloc] || t.bloc} ». ${t.definition} (${t.unite}).`;
        div.querySelector(".src").textContent = `Source : ${t.source}${t.verifiee ? "" : " — choisie, non vérifiée"}. ${t.direction}.`;
        const e = effets.get(t.cle), barre = div.querySelector(".barre"), texte = div.querySelector(".effet");
        div.classList.remove("sans-effet");
        if (!t.lu) { barre.innerHTML = ""; texte.textContent = dernier && dernier.r.mode === "reduit" ? "La chaîne des études ne le lit pas : passez au jumeau (structurel) pour qu'il compte." : "Ce modèle ne le lit pas : il ne change rien ici."; continue; }
        if (!e) { barre.innerHTML = ""; texte.textContent = p ? "Portée absente pour ce résultat." : "Portée en calcul…"; continue; }
        const W = 300, X = (val) => W / 2 + (maxi > 0 ? val / maxi : 0) * (W / 2 - 4);
        const af = p.calculees[p.calculees.length - 1];
        barre.innerHTML = `<svg viewBox="0 0 ${W} 20" preserveAspectRatio="none" aria-hidden="true"><line x1="${W / 2}" x2="${W / 2}" y1="0" y2="20" stroke="currentColor" stroke-opacity=".5"/>` +
          `<rect x="${X(Math.min(e.bas, 0))}" width="${Math.max(0.5, X(0) - X(Math.min(e.bas, 0)))}" y="4" height="12" fill="var(--j-dette)" fill-opacity=".75"/>` +
          `<rect x="${X(0)}" width="${Math.max(0.5, X(Math.max(e.haut, 0)) - X(0))}" y="4" height="12" fill="var(--j-apu)" fill-opacity=".75"/></svg>`;
        const pts = e.points, pz = pts[0], pu = pts[pts.length - 1];
        if (Math.max(Math.abs(e.bas), Math.abs(e.haut)) < seuil) {
          div.classList.add("sans-effet");
          texte.textContent = `Sans effet visible sur ce résultat en ${af}, pour cette mesure : ce canal ${OUVRE[t.bloc] || "ne reçoit rien d'elle"}.`;
        } else texte.textContent = `En ${af}, de ${signe(e.bas, d + 1)} à ${signe(e.haut, d + 1)} ${unite} autour du défaut` + (t.monotone ? ` (à θ = 0 : ${signe(pz, d + 1)} ; à θ = 1 : ${signe(pu, d + 1)}).` : " (lu sur neuf points de 0 à 1).");
      }
    }
    const axe = $("axe-portee");
    axe.innerHTML = p && maxi > 0 ? `<span>le curseur, d'où vient sa loi</span><span>de combien il déplace « ${esc(p.indicateurs[ind].libelle.toLowerCase())} » quand on le pousse de 0 à 1 (rouge : vers le bas, bleu : vers le haut ; l'échelle va de −${fr(maxi, d + 1)} à +${fr(maxi, d + 1)} ${esc(unite)})</span>` : "";
    if (p) $("portee-etat").textContent = `${p.thetas.length} curseurs lus, ${p.tirages} tirages, calculés en ${fr(p.ms, 0)} ms.`;
  }

  function dessinerIndicateurs() {
    const p = dernier && portees.get(dernier.cle), sel = $("indicateur");
    const voulus = p ? Object.entries(p.indicateurs).map(([k, v]) => [k, `${v.libelle.replace(" (B9)", "").replace("APU", "administrations publiques")} en ${p.calculees[p.calculees.length - 1]}`]) : [["dette", "Dette publique"]];
    const actuel = sel.value || "dette";
    sel.innerHTML = voulus.map(([k, l]) => `<option value="${k}"${k === actuel ? " selected" : ""}>${esc(l)}</option>`).join("");
  }

  function dessinerEcartDefaut(r) {
    const z = $("ecart-defaut"), d = defauts.get(dernier.cle), c = dernier.choix;
    if (estDefaut(c) || !d || !r.calculees.length) {
      z.innerHTML = "Tous les curseurs sont au réglage par défaut, ½. Bougez-en un : ce qu'il change s'affiche ici, et sur les courbes plus haut.";
      return;
    }
    const kf = r.calculees.length - 1, af = r.calculees[kf];
    const parts = PRINCIPALES.filter((ch) => r.series[ch] && !r.series[ch].absent && d.series[ch] && r.series[ch].ecart[kf] != null && d.series[ch].ecart[kf] != null)
      .map((ch) => { const dc = DECIMALES[ch] ?? 2, x = r.series[ch].ecart[kf] - d.series[ch].ecart[kf]; return `${esc(r.series[ch].libelle.replace(" (B9)", "").replace(" des APU", "").toLowerCase())} <b data-v="${x}">${signe(x, dc + 1)}</b> ${esc(r.series[ch].unite)}`; });
    const n = Object.values(c.theta).filter((v) => v !== 0.5).length;
    z.innerHTML = `Votre réglage (${n} curseur${n > 1 ? "s" : ""} hors de ½) change, en ${af}, par rapport au défaut : ${parts.join(" ; ")}. <button type="button" id="remettre">remettre les curseurs à ½</button>`;
    $("remettre").addEventListener("click", () => { for (const k of Object.keys(thetaValeurs)) thetaValeurs[k] = 0.5; calculer(); });
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

  function graphique(champ, s, annees, calculees) {
    const W = 440, H = 200, g = 50, d = 8, h = 12, b = 24;
    const parts = Object.entries(s.decomposition || {});
    parts.sort((a, b2) => Math.max(...b2[1].map((x) => Math.abs(x || 0))) - Math.max(...a[1].map((x) => Math.abs(x || 0))));
    let gardees = parts.slice(0, 6);
    if (parts.length > 6) gardees = [...gardees, ["autres", annees.map((_, k) => parts.slice(6).reduce((t, [, v]) => (v[k] == null ? t : t + v[k]), 0))]];
    const vals = [];
    annees.forEach((_, k) => { let p = 0, n = 0; for (const [, v] of gardees) { const x = v[k] || 0; if (x > 0) p += x; else n += x; } vals.push(p, n, s.ecart[k]); });
    const E = echelle(dernier.cle, "barres-" + champ, vals);
    const y = (v) => h + (E.max - v) / (E.max - E.min) * (H - h - b);
    const pas = (W - g - d) / annees.length, x = (k) => g + pas * (k + 0.5), dec = decTicks(E.pas);
    let svg = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(s.libelle)} : écart à la référence par année, et sa décomposition par bloc">`;
    for (const v of E.ticks) svg += `<line x1="${g}" x2="${W - d}" y1="${y(v)}" y2="${y(v)}" stroke="currentColor" stroke-opacity="${v === 0 ? 0.6 : 0.12}"/><text x="${g - 4}" y="${y(v) + 4}" font-size="11" text-anchor="end" fill="currentColor">${signe(v, dec)}</text>`;
    annees.forEach((a, k) => {
      if (k % 3 === 0) svg += `<text x="${x(k)}" y="${H - 7}" font-size="11" text-anchor="middle" fill="currentColor">${a}</text>`;
      if (!calculees.includes(a)) return;
      let p = 0, n = 0;
      gardees.forEach(([nom, v]) => {
        const val = v[k];
        if (!val) return;
        const base = val > 0 ? p : n, haut = base + val;
        svg += `<rect x="${x(k) - pas * 0.32}" width="${pas * 0.64}" y="${Math.min(y(base), y(haut))}" height="${Math.abs(y(base) - y(haut))}" fill="${couleurBloc(nom)}"/>`;
        if (val > 0) p = haut; else n = haut;
      });
    });
    const points = annees.map((a, k) => (s.ecart[k] == null ? null : `${x(k)},${y(s.ecart[k])}`)).filter(Boolean);
    if (points.length > 1) svg += `<polyline points="${points.join(" ")}" fill="none" stroke="currentColor" stroke-width="1.6"/>`;
    svg += "</svg>";
    return svg + `<ul class="legende">${gardees.map(([nom]) => `<li><i style="background:${couleurBloc(nom)}"></i>${esc(nomBloc(nom))}</li>`).join("")}<li><i class="trait"></i>l'écart total</li></ul>`;
  }

  function dessinerSerie(champ, s, annees, calculees) {
    const d = DECIMALES[champ] ?? 2;
    const k = calculees.length ? annees.indexOf(calculees[calculees.length - 1]) : -1;
    const fin = k >= 0 && !s.absent && s.ecart[k] != null
      ? ` <span class="fin">${annees[k]} : <b>${signe(s.ecart[k], d)}</b>${touche(annees[k]) ? marque() : ""}</span>` : "";
    let html = `<section class="serie" id="s-${champ}"><h3>${esc(s.libelle)}${fin}</h3><p class="trace">écart à la référence, ${esc(s.unite)} ; les barres : la part de chaque bloc, chacun sa couleur</p>`;
    if (s.absent || !calculees.length) return html + `<p class="absent" data-absent="${esc(champ)}">Absent : ${esc(s.absent || "rien n'est calculé pour ce réglage")}.</p></section>`;
    const nul = s.ecart.every((x) => x == null || Math.abs(x) < 1e-12);
    if (nul) html += '<p class="note">Calculé, et nul chaque année : aucun bloc de ce modèle ne fait bouger ce champ pour cette mesure.</p>';
    else html += graphique(champ, s, annees, calculees);
    const ligne = (nom, valeurs, f, attrs) => `<tr ${attrs}><th scope="row">${esc(nom)}</th>` +
      annees.map((a, j) => (calculees.includes(a) ? f(valeurs[j], d, a) : ABSENT)).join("") + "</tr>";
    const tete = annees.map((a) => (touche(a) && calculees.includes(a)
      ? `<th data-annee="${a}"${attr()}>${a}${marque()}</th>` : `<th data-annee="${a}">${a}</th>`)).join("");
    html += `<details><summary>Les nombres</summary><table><thead><tr><th></th>${tete}</tr></thead><tbody>`;
    html += ligne("écart", s.ecart, cellule, 'data-ligne="ecart"');
    for (const [nom, v] of Object.entries(s.decomposition || {})) html += ligne("dont " + nomBloc(nom), v, cellule, `data-ligne="part" data-part="${esc(nom)}"`);
    html += ligne(`référence (${s.niveaux})`, s.reference, (x, dd, a) => niveau(x, dd, a, false), 'data-ligne="reference"');
    html += ligne(`variante (${s.niveaux})`, s.variante, (x, dd, a) => niveau(x, dd, a, true), 'data-ligne="variante"');
    html += "</tbody></table></details></section>";
    return html;
  }

  function dessinerDeciles(dec, r) {
    const zone = $("deciles");
    if (dec.absent) {
      const pq = r.mode === "reduit" ? "la chaîne des études ne suit pas les ménages un par un. Passez au jumeau (structurel), qui les suit en cinquante groupes, pour voir qui gagne et qui perd" : dec.absent;
      zone.innerHTML = `<p class="absent" data-absent="deciles">${esc(pq.charAt(0).toUpperCase() + pq.slice(1))}.</p>`; return;
    }
    const annees = Object.keys(dec.annees);
    const choisie = zone.dataset.annee && annees.includes(zone.dataset.annee) ? zone.dataset.annee : annees[0];
    const a = dec.annees[choisie];
    const W = 640, H = 220, g = 56, b = 24, h = 12;
    const vals = [0, ...a.statique, ...a.dynamique, ...a.euros_par_menage, ...a.statique.map((s, i) => s + a.dynamique[i])];
    const E = echelle(dernier.cle, "deciles", vals);
    const y = (v) => h + (E.max - v) / (E.max - E.min) * (H - h - b);
    const pas = (W - g - 10) / 10;
    const C = ["var(--j-mesure)", "var(--j-men)"];
    let svg = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Écart du revenu disponible par ménage et par décile, ${choisie}">`;
    for (const v of E.ticks) svg += `<line x1="${g}" x2="${W - 10}" y1="${y(v)}" y2="${y(v)}" stroke="currentColor" stroke-opacity="${v === 0 ? .6 : .12}"/><text x="${g - 4}" y="${y(v) + 4}" font-size="11" text-anchor="end" fill="currentColor">${signe(v, 0)} €</text>`;
    for (let i = 0; i < 10; i++) {
      const xx = g + pas * i + pas * 0.18, w = pas * 0.64;
      let p = 0, n = 0;
      [[a.statique[i], C[0]], [a.dynamique[i], C[1]]].forEach(([v, c]) => {
        if (!v) return;
        const base = v > 0 ? p : n, haut = base + v;
        svg += `<rect x="${xx}" width="${w}" y="${Math.min(y(base), y(haut))}" height="${Math.abs(y(base) - y(haut))}" fill="${c}"/>`;
        if (v > 0) p = haut; else n = haut;
      });
      svg += `<circle cx="${xx + w / 2}" cy="${y(a.euros_par_menage[i])}" r="3.5" fill="currentColor"/>`;
      svg += `<text x="${xx + w / 2}" y="${H - 6}" font-size="11" text-anchor="middle" fill="currentColor">D${i + 1}</text>`;
    }
    svg += "</svg>";
    const options = annees.map((x) => `<option${x === choisie ? " selected" : ""}>${x}</option>`).join("");
    const c = touche(choisie);
    const td = (x, dd) => cellule(x, dd, choisie);
    const pc = (x) => `<td class="v" data-v="${String(x)}"${c ? attr() : ""}>${fr(100 * x, 0)} %${c ? marque() : ""}</td>`;
    let html = `<p class="lead">L'écart du revenu disponible, en euros par ménage et par an, du dixième le plus modeste des ménages (D1) au plus aisé (D10) : ce que la mesure donne ou prend tout de suite (le choc de la mesure), et ce que l'emploi, les salaires et le chômage y ajoutent ensuite.</p>` +
      `<p class="choix-annee"><label for="annee-deciles">Année</label> <select id="annee-deciles">${options}</select>` +
      (c ? ` <span class="note">${marque()} répartie par la convention</span>` : "") + "</p>" + svg +
      `<ul class="legende"><li><i style="background:${C[0]}"></i>le choc de la mesure</li><li><i style="background:${C[1]}"></i>la suite : emploi, salaires, chômage</li><li><i class="point"></i>le total, € par ménage et par an</li></ul>` +
      `<details><summary>Les nombres, ${choisie}</summary><p class="note">Une cellule (décile × type de ménage) n'a pas de distribution interne : un ménage y gagne ou y perd autant que les autres. Gagnant : plus de ${fr(dec.seuil, 0)} € par an.</p><table><thead><tr><th>décile</th><th>€ par ménage</th><th>dont le choc</th><th>dont la suite</th><th>gagnants</th><th>perdants</th></tr></thead><tbody>`;
    for (let i = 0; i < 10; i++) html += `<tr data-decile="${i + 1}"><th scope="row">D${i + 1}</th>${td(a.euros_par_menage[i], 0)}${td(a.statique[i], 0)}${td(a.dynamique[i], 0)}${pc(a.part_gagnants[i])}${pc(a.part_perdants[i])}</tr>`;
    html += "</tbody></table></details>";
    zone.innerHTML = html;
    $("annee-deciles").addEventListener("change", (ev) => { zone.dataset.annee = ev.target.value; dessinerDeciles(dec, r); });
  }

  /* Un refus du jumeau, dit en mots (J2) ; le texte exact reste à côté. */
  function refusEnMots(r, c) {
    const fin = r.calculees.length ? r.calculees[r.calculees.length - 1] : null;
    if (r.mode !== "structurel") return fin ? `Le calcul s'arrête après ${fin}.` : "Rien n'est calculé.";
    let s = `<strong>${fin ? `Le jumeau ne calcule pas cette mesure au-delà de ${fin}.` : "Le jumeau ne calcule cette mesure pour aucune année."}</strong> Pour la faire tourner, il doit savoir, chaque année, quels impôts elle change et quels ménages elle touche. Le rapport de l'étude ne le dit que pour sa première année, sur la population figée en 2026 : le jumeau ne devine pas le reste.`;
    if (c.vue === "vieillie") s += " Choisissez la population <em>figée en 2026</em> : c'est la seule que le rapport ventile.";
    else if (!c.convention) s += " Cochez la convention : elle répartit chaque année suivante comme la première.";
    else s += " Même avec la convention, la ventilation manque ici : le rapport chiffre un total (une réforme du Smic, des cotisations non réparties par impôt) sans dire quels impôts il touche. <strong>C'est une limite du jumeau aujourd'hui, pas une erreur</strong> : la chaîne des études (réduit), qui n'a pas besoin de cette ventilation, la calcule.";
    return s;
  }

  /* Le jumeau à côté de la chaîne des études (J3) : pourquoi les deux dettes diffèrent. */
  function comparaison(r, c) {
    const red = reduits.get(c.candidat);
    if (!red || !red.calculees.length || !r.calculees.length) return "";
    const kf = r.calculees.length - 1, a = r.calculees[kf], kr = red.calculees.indexOf(a);
    if (kr < 0) return "";
    const ds = r.series.dette.ecart[kf], dr = red.series.dette.ecart[kr];
    const part = (x, k) => { let m = 0, t = 0; for (let j = 0; j <= k; j++) { const pm = partMesure(x, j); if (pm == null) return null; m += pm; t += x.series.solde.ecart[j]; } return m ? 100 * (t - m) / -m : null; };
    const ps = part(r, kf), pr = part(red, kr);
    return `<div class="comparaison" data-comparaison><p><strong>Le chiffrage publié du site est celui de l'étude : ${signe(dr, 2)} pt de dette en ${a}</strong>, calculé par la chaîne des études, sur la population vieillie, à θ½. ` +
      `Le jumeau donne ici ${signe(ds, 2)} pt : ce n'est pas un second chiffrage publié, c'est le même coût passé dans une autre hypothèse sur l'économie${conv ? " (ses années marquées c sont réparties par convention)" : ""}.</p>` +
      `<p><strong>Ce que le jumeau ajoute.</strong> La chaîne des études applique au coût les multiplicateurs moyens publiés pour l'économie française (Mésange). Le jumeau, lui, fait répondre les salaires au chômage, la consommation au revenu de chaque groupe de ménages, l'emploi au coût du travail, bloc par bloc, avec ses curseurs.</p>` +
      (ps != null && pr != null ? `<p><strong>Pourquoi ils divergent.</strong> Surtout par la part du coût qui revient en recettes par l'activité, de 2026 à ${a} : ${fr(pr, 0)} % dans la chaîne des études, ${fr(ps, 0)} % dans le jumeau ; en ${a}, ses blocs y mettent : ${blocsSolde(r, kf)}.</p>` : "") +
      `<p>Lequel croire n'est pas tranché ici : le jumeau est jugé sur l'histoire (<a href="#juge">ce qu'il sait</a>), et il n'y bat pas encore partout la méthode naïve. Il sert à voir par où passe l'effet et ce qui le fait bouger.</p></div>`;
  }

  function blocsSolde(r, k) {
    const parts = Object.entries(r.series.solde.decomposition || {}).filter(([n, v]) => blocDe(n) !== "mesures" && v[k] != null && Math.abs(v[k]) > 0.05);
    parts.sort((u, v) => Math.abs(v[1][k]) - Math.abs(u[1][k]));
    return parts.slice(0, 4).map(([n, v]) => `${esc(nomBloc(n))} ${signe(v[k], 1)} Md€`).join(", ") || "presque rien";
  }

  function dessiner(r) {
    const cv = r.conventions;
    conv = cv ? { annees: new Set(cv.annees), noms: cv.noms.join(" "),
      titre: `réparti par la convention « ${cv.noms.join(", ")} » (D-414)` } : null;
    const m = r.mesure, msgs = [], reserves = [], c = dernier.choix;
    const modele = r.mode === "structurel" ? "le jumeau (structurel)" : "la chaîne des études (réduit)";
    msgs.push(`<p class="titre-mesure">${esc(m.libelle)}<span>calculé par ${modele}${m.rapport ? ` · rapport <code>${esc(m.rapport)}</code>, commit <code>${esc((m.commit || "").slice(0, 7))}</code>` : ""}</span></p>`);
    if (r.refus) msgs.push(`<div class="refus" data-refus><p>${refusEnMots(r, c)}</p><details><summary>le refus exact du calcul</summary><p><code>${esc(r.refus)}</code></p></details></div>`);
    if (r.mode === "structurel" && c.candidat) msgs.push(comparaison(r, c));
    if (cv) {
      const axes = Object.entries(cv.axes).map(([axe, an]) => `${axe === "menages" ? "les ménages" : "les " + axe} (${an[0]} à ${an[an.length - 1]})`).join(" et ");
      msgs.push(`<p class="convention" id="def-convention"><span class="conv">c</span> Les nombres marqués <span class="conv">c</span> sont répartis par une convention, pas chiffrés : ${esc(cv.definition)}. Elle répartit ${esc(axes)} (D-414).</p>`);
    }
    for (const [k, v] of Object.entries(m.non_portes || {})) reserves.push(`<p data-non-porte="${esc(k)}">Non porté (${esc(k)}) : ${esc(v)}</p>`);
    for (const a of r.avertissements || []) reserves.push(`<p>${esc(a)}</p>`);
    if (reserves.length) msgs.push(`<details class="reserves"><summary>Ce que le calcul ne porte pas (${reserves.length})</summary>${reserves.join("")}</details>`);
    $("messages").innerHTML = msgs.join("");
    const an = $("annee");
    an.max = String(Math.max(0, r.calculees.length - 1));
    anneeK = Math.min(anneeK, Math.max(0, r.calculees.length - 1));
    an.value = String(anneeK);
    $("annee-v").textContent = r.calculees[anneeK] || r.annees[0];
    dessinerSchema(r);
    dessinerPrincipales(r);
    $("series").innerHTML = Object.entries(r.series).map(([ch, s]) => dessinerSerie(ch, s, r.annees, r.calculees)).join("") ||
      `<p class="absent" data-absent="series">Rien n'est calculé pour ce réglage.</p>`;
    dessinerIndicateurs();
    dessinerThetas(r.thetas);
    dessinerEcartDefaut(r);
    dessinerDeciles(r.deciles, r);
  }

  function voirAnnee(k) {
    anneeK = k;
    $("annee").value = String(k);
    if (!dernier) return;
    $("annee-v").textContent = dernier.r.calculees[k] || "";
    dessinerSchema(dernier.r);
    dessinerPrincipales(dernier.r);
  }

  /* ---------------------------------------------------------- le chargement */
  /* Ce que le jumeau (structurel) calcule de chaque mesure d'étude, relevé à la
     construction de la page par les refus mêmes du modèle (J2, D-469) : un choix qu'il
     refuse est grisé avant le clic, avec sa raison en une ligne et ce qu'on peut faire à
     la place. */
  const DISPO = (() => { try { return JSON.parse($("structurel-dispo").textContent || "{}"); } catch (e) { return {}; } })();
  let basculeAuto = false;               // le mode réduit choisi par la page, pas par le lecteur
  function regler() {
    const ms = $("mode-structurel"), raison = $("raison-structurel");
    const vieillie = $("vue").querySelector('option[value="vieillie"]');
    const d = $("entree-candidat").checked ? DISPO[$("candidat").value] : null;
    if (!d || !d.figee) { ms.disabled = false; vieillie.disabled = false; raison.hidden = true; return; }
    if (!d.figee.avec) {
      ms.disabled = true;
      if (ms.checked) { $("mode-reduit").checked = true; $("vue").value = "vieillie"; basculeAuto = true; }
      vieillie.disabled = false;
      const opt = $("candidat").selectedOptions[0], groupe = opt && opt.parentElement;
      const autres = groupe ? [...groupe.querySelectorAll("option")].filter((o) => o.value !== opt.value && DISPO[o.value] && DISPO[o.value].figee && DISPO[o.value].figee.avec) : [];
      raison.innerHTML = `<strong>Le jumeau (structurel) ne calcule pas ce choix</strong>, grisé : ${esc(d.figee.raison)}. ` +
        "À la place, la chaîne des études le calcule, choisie ici, sur la population vieillie : c'est le nombre de l'étude." +
        (autres.length ? " Pour voir le jumeau tourner sur ce candidat, prenez une de ses mesures qu'il calcule : " +
          autres.map((o) => `<button type="button" class="lien" data-cle="${esc(o.value)}">${esc(o.textContent.split(" — ").pop())}</button>`).join(", ") + "." : "");
      raison.hidden = false;
      for (const b of raison.querySelectorAll("button[data-cle]")) b.addEventListener("click", () => {
        $("candidat").value = b.dataset.cle;
        $("mode-structurel").checked = true;
        $("vue").value = "figee";
        montrer();
        calculer();
      });
      return;
    }
    ms.disabled = false;
    if (basculeAuto) { ms.checked = true; $("vue").value = "figee"; basculeAuto = false; }
    vieillie.disabled = ms.checked;
    if (ms.checked && $("vue").value === "vieillie") $("vue").value = "figee";
    raison.innerHTML = ms.checked ? "La population vieillie est grisée pour le jumeau : " + esc(d.vieillie.raison || "") + "." : "";
    raison.hidden = !ms.checked;
  }

  function montrer() {
    const hyp = $("entree-hypothese").checked;
    $("bloc-hypothese").hidden = !hyp;
    $("bloc-candidat").hidden = hyp;
    regler();
    $("bloc-convention").hidden = hyp || !$("mode-structurel").checked;
  }

  async function charger() {
    const t0 = performance.now();
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
    for (const id of ["vue", "h-instrument", "h-montant", "h-debut", "h-fin"]) $(id).addEventListener("change", calculer);
    for (const id of ["candidat", "convention"]) $(id).addEventListener("change", () => { montrer(); calculer(); });
    // Chaque modèle s'ouvre sur la population de son calcul (R12, D-469) : la chaîne des
    // études sur la vieillie, celle des nombres publiés ; le jumeau sur la figée.
    for (const el of document.querySelectorAll('input[name="mode"]')) el.addEventListener("change", () => {
      basculeAuto = false;
      $("vue").value = $("mode-reduit").checked ? "vieillie" : "figee";
      montrer();
      calculer();
    });
    for (const el of document.querySelectorAll('input[name="entree"]')) el.addEventListener("change", () => {
      montrer();
      calculer();
    });
    $("reglages").addEventListener("submit", (ev) => ev.preventDefault());
    $("annee").addEventListener("input", (ev) => voirAnnee(Number(ev.target.value)));
    $("indicateur").addEventListener("change", () => { if (dernier) dessinerThetas(dernier.r.thetas); });
    $("jouer").addEventListener("click", () => {
      const b = $("jouer");
      if (lecture) { clearInterval(lecture); lecture = null; b.textContent = "▶ faire tourner"; b.setAttribute("aria-pressed", "false"); return; }
      b.textContent = "❚❚ arrêter"; b.setAttribute("aria-pressed", "true");
      lecture = setInterval(() => {
        const n = dernier ? dernier.r.calculees.length : 1;
        voirAnnee((anneeK + 1) % Math.max(1, n));
      }, 1100);
    });
    LARGE.addEventListener("change", () => { if (dernier) dessinerSchema(dernier.r); });
    calculer();
  }
  charger().catch((e) => { etat.textContent = "Python n'a pas pu se charger dans ce navigateur : " + e.message; window.jumeau.erreur = String(e); });
})();
