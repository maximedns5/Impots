# Audit du but 14 : la cohérence, les paramètres, le modèle, le précalcul, le processus

Audit en lecture seule, le 3 novembre 2026, sur `main` au merge du but 13 (`3c91f9b`).
Il est écrit pour le propriétaire et répond à ses six questions dans l'ordre, puis propose
un but 14. Aucune passe n'a tourné, aucun fichier de `src`, `tests` ou `scripts` n'a
changé. Le conteneur n'avait ni données ni venv : tout vient du code, des rapports commités
et de `docs/DECISIONS.md`. Les nombres sont donc ceux des rapports et des D-entrées. Ceux
que l'audit a recalculés, depuis les rapports JSON ou par une réimplémentation de quarante
lignes, le disent.

Six lectures ont été faites en parallèle, une par pan du code. Leurs rapports détaillés,
avec les références `fichier:ligne`, sont dans `docs/audit_but14/` :

| annexe | pan |
|---|---|
| `1_population.md` | sources, squelette, revenus, imputations, calage, vieillissement |
| `2_moteur_boutons.md` | `ReformSpec`, `FirmReformSpec`, corrections, coût, déciles |
| `3_comportements_theta.md` | canaux C1 à C11, bande, θ, boîte, persistance |
| `4_macro_dette.md` | cadre, Mésange, boucle, dette, vues ; `chaine_min.py` la refait |
| `5_etudes_site_precalcul.md` | chaîne des études, site, API, interface, précalcul |
| `6_processus.md` | temps des buts 11 à 13, tests, alignement sur D-335 |

Ce document en est la synthèse. Les affirmations qui décident d'une proposition ont été
revérifiées dans le code : C5 et C6 ne sont appelés nulle part dans `src` ; `etude.py`
refuse plusieurs commits ; le support de C1 se mesure au 95e centile ; le taux implicite
est calculé sur les intérêts nets ; 49 des 88 champs de `ReformSpec` sont absents de
`ui/index.html`.

**Un fait nouveau en cours d'audit.** Le propriétaire a allégé les règles de tests (D-335,
branche `claude/regles-tests`, `07723ea`, pas encore mergée). La question 6 ne demande donc
plus un régime : elle demande ce que le code doit suivre pour s'aligner sur D-335. Les
entrées de ce but commenceront à D-336.

---

## En bref

* **Le socle est solide** : la provenance des données (manifeste, sha256), le droit
  (openfisca, 23 corrections sourcées), la discipline des élasticités (verdict, rang, sens
  de θ) et le préenregistrement, qui donne son sens au premier chiffre de `BUT.md`.
* **L'architecture s'est empilée but par but.** Elle compte cinq couches d'imputation, avec
  deux conventions de poids et trois de rang. Les chemins de passe sont cinq, et leurs
  politiques d'imputation divergent. La couche de service vit dans `api/main.py`, et on
  l'appelle par ses fonctions privées. Le cadre des études est rangé dans la requête d'une
  exploration de la phase 10. Rien de cela ne fausse un nombre publié aujourd'hui, mais
  chaque but neuf le paie.
* **Trois choix de modèle portent les verdicts publiés plus que l'économie ne le fait :**
  - **Le coin du multiplicateur.** On ajoute ±1σ en absolu, et on le tient dix ans. La
    rétroaction dépasse alors le coût, et le multiplicateur devient négatif à θ = 0.
  - **La persistance « éteint ».** Elle crée une falaise à la quatrième année.
  - **C1.** Une élasticité estimée sur l'IR est appliquée au coin marginal total, sur le
    seul salaire. Sa garde de support ne voit pas une réforme qui ne touche que le haut.

  Six verdicts de dette sur huit (D-333) tiennent à ces trois choix.
* **La dette, la boucle et θ ne coûtent rien à recalculer.** Une fois connues les passes
  de chaque année, ce sont des fonctions fermées d'une vingtaine de nombres par année et par
  vue (moins d'une milliseconde par chemin). Les rapports ne gardent pas ces nombres.
  - Les garder rend un Monte-Carlo sur θ gratuit.
  - Ils rendent aussi le précalcul des curseurs abordable : environ 14 h-machine en
    mécanique seule, 66 h avec les comportements et les chemins.
* **Le processus.** Le but 13 a coûté 18 à 22 h-machine pour une série nominale de 8 à
  11 h. Le surcoût vient de deux sources, toutes deux mesurées :
  - 157 passes refaites à l'identique, ce que D-335 lève ;
  - la mémoire, avec des passes de 6 à 13 Go dans un conteneur de 14 Go.

  Les quelque 260 mutants de D-300 à D-334 n'ont trouvé aucun nombre faux. Le code applique
  encore l'ancienne règle à quatre endroits d'`etude.py`, et un test impose un banc de
  mutations.

---

## 1. Est-ce cohérent ?

### 1.1 Ce qui tient

* **Une seule récurrence de dette.** `dette.path.project` ← `predictif.chaine.run`, que
  tous les appelants partagent. La référence se refait à 10⁻⁴ près depuis les rapports
  (annexe 4, § 3.1).
* **Un seul runner de population** (`population/runner.run`) et une seule source du droit,
  `system.baseline()`. Celle-ci empile la correction de l'IFI et les 23 corrections, chacune
  avec sa citation et son test (annexe 2, § 2).
* **Un seul magasin d'élasticités** : il refuse une ligne sans verdict, une ligne `WRONG`
  et une ligne ouverte sans sens de θ. 26 lignes sont chargées, 8 refusées avec leur motif
  (annexe 3, § 0).
* **Le contrat du site** : du HTML sans script, chaque nombre avec son étage, chaque page
  refaite depuis ses seuls rapports, la dérive refusée (`site.py`, `etude.py`).
* **La lecture aux coins de la boîte est exacte.** Chaque canal de recettes est
  multilinéaire ou monotone en ses paramètres, et p(θ) est monotone : les extrêmes sont aux
  sommets (annexe 3, § 2.2).

### 1.2 Les incohérences qui touchent un nombre ou un verdict publié

Par ordre de gravité. Chacune est détaillée, avec ses références, dans l'annexe citée.

| # | incohérence | effet | annexe |
|---|---|---|---|
| 1 | **Le coin du multiplicateur.** m(θ) = c + (2θ−1)·0,66 : un écart-type inter-études (pays et horizons mêlés) ajouté en absolu et tenu dix ans. À θ = 1, IR tenu, la rétroaction vaut 1,015 point de solde par point de choc : la baisse d'impôt rapporte plus qu'elle ne coûte. À θ = 0, le multiplicateur de la première année est négatif (IR −0,25, cotisations employeurs −0,46). Rien ne le borne. | renverse le signe de la dette chez Attal, Lisnard, Le Pen, Roussel et Mélenchon (D-333) | 4, § 3.4 |
| 2 | **La persistance « éteint » fait une falaise.** Le PIB revient à la référence d'un coup à l'an 4. Pour un point de choc d'IR à θ½, Δb passe de +0,67 à +2,69 point. Pour Attal, de +1,78 à +6,49. Or les multiplicateurs **fiscaux** de Mésange ne décroissent pas à 5 et 10 ans (IR 0,88 → 0,81 → 0,87) : « tenu » est plus proche de la source qu'« éteint ». | le chiffre de tête des études est pris sous « éteint » | 4, § 3.4 |
| 3 | **C1 hors de l'objet de son article.** L'élasticité de Cabannes, Houdré et Landais, estimée sur le taux de l'IR, est appliquée au coin marginal **total** (IR, CSG, cotisations, retraits de prestations), sur la **seule masse salariale brute**, comme un niveau permanent chaque année. 90 ménages de Tondelier sont au plancher 1 − τ = 0,05, où Δln(1−τ) explose. | fait coûter la tranche de 60 % de Tondelier (+848 M€ mécaniques, −1 284 M€ de C1) | 3, § 4.2 et 4.4 |
| 4 | **La garde de support de C1 ne voit pas le haut.** La métrique est le 95e centile pondéré de \|Δτ\|. Une réforme qui touche moins de 5 % des ménages la laisse à 0. Tondelier sort donc « in-support », alors que Δ(1−τ) dépasse le support de 0,03 d'un facteur 5 à 10. La bande n'est jamais élargie, et la boîte ne porte de toute façon pas l'élargissement. | une extrapolation dite « dans le support » | 3, § 4.2 |
| 5 | **Double compte probable de C1 et C7** pour un paquet qui touche à la fois l'IR et la CSG d'activité. La variation de CSG entre dans le τ total de C1 et dans le Δln(net) de C7. La partition de D-220 se fait au niveau des leviers, pas des taux. À vérifier par un test. | Lisnard (CSG + quotient) | 3, § 3.2 |
| 6 | **Le taux de la dette ajoutée est le taux implicite net**, 1,88 % : intérêts nets 2025 sur le stock. r − g vaut −1,1 point pendant dix ans, et la boule de neige d'une réforme coûteuse s'en trouve allégée. Le scénario « marché » existe, mais aucune étude ne l'utilise. | Δb sous-estimé de 5 à 10 % pour une réforme coûteuse | 4, § 1.7 |
| 7 | **L'asymétrie macro entre instruments.** Les accises vont à la « taxe carbone », que la boucle exclut. L'IS, la CVAE, la C3S et les transferts n'ont aucun effet macro. Une baisse de TVA a sa boucle, une baisse d'accise n'en a pas. | les candidats ne sont pas traités de même (Labib contre Le Pen) | 4, § 4.5 |
| 8 | **Trois populations effectives selon le point d'entrée.** Les chiffrages préenregistrés (`scenarios.mechanical_price`) n'imputent jamais le capital. L'API n'impute jamais les IJ. Le solveur n'impute rien, et un bouton de TVA y lève. Le même bouton ne coûte pas la même chose selon le chemin. | latent : aucun scénario ne règle le PFU aujourd'hui | 2, § 4.3 ; 1, § 4.3-11 |
| 9 | **Des zéros confiants.** Les boutons d'IJ sur l'API et ceux d'IFI sur la population rendent 0 sans avertissement. Les lignes de C5 et C6 (patrimoine) sont revendiquées par les leviers d'IFI, mais aucun appelant de `src` ne lance ces canaux. Elles ajoutent à la boîte des coins qui ne bougent rien, et le verdict peut sortir « robuste » sans qu'aucun comportement de patrimoine soit chiffré. | contraire à « un article refusé n'est pas un article à zéro » | 2, § 4.3 ; 3, § 4.3-c |
| 10 | **Deux jeux d'indices pour vieillir.** Les cas (D-317) vieillissent aux indices du PLF et du PLFSS 2027, les études à 3 % et 2 %. D-333 compare la part (population 2024) à la somme de ses cas (vieillis PLF) par une réduction forfaitaire de 6,5 % : c'est la réfutation de Labib. | une réfutation qui tient à la convention | 4, § 1 ; 5, § 4.1-e |
| 11 | **Le site met côte à côte des études de quatre moteurs.** Le PLF et le PLFSS ont été chiffrés avant les IJ (D-305 à D-313) et avant D-310 ; les programmes, après. Chaque page dit son commit, mais l'accueil ne dit pas que les coûts ne se comparent pas. | comparaison trompeuse entre pages | 5, § 5.2 |
| 12 | **La TVA de 2026 pour toutes les années**, et les accises qui lèvent en 2025 : `LOI_ENERGIE` n'a que 2024 et 2026, alors que l'API accepte 2022 à 2026. | un droit de 2024 faux sur l'abonnement électricité et gaz | 2, § 4.2 |

### 1.3 Les incohérences de structure

Elles ne faussent pas un nombre aujourd'hui. Elles rendent chaque but plus lent et chaque
correctif plus risqué.

* **Les couches d'imputation empilées.** Niches (B3), queue haute (phase 7), capital (F1b),
  IJ (but 8) et consommation (but 12) ont chacune leur source, leur facteur de correction et
  leur option du runner. Elles suivent :
  - deux conventions de poids : poids personne pour les salaires, pensions et chômage ;
    poids moyen du ménage pour les IJ et les agrégats. D'où −0,36 % structurel sur la masse
    salariale ;
  - trois conventions de rang : rang pondéré des foyers, seuils absolus publiés, rang des
    ménages.

  Leurs incompatibilités sont tranchées par des refus deux à deux, sans calage commun.
  Chaque couche relance aussi une simulation de référence à chaque passe (annexe 1, § 4.3).
* **Les millésimes mêlés** : EEC 2024, RP 2023, BTS 2024, n° 41 2024, Budget de famille
  **2017**, ERFS 2022, cellules d'entreprises 2023. La population « 2024 » est une structure
  de 2024, calée sur des ménages de 2023, avec une consommation de 2017.
* **La couche de service dans l'API.**
  - Les fonctions qui servent tout le monde sont privées dans `api/main.py` :
    `_price_first_year`, `_population_frame`, `_first_year_request`.
  - La CLI, les scénarios, le programme et les scripts les appellent quand même (une
    quinzaine d'appels). Le domaine dépend donc de l'API.
  - Toute la CLI vit dans `population/cli.py` (2 300 lignes).
  - Une dizaine de chemins produisent un coût (annexe 5, § 2.1).
* **Le cadre des études.** Il est écrit une fois, mais dans `etude/ir.json`, qui est aussi
  la requête de l'étude IR de la phase 10. Une quinzaine de copies vivent sous `etude/**`.
  `programmes/hypotheses/etude.json` porte les mêmes nombres sous d'autres noms. Le cadre
  dit « salaires à 3 %, le rythme du PIB nominal », mais le PIB nominal du scénario est
  3,02 %, et la croissance réelle n'est pas liée aux salaires.
* **Trois conventions de signe** : le ménage (+ = il paie), le coût (+ = l'État perd), la
  bande (+ = recette). Le passage du coût à la recette est refait à la main à chaque appel
  de la bande.
* **Deux représentations de l'incertitude qui se contredisent.**
  - La bande de la phase 3 publie la **médiane** de triangulaires ; θ½ est leur **mode**.
  - Pour une ligne `normal`, [bas ; haut] est un intervalle à 90 % dans la bande, des bornes
    dures dans θ.
  - L'éventail de `fan.py` fait ±1,36σ, la boîte ±1σ.
  - La spec dit « un θ par canal », le code en met un par ligne : C1 en a 2, C7 4, C10 4.
* **Trois conventions de persistance** :
  - les comportements sont un niveau permanent, recalculé chaque année ;
  - la boucle est « éteint » ou « tenu » après trois ans ;
  - l'IS suit une rampe de dix ans.
* **Les pages couplées aux définitions vivantes.** Corriger une coquille dans une plage
  d'un programme, une source ou le cadre casse la page, et seule une nouvelle série de
  passes la répare. Le schéma des rapports n'est pas versionné : un champ rendu obligatoire
  invalide les dix études. Les rapports ne gardent ni l'empreinte des données ni leur
  durée.
* **`etude.py` code chaque type de texte en dur** (`_PLF2027`, `_PLFSS2027`, `_Programme`).
  L'étude du PLF 2028 demandera une classe Python de plus.

### 1.4 Le code mort et la documentation périmée

Ce qu'il y a à retirer ou à corriger, vérifié par `grep` :

* **Modules vides** : `src/impots/mechanical/` et `src/impots/legislation/`.
* **Registres sans lecteur** :
  - `IFI_KNOBS` n'est lu nulle part ;
  - `PRESTATION_KNOBS` n'est lu que par des tests, alors que son commentaire dit que la
    macro et l'interface le lisent ;
  - `entreprises/population.stats_as_dict` n'est appelée nulle part ;
  - la branche `aggregate_deltas` de `sector_balance` n'a pas d'appelant.
* **Code de production qui ne tourne plus qu'en test** : `predictif/elasticites.py` (la
  boucle refusée de la Commission), `predictif/validation.py` et `predictif/macro.at_theta`.
  Ce sont des archives de refus, mais elles entrent dans `make impact`.
* **Canaux écrits, testés, jamais appelés** : C5 et C6 (point 9 du § 1.2).
* **Un même calcul recopié** : la base et le décile de C1 sont dans `api/main.py` et dans
  `accuracy_behavioural.py`.
* **Docstrings et documents périmés** :
  - « seven knobs » (il y en a 77 dans l'arbre), « 2 to 5 brackets » (6 depuis D-320) ;
  - « dix paramètres » dans `accuracy_behavioural.py` ;
  - le capital « identiquement nul » de la carte de score ERFS, faux depuis D-248 ;
  - `reports/reconciliation.md`, qui date du 4 septembre et affiche des pensions de
    400 Md€ ;
  - `docs/BUT.md` et `STATE_AND_NEXT.md`, qui citent `docs/ETUDE_PLF2027.md`, disparu ;
  - D-289, qui cite `scripts/write_etude_plf2027.py`, disparu.
* **Une valeur substituée** : `reform_cost or 0.0`, sept occurrences, change un `None` en
  zéro. C'est le motif que `CLAUDE.md` interdit, même s'il ne se produit pas au palier
  complet.
* **Une douzaine de scripts `verify_*`** qui sont des portes de phases closes. Ce sont des
  archives exécutables, à ranger sous `scripts/archives/`.

---

## 2. Quels paramètres utilise-t-on ?

L'inventaire complet, ligne par ligne, est dans les annexes. Ici, ce qu'il faut en retenir.

### 2.1 Les boutons de réforme : 103

| registre | nombre | ce qu'il écrit | sourcé |
|---|---:|---|---|
| `ReformSpec`, scalaires de l'arbre openfisca | 68 | une feuille de paramètre | le droit, par openfisca |
| plafonds de bandeau, échelle des cotisations, revalorisations, barèmes IR et IFI | 2 + 1 + 4 + 2 | plusieurs feuilles, ou une date légale | idem |
| TVA (4 taux, `tva_postes`) et accises (5) | 10 | couche maison `consommation.py`, hors arbre | `docs/consommation/regles.md` |
| `ifi_obligations_declaratives` | 1 | aucun paramètre ; seulement C6, jamais appelé | — |
| `FirmReformSpec` | 15 | arbre maison `entreprises/parameters/` ; 2 CIR hors arbre | PHASE2_SPEC, D-222 |

Les champs sont tous lus quelque part. Deux boutons d'IJ n'existent que par la correction
22, qui crée leurs paramètres. 49 des 88 boutons des ménages sont absents de l'interface,
dont tous ceux des études publiées : TVA, accises, échelle des cotisations, parts de
quotient, plafond des pensions. Les unités mêlent l'euro par an, l'euro par mois (RSA, PPA,
BMAF), le multiple du SMIC, l'euro par litre et l'euro par MWh. Les gardes croisées sont
jugées contre des constantes de 2024, quelle que soit l'année. Le barème de l'IFI n'a pas
de relecture. Tableau bouton par bouton : annexe 2, § 1.2.

### 2.2 Les hypothèses du cadre

| hypothèse | valeur | défini | lu | sourcé |
|---|---|---|---|---|
| croissance réelle | 1 %/an | `etude/ir.json` et une quinzaine de copies | `dette/scenarios.py`, `reference.py`, `firmes.py` | **non** (scénario nommé) |
| prix | 2 %/an | idem | `reference.py`, `annuel.uprating_for` | **non** |
| salaires par tête | 3 %/an | idem | `uprating.py` | **non** ; découplés du réel |
| pensions, loyers | prix | `uprating.py` | idem | convention |
| dépense | gelée en volume | `dette/path.py`, `reference.py` | seule règle où la boucle tourne | convention ; cache une consolidation de 5,2 points de solde primaire d'ici 2035 (la dette de référence passe de 116 % à 104 %) |
| taux de la dette ajoutée | implicite tenu, 1,883 % | `reference.py:69` (intérêts **nets** 2025 / stock) | `chaine._rate_path` | comptes nationaux, mais net |
| horizon | 10 ans, plafond dur | `dette/path.py:50` | | « M0 » |
| départ | 2025 : dette 115,69 %, PIB 2 991 Md€, solde primaire −2,99 % | `comptes.py` | `chaine.run` | **INSEE, sourcé** |
| persistance | « éteint » ou « tenu », aucune par défaut | `retroaction.py:71-75` | `annuel.py` | **aucune source** |
| θ | ½ commun | JSON des études | `theta.py` | choix |
| loi de référence | « reconduit » : barèmes et prestations figés en euros | `trajectoires.py` | CLI | droit voté |
| vieillissement des cas | PLF et PLFSS 2027 : salaires +2,0 / +2,0 / +2,7 % | `hypotheses.py:75-102` | `chiffrage register` | **sourcé** (D-317) |

Le cadre des études n'a aucune valeur sourcée, et il contredit les cas, qui vieillissent
aux indices du gouvernement. C'est un choix défendable (« scénario nommé »), mais il faut
l'écrire une fois, dans un fichier à lui, et le confronter au moins une fois au cadre du
PLF 2027.

### 2.3 θ, la boîte et les canaux

| canal | objet | paramètre : centre [bas ; haut] | source | dans la bande | appelé |
|---|---|---|---|---|---|
| C1 | revenu imposable | ε_all 0,02 [0,01 ; 0,02] ; ε_top 0,31 [0,15 ; 0,50] | Cabannes, Houdré, Landais 2014 | oui | oui |
| C2 | emploi jusqu'à 2 SMIC | −0,43 [−0,52 ; −0,31] ; −0,1 et 2 fixes | Bunel-L'Horty ; GE SMIC 2025 | non (emplois) | oui |
| C3 | incidence des cotisations | 0 [−0,06 ; 0,25] / 1 [0,85 ; 1,1] | Bozio et al. 2026 | non | oui |
| C4 | investissement | 0 [−0,071 ; 0,069], uniforme | IPP n° 60 | non | oui |
| C5 | patrimoine déclaré | 0 [0 ; 0,36] | Garbinti et al. | oui | **non** |
| C6 | obligations déclaratives | 0,28 pp [0,13 ; 0,50] | Garbinti et al. | non | **non** |
| C7 | heures, 4 groupes | 0,065 à 0,15 | Bargain, Orsini, Peichl 2012 | oui | oui |
| C8 | créations de sociétés | 0,38 [0 ; 0,684] | IPP n° 47 | non | oui |
| C9 | R&D et CIR | 1,1 [0,8 ; 1,4] | IPP n° 22 | non | oui |
| C10 | dividendes et PFU | ε_p, ε_a, s, ω | Bach et al. 2019 | oui | oui |
| C11 | autofinancement | p 0,5 [0 ; 1] ; 12 000 et 20 000 fixes | Trésor-Éco n° 97 et un choix | oui | oui |
| hors canal | croissance de l'IS | 0,00945 [−0,0001 ; 0,019] | Gechert-Heimberger | non (indice) | oui |
| macro | multiplicateur | Mésange ± σ_IMK = 0,66 | INSEE G2017/04 ; IMK WP117 | dette | oui |

Le code compte **onze** canaux, pas dix : C11 date de D-263. Sur les 26 lignes chargées,
24 sont `SCOPE_PROBLEM` et 2 `CONFIRMED`. θ interpole par morceaux, ligne par ligne, du
bas au haut en passant par le centre publié. La boîte calcule les 2^K coins, sans passe de
plus. Un programme qui touche l'IR, la CSG, les allègements et le PFU avec la boucle a
K = 15, soit 32 768 coins. La persistance n'est pas un θ : c'est un scénario discret, et le
verdict parcourt les deux. Détail : annexe 3.

### 2.4 La macro

* **Mésange** (INSEE G2017/04, § 4) : neuf variantes. Les horizons 1, 2, 3, 5, 10 et le
  long terme sont parsés du PDF, mais seuls 1 à 3 ans sont lus. Les multiplicateurs de PIB
  et la ligne de solde primaire sont donnés par instrument (annexe 4, § 2.1).
* **IMK** : un écart-type inter-études par famille ; les instruments fiscaux prennent
  σ = 0,66.
* **Le TES** (Leontief de type I) rend des parts et la fuite à l'importation ; il ne touche
  pas la dette.
* **Aucune élasticité des recettes au PIB.** La ligne du HCFP est morte (verdict `WRONG`).
  La rétroaction est la ligne de solde de Mésange, rendue proportionnelle à m(θ)/c.

### 2.5 La population

| paramètre | valeur | sourcé |
|---|---|---|
| millésime | EEC 2024, 199 451 ménages, environ 423 000 personnes, sans tirage | INSEE |
| passe rapide | 20 000 ménages, PPS avec strate de certitude (D-074) | plafond machine, pas un choix statistique |
| calage | IPF à pondération de ménage intégrée, bornes [0,2 ; 5] par troncature, 15 cellules, dont **une seule marge externe** (5 types de ménage, RP 2023) ; les 10 cellules âge × sexe calent sur la population elle-même | RP 2023 |
| salaires | quantile log-linéaire en Φ⁻¹ à travers (D1, médiane, D9) de la BTS par PCS ; Pareto au-dessus du 95e centile (α ≈ 2,65) ; un facteur pour 1 111,65 Md€ | BTS 2024, CN 2025 |
| pensions, chômage | lognormales, σ = 0,55 et 0,45, calées sur 374,4 et 35,9 Md€ ; « retraité » = inactif de 55 ans ou plus | masses sourcées ; σ et le 55 **non** |
| loyers | (30 + 12 n) m² × loyer au m² | surface **non sourcée** |
| imputations à la passe | capital (n° 41), queue haute L1, niches (Bernoulli par décile), IJ (cellule âge × PCS), consommation (TF106 2017) | chacune sourcée |
| vieillissement | 4 colonnes multipliées ; poids, âges et structure figés | indices déclarés |

Une vingtaine de constantes ne sont pas sourcées : la probabilité d'un garçon, la surface
du logement, les σ, l'âge de 55 ans, la part d'enfants hors du foyer parental (annexe 1,
§ 3).

---

## 3. Peut-on avoir un modèle qui utilise plus de paramètres ?

Oui. Le tableau classe ce qui manque par euros en jeu ou par poids dans les questions des
lecteurs. Le coût est en jours de travail, données comprises : petit, un jour ; moyen,
une semaine ; gros, un but.

| rang | manque | enjeu | ce qui existe déjà | coût |
|---:|---|---|---|---|
| 1 | **Persistance sourcée de la boucle** : les colonnes 5 et 10 ans de Mésange, interpolées | décide six verdicts sur huit | colonnes déjà parsées | petit en code ; une D-entrée de doctrine (rouvre D-055) |
| 2 | **Un multiplicateur borné**, avec une largeur qui dépend de l'horizon | supprime m < 0 et la rétroaction supérieure au coût | `theta.multiplier_at` | petit |
| 3 | **Le taux de marché pour la dette ajoutée** (OAT, encours AFT) | +5 à +10 % de Δb pour une réforme coûteuse | le scénario « marche » existe | nul en code ; une valeur à nommer |
| 4 | **Indexation des pensions et des prestations** (« année blanche ») | 3 à 4 Md€ par point de pensions ; 27 mesures de programmes refusées | `REVALORISATION_KNOBS` | moyen : les pensions sont des entrées, pas des paramètres |
| 5 | **Indexation du barème de l'IR** en bouton | environ 0,5 Md€ par point | `trajectoires.indexation_spec` | petit |
| 6 | **Cotisations patronales par risque** (maladie, vieillesse, famille, chômage) | 6 à 8 Md€ par point de masse privée | l'échelle salariale de D-320, le terme patronal du coût | petit à moyen |
| 7 | **La consommation aux prix** (TVA et accises) | carburants, −0,2 à −0,4 à court terme ; Labib est chiffré sans réponse | consommation par poste imputée | moyen, aucune passe : un canal arithmétique |
| 8 | **C1 sur la base fiscale complète**, avec les réponses croisées salaire ↔ dividendes ↔ plus-values | ce qui renverse Tondelier ; les tranches, la CEHR, la CDHR | capital imputé (D-248) | moyen |
| 9 | **La base de l'IS** (transfert de bénéfices) | 0,3 à 0,6 Md€ par point d'IS | cellules d'entreprises | moyen |
| 10 | **C5 et C6 câblés** | IFI, retours de l'ISF | canaux écrits et testés | **petit** |
| 11 | **Prime de risque endogène** : r = m + β·b | non linéaire pour Attal (+20 points) | — | petit en code, moyen en source |
| 12 | Successions, DMTG, taxe Zucman | 15 à 20 Md€ de DMTG ; 17 mesures refusées | IFI au foyer seulement | **gros** : il faut du patrimoine au ménage |
| 13 | Âge de la retraite | des dizaines de Md€ | rien : les âges sont figés | **gros** : démographie |
| 14 | Les taxes « secteur » du PLF 2027 (2,2 Md€, première porte en euros) | part en euros du PLF | facteur d'échelle dans `agregats/`, branché sur aucun bouton | moyen |
| 15 | Marge extensive aux bas revenus, CEHR, montants ASPA/AAH/ASS, CSG chômage | 0,5 à 1,5 Md€ chacun | variables calculées | petit à moyen |

Les rangs 1 à 3 coûtent peu et rendent les verdicts de dette **plus justes**, sans ajouter
de mesure. Les rangs 4 à 6 ouvrent le plus d'euros des programmes pour le moins de code.
Les rangs 12 et 13 sont des buts entiers.

Plus de paramètres a un prix : chaque bouton ajouté augmente le nombre de coins (2^K) et la
grille de précalcul. Le § 4.4 montre que le Monte-Carlo supprime la première contrainte.

---

## 4. Le modèle mathématique, en détail

Notation : i un individu, f un foyer, h un ménage, w un poids, τ un taux marginal effectif,
t une année, v ∈ {vieillie, figée} une vue.

### 4.1 La génération de la population

**Le squelette.** Chaque couple (logement, trimestre) de l'EEC 2024 est un ménage, sans
tirage, avec son poids `EXTRIAN`. L'âge est tiré uniformément dans la tranche AGE6 :
$a_i \sim \mathcal U\{\ell_b..u_b\}$. Les enfants de moins de 15 ans sont synthétisés, et
le nombre d'enfants suit $K_h \sim \text{Cat}(\pi_{t(h)})$ (RP 2023). On garde
$\max(0, K_h - V_h)$ enfants, où $V_h$ est le nombre de moins de 25 ans visibles. Si l'on
dépasse 1,05 fois la cible, on amincit au hasard. Le foyer 0 est la personne de référence,
son conjoint et les enfants ; chaque autre adulte est son propre foyer.

**Le calage** (`calibrate.py`, fermé). C'est un IPF à pondération de ménage intégrée.
Départ : $w_h^0 = \overline{w_i}_{i \in h}$.

* Marge ménage (cellule c, cible $T_c$) :
  $$w_h \leftarrow w_h \cdot T_{c(h)} \big/ \textstyle\sum_{h' \in c(h)} w_{h'}$$
* Marge personne, avec $n_{hc}$ le compte de la cellule c dans le ménage h :
  $$f_c = \frac{T_c}{\sum_h w_h n_{hc}}, \qquad
  w_h \leftarrow w_h\,\frac{\sum_c n_{hc} f_c}{\sum_c n_{hc}}$$
* Après chaque balayage, troncature à $[0{,}2\,w^0_h ;\ 5\,w^0_h]$.
* Arrêt à 10⁻⁶ en variation relative, ou après 200 itérations ; refus si une marge s'écarte
  de plus de 10 %.

C'est un *raking ratio* approché, pas le calage généralisé de Deville et Särndal. Celui-ci
résoudrait $w_h = w^0_h \exp(x_h^\top \lambda)$, avec la logit bornée de CALMAR. Résultat
(D-017) : 25 itérations, écart sur le type de ménage ramené de 41,5 % à 0,84 %, taille
effective de Kish 143 973 sur 199 451.

**Les revenus.** Ils sont tirés de lois, sans donneur.

* Salaire, pour la PCS g de nœuds $(p_k, q_k)$, $k \in \{0{,}1 ; 0{,}5 ; 0{,}9\}$ :
  $$\log Q_g(z) = \text{interp}\big(z ;\ \Phi^{-1}(p_k),\ \log q_k\big), \qquad
  z_i \sim \mathcal N(0,1)$$
  $$y_i = Q_{g(i)}(z_i) \cdot \frac{\bar y_{s(i)}}{\bar y} \cdot
  \Big(\frac{1620}{2733}\Big)^{\mathbb 1[a_i<25]}$$
* Au-dessus du 95e centile (non pondéré, calculé sur toutes les lignes) :
  $y_i \leftarrow 5593\,(1-u_i)^{-1/\alpha}$, avec $\alpha \approx 2{,}65$.
* Puis $\text{brut}_i = \lambda \cdot 12\,y_i\,q_i / 0{,}7587$, où $q_i$ est la quotité et
  λ le facteur qui cale sur 1 111,65 Md€ sous le poids **personne**.
* Pensions et chômage : $x_i = e^{\sigma \varepsilon_i}$, mis à l'échelle de leur masse.
* Aucune corrélation à l'intérieur du ménage.

**Les imputations, à chaque passe et en option.**

* Capital : par bande b de RFR par part,
  $\text{base}_f = \rho \cdot \frac{\tau^{HB}_b}{0{,}128} \cdot s_j$, avec ρ ≈ 1,17 qui
  corrige le déficit de foyers.
* Queue haute : un facteur par bande de rang pondéré,
  $\phi_k = t_k / \bar r_k \in [0{,}5 ; 5]$.
* Niches : $B_f \sim \text{Bernoulli}\big(\min(N_d / W_d, 1)\big)$.
* IJ : $\text{IJ}_i = k_i\, M / \sum_j \bar w_{h(j)} k_j$, avec la clé
  $k_i = f_{a,p} \min(\text{brut}_i,\ 1{,}8\ \text{SMIC} \times 12)$.
* Consommation :
  $$c_{h,p} = \bar c^{2017}_{p,d(h)} \cdot \frac{UC_h}{\overline{UC}_{d(h)}} \cdot
  \frac{CN_{\text{div}(p)}(t)}{CN_{\text{div}(p)}(2017)}$$

**Le vieillissement.** $x_i(t) = x_i(2024) \prod_{a=2025}^{t} (1 + g_a^{k(x)})$, avec
k ∈ {salaire, prix}, sur quatre colonnes. Poids, âges et structure ne bougent pas.

**La passe rapide** (D-074). Une strate de certitude ($k\,w_h \geq W_{\text{reste}}$, au
point fixe), puis un tirage PPS systématique de Madow. Les ménages hors de la strate
reçoivent $W_{\text{reste}}/k$.

**Ce qui est solide, ce qui est fragile.**

* Solide : la provenance, la reproductibilité octet pour octet, la séparation du calage et
  de la validation, les gardes D-149 (échantillon riche) et D-150 (convergence ≠
  ajustement). L'IR du barème tombe à +8,8 % de sa cible.
* Fragile, et non calé :
  - les foyers fiscaux (−15 %) ;
  - le RSA (+113 %) et l'ASF (×4,5) ;
  - les DOM : `region` n'est pas câblée ;
  - le secteur public : `secteur_public` est tiré mais non câblé, et 5,8 M de salariés
    sont traités comme du privé ;
  - la consommation, imputée à 70 % des comptes nationaux.
* Aucune erreur-type n'est produite. Le bruit d'échantillonnage à 20 000 ménages se mesure
  en points (D-074, D-076), et l'outil le traite par des tolérances déclarées.

**Ce qu'un modèle plus propre ferait** (annexe 1, § 5).

* **Un calage unique**, à la construction, par CALMAR ou samplics, avec une distance raking
  ou une logit bornée. Il porterait sur toutes les marges externes : types de ménage, âge ×
  sexe (pyramide de 2024), DOM, public et privé, nombre de foyers, masses par décile de RFR,
  niches, IJ, consommation par division.
  - Les montants seraient tirés une fois, et seuls les poids bougeraient.
  - Cela supprime les cinq conventions et les une à trois simulations de référence que
    chaque couche relance à chaque passe.
  - Coût : une à deux semaines. **Mais `calibrate.py` est fermé jusqu'à la phase 7 de son
    propre plan. C'est la décision du propriétaire.**
* **Des poids de réplication** : 50 à 100 bootstraps de l'EEC par grappe de logement,
  recalés. Ils donnent un intervalle sur chaque coût au lieu d'une tolérance déclarée.
  Il faut 50 fois plus de passes ; à réserver aux chiffrages publiés.
* **L'ERFS 2022 comme source** plutôt que comme comparateur. Elle effacerait la loi
  synthétique des salaires, le proxy de retraite et le déficit de foyers. Coût : trois à
  six semaines, avec la contrainte de diffusion de D-012.

### 4.2 Le coût mécanique

Ce que le code calcule (`population/aggregate.py:182`), positif quand l'État perd, en
sommant les variables mensuelles sur douze mois :

$$C = \sum_h w_h\,\Delta \text{RD}_h \;-\; \sum_h w_h\,\Delta(\text{SSB} - \text{SB})_h \;-\;
\sum_h w_h\,\Delta(\text{TVA} + \text{accises})_h$$

* Δ = réforme − droit ; RD est le `revenu_disponible` d'openfisca. Le coût embrasse donc
  toute la cascade : IR, CSG, CRDS, cotisations, prélèvements sur le capital, prestations.
* SSB − SB, le super-brut moins le brut, donne les cotisations patronales nettes des
  allègements.
* La somme par instrument ne sert que de contrôle : `sector_balance`, à 10⁻³ du net près,
  avec un plancher de 5 M€.
* Entreprises : $C = -\sum_f w_f\,\Delta(\text{IS} + \text{CS} + \text{CEBGE} + \text{C3S} +
  \text{CVAE})$ sur 19 sections × 4 tailles d'Ésane 2023, sans élasticité ni lien avec les
  ménages.

**Les déciles.** Le niveau de vie est RD^droit / UC, à l'échelle OCDE modifiée. Le rang est
pondéré par ménage. Le Δ est moyen par ménage, avec les parts de gagnants et de perdants à
±10 €. Le pouvoir d'achat retire la TVA et les accises à volumes constants, répercutées en
entier.

**Solide** : la lecture sur le revenu disponible ne peut rien oublier de la cascade, et le
contrôle par instrument tient. **Fragile** : la population effective change avec le point
d'entrée (§ 1.2, point 8), et l'IR est compté en année pleine des revenus, sans le
calendrier du PAS sur le chemin de la dette.

### 4.3 La bande comportementale (étage L3)

On tire 1 000 fois (graine 20260902), chaque ligne du magasin selon sa loi (triangulaire,
uniforme ou normale), **indépendamment**. Puis :

$$R^{(d)} = -C + \sum_{k \in \{C1, C5, C7, C10, C11\}} \Delta R_k^{(d)}, \qquad
\text{bande} = \big(q_{10},\ q_{50},\ q_{90}\big)\big(R^{(d)}\big)$$

La bande est élargie d'un facteur 2 autour de la médiane si la note est « illustrative ».
Les équations des canaux qui entrent dans la bande :

* **C1** :
  $$\Delta R = \sum_i w_i\, z_i\, \varepsilon_{g(i)}
  \big[\ln\max(1-\tau^1_i, 0{,}05) - \ln\max(1-\tau^0_i, 0{,}05)\big]\,\tau^1_i
  = \varepsilon_{\text{all}} A_{\text{bas}} + \varepsilon_{\text{top}} A_{\text{haut}}$$
  avec z le salaire brut du ménage et τ le taux marginal total, en différence finie de
  100 € de salaire par apporteur. Il est calculé sur quatre échantillons de 3 000 ménages,
  plus les ménages dont le salaire dépasse 200 000 €, soit seize simulations par passe.
* **C7** : $\Delta R = \sum_g \varepsilon_g S_g$, avec
  $S_g = \sum_{i \in g} w_i y_i\,\Delta\ln(\text{net})\,\tau^1_i$ ; Δln(net) est un
  scalaire unique, tiré des masses nettes.
* **C10** : multilinéaire en (s, ε_p, ε_a, ω).
* **C11** : $s = (1-p)\,N v / |\text{baisse}| + 0{,}6\,p$, avec N tiré de C2.

Les canaux sont **strictement additifs**, sans terme croisé.

### 4.4 θ, la boîte et les coins

Pour chaque ligne ouverte (bas b, centre c, haut h), avec $t = \theta$ ou $1 - \theta$
selon le sens déclaré :

$$p(t) = \begin{cases} c - (1-2t)(c-b) & t \leq \tfrac12 \\
c + (2t-1)(h-c) & t \geq \tfrac12 \end{cases}$$

Le multiplicateur suit $m_i(h, \theta) = c_i(h) + (2\theta - 1)\,\sigma_{TAX}$. La boîte
est l'ensemble des 2^K coins, chaque ligne revendiquée valant θ = 0 ou 1. Chaque coin
rejoue la bande à un tirage, puis la chaîne, sans passe moteur.

Le verdict est « hausse » ou « baisse » si Δb à la dernière année a le même signe à θ½ et
à **tous** les coins, dans les deux vues et sous les deux persistances. Sinon, il est
« dépend de θ ».

**Ce qui est solide.** La lecture aux coins est exacte, et la garde de monotonie la
protège.

**Ce qui est fragile.** Le verdict est un « pour tout » sur des conjonctions extrêmes :
toutes les élasticités à leur bord, le multiplicateur à +1σ, tenu dix ans. Il ne dit
**pas quelle probabilité** renverse le signe, et la convention « θ = 1 = la réponse la plus
forte de l'économie » mélange des directions de recette opposées.

**Ce qu'un modèle plus propre ferait : un Monte-Carlo à côté de la boîte, pas à sa place.**

* **Le constat qui décide.** Chaque canal de recettes est une fonction fermée de quinze à
  vingt statistiques suffisantes par année et par vue :
  - C1 : $A_{\text{bas}}$ et $A_{\text{haut}}$ ;
  - C7 : les quatre $S_g$ ;
  - C2 et C11 : quatre scalaires ;
  - C10 : six scalaires ;
  - la macro : les impulsions par instrument.

  Un tirage ne demande **aucune passe**.
* **Les lois a priori.** On garde les triangulaires du magasin, en disant pour chaque ligne
  si [bas ; haut] est un intervalle de confiance, un écart entre spécifications ou un
  jugement. Pour le multiplicateur : une normale (centre Mésange, σ IMK), tronquée à m ≥ 0.
* **Les corrélations**, par copule gaussienne :
  - ρ élevé entre les lignes d'un même article (ε_all et ε_top ; les quatre groupes de C7 ;
    ε_p, s et ω) ;
  - ρ ≈ 0 entre familles ;
  - un ρ à discuter entre C1 et le multiplicateur.

  À préenregistrer.
* **Les sorties** : P(Δb_2035 > 0), les quantiles à 5, 50 et 95 %, et les indices de Sobol
  du premier ordre et totaux. Ils diraient, pour Attal, si c'est le multiplicateur ou C1 qui
  porte la variance. Le verdict deviendrait par exemple : « baisse la dette avec une
  probabilité de 0,93 sous ces lois ; renversée seulement au coin m = +1σ, tenu ».
* **Le coût.** Il faut 2 000 tirages pour une probabilité de 0,05 à ±0,005. Avec la méthode
  de Saltelli, des indices de Sobol à K = 15 demandent environ 34 000 évaluations, soit
  quelques secondes vectorisées. C'est autant que les 32 768 coins d'aujourd'hui, et cela
  dit davantage.
* **La condition** : les rapports doivent écrire ces statistiques. Aujourd'hui, elles
  vivent en mémoire pendant `annuel.build` et sont perdues à l'écriture.
* La règle de la phase 9, « θ n'est pas une probabilité », est à **réécrire par une
  D-entrée**, pas à contourner. On publie deux objets nommés : la boîte de θ, et la
  distribution sous des lois déclarées.

**Un émulateur.** Inutile sur l'axe des élasticités, où la forme est exacte. Utile sur
l'axe des **boutons**, où chaque point coûte une passe : voir le § 5.

### 4.5 La macro et la boucle

L'impulsion de l'instrument i, en points de variante, est
$u_{i,t} = 100\, I_{i,t} / (e_i\, Y_t)$, avec $e_i = 1{,}18$ pour la TVA et 1 sinon. Les
chocs permanents décalés se superposent. Pour un horizon $h \leq 3$, ou $h := 3$ sous
« tenu » (et 0 au-delà de 3 sous « éteint ») :

$$y_k = \sum_i \sum_{j \leq k} \frac{(u_{i,j} - u_{i,j-1})\,m_i(k-j+1, \theta)}{100},
\qquad
\varphi_k = \sum_i \sum_{j \leq k} \frac{(u_{i,j} - u_{i,j-1})\,
\big(\text{solde}_i(h) + e_i\big)\,m_i/c_i}{100}$$

Ici y est l'écart de PIB, pris comme nominal (les prix de la réforme sont tenus constants),
et φ l'amélioration du solde primaire. La boucle ne tourne que sous la dépense gelée en
volume, et seulement pour l'IR, la CSG, les cotisations et la TVA.

### 4.6 La dette

La référence, en ratio, avec un excédent primaire positif :

$$b_t = b_{t-1}\,\frac{1 + r}{1 + g} - p_t, \qquad p_t = R - s_t, \qquad
s_t = s_{t-1}\,\frac{1+\pi}{1+g}$$

La réforme :

$$\Delta D_t = \Delta D_{t-1}\,\frac{1+m}{1+g} + \frac{C_t^{v}(\theta)}{Y_t} - \varphi_t,
\qquad \Delta b_t = \frac{b_t + \Delta D_t}{1 + y_t} - b_t$$

Ici $C_t^v(\theta)$ est le coût de l'année t dans la vue v, comportements à θ compris. Les
deux vues appliquent la **même** fonction à deux séries de coûts, contre le même PIB de
référence :

* **figée** : la population de 2024 sous le droit de t ;
* **vieillie** : salaires × 1,03^(t−2024), pensions × 1,02^(t−2024), sous la loi
  « reconduit ».

Le chemin rapide (`/predictif/simulate`) reporte la première année en part de PIB
constante. Sur les 35 points de plage qui ont une dette, Δb est **exactement linéaire** en
le coût : +0,309 point en 2035 par Md€ de 2026, le même vecteur pour tous (recalculé depuis
les rapports, annexe 5, § 4.1). Le chemin chiffré année par année donne 0,24 à 0,29.

**Solide** : la comptabilité (la référence se refait à 10⁻⁴ près), et le refus de la boucle
hors de la seule règle où Mésange la justifie.

**Fragile** :
* les points 1, 2, 6 et 7 du § 1.2 ;
* la dépense gelée en volume, une consolidation implicite de 5,2 points de PIB que la
  référence ne nomme pas comme un effort ;
* la démographie figée ;
* la rétroaction de Mésange, qui est un écart de ratio mais est lue comme des euros, ce qui
  la surestime d'environ 5 à 8 %.

**Ce qu'un modèle plus propre ferait.**

* Il lirait la persistance dans les colonnes 5 et 10 ans de Mésange, en interpolant de 4 à
  10.
* Il borne m à ≥ 0 et φ en dessous du coût.
* Il charge la dette ajoutée au taux de marché, ou à une prime de risque endogène.
* Il donne aux accises, à l'IS et aux transferts un multiplicateur sourcé, ou dit leur
  absence dans le verdict lui-même.

---

## 5. On calcule chez nous, on publie en HTML : la couche de précalcul

### 5.1 Le principe

Le coût d'une réponse se sépare en deux étages, et toute l'architecture en découle.

1. **Les passes, chères.** Elles dépendent de la loi, de la population et des indices de
   salaires et de prix. Une passe rapide prend environ 2 minutes ; avec les taux marginaux
   à froid, jusqu'à 8 minutes. Une passe pèse 6 à 7 Go. Un chemin, c'est 10 ans × 2 vues
   = 20 passes, soit 45 à 96 minutes.
2. **La chaîne, gratuite.** La dette, la boucle, θ, la boîte, les deux persistances et le
   cadre (croissance réelle, taux, règle de dépense, horizon) sont des fonctions fermées de
   quelques nombres par année et par vue. `docs/audit_but14/chaine_min.py` refait la
   chaîne en quarante lignes, retrouve la référence à 10⁻⁴ près et tourne en moins d'une
   milliseconde par chemin. Le navigateur peut en refaire des milliers par seconde.

On précalcule donc l'étage 1 sur une grille de boutons, et le navigateur fait l'étage 2.
Il faut écrire, par point de grille, par année et par vue :

* le coût et ses couches ;
* les impulsions par instrument (au plus six nombres) ;
* les statistiques suffisantes des canaux (quinze à vingt nombres) ;
* les dix déciles.

### 5.2 La grille

Ce que les rapports commités montrent déjà (recalculé, annexe 5, § 4.1) :

| forme du bouton | mesure | conséquence |
|---|---|---|
| taux proportionnel (tranche, CSG, TVA, échelle) | linéaire : 0,001 % (tranche de Tondelier), 0,08 % (CSG de Lisnard), 0,13 % (échelle d'Attal), 0 (TVA) | 5 points suffisent |
| seuil ou part (plafond d'allègement, parts de quotient, plafond du quotient) | non linéaire : l'allègement de Mélenchon s'écarte de 9,9 Md€ de l'interpolation pour 9,5 ; les parts, de 4 % ; le plafond du quotient sature | 9 à 11 points, denses autour de la loi et des seuils |
| accise × TVA sur un même poste | bilinéaire (la TVA porte sur le prix accise comprise) | exact avec un carré de 4 points |
| entreprises (IS, CVAE, C3S, CEBGE) | un chemin de dix ans en 55 s, sans population | grille dense, presque gratuite |

Environ 40 curseurs présentables couvrent les 103 boutons. Il faut compter :

* 7 points chacun en moyenne, plus denses aux seuils ;
* **un point témoin** par curseur, au milieu du plus grand intervalle : il mesure l'erreur
  d'interpolation, qu'on publie à côté du curseur ;
* le point « loi », qui doit rendre 0 € et sert de contrôle gratuit : il aurait vu le
  « 3 contre 3,0 » de D-329.

### 5.3 La combinaison des mesures d'un programme

* **Additif par construction** : les ménages et les entreprises (deux appels), la
  consommation et les revenus. Le programme de Le Pen tombe à la somme de ses deux mesures
  au centime.
* **Les interactions à mesurer** : les paires qui passent par l'assiette de l'IR ou par les
  prestations sous condition de ressources.
  - Exemples : CSG déductible × barème et quotient ; cotisations × CSG × IR ; prime
    d'activité × RSA × allocation logement ; décote × barème.
  - Mesuré : dans le programme de Lisnard, la CSG et le quotient interagissent de
    +330 M€, 1,1 % du total.
  - Il faut un carré 2 × 2 par paire, et environ 25 paires.
* Le site affiche, selon le cas, « interaction mesurée » ou « additivité supposée ».

### 5.4 Ce que le navigateur recalcule

| bloc | en JavaScript | ce qu'il faut précalculer |
|---|---|---|
| référence (dette, PIB, solde, taux) | oui, comptabilité | les séries par cadre, une vingtaine de cadres (croissance × taux × dépense) |
| dette mécanique et boucle | oui, exact | impulsions par instrument, par année et par vue ; tables de Mésange et d'IMK (environ 40 nombres) |
| θ, boîte, Monte-Carlo, Sobol | oui, exact | statistiques suffisantes des canaux |
| coût d'une année hors grille | interpolation | la grille, et l'erreur au point témoin |
| chemin annuel d'un curseur | approché | un ratio « chemin annuel / première année reportée » par famille, mesuré sur un chemin par curseur (aujourd'hui 0,24 à 0,29 contre 0,309, soit 5 à 21 % d'écart) |
| déciles | interpolation | 10 × 3 nombres par point |

### 5.5 Le volume et le temps machine

* **Le volume** : environ 1,5 Ko par point, soit **0,6 à 0,7 Mo** en tout, 150 Ko
  compressés, à côté des 615 Ko de pages d'aujourd'hui.

**Le temps.** Les hypothèses : une passe de ménages avec comportements, environ 5 minutes ;
une passe d'entreprises, environ 1 minute ; un chemin, environ 60 minutes.

| poste | calcul | h-machine |
|---|---|---:|
| grille des ménages | 30 curseurs × 7 points × 5 min | 17,5 |
| densification aux seuils | 10 × 6 × 5 min | 5 |
| points témoins | 40 × 5 min | 3,3 |
| paires | 25 × 4 × 5 min | 8,3 |
| entreprises | 15 × 9 × 1 min | 2,3 |
| ratio du chemin annuel | 30 chemins × 60 min | 30 |
| **total** | | **≈ 66** |
| variante mécanique seule (2 min la passe, sans chemins) | | **≈ 14** |

* **Pas de facteur de reprise sous D-335** : un correctif sans effet sur les nombres ne
  relance plus la grille.
* **La durée murale.** Dans le conteneur de 14,3 Go, une passe à la fois, ou deux en
  partageant la référence : environ 3 jours pour 66 h, environ 7 h pour la variante
  mécanique. Sur une machine de 64 Go à huit processus : environ 9 h et 2 h.
* **Les économies** :
  - partager la passe de référence entre tous les points d'un même commit (la moitié du
    temps d'une passe) ;
  - ne pas recalculer la dette du chemin rapide ;
  - sauter les points égaux à un bout de plage (9 plages sur 19) ;
  - mettre en cache les taux marginaux de la loi, ce qui est déjà fait.

### 5.6 Ce que le site affiche

* **À côté de chaque nombre** : son étage, et sa provenance. Celle-ci est « calculé » si le
  curseur est sur un point de la grille, sinon « interpolé, erreur mesurée ≤ x % au point
  témoin ».
* **Les cas préenregistrés et les études sont des crans du curseur** : la valeur du
  candidat, l'article du PLF, le bas et le haut de la plage. À un cran, on affiche le nombre
  du rapport de l'étude, pas l'interpolation, avec le juge, sa tolérance et le lien vers la
  page statique.
* **Le verdict de dette lit les deux persistances**, et il dit la probabilité sous les lois
  déclarées si le Monte-Carlo est retenu.
* **Une réponse absente le reste**, avec sa raison : la dette des points de la CVAE, une
  mesure refusée.
* **Le commit de la grille**, et celui de chaque étude quand ils diffèrent.

**Une décision du propriétaire.** D-304 interdit le script sur le site. Proposition : les
pages d'étude restent sans script, et une page « explorer » à part ne lit que la grille
commitée. La page de l'explorateur a son propre test, et elle ne calcule que l'étage 2.

**La place dans `BUT.md`.** La grille ne fait monter directement aucun des trois chiffres.
Elle sert le livrable n° 2 (les études lisibles) et la question des lecteurs. Sa D-entrée
devra le justifier, ou le propriétaire réécrire la règle de priorité.

---

## 6. Les tests et le processus

### 6.1 Où le temps est allé

| but | commits | durée murale des commits | part du processus | D-entrées |
|---|---:|---|---:|---|
| 11, les programmes | 14 | 4 h 39 | 21 % | D-319 à D-322 |
| 12, la consommation | 11 | 1 h 39 | environ 45 % | D-323 à D-327 |
| 13, les études | 13 | **19 h 52** | **62 %** | D-328 à D-334 |

La « part du processus » compte les préenregistrements, les correctifs de mémoire, les
reprises, les gardes, le lint et les comptes rendus.

**Le but 13 heure par heure** (annexe 6, § 1.3).

* La série nominale vaut 8 à 11 h-machine :
  - 8 premières années, 57 points de plage et 8 chemins de 20 passes ;
  - soit 73 passes au sens de l'étude.
* Il en a coûté **18 à 22 h**, en quatre reprises :
  - **157 passes courtes refaites à l'identique**, 2,5 à 3 h. C'est la règle « une étude se
    lit sur un seul code », après des correctifs qui ne changeaient aucun nombre ;
  - les chemins tués par la mémoire, environ 2,5 h, inévitables tant que la fuite n'était
    pas trouvée ;
  - les diagnostics, profils, gardes vues échouer et mutations, environ 4 h ;
  - deux redémarrages du conteneur.
* Un seul profil de mémoire d'une passe de 2035, fait **avant** la série, aurait sans doute
  évité deux des quatre reprises.

**Sur D-300 à D-334** :

* **Les passes tuées ou relancées** : neuf épisodes, dont un seul a changé un nombre
  (D-307).
* **Les mutants** : environ 260, plus les 230 du balayage de la phase 9.
  - Environ 15 ont survécu ; ils ont donné environ 12 tests de plus.
  - **Aucun n'a révélé un nombre faux.**
* **Ce qui a trouvé les vrais défauts** : les passes elles-mêmes (le « 3 contre 3,0 », les
  fuites), les tests écrits avant le calcul (les cinq écarts de D-324) et la mesure (les
  huit tests rouges de D-309).

**La suite de tests.**

* 2 604 tests, et autant de lignes de tests que de `src` (46 047 contre 46 425).
* 19 tests lourds, 45 minutes en série.
* `make full` dure 100 à 114 minutes. La dernière date du **20 octobre** : aucune depuis,
  en 13 buts.
* Le gros du temps vient des 13 passes de population de `test_api`, `test_population` et
  `test_scenarios` (environ 35 minutes) et des tests de boutons (8 à 34 s chacun). Ils
  tiennent des nombres, et ce qui les accélérerait relève du moteur, pas des règles.

### 6.2 Ce que le code doit suivre pour s'aligner sur D-335

D-335 lève la reprise après un correctif sans effet sur les nombres. Le code l'impose
encore :

| où | ce qu'il fait | à faire |
|---|---|---|
| `etude.py:1065` | refuse une étude dont les rapports sont sur plusieurs commits | accepter N commits si chaque commit postérieur ne change aucun nombre, et que la page le dise |
| `etude.py:954` (plages) | chaque point sur le commit de la première année | même règle, point par point |
| `etude.py:1163` | la page écrit un seul commit | lister les commits, avec le lien vers le diff |
| `etude.py:900` | `launch` refuse dès qu'un rapport existe : une série interrompue ne reprend pas par la commande (au but 13, la reprise s'est faite à la main) | sauter les rapports déjà écrits, refuser seulement l'écrasement |
| `scripts/write_predictif_etude.py:281, 438, 558` | idem pour les études de la phase 9 à 11 | secondaire, seulement si on les rejoue |

**À garder.**

* Le refus d'un `src/` sale et d'un rapport sans `where` : un rapport doit nommer son code.
* Les comparaisons de deux passes, qui doivent tenir sur un seul code : `bruit_c1.py:354`,
  `ecart_ppa.py:297` et `revisions_vieillies.py:155`.
* Les correctifs de mémoire eux-mêmes : `_liberer`, `_isole` et les `gc.collect`.

**Une condition à décider.** Comment vérifie-t-on qu'« un commit ne change aucun
nombre » ? Deux options.

* **Une passe témoin, recommandée.** On rejoue une passe courte d'une des études sur le
  nouveau commit, et elle doit redonner son rapport à l'identique, hors durée. D-329 à
  D-333 l'ont fait cinq fois, avec succès. Le coût est de 2 minutes.
* **Une liste blanche de fichiers.** Plus fragile.

### 6.3 Les tests qui coûtent sans tenir un nombre

* **Un test qui impose un banc.** `tests/test_gardes_phase9.py:137` exige que chaque
  `raise` de `predictif/` soit dans `reports/gardes_phase9.md`, tué. Toute garde ajoutée ou
  réécrite force un balayage de mutations, quelques minutes à 40. **Contredit D-335** : il
  faut figer le rapport ou retirer le test.
* **Les tests qui lisent le source par chaînes**, et qui cassent à un reformatage :
  - `test_etude_programmes.py:194` et `:280`, l'indentation comprise ;
  - `test_capital.py:224` et `test_top_tail.py:147`, l'ordre des blocs du runner ;
  - `test_pfu.py:187`.
* **Les gardes de mémoire** : `test_population.py:1324` et `:1358`.
* **Les tests lourds de rendu** : les six de `test_zero_masked`, environ 5 minutes,
  vérifient des annotations de rendu sur une passe réelle.
* **Les cinq tests chronométrés.**
* **À garder** :
  - les gardes de provenance (`test_standing_rules`, `test_provenance`, l'ERFS) ;
  - les tests de dérive des pages ;
  - les écritures atomiques ;
  - les passes de population qui tiennent la bande, le solveur et l'équilibre des formes.

**Restent ouverts** : une cadence pour `make full`, par exemple une fois avant chaque PR de
but et pas plus, et un profil de mémoire avant toute série de plus de deux heures.

---

## 7. Les décisions du propriétaire

Les huit premières bougent des nombres publiés. Les quatre dernières sont d'organisation.

1. **La persistance de la boucle.** Lire Mésange à 5 et 10 ans, et retirer la falaise
   d'« éteint » ? Ou garder les deux bornes ?
2. **Le multiplicateur.** Le borner à m ≥ 0 et la rétroaction en dessous du coût ? Quelle
   largeur ?
3. **Le taux de la dette ajoutée.** Le taux de marché, ou l'implicite net ?
4. **C1.** Appliquer ε au coin de l'IR seul, comme l'article, ou au coin total ? Sur quelle
   base ? Avec quelle métrique de support, pondérée par la contribution à C1 ? Ce choix
   change le signe de Tondelier.
5. **C5 et C6.** Les câbler, ou retirer leurs lignes des leviers d'IFI ?
6. **Le Monte-Carlo sur θ.** L'ajouter à côté de la boîte, et réécrire « θ n'est pas une
   probabilité » ?
7. **Le cadre des études.** Le garder (1 %, 2 %, 3 %), ou l'aligner sur le PLF 2027, comme
   les cas ?
8. **Le calage unique.** Ouvrir `calibrate.py` avant la phase 7, ou non ?
9. **La passe témoin** comme condition de D-335 dans `etude.py`.
10. **Le sort de `test_gardes_phase9.py:137`**, et des tests de structure.
11. **Le JavaScript.** Une page « explorer » à part, les études restant sans script ?
12. **La règle de priorité.** Le précalcul et la consolidation ne font monter aucun des
    trois chiffres : faut-il les y faire entrer ?

---

## 8. Proposition de but 14

Les juges de l'automne 2026 sont épuisés. Le suivant, l'Institut Montaigne, est attendu au
premier trimestre 2027. D'ici là, le premier chiffre ne bouge pas. Le deuxième (les
études) a dix pages, dont six verdicts de dette portés par des choix de modèle plutôt que
par l'économie. Le moment sert donc à consolider : un moteur dont chaque chemin chiffre la
même chose, des rapports qui gardent assez pour que la dette et θ se refassent sans passe,
et des verdicts qui ne tiennent plus à un coin artificiel.

Ce but ne fait monter aucun des trois chiffres. Il prépare le deuxième, des études justes
et lisibles, et le précalcul qui le rendra interactif. La règle de priorité veut que ce
déblocage soit dit : il l'est ici, et le propriétaire tranche.

```
/goal Le moteur est cohérent de bout en bout, et c'est mergé dans main. Une seule
politique d'imputation sert tous les chemins de passe (API, CLI, scénarios, programme,
étude), et un bouton qui ne peut pas bouger sur un chemin y est refusé, jamais rendu à zéro.
La couche de service quitte api/main.py pour un module que les chemins appellent par des
fonctions publiques. Le cadre des études vit dans un fichier à lui. etude.py suit D-335 :
plusieurs commits sont acceptés quand une passe témoin rejouée sur le nouveau commit redonne
son rapport à l'identique, et une série interrompue reprend. Chaque rapport de chemin écrit,
par année et par vue, les impulsions par instrument et les statistiques des canaux ; une
fonction pure en refait la dette, la boucle et la boîte de θ, égale au chemin du moteur à
1e-9 près. Les décisions du propriétaire sur la persistance, le multiplicateur, le taux de
la dette ajoutée, C1, C5 et C6 sont appliquées, chacune dans sa D-entrée avec son effet
mesuré. Le code mort et les références périmées listés dans docs/AUDIT_BUT14.md sont
retirés ou corrigés. Les dix études sont relancées une fois, sur un commit figé, après un
profil de mémoire, préenregistrées avec leur pronostic, et chaque page dit ce qui a bougé et
pourquoi. Si la calibration doit changer, s'arrêter et demander. Preuve attendue : le
tableau des points de l'audit, fait ou laissé avec sa raison ; les dix études avant et
après ; la sortie verte de make impact et des lourds ; l'URL de la PR et le SHA du merge.
Ou s'arrêter après 60 tours, en disant ce qui manque.
```

**La borne, et l'ordre.**

1. **D'abord ce qui ne change aucun nombre.**
   - L'imputation unique, la couche de service, le fichier du cadre, l'alignement
     d'`etude.py` et le code mort.
   - Chaque pas est prouvé par la passe témoin, sans reprise.
   - Environ 20 tours.
2. **Ensuite les statistiques dans les rapports et la fonction pure.**
   - La fonction pure se teste contre `chaine.run` sur des entrées synthétiques, sans passe.
   - Environ 10 tours.
3. **Ensuite les décisions de modèle**, chacune avec son effet mesuré.
   - Celles de la macro et de θ (points 1, 2, 3, 6 du § 7) se mesurent **sans passe**, une
     fois les statistiques écrites. Seuls C1 et C5 en demandent une.
   - Environ 15 tours.
4. **Enfin une seule série** : les dix études, sur un commit figé.
   - 10 à 12 h-machine, en une fois.
   - Environ 15 tours.

**Ce qui suit, sans l'écrire dans `BUT.md` avant validation.**

* **But 15, l'explorateur à curseurs.** La grille du § 5 et la page « explorer » sans
  serveur de calcul. La variante mécanique coûte environ 14 h-machine ; avec les
  comportements et les chemins, environ 66 h. Il faut la décision sur le JavaScript.
* **But 16, les boutons les moins chers par euro.** L'indexation des pensions et des
  prestations, l'indexation du barème, les cotisations patronales par risque, C5 et C6.
  Ils ouvrent une trentaine de mesures refusées des programmes, à préenregistrer avant le
  juge.
* **Plus tard, des buts entiers** : les successions et le patrimoine des ménages, l'âge de
  la retraite, le calage unique si le propriétaire ouvre `calibrate.py`.
