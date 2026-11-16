/* « Un ménage comme le mien » (but 25, volet population, D-453).
   Lit les 50 cellules et les cas types chiffrés d'avance que la page porte en JSON, et
   choisit la cellule et le cas type les plus proches des traits donnés. Aucun calcul
   de la loi, aucun envoi : une recherche dans des moyennes publiées. */
(function () {
  "use strict";
  var D = JSON.parse(document.getElementById("donnees-comme-moi").textContent);
  var N = D.types.length;
  var fmt = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 0 });
  function eur(x) { return fmt.format(Math.round(x) || 0) + " €"; }
  function mille(x) {
    return x >= 1e6 ? (x / 1e6).toLocaleString("fr-FR", { maximumFractionDigits: 2 }) +
      " millions" : fmt.format(Math.round(x / 1000) * 1000);
  }
  var ADULTES = { seul: 1, monoparentale: 1, couple_sans_enfant: 2, couple_avec_enfants: 2,
                  complexe: 3 };
  var AVEC_ENFANTS = { monoparentale: 1, couple_avec_enfants: 1, complexe: 1 };

  function uc(type, enfants) {
    return 1 + 0.5 * (ADULTES[type] - 1) + 0.3 * enfants;
  }
  function cellule(decile, type) { return decile * N + D.types.indexOf(type); }
  function moyenne(nom, i) { return D.cellules[nom][i] / D.cellules.menages[i]; }

  /* Le dixième dont le niveau de vie moyen est le plus proche, en proportion. */
  function ranger(type, niveau) {
    var meilleur = 0, ecart = Infinity, niveaux = [];
    for (var k = 0; k < 10; k++) {
      var i = cellule(k, type);
      var nv = D.cellules.revenu_disponible[i] / D.cellules.uc[i];
      niveaux.push(nv);
      var d = Math.abs(Math.log(niveau / nv));
      if (d < ecart) { ecart = d; meilleur = k; }
    }
    return { decile: meilleur, niveaux: niveaux };
  }

  /* Le point du cas type dont le revenu disponible est le plus proche. */
  function casType(type, annuel) {
    var cle = D.cas_types[type];
    if (!cle) return null;
    var cas = D.cas[cle], best = 0, ecart = Infinity;
    cas.points.forEach(function (p, j) {
      var d = Math.abs(p.revenu_disponible - annuel);
      if (d < ecart) { ecart = d; best = j; }
    });
    return { libelle: cas.libelle, point: cas.points[best], salaire: D.salaires[best] };
  }

  function ligne(libelle, valeur) {
    return "<tr><td>" + libelle + "</td><td>" + eur(valeur) + "</td></tr>";
  }

  function dessiner() {
    var type = document.getElementById("type").value;
    var champ = document.getElementById("enfants");
    var avec = !!AVEC_ENFANTS[type];
    champ.disabled = !avec;
    document.getElementById("enfants-l").style.opacity = avec ? 1 : 0.5;
    var enfants = avec ? Math.max(0, Math.min(6, parseInt(champ.value, 10) || 0)) : 0;
    if (type === "couple_avec_enfants" || type === "monoparentale") enfants = Math.max(1, enfants);
    var mensuel = parseInt(document.getElementById("revenu").value, 10);
    document.getElementById("revenu-dit").textContent = fmt.format(mensuel) + " € par mois";
    var annuel = 12 * mensuel;
    var niveau = annuel / uc(type, enfants);
    var r = ranger(type, niveau);
    var i = cellule(r.decile, type);
    var m = D.cellules.menages[i];
    var paie = moyenne("cotisations_salariales", i) + moyenne("csg_crds_salaires", i) +
      moyenne("ir", i) + moyenne("tva", i) + moyenne("accises", i);
    var echelle = r.niveaux.map(function (nv, k) {
      return '<span' + (k === r.decile ? ' class="ici" aria-current="true"' : "") +
        ' title="' + (k + 1) + 'e dixième : ' + eur(nv) + ' par unité de consommation">' +
        (k + 1) + "</span>";
    }).join("");
    var h = '<p class="resultat-tete">Votre niveau de vie : <strong>' + eur(niveau) +
      "</strong> par an et par unité de consommation. Parmi les ménages « " +
      D.libelles[type].toLowerCase() + " », vous ressemblez à ceux du <strong>" +
      (r.decile + 1) + (r.decile === 0 ? "er" : "e") + " dixième</strong> : <strong>" +
      mille(m) + "</strong>" + (m >= 1e6 ? " de" : "") + " ménages, dans la cellule n° " + (i + 1) + ".</p>" +
      '<div class="dixiemes" aria-label="Les dix dixièmes de ce type, du plus modeste au ' +
      'plus aisé">' + echelle + "</div>" +
      '<p class="note-source">Leur niveau de vie moyen : ' + eur(r.niveaux[r.decile]) +
      ". Un ménage de cette cellule compte en moyenne " +
      (D.cellules.personnes[i] / m).toLocaleString("fr-FR", { maximumFractionDigits: 1 }) +
      " personnes, dont " + (D.cellules.en_emploi[i] / m).toLocaleString("fr-FR",
        { maximumFractionDigits: 1 }) + " en emploi.</p>" +
      '<div class="compte-menage"><div><h3>Ce qu\'ils gagnent et reçoivent, par an</h3><table>' +
      ligne("Salaires bruts", moyenne("salaire_brut", i)) +
      ligne("Retraites", moyenne("retraite", i)) +
      ligne("Allocations chômage", moyenne("chomage_brut", i)) +
      ligne("Revenus d'indépendant", moyenne("revenus_non_salaries", i)) +
      ligne("Prestations sociales", moyenne("prestations", i)) +
      ligne("<strong>Revenu disponible</strong>", moyenne("revenu_disponible", i)) +
      "</table></div><div><h3>Ce qu'ils paient, par an</h3><table>" +
      ligne("Cotisations salariales", moyenne("cotisations_salariales", i)) +
      ligne("CSG et CRDS sur les salaires", moyenne("csg_crds_salaires", i)) +
      ligne("Impôt sur le revenu", moyenne("ir", i)) +
      ligne("TVA", moyenne("tva", i)) +
      ligne("Taxes sur l'énergie", moyenne("accises", i)) +
      ligne("<strong>Total</strong>", paie) + "</table></div></div>" +
      '<p class="note-source">Moyennes de la cellule : sa somme sur ses ménages, droit de ' +
      "2024. Les cotisations employeur, payées par l'employeur, ne sont pas comptées ici ; " +
      'elles sont dans <a href="cellules.html#menages">les cellules</a>.</p>';
    var c = casType(type, annuel);
    if (c) {
      var p = c.point;
      h += "<h3>Un cas type proche</h3><p>" + c.libelle + ", " + fmt.format(c.salaire) +
        " € de salaire brut par an au total, chiffré par le moteur au droit de " + D.annee +
        " :</p><table class=\"cas\">" +
        ligne("Salaire brut", p.salaire_brut) +
        ligne("Cotisations salariales", -p.cotisations_salariales) +
        ligne("CSG et CRDS", -(p.csg_deductible + p.csg_imposable + p.crds)) +
        ligne("Impôt sur le revenu", -p.ir) +
        ligne("Prestations", p.prestations) +
        ligne("<strong>Revenu disponible</strong>", p.revenu_disponible) +
        "</table><p class=\"note-source\">Soit " + eur(p.revenu_disponible / 12) +
        " par mois. Le cas type est le point de la grille chiffrée d'avance dont le revenu " +
        'disponible est le plus proche du vôtre (<a href="parcours-1-menage.html">un ' +
        "ménage, pas à pas</a>).</p>";
    } else {
      h += '<p class="note-source">Pas de cas type pour un ménage complexe : sa ' +
        "composition varie trop pour qu'un seul ménage le représente.</p>";
    }
    document.getElementById("resultat").innerHTML = h;
  }
  ["type", "enfants", "revenu"].forEach(function (id) {
    document.getElementById(id).addEventListener("input", dessiner);
  });
  dessiner();
})();
