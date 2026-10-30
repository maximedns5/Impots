"""Named reform scenarios: save, load, compare, and solve for budget neutrality (F2).

Product surface over machinery that already exists. Nothing here adds model risk: a
scenario is a `ReformSpec` with provenance attached, a comparison runs two of them and
lays the layers side by side, and the solver root-finds one knob against the **mechanical**
cost and refuses anything else.

WHY PROVENANCE IS PART OF THE OBJECT. F2 exists so that F1 can price the PLF 2027 the week
it publishes, with chiffrages **pre-registered** — dated, committed, and graded later
against the évaluations préalables and eventually the outturns. A pre-registration is
worth exactly what its date is worth, so `created` and `source` are required fields rather
than metadata a caller may forget: a scenario that cannot say when it was written and
which article it encodes cannot serve as one.

THE SOLVER SOLVES ON THE MECHANICAL LAYER ONLY, AND REFUSES THE REST — this is the design,
not a limitation to be lifted later. The mechanical figure is a number. The behavioural
band, the macro fan, the cell-bound interval and the composition band are **intervals**,
and "the value of a knob that makes an interval equal zero" is not a well-posed question:
any knob value whose interval straddles zero answers it, and the solver would return
whichever the root-finder happened to reach first. That is a confidently-wrong number
with a plausible provenance, which is the failure mode this project fears most.

So `solve_budget_neutral` takes a mechanical pricing function and nothing else, and
`refuse_banded` names the quantities it will not accept. The refusal ships with its test.

THE ROOT-FINDER IS SECANT, NOT BISECTION, and the reason is cost rather than elegance.
Each evaluation is a population run — minutes, not milliseconds — so the difference
between 8 evaluations and 40 is the difference between a usable tool and a batch job. The
price of that choice is that secant can diverge where bisection cannot, so every call
carries an iteration cap and reports whether it converged, and a non-converged result is
returned as such rather than as its last iterate.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

SCENARIOS = Path(__file__).resolve().parents[2] / "scenarios"

#: Quantities the solver will not root-find against, and why each one is an interval
#: rather than a number. Named rather than inferred, so the refusal message can say which
#: one was asked for.
BANDED_QUANTITIES = {
    "behavioural": "la bande comportementale est un intervalle : plusieurs valeurs de "
                   "bouton l'amènent à contenir zéro, et le solveur rendrait celle que "
                   "la recherche a croisée en premier",
    "macro": "l'éventail macro est un intervalle, et par construction il ne porte "
             "jamais de point central à résoudre",
    "cell_bound": "l'incertitude de cellule est l'ensemble des réponses que la donnée "
                  "publiée autorise ; la résoudre reviendrait à choisir un placement",
    "composition": "la bande de composition est plate et sourcée sur un seul fractile "
                   "(D-085) ; s'en servir comme cible ferait passer une hypothèse pour "
                   "une mesure",
}


class ScenarioError(RuntimeError):
    """A scenario could not be built, read, or solved as asked."""


#: A scenario name is an IDENTIFIER, not a path. Letters, digits, underscore, hyphen and
#: dot — but never a separator and never a bare run of dots.
_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


def _check_name(name: str) -> None:
    """Refuse a name that would write outside the scenario directory.

    `directory / f"{name}.json"` interpolates, so `../plf2027` escapes upward and lands
    a file the listing will never show — a chiffrage that looks registered and is not.
    A name containing a separator is a mistake in every case, so it is refused rather
    than sanitised: silently renaming what someone asked for is its own surprise.

    `fullmatch`, not `match`: with `$`, `re.match` accepts a trailing newline, and
    `GET /trajectoires/gel_bareme%0A` went past this guard (D-173).
    """
    if not isinstance(name, str) or not name.strip():
        raise ScenarioError("un scénario sans nom ne peut pas être retrouvé")
    if not _NAME_PATTERN.fullmatch(name):
        raise ScenarioError(
            f"« {name} » n'est pas un nom de scénario. Un nom est un identifiant — "
            f"lettres, chiffres, «_», «-», «.», au plus 64 caractères — et jamais un "
            f"chemin : « ../plf2027 » écrirait hors du dossier des scénarios, où le "
            f"listing ne le verrait jamais, et un chiffrage invisible n'est pas "
            f"enregistré."
        )


def _scenario_path(directory: Path, name: str) -> Path:
    _check_name(name)
    return directory / f"{name}.json"


#: What a scenario may ask the population to be handed before it is priced (D-306).
IMPUTATIONS = frozenset({"ij"})


@dataclass(frozen=True)
class Scenario:
    """A named reform with the provenance a pre-registration needs."""

    name: str
    reform: Any
    """A `ReformSpec`. Typed loosely so this module does not import the API layer."""
    year: int
    created: str
    """ISO date. Required: a pre-registration is worth what its date is worth."""
    source: str
    """What this encodes — «PLF 2027, art. 3», «notre variante», «LFSS 2025 art. 6»."""
    note: str = ""
    tags: tuple[str, ...] = ()
    firm_reform: Any = None
    """A `FirmReformSpec` beside the households' reform, or None (Phase 11, D-246). Left
    out of the file when there is none, so that every scenario written before reads and
    writes back to the byte."""
    annees: tuple[int, ...] = ()
    """The years the text applies the measure, when it names them: PLF 2027 art. 15
    revives the CEBGE for 2027 alone (D-288). Empty, every year it is priced. They start
    at `year`, and are left out of the file when empty, as `firm_reform` is."""
    imputations: tuple[str, ...] = ()
    """What the population is handed before the scenario is priced, beyond what it is built
    with: « ij », the daily allowances of D-305, which a reform of their tax needs (D-306).
    Only the mechanical pricing reads it; a path that would not impute refuses the scenario
    by name rather than price it on a population without the base. Left out of the file
    when empty."""

    def __post_init__(self) -> None:
        _check_name(self.name)
        if not self.source.strip():
            raise ScenarioError(
                f"« {self.name} » n'a pas de source. Un scénario sert à préenregistrer "
                f"un chiffrage : sans l'article qu'il encode, il ne peut pas être "
                f"confronté plus tard à l'évaluation préalable ni au réalisé."
            )
        try:
            date.fromisoformat(self.created)
        except ValueError as error:
            raise ScenarioError(
                f"« {self.name} » : date « {self.created} » illisible ; un "
                f"préenregistrement non daté n'en est pas un"
            ) from error

        if self.annees and (self.annees[0] != self.year or any(
                a >= b for a, b in zip(self.annees, self.annees[1:], strict=False))):
            raise ScenarioError(
                f"« {self.name} » : années {list(self.annees)}. Elles doivent être "
                f"croissantes et sans doublon, et la première est celle du scénario "
                f"({self.year}) : la mesure commence l'année qu'il chiffre.")
        unknown = sorted(set(self.imputations) - IMPUTATIONS)
        if unknown:
            raise ScenarioError(
                f"« {self.name} » : imputations {unknown} inconnues ; le catalogue est "
                f"{sorted(IMPUTATIONS)} (D-306)")

    def reform_in(self, year: int) -> Any:
        """The reform a path prices in `year`: as written in the scenario's first year,
        and after it with each dated revaluation carried, for what a revaluation leaves
        is a level, January to December (D-301)."""
        if self.imputations:
            raise ScenarioError(
                f"« {self.name} » demande {list(self.imputations)} : seul le chiffrage "
                f"mécanique les impute, et ce chemin chiffrerait la réforme sur une "
                f"population sans son assiette (D-306)")
        if year <= self.year:
            return self.reform
        from impots.engine.reforms import carried

        return carried(self.reform)

    def applies(self, year: int) -> bool:
        """Whether the text applies the measure in `year`."""
        return not self.annees or year in self.annees

    def check_years(self, years: Any) -> None:
        """Refuse the years the text does not apply the measure in, for a command that
        prices them without reading `annees`: it would price the measure in a year the
        law does not carry it (D-288)."""
        outside = [y for y in years if self.annees and y not in self.annees]
        if outside:
            raise ScenarioError(
                f"« {self.name} » ne s'applique qu'en {list(self.annees)} : les années "
                f"{outside} chiffreraient la mesure là où le texte ne la porte pas. Seul "
                f"le chemin annuel (`impots predictif`) lit ces années.")

    def to_dict(self) -> dict[str, Any]:
        out = {
            "name": self.name,
            "year": self.year,
            "created": self.created,
            "source": self.source,
            "note": self.note,
            "tags": list(self.tags),
            "reform": self.reform.model_dump(exclude_none=True, mode="json"),
        }
        if self.firm_reform is not None and not self.firm_reform.is_empty():
            out["firm_reform"] = self.firm_reform.model_dump(exclude_none=True, mode="json")
        if self.annees:
            out["annees"] = list(self.annees)
        if self.imputations:
            out["imputations"] = list(self.imputations)
        return out

    def save(self, directory: Path | None = None) -> Path:
        """Write the scenario. Refuses to overwrite — a pre-registration is immutable.

        Editing one in place would let a chiffrage be revised after the fact while
        keeping its original date, which is precisely the thing pre-registration exists
        to prevent. A revision is a new scenario with a new name.
        """
        directory = directory or SCENARIOS
        directory.mkdir(parents=True, exist_ok=True)
        path = _scenario_path(directory, self.name)
        # Exclusive creation, not `exists()` then `write_text`: a dangling link answers
        # False to `exists()` and `write_text` follows it out of the directory. Mode "x"
        # refuses any existing entry, link included, in one system call (D-173).
        try:
            with path.open("x", encoding="utf-8") as handle:
                handle.write(json.dumps(self.to_dict(), ensure_ascii=False, indent=2) + "\n")
        except FileExistsError:
            raise ScenarioError(
                f"{path.name} existe déjà. Un scénario ne se réécrit pas : ce serait "
                f"réviser un chiffrage en gardant sa date, ce que le préenregistrement "
                f"est fait pour empêcher. Enregistrer sous un autre nom."
            ) from None
        return path


def load(name: str, directory: Path | None = None) -> Scenario:
    """Read a scenario back, rebuilding its ReformSpec through the wire model.

    Through the model rather than around it: a scenario file that no longer validates
    is a scenario whose knobs have been renamed or whose bounds have moved, and finding
    that out at load time is the point.
    """
    from impots.api.schemas import ReformSpec
    from impots.entreprises.reforms import FirmReformSpec

    directory = directory or SCENARIOS
    path = _scenario_path(directory, name)
    if path.is_symlink():
        raise ScenarioError(
            f"« {name} » est un lien symbolique : un scénario se lit dans son dossier, "
            f"pas là où un lien le fait pointer (D-173)."
        )
    if not path.exists():
        raise ScenarioError(f"{path} n'existe pas")

    # EVERY way the file can be wrong is a ScenarioError, not just an invalid knob.
    # The first version wrapped the ReformSpec validation alone, so a truncated write, a
    # merge conflict marker or a missing `created` came out as a raw JSONDecodeError or
    # KeyError — which tracebacked `impots scenario list` and 500'd GET /scenarios,
    # taking every OTHER scenario down with the one bad file. A listing that dies on its
    # third row is worse than one that names the bad row and carries on.
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ScenarioError(f"« {name} » est illisible : {error}") from error
    if not isinstance(raw, dict):
        raise ScenarioError(f"« {name} » ne contient pas un objet JSON")
    try:
        reform = ReformSpec.model_validate(raw.get("reform") or {})
        firm_reform = (FirmReformSpec.model_validate(raw["firm_reform"])
                       if raw.get("firm_reform") else None)
    except Exception as error:
        raise ScenarioError(
            f"« {name} » ne valide plus : {error}. Un bouton a été renommé ou ses bornes "
            f"ont bougé depuis l'enregistrement — le scénario doit être relu, pas forcé."
        ) from error
    # AttributeError too: a non-string `source` failed in `.strip()` and escaped,
    # 500ing GET /scenarios for every row (D-173). Tags given as one string became one
    # tag per letter.
    try:
        note = raw.get("note", "")
        tags = raw.get("tags") or ()
        if (not isinstance(note, str) or isinstance(tags, str)
                or not all(isinstance(tag, str) for tag in tags)):
            raise TypeError("la note et les étiquettes doivent être du texte")
        annees = raw.get("annees", [])
        if not isinstance(annees, list) or not all(
                type(a) is int for a in annees):  # a bool is not a year
            raise TypeError(f"annees doit être une liste d'années entières : {annees!r}")
        imputations = raw.get("imputations", [])
        if not isinstance(imputations, list) or not all(
                isinstance(i, str) for i in imputations):
            raise TypeError(f"imputations doit être une liste de noms : {imputations!r}")
        scenario = Scenario(
            name=raw["name"], reform=reform, year=int(raw["year"]),
            created=raw["created"], source=raw["source"], note=note, tags=tuple(tags),
            firm_reform=firm_reform, annees=tuple(annees), imputations=tuple(imputations),
        )
    except ScenarioError:
        raise
    except (KeyError, TypeError, ValueError, AttributeError) as error:
        raise ScenarioError(
            f"« {name} » est incomplet ou mal formé : {error!r}"
        ) from error
    # The name inside the file names every output derived from it — `fiche_{name}.md`,
    # `trajectoire_{name}.json` — so a file that disagrees with its own filename would
    # let `a.json` write `fiche_b.md` (D-173).
    if scenario.name != name:
        raise ScenarioError(
            f"« {name}.json » déclare le nom « {scenario.name} ». Un scénario porte le nom "
            f"de son fichier : sinon ses sorties sont écrites sous un autre nom que celui "
            f"qu'on a demandé."
        )
    return scenario


def available(directory: Path | None = None) -> list[str]:
    directory = directory or SCENARIOS
    if not directory.exists():
        return []
    return sorted(path.stem for path in directory.glob("*.json"))


# --------------------------------------------------------------------------- #
# A/B comparison
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class LayerComparison:
    """One layer, both scenarios, and whether the layer can be differenced at all."""

    layer: str
    a: Any
    b: Any
    comparable: bool
    """False for banded layers: two intervals do not have a difference that is a number."""
    note: str = ""


@dataclass(frozen=True)
class Comparison:
    a: Scenario
    b: Scenario
    layers: list[LayerComparison] = field(default_factory=list)

    @property
    def mechanical_gap(self) -> float | None:
        for layer in self.layers:
            if layer.layer == "mechanical" and layer.comparable:
                return float(layer.b) - float(layer.a)
        return None


def compare(a: Scenario, b: Scenario, price: Callable[[Scenario], dict[str, Any]]) -> Comparison:
    """Lay two scenarios side by side, layer by layer.

    `price` returns a mapping with at least `mechanical`, and optionally `behavioural`,
    `macro`. The banded layers are shown but marked NOT comparable: the difference of two
    intervals is an interval, and printing a single number for it would invent precision
    neither scenario has. This is the same rule the reports already apply — a category
    error that happens to typecheck is still a category error.
    """
    priced_a, priced_b = price(a), price(b)
    layers = [LayerComparison(
        layer="mechanical", a=priced_a.get("mechanical"), b=priced_b.get("mechanical"),
        comparable=priced_a.get("mechanical") is not None
        and priced_b.get("mechanical") is not None,
        note="Le seul étage où une différence est un nombre.",
    )]
    for banded in ("behavioural", "macro"):
        if banded in priced_a or banded in priced_b:
            layers.append(LayerComparison(
                layer=banded, a=priced_a.get(banded), b=priced_b.get(banded),
                comparable=False,
                note=f"Affiché côte à côte, non différencié : {BANDED_QUANTITIES[banded]}.",
            ))
    return Comparison(a=a, b=b, layers=layers)


# --------------------------------------------------------------------------- #
# The budget-neutral solver
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class SolverResult:
    knob: str
    value: float | None
    cost_at_value: float | None
    iterations: int
    converged: bool
    message: str = ""


#: Cap on evaluations. Each one is a population run, so this is minutes per call, and a
#: cap that is generous in iterations is not generous in wall-clock.
MAX_ITERATIONS = 12

#: How close to the target counts as neutral, in euros. Wide on purpose: the mechanical
#: figure itself comes off a 20 000-household subsample whose sampling noise on a national
#: total is of this order (D-074), so a tighter tolerance would be chasing the draw.
NEUTRAL_TOLERANCE_EUR = 50e6


#: The only quantity the solver will root-find against. An ALLOWLIST, and the distinction
#: is not pedantry: the first version tested `quantity in BANDED_QUANTITIES`, so
#: "behavioral" (English spelling), "Behavioural" (capitalised), "cell-bound" (hyphen)
#: and "macro " (trailing space) all sailed past the refusal and were answered with a
#: converged mechanical number. A denylist refuses what it recognises; the caller who
#: most needs refusing is the one who typed the name slightly wrong.
SOLVABLE_QUANTITIES = frozenset({"mechanical"})


def refuse_banded(quantity: str) -> None:
    """Raise unless asked to solve against the mechanical layer.

    Separate and public so the refusal can be tested directly, and so a caller can ask
    the question before spending minutes discovering the answer.
    """
    if quantity in SOLVABLE_QUANTITIES:
        return
    why = BANDED_QUANTITIES.get(quantity)
    if why is None:
        near = {name.lower().replace("-", "_").replace(" ", "")
                for name in BANDED_QUANTITIES}
        normalised = quantity.strip().lower().replace("-", "_").replace(" ", "")
        hint = (f" (« {quantity} » ressemble à une grandeur en bande, mais le solveur ne "
                f"devine pas : il refuse ce qu'il ne reconnaît pas.)"
                if normalised in near or normalised.startswith("behav") else "")
        raise ScenarioError(
            f"Grandeur inconnue : « {quantity} ». Le solveur ne résout que sur "
            f"{sorted(SOLVABLE_QUANTITIES)}, et refuse tout le reste plutôt que de "
            f"retomber silencieusement sur le mécanique — un appelant qui demande autre "
            f"chose et reçoit un nombre mécanique reçoit une réponse à une question "
            f"qu'il n'a pas posée.{hint}"
        )
    raise ScenarioError(
        f"Le solveur ne résout que sur l'étage MÉCANIQUE, et « {quantity} » n'en est "
        f"pas un : {why}. « La valeur du bouton qui annule un intervalle » n'est pas "
        f"une question bien posée — toute valeur dont l'intervalle contient zéro y "
        f"répond, et le solveur rendrait celle que la recherche a croisée en premier."
    )


def solve_budget_neutral(
    knob: str,
    price: Callable[[float], float],
    *,
    bracket: tuple[float, float],
    target_eur: float = 0.0,
    quantity: str = "mechanical",
    tolerance_eur: float = NEUTRAL_TOLERANCE_EUR,
    max_iterations: int = MAX_ITERATIONS,
) -> SolverResult:
    """Find the value of `knob` whose MECHANICAL cost equals `target_eur`.

    `price` maps a knob value to a mechanical cost in euros. Injecting it keeps this
    function testable in milliseconds and keeps the population out of the solver's
    business — the solver's job is root-finding, not simulation.

    Secant rather than bisection, because each evaluation is minutes; see the module
    docstring. A run that does not converge returns `converged=False` and its last
    iterate is NOT presented as the answer.
    """
    refuse_banded(quantity)
    low, high = bracket
    if low >= high:
        raise ScenarioError(f"intervalle vide : [{low}, {high}]")
    if max_iterations < 2:
        raise ScenarioError(
            f"un intervalle demande deux évaluations pour être encadré ; "
            f"max_iterations={max_iterations} est en dessous du minimum")
    validate = getattr(price, "validate", None)
    if validate is not None:
        # The bracket ends are checked BEFORE the first population run, not after it.
        # Without this, `price(low)` completes — minutes — and then `price(high)` raises
        # a raw pydantic ValidationError that escapes the solver and the CLI as a
        # traceback. The knob's own bounds are not always the schema's: `ifi_decote_taux`
        # is declared ge=0 le=1 but cross-field-rejected above 0.0125, so a caller who
        # brackets at the declared range is doing something reasonable and deserves an
        # answer in milliseconds.
        for end in (low, high):
            validate(end)

    x0, x1 = low, high
    f0, f1 = price(x0) - target_eur, price(x1) - target_eur
    iterations = 2

    if abs(f0) <= tolerance_eur:
        return SolverResult(knob, x0, f0 + target_eur, iterations, True,
                            "la borne basse est déjà neutre")
    if abs(f1) <= tolerance_eur:
        return SolverResult(knob, x1, f1 + target_eur, iterations, True,
                            "la borne haute est déjà neutre")
    if f0 * f1 > 0:
        return SolverResult(
            knob, None, None, iterations, False,
            f"Le coût n'atteint pas la cible aux DEUX BORNES de [{low:g}, {high:g}] : "
            f"il vaut {f0 + target_eur:+,.0f} EUR à l'une et {f1 + target_eur:+,.0f} "
            f"EUR à l'autre, soit un écart à la cible de même signe des deux côtés. "
            f"Ce solveur ne cherche pas de racine sans changement de signe — ce qui ne "
            f"veut PAS dire qu'il n'en existe pas : un coût qui passe sous la cible et "
            f"remonte à l'intérieur de l'intervalle a deux racines et deux bornes de "
            f"même signe. Deux échantillons ne peuvent pas dire lequel des deux cas on "
            f"a. Resserrer l'intervalle autour d'une valeur essayée à la main, ou "
            f"l'élargir si le levier semble trop faible.")

    while iterations < max_iterations:
        if f1 == f0:  # pragma: no cover - flat segment
            break
        x2 = x1 - f1 * (x1 - x0) / (f1 - f0)
        if not low <= x2 <= high:
            # Secant left the bracket; fall back to its midpoint for this step rather
            # than extrapolating into knob values the caller never sanctioned.
            x2 = (x0 + x1) / 2.0
        f2 = price(x2) - target_eur
        iterations += 1
        x0, f0, x1, f1 = x1, f1, x2, f2
        if abs(f2) <= tolerance_eur:
            return SolverResult(knob, x2, f2 + target_eur, iterations, True,
                                "neutre à la tolérance déclarée")

    return SolverResult(
        knob, None, None, iterations, False,
        f"Pas de convergence en {iterations} évaluations ; le dernier écart vaut "
        f"{f1:+,.0f} EUR. La dernière itérée n'est PAS rendue comme réponse — un "
        f"solveur qui rend son dernier essai fabrique une précision qu'il n'a pas.")


# --------------------------------------------------------------------------- #
# Wiring the solver to the actual population
# --------------------------------------------------------------------------- #


def scalar_knobs() -> list[str]:
    """The knobs a root-finder can move: the ones that take a single number.

    Derived from the wire model rather than listed, so a knob added to `ReformSpec`
    becomes solvable without anyone remembering to update a list here.

    READ OFF THE ANNOTATION, NOT PROBED WITH A VALUE. The first version validated
    `{name: 0.5}` and called a knob scalar if that passed, which is wrong in a way that
    is easy to miss: it excluded four genuinely scalar knobs whose CROSS-FIELD validators
    reject 0.5 on its own — `af_plafond_tranche_2_base` must sit above tranche 1, and the
    three `ifi_decote_*` parameters are coupled. Those knobs would have been refused with
    "ne prend pas un nombre unique", which is not what was wrong with them.

    Bounds are still enforced, just where they belong: `price()` builds a full ReformSpec
    per evaluation, so an out-of-range knob value fails on the first one.
    """
    import typing

    from impots.api.schemas import ReformSpec

    def is_scalar(annotation: object) -> bool:
        # Unwrap `X | None`, then `Annotated[X, …]`, and ask what is left.
        for arg in typing.get_args(annotation) or (annotation,):
            if arg is type(None):
                continue
            base = typing.get_args(arg)[0] if typing.get_origin(arg) is not None \
                and hasattr(arg, "__metadata__") else arg
            if base in (float, int):
                return True
        return False

    return sorted(name for name, field in ReformSpec.model_fields.items()
                  if is_scalar(field.annotation))


def knob_pricer(
    knob: str,
    *,
    year: int,
    base: Any = None,
    frame: Any = None,
    households: int | None = None,
) -> Callable[[float], float]:
    """Build the `price` callable the solver needs: knob value -> mechanical cost, EUR.

    Positive means the reform COSTS the budget, matching `Aggregates.reform_cost`.

    `base` is an optional `ReformSpec` the knob is varied on top of — that is what makes
    the solver useful for the real question, which is never "what value of this knob is
    free" but "given the reform I actually want, what value of this knob pays for it".

    THE BOUNDS ARE CHECKED HERE, NOT DISCOVERED SIX MINUTES IN. A knob that is not scalar,
    or a value outside the schema's range, fails in milliseconds — before the first
    population run rather than after it.
    """
    from impots.api.main import QUICK_TIER_HOUSEHOLDS
    from impots.api.schemas import ReformSpec
    from impots.population import aggregate as aggregate_module
    from impots.population.runner import run as population_run

    if knob not in ReformSpec.model_fields:
        raise ScenarioError(
            f"« {knob} » n'est pas un bouton. Les boutons scalaires sont : "
            f"{', '.join(scalar_knobs())}.")
    if knob not in scalar_knobs():
        raise ScenarioError(
            f"« {knob} » ne prend pas un nombre unique — `ir_bareme` est un barème "
            f"complet, pas un scalaire, et une recherche de racine se fait sur un "
            f"scalaire. Résoudre sur un bouton scalaire, ou exprimer le déplacement du "
            f"barème comme un scalaire et l'ajouter au modèle.")

    base_fields = base.model_dump(exclude_none=True) if base is not None else {}
    households = households or QUICK_TIER_HOUSEHOLDS

    def validate(value: float) -> None:
        """Build the ReformSpec and throw it away — milliseconds, no engine.

        Attached to `price` so the solver can check its bracket ends before spending a
        population run on them, without the solver needing to know what a ReformSpec is.
        """
        try:
            ReformSpec.model_validate({**base_fields, knob: value})
        except Exception as error:
            raise ScenarioError(
                f"« {knob} » = {value:g} est refusé par le modèle : {error}. La borne "
                f"est hors de ce que ce bouton accepte — noter que les bornes déclarées "
                f"d'un champ ne sont pas toujours les seules : certains boutons ont des "
                f"validateurs CROISÉS qui resserrent l'intervalle réel."
            ) from error

    def price(value: float) -> float:
        reform = ReformSpec.model_validate({**base_fields, knob: value})
        result = population_run(
            frame if frame is not None else _frame(), year=year, reform=reform,
            tier="full", sample=households)
        return float(aggregate_module.aggregate(result.households).reform_cost or 0.0)

    price.validate = validate  # type: ignore[attr-defined]
    return price


def _frame() -> Any:
    from impots.api.main import _population_frame

    return _population_frame()


def mechanical_price(scenario: Scenario, *, frame: Any = None,
                     households: int | None = None) -> dict[str, Any]:
    """Price one scenario's MECHANICAL cost. The `price` argument `compare` expects.

    Returns only the mechanical layer. The banded layers are deliberately absent rather
    than present-and-uncomparable: a caller who wants them can pass their own pricing
    function, and `compare` will then show them side by side without differencing.
    """
    from impots.api.main import QUICK_TIER_HOUSEHOLDS
    from impots.population import aggregate as aggregate_module
    from impots.population.runner import run as population_run

    result = population_run(
        frame if frame is not None else _frame(), year=scenario.year,
        reform=scenario.reform, tier="full",
        sample=households or QUICK_TIER_HOUSEHOLDS,
        impute_ij="ij" in scenario.imputations)
    agg = aggregate_module.aggregate(result.households)
    return {"mechanical": float(agg.reform_cost or 0.0), "deltas": dict(agg.deltas)}
