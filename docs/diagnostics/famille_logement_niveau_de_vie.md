# Diagnostic : allocations familiales, aides au logement, niveau de vie

*Agent `famille_logement_niveau_de_vie`, 10 novembre 2026, sur `claude/but19` (249a3de).
Rien n'a été modifié hors de ce fichier. Les essais sont dans
`/tmp/diag_famille_logement_niveau_de_vie/` (scripts `run_sample.py`, `run2.py`,
`run3.py`, `a2.py` à `a8.py`).*

**Comment les mesures ont été faites.** Le parquet de la population a été lu en entier,
colonnes choisies, sans passe. Les passes OpenFisca ont tourné sur **un échantillon de
20 000 ménages** tiré par `runner.subsample` (PPS systématique, graine 20261110, poids
redressés : 67,20 M de personnes au lieu de 67,42 M), au droit de 2024, sans
vieillissement. Sur cet échantillon, les AF font 10,48 Md€ contre 10,59 Md€ sur la
population entière (passe de la grille), les aides au logement 12,23 contre 12,26 Md€, la
médiane 24 242 contre 24 344 € : l'échantillon reproduit la passe à 1 % près. Toute
mesure ci-dessous qui porte « éch. » est faite sur cet échantillon. Une passe de
scénario (la cinquième de `run3.py`, tous correctifs ensemble) a été tuée par manque de
mémoire partagée ; les effets sont donnés un par un, leur somme n'est pas mesurée.

---

## A. Les allocations familiales

### A1. L'écart, en une phrase

Les allocations familiales du modèle (`af`) font 9,85 / 10,13 / 10,59 Md€ en 2022 / 2023
/ 2024 contre 13,04 / 13,37 / 13,77 Md€ publiés (CCSS), soit −24,5 / −24,2 / −23,1 %.

### A2. Ce que le modèle fait

1. **L'âge.** L'enquête Emploi publique ne donne l'âge qu'en six tranches (`AGE6`) :
   `skeleton.py:88` lit « 15-24 ans » comme un intervalle, et `_draw_ages`
   (`skeleton.py:271`, appelé `:320`) tire l'âge exact **uniformément** dans la tranche,
   **quel que soit le rôle de la personne** dans le ménage. Un enfant de 15-24 ans qui vit
   chez ses parents a donc une chance sur deux d'avoir 20 ans ou plus.
2. **Les moins de 15 ans** n'existent pas dans l'enquête : `_synthesise_children`
   (`skeleton.py:374`) les invente, âge uniforme entre 0 et 14 ans, nombre tiré de la
   loi des familles du recensement (`margins.CHILDREN_PER_FAMILY`), calé sur 11,39 M
   d'enfants (`margins.CHILDREN_UNDER_15`).
3. **Les DOM.** `skeleton.py:324` marque `region = "dom"`, mais `to_openfisca.py`
   (`build_simulation`, `:345` et `:411-436`) ne transmet ni `depcom` ni
   `residence_<dom>` : pour OpenFisca, tout ménage réside en métropole, et la règle des
   DOM (AF dès le premier enfant, `af_eligibilite_dom`) ne s'applique jamais.
4. **Le droit.** OpenFisca-France 176.0.8 calcule `af` (base, majoration pour âge,
   allocation forfaitaire, modulation selon les ressources de N−2) au mois, par famille ;
   âge maximal 20 ans (`def_pac/age_maximal_personnes_charge.yaml`).
5. **Les totaux.** `runner._extract` (`runner.py:291-306`) somme l'année et compte les
   allocataires de décembre ; `verification.py:85` lit `t["af"]`.

### A3. Ce que la statistique publique compte

* **Le juge de la grille** : « Allocations familiales », tableau 1 « Dépenses de
  prestations financées par la CNAF », CCSS. Le rapport de mai 2026 (déjà dans
  `data/raw/MANIFEST.json`, `ccss_mai2026_comptes_secu_resultats2025.pdf`, p. 110) donne
  13 370 M€ en 2023 et 13 766 M€ en 2024, **tous régimes, France entière hors Mayotte**,
  majorations pour âge et allocation forfaitaire comprises.
* **Le compte des familles** : Cnaf, *Analyses statistiques* n° 7, 2026, tableau 1
  (sha256 0d0c4be6…,
  https://caf.fr/sites/default/files/medias/cnaf/Nous_connaitre/Recherche_et_statistiques/Analyses_statistiques/CNAF_n%C2%B07_Analyses_statistiques.pdf
  ) : en 2024, **13 372 M€, 4 786 000 foyers en moyenne mensuelle,
  233 € par foyer et par mois** (2023 : 12 982 M€, 4 833 000, 224 €). Champ : régime
  général (Caf), France entière ; la MSA en est exclue (la Caf fait 97 % des dépenses).
  La différence entre CCSS et Cnaf (0,39 Md€ en 2024) est la MSA et les autres régimes.
* Le chiffre de `margins.BENEFIT_RECIPIENTS["af"]` (4,752 M au 31/12/2024) n'a pas d'URL
  propre (l'URL est la page générique de la Caf du Nord) : non retrouvé tel quel.

### A4. La décomposition de l'écart (2024)

Le modèle : 10,59 Md€ ; 4,15 M de familles allocataires en décembre (éch.), 213 € par
mois. Contre la Cnaf : −13 % de familles, −8 % par famille.

| cause | montant | familles | mesure |
|---|---|---|---|
| âge des 15-24 ans tiré sans le rôle | **+1,17 Md€** | +0,41 M | éch., profil supposé |
| AF des DOM dès le 1er enfant | +0,08 Md€ | +0,20 M | éch. |
| MSA et autres régimes, dans le juge | 0,39 Md€ | | publié |
| reste : −7 % par famille, −4 % de familles | ≈ −1,9 Md€ | | non expliqué |

Le scénario des DOM pose `residence_reunion` sur les ménages `region = "dom"`.

**L'âge, la cause principale.** Dans la population, 14,88 M d'enfants de moins de 20 ans
sont « enfant » d'une famille ; 1,04 M de personnes de moins de 20 ans sont au contraire
demandeur ou conjoint de leur propre famille, et leur âge est plat : 177 000 à 15 ans,
172 000 à 16, 175 000 à 17, 187 000 à 18, 173 000 à 19 (dont 352 000 personnes de
référence en emploi). Ce sont, pour l'essentiel, des 20-24 ans à qui le tirage a donné
15 à 19 ans ; symétriquement, la moitié des enfants de 15-24 ans qui vivent chez leurs
parents reçoivent 20 à 24 ans et sortent des AF. Les marges, elles, sont justes : 12,0 M
de moins de 15 ans et 3,91 M de 15-19 ans dans le modèle, contre 11,79 M et 4,02 M en
logement ordinaire au recensement de 2021 (`TD_POP2_2021`, déjà dans le MANIFEST,
CATPR 01, lignes COM). C'est la loi jointe âge × rôle qui est fausse.

*Le scénario mesuré* retire l'âge des 15-24 ans observés selon leur rôle : un enfant
reçoit l'âge *a* avec une probabilité proportionnelle à la taille de la génération
(recensement 2021 : 805 000 par an à 15-19 ans, 735 000 à 20-24) fois la part des jeunes
de cet âge qui vivent chez leurs parents ; les autres reçoivent le complément. Cette part
est **une hypothèse** : publiée pour la Nouvelle-Aquitaine au recensement de 2013 (Insee
Flash, https://www.insee.fr/fr/statistiques/2573899, figure 1 : 72,1 % à 18 ans,
51,1 % à 20, 37,3 % à 22, 20,7 % à 25), complétée par 97 / 96 / 93 % à 15 / 16 / 17 ans
(supposés) et interpolée à 19, 21, 23 et 24 ans. Aucun tableau national par âge simple
n'a été trouvé. Avec ce profil, 71 % des enfants de 15-24 ans ont moins de 20 ans, au lieu
de 50 % ; les AF passent de 10,48 à 11,65 Md€ (éch.), 4,56 M de familles.

*Ce qui reste* (−1,9 Md€, hypothèses non vérifiées) : la modulation (14 % des familles
allocataires du modèle sont à taux réduit, 0,58 M ; la part publiée n'a pas été
trouvée) ; la composition par rang (73 % de familles de deux enfants dans le modèle ; non
publiée dans la n° 7) ; l'allocation forfaitaire à 20 ans (0,07 Md€ dans le modèle) ;
le « foyer » de la Caf, plus large que la famille du modèle (enfants confiés, recueillis).

### A5. Ce que l'écart fait aux études

Aucune étude ne chiffre aujourd'hui une mesure portant sur les AF : l'indexation de
Mélenchon (+10 %) et le revenu familial de Retailleau sont refusés (portes `indexation`
et `prestations_hors_modele`). Une mesure proportionnelle aux AF (gel, revalorisation)
porterait l'écart **en entier** sur son coût : −23 % aujourd'hui, environ −14 % après le
correctif d'âge. Les déciles : les AF manquantes sont réparties du 1er au 7e dixième
(tableau de la partie C). L'âge des 15-24 ans touche aussi le rattachement au foyer
fiscal (moins de 21 ans sans condition, `skeleton.py:147`) : la part pleine dès le
deuxième enfant de Le Pen et le déplafonnement du quotient de Lisnard en dépendent ;
l'effet n'est pas mesuré ici.

### A6. Le correctif proposé

1. **Tirer l'âge des 15-24 ans selon le rôle** (`skeleton.py:271`, `_draw_ages` reçoit
   le rôle). Donnée : la population des ménages par âge simple et lien à la personne de
   référence, au recensement (fichier détail « individus » du RP, variables d'âge et de
   lien ; l'URL exacte reste à relever, elle n'a pas été vérifiée ici). À défaut, le
   profil régional ci-dessus, déclaré comme hypothèse. Coût : une demi-journée, et
   `make data` pour reconstruire la population ; les marges d'âge (`AGE6`) du calage ne
   bougent pas, `calibrate.py` n'est pas touché. Risque : tous les nombres changent un
   peu (quotient familial, RSA des moins de 25 ans, PPA) ; il faut repasser la grille.
2. **Passer la résidence des DOM** à OpenFisca (`to_openfisca.py:411-436`) : l'enquête
   ne dit pas quel DOM, on prendrait un département par tirage pondéré. Effet faible
   (+0,08 Md€) mais exact en droit ; il touche aussi les aides au logement des DOM.

**Pronostic de la ligne après 1 et 2 :** de −17 % à −11 % (centre −14 %) sur les trois
années ; dans la tolérance de ±25 %, que nul ne change.

### A7. Comment l'expliquer au public

L'enquête qui sert de base ne dit pas l'âge exact des jeunes, seulement « 15 à 24 ans ».
Le modèle tirait cet âge au hasard, comme si un lycéen de 16 ans et un salarié de 23 ans
qui vit seul avaient les mêmes chances d'avoir 16 ans. Or les allocations familiales
s'arrêtent à 20 ans : la moitié des grands enfants vivant chez leurs parents sortaient
du droit trop tôt. En tirant l'âge selon que le jeune vit chez ses parents ou non, il
manque 14 % des allocations familiales au lieu de 23 %. **Le graphique** : la pyramide
des « enfants de la famille » de 15 à 24 ans, modèle avant et après, contre le
recensement. **À faire varier** : la part des jeunes vivant chez leurs parents à chaque
âge, avec le montant des AF qui suit.

---

## B. Les aides au logement

### B1. L'écart, en une phrase

Les aides au logement du modèle (`aide_logement`) font 11,52 / 11,75 / 12,26 Md€ en 2022
/ 2023 / 2024 contre 15,11 / 15,33 / 15,67 Md€ publiés (Cnaf, rapport du directeur
comptable), soit −23,8 / −23,3 / −21,7 %.

### B2. Ce que le modèle fait

1. **Le statut d'occupation** vient de l'enquête (`SO`, `skeleton.py:96-108`) ; les
   ménages sont ensuite calés par `calibrate.py` sur le type de ménage, pas sur le
   statut d'occupation.
2. **La zone** : `skeleton.py:116-121` traduit `STCOMM2020` (ville-centre, banlieue →
   zone 2 ; ville isolée, hors unité urbaine → zone 3). **La zone 1 (Paris et sa petite
   couronne) n'existe pas** : l'enquête publique n'a ni commune ni région (vérifié : 83
   colonnes, aucune géographie hors `METRODOM` et `STCOMM2020`).
3. **Le loyer** : `incomes.py:316` pose une surface de 30 m² + 12 m² par personne
   (hypothèse, `incomes.py:90`), fois 5,6 €/m² en HLM et 8,8 €/m² dans le privé
   (`margins.RENT_PER_M2`, `margins.py:326`). Loyer moyen : 332 € en HLM, 461 € en
   location vide, 425 € en meublé ; zéro pour les accédants et les propriétaires.
4. **Le droit** : OpenFisca calcule APL, ALF et ALS au mois, base ressources
   contemporanéisée depuis 2021 (salaires et chômage des douze mois glissants,
   `aides_logement.py:631-636` d'OpenFisca-France ; revenus non salariaux en N−2). Les
   accédants ne reçoivent rien (aucune date ni nature de prêt n'est transmise).
5. **Les totaux** : comme pour les AF (`runner.py:306`, `verification.py:85`).

### B3. Ce que la statistique publique compte

* **Le juge** : ligne « Logement » des prestations de l'État versées par la branche
  Famille (APL + ALS + ALF, **y compris l'ALT** et les logements-foyers), droits
  constatés, France entière (`lignes.json`, rapports du DCF de la Cnaf).
* **Le partage par filière** : Compte du logement 2023, partie 5 (SDES,
  https://www.statistiques.developpement-durable.gouv.fr/media/7719/download?inline),
  figure 5.8, **hors locaux d'hébergement collectif** : APL 2 440 000 bénéficiaires
  (223 €/mois), ALS 2 061 000 (197 €), ALF 868 000 (319 €), dont propriétaires occupants
  37 000, 27 000 et 73 000. Les trois aides font 15,6 Md€ en 2023 (texte, même page).
* **Les locataires** : recensement 2023, tableau LOG T10, France
  (https://www.insee.fr/fr/statistiques/2011101?geo=FE-1) : 31,22 M de résidences
  principales, **12,58 M de locataires dont 4,55 M en HLM**, 17,94 M de propriétaires.
* **Le compte des allocataires** : 5 809 400 au 31/12/2024 selon
  `margins.BENEFIT_RECIPIENTS` (Drees, Panorama Minima sociaux 2025) ; le site de la
  Drees refuse le conteneur (réponse vide), le chiffre n'a pas été relu à la source.

### B4. La décomposition de l'écart (2024 : −3,41 Md€)

Le modèle : 4,87 M d'allocataires en décembre, 216 € par mois (éch.) ; 38 % des familles
locataires sont aidées ; le loyer réel dépasse le loyer plafond pour 69 % des aidés, si
bien que le loyer ne joue qu'à la marge.

| cause | effet | mesure |
|---|---|---|
| (a) hébergement collectif et ALT, hors champ | ≈ −0,6 Md€ | estimé |
| (b) accédants, sans aide dans le modèle | ≈ −0,33 Md€ | publié, 2023 |
| (c) pas de zone 1 | **−0,31 Md€** | éch., hypothèse |
| (d) locataires trop peu nombreux | −0,8 à −1,6 Md€ | hypothèse |
| (e) reste | −0,6 à −1,4 Md€ | non mesuré |

(a) Le juge de 2023 (15,33 Md€) moins la figure 5.8 multipliée par douze (14,73 Md€) ;
les deux sources n'ont pas le même concept (droits constatés, versements). (b) 137 000
accédants aidés en 2023, figure 5.8, fois leur aide moyenne, fois douze. (c) Mesuré sur
l'échantillon en passant en zone 1 24 % des ménages de zone 2, part supposée de
l'agglomération parisienne. (d) 11,11 M de ménages locataires dans le modèle contre
12,58 M au recensement (−11,7 % ; HLM 3,95 M contre 4,55 M, −13 %) ; borne haute si les
aides suivent le nombre de locataires, borne basse si les locataires manquants sont plus
aisés. (e) Ressources, absence de chômage intermittent, loyers, barème des DOM.

Les causes chiffrées font de −2,0 à −2,8 Md€ sur −3,41. Le compte des propriétaires du
modèle est symétriquement trop haut : 19,28 M (accédants compris) contre 17,94 M.

### B5. Ce que l'écart fait aux études

**L'art. 74 du PLF 2027, volet logement** (`docs/etudes/plfss2027.md`) : le modèle
chiffre 78 M€ d'économie, le chiffrage officiel 101 M€ : −23 %, l'écart de niveau de la
ligne. La mesure est une revalorisation proportionnelle (2,0 % des paramètres) : la
différence de deux passes reprend l'écart de niveau **tel quel**, elle ne l'annule pas.
Les déciles : 43 % de la masse des aides au logement du modèle va au 1er dixième, 21 % au
2e, 15 % au 3e (éch., dixièmes de ménages) ; c'est là que le manque se lit. Le Pen (APL
réservées aux Français) et Retailleau (plafond de cumul) sont refusés ; s'ils étaient
chiffrés, ils hériteraient du même −22 %.

### B6. Le correctif proposé

1. **Le statut d'occupation au calage** (marge LOG T10 : locataires HLM, autres
   locataires, propriétaires). C'est la cause la plus lourde, et elle passe par
   `calibrate.py`, **fermé jusqu'à la phase 7** : à décider par le propriétaire.
2. **La zone 1** : tirer la zone 1 parmi les ménages des villes-centres et banlieues,
   avec une part prise d'une source publiée (population des communes de la zone 1 ;
   arrêté de zonage et recensement, à télécharger). Coût : une heure ; effet +2,5 %.
3. **Le champ du juge** : comparer à la ligne hors hébergement collectif et hors ALT, ou
   dire l'écart de champ. Cela demande une nouvelle ligne préenregistrée (D-entrée), la
   tolérance existante ne bouge pas.
4. **Les accédants** : transmettre une date de prêt antérieure à 2018 à une part des
   primo-accédants, calée sur les 137 000 accédants aidés (figure 5.8). Faible.

**Pronostic de la ligne** : après 2 seul, de −21 à −19 % ; après 1 et 2, de −12 à −6 % ;
après 1, 2 et 3, de −8 à −2 %.

### B7. Comment l'expliquer au public

Le modèle compte 1,5 million de locataires de moins que le recensement, et il ne sait pas
qui habite Paris et sa petite couronne, où les loyers plafonds sont les plus hauts. Il ne
voit pas non plus les résidences collectives (foyers, résidences étudiantes), que la Caf
aide aussi. Chacune de ces trois absences retire une part des aides ; ensemble, elles
font l'essentiel des 22 % qui manquent. **Le tableau** : locataires, allocataires et
montant moyen, modèle contre recensement et Compte du logement, filière par filière.
**À faire varier** : le nombre de locataires et la part de la zone 1.

---

## C. Le niveau de vie médian et le D9/D1

### C1. L'écart, en une phrase

Le niveau de vie médian du modèle est de 22 747 / 23 747 / 24 344 € en 2022 / 2023 / 2024
contre 24 330 / 25 760 / 26 740 € publiés par l'ERFS (−6,5 / −7,8 / −9,0 %), et son
D9/D1 de 3,63 / 3,70 / 3,59 contre 3,38 / 3,49 / 3,48 (+7,4 / +5,9 / +3,2 %).

### C2. Ce que le modèle fait

`aggregate.py:245-253` : niveau de vie = `revenu_disponible` d'OpenFisca du ménage,
divisé par les unités de consommation OCDE (`aggregate.py:57`), quantiles **pondérés par
personne**. Le revenu disponible ne contient que ce que la population porte :
salaires (1 112 Md€ bruts), pensions (374 Md€), chômage (36 Md€), et les prestations
et impôts qu'OpenFisca en déduit. La passe de la grille est **sans imputation**
(`verification.py:10`) : ni revenus du capital, ni indemnités journalières, ni niches.
Le champ n'est pas restreint : DOM compris, aucun filtre sur la personne de référence.
**3,89 M d'actifs occupés non salariés ont un revenu nul** (`is_salarie` faux, aucun
revenu d'indépendant : `skeleton.py:123-125`) ; l'AAH vaut zéro dans la passe (éch.).

### C3. Ce que la statistique publique compte

* **L'ERFS** (Insee Première n° 2004, 2063 et 2117, tableau complémentaire 2 ; les
  trois classeurs ont été retéléchargés, empreintes identiques à `lignes.json`) :
  revenu disponible = revenus d'activité **y compris des indépendants**, de remplacement,
  **du patrimoine** (déclarés et **imputés** pour les produits exonérés : livrets,
  assurance-vie), prestations sociales, moins les impôts directs. Champ : France
  métropolitaine, logement ordinaire, revenu déclaré positif ou nul, personne de
  référence non étudiante. En 2024, en euros 2024 : **D1 13 970, D5 26 740, D9 48 580** ;
  2023 (euros 2023) : 13 460 / 25 760 / 46 960 ; 2022 (euros 2022) : 12 970 / 24 330 /
  43 840.
* **Filosofi 2023** (source fiscale localisée, sans imputation des produits exonérés) :
  voir C8.

### C4. La décomposition de l'écart (2024, éch., métropole)

Base de l'échantillon, métropole : D1 12 144, D5 24 347, D9 43 780, D9/D1 3,605. Contre
l'ERFS : D1 −13,1 %, D5 −8,9 %, D9 −9,9 %.

| cause | effet sur la médiane | mesure |
|---|---|---|
| (a) capital, IJ et niches, imputations du dépôt | **+587 €** (+2,4 %) | éch., passe |
| (b) indépendants sans revenu | +468 à +697 € | éch., hors passe |
| (c) revenus fonciers absents | +532 € | éch., hors passe, hyp. |
| (d) AF et aides au logement au niveau publié | +163 € | éch., hors passe |
| (e) champ : personne de référence étudiante | +100 € | éch., proxy |

(a) Passe complète de l'échantillon avec `impute_capital`, `impute_ij`,
`impute_niches` ; le capital seul fait +86 €. (b) 69,4 Md€ de BIC, BNC et BA
professionnels déclarés, à 70 % nets, répartis par tête sur les non-salariés ; borne
basse en retirant à leurs ménages le RSA, la PPA et les aides au logement. (c) 28,1 Md€
déclarés, à 70 % nets, répartis sur la moitié haute de la distribution (hypothèse).
(d) AF × 1,30 et aides au logement × 1,28, au prorata. (e) Hors des ménages dont la
personne de référence a moins de 25 ans et pas d'emploi.

Les revenus déclarés sont ceux de la DGFiP n° 41, tableau 1 (déjà dans le MANIFEST,
`dgfip_stat_41_ir_2024_tables.xlsx`) : BNC 52,7 Md€ dont 4,3 non professionnels, BIC
26,3 dont 11,5 non professionnels, BA 6,2, fonciers 28,1. Cumulés hors passe (borne basse
des indépendants, fonciers, AF et AL, champ) : médiane 25 576 € ; plus les imputations du
dépôt, ≈ 26 150 €, soit environ −2 % de l'ERFS. Le reste est hypothèse : les pensions
(374 Md€ dans la population contre 400,4 déclarés, rentes et pensions alimentaires
comprises), l'AAH absente, les revenus exonérés que l'ERFS impute.

**Le D9/D1.** Le D1 du modèle est collé au minimum vieillesse : 1,1 % des personnes ont
un niveau de vie entre 12 140 et 12 150 €, toutes dans un ménage qui touche l'ASPA
(1 012 € par mois en 2024) ; l'ASPA du modèle fait 6,35 Md€ pour 1,50 M de ménages
(éch. ; ligne d'un autre diagnostic, non confrontée ici). Sous ce plancher, les ménages
d'indépendants à revenu nul : **45 % des ménages du premier dixième du modèle comptent un
non-salarié sans revenu** (éch.). Le D1 est donc trop bas de 13 % quand le D9 l'est de
10 % : le rapport monte de 3,6 %. Les indépendants le font tomber à 3,40 (borne basse) ou
3,11 (borne haute) ; le cumul ci-dessus, à 3,32.

### C5. Ce que l'écart fait aux études

Les tableaux par décile des pages d'étude rangent les ménages par ce niveau de vie. Le
premier dixième y est, pour près de moitié, fait de ménages d'indépendants sans revenu et,
pour un tiers, de ménages au minimum vieillesse ; les AF et les aides au logement qui
manquent (≈ 6,5 Md€) appauvrissent les trois premiers dixièmes. Pour une réforme chiffrée
par différence de deux passes (TVA énergie de Le Pen, quotient de Lisnard), l'écart de
niveau s'annule dans le coût total, **mais pas dans le partage par décile** : un
indépendant qui gagne à la réforme est compté parmi les plus modestes. Le « niveau de vie
moyen » du 1er dixième (8 275 € dans `plfss2027.md`) est trop bas pour la même raison.
Le sens et l'ordre de grandeur des tableaux tiennent ; la répartition entre le 1er et le
2e dixième ne doit pas être lue finement (les pages le disent déjà : « toute structure plus
fine qu'un décile est un artefact »).

### C6. Le correctif proposé

1. **Mesurer la grille avec les imputations du dépôt** (capital, IJ, niches), ou dire en
   tête de ligne qu'elle est sans : +2,4 % sur la médiane, mesuré. Nouvelle D-entrée.
2. **Imputer les revenus d'indépendants** aux 3,89 M de non-salariés, depuis la n° 41
   (montant par décile de RFR, déjà dans le MANIFEST) et les variables `rpns_*`
   d'OpenFisca. Coût : deux à trois jours (câblage dans `to_openfisca.py`, test sur
   l'IR des indépendants) ; risque : le RSA et la PPA des non-salariés bougent (lignes
   du diagnostic `rsa_ppa`).
3. **Imputer les revenus fonciers** comme le capital (`capital.py`), depuis la n° 41.
4. **Restreindre le champ** de la ligne à celui de l'ERFS (métropole ; étudiants : pas
   de variable, proxy à déclarer).

**Pronostic** : médiane de −4 à −1 % après 1 à 4 ; D9/D1 de −5 à +2 %.

### C7. Comment l'expliquer au public

Le revenu disponible du modèle ne contient que les salaires, les retraites, le chômage et
les aides qu'on en déduit. Il lui manque les revenus des indépendants (artisans,
commerçants, professions libérales, agriculteurs), les loyers perçus et une partie des
revenus de l'épargne, que l'Insee compte. Le niveau de vie médian est donc trop bas de
9 %, et le premier dixième est rempli de ménages d'indépendants qui, dans le modèle,
n'ont rien gagné. **Le graphique** : la courbe des niveaux de vie par centile, modèle et
ERFS, puis le modèle avec chaque revenu ajouté l'un après l'autre (indépendants,
fonciers, capital). **À faire varier** : le revenu moyen des indépendants et sa
répartition.

### C8. Les deux anomalies de D-364

* **La médiane de 25 920 € existe** : c'est Filosofi 2023, France métropolitaine, Insee,
  « Niveau de vie en 2023 : comparaisons régionales et départementales »,
  **https://www.insee.fr/fr/statistiques/2012717**, fichier `TCRD_022.xlsx` (sha256
  1331aa54…), onglet REG, ligne « France métropolitaine » : médiane 25 920, D1 13 200,
  D9 46 500. Champ : ménages fiscaux en logement ordinaire, revenu disponible positif ou
  nul. Les déciles D2 à D8 de `margins.py:346` (17 010 … 38 100) n'y sont pas : non
  retrouvés. Le chiffre est un `use="validation"` (`margins.py:354`), lu par
  `reconcile.py:362` ; il ne cale rien. Il est de 2023, comparé à une population de 2024.
* **L'URL de `margins.py:342`** (8402386) rend 404 ; la bonne est 2012717. La page de
  métadonnées de Filosofi 2023 porte la date du 10/11/2026 et dit le millésime
  « substantiellement retravaillé ». Le fichier `filosofi_2023_all_geo.zip` du MANIFEST
  est en quarantaine, sans URL, absent du disque.
* **ERFS et Filosofi ne mesurent pas la même chose** : la même année 2023, 25 760 €
  (ERFS, revenus du patrimoine imputés) contre 25 920 € (Filosofi, fiscal). L'ERFS est la
  référence nationale ; la grille a raison de la prendre.

---

## Ce qui reste à décider

* Le tirage des âges selon le rôle (A6-1) : le plus gros effet chiffré de ce diagnostic,
  hors `calibrate.py` ; il demande une source nationale par âge simple.
* La marge du statut d'occupation (B6-1) : elle passe par `calibrate.py`, fermé.
* Le revenu des indépendants (C6-2) : il touche les AF, les aides au logement, le RSA, la
  PPA et les déciles d'un coup.
* Corriger l'URL Filosofi (`margins.py:342` → 2012717) : sans effet sur un nombre.
