#!/bin/bash
# D-556 et D-558, étapes 1 et 2 : à lancer par le coordinateur, avec l'accord du propriétaire.
# Worktree /home/user/Impots-b28-etudes, branche claude/but28-etudes, population de D-553
# (5ace8bb6…), src/ propre, HEAD poussé.
set -e
cd /home/user/Impots-b28-etudes
export PYTHONPATH=src
PY=/home/user/Impots-but19/.venv/bin/python
# Les douze de D-556 : leurs rapports sont ceux de 5a68669, gelés puis retirés.
DOUZE="presidentielle_melenchon presidentielle_roussel presidentielle_ruffin presidentielle_tondelier presidentielle_kazib presidentielle_bouamrane presidentielle_attal presidentielle_retailleau presidentielle_lisnard presidentielle_philippe presidentielle_le_pen plfss2027"
# Les cinq de D-558 n'ont plus de rapports (retirés à 5a68669, D-403) : leur gel de aa22293
# reste l'« avant », `etude avant` ne peut pas le refaire (il n'a rien à lire).
sha256sum data/processed/population_2024.parquet | grep -q ^5ace8bb6 || { echo "pas la population de D-553"; exit 1; }
[ -z "$(git status --porcelain src)" ] || { echo "src/ n'est pas propre"; exit 1; }
# 1. Le gel : celui de aa22293 (but 21) remplacé par la série de 5a68669 (but 22)
for n in $DOUZE; do
  git rm -q reports/etudes/$n/avant/serie.json
  $PY -m impots.population.cli etude avant $n
done
# 2. Les rapports de 5a68669 retirés (tout sauf avant/), commit, push
for n in $DOUZE; do git ls-files reports/etudes/$n | grep -v '/avant/' | xargs -r git rm -q; done
for n in $DOUZE; do git add reports/etudes/$n/avant/serie.json; done
git commit -q -m "D-556 : la série de 5a68669 figée, ses rapports retirés avant la série

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01SjST5i6Y2xn5QqodujLdHp"
git push -q
