"""Le jumeau rejoue l'histoire (but 23, lot 6) : estimer sur 2011-2017, noter sur 2018-2019
et 2022-2024, comme D-417 le préenregistre. Ce code rejoue la révision
« rejeu_histoire_r4 » (D-438, `rejeu_histoire.CAS`) : à lancer seulement après le commit
poussé de D-438 ; le rapport porte son commit et refuse un arbre modifié. Le premier juge
(D-420, `rejeu_histoire.json`) se refait sur fe9434f, la deuxième révision (D-423,
`rejeu_histoire_r2.json`) sur 8119f63, la troisième (D-429, `rejeu_histoire_r3.json`)
sur a399c47 ; ce script refuse de les écraser.

    PYTHONPATH=src python scripts/jumeau_rejeu_histoire.py [--sortie reports/jumeau/...]

Ce qui tourne, dans l'ordre : l'estimation des θ de `rejeu_histoire.ESTIMES` (les autres
à ½), chacun sous sa loi a priori (`a_priori.lois`, D-424) ; la note de l'estimation et celle du test aux θ estimés ; la note du test à θ½,
pour dire ce que l'estimation apporte ; chaque note contre le naïf et contre le naïf
mécanique (l'amendement de D-417). Depuis r4 (D-438) : le test aux θ estimés noté aussi
sans 2023 (`rejeu_histoire.SCHEMA_SANS_2023`), et le critère du but (D-431) lu comme
D-438 le préenregistre : un θ identifié contre sa loi de D-424 (`meta_analyse` du YAML
quand la loi est tirée des données), sur la plage du calcul, du côté de θ estimé ; et
le naïf mécanique battu sur plus de 3 cibles du test, avec et sans 2023.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from impots.jumeau import a_priori, thetas, votees
from impots.jumeau import apprentissage as app
from impots.jumeau import rejeu_histoire as rh
from impots.jumeau.blocs.entreprises import population_depuis
from impots.jumeau.cellules import Cellules

RACINE = Path(__file__).resolve().parents[1]


def _commit() -> str:
    sale = subprocess.run(["git", "status", "--porcelain", "--", "src", "scripts"],
                          capture_output=True, text=True, cwd=RACINE, check=True).stdout
    if sale.strip():
        raise SystemExit(f"arbre modifié, le rapport n'aurait pas de commit :\n{sale}")
    return subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True,
                          cwd=RACINE, check=True).stdout.strip()


def _note(note: app.Note) -> dict:
    return {"periode": note.periode, "tenues": note.tenues, "naif_tenues": note.naif_tenues,
            "battues": note.battues, "mecanique_tenues": note.mecanique_tenues,
            "battues_mecanique": note.battues_mecanique, "cibles": len(note.lignes),
            "non_notees": dict(note.non_notees),
            "lignes": [{"cible": ligne.cible, "tolerance": ligne.tolerance,
                        "reqm": ligne.reqm, "reqm_naif": ligne.reqm_naif,
                        "reqm_mecanique": ligne.reqm_mecanique,
                        "tenue": ligne.tenue, "bat_naif": ligne.bat_naif,
                        "bat_mecanique": ligne.bat_mecanique,
                        "erreurs_mecanique": ligne.erreurs_mecanique,
                        "erreurs": ligne.erreurs, "erreurs_naif": ligne.erreurs_naif}
                       for ligne in note.lignes]}


def _loi_d424(cle: str, lois: dict) -> a_priori.Loi:
    """La loi de D-424 de θ : celle du calcul, sauf quand le YAML garde à part la
    méta-analyse d'une loi tirée des données (b, D-438)."""
    entree = a_priori.lire()[cle]
    if "meta_analyse" not in entree:
        return lois[cle]
    m = entree["meta_analyse"]
    return a_priori.loi_depuis(float(m["estimation"]), float(m["ecart_type"]),
                               a_priori.plages()[cle], m["source"])


def _critere(estimation: app.Estimation, lois: dict, notes: dict) -> dict:
    """Le critère du but (D-431), lu comme D-438 le préenregistre."""
    thetas_ = {}
    for k in rh.ESTIMES:
        loi = _loi_d424(k, lois)
        t, sigma = estimation.theta[k], estimation.ecarts_types[k]
        s = loi.ecart_bas if t < loi.moyenne else loi.ecart_haut
        thetas_[k] = {"theta": t, "ecart_type": sigma, "loi_d424": {
            "moyenne": loi.moyenne, "ecart_bas": loi.ecart_bas, "ecart_haut": loi.ecart_haut},
            "s_d424": s, "seuil": s / 2.0, "identifie": sigma < s / 2.0}
    ids = [k for k, v in thetas_.items() if v["identifie"]]
    battues = {n: notes[n]["battues_mecanique"] for n in ("test", "test_sans_2023")}
    return {"thetas": thetas_, "identifies": ids, "bat_mecanique": battues,
            "atteint": bool(ids) and all(v > 3 for v in battues.values())}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sortie", type=Path,
                        default=RACINE / "reports" / "jumeau" / f"{rh.CAS}.json")
    args = parser.parse_args()
    for precedent in rh.CAS_PRECEDENTS:
        if args.sortie.resolve() == (RACINE / "reports" / "jumeau"
                                     / f"{precedent}.json").resolve():
            raise SystemExit(f"le rapport de {precedent} reste ; la révision s'écrit "
                             f"sous son nom, {rh.CAS}.json")
    commit = _commit()
    exogenes = rh.exogenes_publies()
    cellules, base = Cellules.lire(), votees.mesures()
    simuler = rh.simulateur(population=population_depuis(), cellules=cellules,
                            exogenes=exogenes, observateur=rh.etat_publie,
                            votees=base)
    mecanique = rh.simulateur_mecanique(exogenes=exogenes, cellules=cellules,
                                        observateur=rh.etat_publie, votees=base)
    cibles = rh.cibles(100.0 * exogenes.croissance_emploi)
    fixes = {k: 0.5 for k in thetas.REGISTRE if k not in rh.ESTIMES}
    lois = a_priori.lois()
    estimation = app.estimer(app.residus(rh.SCHEMA, simuler, rh.etat_publie,
                                         cibles), rh.ESTIMES, fixes, a_priori=rh.A_PRIORI,
                             lois=lois)
    notes = {}
    for nom, periode, theta, schema in (
            ("estimation", "estimation", estimation.theta, rh.SCHEMA),
            ("test", "test", estimation.theta, rh.SCHEMA),
            ("test_sans_2023", "test", estimation.theta, rh.SCHEMA_SANS_2023),
            ("test_theta_demi", "test", dict.fromkeys(thetas.REGISTRE, 0.5), rh.SCHEMA)):
        note, _ = app.evaluer(periode, schema, theta, simuler, rh.etat_publie,
                              cibles, rh.NON_NOTEES, mecanique)
        notes[nom] = _note(note)
    rapport = {"decision": rh.DECISION, "cas": rh.CAS, "commit": commit,
               "exogenes": {"croissance_tendance": exogenes.croissance_tendance,
                            "croissance_emploi": exogenes.croissance_emploi,
                            "croissance_demande_mondiale":
                                exogenes.croissance_demande_mondiale},
               "estimation": {"theta": {k: estimation.theta[k] for k in rh.ESTIMES},
                              "ecarts_types": dict(estimation.ecarts_types),
                              "ecarts_a_priori": dict(estimation.ecarts_a_priori),
                              "lois": {k: {"moyenne": lois[k].moyenne,
                                           "ecart_bas": lois[k].ecart_bas,
                                           "ecart_haut": lois[k].ecart_haut,
                                           "source": lois[k].source}
                                       for k in rh.ESTIMES},
                              "identifies": list(estimation.identifies),
                              "cout": estimation.cout,
                              "cout_initial": estimation.cout_initial,
                              "iterations": estimation.iterations},
               "notes": notes, "critere_but": _critere(estimation, lois, notes)}
    args.sortie.parent.mkdir(parents=True, exist_ok=True)
    args.sortie.write_text(json.dumps(rapport, indent=1, ensure_ascii=False) + "\n",
                           encoding="utf-8")
    print(args.sortie)


if __name__ == "__main__":
    main()
