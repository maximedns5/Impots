# Consigne commune des étapes 1 à 4 du but 19 (D-365)

Lis d'abord : `CLAUDE.md`, `docs/BUT.md` (but 19), D-362 à D-365 dans `docs/DECISIONS.md`,
`docs/diagnostics/SYNTHESE.md` et le diagnostic de ton étape. Ton worktree est
`/home/user/Impots-but19-eN` (branche `claude/but19-eN`, partie de `claude/but19`). Le code
se lance avec `PYTHONPATH=src .venv/bin/python` depuis ton worktree.

## Les règles

* **Tu ne touches que ton worktree.** Trois autres agents développent les autres étapes en
  même temps, chacun dans le sien ; je joins les branches ensuite. Garde tes changements
  ciblés, pour que la jonction soit simple.
* **Les données.** `data/raw`, `data/interim`, `data/processed` sont des liens vers des
  fichiers partagés. **N'écris jamais à travers un lien** : si un outil doit écrire un
  fichier de `data/`, supprime d'abord le lien (`rm data/processed/<fichier>`, jamais la
  cible) ou donne-lui un chemin dans `/tmp/<ton étape>/`. Une source neuve se télécharge
  dans ton `data/raw` et s'ajoute à `data/raw/MANIFEST.json` (URL, sha256, octets, date,
  description), comme les entrées existantes. Les fichiers de données n'entrent pas dans git.
* **La mémoire est partagée** (15 Go, 4 cœurs, quatre agents). Jamais de passe ni de
  construction sur la population entière. Les essais se font sur un échantillon de
  **15 000 ménages au plus** (`runner.subsample` ou équivalent, graine fixe), une passe à
  la fois, et seulement si `free -g` montre au moins 5 Go disponibles ; sinon attends.
* **Pas de grille, pas d'étude.** Tu ne lances ni `impots verification passe`, ni
  `impots etude lancer`, ni `make full`. La grille et la série tournent après la jonction,
  préenregistrées par moi.
* **Préenregistrement.** Tu ne modifies pas `docs/verification/lignes.json` ni ses
  tolérances, et tu n'écris pas de D-entrée. Une ligne neuve de la grille, une marge neuve
  du calage, une tolérance : tu les proposes dans ton rapport, avec leur source publiée
  (URL, tableau), et je les préenregistre avant tout calcul sur la population entière.
* **Ne masque rien.** Pas d'assertion retouchée pour passer, pas de saut, pas de valeur
  substituée. Un nombre sans source se dit « non trouvé ». Une hypothèse se dit hypothèse.
* **Les tests (D-335).** Un changement qui bouge un nombre a un test qui le tient, vu
  échouer sur le code d'avant quand c'est léger. Pas de test pour la plomberie. Pendant le
  développement : `PYTHONPATH=src .venv/bin/python -m pytest -m "not lourd and not chrono"
  -n 2 <fichiers touchés>`. Ne lance pas `make impact`.
* **L'API.** La réponse de l'API énumère ses champs (`extra_forbidden`) : un champ neuf dans
  `outputs.REGISTRY` la casse (vu au but 18). Une sortie neuve se calcule dans la passe de
  population (`runner.py`), ou le schéma de l'API suit, avec ses tests.
* **Commits.** Commite sur ta branche, en français, des messages qui disent ce qui change
  et pourquoi, terminés par :
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` et
  `Claude-Session: https://claude.ai/code/session_01SjST5i6Y2xn5QqodujLdHp`.
  Pousse ta branche (`git push -u origin claude/but19-eN`), sans PR.

## Ton rapport final

Écris `docs/diagnostics/etape_N.md` dans ton worktree (commité), en français, lignes de 92
caractères au plus :

1. ce qui a changé, fichier par fichier, et pourquoi ;
2. les mesures sur échantillon contre les totaux publiés, avant et après (taille, graine),
   en disant qu'elles ne sont pas aveugles ;
3. **le préenregistrement proposé** : les lignes neuves de la grille ou marges neuves, avec
   source, tolérance et raison ; le pronostic, ligne par ligne de la grille, en fourchette,
   pour 2022, 2023 et 2024 ;
4. ce que l'étape fait aux études (lesquelles bougent, dans quel sens, ordre de grandeur) ;
5. ce qui reste, les doutes, les sources que le conteneur n'a pas pu lire ;
6. les tests lancés et leur sortie.

Ta réponse finale : dix lignes au plus, le SHA de ton dernier commit poussé.
