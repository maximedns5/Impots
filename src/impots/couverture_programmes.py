"""Le tableau de couverture des programmes présidentiels (but 21, D-380).

    python -m impots.couverture_programmes --sortie docs/presidentielle/couverture.md

Pour chacun des fichiers de `programmes/`, ce que le relevé compte : les mesures relevées,
celles qui énoncent un paramètre, les vagues, celles que l'outil chiffre, et les refus
par porte ; puis, pour toutes les mesures ensemble, les refus par porte, en distinguant
ceux dont le candidat donne lui-même un taux ou un montant. Le tableau ne chiffre rien :
c'est un décompte des champs des fichiers, écrit avant tout chiffrage du but 21.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

from impots import programmes as pg


def compter(directory: Path | None = None) -> dict[str, Any]:
    """Le décompte, par candidat et par porte."""
    lignes = []
    portes: Counter[str] = Counter()
    portes_parametrees: Counter[str] = Counter()
    for slug in pg.lister(directory):
        p = pg.charger(slug, directory)
        c = p.couverture()
        refusees = len(p.refusees()) - c["vagues"]
        lignes.append({"slug": slug, "candidat": p.candidat, "releve": p.releve.isoformat(),
                       "mesures": c["mesures"], "parametrees": c["parametrees"],
                       "vagues": c["vagues"], "chiffrees": c["chiffrees"],
                       "refusees": refusees, "portes": c["refus_par_porte"]})
        for m in p.refusees():
            if m.refus.porte == "vague":
                continue
            portes[m.refus.porte] += 1
            if m.precision == "parametree":
                portes_parametrees[m.refus.porte] += 1
    total = {k: sum(row[k] for row in lignes)
             for k in ("mesures", "parametrees", "vagues", "chiffrees", "refusees")}
    return {"lignes": lignes, "total": total, "portes": dict(portes),
            "portes_parametrees": dict(portes_parametrees)}


def _pct(n: int, d: int) -> str:
    return f"{100 * n / d:.0f} %" if d else "—"


def markdown(compte: dict[str, Any], titre: str) -> str:
    t = compte["total"]
    out = [f"# {titre}", "",
           f"Écrit le {date.today().isoformat()} par `python -m impots.couverture_programmes`, "
           "depuis les seuls fichiers de `programmes/` : un décompte, rien n'y est chiffré.",
           "",
           f"**{t['mesures']} mesures relevées** sur {len(compte['lignes'])} programmes : "
           f"{t['chiffrees']} chiffrées ({_pct(t['chiffrees'], t['mesures'])}), "
           f"{t['vagues']} vagues ({_pct(t['vagues'], t['mesures'])}), "
           f"{t['refusees']} refusées par une porte ({_pct(t['refusees'], t['mesures'])}).",
           "", "## Par candidat", "",
           "| candidat | relevé le | relevées | paramétrées | vagues | chiffrées | refusées |",
           "|---|---|---:|---:|---:|---:|---:|"]
    for row in sorted(compte["lignes"], key=lambda r: (-r["chiffrees"], -r["mesures"],
                                                      r["candidat"])):
        out.append(f"| {row['candidat']} | {row['releve']} | {row['mesures']} | "
                   f"{row['parametrees']} | {row['vagues']} | {row['chiffrees']} | "
                   f"{row['refusees']} |")
    out += ["", "## Par porte", "",
            "Une porte dit ce qui manque à l'outil pour chiffrer une mesure. « Chiffrée par le "
            "candidat » : la mesure énonce un taux ou un montant, et seule la porte l'arrête.",
            "", "| porte | refusées | dont chiffrées par le candidat | ce qui manque |",
            "|---|---:|---:|---|"]
    for porte, n in sorted(compte["portes"].items(), key=lambda kv: (-kv[1], kv[0])):
        out.append(f"| `{porte}` | {n} | {compte['portes_parametrees'].get(porte, 0)} | "
                   f"{pg.PORTES.get(porte, '')} |")
    out += ["", "## Par candidat et par porte", ""]
    for row in sorted(compte["lignes"], key=lambda r: r["candidat"]):
        portes = ", ".join(f"`{k}` {v}" for k, v in row["portes"].items() if k != "vague")
        out.append(f"* **{row['candidat']}** — {portes or 'aucun refus par porte'}")
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--sortie", type=Path, required=True)
    parser.add_argument("--titre", default="La couverture des programmes présidentiels")
    args = parser.parse_args(argv)
    args.sortie.write_text(markdown(compter(), args.titre), encoding="utf-8")
    print(f"-> {args.sortie}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
