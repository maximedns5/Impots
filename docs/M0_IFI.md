# M0 — reconnaissance IFI, et ce que la table publiée n'a pas

Portail : `python scripts/verify_ifi.py`. Vert. Rien dans `patrimoine/` ne s'appuie sur
les cellules tant qu'il ne l'est pas.

## Le résultat qui compte : le spec se trompe sur ce qui est publié

`PHASE5_SPEC.md` §2 dit que la table DGFiP par tranche publie « redevable counts,
taxable base, tax due », et fonde tout le dessin du module là-dessus : appliquer notre
barème à la **base publiée par tranche** et comparer à l'**impôt publié par tranche**.

**La base par tranche n'est pas publiée.** Vérifié en lisant les quatre millésimes,
feuille par feuille et cellule par cellule. Ce qui existe :

| Grandeur | Où | Granularité |
|---|---|---|
| Part des foyers imposables | n° 33, Graphique 3 | par tranche (4) |
| Part dans l'IFI total | n° 33, Graphique 3 | par tranche (4) |
| IFI moyen | n° 33, Graphique 3 | par tranche (4) |
| Effectif, **patrimoine net total**, IFI payé, dons | n° 45, Tableau 1 | **agrégat seul** |
| Composition du patrimoine immobilier moyen | n° 23, Graphique 3 | par tranche — pour §4 |

Quatre tranches, pas six : la tranche 0,8–1,3 M du barème n'apparaît jamais, parce que
l'assujettissement commence à 1,3 M. Un lecteur qui aligne les tranches publiées sur les
tranches du barème en décale une.

## La vérification de remplacement, et pourquoi elle n'est pas plus faible

À défaut de base par tranche : **inverser le barème** sur l'IFI moyen de chaque tranche
pour obtenir la base moyenne implicite, puis confronter l'agrégat reconstitué à
l'agrégat publié **indépendamment**. Rien n'est ajusté — l'impôt par tranche et la base
agrégée sont deux publications séparées, et c'est notre arithmétique qui les relie.

Deux propriétés falsifiables en sortent, et c'est ce qui fait la vérification :

1. **La base moyenne implicite doit tomber DANS sa propre tranche.** Rien ne l'y force.
   Un barème mal lu place une moyenne hors de son propre intervalle. Mesuré :
   1,7052 / 3,1772 / 6,0747 / 14,7126 M€ — les quatre dedans.
2. **Le manque doit avoir le bon signe.** La décote, le plafonnement et la réduction
   dons baissent tous l'impôt ; inverser l'impôt doit donc **sous-estimer** la base.
   Mesuré : 436,63 md reconstitués contre 466,79 md publiés, soit **−6,46 %**. Un
   manque de signe inverse aurait voulu dire que notre arithmétique est fausse, pas
   incomplète.

Ordre de grandeur pour situer les −6,46 % : les dons IFI valent 220,7 M€ de base
déclarée, soit environ 165 M€ de réduction d'impôt à 75 %, et la décote joue sur la
fenêtre 1,3–1,4 M. M2 décompose ; M0 constate seulement que le signe et la taille sont
ceux que les postes non modélisés prédisent.

## Ce que la table s'est vérifiée à elle-même

Les deux routes publiées vers l'IFI d'une tranche — sa part du total, et son IFI moyen
multiplié par son effectif — sont **deux nombres distincts de la publication**. Ils
concordent à **+0,003 %** sur les quatre tranches. C'est une vérification de notre
lecture (colonnes appariées, unités, effectifs) et non une tautologie.

## Pièges rencontrés, notés pour la suite

* **L'en-tête ment sur les unités.** n° 45 Tableau 1 titre ses lignes « (M€) » et ses
  cellules sont en **euros** : `Patrimoine net total (M€)` vaut 466 792 714 707. C'est
  le piège des niches (milliers contre euros) dans l'autre sens. `_plausible()` refuse
  un total hors bande plutôt que de croire l'en-tête ou la cellule.
* **Les feuilles ne sont pas adressables par coordonnées.** Le libellé de ligne est en
  colonne 2 dans n° 45 et le bloc de données de n° 33 commence ligne 26 sous un
  graphique. Les deux lecteurs **cherchent** leur bloc par forme ; aucun n'indexe.
* **Les bornes de tranche sont vérifiées contre les libellés du fichier**, pas
  codées en dur en silence : une publication qui recouperait ses tranches serait lue
  avec les anciennes bornes sans que rien ne le dise.
* **Un millésime de plus que le spec.** `n° 45` (avril 2026) publie l'IFI 2025 —
  193 600 foyers, 2,3319 md — et porte 2024 en colonne de comparaison. Le spec ne le
  connaît pas. Les deux sont manifestés ; les tranches restent lues sur n° 33 (2024),
  et la règle de millésime du comparateur s'applique avec force.

## L'effectif publié est arrondi, et l'exact est récupérable

`Effectif` vaut **186 100** dans le bulletin — arrondi à la centaine. Le patrimoine net
total et le patrimoine moyen, eux, sont donnés en pleine précision, et leur quotient
vaut **186 094,000**. **Entier**, à six décimales près : c'est cela qui l'identifie
comme l'effectif vrai plutôt qu'un artefact de division.

Ce n'est pas un détail cosmétique. Chaque effectif de tranche est une part de ce nombre,
et le module revendique une vérification mécanique à calibration zéro : introduire
0,0032 % d'erreur sans raison sous chaque figure de la phase serait exactement le genre
de petite chose qui ne se voit jamais. Les cellules sont donc bâties sur l'effectif
récupéré, et l'intégralité du quotient est ce que le test assert.

## Millésimes, à énoncer sur chaque figure publiée

* **Année d'imposition** des tranches : 2024 (n° 33, paru avril 2025).
* **Année d'imposition** des agrégats : 2024 et 2025 disponibles (n° 45, paru avril 2026).
* **Année budgétaire de comptabilisation** : distincte des deux, à établir en M5 contre
  la ligne budgétaire, pas contre cette phrase.

## Le contrôle fantôme

`impot_fortune_immobiliere_ifi_partir_2018` est **lu par une formule** du paquet — le
portail le vérifie, et ce n'est pas une politesse : l'arbre mort `aide_a_domicile`
(D-064, D-075) vit à un espace de noms de là, et six autres doublons morts ont été
confirmés dans l'arbre amont. Le barème résolu est exactement celui que §1 annonce :
800 k 0,5 % · 1,3 M 0,7 % · 2,57 M 1,0 % · 5 M 1,25 % · 10 M 1,5 %.
