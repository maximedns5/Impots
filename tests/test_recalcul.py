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
    assert len(RAPPORTS) == 46
    cible = vars(creations.charger().elasticite)
    for chemin in RAPPORTS:
        payload = json.loads(chemin.read_text(encoding="utf-8"))
        assert payload["rejeu"]["creations"]["parametres"]["elasticite"] == cible
        assert payload["creations"]["parametres"]["elasticite"] == cible
        assert payload["recalcul"]["decision"] == "D-427"
        assert payload["recalcul"]["nombres_refaits"] == recalcul.concerne(payload)


#: The reports the CVAE or the C3S moved, rewritten without them (D-440): Δb 2035 at θ½,
#: aged view, persistence « lue », points of GDP, before (D-427) and after.
SANS_PRODUCTION = {
    "predictif_pres2027_attal_a18_suppression_cvae": (0.2354, 0.2475),
    "predictif_pres2027_attal_programme": (4.2730, 4.2850),
    "predictif_pres2027_lisnard_l4_suppression_c3s_cvae": (1.5615, 1.6181),
    "predictif_pres2027_lisnard_programme": (5.6541, 5.7107),
    "predictif_pres2027_retailleau_r21_c3s_cvae_forfait_social_cfe": (1.5615, 1.6181),
    "predictif_pres2027_retailleau_programme": (11.3095, 11.3672)}


def _lue(payload) -> float:
    lue = next(s for s in payload["side_by_side"] if s["persistence"] == "lue")
    return 100 * lue["years"][-1]["delta_aged"]


def test_the_reports_the_production_taxes_moved_no_longer_read_them() -> None:
    """D-440: six reports, those whose firm reform moves the CVAE or the C3S, carry the
    channel without them and say it; D-444: the forty others, where they were zero, lose
    them from their lists and say it, their ΔP and every number unchanged."""
    for chemin in RAPPORTS:
        payload = json.loads(chemin.read_text(encoding="utf-8"))
        marque = payload["recalcul"].get("instruments")
        lus = [payload["creations"]["parametres"]["instruments_entreprises"],
               payload["rejeu"]["creations"]["parametres"]["instruments_entreprises"]]
        if chemin.stem in SANS_PRODUCTION:
            assert marque["decision"] == "D-440"
            assert marque["retires"] == list(creations.PRODUCTION)
            assert all(not set(creations.PRODUCTION) & set(i) for i in lus)
            assert marque["variations_avant"] != payload["rejeu"]["creations"]["variations"]
            assert {v: {str(r["year"]): x for r, x in zip(payload["years"], xs,
                                                          strict=True)}
                    for v, xs in payload["rejeu"]["creations"]["variations"].items()
                    } == payload["creations"]["prelevements_eur"]
        else:
            assert marque["decision"] == "D-444" and marque["nombres_refaits"] is False
            assert marque["retires"] == list(creations.PRODUCTION)
            assert all(not set(creations.PRODUCTION) & set(i) for i in lus)
            assert marque["variations_avant"] == payload["rejeu"]["creations"]["variations"]


def test_the_report_before_d440_is_given_back() -> None:
    """Each publishes its new number; ΔP before, the instruments put back and the numbers
    refitted, the number D-427 published (to the byte, D-440, checked once on git)."""
    for chemin in RAPPORTS:
        if chemin.stem not in SANS_PRODUCTION:
            continue
        avant, apres = SANS_PRODUCTION[chemin.stem]
        payload = json.loads(chemin.read_text(encoding="utf-8"))
        assert _lue(payload) == pytest.approx(apres, abs=5e-5)
        marque = payload["recalcul"].pop("instruments")
        block = payload["rejeu"]["creations"]
        block["variations"] = marque["variations_avant"]
        years = [str(r["year"]) for r in payload["years"]]
        payload["creations"]["prelevements_eur"] = {
            v: dict(zip(years, xs, strict=True)) for v, xs in block["variations"].items()}
        for snapshot in (block["parametres"], payload["creations"]["parametres"]):
            snapshot["instruments_entreprises"] += list(creations.PRODUCTION)
        recalcul._refaire(payload)
        assert recalcul.controle(recalcul.ecrire(payload)) == []
        assert _lue(payload) == pytest.approx(avant, abs=5e-5)


def test_retirer_refuses_what_it_cannot_take_out() -> None:
    chemin = next(c for c in RAPPORTS if c.stem in SANS_PRODUCTION)
    payload = json.loads(chemin.read_text(encoding="utf-8"))
    zeros = {v: [0.0] * len(xs) for v, xs in payload["rejeu"]["creations"]["variations"]
             .items()}
    with pytest.raises(recalcul.RecalculError, match="déjà été retirés"):
        recalcul.retirer(payload, zeros, ["impot_societes"], decision="x", date="y")
    del payload["recalcul"]["instruments"]
    with pytest.raises(recalcul.RecalculError, match="pas tous lus"):
        recalcul.retirer(payload, zeros, ["cvae"], decision="x", date="y")
    with pytest.raises(recalcul.RecalculError, match="vues"):
        recalcul.retirer(payload, {"figee": zeros["figee"]}, ["impot_societes"],
                         decision="x", date="y")


@pytest.mark.parametrize("chemin", RAPPORTS, ids=lambda c: c.stem)
def test_the_rewrite_at_its_own_slope_gives_the_report_back(chemin) -> None:
    """The control: to the byte for a report whose numbers were rewritten; for the others,
    to the byte but the families of `AU_PRES`, to 1e-11 relative."""
    texte = chemin.read_text(encoding="utf-8")
    assert recalcul.controle(texte) == []
    payload = json.loads(texte)
    if payload["recalcul"]["nombres_refaits"]:
        assert recalcul.ecrire(recalcul.recalculer(payload)) == texte


def test_back_to_the_old_slope_and_forth_is_the_report_to_the_byte() -> None:
    """At the slope before, then at D-427's, the rewritten report again, byte for byte:
    what the slope moves is all the rewrite moves."""
    for chemin in RAPPORTS:
        texte = chemin.read_text(encoding="utf-8")
        payload = json.loads(texte)
        if not payload["recalcul"]["nombres_refaits"]:
            continue
        marque = payload["recalcul"]
        avant = recalcul.recalculer(payload, marque["elasticite_avant"],
                                    decision=marque["decision"], date=marque["date"])
        assert avant["side_by_side"] != payload["side_by_side"]
        retour = recalcul.recalculer(avant, marque["elasticite"],
                                     decision=marque["decision"], date=marque["date"])
        assert recalcul.ecrire(retour) == texte


def test_a_report_without_the_channel_is_refused() -> None:
    with pytest.raises(recalcul.RecalculError, match="sans le canal"):
        recalcul.recalculer({"rejeu": {"creations": None}, "years": []})
