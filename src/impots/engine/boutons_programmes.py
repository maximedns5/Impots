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

LES BOUTONS QUI LISENT LES DONNÉES DE MÉNAGES IMPUTÉES (but 21, étape 4, suite). Chacun lit
une entrée que `ajouter_donnees_menages` ajoute au droit, nulle pour qui ne la porte pas, et
que la population écrit quand elle impute les données de ménages (`population.menages`) :
une passe qui en règle un les impute (`imputations.MENAGES_KNOBS`). Aucun ne bouge rien à
`None`, la loi.

* **Les pensions alimentaires perçues défiscalisées** (`pensions_alimentaires_exonerees`,
  `pensions_alimentaires_plafond_par_enfant`). La pension que le parent perçoit sort de
  ses revenus imposés comme des pensions (cases 1AO à 1DO), entière ou jusqu'au plafond par
  personne à charge de son foyer. L'impôt, le revenu fiscal de référence et ce qui le lit
  bougent ; les prestations qui comptent la pension dans leurs ressources (RSA, prime,
  aides au logement, ASF) ne bougent pas : la mesure est fiscale. Hypothèse : toute
  pension perçue l'est pour un enfant (l'imputation la donne aux parents isolés).
* **La réduction d'impôt sur les intérêts d'emprunt de la résidence principale**
  (`interets_emprunt_taux`, `interets_emprunt_plafond`,
  `interets_emprunt_plafond_par_enfant`). Le foyer déduit de son impôt le taux de ses
  intérêts qui correspond à son nombre d'enfants mineurs à charge (le dernier taux de la
  liste au-delà), dans la limite d'un plafond, plus un montant par enfant mineur. Le
  plafond borne la réduction, pas les intérêts (hypothèse de traduction). Une réduction,
  qui s'arrête à l'impôt, hors du plafond global des niches. Les intérêts sont ceux que
  l'imputation donne à la personne de référence d'un ménage accédant ; la population ne
  porte ni la date du prêt ni sa durée : une limite de durée n'est pas lue.
* **Le crédit d'impôt sur les frais de trajet domicile-travail** (`credit_trajets_taux`,
  `credit_trajets_franchise`, `credit_trajets_plafond`). Par personne : le taux des frais
  de trajet au-delà de la franchise, dans la limite du plafond ; un crédit, versé à qui
  n'a pas d'impôt. Les frais sont ceux de l'imputation, pour tous les salariés (au-delà de
  ceux qui déclarent leurs frais réels, l'extrapolation d'une loi calée sur eux) ; la
  déduction des frais réels n'est pas touchée.
* **L'exonération des heures supplémentaires** (`heures_sup_exoneration_salariale`,
  `heures_sup_exoneration_csg_crds`, `heures_sup_exoneration_patronale`,
  `heures_sup_franchise_heures`, `heures_sup_plafond_heures`). Sur la rémunération des
  heures imputées, au-delà des premières (la franchise) et dans la limite d'un nombre
  d'heures par an, la part dite des cotisations salariales que la loi laisse (la loi en
  ôte déjà jusqu'à 11,31 % du brut, CSS art. L. 241-17 et D. 241-21 : openfisca ne porte
  pas cette réduction, et l'exonération n'enlève que ce qui la dépasse), de la CSG et de la
  CRDS, et des cotisations patronales nettes des allègements, celles-ci dans le privé
  seulement (un employeur public les verse à l'État). Uniformément sur les mois de l'année.
  Le net imposable que les heures gagnent reste exonéré d'impôt, comme la loi exonère
  celui des heures (dans la limite de 7 500 €, que le bouton ne relit pas). La déduction
  forfaitaire patronale de la loi (0,50 € ou 1,50 € l'heure selon l'effectif) n'est pas
  portée : la population ne dit pas la taille de l'entreprise. Des heures neuves, un
  seuil annuel de durée ou son annualisation ne se portent pas sur des heures imputées.
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
    `etudiant_superieur` et `boursier_superieur`. Le format d'entrée ne les porte pas : le
    bouton `cvec_montant` ne bouge rien sur un ménage du format d'entrée. La population les
    porte quand elle impute les données de ménages (`population.menages`, les étudiants et
    les boursiers calés sur le SIES), ce qu'une passe qui règle le bouton demande
    (`MENAGES_KNOBS`). Elle est alors payée dans la passe de référence aussi.

    **Où elle sort.** Du revenu disponible du ménage, comme un impôt direct : sa
    suppression rend 105 € à l'étudiant non boursier. Le garde des secteurs la compte parmi
    les prélèvements (`guards.STATE_RECEIPTS`) ; elle va au Crous, pas à l'État, comme la
    réduction de loyer de solidarité va au bailleur (D-374) : un biais du coût, dit."""
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
# Les données de ménages, ajoutées au droit de référence comme des entrées.
# --------------------------------------------------------------------------- #
#: Les entrées individuelles et annuelles que `population.menages` écrit et que seuls les
#: boutons de l'étape 4 lisent : (nom, libellé).
ENTREES_MENAGES: tuple[tuple[str, str], ...] = (
    ("heures_sup_brut", "Rémunération brute des heures supplémentaires de l'année"),
    ("heures_sup_nombre", "Heures supplémentaires de l'année"),
    ("frais_trajet_domicile_travail", "Frais de trajet domicile-travail de l'année"),
    ("interets_emprunt_residence_principale",
     "Intérêts de l'emprunt de la résidence principale payés dans l'année"),
)


def ajouter_donnees_menages(system: Any) -> Any:
    """`system` avec les entrées de `ENTREES_MENAGES`, nulles par défaut. Aucune formule du
    droit ne les lit : elles ne bougent rien tant qu'un bouton ne les lit pas."""
    from openfisca_core.model_api import YEAR, Variable
    from openfisca_core.reforms import Reform
    from openfisca_france.entities import Individu

    variables = []
    for nom, libelle in ENTREES_MENAGES:
        variables.append(type(nom, (Variable,), {
            "value_type": float, "entity": Individu, "label": libelle,
            "definition_period": YEAR, "__module__": __name__}))

    class DonneesMenages(Reform):
        name = "impots-donnees-menages"

        def apply(self) -> None:
            for variable in variables:
                self.add_variable(variable)

    return DonneesMenages(system)


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
    "pensions_alimentaires_exonerees": (),
    "pensions_alimentaires_plafond_par_enfant": ("pensions_alimentaires_exonerees",),
    "interets_emprunt_taux": (),
    "interets_emprunt_plafond": ("interets_emprunt_taux",),
    "interets_emprunt_plafond_par_enfant": ("interets_emprunt_taux",
                                            "interets_emprunt_plafond"),
    "credit_trajets_taux": (),
    "credit_trajets_franchise": ("credit_trajets_taux",),
    "credit_trajets_plafond": ("credit_trajets_taux",),
    "heures_sup_exoneration_salariale": (),
    "heures_sup_exoneration_csg_crds": (),
    "heures_sup_exoneration_patronale": (),
    "heures_sup_franchise_heures": (),
    "heures_sup_plafond_heures": (),
}
#: Les boutons des heures supplémentaires : les trois taux, et ce qui borne les heures.
HEURES_SUP_TAUX = ("heures_sup_exoneration_salariale", "heures_sup_exoneration_csg_crds",
                   "heures_sup_exoneration_patronale")
HEURES_SUP_BORNES = ("heures_sup_franchise_heures", "heures_sup_plafond_heures")
#: Les boutons qui lisent les données de ménages imputées (`population.menages`).
MENAGES_KNOBS = frozenset({
    "pensions_alimentaires_exonerees", "pensions_alimentaires_plafond_par_enfant",
    "interets_emprunt_taux", "interets_emprunt_plafond",
    "interets_emprunt_plafond_par_enfant", "credit_trajets_taux",
    "credit_trajets_franchise", "credit_trajets_plafond", *HEURES_SUP_TAUX,
    *HEURES_SUP_BORNES, "cvec_montant"})
#: La part du brut des heures supplémentaires dont la loi réduit déjà les cotisations
#: salariales d'assurance vieillesse (CSS art. D. 241-21) ; openfisca ne la porte pas.
TAUX_REDUCTION_HEURES_SUP_LOI = 0.1131

#: Les étiquettes que relit `verifier_formules` : une formule remplacée se reconnaît à la
#: sienne, et une réforme qui ne l'aurait pas posée est refusée.
ETIQUETTE_JEUNES = "exonération des salaires des jeunes (but 21)"
ETIQUETTE_FAMILLES = "réduction d'impôt des familles (but 21)"
ETIQUETTE_PENSIONS = "pensions alimentaires perçues défiscalisées (but 21)"
ETIQUETTE_INTERETS = "réduction des intérêts d'emprunt (but 21)"
ETIQUETTE_TRAJETS = "crédit des frais de trajet (but 21)"
ETIQUETTE_HEURES_SUP = "heures supplémentaires exonérées (but 21)"


def smic_brut_annuel(parameters: Any, period: Any) -> float:
    """Le SMIC brut de janvier, sur un an : horaire × heures mensuelles × 12."""
    smic = parameters(period.first_month).marche_travail.salaire_minimum.smic
    return float(smic.smic_b_horaire) * float(smic.nb_heures_travail_mensuel) * 12.0


def _exoneration_jeunes(tspr: Any, deduction: Any, age_max: int, plafond_smic: float,
                        annee: int) -> Any:
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
            # The reform starts the year it prices (D-385): the revenus of the years before,
            # which the RFR of N-2 reads for the CSG rate of a pension or of an unemployment
            # benefit, stay those of the law.
            if period.start.year < annee:
                return montant
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


def _reduction_familles(avant_formule: Any, montant: float, enfants_min: int,
                        annee: int) -> Any:
    from openfisca_core.model_api import ADD, YEAR, Variable
    from openfisca_france.entities import FoyerFiscal

    class reductions(Variable):  # openfisca's naming
        value_type = float
        entity = FoyerFiscal
        label = f"Réductions d'impôt, la {ETIQUETTE_FAMILLES} comprise"
        definition_period = YEAR

        def formula(foyer_fiscal, period, parameters):
            avant = avant_formule(foyer_fiscal, period, parameters)
            if period.start.year < annee:  # the reform starts the year it prices (D-385)
                return avant
            individus = foyer_fiscal.members
            activite = (individus("salaire_imposable", period, options=[ADD])
                        + individus("rpns_imposables", period))
            actif = foyer_fiscal.any(activite > 0, role=FoyerFiscal.DECLARANT)
            famille = foyer_fiscal("nb_pac", period) >= enfants_min
            ip_net = foyer_fiscal("ip_net", period)
            return np.minimum(ip_net, avant + actif * famille * montant)

    return reductions


def _datee(reform: Any, classe: Any, annee: int) -> Any:
    """La variable `classe`, dont la formule ne vaut qu'à partir du 1er janvier de `annee` :
    avant, celles du droit. Le premier jour, une réforme ne change pas les revenus des années
    d'avant, que lisent le revenu fiscal de référence de N-2 (le taux de CSG d'une pension,
    l'ARS) et les ressources des aides : sans date, une défiscalisation y aurait baissé la CSG
    des retraités d'un foyer qui perçoit une pension alimentaire."""
    from openfisca_core.model_api import Variable

    ancienne = reform.get_variable(classe.__name__)
    debut = f"{annee}-01-01"
    attrs = {"value_type": classe.value_type, "entity": classe.entity,
             "label": classe.label, "definition_period": classe.definition_period,
             "__module__": __name__}
    if ancienne.set_input is not None:
        attrs["set_input"] = ancienne.set_input
    for date, formule in ancienne.formulas.items():
        if date < debut:
            nom = "formula" if date == "0001-01-01" else f"formula_{date.replace('-', '_')}"
            attrs[nom] = formule
    attrs[f"formula_{debut.replace('-', '_')}"] = classe.formula
    return type(classe.__name__, (Variable,), attrs)


def _appel(formule: Any, entite: Any, period: Any, parameters: Any) -> Any:
    """Une formule d'openfisca, qu'elle lise les paramètres ou non."""
    import inspect

    if len(inspect.signature(formule).parameters) == 2:
        return formule(entite, period)
    return formule(entite, period, parameters)


def _pensions_exonerees(avant_formule: Any, plafond_par_enfant: float | None) -> Any:
    from openfisca_core.model_api import ADD, YEAR, Variable
    from openfisca_france.entities import Individu

    class revenu_assimile_pension(Variable):  # openfisca's naming
        value_type = float
        entity = Individu
        label = f"Revenus imposés comme des pensions, {ETIQUETTE_PENSIONS}"
        definition_period = YEAR

        def formula(individu, period, parameters):
            avant = _appel(avant_formule, individu, period, parameters)
            percue = (individu("pensions_alimentaires_percues", period, options=[ADD])
                      * individu("pensions_alimentaires_percues_decl", period))
            if plafond_par_enfant is None:
                return avant - percue
            enfants = individu.foyer_fiscal("nb_pac", period)
            return avant - np.minimum(percue, plafond_par_enfant * enfants)

    return revenu_assimile_pension


def _enfants_mineurs(foyer_fiscal: Any, period: Any) -> Any:
    from openfisca_france.entities import FoyerFiscal

    mineur = foyer_fiscal.members("age", period.first_month) < 18
    return foyer_fiscal.sum(mineur, role=FoyerFiscal.PERSONNE_A_CHARGE)


def _reduction_interets(avant_formule: Any, taux: tuple[float, ...], plafond: float | None,
                        par_enfant: float, label_avant: str) -> Any:
    from openfisca_core.model_api import YEAR, Variable
    from openfisca_france.entities import FoyerFiscal

    class reductions(Variable):  # openfisca's naming
        value_type = float
        entity = FoyerFiscal
        label = f"{label_avant} ; la {ETIQUETTE_INTERETS} comprise"
        definition_period = YEAR

        def formula(foyer_fiscal, period, parameters):
            avant = _appel(avant_formule, foyer_fiscal, period, parameters)
            interets = foyer_fiscal.sum(foyer_fiscal.members(
                "interets_emprunt_residence_principale", period))
            enfants = _enfants_mineurs(foyer_fiscal, period)
            rang = np.minimum(enfants, len(taux) - 1).astype(int)
            reduction = np.asarray(taux)[rang] * interets
            if plafond is not None:
                reduction = np.minimum(reduction, plafond + par_enfant * enfants)
            return np.minimum(foyer_fiscal("ip_net", period), avant + reduction)

    return reductions


def _credit_trajets(avant_formule: Any, taux: float, franchise: float,
                    plafond: float | None) -> Any:
    from openfisca_core.model_api import YEAR, Variable
    from openfisca_france.entities import FoyerFiscal

    class credits_impot(Variable):  # openfisca's naming
        value_type = float
        entity = FoyerFiscal
        label = f"Crédits d'impôt, le {ETIQUETTE_TRAJETS} compris"
        definition_period = YEAR

        def formula(foyer_fiscal, period, parameters):
            avant = _appel(avant_formule, foyer_fiscal, period, parameters)
            frais = foyer_fiscal.members("frais_trajet_domicile_travail", period)
            credit = taux * np.maximum(frais - franchise, 0.0)
            if plafond is not None:
                credit = np.minimum(credit, plafond)
            return avant + foyer_fiscal.sum(credit)

    return credits_impot


#: Les salaires bruts que l'exonération rapporte les heures à : ceux de la ligne
#: `salaire_brut` du registre (le traitement et les primes d'un titulaire, D-346).
_BRUTS = ("salaire_de_base", "remuneration_principale", "primes_fonction_publique")


def _part_heures_sup(individu: Any, period: Any, franchise: float,
                     plafond: float | None) -> Any:
    """La part du salaire brut de l'année que portent les heures exonérées : celles au-delà
    de la franchise, dans la limite du plafond, à leur rémunération moyenne."""
    from openfisca_core.model_api import ADD

    annee = period.this_year
    heures = individu("heures_sup_nombre", annee)
    brut_hs = individu("heures_sup_brut", annee)
    exonerees = np.maximum(heures - franchise, 0.0)
    if plafond is not None:
        exonerees = np.minimum(exonerees, plafond)
    eligible = np.where(heures > 0, brut_hs * exonerees / np.maximum(heures, 1e-9), 0.0)
    brut = sum(individu(name, annee, options=[ADD]) for name in _BRUTS)
    return np.where(brut > 0, np.minimum(eligible / np.maximum(brut, 1e-9), 1.0), 0.0)


def _heures_sup(reform: Any, spec: Any, annee: int) -> None:
    """Les variables mensuelles que l'exonération des heures supplémentaires réécrit, et le
    revenu catégoriel qui garde exonéré ce qu'elles ajoutent au net imposable."""
    from openfisca_core.model_api import ADD, MONTH, YEAR, Variable
    from openfisca_france.entities import FoyerFiscal, Individu

    from impots.engine.corrections import (
        EXEMPT_SALARY_SHARE,
        SALARIES_AFTER_DEDUCTION,
        SALARY_CATEGORY,
        _SalariesLessTheExemptShare,
    )

    salariale = spec.heures_sup_exoneration_salariale or 0.0
    csg = spec.heures_sup_exoneration_csg_crds or 0.0
    patronale = spec.heures_sup_exoneration_patronale or 0.0
    franchise = spec.heures_sup_franchise_heures or 0.0
    plafond = spec.heures_sup_plafond_heures
    debut = f"{annee}-01-01"

    def part(individu, period):
        return _part_heures_sup(individu, period, franchise, plafond)

    def brut_du_mois(individu, period):
        return sum(individu(name, period) for name in _BRUTS)

    def gain_salarial(cotisations_formula, individu, period, parameters):
        avant = _appel(cotisations_formula, individu, period, parameters)
        reste = np.maximum(-avant - TAUX_REDUCTION_HEURES_SUP_LOI * brut_du_mois(
            individu, period), 0.0)
        return salariale * part(individu, period) * reste

    def mensuelle(nom, avant_formule, ecrire):
        return _datee(reform, type(nom, (Variable,), {
            "value_type": float, "entity": Individu, "definition_period": MONTH,
            "label": f"{reform.get_variable(nom).label}, {ETIQUETTE_HEURES_SUP}",
            "formula": lambda individu, period, parameters: ecrire(
                avant_formule, individu, period, parameters),
            "__module__": __name__}), annee)

    variables = []
    cotisations = reform.get_variable("cotisations_salariales").get_formula(debut)
    if salariale:
        variables.append(mensuelle(
            "cotisations_salariales", cotisations,
            lambda f, i, p, params: _appel(f, i, p, params) + gain_salarial(f, i, p, params)))
    csg_deductible = reform.get_variable("csg_deductible_salaire").get_formula(debut)
    if csg:
        for nom in ("csg_deductible_salaire", "csg_imposable_salaire", "crds_salaire"):
            variables.append(mensuelle(
                nom, reform.get_variable(nom).get_formula(debut),
                lambda f, i, p, params: _appel(f, i, p, params) * (1.0 - csg * part(i, p))))
    if patronale:
        from openfisca_france.model.revenus.activite.salarie import TypesCategorieSalarie

        def moins_patronal(f, i, p, params):
            avant = _appel(f, i, p, params)
            categorie = i("categorie_salarie", p)
            prive = ((categorie == TypesCategorieSalarie.prive_non_cadre)
                     | (categorie == TypesCategorieSalarie.prive_cadre))
            employeur = np.maximum(avant - brut_du_mois(i, p), 0.0)
            return avant - prive * patronale * part(i, p) * employeur

        variables.append(mensuelle(
            "salaire_super_brut", reform.get_variable("salaire_super_brut").get_formula(debut),
            moins_patronal))

    class heures_sup_net_imposable_exonere(Variable):
        value_type = float
        entity = Individu
        label = f"Le net imposable que gagnent les {ETIQUETTE_HEURES_SUP}"
        definition_period = YEAR

        def formula(individu, period, parameters):
            total = 0.0
            for mois in period.get_subperiods(MONTH):
                gain = (gain_salarial(cotisations, individu, mois, parameters)
                        if salariale else 0.0)
                if csg:
                    gain = gain - csg * part(individu, mois) * _appel(
                        csg_deductible, individu, mois, parameters)
                total = total + gain
            return total

    tspr = reform.get_variable(SALARY_CATEGORY).get_formula(debut)
    label_avant = reform.get_variable(SALARY_CATEGORY).label
    deduction = reform.get_variable(SALARIES_AFTER_DEDUCTION).get_formula

    class revenu_categoriel_tspr(Variable):  # openfisca's naming
        value_type = float
        entity = FoyerFiscal
        label = f"{label_avant} ; {ETIQUETTE_HEURES_SUP}"
        definition_period = YEAR

        def formula(foyer_fiscal, period, parameters):
            montant = tspr(foyer_fiscal, period, parameters)
            individus = foyer_fiscal.members
            gain = individus("heures_sup_net_imposable_exonere", period)
            if not (gain > 0).any():
                return montant
            imposable = individus("salaire_imposable", period, options=[ADD])
            share = individus(EXEMPT_SALARY_SHARE, period)
            # La correction 24 exonère sa part du net imposable relevé ; ce que les heures
            # gagnent l'est en entier : la part n'en prend que le reste.
            deja = share * imposable
            exonere = deja + (1.0 - share) * gain
            avec = deduction(period)(_SalariesLessTheExemptShare(individus, -exonere),
                                     period, parameters)
            sans = deduction(period)(_SalariesLessTheExemptShare(individus, -deja), period,
                                     parameters)
            return montant + foyer_fiscal.sum(avec - sans)

    for variable in variables:
        reform.update_variable(variable)
    reform.add_variable(heures_sup_net_imposable_exonere)
    reform.update_variable(_datee(reform, revenu_categoriel_tspr, annee))


def _plus_values_au_bareme(formule: Any) -> Any:
    """Les plus-values du revenu disponible, que la case 2OP ne fait pas disparaître.

    OpenFisca lit le capital du revenu disponible sur les plus-values « hors RNI » du RFR ;
    au barème, 3VG, 3UA, 3TJ et 3VT entrent dans le RNI et sortent de cette liste, et donc
    du revenu du ménage, qui les a pourtant touchées. Sur la population, la suppression du
    PFU faisait perdre aux ménages 19,4 Md€ qu'aucun impôt ne prenait (D-389). On les rend,
    pour les foyers au barème seulement : au PFU, rien ne change."""
    from numpy import where
    from openfisca_core.model_api import YEAR, Variable
    from openfisca_france.entities import FoyerFiscal

    class plus_values_base_large(Variable):
        value_type = float
        entity = FoyerFiscal
        label = "Plus-values du revenu disponible, au barème comme au PFU (but 21, D-389)"
        definition_period = YEAR

        def formula(foyer_fiscal, period, parameters):
            f = formule(period)
            # Les formules d'OpenFisca prennent `parameters` ou non, selon l'année.
            avant = (f(foyer_fiscal, period, parameters)
                     if f.__code__.co_argcount == 3 else f(foyer_fiscal, period))
            rendues = sum(foyer_fiscal(case, period)
                          for case in ("f3vg", "f3ua", "f3tj", "f3vt"))
            return avant + where(foyer_fiscal("f2op", period), rendues, 0)

    return plus_values_base_large


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
        reform.update_variable(_plus_values_au_bareme(
            reform.get_variable("plus_values_base_large").get_formula))
    if spec.ir_exoneration_jeunes_age is not None:
        from impots.engine.corrections import SALARIES_AFTER_DEDUCTION, SALARY_CATEGORY

        tspr = reform.get_variable(SALARY_CATEGORY).get_formula(f"{annee}-01-01")
        deduction = reform.get_variable(SALARIES_AFTER_DEDUCTION).get_formula
        variable = _exoneration_jeunes(tspr, deduction, spec.ir_exoneration_jeunes_age,
                                       spec.ir_exoneration_jeunes_plafond_smic, annee)
        reform.update_variable(variable)
    if spec.reduction_impot_familles_montant is not None:
        avant = reform.get_variable("reductions").get_formula(f"{annee}-01-01")
        reform.update_variable(_reduction_familles(
            avant, spec.reduction_impot_familles_montant,
            spec.reduction_impot_familles_enfants_min, annee))
    # Les boutons des données de ménages : leurs formules datées de l'année chiffrée.
    if spec.pensions_alimentaires_exonerees:
        avant = reform.get_variable("revenu_assimile_pension").get_formula(f"{annee}-01-01")
        reform.update_variable(_datee(reform, _pensions_exonerees(
            avant, spec.pensions_alimentaires_plafond_par_enfant), annee))
    if spec.interets_emprunt_taux is not None:
        avant = reform.get_variable("reductions").get_formula(f"{annee}-01-01")
        reform.update_variable(_datee(reform, _reduction_interets(
            avant, tuple(spec.interets_emprunt_taux), spec.interets_emprunt_plafond,
            spec.interets_emprunt_plafond_par_enfant or 0.0,
            reform.get_variable("reductions").label), annee))
    if spec.credit_trajets_taux is not None:
        avant = reform.get_variable("credits_impot").get_formula(f"{annee}-01-01")
        reform.update_variable(_datee(reform, _credit_trajets(
            avant, spec.credit_trajets_taux, spec.credit_trajets_franchise or 0.0,
            spec.credit_trajets_plafond), annee))
    if any(getattr(spec, knob) for knob in HEURES_SUP_TAUX):
        _heures_sup(reform, spec, annee)


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
              ("reduction_impot_familles_montant", "reductions", ETIQUETTE_FAMILLES),
              ("interets_emprunt_taux", "reductions", ETIQUETTE_INTERETS),
              ("credit_trajets_taux", "credits_impot", ETIQUETTE_TRAJETS))
    for knob, name, label in checks:
        if getattr(spec, knob) is not None and label not in system.variables[name].label:
            problems.append(f"{knob} : la formule de {name} n'est pas la sienne")
    if (spec.pensions_alimentaires_exonerees and ETIQUETTE_PENSIONS
            not in system.variables["revenu_assimile_pension"].label):
        problems.append("pensions_alimentaires_exonerees : la formule de "
                        "revenu_assimile_pension n'est pas la sienne")
    if any(getattr(spec, knob) for knob in HEURES_SUP_TAUX) and (
            ETIQUETTE_HEURES_SUP not in system.variables["revenu_categoriel_tspr"].label):
        problems.append("heures supplémentaires : la formule de revenu_categoriel_tspr "
                        "n'est pas la sienne")
    if problems:
        raise AssertionError("les boutons de formule appliqués ne correspondent pas à la "
                             "réforme demandée — " + " ; ".join(problems))

