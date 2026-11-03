"""F3 M1 — the two references a multi-year chiffrage has to choose between.

**Read `docs/M0_TRAJECTORIES.md` first.** The gate measured the thing this module exists
to fix: the dated tree encodes the future on two parameters out of sixty-two, and the IR
barème is FROZEN from 2026 — 2026, 2027 and 2028 all carry 2025's thresholds. So:

    Pricing a barème freeze against current law returns exactly 0,00 EUR,
    because current law IS the freeze.

That is the PLF-2026-article-9 shape at phase scale (D-095): a change priced against a
baseline that already contains it. The answer there was the backtest suite's `mirror`
field; the answer here has to be bigger, because the thing already in the baseline is not
one measure but the absence of an entire policy.

TWO REFERENCES, AND EVERY FIGURE NAMES ITS OWN.

* `reconduit` — current law extended. This is the LEGAL reference: nobody has voted an
  indexation for 2028, so a taxpayer's 2028 liability under current law really is computed
  on 2025's thresholds. A chiffrage against it answers «what does this measure change
  relative to the law as it stands».
* `indexe` — the same law with the barème, the décote and the plafond du quotient familial
  indexed on a DECLARED price hypothesis. A chiffrage against it answers «what does this
  measure change relative to a law that had kept pace with prices».

**Both are true and they answer different questions.** The freeze costs households a great
deal against `indexe` and nothing at all against `reconduit`. A tool that silently picked
one would be answering a question the reader did not ask, so nothing here has a default:
`reference` is required, and `indexe` additionally requires the hypothesis and its source.

**THE HYPOTHESIS IS SUPPLIED, NEVER FORECAST.** Phase 4's refusals bind: this project does
not predict inflation and will not start. `Indexation` carries a rate the caller states and
a source they name — «the LFI's own indexation assumption», «INSEE's latest observed
index», «a round 2 % chosen to be legible». Pricing «if prices rise by X» is arithmetic;
choosing X is not ours, and the module refuses to choose it.

WHAT M1 DOES NOT DO. It does not uprate the population — that is M2, and until it exists a
trajectory prices future LAW on a 2024 population, which overstates nothing and understates
nothing in particular but is not the same thing as a 2028 chiffrage. `Trajectory.caveat`
says so on every result rather than leaving it to a reader who may not know.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any

#: The last year the IR barème was actually indexed. Measured, not assumed: read through
#: `read_ir_parameters`, the thresholds move 2024 -> 2025 and then stand still, so 2026,
#: 2027 and 2028 all carry 2025's values. `test_the_barème_is_frozen_from_2026` pins it,
#: and it is the fact the whole module rests on — if a future LFI indexes again, that test
#: fails and this constant moves, which is the intended behaviour rather than a nuisance.
LAST_INDEXED_YEAR = 2025

#: The two references. Written out rather than derived, and `reference` is required
#: everywhere: a default would answer a question the caller did not ask.
REFERENCES = ("reconduit", "indexe")

#: What `indexe` moves. The IR parameters whose indexation is the «stealth tax» when it
#: does not happen — thresholds, décote, and the ceiling per half-part. NOT an exhaustive
#: list of everything a real indexation touches: the 10 % déduction forfaitaire floors and
#: ceilings, the pension abattement and several specific QF caps also move in a real
#: indexation article and are not exposed as knobs here. So `indexe` is a LOWER BOUND on
#: what indexation would cost, and `Trajectory.caveat` says so.
INDEXED_KNOBS = ("ir_bareme", "decote_seuil_celib", "decote_seuil_couple",
                 "plafond_qf_demi_part")


class TrajectoryError(RuntimeError):
    """A trajectory was asked for in a way that would produce a misleading figure."""


@dataclass(frozen=True)
class Indexation:
    """A price hypothesis, declared. Never forecast, never defaulted.

    `rate` is the annual uprating applied from `LAST_INDEXED_YEAR` onward — 0.02 for 2 %
    a year. `source` says where it comes from and is mandatory for the same reason a
    scenario's source is: a number whose origin is unstated cannot be argued with.
    """

    rate: float
    source: str

    def __post_init__(self) -> None:
        if not self.source.strip():
            raise TrajectoryError(
                "une hypothèse d'indexation sans source est un chiffre sorti de nulle "
                "part. Dire d'où il vient — l'hypothèse d'une LFI, un indice INSEE "
                "constaté, ou « 2 % ronds, choisis pour être lisibles » — est ce qui "
                "permet d'en discuter. Ce projet ne prévoit pas l'inflation et ne "
                "commencera pas : il chiffre « si les prix montent de X ».")
        if not -0.5 < self.rate < 0.5:
            raise TrajectoryError(
                f"taux d'indexation {self.rate} hors de ]-50 %, +50 %[ : ce n'est "
                f"probablement pas un taux annuel")

    def factor(self, year: int) -> float:
        """Cumulative uprating from the last legislated indexation to `year`."""
        if year <= LAST_INDEXED_YEAR:
            return 1.0
        return (1.0 + self.rate) ** (year - LAST_INDEXED_YEAR)


@dataclass(frozen=True)
class Trajectory:
    """One year of a multi-year chiffrage, and what it is an answer to."""

    year: int
    reference: str
    mechanical_eur: float
    indexation: Indexation | None
    caveat: str

    def line(self) -> str:
        base = (f"{self.year} · référence **{self.reference}** · "
                f"{self.mechanical_eur / 1e9:+.3f} md€")
        if self.indexation is not None:
            base += (f" · indexation {self.indexation.rate:.1%} "
                     f"({self.indexation.source})")
        return base


def indexation_spec(year: int, indexation: Indexation,
                    law: dict[str, Any]) -> dict[str, Any]:
    """The ReformSpec that turns current law into indexed law for `year`.

    Returned as a spec rather than applied, so the caller can see exactly what `indexe`
    moves — and so the indexed reference goes through the same whitelisted-knob path as
    every other reform instead of writing the parameter tree directly.
    """
    factor = indexation.factor(year)
    spec: dict[str, Any] = {
        "ir_bareme": [{"threshold": round(b["threshold"] * factor, 2),
                       "rate": b["rate"]} for b in law["bareme"]],
        "decote_seuil_celib": round(law["decote"]["seuil_celib"] * factor, 2),
        "decote_seuil_couple": round(law["decote"]["seuil_couple"] * factor, 2),
        "plafond_qf_demi_part": round(law["plafond_qf_demi_part"] * factor, 2),
    }
    return spec


def require_reference(reference: str) -> None:
    """Refuse anything but the two named references, and refuse a default.

    An ALLOWLIST, for the reason D-094 established: a denylist refuses what it
    recognises, and the caller who most needs refusing is the one who typed the name
    slightly wrong. A misspelt reference silently answering «reconduit» would publish a
    zero for a freeze and call it a result.
    """
    if reference not in REFERENCES:
        raise TrajectoryError(
            f"référence « {reference} » inconnue. Les deux références sont "
            f"{list(REFERENCES)}, et il n'y a pas de défaut : « reconduit » et "
            f"« indexe » répondent à deux questions différentes, toutes deux légitimes, "
            f"et choisir à la place de l'appelant répondrait à une question qu'il n'a "
            f"pas posée. Un gel de barème coûte cher contre « indexe » et rien du tout "
            f"contre « reconduit ».")


def caveat_for(reference: str, year: int, indexation: Indexation | None) -> str:
    """The sentence that must travel with every trajectory figure."""
    parts = []
    if reference == "reconduit":
        parts.append(
            "Référence « reconduit » : le droit courant prolongé. C'est la référence "
            "LÉGALE — personne n'a voté d'indexation au-delà de "
            f"{LAST_INDEXED_YEAR}, et le barème de {year} est celui de "
            f"{LAST_INDEXED_YEAR}. Un gel de barème chiffré contre elle rend zéro, "
            "et ce zéro est juste : il n'y a rien à geler qui ne le soit déjà.")
    else:
        assert indexation is not None
        parts.append(
            f"Référence « indexe » : le droit courant dont le barème, la décote et le "
            f"plafond par demi-part sont indexés de {indexation.rate:.1%} par an depuis "
            f"{LAST_INDEXED_YEAR} — hypothèse déclarée, non prévue "
            f"({indexation.source}).")
        parts.append(
            "C'est une BORNE INFÉRIEURE de ce qu'une vraie indexation coûterait : une "
            "loi d'indexation déplace aussi les planchers et plafonds de la déduction "
            "forfaitaire de 10 %, l'abattement sur les pensions et plusieurs plafonds "
            "spécifiques de quotient familial, qui ne sont pas exposés ici.")
    parts.append(
        "La population n'est PAS vieillie : ce chiffre applique le droit d'une année "
        "future à une population 2024. C'est le milestone M2 et il n'est pas fait.")
    return " ".join(parts)


def price(
    year: int,
    reference: str,
    *,
    reform: dict[str, Any] | None,
    law: dict[str, Any],
    run: Any,
    indexation: Indexation | None = None,
) -> Trajectory:
    """Price one reform in one year against one named reference.

    `run` maps a reform dict (or None) to a mechanical cost in euros — injected so this
    module stays testable without a population, and so the trajectory logic is not
    entangled with the engine.

    Against `indexe` the cost is the DIFFERENCE between two reforms — indexed-plus-reform
    and indexed-alone — because the indexed reference is itself expressed as a reform.
    Getting that subtraction wrong would silently fold the whole cost of indexation into
    every measure priced against it, which is a large number to hide.
    """
    require_reference(reference)
    if reference == "indexe" and indexation is None:
        raise TrajectoryError(
            "la référence « indexe » exige une hypothèse d'indexation déclarée : "
            "indexer sur un taux implicite reviendrait à prévoir l'inflation en "
            "silence.")

    if reference == "reconduit":
        cost = float(run(reform))
    else:
        assert indexation is not None
        indexed = indexation_spec(year, indexation, law)
        alone = float(run(indexed))
        combined = float(run({**indexed, **(reform or {})} if reform else indexed))
        cost = combined - alone

    return Trajectory(year=year, reference=reference, mechanical_eur=cost,
                      indexation=indexation if reference == "indexe" else None,
                      caveat=caveat_for(reference, year, indexation))


def sweep(
    years: range,
    reference: str,
    *,
    reform: dict[str, Any] | None,
    law_for: Any,
    run_for: Any,
    indexation: Indexation | None = None,
) -> list[Trajectory]:
    """The same reform across several years. Points, never a curve.

    A smooth line drawn through annual points suggests intermediate values that were not
    computed, and the ones that were computed are the only ones this model has.
    """
    require_reference(reference)
    return [price(year, reference, reform=reform, law=law_for(year),
                  run=run_for(year), indexation=indexation) for year in years]


# --------------------------------------------------------------------------- #
# M3 — the knobs gain a time dimension, and every year says what it rests on
# --------------------------------------------------------------------------- #

#: The two sides, and how far the parameter tree has actually been legislated on each.
#:
#: MEASURED, NOT DECLARED. `last_legislated_year` walks the known parameter paths year by
#: year and reports the last year at which any value CHANGES — including a change to
#: absent, which is how the tree encodes the CVAE's abolition. Measured today: households
#: 2027, firms 2030. Hard-coding those would make the module lie the first time an LFI
#: legislates further out; deriving them means the classification updates itself and the
#: pinning test fails loudly instead.
SIDES = ("menages", "entreprises")

#: What a year's figure rests on.
#:
#: `legislated` — a legislator has set the parameters for this year. The tree's value is
#: the law.
#: `reconducted` — no legislator has spoken about this year yet, so the tree carries the
#: last value forward. That is legally correct absent new legislation AND very likely to
#: be superseded, which is exactly why the choice of reference decides the answer.
BASES = ("legislated", "reconducted")


def _paths_for(side: str) -> dict[str, tuple[str, ...]]:
    if side == "menages":
        from impots.engine.reforms import SCALAR_KNOBS

        return dict(SCALAR_KNOBS)
    import pathlib
    import re

    source = (pathlib.Path(__file__).resolve().parents[2]
              / "src" / "impots" / "entreprises" / "reforms.py").read_text(encoding="utf-8")
    return {m[0]: tuple(x.strip().strip("\"'") for x in m[1].split(","))
            for m in re.findall(r'"(\w+)":\s*\(([^)]*)\)', source)}


def _parameters_for(side: str) -> Any:
    if side == "menages":
        from impots.engine.system import baseline

        return baseline().parameters
    from impots.entreprises.system import baseline as firm_baseline

    return firm_baseline().parameters


@lru_cache(maxsize=8)
def last_legislated_year(side: str, horizon: int = 2032) -> int:
    """The last year at which any known parameter on `side` changes value.

    Cached: the walk reads 52 household paths across nine years, each read building a
    parameter node, and `basis_for` calls it once per year of every sweep. Uncached it
    dominated the runtime of a trajectory that does no engine work at all. The tree does
    not change within a process, so the cache cannot go stale.

    A change to ABSENT counts: the CVAE's parameters cease to exist in 2030, and that
    disappearance is the abolition, not a gap. Treating it as a change is what makes the
    firm side legislated through 2030 rather than through 2029.
    """
    if side not in SIDES:
        raise TrajectoryError(f"côté inconnu : {side}. Les côtés sont {list(SIDES)}.")
    parameters = _parameters_for(side)
    years = list(range(2024, horizon + 1))
    last = years[0]
    for path in _paths_for(side).values():
        previous, seen = None, False
        for year in years:
            try:
                node = parameters(f"{year}-01-01")
                for part in path:
                    if part:
                        node = getattr(node, part)
                value: float | None = float(node)
            except Exception:
                value = None
            if seen and value != previous:
                last = max(last, year)
            previous, seen = value, True
    return last


def basis_for(side: str, year: int) -> str:
    """Whether `year` on `side` rests on legislation or on reconduction."""
    return "legislated" if year <= last_legislated_year(side) else "reconducted"


def basis_note(side: str, year: int, reference: str) -> str:
    """What must be said about a year, given what it rests on and which reference.

    Two cases the spec names, and a third that fell out of writing it.
    """
    basis = basis_for(side, year)
    last = last_legislated_year(side)
    if basis == "legislated" and reference == "reconduit":
        return (f"{year} est LÉGIFÉRÉ côté {side} : l'arbre porte les paramètres qu'un "
                f"législateur a fixés pour cette année (dernier changement en {last}). "
                f"Ce chiffre ne dépend d'aucune hypothèse.")
    if basis == "legislated" and reference == "indexe":
        # The third case, and it is not the one the spec anticipated: indexing a year the
        # legislator HAS addressed does not restore a missing indexation, it overwrites a
        # voted barème with a counterfactual one. Legitimate, and a different claim.
        return (f"ATTENTION : {year} est LÉGIFÉRÉ côté {side}, et la référence « indexe » "
                f"y REMPLACE le barème voté par un barème indexé. Ce n'est pas rétablir "
                f"une indexation manquante, c'est écraser une loi existante par une "
                f"contrefactuelle. Légitime, mais ce n'est pas la même affirmation qu'au "
                f"delà de {last}.")
    return (f"{year} est RECONDUIT côté {side} : aucun législateur ne s'est encore "
            f"prononcé sur cette année (dernier changement en {last}), et l'arbre "
            f"reporte la dernière valeur. C'est juste en droit tant que rien n'est voté, "
            f"et très probablement dépassé. La référence choisie — ici « {reference} » — "
            f"décide donc du chiffre, et il faut la lire avec lui.")


@dataclass(frozen=True)
class KnobYear:
    """One knob, one year, one side: the figure and what it rests on."""

    knob: str
    side: str
    year: int
    reference: str
    basis: str
    mechanical_eur: float
    note: str

    def line(self) -> str:
        return (f"{self.year} · {self.knob} · {self.mechanical_eur / 1e9:+.3f} md€ · "
                f"{self.basis}")


def sweep_knob(
    knob: str,
    side: str,
    years: range,
    *,
    reference: str,
    run_for: Any,
    value: Any = None,
) -> list[KnobYear]:
    """Price one knob across years, each result carrying what its year rests on.

    `run_for(year)` returns a callable taking the reform dict — the same injection the
    rest of this module uses, so the time dimension is testable without a population.
    """
    require_reference(reference)
    if side not in SIDES:
        raise TrajectoryError(f"côté inconnu : {side}. Les côtés sont {list(SIDES)}.")
    out: list[KnobYear] = []
    for year in years:
        cost = float(run_for(year)({knob: value} if value is not None else None))
        out.append(KnobYear(
            knob=knob, side=side, year=year, reference=reference,
            basis=basis_for(side, year), mechanical_eur=cost,
            note=basis_note(side, year, reference)))
    return out


# --------------------------------------------------------------------------- #
# M4 (S1) — the band, year by year, with its classes kept apart
# --------------------------------------------------------------------------- #

#: The uncertainty classes a trajectory carries, and the rule that governs them: they are
#: reported SEPARATELY and never summed. The project's uncertainty grammar already keeps
#: parameter / scenario / cell-bound / composition visible; a trajectory adds one.
#:
#: `uprating` is the class this milestone names, and it is MEASURED rather than assumed:
#: its width is the frozen/aged pair from M2. On the 2028 barème freeze that pair is
#: -7,073 md€ against a frozen 2024 population and -8,339 md€ against an aged one, so the
#: uprating hypothesis is worth 1,27 md€ of spread on that reform in that year — more than
#: many behavioural bands, and invisible unless it is named.
UNCERTAINTY_CLASSES = ("uprating", "behavioural")


def max_fan_horizon_years() -> int:
    """How many years past a reform the macro fan may be shown, read from the store.

    Derived, not written: `usable_horizons` is ["1","2","3"] in `multipliers.yaml`, capped
    at three for two independent and converging reasons — §0's refusal of any horizon past
    three years, and the measurement that the long columns are determined by a
    specification choice rather than observed (employer contributions run 1,73 at LT under
    wage-setting and 0,25 under a Phillips curve, a factor of seven). Reading it from the
    store means a store that narrows narrows the trajectory too.
    """
    from impots.macro import store as store_module

    # BOTH containers: a row carrying `from_source_table` — which every multiplier does —
    # lands in `store.tables`, not `store.parameters`. Reading only the latter returned an
    # empty set and this function raised, claiming no horizon was usable when three were.
    # The fan's horizons, those the multiplier and the jobs rows both read: the multiplier
    # reaches 5 and 10 years for the loop's « lue » persistence alone (D-336).
    store = store_module.load()
    rows = [store.tables.get(key) or store.parameters.get(key)
            for key in ("multiplier_by_instrument", "employment_by_instrument")]
    readable = [{int(h) for h in getattr(row, "usable_horizons", ()) if str(h).isdigit()}
                for row in rows if row is not None]
    horizons = set.intersection(*readable) if len(readable) == len(rows) else set()
    if not horizons:
        raise TrajectoryError(
            "aucun horizon utilisable dans le magasin macro : l'éventail ne peut être "
            "montré pour aucune année, et le dire vaut mieux que de supposer trois ans.")
    return max(horizons)


@dataclass(frozen=True)
class YearUncertainty:
    """One year of a trajectory, with every class kept apart.

    There is deliberately NO combined band and no `total` property. The two classes answer
    different questions — «how much does the price hypothesis move this figure» and «how
    much might behaviour move it» — and adding them would assert an independence nobody
    has established while destroying the only information a reader can act on: which of
    the two is doing the work. On the 2028 freeze the uprating class is the larger, and a
    single merged interval would hide that.
    """

    year: int
    basis: str
    mechanical_eur: float
    """Priced on the AGED population — the headline, because it is the more complete."""
    uprating_eur: tuple[float, float]
    """(frozen, aged). The uprating class, measured rather than assumed."""
    behavioural_eur: tuple[float, float] | None
    behavioural_grade: str
    behavioural_note: str
    fan: Any | None
    fan_note: str

    @property
    def uprating_width_eur(self) -> float:
        return abs(self.uprating_eur[1] - self.uprating_eur[0])

    def line(self) -> str:
        parts = [f"{self.year} · {self.basis} · {self.mechanical_eur / 1e9:+.3f} md€",
                 f"vieillissement ±{self.uprating_width_eur / 1e9:.3f}"]
        if self.behavioural_eur is not None:
            low, high = self.behavioural_eur
            parts.append(f"comportement [{low / 1e9:+.3f} ; {high / 1e9:+.3f}] "
                         f"({self.behavioural_grade})")
        else:
            parts.append(f"comportement : {self.behavioural_grade}")
        parts.append("éventail" if self.fan is not None else "pas d'éventail")
        return " · ".join(parts)


def fan_note_for(year: int, base_year: int, horizon: int) -> tuple[bool, str]:
    """Whether the fan may be shown for `year`, and the sentence either way.

    THE HORIZON REFUSAL BINDS PER YEAR, NOT PER REFORM. A 2024-2030 trajectory is not
    «inside the horizon» or «outside» it as a whole: 2026 is two years out and 2030 is
    six, and showing one fan for the reform would silently extend a three-year multiplier
    across six. So each year is judged on its own distance.
    """
    distance = year - base_year
    if distance <= horizon:
        return True, (f"{year} est à {distance} an(s) de {base_year}, dans l'horizon "
                      f"déclaré de {horizon} ans : l'éventail est montré.")
    return False, (
        f"Pas d'éventail pour {year} : {distance} ans après {base_year}, au-delà de "
        f"l'horizon utilisable de {horizon} ans. Ce refus est POSÉ PAR ANNÉE et non par "
        f"réforme — montrer un seul éventail pour la trajectoire étendrait en silence un "
        f"multiplicateur à trois ans sur six. La borne vient du magasin macro, où les "
        f"colonnes longues se sont révélées déterminées par un choix de spécification "
        f"plutôt que mesurées.")


def year_uncertainty(
    year: int,
    *,
    basis: str,
    frozen_eur: float,
    aged_eur: float,
    behavioural: Any = None,
    base_year: int,
    horizon: int | None = None,
    fan: Any = None,
) -> YearUncertainty:
    """Assemble one year's uncertainty, classes apart.

    `behavioural` is whatever the behavioural layer returned FOR THIS YEAR — graded per
    year, not once for the reform. A reform in support in 2026 can be out of support by
    2030 as uprated incomes drift from the range the elasticities were estimated on, and
    that is measured by grading each year rather than carrying 2026's verdict forward.
    """
    horizon = max_fan_horizon_years() if horizon is None else horizon
    allowed, note = fan_note_for(year, base_year, horizon)
    if allowed and fan is None:
        # «Permitted» and «present» are different, and the note said the first while the
        # line said the second. A reader would have read «l'éventail est montré» beside
        # «pas d'éventail» and been right to distrust both.
        note = (f"{year} est dans l'horizon déclaré de {horizon} ans, mais aucun "
                f"éventail n'a été calculé pour cette année — l'étage macro n'a pas été "
                f"demandé, ou il a refusé pour une raison qui lui est propre.")
    band = None
    grade = "aucune bande"
    grade_note = ""
    if behavioural is not None:
        raw = getattr(behavioural, "band", None)
        if raw is not None:
            band = (float(raw.p10), float(raw.p90))
        grade = str(getattr(behavioural, "grade", "aucune bande"))
        grade_note = str(getattr(behavioural, "grade_reason", ""))
    return YearUncertainty(
        year=year, basis=basis, mechanical_eur=aged_eur,
        uprating_eur=(frozen_eur, aged_eur), behavioural_eur=band,
        behavioural_grade=grade, behavioural_note=grade_note,
        fan=(fan if allowed else None), fan_note=note)
