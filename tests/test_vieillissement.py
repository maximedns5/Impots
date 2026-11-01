"""But 10 : un cas se chiffre sur la population vieillie jusqu'à son année (D-317)."""

from __future__ import annotations

import json
from types import SimpleNamespace

import polars as pl
import pytest

from impots import hypotheses as hyp
from impots import preregistration as ch
from impots import uprating as up


@pytest.fixture(autouse=True)
def _fresh():
    hyp.plf2027.cache_clear()
    yield
    hyp.plf2027.cache_clear()


# ----------------------------------------------------------------------------------------
# Les hypothèses, lues dans les deux textes.


def test_the_plf_2027_hypotheses_are_read() -> None:
    h = hyp.plf2027()
    assert h.salaires == pytest.approx({2025: 0.020, 2026: 0.020, 2027: 0.027})
    assert {y: h.prix[y] for y in (2025, 2026, 2027)} == pytest.approx(
        {2025: 0.009, 2026: 0.021, 2027: 0.017})
    assert {y: h.pib_valeur[y] for y in (2025, 2026, 2027)} == pytest.approx(
        {2025: 0.020, 2026: 0.020, 2027: 0.027})


def _edited(tmp_path, source, old, new):
    """Le texte du document, débarrassé de ses balises comme le lecteur le lit, retouché."""
    text = hyp._text(source)
    assert old in text, "la retouche du test ne trouve pas son texte"
    out = tmp_path / source.name
    out.write_text(text.replace(old, new), encoding="utf-8")
    return out


def test_a_missing_wage_sentence_is_refused(tmp_path) -> None:
    plf = _edited(tmp_path, hyp.PLF_2027, "Les salaires progresseraient de",
                  "Les salaires évolueraient de")
    with pytest.raises(hyp.HypothesesError, match="salaires"):
        hyp.plf2027(plf=plf)


def test_wages_that_speed_up_another_year_are_refused(tmp_path) -> None:
    plf = _edited(tmp_path, hyp.PLF_2027, "en moyenne annuelle 2027. Les prix",
                  "en moyenne annuelle 2028. Les prix")
    with pytest.raises(hyp.HypothesesError, match="2028"):
        hyp.plf2027(plf=plf)


def test_a_missing_table_is_refused(tmp_path) -> None:
    plfss = _edited(tmp_path, hyp.PLFSS_2027, "Inflation hors tabac 0,9 %",
                    "Inflation totale 0,9 %")
    with pytest.raises(hyp.HypothesesError, match="tableau"):
        hyp.plf2027(plfss=plfss)


def test_rates_out_of_range_are_refused(tmp_path) -> None:
    plfss = _edited(tmp_path, hyp.PLFSS_2027, "Inflation hors tabac 0,9 %",
                    "Inflation hors tabac 12,9 %")
    with pytest.raises(hyp.HypothesesError, match="hors"):
        hyp.plf2027(plfss=plfss)


def test_an_unknown_set_is_refused() -> None:
    with pytest.raises(hyp.HypothesesError, match="inconnues"):
        hyp.jeu("plf2099")


# ----------------------------------------------------------------------------------------
# Les indices année par année.


def test_yearly_indices_chain() -> None:
    u = up.Uprating.par_annee({2025: 0.02, 2026: 0.03}, {2025: 0.01, 2026: 0.02}, "essai",
                              2024)
    assert u.factor("wage", 2026) == pytest.approx(1.02 * 1.03)
    assert u.factor("price", 2025) == pytest.approx(1.01)
    assert u.factor("wage", 2024) == 1.0
    constant = up.Uprating(wage=u.wage, price=u.price, source="essai", base_year=2024)
    assert u.key() != constant.key()
    assert "2,0\u202f% en 2025" in up.caveat(2026, u)


def test_a_missing_year_is_refused() -> None:
    u = up.Uprating.par_annee({2025: 0.02}, {2025: 0.01}, "essai", 2024)
    with pytest.raises(up.UpratingError, match="2026"):
        u.factor("wage", 2026)


def test_yearly_wages_with_constant_prices_are_refused() -> None:
    with pytest.raises(up.UpratingError, match="même façon"):
        up.Uprating(wage=0.02, price=0.01, source="essai", base_year=2024,
                    wage_by_year=((2025, 0.02),))


def test_a_yearly_rate_out_of_range_is_refused() -> None:
    with pytest.raises(up.UpratingError, match="hors"):
        up.Uprating.par_annee({2025: 0.9}, {2025: 0.01}, "essai", 2024)


def test_households_are_aged_on_the_set() -> None:
    uprating, record = hyp.vieillissement_menages("plf2027", 2024, 2026)
    assert record["facteur_salaires"] == pytest.approx(1.02 * 1.02)
    assert record["facteur_prix"] == pytest.approx(1.009 * 1.021)
    assert record["salaires"] == pytest.approx({"2025": 0.02, "2026": 0.02})
    frame = pl.DataFrame({"salaire_brut_annuel": [100.0], "pension_annuelle": [100.0],
                          "chomage_annuel": [100.0], "loyer_mensuel": [100.0]})
    aged = up.uprate(frame, 2026, uprating)
    assert aged["salaire_brut_annuel"][0] == pytest.approx(104.04)
    assert aged["pension_annuelle"][0] == pytest.approx(100 * 1.009 * 1.021)


def test_the_same_year_ages_nothing() -> None:
    uprating, record = hyp.vieillissement_menages("plf2027", 2024, 2024)
    assert uprating is None and record["facteur_salaires"] == 1.0


def test_households_beyond_the_set_are_refused() -> None:
    with pytest.raises(hyp.HypothesesError, match="2028"):
        hyp.vieillissement_menages("plf2027", 2024, 2028)
    with pytest.raises(hyp.HypothesesError, match="rajeunir"):
        hyp.vieillissement_menages("plf2027", 2024, 2023)


def test_firms_follow_the_accounts_then_the_set() -> None:
    accounts = {2023: 100.0, 2025: 110.0}
    factor, record = hyp.vieillissement_entreprises(
        "plf2027", 2023, 2027, gdp_of=lambda years: {y: accounts[y] for y in years})
    assert factor == pytest.approx(1.10 * 1.020 * 1.027)
    assert record["facteur"] == factor
    assert record["pib_valeur"] == pytest.approx({"2026": 0.020, "2027": 0.027})
    same, _ = hyp.vieillissement_entreprises(
        "plf2027", 2023, 2023, gdp_of=lambda years: {y: accounts[y] for y in years})
    assert same == 1.0


def test_firms_beyond_the_set_are_refused() -> None:
    with pytest.raises(hyp.HypothesesError, match="2031"):
        hyp.vieillissement_entreprises("plf2027", 2023, 2031,
                                       gdp_of=lambda years: {y: 1.0 for y in years})


# ----------------------------------------------------------------------------------------
# L'enregistrement des ménages.


def _household_cli(tmp_path, monkeypatch, year: int, *extra: str):
    from impots import scenarios
    from impots.population import cli

    population = tmp_path / "population_2024.parquet"
    pl.DataFrame({"salaire_brut_annuel": [100.0], "pension_annuelle": [100.0],
                  "chomage_annuel": [100.0], "loyer_mensuel": [100.0]}
                 ).write_parquet(population)
    seen = {}

    def price(scenario, frame, households):
        seen["frame"] = frame
        return {"mechanical": 2.0e8}

    monkeypatch.setattr(cli, "PROCESSED", tmp_path)
    monkeypatch.setattr(scenarios, "load", lambda name: SimpleNamespace(year=year))
    monkeypatch.setattr(scenarios, "mechanical_price", price)
    monkeypatch.setattr(ch, "head_commit", lambda: "abc1234")
    args = cli.build_parser().parse_args([
        "chiffrage", "register", "vieux", "--scenario", "s",
        "--tolerance-relative", "0.3", "--tolerance-absolute", "1e7",
        "--tolerance-rationale", "essai", "--dir", str(tmp_path / "cas"), *extra])
    return args.func(args), seen


def test_a_case_of_another_year_without_indices_is_refused(tmp_path, monkeypatch,
                                                           capsys) -> None:
    code, seen = _household_cli(tmp_path, monkeypatch, 2026)
    assert code == 1 and "frame" not in seen
    assert "--vieillir" in capsys.readouterr().err
    assert not (tmp_path / "cas").exists() or not list((tmp_path / "cas").iterdir())


def test_a_case_is_priced_on_the_aged_population(tmp_path, monkeypatch) -> None:
    code, seen = _household_cli(tmp_path, monkeypatch, 2026, "--vieillir", "plf2027")
    assert code == 0
    assert seen["frame"]["salaire_brut_annuel"][0] == pytest.approx(104.04)
    case = ch.load("vieux", tmp_path / "cas")
    assert case.vieillissement["jeu"] == "plf2027"
    assert (case.vieillissement["de"], case.vieillissement["vers"]) == (2024, 2026)
    assert case.vieillissement["facteur_salaires"] == pytest.approx(1.0404)


def test_a_case_of_its_population_year_needs_no_indices(tmp_path, monkeypatch) -> None:
    code, seen = _household_cli(tmp_path, monkeypatch, 2024)
    assert code == 0
    assert seen["frame"]["salaire_brut_annuel"][0] == 100.0
    assert ch.load("vieux", tmp_path / "cas").vieillissement is None


def test_an_unknown_set_is_refused_by_the_command(tmp_path, monkeypatch, capsys) -> None:
    code, _ = _household_cli(tmp_path, monkeypatch, 2026, "--vieillir", "plf2099")
    assert code == 1 and "inconnues" in capsys.readouterr().err


def test_the_ageing_reads_back_and_old_cases_stay_as_they_were(tmp_path) -> None:
    tolerance = ch.Tolerance(relative=0.3, absolute_eur=1e7, rationale="essai")
    ch.register("ancien", mechanical_eur=1e8, tolerance=tolerance, population_vintage="2024",
                sample=10, scenario="s", directory=tmp_path, now="2026-11-01T00:00:00+00:00")
    assert "vieillissement" not in (tmp_path / "ancien.yaml").read_text(encoding="utf-8")
    ch.register("neuf", mechanical_eur=1e8, tolerance=tolerance, population_vintage="2024",
                sample=10, scenario="s", vieillissement={"jeu": "plf2027", "vers": 2026},
                directory=tmp_path, now="2026-11-01T00:00:00+00:00")
    assert ch.load("neuf", tmp_path).vieillissement == {"jeu": "plf2027", "vers": 2026}


# ----------------------------------------------------------------------------------------
# L'enregistrement des entreprises.

PROROGATION_2027 = {
    "cebge_seuils_et_taux": [{"seuil_ca": 1.5e9, "taux": 0.157},
                             {"seuil_ca": 3e9, "taux": 0.314}],
    "cebge_prorogation_largeur": 1e8,
}


@pytest.fixture(scope="module")
def fixture_firms():
    from impots.entreprises.build import FIXTURE_CELLS, load_cells
    from impots.entreprises.population import build_firms

    cells, ratio, _ = load_cells(FIXTURE_CELLS)
    firms, _ = build_firms(cells, fiscal_to_accounting=ratio)
    return firms


def _firm_cli(tmp_path, monkeypatch, fixture_firms, *extra: str) -> int:
    import impots.entreprises.build as firm_build
    from impots.dette import comptes
    from impots.population import cli

    monkeypatch.setattr(firm_build, "PROCESSED", tmp_path)
    monkeypatch.setattr(ch, "head_commit", lambda: "abc1234")
    monkeypatch.setattr(comptes, "gdp", lambda years: {y: {2023: 100.0, 2025: 110.0}[y]
                                                       for y in years})
    fixture_firms.write_parquet(tmp_path / "firms_2023.parquet")
    (tmp_path / "firms_2023.manifest.json").write_text(
        json.dumps({"cells_are_synthetic": False}), encoding="utf-8")
    reform = tmp_path / "reforme.json"
    reform.write_text(json.dumps(PROROGATION_2027), encoding="utf-8")
    return cli.main([
        "chiffrage", "register-entreprises", "cebge", "--reform", str(reform),
        "--year", "2027", "--vintage", "2023", "--tolerance-relative", "0.30",
        "--tolerance-absolute", "200e6", "--tolerance-rationale", "essai",
        "--dir", str(tmp_path / "cas"), *extra])


def test_a_firm_case_of_another_year_without_indices_is_refused(
        tmp_path, monkeypatch, capsys, fixture_firms) -> None:
    assert _firm_cli(tmp_path, monkeypatch, fixture_firms) == 1
    assert "--vieillir" in capsys.readouterr().err


def test_a_firm_case_is_aged_on_the_gdp(tmp_path, monkeypatch, fixture_firms) -> None:
    from impots.entreprises import aggregate, runner

    assert _firm_cli(tmp_path, monkeypatch, fixture_firms, "--vieillir", "plf2027",
                     "--apres-annexe", "révision vieillie") == 0
    case = ch.load("cebge", tmp_path / "cas")
    frozen = aggregate.aggregate(runner.run(
        fixture_firms, year=2027,
        reform=__import__("impots.entreprises.reforms", fromlist=["FirmReformSpec"])
        .FirmReformSpec.model_validate(PROROGATION_2027)).firms).reform_cost
    factor = 1.10 * 1.020 * 1.027
    assert case.mechanical_eur == pytest.approx(frozen * factor)
    assert case.vieillissement["facteur"] == pytest.approx(factor)
    assert case.revision["apres_annexe"] is True


def test_a_firm_factor_without_its_declaration_is_refused(tmp_path, fixture_firms) -> None:
    from impots.entreprises.reforms import FirmReformSpec

    tolerance = ch.Tolerance(relative=0.3, absolute_eur=2e8, rationale="essai")
    with pytest.raises(ch.ChiffrageError, match="facteur"):
        ch.register_firm("x", spec=FirmReformSpec.model_validate(PROROGATION_2027),
                         year=2027, frame=fixture_firms, tolerance=tolerance,
                         population_vintage="entreprises-2023", facteur=1.1,
                         directory=tmp_path)
    assert not list(tmp_path.iterdir())


def test_yearly_indices_without_years_are_refused() -> None:
    with pytest.raises(up.UpratingError, match="sans année"):
        up.Uprating.par_annee({}, {}, "essai", 2024)


def test_firms_aged_backwards_are_refused() -> None:
    with pytest.raises(hyp.HypothesesError, match="remonterait"):
        hyp.vieillissement_entreprises("plf2027", 2023, 2022,
                                       gdp_of=lambda years: {y: 1.0 for y in years})


def test_a_vintage_without_a_year_does_not_age(tmp_path, monkeypatch, capsys) -> None:
    from impots import scenarios
    from impots.population import cli

    pl.DataFrame({"salaire_brut_annuel": [1.0]}).write_parquet(
        tmp_path / "population_essai.parquet")
    monkeypatch.setattr(cli, "PROCESSED", tmp_path)
    monkeypatch.setattr(scenarios, "load", lambda name: SimpleNamespace(year=2026))
    monkeypatch.setattr(scenarios, "mechanical_price",
                        lambda scenario, frame, households: {"mechanical": 1.0})
    args = cli.build_parser().parse_args([
        "chiffrage", "register", "x", "--scenario", "s", "--vintage", "essai",
        "--tolerance-relative", "0.3", "--tolerance-absolute", "1e7",
        "--tolerance-rationale", "essai", "--vieillir", "plf2027",
        "--dir", str(tmp_path / "cas")])
    assert args.func(args) == 1
    assert "pas d'année" in capsys.readouterr().err


def test_a_firm_vintage_without_a_year_does_not_age(tmp_path, monkeypatch, capsys,
                                                    fixture_firms) -> None:
    import impots.entreprises.build as firm_build
    from impots.population import cli

    monkeypatch.setattr(firm_build, "PROCESSED", tmp_path)
    fixture_firms.write_parquet(tmp_path / "firms_essai.parquet")
    (tmp_path / "firms_essai.manifest.json").write_text(
        json.dumps({"cells_are_synthetic": False}), encoding="utf-8")
    reform = tmp_path / "reforme.json"
    reform.write_text(json.dumps(PROROGATION_2027), encoding="utf-8")
    assert cli.main([
        "chiffrage", "register-entreprises", "x", "--reform", str(reform), "--year", "2027",
        "--vintage", "essai", "--tolerance-relative", "0.3", "--tolerance-absolute", "2e8",
        "--tolerance-rationale", "essai", "--vieillir", "plf2027",
        "--dir", str(tmp_path / "cas")]) == 1
    assert "pas d'année" in capsys.readouterr().err


def test_a_null_firm_factor_is_refused(tmp_path, fixture_firms) -> None:
    from impots.entreprises.reforms import FirmReformSpec

    tolerance = ch.Tolerance(relative=0.3, absolute_eur=2e8, rationale="essai")
    with pytest.raises(ch.ChiffrageError, match="facteur"):
        ch.register_firm("x", spec=FirmReformSpec.model_validate(PROROGATION_2027),
                         year=2027, frame=fixture_firms, tolerance=tolerance,
                         population_vintage="entreprises-2023", facteur=0.0,
                         vieillissement={"facteur": 0.0}, directory=tmp_path)
    assert not list(tmp_path.iterdir())


def test_a_missing_2027_wage_sentence_is_refused(tmp_path) -> None:
    plf = _edited(tmp_path, hyp.PLF_2027, "les salaires accéléreraient",
                  "les salaires évolueraient")
    with pytest.raises(hyp.HypothesesError, match="manque"):
        hyp.plf2027(plf=plf)


def test_a_yearly_rate_out_of_range_inside_a_sane_mean_is_refused() -> None:
    """Un taux d'une année hors bornes, que la moyenne de la série, elle, ne trahit pas."""
    with pytest.raises(up.UpratingError, match="wage 2025"):
        up.Uprating.par_annee({2025: 0.9, 2026: -0.4}, {2025: 0.01, 2026: 0.01}, "essai",
                              2024)


def _revisions_script():
    import importlib.util
    from pathlib import Path

    path = Path(__file__).resolve().parents[1] / "scripts" / "revisions_vieillies.py"
    spec = importlib.util.spec_from_file_location("revisions_vieillies", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_revision_takes_its_blind_case_comparator(tmp_path) -> None:
    import yaml

    tolerance = ch.Tolerance(relative=0.3, absolute_eur=1e7, rationale="essai")
    for name in ("cas", "cas_vieilli"):
        ch.register(name, mechanical_eur=1e8, tolerance=tolerance, population_vintage="2024",
                    sample=10, scenario="s", directory=tmp_path,
                    now="2026-11-01T00:00:00+00:00")
    original = yaml.safe_load((tmp_path / "cas.yaml").read_text(encoding="utf-8"))
    original["comparator"] = {
        "published_eur": -332e6, "source": "fiche, p. 602", "vintage": "PLF 2027",
        "perimeter": "le volet", "net_of": "rien", "sign": "yield",
        "basis": "premiere-annee", "retrieved": "2026-10-29"}
    (tmp_path / "cas.yaml").write_text(yaml.safe_dump(original, allow_unicode=True),
                                       encoding="utf-8")
    _revisions_script().comparateur("cas", tmp_path)
    assert ch.load("cas_vieilli", tmp_path).comparator.published_eur == -332e6


def test_each_revision_keeps_its_blind_case_tolerance() -> None:
    from impots.population import cli

    script = _revisions_script()
    for case in script.CASES:
        args = cli.build_parser().parse_args(script.arguments(case))
        original = ch.load(case)
        assert args.case == f"{case}_vieilli"
        assert (args.tolerance_relative, args.tolerance_absolute) == (
            original.tolerance.relative, original.tolerance.absolute_eur)
        assert args.vieillir == "plf2027" and args.apres_annexe
        assert getattr(args, "mirror", False) == original.mirror


def test_the_committed_table_is_the_rendered_one() -> None:
    """La page des révisions ne dérive pas de ce que le contrôle et le registre disent."""
    script = _revisions_script()
    controle = json.loads(script.CONTROLE.read_text(encoding="utf-8"))
    assert script.TABLEAU.read_text(encoding="utf-8") == script.tableau(controle)


def test_a_table_drawn_from_another_control_differs() -> None:
    script = _revisions_script()
    controle = json.loads(script.CONTROLE.read_text(encoding="utf-8"))
    controle["cas"]["plf2027_art_2"]["fige_aujourd_hui_eur"] *= 1.01
    assert script.TABLEAU.read_text(encoding="utf-8") != script.tableau(controle)


def test_a_control_from_another_commit_is_refused() -> None:
    """Le millésime est le vieilli moins le figé : les deux doivent venir du même commit."""
    script = _revisions_script()
    controle = json.loads(script.CONTROLE.read_text(encoding="utf-8"))
    controle["commit"] = "0" * 40
    with pytest.raises(SystemExit, match="même commit"):
        script.tableau(controle)
