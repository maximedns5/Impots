# A0 — le budget d'exactitude

*Produit par `scripts/accuracy_budget.py` le 2026-09-11. Graine 20260910. Chaque nombre de ce fichier est calculé par ce script ; aucun n'y est recopié.*

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

## A0 v2 — la bande comportementale : mesurée, puis REFUSÉE

Quantité attribuée : **la largeur de la bande publiée (p90 − p10)**, non une variance. `BehaviouralResult` n'expose pas les tirages par canal — il porte des percentiles, et des percentiles ne s'additionnent pas — donc une décomposition de variance n'est pas disponible par l'API publique.

Méthode : épingler une ligne à sa valeur centrale et remesurer ; la différence est sa contribution au premier ordre. Le mécanisme fonctionne. **Ce qu'il produit n'est pas classable**, et voici pourquoi.

| réforme | n | largeur de bande | ligne dominante | part | conjoints |
|---|---|---|---|---|---|
| Décote : taux porté à 30 % | 2 000 | 0,0359 md€ | `eti_top_decile` | 33,7 % | 45,0 % |
| Décote : taux porté à 30 % | 3 000 | 0,0607 md€ | `eti_top_decile` | 87,8 % | 13,6 % |
| Décote : taux porté à 30 % | 4 000 | 0,0264 md€ | `eti_top_decile` | 44,9 % | 42,8 % |
| Décote : taux porté à 30 % | 6 000 | 0,0326 md€ | `eti_all` | 30,0 % | 45,6 % |
| Allègements généraux : plafond porté à 2 SMIC | 2 000 | **refusé : bande de largeur nulle** | — | — | — |
| Allègements généraux : plafond porté à 2 SMIC | 3 000 | **refusé : bande de largeur nulle** | — | — | — |
| Allègements généraux : plafond porté à 2 SMIC | 4 000 | **refusé : bande de largeur nulle** | — | — | — |
| Allègements généraux : plafond porté à 2 SMIC | 6 000 | **refusé : bande de largeur nulle** | — | — | — |
| RSA : montant de base porté à 700 € | 2 000 | **refusé : bande de largeur nulle** | — | — | — |
| RSA : montant de base porté à 700 € | 3 000 | **refusé : bande de largeur nulle** | — | — | — |
| RSA : montant de base porté à 700 € | 4 000 | **refusé : bande de largeur nulle** | — | — | — |
| RSA : montant de base porté à 700 € | 6 000 | **refusé : bande de largeur nulle** | — | — | — |
| Plafond du quotient familial porté à 1 000 € | 2 000 | 0,2620 md€ | `eti_top_decile` | 92,1 % | 9,3 % |
| Plafond du quotient familial porté à 1 000 € | 3 000 | 0,0322 md€ | `eti_all` | 100,0 % | 0,0 % |
| Plafond du quotient familial porté à 1 000 € | 4 000 | 0,0420 md€ | `eti_top_decile` | 33,4 % | 45,1 % |
| Plafond du quotient familial porté à 1 000 € | 6 000 | 0,0287 md€ | `eti_all` | 59,3 % | 34,1 % |

**La largeur de bande elle-même varie d'un facteur 9,1 selon la taille du sous-échantillon**, sans tendance, et la ligne dominante bascule entre `eti_top_decile` et `eti_all` sur 2 des 2 cas mesurés. Un classement lu sur une seule taille aurait donc été un fait sur le tirage, pas sur le modèle.

**La cause était déjà mesurée dans ce même rapport.** La section résolution donne le bruit de sous-échantillon à environ 1,4 % du chiffrage, soit ~0,043 md€ sur une décote de 3,1 md€. Les largeurs de bande mesurées ici valent 0,026 à 0,062 md€ : **le même ordre de grandeur**. L'attribution mesure donc le bruit de tirage autant que les paramètres, et la section qui prédisait exactement cela avait été écrite avant — sans être appliquée à v2.

**Ce que l'attribution vaudrait, et ce qu'elle coûterait.** Le mécanisme est juste et instantané une fois la passe moteur payée : la bande se recalcule mille fois par seconde. Ce qu'il lui faut est une passe **sur la population complète** (199 451 ménages, `sample=None`), où le bruit de tirage est nul par construction. C'est un travail par lots, pas une passe de 40 secondes, et c'est la condition à remplir avant que L3 puisse être ordonné par la mesure.

**Conclusion, dans la grammaire de la phase : L3 n'est pas classé, et son score est « non résolvable au sous-échantillon ».** Refuser de classer est un résultat ; publier le classement de n = 3 000 en aurait été un autre, faux.

## La résolution de l'instrument

**Non mesurée dans ce passage** — relancer avec `--resolution`, qui coûte 12 passes moteur. Le bruit de sous-échantillon n'est pas une source d'erreur du modèle (il vaut zéro quand la frame entière est chiffrée) mais il borne la finesse avec laquelle ce budget peut séparer deux sources mesurées sur un sous-échantillon.

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

