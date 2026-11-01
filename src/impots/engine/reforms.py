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

import functools
from typing import TYPE_CHECKING, Any

from openfisca_core import periods
from openfisca_core.reforms import Reform

from impots.parameters import (
    differs,
    reactivate_bracket,
    resolve,
    update_bracket,
    update_existing,
)

if TYPE_CHECKING:  # pragma: no cover - typing only
    from impots.api.schemas import ReformSpec

PATH_BAREME = ("impot_revenu", "bareme_ir_depuis_1945", "bareme")
PATH_DECOTE = ("impot_revenu", "calcul_impot_revenu", "plaf_qf", "decote")
PATH_PLAFOND_QF_DEMI_PART = (
    "impot_revenu", "calcul_impot_revenu", "plaf_qf",
    "plafond_avantages_procures_par_demi_part", "general",
)
PATH_CSG_ACTIVITE = ("prelevements_sociaux", "contributions_sociales", "csg", "activite")
#: The CSG on pensions (D-320): openfisca's levies read the `deductible` and `imposable`
#: children, by RFR band. Only the taxable part is a knob: the deductible part is already
#: off the declared pension both builders pin on box 1AS (D-176), so moving it moves
#: nothing (measured on three pensioners, one per band). The `taux_*` at the node's root,
#: the sum of the two, is read by no formula.
PATH_CSG_PENSIONS = ("prelevements_sociaux", "contributions_sociales", "csg", "remplacement",
                     "pensions_retraite_invalidite")
_QF = ("impot_revenu", "calcul_impot_revenu", "plaf_qf")
_PS_CAPITAL = ("taxation_capital", "prelevements_sociaux")
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
PATH_AL = ("prestations_sociales", "aides_logement")

#: The two legal revaluations PLF 2027 art. 74 suspends (D-298), each with the month it
#: falls in: the prime d'activité's montant forfaitaire on 1 April (CSS L. 842-3, sixth
#: paragraph) and the housing-aid expense parameters on 1 October (CCH L. 823-4). A
#: revaluation knob is a COEFFICIENT on what the tree carries at that date, written from
#: the first of the month in the priced year, never from January: written from January,
#: the April one would count three months too many and the October one nine. The
#: population runner sums the twelve months, so the year priced is the year in which the
#: revaluation falls, as the budget counts it.
REVALORISATION_KNOBS: dict[str, int] = {
    "ppa_revalorisation_avril": 4,
    "al_revalorisation_octobre": 10,
    "ppa_revalorisation_portee": 4,
    "al_revalorisation_portee": 10,
}
#: The CARRIED knobs (D-301): the revaluation of the year before the priced year, written
#: at that year's legal date, so that every month of the priced year carries it — and the
#: months before it that a benefit reads, the prime's reference quarter among them. What a
#: revaluation leaves in the years after it falls: a level, not a date.
REVALORISATION_DECALAGE: dict[str, int] = {
    "ppa_revalorisation_portee": -1,
    "al_revalorisation_portee": -1,
}
#: Each dated knob and the carried one a path prices in the years after its first.
PORTEE: dict[str, str] = {
    "ppa_revalorisation_avril": "ppa_revalorisation_portee",
    "al_revalorisation_octobre": "al_revalorisation_portee",
}

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

#: The income-tax part of the PFU (D-249). One parameter, read by both formulas that
#: compute it — the PFU outside life insurance (dividends, interest, plus-values) and the
#: one on life insurance above its threshold — and by nothing else: read out of
#: openfisca's source, not assumed from the name. The 7,5 % beside it is the life
#: insurance below the threshold, which this knob does not move.
PATH_PFU = ("taxation_capital", "prelevement_forfaitaire", "partir_2018",
            "taux_prelevement_forfaitaire_rev_capital_eligibles_pfu_interets_dividendes_etc")

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
    # The programmes of 2027 (D-320). The taxable part of the CSG on pensions, by band;
    # the deductible part is off the declared pension both builders pin (D-176).
    "csg_pensions_imposable_taux_plein": (*PATH_CSG_PENSIONS, "imposable", "taux_plein"),
    "csg_pensions_imposable_taux_median": (*PATH_CSG_PENSIONS, "imposable", "taux_median"),
    # The social part of the PFU: the 2026 formula levies the general rate on every
    # capital income but the « allégés » products, and the solidarity levy on all of it.
    "csg_capital_taux_global": (*_PS_CAPITAL, "csg", "taux_global", "produits_de_placement"),
    "prelevement_solidarite_capital": (*_PS_CAPITAL, "prelevements_solidarite",
                                       "produits_de_placement"),
    # The quotient familial: the parts a child brings in the general case, and the
    # ceiling of the first child of a lone parent.
    "qf_parts_enf1": (*_QF, "quotient_familial", "cas_general", "enf1"),
    "qf_parts_enf2": (*_QF, "quotient_familial", "cas_general", "enf2"),
    "qf_parts_enf3_et_sup": (*_QF, "quotient_familial", "cas_general", "enf3_et_sup"),
    "plafond_qf_parent_isole": (*_QF, "plafond_avantages_procures_par_demi_part", "celib_enf"),
    # The daily allowances (D-306): the share of the work-accident ones the income tax
    # exempts, which correction 22 brings into the tree, and openfisca's CSG rate on them,
    # which correction 23 levies. They move nothing on a household without an allowance.
    "ij_at_mp_part_exoneree": ("impot_revenu", "indemnites_journalieres",
                               "part_exoneree_at_mp"),
    # The share of the sickness allowances served for an ALD that the income tax exempts
    # (CGI art. 80 quinquies, 1), which correction 22 also brings in (D-312).
    "ij_ald_part_exoneree": ("impot_revenu", "indemnites_journalieres", "part_exoneree_ald"),
    "csg_ij_taux": ("prelevements_sociaux", "contributions_sociales", "csg", "remplacement",
                    "indemnites_journalieres", "taux_global"),
    # Employer social contributions. The channels that price these (C2, C3) were
    # written in Phase 3 against a knob that did not exist — a spec error on the
    # record (D-032). These are it.
    "allegement_general_plafond": (*PATH_ALLEGEMENT_GENERAL, "plafond"),
    "allegement_general_taux_50_et_plus": (
        *PATH_ALLEGEMENT_GENERAL, "entreprises_de_50_salaries_et_plus"),
    "allegement_general_taux_moins_de_50": (
        *PATH_ALLEGEMENT_GENERAL, "entreprises_de_moins_de_50_salaries"),
    # The 2026 curve that replaced them (D-042, D-240).
    "allegement_general_t_min": (*PATH_ALLEGEMENT_GENERAL, "t_min"),
    "allegement_general_t_delta_moins_de_50": (
        *PATH_ALLEGEMENT_GENERAL, "t_delta_petites_entreprises"),
    "allegement_general_t_delta_50_et_plus": (
        *PATH_ALLEGEMENT_GENERAL, "t_delta_grandes_entreprises"),
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
    # Capital income (D-249).
    "pfu_taux": PATH_PFU,
}

#: Knobs that move the taxation of capital income. Read back by `verify_capital`, the
#: guard 9 of PHASE11_SPEC §10, and claimed by the dividend channel C10.
CAPITAL_KNOBS = frozenset({"pfu_taux", "csg_capital_taux_global",
                           "prelevement_solidarite_capital"})

#: Knobs that multiply every active rate of a set of scales by one factor (D-320). The
#: employee's retirement contributions are five scales, each by tranche of the PSS; a
#: candidate who says « baisser les cotisations salariales » names none of them, and a
#: factor on all five is the one translation that does not choose between them.
_CNAV_SALARIE = ("prelevements_sociaux", "cotisations_securite_sociale_regime_general",
                 "cnav", "salarie")
_COMPLEMENTAIRE = ("prelevements_sociaux", "regimes_complementaires_retraite_secteur_prive")
ECHELLE_KNOBS: dict[str, tuple[tuple[str, ...], ...]] = {
    "cotisations_salariales_retraite_echelle": (
        (*_CNAV_SALARIE, "vieillesse_plafonnee"),
        (*_CNAV_SALARIE, "vieillesse_deplafonnee"),
        (*_COMPLEMENTAIRE, "agirc_arrco", "salarie", "agirc_arrco"),
        (*_COMPLEMENTAIRE, "ceg", "salarie", "ceg"),
        (*_COMPLEMENTAIRE, "cet2019", "salarie", "cet2019"),
    ),
}


def _apply_echelle(parameters: Any, paths: tuple[tuple[str, ...], ...], factor: float,
                   start: Any, instant: str) -> None:
    """Multiply every active rate of each scale by `factor`, from `start`.

    A scale with no active bracket at the instant is refused: the factor would land
    nowhere, and the read-back would find nothing to disagree with."""
    for path in paths:
        node = resolve(parameters, path)
        active = active_bracket_count(node, instant)
        if active == 0:
            raise ValueError(f"le barème {'.'.join(path)} n'a aucune tranche active au "
                             f"{instant} : le facteur ne porterait sur rien")
        for i in range(active):
            rate = node.brackets[i].rate.get_at_instant(instant)
            update_bracket(node, i, active=active, start=start, rate=rate * factor)


def verify_echelles(tax_benefit_system: Any, baseline: Any, spec: ReformSpec,
                    year: int) -> None:
    """Read every scaled rate back against the baseline's, times the factor (D-320)."""
    instant = f"{year}-01-01"
    for knob, paths in ECHELLE_KNOBS.items():
        factor = getattr(spec, knob, None)
        if factor is None:
            continue
        for path in paths:
            got = [float(r) for r in resolve(tax_benefit_system.parameters, path)(instant).rates]
            base = [float(r) for r in resolve(baseline.parameters, path)(instant).rates]
            wanted = [r * factor for r in base]
            if len(got) != len(wanted) or any(differs(g, w) for g, w in zip(got, wanted,
                                                                            strict=False)):
                raise AssertionError(
                    f"{knob} : le barème {'.'.join(path)} appliqué vaut {got}, pas "
                    f"{wanted} ({factor} × {base})")


def moves_capital(spec: ReformSpec | None) -> bool:
    """Whether a reform moves the taxation of capital income — the passes that price it
    then impute the capital, which nothing else declares to them (D-249)."""
    return spec is not None and bool(set(spec.model_dump(exclude_none=True))
                                     & CAPITAL_KNOBS)

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
                                        instant=instant, superseded_by=SUPERSEDED_BY,
                                        knob_for=REPLACEMENT_KNOBS, not_before=NOT_BEFORE)
                for knob, path in PLAFOND_KNOBS.items():
                    value = getattr(spec, knob, None)
                    if value is not None:
                        _apply_plafond(parameters, path, value, start, instant)
                for knob, paths in ECHELLE_KNOBS.items():
                    factor = getattr(spec, knob, None)
                    if factor is not None:
                        _apply_echelle(parameters, paths, factor, start, instant)
                for knob in REVALORISATION_KNOBS:
                    coefficient = getattr(spec, knob, None)
                    if coefficient is not None:
                        _apply_revalorisation(parameters, knob, coefficient, year)
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

#: The knob that moves each replacement, so that the refusal names what to use (D-240).
REPLACEMENT_KNOBS = {
    "t_delta_petites_entreprises": "allegement_general_t_delta_moins_de_50",
    "t_delta_grandes_entreprises": "allegement_general_t_delta_50_et_plus",
}

#: And the other way: the curve does not exist before 2026, where the rates govern.
_BEFORE_THE_CURVE = ("avant la refonte de 2026, la réduction générale se règle par "
                     "« allegement_general_taux_moins_de_50 » et "
                     "« allegement_general_taux_50_et_plus »")
NOT_BEFORE = dict.fromkeys(
    ("t_min", "t_delta_petites_entreprises", "t_delta_grandes_entreprises"),
    _BEFORE_THE_CURVE)


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
    if len(brackets) > active + 1 or len(brackets) > len(node.brackets):
        raise ValueError(
            f"le barème fourni compte {len(brackets)} tranches, le barème légal n'en a que "
            f"{active} d'actives à cette date : une seule tranche dormante peut être "
            f"réveillée, aucune n'est créée (D-320)"
        )
    for i, bracket in enumerate(brackets):
        if i < active:
            update_bracket(node, i, active=active, start=start,
                           rate=bracket.rate, threshold=bracket.threshold)
        else:
            reactivate_bracket(node, i, active=active, start=start,
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
        "allegement_general_taux_moins_de_50", "allegement_general_t_min",
        "allegement_general_t_delta_moins_de_50", "allegement_general_t_delta_50_et_plus",
        "bandeau_maladie_taux", "bandeau_famille_taux",
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


def verify_capital(tax_benefit_system: Any, spec: ReformSpec, year: int) -> None:
    """Read the PFU back, and refuse a system that did not take it (§10, guard 9; D-249).

    The path read is `PATH_PFU` itself, never the knob table the write went through:
    reading back through the table that wrote would confirm a write diverted to any
    neighbouring rate — the shared-path pattern that let D-042 self-confirm.
    """
    wanted = spec.pfu_taux
    if wanted is None:
        return
    got = float(resolve(tax_benefit_system.parameters, PATH_PFU)(f"{year}-01-01"))
    if differs(got, wanted):
        raise AssertionError(
            f"le PFU appliqué ne correspond pas à la réforme demandée — pfu_taux : "
            f"demandé {wanted}, appliqué {got} au {year}-01-01"
        )


@functools.lru_cache(maxsize=8)
def al_parametres_revises_en_octobre(year: int) -> tuple[tuple[str, ...], ...]:
    """The housing-aid parameters the 1 October revision moves, read off the baseline tree.

    Every leaf under `aides_logement` carrying a value dated 1 October of the year before
    `year`: the last revision the tree knows of, whose list is CCH L. 823-4's — the rent
    ceilings, the charge allowances, the foyers' rent equivalences, the flat minimum
    contribution. Derived rather than listed, so a leaf the tree gains is revalued with
    the others; the test holds the derivation to the revision, every leaf moved by the IRL.
    Past the tree's last October revision, that revision's leaves: a path priced to 2035
    revalues what the law revalues, not nothing (D-301).
    """
    from openfisca_core.parameters import Parameter

    from impots.engine.system import baseline as _baseline

    leaves: list[tuple[tuple[str, ...], set[str]]] = []

    def walk(node: Any, path: tuple[str, ...]) -> None:
        if isinstance(node, Parameter):
            leaves.append((path, {value.instant_str for value in node.values_list}))
            return
        for name, child in getattr(node, "children", {}).items():
            walk(child, (*path, name))

    walk(resolve(_baseline().parameters, PATH_AL), PATH_AL)
    octobers = {d for _, dates in leaves for d in dates
                if d.endswith("-10-01") and d <= f"{year - 1}-10-01"}
    if not octobers:
        raise ValueError(f"aucune révision d'octobre des aides au logement dans l'arbre "
                         f"avant le 1er octobre {year - 1}")
    date = max(octobers)
    return tuple(path for path, dates in leaves if date in dates)


def revalorisation_date(knob: str, year: int) -> str:
    """The day a revaluation knob is written from, for `year` priced."""
    return f"{year + REVALORISATION_DECALAGE.get(knob, 0)}-{REVALORISATION_KNOBS[knob]:02d}-01"


def revalorisation_paths(knob: str, year: int) -> tuple[tuple[str, ...], ...]:
    """What a revaluation knob multiplies. The prime d'activité's bonification is a share
    of the montant forfaitaire, so it follows it without a path of its own."""
    if knob in ("ppa_revalorisation_avril", "ppa_revalorisation_portee"):
        return ((*PATH_PPA, "montant_de_base"),)
    if knob in ("al_revalorisation_octobre", "al_revalorisation_portee"):
        return al_parametres_revises_en_octobre(year + REVALORISATION_DECALAGE.get(knob, 0))
    raise KeyError(knob)


def carried(spec: ReformSpec) -> ReformSpec:
    """`spec` as a path prices it in the years after its first: each dated revaluation
    turned into its carried knob, every other knob as it is (D-301)."""
    fields = spec.model_dump(exclude_none=True)
    for dated, carry in PORTEE.items():
        if dated in fields:
            fields[carry] = fields.pop(dated)
    return type(spec).model_validate(fields)


def _breakpoints(parameters: Any, path: tuple[str, ...], date: str, until: str) -> list[str]:
    """`date`, then every day after it and up to `until` on which the tree's value changes."""
    node = resolve(parameters, path)
    later = sorted({v.instant_str for v in node.values_list if date < v.instant_str <= until})
    return [date, *later]


def _apply_revalorisation(parameters: Any, knob: str, coefficient: float, year: int) -> None:
    """Multiply every value the tree carries from the knob's date on by `coefficient`,
    segment by segment: a revaluation the tree already holds later is scaled, not wiped —
    a carried knob is written in the year before, and the priced year may have its own.

    Every value is read before the first write, and the segments are written in order:
    each write runs to the end of time, and the next one takes over at its own start."""
    date = revalorisation_date(knob, year)
    for path in revalorisation_paths(knob, year):
        starts = _breakpoints(parameters, path, date, "9999-12-31")
        values = [resolve(parameters, path)(start) for start in starts]
        for start, value in zip(starts, values, strict=True):
            if value is not None:
                update_existing(parameters, path, start=periods.instant(start),
                                value=float(value) * coefficient, instant=start)


def verify_revalorisations(tax_benefit_system: Any, spec: ReformSpec, year: int) -> None:
    """Read each revaluation back against the BASELINE tree, on its date and before it.

    What it expects is derived here, from the baseline and the legal month, never from the
    write path: the coefficient times the baseline's value on the first of the month and
    on every later day of the priced year the baseline changes, and the baseline's value
    untouched the day before. A coefficient written from January — the easy mistake, since
    every other knob is — passes the first check and fails the last; a parameter the write
    left out fails the first; a carried write that wipes the priced year's own revaluation
    fails the middle one (D-301).
    """
    from impots.engine.system import baseline as _baseline

    reference = _baseline().parameters
    problems: list[str] = []
    for knob in REVALORISATION_KNOBS:
        coefficient = getattr(spec, knob, None)
        if coefficient is None:
            continue
        date = revalorisation_date(knob, year)
        before = str(periods.instant(date).offset(-1, "day"))
        paths = revalorisation_paths(knob, year)
        if not paths:
            problems.append(f"{knob} : aucun paramètre à revaloriser en {year}")
        for path in paths:
            name = ".".join(path[len(PATH_AL):])
            # Every day the BASELINE changes from the date to the end of the priced year:
            # a later revaluation wiped by the write fails here (D-301).
            for point in _breakpoints(reference, path, date, f"{year}-12-31"):
                wanted = float(resolve(reference, path)(point)) * coefficient
                got = float(resolve(tax_benefit_system.parameters, path)(point))
                if differs(got, wanted):
                    problems.append(f"{knob} {name} au {point} : demandé {wanted}, "
                                    f"appliqué {got}")
            untouched = float(resolve(reference, path)(before))
            got_before = float(resolve(tax_benefit_system.parameters, path)(before))
            if differs(got_before, untouched):
                problems.append(f"{knob} {name} écrit avant sa date : {got_before} au "
                                f"{before}, au lieu de {untouched}")
    if problems:
        raise AssertionError(
            "les revalorisations appliquées ne correspondent pas à la réforme demandée — "
            + " ; ".join(problems))


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
