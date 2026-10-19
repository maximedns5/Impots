"""PHASE9_SPEC §9.4 — l'exemple au dossier ne doit pas pouvoir dériver de la chaîne (D-228).

La leçon de D-154, appliquée à une page de dette : un document généré qui s'écarte du code
qu'il illustre est plus dangereux qu'un document absent, parce qu'il sera cru. Trois
gardes, de la moins chère à la plus chère : la page commitée est le rendu du fichier
commité ; le fichier décrit la réforme que le script nomme ; et, là où les comptes APU et
Mésange sont lisibles, les trajectoires du fichier sont ce que la chaîne calcule
aujourd'hui depuis la première année qu'il porte.
"""

from __future__ import annotations

import importlib.util
import json
import math
import sys
from pathlib import Path
from typing import Any

import pytest

from impots.dette import reference
from impots.dette.path import DebtError
from impots.macro import mesange
from impots.predictif import chaine
from impots.predictif.theta import ThetaError
from macro_cases import synthetic_macro_store

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "write_predictif_exemple.py"


def _module():
    spec = importlib.util.spec_from_file_location("write_predictif_exemple", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def script():
    return _module()


@pytest.fixture(scope="module")
def snapshot(script) -> dict[str, Any]:
    return json.loads(script.SNAPSHOT.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def rendered(script, snapshot) -> str:
    return script.render(snapshot)


def test_the_committed_page_is_what_the_script_renders(script, rendered) -> None:
    """LA GARDE ANTI-DÉRIVE. Elle tombe dès qu'on édite la page à la main, ou qu'on change
    le rendu sans relancer le script. Sans données : elle court partout."""
    assert script.OUT.read_text(encoding="utf-8") == rendered, (
        "docs/PREDICTIF_EXEMPLE.md a dérivé de scripts/write_predictif_exemple.py — "
        "relancer le script plutôt que d'éditer la page.")


def test_the_file_prices_the_reform_the_script_names(script, snapshot) -> None:
    """Changer le taux de l'exemple sans refaire la passe laisserait un fichier qui
    chiffre une autre réforme que celle que le script décrit."""
    first = snapshot["premiere_annee"]
    assert script._first_bracket(first) == (script.FROM_RATE, script.TO_RATE)
    assert snapshot["hypotheses"]["horizon"] == script.HORIZON
    assert [(t["regle"], t["persistance"]) for t in snapshot["trajectoires"]] == list(
        script.SCENARIOS)
    assert len(snapshot["trajectoires"][0]["annees"]) == script.HORIZON


def test_the_page_says_it_illustrates_and_recommends_nothing(rendered) -> None:
    assert "illustre la machinerie ; elle ne recommande rien" in rendered
    assert "choisie pour la pédagogie" in rendered
    assert chaine.BANNER in rendered


def test_every_closed_channel_rides_with_its_reason(rendered, snapshot) -> None:
    """§9.4 : « avec les canaux fermés listés et leur raison ». Les cinq de la chaîne sous
    chaque règle, et les deux de la boucle sous la règle où elle ne s'applique pas."""
    for name, reason in chaine.CLOSED.items():
        assert f"- **{name}** : {reason}" in rendered, name
    unlooped = [t for t in snapshot["trajectoires"] if t["persistance"] is None]
    assert unlooped, "l'exemple doit montrer une règle sans boucle"
    for name in chaine.MACRO_CHANNELS:
        assert f"- **{name}**, sous « {unlooped[0]['depense']} » seulement : " in rendered


def test_every_figure_is_named_by_its_spending_scenario(rendered, snapshot) -> None:
    """§3.5 : une trajectoire ne s'affiche jamais sans le nom de son scénario de dépense,
    et sous « gelées en volume » jamais sans sa persistance."""
    for t in snapshot["trajectoires"]:
        assert rendered.count(t["depense"]) >= 6, t["depense"]
        if t["persistance"] is not None:
            assert t["persistance_libelle"].lower() in rendered


# --------------------------------------------------------------------------- #
# the chain stage, on constructed inputs: runs everywhere
# --------------------------------------------------------------------------- #
START = reference.Start(year=2025, gdp_eur=3_000e9, receipts_ratio=0.52,
                        spending_ratio=0.55, debt_ratio=1.15, implicit_rate=0.019)


def _first(central: float, box: tuple[float, float] = (-5.0e9, -4.7e9)) -> dict[str, Any]:
    """A priced first year as the file holds it: 5 Md€ of cost, and receipts at the four
    corners of the two ETI rows that rise as each row's θ does."""
    corners = [{"rows": {"eti_all": a, "eti_top_decile": b},
                "receipts": -5.0e9 + 0.2e9 * a + 0.1e9 * b}
               for a in (0.0, 1.0) for b in (0.0, 1.0)]
    return {"annee": 2026, "cout_eur": 5.0e9,
            "impulsion": {"impot_sur_le_revenu": 5.0e9}, "non_couverts": {},
            "comportement": {"recettes": central, "boite": list(box),
                             "grade": "in-support", "lignes": ["eti_all", "eti_top_decile"],
                             "coins": corners}}


def test_the_box_is_read_at_every_corner_and_the_loop_only_where_it_applies(
        script) -> None:
    paths = script.trajectories(_first(-4.85e9), start=START,
                                macro_store=synthetic_macro_store())
    looped, held, unlooped = paths
    assert len(looped["coins"]) == len(held["coins"]) == 8      # two rows and the multiplier
    assert len(unlooped["coins"]) == 4                          # the two rows alone
    assert all("multiplicateur_macro" not in c["label"] for c in unlooped["coins"])
    for t in paths:
        values = [c["delta"] for c in t["coins"]]
        assert min(values) <= t["delta"][-1] <= max(values)
    # without the loop, the two persistence scenarios are one path, and the unlooped
    # rule's Δb is its own path without the loop, to the float
    assert looped["delta_sans_retroaction"] == held["delta_sans_retroaction"]
    assert unlooped["delta"] == unlooped["delta_sans_retroaction"]
    assert looped["delta"] != held["delta"]
    assert "rétroaction" in unlooped["absent"]


def test_a_delta_at_theta_outside_the_corners_is_refused(script) -> None:
    """GUARD. The box is read at its corners only if each effect is monotone in its θ.
    Receipts at θ = ½ better than at every corner say it is not — here a file whose
    first-year box holds them while its corners do not — and the page would then print a
    box that does not hold the central figure."""
    with pytest.raises(ThetaError, match="sort des coins"):
        script.trajectories(_first(-2.0e9, box=(-5.0e9, -2.0e9)), start=START,
                            macro_store=synthetic_macro_store())


# --------------------------------------------------------------------------- #
# the file against the chain of today: where the accounts and Mésange are readable
# --------------------------------------------------------------------------- #
def _close(a: Any, b: Any, where: str = "") -> None:
    if isinstance(a, float) or isinstance(b, float):
        assert math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-15), where
    elif isinstance(a, dict):
        assert a.keys() == b.keys(), where
        for k in a:
            _close(a[k], b[k], f"{where}.{k}")
    elif isinstance(a, list):
        assert len(a) == len(b), where
        for i, (x, y) in enumerate(zip(a, b, strict=True)):
            _close(x, y, f"{where}[{i}]")
    else:
        assert a == b, where


def test_the_file_is_what_the_chain_computes_today(script, snapshot) -> None:
    """A change of multiplier, of the carry convention, of the loop or of a closed
    channel's reason moves the trajectories: the file must then be re-rendered, and the
    page with it. The population pass is not replayed — three minutes — and the page
    names the commit it ran on."""
    pytest.importorskip("pypdf")
    if not (mesange.RAW / mesange.SOURCE_FILE).exists():
        pytest.skip("data/raw/ n'a pas le document Mésange")
    try:
        start = script._start()
    except (DebtError, OSError) as error:
        pytest.skip(f"comptes APU illisibles dans ce checkout : {error}")
    assert snapshot["depart"] == pytest.approx(
        {"annee": start.year, "dette": start.debt_ratio,
         "solde_primaire": start.primary_balance, "taux_implicite": start.implicit_rate,
         "pib_eur": start.gdp_eur}, rel=1e-12)
    today = script.trajectories(snapshot["premiere_annee"], start=start,
                                macro_store=script._macro_store())
    _close(today, snapshot["trajectoires"], "trajectoires")
