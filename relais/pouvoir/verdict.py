"""D-592 : le modèle (modele.json) contre l'Insee (FPS 2020, fig. 4 ; FPS 2022, fig. 1, 4, 5)."""
import json, sys
m = json.load(open(sys.argv[1]))
def pauv_ok(mod, juge):
    if abs(mod - juge) <= 0.1: return True
    return abs(juge) > 0.2 and 0.5 <= mod / juge <= 2
out = {}
if "ppa_2019" in m:
    p = m["ppa_2019"]; J = -0.7
    b = p["cellules"]["mesuree"]["pauvrete_points"] if p["distribution"].startswith("mes") else p["cellules"]["approchee"]["pauvrete_points"]
    out["ppa"] = {"juge_pauvrete": J, "a": p["micro"]["pauvrete_points"],
                  "b_mesuree": p["cellules"]["mesuree"]["pauvrete_points"],
                  "b_approchee": p["cellules"]["approchee"]["pauvrete_points"],
                  "distribution": p["distribution"], "b_note": b, "tient": pauv_ok(b, J),
                  "a_tient": pauv_ok(p["micro"]["pauvrete_points"], J),
                  "controle_b_vs_a": abs(b - p["micro"]["pauvrete_points"]) <= 0.1,
                  "gini_a": p["micro"]["gini_points"], "d9d1_a": p["micro"]["d9_d1"],
                  "gini_b": p["cellules"]["mesuree"]["gini_points"], "cout": p["micro"]["cout_md"],
                  "gain_nv": p["micro"]["gain_nv_par_decile"]}
if "ir_2020" in m:
    p = m["ir_2020"]; mi = p["micro"]
    J = [0, 0, 10, 20, 70, 140, 230, 290, 250, 160]; Jm = 120; Jp = 0.232; Jc = 5.39
    sJ = sum(J); g = mi["gain_nv_par_decile"]; s = sum(g)
    b = p["cellules"]["mesuree"]["pauvrete_points"]
    out["ir"] = {"cout": mi["cout_md"], "juge_cout": Jc, "gain_moyen": mi["gain_nv_moyen"],
                 "juge_gain": Jm, "gain_tient": abs(mi["gain_nv_moyen"] / Jm - 1) <= 0.3,
                 "decile_max": mi["decile_max"], "juge_max": 8,
                 "max_tient": abs(mi["decile_max"] - 8) <= 1,
                 "d1d3": 100 * sum(g[:3]) / s, "juge_d1d3": 100 * sum(J[:3]) / sJ,
                 "d8d10": 100 * sum(g[7:]) / s, "juge_d8d10": 100 * sum(J[7:]) / sJ,
                 "gain_par_decile": g,
                 "pauv_a": mi["pauvrete_points"], "pauv_b_mesuree": b,
                 "pauv_b_approchee": p["cellules"]["approchee"]["pauvrete_points"],
                 "juge_pauv": Jp, "pauv_tient": pauv_ok(b, Jp),
                 "pauv_a_tient": pauv_ok(mi["pauvrete_points"], Jp),
                 "controle_b_vs_a": abs(b - mi["pauvrete_points"]) <= 0.1,
                 "gini_a": mi["gini_points"], "d9d1_a": mi["d9_d1"]}
    o = out["ir"]; o["d1d3_tient"] = abs(o["d1d3"] - o["juge_d1d3"]) <= 5
    o["d8d10_tient"] = abs(o["d8d10"] - o["juge_d8d10"]) <= 10
print(json.dumps(out, indent=1, ensure_ascii=False))
