// Les comportements (parcours, page 4) : un θ par élasticité, appliqué aux statistiques des
// canaux qu'un rapport d'étude porte (`years[].statistiques.<vue>.canaux`). Chaque ligne du
// magasin prend sa valeur à θ par son centre publié (`rejouer.value_at`) ; chaque canal
// rend sa recette par la formule de `rejouer.receipts` (C1 : ε_tous A_bas + ε_haut A_haut ;
// C7 : Σ ε_g S_g ; C11 à partir des emplois de C2). La dette suit par `activite.js`, le
// multiplicateur à θ½ et la persistance lue. Un test tient ces nombres égaux au moteur.
(function (root) {
  "use strict";
  const A = typeof module !== "undefined" && module.exports
    ? require("./activite.js") : root.ParcoursActivite;

  // Une année d'un rapport aux valeurs `values` : le coût mécanique, la recette de chaque
  // canal (positive quand elle rapporte), les emplois de C2, le coût après comportements.
  function annee(payload, k, view, values) {
    const row = payload.years[k];
    const cost = +row[A.VIEWS[view]];
    const stats = row.statistiques[view];
    const parts = A.canaux(stats.canaux, values);
    const recettes = A.receipts(-cost, stats.canaux, values);
    return { year: +row.year, mecanique: cost, parts, apres: -recettes };
  }

  const api = { annee };
  if (typeof module !== "undefined" && module.exports) { module.exports = api; return; }
  root.ParcoursComportements = api;

  if (typeof document === "undefined") return;
  const ici = document.getElementById("c-curseurs");
  if (!ici) return;
  const D = root.PARCOURS_COMPORTEMENTS;
  const choix = document.getElementById("c-etude");
  const sortie = document.getElementById("c-resultat");
  const curseurs = [...ici.querySelectorAll("input[data-ligne]")];
  const NOMS = { c1_eti: "C1", c7_labour_supply: "C7", c10_dividendes: "C10", c11_autofinancement: "C11" };

  function rendre() {
    const e = D.etudes[+choix.value];
    const lignes = e.payload.rejeu.lignes;
    const theta = { [A.MACRO_ROW]: 0.5 };
    // Les canaux dont le rapport porte une recette : une ligne d'un autre canal est montrée,
    // et dite sans effet ici (le poids du Trésor-Éco quand C11 reste fermé).
    const actifs = new Set();
    for (const y of e.payload.years) for (const k of Object.keys(y.statistiques.vieillie.canaux || {})) actifs.add(k);
    for (const input of curseurs) {
      const key = input.dataset.ligne;
      const boite = input.closest(".curseur");
      const ouvert = key in lignes;
      boite.hidden = !ouvert;
      if (!ouvert) continue;
      theta[key] = +input.value;
      const v = A.valueAt(lignes[key], +input.value);
      document.getElementById("v-" + key).textContent = "θ " + A.nombre(+input.value, 2) + " → " + A.nombre(v, 4)
        + (actifs.has(D.canaux[key]) ? "" : " (sans effet ici : son canal reste fermé)");
    }
    const [values] = A.thetaValues(lignes, theta);
    const view = "vieillie";
    const ans = e.payload.years.map((_, k) => annee(e.payload, k, view, values));
    const cles = A.RECETTES.filter((c) => ans.some((a) => c in a.parts));
    const emplois = ans.some((a) => "emplois_c2" in a.parts);
    const tete = "<th>année</th><th>coût mécanique</th>"
      + cles.map((c) => `<th>recette ${NOMS[c]}</th>`).join("")
      + (emplois ? "<th>emplois C2 (indice)</th>" : "") + "<th>coût après comportements</th>";
    const corps = ans.map((a) => `<tr><td>${a.year}</td><td class="num">${A.md(a.mecanique)}</td>`
      + cles.map((c) => `<td class="num">${A.md(a.parts[c])}</td>`).join("")
      + (emplois ? `<td class="num">${A.signe(a.parts.emplois_c2, 0)}</td>` : "")
      + `<td class="num">${A.md(a.apres)}</td></tr>`).join("");
    const d = A.atTheta(e.payload, theta, { view, persistence: A.READ, variante: null }).delta;
    sortie.innerHTML = `<table><thead><tr>${tete}</tr></thead><tbody>${corps}</tbody></table>`
      + `<p>Dette en ${ans[ans.length - 1].year}, avec la mesure moins sans elle, multiplicateur à θ½ : `
      + `<strong>${A.pt(d[d.length - 1])}</strong>. Toutes les lignes à θ½, la page redonne `
      + `${A.pt(e.temoin)}, le nombre de la page de l'étude.</p>`;
  }
  choix.addEventListener("input", rendre);
  for (const input of curseurs) input.addEventListener("input", rendre);
  rendre();
})(typeof window !== "undefined" ? window : globalThis);
