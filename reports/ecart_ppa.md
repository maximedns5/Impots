# L'écart de la prime d'activité, mesuré contre la Cnaf (D-315)

Commit `280f091`, 20000 ménages tirés comme le cas, palier complet. La prime est celle de décembre, par famille ; la hausse, ce qu'elle gagne quand le forfait vaut 1 % de plus toute l'année. La Cnaf : PA Conjoncture n° 32 (quatrième trimestre 2024, Caf, porté à tous les régimes par 97,0 %) et Analyses statistiques n° 5 (élasticité de la dépense au forfait en 2024 : 3,8 %).

## La base de 2024 et ses trois termes

* Moteur : 1 158 M€ de prime en décembre 2024, 50,4 M€ de plus pour un point de forfait, soit une élasticité de 4,35 (sur l'année : 4,39). La formule, sans les entrants, donne 47,4 M€ ; 122 milliers de familles entrent.
* Cnaf : 952 M€ par mois au quatrième trimestre, tous régimes ; la base vaut 36,2 M€ par point.
* Le rapport des bases : **1,39**.

Découpé par configuration familiale :

| Terme | Logarithme | Part de l'écart |
|---|---:|---:|
| Les effectifs | 0,078 | +23 % |
| Les montants | 0,119 | +36 % |
| L'élasticité : composition | -0,034 | -10 % |
| L'élasticité : interne aux cellules | 0,169 | +51 % |
| **Le rapport des bases** | **0,332** | **1,39** |

Découpé par âge du responsable du dossier :

| Terme | Logarithme | Part de l'écart |
|---|---:|---:|
| Les effectifs | 0,054 | +16 % |
| Les montants | 0,142 | +43 % |
| L'élasticité : composition | -0,018 | -6 % |
| L'élasticité : interne aux cellules | 0,153 | +46 % |
| **Le rapport des bases** | **0,331** | **1,39** |

## Le tableau des écarts

### Par configuration familiale

| | Foyers Cnaf (k) | Foyers moteur (k) | Écart | Montant Cnaf (€) | Montant moteur (€) | Écart | Élasticité moteur | Effet effectifs (M€) | Effet montants (M€) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Hommes seuls | 1 342 | 1 040 | -22,6 % | 149 | 163 | +9,1 % | 4,82 | -45,1 | 14,1 |
| Femmes seules | 1 341 | 1 464 | +9,1 % | 156 | 186 | +19,0 % | 3,94 | 19,1 | 43,4 |
| Personnes seules avec enfant(s) | 1 000 | 785 | -21,5 % | 271 | 234 | -13,7 % | 4,99 | -58,4 | -29,1 |
| Couples sans enfant | 266 | 507 | +90,6 % | 201 | 270 | +34,5 % | 3,94 | 48,4 | 35,1 |
| Couples avec enfant(s) | 823 | 1 248 | +51,7 % | 265 | 318 | +20,1 % | 4,28 | 112,7 | 66,4 |

Ensemble : 4 772 milliers de foyers à la Cnaf (tous régimes), 5 043 au moteur (+5,7 %). Les effets sont en M€ de dépense du mois ; leur somme fait l'écart de dépense que les deux premiers termes portent.

### Par âge du responsable du dossier

| | Foyers Cnaf (k) | Foyers moteur (k) | Écart | Montant Cnaf (€) | Montant moteur (€) | Écart | Élasticité moteur | Effet effectifs (M€) | Effet montants (M€) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| <25 ans | 790 | 994 | +25,9 % | 164 | 220 | +33,8 % | 3,33 | 33,5 | 55,2 |
| 25-34 ans | 1 387 | 1 092 | -21,3 % | 182 | 230 | +26,5 % | 4,76 | -53,7 | 52,7 |
| 35-44 ans | 1 144 | 1 011 | -11,7 % | 224 | 243 | +8,3 % | 4,65 | -29,9 | 18,9 |
| 45-54 ans | 911 | 1 007 | +10,5 % | 225 | 238 | +5,6 % | 4,40 | 21,5 | 12,7 |
| ≥ 55 ans | 539 | 940 | +74,3 % | 203 | 218 | +7,2 % | 4,52 | 81,3 | 13,7 |

Ensemble : 4 771 milliers de foyers à la Cnaf (tous régimes), 5 043 au moteur (+5,7 %). Les effets sont en M€ de dépense du mois ; leur somme fait l'écart de dépense que les deux premiers termes portent.

### Trois sous-populations

| | Part Cnaf | Part moteur | Montant Cnaf (€) | Montant moteur (€) |
|---|---:|---:|---:|---:|
| dont majoration pour isolement | 4,7 % | 2,5 % | 329 | 179 |
| dont au moins une bonification | 92,2 % | 95,9 % | 203 | 226 |
| dont cumul prime d’activité/RSA | 9,0 % | 2,0 % | 180 | 450 |

### Par revenu d'activité du foyer, en part du Smic brut (moteur seul)

Ni PA Conjoncture n° 32 ni les Analyses statistiques n° 5 ne publient cette distribution : elle n'est pas comparée.

| | Foyers (k) | Part | Montant (€) | Élasticité | Part de la hausse |
|---|---:|---:|---:|---:|---:|
| moins de 0,25 Smic | 25 | 0,5 % | 246 | 0,00 | 0,0 % |
| 0,25 à 0,5 Smic | 452 | 9,0 % | 317 | 1,46 | 4,1 % |
| 0,5 à 0,8 Smic | 1 250 | 24,8 % | 293 | 2,77 | 20,1 % |
| 0,8 à 1 Smic | 1 470 | 29,1 % | 214 | 4,36 | 27,2 % |
| 1 à 1,2 Smic | 901 | 17,9 % | 179 | 6,59 | 21,1 % |
| 1,2 à 1,5 Smic | 560 | 11,1 % | 208 | 6,64 | 15,4 % |
| 1,5 Smic et plus | 386 | 7,7 % | 133 | 11,92 | 12,1 % |

### Par montant de prime en décembre (moteur seul)

La Cnaf ne publie que des montants moyens.

| | Foyers (k) | Part | Montant (€) | Élasticité | Part de la hausse |
|---|---:|---:|---:|---:|---:|
| moins de 50 € | 462 | 9,2 % | 33 | 45,56 | 13,9 % |
| 50 à 100 € | 598 | 11,9 % | 75 | 13,23 | 11,7 % |
| 100 à 200 € | 1 112 | 22,0 % | 152 | 6,36 | 21,3 % |
| 200 à 300 € | 1 703 | 33,8 % | 246 | 3,42 | 28,4 % |
| 300 € et plus | 1 168 | 23,2 % | 438 | 2,44 | 24,8 % |

### Au regard du forfait (moteur seul)

Au-dessus : les ressources et le forfait logement dépassent le forfait, qui ne s'annule plus dans la formule.

| | Foyers (k) | Part | Montant (€) | Élasticité | Part de la hausse |
|---|---:|---:|---:|---:|---:|
| au-dessus du forfait | 4 891 | 97,0 % | 225 | 4,58 | 100,0 % |
| en dessous | 152 | 3,0 % | 381 | 0,03 | 0,0 % |

## Les revenus d'activité

Un point de salaire en plus ôte 289,5 M€ à la prime de l'année : une élasticité de -2,23, contre -2,4 à la Cnaf.

## Le lien au cas et à la fiche, en 2026

* Un point de forfait ajoute 59,9 M€ à la prime de décembre 2026 (élasticité 4,55).
* Le cas, 886,7 M€ pour 2,1 points, vaut 7,05 mois de cette hausse.
* La fiche, 995 M€ en année pleine pour 2,3 points, suppose une base de 36,1 M€ par point et par mois : le moteur en a **1,66** fois plus.

## L'écart de D-300, terme à terme

Le rapport de la base du moteur en 2026 à celle de la fiche, à mois et taux égaux, en six termes dont la somme est exacte. La part est celle du logarithme : un terme négatif réduit l'écart.

| Terme | Logarithme | Part de l'écart |
|---|---:|---:|
| L'année : la base du moteur de 2024 à 2026 | 0,173 | +34 % |
| Les effectifs, en 2024 | 0,078 | +15 % |
| Les montants, en 2024 | 0,119 | +23 % |
| L'élasticité, en 2024 : composition | -0,034 | -7 % |
| L'élasticité, en 2024 : interne aux cellules | 0,169 | +33 % |
| La base de la Cnaf en 2024 contre celle de la fiche | 0,003 | +1 % |
| **Le rapport à la fiche, en 2026** | **0,508** | **1,66** |
