"""Les programmes de la présidentielle 2027 (but 11, D-319) : le schéma et ses refus."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from impots import programmes as pg

SOURCE = {"citation": "Nous créerons une tranche à 60 %.", "url": "https://exemple.fr/p",
          "date": "2026-10-01", "type": "programme"}


def _mesure(**over):
    base = {
        "id": "tranche_60", "categorie": "ir", "libelle": "Une tranche à 60 %",
        "parametre": "60 % au-delà de 250 000 €", "precision": "parametree",
        "sources": [SOURCE],
        "chiffrage": {"couche": "menages", "reforme": {"csg_activite_imposable": 0.024},
                      "plages": [{"champ": "csg_activite_imposable", "min": 0.0,
                                  "max": 0.05}]},
    }
    base.update(over)
    return base


def _programme(*mesures, **over):
    base = {"candidat": "Candidat Essai", "slug": "essai", "parti": "Parti", "statut":
            "declare", "statut_source": SOURCE, "releve": "2026-11-01", "annee": 2026,
            "mesures": list(mesures) or [_mesure()]}
    base.update(over)
    return base


def _vague(**over):
    base = _mesure(id="vague", precision="vague", parametre="aucun", chiffrage=None,
                   refus={"porte": "vague", "raison": "aucun taux énoncé"})
    base.update(over)
    return base


def test_a_programme_loads_and_counts_its_coverage(tmp_path) -> None:
    p = _programme(_mesure(), _vague(),
                   _mesure(id="retraite", categorie="retraites", chiffrage=None,
                           refus={"porte": "retraites", "raison": "l'âge n'avance pas"}))
    (tmp_path / "essai.json").write_text(json.dumps(p), encoding="utf-8")
    prog = pg.charger("essai", tmp_path)
    c = prog.couverture()
    assert (c["mesures"], c["parametrees"], c["vagues"], c["chiffrees"]) == (3, 2, 1, 1)
    assert c["part_des_parametrees"] == 0.5
    assert c["refus_par_porte"] == {"retraites": 1, "vague": 1}
    assert pg.lister(tmp_path) == ("essai",)


def test_a_vague_measure_is_never_priced() -> None:
    with pytest.raises(ValidationError, match="vague"):
        pg.Mesure.model_validate(_mesure(precision="vague"))


def test_a_measure_refused_as_vague_must_be_vague() -> None:
    with pytest.raises(ValidationError, match="dite paramétrée"):
        pg.Mesure.model_validate(_vague(precision="parametree"))


def test_a_measure_is_priced_or_refused_never_both_never_neither() -> None:
    with pytest.raises(ValidationError, match="l'un des deux"):
        pg.Mesure.model_validate(_mesure(refus={"porte": "retraites", "raison": "r"}))
    with pytest.raises(ValidationError, match="l'un des deux"):
        pg.Mesure.model_validate(_mesure(chiffrage=None))


def test_an_unknown_door_is_refused() -> None:
    with pytest.raises(ValidationError, match="porte « nulle_part » inconnue"):
        pg.Mesure.model_validate(_mesure(chiffrage=None,
                                         refus={"porte": "nulle_part", "raison": "r"}))


def test_a_knob_the_engine_does_not_have_is_refused() -> None:
    # `tva_taux_normal` était l'exemple jusqu'au but 12, qui en a fait un bouton (D-324).
    with pytest.raises(ValidationError, match="pas un menages valide"):
        pg.Mesure.model_validate(_mesure(chiffrage={"couche": "menages",
                                                    "reforme": {"droits_douane_taux": 0.1}}))


def test_a_firm_reform_is_validated_as_one() -> None:
    m = pg.Mesure.model_validate(_mesure(id="cvae", categorie="entreprises", chiffrage={
        "couche": "entreprises", "reforme": {"cvae_echelle": 0.0}}))
    assert m.chiffrage.couche == "entreprises"
    with pytest.raises(ValidationError, match="pas un entreprises valide"):
        pg.Mesure.model_validate(_mesure(chiffrage={"couche": "entreprises",
                                                    "reforme": {"cvae_echelle": -1.0}}))


def test_a_range_must_hold_the_stated_value_and_name_a_number() -> None:
    with pytest.raises(ValidationError, match="hors de sa plage"):
        pg.Mesure.model_validate(_mesure(chiffrage={
            "couche": "menages", "reforme": {"csg_activite_imposable": 0.024},
            "plages": [{"champ": "csg_activite_imposable", "min": 0.03, "max": 0.05}]}))
    with pytest.raises(ValidationError, match="pas de clé"):
        pg.Mesure.model_validate(_mesure(chiffrage={
            "couche": "menages", "reforme": {"csg_activite_imposable": 0.024},
            "plages": [{"champ": "pfu_taux", "min": 0.0, "max": 0.5}]}))
    with pytest.raises(ValidationError, match="n'est pas sous"):
        pg.Plage.model_validate({"champ": "x", "min": 1.0, "max": 1.0})


def test_a_range_reaches_into_a_scale() -> None:
    bareme = [{"threshold": 0, "rate": 0.0}, {"threshold": 11_497, "rate": 0.11},
              {"threshold": 29_315, "rate": 0.30}, {"threshold": 83_823, "rate": 0.41},
              {"threshold": 180_294, "rate": 0.45}]
    m = pg.Mesure.model_validate(_mesure(chiffrage={
        "couche": "menages", "reforme": {"ir_bareme": bareme},
        "plages": [{"champ": "ir_bareme.4.rate", "min": 0.45, "max": 0.60}]}))
    prog = pg.Programme.model_validate(_programme(m.model_dump(mode="json")))
    menages, _ = prog.reformes({"tranche_60:ir_bareme.4.rate": 0.5})
    assert menages.ir_bareme[4].rate == 0.5
    with pytest.raises(pg.ProgrammeError, match="pas d'élément 9"):
        pg._lire(bareme, "9.rate")


def test_two_measures_setting_one_knob_are_refused() -> None:
    p = pg.Programme.model_validate(_programme(_mesure(), _mesure(id="autre")))
    with pytest.raises(pg.ProgrammeError, match="règlent tous deux"):
        p.reformes()


def test_values_override_the_candidates_within_their_range_only() -> None:
    p = pg.Programme.model_validate(_programme(_mesure()))
    menages, entreprises = p.reformes({"tranche_60:csg_activite_imposable": 0.04})
    assert menages.csg_activite_imposable == 0.04 and entreprises is None
    assert p.reformes()[0].csg_activite_imposable == 0.024
    with pytest.raises(pg.ProgrammeError, match="hors de"):
        p.reformes({"tranche_60:csg_activite_imposable": 0.09})
    with pytest.raises(pg.ProgrammeError, match="paramètres inconnus"):
        p.reformes({"tranche_60:pfu_taux": 0.1})


def test_a_subset_of_measures_prices_alone() -> None:
    p = pg.Programme.model_validate(_programme(
        _mesure(), _mesure(id="pfu", chiffrage={"couche": "menages",
                                                "reforme": {"pfu_taux": 0.10}})))
    menages, _ = p.reformes(mesures=("pfu",))
    assert menages.pfu_taux == 0.10 and menages.csg_activite_imposable is None
    with pytest.raises(pg.ProgrammeError, match="ne sont pas des mesures chiffrées"):
        p.reformes(mesures=("absente",))


def test_the_declared_layer_needs_rho_and_keeps_its_signs() -> None:
    declare = {"montant_eur": 10e9, "sens": "economie_depense", "horizon": "2032",
               "source": SOURCE}
    baisse = {"montant_eur": 4e9, "sens": "baisse_prelevements", "horizon": "2032",
              "source": SOURCE}
    p = pg.Programme.model_validate(_programme(
        _mesure(declare=baisse),
        _mesure(id="effectifs", categorie="depense_publique", chiffrage=None,
                refus={"porte": "depense_publique", "raison": "non microsimulée"},
                declare=declare)))
    couche = p.couche_declaree(0.5)
    assert couche["solde_eur"] == pytest.approx(0.5 * 10e9 - 0.5 * 4e9)
    assert "non vérifié" in couche["statut"]
    with pytest.raises(pg.ProgrammeError, match="dans \\[0, 1\\]"):
        p.couche_declaree(1.2)
    with pytest.raises(TypeError):
        p.couche_declaree()  # type: ignore[call-arg]  # aucune valeur par défaut


def test_only_declared_candidates_have_a_programme() -> None:
    with pytest.raises(ValidationError, match="statut"):
        pg.Programme.model_validate(_programme(statut="pressenti"))


def test_a_file_must_carry_its_own_slug(tmp_path) -> None:
    (tmp_path / "autre.json").write_text(json.dumps(_programme()), encoding="utf-8")
    with pytest.raises(pg.ProgrammeError, match="porte le slug"):
        pg.charger("autre", tmp_path)


def test_a_source_is_read_at_an_url() -> None:
    with pytest.raises(ValidationError, match="se lit à une URL"):
        pg.Source.model_validate({**SOURCE, "url": "Le Monde, 3 octobre"})


def test_two_measures_cannot_share_an_id() -> None:
    with pytest.raises(ValidationError, match="en double"):
        pg.Programme.model_validate(_programme(_mesure(), _mesure()))


def test_every_committed_programme_follows_the_one_schema() -> None:
    """Même schéma pour chaque candidat (D-319) : chaque fichier commité se charge."""
    for slug in pg.lister():
        prog = pg.charger(slug)
        assert prog.statut == "declare"
        prog.reformes()


def test_a_range_must_name_a_number_not_a_list() -> None:
    bareme = [{"threshold": 0, "rate": 0.0}, {"threshold": 11_497, "rate": 0.11}]
    with pytest.raises(ValidationError, match="n'est pas un nombre"):
        pg.Mesure.model_validate(_mesure(chiffrage={
            "couche": "menages", "reforme": {"ir_bareme": bareme},
            "plages": [{"champ": "ir_bareme", "min": 0.0, "max": 1.0}]}))
