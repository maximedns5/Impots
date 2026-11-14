"""La référence et la variante, et leur différence (CADRE.md §3, D-213).

Deux trajectoires se calculent toujours ensemble, sous les mêmes entrées et le même θ :
la RÉFÉRENCE, sans les mesures, et la VARIANTE, avec. Le résultat publié est leur
différence, avec les deux niveaux à côté. Dans la variante, un bloc qui lit le PIB de
référence (Mésange, le canal des créations) lit celui de la référence calculée.

LA DÉCOMPOSITION DE Δb, sans reste. Avec D et Y la dette et le PIB de la variante, D^r et
Y^r ceux de la référence, b^r = D^r/Y^r, et pour chaque clé (origine, mesure) les écarts
de contribution ΔD_c = D_c − D^r_c et ΔY_c = Y_c − Y^r_c :

    Δb = D/Y − D^r/Y^r = Σ_c (ΔD_c − b^r ΔY_c) / Y

Chaque terme est la part d'un bloc et d'une mesure : sa dette ajoutée (ses chocs, ses
recettes induites, ses intérêts au taux marginal), moins ce que son PIB retire au ratio
comme dénominateur. La somme est exacte, à l'arrondi près.

LE DÉPART. `depart_depuis_start` construit l'état de l'année de départ d'un `Start` (le
point de départ des rapports, `dette.reference`) et des parts de chaque groupe ;
`historique.etat_initial` donne l'état publié d'une année. Un départ porte des stocks et
des parts, pas de compte de l'année : ses flux ne sont pas lus.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from impots.jumeau import thetas
from impots.jumeau.champs import DEPENSES, EMPLOIS, RECETTES, REGISTRE, REVENUS
from impots.jumeau.etat import Cle, Etat
from impots.jumeau.pas import Entrees, Modele, pas


class TrajectoireError(ValueError):
    """Une trajectoire que le cadre refuse."""


DEPART: Cle = ("depart", "")


def depart_depuis_start(start: Any, parts: Mapping[str, float], *, n: int = 1) -> Etat:
    """L'état de départ d'un `Start` (ou de son dictionnaire, `rejeu.start`) : le PIB, la
    dette, et chaque groupe réparti selon `parts` — les emplois et les revenus sur le PIB,
    les recettes sur R Y, les dépenses primaires sur s Y. Les parts d'un groupe somment à
    un (signées pour les emplois) ; un groupe sans part est refusé."""
    lire = (start.get if isinstance(start, Mapping) else lambda k: getattr(start, k))
    annee, pib = int(lire("year")), float(lire("gdp_eur")) / 1e9
    totaux = {"emplois": pib, "revenus": pib,
              "apu_recettes": float(lire("receipts_ratio")) * pib,
              "apu_depenses": float(lire("spending_ratio")) * pib}
    etat = Etat(annee, n)
    etat.ecrire("pib", DEPART, pib)
    for groupe, noms in (("emplois", EMPLOIS), ("revenus", REVENUS),
                         ("apu_recettes", RECETTES), ("apu_depenses", DEPENSES)):
        somme = sum(REGISTRE[c].signe * parts.get(c, 0.0) for c in noms)
        if abs(somme - 1.0) > 1e-12:
            raise TrajectoireError(f"parts du groupe « {groupe} » de somme {somme}, pas 1")
        for c in noms:
            etat.ecrire(c, DEPART, parts.get(c, 0.0) * totaux[groupe])
    etat.ecrire("dette", DEPART, float(lire("debt_ratio")) * pib)
    return etat


@dataclass(frozen=True)
class Trajectoire:
    annees: tuple[int, ...]
    reference: tuple[Etat, ...]
    variante: tuple[Etat, ...]
    mesures: tuple[Any, ...]
    theta: Mapping[str, Any]
    avertissements: tuple[str, ...] = field(default_factory=tuple)

    def _rang(self, annee: int) -> int:
        if annee not in self.annees:
            raise TrajectoireError(f"année {annee} hors de la trajectoire {self.annees}")
        return self.annees.index(annee)

    def niveaux(self, champ: str) -> tuple[np.ndarray, np.ndarray]:
        """(référence, variante), de forme (années, n)."""
        return (np.array([e[champ] for e in self.reference]),
                np.array([e[champ] for e in self.variante]))

    def difference(self, champ: str) -> np.ndarray:
        reference, variante = self.niveaux(champ)
        return variante - reference

    @property
    def delta_b(self) -> np.ndarray:
        """Δb_t, en points de PIB divisés par cent (0,01 = un point), (années, n)."""
        return self.difference("ratio_dette")

    @property
    def ecart_pib(self) -> np.ndarray:
        """y_t, le PIB de la variante sur celui de la référence, moins un."""
        reference, variante = self.niveaux("pib")
        return variante / reference - 1.0

    def decomposition(self, annee: int) -> dict[Cle, np.ndarray]:
        """La part de chaque (origine, mesure) dans Δb de l'année ; elle se somme à Δb."""
        k = self._rang(annee)
        ref, var = self.reference[k], self.variante[k]
        b_ref = ref["dette"] / ref["pib"]
        zero = np.zeros(var.n)
        dette_r, dette_v = ref.de("dette"), var.de("dette")
        pib_r, pib_v = ref.de("pib"), var.de("pib")
        cles = set(dette_r) | set(dette_v) | set(pib_r) | set(pib_v)
        return {c: ((dette_v.get(c, zero) - dette_r.get(c, zero))
                    - b_ref * (pib_v.get(c, zero) - pib_r.get(c, zero))) / var["pib"]
                for c in sorted(cles)}


def calculer(depart: Etat, *, entrees: Entrees, mesures: Sequence[Any],
             theta: Mapping[str, Any], blocs: Sequence[Any],
             boucles: Sequence[Sequence[str]] = ()) -> Trajectoire:
    """La référence et la variante sur les années des entrées, depuis `depart`."""
    if entrees.annees[0] != depart.annee + 1:
        raise TrajectoireError(f"départ en {depart.annee}, première année "
                               f"{entrees.annees[0]}")
    identifiants = [m.identifiant for m in mesures]
    if len(set(identifiants)) != len(identifiants):
        raise TrajectoireError(f"mesures d'identifiants en double : {identifiants}")
    thetas.registre(mesures)
    n = thetas.tirages(theta)
    if depart.n != n:
        depart = _etendre(depart, n)
    modele = Modele(blocs, boucles)
    for bloc in modele.blocs:
        preparer = getattr(bloc, "preparer", None)
        if preparer is not None:
            preparer(entrees, mesures)

    def derouler(avec: Sequence[Any], reference: Sequence[Etat] | None) -> list[Etat]:
        etats: list[Etat] = []
        prec = depart
        for k, annee in enumerate(entrees.annees):
            prec = pas(prec, annee=annee, k=k, entrees=entrees, mesures=avec, theta=theta,
                       modele=modele, historique=etats, reference=reference, depart=depart)
            etats.append(prec)
        return etats

    reference = derouler((), None)
    variante = derouler(tuple(mesures), reference)
    avertissements = tuple(a for m in mesures if (a := m.avertissement))
    return Trajectoire(annees=tuple(entrees.annees), reference=tuple(reference),
                       variante=tuple(variante), mesures=tuple(mesures), theta=dict(theta),
                       avertissements=avertissements)


def _etendre(depart: Etat, n: int) -> Etat:
    """Le départ (un seul tirage) recopié sur n tirages."""
    if depart.n != 1:
        raise TrajectoireError(f"départ sur {depart.n} tirages, θ sur {n}")
    etat = Etat(depart.annee, n, publie=depart.publie)
    for nom in depart.champs():
        if REGISTRE[nom].additif:
            etat.copier_contributions(nom, {c: np.full(n, v[0])
                                            for c, v in depart.de(nom).items()})
        else:
            etat.fixer(nom, np.full(n, depart[nom][0]))
    return etat
