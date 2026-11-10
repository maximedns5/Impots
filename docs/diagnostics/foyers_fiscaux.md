# Diagnostic : les foyers fiscaux (`foyers_fiscaux`)

*Rédigé le 10 novembre 2026 sur la branche claude/but19, sans rien modifier au dépôt. Les
scripts d'essai sont dans `/tmp/diag_foyers_fiscaux/` (`compte.py`, `m2.py`, `eec.py`,
`pop2.py`, `pop3.py`, `passe.py`, `tab.py`, `dec.py`, `cal.py`, `art2.py`). Les comptes
viennent du parquet de la population (`data/processed/population_2024.parquet`, toute la
population, sans passe) ; les revenus fiscaux, parts et taux marginaux viennent d'une
passe d'essai sur un échantillon de 20 000 ménages (`runner.subsample`, graine fixe,
poids redressés au total), dite « sur échantillon » chaque fois.*

## 1. L'écart, en une phrase

Le modèle compte **35,34 M de foyers fiscaux** chaque année, contre 40,75 M (revenus
2022), 41,21 M (2023) et 41,64 M (2024) dans l'IRCOM de la DGFiP, soit −13,3 %, −14,3 %
et −15,1 % (biais moyen −14,2 %, 0 année sur 3 dans ±10 %) ; il en manque 6,3 M en 2024,
presque tous non imposés ou dans la tranche à 11 % (−1,8 M à 0 %, −4,8 M à 11 %), tandis
que les tranches à 30 et 41 % sont en excès (+5 à +12 %, +15 à +19 %).

## 2. Ce que le modèle fait

La chaîne, du fichier à la variable :

1. **L'enquête Emploi 2024** (`data/raw/FD_EEC_2024.parquet`, lue par
   `src/impots/population/ingest.py:170`, `load_eec`) : 353 420 lignes de personnes de 15
   ans ou plus, en **ménages ordinaires**, France hors Mayotte. Une ligne par personne et
   par trimestre ; chaque couple (`IDENT`, `TRIM`) devient un ménage (199 451 ménages).
   L'EEC ne dit **ni l'état matrimonial légal, ni le lien de parenté, ni l'âge exact** :
   seulement `COUPL_LOG` (« en couple avec quelqu'un vivant dans le logement »),
   `TYPLOG5` (la configuration du logement) et `AGE6` (cinq tranches d'âge).
2. **Les rôles** (`src/impots/population/skeleton.py:177`, `_observed_persons`) : la
   personne de référence est le plus petit `NOI` ; le conjoint est l'autre personne
   `COUPL_LOG = 1` d'un logement typé couple qui en compte exactement deux
   (`skeleton.py:216-221`). **Tout couple cohabitant ainsi apparié devient un seul foyer
   fiscal, marié, pacsé ou non** : rien ne distingue les concubins.
3. **L'âge exact** est tiré uniformément dans la tranche (`skeleton.py:271`,
   `_draw_ages`) : 15-24 ans, 25-49 ans, etc.
4. **Les personnes à charge** (`skeleton.py:230-268`, `_classify_dependants`) : dans un
   logement typé « avec enfant », toute autre personne de moins de 21 ans, ou de moins de
   25 ans et sans emploi (`skeleton.py:238-240`, constantes `skeleton.py:149-150`), est
   **rattachée** au foyer des parents. Les moins de 15 ans sont synthétisés
   (`skeleton.py:374`, `_synthesise_children`).
5. **Les unités** (`skeleton.py:464-540`, `_assign_units`) : l'unité 0 est la personne
   de référence, son conjoint et les enfants rattachés ; **chaque autre adulte est un
   foyer à lui seul** (`skeleton.py:475`). Le même identifiant sert au foyer fiscal et à
   la famille CAF (`skeleton.py:507-508`). La case T est posée sur un déclarant seul avec
   personne à charge et sans couple observé (`skeleton.py:526-538`).
6. **Les poids** : `EXTRIAN` de l'Insee, puis un ratissage des ménages sur leur type
   (recensement 2023) et des personnes de 15 ans ou plus sur âge × sexe
   (`src/impots/population/build.py:102-116`, `calibrate.standard_margins`). **Aucune
   marge ne porte sur les foyers fiscaux.** Les revenus sont attachés ensuite
   (`build.py:116`), masses salariales et de pensions calées sur leurs totaux.
7. **OpenFisca** : une entité `foyer_fiscal` par `foyer_id`
   (`src/impots/population/to_openfisca.py:369`, rôles `to_openfisca.py:118`).
8. **Le compte** : `n_foyers` somme 1 par foyer, au poids moyen du ménage
   (`src/impots/population/runner.py:268-281`, avec `n_foyers_imposes` et
   `n_foyers_tmi_k` lus sur `ir_tranche`) ; la grille le lit dans
   `src/impots/verification.py:69`. La structure est celle de 2024 ramenée aux autres
   années par les indices de revenus : **le nombre de foyers ne bouge pas d'une année à
   l'autre** (35 335 186 les trois années).

Ce que cela donne, mesuré sur le parquet entier (poids du ménage) :

| | modèle |
|---|---:|
| personnes (enfants synthétisés compris) | 67,42 M |
| ménages | 31,01 M |
| foyers fiscaux | 35,34 M |
| dont foyers de couple (déclarant + conjoint) | 14,86 M |
| dont foyers d'une personne seule | 20,47 M |
| dont foyers avec case T | 2,79 M |
| foyers sans salaire, pension ni chômage | 4,05 M |
| personnes à charge | 17,23 M |
| dont majeures (18 ans ou plus) | 3,44 M |
| déclarants de moins de 18 ans (âge tiré) | 0,53 M |
| foyers des DOM (hors Mayotte) | 1,22 M |
| ménages à 1 / 2 / 3 foyers ou plus | 27,95 / 2,19 / 0,87 M |

Par âge du déclarant principal (âge tiré dans la tranche de l'EEC, donc indicatif à
l'intérieur de 15-24 et de 25-49 ans) :

| âge | foyers | dont couples | dont sans revenu |
|---|---:|---:|---:|
| moins de 18 | 0,53 M | 0,07 M | 0,21 M |
| 18-24 | 1,90 M | 0,19 M | 0,52 M |
| 25-29 | 2,75 M | 1,29 M | 0,44 M |
| 30-39 | 5,48 M | 2,60 M | 0,85 M |
| 40-49 | 5,50 M | 2,59 M | 0,85 M |
| 50-59 | 5,98 M | 2,72 M | 0,89 M |
| 60-64 | 2,97 M | 1,35 M | 0,17 M |
| 65-74 | 3,91 M | 1,62 M | 0,05 M |
| 75-84 | 3,80 M | 1,58 M | 0,05 M |
| 85 et plus | 2,54 M | 0,85 M | 0,02 M |

Par nombre de parts (sur échantillon de 20 000 ménages, 35,21 M de foyers) : 1 part
17,27 M ; 1,5 part 0,05 M ; 2 parts 9,53 M ; 2,5 parts 3,97 M ; 3 parts 2,88 M ; 3,5
parts et plus 1,52 M.

## 3. Ce que la statistique publique compte

* **Le total** : « Nombre de foyers fiscaux », IRCOM 2025 (revenus 2024), fichier
  `national.xls`, onglet « nat », ligne « Total » : 41 635 259, dont 298 023
  non-résidents (ligne « Dont non-résidents (DINR) »). Champ : toutes les déclarations
  de revenus déposées, France entière, Mayotte et non-résidents compris. Source :
  https://static.data.gouv.fr/resources/limpot-sur-le-revenu-par-collectivite-territoriale-ircom/20260526-131537/ircom-2025-revenus-2024.zip
  (de même pour 2022 et 2023, URL dans `docs/verification/lignes.json`). Les DOM y
  comptent 1 315 452 foyers (fichiers `departemental/971` à `976`, lignes « Total »),
  dont **81 549 à Mayotte** et 1 233 903 hors Mayotte.
* **Un foyer fiscal est une déclaration**, pas une personne ni un ménage : un couple
  marié ou pacsé déclare ensemble ; **des concubins déclarent chacun la leur** ; un enfant
  majeur de moins de 21 ans (25 s'il étudie) peut demander son rattachement, sinon il
  déclare seul ; l'année d'un décès, le couple dépose une déclaration jusqu'au décès et
  le survivant une autre (art. 6 CGI) ; un résident d'Ehpad ou de foyer déclare comme tout
  autre contribuable.
* **Par situation de famille** : les agrégats de la déclaration 2042 (DGFiP, « L'impôt
  sur le revenu : les déclarations nationales »,
  https://data.economie.gouv.fr/api/explore/v2.1/catalog/datasets/ir-declarations-2042-nat/exports/csv?use_labels=true,
  manifesté sous `dgfip_ir_2042_nat_export_2026-10-15.csv`), cases cochées :

| revenus | mariés 0AM | pacsés 0AO | célib. 0AC | divorcés 0AD | veufs 0AV | somme |
|---|---:|---:|---:|---:|---:|---:|
| 2022 | 11,30 M | 1,72 M | 17,25 M | 6,59 M | 3,89 M | 40,75 M |
| 2023 | 11,25 M | 1,79 M | 17,62 M | 6,70 M | 3,85 M | 41,21 M |
| 2024 | 11,21 M | 1,84 M | 17,93 M | 6,81 M | 3,83 M | 41,64 M |

  La somme retombe sur le total de l'IRCOM à l'unité près les trois années : les deux
  sources comptent la même chose. Les mêmes agrégats donnent, en 2024, la case T (0BT)
  sur 1,97 M de déclarations, 2,01 M d'enfants majeurs célibataires rattachés (0DJ) dans
  1,72 M de foyers, 15,15 M d'enfants mineurs ou handicapés (0CF) dans 8,78 M de foyers,
  et 0,82 M de déclarations qui déduisent une pension versée à un « 1er enfant majeur
  imposé séparément » (6EL).
* **Par taux marginal** : DGFiP, « nombre de foyers et montant de l'impôt net par taux
  marginal de taxation du barème »,
  https://www.impots.gouv.fr/sites/default/files/media/9_statistiques/0_etudes_et_stats/1_statistiques/1_impots_particuliers/ir/nid_25519_ir_taux_marginal.xlsx,
  onglet de l'année. Les foyers non imposés grâce à la décote y sont à 11 %, pas à 0 %.
* **Par tranche de revenu fiscal de référence** : IRCOM, même onglet, lignes « 0 à
  10 000 » à « Plus de 100 000 ».

## 4. La décomposition de l'écart

### Ce qui manque, par situation (2024)

| | DGFiP 2042 | modèle | écart |
|---|---:|---:|---:|
| foyers de couple (mariés + pacsés) | 13,05 M | 14,86 M | **+1,81 M** |
| foyers d'une personne (célib. + div. + veufs) | 28,58 M | 20,47 M | **−8,11 M** |
| total | 41,64 M | 35,34 M | −6,30 M |
| case T (parent isolé) | 1,97 M | 2,79 M | +0,82 M |

Le modèle a **trop de couples et bien trop de personnes seules en moins**. C'est la
signature des concubins fusionnés : chaque couple en union libre compté comme un foyer
devrait en faire deux.

### Les causes, une à une

| cause | foyers en plus pour le modèle | comment |
|---|---:|---|
| 1. couples en union libre fusionnés | +2,8 à +3,1 M | **mesuré** (ci-dessous) |
| 2. rattachement trop large des 18-24 ans | +1,2 à +1,4 M | mesuré, borne |
| 3. hors ménages ordinaires | +0,8 à +1,2 M | compté, dépôt supposé |
| 4. non-résidents | +0,30 M | **mesuré** (IRCOM) |
| 5. Mayotte | +0,08 M | **mesuré** (IRCOM) |
| 6. décès dans l'année (deux déclarations) | +0,3 à +0,6 M | **hypothèse** |
| somme | **+5,5 à +6,7 M** | contre −6,30 M d'écart |
| en sens contraire (voir plus bas) | quelques 0,1 M | hypothèse |

**1. Les concubins (mesuré).** Le recensement de 2021 (Insee, tableaux détaillés POP3,
https://www.insee.fr/fr/statistiques/fichier/8202264/TD_POP3_2021_csv.zip, déjà manifesté,
lignes `NIVGEO = COM`) compte, parmi les 15 ans ou plus, 23,32 M de personnes mariées,
3,07 M pacsées et **6,11 M en concubinage ou union libre**, soit 18,8 % des 32,49 M de
personnes en couple ; la part est de 86 % à 15-19 ans, 73 % à 20-24, 51 % à 25-29, 33 % à
30-34, 25 % à 35-39, puis 8 % à 60-64 et 3 % à 80 ans ou plus. Les mariés et pacsés du
recensement font 13,19 M de couples, contre 13,05 M de déclarations M et O : les deux
sources s'accordent. Appliquée aux 14,86 M de foyers de couple du modèle, la part de
18,8 % donne 2,8 M de couples à scinder ; le recensement en compte 3,06 M en tout.
Mesure directe sur échantillon : les foyers de couple de l'échantillon ont été scindés au
hasard (graine 7) avec la probabilité d'union libre par âge de l'Insee (Insee Première
n° 1682, figure 1, « Répartition des personnes vivant en couple cohabitant selon le type
d'union, par âge », recensement 2016, https://www.insee.fr/fr/statistiques/3305188 : 88 %
à 20 ans, 64,5 % à 25, 39,9 % à 30, 24,3 % à 40, 18,0 % à 50, 9,5 % à 60, 7,2 % à 65,
4,4 % à 80), le conjoint devenant déclarant de son propre foyer, la case T retirée. Les
foyers passent de **35,21 M à 38,09 M (+2,88 M)**, les foyers de couple de 14,97 M à
12,10 M. La part de 2016 est un peu basse pour 2024 (21 % des personnes en couple en
2016 selon la même page) : la fourchette retenue est +2,8 à +3,1 M.

**2. Le rattachement (mesuré, borne).** Le modèle rattache 3,44 M de personnes de 18 ans
ou plus au foyer de leurs parents (dont 0,46 M en emploi, de 18 à 20 ans). La DGFiP compte
2,01 M d'enfants majeurs rattachés (0DJ, 2024). Les enfants majeurs handicapés, comptés
en 0CF, ne se séparent pas des mineurs dans l'export. L'excès est donc d'au plus 1,43 M,
et la fourchette retenue 1,2 à 1,4 M. Les 0,82 M déclarations qui déduisent une pension à
un enfant majeur imposé séparément (6EL) disent que ces jeunes-là existent comme foyers.
La règle du code (moins de 21 ans toujours rattaché, moins de 25 ans sans emploi
rattaché) est une règle de droit, pas de comportement : le rattachement est une option
que beaucoup de familles n'exercent pas. Le tirage uniforme de l'âge dans 15-24 ans
brouille la frontière de 18 et de 21 ans, ce qui ne change pas l'ordre de grandeur.

**3. Hors ménages ordinaires (compté, dépôt supposé).** Le recensement de 2021 (POP2,
https://www.insee.fr/fr/statistiques/fichier/8202264/TD_POP2_2021_csv.zip, lignes
`NIVGEO = COM`, âge quinquennal 20 ans ou plus) compte **1,25 M d'adultes hors ménages
ordinaires** : 0,91 M en établissement de moyen ou long séjour, maison de retraite,
foyer ou résidence sociale (CATPR 11), 0,10 M en internat ou cité universitaire, 0,05 M
en caserne, 0,09 M en habitation mobile ou sans abri, 0,09 M ailleurs. L'EEC ne les
enquête pas. La plupart déclarent seuls (veufs en Ehpad, travailleurs en foyer) ; une
partie est mariée à un conjoint resté à domicile et déclare avec lui ; des étudiants en
cité sont rattachés. Le taux de dépôt n'est pas mesuré : +0,8 à +1,2 M est une
hypothèse sur ce taux, pas sur le compte.

**4 et 5. Non-résidents et Mayotte (mesurés).** 298 023 foyers non-résidents et 81 549
foyers à Mayotte dans l'IRCOM 2025. L'EEC n'enquête ni l'un ni l'autre. Les DOM hors
Mayotte, eux, tiennent : 1,22 M dans le modèle contre 1,23 M.

**6. Les décès (hypothèse).** 643 200 personnes sont décédées en France en 2024 (Insee
Focus n° 364, https://www.insee.fr/fr/statistiques/8655177). L'année d'un décès dans un
couple marié ou pacsé produit deux déclarations, et la déclaration d'un célibataire
décédé existe pour la part de l'année vécue, alors que l'EEC, enquête continue, ne voit
le défunt qu'une partie de l'année. La part des décédés mariés n'est pas publiée sur
cette page : +0,3 à +0,6 M est une hypothèse. Les mariages et pacs de l'année ne
doublent pas les déclarations depuis les revenus 2011 (imposition commune par défaut) ;
les divorces non plus, les ex-époux déclarant séparément toute l'année.

**En sens contraire, non mesuré.** 0,53 M de déclarants du modèle ont moins de 18 ans
parce que l'âge est tiré uniformément dans 15-24 ans : ce sont pour la plupart des
jeunes adultes mal datés, pas des foyers en trop. 1,07 M de personnes en couple (poids
EEC) ne sont pas appariées, surtout dans les logements « autre » (0,66 M), et comptent
comme deux foyers alors qu'une partie est mariée. Le modèle fait déclarer tout adulte,
alors que certains ne déposent pas.

**La somme** des causes mesurées ou bornées, +5,5 à +6,7 M, encadre l'écart de 6,30 M.
Elle est cohérente avec les situations : une fois les concubins scindés, le modèle a
environ 12,0 M de couples contre 13,05 M déclarés mariés ou pacsés, l'écart de 1,0 M
tenant aux mariés non cohabitants (conjoint en Ehpad ou ailleurs), aux couples non
appariés et aux non-résidents ; et environ 26,2 M de personnes seules contre 28,58 M,
l'écart de 2,4 M tenant aux causes 2, 3 et 6.

### Par tranche de revenu fiscal de référence (sur échantillon de 20 000 ménages)

| RFR | IRCOM 2024 | modèle | écart | modèle, concubins scindés | écart |
|---|---:|---:|---:|---:|---:|
| 0 à 10 000 € | 8,07 M | 6,78 M | −15,9 % | 7,96 M | −1,4 % |
| 10 à 12 000 € | 1,58 M | 1,21 M | −23,4 % | 1,36 M | −13,8 % |
| 12 à 15 000 € | 2,60 M | 1,86 M | −28,5 % | 2,12 M | −18,5 % |
| 15 à 20 000 € | 5,22 M | 3,41 M | −34,8 % | 3,94 M | −24,5 % |
| 20 à 30 000 € | 8,72 M | 6,40 M | −26,6 % | 7,43 M | −14,8 % |
| 30 à 50 000 € | 8,54 M | 8,28 M | −3,1 % | 8,68 M | +1,6 % |
| 50 à 100 000 € | 5,49 M | 5,98 M | +9,0 % | 5,41 M | −1,4 % |
| plus de 100 000 € | 1,41 M | 1,29 M | −8,5 % | 1,18 M | −16,5 % |

Les foyers qui manquent ont un RFR de 10 000 à 30 000 € : c'est la tranche à 11 % et le
bas de la décote. Les concubins scindés comblent le bas (0 à 10 000 €) mais laissent
−15 à −25 % entre 12 000 et 30 000 € : des personnes seules à revenu modeste, que les
causes 2, 3 et 6 (jeunes actifs, résidents d'établissement, veufs) décrivent bien.

### Par taux marginal (sur échantillon), et pourquoi 30 et 41 % sont au-dessus

| TMI | DGFiP 2024 | modèle (grille) | modèle (éch.) | concubins scindés (éch.) |
|---|---:|---:|---:|---:|
| 0 % | 13,13 M | −12,7 % | −13,6 % | −5,0 % |
| 11 % | 20,93 M | −23,2 % | −23,8 % | −19,4 % |
| 30 % | 6,87 M | +4,9 % | +6,9 % | +17,4 % |
| 41 % | 0,43 M | +18,2 % | +14,2 % | +37,4 % |
| 45 % | 0,06 M | +8,1 % | +26,1 % | +43,5 % |

L'échantillon reproduit la grille à quelques points près, sauf à 45 %, où 20 000 ménages
ne portent que quelques dizaines de foyers : cette ligne n'est pas mesurable ainsi.

**La fusion n'explique pas l'excès à 30 et 41 % : elle l'atténue.** Le quotient conjugal
d'un couple fusionné abaisse son taux marginal ; scinder les concubins pousse le mieux
payé de chacun vers 30 ou 41 %. L'hypothèse « des foyers trop gros parce que fusionnés »
est donc infirmée pour ces deux tranches. Ce qui les gonfle tient au revenu :

* **Le nombre de foyers à haut RFR n'est pas en excès** (50 000 € ou plus : 7,27 M contre
  6,90 M dans la base, 6,59 M une fois les concubins scindés ; plus de 100 000 € : −8 à
  −17 %). C'est la composition qui l'est : dans le modèle, 35 % des foyers de 30 000 à
  50 000 € de RFR sont à 30 % ou plus, et 42 % d'entre eux sont des personnes seules. Le
  modèle a trop de personnes seules à revenu de 30 000 à 80 000 €. Recaler les poids des
  foyers sur les huit tranches de RFR de l'IRCOM (post-stratification d'essai, sur
  échantillon) ramène le 11 % à −7 % mais laisse le 30 % à +6 % et le 41 % à +19 % ; avec
  les concubins scindés, +20 % et +56 %.
* **Le revenu imposable du modèle n'a pas de déductions** : aucune des cases de charges
  déductibles n'est dans la population. La DGFiP compte en 2024 (export 2042) 7,08 Md€ de
  versements sur les nouveaux PER (6NS, 6NT ; 1,70 M de cases), 0,99 Md€ de PERP (6RS,
  6RT), 7,95 Md€ de pensions alimentaires versées (6GU, 6EL, 6GI) et 1,09 Md€ de
  déductions diverses (6DD). Ces 17 Md€ abaissent le revenu imposable des foyers à 30 et
  41 % et en font passer une partie sous le seuil. **Hypothèse non mesurée**, mais du bon
  ordre : à un taux marginal moyen de 30 %, 17 Md€ de déductions font environ 5 Md€
  d'impôt, soit 5 % de l'impôt au barème, qui est à +6 à +10 %.
* **Le RFR du modèle n'a ni capitaux ni plus-values** dans la passe de la grille (sans
  imputation) : un foyer réel de 60 000 € de RFR en a une part hors barème, et son revenu
  imposé au barème est plus bas que celui d'un foyer modélisé au même RFR.
* La concentration des pensions sur trop peu de foyers (D-207, D-209 : 12,24 M foyers
  pensionnés contre 15,09 M bénéficiaires de l'abattement) y contribue aussi : la même
  masse sur moins de retraités en met plus au-dessus du seuil de 30 %.

Les déciles de RFR par part le confirment (sur échantillon, moyenne par décile, contre
DGFiP Statistiques n° 41, tableau 2, `data/raw/dgfip_stat_41_ir_2024_tables.xlsx`) : 2e
décile 4 398 € contre 5 093 €, 5e 15 735 contre 15 523, 8e 26 665 contre 24 862, **9e
33 566 contre 31 043 (+8 %)**, dernier 60 610 contre 65 532 (−8 %). Le haut du milieu est
trop épais, la queue trop mince ; le seuil de 30 % (29 315 € par part) tombe dans ce 9e
décile.

**Les foyers imposés tiennent (−0,5 %) par compensation** : les 6,3 M de foyers manquants
sont presque tous non imposés. Scinder les concubins ajoute des foyers imposés : 18,87 M
à 20,29 M sur échantillon (+7,5 %).

**La case T est en excès de 0,82 M** (2,79 M contre 1,97 M) : 0,48 M de ces foyers n'ont
pour personnes à charge que des majeurs, rattachés par la règle de la cause 2 ; le reste
n'est pas expliqué ici.

## 5. Ce que l'écart fait aux études

Les études chiffrent une réforme par l'écart de deux passes sur la même population.
L'écart de niveau du nombre de foyers **ne s'y annule pas** quand la réforme agit foyer
par foyer ou part par part, ce qui est le cas de toutes les mesures de barème, de décote
et de quotient. Il s'y compense en partie : il manque des foyers à 11 % et il y en a trop
à 30 et 41 %.

* **PLF 2027, art. 2** (`docs/etudes/plf2027.md` : revalorisation de 2,1 % des tranches,
  de la décote et du plafond de la demi-part ; 2,85 Md€). Calcul d'ordre de grandeur sur
  échantillon, barème seul (gain par part = 2,1 % × Σ des sauts de taux × seuils
  franchis, sans décote ni plafonnement) : 2,86 Md€ avec les foyers du modèle, 2,92 Md€
  si l'on donne à chaque tranche le nombre de foyers de la DGFiP (−2,1 %), 2,67 Md€ si
  l'on prend en plus les parts moyennes des concubins scindés (+7,5 %). **Le biais du
  coût de l'art. 2 tient dans −2 % à +8 %** : les 4,8 M foyers à 11 % absents (environ 45 €
  chacun, −0,22 Md€) compensent presque l'excès à 30 et 41 % (+0,16 Md€). La part de la
  décote est sous-estimée : ses bénéficiaires sont précisément les foyers à RFR de 12 000
  à 30 000 € qui manquent ; non mesuré, car le nombre de bénéficiaires de la décote n'est
  dans aucun fichier du manifeste.
* **PLF 2027, art. 3** (abattement de 10 % des pensions) : D-209 a mesuré la piste des
  concubins, −1,5 % sur ce que l'article retire, et des établissements, −4,6 %.
* **Le Pen, part entière au 2e enfant** (`qf_parts_enf2`) : le coût dépend des foyers à
  deux enfants et plus, de leur taux marginal et du plafond. Les 1,2 à 1,4 M de majeurs
  rattachés en trop comptent comme enfants de rang 1 ou 2 et font franchir le seuil du 2e
  enfant à des foyers qui ne le franchissent pas : **surestimation probable, non
  mesurée**. La fusion des concubins joue dans les deux sens (revenus mis en commun, mais
  enfants rattachés au seul parent déclarant dans la réalité).
* **Lisnard, déplafonnement du quotient familial** : le gain est concentré sur les foyers
  à 30 et 41 % avec enfants, en excès de 5 à 19 % ; le plafond du premier enfant d'un
  parent isolé y entre, et la case T est en excès de 42 %. **Surestimation probable**,
  d'un ordre de grandeur comparable à l'excès des tranches hautes ; non mesurée.
* **Tondelier, tranche à 60 % au-delà de 250 000 € par part** : la ligne à 45 % tient
  (+4,5 %), les RFR de plus de 100 000 € sont à −8,5 % sur échantillon. La fusion des
  concubins aisés dilue le revenu par part du mieux payé ; la scinder augmenterait un peu
  la base. Effet faible, non mesuré.
* **Les autres études** (prestations, TVA, cotisations) ne lisent pas le foyer fiscal ;
  mais le foyer et la famille CAF partagent leur identifiant (`skeleton.py:507-508`), ce
  qui interdit de corriger l'un sans toucher l'autre (section 6).

## 6. Le correctif proposé

En deux étapes, la première dans le squelette, la seconde à la phase 7, puisque
`calibrate.py` est fermé jusque-là.

**Étape A, la structure (`skeleton.py`), données déjà manifestées.**

1. **Séparer foyer fiscal et famille.** `famille_id` garde l'unité 0 entière (les
   concubins forment une seule famille pour la CAF) ; seul `foyer_id` se scinde. Sans
   cela, scinder les concubins casserait le RSA, la prime d'activité et les aides au
   logement, qui traitent tout couple comme un foyer.
2. **Scinder les couples en union libre** au hasard, graine fixe, avec la part par âge
   quinquennal du recensement 2021 (POP3, `STAT_CONJ_19 = 3` sur 1 + 2 + 3), lue sur
   l'âge moyen du couple. Les enfants restent au déclarant principal, sans case T
   (CE, 15 avril 2016, n° 375682, déjà cité au code).
3. **Un rattachement par probabilité** au lieu de la règle d'âge : la probabilité,
   par tranche d'âge et statut d'activité, calée pour que les majeurs rattachés
   pondérés valent 0DJ (2,01 M en 2024). Les autres déclarent seuls.
4. **Ajouter les adultes hors ménages ordinaires** (POP2, CATPR 11 surtout) comme
   foyers d'une personne, avec des pensions tirées plus bas que celles des ménages
   ordinaires (la publication EHPA de la DREES, que D-209 n'a pas pu lire, serait la
   bonne source).
5. **Les non-résidents et Mayotte** restent hors du modèle : 0,38 M à dire dans la
   ligne, ou à retirer du comparateur dans une ligne nouvelle (la ligne préenregistrée ne
   se modifie pas).
6. **Manifester les trois IRCOM** (URL dans `lignes.json`) : ils ne sont pas dans
   `data/raw/MANIFEST.json` aujourd'hui.

Coût : une centaine de lignes, une reconstruction de la population (`make data`) puis
la grille et toutes les études à refaire (`make full`, sur accord du propriétaire).
Risques : les masses de revenus étant calées après le squelette, plus de foyers
signifient moins de revenu par foyer, ce qui est voulu ; mais la scission tirée au
hasard ignore qui, dans la réalité, est marié (les concubins sont plus jeunes et plus
souvent bi-actifs que le tirage par âge seul ne le dit) ; et les tests de
`tests/test_population.py` qui tiennent la structure changeront de nombres.

**Étape B, le calage des foyers (phase 7).** Une marge de foyers dans le ratissage :
nombre de foyers par situation (M + O contre C + D + V, export 2042) croisé avec les huit
tranches de RFR de l'IRCOM. Le croisement situation × RFR n'est dans aucun fichier du
manifeste ; non trouvé, à chercher dans les tableaux DGFiP. Il faut, en parallèle, les
**charges déductibles** (PER, PERP, pensions alimentaires : 17 Md€, cases 6NS à 6GU de
l'export 2042, déjà manifesté) dans le revenu imposable, faute de quoi le calage sur le
RFR ne corrige pas le revenu imposable des tranches hautes.

**Le pronostic, ligne par ligne** (biais moyen sur 2022-2024 ; l'étape A est appuyée sur
la mesure d'échantillon, l'étape B est une hypothèse) :

| ligne | aujourd'hui | après A | après A + B |
|---|---:|---:|---:|
| Foyers fiscaux | −14,2 % | −5 à 0 % | −2 à +2 % |
| Foyers imposés | −0,5 % | +3 à +12 % | −3 à +5 % |
| TMI 0 % | −13,6 % | 0 à +12 % | −5 à +5 % |
| TMI 11 % | −21,9 % | −20 à −14 % | −10 à 0 % |
| TMI 30 % | +9,4 % | +14 à +22 % | −5 à +10 % |
| TMI 41 % | +17,4 % | +30 à +45 % | −10 à +25 % |
| TMI 45 % | +4,5 % | +5 à +40 % | −15 à +25 % |
| Impôt au barème | +8,0 % | +10 à +14 % | 0 à +6 % |
| Salaires déclarés | −1,1 % | −1,5 à −0,5 % | −1,5 à −0,5 % |

**À lire avant de décider.** L'étape A seule remet le nombre de foyers et la tranche à 0 %
dans leur tolérance, mais **dégrade les tranches à 30 et 41 %, les foyers imposés (2022
hors de ±10 % probable) et l'impôt au barème** : sur échantillon, scinder les concubins
porte l'impôt net de 106,9 à 110,3 Md€ (+3,2 %). Elle rend la population plus juste et
la grille moins flatteuse, parce que l'excès de revenu imposable par personne, que la
fusion cachait, apparaît. Le 11 % ne rentre dans ±15 % qu'avec l'étape B. Le seul
morceau de A qui ne dégrade rien est la séparation foyer / famille, sans effet sur aucun
nombre tant que rien d'autre ne change.

## 7. Comment l'expliquer au public

Le simulateur part d'une enquête qui voit des logements, pas des déclarations d'impôt.
Dans un logement, il met un couple dans une seule déclaration, alors qu'un couple non
marié et non pacsé en remplit deux ; il range les jeunes adultes chez leurs parents,
alors que beaucoup déclarent seuls ; et il ne voit ni les résidents de maisons de
retraite ou de foyers, ni les contribuables vivant à l'étranger ou à Mayotte. Il lui
manque ainsi environ 6 millions de déclarations sur 41,6 millions, surtout des personnes
seules aux revenus modestes, qui paient peu ou pas d'impôt. Cela ne change presque pas le
nombre de foyers qui paient l'impôt, mais cela déforme qui paie à quel taux.

La preuve, pour un lecteur sceptique, tient dans un tableau : les déclarations par
situation de famille (mariés, pacsés, célibataires, divorcés, veufs), publiées par la
DGFiP et qui retombent exactement sur le total, à côté de celles du modèle, puis le même
tableau après chaque correction (concubins, jeunes, établissements, étranger). Un second
graphique, en barres, met côte à côte le nombre de foyers par tranche de revenu fiscal de
référence (IRCOM) et celui du modèle. Le lecteur pourrait faire varier lui-même la part
des couples en union libre (de 15 à 25 % des personnes en couple) et la part des jeunes de
18 à 24 ans qui déclarent seuls, et voir bouger le nombre de foyers, ceux de chaque
tranche et le coût d'une revalorisation du barème.
