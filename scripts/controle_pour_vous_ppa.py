"""Le contrôle de « Pour vous » sur la prime d'activité (but 29, volet `cas`, D-631, D-632).

Le cas type de la Drees (fiche 04 du panorama « Minima sociaux et prestations sociales »,
éditions 2024 et 2025) : une personne seule sans enfant, locataire du parc privé, au Smic
à temps plein. Le modèle : le même ménage par OpenFisca (`impots.cas_types`), au barème de
janvier 2024 et de janvier 2025, le salaire au Smic brut de janvier de l'arbre toute
l'année et les années d'avant, le loyer au plafond de l'aide au logement en zone 2 pour une
personne seule (l'hypothèse préenregistrée, D-631) ; à côté, sans juger, le loyer médian
de la population (D-630). Écrit `reports/jumeau/controle_pour_vous_ppa.json`.

    PYTHONPATH=src python scripts/controle_pour_vous_ppa.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SORTIE = ROOT / "reports" / "jumeau" / "controle_pour_vous_ppa.json"
#: Le juge (D-631, amendement) : les nombres du résumé de la recherche, non aveugles.
PUBLIE = {2024: {"ppa": 222.0, "revenu_disponible": 1621.0},
          2025: {"ppa": 246.0, "revenu_disponible": 1673.0}}
PLAFOND = ("prestations_sociales", "aides_logement", "allocations_logement", "locatif",
           "formule", "l_plafonds_loyers", "par_zone", "zone_2", "personnes_seules")


def tolerance(publie: float) -> float:
    return max(5.0, 0.03 * abs(publie))


def mois(annee: int, loyer: float | None) -> dict[str, float]:
    from impots.api.schemas import Adult, HouseholdInput, Logement
    from impots.cas_types import _simulation
    from impots.engine import situations
    from impots.engine.reforms import resolve
    from impots.engine.system import baseline

    p = baseline().parameters
    janvier = f"{annee}-01-01"
    smic = float(p(janvier).marche_travail.salaire_minimum.smic.smic_b_mensuel)
    plafond = float(resolve(p, PLAFOND)(janvier))
    loyer = plafond if loyer is None else loyer
    h = HouseholdInput(adults=[Adult(salaire_brut_annuel=12 * smic, annee_naissance=1986)],
                       logement=Logement(statut="locataire_vide", loyer_mensuel=loyer,
                                         zone_apl=2))
    sim = _simulation(baseline(), situations.build_situation(h, annee, True), annee)
    m = f"{annee}-01"
    lire = {nom: float(sim.calculate(nom, m)[0]) for nom in
            ("ppa", "aide_logement", "rsa", "salaire_net")}
    rd = float(sim.calculate("revenu_disponible", str(annee))[0])
    return {"smic_brut_mensuel": smic, "loyer": loyer, "plafond_zone_2": plafond, **lire,
            "revenu_disponible_annuel_sur_12": rd / 12.0,
            "revenu_du_mois": lire["salaire_net"] + lire["ppa"] + lire["aide_logement"]
            + lire["rsa"]}


def main() -> int:
    from impots import cas_types

    n = cas_types.niveaux()
    loyer_pop = float(n["loyer_median_par_taille_2024"][1])
    out: dict = {"commit": subprocess.run(["git", "rev-parse", "HEAD"], text=True,
                                          capture_output=True, cwd=ROOT).stdout.strip(),
                 "decision": "D-631, D-632", "publie": PUBLIE, "annees": {}, "verdicts": {}}
    for a in PUBLIE:
        out["annees"][a] = {"plafond": mois(a, None), "loyer_population": mois(a, loyer_pop)}
    v = out["verdicts"]
    for a, pub in PUBLIE.items():
        x = out["annees"][a]["plafond"]
        v[f"C1_{a}"] = {"modele": x["ppa"], "publie": pub["ppa"],
                        "tient": abs(x["ppa"] - pub["ppa"]) <= tolerance(pub["ppa"])}
        for cle in ("revenu_disponible_annuel_sur_12", "revenu_du_mois"):
            v[f"C3_{a}_{cle}"] = {"modele": x[cle], "publie": pub["revenu_disponible"],
                                  "ecart_pct": 100 * (x[cle] / pub["revenu_disponible"] - 1),
                                  "tient": abs(x[cle] / pub["revenu_disponible"] - 1) <= 0.03}
    dm = out["annees"][2025]["plafond"]["ppa"] - out["annees"][2024]["plafond"]["ppa"]
    dp = PUBLIE[2025]["ppa"] - PUBLIE[2024]["ppa"]
    v["C2"] = {"modele": dm, "publie": dp, "rapport": dm / dp,
               "tient": 0.8 <= dm / dp <= 1.2}
    SORTIE.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
