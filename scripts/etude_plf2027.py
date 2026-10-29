"""L'étude du PLF 2027 (D-286, but 1) : le scénario de l'art. 15.

    python scripts/etude_plf2027.py ecrire               # le scénario de l'art. 15

Les passes et la page de l'étude sont celles de la commande (D-301) :
`impots etude lancer plf2027 --ou "..."` et `impots etude ecrire plf2027`, sur la définition
`etudes/plf2027.json`. Reste ici ce que l'étude a écrit une fois, avant ses passes.

RIEN N'EST SAISI. Les articles 2 et 3 sont les scénarios enregistrés le 2026-10-02. Celui
de l'art. 15 est écrit ici depuis `reforms/plf2027_art_15.json`, la réforme que son
enregistrement a chiffrée, et borné à 2027 (D-288) : le texte rétablit la CEBGE pour cet
exercice seul.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = ROOT / "scenarios"
REFORMS = ROOT / "reforms"
CREATED = "2026-10-28"


def art15(reforms: Path = REFORMS) -> Any:
    """The art. 15 scenario: the firm reform its registration priced, for 2027 alone."""
    sys.path.insert(0, str(ROOT / "src"))
    from impots import scenarios
    from impots.api.schemas import ReformSpec
    from impots.entreprises.reforms import FirmReformSpec

    firm = FirmReformSpec.model_validate(json.loads(
        (reforms / "plf2027_art_15.json").read_text(encoding="utf-8")))
    return scenarios.Scenario(
        name="plf2027_art_15", reform=ReformSpec(), year=2027, created=CREATED,
        source=("PLF 2027 (AN, texte n° 3210), art. 15 — Mise à contribution des grandes "
                "entreprises. Volet chiffré : le troisième exercice de la CEBGE, à 15,7 % "
                "et 31,4 %, seuil de 1,5 Md€ (I de l'article), la réforme que "
                "`reforms/plf2027_art_15.json` porte et que son enregistrement a chiffrée."),
        note=("Ne porte PAS la contribution sur le résultat d'exploitation des transporteurs "
              "maritimes (II). Le texte rétablit la CEBGE pour l'exercice 2027 seul : la "
              "mesure est bornée à cette année (D-288)."),
        firm_reform=firm, annees=(2027,))


def main(args: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="what", required=True)
    sub.add_parser("ecrire")
    parser.parse_args(args)
    print(f"-> {art15().save(SCENARIOS)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
