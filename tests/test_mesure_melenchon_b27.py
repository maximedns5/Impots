"""Le volet `mesure` du but 27 (D-508, D-509) : la convention « premiere_annee_d521 », qui
porte une mesure de l'étude aux nombres d'une passe, sur le jumeau seul (aucune passe)."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
P = "pres2027_melenchon_"


@pytest.fixture(scope="module")
def script():
    spec = importlib.util.spec_from_file_location(
        "mesure_melenchon_b27", ROOT / "scripts" / "mesure_melenchon_b27.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _passe_de_l_etude(session, cle, facteur=1.0):
    """Une passe faite des nombres de l'étude, multipliés par `facteur`."""
    c = session.candidats[cle]
    reponse = c["premiere_annee"]["response"]
    imp = c["payload"]["years"][0]["statistiques"]["figee"]["impulses"]
    return {"reform_cost": reponse["reform_cost"] * facteur,
            "deltas": {k: v * facteur for k, v in reponse["deltas"].items()},
            "deciles": [{**d, "mean_delta": d["mean_delta"] * facteur}
                        for d in reponse["deciles"]],
            "impulsions": {k: v * facteur for k, v in imp.items()}}


def test_a_facteur_un_le_jumeau_du_smic_est_celui_de_l_etude(script):
    s = script.session()
    cle = P + "smic_1700_net"
    avant = script.smic_jumeau(s)["figee"]["court"]
    script.redimensionner(s, cle, _passe_de_l_etude(s, cle))
    assert script.smic_jumeau(s)["figee"]["court"] == avant


def test_la_somme_d_avant_d440_suit_le_facteur(script):
    # D-509, correctif de D-508 : sans elle, le point d'indice redimensionné était refusé
    # par la ventilation (« prélèvements hors cotisations des employeurs nuls en 2026, pas
    # en 2027… »), et le Smic lisait une somme d'avant que la passe ne portait plus.
    # D-683 : les rapports de la série de D-559 ne portent plus la somme d'avant D-440
    # (`recalcul`) ; la somme que lit le jumeau est alors ΔP du canal, qui suit le facteur.
    s = script.session()
    cle = P + "point_indice_10"
    k = script.redimensionner(s, cle, _passe_de_l_etude(s, cle, 0.99))
    m = s.mesure(cle, "figee", "parts_premiere_annee")
    assert m.conventions["entreprises"][2035] == "parts_premiere_annee"
    payload = s.candidats[cle]["payload"]
    assert "recalcul" not in payload
    origine = json.loads((ROOT / "reports" / "etudes" / "presidentielle_melenchon" / "mesures"
                          / "point_indice_10"
                          / "predictif_pres2027_melenchon_point_indice_10.json")
                         .read_text(encoding="utf-8"))
    o = origine["rejeu"]["creations"]["variations"]["figee"]
    assert payload["rejeu"]["creations"]["variations"]["figee"][3] == pytest.approx(
        o[3] * k["k_creations"], rel=1e-12)
