#!/bin/bash
S=/tmp/claude-0/-home-user-Impots/8c1eda0e-eb4f-5530-a9a9-deab4a4ca18f/scratchpad
L=$S/passe.lock; PY=/home/user/Impots-but19/.venv/bin/python
cd /home/user/Impots-b29-pouvoir-passes
date -u +"%F %T reprise ir_passe" >> $S/pouvoir/chaine2.log
flock $L env PYTHONPATH=src $PY scripts/juges_pouvoir_b29.py ir_passe > $S/pouvoir/ir_passe.log 2>&1
echo "ir_passe rc=$?" >> $S/pouvoir/chaine2.log
date -u +"%F %T fin" >> $S/pouvoir/chaine2.log
