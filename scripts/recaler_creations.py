"""Les rapports d'études réécrits à l'élasticité déclarée du canal des créations (D-427).

    PYTHONPATH=src python scripts/recaler_creations.py --controle   # rien n'est écrit
    PYTHONPATH=src python scripts/recaler_creations.py              # les rapports réécrits

Sans passe : chaque rapport qui lit le canal est refait depuis ses propres champs
(`predictif.recalcul`), à l'ε de `predictif/parameters/creations_entreprises.yaml`. Le
contrôle refait chaque rapport à l'ε qu'il porte et le compare au fichier commité : à
l'octet près, sauf les champs de `recalcul.AU_PRES`, à `TOLERANCE_AU_PRES` près. Un
rapport dont les prélèvements sur les entreprises et le capital sont nuls ne lit pas ε :
seuls ses paramètres changent. Un rapport déjà à l'ε déclaré n'est pas touché.

    IMPOTS_FIRM_VINTAGE=2023 PYTHONPATH=src python scripts/recaler_creations.py --instruments

D-440 : la CVAE et la C3S sortent du canal (`creations.PRODUCTION`). Un rapport porte ΔP
sommé sur ses instruments ; la couche entreprises, une passe de quelques secondes sur ses
cellules, redonne chaque impôt par année et par vue. Elle doit redonner, au bit près, le
coût de la couche que le rapport porte (`mechanical_by_layer`), et, pour une mesure sans
réforme des ménages, ΔP lui-même : sinon rien n'est écrit. Les montants retirés sortent de
ΔP (`recalcul.retirer`) ; un rapport sans réforme des entreprises n'est pas touché.

    IMPOTS_FIRM_VINTAGE=2023 PYTHONPATH=src python scripts/recaler_creations.py --aligner

D-444 : les rapports sans réforme des entreprises listent encore la CVAE et la C3S, où
elles valent zéro ; elles sortent de leurs listes (`recalcul.aligner`), sans qu'aucun
nombre ne bouge. Le contrôle, avant d'écrire : le rapport aligné, ses deux listes rendues
et sa marque retirée, redonne le fichier commité à l'octet près, et il se redonne lui-même
refait à son ε (`recalcul.controle`).
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from impots.predictif import creations, recalcul

RACINE = Path(__file__).resolve().parents[1]
ETUDES = RACINE / "reports" / "etudes"
DECISION = "D-427"
DECISION_INSTRUMENTS = "D-440"
DECISION_ALIGNEMENT = "D-444"


def rapports() -> list[Path]:
    """Les rapports d'études qui portent le canal des créations."""
    out = []
    for chemin in sorted(ETUDES.glob("**/predictif_*.json")):
        d = json.loads(chemin.read_text(encoding="utf-8"))
        if isinstance(d, dict) and (d.get("rejeu") or {}).get("creations"):
            out.append(chemin)
    return out


def controle(chemin: Path) -> list[str]:
    """Ce que le rapport, refait à son ε, ne redonne pas : vide quand il tient."""
    return [f"{chemin.relative_to(RACINE)} {faute}"
            for faute in recalcul.controle(chemin.read_text(encoding="utf-8"))]


def retraits(payload: dict, instruments: tuple[str, ...]) -> dict[str, list[float]] | None:
    """Les montants de `instruments` que la passe a lus, par vue et par année, redonnés par
    la couche entreprises ; None sans réforme des entreprises. Refuse une couche qui ne
    redonne pas le rapport."""
    from impots import scenarios, service
    from impots.dette.scenarios import GrowthScenario

    if service.FIRM_VINTAGE != "2023":
        raise SystemExit("IMPOTS_FIRM_VINTAGE=2023 : le millésime des études")
    scenario = scenarios.load(payload["scenario"], None)
    if scenario.firm_reform is None or scenario.firm_reform.is_empty():
        return None
    cadre = payload["rejeu"]["cadre"]["growth"]
    growth = GrowthScenario(payload["growth_name"], cadre["real"], cadre["prices"])
    lus = payload["rejeu"]["creations"]["parametres"]["instruments_entreprises"]
    variations = payload["rejeu"]["creations"]["variations"]
    out: dict[str, list[float]] = {}
    for view, values in variations.items():
        out[view] = []
        for row, value in zip(payload["years"], values, strict=True):
            year = int(row["year"])
            if not scenario.applies(year):
                out[view].append(0.0)
                continue
            firm = service.firm_first_year(scenario.firm_reform, year, view=view,
                                           growth=growth)
            porte = row["mechanical_by_layer"][view]["entreprises"]
            if firm.cost != porte:
                raise SystemExit(f"{payload['scenario']} {year} {view} : la couche donne "
                                 f"{firm.cost!r}, le rapport porte {porte!r}")
            if scenario.reform_in(year).is_empty():
                lu = sum(float(firm.deltas.get(i, 0.0)) for i in lus)
                if abs(lu - float(value)) > 1e-9 * max(abs(float(value)), 1.0):
                    raise SystemExit(f"{payload['scenario']} {year} {view} : ΔP {value!r}, "
                                     f"la couche {lu!r}")
            out[view].append(sum(float(firm.deltas.get(i, 0.0)) for i in instruments))
    return out


def retirer_instruments() -> int:
    """D-440 : la CVAE et la C3S sortent des rapports qui les lisent."""
    instruments = creations.PRODUCTION
    for chemin in rapports():
        payload = json.loads(chemin.read_text(encoding="utf-8"))
        lus = payload["rejeu"]["creations"]["parametres"]["instruments_entreprises"]
        if not set(instruments) & set(lus):
            continue
        montants = retraits(payload, instruments)
        if montants is None or not any(v for vs in montants.values() for v in vs):
            continue
        refait = recalcul.retirer(payload, montants, instruments,
                                  decision=DECISION_INSTRUMENTS,
                                  date=date.today().isoformat())
        texte = recalcul.ecrire(refait)
        if recalcul.controle(texte):
            raise SystemExit(f"{chemin} : le rapport refait ne se redonne pas")
        chemin.write_text(texte, encoding="utf-8")
        print(f"  -> {chemin.relative_to(RACINE)}")
    return 0


def aligner() -> int:
    """D-444 : la CVAE et la C3S sortent des listes des rapports où elles valent zéro."""
    instruments = creations.PRODUCTION
    alignes = 0
    for chemin in rapports():
        texte = chemin.read_text(encoding="utf-8")
        payload = json.loads(texte)
        lus = payload["rejeu"]["creations"]["parametres"]["instruments_entreprises"]
        if not set(instruments) & set(lus):
            continue
        montants = retraits(payload, instruments)
        if montants is not None and any(v for vs in montants.values() for v in vs):
            raise SystemExit(f"{chemin} : la CVAE ou la C3S y bouge, ce n'est pas un "
                             f"alignement (D-440)")
        aligne = recalcul.aligner(payload, instruments, decision=DECISION_ALIGNEMENT,
                                  date=date.today().isoformat())
        refait = recalcul.ecrire(aligne)
        # Le contrôle : les listes rendues et la marque retirée, l'octet près ; puis le
        # rapport aligné, refait à son ε, se redonne.
        rendu = json.loads(refait)
        for cle in ("rejeu", None):
            bloc = (rendu[cle]["creations"] if cle else rendu["creations"])["parametres"]
            source = (payload[cle]["creations"] if cle else payload["creations"])
            bloc["instruments_entreprises"] = source["parametres"]["instruments_entreprises"]
            bloc["instruments_menages"] = source["parametres"]["instruments_menages"]
        del rendu["recalcul"]["instruments"]
        if recalcul.ecrire(rendu) != texte:
            raise SystemExit(f"{chemin} : aligné, il ne redonne pas le rapport commité")
        fautes = recalcul.controle(refait)
        if fautes:
            raise SystemExit(f"{chemin} : aligné, il ne se redonne pas : {fautes[:3]}")
        chemin.write_text(refait, encoding="utf-8")
        alignes += 1
        print(f"  -> {chemin.relative_to(RACINE)} : contrôle tenu, à l'octet")
    print(f"{alignes} rapports alignés, chacun contrôlé")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--controle", action="store_true")
    ap.add_argument("--instruments", action="store_true",
                    help="retirer la CVAE et la C3S du canal (D-440)")
    ap.add_argument("--aligner", action="store_true",
                    help="les retirer des listes où elles valent zéro (D-444)")
    args = ap.parse_args()
    cible = vars(creations.charger().elasticite)
    fautes = [f for c in rapports() for f in controle(c)]
    if fautes:
        print("\n".join(fautes[:20]), file=sys.stderr)
        print(f"contrôle refusé : {len(fautes)} écarts", file=sys.stderr)
        return 1
    print(f"contrôle : {len(rapports())} rapports refaits à leur ε")
    if args.controle:
        return 0
    if args.instruments:
        return retirer_instruments()
    if args.aligner:
        return aligner()
    for chemin in rapports():
        payload = json.loads(chemin.read_text(encoding="utf-8"))
        porte = payload["rejeu"]["creations"]["parametres"]["elasticite"]
        if porte == cible:
            continue
        refait = recalcul.recalculer(payload, cible, decision=DECISION,
                                     date=date.today().isoformat())
        chemin.write_text(recalcul.ecrire(refait), encoding="utf-8")
        print(f"  -> {chemin.relative_to(RACINE)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
