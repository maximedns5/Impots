"""F5 M1 — the taxe foncière cells: commune × strate, as published.

**Nothing here is synthesised.** Every base and every rate is read from the REI exactly as
the DGFiP published it; there is no imputation, no draw and no cell fitted to a total. That
makes this the first module in the project whose cells are not a construction — and it
changes what the baseline check IS. Elsewhere the reconciliation asks «does our synthetic
population reproduce a published total»; here it asks «does our arithmetic on THEIR bases
reproduce THEIR produits», commune by commune. That is a much stronger question and it has
a much cleaner answer.

THE IDENTITY, AND THE TERM THAT WAS MISSING FROM IT. The obvious form is
`base × taux = produit`. Measured over 34 819 communes it holds to a median relative error
of 0,023 %, which is already rounding. But the REI also publishes a **lissage** (`E16`), and 13 430
communes carry a non-zero one. Adding it drops THEIR median error from 0,0355 % to
0,0012 % — thirty times better. So the identity this module asserts is

    base × taux / 100 + lissage = produit

and the lissage is not a correction anyone should apply silently: it is a published term of
the calculation that a two-factor reading simply omits.

WHAT STILL DOES NOT RECONCILE, PINNED RATHER THAN ABSORBED. **55 communes out of 34 819**
sit more than 1 % away once the lissage is in, the worst at 5,97 %, and every one of them
has **no lissage at all** — so the term above cannot be what is missing. Their effective rate is
below their published rate (base 227 676 at 19,40 % should yield 44 169; the REI says
41 682, an effective 18,31 %), which points at an abattement or an exonération this module
does not read. That is 0,16 % of communes and well under a part per thousand of the national total, and it is
recorded as unexplained rather than smoothed: a residual with a name is a lead, a residual
absorbed into a tolerance is a lie with error bars.
"""

from __future__ import annotations

import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ARCHIVE = Path(__file__).resolve().parents[3] / "data" / "raw" / "rei_2025.zip"

#: The strata of the foncier bâti: base column, rate column, produit column, lissage
#: column. `None` where the REI publishes no such column for that stratum.
#:
#: Rates are in PERCENT in this file — the /100 lives in `produit_of`, once, rather than
#: at every call site.
FB_STRATA: dict[str, tuple[str, str, str | None, str | None]] = {
    "commune": ("E11", "E12", "E13", "E16"),
    "intercommunalite": ("E31", "E32", "E33", "E36"),
    "tse": ("E51", "E52", "E53", "E56"),
    "tse_autres": ("E51A", "E52A", "E53A", "E56A"),
    "gemapi": ("E51gGEMAPI", "E52gGEMAPI", "E53gGEMAPI", "E56gGEMAPI"),
    "tasa": ("E51TASA", "E52TASA", None, None),
}

#: The non bâti. Read but NOT validated: the gate measured our reading at -59,7 % against
#: the published 2,7 Md€ and could not find the missing strata (D-100). Carried so the
#: hole stays visible in the code as well as the document.
FNB_STRATA: dict[str, tuple[str, str, str | None, str | None]] = {
    "commune": ("B11", "B12", "B13", None),
    "intercommunalite": ("B31", "B32", "B33", None),
    "tse": ("B51", "B52", "B53", None),
}

#: Communes whose produit the identity cannot reproduce, measured WITH the lissage term.
#: Pinned as a COUNT rather than a list: the list would rot with the vintage, the count is
#: the finding.
#:
#: 79 without the lissage, 55 with it — and the 24 that the term explains are precisely the
#: ones that carried a non-zero lissage. Writing 79 here first and measuring afterwards
#: would have pinned the wrong number; the constant follows the measurement rather than
#: the other way round.
UNEXPLAINED_COMMUNES = 55
UNEXPLAINED_TOLERANCE = 0.01
#: The relative error at which the identity is considered to hold. Not a fitted tolerance:
#: the median is 0,023 % and the 99th percentile 0,49 %, so 1 % separates «rounding» from
#: «something else is going on» rather than being chosen to make a number pass.
IDENTITY_TOLERANCE = 0.01


class CellError(RuntimeError):
    """The REI could not be read into cells as asked."""


@dataclass(frozen=True)
class Cells:
    """One row per commune, with the published bases, rates and produits."""

    frame: Any
    vintage: str
    strata: tuple[str, ...]

    @property
    def communes(self) -> int:
        return int(self.frame.height)


def read(archive: Path | None = None, vintage: str = "2025") -> Cells:
    """Read the REI into commune cells. Latin-1, semicolons, comma decimals.

    The encoding is asserted rather than guessed: a UTF-8 read with `errors="replace"`
    corrupts commune names silently, which is the trap `verify_rei.py` exists to catch.
    """
    import polars as pl

    path = archive or ARCHIVE
    if not path.exists():
        raise CellError(f"{path} absent — voir data/raw/MANIFEST.json")
    with zipfile.ZipFile(path) as bundle:
        name = next((n for n in bundle.namelist() if n.endswith(".csv")), None)
        if name is None:
            raise CellError(f"{path} ne contient pas de CSV")
        raw = bundle.read(name)
    try:
        text = raw.decode("latin-1")
    except UnicodeDecodeError as error:  # pragma: no cover - latin-1 cannot fail
        raise CellError(f"encodage inattendu : {error}") from error

    frame = pl.read_csv(text.encode("utf-8"), separator=";", infer_schema_length=0)
    number = lambda column: (  # noqa: E731
        pl.col(column).str.replace_all(",", ".").cast(pl.Float64, strict=False)
        .fill_null(0.0))

    columns = [pl.col("DEP").alias("dep"), pl.col("COM").alias("com"),
               pl.col("LIBCOM").alias("libelle")]
    present = []
    for stratum, (base, rate, produit, lissage) in FB_STRATA.items():
        if base not in frame.columns:
            continue
        present.append(stratum)
        columns += [number(base).alias(f"fb_{stratum}_base"),
                    number(rate).alias(f"fb_{stratum}_taux")]
        if produit and produit in frame.columns:
            columns.append(number(produit).alias(f"fb_{stratum}_produit"))
        if lissage and lissage in frame.columns:
            columns.append(number(lissage).alias(f"fb_{stratum}_lissage"))
    return Cells(frame=frame.select(columns), vintage=vintage,
                 strata=tuple(present))


def produit_of(cells: Cells, stratum: str = "commune") -> Any:
    """base × taux / 100 + lissage, per commune. The identity, with its third term."""
    import polars as pl

    # The stratum is checked against `cells.strata` BEFORE the frame is touched: the
    # first version read `cells.frame.columns` and crashed with an AttributeError on a
    # cells object that had none, turning a refusal into a stack trace.
    if stratum not in cells.strata:
        raise CellError(
            f"strate « {stratum} » absente des cellules (présentes : "
            f"{list(cells.strata)}). Rendre zéro se lirait « cette strate ne rapporte "
            f"rien », ce qui n'est pas ce qu'on sait.")
    base, taux = f"fb_{stratum}_base", f"fb_{stratum}_taux"
    computed = pl.col(base) * pl.col(taux) / 100.0
    lissage = f"fb_{stratum}_lissage"
    if lissage in cells.frame.columns:
        computed = computed + pl.col(lissage)
    return computed


def identity_residuals(cells: Cells, stratum: str = "commune") -> Any:
    """Per-commune relative error of the identity, for communes that have both sides."""
    import polars as pl

    produit = f"fb_{stratum}_produit"
    if produit not in cells.frame.columns:
        raise CellError(
            f"la strate « {stratum} » ne publie pas de produit : l'identité ne peut pas "
            f"y être vérifiée, et la vérifier ailleurs ne dit rien d'elle.")
    return (cells.frame
            .with_columns(calcule=produit_of(cells, stratum))
            .filter((pl.col(f"fb_{stratum}_base") > 0) & (pl.col(produit) > 0))
            .with_columns(residual=((pl.col("calcule") - pl.col(produit))
                                    / pl.col(produit)).abs()))


def national(cells: Cells, strata: tuple[str, ...] | None = None) -> float:
    """The national foncier bâti, summed over the strata asked for."""
    total = 0.0
    for stratum in (strata or cells.strata):
        total += float(cells.frame.select(produit_of(cells, stratum).sum()).item())
    return total
