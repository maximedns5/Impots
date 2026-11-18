"""Une proposition composée par le lecteur (but 29, volet `tableau`, D-605).

Le lecteur choisit des mesures dans la bibliothèque que la page du jumeau lit déjà (les
rapports d'étude commités : les programmes, leurs mesures, les volets des textes) et des
lois hypothétiques (`navigateur.HYPOTHESES` : un instrument, un montant, des années), puis
règle, pour une mesure d'étude, son INTENSITÉ (`echelle`, k fois la mesure chiffrée) et
son ANNÉE D'ENTRÉE (`decalage`, d années plus tard). Le moteur la calcule comme un
programme : `trajectoire.calculer` avec toutes ses mesures, chacune son identifiant.

CE QUE FAIT UNE ÉCHELLE. Une mesure d'étude porte ce qu'une passe sur la population a
chiffré : son coût mécanique, ses impulsions, ses prélèvements, ses chocs par décile et
par impôt, et les statistiques suffisantes de ses canaux de comportement (D-336). k les
multiplie tous : la mesure à k fois son intensité, au premier ordre. Ce n'est pas une
passe : un barème deux fois plus fort ne coûte pas exactement deux fois plus (les effets
de seuil, les non-linéarités des barèmes, le comportement au second ordre). La mesure le
dit (`raison`), et chaque dimension qui la lit est « illustrative ».

CE QUE FAIT UN DÉCALAGE. Chaque année de la mesure passe d années plus tard ; ce qui sort
de 2035 est perdu. Les montants restent ceux de leur année d'origine, en euros courants :
ni la croissance ni les prix des années gagnées ne s'y ajoutent (une approximation, dite).

CE QUI EST REFUSÉ, avec sa raison : une échelle sur une hausse du Smic ou un seuil
d'allègements que lit le bloc `travail` (D-478, D-540) : la loi est dans la passe de la
première année et dans un coefficient, pas dans un montant ; un canal de comportement
dont la forme n'est pas connue ici ; une échelle négative ou nulle.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping
from typing import Any

#: Les bornes que la page propose ; le moteur accepte au-delà, la page non.
ECHELLE_MAX = 3.0
DECALAGE_MAX = 9


class PropositionError(ValueError):
    """Une proposition que le moteur ne sait pas calculer, et pourquoi."""


def _fois(d: Mapping[Any, Any] | None, k: float) -> dict[Any, Any] | None:
    """Chaque nombre d'un dictionnaire (imbriqué, listes comprises) fois k."""
    if d is None:
        return None

    def f(x: Any) -> Any:
        if isinstance(x, Mapping):
            return {c: f(v) for c, v in x.items()}
        if isinstance(x, list | tuple):
            return [f(v) for v in x]
        if isinstance(x, bool) or x is None:
            return x
        if isinstance(x, int | float):
            return float(x) * k
        return x

    return f(d)


#: La part de chaque canal de recettes que k multiplie (`predictif.rejouer.receipts`) :
#: chaque canal y est linéaire en ces nombres.
_CANAUX = {
    "c1_eti": ("A_bas", "A_haut"),
    "c7_labour_supply": ("S",),
    "c2_employment": ("anchor", "tail"),
    "c10_dividendes": ("delta_log",),
    "c11_autofinancement": ("tresor_eco",),
}


def _canaux(c: Mapping[str, Any] | None, k: float, ident: str) -> dict[str, Any] | None:
    if c is None:
        return None
    out: dict[str, Any] = {}
    for nom, stats in c.items():
        if nom not in _CANAUX:
            raise PropositionError(f"« {ident} » : canal de comportement « {nom} » dont la "
                                   f"mise à l'échelle n'est pas écrite (D-605)")
        stats = dict(stats)
        for cle in _CANAUX[nom]:
            if cle in stats:
                stats[cle] = _fois({"x": stats[cle]}, k)["x"]
        out[nom] = stats
    return out


def _decaler(d: Mapping[int, Any] | None, n: int, fin: int) -> dict[int, Any] | None:
    if d is None:
        return None
    return {int(a) + n: v for a, v in d.items() if int(a) + n <= fin}


def transformer(m: Any, *, echelle: float = 1.0, decalage: int = 0, identifiant: str,
                fin: int) -> tuple[Any, str | None]:
    """La mesure `m` à `echelle` fois son intensité et `decalage` ans plus tard, sous
    `identifiant` ; et la raison qui la rend illustrative, ou None si elle est intacte."""
    echelle, decalage = float(echelle), int(decalage)
    if not echelle > 0:
        raise PropositionError(f"« {m.libelle} » : échelle {echelle:g}, il la faut "
                               f"positive (retirer la mesure plutôt que la mettre à zéro)")
    if decalage < 0:
        raise PropositionError(f"« {m.libelle} » : une mesure ne s'avance pas avant "
                               f"l'année de son rapport (décalage {decalage})")
    if echelle != 1.0 and m.travail:
        raise PropositionError(
            f"« {m.libelle} » : une hausse du Smic ou un seuil d'allègements se lit par le "
            f"bloc `travail` dans la passe de sa première année (D-478, D-540) ; la mettre "
            f"à l'échelle demande une passe, pas une multiplication")
    raisons = []
    out = dataclasses.replace(m, identifiant=identifiant)
    if echelle != 1.0:
        k = echelle
        out = dataclasses.replace(
            out, chocs=_fois(out.chocs, k), impulsions=_fois(out.impulsions, k),
            prelevements=_fois(out.prelevements, k),
            prelevements_canal=_fois(out.prelevements_canal, k), couts=_fois(out.couts, k),
            canaux={a: _canaux(c, k, m.libelle) for a, c in out.canaux.items()},
            menages=_fois(out.menages, k), entreprises=_fois(out.entreprises, k),
            prelevements_publics=_fois(out.prelevements_publics, k))
        raisons.append(f"{f'{k:g}'.replace('.', ',')} fois la mesure chiffrée, au premier ordre : chaque montant "
                       f"de sa passe multiplié, pas une passe refaite")
    if decalage:
        n = decalage
        annees = tuple(a + n for a in out.annees if a + n <= fin)
        if not annees:
            raise PropositionError(f"« {m.libelle} » : décalée de {n} ans, elle sort de "
                                   f"l'horizon ({fin})")
        conventions = {axe: _decaler(a, n, fin) for axe, a in out.conventions.items()}
        out = dataclasses.replace(
            out, annees=annees, chocs=_decaler(out.chocs, n, fin),
            impulsions=_decaler(out.impulsions, n, fin),
            prelevements=_decaler(out.prelevements, n, fin),
            prelevements_canal=_decaler(out.prelevements_canal, n, fin),
            couts=_decaler(out.couts, n, fin), canaux=_decaler(out.canaux, n, fin),
            menages=_decaler(out.menages, n, fin),
            entreprises=_decaler(out.entreprises, n, fin),
            prelevements_publics=_decaler(out.prelevements_publics, n, fin),
            part_emplois_publics=_decaler(out.part_emplois_publics, n, fin),
            travail=_decaler(out.travail, n, fin), conventions=conventions)
        raisons.append(f"entrée {n} an{'s' if n > 1 else ''} plus tard, les montants de "
                       f"chaque année gardés en euros de leur année d'origine")
    return out, (" ; ".join(raisons) or None)
