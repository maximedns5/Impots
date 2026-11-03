"""Les paramètres de la loi à un instant, sans les reconstruire à chaque fois (D-311).

openfisca construit, pour chaque instant qu'une formule lit, l'arbre entier des paramètres
à cet instant : 19 ms pour la loi de 2024, et un calcul de ménage au palier complet en lit
quelque 130. Il les garde dans un `functools.lru_cache` de 128 entrées, partagé par tous les
systèmes. Un calcul de référence en demande davantage : il reconstruisait 32 arbres à
chaque fois. Un système réformé neuf, lui, les reconstruisait tous, alors qu'une réforme ne
change que quelques feuilles.

Deux remèdes, qui ne changent aucune valeur lue :

* `memoriser` donne à un système son propre cache, sans limite de taille : il y a un arbre
  par instant lu, et un système en lit quelques centaines au plus.
* `greffer_sur` donne à un système réformé l'arbre de sa référence à chaque instant, où
  seules les branches que la réforme change sont refaites, à partir de ses propres
  paramètres. Les chemins de ces branches sont calculés une fois, à la construction, et
  l'arbre greffé est comparé à l'arbre complet avant que quiconque calcule avec.
"""

from __future__ import annotations

from typing import Any

from openfisca_core import periods
from openfisca_core.parameters import Parameter, ParameterNodeAtInstant, ParameterScale


class GreffeError(AssertionError):
    """L'arbre greffé d'un système réformé n'est pas son arbre complet."""


def instant_de(instant: Any) -> periods.Instant:
    """L'instant que lit `get_parameters_at_instant`, sous ses quatre formes."""
    if isinstance(instant, periods.Instant):
        return instant
    if isinstance(instant, periods.Period):
        return instant.start
    return periods.instant(instant)


def differences(base: Any, reforme: Any, chemin: tuple[str, ...] = ()) -> list[tuple[str, ...]]:
    """Les chemins des plus hauts nœuds où `reforme` diffère de `base`.

    Une feuille diffère si une de ses valeurs datées diffère ; un barème, si son type, le
    nombre de ses tranches ou l'une de leurs valeurs diffère, et il est alors refait
    entier. Un nœud dont les enfants ne sont pas les mêmes, dans le même ordre, est refait
    entier aussi : l'ordre des enfants est celui de l'arbre complet."""
    if type(base) is not type(reforme):
        return [chemin]
    if isinstance(reforme, Parameter):
        # The control of `greffer_sur` reads the trees' text, where a knob written back at
        # its law's integer value (3.0 over 3) differs, though `==` says equal: such a leaf
        # is grafted, or the control refused the reform (D-329).
        return [] if base == reforme and repr(base) == repr(reforme) else [chemin]
    if isinstance(reforme, ParameterScale):
        pareil = (base.metadata.get("type") == reforme.metadata.get("type")
                  and len(base.brackets) == len(reforme.brackets)
                  and all(not differences(b, r)
                          for b, r in zip(base.brackets, reforme.brackets, strict=True)))
        return [] if pareil else [chemin]
    if list(base.children) != list(reforme.children):
        return [chemin]
    sortie: list[tuple[str, ...]] = []
    for nom in reforme.children:
        sortie += differences(base.children[nom], reforme.children[nom], (*chemin, nom))
    return sortie


def _copie(noeud: ParameterNodeAtInstant) -> ParameterNodeAtInstant:
    neuf = ParameterNodeAtInstant.__new__(ParameterNodeAtInstant)
    neuf.__dict__ = dict(noeud.__dict__)
    neuf._children = dict(noeud._children)
    return neuf


def greffer(base_a: ParameterNodeAtInstant, racine_reforme: Any,
            chemins: list[tuple[str, ...]], instant: str) -> Any:
    """L'arbre de la réforme à `instant` : celui de la référence, où les nœuds des chemins
    et leurs ancêtres sont des copies, et les nœuds changés lus dans la réforme. Rien de
    l'arbre de la référence n'est modifié."""
    if () in chemins:
        return racine_reforme._get_at_instant(instant)
    copies = {(): _copie(base_a)}
    for chemin in chemins:
        parent, noeud_reforme = copies[()], racine_reforme
        for rang, nom in enumerate(chemin[:-1]):
            prefixe = chemin[:rang + 1]
            if prefixe not in copies:
                copies[prefixe] = _copie(parent._children[nom])
                parent._children[nom] = copies[prefixe]
                setattr(parent, nom, copies[prefixe])
            parent = copies[prefixe]
            noeud_reforme = noeud_reforme.children[nom]
        nom = chemin[-1]
        valeur = noeud_reforme.children[nom]._get_at_instant(instant)
        if valeur is None:
            parent._children.pop(nom, None)
            parent.__dict__.pop(nom, None)
        elif nom in parent._children:
            parent._children[nom] = valeur
            setattr(parent, nom, valeur)
        else:
            # Absente de la référence à cet instant : à sa place parmi les enfants.
            parent._children = {cle: (valeur if cle == nom else parent._children[cle])
                                for cle in noeud_reforme.children
                                if cle == nom or cle in parent._children}
            setattr(parent, nom, valeur)
    return copies[()]


def memoriser(systeme: Any) -> None:
    """Un cache des arbres par instant propre à `systeme`, sans limite de taille."""
    construire = type(systeme).get_parameters_at_instant.__wrapped__
    cache: dict[periods.Instant, Any] = {}

    def a_l_instant(instant: Any) -> Any:
        cle = instant_de(instant)
        if cle not in cache:
            cache[cle] = construire(systeme, cle)
        return cache[cle]

    systeme.get_parameters_at_instant = a_l_instant


def greffer_sur(systeme: Any, reference: Any, controles: tuple[str, ...]) -> None:
    """Les arbres de `systeme`, greffés sur ceux de `reference`, avec leur cache.

    Avant de rendre la main, l'arbre greffé est comparé à l'arbre complet à chacun des
    instants de `controles` : une différence que `differences` aurait manquée lève ici, et
    non dans un chiffre."""
    chemins = differences(reference.parameters, systeme.parameters)
    cache: dict[periods.Instant, Any] = {}

    def a_l_instant(instant: Any) -> Any:
        cle = instant_de(instant)
        if cle not in cache:
            cache[cle] = greffer(reference.get_parameters_at_instant(cle), systeme.parameters,
                                 chemins, str(cle))
        return cache[cle]

    for instant in controles:
        complet = repr(systeme.parameters.get_at_instant(instant))
        if repr(a_l_instant(instant)) != complet:
            raise GreffeError(
                f"au {instant}, les paramètres greffés de la réforme ne sont pas les siens : "
                f"{len(chemins)} chemins changés trouvés, un autre manque")
    systeme.get_parameters_at_instant = a_l_instant
