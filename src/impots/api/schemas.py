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


class Niches(BaseModel):
    """Bases for the réductions and crédits d'impôt (B3).

    Without them every niche is zero, which is why the population's income tax is a
    BARÈME figure and is validated against the barème line (98.84 bn) rather than
    against net receipts: the 19.53 bn of réductions and crédits nationally is money
    the model had no way to express.

    **Amounts are for the simulated year only, not spread across the income history.**
    The three-year history exists to give means-tested benefits a realistic reference
    period; asserting three identical years of charitable giving would be a different
    claim, and one nobody made.

    Every rate below was verified by computation rather than read off a rate table:
    5 000 € of home help returns a 2 500 € credit, 1 000 € of donations 660 € or 750 €
    depending on the class, 200 € of union dues 132 €.
    """

    model_config = ConfigDict(extra="forbid")

    salarie_domicile: Annotated[float, Field(ge=0, le=100_000)] = 0.0
    """Sommes versées pour l'emploi d'un salarié à domicile (case 7DB). A CRÉDIT at
    50 %, so it reaches households with no tax to reduce — which is why it is the
    largest niche and why it cannot be imputed to taxpayers alone."""
    salarie_domicile_aides_percues: Annotated[float, Field(ge=0, le=100_000)] = 0.0
    """Aides perçues for that employment — APA, PCH, CESU préfinancé (case 7DR). They
    reduce the eligible base, so omitting them overstates the credit."""
    dons_oeuvres: Annotated[float, Field(ge=0, le=1_000_000)] = 0.0
    """Dons to organismes d'intérêt général (case 7UF) — 66 %."""
    dons_aide_personnes_en_difficulte: Annotated[float, Field(ge=0, le=1_000_000)] = 0.0
    """Dons to organismes d'aide aux personnes en difficulté (case 7UD) — 75 %. A
    separate case because the rate and the ceiling both differ."""
    frais_garde_par_enfant: Annotated[list[float], Field(max_length=3)] = Field(
        default_factory=list)
    """Frais de garde, PER CHILD under six (cases 7GA, 7GB, 7GC in order).

    A list rather than a total because the ceiling applies per child: splitting one
    total equally would give a different — and generally larger — credit than an
    uneven real split whenever the ceiling binds.

    **THE ENGINE APPLIES NO ELIGIBILITY TEST**, and an earlier version of this
    docstring said it did. Measured: a household with a fifteen-year-old gets the
    credit, and so does a household with NO CHILDREN AT ALL. These cases are
    declaration boxes and openfisca trusts the declarant, exactly as the paper form
    does — eligibility is the administration's job, not the formula's. So the wire
    format checks it instead: `situations.assert_niche_eligibility` refuses more
    childcare amounts than there are children young enough to have them."""
    cotisations_syndicales: Annotated[list[float], Field(max_length=2)] = Field(
        default_factory=list)
    """Union dues, PER ADULT in order (case 7AC). Individual-level, unlike every other
    niche here, because the entitlement follows the member and not the foyer. Checked
    against the number of adults for the same reason as the childcare list."""
    enfants_college: Annotated[int, Field(ge=0, le=MAX_CHILDREN)] = 0
    enfants_lycee: Annotated[int, Field(ge=0, le=MAX_CHILDREN)] = 0
    enfants_superieur: Annotated[int, Field(ge=0, le=MAX_CHILDREN)] = 0
    """Counts of children in education (cases 7EA, 7EC, 7EF) — flat amounts per child,
    not a rate on a base: 61 €, 153 € and 183 € respectively as computed. Their sum is
    checked against the household's dependants, since the engine will otherwise grant a
    school-fees reduction to a childless foyer."""

    @property
    def declared_school_children(self) -> int:
        return self.enfants_college + self.enfants_lycee + self.enfants_superieur


#: Niche field -> the déclaration case it writes. One source of truth, so the wire
#: format, the situation builder and the tests cannot disagree about which box a field
#: lands in. Every case was enumerated out of the live variable registry, not from a
#: form: `f7d*` alone also contains five PME-subscription boxes and an invalidity flag,
#: and picking a plausible-looking name would have been picking the wrong one.
NICHE_CASES: dict[str, str] = {
    "salarie_domicile": "f7db",
    "salarie_domicile_aides_percues": "f7dr",
    "dons_oeuvres": "f7uf",
    "dons_aide_personnes_en_difficulte": "f7ud",
    "enfants_college": "f7ea",
    "enfants_lycee": "f7ec",
    "enfants_superieur": "f7ef",
}
#: The per-child childcare cases, in the order the list fills them.
NICHE_GARDE_CASES: tuple[str, ...] = ("f7ga", "f7gb", "f7gc")
#: Individual-level, so it is written onto the adults rather than the foyer fiscal.
NICHE_SYNDICALES_CASE = "f7ac"


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
    niches: Niches | None = None
    """Réductions and crédits d'impôt bases. Absent means every niche is zero, which
    is the engine answering as asked and not a wiring gap."""

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


#: The 2024 legal values of the two AF modulation ceilings, needed only so that a
#: reform moving ONE of them can be checked against the other's baseline. Pinned here
#: rather than read from the tree because a validator must not need a tax-benefit
#: system: `test_af_plafond_baselines_match_the_tree` keeps them honest.
AF_PLAFOND_TRANCHE_1_BASE_2024 = 62_474.0
AF_PLAFOND_TRANCHE_2_BASE_2024 = 87_430.0


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
    # Employer social contributions (D-038). Plafonds are in multiples of the SMIC,
    # which is why their ceiling is 10 and not 1: 1.6 is today's réduction générale.
    allegement_general_plafond: Annotated[float, Field(ge=0.0, le=10.0)] | None = None
    allegement_general_taux_50_et_plus: Annotated[float, Field(ge=0.0, le=1.0)] | None = None
    allegement_general_taux_moins_de_50: Annotated[float, Field(ge=0.0, le=1.0)] | None = None
    bandeau_maladie_plafond: Annotated[float, Field(ge=0.0, le=10.0)] | None = None
    bandeau_maladie_taux: Annotated[float, Field(ge=0.0, le=1.0)] | None = None
    bandeau_famille_plafond: Annotated[float, Field(ge=0.0, le=10.0)] | None = None
    bandeau_famille_taux: Annotated[float, Field(ge=0.0, le=1.0)] | None = None
    # Prestations (B1) — the spending side of the debate. Monthly amounts in euros,
    # rates as fractions, income ceilings in euros per year. The upper bounds are
    # deliberately generous: this tool exists to price proposals, including ones
    # nobody has made, and a bound tight enough to be "realistic" would be a
    # political judgement wearing a validation's clothes.
    rsa_montant_de_base: Annotated[float, Field(ge=0, le=5_000)] | None = None
    ppa_montant_de_base: Annotated[float, Field(ge=0, le=5_000)] | None = None
    ppa_pente: Annotated[float, Field(ge=0.0, le=1.0)] | None = None
    """The share of activity income added back before the taper — 61 % today. The
    single parameter that most directly sets the marginal rate a working household on
    the prime d'activité faces."""
    ppa_bonification_taux_max: Annotated[float, Field(ge=0.0, le=1.0)] | None = None
    bmaf: Annotated[float, Field(ge=0, le=5_000)] | None = None
    """The base every family benefit is a multiple of. Broad: it moves AF, CF, ASF and
    the rest together, not one of them."""
    af_taux_2_enfants: Annotated[float, Field(ge=0.0, le=5.0)] | None = None
    af_taux_3_enfants: Annotated[float, Field(ge=0.0, le=5.0)] | None = None
    af_modulation_taux_tranche_2: Annotated[float, Field(ge=0.0, le=1.0)] | None = None
    af_modulation_taux_tranche_3: Annotated[float, Field(ge=0.0, le=1.0)] | None = None
    """Setting both modulation tranches to 1 restores universal family allowances,
    which is a live proposal and is now one knob."""
    af_plafond_tranche_1_base: Annotated[float, Field(ge=0, le=1_000_000)] | None = None
    af_plafond_tranche_2_base: Annotated[float, Field(ge=0, le=1_000_000)] | None = None
    af_majoration_plafond_par_enfant: Annotated[float, Field(ge=0, le=100_000)] | None = None
    """The modulation ceilings the formula actually reads. It builds its own threshold
    from the `_base` value plus one majoration per child; the published
    `plafond_tranche_1` / `plafond_tranche_2` are derived figures no formula consults,
    and a knob aimed at them would move nothing."""
    al_minoration_forfaitaire: Annotated[float, Field(ge=0, le=1_000)] | None = None
    """The 2017 flat cut to housing benefit — five euros a month."""
    # IR niches (B3). Rates as fractions, ceilings in euros except
    # `dons_plafond_part_rfr`, which is a SHARE of the revenu fiscal de référence, and
    # `plafond_global_niches`, which caps the lot.
    saldom_taux: Annotated[float, Field(ge=0.0, le=1.0)] | None = None
    saldom_plafond: Annotated[float, Field(ge=0, le=200_000)] | None = None
    gardenf_taux: Annotated[float, Field(ge=0.0, le=1.0)] | None = None
    gardenf_plafond: Annotated[float, Field(ge=0, le=100_000)] | None = None
    """Per CHILD, not per household — 3 500 EUR today, and the ceiling that makes an
    uneven split of the same total worth more than an even one."""
    dons_taux: Annotated[float, Field(ge=0.0, le=1.0)] | None = None
    dons_plafond_part_rfr: Annotated[float, Field(ge=0.0, le=1.0)] | None = None
    """A share of the revenu fiscal de référence — 20 % today, not a euro amount."""
    dons_coluche_taux: Annotated[float, Field(ge=0.0, le=1.0)] | None = None
    dons_coluche_plafond: Annotated[float, Field(ge=0, le=100_000)] | None = None
    """The 75 % rate for donations to organisations helping people in difficulty, and
    the euro ceiling above which the ordinary 66 % takes over."""
    cotisations_syndicales_taux: Annotated[float, Field(ge=0.0, le=1.0)] | None = None
    frais_scolarite_college: Annotated[float, Field(ge=0, le=10_000)] | None = None
    frais_scolarite_lycee: Annotated[float, Field(ge=0, le=10_000)] | None = None
    frais_scolarite_superieur: Annotated[float, Field(ge=0, le=10_000)] | None = None
    """Flat amounts per child — 61, 153 and 183 EUR — not rates on a base."""
    plafond_global_niches: Annotated[float, Field(ge=0, le=1_000_000)] | None = None
    """The global cap on réductions and crédits, 10 000 EUR. It bites only on a
    household claiming more than that, so a chiffrage of it says nothing about anyone
    else."""

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

    @model_validator(mode="after")
    def _check_af_plafonds(self) -> ReformSpec:
        """The two modulation ceilings must stay ordered.

        Inverting them is not caught anywhere downstream: the AF formula branches on
        `above tranche 1` then `above tranche 2`, so a tranche-1 ceiling above the
        tranche-2 one produces a household that is in neither band and receives an
        amount belonging to neither rate. Measured, not theorised — lifting only the
        first ceiling gave a 150 k household 2 214 EUR where full rate is 1 771.

        The unset ceiling keeps its legal value, so a reform moving one must be checked
        against the other's baseline, not against nothing.
        """
        low, high = self.af_plafond_tranche_1_base, self.af_plafond_tranche_2_base
        if low is None and high is None:
            return self
        effective_low = low if low is not None else AF_PLAFOND_TRANCHE_1_BASE_2024
        effective_high = high if high is not None else AF_PLAFOND_TRANCHE_2_BASE_2024
        if effective_low > effective_high:
            raise ValueError(
                f"Le plafond de tranche 1 ({effective_low:,.0f} €) doit rester "
                f"inférieur ou égal à celui de tranche 2 ({effective_high:,.0f} €) : "
                f"au-dessus, un foyer n'est dans aucune des deux tranches et perçoit "
                f"un montant qui ne correspond à aucun taux."
                .replace(",", " ")
            )
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
    ir_avant_niches: float
    """After the décote, before réductions and crédits — the quantity the published
    barème figure measures."""
    reductions: float
    credits_impot: float
    """Réductions and crédits d'impôt. Zero for a household that declares no base,
    which is every household in the synthetic population — the 19.53 bn of niches
    nationally is why the population's IR is validated against the barème line and not
    against net receipts."""
    # benefits block (famille) — full tier only
    af: float | None = None
    ppa: float | None = None
    rsa: float | None = None
    aide_logement: float | None = None
    aefa: float | None = None
    """The prime de Noël. It rides on RSA eligibility rather than being reformed
    directly, which is how it went unitemised until the double-entry guard found it."""
    crds_pfam: float | None = None
    crds_logement: float | None = None
    crds_mini: float | None = None
    """CRDS levied on the benefits above — NEGATIVE, as the engine stores it, because a
    benefit's net value is `gross + crds`. Shown rather than folded in so a reader can
    see that the reported benefit is gross and the disposable income is not."""
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


class EmtrDecile(BaseModel):
    """One decile of the marginal-rate distribution — deciles of EMTR, not of income.

    Worth its own table rather than a footnote: France's marginal-rate distribution
    has a long right tail created by benefit tapers overlapping income tax, and the
    households in that tail are poor, not rich.
    """

    model_config = ConfigDict(extra="forbid")

    decile: int
    households: float
    emtr_median: float
    emtr_mean: float


class NarrowBandFlag(BaseModel):
    """Whether a reform's yield rests on a narrow wage band (D-046)."""

    model_config = ConfigDict(extra="forbid")

    share: float
    flagged: bool
    window: float
    share_threshold: float
    thresholds: list[float] = Field(default_factory=list)
    caveat: str = ""


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
    band: BehaviouralBand | None = None
    """The channel's own band, in its own unit. C4 reports a percentage change in
    investment, which is why a channel carries a band separately from the revenue one
    it may or may not belong in."""
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


# --------------------------------------------------------------------------- #
# Macro (Phase 4, L4) — PHASE4_SPEC §4
#
# The fan never renders without its strip, so the strip is REQUIRED on this block
# rather than optional: a client cannot receive quantiles without also receiving the
# cycle state, the design, the leakage, the horizon, the vintage and the grade.
# --------------------------------------------------------------------------- #
class MacroQuantiles(BaseModel):
    model_config = ConfigDict(extra="forbid")

    p10: float
    p50: float
    p90: float
    unit: str


class MacroDecomposition(BaseModel):
    """Where the spread comes from, reported separately (§1)."""

    model_config = ConfigDict(extra="forbid")

    horizon: str
    parameter: float
    scenario: float
    scenario_available: bool
    scenario_unavailable_because: str = ""


class MacroBranch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    label: str
    output_share: float
    employment_share: float


class MacroAssumptions(BaseModel):
    """Everything §4 forbids the fan to render without."""

    model_config = ConfigDict(extra="forbid")

    cycle_state: str
    design: str
    leakage: float | None = None
    leakage_applied: bool
    horizons: list[str]
    parameters_vintage: str
    grade: str
    covered_share: float
    instruments: list[str]
    simulation_conditions: str
    caveats: list[str] = Field(default_factory=list)
    banner: str


class Macro(BaseModel):
    """The macro fan (L4).

    `unavailable` is not an error state. Most reforms this repository can express have
    no macro path at all — transfers and corporate instruments have no published
    multiplier — and saying so with a reason is the designed outcome, not a failure.
    """

    model_config = ConfigDict(extra="forbid")

    available: bool
    unavailable_because: str = ""
    gdp: dict[str, MacroQuantiles] = Field(default_factory=dict)
    jobs: dict[str, MacroQuantiles] = Field(default_factory=dict)
    decomposition: list[MacroDecomposition] = Field(default_factory=list)
    composition: list[MacroBranch] = Field(default_factory=list)
    assumptions: MacroAssumptions | None = None
    notes: list[str] = Field(default_factory=list)
    uncovered: dict[str, str] = Field(default_factory=dict)
    """Instruments the reform moved that have no multiplier, with the reason each is
    missing. Carried so the client can show what the fan does NOT describe."""


class NicheBlindSpot(BaseModel):
    """A reform moved a niche this population cannot answer for (B3).

    Present rather than absent is the whole point: without it the response would carry
    a confident zero, and a confident zero here reads as "this credit does nothing"
    when it means "this population declares no such spending".
    """

    model_config = ConfigDict(extra="forbid")

    knobs: list[str]
    declared_base_eur: float
    """Réductions plus crédits across the population. Zero is the whole problem."""
    national_niches_eur: float = 19.53e9
    """What the omission is worth nationally, for scale — DGFiP, against a barème
    yield of 98.84 bn."""
    message: str


class PopulationSimulateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reform: ReformSpec
    year: Annotated[int, Field(ge=MIN_YEAR, le=MAX_YEAR)] = 2024
    tier: PopulationTier = "quick"
    behavioural: bool = False
    """Opt-in, because the marginal rates a behavioural band needs are two more
    full-tier runs. Off by default so the mechanical answer stays fast, and the
    response says how many households the rates were computed on when it is on."""
    macro: bool = False
    """Opt-in, and cheap — the fan is a thousand draws over a parsed table. Off by
    default because most reforms have no macro path and a block saying so on every
    response would be noise."""
    impute_niches: bool = False
    """Hand out réduction and crédit bases from the published DGFiP decile table, so a
    niche reform costs something. Opt-in and OFF BY DEFAULT because it is a
    CALIBRATION: the niche totals then match DGFiP by construction, and the net-yield
    reconciliation line stops being independent evidence for that component. It also
    costs an extra baseline pass, since the deciles are of a quantity the first pass
    has to compute."""

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
    emtr_deciles: list[EmtrDecile] = Field(default_factory=list)
    narrow_band: NarrowBandFlag | None = None
    reconciliation: list[ReconciliationLine] = Field(default_factory=list)
    behavioural: Behavioural | None = None
    macro: Macro | None = None
    niche_blind_spot: NicheBlindSpot | None = None
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
