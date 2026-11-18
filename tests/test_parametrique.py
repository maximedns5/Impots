"""Votre barème (D-660) : le réglage du lecteur traduit en boutons du moteur, la file, et
le jumeau sur les deux rapports d'une passe, chaque dimension dite illustrative.

Aucune passe sur la population ici : les deux passes (la première année, le chemin
annuel) sont remplacées par les rapports commités d'une mesure d'étude qui a le même
format, le Smic à 2 000 € bruts de Marine Tondelier ; le jumeau doit alors rendre, au bit,
les nombres de cette mesure lue comme une étude, sous un statut « illustratif ».
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from impots import parametrique

ROOT = Path(__file__).resolve().parents[1]
ETUDE = ROOT / "reports" / "etudes" / "presidentielle_tondelier" / "mesures" / "smic_2000_brut"
SCENARIO = "pres2027_tondelier_smic_2000_brut"
BAREME = [{"threshold": 0.0, "rate": 0.0}, {"threshold": 11_600.0, "rate": 0.11},
          {"threshold": 29_579.0, "rate": 0.3}, {"threshold": 84_577.0, "rate": 0.41},
          {"threshold": 181_917.0, "rate": 0.45}]


@pytest.fixture
def ici(tmp_path, monkeypatch) -> Path:
    monkeypatch.setenv(parametrique.ENV_DOSSIER, str(tmp_path / "propositions"))
    monkeypatch.setenv(parametrique.ENV_VERROU, str(tmp_path / "passe.lock"))

    def interdit(d: Path) -> None:
        raise AssertionError("un test ne lance jamais une passe sur la population")

    # Aucun test ne détache une vraie passe (D-661 : une première version l'a fait).
    monkeypatch.setattr(parametrique, "_detacher", interdit)
    return tmp_path / "propositions"


def test_each_setting_becomes_its_engine_knob() -> None:
    reform, imputations = parametrique.reforme(
        {"smic": 5, "rsa": 10, "prime_activite": -2.5, "pensions": 1, "ir_points": 1,
         "ir_tranche_seuil": 250_000, "ir_tranche_taux": 50, "tva_normal": 21,
         "cotisations_retraite": -10}, bareme=lambda: [dict(t) for t in BAREME])
    assert reform == {
        "smic_revalorisation": 1.05, "smic_diffusion_profil": "annee_avec_effets_fixes",
        "smic_diffusion_echelle": 0.0,
        "indexations": {"rsa": {"2026": 1.1}, "prime_activite": {"2026": 0.975},
                        "pensions": {"2026": 1.01}},
        "ir_bareme": [{"threshold": 0.0, "rate": 0.0}, {"threshold": 11_600.0, "rate": 0.12},
                      {"threshold": 29_579.0, "rate": 0.31},
                      {"threshold": 84_577.0, "rate": 0.42},
                      {"threshold": 181_917.0, "rate": 0.46},
                      {"threshold": 250_000.0, "rate": 0.5}],
        "tva_taux_normal": 0.21, "cotisations_salariales_retraite_echelle": 0.9}
    assert imputations == ["consommation"]
    # La valeur neutre de chaque réglage laisse la loi : elle n'entre pas dans la réforme.
    assert parametrique.reforme({"smic": 5, "tva_normal": 20, "rsa": 0}) == (
        {"smic_revalorisation": 1.05, "smic_diffusion_profil": "annee_avec_effets_fixes",
         "smic_diffusion_echelle": 0.0}, [])


def test_the_ir_points_read_the_2026_scale_of_the_tree() -> None:
    reform, _ = parametrique.reforme({"ir_points": -1})
    loi = parametrique._ir_2026()
    assert [t["threshold"] for t in reform["ir_bareme"]] == [t["threshold"] for t in loi]
    assert [t["rate"] for t in reform["ir_bareme"]] == [
        round(t["rate"] - 0.01, 6) if t["rate"] > 0 else 0.0 for t in loi]


@pytest.mark.parametrize("reglage, raison", [
    ({}, "ne change rien"), ({"smic": 0}, "ne change rien"),
    ({"age_retraite": 60}, "inconnus"), ({"smic": 40}, "hors de"),
    ({"ir_tranche_seuil": 250_000}, "seuil et son taux"),
    ({"ir_tranche_seuil": 100_000, "ir_tranche_taux": 50}, "sous la dernière"),
    ({"rsa": "beaucoup"}, "pas un nombre")])
def test_a_setting_the_engine_cannot_carry_is_refused(reglage, raison) -> None:
    with pytest.raises(parametrique.PropositionError, match=raison):
        parametrique.reforme(reglage, bareme=lambda: [dict(t) for t in BAREME])


def _copier(ici: Path, nom: str, genre: str) -> None:
    shutil.copy(ETUDE / f"{genre}_{SCENARIO}.json", ici / f"{genre}_{nom}.json")


def _tableau(ici: Path, nom: str) -> None:
    """Le tableau des cas types que la passe écrirait : celui de la mesure d'étude."""
    from impots.jumeau.impacts import pour_vous

    tab = dict(pour_vous.charger())
    tab["mesures"] = {nom: tab["mesures"][SCENARIO]}
    (ici / "cas_types.json").write_text(json.dumps(tab), encoding="utf-8")


def test_a_proposition_gives_the_studys_numbers_every_dimension_illustrative(ici) -> None:
    from impots import site_jumeau
    from impots.jumeau import navigateur

    lances: list[Path] = []
    e = parametrique.proposer({"smic": 8.18}, lancer=lances.append)
    assert e["etat"] == "en_file" and e["statut"] == "illustratif"
    assert lances == [ici / e["id"]]
    # La même proposition, demandée deux fois, n'est mise en file qu'une fois.
    assert parametrique.proposer({"smic": 8.18}, lancer=lances.append)["id"] == e["id"]
    assert len(lances) == 1
    donnees = json.loads(json.dumps(site_jumeau.donnees()))
    fait = parametrique.passer(
        lances[0], premiere_annee=lambda d, n: _copier(d, n, "premiere_annee"),
        chemin_annuel=lambda d, n: _copier(d, n, "predictif"),
        cas_types=_tableau, session=navigateur.Session(donnees), tirages=4)
    assert fait["etat"] == "fait" and fait["erreur"] is None
    assert set(fait["temps"]) == {"attente_verrou_s", "premiere_annee_s",
                                  "chemin_annuel_s", "cas_types_s", "jumeau_s"}
    r = parametrique.etat(e["id"])["resultat"]
    assert r["proposition"]["statut"] == "illustratif"
    assert r["reglage"]["mode"] == "structurel" and r["pourquoi_mode"] is None
    dims = [d for d in r["dimensions"] if "erreur" not in d]
    assert len(dims) == len(r["dimensions"]) >= 5
    for d in dims:
        assert d["statut"] == "illustratif" and d["juge"] is None, d["cle"]
        assert any(parametrique.RAISON in x for x in d["limites"]), d["cle"]
    # Le jumeau lit la passe comme il lit la mesure d'étude : les mêmes nombres, au bit.
    etude = json.loads(navigateur.impacts_json(
        navigateur.Session(json.loads(json.dumps(donnees))),
        json.dumps({"candidat": SCENARIO, "tirages": 4})))
    for a, b in zip(r["ensemble"], etude["ensemble"], strict=True):
        assert a["cle"] == b["cle"] and a["tete"] == b["tete"], a["cle"]


def test_a_failed_pass_says_why(ici) -> None:
    e = parametrique.proposer({"rsa": 5}, lancer=lambda d: None)

    def casse(d: Path, n: str) -> None:
        raise RuntimeError("la passe a manqué de mémoire")

    with pytest.raises(RuntimeError):
        parametrique.passer(ici / e["id"], premiere_annee=casse)
    echec = parametrique.etat(e["id"])
    assert echec["etat"] == "echec" and "manqué de mémoire" in echec["erreur"]
    # Une proposition en échec se relance.
    lances: list[Path] = []
    assert parametrique.proposer({"rsa": 5}, lancer=lances.append)["etat"] == "en_file"
    assert lances


def test_the_api_queues_a_proposition_and_says_its_state(ici, monkeypatch) -> None:
    from fastapi.testclient import TestClient

    from impots.api.main import app

    lances: list[Path] = []
    monkeypatch.setattr(parametrique, "_detacher", lances.append)
    monkeypatch.setattr(parametrique, "FILE_MAX", 2)
    client = TestClient(app)
    menu = client.get("/impacts/proposition/boutons").json()
    assert menu["statut"] == "illustratif" and {b["id"] for b in menu["boutons"]} >= {
        "smic", "rsa", "prime_activite", "ir_points", "tva_normal"}
    r = client.post("/impacts/proposition", json={"boutons": {"smic": 5}})
    assert r.status_code == 202, r.text
    ident = r.json()["id"]
    assert client.get(f"/impacts/proposition/{ident}").json()["etat"] == "en_file"
    assert client.post("/impacts/proposition", json={"boutons": {"smic": 50}}
                       ).status_code == 422
    assert client.get("/impacts/proposition/votre_bareme_000000000000").status_code == 404
    assert client.get("/impacts/proposition/..%2Fetat").status_code in (404, 422)
    assert client.post("/impacts/proposition", json={"rsa": 5}).status_code == 202
    plein = client.post("/impacts/proposition", json={"rsa": 6})
    assert plein.status_code == 503 and "file" in plein.json()["detail"]
    assert [p.name for p in lances] == [ident, lances[1].name] and len(lances) == 2
    monkeypatch.setenv(parametrique.ENV_PASSES, "non")
    ferme = client.post("/impacts/proposition", json={"rsa": 7})
    assert ferme.status_code == 503 and "ne lance pas" in ferme.json()["detail"]
    # Une proposition déjà là reste servie.
    assert client.post("/impacts/proposition", json={"boutons": {"smic": 5}}
                       ).json()["id"] == ident
    assert len(lances) == 2
