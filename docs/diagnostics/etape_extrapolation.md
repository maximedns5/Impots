# Étape « extrapolation » du but 19 : les totaux sur les salaires portés à la France entière

*Branche `claude/but19-haut`, à la suite de f70e69e, le 10 novembre 2026. Consigne :
`docs/diagnostics/CONSIGNE_ETAPES.md` et la décision du propriétaire du 10 novembre
(extrapoler, en supposant les salariés absents semblables aux présents ; chaque page le
dira). Aucune grille entière, aucune étude, aucune D-entrée ; `lignes.json` n'est pas touché
; `calibrate.py` non plus. Mesures sur 15 000 ménages (graine 20240101), droit 2024 sauf la
grille ; elles ne sont pas aveugles. Scripts d'essai, hors dépôt :
`/tmp/claude-0/-home-user-Impots/8c1eda0e-eb4f-5530-a9a9-deab4a4ca18f/scratchpad/extrap/`.*

## 0. En une phrase

Chaque salaire reste à sa valeur publiée ; dans les totaux et dans l'écart d'une réforme,
les montants assis sur le salaire d'un salarié (hors gérants) comptent **27,18 / 25,29 =
1,0747** fois, et rien d'autre ne bouge : les cotisations salariales passent de −17 à −11 %
du publié, la CSG d'activité de −13 à −7 %, D121 de −10 à −3 %, mais la réduction générale
de +6 à +14 % et le bandeau maladie de +13 à +21 % ; le coût du « droit au brut » d'Attal
passe de 55,8 à **60,9 Md€** (+9,1 %), l'impôt, les prestations et les niveaux de vie sont
inchangés à l'euro.

## 1. La méthode, et celles qui sont écartées

### 1.1 Retenue : un poids de personne sur les seuls instruments assis sur les salaires

**Ce qui est porté.** `aggregate.ASSIS_SUR_LES_SALAIRES` : salaire brut, super-brut et net,
cotisations salariales et employeurs, CSG déductible et imposable et CRDS sur les salaires,
réduction générale et bandeaux maladie et famille, et les trois mesures de D121
(prélèvements D291, pension de l'État D122, rémunération hors brut). Pour chacun, la passe
écrit par ménage une colonne `{clé}_hors_champ` : Σ sur ses membres de (K − 1) × le montant
de la personne, K = `margins.EXTRAPOLATION_SALARIES` pour chacun sauf les gérants
majoritaires (dont le salaire déclaré, 37,1 Md€, est déjà le leur entier : la masse des
salariés est (D11 − gérants) × 0,9305, celle des gérants n'est pas réduite). Un total, de
référence ou de réforme, est la somme pondérée plus celle de sa colonne hors champ ; un
écart est la différence de deux totaux portés. La masse portée vaut D11 : 1 109,9 Md€ sur
l'échantillon contre 1 111,65 publiés (−0,2 %).

**Le coût et l'identité comptable.** Le coût est Δ revenu disponible − Δ cotisations
employeurs payées (D-039). Les cotisations employeurs payées se lisent sur le super-brut et
le brut portés. Le revenu disponible est porté par son seul salaire net
(`revenu_disponible_hors_champ` est celui de `salaire_net`) : un salarié absent reçoit ce
que la réforme change à son net, rien d'autre. Comme Δ net = − Δ (cotisations + CSG + CRDS)
quand le brut ne bouge pas, ce qui s'ajoute au coût est exactement ce que les prélèvements
portés perdent de plus, et `guards.sector_balance` tient sans retouche (§ 2.2).

**Ce qui n'est pas porté, et pourquoi** (la même liste dans le docstring) :

* **L'impôt sur le revenu et son assiette** (`salaire_imposable`, l'IR, les foyers, les
  tranches). L'assiette est calée sur les salaires imposables déclarés
  (`margins.DECLARED_TAXABLE_WAGES`, 829,3 Md€) et l'atteint à 0,1 % sur le champ de
  l'enquête (`etape_haut.md` § 8.1, part exonérée nulle) : la porter mettrait les salaires
  déclarés à +7,5 % du publié et l'IR au barème de +5 % à +12 % environ. Le retour d'une
  réforme sur l'IR est celui des déclarations. C'est l'hypothèse la plus discutable de
  l'étape : si les absents déclaraient aussi en France (ce que les déclarations ne montrent
  pas), le coût d'Attal serait 60,0 Md€ au lieu de 60,9 (K × le coût de l'enquête).
* **Les prestations** (prime d'activité, RSA, aides au logement, AF) : celles des ménages
  enquêtés, que l'enquête pondère à la France ; un frontalier ou un résident de foyer n'en
  porte pas qui se lise ici. La prime d'une réforme sur les salaires n'est donc pas portée
  (−1,29 Md€ dans le coût d'Attal, inchangé).
* **Les retraités, les chômeurs, les non-salariés** (et la CSG sur leurs revenus), **les
  niveaux de vie, les déciles, les gagnants et perdants** : aucun ménage ne change de revenu
  ni de poids.
* **Les instruments mixtes.** Un foyer qui a un salaire et une pension : ses cotisations et
  sa CSG d'activité sont portées, sa CSG sur la pension, son IR et sa prime ne le sont pas.
  Les allègements sont individuels et entièrement assis sur le salaire : portés. La CSG sur
  les indemnités journalières (`csg_ij`) est calée sur la CCSS : non portée.

**Le réglage.** `margins.EXTRAPOLATION_SALARIES` (Figure, `use="context"`, sources et
caveat) ; `aggregate.EXTRAPOLER_SALARIES = True` (éteint, les totaux sont ceux de l'enquête
: c'est ainsi que l'« avant » est mesuré ci-dessous, sur la même passe) ;
`Aggregates.extrapolation_salaires` (1,0747, ou 1 sans colonne hors champ) ; et
`aggregate.PHRASE_EXTRAPOLATION`, la phrase d'une page publique :

> Les cotisations, la CSG et les allègements sur les salaires, et le coût des réformes qui
> les touchent, sont portés aux 27,2 millions de salariés de la France entière, en
> supposant les 1,9 million que l'enquête Emploi ne voit pas semblables aux autres ;
> l'impôt sur le revenu, les prestations et les niveaux de vie restent ceux des ménages
> enquêtés.

### 1.2 Écartée : une marge de plus dans le calage

Essai (raking seul, sans passe, sur la population entière) : une marge de personnes «
salarié / autre » qui porte les salariés pondérés de 24,93 à 26,84 M (× K), avec les trois
marges en place tenues à leurs valeurs actuelles. Le raking converge (34 itérations, aucun
ménage borné, ESS 138 273), et ce que la marge coûte :

| | avant | après | |
|---|---:|---:|---:|
| salariés (M) | 24,93 | 26,84 | +7,7 % |
| chômeurs (M) | 2,44 | 2,16 | −11,7 % |
| inactifs de 15 ans ou plus (M) | 24,26 | 23,08 | −4,9 % |
| retraités, pension > 0 (M) | 16,00 | 15,61 | −2,4 % |
| non-salariés (M) | 3,79 | 3,33 | −12,3 % |
| pensions (Md€, à revenu individuel fixé) | 374,4 | 365,3 | −2,4 % |
| chômage (Md€) | 35,9 | 31,7 | −11,7 % |
| salaires bruts (Md€) | 1 037,0 | 1 102,1 | +6,3 % |

L'âge, le sexe et les types de ménage tiennent : la marge déplace le poids, à âge et sexe
donnés, des ménages de chômeurs, d'inactifs, de non-salariés et de retraités vers ceux de
salariés. Les absents ne sont pas des résidents mal pondérés : ils vivent hors des logements
ordinaires, hors de France ou ont un emploi que la semaine de l'enquête ne voit pas. Le
calage casserait le taux d'emploi que l'enquête publie, retirerait 12 % des chômeurs (la
masse du chômage recalée, chacun recevrait 13 % de plus), changerait les prestations et les
niveaux de vie, et porterait l'assiette de l'IR au-dessus des déclarations. Écartée.

### 1.3 Écartées aussi

* **Un facteur sur toute la ligne d'un foyer qui a un salaire** : porterait la pension du
  conjoint, les AF des enfants et l'IR entier : des retraités et des prestations gonflés à
  tort.
* **Ajouter des salariés synthétiques** (des copies des salariés présents, en ménages d'une
  personne) : la même hypothèse, une passe plus lourde, et des foyers fiscaux et des
  prestations inventés (une personne seule au SMIC a une prime d'activité).
* **Lire les lignes publiées sur le champ de l'enquête** (le publié × 0,9305) : laisse le
  coût des réformes à 93 % de la France entière, ce que la décision refuse.

## 2. Les mesures

### 2.1 Les totaux (15 000 ménages, droit 2024)

Une passe, deux lectures (`EXTRAPOLER_SALARIES` éteint puis allumé). L'écart au publié est
celui de la grille de 2024 (§ 3).

| 2024, 15 000 ménages | avant | après | écart publié, avant → après |
|---|---:|---:|---|
| cotisations salariales (Md€) | 112,26 | 120,35 | −17,1 → −11,1 % |
| cotisations employeurs, super-brut − brut (Md€) | 379,25 | 406,70 | +15,2 → +23,5 % |
| cotisations employeurs D121 (Md€) | 297,50 | 318,89 | −9,7 → −3,2 % |
| réduction générale (Md€) | 41,85 | 44,84 | +6,4 → +14,0 % |
| bandeau maladie (Md€) | 29,86 | 32,03 | +12,9 → +21,1 % |
| bandeau famille (Md€) | 11,20 | 12,01 | +16,8 → +25,2 % |
| CSG d'activité (Md€) | 93,97 | 100,75 | −13,1 → −6,9 % |
| CSG d'activité avec les non-salariés (Md€) | 100,04 | 106,81 | −7,5 → −1,3 % |
| salaire brut (Md€) | 1 035,2 | 1 109,9 | (D11 : 1 111,65) |
| salaires déclarés, `salaire_imposable` (Md€) | 857,5 | 857,5 | −8,0 % |
| IR au barème (Md€) | 103,77 | 103,77 | +5,0 % |
| foyers à 0 / 11 / 30 / 41 / 45 % (M) | 11,95 / 18,26 / 7,98 / 0,408 / 0,095 | idem | |
| foyers imposés (M) | 21,16 | 21,16 | +7,5 % |
| prime servie (Md€) | 7,60 | 7,60 | −26,1 % |
| RSA servi (Md€) | 12,04 | 12,04 | +2,1 % |
| niveau de vie médian servi (€) | 24 561 | 24 561 | −8,1 % |
| D9/D1 servi | 3,311 | 3,311 | −4,9 % |
| revenu disponible (Md€, son net de salaire porté) | 1 265,9 | 1 325,6 | |

### 2.2 Le coût de trois réformes sur les salaires (15 000 ménages, droit 2024)

| réforme | coût avant | coût après | | Δ cotis. ou CSG | Δ IR | Δ prime |
|---|---:|---:|---:|---:|---:|---:|
| Attal, « droit au brut » (cotisations retraite salariales × 0,22) | 55,83 | **60,93** | +9,1 % | −71,32 → −76,42 | +13,76 | −1,29 |
| CSG déductible d'activité −0,5 point | 4,02 | **4,38** | +9,2 % | −5,11 → −5,48 | +0,97 | −0,10 |
| réduction générale jusqu'à 2 SMIC (Mélenchon) | 15,93 | **17,10** | +7,3 % | employeurs −15,93 → −17,10 | 0 | 0 |

(Md€.) Le coût gagne plus que 7,5 % quand le retour par l'IR et la prime, non porté, est
grand ; moins de 7,5 % quand la réforme touche des gérants (les allègements que le modèle
leur donne, biais connu de l'étape « ir », ne sont pas portés). L'identité comptable : le
coût rapporté contre le coût reconstitué des postes, Attal 60,927 contre 60,966 Md€ (−0,06
%, −0,06 % avant aussi), CSG 4,384 contre 4,388, allègements à l'euro ; le garde n'a pas
levé. Le coût en droit (plein recours) suit : Attal 54,63 → 59,73.

### 2.3 Sur la fixture et la population entière (tests)

Sur les 400 ménages de la fixture, la réforme d'Attal fuit de 0,15 % du net (180 739 € sur
116,7 M€) vers des prestations que la passe ne rapporte pas, **avant comme après** l'étape :
`sector_balance` la refuserait. Les tests neufs vérifient donc l'identité sur ce que
l'extrapolation ajoute, poste par poste. Le test lourd
`test_every_reform_shape_balances_on_the_real_population` **échoue, avant comme après**
l'étape, sur `csg_activite_imposable = 0,034` : coût −10,50 Md€ contre −9,92 reconstitués
sans l'extrapolation (réglage éteint, ce que faisait le code d'avant ; −11,23 contre −10,66
avec) ; l'écart, 0,58 Md€, est la CSG des non-salariés (`csg_non_salarie`, étape 2), qui
entre dans le revenu disponible et n'est pas dans `guards.STATE_RECEIPTS`. Hors de cette
étape ; le correctif probable est d'ajouter `csg_non_salarie` aux recettes, à faire et
tester à part.

## 3. La grille sur 15 000 ménages, et le pronostic

`docs/diagnostics/grille_ech_extrapolation.json` (commité) : `grille_ech.py`, les trois
années, sur la population de ce worktree. Écarts au publié en %, avant (la variante retenue
de `etape_haut.md` § 8.4, `grille_ech_haut.json`) et après ; pronostic : l'écart d'après,
élargi de 5 points pour les minima sociaux (RSA et prime), 5 / 10 / 25 pour les tranches à
30 / 41 / 45 %, 3 ailleurs, 0,5 pour les entreprises. « h » : hors de la tolérance attendu ;
« b » : au bord.

| ligne | tol. | avant 22 / 23 / 24 | après 22 / 23 / 24 | pronostic 2022 | 2023 | 2024 |
|---|---|---|---|---|---|---|
| `af_montant` | 25 | −15,3 / −15,0 / −13,7 | −15,3 / −15,0 / −13,7 | −18 à −12 | −18 à −12 | −17 à −11 |
| `aide_logement_montant` | 25 | −27,4 / −27,1 / −25,4 | −27,4 / −27,1 / −25,4 | −30 à −24 b | −30 à −24 b | −28 à −22 b |
| `bandeau_famille` | 15 | +19,7 / +17,5 / +16,8 | +28,4 / +26,0 / +25,2 | +25 à +31 h | +23 à +29 h | +22 à +28 h |
| `bandeau_maladie` | 15 | +15,0 / +13,4 / +12,9 | +23,3 / +21,6 / +21,1 | +20 à +26 h | +19 à +25 h | +18 à +24 h |
| `c3s` | 25 | +11,9 / +6,2 / +1,2 | +11,9 / +6,2 / +1,2 | +11,4 à +12,4 | +5,7 à +6,7 | +0,7 à +1,7 |
| `contribution_sociale_is` | 25 | −20,2 / +33,8 / +20,3 | −20,2 / +33,8 / +20,3 | −20,7 à −19,7 | +33,3 à +34,3 h | +19,8 à +20,8 |
| `cotisations_employeurs` | 15 | +18,1 / +17,1 / +15,2 | +26,7 / +25,6 / +23,5 | +24 à +30 h | +23 à +29 h | +20 à +26 h |
| `cotisations_employeurs_d121` | 15 | −7,2 / −8,1 / −9,7 | −0,5 / −1,5 / −3,2 | −4 à +2 | −4 à +2 | −6 à 0 |
| `cotisations_salariales` | 10 | −14,5 / −15,9 / −17,1 | −8,3 / −9,8 / −11,1 | −11 à −5 b | −13 à −7 b | −14 à −8 b |
| `csg_activite` | 15 | −12,7 / −12,6 / −13,1 | −6,4 / −6,3 / −6,9 | −9 à −3 | −9 à −3 | −10 à −4 |
| `csg_activite_avec_non_salaries` | 15 | −7,1 / −6,9 / −7,5 | −0,8 / −0,6 / −1,3 | −4 à +2 | −4 à +2 | −4 à +2 |
| `csg_remplacement` | 10 | −3,8 / −2,0 / −6,4 | −3,8 / −2,0 / −6,4 | −7 à −1 | −5 à +1 | −9 à −3 |
| `cvae` | 25 | — / — / −15,2 | — / — / −15,2 | — | — | −15,7 à −14,7 |
| `d9_d1` | 15 | −7,1 / −9,1 / −9,7 | −7,1 / −9,1 / −9,7 | −10 à −4 | −12 à −6 | −13 à −7 |
| `d9_d1_servi` | 15 | −2,0 / −4,4 / −4,9 | −2,0 / −4,4 / −4,9 | −5 à +1 | −7 à −1 | −8 à −2 |
| `foyers_fiscaux` | 10 | −5,0 / −6,1 / −7,1 | −5,0 / −6,1 / −7,1 | −8 à −2 | −9 à −3 | −10 à −4 b |
| `foyers_fiscaux_residents_hors_mayotte` | 10 | — / — / −6,2 | — / — / −6,2 | — | — | −9 à −3 |
| `foyers_imposes` | 10 | +15,3 / +12,6 / +7,5 | +15,3 / +12,6 / +7,5 | +12 à +18 h | +10 à +16 b | +5 à +11 b |
| `foyers_tmi_0` | 15 | −10,1 / −10,9 / −9,0 | −10,1 / −10,9 / −9,0 | −13 à −7 | −14 à −8 | −12 à −6 |
| `foyers_tmi_1` | 15 | −10,0 / −11,4 / −12,7 | −10,0 / −11,4 / −12,7 | −13 à −7 | −14 à −8 | −16 à −10 b |
| `foyers_tmi_2` | 15 | +24,1 / +23,3 / +16,1 | +24,1 / +23,3 / +16,1 | +19 à +29 h | +18 à +28 h | +11 à +21 b |
| `foyers_tmi_3` | 30 | −8,8 / −5,6 / −6,1 | −8,8 / −5,6 / −6,1 | −19 à +1 | −16 à +4 | −16 à +4 |
| `foyers_tmi_4` | 30 | +42,8 / +56,1 / +54,9 | +42,8 / +56,1 / +54,9 | +18 à +68 b | +31 à +81 h | +30 à +80 b |
| `impots_salaires_calcules` | 20 | −10,1 / −10,0 / −10,4 | −3,6 / −3,6 / −4,0 | −7 à −1 | −7 à −1 | −7 à −1 |
| `impots_salaires_d291` | ctx | −71,4 / −71,6 / −71,7 | −69,3 / −69,6 / −69,7 | −72 à −66 | −73 à −67 | −73 à −67 |
| `ir_bareme` | 10 | — / +9,4 / +5,0 | — / +9,4 / +5,0 | — | +6 à +12 b | +2 à +8 |
| `ir_net` | 15 | +17,1 / +19,6 / +15,4 | +17,1 / +19,6 / +15,4 | +14 à +20 b | +17 à +23 h | +12 à +18 b |
| `is` | 20 | −19,7 / −0,8 / +2,0 | −19,7 / −0,8 / +2,0 | −20,2 à −19,2 b | −1,3 à −0,3 | +1,5 à +2,5 |
| `niveau_de_vie_median` | 15 | −5,3 / −6,5 / −7,7 | −5,3 / −6,5 / −7,7 | −8 à −2 | −10 à −4 | −11 à −5 |
| `niveau_de_vie_median_servi` | 15 | −5,7 / −6,9 / −8,1 | −5,7 / −6,9 / −8,1 | −9 à −3 | −10 à −4 | −11 à −5 |
| `pension_etat_d122` | ctx | −11,9 / −11,4 / −13,7 | −5,3 / −4,8 / −7,2 | −8 à −2 | −8 à −2 | −10 à −4 |
| `pensions_declarees` | ctx | +3,8 / +3,4 / — | +3,8 / +3,4 / — | +1 à +7 | 0 à +6 | — |
| `ppa_foyers` | 25 | +40,9 / +32,7 / +37,6 | +40,9 / +32,7 / +37,6 | +36 à +46 h | +28 à +38 h | +33 à +43 h |
| `ppa_foyers_servis` | 25 | −30,3 / −34,2 / −32,1 | −30,3 / −34,2 / −32,1 | −35 à −25 h | −39 à −29 h | −37 à −27 h |
| `ppa_montant` | 13 | −19,1 / −21,0 / −17,6 | −19,1 / −21,0 / −17,6 | −24 à −14 h | −26 à −16 h | −23 à −13 b |
| `ppa_montant_servi` | 13 | −27,5 / −29,1 / −26,1 | −27,5 / −29,1 / −26,1 | −32 à −22 h | −34 à −24 h | −31 à −21 h |
| `reduction_generale` | 15 | +7,7 / +4,6 / +6,4 | +15,4 / +12,0 / +14,0 | +12 à +18 b | +9 à +15 b | +11 à +17 b |
| `revenus_non_salaries_hors_gerants` | 15 | +15,6 / +18,8 / +8,2 | +15,6 / +18,8 / +8,2 | +13 à +19 b | +16 à +22 h | +5 à +11 |
| `rsa_foyers` | 25 | — / +48,6 / +49,4 | — / +48,6 / +49,4 | — | +44 à +54 h | +44 à +54 h |
| `rsa_foyers_servis` | 25 | — / −2,0 / −1,7 | — / −2,0 / −1,7 | — | −7 à +3 | −7 à +3 |
| `rsa_montant` | 14 | +5,7 / +7,4 / +10,0 | +5,7 / +7,4 / +10,0 | +1 à +11 | +2 à +12 | +5 à +15 b |
| `rsa_montant_servi` | 14 | −1,8 / −0,2 / +2,1 | −1,8 / −0,2 / +2,1 | −7 à +3 | −5 à +5 | −3 à +7 |
| `salaires_declares` | 10 | −6,8 / −8,0 / −8,0 | −6,8 / −8,0 / −8,0 | −10 à −4 | −11 à −5 b | −11 à −5 b |

Au centre de l'échantillon : **71 lignes sur 113 dans leur tolérance** (73 avant). Gagnées
(2) : les cotisations salariales de 2022 et 2023 (−8,3 et −9,8 %). Perdues (4) : le bandeau
maladie des trois années (de +13 à +15 % à +21 à +23 %) et la réduction générale de 2022
(+15,4 %). Se rapprochent : D121 (−3 %), la CSG d'activité (−7 %, avec les non-salariés −1
%), les impôts sur les salaires calculés (−4 %), les cotisations salariales de 2024 (−11,1
%, au bord), la pension de l'État (contexte). S'éloignent : le bandeau famille (déjà dehors,
+25 %), les cotisations employeurs au sens de D-363 (déjà dehors, +24 %), la réduction
générale (+12 à +15 %). Rien d'autre ne bouge, à l'euro.

**Ce que la grille dit.** Les prélèvements assis sur la masse (cotisations, CSG, D121)
tombent à quelques points du publié : l'hypothèse tient pour eux. Les allègements, eux,
passent à +14 / +21 / +25 % : ils étaient déjà au-dessus du publié sur le champ de
l'enquête, et les porter, alors que les absents sont en moyenne moins payés (plus
d'allègement par tête, pas moins), ne peut que creuser. L'excès des allègements est
antérieur à l'étape : trop de salaires au voisinage du SMIC, ou le SMIC proratisé (quotité,
mois travaillés de l'étape « ppa ») trop bas, dans la population de l'enquête. C'est le
prochain défaut à chercher ; l'extrapolation le rend visible.

**Le préenregistrement proposé.** Aucune ligne neuve ni marge neuve. Les lignes
`cotisations_salariales`, `cotisations_employeurs`, `cotisations_employeurs_d121`,
`reduction_generale`, `bandeau_maladie`, `bandeau_famille`, `csg_activite`,
`csg_activite_avec_non_salaries`, `impots_salaires_calcules` et `pension_etat_d122` lisent
désormais des totaux portés : leur mesure change de sens, sans changer de nom ; la D-entrée
de jonction doit le dire, avec la phrase de § 1.1 et le facteur (1,0747, 2024 ; le même
appliqué en 2022 et 2023, faute du rapport des années vieillies, hypothèse). Le pronostic
est le tableau ci-dessus.

## 4. Ce que l'étape fait aux études

Sans les relancer. Seules bougent les études dont la réforme touche un instrument porté :

* **Attal** (cotisations retraite salariales × 0,22) : le coût mécanique +9 % (55,8 → 60,9
  Md€ en droit 2024 sur l'échantillon) ; les gains par décile, inchangés.
* **Retailleau** (le même bouton × 0,87) : +9 % environ, le même rapport.
* **Mélenchon** (réduction générale à 2 SMIC) : +7,3 % (15,9 → 17,1 Md€). Le canal d'emploi
  C2 lit les salariés de la passe (`run.persons`) à leur poids : ses emplois ne sont pas
  portés, alors que `contribution_delta` l'est ; la bande comportementale mélange donc les
  deux champs. À décider : porter aussi le poids des salariés dans `persons`, ou dire la
  bande sur le champ de l'enquête.
* **Lisnard** (CSG d'activité à 6,6 %, quotient familial déplafonné) : la part CSG +9 %
  environ (le −0,5 point mesuré : +9,2 %), la part du quotient inchangée.
* **Inchangées** : PLF 2027 art. 2, 3 et 15 (barème, pensions), PLFSS art. 74 (prime et
  APL), Labib, Le Pen, Roussel (TVA et accises), Tondelier (barème). Aucun nombre n'en
  bouge, à l'euro, puisque rien de ce qu'elles touchent n'est porté.

## 5. Ce qui reste, les doutes

* **Le retour par l'IR** d'une réforme sur les salaires n'est pas porté (§ 1.1) : 0,9 Md€
  sur Attal. Le choix suit les déclarations ; il se discute.
* **Le facteur est celui de 2024**, appliqué aux trois années de la grille.
* **Les gérants** gardent les allègements et cotisations salariales que le modèle leur donne
  (biais de l'étape « ir ») ; ils ne sont pas portés.
* **C2** (§ 4) et toute sortie qui lit les personnes de la passe (`run.persons`) restent sur
  le champ de l'enquête.
* **La page publique** : la phrase et le réglage existent (`PHRASE_EXTRAPOLATION`,
  `Aggregates.extrapolation_salaires`) ; aucune page ne les lit encore.
* **Deux identités qui fuient avant l'étape** (§ 2.3) : la CSG des non-salariés hors des
  recettes du garde, et la fuite de 0,15 % de la fixture.
* Le revenu disponible total porté (1 325,6 Md€) n'est comparé à rien ; s'il l'était, il
  compterait le net des absents et pas leurs autres revenus.

## 6. Les fichiers changés, et les tests

* `population/margins.py` : la Figure `EXTRAPOLATION_SALARIES` (1 / `CHAMP_SALARIES_
  ENQUETE`), sources (T_6210 ; ECRT 2026 fiche 2.1 et enquête Emploi 2024) et caveat.
* `population/aggregate.py` : `ASSIS_SUR_LES_SALAIRES`, `HORS_CHAMP`, `EXTRAPOLER_SALARIES`,
  `PHRASE_EXTRAPOLATION`, `extrapole()`, le champ `Aggregates.extrapolation_salaires` ; les
  totaux, les totaux de réforme et les cotisations employeurs payées lisent `extrapole`. Les
  comptes, quantiles et déciles non.
* `population/runner.py` : les colonnes `{clé}_hors_champ` (et `_reform`) des instruments
  portés, K − 1 pour chaque personne sauf les gérants. Aucune clé neuve dans
  `outputs.REGISTRY` ni dans `Aggregates.totals` : la réponse de l'API ne change pas de
  champs.
* `tests/test_extrapolation.py` (neuf, 5 tests) : le facteur ; le brut porté (gérants une
  fois, salariés K fois) ; les instruments portés et les autres inchangés à l'euro (IR,
  assiette, prime, RSA, AL, AF, retraites, CSG des retraités et non-salariés, comptes,
  quantiles, déciles) ; le coût d'Attal gagne K − 1 fois la baisse des cotisations hors
  gérants et exactement ce que les recettes perdent de plus ; la réduction générale à 2
  SMIC.

```
PYTHONPATH=src .venv/bin/python -m pytest -m "not lourd and not chrono" -n 2 \
  tests/test_extrapolation.py
5 passed
# sur le code d'avant (git stash des sources) : 5 failed (AttributeError : ni la Figure,
# ni le réglage, ni les colonnes hors champ n'existent)
PYTHONPATH=src .venv/bin/python -m pytest -m "not lourd and not chrono" -n 2 \
  tests/test_population.py tests/test_verification.py tests/test_non_salaries.py \
  tests/test_salaires_exoneres.py tests/test_api.py tests/test_recours.py \
  tests/test_consommation.py tests/test_agregats.py tests/test_reporting.py \
  tests/test_zero_masked.py
277 passed
PYTHONPATH=src .venv/bin/python -m pytest -m "not lourd and not chrono" -n 3 \
  tests/test_behavioural.py tests/test_narrow_band.py tests/test_top_tail.py \
  tests/test_ij.py tests/test_cdhr.py tests/test_instrument_coverage.py \
  tests/test_retroaction.py tests/test_cells.py tests/test_macro.py \
  tests/test_prestations.py tests/test_niche_imputation.py
293 passed, 2 skipped
# lourds, chacun seul :
tests/test_api.py::test_population_simulate_prices_a_reform                 1 passed
tests/test_population.py::test_every_reform_shape_balances_on_the_real_population
                                              1 failed, avant comme après (§ 2.3)
ruff check (fichiers touchés) : propre
```

Non lancés : la suite entière, `make impact`, les autres lourds, la grille entière.
