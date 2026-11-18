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
    "illustratif": ["illustratif", "◌ illustratif", "Un ordre de grandeur : une partie de la chaîne est déclarée (une loi simple, une mesure mise à l'échelle ou décalée) ou approchée (un programme pris par ses mesures), pas chiffrée par une passe."],
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
  const onglets = ["programme", "mesure", "composer", "bareme", "comparer"];
  let onglet = "programme";
  function montrer(o) {
    onglet = o;
    for (const x of onglets) {
      $("o-" + x).setAttribute("aria-selected", String(x === o));
      $("p-" + x).hidden = x !== o;
    }
    // Comparer remplace le résultat d'un choix par la vue côte à côte (D-652).
    $("resultat").hidden = o === "comparer";
    $("comparer").hidden = o !== "comparer";
    if (o === "comparer") {
      comparer();
      try { history.replaceState(null, "", "#comparer"); } catch (e) { /* page locale */ }
    }
  }
  for (const x of onglets) $("o-" + x).addEventListener("click", () => {
    montrer(x);
    if (x === "programme") choisir({ candidat: $("programme").value });
    if (x === "mesure") choisir({ candidat: $("mesure").value });
    if (x === "composer" && !$("composition").children.length) ajouterMesure();
    if (x === "bareme") try { history.replaceState(null, "", "#bareme"); } catch (e) { /* page locale */ }
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

  /* ------------------------------------------------------------ votre barème (D-660) */
  // La page montre le menu sans l'API ; « Lancer » appelle l'API à la même origine
  // (`POST /impacts/proposition`), suit l'état, puis dessine le résultat comme un autre.
  const BR = B.bareme || { boutons: [], hors_menu: [] };
  const API = "/impacts/proposition";
  const LOCAL = `<p>La passe tourne sur un serveur qui a le moteur et la population : ce site statique n'en a pas. Pour la lancer chez vous, dans le dépôt, la population construite (<code>make data</code>) :</p>
    <ol><li><code>PYTHONPATH=src python -m impots.site_impacts ecrire</code> (la page, environ deux minutes)</li>
    <li><code>IMPOTS_AUTH=aucune PYTHONPATH=src uvicorn impots.api.main:app</code></li>
    <li>ouvrir <code>http://localhost:8000/site/impacts.html#bareme</code></li></ol>`;
  function bouton(b) {
    const v = b.id === "ir_tranche_seuil" ? 0 : b.neutre;
    return `<label data-b="${esc(b.id)}"><span>${esc(b.libelle)}</span>
      <span class="i-ligne"><input type="number" data-b="${esc(b.id)}" min="${b.min}" max="${b.max}" step="${b.pas}" value="${v}"> ${esc(b.unite === "%" && b.id !== "tva_normal" && b.id !== "ir_tranche_taux" ? "% de plus" : b.unite)}</span>
      <span class="i-aide">${esc(b.aide)}</span></label>`;
  }
  $("bareme-boutons").innerHTML = BR.boutons.map(bouton).join("");
  $("bareme-hors").innerHTML = BR.hors_menu.map((h) => `<li>${esc(h)}</li>`).join("");
  for (const i of $("bareme-boutons").querySelectorAll("input")) i.addEventListener("input", () => {
    const b = BR.boutons.find((x) => x.id === i.dataset.b);
    i.closest("label").classList.toggle("i-bouge", Number(i.value) !== b.neutre);
  });
  $("bareme-neutre").addEventListener("click", () => {
    for (const i of $("bareme-boutons").querySelectorAll("input")) {
      i.value = BR.boutons.find((x) => x.id === i.dataset.b).neutre;
      i.closest("label").classList.remove("i-bouge");
    }
  });
  function reglageBareme() {
    const out = {};
    for (const i of $("bareme-boutons").querySelectorAll("input")) {
      const b = BR.boutons.find((x) => x.id === i.dataset.b);
      const v = Number(String(i.value).replace(",", "."));
      if (i.value !== "" && isFinite(v) && v !== b.neutre) out[b.id] = v;
    }
    return out;
  }
  function etatBareme(html, refus) {
    const e = $("bareme-etat");
    e.hidden = false;
    e.classList.toggle("i-refus", !!refus);
    e.innerHTML = html;
  }
  const ETAPES = { premiere_annee: "la première année (20 000 ménages, comportements, boucle)", chemin_annuel: "chaque année jusqu'en 2035 (la plus longue)", cas_types: "les cas types de « Pour vous »", jumeau: "le jumeau, toutes les dimensions" };
  let suivi = null;
  async function suivre(id) {
    clearTimeout(suivi);
    let r;
    try { r = await fetch(`${API}/${encodeURIComponent(id)}`, { headers: { Accept: "application/json" } }); }
    catch (e) { etatBareme("Le serveur ne répond plus : " + esc(e.message) + LOCAL, true); return; }
    const e = await r.json().catch(() => ({}));
    window.impacts.bareme = e;
    if (!r.ok) { etatBareme(esc(e.detail || r.status), true); return; }
    if (e.etat === "fait" && e.resultat) {
      etatBareme(`<b>Fait.</b> ${esc(e.libelle)} — ${Object.entries(e.temps || {}).map(([k, v]) => `${esc(k.replace(/_s$/, "").replace(/_/g, " "))} ${fr(v / 60, 1).replace("+", "")} min`).join(", ")}. Le résultat est ci-dessous.`);
      dessiner(e.resultat);
      return;
    }
    if (e.etat === "echec") { etatBareme(`<b>La passe a échoué :</b> <code>${esc(e.erreur)}</code>`, true); return; }
    const depuis = e.debut ? Math.round((Date.now() - Date.parse(e.debut)) / 60000) : null;
    etatBareme(e.etat === "en_file"
      ? `<b>En file</b> : ${esc(e.libelle)}. Une passe tourne déjà sur le serveur ; la vôtre partira après elle. La page vérifie toutes les quinze secondes.`
      : `<b>En cours</b> (${depuis === null ? "" : depuis + " min, "}environ trois quarts d'heure en tout) : ${esc(ETAPES[e.etape] || e.etape || "")}. Vous pouvez laisser la page ouverte, ou revenir plus tard à <code>${esc(location.pathname)}#bareme=${esc(id)}</code>.`);
    suivi = setTimeout(() => suivre(id), 15000);
  }
  $("bareme-lancer").addEventListener("click", async () => {
    const boutons = reglageBareme();
    if (!Object.keys(boutons).length) { etatBareme("Bougez au moins un réglage : à leur valeur de départ, ils laissent la loi.", true); return; }
    etatBareme("Envoi au serveur…");
    let r;
    try { r = await fetch(API, { method: "POST", headers: { "Content-Type": "application/json", Accept: "application/json" }, body: JSON.stringify({ boutons }) }); }
    catch (e) { etatBareme("<b>Aucun serveur de calcul ici.</b>" + LOCAL, true); return; }
    const e = await r.json().catch(() => null);
    if (r.status === 404 || r.status === 405 || e === null) { etatBareme("<b>Aucun serveur de calcul ici.</b>" + LOCAL, true); return; }
    if (!r.ok) {
      etatBareme(`<b>Le serveur refuse :</b> ${esc(e.detail || r.status)}${r.status === 503 && /clé/.test(e.detail || "") ? LOCAL : ""}`, true);
      return;
    }
    try { history.replaceState(null, "", "#bareme=" + e.id); } catch (x) { /* page locale */ }
    suivre(e.id);
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
      (r.pourquoi_mode ? ` <b>${r.composee ? "Pourquoi par ses mesures" : "Pourquoi pas le jumeau complet"} :</b> ${esc(r.pourquoi_mode)}.` : "");
  }
  function dessiner(r) {
    window.impacts.resultat = r;
    window.impacts.calculs += 1;
    $("titre-resultat").textContent = r.mesure ? r.mesure.libelle : "";
    $("reglage").innerHTML = ligneReglage(r);
    const av = [];
    const parMesures = r.pourquoi_mode && D.precalcul[r.candidat + "@mesures"];
    if (parMesures) av.push(`<div class="i-avert i-refus"><b>Le jumeau complet refuse ce programme entier</b> (la raison est ci-dessus) : il est calculé par la chaîne des études, sans les ménages ni les entreprises. Ses mesures, elles, passent une à une dans le jumeau complet. <button type="button" class="i-lien" data-voir="${esc(r.candidat)}@mesures">Voir le calcul par ses mesures</button></div>`);
    if (r.couverture) av.push(couverture(r));
    if (r.refus) av.push(`<div class="i-avert i-refus"><b>Le jumeau ne calcule ${r.calculees && r.calculees.length ? "que jusqu'en " + r.calculees[r.calculees.length - 1] : "aucune année"} :</b> ${esc(r.refus)}</div>`);
    if (r.proposition) av.push(`<div class="i-avert i-refus"><b>Votre barème, un chiffrage illustratif.</b> ${esc(r.proposition.libelle)}. Une passe sur la population faite à votre demande, que personne n'a enregistrée avant de la voir : chaque dimension est illustrative, aucune n'est comparée à un chiffrage officiel (D-660).</div>`);
    if (r.composition) av.push(`<div class="i-avert"><b>La proposition :</b><ul>${r.composition.map((m) => `<li>${esc(m.libelle)}${m.transformee ? " — <i>" + esc(m.transformee) + "</i>" : ""}</li>`).join("")}</ul></div>`);
    if (r.avertissements && r.avertissements.length) av.push(`<div class="i-avert"><ul>${r.avertissements.map((a) => `<li>${esc(a)}</li>`).join("")}</ul></div>`);
    const mods = Object.entries(r.modules_en_erreur || {});
    if (mods.length) av.push(`<div class="i-avert i-refus"><b>Dimensions qui ne se chargent pas :</b><ul>${mods.map(([m, e]) => `<li>${esc(m)} : ${esc(e)}</li>`).join("")}</ul></div>`);
    $("avertissements").innerHTML = av.join("");
    for (const b of $("avertissements").querySelectorAll("[data-voir]")) b.addEventListener("click", () => choisir({ candidat: b.dataset.voir }));
    bref(r);
    if (!r.candidat || !D.precalcul[r.candidat]) retenir(r);
    $("ensemble").innerHTML = (r.ensemble || []).map(carte).join("") ||
      '<p class="i-aide">Aucune dimension calculée.</p>';
    $("fiches").innerHTML = "";
    for (const d of r.dimensions || []) $("fiches").appendChild(fiche(d));
    pourVous();
  }

  /* ------------------------------------------------------------ pour vous (D-630) */
  const PV = ["foyer", "enfants", "activite", "logement", "age"];
  for (const k of PV) $("pv-" + k).addEventListener("change", pourVous);
  function cleCas() {
    const v = Object.fromEntries(PV.map((k) => [k, $("pv-" + k).value]));
    if (v.activite === "retraite") return `${v.foyer}-0-retraite-${v.logement}-62_plus`;
    return `${v.foyer}-${v.enfants}-${v.activite}-${v.logement}-${v.age === "62_plus" ? "50_61" : v.age}`;
  }
  const euros = (x) => fr(x, 0) + " €";
  let casProgrammes = null;
  async function pourVous() {
    const out = $("pv-resultat");
    const r = window.impacts.resultat;
    const d = r && (r.dimensions || []).find((x) => x.cle === "pour_vous");
    if (!d) { out.innerHTML = '<p class="i-aide">Pas calculé pour ce choix.</p>'; return; }
    if (d.erreur) { out.innerHTML = `<div class="i-avert i-refus"><b>Non calculé :</b> ${esc(d.erreur)}</div>`; return; }
    if (!d.notes.cas && d.notes.fichier) {
      // Les cas types des programmes précalculés sont dans un fichier à part (D-630).
      try {
        if (!casProgrammes) { out.innerHTML = '<p class="i-aide">Chargement des cas types…</p>'; casProgrammes = await fetch(d.notes.fichier).then((x) => { if (!x.ok) throw new Error(x.status); return x.json(); }); }
      } catch (e) { out.innerHTML = `<div class="i-avert i-refus">Les cas types ne se chargent pas (${esc(e.message)}).</div>`; return; }
      if (window.impacts.resultat !== r) return;
      d.notes.cas = casProgrammes[r.candidat];
      if (!d.notes.cas) { out.innerHTML = '<p class="i-aide">Pas de cas type pour ce programme.</p>'; return; }
    }
    const v = Object.fromEntries(PV.map((k) => [k, $("pv-" + k).value]));
    const cle = cleCas(), C = d.notes.cas, i0 = C.cles.indexOf(cle), an = d.annees;
    const c = i0 < 0 ? null : Object.fromEntries(Object.entries(C).filter(([, x]) => Array.isArray(x)).map(([k, x]) => [k, x[i0]]));
    if (c && c.depart) c.depart = Object.fromEntries(C.depart_champs.map((k, j) => [k, c.depart[j]]));
    if (c && c.depart) c.depart.programme = d.notes.programme;
    if (!c) { out.innerHTML = '<p class="i-aide">Ce cas type n\'est pas dans la grille.</p>'; return; }
    const f = an.length - 1;
    const notes = [];
    if (v.activite === "retraite" && v.enfants !== "0") notes.push("un retraité est pris sans enfant à charge");
    if (v.activite !== "retraite" && v.age === "62_plus") notes.push("un actif de 62 ans ou plus est pris à 50-61 ans");
    const approx = { length: c.origines.cellule || 0 }, exact = { length: c.origines.openfisca || 0 };
    const pct = (i) => 100 * c.reel[i] / c.rd;
    const origine = !Object.keys(c.origines).length ? "aucune mesure lue" : approx.length && !exact.length
      ? "<b>approximation</b> : le gain moyen d'un ménage du même décile de niveau de vie (la cellule), pas un calcul de votre situation"
      : approx.length ? `calculé par OpenFisca pour ${exact.length} mesure(s), <b>approximé par la cellule</b> pour ${approx.length}`
      : "calculé par OpenFisca pour ce cas type, avant et après la mesure (impôts, cotisations, prestations, TVA)";
    const L = c.lignes;
    const lignes = L ? [["impot_revenu", "impôt sur le revenu", -1], ["prelevements_travail", "cotisations, CSG et CRDS", -1],
      ["prestations", "prestations (prime d'activité, aides au logement, allocations…)", 1], ["salaire_net", "salaire net", 1],
      ["pensions_chomage", "pensions ou allocations chômage (brutes)", 1], ["taxes_consommation", "TVA et accises payées", -1]]
      .filter(([k]) => L[k]).map(([k, lib, s]) => `<li>${esc(lib)} : ${k === "impot_revenu" || k === "prelevements_travail" || k === "taxes_consommation" ? (L[k] > 0 ? "+" + fr(L[k], 0).replace("+", "") + " € à payer" : fr(-L[k], 0).replace("+", "") + " € de moins à payer") : euros(L[k])}</li>`).join("") : "";
    const dep = c.depart;
    const depart = !dep ? "<p class=\"pv-depart\">Âge de départ : vous êtes déjà à la retraite, ou ce n'est pas un actif.</p>"
      : !dep.programme || !dep.ecart_age_legal ? "<p class=\"pv-depart\">Âge de départ : ce choix ne change pas l'âge légal de votre génération (seul un programme entier qui le règle le porte ici).</p>"
      : `<p class="pv-depart">Âge de départ : votre génération atteint l'âge légal (${nf(dep.age_legal_reference % 1 ? 2 : 0).format(dep.age_legal_reference)} ans dans la loi actuelle) en ${dep.annee} ; le programme le change de <b>${fr(dep.ecart_age_legal, 2)} an</b>, soit un départ effectif de ${fr(dep.ecart_age_effectif, 2)} an (de ${fr(dep.effectif_bas, 2)} à ${fr(dep.effectif_haut, 2)}) et ${fr(dep.retraite_sans_limitation_ans, 2)} an de retraite sans limitation d'activité.</p>`;
    const actif = ["smic", "median", "eleve", "independant"].includes(v.activite);
    const sansEco = !(d.notes.economie && d.notes.economie.lus || []).includes("salaire_moyen")
      ? '<div class="i-avert">Ce calcul ne porte ni les salaires, ni les prix, ni le chômage du jumeau (la chaîne des études) : le revenu est la mesure elle-même, et le risque de chômage n\'est pas lu.</div>' : "";
    out.innerHTML = `<p class="pv-cas">Le cas type : ${esc([d.notes.grille.libelles[v.foyer], v.activite === "retraite" ? "" : v.enfants + " enfant(s)", d.notes.grille.libelles[v.activite], d.notes.grille.libelles[v.logement], d.notes.grille.libelles[v.activite === "retraite" ? "62_plus" : v.age]].filter(Boolean).join(", "))} ; revenu disponible sans la mesure : ${euros(c.rd).replace("+", "")} par an.${notes.length ? " (" + esc(notes.join(" ; ")) + ")" : ""} ${statut(d)}</p>
      ${sansEco}<div class="pv-tetes">
        <div class="pv-tete"><h3>Votre revenu disponible réel, en ${an[f]}</h3><p class="i-gros" data-v="${c.reel[f]}">${euros(c.reel[f])}<small> par an</small></p><p>${fr(pct(f))} % ; en ${an[0]} : ${euros(c.reel[0])}</p></div>
        <div class="pv-tete"><h3>Dont la mesure elle-même</h3><p class="i-gros">${euros(c.statique[f])}<small> par an</small></p><p>${origine}</p></div>
        <div class="pv-tete"><h3>Votre risque d'être au chômage</h3>${actif ? `<p class="i-gros">${fr(c.risque[f])}<small> point</small></p><p>aujourd'hui ${fr(c.risque0, 1).replace("+", "")} % pour un ménage comme le vôtre</p>` : "<p>Vous n'êtes pas en emploi : votre risque n'est pas calculé ; le chômage autour de vous compte dans la satisfaction.</p>"}</div>
        <div class="pv-tete"><h3>Satisfaction dans la vie (0 à 10)</h3><p class="i-gros">${fr(c.sat[f], 3)}<small> point</small></p><p>entre ${fr(c.sat_bande[0], 3)} et ${fr(c.sat_bande[1], 3)} ; un ordre de grandeur</p></div>
        <div class="pv-tete"><h3>Espérance de vie</h3><p class="i-gros">${fr(c.ev[f], 2)}<small> mois</small></p><p>si l'écart de revenu durait ; entre ${fr(c.ev_bande[0], 2)} et ${fr(c.ev_bande[1], 2)}</p></div>
      </div>
      ${lignes ? `<h4>Ce que la mesure change à vos impôts et prestations (par an, la première année)</h4><ul class="pv-lignes">${lignes}</ul>` : ""}
      ${depart}`;
    out.appendChild(courbe({ libelle: "Votre revenu disponible réel", unite: "€ par an", valeurs: c.reel }, an));
    const t = an.map((a, i) => `<tr><td>${a}</td><td>${fr(c.reel[i], 0)}</td><td>${fr(pct(i))}</td><td>${fr(c.statique[i], 0)}</td><td>${actif ? fr(c.risque[i]) : "—"}</td><td>${fr(c.sat[i], 3)}</td><td>${fr(c.ev[i], 2)}</td></tr>`).join("");
    const det = document.createElement("details");
    det.innerHTML = `<summary>Année par année</summary><div class="i-defile"><table class="i-table"><thead><tr><th>année</th><th>revenu réel (€)</th><th>%</th><th>dont la mesure (€)</th><th>risque de chômage (points)</th><th>satisfaction</th><th>espérance de vie (mois)</th></tr></thead><tbody>${t}</tbody></table></div>`;
    out.appendChild(det);
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
    det.innerHTML = `<summary>Les nombres, année par année</summary><div class="i-defile"><table class="i-table"><thead><tr><th>année</th><th>${esc(ind.unite)}</th>${ind.bas ? "<th>bas de la bande</th><th>haut de la bande</th>" : ""}</tr></thead><tbody>${lignes}</tbody></table></div>`;
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
      <figcaption>${esc(ind.libelle)} : écart à la trajectoire sans la mesure (${esc(ind.unite)})${ind.bas ? " ; en clair, la bande (ce qu'elle est : « Ce qu'il faut savoir »)" : ""}.</figcaption>`;
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


  /* ------------------------------------------------------------ en bref (D-650) */
  function phrase(p) {
    // La phrase commence par le titre de sa dimension : il devient le lien vers sa fiche.
    const t = p.texte || "";
    const debut = p.dimension && p.titre && t.startsWith(p.titre)
      ? `<a href="#f-${esc(p.dimension)}">${esc(p.titre)}</a>${esc(t.slice(p.titre.length))}` : esc(t);
    return `<span class="b-phrase b-${esc(p.sorte)}"${p.certitude ? ` data-certitude="${esc(p.certitude)}"` : ""}${p.dimension ? ` data-dimension="${esc(p.dimension)}"` : ""}>${debut}</span>`;
  }
  function bref(r) {
    const s = r.synthese;
    if (!s || !s.phrases || !s.phrases.length) {
      $("bref").innerHTML = '<p class="i-aide">Pas de paragraphe pour ce calcul.</p>';
      $("bref-avert").textContent = "";
      return;
    }
    // L'essentiel d'un tenant (le cadre, le plus net, les arbitrages), puis une phrase par
    // dimension, puis pour qui, puis ce qui manque.
    const de = (...sortes) => s.phrases.filter((p) => sortes.includes(p.sorte));
    const para = (xs) => xs.length ? `<p class="i-bref-texte">${xs.map(phrase).join(" ")}</p>` : "";
    const liste = (xs) => xs.length ? `<ul class="i-bref-liste">${xs.map((p) => `<li>${phrase(p)}</li>`).join("")}</ul>` : "";
    $("bref").innerHTML = para(de("cadre", "plus_net", "arbitrage")) + liste(de("tete")) +
      liste(de("pour_qui", "detail")) + para(de("absent", "erreur"));
    $("bref-avert").textContent = s.avertissement || "";
  }
  function couverture(r) {
    // D-652, D-655 : le programme par ses mesures chiffrées et leur interaction.
    const c = r.couverture, k = r.composee;
    const md = (x) => fr(x, 1).replace("+", "") + " Md€";
    const somme = c.mesures === null || c.mesures === undefined ? "absente (une mesure sans coût cette année-là : " + esc(c.sans_cout.join(", ")) + ")" : md(c.mesures);
    const inter = c.interaction === null || c.interaction === undefined ? "" : `, plus ${fr(c.interaction, 2)} Md€ d'interaction`;
    const tete = k ? `<b>${esc(k.titre)}</b>${esc(k.texte.slice(k.titre.length))}<ul>${k.mesures.map((m) => `<li>${esc(m.libelle.split(" : ").pop())}</li>`).join("")}</ul>` : `<b>Le programme, par ses mesures.</b> `;
    return `<div class="i-avert i-compose">${tete}Ce que cela couvre, au coût mécanique de ${c.annee} : ${somme} pour la somme des mesures${inter}, ${md(c.programme)} pour le programme entier.${c.age ? ` L'âge de départ du programme (${esc(c.age)}) n'est dans aucune de ses mesures chiffrées : comme pour tout programme entier, la santé et « Pour vous » le lisent, les comptes publics ne le chiffrent pas.` : ""} <button type="button" class="i-lien" data-voir="${esc(r.programme)}">Voir le programme entier par la chaîne des études</button></div>`;
  }

  /* ------------------------------------------------------------ comparer (D-652) */
  // Les mesures et propositions calculées dans la page s'ajoutent à la comparaison.
  const extras = [];
  function retenir(r) {
    const nom = r.mesure ? r.mesure.libelle : "votre calcul";
    const i = extras.findIndex((x) => x.nom === nom);
    if (i >= 0) extras.splice(i, 1);
    extras.unshift({ cle: "extra-" + (++numeroLigne), nom: "Votre calcul : " + nom, r, extra: true });
    extras.splice(5);
  }
  function nomProgramme(cle) {
    const base = cle.replace(/@mesures$/, "");
    const lib = (B.libelles[base] || base).split(" : ")[0];
    return cle.endsWith("@mesures") ? lib + ", par ses mesures" : lib;
  }
  function lignesComparees() {
    const out = [];
    for (const [cle, r] of Object.entries(D.precalcul)) out.push({ cle, nom: nomProgramme(cle), r, refuse: !!r.pourquoi_mode, mesures: cle.endsWith("@mesures") });
    out.sort((a, b) => nomProgramme(a.cle.replace(/@mesures$/, "")).localeCompare(nomProgramme(b.cle.replace(/@mesures$/, "")), "fr") || (a.mesures - b.mesures));
    return out.concat(extras);
  }
  function unionDimensions(lignes) {
    const dims = new Map();
    for (const l of lignes) for (const d of l.r.dimensions || []) {
      if (d.erreur) continue;
      if (!dims.has(d.cle)) dims.set(d.cle, { cle: d.cle, titre: d.titre, question: d.question, indicateurs: new Map() });
      const u = dims.get(d.cle);
      for (const i of d.indicateurs || []) if (!u.indicateurs.has(i.cle)) u.indicateurs.set(i.cle, { cle: i.cle, libelle: i.libelle, unite: i.unite, sens: i.sens });
    }
    return dims;
  }
  function point(r, dc, ic, annee) {
    const d = (r.dimensions || []).find((x) => x.cle === dc);
    if (!d) return { absent: "dimension non calculée" };
    if (d.erreur) return { absent: "non calculée : " + d.erreur };
    const ind = (d.indicateurs || []).find((x) => x.cle === ic);
    if (!ind) return { absent: "absent ici", statut: d.statut };
    const i = (d.annees || []).indexOf(annee);
    const v = i < 0 ? null : (ind.valeurs || [])[i];
    if (v === null || v === undefined) return { absent: "absent cette année", statut: d.statut };
    const b = ind.bas ? ind.bas[i] : null, h = ind.haut ? ind.haut[i] : null;
    // Le sens est sûr quand la bande reste d'un côté de zéro, celui du nombre (D-650).
    const net = b !== null && h !== null && b !== undefined && h !== undefined && ((b > 1e-9 && h > 1e-9 && v > 1e-9) || (b < -1e-9 && h < -1e-9 && v < -1e-9));
    const largeur = net ? Math.max(h, b) - Math.min(h, b) : 0;
    return { v, b: b ?? null, h: h ?? null, statut: d.statut, juge: d.juge, sens: ind.sens, net,
      nettete: net ? (largeur > 1e-12 ? Math.min(Math.abs(b), Math.abs(h)) / largeur : Infinity) : -1 };
  }
  function trier(lignes, cle) {
    const t = $("cmp-tri").value;
    const val = (l) => l[cle];
    return lignes.slice().sort((a, b) => {
      if (t === "nom") return a.nom.localeCompare(b.nom, "fr");
      const pa = val(a), pb = val(b);
      if (pa.v === undefined || pa.v === null) return (pb.v === undefined || pb.v === null) ? a.nom.localeCompare(b.nom, "fr") : 1;
      if (pb.v === undefined || pb.v === null) return -1;
      if (t === "net") return (pb.nettete - pa.nettete) || (Math.abs(pb.v) - Math.abs(pa.v));
      return t === "bas" ? pa.v - pb.v : pb.v - pa.v;
    });
  }
  const STATUT_COURT = { "jugé": "jugé", "sourcé, non jugé": "sourcé", "illustratif": "illustratif" };
  function badges(l) {
    const out = [];
    if (l.refuse) out.push('<span class="c-badge c-reduit" title="Le jumeau complet refuse ce programme : la chaîne des études, sans les ménages ni les entreprises">chaîne des études</span>');
    if (l.mesures) out.push('<span class="c-badge" title="Le jumeau complet, sur la proposition composée de ses mesures">jumeau complet, par ses mesures</span>');
    if (l.extra) out.push('<span class="c-badge">calculé dans la page</span>');
    return out.join(" ");
  }
  let cmpPret = false;
  function comparer() {
    const lignes = lignesComparees();
    const dims = unionDimensions(lignes);
    const annees = (lignes[0] && lignes[0].r.annees) || B.annees;
    const selD = $("cmp-dimension"), selI = $("cmp-indicateur"), selA = $("cmp-annee");
    const dChoisie = selD.value && dims.has(selD.value) ? selD.value : dims.keys().next().value;
    selD.innerHTML = [...dims.values()].map((d) => `<option value="${esc(d.cle)}"${d.cle === dChoisie ? " selected" : ""}>${esc(d.titre)}</option>`).join("");
    const dim = dims.get(dChoisie);
    if (!dim) { $("cmp-liste").innerHTML = '<p class="i-aide">Aucune dimension calculée.</p>'; return; }
    const iChoisi = selI.value && dim.indicateurs.has(selI.value) ? selI.value : dim.indicateurs.keys().next().value;
    selI.innerHTML = [...dim.indicateurs.values()].map((i) => `<option value="${esc(i.cle)}"${i.cle === iChoisi ? " selected" : ""}>${esc(i.libelle)}</option>`).join("");
    const aChoisie = selA.value && annees.includes(+selA.value) ? +selA.value : annees[annees.length - 1];
    selA.innerHTML = annees.map((a) => `<option${a === aChoisie ? " selected" : ""}>${a}</option>`).join("");
    if (!cmpPret) {
      for (const x of [selD, selI, selA, $("cmp-tri")]) x.addEventListener("change", comparer);
      cmpPret = true;
    }
    const ind = dim.indicateurs.get(iChoisi);
    $("cmp-question").textContent = `${dim.question} ${ind.libelle}, en ${aChoisie} (${ind.unite}, écart à la trajectoire sans la mesure).`;
    for (const l of lignes) l.p = point(l.r, dChoisie, iChoisi, aChoisie);
    const liste = trier(lignes, "p");
    const xs = [0];
    for (const l of liste) if (l.p.v !== undefined) xs.push(l.p.v, l.p.b ?? l.p.v, l.p.h ?? l.p.v);
    let lo = Math.min(...xs), hi = Math.max(...xs);
    if (hi - lo < 1e-12) { lo -= 1; hi += 1; }
    const pad = (hi - lo) * 0.04; lo -= pad; hi += pad;
    const X = (x) => (100 * (x - lo) / (hi - lo)).toFixed(2) + "%";
    $("cmp-liste").innerHTML = liste.map((l) => {
      const p = l.p;
      const tete = `<div class="c-nom"><b>${esc(l.nom)}</b> ${badges(l)}</div>`;
      if (p.v === undefined) return `<div class="c-ligne c-absente" role="listitem">${tete}<div class="c-piste"><span class="c-zero" style="left:${X(0)}"></span></div><div class="c-val">—<small>${esc(p.absent)}</small></div></div>`;
      const c = !p.sens || Math.abs(p.v) < 1e-9 ? "neutre" : p.v * p.sens > 0 ? "mieux" : "moins";
      const bande = p.b !== null && p.h !== null ? `<span class="c-bande" style="left:${X(Math.min(p.b, p.h))};width:calc(${X(Math.max(p.b, p.h))} - ${X(Math.min(p.b, p.h))})"></span>` : "";
      const [cs] = STATUTS[p.statut] || [""];
      return `<div class="c-ligne" role="listitem" data-cle="${esc(l.cle)}" data-v="${p.v}">${tete}
        <div class="c-piste" aria-hidden="true"><span class="c-zero" style="left:${X(0)}"></span>${bande}<span class="c-point ${c}" style="left:${X(p.v)}"></span></div>
        <div class="c-val"><span class="c-nombre">${fr(p.v)}</span><small>${p.b !== null && p.h !== null ? `de ${fr(p.b)} à ${fr(p.h)}${p.net ? "" : " : sens pas sûr"}` : "sans bande"}</small><span class="i-statut ${cs}">${esc(STATUT_COURT[p.statut] || p.statut || "")}</span></div></div>`;
    }).join("");
    // Les refus du jumeau complet, avec leur raison et le calcul par leurs mesures.
    const refus = lignes.filter((l) => l.refuse);
    $("cmp-refus").innerHTML = refus.length ? `<div class="i-avert i-refus"><b>Refusés par le jumeau complet :</b><ul>${refus.map((l) => {
      const m = D.precalcul[l.cle + "@mesures"];
      const c = m && m.couverture;
      return `<li><b>${esc(l.nom)}</b> : ${esc((l.r.pourquoi_mode || "").replace(/ : la chaîne des études.*$/, ""))}. Deux lignes : la chaîne des études sur le programme entier (sans les ménages ni les entreprises : plusieurs dimensions y sont absentes, pas nulles), et le jumeau complet sur ses ${c ? c.nombre : ""} mesures et leur interaction${c ? `, qui couvrent ${c.mesures === null ? "un coût inconnu" : fr(c.mesures, 1).replace("+", "") + " Md€"}${c.interaction === null || c.interaction === undefined ? "" : " et " + fr(c.interaction, 2) + " Md€ d'interaction"} des ${fr(c.programme, 1).replace("+", "")} Md€ du programme en ${c.annee} (coût mécanique ; l'interaction ne se lit que sur le solde, pas entre les ménages)` : ""}${c && c.age ? " ; l'âge de départ du programme, dans aucune de ses mesures, est lu par la santé et « Pour vous » comme pour tout programme" : ""}.</li>`;
    }).join("")}</ul></div>` : "";
    tableau(lignes, dims, aChoisie);
    window.impacts.comparaison = { dimension: dChoisie, indicateur: iChoisi, annee: aChoisie, lignes: liste.map((l) => ({ cle: l.cle, nom: l.nom, v: l.p.v ?? null })) };
  }
  let triTable = null;
  function tableau(lignes, dims, annee) {
    const cols = [...dims.values()].map((d) => ({ d, i: d.indicateurs.values().next().value }));
    for (const l of lignes) l.cols = cols.map((c) => point(l.r, c.d.cle, c.i.cle, annee));
    let rows = lignes.slice();
    if (triTable) {
      const k = triTable.k, s = triTable.s;
      rows.sort((a, b) => {
        if (k < 0) return s * a.nom.localeCompare(b.nom, "fr");
        const va = a.cols[k].v, vb = b.cols[k].v;
        if (va === undefined) return vb === undefined ? 0 : 1;
        if (vb === undefined) return -1;
        return s * (va - vb);
      });
    }
    const aria = (k) => !triTable || triTable.k !== k ? "none" : triTable.s > 0 ? "ascending" : "descending";
    const tete = `<thead><tr><th scope="col" aria-sort="${aria(-1)}"><button type="button" data-k="-1">Programme</button></th>${cols.map((c, k) => `<th scope="col" aria-sort="${aria(k)}"><button type="button" data-k="${k}">${esc(c.d.titre)}<small>${esc(c.i.libelle)} (${esc(c.i.unite)})</small></button></th>`).join("")}</tr></thead>`;
    const corps = rows.map((l) => `<tr><th scope="row">${esc(l.nom)}${l.refuse ? " <small>(chaîne des études)</small>" : ""}${l.mesures ? " <small>(jumeau complet)</small>" : ""}</th>${l.cols.map((p) => {
      if (p.v === undefined) return `<td class="c-vide" title="${esc(p.absent)}">—</td>`;
      const c = !p.sens || Math.abs(p.v) < 1e-9 ? "" : p.v * p.sens > 0 ? "c-mieux" : "c-moins";
      const [cs] = STATUTS[p.statut] || [""];
      return `<td class="${c}" data-v="${p.v}"><span>${fr(p.v)}</span>${p.b !== null && p.h !== null ? `<small>${fr(p.b)} à ${fr(p.h)}${p.net ? "" : " ?"}</small>` : "<small>sans bande</small>"}<small class="c-st ${cs}">${esc(STATUT_COURT[p.statut] || "")}</small></td>`;
    }).join("")}</tr>`).join("");
    $("cmp-table").innerHTML = `<caption class="i-cache">Le nombre de tête de chaque dimension en ${annee}, par programme</caption>${tete}<tbody>${corps}</tbody>`;
    for (const b of $("cmp-table").querySelectorAll("thead button")) b.addEventListener("click", () => {
      const k = +b.dataset.k;
      triTable = triTable && triTable.k === k ? { k, s: -triTable.s } : { k, s: k < 0 ? 1 : -1 };
      tableau(lignes, dims, annee);
    });
  }

  /* ------------------------------------------------------------ au départ */
  const voulu = decodeURIComponent((location.hash || "").slice(1));
  if (voulu === "bareme" || voulu.startsWith("bareme=")) {
    montrer("bareme");
    if (voulu.startsWith("bareme=")) suivre(voulu.slice(7));
  }
  const estProgramme = B.groupes.some((g) => g.programme === voulu);
  const estMesure = !estProgramme && B.groupes.some((g) => g.mesures.some((m) => m.cle === voulu));
  if (estMesure) { montrer("mesure"); $("mesure").value = voulu; choisir({ candidat: voulu }); }
  else if (voulu.endsWith("@mesures") && D.precalcul[voulu]) {
    $("programme").value = D.precalcul[voulu].programme; choisir({ candidat: voulu });
  } else {
    const p = estProgramme ? voulu : D.defaut;
    if (p) { $("programme").value = p; choisir({ candidat: p }); }
    if (voulu === "comparer") montrer("comparer");
  }
})();
