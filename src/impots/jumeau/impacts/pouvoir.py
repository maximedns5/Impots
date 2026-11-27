"""Le pouvoir d'achat : ce qu'une mesure change au revenu réel des ménages (but 29, D-591).

LA QUESTION. Une fois les prix passés, les ménages ont-ils plus ou moins de quoi vivre, et
lesquels ? Pour chaque année de la trajectoire et chaque cellule de ménages (décile de
niveau de vie × type de ménage, `jumeau.cellules`), l'écart du revenu disponible que la
variante apporte à la référence, en euros par unité de consommation et en %, nominal
puis réel.

LA CHAÎNE, cellule c, année k, sur les blocs des ménages (`blocs.menages`, D-409, D-414) :

    ΔRD_c,k        le choc statique de la mesure sur le décile (sa passe sur la
                   population), réparti au prorata des ménages, plus l'emploi, les salaires
                   et les allocations chômage que la dynamique apporte
                   (`gagnants.gagnants_perdants`, `menages.revenus_cellules`) ;
    I_c,k = p̂c_k P_c Y_k / Y_0    les pensions et prestations indexées sur le prix de la
                   consommation (Mésange, p. 100 ; le bloc `consommation` les verse) ;
    ΔRD^nom = ΔRD + I                                le gain nominal ;
    R_c,k = p̂c_k RD_c Y_k / Y_0    ce que la hausse des prix reprend : le revenu de
                   référence au prix plus haut de la consommation ;
    ΔRD^réel = ΔRD^nom − R           le gain réel, au premier ordre, comme le modèle.

p̂c est l'écart du prix de la consommation des ménages à la référence
(`ecart_prix_consommation`, le bloc `commerce`, l'équation (PC) de Mésange, p. 24), somme
des mesures ; nul (absent) hors du mode structurel. RD_c, P_c, les cellules de 2024
rapportées au PIB de 2024, fois le PIB de la référence de l'année (`menages.structure`),
comme le bloc `consommation`. Les euros sont ensuite ramenés aux prix de l'année de départ
par le déflateur de la consommation de la référence (`prix_c_menages`, chaîné) : un euro
« de 2025 ».

CE QUE RENDENT LES CELLULES, ET CE QU'ELLES NE RENDENT PAS. Une cellule n'a pas de
distribution interne : ses ménages gagnent tous autant. La part des gagnants est celle des
ménages des cellules dont le gain réel par ménage dépasse le seuil des rapports
(`gagnants.SEUIL`, 10 € par an). Un « cas type » est une cellule nommée (un décile, un
type) : pas un ménage-type au sens des barèmes, son revenu moyen.

LES BANDES. Une trajectoire calculée sur un axe de tirages (le tirage 0 au réglage, les
suivants tirés des lois de θ du navigateur, `trajectoire_tiree`) donne à chaque nombre
sa bande, les quantiles de 5 et 95 % des tirages ; un seul tirage, pas de bande, et la
dimension le dit.

Ce module tourne dans le navigateur (D-415) : numpy seulement.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np

from impots.jumeau.cellules import N_DECILES, TYPES
from impots.jumeau.impacts import Dimension, Indicateur, Source, inscrire

#: Les libellés des types de ménages, dans l'ordre de `cellules.TYPES`.
LIBELLES_TYPES = {
    "seul": "Personnes seules", "monoparentale": "Familles monoparentales",
    "couple_sans_enfant": "Couples sans enfant", "couple_avec_enfants": "Couples avec enfants",
    "complexe": "Ménages complexes",
}
#: Les cas types : des cellules nommées (décile de 1 à 10, type).
CAS_TYPES = (
    ("Personne seule modeste (D2)", 2, "seul"),
    ("Famille monoparentale modeste (D2)", 2, "monoparentale"),
    ("Couple avec enfants, niveau de vie médian (D5)", 5, "couple_avec_enfants"),
    ("Personne seule, niveau de vie médian (D5)", 5, "seul"),
    ("Couple sans enfant aisé (D9)", 9, "couple_sans_enfant"),
    ("Couple avec enfants aisé (D9)", 9, "couple_avec_enfants"),
)
#: Les quantiles de la bande, en %.
BANDE = (5.0, 95.0)

SOURCES = (
    Source("Insee, Mésange (document de travail G2017-04)", "p. 24, équation (PC) ; p. 100",
           "le prix de la consommation des ménages ; l'indexation des prestations sur lui"),
    Source("Cellules de ménages du jumeau (D-409), population de D-553",
           "`data/processed/jumeau_cellules_2024.json`, passe OpenFisca de 2024",
           "le revenu disponible, les pensions et prestations, les unités de consommation "
           "de chaque cellule (échelle de l'OCDE modifiée)"),
    Source("Les rapports des études (passe OpenFisca de la première année)",
           "`deciles` de la passe des ménages, mean_delta × n_households",
           "le choc statique de la mesure sur chaque décile"),
)
LIMITES = (
    "Une cellule n'a pas de distribution interne : tous ses ménages gagnent ou perdent "
    "autant ; la part des gagnants est celle des ménages des cellules qui gagnent.",
    "Le choc statique d'une mesure vient par décile et se répartit entre les types du "
    "décile au prorata de leurs ménages : une mesure ciblée sur un type (les familles, "
    "les retraités) n'est pas vue comme telle à l'intérieur du décile.",
    "Le gain réel est au premier ordre (ΔRD − p̂c RD), comme le modèle ; le prix est celui "
    "de la consommation moyenne des ménages, le même pour toutes les cellules.",
    "Hors du mode structurel, ni la dynamique (emploi, salaires) ni les prix : le gain est "
    "le choc statique seul.",
    "Le gain par type de ménage dépend de la clé qui répartit le choc d'un décile entre "
    "ses types (le rapport ne le dit pas) : les ménages pour le modèle ; les bornes sous "
    "deux autres clés (les UC, le revenu) sont dans les notes.",
)


# --------------------------------------------------------------------------- #
# la trajectoire
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Chemin:
    """Ce que la dimension lit d'une trajectoire."""

    annees: tuple[int, ...]
    reference: tuple[Any, ...]
    variante: tuple[Any, ...]
    mesures: tuple[Any, ...]


def chemin(variante: Any, reference: Any = None, mesures: Sequence[Any] | None = None,
           annees: Sequence[int] | None = None) -> Chemin:
    """Une `Trajectoire` (en `variante`), ou les deux suites d'états et les mesures."""
    if hasattr(variante, "variante") and hasattr(variante, "reference"):
        t = variante
        return Chemin(tuple(t.annees), tuple(t.reference), tuple(t.variante),
                      tuple(t.mesures))
    if reference is None or mesures is None:
        raise ValueError("pouvoir d'achat : une trajectoire, ou la variante, la référence "
                         "et les mesures")
    var, ref = tuple(variante), tuple(reference)
    ans = tuple(annees) if annees is not None else tuple(e.annee for e in var)
    return Chemin(ans, ref, var, tuple(mesures))


def _somme_mesures(etat: Any, champ: str) -> np.ndarray:
    if not etat.present(champ):
        return np.zeros(etat.n)
    parts = etat.par_mesure(champ)
    total = np.zeros(etat.n)
    for m, v in parts.items():
        if m:
            total = total + np.asarray(v, dtype=float)
    return total


# --------------------------------------------------------------------------- #
# le revenu des cellules
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Revenus:
    """Les revenus des cinquante cellules, année par année et tirage par tirage.

    Les montants sont en Md€ courants, de forme (années, 50, tirages) ; `prix` est p̂c,
    (années, tirages) ; `deflateur` le prix de la consommation de la référence, chaîné
    depuis l'année de départ (= 1), (années, tirages)."""

    annees: tuple[int, ...]
    menages: np.ndarray
    personnes: np.ndarray
    uc: np.ndarray
    rd_ref: np.ndarray
    dynamique: np.ndarray
    """ΔRD : le choc statique et la dynamique (emploi, salaires, chômage)."""
    indexation: np.ndarray
    reprise: np.ndarray
    prix: np.ndarray
    deflateur: np.ndarray
    structurel: bool
    """La trajectoire porte-t-elle les blocs des ménages (la dynamique, les prix) ?"""

    @property
    def nominal(self) -> np.ndarray:
        return self.dynamique + self.indexation

    @property
    def reel(self) -> np.ndarray:
        return self.nominal - self.reprise

    @property
    def n(self) -> int:
        return int(self.rd_ref.shape[2])


def revenus(traj: Any, depart: Any, cellules: Any, params: Any = None) -> Revenus:
    """Les revenus des cellules sur une trajectoire (une `Trajectoire` ou un `Chemin`)."""
    from impots.jumeau.blocs.menages import charger, structure
    from impots.jumeau.gagnants import gagnants_perdants

    c = traj if isinstance(traj, Chemin) else chemin(traj)
    params = params if params is not None else charger()
    st = structure(cellules, params.pib_cellules)
    g = gagnants_perdants(c, depart, cellules, params)
    n = c.variante[0].n
    pib = np.stack([np.broadcast_to(np.asarray(e["pib"], dtype=float), (n,))
                    for e in c.reference])                               # (A, n)
    rd_ref = st.rd_pib[None, :, None] * pib[:, None, :]
    prest = st.prestations_pib[None, :, None] * pib[:, None, :]
    pc = np.stack([_somme_mesures(e, "ecart_prix_consommation") for e in c.variante])
    prix_ref = np.stack([
        np.broadcast_to(np.asarray(e["prix_c_menages"], dtype=float), (n,))
        if e.present("prix_c_menages") else np.ones(n) for e in c.reference])
    structurel = any(e.present("ecart_prix_consommation") for e in c.variante)
    return Revenus(
        annees=c.annees, menages=np.asarray(cellules["menages"], dtype=float),
        personnes=np.asarray(cellules["personnes"], dtype=float),
        uc=np.asarray(cellules["uc"], dtype=float), rd_ref=rd_ref,
        dynamique=np.asarray(g.ecart_md, dtype=float), indexation=prest * pc[:, None, :],
        reprise=rd_ref * pc[:, None, :], prix=pc, deflateur=np.cumprod(prix_ref, axis=0),
        structurel=bool(structurel))


# --------------------------------------------------------------------------- #
# les groupes
# --------------------------------------------------------------------------- #
def groupes() -> dict[str, np.ndarray]:
    """Les groupes de cellules, en indicatrices (50,) : l'ensemble, chaque décile, chaque
    type et chaque cas type."""
    dec = np.repeat(np.arange(N_DECILES), len(TYPES))
    typ = np.tile(np.arange(len(TYPES)), N_DECILES)
    out: dict[str, np.ndarray] = {"Ensemble": np.ones(dec.size)}
    for d in range(N_DECILES):
        out[f"D{d + 1}"] = (dec == d).astype(float)
    for i, t in enumerate(TYPES):
        out[LIBELLES_TYPES[t]] = (typ == i).astype(float)
    for nom, d, t in CAS_TYPES:
        out[nom] = ((dec == d - 1) & (typ == TYPES.index(t))).astype(float)
    return out


def par_uc(montant: np.ndarray, uc: np.ndarray, indic: np.ndarray) -> np.ndarray:
    """€ par unité de consommation et par an d'un groupe : (années, tirages)."""
    return np.einsum("akn,k->an", montant, indic) * 1e9 / float((uc * indic).sum())


def en_part(montant: np.ndarray, base: np.ndarray, indic: np.ndarray) -> np.ndarray:
    """En % de la base du groupe : (années, tirages)."""
    return 100.0 * np.einsum("akn,k->an", montant, indic) / np.einsum("akn,k->an", base,
                                                                         indic)


def bande(x: np.ndarray, debut: int | None) -> tuple[np.ndarray, np.ndarray | None,
                                                      np.ndarray | None]:
    """(valeur au tirage 0, bas, haut) d'une série (années, tirages) ; la bande, les
    quantiles de 5 et 95 % des tirages `debut:`, s'il y en a au moins deux."""
    x = np.asarray(x, dtype=float)
    if debut is None or x.shape[1] - debut < 2:
        return x[:, 0], None, None
    q = np.percentile(x[:, debut:], BANDE, axis=1)
    return x[:, 0], q[0], q[1]


def _indicateur(cle: str, libelle: str, unite: str, series: Mapping[str, np.ndarray],
                debut: int | None, sens: int = 1, principal: str = "Ensemble"
                ) -> Indicateur:
    v, b, h = bande(series[principal], debut)
    return Indicateur(cle=cle, libelle=libelle, unite=unite, valeurs=v, bas=b, haut=h,
                      par_groupe={g: s[:, 0] for g, s in series.items()}, sens=sens)


def _debut(n: int, options: Mapping[str, Any]) -> int | None:
    if "tirages_depuis" in options:
        return options["tirages_depuis"]
    return 1 if n > 2 or (n == 2 and options.get("tirages") is not None) else None


# --------------------------------------------------------------------------- #
# la dimension
# --------------------------------------------------------------------------- #
def tableaux(r: Revenus) -> dict[str, dict[str, np.ndarray]]:
    """Les séries de la dimension, par groupe : chaque valeur (années, tirages)."""
    gs = groupes()
    euros_depart = 1.0 / r.deflateur
    out: dict[str, dict[str, np.ndarray]] = {
        "reel_uc": {}, "reel_pct": {}, "nominal_uc": {}, "reprise_uc": {},
        "gagnants": {}, "perdants": {}}
    from impots.jumeau.gagnants import SEUIL

    par_menage = r.reel * 1e9 / r.menages[None, :, None]
    for nom, ind in gs.items():
        out["reel_uc"][nom] = par_uc(r.reel, r.uc, ind) * euros_depart
        out["nominal_uc"][nom] = par_uc(r.dynamique, r.uc, ind) * euros_depart
        out["reprise_uc"][nom] = par_uc(r.reprise - r.indexation, r.uc, ind) * euros_depart
        out["reel_pct"][nom] = en_part(r.reel, r.rd_ref, ind)
        m = r.menages * ind
        out["gagnants"][nom] = 100.0 * np.einsum("akn,k->an", (par_menage > SEUIL) * 1.0,
                                                 m) / m.sum()
        out["perdants"][nom] = 100.0 * np.einsum("akn,k->an", (par_menage < -SEUIL) * 1.0,
                                                 m) / m.sum()
    return out


@inscrire("pouvoir_achat")
def pouvoir_achat(variante: Any, reference: Any, depart: Any, cellules: Any,
                  **options: Any) -> Dimension:
    """Le pouvoir d'achat, par décile, par type de ménage et par cas type, année par année.

    `variante` : une `Trajectoire`, ou la suite des états de la variante (alors
    `reference` est celle de la référence et `options["mesures"]` les mesures).
    `options["tirages_depuis"]` : le premier tirage des lois de θ (1 par défaut s'il y a
    plus de deux tirages) ; None, pas de bande."""
    r, mesures = revenus_de(variante, reference, depart, cellules, options)
    debut = _debut(r.n, options)
    t = tableaux(r)
    an = depart.annee if hasattr(depart, "annee") else options.get("annee_euros", "départ")
    euros = f"€ de {an} par UC et par an"
    indicateurs = (
        _indicateur("reel_uc", "Gain de revenu disponible réel, par unité de consommation",
                    euros, t["reel_uc"], debut),
        _indicateur("reel_pct", "Gain de revenu disponible réel", "% du revenu disponible",
                    t["reel_pct"], debut),
        _indicateur("nominal_uc", "Gain nominal, avant les prix", euros,
                    t["nominal_uc"], debut),
        _indicateur("reprise_uc", "Ce que la hausse des prix reprend du gain nominal, net "
                    "de l'indexation des pensions et prestations", euros, t["reprise_uc"],
                    debut, sens=-1),
        _indicateur("gagnants", "Ménages gagnants (gain réel de plus de 10 € par an)",
                    "% des ménages", t["gagnants"], debut, sens=0),
        _indicateur("perdants", "Ménages perdants (perte réelle de plus de 10 € par an)",
                    "% des ménages", t["perdants"], debut, sens=0),
    )
    limites = list(LIMITES)
    bornes = bornes_types(r, cellules, mesures) if mesures else None
    if not r.structurel:
        limites.insert(0, "Cette trajectoire ne porte pas la boucle prix-salaires : le gain "
                          "réel est le gain nominal, sans prix ni dynamique des prix.")
    if debut is None:
        limites.append("Un seul réglage de θ : pas de bande. Les bandes viennent des tirages "
                       "des lois de θ du navigateur (`trajectoire_tiree`).")
    juge = options.get("juge_pouvoir")
    return Dimension(
        cle="pouvoir_achat", titre="Le pouvoir d'achat",
        question="Une fois les prix passés, les ménages ont-ils plus ou moins de quoi "
                 "vivre, et lesquels ?",
        annees=r.annees, indicateurs=indicateurs,
        statut="jugé" if juge else "sourcé, non jugé", sources=SOURCES,
        limites=tuple(limites), juge=juge,
        notes={"seuil_gagnant_euros": 10.0, "structurel": r.structurel,
               "tirages": r.n, "tirages_depuis": debut,
               "types_bornes_repartition": bornes,
               "prix_consommation_pct": [float(x) for x in 100.0 * r.prix[:, 0]],
               "cas_types": [{"nom": n_, "decile": d, "type": ty} for n_, d, ty in CAS_TYPES],
               "cellules_uc": {f"D{k // len(TYPES) + 1}·{TYPES[k % len(TYPES)]}":
                               [float(x) for x in r.reel[:, k, 0] * 1e9 / r.uc[k]
                                / r.deflateur[:, 0]] for k in range(r.uc.size)}})


# --------------------------------------------------------------------------- #
# le choc statique : sa répartition entre les types d'un décile, un chemin sans jumeau
# --------------------------------------------------------------------------- #
#: Les clés de répartition du choc statique d'un décile entre ses cellules : celle du
#: modèle (les ménages, `menages.revenus_cellules`), et deux autres, pour borner ce que la
#: clé fait au gain par type (le rapport ne dit pas qui, dans le décile, gagne).
REPARTITIONS = {"menages": "au prorata des ménages (le modèle)",
                "uc": "au prorata des unités de consommation",
                "revenu_disponible": "au prorata du revenu disponible"}


def repartir(choc: Sequence[float], cellules: Any, cle: str = "menages") -> np.ndarray:
    """Le choc d'un décile (10 Md€) réparti entre ses cellules (50,), selon `cle`."""
    poids = np.asarray(cellules[cle], dtype=float)
    dec = np.repeat(np.arange(N_DECILES), len(TYPES))
    par_decile = np.bincount(dec, weights=poids, minlength=N_DECILES)
    return np.asarray(choc, dtype=float)[dec] * poids / par_decile[dec]


def _chocs(mesures: Sequence[Any], annees: Sequence[int]) -> np.ndarray:
    """La somme des chocs par décile des mesures, (années, 10) Md€."""
    from impots.jumeau.blocs.menages import choc_menages

    out = np.zeros((len(annees), N_DECILES))
    for k, a in enumerate(annees):
        for m in mesures:
            d = choc_menages(m, a).get("deciles")
            if d is not None:
                out[k] += np.asarray(d, dtype=float)
    return out


def bornes_types(r: Revenus, cellules: Any, mesures: Sequence[Any]
                 ) -> dict[str, dict[str, list[float]]]:
    """Le gain réel par UC de chaque type (€ de l'année de départ, tirage 0), sous chaque
    clé de répartition du choc statique : {type : {clé : [années]}}."""
    chocs = _chocs(mesures, r.annees)
    modele = np.stack([repartir(x, cellules, "menages") for x in chocs])
    out: dict[str, dict[str, list[float]]] = {}
    typ = np.tile(np.arange(len(TYPES)), N_DECILES)
    for cle in REPARTITIONS:
        autre = np.stack([repartir(x, cellules, cle) for x in chocs])
        reel = r.reel[:, :, 0] - modele + autre
        for i, t in enumerate(TYPES):
            s = typ == i
            v = reel[:, s].sum(axis=1) * 1e9 / r.uc[s].sum() / r.deflateur[:, 0]
            out.setdefault(LIBELLES_TYPES[t], {})[cle] = [float(x) for x in v]
    return out


@dataclass(frozen=True)
class Statique:
    """Une mesure sans trajectoire : ses chocs par décile, année par année (Md€, gain des
    ménages positif), lus sur la passe de son rapport. Ce que `revenus_statiques` lit."""

    identifiant: str
    menages: Mapping[int, Mapping[str, Any]]


def revenus_statiques(chocs: Mapping[int, Sequence[float]], cellules: Any,
                      params: Any = None) -> tuple[Revenus, list[Statique]]:
    """Les revenus des cellules sous le seul choc statique (pas de dynamique, pas de prix),
    aux revenus des cellules : pour une mesure que le mode structurel refuse."""
    annees = tuple(sorted(chocs))
    mesure = Statique("statique", {a: {"deciles": list(chocs[a])} for a in annees})
    dyn = np.stack([repartir(chocs[a], cellules) for a in annees])[:, :, None]
    rd = np.asarray(cellules["revenu_disponible"], dtype=float) / 1e9
    a_ = len(annees)
    zero = np.zeros((a_, rd.size, 1))
    return Revenus(annees=annees, menages=np.asarray(cellules["menages"], dtype=float),
                   personnes=np.asarray(cellules["personnes"], dtype=float),
                   uc=np.asarray(cellules["uc"], dtype=float),
                   rd_ref=np.broadcast_to(rd[None, :, None], (a_, rd.size, 1)).copy(),
                   dynamique=dyn, indexation=zero, reprise=zero, prix=np.zeros((a_, 1)),
                   deflateur=np.ones((a_, 1)), structurel=False), [mesure]


def chocs_du_rapport(premiere_annee: Mapping[str, Any]) -> dict[int, list[float]]:
    """Le choc par décile de la passe des ménages d'un rapport de première année (Md€),
    même quand le jumeau ne le lit pas (une réforme du Smic, D-412) : le gain statique."""
    from impots.jumeau.blocs.menages import menages_depuis_deciles
    from impots.jumeau.mesures import _passes

    passes = _passes(premiere_annee)
    if "menages" not in passes or not passes["menages"]["reponse"].get("deciles"):
        raise ValueError("le rapport n'a pas de passe des ménages par décile")
    annee = int(passes["menages"]["requete"]["year"])
    return {annee: menages_depuis_deciles(passes["menages"]["reponse"]["deciles"])}


def revenus_de(variante: Any, reference: Any, depart: Any, cellules: Any,
               options: Mapping[str, Any]) -> tuple[Revenus, Sequence[Any]]:
    """Les revenus d'une trajectoire, ou ceux que `options["revenus"]` donne (un couple
    (Revenus, mesures) de `revenus_statiques`)."""
    if options.get("revenus") is not None:
        r, mesures = options["revenus"]
        return r, mesures
    cs = chemins(variante, reference, options)
    r = joindre([revenus(c, depart, cellules, options.get("params")) for c in cs])
    return r, cs[0].mesures


def chemins(variante: Any, reference: Any, options: Mapping[str, Any]) -> list[Chemin]:
    """Le chemin au réglage, puis, si le tableau en donne (`options["tirages"]`, la même
    trajectoire vectorisée sur les tirages des θ, D-605), celui des tirages : le tirage 0
    est le réglage, les suivants font la bande (`tirages_depuis` = 1)."""
    cs = [chemin(variante, reference, options.get("mesures"), options.get("annees"))]
    t = options.get("tirages")
    if (t is not None and hasattr(t, "variante") and hasattr(t, "reference")
            and len(t.annees) == len(cs[0].annees)):
        cs.append(chemin(t))
    return cs


def joindre(rs: Sequence[Revenus]) -> Revenus:
    """Les revenus de plusieurs chemins, mis bout à bout sur l'axe des tirages."""
    if len(rs) == 1:
        return rs[0]
    a = rs[0]

    def cat(champ: str) -> np.ndarray:
        x = [np.asarray(getattr(r, champ)) for r in rs]
        return np.concatenate(x, axis=x[0].ndim - 1)

    return Revenus(annees=a.annees, menages=a.menages, personnes=a.personnes, uc=a.uc,
                   rd_ref=cat("rd_ref"), dynamique=cat("dynamique"),
                   indexation=cat("indexation"), reprise=cat("reprise"), prix=cat("prix"),
                   deflateur=cat("deflateur"), structurel=a.structurel)


# --------------------------------------------------------------------------- #
# les tirages des lois de θ, pour les bandes
# --------------------------------------------------------------------------- #
def trajectoire_tiree(session: Any, choix: Mapping[str, Any], tirages: int = 200,
                      graine: int | None = None) -> tuple[Any, Any, str | None]:
    """La trajectoire d'un réglage du navigateur sur un axe de tirages : le tirage 0 au
    réglage (`choix["theta"]`), les `tirages` suivants tirés ensemble des lois de θ
    (`navigateur.loi_de`, D-424, D-438), comme `Session.portee` sans les points des
    boîtes. Rend (trajectoire, départ, refus)."""
    from impots.jumeau import navigateur

    graine = navigateur.GRAINE if graine is None else graine
    ctx = session._contexte(choix)
    lus = [t for t in ctx["registre"] if t["lu"]]
    manque = [t["cle"] for t in lus if t["cle"] not in ctx["theta"]]
    if manque:
        raise navigateur.NavigateurError(f"θ sans réglage : {manque}")
    rng = np.random.default_rng(graine)
    theta = {t["cle"]: np.concatenate([[ctx["theta"][t["cle"]]], navigateur._tirer(
        navigateur.loi_de(t["cle"]), tirages, rng)]) for t in lus}
    traj, refus = session._derouler(ctx, theta)
    return traj, ctx["depart"], refus


__all__ = ["CAS_TYPES", "Chemin", "Revenus", "Statique", "bornes_types", "chemin",
           "chocs_du_rapport", "groupes", "pouvoir_achat", "repartir", "revenus",
           "revenus_de", "revenus_statiques", "trajectoire_tiree"]
