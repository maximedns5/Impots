"""FirmReformSpec -> an openfisca `Reform` (PHASE2_SPEC §1.3).

A whitelist of named knobs, never raw parameter paths — same reasoning as the
household side: raw paths are an injection surface into the parameter tree and
make the cache key unbounded.

The knobs are chosen to price the questions actually being asked of French
corporate tax: move the IS rate, widen or narrow the PME reduced-rate slice,
renew or drop the CEBGE, change the C3S abattement. `cebge_seuils_et_taux` is
paired because a threshold without its rate is not a policy.
"""

from __future__ import annotations

from itertools import pairwise
from typing import Annotated, Any

from openfisca_core import periods
from openfisca_core.reforms import Reform
from pydantic import BaseModel, ConfigDict, Field, model_validator

from impots.parameters import (
    create_parameter,
    differs,
    exists_at,
    resolve,
    update_existing,
)

#: knob -> path in the parameter tree. Never `is`: a node of that name breaks
#: attribute access on the parameter tree, since it is a Python keyword.
SCALAR_KNOBS: dict[str, tuple[str, ...]] = {
    "is_taux_normal": ("impot_societes", "taux_normal"),
    "is_taux_reduit": ("impot_societes", "taux_reduit"),
    "is_plafond_taux_reduit": ("impot_societes", "plafond_taux_reduit"),
    "is_pme_plafond_ca": ("impot_societes", "plafond_ca_taux_reduit"),
    "cs_taux": ("impot_societes", "contribution_sociale", "taux"),
    "cs_abattement": ("impot_societes", "contribution_sociale", "abattement"),
    "c3s_taux": ("c3s", "taux"),
    "c3s_abattement": ("c3s", "abattement"),
    "cvae_taux_max": ("cvae", "taux_max"),
    "cvae_degrevement": ("cvae", "degrevement", "montant"),
}

#: The CEBGE knob is paired rather than scalar, and these are the paths one tranche
#: writes to: its threshold, its rate, and the top of the 100 M€ band over which the
#: rate ramps up from zero. The band is *derived* from the threshold rather than
#: exposed, so a reform cannot leave a threshold and its smoothing band inconsistent
#: — which would silently tax a firm at a rate the spec never asked for.
CEBGE_TRANCHE_PATHS: tuple[tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]], ...] = (
    (("cebge", "seuil_ca"), ("cebge", "taux_base"), ("cebge", "lissage", "borne_haute")),
    (
        ("cebge", "seuil_ca_taux_majore"),
        ("cebge", "taux_majore"),
        ("cebge", "lissage", "borne_haute_taux_majore"),
    ),
)


#: The CVAE's whole schedule, as the law moves it from one year to the next (D-254): the
#: ceiling rate, the slopes and intercepts of the brackets below it, and the
#: complementary dégrèvement, which the law scales with them (188, 125, 63 €). The
#: thresholds, the caps on value added and the franchise are not rates, and the law
#: leaves them where they are.
CVAE_SCHEDULE: tuple[tuple[str, ...], ...] = (
    ("cvae", "taux_max"),
    ("cvae", "bareme", "pente_t1"), ("cvae", "bareme", "pente_t2"),
    ("cvae", "bareme", "pente_t3"),
    ("cvae", "bareme", "base_t2"), ("cvae", "bareme", "base_t3"),
    ("cvae", "degrevement", "montant"),
)


class CebgeTranche(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)  # D-173

    seuil_ca: Annotated[float, Field(ge=0)]
    taux: Annotated[float, Field(ge=0.0, le=1.0)]


class FirmReformSpec(BaseModel):
    """The whitelisted firm-tax knobs. All optional; an empty spec is no reform."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)  # D-173

    is_taux_normal: Annotated[float, Field(ge=0.0, le=1.0)] | None = None
    is_taux_reduit: Annotated[float, Field(ge=0.0, le=1.0)] | None = None
    is_plafond_taux_reduit: Annotated[float, Field(ge=0, le=100_000_000)] | None = None
    is_pme_plafond_ca: Annotated[float, Field(ge=0, le=1_000_000_000)] | None = None
    cs_taux: Annotated[float, Field(ge=0.0, le=1.0)] | None = None
    cs_abattement: Annotated[float, Field(ge=0, le=1_000_000_000)] | None = None
    c3s_taux: Annotated[float, Field(ge=0.0, le=1.0)] | None = None
    c3s_abattement: Annotated[float, Field(ge=0, le=1_000_000_000)] | None = None
    cvae_taux_max: Annotated[float, Field(ge=0.0, le=1.0)] | None = None
    cvae_degrevement: Annotated[float, Field(ge=0, le=1_000_000)] | None = None
    cvae_echelle: Annotated[float, Field(ge=0.0, le=3.0)] | None = Field(
        default=None,
        description="The CVAE's whole schedule of the year, scaled: the ceiling, the "
        "brackets below it and the dégrèvement, as the law moves them itself (D-254). 0 "
        "abolishes it, 0.5 halves it. In a year where the law has abolished it, there is "
        "nothing to scale. Not with `cvae_taux_max` or `cvae_degrevement`, which it "
        "already moves.")
    cir_taux: Annotated[float, Field(ge=0.0, le=1.0)] | None = Field(
        default=None,
        description="The CIR research rate on each declarant's expenses up to 100 M€. "
        "Not a parameter of the firm system: priced on the créance of a GECIR millésime "
        "by `impots.agregats.cir`, with its banner, and never inside `reform_cost` "
        "(D-222).")
    cir_taux_au_dela: Annotated[float, Field(ge=0.0, le=1.0)] | None = Field(
        default=None,
        description="The CIR research rate on the expenses above 100 M€; same route.")
    cebge_seuils_et_taux: list[CebgeTranche] | None = Field(
        default=None,
        max_length=len(CEBGE_TRANCHE_PATHS),
        description="Paired thresholds and rates for the CEBGE, lowest first. A "
        "threshold without its rate is not a policy, so they move together or not at "
        "all. At most two tranches, matching the statute's own shape.",
    )
    impots_production_baisse: Annotated[float, Field(ge=0, le=200e9)] | None = Field(
        default=None,
        description="Une enveloppe de baisse des impôts de production, en euros par an (but "
        "21, étape 2). Les seuls impôts de production que le moteur porte sont la CVAE et la "
        "C3S : la baisse est répartie entre elles (`impots_production_part_cvae`, au prorata "
        "de leur rendement par défaut) et traduite, sur la population de la passe, en un "
        "facteur du barème de la CVAE et un taux de C3S tels que leur rendement statique "
        "baisse de l'enveloppe. Son coût est l'enveloppe par construction (D-380), le "
        "facteur de la CVAE réglé sur la passe au millionième ; ce qu'elle apprend est qui y gagne, le retour "
        "d'IS de la déductibilité (D-347) et la dette. Une enveloppe au-delà de ce que la "
        "CVAE et la C3S rapportent est refusée : la CFE, la taxe foncière des entreprises, "
        "le versement mobilité et les autres impôts de production ne sont pas dans le "
        "moteur. Pas avec les boutons de la CVAE ni `c3s_taux`, qu'elle règle déjà.")
    impots_production_part_cvae: Annotated[float, Field(ge=0.0, le=1.0)] | None = Field(
        default=None,
        description="La part de l'enveloppe portée par la CVAE, le reste par la C3S. Sans "
        "elle, le prorata de leur rendement sur la population de la passe. L'hypothèse de "
        "traduction ; sa plage va de 0 (toute la baisse sur la C3S) à 1 (toute sur la "
        "CVAE), dans la limite de ce que chacune rapporte.")
    cebge_prorogation_largeur: Annotated[float, Field(gt=0, le=1_000_000_000)] | None = Field(
        default=None,
        description="Revive the CEBGE in a year where the tree no longer carries it, with "
        "this smoothing-band width in EUR. The width must come from the text that revives "
        "the contribution (PLF 2027 art. 15: « 1,5 milliard … 1,6 milliard », « au "
        "dénominateur, 100 millions d'euros »); nothing is derived from a lapsed year. "
        "Requires both tranches of `cebge_seuils_et_taux`, and is refused in a year where "
        "the CEBGE still exists, since creating what exists would bypass D-044.",
    )

    @model_validator(mode="after")
    def _check(self) -> FirmReformSpec:
        both_rates_set = self.is_taux_reduit is not None and self.is_taux_normal is not None
        if both_rates_set and self.is_taux_reduit > self.is_taux_normal:
            raise ValueError(
                "le taux réduit dépasse le taux normal : la tranche réduite "
                "deviendrait une surtaxe, ce qui n'est presque jamais l'intention."
            )
        if self.cebge_seuils_et_taux is not None:
            tranches = self.cebge_seuils_et_taux
            if not tranches:
                raise ValueError("cebge_seuils_et_taux ne peut pas être une liste vide")
            seuils = [t.seuil_ca for t in tranches]
            if any(a >= b for a, b in pairwise(seuils)):
                raise ValueError(
                    f"les seuils de CA doivent être strictement croissants ; reçu {seuils}"
                )
        if self.cvae_echelle is not None:
            moved = [knob for knob in ("cvae_taux_max", "cvae_degrevement")
                     if getattr(self, knob) is not None]
            if moved:
                raise ValueError(
                    f"cvae_echelle avec {moved} : le facteur règle déjà le barème entier, "
                    f"ce plafond et ce dégrèvement compris ; lequel l'emporterait serait "
                    f"l'ordre des écritures, pas une politique.")
        if self.impots_production_part_cvae is not None \
                and self.impots_production_baisse is None:
            raise ValueError("impots_production_part_cvae sans impots_production_baisse : "
                             "une part de rien.")
        if self.impots_production_baisse is not None:
            moved = [knob for knob in ("cvae_echelle", "cvae_taux_max", "cvae_degrevement",
                                       "c3s_taux")
                     if getattr(self, knob) is not None]
            if moved:
                raise ValueError(
                    f"impots_production_baisse avec {moved} : l'enveloppe règle déjà le "
                    f"barème de la CVAE et le taux de la C3S.")
        if self.cebge_prorogation_largeur is not None and len(
                self.cebge_seuils_et_taux or ()) != len(CEBGE_TRANCHE_PATHS):
            raise ValueError(
                "une prorogation de la CEBGE rétablit tout son barème : "
                "cebge_seuils_et_taux doit en donner les deux tranches. N'en créer "
                "qu'une laisserait l'autre nulle, et la formule lit les deux.")
        return self

    def is_empty(self) -> bool:
        """True when no knob is set — treated as no reform rather than as an identity
        reform, so nothing is rebuilt to prove that nothing changed."""
        return not self.model_dump(exclude_none=True)


def _largeur(parameters: Any, instant: str) -> float:
    """Width of the CEBGE smoothing bands, or a refusal.

    The CEBGE lapses after its second exercice, and its parameters go null with it.
    A reform that revives it in a later year therefore has no band width to derive
    the smoothing from — and inventing 100 M€ back would be putting a number into
    the tree that no source supports for that year. Refusing says so out loud.
    """
    width = resolve(parameters, ("cebge", "lissage", "largeur"))(instant)
    if width is None:
        raise ValueError(
            f"la CEBGE n'existe plus au {instant} : ses paramètres sont nuls, donc la "
            "largeur de la bande de lissage n'est pas définie et le barème réformé "
            "serait une falaise. Rétablir la CEBGE demande un paramétrage daté, pas "
            "un curseur : `cebge_prorogation_largeur`, avec la largeur que le texte de "
            "rétablissement fixe."
        )
    return float(width)


def _retablir_cebge(parameters: Any, spec: FirmReformSpec, start: Any, instant: str) -> None:
    """Bring the CEBGE back for a year where it has lapsed — by CREATING its parameters.

    `update_existing` refuses this, and must: writing a parameter that does not exist
    at the instant is how a reform once reported success and changed nothing (D-044).
    Creation goes through `create_parameter`, the deliberately named door, and only
    here, only for a year where the contribution is gone, and only with a band width
    the caller declares from the reviving text. Where the CEBGE still exists, creating
    it would be the bypass that door exists to prevent.
    """
    if exists_at(parameters, ("cebge", "taux_base"), instant):
        raise ValueError(
            f"la CEBGE existe déjà au {instant} : il n'y a rien à rétablir. La déplacer "
            "relève de cebge_seuils_et_taux seul ; créer ce qui existe contournerait la "
            "garde de D-044.")
    largeur = float(spec.cebge_prorogation_largeur or 0.0)
    create_parameter(parameters, ("cebge", "lissage", "largeur"), start=start, value=largeur)
    for tranche, (seuil_path, taux_path, borne_path) in zip(
            spec.cebge_seuils_et_taux or (), CEBGE_TRANCHE_PATHS, strict=True):
        create_parameter(parameters, seuil_path, start=start, value=tranche.seuil_ca)
        create_parameter(parameters, taux_path, start=start, value=tranche.taux)
        create_parameter(parameters, borne_path, start=start,
                         value=tranche.seuil_ca + largeur)


def _scale_cvae(parameters: Any, factor: float, start: Any, instant: str) -> None:
    """The year's whole CVAE schedule times `factor`, read on the tree being reformed —
    the law of that year, cloned. Where the law has abolished the CVAE its schedule is
    null, and there is nothing to scale: nothing is written, and the year costs
    nothing (D-254)."""
    for path in CVAE_SCHEDULE:
        law = resolve(parameters, path)(instant)
        if law is None:
            continue
        update_existing(parameters, path, start=start, value=factor * float(law),
                        instant=instant)


def make_reform(spec: FirmReformSpec, year: int, name: str) -> type[Reform]:
    """The `Reform` applying `spec` from `{year}-01-01`.

    `Reform(system)` clones the parameter tree, so the baseline survives — the
    property `test_no_mutation` keeps honest on the household side and does the
    same here.
    """
    if spec.impots_production_baisse is not None:
        raise ValueError(
            "une enveloppe d'impôts de production se traduit sur la population de la passe "
            "(`traduire_enveloppe`, que `runner.run` appelle) avant d'être une réforme : "
            "son facteur dépend de ce que la CVAE et la C3S y rapportent.")
    start = periods.instant(f"{year}-01-01")
    instant = f"{year}-01-01"
    reform_name = f"impots-firm-reform:{name}"

    class FirmReform(Reform):
        name = reform_name

        def apply(self) -> None:
            def modify(parameters: Any) -> Any:
                for knob, path in SCALAR_KNOBS.items():
                    value = getattr(spec, knob)
                    if value is not None:
                        update_existing(parameters, path, start=start, value=value,
                                        instant=instant)
                if spec.cvae_echelle is not None:
                    _scale_cvae(parameters, spec.cvae_echelle, start, instant)
                if spec.cebge_prorogation_largeur is not None:
                    _retablir_cebge(parameters, spec, start, instant)
                    return parameters
                largeur = _largeur(parameters, instant) if spec.cebge_seuils_et_taux else 0.0
                for tranche, paths in zip(
                    spec.cebge_seuils_et_taux or (), CEBGE_TRANCHE_PATHS, strict=False
                ):
                    seuil_path, taux_path, borne_path = paths
                    update_existing(parameters, seuil_path, start=start,
                                    value=tranche.seuil_ca, instant=instant)
                    update_existing(parameters, taux_path, start=start,
                                    value=tranche.taux, instant=instant)
                    update_existing(parameters, borne_path, start=start,
                                    value=tranche.seuil_ca + largeur, instant=instant)
                return parameters

            self.modify_parameters(modifier_function=modify)

    return FirmReform


def _cvae_read_back(system: Any, factor: float, instant: str) -> list[str]:
    """Each rate of the schedule against `factor` times the BASELINE's, not the reformed
    tree's: a reform that moved the law it is checked against would define its own
    answer. Where the baseline has no CVAE, the reformed tree must have none either."""
    from impots.entreprises.system import baseline as _baseline

    problems = []
    for path in CVAE_SCHEDULE:
        law = resolve(_baseline().parameters, path)(instant)
        got = resolve(system.parameters, path)(instant)
        name = ".".join(path)
        if law is None:
            if got is not None:
                problems.append(f"cvae_echelle: {name} vaut {got} là où la loi n'a plus de "
                                f"CVAE")
            continue
        wanted = factor * float(law)
        if got is None or differs(float(got), wanted):
            problems.append(f"cvae_echelle: {name} demandé {wanted}, appliqué {got}")
    return problems


def _knob_paths(knob: str) -> tuple[tuple[str, ...], ...]:
    """The parameters a knob writes, for `law_moves`. The CIR's knobs write none: they
    are priced on the créance flow, outside the tree (D-222)."""
    if knob in SCALAR_KNOBS:
        return (SCALAR_KNOBS[knob],)
    if knob == "cvae_echelle":
        return CVAE_SCHEDULE
    if knob in ("impots_production_baisse", "impots_production_part_cvae"):
        return (*CVAE_SCHEDULE, SCALAR_KNOBS["c3s_taux"])
    if knob in ("cebge_seuils_et_taux", "cebge_prorogation_largeur"):
        return (*(path for paths in CEBGE_TRANCHE_PATHS for path in paths),
                ("cebge", "lissage", "largeur"))
    return ()


def law_moves(spec: FirmReformSpec, parameters: Any, first: int, last: int) -> dict[str, int]:
    """For each knob `spec` sets, the first year after `first`, up to `last`, in which the
    law of a parameter it writes is not that of `first`; knobs whose law holds are left
    out. What a path that carries `first` over the years cannot see (D-254)."""
    def law(path: tuple[str, ...], year: int) -> Any:
        try:
            return resolve(parameters, path)(f"{year}-01-01")
        except (AttributeError, KeyError):
            return None

    out: dict[str, int] = {}
    for knob in spec.model_dump(exclude_none=True):
        for year in range(first + 1, last + 1):
            if any(law(path, year) != law(path, first) for path in _knob_paths(knob)):
                out[knob] = year
                break
    return out


def verify_scales(system: Any, spec: FirmReformSpec, year: int) -> None:
    """Read the reformed parameters back and refuse anything that is not what was asked.

    D-007 made portable. On the household side the prescribed way of neutralising
    surplus barème brackets silently *summed* their rates — three 40 % brackets
    became one at 120 %, and a 240 k€ household was charged 158 160 € instead of
    58 720 € with no error raised anywhere. Nothing here is barème-shaped yet; the
    CVAE schedule will be, and the guard exists before the thing it guards.
    """
    instant = f"{year}-01-01"
    problems: list[str] = []
    for knob, path in SCALAR_KNOBS.items():
        wanted = getattr(spec, knob)
        if wanted is None:
            continue
        got = float(resolve(system.parameters, path)(instant))
        if differs(got, wanted):
            problems.append(f"{knob}: demandé {wanted}, appliqué {got}")
    if spec.cvae_echelle is not None:
        problems += _cvae_read_back(system, spec.cvae_echelle, instant)
    if not spec.cebge_seuils_et_taux:
        if problems:
            raise AssertionError(
                "les paramètres appliqués ne correspondent pas à la réforme demandée — "
                + " ; ".join(problems)
            )
        return
    # From the BASELINE, not from the system under test: the expected smoothing bound
    # is `seuil + largeur`, so reading `largeur` out of the reformed tree would let a
    # reform that moved it define the answer it is checked against.
    from impots.entreprises.system import baseline as _baseline

    if spec.cebge_prorogation_largeur is not None:
        # A revived CEBGE has no baseline band to read: the expected width is the one
        # the SPEC declares — still independent of the system under test — and the
        # created width is read back like every other value.
        largeur = float(spec.cebge_prorogation_largeur)
        got_width = resolve(system.parameters, ("cebge", "lissage", "largeur"))(instant)
        if got_width is None or differs(float(got_width), largeur):
            problems.append(f"cebge_prorogation_largeur: demandé {largeur}, appliqué "
                            f"{got_width}")
    else:
        largeur = _largeur(_baseline().parameters, instant)
    for index, (tranche, paths) in enumerate(
        zip(spec.cebge_seuils_et_taux or (), CEBGE_TRANCHE_PATHS, strict=False)
    ):
        seuil_path, taux_path, borne_path = paths
        for label, path, wanted_value in (
            ("seuil_ca", seuil_path, tranche.seuil_ca),
            ("taux", taux_path, tranche.taux),
            ("borne de lissage", borne_path, tranche.seuil_ca + largeur),
        ):
            got = float(resolve(system.parameters, path)(instant))
            if differs(got, wanted_value):
                problems.append(
                    f"cebge_seuils_et_taux[{index}].{label}: demandé {wanted_value}, "
                    f"appliqué {got}"
                )
    if problems:
        raise AssertionError(
            "les paramètres appliqués ne correspondent pas à la réforme demandée — "
            + "; ".join(problems)
        )


class EnveloppeError(ValueError):
    """Une enveloppe d'impôts de production qui ne se traduit pas sur ce que le moteur porte."""


def traduire_enveloppe(spec: FirmReformSpec, cvae_loi: float, c3s_loi: float,
                       c3s_taux_loi: float) -> tuple[FirmReformSpec, dict[str, float]]:
    """L'enveloppe de `spec` traduite en un facteur du barème de la CVAE et un taux de C3S,
    sur ce que les deux rapportent dans la population de la passe (`cvae_loi`, `c3s_loi`, en
    euros pondérés) : la réforme, sans l'enveloppe, et la traduction, pour le rapport.

    La règle, une hypothèse dite : la baisse est répartie entre la CVAE et la C3S, au prorata
    de leur rendement sans `impots_production_part_cvae`, et chacune baisse de sa part, à
    proportion — un facteur sur tout le barème de la CVAE (ses taux et son dégrèvement,
    comme `cvae_echelle`), une baisse du taux de la C3S. La C3S est linéaire dans son taux ;
    la CVAE ne l'est qu'à l'arrondi de ses taux au centième près, et `runner.run` règle son
    facteur sur la passe jusqu'au millionième de son rendement. Refusée au-delà de ce que
    chacune rapporte : le moteur ne porte pas les autres impôts de production."""
    baisse = float(spec.impots_production_baisse or 0.0)
    total = cvae_loi + c3s_loi
    if baisse > total * (1 + 1e-9):
        raise EnveloppeError(
            f"une baisse de {baisse / 1e9:.2f} Md€ des impôts de production : la CVAE et la "
            f"C3S, les seuls que le moteur porte, rapportent {total / 1e9:.2f} Md€ sur cette "
            f"population. La CFE, la taxe foncière des entreprises, le versement mobilité et "
            f"les autres n'y sont pas ; le reste de l'enveloppe ne se traduirait en rien.")
    part = (spec.impots_production_part_cvae if spec.impots_production_part_cvae is not None
            else (cvae_loi / total if total > 0 else 0.0))
    baisse_cvae, baisse_c3s = part * baisse, (1.0 - part) * baisse
    for nom, cut, rendement in (("CVAE", baisse_cvae, cvae_loi), ("C3S", baisse_c3s, c3s_loi)):
        if cut > rendement * (1 + 1e-9):
            raise EnveloppeError(
                f"la part de l'enveloppe portée par la {nom}, {cut / 1e9:.2f} Md€, dépasse ce "
                f"qu'elle rapporte sur cette population, {rendement / 1e9:.2f} Md€.")
    fields = spec.model_dump(exclude_none=True)
    fields.pop("impots_production_baisse", None)
    fields.pop("impots_production_part_cvae", None)
    echelle = 1.0 - baisse_cvae / cvae_loi if cvae_loi > 0 else 1.0
    taux = c3s_taux_loi * (1.0 - baisse_c3s / c3s_loi) if c3s_loi > 0 else c3s_taux_loi
    fields["cvae_echelle"] = max(0.0, min(1.0, echelle))
    fields["c3s_taux"] = max(0.0, taux)
    traduction = {"enveloppe_eur": baisse, "part_cvae": part, "baisse_cvae_eur": baisse_cvae,
                  "baisse_c3s_eur": baisse_c3s, "cvae_echelle": fields["cvae_echelle"],
                  "c3s_taux": fields["c3s_taux"], "cvae_loi_eur": cvae_loi,
                  "c3s_loi_eur": c3s_loi}
    return FirmReformSpec.model_validate(fields), traduction
