"""Le choc combiné du bloc `travail` et les formes de la diffusion, sur Mélenchon (but 28,
volet `interaction`, D-540 et suivantes).

Le jumeau seul, en secondes, aucune passe : les mesures portées aux nombres des passes de
D-521 (convention « premiere_annee_d521 », `mesure_melenchon_b27`), en structurel, θ½,
financement à ½.

* le Smic seul (la passe complète, comme D-534), vues figée et vieillie ;
* le programme par ses mesures seules et l'interaction de sa passe (D-502), figée et
  vieillie ; les paires Smic × exonérations et Smic × point d'indice, Δ(i+j) − Δi − Δj ;
  au réglage par défaut, les 21 paires (`paires_jumeau`) ;
* chaque réglage des formes (`travail.formes`) et de la boucle prix (`commerce.prix`),
  quand le code les porte.

    PYTHONPATH=src python scripts/interaction_b28.py <sortie.json> [rapide]
"""

from __future__ import annotations

import contextlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ICI = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("mesure_melenchon_b27",
                                               ICI / "mesure_melenchon_b27.py")
mm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mm)

CLE = "pres2027_melenchon_smic_1700_net"
VUES = ("figee", "vieillie")
CHAMPS = ("emploi_2035", "b9_2035", "dette_2035")
#: Les réglages essayés : (formes du bloc `travail`, réglage de la boucle prix).
REGLAGES: dict[str, tuple[dict[str, str], str | None]] = {
    "defaut": ({}, None),
    "recentrage_nouveau": ({"recentrage": "nouveau"}, None),
    "profil_croissant": ({"profil": "croissant"}, None),
    "profil_decroissant": ({"profil": "decroissant"}, None),
    "portee_2": ({"portee": "2"}, None),
    "recentrage_et_portee_2": ({"recentrage": "nouveau", "portee": "2"}, None),
    "prix_harasztosi_lindner": ({}, "harasztosi_lindner"),
    "prix_diagnostic_juge": ({}, "diagnostic_juge"),
}


def commit() -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ICI.parent,
                          capture_output=True, text=True, check=True).stdout.strip()


@contextlib.contextmanager
def reglage(formes: dict[str, str], prix: str | None):
    from impots.jumeau.blocs import commerce, travail

    with contextlib.ExitStack() as pile:
        if formes:
            pile.enter_context(travail.formes(**formes))
        if prix:
            pile.enter_context(commerce.prix(prix))
        yield


def sessions() -> tuple[Any, Any]:
    from impots.jumeau import papillon as pa

    s_smic = mm.session()
    mm.redimensionner(s_smic, CLE, mm.lire("complet_propres_smic"))
    prog = mm.session()
    cle_p, seules = pa.cles(prog, "melenchon")
    for c_ in seules:
        n = mm.COURTS[c_.removeprefix("pres2027_melenchon_")]
        mm.redimensionner(prog, c_, mm.lire(f"rapide_union_{n}"))
    mm.redimensionner(prog, cle_p, mm.lire("rapide_union_programme"))
    return s_smic, prog


def court(S: Any, mesures: list[Any], cle: str) -> dict[str, float]:
    from impots.jumeau import papillon as pa

    tr, _ = pa.trajectoire(S, mesures, cle=cle, theta=mm.FIN)
    return mm.court_(pa.ecarts(tr))


def mesurer(s_smic: Any, prog: Any, *, paires_toutes: bool) -> dict[str, Any]:
    from impots.jumeau import papillon as pa

    out: dict[str, Any] = {}
    cle_p, _ = pa.cles(prog, "melenchon")
    for vue in VUES:
        V: dict[str, Any] = {}
        V["smic_seul"] = court(s_smic, [s_smic.mesure_structurel(
            CLE, vue, "parts_premiere_annee")], CLE)
        ms = pa.mesures_seules(prog, "melenchon", vue)
        V["programme"] = court(prog, ms, cle_p)
        par = {mm.COURTS[m.identifiant.removeprefix("pres2027_melenchon_")]: m
               for m in ms[:-1]}
        un = {n: court(prog, [par[n]], cle_p) for n in ("smic", "exo", "pi")}
        V["seules"] = un
        V["paires"] = {}
        for a, b in (("smic", "exo"), ("smic", "pi")):
            ab = court(prog, [par[a], par[b]], cle_p)
            V["paires"][f"{a}+{b}"] = {
                "ensemble": {k: ab[k] for k in CHAMPS},
                "ecart_a_la_somme": {k: round(ab[k] - un[a][k] - un[b][k], 4)
                                     for k in CHAMPS}}
        if paires_toutes and vue == "figee":
            V["paires_21"] = mm.paires_jumeau(prog, vue)
        out[vue] = V
    return out


def main(dest: str, rapide: bool = False) -> None:
    from impots.jumeau.blocs import commerce, travail

    s_smic, prog = sessions()
    res: dict[str, Any] = {"commit": commit(), "convention": mm.CONVENTION_D521,
                           "reglages": {}}
    porte = hasattr(travail, "formes"), hasattr(commerce, "prix")
    for nom, (formes, prix) in REGLAGES.items():
        if (formes and not porte[0]) or (prix and not porte[1]):
            continue
        with reglage(formes, prix):
            res["reglages"][nom] = {"formes": formes, "prix": prix,
                                    **mesurer(s_smic, prog,
                                              paires_toutes=(nom == "defaut"
                                                             and not rapide))}
        print(nom, json.dumps(res["reglages"][nom]["figee"]["smic_seul"]), flush=True)
    Path(dest).parent.mkdir(parents=True, exist_ok=True)
    Path(dest).write_text(json.dumps(res, ensure_ascii=False, indent=1) + "\n",
                          encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1], rapide=len(sys.argv) > 2 and sys.argv[2] == "rapide")
