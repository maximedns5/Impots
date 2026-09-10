# A0 — le budget d'exactitude

*Produit par `scripts/accuracy_budget.py` le 2026-09-10. Graine 20260910. Chaque nombre de ce fichier est calculé par ce script ; aucun n'y est recopié.*

Ce budget classe les sources d'incertitude déclarées, réforme de référence par réforme de référence. **Son classement ordonne les leviers L1-L6 de la phase 7**, et un levier qu'il classe bas est écarté avec son score au dossier : refuser du travail est un résultat.

## Ce que ce budget peut et ne peut pas comparer

Trois classes, et **une part ne se calcule jamais entre elles** :

* **`sampled`** — une loi nommée et tirable existe. La part de variance est une mesure.
* **`swing`** — seules deux bornes existent. La largeur est mesurée ; la convertir en variance suppose une forme sur l'intervalle (`VARIANCE_OF_A_RANGE = 12`, une convention isolée dans une constante nommée pour être contestable en un seul endroit).
* **`unmeasured`** — la spec déclare la source, le dépôt n'a ni loi ni bornes. Rapportée **sans part**, jamais omise : une source absente d'un budget se lit « elle ne compte pas ».

## Les huit réformes de référence

| clé | famille | réforme | chaîne |
|---|---|---|---|
| `bareme` | barème | Décote : taux porté à 30 % | household |
| `allegements` | allègements | Allègements généraux : plafond porté à 2 SMIC | household |
| `prestations` | prestations | RSA : montant de base porté à 700 € | household |
| `niches` | niches | Plafond du quotient familial porté à 1 000 € | household |
| `is` | IS | IS : taux normal porté à 30 % | firm |
| `cvae` | CVAE | CVAE : taux maximal porté à 0,5 % | firm |
| `ifi` | IFI | IFI : seuil d'assujettissement porté à 2 M€ | patrimoine |
| `trajectoire` | trajectoire | Gel du barème, trajectoire 2026-2029 | trajectory |

## Résultats, cas par cas

### Décote : taux porté à 30 %

*aucune source mesurable aujourd'hui.*

* **store comportemental (lois tirables) — NON MESURÉE.** attribuer la variance par paramètre demande de rejouer band.compute sur les tableaux d'une passe plein tarif ; le coût est une passe moteur par cas, pas par tirage. Prévu en A0 v2. Mesuré au gate : le store porte 10 lignes dont 2 dégénérées, et in_revenue_band n'apparaît que deux fois — trois lignes seulement peuvent déplacer un euro.
* **construction de la population (graines skeleton/incomes) — NON MESURÉE.** les graines de construction (20240101) ne sont tirées qu'une fois et la France synthétique n'est jamais reconstruite ; mesurer cette source demande une reconstruction complète à une seconde graine, c'est un gate en soi. Le sous-échantillon N'EST PAS un substitut : sa variance est nulle en production.

### Allègements généraux : plafond porté à 2 SMIC

*aucune source mesurable aujourd'hui.*

* **store comportemental (lois tirables) — NON MESURÉE.** attribuer la variance par paramètre demande de rejouer band.compute sur les tableaux d'une passe plein tarif ; le coût est une passe moteur par cas, pas par tirage. Prévu en A0 v2. Mesuré au gate : le store porte 10 lignes dont 2 dégénérées, et in_revenue_band n'apparaît que deux fois — trois lignes seulement peuvent déplacer un euro.
* **construction de la population (graines skeleton/incomes) — NON MESURÉE.** les graines de construction (20240101) ne sont tirées qu'une fois et la France synthétique n'est jamais reconstruite ; mesurer cette source demande une reconstruction complète à une seconde graine, c'est un gate en soi. Le sous-échantillon N'EST PAS un substitut : sa variance est nulle en production.

### RSA : montant de base porté à 700 €

*aucune source mesurable aujourd'hui.*

* **store comportemental (lois tirables) — NON MESURÉE.** attribuer la variance par paramètre demande de rejouer band.compute sur les tableaux d'une passe plein tarif ; le coût est une passe moteur par cas, pas par tirage. Prévu en A0 v2. Mesuré au gate : le store porte 10 lignes dont 2 dégénérées, et in_revenue_band n'apparaît que deux fois — trois lignes seulement peuvent déplacer un euro.
* **construction de la population (graines skeleton/incomes) — NON MESURÉE.** les graines de construction (20240101) ne sont tirées qu'une fois et la France synthétique n'est jamais reconstruite ; mesurer cette source demande une reconstruction complète à une seconde graine, c'est un gate en soi. Le sous-échantillon N'EST PAS un substitut : sa variance est nulle en production.

### Plafond du quotient familial porté à 1 000 €

*aucune source mesurable aujourd'hui.*

* **store comportemental (lois tirables) — NON MESURÉE.** attribuer la variance par paramètre demande de rejouer band.compute sur les tableaux d'une passe plein tarif ; le coût est une passe moteur par cas, pas par tirage. Prévu en A0 v2. Mesuré au gate : le store porte 10 lignes dont 2 dégénérées, et in_revenue_band n'apparaît que deux fois — trois lignes seulement peuvent déplacer un euro.
* **construction de la population (graines skeleton/incomes) — NON MESURÉE.** les graines de construction (20240101) ne sont tirées qu'une fois et la France synthétique n'est jamais reconstruite ; mesurer cette source demande une reconstruction complète à une seconde graine, c'est un gate en soi. Le sous-échantillon N'EST PAS un substitut : sa variance est nulle en production.

### IS : taux normal porté à 30 %

Chiffrage central : **-15,5262 md€**.

| source | écart-type | part | tirages |
|---|---|---|---|
| placement intra-cellule des entreprises | 0,0717 md€ | 100,0 % | 128 |

* **encadrement de cellule (entreprises) — NON MESURÉE.** rien dans src/impots/entreprises/ ne calcule de bas/haut : FirmAggregates n'a pas de champ d'intervalle. L'incertitude de cellule y est portée par le placement, pas par une borne.
* **construction de la population (graines skeleton/incomes) — NON MESURÉE.** les graines de construction (20240101) ne sont tirées qu'une fois et la France synthétique n'est jamais reconstruite ; mesurer cette source demande une reconstruction complète à une seconde graine, c'est un gate en soi. Le sous-échantillon N'EST PAS un substitut : sa variance est nulle en production.

### CVAE : taux maximal porté à 0,5 %

Chiffrage central : **-1,8545 md€**.

| source | écart-type | part | tirages |
|---|---|---|---|
| placement intra-cellule des entreprises | 0,0467 md€ | 100,0 % | 128 |

* **encadrement de cellule (entreprises) — NON MESURÉE.** rien dans src/impots/entreprises/ ne calcule de bas/haut : FirmAggregates n'a pas de champ d'intervalle. L'incertitude de cellule y est portée par le placement, pas par une borne.
* **construction de la population (graines skeleton/incomes) — NON MESURÉE.** les graines de construction (20240101) ne sont tirées qu'une fois et la France synthétique n'est jamais reconstruite ; mesurer cette source demande une reconstruction complète à une seconde graine, c'est un gate en soi. Le sous-échantillon N'EST PAS un substitut : sa variance est nulle en production.

### IFI : seuil d'assujettissement porté à 2 M€

Chiffrage central : **-1,0052 md€**.

| source (bornes) | largeur | part entre bornes |
|---|---|---|
| placement intra-tranche (IFI) | 0,1753 md€ | 100,0 % |

* **facteur de composition (ISF) — NON MESURÉE.** CompositionFactor est plat et sourcé sur un seul fractile (D-085) ; le module écrit lui-même « rien ici n'est un intervalle de confiance ». Il ne s'applique qu'au chiffrage ISF, pas à ce cas.
* **construction de la population (graines skeleton/incomes) — NON MESURÉE.** les graines de construction (20240101) ne sont tirées qu'une fois et la France synthétique n'est jamais reconstruite ; mesurer cette source demande une reconstruction complète à une seconde graine, c'est un gate en soi. Le sous-échantillon N'EST PAS un substitut : sa variance est nulle en production.

### Gel du barème, trajectoire 2026-2029

*aucune source mesurable aujourd'hui.*

* **hypothèse d'uprating — NON MESURÉE.** la paire vieillie/gelée N'EST PAS un intervalle d'uprating : sa borne basse chiffre une population dont les revenus n'ont pas bougé. Un vrai balayage demande deux hypothèses SOURCÉES autour de l'hypothèse déclarée, et ce projet ne prévoit ni salaires ni prix — les bornes sont à l'appelant de les sourcer.
* **construction de la population (graines skeleton/incomes) — NON MESURÉE.** les graines de construction (20240101) ne sont tirées qu'une fois et la France synthétique n'est jamais reconstruite ; mesurer cette source demande une reconstruction complète à une seconde graine, c'est un gate en soi. Le sous-échantillon N'EST PAS un substitut : sa variance est nulle en production.

## La résolution de l'instrument, qui n'est PAS une source

Mesuré sur « Décote : taux porté à 30 % », 12 tirages de sous-échantillon à n = 4 000 ménages : moyenne 3,1229 md€, écart-type **0,0427 md€**, soit 1,37 % du chiffrage.

**Cette variance vaut exactement zéro en production.** `runner.run(sample=None)` chiffre la frame entière : re-tirer le sous-échantillon ne déplace rien de ce qui est déployé. Elle n'est donc pas une source d'erreur du modèle, et la classer comme telle enverrait la phase 7 vers une grandeur qui n'existe pas quand le modèle tourne pour de vrai.

Ce qu'elle dit en revanche, et pourquoi elle est ici : c'est **la finesse avec laquelle A0 peut séparer deux sources** lorsqu'il mesure sur un sous-échantillon. Toute source dont la contribution est plus petite que cet écart-type est indiscernable du bruit de tirage, et le budget ne doit pas prétendre les ordonner.

D-074 avait déjà mesuré la même chose par l'autre bout : 1,49 point d'écart-type par tirage sur la ligne barème à n = 50 000.

## Ce que ce passage ordonne

Rapportée au chiffrage central de son propre cas — la seule façon de comparer une source à travers des réformes d'ordres de grandeur différents :

| famille | source | contribution relative | méthode |
|---|---|---|---|
| IFI | placement intra-tranche (IFI) | 17,44 % | `swing` |
| CVAE | placement intra-cellule des entreprises | 2,52 % | `sampled` |
| IS | placement intra-cellule des entreprises | 0,46 % | `sampled` |

**Le plus gros contributeur mesuré à ce jour est placement intra-tranche (IFI) sur IFI, à 17,44 % du chiffrage.** 

Et la lecture qui compte davantage que le classement lui-même : **le placement pèse relativement bien plus sur la CVAE que sur l'IS**, alors que c'est la même mesure de placement tirée de la même façon. La raison est structurelle et non statistique — la CVAE est un instrument à coudes, l'IS est quasi linéaire dans la tranche qui porte l'essentiel de l'assiette, et un placement qui déplace des entreprises de part et d'autre d'un coude change le résultat là où une transformation linéaire l'ignore. C'est le même argument que le refus de la classe seuil-sur-ratio (D-105.2), rencontré ici par la mesure au lieu de l'être par le raisonnement.

**Ce que ce passage NE dit pas.** Quatre des huit cas n'ont aucune source mesurable aujourd'hui, et trois sources déclarées par la spec sont NON MESURÉES avec leur raison. Le classement ci-dessus ordonne donc ce qui a pu être mesuré, pas l'ensemble des erreurs du modèle : le lire comme un classement complet serait exactement l'erreur que ce budget existe pour éviter.

