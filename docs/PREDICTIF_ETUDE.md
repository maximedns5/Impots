# L'étude : quelles baisses d'impôt font baisser la dette en 2035, et pour quels θ ?

> Généré par `scripts/write_predictif_etude.py` depuis `etude/*.json` et `reports/exploration_etude_*.json`. Ne pas éditer à la main : `tests/test_predictif_etude.py` tient que cette page est le rendu de ces fichiers.

> Prédictif conditionnel : chaque chiffre dépend des scénarios nommés de dépense, de croissance et de taux, et des coefficients θ qui placeront chaque effet dans sa fourchette publiée. Ce n'est pas une prévision : changer un scénario change la réponse.

> Les dépenses publiques (~57 % du PIB) ne sont PAS microsimulées ici ; seule la tranche des transferts l'est. Ce panneau est un scénario comptable.

## Préenregistrée

Les quatre requêtes, une par instrument, sont sous `etude/`. Elles ont été commitées avant toute passe, avec le pronostic écrit dans D-237. Chaque rapport a joué la requête commitée, à l'identique, sur le même commit : `e0c3d7fe901b320e9b0b3c8ed1e39f8c678223d5`, le 2026-10-21. Les passes ont tourné ici : un conteneur cloud de Claude Code, en tâche de fond.

Un premier tour a tourné sur le commit du préenregistrement, `6dab3a404722c57f53f3f2cc60c9cc98b2dc6f7f`. Ses rapports ne portaient pas ce qui manque à la chaîne : la boucle absente pour le plafond de la réduction générale des cotisations employeurs s'y serait lue comme nulle (D-238). Le second tour le porte, et redonne le premier chiffre pour chiffre : `reports/etude_premier_tour/` le garde, et le rendu refuse de tourner si un seul chiffre diffère.

## Le cadre

- Dépense : Dépenses gelées en volume. C'est la seule règle où la boucle PIB → recettes s'applique (D-218).
- Croissance : Croissance réelle 1 %, prix 2 %. Taux : Taux implicite tenu à son niveau de 2025.
- Salaires : 3 % par an, prix 2 % (3 % ronds, le rythme du PIB nominal du scénario).
- θ = ½ partout. Comportement et boucle chiffrés, les deux persistances de l'effet macro côte à côte (D-230).
- Cible : Δb 2035 ≤ +0,00 pt, la dette de la réforme sous celle de la référence en 2035. Part du PIB : Δb, la dette de la réforme moins celle de la référence ; négatif, la réforme allège la dette.
- Vues : vieillie, la population de 2024 vieillie jusqu'à la première année projetée, la vue de tête (D-216, D-226) ; figée, la population de 2024 telle quelle, le droit de l'année appliqué à ses revenus ; un paquet qui ne tient que là n'est pas un plan (D-155).
- Convention : Δ tenu en part de PIB constante au-delà de la dernière année chiffrée (convention, pas un chiffrage).
- Convention : à θ fixé, la trajectoire est un nombre : sa dispersion est la boîte θ, relue aux coins (« robuste » ou « dépend de θ »).

## Le menu

Les baisses que la population chiffre et que la chaîne porte, de un à une dizaine de milliards. L'IS n'y entre pas : la chaîne chiffre les réformes de la population, et le taux de l'IS n'en est pas une (D-228). La couche entreprises dit ses indices à part.

| Instrument | Bouton | Grille | Coût 2026, vieillie |
|---|---|---|---|
| La CSG déductible sur les revenus d'activité | `csg_activite_deductible` | 5,8 %, 6,1 %, 6,4 %, 6,7 % | de 0,88 Md€ à 8,81 Md€ |
| Le plafond de la réduction générale des cotisations employeurs | `allegement_general_plafond` | 3,5 SMIC, 4,5 SMIC, 5,5 SMIC, 6,5 SMIC | de 1,78 Md€ à 5,65 Md€ |
| Le taux de la décote de l'IR | `decote_taux` | 10 %, 20 %, 30 %, 40 % | de 0,94 Md€ à 10,28 Md€ |
| Les taux du barème de l'IR, mis à l'échelle | `ir_bareme_echelle` | × 0,93, × 0,95, × 0,97, × 0,99 | de 1,38 Md€ à 9,63 Md€ |

`ir_bareme_echelle` : chaque taux du barème de l'IR en vigueur multiplié par ce facteur, les seuils inchangés. Le barème en vigueur qu'elle met à l'échelle est celui de 2026, ses taux 0 %, 11 %, 30 %, 41 %, 45 %.

## La réponse

| Instrument | Effet macro éteint après trois ans | Effet macro tenu au niveau de la troisième année |
|---|---|---|
| La CSG déductible sur les revenus d'activité | non à θ = ½ : le paquet le plus proche, 6,7 %, laisse Δb = +0,23 pt. Elle ne baisse à aucun coin de la boîte θ. | non à θ = ½ : le paquet le plus proche, 6,7 %, laisse Δb = +0,08 pt. Elle baisse à 16 coins sur 32, à chaque paquet : ceux où multiplicateur_macro = 1. |
| Le plafond de la réduction générale des cotisations employeurs | non à θ = ½ : le paquet le plus proche, 3,5 SMIC, laisse Δb = +0,55 pt. Elle ne baisse à aucun coin de la boîte θ. Attention : la boucle PIB → recettes est absente pour ce paquet, non nulle ; voir ce qui manque à la chaîne. | non à θ = ½ : le paquet le plus proche, 3,5 SMIC, laisse Δb = +0,55 pt. Elle ne baisse à aucun coin de la boîte θ. Attention : la boucle PIB → recettes est absente pour ce paquet, non nulle ; voir ce qui manque à la chaîne. |
| Le taux de la décote de l'IR | non à θ = ½ : le paquet le plus proche, 40 %, laisse Δb = +0,26 pt. Elle ne baisse à aucun coin de la boîte θ. | non à θ = ½ : le paquet le plus proche, 40 %, laisse Δb = +0,11 pt. Elle baisse à 4 coins sur 8, à chaque paquet : ceux où multiplicateur_macro = 1. |
| Les taux du barème de l'IR, mis à l'échelle | non à θ = ½ : le paquet le plus proche, × 0,99, laisse Δb = +0,30 pt. Elle ne baisse à aucun coin de la boîte θ. | non à θ = ½ : le paquet le plus proche, × 0,99, laisse Δb = +0,08 pt. Elle baisse à 4 coins sur 8, à chaque paquet : ceux où multiplicateur_macro = 1. |

### La CSG déductible sur les revenus d'activité

Une baisse de la CSG déductible sur les revenus d'activité, de 6,8 % à 6,7, 6,4, 6,1 ou 5,8 %, fait-elle baisser la dette en 2035, et pour quels θ ?

**Effet macro éteint après trois ans.** non à θ = ½ : le paquet le plus proche, 6,7 %, laisse Δb = +0,23 pt. Elle ne baisse à aucun coin de la boîte θ.

| Paquet | Coût 2026, vieillie | Coût 2026, figée | Δb 2035 à θ = ½, vieillie | Δb 2035, figée | Boîte θ, vieillie | Coins où la dette baisse |
|---|---|---|---|---|---|---|
| 5,8 % | 8,81 Md€ | 8,34 Md€ | +2,26 pt | +2,14 pt | [+1,84 pt ; +2,66 pt] | aucun des 32 |
| 6,1 % | 6,16 Md€ | 5,84 Md€ | +1,58 pt | +1,50 pt | [+1,29 pt ; +1,86 pt] | aucun des 32 |
| 6,4 % | 3,53 Md€ | 3,34 Md€ | +0,90 pt | +0,85 pt | [+0,74 pt ; +1,07 pt] | aucun des 32 |
| 6,7 % | 0,88 Md€ | 0,83 Md€ | +0,23 pt | +0,21 pt | [+0,18 pt ; +0,27 pt] | aucun des 32 |

**Effet macro tenu au niveau de la troisième année.** non à θ = ½ : le paquet le plus proche, 6,7 %, laisse Δb = +0,08 pt. Elle baisse à 16 coins sur 32, à chaque paquet : ceux où multiplicateur_macro = 1.

| Paquet | Coût 2026, vieillie | Coût 2026, figée | Δb 2035 à θ = ½, vieillie | Δb 2035, figée | Boîte θ, vieillie | Coins où la dette baisse |
|---|---|---|---|---|---|---|
| 5,8 % | 8,81 Md€ | 8,34 Md€ | +0,83 pt | +0,77 pt | [−0,62 pt ; +2,28 pt] | 16 sur 32 (multiplicateur_macro = 1) |
| 6,1 % | 6,16 Md€ | 5,84 Md€ | +0,58 pt | +0,54 pt | [−0,43 pt ; +1,59 pt] | 16 sur 32 (multiplicateur_macro = 1) |
| 6,4 % | 3,53 Md€ | 3,34 Md€ | +0,33 pt | +0,31 pt | [−0,25 pt ; +0,91 pt] | 16 sur 32 (multiplicateur_macro = 1) |
| 6,7 % | 0,88 Md€ | 0,83 Md€ | +0,08 pt | +0,08 pt | [−0,06 pt ; +0,23 pt] | 16 sur 32 (multiplicateur_macro = 1) |

**Ce qui manque à la chaîne**, pour le paquet le plus proche : absent, et non nul.

- rétroaction, instruments non couverts : af, aide_logement, crds_logement, crds_mini, crds_pfam, ppa, rsa : Mésange ne publie pas de variante de transfert. La variante « dépense publique générique » en contient, mais c'est un COMPOSITE dont la page 106 donne la composition exacte : 8 % investissement public, 25 % rémunérations publiques, 9 % prestations en nature, 12 % consommations intermédiaires et 46 % prestations sociales en espèces — et le document dit que ces composantes se transmettent à des vitesses différentes. L'emprunter surestimerait : les méta-analyses IMK donnent 0,39 (WP117) et 0,54 (WP139) pour les transferts contre 1,01 et 0,90 pour la dépense, soit un facteur deux à trois. Un canal qui meurt vaut mieux qu'un canal qui se trompe d'un facteur deux.

**Les indices de §7, pour le paquet le plus proche de la cible**, vue vieillie, tirés de la passe qui l'a chiffré.

Paquet le plus proche de la cible : **6,7 %**.

| Pour | Indice | Unité | Valeur à θ [boîte θ] |
|---|---|---|---|
| Les gens | Revenu disponible, par décile de niveau de vie | EUR par ménage et par an | D1 : +0,69 ; D2 : +4,32 ; D3 : +11,32 ; D4 : +15,27 ; D5 : +20,12 ; D6 : +27,79 ; D7 : +32,42 ; D8 : +38,43 ; D9 : +46,30 ; D10 : +86,98 |
| Les gens | Revenu disponible brut réel des ménages (pouvoir d'achat) | % d'écart au compte central | à 1 an : +0,05 ; à 2 ans : +0,06 ; à 3 ans : +0,06 |
| Les gens | Consommation des ménages, en volume | % d'écart au compte central | à 1 an : +0,02 [−0,01 ; +0,06] ; à 2 ans : +0,05 [+0,01 ; +0,09] ; à 3 ans : +0,06 [+0,02 ; +0,10] |
| Les gens | Emploi au voisinage du SMIC | emplois | absent : le canal ne s'ouvre pas pour cette réforme |
| Les gens | Emploi salarié marchand | milliers d'ETP | à 1 an : +0,68 [−0,41 ; +1,77] ; à 2 ans : +3,10 [+0,67 ; +5,53] ; à 3 ans : +4,89 [+1,33 ; +8,45] |
| Les gens | Revenus d'activité bruts que déplacent les heures | EUR par an | 2026 : +94 172 825 [+10 988 659 ; +183 253 791] |
| Les entreprises | Investissement des entreprises non financières, en volume | % d'écart au compte central | à 1 an : +0,02 [−0,01 ; +0,06] ; à 2 ans : +0,06 [+0,01 ; +0,11] ; à 3 ans : +0,06 [+0,02 ; +0,10] |
| Les entreprises | Charge fiscale de production | % de la valeur ajoutée | absent : Couche entreprises (`/entreprises/simulate`) : la trajectoire chiffre les réformes de la population, et cet indice ne s'y calcule pas. |
| Les startups | Créations de sociétés | points de taux de création | absent : Couche entreprises (`/entreprises/simulate`) : la trajectoire chiffre les réformes de la population, et cet indice ne s'y calcule pas. |
| Les entreprises | Dépense de R&D | EUR de R&D | absent : Couche entreprises (`/entreprises/simulate`) : la trajectoire chiffre les réformes de la population, et cet indice ne s'y calcule pas. |
| L'État | Solde primaire, écart de la réforme, effet macro éteint après trois ans | pts de PIB | 2035 : −0,027 pt |
| L'État | Dette, écart de la réforme, effet macro éteint après trois ans | pts de PIB | 2035 : +0,225 pt |
| L'État | Charge d'intérêts de la dette supplémentaire, effet macro éteint après trois ans | pts du PIB de référence | 2035 : +0,004 pt |
| L'État | Solde primaire, écart de la réforme, effet macro tenu au niveau de la troisième année | pts de PIB | 2035 : −0,010 pt |
| L'État | Dette, écart de la réforme, effet macro tenu au niveau de la troisième année | pts de PIB | 2035 : +0,082 pt |
| L'État | Charge d'intérêts de la dette supplémentaire, effet macro tenu au niveau de la troisième année | pts du PIB de référence | 2035 : +0,002 pt |

### Le plafond de la réduction générale des cotisations employeurs

Un relèvement du plafond de la réduction générale, de 3 SMIC à 3,5, 4,5, 5,5 ou 6,5 SMIC, fait-elle baisser la dette en 2035, et pour quels θ ?

**Effet macro éteint après trois ans.** non à θ = ½ : le paquet le plus proche, 3,5 SMIC, laisse Δb = +0,55 pt. Elle ne baisse à aucun coin de la boîte θ. Attention : la boucle PIB → recettes est absente pour ce paquet, non nulle ; voir ce qui manque à la chaîne.

| Paquet | Coût 2026, vieillie | Coût 2026, figée | Δb 2035 à θ = ½, vieillie | Δb 2035, figée | Boîte θ, vieillie | Coins où la dette baisse |
|---|---|---|---|---|---|---|
| 3,5 SMIC | 1,78 Md€ | 1,46 Md€ | +0,55 pt | +0,45 pt | [+0,55 pt ; +0,55 pt] | aucun des 16 |
| 4,5 SMIC | 3,38 Md€ | 2,70 Md€ | +1,05 pt | +0,83 pt | [+1,05 pt ; +1,05 pt] | aucun des 16 |
| 5,5 SMIC | 4,69 Md€ | 4,06 Md€ | +1,45 pt | +1,25 pt | [+1,45 pt ; +1,45 pt] | aucun des 16 |
| 6,5 SMIC | 5,65 Md€ | 4,82 Md€ | +1,74 pt | +1,49 pt | [+1,74 pt ; +1,74 pt] | aucun des 16 |

**Effet macro tenu au niveau de la troisième année.** non à θ = ½ : le paquet le plus proche, 3,5 SMIC, laisse Δb = +0,55 pt. Elle ne baisse à aucun coin de la boîte θ. Attention : la boucle PIB → recettes est absente pour ce paquet, non nulle ; voir ce qui manque à la chaîne.

| Paquet | Coût 2026, vieillie | Coût 2026, figée | Δb 2035 à θ = ½, vieillie | Δb 2035, figée | Boîte θ, vieillie | Coins où la dette baisse |
|---|---|---|---|---|---|---|
| 3,5 SMIC | 1,78 Md€ | 1,46 Md€ | +0,55 pt | +0,45 pt | [+0,55 pt ; +0,55 pt] | aucun des 16 |
| 4,5 SMIC | 3,38 Md€ | 2,70 Md€ | +1,05 pt | +0,83 pt | [+1,05 pt ; +1,05 pt] | aucun des 16 |
| 5,5 SMIC | 4,69 Md€ | 4,06 Md€ | +1,45 pt | +1,25 pt | [+1,45 pt ; +1,45 pt] | aucun des 16 |
| 6,5 SMIC | 5,65 Md€ | 4,82 Md€ | +1,74 pt | +1,49 pt | [+1,74 pt ; +1,74 pt] | aucun des 16 |

**Ce qui manque à la chaîne**, pour le paquet le plus proche : absent, et non nul.

- rétroaction : aucun instrument de cette réforme n'a de ligne de solde dans Mésange : il n'y a pas de rétroaction à lire, et une rétroaction nulle se lirait comme un constat. Non couverts : {'cotisations_employeurs_ciblees': "pas de ligne de solde dans Mésange (variante ciblée, encadré 14) : ni rétroaction ni effet sur le PIB, plutôt que la moitié d'une variante"}

**Les indices de §7, pour le paquet le plus proche de la cible**, vue vieillie, tirés de la passe qui l'a chiffré.

Paquet le plus proche de la cible : **3,5 SMIC**.

| Pour | Indice | Unité | Valeur à θ [boîte θ] |
|---|---|---|---|
| Les gens | Revenu disponible, par décile de niveau de vie | EUR par ménage et par an | D1 : +0,00 ; D2 : +0,00 ; D3 : +0,00 ; D4 : +0,00 ; D5 : +0,00 ; D6 : +0,00 ; D7 : +0,00 ; D8 : +0,00 ; D9 : +0,00 ; D10 : +0,00 |
| Les gens | Revenu disponible brut réel des ménages (pouvoir d'achat) | % d'écart au compte central | absent : aucun instrument de la réforme n'a cette ligne dans Mésange |
| Les gens | Consommation des ménages, en volume | % d'écart au compte central | absent : aucun instrument de la réforme n'a cette ligne dans Mésange |
| Les gens | Emploi au voisinage du SMIC | emplois | 2026 : +227 [+170 ; +270] |
| Les gens | Emploi salarié marchand | milliers d'ETP | à 1 an : +5,83 [−12,49 ; +24,16] ; à 2 ans : +16,28 [−2,25 ; +34,81] ; à 3 ans : +23,27 [+4,07 ; +42,46] |
| Les gens | Revenus d'activité bruts que déplacent les heures | EUR par an | absent : le canal ne s'ouvre pas pour cette réforme |
| Les entreprises | Investissement des entreprises non financières, en volume | % d'écart au compte central | absent : aucun instrument de la réforme n'a cette ligne dans Mésange |
| Les entreprises | Charge fiscale de production | % de la valeur ajoutée | absent : Couche entreprises (`/entreprises/simulate`) : la trajectoire chiffre les réformes de la population, et cet indice ne s'y calcule pas. |
| Les startups | Créations de sociétés | points de taux de création | absent : Couche entreprises (`/entreprises/simulate`) : la trajectoire chiffre les réformes de la population, et cet indice ne s'y calcule pas. |
| Les entreprises | Dépense de R&D | EUR de R&D | absent : Couche entreprises (`/entreprises/simulate`) : la trajectoire chiffre les réformes de la population, et cet indice ne s'y calcule pas. |
| L'État | Solde primaire, écart de la réforme, effet macro éteint après trois ans | pts de PIB | 2035 : −0,058 pt |
| L'État | Dette, écart de la réforme, effet macro éteint après trois ans | pts de PIB | 2035 : +0,549 pt |
| L'État | Charge d'intérêts de la dette supplémentaire, effet macro éteint après trois ans | pts du PIB de référence | 2035 : +0,009 pt |
| L'État | Solde primaire, écart de la réforme, effet macro tenu au niveau de la troisième année | pts de PIB | 2035 : −0,058 pt |
| L'État | Dette, écart de la réforme, effet macro tenu au niveau de la troisième année | pts de PIB | 2035 : +0,549 pt |
| L'État | Charge d'intérêts de la dette supplémentaire, effet macro tenu au niveau de la troisième année | pts du PIB de référence | 2035 : +0,009 pt |

### Le taux de la décote de l'IR

Une décote plus généreuse, son taux ramené de 45,25 % à 40, 30, 20 ou 10 %, fait-elle baisser la dette en 2035, et pour quels θ ?

**Effet macro éteint après trois ans.** non à θ = ½ : le paquet le plus proche, 40 %, laisse Δb = +0,26 pt. Elle ne baisse à aucun coin de la boîte θ.

| Paquet | Coût 2026, vieillie | Coût 2026, figée | Δb 2035 à θ = ½, vieillie | Δb 2035, figée | Boîte θ, vieillie | Coins où la dette baisse |
|---|---|---|---|---|---|---|
| 10 % | 10,28 Md€ | 9,85 Md€ | +2,82 pt | +2,70 pt | [+2,45 pt ; +3,19 pt] | aucun des 8 |
| 20 % | 5,95 Md€ | 5,79 Md€ | +1,73 pt | +1,68 pt | [+1,47 pt ; +1,99 pt] | aucun des 8 |
| 30 % | 3,14 Md€ | 3,08 Md€ | +0,86 pt | +0,84 pt | [+0,74 pt ; +0,97 pt] | aucun des 8 |
| 40 % | 0,94 Md€ | 0,93 Md€ | +0,26 pt | +0,26 pt | [+0,23 pt ; +0,30 pt] | aucun des 8 |

**Effet macro tenu au niveau de la troisième année.** non à θ = ½ : le paquet le plus proche, 40 %, laisse Δb = +0,11 pt. Elle baisse à 4 coins sur 8, à chaque paquet : ceux où multiplicateur_macro = 1.

| Paquet | Coût 2026, vieillie | Coût 2026, figée | Δb 2035 à θ = ½, vieillie | Δb 2035, figée | Boîte θ, vieillie | Coins où la dette baisse |
|---|---|---|---|---|---|---|
| 10 % | 10,28 Md€ | 9,85 Md€ | +1,20 pt | +1,15 pt | [−0,37 pt ; +2,78 pt] | 4 sur 8 (multiplicateur_macro = 1) |
| 20 % | 5,95 Md€ | 5,79 Md€ | +0,79 pt | +0,77 pt | [−0,17 pt ; +1,75 pt] | 4 sur 8 (multiplicateur_macro = 1) |
| 30 % | 3,14 Md€ | 3,08 Md€ | +0,36 pt | +0,36 pt | [−0,12 pt ; +0,84 pt] | 4 sur 8 (multiplicateur_macro = 1) |
| 40 % | 0,94 Md€ | 0,93 Md€ | +0,11 pt | +0,11 pt | [−0,03 pt ; +0,26 pt] | 4 sur 8 (multiplicateur_macro = 1) |

**Les indices de §7, pour le paquet le plus proche de la cible**, vue vieillie, tirés de la passe qui l'a chiffré.

Paquet le plus proche de la cible : **40 %**.

| Pour | Indice | Unité | Valeur à θ [boîte θ] |
|---|---|---|---|
| Les gens | Revenu disponible, par décile de niveau de vie | EUR par ménage et par an | D1 : +0,04 ; D2 : +0,37 ; D3 : +1,28 ; D4 : +14,85 ; D5 : +48,13 ; D6 : +80,48 ; D7 : +86,67 ; D8 : +61,11 ; D9 : +8,00 ; D10 : +2,91 |
| Les gens | Revenu disponible brut réel des ménages (pouvoir d'achat) | % d'écart au compte central | à 1 an : +0,05 ; à 2 ans : +0,06 ; à 3 ans : +0,06 |
| Les gens | Consommation des ménages, en volume | % d'écart au compte central | à 1 an : +0,02 [−0,02 ; +0,06] ; à 2 ans : +0,05 [+0,01 ; +0,09] ; à 3 ans : +0,06 [+0,01 ; +0,10] |
| Les gens | Emploi au voisinage du SMIC | emplois | absent : le canal ne s'ouvre pas pour cette réforme |
| Les gens | Emploi salarié marchand | milliers d'ETP | à 1 an : +0,73 [−0,45 ; +1,92] ; à 2 ans : +3,33 [+0,68 ; +5,98] ; à 3 ans : +5,32 [+1,33 ; +9,31] |
| Les gens | Revenus d'activité bruts que déplacent les heures | EUR par an | absent : le canal ne s'ouvre pas pour cette réforme |
| Les entreprises | Investissement des entreprises non financières, en volume | % d'écart au compte central | à 1 an : +0,02 [−0,02 ; +0,06] ; à 2 ans : +0,06 [+0,01 ; +0,11] ; à 3 ans : +0,06 [+0,02 ; +0,11] |
| Les entreprises | Charge fiscale de production | % de la valeur ajoutée | absent : Couche entreprises (`/entreprises/simulate`) : la trajectoire chiffre les réformes de la population, et cet indice ne s'y calcule pas. |
| Les startups | Créations de sociétés | points de taux de création | absent : Couche entreprises (`/entreprises/simulate`) : la trajectoire chiffre les réformes de la population, et cet indice ne s'y calcule pas. |
| Les entreprises | Dépense de R&D | EUR de R&D | absent : Couche entreprises (`/entreprises/simulate`) : la trajectoire chiffre les réformes de la population, et cet indice ne s'y calcule pas. |
| L'État | Solde primaire, écart de la réforme, effet macro éteint après trois ans | pts de PIB | 2035 : −0,031 pt |
| L'État | Dette, écart de la réforme, effet macro éteint après trois ans | pts de PIB | 2035 : +0,261 pt |
| L'État | Charge d'intérêts de la dette supplémentaire, effet macro éteint après trois ans | pts du PIB de référence | 2035 : +0,004 pt |
| L'État | Solde primaire, écart de la réforme, effet macro tenu au niveau de la troisième année | pts de PIB | 2035 : −0,013 pt |
| L'État | Dette, écart de la réforme, effet macro tenu au niveau de la troisième année | pts de PIB | 2035 : +0,113 pt |
| L'État | Charge d'intérêts de la dette supplémentaire, effet macro tenu au niveau de la troisième année | pts du PIB de référence | 2035 : +0,002 pt |

### Les taux du barème de l'IR, mis à l'échelle

Une baisse de chaque taux du barème de l'IR en vigueur de 1, 3, 5 ou 7 %, ses seuils inchangés, fait-elle baisser la dette en 2035, et pour quels θ ?

**Effet macro éteint après trois ans.** non à θ = ½ : le paquet le plus proche, × 0,99, laisse Δb = +0,30 pt. Elle ne baisse à aucun coin de la boîte θ.

| Paquet | Coût 2026, vieillie | Coût 2026, figée | Δb 2035 à θ = ½, vieillie | Δb 2035, figée | Boîte θ, vieillie | Coins où la dette baisse |
|---|---|---|---|---|---|---|
| × 0,93 | 9,63 Md€ | 8,57 Md€ | +2,16 pt | +1,89 pt | [+1,56 pt ; +2,72 pt] | aucun des 8 |
| × 0,95 | 6,88 Md€ | 6,12 Md€ | +1,53 pt | +1,35 pt | [+1,11 pt ; +1,94 pt] | aucun des 8 |
| × 0,97 | 4,13 Md€ | 3,67 Md€ | +0,91 pt | +0,80 pt | [+0,64 pt ; +1,16 pt] | aucun des 8 |
| × 0,99 | 1,38 Md€ | 1,23 Md€ | +0,30 pt | +0,26 pt | [+0,21 pt ; +0,38 pt] | aucun des 8 |

**Effet macro tenu au niveau de la troisième année.** non à θ = ½ : le paquet le plus proche, × 0,99, laisse Δb = +0,08 pt. Elle baisse à 4 coins sur 8, à chaque paquet : ceux où multiplicateur_macro = 1.

| Paquet | Coût 2026, vieillie | Coût 2026, figée | Δb 2035 à θ = ½, vieillie | Δb 2035, figée | Boîte θ, vieillie | Coins où la dette baisse |
|---|---|---|---|---|---|---|
| × 0,93 | 9,63 Md€ | 8,57 Md€ | +0,64 pt | +0,55 pt | [−1,08 pt ; +2,34 pt] | 4 sur 8 (multiplicateur_macro = 1) |
| × 0,95 | 6,88 Md€ | 6,12 Md€ | +0,45 pt | +0,38 pt | [−0,78 pt ; +1,67 pt] | 4 sur 8 (multiplicateur_macro = 1) |
| × 0,97 | 4,13 Md€ | 3,67 Md€ | +0,26 pt | +0,22 pt | [−0,49 pt ; +0,99 pt] | 4 sur 8 (multiplicateur_macro = 1) |
| × 0,99 | 1,38 Md€ | 1,23 Md€ | +0,08 pt | +0,07 pt | [−0,17 pt ; +0,33 pt] | 4 sur 8 (multiplicateur_macro = 1) |

**Les indices de §7, pour le paquet le plus proche de la cible**, vue vieillie, tirés de la passe qui l'a chiffré.

Paquet le plus proche de la cible : **× 0,99**.

| Pour | Indice | Unité | Valeur à θ [boîte θ] |
|---|---|---|---|
| Les gens | Revenu disponible, par décile de niveau de vie | EUR par ménage et par an | D1 : +0,01 ; D2 : +0,10 ; D3 : +0,37 ; D4 : +4,24 ; D5 : +13,82 ; D6 : +23,70 ; D7 : +33,07 ; D8 : +48,28 ; D9 : +76,94 ; D10 : +243 |
| Les gens | Revenu disponible brut réel des ménages (pouvoir d'achat) | % d'écart au compte central | à 1 an : +0,08 ; à 2 ans : +0,08 ; à 3 ans : +0,09 |
| Les gens | Consommation des ménages, en volume | % d'écart au compte central | à 1 an : +0,04 [−0,02 ; +0,09] ; à 2 ans : +0,07 [+0,02 ; +0,13] ; à 3 ans : +0,08 [+0,02 ; +0,15] |
| Les gens | Emploi au voisinage du SMIC | emplois | absent : le canal ne s'ouvre pas pour cette réforme |
| Les gens | Emploi salarié marchand | milliers d'ETP | à 1 an : +1,07 [−0,65 ; +2,80] ; à 2 ans : +4,87 [+1,00 ; +8,74] ; à 3 ans : +7,77 [+1,94 ; +13,60] |
| Les gens | Revenus d'activité bruts que déplacent les heures | EUR par an | absent : le canal ne s'ouvre pas pour cette réforme |
| Les entreprises | Investissement des entreprises non financières, en volume | % d'écart au compte central | à 1 an : +0,04 [−0,02 ; +0,09] ; à 2 ans : +0,09 [+0,02 ; +0,16] ; à 3 ans : +0,09 [+0,02 ; +0,15] |
| Les entreprises | Charge fiscale de production | % de la valeur ajoutée | absent : Couche entreprises (`/entreprises/simulate`) : la trajectoire chiffre les réformes de la population, et cet indice ne s'y calcule pas. |
| Les startups | Créations de sociétés | points de taux de création | absent : Couche entreprises (`/entreprises/simulate`) : la trajectoire chiffre les réformes de la population, et cet indice ne s'y calcule pas. |
| Les entreprises | Dépense de R&D | EUR de R&D | absent : Couche entreprises (`/entreprises/simulate`) : la trajectoire chiffre les réformes de la population, et cet indice ne s'y calcule pas. |
| L'État | Solde primaire, écart de la réforme, effet macro éteint après trois ans | pts de PIB | 2035 : −0,037 pt |
| L'État | Dette, écart de la réforme, effet macro éteint après trois ans | pts de PIB | 2035 : +0,299 pt |
| L'État | Charge d'intérêts de la dette supplémentaire, effet macro éteint après trois ans | pts du PIB de référence | 2035 : +0,005 pt |
| L'État | Solde primaire, écart de la réforme, effet macro tenu au niveau de la troisième année | pts de PIB | 2035 : −0,011 pt |
| L'État | Dette, écart de la réforme, effet macro tenu au niveau de la troisième année | pts de PIB | 2035 : +0,083 pt |
| L'État | Charge d'intérêts de la dette supplémentaire, effet macro tenu au niveau de la troisième année | pts du PIB de référence | 2035 : +0,002 pt |

## Complément, hors préenregistrement

Joué après le résultat de l'étude, et hors de son préenregistrement. Chaque complément rejoue à l'identique la requête préenregistrée de son instrument, nom, titre et question exceptés, et ses coûts sont ceux de l'étude, paquet pour paquet : seul le classement du choc macro a changé (D-239).

### Relèvement du plafond de la réduction générale, sous la variante uniforme — complément hors préenregistrement

Le plafond de la réduction générale reclassé sous la variante uniforme de Mésange, qui a sa ligne de solde (D-239) : un relèvement de 3 SMIC à 3,5, 4,5, 5,5 ou 6,5 SMIC fait-il baisser la dette en 2035, et pour quels θ ? Joué après le résultat de l'étude, hors préenregistrement.

Commit `cacd43af7a5a506d476cfcbc454a58439d1e614b`, le 2026-10-21, ici : un conteneur cloud de Claude Code, en tâche de fond.

**Effet macro éteint après trois ans.** non à θ = ½ : le paquet le plus proche, 3,5 SMIC, laisse Δb = +0,47 pt. Elle ne baisse à aucun coin de la boîte θ. Dans l'étude, le même paquet laissait Δb = +0,55 pt.

| Paquet | Coût 2026, vieillie | Coût 2026, figée | Δb 2035 à θ = ½, vieillie | Δb 2035, figée | Boîte θ, vieillie | Coins où la dette baisse |
|---|---|---|---|---|---|---|
| 3,5 SMIC | 1,78 Md€ | 1,46 Md€ | +0,47 pt | +0,38 pt | [+0,35 pt ; +0,58 pt] | aucun des 16 |
| 4,5 SMIC | 3,38 Md€ | 2,70 Md€ | +0,89 pt | +0,71 pt | [+0,66 pt ; +1,11 pt] | aucun des 16 |
| 5,5 SMIC | 4,69 Md€ | 4,06 Md€ | +1,23 pt | +1,06 pt | [+0,91 pt ; +1,54 pt] | aucun des 16 |
| 6,5 SMIC | 5,65 Md€ | 4,82 Md€ | +1,48 pt | +1,26 pt | [+1,10 pt ; +1,85 pt] | aucun des 16 |

**Effet macro tenu au niveau de la troisième année.** non à θ = ½ : le paquet le plus proche, 3,5 SMIC, laisse Δb = +0,13 pt. Elle baisse à 8 coins sur 16, à chaque paquet : ceux où multiplicateur_macro = 1. Dans l'étude, le même paquet laissait Δb = +0,55 pt.

| Paquet | Coût 2026, vieillie | Coût 2026, figée | Δb 2035 à θ = ½, vieillie | Δb 2035, figée | Boîte θ, vieillie | Coins où la dette baisse |
|---|---|---|---|---|---|---|
| 3,5 SMIC | 1,78 Md€ | 1,46 Md€ | +0,13 pt | +0,11 pt | [−0,27 pt ; +0,54 pt] | 8 sur 16 (multiplicateur_macro = 1) |
| 4,5 SMIC | 3,38 Md€ | 2,70 Md€ | +0,26 pt | +0,20 pt | [−0,52 pt ; +1,03 pt] | 8 sur 16 (multiplicateur_macro = 1) |
| 5,5 SMIC | 4,69 Md€ | 4,06 Md€ | +0,35 pt | +0,31 pt | [−0,72 pt ; +1,42 pt] | 8 sur 16 (multiplicateur_macro = 1) |
| 6,5 SMIC | 5,65 Md€ | 4,82 Md€ | +0,43 pt | +0,36 pt | [−0,86 pt ; +1,72 pt] | 8 sur 16 (multiplicateur_macro = 1) |

## La courbe de 2026, préenregistrée à part

Depuis la refonte de 2026, la réduction générale est une courbe, et l'étude n'en chiffrait que le plafond, qui n'est plus que son seuil de sortie (D-239). Les boutons de la courbe (D-240) sont rejoués ici, après l'étude, et préenregistrés à part : les requêtes sous `etude/courbe/` ont été commitées avant toute passe, avec le pronostic écrit dans D-241. Chacune tient le cadre de l'étude champ pour champ ; seuls son nom, son titre, sa question et sa grille diffèrent. Chaque rapport a joué sa requête, à l'identique, sur le même commit : `881f41f5509410d6770c28975e706250619c6842`, le 2026-10-25. Les passes ont tourné ici : un conteneur cloud de Claude Code, en tâche de fond.

Un premier tour a tourné sur le commit du préenregistrement, `893e4de1f8908f6b2d15af6192250494e386a065`. Son emploi au voisinage du SMIC (C2) ne lisait que 15 % des salariés (D-246). Le second tour le corrige. C2 n'entre ni dans les recettes ni dans la dette, et le second tour redonne le premier chiffre pour chiffre sur les coûts, les Δb et les coins de la boîte θ : `reports/courbe_premier_tour/` le garde, et le rendu refuse de tourner si un seul chiffre diffère.

| Instrument | Bouton | Grille | Coût 2026, vieillie |
|---|---|---|---|
| Le plancher t_min de la réduction générale de 2026 | `allegement_general_t_min` | 2,1 %, 2,4 %, 2,7 %, 3 % | de 0,76 Md€ à 7,62 Md€ |
| Le t_delta de la réduction générale de 2026 | `allegement_general_t_delta_moins_de_50` | 38,31 %, 39,31 %, 40,31 %, 41,31 % | de 1,00 Md€ à 7,01 Md€ |

La population ne porte pas d'effectif d'entreprise : chaque salarié y est rangé dans une entreprise de moins de 50, dont le `t_delta` est donc celui de tous. Chaque paquet chiffre ainsi une hausse des deux `t_delta` du même nombre de points (D-241).

### La réponse de la courbe

| Instrument | Effet macro éteint après trois ans | Effet macro tenu au niveau de la troisième année |
|---|---|---|
| Le plancher t_min de la réduction générale de 2026 | non à θ = ½ : le paquet le plus proche, 2,1 %, laisse Δb = +0,24 pt. Elle ne baisse à aucun coin de la boîte θ. Attention : la boucle PIB → recettes est absente pour ce paquet, non nulle ; voir ce qui manque à la chaîne. | non à θ = ½ : le paquet le plus proche, 2,1 %, laisse Δb = +0,24 pt. Elle ne baisse à aucun coin de la boîte θ. Attention : la boucle PIB → recettes est absente pour ce paquet, non nulle ; voir ce qui manque à la chaîne. |
| Le t_delta de la réduction générale de 2026 | non à θ = ½ : le paquet le plus proche, 38,31 %, laisse Δb = +0,31 pt. Elle ne baisse à aucun coin de la boîte θ. Attention : la boucle PIB → recettes est absente pour ce paquet, non nulle ; voir ce qui manque à la chaîne. | non à θ = ½ : le paquet le plus proche, 38,31 %, laisse Δb = +0,31 pt. Elle ne baisse à aucun coin de la boîte θ. Attention : la boucle PIB → recettes est absente pour ce paquet, non nulle ; voir ce qui manque à la chaîne. |

### Le plancher t_min de la réduction générale de 2026

Un relèvement du plancher t_min de la courbe de 2026, de 2 % à 2,1, 2,4, 2,7 ou 3 %, fait-il baisser la dette en 2035, et pour quels θ ?

**Effet macro éteint après trois ans.** non à θ = ½ : le paquet le plus proche, 2,1 %, laisse Δb = +0,24 pt. Elle ne baisse à aucun coin de la boîte θ. Attention : la boucle PIB → recettes est absente pour ce paquet, non nulle ; voir ce qui manque à la chaîne.

| Paquet | Coût 2026, vieillie | Coût 2026, figée | Δb 2035 à θ = ½, vieillie | Δb 2035, figée | Boîte θ, vieillie | Coins où la dette baisse |
|---|---|---|---|---|---|---|
| 2,1 % | 0,76 Md€ | 0,76 Md€ | +0,24 pt | +0,23 pt | [+0,24 pt ; +0,24 pt] | aucun des 16 |
| 2,4 % | 3,05 Md€ | 3,02 Md€ | +0,94 pt | +0,93 pt | [+0,94 pt ; +0,94 pt] | aucun des 16 |
| 2,7 % | 5,34 Md€ | 5,29 Md€ | +1,65 pt | +1,63 pt | [+1,65 pt ; +1,65 pt] | aucun des 16 |
| 3 % | 7,62 Md€ | 7,56 Md€ | +2,35 pt | +2,34 pt | [+2,35 pt ; +2,35 pt] | aucun des 16 |

**Effet macro tenu au niveau de la troisième année.** non à θ = ½ : le paquet le plus proche, 2,1 %, laisse Δb = +0,24 pt. Elle ne baisse à aucun coin de la boîte θ. Attention : la boucle PIB → recettes est absente pour ce paquet, non nulle ; voir ce qui manque à la chaîne.

| Paquet | Coût 2026, vieillie | Coût 2026, figée | Δb 2035 à θ = ½, vieillie | Δb 2035, figée | Boîte θ, vieillie | Coins où la dette baisse |
|---|---|---|---|---|---|---|
| 2,1 % | 0,76 Md€ | 0,76 Md€ | +0,24 pt | +0,23 pt | [+0,24 pt ; +0,24 pt] | aucun des 16 |
| 2,4 % | 3,05 Md€ | 3,02 Md€ | +0,94 pt | +0,93 pt | [+0,94 pt ; +0,94 pt] | aucun des 16 |
| 2,7 % | 5,34 Md€ | 5,29 Md€ | +1,65 pt | +1,63 pt | [+1,65 pt ; +1,65 pt] | aucun des 16 |
| 3 % | 7,62 Md€ | 7,56 Md€ | +2,35 pt | +2,34 pt | [+2,35 pt ; +2,35 pt] | aucun des 16 |

**Ce qui manque à la chaîne**, pour le paquet le plus proche : absent, et non nul.

- rétroaction : aucun instrument de cette réforme n'a de ligne de solde dans Mésange : il n'y a pas de rétroaction à lire, et une rétroaction nulle se lirait comme un constat. Non couverts : {'cotisations_employeurs_ciblees': "pas de ligne de solde dans Mésange (variante ciblée, encadré 14) : ni rétroaction ni effet sur le PIB, plutôt que la moitié d'une variante"}

**Les indices de §7, pour le paquet le plus proche de la cible**, vue vieillie, tirés de la passe qui l'a chiffré.

Paquet le plus proche de la cible : **2,1 %**.

| Pour | Indice | Unité | Valeur à θ [boîte θ] |
|---|---|---|---|
| Les gens | Revenu disponible, par décile de niveau de vie | EUR par ménage et par an | D1 : +0,00 ; D2 : +0,00 ; D3 : +0,00 ; D4 : +0,00 ; D5 : +0,00 ; D6 : +0,00 ; D7 : +0,00 ; D8 : +0,00 ; D9 : +0,00 ; D10 : +0,00 |
| Les gens | Revenu disponible brut réel des ménages (pouvoir d'achat) | % d'écart au compte central | absent : aucun instrument de la réforme n'a cette ligne dans Mésange |
| Les gens | Consommation des ménages, en volume | % d'écart au compte central | absent : aucun instrument de la réforme n'a cette ligne dans Mésange |
| Les gens | Emploi au voisinage du SMIC | emplois | 2026 : +3 683 [+2 777 ; +4 363] |
| Les gens | Emploi salarié marchand | milliers d'ETP | à 1 an : +2,50 [−5,35 ; +10,35] ; à 2 ans : +6,98 [−0,96 ; +14,91] ; à 3 ans : +9,97 [+1,74 ; +18,19] |
| Les gens | Revenus d'activité bruts que déplacent les heures | EUR par an | absent : le canal ne s'ouvre pas pour cette réforme |
| Les entreprises | Investissement des entreprises non financières, en volume | % d'écart au compte central | absent : aucun instrument de la réforme n'a cette ligne dans Mésange |
| Les entreprises | Charge fiscale de production | % de la valeur ajoutée | absent : Couche entreprises (`/entreprises/simulate`) : la trajectoire chiffre les réformes de la population, et cet indice ne s'y calcule pas. |
| Les startups | Créations de sociétés | points de taux de création | absent : Couche entreprises (`/entreprises/simulate`) : la trajectoire chiffre les réformes de la population, et cet indice ne s'y calcule pas. |
| Les entreprises | Dépense de R&D | EUR de R&D | absent : Couche entreprises (`/entreprises/simulate`) : la trajectoire chiffre les réformes de la population, et cet indice ne s'y calcule pas. |
| L'État | Solde primaire, écart de la réforme, effet macro éteint après trois ans | pts de PIB | 2035 : −0,025 pt |
| L'État | Dette, écart de la réforme, effet macro éteint après trois ans | pts de PIB | 2035 : +0,235 pt |
| L'État | Charge d'intérêts de la dette supplémentaire, effet macro éteint après trois ans | pts du PIB de référence | 2035 : +0,004 pt |
| L'État | Solde primaire, écart de la réforme, effet macro tenu au niveau de la troisième année | pts de PIB | 2035 : −0,025 pt |
| L'État | Dette, écart de la réforme, effet macro tenu au niveau de la troisième année | pts de PIB | 2035 : +0,235 pt |
| L'État | Charge d'intérêts de la dette supplémentaire, effet macro tenu au niveau de la troisième année | pts du PIB de référence | 2035 : +0,004 pt |

### Le t_delta de la réduction générale de 2026

Un relèvement du t_delta de la courbe de 2026, de 37,81 % à 38,31, 39,31, 40,31 ou 41,31 %, fait-il baisser la dette en 2035, et pour quels θ ?

**Effet macro éteint après trois ans.** non à θ = ½ : le paquet le plus proche, 38,31 %, laisse Δb = +0,31 pt. Elle ne baisse à aucun coin de la boîte θ. Attention : la boucle PIB → recettes est absente pour ce paquet, non nulle ; voir ce qui manque à la chaîne.

| Paquet | Coût 2026, vieillie | Coût 2026, figée | Δb 2035 à θ = ½, vieillie | Δb 2035, figée | Boîte θ, vieillie | Coins où la dette baisse |
|---|---|---|---|---|---|---|
| 38,31 % | 1,00 Md€ | 1,10 Md€ | +0,31 pt | +0,34 pt | [+0,31 pt ; +0,31 pt] | aucun des 16 |
| 39,31 % | 3,01 Md€ | 3,29 Md€ | +0,93 pt | +1,01 pt | [+0,93 pt ; +0,93 pt] | aucun des 16 |
| 40,31 % | 5,01 Md€ | 5,48 Md€ | +1,55 pt | +1,69 pt | [+1,55 pt ; +1,55 pt] | aucun des 16 |
| 41,31 % | 7,01 Md€ | 7,67 Md€ | +2,17 pt | +2,37 pt | [+2,17 pt ; +2,17 pt] | aucun des 16 |

**Effet macro tenu au niveau de la troisième année.** non à θ = ½ : le paquet le plus proche, 38,31 %, laisse Δb = +0,31 pt. Elle ne baisse à aucun coin de la boîte θ. Attention : la boucle PIB → recettes est absente pour ce paquet, non nulle ; voir ce qui manque à la chaîne.

| Paquet | Coût 2026, vieillie | Coût 2026, figée | Δb 2035 à θ = ½, vieillie | Δb 2035, figée | Boîte θ, vieillie | Coins où la dette baisse |
|---|---|---|---|---|---|---|
| 38,31 % | 1,00 Md€ | 1,10 Md€ | +0,31 pt | +0,34 pt | [+0,31 pt ; +0,31 pt] | aucun des 16 |
| 39,31 % | 3,01 Md€ | 3,29 Md€ | +0,93 pt | +1,01 pt | [+0,93 pt ; +0,93 pt] | aucun des 16 |
| 40,31 % | 5,01 Md€ | 5,48 Md€ | +1,55 pt | +1,69 pt | [+1,55 pt ; +1,55 pt] | aucun des 16 |
| 41,31 % | 7,01 Md€ | 7,67 Md€ | +2,17 pt | +2,37 pt | [+2,17 pt ; +2,17 pt] | aucun des 16 |

**Ce qui manque à la chaîne**, pour le paquet le plus proche : absent, et non nul.

- rétroaction : aucun instrument de cette réforme n'a de ligne de solde dans Mésange : il n'y a pas de rétroaction à lire, et une rétroaction nulle se lirait comme un constat. Non couverts : {'cotisations_employeurs_ciblees': "pas de ligne de solde dans Mésange (variante ciblée, encadré 14) : ni rétroaction ni effet sur le PIB, plutôt que la moitié d'une variante"}

**Les indices de §7, pour le paquet le plus proche de la cible**, vue vieillie, tirés de la passe qui l'a chiffré.

Paquet le plus proche de la cible : **38,31 %**.

| Pour | Indice | Unité | Valeur à θ [boîte θ] |
|---|---|---|---|
| Les gens | Revenu disponible, par décile de niveau de vie | EUR par ménage et par an | D1 : +0,00 ; D2 : +0,00 ; D3 : +0,00 ; D4 : +0,00 ; D5 : +0,00 ; D6 : +0,00 ; D7 : +0,00 ; D8 : +0,00 ; D9 : +0,00 ; D10 : +0,00 |
| Les gens | Revenu disponible brut réel des ménages (pouvoir d'achat) | % d'écart au compte central | absent : aucun instrument de la réforme n'a cette ligne dans Mésange |
| Les gens | Consommation des ménages, en volume | % d'écart au compte central | absent : aucun instrument de la réforme n'a cette ligne dans Mésange |
| Les gens | Emploi au voisinage du SMIC | emplois | 2026 : +9 960 [+7 353 ; +11 914] |
| Les gens | Emploi salarié marchand | milliers d'ETP | à 1 an : +3,28 [−7,04 ; +13,61] ; à 2 ans : +9,17 [−1,26 ; +19,61] ; à 3 ans : +13,11 [+2,29 ; +23,92] |
| Les gens | Revenus d'activité bruts que déplacent les heures | EUR par an | absent : le canal ne s'ouvre pas pour cette réforme |
| Les entreprises | Investissement des entreprises non financières, en volume | % d'écart au compte central | absent : aucun instrument de la réforme n'a cette ligne dans Mésange |
| Les entreprises | Charge fiscale de production | % de la valeur ajoutée | absent : Couche entreprises (`/entreprises/simulate`) : la trajectoire chiffre les réformes de la population, et cet indice ne s'y calcule pas. |
| Les startups | Créations de sociétés | points de taux de création | absent : Couche entreprises (`/entreprises/simulate`) : la trajectoire chiffre les réformes de la population, et cet indice ne s'y calcule pas. |
| Les entreprises | Dépense de R&D | EUR de R&D | absent : Couche entreprises (`/entreprises/simulate`) : la trajectoire chiffre les réformes de la population, et cet indice ne s'y calcule pas. |
| L'État | Solde primaire, écart de la réforme, effet macro éteint après trois ans | pts de PIB | 2035 : −0,033 pt |
| L'État | Dette, écart de la réforme, effet macro éteint après trois ans | pts de PIB | 2035 : +0,310 pt |
| L'État | Charge d'intérêts de la dette supplémentaire, effet macro éteint après trois ans | pts du PIB de référence | 2035 : +0,005 pt |
| L'État | Solde primaire, écart de la réforme, effet macro tenu au niveau de la troisième année | pts de PIB | 2035 : −0,033 pt |
| L'État | Dette, écart de la réforme, effet macro tenu au niveau de la troisième année | pts de PIB | 2035 : +0,310 pt |
| L'État | Charge d'intérêts de la dette supplémentaire, effet macro tenu au niveau de la troisième année | pts du PIB de référence | 2035 : +0,005 pt |

## Ce que l'étude ne dit pas

- Ce n'est pas une prévision. Chaque chiffre dépend des scénarios nommés et de θ ; un autre scénario donne une autre réponse.
- Une seule valeur de θ, ½, et ses coins. La boîte θ est l'étendue aux coins, ni une somme de tranches ni un intervalle de probabilité.
- La première année est chiffrée, les suivantes reportées en part de PIB : une convention, que `impots predictif` lève année par année (D-236).
- Ni l'IS, ni les dividendes, ni la couche entreprises : la chaîne ne les porte pas. Ce qu'elle ferme, et pourquoi :
  - IS et investissement des entreprises : aucune variante d'IS dans Mésange 2017, et aucune réestimation publiée depuis ; le seul chiffre localisé, un multiplicateur moyen de 0,7 pour la hausse d'IS de 2013 dans un billet de l'OFCE, n'est plus en ligne et n'aurait ni profil par horizon ni ligne de solde (§5, D-219). Le rapport final du comité d'évaluation de la fiscalité du capital (France Stratégie, 2023), lu, ne chiffre aucun effet de la baisse de l'IS à 25 % sur l'investissement : il résume une littérature, sans estimation française (§6.2, D-221).
  - transferts : Mésange n'a pas de variante de transfert. Les deux méta-analyses IMK donnent 0,39 (écart-type 0,47) et 0,54 (écart-type 1,16) : elles divergent sur le centre, d'un facteur 2,5 sur la largeur, mêlent les horizons d'un à douze ans et n'ont ni ligne de solde ni centre français (§5, D-214, D-219).
  - créations d'entreprises : C8 est un indice illustratif de la couche entreprises, en points de taux de création de sociétés, jamais une recette ; la trajectoire chiffre les réformes de la population, et le taux d'IS n'en est pas une (§6.3, D-221).
  - R&D et CIR : C9 est un indice illustratif de la couche entreprises, en euros de R&D, jamais une recette ; la créance du CIR, induite comprise, n'est pas la recette d'une année, et la trajectoire chiffre les réformes de la population (§6.4, D-222).
  - dividendes : la population ne porte aucun revenu du capital (§6.5).
- Elle ne recommande rien. Elle dit ce que la machine répond, sous ces hypothèses, à la question posée.
