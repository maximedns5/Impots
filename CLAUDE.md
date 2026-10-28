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
