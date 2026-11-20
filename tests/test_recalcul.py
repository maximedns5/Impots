"""The studies' reports rewritten at D-427's slope without a pass (`predictif.recalcul`)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from impots.predictif import creations, recalcul

RACINE = Path(__file__).resolve().parents[1]
RAPPORTS = [c for c in sorted((RACINE / "reports" / "etudes").glob("**/predictif_*.json"))
            if (json.loads(c.read_text(encoding="utf-8")).get("rejeu") or {})
            .get("creations")]


def test_every_study_report_reads_the_channel_at_the_declared_slope() -> None:
    """D-683: the series of D-559 computed the 48 reports at D-427's slope in their pass;
    none carries the rewrite of D-427 (`recalcul`) any more. On the series of 5a68669,
    46 reports, each rewritten without a pass and marked."""
    assert len(RAPPORTS) == 48
    cible = vars(creations.charger().elasticite)
    for chemin in RAPPORTS:
        payload = json.loads(chemin.read_text(encoding="utf-8"))
        assert payload["rejeu"]["creations"]["parametres"]["elasticite"] == cible
        assert payload["creations"]["parametres"]["elasticite"] == cible
        assert "recalcul" not in payload


#: The six reports the CVAE or the C3S moved, which D-440 rewrote without them: Δb 2035 at
#: θ½, aged view, persistence « lue », points of GDP, after D-440 (series of 5a68669) and
#: on the series of D-559, computed by a pass without the two taxes (D-683).
SANS_PRODUCTION = {
    "predictif_pres2027_attal_a18_suppression_cvae": (0.2475, 0.2475),
    "predictif_pres2027_attal_programme": (4.2850, 3.9775),
    "predictif_pres2027_lisnard_l4_suppression_c3s_cvae": (1.6181, 1.6181),
    "predictif_pres2027_lisnard_programme": (5.7107, 5.7051),
    "predictif_pres2027_retailleau_r21_c3s_cvae_forfait_social_cfe": (1.6181, 1.6181),
    "predictif_pres2027_retailleau_programme": (11.3672, 10.8723)}


def _lue(payload) -> float:
    lue = next(s for s in payload["side_by_side"] if s["persistence"] == "lue")
    return 100 * lue["years"][-1]["delta_aged"]


def test_the_reports_the_production_taxes_moved_no_longer_read_them() -> None:
    """D-440, D-444: no report reads the CVAE or the C3S in the channel; on the series of
    D-559, from the pass on (D-683), not by a rewrite."""
    for chemin in RAPPORTS:
        payload = json.loads(chemin.read_text(encoding="utf-8"))
        lus = [payload["creations"]["parametres"]["instruments_entreprises"],
               payload["rejeu"]["creations"]["parametres"]["instruments_entreprises"]]
        assert all(not set(creations.PRODUCTION) & set(i) for i in lus)


def test_the_pass_gives_back_what_d440_rewrote() -> None:
    """D-683: the three measures alone D-440 rewrote without a pass give, computed by the
    pass of D-559, the number D-440 published, to 5e-5 point; the programmes their own
    (their other measures moved with the series)."""
    vus = set()
    for chemin in RAPPORTS:
        if chemin.stem not in SANS_PRODUCTION:
            continue
        d440, d559 = SANS_PRODUCTION[chemin.stem]
        assert _lue(json.loads(chemin.read_text(encoding="utf-8"))) == pytest.approx(
            d559, abs=5e-5)
        if "programme" not in chemin.stem:
            assert d559 == d440
        vus.add(chemin.stem)
    assert vus == set(SANS_PRODUCTION)


def test_retirer_refuses_what_it_cannot_take_out() -> None:
    chemin = next(c for c in RAPPORTS if c.stem in SANS_PRODUCTION)
    payload = json.loads(chemin.read_text(encoding="utf-8"))
    zeros = {v: [0.0] * len(xs) for v, xs in payload["rejeu"]["creations"]["variations"]
             .items()}
    retire = recalcul.retirer(payload, zeros, ["impot_societes"], decision="x", date="y")
    with pytest.raises(recalcul.RecalculError, match="déjà été retirés"):
        recalcul.retirer(retire, zeros, ["cebge"], decision="x", date="y")
    with pytest.raises(recalcul.RecalculError, match="pas tous lus"):
        recalcul.retirer(payload, zeros, ["cvae"], decision="x", date="y")
    with pytest.raises(recalcul.RecalculError, match="vues"):
        recalcul.retirer(payload, {"figee": zeros["figee"]}, ["impot_societes"],
                         decision="x", date="y")


@pytest.mark.parametrize("chemin", RAPPORTS, ids=lambda c: c.stem)
def test_the_rewrite_at_its_own_slope_gives_the_report_back(chemin) -> None:
    """The control, and the rewrite at the report's own slope: its paths, unchanged
    (D-683: on the series of D-559, computed by a pass, every report)."""
    texte = chemin.read_text(encoding="utf-8")
    assert recalcul.controle(texte) == []
    payload = json.loads(texte)
    assert recalcul.recalculer(payload)["side_by_side"] == payload["side_by_side"]


def test_back_to_the_old_slope_and_forth_is_the_report() -> None:
    """At the slope before D-427, then back at its own, the report's paths again, for
    each report the slope concerns: what the slope moves is all the rewrite moves."""
    avant = {"centre": 0.20, "bas": 0.043, "haut": 0.356}
    cible = vars(creations.charger().elasticite)
    vus = 0
    for chemin in RAPPORTS:
        payload = json.loads(chemin.read_text(encoding="utf-8"))
        if not recalcul.concerne(payload):
            continue
        vus += 1
        ancien = recalcul.recalculer(payload, avant, decision="D-427", date="x")
        assert ancien["side_by_side"] != payload["side_by_side"]
        retour = recalcul.recalculer(ancien, cible, decision="D-427", date="x")
        assert retour["side_by_side"] == payload["side_by_side"]
    assert vus > 0


def test_a_report_without_the_channel_is_refused() -> None:
    with pytest.raises(recalcul.RecalculError, match="sans le canal"):
        recalcul.recalculer({"rejeu": {"creations": None}, "years": []})
