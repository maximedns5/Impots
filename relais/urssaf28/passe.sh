#!/bin/bash
# Les passes de D-580 : population, grille 2024-2022, complément 2022, cellules, entrées,
# puis les rejeux (fin des exonérations, paire Smic × exonérations). Chaque étape sous le
# verrou commun, une à la fois : elles alternent avec la série des études.
cd /home/user/Impots-b28-point2
S=/tmp/claude-0/-home-user-Impots/8c1eda0e-eb4f-5530-a9a9-deab4a4ca18f/scratchpad
U=$S/urssaf28
L=$S/passe.lock
PY=/home/user/Impots-but19/.venv/bin/python
export PYTHONPATH=src
imp() { flock $L $PY -c "import sys; from impots.population.cli import main; sys.argv=['impots']+sys.argv[1:]; sys.exit(main())" "$@"; }
echo "=== commit $(git rev-parse --short HEAD) $(date)"
echo "=== build $(date)"; imp population build 2>&1 | grep -v -i warn; echo "rc=${PIPESTATUS[0]} $(date)"
cp data/processed/population_2024.parquet $U/population_d581.parquet
cp data/processed/population_2024.manifest.json $U/population_d581.manifest.json
sha256sum data/processed/population_2024.parquet
for a in 2024 2023 2022; do
  echo "=== $a $(date)"; imp verification passe --annee $a 2>&1 | grep -v -i "warning\|exoneration_degressive\|estimation_abattue"; echo "rc=${PIPESTATUS[0]} $a $(date)"
  cp reports/verification/passe_$a.json $U/passe_$a.json
done
echo "=== complément 2022 $(date)"; flock $L $PY scripts/ligne_bandeau_famille_tranche.py 2022 > $U/complement_2022.log 2>&1; echo "rc=$?"
echo "=== écrire $(date)"; imp verification ecrire 2>&1 | tail -5; echo "rc=${PIPESTATUS[0]}"
echo "=== cellules $(date)"; flock $L $PY scripts/jumeau_cellules.py --menages 30000 2>&1 | grep -v -i warn | tail -40; echo "rc=${PIPESTATUS[0]}"
echo "=== entrées $(date)"; flock $L $PY -m impots.jumeau.navigateur ecrire 2>&1 | tail -3; echo "rc=${PIPESTATUS[0]}"
flock $L $PY -m impots.site_population.agregats 2>&1 | tail -3; echo "rc=${PIPESTATUS[0]}"
echo "=== rejeux $(date)"
export EXOS28_SORTIE=$U/exos MESURE27_SORTIE=$U/mesure
echo "=== exos d581 $(date)"; flock $L $PY scripts/exos_decomposition_b28.py passe d581 $U/population_d581.parquet --controle 2>&1 | grep -v -i warn | tail -4; echo "rc=${PIPESTATUS[0]}"
for spec in "rapide_union_smic smic union" "rapide_union_exo exo union" "rapide_union_smic+exo smic,exo union"; do
  set -- $spec; echo "=== $1 $(date)"; flock $L $PY scripts/mesure_melenchon_b27.py passe $1 $2 rapide $3 2>&1 | grep -v -i warn | tail -2; echo "rc=${PIPESTATUS[0]}"
done
echo FIN $(date)
