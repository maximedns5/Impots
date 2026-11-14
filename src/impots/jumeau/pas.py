"""Le pas annuel (CADRE.md §3) : entrées, blocs, point fixe, fermeture des comptes,
identités.

`pas(etat_prec, ...) -> etat_t` :

1. les ENTRÉES exogènes de l'année (`Entrees`) : croissance réelle et prix, règle de
   dépense, taux de la dette de référence et taux marginal, nommés comme `dette.scenarios`
   les nomme ;
2. les CHOCS STATIQUES des mesures s'inscrivent sur leurs champs : c'est le bloc
   `mesures`, qui tourne avant ceux qui les lisent ;
3. les BLOCS tournent dans l'ordre du `Modele`. Une boucle simultanée, déclarée comme
   telle, se résout par point fixe de Gauss-Seidel : tolérance 1e-10 en relatif, 100
   itérations au plus ; sinon le pas refuse en nommant le bloc et le champ ;
4. le CADRE FERME LES COMPTES, et lui seul (`fermer`) : les recettes et les dépenses
   primaires, les intérêts nets aux taux du scénario, B9, le solde primaire, la dette
   d'ouverture et de fin d'année, le ratio, le taux implicite, la croissance du PIB en
   volume chaînée ;
5. les IDENTITÉS sont vérifiées (`identites.verifier`), continuité de la dette comprise.

LES INTÉRÊTS, PAR ORIGINE. La dette de fin d'année se décompose par (origine, mesure)
comme tout champ additif. La part de référence (le départ publié et la trajectoire de
`tendance`) est chargée au taux de référence de l'année ; toute autre part, la dette
qu'ajoutent les mesures, au taux marginal du scénario : c'est `chaine.run`, où la dette
ajoutée suit ΔD_t = ΔD_{t−1}(1 + m) + Δcoût_t. Chaque mesure porte ainsi les intérêts de
sa propre dette, et la décomposition de Δb se somme sans reste.

Le pas ne lit aucun fichier et n'utilise ni pandas ni OpenFisca.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

import numpy as np

from impots.jumeau import identites
from impots.jumeau.champs import DEPENSES, EMPLOIS_EN_VOLUME, FERMES, RECETTES, REGISTRE
from impots.jumeau.champs import champ as definition
from impots.jumeau.etat import ChampAbsent, Cle, Etat

#: Les origines dont la dette se charge au taux de référence.
ORIGINES_REFERENCE = frozenset({"depart", "publie", "tendance"})
TOLERANCE_POINT_FIXE = 1e-10
ITERATIONS_MAX = 100
REGLES = ("part_pib_constante", "gele_en_volume", "personnalise")


class PasError(ValueError):
    """Un pas, ou un modèle, que le cadre refuse."""


class NonConvergence(PasError):
    """Le point fixe d'une boucle ne converge pas."""


# --------------------------------------------------------------------------- #
# les entrées exogènes
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Entrees:
    """Les scénarios nommés, une valeur par année de la trajectoire."""

    annees: tuple[int, ...]
    croissance_reelle: tuple[float, ...]
    prix: tuple[float, ...]
    regle_depense: str
    croissance_depense: float | None
    taux_reference: tuple[float, ...]
    taux_marginal: float
    noms: Mapping[str, str]

    def __post_init__(self) -> None:
        k = len(self.annees)
        for nom, serie in (("croissance réelle", self.croissance_reelle),
                           ("prix", self.prix), ("taux de référence", self.taux_reference)):
            if len(serie) != k:
                raise PasError(f"{nom} : {len(serie)} valeurs pour {k} années")
        if self.regle_depense not in REGLES:
            raise PasError(f"règle de dépense « {self.regle_depense} » inconnue")
        if self.regle_depense == "personnalise" and self.croissance_depense is None:
            raise PasError("règle « personnalise » sans croissance de la dépense")

    def nominale(self, k: int) -> float:
        return (1.0 + self.croissance_reelle[k]) * (1.0 + self.prix[k]) - 1.0

    def facteur_depense(self, k: int) -> float:
        """s_t / s_{t−1}, la règle de `dette.reference`."""
        nominale = self.nominale(k)
        if self.regle_depense == "part_pib_constante":
            return 1.0
        if self.regle_depense == "gele_en_volume":
            return (1.0 + self.prix[k]) / (1.0 + nominale)
        return (1.0 + float(self.croissance_depense)) / (1.0 + nominale)

    @classmethod
    def depuis_rejeu(cls, rejeu: Mapping[str, Any], annees: Sequence[int]) -> Entrees:
        """Les scénarios qu'un rapport porte (`rejeu.cadre`, D-336)."""
        cadre = rejeu["cadre"]
        k = len(annees)
        taux = [float(t) for t in cadre["taux"]["reference"]]
        if len(taux) < k:
            raise PasError(f"le rapport porte {len(taux)} taux pour {k} années")
        return cls(annees=tuple(annees),
                   croissance_reelle=(float(cadre["growth"]["real"]),) * k,
                   prix=(float(cadre["growth"]["prices"]),) * k,
                   regle_depense=cadre["spending"]["rule"],
                   croissance_depense=cadre["spending"].get("growth"),
                   taux_reference=tuple(taux[:k]),
                   taux_marginal=float(cadre["taux"]["marginal"]),
                   noms={"taux": cadre["taux"]["kind"]})


# --------------------------------------------------------------------------- #
# les blocs et le modèle
# --------------------------------------------------------------------------- #
class Bloc(Protocol):
    nom: str
    lit: tuple[str, ...]
    ecrit: tuple[str, ...]
    thetas: tuple[str, ...]

    def contribue(self, ctx: Contexte) -> Mapping[str, Mapping[str, Any]]:
        """{champ: {mesure: tableau}}, la mesure « » pour une contribution qui n'est
        celle d'aucune mesure."""


class Modele:
    """Des blocs dans un ordre, et leurs boucles simultanées déclarées.

    REFUSÉ À LA CONSTRUCTION : un champ inconnu du registre ; un bloc qui écrit un champ
    que le cadre ferme ; un champ non additif écrit par deux blocs ; un bloc qui lit un
    champ qu'aucun bloc antérieur n'écrit, hors d'une boucle déclarée qui l'écrit."""

    def __init__(self, blocs: Sequence[Bloc],
                 boucles: Sequence[Sequence[str]] = ()) -> None:
        noms = [b.nom for b in blocs]
        if len(set(noms)) != len(noms):
            raise PasError(f"blocs en double : {noms}")
        reserves = {"depart", "publie", "cadre"}
        if reserves & set(noms):
            raise PasError(f"noms réservés à l'origine des contributions : {reserves}")
        self.blocs = tuple(blocs)
        position = {b.nom: i for i, b in enumerate(blocs)}
        groupes: list[list[Bloc]] = []
        dans_boucle: dict[str, int] = {}
        for numero, boucle in enumerate(boucles):
            membres = sorted(position[n] for n in boucle)
            if membres != list(range(membres[0], membres[0] + len(membres))):
                raise PasError(f"boucle {list(boucle)} : ses blocs doivent se suivre")
            for n in boucle:
                dans_boucle[n] = numero
        i = 0
        while i < len(blocs):
            numero = dans_boucle.get(blocs[i].nom)
            if numero is None:
                groupes.append([blocs[i]])
                i += 1
            else:
                groupe = [b for b in blocs if dans_boucle.get(b.nom) == numero]
                groupes.append(groupe)
                i += len(groupe)
        self.groupes = tuple(tuple(g) for g in groupes)
        self.boucles = {i for i, g in enumerate(self.groupes)
                        if any(b.nom in dans_boucle for b in g)}
        ecrits: dict[str, str] = {}
        for g, groupe in enumerate(self.groupes):
            dans_groupe = {c for b in groupe for c in b.ecrit}
            for bloc in groupe:
                for nom in (*bloc.lit, *bloc.ecrit):
                    definition(nom)
                fermes = sorted(set(bloc.ecrit) & set(FERMES))
                if fermes:
                    raise PasError(f"bloc « {bloc.nom} » : écrit {fermes}, que le cadre "
                                   f"seul ferme")
                for nom in bloc.lit:
                    permis = nom in ecrits or (g in self.boucles and nom in dans_groupe)
                    if not permis:
                        raise PasError(f"bloc « {bloc.nom} » : lit « {nom} », qu'aucun "
                                       f"bloc antérieur n'écrit")
            for bloc in groupe:
                for nom in bloc.ecrit:
                    if not REGISTRE[nom].additif and nom in ecrits:
                        raise PasError(f"« {nom} » n'est pas additif et deux blocs "
                                       f"l'écrivent ({ecrits[nom]}, {bloc.nom})")
                    ecrits.setdefault(nom, bloc.nom)
        self.ecrits = dict(ecrits)


# --------------------------------------------------------------------------- #
# le contexte d'un bloc
# --------------------------------------------------------------------------- #
class Contexte:
    """Ce qu'un bloc voit d'une année : ses lectures déclarées de l'année, tout le passé
    de la trajectoire, la référence, les entrées, les mesures et θ."""

    def __init__(self, *, annee: int, k: int, n: int, theta: Mapping[str, Any],
                 entrees: Entrees, prec: Etat, courant: Etat, historique: Sequence[Etat],
                 reference: Sequence[Etat] | None, mesures: Sequence[Any],
                 depart: Etat) -> None:
        self.annee, self.k, self.n = annee, k, n
        self.theta, self.entrees = theta, entrees
        self.prec, self.courant = prec, courant
        self.historique, self.reference = historique, reference
        self.mesures, self.depart = mesures, depart
        self.bloc: Bloc | None = None
        self.amorce: dict[str, np.ndarray] = {}

    def _permis(self, nom: str) -> None:
        if self.bloc is not None and nom not in self.bloc.lit:
            raise PasError(f"bloc « {self.bloc.nom} » : lit « {nom} » sans le déclarer")

    def lire(self, nom: str) -> np.ndarray:
        """Un champ de l'année, déclaré dans `lit`."""
        self._permis(nom)
        if not self.courant.present(nom) and nom in self.amorce:
            return self.amorce[nom]
        return self.courant[nom]

    def par_mesure(self, nom: str) -> dict[str, np.ndarray]:
        """Un champ de l'année, déclaré dans `lit`, par mesure."""
        self._permis(nom)
        return self.courant.par_mesure(nom)

    def passe(self, j: int) -> Etat:
        """L'état de l'année j < k de la trajectoire."""
        if not 0 <= j < self.k:
            raise PasError(f"année {j} : le passé va de 0 à {self.k - 1}")
        return self.historique[j]

    def pib_reference(self, j: int) -> np.ndarray:
        """Le PIB de la trajectoire de référence à l'année j ≤ k. Dans la référence
        elle-même, à l'année k, le PIB écrit par les blocs qui ont déjà tourné."""
        if self.reference is not None:
            return self.reference[j]["pib"]
        return self.courant["pib"] if j == self.k else self.passe(j)["pib"]


# --------------------------------------------------------------------------- #
# le pas
# --------------------------------------------------------------------------- #
def _ecrire(etat: Etat, bloc: Bloc, contributions: Mapping[str, Mapping[str, Any]]) -> None:
    inattendus = sorted(set(contributions) - set(bloc.ecrit))
    if inattendus:
        raise PasError(f"bloc « {bloc.nom} » : écrit {inattendus}, non déclarés")
    etat.retirer(bloc.nom)
    for nom in bloc.ecrit:
        parts = contributions.get(nom, {})
        if REGISTRE[nom].additif:
            etat.declarer(nom)
            for mesure, valeur in parts.items():
                etat.ecrire(nom, (bloc.nom, mesure), valeur)
        else:
            if set(parts) != {""}:
                raise PasError(f"bloc « {bloc.nom} » : « {nom} » n'est pas additif, une "
                               f"seule valeur, sous la clé « »")
            etat.fixer(nom, parts[""])


def _tourner(etat: Etat, groupe: Sequence[Bloc], ctx: Contexte, boucle: bool) -> None:
    if not boucle:
        ctx.bloc = groupe[0]
        _ecrire(etat, groupe[0], groupe[0].contribue(ctx))
        ctx.bloc = None
        return
    champs = [c for b in groupe for c in b.ecrit]
    ctx.amorce = {c: (ctx.prec[c] if ctx.prec.present(c) else np.zeros(ctx.n))
                  for c in champs}
    avant = None
    for _ in range(ITERATIONS_MAX):
        for bloc in groupe:
            ctx.bloc = bloc
            _ecrire(etat, bloc, bloc.contribue(ctx))
        ctx.bloc = None
        apres = {c: etat[c].copy() for c in champs}
        if avant is not None:
            ecarts = {c: np.max(np.abs(apres[c] - avant[c])
                                / np.maximum(np.abs(apres[c]), 1.0)) for c in champs}
            pire = max(ecarts, key=ecarts.get)
            if ecarts[pire] <= TOLERANCE_POINT_FIXE:
                ctx.amorce = {}
                return
        avant = apres
    auteur = next(b.nom for b in groupe if pire in b.ecrit)
    raise NonConvergence(f"point fixe sans convergence en {etat.annee} après "
                         f"{ITERATIONS_MAX} itérations : bloc « {auteur} », champ « {pire} » "
                         f"(écart relatif {ecarts[pire]:.3e})")


def _somme_par_cle(etat: Etat, noms: Sequence[str], signes: Sequence[float]
                   ) -> dict[Cle, np.ndarray]:
    out: dict[Cle, np.ndarray] = {}
    for nom, signe in zip(noms, signes, strict=True):
        for cle, valeur in etat.de(nom).items():
            out[cle] = out[cle] + signe * valeur if cle in out else signe * valeur
    return out


def fermer(etat: Etat, prec: Etat, entrees: Entrees, k: int) -> None:
    """Le cadre ferme les comptes (§3.4), contribution par contribution."""
    recettes = _somme_par_cle(etat, RECETTES, [1.0] * len(RECETTES))
    depenses = _somme_par_cle(etat, DEPENSES, [1.0] * len(DEPENSES))
    ouverture = dict(prec.de("dette"))
    interets = {cle: (entrees.taux_reference[k] if cle[0] in ORIGINES_REFERENCE
                      else entrees.taux_marginal) * d for cle, d in ouverture.items()}
    etat.copier_contributions("apu_recettes", recettes)
    etat.copier_contributions("apu_depenses_primaires", depenses)
    etat.copier_contributions("interets_nets", interets)
    zero = np.zeros(etat.n)
    cles = set(recettes) | set(depenses) | set(interets)
    b9 = {c: recettes.get(c, zero) - depenses.get(c, zero) - interets.get(c, zero)
          for c in cles}
    etat.copier_contributions("b9", b9)
    etat.copier_contributions("solde_primaire",
                              {c: b9[c] + interets.get(c, zero) for c in cles})
    etat.copier_contributions("dette_ouverture", ouverture)
    flux = _somme_par_cle(etat, ("sfa", "ecart_millesime_dette", "ecart_eurostat"),
                          (1.0, 1.0, 1.0))
    cles_dette = set(ouverture) | set(b9) | set(flux)
    etat.copier_contributions("dette", {
        c: ouverture.get(c, zero) - b9.get(c, zero) + flux.get(c, zero) for c in cles_dette})
    etat.fixer("ratio_dette", etat["dette"] / etat["pib"])
    etat.fixer("taux_implicite", etat["interets_nets"] / etat["dette_ouverture"])
    try:
        volume = np.zeros(etat.n)
        for nom in EMPLOIS_EN_VOLUME:
            signe = REGISTRE[nom].signe
            volume = volume + signe * (etat[nom] / etat[f"prix_{nom}"] - prec[nom])
        etat.fixer("croissance_volume_pib", volume / prec["pib"])
    except ChampAbsent:
        # Sans les prix ou les emplois de l'an passé, le volume n'est pas calculé :
        # absent, et tout ce qui le lit refuse en le nommant.
        pass


def pas(prec: Etat, *, annee: int, k: int, entrees: Entrees, mesures: Sequence[Any],
        theta: Mapping[str, Any], modele: Modele, historique: Sequence[Etat],
        reference: Sequence[Etat] | None, depart: Etat) -> Etat:
    """L'état de l'année `annee`, la k-ième de la trajectoire, depuis l'état `prec`."""
    if entrees.annees[k] != annee:
        raise PasError(f"année {annee} au rang {k}, les entrées y portent "
                       f"{entrees.annees[k]}")
    etat = Etat(annee, prec.n)
    ctx = Contexte(annee=annee, k=k, n=prec.n, theta=theta, entrees=entrees, prec=prec,
                   courant=etat, historique=historique, reference=reference,
                   mesures=mesures, depart=depart)
    for g, groupe in enumerate(modele.groupes):
        _tourner(etat, groupe, ctx, g in modele.boucles)
    fermer(etat, prec, entrees, k)
    identites.verifier(etat, prec)
    return etat
