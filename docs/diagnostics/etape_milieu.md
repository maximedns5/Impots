# Étape « milieu » du but 19 : la tranche à 30 %, les foyers imposés, l'assiette de l'IR

*Branche `claude/but19-milieu`, partie de `claude/but19` (42db106, D-369), le 10 novembre
2026. Consigne : `docs/diagnostics/CONSIGNE_ETAPES.md` et la demande du coordinateur
(l'excès de la tranche à 30 % et des foyers imposés après D-368). Aucune grille entière,
aucune étude, aucune D-entrée ; `lignes.json` n'est pas touché ; `to_openfisca.py`,
`engine/corrections.py`, `aggregate.py` et `runner.py` (l'étape des allègements, en
parallèle) ne le sont pas. La population de `data/processed` (copie réelle) est
reconstruite avec ce code. Scripts d'essai, hors dépôt :
`/tmp/claude-0/-home-user-Impots/8c1eda0e-eb4f-5530-a9a9-deab4a4ca18f/scratchpad/milieu/`.*

## 0. En une phrase

L'excès du milieu ne vient pas de la forme des salaires, qui tient les centiles publiés en
EQTP à 1 % près, mais de leur **assiette imposable** : D-368 a ramené la masse des salaires
au champ de l'enquête (× 0,9305) et laissé la part exonérée viser les salaires déclarés de
la France entière ; les 25,3 M de salariés de l'enquête déclaraient donc ce que déclarent
27,2 M, et la part tombait à 0. Calée sur la part du champ des salaires déclarés (même
rapport, mêmes sources), la part revient à 6,85 % : sur 15 000 ménages, la tranche à 30 %
passe de **+16,1 à +3,7 %**, les foyers imposés de **+7,5 à +2,6 %**, l'IR net de +15,4 à
+3,9 % ; mais l'IR au barème passe de +5,0 à **−5,6 %** et la tranche à 41 % de −6 à
**−19 %**, toutes deux dans leur tolérance : c'est le prix de l'IR non extrapolé (D-368),
qui se voit maintenant en entier (§ 5).

## 1. Ce qui a changé, fichier par fichier

**`population/incomes.py`** :

* `PART_EXONEREE_SUR_LE_CHAMP` (neuf, `True`) : dans `attach_incomes`, la cible de la part
  exonérée devient `DECLARED_TAXABLE_WAGES × CHAMP_SALARIES_ENQUETE` (829,33 × 0,9305 =
  771,7 Md€) au lieu de 829,33 Md€. La masse brute des salariés est D11 hors gérants fois
  le même rapport depuis D-368 ; leur assiette déclarée l'est maintenant aussi. La part
  vaut 0,0685 sur la population (0 avant). Elle reste commune à tous les salariés
  (hypothèse de l'étape « ir ») et n'est lue que par l'impôt (correction 24). `False`
  refait la population de D-368.
* `RANG_EQTP` (neuf, `True`) : dans `_draw_net_eqtp`, le rang de chaque salarié sur la
  courbe publiée, et l'ajustement par âge et sexe, sont pondérés par son poids fois sa
  quotité. Les quantiles publiés sont ceux des « salariés en EQTP » (IP n° 2079, figure 3 :
  « 10 % des salariés en EQTP » ; figure 2, effectifs « en milliers d'EQTP »). Un rang par
  tête donnait aux temps partiels, bas dans le tirage, plus de la courbe qu'ils n'en
  tiennent. La durée n'est pas comptée une seconde fois : un échantillon d'une semaine
  tient déjà un poste au prorata du temps où il est tenu. Effet mesuré : faible (le
  facteur de calage de la masse passe de 0,988 à 0,997 ; les quantiles EQTP de 0,5 %).
  Un cadre sans quotité (les cadres synthétiques des tests) est rangé par tête.

**Tests.** `tests/test_salaires_haut.py` : `test_the_published_quantiles_are_held_in_eqtp`
(neuf, trois cas) ; `tests/test_non_salaries.py` :
`test_the_exempt_share_makes_the_declared_salaries`, dont la cible devient la part du
champ (la raison est dans le test). § 7.

`PLEIN_AVANT` n'est pas recalé : le facteur de l'emploi discontinu vaut 0,99999 sur la
population reconstruite.

## 2. Où est l'excès

Mesures foyer par foyer sur 15 000 ménages (`runner.subsample`, graine 20240101), droit
2024, palier complet, sans imputation, sur la population de D-368 (identique à celle de
`data/processed` au départ, refaite à l'octet). **Pas aveugles** : faites en développant.

### 2.1 La forme des salaires tient les quantiles publiés

Le salaire net mensuel en EQTP des salariés du privé (salaire annuel / quotité / mois
travaillés), pondéré par l'EQTP, contre l'IP n° 2079 :

| | P5 | P10 | P25 | P50 | P90 | P95 | P99 |
|---|---:|---:|---:|---:|---:|---:|---:|
| modèle, D-368 | 1 352 | 1 481 | 1 734 | 2 184 | 4 340 | 5 603 | 10 254 |
| modèle, après | 1 358 | 1 488 | 1 741 | 2 183 | 4 321 | 5 576 | 10 233 |
| publié | 1 362 | 1 492 | 1 746 | 2 190 | 4 334 | 5 593 | 10 261 |

**Le temps partiel est appliqué une fois** au montant (`gross_annual *= quotite_travail`,
puis les mois travaillés de l'étape « ppa », qui le répartissent sans changer la masse) ;
openfisca ne reçoit ni heures ni quotité. Il ne l'était **aucune fois** au rang, quand les
quantiles publiés le comptent : corrigé (`RANG_EQTP`), d'effet faible, parce que la quotité
de l'enquête est peu liée au tirage par PCS, âge et sexe.

### 2.2 Ce qui est trop haut : l'assiette par tête, pas la forme

Les salaires déclarés de 2024 par personne (export 2042 de la DGFiP, déjà au manifeste) :
1AJ 22,92 M de déclarants (616,0 Md€), 1BJ 6,40 M (175,1), 1CJ et 1DJ 1,03 M, soit
**30,35 M** de personnes, plus 0,82 M de gérants (1GB, 1HB). Le modèle paie **28,58 M** de
personnes (gérants et sortants compris), dont 20,71 M déclarants principaux, 6,35 M
conjoints, 1,51 M personnes à charge. Avant ce correctif, il leur faisait déclarer 857 Md€
(828 hors gérants), le total de la France : **chacun 7 à 8 % de trop**. C'est ce que dit
D-368 de la masse (les salariés absents de l'enquête sont 1,9 M) et ce que la part
exonérée défaisait en visant le total national.

Le revenu salarial annuel net par personne (ECRT 2026, fiche « Revenu salarial », 2023,
non calé) le confirme et dit où : médiane du modèle 23 616 € contre 22 270 (2023), D9
46 727 contre 44 590, soit +3 et +2 % une fois la hausse de 2024 retirée ; mais par PCS,
la médiane des **employés** est à 19 927 € contre 17 270 (+12 %), celle des **ouvriers** à
22 037 contre 19 300 (+11 %), quand celles des cadres (+3 %) et des professions
intermédiaires (0 %) tiennent. Le volume de travail moyen du modèle est de 0,844 EQTP
contre 0,77 publié (0,68 pour les employés, 0,73 pour les ouvriers) : ce qui manque, ce
sont les contrats courts et les années incomplètes, que la semaine de l'enquête ne voit
pas (l'étape « ppa » bute sur sa borne, `emploi_discontinu.PLEIN_AVANT`). Le D1 du modèle,
8 305 € contre 3 470, le dit aussi.

### 2.3 Par tranche de RFR (IRCOM 2025), avant → après

Foyers, foyers imposés, foyers déclarant des salaires et leur montant (`salaire_imposable`
d'openfisca, avant part exonérée ; l'IRCOM compte aussi le chômage), en M et Md€ :

| RFR | foyers | imposés | f. salaires | salaires | IRCOM : foyers / imposés / f. sal. / sal. |
|---|---|---|---|---|---|
| 0-10 k | 7,40 → 7,59 | 0 → 0 | 1,61 → 1,81 | 10,4 → 12,6 | 8,07 / 0,18 / 3,02 / 18,4 |
| 10-12 k | 1,28 → 1,30 | 0 → 0 | 0,47 → 0,49 | 5,4 → 6,2 | 1,58 / 0,05 / 0,92 / 10,8 |
| 12-15 k | 2,14 → 2,30 | 0 → 0 | 1,00 → 1,15 | 13,6 → 16,9 | 2,60 / 0,09 / 1,59 / 23,2 |
| 15-20 k | 4,44 → 4,91 | 1,77 → 1,89 | 2,78 → 3,25 | 51,3 → 64,2 | 5,22 / 1,49 / 3,70 / 71,5 |
| 20-30 k | 8,11 → 8,19 | 5,61 → 5,55 | 5,58 → 5,65 | 143,7 → 155,4 | 8,72 / 5,34 / 6,09 / 159,4 |
| 30-50 k | 8,74 → 8,42 | 7,31 → 6,89 | 5,99 → 5,67 | 236,1 → 237,7 | 8,54 / 6,16 / 5,74 / 223,3 |
| 50-100 k | 5,65 → 5,19 | 5,53 → 5,07 | 4,28 → 3,82 | 283,9 → 266,4 | 5,49 / 5,00 / 4,21 / 273,5 |
| > 100 k | 0,93 → 0,80 | 0,93 → 0,80 | 0,76 → 0,63 | 113,2 → 98,0 | 1,41 / 1,37 / 1,17 / 150,3 |

L'excès des foyers imposés était de 30 à 100 000 € de RFR (+1,7 M, dont 1,15 M de 30 à
50 000 €, où 84 % des foyers du modèle étaient imposés contre 72 %) ; il en reste 0,8 M.
Le modèle manque de **foyers à petits salaires** sous 20 000 € (3,5 M déclarant des
salaires contre 6,5 M au compte de l'IRCOM) : les contrats courts du § 2.2 et les foyers
absents du § 2.6. Au-dessus de 100 000 €, la tranche a 0,80 M de foyers contre 1,41 : le
capital (absent de cette passe) y fait monter les foyers réels ; le correctif l'abaisse
encore (§ 5).

### 2.4 Par taux marginal (DGFiP), avant → après

| TMI | foyers (M) | publié | écart | impôt au barème / impôt net publié (Md€) |
|---|---|---:|---|---|
| 0 % | 11,95 → 12,39 | 13,13 | −9,0 → −5,6 % | 0 → 0 / −0,6 |
| 11 % | 18,26 → 18,75 | 20,93 | −12,7 → −10,4 % | 16,3 → 15,8 / 12,7 |
| 30 % | 7,98 → 7,12 | 6,87 | **+16,1 → +3,7 %** | 58,0 → 51,2 / 48,9 |
| 41 % | 0,408 → 0,350 | 0,434 | −6,0 → −19,4 % | 14,9 → 13,1 / 17,8 |
| 45 % | 0,095 → 0,083 | 0,061 | +55 → +35 % | 14,6 → 13,2 / 12,5 |

Par décile de RFR par part (DGFiP n° 41, tableau 2), l'impôt au barème moyen des 6e à 9e
déciles passait le publié de 75, 42, 26 et 22 % ; après, de 35, 18, 10 et 6 %.

### 2.5 Les foyers imposés : la moitié est une affaire de mesure

L'IRCOM compte les foyers dont l'impôt net, **après réductions et crédits**, est positif
(19,68 M). La ligne `foyers_imposes` de la grille les compte dans la passe sans imputation,
donc avant crédits. Dans la passe imputée (niches et capital, celle de l'IR net), sur le
même échantillon : **19,86 M avant ce correctif (+0,9 %), 18,95 M après (−3,7 %)**, contre
21,16 et 20,20 M dans la passe de la grille. Les crédits d'impôt (emploi à domicile 5,1 M
de foyers, garde d'enfants 1,9 M ; n° 41, tableau 3) rendent environ 1,3 M de foyers non
imposés que la grille compte imposés. Proposé au § 4.

### 2.6 Ce qui n'y est pour rien, ou ne se corrige pas sans données absentes

* **L'appariement des conjoints.** L'IR d'un couple marié ou pacsé ne dépend que de la
  somme de ses revenus : la répartition entre conjoints ne touche ni ses parts ni son
  taux marginal. Elle ne compte que pour les concubins, déclarés à part (2,9 M de couples
  scindés, étape 3). Dans le modèle : 12,14 M de foyers de couple (13,05 déclarés), 4,82 M
  à deux salaires ; 6,35 M de conjoints payés contre 6,40 M de 1BJ ; corrélation des
  logarithmes 0,12 ; le moins payé apporte 36 % en moyenne. Aucune mesure publiée de la
  corrélation n'est au manifeste : non vérifiable, et sans effet sur la tranche à 30 %
  des foyers joints.
* **Le quotient familial.** Personnes à charge 16,67 M contre 17,2 M environ (0CF 15,15 M
  et 0DJ 2,01 M) ; la case T est en excès de 0,8 M (étape 3), ce qui baisse l'impôt et
  ne pousse pas la tranche à 30 %. Les parts par tranche ne sont pas publiées.
* **Les foyers manquants** (−6 %, 2,9 M) : hors ménages ordinaires (1,25 M d'adultes,
  POP2), non-résidents (0,30 M), Mayotte (0,08 M), décès de l'année (`foyers_fiscaux.md`).
  Ils sont presque tous non imposés : leur absence fait les tranches à 0 et 11 % trop
  basses (−5,6 et −10,4 % après), **pas le compte** des foyers imposés (l'IRCOM n'en a que
  0,32 M sous 15 000 € de RFR). Les ajouter demande leurs revenus (l'enquête EHPA de la
  Drees n'est pas lisible ici) : non fait.
* **Les contrats courts** (§ 2.2) : 2 à 2,5 M de personnes payées dans l'année que la
  semaine de l'enquête ne voit pas, aux salaires annuels faibles. Le volume de travail
  publié (0,77) n'est pas atteignable par les flux de l'enquête (`PLEIN_AVANT` à sa borne
  donne 0,813). Il faudrait la distribution des durées d'emploi dans l'année par personne
  (panel Tous salariés, DSN, hors du conteneur) : non fait. C'est le reste de l'excès des
  employés et ouvriers, et du manque de petits salaires sous 20 000 € de RFR.
* **Les charges déductibles et frais réels** (17 Md€ et 35 Md€) : leur clé par tranche
  n'est pas publiée (étapes « ir » et 3) : non câblés.

### 2.7 Pourquoi le D9/D1 du niveau de vie s'est resserré

De D-367 à D-369, le D9/D1 (droit) est passé de −1 à −9 % du publié. Les mesures de
l'étape « haut » (§ 7.3 et 8.3, servi, 15 000 ménages) le décomposent : 3,544 avant, 3,465
quand toute la distribution est lue sur les quantiles publiés (le bas des salaires monte,
D1 +4 % ; le haut s'amincit), **3,311 quand la masse est ramenée au champ** (× 0,9305 :
les ménages du D9, qui vivent de salaires, perdent 7 % ; ceux du D1, de prestations et de
pensions, presque rien). Les deux tiers viennent du champ, un tiers de la forme. Ce
correctif rend 1,3 % (l'impôt baisse surtout au-dessus de la médiane) : D9/D1 servi 3,312
→ 3,357, droit 3,143 → 3,182. Le reste ne se corrige pas sans défaire D-368 ; le capital,
absent de la passe de la grille et compté par l'ERFS, en est une autre part (non mesuré :
la passe imputée ne calcule pas les déciles).

## 3. Les mesures, avant et après (2024, 15 000 ménages)

Avant : la population de D-368. Après : celle de ce code. Même échantillon, mêmes ménages,
poids, pensions et prestations ; seuls la part exonérée (0 → 6,85 %) et, très peu, les
salaires bruts (le rang en EQTP) changent.

| 2024 | avant | après | publié | écart, avant → après |
|---|---:|---:|---:|---|
| foyers à 0 / 11 % (M) | 11,95 / 18,26 | 12,39 / 18,75 | 13,13 / 20,93 | −9,0 / −12,7 → −5,6 / −10,4 % |
| foyers à 30 % (M) | 7,98 | 7,12 | 6,87 | +16,1 → +3,7 % |
| foyers à 41 / 45 % (M) | 0,408 / 0,095 | 0,350 / 0,083 | 0,434 / 0,061 | −6 / +55 → −19 / +35 % |
| foyers imposés, grille (M) | 21,16 | 20,20 | 19,68 | +7,5 → +2,6 % |
| foyers imposés, passe imputée (M) | 19,86 | 18,95 | 19,68 | +0,9 → −3,7 % |
| IR au barème (Md€) | 103,77 | 93,30 | 98,84 | +5,0 → −5,6 % |
| IR net, passe imputée (Md€) | 105,70 | 95,20 | | +15,4 → +3,9 % (grille) |
| salaires déclarés (Md€) | 857,5 | 857,5 | 932,1 | −8,0 % (inchangé) |
| niveau de vie médian, servi (€) | 24 561 | 24 702 | 26 740 | −8,1 → −7,6 % |
| D9/D1, servi / droit | 3,312 / 3,143 | 3,357 / 3,182 | | droit −9,7 → −8,6 % |
| prime servie (Md€) | 7,67 | 7,62 | 10,28 | −0,7 % |
| RSA servi (Md€) | 11,90 | 11,90 | 11,79 | inchangé |
| réduction générale, portée (Md€) | 44,84 | 44,53 | 39,35 | +14,0 → +13,1 % |

La ligne des salaires déclarés lit `salaire_imposable` d'openfisca, avant la part
exonérée : elle ne bouge pas. La prime baisse un peu (−0,7 %) : le rang en EQTP relève les
taux mensuels de 0,9 %. La réduction générale baisse de 0,7 % pour la même raison.

## 4. Le préenregistrement proposé

### 4.1 Marges

Aucune marge neuve. La cible de la part exonérée garde ses deux sources dépensées
(`DECLARED_TAXABLE_WAGES`, export 2042 et IRCOM ; `CHAMP_SALARIES_ENQUETE`, ECRT 2026 et
comptes nationaux) ; c'est leur produit qui est visé. Le rang en EQTP ne dépense rien.

### 4.2 Lignes neuves proposées

* **Foyers imposés après réductions et crédits** (validation, ±10 %) : IRCOM, « nombre
  de foyers fiscaux imposés » (19 681 757 en 2024 ; IRCOM 2024 et 2023 pour 2023 et
  2022), mesurés dans la passe imputée de l'IR net (`verification.mesures_ir_net`, compte
  `n_foyers_imposes`). Raison : c'est ce que l'IRCOM compte ; la ligne actuelle compte
  avant crédits (§ 2.5). Pronostic 2024 : −9 à +2 % (−3,7 sur l'échantillon, ±5) ; 2022 et
  2023 non mesurés.
* **Personnes déclarant des salaires** (contexte) : export 2042, cases 1AJ + 1BJ + 1CJ +
  1DJ (30,35 M en 2024), contre les personnes payées de la population hors gérants.
  Raison : c'est la mesure publiée du défaut d'effectif qui reste (§ 2.2). Pronostic :
  −10 à −4 % (27,6 M environ).
* **Médiane du revenu salarial des employés et des ouvriers** (contexte) : ECRT 2026,
  fiche « Revenu salarial », figure 3 (2023 : 17 270 et 19 300 €). Raison : elle dit où
  l'emploi discontinu manque. Pronostic : +9 à +15 %.

La proposition de l'étape « haut » (salaires des foyers de plus de 100 000 € de RFR,
contexte) tient ; son pronostic 2024 devient −38 à −30 % (98,0 contre 150,3 Md€).

### 4.3 Le pronostic, ligne par ligne

`docs/diagnostics/grille_ech_milieu.json` (commité) : `grille_ech.py` sur 15 000 ménages
(graine 20240101), les trois années, population de ce code ; « avant » est
`grille_ech_extrapolation.json`, la même grille avec le code de D-368. Le pronostic est
l'écart d'après élargi de 5 points pour les minima sociaux, les aides au logement et les
allocations familiales, 5 / 10 / 25 pour les tranches à 30 / 41 / 45 %, 4 pour l'IR, 0,5
pour les entreprises, 3 ailleurs. « h » : hors de la tolérance attendu ; « b » : au bord.
Écarts en %. **Pas aveugle.**

| ligne | tol. | avant 22 / 23 / 24 | après 22 / 23 / 24 | 2022 | 2023 | 2024 |
|---|---|---|---|---|---|---|
| `af_montant` | 25 | −15,3 / −15,0 / −13,7 | −15,3 / −15,0 / −13,7 | −20 à −10 | −20 à −10 | −19 à −9 |
| `aide_logement_montant` | 25 | −27,4 / −27,1 / −25,4 | −27,5 / −27,1 / −25,5 | −32 à −22 b | −32 à −22 b | −30 à −20 b |
| `bandeau_famille` | 15 | +28,4 / +26,0 / +25,2 | +28,6 / +26,3 / +25,5 | +26 à +32 h | +23 à +29 h | +23 à +29 h |
| `bandeau_maladie` | 15 | +23,3 / +21,6 / +21,1 | +23,7 / +22,0 / +21,5 | +21 à +27 h | +19 à +25 h | +18 à +24 h |
| `c3s` | 25 | +11,9 / +6,2 / +1,2 | +11,9 / +6,2 / +1,2 | +11,4 à +12,4 | +5,7 à +6,7 | +0,7 à +1,7 |
| `contribution_sociale_is` | 25 | −20,2 / +33,8 / +20,3 | −20,2 / +33,8 / +20,3 | −20,7 à −19,7 | +33,3 à +34,3 h | +19,8 à +20,8 |
| `cotisations_employeurs` | 15 | +26,7 / +25,6 / +23,5 | +26,7 / +25,6 / +23,6 | +24 à +30 h | +23 à +29 h | +21 à +27 h |
| `cotisations_employeurs_d121` | 15 | −0,5 / −1,5 / −3,2 | −0,5 / −1,4 / −3,1 | −3 à +3 | −4 à +2 | −6 à 0 |
| `cotisations_salariales` | 10 | −8,3 / −9,8 / −11,1 | −8,3 / −9,8 / −11,1 | −11 à −5 b | −13 à −7 b | −14 à −8 b |
| `csg_activite` | 15 | −6,4 / −6,3 / −6,9 | −6,4 / −6,3 / −6,9 | −9 à −3 | −9 à −3 | −10 à −4 |
| `csg_activite_avec_non_salaries` | 15 | −0,8 / −0,6 / −1,3 | −0,8 / −0,6 / −1,3 | −4 à +2 | −4 à +2 | −4 à +2 |
| `csg_remplacement` | 10 | −3,8 / −2,0 / −6,4 | −3,9 / −2,1 / −6,5 | −7 à −1 | −5 à +1 | −10 à −4 |
| `cvae` | 25 | — / — / −15,2 | — / — / −15,2 | — | — | −15,7 à −14,7 |
| `d9_d1` | 15 | −7,1 / −9,1 / −9,7 | −6,0 / −8,1 / −8,6 | −9 à −3 | −11 à −5 | −12 à −6 |
| `d9_d1_servi` | 15 | −2,0 / −4,4 / −4,9 | −0,9 / −3,3 / −3,5 | −4 à +2 | −6 à 0 | −7 à −1 |
| `foyers_fiscaux` | 10 | −5,0 / −6,1 / −7,1 | −5,0 / −6,1 / −7,1 | −8 à −2 | −9 à −3 | −10 à −4 b |
| `foyers_fiscaux_residents_hors_mayotte` | 10 | — / — / −6,2 | — / — / −6,2 | — | — | −9 à −3 |
| `foyers_imposes` | 10 | +15,3 / +12,6 / +7,5 | +10,0 / +7,4 / +2,6 | +7 à +13 b | +4 à +10 b | 0 à +6 |
| `foyers_tmi_0` | 15 | −10,1 / −10,9 / −9,0 | −6,6 / −7,4 / −5,6 | −10 à −4 | −10 à −4 | −9 à −3 |
| `foyers_tmi_1` | 15 | −10,0 / −11,4 / −12,7 | −7,8 / −9,1 / −10,4 | −11 à −5 | −12 à −6 | −13 à −7 |
| `foyers_tmi_2` | 15 | +24,1 / +23,3 / +16,1 | +10,7 / +10,0 / +3,7 | +6 à +16 b | +5 à +15 | −1 à +9 |
| `foyers_tmi_3` | 30 | −8,8 / −5,6 / −6,1 | −22,6 / −19,4 / −19,4 | −33 à −13 b | −29 à −9 | −29 à −9 |
| `foyers_tmi_4` | 30 | +42,8 / +56,1 / +54,9 | +24,2 / +32,4 / +34,7 | −1 à +49 b | +7 à +57 b | +10 à +60 b |
| `impots_salaires_calcules` | 20 | −3,6 / −3,6 / −4,0 | −3,7 / −3,6 / −4,0 | −7 à −1 | −7 à −1 | −7 à −1 |
| `impots_salaires_d291` | ctx | −69,3 / −69,6 / −69,7 | −69,3 / −69,6 / −69,7 | −72 à −66 | −73 à −67 | −73 à −67 |
| `ir_bareme` | 10 | — / +9,4 / +5,0 | — / −1,6 / −5,6 | — | −6 à +2 | −10 à −2 |
| `ir_net` | 15 | +17,1 / +19,6 / +15,4 | +5,2 / +7,4 / +3,9 | +1 à +9 | +3 à +11 | 0 à +8 |
| `is` | 20 | −19,7 / −0,8 / +2,0 | −19,7 / −0,8 / +2,0 | −20,2 à −19,2 b | −1,3 à −0,3 | +1,5 à +2,5 |
| `niveau_de_vie_median` | 15 | −5,3 / −6,5 / −7,7 | −4,9 / −6,1 / −7,3 | −8 à −2 | −9 à −3 | −10 à −4 |
| `niveau_de_vie_median_servi` | 15 | −5,7 / −6,9 / −8,1 | −5,2 / −6,5 / −7,6 | −8 à −2 | −9 à −3 | −11 à −5 |
| `pension_etat_d122` | ctx | −5,3 / −4,8 / −7,2 | −5,2 / −4,7 / −7,2 | −8 à −2 | −8 à −2 | −10 à −4 |
| `pensions_declarees` | ctx | +3,8 / +3,4 / — | +3,8 / +3,4 / — | +1 à +7 | 0 à +6 | — |
| `ppa_foyers` | 25 | +40,9 / +32,7 / +37,6 | +39,9 / +32,0 / +36,3 | +35 à +45 h | +27 à +37 h | +31 à +41 h |
| `ppa_foyers_servis` | 25 | −30,3 / −34,2 / −32,1 | −30,1 / −34,0 / −32,0 | −35 à −25 h | −39 à −29 h | −37 à −27 h |
| `ppa_montant` | 13 | −19,1 / −21,0 / −17,6 | −19,7 / −21,5 / −18,1 | −25 à −15 h | −27 à −17 h | −23 à −13 h |
| `ppa_montant_servi` | 13 | −27,5 / −29,1 / −26,1 | −27,3 / −29,0 / −25,9 | −32 à −22 h | −34 à −24 h | −31 à −21 h |
| `reduction_generale` | 15 | +15,4 / +12,0 / +14,0 | +14,6 / +11,2 / +13,1 | +12 à +18 b | +8 à +14 | +10 à +16 b |
| `revenus_non_salaries_hors_gerants` | 15 | +15,6 / +18,8 / +8,2 | +15,6 / +18,8 / +8,2 | +13 à +19 b | +16 à +22 h | +5 à +11 |
| `rsa_foyers` | 25 | — / +48,6 / +49,4 | — / +48,6 / +49,4 | — | +44 à +54 h | +44 à +54 h |
| `rsa_foyers_servis` | 25 | — / −2,0 / −1,7 | — / −3,2 / −2,9 | — | −8 à +2 | −8 à +2 |
| `rsa_montant` | 14 | +5,7 / +7,4 / +10,0 | +5,7 / +7,4 / +9,9 | +1 à +11 | +2 à +12 | +5 à +15 b |
| `rsa_montant_servi` | 14 | −1,8 / −0,2 / +2,1 | −3,0 / −1,4 / +0,9 | −8 à +2 | −6 à +4 | −4 à +6 |
| `salaires_declares` | 10 | −6,8 / −8,0 / −8,0 | −6,8 / −8,0 / −8,0 | −10 à −4 | −11 à −5 b | −11 à −5 b |

Au centre de l'échantillon : **81 lignes notées sur 113 dans leur tolérance** (71 avec le
code de D-368 sur le même échantillon ; la population entière en tenait 79 à D-369).
**Gagnées** : la tranche à 30 % les trois années, les foyers imposés de 2022 et 2023,
l'IR net les trois années, la tranche à 45 % de 2022 (les foyers imposés de 2022 au
bord, à +10,0 %). **Perdue** : aucune. **S'éloignent
sans sortir** : la tranche à 41 % (−6 à −19 %), l'IR au barème de 2024 (+5,0 à −5,6 %).

**Le biais de l'échantillon.** À D-369, la population entière mettait l'IR au barème de
2024 2 points sous l'échantillon (+3 contre +5) : l'IR au barème de 2024 tomberait vers
−7,5 %, dans la fourchette annoncée mais près de son bord bas ; la tranche à 41 % vers −18.

## 5. Ce que l'étape fait aux études

Ordres de grandeur, non mesurés sur les études :

* **Les réformes du barème** (PLF 2027 art. 2, la tranche à 30 %, Le Pen, Lisnard,
  Tondelier) : l'assiette imposable des salaires baisse de 6,85 %, l'impôt au barème de
  10 %. Une indexation coûte environ 8 à 10 % de moins ; une réforme de la tranche à 30 %
  touche 11 % de foyers de moins ; celles du haut (41 et 45 %, plafond du quotient) 13 à
  14 % de base en moins.
* **Les réformes des salaires** (Attal, Retailleau, CSG) : le retour par l'IR, non porté
  par l'extrapolation, baisse d'environ 10 % ; le coût d'Attal (60,9 Md€, retour de
  13,8 Md€ par l'IR) monterait de 1 à 1,5 Md€. Cotisations, CSG et allègements : < 1 %.
* **Les prestations** (prime, RSA, aides au logement, AF) : moins de 1 %.
* **Les déciles** : niveau de vie médian +0,5 %, D9/D1 +1,3 %.

## 6. Ce qui reste, les doutes, la décision

* **La décision.** Le correctif complète D-368 : la masse et l'assiette déclarée sont
  ramenées au champ de l'enquête par le même rapport. Il en suit que l'IR, que D-368 ne
  porte pas, compte les salariés de l'enquête seulement, et se compare à un total qui
  compte tous ceux de la France : la ligne de l'IR au barème passe sous le publié de
  l'ordre de leur part. Si le coordinateur préfère garder l'IR au barème au-dessus de 0,
  `PART_EXONEREE_SUR_LE_CHAMP = False` refait D-368 ; l'autre voie, cohérente aussi, est de
  porter l'IR des salariés absents (une décision du propriétaire, comme D-368).
* **La part est commune** (hypothèse de l'étape « ir ») : les heures supplémentaires
  exonérées (21,8 Md€ déclarés, 12,4 M de personnes) vont au milieu, l'épargne salariale
  plus haut, les apprentis en bas ; aucune clé publiée. Une part commune retire autant au
  haut qu'au milieu : c'est pourquoi la tranche à 41 % recule. Une clé publiée par PCS
  des heures supplémentaires (Dares) la placerait mieux ; non trouvée dans le manifeste.
* **Le rapport des effectifs** suppose les absents semblables aux présents (D-368). Plus
  bas payés (§ 2.2), leur part des salaires déclarés est plus petite que 7 % : la part
  exonérée est peut-être un peu forte.
* **L'emploi discontinu** reste trop court (volume 0,844 contre 0,77) : le reste de l'excès
  des employés et ouvriers, et le manque de petits salaires (§ 2.6). Non corrigeable sans
  la distribution des durées d'emploi (panel Tous salariés).
* **Les foyers manquants, les charges déductibles, le capital** : § 2.6.
* **Sources** lues : IRCOM 2025 (`national.xls`, converti par LibreOffice), DGFiP taux
  marginaux 2019-2024, export 2042, DGFiP n° 41 (tableaux 2 et 3), IP n° 2079, ECRT 2026
  fiche « Revenu salarial ». Non trouvées : la corrélation des salaires dans le couple, la
  part exonérée par décile, les heures supplémentaires par PCS, les parts par taux
  marginal.

## 7. Les tests lancés

```
PYTHONPATH=src .venv/bin/python -m pytest -m "not lourd and not chrono" -n 2 \
  tests/test_salaires_haut.py tests/test_non_salaries.py tests/test_salaires_exoneres.py \
  tests/test_population.py tests/test_emploi_discontinu.py tests/test_foyers_fiscaux.py
140 passed in 118.07s
# test_the_published_quantiles_are_held_in_eqtp, RANG_EQTP éteint (le code d'avant) :
3 failed (quartile +1,4 %, médiane +2,7 %, P80 +3,6 % au-dessus du publié)
# test_the_exempt_share_makes_the_declared_salaries, incomes.py d'avant (git stash) :
1 failed (salaires déclarés de la fixture 7,2 % au-dessus de la cible du champ)
ruff check (fichiers touchés) : propre
```

Non lancés : la suite entière, `make impact`, les lourds, la grille entière, les études.
