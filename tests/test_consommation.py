"""La couche consommation (but 12, D-323, D-324) : la table des taux, l'imputation, la TVA et
les accises à volumes constants, les boutons et leur câblage dans la passe."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import polars as pl
import pytest

from impots import consommation as co
from impots.api.schemas import ReformSpec

ROOT = Path(__file__).resolve().parents[1]


def _script():
    path = ROOT / "scripts" / "table_postes_tva.py"
    spec = importlib.util.spec_from_file_location("table_postes_tva", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# --- la table ------------------------------------------------------------------------


def test_the_committed_table_is_the_generated_one(tmp_path) -> None:
    """La table que lit le moteur est celle que le script tire de regles.md, rien d'autre."""
    s = _script()
    assert co.POSTES.read_text(encoding="utf-8") == s.ecrire(s.lire(), tmp_path / "t.csv")


def test_the_table_holds_every_leaf_of_the_consumption() -> None:
    """GARDE (D-324). Les codes à trois chiffres et deux lettres (`022ZZ`, le tabac) étaient
    écartés par le motif du script : 1 549 € par ménage de 2017 jamais taxés."""
    codes = {p.code for p in co.postes()}
    assert {"022ZZ", "032ZZ", "045AZ", "073ZZ", "093AZ"} <= codes
    assert len(codes) == 138 and not any(c.startswith("13") for c in codes)


def test_a_mixed_poste_without_a_decision_is_refused(monkeypatch) -> None:
    """GARDE (D-324). Une cellule « MIXTE » qui ne nomme qu'un taux (les automobiles : 20 %
    sur le neuf, la marge sur l'occasion) passait pour un taux unique."""
    s = _script()
    mixtes = dict(s.MIXTES)
    mixtes.pop("0711Z")
    monkeypatch.setattr(s, "MIXTES", mixtes)
    with pytest.raises(SystemExit, match="0711Z : poste mêlé sans décision"):
        s.lire()


def test_an_ambiguous_poste_without_a_decision_is_refused(monkeypatch) -> None:
    s = _script()
    mixtes = dict(s.MIXTES)
    mixtes.pop("0611Z")
    monkeypatch.setattr(s, "MIXTES", mixtes)
    with pytest.raises(SystemExit, match="0611Z"):
        s.lire()


def test_a_decision_outside_its_bounds_is_refused(monkeypatch) -> None:
    s = _script()
    monkeypatch.setattr(s, "MIXTES", {**s.MIXTES, "11111": (0.20, 0.10, 0.10, "x")})
    with pytest.raises(SystemExit, match=r"11111 : le taux 0\.2 n'est pas entre ses bornes"):
        s.lire()


def test_a_decision_for_a_poste_the_table_lacks_is_refused(monkeypatch) -> None:
    s = _script()
    monkeypatch.setattr(s, "MIXTES", {**s.MIXTES, "99999": (0.2, 0.2, 0.2, "x")})
    with pytest.raises(SystemExit, match="absents de la table"):
        s.lire()


# --- l'imputation --------------------------------------------------------------------


def test_tf106_refuses_a_poste_it_does_not_carry(monkeypatch) -> None:
    extra = co.Poste("99999", "absent", 0.2, 0.2, 0.2, False, "")
    vrais = co.postes()
    monkeypatch.setattr(co, "postes", lambda path=co.POSTES: (*vrais, extra))
    with pytest.raises(co.ConsommationError, match="99999"):
        co.tf106.__wrapped__(co.BDF)


def test_tf106_refuses_a_leaf_the_table_forgets(monkeypatch) -> None:
    """GARDE (D-324). La table qui oubliait le tabac se chargeait sans un mot."""
    vrais = tuple(p for p in co.postes() if p.code != "022ZZ")
    monkeypatch.setattr(co, "postes", lambda path=co.POSTES: vrais)
    with pytest.raises(co.ConsommationError, match="oublie les postes \\['022ZZ'\\]"):
        co.tf106.__wrapped__(co.BDF)


def test_the_joint_bill_is_split_within_its_decile() -> None:
    """GARDE (R11, D-324). La facture commune d'électricité et de gaz n'avait aucune accise :
    elle va aux deux factures séparées, au prorata de chaque décile."""
    import csv
    import io
    import zipfile

    t = co.tf106()
    assert "04500" not in t
    with zipfile.ZipFile(co.BDF) as z:
        nom = next(n for n in z.namelist() if n.lower() == "tf106.csv")
        rows = list(csv.DictReader(io.StringIO(z.read(nom).decode("latin-1")), delimiter=";"))
    brut = {(r["NOMENCLATURE"], r["DECUC"]): float(r["CONSO"]) for r in rows}
    for k in range(1, 11):
        e, g, c = (brut[(code, str(k))] for code in ("04511", "0452Z", "04500"))
        assert t["04511"][k - 1] == pytest.approx(e + c * e / (e + g))
        assert t["0452Z"][k - 1] == pytest.approx(g + c * g / (e + g))
    with pytest.raises(ValueError, match="04500"):
        ReformSpec(tva_postes={"04500": 0.055})


def test_at_the_survey_year_nothing_moves() -> None:
    assert all(f == pytest.approx(1.0) for f in co.croissance(2017).values())


def test_a_poste_follows_its_division_or_the_total() -> None:
    """GARDE (D-324). D-323 dit la division ; le code suivait la sous-classe, dont les
    numéros ne se répondent pas d'une nomenclature à l'autre (le tabac)."""
    f = co.croissance(2024)
    cn = co._comptes()
    total = co._total(cn, 2024) / co._total(cn, 2017)
    division = cn["CP07"][2024] / cn["CP07"][2017]
    assert f["07221"] == pytest.approx(division)
    assert f["07221"] != pytest.approx(cn["CP0722"][2024] / cn["CP0722"][2017])
    assert f["022ZZ"] == pytest.approx(cn["CP02"][2024] / cn["CP02"][2017])
    assert f["0942Z"] == pytest.approx(total)


def test_past_the_accounts_the_prices_must_be_given() -> None:
    with pytest.raises(co.ConsommationError, match="pas de comptes nationaux en 2026"):
        co.croissance(2026)
    base = co.croissance(2025)
    plus = co.croissance(2027, {2026: 0.02, 2027: 0.01})
    for code, facteur in base.items():
        assert plus[code] == pytest.approx(facteur * 1.02 * 1.01)


def test_the_imputation_keeps_each_decile_s_mean() -> None:
    rng = np.random.default_rng(0)
    n = 3000
    deciles = rng.integers(1, 11, n)
    uc = rng.uniform(1.0, 3.0, n)
    poids = rng.uniform(100.0, 2000.0, n)
    conso = co.imputer(deciles, uc, poids, 2024)
    facteurs = co.croissance(2024)
    for code, valeurs in co.tf106().items():
        for k in (1, 5, 10):
            m = deciles == k
            assert np.average(conso[code][m], weights=poids[m]) == pytest.approx(
                valeurs[k - 1] * facteurs[code])
    with pytest.raises(co.ConsommationError, match="de 1 à 10"):
        co.imputer(np.array([0, 3]), np.ones(2), np.ones(2), 2024)


# --- la TVA et les accises -----------------------------------------------------------


def _une_depense(code: str, euros: float) -> dict[str, np.ndarray]:
    conso = {c: np.zeros(1) for c in co.tf106()}
    conso[code] = np.array([euros])
    return conso


def test_the_vat_of_a_poste_is_its_share_of_the_spending() -> None:
    out = co.taxes(_une_depense("032ZZ", 120.0), co.Fiscalite.droit(2024))
    assert out["tva"][0] == pytest.approx(20.0)
    assert out["accises"][0] == 0.0


def test_an_excise_moves_at_constant_volumes_and_carries_its_vat() -> None:
    droit = co.Fiscalite.droit(2024)
    conso = _une_depense("04511", 1000.0)
    base = co.taxes(conso, droit)
    mwh = 1000.0 / droit.prix["electricite"]
    assert base["accises"][0] == pytest.approx(mwh * 21.0)
    assert base["tva"][0] == pytest.approx(1000.0 * 0.2 / 1.2)
    reforme = co.taxes(conso, droit.reformee(ReformSpec(accise_electricite=31.0)),
                       reference=droit)
    assert reforme["accises"][0] - base["accises"][0] == pytest.approx(mwh * 10.0)
    assert reforme["tva"][0] - base["tva"][0] == pytest.approx(mwh * 10.0 * 0.2)


def test_a_vat_cut_on_fuel_is_its_rate_on_the_price_before_vat() -> None:
    droit = co.Fiscalite.droit(2024)
    conso = _une_depense("07221", 1200.0)
    base = co.taxes(conso, droit)
    reforme = co.taxes(conso, droit.reformee(ReformSpec(tva_postes={"carburants": 0.055})),
                       reference=droit)
    assert reforme["tva"][0] == pytest.approx(1000.0 * 0.055)
    assert reforme["accises"][0] == pytest.approx(base["accises"][0])


def test_a_rate_knob_moves_the_postes_at_that_rate_and_no_other() -> None:
    droit = co.Fiscalite.droit(2024)
    reforme = droit.reformee(ReformSpec(tva_taux_reduit=0.06))
    for p in co.postes():
        attendu = 0.06 if p.taux == 0.055 else droit.taux[p.code]
        assert reforme.taux[p.code] == attendu, p.code


def test_a_group_reaches_each_of_its_postes_and_an_unknown_key_is_refused() -> None:
    droit = co.Fiscalite.droit(2024)
    reforme = droit.reformee(ReformSpec(tva_postes={"energie": 0.055}))
    assert all(reforme.taux[c] == 0.055 for c in co.GROUPES["energie"])
    with pytest.raises(ValueError, match="tva_postes"):
        ReformSpec(tva_postes={"inconnu": 0.1})
    with pytest.raises(ValueError, match="tva_postes"):
        ReformSpec(tva_postes={})


def test_a_year_without_its_excises_is_refused() -> None:
    with pytest.raises(co.ConsommationError, match="2019"):
        co.Fiscalite.droit(2019)


def test_the_knobs_of_the_layer_are_the_spec_s_consumption_fields() -> None:
    """Un bouton de consommation hors de BOUTONS irait à openfisca, qui ne le lit pas."""
    champs = {f for f in ReformSpec.model_fields if f.startswith(("tva_", "accise_"))}
    assert champs == set(co.BOUTONS)
    spec = ReformSpec(tva_taux_normal=0.21, accise_gaz=20.0, pfu_taux=0.3)
    assert co.touche(spec) and not co.touche(co.sans_consommation(spec))
    assert co.sans_consommation(spec).pfu_taux == 0.3


def test_one_household_refuses_a_consumption_knob() -> None:
    """GARDE (D-324). Un ménage seul n'a pas de consommation : le bouton y était mort."""
    from impots.api.schemas import HouseholdInput
    from impots.engine.compute import compute

    household = HouseholdInput.model_validate(
        {"adults": [{"salaire_brut_annuel": 30_000, "annee_naissance": 1980}]})
    with pytest.raises(ValueError, match="un ménage seul n'a pas de consommation"):
        compute(household, 2024, reform=ReformSpec(tva_taux_normal=0.21))


# --- le câblage ----------------------------------------------------------------------


def _foyers(n: int = 400) -> pl.DataFrame:
    rng = np.random.default_rng(1)
    return pl.DataFrame({
        "weight": rng.uniform(1_000.0, 5_000.0, n),
        "n_aged_14_plus": rng.integers(1, 4, n),
        "n_children_under_14": rng.integers(0, 3, n),
        "n_persons": rng.integers(1, 6, n),
        "revenu_disponible": rng.uniform(8_000.0, 120_000.0, n),
    })


def test_the_columns_carry_the_reform_only_when_it_touches_consumption() -> None:
    foyers = _foyers()
    sans = co.colonnes(foyers, 2024)
    assert set(sans) == {"tva_menages", "accises_energie", "consommation_imputee"}
    avec = co.colonnes(foyers, 2024, ReformSpec(tva_taux_normal=0.21))
    assert (avec["tva_menages_reform"] > avec["tva_menages"]).all()
    assert np.array_equal(avec["accises_energie_reform"], avec["accises_energie"])


def test_the_cost_and_the_deciles_count_the_consumption_taxes() -> None:
    """GARDE. Le coût public d'une hausse de TVA est la recette en plus, en négatif ; le
    pouvoir d'achat de chaque ménage baisse de la taxe qu'il paie en plus."""
    from impots.population.aggregate import aggregate

    foyers = _foyers()
    couche = co.colonnes(foyers, 2024, ReformSpec(tva_taux_normal=0.21))
    frame = foyers.with_columns(
        pl.col("revenu_disponible").alias("revenu_disponible_reform"),
        *[pl.Series(k, v) for k, v in couche.items()])
    agg = aggregate(frame)
    w = foyers["weight"].to_numpy()
    paye = couche["tva_menages_reform"] - couche["tva_menages"]
    assert agg.reform_cost == pytest.approx(-float(w @ paye))
    assert agg.balance["unexplained"] == pytest.approx(0.0, abs=1.0)
    assert all(row.mean_delta < 0 for row in agg.deciles)
    total = sum(row.mean_delta * row.n_households for row in agg.deciles)
    assert total == pytest.approx(-float(w @ paye))


def test_the_pass_refuses_a_consumption_knob_without_the_imputation() -> None:
    from impots.population.runner import run
    from impots.population.to_openfisca import WiringError

    with pytest.raises(WiringError, match="consommation"):
        run(pl.DataFrame(), year=2024, reform=ReformSpec(tva_taux_normal=0.21))


def test_a_scenario_asks_for_the_imputation_and_the_pass_receives_it(monkeypatch) -> None:
    from impots import scenarios
    from impots.population import runner

    seen = {}

    def run(frame, **kwargs):
        seen.update(kwargs)
        raise RuntimeError("arrêté")

    monkeypatch.setattr(runner, "run", run)
    scen = scenarios.Scenario(name="essai", year=2024, created="2026-11-02", source="essai",
                              reform=ReformSpec(tva_taux_normal=0.21),
                              imputations=("consommation",))
    with pytest.raises(RuntimeError, match="arrêté"):
        scenarios.mechanical_price(scen, frame=object(), prix_au_dela={2026: 0.02})
    assert seen["impute_consommation"] is True and seen["prix_au_dela"] == {2026: 0.02}


def test_the_api_imputes_whenever_the_reform_touches_consumption(monkeypatch) -> None:
    from types import SimpleNamespace

    from impots.api import main
    from impots.population import runner

    seen = []

    def run(frame, **kwargs):
        seen.append(kwargs["impute_consommation"])
        raise RuntimeError("arrêté")

    monkeypatch.setattr(runner, "run", run)
    for reform, attendu in ((ReformSpec(accise_gazole=0.7), True),
                            (ReformSpec(pfu_taux=0.3), False)):
        with pytest.raises(RuntimeError, match="arrêté"):
            main._run_population(SimpleNamespace(year=2024, reform=reform, sample=100),
                                 object())
        assert seen[-1] is attendu


def test_a_pass_prices_a_consumption_reform_on_the_fixture_population() -> None:
    """La passe entière, sur la population de test : l'arbre ne voit pas les boutons de
    consommation, le revenu disponible ne bouge pas, et le coût est la TVA en plus."""
    from impots.population import margins
    from impots.population.aggregate import aggregate
    from impots.population.incomes import attach_incomes, household_share_of_france
    from impots.population.runner import run
    from impots.population.skeleton import build_skeleton

    children = {k: np.array(v) for k, v in margins.CHILDREN_PER_FAMILY.items()}
    frame, _ = build_skeleton(children_per_household=children, source=pl.read_parquet(
        ROOT / "tests" / "fixtures" / "eec_sample.parquet"))
    frame, _ = attach_incomes(frame, targets_scale=household_share_of_france(frame))
    r = run(frame, year=2024, reform=ReformSpec(tva_taux_normal=0.21), tier="full",
            impute_consommation=True)
    h = r.households
    assert (h["revenu_disponible_reform"] == h["revenu_disponible"]).all()
    assert (h["tva_menages_reform"] > h["tva_menages"]).all()
    agg = aggregate(h)
    w = h["weight"].to_numpy()
    plus = float(w @ (h["tva_menages_reform"] - h["tva_menages"]).to_numpy())
    assert agg.reform_cost == pytest.approx(-plus)
    assert agg.balance["unexplained"] == pytest.approx(0.0, abs=1.0)
    assert "consommation_s" in r.timings


# --- la vérification préenregistrée (D-323, D-324) -----------------------------------


def _verif():
    path = ROOT / "scripts" / "verifier_consommation.py"
    spec = importlib.util.spec_from_file_location("verifier_consommation", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_check_reads_its_targets_from_the_manifested_files() -> None:
    v = _verif()
    assert v.tva_nette_2024() == pytest.approx(209e9)
    assert v.depense_cn_2024() == pytest.approx(1_527_122.9e6, rel=1e-6)
    assert v.carburants_sdes_2024() == pytest.approx((29_900.98 + 22_751.92) * 1e6, rel=1e-6)


def test_the_check_refuses_a_pass_that_taxed_another_consumption() -> None:
    """GARDE. La vérification recalcule la consommation de la passe : si elle ne retrouve
    pas la TVA que la passe a écrite, elle ne vérifie pas la même chose, et le dit."""
    v = _verif()
    foyers = _foyers()
    frame = foyers.with_columns(
        *[pl.Series(k, x) for k, x in co.colonnes(foyers, 2024).items()])
    r = v.verifier(frame)
    assert set(r) >= {"couverture", "tva", "point", "carburants", "accises", "profil"}
    faux = frame.with_columns(pl.col("tva_menages") * 1.01)
    with pytest.raises(SystemExit, match="ne lisent pas la même consommation"):
        v.verifier(faux)


# --- la consommation sur le chemin annuel (D-328) -------------------------------------


def test_past_the_last_law_the_excises_are_carried_and_the_prices_follow_the_index() -> None:
    """GARDE (D-328). Le chemin annuel chiffre 2027 à 2035 : les accises de 2026 y sont
    reconduites, et les prix qui tirent les volumes suivent l'indice qui porte les euros."""
    indice = {a: 0.02 for a in range(2026, 2031)}
    droit = co.Fiscalite.droit(2030, prix_au_dela=indice)
    assert droit.accise == co.LOI_ENERGIE[2026]["accise"]
    for produit, prix in co.LOI_ENERGIE[2026]["prix"].items():
        assert droit.prix[produit] == pytest.approx(prix * 1.02 ** 4)
    with pytest.raises(co.ConsommationError, match="2028"):
        co.Fiscalite.droit(2030, prix_au_dela={2027: 0.02})
    with pytest.raises(co.ConsommationError, match="2025"):
        co.Fiscalite.droit(2025)


def test_the_consumption_year_is_the_population_s_not_the_law_s() -> None:
    """GARDE (D-328). Sur une population qui n'est pas vieillie, la consommation est celle
    de son millésime, aux prix de son millésime ; le droit reste celui de l'année."""
    foyers = _foyers()
    a = co.colonnes(foyers, 2026, annee_consommation=2024)
    conso, _, _ = co.imputer_menages(foyers, 2024)
    attendu = co.taxes(conso, co.Fiscalite.droit(2026, annee_prix=2024))
    assert np.allclose(a["consommation_imputee"], sum(conso.values()))
    assert np.allclose(a["accises_energie"], attendu["accises"])
    b = co.colonnes(foyers, 2026)
    assert b["consommation_imputee"].sum() > a["consommation_imputee"].sum()


def test_the_frame_s_price_index_carries_the_years_past_the_accounts() -> None:
    from impots import uprating as up

    cadre = up.Uprating(wage=0.03, price=0.02, source="essai", base_year=2024)
    assert co.prix_du_cadre(cadre, 2028) == {2026: 0.02, 2027: 0.02, 2028: 0.02}
    par_annee = up.Uprating.par_annee({2025: 0.02, 2026: 0.03}, {2025: 0.01, 2026: 0.015},
                                      source="essai", base_year=2024)
    assert co.prix_du_cadre(par_annee, 2026) == {2026: 0.015}


def test_each_view_of_the_path_imputes_its_own_consumption(monkeypatch) -> None:
    """GARDE (D-328). La vue vieillie impute l'année, à l'indice du cadre ; la vue figée,
    le millésime. La première année du simulateur aussi, sur sa population telle quelle."""
    from types import SimpleNamespace

    from impots import uprating as up
    from impots.api import main
    from impots.population import runner

    seen = []

    def run(frame, **kwargs):
        seen.append(kwargs)
        raise RuntimeError("arrêté")

    monkeypatch.setattr(runner, "run", run)
    monkeypatch.setattr(main, "_population_frame", lambda: pl.DataFrame({"x": [1]}))
    monkeypatch.setattr(up, "uprate", lambda frame, year, hypothesis: frame)
    cadre = up.Uprating(wage=0.03, price=0.02, source="essai", base_year=2024)
    request = main.YearPass(reform=ReformSpec(accise_gazole=0.7), year=2028, behavioural=False)
    for view in (main.FIRST_YEAR_VIEW, main.FROZEN_VIEW):
        with pytest.raises(RuntimeError, match="arrêté"):
            main._price_households(request, uprating=cadre, macro=False, view=view)
    aged, frozen = seen
    assert aged["annee_consommation"] == 2028
    assert aged["prix_au_dela"] == {2026: 0.02, 2027: 0.02, 2028: 0.02}
    assert frozen["annee_consommation"] == 2024 and frozen["prix_au_dela"] is None
    with pytest.raises(RuntimeError, match="arrêté"):
        main._run_population(SimpleNamespace(year=2026, reform=ReformSpec(accise_gazole=0.7)),
                             object())
    assert seen[-1]["annee_consommation"] == 2024


def test_the_path_s_own_passes_impute_the_consumption_of_their_view() -> None:
    from impots import uprating as up
    from impots.population import cli

    cadre = up.Uprating(wage=0.03, price=0.02, source="essai", base_year=2024)
    spec = ReformSpec(tva_taux_normal=0.21)
    assert cli._consommation(ReformSpec(pfu_taux=0.3), 2027, "vieillie", cadre, "2024") == {}
    assert cli._consommation(spec, 2027, "figee", cadre, "2024") == {
        "impute_consommation": True, "annee_consommation": 2024}
    assert cli._consommation(spec, 2027, "vieillie", cadre, "2024") == {
        "impute_consommation": True, "annee_consommation": 2027,
        "prix_au_dela": {2026: 0.02, 2027: 0.02}}


def test_the_path_takes_a_consumption_scenario_and_still_refuses_the_sick_pay() -> None:
    from impots import scenarios

    def scen(imputations):
        return scenarios.Scenario(name="essai", year=2026, created="2026-11-02",
                                  source="essai", reform=ReformSpec(tva_taux_normal=0.21),
                                  imputations=imputations)

    assert scen(("consommation",)).reform_in(2030).tva_taux_normal == 0.21
    with pytest.raises(scenarios.ScenarioError, match="D-306"):
        scen(("ij",)).reform_in(2026)


def test_the_marginal_rates_read_the_tree_part_of_a_consumption_reform(monkeypatch) -> None:
    """GARDE (D-328). Une passe avec comportements calcule les taux marginaux sous la
    réforme : avec ses boutons de TVA, l'arbre la refusait, et toute bande d'une réforme de
    consommation tombait. L'arbre en reçoit la part qu'il lit, et rien d'autre."""
    from impots.behavioural import emtr

    seen = []

    def reformed_for(spec, year):
        seen.append(spec)
        raise RuntimeError("arrêté")

    monkeypatch.setattr(emtr, "reformed_for", reformed_for)
    monkeypatch.setattr(emtr, "_rate", lambda *a, **k: (np.zeros(1), np.zeros(1)))
    monkeypatch.setattr(emtr, "_priced", lambda population, sample, seed: population)
    frame = pl.DataFrame({"household_id": [1], "weight": [1.0],
                          "salaire_brut_annuel": [20_000.0]})
    seul = emtr.compute(frame, 2024, ReformSpec(tva_taux_normal=0.21))
    assert "emtr_reform" not in seul.households.columns and not seen
    with pytest.raises(RuntimeError, match="arrêté"):
        emtr.compute(frame, 2024, ReformSpec(tva_taux_normal=0.21, pfu_taux=0.3))
    assert seen == [ReformSpec(pfu_taux=0.3)]
