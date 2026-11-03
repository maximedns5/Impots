# Impots — à lire en début de session

* **Le but** : `docs/BUT.md`. Pour qui, les trois réponses, le livrable, le critère de
  réussite (les chiffrages officiels retrouvés), la règle de priorité et le `/goal` en
  cours. Un travail se choisit contre ce document.
* **L'état** : `docs/STATE_AND_NEXT.md`. **Les décisions** : `docs/DECISIONS.md`.

## Les règles qui ne se discutent pas

* Ne pas toucher `src/impots/population/calibrate.py` (fermé jusqu'à la phase 7).
* Ne jamais masquer un échec : pas d'assertion retouchée pour passer, pas de saut
  générique, pas de valeur substituée. Un test qui échoue de façon inattendue : soupçonner
  le test d'abord. Les fichiers de données n'entrent pas dans git.
* Un chiffrage comparé à un juge officiel, ou publié dans une étude, est préenregistré avec
  son pronostic dans une D-entrée commitée et poussée avant de tourner. Son résultat va dans
  une nouvelle D-entrée, en français, dans le style des entrées existantes (lignes de 92
  caractères au plus).
* On n'ouvre pas une annexe d'évaluations préalables avant le commit des enregistrements,
  et aucune tolérance n'est modifiée après le premier calcul.
* Pas de `make full` sans l'accord du propriétaire.

## Les tests, proportionnés (D-335)

Le développement passe d'abord ; les tests tiennent les nombres, pas la plomberie.

* **Un correctif qui change un nombre** a un test qui le tient. On le voit échouer sur le
  code d'avant quand c'est léger, quelques secondes ; sinon, le commit le dit.
* **La plomberie** (mémoire, temps, rendu, structure du code) n'a pas de test dédié, ni de
  test qui lit le source : son effet se mesure une fois et se dit dans le commit ou la
  D-entrée.
* **Pas de banc de mutations**, sauf à la demande du propriétaire.
* **Pendant le développement**, les tests légers des fichiers touchés, quelques minutes au
  plus : `pytest -m "not lourd and not chrono" -n $JOBS <fichiers>`. `make impact` (D-309)
  et les lourds (`tests/lourds.txt`, chacun dans son processus) tournent une fois, avant la
  PR du but. On évite d'écrire un test qui lance une passe sur la population réelle ; s'il
  le faut, il va dans `tests/lourds.txt`. Plus `node ui/check.mjs` si la page change.
* **Un correctif qui ne change aucun nombre** ne fait pas relancer les passes déjà faites :
  la D-entrée le dit, et chaque rapport garde son commit.
* **Une passe d'essai** (un profil de mémoire, une mesure de temps, un essai hors rapports)
  n'a pas besoin de D-entrée.

## Comment on travaille, pour aller vite

* **Un but à la fois**, dans son propre worktree, sur une branche `claude/<but>` partie
  de `origin/main`. Une PR par but ; le propriétaire décide du merge.
* **Les données** ne sont jamais dans git : `make data` les prépare dans un checkout
  neuf. Le code se lance avec le venv du dépôt et `PYTHONPATH=src`.
* **Une passe longue** se lance détachée (`setsid nohup … &`) : les tâches de fond d'une
  session peuvent être tuées en route. On ne modifie ni `src` ni `scripts` dans un
  worktree où une passe tourne.
* **L'API en local** : `IMPOTS_AUTH=aucune uvicorn impots.api.main:app`. Sans cela, les
  calculs sont fermés (D-295).
* **Le compte rendu** au propriétaire est en français : ce qui est fait, ce qui ne l'est
  pas, ce qui reste à décider.
