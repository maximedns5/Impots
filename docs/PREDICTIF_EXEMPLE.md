# Exemple prédictif : une baisse de l'IR d'environ 5 Md€, sa dette à 10 ans

<!-- Généré par scripts/write_predictif_exemple.py depuis reports/exemple_predictif.json. Ne pas éditer à la main : tests/test_predictif_exemple.py refuse une page qui dérive. -->

> **Cette page illustre la machinerie ; elle ne recommande rien. La réforme est choisie pour la pédagogie — une baisse de barème touche le plus de canaux ouverts — et non parce qu'elle serait souhaitable.**
>
> Prédictif conditionnel : chaque chiffre dépend des scénarios nommés de dépense, de croissance et de taux, et des coefficients θ qui placeront chaque effet dans sa fourchette publiée. Ce n'est pas une prévision : changer un scénario change la réponse.
>
> Les dépenses publiques (~57 % du PIB) ne sont PAS microsimulées ici ; seule la tranche des transferts l'est. Ce panneau est un scénario comptable.

L'exemple que PHASE9_SPEC §9.4 met au dossier, et D-228 le consigne. Chaque nombre ci-dessous sort de la chaîne de la phase 9 telle qu'elle est : rien n'est saisi, et le script qui écrit cette page la réécrit à l'identique ou le test échoue.

## La réforme et sa première année

Le taux de la première tranche du barème de l'IR passe de 11 % à 10 %, les seuils et les autres taux inchangés, à partir de 2026.

| Tranche à partir de | Taux en vigueur | Taux de la réforme |
|---:|---:|---:|
| 0 € | 0 % | 0 % |
| 11 600 € | 11 % | 10 % |
| 29 579 € | 30 % | 30 % |
| 84 577 € | 41 % | 41 % |
| 181 917 € | 45 % | 45 % |

- **Coût mécanique de 2026** : 4,84 Md€, une passe de l'échantillon rapide, vue « vieillie ». Population synthétique construite à partir de données ouvertes : structure des ménages observée dans l'enquête Emploi, revenus entièrement simulés à partir de distributions publiées. Les écarts aux totaux publiés sont dans reports/reconciliation.md. Les niveaux de RSA, de prime d'activité et de la distribution des niveaux de vie ne sont pas publiables en l'état (D-015) ; les écarts entre droit courant et réforme le sont. Ce résultat porte sur un sous-échantillon déterministe de 20 000 ménages repondérés, pas sur la population complète : attendez-vous à un bruit d'échantillonnage de l'ordre du pour cent sur les agrégats. Vue « vieillie » : l'année 2026 est chiffrée avec sa législation sur la population 2024 vieillie jusqu'à elle, la vue de tête de la commande `impots predictif` (D-216, D-226) ; la vue « figée », que la commande donne à côté, n'est pas chiffrée ici. Population vieillie mécaniquement de 2024 à 2026 — salaires 3,0 % par an, prix 2,0 % par an, hypothèses DÉCLARÉES et non prévues (hypothèse déclarée de cet exemple : salaire nominal au rythme du PIB nominal du scénario de croissance). La structure des ménages, les âges et les poids n'ont PAS bougé : c'est la France de l'année de base avec l'argent de l'année d'arrivée, et cela biaise vers l'immobilité démographique. **Cette population n'est plus calibrée** : les totaux dépensés au registre le sont sur l'année de base, et il n'existe pas de total publié pour une année future. Toute ligne de réconciliation sur cette année refuse un verdict de tolérance plutôt que d'en donner un qui se lirait comme une validation.
- **Comportement à θ = ½** : la réforme coûte 4,803 Md€ une fois les réponses comptées ; boîte θ de la première année 4,798 Md€ à 4,822 Md€, aux coins des lignes revendiquées (`eti_all`, `eti_top_decile`). Grade : in-support.
- **Impulsion macro**, par variante de Mésange, expansionniste positive : impot_sur_le_revenu +4,84 Md€.
- **Calcul** : passe du 2026-10-19, commit `104e29f4117f`. La chaîne porte ce coût en part de PIB constante au-delà de 2026 (la version rapide de `/predictif/simulate`) : les années suivantes sont une convention, pas un chiffrage.

## Les hypothèses nommées

- Croissance : Croissance réelle 1 %, prix 2 %. Taux : Taux implicite tenu à son niveau de 2025.
- Salaires de la population vieillie : 3,02 % par an, hypothèse déclarée de cet exemple : salaire nominal au rythme du PIB nominal du scénario de croissance.
- θ = ½ sur chaque ligne ouverte, le centre publié de chacune (`dividend_elasticity_firm_owners`, `dividend_elasticity_other_holders`, `dividend_share_firm_owners`, `dividend_wage_shift_firm_owners`, `employment_elasticity_smic`, `eti_all`, `eti_top_decile`, `firm_creation_profit_tax`, `is_croissance_pib`, `labour_supply_married_men`, `labour_supply_married_women`, `labour_supply_single_men`, `labour_supply_single_women`, `passthrough_benefit_linked`, `passthrough_unlinked`, `production_tax_investment`, `rd_cir_multiplier`, `wealth_disclosure_growth_effect_pp`, `wealth_tax_rate_elasticity`, `multiplicateur_macro`). La boîte θ déplace à 0 et à 1 les seules lignes que la réforme revendique, et le multiplicateur là où la boucle s'applique ; les autres θ ne sont lus par aucun canal de cette réforme.
- Départ : comptes APU 2025, dette 115,7 % du PIB, solde primaire −3,0 % du PIB, taux implicite 1,88 %, PIB 2 991,06 Md€.

## Δb en 2035, à θ = ½, et la boîte θ

Δb est la dette de la réforme moins celle de la référence, en points de PIB, sous les mêmes scénarios : positif, la réforme alourdit la dette.

| Scénario | Δb 2035 à θ = ½ | Boîte θ, aux coins | Le signe tient-il ? |
|---|---:|---:|---|
| Dépenses gelées en volume · effet macro éteint après trois ans | +1,30 pt | +1,13 pt à +1,47 pt | oui, à chaque coin |
| Dépenses gelées en volume · effet macro tenu au niveau de la troisième année | +0,54 pt | −0,20 pt à +1,28 pt | non : dépend de θ |
| Dépenses constantes en % du PIB (sans boucle : persistance sans objet) | +1,48 pt | +1,48 pt à +1,49 pt | oui, à chaque coin |

La boîte est l'étendue de Δb quand chaque θ revendiqué parcourt [0 ; 1], lue aux coins après contrôle de monotonie : ni un intervalle de probabilité, ni une somme de tranches.

Sous « Dépenses gelées en volume · effet macro tenu au niveau de la troisième année », le signe de Δb change d'un coin à l'autre : −0,20 pt au coin (eti_all = 1, eti_top_decile = 1, multiplicateur_macro = 1), +1,28 pt au coin (eti_all = 0, eti_top_decile = 0, multiplicateur_macro = 0). La réforme y alourdit ou allège la dette selon où l'on place les effets dans leurs fourchettes publiées : la chaîne ne tranche pas, et le dit.

## La décomposition par source, en 2035

Le chiffre central se décompose dans l'ordre où la chaîne l'assemble : le coût mécanique seul, puis les recettes à θ = ½ du comportement, puis la boucle PIB → recettes en ses deux termes — le solde primaire que Mésange rend, recettes et dépenses induites, et le PIB de la réforme, qui divise sa dette et pèse donc à proportion du ratio de dette lui-même. Chaque terme est la différence entre deux étapes de la chaîne, et la somme tombe juste ; dans un autre ordre, les termes ne pèseraient pas tout à fait pareil.

| Scénario | Mécanique | Comportement | Rétroaction : solde | Rétroaction : PIB | Δb |
|---|---:|---:|---:|---:|---:|
| Dépenses gelées en volume · effet macro éteint après trois ans | +1,50 pt | −0,01 pt | −0,18 pt | +0,00 pt | +1,30 pt |
| Dépenses gelées en volume · effet macro tenu au niveau de la troisième année | +1,50 pt | −0,01 pt | −0,80 pt | −0,14 pt | +0,54 pt |
| Dépenses constantes en % du PIB (sans boucle : persistance sans objet) | +1,50 pt | −0,01 pt | absente | absente | +1,48 pt |

Les tranches de la chaîne, chacune sur son seul axe, au même horizon — à ne pas additionner (`dette.decomposition`) :

- **Dépenses gelées en volume · effet macro éteint après trois ans**
  - Boîte θ du comportement : chaque effet revendiqué n'importe où dans sa fourchette publiée, bornes lues aux coins : dette de la réforme de 105,08 % à 105,09 % du PIB.
  - Éventail macro : θ du multiplicateur de 0 à 1, comportement à sa valeur, bornes lues aux deux bouts : dette de la réforme de 104,92 % à 105,25 % du PIB.
  - Grille de scénarios : non calculée. Une seule combinaison de scénarios : chaque autre combinaison est un autre calcul, sous ses propres noms.
- **Dépenses gelées en volume · effet macro tenu au niveau de la troisième année**
  - Boîte θ du comportement : chaque effet revendiqué n'importe où dans sa fourchette publiée, bornes lues aux coins : dette de la réforme de 104,32 % à 104,33 % du PIB.
  - Éventail macro : θ du multiplicateur de 0 à 1, comportement à sa valeur, bornes lues aux deux bouts : dette de la réforme de 103,59 % à 105,06 % du PIB.
  - Grille de scénarios : non calculée. Une seule combinaison de scénarios : chaque autre combinaison est un autre calcul, sous ses propres noms.
- **Dépenses constantes en % du PIB (sans boucle : persistance sans objet)**
  - Boîte θ du comportement : chaque effet revendiqué n'importe où dans sa fourchette publiée, bornes lues aux coins : dette de la réforme de 133,45 % à 133,46 % du PIB.
  - Rétroaction macro : non calculée. Rétroaction non appliquée sous « Dépenses constantes en % du PIB » : pendant une variante, la dépense de Mésange ne réagit qu'en prix (note 70, folio 93). Sous une autre règle, une partie de l'amélioration du solde disparaîtrait, et la corriger par une formule serait dériver un chiffre, pas le lire (D-214).
  - Grille de scénarios : non calculée. Une seule combinaison de scénarios : chaque autre combinaison est un autre calcul, sous ses propres noms.

## Les coins de la boîte θ

- **Dépenses gelées en volume · effet macro éteint après trois ans** : eti_all = 0, eti_top_decile = 0, multiplicateur_macro = 0 → +1,47 pt ; eti_all = 0, eti_top_decile = 0, multiplicateur_macro = 1 → +1,14 pt ; eti_all = 0, eti_top_decile = 1, multiplicateur_macro = 0 → +1,47 pt ; eti_all = 0, eti_top_decile = 1, multiplicateur_macro = 1 → +1,14 pt ; eti_all = 1, eti_top_decile = 0, multiplicateur_macro = 0 → +1,47 pt ; eti_all = 1, eti_top_decile = 0, multiplicateur_macro = 1 → +1,14 pt ; eti_all = 1, eti_top_decile = 1, multiplicateur_macro = 0 → +1,46 pt ; eti_all = 1, eti_top_decile = 1, multiplicateur_macro = 1 → +1,13 pt.
- **Dépenses gelées en volume · effet macro tenu au niveau de la troisième année** : eti_all = 0, eti_top_decile = 0, multiplicateur_macro = 0 → +1,28 pt ; eti_all = 0, eti_top_decile = 0, multiplicateur_macro = 1 → −0,19 pt ; eti_all = 0, eti_top_decile = 1, multiplicateur_macro = 0 → +1,28 pt ; eti_all = 0, eti_top_decile = 1, multiplicateur_macro = 1 → −0,19 pt ; eti_all = 1, eti_top_decile = 0, multiplicateur_macro = 0 → +1,27 pt ; eti_all = 1, eti_top_decile = 0, multiplicateur_macro = 1 → −0,19 pt ; eti_all = 1, eti_top_decile = 1, multiplicateur_macro = 0 → +1,27 pt ; eti_all = 1, eti_top_decile = 1, multiplicateur_macro = 1 → −0,20 pt.
- **Dépenses constantes en % du PIB (sans boucle : persistance sans objet)** : eti_all = 0, eti_top_decile = 0 → +1,49 pt ; eti_all = 0, eti_top_decile = 1 → +1,49 pt ; eti_all = 1, eti_top_decile = 0 → +1,48 pt ; eti_all = 1, eti_top_decile = 1 → +1,48 pt.

## Année par année, à θ = ½

| Année | Dépenses gelées en volume · effet macro éteint après trois ans | Dépenses gelées en volume · effet macro tenu au niveau de la troisième année | Dépenses constantes en % du PIB (sans boucle : persistance sans objet) |
|---|---:|---:|---:|
| 2026 | +0,051 pt | +0,051 pt | +0,156 pt |
| 2027 *(report)* | +0,049 pt | +0,049 pt | +0,310 pt |
| 2028 *(report)* | +0,102 pt | +0,102 pt | +0,462 pt |
| 2029 *(report)* | +0,417 pt | +0,164 pt | +0,613 pt |
| 2030 *(report)* | +0,569 pt | +0,227 pt | +0,762 pt |
| 2031 *(report)* | +0,718 pt | +0,289 pt | +0,910 pt |
| 2032 *(report)* | +0,866 pt | +0,352 pt | +1,056 pt |
| 2033 *(report)* | +1,013 pt | +0,414 pt | +1,200 pt |
| 2034 *(report)* | +1,157 pt | +0,476 pt | +1,342 pt |
| 2035 *(report)* | +1,300 pt | +0,539 pt | +1,484 pt |

Les niveaux, en 2035 : Dépenses gelées en volume · effet macro éteint après trois ans, référence 103,8 % et réforme 105,1 % du PIB ; Dépenses gelées en volume · effet macro tenu au niveau de la troisième année, référence 103,8 % et réforme 104,3 % du PIB ; Dépenses constantes en % du PIB (sans boucle : persistance sans objet), référence 132,0 % et réforme 133,5 % du PIB. Le niveau dépend de scénarios que personne ne peut sourcer ; l'écart en dépend beaucoup moins, et c'est lui le chiffre.

## Les canaux fermés, et pourquoi

- **IS et investissement des entreprises** : aucune variante d'IS dans Mésange 2017, et aucune réestimation publiée depuis ; le seul chiffre localisé, un multiplicateur moyen de 0,7 pour la hausse d'IS de 2013 dans un billet de l'OFCE, n'est plus en ligne et n'aurait ni profil par horizon ni ligne de solde (§5, D-219). Le rapport final du comité d'évaluation de la fiscalité du capital (France Stratégie, 2023), lu, ne chiffre aucun effet de la baisse de l'IS à 25 % sur l'investissement : il résume une littérature, sans estimation française (§6.2, D-221). L'équation (6) de Hanappi, Millot et Turban (OCDE, 2023), la seule qui lise le taux légal avec ses écarts-types, ne s'ouvre pas : ses composantes se mesurent autour de valeurs de référence que l'article n'imprime pas, et la seule décomposition publiée, la figure A E.1, est une image sans valeurs (D-247).
- **transferts** : Mésange n'a pas de variante de transfert. Les deux méta-analyses IMK donnent 0,39 (écart-type 0,47) et 0,54 (écart-type 1,16) : elles divergent sur le centre, d'un facteur 2,5 sur la largeur, mêlent les horizons d'un à douze ans et n'ont ni ligne de solde ni centre français (§5, D-214, D-219).
- **créations d'entreprises** : C8 est un indice illustratif de la couche entreprises, en points de taux de création de sociétés, jamais une recette : la trajectoire chiffre le coût d'une baisse d'IS (D-244), pas les sociétés qu'elle ferait naître (§6.3, D-221). Le niveau national, sur Da Rin, Di Giacomo et Sembenelli, est refusé : la méthode de l'OCDE ne redonne pas le TMEI composite publié pour la France en 2025 (15,62 contre 14,97), faute des amortissements de ses cinq sous-groupes de biens corporels. La construction des auteurs prend aussi ce que le projet n'a pas : les amortissements du guide fiscal d'Ernst & Young et les marges des branches américaines (STAN) (D-247).
- **R&D et CIR** : C9 est un indice illustratif de la couche entreprises, en euros de R&D, jamais une recette ; la créance du CIR, induite comprise, n'est pas la recette d'une année, et le CIR reste hors de la trajectoire (§6.4, D-222, D-244).
- **rétroaction PIB → recettes**, sous « Dépenses constantes en % du PIB » seulement : Rétroaction non appliquée sous « Dépenses constantes en % du PIB » : pendant une variante, la dépense de Mésange ne réagit qu'en prix (note 70, folio 93). Sous une autre règle, une partie de l'amélioration du solde disparaîtrait, et la corriger par une formule serait dériver un chiffre, pas le lire (D-214).
- **multiplicateur macro**, sous « Dépenses constantes en % du PIB » seulement : Rétroaction non appliquée sous « Dépenses constantes en % du PIB » : pendant une variante, la dépense de Mésange ne réagit qu'en prix (note 70, folio 93). Sous une autre règle, une partie de l'amélioration du solde disparaîtrait, et la corriger par une formule serait dériver un chiffre, pas le lire (D-214).

## Ce qui est absent, et les conventions

- Absent, Dépenses constantes en % du PIB (sans boucle : persistance sans objet) — rétroaction : Rétroaction non appliquée sous « Dépenses constantes en % du PIB » : pendant une variante, la dépense de Mésange ne réagit qu'en prix (note 70, folio 93). Sous une autre règle, une partie de l'amélioration du solde disparaîtrait, et la corriger par une formule serait dériver un chiffre, pas le lire (D-214).
- Convention : Prélèvements constants en % du PIB
- Convention : Boîte θ : étendue des résultats quand chaque θ revendiqué parcourt [0 ; 1], lue aux coins après contrôle de monotonie. Ni une somme de tranches, ni un intervalle de probabilité.
- Convention, sous « Dépenses gelées en volume » : La ligne de Mésange est l'effet induit sur le solde PRIMAIRE : recettes, prestations chômage, transferts indexés sur le PIB et dépenses indexées sur les prix (note 70, tableau 10). Les intérêts de la dette supplémentaire sont ceux de la chaîne.
- Convention, sous « Dépenses gelées en volume » : Rétroaction mesurée contre le coût ex ante BRUT que la chaîne compte : un point pour les cotisations et la CSG, 1,18 pour la TVA, dont les APU versent environ 15 % (folio 112).
- Convention, sous « Dépenses gelées en volume » : Prix de la réforme tenus constants dans la croissance nominale : Mésange n'imprime aucun déflateur du PIB (D-214).
- Convention, sous « Dépenses gelées en volume » : Rétroaction proportionnelle au multiplicateur quand θ macro le déplace : hypothèse de §4.1. Bonne pour l'IR et la CSG, médiocre pour les cotisations employeurs la première année, où la rétroaction vaut 1,40 fois l'effet sur le PIB contre 0,46 pour l'IR (D-214).
- Convention, sous « Dépenses gelées en volume » : Impulsion = chiffrage mécanique, ex ante comme les variantes de Mésange. Le comportement de la phase 3 ne la modifie pas, et son recoupement avec la réponse de Mésange n'est pas mesuré.
- Convention, sous « Dépenses gelées en volume » : Chocs superposés : Mésange est linéaire, et une impulsion qui change d'une année à l'autre y est la somme de chocs permanents décalés.
- Convention, sous « Dépenses gelées en volume » : La colonne « 1 an » est lue comme une moyenne de la première année, ce que le document dit pour le tableau 12 et que la ligne de solde ne répète pas.
- Convention, sous « Dépenses gelées en volume · effet macro éteint après trois ans » : Au-delà de trois ans : Effet macro éteint après trois ans.
- Convention : Δ tenu en part de PIB constante au-delà de la dernière année chiffrée (convention, pas un chiffrage)
- Convention, sous « Dépenses gelées en volume · effet macro tenu au niveau de la troisième année » : Au-delà de trois ans : Effet macro tenu au niveau de la troisième année.

## Refaire le calcul

- `python scripts/write_predictif_exemple.py --price` : la passe de population (trois minutes, `data/` requis), puis la chaîne et la page.
- `python scripts/write_predictif_exemple.py` : la chaîne et la page depuis la première année du fichier (comptes APU et document Mésange requis).
- La même réforme sous d'autres scénarios ou un autre θ : `POST /predictif/simulate` ou le panneau prédictif de la page ; chaque autre combinaison est un autre calcul, sous ses propres noms.
