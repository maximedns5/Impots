# Runbook — la semaine où le PLF 2027 paraît

Le triage (`PLF2027_COVERAGE.md`) dit **ce que** l'outil sait chiffrer. Ce document dit
**dans quel ordre** le faire, pour que la semaine de publication soit de l'exécution et
non de la conception.

La règle qui gouverne tout le reste : **un chiffrage vaut ce que vaut sa date.** Tout ce
qui suit est ordonné pour qu'un chiffre soit enregistré et committé AVANT que le chiffre
officiel soit lu. Une fois l'évaluation préalable ouverte, il est trop tard pour
préenregistrer quoi que ce soit, et aucune discipline ne rattrape cela.

---

## 0. Avant même de lire le texte (30 minutes, à faire une fois)

```bash
make full                     # une ligne verte dans reports/full_pass_log.md
git status --short            # l'arbre doit être propre : le commit de chaque
                              # chiffrage est son horodatage
```

Un arbre sale au moment d'enregistrer rend le hash de commit inutilisable comme témoin.

---

## 1. Manifester le texte (10 minutes)

Le PLF paraît en open data à l'Assemblée nationale sous la forme
`https://www.assemblee-nationale.fr/dyn/opendata/PRJLANR5L17B<numéro>.html`, et
l'annexe des évaluations préalables sous
`.../dyn/dyn/contenu/visualisation/<id>/file/…Evaluations…pdf`.

**Relever les URL sur la page de publication, jamais dans un index de recherche** — la
règle du pointeur (`SOURCE_POINTERS.md`) est née d'une URL qu'un index servait encore
neuf mois après un redépôt.

```bash
curl -sL -o data/raw/plf2027_texte_an.html   "<url du texte>"
curl -sL -o data/raw/plf2027_evaluations_prealables.pdf "<url de l'annexe>"
```

Puis ajouter les deux au manifeste avec leur sha256 et une description qui porte **la
structure** : où sont les titres d'articles, où est le rendement, et quelle est l'unité.
Reprendre mot pour mot les avertissements des entrées 2026, qui sont des pièges de
format et non des accidents :

* le rendement vit en **4.2.1** et n'a **pas de forme unique** — tableau à cinq colonnes,
  chronique à treize colonnes, ou simple phrase en prose. En 2026, un extracteur qui ne
  cherchait que des tableaux a raté l'article 4, c'est-à-dire **le plus gros montant de
  toute l'annexe et le seul article chiffrable** ;
* **l'unité est déclarée par fiche** et varie : en 2026, les articles 5 et 6 en
  milliards, tous les autres en millions. Un facteur mille ;
* et une fiche peut se contredire : l'article 2 portait « 1,5 » sous un en-tête « en
  millions » dont la note de méthode disait « 1,5 Md€ ». Ce montant-là n'entre pas dans
  un chiffre, il entre dans `YIELD_AMBIGUOUS`.

## 2. Re-dériver le triage sur les vrais articles (2 à 4 heures)

```bash
# découper le texte comme en 2026 : les <h6> portent « ARTICLE n : intitulé »
# et la section fiscale est « I – Impôts et ressources autorisées / B – Mesures fiscales »
```

Pour chaque article publié : le rattacher à une **catégorie** de
`src/impots/plf_coverage.py`, et prendre la case de cette catégorie. Les catégories sont
faites pour survivre à une renumérotation ; c'est leur seule raison d'être.

**Un article dont la catégorie est absente est une décision de triage NEUVE.** La
prendre, l'écrire, et dire dans le fichier qu'elle a été prise le jour même. Un refus
préenregistré est une limite ; un refus improvisé est une excuse, et la seule différence
visible est cette mention.

Trois pièges à vérifier **avant** d'annoncer un article chiffrable, chacun ayant coûté
une fausse promesse en 2026 :

1. **L'arbre contient-il déjà la mesure ?** Si le droit courant porte déjà l'état final
   de l'article, le chiffrer contre lui rend 0,00 EUR — un zéro confiant. C'est le champ
   `mirror` de la suite de backtests : le cas doit encoder **l'abrogation**. Vérifier en
   lisant le paramètre année par année, pas en supposant.
2. **Le bouton bouge-t-il tout ce que l'article bouge ?** Si l'article déplace six
   coefficients et qu'un bouton en déplace un, c'est `bound: lower` : le chiffre simulé
   DOIT atterrir en dessous du publié, et le dépasser est un constat, pas une réussite.
3. **La population contient-elle des contribuables que la mesure atteint ?** Un paramètre
   vivant sur une assiette vide donne zéro. C'est la case `population_blind`.

Puis :

```bash
.venv/bin/python -m pytest tests/test_plf_coverage.py -q   # boutons et chemins vérifiés
.venv/bin/python scripts/write_plf_coverage.py             # le document se régénère
```

## 3. Câbler les petits boutons pré-identifiés (variable, 1 à 3 h par bouton)

Uniquement ceux que le triage a marqués `small_knob` **et dont le chemin de paramètre a
déjà été vérifié**. Pour chacun :

* ajouter le champ à `ReformSpec` avec ses bornes ;
* router l'écriture par `update_existing` — jamais d'écriture directe ;
* **le faire bouger sur un ménage avant de le déclarer vivant** (D-081). Un ménage qui
  n'exerce pas le levier ne prouve rien : quatre boutons IFI ont failli être déclarés
  morts pour cette raison ;
* vérifier que l'instrument entre bien dans le registre de sortie ET dans
  `STATE_RECEIPTS`/`STATE_TRANSFERS`. Sinon la garde de partie double refusera la
  course — ce qui est le bon comportement, et c'est exactement le prérequis relevé pour
  la CDHR.

Un bouton qu'on n'a pas eu le temps de câbler proprement **n'est pas câblé**. Le triage
avait dit `small_knob`, la semaine dira `non câblé faute de temps`, et c'est une phrase
honnête.

## 4. Enregistrer les chiffrages — AVANT de lire l'annexe (1 h)

C'est l'étape qui porte toute la valeur, et son ordre n'est pas négociable.

```bash
.venv/bin/python -m impots.population.cli scenario save plf2027_art_N \
  --reform reforms/plf2027_art_N.json \
  --source "PLF 2027, art. N — <intitulé exact>"

.venv/bin/python -m impots.population.cli chiffrage register plf2027_art_N \
  --scenario plf2027_art_N \
  --tolerance-relative 0.20 \
  --tolerance-absolute 200e6 \
  --tolerance-rationale "…pourquoi CELLE-CI, et pas une autre…" \
  --sample 20000

git add chiffrages_preregistres/plf2027_art_N.yaml scenarios/plf2027_art_N.json
git commit -m "Pré-enregistrement : PLF 2027 art. N"
```

**Le fichier n'est pas le préenregistrement — le commit l'est.**
`verify_tolerance_unchanged` refuse de noter un cas jamais committé, et lit ensuite la
tolérance dans l'**historique git** et non dans le fichier : une tolérance élargie une
fois la réponse connue transforme chaque manqué en réussi et laisse un fichier
indiscernable d'un fichier honnête. Le fichier ne peut pas attraper cela. Git le peut.

Sur la tolérance, deux choses :

* elle est une **paire**, relative et absolue, et l'indulgence est la plus large des deux.
  Un article chiffré « sans impact budgétaire » publie 0, et une tolérance purement
  relative exigerait de lui une précision infinie ;
* la justification est obligatoire. Dire pourquoi celle-ci **avant** de connaître la
  réponse est ce qui en fait un engagement plutôt qu'un nombre.

Enregistrer **tous** les articles chiffrables, y compris ceux dont on pressent qu'ils
seront mauvais. Un registre qui ne contient que les cas où l'on se sentait sûr ne mesure
rien.

## 5. Puis, et seulement puis, lire l'annexe (2 h)

Saisir le comparateur dans chaque cas : `published_eur`, `source`, `vintage`,
`perimeter`, `net_of`, `sign` (« cost » ou « yield », **porté et jamais déduit du signe
du nombre** — les documents publiés sont incohérents là-dessus) et `basis`
(« annee-pleine » ou « premiere-annee »).

```bash
.venv/bin/python -m impots.population.cli chiffrage grade plf2027_art_N
.venv/bin/python -m impots.population.cli chiffrage report
git add chiffrages_preregistres/ reports/chiffrages_preregistres.md && git commit -m "Comparateurs et notes"
```

**Un cas rouge est un constat à écrire, jamais un nombre à faire disparaître.** Et
l'ordre mécanique-avant-économique (D-029) s'applique : avant d'invoquer le réalisme de
la population, essayer le mauvais millésime, un bouton qui n'exprime pas l'article, et
une discordance année-pleine / première-année.

## 6. Ce qu'on ne fait pas cette semaine-là

* **On ne publie rien.** La section publication reste gelée par le propriétaire.
* **On n'élargit aucune tolérance.** Une révision est un nouveau cas, daté d'aujourd'hui,
  qui laisse l'ancien porter sa note.
* **On n'invente aucun chiffre** pour un article que le triage a refusé. « Nous n'avons
  pas su chiffrer X » est un résultat, et il a été préenregistré en septembre.

---

## Ce que la semaine produira, honnêtement

Sur la structure 2026, **un** article fiscal sur 29 était chiffrable — mais il portait
46 % du rendement que l'annexe quantifie, parce que c'était le plus gros. Attendre du
PLF 2027 un ordre de grandeur comparable est raisonnable ; attendre mieux ne l'est pas,
et le dire d'avance est le seul moyen que le résultat signifie quelque chose.

L'intégrité du préenregistrement est de **qualité interne** : un hash de commit dans un
dépôt privé. C'est honnête pour un usage interne et ne convaincrait personne à
l'extérieur, puisque le propriétaire du dépôt peut réécrire l'histoire. Si la crédibilité
externe devient un enjeu, il faut un horodatage **hors du dépôt au moment de
l'enregistrement** — un commit public, un hash publié. C'est une décision du propriétaire,
enregistrée comme option et non prise (D-095).
