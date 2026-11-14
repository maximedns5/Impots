"""Les blocs structurels des ménages (but 23, lot 4, D-409) : consommation, emploi, salaires.

Trois blocs, dans une boucle simultanée que le cadre résout par point fixe (CADRE.md §3) :
la consommation fait le PIB, le PIB fait l'emploi, l'emploi et le chômage font les
salaires, les salaires et l'emploi font le revenu des ménages, qui fait la consommation.
Ils portent à la place de Mésange ses canaux « consommation_menages », « emploi » et
« salaires » (`remplace`, `jumeau/canaux.py`) : avec eux, le bloc `mesange` est refusé.

UN MODÈLE LINÉAIRE, EN ÉCARTS. Comme Mésange, chaque bloc écrit la référence sous la
mesure « » et, sous chaque mesure m, son écart à la référence, linéarisé : les écarts des
mesures s'additionnent, ce qui fait la décomposition par mesure, et chaque tirage de θ
est un vecteur. Un profil publié R(h), cumulé, à l'horizon h = k − j + 1 années, se lit
par l'opérateur de retard (Mésange est linéaire : un choc qui change est une somme de
chocs permanents décalés, comme le bloc `mesange`) :

    L[z, R]_k = Σ_{j ≤ k} (z_j − z_{j−1}) R(k − j + 1),   z_{−1} = 0

R est interpolé linéairement entre les horizons lus (1, 2, 5 ans et le long terme, placé
à dix ans, `menages.yaml`). Les sources de chaque valeur sont dans
`jumeau/parametres/menages.yaml` ; Mésange est le document G2017-04 de l'Insee (p. = page
du PDF).

LES RÉFÉRENCES de l'année k (Y_k le PIB de la référence, a = D1/PIB du départ) :
D1_k = a Y_k ; les emplois, la population active et les chômeurs de l'année de départ,
constants (Mésange, p. 40, note 27 : population active constante en projection) ;
E_sm = π E_sal l'emploi salarié marchand (π, `part_marchande_salaries`) ; W_k = D1_k /
E_sal la rémunération moyenne ; u = U/PA le taux de chômage de départ.

BLOC `emploi` (Mésange, demande de travail p. 39 à 48 ; offre, C7) :

    ŷ_j = ΔPIB_{m,j} / Y_j                  l'écart de production de la mesure
    τ̂_j = −I^{ce}_{m,j} / D1_j,  τ̂ᶜ_j = −I^{cec}_{m,j} / D1_j   les cotisations employeurs,
                                            uniformes et ciblées (impulsions de la mesure)
    ĉ_j = ŵ_j + τ̂_j                         l'écart du coût réel du travail (prix fixes)
    ê_k = L[ŷ, R_va]_k + (η/0,44) (L[ĉ, R_c]_k + L[τ̂ᶜ, R_c^NQ]_k)
    ΔE_sm = ê_k E_sm ;  ΔE_sal = ΔE_sm ;  ΔE_tot = (1 + r_ns) ΔE_sm
    ΔPA_k = PA ŵ_k Σ_g s_g ε_g ;  ΔU_k = ΔPA_k − ΔE_tot

R_va, R_c : les profils p. 48, pondérés 0,69 / 0,31 entre qualifiés et non qualifiés
(p. 40) ; R_c^NQ celui des non qualifiés seuls, pour l'allègement ciblé. η(θ) :
l'élasticité de long terme au coût (0,44, p. 39 ; 0,31 et 0,52, Bunel et L'Horty 2012).
r_ns : les non-salariés sur les salariés marchands, qui bougent avec eux (p. 40). ε_g, s_g :
les quatre élasticités de C7 (Bargain, Orsini et Peichl 2012) à leur θ et la part de
chaque groupe dans la masse salariale des cellules. L'offre ne répond qu'au salaire que la
dynamique forme : la réponse des heures au changement d'impôt de la mesure est déjà dans
ses recettes (C7, `mesures_non_ventilees`), et la compter ici la compterait deux fois.

BLOC `salaires` (Mésange, équations WS p. 57 à 65) :

    Δu_j = 100 ((1 − u) ΔPA_j − ΔE_tot,j) / PA        l'écart du taux de chômage, points
    p̂_j = ŷ_j − ê_j                                     l'écart de productivité apparente
    κ̂_j = −I^{cs}_{m,j} / D1_j                          les cotisations salariés
    ŵ_k = b L[Δu, S_u]_k / 100 + L[p̂, S_p]_k + L[κ̂, S_p]_k + L[smic, S_smic]_k
    ΔW_k = π W_k ŵ_k ;  ΔD1_k = π D1_k (ê_k + ŵ_k)

S_u, S_p, S_smic : les profils p. 65, pondérés 0,69 / 0,31 ; b(θ) le facteur sur la
semi-élasticité au chômage (Mésange 2017 au centre, 2010 en haut, la moitié en bas,
choisie). Le coin fiscalo-social s'indexe unitairement à long terme (p. 64, sigma_W = 1 note
45) : une cotisation salariale déplace le salaire brut d'autant, une cotisation
employeur reste sur le coût ; son profil d'ajustement, que Mésange n'imprime pas, est
celui de la productivité (choisi). « smic » est le Smic réel efficace de la mesure (une
fraction, `Mesure.menages[annee]["smic"]`). Les prix sont ceux du scénario : ni la
boucle prix-salaires ni l'indexation aux prix ne sont modélisées.

La masse salariale se répartit (`revenus_cellules`) : la part de l'emploi, π D1 ê, entre
les cellules au prorata de leurs chômeurs (ceux qui trouvent ou perdent l'emploi) ; la
part du salaire, π D1 ŵ, au prorata de leur salaire super-brut ; chaque euro de la cellule
c en revenu disponible au taux ρ_c = (net − IR des salaires) / super-brut, en cotisations
(D61) au taux (super-brut − net − CSG) / super-brut, en CSG, CRDS et IR (D5) au reste,
les taux moyens de la cellule (pas marginaux, dit). Les allocations chômage suivent les
chômeurs : ΔB = β_b W_k ΔU, β_b l'allocation moyenne par chômeur sur la rémunération
moyenne des cellules ; aux ménages des cellules au prorata de leurs chômeurs, en dépense
(D62) aux APU. Le bloc écrit ΔD1 en rémunérations et −ΔD1 en EBE (à PIB donné, la masse
salariale se prend sur la marge) : l'identité des revenus tient.

BLOC `consommation` (Mésange p. 30 à 34 ; Insee, Note de conjoncture de juin 2019) :

    ΔRD_{c,k} = choc_{d(c),k} M_c / M_d + ρ_c ΔD1_{c,k} + ΔB_{c,k}
    PMC_d(h) = e(h) [APC + κ (APC_d − APC)]
    ΔC_{c,k} = Σ_j (ΔRD_{c,j} − ΔRD_{c,j−1}) PMC_{d(c)}(k − j + 1) + C_{c,k} L[Δu, Q_u]_k / 100

choc_d : le choc statique de la mesure sur le décile d, Md€, gain des ménages positif
(`Mesure.menages[annee]["deciles"]`, d'une passe sur la population, §5), réparti entre
les cellules du décile au prorata de leurs ménages M ; e(h) l'élasticité cumulée de la
consommation au revenu réel (Mésange p. 34 au centre, Insee 2019 tableau 3 l'autre
borne) ; APC, APC_d les propensions moyennes des cellules ; κ = q κ_max, q(θ) ; Q_u la
réponse de la consommation au chômage (épargne de précaution, Mésange p. 34) ; C_{c,k} la
consommation de référence de la cellule. Le bloc écrit ΔC = Σ_c ΔC_c sur la consommation
des ménages et sur le PIB, la TVA et les accises t ΔC (t, leur taux moyen dans les
cellules) en D2 des APU et en impôts sur la production, le reste en EBE : les identités
des emplois et des revenus tiennent. Il ne retranche pas les importations : c'est le
lot 3, qui le fera sur la consommation que ce bloc écrit. Il écrit aussi le revenu
disponible et la consommation de chaque décile, référence comprise : les montants des
cellules en part du PIB de 2024, fois Y_k.

UNE MESURE SANS CHOC PAR DÉCILE, mais avec une impulsion sur un instrument des ménages
(IR, CSG, cotisations salariés, TVA, taxe carbone), est refusée avant le premier pas : son
canal de la consommation serait un zéro qui se lirait comme un chiffrage.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from impots.jumeau import thetas
from impots.jumeau.cellules import N_DECILES, TYPES, Cellules
from impots.jumeau.champs import DECILES_MENAGES
from impots.jumeau.etat import ChampAbsent, Etat
from impots.jumeau.pas import Contexte, Entrees
from impots.predictif.rejouer import value_at

PARAMETRES = Path(__file__).resolve().parents[1] / "parametres" / "menages.yaml"
OFFRE = (Path(__file__).resolve().parents[2] / "behavioural" / "parameters"
         / "labour_supply.yaml")
#: Les instruments de Mésange dont le canal de la consommation passe par les ménages.
INSTRUMENTS_MENAGES = ("impot_sur_le_revenu", "csg", "cotisations_salaries", "tva",
                       "taxe_carbone")
CHAMPS_TRAVAIL = ("population_active", "emploi_total", "emploi_salarie", "chomage")
RDB = tuple(f"rdb_d{d:02d}" for d in DECILES_MENAGES)
CONSO = tuple(f"conso_d{d:02d}" for d in DECILES_MENAGES)
CLES_MENAGES = frozenset({"deciles", "smic"})


class MenagesError(ValueError):
    """Un bloc des ménages qui ne se construit ou ne se lit pas."""


# --------------------------------------------------------------------------- #
# les paramètres
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Parametres:
    horizons: np.ndarray
    emploi_va: np.ndarray
    emploi_cout: np.ndarray
    emploi_cout_nq: np.ndarray
    sigma: dict[str, float]
    salaires_chomage: np.ndarray
    salaires_productivite: np.ndarray
    salaires_smic: np.ndarray
    echelle_chomage: dict[str, float]
    references: dict[int, dict[str, float]]
    part_marchande: float
    non_salaries: float
    conso_centre: np.ndarray
    conso_autre: np.ndarray
    conso_chomage: np.ndarray
    pente: dict[str, float]
    pib_cellules: float
    offre: dict[str, dict[str, Any]]


def charger(chemin: Path = PARAMETRES, offre: Path = OFFRE) -> Parametres:
    """Les valeurs de `menages.yaml` et les quatre lignes de C7 du magasin."""
    p = yaml.safe_load(chemin.read_text(encoding="utf-8"))
    q = float(p["emploi"]["part_qualifies"]["valeur"])

    def mele(bloc: Mapping[str, Any], nom: str) -> np.ndarray:
        return (q * np.asarray(bloc["qualifie"][nom], dtype=float)
                + (1.0 - q) * np.asarray(bloc["non_qualifie"][nom], dtype=float))

    def borne(d: Mapping[str, Any]) -> dict[str, float]:
        return {"low": float(d["bas"]), "central": float(d["centre"]),
                "high": float(d["haut"]), "un": "high"}

    lignes = yaml.safe_load(offre.read_text(encoding="utf-8"))["parameters"]
    groupes = {"femmes_en_couple": "labour_supply_married_women",
               "hommes_en_couple": "labour_supply_married_men",
               "femmes_seules": "labour_supply_single_women",
               "hommes_seuls": "labour_supply_single_men"}
    offre_rows = {}
    for groupe, cle in groupes.items():
        v = lignes[cle]["value"]
        offre_rows[groupe] = {"cle": cle, "low": v["low"], "central": v["central"],
                              "high": v["high"], "un": lignes[cle]["theta"]["un"]}
    e, s, c = p["emploi"], p["salaires"], p["consommation"]
    refs = {int(a): {k: float(x) for k, x in v.items()}
            for a, v in e["references"].items() if str(a).isdigit()}
    return Parametres(
        horizons=np.asarray(p["horizons"]["lus"], dtype=float),
        emploi_va=mele(e, "valeur_ajoutee"), emploi_cout=mele(e, "cout_reel"),
        emploi_cout_nq=np.asarray(e["non_qualifie"]["cout_reel"], dtype=float),
        sigma=borne(e["elasticite_cout"]),
        salaires_chomage=mele(s, "chomage"), salaires_productivite=mele(s, "productivite"),
        salaires_smic=mele(s, "smic"), echelle_chomage=borne(s["echelle_chomage"]),
        references=refs, part_marchande=float(e["part_marchande_salaries"]["valeur"]),
        non_salaries=float(e["non_salaries_sur_salaries_marchands"]["valeur"]),
        conso_centre=np.asarray(c["elasticite_revenu"]["centre"], dtype=float),
        conso_autre=np.asarray(c["elasticite_revenu"]["autre"], dtype=float),
        conso_chomage=np.asarray(c["chomage"]["valeur"], dtype=float),
        pente=borne(c["pente_deciles"]),
        pib_cellules=float(p["normalisation"]["pib_annee_cellules"]["valeur"]),
        offre=offre_rows)


#: L'horizon le plus long qu'une trajectoire lit, en années.
HORIZON_MAX = 100


def profil(points: np.ndarray, horizons: np.ndarray, h: int) -> Any:
    """R(h), interpolé entre les horizons lus ; au-delà du dernier, le long terme. Les
    points peuvent porter un axe de tirages en dernier."""
    pts = np.asarray(points, dtype=float)
    return poids_interpolation(horizons, h)[-1] @ pts


def poids_interpolation(horizons: np.ndarray, h_max: int) -> np.ndarray:
    """La matrice (h_max, len(horizons)) qui donne R(1) … R(h_max) depuis les points lus :
    l'interpolation linéaire de `np.interp`, écrite une fois."""
    out = np.zeros((h_max, len(horizons)))
    for h in range(1, h_max + 1):
        unite = np.eye(len(horizons))
        out[h - 1] = [np.interp(h, horizons, unite[:, i]) for i in range(len(horizons))]
    return out


def retard(z: Sequence[Any], table: np.ndarray) -> Any:
    """L[z, R]_k = Σ_{j ≤ k} (z_j − z_{j−1}) R(k − j + 1), k le dernier rang de z ;
    `table[h − 1]` est R(h)."""
    k = len(z) - 1
    total: Any = 0.0
    precedent: Any = 0.0
    for j, valeur in enumerate(z):
        pas_ = valeur - precedent
        precedent = valeur
        total = total + pas_ * table[k - j]
    return total


# --------------------------------------------------------------------------- #
# ce que les cellules donnent aux blocs
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Structure:
    """Les parts et les taux des cellules, en euros de 2024 rapportés au PIB de 2024."""

    menages: np.ndarray
    part_chomeurs: np.ndarray
    part_super_brut: np.ndarray
    rho: np.ndarray
    taux_d61: np.ndarray
    taux_d5: np.ndarray
    rd_pib: np.ndarray
    conso_pib: np.ndarray
    apc: float
    apc_decile: np.ndarray
    kappa_max: float
    taux_conso: float
    allocation_sur_salaire: float
    parts_offre: dict[str, float]
    decile: np.ndarray


def structure(cel: Cellules, pib_cellules: float) -> Structure:
    sb = cel["salaire_super_brut"]
    net, csg, ir = cel["salaire_net"], cel["csg_crds_salaires"], cel["ir"]
    imposable = cel["salaire_imposable"] + cel["retraite"] + cel["chomage_brut"]
    ir_salaires = np.divide(ir * cel["salaire_imposable"], imposable,
                            out=np.zeros_like(ir), where=imposable > 0)
    sans_salaire = sb <= 0
    rho = np.divide(net - ir_salaires, sb, out=np.zeros_like(sb), where=~sans_salaire)
    d61 = np.divide(sb - net - csg, sb, out=np.zeros_like(sb), where=~sans_salaire)
    d5 = np.where(sans_salaire, 0.0, 1.0 - rho - d61)
    # Une cellule sans salaire n'a ni chômeur qui retrouve un emploi à son taux, ni part
    # de la masse : ses taux ne servent pas ; sa part des chômeurs, si elle en a, prend
    # les taux moyens.
    total_sb = float(sb.sum())
    moyen = (float((rho * sb).sum() / total_sb), float((d61 * sb).sum() / total_sb))
    rho = np.where(sans_salaire, moyen[0], rho)
    d61 = np.where(sans_salaire, moyen[1], d61)
    d5 = np.where(sans_salaire, 1.0 - moyen[0] - moyen[1], d5)
    rd, conso = cel["revenu_disponible"], cel["consommation"]
    apc = float(conso.sum() / rd.sum())
    apc_d = cel.par_decile("consommation") / cel.par_decile("revenu_disponible")
    au_dessus = apc_d > apc
    kappa_max = float(np.min((1.0 - apc) / (apc_d[au_dessus] - apc))) if au_dessus.any() \
        else 0.0
    if apc >= 1.0:
        raise MenagesError(f"propension moyenne des cellules {apc:.3f} ≥ 1")
    salaire_moyen = total_sb / cel.total("salaries")
    allocation = cel.total("chomage_brut") / cel.total("chomeurs")
    return Structure(
        menages=cel["menages"], part_chomeurs=cel["chomeurs"] / cel.total("chomeurs"),
        part_super_brut=sb / total_sb, rho=rho, taux_d61=d61, taux_d5=d5,
        rd_pib=rd / 1e9 / pib_cellules, conso_pib=conso / 1e9 / pib_cellules, apc=apc,
        apc_decile=apc_d, kappa_max=min(1.0, kappa_max),
        taux_conso=float((cel["tva"] + cel["accises"]).sum() / conso.sum()),
        allocation_sur_salaire=allocation / salaire_moyen,
        parts_offre=dict(cel.parts_offre), decile=cel.deciles)


# --------------------------------------------------------------------------- #
# les références de l'année, et les écarts d'une mesure lus sur un état
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Reference:
    pib: np.ndarray
    d1: np.ndarray
    salaire: np.ndarray
    emploi_salarie: float
    emploi_marchand: float
    emploi_total: float
    chomeurs: float
    population_active: float

    @property
    def taux_chomage(self) -> float:
        return self.chomeurs / self.population_active


def reference(params: Parametres, depart: Etat, pib: np.ndarray) -> Reference:
    annee = depart.annee
    if annee not in params.references:
        raise MenagesError(f"aucun niveau d'emploi de référence pour {annee} dans "
                           f"menages.yaml ({sorted(params.references)})")
    r = params.references[annee]
    part_d1 = float(depart["remunerations"][0]) / float(depart["pib"][0])
    d1 = part_d1 * np.asarray(pib, dtype=float)
    return Reference(pib=np.asarray(pib, dtype=float), d1=d1,
                     salaire=d1 * 1e6 / r["emploi_salarie"],
                     emploi_salarie=r["emploi_salarie"],
                     emploi_marchand=params.part_marchande * r["emploi_salarie"],
                     emploi_total=r["emploi_total"], chomeurs=r["chomeurs"],
                     population_active=r["emploi_total"] + r["chomeurs"])


def _de(etat: Etat, nom: str, mesure: str, n: int) -> np.ndarray:
    """L'écart d'une mesure sur un champ de l'état ; nul si l'état ne le porte pas encore
    (la première itération du point fixe part de l'écart nul) ou si la mesure n'y a rien
    écrit."""
    try:
        parts = etat.par_mesure(nom)
    except ChampAbsent:
        return np.zeros(n)
    return parts.get(mesure, np.zeros(n))


@dataclass(frozen=True)
class Ecarts:
    """Les écarts d'une mesure à une année, en parts (ê, ŵ, ŷ) et en milliers."""

    y: np.ndarray
    e: np.ndarray
    w: np.ndarray
    d_pa: np.ndarray
    d_tot: np.ndarray
    d_u: np.ndarray


def ecarts(etat: Etat, mesure: str, ref: Reference, params: Parametres) -> Ecarts:
    n = etat.n
    return Ecarts(
        y=_de(etat, "pib", mesure, n) / ref.pib,
        e=_de(etat, "emploi_salarie", mesure, n) / ref.emploi_marchand,
        w=_de(etat, "salaire_moyen", mesure, n) / (params.part_marchande * ref.salaire),
        d_pa=_de(etat, "population_active", mesure, n),
        d_tot=_de(etat, "emploi_total", mesure, n),
        d_u=_de(etat, "chomage", mesure, n))


def chomage_points(ec: Ecarts, ref: Reference) -> np.ndarray:
    """Δu, l'écart du taux de chômage en points : 100 ((1 − u) ΔPA − ΔE_tot) / PA."""
    return 100.0 * ((1.0 - ref.taux_chomage) * ec.d_pa - ec.d_tot) / ref.population_active


def impulsion(etat: Etat, instrument: str, mesure: str) -> np.ndarray:
    return _de(etat, f"impulsion_{instrument}", mesure, etat.n)


def choc_menages(mesure: Any, annee: int) -> Mapping[str, Any]:
    """Le choc de la mesure sur les ménages de l'année : {"deciles": 10 Md€, "smic": x}."""
    menages = getattr(mesure, "menages", None) or {}
    return menages.get(annee, {})


def revenus_cellules(etat: Etat, mesure: Any, ref: Reference, params: Parametres,
                     st: Structure) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(ΔRD par cellule, ΔD1 par cellule, ΔB), de forme (50, n), (50, n) et (n,), Md€ :
    l'écart du revenu disponible de chaque cellule à une année, le choc statique de la
    mesure et ce que la dynamique de l'emploi et des salaires lui apporte."""
    ec = ecarts(etat, mesure.identifiant, ref, params)
    pi_d1 = params.part_marchande * ref.d1
    d1_c = (np.outer(st.part_chomeurs, pi_d1 * ec.e)
            + np.outer(st.part_super_brut, pi_d1 * ec.w))
    db = st.allocation_sur_salaire * ref.salaire * ec.d_u * 1e3 / 1e9
    rd = st.rho[:, None] * d1_c + np.outer(st.part_chomeurs, db)
    choc = choc_menages(mesure, etat.annee).get("deciles")
    if choc is not None:
        par_decile = np.bincount(st.decile, weights=st.menages, minlength=N_DECILES)
        poids = st.menages / par_decile[st.decile]
        rd = rd + (np.asarray(choc, dtype=float)[st.decile] * poids)[:, None]
    return rd, d1_c, db


def menages_depuis_deciles(rows: Sequence[Any]) -> list[float]:
    """Le choc par décile d'un rapport (`aggregate.DecileRow`, ou ses dictionnaires) en
    Md€, gain des ménages positif : mean_delta × n_households."""
    out = [0.0] * N_DECILES
    for r in rows:
        lire = (r.get if isinstance(r, Mapping) else lambda k, r=r: getattr(r, k))
        if lire("mean_delta") is None:
            raise MenagesError("un décile sans écart de réforme : pas de choc à lire")
        out[int(lire("decile")) - 1] = float(lire("mean_delta")) * float(
            lire("n_households")) / 1e9
    return out


# --------------------------------------------------------------------------- #
# les blocs
# --------------------------------------------------------------------------- #
class _Base:
    """Ce que les trois blocs partagent : les paramètres, la structure des cellules, les
    tables des profils, les références de l'année et les écarts d'une mesure. Les
    grandeurs d'une année passée ne changent plus : elles sont gardées (`_memo`), sous
    l'état qui les porte, le temps d'une trajectoire."""

    nom: str

    def __init__(self, cellules: Cellules, params: Parametres | None = None) -> None:
        self.params = params if params is not None else charger()
        self.cellules = cellules
        self.st = structure(cellules, self.params.pib_cellules)
        p = self.params
        self.poids = poids_interpolation(p.horizons, HORIZON_MAX)
        self.tables = {nom: self.poids @ v for nom, v in (
            ("emploi_va", p.emploi_va), ("emploi_cout", p.emploi_cout),
            ("emploi_cout_nq", p.emploi_cout_nq), ("salaires_chomage", p.salaires_chomage),
            ("salaires_productivite", p.salaires_productivite),
            ("salaires_smic", p.salaires_smic), ("conso_chomage", p.conso_chomage))}
        self._memo: dict[tuple[Any, ...], tuple[Any, Any]] = {}
        self._fixes: dict[Any, Any] = {}
        self._fixes_de: tuple[Any, Any] | None = None

    def _fixe(self, ctx: Contexte, cle: Any, calcul: Any) -> Any:
        """Une valeur de l'année courante que les itérations du point fixe ne changent
        pas (la référence, θ, les propensions) : calculée une fois par année."""
        if self._fixes_de is None or self._fixes_de[0] is not ctx.courant \
                or self._fixes_de[1] is not ctx.theta:
            self._fixes, self._fixes_de = {}, (ctx.courant, ctx.theta)
        if cle not in self._fixes:
            self._fixes[cle] = calcul()
        return self._fixes[cle]

    def _garde(self, ctx: Contexte, j: int, cle: tuple[Any, ...], calcul: Any) -> Any:
        """La valeur d'une année j : calculée à chaque itération pour l'année courante,
        une fois pour une année passée."""
        if ctx.k + 1 > HORIZON_MAX:
            raise MenagesError(f"trajectoire de plus de {HORIZON_MAX} ans")
        if j == ctx.k:
            return calcul()
        etat = ctx.passe(j)
        memo = self._memo.get((id(etat), *cle))
        if memo is None or memo[0] is not etat:
            memo = (etat, calcul())
            self._memo[(id(etat), *cle)] = memo
        return memo[1]

    def _debut(self, ctx: Contexte) -> None:
        if ctx.k == 0:
            self._memo.clear()

    def _ref(self, ctx: Contexte, j: int) -> Reference:
        # Le PIB de référence de l'année ne bouge pas pendant le point fixe : dans la
        # variante, c'est celui de la référence calculée ; dans la référence, les blocs
        # des ménages n'écrivent pas de PIB.
        if j == ctx.k:
            return self._fixe(ctx, "ref", lambda: reference(
                self.params, ctx.depart, ctx.pib_reference(j)))
        return self._garde(ctx, j, ("ref",), lambda: reference(
            self.params, ctx.depart, ctx.pib_reference(j)))

    def _etat(self, ctx: Contexte, j: int) -> Etat:
        return ctx.courant if j == ctx.k else ctx.passe(j)

    def _ecarts(self, ctx: Contexte, j: int, m: str) -> Ecarts:
        return self._garde(ctx, j, ("ecarts", m), lambda: ecarts(
            self._etat(ctx, j), m, self._ref(ctx, j), self.params))

    def _chemin(self, ctx: Contexte, m: str) -> tuple[list[Ecarts], list[Reference]]:
        return ([self._ecarts(ctx, j, m) for j in range(ctx.k + 1)],
                [self._ref(ctx, j) for j in range(ctx.k + 1)])

    def _impulsion(self, ctx: Contexte, j: int, instrument: str, m: str) -> np.ndarray:
        return self._garde(ctx, j, ("impulsion", instrument, m), lambda: -impulsion(
            self._etat(ctx, j), instrument, m) / self._ref(ctx, j).d1)

    def _du(self, ctx: Contexte, j: int, m: str) -> np.ndarray:
        return self._garde(ctx, j, ("du", m), lambda: chomage_points(
            self._ecarts(ctx, j, m), self._ref(ctx, j)))

    def _theta(self, ctx: Contexte, cle: str, row: Mapping[str, Any]) -> np.ndarray:
        return self._fixe(ctx, ("theta", cle), lambda: np.asarray(
            value_at(row, thetas.lire(ctx.theta, cle, ctx.n)), dtype=float))


class Emploi(_Base):
    nom = "emploi"
    lit = ("pib", "salaire_moyen", *CHAMPS_TRAVAIL, "impulsion_cotisations_employeurs",
           "impulsion_cotisations_employeurs_ciblees")
    ecrit = CHAMPS_TRAVAIL
    thetas = (thetas.EMPLOI_COUT, *thetas.OFFRE_TRAVAIL)
    remplace = ("emploi",)

    def contribue(self, ctx: Contexte) -> dict[str, dict[str, Any]]:
        self._debut(ctx)
        p, k, tb = self.params, ctx.k, self.tables
        ref = self._ref(ctx, k)
        out: dict[str, dict[str, Any]] = {
            "population_active": {"": ref.population_active},
            "emploi_total": {"": ref.emploi_total},
            "emploi_salarie": {"": ref.emploi_salarie}, "chomage": {"": ref.chomeurs}}
        if not ctx.mesures:
            return out
        echelle = self._theta(ctx, thetas.EMPLOI_COUT, p.sigma) / p.sigma["central"]
        elasticite = sum(self.st.parts_offre.get(g, 0.0)
                         * self._theta(ctx, row["cle"], row) for g, row in p.offre.items())
        for m in ctx.mesures:
            ident = m.identifiant
            chemin, _ = self._chemin(ctx, ident)
            tau = [self._impulsion(ctx, j, "cotisations_employeurs", ident)
                   for j in range(k + 1)]
            cible = [self._impulsion(ctx, j, "cotisations_employeurs_ciblees", ident)
                     for j in range(k + 1)]
            cout = [ec.w + t for ec, t in zip(chemin, tau, strict=True)]
            e_k = (retard([ec.y for ec in chemin], tb["emploi_va"])
                   + echelle * (retard(cout, tb["emploi_cout"])
                                + retard(cible, tb["emploi_cout_nq"])))
            e_k = np.zeros(ctx.n) + e_k
            d_sm = e_k * ref.emploi_marchand
            d_tot = (1.0 + p.non_salaries) * d_sm
            d_pa = ref.population_active * elasticite * chemin[-1].w
            out["emploi_salarie"][ident] = d_sm
            out["emploi_total"][ident] = d_tot
            out["population_active"][ident] = d_pa
            out["chomage"][ident] = d_pa - d_tot
        return out


class Salaires(_Base):
    nom = "salaires"
    lit = ("pib", "salaire_moyen", *CHAMPS_TRAVAIL, "impulsion_cotisations_salaries")
    ecrit = ("salaire_moyen", "remunerations", "ebe_revenu_mixte", "apu_r_d61", "apu_r_d5",
             "apu_d_d62")
    thetas = (thetas.SALAIRES_CHOMAGE,)
    remplace = ("salaires",)

    def preparer(self, entrees: Entrees, mesures: Sequence[Any]) -> None:
        verifier_menages(mesures)

    def contribue(self, ctx: Contexte) -> dict[str, dict[str, Any]]:
        self._debut(ctx)
        p, st, k, tb = self.params, self.st, ctx.k, self.tables
        ref = self._ref(ctx, k)
        out: dict[str, dict[str, Any]] = {c: {} for c in self.ecrit}
        out["salaire_moyen"][""] = ref.salaire
        if not ctx.mesures:
            return out
        b = self._theta(ctx, thetas.SALAIRES_CHOMAGE, p.echelle_chomage)
        for m in ctx.mesures:
            ident = m.identifiant
            chemin, _ = self._chemin(ctx, ident)
            du = [self._du(ctx, j, ident) for j in range(k + 1)]
            prod = [ec.y - ec.e for ec in chemin]
            coin = [self._impulsion(ctx, j, "cotisations_salaries", ident)
                    for j in range(k + 1)]
            smic = [float(choc_menages(m, ctx.annee - k + j).get("smic", 0.0))
                    for j in range(k + 1)]
            w_k = (b * retard(du, tb["salaires_chomage"]) / 100.0
                   + retard(prod, tb["salaires_productivite"])
                   + retard(coin, tb["salaires_productivite"])
                   + retard(smic, tb["salaires_smic"]))
            w_k = np.zeros(ctx.n) + w_k
            out["salaire_moyen"][ident] = p.part_marchande * ref.salaire * w_k
            # La masse de l'année, avec l'emploi de l'année et ce salaire.
            pi_d1 = p.part_marchande * ref.d1
            d1_c = (np.outer(st.part_chomeurs, pi_d1 * chemin[-1].e)
                    + np.outer(st.part_super_brut, pi_d1 * w_k))
            d1 = d1_c.sum(axis=0)
            out["remunerations"][ident] = d1
            out["ebe_revenu_mixte"][ident] = -d1
            out["apu_r_d61"][ident] = st.taux_d61 @ d1_c
            out["apu_r_d5"][ident] = st.taux_d5 @ d1_c
            out["apu_d_d62"][ident] = (st.allocation_sur_salaire * ref.salaire
                                       * chemin[-1].d_u * 1e3 / 1e9)
        return out


def verifier_menages(mesures: Sequence[Any]) -> None:
    """Les refus du lot 4, avant le premier pas : un choc aux ménages mal formé ; une
    impulsion sur un instrument des ménages sans choc par décile."""
    for m in mesures:
        menages = getattr(m, "menages", None) or {}
        for annee, choc in menages.items():
            inconnues = sorted(set(choc) - CLES_MENAGES)
            if inconnues:
                raise MenagesError(f"mesure « {m.identifiant} », {annee} : clés du choc "
                                   f"aux ménages inconnues {inconnues} ({sorted(CLES_MENAGES)})")
            if "deciles" in choc and len(choc["deciles"]) != N_DECILES:
                raise MenagesError(f"mesure « {m.identifiant} », {annee} : "
                                   f"{len(choc['deciles'])} déciles, pas {N_DECILES}")
        for annee, impulsions in (m.impulsions or {}).items():
            touches = sorted(i for i in INSTRUMENTS_MENAGES if impulsions.get(i))
            if touches and "deciles" not in menages.get(annee, {}):
                raise MenagesError(
                    f"mesure « {m.identifiant} », {annee} : une impulsion sur {touches} et "
                    f"aucun choc par décile : le canal de la consommation, que le bloc "
                    f"des ménages porte à la place de Mésange, serait un zéro")


class Consommation(_Base):
    nom = "consommation"
    lit = ("pib", "salaire_moyen", *CHAMPS_TRAVAIL)
    ecrit = ("c_menages", "pib", "impots_production", "ebe_revenu_mixte", "apu_r_d2", *RDB,
             *CONSO)
    thetas = (thetas.CONSOMMATION_PROFIL, thetas.CONSOMMATION_PENTE)
    remplace = ("consommation_menages",)

    def __init__(self, cellules: Cellules, params: Parametres | None = None) -> None:
        super().__init__(cellules, params)
        self.indicatrices = np.stack([self.st.decile == d for d in range(N_DECILES)]
                                     ).astype(float)

    def preparer(self, entrees: Entrees, mesures: Sequence[Any]) -> None:
        verifier_menages(mesures)

    def pmc(self, ctx: Any) -> np.ndarray:
        """PMC_d(h) pour h = 1 … k + 1 : forme (k + 1, 10, n)."""
        p, st = self.params, self.st
        bas = np.minimum(p.conso_centre, p.conso_autre)
        haut = np.maximum(p.conso_centre, p.conso_autre)
        t = thetas.lire(ctx.theta, thetas.CONSOMMATION_PROFIL, ctx.n)
        e_pts = np.stack([value_at({"low": lo, "central": c, "high": hi, "un": "high"}, t)
                          for lo, c, hi in zip(bas, p.conso_centre, haut, strict=True)])
        e_h = poids_interpolation(p.horizons, ctx.k + 1) @ e_pts  # (k + 1, n)
        kappa = st.kappa_max * np.asarray(value_at(p.pente, thetas.lire(
            ctx.theta, thetas.CONSOMMATION_PENTE, ctx.n)), dtype=float)
        forme = st.apc + kappa[None, :] * (st.apc_decile[:, None] - st.apc)  # (10, n)
        return e_h[:, None, :] * forme[None, :, :]

    def _rd(self, ctx: Contexte, j: int, m: Any) -> np.ndarray:
        return self._garde(ctx, j, ("rd", m.identifiant), lambda: revenus_cellules(
            self._etat(ctx, j), m, self._ref(ctx, j), self.params, self.st)[0])

    def contribue(self, ctx: Contexte) -> dict[str, dict[str, Any]]:
        self._debut(ctx)
        st, k = self.st, ctx.k
        ref = self._ref(ctx, k)
        out: dict[str, dict[str, Any]] = {c: {} for c in self.ecrit}
        rd_ref = self.indicatrices @ np.outer(st.rd_pib, ref.pib)
        c_ref_cellules = np.outer(st.conso_pib, ref.pib)
        c_ref = self.indicatrices @ c_ref_cellules
        for d in range(N_DECILES):
            out[RDB[d]][""] = rd_ref[d]
            out[CONSO[d]][""] = c_ref[d]
        if not ctx.mesures:
            return out
        pmc = self._fixe(ctx, "pmc", lambda: self.pmc(ctx))
        for m in ctx.mesures:
            ident = m.identifiant
            rds = [self._rd(ctx, j, m) for j in range(k + 1)]
            du = [self._du(ctx, j, ident) for j in range(k + 1)]
            dc = c_ref_cellules * (retard(du, self.tables["conso_chomage"]) / 100.0)
            precedent = 0.0
            for j, rd in enumerate(rds):
                dc = dc + (rd - precedent) * pmc[k - j][st.decile]
                precedent = rd
            total = dc.sum(axis=0)
            out["c_menages"][ident] = total
            out["pib"][ident] = total
            out["impots_production"][ident] = st.taux_conso * total
            out["apu_r_d2"][ident] = st.taux_conso * total
            out["ebe_revenu_mixte"][ident] = (1.0 - st.taux_conso) * total
            rd_d = self.indicatrices @ rds[-1]
            c_d = self.indicatrices @ dc
            for d in range(N_DECILES):
                out[RDB[d]][ident] = rd_d[d]
                out[CONSO[d]][ident] = c_d[d]
        return out


#: L'ordre des trois blocs et leur boucle, à brancher après `tendance` et `mesures`.
ORDRE = ("consommation", "emploi", "salaires")


def blocs_menages(cellules: Cellules, params: Parametres | None = None
                  ) -> tuple[list[Any], tuple[str, ...]]:
    """Les trois blocs des ménages dans leur ordre, et la boucle qui les lie."""
    params = params if params is not None else charger()
    return ([Consommation(cellules, params), Emploi(cellules, params),
             Salaires(cellules, params)], ORDRE)


__all__ = [
    "TYPES",
    "Consommation",
    "Emploi",
    "Salaires",
    "blocs_menages",
    "charger",
    "menages_depuis_deciles",
    "revenus_cellules",
]
