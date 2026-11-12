"""Les boutons des programmes de 2027 qui ne sont pas un paramètre de l'arbre (but 21, étape 2).

Le but 21 ouvre les mesures que le moteur savait calculer sans avoir de bouton pour elles.
Quatre ne se règlent pas en écrivant un paramètre d'openfisca : elles changent une formule
ou une donnée. Chacune est ici, avec ce qu'elle fait et ce qu'elle ne fait pas.

* **L'exonération d'impôt sur le revenu des jeunes** (`ir_exoneration_jeunes_age`,
  `ir_exoneration_jeunes_plafond_smic`). Les salaires imposables d'une personne de moins de
  l'âge dit, au 1er janvier de l'année des revenus, sortent du revenu catégoriel des
  traitements et salaires, jusqu'au plafond dit en SMIC brut annuels : la part exonérée est
  celle du salaire imposable qui correspond aux premiers euros bruts, jusqu'au plafond. Un
  abattement, pas une falaise : le salaire au-dessus du plafond reste imposé, et rien de
  l'exonération n'est perdu. C'est l'hypothèse de traduction ; la lecture « exonéré
  seulement sous le plafond, tout imposé au-dessus » est l'autre, et n'est pas codée. Les
  revenus des non-salariés, les pensions et le chômage ne sont pas exonérés ; le revenu
  fiscal de référence perd la part exonérée, comme celle de la correction 24 ; les
  prestations, qui lisent le salaire entier, ne bougent pas.
* **La suppression du prélèvement forfaitaire unique** (`pfu_supprime`). Chaque foyer est
  imposé comme s'il cochait la case 2OP : ses revenus du capital passent au barème, avec ce
  que le barème leur donne (l'abattement de 40 % sur les dividendes, la CSG déductible sur
  ces revenus). Les prélèvements sociaux ne changent pas. Ce que la population porte de ces
  revenus est l'imputation de D-248 (2DC, 2TR, 2TS, 3VG) : le bouton entre dans
  `CAPITAL_KNOBS`, et une passe qui le règle impute le capital. L'assurance vie, les
  plus-values d'avant 2018 et leurs abattements pour durée de détention, que la population ne
  porte pas, ne sont pas chiffrés.
* **La réduction d'impôt des familles** (`reduction_impot_familles_montant`,
  `reduction_impot_familles_enfants_min`). Un montant par foyer fiscal qui compte au moins
  ce nombre de personnes à charge et dont un déclarant au moins a un revenu d'activité
  (salaire ou revenu non salarié imposable) : « les familles qui travaillent ». Une
  réduction, pas un crédit : elle s'arrête à l'impôt dû, comme les autres réductions, et un
  foyer non imposable n'en reçoit rien. Hors du plafond global des niches.
* **L'indexation année par année** (`indexations`). Pour chaque prestation, un coefficient
  par année, écrit à la date légale de sa revalorisation de cette année-là, sur ce que
  l'arbre porte alors : 1,0 laisse le droit, 1,02 revalorise de 2 % de plus, 0,98 de 2 %
  de moins. Les années se composent : une passe de l'année Y applique, dans l'ordre, chaque
  coefficient des années jusqu'à Y, si bien qu'un chemin annuel lit le même bouton chaque
  année et porte le niveau qu'ont laissé les années d'avant (D-301). Les pensions de
  retraite ne sont pas des paramètres mais des données de la population : leur coefficient
  multiplie la pension déclarée de la passe de la réforme (`facteur_pensions`), au 1er
  janvier.

La CVEC, elle, est un paramètre (`cvec.montant`, le bouton `cvec_montant`) : l'arbre
d'openfisca ne la porte pas, et `ajouter_cvec` l'ajoute au droit de référence (voir là).
"""

from __future__ import annotations

from typing import Any

import numpy as np
from openfisca_core import periods

from impots.parameters import differs, resolve, update_existing

# --------------------------------------------------------------------------- #
# L'indexation année par année.
# --------------------------------------------------------------------------- #
_MINIMA = ("prestations_sociales", "solidarite_insertion", "minima_sociaux")
_ASPA = ("prestations_sociales", "solidarite_insertion", "minimum_vieillesse", "aspa")

#: Chaque prestation qu'une indexation peut régler : le mois de sa revalorisation légale,
#: et les paramètres qu'elle multiplie. Les chemins ont été lus dans l'arbre, avec leurs
#: dates : le RSA, la prime d'activité, la BMAF et l'AAH au 1er avril (CSS L. 161-25), le
#: minimum vieillesse au 1er janvier, les aides au logement au 1er octobre (CCH L. 823-4).
#: La BMAF porte toutes les prestations familiales qui en sont un multiple (AF, CF, ASF,
#: ARS…). Les pensions de retraite, au 1er janvier, sont des données : aucun chemin.
INDEXATIONS: dict[str, int] = {
    "rsa": 4,
    "prime_activite": 4,
    "prestations_familiales": 4,
    "aah": 4,
    "minimum_vieillesse": 1,
    "aides_logement": 10,
    "pensions": 1,
}

_CHEMINS: dict[str, tuple[tuple[str, ...], ...]] = {
    "rsa": ((*_MINIMA, "rsa", "rsa_m", "montant_de_base_du_rsa"),),
    "prime_activite": ((*_MINIMA, "ppa", "pa_m", "montant_de_base"),),
    "prestations_familiales": (("prestations_sociales", "prestations_familiales", "bmaf",
                                "bmaf"),),
    "aah": (("prestations_sociales", "prestations_etat_de_sante", "invalidite", "aah",
             "montant"),),
    # Le montant maximal et le plafond de ressources, qui valent la même chose et se
    # revalorisent ensemble : n'en bouger qu'un ferait une allocation différentielle qui
    # ne rejoint plus son plafond.
    "minimum_vieillesse": tuple((*_ASPA, node, who)
                                for node in ("montant_maximum_annuel", "plafond_ressources")
                                for who in ("personnes_seules", "couples")),
}

#: Les années qu'un coefficient peut viser : celles qu'un chemin d'étude chiffre.
ANNEES_INDEXATION = (2024, 2040)


def indexation_date(prestation: str, annee: int) -> str:
    return f"{annee}-{INDEXATIONS[prestation]:02d}-01"


def indexation_chemins(prestation: str, annee: int) -> tuple[tuple[str, ...], ...]:
    """Les paramètres que l'indexation d'une prestation multiplie en `annee`."""
    if prestation == "aides_logement":
        from impots.engine.reforms import al_parametres_revises_en_octobre

        return al_parametres_revises_en_octobre(annee + 1)
    return _CHEMINS.get(prestation, ())


def _coefficients(spec: Any, annee: int) -> list[tuple[str, int, float]]:
    """(prestation, année, coefficient) jusqu'à `annee`, dans l'ordre des années."""
    indexations = getattr(spec, "indexations", None) or {}
    return sorted(((p, y, c) for p, par_annee in indexations.items()
                   for y, c in par_annee.items() if y <= annee),
                  key=lambda t: (t[1], INDEXATIONS[t[0]], t[0]))


def _segments(parameters: Any, path: tuple[str, ...], date: str) -> list[str]:
    node = resolve(parameters, path)
    later = sorted({v.instant_str for v in node.values_list if v.instant_str > date})
    return [date, *later]


def appliquer_indexations(parameters: Any, spec: Any, annee: int) -> None:
    """Chaque coefficient des années jusqu'à `annee`, écrit à sa date légale, segment par
    segment, sur ce que l'arbre porte alors : une revalorisation que l'arbre porte plus tard
    est multipliée, pas effacée, et les années se composent dans l'ordre (D-301)."""
    for prestation, y, coefficient in _coefficients(spec, annee):
        date = indexation_date(prestation, y)
        for path in indexation_chemins(prestation, y):
            starts = _segments(parameters, path, date)
            values = [resolve(parameters, path)(start) for start in starts]
            for start, value in zip(starts, values, strict=True):
                if value is not None:
                    update_existing(parameters, path, start=periods.instant(start),
                                    value=float(value) * coefficient, instant=start)


def verifier_indexations(system: Any, spec: Any, annee: int) -> None:
    """Relit chaque paramètre indexé contre l'arbre de RÉFÉRENCE : à chaque date de l'année
    chiffrée, la valeur de référence fois le produit des coefficients déjà tombés ; la veille
    de la première date, la valeur de référence. L'attendu se déduit de la référence et des
    dates légales, jamais du chemin d'écriture."""
    from impots.engine.system import baseline

    reference = baseline().parameters
    coefficients = _coefficients(spec, annee)
    problems: list[str] = []
    for prestation in sorted({p for p, _, _ in coefficients}):
        mine = [(y, c) for p, y, c in coefficients if p == prestation]
        dates = [indexation_date(prestation, y) for y, _ in mine]
        for path in {path for y, _ in mine for path in indexation_chemins(prestation, y)}:
            name = ".".join(path[-3:])
            points = {f"{annee}-{m:02d}-01" for m in range(1, 13)} | {
                d for d in dates if d.startswith(f"{annee}-")}
            for point in sorted(points):
                base = resolve(reference, path)(point)
                if base is None:
                    continue
                factor = 1.0
                for (_, c), d in zip(mine, dates, strict=True):
                    if d <= point:
                        factor *= c
                got = float(resolve(system.parameters, path)(point))
                if differs(got, float(base) * factor):
                    problems.append(f"{prestation} {name} au {point} : demandé "
                                    f"{float(base) * factor}, appliqué {got}")
            before = str(periods.instant(dates[0]).offset(-1, "day"))
            base = resolve(reference, path)(before)
            if base is not None:
                got = float(resolve(system.parameters, path)(before))
                if differs(got, float(base)):
                    problems.append(f"{prestation} {name} écrit avant sa date : {got} au "
                                    f"{before}, au lieu de {float(base)}")
    if problems:
        raise AssertionError("les indexations appliquées ne correspondent pas à la réforme "
                             "demandée — " + " ; ".join(problems))


def facteur_pensions(spec: Any, annee: int) -> float:
    """Le produit des coefficients des pensions jusqu'à `annee` : ce que la passe de la
    réforme multiplie la pension déclarée par. 1 sans indexation des pensions."""
    factor = 1.0
    for prestation, _, coefficient in _coefficients(spec, annee):
        if prestation == "pensions":
            factor *= coefficient
    return factor


# --------------------------------------------------------------------------- #
# La CVEC, ajoutée au droit de référence.
# --------------------------------------------------------------------------- #
#: Le montant de la CVEC par année universitaire, à l'année de sa rentrée (C. éduc. art.
#: L. 841-5 et l'arrêté qui l'indexe chaque année sur les prix) : 100 € en 2023-2024,
#: 103 € en 2024-2025, 105 € en 2025-2026. Celui de 2026-2027 n'est pas dans l'arbre : le
#: droit de 2025 est reconduit, comme le fait openfisca pour tout paramètre au-delà de son
#: dernier relevé.
CVEC_MONTANTS = {"2023-01-01": 100.0, "2024-01-01": 103.0, "2025-01-01": 105.0}
CVEC_PATH = ("cvec", "montant")
CVEC_DEPUIS = "2023-01-01"


def ajouter_cvec(system: Any) -> Any:
    """`system` avec la CVEC : son paramètre, ses deux entrées, son montant, et le revenu
    disponible qui la paie.

    **Ce qu'elle est.** La contribution de vie étudiante et de campus, due chaque année par
    l'étudiant inscrit dans une formation initiale du supérieur, sauf s'il est boursier sur
    critères sociaux (ou réfugié, ou bénéficiaire de la protection subsidiaire). Elle va au
    Crous. openfisca ne la calcule pas.

    **Ce qu'elle lit.** Deux entrées d'un individu, fausses par défaut :
    `etudiant_superieur` et `boursier_superieur`. Ni le format d'entrée ni la population ne
    les portent encore (la population ne distingue ni le supérieur ni les boursiers) : le
    bouton `cvec_montant` ne bouge rien sur un ménage du format d'entrée, et une passe sur
    la population qui le règle est refusée plutôt que chiffrée à zéro. Il se voit bouger sur
    une simulation qui écrit ces deux entrées (`tests/test_boutons_programmes.py`).

    **Où elle sort.** Du revenu disponible du ménage, comme un impôt direct : sa
    suppression rend 105 € à l'étudiant non boursier. Le rayon : nul aujourd'hui, personne
    ne déclarant d'étudiant du supérieur."""
    from openfisca_core.model_api import YEAR, Variable
    from openfisca_core.parameters import ParameterNode
    from openfisca_core.reforms import Reform
    from openfisca_france.entities import Individu, Menage

    base_rd = system.variables["revenu_disponible"]

    class etudiant_superieur(Variable):
        value_type = bool
        entity = Individu
        label = "Inscrit dans une formation initiale de l'enseignement supérieur"
        definition_period = YEAR

    class boursier_superieur(Variable):
        value_type = bool
        entity = Individu
        label = "Boursier sur critères sociaux de l'enseignement supérieur"
        definition_period = YEAR

    class cvec(Variable):
        value_type = float
        entity = Individu
        label = "Contribution de vie étudiante et de campus (C. éduc. art. L. 841-5)"
        reference = "https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000037388611"
        definition_period = YEAR

        def formula_2023_01_01(individu, period, parameters):
            montant = parameters(period.start).cvec.montant
            due = individu("etudiant_superieur", period) & ~individu(
                "boursier_superieur", period)
            return due * montant

    class revenu_disponible(Variable):  # openfisca's naming
        value_type = float
        entity = Menage
        label = "Revenu disponible du ménage, la CVEC payée"
        reference = base_rd.reference
        definition_period = YEAR

        def formula(menage, period, parameters):
            avant = base_rd.get_formula(period.start)(menage, period, parameters)
            return avant - menage.sum(menage.members("cvec", period))

    def parametres(parameters: Any) -> Any:
        parameters.add_child("cvec", ParameterNode("cvec", data={
            "description": "Contribution de vie étudiante et de campus",
            "montant": {"description": "Montant annuel par étudiant non boursier",
                        "unit": "currency", "values": dict(CVEC_MONTANTS)}}))
        return parameters

    class Cvec(Reform):
        name = "impots-cvec"

        def apply(self) -> None:
            self.modify_parameters(modifier_function=parametres)
            for variable in (etudiant_superieur, boursier_superieur, cvec):
                self.add_variable(variable)
            self.update_variable(revenu_disponible)

    return Cvec(system)


# --------------------------------------------------------------------------- #
# Les boutons qui changent une formule.
# --------------------------------------------------------------------------- #
#: Les champs de `ReformSpec` qu'applique `appliquer_formules`, chacun avec le ou les champs
#: qui vont avec lui.
FORMULE_KNOBS: dict[str, tuple[str, ...]] = {
    "pfu_supprime": (),
    "ir_exoneration_jeunes_age": ("ir_exoneration_jeunes_plafond_smic",),
    "ir_exoneration_jeunes_plafond_smic": ("ir_exoneration_jeunes_age",),
    "reduction_impot_familles_montant": ("reduction_impot_familles_enfants_min",),
    "reduction_impot_familles_enfants_min": ("reduction_impot_familles_montant",),
    "indexations": (),
}

#: Les étiquettes que relit `verifier_formules` : une formule remplacée se reconnaît à la
#: sienne, et une réforme qui ne l'aurait pas posée est refusée.
ETIQUETTE_JEUNES = "exonération des salaires des jeunes (but 21)"
ETIQUETTE_FAMILLES = "réduction d'impôt des familles (but 21)"


def smic_brut_annuel(parameters: Any, period: Any) -> float:
    """Le SMIC brut de janvier, sur un an : horaire × heures mensuelles × 12."""
    smic = parameters(period.first_month).marche_travail.salaire_minimum.smic
    return float(smic.smic_b_horaire) * float(smic.nb_heures_travail_mensuel) * 12.0


def _exoneration_jeunes(tspr: Any, deduction: Any, age_max: int, plafond_smic: float) -> Any:
    from openfisca_core.model_api import ADD, YEAR, Variable
    from openfisca_france.entities import FoyerFiscal

    from impots.engine.corrections import EXEMPT_SALARY_SHARE, _SalariesLessTheExemptShare

    class revenu_categoriel_tspr(Variable):  # openfisca's naming
        value_type = float
        entity = FoyerFiscal
        label = f"Revenu catégoriel des traitements et salaires, {ETIQUETTE_JEUNES}"
        definition_period = YEAR

        def formula(foyer_fiscal, period, parameters):
            montant = tspr(foyer_fiscal, period, parameters)
            individus = foyer_fiscal.members
            jeune = individus("age", period.first_month) < age_max
            if not jeune.any():
                return montant
            imposable = individus("salaire_imposable", period, options=[ADD])
            share = individus(EXEMPT_SALARY_SHARE, period)
            # Ce que la correction 24 exonère déjà, puis ce que l'âge exonère du reste.
            deja = share * imposable
            brut = individus("salaire_de_base", period, options=[ADD])
            plafond = plafond_smic * smic_brut_annuel(parameters, period)
            ratio = np.where(brut > plafond, plafond / np.maximum(brut, 1.0), 1.0)
            exonere = jeune * ratio * (imposable - deja)
            avec = deduction(period)(_SalariesLessTheExemptShare(individus, -(deja + exonere)),
                                     period, parameters)
            sans = deduction(period)(_SalariesLessTheExemptShare(individus, -deja), period,
                                     parameters)
            return montant + foyer_fiscal.sum(avec - sans)

    return revenu_categoriel_tspr


def _reduction_familles(avant_formule: Any, montant: float, enfants_min: int) -> Any:
    from openfisca_core.model_api import ADD, YEAR, Variable
    from openfisca_france.entities import FoyerFiscal

    class reductions(Variable):  # openfisca's naming
        value_type = float
        entity = FoyerFiscal
        label = f"Réductions d'impôt, la {ETIQUETTE_FAMILLES} comprise"
        definition_period = YEAR

        def formula(foyer_fiscal, period, parameters):
            avant = avant_formule(foyer_fiscal, period, parameters)
            individus = foyer_fiscal.members
            activite = (individus("salaire_imposable", period, options=[ADD])
                        + individus("rpns_imposables", period))
            actif = foyer_fiscal.any(activite > 0, role=FoyerFiscal.DECLARANT)
            famille = foyer_fiscal("nb_pac", period) >= enfants_min
            ip_net = foyer_fiscal("ip_net", period)
            return np.minimum(ip_net, avant + actif * famille * montant)

    return reductions


def appliquer_formules(reform: Any, spec: Any, annee: int) -> None:
    """Les boutons de formule que `spec` règle, posés sur la réforme qui s'applique."""
    from openfisca_core.model_api import YEAR, Variable
    from openfisca_france.entities import FoyerFiscal

    if spec.pfu_supprime:
        class f2op(Variable):
            value_type = bool
            entity = FoyerFiscal
            label = "Option pour le barème, imposée à tous : le PFU supprimé (but 21)"
            definition_period = YEAR
            default_value = True
            cerfa_field = "2OP"

        reform.update_variable(f2op)
    if spec.ir_exoneration_jeunes_age is not None:
        from impots.engine.corrections import SALARIES_AFTER_DEDUCTION, SALARY_CATEGORY

        tspr = reform.get_variable(SALARY_CATEGORY).get_formula(f"{annee}-01-01")
        deduction = reform.get_variable(SALARIES_AFTER_DEDUCTION).get_formula
        variable = _exoneration_jeunes(tspr, deduction, spec.ir_exoneration_jeunes_age,
                                       spec.ir_exoneration_jeunes_plafond_smic)
        reform.update_variable(variable)
    if spec.reduction_impot_familles_montant is not None:
        avant = reform.get_variable("reductions").get_formula(f"{annee}-01-01")
        reform.update_variable(_reduction_familles(
            avant, spec.reduction_impot_familles_montant,
            spec.reduction_impot_familles_enfants_min))


def verifier_formules(system: Any, spec: Any, annee: int) -> None:
    """Relit chaque formule remplacée sur le système réformé, et refuse celui qui ne
    l'aurait pas posée : un bouton qui écrit sans que la formule de l'année le lise est
    le défaut que ce dépôt a rencontré quatre fois (D-044, D-062, D-064, D-071)."""
    problems = []
    if spec.pfu_supprime and system.variables["f2op"].default_value is not True:
        problems.append("pfu_supprime : la case 2OP n'est pas cochée par défaut")
    if spec.pfu_supprime is False and system.variables["f2op"].default_value is not False:
        problems.append("pfu_supprime=False : la case 2OP est cochée par défaut")
    checks = (("ir_exoneration_jeunes_age", "revenu_categoriel_tspr", ETIQUETTE_JEUNES),
              ("reduction_impot_familles_montant", "reductions", ETIQUETTE_FAMILLES))
    for knob, name, label in checks:
        if getattr(spec, knob) is not None and label not in system.variables[name].label:
            problems.append(f"{knob} : la formule de {name} n'est pas la sienne")
    if problems:
        raise AssertionError("les boutons de formule appliqués ne correspondent pas à la "
                             "réforme demandée — " + " ; ".join(problems))

