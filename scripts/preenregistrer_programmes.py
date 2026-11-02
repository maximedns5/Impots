#!/usr/bin/env python
"""Préenregistrer les mesures chiffrées des programmes présidentiels (but 11, D-321).

Chaque mesure chiffrée d'un programme devient un cas aveugle, `pres2027_<slug>_<id>`, que le
chiffrage de l'Institut Montaigne (annoncé au premier trimestre 2027) notera. Le cas est
enregistré par la commande même des cas du PLF, sur la population vieillie jusqu'à l'année
du droit (`--vieillir plf2027`, but 10), avant que le juge ne publie : aucun chiffrage de tiers
n'est lu avant le commit des enregistrements (D-319).

Deux temps, chacun sur un commit propre :

* `--ecrire` : un scénario `scenarios/pres2027_*.json` par mesure des ménages, une réforme
  `reforms/pres2027_*.json` par mesure des entreprises, tirés du programme sans rien y
  ajouter ;
* `--enregistrer` : les cas, l'un après l'autre, depuis un worktree figé sur le commit qui
  porte ces fichiers.

La tolérance suit une règle par classe, écrite ici et dans D-321, la même pour chaque
candidat.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

PREFIXE = "pres2027"
JEU = "plf2027"
VINTAGE_MENAGES = "2024"
VINTAGE_ENTREPRISES = "2023"
ECHANTILLON = 20_000

#: Les classes de tolérance (D-321). Une mesure qui ne touche que le haut de la
#: distribution est moins sûre : la population a de bons agrégats et des queues faibles
#: (README, L1). Les entreprises suivent la tolérance de l'art. 15 du PLF 2027.
CLASSES: dict[str, tuple[float, float, str]] = {
    "menages": (0.25, 200e6,
                "Mesure des ménages sur une large assiette (salaires, CSG, quotient "
                "familial) : le moteur retrouve ses agrégats à quelques pour cent. Le juge "
                "chiffre peut-être une autre année que 2026 (la croissance nominale en écarte "
                "de 3 % par an) et contre la continuité des politiques, pas le droit gelé."),
    "haut": (0.40, 200e6,
             "Mesure qui ne touche que le haut de la distribution (au-delà de 250 000 € par "
             "part, ou le plafond du quotient familial) : la population a de bons agrégats et "
             "des queues faibles (README, L1), et le juge chiffre peut-être une autre année."),
    "entreprises": (0.30, 200e6,
                    "Mesure des entreprises sur le millésime synthétique de 2023 vieilli par "
                    "le PIB nominal (D-246), la tolérance de l'art. 15 du PLF 2027. La CVAE "
                    "disparaît du droit en 2028 : un juge qui chiffre contre ce droit-là la "
                    "compte pour moins que le droit de 2026."),
    "consommation": (0.30, 200e6,
                     "Mesure de TVA ou d'accise sur la consommation imputée du Budget de "
                     "famille 2017 vieillie (D-323), à volumes constants et répercutée en "
                     "entier dans les prix : le juge peut compter une réaction de la "
                     "consommation, une répercussion partielle, une autre année, et la "
                     "vérification des agrégats (D-325) dit l'écart de l'assiette."),
}
#: La classe de chaque mesure chiffrée, par id ; une mesure sans classe est refusée.
CLASSE = {
    "exonerations_au_dela_2_smic": "menages",
    "tranche_ir_60": "haut",
    "lp22_part_pleine_2e_enfant": "menages",
    "a16_droit_au_brut": "menages",
    "a18_suppression_cvae": "entreprises",
    "r19_gains_rendus_moitie": "menages",
    "r21_c3s_cvae_forfait_social_cfe": "entreprises",
    "l1_csg_activite_6_6": "menages",
    "l4_suppression_c3s_cvae": "entreprises",
    "l20_deplafonnement_qf": "haut",
    "lp20_tva_energie": "consommation",
    "tva_carburants_5_5": "consommation",
    "suppression_tva_taxes_carburants": "consommation",
}


def cas() -> list[tuple[str, object, object]]:
    """(nom du cas, programme, mesure), pour chaque mesure chiffrée de chaque programme."""
    from impots import programmes as pg

    out = []
    for slug in pg.lister():
        p = pg.charger(slug)
        for m in p.chiffrees():
            if m.id not in CLASSE:
                raise SystemExit(f"{slug}/{m.id} : aucune classe de tolérance (D-321)")
            out.append((f"{PREFIXE}_{slug}_{m.id}", p, m))
    connus = {m.id for _, _, m in out}
    orphelines = sorted(set(CLASSE) - connus)
    if orphelines:
        raise SystemExit(f"des classes pour des mesures qui ne sont plus chiffrées : "
                         f"{orphelines}")
    return out


def source(p, m) -> str:
    s = m.sources[0]
    return (f"{p.candidat} ({p.parti}), programme relevé le {p.releve.isoformat()} — "
            f"{m.libelle} : « {s.citation} » ({s.url}, {s.date.isoformat()})")


def ecrire() -> list[Path]:
    """Les scénarios et les réformes, tirés des programmes sans rien y ajouter."""
    from impots import consommation
    from impots import programmes as pg

    ecrits = []
    for nom, p, m in cas():
        if m.chiffrage.couche == "menages":
            path = ROOT / "scenarios" / f"{nom}.json"
            doc = {"name": nom, "year": p.annee, "created": "2026-11-01",
                   "source": source(p, m), "note": m.chiffrage.note,
                   "tags": ["presidentielle_2027", p.slug], "reform": m.chiffrage.reforme}
            if consommation.touche(pg._spec("menages", m.chiffrage.reforme)):
                # La TVA et les accises ne mordent que sur la consommation imputée (D-323).
                doc["imputations"] = ["consommation"]
                doc["created"] = "2026-11-02"
        else:
            path = ROOT / "reforms" / f"{nom}.json"
            doc = dict(m.chiffrage.reforme)
        path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        ecrits.append(path)
    return ecrits


def arguments(nom: str, p, m) -> list[str]:
    relative, absolute, raison = CLASSES[CLASSE[m.id]]
    common = [nom, "--tolerance-relative", repr(relative), "--tolerance-absolute",
              repr(absolute), "--tolerance-rationale", f"Classe « {CLASSE[m.id]} » (D-321). "
              f"{raison}", "--note", f"{source(p, m)}. {m.chiffrage.note}",
              "--vieillir", JEU]
    if m.chiffrage.couche == "menages":
        return ["chiffrage", "register", *common, "--scenario", nom,
                "--vintage", VINTAGE_MENAGES, "--sample", str(ECHANTILLON)]
    return ["chiffrage", "register-entreprises", *common,
            "--reform", str(ROOT / "reforms" / f"{nom}.json"), "--year", str(p.annee),
            "--vintage", VINTAGE_ENTREPRISES]


TABLEAU = ROOT / "reports" / "programmes_presidentielle.md"


def tableau(directory: Path | None = None) -> str:
    """Le tableau du but 11, candidat par candidat : les mesures, ce qui est chiffré, ce qui
    est refusé et par quelle porte, ce qui est préenregistré et son coût. Rien n'y est
    saisi : tout vient des programmes et du registre."""
    from impots import preregistration as ch
    from impots import programmes as pg

    def md(x: float) -> str:
        return f"{x / 1e9:+.3f}".replace(".", ",")

    lignes = [
        "# Les programmes de la présidentielle 2027 dans le moteur (D-319 à D-322)", "",
        "Candidats déclarés au 1er novembre 2026, mesures relevées et sourcées dans "
        "`programmes/`. Une mesure est chiffrée (traduite en paramètres du moteur), refusée "
        "(avec la porte qui l'ouvrirait) ou vague (sans paramètre). Les mesures chiffrées sont "
        "préenregistrées avant le chiffrage de l'Institut Montaigne ; leur coût est celui de "
        "2026, sur la population vieillie, en milliards d'euros, positif quand l'État perd.",
        "", "| candidat | mesures | paramétrées | vagues | chiffrées | préenregistrées | "
        "refusées, par porte |", "|---|---:|---:|---:|---:|---:|---|"]
    detail = ["", "## Les cas préenregistrés", "",
              "| cas | classe | tolérance | coût 2026 | juge |", "|---|---|---:|---:|---|"]
    totaux = [0, 0, 0, 0, 0]
    registre = set(ch.CHIFFRAGES.glob("*.yaml")) if directory is None else set(
        directory.glob("*.yaml"))
    noms = {f.stem for f in registre}
    for slug in pg.lister():
        p = pg.charger(slug)
        c = p.couverture()
        cases = [f"{PREFIXE}_{slug}_{m.id}" for m in p.chiffrees()]
        faits = [n for n in cases if n in noms]
        portes = ", ".join(f"{k} {v}" for k, v in c["refus_par_porte"].items()
                           if k != "vague") or "—"
        lignes.append(f"| {p.candidat} | {c['mesures']} | {c['parametrees']} | {c['vagues']} "
                      f"| {c['chiffrees']} | {len(faits)} | {portes} |")
        for i, v in enumerate((c["mesures"], c["parametrees"], c["vagues"], c["chiffrees"],
                               len(faits))):
            totaux[i] += v
        for n in faits:
            cas_ = ch.load(n, directory)
            m = next(x for x in p.chiffrees() if n.endswith(x.id))
            juge = ("à venir" if cas_.comparator is None else
                    ch.grade(cas_).verdict)
            detail.append(f"| `{n}` | {CLASSE[m.id]} | {cas_.tolerance.relative:.0%} | "
                          f"{md(cas_.mechanical_eur)} | {juge} |")
    lignes.append(f"| **total** | **{totaux[0]}** | **{totaux[1]}** | **{totaux[2]}** | "
                  f"**{totaux[3]}** | **{totaux[4]}** | |")
    return "\n".join(lignes + detail + [""])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--ecrire", action="store_true")
    group.add_argument("--enregistrer", action="store_true")
    group.add_argument("--lister", action="store_true")
    group.add_argument("--rendre", action="store_true")
    args = parser.parse_args()
    if args.rendre:
        TABLEAU.write_text(tableau(), encoding="utf-8")
        print(f"-> {TABLEAU.relative_to(ROOT)}")
        return 0
    if args.ecrire:
        for path in ecrire():
            print(f"-> {path.relative_to(ROOT)}")
        return 0
    if args.lister:
        for nom, _, m in cas():
            print(f"{nom}  [{CLASSE[m.id]}, {m.chiffrage.couche}]")
        return 0
    from impots.population import cli

    for nom, p, m in cas():
        print(f"== {nom}", flush=True)
        code = cli.main(arguments(nom, p, m))
        if code != 0:
            return code
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
