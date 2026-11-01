#!/usr/bin/env python
"""Les cinq cas notés du PLF 2027, rechiffrés sur la population vieillie (but 10, D-317).

Chaque cas aveugle est rechiffré sous un nouveau nom, `<cas>_vieilli`, sur la population
vieillie jusqu'à son année aux hypothèses du PLF 2027 (`--vieillir plf2027`). Ce sont des
révisions écrites après l'annexe, comptées à part (D-292) ; leur tolérance est celle du cas
aveugle, inchangée. Trois temps, chacun sur un commit propre :

* `--controle` : chaque cas repassé SANS vieillissement sur le commit présent, pour séparer
  ce que le moteur a changé depuis l'enregistrement de ce que le millésime change. Il écrit
  `reports/revisions_vieillies_controle.json` et n'enregistre rien.
* `--enregistrer` : les cinq révisions, par la commande `impots chiffrage register`.
* `--comparateurs` : le comparateur de chaque cas aveugle, recopié dans sa révision, dans
  un commit à part, après celui des enregistrements.
* `--rendre` : `reports/revisions_vieillies.md`, le tableau avant et après, depuis le
  contrôle et le registre.

Usage : `.venv/bin/python scripts/revisions_vieillies.py --controle` (puis les deux
autres). Les passes des ménages tirent 20 000 ménages, comme les cas aveugles.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

CASES = ("plf2027_art_2", "plf2027_art_3", "plf2027_art_74_ppa", "plf2027_art_74_apl",
         "plf2027_art_15")
FIRM_REFORMS = {"plf2027_art_15": ROOT / "reforms" / "plf2027_art_15.json"}
SUFFIX = "_vieilli"
JEU = "plf2027"
RAISON = ("but 10 : le cas aveugle rechiffré sur la population vieillie jusqu'à son année, "
          "aux hypothèses du PLF 2027 et de son PLFSS (D-317)")
CONTROLE = ROOT / "reports" / "revisions_vieillies_controle.json"


def _original(case: str):
    from impots import preregistration as ch

    return ch.load(case)


def arguments(case: str) -> list[str]:
    """La ligne de commande qui enregistre la révision de `case`, sa tolérance recopiée."""
    original = _original(case)
    t = original.tolerance
    common = [
        f"{case}{SUFFIX}",
        "--tolerance-relative", repr(t.relative),
        "--tolerance-absolute", repr(t.absolute_eur),
        "--tolerance-rationale", f"Celle du cas aveugle {case}, inchangée (D-292). "
                                 f"{t.rationale}",
        "--note", f"Révision de {case} sur la population vieillie (D-317). {original.note}",
        "--apres-annexe", RAISON, "--vieillir", JEU,
    ]
    if case in FIRM_REFORMS:
        reform = original.reform
        return ["chiffrage", "register-entreprises", *common,
                "--reform", str(FIRM_REFORMS[case]), "--year", str(reform["annee"]),
                "--vintage", original.population_vintage.removeprefix("entreprises-")]
    out = ["chiffrage", "register", *common, "--scenario", original.scenario,
           "--vintage", original.population_vintage, "--sample", str(original.sample)]
    return out + (["--mirror"] if original.mirror else [])


def controle() -> dict[str, object]:
    """Chaque cas repassé sans vieillissement, sur le commit présent."""
    import polars as pl

    from impots import scenarios
    from impots.entreprises import aggregate, runner
    from impots.entreprises import build as firm_build
    from impots.entreprises.reforms import FirmReformSpec
    from impots.population.cli import PROCESSED
    from impots.predictif import recherche

    commit, dirty = recherche.code_state(ROOT)
    out: dict[str, object] = {"commit": commit, "dirty": dirty, "cas": {}}
    for case in CASES:
        original = _original(case)
        if case in FIRM_REFORMS:
            vintage = original.population_vintage.removeprefix("entreprises-")
            spec = FirmReformSpec.model_validate_json(
                FIRM_REFORMS[case].read_text(encoding="utf-8"))
            frame = pl.read_parquet(firm_build.PROCESSED / f"firms_{vintage}.parquet")
            cost = aggregate.aggregate(runner.run(
                frame, year=original.reform["annee"], reform=spec).firms).reform_cost
        else:
            scenario = scenarios.load(original.scenario)
            frame = pl.read_parquet(PROCESSED / f"population_{original.population_vintage}"
                                                f".parquet")
            cost = scenarios.mechanical_price(scenario, frame=frame,
                                              households=original.sample)["mechanical"]
        out["cas"][case] = {"enregistre_eur": original.mechanical_eur,
                            "fige_aujourd_hui_eur": float(cost or 0.0),
                            "commit_enregistrement": original.commit}
        print(f"  {case} : enregistré {original.mechanical_eur / 1e9:+.3f}, figé aujourd'hui "
              f"{float(cost or 0.0) / 1e9:+.3f} md EUR", flush=True)
    return out


def comparateur(case: str, directory: Path | None = None) -> Path:
    """Recopie le comparateur du cas aveugle dans sa révision, à la place de son `null`."""
    import yaml

    from impots import preregistration as ch

    directory = directory or ch.CHIFFRAGES
    original = yaml.safe_load((directory / f"{case}.yaml").read_text(encoding="utf-8"))
    path = directory / f"{case}{SUFFIX}.yaml"
    text = path.read_text(encoding="utf-8")
    if text.count("\ncomparator: null\n") != 1:
        raise SystemExit(f"{path.name} : pas exactement un « comparator: null » à remplacer")
    block = yaml.safe_dump({"comparator": original["comparator"]}, allow_unicode=True,
                           sort_keys=False, width=88)
    path.write_text(text.replace("\ncomparator: null\n", "\n" + block), encoding="utf-8")
    loaded = ch.load(f"{case}{SUFFIX}", directory)
    if loaded.comparator is None or loaded.comparator.published_eur != \
            original["comparator"]["published_eur"]:
        raise SystemExit(f"{path.name} : le comparateur ne se relit pas")
    return path


TABLEAU = ROOT / "reports" / "revisions_vieillies.md"


def tableau(controle: dict, directory: Path | None = None) -> str:
    """Le tableau des cinq révisions : l'enregistré, le figé d'aujourd'hui, le vieilli, la
    fiche, et l'écart avant et après. Rien n'y est saisi : tout vient du contrôle et du
    registre, et la note est celle de `grade`."""
    from impots import preregistration as ch

    def fr(x: float, d: int = 3) -> str:
        return f"{x:+.{d}f}".replace(".", ",")

    lines = [
        "# Les cinq cas du PLF 2027 sur la population vieillie (D-317, D-318)", "",
        f"Contrôle et révisions sur `{controle['commit'][:7]}`. En milliards d'euros, au "
        "signe de la note (un cas miroir est retourné, D-298). L'écart est rapporté à la "
        "fiche ; le millésime est ce que le vieillissement déplace, le vieilli moins le figé "
        "d'aujourd'hui, sur le même commit.", "",
        "| cas | enregistré | figé aujourd'hui | vieilli | fiche | écart figé | écart vieilli "
        "| millésime | note vieillie |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---|"]
    for case in CASES:
        original = ch.load(case, directory)
        revision = ch.load(f"{case}{SUFFIX}", directory)
        if revision.commit != controle["commit"]:
            raise SystemExit(f"{case}{SUFFIX} chiffré sur {revision.commit[:7]}, le contrôle "
                             f"sur {controle['commit'][:7]} : le millésime ne se lit que sur "
                             "le même commit")
        aged = ch.grade(revision)
        sign = -1.0 if original.mirror else 1.0
        registered = sign * original.mechanical_eur
        frozen = sign * controle["cas"][case]["fige_aujourd_hui_eur"]
        published = aged.published_eur
        lines.append(
            f"| {case} | {fr(registered / 1e9)} | {fr(frozen / 1e9)} | "
            f"{fr(aged.simulated_eur / 1e9)} | {fr(published / 1e9)} | "
            f"{fr((frozen - published) / abs(published) * 100, 1)} % | "
            f"{fr((aged.simulated_eur - published) / abs(published) * 100, 1)} % | "
            f"{fr((aged.simulated_eur - frozen) / 1e9)} | **{aged.verdict}** |")
    within = sum(ch.grade(ch.load(f"{c}{SUFFIX}", directory)).verdict == "within"
                 for c in CASES)
    blind = sum(ch.grade(ch.load(c, directory)).verdict == "within" for c in CASES)
    lines += ["", f"**{within} sur {len(CASES)} révisions vieillies dans la tolérance**, "
              f"contre {blind} sur {len(CASES)} cas aveugles, dont la note ne bouge pas.", ""]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--controle", action="store_true")
    group.add_argument("--enregistrer", action="store_true")
    group.add_argument("--comparateurs", action="store_true")
    group.add_argument("--rendre", action="store_true")
    args = parser.parse_args()
    if args.rendre:
        found = json.loads(CONTROLE.read_text(encoding="utf-8"))
        if found["dirty"]:
            raise SystemExit("le contrôle a tourné sur un arbre modifié")
        TABLEAU.write_text(tableau(found), encoding="utf-8")
        print(f"-> {TABLEAU}")
        return 0
    if args.controle:
        found = controle()
        CONTROLE.write_text(json.dumps(found, indent=2, ensure_ascii=False) + "\n",
                            encoding="utf-8")
        print(f"-> {CONTROLE}")
        return 0
    if args.enregistrer:
        from impots.population import cli

        for case in CASES:
            code = cli.main(arguments(case))
            if code != 0:
                return code
        return 0
    for case in CASES:
        print(f"-> {comparateur(case)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
