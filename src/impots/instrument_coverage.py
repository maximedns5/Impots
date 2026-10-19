"""Phase 8 §2.4 — « le maximum d'instruments », as an auditable claim rather than a vibe.

§2.4 defines the phase's breadth claim: every instrument of the inventory is either
**priced** (bucket A or B), **gated** with the gate named (C), or **refused** with the
reason displayed (D) — and the claim is checked against a published universe rather
than asserted. This module is the table that claim is computed from.

**Nothing here is typed that the code cannot be asked about.** Every row naming a knob,
a firm-spec field or an aggregate instrument is verified by `tests/test_instrument_
coverage.py` against the real objects: a row claiming the tool prices something it
cannot is the failure mode this table exists to prevent, and it is the one a reader
would never catch. That is the `plf_coverage.py` discipline applied to the instrument
universe instead of to a PLF's articles.

**What this table does NOT carry is euros**, and the absence is the honest state rather
than an omission. §2.4 wants coverage weighed against the Voies et Moyens universe above
a threshold; the receipts of each line come from that document, this repository does not
carry it (`docs/M2_ANCHORS.md`), and **the threshold itself has never been recorded** —
§9 expects it as a D-entry and there is none. So the coverage claim here is by COUNT and
says so; weighing it by euros waits on both. A count treats a droit de timbre and a
four-billion contribution alike, which is exactly why `plf_coverage.py` reports two
headlines that disagree — the same correction is owed here and cannot be made yet.
"""

from __future__ import annotations

from dataclasses import dataclass

#: §2.1's four buckets, and nothing else. A row outside them is a row nobody classified.
BUCKETS = ("A", "B", "C", "D")

#: Where §2.3's inventory is transcribed from. Rows are the spec's, not this module's.
SPEC = "docs/PHASE8_SPEC.md §2.3.1–§2.3.3"


@dataclass(frozen=True)
class Instrument:
    """One line of the inventory, with whatever makes its bucket checkable.

    `prices_with` is the load-bearing field for A and B: the names the row claims the
    code carries. The tests resolve every one of them. For C it must name its gate, for
    D its reason — §2.1 makes refusals allowlists that SPEAK, so a D row with no reason
    is a silent omission wearing a classification.
    """

    code: str
    label: str
    family: str          # produits | personnes | entreprises
    bucket: str
    prices_with: tuple[str, ...] = ()
    gate: str = ""
    reason: str = ""
    note: str = ""
    already_live: bool = False   # « déjà en place » before Phase 8
    added_by: str = ""
    """The D-entry that priced it AFTER Phase 8, if one did: a row priced later must not
    be counted as what Phase 8 added (D-222, the CIR)."""

    def __post_init__(self) -> None:
        if self.bucket not in BUCKETS:
            raise ValueError(f"{self.code}: bucket {self.bucket!r} hors de {BUCKETS}")


#: §2.3.1 — produits. Every row's bucket is the spec's.
PRODUITS: tuple[Instrument, ...] = (
    Instrument("tva", "TVA (20 / 10 / 5,5 / 2,1)", "produits", "B",
               prices_with=(),
               note="Ventilation par taux depuis la CN COICOP (R5) absente : reprise "
                    "proportionnelle seulement, et le sous-bouton « restructuration "
                    "d'assiette » reste D tant que R5 ne donne pas l'assiette par taux. "
                    "L'arbre porte bien les quatre taux (0,20 / 0,10 / 0,055 / 0,021)."),
    Instrument("accise_energies", "Accise énergies (ex-TICPE)", "produits", "B",
               note="Tarif × volume : volumes CCTN/DGEC non manifestés."),
    Instrument("accise_tabacs", "Accise tabacs", "produits", "B",
               note="Volumes OFDT non manifestés. Cas noté de §6.2."),
    Instrument("accise_alcools", "Accise alcools", "produits", "B",
               note="Volumes DGDDI/OFDT non manifestés."),
    Instrument("accise_electricite_gaz", "Accise électricité / gaz", "produits", "B",
               note="Historique de tarifs post-2022 heurté ; ancrer sur la dernière "
                    "année close."),
    Instrument("tsn", "Taxe sur les services numériques", "produits", "B",
               prices_with=("agregats:tsn",)),
    Instrument("ttf", "Taxe sur les transactions financières", "produits", "B",
               prices_with=("agregats:ttf",)),
    Instrument("carbone_nouveau", "Instruments carbone nouveaux (hypothétiques)",
               "produits", "D",
               reason="Ce projet REPRIX des instruments qui existent en droit ; il ne "
                      "conçoit pas de taxes hypothétiques. C'est un autre produit, avec "
                      "d'autres exigences d'honnêteté."),
)

#: §2.3.2 — personnes.
PERSONNES: tuple[Instrument, ...] = (
    Instrument("ir", "IR (barème, décote, QF, CEHR, niches)", "personnes", "A",
               prices_with=("knob:decote_taux", "knob:decote_seuil_celib",
                            "knob:plafond_qf_demi_part", "knob:saldom_taux"),
               already_live=True),
    Instrument("csg_crds", "CSG / CRDS", "personnes", "A",
               prices_with=("knob:csg_activite_deductible",
                            "knob:csg_activite_imposable"),
               already_live=True),
    Instrument("pfu_menage", "PFU / RCM — calculateur ménage", "personnes", "A",
               already_live=True,
               note="Couche ménage seulement ; la couche population est la ligne "
                    "suivante."),
    Instrument("pfu_population", "PFU — couche population", "personnes", "C",
               gate="F1B_CAPITAL_GATE (RCM par tranche)",
               note="La phase 8 ne l'avance ni ne le bloque."),
    Instrument("cdhr", "CDHR", "personnes", "D",
               reason="Refus fermé : seuil-sur-ratio, mal posé depuis des moyennes de "
                      "cellules à toute granularité. Restated ici pour que « maximum "
                      "d'instruments » ne se lise pas comme une réouverture."),
    Instrument("ifi", "IFI (et ISF/IGF historiques)", "personnes", "A",
               prices_with=("knob:ifi_decote_taux", "knob:ifi_plafonnement_taux",
                            "knob:ifi_forfait_mobilier"),
               already_live=True),
    Instrument("dmtg", "DMTG (successions, donations)", "personnes", "C",
               gate="F7 (inchangé, non élargi par cette phase — R6)"),
    Instrument("th_rs_thlv", "TH résidences secondaires + THLV", "personnes", "C",
               gate="R7 — recon REI",
               note="rei_2025.zip EST manifesté et sourcé, et verify_rei.py existe ; la "
                    "recon n'a pas tourné faute du fichier sur cette machine. C→B si le "
                    "REI porte l'assiette, avec agrégation communale vers le national "
                    "et jamais de distribution par ménage."),
    Instrument("tf_menages", "Taxe foncière (part ménages)", "personnes", "C",
               gate="R7 — recon REI",
               note="Même route. Le partage ménages/entreprises de la TF est lui-même "
                    "NON MESURÉ : sans partage publié, l'instrument chiffre le total "
                    "avec le partage étiqueté « scénario »."),
    Instrument("prestations", "Prestations (RSA, PPA, AF, AL…)", "personnes", "A",
               prices_with=("knob:rsa_montant_de_base", "knob:ppa_pente",
                            "knob:af_taux_2_enfants", "knob:al_minoration_forfaitaire"),
               already_live=True,
               note="Instruments de dépense : ils entrent au §3 par le solde primaire "
                    "comme toute réforme."),
)

#: §2.3.3 — entreprises.
ENTREPRISES: tuple[Instrument, ...] = (
    Instrument("is", "IS (taux normal/réduit, CS, CEBGE)", "entreprises", "A",
               prices_with=("firm:is_taux_normal", "firm:is_taux_reduit",
                            "firm:cs_taux", "firm:cebge_seuils_et_taux"),
               already_live=True),
    Instrument("cvae_c3s", "CVAE (jusqu'en 2030), C3S", "entreprises", "A",
               prices_with=("firm:cvae_taux_max", "firm:c3s_taux",
                            "firm:c3s_abattement"),
               already_live=True),
    Instrument("cotisations", "Cotisations et allègements", "entreprises", "A",
               prices_with=("knob:allegement_general_plafond", "knob:bandeau_maladie_taux",
                            "plafond:bandeau_famille_plafond"),
               already_live=True),
    Instrument("cir", "CIR", "entreprises", "B",
               prices_with=("firm:cir_taux", "firm:cir_taux_au_dela"),
               added_by="D-222",
               note="Chiffré AVEC BANNIÈRE sur le flux de créance du millésime GECIR 2019 "
                    "(semi-définitif), au taux plein sous le seuil de dépenses par "
                    "déclarant et au taux réduit au-delà : la ventilation reconstruit la "
                    "créance publiée à 0,09 % près. La dépense fiscale de Voies et Moyens "
                    "est montrée à côté, jamais à la place ; le stock de reports reste NON "
                    "MESURÉ."),
    Instrument("taxe_sur_les_salaires", "Taxe sur les salaires", "entreprises", "B",
               prices_with=("agregats:taxe_sur_les_salaires",),
               note="L'incidence sectorielle (banques, santé, associations) se STATUE en "
                    "composition depuis des sources publiées ; elle ne se modélise pas "
                    "en distribution."),
    Instrument("versement_mobilite", "Versement mobilité", "entreprises", "B",
               prices_with=("agregats:versement_mobilite",),
               note="Multiplicateur uniforme ; les taux par AOM sont D — pas de "
                    "simulateur local."),
    Instrument("dmto", "DMTO", "entreprises", "B",
               prices_with=("agregats:dmto",)),
    Instrument("tascom", "TASCOM", "entreprises", "B",
               prices_with=("agregats:tascom",)),
    Instrument("tgap", "TGAP", "entreprises", "B",
               prices_with=("agregats:tgap",)),
    Instrument("forfait_social", "Forfait social", "entreprises", "B",
               prices_with=("agregats:forfait_social",)),
    Instrument("taxe_apprentissage", "Taxe d'apprentissage et assimilés",
               "entreprises", "B",
               prices_with=("agregats:taxe_apprentissage",)),
    Instrument("cfe_locales", "CFE / CVAE locales au-delà de l'existant",
               "entreprises", "C",
               gate="Réemploi du REI uniquement — aucun nouveau simulateur local"),
)

INVENTORY: tuple[Instrument, ...] = PRODUITS + PERSONNES + ENTREPRISES


def by_bucket(bucket: str) -> tuple[Instrument, ...]:
    return tuple(i for i in INVENTORY if i.bucket == bucket)


def priced() -> tuple[Instrument, ...]:
    """A and B alike — but only the ones that actually name what prices them.

    A B-bucket row with an empty `prices_with` is CLASSIFIED, not priced: the TVA and
    the four accises sit there today, blocked on sources. Counting them as priced is
    the exact overstatement §2.4 exists to prevent.
    """
    return tuple(i for i in INVENTORY if i.bucket in ("A", "B") and i.prices_with)


def classified_but_unbuilt() -> tuple[Instrument, ...]:
    return tuple(i for i in INVENTORY if i.bucket in ("A", "B") and not i.prices_with)


def share_priced() -> float:
    return len(priced()) / len(INVENTORY)


def new_in_phase_8() -> tuple[Instrument, ...]:
    """What this phase added, as opposed to what it inherited and re-declared."""
    return tuple(i for i in priced() if not i.already_live and not i.added_by)


def added_after_phase_8() -> tuple[Instrument, ...]:
    """Priced by a later D-entry, each naming it."""
    return tuple(i for i in priced() if i.added_by)
