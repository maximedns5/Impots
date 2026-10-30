# Impots — à lire en début de session

* **Le but** : `docs/BUT.md`. Pour qui, les trois réponses, le livrable, le critère de
  réussite (les chiffrages officiels retrouvés), la règle de priorité et le `/goal` en
  cours. Un travail se choisit contre ce document.
* **L'état** : `docs/STATE_AND_NEXT.md`. **Les décisions** : `docs/DECISIONS.md`.

## Les règles qui ne se discutent pas

* Ne pas toucher `src/impots/population/calibrate.py` (fermé jusqu'à la phase 7).
* Chaque garde a un test qui la tue, vu échouer sur le code d'avant le correctif. Un test
  qui échoue de façon inattendue : soupçonner le test d'abord.
* Ne jamais masquer un échec : pas d'assertion retouchée, pas de saut générique, pas de
  valeur substituée. Les fichiers de données n'entrent pas dans git.
* Pas de `make full` sans l'accord du propriétaire. Lancer les tests ciblés, pas toute la
  suite.
* Chaque passe longue est préenregistrée, avec son pronostic, dans une D-entrée commitée
  et poussée avant de tourner. Son résultat va dans une nouvelle D-entrée, en français, dans
  le style des entrées existantes (lignes de 92 caractères au plus).
* On n'ouvre pas une annexe d'évaluations préalables avant le commit des enregistrements,
  et aucune tolérance n'est modifiée après le premier calcul.

## Comment on travaille, pour aller vite

* **Un but à la fois**, dans son propre worktree, sur une branche `claude/<but>` partie
  de `origin/main`. Une PR par but ; le propriétaire décide du merge.
* **Les données** ne sont jamais dans git : `make data` les prépare dans un checkout
  neuf. Le code se lance avec le venv du dépôt et `PYTHONPATH=src`.
* **Les tests ciblés** : `make impact` (D-309). Un test vert n'est rejoué que si un fichier
  qu'il importe, même indirectement, ou qu'il lit a changé depuis ; en parallèle sur
  `JOBS` workers. La première fois, tout tourne. Plus `node ui/check.mjs` si la page
  change. Une sélection n'est pas une passe complète : avant une revue, `make full`, avec
  l'accord du propriétaire.
* **Une passe longue** se lance détachée (`setsid nohup … &`) : les tâches de fond d'une
  session peuvent être tuées en route. On ne modifie ni `src` ni `scripts` dans un
  worktree où une passe ou un banc de mutations tourne.
* **Une garde neuve** se vérifie aussi par mutation : chaque mutation est tuée par un
  test, ou nommée comme équivalente dans la D-entrée.
* **L'API en local** : `IMPOTS_AUTH=aucune uvicorn impots.api.main:app`. Sans cela, les
  calculs sont fermés (D-295).
* **Le compte rendu** au propriétaire est en français : ce qui est fait, ce qui ne l'est
  pas, ce qui reste à décider.
