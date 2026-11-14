"""Le bloc `mesange` : l'impulsion par instrument → le PIB → le solde (CADRE.md §4).

La boucle de `predictif.retroaction`, réécrite en bloc, avec la même arithmétique que
`predictif.rejouer.loop` (ses fonctions d'horizon sont reprises telles quelles). Ses
sources : Insee, Mésange (G2017-04), les variantes par instrument, lignes du PIB et du
solde primaire (D-214, D-218) ; IMK WP 117, l'écart-type inter-études (D-336).

ÉQUATIONS, pour la mesure m, l'instrument i et l'année k de la trajectoire (années 0 à k) :

    u_{i,j} = 100 I_{m,i,j} / (b_i Y_j)                l'impulsion en points de variante
    Δu_{i,j} = u_{i,j} − u_{i,j−1}                      (Mésange est linéaire : un choc
                                                         qui change est une somme de chocs
                                                         permanents décalés)
    h = horizon lu à k − j + 1 selon la persistance (« lue », « eteint », « tenu »)
    m_i(h) = max(0, c_i(h) + (2θ − 1) sd_i)              le multiplicateur à θ
    φ_i(h) = min((solde_i(h) + b_i) m_i(h) / c_i(h), b_i)
    y_k = Σ_i Σ_{j ≤ k} Δu_{i,j} m_i(h) / 100           l'écart de PIB, part de Y_k
    φ_k = Σ_i Σ_{j ≤ k} Δu_{i,j} φ_i(h) / 100           l'effet sur le solde, part de Y_k

I est l'impulsion en Md€ (signe expansionniste), b_i le coût brut d'un point de variante,
Y le PIB de la référence. Le bloc écrit y_k Y_k sur le PIB, sur les emplois et les
revenus non ventilés (Mésange ne publie que la ligne du PIB), et φ_k Y_k sur l'effet
induit sur le solde.

QUATRE REFUS, ceux de `retroaction` : une autre règle de dépense que « gele_en_volume » (la
dépense de Mésange ne réagit qu'en prix) ; une persistance inconnue, ou aucune au-delà
de l'horizon court ; un horizon au-delà du dernier que Mésange imprime ; une mesure qui
porte des impulsions et aucune table. Un instrument sans ligne de solde (variante ciblée,
taxe carbone) n'a pas de table : il n'a aucun effet, et son rapport le liste comme non
couvert (`retroaction.compute`).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np

from impots.jumeau import thetas
from impots.jumeau.champs import IMPULSIONS
from impots.jumeau.pas import Contexte, Entrees
from impots.predictif import rejouer, retroaction
from impots.predictif.theta import MACRO_ROW


class MesangeError(ValueError):
    """La boucle ne se lit pas comme Mésange l'imprime."""


class Mesange:
    nom = "mesange"
    lit = IMPULSIONS
    ecrit = ("pib", "emplois_non_ventiles", "revenus_non_ventiles", "solde_induit")
    thetas = (MACRO_ROW,)
    porte = ("investissement_cout_du_capital",)
    """Ses multiplicateurs portent la réponse de l'investissement au coût du capital de
    ses instruments (Mésange, éq. d'investissement, p. 44 du PDF) : un bloc structurel
    qui la porte aussi est refusé avec lui (`canaux`, D-407)."""

    def __init__(self, persistance: str | None, *, variante: str | None = None,
                 tables: Mapping[str, Any] | None = None) -> None:
        if persistance is not None and persistance not in rejouer.PERSISTENCES:
            raise MesangeError(f"persistance « {persistance} » inconnue "
                               f"({rejouer.PERSISTENCES})")
        if variante not in (None, rejouer.SALARIALE):
            raise MesangeError(f"variante « {variante} » inconnue")
        self.persistance, self.variante, self.tables = persistance, variante, tables

    def preparer(self, entrees: Entrees, mesures: Sequence[Any]) -> None:
        """Les refus de `retroaction.compute`, avant le premier pas."""
        if entrees.regle_depense != retroaction.SPENDING_RULE:
            raise MesangeError(retroaction.spending_reason(entrees.regle_depense))
        for m in mesures:
            tables = self._tables(m)
            if tables is None:
                continue
            if self.persistance is None and len(entrees.annees) > int(tables["court"]):
                raise MesangeError(f"trajectoire de {len(entrees.annees)} ans sans "
                                   f"persistance nommée : au-delà de {tables['court']} ans, "
                                   f"« lue », « eteint » ou « tenu » (D-055, D-336)")

    def _tables(self, mesure: Any) -> Mapping[str, Any] | None:
        return mesure.macro if mesure.macro is not None else self.tables

    def contribue(self, ctx: Contexte) -> dict[str, dict[str, Any]]:
        z = 2.0 * thetas.lire(ctx.theta, MACRO_ROW, ctx.n) - 1.0
        k = ctx.k
        historiques = {nom: [ctx.passe(j).par_mesure(nom) for j in range(k)]
                       + [ctx.par_mesure(nom)] for nom in IMPULSIONS}
        pib = [ctx.pib_reference(j) for j in range(k + 1)]
        out: dict[str, dict[str, Any]] = {c: {} for c in self.ecrit}
        for m in ctx.mesures:
            chemins = {nom.removeprefix("impulsion_"): [an.get(m.identifiant) for an in h]
                       for nom, h in historiques.items()}
            chemins = {i: c for i, c in chemins.items() if any(
                v is not None and np.any(v != 0.0) for v in c)}
            if not chemins:
                continue
            tables = self._tables(m)
            if tables is None:
                raise MesangeError(f"mesure « {m.identifiant} » : des impulsions sur "
                                   f"{sorted(chemins)} et aucune table de Mésange")
            y_k, phi_k = self._annee(chemins, pib, tables, z, k)
            out["pib"][m.identifiant] = y_k * pib[k]
            out["emplois_non_ventiles"][m.identifiant] = y_k * pib[k]
            out["revenus_non_ventiles"][m.identifiant] = y_k * pib[k]
            out["solde_induit"][m.identifiant] = phi_k * pib[k]
        return out

    def _annee(self, chemins: Mapping[str, list], pib: Sequence[np.ndarray],
               tables: Mapping[str, Any], z: np.ndarray, k: int
               ) -> tuple[np.ndarray, np.ndarray]:
        """(y_k, φ_k) : `rejouer.loop` à la seule année k."""
        lus = [int(h) for h in tables["horizons"]]
        court = int(tables["court"])
        instruments = tables["instruments"]
        y_k = phi_k = 0.0
        for instrument in sorted(set(chemins) & set(instruments)):
            table = instruments[instrument]
            unites = [(0.0 if v is None else v) * 100.0 / (table["brut"] * y)
                      for v, y in zip(chemins[instrument], pib, strict=True)]
            for j in range(k + 1):
                pas_ = unites[j] - (unites[j - 1] if j else 0.0)
                if not np.any(pas_):
                    continue
                h = rejouer._read_horizon(k - j + 1, self.persistance, lus, court)
                if h is None:
                    continue
                centre = rejouer._interpolated(table["pib"], h, lus)
                if self.variante == rejouer.SALARIALE and "pib_salariale" in table:
                    decale = rejouer._interpolated(table["pib_salariale"], h, lus)
                else:
                    decale = centre
                m = np.maximum(0.0, decale + z * table["sd"])
                brut = table["brut"]
                f = np.minimum((rejouer._interpolated(table["solde"], h, lus) + brut)
                               * m / centre, brut)
                y_k = y_k + pas_ * m / 100.0
                phi_k = phi_k + pas_ * f / 100.0
        zero = np.zeros_like(z)
        return zero + y_k, zero + phi_k
