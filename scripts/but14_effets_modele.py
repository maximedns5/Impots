"""L'effet des décisions 1 à 3 de D-336 sur Δb 2035, sans passe (`reports/but14_effets_modele.md`).

Le choc synthétique d'un point d'IR permanent de `docs/audit_but14/chaine_min.py` ; Attal
et Mélenchon reconstruits depuis leurs rapports commités : coûts par an et par vue du
rapport annuel, impulsions par instrument au prorata de la première année (deltas du
rapport de première année, couche des ménages). « Avant » est l'arithmétique de cedce46
(éteint ou tenu, sans borne), écrite ici à part ; « après » est relue par `rejouer`.

    PYTHONPATH=src .venv/bin/python scripts/but14_effets_modele.py
"""

from __future__ import annotations

import json
from pathlib import Path

from impots.macro import store as macro_store_module
from impots.predictif import montecarlo, rejouer, retroaction

ROOT = Path(__file__).resolve().parents[1]
TABLES = retroaction.replay_tables(
    macro_store_module.load(),
    ["impot_sur_le_revenu", "csg", "cotisations_salaries", "cotisations_employeurs", "tva"])
READ = TABLES["horizons"]
#: The study frame's start, as `chaine_min.py` reproduces it: s0 by reproduction.
P0, S0 = -0.029870353480509815, 0.5505
START = {"gdp_eur": 2991.056e9, "debt_ratio": 1.15693757321829,
         "implicit_rate": 0.01882827582292081, "receipts_ratio": P0 + S0,
         "spending_ratio": S0}
CONFIGS = [("avant : éteint, non borné", "eteint", False),
           ("avant : tenu, non borné", "tenu", False),
           ("décision 1 : lue, non borné", "lue", False),
           ("décisions 1 et 2 : lue, borné", "lue", True),
           ("décision 2 seule : éteint, borné", "eteint", True),
           ("décision 2 seule : tenu, borné", "tenu", True)]
MAP = {"ir": "impot_sur_le_revenu", "cdhr": "impot_sur_le_revenu", "csg_imposable": "csg",
       "csg_deductible": "csg", "crds": "csg", "csg_ij": "csg",
       "cotisations_salariales": "cotisations_salaries",
       "cotisations_employeur": "cotisations_employeurs"}


def _interp(row: dict, h: int) -> float:
    if h in READ:
        return row[str(h)]
    lo = max(x for x in READ if x < h)
    hi = min(x for x in READ if x > h)
    return row[str(lo)] + (h - lo) / (hi - lo) * (row[str(hi)] - row[str(lo)])


def _response(instrument: str, h: int, theta: float, persistence: str,
              bounded: bool) -> tuple[float, float]:
    table = TABLES["instruments"][instrument]
    if persistence == "lue" or h <= 3:
        at = h
    elif persistence == "eteint":
        return 0.0, 0.0
    else:
        at = 3
    centre = _interp(table["pib"], at)
    m = centre + (2 * theta - 1) * table["sd"]
    if bounded:
        m = max(0.0, m)
    f = (_interp(table["solde"], at) + table["brut"]) * m / centre
    if bounded:
        f = min(f, table["brut"])
    return m, f


def delta(start: dict, costs: list, impulses: list, theta: float, persistence: str,
          bounded: bool) -> list[float]:
    """Δb (points) par an : dépense gelée en volume, croissance 1 % + 2 %, taux tenu."""
    g = 1.01 * 1.02 - 1
    factor = 1.02 / (1 + g)
    r = start["implicit_rate"]
    y_eur, s, b = start["gdp_eur"], start["spending_ratio"], start["debt_ratio"]
    gdp, ref = [], []
    for _ in costs:
        y_eur *= 1 + g
        s *= factor
        b = b * (1 + r) / (1 + g) - (start["receipts_ratio"] - s)
        gdp.append(y_eur)
        ref.append(b)
    covered = sorted({i for yr in impulses for i, v in yr.items() if v}
                     & set(TABLES["instruments"]))
    units = {i: [yr.get(i, 0.0) * 100 / (TABLES["instruments"][i]["brut"] * y)
                 for yr, y in zip(impulses, gdp, strict=True)] for i in covered}
    debt, out = 0.0, []
    for k in range(len(costs)):
        gap = phi = 0.0
        for i in covered:
            for j in range(k + 1):
                step = units[i][j] - (units[i][j - 1] if j else 0.0)
                if step:
                    m, f = _response(i, k - j + 1, theta, persistence, bounded)
                    gap += step * m / 100
                    phi += step * f / 100
        debt = debt * (1 + r) / (1 + g) - (-costs[k] / gdp[k] + phi)
        out.append(((ref[k] + debt) / (1 + gap) - ref[k]) * 100)
    return out


def table(name: str, start: dict, costs: list, impulses: list) -> None:
    print(f"\n### {name}\n")
    print("| configuration | θ = 0 | θ = ½ | θ = 1 |")
    print("|---|---:|---:|---:|")
    for label, persistence, bounded in CONFIGS:
        values = [delta(start, costs, impulses, t, persistence, bounded)[-1]
                  for t in (0.0, 0.5, 1.0)]
        print(f"| {label} | {values[0]:+.2f} | {values[1]:+.2f} | {values[2]:+.2f} |")


def payload_of(start: dict, views: dict, first_year: int = 2026) -> dict:
    """The fields `rejouer` reads, built from the reconstruction."""
    (aged_costs, aged_imp), (frozen_costs, frozen_imp) = views["vieillie"], views["figee"]
    years = [{"year": first_year + k, "mechanical_aged_eur": aged_costs[k],
              "mechanical_frozen_eur": frozen_costs[k],
              "statistiques": {"vieillie": {"impulses": aged_imp[k], "canaux": None},
                               "figee": {"impulses": frozen_imp[k], "canaux": None}}}
             for k in range(len(aged_costs))]
    return {"years": years, "rejeu": {
        "start": start, "looped": True, "behavioural": False, "lignes": {},
        "box_rows": [rejouer.MACRO_ROW], "macro": TABLES,
        "cadre": {"growth": {"real": 0.01, "prices": 0.02},
                  "spending": {"rule": "gele_en_volume", "growth": None},
                  "taux": {"reference": [start["implicit_rate"]] * len(aged_costs),
                           "marginal": start["implicit_rate"]}}}}


def candidate(name: str) -> tuple[dict, dict]:
    folder = ROOT / "reports" / "etudes" / f"presidentielle_{name}"
    first = json.loads((folder / f"premiere_annee_pres2027_{name}_programme.json")
                       .read_text(encoding="utf-8"))
    response = first["response"].get("menages", first["response"])
    deltas, cost0 = response["deltas"], -response["behavioural"]["mechanical"]
    shares: dict[str, float] = {}
    # The employer's contributions are the super-gross wage less the gross (API).
    employer = deltas.get("salaire_super_brut", 0.0) - deltas.get("salaire_brut", 0.0)
    if employer:
        shares["cotisations_employeurs"] = -employer / cost0
    for key, value in deltas.items():
        if key in MAP and value:
            shares[MAP[key]] = shares.get(MAP[key], 0.0) - value / cost0
    report = json.loads((folder / f"predictif_pres2027_{name}_programme.json")
                        .read_text(encoding="utf-8"))
    st = report["start"]
    start = {"gdp_eur": st["gdp_eur"], "debt_ratio": st["debt_ratio"],
             "implicit_rate": st["implicit_rate"],
             "receipts_ratio": st["primary_balance"] + S0, "spending_ratio": S0}
    print(f"\n{name} : impulsion par euro de coût des ménages {shares}")
    views = {}
    for view, key in (("vieillie", "mechanical_aged_eur"), ("figee", "mechanical_frozen_eur")):
        rows = report["years"]
        costs = [r[key] for r in rows]
        menages = [(r.get("mechanical_by_layer") or {}).get(view, {}).get("menages", r[key])
                   for r in rows]
        impulses = [{i: s * c for i, s in shares.items()} for c in menages]
        suffix = "aged" if view == "vieillie" else "frozen"
        written = {p["persistence"]: round(p["years"][-1][f"delta_{suffix}"] * 100, 2)
                   for p in report["side_by_side"]}
        mine = {p: round(delta(start, costs, impulses, 0.5, p, False)[-1], 2)
                for p in ("eteint", "tenu")}
        print(f"  contrôle {view} : rapport {written}, reconstruit {mine}")
        table(f"{name.capitalize()}, vue {view}", start, costs, impulses)
        views[view] = (costs, impulses)
    return start, views


def main() -> None:
    gdp = [START["gdp_eur"] * 1.0302 ** (k + 1) for k in range(10)]
    costs = [0.01 * y for y in gdp]
    impulses = [{"impot_sur_le_revenu": c} for c in costs]
    table("Choc synthétique : un point de PIB d'IR en moins, permanent", START, costs,
          impulses)
    cases = {"choc IR d'un point": payload_of(START, {"vieillie": (costs, impulses),
                                                       "figee": (costs, impulses)})}
    for name in ("attal", "melenchon"):
        start, views = candidate(name)
        cases[name.capitalize()] = payload_of(start, views)
    print("\n### Monte-Carlo sous « lue » (2 000 tirages, graine fixe), Δb 2035\n")
    print("| cas | vue | P(Δb > 0) | q5 | q50 | q95 | θ½ |")
    print("|---|---|---:|---:|---:|---:|---:|")
    for name, payload in cases.items():
        monte = montecarlo.run(payload)
        for view in ("vieillie", "figee"):
            read, q = monte["vues"][view], monte["vues"][view]["quantiles"]
            half = rejouer.at_theta(payload, {rejouer.MACRO_ROW: 0.5}, view=view,
                                    persistence="lue").delta[-1] * 100
            print(f"| {name} | {view} | {read['p_hausse']:.3f} | {q['q05'] * 100:+.2f} | "
                  f"{q['q50'] * 100:+.2f} | {q['q95'] * 100:+.2f} | {half:+.2f} |")


if __name__ == "__main__":
    main()
