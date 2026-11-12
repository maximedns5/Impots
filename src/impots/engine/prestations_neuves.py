"""Les prestations neuves des programmes de 2027, en variables OpenFisca (but 21, étape 3).

Trois prestations que la loi n'a pas, chacune ajoutée au système par la réforme qui pose
son groupe de champs (`api.prestations_neuves`), et par elle seule : la loi de référence
n'en porte aucune variable, et une réforme qui ne pose aucun groupe laisse le système
intact. Le bouton à sa valeur par défaut, `None`, coûte donc exactement 0 €.

Chaque variable a une formule datée du 1er janvier de l'année chiffrée (nulle avant) et
entre dans le revenu disponible par `prestations_sociales`, enveloppée ici comme les
corrections enveloppent une formule d'openfisca (`engine.corrections`). Elle a sa ligne au
registre (`engine.outputs`, une ligne `projet` : zéro là où la variable n'existe pas), sa
place parmi les transferts du garde des secteurs (`guards.STATE_TRANSFERS`) et parmi les
postes sans multiplicateur (`macro.shocks.UNMAPPED`, « transfert »). Les prestations
qu'elle remplace sont mises à zéro par une formule datée du même jour, qui garde celles
d'openfisca avant : elles disparaissent du revenu disponible, de leur ligne et de ce qui
les lit (la prime de Noël suit le RSA et l'ASS ; la CRDS de la prime d'activité suit la
prime ; celle des allocations familiales les suit).

---

**Le revenu d'incitation à l'activité (`ria`, individu, mois).** Pour une personne d'âge
`age_minimum` ≤ âge < `age_maximum` :

    ria = max(0, socle + insertion × justifie − taux_revenus_activite × activité
                 − taux_autres_revenus × remplacement)

et 0 si `activité` dépasse `plafond_revenus_activite`. `activité` : le salaire net du mois
et le douzième du revenu d'indépendant imposable de l'année (positif) ; `remplacement` :
l'allocation chômage et la pension de retraite nettes du mois. `justifie` : la personne a
un revenu d'activité dans le mois, ou, avec `insertion_demandeurs_emploi`, touche une
allocation chômage ou est déclarée chômeuse. Une allocation individuelle : ni le conjoint
ni les enfants ne la changent (« le RIA ne dépend pas de la situation familiale »). Elle
n'est pas imposable, ne porte ni CSG ni CRDS, et n'entre pas dans les ressources des
aides au logement ni des prestations familiales (« n'interfère ni avec les allocations
familiales ni avec les aides au logement »).

*Ce qu'elle remplace* : le RSA, la prime d'activité, l'ASS (chacun par son drapeau) et,
avec eux, la prime de Noël. *Ce qu'elle laisse* : les aides au logement, les prestations
familiales, l'AAH, l'ASPA. *Ce que le moteur ne lit pas* : la condition de « situation
régulière » (la population ne porte pas la nationalité), les heures de formation ou de
recherche d'emploi (d'où l'hypothèse de `justifie`).

*Le non-recours, une hypothèse* : celui du RSA, la prestation qu'elle remplace et dont
elle reprend le socle. La passe de population le sert en espérance avec la loi du RSA
(`population.recours`, τ = 79 €, p_max calé), sur le droit de la famille par unité de
consommation ramené en euros de 2021 par le montant de base du RSA. Une personne qui
touchait la prime d'activité recourt donc au RIA comme un allocataire du RSA, plus
souvent qu'à la prime : un biais à dire.

**L'allocation par enfant (`allocation_enfant`, famille, mois).** Pour chaque enfant de la
famille d'âge < `age_maximum`, l'aîné étant le premier :

    montant_par_enfant, ou montant_troisieme_enfant pour le troisième ;

ou, avec `par_famille`, `montant_par_enfant` une fois pour la famille qui a un enfant
éligible. Avec `degressivite_part_ir` > 0, la somme baisse de cette part du douzième de
l'impôt sur le revenu du foyer fiscal du demandeur, sans descendre sous
`plancher_par_enfant` par enfant éligible (ni monter au-dessus de la somme). Elle n'est ni
imposable, ni soumise à la CRDS (le revenu familial passe par la DGFiP), et n'entre pas
dans les ressources du RSA, de la prime d'activité ni des aides au logement : une
hypothèse, que le revenu familial suggère (le candidat reproche au RSA et à la prime de
compter les allocations familiales) sans l'écrire.

*Ce qu'elle remplace* : les allocations familiales (avec la majoration pour âge et le
forfait), le complément familial et l'allocation de rentrée scolaire, chacun par son
drapeau. *Ce qu'elle laisse* : la PAJE, l'ASF, l'AEEH, les aides au logement. Le quotient
familial et la réduction pour frais de scolarité ont leurs boutons. *Ce que le moteur ne
lit pas* : la condition de cinq ans de résidence régulière et d'activité du revenu
familial, ni le supplément familial de traitement ni les bourses, qu'il remplace aussi.

*Le non-recours, une hypothèse* : 1, celui des allocations familiales dans le moteur, que
la Caf verse sans demande dès qu'elle connaît l'enfant, et le revenu familial passerait
par le prélèvement à la source.

**La garantie d'autonomie des jeunes (`garantie_autonomie`, individu, mois).** Pour une
personne d'âge `age_minimum` ≤ âge < `age_maximum` :

    garantie = max(0, seuil − taux_ressources × ressources propres du mois)

`ressources propres` : le salaire net, le douzième du revenu d'indépendant imposable
(positif), l'allocation chômage et la pension nettes. Ni les ressources des parents ni les
prestations de la famille. Elle n'est ni imposable ni soumise à la CRDS, et n'entre dans
les ressources d'aucune autre prestation. *Ce qu'elle remplace* : rien ; un jeune au RSA ou
à la prime d'activité garde l'un et l'autre, calculés sans elle. *Le non-recours, une
hypothèse* : celui du RSA, une allocation différentielle à demander, servi de même.

**L'assurance chômage** n'a pas de variable : voir `api.prestations_neuves`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np

if TYPE_CHECKING:  # pragma: no cover - typing only
    from impots.api.schemas import ReformSpec

#: Les variables de chaque groupe, du même nom que son champ et sa ligne au registre.
VARIABLES = ("ria", "allocation_enfant", "garantie_autonomie")

#: La variable que chaque drapeau de remplacement met à zéro.
REMPLACEES = {
    "remplace_rsa": "rsa",
    "remplace_ppa": "ppa",
    "remplace_ass": "ass",
    "remplace_af": "af",
    "remplace_cf": "cf",
    "remplace_ars": "ars",
}


def actives(spec: ReformSpec | None) -> tuple[str, ...]:
    """Les prestations neuves qu'une réforme pose."""
    if spec is None:
        return ()
    return tuple(name for name in VARIABLES if getattr(spec, name, None) is not None)


def appliquer(reform: Any, spec: ReformSpec, year: int) -> None:
    """Ajoute au système de `reform` les prestations que `spec` pose, met à zéro celles
    qu'elles remplacent et les verse au revenu disponible, à partir du 1er janvier de
    `year`. Ne fait rien pour une réforme qui n'en pose aucune."""
    groupes = actives(spec)
    if not groupes:
        return
    builders = {"ria": _ria, "allocation_enfant": _allocation_enfant,
                "garantie_autonomie": _garantie_autonomie}
    for name in groupes:
        reform.add_variable(builders[name](getattr(spec, name), year))
    remplacees = sorted({variable for name in groupes
                         for drapeau, variable in REMPLACEES.items()
                         if getattr(getattr(spec, name), drapeau, False)})
    for variable in remplacees:
        reform.update_variable(_nulle(reform.get_variable(variable), year))
    sociales = reform.get_variable("prestations_sociales").get_formula(f"{year}-01-01")
    reform.update_variable(_prestations_sociales(sociales, groupes, year))


def _formula_name(year: int) -> str:
    return f"formula_{year}_01_01"


def _variable(name: str, entity: Any, label: str, formula: Any, year: int) -> Any:
    """Une variable mensuelle en euros, dont la formule part du 1er janvier de `year`."""
    from openfisca_core.model_api import MONTH, Variable

    return type(name, (Variable,), {
        "value_type": float,
        "entity": entity,
        "label": label,
        "definition_period": MONTH,
        _formula_name(year): formula,
    })


def _activite(individu: Any, period: Any) -> Any:
    """Les revenus d'activité nets du mois : le salaire net et le douzième du revenu
    d'indépendant imposable de l'année, s'il est positif."""
    rpns = individu("rpns_imposables", period.this_year) / 12.0
    return individu("salaire_net", period) + np.maximum(rpns, 0.0)


def _remplacement(individu: Any, period: Any) -> Any:
    """Les revenus de remplacement nets du mois : l'allocation chômage et la pension."""
    return individu("chomage_net", period) + individu("retraite_nette", period)


def _ria(groupe: Any, year: int) -> Any:
    from openfisca_france.entities import Individu
    from openfisca_france.model.base import TypesActivite

    def formula(individu, period, parameters):
        age = individu("age", period)
        eligible = (age >= groupe.age_minimum) & (age < groupe.age_maximum)
        activite = _activite(individu, period)
        justifie = activite > 0
        if groupe.insertion_demandeurs_emploi:
            chomeur = individu("activite", period) == TypesActivite.chomeur
            justifie = justifie | chomeur | (individu("chomage_brut", period) > 0)
        montant = np.maximum(
            0.0,
            groupe.socle + groupe.insertion * justifie
            - groupe.taux_revenus_activite * activite
            - groupe.taux_autres_revenus * _remplacement(individu, period))
        if groupe.plafond_revenus_activite is not None:
            montant = np.where(activite > groupe.plafond_revenus_activite, 0.0, montant)
        return eligible * montant

    return _variable("ria", Individu, "Revenu d'incitation à l'activité (but 21, étape 3)",
                     formula, year)


def _allocation_enfant(groupe: Any, year: int) -> Any:
    from openfisca_france.entities import Famille

    troisieme = (groupe.montant_par_enfant if groupe.montant_troisieme_enfant is None
                 else groupe.montant_troisieme_enfant)

    def formula(famille, period, parameters):
        age = famille.members("age", period)
        eligible = famille.members.has_role(Famille.ENFANT) & (age < groupe.age_maximum)
        nombre = famille.sum(eligible)
        if groupe.par_famille:
            total = groupe.montant_par_enfant * (nombre > 0)
            plancher = groupe.plancher_par_enfant * (nombre > 0)
        else:
            rang = famille.members.get_rank(famille, -age, condition=eligible)
            par_enfant = np.where(rang == 2, troisieme, groupe.montant_par_enfant)
            total = famille.sum(eligible * par_enfant)
            plancher = groupe.plancher_par_enfant * nombre
        if groupe.degressivite_part_ir > 0:
            impot_i = famille.members.foyer_fiscal("impot_revenu_restant_a_payer",
                                                   period.this_year)
            # openfisca stocke l'impôt négatif : ce que le foyer paie est son opposé.
            impot = -famille.value_from_person(impot_i, role=Famille.DEMANDEUR)
            reduit = total - groupe.degressivite_part_ir * np.maximum(impot, 0.0) / 12.0
            total = np.minimum(total, np.maximum(reduit, plancher))
        return total

    return _variable("allocation_enfant", Famille,
                     "Allocation par enfant dès le premier (but 21, étape 3)", formula, year)


def _garantie_autonomie(groupe: Any, year: int) -> Any:
    from openfisca_france.entities import Individu

    def formula(individu, period, parameters):
        age = individu("age", period)
        eligible = (age >= groupe.age_minimum) & (age < groupe.age_maximum)
        ressources = _activite(individu, period) + _remplacement(individu, period)
        return eligible * np.maximum(0.0, groupe.seuil - groupe.taux_ressources * ressources)

    return _variable("garantie_autonomie", Individu,
                     "Garantie d'autonomie des jeunes (but 21, étape 3)", formula, year)


def _nulle(variable: Any, year: int) -> Any:
    """La variable d'openfisca, nulle à partir du 1er janvier de `year` ; ses formules
    d'avant restent (`update_variable` les garde)."""
    from openfisca_core.model_api import Variable

    def formula(population, period, parameters):
        return np.zeros(population.count)

    return type(variable.name, (Variable,), {
        "label": f"{variable.label} (remplacée par une prestation neuve, but 21)",
        _formula_name(year): formula,
    })


def _prestations_sociales(openfisca_formula: Any, groupes: tuple[str, ...], year: int) -> Any:
    """`prestations_sociales`, avec les prestations neuves de l'année : la formule
    d'openfisca pour le reste."""
    import inspect

    from openfisca_core.model_api import ADD, Variable

    # openfisca's own takes `(famille, period)`; a wrapped one may take the parameters too.
    avec_parametres = len(inspect.signature(openfisca_formula).parameters) > 2

    def formula(famille, period, parameters):
        neuves = 0.0
        for name in groupes:
            if name == "allocation_enfant":
                neuves = neuves + famille(name, period, options=[ADD])
            else:
                neuves = neuves + famille.sum(famille.members(name, period, options=[ADD]))
        avant = (openfisca_formula(famille, period, parameters) if avec_parametres
                 else openfisca_formula(famille, period))
        return avant + neuves

    return type("prestations_sociales", (Variable,), {
        "label": "Prestations sociales, les prestations neuves comprises (but 21, étape 3)",
        _formula_name(year): formula,
    })
