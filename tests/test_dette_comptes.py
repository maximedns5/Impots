"""Phase 8 §6.1 — assembling realized inputs, and the two traps in the published files."""

from __future__ import annotations

import pytest

from impots.dette import comptes
from impots.dette.path import DebtError

YEARS = list(range(2019, 2026))

needs_files = pytest.mark.skipif(
    not (comptes.RAW / comptes.APU_FILE).exists(),
    reason="les fichiers INSEE ne sont pas dans ce checkout (data/raw est ignoré)",
)


# --------------------------------------------------------------------------- #
# trap 1 — D41 has TWO legs and the identity wants the net
# --------------------------------------------------------------------------- #
def test_net_interest_is_uses_minus_resources_not_uses_alone() -> None:
    """Public administrations both pay and receive interest.

    Reading the uses row alone overstates the charge by the resources leg — about 8 % on
    2025 — and `r` is that charge over the stock, so the error lands whole on the rate.
    Asserted on a constructed year so it holds whatever the published figures become.
    """
    year = comptes.ApuYear(year=2025, interest_resources_eur=5.268e9,
                           interest_uses_eur=67.516e9, net_lending_eur=-151.592e9)
    assert year.interest_net_eur == pytest.approx(62.248e9)
    assert year.interest_net_eur != year.interest_uses_eur


def test_the_primary_balance_adds_interest_back_with_surplus_positive() -> None:
    """`path` takes the primary balance SURPLUS POSITIVE. A sign error here inverts the
    whole trajectory while still looking like a trajectory."""
    year = comptes.ApuYear(year=2025, interest_resources_eur=5.268e9,
                           interest_uses_eur=67.516e9, net_lending_eur=-151.592e9)
    assert year.primary_balance_eur == pytest.approx(-89.344e9)
    assert year.primary_balance_eur > year.net_lending_eur


def test_a_file_carrying_one_d41_row_is_refused(monkeypatch) -> None:
    """The kill test for the two-leg guard.

    A vintage that merged the legs, or a parse that found only one, would silently make
    the net equal the gross. Refused by name instead.
    """
    rows = [("1.7", None), ("Unité",), (None,), ("2019", "2020"),
            ("D41 Intérêts", None, 1.0, 2.0),
            ("B9 Capacité", None, -1.0, -2.0)]
    monkeypatch.setattr(comptes, "_rows", lambda *a, **k: rows)
    monkeypatch.setattr(comptes, "_year_columns", lambda *a, **k: {2019: 2, 2020: 3})
    with pytest.raises(DebtError, match="attendu 2"):
        comptes.apu_account([2019])


def test_a_textual_cell_is_refused_rather_than_read_as_zero(monkeypatch) -> None:
    """« n.d. » coerced to 0 would pass through every later check without a murmur."""
    rows = [("D41 Intérêts", None, "n.d."), ("D41 Intérêts", None, 2.0),
            ("B9 Capacité", None, -1.0)]
    monkeypatch.setattr(comptes, "_rows", lambda *a, **k: rows)
    monkeypatch.setattr(comptes, "_year_columns", lambda *a, **k: {2019: 2})
    with pytest.raises(DebtError, match="manquante ou textuelle"):
        comptes.apu_account([2019])


# --------------------------------------------------------------------------- #
# trap 2 — the stock is in MILLIONS, its neighbours in milliards
# --------------------------------------------------------------------------- #
def test_a_stock_read_in_milliards_fails_the_unit_check(monkeypatch) -> None:
    """THE guard for the lying-header class, and its kill test in one.

    A factor of a thousand still parses as a number and still plots as a curve. Only the
    published ratio catches it, which is why the check divides by GDP instead of asserting
    the unit in a comment. The implementation that fails here is the natural misreading:
    treating the column as milliards because every column beside it is.
    """
    # The raw cell reads 2 387 398,96. Converted correctly (x1e6) that is 2,39e12 EUR;
    # misread as milliards (x1e9) it is 2,39e15 — a thousand times too large, and still
    # an ordinary-looking float.
    monkeypatch.setattr(comptes, "debt",
                        lambda years: {y: (2387398.96e9, 0.98178) for y in years})
    monkeypatch.setattr(comptes, "gdp", lambda years: {y: 2432.207e9 for y in years})
    with pytest.raises(DebtError, match="unités ne concordent pas"):
        comptes.check_units([2019])


def test_the_correct_unit_passes_the_same_check(monkeypatch) -> None:
    """The twin: a guard that refuses the right answer too is not a guard."""
    monkeypatch.setattr(comptes, "debt",
                        lambda years: {y: (2387398.96e6, 0.98178) for y in years})
    monkeypatch.setattr(comptes, "gdp", lambda years: {y: 2432.207e9 for y in years})
    assert abs(comptes.check_units([2019])[2019]) < comptes.UNIT_TOLERANCE


# --------------------------------------------------------------------------- #
# the SFA is mandatory and names where it comes from
# --------------------------------------------------------------------------- #
def test_the_missing_sfa_is_refused_and_says_where_to_get_it() -> None:
    """A refusal that does not say what would lift it is indistinguishable from a wall."""
    with pytest.raises(DebtError, match="ajustement flux-stocks absent") as raised:
        comptes.realized_years([2019], sfa={})
    message = str(raised.value)
    assert "EDP" in message and "gov_10dd_edpt1" in message
    assert "7.301" in message, (
        "le refus doit dire que la table 7.301 ne le portera JAMAIS, sinon le prochain "
        "lecteur ira le chercher dans un millésime plus récent")


def test_a_partially_supplied_sfa_is_refused_year_by_year() -> None:
    """Supplying five years of seven and defaulting the rest is the fit this forbids."""
    with pytest.raises(DebtError, match=r"2024, 2025"):
        comptes.realized_years(YEARS, sfa={y: 0.001 for y in range(2019, 2024)})


# --------------------------------------------------------------------------- #
# against the real published files
# --------------------------------------------------------------------------- #
@needs_files
def test_the_units_reconcile_on_every_published_year() -> None:
    residuals = comptes.check_units(YEARS)
    assert set(residuals) == set(YEARS)
    assert max(abs(v) for v in residuals.values()) < comptes.UNIT_TOLERANCE


@needs_files
def test_the_covid_year_is_where_it_should_be() -> None:
    """A plausibility check with a known answer: 2020 is the deepest deficit of the span,
    by a wide margin. If the assembler were reading the wrong column or the wrong row,
    this is the first thing that would stop being true."""
    accounts = comptes.apu_account(YEARS)
    worst = min(accounts, key=lambda y: accounts[y].net_lending_eur)
    assert worst == 2020
    assert accounts[2020].net_lending_eur < -200e9


@needs_files
def test_the_interest_charge_rises_with_the_rate_shock() -> None:
    """Net interest roughly doubles between 2020 and 2025 — the shape the whole §3.2
    machinery exists to project. Shape, not level: no tolerance is being spent here."""
    accounts = comptes.apu_account(YEARS)
    assert accounts[2025].interest_net_eur > 1.8 * accounts[2020].interest_net_eur


@needs_files
def test_assembling_with_a_supplied_sfa_produces_one_realized_year_each() -> None:
    """The assembler end to end, with a PLACEHOLDER sfa that is explicitly not real.

    It proves the wiring: that r, g and the primary balance are computed and land in
    plausible ranges. It grades nothing — `backtest` still refuses an identically-zero
    series, and the real figures are the outstanding download.
    """
    placeholder = {y: 0.001 * (1 if y % 2 else -1) for y in YEARS}
    years = comptes.realized_years(YEARS, sfa=placeholder)
    assert [y.year for y in years] == YEARS
    for entry in years:
        assert 0.0 < entry.r < 0.06, f"{entry.year} : taux implicite {entry.r}"
        assert -0.10 < entry.primary_balance < 0.05
        assert 0.9 < entry.published_ratio < 1.3
    # 2020: GDP fell. If g came out positive the year alignment would be wrong.
    assert next(y for y in years if y.year == 2020).g < 0


# --------------------------------------------------------------------------- #
# the tautology: an SFA derived from the path the backtest must reproduce
# --------------------------------------------------------------------------- #
@needs_files
def test_a_derived_sfa_is_refused_by_type_not_by_value() -> None:
    """The refusal keys on PROVENANCE, which is the only thing that distinguishes it.

    A derived SFA and a published one can hold the very same number; what separates them
    is where they came from. So the guard cannot test magnitude — it tests the type, and
    `ImpliedSfa` exists solely to carry that provenance through a float.
    """
    implied = comptes.sfa_implied_by_identity(YEARS)
    assert all(isinstance(v, comptes.ImpliedSfa) for v in implied.values())
    with pytest.raises(DebtError, match="DÉRIVÉ"):
        comptes.realized_years(YEARS, sfa=implied)
    # The SAME numbers, stripped of their provenance, pass — proving the guard is about
    # where the series came from and not about what it contains.
    bare = {y: float(v) for y, v in implied.items()}
    assert len(comptes.realized_years(YEARS, sfa=bare)) == len(YEARS)


@needs_files
def test_the_derived_sfa_would_score_a_near_perfect_backtest_measuring_nothing() -> None:
    """WHY that guard exists, demonstrated rather than asserted.

    Feeding the identity an SFA computed as `Δdette − déficit` closes it by construction.
    Measured here: the modelled path tracks the published one to under 0,05 point of GDP
    across seven years — a score any honest tolerance waves through, produced by a
    backtest in which no model error could ever appear.

    This test is what stops the guard from looking like excessive caution. If someone
    removes `ImpliedSfa` on the grounds that the derivation « is just the SFA », this
    number is the answer.
    """
    from impots.dette.path import backtest

    implied = comptes.sfa_implied_by_identity(YEARS)
    assembled = comptes.realized_years(YEARS, sfa={y: float(implied[y]) for y in YEARS})
    points = backtest(comptes.opening_ratio(YEARS[0]), assembled, tolerance=10.0)
    worst = max(abs(p.residual) for p in points)
    assert worst < 0.0005, (
        f"résidu maximal {worst * 100:.4f} pt — attendu quasi nul PAR CONSTRUCTION ; "
        f"s'il ne l'est plus, la dérivation a changé et l'argument de la garde avec elle")
    assert all(p.within for p in points)


# --------------------------------------------------------------------------- #
# §6.1 — le backtest noté, tolérance préenregistrée en c6c5db4 (D-167)
# --------------------------------------------------------------------------- #
FENETRE = list(range(2021, 2026))

#: ±0,10 point de PIB. Préenregistrée PAR COMMIT avant le premier résidu : la valeur vit
#: dans l'historique git, et l'élargir après coup y laisse une trace qu'une relecture du
#: fichier ne peut pas cacher (`verify_tolerance_unchanged`, même principe).
TOLERANCE_61 = 0.0010


@needs_files
def test_the_debt_identity_reproduces_the_published_path_2021_2025() -> None:
    """§6.1. Cinq années, un seul millésime, SFA reconstruit depuis ses composantes.

    La fenêtre s'arrête en 2021 vers le bas et le DIT : les notifications qui portent
    2019-2020 sont sur un autre millésime, où le déficit 2019 diffère de 16,5 md€ et où
    l'ajustement de cette année CHANGE DE SIGNE (D-167).
    """
    from impots.dette.path import backtest

    sfa = comptes.sfa_publie(FENETRE)
    annees = comptes.realized_years(FENETRE, sfa=sfa)
    points = backtest(comptes.opening_ratio(FENETRE[0]), annees, tolerance=TOLERANCE_61)

    hors = [(p.year, round(p.residual * 100, 3)) for p in points if not p.within]
    assert not hors, f"années hors bande sans cause mécanique nommée : {hors}"
    assert len(points) == len(FENETRE)


@needs_files
def test_the_2025_residual_is_the_vintage_term_left_by_the_october_notification() -> None:
    """Ce que 2025 montre sur la notification EDP d'octobre 2026 (D-340 à D-342).

    Sur celle d'avril, le résidu de 2025 était quasi nul (+0,001 pt) parce que deux erreurs
    s'annulaient : une erreur propre de −0,031 et le report de 2024 (D-168). La
    notification d'octobre relève le SFA de 2025 de 0,019 pt et rapproche Eurostat du compte
    INSEE de 62 % : le zéro disparaît, 2025 affiche +0,020 pt, et ce qui reste de l'écart
    de millésime (+0,012) est toujours exactement l'opposé de l'erreur propre de l'année.

    Les bornes sont celles du pronostic de D-340, écrit avant le calcul : résidu 2025 dans
    [+0,015 ; +0,025] pt, erreur propre et terme de millésime de somme nulle à 0,0002 pt.
    Ce test fige un CONSTAT de ce millésime. S'il casse, c'est que le millésime a changé :
    on le renomme sur une D-entrée neuve, on ne l'élargit pas.
    """
    from impots.dette.path import backtest

    sfa = comptes.sfa_publie(FENETRE)
    annees = comptes.realized_years(FENETRE, sfa=sfa)
    points = backtest(comptes.opening_ratio(FENETRE[0]), annees, tolerance=TOLERANCE_61)

    par_an = {p.year: p for p in points}
    a2025 = next(a for a in annees if a.year == 2025)
    facteur = (1 + a2025.r) / (1 + a2025.g)
    epsilon = par_an[2025].residual - par_an[2024].residual * facteur

    # Le terme de millésime, mesuré INDÉPENDAMMENT : SFA implicite côté INSEE contre SFA
    # publié côté Eurostat.
    stocks = comptes.debt([2024, 2025])
    implicite = ((stocks[2025][0] - stocks[2024][0])
                 + comptes.apu_account([2025])[2025].net_lending_eur)
    pib = comptes.gdp([2025])[2025]
    millesime = implicite / pib - sfa[2025]

    assert 0.00015 <= par_an[2025].residual <= 0.00025, (
        f"résidu 2025 {par_an[2025].residual * 100:+.4f} pt, hors du pronostic de D-340")
    assert epsilon < 0 < millesime, "erreur propre négative, terme de millésime positif"
    assert abs(epsilon + millesime) < 0.000002, (
        f"l'erreur propre de 2025 ({epsilon:+.6f}) doit être l'opposé du terme de "
        f"millésime mesuré à part ({millesime:+.6f}) — sinon la cause nommée dans D-167 "
        f"n'est pas celle qui agit")


@needs_files
def test_residuals_damp_rather_than_accumulate_because_growth_exceeds_the_rate() -> None:
    """Pourquoi les résidus ne s'empilent pas sur cinq ans.

    Le report est multiplié par (1+r)/(1+g) à chaque pas. Sur cette fenêtre g dépasse r
    partout, donc le facteur reste sous 1 et une erreur passée DÉCROÎT. Ce n'est pas une
    propriété du modèle, c'est l'arithmétique de la boule de neige — et elle cesse de
    jouer dès que r rattrape g, ce que 2025 (facteur 0,9998) montre déjà.
    """
    sfa = comptes.sfa_publie(FENETRE)
    annees = comptes.realized_years(FENETRE, sfa=sfa)
    facteurs = {a.year: (1 + a.r) / (1 + a.g) for a in annees}
    assert all(f < 1.0 for f in facteurs.values()), facteurs
    assert facteurs[2025] > 0.99, (
        "2025 approche 1 : la croissance nominale ne dépasse presque plus le taux "
        "implicite, et l'amortissement des erreurs passées disparaît avec elle")
