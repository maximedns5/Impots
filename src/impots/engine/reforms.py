"""ReformSpec (JSON) -> an openfisca `Reform` subclass (spec §3.4).

Only the seven whitelisted knobs below can be moved. The API never accepts a raw
parameter path: that would be an injection surface into the parameter tree, and it
would make the reform-cache key unbounded.

The barème is the delicate one. `impot_revenu.bareme_ir_depuis_1945.bareme` is a
`ParameterScale` holding 14 historical brackets, of which only the first five
resolve to a value at a 2024 instant — the rest return `None` and are dropped from
the evaluated scale. So a user barème of *n* brackets is written onto brackets
0..n-1, and brackets n..4 must be neutralised. v1 never *adds* a bracket to the
scale, which is why `ReformSpec` caps the barème at five rows.

**How the surplus brackets are neutralised, and why it is not obvious.** Building a
`MarginalRateTaxScale` from a `ParameterScale` *merges brackets that share a
threshold by summing their rates* — the behaviour cotisation scales rely on to
stack contributions. So giving each surplus bracket the top threshold *and the top
rate* does not make it a no-op: three brackets at 40 % merge into a single 120 %
bracket. A three-bracket user barème computed 158 160 € of tax on a household that
owed 58 720 €. The surplus brackets therefore take the top threshold and a rate of
**zero**, so the merge sums to exactly the top rate. `verify_bareme` re-reads the
evaluated scale afterwards and refuses to serve a reform whose scale is not
bracket-for-bracket what the user asked for.

Do not confuse the two objects: the editable node (`bareme`) exposes
`.brackets[i].rate.update(...)`; the evaluated scale (`bareme(instant)`) is a
`MarginalRateTaxScale` exposing `.thresholds` / `.rates` and has no `.brackets`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from openfisca_core import periods
from openfisca_core.reforms import Reform

if TYPE_CHECKING:  # pragma: no cover - typing only
    from impots.api.schemas import ReformSpec

PATH_BAREME = ("impot_revenu", "bareme_ir_depuis_1945", "bareme")
PATH_DECOTE = ("impot_revenu", "calcul_impot_revenu", "plaf_qf", "decote")
PATH_PLAFOND_QF_DEMI_PART = (
    "impot_revenu", "calcul_impot_revenu", "plaf_qf",
    "plafond_avantages_procures_par_demi_part", "general",
)
PATH_CSG_ACTIVITE = ("prelevements_sociaux", "contributions_sociales", "csg", "activite")

_REDUCTIONS = ("prelevements_sociaux", "reductions_cotisations_sociales")
PATH_ALLEGEMENT_GENERAL = (*_REDUCTIONS, "allegement_general", "ensemble_des_entreprises")
#: The maladie bandeau's parameters live under `alleg_gen.mmid`, NOT under the
#: `mmid` of `cotisations_securite_sociale_regime_general` — that one carries the
#: contribution rates the bandeau reduces (13 % / 7 %), not the reduction itself.
PATH_BANDEAU_MALADIE = (*_REDUCTIONS, "alleg_gen", "mmid")
PATH_BANDEAU_FAMILLE = (*_REDUCTIONS, "allegement_cotisation_allocations_familiales")

#: Every child name a bandeau plafond has carried. The node's shape CHANGES BY YEAR
#: — `plafond` before 2024, `plafond_smic_courant` **and** `plafond_smic_2023_12_31`
#: during 2024, `plafond_smic_2025_01_01` from 2025 — so a knob pinned to one child
#: silently stops working when the tree moves under it.
#:
#: Worse, in 2024 the formula takes `max(plafond_smic_courant × smic,
#: plafond_smic_2023_12_31 × smic_2023-12)`. Writing one child alone can therefore
#: change nothing at all, because the other term still wins the max. So a plafond
#: knob writes EVERY child present at the instant, and `verify_allegements` reads
#: them all back.
BANDEAU_PLAFOND_CHILDREN = (
    "plafond", "plafond_smic", "plafond_smic_courant",
    "plafond_smic_2023_12_31", "plafond_smic_2025_01_01",
)

#: Knobs that write a value to every plafond child a node has at the instant.
PLAFOND_KNOBS: dict[str, tuple[str, ...]] = {
    "bandeau_maladie_plafond": PATH_BANDEAU_MALADIE,
    "bandeau_famille_plafond": PATH_BANDEAU_FAMILLE,
}

#: knob name -> path of the scalar parameter it moves
SCALAR_KNOBS: dict[str, tuple[str, ...]] = {
    "decote_seuil_celib": (*PATH_DECOTE, "seuil_celib"),
    "decote_seuil_couple": (*PATH_DECOTE, "seuil_couple"),
    "decote_taux": (*PATH_DECOTE, "taux"),
    "plafond_qf_demi_part": PATH_PLAFOND_QF_DEMI_PART,
    "csg_activite_imposable": (*PATH_CSG_ACTIVITE, "imposable"),
    "csg_activite_deductible": (*PATH_CSG_ACTIVITE, "deductible"),
    # Employer social contributions. The channels that price these (C2, C3) were
    # written in Phase 3 against a knob that did not exist — a spec error on the
    # record (D-032). These are it.
    "allegement_general_plafond": (*PATH_ALLEGEMENT_GENERAL, "plafond"),
    "allegement_general_taux_50_et_plus": (
        *PATH_ALLEGEMENT_GENERAL, "entreprises_de_50_salaries_et_plus"),
    "allegement_general_taux_moins_de_50": (
        *PATH_ALLEGEMENT_GENERAL, "entreprises_de_moins_de_50_salaries"),
    "bandeau_maladie_taux": (*PATH_BANDEAU_MALADIE, "taux"),
    "bandeau_famille_taux": (*PATH_BANDEAU_FAMILLE, "reduction"),
}


def resolve(parameters: Any, path: tuple[str, ...]) -> Any:
    """Walk a dotted parameter path on a parameter tree."""
    node = parameters
    for part in path:
        node = getattr(node, part)
    return node


def active_bracket_count(bareme_node: Any, instant: Any) -> int:
    """How many of the scale's brackets carry a value at `instant`.

    Derived rather than hardcoded: the count is 5 for 2024, but it has changed over
    the eighty years this scale covers, and a magic `5` would silently corrupt the
    scale in any year where it is wrong.
    """
    count = 0
    for bracket in bareme_node.brackets:
        if bracket.rate.get_at_instant(instant) is None:
            break
        count += 1
    return count


def make_reform(spec: ReformSpec, year: int, name: str) -> type[Reform]:
    """Build the `Reform` subclass that applies `spec` from `{year}-01-01` onwards.

    `Reform(tbs)` clones the parameter tree, so the baseline system is untouched —
    `test_no_mutation` is the standing proof of that.
    """
    start = periods.instant(f"{year}-01-01")
    instant = f"{year}-01-01"
    reform_name = f"impots-user-reform:{name}"

    class UserReform(Reform):
        name = reform_name

        def apply(self) -> None:
            def modify(parameters: Any) -> Any:
                if spec.ir_bareme is not None:
                    _apply_bareme(parameters, spec.ir_bareme, start)
                for knob, path in SCALAR_KNOBS.items():
                    value = getattr(spec, knob)
                    if value is not None:
                        resolve(parameters, path).update(start=start, value=value)
                for knob, path in PLAFOND_KNOBS.items():
                    value = getattr(spec, knob, None)
                    if value is not None:
                        _apply_plafond(parameters, path, value, start, instant)
                return parameters

            self.modify_parameters(modifier_function=modify)

    return UserReform


def plafond_children(node: Any) -> tuple[str, ...]:
    """The plafond children a bandeau node carries **at a given instant**.

    Must be called on a node already evaluated at that instant, never on the editable
    tree: an editable `ParameterNode` answers `hasattr` for every child defined at
    *any* date, so asking it which plafonds exist in 2024 returns the 2025 one too.
    Writing to that child is not an error and produces no warning — it simply lands
    where the year's formula never looks, or, worse, where a later year's does.
    """
    return tuple(name for name in BANDEAU_PLAFOND_CHILDREN if hasattr(node, name))


def _apply_plafond(
    parameters: Any, path: tuple[str, ...], value: float, start: Any, instant: str
) -> None:
    """Set the plafonds the year's formula actually reads, and only those.

    In 2024 that is two of them, because the formula takes a max over both — writing
    one alone leaves the other winning the max and the reform doing nothing. Refuses
    outright when the node carries no plafond at that instant: a knob that writes
    nowhere is precisely the failure this design exists to prevent.
    """
    node = resolve(parameters, path)
    children = plafond_children(node(instant))
    if not children:
        raise ValueError(
            f"le nœud {'.'.join(path)} ne porte aucun plafond au {instant} "
            f"(cherché : {', '.join(BANDEAU_PLAFOND_CHILDREN)}) — l'arbre a bougé, "
            "et écrire dans le vide serait pire que refuser"
        )
    for name in children:
        getattr(node, name).update(start=start, value=value)


def _apply_bareme(parameters: Any, brackets: list[Any], start: Any) -> None:
    """Replace the active IR scale with the user's brackets, collapsing the surplus."""
    node = resolve(parameters, PATH_BAREME)
    active = active_bracket_count(node, start)
    if len(brackets) > active:
        raise ValueError(
            f"le barème fourni compte {len(brackets)} tranches, le barème légal n'en a que "
            f"{active} d'actives à cette date ; v1 ne crée pas de tranche supplémentaire"
        )
    for i, bracket in enumerate(brackets):
        node.brackets[i].rate.update(start=start, value=bracket.rate)
        node.brackets[i].threshold.update(start=start, value=bracket.threshold)
    # Neutralise the leftover active brackets. They take the top threshold and a
    # rate of ZERO: brackets sharing a threshold are merged by *summing* their
    # rates, so 0 leaves the top rate untouched while repeating the top rate would
    # multiply it. `.update` cannot write None, so a bracket cannot be deactivated
    # outright — this is the way to make one vanish.
    top = brackets[-1]
    for j in range(len(brackets), active):
        node.brackets[j].rate.update(start=start, value=0.0)
        node.brackets[j].threshold.update(start=start, value=top.threshold)


def read_ir_parameters(tax_benefit_system: Any, year: int) -> dict[str, Any]:
    """Current-law values behind the whitelisted knobs, read live (spec §4).

    The UI prefills its reform panel from this; hardcoding it here would let the
    panel drift away from the law the engine is actually applying.
    """
    instant = f"{year}-01-01"
    parameters = tax_benefit_system.parameters
    scale = resolve(parameters, PATH_BAREME)(instant)
    decote = resolve(parameters, PATH_DECOTE)
    csg = resolve(parameters, PATH_CSG_ACTIVITE)
    return {
        "year": year,
        "bareme": [
            {"threshold": float(threshold), "rate": float(rate)}
            for threshold, rate in zip(scale.thresholds, scale.rates, strict=True)
        ],
        "decote": {
            "seuil_celib": float(decote.seuil_celib(instant)),
            "seuil_couple": float(decote.seuil_couple(instant)),
            "taux": float(decote.taux(instant)),
        },
        "plafond_qf_demi_part": float(resolve(parameters, PATH_PLAFOND_QF_DEMI_PART)(instant)),
        "csg_activite": {
            "imposable": float(csg.imposable(instant)),
            "deductible": float(csg.deductible(instant)),
        },
    }


def verify_allegements(tax_benefit_system: Any, spec: ReformSpec, year: int) -> None:
    """Read back every allègement knob, and refuse a system that did not take them.

    D-007 made portable to a node whose *shape* moves. The employer-contribution
    plafonds are the sharpest case in the tree: their child names change by year, and
    during 2024 the formula takes a max over two of them — so writing one child and
    seeing no error is entirely compatible with having changed nothing. This reads
    back every child that was written, at the instant it was written for.
    """
    instant = f"{year}-01-01"
    problems: list[str] = []

    for knob in (
        "allegement_general_plafond", "allegement_general_taux_50_et_plus",
        "allegement_general_taux_moins_de_50", "bandeau_maladie_taux",
        "bandeau_famille_taux",
    ):
        wanted = getattr(spec, knob, None)
        if wanted is None:
            continue
        got = float(resolve(tax_benefit_system.parameters, SCALAR_KNOBS[knob])(instant))
        if abs(got - wanted) > 1e-9 * max(abs(wanted), 1.0):
            problems.append(f"{knob} : demandé {wanted}, appliqué {got}")

    for knob, path in PLAFOND_KNOBS.items():
        wanted = getattr(spec, knob, None)
        if wanted is None:
            continue
        node = resolve(tax_benefit_system.parameters, path)(instant)
        children = plafond_children(node)
        if not children:
            problems.append(f"{knob} : le nœud ne porte aucun plafond à {instant}")
            continue
        for name in children:
            got = float(getattr(node, name))
            if abs(got - wanted) > 1e-9 * max(abs(wanted), 1.0):
                problems.append(
                    f"{knob}.{name} : demandé {wanted}, appliqué {got} — le plafond "
                    f"effectif est un max sur ces enfants, donc un seul non appliqué "
                    f"suffit à annuler la réforme"
                )

    if problems:
        raise AssertionError(
            "les allègements appliqués ne correspondent pas à la réforme demandée — "
            + " ; ".join(problems)
        )


def verify_bareme(tax_benefit_system: Any, spec: ReformSpec, year: int) -> None:
    """Refuse to serve a reformed system whose IR scale is not what was asked for.

    The `ParameterScale` -> `MarginalRateTaxScale` conversion merges brackets that
    share a threshold by summing their rates, which once turned a 40 % top bracket
    into a 120 % one without raising anything. A wrong tax number that looks
    plausible is the worst failure this project can have, so the scale is read back
    and compared bracket for bracket.
    """
    if spec.ir_bareme is None:
        return
    scale = resolve(tax_benefit_system.parameters, PATH_BAREME)(f"{year}-01-01")
    want_thresholds = [b.threshold for b in spec.ir_bareme]
    want_rates = [b.rate for b in spec.ir_bareme]
    got_thresholds = [float(t) for t in scale.thresholds]
    got_rates = [float(r) for r in scale.rates]
    # The length check runs first and short-circuits, so `strict=False` here is
    # not papering over a mismatch — a wrong length is reported, not raised.
    ok = (
        len(got_rates) == len(want_rates)
        and all(
            abs(g - w) < 1e-9
            for g, w in zip(got_thresholds, want_thresholds, strict=False)
        )
        and all(abs(g - w) < 1e-9 for g, w in zip(got_rates, want_rates, strict=False))
    )
    if not ok:
        raise AssertionError(
            "le barème appliqué ne correspond pas au barème demandé — "
            f"demandé thresholds={want_thresholds} rates={want_rates}, "
            f"obtenu thresholds={got_thresholds} rates={got_rates}"
        )
