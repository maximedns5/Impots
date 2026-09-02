"""The wire format — single source of truth (spec §4).

Deliberately free of any FastAPI import: `impots.engine` imports these models, and
the engine must stay usable without a web framework (Phase 1 runs it over a
population, not over HTTP).

Sign convention (spec §3.3): every monetary field in a response is a **positive
magnitude**; the direction is carried by the field name. `ir` is tax paid,
`cotisations_salariales` is contributions withheld. Only `delta` is signed, and a
positive delta means "more of that thing under the reform" — so `delta.ir = +200`
reads as "pays 200 EUR more tax".
"""

from __future__ import annotations

from itertools import pairwise
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from impots.entreprises.reforms import FirmReformSpec

# Year window Phase 0 will answer for. The golden values are 2024; the engine
# holds law well outside this range, but nothing here has been checked against it.
MIN_YEAR = 2022
MAX_YEAR = 2026
MIN_BIRTH_YEAR = 1920
MAX_SALARY = 10_000_000.0
MAX_CHILDREN = 8
# v1 replaces the active brackets of the IR scale in place; it never adds brackets
# to the ParameterScale (spec §3.4).
MAX_BAREME_BRACKETS = 5
MIN_BAREME_BRACKETS = 2


# --------------------------------------------------------------------------- #
# Request: the household
# --------------------------------------------------------------------------- #
class Adult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    salaire_brut_annuel: Annotated[float, Field(ge=0, le=MAX_SALARY)] = Field(
        description="Gross annual salary in EUR. Divided by 12 onto the monthly "
        "`salaire_de_base` input the engine expects."
    )
    annee_naissance: Annotated[int, Field(ge=MIN_BIRTH_YEAR, le=MAX_YEAR)]


class Child(BaseModel):
    model_config = ConfigDict(extra="forbid")

    annee_naissance: Annotated[int, Field(ge=MIN_BIRTH_YEAR, le=MAX_YEAR)]


class Logement(BaseModel):
    """Optional ménage-level housing inputs. Without them `aide_logement` is 0 —
    that is the engine answering the question as asked, not a wiring bug (spec §7.9)."""

    model_config = ConfigDict(extra="forbid")

    statut: str = Field(
        description="`statut_occupation_logement` enum member name, e.g. 'locataire_vide'. "
        "Only the locataire_* statuts can ever produce a housing aid."
    )
    loyer_mensuel: Annotated[float, Field(ge=0, le=100_000)] = 0.0
    # Not optional, and not defaulted silently: leaving `zone_apl` unset does not
    # mean "no zone", it means zone 2. Stating it keeps a substantive assumption
    # visible. Zone 0 ("non renseigné") exists in the engine's enum and crashes the
    # housing cascade, hence the 1..3 bound.
    zone_apl: Annotated[int, Field(ge=1, le=3)] = 2


class HouseholdInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    adults: Annotated[list[Adult], Field(min_length=1, max_length=2)]
    children: Annotated[list[Child], Field(max_length=MAX_CHILDREN)] = Field(default_factory=list)
    couple_marie_ou_pacse: bool = False
    parent_isole: bool | None = Field(
        default=None,
        description="Case T — parent isolé. Worth half a fiscal part. Left unset it is "
        "inferred: true for a lone adult with at least one dependent child, which is "
        "what a one-adult household with children describes, false otherwise. Set it "
        "explicitly to false for a lone filer who does not in fact live alone.",
    )
    logement: Logement | None = None

    def resolved_parent_isole(self) -> bool:
        """Whether to claim case T for this household."""
        lone_parent = len(self.adults) == 1 and bool(self.children)
        return lone_parent if self.parent_isole is None else self.parent_isole

    @model_validator(mode="after")
    def _check_couple(self) -> HouseholdInput:
        if len(self.adults) == 2 and not self.couple_marie_ou_pacse:
            raise ValueError(
                "Phase 0 modélise un adulte seul ou un couple marié/pacsé. Le concubinage "
                "(deux foyers fiscaux distincts) n'est pas encore supporté : mettez "
                "couple_marie_ou_pacse=true, ou simulez chaque adulte séparément."
            )
        if len(self.adults) == 1 and self.couple_marie_ou_pacse:
            raise ValueError(
                "couple_marie_ou_pacse=true demande deux adultes ; un seul a été fourni."
            )
        if self.parent_isole and (len(self.adults) != 1 or not self.children):
            raise ValueError(
                "parent_isole=true suppose un adulte seul avec au moins un enfant à charge."
            )
        return self


# --------------------------------------------------------------------------- #
# Request: the reform
# --------------------------------------------------------------------------- #
class IRBracket(BaseModel):
    model_config = ConfigDict(extra="forbid")

    threshold: Annotated[float, Field(ge=0)]
    rate: Annotated[float, Field(ge=0.0, le=1.0)]


class ReformSpec(BaseModel):
    """A whitelist of named knobs, never raw parameter paths.

    Raw paths would be an injection surface into the parameter tree and would make
    the reform-cache key unbounded (spec §3.4).
    """

    model_config = ConfigDict(extra="forbid")

    ir_bareme: list[IRBracket] | None = Field(
        default=None,
        description="Complete replacement of the active IR scale: 2 to 5 brackets, "
        "first threshold 0, thresholds strictly increasing.",
    )
    decote_seuil_celib: Annotated[float, Field(ge=0, le=100_000)] | None = None
    decote_seuil_couple: Annotated[float, Field(ge=0, le=100_000)] | None = None
    decote_taux: Annotated[float, Field(ge=0.0, le=1.0)] | None = None
    plafond_qf_demi_part: Annotated[float, Field(ge=0, le=100_000)] | None = None
    csg_activite_imposable: Annotated[float, Field(ge=0.0, le=1.0)] | None = None
    csg_activite_deductible: Annotated[float, Field(ge=0.0, le=1.0)] | None = None

    @model_validator(mode="after")
    def _check_bareme(self) -> ReformSpec:
        if self.ir_bareme is None:
            return self
        n = len(self.ir_bareme)
        if n < MIN_BAREME_BRACKETS:
            raise ValueError(f"Le barème doit compter au moins {MIN_BAREME_BRACKETS} tranches.")
        if n > MAX_BAREME_BRACKETS:
            raise ValueError(
                f"Le barème est limité à {MAX_BAREME_BRACKETS} tranches en v1 : les tranches "
                "actives du barème légal sont remplacées sur place, aucune tranche n'est ajoutée "
                "au ParameterScale."
            )
        if self.ir_bareme[0].threshold != 0:
            raise ValueError(
                "La première tranche doit commencer à 0 € : un barème marginal doit couvrir "
                "l'ensemble des revenus."
            )
        thresholds = [b.threshold for b in self.ir_bareme]
        if any(a >= b for a, b in pairwise(thresholds)):
            raise ValueError(f"Les seuils doivent être strictement croissants ; reçu {thresholds}.")
        return self

    def is_empty(self) -> bool:
        """True when no knob is set — treated as 'no reform' rather than as an
        identity reform, so we never pay 0.5 s to clone the parameter tree for nothing."""
        return not self.model_dump(exclude_none=True)


# --------------------------------------------------------------------------- #
# Request envelope
# --------------------------------------------------------------------------- #
Tier = Literal["light", "full"]


class SimulateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    household: HouseholdInput
    year: Annotated[int, Field(ge=MIN_YEAR, le=MAX_YEAR)] = 2024
    reform: ReformSpec | None = None
    tier: Tier = "light"
    emtr: bool = False
    historique_revenus: bool = Field(
        default=True,
        description="Replicate the salary and housing across the two preceding years so "
        "that means-tested benefits are assessed against a real reference period rather "
        "than an empty one. On by default since D-011; set false only to reproduce the "
        "Phase 0 single-year wiring — see docs/DECISIONS.md D-005 and D-011.",
    )
    debug: bool = False

    @model_validator(mode="after")
    def _check_envelope(self) -> SimulateRequest:
        if self.emtr and self.tier == "light":
            raise ValueError(
                "emtr=true exige tier='full' : le taux marginal effectif est calculé par "
                "différence finie sur le revenu disponible, ce qui demande la cascade complète "
                "des prestations."
            )
        born_late = [
            a.annee_naissance for a in self.household.adults if a.annee_naissance > self.year
        ] + [c.annee_naissance for c in self.household.children if c.annee_naissance > self.year]
        if born_late:
            raise ValueError(
                f"Année de naissance postérieure à l'année simulée ({self.year}) : {born_late}."
            )
        return self


# --------------------------------------------------------------------------- #
# Response
# --------------------------------------------------------------------------- #
class ResultRows(BaseModel):
    """One column of the results table. All amounts are annual EUR, positive
    magnitudes, summed across household members where the variable is individual.

    The famille/ménage rows are `None` in a `light` response — they were not
    computed, which is not the same as being zero."""

    model_config = ConfigDict(extra="forbid")

    # salary block (individu, summed over members)
    salaire_brut: float
    salaire_super_brut: float
    salaire_net: float
    salaire_imposable: float
    cotisations_salariales: float
    cotisations_employeur: float
    csg_deductible: float
    csg_imposable: float
    crds: float
    # tax block (foyer fiscal)
    ir: float
    ir_avant_reductions: float
    parts_fiscales: float
    revenu_fiscal_reference: float
    # benefits block (famille) — full tier only
    af: float | None = None
    ppa: float | None = None
    rsa: float | None = None
    aide_logement: float | None = None
    # bottom line (ménage) — full tier only
    revenu_disponible: float | None = None
    # unnormalised engine output, debug requests only
    raw: dict[str, float] | None = None


class Timings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    build_ms: float
    compute_ms: float
    emtr_ms: float | None = None
    total_ms: float
    reform_cache_hit: bool | None = None


class SimulateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    baseline: ResultRows
    reform: ResultRows | None = None
    delta: ResultRows | None = None
    emtr: float | None = None
    emtr_reform: float | None = None
    tier: Tier
    year: int
    historique_revenus: bool
    timings: Timings
    engine: dict[str, str]


# --------------------------------------------------------------------------- #
# GET /parameters/ir
# --------------------------------------------------------------------------- #
class DecoteParameters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    seuil_celib: float
    seuil_couple: float
    taux: float


class CsgActiviteParameters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    imposable: float
    deductible: float


class IRParameters(BaseModel):
    """Current law, read live from the parameter tree — never hardcoded (spec §4)."""

    model_config = ConfigDict(extra="forbid")

    year: int
    bareme: list[IRBracket]
    decote: DecoteParameters
    plafond_qf_demi_part: float
    csg_activite: CsgActiviteParameters


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    openfisca_france: str
    openfisca_core: str
    warm: bool
    licence: str = "AGPL-3.0-or-later"
    source_url: str | None = Field(
        default=None,
        description="Where this running version's Corresponding Source can be obtained. "
        "AGPL section 13 requires offering it to anyone interacting with the software "
        "over a network; set IMPOTS_SOURCE_URL before deploying. None means the "
        "server has not been told, which is only acceptable when it is not reachable "
        "by anyone else.",
    )


# --------------------------------------------------------------------------- #
# Population (L1) — PHASE1_SPEC §6
#
# Only the quick tier is reachable over HTTP. A full-tier run over 199 451
# households is minutes, not seconds, and belongs to the CLI (§1.1).
# --------------------------------------------------------------------------- #
PopulationTier = Literal["quick"]

#: Households in a quick-tier subsample. Deterministic, PPS, self-weighting.
QUICK_TIER_HOUSEHOLDS = 20_000


class BehaviouralBand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    p10: float
    p50: float
    p90: float
    unit: str = "EUR"


class BehaviouralChannel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    label: str
    applies: bool
    central: float | None = None
    unit: str = "EUR"
    message: str = ""
    grade: str | None = None
    diagnostics: dict[str, Any] = Field(default_factory=dict)


class Behavioural(BaseModel):
    """The band around a mechanical figure (L3).

    `mechanical` is repeated here on purpose: a client reading this block must be
    able to see that the band is a range *around* the mechanical number and never a
    replacement for it.
    """

    model_config = ConfigDict(extra="forbid")

    mechanical: float
    band: BehaviouralBand | None = None
    grade: str
    grade_reason: str = ""
    channels: list[BehaviouralChannel] = Field(default_factory=list)
    seed: int
    draws: int
    parameters_vintage: str = ""
    notes: list[str] = Field(default_factory=list)
    emtr_households: int | None = None
    """How many households the marginal rates were computed on, when a channel needed
    them. Stated because it is a subsample and the band inherits its noise."""


class PopulationSimulateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reform: ReformSpec
    year: Annotated[int, Field(ge=MIN_YEAR, le=MAX_YEAR)] = 2024
    tier: PopulationTier = "quick"
    behavioural: bool = False
    """Opt-in, because the marginal rates a behavioural band needs are two more
    full-tier runs. Off by default so the mechanical answer stays fast, and the
    response says how many households the rates were computed on when it is on."""

    @model_validator(mode="after")
    def _check_reform(self) -> PopulationSimulateRequest:
        if self.reform.is_empty():
            raise ValueError(
                "Une réforme est requise : sans réforme, /population/baseline sert "
                "les agrégats de référence déjà calculés, sans refaire tourner le moteur."
            )
        return self


class DecileRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decile: int
    n_households: float
    mean_niveau_de_vie: float
    mean_baseline: float
    mean_reform: float | None = None
    mean_delta: float | None = None
    share_winners: float | None = None
    share_losers: float | None = None
    share_unaffected: float | None = None


class ReconciliationLine(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str
    simulated: float | None
    published: float
    residual: float | None
    use: str
    status: str
    source: str


class PopulationMeta(BaseModel):
    """Which population produced the numbers on screen, and how far it can be trusted."""

    model_config = ConfigDict(extra="forbid")

    vintage: str
    branch: str
    households: float
    persons: float
    tier: str
    sampled_households: int | None
    note: str
    limitations: list[str]


class PopulationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    meta: PopulationMeta
    totals: dict[str, float]
    totals_reform: dict[str, float] = Field(default_factory=dict)
    deltas: dict[str, float] = Field(default_factory=dict)
    reform_cost: float | None = None
    deciles: list[DecileRow] = Field(default_factory=list)
    reconciliation: list[ReconciliationLine] = Field(default_factory=list)
    behavioural: Behavioural | None = None
    timings: dict[str, float] = Field(default_factory=dict)


# --------------------------------------------------------------------------- #
# Firms (Phase 2) — PHASE2_SPEC §4
#
# Synchronous: the whole IS population prices in well under a second, so there is
# no quick tier and no batch machinery on this side.
# --------------------------------------------------------------------------- #
class FirmSimulateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reform: FirmReformSpec
    year: Annotated[int, Field(ge=2022, le=MAX_YEAR + 4)] = 2026

    @model_validator(mode="after")
    def _check_reform(self) -> FirmSimulateRequest:
        if self.reform.is_empty():
            raise ValueError(
                "Une réforme est requise : sans réforme, /entreprises/baseline sert "
                "les agrégats de référence sans refaire tourner le moteur."
            )
        return self


class FirmCell(BaseModel):
    """One sector x size cell of the incidence table."""

    model_config = ConfigDict(extra="forbid")

    naf_section: str
    taille: str
    n_firms: float
    turnover: float
    tax_baseline: float
    is_brut: float
    mean_effective_rate: float
    tax_reform: float | None = None
    mean_delta: float | None = None
    delta_effective_rate: float | None = None
    share_affected: float | None = None


class FirmSizeRow(BaseModel):
    """The effective-rate profile — the firm analogue of the interdecile ratio."""

    model_config = ConfigDict(extra="forbid")

    taille: str
    n_firms: float
    mean_effective_rate: float
    median_effective_rate: float
    share_zero_tax: float


class FirmMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vintage: str
    year: int
    cells_are_synthetic: bool
    n_firms: float
    turnover: float
    share_zero_is: float
    note: str
    limitations: list[str]


class FirmResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    meta: FirmMeta
    totals: dict[str, float]
    totals_reform: dict[str, float] = Field(default_factory=dict)
    deltas: dict[str, float] = Field(default_factory=dict)
    reform_cost: float | None = None
    cells: list[FirmCell] = Field(default_factory=list)
    by_size: list[FirmSizeRow] = Field(default_factory=list)
    behavioural: Behavioural | None = None
    timings: dict[str, float] = Field(default_factory=dict)
