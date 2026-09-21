"""Phase 8 §4 — l'explorateur d'objectif, et les quatre façons dont il refuserait de tromper.

Les deux tests de mise à mort que §4.2 nomme sont ici sous leur nom : une cible en bande
déclenche le refus, et un cas construit à la main où l'optimum mécanique est fragile fait
RENDRE le drapeau. Les deux ont été vus échouer avant d'être verts — le premier en
élargissant la liste blanche, le second en rendant `_fragile` toujours faux.

Le refus réutilise `refuse_banded`, et §4.2 exige que la surface NEUVE — les contraintes —
reçoive ses propres tests plutôt que la confiance héritée. C'est la leçon de
l'historique denylist→allowlist réparé : une garde correcte pour un bouton n'est pas une
garde vérifiée pour dix, et l'héritage transporte la confiance sans transporter la
preuve.
"""

from __future__ import annotations

import json
import re

import pytest

from impots.explorer import (
    CONSTRAINT_CODES,
    OBJECTIVE_QUANTITIES,
    BandedObjectiveRefused,
    Bound,
    Candidate,
    Constraint,
    Evaluation,
    ExplorerError,
    SearchLog,
    ceiling_eur,
    fragile,
    frozen_only,
    plans,
    refuse_banded_constraint,
    refuse_banded_objective,
    search,
)
from impots.scenarios import BANDED_QUANTITIES, SOLVABLE_QUANTITIES

BN = 1e9


def _linear(per_knob: dict[str, float], *, frozen_bonus: float = 0.0,
            band_halfwidth: float | None = None,
            constraint_of=None):
    """Une évaluation jouet, exacte et sans population : `Σ (f − 1) × ancre`.

    Volontairement analytique. Ce fichier teste la MACHINE de recherche — l'ordre, les
    drapeaux, les refus — et un évaluateur dont on ne connaît pas la réponse à l'avance
    ne dit pas si un candidat manquant vient de la recherche ou du modèle.
    """
    def evaluate(knobs: dict[str, float]) -> Evaluation:
        aged = sum((value - 1.0) * per_knob[knob] for knob, value in knobs.items())
        band = None if band_halfwidth is None else (aged - band_halfwidth,
                                                    aged + band_halfwidth)
        return Evaluation(
            aged_eur=aged,
            frozen_eur=aged * (1.0 + frozen_bonus),
            band=band,
            band_reason="" if band is not None else "évaluateur de test, aucune preuve",
            constraints={} if constraint_of is None else constraint_of(knobs),
        )
    return evaluate


# --------------------------------------------------------------------------- #
# §4.2, tueur n° 1 — une cible en bande est refusée, par son nom
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("quantity", sorted(BANDED_QUANTITIES))
def test_a_banded_target_is_refused_and_the_message_says_why_it_is_ill_posed(
        quantity: str) -> None:
    """Le tueur que §4.2 nomme. Vu échouer en ajoutant la grandeur à OBJECTIVE_QUANTITIES.

    Le message doit porter l'argument, pas seulement le verdict : optimiser SUR un
    intervalle n'est pas une question mal répondue, c'est une question mal posée, et un
    appelant à qui on dit « refusé » sans le lui expliquer réessaiera par un autre nom.
    """
    with pytest.raises(BandedObjectiveRefused) as caught:
        refuse_banded_objective(quantity)
    message = str(caught.value)
    assert "bien posée" in message
    assert "APRÈS la recherche" in message


def test_an_unknown_target_is_refused_too_because_the_list_is_white() -> None:
    """La faute de frappe est le cas qui a le PLUS besoin d'être refusé.

    Une liste noire ne refuse que ce qu'elle reconnaît : « mechanicall » y passerait, et
    l'explorateur rendrait des candidats contre une grandeur que personne n'a définie.
    """
    with pytest.raises(BandedObjectiveRefused, match="hors liste blanche"):
        refuse_banded_objective("mechanicall")


def test_the_only_accepted_target_is_the_mechanical_one() -> None:
    """Épingle la liste blanche v1, celle que §9 attend au journal des décisions.

    Fait tomber l'élargissement silencieux : quiconque ajoute une grandeur ici doit
    passer par ce test, donc par une entrée D.
    """
    assert sorted(OBJECTIVE_QUANTITIES) == ["mechanical"]
    assert OBJECTIVE_QUANTITIES <= SOLVABLE_QUANTITIES
    refuse_banded_objective("mechanical")  # ne lève pas


def test_the_objective_refusal_delegates_rather_than_duplicating_the_rule() -> None:
    """Le message du solveur d'un bouton doit se retrouver DANS celui de l'explorateur.

    Sinon les deux surfaces divergeraient : une grandeur rendue refusable en aval
    resterait acceptable ici, et l'explorateur serait la porte de service du solveur.
    """
    banded = sorted(BANDED_QUANTITIES)[0]
    with pytest.raises(BandedObjectiveRefused) as caught:
        refuse_banded_objective(banded)
    message = str(caught.value)
    assert "étage MÉCANIQUE" in message, "le diagnostic du solveur doit être repris"
    assert "hors liste blanche" in message, "et la liste de l'explorateur, nommée"


def test_every_refusal_names_the_explorer_allowlist_so_no_branch_is_dead() -> None:
    """La garde morte trouvée en écrivant ces tests, épinglée pour de bon.

    La première version sortait par deux `raise` : le diagnostic délégué, et un « hors
    liste blanche » atteignable seulement si `refuse_banded` ACCEPTAIT la grandeur. Les
    deux listes étant égales, cette seconde branche ne pouvait pas s'exécuter — elle se
    lisait comme une garde et ne protégeait rien. Désormais il n'y a qu'une sortie, et
    tout refus nomme la liste blanche quelle que soit la route.
    """
    for quantity in [*sorted(BANDED_QUANTITIES), "mechanicall", "", "MECHANICAL"]:
        with pytest.raises(BandedObjectiveRefused) as caught:
            refuse_banded_objective(quantity)
        assert "hors liste blanche" in str(caught.value)


# --------------------------------------------------------------------------- #
# la surface NEUVE — les contraintes. Ses propres tests, pas la confiance héritée.
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("code", ["emploi", "perte_comportementale", "dette_pib_macro",
                                  "mechanical_totall", ""])
def test_a_constraint_outside_the_allowlist_is_refused_by_name(code: str) -> None:
    """La surface neuve de §4.2, testée pour elle-même.

    Une contrainte en bande ferait entrer l'optimisation sur intervalle par la porte de
    service : « le paquet qui atteint la cible SANS perte d'emploi » choisit parmi des
    intervalles exactement comme une cible en bande le ferait, et rien dans le refus de
    la CIBLE ne l'attraperait.
    """
    with pytest.raises(BandedObjectiveRefused, match="porte de service"):
        refuse_banded_constraint(code)


def test_the_constraint_allowlist_is_pinned_and_holds_the_mechanical_distinction() -> None:
    """§4.1 admet « decile 1–3 net loss ≤ 0 » parce qu'elle est MÉCANIQUE, pas parce
    qu'elle est distributionnelle. La liste est épinglée pour que la raison reste lisible."""
    assert sorted(CONSTRAINT_CODES) == [
        "decile_1_3_net_loss", "mechanical_total", "per_instrument_bound"]
    for code in CONSTRAINT_CODES:
        refuse_banded_constraint(code)  # ne lève pas


def test_a_constraint_without_a_bound_is_refused_rather_than_displayed() -> None:
    """Une contrainte qui ne contraint rien est PIRE que pas de contrainte.

    Elle s'affiche sous le tableau, ne retire aucun candidat, et se lit comme respectée.
    Vu échouer en laissant `at_most`/`at_least` tous deux à None sans garde.
    """
    with pytest.raises(ExplorerError, match="comme respectée"):
        Constraint("mechanical_total")


def test_a_constraint_whose_floor_exceeds_its_ceiling_is_refused() -> None:
    """Sinon « aucun candidat » se lirait comme « aucune solution »."""
    with pytest.raises(ExplorerError, match="aucun candidat"):
        Constraint("mechanical_total", at_most=1.0, at_least=2.0)


def test_a_declared_constraint_actually_removes_candidates() -> None:
    """Le test qui distingue « appliquée » de « acceptée ».

    Vu échouer sur la première version du module, qui vérifiait les codes de contrainte
    puis les ignorait : la recherche rendait exactement les mêmes candidats avec et sans
    contrainte, et le tableau portait quand même sa ligne « contrainte : … ».
    """
    anchors = {"a": 100 * BN}
    bounds = [Bound("a", 1.0, 1.10, 0.01)]

    def perte(knobs):
        # Une perte nette proportionnelle à la hausse — mécanique, pas une bande.
        return {"decile_1_3_net_loss": (knobs["a"] - 1.0) * 10 * BN}

    without, _ = search(target_eur=1 * BN, bounds=bounds,
                        evaluate=_linear(anchors, constraint_of=perte))
    with_limit, log = search(
        target_eur=1 * BN, bounds=bounds,
        evaluate=_linear(anchors, constraint_of=perte),
        constraints=[Constraint("decile_1_3_net_loss", at_most=0.30 * BN)])

    assert len(with_limit) < len(without)
    assert all(c.evaluation.constraints["decile_1_3_net_loss"] <= 0.30 * BN
               for c in with_limit)
    assert log.excluded, "les candidats retirés doivent être nommés, pas disparaître"
    assert "decile_1_3_net_loss" in log.excluded[0][1]


def test_an_unmeasured_constraint_is_refused_rather_than_assumed_satisfied() -> None:
    """« Pas mesuré » traité comme « respectée » est la seule des deux lectures
    indéfendable — et c'est celle qu'un `dict.get(code, 0.0)` produirait."""
    with pytest.raises(ExplorerError, match="pas mesuré"):
        search(target_eur=0.0, bounds=[Bound("a", 1.0, 1.02, 0.01)],
               evaluate=_linear({"a": 100 * BN}),
               constraints=[Constraint("decile_1_3_net_loss", at_most=0.0)])


def test_no_candidate_with_a_constraint_is_distinguishable_from_no_candidate_at_all(
) -> None:
    """Deux tableaux vides, deux réponses différentes. Le journal les sépare."""
    anchors = {"a": 100 * BN}
    bounds = [Bound("a", 1.0, 1.10, 0.01)]

    def perte(knobs):
        return {"decile_1_3_net_loss": (knobs["a"] - 1.0) * 10 * BN}

    impossible, log_c = search(
        target_eur=1 * BN, bounds=bounds, evaluate=_linear(anchors, constraint_of=perte),
        constraints=[Constraint("decile_1_3_net_loss", at_most=0.0)])
    unreachable, log_t = search(
        target_eur=50 * BN, bounds=bounds, evaluate=_linear(anchors, constraint_of=perte))

    assert impossible == () and unreachable == ()
    assert log_c.excluded and not log_t.excluded


# --------------------------------------------------------------------------- #
# §4.2, tueur n° 2 — l'optimum mécanique est fragile, et le drapeau le DIT
# --------------------------------------------------------------------------- #
def test_a_hand_built_band_fragile_optimum_renders_the_fragile_flag() -> None:
    """Le second tueur que §4.2 nomme, sur un cas construit exprès.

    La cible est +10 md€ ; l'optimum mécanique la touche tout juste ; sa bande de ±6 md€
    va donc de +4 à +16 md€ et contient l'échec. Le candidat est valide et faux à la
    fois, et c'est précisément ce que le drapeau existe pour dire.

    Vu échouer en faisant rendre `False` à `_fragile` : le candidat restait rendu, au
    même rang, sans une ligne signalant que l'intervalle des preuves contient l'échec.
    """
    candidates, _ = search(
        target_eur=10 * BN,
        bounds=[Bound("a", 1.0, 1.10, 0.01)],
        evaluate=_linear({"a": 100 * BN}, band_halfwidth=6 * BN))

    best = candidates[0]
    assert best.meets_target
    assert best.fragile
    assert "enjambe la cible" in best.fragility_reason
    assert fragile(candidates)[0] is best


def test_a_band_entirely_above_the_target_is_not_fragile_and_says_so() -> None:
    """La garde doit discriminer, sinon « fragile » ne veut rien dire.

    Le test négatif du précédent : un drapeau qui s'allume toujours est un drapeau qu'on
    apprend à ignorer.
    """
    candidates, _ = search(
        target_eur=1 * BN,
        bounds=[Bound("a", 1.10, 1.10, 0.01)],
        evaluate=_linear({"a": 100 * BN}, band_halfwidth=1 * BN))
    assert not candidates[0].fragile
    assert "au-dessus" in candidates[0].fragility_reason


def test_an_absent_band_is_not_read_as_an_absence_of_fragility() -> None:
    """Le piège exact de « banded or absent » : `fragile=False` faute de bande se lit
    comme « robuste » si la raison ne le dément pas dans la même phrase."""
    candidates, _ = search(
        target_eur=1 * BN, bounds=[Bound("a", 1.05, 1.05, 0.01)],
        evaluate=_linear({"a": 100 * BN}))
    reason = candidates[0].fragility_reason
    assert not candidates[0].fragile
    assert "absence de drapeau" in reason and "absence de mesure" in reason


def test_an_evaluation_with_neither_band_nor_reason_is_refused() -> None:
    """Une absence muette se lit comme un zéro mesuré — partout ailleurs dans ce dépôt
    aussi."""
    with pytest.raises(ExplorerError, match="zéro mesuré"):
        Evaluation(aged_eur=1.0, frozen_eur=1.0)


def test_an_inverted_band_is_refused() -> None:
    with pytest.raises(ExplorerError, match="bande inversée"):
        Evaluation(aged_eur=1.0, frozen_eur=1.0, band=(2.0, 1.0))


# --------------------------------------------------------------------------- #
# §4.3 — la règle anti-triche : gelé n'est pas un plan
# --------------------------------------------------------------------------- #
def test_a_bundle_that_only_closes_the_gap_frozen_is_not_counted_as_a_plan() -> None:
    """La règle anti-triche de §4.3, affichée ET testée.

    Le piège flatte : un gel de barème « rapporte » d'autant plus que la population
    qu'on lui oppose est figée, donc la version gelée d'un candidat est systématiquement
    la plus belle. Ici l'affichage gelé dépasse la cible de 30 % ; le vieilli ne
    l'atteint pas.

    Vu échouer en faisant lire `frozen_eur` à la place de `aged_eur` pour `meets_target`
    — tous les candidats devenaient des plans, et le tableau ne contenait plus rien qui
    permette de s'en apercevoir.
    """
    candidates, _ = search(
        target_eur=11 * BN,
        bounds=[Bound("a", 1.10, 1.10, 0.01)],
        evaluate=_linear({"a": 100 * BN}, frozen_bonus=0.30))

    only = candidates[0]
    assert only.aged_eur == pytest.approx(10 * BN)
    assert only.frozen_eur == pytest.approx(13 * BN)
    assert not only.meets_target and only.frozen_only
    assert plans(candidates) == ()
    assert frozen_only(candidates) == (only,)


def test_the_frozen_only_candidate_is_rendered_rather_than_dropped() -> None:
    """Le cacher le rendrait indétectable, et quelqu'un le retrouverait ailleurs en
    croyant l'avoir trouvé."""
    candidates, _ = search(
        target_eur=11 * BN, bounds=[Bound("a", 1.10, 1.10, 0.01)],
        evaluate=_linear({"a": 100 * BN}, frozen_bonus=0.30))
    assert len(candidates) == 1


# --------------------------------------------------------------------------- #
# §4.3 — rejouable à l'identique
# --------------------------------------------------------------------------- #
def test_two_runs_produce_the_same_order_the_same_candidates_and_the_same_digest(
) -> None:
    """« Re-runnable to identical output », rendu vérifiable.

    L'empreinte porte sur la SÉQUENCE des points visités, pas sur leur ensemble : un
    journal qui n'enregistre pas l'ordre ne prouve pas la rejouabilité, il l'affirme.
    """
    anchors = {"a": 40 * BN, "b": 30 * BN, "c": 20 * BN}
    bounds = [Bound("a", 0.98, 1.02, 0.01), Bound("b", 0.98, 1.02, 0.01),
              Bound("c", 0.98, 1.02, 0.01)]

    first, log1 = search(target_eur=0.5 * BN, bounds=bounds, evaluate=_linear(anchors))
    second, log2 = search(target_eur=0.5 * BN, bounds=bounds, evaluate=_linear(anchors))

    assert log1.order == log2.order
    assert log1.digest() == log2.digest()
    assert [c.knobs for c in first] == [c.knobs for c in second]
    assert log1.evaluations == 5 ** 3


def test_a_different_search_produces_a_different_digest() -> None:
    """Sinon l'empreinte ne prouverait rien : une constante se rejoue aussi."""
    anchors = {"a": 40 * BN}
    _, wide = search(target_eur=0.0, bounds=[Bound("a", 0.98, 1.02, 0.01)],
                     evaluate=_linear(anchors))
    _, narrow = search(target_eur=0.0, bounds=[Bound("a", 0.99, 1.01, 0.01)],
                       evaluate=_linear(anchors))
    assert wide.digest() != narrow.digest()


def test_the_digest_is_over_the_sequence_and_not_merely_the_set() -> None:
    """Le tueur du journal, isolé.

    Les deux journaux visitent les MÊMES points et relèvent les MÊMES valeurs ; seul
    l'ordre diffère. Écrit d'abord comme « deux recherches de tailles différentes », ce
    qui laissait passer un journal réduit à son nombre de points : les longueurs
    différaient déjà. Ici elles sont égales, et `values_aged` aussi — l'ordre est la
    seule chose qui reste pour séparer les deux empreintes.
    """
    premier = SearchLog(seed=0)
    premier.record({"k": 1.0}, 5.0)
    premier.record({"k": 2.0}, 5.0)
    second = SearchLog(seed=0)
    second.record({"k": 2.0}, 5.0)
    second.record({"k": 1.0}, 5.0)

    assert premier.values_aged == second.values_aged
    assert premier.evaluations == second.evaluations
    assert premier.digest() != second.digest()


def test_the_log_persists_with_its_digest_inside(tmp_path) -> None:
    """§4.3 demande le journal « persisted ». Écrit avec son empreinte, pour qu'un
    contradicteur recalcule plutôt qu'il fasse confiance."""
    _, log = search(target_eur=0.0, bounds=[Bound("a", 1.0, 1.02, 0.01)],
                    evaluate=_linear({"a": 40 * BN}))
    written = log.persist(tmp_path / "journal" / "search.json")
    payload = json.loads(written.read_text(encoding="utf-8"))
    assert payload["digest"] == log.digest()
    assert len(payload["order"]) == log.evaluations


def test_the_candidate_order_is_total_so_ties_cannot_reshuffle() -> None:
    """Deux paquets à égalité d'écart doivent sortir dans un ordre imposé par leurs
    valeurs, sinon « rejouable à l'identique » dépend de l'ordre de parcours d'un dict."""
    anchors = {"a": 50 * BN, "b": 50 * BN}
    bounds = [Bound("a", 1.0, 1.02, 0.01), Bound("b", 1.0, 1.02, 0.01)]
    candidates, _ = search(target_eur=1 * BN, bounds=bounds, evaluate=_linear(anchors))
    ecarts = [abs(c.aged_eur - 1 * BN) for c in candidates]
    assert ecarts == sorted(ecarts)
    tied = [c.knobs for c in candidates if abs(c.aged_eur - 1 * BN) < 1e-6]
    assert tied == sorted(tied, key=lambda k: tuple(sorted(k.items())))


# --------------------------------------------------------------------------- #
# les gardes de l'espace de recherche
# --------------------------------------------------------------------------- #
def test_an_empty_bound_list_is_refused_rather_than_returning_nothing() -> None:
    with pytest.raises(ExplorerError, match="aucune solution"):
        search(target_eur=0.0, bounds=[], evaluate=_linear({}))


def test_a_grid_larger_than_the_evaluation_budget_is_refused_not_truncated() -> None:
    """Une recherche tronquée en silence rend « pas de candidat » pour une raison qui
    n'est pas la bonne."""
    bounds = [Bound(f"k{i}", 0.98, 1.02, 0.01) for i in range(6)]
    with pytest.raises(ExplorerError, match=re.escape("points de grille")):
        search(target_eur=0.0, bounds=bounds,
               evaluate=_linear({f"k{i}": BN for i in range(6)}), max_evaluations=100)


def test_a_duplicated_knob_in_the_bounds_is_refused() -> None:
    """Le second écraserait le premier dans le paquet, et la grille explorerait une
    dimension fantôme — plus de points, pas plus d'espace."""
    with pytest.raises(ExplorerError, match="dimension fantôme"):
        search(target_eur=0.0,
               bounds=[Bound("a", 1.0, 1.01, 0.01), Bound("a", 1.0, 1.01, 0.01)],
               evaluate=_linear({"a": BN}))


@pytest.mark.parametrize(("low", "high", "step", "match"), [
    (1.0, 1.1, 0.0, "≤ 0"),
    (1.0, 1.1, -0.01, "≤ 0"),
    (1.1, 1.0, 0.01, "basse"),
])
def test_a_bound_that_cannot_be_discretized_is_refused(low, high, step, match) -> None:
    with pytest.raises(ExplorerError, match=match):
        Bound("a", low, high, step)


def test_a_degenerate_bound_is_one_point_not_zero() -> None:
    """`low == high` est un bouton tenu fixe, pas une plage vide : rendre zéro point
    ferait disparaître l'instrument du paquet sans le dire."""
    assert Bound("a", 1.0, 1.0, 0.01).grid() == (1.0,)


def test_the_grid_is_inclusive_of_both_ends() -> None:
    """±2 points au pas de 1 doit donner CINQ valeurs, les deux bornes comprises.

    Une grille exclusive à droite retirerait en silence l'extrémité de chaque plage,
    c'est-à-dire exactement le paquet le plus fort — et le plafond arithmétique calculé
    par `ceiling_eur`, lui, la compte.
    """
    assert Bound("a", 0.98, 1.02, 0.01).grid() == (0.98, 0.99, 1.0, 1.01, 1.02)


def test_the_grid_is_free_of_binary_drift() -> None:
    """L'arrondi de `grid()`, sur un cas où il porte vraiment.

    Écrit d'abord sur ±2 points au pas de 1 avec l'affirmation que `0.98 + 3 * 0.01`
    dérivait : c'est FAUX, la somme y retombe pile sur 1,01 et la mutation qui retirait
    l'arrondi restait verte. Le cas où elle dérive est ici — sans arrondi, le cinquième
    point de [0,90 ; 1,00] au pas de 1 vaut 0,9400000000000001.

    Ce n'est pas de la cosmétique : la valeur du bouton est une CLÉ de paquet et entre
    dans l'empreinte du journal. Deux routes vers le même point en feraient deux points,
    et le document publierait 0,9400000000000001 comme un taux.
    """
    assert 0.9 + 4 * 0.01 != 0.94, "le cas choisi doit vraiment dériver"
    assert Bound("a", 0.90, 1.00, 0.01).grid()[4] == 0.94


# --------------------------------------------------------------------------- #
# le plafond arithmétique — pourquoi « aucun candidat » n'accuse pas la recherche
# --------------------------------------------------------------------------- #
def test_the_arithmetic_ceiling_separates_unreachable_from_unfound() -> None:
    """±2 points sur 52 md€ d'ancres plafonnent à ~1 md€. Viser +20 md€ n'est pas une
    recherche qui échoue, c'est une cible hors d'atteinte — et les deux rendent le même
    tableau vide si personne ne calcule le plafond."""
    anchors = {"a": 40 * BN, "b": 12 * BN}
    bounds = [Bound("a", 0.98, 1.02, 0.01), Bound("b", 0.98, 1.02, 0.01)]
    plafond = ceiling_eur(bounds, anchors)
    assert plafond == pytest.approx(0.02 * 52 * BN)

    candidates, log = search(target_eur=20 * BN, bounds=bounds, evaluate=_linear(anchors))
    assert candidates == () and log.evaluations == 25
    assert plafond < 20 * BN


def test_a_ceiling_computed_on_a_subset_of_the_bounds_is_refused() -> None:
    """Il serait plus BAS que le vrai, donc déclarerait hors d'atteinte une cible qui ne
    l'est pas — un refus rassurant, la pire espèce."""
    with pytest.raises(ExplorerError, match="sous-ensemble"):
        ceiling_eur([Bound("a", 0.98, 1.02, 0.01), Bound("b", 0.98, 1.02, 0.01)],
                    {"a": 40 * BN})


# --------------------------------------------------------------------------- #
# la forme des objets rendus
# --------------------------------------------------------------------------- #
def test_a_candidate_exposes_both_displays_because_one_of_them_flatters() -> None:
    """« Cette loi, sur la France d'aujourd'hui, avec l'argent de demain » — les deux
    chiffres voyagent ensemble ou le plus beau voyage seul."""
    evaluation = Evaluation(aged_eur=1.0, frozen_eur=2.0, band=(0.0, 3.0))
    candidate = Candidate(knobs={"a": 1.0}, evaluation=evaluation, meets_target=True,
                          frozen_only=False, fragile=True)
    assert candidate.aged_eur == 1.0 and candidate.frozen_eur == 2.0


def test_the_search_log_counts_every_evaluation_including_the_excluded_ones() -> None:
    """Un candidat retiré par contrainte a COÛTÉ une évaluation. Ne pas la compter
    ferait mentir le budget d'évaluations sur le temps que la recherche a pris."""
    log = SearchLog(seed=0)
    log.record({"a": 1.0}, 1.0)
    log.exclude({"a": 1.0}, "raison")
    assert log.evaluations == 1 and len(log.excluded) == 1
