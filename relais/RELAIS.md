# Relais du 18 novembre 2026 : reprendre les buts 28 et 29

Cette branche (`claude/relais-b28-b29`, partie de `claude/but29`) ne se merge pas. Elle
porte ce que l'ancienne session gardait hors du dépôt, dans son scratchpad, pour qu'une
nouvelle session reprenne. Les chemins absolus des scripts (`/home/user/Impots-…`,
`S=/tmp/claude-0/…/scratchpad`) sont ceux de l'ancien conteneur : les adapter.

## Le piège qui a tout arrêté

Le conteneur est repris dès que la session n'a plus rien en cours, et les passes détachées
(`setsid nohup`) meurent avec lui (redémarrages vers 06:30 et 11:00 UTC). Tant qu'une passe
tourne, garder la session occupée : une commande Bash `run_in_background` (timeout max
7 200 000 ms) qui attend la fin des passes, relancée à chaque notification.

## Les branches (toutes poussées, aucune PR, le propriétaire décide)

| branche | tête | ce que c'est |
|---|---|---|
| `claude/but28` | — | but 28, jonctions D-555, D-570, D-575 |
| `claude/but28-suite` | 1011637 | population D-553 (empreinte 5ace8bb6406d…) |
| `claude/but28-etudes` | 01a24df | la série des 17 études (D-556), code figé |
| `claude/but28-point2` | 57038e6 | forme Urssaf préenregistrée (D-580), passes à faire |
| `claude/but29` | c3511eb | but 29, page « Ce que ça change », jonction D-610, D-674, D-675 |
| `claude/but29-pouvoir` | d3679d0 | volet pouvoir, joint dans but29 |
| (détaché) | 4cbe38f | worktree figé des passes du juge de l'Insee (pouvoir) |

## Les trois travaux à finir, dans l'ordre que le propriétaire a donné

Le propriétaire : « laisse la série finir, continue ». Un seul verrou commun (`flock` sur un
fichier `passe.lock`) pour toutes les passes sur la population ; une à la fois (15 Go).

### 1. La série des 17 études (D-556, puis D-559)

* Worktree sur `claude/but28-etudes` à **01a24df**, sans commit avant la fin de la série :
  `etude lancer` saute un rapport déjà écrit **sur le même commit**.
* Données : `make data`, puis la population de D-553 construite sur `claude/but28-suite`
  (1011637) et copiée dans `data/processed` du worktree des études ; le script vérifie
  l'empreinte (5ace8bb6406d…). Les cellules du jumeau (`jumeau_cellules_2024.json`) aussi.
* Les rapports déjà faits sont ici, `rapports_serie/reports/etudes/…` (Mélenchon entier,
  Roussel en partie) : les copier, non commités, dans le worktree des études.
* Lancer `etudes28/serie_lancer.sh` (adapter S et le chemin). Ordre : melenchon, roussel,
  ruffin, tondelier, kazib, bouamrane, attal, retailleau, lisnard, philippe, le_pen,
  plfss2027, plf2027, glucksmann, labib, arthaud, zemmour. Mélenchon a pris environ 4 h 40.
* Après : commiter les rapports, `impots etude ecrire` et `impots etude verifier` par
  étude, rejouer les lignes `j` de `etudes28/lancer.sh` (jumeau, hors verrou), écrire
  D-559 (le résultat, contre les pronostics de D-556/D-558).

### 2. La forme Urssaf (D-580 préenregistrée → D-581, D-582)

* Worktree sur `claude/but28-point2` à 57038e6 ; `urssaf28/passe.sh` : construction de la
  population (14 s ; empreinte attendue e7d0c0560567…, facteur horaire 1,01989), grilles
  2024, 2023, 2022, complément 2022, `verification ecrire`, cellules, entrées, puis les
  rejeux (fin des exonérations, paire Smic × exonérations). Environ 1 h 30 de verrou.
* Rien n'a encore tourné au-delà de la construction. D-581 (grille) et D-582 (rejeux)
  s'écrivent contre D-580, sans toucher aucune tolérance.

### 3. Le juge de l'Insee du pouvoir d'achat (D-591 préenregistré → D-592, D-640)

* Worktree détaché à 4cbe38f. `pouvoir/A_FINIR.md` dit tout. Les niveaux de vie sont faits
  (`pouvoir_rapports/niveaux_de_vie_cellules.json`, à remettre dans `reports/jumeau/`) ;
  `ppa_passe` a fini une fois (3 min) mais sa sortie est hors du dépôt : la refaire, puis
  `ir_passe`, puis `juges_pouvoir_b29.py rapport`, puis `pouvoir/verdict.py`.
* Le pronostic de D-591 annonce trois écarts hors tolérance : ils restent écrits tels quels.
* Les juges (FPS 2020 fig. 4 ; FPS 2022 dossier D2, et non FPS 2021) sont au manifeste.

## Ce qui attend le propriétaire

Dans `docs/CE_QUE_CA_CHANGE.md` (branche but29) : le coefficient du chômage autour de soi,
la symétrie de la pression du coût, la ligne de Mélenchon et Tondelier, le défaut de
`IMPOTS_VERROU_PASSES`, l'édition du juge de l'impôt (FPS 2022 au lieu de 2021), la liste
`LISENT_LES_DECILES`, la grille étendue des cas types, les calendriers d'âge, les parts
causales de la santé, l'outre-mer trop riche ; et les PR des buts 27, 28, 29.
