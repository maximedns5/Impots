# Étape 4 du but 19 : le non-recours dans le calcul, en espérance

Le 10 novembre 2026, branche `claude/but19-e4`. Consigne : `CONSIGNE_ETAPES.md` (N = 4).
Diagnostics : `rsa_ppa.md` (correctif C2), `famille_logement_niveau_de_vie.md`,
`demarche.md` (§ 2.2), `SYNTHESE.md` (§ 1 E). Aucune passe sur la population entière,
aucune grille, aucune étude : toutes les mesures ci-dessous sont sur un échantillon de
15 000 ménages (`runner.subsample`, graine `SAMPLE_SEED` = 20240101), **et elles ne sont
pas aveugles** : le calage et les pronostics viennent du même échantillon. Les scripts
d'essai sont dans `/tmp/but19-e4/scripts/` (`calage.py`, `mesure.py`, `fit_bins.py`).

## 1. Ce qui a changé, fichier par fichier

**`src/impots/population/recours.py`** (neuf). La loi de recours, ses sources et son calage.

* La forme : `p(x) = p_max × (1 − exp(−x / τ))`, où `x` est le droit **mensuel par unité
  de consommation** (l'échelle du RSA, n° 1370, note 2 : 1 ; +0,5 ; +0,3 ; +0,3 en couple
  ou +0,4 pour un parent isolé ; +0,4), ramené en euros de la fin de 2021 par le montant
  de base de la prestation dans la **loi de référence** du mois (565,34 € pour le RSA et
  553,71 € pour la prime en novembre 2021 ; 635,71 € et 622,63 € d'avril 2024). Le
  déflateur ne lit jamais la réforme : une réforme du forfait ne déplace pas le recours de
  tous par le dénominateur. `p(0) = 0`, `p` croît et sature. **La forme exponentielle est
  une hypothèse** ; elle a été retenue parce qu'elle est monotone, lisse (une réforme ne
  fait pas sauter une famille d'une marche) et nulle en zéro.
* `τ`, ajusté sur les recours par tranche publiés :
  * RSA, **τ = 79 €** : moindres carrés pondérés par les éligibles, sur les six tranches
    du graphique 1 du n° 1370 (fourchette haute, 944 k recourants, 561 k non-recourants).
    Recours par tranche de 100 € par UC : 0,40 ; 0,47 ; 0,70 ; 0,79 ; 0,75 ; 0,33. La
    dernière tranche (500 à 600 €) contredit la croissance ; la Drees la dit peut-être
    conjoncturelle (l'après-Covid) ; elle est gardée. Sans elle, τ = 103 €.
  * Prime, **τ = 21 €** : le n° 1379 **n'a pas été lu** ; la presse en rapporte la
    répartition des 3,4 M de non-recourants (32 % sous 50 € par mois et par UC, 29 % de
    50 à 100, 17 % de 100 à 150, 12 % de 150 à 200, 10 % au-delà) et la part des 3,2 M
    de recourants sous 50 € (20 %). D'où un recours de 0,37 sous 50 € et de 0,525
    au-delà, un rapport de 0,705 que τ = 21 € refait aux milieux des tranches (au-delà de
    50 €, pondérés par la répartition des non-recourants : hypothèse).
* `p_max`, **calé** (`p_max_cale`, solution exacte) pour que le modèle refasse le milieu
  de la fourchette publiée du non-recours **en foyers**, parmi les familles ayant droit en
  décembre 2024 : RSA 35 % (33 à 37 %), **p_max = 0,6740** ; prime 50 % (48 à 52 %),
  **p_max = 0,5253**. Le taux **en masse** n'entre pas dans le calage, il en est le
  contrôle (§ 2). Le calage en foyers est retenu parce qu'une revalorisation du forfait,
  la réforme la plus fréquente, donne le même euro par UC à chaque famille : son coût
  suit le nombre de recourants plus que la masse.
* `caler(population)` refait ce calage. **La jonction des étapes 2 et 3 doit le relancer**
  : `p_max` dépend de la répartition des droits du modèle, que le revenu des indépendants
  et le découpage des foyers changent. Le nouveau `p_max` se préenregistre avec la grille.
* `colonnes(built)` calcule, par famille et mois par mois, le droit et le servi du RSA et
  de la prime ; la CRDS de la prime (`crds_mini`) suit la prime ; la prime de Noël
  (`aefa`) suit le recours au RSA de décembre (de novembre si décembre est nul), parce
  qu'elle n'est versée qu'aux allocataires.

**`src/impots/population/runner.py`**. Au palier complet, `_extract` sert en espérance
(`_serve_in_expectation`) : `rsa`, `ppa`, `crds_mini`, `aefa` deviennent ce qui est versé
en espérance, et `revenu_disponible` perd exactement ce qui n'est pas réclamé. Les droits
restent sous `rsa_droit`, `ppa_droit`, `crds_mini_droit`, `aefa_droit`,
`revenu_disponible_droit` ; les foyers servis en espérance de décembre sous
`n_allocataires_rsa_servi` et `n_allocataires_ppa_servi`. Les comptes
`n_allocataires_*` restent des comptes d'ayants droit. Un garde-fou vérifie que le droit
lu mois par mois refait celui du registre, à l'arrondi du float32 près. Le choix de
servir sous les noms ordinaires (et non dans des colonnes neuves) fait que tout ce qui lit
la passe porte le non-recours sans qu'on l'y câble : le coût (`reform_cost`), les déciles,
l'identité comptable (D-045), les chocs macro (`shocks.py`, « transfert »), l'offre de
travail, la consommation, le chemin annuel et la dette. Le palier léger ne change pas.

**`src/impots/population/aggregate.py`**. Les droits rejoignent `INSTRUMENTS` (donc les
totaux, les deltas et la réponse de l'API, dont `totals` et `deltas` sont des
dictionnaires : aucun champ neuf dans le schéma) ; les deux comptes servis rejoignent
`COUNTS`. Deux champs neufs d'`Aggregates`, que l'API ne lit pas (elle énumère ce
qu'elle prend) : `reform_cost_droit`, le coût à recours complet, et
`niveau_de_vie_quantiles_droit`. Les déciles se forment sur le revenu disponible servi.

**`src/impots/verification.py`, `src/impots/population/reconcile.py`**. Les lignes
existantes lisent le **droit** et le pont, comme préenregistré (D-363) : diviser le
servi par le pont compterait le non-recours deux fois. `TAKE_UP_BRIDGE` n'est pas
touché. La passe de la grille mesure à côté, sous des noms qu'aucune ligne de
`lignes.json` ne lit : `rsa servi en espérance`, `ppa servie en espérance`,
`n_allocataires_rsa_servi`, `n_allocataires_ppa_servi`, `niveau de vie médian servi,
pondéré personne`, `D9/D1 servi, pondéré personne`. Les niveaux de vie de la grille et
de la réconciliation restent à recours complet.

**`src/impots/population/cli.py`**. La limite « Benefits assume 100 % take-up »,
devenue fausse, dit maintenant ce que fait la passe.

**Ce qui ne change pas.** Le calcul d'**un ménage** (`engine`, l'API ménage) donne son
droit : c'est ce qu'il toucherait s'il le demandait. `outputs.REGISTRY` n'est pas touché.
Les aides au logement gardent un recours de 1 (§ 5).

**Comment l'espérance traite une réforme qui change le droit.** Le coût est la
différence de deux espérances, Σ p(d′) d′ − Σ p(d) d. Il compte les recourants qui
touchent plus (p(d) Δd) et les familles que le droit plus grand amène à recourir
(Δp × d′). Une famille nouvellement éligible recourt comme une ancienne au même montant :
une hypothèse (le n° 1370 dit les non-recourants plus récemment éligibles, plus
proches de l'emploi, plus souvent propriétaires), qui surestime sans doute le recours
des nouveaux éligibles. Aucun tirage : la différence de deux passes n'a pas de bruit.

## 2. Les mesures, avant et après

**Totaux de 2024 contre les totaux publiés** (15 000 ménages, droit 2024, palier complet,
sans imputation, comme la passe de la grille ; Cnaf, rapport du directeur comptable, État
et départements ; foyers : RSA Conjoncture n° 45 et PA Conjoncture n° 32, T4 2024) :

| mesure | publié | avant (pont) | après (servi) |
|---|---|---|---|
| RSA, Md€ | 11,79 | 19,00 (+61,1 %) | 17,16 (+45,5 %) |
| prime d'activité, Md€ | 10,28 | 7,71 (−25,0 %) | 6,92 (−32,7 %) |
| aides au logement, Md€ | 15,67 | 11,93 (−23,9 %) | inchangé |
| foyers au RSA (décembre), M | 1,826 | 3,558 (+94,9 %) | 2,313 (+26,7 %) |
| foyers à la prime (décembre), M | 4,628 | 5,105 (+10,3 %) | 2,553 (−44,8 %) |
| niveau de vie médian, € | 26 740 | 24 406 (−8,7 %) | 24 268 (−9,2 %) |
| D9/D1 | 3,48 | 3,54 (+1,7 %) | 3,73 (+7,3 %) |

« Avant » : le droit divisé par le pont (1,355 et 1,725) pour les montants, le droit seul
pour les foyers et le niveau de vie. Droits de l'échantillon : RSA 25,74 Md€, prime
13,31 Md€. Servi sur droit : 66,7 % pour le RSA, 52,0 % pour la prime.

**Ce que disent ces nombres.**

* **Le contrôle en masse manque de peu.** Le recours en masse du modèle est de 66,7 %
  (RSA) et 52,0 % (prime), sous les fourchettes publiées (68 à 71 % et 54 à 57 %). Les
  droits du modèle sont presque tous au plafond (79 % des familles au RSA entre 400 et
  500 € par UC ; 14 % des familles à la prime sous 50 €, quand la presse en dit 26 %
  parmi les éligibles de la Drees) : la pente du recours y mord peu, et le calage en
  foyers donne une masse un peu basse. Calé sur la masse, `p_max` monterait de 4 % (RSA)
  et de 7 % (prime).
* **Le RSA servi reste haut** (+45,5 %) : ce n'est plus le non-recours, ce sont les
  1,67 M de familles d'indépendants sans revenu (cause A, étape 2). L'essai du
  diagnostic (revenu des indépendants : 16,60 Md€ de droits sur 26,71) donnerait un RSA
  servi d'environ 11,1 Md€, −6 %.
* **Le pont et le servi ne disent pas la même chose.** Le pont de 1,355 rapporte les
  éligibles à **tous** les payés, y compris les 16 % de bénéficiaires que la méthode de
  la Drees juge non éligibles (« beta error », n° 1370, tableau 1) ; le servi les laisse
  dehors, parce qu'il ne sert que les recourants éligibles. Si ces bénéficiaires sont des
  éligibles mal classés, le recours vrai est plus haut, d'un facteur allant jusqu'à
  1 / 0,84 pour le RSA (en foyers) ; le n° 1379 donne 470 000 foyers de ce type pour la
  prime (presse). C'est la plus grosse incertitude du servi, à dire sur chaque ligne.
* **La prime servie descend** (−32,7 % en masse, −44,8 % en foyers) : la ligne des foyers,
  aujourd'hui tenue, sort de sa tolérance, comme le diagnostic l'annonçait (C2 : de −45
  à −35 %). C'est l'erreur qu'elle cachait : le modèle a deux fois trop peu d'ayants droit
  à la prime, chacun trop bien payé (petits salaires et années incomplètes absents).
* **Le niveau de vie** : le servi abaisse surtout le premier dixième (D1 −5,3 %), le
  D9/D1 monte de 3,54 à 3,73. L'ERFS observe des versements : le servi est le bon
  concept, et il éloigne la ligne de son total.

**Le coût d'une réforme, avant et après** (15 000 ménages, mêmes passes) :

| réforme | droit | coût à recours complet | coût servi | rapport |
|---|---|---|---|---|
| prime, forfait +2,1 % en avril (art. 74) | 2024 | 752,3 M€ | 393,6 M€ | 0,523 |
| Attal A16 (droit au brut) : Δ prime | 2026 | −2 408 M€ | −1 261 M€ | 0,524 |
| même réforme : coût total | 2026 | 57 549 M€ | 58 715 M€ | +2,0 % |
| RSA à 700 € (`rsa_700`, fiche interne) | 2024 | 3 652 M€ | 2 479 M€ | 0,679 |

La population de l'essai de 2026 n'est pas vieillie (indicatif : seul le rapport sert).
Le rapport marginal de la prime (0,52) est presque son recours moyen : la hausse du
forfait donne autant à chaque UC, et les familles amenées à recourir compensent les
petits droits moins réclamés. Celui du RSA à 700 € (0,68) dépasse son recours en foyers
(0,65) : la hausse porte surtout sur des droits au plafond, et amène des recourants.
L'identité comptable tient sur le servi (écart de −267 € sur 394 M€).

**Les déciles de l'art. 74 (miroir, 2024)** : le gain moyen du 3e dixième passe de 63,6 €
à 32,2 € par ménage et par an, celui du 1er de 8,7 à 5,5 € ; tous les dixièmes sont à
peu près divisés par deux.

## 3. Le préenregistrement proposé

**Les lignes neuves de la grille** (à côté des lignes existantes, qui gardent le pont ;
`lignes.json` non touché) :

| id proposé | `modele` | publié (2022 / 2023 / 2024) | tolérance |
|---|---|---|---|
| `rsa_montant_servi` | `rsa servi en espérance` | 11,40 / 11,60 / 11,79 Md€ | ±14 % |
| `ppa_montant_servi` | `ppa servie en espérance` | 9,66 / 10,17 / 10,28 Md€ | ±13 % |
| `rsa_foyers_servis` | `n_allocataires_rsa_servi` | refusée / 1,822 / 1,826 M | ±25 % |
| `ppa_foyers_servis` | `n_allocataires_ppa_servi` | 4,620 / 4,555 / 4,628 M | ±25 % |
| `ndv_median_servi` | `niveau de vie médian servi, […]` | 24 330/25 760/26 740 € | ±15 % |
| `d9_d1_servi` | `D9/D1 servi, pondéré personne` | 3,38 / 3,49 / 3,48 | ±15 % |

Les totaux publiés sont **ceux des lignes existantes** (mêmes sources, mêmes sha256 dans
`lignes.json`) : Cnaf, rapport du directeur comptable et financier, § 4.1.3, droits
constatés, État et départements ; Cnaf-DSER, RSA Conjoncture n° 41 et 45, PA Conjoncture
n° 28 et 32, tableau 1, moyenne du T4 ; Insee Première n° 2004, 2063 et 2117. Les
tolérances sont celles des lignes existantes, pour la même raison : le champ Caf (sans
la MSA), la France entière contre la métropole de la Drees. La raison des lignes : elles
comparent enfin des payés à des payés, en foyers comme en masse, sans pont. Le `modele`
complet de `ndv_median_servi` est `niveau de vie médian servi, pondéré personne`.

**Une marge de calage neuve** (la loi de recours, pas `calibrate.py`) : `p_max` du RSA et
de la prime, recalés par `recours.caler` sur la population de la jonction, cibles 65 %
et 50 % de recours en foyers (milieux des fourchettes du n° 1370, tableau 1, et du
n° 1379, communiqué de la Drees) ; `τ` fixés à 79 et 21 €. À préenregistrer avec leurs
valeurs avant la grille.

**Le pronostic**, pour la population de cette branche seule (sans les étapes 2 et 3),
tiré de l'échantillon et de la grille de D-364 (non aveugle) :

| ligne | 2022 | 2023 | 2024 |
|---|---|---|---|
| `rsa_montant_servi` | +37 à +49 % | +40 à +52 % | +43 à +55 % |
| `ppa_montant_servi` | −40 à −31 % | −41 à −33 % | −39 à −30 % |
| `rsa_foyers_servis` | refusée | +22 à +35 % | +22 à +35 % |
| `ppa_foyers_servis` | −48 à −40 % | −50 à −43 % | −49 à −42 % |
| `niveau_de_vie_median_servi` | −9 à −5 % | −10 à −7 % | −11 à −8 % |
| `d9_d1_servi` | +9 à +17 % | +8 à +15 % | +5 à +13 % |

Les lignes existantes : **inchangées à l'euro**, puisqu'elles lisent le droit (le code
de leur mesure ne change que de nom de colonne).

**Avec l'étape 2 jointe** (revenu des indépendants, essai du diagnostic) et `p_max`
recalé : `rsa_montant_servi` de −15 à +5 % ; `rsa_foyers_servis` de −5 à +20 % ;
`ppa_montant_servi` de −32 à −22 % ; `ppa_foyers_servis` de −45 à −35 %. Hypothèse :
non mesuré ensemble ici.

## 4. Ce que l'étape fait aux études

Aucune étude n'est relancée. Les effets ci-dessous appliquent le rapport marginal mesuré
(0,52 pour la prime, environ 0,43 à 0,68 pour le RSA) aux deltas des rapports
(`reports/etudes/*/premiere_annee_*.json`), sauf Attal A16, mesuré.

| étude | Δ prime à recours complet | Δ prime servi | effet sur le coût |
|---|---|---|---|
| PLFSS art. 74, prime | +874 M€ (coût 870 M€) | ≈ +457 M€ | coût ≈ 455 M€ (−48 %) |
| PLFSS art. 74, APL | −3,3 M€ | ≈ −1,7 M€ | +2 M€ sur 78 M€ |
| Attal | −2 367 M€ ; RSA −63 | ≈ −1 240 ; RSA ≈ −27 | ≈ +1,2 Md€ sur 57,0 (+2,0 %) |
| Lisnard | −916 M€ ; RSA −25 | ≈ −480 ; RSA ≈ −11 | ≈ +0,45 Md€ sur 28,9 (+1,6 %) |
| Retailleau | −441 M€ ; RSA −14 | ≈ −231 ; RSA ≈ −6 | ≈ +0,22 Md€ sur 9,5 (+2,3 %) |
| Le Pen, Labib, Mélenchon, Roussel, Tondelier | 0 | 0 | aucun |

* **L'art. 74, volet prime.** Le préenregistré de −887 M€ deviendrait environ −464 M€,
  contre −332 M€ publiés. Par mois et par point de forfait, le rapport au chiffrage
  officiel passe de **1,66 à environ 0,87** (le diagnostic attendait 0,95 à 1,05 ; le
  servi en masse, un peu bas, § 2, en explique une partie). L'écart en euros (environ
  +130 M€) reste hors de la tolérance de 100 M€ : il tient au nombre de mois (7,05 contre
  4), que l'étape ne touche pas.
* **Le volet logement** ne bouge pas : recours 1.
* **Les programmes** : les baisses de prime induites par la hausse du salaire net sont
  divisées par deux, et leur coût monte de 1,6 à 2,3 %. Aucun verdict de dette ne devrait
  en dépendre (non recalculé). Les déciles du bas perdent moins.
* **La fiche RSA à 700 €** (hors des dix études) : 3,65 Md€ → 2,48 Md€ (échantillon).

## 5. Ce qui reste, les doutes, les sources non lues

* **Le n° 1379 (prime) n'a pas été lu.** Le site de la Drees refuse le conteneur (réponse
  vide, puis 503 par un second outil) ; l'archive de l'Internet Archive (instantané du
  14 août 2026) existe mais la connexion est coupée par le mandataire. Lu à sa place :
  le communiqué de la Drees par la presse (toutsurmesfinances, Le Média social, ADCF,
  moneyvox). Les taux en foyers (48 à 52 %) et en masse (43 à 46 %) y sont concordants ;
  la répartition des recourants par tranche n'est connue que sous 50 € (20 %), par une
  seule source de presse (Le Média social). **À vérifier sur le PDF** avant le
  préenregistrement, avec ses données (`drees_ER1379_…_donnees.xlsx`, au manifeste en
  quarantaine, absent du disque).
* **Le n° 1370 (RSA)** a été lu sur la copie du Média social que le diagnostic avait
  trouvée (`/tmp/diag_rsa_ppa/dl/er1370.pdf`, sha256 dd2f52db…, celui de l'entrée en
  quarantaine du manifeste). Proposé : renseigner l'URL de cette entrée. Aucun fichier
  neuf n'a été écrit dans `data/raw`.
* **Les aides au logement : taux non trouvé.** Ni la Drees ni la Cnaf ne publient de
  taux national relevé ici ; le rapport du Sénat n° 836 (2023) le dit plus faible que
  celui du RSA, sans nombre ; l'étude Cnaf de 2000 (Le Havre) est locale. Recours gardé
  à 1.
* **Le recours de 2021 appliqué à 2022-2026** : une hypothèse ; la Cnaf préremplit la
  déclaration de la prime depuis 2025, ce qui a pu relever le recours.
* **La « beta error »** (§ 2) : le servi ne sert que les recourants éligibles ; le pont,
  tous les payés. Une variante calée sur les payés relèverait `p_max` de 10 à 16 %.
* **La forme** : exponentielle, hypothèse. La dernière tranche du RSA (500 à 600 €) la
  contredit. τ pèse peu sur le RSA (presque tous les droits du modèle sont au plafond) ;
  il pèse sur la prime, dont la pente vient de deux tranches de presse.
* **Les nouveaux éligibles** recourent comme les anciens au même montant (§ 1).
* **Le recours ne dépend que du montant**, pas de l'ancienneté, du statut d'occupation
  ni du cumul RSA et prime (la Cnaf compte 22,8 % de cumulants, le modèle 2,6 %) : les
  deux recours sont indépendants.
* **Le calage dépend de la population** : à refaire à la jonction (`recours.caler`).
* **Les pages et le site** (`site/plfss2027.html`, « D'où viennent ces nombres ») disent
  encore le recours complet : ils se réécrivent avec la série.
* **`erfs/scorecard.py`** dit encore que le modèle calcule un droit ; il compare des
  effectifs et n'a pas été touché.

## 6. Les tests lancés

* `tests/test_recours.py` (neuf, 6 tests) : la loi (τ, p_max, la forme), le calage exact,
  l'échelle d'UC, le déflateur, le pont gardé, et une passe du fixture (400 logements)
  avec la réforme `rsa_montant_de_base = 700` : servi + non réclamé = droit, colonne par
  colonne et pour le revenu disponible, coût servi entre 0 et le coût à recours complet,
  identité comptable tenue. **Vu échouer sur le code d'avant** (pas de colonne
  `*_droit`) : `1 failed, 5 passed`.
* `tests/test_population.py::test_a_renters_disposable_income_does_not_depend_on_
  evaluation_order` compare désormais le revenu disponible du moteur à
  `revenu_disponible_droit` : c'est le concept qu'il testait, servi sous un autre nom.
* `PYTHONPATH=src .venv/bin/python -m pytest -m "not lourd and not chrono" -n 2` sur
  test_population, test_verification, test_api, test_grille, test_zero_masked,
  test_recours : 195 passés (avant la correction du test d'ordre : 1 échec, celui-là).
* Puis sur test_annees, test_api_predictif, test_apres_annexe, test_autofinancement,
  test_behavioural, test_capital, test_cdhr, test_consommation, test_narrow_band,
  test_niche_imputation, test_offre_travail, test_population, test_prestations,
  test_recours, test_reporting, test_revalorisation_portee, test_top_tail, test_uprating,
  test_predictif_etude, test_ij_moteur : **728 passés, 2 sautés** (9 min 22 s).
* Puis test_bruit_c1, test_cli_predictif, test_dette_comptes, test_fan, test_firmes_vues,
  test_foncier, test_patrimoine, test_predictif_annuel_boucle, test_etude, test_engine :
  **708 passés** (6 min 50 s).
* Non lancés : les lourds (`tests/lourds.txt`) et `make impact`, comme la consigne le
  demande ; `ruff check` des fichiers touchés : propre.
