"""La boucle population ↔ jumeau (but 28, volet `boucle`, D-545).

POURQUOI. Le jumeau fait des emplois (bloc `emploi`) ; la population n'en reçoit rien. Ce
que ces emplois rendent aux APU et aux ménages, le jumeau le compte par des taux moyens
de cellule (`blocs.menages`) : la masse de l'emploi, π D1 ê, va aux cellules au prorata
de leurs chômeurs, chaque euro en revenu au taux ρ_c, en cotisations au taux t61_c, en
CSG, CRDS et IR au taux t5_c, et chaque chômeur de moins rend β W d'allocation (β
l'allocation moyenne par chômeur sur le super-brut moyen par salarié). Aucune autre
prestation ne bouge : ni le RSA, ni la prime d'activité, ni les aides au logement. Et
chaque emploi créé est payé le salaire moyen W. Ce module remplace ces élasticités
forfaitaires par une microsimulation : des chômeurs de la population deviennent
salariés, OpenFisca recalcule leurs impôts, leurs cotisations et leurs prestations, et
l'écart revient au jumeau.

LA RÈGLE DE LA TRANSITION (`variantes`).

* *Qui.* Les chômeurs au sens du BIT de la population (`statut_activite` « unemployed »,
  l'enquête Emploi), de 15 à 64 ans, chacun avec la même probabilité par unité de poids.
  C'est la règle du jumeau, dite : la population active y est constante (Mésange, p. 40,
  note 27), un emploi marchand de plus est un chômeur de moins (ΔU = −ΔE, hors la réponse
  de l'offre au salaire), et la masse va « au prorata des chômeurs » des cellules. Les
  inactifs ne sont pas tirés : le jumeau ne les fait pas entrer dans l'emploi.
* *Dans quel ménage.* Le sien : chaque chômeur fait une variante de son ménage, où lui
  seul change ; les autres membres, le logement, les enfants restent. La repondération
  est un mélange : la variante reçoit la part s du poids du ménage, l'original garde
  1 − s. Le total est linéaire en s (§ plus bas).
* *À quel salaire.* Le taux mensuel brut de la personne quand elle travaille : celui de
  ses mois en emploi de l'année, quand elle en a (son salaire sur ses mois travaillés,
  `mois_travailles`) ; sinon celui d'un donneur tiré, à graine fixe, parmi les chômeurs
  qui en ont un, du même sexe et du même côté de 25 ans. C'est la règle de la population
  elle-même (`population.emploi_discontinu`, étape « ppa » du but 19 : le taux mensuel
  d'un salarié de la même classe d'emploi, du même sexe et du même côté de 25 ans,
  d'abord parmi les contrats à durée limitée), qu'on prolonge sans rien caler. La quotité
  est la sienne (celle de son donneur). La variante travaille douze mois sur douze, sans
  allocation chômage ; l'emploi gagné, en personnes-années, est 1 − m/12, m les mois
  qu'elle travaillait déjà. Le câblage écrit le même salaire sur les années d'historique
  (`to_openfisca`, l'hypothèse stationnaire de D-011) : la variante tient l'emploi
  durablement, et les aides au logement le lisent dans leurs ressources de N − 2.

LES COEFFICIENTS (`coefficients`). Par personne-année d'emploi, la moyenne pondérée des
écarts variante − original, en euros de l'année de la passe : le super-brut, les
cotisations (super-brut − net − CSG et CRDS des salaires : la définition de `t61`), la
CSG et la CRDS des salaires, l'IR et la CSG et la CRDS du chômage (D5), l'allocation
chômage brute, les autres prestations (`cellules.PRESTATIONS`, servies en espérance),
le revenu disponible, et sa répartition entre les cinquante cellules (le décile et le
type du ménage d'origine). Chaque montant est rapporté au super-brut moyen par salarié
de la même passe, comme β l'est dans le jumeau : un ratio, que le jumeau porte à chaque
année par sa rémunération moyenne W_k.

CE QUI REVIENT AU JUMEAU (`corrections`), et le double compte. La boucle ne s'ajoute pas
aux taux forfaitaires : elle les remplace pour la part de l'emploi de la masse, et pour
elle seule. Pour la mesure m, l'année k, M = π D1_k ê_k (Md€), la masse que le jumeau
donne aux emplois salariés marchands, q le super-brut d'une embauche sur W :

    remunerations   += (q − 1) M         EBE −= idem (le PIB ne bouge pas)
    apu_r_d61       += (c61 − Σ_c p_c t61_c) M
    apu_r_d5        += (c5 − Σ_c p_c t5_c) M
    apu_d_d62       += (cch + β) M + cpr M
    ΔRD_c           += (r_c − (ρ_c − β) p_c) M

p_c la part des chômeurs de la cellule, c61, c5, cch, cpr, r_c les coefficients de la
microsimulation sur W. Avec les coefficients du forfait (`forfait`), chaque correction
est nulle : le jumeau d'avant, au bit. Ce que la boucle ne touche pas : la part du
salaire de la masse (π D1 ŵ, au prorata du super-brut), la part de la population
active (la réponse de l'offre au salaire, au forfait β), les non-salariés (r_ns), les
emplois publics (D-418), les prestations indexées sur les prix (D-414), le choc
statique de la mesure (sa passe). L'IS sur les profits induits (`recettes_induites`) lit
l'EBE de `salaires`, qui porte la correction de q : un même PIB, partagé autrement.

LE POINT FIXE. La passe est linéaire en s : le total d'une grandeur sur la population
repondérée est Σ_h w_h [(1 − s) X_h + s X_h'], et ses écarts par personne-année ne
dépendent pas de s. Une passe donne donc les coefficients de toutes les itérations :
refaire la passe à l'emploi que le jumeau rend redonne les mêmes, au terme près des
ménages qui ont deux chômeurs (les deux transitions ensemble, d'ordre s², que
`interaction_paires` mesure) et des chômeurs tirés deux fois (s ≤ 1, loin du bord : le
jumeau crée au plus quelques centaines de milliers d'emplois pour 2,4 millions de
chômeurs). La boucle jumeau → population → jumeau se résout alors dans le jumeau, par le
point fixe de Gauss-Seidel du pas (CADRE.md §3), puisque les corrections sont écrites par
les blocs de la boucle simultanée. `emploi_impose` sert à la montrer itération par
itération : la correction lit un emploi donné, celui de l'itération d'avant, au lieu de
celui de l'état.

CE QUE LA BOUCLE NE FAIT PAS. Le signe : un emploi détruit est lu comme le miroir d'un
emploi créé (les mêmes personnes, à la marge), non comme la perte d'un emploi par un
salarié en poste. L'année : les coefficients d'une année de passe valent pour toute la
trajectoire, portés par W_k (la loi et la structure de l'année de la passe). Les
inactifs, la durée du chômage, la reprise à un salaire plus bas que celui d'avant.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from impots.jumeau.cellules import N_CELLULES, PRESTATIONS, TYPES

#: Le statut des chômeurs au sens du BIT dans la population (l'enquête Emploi).
CHOMEUR = "unemployed"
AGES = (15, 64)
GRAINE = 2028
#: Le préfixe des ménages variantes : un identifiant qui ne recoupe aucun autre.
PREFIXE = "B28:"
#: Les grandeurs par personne-année, dans l'ordre du rapport.
GRANDEURS = ("super_brut", "d61", "d5", "chomage", "prestations", "rd", "residu")


class BoucleError(ValueError):
    """Une boucle qui ne se lit pas ou qui ne se construit pas."""


def mois(masques: Any) -> np.ndarray:
    """Le nombre de mois travaillés d'un masque de douze bits (`mois_travailles`)."""
    m = np.asarray(masques, dtype=np.int64) & 0xFFF
    return np.array([bin(int(x)).count("1") for x in m], dtype=np.int64)


def taux_mensuels(frame: Any, graine: int = GRAINE) -> np.ndarray:
    """Le taux mensuel brut de chaque chômeur de `frame` quand il travaille (NaN pour les
    autres) : son salaire sur ses mois travaillés quand il en a un ; sinon celui d'un
    donneur tiré à graine fixe parmi les chômeurs qui en ont un, du même sexe et du même
    côté de 25 ans. Refusé si une case n'a aucun donneur."""
    statut = frame["statut_activite"].to_numpy()
    chomeur = statut == CHOMEUR
    salaire = frame["salaire_brut_annuel"].to_numpy().astype(float)
    m = mois(frame["mois_travailles"].to_numpy())
    propre = chomeur & (salaire > 0) & (m > 0)
    taux = np.full(len(statut), np.nan)
    taux[propre] = salaire[propre] / m[propre]
    sexe = frame["sex"].to_numpy()
    jeune = frame["age"].to_numpy() < 25
    rng = np.random.default_rng(graine)
    for s in np.unique(sexe[chomeur]):
        for j in (False, True):
            case = chomeur & (sexe == s) & (jeune == j)
            receveurs = np.flatnonzero(case & ~propre)
            if receveurs.size == 0:
                continue
            donneurs = np.flatnonzero(case & propre)
            if donneurs.size == 0:
                raise BoucleError(f"aucun donneur de salaire pour les chômeurs {s}, "
                                  f"{'moins' if j else 'plus'} de 25 ans")
            taux[receveurs] = taux[donneurs[rng.integers(0, donneurs.size,
                                                         receveurs.size)]]
    return taux


def variantes(frame: Any, graine: int = GRAINE, taux: Mapping[int, float] | None = None
              ) -> tuple[Any, Any]:
    """(les ménages variantes, les liens) : pour chaque chômeur de 15 à 64 ans de
    `frame`, une copie de son ménage où lui seul devient salarié douze mois sur douze, à
    son taux mensuel (`taux_mensuels`), sans allocation chômage. Les liens : l'identifiant
    du ménage variante, celui d'origine, la personne, ses personnes-années d'emploi
    gagnées (1 − m/12) et le salaire brut annuel de la variante. `taux` : le taux
    mensuel de chaque chômeur (par `person_id`), tiré sur une population plus grande que
    `frame` (un sous-échantillon a trop peu de donneurs) ; absent, tiré sur `frame`."""
    import polars as pl

    if taux is None:
        taux = taux_mensuels(frame, graine)
    else:
        taux = np.array([taux.get(int(p), np.nan) for p in frame["person_id"].to_list()])
    age = frame["age"].to_numpy()
    statut = frame["statut_activite"].to_numpy()
    candidats = np.flatnonzero((statut == CHOMEUR) & (age >= AGES[0]) & (age <= AGES[1]))
    if candidats.size == 0:
        raise BoucleError("aucun chômeur de 15 à 64 ans dans la population")
    pid = frame["person_id"].to_numpy()
    hid = frame["household_id"].to_numpy()
    m = mois(frame["mois_travailles"].to_numpy())
    salaire = frame["salaire_brut_annuel"].to_numpy().astype(float)
    base = int(pid.max()) + 1
    morceaux, liens = [], []
    par_menage = frame.with_row_index("_ligne").partition_by("household_id", as_dict=True)
    for rang, i in enumerate(candidats):
        menage = par_menage[(hid[i],)]
        tag = f"{PREFIXE}{pid[i]}:"
        lui = pl.col("person_id") == int(pid[i])
        annuel = 12.0 * float(taux[i])
        v = menage.with_columns(
            (pl.lit(tag) + pl.col("household_id")).alias("household_id"),
            (pl.lit(tag) + pl.col("foyer_id")).alias("foyer_id"),
            (pl.lit(tag) + pl.col("famille_id")).alias("famille_id"),
            (pl.col("person_id") + base * (rang + 1)).alias("person_id"),
            pl.when(lui).then(pl.lit("employed")).otherwise(pl.col("statut_activite"))
            .alias("statut_activite"),
            pl.when(lui).then(pl.lit(True)).otherwise(pl.col("is_salarie"))
            .alias("is_salarie"),
            pl.when(lui).then(pl.lit(annuel)).otherwise(pl.col("salaire_brut_annuel"))
            .alias("salaire_brut_annuel"),
            pl.when(lui).then(pl.lit(0.0)).otherwise(pl.col("chomage_annuel"))
            .alias("chomage_annuel"),
            pl.when(lui).then(pl.lit(0xFFF, dtype=pl.Int64))
            .otherwise(pl.col("mois_travailles")).alias("mois_travailles"),
        ).drop("_ligne")
        morceaux.append(v)
        gagne = 1.0 - (m[i] / 12.0 if salaire[i] > 0 else 0.0)
        liens.append({"household_id": f"{tag}{hid[i]}", "origine": str(hid[i]),
                      "person_id": int(pid[i]), "annees": gagne, "salaire_brut": annuel})
    return pl.concat(morceaux), pl.DataFrame(liens)


# --------------------------------------------------------------------------- #
# les coefficients
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Coefficients:
    """Par personne-année d'emploi gagnée, en part du super-brut moyen par salarié de la
    passe (W) : ce que la transition rend. `rd_cellules` somme à `rd`."""

    super_brut: float
    d61: float
    d5: float
    chomage: float
    prestations: float
    rd: float
    rd_cellules: np.ndarray
    annee: int | None = None
    meta: Mapping[str, Any] = field(default_factory=dict)
    emploi_impose: Mapping[int, float] | None = None
    """{année : ΔE salarié marchand, milliers} : la correction lit cet emploi au lieu de
    celui de l'état (l'itération d'avant, pour montrer le point fixe) ; absent, l'état."""

    def __post_init__(self) -> None:
        if np.shape(self.rd_cellules) != (N_CELLULES,):
            raise BoucleError(f"rd_cellules de forme {np.shape(self.rd_cellules)}")
        if abs(float(np.sum(self.rd_cellules)) - self.rd) > 1e-9 * max(1.0, abs(self.rd)):
            raise BoucleError("la répartition du revenu entre les cellules ne somme pas")


def _colonne(h: Any, nom: str, suffixe: str) -> np.ndarray:
    c = f"{nom}{suffixe}"
    if c not in h.columns:
        if suffixe and nom in h.columns:
            c = nom  # une colonne que la réforme ne change pas
        else:
            raise BoucleError(f"la passe n'a pas la colonne « {c} »")
    return h[c].to_numpy().astype(float)


def grandeurs_menage(h: Any, suffixe: str = "") -> dict[str, np.ndarray]:
    """Par ménage d'une passe (`RunResult.households`), les grandeurs de la boucle, en
    euros (recettes et prestations positives)."""
    sb = _colonne(h, "salaire_super_brut", suffixe)
    net = _colonne(h, "salaire_net", suffixe)
    csg = sum(_colonne(h, c, suffixe) for c in ("csg_deductible", "csg_imposable", "crds"))
    ir = _colonne(h, "ir", suffixe)
    csg_ch = _colonne(h, "csg_chomage", suffixe)
    ch = _colonne(h, "chomage_brut", suffixe)
    pr = sum(_colonne(h, c, suffixe) for c in PRESTATIONS if c in h.columns)
    rd = _colonne(h, "revenu_disponible", suffixe)
    return {"super_brut": sb, "d61": sb - net - csg, "d5": csg + ir + csg_ch,
            "chomage": ch, "prestations": pr, "rd": rd,
            # ce que le revenu disponible porte au-delà : il doit rester petit
            "residu": rd - (net - ir - csg_ch + ch + pr)}


def coefficients(originaux: Any, variants: Any, liens: Any, cellule: Mapping[str, int],
                 salaire_moyen: float, poids: Mapping[str, float], *,
                 suffixe: str = "", annee: int | None = None,
                 meta: Mapping[str, Any] | None = None) -> Coefficients:
    """Les coefficients d'une passe : `originaux` et `variants`, les ménages de la passe
    (`RunResult.households`, éventuellement la même table), `liens` (`variantes`),
    `cellule` la cellule (0 à 49) de chaque ménage d'origine, `salaire_moyen` le
    super-brut moyen par salarié de la passe (W), `poids` le poids de chaque ménage
    d'origine. `suffixe` : « _reform » pour lire le monde de la réforme."""
    def table(h: Any) -> dict[str, dict[str, float]]:
        g = grandeurs_menage(h, suffixe)
        ids = h["household_id"].to_list()
        return {k: dict(zip(ids, v.tolist(), strict=True)) for k, v in g.items()}

    o, v = table(originaux), table(variants)
    lv = liens["household_id"].to_list()
    lo = liens["origine"].to_list()
    an = liens["annees"].to_numpy().astype(float)
    w = np.array([poids[x] for x in lo], dtype=float)
    emplois = float((w * an).sum())
    if emplois <= 0:
        raise BoucleError("aucune personne-année d'emploi gagnée")
    out: dict[str, float] = {}
    ecarts: dict[str, np.ndarray] = {}
    for k in GRANDEURS:
        d = np.array([v[k][a] - o[k][b] for a, b in zip(lv, lo, strict=True)])
        ecarts[k] = d
        out[k] = float((w * d).sum()) / emplois / salaire_moyen
    c = np.array([cellule[b] for b in lo], dtype=int)
    rd_c = np.bincount(c, weights=w * ecarts["rd"], minlength=N_CELLULES) / emplois \
        / salaire_moyen
    rd_c = rd_c + (out["rd"] - rd_c.sum()) / N_CELLULES  # l'arrondi seul
    info = dict(meta or {})
    info.update(transitions=len(lv), emplois_personnes_annees=emplois,
                salaire_moyen=salaire_moyen, residu=out["residu"],
                salaire_brut_embauche=float((w * liens["salaire_brut"].to_numpy()).sum()
                                            / w.sum()))
    return Coefficients(super_brut=out["super_brut"], d61=out["d61"], d5=out["d5"],
                        chomage=out["chomage"], prestations=out["prestations"],
                        rd=out["rd"], rd_cellules=rd_c, annee=annee, meta=info)


def interaction_paires(originaux: Any, seuls: Any, ensemble: Any, suffixe: str = ""
                       ) -> dict[str, float]:
    """Le terme d'ordre s² d'un ménage à deux chômeurs : X(les deux) − X(l'un) − X(l'autre)
    + X(aucun), sommé, contre la somme des deux écarts seuls. `seuls` : {origine : (X(a),
    X(b))} ; `ensemble`, `originaux` : {origine : X}."""
    inter = sum(ensemble[h] - a - b + originaux[h] for h, (a, b) in seuls.items())
    simple = sum(a + b - 2 * originaux[h] for h, (a, b) in seuls.items())
    return {"interaction": float(inter), "seuls": float(simple)}


def forfait(st: Any, annee: int | None = None) -> Coefficients:
    """Les coefficients que le jumeau porte sans la boucle (`blocs.menages.Structure`) :
    avec eux, chaque correction est nulle."""
    p = np.asarray(st.part_chomeurs, dtype=float)
    beta = float(st.allocation_sur_salaire)
    rd_c = (np.asarray(st.rho, dtype=float) - beta) * p
    return Coefficients(super_brut=1.0, d61=float(p @ st.taux_d61), d5=float(p @ st.taux_d5),
                        chomage=-beta, prestations=0.0, rd=float(rd_c.sum()),
                        rd_cellules=rd_c, annee=annee, meta={"forfait": True})


def masse(coef: Coefficients, annee: int, emploi_etat: Any, emploi_marchand: float,
          pi_d1: Any) -> np.ndarray:
    """M, la masse de l'emploi salarié marchand de la mesure, Md€ : π D1 ê, ê celui de
    l'état, ou celui que la boucle impose (`emploi_impose`, en milliers)."""
    if coef.emploi_impose is not None:
        e = float(coef.emploi_impose.get(annee, 0.0)) / emploi_marchand
        return np.asarray(pi_d1, dtype=float) * e
    return np.asarray(pi_d1, dtype=float) * np.asarray(emploi_etat, dtype=float)


def corrections(coef: Coefficients, st: Any, m: Any) -> dict[str, Any]:
    """Ce que la boucle ajoute au jumeau pour la masse M (Md€, forme (n,)) : l'écart
    entre la microsimulation et le forfait des cellules, champ par champ ; « rd » est de
    forme (50, n)."""
    f = forfait(st)
    m = np.asarray(m, dtype=float)
    return {
        "remunerations": (coef.super_brut - f.super_brut) * m,
        "apu_r_d61": (coef.d61 - f.d61) * m,
        "apu_r_d5": (coef.d5 - f.d5) * m,
        "apu_d_d62": ((coef.chomage - f.chomage) + (coef.prestations - f.prestations)) * m,
        "rd": np.outer(np.asarray(coef.rd_cellules) - f.rd_cellules, m),
    }


def cellules_de(h: Any, frame: Any) -> dict[str, int]:
    """La cellule (décile de niveau de vie de la passe × type) de chaque ménage d'une
    passe de référence, comme `cellules.construire` la range."""
    from impots.jumeau.cellules import types_menages
    from impots.population.aggregate import consumption_units, weighted_decile_index

    t = h.join(types_menages(frame), on="household_id", how="left")
    if t["type"].null_count():
        raise BoucleError("des ménages de la passe sans type")
    uc = consumption_units(t["n_aged_14_plus"].to_numpy(), t["n_children_under_14"].to_numpy())
    d = weighted_decile_index(t["revenu_disponible"].to_numpy().astype(float) / uc,
                              t["weight"].to_numpy().astype(float))
    c = d * len(TYPES) + np.array([TYPES.index(x) for x in t["type"]])
    return dict(zip(t["household_id"].to_list(), c.tolist(), strict=True))


__all__ = ["Coefficients", "coefficients", "corrections", "forfait", "masse", "variantes"]
