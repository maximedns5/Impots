# Étape al du but 19 : les aides au logement et les allocations familiales

*Branche `claude/but19-al`, partie de `claude/but19` (cde8a32, étapes 1 à 4 jointes), le
10 novembre 2026. Consigne : `CONSIGNE_ETAPES.md` (N = « al »). Diagnostics suivis :
`famille_logement_niveau_de_vie.md` (A, B), `etape_2.md`, `etape_3.md`, `etape_4.md`.
Aucune passe ni construction sur la population entière, aucune grille, aucune étude,
aucune D-entrée ; `lignes.json` et `calibrate.py` non touchés. `incomes.py` est touché
**d'un seul bloc** (le loyer, voir § 1) : l'agent de l'impôt sur le revenu doit le savoir
pour la jonction. Scripts d'essai : `/tmp/but19_al/scripts/` (`diag_al.py` famille par
famille, `ana_al.py`, `ana_af.py`, `mesure.py`), variantes : `/tmp/but19_al/var/`.*

## 1. Ce qui a changé, fichier par fichier

**`src/impots/population/logement.py`** (neuf). Où vit un ménage, pour l'aide au
logement.

* `draw_zone_and_departement` : la zone APL est **tirée**, ménage par ménage, sur son
  propre flux (`default_rng([graine, 8])` : aucun autre tirage ne bouge). L'EEC ne dit
  que la place de la commune dans son unité urbaine (`STCOMM2020` : ville-centre,
  banlieue, ville isolée, hors unité urbaine) et métropole / DOM. Chaque ménage reçoit la
  zone 1, 2 ou 3 avec la part des résidences principales du recensement de même statut
  d'unité urbaine **et de même statut d'occupation** (HLM, autre locataire, autre) qui
  sont dans une commune de cette zone. Les DOM sont tous en zone 2 (le fichier de
  zonage le dit) et reçoivent un département (971 à 974) tiré aux résidences principales.
* `monthly_rent` : le loyer HLM est le loyer moyen du RPLS au 1er janvier 2024,
  **7,68 €/m² en zone 1** (Île-de-France, le plus proche que la population puisse dire)
  et **6,15 €/m² ailleurs** (province et DROM), fois la règle de surface d'avant
  (30 m² + 12 m² par personne, hypothèse inchangée, déplacée ici depuis `incomes.py`).
  Le loyer privé ne change pas (8,8 €/m²).

**`src/impots/population/skeleton.py`**. La table `ZONE_APL` (ville-centre et banlieue
en zone 2, le reste en zone 3 : **jamais de zone 1**) est remplacée par `_draw_zone`,
appelé une fois les enfants synthétisés ajoutés ; colonne neuve `departement` (nulle en
métropole). Les enfants synthétisés ne portent plus la zone, ils la reçoivent du tirage.

**`src/impots/population/incomes.py`** (un bloc). Le calcul du loyer (12 lignes) devient
un appel à `logement.monthly_rent` ; les deux constantes de surface partent dans
`logement.py`. Rien d'autre ; aucun tirage n'est consommé, aucun salaire ne bouge.

**`src/impots/population/to_openfisca.py`**. Si le cadre porte `departement`, le
ménage d'un DOM reçoit `depcom` = « 97x01 » (les `residence_<dom>` d'openfisca lisent
le préfixe) sur les 36 mois, et son foyer `depcom_foyer` sur N−2 à N, **avant** que le
RFR de N−2 soit épinglé. La métropole garde les valeurs par défaut (`""`, `"00000"`) :
rien de ce qui lit `depcom` n'y bouge. S'appliquent alors : les AF dès le premier enfant
(`af_eligibilite_dom`), les plafonds et le forfait de charges des DOM pour l'aide au
logement, **l'abattement DOM de l'impôt** (30 %, 40 % en Guyane, plafonnés).

**`src/impots/population/margins.py`**. `APL_ZONE_BY_STCOMM` (douze cases × trois zones)
et `APL_ZONE_SOURCES` ; `DOM_HOUSEHOLDS_BY_DEPARTEMENT` ; `HLM_RENT_PER_M2` (RPLS).
`RENT_PER_M2["social"]` (5,6 €/m²) est retiré ; `RENT_PER_M2["prive"]` reçoit un
avertissement : la page citée (France portrait social, 8612568, relue le 10 novembre) ne
donne aucun loyer au m² ; **la valeur 8,8 est non retrouvée**. Elle ne pèse presque pas :
le loyer d'un locataire du privé non meublé dépasse toujours son loyer plafond.

**`build.py`** : la colonne `departement` au schéma. **`reconcile.py`** : le texte qui
disait la zone 1 impossible. **`data/raw/MANIFEST.json`** : quatre sources neuves (§ 5).

**Comment la table de zones est faite** (`/tmp/but19_al/scripts/zone_final.py`). Commune
par commune : résidences principales, locataires et HLM louées vides du RP 2023 (base
des principaux indicateurs, géographie 2026, `COM_2023`, colonnes 3, 64 et 65) ; statut
de la commune dans l'unité urbaine 2020 (`STATUT_COM_UU`, géographie 2026) ; zone du
fichier d'openfisca `assets/apl/20110914_zonage.csv`, celui que lit sa formule
`zone_apl`. Toutes les communes ont un statut ; 151 résidences principales n'ont pas de
zone (communes du fichier de 2014 disparues) et sont laissées de côté. Les parts :

| statut d'unité urbaine | HLM en zone 1 | autres locataires en zone 1 | autres en zone 1 |
|---|---|---|---|
| banlieue | 45,9 % | 37,8 % | 28,6 % |
| ville-centre | 11,9 % | 14,2 % | 11,0 % |
| ville isolée | 3,3 % | 2,3 % | 2,8 % |
| hors unité urbaine | 0,8 % | 1,1 % | 1,2 % |

Le tirage déplace aussi vers la zone 3 un tiers des locataires des villes-centres (Tours,
Angers… ne sont pas en zone 2), ce qui retire une part de ce que la zone 1 apporte.

**Tests** : `tests/test_logement.py` (six tests ; voir § 6).

## 2. Les mesures, avant et après

**Comment.** 20 000 ménages de `data/processed/population_2024.parquet` (population
jointe, étapes 2 et 3), `runner.subsample`, graine `SAMPLE_SEED` = 20240101, droit 2024,
palier complet, sans imputation. La population n'a pas été reconstruite (interdit) :
l'« après » applique aux ménages de l'échantillon les fonctions de `logement.py` (zone,
département, loyer), la colonne `STCOMM2020` étant relue dans l'EEC par l'identifiant
du ménage (`IDENT-TRIM`). Le tirage porte donc sur l'échantillon et non sur la
population, avec la même loi. **Ces mesures ne sont pas aveugles** : je les ai faites en
choisissant les correctifs.

| ligne (2024) | avant | après | publié | écart après |
|---|---|---|---|---|
| aides au logement, Md€ | 11,98 | **12,67** | 15,67 | −19,1 % |
| allocataires AL, décembre, M | 4,92 | 5,06 | ≈ 5,8 (non relu) | |
| AF, Md€ | 11,38 | **11,45** | 13,77 | −16,8 % |
| familles AF, décembre, M | 4,49 | 4,67 | 4,786 (Cnaf, moyenne) | −2,4 % |
| IR au barème avant niches, Md€ | 129,47 | 128,87 | | −0,47 % |
| RSA servi / droit, Md€ | 10,50 / 15,84 | 10,48 / 15,82 | | −0,16 % |
| prime d'activité servie / droit, Md€ | 6,63 / 12,78 | 6,56 / 12,66 | | −1,0 % |
| foyers imposés, M | 21,84 | 21,73 | | −0,48 % |
| salaires imposables, CSG | | | | ≤ +0,03 % |
| niveau de vie D1, € | 12 789 | 12 835 | | +0,36 % |
| niveau de vie D5, € | 25 574 | 25 586 | | +0,05 % |
| niveau de vie D9, € | 45 390 | 45 474 | | +0,18 % |

Ce qui bouge et pourquoi : l'IR baisse de l'abattement DOM (0,60 Md€ sur l'échantillon ;
la dépense fiscale 110302 vaut **426 M€ en 2024**, 383 M€ en 2023, voies et moyens
tome II des PLF 2026 et 2025, déjà au manifeste : le modèle est haut de 40 %, sur
quelques centaines de foyers des DOM de l'échantillon). La prime et le RSA baissent du
forfait logement des nouveaux allocataires de l'aide au logement. Rien d'autre ne bouge
hors des DOM et des locataires.

**L'effet de chaque correctif sur les aides au logement** (même échantillon, mesures
famille par famille, `diag_al.py`, montant annuel) :

| pas | Md€ | effet |
|---|---|---|
| avant | 11,98 | |
| + zone tirée | 12,15 | +0,17 |
| + loyer HLM du RPLS | 12,73 | +0,58 |
| + département des DOM | 12,67 | −0,05 (barème des DOM) ; AF +0,07 |

### 2.1 Les aides au logement : l'écart restant, décomposé

Après l'étape : 12,67 Md€ contre 15,67, **−3,0 Md€**. Ce que le modèle sert, par aide
(décembre, montant mensuel moyen), contre le Compte du logement 2023 (SDES, partie 5,
figure 5.8, hors locaux d'hébergement collectif) :

| aide | modèle, M | €/mois | publié 2023, M | €/mois |
|---|---|---|---|---|
| APL | 2,28 | 203 | 2,44 | 223 |
| ALS | 2,08 | 202 | 2,06 | 197 |
| ALF | 0,71 | 301 | 0,87 | 319 |

L'ALS est juste ; le manque est dans l'APL (le parc social : nombre et montant) et dans
l'ALF (les familles du privé). Après le loyer du RPLS, 60 % des locataires HLM aidés
paient plus que leur loyer plafond (39 % avant) ; le loyer de l'Ancols en mettrait 96 %.

| cause | effet | mesure |
|---|---|---|
| (a) foyers, résidences, ALT : hors des ménages ordinaires | ≈ −0,6 | estimé (B4 a) |
| (b) accédants, sans aide dans le modèle | ≈ −0,33 | publié, 2023 |
| (c) histoire des revenus en régime permanent nominal | −0,23 | éch., scénario |
| (d) loyer HLM moyen sous l'Ancols (389 € contre 442 €) | −0,13 | éch., scénario |
| (e) revenus des locataires non liés au statut d'occupation | ? | hypothèse |
| (f) **surcompte** : hébergés dans un logement de famille | **+0,78** | éch. |
| (g) **surcompte** : ménages « autres », sans colocation | **+1,0** | éch., scénario |

* (c) Les années N−1 et N−2 répètent les revenus nominaux de N (D-011, « steady
  state »). La base ressources de l'aide lit les salaires des douze mois glissants
  (M−13 à M−2) et les autres revenus de N−2 : elle est surestimée de la croissance des
  salaires. Le scénario (`var/v5.py`) déflate N−1 et N−2 par le salaire par tête et
  l'IPC constatés de l'Insee (`hypotheses.insee_constate` : +2,64 % en 2024, +4,66 % en
  2023) : aides au logement +0,23 Md€, AF +0,24 Md€. Il touche aussi le RSA, la prime et
  le taux de CSG des pensions : c'est une décision, pas un correctif de cette étape.
* (d) L'Ancols (« Panorama du logement social 2026 ») donne un loyer moyen hors charges
  de 442 € en 2024 ; **lu dans la presse (AFP, MoneyVox, Banque des territoires), le
  panorama lui-même n'a pas été lu**. Le modèle fait 389 € (332 € avant) : la règle de
  surface donne 59 m² en moyenne au parc social. Caler le loyer HLM sur 442 € ajoute
  0,13 Md€ (`var/v3.py`) ; non fait, faute de la source primaire.
* (f) Toute personne du logement qui n'est ni la personne de référence, ni son conjoint,
  ni un enfant rattachable forme sa propre famille (`skeleton._classify_dependants`). Un
  enfant majeur qui travaille, un parent âgé hébergé, reçoivent l'aide au logement **sur
  le loyer entier du ménage**, avec le plafond d'une personne seule : 0,38 M de familles,
  0,78 Md€ dans les ménages que l'EEC type « famille monoparentale » ou « couple avec
  enfants » (`TYPLOG5` 2 et 4). En droit, un hébergé qui ne paie pas de loyer n'a rien.
* (g) Les ménages « autres » (`TYPLOG5` = 5) de plusieurs familles : 0,51 M de familles
  secondaires aidées, 1,26 Md€. Ce sont des colocations ou des hébergés. Les déclarer en
  colocation (`coloc`, plafond et charges de colocation) retire 1,0 Md€ (`var/v6.py`) ;
  les traiter en hébergés retirerait davantage.
* (e) L'EEC n'a aucun revenu ; les salaires sont tirés selon la PCS, l'âge, le sexe et
  la quotité, pas selon le statut d'occupation. À PCS égale, un locataire HLM gagne
  moins qu'un propriétaire : le modèle donne aux locataires des ressources trop hautes.
  Le corriger demande une marge de revenu par statut d'occupation (§ 3) et passe par le
  calage.

**Ce que cela veut dire.** Les causes hors champ (a, b) font −0,9 Md€. Les surcomptes
(f, g) font +0,8 à +1,8 Md€ : corrigés, ils porteraient le modèle à 10,9 à 11,9 Md€, et
l'écart des locataires ordinaires à −2,9 à −3,9 Md€, **plus grand qu'il n'y paraît**.
Le nombre d'allocataires en témoigne : 5,06 M dans le modèle, dont 0,38 M d'hébergés et
une part des 0,51 M de familles secondaires, contre 5,23 M de locataires aidés hors
foyers et hors accédants (figure 5.8, 2023). Le reste tient sans doute à (c) et (e).

**Le compte de la Cnaf (5,8 M).** Non relu : le site de la Drees refuse toujours le
conteneur. Le fichier Insee / Cnaf des bénéficiaires par commune au 31/12/2024 (§ 5)
compte **4,62 M d'allocataires d'une aide au logement dans les seules communes à Iris**,
qui logent 9,81 M des 12,58 M de locataires du recensement ; rapporté aux locataires,
5,9 M (règle de trois, hypothèse). Le chiffre de 5,8 M est donc plausible ; il comprend
les foyers et les résidences.

**Par zone** (même fichier, communes à Iris, zone d'openfisca ; modèle, familles aidées
en décembre) : zone 1, 0,96 M d'allocataires (96 % des locataires de la zone 1 sont dans
des communes à Iris) contre **1,20 M dans le modèle** ; zone 2 de métropole, 2,47 M au
moins contre 2,06 M. Le modèle aide trop en zone 1 : les locataires qu'il y tire ont le
revenu d'un locataire de banlieue ou de ville-centre quelconque, alors que ceux de
l'agglomération parisienne sont plus aisés (à Paris, 0,33 allocataire par locataire).
Le niveau de la zone 1 est juste (2,69 M de locataires contre 2,70 M au recensement) ;
qui y vit ne l'est pas, faute de géographie dans l'EEC.

### 2.2 Les allocations familiales

Après l'étape : 11,45 Md€ contre 13,77 (CCSS, tous régimes) ou 13,37 (Cnaf, Caf seules).
Familles : 4,67 M en décembre contre 4,786 M en moyenne mensuelle (−2,4 %), dont 0,18 M
de familles d'un enfant des DOM, neuves. **Montant par famille : 204 € par mois contre
233 € (−12 %).** C'est là qu'est l'écart.

| nombre d'enfants (AF) | familles, M | €/mois | majoration pour âge, Md€ |
|---|---|---|---|
| 1 (DOM) | 0,18 | 34 | 0,02 |
| 2 | 3,26 | 141 | 0,28 |
| 3 | 0,95 | 349 | 0,49 |
| 4 | 0,25 | 543 | 0,15 |
| 5 et plus | 0,06 | 679 | 0,02 |

* **La modulation** : 17,8 % des familles allocataires du modèle sont à taux réduit
  (0,41 M à la moitié, 0,43 M au quart). À sa création, la réponse ministérielle à la
  question écrite n° 69943 (AN, 14e législature,
  https://questions.assemblee-nationale.fr/dyn/14/questions/QANR5L14QE69943.pdf)
  annonçait 5 % à la moitié et 6 % au quart, 11 % en tout ; les plafonds suivent les
  prix, les revenus ont crû plus vite depuis 2013, la part de 2024 est donc plus haute,
  **non trouvée**. Le régime permanent nominal (c)
  en est une cause : avec l'histoire déflatée, 14,5 % et +0,24 Md€.
* **La majoration pour âge** (0,94 Md€) et **l'allocation forfaitaire** (0,08 Md€) :
  pas de montant publié trouvé pour les comparer (la Cnaf n° 7 ne les sépare pas).
* **La structure par rang** : non publiée dans les sources lues (Cnaf n° 7 ; le fichier
  par commune ne compte que les couples de trois enfants et plus, toutes prestations).
* **Les DOM** : faits (+0,07 Md€, +0,18 M de familles).
* **L'âge** : fait à l'étape 3.

Ce qui reste (−1,5 Md€ contre la Cnaf, une fois la modulation et l'histoire
mises à part) n'est pas expliqué par une source lue. Hypothèses : le foyer de la Caf est
plus large que la famille du modèle (enfants confiés, recueillis) ; un enfant de 15 à
19 ans qui gagne plus de 55 % du SMIC sort du droit (règle exacte, mais les salaires des
jeunes sont tirés sans lien avec leur rôle) ; la répartition par rang.

## 3. Le préenregistrement proposé

**Lignes neuves** (aucune n'est dans `lignes.json` ; à préenregistrer par le
coordinateur) :

1. **« Réduction d'IR des contribuables des DOM »**, dépense fiscale 110302 : 426 M€ en
   2024 (594 883 ménages), 383 M€ en 2023 (580 573), voies et moyens tome II des PLF
   2026 (p. 225 de l'annexe) et 2025 ; 2022 : PLF 2024, non au manifeste, à télécharger.
   Modèle : l'IR au barème sans puis avec `depcom_foyer` (une passe de plus, ou une
   sortie qui recalcule `ir_plaf_qf` sans résidence) — **la sortie n'existe pas**, à
   écrire dans `runner.py`. Tolérance proposée ±35 % (Mayotte absente de la population,
   ses foyers ont la réduction de 40 %). Pronostic : +20 à +60 % (0,60 Md€ mesuré sur peu
   de foyers des DOM).
2. **« Allocataires d'une aide au logement en zone 1 »**, 31/12/2024 : somme de `AAL`
   sur les communes de zone 1 du fichier `beneficiaires_CAF_31-12-2024_Iris.xlsx`
   (onglet COM_2025, arrondissements de Paris, Lyon et Marseille retirés), 0,957 M.
   Modèle : familles aidées en décembre, ménages de zone 1. Le publié compte les foyers
   et résidences, le modèle non. Tolérance proposée ±25 %. Pronostic 2024 : **+20 à
   +30 %**, à la limite ou hors de la tolérance (§ 2.1). 2024 seulement.

**Marges neuves** (à décider ; elles passent par `calibrate.py` ou par les tirages) :

* le **revenu des ménages par statut d'occupation** (Filosofi ou ERFS publient le niveau
  de vie selon le statut d'occupation ; tableau non relevé ici) : la cause (e) ;
* le **loyer moyen HLM** de l'Ancols (442 €, 2024), si le panorama est lu : cale la
  surface du parc social (cause d).

**Le pronostic des lignes touchées** (grille entière, une fois les branches jointes ;
le niveau 2024 vient de l'échantillon, qui refait la passe à 1 % près selon le
diagnostic ; les années 2022 et 2023 gardent l'écart de pente du diagnostic) :

| ligne | 2022 | 2023 | 2024 |
|---|---|---|---|
| aide_logement_montant (±25 %) | −24 à −18 % | −23 à −17 % | −22 à −16 % |
| af_montant (±25 %) | −21 à −15 % | −21 à −15 % | −20 à −14 % |
| ir_bareme (±10 %) | −0,3 à −0,6 pt | −0,3 à −0,6 pt | −0,3 à −0,6 pt |
| foyers_imposes | −0,3 à −0,6 pt | idem | idem |
| ppa_montant | −0,7 à −1,3 pt | idem | idem |
| rsa_montant, rsa_foyers | −0,1 à −0,3 pt | idem | idem |
| ppa_foyers | −0,2 à −0,4 pt | idem | idem |
| niveau_de_vie_median | 0 à +0,1 pt | idem | idem |
| d9_d1 | −0,1 à −0,4 pt | idem | idem |

Les « pt » sont le déplacement de l'écart dû à cette étape seule, à ajouter à ce que la
jonction des autres étapes donnera. Les autres lignes ne bougent pas (salaires, CSG,
cotisations : ≤ 0,03 %). Pour `ir_bareme` : si l'« impôt au barème » de la DGFiP n° 41
est compté avant la réduction DOM, l'étape éloigne le modèle de 0,4 % de son juge ; s'il
est compté après, elle l'en rapproche. Je ne l'ai pas vérifié.

## 4. Ce que l'étape fait aux études

* **Art. 74 du PLF 2027, volet logement** (`plfss2027.md` : −78 M€ contre −101 M€). La
  mesure est une revalorisation proportionnelle des paramètres : son coût suit le niveau
  des aides, +5,7 % ici, un peu plus en zone 1 où plus de locataires sont au plafond.
  Pronostic : **−80 à −86 M€** (centre −82), toujours dans la tolérance de 40 M€. Mais
  les surcomptes (f, g) jouent en sens inverse ; corrigés, l'étude retomberait vers
  −70 M€.
* **Volet prime d'activité du même article** : −1 % de niveau, quelques M€.
* **Les études qui touchent l'IR** (Lisnard, Le Pen, Attal…) : le niveau de l'IR baisse
  de 0,5 % ; les coûts des réformes du barème baissent de la part des DOM, moins de 1 %.
* **Les tableaux par décile** : le premier dixième gagne un peu (D1 +0,4 %) ; l'ordre
  de grandeur ne change pas.
* Aucune étude ne chiffre aujourd'hui une mesure des AF (refusées par les portes).

## 5. Ce qui reste, les doutes, les sources

**Fait.** La zone (tirée, sourcée), les DOM (transmis), le loyer HLM (RPLS).

**Non fait, et pourquoi.**

* Les **hébergés et colocations** (f, g) : la correction la plus lourde (−0,8 à
  −1,8 Md€), dans le sens qui éloigne du juge. Elle demande une décision : soit donner
  une seule famille au logement quand les autres sont des parents hébergés (le
  découpage de `_assign_units`), soit transmettre `coloc` et partager le loyer. L'EEC
  ne dit pas qui paie le loyer.
* Les **accédants** (APL accession, 137 000 en 2023) : aucune date ni nature de prêt
  dans l'EEC ; ≈ 0,33 Md€.
* L'**hébergement collectif** (foyers, résidences, Crous, ALT) : hors des ménages
  ordinaires ; ≈ 0,6 Md€. Une ligne « hors foyers » demanderait un juge à ce champ ;
  la figure 5.8 du Compte du logement l'est, mais en versements et non en droits.
* Le **régime permanent nominal** : à décider (touche toutes les prestations).
* Les **revenus par statut d'occupation** : donnée absente de l'EEC.

**Doutes.** La zone tirée met en zone 1 des ménages de banlieue « moyens » ; le niveau
est juste, la composition non (§ 2.1). La règle de surface reste une hypothèse. Le loyer
privé de 8,8 €/m² n'a pas de source retrouvée. Le RPLS mesure un loyer par m² de surface
habitable, la règle de surface est une surface sans définition.

**Sources téléchargées** (dans `data/raw`, ajoutées au manifeste, hors git) :

* `UU2020_au_01-01-2026.zip` (Insee, base des unités urbaines 2020, sha256 262e511e…,
  1 072 365 octets), https://www.insee.fr/fr/information/4802589 ;
* `base_cc_logement_2023_xlsx.zip` (Insee, RP 2023, logement, principaux indicateurs,
  0eccb43a…, 62 588 981 octets), https://www.insee.fr/fr/statistiques/8997194 ;
* `beneficiaires_CAF_31-12-2024_Iris.xlsx` (Insee / Cnaf, e8f02333…, 2 641 821 octets),
  https://www.insee.fr/fr/statistiques/8682393 ;
* `sdes_rpls_2024_datalab_essentiel.pdf` (SDES, RPLS au 1er janvier 2024, 06ea948c…,
  522 296 octets),
  https://www.statistiques.developpement-durable.gouv.fr/media/7974/download?inline.

Les classeurs de l'Insee ont une feuille de styles qu'openpyxl refuse : ils ont été lus
par un lecteur XML minimal (`/tmp/but19_al/scripts/xlsx.py`).

**Non lues** : la Drees (Panorama des minima sociaux, refus du conteneur) ; le panorama
2026 de l'Ancols (lu par la presse seulement) ; un tableau de la Cnaf des familles
allocataires des AF par rang et par taux de modulation (non trouvé) ; la surface moyenne
du parc social (non trouvée).

## 6. Les tests

`tests/test_logement.py`, six tests, tenant des nombres :

* la table des zones refait son total déclaré ;
* les zones tirées refont les parts du recensement, case par case, à 0,6 point ;
* les DOM sont en zone 2, les départements aux parts du recensement ;
* le loyer HLM vaut 7,68 / 6,15 €/m² selon la zone, le privé 8,8 ;
* une famille réunionnaise d'un enfant reçoit les AF (> 250 € par an), la même en
  métropole rien ;
* un foyer réunionnais de 40 000 € a l'abattement DOM (1 168 € contre 2 023 €).

Vus échouer sur le code d'avant (`git stash`, `logement.py` laissé) : les six échouent,
les deux derniers parce que le département n'est pas transmis.

```
$ pytest -q -p no:randomly tests/test_logement.py
6 passed in 4.46s
$ pytest -m "not lourd and not chrono" -n 2 -q tests/test_population.py
  tests/test_foyers_fiscaux.py tests/test_non_salaries.py tests/test_secteur_public.py
  tests/test_logement.py tests/test_prestations.py tests/test_emtr_explorer.py
  tests/test_ij.py tests/test_capital.py tests/test_recours.py tests/test_annees.py
246 passed in 141.60s
$ pytest -m "not lourd and not chrono" -n 2 -q tests/test_uprating.py
  tests/test_vieillissement.py
53 passed in 26.35s
```

Un essai de construction du squelette sur un sixième des ménages de l'EEC (non calé) :
5,10 M de ménages en zone 1, 10,36 M en zone 2, 15,18 M en zone 3 (recensement :
5,21 / 10,26 / 14,97 M), une seule zone par ménage. Ni `make impact` ni les lourds n'ont
tourné. **La population doit être reconstruite** (`make data`) pour porter la colonne
`departement` ; sans elle, `to_openfisca` se comporte comme avant.

## 7. Suite : qui est au bail (les deux surcomptes corrigés)

*Le 10 novembre 2026, après la jonction de `claude/but19` (étapes al et « ir ») dans
cette branche. Population **reconstruite dans ce worktree** (`impots population build`,
une fois, liens `population_2024.*` supprimés d'abord ; 423 347 personnes, 199 451
ménages, calage en 27 itérations, aucun écrêtage).*

### 7.1 La règle et sa source

* **CCH art. R. 821-4** : « Lorsque plusieurs personnes ou ménages constituant des foyers
  distincts occupent le même logement et qu'ils sont […] cotitulaires du bail ou de
  l'engagement de location, une aide personnelle au logement peut être accordée à
  chacune de ces personnes ou chacun de ces ménages. » Un foyer distinct qui n'est pas
  au bail (un fils de 26 ans qui travaille, une mère veuve, logés par la famille) n'a
  pas d'aide.
* **CCH art. D. 842-3** : en colocation, « le loyer principal retenu est le résultat du
  quotient du loyer effectivement payé par le nombre de cotitulaires du bail ».
* **CCH art. D. 823-16** et arrêté du 27 septembre 2019, art. 8 : le loyer plafond des
  colocataires est 0,75 fois celui d'une personne isolée (le paramètre `coef_colocation`
  d'openfisca, lu quand `coloc` est vrai, avec le forfait de charges des colocataires).
* **CASF art. R. 262-9** (forfait logement du RSA ; la prime le reprend) : une personne
  hébergée à titre gratuit a le forfait logement entier.
* Les deux premiers textes sont lus dans un extrait du CCH (sites-cites.fr, « dispositions
  réglementaires APL », 2022) ; Légifrance n'a pas été relu depuis le conteneur.

**Ce que fait openfisca.** Chaque famille lit le loyer de son ménage
(`famille.demandeur.menage('loyer')`) : un logement, une famille. `coloc` existe (plafond
et charges), aucune variable ne dit qu'une famille est hors du bail, et
`proprietaire_proche_famille` (le logement d'un parent) n'annule que l'ALS et l'ALF, pas
l'APL.

### 7.2 Ce qui change

* **`engine/corrections.py`, correction 25** (sur le modèle de la 24 : une entrée qui
  manque à openfisca, pas un désaccord avec lui ; pas d'entrée dans `CORRECTIONS`, faute
  de test de mort à écrire). Variable d'entrée `aide_logement_heberge` (famille, mois,
  fausse par défaut). `aide_logement_montant_brut` est nul pour une famille hébergée
  (APL, ALS et ALF, CRDS comprise), enveloppé autour de la correction 6.
  `rsa_forfait_logement` et `ppa_forfait_logement` lui comptent le forfait entier : la
  formule d'openfisca relue comme si l'aide dépassait le forfait. **Une D-entrée est
  à écrire** par le coordinateur (je n'en écris pas).
* **`population/logement.py`, `lodging`** ; `skeleton.py` (après `_assign_units`),
  `build.py` : deux colonnes. `aide_logement_heberge` : les familles autres que celle de
  la personne de référence, dans un logement que l'EEC type comme celui d'une famille
  (`TYPLOG5` 1 à 4). `colocation` : un logement « autre » (`TYPLOG5` 5) de plusieurs
  familles. Population reconstruite : 0,90 M de familles hébergées chez des locataires
  (1,29 M chez des propriétaires, sans effet), 1,02 M de ménages en colocation.
* **`population/to_openfisca.py`** : `coloc` par ménage, le loyer d'une colocation divisé
  par son nombre de familles, `aide_logement_heberge` par famille, sur les 36 mois. Sans
  les colonnes, rien ne change.
* **Hypothèses**, car l'EEC ne dit pas qui a signé le bail : dans un logement de famille,
  personne d'autre que la famille de référence n'est au bail ; dans un logement
  « autre », toutes les familles le sont. La seconde surestime sans doute l'aide (une
  part de ces familles est hébergée).

### 7.3 La mesure

20 000 ménages de la population reconstruite, `runner.subsample`, graine 20240101, droit
2024, palier complet. « Avant » : la même population sans les deux colonnes (le code
d'avant) ; « après » : avec. Non aveugle.

| ligne (2024) | avant | hébergés seuls | après | publié |
|---|---|---|---|---|
| aides au logement, Md€ | 13,05 | 12,25 | **11,16** | 15,67 |
| allocataires AL, décembre, M | 5,21 | 4,80 | **4,63** | ≈ 5,8 |
| prime d'activité servie, Md€ | 7,13 | 7,06 | 7,10 | |
| RSA servi, Md€ | 10,550 | 10,545 | 10,549 | |
| IR, AF, CSG, salaires | | | ±0,00 % | |
| niveau de vie D1 / D5 / D9 | | | −0,5 / −0,1 / 0,0 % | |

Les hébergés font −0,80 Md€ et −0,41 M d'allocataires ; la colocation −1,10 Md€ et
−0,17 M. L'aide d'avant était de 13,05 Md€ et non 12,67 (§ 2) : la population est
reconstruite avec l'étape « ir », qui change les ressources.

**Le RSA et la prime.** Le RSA ne bouge pas (−0,01 %). La prime baisse de 0,07 Md€ par
les hébergés : ceux dont l'aide était sous le forfait logement en retiraient moins que le
forfait ; hébergés à titre gratuit, ils en retirent le forfait entier, comme le veut la
règle. La colocation la remonte de 0,03 Md€ (une aide plus petite, un forfait plus
petit). Ce sont des mouvements de droit, pas des erreurs.

**Le niveau de vie** du premier dixième baisse de 0,5 % : l'aide retirée était dans les
bas revenus.

### 7.4 Ce que cela dit, et le pronostic révisé

L'écart de la ligne passe de −17 % à **−29 %** (11,16 contre 15,67 Md€), **hors de la
tolérance de ±25 %**. Le modèle était dans la tolérance parce qu'il comptait deux fois
des loyers. Ce qui manque désormais, −4,5 Md€ : hors champ ≈ 0,9 (foyers et résidences,
accédants, § 2.1 a et b) ; régime permanent nominal 0,23 ; loyer HLM de l'Ancols 0,13 ;
le reste, ≈ 3,2 Md€, pour l'essentiel des locataires ordinaires trop riches dans le
modèle (cause e : les revenus ne sont pas tirés selon le statut d'occupation) et trop
peu nombreux à être aidés (4,63 M d'allocataires contre 5,23 M de locataires aidés hors
foyers et accédants en 2023, −11 %). C'est la marge de revenu par statut d'occupation
(§ 3) qui le corrigerait.

**Pronostic révisé, ligne `aide_logement_montant` (±25 %)** — les années 2022 et 2023
gardent l'écart de pente du diagnostic (1 à 2 points plus bas que 2024) :

| année | publié, Md€ | pronostic |
|---|---|---|
| 2022 | 15,11 | −34 à −28 % (hors tolérance) |
| 2023 | 15,33 | −33 à −27 % (hors tolérance) |
| 2024 | 15,67 | −32 à −26 % (hors tolérance) |

La ligne neuve proposée « allocataires en zone 1 » (§ 3) baisse aussi (de +20 à +30 %
vers 0 à +20 %, hypothèse : la zone n'a pas été remesurée). **L'art. 74 du PLF 2027, volet logement** suit le niveau : de −82 M€ (§ 4) à
**−70 à −76 M€** contre −101 M€ officiels, encore dans la tolérance de 40 M€. Les autres
lignes ne bougent pas, sauf la prime (−0,5 % de niveau, −0,7 % de foyers servis).

### 7.5 Les tests

`tests/test_logement.py`, quatre tests neufs : l'hébergé n'a pas d'aide, en location
privée et en HLM (avant : 3 464 € par an, vu échouer) ; la famille de référence garde la
sienne ; le forfait logement du RSA de l'hébergé ne bouge pas (76,29 € par mois) ; la
colocation a 0,75 fois le plafond (208,71 € contre 278,28 €), la moitié du loyer
(350 €) et une aide plus basse de plus de 300 € par an (vu échouer). Sur le code d'avant
(`corrections.py` et `to_openfisca.py` remis), trois échouent ; le test du forfait passe,
il garde que rien ne bouge.

```
$ pytest -q -p no:randomly tests/test_logement.py
10 passed in 13.12s
$ pytest -m "not lourd and not chrono" -n 2 -q tests/test_engine.py
  tests/test_population.py tests/test_foyers_fiscaux.py tests/test_logement.py
  tests/test_prestations.py tests/test_secteur_public.py tests/test_salaires_exoneres.py
  tests/test_non_salaries.py
525 passed in 377.03s
```
