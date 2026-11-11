# Diagnostic : l'impôt sur le revenu net, et la couche entreprises

Auteur : agent `ir_net_et_entreprises`, 10 novembre 2026, sur `claude/but19` (249a3de).
Rien n'est modifié hors de ce fichier. Les scripts d'essai sont dans
`/tmp/diag_ir_net_et_entreprises/` (`ir_echantillon_v2.py`, `cdhr.py`, `cotis.py`,
`firmes.py`, `firmes_cs.py`, `groupes2042.py`) ; les tableaux de l'Insee téléchargés pour
ce diagnostic sont dans `/tmp/diag_ir_net_et_entreprises/dl/`, avec leur sha256 cité.

**Les mesures faites ici.** Trois passes sur un échantillon de **20 000 ménages** (le
tirage du runner, `runner.subsample`, graine fixe, poids qui gardent le total ; 35,21 M de
foyers pondérés), au droit de 2024 (et 2025 pour la CDHR), une passe à la fois. La couche
entreprises est lue en entier (15 954 lignes, sans échantillon). Tout le reste est lu
dans les rapports déjà écrits ou dans les fichiers publiés. Un nombre « sur échantillon »
le dit ; l'`ip_net` de l'échantillon est 2,1 % au-dessus de celui de la population
entière (106,76 contre 104,53 Md€), les écarts entre deux passes le sont beaucoup moins.

Le document a deux volets, A (l'impôt sur le revenu net) et B (la couche entreprises), et
une annexe C sur les cotisations à la charge des salariés, demandée en passant. Chaque
partie du plan imposé les traite dans cet ordre.

---

## 1. L'écart, en une phrase

**A. L'IR net.** La réconciliation (`reports/reconciliation.md`, 2024) donne l'impôt sur
le revenu simulé à 104,7 Md€ contre 88,0 Md€ de recettes nettes de l'État, **+19,0 %**,
alors que l'impôt au barème de la grille n'est qu'à **+10,3 % en 2023 et +5,8 % en
2024** (`docs/verification/GRILLE.md` ; refusé en 2022, faute de total).

**B. Les entreprises.** Contre l'Insee (comptes nationaux, tableau 3.217), sur 2022, 2023
et 2024 :

| ligne | 2022 | 2023 | 2024 |
|---|---|---|---|
| IS avant crédits d'impôt | −16,8 % | +2,7 % | +5,6 % |
| contribution sociale sur l'IS | −17,4 % | +38,6 % | +24,6 % |
| C3S | +15,9 % | +10,0 % | +4,8 % |
| CVAE | refusée | refusée | −12,1 % |

**C. Les cotisations salariales** : −8,9 %, −10,3 %, −11,6 % contre D613CE.

---

## 2. Ce que le modèle fait

### A. De la déclaration à « l'IR » de la réconciliation

1. La population (`data/processed/population_2024.parquet`) ne porte que des salaires,
   des pensions et du chômage. Aucun revenu du capital, aucun revenu d'indépendant, aucune
   base de réduction ou de crédit d'impôt, sauf imputation.
2. OpenFisca-France 176.0.8 calcule la chaîne de l'impôt (fichier
   `openfisca_france/model/prelevements_obligatoires/impot_revenu/ir.py`) :
   `ir_ss_qf` → `ir_brut` (quotient familial) → `ir_plaf_qf` (plafonnement) → `ip_net`
   (après la décote, `ir.py:1711`) → `iaidrdi = ip_net − reductions` (`ir.py:1738`) →
   `iai` (`ir.py:2259`) → `impot_revenu_avant_seuils_mise_recouvrement`
   `= −(iai + CEHR + PFU − credits_impot − acomptes)` → `impot_revenu_restant_a_payer`
   (`ir.py:2454`), après les seuils de mise en recouvrement.
3. Le projet lit ces variables par les lignes de `src/impots/engine/outputs.py` :
   `ir` = `impot_revenu_restant_a_payer` (ligne 107), `ir_avant_niches` = `ip_net`
   (127), `reductions` (129), `credits_impot` (131), `pfu` (137, un « dont » de `ir`),
   `cdhr` (150, hors de `ir`).
4. La réconciliation compare `ir` à `IR_NET_YIELD` (`population/reconcile.py:256`,
   `population/margins.py:184`) et `ir_avant_niches` au barème de la DGFiP
   (`reconcile.py:239`). La grille du but 18 (`src/impots/verification.py:80`) ne lit
   que le barème : l'IR net n'y a pas de ligne (D-364).
5. **Les niches ne sont imputées qu'à la demande.** La politique unique
   (`src/impots/population/imputations.py:13-17`, D-336) impute le capital, la
   consommation et les IJ quand la réforme les règle (`exigees`, ligne 88), et les niches
   « sur demande seulement : leur imputation est une calibration ». L'API ne les impute
   que si la requête porte `impute_niches` (`src/impots/service.py:579`) ; aucune page
   d'étude ne le demande (les rapports `reports/etudes/*/premiere_annee_*.json` portent
   `reductions = credits_impot = 0`, `pfu = cdhr = 0`).
6. Quand on la demande, l'imputation (`population/niches.py:80-91`,
   `population/runner.py:325`, une passe de base en plus) tire cinq dispositifs par
   décile de RFR par part : emploi à domicile (7DB), garde (7GA), cotisations syndicales
   (7AC), dons (7UF, 7UD), soit 10,6 Md€ calés sur la DGFiP. Le capital
   (`runner.py:356`) donne le PFU de la DGFiP n° 41 par fractile (10,32 Md€).

### B. De l'Ésane à l'IS de la grille

1. `src/impots/entreprises/cells.py:411` construit 18 sections NAF × 4 tailles depuis
   l'Ésane 2023 (effectifs, chiffre d'affaires, valeur ajoutée, résultat courant), le
   Focus 372 (partage ETI/GE) et la **DGFiP Statistiques n° 39 de 2024** (bénéfices par
   taille, `read_dgfip`, ligne 305). Le résultat net de chaque taille est porté au
   bénéfice des seules entreprises bénéficiaires par le rapport bénéfices / résultat
   fiscal de la DGFiP (`gross_up`, ligne 524), puis le niveau national est fixé par
   `fiscal_to_accounting` (ligne 593) : **les bénéfices de la population valent ceux de
   la DGFiP pour 2024, 283,95 Md€, au centime** (mesuré : 283,9506 Md€).
2. `entreprises/population.py:102` tire dans chaque cellule un chiffre d'affaires
   lognormal, des marges, et une perte avec la probabilité de la cellule ; les totaux de
   la cellule sont ramenés aux siens. 15 954 lignes : 7 170 micro, 5 014 PME, 3 460
   ETI, 310 GE (`data/processed/firms_2023.parquet`).
3. `entreprises/variables.py` : l'IS (ligne 142, 15 % jusqu'au plafond pour les
   éligibles, 25 % au-delà), la contribution sociale (ligne 158 : 3,3 % de l'IS au-delà
   de 763 000 €, pour un chiffre d'affaires d'au moins 7,63 M€), la C3S (ligne 188, sur
   le chiffre d'affaires **de l'année**, alors que la loi prend celui de l'année d'avant,
   ce que la docstring dit), la CVAE (ligne 298, sur la valeur ajoutée comptable).
4. `src/impots/verification.py:93-110` calcule ces totaux au droit de l'année, puis les
   multiplie par le PIB nominal de l'année sur celui de 2023 (`BASE_FIRMES = 2023`,
   ligne 32 ; `hypotheses.vieillissement_entreprises`, `src/impots/hypotheses.py:211`,
   D-246) : 0,9366 pour 2022, 1 pour 2023, 1,0358 pour 2024 (PIB de
   `impots.dette.comptes` : 2 654,0, 2 833,8 et 2 935,2 Md€).

Mesuré sur la couche entière : l'IS de base vaut **69,31 Md€** (le même aux droits de
2022, 2023 et 2024), la contribution sociale 1,403, la C3S 5,289, la CVAE 3,282 (2024).
La grille est exactement ces nombres fois le facteur du PIB.

---

## 3. Ce que la statistique publique compte

### A. L'IR

* **Recettes nettes de l'État** (`IR_NET_YIELD`, 87,99 Md€ en 2024) : exécution
  budgétaire, c'est-à-dire l'argent encaissé en 2024 (prélèvement à la source de 2024,
  solde des revenus de 2023, moins les restitutions et les crédits remboursés). La source
  dans `margins.py` n'est que « budget.gouv.fr » sans page ni tableau : **non revérifiée
  ici**.
* **L'impôt des revenus de 2024 par la DGFiP**, Statistiques n° 41, novembre 2025,
  POTE 3e émission (`data/raw/dgfip_stat_41_impot_revenu_2024_donnees.xlsx`, URL [n41]
  en fin de document), tableau 2 et tableau 3 :

| composante (revenus 2024) | Md€ |
|---|---|
| impôt au barème | 98,84 |
| impôt hors barème (PFU et autres) | 10,32 |
| CEHR | 1,98 |
| réductions et crédits d'impôt (RICI) | −19,53 |
| **impôt net implicite** | **91,61** |

Le détail des RICI (tableau 3) : crédits 9,77 (emploi à domicile 6,52, garde 1,79,
cotisations syndicales 0,15, autres 1,31) ; réductions 9,75 (dons 1,64, dons aux
personnes en difficulté 0,51, investissements outre-mer 0,76, scolarité 0,47,
dépendance 0,31, souscriptions PME 0,10, dispositifs locatifs Pinel, Denormandie,
Scellier, Duflot 1,73, **revenus de source étrangère 3,83**, autres 0,40). La dernière
n'est pas une niche : elle retire l'impôt français sur un revenu étranger que le barème
publié contient et que la population n'a pas.

Le n° 41 ne publie ni la décote ni le plafonnement du quotient : **non trouvés**.

### B. Les entreprises

* **Insee, comptes nationaux base 2020, tableau 3.217** (édition 2026,
  https://www.insee.fr/fr/statistiques/fichier/8988845/t_3217_fr.xlsx, sha256
  589b94cf…, lignes 78, 81, 58 et 56), en droits constatés selon `lignes.json`, tous
  affectataires. Les séries complètes, que la grille ne montre pas (Md€) :

| année | 2016 | 2017 | 2018 | 2019 | 2020 |
|---|---|---|---|---|---|
| IS (Insee D51) | 48,7 | 57,8 | 54,4 | 59,7 | 56,0 |
| IS brut DGFiP, exercice | 52,3 | 53,7 | 55,1 | 64,7 | 53,9 |
| contribution sociale | 0,98 | 1,14 | 1,12 | 1,24 | 1,17 |
| C3S | 3,55 | 3,56 | 3,77 | 3,90 | 4,11 |
| CVAE | 13,5 | 13,5 | 14,2 | 15,2 | 15,0 |

| année | 2021 | 2022 | 2023 | 2024 | 2025 |
|---|---|---|---|---|---|
| IS (Insee D51) | 62,0 | 78,0 | 67,5 | 68,0 | 69,5 |
| IS brut DGFiP, exercice | 71,0 | 68,3 | 68,6 | 69,0 | — |
| contribution sociale | 1,04 | 1,59 | 1,01 | 1,17 | 1,15 |
| C3S | 3,66 | 4,27 | 4,81 | 5,23 | 5,34 |
| CVAE | 7,5 | 9,0 | 5,2 | 3,87 | 3,75 |

* **L'IS brut DGFiP par exercice** : 2016 à 2022, Insee Analyses n° 112, figure 1
  (`data/raw/insee_ia112_taux_implicite_is_2016_2022.xlsx`,
  https://www.insee.fr/fr/statistiques/fichier/8630968/IA112.xlsx, source « DGFiP,
  liasses fiscales BIC-IS ») ; 2024 : DGFiP Statistiques n° 39, tableau 2, 69,05 Md€
  (`data/raw/dgfip_stat_39_impot_benefice_2024_donnees.xlsx`, URL [n39] en fin de
  document) ;
  2023 : déduit de la variation publiée au même tableau (+0,63 %), 68,6 Md€.
* Les bénéfices DGFiP : 278,0 Md€ en 2022 (hors plus-values et brevets, IA112), 282,6 en
  2023 (déduit de +0,48 %), 283,95 en 2024 (n° 39). Résultat fiscal des sociétés à l'IS :
  186,4 (2021), 164,1 (2022), 180,9 (2023), 172,0 (2024) (n° 39, graphique 1).
* **Le compte des sociétés non financières** (Insee T_7101,
  https://www.insee.fr/fr/statistiques/fichier/8988829/T_7101_fr.xlsx, sha256
  192cf3b1…) : EBE 423,1 (2021), 420,2 (2022), 487,1 (2023), 500,5 (2024), 497,5
  (2025) ; impôts sur le revenu payés (D51) 53,3, 68,6, 63,3, 65,1, 73,4 ; production
  3 148, 3 664, 3 800, 3 827, 3 877.

---

## 4. La décomposition de l'écart

### A. De +6 % au barème à +19 % au net

**La chaîne du modèle**, mesurée sur l'échantillon de 20 000 ménages, droit de 2024
(Md€) :

| étape | sans imputation | niches imputées | niches et capital |
|---|---|---|---|
| impôt sans quotient (`ir_ss_qf`) | 128,44 | 128,44 | 128,44 |
| après quotient (`ir_brut`) | 107,65 | 107,65 | 107,65 |
| plafonnement du quotient | +5,32 | +5,32 | +5,32 |
| décote | −6,21 | −6,21 | −6,21 |
| **au barème (`ip_net`)** | **106,76** | **106,76** | **106,76** |
| réductions | 0 | −2,06 | −2,08 |
| crédits | 0 | −8,62 | −8,63 |
| CEHR | +0,18 | +0,18 | +1,90 |
| PFU | 0 | 0 | +10,30 |
| seuils de recouvrement | −0,01 | −0,01 | −0,13 |
| **net (`ir`)** | **106,93** | **96,26** | **108,12** |
| foyers imposés (M) | 18,87 | 17,63 | 17,70 |

Sur la population entière, la réconciliation lit `ip_net` = 104,53 et `ir` = 104,71 :
l'écart de +0,18 est la CEHR des seuls salaires, mesurée à 0,18 sur l'échantillon.

**La décomposition de l'écart de la réconciliation** (2024, Md€), terme à terme contre
les publications citées au §3 :

| cause | Md€ | comment c'est mesuré |
|---|---|---|
| le barème du modèle au-dessus de la DGFiP | +5,69 | 104,53 − 98,84 |
| les RICI absentes (`reductions = credits = 0`) | +19,53 | n° 41, tableau 3 |
| dont imputables par le code actuel (5 dispositifs) | +10,6 | calés, mesuré 10,68 |
| dont non imputés (Pinel, outre-mer, scolarité, dépendance…) | +5,1 | n° 41 |
| dont « revenus de source étrangère » | +3,83 | n° 41 |
| le PFU absent | −10,32 | n° 41, tableau 2 |
| la CEHR quasi absente | −1,80 | 1,98 publié, 0,18 simulé |
| du rôle au budget (impôt net 91,61 contre 87,99) | +3,62 | résidu, non expliqué |
| **somme** | **+16,72** | |
| **écart de la réconciliation** | **+16,72** | 104,71 − 87,99 |

La somme tombe sur l'écart par construction : c'est une identité comptable, chaque terme
étant lu dans une publication. Ce qui reste **non expliqué**, c'est le dernier terme,
3,62 Md€ entre l'impôt des rôles et l'encaissement budgétaire. Hypothèses, non vérifiées :
le décalage de l'encaissement (une année de budget mêle le prélèvement à la source de
l'année et le solde des revenus d'avant, plus faibles), les restitutions, et le
périmètre du PFU (une part du prélèvement sur les revenus du capital peut être comptée
hors de la ligne IR du budget ; l'Insee la range dans une ligne à part, 3,88 Md€ en 2024,
t_3217 ligne 74).

**Lecture.** Le +19 % n'est pas une erreur du moteur : c'est un modèle brut de 19,5 Md€
de réductions et crédits, sans les 10,3 Md€ de PFU ni la CEHR, comparé à un encaissement.
Les deux grands oublis se compensent en partie (+19,5 et −12,1). **Allumer les deux
imputations n'arrange pas la ligne** : estimé sur la population entière à partir de
l'échantillon, `ir` passerait à ≈ 105,9 Md€, +20 % contre le budget, parce que 8,9 Md€
de RICI restent non imputés et que le barème reste haut de 5,7 Md€.

**Les grandes niches dans les déclarations 2042** (`data/raw/dgfip_ir_2042_nat_export_
2026-10-15.csv`, https://data.economie.gouv.fr/explore/dataset/ir-declarations-2042-nat/ ;
les cases portent la **dépense déclarée**, pas l'avantage) :

| cases | 2022 | 2023 | 2024 | avantage publié 2024 |
|---|---|---|---|---|
| 7DB emploi à domicile | 4,68 M ; 13,03 | 4,91 M ; 14,19 | 5,19 M ; 15,37 | 6,52 |
| 7DR aides perçues (à déduire) | 0,37 M ; 0,83 | 0,41 M ; 1,02 | 0,43 M ; 1,16 | |
| 7GA-7GG garde < 6 ans | 2,25 M ; 3,96 | 2,30 M ; 4,38 | 2,33 M ; 4,61 | 1,79 |
| 7UF dons aux œuvres | 3,64 M ; 2,36 | 3,91 M ; 2,74 | 3,97 M ; 2,88 | 1,64 |
| 7UD dons, personnes en difficulté | 2,18 M ; 0,71 | 2,19 M ; 0,74 | 2,26 M ; 0,77 | 0,51 |
| 7XS-7XY reports de dons | 0,09 M ; 0,84 | 0,10 M ; 0,90 | 0,10 M ; 1,02 | |
| 7CD/7CE dépendance (hébergement) | 0,45 M ; 8,00 | 0,45 M ; 8,41 | 0,46 M ; 9,02 | 0,31 |
| 7AC-7AG cotisations syndicales | 1,38 M ; 0,23 | 1,41 M ; 0,24 | 1,44 M ; 0,25 | 0,15 |
| 7CF/7CH/7CI souscriptions PME | 0,04 M ; 0,44 | 0,05 M ; 0,41 | 0,03 M ; 0,28 | 0,10 |

(foyers ; Md€ de dépense déclarée.) Les 73 cases « Pinel » et 121 cases « Scellier » ne
s'additionnent pas : elles mêlent des prix d'acquisition et des reports de réduction déjà
calculés ; l'avantage publié des dispositifs locatifs est 1,73 Md€. La dépendance montre
le piège des réductions : 9,0 Md€ de dépenses déclarées pour 0,31 Md€ d'avantage, parce
qu'une réduction est plafonnée et **ne dépasse jamais l'impôt dû** ; les résidents en
établissement paient peu d'impôt.

### B. Les entreprises

**L'IS.** La base de 69,31 Md€ est la DGFiP de **2024** (bénéfices 283,95, IS brut
69,05 : +0,4 %), portée sous l'étiquette « millésime 2023 » parce que l'Ésane qui donne
la forme est de 2023. Elle est ensuite vieillie depuis 2023 par le PIB. Trois causes,
multiplicatives, chacune lue dans les séries du §3 :

| | 2022 | 2023 | 2024 |
|---|---|---|---|
| la base contre l'IS DGFiP de l'exercice | +1,5 % | +1,0 % | +0,4 % |
| le PIB ramène la base (0,9366 ; 1 ; 1,0358) | −6,3 % | 0 | +3,6 % |
| l'Insee (D51) contre l'exercice DGFiP | −12,5 % | −1,7 % | −1,6 % |
| **produit, contre l'écart de la grille** | **−16,8 %** | **+2,7 %** | **+5,6 %** |

(La troisième ligne est l'écart de l'exercice DGFiP à l'Insee, compté en sens inverse :
68,3/78,0, 68,6/67,5, 69,05/67,96.) Les produits retombent sur la grille au dixième.

* **Pourquoi le PIB ne suit pas les bénéfices.** De 2022 à 2024, le PIB nominal monte de
  10,6 % ; les bénéfices de la DGFiP de 2,1 % (2022 hors plus-values et brevets, champ
  voisin), l'IS brut par exercice de 1,1 %. Les
  marges de 2022 étaient hautes, le PIB de 2023 a été porté par les prix, et la hausse
  de l'EBE des SNF en 2023 (+15,9 %) ne s'est pas transmise au bénéfice fiscal
  (+1,6 %) : amortissements, charges financières, déficits reportés s'intercalent. Le
  PIB ramené en arrière fait baisser un IS qui, en réalité, n'a pas bougé.
* **Le double vieillissement de 2024.** La base est déjà celle de 2024 ; la multiplier
  par le PIB de 2024 sur 2023 ajoute 3,6 % qui n'existent pas. C'est la plus grande
  cause de l'écart de 2024, et elle passe dans chaque étude (voir §5).
* **L'année 2022 de l'Insee.** L'IS de l'Insee en 2022 (78,0) dépasse à la fois
  l'exercice 2022 de la DGFiP (68,3) et celui de 2021 (71,0). Le D51 des SNF fait le même
  saut (68,6 en 2022 contre 53,3 en 2021) quand leur EBE est plat (420,2 contre 423,1).
  **Hypothèse, non vérifiée** : le D51 de l'Insee suit le calendrier des paiements
  (acomptes calculés sur l'exercice précédent, record en 2021, et solde), pas le bénéfice
  de l'année. Aucun vieillissement d'un exercice ne reproduit ce saut. Une passe d'essai
  le montre : vieillir la base par l'IS DGFiP de chaque exercice (et non par le PIB)
  laisserait l'écart de 2022 à −12,1 %, celui de 2023 à +2,1 % et celui de 2024 à
  +2,0 % (calcul sur les séries du §3, sans passe).

**La contribution sociale.** Elle vaut 3,3 % de l'IS au-delà de 763 000 € : elle ne vit
que dans le haut de la distribution, que la couche dit elle-même ne pas affirmer.

* **Sa concentration, mesurée** (droit de 2024, sans vieillissement) : 1,403 Md€, dont
  0,787 portés par les 218 lignes GE et 0,468 par 1 653 lignes ETI ; les 100 premières
  lignes en portent 51,5 %, les 10 premières 17,6 %. Un tirage lognormal différent dans
  une cellule GE la déplace donc de plusieurs points.
* **Sa sensibilité, mesurée** : bénéfices des ETI et des GE ×0,85 ou ×1,15 → IS −8,9 %
  ou +8,9 %, contribution sociale −14,4 % ou +14,4 %. Elle bouge comme les bénéfices des
  grandes, l'IS comme la moyenne. La DGFiP montre que ces deux moyennes divergent : en
  2024, le résultat fiscal des GE baisse de 16,1 %, celui de l'ensemble de 4,9 % (n° 39,
  tableau 2). Le rapport CS/IS de l'Insee va de 2,04 % (2022) à 1,50 % (2023) et 1,72 %
  (2024) ; celui du modèle reste à 2,02 %.
* **La pente des tailles, mesurée.** Bénéfices du modèle contre la DGFiP 2024, par
  taille : micro 83,4 contre 65,9 ; PME 35,5 contre 78,5 ; ETI 69,1 contre 64,5 ; GE
  96,0 contre 75,0 Md€. IS : micro 19,5 contre 14,0 ; PME 8,5 contre 19,2 ; ETI 17,3
  contre 16,2 ; GE 24,0 contre 19,6. Ramener les bénéfices de chaque taille sur ceux de
  la DGFiP donne une contribution sociale de 1,205 Md€ (au lieu de 1,403), +3,3 % sur
  l'Insee de 2024. **Réserve** : les tailles de l'Insee (entreprises profilées, groupes)
  et celles de la DGFiP (n° 39 compte 400 GE et 220 600 PME, contre 311 et 162 238 à
  l'Insee) ne sont pas les mêmes ; `cells.py` refuse pour cette raison les effectifs de
  la DGFiP par taille. La pente peut être une différence de nomenclature autant qu'une
  erreur. **À trancher** en lisant la définition des tailles du n° 39.
* **Un artefact du tirage, mesuré** : 5 lignes « micro » (3 121 entreprises pondérées)
  paient 0,141 Md€ de contribution sociale, soit 10 % du total. Ce sont des tirages de la
  queue lognormale : 62 193 micro-entreprises pondérées ont un chiffre d'affaires au-delà
  de 2 M€ et portent 52,9 des 83,4 Md€ de bénéfices des micro ; une a 56 M€ de chiffre
  d'affaires et 24 M€ de bénéfice.
* **Décomposition 2024 (+24,6 %)** : +20,3 % sans vieillissement (1,403 contre 1,166),
  puis +3,6 % de PIB. Des 20,3 points, la pente des tailles en explique au plus 17 (sous
  la réserve dite), l'artefact micro au plus 12, les deux se recouvrant ; non séparés.
  **2023 (+38,6 %)** : même base, contre le creux de l'Insee (1,01, −36 % sur 2022 quand
  l'IS ne baisse que de 13,5 %). **2022 (−17,4 %)** : le PIB ramène la base de 6,3 %, et
  l'Insee de 2022 est au sommet, comme son IS. Le modèle a un rapport CS/IS fixe ; le
  monde ne l'a pas.

**La C3S.** La base est le chiffre d'affaires de l'Ésane 2023, et la C3S due en 2024 est
assise sur celui de 2023. Comparée au bon millésime, la base tombe juste : 5,289 contre
5,228 Md€ en 2024, **+1,2 %**. La grille lui applique au contraire le PIB de 2024 sur
2023 (+3,6 %), et, en remontant, le PIB d'une année au lieu du chiffre d'affaires de
l'année d'avant. Avec le décalage d'un an et la production des SNF (T_7101) comme indice
du chiffre d'affaires : 2023, 5,289 × 3 664/3 800 = 5,10 contre 4,81, **+6,0 %** ; 2022,
5,289 × 3 148/3 800 = 4,38 contre 4,27, **+2,5 %** (calcul, sans passe). Le décalage et
l'indice expliquent donc l'essentiel de +16 / +10 / +5 %.

**La CVAE 2024 (−12,1 %)** : −15,1 % sans vieillissement (3,282 contre 3,868), puis
+3,6 % de PIB. Causes **non mesurées** : la valeur ajoutée comptable de l'Ésane sous-estime
celle de la CVAE (loyers et crédit-bail ne s'y déduisent pas, `variables.py:312`) ; la
section K (finance) est presque absente de la couche (6,4 Md€ de valeur ajoutée, contre
des banques et assureurs redevables de la CVAE) ; la CVAE de 2024 se calcule sur la
valeur ajoutée de 2024, pas de 2023. L'Insee suit bien le taux de l'année : 3,87/5,20 =
0,744 pour un taux plafond passé de 0,375 % à 0,28 % (0,747).

---

## 5. Ce que l'écart fait aux études

### A. L'impôt sur le revenu

Les études qui touchent l'IR : le **PLF 2027** (art. 2, revalorisation du barème,
+2,85 Md€ contre +4,20 officiels, hors tolérance ; art. 3, plafond de l'abattement des
pensions, −1,12 contre −1,10), **Tondelier** (tranche à 60 %), **Le Pen** (part entière
dès le deuxième enfant, −2,70 Md€ d'IR), **Lisnard** (déplafonnement du quotient), et par
ricochet **Attal** (« droit au brut » : le salaire imposable monte quand les cotisations
baissent).

**Une hausse de barème sans réductions coûte-t-elle plus ? Oui, à peine.** Les crédits
sont remboursables et ne dépendent pas de l'impôt : ils ne changent aucun coût. Une
réduction ne dépasse jamais l'impôt : quand l'impôt baisse sous la réduction, la baisse
est « absorbée ». Mesuré sur l'échantillon (droit de 2024, avec et sans les niches
imputées) :

| réforme d'essai | Δ au barème | Δ net, niches imputées | part absorbée |
|---|---|---|---|
| tranches revalorisées de 2,1 % | −2,510 | −2,504 | 0,23 % |
| tranche à 60 % au-delà de 250 000 € | +0,853 | +0,853 | 0,00 % |
| part entière au 2e enfant | −2,714 | −2,711 | 0,10 % |
| abattement des pensions plafonné à 3 000 € | +1,106 | +1,105 | 0,07 % |
| +1 point sur chaque tranche | +6,888 | +6,876 | 0,18 % |

L'imputation ne porte que 2,06 Md€ de réductions (les dons) sur les 9,75 publiés. **Hors
mesure, hypothèse** : si toutes les réductions absorbaient au même rythme, la part
absorbée serait multipliée par 4,7 au plus, soit ≈ 1 % ; les réductions qui ne sont pas
imputées (dépendance, outre-mer, Pinel) sont justement celles qui saturent l'impôt, ce qui
peut la porter un peu plus haut pour une réforme du bas du barème. C'est petit devant le
biais de niveau du barème (+6 à +10 %) et devant les 15 % de foyers qui manquent.

Le PFU et la CEHR ne bougent avec aucune de ces réformes (la CEHR suit le RFR, pas
l'impôt). La CDHR, droit de 2025, capital imputé à l'indice 1 (hypothèse déclarée) :
0,07 Md€ seulement dans le modèle (l'Insee : 0,37 en 2025) ; elle baisse de 0,025 Md€
quand une hausse d'un point rapporte 6,84, et ne bouge pas avec la tranche à 60 %
(mesuré sur l'échantillon).

**Ce qui bouge davantage** : le nombre de foyers imposés (18,87 M sans niches, 17,63 M
avec, −6,6 %) et donc les colonnes « gagnants / perdants » des déciles. Une page qui dit
« X % des foyers gagnent » à une réforme du barème le dit sur une population où personne
n'efface son impôt par un crédit.

**L'écart de l'art. 2 (−30 %) ne vient pas des niches** : elles ne pourraient que réduire
le coût simulé, qui est déjà sous l'officiel.

### B. Les entreprises

Les études qui touchent la couche : **PLF 2027 art. 15** (CEBGE, −7,05 Md€ contre −5,50
officiels), **Attal** (suppression de la CVAE, +2,55 Md€ en 2026), **Lisnard** et
**Retailleau** (C3S et CVAE, +6,55 Md€, dont ≈ 4,0 de C3S et 2,55 de CVAE, nets du retour
d'IS de D-347). **Mélenchon** (fin des allègements au-dessus de 2 SMIC) est chiffré dans
la couche ménages et publié « brut d'IS » : le niveau de l'IS n'y entre pas, mais son
retour (jusqu'à 25 % du montant) manque. **Le Pen** n'a aucune mesure d'entreprise dans
sa part chiffrée (TVA et quotient).

* **Le double vieillissement (+3,6 %) passe en entier dans chaque coût** de la couche :
  un coût est la différence de deux passes, multipliée par le facteur du PIB depuis 2023
  (1,087 en 2026) ; partir de 2024 donnerait ≈ 1,049. Les coûts d'entreprises de toutes
  les études sont donc hauts de ≈ 3,6 % : ≈ 0,09 Md€ pour Attal, ≈ 0,24 pour Lisnard et
  Retailleau, ≈ 0,25 pour la CEBGE.
* **La CVAE** est basse de 12 à 15 % : les suppressions d'Attal, de Lisnard et de
  Retailleau sont sous-chiffrées d'autant sur leur part CVAE, ≈ 0,35 à 0,45 Md€,
  partiellement compensés par le +3,6 %.
* **La C3S** est juste à son bon millésime : le seul biais est le +3,6 % (≈ 0,15 Md€).
* **La CEBGE** (art. 15) se calcule sur l'IS des groupes de plus de 1,5 Md€ de chiffre
  d'affaires : elle lit la cellule GE. Les bénéfices des GE du modèle dépassent ceux de la
  DGFiP de 28 % (96,0 contre 75,0), et le chiffrage dépasse l'officiel de 28 %
  (7,05 contre 5,50). **Hypothèse, non vérifiée** : les deux sont la même chose. Mais la
  CEBGE s'apprécie au niveau du groupe intégré, plus proche des GE profilées de l'Insee
  que d'un découpage par unité légale ; la coïncidence ne prouve rien tant que la
  nomenclature du n° 39 n'est pas lue.
* **Une réforme du taux d'IS** (l'explorateur, D-246 : un point coûte 3,10 / 3,38 Md€ en
  2026) est proportionnelle à la base : +3,6 % de trop. Le saut de l'Insee en 2022 ne
  touche aucune étude : il n'est que dans le juge.

---

## 6. Le correctif proposé

Aucun correctif n'est appliqué. Chaque pronostic est à préenregistrer dans une D-entrée
avant toute passe ; les lignes de `lignes.json` ne changent pas après le calcul, un juge
nouveau est une ligne nouvelle.

### A. L'IR net

* **A1. Une ligne « IR net » comparable.** Le modèle : `ip_net − RICI + PFU + CEHR`,
  niches et capital imputés. Le juge : l'impôt net du n° 41 (91,61 Md€), le budget
  restant en contexte avec son pont de 3,62. Données : déjà dans `data/raw`. Coût : une
  passe de base de plus. Risque : la ligne devient en partie calée (le PFU et 10,6 des
  19,5 Md€ de RICI), à dire sur la ligne. **Pronostic : +16 % (+14 à +18).**
* **A2. Imputer les RICI manquantes** : scolarité (cases 7EA, 7EC, 7EF du 2042, des
  nombres d'enfants), dépendance (7CD), outre-mer, dispositifs locatifs (l'avantage du
  n° 41), autres ; sortir les 3,83 Md€ de « source étrangère » des deux côtés. Données :
  le 2042 et le n° 41, déjà là. Coût : moyen. Risque : les bases tirées par décile
  ignorent qui déclare ; la dépendance demande l'âge. **Pronostic, avec A1 : +6 à
  +10 %**, il ne reste que le biais du barème.
* **A3. Imputer les niches par défaut** dans les études qui touchent l'IR. Coût : une
  passe de base de plus par étude. Risque : aucun sur les coûts (≤ 0,25 % mesuré).
  **Pronostic : coûts ±0,3 % ; foyers imposés −6,6 %**, et les colonnes « gagnants ».
* **A4. Le biais du barème lui-même** (foyers −15 %, revenus non salariaux absents) :
  hors de ce volet.

**Recommandation** : A1 d'abord (une ligne, aucun code de calcul), A2 ensuite. A3 est une
décision du propriétaire : il ne change pas un coût, il change ce que la page dit des
gagnants.

### B. Les entreprises

* **E1. Dater la couche de 2024** (`BASE_FIRMES = 2024` pour l'IS et la contribution
  sociale, `verification.py:32` et le facteur des études). Données : déjà là. Coût : une
  constante, et la réécriture des études. Risque : toutes les études d'entreprises
  baissent de ≈ 3,6 %. **Pronostic IS : 2022 −20 % (−21 à −18), 2023 −1 % (−2 à +1),
  2024 +2 % (+1 à +3).**
* **E2. Vieillir l'IS par l'IS DGFiP de l'exercice** pour les années constatées, par le
  PIB au-delà. Données : IA112 et n° 39, déjà là. Coût : petit. Risque : l'IS devient
  calé chaque année et la ligne ne teste plus que la forme. **Pronostic IS : 2022
  −12 %, 2023 +2 %, 2024 +2 % (±1).**
* **E3. La C3S sur le chiffre d'affaires de l'année d'avant**, indexé par la production
  des SNF. Données : T_7101 (à manifester). Coût : petit. **Pronostic C3S : 2022 +3 %,
  2023 +6 %, 2024 +1 % (±2).**
* **E4. Borner le tirage** : aucune micro-entreprise à 7,63 M€ de chiffre d'affaires ou
  plus, aucune PME au-delà de son seuil. Coût : petit. Risque : change la forme des
  cellules et l'incidence par taille. **Pronostic contribution sociale 2024 : de
  +25 % à +10 à +15 %.**
* **E5. Lire la nomenclature des tailles du n° 39** ; si elle est celle de l'Insee,
  recaler les bénéfices par taille. Coût : une lecture. Risque : si les nomenclatures
  diffèrent, recaler serait une erreur. **Pronostic : contribution sociale 2024 +3 à
  +8 % ; CEBGE de l'art. 15 −20 à −25 %.**
* **E6. La CVAE** : une valeur ajoutée fiscale (loyers et crédit-bail réintégrés) et la
  finance. Données : non trouvées par cellule. **Pronostic CVAE 2024 : −5 à −10 %.**
* **E7. Un juge par exercice** (IS brut DGFiP) à côté de l'Insee. Données : IA112, n° 39.
  Risque : avec E2, ce juge devient calé.

**La contribution sociale reste volatile quoi qu'on fasse au modèle.** Avec E1 et E4
(base sans les lignes micro, 1,262 Md€) : −28 % en 2022, +20 % en 2023, +8 % en 2024 ;
avec E2 à la place du PIB : −22 %, +24 %, +8 % (calcul sur les séries, sans passe). C'est
le juge qui bouge : la série de l'Insee va de 1,01 à 1,59 en deux ans. Seul un juge par
exercice la stabiliserait, s'il existe (non trouvé pour la contribution sociale seule).

**Ce qui se gagnerait avec des bénéfices par année** : la DGFiP par exercice (IA112 et
n° 39) donne l'IS de l'année, à 2 % de l'Insee en 2023 et 2024 (mais de −7 à +15 % de
2016 à 2022 : les deux statistiques ne datent pas l'IS pareil) ; l'EBE des SNF ne le donne
pas (+15,9 % d'EBE en 2023 pour +1,6 % de bénéfice) et ne doit pas servir d'indice ; les
comptes des SNF donnent la production, bon indice de la C3S. Le saut de l'Insee de 2022
ne se gagne par aucune donnée de bénéfice, si l'hypothèse du calendrier (§4 B) tient.

---

## 7. Comment l'expliquer au public

**L'impôt sur le revenu.** Le simulateur calcule bien l'impôt du barème, à 6 à 10 %
près. Il ne calcule pas, par défaut, ce que les ménages retirent de cet impôt (emploi à
domicile, garde d'enfants, dons : 19,5 milliards) ni ce qu'ils paient en plus sur leur
épargne (prélèvement forfaitaire : 10,3 milliards). Comparé à l'argent que l'État encaisse,
il paraît donc trop haut de 19 %. Pour chiffrer une réforme du barème, l'oubli ne coûte
presque rien : une réduction d'impôt ne change le coût d'une réforme que pour les foyers
dont elle efface tout l'impôt, et nous l'avons mesuré à moins de 0,3 %.

*La preuve* : un tableau en escalier, côte à côte, la DGFiP et le simulateur, du barème
à l'impôt net (le tableau du §4 A), chaque marche avec sa source. Le lecteur peut allumer
ou éteindre les niches et le capital et voir chaque marche bouger, et la ligne des coûts
de réforme rester immobile.

**Les entreprises.** Le simulateur part des bénéfices déclarés de 2024 et les fait
évoluer comme le PIB. Mais les bénéfices n'ont pas suivi le PIB : ils sont restés plats
de 2022 à 2024 quand le PIB montait de 10 %. Et l'impôt sur les sociétés que publie
l'Insee saute en 2022 parce qu'il suit les dates de paiement, pas les bénéfices de
l'année. La contribution sociale, payée par quelques centaines de grands groupes, amplifie
tout cela.

*La preuve* : un graphique de 2016 à 2025 avec trois courbes, l'IS de l'Insee, l'IS de
la DGFiP par exercice et l'IS du simulateur ; un lecteur y voit que le simulateur reste à
5 % de la seconde les trois années et que l'écart de 2022 est entre les deux statistiques
publiques. Ce
qu'il pourrait faire varier : l'indice de vieillissement (PIB, IS par exercice,
production), l'année de base de la couche, et la part des bénéfices des grands groupes.

---

## Annexe C. Les cotisations à la charge des salariés (−9 à −12 %)

**Le modèle**, mesuré sur l'échantillon (2024, 121,3 Md€ contre 119,68 sur la population
entière) : taux effectif de 10,78 % du brut. Privé non cadre 11,01 % (vieillesse
plafonnée 45,6, déplafonnée 3,4, Agirc-Arrco 37,0, CEG 7,7, CET 0,6) ; titulaires
10,12 % (pension civile 21,5, RAFP 1,9) ; non-titulaires 9,67 % (Ircantec 1,3). Valent
**zéro** : l'assurance chômage salariale (juste depuis 2018), la cotisation maladie
d'Alsace-Moselle (`mmid_salarie`), l'APEC (aucun cadre).

**Le juge** : D613CE, « cotisations sociales effectives obligatoires à la charge des
salariés », compte des ménages T_7401 (sha256 f27bfdff…, celui de `lignes.json`).

**La décomposition de 2024 (−11,6 %, −15,8 Md€)**, mesurée sauf mention :

* **L'assiette, −2,6 %.** Le brut du modèle (1 107,7) est calé sur le D11 versé par les
  employeurs résidents (1 111,65, tableau 6205, `margins.TOTAL_GROSS_WAGES`), alors que
  le juge est du côté des ménages, dont le D11 reçu vaut 1 137,2 (T_7401, ligne 40) : la
  différence, 25,6 Md€, est pour l'essentiel le salaire reçu du reste du monde
  (frontaliers ; hypothèse sur la nature, le montant est lu).
* **Le taux, −9,3 %** : 10,80 % contre 135,44 / 1 137,2 = 11,91 %, soit ≈ 12,6 Md€.
  **Hypothèse principale, non vérifiée** : D613CE contient des cotisations à des régimes
  que le modèle ne porte pas, les régimes privés obligatoires d'entreprise (santé,
  prévoyance, retraite supplémentaire) et les régimes étrangers des frontaliers. L'indice
  est lu : en 2024, les ménages versent 329,3 (D611) + 171,6 (D613) = 501,0 Md€ de
  cotisations effectives, et les administrations publiques n'en reçoivent que 432,4
  (t_3201 : D61 483,63 moins imputées 51,24) ; 68,6 Md€ vont ailleurs, et le compte des
  ménages porte une rémunération du service des régimes d'assurance sociale (D61SC,
  −10,8). La part salariale de ces 68,6 Md€ n'est **pas trouvée** : DREES (comptes de la
  protection sociale) refuse le conteneur (connexion réinitialisée).
* Petits trous, **non chiffrés** : Alsace-Moselle, APEC.

**Ce que cela fait aux études** : « droit au brut » d'Attal (cotisations de retraite des
salariés ×0,22, 56,98 Md€ côté ménages) est proportionnel à cette assiette. Si l'écart est
fait de régimes privés et étrangers, que la mesure ne touche pas, le coût est juste ; s'il
est fait de cotisations publiques manquantes, il est sous-chiffré d'au plus ≈ 10 %.

**Le correctif** : juger la ligne sur les cotisations salariales **reçues par les
administrations publiques** (à trouver dans les comptes détaillés des ASSO, ou la DREES
hors du conteneur), et caler le brut sur le même champ que le juge. Pronostic, si
l'hypothèse tient : de −12 / −9 % à −5 / 0 %.

---

## Les deux URL longues

Laissées entières pour rester copiables ; elles sont aussi dans `data/raw/MANIFEST.json`.

* [n41] DGFiP Statistiques n° 41 : https://www.impots.gouv.fr/sites/default/files/media/9_statistiques/0_etudes_et_stats/0_publications/dgfip_statistiques/2025/num41_11/dgfip_stat_41.xlsx

* [n39] DGFiP Statistiques n° 39 : https://www.impots.gouv.fr/sites/default/files/media/9_statistiques/0_etudes_et_stats/0_publications/dgfip_statistiques/2025/num39_09/dgfip_stat_39_limpot-sur-le-benefice-2024-des-entreprises.xlsx
