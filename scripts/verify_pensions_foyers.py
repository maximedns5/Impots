#!/usr/bin/env python
"""The three candidate sources of D-207's missing pension foyers, measured (D-209).

D-207 found the 400,4 Md€ of declared pensions sitting on 12,24 M foyers, against 15,09 M
beneficiaries of the 10 % abatement in the Voies et moyens, and named three candidates
read in the code. This script measures each, and what each would do to the tail where
art. 3 bites.

1. **Retirees in institutions.** The EEC surveys ordinary dwellings only. RP 2021 POP2
   counts the persons of 60 or more in CATPR 11 (moyen ou long séjour, maison de
   retraite, foyer).
2. **The pensioner rule.** `incomes.py` gives a pension to every inactive person of 55 or
   more, the age drawn inside a band. The EEC carries a declared status the rule ignores,
   ESEG_1 = 8 « Retraités », so the population is rebuilt with each person's EEC key
   (`noi`), checked identical to the built one, and the two rules compared.
3. **Cohabiting couples.** The skeleton puts every couple in one foyer; a couple neither
   married nor pacsé files two returns. RP 2021 POP3 gives the share of « concubinage ou
   union libre » among persons in a couple, by age.

THE TAIL, WITHOUT THE ENGINE. Each correction is applied to the same pension draws
(seeded here, so a difference between rows is the rule and not the noise), the mass held
at its calibration target, and the abatement recomputed foyer by foyer: the foyers whose
abatement exceeds 3 000 EUR, and the abatement art. 3 takes away. That mass moves the tax
in proportion only at unchanged marginal rates, which is the approximation this script
makes and says. Residents of institutions are drawn from the same law as everyone else,
which overstates their pensions and so the dilution: their row is an upper bound.

TWO READING TRAPS in the census files, both silent: Paris, Lyon and Marseille have a COM
row AND ARM rows, so only NIVGEO = COM is summed; and AGEQ80_14 is a five-year band whose
last value, 080, is open.

Usage: `.venv/bin/python scripts/verify_pensions_foyers.py` (about a minute; needs the
`tests` profile, the two RP archives and `data/processed/population_2024.parquet`).
"""

from __future__ import annotations

import sys
import zipfile
from pathlib import Path

import numpy as np
import polars as pl

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

RAW = ROOT / "data" / "raw"
POPULATION = ROOT / "data" / "processed" / "population_2024.parquet"
POP2 = RAW / "TD_POP2_2021_csv.zip"
POP3 = RAW / "TD_POP3_2021_csv.zip"

SIGMA = 0.55            # incomes.PENSION_SIGMA, read below and checked
MIN_ABATTEMENT = 454.0  # 2025 incomes, the frozen tree the art. 3 scenario runs on
PLAFOND, SOUS_PLAFOND = 4439.0, 3000.0
VM_120401_FOYERS = 15_085_237
ANNEX_FOYERS_RETRAITE = 13.4e6

#: Pinned at D-209. Counts in persons or foyers, ratios to the uncorrected row.
PINS = {
    "institutions": (0.701e6, 0.01),
    "concubins_60": (0.0848, 0.01),
    "pension_sans_retraite": (1.273e6, 0.01),
    "retraite_sans_pension": (0.611e6, 0.01),
    "emploi_65": (0.605e6, 0.01),
    "foyers_trois": (12.83e6, 0.01),
    "perdu_trois": (0.964, 0.005),
}


def _census(path: Path, name: str) -> pl.DataFrame:
    with zipfile.ZipFile(path).open(name) as handle:
        frame = pl.read_csv(handle.read(), separator=";", infer_schema=False)
    return frame.filter(pl.col("NIVGEO") == "COM").with_columns(pl.col("NB").cast(pl.Float64))


def _population_with_eseg() -> pl.DataFrame:
    """The built population, rebuilt with each person's EEC key and checked identical."""
    from impots.population import margins, skeleton
    from impots.population.calibrate import check_rake_result, rake, standard_margins, with_cells
    from impots.population.incomes import attach_incomes
    from impots.population.ingest import load_eec

    columns = skeleton.SKELETON_COLUMNS
    skeleton.SKELETON_COLUMNS = [*columns, "noi"]
    try:
        children = {k: np.array(v) for k, v in margins.CHILDREN_PER_FAMILY.items()}
        frame, _ = skeleton.build_skeleton(children_per_household=children,
                                           seed=skeleton.SEED)
    finally:
        skeleton.SKELETON_COLUMNS = columns
    frame = with_cells(frame)
    frame, diagnostics = rake(frame, standard_margins(frame))
    check_rake_result(diagnostics)
    frame, _ = attach_incomes(frame, seed=skeleton.SEED)

    built = pl.read_parquet(POPULATION).select("person_id", "weight", "pension_annuelle")
    same = frame.select("person_id", pl.col("weight").alias("w"),
                        pl.col("pension_annuelle").alias("p")).join(built, on="person_id")
    if (same.height != built.height
            or (same["w"] - same["weight"]).abs().max() > 1e-9
            or (same["p"] - same["pension_annuelle"]).abs().max() > 1e-6):
        raise SystemExit("la population reconstruite n'est pas celle du chiffrage")

    eec = load_eec().select(
        pl.concat_str([pl.col("IDENT"), pl.lit("-"), pl.col("TRIM")]).alias("household_id"),
        pl.col("NOI").alias("noi"), "ESEG_1", "ACTEU", "AGE6")
    return frame.join(eec, on=["household_id", "noi"], how="left")


def main() -> int:
    from impots.population.incomes import PENSION_SIGMA

    for path in (POPULATION, POP2, POP3):
        if not path.exists():
            print(f"{path} absent", file=sys.stderr)
            return 1
    if PENSION_SIGMA != SIGMA:
        print(f"PENSION_SIGMA vaut {PENSION_SIGMA}, ce script suppose {SIGMA}",
              file=sys.stderr)
        return 1
    failures: list[str] = []

    def pin(name: str, value: float) -> None:
        expected, tolerance = PINS[name]
        if abs(value / expected - 1) > tolerance:
            failures.append(f"{name} : {value:,.4f} contre {expected:,.4f} épinglé")

    # 1. Persons of 60 or more outside ordinary dwellings, in care or retirement homes.
    pop2 = _census(POP2, "TD_POP2_2021.csv").with_columns(pl.col("AGEQ100").cast(pl.Int32))
    institutions = pop2.filter((pl.col("CATPR") == "11") & (pl.col("AGEQ100") >= 60))["NB"].sum()
    print(f"1. en établissement, 60 ans ou plus (RP 2021, CATPR 11) : {institutions / 1e6:.3f} M "
          f"sur {pop2['NB'].sum() / 1e6:.2f} M habitants")
    pin("institutions", institutions)

    # 3, read first because the scenarios need it: concubins among persons in a couple.
    pop3 = _census(POP3, "TD_POP3_2021.csv")
    couples = (pop3.filter(pl.col("STAT_CONJ_19").is_in(["1", "2", "3"]))
               .group_by("AGEQ80_14")
               .agg((pl.col("NB").filter(pl.col("STAT_CONJ_19") == "3").sum()
                     / pl.col("NB").sum()).alias("part"))
               .with_columns(pl.col("AGEQ80_14").cast(pl.Int32)).sort("AGEQ80_14"))
    share_by_band = dict(couples.iter_rows())
    print("3. part des concubins parmi les personnes en couple (RP 2021, POP3) : "
          + ", ".join(f"{band}+ {share_by_band[band]:.1%}" for band in range(55, 85, 5)))
    pin("concubins_60", share_by_band[60])

    # 2. The rule against the declared status.
    p = _population_with_eseg()
    w = p["weight"].to_numpy()
    age = p["age"].to_numpy()
    acteu = p["ACTEU"].fill_null("").to_numpy()
    age6 = p["AGE6"].fill_null("").to_numpy()
    retired = p["ESEG_1"].fill_null("").to_numpy() == "8"
    rule = p["pension_annuelle"].to_numpy() > 0
    old_inactive = (acteu == "3") & np.isin(age6, ["65", "90"]) & ~retired
    working_old = (acteu == "1") & np.isin(age6, ["65", "90"])
    declared = retired | old_inactive | working_old
    print(f"2. pensionnés de la règle : {w[rule].sum() / 1e6:.2f} M ; dont retraités déclarés "
          f"{w[rule & retired].sum() / 1e6:.2f} M, inactifs de 65 ans ou plus non codés "
          f"{w[rule & old_inactive].sum() / 1e6:.2f} M, ni l'un ni l'autre "
          f"{w[rule & ~retired & ~old_inactive].sum() / 1e6:.2f} M")
    print(f"   retraités déclarés sans pension : {w[retired & ~rule].sum() / 1e6:.2f} M ; "
          f"65 ans ou plus en emploi, sans pension : {w[working_old].sum() / 1e6:.2f} M")
    pin("pension_sans_retraite", w[rule & ~retired & ~old_inactive].sum())
    pin("retraite_sans_pension", w[retired & ~rule].sum())
    pin("emploi_65", w[working_old].sum())

    # The tail, foyer by foyer, under each correction.
    codes, fidx = np.unique(p["foyer_id"].to_numpy(), return_inverse=True)
    nf = codes.size
    fw = np.bincount(fidx, weights=w) / np.bincount(fidx)   # the runner's foyer weight
    principal = p["role_foyer"].to_numpy() == "declarant_principal"
    decl_age = np.zeros(nf)
    decl_age[fidx[principal]] = age[principal]
    split = np.select([decl_age >= band for band in range(80, 50, -5)],
                      [share_by_band[band] for band in range(80, 50, -5)],
                      default=share_by_band[55])
    rng = np.random.default_rng(20261015)
    z = rng.standard_normal(p.height)
    outside = np.exp(SIGMA * rng.standard_normal(200_000))
    mass = float((p["pension_annuelle"].to_numpy() * w).sum())

    def abattement(pension):
        return np.where(pension > 0, np.minimum(np.maximum(0.1 * pension, MIN_ABATTEMENT),
                                                pension), 0.0)

    def tail(chosen, couples_split=False, residents=0.0):
        draw = np.where(chosen, np.exp(SIGMA * z), 0.0)
        scale = mass / ((draw * w).sum() + residents * outside.mean())
        a = abattement(draw * scale)
        total = np.bincount(fidx, weights=a, minlength=nf)
        holders = np.bincount(fidx, weights=(a > 0).astype(float), minlength=nf)
        taken = np.minimum(total, PLAFOND) - np.minimum(total, SOUS_PLAFOND)
        foyers, hit, lost = (fw * (total > 0)).sum(), (fw * (total > SOUS_PLAFOND)).sum(), \
            (fw * taken).sum()
        if couples_split:   # expected value: the couple files two returns with share s
            s = np.where(holders >= 2, split, 0.0)
            alone_lost = np.bincount(fidx, weights=np.minimum(a, PLAFOND)
                                     - np.minimum(a, SOUS_PLAFOND), minlength=nf)
            alone_hit = np.bincount(fidx, weights=(a > SOUS_PLAFOND).astype(float),
                                    minlength=nf)
            foyers += (fw * s).sum()
            hit += (fw * s * (alone_hit - (total > SOUS_PLAFOND))).sum()
            lost += (fw * s * (alone_lost - taken)).sum()
        if residents:       # single foyers, at the same draw law
            g = abattement(outside * scale)
            foyers += residents
            hit += residents * (g > SOUS_PLAFOND).mean()
            lost += residents * (np.minimum(g, PLAFOND) - np.minimum(g, SOUS_PLAFOND)).mean()
        return foyers, hit, lost

    rows = [
        ("règle actuelle", tail(rule)),
        ("1 : + établissements (borne haute)", tail(rule, residents=institutions)),
        ("2 : retraite déclarée, cumul compris", tail(declared)),
        ("3 : concubins séparés", tail(rule, couples_split=True)),
        ("les trois", tail(declared, couples_split=True, residents=institutions)),
    ]
    reference = rows[0][1][2]
    print(f"\n   {'':38s} {'foyers':>8s} {'> 3 000':>8s} {'perdu':>9s}")
    for label, (foyers, hit, lost) in rows:
        print(f"   {label:38s} {foyers / 1e6:7.2f}M {hit / 1e6:7.2f}M "
              f"{lost / 1e9:6.2f}Md  ×{lost / reference:.3f}")
    print(f"   (annexe : {ANNEX_FOYERS_RETRAITE / 1e6:.1f} M foyers de retraités ; VM 120401 : "
          f"{VM_120401_FOYERS / 1e6:.2f} M foyers bénéficiaires)")
    pin("foyers_trois", rows[-1][1][0])
    pin("perdu_trois", rows[-1][1][2] / reference)

    for failure in failures:
        print(f"ÉCHEC  {failure}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
