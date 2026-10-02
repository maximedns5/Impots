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

from impots.parameters import differs, resolve, update_bracket, update_existing

if TYPE_CHECKING:  # pragma: no cover - typing only
    from impots.api.schemas import ReformSpec

PATH_BAREME = ("impot_revenu", "bareme_ir_depuis_1945", "bareme")
PATH_DECOTE = ("impot_revenu", "calcul_impot_revenu", "plaf_qf", "decote")
PATH_PLAFOND_QF_DEMI_PART = (
    "impot_revenu", "calcul_impot_revenu", "plaf_qf",
    "plafond_avantages_procures_par_demi_part", "general",
)
PATH_CSG_ACTIVITE = ("prelevements_sociaux", "contributions_sociales", "csg", "activite")
PATH_ABATTEMENT_PENSIONS = (
    "impot_revenu", "calcul_revenus_imposables", "deductions", "abatpen")

# --------------------------------------------------------------------------- #
# Prestations (B1). The other half of French fiscal debate: until now this tool
# could reform taxes but not transfers, which meant it could price an austerity
# package's revenue side and say nothing about its spending side.
#
# Every path below was READ OUT OF THE TREE at 2024-01-01, not transcribed from
# documentation. Two things that reading found and an assumption would have missed:
# `rsa.rsa_m.pente` exists as a child but its value is null at this instant, so the
# RSA taper is not parameterised and is not a knob; and the housing formula is nested
# per region and per family size, which is why only its one flat scalar appears here.
_MINIMA = ("prestations_sociales", "solidarite_insertion", "minima_sociaux")
PATH_RSA_MONTANT = (*_MINIMA, "rsa", "rsa_m", "montant_de_base_du_rsa")
#: The forfait logement — a flat deduction from the RSA for a household that is housed,
#: expressed as a share of the base amount and stepped by household size. It is the
#: second dial of the RSA after the base itself, and it moves the benefit DOWN: a
#: household with housing is treated as already receiving part of its needs in kind.
PATH_RSA_FORFAIT_LOGEMENT = (*_MINIMA, "rsa", "rsa_fl", "forfait_logement")
PATH_PPA = (*_MINIMA, "ppa", "pa_m")

_FAMILIALES = ("prestations_sociales", "prestations_familiales")
#: The base monthly amount every family benefit is a multiple of. Moving it moves AF,
#: CF, ASF and the rest together — a broad instrument, and labelled as one.
PATH_BMAF = (*_FAMILIALES, "bmaf", "bmaf")
_AF = (*_FAMILIALES, "prestations_generales", "af")
PATH_AF_TAUX = (*_AF, "af_cm", "taux")
PATH_AF_MODULATION = (*_AF, "af_cm", "modulation")
PATH_AF_RESSOURCES = (*_AF, "af_cond_ress")

#: The 2017 flat cut to housing benefit — five euros a month, and one of the most
#: argued-over scalars in the French welfare system. The rest of the housing formula
#: is nested per region (métropole, DOM, Mayotte, Saint-Pierre-et-Miquelon) and per
#: number of dependants, with a node shape that varies by year: the same trap as the
#: bandeau plafonds (D-044), and it needs its own increment rather than a knob bolted
#: on here.
#: Wealth tax (Phase 5). The IFI node's children are exactly `bareme`, `decote`,
#: `forfait_mobilier`, `plaf`, `reduc_exo` and `reduc_impot` — measured, and the
#: absence matters: **there is no seuil d'assujettissement parameter**. The 1,3 M
#: liability threshold that PHASE5_SPEC §3 asks for a knob on exists in the tree ONLY
#: as the décote's lower bound, which is why `ifi_decote_borne_inferieure` is the knob
#: that moves it. That is the "classic confusion" the spec warned about, resolved by
#: looking rather than by assuming a parameter with the obvious name exists.
_IFI = ("taxation_capital", "impot_fortune_immobiliere_ifi_partir_2018")
PATH_IFI_DECOTE = (*_IFI, "decote")
PATH_IFI_DONS = (*_IFI, "reduc_impot",
                 "reduction_dons_certains_organismes_interet_general")

PATH_AL_MINORATION = (
    "prestations_sociales", "aides_logement", "allocations_logement", "locatif",
    "minoration_forfaitaire",
)

# --------------------------------------------------------------------------- #
# IR niches (B3) — réductions and crédits d'impôt.
#
# Every path below was read out of the tree at 2024-01-01 and every value cross-checked
# against a COMPUTED outcome: 5 000 EUR of home help returns 2 500, so the rate really
# is the 0.5 the tree prints; 6 000 on one child returns 1 750, so the ceiling really is
# the 3 500 per child. Agreement between the parameter and the behaviour is the check —
# either alone can be a parameter the formula never reads (D-062).
_RI = ("impot_revenu", "calcul_reductions_impots")
_CI = ("impot_revenu", "credits_impots")
PATH_NICHE_SALDOM = (*_CI, "emploi_salarie_domicile")
PATH_NICHE_GARDENF = (*_CI, "gardenf")
PATH_NICHE_DONS = (*_RI, "dons")
PATH_NICHE_SYNDICALES = (*_CI, "cotisations_syndicales")
PATH_NICHE_SCOLARITE = (*_RI, "enfants_scolarises")
#: The global cap on niches — 10 000 EUR, and the single most argued-over number in
#: this family. It binds only on households claiming more than that, which is why its
#: knob has to be verified on one that does.
PATH_PLAFOND_GLOBAL_NICHES = (*_CI, "plaf_nich", "plafond")

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
    "abattement_pensions_plafond": (*PATH_ABATTEMENT_PENSIONS, "max"),
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
    # Prestations (B1) — the spending side.
    "rsa_montant_de_base": PATH_RSA_MONTANT,
    "rsa_forfait_logement_1_personne": (*PATH_RSA_FORFAIT_LOGEMENT, "taux_1_personne"),
    "rsa_forfait_logement_2_personnes": (*PATH_RSA_FORFAIT_LOGEMENT, "taux_2_personnes"),
    "rsa_forfait_logement_3_personnes_ou_plus": (
        *PATH_RSA_FORFAIT_LOGEMENT, "taux_3_personnes_ou_plus"),
    "ppa_montant_de_base": (*PATH_PPA, "montant_de_base"),
    # The 61 % of activity income added back before the taper: the single parameter
    # that most directly sets the marginal rate faced by working households on PPA,
    # and therefore the one the EMTR machinery has been waiting for.
    "ppa_pente": (*PATH_PPA, "majoration_ressources_revenus_activite"),
    "ppa_bonification_taux_max": (*PATH_PPA, "bonification", "taux_bonification_max"),
    "bmaf": PATH_BMAF,
    "af_taux_2_enfants": (*PATH_AF_TAUX, "enf2"),
    "af_taux_3_enfants": (*PATH_AF_TAUX, "enf3"),
    # The 2015 modulation: allocations halve above one income threshold and quarter
    # above a second. Setting both tranches to 1 restores universality, which is a
    # live proposal and now a single knob.
    "af_modulation_taux_tranche_2": (*PATH_AF_MODULATION, "taux_tranche_2"),
    "af_modulation_taux_tranche_3": (*PATH_AF_MODULATION, "taux_tranche_3"),
    # `plafond_tranche_1` and `plafond_tranche_2` exist in the tree, accept a write,
    # and are NEVER READ BY THE FORMULA: they are the published values already
    # including two children's worth of majoration (62 474 + 2 x 6 246 = 74 966). The
    # formula computes its own ceiling from `_base` plus `nb_enf_tot` majorations.
    # Pointing a knob at the derived value writes successfully and moves nothing — the
    # D-044 failure in a new shape, caught here only because the verification runs a
    # household through the engine instead of reading back what it just wrote.
    "af_plafond_tranche_1_base": (*PATH_AF_RESSOURCES, "plafond_tranche_1_base"),
    "af_plafond_tranche_2_base": (*PATH_AF_RESSOURCES, "plafond_tranche_2_base"),
    "af_majoration_plafond_par_enfant": (
        *PATH_AF_RESSOURCES, "majoration_plafond_par_enfant_supplementaire"),
    "al_minoration_forfaitaire": PATH_AL_MINORATION,
    # --- IFI (Phase 5) --------------------------------------------------------------
    # Every one of these was verified by RUNNING A HOUSEHOLD, and four of them looked
    # dead on the first try because the household did not exercise them: the décote
    # knobs need an assiette inside the 1,3-1,4 M window, and the dons ceiling needs a
    # donation large enough to reach it. Watching one household and concluding "dead"
    # is the near-miss that nearly deleted three working employer knobs (D-071).
    "ifi_decote_parametre": (*PATH_IFI_DECOTE, "parametre_calcul_decote"),
    "ifi_decote_taux": (*PATH_IFI_DECOTE, "taux_decote"),
    "ifi_decote_borne_inferieure": (*PATH_IFI_DECOTE, "borne_inferieure_decote"),
    "ifi_decote_borne_superieure": (*PATH_IFI_DECOTE, "borne_superieure_decote"),
    "ifi_plafonnement_taux": (*_IFI, "plaf", "plafonnement_taux_imposition"),
    "ifi_abattement_residence_principale": (
        *_IFI, "reduc_exo", "abattement_residence_principale"),
    "ifi_dons_taux": (*PATH_IFI_DONS, "taux"),
    "ifi_dons_plafond": (*PATH_IFI_DONS, "limite_reduction"),
    "ifi_forfait_mobilier": (*_IFI, "forfait_mobilier", "majoration_forfaitaire"),
    # The ceiling on the SUM of IFI réductions. Its twin
    # `plafond_somme_reduction_pme_fcip_fip_pme` carries the same 50 000 and is read by
    # nothing — one of the dead look-alikes found upstream (D-075). Aiming a knob at the
    # twin would write successfully and move nothing, so the name here matters.
    "ifi_plafond_reductions": (
        *_IFI, "reduc_impot", "plafond_somme_trois_reductions_pme_fcip_fip_pme_dons"),
    # Non-bâti: bois et forêts, biens ruraux. Exercised only by a foyer that declares
    # some — measured on b1bc/b1be/b1bh, dead on a foyer holding only bâti.
    "ifi_non_bati_seuil": (*_IFI, "forfait_mobilier", "non_bati", "seuil"),
    "ifi_non_bati_taux_bois_forets": (
        *_IFI, "forfait_mobilier", "non_bati", "taux_bois_forets"),
    # IR niches (B3).
    "saldom_taux": (*PATH_NICHE_SALDOM, "taux"),
    "saldom_plafond": (*PATH_NICHE_SALDOM, "plafond"),
    "gardenf_taux": (*PATH_NICHE_GARDENF, "taux"),
    "gardenf_plafond": (*PATH_NICHE_GARDENF, "plafond"),
    "dons_taux": (*PATH_NICHE_DONS, "taux_reduction"),
    "dons_plafond_part_rfr": (*PATH_NICHE_DONS, "plafond_dons"),
    "dons_coluche_taux": (*PATH_NICHE_DONS, "dons_coluche", "taux"),
    "dons_coluche_plafond": (*PATH_NICHE_DONS, "dons_coluche", "plafond"),
    "cotisations_syndicales_taux": (*PATH_NICHE_SYNDICALES, "taux"),
    "frais_scolarite_college": (*PATH_NICHE_SCOLARITE, "college"),
    "frais_scolarite_lycee": (*PATH_NICHE_SCOLARITE, "lycee"),
    "frais_scolarite_superieur": (*PATH_NICHE_SCOLARITE, "universite"),
    "plafond_global_niches": PATH_PLAFOND_GLOBAL_NICHES,
}

#: Knobs that move an IR niche. Grouped for the same three reasons the prestations are:
#: the UI panels them apart, and a reader needs to know which levers only bite on a
#: household that actually declares the corresponding base.
NICHE_KNOBS = frozenset({
    "saldom_taux", "saldom_plafond", "gardenf_taux", "gardenf_plafond",
    "dons_taux", "dons_plafond_part_rfr", "dons_coluche_taux", "dons_coluche_plafond",
    "cotisations_syndicales_taux", "frais_scolarite_college", "frais_scolarite_lycee",
    "frais_scolarite_superieur", "plafond_global_niches",
})

#: Knobs that move the IFI (Phase 5). Grouped for the same reason as the niches: the UI
#: panels them apart, and every one of them bites only on a foyer that declares real
#: estate AND has income — with no income the plafonnement abates the whole tax and
#: every one of these looks dead.
IFI_KNOBS = frozenset({
    "ifi_decote_parametre", "ifi_decote_taux", "ifi_decote_borne_inferieure",
    "ifi_decote_borne_superieure", "ifi_plafonnement_taux",
    "ifi_abattement_residence_principale", "ifi_dons_taux", "ifi_dons_plafond",
    "ifi_forfait_mobilier", "ifi_plafond_reductions", "ifi_non_bati_seuil",
    "ifi_non_bati_taux_bois_forets",
})

#: `af_cm.modulation.taux_tranche_1` is NOT a knob, and the reason is the fourth
#: instance of the read-back-blind class. It exists, resolves to 1.0 at 2024-01-01, and
#: the AF formula never reads it: `taux_helper` hardcodes the full rate as
#: `(base_ressources <= plafond1) * 1`. A knob aimed at it writes successfully and moves
#: nothing — measured, halving it left a two-child family's AF at 1 771,44 EUR.
#:
#: No name-based rule can catch this one. `modulation` is referenced in the model, and
#: so is `taux_tranche_1` — but only under `af_maj_dom.majoration_premier_enfant`, a
#: different parameter that happens to reuse the leaf name. Only an outcome test settles
#: it, which is why `test_every_knob_moves_an_outcome` replaced the grep rule.

#: Knobs that move a transfer rather than a levy. Kept as a set because three
#: different layers need to know: the double-entry guard signs them the other way, the
#: macro layer looks for a spending instrument, and the UI groups them apart.
PRESTATION_KNOBS = frozenset({
    "rsa_montant_de_base", "rsa_forfait_logement_1_personne",
    "rsa_forfait_logement_2_personnes", "rsa_forfait_logement_3_personnes_ou_plus",
    "ppa_montant_de_base", "ppa_pente",
    "ppa_bonification_taux_max", "bmaf", "af_taux_2_enfants", "af_taux_3_enfants",
    "af_modulation_taux_tranche_2", "af_modulation_taux_tranche_3",
    "af_plafond_tranche_1_base", "af_plafond_tranche_2_base",
    "af_majoration_plafond_par_enfant", "al_minoration_forfaitaire",
})


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
                if spec.ifi_bareme is not None:
                    _apply_bareme(parameters, spec.ifi_bareme, start,
                                  path=(*_IFI, "bareme"))
                for knob, path in SCALAR_KNOBS.items():
                    value = getattr(spec, knob)
                    if value is not None:
                        update_existing(parameters, path, start=start, value=value,
                                        instant=instant, superseded_by=SUPERSEDED_BY)
                for knob, path in PLAFOND_KNOBS.items():
                    value = getattr(spec, knob, None)
                    if value is not None:
                        _apply_plafond(parameters, path, value, start, instant)
                return parameters

            self.modify_parameters(modifier_function=modify)

    return UserReform


#: What replaced an instrument, for the message when a knob no longer applies.
#: The 2026 refonte does not reparameterise the allègements — it REPLACES them. Both
#: bandeaux disappear and the réduction générale becomes a power function
#: (`puissance`, `t_min`, `t_delta_*`) extending to 3 SMIC. A knob pointing at the old
#: children is not merely stale there; it names something that no longer exists.
SUPERSEDED_BY = {
    "entreprises_de_moins_de_50_salaries": "t_delta_petites_entreprises",
    "entreprises_de_50_salaries_et_plus": "t_delta_grandes_entreprises",
}


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
        update_existing(parameters, (*path, name), start=start, value=value,
                        instant=instant)


def _apply_bareme(parameters: Any, brackets: list[Any], start: Any,
                  path: tuple[str, ...] = PATH_BAREME) -> None:
    """Replace the active scale with the user's brackets, collapsing the surplus.

    `path` defaults to the IR scale; the IFI passes its own. The machinery is shared
    because the surplus-bracket trick below is subtle enough that a second copy of it
    would be a second place to get it wrong.
    """
    node = resolve(parameters, path)
    active = active_bracket_count(node, start)
    if len(brackets) > active:
        raise ValueError(
            f"le barème fourni compte {len(brackets)} tranches, le barème légal n'en a que "
            f"{active} d'actives à cette date ; v1 ne crée pas de tranche supplémentaire"
        )
    for i, bracket in enumerate(brackets):
        update_bracket(node, i, active=active, start=start,
                       rate=bracket.rate, threshold=bracket.threshold)
    # Neutralise the leftover active brackets. They take the top threshold and a
    # rate of ZERO: brackets sharing a threshold are merged by *summing* their
    # rates, so 0 leaves the top rate untouched while repeating the top rate would
    # multiply it. `.update` cannot write None, so a bracket cannot be deactivated
    # outright — this is the way to make one vanish.
    top = brackets[-1]
    for j in range(len(brackets), active):
        update_bracket(node, j, active=active, start=start,
                       rate=0.0, threshold=top.threshold)


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
        if differs(got, wanted):
            problems.append(f"{knob} : demandé {wanted}, appliqué {got}")

    # The set of plafonds to check comes from the BASELINE tree, not the reformed
    # one. Taking it from the system under test would let the write path define its
    # own expectation — the shared-path pattern that let D-042 self-confirm. Creation
    # is impossible now, so this is belt and braces; it is also the only version of
    # this check that stays correct if that ever changes.
    from impots.engine.system import baseline as _baseline

    reference = _baseline().parameters
    for knob, path in PLAFOND_KNOBS.items():
        wanted = getattr(spec, knob, None)
        if wanted is None:
            continue
        node = resolve(tax_benefit_system.parameters, path)(instant)
        children = plafond_children(resolve(reference, path)(instant))
        if not children:
            problems.append(f"{knob} : le nœud ne porte aucun plafond à {instant}")
            continue
        for name in children:
            if not hasattr(node, name):
                problems.append(
                    f"{knob}.{name} : présent dans le droit courant, absent du "
                    f"système réformé — la réforme a supprimé un plafond au lieu "
                    f"de le déplacer"
                )
                continue
            got = float(getattr(node, name))
            if differs(got, wanted):
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
