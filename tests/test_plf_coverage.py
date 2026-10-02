"""The PLF coverage triage, checked against the code it describes.

A triage is a PRE-REGISTRATION: it will be read in October under time pressure and
believed. So every claim it makes about the codebase is verified here rather than
asserted — a knob it names must exist verbatim in the wire model, and a parameter path it
names must resolve in the tree. A document that drifts from the code is worse than none.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from impots.api.schemas import ReformSpec
from impots.entreprises.reforms import FirmReformSpec
from impots.plf_coverage import (
    ARTICLES,
    BUCKETS,
    engine_ready_but_blind,
    priceable_today,
    share_priceable,
)


def test_every_fiscal_article_is_classified_exactly_once():
    """29 articles in « B – Mesures fiscales », each in exactly one bucket."""
    assert len(ARTICLES) == 29
    assert {a.numero for a in ARTICLES} == set(range(2, 31))
    for article in ARTICLES:
        assert article.bucket in BUCKETS


@pytest.mark.parametrize("article", ARTICLES, ids=lambda a: f"art{a.numero}")
def test_every_knob_the_triage_names_exists(article):
    """Fails when a knob is renamed or removed and the triage is not updated.

    The triage promises publication week that these knobs express these articles. A
    promise pointing at a knob that no longer exists is discovered on the day.
    """
    from impots.api.schemas import ReformSpec
    from impots.entreprises.reforms import FirmReformSpec

    known = set(ReformSpec.model_fields) | set(FirmReformSpec.model_fields)
    for knob in article.knobs:
        assert knob in known, f"art. {article.numero} nomme « {knob} », qui n'existe pas"


@pytest.mark.parametrize("article", ARTICLES, ids=lambda a: f"art{a.numero}")
def test_every_parameter_path_the_triage_names_resolves(article):
    """A `small_knob` claim says publication week is wiring, not modelling. That is only
    true if the parameter is actually there — checked at 2026-01-01, the year priced."""
    from impots.engine.system import baseline
    from impots.parameters import exists_at

    parameters = baseline().parameters
    for path in article.paths:
        assert exists_at(parameters, path, "2026-01-01"), (
            f"art. {article.numero} : « {'.'.join(path)} » ne résout pas")


def test_a_priceable_article_names_at_least_one_knob():
    """Fails on an article promised as priceable with nothing named to price it with."""
    for article in ARTICLES:
        if article.bucket == "priceable_now":
            assert article.knobs, f"art. {article.numero} : chiffrable avec quoi ?"


def test_a_refusal_states_which_of_data_structure_or_scope():
    """The refusal list is half the deliverable, and a refusal without a stated kind is
    an excuse. Fails if one loses its reason."""
    for article in ARTICLES:
        if article.bucket == "not_priceable":
            reason = article.raison.lower()
            assert any(word in reason for word in ("data", "structure", "scope")), (
                f"art. {article.numero} refusé sans dire de quel genre")


def test_a_population_blind_article_names_what_would_unlock_it():
    """A refusal whose cause is DATA must name the door.

    Fails if an article lands in `population_blind` with no `unlock` — the dataclass
    refuses to construct then, so this pins the rule at the collection level too. A door
    far away is still a door, and the document must not read as a permanent refusal.
    """
    from impots.plf_coverage import ARTICLES as A

    blind = [a for a in A if a.bucket == "population_blind"]
    assert blind
    for article in blind:
        assert article.unlock, f"art. {article.numero} : aveugle sans porte nommée"


def test_the_unlock_names_microdata_where_that_is_the_unlock():
    """The brief's rule: the triage keeps naming real income microdata as the unlock for
    the capital-income refusals, neither promising it nor pretending it is gone."""
    from impots.plf_coverage import ARTICLES as A

    cdhr = next(a for a in A if a.numero == 2)
    assert "microdata" in cdhr.unlock and "D-096" in cdhr.unlock


def test_the_cdhr_unlock_records_that_erfs_was_tried_and_did_not_open_it():
    """D-141. The previous assertion could not have caught the lie it was guarding.

    D-096 named « des microdonnées de revenus (ERFS) » as the unlock. The ERFS 2022 FPR
    was then obtained and the gate re-run, and it did NOT open: the CDHR's population
    lives entirely in the last centile, which a household survey undercounts by its
    SAMPLING DESIGN rather than by its granularity. Leaving ERFS named as the key would
    send the next reader to fetch a key already known not to turn.

    The old test asserted only that « microdata » and « D-096 » appear — both of which
    stayed true the whole time the clause was false. This one names the implementation
    that would make it fail: an unlock reverting to « real income microdata (ERFS ... ) »
    passes the old assertions and fails these.
    """
    from impots.plf_coverage import ARTICLES as A

    cdhr = next(a for a in A if a.numero == 2)
    assert "D-141" in cdhr.unlock, (
        "la clause doit dater le ré-examen : sans lui, « microdonnées » se relit comme "
        "une porte jamais essayée")
    assert "POTE" in cdhr.unlock or "échantillon lourd" in cdhr.unlock, (
        "une clause d'unlock doit dire CE QUI ouvrirait la porte ; « des microdonnées » "
        "ne le dit plus, puisque des microdonnées ont été essayées sans succès")
    assert "PAS l'ERFS" in cdhr.unlock, (
        "l'ERFS doit être nommée comme essayée-et-insuffisante, sinon le prochain "
        "lecteur refera le chemin")


def test_both_headlines_are_computed_and_disagree():
    """THE reason the brief asked for two.

    By article count the tool covers a few per cent; by quantified yield, far more,
    because the one priceable article is the largest quantified figure in the annex.
    Publishing either alone misleads — one flatters, the other damns. Fails if a headline
    becomes a typed constant or if the yield table loses the CEBGE.
    """
    from impots.plf_coverage import (
        priceable_yield_meur,
        quantified_yield_meur,
        share_of_yield,
        share_priceable,
    )

    assert share_priceable() < 0.10
    assert share_of_yield() > 0.30
    assert share_of_yield() > 5 * share_priceable()
    assert priceable_yield_meur() == 4_000.0
    assert quantified_yield_meur() > priceable_yield_meur()


def test_ambiguous_yields_are_excluded_not_guessed():
    """Article 2's cell says 1,5 under a « millions » header whose own method note says
    1,5 Md€ — a factor of a thousand the document does not settle. Fails if it is given a
    number anyway, which would move the denominator by 1.5 bn on a guess."""
    from impots.plf_coverage import YIELD_AMBIGUOUS, YIELDS_2026_MEUR

    assert set(YIELDS_2026_MEUR) & set(YIELD_AMBIGUOUS) == set()
    assert 2 in YIELD_AMBIGUOUS and 2 not in YIELDS_2026_MEUR


def test_engine_ready_and_population_blind_is_its_own_category():
    """THE distinction the three buckets cannot carry.

    An article whose parameters exist but whose taxpayers this population does not
    contain prices at a confident zero if wired. Article 2 (CDHR) is the case: its
    variable fires at -75 836 EUR on a foyer with 2 M EUR of dividends, and our
    population has no capital income at all. Fails if the flags collapse back into the
    bucket.
    """
    blind = engine_ready_but_blind()
    assert blind, "la catégorie « moteur prêt, population aveugle » a disparu"
    assert 2 in {a.numero for a in blind}
    for article in blind:
        assert article.engine_ready and not article.population_can_exercise


def test_the_headline_is_computed_not_typed():
    """The share is derived from the table, so the document cannot claim a coverage its
    own rows do not support."""
    assert priceable_today()
    assert 0.0 < share_priceable() < 0.5
    assert share_priceable() == len(priceable_today()) / len(ARTICLES)


def test_the_source_is_named_by_identifier_not_by_url():
    """The pointer rule (docs/SOURCE_POINTERS.md): an identifier travels, a URL rots."""
    from impots.plf_coverage import SOURCE

    assert "sha256" in SOURCE and "n° 1906" in SOURCE
    assert "http" not in SOURCE


def test_the_document_is_in_sync_with_the_table():
    """`docs/PLF2027_COVERAGE.md` is generated. Fails if someone edits the .md by hand.

    A generated document edited in place is the worst of both: it looks authoritative and
    the next regeneration silently discards the edit. Edit `src/impots/plf_coverage.py`
    and run `scripts/write_plf_coverage.py`.
    """
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    from write_plf_coverage import OUT, build

    assert OUT.read_text(encoding="utf-8") == build(), (
        "docs/PLF2027_COVERAGE.md diverge de la table — "
        "relancer scripts/write_plf_coverage.py")


# --------------------------------------------------------------------------- #
# Le PLF 2027 réel — triage du jour de parution (2026-10-02)
# --------------------------------------------------------------------------- #
def test_every_2027_fiscal_article_is_classified_exactly_once():
    """Les articles 1 à 33 du texte n° 3210 : un découpage qui en perd un (le 23, avant
    la correction du découpeur) ne doit pas pouvoir passer pour un triage complet."""
    from impots.plf_coverage import ARTICLES_2027, BUCKETS

    assert [a.numero for a in ARTICLES_2027] == list(range(1, 34))
    for article in ARTICLES_2027:
        assert article.bucket in BUCKETS
        assert article.decision in ("septembre", "neuve"), article.numero


def test_a_september_decision_names_a_september_category():
    """« Catégorie de septembre » est une affirmation vérifiable : la catégorie doit
    exister, à la lettre, dans le triage préenregistré. Sinon c'est une décision du jour
    habillée en décision d'avance, ce que le runbook interdit de laisser passer."""
    from impots.plf_coverage import ARTICLES, ARTICLES_2027

    septembre = {a.categorie for a in ARTICLES}
    for article in ARTICLES_2027:
        if article.decision == "septembre":
            assert article.categorie in septembre, (article.numero, article.categorie)


def test_a_new_2027_decision_is_dated_the_day_it_was_taken():
    from impots.plf_coverage import ARTICLES_2027, DATE_TRIAGE_2027

    assert DATE_TRIAGE_2027 == "2026-10-02"
    neuves = [a for a in ARTICLES_2027 if a.decision == "neuve"]
    assert neuves, "un texte réel porte forcément des catégories que septembre n'a pas vues"


@pytest.mark.parametrize("numero", range(1, 34))
def test_every_2027_knob_exists(numero):
    from impots.plf_coverage import ARTICLES_2027

    article = ARTICLES_2027[numero - 1]
    known = set(ReformSpec.model_fields) | set(FirmReformSpec.model_fields)
    for knob in article.knobs:
        assert knob in known, f"art. {numero} nomme un bouton inexistant : {knob}"


def test_every_priceable_2027_article_carries_a_reform_that_validates():
    """Un article déclaré chiffrable doit pointer une réforme qui se lit avec le bon modèle
    et qui touche exactement les boutons que la table annonce."""
    import json

    from impots.plf_coverage import ARTICLES_2027

    root = Path(__file__).resolve().parents[1]
    chiffrables = [a for a in ARTICLES_2027 if a.bucket == "priceable_now"]
    assert [a.numero for a in chiffrables] == [2, 3, 15]
    for article in chiffrables:
        model = FirmReformSpec if article.chaine == "entreprises" else ReformSpec
        payload = json.loads((root / article.reforme).read_text(encoding="utf-8"))
        spec = model.model_validate(payload)
        assert sorted(spec.model_dump(exclude_none=True)) == sorted(article.knobs)


def test_a_priceable_household_article_has_its_dated_scenario():
    """Le pas 4 du runbook enregistre un scénario avant de chiffrer : le scénario daté
    porte la réforme même que la table pointe."""
    import json

    from impots import scenarios
    from impots.plf_coverage import ARTICLES_2027

    root = Path(__file__).resolve().parents[1]
    for article in ARTICLES_2027:
        if article.bucket != "priceable_now" or article.chaine != "ménages":
            continue
        scenario = scenarios.load(f"plf2027_art_{article.numero}")
        payload = json.loads((root / article.reforme).read_text(encoding="utf-8"))
        assert scenario.reform == ReformSpec.model_validate(payload)
        assert scenario.year == 2026, "mesures d'IR sur les revenus 2026 (art. 33, 2°)"


def test_a_2027_refusal_states_which_of_data_structure_or_scope():
    from impots.plf_coverage import ARTICLES_2027

    for article in ARTICLES_2027:
        if article.bucket == "not_priceable":
            assert article.raison.split(".")[0].split(" ")[0] in (
                "data", "structure", "scope"), (article.numero, article.raison[:40])
