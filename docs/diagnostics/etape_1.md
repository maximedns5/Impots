# Étape 1 du but 19 : les textes faux, et une grille qui compare ce qu'elle doit

Agent de l'étape 1, 10 novembre 2026, branche `claude/but19-e1`. Rien ne touche la
construction de la population. Aucune passe d'étude, aucune passe de la grille sur la
population entière. Les essais sont sur 15 000 ménages (`runner.subsample`, graine
20240101) ; leurs scripts et sorties sont dans `/tmp/etape1/essai/`.

## 1. Ce qui a changé, fichier par fichier

### Les pages d'étude (commit a8d3281)

* `src/impots/etude.py`, `_boucle` : « Sans aucun effet sur l'activité, la dette
  serait… » lisait le coin `multiplicateur_macro = 0` de la boîte θ (le multiplicateur au
  bas de sa fourchette publiée, θ = 0, pas à zéro). La phrase lit désormais la marche « le
  coût, sans boucle » de la décomposition de D-349 (`path.lectures.decomposition.vieillie
  .cout`), déjà dans chaque rapport `predictif_*.json` : aucun calcul, aucun rejeu. Elle
  dit « le coût seul, sans la boucle macro », ou « le coût après les comportements, à θ½,
  sans la boucle macro » quand la ligne a une bande. Conséquence voulue : la phrase paraît
  aussi sur les lignes dont la boîte porte d'autres paramètres que le multiplicateur, qui
  ne l'avaient pas (le coin à une seule clé n'existait pas chez elles).
* `etude.py`, `raison_bande` et la tête « Ce que dit cette étude » : une réforme des
  cotisations des salariés (`cotisations_salariales_*`, Attal et Retailleau) n'a pas de
  bande par un choix du modèle, pas faute d'étude : le canal de l'offre de travail (C7,
  Bargain, Orsini et Peichl) ne revendique que `csg_activite_deductible` et
  `csg_activite_imposable` (`behavioural/parameters/labour_supply.yaml`,
  `responds_to_knobs` ; D-220 : une seule variation du salaire net par personne y suffit,
  l'assiette de la CSG étant presque tout le brut, quand celle des cotisations de retraite
  est en partie plafonnée). Le texte vrai est `etude.RAISON_OFFRE_DE_TRAVAIL` ;
  `raison_bande` prend la réforme.
* `src/impots/site_explorer/explorer.js` : l'explorateur disait « verdict » pour le signe
  de la boîte θ ; il dit « selon θ », comme la colonne des pages, et précise que le verdict
  des pages lit le Monte-Carlo. `verdictOf` devient `selonTheta`. Le test qui tient
  l'explorateur contre la chaîne (`tests/test_page_explorer.py`) reste vert.
* `docs/etudes/*.md` et `site/*.html` réécrits par `impots etude ecrire` (dix études) et
  `impots site construire` ; `etude verifier` (dix) et `site verifier` passent.

**Chaque nombre affiché qui change, page par page** (dette de 2035, points de PIB, vue
vieillie, « sans aucun effet sur l'activité ») :

| page | ligne | avant | après |
|---|---|---|---|
| presidentielle_attal | la part chiffrée | +13,95 | +18,30 |
| presidentielle_labib | la part chiffrée | +5,71 | +5,90 |
| presidentielle_le_pen | la part chiffrée | +3,98 | +4,42 |
| presidentielle_retailleau | la part chiffrée | +3,98 | +4,69 |
| presidentielle_roussel | la part chiffrée | +1,42 | +1,56 |
| plf2027 | art. 3 | −0,35 | −0,40 |
| plf2027 | art. 2 | absent | +0,97 (après comportements, à θ½) |
| presidentielle_lisnard | la part chiffrée | absent | +11,23 (après comportements, à θ½) |
| presidentielle_melenchon | la part chiffrée | absent | −2,28 |
| presidentielle_tondelier | la part chiffrée | absent | +0,01 (après comportements, à θ½) |

Ces nombres étaient déjà sur chaque page, colonne « le coût, sans boucle » du tableau
« D'où vient Δb ». Le PLFSS 2027 et l'art. 15 du PLF ne changent pas (aucun effet sur
l'activité n'y est lu). Les textes : Attal et Retailleau disent « il n'ouvre pas aux
cotisations des salariés le canal de l'offre de travail qu'il ouvre à la CSG, un choix du
modèle » au lieu de « aucune étude publiée ne le permet ici », et leur paragraphe « Bande
comportementale » donne la raison vraie. Aucun autre nombre ne bouge.

### La grille (commit suivant)

* `src/impots/population/runner.py` : `employeurs_d121(built)` et trois sorties neuves de
  la passe de population (pas de `outputs.REGISTRY`, l'API n'en voit pas de champ neuf) :
  * `prelevements_salaires_d291` : `PRELEVEMENTS_D291`, onze variables d'OpenFisca que
    `cotisations_employeur` somme et que l'Insee classe en impôts sur les salaires
    (`contribution_unique_formation_professionnelle_alternance`,
    `contribution_solidarite_autonomie`, `fnal`, `ags`, `taxe_salaires`, `forfait_social`,
    `versement_transport`, `participation_effort_construction`,
    `contribution_developpement_apprentissage`,
    `contribution_supplementaire_apprentissage`, `conge_individuel_formation_cdd`) ; les
    sept dernières valent zéro aujourd'hui, listées pour qu'un câblage futur les sorte ;
  * `pension_employeur_etat` : `pension_employeur` des mois où la personne est
    `public_titulaire_etat` ou `public_titulaire_militaire` (D122). La CNRACL reste en
    D121. L'ATI de l'État (`ati_atiacl`, 0,3 Md€ au diagnostic) reste en D121 :
    hypothèse ;
  * `remuneration_hors_brut` : `indemnite_residence` + `supplement_familial_traitement`.
* `src/impots/population/aggregate.py` : les trois noms entrent dans `INSTRUMENTS`
  (totaux ; aucun coût, aucune partie double ne les lit).
* `src/impots/verification.py` :
  * `employeurs(t)` : la mesure « salaire_super_brut − salaire_brut − D291 − pension de
    l'État − hors brut » et les trois parts, chacune à part. La mesure de D-363
    (`salaire_super_brut - salaire_brut`) reste telle quelle ;
  * `mesures_ir_net` : l'IR net comparable (§ 3, ligne D) d'une passe à part, tier
    léger, niches et capital imputés, par lots ; chaque lot pèse la France entière le
    temps de son imputation (voir § 5, le défaut trouvé) ; `indice_capital` vieillit le
    capital imputé de 2024 par l'impôt hors barème publié (`HORS_BAREME`). La passe de la
    grille coûte une passe légère imputée de plus par année (≈ 45 s pour 15 000 ménages
    sur l'essai ; ordre de grandeur sur la population entière : quelques minutes par
    année, non mesuré) ;
  * `MILLESIME_FIRMES = "2023"` nomme le fichier (`firms_2023.parquet`, non renommé) ;
    `BASE_FIRMES` vaut désormais `firmes.base_year("2023")` = **2024**.
* `src/impots/predictif/firmes.py` : `ANNEE_DES_IMPOTS = {"2023": 2024}`. Le millésime
  « 2023 » a la forme de l'Ésane 2023, mais `entreprises/cells.py` fixe ses bénéfices sur
  ceux de la DGFiP de 2024 (`entreprises/margins.TAXABLE_PROFIT`, 283,95 Md€, year=2024) ;
  son IS au droit de 2024 est celui de la DGFiP (69,31 contre 69,05 Md€), et son chiffre
  d'affaires de 2023 est l'assiette de la C3S de 2024 (`margins.C3S_2024`). `base_year`
  rend 2024 : la vue vieillie des études (`aging_factor`) part de 2024, et ses notes le
  disent (« depuis 2024, l'année de ses bénéfices »). Seule la CVAE, sur la valeur
  ajoutée de 2023, reste un an en arrière (≈ −1 à −3 %, non mesuré).
* `src/impots/population/cli.py`, `_vieillir_entreprises` : la même année de base pour
  l'enregistrement des chiffrages d'entreprises vieillis.
* `src/impots/population/margins.py` : `FILOSOFI_URL` =
  <https://www.insee.fr/fr/statistiques/2012717> (vérifiée : « Niveau de vie en 2023 »,
  fichier `TCRD_022.xlsx`, sha256 1331aa54…65a5, feuille REG, ligne « France
  métropolitaine » : médiane 25 920, D1 13 200, D9 46 500 ; l'ancienne page 8402386 rend
  404). Les déciles D2 à D8 (17 010 … 38 100) ne sont sur aucune publication relue :
  retirés de `NIVEAU_DE_VIE_DECILES` (rien ne les lisait), qui garde D1, D5 et D9. Le
  Gini 0,297 n'est pas sur cette page non plus : il reste, avec une réserve « non
  retrouvé » (rien ne le lit) ; le D9/D1 de 3,5 en découle (46 500 / 13 200 = 3,52).
  Aucun nombre ne change.
* `data/raw` (hors git) et `data/raw/MANIFEST.json` : quatre sources ajoutées, URL,
  sha256, octets, date : DGFiP n° 32 (`dgfip_stat_32_2025.xlsx`, le même fichier que
  celui en quarantaine sans URL), DGFiP n° 22 (`dgfip_stat_22_ir_2022.xlsx`), Filosofi
  `insee_filosofi_2023_TCRD_022.xlsx`, et le T_7401 que `lignes.json` cite
  (`insee_cn2026_T_7401_compte_menages.xlsx`, sha256 f27bfdff…, le même).

## 2. Les mesures sur échantillon, contre les totaux publiés

15 000 ménages, graine 20240101, un essai par année (loi de l'année, population de 2024
ramenée par les indices constatés de D-362). **Ces mesures ne sont pas aveugles** : je les
ai vues avant d'écrire les pronostics du § 3. La masse salariale de l'échantillon dépasse
celle de la population de 0,47 % chaque année ; la colonne « à la masse » divise les
mesures de salaires d'autant. L'IR de l'échantillon est 1,5 % sous celui de la population
(barème : 102,95 contre 104,53 Md€ en 2024).

| mesure (Md€) | 2022 | 2023 | 2024 |
|---|---:|---:|---:|
| super-brut − brut (mesure de D-363) | 393,96 | 411,12 | 423,49 |
| − prélèvements D291 | 15,91 | 16,66 | 17,53 |
| − pension de l'État | 66,74 | 69,85 | 71,69 |
| − salaires hors brut | 2,75 | 2,86 | 2,92 |
| **= D121 du modèle** | **308,56** | **321,75** | **331,35** |
| D121 publié (T_7401, l. 42) | 298,90 | 314,36 | 329,34 |
| écart brut / à la masse | +3,2 / +2,7 % | +2,4 / +1,9 % | +0,6 / +0,1 % |
| avant (super-brut − brut, grille D-364) | +33,0 % | +31,9 % | +29,7 % |
| D291 que le modèle calcule, publié (4 lignes) | 16,60 | 17,38 | 18,37 |
| écart, à la masse | −4,6 % | −4,6 % | −5,0 % |
| pension de l'État contre D122 (66,0 / 68,7 / 72,4) | +0,6 % | +1,2 % | −1,5 % |
| IR net, niches et capital imputés | 95,03 | 98,78 | 104,66 |
| IR net publié | 82,1 | 83,5 | 91,62 |
| écart brut | +15,7 % | +18,3 % | +14,2 % |
| écart ramené au barème de la population | ≈ +17,5 % | ≈ +20,2 % | ≈ +16,0 % |
| dont RICI imputées | 9,20 | 9,90 | 10,56 |

La pension de l'État de cet échantillon (71,7 Md€ en 2024) est sous celle du diagnostic
(77,3 sur 20 000 ménages) : les titulaires de l'État sont peu nombreux et lourds, le
tirage les fait varier ; la mesure D121 retombe pourtant au même point (331,3 dans les
deux), parce que le super-brut bouge avec eux.

**L'imputation par lots**, mesurée une fois (2024, même échantillon) : en un seul lot,
RICI 10,56 et IR 104,66 Md€ ; en quatre lots corrigés, 10,52 et 105,54 (+0,8 %, terme
d'échantillonnage des lots, non expliqué plus avant) ; en quatre lots par
`households_par_lots` tel qu'il est, **RICI 40,01 et IR 76,11** : le défaut du § 5.

## 3. Le préenregistrement proposé

Lignes neuves de `docs/verification/lignes.json`, une par année (2022, 2023, 2024). Les
pronostics viennent de l'essai du § 2 : ils ne sont pas aveugles, la D-entrée doit le dire.

**A. `cotisations_employeurs_d121`** — « Cotisations effectives des employeurs au sens
D121 (hors impôts sur les salaires, pension de l'État et salaires hors brut) ».
`modele` : « salaire_super_brut - salaire_brut - D291 - pension de l'État - hors brut ».
Publié : D121, Insee T_7401 (édition mai 2026), feuille T_7401, ligne 42, 298,904 /
314,359 / 329,335 Md€, [T7401], sha256 f27bfdff…826e. Tolérance ±15 % (celle de
D-363 : D121 compte la prévoyance d'entreprise, absente). Usage : validation. Raison : la ligne de D-363 comparait un
agrégat qui contient 97 Md€ que D121 ne compte pas. La ligne est tenue en partie par
compensation (prévoyance, AT à 0,64 %, frontaliers, contractuels lus titulaires tirent
vers le bas ; un surplus non identifié vers le haut). **Pronostic** : 2022 de −3 à
+6 %, 2023 de −3 à +5 %, 2024 de −4 à +4 % ; dans la tolérance les trois années.

**B. `impots_salaires_calcules`** — « Impôts sur les salaires que le moteur calcule
(formation et apprentissage, Fnal, CSA, AGS) ». `modele` : `prelevements_salaires_d291`.
Publié : Insee t_3217 (2026), lignes 42 + 44 + 45 + 47, 16,604 / 17,378 / 18,367 Md€,
<https://www.insee.fr/fr/statistiques/fichier/8988845/t_3217_fr.xlsx>, sha256 589b94cf….
Tolérance ±20 % (taux légaux sur une assiette calée ; l'effectif nul prend le Fnal des
moins de 50 salariés, 0,10 % plafonné, au lieu de 0,50 % déplafonné au-delà). Usage :
validation. **Pronostic** : de −10 à 0 % les trois années (essai : −4,6 à −5,0 %).

**C. `impots_salaires_d291`** — « Impôts sur les salaires et la main-d'œuvre (D291),
total ». Même `modele`. Publié : t_3217 ligne 39, 52,143 / 55,098 / 58,131 Md€. Usage :
contexte, sans tolérance : le moteur n'a ni la taxe sur les salaires, ni le versement
mobilité, ni le forfait social, ni la PEEC, ni la contribution sur les stock-options
(≈ 40 Md€). **Pronostic** : de −72 à −66 %.

**D. `pension_etat_d122`** — « Contribution de l'État aux pensions de ses titulaires,
contre les cotisations imputées (D122) ». `modele` : `pension_employeur_etat`. Publié :
T_7401 ligne 43, 66,021 / 68,726 / 72,435 Md€. Usage : contexte (D122 compte d'autres
employeurs ; les titulaires du modèle comprennent des CDI, D-346). **Pronostic** : de
−8 à +8 %.

**E. `ir_net`** — « Impôt sur le revenu net (barème, hors barème, CEHR, moins réductions
et crédits) ». `modele` : « ir, niches et capital imputés » (`impot_revenu_restant_a_payer`
d'une passe imputée). Définition retenue : la proposition A1 du diagnostic, parce que c'est
la seule passe où le modèle porte les quatre termes que la DGFiP additionne ; le juge est
l'IR net des avis d'imposition, pas les recettes budgétaires (le budget mêle deux années
de revenus et les restitutions : 3,6 Md€ d'écart non expliqués). Publié :
* 2022 : 82,1 Md€, DGFiP Statistiques n° 22 (avril 2024), onglet « Graphique 1 », ligne
  2022, « Montant d'émission IR » (hors crédit d'impôt PFU, données de février) ; même
  valeur dans le n° 32 ; [n22], sha256 ca584091… ;
* 2023 : 83,5 Md€, DGFiP n° 32 (avril 2025), onglet « Graphique 1 », ligne 2023 ;
  [n32], sha256 d8721958… ;
* 2024 : 91,62 Md€, DGFiP n° 41 (novembre 2025) : tableau 2, impôt au barème 98,843 +
  impôt hors barème 10,32 + CEHR 1,98 ; moins tableau 3, « Crédits et réductions
  d'impôt » 19,525 (hors RICI PFU). Le texte du n° 41 dit « 92 Md€ » ; la somme du
  graphique 1 (83,5 + 8,26 = 91,76) ajoute 0,15 Md€ de « petites impositions » que le
  modèle n'a pas. Fichier `data/raw/dgfip_stat_41_impot_revenu_2024_donnees.xlsx`, URL
  [n41] du diagnostic `ir_net_et_entreprises.md`.

Tolérance proposée ±15 % : l'impôt au barème a ±10 % (D-363), et 8,9 Md€ de RICI
publiées (scolarité, dépendance, outre-mer, dispositifs locatifs, source étrangère) ne
sont pas imputables par le code actuel. Le PFU (par `indice_capital`, une hypothèse
déclarée qui cale le hors-barème de chaque année) et 10,6 des 19,5 Md€ de RICI sont
calés : la ligne le dit. **Pronostic** : 2022 de +13 à +21 %, 2023 de +16 à +23 %, 2024
de +13 à +19 % ; hors de ±15 % au moins en 2023, probablement les trois années. C'est le
biais du barème (+6 à +10 %) et les RICI non imputées, pas le passage au net.

**F. Les lignes des entreprises existantes**, sans changer `lignes.json` : leur mesure
change par `BASE_FIRMES = 2024`. Ces nombres ne sont pas des pronostics mais un calcul :
la couche ne change pas, seul le facteur (PIB de l'année sur PIB de 2024 au lieu de 2023,
× 0,9655) change. IS : 2022 −16,8 → **−19,7 %**, 2023 +2,7 → **−0,8 %**, 2024 +5,6 →
**+2,0 %**. Contribution sociale : −17,4 → −20,2 ; +38,6 → +33,8 ; +24,6 → +20,3 %. C3S :
+15,9 → +11,9 ; +10,0 → +6,2 ; +4,8 → +1,2 %. CVAE 2024 : −12,1 → −15,1 %.

**E2, le vieillissement par l'IS de l'exercice**, proposé, non codé : une série publiée
existe pour la grille (IS brut DGFiP par exercice : Insee Analyses n° 112, figure 1,
2016 à 2022, `data/raw/insee_ia112_taux_implicite_is_2016_2022.xlsx` ; DGFiP n° 39,
tableau 2, 69,05 Md€ en 2024 et +0,63 % sur 2023). Facteurs depuis 2024 : 2022 68,3 /
69,05 = 0,989 ; 2023 68,6 / 69,05 = 0,994. Calcul, sans passe : IS 2022 **−12,1 %**, 2023
**+2,1 %**, 2024 +2,0 % ; contribution sociale −12,7 / +37,7 / +20,3 %. Le saut de l'Insee
en 2022 reste (il suit les paiements). Risque : l'IS devient calé chaque année, la ligne
ne teste plus que la forme. Aucune série n'existe au-delà de 2024 : les études, qui
chiffrent 2026 et après, resteraient au PIB. À décider par le propriétaire ; je ne l'ai
pas codé pour ne pas caler la ligne sans décision.

## 4. Ce que l'étape fait aux études

* **Les textes** (§ 1) : dix nombres affichés changent ou apparaissent, aucun rapport.
* **Les cotisations D121 et l'IR net** : aucune étude, ce sont des mesures de la grille ;
  `_employer_contribution_delta` lit toujours super-brut − brut.
* **L'année des entreprises** : à la prochaine série, chaque coût d'entreprises de la vue
  vieillie baisse de 3,45 % (PIB 2023 / PIB 2024 = 2 833,8 / 2 935,2), la vue figée ne
  bouge pas. Ordre de grandeur, sur les montants des pages : Attal, CVAE 2,55 → ≈ 2,46 Md€
  (−0,09) ; Lisnard et Retailleau, C3S et CVAE 6,55 → ≈ 6,32 (−0,23 chacun) ; PLF art. 15
  (CEBGE) −7,05 → ≈ −6,81 (−0,24), son écart au chiffrage officiel (−5,50) de +28 à
  ≈ +24 %, toujours dans sa tolérance ; leurs dettes de 2035, dans la même proportion pour
  la part des entreprises (art. 15 : −0,23 → ≈ −0,22 pt). Le chiffrage enregistré
  `chiffrages_preregistres/plf2027_art_15_vieilli.yaml` (facteur 1,1057 depuis 2023)
  passerait à ≈ 1,0675 s'il était refait. Mélenchon, Labib, Le Pen, Roussel, Tondelier, le
  PLFSS : rien.
* **Filosofi** : aucun nombre.

## 5. Ce qui reste, les doutes

* **Un défaut trouvé, hors de mon périmètre** : `runner.households_par_lots` avec
  `impute_niches=True` tire les niches quatre fois trop par lot (`niches.impute` divise
  les bénéficiaires nationaux par le poids de la tranche dans le lot, et la probabilité
  est bornée à 1). Mesuré : 40,0 Md€ de RICI au lieu de 10,6 sur 15 000 ménages en quatre
  lots. Seule la réconciliation (`impots population reconcile --lots N --impute-niches`)
  l'appelle ainsi ; ma passe de la grille ne passe pas par elle. À corriger dans
  `runner.py` (repondérer chaque lot le temps de l'imputation, comme `mesures_ir_net`).
* L'ATI de l'État laissée en D121 (0,3 Md€) ; les contractuels en CDI lus titulaires
  (D-346) portent une pension de l'État qu'ils ne devraient pas porter.
* L'indice du capital de 2022 (7,505 Md€) mêle le niveau de 2023 du n° 32 (février) et la
  variation du n° 41 (septembre) ; hypothèse déclarée.
* La CVAE reste sur la valeur ajoutée de 2023 avec l'année de base 2024.
* Le Gini 0,297 de Filosofi 2023 n'est pas retrouvé.
* L'écart de +0,8 % entre l'IR net imputé en un lot et en quatre lots n'est pas expliqué
  (le capital, dit indépendant de l'échelle, en est le suspect).
* Sources lues : impots.gouv.fr (n° 22, n° 32) et insee.fr (TCRD_022, T_7401) ont
  répondu ; rien n'a été refusé.

## 6. Les tests

Nouveaux ou modifiés, vus échouer sur le code d'avant quand ils tiennent un nombre :

* `tests/test_etude_programmes.py` : la dette sans boucle d'Attal (18,30, pas 13,95) ; la
  raison vraie d'Attal et Retailleau. Vus échouer sur l'`etude.py` d'avant.
* `tests/test_firmes_vues.py` : le millésime « 2023 » vieilli depuis 2024 ;
  `verification.BASE_FIRMES == 2024`. Le test du facteur, qui tenait la base 2023, tient
  maintenant un millésime « 2024 ». Vus échouer sur le code d'avant.
* `tests/test_vieillissement.py` : le chiffrage d'entreprises vieilli suit le PIB depuis
  2024 (le PIB simulé gagne une année 2024).
* `tests/test_site.py` : `raison_bande` reçoit la réforme (signature changée).
* `tests/test_secteur_public.py` : un titulaire de l'État à 36 000 € porte 22 377 € de
  pension de l'État ; un salarié du privé, 658,80 € de D291 (1,83 %).
* `tests/test_verification_d121.py` : l'arithmétique de D121 (428,9 − 17,4 − 77,3 − 2,9
  = 331,3) ; l'indice du capital.

Sorties (`pytest -m "not lourd and not chrono" -n 2`) :

* `test_etude_programmes`, `test_etude`, `test_site`, `test_page_explorer`,
  `test_etude_page_plf2027`, `test_predictif_etude` : 395 passés (le seul échec, de
  `test_site`, venait de la signature, corrigée et repassée).
* `test_verification`, `test_verification_d121`, `test_firmes_vues`,
  `test_chiffrage_entreprises`, `test_secteur_public`, `test_cdhr`, `test_ij_moteur`,
  `test_vieillissement`, `test_engine` : 458 passés, 1 échec (`test_vieillissement`, PIB
  simulé sans 2024), corrigé : 9 passés sur le fichier filtré.
* Dernière passe, après toutes les corrections : `test_donnees`, `test_site`,
  `test_page_explorer`, `test_etude_programmes`, `test_etude`, `test_vieillissement` :
  207 passés. `etude verifier` (dix études) et `site verifier` passent.
* Non lancés, selon la consigne : `make impact`, les lourds, la grille, les études.

## Les URL longues

Laissées entières pour rester copiables ; elles sont aussi dans `data/raw/MANIFEST.json`.

* [T7401] https://www.insee.fr/fr/statistiques/fichier/8988835/T_7401_fr.xlsx

* [n22] https://www.impots.gouv.fr/sites/default/files/media/9_statistiques/0_etudes_et_stats/0_publications/dgfip_statistiques/2024/num22_04/dgfip_stat_ir_2022.xlsx

* [n32] https://www.impots.gouv.fr/sites/default/files/media/9_statistiques/0_etudes_et_stats/0_publications/dgfip_statistiques/2025/num32_04/dgfip_stat_32_2025.xlsx
