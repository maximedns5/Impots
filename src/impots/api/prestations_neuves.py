"""Les prestations neuves des programmes de 2027, comme groupes de champs de `ReformSpec`
(but 21, étape 3).

Un groupe par prestation que le moteur ne porte pas : le revenu d'incitation à l'activité
(`ria`), une allocation par enfant dès le premier (`allocation_enfant`) et une garantie
d'autonomie des jeunes (`garantie_autonomie`). Chacun vaut `None` par défaut, et une
réforme qui ne le pose pas ne touche pas au système : la loi n'en voit aucune variable,
et le bouton à sa valeur par défaut coûte exactement 0 €.

Dans chaque groupe, deux sortes de champs, et la différence compte :

* **ceux du candidat** (un montant, un taux, un âge qu'il énonce, ce que la prestation
  remplace) n'ont pas de valeur par défaut : la réforme qui pose le groupe les écrit, et
  le fragment d'un programme les tire de sa citation ;
* **ceux de la traduction** (ce que le candidat ne dit pas et que le moteur doit
  trancher) ont une valeur par défaut, une hypothèse dite dans leur description, que
  l'utilisateur peut faire varier.

Les formules sont dans `impots.engine.prestations_neuves` ; la documentation de chaque
règle, de ce qu'elle remplace, de ce qu'elle laisse et de son non-recours y est aussi.

**L'assurance chômage n'a pas de groupe.** La population porte un montant annuel
d'allocation par chômeur au sens du BIT, tiré et calé sur la masse de l'Unédic
(`population.incomes`), réparti sur les mois sans salaire : ni durée d'indemnisation
écoulée, ni salaire journalier de référence, ni motif de fin de contrat, ni âge à
l'ouverture des droits. Aucune des règles des programmes (durée maximale de 12 mois sous
50 ans, rupture conventionnelle indemnisée six mois, abrogation des réformes de 2019 à
2025 qui portent sur l'accès, le montant, la durée et la dégressivité) ne se lit sur ces
données sans en inventer la moitié : elles restent refusées, porte « prestations hors du
modèle ».
"""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator

#: Le même réglage que les modèles d'entrée de `api.schemas` : pas d'infini ni de NaN, pas
#: de champ inconnu (D-173).
_CONFIG = ConfigDict(extra="forbid", allow_inf_nan=False)

#: €/mois : la borne haute de chaque montant. Large exprès, comme les prestations de B1 :
#: une borne « réaliste » serait un jugement politique habillé en validation.
MONTANT_MAX = 5_000.0


class RIA(BaseModel):
    """Le revenu d'incitation à l'activité : une allocation **individuelle**, mensuelle,
    `socle + insertion − taux × revenus d'activité − autres revenus`, bornée à zéro et
    nulle au-delà d'un plafond de revenus d'activité. Le programme de Retailleau (r15) :
    socle 300 €, insertion 250 €, 30 % du salaire déduit, extinction au-delà de 1 833 €
    de revenus d'activité par mois, de 18 à 65 ans, à la place du RSA, de la prime
    d'activité et de l'ASS."""

    model_config = _CONFIG

    # --- ce que le candidat énonce -------------------------------------------------------
    socle: Annotated[float, Field(ge=0, le=MONTANT_MAX)]
    """€/mois, versé à toute personne éligible sans revenu."""
    insertion: Annotated[float, Field(ge=0, le=MONTANT_MAX)]
    """€/mois, ajouté au socle d'une personne qui travaille, ou qui justifie de son
    activité de recherche d'emploi (voir `insertion_demandeurs_emploi`)."""
    taux_revenus_activite: Annotated[float, Field(ge=0.0, le=1.0)]
    """La part des revenus d'activité nets du mois déduite de l'allocation."""
    plafond_revenus_activite: Annotated[float, Field(ge=0, le=100_000)] | None = None
    """€/mois de revenus d'activité nets au-delà desquels l'allocation est nulle ; `None`
    si le candidat n'en dit pas (la déduction seule l'éteint). La seule valeur par défaut
    d'un champ du candidat : une réforme se relit par `model_dump(exclude_none=True)`, qui
    ôte un `None` imbriqué, et le défaut doit le rendre."""
    remplace_rsa: bool
    remplace_ppa: bool
    remplace_ass: bool
    """Les prestations que le RIA remplace, nulles dès le 1er janvier de l'année chiffrée.
    La prime de Noël, versée aux allocataires du RSA et de l'ASS, s'éteint avec eux."""

    # --- ce que le moteur tranche, des hypothèses ---------------------------------------
    age_minimum: Annotated[int, Field(ge=14, le=70)] = 18
    """Âge à partir duquel la personne est éligible. 18 : « une personne adulte »."""
    age_maximum: Annotated[int, Field(ge=15, le=120)] = 65
    """Âge à partir duquel elle ne l'est plus. 65 : « de moins de 65 ans »."""
    insertion_demandeurs_emploi: bool = True
    """Hypothèse : une personne sans activité qui touche une allocation chômage dans le
    mois, ou que le ménage déclare chômeuse, justifie des quinze heures de recherche
    d'emploi et touche l'insertion. La population ne porte ni les heures de formation ni
    celles de recherche ; une personne inactive sans allocation chômage ne la touche pas."""
    taux_autres_revenus: Annotated[float, Field(ge=0.0, le=1.0)] = 1.0
    """Hypothèse : la part des revenus de remplacement nets de la personne (allocation
    chômage, pension de retraite) déduite de l'allocation. 1 : le RIA « Socle » est versé
    à une personne « sans activité et sans revenu » ; le candidat ne dit pas comment un
    revenu autre que le salaire l'entame, et une allocation différentielle à 100 % est la
    règle du RSA et de l'ASS qu'il remplace."""

    @model_validator(mode="after")
    def _ages(self) -> RIA:
        if self.age_minimum >= self.age_maximum:
            raise ValueError(f"RIA : l'âge minimum ({self.age_minimum}) doit rester sous "
                             f"l'âge maximum ({self.age_maximum}).")
        return self


class AllocationEnfant(BaseModel):
    """Une allocation par enfant à charge **dès le premier**, mensuelle, versée à la
    famille. Un même moteur pour deux mesures : le revenu familial de Retailleau (r27 :
    240 € par enfant de la naissance à 18 ans, 480 € pour le troisième, à la place des
    allocations familiales, de leur majoration pour âge, du complément familial et de
    l'allocation de rentrée scolaire) et l'allocation familiale unique de Philippe (p11 :
    350 € par mois dès le premier enfant, dégressive selon l'impôt sur le revenu)."""

    model_config = _CONFIG

    # --- ce que le candidat énonce -------------------------------------------------------
    montant_par_enfant: Annotated[float, Field(ge=0, le=MONTANT_MAX)]
    """€/mois, pour chaque enfant éligible (ou pour la famille, `par_famille`)."""
    montant_troisieme_enfant: Annotated[float, Field(ge=0, le=MONTANT_MAX)] | None = None
    """€/mois pour le troisième enfant éligible, l'aîné étant le premier ; `None` : le
    montant de chaque enfant."""
    age_maximum: Annotated[int, Field(ge=1, le=25)]
    """L'enfant est éligible jusqu'à la veille de cet âge : 18 pour « de la naissance
    jusqu'à 18 ans »."""
    remplace_af: bool
    remplace_cf: bool
    remplace_ars: bool
    """Les prestations familiales que l'allocation remplace, nulles dès le 1er janvier de
    l'année chiffrée (les allocations familiales avec leur majoration pour âge et leur
    forfait). Le quotient familial et la réduction d'impôt pour frais de scolarité, que le
    revenu familial remplace aussi, ont leurs boutons (`qf_parts_enf*`,
    `frais_scolarite_*`) : le fragment du programme les pose à côté."""

    # --- ce que le moteur tranche, des hypothèses ---------------------------------------
    par_famille: bool = False
    """Hypothèse de lecture : le montant est versé une fois par famille qui a au moins un
    enfant éligible, et non par enfant. Faux par défaut."""
    degressivite_part_ir: Annotated[float, Field(ge=0.0, le=10.0)] = 0.0
    """Hypothèse de traduction : l'allocation annuelle de la famille baisse de cette part
    de l'impôt sur le revenu de son foyer fiscal (celui du demandeur), un douzième par
    mois. 0 : pas de dégressivité. Philippe dit l'allocation « dégressive en fonction de
    l'impôt sur le revenu » sans barème : la mesure est vague sur ce point, et ce champ
    seul la rend chiffrable."""
    plancher_par_enfant: Annotated[float, Field(ge=0, le=MONTANT_MAX)] = 0.0
    """€/mois par enfant éligible sous lequel la dégressivité ne descend pas."""


class GarantieAutonomie(BaseModel):
    """La garantie d'autonomie des jeunes : une allocation **individuelle**, mensuelle,
    différentielle, qui porte les ressources propres de chaque jeune d'une tranche d'âge à
    un seuil. Le programme de Mélenchon : « plus aucun jeune ne doit vivre sous le seuil
    de pauvreté, fixé à 1 337 euros par mois »."""

    model_config = _CONFIG

    # --- ce que le candidat énonce -------------------------------------------------------
    seuil: Annotated[float, Field(ge=0, le=MONTANT_MAX)]
    """€/mois de ressources propres que la garantie complète."""

    # --- ce que le moteur tranche, des hypothèses ---------------------------------------
    age_minimum: Annotated[int, Field(ge=14, le=40)] = 18
    age_maximum: Annotated[int, Field(ge=15, le=41)] = 25
    """Hypothèse : de 18 ans à la veille de 25 ans, l'âge sous lequel le RSA est fermé
    sans enfant ni activité suffisante. Le candidat dit « les jeunes », sans âge."""
    taux_ressources: Annotated[float, Field(ge=0.0, le=1.0)] = 1.0
    """Hypothèse : la part des ressources propres nettes du mois (salaire, revenu
    d'indépendant, allocation chômage, pension) que la garantie déduit. 1 : elle les
    complète au seuil, ni plus ni moins. Les ressources des parents ne comptent pas
    (« autonomie »), ni les prestations de la famille."""

    @model_validator(mode="after")
    def _ages(self) -> GarantieAutonomie:
        if self.age_minimum >= self.age_maximum:
            raise ValueError(f"garantie d'autonomie : l'âge minimum ({self.age_minimum}) "
                             f"doit rester sous l'âge maximum ({self.age_maximum}).")
        return self


#: Le champ de `ReformSpec` de chaque groupe, et sa ligne au registre du moteur.
GROUPES = ("ria", "allocation_enfant", "garantie_autonomie")

#: Les boutons de `ReformSpec` qu'une prestation remplacée rend morts : la réforme qui pose
#: les deux est refusée, plutôt que de laisser un bouton écrire dans une prestation nulle.
BOUTONS_REMPLACES: dict[tuple[str, str], tuple[str, ...]] = {
    ("ria", "remplace_rsa"): ("rsa_montant_de_base", "rsa_forfait_logement_1_personne",
                              "rsa_forfait_logement_2_personnes",
                              "rsa_forfait_logement_3_personnes_ou_plus"),
    ("ria", "remplace_ppa"): ("ppa_montant_de_base", "ppa_pente", "ppa_bonification_taux_max",
                              "ppa_revalorisation_avril", "ppa_revalorisation_portee"),
    ("allocation_enfant", "remplace_af"): (
        "af_taux_2_enfants", "af_taux_3_enfants", "af_modulation_taux_tranche_2",
        "af_modulation_taux_tranche_3", "af_plafond_tranche_1_base",
        "af_plafond_tranche_2_base", "af_majoration_plafond_par_enfant"),
}


def boutons_morts(spec: object) -> list[str]:
    """Les boutons posés par `spec` qu'une prestation neuve qu'il pose aussi rend morts."""
    morts = []
    for (groupe, drapeau), boutons in BOUTONS_REMPLACES.items():
        valeur = getattr(spec, groupe, None)
        if valeur is not None and getattr(valeur, drapeau):
            morts += [b for b in boutons if getattr(spec, b, None) is not None]
    return morts
