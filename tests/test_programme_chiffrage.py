"""`impots programme` (but 11, D-319) : la part chiffrée, ses refus, et les trois réponses."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from impots import programme_chiffrage as pc
from impots import programmes as pg

SOURCE = {"citation": "c", "url": "https://exemple.fr", "date": "2026-10-01",
          "type": "programme"}


def _prog(**over):
    base = {
        "candidat": "Essai", "slug": "essai", "parti": "P", "statut": "declare",
        "statut_source": SOURCE, "releve": "2026-11-01", "annee": 2026,
        "mesures": [
            {"id": "csg", "categorie": "csg_cotisations", "libelle": "CSG", "parametre": "x",
             "precision": "parametree", "sources": [SOURCE],
             "chiffrage": {"couche": "menages", "reforme": {"csg_activite_imposable": 0.02},
                           "plages": [{"champ": "csg_activite_imposable", "min": 0.0,
                                       "max": 0.024}]},
             "declare": {"montant_eur": 2e9, "sens": "baisse_prelevements",
                         "horizon": "2028", "source": SOURCE}},
            {"id": "cvae", "categorie": "entreprises", "libelle": "CVAE", "parametre": "0",
             "precision": "parametree", "sources": [SOURCE],
             "chiffrage": {"couche": "entreprises", "reforme": {"is_taux_normal": 0.24}}},
            {"id": "retraite", "categorie": "retraites", "libelle": "âge", "parametre": "60",
             "precision": "parametree", "sources": [SOURCE],
             "refus": {"porte": "retraites", "raison": "l'âge n'avance pas"},
             "declare": {"montant_eur": 10e9, "sens": "depense", "horizon": "2030",
                         "source": SOURCE}},
        ]}
    base.update(over)
    return pg.Programme.model_validate(base)


HYP = {"spending": {"kind": "gele_en_volume"}, "horizon": 10}


def test_without_hypotheses_nothing_is_simulated() -> None:
    r = pc.rapport(_prog())
    assert "chiffrage" not in r and "couche_declaree" not in r
    assert r["couverture"]["chiffrees"] == 2
    assert [m["sort"] for m in r["mesures"]] == ["chiffrée", "chiffrée", "refusée"]
    assert r["mesures"][2]["ouvrirait"] == pg.PORTES["retraites"]
    assert r["reforme_menages"] == {"csg_activite_imposable": 0.02}
    assert r["reforme_entreprises"] == {"is_taux_normal": 0.24}


def test_the_simulated_request_carries_the_programme_and_only_the_given_hypotheses() -> None:
    seen = {}

    def simuler(request):
        seen["request"] = request
        return SimpleNamespace(model_dump=lambda mode: {"mechanical_first_year_eur": 1e9,
                                                         "years": [2026, 2035],
                                                         "delta": [0.0, 0.4]})

    from pydantic import ValidationError

    hyp = {"spending": {"rule": "gele_en_volume"},
           "growth": {"name": "g", "real": 0.01, "prices": 0.02},
           "rate": {"name": "tenu", "kind": "implicite_tenu"}, "horizon": 10,
           "theta": {"common": 0.5},
           "uprating": {"wage": 0.03, "source": "hypothèse d'essai"}}
    with pytest.raises(ValidationError, match="theta"):  # aucune hypothèse n'a de défaut
        pc.rapport(_prog(), hypotheses={k: v for k, v in hyp.items() if k != "theta"},
                   simuler=simuler)
    r = pc.rapport(_prog(), hypotheses=hyp, simuler=simuler, rho=0.5)
    req = seen["request"]
    assert req.reform.csg_activite_imposable == 0.02
    assert req.firm_reform.is_taux_normal == 0.24
    assert r["chiffrage"]["delta"][-1] == 0.4
    assert "pas sur le programme" in r["avertissement"]
    assert r["couche_declaree"]["solde_eur"] == pytest.approx(0.5 * (-2e9 - 10e9))
    assert all("couche" not in k for k in r["chiffrage"])


def test_values_and_a_subset_reach_the_reform() -> None:
    r = pc.rapport(_prog(), valeurs={"csg:csg_activite_imposable": 0.01}, mesures=("csg",))
    assert r["reforme_menages"] == {"csg_activite_imposable": 0.01}
    assert r["reforme_entreprises"] is None and r["mesures_chiffrees_retenues"] == ["csg"]


def test_a_programme_with_nothing_priced_has_nothing_to_simulate() -> None:
    p = _prog(mesures=[_prog().mesures[2].model_dump(mode="json")])
    with pytest.raises(pc.ChiffrageError, match="rien à simuler"):
        pc.rapport(p, hypotheses=HYP, simuler=lambda req: None)


def test_the_hypotheses_file_cannot_carry_the_reform(tmp_path) -> None:
    f = tmp_path / "h.json"
    f.write_text(json.dumps({"horizon": 10, "reform": {"pfu_taux": 0.3}}), encoding="utf-8")
    with pytest.raises(pc.ChiffrageError, match="viennent du programme"):
        pc.lire_hypotheses(f)
    f.write_text(json.dumps({"horizon": 10, "theta_par_defaut": 0.5}), encoding="utf-8")
    with pytest.raises(pc.ChiffrageError, match="clés inconnues"):
        pc.lire_hypotheses(f)


def test_values_are_read_as_measure_field_number() -> None:
    assert pc.lire_valeurs(["csg:csg_activite_imposable=0.01"]) == {
        "csg:csg_activite_imposable": 0.01}
    with pytest.raises(pc.ChiffrageError, match="attendu"):
        pc.lire_valeurs(["sans_egal"])
    with pytest.raises(pc.ChiffrageError, match="pas un nombre"):
        pc.lire_valeurs(["csg:csg_activite_imposable=beaucoup"])


def test_the_command_lists_reports_and_refuses(tmp_path, monkeypatch, capsys) -> None:
    from impots.population import cli

    (tmp_path / "essai.json").write_text(_prog().model_dump_json(), encoding="utf-8")
    monkeypatch.setattr(pg, "PROGRAMMES", tmp_path)
    assert cli.main(["programme"]) == 0
    assert capsys.readouterr().out.split() == ["essai"]
    out = tmp_path / "r.json"
    assert cli.main(["programme", "essai", "--rho", "0.25", "--sortie", str(out)]) == 0
    printed = capsys.readouterr().out
    assert "2 chiffrées" in printed and "couche déclarée" in printed
    assert json.loads(out.read_text(encoding="utf-8"))["couche_declaree"]["rho"] == 0.25
    assert cli.main(["programme", "essai", "--rho", "2"]) == 1
    assert "dans [0, 1]" in capsys.readouterr().err
    assert cli.main(["programme", "absent"]) == 1


def _script():
    import importlib.util
    from pathlib import Path

    path = Path(__file__).resolve().parents[1] / "scripts" / "preenregistrer_programmes.py"
    spec = importlib.util.spec_from_file_location("preenregistrer_programmes", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_every_priced_measure_has_its_case_files_as_committed() -> None:
    """Le scénario ou la réforme d'un cas est la mesure du programme, sans rien d'autre ;
    chaque mesure chiffrée a sa classe de tolérance (D-321)."""
    from impots import scenarios
    from impots.entreprises.reforms import FirmReformSpec

    s = _script()
    for nom, p, m in s.cas():
        assert m.id in s.CLASSE
        if m.chiffrage.couche == "menages":
            scen = scenarios.load(nom)
            assert scen.year == p.annee
            assert scen.reform == pg._spec("menages", m.chiffrage.reforme)
        else:
            path = s.ROOT / "reforms" / f"{nom}.json"
            assert FirmReformSpec.model_validate_json(path.read_text(encoding="utf-8")) == \
                pg._spec("entreprises", m.chiffrage.reforme)


def test_a_priced_measure_without_a_tolerance_class_is_refused(monkeypatch) -> None:
    s = _script()
    classe = dict(s.CLASSE)
    classe.pop("tranche_ir_60")
    monkeypatch.setattr(s, "CLASSE", classe)
    with pytest.raises(SystemExit, match="aucune classe de tolérance"):
        s.cas()


def test_a_tolerance_class_for_a_measure_no_longer_priced_is_refused(monkeypatch) -> None:
    s = _script()
    monkeypatch.setattr(s, "CLASSE", {**s.CLASSE, "mesure_disparue": "menages"})
    with pytest.raises(SystemExit, match="ne sont plus chiffrées"):
        s.cas()


def test_the_committed_table_is_the_rendered_one() -> None:
    """La page du but 11 ne dérive pas de ses programmes ni de son registre."""
    s = _script()
    assert s.TABLEAU.read_text(encoding="utf-8") == s.tableau()


def test_the_printed_debt_is_in_points_of_gdp() -> None:
    """La trajectoire est une fraction du PIB : 0,0954 s'imprime +9,54 pt, pas +0,10."""
    r = pc.rapport(_prog())
    r["chiffrage"] = {"mechanical_first_year_eur": 30.9e9, "years": [2026, 2035],
                      "delta": [0.01, 0.0954]}
    ligne = next(x for x in pc.resume(r) if "dette en 2035" in x)
    assert "+9.54 pt de PIB" in ligne, ligne
