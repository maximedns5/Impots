"""L'apprentissage et le juge du passé (but 23, lot 6, D-417) : estimer, rejouer, noter.

Le premier juge du jumeau (D-404) : il part de l'état publié d'une année passée, reçoit ce
qui s'est passé ensuite (les chocs budgétaires observés et les exogènes), et sa
trajectoire est comparée aux séries publiées. Ses θ s'estiment sur une période et se
notent sur une autre, jamais sur la même. Ce module est GÉNÉRIQUE : il ne lit aucun
fichier, il reçoit un simulateur (une fenêtre et θ donnent une `Trajectoire`) et un
observateur (une année donne l'état publié). Les entrées réelles, les fenêtres, les
cibles et leurs tolérances préenregistrées sont dans `jumeau.rejeu_histoire`.

LES FENÊTRES. Une `Fenetre` part de l'état publié de l'année `depart`, rejoue les années
`depart + 1` à `fin` et note les années `notees`. Un `Schema` porte les fenêtres de
l'estimation et celles du test ; il refuse une année notée des deux côtés, une année
exclue (2020 et 2021, D-417) qu'une fenêtre rejouerait ou noterait, et une fenêtre vide.

LES CIBLES. Une `Cible` est une grandeur que le jumeau calcule et qu'une série publie, la
même fonction de l'état de l'année et de celui d'avant des deux côtés (une croissance en
volume, une part du PIB, un taux), en points de pourcentage, avec sa tolérance et sa
raison. `ajout` est un terme connu avant le test, ajouté au jumeau et au naïf (la
croissance tendancielle de l'emploi, que la référence du cadre tient constant).

LA NOTE. Pour une cible et une période : e_t = jumeau_t − publié_t chaque année notée,
REQM = √(Σ e_t² / T) ; la cible est TENUE si REQM ≤ tolérance. Le NAÏF est la référence de
la même trajectoire (`Trajectoire.reference` : la croissance tendancielle, les recettes
et les dépenses en part constante du PIB, l'emploi et le chômage du départ, les mêmes
prix, taux et ajustement flux-stocks que le jumeau) ; le jumeau BAT LE NAÏF si sa REQM est
strictement plus petite. La note de la période : la part des cibles tenues, et la part où
le jumeau bat le naïf. Un jumeau qui ne bat pas le naïf le dit.

L'ESTIMATION. Les θ estimés minimisent, dans la boîte [0 ; 1] de chacun (jamais au-delà
des plages publiées) :

    J(θ) = Σ_fenêtres Σ_cibles Σ_t (e_t(θ) / tol_c)² + λ Σ_i ((θ_i − ½) / ½)²

des moindres carrés pondérés par l'inverse du carré des tolérances, pénalisés vers ½ :
c'est le mode a posteriori d'une vraisemblance gaussienne d'écart-type la tolérance, sous
un a priori gaussien centré en ½, d'écart-type ½ (λ = 1). La minimisation est un
Levenberg-Marquardt projeté sur la boîte ; la jacobienne se calcule par différences
finies en un seul appel du simulateur, les θ perturbés sur l'axe des tirages (CADRE.md §7).
L'écart-type approché de chaque θ est la racine de la diagonale de (JᵀJ)⁻¹ au point
trouvé ; un θ d'écart-type au-delà de `IDENTIFIE` est dit non identifié : il reste
estimé, mais l'a priori le porte.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from impots.jumeau.etat import Etat


class ApprentissageError(ValueError):
    """Un schéma, une cible ou une estimation que le juge refuse."""


# --------------------------------------------------------------------------- #
# les fenêtres et le schéma
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Fenetre:
    depart: int
    fin: int
    notees: tuple[int, ...]

    def __post_init__(self) -> None:
        if self.fin <= self.depart:
            raise ApprentissageError(f"fenêtre de {self.depart} à {self.fin} : vide")
        if not self.notees:
            raise ApprentissageError(f"fenêtre {self.depart}–{self.fin} sans année notée")
        if tuple(sorted(set(self.notees))) != tuple(self.notees):
            raise ApprentissageError(f"années notées {self.notees} : croissantes, uniques")
        dehors = [a for a in self.notees if a not in self.annees]
        if dehors:
            raise ApprentissageError(f"années notées {dehors} hors de la fenêtre "
                                     f"{self.depart + 1}–{self.fin}")

    @property
    def annees(self) -> tuple[int, ...]:
        """Les années rejouées, de `depart + 1` à `fin`."""
        return tuple(range(self.depart + 1, self.fin + 1))


@dataclass(frozen=True)
class Schema:
    estimation: tuple[Fenetre, ...]
    test: tuple[Fenetre, ...]
    exclues: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        if not self.estimation or not self.test:
            raise ApprentissageError("un schéma sans fenêtre d'estimation ou de test")
        for nom, fenetres in (("estimation", self.estimation), ("test", self.test)):
            notees = [a for f in fenetres for a in f.notees]
            if len(set(notees)) != len(notees):
                raise ApprentissageError(f"{nom} : une année notée deux fois {notees}")
            for f in fenetres:
                touchees = sorted(set(f.annees) & set(self.exclues))
                if touchees:
                    raise ApprentissageError(
                        f"{nom} : la fenêtre {f.depart}–{f.fin} rejoue les années exclues "
                        f"{touchees}")
        communes = sorted(set(self.annees("estimation")) & set(self.annees("test")))
        if communes:
            raise ApprentissageError(f"années notées à l'estimation et au test : {communes} "
                                     f"(jamais sur la même)")

    def annees(self, periode: str) -> tuple[int, ...]:
        fenetres = self.fenetres(periode)
        return tuple(sorted(a for f in fenetres for a in f.notees))

    def fenetres(self, periode: str) -> tuple[Fenetre, ...]:
        if periode == "estimation":
            return self.estimation
        if periode == "test":
            return self.test
        raise ApprentissageError(f"période « {periode} » : « estimation » ou « test »")


# --------------------------------------------------------------------------- #
# les cibles
# --------------------------------------------------------------------------- #
Valeur = Callable[[Etat, Etat], np.ndarray]
"""(état de l'année, état d'avant) → la grandeur notée, forme (n,)."""


@dataclass(frozen=True)
class Cible:
    nom: str
    libelle: str
    unite: str
    tolerance: float
    raison: str
    jumeau: Valeur
    publie: Valeur | None = None
    """La même grandeur côté publié, quand le champ diffère (les créations)."""
    ajout: float = 0.0
    """Ajouté au jumeau et au naïf : un terme connu avant le test, dit."""

    def __post_init__(self) -> None:
        if not self.tolerance > 0:
            raise ApprentissageError(f"cible « {self.nom} » : tolérance {self.tolerance}")


def _a(etat: Etat, nom: str) -> np.ndarray:
    return np.asarray(etat[nom], dtype=float)


def croissance(champ: str) -> Valeur:
    """100 (x_t / x_{t−1} − 1)."""
    return lambda e, p: 100.0 * (_a(e, champ) / _a(p, champ) - 1.0)


def croissance_volume(champ: str, prix: str) -> Valeur:
    """100 (x_t / (p_t x_{t−1}) − 1), p_t le déflateur sur l'année d'avant (CADRE.md §2)."""
    return lambda e, p: 100.0 * (_a(e, champ) / (_a(e, prix) * _a(p, champ)) - 1.0)


def champ_fixe(champ: str, echelle: float = 100.0) -> Valeur:
    """echelle x_t (une croissance ou un ratio que le cadre fixe)."""
    return lambda e, p: echelle * _a(e, champ)


def part(num: str, den: str = "pib") -> Valeur:
    """100 num_t / den_t."""
    return lambda e, p: 100.0 * _a(e, num) / _a(e, den)


# --------------------------------------------------------------------------- #
# le rejeu d'une fenêtre
# --------------------------------------------------------------------------- #
Simulateur = Callable[[Fenetre, Mapping[str, Any]], Any]
"""(fenêtre, θ) → une `Trajectoire` (référence et variante) depuis l'état publié."""
Observateur = Callable[[int], Etat]
"""année → l'état publié de l'année (`historique.etat_initial`, ou synthétique)."""


@dataclass(frozen=True)
class Rejeu:
    """Une fenêtre rejouée : par cible, {année : valeur} du jumeau, du naïf, du publié."""

    fenetre: Fenetre
    jumeau: Mapping[str, Mapping[int, np.ndarray]]
    naif: Mapping[str, Mapping[int, np.ndarray]]
    publie: Mapping[str, Mapping[int, float]]


def _serie(cible: Cible, etats: Mapping[int, Etat], depart: Etat, annees: Sequence[int],
           fonction: Valeur, ajout: float) -> dict[int, np.ndarray]:
    out = {}
    for a in annees:
        out[a] = fonction(etats[a], etats.get(a - 1, depart)) + ajout
    return out


def rejouer(fenetre: Fenetre, theta: Mapping[str, Any], simulateur: Simulateur,
            observateur: Observateur, cibles: Sequence[Cible]) -> Rejeu:
    trajectoire = simulateur(fenetre, theta)
    if tuple(trajectoire.annees) != fenetre.annees:
        raise ApprentissageError(f"le simulateur rend {trajectoire.annees}, la fenêtre "
                                 f"{fenetre.annees}")
    variante = dict(zip(trajectoire.annees, trajectoire.variante, strict=True))
    reference = dict(zip(trajectoire.annees, trajectoire.reference, strict=True))
    publies = {a: observateur(a) for a in (fenetre.depart, *fenetre.annees)}
    depart = publies[fenetre.depart]
    jumeau, naif, publie = {}, {}, {}
    for c in cibles:
        jumeau[c.nom] = _serie(c, variante, depart, fenetre.notees, c.jumeau, c.ajout)
        naif[c.nom] = _serie(c, reference, depart, fenetre.notees, c.jumeau, c.ajout)
        obs = _serie(c, publies, depart, fenetre.notees, c.publie or c.jumeau, 0.0)
        publie[c.nom] = {a: float(np.asarray(v).reshape(-1)[0]) for a, v in obs.items()}
    return Rejeu(fenetre, jumeau, naif, publie)


# --------------------------------------------------------------------------- #
# la note
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class LigneNote:
    cible: str
    tolerance: float
    erreurs: Mapping[int, float]
    erreurs_naif: Mapping[int, float]
    reqm: float
    reqm_naif: float

    @property
    def tenue(self) -> bool:
        return self.reqm <= self.tolerance

    @property
    def naif_tenu(self) -> bool:
        return self.reqm_naif <= self.tolerance

    @property
    def bat_naif(self) -> bool:
        return self.reqm < self.reqm_naif


@dataclass(frozen=True)
class Note:
    periode: str
    lignes: tuple[LigneNote, ...]
    non_notees: Mapping[str, str] = field(default_factory=dict)

    @property
    def tenues(self) -> int:
        return sum(ligne.tenue for ligne in self.lignes)

    @property
    def naif_tenues(self) -> int:
        return sum(ligne.naif_tenu for ligne in self.lignes)

    @property
    def battues(self) -> int:
        return sum(ligne.bat_naif for ligne in self.lignes)

    @property
    def part_tenue(self) -> float:
        return self.tenues / len(self.lignes)

    def ligne(self, cible: str) -> LigneNote:
        for ligne in self.lignes:
            if ligne.cible == cible:
                return ligne
        raise ApprentissageError(f"cible « {cible} » absente de la note")


def _scalaire(v: np.ndarray, quoi: str) -> float:
    v = np.asarray(v, dtype=float).reshape(-1)
    if v.size != 1:
        raise ApprentissageError(f"{quoi} : la note se calcule sur un seul θ, pas {v.size}")
    return float(v[0])


def noter(periode: str, rejeux: Sequence[Rejeu], cibles: Sequence[Cible],
          non_notees: Mapping[str, str] | None = None) -> Note:
    """La note d'une période, sur les rejeux de ses fenêtres, à un seul θ."""
    lignes = []
    for c in cibles:
        erreurs: dict[int, float] = {}
        naif: dict[int, float] = {}
        for r in rejeux:
            for a in r.fenetre.notees:
                if a in erreurs:
                    raise ApprentissageError(f"{c.nom} : l'année {a} notée deux fois")
                obs = r.publie[c.nom][a]
                erreurs[a] = _scalaire(r.jumeau[c.nom][a], c.nom) - obs
                naif[a] = _scalaire(r.naif[c.nom][a], c.nom) - obs
        e, en = np.array(list(erreurs.values())), np.array(list(naif.values()))
        lignes.append(LigneNote(cible=c.nom, tolerance=c.tolerance,
                                erreurs=dict(sorted(erreurs.items())),
                                erreurs_naif=dict(sorted(naif.items())),
                                reqm=float(np.sqrt(np.mean(e ** 2))),
                                reqm_naif=float(np.sqrt(np.mean(en ** 2)))))
    return Note(periode=periode, lignes=tuple(lignes), non_notees=dict(non_notees or {}))


def evaluer(periode: str, schema: Schema, theta: Mapping[str, Any], simulateur: Simulateur,
            observateur: Observateur, cibles: Sequence[Cible],
            non_notees: Mapping[str, str] | None = None) -> tuple[Note, tuple[Rejeu, ...]]:
    """Rejoue les fenêtres d'une période à θ et les note."""
    rejeux = tuple(rejouer(f, theta, simulateur, observateur, cibles)
                   for f in schema.fenetres(periode))
    return noter(periode, rejeux, cibles, non_notees), rejeux


# --------------------------------------------------------------------------- #
# l'estimation
# --------------------------------------------------------------------------- #
#: L'écart-type approché au-delà duquel un θ est dit non identifié.
IDENTIFIE = 0.25
PAS_DIFFERENCES = 0.02
AMORTISSEMENTS = (1e-4, 1e-3, 1e-2, 1e-1, 1.0, 10.0)


def residus(schema: Schema, simulateur: Simulateur, observateur: Observateur,
            cibles: Sequence[Cible]) -> Callable[[Mapping[str, Any]], np.ndarray]:
    """θ (scalaires ou tableaux sur n tirages) → les résidus normalisés de l'estimation,
    (n, m) : (jumeau − publié) / tolérance, par fenêtre, cible et année notée."""
    publies: dict[int, Etat] = {}

    def observer(annee: int) -> Etat:
        if annee not in publies:
            publies[annee] = observateur(annee)
        return publies[annee]

    def calcul(theta: Mapping[str, Any]) -> np.ndarray:
        colonnes = []
        for f in schema.fenetres("estimation"):
            r = rejouer(f, theta, simulateur, observer, cibles)
            for c in cibles:
                for a in f.notees:
                    colonnes.append((np.asarray(r.jumeau[c.nom][a], dtype=float).reshape(-1)
                                     - r.publie[c.nom][a]) / c.tolerance)
        return np.column_stack(np.broadcast_arrays(*colonnes))
    return calcul


@dataclass(frozen=True)
class Estimation:
    theta: Mapping[str, float]
    """Tous les θ : les estimés et ceux tenus à leur valeur fixe."""
    estimes: tuple[str, ...]
    cout: float
    cout_initial: float
    ecarts_types: Mapping[str, float]
    iterations: int
    a_priori: float

    @property
    def identifies(self) -> tuple[str, ...]:
        return tuple(k for k in self.estimes if self.ecarts_types[k] < IDENTIFIE)


def estimer(fonction: Callable[[Mapping[str, Any]], np.ndarray], estimes: Sequence[str],
            fixes: Mapping[str, float], *, a_priori: float = 1.0,
            depart: Mapping[str, float] | None = None, iterations: int = 40,
            tolerance: float = 1e-10) -> Estimation:
    """Le Levenberg-Marquardt projeté sur [0 ; 1]^p (docstring du module). `fonction` rend
    les résidus (n, m) pour des θ sur n tirages ; `fixes` les θ qui ne sont pas estimés
    (à ½ dans D-417). Le départ est ½ pour chaque θ estimé, sauf `depart`."""
    estimes = tuple(estimes)
    p = len(estimes)
    if not p or len(set(estimes)) != p:
        raise ApprentissageError(f"θ estimés {estimes} : au moins un, sans doublon")
    communs = sorted(set(estimes) & set(fixes))
    if communs:
        raise ApprentissageError(f"θ à la fois estimés et fixés : {communs}")
    if any(not 0.0 <= float(v) <= 1.0 for v in fixes.values()):
        raise ApprentissageError("un θ fixé hors de [0 ; 1]")
    if a_priori < 0:
        raise ApprentissageError(f"poids de l'a priori {a_priori} négatif")
    racine = np.sqrt(a_priori)

    def lot(points: np.ndarray) -> np.ndarray:
        """Les résidus augmentés de l'a priori, (len(points), m + p)."""
        theta: dict[str, Any] = {k: float(v) for k, v in fixes.items()}
        n = points.shape[0]
        for i, k in enumerate(estimes):
            theta[k] = points[:, i] if n > 1 else float(points[0, i])
        r = np.atleast_2d(np.asarray(fonction(theta), dtype=float))
        if r.shape[0] != n:
            r = np.broadcast_to(r, (n, r.shape[1]))
        prior = racine * (points - 0.5) / 0.5
        out = np.hstack([r, prior])
        if not np.all(np.isfinite(out)):
            raise ApprentissageError("résidus non finis : le simulateur a refusé ou divergé")
        return out

    def jacobienne(x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        pas = np.where(x + PAS_DIFFERENCES <= 1.0, PAS_DIFFERENCES, -PAS_DIFFERENCES)
        points = np.vstack([x, x + np.diag(pas)])
        r = lot(points)
        return r[0], ((r[1:] - r[0]) / pas[:, None]).T

    x = np.array([float((depart or {}).get(k, 0.5)) for k in estimes])
    if np.any((x < 0) | (x > 1)):
        raise ApprentissageError("départ de l'estimation hors de [0 ; 1]")
    r0, jac = jacobienne(x)
    cout = cout_initial = float(r0 @ r0)
    faites = 0
    while faites < iterations:
        faites += 1
        jtj, jtr = jac.T @ jac, jac.T @ r0
        echelle = np.diag(np.diag(jtj)) + 1e-12 * np.eye(p)
        candidats = []
        for mu in AMORTISSEMENTS:
            try:
                pas = np.linalg.solve(jtj + mu * echelle, -jtr)
            except np.linalg.LinAlgError:
                continue
            candidats.append(np.clip(x + pas, 0.0, 1.0))
        if not candidats:
            break
        points = np.vstack(candidats)
        couts = np.sum(lot(points) ** 2, axis=1)
        meilleur = int(np.argmin(couts))
        if not couts[meilleur] < cout - tolerance * max(1.0, cout):
            break
        deplacement = float(np.max(np.abs(points[meilleur] - x)))
        x, cout = points[meilleur], float(couts[meilleur])
        r0, jac = jacobienne(x)
        if deplacement < 1e-7:
            break
    jtj = jac.T @ jac
    try:
        covariance = np.linalg.inv(jtj)
        ecarts = np.sqrt(np.clip(np.diag(covariance), 0.0, None))
    except np.linalg.LinAlgError:
        ecarts = np.full(p, np.inf)
    theta = {k: float(v) for k, v in fixes.items()}
    theta.update({k: float(v) for k, v in zip(estimes, x, strict=True)})
    return Estimation(theta=theta, estimes=estimes, cout=cout, cout_initial=cout_initial,
                      ecarts_types=dict(zip(estimes, map(float, ecarts), strict=True)),
                      iterations=faites, a_priori=a_priori)
