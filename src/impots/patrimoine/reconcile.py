"""The patrimoine section of the reconciliation report (Phase 5 M5).

**Nothing in this module is calibrated, so every line here is validation or context.**
That is the section's distinctive property and it is stated on the page rather than left
for a reader to infer: DGFiP publishes the population, so the cells are read rather than
fitted, and there is no margin to spend. The household report has four calibration lines
and says so; this one has none.

WHICH TOTAL THE MODEL IS COMPARED AGAINST, and why the spec's instruction could not be
followed literally. `PHASE5_SPEC` §6 says to check "total IFI yield vs the budget line
(~2.2-2.3 bn recent years)". Those two halves are inconsistent, and following the
sentence would have printed a residual that is not model error:

  * the DGFiP statistical bulletin reports **2,159 md** for the 2024 assessment;
  * budget line 1406 books **2,739 md** for exécution 2024 — read from the Voies et
    Moyens annexe to the PLF 2026, page 23;
  * the gap is **+26,9 %**, and it is entirely accounting basis.

The publisher of both series says so itself, in the very bulletin the cells come from
(n° 33, encadré 1): «En pratique, l'administration fiscale collecte chaque année les
montants d'impôt indiqués dans les avis, mais aussi ceux non recouvrés des émissions
antérieures ainsi que ceux relatifs aux contrôles fiscaux. Les données budgétaires
publiées par ailleurs peuvent donc être différentes des montants présentés dans cette
publication.»

So the model is judged against the **émission** basis, which is the one it computes, and
the budget line appears as **context** with the difference named. Comparing a
declaration-based simulation to a cash-collection line would report roughly a quarter of
the tax as model error when it is prior-year recovery and contrôle fiscal.

A trap worth recording because it nearly caught the reading: **2 739 M€ also appears on
page 29 of the same document**, for accises on natural gas. A grep for the number finds
the wrong line first.

WHAT IS ACTUALLY VALIDATED HERE, since most of the obvious candidates are tautologies.
The cells are read from the publication, so comparing their counts or their tax back to
the publication proves arithmetic and nothing else. The one genuinely falsifiable line is
the mechanical check of M2: invert the barème on each tranche's published mean tax, sum
the implied bases, and confront the total with the **independently published** aggregate
base. Two separate publications, joined only by our arithmetic.
"""

from __future__ import annotations

from pathlib import Path

from impots import reporting
from impots.patrimoine import cells as cells_module
from impots.patrimoine import ifi_cells

REPORTS = Path(__file__).resolve().parents[3] / "reports"

Line = reporting.Line
Figure = reporting.Figure

DGFIP_IFI_URL = "https://www.impots.gouv.fr/dgfip-statistiques-limpot-sur-la-fortune-immobiliere-en-2024"
VM_URL = (
    "https://www.assemblee-nationale.fr/dyn/dyn/contenu/visualisation/1087930/"
    "file/PLF%202026%20-%20V&M%20TI%20-%20Evaluations%20des%20recettes.pdf"
)

#: The aggregate net taxable wealth DGFiP publishes for the 2024 assessment. This is the
#: comparator for the barème-inversion check, and it is published INDEPENDENTLY of the
#: per-tranche tax the check inverts — which is what stops the check being circular.
BASE_AGREGEE = Figure(
    value=466_792_714_707.0, unit="EUR", year=2024,
    scope="Patrimoine net total imposable à l'IFI, France entière, émissions 2024",
    source="DGFiP Statistiques n° 45, tableau 1", url=DGFIP_IFI_URL, use="validation",
    caveat="Publié à part de l'impôt par tranche, ce qui rend la confrontation non "
           "circulaire. L'en-tête du tableau annonce des M€ et les cellules sont en "
           "euros (D-078).",
)

#: The IFI total on the ÉMISSION basis — what our engine computes.
IFI_EMISSIONS = Figure(
    value=2_158_803_348.0, unit="EUR", year=2024,
    scope="IFI payé, base émissions, France entière",
    source="DGFiP Statistiques n° 45, tableau 1", url=DGFIP_IFI_URL, use="context",
    caveat="Contexte et non validation : les cellules sont LUES dans cette publication, "
           "donc leur somme la reproduit par construction. Comparer les deux mesurerait "
           "notre arithmétique de lecture, pas le modèle.",
)

#: The budget line, on the collection basis. Context only, and the note says why.
IFI_LIGNE_BUDGETAIRE = Figure(
    value=2_739_000_000.0, unit="EUR", year=2024,
    scope="Recettes d'IFI encaissées, ligne 1406, exécution budgétaire 2024",
    source="Évaluation des voies et moyens, annexe au PLF 2026, tome I, p. 23",
    url=VM_URL, use="context",
    caveat="BASE COMPTABLE DIFFÉRENTE. Encaissements, incluant les émissions "
           "antérieures non recouvrées et le contrôle fiscal ; le bulletin statistique "
           "est sur base d'émission. La DGFiP le dit elle-même dans l'encadré 1 du "
           "n° 33. Le modèle ne doit PAS être jugé contre cette ligne.",
)

#: Declared tolerance on the inversion check. Wide, and the width is reasoned: the
#: shortfall it measures is the reliefs the inversion cannot see, and M2 apportions them
#: — 58 % dons, up to 3 % décote, the rest plafonnement. A tight tolerance here would be
#: pretending the reliefs are small rather than measuring them.
TOLERANCE_INVERSION = 0.12


def build_lines(year: int = ifi_cells.TRANCHE_YEAR) -> list[Line]:
    """The patrimoine lines. All validation or context — nothing is calibrated."""
    check = cells_module.mechanical_check(year)
    dons_share = check.dons_explains_eur / check.shortfall_eur
    decote_share = check.decote_explains_at_most_eur / check.shortfall_eur
    rest_share = check.unexplained_eur / check.shortfall_eur

    return [
        Line.from_figure(
            BASE_AGREGEE, "Base agrégée — barème inversé",
            check.reconstructed_base_eur, TOLERANCE_INVERSION,
            f"**La seule ligne réellement falsifiable de cette section, et rien n'y est "
            f"calibré.** La base par tranche n'est pas publiée (D-078), donc chaque "
            f"cellule tire sa base moyenne en INVERSANT le barème sur son impôt moyen "
            f"publié ; l'agrégat reconstitué est ensuite confronté à un agrégat publié "
            f"SÉPARÉMENT. Deux publications distinctes, reliées par notre seule "
            f"arithmétique.\n\n"
            f"Le manque est attendu et son SIGNE est le test : décote, plafonnement et "
            f"réduction dons baissent tous l'impôt, donc inverser l'impôt doit "
            f"sous-estimer la base. Un manque de signe inverse voudrait dire que "
            f"l'arithmétique est fausse, pas incomplète.\n\n"
            f"Décomposé plutôt que toléré : les dons expliquent {dons_share:.0%} du "
            f"manque (montant publié, réduction à 75 %, plafond par foyer NON appliqué "
            f"donc borne haute), la décote au plus {decote_share:.0%}, et "
            f"{rest_share:.0%} restent pour le plafonnement — **nommé et non attribué**, "
            f"faute de quoi le répartir par différence reviendrait à l'appeler expliqué.",
            source="DGFiP",
        ),
        Line.from_figure(
            IFI_EMISSIONS, "IFI total — base émissions (pour mémoire)",
            sum(cell.published_ifi_eur for cell in check.cells), 0.01,
            "Contexte, pas validation, et la distinction est la règle du registre : les "
            "cellules sont LUES dans cette publication, donc leur somme la reproduit à "
            "l'arrondi près. Ce que cette ligne vérifie est notre lecture — colonnes "
            "appariées, unités, effectifs — et rien d'autre.",
            source="DGFiP",
        ),
        Line.from_figure(
            IFI_LIGNE_BUDGETAIRE, "IFI — ligne budgétaire 1406 (autre base)",
            None, 0.30,
            f"**Le modèle n'est pas jugé contre cette ligne, et c'est le point.** Elle "
            f"vaut 2 739 M€ pour l'exécution 2024 quand le bulletin statistique porte "
            f"2 159 M€ pour le même millésime d'imposition, soit "
            f"{IFI_LIGNE_BUDGETAIRE.value / IFI_EMISSIONS.value - 1:+.1%} — un écart "
            f"entièrement comptable. La ligne budgétaire est sur base d'ENCAISSEMENT et "
            f"agrège les avis courants, les émissions antérieures non recouvrées et le "
            f"contrôle fiscal ; le bulletin est sur base d'ÉMISSION, qui est ce que le "
            f"moteur calcule.\n\n"
            f"L'éditeur des deux séries le dit lui-même, dans le bulletin d'où viennent "
            f"les cellules : « Les données budgétaires publiées par ailleurs peuvent "
            f"donc être différentes des montants présentés dans cette publication. »\n\n"
            f"`PHASE5_SPEC` §6 demandait de comparer « vs the budget line (~2,2-2,3 bn) "
            f"» : les deux moitiés de cette phrase ne désignent pas la même série, et "
            f"suivre la lettre aurait imprimé un quart de l'impôt comme erreur de "
            f"modèle.",
            source="Voies et moyens, PLF 2026",
        ),
    ]


INTRO = (
    "**Aucune ligne de cette section n'est calibrée.** C'est la propriété distinctive du "
    "module et la raison d'avoir choisi cette phase : la DGFiP publie la population, donc "
    "les cellules sont LUES et non ajustées, et il n'y a aucune marge à dépenser. Le "
    "rapport ménages porte quatre lignes de calibration et le dit ; celui-ci n'en porte "
    "aucune.\n\n"
    "Millésimes du comparateur, tous les trois différents : tranches **2024** (n° 33, "
    "paru en avril 2025), agrégats **2024** (n° 45, paru en avril 2026), droit appliqué "
    "**2024**. Une quatrième année existe et ne sert PAS à juger le modèle — l'année de "
    "comptabilisation budgétaire, dont la ligne figure ci-dessous en contexte."
)


def render(year: int = ifi_cells.TRANCHE_YEAR) -> str:
    """The patrimoine report, as markdown."""
    sources = {
        "BASE_AGREGEE": BASE_AGREGEE,
        "IFI_EMISSIONS": IFI_EMISSIONS,
        "IFI_LIGNE_BUDGETAIRE": IFI_LIGNE_BUDGETAIRE,
    }
    return reporting.render(
        title="Reconciliation report — patrimoine (IFI)",
        vintage=str(year),
        engine="openfisca-france 176.0.8, corrigé (D-079)",
        intro=INTRO,
        lines=build_lines(year),
        sources=sources,
        notes=method_notes(year),
        generated_by="impots patrimoine reconcile",
    )


def method_notes(year: int = ifi_cells.TRANCHE_YEAR) -> list[str]:
    """What a reader needs to judge the section, said once and in full."""
    check = cells_module.mechanical_check(year)
    return [
        "### Pourquoi le modèle n'est pas jugé contre la ligne budgétaire",
        "",
        "La ligne 1406 vaut 2 739 M€ en exécution 2024 ; le bulletin statistique porte "
        "2 159 M€ pour le même millésime d'imposition. L'écart de +26,9 % est "
        "**entièrement comptable** : la ligne budgétaire est sur base d'encaissement et "
        "agrège les avis courants, les émissions antérieures non recouvrées et le "
        "contrôle fiscal, quand le bulletin est sur base d'émission — ce que le moteur "
        "calcule. L'éditeur des deux séries l'écrit dans l'encadré 1 du n° 33 : « Les "
        "données budgétaires publiées par ailleurs peuvent donc être différentes des "
        "montants présentés dans cette publication. »",
        "",
        "### Ce que la ligne falsifiable teste, et ce qu'elle ne teste pas",
        "",
        f"Base reconstituée {check.reconstructed_base_eur / 1e9:.2f} md contre "
        f"{check.aggregate.base_eur / 1e9:.2f} md publiés, soit "
        f"{-check.shortfall_share:+.2%}. Le manque est ce que l'inversion ne peut pas "
        f"voir, et il est réparti plutôt que toléré : dons "
        f"{check.dons_explains_eur / 1e9:.2f} md, décote au plus "
        f"{check.decote_explains_at_most_eur / 1e9:.2f} md, reste "
        f"{check.unexplained_eur / 1e9:.2f} md laissé au plafonnement, **nommé et non "
        f"attribué**.",
        "",
        "Ce que la section ne teste pas : le niveau de l'IFI lui-même. Les cellules "
        "étant lues dans la publication, leur somme la reproduit par construction, et "
        "une ligne qui s'en féliciterait mesurerait notre lecture.",
    ]


def write(year: int = ifi_cells.TRANCHE_YEAR) -> Path:
    """Write the patrimoine report beside the household and firm ones."""
    return reporting.write(REPORTS / "reconciliation_patrimoine.md", render(year))
