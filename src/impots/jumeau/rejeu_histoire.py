"""Le jumeau rejoue l'histoire de la France (but 23, lot 6) : ce qui y entre, les fenêtres,
les cibles et leurs tolérances, préenregistrés dans D-417 avant tout calcul.

LA RÉVISION « rejeu_histoire_r2 » (D-421, `CAS`). Le premier juge (D-420) a tourné sur
fe9434f, qui seul le refait. Les fenêtres, les cibles, les tolérances, les θ estimés et
les deux naïfs ne changent pas ; ce qui change, après le diagnostic de D-421 :

* les cotisations des employeurs et des salariés lisent chacune leur ligne, D611 et
  D613CE du compte des APU (t. 7.301), au lieu de se partager à parts égales la ligne
  des cotisations effectives de la t. 3.217 ; les cotisations des non-salariés n'entrent
  dans aucune famille (aucun instrument de la base) ;
* le CICE est un instrument à part (`cice`) : ses mesures datent la seule ligne des
  subventions, plus celle des cotisations patronales ;
* une mesure étalée compte chaque année où le droit change (`MesureVotee.annees_effet`) ;
* la demande mondiale adressée à la France (OCDE) entre au commerce, en écart à sa
  propre tendance de l'estimation (`ecarts_demande_mondiale`) ;
* (l'amendement) la variation d'une année votée ne compte que dans le sens de la loi
  (`variation_comptee`, `MesureVotee.sens`) ; le jumeau est celui de la jonction D-422
  (l'emploi public de D-418 compris).

AUCUN MONTANT OFFICIEL DE MESURE N'ENTRE (D-359 à D-361). Les évaluations préalables des
PLF et des PLFSS sont des juges mis de côté ; la base des mesures votées ne porte que le
droit (`jumeau.votees`). Ce qui entre est LU DANS LES COMPTES PUBLIÉS, et la base des
mesures votées ne sert qu'à DATER et à ATTRIBUER.

LES CHOCS BUDGÉTAIRES OBSERVÉS (`chocs_observes`), pour une fenêtre partie de l'année s,
chaque année t rejouée, Y_t le PIB de la référence (la tendance, `Tendance.chemin`) :

* les recettes, par famille F d'impôts de la t. 3.217 (`FAMILLES`) : le taux apparent
  τ_u = Σ_{l ∈ F} s_l T_{l,u} / B_u, T_l la ligne publiée, s_l son signe (un crédit d'impôt
  compte en moins), B la base de la famille (la consommation des ménages pour la TVA et
  la TICPE, l'EBE et le revenu mixte pour l'IS, les rémunérations pour les cotisations
  et le CICE, le PIB pour le reste). Seules comptent les années u où la base
  des mesures votées porte une mesure d'un instrument de la famille, d'effet en u (hors
  les mesures censurées ou abrogées avant leur effet) ; une variation du taux apparent
  une autre année est tenue pour non discrétionnaire et n'entre pas :

      ΔT_{F,t} = Σ_{s < u ≤ t} w_{F,u} (τ_u − τ_{u−1}) · (B_s / PIB_s) · Y_t

  w_{F,u} vaut 1 quand un instrument de F a une année d'effet en u, 0 sinon (D-417 ; les
  années d'effet d'une mesure étalée, D-421). LE CHOIX (b) DE D-421 AMENDÉ, un choix de
  modèle : la variation de l'année votée ne compte que dans le sens que la loi donne
  (`variation_comptee` : une baisse votée ne fait pas une hausse ; un barème seulement
  indexé ne fait rien ; des mesures de sens contraires, ou mixtes, comptent la variation
  entière). Moins du cycle entre ainsi par les années votées ; il en reste. ΔT entre
  au compte des APU, catégorie de la famille, au signe du moteur (−ΔT : une hausse est un
  gain) ; sur l'instrument de Mésange que lisent les blocs (−ΔT, signe expansionniste) ;
  aux ménages par décile (−ΔT réparti selon la variable des cellules que la famille
  nomme, comme `comparaison.mesure`) ; aux entreprises sur leur impôt (+ΔT, recettes
  positives, lot 2) ;
* les dépenses primaires, par catégorie j de la t. 3.201 : la dépense publiée moins la
  même part du PIB qu'au départ, sur le PIB de la référence,

      ΔG_{j,t} = G_{j,t} − (G_{j,s} / PIB_s) · Y_t

  ce qui fait la dépense du jumeau égale à la dépense publiée (la référence tient la
  dépense en part constante du PIB, `part_pib_constante`). C'est la mesure « effort en
  dépense » : la dépense au-delà de la croissance de la tendance. Les prestations (D62)
  vont aux ménages par décile selon leurs pensions, allocations chômage et prestations.

LES EXOGÈNES OBSERVÉS (`exogenes_publies`), les mêmes pour le jumeau et le naïf :

* les prix : la croissance du déflateur du PIB (t. 1.103), imposée ; le jumeau ne prévoit
  pas l'inflation, elle lui est donnée, comme le scénario de prix des études ;
* les taux : la dette de référence se charge au taux r_t = r_{t−1} + (OAT_t − r_{t−1}) / 8,
  r_s le taux implicite publié du départ, l'OAT à dix ans d'Eurostat, 8 ans la durée de vie
  moyenne de la dette (choisie, non vérifiée, l'ordre de grandeur que l'AFT publie) ; le
  taux marginal, l'OAT de la première année de la fenêtre ;
* l'ajustement flux-stocks publié (t. 3.105 et Eurostat, `historique`), imposé par le
  bloc `ajustement_observe` ;
* la croissance réelle de la tendance : la moyenne de la croissance publiée du PIB en
  volume sur les années de l'estimation, jamais celles du test ; de même pour l'emploi
  (`ajout` de sa cible : la référence du cadre tient l'emploi du départ constant).

LA DEMANDE MONDIALE (D-421). L'indice XMKT de l'OCDE, W ; pour la fenêtre partie de s,
l'écart que lit le bloc `commerce` (`DemandeMondiale`) est

      d_t = (W_t / W_s) / (1 + g_W)^(t − s) − 1

g_W la croissance moyenne de W sur les années notées de l'estimation, comme celle du PIB
de la tendance : la référence fait croître les échanges comme le PIB de la tendance, qui
porte déjà la croissance moyenne des marchés et la perte de parts de marché ; seul
l'écart de la demande à sa tendance entre. Il entre dans la variante, sous la mesure
observée `observe_demande_mondiale` : la référence de la trajectoire, qui est le naïf,
reste à la tendance, et le naïf mécanique n'a pas de bloc du commerce ; elle ne change
ni l'un ni l'autre.

CE QUI MANQUE, ET COMMENT C'EST TRAITÉ. Les prix du pétrole et des importations : aucun bloc ne porte un choc de prix étranger (le
commerce, D-408) ; ils n'entrent que par le déflateur imposé. La démographie : la
population active de la référence est celle du départ (Mésange, p. 40) ; la tendance de
l'emploi le corrige pour la cible de l'emploi seulement. Les défaillances : le jumeau ne
les calcule pas, elles ne sont pas notées. Les restitutions de crédits d'impôt sont des
dépenses (D9) déjà dans la dépense publiée : seuls les crédits imputés entrent en
recettes. Les impôts sans instrument dans la base (tabacs, droits d'enregistrement,
taxe foncière, taxe sur les salaires, audiovisuel) n'entrent pas.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from typing import Any

import numpy as np

from impots.jumeau import apprentissage as app
from impots.jumeau.apprentissage import Cible, Fenetre, Schema
from impots.jumeau.champs import APU_DEPENSES
from impots.jumeau.etat import Etat
from impots.jumeau.mesures import OBSERVE, Mesure
from impots.jumeau.pas import Entrees

# --------------------------------------------------------------------------- #
# le schéma et les θ (D-417)
# --------------------------------------------------------------------------- #
#: Estimer sur 2011-2017, noter sur 2018-2019 et 2022-2024 ; 2020 et 2021 exclus (le
#: Covid : aucun bloc ne porte un confinement), la fenêtre du test d'après part de
#: l'état publié de 2021.
SCHEMA = Schema(
    estimation=(Fenetre(2010, 2014, (2011, 2012, 2013, 2014)),
                Fenetre(2014, 2017, (2015, 2016, 2017))),
    test=(Fenetre(2017, 2019, (2018, 2019)), Fenetre(2021, 2024, (2022, 2023, 2024))),
    exclues=(2020, 2021))

#: Les θ estimés : ceux des canaux de la demande et des échanges que les chocs observés
#: excitent. Les autres restent à ½.
ESTIMES = ("jumeau_consommation_profil", "jumeau_emploi_elasticite_cout",
           "jumeau_salaires_chomage", "commerce_elasticite_prix_exportations",
           "commerce_elasticite_prix_importations", "investissement_accelerateur",
           "investissement_cout_capital")
A_PRIORI = 1.0
#: Le cas que ce code rejoue, et la D-entrée qui le préenregistre ; le premier juge
#: (« rejeu_histoire », D-417, D-420) se refait sur fe9434f.
CAS, DECISION = "rejeu_histoire_r2", "D-421"
#: Durée de vie moyenne de la dette, en années (choisie, non vérifiée).
DUREE_VIE_DETTE = 8.0
#: Les statuts d'une mesure qui n'a jamais eu d'effet.
SANS_EFFET = frozenset({"censuree", "abrogee_avant_effet"})


# --------------------------------------------------------------------------- #
# les cibles (D-417) : tolérances préenregistrées, en points
# --------------------------------------------------------------------------- #
def cibles(ajout_emploi: float = 0.0) -> tuple[Cible, ...]:
    """Les douze cibles notées ; `ajout_emploi` la croissance tendancielle de l'emploi
    (points par an), lue sur l'estimation."""
    c = app
    return (
        Cible("pib_volume", "Croissance du PIB en volume", "point de %", 1.0,
              "l'ordre de l'erreur des prévisions de croissance à un an hors crise",
              c.champ_fixe("croissance_volume_pib")),
        Cible("emploi", "Croissance de l'emploi intérieur total", "point de %", 0.8,
              "la croissance de l'emploi varie de ±1 point autour de sa tendance",
              c.croissance("emploi_total"), ajout=ajout_emploi),
        Cible("chomage", "Taux de chômage (chômeurs sur emploi plus chômeurs)", "point",
              0.8, "un point de chômage est l'écart que le débat public lit",
              lambda e, p: 100.0 * app._a(e, "chomage") / app._a(e, "population_active")),
        Cible("exportations", "Croissance des exportations en volume", "point de %", 4.0,
              "la volatilité annuelle des échanges hors crise",
              c.croissance_volume("exportations", "prix_exportations")),
        Cible("importations", "Croissance des importations en volume", "point de %", 4.0,
              "la volatilité annuelle des échanges hors crise",
              c.croissance_volume("importations", "prix_importations")),
        Cible("recettes_d2", "Impôts sur la production et les importations (D2)",
              "point de PIB", 0.4, "un dixième de la catégorie", c.part("apu_r_d2")),
        Cible("recettes_d5", "Impôts courants sur le revenu et le patrimoine (D5)",
              "point de PIB", 0.5, "l'IS, volatil, y est", c.part("apu_r_d5")),
        Cible("recettes_d61", "Cotisations sociales nettes (D61)", "point de PIB", 0.4,
              "un vingtième de la catégorie", c.part("apu_r_d61")),
        Cible("recettes", "Recettes des APU hors intérêts", "point de PIB", 0.8,
              "la somme des trois tolérances, moins leur compensation",
              c.part("apu_recettes")),
        Cible("solde", "Capacité de financement des APU (B9)", "point de PIB", 1.0,
              "l'écart que les lois de programmation tiennent pour un dérapage",
              c.part("b9")),
        Cible("dette", "Dette de Maastricht", "point de PIB", 3.0,
              "trois années d'erreur de solde d'un point, cumulées",
              c.champ_fixe("ratio_dette")),
        Cible("creations", "Croissance des créations d'entreprises classiques", "point de %",
              10.0, "la volatilité annuelle des créations hors micro-entrepreneurs",
              c.croissance("creations_societes"),
              publie=c.croissance("creations_classiques")),
    )


NON_NOTEES = {
    "defaillances": ("le jumeau ne calcule pas les défaillances ; ses fermetures de "
                     "sociétés ne sont pas des défaillances (D-412)"),
    "depenses": ("les dépenses primaires sont une entrée (les chocs observés) : les noter "
                 "serait noter l'entrée"),
}


# --------------------------------------------------------------------------- #
# les familles d'impôts
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Famille:
    nom: str
    libelle: str
    lignes: tuple[tuple[str, float], ...]
    """(champ de l'état publié, et son signe) : un impôt de la t. 3.217
    (`champs.IMPOTS_3217`) ou une ligne de la t. 3.201."""
    base: str
    instruments: frozenset[str]
    categorie: str | None
    """La catégorie du compte des APU ; None pour un signal sans choc sur le compte."""
    impulsion: str | None = None
    deciles: tuple[str, ...] = ()
    entreprise: str | None = None


FAMILLES: tuple[Famille, ...] = (
    Famille("tva", "TVA", (("impot_tva", 1.0),), "c_menages", frozenset({"tva"}),
            "apu_r_d2", impulsion="tva", deciles=("tva",)),
    Famille("ticpe", "Accises sur l'énergie (TICPE)", (("impot_ticpe", 1.0),), "c_menages",
            frozenset({"accises_energie"}), "apu_r_d2", impulsion="taxe_carbone",
            deciles=("accises",)),
    Famille("ir", "Impôt sur le revenu", (("impot_ir", 1.0),), "pib",
            frozenset({"ir", "ir_capital"}), "apu_r_d5", impulsion="impot_sur_le_revenu",
            deciles=("ir",)),
    Famille("csg", "CSG et CRDS", (("impot_csg", 1.0), ("impot_crds", 1.0)), "pib",
            frozenset({"csg"}), "apu_r_d5", impulsion="csg",
            deciles=("csg_crds_salaires",)),
    # Les cotisations effectives par payeur, D611 et D613CE (t. 7.301, D-421) : D-417 les
    # lisait sur leur somme (t. 3.217), partagée à parts égales les années où les deux
    # instruments étaient votés, et entière à celui des deux qui l'était seul.
    Famille("cotisations_employeurs", "Cotisations employeurs",
            (("impot_cotisations_employeurs", 1.0),), "remunerations",
            frozenset({"cotisations_employeurs"}), "apu_r_d61",
            impulsion="cotisations_employeurs", entreprise="cotisations_employeurs"),
    Famille("cotisations_salaries", "Cotisations salariés",
            (("impot_cotisations_salaries", 1.0),), "remunerations",
            frozenset({"cotisations_salaries"}), "apu_r_d61",
            impulsion="cotisations_salaries", deciles=("cotisations_salariales",)),
    # Le CICE : une subvention (D3) dans les comptes publiés, de 2013 à 2018, que les
    # dépenses observées portent déjà au compte des APU ; la famille n'en porte que le
    # signal du coût du travail, sans second choc sur le compte (catégorie None). Ses
    # mesures sont de l'instrument `cice` (D-421) : D-417 les rangeait aux cotisations
    # employeurs, dont elles votaient la ligne sans la changer.
    Famille("subventions_cice", "Subventions sur la production (CICE)",
            (("apu_d_d3", -1.0),), "remunerations", frozenset({"cice"}),
            None, impulsion="cotisations_employeurs", entreprise="cotisations_employeurs"),
    Famille("is", "Impôt sur les sociétés, avant crédits", (("impot_is", 1.0),),
            "ebe_revenu_mixte", frozenset({"is"}), "apu_r_d5", entreprise="impot_societes"),
    Famille("production", "Impôts de production (CVAE, CFE, TP, C3S)",
            (("impot_cvae", 1.0), ("impot_cfe", 1.0), ("impot_taxe_professionnelle", 1.0),
             ("impot_c3s", 1.0)), "pib", frozenset({"impots_production"}), "apu_r_d2",
            entreprise="cvae"),
    Famille("taxe_habitation", "Taxe d'habitation", (("impot_taxe_habitation", 1.0),),
            "pib", frozenset({"taxe_habitation"}), "apu_r_d5",
            deciles=("revenu_disponible",)),
    Famille("patrimoine", "ISF et IFI", (("impot_isf_ifi", 1.0),), "pib",
            frozenset({"patrimoine"}), "apu_r_d5"),
    Famille("transmission", "Droits de mutation à titre gratuit", (("impot_dmtg", 1.0),),
            "pib", frozenset({"transmission"}), "apu_r_d91"),
)
#: Les prestations par décile : pensions, allocations chômage, prestations (comme
#: `comparaison.mesure`, la variante « dépense publique »).
DECILES_PRESTATIONS = ("retraite", "chomage_brut", "prestations")
CATEGORIES_DEPENSE = tuple(nom for nom, *_ in APU_DEPENSES)


def _valeur(etat: Etat, nom: str) -> float:
    return float(np.asarray(etat[nom]).reshape(-1)[0])


def taux_apparent(famille: Famille, etat: Etat) -> float:
    """Σ s_l T_l / B, une ligne absente de l'année (l'impôt n'existe pas) comptant pour
    zéro."""
    total = sum(signe * _valeur(etat, ligne) for ligne, signe in famille.lignes
                if etat.present(ligne))
    return total / _valeur(etat, famille.base)


def annees_votees(instruments: frozenset[str], votees: Sequence[Any]) -> frozenset[int]:
    """Les années d'effet des mesures votées d'un instrument (hors celles sans effet) :
    chaque année où une mesure étalée change le droit (`annees_effet`, D-421)."""
    return frozenset(a for m in votees
                     if m.instrument in instruments and m.statut not in SANS_EFFET
                     for a in m.annees_effet)


def poids(famille: Famille, annee: int, votees: Sequence[Any]) -> float:
    """w_{F,u} : 1 l'année d'effet d'un instrument de la famille, 0 sinon."""
    return 1.0 if annee in annees_votees(famille.instruments, votees) else 0.0


def sens_votes(famille: Famille, annee: int, votees: Sequence[Any]) -> frozenset[str]:
    """Les sens des mesures de la famille qui ont effet en `annee` (`sens_en`)."""
    return frozenset(x for m in votees
                     if m.instrument in famille.instruments and m.statut not in SANS_EFFET
                     for x in m.sens_en(annee))


def variation_comptee(famille: Famille, annee: int, variation: float,
                      votees: Sequence[Any]) -> float:
    """La part de τ_u − τ_{u−1} qui entre (D-421 amendé, le choix (b)) : rien une année
    sans mesure ; la variation entière si les mesures de l'année sont de sens contraires
    ou mixtes ; seulement sa part dans le sens voté si toutes vont dans le même sens
    (une baisse votée ne fait pas une hausse, ni l'inverse) ; rien si elles ne font que
    reconduire le droit (neutre : un barème indexé). Le τ porte le signe du prélèvement
    (`Famille.lignes`), et le sens est celui du prélèvement."""
    if poids(famille, annee, votees) == 0.0:
        return 0.0
    sens = sens_votes(famille, annee, votees) - {"neutre"}
    if not sens:
        return 0.0
    if "mixte" in sens or sens == {"hausse", "baisse"}:
        return variation
    return max(variation, 0.0) if sens == {"hausse"} else min(variation, 0.0)


def _cle(cellules: Any, variables: Sequence[str]) -> list[float]:
    valeurs = sum(np.asarray(cellules.par_decile(v), dtype=float) for v in variables)
    total = float(np.sum(valeurs))
    if total <= 0:
        raise app.ApprentissageError(f"cellules : {variables} de somme {total}")
    return [float(v) / total for v in valeurs]


def chocs_observes(fenetre: Fenetre, publies: Mapping[int, Etat],
                   pib_reference: Sequence[float], votees: Sequence[Any],
                   cellules: Any) -> list[Mesure]:
    """Les mesures observées de la fenêtre (docstring du module), une par famille d'impôts
    dont un instrument est voté dans la fenêtre, et une pour la dépense. `publies` porte
    les états publiés du départ à la fin ; `pib_reference` le PIB de la tendance, année
    par année."""
    annees = fenetre.annees
    if len(pib_reference) != len(annees):
        raise app.ApprentissageError(f"{len(pib_reference)} PIB pour {len(annees)} années")
    s = fenetre.depart
    depart = publies[s]
    pib_s = _valeur(depart, "pib")
    mesures: list[Mesure] = []
    for famille in FAMILLES:
        taux = {a: taux_apparent(famille, publies[a]) for a in (s, *annees)}
        part_base = _valeur(depart, famille.base) / pib_s
        cumul, delta = 0.0, {}
        for a, y in zip(annees, pib_reference, strict=True):
            cumul += variation_comptee(famille, a, taux[a] - taux[a - 1], votees)
            delta[a] = cumul * part_base * float(y)
        if not any(delta.values()):
            continue
        attribuees = sorted(m.id for m in votees if m.instrument in famille.instruments
                            and any(s < a <= fenetre.fin for a in m.annees_effet)
                            and m.statut not in SANS_EFFET)
        mesures.append(Mesure(
            identifiant=f"observe_{famille.nom}",
            libelle=f"{famille.libelle}, taux apparent observé ({', '.join(attribuees)})",
            auteur="comptes publiés, datés par la base des mesures votées",
            origine=OBSERVE, annees=annees,
            chocs=({a: {famille.categorie: -d} for a, d in delta.items()}
                   if famille.categorie else {}),
            impulsions=({a: {famille.impulsion: -d} for a, d in delta.items()}
                        if famille.impulsion else {}),
            menages=({a: {"deciles": [-d * c for c in _cle(cellules, famille.deciles)]}
                      for a, d in delta.items()} if famille.deciles else None),
            entreprises=({a: {famille.entreprise: d} for a, d in delta.items()}
                         if famille.entreprise else None)))
    chocs: dict[int, dict[str, float]] = {}
    for a, y in zip(annees, pib_reference, strict=True):
        chocs[a] = {j: _valeur(publies[a], j) - _valeur(depart, j) / pib_s * float(y)
                    for j in CATEGORIES_DEPENSE}
    cle = _cle(cellules, DECILES_PRESTATIONS)
    mesures.append(Mesure(
        identifiant="observe_depenses", libelle="Dépenses primaires publiées (t. 3.201)",
        auteur="comptes publiés", origine=OBSERVE, annees=annees, chocs=chocs,
        menages={a: {"deciles": [chocs[a]["apu_d_d62"] * c for c in cle]}
                 for a in annees}))
    return mesures


# --------------------------------------------------------------------------- #
# les exogènes et l'ajustement flux-stocks
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Exogenes:
    """Ce que reçoivent le jumeau et le naïf, au-delà des chocs : par année."""

    croissance_tendance: float
    croissance_emploi: float
    prix: Mapping[int, float]
    oat: Mapping[int, float]
    """En fraction (0,02 = 2 %)."""
    sfa: Mapping[int, float]
    demande_mondiale: Mapping[int, float] = dataclass_field(default_factory=dict)
    """W, l'indice de la demande mondiale adressée à la France (OCDE), par année (D-421) ;
    vide, la demande reste au sentier de la tendance."""
    croissance_demande_mondiale: float = 0.0
    """g_W, sa croissance moyenne sur les années notées de l'estimation."""


def etat_publie(annee: int) -> Etat:
    """L'état publié de l'année (`historique.etat_initial`), plus les cotisations
    effectives des employeurs et des salariés du compte des APU (t. 7.301, D-421), que
    lisent les familles des cotisations ; l'état publié du cadre n'en change pas."""
    from impots.jumeau import historique, series

    etat = historique.etat_initial(annee)
    for nom, serie in (("impot_cotisations_employeurs", "cotisations_employeurs_apu"),
                       ("impot_cotisations_salaries", "cotisations_salaries_apu")):
        etat.ecrire(nom, ("publie", ""), series.lire(serie)[annee])
    return etat


def exogenes_publies(schema: Schema = SCHEMA) -> Exogenes:
    """Les exogènes lus dans les séries publiées (`jumeau.series`, `historique`) ; les
    tendances sur les seules années notées de l'estimation."""
    from impots.jumeau import historique, series

    volume, emploi = series.lire("volume_pib"), series.lire("emploi_total")
    estimation = schema.annees("estimation")
    g = float(np.mean([volume[a] / volume[a - 1] - 1.0 for a in estimation]))
    ge = float(np.mean([emploi[a] / emploi[a - 1] - 1.0 for a in estimation]))
    indice = series.lire("indice_prix_pib")
    oat = series.lire("taux_oat_10ans")
    annees = sorted({a for f in (*schema.estimation, *schema.test) for a in f.annees})
    w = series.lire("demande_mondiale")
    gw = float(np.mean([w[a] / w[a - 1] - 1.0 for a in estimation]))
    return Exogenes(croissance_tendance=g, croissance_emploi=ge,
                    prix={a: indice[a] / indice[a - 1] - 1.0 for a in annees},
                    oat={a: oat[a] / 100.0 for a in annees},
                    sfa={a: _valeur(historique.etat_initial(a), "sfa") for a in annees},
                    demande_mondiale=dict(w), croissance_demande_mondiale=gw)


#: La mesure observée qui porte la demande mondiale dans la variante du jumeau (D-421) :
#: la référence, qui est le naïf, reste à la tendance.
DEMANDE_MONDIALE = "observe_demande_mondiale"


def mesure_demande_mondiale(fenetre: Fenetre) -> Mesure:
    """Une mesure observée sans choc sur le compte : la clé sous laquelle le bloc
    `commerce` inscrit l'écart de la demande mondiale (`DemandeMondiale.mesure`)."""
    return Mesure(identifiant=DEMANDE_MONDIALE,
                  libelle="Demande mondiale adressée à la France (OCDE, XMKT), écart à sa "
                          "tendance de l'estimation",
                  auteur="OCDE, Economic Outlook n° 119", origine=OBSERVE,
                  annees=fenetre.annees)


def ecarts_demande_mondiale(fenetre: Fenetre, exogenes: Exogenes) -> dict[int, float]:
    """d_t = (W_t / W_s) / (1 + g_W)^(t − s) − 1 pour chaque année de la fenêtre (le
    docstring du module) ; vide sans série."""
    w, s = exogenes.demande_mondiale, fenetre.depart
    if not w:
        return {}
    manquantes = [a for a in (s, *fenetre.annees) if a not in w]
    if manquantes:
        raise app.ApprentissageError(f"demande mondiale absente en {manquantes}")
    g = exogenes.croissance_demande_mondiale
    return {a: w[a] / w[s] / (1.0 + g) ** (a - s) - 1.0 for a in fenetre.annees}


def entrees(fenetre: Fenetre, exogenes: Exogenes, depart: Etat) -> Entrees:
    annees = fenetre.annees
    r = _valeur(depart, "interets_nets") / _valeur(depart, "dette_ouverture")
    taux = []
    for a in annees:
        r += (exogenes.oat[a] - r) / DUREE_VIE_DETTE
        taux.append(r)
    return Entrees(annees=annees, croissance_reelle=(exogenes.croissance_tendance,)
                   * len(annees), prix=tuple(exogenes.prix[a] for a in annees),
                   regle_depense="part_pib_constante", croissance_depense=None,
                   taux_reference=tuple(taux), taux_marginal=exogenes.oat[annees[0]],
                   noms={"histoire": f"rejeu {fenetre.depart}–{fenetre.fin} ({CAS}, "
                                     f"{DECISION})"})


class AjustementObserve:
    """L'ajustement flux-stocks publié de chaque année, imposé au jumeau et au naïf
    (sous la mesure « »)."""

    nom = "ajustement_observe"
    lit: tuple[str, ...] = ()
    ecrit = ("sfa",)
    thetas: tuple[str, ...] = ()

    def __init__(self, sfa: Mapping[int, float]) -> None:
        self.sfa = dict(sfa)

    def contribue(self, ctx: Any) -> dict[str, dict[str, Any]]:
        if ctx.annee not in self.sfa:
            raise app.ApprentissageError(f"ajustement flux-stocks de {ctx.annee} absent")
        return {"sfa": {"": np.full(ctx.n, float(self.sfa[ctx.annee]))}}


# --------------------------------------------------------------------------- #
# le simulateur
# --------------------------------------------------------------------------- #
def menages_au_depart(params: Any, depart: Etat) -> Any:
    """Les paramètres des ménages, avec les niveaux d'emploi de l'année de départ lus dans
    l'état publié (`menages.yaml` ne les porte que pour 2024 et 2025) : l'emploi salarié
    et total des comptes (t. 6.210, 6.208), les chômeurs BIT d'Eurostat (D-412 : pas
    l'enquête Emploi de la référence du lot 4 ; écart dit)."""
    import dataclasses

    niveaux = {"emploi_salarie": _valeur(depart, "emploi_salarie"),
               "emploi_total": _valeur(depart, "emploi_total"),
               "chomeurs": _valeur(depart, "chomage")}
    return dataclasses.replace(params, references={**params.references,
                                                   depart.annee: niveaux})


def simulateur(*, population: Any, cellules: Any, exogenes: Exogenes,
               observateur: app.Observateur, votees: Sequence[Any]) -> app.Simulateur:
    """(fenêtre, θ) → la trajectoire du modèle structurel complet depuis l'état publié du
    départ, sous les chocs observés et les exogènes ; les entrées d'une fenêtre se
    calculent une fois (elles ne dépendent pas de θ), les blocs à chaque appel (ils
    gardent des grandeurs par état, `menages._garde`)."""
    from impots.jumeau.blocs import ordre_structurel
    from impots.jumeau.blocs.commerce import TENDANCE, Commerce, DemandeMondiale
    from impots.jumeau.blocs.entreprises import charger as charger_entreprises
    from impots.jumeau.blocs.menages import charger as charger_menages
    from impots.jumeau.blocs.tendance import Tendance
    from impots.jumeau.trajectoire import calculer

    p_entreprises, p_menages = charger_entreprises(), charger_menages()

    preparees: dict[Fenetre, tuple[Any, ...]] = {}

    def preparer(fenetre: Fenetre) -> tuple[Any, ...]:
        if fenetre not in preparees:
            publies = {a: observateur(a) for a in (fenetre.depart, *fenetre.annees)}
            depart = publies[fenetre.depart]
            e = entrees(fenetre, exogenes, depart)
            pib = [Tendance(depart).chemin(e, k)[0] for k in range(len(e.annees))]
            mesures = chocs_observes(fenetre, publies, pib, votees, cellules)
            preparees[fenetre] = (depart, e, mesures)
        return preparees[fenetre]

    def simuler(fenetre: Fenetre, theta: Mapping[str, Any]) -> Any:
        depart, e, mesures = preparer(fenetre)
        menages = menages_au_depart(p_menages, depart)
        ecarts = ecarts_demande_mondiale(fenetre, exogenes)
        scenario = (DemandeMondiale(f"OCDE XMKT, écart à sa tendance depuis {fenetre.depart}",
                                    ecarts, mesure=DEMANDE_MONDIALE) if ecarts else TENDANCE)
        commerce = Commerce(demande_mondiale=scenario, boucle_prix=menages.part_marchande)
        blocs, boucles = ordre_structurel(depart, population, cellules,
                                          entreprises=p_entreprises, menages=menages,
                                          commerce=commerce)
        if ecarts:
            mesures = [*mesures, mesure_demande_mondiale(fenetre)]
        blocs.append(AjustementObserve(exogenes.sfa))
        return calculer(depart, entrees=e, mesures=mesures, theta=theta, blocs=blocs,
                        boucles=boucles)
    return simuler


def simulateur_mecanique(*, exogenes: Exogenes, observateur: app.Observateur,
                         votees: Sequence[Any], cellules: Any) -> app.Simulateur:
    """Le naïf mécanique (amendement de D-417) : la tendance, les chocs observés au compte
    des APU (bloc `mesures`) et l'ajustement flux-stocks publié, sans aucun bloc de
    comportement ni de bouclage ; les mêmes entrées que `simulateur`."""
    from impots.jumeau.blocs.mesures import Mesures
    from impots.jumeau.blocs.tendance import Tendance
    from impots.jumeau.trajectoire import calculer

    preparees: dict[Fenetre, tuple[Any, ...]] = {}

    def simuler(fenetre: Fenetre, theta: Mapping[str, Any]) -> Any:
        if fenetre not in preparees:
            publies = {a: observateur(a) for a in (fenetre.depart, *fenetre.annees)}
            depart = publies[fenetre.depart]
            e = entrees(fenetre, exogenes, depart)
            pib = [Tendance(depart).chemin(e, k)[0] for k in range(len(e.annees))]
            preparees[fenetre] = (depart, e, chocs_observes(fenetre, publies, pib, votees,
                                                            cellules))
        depart, e, mesures = preparees[fenetre]
        blocs = [Tendance(depart), Mesures(), AjustementObserve(exogenes.sfa)]
        return calculer(depart, entrees=e, mesures=mesures, theta=theta, blocs=blocs)
    return simuler
