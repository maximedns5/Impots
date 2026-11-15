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
