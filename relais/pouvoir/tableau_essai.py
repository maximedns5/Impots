import json, sys, time
from impots import site_jumeau
from impots.jumeau import navigateur
from impots.jumeau.mesures import CONVENTION_PARTS
s = navigateur.Session(json.loads(json.dumps(site_jumeau.donnees())))
for cand in sys.argv[1:]:
    t0 = time.time()
    out = json.loads(navigateur.impacts_json(s, json.dumps({"candidat": cand, "tirages": 50})))
    print(cand, "refus", out.get("refus"), round(time.time() - t0, 1), "s")
    imp = out.get("impacts") or out.get("dimensions") or out
    dims = imp["dimensions"] if "dimensions" in imp else imp
    for d in dims:
        if "erreur" in d:
            print("  ", d["cle"], "ERREUR", d["erreur"]); continue
        i = d["indicateurs"][0]
        print("  ", d["cle"], d["statut"], i["cle"], [round(x, 2) if x is not None else None for x in i["valeurs"][:1] + i["valeurs"][-1:]],
              "bande", None if i["bas"] is None else (round(i["bas"][-1], 2), round(i["haut"][-1], 2)))
    print("  modules en erreur", imp.get("modules_en_erreur"))
