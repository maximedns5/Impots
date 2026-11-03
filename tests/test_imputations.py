"""Une seule politique d'imputation, et la garde du zéro confiant (but 14, D-336).

Tous légers : des objets réforme, et des passes arrêtées avant de tourner. Chaque règle a
son test ; ceux des chemins voient ce que la passe aurait reçu, et échouent sur le code
d'avant, où chaque chemin recopiait sa propre politique (audit du but 14, annexe 2,
§ 4.3)."""

from __future__ import annotations

from types import SimpleNamespace

import polars as pl
import pytest

from impots import guards, service
from impots.api.schemas import IRBracket, ReformSpec
from impots.population import imputations as imp

# --- la politique, règle par règle --------------------------------------------------


def test_a_capital_knob_imputes_the_capital() -> None:
    assert imp.imputations(ReformSpec(pfu_taux=0.2), 2024).noms() == (imp.CAPITAL,)
    assert imp.imputations(ReformSpec(csg_capital_taux_global=0.1), 2024).capital


def test_a_consumption_knob_imputes_the_consumption() -> None:
    assert imp.imputations(ReformSpec(tva_taux_normal=0.21), 2026).noms() == (
        imp.CONSOMMATION,)
    assert imp.imputations(ReformSpec(accise_gazole=0.7), 2024).consommation


def test_a_sick_pay_knob_imputes_the_sick_pay_in_2024_and_is_refused_after() -> None:
    assert imp.imputations(ReformSpec(csg_ij_taux=0.08), 2024).noms() == (imp.IJ,)
    with pytest.raises(imp.ImputationRefusee, match="csg_ij_taux"):
        imp.imputations(ReformSpec(csg_ij_taux=0.08), 2026)


def test_what_the_caller_asks_is_added_and_nothing_else() -> None:
    reform = ReformSpec(decote_taux=0.3)
    assert imp.imputations(reform, 2024).noms() == ()
    assert imp.imputations(reform, 2024, demandees=(imp.NICHES,)).noms() == (imp.NICHES,)
    assert imp.imputations(reform, 2024, demandees=(imp.IJ, imp.CONSOMMATION)).noms() == (
        imp.CONSOMMATION, imp.IJ)
    with pytest.raises(imp.ImputationRefusee, match="inconnues"):
        imp.imputations(reform, 2024, demandees=("patrimoine",))


def test_an_ifi_knob_is_refused_on_the_population_with_its_gate() -> None:
    for reform in (ReformSpec(ifi_decote_taux=0.01),
                   ReformSpec(ifi_bareme=[IRBracket(threshold=1_300_000, rate=0.01)]),
                   ReformSpec(ifi_obligations_declaratives="renforcees")):
        with pytest.raises(imp.ImputationRefusee, match="porte « patrimoine »"):
            imp.imputations(reform, 2024)


def test_a_path_that_cannot_impute_what_a_knob_needs_refuses_it() -> None:
    with pytest.raises(imp.ImputationRefusee, match="le chemin d'essai n'impute pas"):
        imp.imputations(ReformSpec(tva_taux_normal=0.21), 2026, possibles=(imp.CAPITAL,),
                        chemin="le chemin d'essai")
    # Ce qu'il sait imputer passe.
    assert imp.imputations(ReformSpec(pfu_taux=0.2), 2024,
                           possibles=(imp.CAPITAL,)).capital


def test_a_consumption_year_the_table_cannot_serve_is_refused_before_the_pass() -> None:
    with pytest.raises(imp.ImputationRefusee, match="1er août 2025"):
        imp.imputations(ReformSpec(tva_taux_normal=0.21), 2025)


# --- la garde du zéro confiant -------------------------------------------------------


def test_the_guard_names_every_knob_that_cannot_move() -> None:
    knobs = ["pfu_taux", "tva_taux_normal", "csg_ij_taux", "ifi_decote_taux", "saldom_taux",
             "decote_taux"]
    blind = guards.zero_confiant(knobs, (), {})
    assert set(blind) == set(knobs) - {"decote_taux"}
    # Imputés, ils bougent ; l'IFI jamais.
    imputed = (imp.CAPITAL, imp.CONSOMMATION, imp.IJ, imp.NICHES)
    assert set(guards.zero_confiant(knobs, imputed, {"credits_impot": 1e9})) == {
        "ifi_decote_taux"}
    # Le plafond global reste aveugle, même les bases imputées.
    assert set(guards.zero_confiant(["plafond_global_niches"], imputed,
                                    {"credits_impot": 1e9})) == {"plafond_global_niches"}


def test_the_guard_refuses_with_each_reason() -> None:
    with pytest.raises(guards.ZeroConfiantError, match="`csg_ij_taux` ne bouge pas"):
        guards.refuse_zero_confiant(["csg_ij_taux"], (), {}, chemin="essai")
    guards.refuse_zero_confiant(["csg_ij_taux"], (imp.IJ,), {}, chemin="essai")


def test_an_absent_cost_is_refused_not_turned_into_zero() -> None:
    with pytest.raises(guards.CoutAbsentError, match="pas un coût nul"):
        guards.cout_calcule(None, chemin="essai")
    assert guards.cout_calcule(0.0, chemin="essai") == 0.0


# --- aucun nombre publié ne change -----------------------------------------------------


def test_every_registered_scenario_gets_what_each_path_gave_it_before() -> None:
    """Chaque scénario de `scenarios/` reçoit, de la politique unique, exactement ce que
    lui donnait chacun des chemins qui le chiffrent : le chiffrage mécanique (ce que le
    scénario demande), l'API et le chemin annuel (le capital et la consommation quand la
    réforme les règle). Aucun ne règle le capital, l'IFI ni une niche aujourd'hui."""
    from impots import consommation
    from impots import scenarios as sc
    from impots.engine.reforms import moves_capital

    for name in sc.available():
        scenario = sc.load(name)
        reform, year = scenario.reform, scenario.year
        got = imp.imputations(reform, year, demandees=scenario.imputations)
        before = SimpleNamespace(
            capital=False, consommation="consommation" in scenario.imputations,
            ij="ij" in scenario.imputations, niches=False)
        assert vars(before) == {k: getattr(got, k) for k in vars(before)}, name
        if "ij" not in scenario.imputations:
            api = imp.imputations(reform, year)
            assert (api.capital, api.consommation, api.ij, api.niches) == (
                moves_capital(reform), consommation.touche(reform), False, False), name


def test_every_programme_measure_gets_what_the_api_gave_it_before() -> None:
    from impots import consommation
    from impots import programmes as pg
    from impots.engine.reforms import moves_capital

    for slug in pg.lister():
        menages, _ = pg.charger(slug).reformes()
        if menages is None or menages.is_empty():
            continue
        got = imp.imputations(menages, 2026)
        assert (got.capital, got.consommation, got.ij, got.niches) == (
            moves_capital(menages), consommation.touche(menages), False, False), slug


# --- chaque chemin appelle la politique ------------------------------------------------


class _Arret(Exception):
    pass


def _spy(monkeypatch) -> list[dict]:
    from impots.population import runner

    seen: list[dict] = []

    def run(frame, **kwargs):
        seen.append(kwargs)
        raise _Arret

    monkeypatch.setattr(runner, "run", run)
    return seen


def test_the_mechanical_pricing_imputes_the_capital_a_pfu_reform_needs(monkeypatch) -> None:
    """Avant, `mechanical_price` n'imputait jamais le capital : un préenregistrement du PFU
    aurait coûté zéro."""
    from impots import scenarios as sc

    seen = _spy(monkeypatch)
    scenario = sc.Scenario(name="essai_pfu", year=2024, created="2026-11-03",
                           source="essai", reform=ReformSpec(pfu_taux=0.2))
    with pytest.raises(_Arret):
        sc.mechanical_price(scenario, frame=pl.DataFrame(), households=10)
    assert seen[-1]["impute_capital"] is True


def test_the_solver_imputes_the_consumption_a_vat_knob_needs(monkeypatch) -> None:
    """Avant, le solveur n'imputait rien : un bouton de TVA y levait `WiringError`."""
    from impots import scenarios as sc

    seen = _spy(monkeypatch)
    price = sc.knob_pricer("tva_taux_normal", year=2026, frame=pl.DataFrame(),
                           households=10)
    with pytest.raises(_Arret):
        price(0.21)
    assert seen[-1]["impute_consommation"] is True
    with pytest.raises(imp.ImputationRefusee, match="patrimoine"):
        sc.knob_pricer("ifi_decote_taux", year=2024, frame=pl.DataFrame())(0.01)


def test_the_api_imputes_the_sick_pay_an_ij_knob_needs(monkeypatch) -> None:
    """Avant, l'API n'imputait jamais les IJ : un bouton des IJ y rendait un zéro."""
    seen = _spy(monkeypatch)
    with pytest.raises(_Arret):
        service.run_population(
            SimpleNamespace(year=2024, reform=ReformSpec(csg_ij_taux=0.08)), pl.DataFrame())
    assert seen[-1]["impute_ij"] is True
    with pytest.raises(service.ServiceError) as refused:
        service.run_population(
            SimpleNamespace(year=2024, reform=ReformSpec(ifi_decote_taux=0.01)),
            pl.DataFrame())
    assert refused.value.status_code == 422


def test_the_annual_path_refuses_what_it_cannot_impute(monkeypatch) -> None:
    from impots.population import cli

    _spy(monkeypatch)
    with pytest.raises(imp.ImputationRefusee, match="n'impute pas \\['ij'\\]"):
        cli._chemin_pass(pl.DataFrame(), 2024, ReformSpec(csg_ij_taux=0.08), capital=False,
                         index=1.0, sample=10, view="figee", uprating=None, vintage="2024",
                         chemin="le chemin annuel")


def test_the_annual_path_imputes_the_scenario_s_capital_in_both_passes(monkeypatch) -> None:
    """Contre `indexe` un coût est la différence de deux passes : le capital décidé sur la
    réforme du scénario est imputé aussi dans la passe de l'indexation seule, qui ne règle
    pas le PFU (D-249). Remplace le test qui comptait des chaînes dans le source (D-336)."""
    from impots.population import cli

    seen = _spy(monkeypatch)
    with pytest.raises(_Arret):
        cli._chemin_pass(pl.DataFrame(), 2026, ReformSpec(decote_taux=0.3), capital=True,
                         index=1.06, sample=10, view="figee", uprating=None,
                         vintage="2024", chemin="le chemin annuel")
    assert seen[-1]["impute_capital"] is True and seen[-1]["capital_index"] == 1.06
