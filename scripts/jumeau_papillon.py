"""Le papillon d'un programme, regardé d'un œil critique (but 27, volet `papillon`, D-500 à
D-503) : `python scripts/jumeau_papillon.py [slug]` écrit `reports/papillon/<slug>.json`.

Le jumeau seulement, en secondes : aucune passe sur la population. θ½ partout sauf dit ;
les θ du financement à ½ (D-481). Chaque nombre d'une convention le dit (`conventions`).
"""

from __future__ import annotations

import dataclasses
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from impots import site_jumeau  # noqa: E402
from impots.jumeau import navigateur  # noqa: E402
from impots.jumeau import papillon as pa  # noqa: E402
from impots.jumeau.financement import comptes  # noqa: E402

CONV = "parts_premiere_annee"
FIN = {"financement_a16_part_cnav": 0.5, "financement_compensation": 0.5}


def r(x: float, d: int = 3) -> float:
    return round(float(x), d)


def court(e: dict) -> dict:
    out = {"dette_2035": r(e["dette_pts"][-1]), "b9_2026": r(e["b9"][0], 2),
           "b9_2035": r(e["b9"][-1], 2), "pib_2035": r(e["pib_pct"][-1])}
    if "emploi_total" in e:
        out["emploi_2035"] = r(e["emploi_total"][-1], 1)
    return out


def serie(e: dict) -> dict:
    return {k: [r(x) for x in v] for k, v in e.items()}


def lancer(S, mesures, cle, mode="structurel", theta=None):
    tr, th = pa.trajectoire(S, mesures, cle=cle, mode=mode, theta=theta)
    return tr, th, pa.ecarts(tr)


def main(slug: str = "melenchon") -> Path:
    S = navigateur.Session(site_jumeau.donnees())
    cle_p, seules = pa.cles(S, slug)
    out: dict = {"candidat": slug, "theta": "½ pour chaque θ lu", "vues": {}}

    for vue in ("figee", "vieillie"):
        V: dict = {}
        # --- la somme, au bit
        V["somme_couts"] = {str(a): v for a, v in pa.verifier_somme(S, slug, vue, CONV).items()}
        ms = pa.mesures_seules(S, slug, vue)
        V["interaction"] = {str(a): {"cout": r(ms[-1].couts[a]),
                                     "cotisations_employeurs": r(
                                         ms[-1].impulsions[a]["cotisations_employeurs"])}
                            for a in ms[-1].annees}
        # --- le programme : réduit (les études) et structurel (mesures seules)
        trr, _, er = lancer(S, [S.mesure(cle_p, vue)], cle_p, mode="reduit")
        trs, ths, es = lancer(S, ms, cle_p, theta=FIN)
        V["programme"] = {"reduit": serie(er), "structurel_mesures_seules": serie(es),
                          "court": {"reduit": court(er), "structurel": court(es)}}
        V["identites"] = {"structurel": pa.identites(trs, ms),
                          "reduit": pa.identites(trr, [S.mesure(cle_p, vue)])}
        c = comptes.decomposer(trs, ms, ths)
        res = comptes.resume(c)
        V["sous_secteurs"] = {s: {"b9_2026": d["b9"]["ecart"][0], "b9_2035": d["b9"]["ecart"][-1],
                                  "dette_2035": d["dette"]["ecart"][-1]}
                              for s, d in res["sous_secteurs"].items()}
        V["sous_secteurs_residus"] = {k: float(v) for k, v in res["residus"].items()}
        V["compensation_2026"] = {k: v[0] for k, v in res["compensation"].items()}
        V["cascade_simple"] = {"structurel": pa.cascade_simple(trs),
                               "reduit": pa.cascade_simple(trr)}
        # --- mesure par mesure
        M: dict = {}
        somme = {"dette_2035": 0.0, "b9_2035": 0.0, "emploi_2035": 0.0}
        for m, c_ in zip(ms, [*seules, cle_p], strict=True):
            nom = m.identifiant.removeprefix(f"pres2027_{slug}_")
            _, _, e_s = lancer(S, [m], c_, theta=FIN)
            d = {"structurel": court(e_s), "conventions": {k: sorted(set(v.values()))
                                                           for k, v in m.conventions.items()}}
            if c_ != cle_p:
                _, _, e_r = lancer(S, [S.mesure(c_, vue)], c_, mode="reduit")
                d["reduit"] = court(e_r)
                d["b9_structurel"] = [r(x, 2) for x in e_s["b9"]]
            for k in somme:
                somme[k] += d["structurel"].get(k, 0.0)
            M[nom] = d
        V["mesures"] = M
        V["somme_des_mesures"] = {k: r(v) for k, v in somme.items()}
        V["interaction_jumeau"] = {k: r(court(es)[k] - somme[k]) for k in somme}
        # --- le point d'indice, avant et après la rémunération publique (D-500)
        c_pi = f"pres2027_{slug}_point_indice_10"
        if c_pi in S.candidats:
            avant = S.mesure(c_pi, vue, CONV)
            apres = S.mesure_structurel(c_pi, vue, CONV)
            _, _, ea = lancer(S, [avant], c_pi, theta=FIN)
            _, _, ep = lancer(S, [apres], c_pi, theta=FIN)
            red = S.mesure(c_pi, vue)
            sans = dataclasses.replace(red, impulsions={
                a: {i: v for i, v in imp.items() if i not in pa.INSTRUMENTS_PAIE}
                for a, imp in red.impulsions.items()})
            _, _, rr = lancer(S, [red], c_pi, mode="reduit")
            _, _, rs = lancer(S, [sans], c_pi, mode="reduit")
            prog = S.mesure(cle_p, vue)
            corr = dataclasses.replace(prog, impulsions={
                a: {i: v - red.impulsions.get(a, {}).get(i, 0.0) * (i in pa.INSTRUMENTS_PAIE)
                    for i, v in imp.items()} for a, imp in prog.impulsions.items()})
            _, _, rp = lancer(S, [corr], cle_p, mode="reduit")
            V["programme"]["court"]["reduit_sans_paie_publique"] = court(rp)
            V["point_indice"] = {"structurel_avant": court(ea), "structurel_apres": court(ep),
                                 "reduit_publie": court(rr),
                                 "reduit_sans_paie_publique": court(rs)}
        # --- en regard : la prime de risque
        _, entrees, _, _ = S._modele("structurel", ms[0], cle_p)
        _, entrees_r, _, _ = S._modele("reduit", S.mesure(cle_p, vue), cle_p)
        V["prime_de_risque"] = {
            "structurel": {str(t): [r(x) for x in pa.prime_de_risque(trs, entrees, t)[
                "dette_pts"]] for t in (0.0, 0.5, 1.0)},
            "reduit": {str(t): [r(x) for x in pa.prime_de_risque(trr, entrees_r, t)[
                "dette_pts"]] for t in (0.0, 0.5, 1.0)}}
        # --- l'étude simplifiée
        V["sensibilites"] = pa.sensibilites(S, ms, cle=cle_p, theta=FIN)
        # --- les cas qui se retournent : le signe de l'emploi ou du solde de 2035 d'une
        # mesure seule qui change quand un θ va de 0 à 1
        if vue == "figee":
            ret = {}
            for m, c_ in zip(ms[:-1], seules, strict=True):
                lignes = pa.sensibilites(S, [m], cle=c_, theta=FIN)
                for x in lignes:
                    for champ in ("emploi", "b9"):
                        a0, a1 = x[f"{champ}_a_zero"], x[f"{champ}_a_un"]
                        if a0 is not None and a0 * a1 < 0:
                            ret.setdefault(m.identifiant.removeprefix(
                                f"pres2027_{slug}_"), []).append(
                                {"theta": x["cle"], "champ": champ, "a_zero": r(a0, 2),
                                 "centre": r(x[f"{champ}_centre"], 2), "a_un": r(a1, 2)})
            V["retournements_theta"] = ret
        out["vues"][vue] = V

    out["dividendes_pfu"] = {str(t): pa.dividendes_pfu(t) for t in (0.0, 0.5, 1.0)}
    from impots.jumeau.blocs.menages import charger as charger_menages

    pm = charger_menages()
    ref = pm.references[max(pm.references)]
    marchand = pm.part_marchande * ref["emploi_salarie"]
    out["emploi_exonerations"] = {str(t): pa.emploi_exonerations(
        2.0, t, emploi_marchand_milliers=marchand) for t in (0.0, 0.5, 1.0)}
    out["emploi_marchand_milliers"] = r(marchand, 1)

    dest = ROOT / "reports" / "papillon" / f"{slug}.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float) + "\n",
                    encoding="utf-8")
    return dest


if __name__ == "__main__":
    print(main(*sys.argv[1:]))
