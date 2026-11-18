#!/bin/bash
# D-556 → D-557 : les études du jumeau sur la population de D-553. Passes une à une sous le
# verrou commun ; le jumeau (secondes) hors verrou.
S=/tmp/claude-0/-home-user-Impots/8c1eda0e-eb4f-5530-a9a9-deab4a4ca18f/scratchpad
E=$S/etudes28
L=$S/passe.lock
cd /home/user/Impots-b28-etudes
PY=/home/user/Impots-but19/.venv/bin/python
export PYTHONPATH=src MESURE27_SORTIE=$E/mesure_d553 MESURE27_POPULATION=d553 \
  MESURE27_RAPPORT=reports/etudes/mesure_melenchon_b27/d553 \
  JUGES28_SORTIE=$S/suite28/juges_d553 BOUCLE28_SORTIE=$E/boucle
M=scripts/mesure_melenchon_b27.py
echo "=== commit $(git rev-parse --short HEAD) $(date) $(sha256sum data/processed/population_2024.parquet | cut -c1-12) $(sha256sum data/processed/jumeau_cellules_2024.json | cut -c1-12)"
f() { echo "=== $* $(date)"; flock $L "$@" 2>&1 | grep -v -i "warn\|estimation_abattue\|exoneration_degressive ="; echo "rc=${PIPESTATUS[0]} $(date)"; }
j() { echo "=== $* $(date)"; "$@" 2>&1 | grep -v -i "warn"; echo "rc=${PIPESTATUS[0]} $(date)"; }
f $PY $M passe rapide_but19_smic smic rapide propres /home/user/Impots-but19/data/processed/population_2024.parquet
f $PY $M passe complet_propres_smic smic complet propres
f $PY $M programme
f $PY scripts/boucle_b28.py passe cice
f $PY scripts/boucle_b28.py passe smic
j $PY $M analyser
j $PY $M jumeau
j $PY scripts/reaction_diffusion_b28.py reports/etudes/reaction_b28/diffusion_d557.json
j $PY scripts/interaction_b28.py reports/etudes/interaction_b28/defaut_d557.json
j $PY scripts/interaction_cice_b28.py reports/etudes/interaction_b28/cice_d557.json
j $PY scripts/boucle_b28.py jumeau passes
j $PY scripts/boucle_b28.py rapport resultats_d557 D-545 D-546 D-556 D-557
echo FIN $(date)
