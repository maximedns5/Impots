# Diagnostic : les cotisations effectives des employeurs (D121)

Agent `cotisations_employeurs`, 10 novembre 2026, sur `claude/but19` (249a3de). Aucune
ligne de `src/`, `scripts/`, `tests/`, `reports/` ni `docs/` n'est modifiée hors de ce
fichier. Les scripts d'essai sont dans `/tmp/diag_cotisations_employeurs/`.

## 1. L'écart, en une phrase

La ligne « Cotisations effectives des employeurs, après allègements » de la grille
(`docs/verification/GRILLE.md`, D-364) lit 397,4 / 414,8 / 427,1 Md€ en 2022 / 2023 / 2024
dans le modèle, contre 298,9 / 314,4 / 329,3 Md€ publiés par l'Insee (D121), soit +33,0 %,
+31,9 % et +29,7 %, hors de la tolérance de ±15 % les trois années, et de signe contraire
au pronostic de D-363.

## 2. Ce que le modèle fait

La chaîne, du fichier au nombre :

1. **La frame.** `data/processed/population_2024.parquet` porte par personne
   `salaire_brut_annuel` (calé sur D11 du tableau 6.205, 1 111,65 Md€ en 2024 :
   `src/impots/population/margins.py:71`), `secteur_public`, `fonction_publique`,
   `titulaire` et `quotite_travail`.
2. **Le câblage.** `src/impots/population/to_openfisca.py:292` (`public_service`, D-346) :
   tout salarié du privé part en `prive_non_cadre` ; un titulaire part dans sa fonction
   publique, payé d'un traitement indiciaire TIB = brut / 1,195 et des primes
   qu'OpenFisca calcule ; un contractuel public part en `public_non_titulaire`. Les
   entrées sont posées mois par mois (`to_openfisca.py:424-426`). Rien ne pose
   `effectif_entreprise` (0 pour tous, mesuré), ni la commune de l'employeur, ni le
   statut de cadre, ni le temps partiel (`quotite_travail` est dans la frame, pas dans la
   simulation), ni le taux d'accident du travail (risque « faible », 0,64 %, pour tous).
3. **La variable OpenFisca** (openfisca-france 176.0.8, dans `.venv`) : `salaire_super_brut`
   (`openfisca_france/model/revenus/activite/salarie.py:1472`) =
   `salaire_super_brut_hors_allegements` (`salarie.py:1435`) − `exonerations` −
   `allegement_general` + primes de partage de la valeur exonérées ; et
   `salaire_super_brut_hors_allegements` = salaire de base + rémunération principale +
   primes de la fonction publique + **indemnité de résidence + supplément familial de
   traitement** + cantine + … − `cotisations_employeur`. `cotisations_employeur`
   (`prelevements_sociaux/cotisations_sociales/travail_totaux.py:78`, formule depuis 2019)
   somme 19 variables, plus `cotisations_employeur_main_d_oeuvre`
   (`prelevements_sociaux/taxes_salaires_main_oeuvre.py:171`), qui en somme 11 autres : la
   liste complète est au tableau du §4.
4. **Le registre.** `src/impots/engine/outputs.py:57-60` : `salaire_brut` = salaire de
   base + rémunération principale + primes de la fonction publique (sans l'indemnité de
   résidence ni le SFT) ; `salaire_super_brut` tel qu'OpenFisca le rend.
5. **La grille.** `src/impots/verification.py:74` compare
   `salaire_super_brut − salaire_brut`, sommé et pondéré par
   `src/impots/population/aggregate.py`, au total publié
   (`docs/verification/lignes.json`, entrées `cotisations_employeurs`).

La même différence sert au coût des réformes : `aggregate.py:167`
(`_employer_contribution_delta`) lit Δ(super-brut − brut) entre deux passes.

## 3. Ce que la statistique publique compte

**D121, « cotisations sociales effectives à la charge des employeurs »**, comptes nationaux
annuels base 2020, édition mai 2026, tableau 7.401, compte des ménages (S14), ressources du
compte d'affectation des revenus primaires, ligne 42 (et D611, ligne 77) :
<https://www.insee.fr/fr/statistiques/fichier/8988835/T_7401_fr.xlsx> (téléchargé ici,
sha256 f27bfdff…826e, le même que `lignes.json`). Relu dans ce fichier :

| ligne du T_7401 (S14, ressources) | 2022 | 2023 | 2024 |
|---|---:|---:|---:|
| D11 salaires et traitements bruts | 1 042,9 | 1 101,9 | 1 137,2 |
| D121 cotisations effectives des employeurs | 298,9 | 314,4 | 329,3 |
| D122 cotisations imputées des employeurs | 66,0 | 68,7 | 72,4 |

Trois règles du SEC 2010, telles que les tableaux de l'Insee les appliquent :

* **Les prélèvements sur les salaires qui ne donnent pas de droit sont des impôts (D291),
  pas des cotisations.** Tableau 3.217 « Principaux impôts par catégorie »
  (<https://www.insee.fr/fr/statistiques/fichier/8988845/t_3217_fr.xlsx>, déjà dans
  `data/raw/MANIFEST.json`), lignes 39 à 48, en Md€ :

  | D291, impôts sur les salaires et la main-d'œuvre | 2022 | 2023 | 2024 |
  |---|---:|---:|---:|
  | total D291 | 52,1 | 55,1 | 58,1 |
  | taxe sur les salaires | 16,0 | 16,7 | 17,3 |
  | versement mobilité | 10,6 | 11,4 | 12,2 |
  | formation professionnelle et apprentissage | 10,7 | 11,2 | 11,4 |
  | forfait social | 6,2 | 6,4 | 6,3 |
  | Fnal | 2,7 | 2,8 | 2,9 |
  | contribution solidarité autonomie (CSA) | 2,3 | 2,4 | 2,5 |
  | participation à l'effort de construction | 1,4 | 1,5 | 1,5 |
  | régime de garantie des salaires (AGS) | 0,9 | 1,0 | 1,5 |
  | contribution patronale sur stock-options | 0,8 | 1,0 | 1,0 |

* **La contribution de l'État employeur au régime de pension de ses fonctionnaires est
  une cotisation imputée (D122)**, pas effective : le régime n'a pas d'existence séparée
  de l'employeur. La CNRACL (territoriale, hospitalière), l'Ircantec et le RAFP sont des
  caisses distinctes : effectives. Cette règle est celle du SEC 2010 (§ 4.98 à 4.100) ; je
  ne l'ai pas retrouvée écrite dans une note de l'Insee, et je n'ai pas trouvé publié le
  détail de D122 par employeur (non trouvé).
* **Le champ** est celui des ressources des ménages résidents : D11 y vaut 1 137,2 Md€ en
  2024, quand le D11 des branches résidentes (6.205, la cible de calage) vaut
  1 111,65 Md€. L'écart de 25,6 Md€ est, pour l'essentiel, la rémunération reçue du
  reste du monde (frontaliers) ; D121 en porte la part patronale. Non mesuré ici.

D121 comprend les cotisations patronales aux régimes privés obligatoires d'entreprise
(prévoyance, complémentaire santé), que le modèle ne calcule pas (§4).

## 4. La décomposition de l'écart

**Comment.** Une passe 2024 sur un échantillon de 20 000 ménages (43 584 personnes) tiré
de `population_2024.parquet` par `runner.subsample` (PPS systématique, graine
20240101), qui garde le total des poids (31,01 M de ménages) ; la masse salariale de
l'échantillon vaut 1 125,1 Md€ contre 1 111,65 sur la frame entière, et chaque nombre
ci-dessous est ramené à la masse entière (× 0,988). Chaque variable que `salaire_super_brut`
somme est lue par `PopulationSimulation.calculate(v, add=True)` et ventilée par
`categorie_salarie`. Script : `/tmp/diag_cotisations_employeurs/decomp.py` et
`analyse.py`. **Mesure sur échantillon**, sur 2024 seulement. Contrôle : l'échantillon
redonne `super-brut − brut` = 428,9 Md€, contre 427,1 dans la passe entière de la grille
(+0,4 %).

**Ce que somme le super-brut, en 2024, par catégorie** (Md€, ramenés à la masse
entière ; cotisations en valeur positive) :

| variable OpenFisca | total | privé | c. pub. | t. État | t. hosp. | t. terr. | classe |
|---|---:|---:|---:|---:|---:|---:|---|
| `mmid_employeur_net_allegement` | 105,3 | 82,7 | 4,6 | 10,1 | 2,9 | 5,0 | D121 |
| `pension_employeur` | 105,0 | — | — | **77,3** | 10,2 | 17,5 | (3) |
| `vieillesse_plafonnee_employeur` | 58,3 | 55,8 | 2,5 | — | — | — | D121 |
| `agirc_arrco_employeur` | 54,8 | 54,8 | — | — | — | — | D121 |
| `famille_net_allegement` | 45,5 | 33,5 | 1,9 | 5,5 | 1,7 | 2,9 | D121 |
| `chomage_employeur` | 33,3 | 33,3 | — | — | — | — | D121 |
| `vieillesse_deplafonnee_employeur` | 17,8 | 17,1 | 0,7 | — | — | — | D121 |
| `contribution_unique_formation_…` (1) | 11,7 | 10,4 | 0,2 | 0,6 | 0,2 | 0,3 | **D291** |
| `contribution_equilibre_general_employeur` | 11,4 | 11,4 | — | — | — | — | D121 |
| `accident_du_travail` | 5,4 | 5,4 | — | — | — | — | D121 |
| `contribution_solidarite_autonomie` | 3,2 | 2,5 | 0,1 | 0,3 | 0,1 | 0,2 | **D291** |
| `ircantec_employeur` | 2,0 | — | 2,0 | — | — | — | D121 |
| `rafp_employeur` | 1,9 | — | — | 1,0 | 0,3 | 0,6 | D121 |
| `ags` | 1,6 | 1,6 | — | — | — | — | **D291** |
| `contribution_equilibre_technique_employeur` | 0,9 | 0,9 | — | — | — | — | D121 |
| `fnal` | 0,8 | 0,7 | 0,0 | 0,1 | 0,0 | 0,0 | **D291** |
| `ati_atiacl` | 0,7 | — | — | 0,3 | 0,1 | 0,2 | ATI État : D122 (hyp.) |
| `fonds_emploi_hospitalier` | 0,3 | — | — | — | 0,3 | — | D121 |
| `financement_organisations_syndicales` | 0,1 | 0,1 | 0,0 | — | — | — | non classé |
| **somme `cotisations_employeur`** | **460,2** | | | | | | |
| − `allegement_general` | −34,2 | −34,2 | | | | | |
| + indemnité de résidence et SFT (2) | +2,9 | — | 0,4 | 1,4 | 0,5 | 0,7 | **D11** |
| **= super-brut − brut** | **428,9** | 276,2 | 12,5 | 96,6 | 16,3 | 27,3 | |

Colonnes : c. pub. = contractuels publics ; t. = titulaires. (1)
`contribution_unique_formation_professionnelle_alternance`. (2) `indemnite_residence` +
`supplement_familial_traitement`, que `salaire_brut` ne compte pas. (3) État : D122 ;
CNRACL (hospitalière, territoriale) : D121.

Valent **zéro** pour tous : `taxe_salaires`, `forfait_social`, `versement_transport`,
`participation_effort_construction`, `contribution_developpement_apprentissage`,
`contribution_supplementaire_apprentissage`, `conge_individuel_formation_cdd`,
`apec_employeur`, `prevoyance_obligatoire_cadre`, `prevoyance_complementaire_employeur`,
`complementaire_sante_employeur`, `exonerations`, les primes de partage de la valeur.
Les bandeaux maladie et famille (27,4 et 10,9 Md€) sont déjà nets dans les deux lignes
`*_net_allegement`. Masse brute par catégorie : privé 847,2 Md€ (19,3 M de salariés),
titulaires de l'État 124,4 (2,30 M), territoriaux 66,0 (1,62 M), hospitaliers 38,7
(0,96 M), contractuels publics 35,4 (0,97 M).

**Les causes, chiffrées** (2024, Md€, ramenées à la masse entière) :

| cause | mesurée | Md€ |
|---|---|---:|
| (b) contribution de l'État à ses pensions (74,28 % du TIB) : D122, pas D121 | oui | 77,3 |
| (a) prélèvements classés D291 que le modèle calcule (4) | oui | 17,4 |
| (c1) indemnité de résidence et SFT : des salaires (D11), pas des cotisations | oui | 2,9 |
| (b') ATI des fonctionnaires de l'État, versée par l'État : D122 | hypothèse | 0,3 |
| **somme des causes mesurées (a, b, c1)** | | **97,6** |
| **écart à expliquer** (428,9 − 329,3 ; 97,8 sur la passe entière) | | **99,6** |

(4) Formation et apprentissage 11,7, CSA 3,2, AGS 1,6, Fnal 0,8.

Le modèle reclassé vaut 428,9 − 97,6 = **331,3 Md€, soit +0,6 %** de D121 (329,3) ;
+0,5 % si l'ATI de l'État va aussi en D122. Les trois causes mesurées expliquent 98 % de
l'écart.

**Ce que ce +0,6 % cache : des erreurs de sens opposés, non mesurées.** La quasi-égalité
n'est pas une preuve que le reste est juste :

* *Manquent au modèle, et sont dans D121* : les contributions patronales aux contrats
  collectifs de prévoyance et de complémentaire santé (zéro dans le modèle ; montant
  publié non trouvé ici) ; la prévoyance obligatoire des cadres et l'Apec (aucun salarié
  n'est cadre) ; l'accident du travail, à 0,64 % pour tous (le risque « faible »
  d'OpenFisca, `travail_prive.py:1102`), d'où 5,4 Md€ (le total publié de la branche
  AT-MP n'a pas été relevé ici) ; la part patronale sur la rémunération des frontaliers
  (D11 du 7.401 dépasse celui du 6.205 de 25,6 Md€).
* *Pèsent dans l'autre sens* : les « titulaires » de l'État lus dans l'enquête Emploi
  comprennent les contractuels en CDI (D-346 le dit) ; la masse des titulaires de l'État
  (124,4 Md€ pour 2,30 M) porte une contribution de pension de 77,3 Md€, au-dessus de
  tout D122 (72,4 Md€, tous employeurs). Après le reclassement, cette erreur ne pèse plus
  sur D121 que par ce que ces contractuels devraient payer en effectif (CNAV, Ircantec),
  qui manque : elle tire le modèle vers le bas, elle aussi. Ce qui tire vers le haut n'est
  pas identifié (hypothèse : une masse privée plus concentrée au-dessus de 1,6 SMIC que
  dans la réalité, cohérente avec la réduction générale à −12 % dans la grille).
* *La part de D291 absente* : la taxe sur les salaires, le versement mobilité, le forfait
  social, la PEEC et la contribution sur stock-options valent zéro, faute
  d'`effectif_entreprise`, de commune d'employeur et d'assujettissement. Le Fnal sort à
  0,8 Md€ (0,10 % plafonné, celui des moins de 50 salariés) contre 2,9 publiés. Hors de
  la ligne D121, mais c'est un trou de 40 Md€ des impôts sur les salaires, que la grille ne
  voit pas, faute de ligne.

**Les années 2022 et 2023** ne sont pas mesurées sur échantillon. L'écart y a la même
taille relative (D-364 : biais stable) et le taux de la contribution de l'État (74,28 %)
est inchangé de 2022 à 2024 dans les paramètres d'OpenFisca ; le même reclassement doit y
porter (hypothèse).

**La masse salariale.** Le brut du modèle vaut D11 par construction : 1 111,65 Md€ en
2024 (6.205, ligne `_T`, déjà dans `data/raw`), recalée et conservée par le câblage du
secteur public. Le rapport cotisations/brut est de 38,4 % dans le modèle (427,1 /
1 111,65), contre 29,0 % dans les comptes (D121 / D11 du 7.401) ; reclassé, il tombe à
29,8 %. L'assiette n'est pas la cause ; la définition l'est.

## 5. Ce que l'écart fait aux études

Une seule étude chiffre aujourd'hui une mesure qui passe par les cotisations des
employeurs : **Mélenchon** (`docs/etudes/presidentielle_melenchon.md`,
`scenarios/pres2027_melenchon_exonerations_au_dela_2_smic.json`), qui ramène le plafond
de sortie de la réduction générale de 3 à 2 SMIC (`allegement_general_plafond`), pour
+6,61 Md€. Son coût est Δ(super-brut − brut) entre deux passes (`aggregate.py:167`).
Aucune des trois causes de l'écart (pension de l'État, prélèvements D291, indemnité de
résidence et SFT) ne dépend de la réduction générale : elles sont identiques dans les
deux passes et **s'annulent exactement dans le coût**. Ce que le coût peut porter, c'est
l'erreur sur la réduction générale elle-même (ligne de la grille à −12 %), et deux
défauts voisins vus ici : l'effectif nul, qui prend le coefficient T des moins de 50
salariés pour tous, et le temps partiel non câblé (`quotite_travail` n'entre pas dans
OpenFisca), qui place un mi-temps à 2,5 SMIC horaire sous 2 SMIC mensuels et le soustrait
à la mesure (hypothèse de sens : sous-estimation du rendement ; non mesuré).

**Attal** (`a16_droit_au_brut`) et **Retailleau** (`r19_gains_rendus_moitie`) chiffrent
les cotisations **salariales** de retraite (`cotisations_salariales_retraite_echelle`) :
le super-brut ne bouge pas, la ligne D121 n'y entre pas. **Labib** ne chiffre que la TVA
et les accises des carburants ; sa « suppression des allègements » est refusée (vague).
Les mesures patronales de **Retailleau** (« choc fiscal », cotisations patronales non
contributives) et de **Lisnard** (baisse des cotisations rendue en net) sont refusées ;
celle du PLFSS 2027 sur l'assiette des allègements aussi (porte `donnee_menages`).

**Le risque est pour la suite.** Une mesure qui toucherait un taux patronal en
proportion lirait une assiette qui mêle cotisations, impôts sur les salaires et la
pension de l'État : une baisse « des cotisations patronales non contributives » de
Retailleau, si elle était chiffrée sur `cotisations_employeur`, ramasserait la CSA, le
Fnal et la formation (17 Md€ d'impôts), et une baisse uniforme de « toutes les
cotisations » ramasserait 77 Md€ que l'État se verse à lui-même, sans effet sur le
solde public.

**Ailleurs dans le moteur.** La boucle macro (`macro/shocks.py:243`) et le contrôle de
partie double (`guards.py:414`) lisent le delta, pas le niveau. L'autofinancement
(`behavioural/autofinancement.py:40`) lit le super-brut d'un emploi privé au SMIC : CSA,
Fnal et formation y sont des recettes publiques quelle que soit leur classe, et la
pension de l'État n'y entre pas ; rien à corriger. L'interface affiche
« Cotisations employeur » (`cotisations_employeur`, brute des allègements, impôts sur
salaires compris) : un libellé à préciser, pas un nombre faux.

## 6. Le correctif proposé

**Ne pas toucher au coût du travail.** `salaire_super_brut` reste ce que lit le coût des
réformes et l'autofinancement : c'est le coût du travail, impôts sur salaires compris,
et l'écart s'y annule.

**Ajouter une mesure « au sens D121 » pour la grille seule.**

1. Trois lignes de registre (`src/impots/engine/outputs.py`), lues au tier `full` :
   * `prelevements_salaires_d291` : somme (signe inversé) de
     `contribution_unique_formation_professionnelle_alternance`,
     `contribution_solidarite_autonomie`, `fnal`, `ags`, `taxe_salaires`,
     `forfait_social`, `versement_transport`, `participation_effort_construction`,
     `contribution_developpement_apprentissage`,
     `contribution_supplementaire_apprentissage`, `conge_individuel_formation_cdd` ;
   * `pension_employeur_etat` : une variable de projet (D-308) qui vaut
     `pension_employeur` (et l'ATI) pour `public_titulaire_etat` et
     `public_titulaire_militaire`, zéro sinon ;
   * `remuneration_hors_brut` : `indemnite_residence` + `supplement_familial_traitement`
     (ou, mieux, les ajouter à `salaire_brut` en `extra`, ce qui change le brut des
     titulaires de 2,9 Md€ et doit alors se dire).
2. Dans `src/impots/verification.py:74`, la mesure devient
   `super-brut − brut − prelevements_salaires_d291 − pension_employeur_etat −
   remuneration_hors_brut`. Un champ neuf de `lignes.json` ; l'ancienne définition reste
   lisible dans la D-entrée.
3. Deux lignes neuves, préenregistrées avec elle : **D291** contre le tableau 3.217
   (52,1 / 55,1 / 58,1 Md€), pronostic −75 % à −65 % (le modèle n'en a que 17 Md€ : il lui
   manque la taxe sur les salaires, le versement mobilité et le forfait social) ; et la
   **pension de l'État** en ligne de contexte contre D122 (66,0 / 68,7 / 72,4 Md€), D122
   contenant d'autres employeurs (à noter « contexte », pas « validation »).

**Données.** Tout est déjà là, sauf le T_7401, que `lignes.json` cite (URL et sha256) mais
que `data/raw/MANIFEST.json` ne porte pas : l'ajouter
(<https://www.insee.fr/fr/statistiques/fichier/8988835/T_7401_fr.xlsx>). Le 3.217 est au
manifeste.

**Coût.** Une demi-journée : trois lignes de registre, une variable de projet, un test
léger qui tient deux nombres (un titulaire de l'État à 36 000 € : la mesure D121 exclut
74,28 % de son TIB de 30 126 €, soit 22 378 € ; un salarié du privé au SMIC : elle exclut
CSA, Fnal, AGS et formation), puis les trois passes de la grille (19 minutes, D-364).

**Risque.** (i) La ligne serait tenue en partie par compensation (§4) : le dire dans la
D-entrée. (ii) **Ce pronostic n'est pas aveugle** : il vient d'une mesure sur échantillon
de 2024 faite dans ce diagnostic ; la D-entrée de préenregistrement doit le dire et
garder la tolérance de ±15 %. (iii) Ne pas laisser la nouvelle variable entrer dans le
coût : un test ou une revue doit vérifier que `_employer_contribution_delta` ne la lit pas.

**Pronostic de la ligne après correctif** : 2024, de −8 % à +3 % (point mesuré sur
échantillon : +0,6 %) ; 2022 et 2023, de −9 % à +4 % (non mesurées) ; les trois années
dans ±15 %. La fourchette penche vers le bas parce que les erreurs non mesurées connues
(prévoyance et santé d'entreprise, accident du travail, frontaliers, contractuels lus
titulaires) tirent toutes le modèle sous le total publié.

**Plus tard, hors de ce correctif** : câbler `effectif_entreprise` et une commune
d'employeur (Fnal, versement mobilité, coefficient de la réduction générale), le temps
partiel (`contrat_de_travail`, heures), le statut de cadre, et un taux d'accident du
travail moyen. Ces correctifs changent des nombres d'étude (Mélenchon), contrairement au
reclassement.

## 7. Comment l'expliquer au public

Le modèle calculait 427 milliards de cotisations patronales en 2024, l'Insee en compte
329. Presque toute la différence est une question de rangement, pas de calcul. D'abord,
     quand l'État verse 74 % du traitement de ses fonctionnaires à leur caisse de retraite,
     il se paie à lui-même : la comptabilité nationale l'appelle « cotisation imputée » et
     la met à part (77 milliards). Ensuite, certaines sommes payées sur les salaires sont
     des impôts et non des cotisations, parce qu'elles n'ouvrent aucun droit (formation,
     apprentissage, solidarité autonomie, logement, garantie des salaires : 17 milliards).
     Enfin, l'indemnité de résidence et le supplément familial des fonctionnaires sont des
     salaires (3 milliards). Rangé comme l'Insee, le modèle donne 331 milliards (mesure sur
     échantillon), et le coût des réformes, qui compare deux calculs sur la même base, n'en
     change pas.

**Ce qui le prouverait à un lecteur sceptique** : une cascade de 428,9 Md€ (le modèle,
sur l'échantillon mesuré ; 427,1 sur la population entière) à 329,3 Md€ (l'Insee), une
marche par cause (−77,3 pension de l'État, −17,4 impôts sur salaires, −2,9 salaires hors
brut, résidu +2,0), avec, pour chaque marche, la variable OpenFisca, la catégorie de
salariés qui la porte et la classe de l'Insee (D121, D122, D291, D11) ; à côté, le
tableau du §4 par catégorie.

**Ce qu'un lecteur pourrait faire varier** : cocher ou décocher chaque reclassement (la
pension de l'État en effectif ou en imputé ; les impôts sur salaires dans ou hors des
cotisations) et voir la ligne passer de 427 à 331 ; et, pour la mesure de Mélenchon,
vérifier que son coût ne bouge pas quel que soit le rangement choisi.
