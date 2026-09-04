"""One outcome case per reform knob, and the reason for every exemption.

**This registry exists because a name-based rule could not do the job.** The earlier
standing rule required a knob's parameter node to appear somewhere in openfisca's model
source, and it passed `af_cm.modulation.taux_tranche_1` — a parameter that resolves to
1.0, that the AF formula never reads (`taux_helper` hardcodes the full rate as
`(base_ressources <= plafond1) * 1`), and whose leaf name nevertheless occurs in the
source under `af_maj_dom.majoration_premier_enfant`, an unrelated parameter that reuses
it. Grep is defeated by name reuse. Only running a household settles it.

So every knob must appear here with a household on which it demonstrably moves an
output, or with an explicit reason why no such household can be built. There is exactly
one of the latter, and it is not a loophole: it is a limitation of the wire format,
written down.
"""

from __future__ import annotations

MODESTE = {"adults": [{"salaire_brut_annuel": 26_000, "annee_naissance": 1990}]}
COUPLE = {
    "adults": [{"salaire_brut_annuel": 28_000, "annee_naissance": 1985},
               {"salaire_brut_annuel": 26_000, "annee_naissance": 1987}],
    "couple_marie_ou_pacse": True,
}
SMIC = {"adults": [{"salaire_brut_annuel": 22_000, "annee_naissance": 1990}]}
AISE_2_ENFANTS = {
    "adults": [{"salaire_brut_annuel": 100_000, "annee_naissance": 1980}],
    "children": [{"annee_naissance": 2012}, {"annee_naissance": 2015}],
}
FAMILLE_MODESTE = {
    "adults": [{"salaire_brut_annuel": 40_000, "annee_naissance": 1985}],
    "children": [{"annee_naissance": 2012}, {"annee_naissance": 2015}],
}
FAMILLE_AISEE = {
    "adults": [{"salaire_brut_annuel": 100_000, "annee_naissance": 1980},
               {"salaire_brut_annuel": 50_000, "annee_naissance": 1982}],
    "couple_marie_ou_pacse": True,
    "children": [{"annee_naissance": 2012}, {"annee_naissance": 2015}],
}
TEMPS_PARTIEL = {
    "adults": [{"salaire_brut_annuel": 11_000, "annee_naissance": 1990}],
    "children": [{"annee_naissance": 2015}],
}
LOGE_SEUL = {
    "adults": [{"salaire_brut_annuel": 0, "annee_naissance": 1995}],
    "logement": {"statut": "locataire_vide", "loyer_mensuel": 500, "zone_apl": 2},
}
LOGE_COUPLE = {
    "adults": [{"salaire_brut_annuel": 0, "annee_naissance": 1990},
               {"salaire_brut_annuel": 0, "annee_naissance": 1992}],
    "couple_marie_ou_pacse": True,
    "logement": {"statut": "locataire_vide", "loyer_mensuel": 600, "zone_apl": 2},
}
LOGE_TROIS = {**LOGE_COUPLE, "children": [{"annee_naissance": 2015}]}
LOCATAIRE_PPA = {**TEMPS_PARTIEL,
                 "logement": {"statut": "locataire_vide", "loyer_mensuel": 700,
                              "zone_apl": 1}}
NICHE_FOYER = {**AISE_2_ENFANTS}

# --- IFI households ------------------------------------------------------------------
# Every one carries INCOME, and that is not decoration: the plafonnement caps IFI plus
# income tax at 75 % of income, so a wealthy foyer with no salary owes NO IFI and every
# IFI knob would look dead. Measured: 2 M of real estate gives 7 400 EUR of barème and
# 0 EUR of tax at zero income.
def _riche(patrimoine: dict, salaire: int = 900_000) -> dict:
    return {"adults": [{"salaire_brut_annuel": salaire, "annee_naissance": 1970}],
            "patrimoine": patrimoine}

#: Assiette 3,5 M — well clear of the décote window, so the barème knobs bite cleanly.
IFI_RICHE = _riche({"residence_principale": 1_000_000,
                    "autres_immeubles_batis": 2_500_000,
                    "dons_organismes_interet_general": 20_000})
#: Assiette 1,35 M — INSIDE the décote window. The décote knobs moved nothing on a
#: household above 1,4 M, which is how three of them briefly looked dead.
IFI_DECOTE = _riche({"autres_immeubles_batis": 1_350_000}, salaire=400_000)
#: Assiette 1,25 M — BELOW the window, so moving its lower bound pulls this foyer in.
IFI_SOUS_LE_SEUIL = _riche({"autres_immeubles_batis": 1_250_000}, salaire=400_000)
#: Assiette 1,45 M — just ABOVE the window, so moving its upper bound pulls it in.
IFI_AU_DESSUS = _riche({"autres_immeubles_batis": 1_450_000}, salaire=400_000)
#: Dons big enough to reach the 50 000 EUR ceiling: 100 000 x 75 % = 75 000.
IFI_GROS_DONS = _riche({"autres_immeubles_batis": 12_000_000,
                        "dons_organismes_interet_general": 100_000}, salaire=3_000_000)

#: knob -> (household, niches to declare or None, output row, value, expected sign of
#: the change in that row). Sign is +1 when the output RISES.
CASES: dict[str, tuple[dict, dict | None, str, float, int]] = {
    # --- income tax ---------------------------------------------------------------
    "decote_seuil_celib": (MODESTE, None, "ir", 2_000.0, -1),
    "decote_seuil_couple": (COUPLE, None, "ir", 3_000.0, -1),
    "decote_taux": (MODESTE, None, "ir", 0.30, -1),
    "plafond_qf_demi_part": (AISE_2_ENFANTS, None, "ir", 1_000.0, +1),
    "csg_activite_imposable": (MODESTE, None, "csg_imposable", 0.05, +1),
    "csg_activite_deductible": (MODESTE, None, "csg_deductible", 0.10, +1),
    # --- employer contributions ----------------------------------------------------
    # Watched on `allegement_general`, NOT on `cotisations_employeur`: that row is
    # gross of the reductions, so an earlier sweep of these three read "no movement"
    # and nearly deleted three working knobs.
    "allegement_general_plafond": (SMIC, None, "allegement_general", 1.8, +1),
    "allegement_general_taux_moins_de_50": (
        SMIC, None, "allegement_general", 0.40, +1),
    "bandeau_maladie_taux": (SMIC, None, "allegement_bandeau_maladie", 0.02, -1),
    "bandeau_famille_taux": (SMIC, None, "allegement_bandeau_famille", 0.01, -1),
    # --- prestations ----------------------------------------------------------------
    "rsa_montant_de_base": (LOGE_SEUL, None, "rsa", 700.0, +1),
    "rsa_forfait_logement_1_personne": (LOGE_SEUL, None, "rsa", 0.30, -1),
    "rsa_forfait_logement_2_personnes": (LOGE_COUPLE, None, "rsa", 0.35, -1),
    "rsa_forfait_logement_3_personnes_ou_plus": (LOGE_TROIS, None, "rsa", 0.35, -1),
    "ppa_montant_de_base": (TEMPS_PARTIEL, None, "ppa", 700.0, +1),
    "ppa_pente": (TEMPS_PARTIEL, None, "ppa", 0.70, +1),
    "ppa_bonification_taux_max": (TEMPS_PARTIEL, None, "ppa", 0.40, +1),
    "bmaf": (FAMILLE_MODESTE, None, "af", 500.0, +1),
    "af_taux_2_enfants": (FAMILLE_MODESTE, None, "af", 0.40, +1),
    "af_taux_3_enfants": (
        {**FAMILLE_MODESTE, "children": [{"annee_naissance": 2012},
                                         {"annee_naissance": 2015},
                                         {"annee_naissance": 2018}]},
        None, "af", 0.50, +1),
    # 115 000 EUR, not 100 000: the modulation compares against BASE RESSOURCES —
    # net, two years back, roughly 0.72 of gross — so a 100 000 household is still in
    # tranche 1 and this knob would have moved nothing. Measured across four incomes.
    "af_modulation_taux_tranche_2": (
        {"adults": [{"salaire_brut_annuel": 115_000, "annee_naissance": 1980}],
         "children": [{"annee_naissance": 2012}, {"annee_naissance": 2015}]},
        None, "af", 0.90, +1),
    "af_modulation_taux_tranche_3": (FAMILLE_AISEE, None, "af", 1.0, +1),
    "af_plafond_tranche_1_base": (FAMILLE_MODESTE, None, "af", 12_000.0, -1),
    "af_plafond_tranche_2_base": (FAMILLE_AISEE, None, "af", 500_000.0, +1),
    "af_majoration_plafond_par_enfant": (FAMILLE_AISEE, None, "af", 50_000.0, +1),
    "al_minoration_forfaitaire": (
        LOCATAIRE_PPA, None, "aide_logement", 20.0, -1),
    # --- IR niches ------------------------------------------------------------------
    "saldom_taux": (NICHE_FOYER, {"salarie_domicile": 5_000}, "ir", 0.30, +1),
    "saldom_plafond": (NICHE_FOYER, {"salarie_domicile": 15_000}, "ir", 6_000.0, +1),
    "gardenf_taux": (
        {**NICHE_FOYER, "children": [{"annee_naissance": 2021}]},
        {"frais_garde_par_enfant": [2_000.0]}, "ir", 0.30, +1),
    "gardenf_plafond": (
        {**NICHE_FOYER, "children": [{"annee_naissance": 2021}]},
        {"frais_garde_par_enfant": [3_000.0]}, "ir", 1_000.0, +1),
    "dons_taux": (NICHE_FOYER, {"dons_oeuvres": 1_000}, "ir", 0.50, +1),
    "dons_plafond_part_rfr": (NICHE_FOYER, {"dons_oeuvres": 30_000}, "ir", 0.02, +1),
    "dons_coluche_taux": (
        NICHE_FOYER, {"dons_aide_personnes_en_difficulte": 800}, "ir", 0.50, +1),
    "dons_coluche_plafond": (
        NICHE_FOYER, {"dons_aide_personnes_en_difficulte": 800}, "ir", 200.0, +1),
    "cotisations_syndicales_taux": (
        NICHE_FOYER, {"cotisations_syndicales": [300.0]}, "ir", 0.40, +1),
    "frais_scolarite_college": (NICHE_FOYER, {"enfants_college": 1}, "ir", 200.0, -1),
    "frais_scolarite_lycee": (NICHE_FOYER, {"enfants_lycee": 1}, "ir", 300.0, -1),
    "frais_scolarite_superieur": (
        NICHE_FOYER, {"enfants_superieur": 1}, "ir", 400.0, -1),
    # --- IFI -----------------------------------------------------------------------
    # `ifi_decote_borne_inferieure` is the knob that moves the SEUIL D'ASSUJETTISSEMENT.
    # There is no separate seuil parameter — the IFI node's children are bareme, decote,
    # forfait_mobilier, plaf, reduc_exo, reduc_impot, and nothing else. That is the
    # "classic confusion" PHASE5_SPEC §3 warned about, settled by looking.
    "ifi_decote_parametre": (IFI_DECOTE, None, "ifi", 25_000.0, -1),
    "ifi_decote_taux": (IFI_DECOTE, None, "ifi", 0.008, -1),
    # Lowering the lower bound RAISES this foyer's tax, and that is the point: the same
    # parameter is the seuil d'assujettissement, so a foyer at 1,25 M goes from owing
    # nothing to owing something. The sign is the evidence that the knob moves the seuil.
    "ifi_decote_borne_inferieure": (IFI_SOUS_LE_SEUIL, None, "ifi", 1_200_000.0, +1),
    # TIGHTENING the upper bound, not widening it: widening without raising the
    # parameter drives the décote negative, which `_check_ifi_decote` now refuses.
    "ifi_decote_borne_superieure": (IFI_DECOTE, None, "ifi", 1_320_000.0, +1),
    "ifi_plafonnement_taux": (IFI_RICHE, None, "ifi", 0.375, -1),
    "ifi_abattement_residence_principale": (IFI_RICHE, None, "ifi", 0.15, +1),
    "ifi_dons_taux": (IFI_RICHE, None, "ifi", 0.375, +1),
    "ifi_dons_plafond": (IFI_GROS_DONS, None, "ifi", 20_000.0, +1),
    "ifi_forfait_mobilier": (IFI_RICHE, None, "ifi", 0.05, +1),
    "plafond_global_niches": (
        {**NICHE_FOYER, "children": [{"annee_naissance": 2019},
                                     {"annee_naissance": 2021},
                                     {"annee_naissance": 2022}]},
        {"salarie_domicile": 12_000,
         "frais_garde_par_enfant": [3_500.0, 3_500.0, 3_500.0]},
        "ir", 4_000.0, +1),
}

#: Knobs with no household case, and why. An exemption needs a reason a reader can
#: check, not a shrug — an unexplained exemption is how a dead knob would hide here.
EXEMPT: dict[str, str] = {
    "allegement_general_taux_50_et_plus": (
        "Le taux s'applique aux employeurs d'au moins 50 salariés. `HouseholdInput` "
        "n'expose pas `effectif_entreprise` — le moteur traite tout foyer comme un "
        "employeur de moins de 50 — donc aucun ménage exprimable ne peut le faire "
        "bouger. Vérifié : sur un foyer au SMIC, le porter de 0,3234 à 0,40 laisse "
        "`allegement_general` à 6 408,60 EUR, inchangé au centime. Le paramètre EST lu "
        "par la formule (branche effectif >= 50), donc le levier est réel et c'est le "
        "format d'entrée qui ne peut pas l'atteindre, pas le paramètre qui est mort. "
        "À lever le jour où un effectif devient déclarable."
    ),
}
