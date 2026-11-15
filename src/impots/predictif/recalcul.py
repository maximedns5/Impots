"""A report's company-creations slope changed without a pass (D-427).

The owner moved ε, the slope of the creations channel, from 0,20 to 0,043 (D-427). Every
report that reads the channel carries its parameters (`creations.instantane`) and,
beside them, everything a pass and its replay derived from them: the paths in both views
under each persistence, the θ box (every year priced and the first year carried), the
Monte-Carlo, the readings and the channel's own paths. Those fields are what
`predictif.rejouer` refits from the report alone, to the bit (D-336, D-403): this module
rewrites them at another ε, and nothing else. The passes are not run again; the report
keeps its commit and says the recomputation (`recalcul`).

THE CONTROL. At the ε a report carries, `recalculer` gives back to the byte the paths,
the box read every year priced and the channel's paths. Three families it gives back to
about 1e-12 only (3e-12 at worst, relative, on the studies of D-427), because the report
wrote them with an arithmetic the replay no longer follows to the ulp: the box with the
first year carried (`exploration.trajectory`, the chain, not the replay), the Monte-Carlo
and the readings (written by the replay before D-403 put the channel last). `AU_PRES`
names them; the test holds both.

A report whose levies on firms and capital are zero every year does not read ε
(`concerne`): its parameters say the new slope, and no number of it is rewritten — none
depends on ε, the channel being zero at every slope.

INSTRUMENTS THE CHANNEL STOPS READING (D-440). The owner took the CVAE and the C3S out of
the channel (`creations.PRODUCTION`). A report carries ΔP summed over its instruments, not
each one; the firm layer that priced them is a pass on the firm cells, of seconds, which
gives back each tax by year and view (`scripts/recaler_creations.py --instruments`, which
checks it gives back the firm layer's cost the report carries, to the bit). `retirer`
takes those amounts out of ΔP, drops the instruments from both snapshots and refits every
number from the report's own fields, as `recalculer` does; `recalcul.instruments` says it
and keeps ΔP before, so that the report before is replayed from the report after.
"""

from __future__ import annotations

import copy
import itertools
import json
from collections.abc import Mapping, Sequence
from typing import Any

from impots.predictif import creations, montecarlo, rejouer

#: The fields the replay refits to about 1e-12, not to the bit (module docstring).
AU_PRES = ("theta_box/paths/first_year", "monte_carlo", "lectures")
#: Their relative tolerance in the control.
TOLERANCE_AU_PRES = 1e-11

#: The views a report writes, and its keys.
_CLES = {"vieillie": ("reform_aged", "delta_aged"),
         "figee": ("reform_frozen", "delta_frozen")}


class RecalculError(ValueError):
    """The report is not one this module rewrites."""


def ecrire(payload: Mapping[str, Any]) -> str:
    """A report as the chain writes it (`cli`, `json.dumps`, indent 2)."""
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


def concerne(payload: Mapping[str, Any]) -> bool:
    """Whether the report reads the channel with a levy that moves: only then does ε."""
    block = (payload.get("rejeu") or {}).get("creations")
    return bool(block) and any(float(v) != 0.0 for vs in block["variations"].values()
                               for v in vs)


def _theta(payload: Mapping[str, Any]) -> dict[str, float]:
    """θ by row: the box's rows at the θ the report read them at, every claimed row at ½."""
    rows = list(payload["rejeu"]["box_rows"])
    lu = (payload.get("lectures") or {}).get("theta") or {}
    theta = {**dict.fromkeys(payload["rejeu"]["lignes"], 0.5),
             **dict.fromkeys(rows, 0.5), **lu}
    return theta


def _replay(payload: Mapping[str, Any]) -> dict[str, Any]:
    """What `annuel.build` hands the Monte-Carlo and the readings."""
    return {"years": [{k: row[k] for k in ("year", "basis", "mechanical_frozen_eur",
                                          "mechanical_aged_eur", "statistiques")}
                      for row in payload["years"]],
            "rejeu": payload["rejeu"]}


def _porte(payload: Mapping[str, Any]) -> dict[str, Any]:
    """The first year carried as a share of GDP (`annuel`'s « first_year » reading)."""
    return {"years": [payload["years"][0]], "carry": rejouer.CARRY,
            "horizon": len(payload["years"]), "rejeu": payload["rejeu"]}


def _coins(rows: list[str], theta: Mapping[str, float]) -> list[dict[str, float]]:
    """`theta.corners`' order: the rows sorted, each at 0 or 1."""
    keys = sorted(rows)
    return [{**theta, **dict(zip(keys, combo, strict=True))}
            for combo in itertools.product((0.0, 1.0), repeat=len(keys))]


def recalculer(payload: Mapping[str, Any], elasticite: Mapping[str, float] | None = None,
               *, decision: str | None = None, date: str | None = None) -> dict[str, Any]:
    """The report at the slope `elasticite` (centre, bas, haut), or at its own when None.
    With a new slope, `decision` and `date` name the recomputation in `recalcul`."""
    out = copy.deepcopy(dict(payload))
    rejeu = out.get("rejeu") or {}
    if not rejeu.get("creations") or "creations" not in out:
        raise RecalculError("rapport sans le canal des créations : rien à recalculer")
    if out.get("carry") is not None:
        raise RecalculError("un rapport reporté ne porte pas ses chemins")
    avant = dict(rejeu["creations"]["parametres"]["elasticite"])
    if elasticite is not None:
        nouveau = {"centre": float(elasticite["centre"]), "bas": float(elasticite["bas"]),
                   "haut": float(elasticite["haut"])}
        creations.Plage(**nouveau)
        rejeu["creations"]["parametres"]["elasticite"] = dict(nouveau)
        out["creations"]["parametres"]["elasticite"] = dict(nouveau)
    if not concerne(out):
        if elasticite is not None:
            out["recalcul"] = _marque(avant, rejeu, decision, date, out, nul=True)
        return out
    _refaire(out)
    if elasticite is not None:
        out["recalcul"] = _marque(avant, rejeu, decision, date, out, nul=False)
    return out


def _refaire(out: dict[str, Any]) -> None:
    """Every number the replay derives from the channel, refitted in place."""
    rejeu = out["rejeu"]
    theta = _theta(out)
    side = bool(out.get("side_by_side"))
    chemins = ([(s["persistence"], s["years"]) for s in out["side_by_side"]] if side
               else [(out.get("persistence"), out["years"])])
    lus: dict[tuple[Any, str], Any] = {}
    for persistence, rows in chemins:
        for view, (k_reform, k_delta) in _CLES.items():
            path = rejouer.at_theta(out, theta, view=view, persistence=persistence)
            lus[(persistence, view)] = path
            for row, r, d in zip(rows, path.reform, path.delta, strict=True):
                row[k_reform], row[k_delta] = r, d

    box = out.get("theta_box")
    if box:
        corners = _coins(box["rows"], theta)
        porte = _porte(out)
        for entry in box["paths"]:
            persistence = entry["persistence"]
            for view in _CLES:
                every = entry["every_year"][view]
                every["theta"] = lus[(persistence, view)].delta[-1]
                for pair, corner in zip(every["corners"], corners, strict=True):
                    pair[1] = rejouer.at_theta(out, corner, view=view,
                                               persistence=persistence).delta[-1]
                first = entry["first_year"][view]
                first["theta"] = rejouer.at_theta(porte, theta, view=view,
                                                  persistence=persistence).delta[-1]
                for pair, corner in zip(first["corners"], corners, strict=True):
                    pair[1] = rejouer.at_theta(porte, corner, view=view,
                                               persistence=persistence).delta[-1]

    replay = _replay(out)
    if out.get("monte_carlo") is not None:
        out["monte_carlo"] = montecarlo.run(replay)
    if out.get("lectures") is not None:
        from impots.predictif.annuel import _lectures

        out["lectures"] = _lectures(replay, dict(out["lectures"]["theta"]))

    block = rejeu["creations"]
    params = creations.depuis(block["parametres"])
    c = creations.productivite_a(block["theta"], params)
    gdp = rejouer.reference_path(rejeu, rejeu["start"], len(out["years"]))[0]
    years = [int(r["year"]) for r in out["years"]]
    for entry in out["creations"]["chemins"]:
        persistence = entry["persistence"]
        for view in _CLES:
            if view not in entry:
                continue
            effet = creations.effet([float(v) for v in block["variations"][view]], gdp,
                                    years, c=c, params=params,
                                    receipts_ratio=rejeu["start"]["receipts_ratio"])
            ends = {key: rejouer.at_theta(out, {**theta, rejouer.CREATIONS_ROW: key},
                                          view=view, persistence=persistence).delta[-1]
                    for key in (0.0, 1.0)}
            drawn = entry[view]
            drawn.update({**effet.payload(), "theta": block["theta"],
                          "preenregistrement": params.preenregistrement,
                          "boite": {"theta": lus[(persistence, view)].delta[-1],
                                    "c0": ends[0.0], "c1": ends[1.0]},
                          "delta_sans_creations": drawn["delta_sans_creations"]})


def retirer(payload: Mapping[str, Any], retraits: Mapping[str, Sequence[float]],
            instruments: Sequence[str], *, decision: str, date: str) -> dict[str, Any]:
    """The report without `instruments` in the channel (D-440): `retraits[view]`, their
    sum by year priced, euros, receipts positive, taken out of ΔP; the instruments dropped
    from both snapshots; every number refitted at the report's own slope."""
    out = copy.deepcopy(dict(payload))
    rejeu = out.get("rejeu") or {}
    if not rejeu.get("creations") or "creations" not in out:
        raise RecalculError("rapport sans le canal des créations : rien à recalculer")
    block = rejeu["creations"]
    snapshots = (block["parametres"], out["creations"]["parametres"])
    lus = [*snapshots[0]["instruments_entreprises"], *snapshots[0]["instruments_menages"]]
    if not instruments or not set(instruments) <= set(lus):
        raise RecalculError(f"instruments {list(instruments)} : pas tous lus par le rapport")
    if out.get("carry") is not None:
        raise RecalculError("un rapport reporté ne porte pas ses chemins")
    if (out.get("recalcul") or {}).get("instruments"):
        raise RecalculError("des instruments ont déjà été retirés de ce rapport")
    avant = copy.deepcopy(block["variations"])
    if set(retraits) != set(avant):
        raise RecalculError(f"vues {sorted(retraits)} contre {sorted(avant)}")
    for view, values in avant.items():
        if len(retraits[view]) != len(values):
            raise RecalculError(f"vue « {view} » : {len(retraits[view])} années retirées "
                                f"pour {len(values)}")
        block["variations"][view] = [float(v) - float(r)
                                     for v, r in zip(values, retraits[view], strict=True)]
    years = [str(r["year"]) for r in out["years"]]
    out["creations"]["prelevements_eur"] = {
        view: dict(zip(years, values, strict=True))
        for view, values in block["variations"].items()}
    for snapshot in snapshots:
        for key in ("instruments_entreprises", "instruments_menages"):
            snapshot[key] = [i for i in snapshot[key] if i not in instruments]
    _refaire(out)
    marque = dict(out.get("recalcul") or {})
    marque["instruments"] = {
        "decision": decision, "date": date, "retires": list(instruments),
        "objet": ("des instruments retirés du canal des créations, sans passe : leurs "
                  "montants, année par année, redonnés par la couche entreprises, sortis "
                  "des prélèvements du canal ; les chemins, la boîte, le Monte-Carlo, les "
                  "lectures et le canal refaits par le rejeu depuis les champs du rapport ; "
                  "la passe reste celle de « commit »"),
        "variations_avant": avant, "commit_passe": out.get("commit")}
    out["recalcul"] = marque
    return out


def _marque(avant: Mapping[str, float], rejeu: Mapping[str, Any], decision: str | None,
            date: str | None, out: Mapping[str, Any], *, nul: bool) -> dict[str, Any]:
    """The `recalcul` field: what changed, when, by which decision, on which pass."""
    objet = ("l'élasticité du canal des créations, changée sans passe ; aucun prélèvement "
             "sur les entreprises ou le capital ne bouge : aucun nombre ne change" if nul
             else "l'élasticité du canal des créations, changée sans passe : les chemins, "
             "la boîte, le Monte-Carlo, les lectures et le canal refaits par le rejeu "
             "depuis les champs du rapport ; la passe reste celle de « commit »")
    marque = {"decision": decision, "date": date, "objet": objet,
              "nombres_refaits": not nul, "elasticite_avant": dict(avant),
              "elasticite": dict(rejeu["creations"]["parametres"]["elasticite"]),
              "commit_passe": out.get("commit")}
    instruments = (out.get("recalcul") or {}).get("instruments")
    if instruments:
        marque["instruments"] = instruments
    return marque


def ecarts(a: Any, b: Any, chemin: str = "") -> list[tuple[str, Any, Any]]:
    """The leaves that differ, with their path (list indices left out)."""
    if isinstance(a, dict) and isinstance(b, dict):
        if list(a) != list(b):
            return [(chemin, list(a), list(b))]
        return [e for k in a for e in ecarts(a[k], b[k], f"{chemin}/{k}")]
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return [(chemin, len(a), len(b))]
        return [e for x, y in zip(a, b, strict=True) for e in ecarts(x, y, chemin)]
    return [] if a == b else [(chemin, a, b)]


def controle(texte: str) -> list[str]:
    """What a committed report, rewritten at the ε it carries, does not give back: to the
    byte, but the fields of `AU_PRES`, to `TOLERANCE_AU_PRES`. Empty when it holds."""
    payload = json.loads(texte)
    refait = ecrire(recalculer(payload))
    if refait == texte:
        return []
    fautes = []
    for ou, a, b in ecarts(json.loads(refait), payload):
        au_pres = any(ou.startswith("/" + f) for f in AU_PRES)
        if (au_pres and isinstance(a, float) and isinstance(b, float)
                and abs(a - b) <= TOLERANCE_AU_PRES * max(abs(b), 1e-300)):
            continue
        fautes.append(f"{ou} : {a!r} contre {b!r}")
    return fautes
