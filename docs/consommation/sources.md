# But 12 — les sources publiques de la consommation, de la TVA et des accises

Recherche du 2 novembre 2026. Chaque fichier cité a été téléchargé hors du dépôt, dans le
bac à sable de la session, ouvert et lu ; sa taille en octets et son sha256 sont ceux du
fichier servi ce jour-là. Rien n'est entré dans `data/` et rien n'a été ajouté au
manifeste (trois sources y sont déjà, dites « déjà au manifeste ») : ce document sert à
préparer les entrées de `KNOWN_SOURCES`, il ne les remplace pas. Les
chiffres cités sont relevés dans les fichiers ; ceux marqués « calcul » sont les miens et
ne sont pas publiés.

Licences : l'Insee et le SDES publient sous Licence Ouverte (Insee : page
<https://www.insee.fr/fr/information/2008466>, Licence Ouverte 2.0 ; SDES : mentions
légales, « licence ouverte telle que décrite dans le décret n° 2017-638 »). Pour les
autres producteurs, la licence est dite « non vérifiée » quand je ne l'ai pas lue.

## 0. En une page

| besoin | meilleure source | principal manque |
|---|---|---|
| 1. conso par poste × décile | Insee, BdF 2017, TF106 (326 postes, 10 déciles, euros) | croisements à une seule dimension ; 2017 |
| 2. CN par fonction | Insee, conso des ménages 2025, `T_CONSO_EFF_FONCTION` | COICOP 2018, pas celle de BdF ; 4 positions |
| 3. TVA par taux | DGFiP Stat. n° 37 (bases par taux 2024) + Trésor-Éco n° 371 | aucune TVA par taux payée par les seuls ménages |
| 4. énergie | SDES, bilan 2024 (Mtep et € des ménages par carburant) + Budget vert 2027 (60 % ménages) | pas de volume par décile ; litres à convertir |

## 1. La consommation des ménages par poste et par décile

### 1.1 Insee Résultats, « Les dépenses des ménages en France en 2017 » (France entière)

* Page : <https://www.insee.fr/fr/statistiques/4648335> (sommaire 4648339). Parue le
  15/09/2020 ; avis du 07/10/2020 : ajout du fichier de cadrage CAD01. Données : enquête
  Budget de famille 2017, collecte de septembre 2016 à septembre 2017. Licence Ouverte 2.0.
* Fichiers téléchargés et vérifiés :
  * `https://www.insee.fr/fr/statistiques/fichier/4648335/bdf2017fe_csv.zip` — 87 411 o —
    `f6d4a3344031f4acb6037a2a370deb7774d7b2e3d2192f600b38d75e3627169d`. Les 21 tableaux
    en CSV (UTF-8, séparateur `;`) : tf101 à tf107, tf201 à tf207, tf301 à tf307.
  * `https://www.insee.fr/fr/statistiques/fichier/4648335/bdf2017fe_xlsx.zip` — 456 611 o
    — `b0a881814dbc7e102dee6832c3a75f01818fb852acdc7c7a59b0978f193e6f4a`. Les mêmes en xlsx.
  * `https://www.insee.fr/fr/statistiques/fichier/4648335/metadonnees_bdf2017.csv` —
    44 714 o — `135fb2a80c84efad21bf78fe678259852519cebab1514546b9f47f0880fe1e0a`. Libellés
    de tous les codes (postes, modalités).
  * `https://www.insee.fr/fr/statistiques/fichier/4648335/TF106.csv` — 43 571 o —
    `438e502c70244f40e8eb0b019a1e89287e1c2fe1da0b063284258f8b9ac47f77` (identique au
    tf106.csv de l'archive). Le tableau central : dépense par poste et par décile.
  * `https://www.insee.fr/fr/statistiques/fichier/4648335/cad01_fe.xlsx` — 8 498 o —
    `3cc201e8a59283efb82279f997f0fa8d06907c45d058abe913f60056d414b5a2`. Effectifs de
    ménages (en milliers) par modalité de chaque croisement : 29 388 au total, de 2 924 à
    2 950 par décile.
* **Le niveau de détail.** Les tableaux TF101 à TF107 portent 326 postes, codés sur la
  COICOP (variante ECOICOP/HBS de l'Insee, avec des suffixes A, B, Z propres à l'enquête) :
  13 à 2 positions (01 à 12, plus 13 « hors champ » : impôts, gros travaux, remboursements),
  53 à 3, 113 à 4, 146 à 5, plus `CTOTALE` (« total de la consommation, champ comptabilité
  nationale »). Les tableaux TF201 à TF207 n'ont que 61 postes (`NOMENCLATURE2` : les 12
  divisions et 48 groupes à 3 positions).
* **Les postes de l'énergie** : 0450 « électricité + gaz (non dissociables) », 0451
  électricité, 0452 gaz et combustibles liquéfiés (gaz de ville, butane), 0453 combustibles
  liquides, 045A combustibles solides, 0722 = 07221 « carburants, électricité, huiles,
  lubrifiants ». **Gazole et essence ne sont pas séparés**, et l'électricité des véhicules
  est dans 07221.
* **Les croisements**, tous à une seule dimension (poste × une variable) :
  * TF101 zone d'étude et d'aménagement du territoire (8 ZEAT et les DOM) ;
  * TF102 âge de la personne de référence (7 classes) ;
  * TF103 catégorie socioprofessionnelle de la personne de référence (8) ;
  * TF104 catégorie de la commune (5 : rural, moins de 20 000 h, 20 000 à 100 000, plus de
    100 000, agglomération parisienne) — c'est la tranche d'unité urbaine regroupée ;
  * TF105 type de ménage (5 : personne seule, famille monoparentale, couple sans enfant,
    couple avec enfants, autre) ;
  * TF106 décile de niveau de vie (10) ;
  * TF107 statut d'occupation × quintile de niveau de vie (2 × 5) — le seul croisement
    double publié.
  Il n'y a **ni poste × décile × type de ménage, ni poste × décile × âge**.
* **Montants ou parts** : les TF1xx sont des **montants**, dépense annuelle moyenne en euros
  par ménage (moyenne sur tous les ménages de la cellule, consommateurs ou non) ; les TF2xx
  des **parts** (coefficients budgétaires en %, 61 postes) ; les TF3xx des taux
  d'équipement (33 biens, dont « au moins une voiture » et « 2 voitures ou plus », par
  décile en TF306).
* Exemples relevés dans TF106 (euros par ménage, D1 → D10) : total champ CN 16 123 → 48 353 ;
  0722 carburants 622 → 1 375 ; 0451 électricité 592 → 957 ; 0452 gaz 159 → 386.
* **Ce qu'elle ne donne pas.**
  * Les loyers imputés (041 = loyers effectivement payés, nets des aides) ; la santé est
    nette des remboursements. Pour la TVA payée par les ménages, ce sont les bons concepts.
  * Le niveau des comptes : l'enquête sous-déclare. Calcul (TF106 × 29,388 M ménages, contre
    les comptes de 2017 du millésime 2026) : carburants 32,6 Md€ contre 42,5 (77 %) ; énergie
    du logement 39,8 contre 46,2 (86 %) ; total 805 contre 1 006 hors loyers imputés (80 %).
  * Des postes à taux mixte : 0611 (médicaments remboursables à 2,1 %, non remboursables à
    10 %, appareils à 20 % ou 5,5 %), 111 restauration (10 %, alcool à 20 %), 0451/0452
    (abonnement à 5,5 % jusqu'au 31/07/2025 puis 20 %, consommation à 20 %).
  * Le champ est France entière, DOM compris (hors Mayotte, enquêtée un an plus tard) : la
    TVA des DOM (8,5 % et 2,1 %) et l'absence d'accise métropolitaine s'y appliquent.
* **Piège de lecture** : les `TFxxx.xlsx` sont en OOXML « strict » ; openpyxl 3.1.5 (le venv
  du dépôt) n'y lit aucune feuille. Lire les CSV. Dans le fichier de métadonnées, les codes
  perdent le zéro initial (`1`, `11`, `111` pour `01`, `011`, `0111` dans les tableaux).

### 1.2 Le même pour la France métropolitaine

* Page : <https://www.insee.fr/fr/statistiques/4648319>, parue le 15/09/2020. Mêmes
  tableaux, numérotés TM101 à TM307, déciles calculés sur la métropole.
  * `https://www.insee.fr/fr/statistiques/fichier/4648319/bdf2017fm_csv.zip` — 94 481 o —
    `31683080abc029659b516cab8d49a7156f0176fa5bc9de1cd1cd869524fe63b7`.
  * `https://www.insee.fr/fr/statistiques/fichier/4648319/bdf2017fm_xlsx.zip` — 453 992 o
    — `fcf2451c98b7dddd716d7263efa48f3c315a1827985d8438799ea13c6fac3c43`.
  * `https://www.insee.fr/fr/statistiques/fichier/4648319/cad01_fm.xlsx` — 8 492 o —
    `4aa6f40ca2af22331fbb5a93e0ce165327386ca25c2103c80aafee1c98b1fd65` (28 576 milliers de
    ménages).
* TM106 : total 16 547 (D1) → 48 456 (D10) ; 0722 : 616 → 1 366. À préférer si la
  population du moteur est métropolitaine, ou pour traiter les DOM à part.
* Les DOM : « La consommation des ménages dans les DOM en 2017 »,
  <https://www.insee.fr/fr/statistiques/4257987> (30/01/2020) — page sans fichier de données.

### 1.3 Insee Première n° 1749 et sa note de recalage

* Page : <https://www.insee.fr/fr/statistiques/4127596>, parue le 17/04/2019, données 2011
  et 2017.
  * `https://www.insee.fr/fr/statistiques/fichier/4127596/ip1749.xls` — 24 064 o —
    `e536f6cd4f0a0d4d962b9866077d5391eb9ae16083a6d42e56a64f7b7827c321`. Données **recalées
    sur les comptes** : écart à la moyenne par type de ménage, âge, statut, quintile et
    **tranche d'unité urbaine** (5 classes) ; parts par poste à 2 positions, propriétaires
    et locataires des quintiles 1 et 5.
  * `https://www.insee.fr/fr/statistiques/fichier/4127596/Note-methodologique-recalage.pdf`
    — 36 267 o — `435a7a19bf4bd8a03e2e947a2431040c8ce587fb6ee88a7f0c79c6183851fc6e`.
* La note décrit la méthode que le but peut reprendre : un facteur multiplicatif par poste
  de la COICOP à 12 postes, après avoir ramené les comptes au champ de l'enquête (ménages
  ordinaires, correction territoriale ventilée, sans autoconsommation, loyers imputés, Sifim,
  achats de véhicules entre particuliers). Sur ce champ commun, les comptes valent **84 %**
  de la consommation du champ habituel.
* Elle ne donne pas les facteurs de recalage poste par poste.

### 1.4 Une vague plus récente : non

* L'Insee a lancé l'édition 2026 le 2 janvier 2026 (communiqué :
  <https://www.insee.fr/fr/information/8719834>), 29 000 ménages, collecte sur toute l'année
  2026, désormais encadrée par un règlement européen ; édition suivante en 2030. Le document
  de travail Prometheus du CGDD (§ 4.1) annonce une « disponibilité en 2028 ». **Les tableaux
  de 2017 restent la seule source par poste et par décile** pour ce but.

### 1.5 Ce qui n'existe qu'en microdonnées

* Progedo-ADISP, « Budget des familles (BDF) - 2017 », DOI 10.13144/lil-1416,
  <https://data.progedo.fr/studies/doi/10.13144/lil-1416>. Statut « FPR » (fichier de
  production et de recherche) ; version 2 du 23/05/2025 (ajout de la table C06 ; version 1
  du 17/09/2020). Conditions (<https://data.progedo.fr/access_conditions>) : chercheurs,
  doctorants ou étudiants rattachés à un établissement habilité, habilitation individuelle
  par le Comité du secret statistique, engagement de confidentialité signé ; les données plus
  fines passent par le CASD, payant.
* Ce qu'on n'aura donc pas : les distributions jointes (poste × décile × type de ménage ou
  × âge), la part de ménages consommateurs et la dispersion dans une cellule, les quelque
  900 postes budgétaires de l'enquête (plus fins que les 326 publiés, et peut-être la
  séparation gazole et essence), et le lien ménage par ménage avec le revenu.

### 1.6 Le précédent : l'Insee, la DREES et la DG Trésor imputent déjà ainsi

* Le module de taxation indirecte d'Ines : André, Biotteau et Duval, document de travail
  DREES n° 60 (2016), page
  <https://drees.solidarites-sante.gouv.fr/publications/documents-de-travail-1998-2019/module-de-taxation-indirecte-du-modele-ines-hypotheses>.
  **Inaccessible** depuis cette session : le serveur rend une réponse vide (curl 52). Je n'ai
  pas utilisé de miroir.
* Le Trésor-Éco n° 371 (§ 3.3) répartit la TVA par niveau de vie avec « l'enquête Budget de
  famille 2017 recalée sur la consommation des ménages par poste de la comptabilité
  nationale » : c'est exactement l'imputation par cellule visée ici.

## 2. La consommation finale des ménages par fonction, comptes nationaux

### 2.1 Insee Résultats, « Consommation des ménages en 2025 » (base 2020)

* Page : <https://www.insee.fr/fr/statistiques/8988813>, parue le 29/05/2026. Séries de 1959
  à 2025 (campagne de mai 2026 : 2025 provisoire, 2024 semi-définitif). Licence Ouverte 2.0.
* `https://www.insee.fr/fr/statistiques/fichier/8988813/T_CONSO_EFF_FONCTION_fr.xlsx` —
  546 600 o — `e7a0b42f2b572c7b92a42ce4f02b616df22410d7781d806c350dbe4ab9f7396d`.
  Consommation effective des ménages par fonction, « niveaux diffusables les plus fins » :
  onglets `MEURcour` (M€ courants), `MEUR2020` (volumes chaînés), indices de prix, de valeur
  et de volume, `COEFFCOUR` (coefficients budgétaires).
  * **Nomenclature : COICOP 2018**, jusqu'à 4 positions (101 classes à 4 positions) : 08
    est devenu « Information et communication », 09 « Loisirs,
    sport et culture », 12 « Assurance et services financiers », 13 « Soins corporels,
    protection sociale… », CP14 et CP15 les dépenses individualisables des ISBLSM et des
    APU, CP16 le solde territorial. BdF 2017 suit l'ancienne COICOP : **il faut une table de
    passage**, surtout pour les postes 08, 09, 12 et 13.
  * La ligne `CPDEP` « Dépense de consommation des ménages » isole la dépense des ménages
    de la consommation effective : 1 527,1 Md€ en 2024.
  * Relevés pour 2024 (M€) : CP0451 électricité 42 132 ; CP0452 gaz 16 753 (gaz liquéfiés
    compris) ; CP0453 combustibles liquides 3 091 ; CP0722 carburants et lubrifiants 51 955 ;
    CP042 loyers imputés 220 469 (à retirer) ; CP111 restauration 104 236.
* `https://www.insee.fr/fr/statistiques/fichier/8988813/T_CONSO_EFF_PRODUITS_MENAGES_fr.xlsx`
  — 1 497 046 o — `6af541fc634d01b996659c2c86f0f2096826e6549de4dad46c37cf24b5c6ed2d`.
  Dépense des ménages par **produit** (CPF, jusqu'à un niveau plus fin que A138). Il sépare
  les carburants, que la COICOP ne sépare pas : 2024, super sans plomb 22 784 M€, gasoil
  27 268, fioul domestique 3 091, GPL 1 609, lubrifiants 1 823.
* `https://www.insee.fr/fr/statistiques/fichier/8988813/T_2201_2202_fr.xlsx` — 45 332 o —
  `694cf01bf7f06ef46f4a59ec282e8e96d1b6cf33bc359245b6e41bcc11bac906`. Tableaux 2.201 et
  2.202 simplifiés (Md€).
* `https://www.insee.fr/fr/statistiques/fichier/8988813/T_5201_5203_fr.xlsx` — 158 738 o —
  `fea52ce32e32a2e140cc8f358762974b6fd5c55a1c46565846062c1560ea3e63`. Dépense de
  consommation finale par produit en 38 postes.
* **Ce qu'elles ne donnent pas** : aucune répartition par ménage ou par décile, pas de 5ᵉ
  position COICOP, et le champ est celui des comptes (non-résidents, ménages hors ménages
  ordinaires, autoconsommation), qu'il faut ramener à celui de l'enquête (§ 1.3).

### 2.2 Les comptes par catégorie de ménage (contrôle de forme seulement)

* Page : <https://www.insee.fr/fr/statistiques/8574663>, parue le 16/04/2026, comptes
  distribués 2020 à 2023 (expérimentaux).
  * `https://www.insee.fr/fr/statistiques/fichier/8574663/T_CND_101.xlsx` — 40 759 o —
    `8e4d2ec005e9351f7105c796ac2e0ae8afc1f53b70b165d04f9387ed8cf838ef` (par vingtième de
    niveau de vie).
  * `https://www.insee.fr/fr/statistiques/fichier/8574663/T_CND_102.xlsx` — 26 365 o —
    `2d590a3ac1badcb877dd8e674dc89d347b6ec35324899ae791c45b130a66d945` (par groupe).
* Une ligne « Taxes sur les produits (TVA, TICPE, accises, DMTO, etc.) » répartie par
  vingtième : 318,6 Md€ en 2023, de 8,2 (V1) à 33,3 (V20). C'est **toute** la D21 de
  l'économie imputée aux ménages, pas la TVA seule ni ce que paient les ménages : un contrôle
  de profil, pas une cible. Pas de consommation par poste. La campagne suivante est annoncée
  pour novembre 2026 (<https://www.insee.fr/fr/statistiques/8988803>).

## 3. Les recettes de TVA par taux, et la part des ménages

### 3.1 DGFiP Statistiques n° 37, « La TVA économique augmente de 1,1 % en 2024 »

* Page : <https://www.impots.gouv.fr/dgfip-statistiques-la-tva-economique-augmente-de-11-en-2024>,
  parue le 02/09/2025, données des déclarations de 2024. Licence non vérifiée sur la page
  (Licence Ouverte pour les autres numéros déjà au manifeste).
  * `https://www.impots.gouv.fr/sites/default/files/media/9_statistiques/0_etudes_et_stats/0_publications/dgfip_statistiques/2025/num37_09/dgfip_stat_37_2025.xlsx`
    — 53 480 o — `454b74964e8c736b74eedd59ad94f3ba5e9eef1b3596c80a5dfe8cdff42bad8f`.
  * `https://www.impots.gouv.fr/sites/default/files/media/9_statistiques/0_etudes_et_stats/0_publications/dgfip_statistiques/2025/num37_09/dgfip_stat_37_2025.pdf`
    — 503 098 o — `16e34932647e399304450655ea8ba6029166b0fa7be3e8d1f32ffe93ac9eb62a`.
* **Tableau 3, « Évolution des bases de TVA par taux » (2024, Md€)** : chiffre d'affaires
  taxable 5 588 ; taux normal 20 % 3 987 (71,4 %) ; intermédiaire 10 % 312 ; réduit 5,5 %
  848 ; particulier 2,1 % 126 ; DOM 8,5 % 36 et 2,1 % 21 ; produits pétroliers continent
  (20 %) 72, Corse (13 %) 1 ; importations au taux normal 145, aux taux réduits 28 ; autres
  11. Tableau 1 : TVA collectée 938 Md€, TVA économique 203 + 5,6 (guichets uniques) = 209.
* Calcul de contrôle : base × taux redonne 925 Md€ de TVA collectée sur les lignes à taux
  unique, contre 938 publiés. **C'est une TVA collectée sur toutes les ventes**, achats des
  entreprises compris, dont la majeure partie est ensuite déduite : elle ne dit pas ce que
  paient les ménages.

### 3.2 DGFiP Statistiques n° 50, « La TVA économique augmente de 1,0 % en 2025 »

* Page : <https://www.impots.gouv.fr/dgfip-statistiques-la-tva-economique-augmente-de-10-en-2025>,
  parue le 15/09/2026, données 2025.
  * `https://www.impots.gouv.fr/sites/default/files/media/9_statistiques/0_etudes_et_stats/0_publications/dgfip_statistiques/2026/num50_09/dgfip_stat_50_tva-2026.xlsx`
    — 38 569 o — `e57c79d75e39de490f81a9b09bfe992fd2dfae3ebf32de4fd8817aa9c77d4bea`.
  * `https://www.impots.gouv.fr/sites/default/files/media/9_statistiques/0_etudes_et_stats/0_publications/dgfip_statistiques/2026/num50_09/dgfip_stat_50_tva-2026.pdf`
    — 289 279 o — `9bb1223226f5bb300ebeadc4aa2f5b0493a73851128de05dd1b32502fb1c14f7`.
* TVA collectée 943,3 Md€, TVA économique 210,7 ; « graphique 1 » : variations de base par
  taux de 2021 à 2025 en Md€ (2025 : 20 % +6,5 ; 5,5 % +28,5 ; 10 % +11,9 ; 2,1 % +8,9).
  **Les niveaux par taux ne sont publiés que pour 2024** (n° 37).
* À ne pas confondre : `https://www.impots.gouv.fr/sites/default/files/media/9_statistiques/0_etudes_et_stats/0_publications/dgfip_statistiques/2024/num20_03/dgfip_stat_20_2024.pdf`
  (n° 20, mars 2024, 219 635 o, `601d9b7a0e65ccd6fbe2d5883e330a05811ad5592ce2626a0b3202f4045da59a`)
  est une première estimation de 2023 sans détail par taux.

### 3.3 DG Trésor, Trésor-Éco n° 371, « Analyse de la composition des recettes de TVA »

* Page : <https://www.tresor.economie.gouv.fr/Articles/2025/09/25/analyse-de-la-composition-des-recettes-de-tva>,
  parue le 25/09/2025. Modèle de la TVA théorique sur le compte semi-définitif 2022. Licence
  non vérifiée (la DG Trésor n'est pas dans la liste des producteurs donnée, mais c'est une
  administration de l'État).
  * `https://www.tresor.economie.gouv.fr/Articles/c462ac7f-76db-4c33-9bb3-dcc6886ed898/files/f4d0d1ac-fc61-4cf3-ab3f-094385b218bd`
    — 544 891 o — `d3daa52ccfdc05978c7939d97ece4018803c0d0a868191c5c538699dc6bcadfb`.
* **La part des ménages** : « En 2022, 65,1 % des recettes de TVA nette émanaient des
  ménages, 14,1 % des administrations publiques, 19,4 % des entreprises et 1,5 % des
  associations. »
* **Le rendement d'un point par taux en 2025** (tableaux 1 et 2, Md€) : brut 13,7 (2,1 % :
  0,4 ; 5,5 % : 2,4 ; 10 % : 1,9 ; 20 % : 8,9) ; net de la part payée par les APU 11,4
  (0,4 ; 2,0 ; 1,6 ; 7,5). Calcul : soit des assiettes rémanentes d'environ 40, 240, 190 et
  890 Md€, tous agents confondus.
* Par niveau de vie (BdF 2017 recalée) : 12 % du rendement d'une hausse uniforme porte sur le
  premier cinquième, 31 % sur le dernier ; plus de 40 % de la consommation des ménages n'est
  pas au taux plein.
* **Manque** : la ventilation par taux et par agent (graphique 3) n'existe qu'en image ; les
  assiettes des seuls ménages par taux ne sont pas chiffrées dans le texte.

### 3.4 Voies et moyens, tome I, PLF 2026 (déjà au manifeste)

* `https://www.assemblee-nationale.fr/dyn/dyn/contenu/visualisation/1087930/file/PLF%202026%20-%20V&M%20TI%20-%20Evaluations%20des%20recettes.pdf`
  — 1 099 987 o — `4703605df8bfd1b4a20b1889839ebc1ea5a9b434eb4460eb2b40749e107371a0`
  (`vm_tome1_plf2026_recettes.pdf`). Annexe au PLF 2026, octobre 2025 ; exécution 2024.
* Pages 31 à 33 : TVA brute totale 289,2 Md€ en 2024, remboursements 78,5, nette totale
  210,7, dont État 96,8. Et : « la TVA repose pour environ **trois cinquièmes** sur les
  dépenses de consommation des ménages et, pour le reste, sur l'investissement […] et les
  consommations intermédiaires non déductibles (pour un cinquième chacun environ) ».
  **Aucun détail par taux.**
* Le tome I du PLF 2025 se re-source : `https://www2.assemblee-nationale.fr/static/17/Annexes-DL/PLF-2025/Voies_et_moyens_Tome_1_2025.pdf`
  — 1 563 676 o — `c01eccd5eb0a96912b0ad84b5db354fc3c9eaf80bd7db20c023e10057ab5648b`,
  **le sha256 de `voies_et_moyens_tome1_plf2025.pdf`, en quarantaine faute d'URL** (D-028).

### 3.5 Voies et moyens, tome II, PLF 2026 : dépenses fiscales (déjà au manifeste)

* `https://www.assemblee-nationale.fr/dyn/dyn/contenu/visualisation/1087933/file/Voies_et_moyens_Tome_2_2026.pdf`
  — 1 556 078 o — `f8fdf8072037fbc0cff1839c880718f184ea0c011572ae43bf58a12b20142214`.
* Dépenses fiscales de TVA : 10 920 M€ (2024), 11 005 (2025), 12 366 (2026). Fiches relevées
  (réalisation 2024 / prévision 2025 / 2026, M€) : 730221 restauration à 10 % 2 025 / 2 035
  / 2 275 ; 730213 travaux à 10 % 2 195 / 2 205 / 2 465 ; 730223 rénovation énergétique à
  5,5 % 935 / 940 / 1 050 ; 730205 hébergement à 10 % 695 / 695 / 780.
* **Deux pièges.** Depuis le PLF 2024, le coût d'une dépense fiscale de TVA est la seule
  part de l'État après transferts (environ la moitié de la recette). L'estimation avant
  transferts est annoncée « en annexe au présent tome II » : **je ne l'ai pas trouvée dans
  les 252 pages**. Et les taux réduits les plus coûteux **ne sont pas** des dépenses
  fiscales (p. 10-11) : 5,5 % sur l'alimentation et l'eau, 2,1 % sur les médicaments
  remboursables, 10 % sur le transport de voyageurs, 5,5 % sur les livres. Le tome II ne
  peut donc pas contrôler seul les assiettes à taux réduit.

### 3.6 Conseil des prélèvements obligatoires, « La TVA, un impôt à recentrer… », 2023

* `https://www.ccomptes.fr/system/files/2023-02/20230209-TVA_0.pdf` — 1 852 793 o —
  `ee67a7229d9357d2f4cf005d1e767297a6f608a5e78e279060142903daedf8a7`. Rapport de février
  2023 (fichier daté du 9 février). Licence non vérifiée.
* Les mesures dérogatoires au taux normal coûtent « au moins 47 Md€ » (24 % du rendement de
  2021) ; tableau 2, les dix plus coûteuses en 2020 (Md€) : 5,5 % sur l'alimentation 20,1 ;
  10 % travaux 3,3 ; 10 % restauration 3,0 ; DOM 2,9 ; 10 % transport 2,8 ; 2,1 %
  médicaments 2,6 ; 5,5 % rénovation énergétique 1,3 ; 5,5 % logement social 1,0 ;
  appareillages handicapés 0,9 ; 10 % locatif social 0,9. La base au taux normal est 65 %
  de l'assiette (2019). **C'est le seul chiffrage public trouvé des taux réduits hors
  dépenses fiscales**, mais il date de 2020.
* Non trouvé : le rapport particulier n° 5 du CPO (Grégoire et Veillon, 2022) sur les effets
  par niveau de vie ; un rapport de la Cour des comptes donnant la TVA par taux.

### 3.7 Comptes nationaux, tableau 3.217 (déjà au manifeste)

* `https://www.insee.fr/fr/statistiques/fichier/8988845/t_3217_fr.xlsx` : TVA (D211)
  207,8 Md€ en 2024, en droits constatés, toutes catégories de payeurs.

### 3.8 Voies et moyens du PLF 2027 : non trouvé

* La page du dossier de l'Assemblée (<https://www.assemblee-nationale.fr/dyn/17/dossiers/PLF_2027>,
  lue le 2 novembre 2026) liste « Voies et Moyens, tome 1 » et « tomes 2 » **sans lien**.
* budget.gouv.fr renvoie 403 (Incapsula) à toutes les requêtes de cette session. Je ne l'ai
  pas contourné.

## 4. L'énergie

### 4.1 La consommation de carburants des ménages

**SDES, « Bilan énergétique de la France pour 2024 »**, données définitives. Page :
<https://www.statistiques.developpement-durable.gouv.fr/bilan-energetique-de-la-france-pour-2024>,
publication du 03/03/2026 (page du 04/03/2026). Licence ouverte (décret 2017-638).

* `https://www.statistiques.developpement-durable.gouv.fr/media/8958/download?inline` —
  947 562 o — `10f6c43b574c28726a542831419ff484c0321cf86fdb2ce5fdf73816ef7ebdb9`. Séries
  longues (xlsx), 1960 à 2024, une ligne par série (`CODTOT`, libellé, énergie, unité,
  niveau géographique, données réelles ou corrigées du climat). Séries **des ménages** pour
  la France entière (2017 → 2024) :
  * PS203MFR gazole routier, biodiesel compris : 19,84 → 15,19 Mtep ;
  * PS204MFR supercarburants, bioessence comprise : 6,98 → 9,66 Mtep ;
  * PS206MFR GPL carburant : 0,07 → 0,12 Mtep ; PS249/PS250 : les mêmes hors biocarburants ;
  * N149MFR dépense en gazole : 28 411 → 29 901 M€ ; N150MFR supercarburant : 12 444 →
    22 752 M€ ;
  * 1328 dépense moyenne par ménage en carburants : 1 672,5 € (2024).
* `https://www.statistiques.developpement-durable.gouv.fr/media/9087/download?inline` —
  8 592 722 o — `42a090baa16d0e3873995af0c3066dd5cda20b39c010db5f1ce64fa072d79028`. La
  publication (PDF) : en 2024 les ménages dépensent 52,8 Md€ en produits pétroliers pour le
  transport ; les taxes énergétiques font **36,5 %** de leur dépense de carburant (65 €/MWh
  en moyenne ; calcul : environ 19 Md€) ; l'ex-TICPE rapporte 30,7 Md€ nets des
  remboursements avant affectations ; la TVA sur les produits pétroliers, hors part
  déductible, 9,7 Md€.
* `https://www.statistiques.developpement-durable.gouv.fr/media/8956/download?inline` —
  288 287 o — `8c6589a675b50e1294411836a161129d0638838eb949324ddb99944a82b4fc3f` (figures,
  dont l'onglet « Analyse dépense des ménages »).
* `https://www.statistiques.developpement-durable.gouv.fr/media/8957/download?inline` —
  92 871 o — `506a86b062ae9fab86ef3ce1e727cfc71bf4b294c1d5fd31724b1c371796e320` (bilans
  physiques et monétaires 2020-2024).
* **Ce qu'il ne donne pas** : des litres (les accises sont en €/hl ; les coefficients de
  conversion devraient être dans la méthodologie, `media/9074`, non téléchargée) et un
  détail par décile. Les euros diffèrent de l'Insee : 29,9 Md€ de gazole contre 27,3 en
  comptes nationaux (§ 2.1) pour 2024 ; le super concorde (22,8). L'écart est à trancher
  avant d'en faire une cible.

**Insee, « Consommation de produits pétroliers »** (source : Comité professionnel du
pétrole). Page <https://www.insee.fr/fr/statistiques/2119673>, parue le 23/10/2026, 1965 à
2025.

* `https://www.insee.fr/fr/statistiques/fichier/2119673/sect-ind-ener-petrole-conso.xlsx` —
  28 003 o — `07a4682ec0b6f6e51d8c0238f33b341d7bd121e6497d1fdc964f46f910ba8554`. En Mt,
  **tous consommateurs** : gazole 27,98 (2024) et 27,02 (2025) ; carburants auto 11,14 et
  11,77 ; fioul domestique 3,57 et 3,46.

**Par décile.**

* BdF 2017, TF106 et TM106 : poste 0722 en euros, sans séparer les carburants (§ 1.1).
* CGDD, document de travail « Le modèle Prometheus de microsimulation de la facture
  énergétique des ménages », mars 2025 :
  `https://www.ecologie.gouv.fr/sites/default/files/publications/document_travail_70_prometheus_microsimulation_facture_energetique_menage_mars2025.pdf`
  — 3 554 927 o — `924fd2ba47f347bc09771808c762a5e9d68dfd47b426b4f88868877ef8360327`.
  Licence non vérifiée. **Tableau 15 (2019, métropole) : facture par décile et par énergie**,
  avec le gazole et l'essence séparés : D1 645 € de gazole et 159 € d'essence, D10 1 251 et
  578 ; moyenne 1 048 et 343. Tableaux 16 et 17 : fiscalité et taux d'effort par décile.
  Sources : ENL 2013, EMP 2019, ERFS. Ce sont des euros de 2019, et le modèle, pas une
  observation.

### 4.2 Les recettes des accises sur l'énergie, et la part des ménages

* **Voies et moyens, tome I, PLF 2026** (§ 3.4), pages 26 à 31, exécution 2024 : ex-TICPE
  (ligne 1501) brute totale 31,6 Md€, transferts aux collectivités −11,9, AFITF −1,7,
  brute État 18,1, remboursements −2,0, **nette État 16,0** ; gaz naturel (1502) nette
  2 739 M€ ; **électricité (1503) nette 1 518 M€** en 2024, 5 630 M€ prévus en 2025 (sortie
  du bouclier). La nomenclature 1501 à 1504 est neuve (D-166).
* **Comptes nationaux, tableau 3.217** (§ 3.7), 2024 : TICPE 30,2 Md€, TICFE 4,8, TICGN 3,2.
  L'écart avec la ligne 1503 (1,5) est à expliquer avant de choisir une cible pour
  l'électricité.
* **Voies et moyens, tome II, PLF 2026** (§ 3.5) : dépenses fiscales d'accise de 2024, sur
  les produits énergétiques 6 307 M€, sur l'électricité 763, sur le gaz 802. Ce sont surtout
  des tarifs professionnels : 800221 transport routier de marchandises 1 178 ; 800229
  travaux agricoles 1 754 ; 800220 taxis 59 ; 800401 DOM 1 466. Elles bornent par
  différence ce que paient les ménages.
* **Rapport sur l'impact environnemental du budget (« Budget vert »), annexe au PLF 2027**,
  octobre 2026 :
  `https://www.assemblee-nationale.fr/dyn/contenu/visualisation/1129732/file/4-Jaune%202027%20-%20Budget%20vert.pdf`
  — 6 506 495 o — `db144c8a202c50553520d3cdc4d4c7124deca39ad06d67caa0729be5789f0600`,
  312 pages ; Assemblée nationale, Licence Ouverte selon le manifeste.
  * **Partie II, section C (p. 249-262)** : « L'accise sur les énergies représente 39,7 Md€ de
    recettes nettes en 2025 […] Elle est payée à **60 % par les ménages** et à 40 % par les
    entreprises et administrations » (63 % et 37 % pour la composante carbone).
  * **Par ménage en 2025** (modèle Prometheus, métropole) : 750 € de fiscalité énergétique
    hors TVA (225 € pour le logement, 525 € pour le transport ; 600 € sur les combustibles et
    carburants, 150 € sur l'électricité). **Par décile** : D1 490 € (190 + 300), D10 1 005 €
    (300 + 705) ; 3,4 % et 0,8 % du revenu. Les déciles intermédiaires et les découpages
    par aire d'attraction ne sont qu'en graphiques.
  * Tableau 6 (p. 296-297) : tarification effective du carbone en 2026 par acteur et par
    produit.
* SDES (§ 4.1) : accises et CTA font 9,6 % de la dépense d'énergie du logement, 199 € par
  ménage en 2024.
* **Manque** : aucun montant publié de l'accise sur l'électricité payée par les seuls
  ménages ; il se reconstruit (tarif « ménages et assimilés » × consommation résidentielle),
  et 2024 est une année anormale (bouclier jusqu'en février).

### 4.3 La consommation d'électricité et de gaz des ménages

* SDES, séries longues (§ 4.1), France entière, 2024 : électricité du résidentiel
  **150,94 TWh** (EL043TFR ; 161,12 en 2017), dépense TTC 42 246 M€ (CE027MFR), prix TTC
  279,9 €/MWh (CE063) ; gaz naturel du résidentiel **100,24 TWh PCI** (GA026TFR), soit
  111,38 PCS (GA026SFR ; 142,71 PCI en 2017), dépense TTC 13 978 M€ (CO019MFR) ; fioul
  domestique des ménages 2,54 Mtep (PS202MFR), GPL combustible 0,65 Mtep.
* CRE, Observatoire des marchés de détail du 1er trimestre 2026 (juin 2026) :
  `https://www.cre.fr/fileadmin/Documents/Rapports_et_etudes/2026/Observatoire_T1_2026.pdf`
  — 4 494 584 o — `a202fa91e9a22e186133ff1650bde613d7d08940fedd55e47c55dccf62db0d50`.
  Licence non vérifiée (la page des mentions légales renvoie 404). Tableau 2 : 35 082 000
  sites résidentiels d'électricité au 31/03/2026, 144,3 TWh annualisés ; tableau 6 :
  10 311 000 sites résidentiels de gaz, 93 TWh. Ce sont des sites (résidences secondaires
  comprises), pas des ménages ; aucune répartition par revenu.
* Comptes nationaux (§ 2.1) : CP0451 et CP0452 en euros. Le gaz de la COICOP comprend les
  gaz liquéfiés (16,8 Md€ contre 14,0 pour le seul gaz naturel du SDES).

## 5. Ce qui manque, ou ce qui a bloqué

* Les Voies et moyens du PLF 2027 (tomes I et II) : pas de lien sur la page du dossier de
  l'Assemblée ; budget.gouv.fr bloqué (403 Incapsula, non contourné). Les PLF 2026 servent
  à leur place.
* data.economie.gouv.fr : la connexion est coupée par le relais (`ws_closed_mid_exchange`,
  quatre essais). La liste dématérialisée des dépenses fiscales n'a pas été vue.
* Le document de travail DREES n° 60 (module de taxation indirecte d'Ines) : réponse vide du
  serveur.
* Aucune TVA par taux payée par les seuls ménages n'est publiée ; on n'a que des parts
  (trois cinquièmes, 65,1 %) et le point de TVA par taux tous agents.
* Aucun volume de carburant (litres) par décile ; aucun croisement poste × décile × type
  de ménage hors microdonnées.
* L'IPP publie les barèmes de la TVA et de la TICPE (<https://www.ipp.eu/baremes-ipp/>),
  utiles comme paramètres, non téléchargés : ce ne sont pas des agrégats.

## 6. Avis sur l'imputation par cellule

**Poste × décile : faisable, et sans inventer de répartition.** TF106 (ou TM106) donne un
montant par ménage pour 326 postes × 10 déciles, sur des déciles de niveau de vie au sens de
l'Insee (échelle OCDE modifiée), la même que celle du moteur. C'est la méthode de la DG
Trésor (Trésor-Éco n° 371) : BdF 2017 recalée sur les comptes par poste. La chaîne a trois
maillons publics : la cellule de 2017 ; un facteur par poste vers les comptes de 2024 (ramenés
au champ de l'enquête comme dans la note de l'IP 1749) ; une table de passage entre l'ancienne
COICOP et la COICOP 2018. Ce dernier maillon est le plus fragile.

**× type de ménage : seulement par hypothèse.** TF105 et TF106 sont deux marges séparées.
Une cellule décile × type demande un calage croisé (IPF) qui suppose qu'aucune interaction
n'existe au-delà des marges. C'est une hypothèse à préenregistrer et à dire. La vraie
cellule jointe est dans le FPR de l'ADISP, hors de portée.

**Les contrôles d'agrégats existent** : la TVA nette, et sa part payée par les ménages (trois
cinquièmes selon les Voies et moyens, 65,1 % en 2022 selon le Trésor) ; le point de TVA par
taux ; les bases DGFiP par taux ; les accises payées à 60 % par les ménages et les 750 € par
ménage, D1 et D10 compris (Budget vert) ; les Mtep et euros de carburant des ménages (SDES).

**Quatre risques à traiter avant le juge** :
* séparer gazole et essence par décile (Prometheus 2019, ou les parts nationales du SDES) ;
* le champ DOM (TF ou TM) ;
* les postes à taux mixte ;
* l'écart de 2,6 Md€ sur le gazole entre le SDES et l'Insee.
