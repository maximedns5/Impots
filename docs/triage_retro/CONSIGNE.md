# Consigne du triage rétrospectif (but 18, D-359)

Tu tries, article par article, des projets de loi de finances (PLF) et de financement de la
sécurité sociale (PLFSS) déposés entre 2020 et 2024, pour un simulateur fiscal français
(dépôt `/home/user/Impots-but18`). Le but : dire, pour chaque article, si le moteur peut le
chiffrer **sur la population des ménages ou des entreprises de son année**, et sinon
pourquoi. Ce triage précède l'ouverture des chiffrages du gouvernement (les « évaluations
préalables »), qui serviront de juge ensuite : il doit être fait **à l'aveugle**.

## Règles absolues

* **Ne lis que** les fichiers `data/interim/textes_retro/<clé>.md` (ou `.json`) qui te sont
  confiés, et le code du dépôt (`src/`, `scenarios/`, `reforms/`, `tests/`). Les exposés
  des motifs y sont **montants masqués** ; n'essaie pas de retrouver un montant.
* **N'ouvre aucun fichier de `data/raw/`**, aucun fichier de `chiffrages_preregistres/`,
  de `reports/`, ni `docs/DECISIONS.md` : ils contiennent des chiffrages.
* **Aucun accès réseau** : pas de curl, pas de recherche web.
* **N'écris que** ton fichier de sortie, `data/interim/triage_retro/<clé>.json`. Ne
  modifie rien d'autre, ne commite rien.
* Si tu connais de mémoire le rendement officiel d'un article, **ne l'écris nulle part** :
  signale seulement `"rendement_connu": true` sur l'article.

## Ce qu'est « chiffrable »

Le moteur chiffre une réforme comme un écart entre deux passes de la loi sur une
population : la loi de l'année (OpenFisca-France) et la même loi avec quelques paramètres
changés, les **boutons**. Les boutons existants sont les champs de `ReformSpec` (ménages)
et `FirmReformSpec` (entreprises) dans `src/impots/api/schemas.py` ; certains lisent un
chemin de paramètre libre (`parametres`, s'il existe : vérifie). Le triage du PLF 2027,
dans `src/impots/plf_coverage.py` (`ARTICLES_2027`, et `ARTICLES` pour les catégories de
septembre), montre le ton et les raisons attendues ; reprends ses catégories quand elles
s'appliquent.

La population des ménages est synthétique : la structure des ménages de l'enquête Emploi,
des revenus d'activité, de remplacement et du capital construits, des prestations
calculées ; pas de patrimoine détaillé, pas de transmissions, pas d'épargne détaillée,
pas d'indemnités de rupture. La population d'entreprises est synthétique, par cellules
(secteur × taille) : IS, contributions, CVAE, C3S, CEBGE. Une consommation par poste existe
(TVA par poste, accises sur l'énergie). Les retraites sont des données : pas de règle de
calcul des pensions, pas d'âge légal.

Quatre cases, une par article :

* `chiffrable` : un ou plusieurs boutons existants expriment le cœur de l'article (ou un
  volet clairement séparable, que tu nommes), **et** la population porte des gens que la
  mesure touche. Donne les boutons et la valeur, et l'année d'effet sur les revenus.
* `structure` : la mesure est hors de la structure du moteur (un paramètre absent, une
  règle que le moteur ne code pas, un dispositif nouveau).
* `donnees` : la structure existerait, mais la population ne porte pas la base (patrimoine,
  successions, niches très ciblées, revenus que la population n'a pas).
* `perimetre` : hors du champ d'un chiffrage d'impôt ou de prestation des ménages ou des
  entreprises (articles d'équilibre, de crédits, de plafonds d'emplois, de garanties,
  dotations aux collectivités, finances sociales agrégées, ONDAM, mesures d'organisation).

Sois strict : un article que tu ne peux pas exprimer avec des boutons qui existent **à la
lettre** n'est pas chiffrable. Un « chiffrable » douteux coûte plus cher qu'un refus.

## Sortie

Un JSON par texte, `data/interim/triage_retro/<clé>.json` :

```json
{"texte": "<clé>", "trie_par": "agent but 18", "articles": [
  {"numero": "2", "intitule": "…", "case": "chiffrable|structure|donnees|perimetre",
   "raison": "une ou deux phrases, en français",
   "volet": "le volet chiffré s'il n'est pas l'article entier, sinon \"\"",
   "boutons": {"nom_du_champ": valeur, "…": "…"},
   "couche": "menages|entreprises|\"\"",
   "annee_revenus": 2020,
   "rendement_connu": false}
]}
```

Un article par entrée, tous les articles du texte, dans l'ordre. Termine par un court
compte rendu dans ta réponse : combien d'articles par case, la liste des chiffrables avec
leurs boutons, et les doutes.
