# Étape « alleg » du but 19 : la règle des allègements et leur câblage

Agent `alleg`, 10 novembre 2026, worktree `Impots-but19-alleg`, branche
`claude/but19-alleg` partie de 42db106 (`claude/but19`, D-369). Aucune D-entrée, aucune
ligne ni tolérance de `docs/verification/lignes.json` touchée. Ni `incomes.py` ni
`calibrate.py` : la distribution des salaires est le terrain d'un autre agent.

## 0. En une phrase

Les allègements étaient trop hauts (réduction générale +14 %, bandeau maladie +22 %,
bandeau famille +27 % à D-369) pour trois défauts de règle, tous corrigés ici : le temps
partiel n'était pas câblé (un mi-temps payé deux SMIC de l'heure était lu au SMIC, avec
toute la réduction générale, 7,1 Md€), les gérants majoritaires et les salariés des
particuliers employeurs recevaient des allègements que la loi ne leur donne pas (1,8 et
2,7 Md€), et les personnes sorties d'emploi payées au taux d'un donneur n'en avaient pas
la quotité (0,7 Md€). Après correction, sur 15 000 ménages : réduction générale −17 %,
bandeau maladie +12 %, bandeau famille +18 %. **La réduction générale passe sous la
tolérance de l'autre côté** ; avec les bandeaux encore trop hauts, cela dit que la
distribution des salaires horaires du privé a trop peu de masse sous 1,6 SMIC et trop
entre 1,6 et 3,5 SMIC : un défaut de distribution, plus de règle (§ 5).

## 1. Ce qui a changé, fichier par fichier

* **`src/impots/engine/corrections.py`** — correction 26, sur le modèle des corrections
  24 et 25 (une entrée qu'openfisca n'a pas) : une variable de projet
  `exclu_allegements` (individu, mois, fausse par défaut) et `assiette_allegement`
  enveloppée, nulle pour une personne exclue. L'assiette nulle annule la réduction
  générale et les deux bandeaux (et les exonérations ciblées, qui ne s'appliquent pas
  non plus). Les cotisations du gérant restent celles d'un salarié (biais de l'étape
  « ir », non traité ici, § 5).
* **`src/impots/population/to_openfisca.py`** — deux fonctions et leur écriture, mois par
  mois, sur les trois années d'historique :
  * `working_time` : un salarié payé dont `quotite_travail` est sous 1 part en
    `contrat_de_travail = temps_partiel`, `heures_remunerees_volume` = quotité × durée
    légale du mois (151,67 h). openfisca proratise alors le SMIC de la réduction générale
    et des bandeaux (`coefficient_proratisation`, CSS art. D. 241-7, I) et le plafond de
    la sécurité sociale (BOSS, assiette, § 810). Avant : tout le monde à temps plein.
  * `excluded_from_allegements` : les gérants majoritaires (`regime_non_salarie`
    `gerant_bic`/`gerant_bnc`) et les salariés d'un particulier employeur.
  * `WIRING` passe à `D-346_ns_ir_md_al` : les caches d'avant ne sont plus servis.
* **`src/impots/population/skeleton.py`** — la colonne `particulier_employeur`, lue sur
  `CHPUB` = 7 (« un particulier ») de l'enquête Emploi, pour un salarié ; lue absente d'un
  cadre fait à la main (comme ANCEMPL4).
* **`src/impots/population/build.py`** — `particulier_employeur` dans le schéma.
* **`src/impots/population/emploi_discontinu.py`** — la personne sans emploi payée au
  taux mensuel de son donneur prend aussi sa quotité (déjà tirée, `_tirages_et_quotite`,
  mais gardée locale) et son type d'employeur. Aucun tirage ne change.
* **`tests/test_allegements.py`** (neuf, 4 tests) et un test dans
  `tests/test_emploi_discontinu.py` (§ 6).
* **`docs/diagnostics/grille_ech_alleg.json`** : la grille sur 15 000 ménages, ce code.
  **`docs/diagnostics/pronostic_alleg_projet.json`** : le pronostic proposé (§ 3).

**La population reconstruite** (`impots population build`, graine 20240101, sur les
copies réelles du worktree) : toutes les colonnes de la population de D-368 sont
identiques à l'octet, sauf `quotite_travail` sur 4 237 lignes (les sortants payés, 0,73 M
de personnes pondérées passent sous 1) et la colonne neuve `particulier_employeur`
(0,83 M de personnes payées, 15,5 Md€ de salaires bruts). Le facteur des mois travaillés
reste 0,9999968. `aggregate.py` et `runner.py` n'ont pas eu à changer : la mesure des
allègements y était juste, c'est la règle en amont qui ne l'était pas.

## 2. Les mesures, avant et après

**Comment.** Échantillon de 15 000 ménages (`runner.subsample`, graine 20240101), droit
2024 sauf mention, montants portés par l'extrapolation de D-368 (× 1,0747 hors gérants),
comme la grille. « Avant » : le code de 42db106 sur la population de D-368 ; « après » :
ce code sur la population reconstruite. Scripts hors dépôt (`decomp.py`, `etapes.py`,
`etudes.py`, `table.py` dans le scratchpad de la session). **Ces mesures ne sont pas
aveugles** : elles ont été faites avec le code et servent au pronostic.

### 2.1 Les marches de l'écart, une correction à la fois (2024, Md€)

| marche | réd. générale | bandeau maladie | bandeau famille |
|---|---:|---:|---:|
| avant (D-369 sur l'échantillon) | 44,74 | 32,07 | 12,03 |
| gérants majoritaires exclus | −1,78 | −0,87 | −0,34 |
| salariés des particuliers employeurs exclus | −2,66 | −0,93 | −0,29 |
| temps partiel des occupés câblé | −7,07 | −0,55 | −0,06 |
| quotité du donneur pour les sortants | −0,65 | −0,02 | −0,00 |
| **après** | **32,58** | **29,70** | **11,34** |
| publié (CCSS juin 2025, fiche 1.6, tableau 2) | 39,35 | 26,44 | 9,59 |
| écart avant → après | +13,7 % → −17,2 % | +21,3 % → +12,3 % | +25,4 % → +18,2 % |

La première ligne refait exactement la mesure d'avant (ce code, la population neuve
remise à temps plein, sans exclusion) : les marches sont propres.

### 2.2 Par catégorie de salarié, et ce que la loi leur donne (2024, Md€)

| catégorie | M pers. | brut | RG avant → après | BM | BF | la loi |
|---|---:|---:|---|---|---|---|
| privé occupé | 18,5 | 782 | 39,2 → 29,8 | 29,5 → 28,1 | 11,1 → 10,8 | oui, proratisé |
| privé sorti dans l'année | 2,6 | 35 | 3,8 → 2,8 | 1,8 → 1,6 | 0,6 → 0,6 | oui, proratisé |
| salarié d'un particulier | 0,8 | 16 | 2,7 → 0 | 0,9 → 0 | 0,3 → 0 | non (L. 241-13, II) |
| gérant majoritaire | 0,8 | 35 | 1,8 → 0 | 0,9 → 0 | 0,3 → 0 | non (non salarié) |
| contractuel public | 1,0 | 32 | 0 | 0 | 0 | non, sauf EPIC |
| titulaire | 4,8 | 178 | 0 | 0 | 0 | non |

Les avant de « salarié d'un particulier » sont lus sur la marche 2.1 (ils étaient dans le
privé). Ce que dit la loi, catégorie par catégorie :

* **Privé** : la réduction générale (CSS art. L. 241-13) sous 1,6 SMIC, les bandeaux
  maladie (L. 241-2-1) et famille (L. 241-6-1) sous 2,5 et 3,5 SMIC (en 2024 : le plus
  favorable de 2 et 3,5 SMIC courants et de 2,5 et 3,5 SMIC du 31 décembre 2023, ce que
  lit openfisca, `plafond_smic_2023_12_31`). Le SMIC de comparaison est proratisé à la
  durée du contrat, hors heures supplémentaires et complémentaires (D. 241-7, I) : à
  raison depuis cette étape.
* **Apprentis** : la réduction générale s'applique depuis 2019. L'enquête ne les sépare
  que dans « alternance, stage » (STATUTDET 24, 0,98 M), que la population ne garde pas ;
  ils sont traités comme le privé, ce qui est la loi pour l'apprenti. openfisca multiplie
  la réduction par `not_(apprenti)` sur toutes les années, ce qui serait faux depuis
  2019, mais `apprenti` n'est jamais posé : sans effet ici, à signaler en amont.
* **Contractuels publics et titulaires** : rien (D-346), à raison : l'État, les
  collectivités et les hôpitaux ne sont ni dans L. 5422-13 ni dans le 3° de L. 5424-1.
* **Gérants majoritaires** : affiliés aux non-salariés, hors du régime général ; aucun
  allègement. À tort avant, à raison après.
* **Particuliers employeurs** : exclus de la réduction générale par le II de L. 241-13,
  et des bandeaux par le renvoi de L. 241-2-1 et L. 241-6-1 au champ de ce II (lecture
  du texte ; la déduction forfaitaire par heure qui leur est propre n'est pas une ligne
  de la grille). À tort avant, à raison après.
* **Régimes spéciaux** (SNCF, RATP, IEG, Banque de France…) : leurs statutaires ne sont
  pas dans le champ (auto-assurance chômage, maladie hors régime général pour certains).
  L'enquête ne les distingue pas (CHPUB 2, « entreprise publique », 1,09 M, mêle La
  Poste et les salariés de droit privé) : **non corrigé**. Ordre de grandeur, hypothèse :
  0,35 M de statutaires, presque tous au-dessus de 1,6 SMIC, 0,3 à 0,8 Md€ de bandeaux.
* **Les DOM** : la Lodeom y remplace la réduction générale pour la plupart des
  employeurs, et la CCSS la compte à part. Le modèle donne la réduction générale :
  **non corrigé**, quelques points de la ligne au plus (hypothèse, non mesuré).

### 2.3 Par tranche de salaire en SMIC et par temps de travail (privé, 2024, Md€)

Tranche « de la loi » : brut annuel ÷ (SMIC mensuel × mois payés × quotité), avec un
SMIC moyen indicatif (1 766,92 €) ; RG = réduction générale, BM, BF = bandeaux.

| tranche | temps | M pers. | RG avant → après | BM avant → après | BF avant → après |
|---|---|---:|---|---|---|
| < 1,6 | plein | 8,6 | 30,2 → 28,2 | 13,5 → 12,9 | 4,1 → 3,9 |
| < 1,6 | partiel | 2,2 | 9,5 → 4,3 | 2,0 → 1,9 | 0,6 → 0,6 |
| 1,6 à 2,5 | plein | 5,6 | 0,0 → 0,0 | 13,8 → 13,6 | 4,2 → 4,2 |
| 1,6 à 2,5 | partiel | 0,9 | 3,0 → 0 | 1,3 → 1,3 | 0,4 → 0,4 |
| 2,5 à 3,5 | partiel | 0,3 | 0,3 → 0 | 0,5 → 0 | 0,2 → 0,2 |
| > 3,5 | partiel | 0,1 | 0,0 → 0 | 0,1 → 0 | 0,1 → 0 |

(Les avant comptent encore les salariés des particuliers et les sortants à quotité 1 ;
les plein temps des tranches 2,5 et plus n'ont pas bougé.) Avant, 3,3 Md€ de réduction
générale allaient à des temps partiels payés plus de 1,6 SMIC de l'heure, et la loi ne
leur en donne aucune.

### 2.4 La proratisation et le SMIC de référence, vérifiés

* **Le SMIC du mois.** openfisca lit `smic_b_horaire` mois par mois (2024 : 11,65 € de
  janvier à octobre, 11,88 € en novembre et décembre ; 2023 : 11,27 puis 11,52 ; 2022 :
  10,57, 10,85, 11,07) × 151,67 h × `coefficient_proratisation`. Relu dans les paramètres
  du système corrigé.
* **Le temps partiel** : `coefficient_proratisation` = heures payées ÷ durée légale ;
  avant l'étape, 1 pour tous, `quotite_travail` n'entrait pas dans la simulation.
* **L'emploi discontinu (D-368).** Les trois allègements sont en recouvrement
  « progressif » par défaut : le montant de l'année est la somme de leur calcul mois par
  mois (`compute_allegement_progressif`). Un salarié payé six mois a son salaire sur ses
  six mois, chaque mois comparé au SMIC du mois ; les mois sans paie ont une assiette
  nulle et ne donnent rien. Son SMIC de référence est donc celui de ses six mois, comme
  le veut D. 241-7 (SMIC « corrigé à proportion de la durée de travail […] au titre de
  la période où ils sont présents dans l'entreprise ») : **juste, avant comme après**
  (test `test_an_employee_paid_six_months_has_the_smic_of_six_months`, qui tenait déjà).
  Une paie constante dans les mois payés est une hypothèse du câblage (D-368) ; la loi
  annualise, ce qui donne le même montant à paie constante.
* **Les heures supplémentaires** ne sont pas séparées : elles sont dans le brut tiré et
  le SMIC n'en est pas majoré, ce qui est la règle (D. 241-7). Aucune variable ne les
  porte : rien à corriger, rien à mesurer.
* **L'effectif de l'entreprise** reste 0 : le coefficient des moins de 50 salariés
  (0,3194 en 2024, 0,3234 au-delà) pour tous ; la réduction générale serait de 0,5 à
  1 % plus haute avec les effectifs (hypothèse : 55 à 60 % des salariés au-delà de 50).

### 2.5 La grille sur 15 000 ménages, avant et après (écart au publié, %)

Seules les lignes qui bougent de plus de 0,05 point. Toutes les autres sont identiques.

| ligne | 2022 | 2023 | 2024 |
|---|---|---|---|
| `reduction_generale` (tol. 15) | +15,4 → −16,1 | +12,0 → −17,9 | +14,0 → −16,9 |
| `bandeau_maladie` (15) | +23,3 → +14,3 | +21,6 → +12,8 | +21,1 → +12,2 |
| `bandeau_famille` (15) | +28,4 → +20,9 | +26,0 → +18,6 | +25,2 → +18,0 |
| `cotisations_employeurs_d121` (15) | −0,5 → +4,2 | −1,5 → +3,2 | −3,2 → +1,4 |
| `cotisations_employeurs` (15, mesure de D-363) | +26,7 → +31,4 | +25,6 → +30,3 | +23,5 → +28,1 |
| `cotisations_salariales` (10) | −8,3 → −8,4 | −9,8 → −9,8 | −11,1 → −11,2 |

En niveau (2024, Md€) : réduction générale 44,85 → 32,71 ; bandeaux 32,03 → 29,67 et
12,01 → 11,32 ; D121 318,9 → 334,0 (329,3 publié) ; cotisations salariales 120,35 →
120,28 (−0,06 %, le plafond de la sécurité sociale proratisé des temps partiels : moins
de vieillesse plafonnée, plus de tranche 2) ; prélèvements D291 −0,05 % (AGS et Fnal
plafonnés).

**Ce qui ne bouge pas à tort.** L'IR avant niches +0,02 % (le net imposable des temps
partiels au-dessus du plafond proratisé), la prime d'activité −0,01 %, les allocations
familiales −0,004 %, le RSA, les aides au logement, la CSG (+0,002 %) et les niveaux de
vie à moins de 0,01 %. Rien d'autre que le plafond proratisé ne passe du côté des
ménages : l'assiette des allègements n'entre dans aucun revenu.

**Le compte** : 71 lignes sur 113 tenues avant, 72 après, sur l'échantillon. Gagnées :
le bandeau maladie des trois années. Perdues : la réduction générale de 2023 et 2024,
de l'autre côté. Le bandeau famille reste dehors.

## 3. Le préenregistrement proposé

**Aucune ligne neuve, aucune marge neuve, aucune tolérance.** Une source manque pour
dire où est la masse : la distribution des salaires horaires du privé en parts de SMIC
(Dares sur la base Tous salariés 2022, graphique 3.6 du rapport Bozio-Wasmer 2024, déjà
dans `data/raw`) ; le graphique n'a pas de données lisibles dans le conteneur (non
relevée). Si elle se trouve en tableau, une ligne « part des salariés du privé sous 1,6
SMIC horaire » serait la mesure directe de ce qui reste (§ 5) ; à proposer avec sa source.

**Le pronostic**, ligne par ligne, dans `docs/diagnostics/pronostic_alleg_projet.json`.
Centre = écart de la population entière à D-369 (`reports/verification/grille.json`,
commit 114f885) plus le déplacement mesuré sur 15 000 ménages entre avant et après ;
fourchette = centre ± la marge de D-368 (5 points minima sociaux, aides au logement,
AF ; 5, 10, 25 pour les tranches à 30, 41, 45 % ; 4 pour l'IR ; 0,5 entreprises ;
3 ailleurs). Il annonce **80 lignes sur 113** dans leur tolérance (79 à D-369). Pas
aveugle. « h » : hors de la tolérance attendu.

| ligne | tol. | marge | 2022 | 2023 | 2024 |
|---|---|---|---|---|---|
| `cotisations_salariales` | 10 | 3 | −11 à −5 | −13 à −7 | −14 à −8 h |
| `cotisations_employeurs` | 15 | 3 | +28 à +34 h | +27 à +33 h | +25 à +31 h |
| `reduction_generale` | 15 | 3 | −19 à −13 h | −20 à −14 h | −19 à −13 h |
| `bandeau_maladie` | 15 | 3 | +12 à +18 | +10 à +16 | +9 à +15 |
| `bandeau_famille` | 15 | 3 | +18 à +24 h | +16 à +22 h | +16 à +22 h |
| `csg_activite` | 15 | 3 | −10 à −4 | −9 à −3 | −10 à −4 |
| `csg_remplacement` | 10 | 3 | −6 à +0 | −4 à +2 | −8 à −2 |
| `foyers_fiscaux` | 10 | 3 | −8 à −2 | −9 à −3 | −10 à −4 |
| `foyers_imposes` | 10 | 3 | +12 à +18 h | +9 à +15 h | +4 à +10 |
| `foyers_tmi_0` | 15 | 3 | −13 à −7 | −14 à −8 | −12 à −6 |
| `foyers_tmi_1` | 15 | 3 | −13 à −7 | −14 à −8 | −15 à −9 |
| `foyers_tmi_2` | 15 | 5 | +19 à +29 h | +18 à +28 h | +11 à +21 h |
| `foyers_tmi_3` | 30 | 10 | −17 à +3 | −13 à +7 | −15 à +5 |
| `foyers_tmi_4` | 30 | 25 | −21 à +29 | −12 à +38 | −10 à +40 |
| `salaires_declares` | 10 | 3 | −10 à −4 | −11 à −5 | −11 à −5 |
| `niveau_de_vie_median` | 15 | 3 | −8 à −2 | −9 à −3 | −10 à −4 |
| `d9_d1` | 15 | 3 | −10 à −4 | −13 à −7 | −13 à −7 |
| `rsa_montant` | 14 | 5 | +3 à +13 | +5 à +15 | +7 à +17 |
| `ppa_montant` | 13 | 5 | −26 à −16 h | −28 à −18 h | −25 à −15 h |
| `aide_logement_montant` | 25 | 5 | −34 à −24 h | −33 à −23 h | −32 à −22 h |
| `af_montant` | 25 | 5 | −20 à −10 | −20 à −10 | −19 à −9 |
| `ppa_foyers` | 25 | 5 | +33 à +43 h | +26 à +36 h | +30 à +40 h |
| `is` | 20 | 0,5 | −20 à −19 | −1 à −0 | +1 à +2 |
| `contribution_sociale_is` | 25 | 0,5 | −21 à −20 | +33 à +34 h | +20 à +21 |
| `c3s` | 25 | 0,5 | +11 à +12 | +6 à +7 | +1 à +2 |
| `ir_bareme` | 10 | 4 | — | +1 à +9 | −3 à +5 |
| `rsa_foyers` | 25 | 5 | — | +47 à +57 h | +48 à +58 h |
| `cvae` | 25 | 0,5 | — | — | −16 à −15 |
| `cotisations_employeurs_d121` | 15 | 3 | +1 à +7 | +0 à +6 | −2 à +4 |
| `csg_activite_avec_non_salaries` | 15 | 3 | −5 à +1 | −4 à +2 | −5 à +1 |
| `d9_d1_servi` | 15 | 3 | −5 à +1 | −7 à −1 | −8 à −2 |
| `foyers_fiscaux_residents_hors_mayotte` | 10 | 3 | — | — | −9 à −3 |
| `impots_salaires_calcules` | 20 | 3 | −7 à −1 | −6 à −0 | −7 à −1 |
| `ir_net` | 15 | 4 | +8 à +16 | +10 à +18 | +6 à +14 |
| `niveau_de_vie_median_servi` | 15 | 3 | −8 à −2 | −10 à −4 | −11 à −5 |
| `ppa_foyers_servis` | 25 | 5 | −36 à −26 h | −40 à −30 h | −38 à −28 h |
| `ppa_montant_servi` | 13 | 5 | −34 à −24 h | −35 à −25 h | −32 à −22 h |
| `revenus_non_salaries_hors_gerants` | 15 | 3 | +1 à +7 | +3 à +9 | −6 à +0 |
| `rsa_foyers_servis` | 25 | 5 | — | −6 à +4 | −5 à +5 |
| `rsa_montant_servi` | 14 | 5 | −6 à +4 | −4 à +6 | −2 à +8 |

Pourquoi ce centre plutôt que l'écart brut de l'échantillon (aussi dans le fichier) :
l'échantillon de 15 000 ménages s'écarte de la population entière de plusieurs points sur
des lignes que l'étape ne touche pas (foyers à 45 % : +55 % contre +11 % ; IR net : +15
contre +12) ; seul le déplacement vient de l'étape. La marge de 3 points des allègements
couvre l'écart d'échantillonnage vu à D-368 (réduction générale 2022 : +16,0 sur 20 000
ménages, +14 sur la population). Si le propriétaire préfère la méthode de D-368 (centre =
échantillon), le compte annoncé est 72 sur 113.

## 4. Ce que l'étape fait aux études

Coût mécanique, droit 2026, population vieillie de 2024 à 2026 par le jeu `plf2027`,
15 000 ménages, avant → après (Md€ ; un coût négatif est une recette) :

* **Mélenchon** (réduction générale arrêtée à 2 SMIC) : −6,58 → −6,51, soit **−1,1 %** de
  rendement. Trois effets de sens contraires : les gérants et les salariés des
  particuliers au-delà de 2 SMIC n'ont plus de réduction à perdre (le rendement baisse) ;
  les temps partiels payés 2 à 3 SMIC de l'heure, lus jusqu'ici sous 2 SMIC, en perdent
  une (il monte). Le canal d'emploi C2 lit les mêmes personnes : il bouge dans le même
  sens, non mesuré ici.
* **Attal** (cotisations salariales de retraite × 0,22) : 63,00 → 62,94, −0,1 % ; le
  plafond proratisé des temps partiels réduit un peu l'assiette plafonnée.
* **Retailleau** (même bouton × 0,87) : 10,554 → 10,545, −0,1 %.
* **Les autres** (barème, pensions, TVA, accises, prime et APL du PLFSS) ne lisent ni
  l'assiette des allègements ni le plafond : inchangées à moins de 0,05 % (IR +0,02 %).

## 5. Ce qui reste, les doutes, les sources

* **La réduction générale passe à −17 %.** La règle est maintenant celle de la loi pour
  tout ce que la population sait dire. Ce qui reste est la forme des salaires horaires
  du privé : il manque de la masse sous 1,6 SMIC (la réduction générale publiée suppose
  environ 7 Md€ de plus) et il y en a trop sous 2,5 et 3,5 SMIC (bandeaux : environ 54 et
  97 Md€ d'assiette de trop). Deux pistes pour l'agent des salaires, hypothèses, non
  mesurées : (i) le salaire horaire d'un temps partiel est tiré comme celui d'un temps
  plein du même âge, sexe et groupe, quand les temps partiels sont plus souvent près du
  SMIC (rapport Bozio-Wasmer 2024, ch. 3) ; (ii) les quantiles publiés en EQTP pèsent
  chaque poste par son volume de travail, la population chaque personne par son poids.
* **Le facteur d'extrapolation (1,0747)** porte les allègements de tous les présents ;
  si les absents de l'enquête sont moins payés (D-368 le dit plausible), la réduction
  générale serait sous-estimée et les bandeaux sur-estimés par le même facteur : sens
  compatible avec ce qui reste. Hypothèse.
* **Les gérants** gardent des cotisations de salarié et d'employeur au régime général
  (3,6 Md€ de cotisations salariales, étape « ir ») au lieu de celles de la SSI : les
  retirer ferait baisser la ligne D121 d'environ 2 à 3 points et les cotisations
  salariales de 3 points (hypothèse d'ordre de grandeur). Hors du champ de l'étape.
* **Non corrigés, faute de variable** : les statutaires des régimes spéciaux, la Lodeom
  dans les DOM, l'effectif de l'entreprise (§ 2.2 et 2.4). Les deux premiers font
  baisser les allègements, le troisième monter la réduction générale.
* **Le renvoi des bandeaux au champ du II de L. 241-13** pour les particuliers employeurs
  est ma lecture du texte ; je n'ai pas relu le BOSS dans le conteneur. Si les bandeaux
  leur étaient dus, ils remonteraient de 0,93 et 0,29 Md€ (§ 2.1).
* **Le salarié d'un particulier** est repéré par l'employeur de son emploi principal
  (CHPUB) ; un second emploi chez un particulier, ou un premier chez un particulier et
  un second en entreprise, n'est pas vu. La personne sortie d'emploi prend le type
  d'employeur de son donneur (hypothèse, comme sa quotité).
* **Sources non lues dans le conteneur** : les données du graphique 3.6 de Bozio-Wasmer
  (distribution horaire en parts de SMIC) ; la répartition des allègements par tranche de
  salaire de l'Urssaf (non trouvée).

## 6. Les tests

Tests neufs, vus échouer sur le code d'avant (code de `src` remis à 42db106, tests
gardés) :

* `tests/test_allegements.py` : le mi-temps à deux SMIC de l'heure n'a pas de réduction
  générale et a les deux bandeaux (avant : 6 772 € de réduction générale) ; le 40 % à
  trois SMIC de l'heure perd la réduction générale et le bandeau maladie (avant : 4 574 €
  de réduction générale) ; le gérant et le
  salarié d'un particulier n'ont aucun allègement (avant : 6 772 € de réduction
  générale) ; le salarié payé six mois a le SMIC de six mois (tenait déjà, dit dans le
  test). Avant : 3 échecs, 1 réussite ; après : 4 réussites.
* `tests/test_emploi_discontinu.py::test_a_leaver_works_at_his_donor_s_quotite` : avant,
  la quotité des sortants restait 1 (échec) ; après, celle du donneur.

Lancés pendant le développement (`pytest -m "not lourd and not chrono" -n 2`) :
`test_allegements`, `test_emploi_discontinu`, `test_secteur_public`, `test_population`,
`test_salaires_exoneres`, `test_logement`, `test_non_salaries`, `test_extrapolation`,
`test_engine`, `test_ij`, `test_ij_moteur` : 548 réussis, 1 échec,
`test_population::test_case_t_follows_the_couple_not_the_dwelling`, dont le cadre
d'enquête fait à la main n'a pas `CHPUB` ; le squelette lit maintenant la colonne absente
comme les autres variables optionnelles (ANCEMPL4), sans toucher au test : 5 réussis sur
la relance du fichier ciblé. Ni `make impact` ni les lourds.
