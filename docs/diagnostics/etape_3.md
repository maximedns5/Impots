# Étape 3 du but 19 : les foyers fiscaux, l'âge des jeunes, le calage

*Branche `claude/but19-e3`, partie de `claude/but19` (e069658), le 10 novembre 2026.
Diagnostics suivis : `foyers_fiscaux.md` (étapes A et B),
`famille_logement_niveau_de_vie.md` (A6-1, B6-1), `SYNTHESE.md`. Aucune passe ni
construction sur la population entière ; `incomes.py` et `lignes.json` ne sont pas
touchés.*

## 1. Ce qui a changé, fichier par fichier

**`src/impots/population/skeleton.py`** — le foyer fiscal se sépare de la famille.

* `_assign_units` : la famille (CAF) reste l'unité 0 entière, comme avant ; le foyer
  fiscal en retire ceux qui déclarent seuls. Un conjoint en union libre et un enfant
  majeur non rattaché deviennent déclarants principaux d'un foyer numéroté par leur
  place, et gardent leur rôle de conjoint ou d'enfant dans la famille. OpenFisca lit
  déjà ce cas : les ressources fiscales d'une famille sont celles du foyer du demandeur
  et celles du foyer du conjoint quand il en est le déclarant principal
  (`famille.conjoint.foyer_fiscal(...) * has_role(DECLARANT_PRINCIPAL)` dans les aides
  au logement et les prestations familiales) ; `statut_marital` vaut « pacsé » pour deux
  déclarants d'un foyer, « célibataire » sinon. La case T suit : un parent dont le
  concubin déclare seul vit en couple (CE, 15 avril 2016), pas de case T.
* `_draw_foyers` (nouveau), deux tirages sur des générateurs propres
  (`default_rng([seed, 6])`) :
  * **les concubins** : chaque couple apparié est scindé avec la moyenne des parts
    d'union libre de ses deux membres, par âge quinquennal, du recensement 2021 (POP3,
    déjà manifesté) ; les enfants restent au foyer de la personne de référence ;
  * **le rattachement** : un mineur de la famille est toujours rattaché ; un majeur
    éligible (18-20 ans, ou 21-24 ans sans emploi, la règle du code inchangée) l'est
    avec une probabilité commune, fixée pour que les rattachés pondérés valent la case
    0DJ (2 014 392 enfants en 2024), ramenée à la part de la France que pèse le cadre.
    Sur l'échantillon, cette probabilité vaut 0,69. Un majeur non rattaché déclare
    seul et reste enfant de la famille, où la CAF applique ses propres tests d'âge et
    de ressources.
* `_draw_young_ages_by_role` et `child_share_by_age` (nouveaux) : l'âge exact des
  15-24 ans est retiré selon leur place. Un enfant de la famille reçoit l'âge *a* avec
  une probabilité proportionnelle à N(a)·s(a), un autre jeune à N(a)·(1 − s(a)) ; N est
  la population des ménages ordinaires (POP2 2021), s la part qui vit comme enfant. Le
  tirage uniforme d'avant est gardé et consommé sur le même générateur, pour que les
  enfants synthétisés soient exactement ceux d'avant.
* Docstrings du module et de `_classify_dependants` mis à jour ; `SkeletonStats` dit la
  probabilité de rattachement.

**`src/impots/population/margins.py`** — les sources des tirages et de la marge neuve,
chacune avec son année et son usage (`calibration`) : `UNION_LIBRE_SHARE_BY_AGE`,
`RATTACHES_MAJEURS`, `CHILDREN_18_24`, `ORDINARY_HOUSEHOLD_POPULATION_15_24`,
`CHILD_SHARE_SHAPE`, `TENURE_2023`, `HOUSEHOLDS_BY_TENURE`, `tenure_targets()`.

**`src/impots/population/calibrate.py`** (ouvert par D-365) — une marge neuve, le statut
d'occupation : `with_cells` ajoute la colonne `tenure` (accédants et propriétaires,
HLM, autres locataires, logés gratuitement), `standard_margins` la marge `tenure`, cible
LOG T10 2023 en parts ramenées au total des ménages par type (31,27 M), pour que les deux
marges ne se contredisent pas (D-150). Rien d'autre ne bouge dans le ratissage.

**`data/raw/MANIFEST.json`** — trois sources neuves, téléchargées dans `data/raw` (hors
git) : `TD_FAM6v1_2021_csv.zip` (Insee, RP 2021, enfants des familles par âge),
`insee_rp2022_SL_PERS1_series_longues.xlsx` (Insee, RP 2022, mode de cohabitation par
âge), `insee_rp2023_log_t10_france.html` (Insee, RP 2023, LOG T10).

**Tests** — `tests/test_foyers_fiscaux.py` (neuf tests) ; dans `tests/test_population.py`,
deux tests retouchés et pourquoi :

* `test_standard_margins_hold_age_sex_as_a_drift_constraint` fixait la liste des marges
  à deux ; elle en a trois, la marge neuve proposée ici.
* `test_case_t_follows_the_couple_not_the_dwelling` construisait huit logements dont
  la prémisse était « tout couple est une déclaration, tout enfant de 15-24 ans inactif
  est rattaché ». Les deux sont maintenant tirés : le test tient le tirage hors du jeu
  (monkeypatch de `_draw_foyers`), pour que ses huit réponses restent celles de la règle
  de la case T. Le découpage est tenu par les tests neufs. Aucune assertion n'a changé.

**Ce qui n'a pas été fait, et pourquoi.**

* **Les adultes hors ménages ordinaires** (1,25 M au recensement, POP2) : non ajoutés.
  Il faudrait leur donner des ménages, des pensions et des droits (APL en foyer, ASPA en
  Ehpad) sans source de revenus lisible (l'enquête EHPA de la Drees refuse le
  conteneur) ; ils sortiraient du champ de l'ERFS (logement ordinaire) que la ligne du
  niveau de vie compare, et la masse des pensions, calée, se répartirait sur eux, ce qui
  déplacerait toutes les lignes de l'impôt. Proposition : une ligne de grille neuve qui
  retire du juge ce que la population ne peut pas porter (section 3).
* **La zone 1 des aides au logement** : la population ne la porte pas (l'EEC publique n'a
  ni commune ni région) ; une marge ne peut viser une catégorie absente. Un tirage au
  hasard parmi les villes-centres et banlieues donnerait le niveau, pas les ménages
  (diagnostic : +0,31 Md€). Proposé, non fait.
* **Le calage par situation de famille** : essayé, refusé (section 2.3).
* **Le calage par tranche de RFR** : impossible dans cette architecture (section 2.4).
* **Les charges déductibles** (PER, PERP, pensions alimentaires, 6DD : 17,1 Md€ en 2024,
  export 2042) : non faites, ce n'est pas simple. Il faut des cases neuves dans
  `to_openfisca.py` (f6ns, f6rs, f6gu, f6el, f6dd), une clé de répartition (aucun
  tableau par décile de RFR n'est publié pour ces cases dans le manifeste ; la pension
  alimentaire suppose un parent séparé, que l'EEC ne dit pas) et une seconde passe comme
  pour les niches. Proposition : une imputation par décile de RFR par part, sur le
  modèle de `niches.py`, si la DGFiP publie ces cases par décile ; sinon par la part des
  foyers à 30 % et plus, hypothèse déclarée.

## 2. Les mesures, avant et après

**Comment.** Un échantillon de 15 000 ménages de l'EEC 2024, tiré par
`runner.subsample` (PPS systématique, graine 20261110) sur les couples (IDENT, TRIM) ;
puis, comme `build.py` : squelette (graine 20240101), ratissage, revenus, et une passe
complète au droit de 2024, sans imputation. « Avant » est le code de e069658, extrait par
`git archive` ; « après » celui de cette branche, sur le même échantillon. L'échantillon
reproduit la population entière : 35,43 M de foyers contre 35,34 M, 10,75 Md€ d'AF contre
10,59. **Ces mesures ne sont pas aveugles** : je les ai faites en développant, et les
pronostics de la section 3 en sont tirés. Scripts : `/tmp/but19-e3/mesure.py`,
`cmp.py`, `reforme.py` (hors dépôt). Une passe : 32 à 40 s, 0,7 Go pour la construction.

Colonnes : **A** = squelette neuf, sans la marge du statut d'occupation ; **A+B** = la
branche telle qu'elle est.

### 2.1 La structure (comptes pondérés, poids du ménage)

| | avant | A | A+B | publié |
|---|---:|---:|---:|---:|
| foyers fiscaux | 35,43 M | 38,81 M | 38,86 M | 41,64 M (IRCOM 2024) |
| dont de couple | 14,85 M | 12,07 M | 12,06 M | 13,05 M (0AM + 0AO) |
| dont d'une personne | 20,58 M | 26,74 M | 26,80 M | 28,58 M (0AC+0AD+0AV) |
| case T | 2,84 M | 2,77 M | 2,78 M | 1,97 M (0BT) |
| majeurs à charge | 3,57 M | 2,09 M | 2,08 M | 2,01 M (0DJ, calé) |
| déclarants de moins de 18 ans | 0,54 M | 0,03 M | 0,03 M | ≈ 0 |
| enfants de la famille de 18-24 ans | 3,57 M | 2,92 M | 2,92 M | 2,93 M (FAM6, calé) |
| familles (CAF) | 35,43 M | 35,17 M | 35,20 M | |
| ménages locataires | 11,17 M | 11,17 M | 12,51 M | 12,58 M (LOG T10, calé) |
| dont HLM | 3,99 M | 3,99 M | 4,52 M | 4,55 M |
| propriétaires et accédants | 19,10 M | 19,10 M | 17,83 M | 17,94 M |

Les familles bougent de 35,43 à 35,20 M par l'âge seul : un jeune salarié de 15-24 ans
qui vit chez ses parents reçoit plus souvent moins de 21 ans, et la règle de la famille
(moins de 21 ans, ou moins de 25 ans sans emploi) le garde enfant. **Le découpage du
foyer seul ne touche pas les familles** : une variante (foyers neufs, âge uniforme, sans
marge) donne 35,43 M de familles, et l'AF, les aides au logement, le RSA et la prime
d'activité identiques à l'avant à quatre chiffres (10,75 ; 12,14 ; 26,74 ; 13,25 Md€),
pour 39,77 M de foyers.

### 2.2 Les lignes de la grille (droit 2024)

| | avant | A | A+B | publié 2024 | A+B/avant |
|---|---:|---:|---:|---:|---:|
| foyers fiscaux | 35,43 M | 38,81 M | 38,86 M | 41,64 M | +9,7 % |
| foyers imposés | 18,93 M | 20,35 M | 20,34 M | 19,68 M | +7,5 % |
| TMI 0 % | 11,61 M | 13,24 M | 13,34 M | 13,13 M | +14,9 % |
| TMI 11 % | 16,01 M | 16,91 M | 16,82 M | 20,93 M | +5,0 % |
| TMI 30 % | 7,28 M | 8,01 M | 8,06 M | 6,87 M | +10,6 % |
| TMI 41 % | 0,454 M | 0,577 M | 0,571 M | 0,434 M | +25,9 % |
| TMI 45 % | 0,068 M | 0,077 M | 0,075 M | 0,061 M | +11,0 % |
| IR au barème | 103,5 Md€ | 107,7 | 108,0 | 98,8 | +4,3 % |
| AF | 10,75 Md€ | 12,15 | 12,19 | 13,77 | +13,4 % |
| aides au logement | 12,14 Md€ | 12,25 | 13,51 | 15,67 | +11,3 % |
| RSA (droits) | 26,74 Md€ | 26,54 | 26,57 | 11,79 × 1,355 | −0,6 % |
| prime d'activité | 13,25 Md€ | 12,60 | 12,67 | 10,28 × 1,725 | −4,3 % |
| allocataires AF (déc.) | 4,26 M | 4,72 M | 4,73 M | 4,79 M (Cnaf) | +11,1 % |
| allocataires PA | 5,11 M | 4,94 M | 4,97 M | 4,63 M | −2,7 % |
| allocataires RSA | 3,62 M | 3,60 M | 3,61 M | 1,83 M | −0,3 % |
| allocataires AL | 4,81 M | 4,81 M | 5,33 M | 5,81 M | +10,7 % |
| niveau de vie médian | 24 406 € | 24 343 | 24 320 | 26 740 | −0,4 % |
| D9/D1 | 3,575 | 3,572 | 3,574 | 3,48 | 0,0 % |
| salaires imposables | 916,4 Md€ | 917,1 | 917,3 | 932,1 | +0,1 % |

Ce qu'il faut lire :

* **Les foyers** rentrent dans leur tolérance, la tranche à 0 % aussi ; les familles
  CAF ne bougent pas du fait du découpage. L'écart restant (2,8 M) est celui que la
  population ne peut pas porter : hors ménages ordinaires, non-résidents (0,30 M),
  Mayotte (0,08 M), décès de l'année, et les couples non appariés (le modèle a 12,06 M de
  foyers de couple contre 13,05 M déclarés mariés ou pacsés).
* **Comme le diagnostic l'annonçait, les tranches hautes se dégradent** : scinder les
  concubins pousse le mieux payé de chacun à 30 ou 41 %. 30 % passe de +6 à +17 %, 41 %
  de +5 à +32 % (sur l'échantillon), l'impôt au barème de +4,7 à +9,2 %. La tranche à
  11 % ne gagne que 0,8 M de ses 4,9 M manquants. Rien dans cette étape ne corrige le
  revenu imposable des personnes seules de 30 000 à 80 000 € ; les charges déductibles
  et le revenu des indépendants (étape 2) y entrent.
* **La prime d'activité baisse de 4,3 % par l'âge seul** (la variante sans l'âge la
  laisse à l'identique) : de jeunes salariés de 20-24 ans, rajeunis, rejoignent la
  famille de leurs parents, qui compte leurs revenus. La ligne était à −27 % : elle
  s'éloigne de 3 points. C'est l'effet de la règle de la famille, pas du foyer fiscal.
* **L'AF** gagne 1,4 Md€ (diagnostic : +1,17) ; **les aides au logement** 1,4 Md€, dont
  1,3 par la marge du statut d'occupation (diagnostic : −0,8 à −1,6 Md€ d'écart sur ce
  point). La médiane du niveau de vie baisse de 0,4 % : plus de foyers, des CSG au taux
  du RFR d'un foyer plus petit.
* **La case T** reste en excès (2,78 M contre 1,97 M) : le découpage en retire 0,20 M
  (variante sans l'âge : 2,64 M), l'âge en rend 0,14 en rajeunissant des enfants qui
  redeviennent à charge. Le reste n'est pas expliqué ici.

### 2.3 Le calage par situation de famille : essayé, refusé

Une marge de foyers par situation (déclarants principaux, couple : 13,05 M, une personne
: 28,58 M, export 2042 de 2024), ajoutée au ratissage sur l'échantillon. Le ratissage
atteint la marge à 1e-8 près, mais **il défait les autres** : le type de ménage manque de
6,6 %, l'âge × sexe de 7,4 %, la population passe à 72,95 M de personnes (+7,5 %), la
médiane perd 5,4 %, la prime d'activité gagne 27 %. Ce n'est pas un calage, c'est une
contradiction : les ménages de couple sont déjà fixés par le recensement (14,96 M) ; il
manque des foyers parce que la population ne voit pas des déclarants (hors ménages
ordinaires, non-résidents, conjoints non appariés), et aucun poids de ménage ne les
crée. Le bon instrument du nombre de couples est la scission, pas le poids. **Je ne
propose pas cette marge.** Elle passerait sous la borne de 10 % de `check_rake_result`
sur l'échantillon, ce qui est une raison de plus de ne pas la croire.

### 2.4 Le calage par tranche de RFR : pas dans cette architecture

Le ratissage tourne avant les revenus (`build.py`, l'ordre est porteur : les revenus
calent la masse salariale sur les poids en vigueur). Le RFR sort d'une passe OpenFisca.
Un calage sur les huit tranches de l'IRCOM demanderait : une première passe, des
cellules « foyers par tranche de RFR » par ménage, un ratissage joint avec le type, le
statut d'occupation et l'âge × sexe, puis un nouveau calage de la masse salariale, des
pensions et du chômage sur les poids neufs, ce qui déplace le RFR : une boucle. Sur la
population entière : une passe légère (fiscal seul) par tour, 4 lots, une dizaine de
minutes chacune d'après les passes de la grille (19 min pour trois passes complètes),
deux ou trois tours, la mémoire d'une passe légère par lot. C'est un chantier de phase 7,
pas une marge. Le diagnostic l'a essayé en post-stratification : il ramène le 11 % à
−7 % mais laisse 30 % et 41 % au-dessus (+6 et +19 %, +20 et +56 % concubins scindés) :
le défaut est dans le revenu imposable, pas dans le compte des foyers.

### 2.5 Deux réformes d'essai (échantillon, droit 2024, coût sur l'IR au barème)

| réforme | avant | après | écart |
|---|---:|---:|---:|
| barème, décote, plafond du QF + 2,1 % (PLF 2027, art. 2) | −2,82 Md€ | −2,84 | +0,8 % |
| plafond de la demi-part doublé (Lisnard) | −3,86 Md€ | −3,72 | −3,5 % |

## 3. Le préenregistrement proposé

### 3.1 Les marges et calages neufs (tous `use="calibration"`, dépensés)

| marge | source | année | cible |
|---|---|---|---|
| union libre par âge (1) | Insee, RP, TD_POP3 | 2021 | 18,8 % des personnes en couple |
| majeurs rattachés (2) | DGFiP, export 2042, 0DJ | 2024 | 2 014 392 enfants |
| enfants des familles, 18-24 ans (3) | Insee, RP, TD_FAM6v1 | 2021 | 2 930 587 |
| statut d'occupation (4) | Insee, RP, LOG T10, France | 2023 | 4 cases, ci-dessous |

1. Tirage du squelette. TD_POP3 est déjà manifesté ; lignes NIVGEO = COM, STAT_CONJ 3
   sur 1 + 2 + 3, par âge quinquennal : 86 % à 15-19 ans, 73 % à 20-24, 51 % à 25-29 …
   2,7 % à 80 ans ou plus.
2. Tirage du squelette ; nombre d'enfants (deuxième colonne de l'export manifesté),
   1 720 889 foyers.
3. Âge des 15-24 ans ; AGEFOR5 = 18, lignes NIVGEO = COM.
4. `calibrate.standard_margins` : propriétaires et accédants 17 944 861, locataires HLM
   4 546 449, autres locataires 8 037 800, logés gratuitement 691 037 ; leurs parts
   portées sur 31 274 700 ménages (le total de la marge par type).

La forme par âge simple des 18-24 ans est régionale (Insee Flash Nouvelle-Aquitaine
n° 21, RP 2013) ; son niveau est porté sur le national par un décalage logit. **Aucune
source nationale par âge simple n'a été trouvée** (cherché : Insee Première n° 1686,
bandes 18-24 et 25-29 ; RP séries longues SL_PERS1, bandes 0-17 et 18-29 ; TD_FAM6,
bande 18-24 ; les Flash régionaux). Le fichier détail « individus » du recensement
(AGEREV, LPRM) la donnerait ; il n'a pas été téléchargé (plusieurs centaines de Mo).
Les parts à 15-17 ans (97 %) sont une hypothèse proche des 98,1 % de SL_PERS1 (0-17).

### 3.2 Les lignes neuves proposées pour la grille (aucune tolérance existante ne bouge)

* **Foyers fiscaux résidents hors Mayotte**, IRCOM, total moins « Dont non-résidents »
  moins les fichiers 976 : 41 255 687 en 2024 (41 635 259 − 298 023 − 81 549) ; 2022 et
  2023 à relever dans les IRCOM 2023 et 2024 (URL dans `lignes.json`). Tolérance ±10 %,
  comme la ligne existante. Raison : le modèle ne peut porter ni l'un ni l'autre.
* **Foyers de couple (0AM + 0AO)** et **foyers d'une personne (0AC + 0AD + 0AV)**,
  export 2042 manifesté : 13,02 / 13,04 / 13,05 M et 27,73 / 28,18 / 28,58 M pour 2022,
  2023, 2024. Tolérance ±15 %. Raison : c'est le tableau qui prouve le découpage
  (diagnostic, section 7).
* **Case T (0BT)** : 1,89 / 1,95 / 1,97 M. Tolérance ±25 % : un excès non expliqué.
* **Ménages locataires**, LOG T10 : **non**, la marge la dépense.
* **Majeurs rattachés (0DJ)** : **non**, le tirage la dépense.

### 3.3 Le pronostic, ligne par ligne, de cette étape seule

Calculé en appliquant aux écarts de la grille de D-364 le rapport après/avant mesuré
sur l'échantillon, élargi de 3 à 4 points (l'échantillon, la population entière, un
tirage neuf). Le pronostic suppose les autres étapes absentes ; la jonction avec
l'étape 2 (le revenu des indépendants) poussera l'impôt et les tranches hautes vers le
haut, le RSA et le D9/D1 vers le bas.

| ligne (tolérance) | 2022 | 2023 | 2024 |
|---|---|---|---|
| foyers fiscaux (±10 %) | −8 à −2 % | −9 à −3 % | −10 à −4 % |
| foyers imposés (±10 %) | +7 à +13 % | +5 à +11 % | 0 à +6 % |
| TMI 0 % (±15 %) | −5 à +4 % | −5 à +3 % | −4 à +5 % |
| TMI 11 % (±15 %) | −20 à −13 % | −21 à −14 % | −23 à −15 % |
| TMI 30 % (±15 %) | +19 à +28 % | +18 à +27 % | +11 à +20 % |
| TMI 41 % (±30 %) | +35 à +55 % | +38 à +58 % | +38 à +58 % |
| TMI 45 % (±30 %) | −5 à +25 % | 0 à +35 % | 0 à +35 % |
| IR au barème (±10 %) | refusée | +12 à +18 % | +7 à +13 % |
| AF (±25 %) | −17 à −11 % | −17 à −11 % | −16 à −10 % |
| aides au logement (±25 %) | −18 à −12 % | −18 à −12 % | −16 à −10 % |
| RSA, montant (±14 %) | +54 à +60 % | +57 à +63 % | +60 à +67 % |
| RSA, foyers (±25 %) | refusée | +94 à +100 % | +95 à +101 % |
| prime d'activité, montant (±13 %) | −34 à −28 % | −36 à −30 % | −33 à −27 % |
| prime d'activité, foyers (±25 %) | +5 à +12 % | 0 à +7 % | +3 à +10 % |
| niveau de vie médian (±15 %) | −8 à −6 % | −9 à −7 % | −10 à −8 % |
| D9/D1 (±15 %) | +6 à +9 % | +5 à +7 % | +2 à +5 % |
| salaires déclarés (±10 %) | −1 à +1 % | −2 à 0 % | −2 à 0 % |
| CSG de remplacement (±10 %) | −7 à −4 % | −5 à −2 % | −9 à −6 % |
| foyers résidents hors Mayotte (neuve, ±10 %) | −7 à −1 % | −8 à −2 % | −9 à −3 % |
| foyers de couple (neuve, ±15 %) | −10 à −5 % | −10 à −5 % | −10 à −5 % |
| foyers d'une personne (neuve, ±15 %) | −7 à −2 % | −8 à −3 % | −8 à −4 % |
| case T (neuve, ±25 %) | +35 à +50 % | +35 à +50 % | +35 à +48 % |

Les cotisations, allègements, CSG d'activité et lignes des entreprises ne bougent pas
(les salaires sont les mêmes, la marge du statut d'occupation déplace des poids de
ménages à type égal ; mesuré : salaires imposables +0,1 %).

Ce que cette étape fait gagner et perdre à la grille, si le pronostic tient : entrent
dans leur tolérance les foyers fiscaux (les trois années) ; restent dedans la TMI 0 %,
l'AF, les aides au logement, plus près du centre ; sortent les foyers imposés de 2022,
la TMI 30 % les trois années (2024 au bord), la TMI 41 %, et l'impôt au barème de 2023
(2024 au bord). C'est le prix annoncé par le diagnostic de l'étape A sans l'étape B.

## 4. Ce que l'étape fait aux études

Les études chiffrent une réforme par l'écart de deux passes. Mesuré sur l'échantillon :

* **Indexation du barème, de la décote et du plafond (PLF 2027, art. 2)** : +0,8 % sur
  le coût. Les foyers à 11 % ajoutés et ceux poussés à 30 % se compensent, comme le
  diagnostic le disait (−2 à +8 %).
* **Plafond du quotient familial (Lisnard)** : −3,5 % sur le coût. Moins de majeurs à
  charge (3,57 → 2,08 M) et des concubins scindés dont les enfants restent à un seul
  parent.
* **Part entière au 2e enfant (Le Pen)** : non mesurée ; même sens que Lisnard, plus
  marqué (le rang 2 dépendait des majeurs rattachés en trop) : −3 à −10 %, hypothèse.
* **Abattement des pensions (PLF 2027, art. 3)** : D-209 avait mesuré la piste des
  concubins à −1,5 % ; même ordre attendu.
* **PLFSS 2027, art. 74, volet logement** : le coût suit les aides au logement, +11 %
  (de 78 vers 87 M€ environ contre 101 M€ officiels).
* **Mesures sur la prime d'activité** (art. 74, Attal) : −3 à −5 % par l'âge.
* **Tondelier (60 % au-delà de 250 000 € par part)** : faible, quelques %, non mesuré
  (la tranche à 45 % n'est pas mesurable sur 15 000 ménages).
* **TVA, accises, cotisations** : rien, sinon par les poids du statut d'occupation
  (déciles légèrement déplacés vers les locataires).

## 5. Ce qui reste, les doutes, les sources

* **Reconstruire la population entière.** Dans le worktree de la jonction, après le
  merge des étapes, sans toucher les cibles des liens : `rm data/processed/
  population_2024.parquet data/processed/population_2024.manifest.json` (les liens, pas
  leurs cibles), puis `PYTHONPATH=src .venv/bin/impots population build` (ou `make
  data`). Mesuré sur 15 000 ménages : squelette 0,2 s, ratissage 0,2 s (29 itérations au
  lieu de 24), revenus 0,0 s, 0,7 Go ; sur la population entière, quelques secondes de
  plus qu'aujourd'hui, la même mémoire. Les nouvelles sources ne sont pas lues à la
  construction (les constantes sont dans `margins.py`) : `make data` sur un checkout
  neuf n'en a pas besoin. La passe de la grille aura environ 10 % de foyers de plus :
  l'entité `foyer_fiscal` grandit d'autant, le temps et la mémoire des quatre lots de
  quelques % (mesuré : 32 à 40 s contre 34 s par passe d'échantillon). Les caches
  d'EMTR se recalculent d'eux-mêmes (empreinte du cadre, D-276).
* **Les lourds et les golden** (`tests/lourds.txt`, `tests/golden`) changeront de
  nombres avec la population : ils sont à repasser avant la PR du but ; je ne les ai pas
  lancés.
* **La scission ignore qui est marié** : elle ne lit que l'âge. Les concubins réels sont
  plus souvent bi-actifs ; un tirage par âge et activité serait meilleur, mais la part
  d'union libre par activité n'est pas dans POP3.
* **0DJ compte des rattachés qui ne vivent pas chez leurs parents** (étudiants logés
  seuls, ménages à eux dans l'EEC) : le modèle rattache donc un peu trop de ceux qu'il
  voit. Combien : non publié.
* **La case T** reste à +41 % ; non expliquée.
* **Le profil d'âge** des 18-24 ans est régional ; les 15-17 ans à 97 % sont une
  hypothèse. Le modèle a 8,05 M de 15-24 ans contre 7,70 M en ménages ordinaires au
  recensement 2021 : un écart de l'EEC, que la contrainte d'âge × sexe garde.
* **Sources non lues par le conteneur** : aucune bloquée pour cette étape. LOG T10 est
  une page HTML (enregistrée et manifestée), pas un fichier de données.
* **Interaction avec l'étape 2** (indépendants, `incomes.py`) : aucune collision de code ;
  les deux étapes déplacent l'impôt au barème et les tranches hautes dans le même sens.

## 6. Les tests lancés

```
PYTHONPATH=src .venv/bin/python -m pytest -m "not lourd and not chrono" -n 2 \
    tests/test_foyers_fiscaux.py tests/test_population.py
101 passed in 61.95s

PYTHONPATH=src .venv/bin/python -m pytest -m "not lourd and not chrono" -n 2 \
    tests/test_capital.py tests/test_consommation.py tests/test_niche_imputation.py \
    tests/test_zero_masked.py
93 passed, 3 warnings in 127.99s

# les tests neufs sur le code d'avant (git archive e069658) :
ERROR tests/test_foyers_fiscaux.py — collection (les fonctions n'existent pas)

.venv/bin/ruff check (fichiers touchés) : All checks passed!
```

Avant la retouche des deux tests de `test_population.py`, sur le code neuf : `2 failed,
90 passed` (les deux décrits en section 1).
