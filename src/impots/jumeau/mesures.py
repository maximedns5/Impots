"""Les mesures (CADRE.md §5) : ce qui entre dans le jumeau, par son choc statique.

Une `Mesure` porte un identifiant, un libellé, son auteur, ses années d'effet et ses chocs
statiques par année, en Md€ :

* sur les catégories du compte des APU (`chocs`, signe du moteur : un coût est positif) ;
* sur les instruments de Mésange (`impulsions`, signe expansionniste, comme
  `shocks.Impulse.by_instrument`) ;
* sur les prélèvements des entreprises et du capital que lit le canal des créations
  (`prelevements`, recettes positives) ;
* sur les ménages par décile et les entreprises par taille (`menages`, `entreprises`),
  portés pour les lots 4 et 2, que le lot 1 ne lit pas.

DEUX ORIGINES, et aucune autre. `depuis_rapport` lit le choc d'une passe déjà faite sur la
population, une fois, et garde son rapport et son commit : son coût mécanique et ses
recettes de comportement à θ (les statistiques suffisantes des canaux, D-336), que le
rapport ne ventile pas entre catégories et qui vont donc sur « mesures_non_ventilees ».
`hypothese` déclare une loi directement, pour les curseurs : chaque trajectoire qui la lit
le dit (`Mesure.avertissement`). Le jumeau ne relance jamais OpenFisca dans un pas.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from impots.jumeau.champs import DEPENSES, IMPULSIONS, RECETTES
from impots.predictif import rejouer

#: Les catégories qu'un choc déclaré peut toucher : celles du compte des APU, hors les
#: deux champs que seuls les blocs écrivent.
CATEGORIES = tuple(c for c in (*RECETTES, *DEPENSES)
                   if c not in ("solde_induit", "mesures_non_ventilees"))
INSTRUMENTS = tuple(i.removeprefix("impulsion_") for i in IMPULSIONS)
RAPPORT, HYPOTHESE = "rapport", "hypothese"
EURO = 1e9
"""Les rapports sont en euros, le jumeau en Md€."""


class MesureError(ValueError):
    """Une mesure qui ne peut pas entrer telle quelle."""


@dataclass(frozen=True)
class Mesure:
    identifiant: str
    libelle: str
    auteur: str
    origine: str
    annees: tuple[int, ...]
    chocs: Mapping[int, Mapping[str, float]] = field(default_factory=dict)
    impulsions: Mapping[int, Mapping[str, float]] = field(default_factory=dict)
    prelevements: Mapping[int, float] = field(default_factory=dict)
    couts: Mapping[int, float] = field(default_factory=dict)
    """Le coût mécanique de la passe, Md€, signe du moteur (rapport seulement)."""
    canaux: Mapping[int, Mapping[str, Any] | None] = field(default_factory=dict)
    """Les statistiques suffisantes des canaux de recettes, en euros, par année."""
    lignes: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    """Les lignes θ du comportement que le rapport réclame."""
    macro: Mapping[str, Any] | None = None
    """Les tables de Mésange des instruments que le rapport lit."""
    creations: Mapping[str, Any] | None = None
    """Les paramètres du canal des créations, tels que le rapport les porte."""
    report: str | None = None
    """« part_pib_constante » : la première année tenue en part du PIB de référence."""
    menages: Mapping[int, Any] | None = None
    entreprises: Mapping[int, Any] | None = None
    rapport: str | None = None
    commit: str | None = None

    def __post_init__(self) -> None:
        if not self.identifiant:
            raise MesureError("une mesure sans identifiant ne se décompose pas")
        if self.origine not in (RAPPORT, HYPOTHESE):
            raise MesureError(f"origine « {self.origine} » : « rapport » ou « hypothese »")
        if self.origine == RAPPORT and not (self.rapport and self.commit):
            raise MesureError(f"mesure « {self.identifiant} » tirée d'un rapport sans son "
                              f"rapport et son commit : son choc ne se retrouverait pas")
        for annee, chocs in self.chocs.items():
            inconnues = sorted(set(chocs) - set(CATEGORIES))
            if inconnues:
                raise MesureError(f"mesure « {self.identifiant} », {annee} : catégories "
                                  f"inconnues du compte des APU {inconnues}")
        for annee, impulsions in self.impulsions.items():
            inconnus = sorted(set(impulsions) - set(INSTRUMENTS))
            if inconnus:
                raise MesureError(f"mesure « {self.identifiant} », {annee} : instruments "
                                  f"de Mésange inconnus {inconnus}")
        if self.report not in (None, rejouer.CARRY):
            raise MesureError(f"convention de report « {self.report} » inconnue")

    @property
    def avertissement(self) -> str | None:
        if self.origine == HYPOTHESE:
            return (f"Loi hypothétique « {self.libelle} » ({self.identifiant}) : déclarée "
                    f"directement, sans passe sur la population ; chaque nombre qu'elle "
                    f"touche est une hypothèse.")
        return None

    @classmethod
    def depuis_rapport(cls, payload: Mapping[str, Any], *, vue: str, identifiant: str,
                       libelle: str, auteur: str, rapport: str,
                       commit: str | None = None) -> Mesure:
        """La mesure d'un rapport du chemin annuel, ou d'une première année reportée
        (`annuel.carried_payload`), dans la vue `vue` ; ce que `rejouer.chemin` lit."""
        if vue not in rejouer.VIEWS:
            raise MesureError(f"vue « {vue} » inconnue ({sorted(rejouer.VIEWS)})")
        rejeu = rejouer._rejeu(payload)
        rows = payload["years"]
        report = payload.get("carry")
        if report not in (None, rejouer.CARRY):
            raise MesureError(f"convention de report « {report} » inconnue")
        if report and len(rows) != 1:
            raise MesureError("un rapport reporté porte sa seule première année")
        premiere = int(rows[0]["year"])
        annees = (tuple(range(premiere, premiere + int(payload["horizon"]))) if report
                  else tuple(int(r["year"]) for r in rows))
        stats = {int(r["year"]): r["statistiques"][vue] for r in rows}
        couts = {int(r["year"]): float(r[rejouer.VIEWS[vue]]) / EURO for r in rows}
        avec_canaux = rejeu["behavioural"] and all(s.get("canaux") is not None
                                                   for s in stats.values())
        canaux = {a: (s["canaux"] if avec_canaux else None) for a, s in stats.items()}
        impulsions = {a: {i: float(v) / EURO for i, v in (s["impulses"] or {}).items()}
                      for a, s in stats.items()} if rejeu["looped"] else {}
        prelevements: dict[int, float] = {}
        creations = rejeu.get("creations")
        if creations:
            variations = [float(v) / EURO for v in creations["variations"][vue]]
            prelevements = dict(zip(sorted(stats), variations, strict=True))
        return cls(identifiant=identifiant, libelle=libelle, auteur=auteur,
                   origine=RAPPORT, annees=annees, impulsions=impulsions,
                   prelevements=prelevements, couts=couts, canaux=canaux,
                   lignes=dict(rejeu["lignes"]), macro=rejeu["macro"] if rejeu["looped"]
                   else None, creations=dict(creations["parametres"]) if creations
                   else None, report=report, rapport=rapport,
                   commit=commit or payload.get("commit"))

    @classmethod
    def hypothese(cls, identifiant: str, libelle: str, *,
                  chocs: Mapping[int, Mapping[str, float]],
                  impulsions: Mapping[int, Mapping[str, float]] | None = None,
                  prelevements: Mapping[int, float] | None = None,
                  macro: Mapping[str, Any] | None = None,
                  creations: Mapping[str, Any] | None = None,
                  auteur: str = "loi hypothétique") -> Mesure:
        """Une loi déclarée directement, en Md€ ; ses années sont celles de ses chocs."""
        annees = sorted({*chocs, *(impulsions or {}), *(prelevements or {})})
        if not annees:
            raise MesureError(f"loi hypothétique « {identifiant} » sans aucun choc")
        return cls(identifiant=identifiant, libelle=libelle, auteur=auteur,
                   origine=HYPOTHESE, annees=tuple(annees), chocs=dict(chocs),
                   impulsions=dict(impulsions or {}), prelevements=dict(prelevements or {}),
                   macro=macro, creations=creations)
