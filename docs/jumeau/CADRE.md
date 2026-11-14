# Le cadre du jumeau numérique (but 23, lot 1)

Ce document fixe les conventions que tous les lots du jumeau branchent (D-404). Il dit ce
qu'est l'état de l'économie, comment il avance d'une année, ce qu'est un bloc, quelles
identités tiennent à chaque pas, et comment une mesure y entre. Un lot qui a besoin d'en
changer une règle l'écrit ici, dans sa D-entrée, avant de coder.

## 1. Ce que le cadre est, et ce qu'il n'est pas

Le cadre est le **socle comptable et temporel** du jumeau, dans `src/impots/jumeau/`. Il ne
porte aucun comportement économique propre : les comportements sont dans des blocs. Il
garantit trois choses, quels que soient les blocs branchés :

1. **Les identités tiennent** à chaque pas, à 1e-9 du PIB près ; sinon le pas refuse.
2. **Chaque nombre se décompose** par bloc et par mesure : on sait toujours d'où il vient.
3. **Le pas est rapide** : du numpy pur, sans lecture de fichier, vectorisé sur un axe de
   tirages, pour que les curseurs tournent en direct (lot 7).

La chaîne actuelle des études (`predictif.chaine`, `predictif.rejouer`) se retrouve comme
un cas particulier du jumeau : mêmes scénarios, mêmes blocs, même Δb à 1e-9 près.

## 2. L'état de l'économie

`Etat` porte, pour une année t, des grandeurs en **milliards d'euros courants** (sauf
mention contraire), chacune un tableau numpy de forme `(n,)`, n le nombre de tirages (n = 1 pour
un calcul simple). Chaque champ a son unité, son code de comptabilité nationale (SEC 2010)
et sa source dans `jumeau/champs.py`, qui est le registre unique.

**Les emplois du PIB** (Insee, comptes nationaux, T_1101) :
PIB = C_ménages + C_APU + FBCF_sociétés + FBCF_ménages + FBCF_APU + ΔStocks + X − M.
Chaque composante a sa valeur et son déflateur (indice, année précédente = 1). Le PIB en
volume se chaîne comme l'Insee : sa croissance est la somme des croissances en volume des
composantes pondérées par leurs parts nominales de l'année précédente.

**Les revenus** : PIB = D1 (rémunérations) + EBE et revenu mixte + (D2 − D3) + écart
statistique. L'écart statistique est un champ nommé, lu dans les données pour l'histoire,
tenu constant en part du PIB en projection : jamais un résidu silencieux.

**Les administrations publiques** (S13, Insee t. 3.201 et 3.217) :

* recettes : impôts sur la production (D2, dont TVA), impôts courants sur le revenu et le
  patrimoine (D5 : IR, CSG, IS…), cotisations sociales (D61), impôts en capital (D91),
  autres recettes ; le détail par impôt de t. 3.217 en sous-champs ;
* dépenses : consommation (C_APU), prestations (D62, D632), subventions (D3), intérêts
  nets (D41, emplois moins ressources, `dette.comptes`), FBCF_APU, autres ;
* solde B9 = recettes − dépenses ; solde primaire = B9 + intérêts nets.

**La dette** (Maastricht) : D_t = D_{t−1} − B9_t + SFA_t ; ratio b_t = D_t / PIB_t ; taux
implicite = intérêts nets_t / D_{t−1}. Le SFA est un champ nommé (lu pour l'histoire,
Eurostat ; nul en projection, par une convention dite).

**Le travail** (lot 4) : population active, emploi total et salarié, chômage, salaire
moyen par tête. **Les entreprises** (lot 2) : stock de sociétés, créations, fermetures,
productivité moyenne, investissement. **Le reste du monde** (lot 3) : demande mondiale,
prix relatifs, exportations, importations, solde courant.

**Un champ non calculé est absent, pas nul.** L'état porte un masque : un champ que
personne n'a écrit est absent, et une identité ou un graphique qui le lit refuse en le
nommant. Aucun NaN ne circule.

## 3. Le pas annuel

`pas(etat_prec, entrees_t, mesures_t, theta, blocs) -> etat_t` :

1. **Les entrées exogènes** de l'année : les scénarios nommés de croissance, de prix, de
   taux et de dépense (`dette.scenarios`, `dette.reference`), la demande mondiale, la
   démographie. Ils sont nommés comme aujourd'hui ; changer un scénario change la
   réponse.
2. **Les chocs statiques** des mesures de l'année (§5) s'inscrivent sur leurs champs.
3. **Les blocs** tournent dans l'ordre que leurs déclarations imposent (§4). La boucle
   simultanée (activité → revenus → recettes → consommation → activité) se résout par
   point fixe de Gauss-Seidel : tolérance 1e-10 en relatif, 100 itérations au plus ; un
   pas qui ne converge pas refuse, avec le bloc et le champ en cause.
4. **Le cadre ferme les comptes**, et lui seul : les sommes de recettes et de dépenses,
   B9, la dette, les ratios, le taux implicite, le PIB chaîné. Aucun bloc ne les écrit.
5. **Les identités sont vérifiées** (§6) ; une identité violée arrête le pas.

Deux trajectoires se calculent toujours ensemble, la **référence** (sans les mesures) et
la **variante** (avec), sous les mêmes scénarios et le même θ. Le résultat publié est
leur **différence**, avec les deux niveaux à côté, comme la chaîne actuelle (D-213).

## 4. Les blocs

Un bloc est un module de `src/impots/jumeau/blocs/` qui déclare :

* `nom` ;
* `lit` et `ecrit` : les champs qu'il lit et ceux auxquels il ajoute une contribution ;
* `thetas` : ses paramètres incertains, chacun une ligne θ (§7) ;
* ses **équations**, écrites dans sa docstring, avec leurs sources (document et page) ;
* `contribue(ctx) -> dict[champ, tableau]` : ses contributions de l'année.

**Une contribution est additive et gardée à part.** Plusieurs blocs peuvent écrire le même
champ : le cadre somme leurs contributions et garde chacune, par bloc et par mesure. C'est
ce qui fait les cascades « comment le nombre se forme » du but 22, à chaque année. Un
bloc qui lit un champ qu'aucun bloc antérieur ni le cadre n'a écrit est refusé à la
construction, pas au calcul.

**Les blocs du lot 1**, le minimum pour que le cadre tourne et retrouve la chaîne :

* `tendance` : la trajectoire de référence (croissance, prix, règle de dépense, recettes
  constantes en part du PIB : la convention de `dette.reference`) ;
* `mesures` : les chocs statiques des mesures sur les recettes et les dépenses (§5) ;
* `mesange` : l'impulsion par instrument → PIB → solde, la boucle de `predictif.
  retroaction` réécrite en bloc, avec son θ de multiplicateur ;
* `creations` : le canal du but 22 (`predictif.creations`), tel quel, en bloc. Le lot 2 le
  remplacera.

## 5. Les mesures

Une `Mesure` porte un identifiant, un libellé, son auteur (gouvernement, candidat, loi
hypothétique), ses années d'effet, et ses **chocs statiques par année** :

* sur les recettes et les dépenses des APU, par catégorie (Md€, signe du moteur : un coût
  est positif) ;
* sur les instruments de Mésange (l'impulsion) ;
* sur les ménages par décile (pour le lot 4) et sur les entreprises par taille et par
  impôt (pour le lot 2), quand le rapport les porte.

Le choc statique vient **d'une passe déjà faite sur la population**, une fois, et il porte
son rapport et son commit (`Mesure.depuis_rapport`). Une loi hypothétique, pour les
curseurs, se déclare directement (`Mesure.hypothese`) et le dit sur chaque nombre qu'elle
touche. Le jumeau ne relance jamais OpenFisca dans un pas.

## 6. Les identités vérifiées à chaque pas

Toutes à 1e-9 × PIB près, sur chaque tirage :

1. les emplois du PIB sommés égalent le PIB nominal ;
2. les revenus, écart statistique compris, égalent le PIB ;
3. les recettes et les dépenses des APU égalent la somme de leurs catégories, et
   B9 = recettes − dépenses ;
4. D_t = D_{t−1} − B9_t + SFA_t ;
5. chaque champ égale la somme de ses contributions (référence plus blocs plus mesures).

**Sur l'histoire, les identités se vérifient d'abord sur les données publiées** :
`etat_initial(annee)`, de 2010 à 2025, lu dans les tables manifestées, doit les tenir avec
son écart statistique publié. Si les comptes publiés ne bouclent pas comme le cadre le
dit, c'est le cadre qu'on corrige.

## 7. Les θ

Chaque paramètre incertain est une ligne θ, au format de `predictif.theta` : une clé, sa
**définition mathématique** (l'équation où il entre), son unité, sa valeur à θ = 0, à
θ = 1 et à θ½, sa direction, et sa source (document, page, tableau). Une valeur choisie
sans source le dit (« choisie, non vérifiée »), comme D-402. θ se règle de 0 à 1 ; un
tirage Monte-Carlo prend θ sur l'axe des tirages. Les θ de tous les blocs vivent dans un
registre unique, `jumeau/thetas.py`, que les curseurs lisent.

## 8. Les performances, et le navigateur

Le pas ne lit aucun fichier et n'utilise ni pandas ni OpenFisca. Les cibles, mesurées une
fois et dites dans la D-entrée du lot (pas de test de temps, D-335) : une trajectoire de
dix ans, n = 1, en moins de 50 ms ; n = 2 000 en moins de 2 s. Le portage dans le
navigateur est le lot 7. Il réécrira le pas en JavaScript, tenu égal au Python par un
test, comme `site_explorer` aujourd'hui, ou utilisera Pyodide. Le lot 1 garde le cœur
portable : des fonctions pures sur des tableaux.

## 9. L'organisation du code

```
src/impots/jumeau/
  champs.py       le registre des champs : unité, code SEC, source, lot propriétaire
  etat.py         Etat, le masque des absents, les contributions par bloc et par mesure
  identites.py    les identités du §6, les résidus, le refus
  pas.py          le pas annuel, le point fixe, la fermeture des comptes
  trajectoire.py  référence et variante, la différence, sous scénarios et θ nommés
  mesures.py      Mesure, depuis_rapport, hypothese
  thetas.py       le registre des θ
  historique.py   etat_initial(annee), 2010 à 2025, depuis les tables manifestées
  blocs/          tendance, mesures, mesange, creations ; puis ceux des lots 2 à 4
  parametres/     les valeurs des blocs, en YAML, chacune avec sa source
```

## 10. Ce que le lot 1 doit prouver

* **Les identités** : un test fait tourner le cadre sous des blocs et des mesures
  synthétiques, sur plusieurs θ et un axe de tirages, et vérifie le §6 à chaque pas.
* **La chaîne retrouvée** : avec `tendance`, `mesures`, `mesange` et les scénarios des
  études, Δb du jumeau égale `rejouer.chemin` à 1e-9 près, sur les mêmes passes que
  `tests/test_rejouer.py`, sous les trois persistances et plusieurs θ ; puis avec
  `creations`.
* **L'histoire lue** : `etat_initial(annee)` tient les identités sur les données publiées,
  de 2010 à 2025 (un test lourd s'il lit les fichiers bruts, sinon léger).
* **Un nombre décomposé** : la contribution de chaque bloc et de chaque mesure à Δb₂₀₃₅
  se somme à Δb₂₀₃₅.

Ce que le lot 1 ne fait pas : les comportements des entreprises (lot 2), du commerce (lot
3) et des ménages (lot 4), les séries et la base des mesures votées (lot 5), l'estimation
et le juge du passé (lot 6), les curseurs (lot 7). Leurs champs existent dans le registre,
absents.
