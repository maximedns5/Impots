# Consigne commune des diagnostics (après le but 18, 10 novembre 2026)

Dépôt : `/home/user/Impots-but19` (branche claude/but19, partie de main après la fusion du
but 18). Le code se lance avec `PYTHONPATH=src .venv/bin/python` depuis ce dossier.

## Le contexte

Un simulateur fiscal français (OpenFisca-France sur une population synthétique de ménages
construite depuis l'enquête Emploi, calée sur des totaux publiés ; une couche d'entreprises
par cellules ; des comportements et une boucle macro qui mènent à une dette en 2035) chiffre
les programmes des candidats à la présidentielle de 2027 et les PLF/PLFSS. Le but 18 a
mesuré chaque instrument contre un total publié sur 2022, 2023 et 2024 :
`docs/verification/GRILLE.md` (le tableau), `docs/verification/lignes.json` (sources,
tolérances), `reports/verification/passe_*.json` (les mesures), `src/impots/verification.py`
(la passe), D-362 à D-364 dans `docs/DECISIONS.md` (lire D-364 en entier). L'erreur est un
biais de structure, stable d'une année à l'autre.

Le propriétaire veut maintenant **comprendre chaque écart** pour le corriger, puis pouvoir
**prouver au public la démarche** : chaque nombre doit pouvoir s'expliquer, se vérifier et
se faire varier par un lecteur qui n'a pas lu le dépôt.

## Les règles absolues

* **Ne modifie rien dans `src/`, `scripts/`, `tests/`, `etudes/`, `reports/`, `site/`,
  `docs/` sauf ton fichier de sortie.** Ne commite rien, ne pousse rien. Tes scripts
  d'essai vont dans `/tmp/diag_<ton nom>/`.
* **Ne touche jamais `src/impots/population/calibrate.py`** (lecture permise).
* **N'ouvre aucune évaluation préalable de PLF/PLFSS** ni `data/interim/textes_retro/`,
  `data/interim/triage_retro/`, `chiffrages_preregistres/` : un banc futur en dépend.
* **La mémoire est partagée** (15 Go, 4 cœurs, six agents en même temps). Jamais de passe
  sur la population entière. Un essai se fait sur un échantillon de **20 000 ménages au
  plus** (tirés au hasard, graine fixe, poids multipliés pour garder le total), une passe
  à la fois, et seulement si `free -g` montre au moins 5 Go disponibles ; sinon attends.
  Préfère lire les rapports déjà écrits et le parquet de la population (polars, colonnes
  choisies) à refaire des passes.
* **Le réseau** : les sources publiques (insee.fr, impots.gouv.fr, data.economie.gouv.fr,
  securite-sociale.fr, caf.fr, drees.solidarites-sante.gouv.fr, legifrance) sont
  permises en lecture ; certaines refusent le conteneur, dis-le. Toute source citée porte
  son URL exacte et le tableau ou la page ; **n'invente aucun nombre** : un nombre sans
  source se dit « non trouvé ».
* **Ne masque rien** : une hypothèse non vérifiée se dit hypothèse ; une mesure faite sur
  échantillon se dit sur échantillon, avec sa taille.

## La sortie

Un seul fichier, `docs/diagnostics/<ton nom>.md`, **en français**, lignes de 92 caractères
au plus, écrit pour deux lecteurs : le propriétaire (qui décide du correctif) et, plus
tard, un lecteur public intelligent qui n'a pas lu le code. Plan imposé :

1. **L'écart, en une phrase** (la ligne de la grille, ses trois années).
2. **Ce que le modèle fait** : la chaîne exacte, du fichier de données à la variable
   OpenFisca, avec les chemins de code (`fichier:ligne`).
3. **Ce que la statistique publique compte** : la définition exacte du total publié, son
   champ, sa source.
4. **La décomposition de l'écart** : chaque cause, chiffrée quand tu as pu la mesurer (dis
   comment), sinon dite hypothèse ; la somme des causes mesurées contre l'écart total.
5. **Ce que l'écart fait aux études** : quels candidats ou articles en dépendent, et si
   l'écart de niveau se reporte sur un coût de réforme (différence de deux passes) ou s'y
   annule. Les pages sont dans `docs/etudes/*.md`.
6. **Le correctif proposé** : ce qu'il faut changer, les données nécessaires (déjà dans
   `data/raw/MANIFEST.json` ou à télécharger, avec l'URL), le coût, le risque, et le
   pronostic de la ligne de la grille après correctif (une fourchette).
7. **Comment l'expliquer au public** : trois à six phrases simples, et le graphique ou le
   tableau qui le prouverait à un lecteur sceptique ; ce qu'un lecteur pourrait faire
   varier lui-même.

Ta réponse finale : un résumé de dix lignes au plus et le chemin du fichier.
