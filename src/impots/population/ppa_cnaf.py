"""Ce que la Cnaf publie des bénéficiaires de la prime d'activité en 2024, lu dans ses PDF (D-315).

Deux publications de la Cnaf, manifestées, comparateurs de la mesure de l'écart de la prime
(but 9) et source d'aucune imputation :

* **PA Conjoncture n° 32** (mars 2025), tableau 1, p. 4 : les foyers bénéficiaires du
  quatrième trimestre 2024 (moyenne du trimestre), leur montant moyen et la dépense du
  trimestre, par configuration familiale, par âge du responsable du dossier, et pour trois
  sous-populations. Le champ est celui des Caf, que la p. 2 rapporte au total de tous les
  régimes : 97,0 % des bénéficiaires et 96,4 % des dépenses en 2023.
* **Analyses statistiques n° 5** (2025), encadré 2, p. 3 : les élasticités de la dépense
  de 2024, estimées avec le modèle César-PA de la Cnaf : au montant forfaitaire (y compris
  le forfait logement), aux revenus d'activité, aux prestations familiales.

Chaque lecture est refusée si la ligne manque, ou si les configurations ne font pas
l'ensemble que le tableau imprime.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

RAW = Path(__file__).resolve().parents[3] / "data" / "raw"
CONJONCTURE = RAW / "cnaf_pa_conjoncture_32_2024t4.pdf"
ANALYSES = RAW / "cnaf_analyses_statistiques_5_2025_pa.pdf"

#: Les lignes du tableau 1, dans l'ordre où il les imprime, sous les clés de la mesure.
CONFIGURATIONS = (
    ("homme_seul", "Hommes seuls"),
    ("femme_seule", "Femmes seules"),
    ("seul_avec_enfants", "Personnes seules avec enfant(s)"),
    ("couple_sans_enfant", "Couples sans enfant"),
    ("couple_avec_enfants", "Couples avec enfant(s)"),
)
AGES = (
    ("moins_25", "<25 ans"),
    ("25_34", "25-34 ans"),
    ("35_44", "35-44 ans"),
    ("45_54", "45-54 ans"),
    ("55_plus", "≥ 55 ans"),
)
SOUS_POPULATIONS = (
    ("majoration_isolement", "dont majoration pour isolement"),
    ("bonification", "dont au moins une bonification"),
    ("cumul_rsa", "dont cumul prime d’activité/RSA"),
)

_COUNT = r"(\d{1,3}(?: \d{3})?)"
_RATE = r"(-?\d+,\d)"
#: Une ligne : bénéficiaires, part, deux évolutions, montant moyen, son évolution,
#: dépenses du trimestre, leur évolution, contribution à la croissance.
_ROW = (rf"\s+{_COUNT}\s+{_RATE}\s+{_RATE}\s+{_RATE}\s*(\d+)\s+{_RATE}\s+{_COUNT}"
        rf"\s+{_RATE}\s+{_RATE}")
_FIELD = re.compile(
    r"représente\s+(\d+,\d)\s*%\s+des\s+dépenses\s+et\s+(\d+,\d)\s*%\s+des\s+bénéficiaires"
    r"\s+tous\s+régimes\s+en\s+(\d{4})")
_FORFAIT = re.compile(
    r"une\s+augmentation\s+de\s+1\s*%\s+de\s+ceux-ci\s+fait\s+progresser\s+les\s+dépenses"
    r"\s+de\s+(\d+,\d)\s*%\s+en\s+(\d{4})")
_ACTIVITE = re.compile(
    r"quand\s+les\s+revenus\s+d.activité\s+augmentent\s+de\s+1\s*%,\s+les\s+dépenses"
    r"\s+diminuent\s+de\s+(\d+,\d)\s*%\s+en\s+(\d{4})")
_SPENDING = re.compile(r"passent\s+de\s+(\d+,\d+)\s+milliards\s+d.euros\s+à\s+(\d+,\d+)"
                       r"\s+milliards\s+d.euros")
_ANNUAL = re.compile(r"(\d,\d+)\s+millions\s+de\s+foyers\s+perçoivent\s+la\s+prestation\s+"
                     r"en\s+(\d{4}),\s+pour\s+un\s+montant\s+moyen\s+de\s+(\d+)\s+euros")


class CnafError(RuntimeError):
    """Une publication de la Cnaf ne dit pas ce que la mesure lui fait dire."""


@dataclass(frozen=True)
class Cellule:
    """Une ligne du tableau 1 : le trimestre, pas l'année."""

    beneficiaires: float      # foyers, moyenne du trimestre
    montant_moyen: float      # € par mois
    depense_trimestre: float  # €


@dataclass(frozen=True)
class Conjoncture:
    """Le tableau 1 du quatrième trimestre 2024, et le champ des Caf."""

    ensemble: Cellule
    configurations: dict[str, Cellule]
    ages: dict[str, Cellule]
    sous_populations: dict[str, Cellule]
    part_caf_beneficiaires: float
    part_caf_depenses: float


@dataclass(frozen=True)
class Elasticites:
    """L'encadré 2 : la variation de la dépense pour 1 % de plus, et l'année."""

    forfait: float
    revenus_activite: float
    annee: int
    depense_annuelle: float   # € versés par les Caf dans l'année
    beneficiaires_annuels: float
    montant_moyen_annuel: float


def _number(text: str) -> float:
    return float(text.replace(" ", "").replace(",", "."))


def _pages(pdf: Path) -> list[str]:
    from pypdf import PdfReader

    if not pdf.exists():
        raise CnafError(f"{pdf.name} absent : `impots donnees` le télécharge (manifeste)")
    return [page.extract_text() or "" for page in PdfReader(str(pdf)).pages]


def _row(text: str, label: str) -> Cellule:
    found = re.search(re.escape(label) + _ROW, text)
    if found is None:
        raise CnafError(f"PA Conjoncture n° 32, tableau 1 : la ligne « {label} » manque")
    return Cellule(beneficiaires=_number(found[1]) * 1e3,
                   montant_moyen=_number(found[5]),
                   depense_trimestre=_number(found[7]) * 1e6)


def _check_sum(parts: dict[str, Cellule], whole: Cellule, what: str) -> None:
    """Les lignes doivent faire l'ensemble, à l'arrondi du millier et du million près."""
    count = sum(cell.beneficiaires for cell in parts.values())
    spend = sum(cell.depense_trimestre for cell in parts.values())
    if abs(count - whole.beneficiaires) > 3e3 or abs(spend - whole.depense_trimestre) > 3e6:
        raise CnafError(
            f"PA Conjoncture n° 32 : les {what} font {count / 1e3:.0f} milliers de foyers et "
            f"{spend / 1e6:.0f} M€, l'ensemble {whole.beneficiaires / 1e3:.0f} milliers et "
            f"{whole.depense_trimestre / 1e6:.0f} M€ ; la lecture est fausse")


@lru_cache(maxsize=2)
def conjoncture(pdf: Path = CONJONCTURE) -> Conjoncture:
    """Le tableau 1, p. 4, et le champ, p. 2."""
    pages = _pages(pdf)
    if len(pages) < 4:
        raise CnafError(f"PA Conjoncture n° 32 : {len(pages)} pages, le tableau 1 est p. 4")
    table = pages[3]
    ensemble = _row(table, "Ensemble")
    configurations = {key: _row(table, label) for key, label in CONFIGURATIONS}
    ages = {key: _row(table, label) for key, label in AGES}
    sous = {key: _row(table, label) for key, label in SOUS_POPULATIONS}
    _check_sum(configurations, ensemble, "configurations familiales")
    _check_sum(ages, ensemble, "tranches d'âge")
    field = _FIELD.search(pages[1])
    if field is None:
        raise CnafError("PA Conjoncture n° 32, p. 2 : la part des Caf dans tous les régimes "
                        "manque")
    share_spend, share_count = _number(field[1]) / 100, _number(field[2]) / 100
    if not (0.9 < share_count <= 1 and 0.9 < share_spend <= 1):
        raise CnafError(f"PA Conjoncture n° 32 : une part des Caf de {share_count:.1%} des "
                        f"bénéficiaires et {share_spend:.1%} des dépenses ; la lecture est "
                        "fausse")
    return Conjoncture(ensemble=ensemble, configurations=configurations, ages=ages,
                       sous_populations=sous, part_caf_beneficiaires=share_count,
                       part_caf_depenses=share_spend)


@lru_cache(maxsize=2)
def elasticites(pdf: Path = ANALYSES) -> Elasticites:
    """L'encadré 2, p. 3, et les chiffres clés, p. 1."""
    pages = _pages(pdf)
    if len(pages) < 3:
        raise CnafError(f"Analyses statistiques n° 5 : {len(pages)} pages, l'encadré 2 est "
                        "p. 3")
    forfait = _FORFAIT.search(pages[2])
    activite = _ACTIVITE.search(pages[2])
    if forfait is None or activite is None:
        raise CnafError("Analyses statistiques n° 5, encadré 2 : une élasticité manque")
    if forfait[2] != activite[2]:
        raise CnafError(f"Analyses statistiques n° 5 : élasticités de {forfait[2]} et de "
                        f"{activite[2]}")
    spending = _SPENDING.search(pages[0])
    annual = _ANNUAL.search(pages[0])
    if spending is None or annual is None:
        raise CnafError("Analyses statistiques n° 5, p. 1 : la dépense ou les bénéficiaires "
                        "de l'année manquent")
    if annual[2] != forfait[2]:
        raise CnafError(f"Analyses statistiques n° 5 : bénéficiaires de {annual[2]}, "
                        f"élasticités de {forfait[2]}")
    out = Elasticites(forfait=_number(forfait[1]) / 100,
                      revenus_activite=-_number(activite[1]) / 100,
                      annee=int(forfait[2]),
                      depense_annuelle=_number(spending[2]) * 1e9,
                      beneficiaires_annuels=_number(annual[1]) * 1e6,
                      montant_moyen_annuel=_number(annual[3]))
    if not (out.forfait > 1 / 100 and out.revenus_activite < 0):
        raise CnafError(f"Analyses statistiques n° 5 : élasticité au forfait {out.forfait:.1%}"
                        f", aux revenus d'activité {out.revenus_activite:.1%} ; la lecture est "
                        "fausse")
    return out
