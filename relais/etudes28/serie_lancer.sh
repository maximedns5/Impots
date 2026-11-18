#!/bin/bash
# D-556 et D-558, étape 3 : les dix-sept études, une à la fois, sous le verrou commun.
#   setsid nohup bash $S/etudes28/serie_lancer.sh > $S/etudes28/serie.log 2>&1 &
# Une étude interrompue se reprend en relançant ce script : `lancer` saute les rapports
# déjà écrits sur le même commit.
S=/tmp/claude-0/-home-user-Impots/8c1eda0e-eb4f-5530-a9a9-deab4a4ca18f/scratchpad
cd /home/user/Impots-b28-etudes
export PYTHONPATH=src
PY=/home/user/Impots-but19/.venv/bin/python
ETUDES="presidentielle_melenchon presidentielle_roussel presidentielle_ruffin presidentielle_tondelier presidentielle_kazib presidentielle_bouamrane presidentielle_attal presidentielle_retailleau presidentielle_lisnard presidentielle_philippe presidentielle_le_pen plfss2027 plf2027 presidentielle_glucksmann presidentielle_labib presidentielle_arthaud presidentielle_zemmour"
echo "=== commit $(git rev-parse --short HEAD) $(date) $(sha256sum data/processed/population_2024.parquet | cut -c1-12)"
for n in $ETUDES; do
  echo "== $n $(date)"
  flock $S/passe.lock $PY -m impots.population.cli etude lancer $n \
    --ou "conteneur cloud, 15 Go, 4 cœurs, une file"
  echo "rc=$? $(date)"
done
echo FIN $(date)
