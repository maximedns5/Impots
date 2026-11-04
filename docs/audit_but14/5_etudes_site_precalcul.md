# Audit — les études, le site, l'API, et une couche de précalcul

Audit en lecture seule de `/home/user/Impots` au commit `3c91f9b` (branche
`claude/but14-audit`, 2026-11-03). Aucun fichier du dépôt n'a été modifié. Aucune passe
lancée : le conteneur n'a pas de venv (`.venv` absent, `openfisca_core` non installé), donc
même `impots site verifier`, pourtant léger, n'a pas tourné. Tout ce qui suit se lit dans le
code, les rapports commités et `docs/DECISIONS.md`. Les chiffres de linéarité et
d'additivité de la partie 4 sont **recalculés ici** depuis les 57 rapports de plage commités,
avec `python3` et `json` seulement.

---

## 1. La chaîne d'une étude : `etudes/<nom>.json` → `docs/etudes/<nom>.md` → `site/*.html`

### 1.1 La définition

`etudes/<nom>.json` a 10 champs autorisés (`src/impots/etude.py:50-51`) : `nom`, `titre`,
`texte` (`plf2027`, `plfss2027` ou `programme`), `preenregistrement` (la D-entrée), `cadre`
(le nom d'une requête sous `etude/`), `millesime_entreprises`, `scenarios` (chacun avec
`miroir` et `titre` facultatifs), plus `programme`, `page` et `rapports` facultatifs. Il y a
10 définitions : `plf2027` (D-289), `plfss2027` (D-302), et 8 `presidentielle_<slug>` (D-328).
Celles des programmes sont **générées** par `scripts/preenregistrer_programmes.py --etudes`
depuis `programmes/<slug>.json`, et un test refuse leur dérive (D-328).

Les 10 définitions ont toutes `"cadre": "ir"`. Les hypothèses (croissance, taux, dépense, θ,
salaires, horizon) sont donc écrites **une seule fois**, dans `etude/ir.json`, qui est la
requête d'exploration de **l'étude IR de la phase 10** (D-237, « Baisse proportionnelle des
taux du barème de l'IR », avec `bounds` et `target`). `Etude.frame()` n'en lit que le cadre
(`etude.py:965-976`), et `lines()` refuse un cadre qui ne soit pas θ½ avec comportements et
boucle (`etude.py:1085-1087`). C'est cohérent mais fragile : les études publiées dépendent
d'un fichier qui porte le nom et la question d'une autre étude. Si l'on touchait
`etude/ir.json` pour la phase 10, les 10 pages dériveraient.

### 1.2 Les passes (`impots etude lancer <nom> --ou "…"`)

`Etude.passes()` (`etude.py:857-868`) donne la liste ordonnée des passes, chacune dans son
propre processus (`launch`, `etude.py:887-917`) :

1. **Une première année par scénario** : `impots etude premiere`. Elle passe par
   `first_year()` (`etude.py:118-141`), qui appelle l'API **en processus** par un
   `TestClient` : `/population/simulate` (comportements et macro demandés), ou
   `/entreprises/simulate`, ou les deux côte à côte pour une part « mixte »
   (`MIXTE`, `etude.py:89`, `first_year_payload` `:92-115`).
2. **Trois points par plage** (programmes seulement) : `impots etude plage`. Cela donne bas,
   valeur du candidat et haut (`POINTS`, `etude.py:54`). Chaque point est la mesure seule,
   mécanique, par le chemin rapide `POST /predictif/simulate` (`plage_request` `:144-171`,
   `plage` `:177-212`). Quand le droit des entreprises bouge dans l'horizon (la CVAE),
   `dette_absente` (`:215-229`) bascule sur `/entreprises/simulate` en 2026 : le coût seul,
   sans dette (D-254).
3. **Un chemin annuel par scénario** : `impots predictif`. Il va de 2026 à 2035, dans les
   deux vues (vieillie et figée), sous les deux persistances, avec la boîte de θ. La commande
   est construite par `scripts/etude_annuelle.py` (`argv` `:90`), chargé dynamiquement
   (`_script`, `etude.py:78-86`). Chaque passe-année du chemin tourne dans un processus neuf
   (`cli._isole`, `population/cli.py:1528`, D-331). Les caches sont vidés avant (`_liberer`,
   `:1544`, D-330).

Les comptes du but 13 (D-328, vérifiés dans `reports/etudes/*/plages/`) :

| étude | premières années | points de plage | chemins |
|---|---:|---:|---:|
| Attal | 1 (mixte) | 6 | 1 |
| Labib | 1 | 9 | 1 |
| Le Pen | 1 | 6 | 1 |
| Lisnard | 1 (mixte) | 18 | 1 |
| Mélenchon | 1 | 3 | 1 |
| Retailleau | 1 (mixte) | 9 | 1 |
| Roussel | 1 | 3 | 1 |
| Tondelier | 1 | 3 | 1 |
| **total** | **8** | **57** (19 plages, dont 15 points sans dette) | **8** |

Cela fait **73 passes** pour le but 13. Un chemin, c'est 10 années × 2 vues = 20 passes de
population, plus la boîte de θ, évaluée sur les mêmes entrées : les coins de θ ne sont pas
des passes en plus (`comportement.evaluate`, `predictif/comportement.py:56-66`). Le PLF 2027
a 3 + 3 passes, le PLFSS 2027 2 + 2.

**Les gardes avant de lancer** (`preregistered`, `etude.py:870-885` ; `launch`) :
- refus si `src/` est modifié ;
- refus si la D-entrée de préenregistrement n'est pas dans `HEAD:docs/DECISIONS.md` ;
- refus si aucune branche distante ne porte le commit ;
- refus si un rapport est déjà là.

`IMPOTS_AUTH=aucune` et le millésime d'entreprises sont posés pour les sous-processus.

### 1.3 Les rapports commités

Rapports par défaut sous `reports/etudes/<nom>/` (77 fichiers commités), sauf le PLF, qui
écrit sous `reports/etude_plf2027/` (champ `rapports`). Chaque rapport porte `commit`,
`dirty`, `where` et `computed`. **Aucune durée n'est enregistrée dans les rapports.**

| étude | commit des rapports | date |
|---|---|---|
| plf2027 | `02fd623` | 2026-10-28 |
| plfss2027 | `b73ffcf` | 2026-10-29 |
| 6 programmes | `82f4926` | 2026-11-02 |
| Lisnard, Tondelier | `c36984d` | 2026-11-03 |

Les rapports pèsent 1,3 Mo (`reports/etudes/`). Le chemin de Lisnard fait à lui seul 300 Ko.

### 1.4 La page et le test de dérive

- `impots etude ecrire <nom>` produit `render(load())` (`etude.py:1068-1072`), où `lines()`
  rend chaque nombre comme un jeton de `Nombres` qui porte son étage (`etude.py:341-380`). Un
  montant sans étage est refusé.
- `Etude.load()` (`etude.py:978-1065`) refuse un rapport manquant ou en trop, un rapport sans
  commit ou sur un `src/` sale, ou sans `where`. Il refuse aussi une première année dont la
  requête n'est pas **celle que les scénarios donnent aujourd'hui** (`:1011-1015`), un chemin
  hors du cadre (`:1037-1043`), et des rapports de plusieurs commits (`:1060-1063`).
  `load_plages` (`:941-963`) recalcule `plage_request` **depuis `programmes/*.json` et
  `etude/ir.json` d'aujourd'hui**, et compare.
- `Etude.drift()` (`etude.py:1365-1377`) re-rend la page depuis les rapports et la compare au
  texte commité (`difference`, `:782-794`, qui donne la ligne et le contexte). Les tests
  `tests/test_etude.py:31-34` (une instance par définition) et `:52-57` (la page modifiée,
  vue échouer) en sont la garde.
- Le site : `impots site construire` donne `site.build()` (`src/impots/site.py:194-230`), qui
  **re-vérifie la dérive de chaque étude** (`:199-201`) et prend le texte ligne pour ligne
  (`Etude.lines`). Il refuse tout `<script` (`:225-227`). `site.drift()` (`:246-258`) compare
  chaque fichier, et `tests/test_site.py:39` le tient. Le site fait 14 fichiers, 615 Ko :
  `index.html`, `presidentielle.html` (les 24 candidats), 10 pages d'étude, `style.css` et
  `.nojekyll`.
- Le workflow `.github/workflows/site.yml` n'a qu'un `workflow_dispatch`. Il lance
  `impots site verifier`, sans données ni passe, et ne publie sur Pages que si
  `vars.SITE_PUBLIE == 'oui'`. Comme `test.yml` depuis D-212, il ne tourne jamais tout seul :
  le dépôt n'a plus de runner.

**Ce que le test de dérive garantit, et ce qu'il ne garantit pas.** Il garantit que la page
est le rendu des rapports par le code de rendu d'aujourd'hui, et que les rapports
correspondent aux définitions d'aujourd'hui (scénarios, programmes, cadre). Il ne garantit
pas que les rapports seraient les mêmes si l'on rechiffrait aujourd'hui : aucun nombre n'est
recalculé (voir 5.2).

---

## 2. Cohérence de l'architecture

### 2.1 Combien de chemins produisent un chiffrage

Le point d'entrée `impots` est `impots.population.cli:main` (`pyproject.toml:43`). Toute la
CLI, 13 groupes, vit dans `src/impots/population/cli.py`. Les chemins qui produisent un coût :

| # | chemin | ce qu'il appelle | où |
|---|---|---|---|
| 1 | `impots population run` | `runner.run` direct | `cli.py` `cmd_run` |
| 2 | `impots entreprises run` | `firm_runner.run` | `cli.py:582` |
| 3 | `impots scenario compare / solve` | `scenarios.py`, qui lit `api.main._population_frame` et `QUICK_TIER_HOUSEHOLDS` | `scenarios.py:594-655` |
| 4 | `impots chiffrage register [entreprises]` | runner direct / `firm_runner` | `preregistration.py:596`, `cli.py` |
| 5 | `impots fiche` | `TestClient(app).post("/population/simulate")` | `cli.py:1164-1173` |
| 6 | `impots trajectoire` | trajectoires | `cli.py` `cmd_trajectoire` |
| 7 | `impots predictif` (chemin annuel) | `api._price_first_year` par année, isolé | `cli.py:1413-1481` |
| 8 | `impots exploration` | `explorer` + `api._price_first_year` | `cli.py:1714-1770` |
| 9 | `impots etude premiere / plage` | `TestClient` sur `/population`, `/entreprises`, `/predictif/simulate` | `etude.py:118-212` |
| 10 | `impots programme` | `api.main.predictif_simulate` appelé comme fonction | `programme_chiffrage.py:110-118` |
| 11 | l'API : `/simulate`, `/population/simulate`, `/entreprises/simulate`, `/predictif/simulate` | | `api/main.py:240, 915, 1123, 1647` |
| 12 | des scripts sur mesure qui appellent `runner.run` eux-mêmes | `verify_ecart_art2.py:90,138`, `verify_pensions_art3.py:114,133`, `revisions_vieillies.py:91`, `bruit_c1.py`, `c1_quatre.py`, `accuracy_budget.py`, `verifier_consommation.py`… | `scripts/` |

Cela fait **une dizaine de chemins**. Il y a pourtant un vrai point de convergence :
`api/main.py` porte la couche de service (`_price_first_year` `:1493`, `_price_households`
`:1538`, `_macro` `:602`, `_narrow_band` `:473`). Les chemins 5, 7, 8, 9 et 10 passent par
elle. Mais ils y entrent par des **fonctions privées** : 5 appels à `api._price_first_year`,
4 à `_first_year_request`, 3 à `_predictif_hypotheses` et 3 à `_population_frame` depuis
`src/` et `scripts/` (grep). Les chemins 1, 2, 4 et les scripts de vérification passent
directement par `runner.run`, sans l'API. Le chemin rapide (`/predictif/simulate`) et le
chemin annuel (`impots predictif`) sont deux mises en œuvre distinctes de la dette.

**Doublons à signaler** :
- **Deux façons de chiffrer un programme.** `impots programme` (chemin rapide, rapports
  `reports/programmes/*.json`) et `impots etude` sur `presidentielle_*` (première année, plages
  et chemin annuel).
- **Deux systèmes d'étude.** `impots etude` produit `docs/etudes/`, et
  `scripts/write_predictif_etude.py` (**2 514 lignes**, un script, pas un module) rend
  `docs/PREDICTIF_ETUDE.md` (997 lignes) depuis les explorations de la phase 10. Le second
  n'est pas sur le site.
- **Deux « explorateurs ».** `explorer.py` (phase 8, la recherche de paquets) et
  `predictif/exploration.py`. Ce n'est pas un doublon : le second importe `Evaluation` du
  premier (`predictif/exploration.py:39`). `emtr_explorer.py` est une troisième chose
  (`impots emtr-explorer`).

### 2.2 Modules et scripts morts

Les modules du pan sont tous importés par `src`, un script ou un test. **Aucun n'est mort.**

| module | importé par `src` | par des tests |
|---|---:|---:|
| `accuracy_behavioural` | 0 | `scripts/accuracy_budget.py` + 1 test |
| `accuracy_cases` | 0 | 2 tests |
| `instrument_coverage` | 0 | 2 tests (+ `write_instrument_coverage.py`) |
| `dependances` | 0 | 2 tests |
| `identifiants` | 6 | |
| `guards` | 6 | 11 |

Les scripts sont tous des outils ponctuels d'une D-entrée. Aucun n'est appelé par le
`Makefile`, sauf `ci_local`. Les workflows appellent `check_no_data_committed`,
`verify_openfisca` et `verify_population_engine`. Sont cités seulement dans `docs/`, sans
test ni appel :
- `accuracy_budget` ;
- `gate_l1_top_tail` ;
- `verify_c2_emploi` ;
- `verify_ecart_art2` ;
- `verify_eec`, `verify_erfs` ;
- `verify_firm_engine` ;
- `verify_mesange_solde` ;
- `verify_pensions_art3`, `verify_pensions_foyers`, `verify_pensions_masse` ;
- `verify_perimetre`, `verify_stat39`.

Ce sont des portes de phases closes, « publiées à côté des specs » (`pyproject.toml:107`).
Mortes au sens strict : non. Archives exécutables : oui.

`scripts/etude_plf2027.py` (60 lignes) ne fait plus qu'écrire le scénario de l'art. 15. Son
docstring le dit, et D-301 a remplacé le reste.

**Des références périmées.** `docs/BUT.md:171` et `docs/STATE_AND_NEXT.md:279` citent
`docs/ETUDE_PLF2027.md`, et D-289 cite `scripts/write_etude_plf2027.py` : ni l'un ni l'autre
n'existe plus. `tests/test_write_etude_plf2027.py` reste, comme fournisseur de gabarits pour
`tests/test_etude.py:23`, sous un nom qui n'est plus le sien.

Seize rapports à la racine de `reports/` n'ont pas de référence littérale dans le code. La
plupart sont lus par motif : `TRAJECTORIES.glob("predictif_*.json" | "exploration_*.json" |
"emtr_*.json")`, `api/main.py:1253, 1276, 1305`, et l'interface les affiche. Les
explorations `courbe_*` sont lues par `write_predictif_etude.py`. Restent sans lecteur
trouvé : `fiche_allegement_2smic.md`, `fiche_rsa_700.md`, `full_pass_durations.md`,
`full_pass_log.md`. Ce sont des archives.

### 2.3 L'interface `ui/index.html` (3 524 lignes)

**Elle parle à l'API.** `const API = location.origin` (`ui/index.html:1382`). Les `fetch`
vont vers `/simulate`, `/population/baseline|simulate`, `/entreprises/baseline|simulate`,
`/predictif/simulate`, `/predictif[/{nom}]` et `/explorations[/{nom}]` (`:2219-3260`).
L'API la sert à `/` (`api/main.py:1806-1816`). Ouverte depuis le disque, l'origine est
`null`, refusée depuis D-295. `ui/check.mjs` la teste à la main, hors CI (D-003).

**Elle est en retard.** Dernier commit : `b26092a`, 2026-10-29 (D-295). Il manque
**25 boutons** du `ReformSpec` (88 champs, `api/schemas.py:751`) et de `FirmReformSpec` :

| boutons absents | où ils servent |
|---|---|
| `abattement_pensions_plafond` | **l'art. 3 du PLF 2027** |
| `cotisations_salariales_retraite_echelle` | **Attal, Retailleau** |
| `tva_*`, `tva_postes`, `accise_*` | **Le Pen, Roussel, Labib**, but 12 |
| `qf_parts_enf*`, `plafond_qf_parent_isole` | **Le Pen, Lisnard** |
| `cebge_seuils_et_taux` | **l'art. 15 du PLF** |
| `ij_*`, `csg_ij_taux` | but 8 |
| `ppa_revalorisation_*`, `al_revalorisation_*` | but 9 et 10 |
| `cs_taux`, `cir_taux`, `ifi_bareme`, `csg_capital_taux_global`… | |

Elle ne connaît ni les études, ni les programmes, ni le site. Aucune des réformes publiées
sur le site ne se rejoue donc depuis l'interface.

### 2.4 Le site

Il est en HTML pur, sans script, garanti par `site.py:225-227` et le test
`test_no_page_runs_a_script`. Le texte est celui de l'étude, à la ligne près. Chaque nombre
porte un badge d'étage relié à la légende (`_badge`, `site.py:47-55`). Une étude non lancée
est listée « préenregistrée », sans page. **Le site ne calcule rien** (`site.py:11-13`) : une
couche à curseurs en JavaScript contredit ce contrat de D-304, et il faudrait une nouvelle
décision du propriétaire et une nouvelle D-entrée (voir 4.8).

### 2.5 La taille des gros modules

**`api/schemas.py`, 2 700 lignes, 85 classes.** C'est le format d'échange, « source unique
de vérité » (docstring `:1-12`), sans FastAPI, parce que le moteur l'importe.
- `ReformSpec` fait à lui seul **385 lignes et 88 boutons**, chacun avec son type, ses
  bornes et sa doc. Les validateurs (25 `field_validator`/`model_validator`) gardent les
  formes : le barème jusqu'à 6 tranches, les refus de forme.
- `HouseholdInput` (156 lignes), `Adult` (107) et `HandicapEnfant` (93) décrivent le ménage
  type.
- Les réponses de 12 points d'API : `PredictifReportResponse` 90, `ExplorationRequest` 88,
  `PredictifResponse` 81, `ResultRows` 102, `Niches` 69…
- 216 `Field(`, environ 340 lignes de docstring ou de commentaires.

Le volume est de la description, pas de la logique. Mais le fichier mêle requête, réponse et
quelques règles métier (`_refuse_a_law_the_carry_cannot_see`, que `etude.py:219` importe).
On pourrait le découper par domaine (ménage, population, entreprises, prédictif,
exploration) sans rien changer au fond.

**`population/cli.py`, 2 300 lignes, 48 fonctions.** C'est toute la CLI `impots`, pas
seulement la population. `build_parser` fait **415 lignes**. `cmd_predictif` fait 204 lignes,
avec la logique mémoire de D-330 et D-331 (`_isole`, `_liberer`). Viennent ensuite
`cmd_trajectoire` (115), `cmd_exploration` (106) et `cmd_chiffrage_register_entreprises`
(84). Sa place sous `population/` est historique (la phase 1). Elle explique que
`etude.py:860` lance `-m impots.population.cli etude …`.

**`api/main.py`, 1 816 lignes, 62 fonctions.** Elle contient les points d'API, mais surtout
la **couche de service** dont dépendent la CLI et les scripts : `predictif_simulate` (156
lignes), `_macro` (86), `_narrow_band` (85), `_price_households`, `_employer_inputs`,
`_price_first_year`. Cette couche n'a pas de module à elle, d'où les appels privés relevés
en 2.1.

**`etude.py`, 1 495 lignes.** Le texte de chaque type de document y est codé en dur :
`_PLF2027` (`:431`), `_PLFSS2027` (`:481`), `_Programme` (`:559`) et
`TEXTES = {"plf2027", "plfss2027", "programme"}` (`:769-770`). Une étude du PLF 2028
demandera une classe de plus, en Python : « une étude par commande » ne vaut que pour un
type de texte déjà connu.

Les autres modules du pan : `plf_coverage.py` 1 417, `preregistration.py` 731,
`explorer.py` 550, `fiche.py` 480, `reporting.py` 475, `guards.py` 436, `accuracy_cases.py`
405, `programmes.py` 370, `accuracy.py` 328, `site.py` 278, `securite.py` 275,
`accuracy_behavioural.py` 241, `emtr_explorer.py` 227, `instrument_coverage.py` 218,
`programme_chiffrage.py` 146, `dependances.py` 123, `identifiants.py` 36.

---

## 3. Le coût observé des passes

Les rapports ne gardent aucune durée. Ce qui suit vient des D-entrées.

| quoi | durée | mémoire | source |
|---|---|---|---|
| passe de population au palier complet (20 000 ménages, `QUICK_TIER_HOUSEHOLDS`, `schemas.py:1368`) | ~2 min (« quatre passes rapides, 8 min 7 s ») | 6 à 7 Go | D-235 (`DECISIONS.md:17328`), D-309 |
| une passe-année du chemin annuel | 90 à 130 s, toutes reprises | 6,1 à 6,2 Go | D-236 (`:17528-17531`) |
| la même, en 2035 vieillie, avec comportements, taux marginaux sans cache | **490 s** (~8 min) | pic à 7,4 Go | D-332 |
| `/population/simulate`, un appel | 30 s à 1 min 30 | | `DECISIONS.md:8574` (phase 8) |
| un chemin d'exploration de quatre ans | 8 passes en 14 min | 6,1 Go | `STATE_AND_NEXT.md:716` |
| un chemin de dix ans (estimé, D-237) | « 16 chemins demanderaient 11 h », soit ~40 min | | `DECISIONS.md:21409-21414` |
| un chemin de dix ans, annoncé par D-328 | « une demi-heure environ » | | D-328 |
| chemins du PLFSS (2 premières années et 2 chemins) | **1 h 23** en tout | | `STATE_AND_NEXT.md:142` |
| chemin d'Attal (but 13) | n.d. | pic à 11,8 Go | D-331 |
| chemin de Tondelier | **86 min** (une tentative tuée après 82 min) | pic du conteneur à 8,4 Go après D-332, 13,9 Go avant | D-332, D-333 |
| chemin de Lisnard | **96 min** | idem | D-333 |
| entreprises seules, CVAE sur dix ans | **55 s**, sans passe de population | | `DECISIONS.md:21192` |
| un ménage, une réforme neuve, palier complet | 12,3 s → **6,2 s** après la greffe | 314 Mo | D-311 |
| test lourd, 4 passes de population | 516 s (`full_pass_durations.md`) ; 6 min 30 après D-334 | 6,7 Go | D-334 |
| `make full` | 1 h 47 (10-14) ; 1 h 43 (10-20, chez le propriétaire) | | `full_pass_durations.md`, `DECISIONS.md:17144` |

**Le nombre total de passes du but 13.** La série nominale est de **73 passes** : 8
premières années, 57 points, 8 chemins de 20 passes-années, soit 8 + 57 + 160 = 225 passes
de population au sens strict, moins les 15 points des entreprises, qui n'en lancent pas.
Réellement exécuté, d'après D-329 à D-333 :

| essai | ce qui a tourné |
|---|---|
| sur `3b02ae4` | 46 passes courtes, puis l'arrêt (le bug de la greffe, « 3 » contre « 3.0 ») |
| sur `07783a4` | 65 passes courtes, puis le chemin d'Attal tué à 13,9 Go |
| sur `82f4926` | 65 courtes ; 5 chemins au bout, 2 tués (Lisnard après 10 min, Tondelier après 17 min) |
| sur `ac36508` | 23 courtes ; un redémarrage du conteneur ; Tondelier tué après 82 min |
| sur `c36984d` | 23 courtes ; un redémarrage ; Tondelier 86 min, Lisnard 96 min |

Soit **environ 222 passes courtes et 11 chemins lancés (8 utiles)**. Mon estimation, avec
des hypothèses explicites (passe courte 2 à 4 min, chemin d'environ 45 min hors Tondelier et
Lisnard, chemins tués comptés à leur durée) :

| poste | calcul | heures |
|---|---|---:|
| passes courtes | 222 × 3 min | ≈ 11 |
| chemins utiles | 6 × 45 + 86 + 96 min | ≈ 7,5 |
| chemins tués | ≈ 1 + 0,2 + 0,3 + 1,4 | ≈ 3 |
| **total** | | **≈ 20 à 22 h-machine** |

La série nominale seule fait **≈ 10 à 11 h**. Le surcoût vient de la règle « une étude se
lit sur un seul code » : chaque correctif relance tout. Il faut aussi compter la mémoire :
un seul processus de 6 à 13 Go dans un conteneur de 14 Go, d'où une passe à la fois.

---

## 4. Proposition : une couche de précalcul pour un site statique à curseurs

### 4.1 Ce que les rapports commités montrent déjà (mesuré ici)

**a) La dette du chemin rapide est exactement linéaire en le coût.** Sur les 35 points de
plage qui ont un coût non nul et une dette, le rapport Δb(année) / coût est le même au
1e-17 près. Il vaut `[0,000325 ; 0,000645 ; … ; 0,003089]` par Md€ de 2026, de 2026 à 2035,
soit **+0,309 pt de PIB en 2035 par Md€** dans le cadre `ir`. Le chemin rapide n'est donc
qu'une multiplication : `etude.plage` n'apporte aucune information de dette au-delà du coût.
Ce vecteur se calcule une fois par cadre, et le navigateur peut le faire lui-même.

**b) Un taux proportionnel donne un coût linéaire.** On interpole le point du candidat entre
le bas et le haut, et on regarde l'écart au coût calculé :

| plage | écart à l'interpolation |
|---|---|
| tranche à 60 % de l'IR (Tondelier), 45 → 60 → 67,5 % | −6,9378 Md€ par point de taux aux deux bouts : linéaire à 0,001 % près |
| TVA énergie (Le Pen), TVA carburants (Roussel) | 0,000 Md€ |
| échelle des cotisations retraite (Attal, 0 → 0,22 → 1) | 0,103 sur 76,9 Md€ (0,13 %) |
| échelle des cotisations retraite (Retailleau) | 0,009 Md€ |
| CSG déductible (Lisnard) | 0,019 sur 24,6 Md€ (0,08 %) |
| CSG imposable (Lisnard) | −0,005 Md€ |

**c) Un seuil ou une part ne le sont pas.**

| plage | écart | ce qu'il dit |
|---|---|---|
| plafond de la réduction générale (Mélenchon, 1,5 → 2 → 3 SMIC) : −29,18 / −9,52 / 0 Md€ | **9,9 Md€ sur 9,5** | non linéaire |
| parts de quotient pour le 2e enfant (Le Pen, 0,5 → 1 → 1,25) | 0,119 sur 2,9 Md€ (**4 %**) | |
| plafond du quotient (Lisnard) | 0,88 → 5,95 → 5,95 | **sature** |

**d) L'additivité dans un programme** (coût vieilli de 2026 de la part, contre la somme des
points « candidat » de chaque mesure seule) :
- **Le Pen** (TVA énergie + part pleine du 2e enfant) : 11 625 133 664,75 + 2 916 033 217,45
  = 14 541 166 882,20 €, **exactement** le coût du programme. Il n'y a aucune interaction.
- **Lisnard** (CSG 6,6 % + déplafonnement du quotient) : 24,605 + 5,953 = 30,558 Md€, contre
  **30,888** pour la part des ménages. L'interaction vaut **+330 M€** : 1,1 % du total, 5,5 %
  de la mesure du quotient. C'est le passage par l'assiette de l'IR (la CSG déductible
  change le revenu imposable).
- Les parts mixtes (Attal, Retailleau, Lisnard) additionnent la couche des ménages et celle
  des entreprises **par construction** : deux appels (`MIXTE`).

**e) Une incohérence de convention à corriger avant le précalcul.** Les points d'entreprises
viennent de `/entreprises/simulate` (non vieilli). Le chemin, lui, porte la couche des
entreprises vieillie (Lisnard : 8,571 contre 9,320 Md€). Le coût d'un point « candidat » des
ménages (vieilli 2026, palier rapide) n'est pas non plus celui de la première année publiée
(population 2024 non vieillie) : Labib 21,17 contre 22,89 Md€ (−7,5 %), Attal 76,92 + 3,28
contre 73,14 + 3,28. La page le dit (D-328). Un lecteur à curseurs verrait deux coûts au
même point : il faut **une seule convention** dans la grille.

### 4.2 Les familles de boutons et leur grille

Il y a 88 champs `ReformSpec` et 15 `FirmReformSpec`. On peut les regrouper en **une
quarantaine de curseurs** présentables :

| famille (boutons) | forme | grille proposée | interpolation, et erreur attendue |
|---|---|---|---|
| IR : échelle du barème (`ir_bareme_echelle`), taux de chaque tranche (×5) | taux proportionnel | 5 points : la loi, ±1 et ±3 pts, plus les bouts de plage | linéaire ; < 0,01 % mesuré (Tondelier) |
| IR : seuils des tranches (×5), décote (seuils, taux), plafond du quotient, parts | seuil ou part | 9 points, plus denses près de la loi | spline monotone par morceaux ; 4 % à 3 points (part du 2e enfant), à remesurer à 9 |
| CSG activité (imposable, déductible), CSG pensions, capital, prélèvement de solidarité, PFU | taux | 5 points | linéaire ; < 0,1 % (Lisnard) |
| cotisations : échelle de la retraite salariale | échelle | 5 points | linéaire ; 0,13 % (Attal) |
| allègements : plafond et `t_min`/`t_delta` de la réduction générale, bandeaux maladie et famille | **seuil** de la courbe | **11 points** (1,3 à 3,5 SMIC par 0,2), plus `t_delta` à 5 | non linéaire : 9,9 Md€ d'écart à 3 points ; interpolation par morceaux, erreur à mesurer sur des points témoins |
| prestations : RSA, prime d'activité (montant, pente), BMAF, AF, AL | montant en € | 5 points | presque linéaire (recours fixe) ; à mesurer |
| TVA : 4 taux, `tva_postes` (≈ 12 postes) | taux, volumes fixes | 3 points par taux ou poste | linéaire exact (0,000) |
| accises : gazole, essence, fioul, électricité, gaz | €/unité, volumes fixes | 3 points | linéaire ; **terme croisé TVA × accise** sur un même poste (la TVA porte sur le prix accise comprise) : bilinéaire, exact avec 4 points |
| niches (dons, emploi à domicile, garde, plafond global) | taux et plafond | 5 + 5 points | taux linéaire, plafond par morceaux |
| IFI : barème, décote, abattement | taux et seuils | 5 à 7 points | idem |
| IS : taux normal, taux réduit et son plafond | taux et seuil | 5 points | `/entreprises/simulate` : **55 s le chemin de dix ans**, donc on peut être dense |
| CVAE (échelle, taux, dégrèvement), C3S, CS, CIR, CEBGE | taux et échelle | 5 à 9 points | idem ; la CVAE n'a pas de chemin rapide (D-254), le chemin annuel des entreprises suffit et coûte peu |

**Contrôle gratuit** : le point « loi » doit rendre 0 €. C'est le défaut de la greffe de
D-329, que cette grille aurait vu tout de suite.

**Mesure de l'erreur d'interpolation.** Pour chaque bouton, calculer un **point témoin**
hors grille (le milieu du plus grand intervalle), noter l'écart entre l'interpolation et le
calcul, et publier cet écart à côté du curseur. Ce point témoin se préenregistre comme une
tolérance (« interpolation à moins de x % »), avant le calcul.

### 4.3 La combinaison dans un programme

- **Additif par construction** : ménages + entreprises (deux appels) ; consommation (TVA et
  accises) + revenus. La consommation est imputée à volumes fixes, et Le Pen le montre au
  centime.
- **Interactions à mesurer** : toutes les paires qui touchent l'assiette ou le calcul de
  l'IR et des prestations sous condition de ressources. Ce sont : CSG déductible × barème et
  quotient (mesuré : +1,1 %) ; cotisations × CSG × IR ; prime d'activité × RSA × AL ;
  allègements × cotisations ; décote × barème. Pour chaque paire, un carré 2 × 2 (les deux
  bouts) donne le terme croisé. Comptons **≈ 25 paires × 4 points**. Le site ajoute le terme
  croisé, bilinéaire, et affiche « interaction mesurée sur n paires ; les autres paires
  supposées additives ».
- **Ce qui reste à faire tourner** : les programmes des candidats et les articles des PLF,
  combinaisons préenregistrées. On les calcule exactement par le chemin complet, comme
  aujourd'hui. La grille sert l'exploration, pas la publication.

### 4.4 Ce que le navigateur peut recalculer

| bloc | calculable en JS ? | ce qu'il faut précalculer |
|---|---|---|
| dette du chemin rapide (mécanique) | **oui, exactement** : Δb(t) = coût × v(t) | le vecteur `v` par cadre (10 nombres) ; un cadre par combinaison croissance × taux × dépense proposée (3 × 3 × 2 = 18 cadres, ~2 Ko) |
| chemin de référence (dette, PIB, taux, solde) | oui, c'est de la comptabilité (`dette/path.project`, `predictif/chaine.py:356-386`) | les séries annuelles de référence par cadre |
| θ : les comportements | **oui, si** on stocke par point les recettes de chaque canal à θ ∈ {0, ½, 1} | p(θ) est linéaire par morceaux autour de ½ (`predictif/theta.py`, docstring) ; si chaque canal est linéaire en son paramètre, 3 valeurs suffisent ; la boîte est le min/max sur les coins (`comportement.py:64-66`), calculable en JS sur des canaux additifs |
| boucle macro (multiplicateur, persistance « éteint » ou « tenu ») | oui, en première approximation : réponses impulsionnelles linéaires de Mésange | le vecteur IRF par persistance et les coins du multiplicateur |
| coût vieilli année par année (chemin annuel) | **non** : droit qui bouge (CVAE 2030), revalorisation, vieillissement | un **ratio chemin annuel / chemin rapide** par famille de boutons, mesuré sur un point par bouton ; D-333 donne 0,243 à 0,292 pt/Md€ au chemin complet, contre 0,309 au rapide (écart de 5 à 21 %) |
| déciles, gagnants et perdants | par interpolation des 10 déciles aux points de la grille | 10 × 3 nombres par point |

Avertissement à écrire sur la page : **le signe de la dette peut se retourner** sous les
comportements (Tondelier : recette mécanique, dette en hausse, D-333) et sous le
multiplicateur tenu (Attal : +20,3 pt à θ½, −6,9 pt au coin). On ne peut donc pas déduire la
dette du coût mécanique seul. Le JS doit porter les canaux, pas un simple ratio.

### 4.5 Le volume

Par point de grille : le coût dans deux vues, 10 déciles × 3, la bande (3 nombres),
≈ 6 canaux × 3 θ, l'étage, le commit. Soit **≈ 1,5 Ko** en JSON.

| poste | taille |
|---|---|
| 40 curseurs × ~7 points ≈ 280 points, avec leurs points témoins | ≈ 450 Ko |
| 25 paires × 4 points | ≈ 150 Ko |
| 18 cadres de référence × 10 ans × ~8 séries, plus les IRF | ≈ 30 Ko |
| **total** | **≈ 0,6 à 0,7 Mo**, **≈ 120 à 150 Ko** compressé |

Les pages HTML actuelles (615 Ko) restent à côté.

### 4.6 Le temps machine (hypothèses explicites)

Hypothèses : une passe rapide de population avec comportements et θ ≈ **5 min** (D-332 :
490 s pour une passe-année avec taux marginaux à froid ; 2 min sans comportements, D-235).
Une passe des entreprises ≈ **1 min**. Un chemin annuel ≈ **45 à 95 min** (D-333).
Pic à 7 Go par processus.

| poste | calcul | heures-machine |
|---|---|---:|
| ménages, grille de base | 30 curseurs × 7 points × 5 min | 17,5 |
| seuils, densification | 10 curseurs × 6 points de plus × 5 min | 5 |
| points témoins | 40 × 1 × 5 min | 3,3 |
| paires | 25 × 4 × 5 min | 8,3 |
| entreprises, grille et chemins annuels | 15 curseurs × 9 points × 1 min | 2,3 |
| ratio chemin annuel / chemin rapide | 30 curseurs ménages × 1 chemin × 60 min | 30 |
| cadres de référence | comptabilité, sans population | ≈ 0 |
| **total** | | **≈ 66 h-machine** |

Variante légère, mécanique seule (2 min la passe, sans les chemins annuels) : 280 × 2 + 100
× 2 + 40 × 2 min ≈ **14 h**. Variante lourde (deux chemins annuels par curseur, aux deux
bouts) : **≈ 96 h**.

**Facteur de reprise.** Le but 13 a coûté 2 fois sa série nominale (partie 3). Comptons
**≈ 130 h** pour un premier précalcul complet, et 66 h à chaque nouvelle version du moteur,
puisque la règle « une étude, un code » invalide la grille à chaque correctif. Avec un
processus à la fois dans le conteneur actuel (14 Go), cela fait 3 à 6 jours d'horloge. Sur
une machine de 64 Go à 8 processus, ≈ 9 à 17 h.

**Les économies évidentes** :
- ne pas recalculer la dette du chemin rapide (4.1 a) ;
- passer les points « candidat » égaux à un bout (9 plages sur 19 en ont deux identiques) ;
- calculer les entreprises densément, elles ne coûtent rien ;
- partager la référence entre tous les points d'un même commit (la passe de référence est la
  moitié du temps d'une passe).

### 4.7 Ce que la page affiche : précision et cas préenregistrés

- **À côté de chaque nombre** : l'étage (L0 à L4, le badge actuel, `site.py:47-55`) et la
  **provenance** : « calculé » (le curseur est sur un point de la grille) ou « interpolé,
  erreur mesurée ≤ x % au point témoin ». Pour une combinaison : « additivité supposée » ou
  « interaction mesurée ».
- **Les cas préenregistrés** apparaissent comme des **crans** sur le curseur : la valeur du
  candidat, l'article du PLF, le bas et le haut de la plage du programme. À un cran, le
  nombre affiché est celui du rapport de l'étude, pas l'interpolation. Le juge (évaluation
  préalable, Institut Montaigne) et sa tolérance sont dits à côté, avec le lien vers la page
  d'étude statique.
- **Le commit** de la grille, et celui de chaque étude, quand ils diffèrent (voir 5.2).
- **Une réponse absente** reste dite absente avec sa raison : la dette des points CVAE
  (D-254), les mesures refusées par porte.

### 4.8 Ce qui demande une décision du propriétaire

1. **Du JavaScript sur le site.** Aujourd'hui, `site.build` refuse tout `<script`
   (`site.py:225-227`), ce qui est le contrat de D-304. Proposition : garder les pages
   d'étude sans script, et ajouter une page « explorer » à part, avec son propre test, qui ne
   lit que la grille commitée.
2. **La règle du commit unique.** Une grille de 66 h ne se tient pas sur un seul commit si le
   moteur bouge. Soit on fige le moteur pendant la passe (un worktree figé, comme le but
   13), soit on permet un commit par famille de curseurs, et la page le dit.
3. **Le préenregistrement.** Il faut une D-entrée pour la grille, avec la tolérance
   d'interpolation de chaque famille avant le calcul. C'est la règle de `CLAUDE.md`.
4. **La place dans `BUT.md`.** Ce travail ne fait monter directement aucun des trois chiffres
   de la règle de priorité. Il rend lisibles les études, sans en publier de nouvelles. Sa
   D-entrée doit le justifier.

---

## 5. Cohérence entre études, et rapports non régénérables

### 5.1 Ce qui est écrit une fois

- **Le cadre** : `etude/ir.json` pour les 10 études. Les hypothèses sont écrites une fois
  (D-289), mais dans un fichier d'exploration de la phase 10 (voir 1.1).
- **L'étage de chaque réponse** (`ETAGES`, `etude.py:323`), le verdict (`VERDICTS`, `:284`),
  les vues (`VIEWS`, `:282`) : partagés.
- **Les phrases du cadre et des « d'où viennent ces nombres »** sont générées par `lines()` à
  partir du rapport, donc identiques.
- **Le texte propre à chaque type** (chapeau, refus) vit dans trois classes. Quelques reprises
  de vocabulaire : sur la page d'un programme, l'en-tête dit encore « sous la première
  persistance de l'effet macro de **chaque article** » (`docs/etudes/presidentielle_lisnard.md:15`),
  alors que le programme n'a pas d'articles. D-333 relève aussi « 1 mesures chiffrées »,
  laissé tel quel.

### 5.2 Des études sur des moteurs différents

Le site présente côte à côte des études chiffrées sur **quatre codes**. Entre `02fd623`
(PLF, 10-28) et `c36984d` (11-03), le moteur a changé en profondeur, avec des effets sur les
nombres :

| D-entrée | changement |
|---|---|
| D-305 à D-313 | les IJ dans la population, l'IR et la CSG ; l'exonération ALD |
| D-310 | les ménages du haut dans chaque échantillon des taux marginaux, qui touche C1 et donc la bande |
| D-311 | la greffe des paramètres ; même résultat annoncé, « octet pour octet » |
| D-318 | le vieillissement |
| D-328 | `/population/simulate` lit la consommation de 2024 au lieu de 2026 ; les taux marginaux d'une réforme de consommation |
| D-329 | la greffe : « 3 » contre « 3.0 » |

Les pages du PLF 2027 et du PLFSS 2027 sont donc **sans IJ et sans la correction de D-310**.
Les programmes en ont. Chaque page dit son commit, ce qui est honnête, mais deux coûts du
site ne sont pas comparables entre eux, et rien sur l'accueil ne le signale.

### 5.3 Les rapports commités qui ne se régénèrent plus

- **Le rendu se régénère** : la page vient des rapports, par le code d'aujourd'hui, et la
  garde de dérive le vérifie (`etude.py:1365-1377`, `site.py:246-258`).
- **Les nombres, non.** Rejouer `impots etude lancer` sur `HEAD` donnerait d'autres nombres
  pour le PLF et le PLFSS (5.2). Les rejouer à l'identique demande de revenir à `02fd623` ou
  `b73ffcf`. Ces commits existent, mais leurs worktrees figés (`/home/user/wt/but6-run`…)
  n'existent plus, et il faut `make data` avec les mêmes données. Rien n'enregistre
  l'empreinte des données d'entrée dans les rapports, seulement le commit.
- **Le couplage aux définitions vivantes est un piège.** `load` et `load_plages` comparent
  les requêtes enregistrées à celles que les scénarios, `programmes/*.json` et
  `etude/ir.json` donnent **aujourd'hui** (`etude.py:950-961`, `:1011-1015`). Corriger une
  coquille dans une plage d'un programme, une source, ou le cadre, casse la page, puis le
  site, et la seule réparation est de relancer les passes de l'étude (73 pour le but 13,
  ≈ 10 à 20 h). C'est voulu (aucune page ne dit ce que ses rapports n'ont pas chiffré), mais
  le coût de maintenance est élevé, et une grille de précalcul aurait le même couplage.
- **Les réponses validées par le schéma d'aujourd'hui.** `PredictifReportResponse`,
  `PopulationResponse` et `FirmResponse` valident les rapports à la lecture (`etude.py:1017-1033`).
  Un champ rendu obligatoire dans `api/schemas.py` invalide d'un coup les 10 études. Rien ne
  versionne le schéma des rapports.
- **D'autres pages ne sont pas sur le site** : `docs/PREDICTIF_ETUDE.md`, rendue par
  `scripts/write_predictif_etude.py` avec sa propre garde (`tests/test_predictif_etude.py`),
  `docs/PREDICTIF_EXEMPLE.md` et les fiches `reports/fiche_*.md`. Elles relèvent d'une autre
  chaîne de rendu, avec les mêmes principes mais un code distinct.

### 5.4 Les pronostics, entre études

D-333 fait la synthèse : les 8 coûts sont dans leur fourchette, et 6 verdicts sur 8 manquent
leur pronostic. Le verdict préenregistré pensait la dette sur le coût mécanique et sur la
persistance « éteinte ». La page du PLF dit 5 « baisse » et 4 « dépend de θ ». C'est un point
de méthode à porter dans la grille : le verdict « robuste » ou « dépend de θ » doit lire les
deux persistances, sinon le curseur affichera un signe que la boîte contredit.

---

## Les risques, en bref

1. La couche de service vit dans `api/main.py` et se consomme par des fonctions privées.
2. `etude/ir.json` est à la fois une requête de la phase 10 et le cadre de toutes les études.
3. Les pages publiées viennent de quatre moteurs, sans signal sur l'accueil.
4. Toute retouche d'un programme ou du schéma oblige à relancer les passes (des heures).
5. L'interface n'expose pas 25 boutons, dont tous ceux des études publiées.
6. Les références à `ETUDE_PLF2027.md` et `write_etude_plf2027.py` sont mortes.
7. Les rapports ne gardent ni durée ni empreinte des données.
