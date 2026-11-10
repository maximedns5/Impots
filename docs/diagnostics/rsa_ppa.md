# Diagnostic rsa_ppa : le RSA servi à deux fois trop de foyers, la prime à trop peu

Diagnostic du 10 novembre 2026, après le but 18. Consigne : `docs/diagnostics/CONSIGNE.md`.
Rien n'est modifié hors de ce fichier. Les scripts d'essai sont dans `/tmp/diag_rsa_ppa/`
(`run_sample.py`, `run_indep.py`, `analyse.py`, `decomp.py`, `decomp2.py`,
`an_indep.py`) ; les publications téléchargées, dans `/tmp/diag_rsa_ppa/dl/`.

**Toutes les mesures du modèle de ce fichier sont faites sur un échantillon** : 20 000
ménages (43 584 personnes) tirés par `runner.subsample` (tirage systématique proportionnel
au poids, graine `SAMPLE_SEED` = 20240101, poids repondérés pour garder le total), droit
2024, population de 2024, palier complet, sans imputation (comme la passe de la grille).
L'échantillon refait la passe entière à 2 % près : RSA de décembre, 3,684 M de foyers
contre 3,622 M ; masse annuelle de droits 26,71 Md€ contre 26,31 ; prime d'activité,
4,961 M de foyers contre 5,046 M, 12,79 Md€ contre 12,97.

## 1. L'écart, en une phrase

Le RSA versé, droits simulés divisés par le pont de 1,355, dépasse de +61,4 % (2022),
+58,4 % (2023) et +64,7 % (2024) le total de la Cnaf (11,4 / 11,6 / 11,8 Md€), et ses
foyers de +97,8 % et +98,4 % (2023, 2024 : 3,6 M contre 1,82 M) ; la prime d'activité,
divisée par 1,725, est à −28,2 %, −30,0 % et −26,9 % (contre 9,7 / 10,2 / 10,3 Md€) quand
ses foyers sont à +11,5 %, +6,0 % et +9,0 % (`docs/verification/GRILLE.md`).

La réponse courte : **la moitié des foyers « au RSA » du modèle sont des familles
d'indépendants à qui la population ne donne aucun revenu** ; une fois ceux-là traités, le
RSA tombe dans sa fourchette. La prime, elle, n'a pas « assez de foyers » : la grille
compare des ayants droit à des payés. Rapportée au non-recours publié, elle a **moitié trop
peu d'ayants droit, chacun trop bien payé**.

## 2. Ce que le modèle fait

La chaîne, du fichier de données à la variable OpenFisca :

1. **La population** (`data/processed/population_2024.parquet`, 199 451 ménages) vient de
   l'enquête Emploi, qui ne porte aucun revenu. `population/incomes.py` en tire trois :
   * le salaire, pour les seuls **salariés** occupés (`incomes.py:267-273`) : un salaire
     en équivalent temps plein tiré d'une distribution publiée, fois la quotité, fois
     douze mois. Personne n'a d'année incomplète : un emploi à la semaine de l'enquête vaut
     douze mois de salaire au même taux ;
   * une pension pour **tout** inactif de 55 ans ou plus (`incomes.py:79`, `:285`), et
     pour lui seul ;
   * une allocation chômage pour **tout** chômeur au sens du BIT (`incomes.py:297`) : la
     masse de l'Unédic est répartie sur tous, aucun chômeur n'est non indemnisé.
   * Rien d'autre (`incomes.py:19-21`) : ni revenu d'indépendant, ni revenu du capital ou
     de l'épargne, ni AAH, ASS, pension d'invalidité, pension alimentaire. Les **3,98 M
     d'indépendants** occupés (pondérés ; 3,89 M sur la population entière) ont un revenu
     d'activité nul.
2. **Les familles** (`population/skeleton.py:475-508`) : la personne de référence, son
   conjoint et les enfants rattachés forment la famille 0 du ménage ; tout autre adulte
   (un enfant de 25 ans ou plus chez ses parents, un colocataire) devient demandeur de sa
   propre famille. `etudiant` n'est jamais écrit.
3. **Le câblage** (`population/to_openfisca.py:389-430`) : salaire, pension et chômage
   annuels divisés par douze et écrits identiques sur les 36 mois de 2022 à 2024. La base
   trimestrielle du RSA (`rsa_base_ressources`, moyenne des trois mois précédents) et de la
   prime voit donc chaque mois le douzième de l'année : aucune variation infra-annuelle.
4. **Le calcul** : OpenFisca 176.0.8, `rsa` et `ppa` au niveau famille, mois par mois.
   Le droit est servi à tout ayant droit : **le recours est de 100 %**.
5. **La lecture** : la grille somme les douze mois (`runner.py:313-322`) et compte les
   familles dont le droit de **décembre** dépasse 0,50 € (`runner.py:306-310`).
6. **Le pont** : `verification.py:34` divise la masse annuelle par 1,355 (RSA) et 1,725
   (prime), milieux de `margins.TAKE_UP_BRIDGE` (`population/margins.py:300-303`). Les
   **comptes** de foyers ne sont pas divisés. Le pont n'est lu que par la réconciliation
   (`population/reconcile.py:302`) et la grille (`verification.py:83-84`) : **aucune
   étude ne le lit** (recherche de `TAKE_UP`, `recours`, `PONT` dans `src/impots`).

## 3. Ce que la statistique publique compte

* **Montants** (`docs/verification/lignes.json`, `rsa_montant`, `ppa_montant`) : le
  rapport du directeur comptable et financier de la Cnaf sur les comptes de chaque année,
  § 4.1.3, droits constatés, branche Famille (pour le RSA, parts État et départements
  additionnées). Champ Caf : la MSA n'y est pas (la Caf faisait 98,5 % des dépenses et des
  bénéficiaires du RSA tous régimes en 2022, RSA Conjoncture n° 45, p. 2 ; 96,4 % des
  dépenses de prime en 2023, PA Conjoncture n° 32, p. 2). Ce sont des sommes **versées**,
  donc après non-recours.
* **Foyers** : la moyenne du quatrième trimestre, champ Caf, France entière. RSA :
  1 826 000 au T4 2024, montant moyen 557 €/mois (Cnaf-DSER, RSA Conjoncture n° 45, mars
  2025, tableau 1, p. 4,
  https://www.caf.fr/sites/default/files/medias/cnaf/Nous_connaitre/Recherche_et_statistiques/Rsa%20Conjoncture/RSA%20Conjoncture_2024T4.pdf).
  Prime : 4 628 000, 200 €/mois (PA Conjoncture n° 32, tableau 1, p. 4, déjà au manifeste,
  `data/raw/cnaf_pa_conjoncture_32_2024t4.pdf`). Ce sont des foyers **payés**.
* **Le non-recours**, d'où sort le pont :
  * RSA : Drees, Études et Résultats n° 1370 (mai 2026, C. Gayet), tableau 1, p. 3,
    France métropolitaine, logement ordinaire, T4 2021. Éligibles 1 505 à 1 683 milliers,
    recourants 944 à 1 122, non-recourants 561 ; non-recours de 37 à 33 % des foyers, de 32
    à 29 % de la masse ; « beta error » (bénéficiaires jugés non éligibles) 16 % des foyers,
    11 % de la masse. Le site de la Drees refuse le conteneur (réponse vide ou 503, le 10
    novembre) ; le PDF a été lu sur une copie,
    https://www.lemediasocial.fr/hulkStatic/EL/ELI/2026/05/fcdfaf271-f458-4b5a-8fbc-d2700ed9db7a/sharp_/ANX/er1370-non-recours-rsa.pdf,
    dont le sha256 (dd2f52db…) est **celui du fichier mis en quarantaine** sans URL dans
    `data/raw/MANIFEST.json` (`drees_ER1370_non_recours_RSA.pdf`) : c'est le même fichier.
  * Prime : Drees, Études et Résultats n° 1379 (juillet 2026),
    https://www.drees.solidarites-sante.gouv.fr/sites/default/files/2026-07/ER1379_Non-recours_PA.pdf.
    **Non lu** : le serveur refuse le conteneur. Ce que j'en cite vient du résumé d'un
    moteur de recherche et reste à vérifier : 6,6 à 7,1 M de foyers éligibles en métropole
    au T4 2021, non-recours de 48 à 52 % des foyers, de 43 à 46 % de la masse.

**Ce que le pont devrait valoir.** Le tableau 1 du n° 1370 donne deux rapports
« droits / versé », selon qu'on garde ou non les bénéficiaires que la méthode juge non
éligibles :

| rapport (RSA, n° 1370, tableau 1) | en masse | en foyers |
|---|---|---|
| éligibles / recourants éligibles | 1,41 à 1,46 | 1,50 à 1,59 |
| éligibles / tous les payés (beta error comprise) | 1,26 à 1,30 | 1,26 à 1,34 |

Le pont du code, 1,30 à 1,41, est à cheval sur les deux lignes ; son milieu 1,355 est
défendable, mais l'incertitude du pont en masse est de 1,26 à 1,46, soit ±8 % sur la ligne.
Pour la prime, 43 à 46 % de non-recours en masse donneraient 1,75 à 1,85 (contre 1,68 à
1,77 dans le code), et 48 à 52 % en foyers un pont des comptes de 1,92 à 2,08 — sous
réserve de lecture du n° 1379.

## 4. La décomposition de l'écart

### 4.1 Le RSA : qui sont les 3,7 M de foyers du modèle

Sur l'échantillon, décembre 2024, catégories exclusives prises dans l'ordre :

| catégorie (échantillon, 20 000 ménages) | foyers | part | €/mois | masse an. |
|---|---|---|---|---|
| a. famille avec un indépendant (revenu nul) | 1 672 k | 45,4 % | 675 | 13,38 Md€ |
| b. adulte hébergé chez un autre (hors a) | 530 k | 14,4 % | 529 | 3,33 Md€ |
| c. aucun revenu, demandeur < 55 ans (hors a, b) | 1 296 k | 35,2 % | 627 | 9,64 Md€ |
| e. avec un salaire | 48 k | 1,3 % | 167 | 0,09 Md€ |
| f. avec une allocation chômage | 87 k | 2,4 % | 166 | 0,16 Md€ |
| g. avec une pension | 51 k | 1,4 % | 177 | 0,10 Md€ |
| **ensemble** | **3 684 k** | | **611** | **26,71 Md€** |

69,6 % des foyers du modèle n'ont **aucune ressource** dans la base du RSA ; 2,6 %
cumulent RSA et prime (Cnaf, T4 2024 : 22,8 %) ; 4,4 % touchent le RSA majoré (Cnaf :
11,6 %). Les 1,67 M de familles d'indépendants sont 47 % des 3,56 M de familles où vit un
indépendant.

**La structure, contre la Cnaf** (part des foyers, T4 2024, RSA Conjoncture n° 45,
tableau 1 ; « modèle » = échantillon, décembre 2024) :

| | Cnaf | modèle | modèle sans les familles d'indépendants | essai 4.2 |
|---|---|---|---|---|
| hommes seuls | 37,0 % | 33,4 % | 35,1 % | 34,5 % |
| femmes seules | 19,3 % | 24,6 % | 29,8 % | 27,8 % |
| seuls avec enfant(s) | 32,6 % | 18,9 % | 23,2 % | 21,5 % |
| couples sans enfant | 2,3 % | 6,8 % | 3,8 % | 4,3 % |
| couples avec enfant(s) | 8,8 % | 16,3 % | 8,1 % | 12,0 % |
| moins de 25 ans | 4,0 % | 1,5 % | 2,5 % | 1,9 % |
| 45-54 ans | 19,9 % | 34,0 % | 41,4 % | 38,1 % |
| 55 ans ou plus | 18,0 % | 13,6 % | 3,2 % | 8,9 % |
| DOM | 10,5 % | 8,1 % | | |
| montant moyen | 557 € | 611 € | 559 € | 526 € |
| foyers | 1 826 k | 3 684 k | 2 013 k | 2 666 k |

Sans les familles d'indépendants, la structure et le montant moyen ressemblent à ceux de la
Cnaf (559 € contre 557 €). Ce sont les indépendants qui portent l'excès de couples et le
montant trop haut (675 €, souvent des couples sans aucune ressource). Le statut
d'occupation : 49,5 % des foyers du modèle sont propriétaires ou accédants (37,5 % hors
indépendants) ; la part publiée chez les allocataires n'a pas été trouvée.

### 4.2 La cause mesurée : le revenu nul des indépendants

**Essai** (`run_indep.py`, même échantillon, une seule passe) : un revenu d'activité
non salariée tiré pour chaque indépendant, écrit sur `rpns_autres_revenus` de 2022 à 2024
(qu'OpenFisca lit, annualisé, dans les ressources du RSA et de la prime, `rsa.py:1061`,
`ppa.py:202`). Les paramètres viennent de l'Insee Première n° 2114 (juin 2026, figure 1 et
texte, p. 1-2,
https://www.insee.fr/fr/statistiques/fichier/version-html/9013403/IP2114.pdf) : 52 % de
micro-entrepreneurs, revenu moyen 680 €/mois, médian 330 € ; 48 % de non-salariés
« classiques », revenu moyen 4 150 €, 9,6 % de revenus nuls ou déficitaires. **La forme
est une hypothèse** (lognormales ; σ = 1,20 pour les micro-entrepreneurs, déduit de la
moyenne et de la médiane ; σ = 1,0 supposé pour les autres). Revenu moyen tiré : 2 363 €
par mois (Insee, ensemble y compris micro-entrepreneurs : 2 350 €).

| essai (échantillon) | foyers | €/mois | masse an. | grille 2024 |
|---|---|---|---|---|
| RSA, modèle actuel | 3 684 k | 611 | 26,71 Md€ | pont : +67 % ; foyers : +102 % |
| RSA, revenu des indép. | 2 666 k | 526 | 16,60 Md€ | pont : +3,9 % ; foyers : +46 % |
| prime, modèle actuel | 4 961 k | 230 | 12,79 Md€ | pont : −28 % ; foyers : +7 % |
| prime, revenu des indép. | 5 583 k | 214 | 13,49 Md€ | pont : −24 % ; foyers : +21 % |

**Sur la ligne du montant du RSA en 2024, l'écart de l'échantillon est de +67 points ; le
revenu des indépendants en explique 63, et il reste +3,9 %, dans la tolérance de ±14 % et
dans l'incertitude du pont (de −3 % à +12 % selon qu'on le prend à 1,26 ou 1,46).** Il
reste 653 k foyers d'indépendants au RSA, des micro-entrepreneurs pour l'essentiel : ce
n'est pas un défaut, ce sont des droits plausibles.

### 4.3 Le compte des foyers du RSA : le non-recours est dans l'écart

La ligne des foyers compare des **ayants droit** à des **payés**, sans pont. Le pont des
comptes du n° 1370 (1,26 à 1,59) dit qu'un modèle juste devrait trouver **2,30 à 2,90 M**
d'éligibles pour 1,826 M de payés : un écart de +26 à +59 % est attendu, pas une erreur.
Décomposition du compte de 2024, en millions de foyers :

| marche | foyers |
|---|---|
| payés par les Caf (T4 2024) | 1,83 |
| + non-recours (pont des comptes 1,26 à 1,59) | +0,47 à +1,07 |
| = éligibles attendus | 2,30 à 2,90 |
| écart de structure restant (essai : 2,67 − éligibles attendus) | −0,23 à +0,37 |
| + indépendants à revenu nul (3,68 − 2,67, mesuré) | +1,02 |
| = modèle (échantillon) | 3,68 |

La somme des causes mesurées refait l'écart total : +1,85 M = non-recours (+0,47 à +1,07)
+ structure (−0,23 à +0,37) + indépendants (+1,02).

### 4.4 Ce qui reste, et pousse dans les deux sens (hypothèses, non mesurées)

Dans les 2,67 M de l'essai, des erreurs de signes opposés se compensent :

* **Vers le haut.** L'AAH, l'ASS, l'ASI, les pensions d'invalidité et alimentaires sont
  nulles : leurs bénéficiaires paraissent sans ressource (groupe c, 1,30 M, dont 623 k de
  45-54 ans ; Cnaf : 19,9 % des foyers ont 45-54 ans, le modèle 38 à 41 %). L'AAH compte
  1,40 M d'allocataires fin 2024 (communiqué de la Drees du 4 décembre 2025, vu par un
  moteur de recherche, page non joignable ; à vérifier) et son montant dépasse le socle du
  RSA d'une personne seule. Les revenus de l'épargne (`rsa_base_ressources_patrimoine`)
  sont nuls. Les 530 k adultes hébergés (25-54 ans, inactifs) sont des ayants droit en
  droit, que la Drees trouve peu recourants (n° 1370 : non-recourants plus proches de
  l'emploi, plus souvent propriétaires) — le pont moyen ne le sait pas.
* **Vers le bas.** Tout inactif de 55 ans ou plus a une pension (`incomes.py:79`) : le
  modèle a 3 à 9 % de foyers de 55 ans ou plus, la Cnaf 18 %. Tout chômeur est indemnisé :
  2,4 % des foyers du modèle ont une allocation chômage ; la part publiée des chômeurs non
  indemnisés n'a pas été relevée ici. Personne ne travaille une partie de l'année : 1,3 %
  des foyers du modèle ont un salaire, alors que 22,8 % des foyers de la Cnaf cumulent RSA
  et prime. Les parents isolés manquent (21,5 % contre 32,6 %), le RSA majoré aussi (4,4 %
  contre 11,6 %).

### 4.5 La prime d'activité : assez de foyers payés, moitié trop peu d'ayants droit

La grille juge le montant avec le pont et le compte sans : les deux lignes disent pourtant
la même chose. En 2024 (passe entière) :

| | modèle (droits) | Cnaf (versé) | rapport | pont attendu (n° 1379, non lu) |
|---|---|---|---|---|
| masse | 12,97 Md€ | 10,28 Md€ | 1,26 | 1,75 à 1,85 (code : 1,725) |
| foyers | 5,05 M | 4,63 M | 1,09 | 1,92 à 2,08 |
| €/mois par foyer | 230 (échant.) | 200 | 1,15 | |

Avec un non-recours de moitié des foyers, il faudrait **8,9 à 9,6 M d'ayants droit** pour
4,63 M de payés : le modèle en a **45 à 48 % de moins**. Et son montant moyen (230 €) est
au-dessus de celui des payés (200 €), alors que les non-recourants touchent en moyenne
moins (c'est pourquoi le pont en masse est plus petit que le pont en foyers) : l'ayant droit
moyen devrait toucher autour de 200 × 1,725 / 2,0 ≈ 173 € ; le modèle le paie un tiers de
plus. −45 % de foyers fois +33 % de montant font le −27 % de la ligne (0,55 × 1,33 ≈
0,73).

Ce que l'échantillon montre (décembre 2024) : 4 % seulement des foyers du modèle ont des
revenus d'activité sous un demi-Smic net (1 398,70 €, hypothèse de conversion), 9,1 %
touchent moins de 50 € ; hommes seuls 20,7 % (Cnaf 28,1 %), parents isolés 15,5 % (21,0 %),
couples sans enfant 10,0 % (5,6 %), couples avec enfants 24,7 % (17,2 %), 55 ans ou plus
18,5 % (11,3 %). D-316 avait trouvé la même structure (trop de couples et d'âgés, trop peu
d'hommes seuls et de parents isolés, montants trop hauts, presque pas de cumul avec le
RSA).

**Causes, par ordre de poids supposé :**

* **Les petits salaires et les années incomplètes** (hypothèse, non mesurée) : le salaire
  est un équivalent temps plein fois la quotité, douze mois sur douze. Les contrats courts,
  les mois partiels, les intérimaires, qui font l'essentiel des ayants droit de la prime
  et de son non-recours (n° 1379 : éligibilité « ponctuelle ou récente »), n'existent pas.
  Le salaire médian des allocataires est trop haut, la bonification trop fréquente.
* **Les indépendants** (mesuré, 4.2) : +0,62 M de foyers, +0,70 Md€ ; le montant moyen
  baisse de 230 à 214 €. La ligne du montant passe de −28 à −24 % (échantillon).
* **Le pont lui-même** : à 1,80 au lieu de 1,725, la ligne perd encore 4 points.

## 5. Ce que l'écart fait aux études

**Le coût d'une réforme ne prend pas le pont.** Les études chiffrent la différence de deux
passes de droits à recours complet (`runner.run`, aucune lecture de `TAKE_UP_BRIDGE`). Le
chiffrage officiel d'une mesure sur une prestation quérable porte sur des sommes versées.
Pour une réforme qui déplace la prestation à peu près en proportion de sa masse
(revalorisation, hausse de salaire net), l'écart de niveau **se reporte entier** sur le coût
: le coût du modèle est au coût officiel ce que la masse de droits est à la masse versée.
Il ne s'annule que pour une réforme qui ne touche pas la prestation.

* **PLF 2027, art. 74, volet prime** (`docs/etudes/plfss2027.md`, la seule étude notée
  contre un chiffrage officiel qui touche ces prestations) : préenregistré −887 M€ sur 7,05
  mois effectifs à 2,1 %, publié −332 M€ sur 4 mois à 2,3 %. Ramenés à un mois et à un
  point de revalorisation : 887 / 7,05 / 2,1 = 59,9 M€ ; 332 / 4 / 2,3 = 36,1 M€. Rapport
  **1,66** (D-316 le trouvait aussi) : c'est, presque exactement, le pont de 1,725. **Le
  dépassement de l'art. 74 est le non-recours**, pas une erreur de barème. Le revenu des
  indépendants le grossirait de quelques points (+5,5 % de masse dans l'essai).
* **Effets induits sur la prime dans les programmes** (`reports/etudes/*/premiere_annee_
  *.json`, `deltas/ppa`, droit 2026) : Attal −2,37 Md€ (sur un coût de 59,53), Lisnard
  −0,92 (sur 35,43), Retailleau −0,44 (sur 16,08). Ce sont des économies à recours complet.
  Si elles se réduisent dans la proportion du pont (hypothèse), elles valent 1,0 à 1,1 Md€,
  0,4 et 0,2 de moins : le coût d'Attal monterait d'environ 1,0 Md€ (+1,7 %), celui de
  Lisnard de 0,4 (+1,1 %), celui de Retailleau de 0,2 (+1,2 %). Aucun verdict de dette ne
  paraît dépendre de cet ordre de grandeur (non recalculé). Les deltas du RSA y sont
  petits (−63, −25 et −14 M€).
* **Une réforme du RSA** (aucune n'est chiffrée par une étude ; les mesures RIA de
  Retailleau et « charges négatives » de Lisnard sont refusées) : la variante interne
  `reports/fiche_rsa_700.md` (socle à 700 €, +3,78 Md€) porte les deux erreurs ensemble :
  1,67 M de familles d'indépendants sans ressource, qui touchent la hausse entière, et le
  recours complet. Hypothèse proportionnelle : environ 3,78 × 16,6 / 26,7 / 1,355 ≈ 1,7
  Md€, soit moins de la moitié.
* **Les déciles** : les 1,67 M de familles d'indépendants sont placées au bas de la
  distribution avec un RSA qu'elles n'ont pas ; toute mesure lue par décile (le premier
  dixième) en est déformée. Non mesuré ici.

## 6. Le correctif proposé

Trois changements, dans cet ordre ; aucun ne touche `calibrate.py`.

**C1. Un revenu pour les indépendants** (`population/incomes.py`, nouveau bloc ; câblage
sur `rpns_autres_revenus` ou, pour les micro-entrepreneurs, `rpns_micro_entreprise_*`, sur
N-2 à N dans `to_openfisca.py`).
* Données : Insee Première n° 2114 (figure 1 : effectifs, revenus moyens et part des
  revenus nuls par statut et secteur ; quartiles et déciles des micro-entrepreneurs dans
  le texte), à télécharger (URL en 4.2) et à manifester ; les déciles par secteur sont dans
  « Emploi et revenus des indépendants », Insee Références 2025
  (https://www.insee.fr/fr/statistiques/8376583, non ouvert ici). La PCS de l'enquête
  Emploi (`pcs`) donne le secteur ; la distinction micro / classique ne s'y lit pas et
  se tire (52 / 48 %).
* Coût : une journée, un test qui tient la masse et la part des revenus nuls.
* Risque : **ce revenu entre dans l'impôt sur le revenu, la CSG et le RFR** (environ 110
  Md€ par an, 3,9 M × 2 350 € × 12) : les lignes de l'impôt, des foyers imposés et des
  tranches bougent toutes. Il faut le préenregistrer comme un changement de population,
  pas comme un correctif du RSA. Variante prudente : ne l'écrire d'abord que dans les
  ressources des prestations, et le dire.
* Pronostic (2024) : RSA, montant (pont) **de −5 à +15 %** (essai : +3,9 %) ; foyers du
  RSA, sans pont, de +35 à +60 % (essai : +46 %). Prime, montant (pont) de −28 à −20 %
  (essai : −24 %) ; foyers, de +10 à +25 % (essai : +21 %).

**C2. Le non-recours dans le calcul**, pour les études comme pour la grille. Un poids de
recours par famille, fonction du montant de droit (le n° 1370, graphique 1, donne la
distribution des montants des recourants et des non-recourants ; le n° 1379 de même pour
la prime), appliqué **en espérance** (le droit fois la probabilité, pas un tirage, pour ne
pas ajouter de bruit à une différence de deux passes), calé pour refaire les deux taux
publiés (foyers et masse). Le coût d'une réforme devient Σ p(montant) × Δdroit. La grille
compare alors des recourants à des payés, en foyers comme en masse, et le pont fixe de
`verification.py:34` disparaît.
* Données : les fichiers de données des n° 1370 et 1379 (au manifeste, en quarantaine,
  sans URL ; le PDF du n° 1370 est retrouvé, voir § 3 ; le site de la Drees refuse le
  conteneur, à télécharger depuis un autre poste).
* Coût : deux jours. Risque : le recours dépend aussi de l'ancienneté et du statut
  d'occupation, qu'un poids par montant ne voit pas ; et une réforme qui crée des ayants
  droit nouveaux (une hausse du socle) les verrait recourir comme les anciens au même
  montant, ce qui est une hypothèse à dire.
* Pronostic (2024, avec C1) : RSA, montant de −10 à +15 % ; foyers (recourants contre
  payés) **de −15 à +20 %** ; prime, montant de −28 à −18 % ; foyers de la prime, **de −45
  à −35 %** : la ligne aujourd'hui « tenue » sortira de sa tolérance, et c'est la vérité
  qu'elle cache. L'art. 74 passerait d'un rapport 1,66 au chiffrage officiel à 0,95-1,05
  par mois et par point.

**C3. Des ressources mieux construites** (le travail long, à décider après C1 et C2) :
* des mois incomplets pour les salariés (contrats courts, entrées et sorties d'emploi),
  qui donneraient à la prime ses petits ayants droit et au RSA ses cumulants (Cnaf :
  22,8 %) — la donnée manque : la distribution des revenus d'activité mensuels des
  allocataires n'est publiée dans aucune source lue (D-316) ; le DRM de la Drees la porte
  mais n'est pas ouvert ;
* l'AAH (taux d'incapacité tiré pour les inactifs de 20 à 59 ans, calé sur 1,40 M) et les
  pensions d'invalidité, qui ôteraient des ayants droit du groupe c ;
* la part des chômeurs non indemnisés, et la retraite à partir de l'âge réel plutôt que de
  tout inactif de 55 ans, qui en ajouteraient chez les chômeurs et les 55-64 ans.
* Pronostic : prime, montant de −15 à +5 %, foyers (recourants) de −20 à +10 % ; RSA
  inchangé à ±5 points près, les deux sens se compensant. Hypothèse : les ordres de
  grandeur de C3 ne sont pas mesurés.

## 7. Comment l'expliquer au public

Le simulateur calcule ce à quoi chaque ménage **a droit** ; la Caf compte ce qu'elle
**verse**, et un tiers des ayants droit au RSA, la moitié de ceux de la prime d'activité,
ne la demandent pas (Drees). Comparer les deux sans correction mélange une erreur du
modèle et un fait de société. Une fois le non-recours retiré, il restait au RSA un excès
d'une moitié : il venait des 3,9 millions d'indépendants, à qui la population ne donnait
aucun revenu, et que le modèle croyait donc sans ressources. En leur donnant les revenus
que l'Insee publie, le RSA du modèle retombe à 4 % du total versé. La prime d'activité a
l'erreur inverse : le modèle ne voit pas assez de petits salaires et de mois partiels, et
a deux fois trop peu d'ayants droit, chacun trop bien payé.

**Le graphique qui le prouverait** : une barre par source, en millions de foyers au RSA à
la fin de 2024 — payés par les Caf (1,83) ; éligibles selon la Drees (2,3 à 2,9, la
fourchette dessinée) ; modèle actuel (3,68), coupé en « familles sans indépendant »
(2,01) et « familles d'indépendants sans revenu » (1,67) ; modèle avec les revenus des
indépendants (2,67). La même figure en milliards d'euros, et la même pour la prime, où la
barre du modèle tombe sous la fourchette des éligibles. À côté, le tableau de la
configuration familiale du § 4.1, colonne Cnaf contre colonne modèle.

**Ce qu'un lecteur pourrait faire varier lui-même** : le taux de non-recours (de 0 % à
la fourchette de la Drees, en foyers et en masse), le revenu des indépendants (nul, ou
tiré de l'Insee, avec la part des micro-entrepreneurs), et voir bouger les deux barres et
le coût d'une revalorisation de la prime — l'art. 74 passant de 1,66 fois le chiffrage
officiel à son niveau.
