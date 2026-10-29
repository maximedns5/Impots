"""Pre-registered chiffrages: the FORWARD half of the backtest suite (F1).

**READ `impots.behavioural.chiffrages` FIRST — this module is its mirror image, and it
was written second, badly, by someone who had not read it.** That suite grades L2 against
published costings of articles ALREADY enacted: the comparator exists, and the question is
whether our arithmetic matches the state's. This module handles the case where the
comparator does NOT exist yet: the article is published, we price it, and the official
figure arrives weeks later. Backward and forward halves of one idea.

The first version of this file invented its own vocabulary for the comparator and was
poorer for it. It now takes `Published`, `Sign` and `Basis` from the backtest suite, so a
figure means the same thing in both directions, and it adopts two of that suite's fields
whose necessity it had rediscovered the hard way while triaging the PLF 2026:

* `mirror` — «Where an article's end state is already the law the parameter tree carries,
  replaying it is a no-op against the baseline, so the case has to run the repeal
  instead». That is PLF 2026 article 9 exactly: the dons Coluche ceiling is already at
  2 000 EUR in the tree, so pricing the article against it returns 0,00 EUR. The triage
  called this a discovery; it was a rediscovery, and the machinery already existed.
* `bound` — «`lower` when the simulator can express only PART of what the published
  figure costs, so the honest test is an inequality». That is article 11 exactly:
  `cvae_taux_max` moves one of six scale coefficients.

WHAT IS GENUINELY NEW HERE, and the only reason this module exists rather than a flag on
the other one: a chiffrage written BEFORE its comparator can have its tolerance changed
AFTER, and nothing in a backward-looking suite needs to defend against that.

One YAML case per chiffrage: what was priced, on what, when, and — declared **before** the
official figure exists — the tolerance the grade will use. When the évaluation préalable
appears, its figure enters with the full comparator discipline and the case grades itself.

WHY THIS IS NOT JUST A SPREADSHEET. A model that publishes its estimate after the official
one is worth nothing; a model that published first, dated, and can be checked afterwards is
worth exactly the difference between its record and chance. That difference only survives if
the tolerance cannot move once the answer is known — which is the temptation this file exists
to remove. So the tolerance is declared at registration and its immutability is a property
`verify_tolerance_unchanged` ASSERTS from git history, not a habit anyone has to keep.

THIS IS MEASUREMENT INFRASTRUCTURE, so it gets the three standing questions at birth
rather than after an incident.

**1. Can this check's denominator go to zero?** Yes, and that is not hypothetical: a PLF
article whose chiffrage is "sans impact budgétaire" publishes 0, and plenty publish tens of
millions where our sampling noise is of the same order. A purely relative tolerance would
then demand infinite precision, and every such case would grade red for arithmetic reasons.
So a tolerance is a PAIR — relative and absolute — and the allowance is the larger of the
two. `binding` records which one decided, because a grade that never says which of its two
gates it passed is a grade you cannot read. This is D-093's lesson applied before the
incident instead of after it.

**2. Did I test the fix on a shape other than the one that alerted me?** The grading is
exercised on: a published figure of zero, a negative one (a measure that raises revenue), a
simulated figure of the opposite sign to the published one, and both gates binding in turn.
D-094 exists because a fix was tested only on the shape that prompted it.

**3. Have I ever seen this check fail?** `tests/test_chiffrages.py` opens with a stub case
carrying a known miss, and asserts it grades OUTSIDE. Until that test passes, no real case
may enter — a harness whose red light has never been seen is not a harness, it is a hope.
That is the same rule that `make full` broke by being unable to record a failure at all.

WHAT THE HARNESS REFUSES, and each refusal has its test:

* to grade a case that has never been committed — the commit IS the pre-registration, so an
  uncommitted case is a draft, not a record;
* to grade a case whose tolerance block changed after the file was introduced;
* to grade against a comparator missing any of source, vintage, perimeter or net_of — an
  official figure whose perimeter is unstated cannot be compared to ours, and the ways two
  budget figures can differ while both being right are numerous enough that leaving it to
  the reader is a way of not saying;
* to overwrite an existing case.

PRE-REGISTRATION INTEGRITY IS INTERNAL-GRADE, AND SAYS SO. The record is a commit hash in a
private repository plus a dated line in the full-pass log. That is honest for internal use
and would convince nobody external, because the repository owner can rewrite history. If
external credibility ever matters, the chiffrage would need a timestamp outside the repo —
a public commit, a published hash — AT REGISTRATION TIME, which is a decision for the owner
and is recorded as an option rather than taken here.
"""

from __future__ import annotations

import subprocess
from dataclasses import asdict, dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

CHIFFRAGES = Path(__file__).resolve().parents[2] / "chiffrages_preregistres"
"""Deliberately NOT `tests/chiffrages/`, which holds the BACKWARD half — historical
articles whose published costing already exists. Two directories because two
artefacts: a backtest case is written after the answer, a pre-registration before it."""

#: Comparator fields that must be filled before a grade is possible. Not decoration: two
#: budget figures can differ while both are right — one gross of the CSG a measure induces
#: and one net, one on a full year and one on the part of it the measure runs, one on the
#: State's take and one on all administrations. A comparison that does not state which is
#: not a comparison.
REQUIRED_COMPARATOR_FIELDS = ("published_eur", "source", "vintage", "perimeter", "net_of")


class ChiffrageError(RuntimeError):
    """A chiffrage could not be registered, read, or graded as asked."""


@dataclass(frozen=True)
class Tolerance:
    """What will count as a hit — fixed before the answer is known.

    Two gates, and the allowance is the LARGER. See question 1 in the module docstring:
    a relative-only tolerance demands infinite precision of a chiffrage published as zero,
    and near-infinite precision of one published at a few tens of millions, which is inside
    our own sampling noise.
    """

    relative: float
    absolute_eur: float
    rationale: str

    def __post_init__(self) -> None:
        if not 0 < self.relative < 1:
            raise ChiffrageError(
                f"tolérance relative {self.relative} hors ]0, 1[ : une tolérance de 0 ne "
                f"peut jamais être tenue, une de 1 ne mesure rien")
        if self.absolute_eur <= 0:
            raise ChiffrageError(
                f"tolérance absolue {self.absolute_eur} : elle doit être strictement "
                f"positive, car c'est elle qui rend gradable un chiffrage publié à zéro")
        if not self.rationale.strip():
            raise ChiffrageError(
                "une tolérance sans justification est un nombre choisi après coup en "
                "esprit sinon en fait : dire pourquoi CELLE-CI, avant de connaître la "
                "réponse, est ce qui la rend un engagement")

    def allowance(self, published_eur: float) -> tuple[float, str]:
        """The euros of gap permitted, and which of the two gates decided."""
        relative = self.relative * abs(published_eur)
        if relative >= self.absolute_eur:
            return relative, "relative"
        return self.absolute_eur, "absolue"


@dataclass(frozen=True)
class Comparator:
    """The official figure, with everything needed to know what it is a figure OF.

    `sign` and `basis` are taken from `impots.behavioural.chiffrages.Published`, and are
    not decoration. The published documents are inconsistent about sign — some print a
    cost as a positive number under a «coût» heading — so carrying it explicitly is what
    stops a case flipping green to red at twice the magnitude. And an année-pleine figure
    compared against a première-année simulation is a basis mismatch, which D-029 requires
    be tried as a MECHANICAL explanation before anyone reaches for population realism.

    `published_eur` is SIGNED, in the engine's convention: a cost positive, a yield
    negative, like `mechanical_eur`, because `grade` subtracts one from the other as they
    stand. Carrying `sign` alone stopped nothing: `grade` never read it, and the printed
    «gain de 1,1 Md€» typed as +1.1e9 under `sign: yield` graded a yield against a cost
    (D-204). So the two must agree, and a comparator where they contradict each other is
    refused at birth (D-206). Zero contradicts neither.
    """

    published_eur: float
    source: str
    vintage: str
    perimeter: str
    net_of: str
    sign: str = "cost"
    basis: str = "unstated"
    retrieved: str = ""

    def __post_init__(self) -> None:
        if self.sign not in ("cost", "yield"):
            raise ChiffrageError(
                f"sign « {self.sign} » : « cost » ou « yield », jamais déduit du signe "
                f"du nombre — les documents publiés sont incohérents là-dessus")
        if self.basis not in ("annee-pleine", "premiere-annee", "unstated"):
            raise ChiffrageError(f"basis « {self.basis} » inconnu")
        # A missing amount is `grade`'s refusal to make, with the other missing fields.
        amount = self.published_eur
        if isinstance(amount, (int, float)) and (
                (amount > 0 and self.sign == "yield") or (amount < 0 and self.sign == "cost")):
            raise ChiffrageError(
                f"published_eur {amount:+.0f} et sign « {self.sign} » se contredisent. "
                f"`grade` lit le montant tel quel, dans la convention du moteur : un coût "
                f"positif, un gain négatif. Un gain saisi positif serait noté contre un "
                f"coût, à deux fois l'écart (D-204). Saisir le montant signé.")

    @property
    def signed(self) -> float:
        """Positive raises money, negative costs it — the backtest suite's convention."""
        return (-abs(self.published_eur) if self.sign == "cost"
                else abs(self.published_eur))


@dataclass(frozen=True)
class Chiffrage:
    """One pre-registered estimate."""

    case: str
    pre_registered: str
    commit: str
    population_vintage: str
    sample: Any
    engine: dict[str, str]
    mechanical_eur: float
    tolerance: Tolerance
    scenario: str | None = None
    reform: dict[str, Any] | None = None
    behavioural: dict[str, Any] | None = None
    intervals: dict[str, Any] = field(default_factory=dict)
    fan: dict[str, Any] | None = None
    note: str = ""
    bound: str = "two-sided"
    """`lower` when we express only PART of what the published figure costs, so the
    honest test is an inequality and landing ABOVE the published figure is a finding.
    Taken from the backtest suite, which learned it on the barème indexations."""
    mirror: bool = False
    """The reform encodes the article's REVERSE, because its end state is already the
    law the tree carries. PLF 2026 article 9 is the live case."""
    comparator: Comparator | None = None
    revision: dict[str, Any] | None = None
    """The case this one revises, when it is a revision written after the annex was opened
    (D-292): never a blind registration, and counted apart from them."""

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "case": self.case,
            "pre_registered": self.pre_registered,
            "commit": self.commit,
            "scenario": self.scenario,
            "reform": self.reform,
            "population_vintage": self.population_vintage,
            "sample": self.sample,
            "engine": dict(self.engine),
            "chiffrage": {
                "mechanical_eur": self.mechanical_eur,
                "behavioural": self.behavioural,
                "intervals": self.intervals or None,
                "fan": self.fan,
            },
            "tolerance": asdict(self.tolerance),
            "note": self.note,
            "bound": self.bound,
            "mirror": self.mirror,
            "comparator": asdict(self.comparator) if self.comparator else None,
        }
        # Only on a revision: every case written before reads and writes back as it was.
        if self.revision is not None:
            payload["revision"] = dict(self.revision)
        return payload


#: A grade is one of these, and never a number on its own. "outside" carries a direction
#: because "we were 30 % out" and "we were 30 % out ON THE HIGH SIDE, as we were on the
#: last four" are different pieces of information, and only the second accumulates.
VERDICTS = ("within", "outside")


@dataclass(frozen=True)
class Grade:
    case: str
    verdict: str
    direction: str
    simulated_eur: float
    published_eur: float
    gap_eur: float
    allowed_eur: float
    binding: str
    relative_gap: float | None

    def line(self) -> str:
        """One row of the report, computing its own numbers from its own fields.

        Written here rather than in the report template so prose cannot drift from the
        run it sits beside — the mechanism the review asked to spread to every
        hand-written number in `reports/`.
        """
        pub = f"{self.published_eur / 1e9:+.3f}"
        sim = f"{self.simulated_eur / 1e9:+.3f}"
        gap = f"{self.gap_eur / 1e9:+.3f}"
        rel = "n/a" if self.relative_gap is None else f"{self.relative_gap:+.1%}"
        return (f"| {self.case} | {sim} | {pub} | {gap} | {rel} | "
                f"{self.allowed_eur / 1e9:.3f} ({self.binding}) | "
                f"**{self.verdict}** {self.direction} |")


def grade(chiffrage: Chiffrage) -> Grade:
    """Compare a pre-registered chiffrage with the official figure. Refuses if it cannot.

    The comparison itself is one subtraction. Everything load-bearing here is in what it
    declines to do without.
    """
    if chiffrage.comparator is None:
        raise ChiffrageError(
            f"« {chiffrage.case} » n'a pas de comparateur : rien à noter tant que "
            f"l'évaluation préalable n'est pas parue et saisie.")
    missing = [name for name in REQUIRED_COMPARATOR_FIELDS
               if getattr(chiffrage.comparator, name, None) in (None, "")]
    if missing:
        raise ChiffrageError(
            f"« {chiffrage.case} » : comparateur incomplet, il manque {', '.join(missing)}. "
            f"Deux chiffres budgétaires peuvent différer en étant tous deux justes — l'un "
            f"brut de la CSG qu'une mesure induit et l'autre net, l'un en année pleine et "
            f"l'autre sur la fraction courue, l'un sur l'État et l'autre sur toutes les "
            f"administrations. Ne pas le dire, c'est laisser au lecteur une comparaison "
            f"qu'on n'a pas faite.")

    published = float(chiffrage.comparator.published_eur)
    simulated = float(chiffrage.mechanical_eur)
    gap = simulated - published
    allowed, binding = chiffrage.tolerance.allowance(published)
    if chiffrage.bound == "lower":
        # We express only part of what the published figure costs, so the simulated
        # figure MUST land below it in magnitude. A symmetric window would put half its
        # area in a region the case itself says is unreachable, and landing above is a
        # finding rather than a pass. Taken from the backtest suite's `bound: lower`.
        overshoot = abs(simulated) - abs(published)
        verdict = "within" if overshoot <= allowed else "outside"
    else:
        verdict = "within" if abs(gap) <= allowed else "outside"
    if gap > 0:
        direction = "au-dessus"
    elif gap < 0:
        direction = "en-dessous"
    else:
        direction = "pile"
    return Grade(
        case=chiffrage.case, verdict=verdict, direction=direction,
        simulated_eur=simulated, published_eur=published, gap_eur=gap,
        allowed_eur=allowed, binding=binding,
        # None rather than infinity when the official figure is zero: a relative gap
        # against zero is not a large number, it is not a number.
        relative_gap=(gap / abs(published)) if published else None,
    )


# --------------------------------------------------------------------------- #
# Persistence, and the integrity of "declared before"
# --------------------------------------------------------------------------- #


def _git(*args: str, cwd: Path | None = None) -> str:
    done = subprocess.run(
        ["git", *args], cwd=str(cwd or CHIFFRAGES.parent),
        capture_output=True, text=True, check=False)
    if done.returncode != 0:
        raise ChiffrageError(f"git {' '.join(args)} : {done.stderr.strip()}")
    return done.stdout


def head_commit() -> str:
    return _git("rev-parse", "HEAD").strip()


def tolerance_history(case: str, directory: Path | None = None) -> list[dict[str, Any]]:
    """Every distinct tolerance block this case has had, oldest first.

    Read from git rather than from the file, because the file only ever shows the last
    one. This is what turns "declared at pre-registration time, never after" from a habit
    into a property a test can assert.
    """
    import yaml

    directory = directory or CHIFFRAGES
    path = _case_path(directory, case)
    root = directory.parent
    rel = path.relative_to(root)
    try:
        revisions = _git("log", "--follow", "--format=%H", "--", str(rel),
                         cwd=root).split()
    except ChiffrageError as error:
        # An empty repository, or none at all, is not a git failure to report upward: it
        # is the answer "this case has no history", which the caller turns into "not
        # pre-registered". Anything else is a real git problem and still propagates.
        text = str(error)
        if "does not have any commits" in text or "not a git repository" in text:
            return []
        raise
    seen: list[dict[str, Any]] = []
    for revision in reversed(revisions):
        try:
            blob = _git("show", f"{revision}:{rel}", cwd=root)
        except ChiffrageError:  # pragma: no cover - a rename's far side
            continue
        document = yaml.safe_load(blob) or {}
        tolerance = document.get("tolerance")
        if tolerance and (not seen or tolerance != seen[-1]):
            seen.append(tolerance)
    return seen


def verify_tolerance_unchanged(case: str, directory: Path | None = None) -> None:
    """Refuse a case whose tolerance moved after it was first committed.

    THE ONE RULE THAT MAKES THE REST WORTH ANYTHING. A tolerance widened once the official
    figure is known converts every miss into a hit, and leaves a file that looks exactly
    like an honest one. Git remembers; the file does not.
    """
    history = tolerance_history(case, directory)
    if not history:
        raise ChiffrageError(
            f"« {case} » n'a jamais été committé : il n'est donc pas préenregistré. Le "
            f"commit EST l'enregistrement — un fichier non versionné est un brouillon, "
            f"et le noter reviendrait à dater après coup.")
    if len(history) > 1:
        raise ChiffrageError(
            f"« {case} » : la tolérance a changé {len(history) - 1} fois depuis "
            f"l'enregistrement. Déclarée {history[0]}, aujourd'hui {history[-1]}. Une "
            f"tolérance élargie une fois le chiffre officiel connu transforme chaque "
            f"manqué en réussi et laisse un fichier qui ressemble trait pour trait à un "
            f"fichier honnête. Enregistrer un NOUVEAU cas, daté d'aujourd'hui, et laisser "
            f"celui-ci porter sa note.")


def _case_path(directory: Path, case: str) -> Path:
    """A case name is an identifier, not a path — the same rule as scenarios (D-094)."""
    from impots.scenarios import _check_name

    _check_name(case)
    return directory / f"{case}.yaml"


def save(chiffrage: Chiffrage, directory: Path | None = None) -> Path:
    """Write a case. Refuses to overwrite: a pre-registration is not editable."""
    import yaml

    directory = directory or CHIFFRAGES
    directory.mkdir(parents=True, exist_ok=True)
    path = _case_path(directory, chiffrage.case)
    # Exclusive creation, as for scenarios: `exists()` is False for a dangling link and
    # `write_text` follows it out of the directory (D-173).
    try:
        with path.open("x", encoding="utf-8") as handle:
            handle.write(
                yaml.safe_dump(chiffrage.to_dict(), allow_unicode=True, sort_keys=False))
    except FileExistsError:
        raise ChiffrageError(
            f"{path.name} existe déjà. Un chiffrage préenregistré ne se réécrit pas — "
            f"c'est précisément ce que « préenregistré » veut dire. Pour une révision, "
            f"un nouveau cas sous un nouveau nom, daté d'aujourd'hui.") from None
    return path


def load(case: str, directory: Path | None = None) -> Chiffrage:
    """Read a case back. Every way the file can be wrong is a ChiffrageError (D-094)."""
    import yaml

    directory = directory or CHIFFRAGES
    path = _case_path(directory, case)
    if path.is_symlink():
        raise ChiffrageError(
            f"« {case} » est un lien symbolique : un chiffrage se lit dans son dossier, "
            f"pas là où un lien le fait pointer (D-173).")
    if not path.exists():
        raise ChiffrageError(f"{path} n'existe pas")
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, ValueError, yaml.YAMLError) as error:
        raise ChiffrageError(f"« {case} » est illisible : {error}") from error
    if not isinstance(document, dict):
        raise ChiffrageError(f"« {case} » ne contient pas un document YAML")
    try:
        stack = document.get("chiffrage") or {}
        comparator = document.get("comparator")
        return Chiffrage(
            case=document["case"],
            pre_registered=document["pre_registered"],
            commit=document["commit"],
            population_vintage=str(document["population_vintage"]),
            sample=document.get("sample"),
            engine=dict(document.get("engine") or {}),
            mechanical_eur=float(stack["mechanical_eur"]),
            tolerance=Tolerance(**document["tolerance"]),
            scenario=document.get("scenario"),
            reform=document.get("reform"),
            behavioural=stack.get("behavioural"),
            intervals=stack.get("intervals") or {},
            fan=stack.get("fan"),
            note=document.get("note") or "",
            bound=document.get("bound", "two-sided"),
            mirror=bool(document.get("mirror", False)),
            comparator=Comparator(**comparator) if comparator else None,
            revision=document.get("revision"),
        )
    except ChiffrageError:
        raise
    except (KeyError, TypeError, ValueError) as error:
        raise ChiffrageError(
            f"« {case} » est incomplet ou mal formé : {error!r}") from error


def available(directory: Path | None = None) -> list[str]:
    directory = directory or CHIFFRAGES
    if not directory.exists():
        return []
    return sorted(path.stem for path in directory.glob("*.yaml"))


def register(
    case: str,
    *,
    mechanical_eur: float,
    tolerance: Tolerance,
    population_vintage: str,
    sample: Any,
    scenario: str | None = None,
    reform: dict[str, Any] | None = None,
    behavioural: dict[str, Any] | None = None,
    intervals: dict[str, Any] | None = None,
    fan: dict[str, Any] | None = None,
    note: str = "",
    bound: str = "two-sided",
    mirror: bool = False,
    directory: Path | None = None,
    now: str | None = None,
) -> Path:
    """Stamp a chiffrage with the moment and the tree it was computed on.

    The timestamp is taken here, not passed by a caller: a pre-registration whose date its
    author chooses is not one. `now` exists so tests are deterministic and for no other
    reason.
    """
    from impots.engine import versions

    if scenario is None and reform is None:
        raise ChiffrageError(
            f"« {case} » ne dit pas ce qui a été chiffré : donner soit un scénario "
            f"enregistré, soit la réforme elle-même.")
    stamp = now or datetime.now(UTC).isoformat(timespec="seconds")
    chiffrage = Chiffrage(
        case=case, pre_registered=stamp, commit=head_commit(),
        population_vintage=population_vintage, sample=sample,
        engine=versions(), mechanical_eur=float(mechanical_eur), tolerance=tolerance,
        scenario=scenario, reform=reform, behavioural=behavioural,
        intervals=intervals or {}, fan=fan, note=note,
        bound=bound, mirror=mirror,
    )
    return save(chiffrage, directory)


def register_firm(
    case: str,
    *,
    spec: Any,
    year: int,
    frame: Any,
    tolerance: Tolerance,
    population_vintage: str,
    note: str = "",
    directory: Path | None = None,
) -> Path:
    """Price a FIRM reform over a firm population, and pre-register the figure.

    The household path goes through a saved scenario, and a scenario is a household
    `ReformSpec`: a firm reform had no way into this registry. Found on PLF 2027
    publication day, for the CEBGE — the article the September triage marked
    `priceable_now`. There is no scenario file to point at, so the reform is recorded
    whole — chain, year, spec — and, as on the household side, the figure is computed
    here from the run and never handed in.
    """
    from impots.entreprises import aggregate as firm_aggregate
    from impots.entreprises import runner as firm_runner

    result = firm_runner.run(frame, year=year, reform=spec)
    cost = firm_aggregate.aggregate(result.firms).reform_cost
    return register(
        case, mechanical_eur=float(cost or 0.0), tolerance=tolerance,
        population_vintage=population_vintage, sample="population complète",
        reform={"chaine": "entreprises", "annee": year,
                "spec": spec.model_dump(exclude_none=True, mode="json")},
        note=note, directory=directory)


def revise_to_budget_year(case: str, new_case: str, *, year: int, raison: str,
                          directory: Path | None = None, scenarios_dir: Path | None = None,
                          now: str | None = None) -> Path:
    """A new case, the registered `case` turned from its full year to the budget effect of
    `year` that its comparator publishes, by the PAS calendar (`impots.pas`, D-292).

    Only the basis changes: the figure is the registered one, on its population and its
    engine, and its tolerance and comparator are kept. The full year is held constant from
    one income year to the next, as the registered population does not age. The revision
    says the case it revises and that it was written after the annex was opened: it is
    never a blind registration, and the report counts it apart.
    """
    from impots import pas
    from impots import scenarios as scenarios_module

    original = load(case, directory)
    if original.comparator is None:
        raise ChiffrageError(f"« {case} » n'a pas de comparateur : il n'y a pas de base à "
                             f"rejoindre.")
    if original.comparator.basis != "premiere-annee":
        raise ChiffrageError(
            f"« {case} » est noté contre un chiffre en année pleine, « "
            f"{original.comparator.basis} » : la base est déjà celle du simulateur.")
    if original.scenario is None:
        raise ChiffrageError(
            f"« {case} » n'est pas un scénario des ménages : le calendrier du PAS ne vaut "
            f"que pour l'impôt sur le revenu.")
    try:
        first = scenarios_module.load(original.scenario, scenarios_dir).year
    except scenarios_module.ScenarioError as error:
        raise ChiffrageError(f"« {case} » : son scénario ne se lit pas : {error}") from error
    if year <= first:
        raise ChiffrageError(
            f"année budgétaire {year} : la mesure vaut à partir des revenus {first}, et "
            f"ne pèse sur le budget qu'à partir de {first + 1}.")
    full_year = {y: original.mechanical_eur for y in range(first, year + 1)}
    budget = pas.budget_effects(full_year, first_income_year=first, years=(year,))[year]
    stamp = now or datetime.now(UTC).isoformat(timespec="seconds")
    revised = replace(
        original, case=new_case, pre_registered=stamp, commit=head_commit(),
        mechanical_eur=float(budget),
        note=(f"Révision de « {case} », écrite après l'ouverture de l'annexe : pas un "
              f"préenregistrement aveugle. {raison}"),
        revision={"de": case, "apres_annexe": True, "annee_budgetaire": year,
                  "premiere_annee_de_revenus": first,
                  "annee_pleine_eur": original.mechanical_eur,
                  "methode": f"impots.pas.budget_effects, {pas.MONTHS_UPDATED} mois de "
                             f"taux mis à jour", "raison": raison})
    return save(revised, directory)


def report(directory: Path | None = None) -> str:
    """The scoreboard, every number computed from the cases rather than typed.

    An ungraded case appears as ungraded. That is the whole value of the table: a record
    that only lists the cases with answers is not a record, it is a selection.
    """
    directory = directory or CHIFFRAGES
    names = available(directory)
    lines = [
        "# Chiffrages préenregistrés",
        "",
        "Généré par `impots chiffrage report`. Chaque nombre est calculé depuis les cas ;",
        "aucun n'est saisi à la main.",
        "",
        "| cas | simulé (md) | publié (md) | écart (md) | écart rel. | toléré (md) | note |",
        "|---|---|---|---|---|---|---|",
    ]
    graded, revised, pending, refused = [], [], [], []
    for name in names:
        try:
            case = load(name, directory)
        except ChiffrageError as error:
            refused.append((name, str(error)))
            continue
        # A case with no comparator is not yet gradeable, so the integrity check would be
        # premature: it gates GRADING, not listing. Checking it here would file every
        # freshly written case under "non notable" for a reason that has not arisen yet.
        if case.comparator is None:
            pending.append(case)
            continue
        try:
            verify_tolerance_unchanged(name, directory)
            (revised if case.revision else graded).append((grade(case), case))
        except ChiffrageError as error:
            refused.append((name, str(error)))

    for verdict, _ in graded:
        lines.append(verdict.line())
    if not graded:
        lines.append("| _aucun cas noté_ | | | | | | |")

    within = sum(1 for g, _ in graded if g.verdict == "within")
    lines += ["", f"**{within} sur {len(graded)} dans la tolérance déclarée.**"]
    if graded:
        high = sum(1 for g, _ in graded if g.gap_eur > 0)
        lines.append(
            f"Direction des écarts : {high} au-dessus, {len(graded) - high} en-dessous — "
            f"un biais systématique se lit ici avant de se lire dans les moyennes.")
    if revised:
        lines += ["", "## Révisions, écrites après l'annexe", "",
                  "Une révision ne change que la base d'un cas enregistré, après l'ouverture "
                  "de l'annexe : elle n'est pas un préenregistrement aveugle, et ne compte "
                  "pas dans le total ci-dessus.", "",
                  "| cas | simulé (md) | publié (md) | écart (md) | écart rel. | toléré (md) "
                  "| note | révise |", "|---|---|---|---|---|---|---|---|"]
        for verdict, case in revised:
            lines.append(verdict.line() + f" {case.revision.get('de')} |")
        ok = sum(1 for g, _ in revised if g.verdict == "within")
        lines += ["", f"**{ok} sur {len(revised)} dans la tolérance, hors du compte des cas "
                      f"aveugles.**"]
    if pending:
        lines += ["", "## En attente d'un comparateur", ""]
        for case in pending:
            lines.append(
                f"* **{case.case}** — préenregistré le {case.pre_registered}, "
                f"mécanique {case.mechanical_eur / 1e9:+.3f} md, toléré "
                f"{case.tolerance.relative:.0%} ou "
                f"{case.tolerance.absolute_eur / 1e6:.0f} M au choix du plus large.")
    if refused:
        lines += ["", "## Non notables, et pourquoi", ""]
        for name, why in refused:
            lines.append(f"* **{name}** — {why}")
    return "\n".join(lines) + "\n"
