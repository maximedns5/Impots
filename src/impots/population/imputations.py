"""Une seule politique d'imputation pour toutes les passes de population (but 14, D-336).

La population est construite sans revenus du capital, sans consommation, sans indemnités
journalières et sans bases de niches. Une réforme qui règle l'un de ces instruments ne
bouge rien sur elle : son coût serait un zéro confiant. Cinq chemins de passe (l'API, les
deux copies du chemin annuel de la CLI, `scenarios.mechanical_price`, le solveur)
recopiaient chacun leur politique, et elles divergeaient : le préenregistrement n'imputait
jamais le capital, le solveur rien du tout, l'API jamais les IJ (audit du but 14, annexe 2,
§ 4.3).

Ici, une fonction le décide pour tous : `imputations` rend l'union de ce que l'appelant
demande et de ce dont la réforme a besoin pour bouger,

* le capital (PFU, CSG et solidarité du capital) quand la réforme le règle (D-249) ;
* la consommation quand elle règle la TVA ou une accise (D-323) ;
* les IJ quand elle règle leur impôt ou leur CSG (D-306) ;
* les niches, sur demande seulement : leur imputation est une calibration, et le plafond
  global reste aveugle même imputé (`guards.DISPERSION_DEPENDENT_KNOBS`) ;
* les données de ménages des programmes (heures supplémentaires, frais de trajet et frais
  réels, pensions alimentaires, frais de garde, intérêts d'emprunt, étudiants et
  boursiers), sur demande, et quand la réforme règle un bouton qui les lit
  (`boutons_programmes.MENAGES_KNOBS`) : une calibration sur leurs totaux publiés
  (`population.menages`, but 21). Une autre année que 2024 les impute sur la population
  ramenée à 2024 et les vieillit (`menages.impute`) : le runner refuse une telle passe
  sans les facteurs qui ont vieilli sa population.

Ce qu'une passe ne peut pas imputer est refusé, avec sa raison, avant la passe, jamais
rendu à zéro : un bouton de l'IFI (la population ne porte aucun patrimoine), les IJ hors
de l'année que le CCSS décrit, ou ce qu'un chemin déclare ne pas savoir faire. Après la
passe, `guards.zero_confiant` relit le résultat sur tous les chemins.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

CAPITAL = "capital"
CONSOMMATION = "consommation"
IJ = "ij"
NICHES = "niches"
MENAGES = "menages"
#: Ce qu'une passe sait imputer, dans l'ordre où le runner les fait.
CATALOGUE = (CAPITAL, CONSOMMATION, IJ, NICHES, MENAGES)

#: Les boutons des indemnités journalières (D-306, D-312) : ils ne mordent que sur les IJ
#: imputées (D-305).
IJ_KNOBS = frozenset({"ij_at_mp_part_exoneree", "ij_ald_part_exoneree", "csg_ij_taux"})

#: Pourquoi un bouton de l'IFI est refusé sur la population (D-336, décision 5).
IFI_REFUSE = (
    "{knobs} : l'IFI ne se chiffre pas sur la population, qui ne porte aucun patrimoine "
    "(porte « patrimoine ») ; son coût y serait un zéro par absence d'assiette, non par "
    "absence d'effet. Le calculateur foyer par foyer, lui, le chiffre dès que le "
    "patrimoine est saisi.")


class ImputationRefusee(ValueError):
    """Une passe ne peut pas imputer ce que la réforme exige pour bouger : refusée avant la
    passe, avec sa raison, plutôt que chiffrée à zéro. Une `ValueError`, que chaque chemin
    refuse déjà à sa façon (un 422, un statut de sortie)."""


@dataclass(frozen=True)
class Imputations:
    """Ce qu'une passe impute avant d'être chiffrée."""

    capital: bool = False
    consommation: bool = False
    ij: bool = False
    niches: bool = False
    menages: bool = False

    def noms(self) -> tuple[str, ...]:
        return tuple(nom for nom in CATALOGUE if getattr(self, nom))

    def runner(self) -> dict[str, bool]:
        """Les mots-clés de `runner.run` : ceux de ce qui est imputé seulement, les autres
        valant faux par défaut. Une passe sans imputation est appelée comme avant."""
        return {f"impute_{nom}": True for nom in self.noms()}


def _knobs(reform: Any) -> frozenset[str]:
    if reform is None:
        return frozenset()
    return frozenset(reform.model_dump(exclude_none=True))


def ifi_knobs() -> frozenset[str]:
    """Les boutons de l'IFI, lus sur le schéma : un bouton ajouté y entre seul."""
    from impots.api.schemas import ReformSpec

    return frozenset(name for name in ReformSpec.model_fields if name.startswith("ifi_"))


def exigees(reform: Any) -> frozenset[str]:
    """Ce que la réforme exige d'imputer pour bouger : rien d'autre ne le déclare à la
    passe."""
    from impots import consommation
    from impots.engine.reforms import moves_capital

    voulues = set()
    if moves_capital(reform):
        voulues.add(CAPITAL)
    if reform is not None and consommation.touche(reform):
        voulues.add(CONSOMMATION)
    if _knobs(reform) & IJ_KNOBS:
        voulues.add(IJ)
    if _knobs(reform) & menages_knobs():
        voulues.add(MENAGES)
    return frozenset(voulues)


def menages_knobs() -> frozenset[str]:
    from impots.engine.boutons_programmes import MENAGES_KNOBS

    return MENAGES_KNOBS


def imputations(reform: Any, annee: int, *, demandees: Iterable[str] = (),
                possibles: Iterable[str] = CATALOGUE,
                chemin: str = "cette passe") -> Imputations:
    """L'union de ce que l'appelant demande (`demandees`) et de ce dont `reform` a besoin
    pour bouger, pour une passe de l'année `annee`.

    `possibles` dit ce que le chemin sait imputer ; ce que la réforme exige au-delà est
    refusé, nommé avec le chemin (`chemin`). Refusés aussi, partout : un bouton de l'IFI,
    et les IJ hors de l'année que le CCSS décrit (D-305). Ni l'indice du capital ni l'année
    de la consommation ne sont décidés ici : ils suivent le cadre de chaque chemin, et le
    runner refuse un capital d'une autre année sans indice (D-249)."""
    demandees = frozenset(demandees)
    inconnues = sorted(demandees - set(CATALOGUE))
    if inconnues:
        raise ImputationRefusee(
            f"imputations {inconnues} inconnues ; le catalogue est {list(CATALOGUE)}")
    ifi = sorted(_knobs(reform) & ifi_knobs())
    if ifi:
        raise ImputationRefusee(IFI_REFUSE.format(
            knobs=", ".join(f"`{knob}`" for knob in ifi)))
    exige = exigees(reform)
    voulues = demandees | exige
    hors = sorted(voulues - frozenset(possibles))
    if hors:
        raise ImputationRefusee(
            f"{chemin} n'impute pas {hors}, que la réforme exige pour bouger "
            f"({_pourquoi(reform, hors)}) : elle la chiffrerait sur une population sans "
            f"son assiette, à zéro.")
    if IJ in voulues:
        from impots.population import ij as ij_module

        if annee != ij_module.YEAR:
            raise ImputationRefusee(
                f"IJ imputées pour {annee} : le CCSS de mai 2026 est lu pour "
                f"{ij_module.YEAR}, et une autre année demanderait de vieillir la masse, "
                f"ce qui n'est pas fait (D-305) ; "
                f"{_pourquoi(reform, [IJ]) or 'demandées par l’appelant'}")
    if CONSOMMATION in voulues:
        from impots import consommation

        try:
            consommation.annee_servie(annee)
        except consommation.ConsommationError as error:
            raise ImputationRefusee(str(error)) from error
    return Imputations(**{nom: nom in voulues for nom in CATALOGUE})


def _pourquoi(reform: Any, noms: Iterable[str]) -> str:
    """Les boutons de `reform` qui exigent chacune de `noms`."""
    from impots import consommation
    from impots.engine.reforms import CAPITAL_KNOBS

    knobs = _knobs(reform)
    par_nom = {CAPITAL: knobs & CAPITAL_KNOBS,
               CONSOMMATION: {k for k in knobs if k in consommation.BOUTONS},
               IJ: knobs & IJ_KNOBS, MENAGES: knobs & menages_knobs()}
    return " ; ".join(f"{nom} : {', '.join(sorted(par_nom.get(nom, ())))}"
                      for nom in noms if par_nom.get(nom))
