# Volet pouvoir : ce qui reste (état au 18/11, 05:06 UTC)

La chaîne détachée chaine2.sh tourne dans /home/user/Impots-b29-pouvoir-passes, un worktree
figé à 4cbe38f. Elle enchaîne nv, ppa_passe puis ir_passe, chacune sous le verrou.
Son journal : chaine2.log, nv.log, ppa_passe.log, ir_passe.log (ici).

Quand chaine2.log affiche « fin » :
1. Copier /home/user/Impots-b29-pouvoir-passes/reports/jumeau/niveaux_de_vie_cellules.json
   dans /home/user/Impots-b29-pouvoir/reports/jumeau/, puis commiter (D-640 : les nombres
   de D-593 sur la mesurée, avec tableau_essai.py).
2. Dans le worktree des passes :
   PYTHONPATH=src /home/user/Impots-but19/.venv/bin/python scripts/juges_pouvoir_b29.py rapport
   C'est léger, sans verrou. Copier ensuite reports/verification/juges_pouvoir_b29/modele.json.
3. python3 verdict.py <modele.json>. Les juges y sont codés :
   - prime 2019 : FPS 2020, fig. 4, pauvreté −0,7 point (sur 2019 comme en consolidé) ;
     Gini et D9/D1 sans juge par mesure (seule une part de 72 % est publiée, pas notée).
   - impôt 2020 : FPS 2022, dossier D2 (et non FPS 2021, qui n'a pas ce dossier ;
     data/raw/insee_fps2022_d2_donnees.xlsx). Fig. 1 : coût 5,39 Md€ ; fig. 4 : par
     dixième 0,0,10,20,70,140,230,290,250,160 €, moyenne 120 € ; fig. 5 : pauvreté
     +0,232 point. Gini sans juge. C'est un effet consolidé, sur la législation 2021.
4. D-592 : écrire le résultat et ne retoucher aucune tolérance.
