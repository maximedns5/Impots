import json, time, sys
import numpy as np
from impots import site_jumeau
from impots.jumeau import navigateur
from impots.jumeau.impacts import pouvoir
s=navigateur.Session(json.loads(json.dumps(site_jumeau.donnees())))
tir=int(sys.argv[1]) if len(sys.argv)>1 else 0
for cle in sys.argv[2:] or ["pres2027_retailleau_programme","pres2027_attal_programme"]:
    choix={"mode":"structurel","vue":"figee","candidat":cle,"convention":"parts_premiere_annee"}
    out=s.calculer({**choix,"theta":{}})
    th={t["cle"]:0.5 for t in out["thetas"]}
    t=time.time()
    traj,dep,refus=pouvoir.trajectoire_tiree(s,{**choix,"theta":th},tirages=tir)
    t1=time.time()-t
    d=pouvoir.pouvoir_achat(traj,None,dep,s.cellules)
    print(cle, "traj", round(t1,1),"s dim", round(time.time()-t-t1,1))
    for i in d.indicateurs:
        print(" ",i.cle, i.unite, np.round(i.valeurs[[0,4,9]],2), None if i.bas is None else (np.round(i.bas[[0,9]],2), np.round(i.haut[[0,9]],2)))
        if i.cle in ("reel_uc","reel_pct","gagnants"):
            for g in ["D1","D2","D5","D9","D10","Familles monoparentales","Personnes seules"]:
                print("    ",g, np.round(i.par_groupe[g][[0,9]],2))
    print("  prix", np.round(d.notes["prix_consommation_pct"],3))
    from impots.jumeau.impacts import entente
    t=time.time()
    e=entente.entente(traj,None,dep,s.cellules)
    print(" entente", round(time.time()-t,1), "s", e.notes["distribution"][:30], e.notes["reference"])
    print("  pauvrete types ref", {k:round(v,1) for k,v in e.notes["pauvrete_types_reference_pct"].items()})
    for i in e.indicateurs:
        print(" ",i.cle, i.unite, np.round(i.valeurs[[0,4,9]],3), None if i.bas is None else (np.round(i.bas[[0,9]],3), np.round(i.haut[[0,9]],3)))
        if i.par_groupe:
            for g,v in i.par_groupe.items(): print("    ",g, np.round(v[[0,9]],2))
