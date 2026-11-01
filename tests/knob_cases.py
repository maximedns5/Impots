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
#: Seul, au-dessus du forfait de la prime d'activité : c'est là que la prime suit le montant
#: forfaitaire. En dessous, elle ne dépend que des revenus d'activité et de la bonification,
#: et sa revalorisation ne la déplace que de quelques centimes (mesuré, D-298).
SEUL_PPA = {"adults": [{"salaire_brut_annuel": 15_000, "annee_naissance": 1990}]}
NICHE_FOYER = {**AISE_2_ENFANTS}
#: Un retraité dont l'abattement de 10 % dépasse le plafond : seul un foyer de ce genre
#: peut faire bouger `abattement_pensions_plafond` (PLF 2027, art. 3).
RETRAITE_AISE = {"adults": [{"salaire_brut_annuel": 0, "annee_naissance": 1955,
                             "pension_annuelle": 50_000}]}
#: Un retraité au taux médian de la CSG (D-320) : 21 000 EUR déclarés le placent dans la
#: bande médiane en 2026, où le taux imposable vaut 2,4 %.
RETRAITE_MEDIAN = {"adults": [{"salaire_brut_annuel": 0, "annee_naissance": 1955,
                               "pension_annuelle": 21_000}]}
#: Un couple à trois enfants : le troisième seul apporte une part entière (D-320).
COUPLE_3_ENFANTS = {
    "adults": [{"salaire_brut_annuel": 90_000, "annee_naissance": 1980},
               {"salaire_brut_annuel": 60_000, "annee_naissance": 1981}],
    "couple_marie_ou_pacse": True,
    "children": [{"annee_naissance": 2010}, {"annee_naissance": 2012},
                 {"annee_naissance": 2015}],
}
#: Un parent isolé aisé : la demi-part du premier enfant (case T) bute sur son plafond de
#: 4 262 EUR en 2026, qu'il faut donc atteindre pour qu'en abaisser le plafond compte.
PARENT_ISOLE_AISE = {"adults": [{"salaire_brut_annuel": 80_000, "annee_naissance": 1980}],
                     "children": [{"annee_naissance": 2012}]}
#: Un foyer qui déclare des dividendes : sans revenus du capital, le PFU ne mord sur rien
#: (D-249). 10 000 EUR doivent 1 280 EUR de PFU, que le bouton porte à 2 000.
RENTIER = {"adults": [{"salaire_brut_annuel": 30_000, "annee_naissance": 1975}],
           "capital": {"dividendes": 10_000.0}}
#: Les deux plafonds de bandeau sont exprimés en multiples de SMIC, donc le ménage doit
#: se trouver DANS le bandeau pour qu'en abaisser le plafond le lui retire. Au SMIC 2024
#: d'environ 21 203 EUR brut, 45 000 EUR font 2,12 SMIC — sous le plafond maladie de 2,5
#: et sous le plafond famille de 3,5 — et 60 000 EUR font 2,83 SMIC, au-dessus du maladie
#: et sous le famille.
DEUX_SMIC = {"adults": [{"salaire_brut_annuel": 45_000, "annee_naissance": 1990}]}
TROIS_SMIC = {"adults": [{"salaire_brut_annuel": 60_000, "annee_naissance": 1990}]}

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
#: Non-bâti — bois, biens ruraux, parts de groupements. The non-bâti knobs are dead on a
#: foyer holding only bâti, which is why they get their own household rather than a
#: verdict from the one above.
IFI_NON_BATI = _riche({"autres_immeubles_batis": 2_500_000,
                       "bois_et_forets": 800_000,
                       "biens_ruraux_loues_long_terme": 500_000,
                       "parts_groupements_forestiers_agricoles": 500_000},
                      salaire=400_000)

#: knob -> (household, niches to declare or None, output row, value, expected sign of
#: the change in that row). Sign is +1 when the output RISES.
CASES: dict[str, tuple[dict, dict | None, str, float, int]] = {
    # --- income tax ---------------------------------------------------------------
    "decote_seuil_celib": (MODESTE, None, "ir", 2_000.0, -1),
    "decote_seuil_couple": (COUPLE, None, "ir", 3_000.0, -1),
    "decote_taux": (MODESTE, None, "ir", 0.30, -1),
    "plafond_qf_demi_part": (AISE_2_ENFANTS, None, "ir", 1_000.0, +1),
    "abattement_pensions_plafond": (RETRAITE_AISE, None, "ir", 3_000.0, +1),
    "csg_activite_imposable": (MODESTE, None, "csg_imposable", 0.05, +1),
    "csg_activite_deductible": (MODESTE, None, "csg_deductible", 0.10, +1),
    # --- employer contributions ----------------------------------------------------
    # Watched on `allegement_general`, NOT on `cotisations_employeur`: that row is
    # gross of the reductions, so an earlier sweep of these three read "no movement"
    # and nearly deleted three working knobs.
    "allegement_general_plafond": (SMIC, None, "allegement_general", 1.8, +1),
    "allegement_general_taux_moins_de_50": (
        SMIC, None, "allegement_general", 0.40, +1),
    # The 2026 curve (D-240): run in 2026, where it exists (`YEARS`).
    "allegement_general_t_min": (SMIC, None, "allegement_general", 0.03, +1),
    "allegement_general_t_delta_moins_de_50": (
        SMIC, None, "allegement_general", 0.40, +1),
    "bandeau_maladie_taux": (SMIC, None, "allegement_bandeau_maladie", 0.02, -1),
    "bandeau_famille_taux": (SMIC, None, "allegement_bandeau_famille", 0.01, -1),
    # Les deux PLAFOND_KNOBS. Ils étaient hors de TOUTE règle de couverture jusqu'à
    # D-151 : le registre ne quantifiait que sur SCALAR_KNOBS, donc aucune règle ne
    # pouvait les signaler manquants, et tout autre test qui les nomme relit l'arbre ou
    # vérifie quels enfants ont été écrits — la forme D-044 exactement, dans les leviers
    # censés s'en garder. Déplacés en portant le plafond SOUS le ménage, ce qui retire la
    # réduction : mesuré 1 080,00 -> 0,00 EUR sur le famille (1,80 % du salaire) et
    # 2 700,00 -> 0,00 sur le maladie (6,00 %), `salaire_super_brut` montant d'autant.
    "bandeau_famille_plafond": (
        TROIS_SMIC, None, "allegement_bandeau_famille", 2.0, -1),
    "bandeau_maladie_plafond": (
        DEUX_SMIC, None, "allegement_bandeau_maladie", 1.5, -1),
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
    # Les deux revalorisations de l'art. 74 du PLF 2027 (D-298), des coefficients écrits à
    # leur date légale : avril pour la prime, octobre pour le logement. Le mois exact est
    # tenu par `test_revalorisations.py`, ménage et arbre ; ici, l'année bouge.
    "ppa_revalorisation_avril": (SEUL_PPA, None, "ppa", 1.10, +1),
    "al_revalorisation_octobre": (LOCATAIRE_PPA, None, "aide_logement", 1.10, +1),
    "ppa_revalorisation_portee": (SEUL_PPA, None, "ppa", 1.10, +1),
    "al_revalorisation_portee": (LOCATAIRE_PPA, None, "aide_logement", 1.10, +1),
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
    # Lowering the ceiling on the SUM of réductions leaves less relief, so tax rises.
    "ifi_plafond_reductions": (IFI_GROS_DONS, None, "ifi", 10_000.0, +1),
    # Both non-bâti knobs shrink an exemption, so both raise the tax.
    "ifi_non_bati_seuil": (IFI_NON_BATI, None, "ifi", 50_000.0, +1),
    "ifi_non_bati_taux_bois_forets": (IFI_NON_BATI, None, "ifi", 0.5, +1),
    # --- capital income (D-249) -------------------------------------------------------
    "pfu_taux": (RENTIER, None, "ir", 0.20, +1),
    # --- the programmes of 2027 (D-320) -----------------------------------------------
    "csg_capital_taux_global": (RENTIER, None, "prelevements_sociaux_capital", 0.12, +1),
    "prelevement_solidarite_capital": (RENTIER, None, "prelevements_sociaux_capital", 0.09,
                                       +1),
    "csg_pensions_imposable_taux_plein": (RETRAITE_AISE, None, "revenu_disponible", 0.04,
                                          -1),
    "csg_pensions_imposable_taux_median": (RETRAITE_MEDIAN, None, "revenu_disponible", 0.04,
                                           -1),
    "qf_parts_enf1": (AISE_2_ENFANTS, None, "ir", 1.0, -1),
    "qf_parts_enf2": (AISE_2_ENFANTS, None, "ir", 1.0, -1),
    "qf_parts_enf3_et_sup": (COUPLE_3_ENFANTS, None, "ir", 1.5, -1),
    "plafond_qf_parent_isole": (PARENT_ISOLE_AISE, None, "ir", 2_000.0, +1),
    "cotisations_salariales_retraite_echelle": (MODESTE, None, "revenu_disponible", 0.5, +1),
    "plafond_global_niches": (
        {**NICHE_FOYER, "children": [{"annee_naissance": 2019},
                                     {"annee_naissance": 2021},
                                     {"annee_naissance": 2022}]},
        {"salarie_domicile": 12_000,
         "frais_garde_par_enfant": [3_500.0, 3_500.0, 3_500.0]},
        "ir", 4_000.0, +1),
}

#: The year a case runs in, when not 2024: a knob of the 2026 curve does not exist
#: before it, and is refused there by name (D-042, D-240).
YEARS: dict[str, int] = {
    # The programmes of 2027 are priced on the law of 2026 (D-320).
    **dict.fromkeys((
        "csg_capital_taux_global", "prelevement_solidarite_capital",
        "csg_pensions_imposable_taux_plein", "csg_pensions_imposable_taux_median",
        "qf_parts_enf1", "qf_parts_enf2", "qf_parts_enf3_et_sup", "plafond_qf_parent_isole",
        "cotisations_salariales_retraite_echelle"), 2026),
    "allegement_general_t_min": 2026,
    "allegement_general_t_delta_moins_de_50": 2026,
    "allegement_general_t_delta_50_et_plus": 2026,
    # Portés, ils écrivent la revalorisation de l'année d'avant : en 2027, celle de 2026,
    # la première année qu'un chemin les chiffre (D-301). En 2024, le bouton du logement
    # lirait la révision de 2022, faite en juillet, dont l'octobre ne touche pas le loyer.
    "ppa_revalorisation_portee": 2027,
    "al_revalorisation_portee": 2027,
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
    "allegement_general_t_delta_50_et_plus": (
        "Le même cas pour la courbe de 2026 (D-240) : le `t_delta` des employeurs d'au "
        "moins 50 salariés, que `HouseholdInput` ne peut pas exprimer. Vérifié en 2026 : "
        "sur un foyer au SMIC, le porter de 0,3821 à 0,42 laisse `allegement_general` à "
        "8 707,78 EUR, inchangé au centime, quand le même saut du `t_delta` des moins de "
        "50 le porte à 9 623,17 EUR. La formule le lit (branche effectif >= 50) ; c'est "
        "le format d'entrée qui ne l'atteint pas."
    ),
    # Les IJ (D-306). Le format d'entrée ne porte aucune indemnité journalière : la
    # population les porte quand `impute_ij` tourne (D-305), et c'est sur elle que
    # `tests/test_ij_moteur.py` voit chacun des deux boutons bouger l'impôt ou le revenu
    # disponible, à l'euro, et ne rien bouger sans IJ.
    "ij_at_mp_part_exoneree": (
        "La part des IJ AT-MP exonérée d'IR (CGI art. 81, 8°). `HouseholdInput` ne porte "
        "aucune IJ, donc aucun ménage exprimable ne la fait bouger. Vérifié sur 40 ménages "
        "de la population, IJ imputées : la porter de 0,5 à 0 coûte 660 EUR d'IR au total, "
        "et rien sans les IJ (test_ij_moteur.py). La formule la lit (correction 22)."
    ),
    "ij_ald_part_exoneree": (
        "La part des IJ maladie servies au titre d'une ALD exonérée d'IR (CGI art. 80 "
        "quinquies, 1). `HouseholdInput` ne porte aucune IJ. Vérifié sur les mêmes 40 "
        "ménages : la porter à 0,5 fait entrer dans les salaires la moitié de leur part ALD, "
        "nette de CSG, et rien sans elles (test_ij_moteur.py). La correction 22 la lit (D-312)."
    ),
    "csg_ij_taux": (
        "Le taux de CSG des IJ (CSS art. L. 136-8). `HouseholdInput` ne porte aucune IJ. "
        "Vérifié sur les mêmes 40 ménages : 9,2 % au lieu de 6,2 % prend exactement trois "
        "points de leurs IJ au revenu disponible, et rien sans elles (test_ij_moteur.py). "
        "La correction 23 le lit."
    ),
}
