# M2 — ce qu'il faut pour chiffrer le seau B, et ce qui est déjà là

**Établi par mesure, pas par mémoire.** Chaque ligne de ce document sort de
`data/raw/MANIFEST.json` lu par `load_manifest()`, pas d'un souvenir de ce qui avait
été téléchargé. La session qui l'écrit tourne dans un conteneur **sans aucun fichier
de `data/raw/` et sans accès réseau** — les deux vérifiés : `find data -type f` rend
cinq fichiers dont aucun n'est une source, et le proxy refuse
`www.assemblee-nationale.fr`, `www.insee.fr`, `www.ofdt.fr` et `ec.europa.eu`. Donc
aucun chiffre d'ancre n'a pu être lu ici, et aucun n'est écrit dans ce document :
en écrire un de mémoire est précisément ce que `ReceiptsAnchor` refuse.

## L'état du manifeste, mesuré

**145 fichiers manifestés : 69 sourcés, 76 en quarantaine.** Un fichier en
quarantaine porte une somme de contrôle et aucune URL — ce qui prouve que les octets
n'ont pas bougé, et rien sur leur provenance (D-028).

## Ce qui bloque, et qui n'est pas ce qu'on croit

`ReceiptsAnchor.verify()` refuse **par son nom** un fichier en quarantaine :

> « *est en quarantaine ou sans URL. Une somme de contrôle prouve que les octets
> n'ont pas changé, pas d'où ils viennent (D-028) — et une ancre de recettes est
> exactement le genre de chiffre qui doit être reproductible par un tiers.* »

Et les trois documents vers lesquels on tend naturellement la main pour une ancre de
recettes **sont en quarantaine** :

| fichier | état |
|---|---|
| `voies_et_moyens_tome1_plf2026.pdf` | quarantaine — aucune URL |
| `budget_execution_2025_recettes_fiscales_nettes.pdf` | quarantaine — aucune URL |
| `ccomptes_budget_etat_2025_resultats_gestion.pdf` | quarantaine — aucune URL |

**Le piège, et il se referme dans le bon sens.** `vm_tome1_plf2026_recettes.pdf` est
sourcé, avec URL — et porte le **même sha256** que
`voies_et_moyens_tome1_plf2026.pdf` : `4703605d…`. C'est le même document, manifesté
deux fois, une fois utilisable et une fois non. Un agent qui ancrerait sur la copie
en quarantaine verrait le moteur refuser et conclurait que l'ancre manque. Elle ne
manque pas : **c'est la copie sourcée qu'il faut nommer.**

Les deux ancres de recettes utilisables aujourd'hui, toutes deux sourcées :

* `vm_tome1_plf2026_recettes.pdf` — Voies et moyens tome I, PLF 2026, évaluation des
  recettes. Ligne par ligne, tout le revenu de l'État. **Règle de millésime : les
  colonnes des Voies et Moyens sont des années BUDGÉTAIRES** (D-067) ; un modèle en
  revenus 2024 lit la colonne 2025. C'est la quatrième fois que la convention de
  millésime du comparateur est l'erreur entière.
* `insee_cn2025_t3217_principaux_impots_par_categorie.xlsx` — comptes nationaux,
  principaux impôts par catégorie. Périmètre comptabilité nationale, pas budget de
  l'État : les deux ne sont pas interchangeables et la ligne doit dire laquelle.

## Instrument par instrument

`R` = ancre de recettes, `V` = assiette physique ou ventilation. Un instrument dont
la reprise est proportionnelle n'a besoin que de `R` ; un instrument en tarif ×
volume a besoin des deux.

| Instrument (§2.3) | besoin | ancre `R` | assiette `V` | constructible aujourd'hui |
|---|---|---|---|---|
| TSN | `R` seul | **en main** (VM tome I) | — | **oui** |
| TTF | `R` seul | **en main** | — | **oui** |
| Taxe sur les salaires | `R` seul | **en main** | — | **oui** |
| Versement mobilité | `R` seul, multiplicateur uniforme | **en main** | — | **oui** |
| DMTO | `R` seul | **en main** | — | **oui** |
| Petites taxes (TASCOM, TGAP, forfait social, taxe d'apprentissage) | `R` seul | **en main** | — | **oui** |
| TVA | `R` + ventilation par taux | **en main** | **ABSENTE** — aucune source COICOP au manifeste | reprise proportionnelle seulement ; le sous-bouton « restructuration d'assiette » reste **D** tant que R5 ne donne pas l'assiette par taux au grain COICOP |
| Accise énergies (ex-TICPE) | `R` + volumes | **en main** | **ABSENTE** — ni CCTN ni DGEC | non |
| Accise tabacs | `R` + volumes | **en main** | **ABSENTE** — aucun OFDT | non |
| Accise alcools | `R` + volumes | **en main** | **ABSENTE** — aucun DGDDI | non |
| Accise électricité / gaz | `R` + tarifs par millésime | **en main** | **ABSENTE** | non |

Cherché sur l'ensemble du manifeste, clés et métadonnées : `coicop`, `cctn`, `dgec`,
`ofdt`, `tabac`, `dgddi`, `alcool`, `ticfe`, `ticgn`, `versement mobilité`, `dmto`,
`tascom`, `tgap`, `forfait social`, `apprentissage`. **Zéro correspondance sourcée.**

## CORRECTION DU 2026-09-25 — la table ci-dessus est fausse pour six instruments

**Le document a été écrit dans un conteneur sans `data/raw/` et sans réseau**, ce qu'il
annonce lui-même. Sa colonne « ancre `R` » disait donc « en main (VM tome I) » sur la foi
du manifeste, sans jamais OUVRIR le fichier. Vérifié ici, sur la machine qui l'a : six des
neuf instruments n'ont **aucune ligne de recette** dans ce document, et la raison est
structurelle — ce sont des recettes qui ne vont pas à l'État.

**Mesuré dans `vm_tome1_plf2026_recettes.pdf`, 102 pages, texte extrait :**

| instrument | ligne État | montant publié | verdict |
|---|---|---|---|
| TSN | **1430** | **785 M€** (exécution 2024) | ancre en main |
| TTF | **1797** | **1 332 M€** (exécution 2024) | ancre en main |
| TGAP | **1756** | **1 150 M€** (exécution 2024) | ancre en main |
| accises énergies (nettes) | 1501–1504 | **20,2 md€** (exéc. 2024) ; 22,9 au PLF 2026 | ancre en main |
| TVA (nette) | — (agrégat) | **96,8 md€** (exéc. 2024) ; 109,1 au PLF 2026 | ancre en main |
| taxe sur les salaires | **aucune** | — | affectée à la Sécu : **autre source** |
| forfait social | **aucune** | — | affecté à la Sécu : **autre source** |
| taxe d'apprentissage | **aucune** | — | France compétences : **autre source** |
| versement mobilité | aucune (mention en PSR de compensation) | — | recette des AOM : **autre source** |
| DMTO | aucune (mention en fonds de péréquation) | — | recette départementale : **autre source** |
| TASCOM | aucune (mention dans un CCF) | — | recette locale : **autre source** |
| accise tabacs | **aucune** | — | affectée à la Sécu : **autre source** |
| accise alcools | **aucune** | — | affectée à la Sécu : **autre source** |

**La convention de colonne, relevée mot pour mot** et non déduite : « Exécution 2024 |
LFI 2025 | Révisé 2025 | Écart | PLF 2026 | Écart ». Une ancre doit dire LAQUELLE, et
`vintage_convention` vaut `budget` pour toutes ces lignes.

**Un piège de millésime dans le document même** : jusqu'au 31 décembre 2025, l'accise
ex-TICPE était à la ligne 1501 et les autres accises énergies regroupées ailleurs ; le
découpage 1501/1502/1503/1504 est **nouveau**. Une ancre qui nomme une ligne sans nommer
son millésime pointera la mauvaise recette dès la publication suivante.

**Ce que cela change pour M2.** Trois instruments seulement sont ancrables depuis la source
que le document nommait — TSN, TTF, TGAP — plus la TVA et les accises énergies en agrégat.
**Six exigent une source que le dépôt n'a pas**, et ce n'est pas un oubli de téléchargement :
ce sont des recettes affectées, qui ne figurent pas au budget de l'État par construction.

## La liste de téléchargements — révisée le 2026-09-25

**Ce qu'il faut demander, en plus de ce que la liste ci-dessous porte déjà :**

* **Les recettes affectées à la Sécurité sociale** (taxe sur les salaires, forfait social,
  accises tabacs et alcools) : annexe recettes du PLFSS, ou le rapport de la CCSS. Note :
  `ccss_mai2026_comptes_secu_resultats2025.pdf` est **déjà au manifeste mais en
  quarantaine** — il lui manque une URL, pas un téléchargement. C'est le même piège que la
  7.301, et il se lève de la même façon.
* **Les recettes locales** (versement mobilité, DMTO, TASCOM) : les états DGFiP/DGCL de
  fiscalité locale. Aucun candidat au manifeste.

## La liste de téléchargements

Pour chacun : le document exact, comment reconnaître le bon, et le contrôle à faire
AVANT de s'en servir. Aucune valeur attendue n'est donnée : aucune n'est dérivable
depuis ce dépôt, et une valeur de mémoire ne serait pas une vérification, seulement
une seconde chance de se tromper pareil.

1. **Ventilation de la consommation des ménages par produit (COICOP) — comptes
   nationaux, R5.** Ce qu'il faut : la consommation finale des ménages par fonction
   COICOP, au grain le plus fin publié, pour la dernière année close. Reconnaître le
   bon : la somme des postes doit reproduire la consommation finale des ménages du
   tableau des ressources-emplois du même millésime. Sans lui, la TVA ne se reprend
   que proportionnellement.
2. **Volumes de carburants — CCTN (bilan de la circulation) ou DGEC.** Mises à la
   consommation par produit (gazole, SP95/98, GNR…), en volume, dernière année close.
   Reconnaître le bon : tarif accise × volume doit retrouver la ligne de recettes des
   Voies et Moyens du même millésime, à quelques pour cent.
3. **Volumes de tabac — OFDT.** Livraisons aux buralistes, en tonnes ou en unités de
   vente, série annuelle. Il en faut une **série**, pas une année : c'est l'épisode
   §6.2 (trajectoire à 10 €/paquet, 2018-2020) qui est le cas noté de M2, et il se
   note sur la réaction des volumes. Même contrôle tarif × volume contre les recettes.
4. **Volumes d'alcool — DGDDI ou OFDT.** Mises à la consommation par catégorie
   (bières, vins, spiritueux), dernière année close. Même contrôle.
5. **Tarifs d'accise électricité et gaz par millésime — textes ou séries DGEC.**
   L'historique post-2022 est heurté (bouclier tarifaire) : il faut les tarifs datés,
   pas un taux courant. **Ancrer sur la dernière année close**, et la ligne doit dire
   laquelle.
6. **L'ajustement flux-stocks (M1 §6.1), toujours manquant — ET LE CODE DONNÉ ICI ÉTAIT
   FAUX.** Vérifié à l'API de diffusion le 2026-09-25 (D-163) : `gov_10dd_edpt1` existe
   mais ses 18 postes ne contiennent **aucun** ajustement flux-stocks, et `gov_10dd_sfa`,
   annoncé par ailleurs, rend **HTTP 404**. La bonne table est **`gov_10dd_edpt3`**,
   « Transition from the deficit/surplus to the change in debt ». Deux réserves qui
   comptent : **2019 et 2020 sont ABSENTS pour la France** sur ce poste, donc Eurostat seul
   ne couvre pas la fenêtre de §6.1 ; et le SFA n'y est pas une ligne mais un jeu de
   COMPOSANTES (`F_ASS`, `ORADJ`, `K61`, `KX`, `YA3`) dont la somme diffère de la
   différence `GD_CH − B9_T3` de 0,3 à 0,5 md€ — c'est cet écart qui en fait une mesure
   indépendante, et la sortie du piège de D-148.

**Pour tout export Eurostat personnalisé, l'URL n'est pas stable** — elle pointe un
UUID de session. Enregistrer le code du dataset et la requête dans `provenance`
plutôt que de faire semblant que le lien est reproductible (D-142).

**Et vérifier l'empreinte avant tout usage.** Un même nom de fichier sur deux
millésimes est la façon la plus simple de certifier des octets que personne n'a
téléchargés — c'est exactement ce qui s'est produit avec la 7.301.

## La table d'ancres, et comment la remplir

Le branchement existe depuis D-153 : les neuf instruments à reprise proportionnelle sont
**déclarés dans le code sans aucun chiffre**, et leurs euros sont lus depuis
`data/processed/receipts_anchors.json` — généré sur une machine qui a `data/raw/`,
gitignoré comme la table de cellules firmes. Un test refuse tout littéral monétaire dans
`src/impots/agregats/instruments.py`, et on l'a vu échouer en y écrivant un montant.

Une ligne par instrument :

```json
{"instrument": "tsn", "year": 2025, "amount_eur": 0.0,
 "manifest_file": "vm_tome1_plf2026_recettes.pdf",
 "vintage_convention": "budget", "note": "ligne X des Voies et Moyens tome I"}
```

`vintage_convention` n'a **pas de défaut** et vaut `budget`, `revenus` ou
`comptabilite_nationale` : une ligne sans elle est refusée au chargement. C'est la garde
de D-067 posée à l'entrée du chiffre, parce que trois fois déjà la convention de
millésime du comparateur a été l'erreur entière. Une ligne pointant un fichier absent du
manifeste ou en quarantaine est refusée aussi, et deux lignes pour un même instrument
également — sinon celle qui gagne dépend de l'ordre du fichier.

Les codes attendus : `tsn`, `ttf`, `taxe_sur_les_salaires`, `versement_mobilite`,
`dmto`, `tascom`, `tgap`, `forfait_social`, `taxe_apprentissage`. Un instrument sans
ligne n'est pas construit avec un substitut : il est **nommé manquant**, pour que la
revendication de couverture (§2.4) compte ce qui existe et non ce qui a été déclaré.

Tant que la table n'existe pas, `load_anchors()` lève `AnchorTableMissing` en renvoyant
vers ce document. Ce n'est pas un défaut : c'est l'état attendu de tout dépôt sans
`data/raw/`, et l'interface doit le dire plutôt que d'afficher un instrument sans
chiffre derrière.

## Ce qui peut donc être construit sans un seul téléchargement

Six instruments à reprise proportionnelle : TSN, TTF, taxe sur les salaires,
versement mobilité, DMTO, et la tranche des petites taxes. Plus la TVA en reprise
proportionnelle, son sous-bouton de restructuration d'assiette restant **D** avec sa
raison affichée.

Ce qu'ils exigent en plus de l'ancre, et qui ne se télécharge pas : la **bande
comportementale**, ou son absence dite. §2.3.1 impose un grade d'avertissement
« assiette très mobile » sur toute bande TSN, et pour la TTF une bande large ou
absente, la littérature sur la fuite d'assiette étant contestée. Sans ligne de
preuve vérifiée, la sortie lit « aucune réponse comportementale modélisée » — jamais
un zéro, qui serait une affirmation que personne n'a mesurée.
