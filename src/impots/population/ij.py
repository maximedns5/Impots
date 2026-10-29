"""Les indemnités journalières de la sécurité sociale, imputées sur la population (but 8, D-305).

**C'est une calibration, et elle dépense sa source.** Le rapport à la Commission des
comptes de la sécurité sociale de mai 2026 publie ce que le régime général a versé en
indemnités journalières en 2024 : 15 645 M€ au total (fiche 2.3, tableau 1, en dépenses
remboursées, anciens affiliés du RSI compris), dont 4 955 M€ pour la branche AT-MP
(fiche 4.4, tableau 1). La maladie en est la différence, 10 690 M€. Ce module lit ces
deux lignes dans le PDF manifesté, puis répartit chaque masse sur les salariés du privé.
Les totaux de la population sont alors ceux du CCSS par construction : ils ne pourront
jamais servir de preuve de quoi que ce soit, et `margins.SICK_PAY_BY_BRANCH` porte
`use="calibration"` pour cette raison.

LA CLÉ. L'enquête Emploi 2024 dit, pour chaque salarié du privé, s'il était absent pour
« congé maladie (y compris arrêt après un accident au travail) » la semaine de référence
(`RABS` = 2). La part pondérée des absents, par tranche d'âge et groupe de PCS, est la
fréquence des arrêts de la cellule : 0,55 % chez les cadres de moins de 25 ans, 8,62 %
chez les ouvriers de 50 à 64 ans. Chaque salarié du privé reçoit cette fréquence fois son
salaire brut, plafonné au salaire de référence des IJ maladie de 2024 (1,8 SMIC), puis la
masse de chaque branche est répartie au prorata.

CINQ ARTEFACTS, DÉCLARÉS, PARCE QU'AUCUN NE SE VOIT DANS LA SORTIE.

1. **Chaque salarié du privé reçoit l'espérance de sa cellule**, arrêté ou non. Tous en
   ont donc un peu, alors qu'une année n'en voit qu'une partie. Un impôt proportionnel ne
   voit pas la différence ; un barème progressif et les ressources d'une prestation la
   voient, et c'est la première chose qu'un appariement améliorerait.
2. **Les deux branches ont la même clé.** L'enquête ne sépare pas l'arrêt maladie de
   l'arrêt pour accident du travail. Les AT-MP sont en réalité plus ouvriers que la
   maladie ; ici, leur masse suit la même fréquence.
3. **Le régime général seul, et le privé seul.** La masse est celle du régime général,
   indépendants anciennement affiliés au RSI compris, et elle va entière aux salariés du
   privé : la population n'a pas de revenu d'indépendant (KNOWN_LIMITATIONS), et le
   fonctionnaire titulaire garde son traitement. Les régimes spéciaux et agricoles ne
   sont pas dans la masse.
4. **Le plafond est celui de la maladie.** Le salaire de référence des AT-MP a son propre
   plafond, plus haut ; la clé n'en tient pas compte.
5. **Ni l'ALD, ni la durée.** Le CCSS sépare les arrêts de moins et de plus de trois mois
   (37 % et 29 % des dépenses de 2025, les AT-MP 34 %), mais aucune source ouverte ne
   donne la part des IJ versées au titre d'une affection de longue durée : les Voies et
   moyens disent de la dépense fiscale 120204 « Bénéficiaires : non déterminé ». La
   colonne maladie ne se scinde donc pas, et c'est ce qui manque au volet ALD de l'art. 2
   du PLF 2027.

Ce que la population en fait : openfisca lit `indemnites_journalieres_maladie` et
`indemnites_journalieres_accident_travail` dans les ressources du RSA, de la prime
d'activité, de l'ASS et de l'ASPA. Il ne les met ni dans l'impôt sur le revenu ni dans la
CSG (la CSG sur les IJ est un TODO du modèle) : le volet 4.2.1.4 de l'art. 2 demande ce
câblage, qui n'est pas fait ici (D-305).

Les montants sont ceux de 2024. Une autre année demanderait de vieillir la masse, ce qui
n'est pas fait ici : elle est refusée par son nom.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np
import polars as pl

from impots.donnees import RAW

CCSS = RAW / "ccss_mai2026_comptes_secu_resultats2025.pdf"
EEC = RAW / "FD_EEC_2024.parquet"
YEAR = 2024

#: Les deux lignes lues, par page du PDF (comptée à partir de 1) : la fiche 2.3 (soins de
#: ville du régime général) et la fiche 4.4 (comptes de la CNAM AT-MP).
TOTAL_PAGE = 94
ATMP_PAGE = 161
#: « Indemnités journalières 15 645 16 445 5,1% 15% 0,7 6,2% » : 2024, 2025, évolution...
TOTAL_LINE = re.compile(r"^Indemnités journalières (\d{1,3}(?: \d{3})*) "
                        r"(\d{1,3}(?: \d{3})*) \d", re.M)
#: « Indemnités journalières 4 955 10,1 5 480 10,6 5 877 7,3 » : 2024, %, 2025, %...
ATMP_LINE = re.compile(r"^Indemnités journalières (\d{1,3}(?: \d{3})*) -?\d+,\d "
                       r"(\d{1,3}(?: \d{3})*) -?\d+,\d", re.M)

#: Ce que le texte de la fiche 2.3 dit de 2025 : les AT-MP font 34 % des dépenses d'IJ.
#: Les deux tableaux lus doivent le redire, à l'arrondi près.
ATMP_SHARE_2025_TEXT = 0.34
ATMP_SHARE_TOLERANCE = 0.01

#: Le salaire de référence des IJ maladie est plafonné à 1,8 SMIC en 2024 (1,4 depuis le
#: 1er avril 2025, CCSS fiche 2.3).
CAP_SMIC = 1.8
#: Les totaux imputés doivent rendre ceux du CCSS à cette précision près : c'est la garde.
TOTAL_TOLERANCE = 1e-6

#: `AGE6` de l'enquête, les deux dernières tranches réunies (35 salariés du privé au-delà
#: de 90 ans ne font pas une cellule).
AGE_BANDS = ((15, "15"), (25, "25"), (50, "50"), (65, "65"))
PCS_GROUP = {"30": "cadre", "40": "profession_intermediaire", "51": "employe",
             "52": "employe", "61": "ouvrier", "62": "ouvrier"}
NO_PCS = "sans_pcs"


class SickPayError(ValueError):
    """La source ne se lit pas comme attendu, ou l'imputation ne rend pas ses totaux."""


@dataclass(frozen=True)
class Published:
    """Les IJ du régime général, en M€, telles que le CCSS de mai 2026 les publie."""

    total_2024: float
    total_2025: float
    atmp_2024: float
    atmp_2025: float

    @property
    def maladie_2024(self) -> float:
        return self.total_2024 - self.atmp_2024


def _meur(text: str) -> float:
    return float(text.replace(" ", ""))


@lru_cache(maxsize=4)
def published(pdf: Path = CCSS) -> Published:
    """Les deux lignes du CCSS, lues dans le PDF ; refusé si l'une manque ou dément le texte."""
    from pypdf import PdfReader

    if not pdf.exists():
        raise SickPayError(f"{pdf.name} absent : `impots donnees` le télécharge (manifeste)")
    reader = PdfReader(str(pdf))
    total = TOTAL_LINE.search(reader.pages[TOTAL_PAGE - 1].extract_text() or "")
    atmp = ATMP_LINE.search(reader.pages[ATMP_PAGE - 1].extract_text() or "")
    if total is None or atmp is None:
        missing = "fiche 2.3, tableau 1" if total is None else "fiche 4.4, tableau 1"
        raise SickPayError(f"CCSS mai 2026 : la ligne des IJ manque ({missing})")
    out = Published(_meur(total[1]), _meur(total[2]), _meur(atmp[1]), _meur(atmp[2]))
    share = out.atmp_2025 / out.total_2025
    if abs(share - ATMP_SHARE_2025_TEXT) > ATMP_SHARE_TOLERANCE:
        raise SickPayError(
            f"CCSS mai 2026 : les AT-MP font {share:.1%} des IJ de 2025 dans les tableaux "
            f"et {ATMP_SHARE_2025_TEXT:.0%} dans le texte ; la lecture est fausse")
    return out


def _age_band(age: np.ndarray) -> np.ndarray:
    out = np.full(age.shape, "", dtype=object)
    for low, code in AGE_BANDS:
        out[age >= low] = code
    return out


@lru_cache(maxsize=2)
def frequencies(eec: Path = EEC) -> dict[tuple[str, str], float]:
    """La part pondérée des salariés du privé en congé maladie la semaine de référence,
    par tranche d'âge et groupe de PCS."""
    df = pl.read_parquet(eec, columns=["RABS", "STATUT", "PUB3FP", "AGE6", "PCS1Q",
                                       "EXTRIAN", "ACTEU"])
    private = df.filter((pl.col("ACTEU") == "1") & (pl.col("STATUT") == "2")
                        & (pl.col("PUB3FP") == "4"))
    private = private.with_columns(
        pl.col("PCS1Q").replace_strict(PCS_GROUP, default=NO_PCS).alias("pcs"),
        pl.when(pl.col("AGE6").is_in(["65", "90"])).then(pl.lit("65"))
          .otherwise(pl.col("AGE6")).alias("age"),
        (pl.col("RABS") == "2").fill_null(False).cast(pl.Float64).alias("sick"),
    )
    cells = private.group_by(["age", "pcs"]).agg(
        ((pl.col("sick") * pl.col("EXTRIAN")).sum() / pl.col("EXTRIAN").sum()).alias("f"))
    return {(row["age"], row["pcs"]): float(row["f"]) for row in cells.iter_rows(named=True)}


def reference_wage_cap(year: int = YEAR) -> float:
    """Le plafond annuel du salaire de référence des IJ maladie : 1,8 SMIC mensuel × 12."""
    from impots.engine.system import baseline

    smic = baseline().parameters(f"{year}-07-01").marche_travail.salaire_minimum.smic
    return CAP_SMIC * float(smic.smic_b_horaire) * float(smic.nb_heures_travail_mensuel) * 12


def keys(frame: pl.DataFrame, cap: float, cells: dict[tuple[str, str], float]) -> np.ndarray:
    """La clé de chaque personne : fréquence de sa cellule × salaire brut plafonné ; zéro
    hors des salariés du privé en emploi."""
    eligible = (frame["is_salarie"].to_numpy()
                & ~frame["secteur_public"].to_numpy()
                & (frame["statut_activite"].to_numpy() == "employed"))
    ages = _age_band(frame["age"].to_numpy())
    pcs = frame["pcs"].fill_null(NO_PCS).to_numpy()
    freq = np.array([cells.get((a, p), np.nan) if ok else 0.0
                     for a, p, ok in zip(ages, pcs, eligible)], dtype=np.float64)
    if np.isnan(freq).any():
        raise SickPayError("un salarié du privé tombe dans une cellule que l'enquête n'a pas")
    wage = np.minimum(frame["salaire_brut_annuel"].to_numpy().astype(np.float64), cap)
    return freq * np.maximum(wage, 0.0)


def impute(frame: pl.DataFrame, year: int = YEAR, *, source: Published | None = None,
           cells: dict[tuple[str, str], float] | None = None) -> pl.DataFrame:
    """La population avec `ij_maladie_annuel` et `ij_atmp_annuel`, en euros par personne,
    dont les totaux pondérés sont ceux du CCSS ; refusé hors de 2024."""
    if year != YEAR:
        raise SickPayError(
            f"IJ imputées pour {year} : le CCSS de mai 2026 est lu pour {YEAR}, et une "
            f"autre année demanderait de vieillir la masse, ce qui n'est pas fait (D-305)")
    source = published() if source is None else source
    key = keys(frame, reference_wage_cap(year), frequencies() if cells is None else cells)
    weights = frame["weight"].to_numpy().astype(np.float64)
    mass = float(weights @ key)
    if not mass > 0:
        raise SickPayError("aucun salarié du privé dans la population : rien à répartir")
    out = frame.with_columns(
        pl.Series("ij_maladie_annuel", key * (source.maladie_2024 * 1e6 / mass)),
        pl.Series("ij_atmp_annuel", key * (source.atmp_2024 * 1e6 / mass)),
    )
    # Not `verify` here: the scaling makes it true by construction (D-305, an
    # equivalent mutant). The tests run it on the real population.
    return out


def verify(frame: pl.DataFrame, source: Published) -> dict[str, float]:
    """Chaque colonne contre son agrégat : les totaux pondérés, en M€, à 1e-6 près."""
    weights = frame["weight"].to_numpy().astype(np.float64)
    totals = {"maladie": float(weights @ frame["ij_maladie_annuel"].to_numpy()) / 1e6,
              "atmp": float(weights @ frame["ij_atmp_annuel"].to_numpy()) / 1e6}
    expected = {"maladie": source.maladie_2024, "atmp": source.atmp_2024}
    for branch, total in totals.items():
        if abs(total / expected[branch] - 1) > TOTAL_TOLERANCE:
            raise SickPayError(
                f"IJ {branch} : {total:,.1f} M€ imputés contre {expected[branch]:,.1f} "
                f"publiés par le CCSS")
    if (frame["ij_maladie_annuel"] < 0).any() or (frame["ij_atmp_annuel"] < 0).any():
        raise SickPayError("une IJ imputée est négative")
    return totals
