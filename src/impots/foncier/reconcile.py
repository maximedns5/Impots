"""F5 M3 — the taxe foncière reconciliation, and the household figure this cannot give.

**The surface stops at the commune, and that is the finding rather than a gap to fill
later.** The REI is a communal file: it publishes a commune's total base and its rates. It
does not publish, and nothing open publishes, the valeur locative of an individual
property. So this module can price a TF reform nationally or for any set of communes, and
it **cannot tell a household what its taxe foncière is** — not approximately, not with a
caveat. A household's TF is its own property's valeur locative times its commune's rates,
and the first factor does not exist in any open source.

That is why there is no household-calculator extension here. Adding a commune selector
that returned a commune's RATE beside the household's other figures would read as a TF
estimate to every user who saw it, and the rate alone is not one. The refusal is the
feature.

WHAT THE RECONCILIATION LINE IS, AND WHY IT IS UNUSUALLY STRONG. Everywhere else in this
project a reconciliation line asks «does our synthetic population reproduce a published
total», and a calibrated line proves nothing because it was fitted. Here the cells are
PUBLISHED, so the line asks «does our arithmetic on their bases reproduce their produits».
Nothing was fitted to anything. It is the only line in the project that is neither
calibration nor a comparison against an independent estimate: it is an audit of an
identity, and it either holds or it does not.
"""

from __future__ import annotations

from typing import Any

from impots import reporting
from impots.foncier import cells as cells_module

#: Comparator, with its perimeter, because the perimeter is half the information here:
#: DGFiP Statistiques n° 46 leads with 55,1 Md€ INCLUDING taxes annexes and frais de
#: gestion, and that is NOT what a base x rate reconstruction produces. Taking the
#: headline gives -21 % and condemns a correct reading (D-100).
PUBLISHED_FB_EUR = 43.1e9
PUBLISHED_SOURCE = (
    "DGFiP Statistiques n° 46 (mai 2026), « hors taxes annexes et frais de gestion, les "
    "montants dus de TFPB sont de 43,1 Md€ en 2025 ». Le titre de la publication, "
    "55,1 Md€, LES INCLUT et n'est pas le comparateur d'une reconstitution base × taux."
)

#: Declared tolerance. 2 % rather than 1 % because the document does not say which strata
#: count among the «taxes annexes» it excludes, so the two defensible reconstructions —
#: commune+interco at -0,76 % and all strata at +0,89 % — must both pass.
TOLERANCE = 0.02


def identity_audit(cells: cells_module.Cells) -> dict[str, Any]:
    """The identity check, reported as an AUDIT rather than as a reconciliation line.

    It does not fit the `Line` shape and forcing it in was a category error: a Line
    compares a simulated figure to a published target, and this compares a computed
    figure to the SAME SOURCE's own figure, per commune, with a target of zero error. A
    zero target has no relative residual, which is exactly what broke `Line.status` when
    the attempt was made.
    """
    residuals = cells_module.identity_residuals(cells)
    return {
        "communes": int(residuals.height),
        "median_relative_error": float(residuals["residual"].median()),
        "p99_relative_error": float(residuals["residual"].quantile(0.99)),
        "unexplained": int((residuals["residual"]
                            > cells_module.IDENTITY_TOLERANCE).sum()),
        "note": (
            "Ce n'est pas une calibration et ce n'est pas une validation externe : les "
            "bases et les taux sont PUBLIÉS, rien n'a été ajusté à rien, et cet audit "
            "vérifie une IDENTITÉ. Les communes restantes au-delà de 1 % sont épinglées "
            "comme inexpliquées (D-111) — aucune ne porte de lissage, donc ce terme "
            "n'est pas ce qui manque. 46 des 55 ont un taux effectif SOUS leur taux "
            "publié, ce qui désignerait un abattement non lu ; mais 9 vont dans "
            "l'AUTRE sens, qu'aucun abattement n'explique. Les 454 colonnes non nulles "
            "du REI ont été balayées sur ces communes et aucune ne reproduit l'écart, "
            "la plus proche à 71 % près (C3, D-127). L'écart net vaut 34 886 € sur "
            "43,487 md€, soit 8,0e-07 du produit national : épinglé avec la tentative "
            "au dossier, pas expliqué."),
    }


def lines(cells: cells_module.Cells) -> list[Any]:
    """The TF reconciliation line: the national comparison. The identity is an audit."""
    national = cells_module.national(cells)

    return [
        reporting.Line(
            label="Taxe foncière bâtie, produit national",
            simulated=national, published=PUBLISHED_FB_EUR, unit="EUR",
            source=PUBLISHED_SOURCE, use="validation", tolerance=TOLERANCE,
            note=(
                "COMPARAISON PARTIELLEMENT CIRCULAIRE, et il faut le dire : la "
                "publication n° 46 est tirée du même REI. Cette ligne valide donc notre "
                "LECTURE du fichier — les bonnes colonnes, le bon facteur cent sur les "
                "taux, le terme de lissage — et non un modèle. Une validation externe "
                "demanderait des recettes constatées en comptabilité publique, pas la "
                "statistique dérivée du fichier d'entrée."),
        ),
    ]


def household_refusal() -> str:
    """Why there is no per-household taxe foncière, in the words a UI would print."""
    return (
        "Ce modèle ne peut pas calculer VOTRE taxe foncière, et ce n'est pas une "
        "limite temporaire. La TF d'un logement est la valeur locative cadastrale de ce "
        "logement multipliée par les taux de sa commune. Les taux sont publiés — ils "
        "sont dans le REI, commune par commune. La valeur locative de votre logement ne "
        "l'est pas, et aucune source ouverte ne la publie. Afficher le taux de votre "
        "commune à côté de vos autres chiffres se lirait comme une estimation de votre "
        "impôt ; ce n'en serait pas une."
    )
