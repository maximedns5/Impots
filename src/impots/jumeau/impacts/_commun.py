"""Ce que les dimensions du volet `tableau` partagent (D-606) : l'écart d'un champ de
l'état, sa bande sur les tirages des θ, et le statut que lit une proposition.

Les options que le tableau passe à chaque dimension (`navigateur.Session`, D-605) :

* `trajectoire` : la `Trajectoire` au réglage (un tirage) ; `variante` et `reference` en
  sont les états, année par année ;
* `tirages` : la même trajectoire, vectorisée sur des tirages des θ que le modèle lit,
  chacun selon sa loi (`a_priori`, D-424) : de forme (années, n) ; None si le réglage
  n'en demande pas ;
* `mesures` : les mesures ; `illustratives` : {identifiant : raison} pour celles dont le
  choc est déclaré (une loi hypothétique) ou transformé (`proposition.transformer`) ;
* `mode`, `thetas` (le registre des θ, leur origine dans `loi.origine`), `juge` (ce que
  dit le juge de l'histoire, D-439, `site_jumeau.juge`), `annees` (calculées).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np

#: Les quantiles de la bande, comme la plage de la page du jumeau (D-459) : 5 et 95 %.
QUANTILES = (5.0, 95.0)


def ecart(reference: Sequence[Any], variante: Sequence[Any], champ: str
          ) -> np.ndarray | None:
    """variante − référence d'un champ, (années, n) ; None s'il manque une année d'un
    côté : absent, jamais zéro."""
    if not all(e.present(champ) for e in (*reference, *variante)):
        return None
    return np.array([np.asarray(v[champ] - r[champ], dtype=float)
                     for r, v in zip(reference, variante, strict=True)])


def niveaux(etats: Sequence[Any], champ: str) -> np.ndarray | None:
    if not all(e.present(champ) for e in etats):
        return None
    return np.array([np.asarray(e[champ], dtype=float) for e in etats])


def serie(f: Any, options: Mapping[str, Any], reference: Sequence[Any],
          variante: Sequence[Any]) -> tuple[np.ndarray, np.ndarray | None,
                                            np.ndarray | None] | None:
    """La valeur au réglage et sa bande (5 et 95 % des tirages) d'un indicateur
    f(reference, variante) -> (années, n) ou None."""
    centre = f(reference, variante)
    if centre is None:
        return None
    valeurs = np.asarray(centre, dtype=float)[:, 0]
    bas = haut = None
    t = options.get("tirages")
    if t is not None and len(t.annees) == len(valeurs):
        x = f(t.reference, t.variante)
        if x is not None and np.asarray(x).shape[1] > 1:
            bas, haut = (np.percentile(np.asarray(x, dtype=float), q, axis=1)
                         for q in QUANTILES)
    return valeurs, bas, haut


def statut(options: Mapping[str, Any]) -> tuple[str, list[str]]:
    """« illustratif » quand une mesure est déclarée ou transformée (son choc n'est pas
    celui d'une passe), sinon « sourcé, non jugé » ; et les limites qui le disent."""
    ill = dict(options.get("illustratives") or {})
    if ill:
        return "illustratif", [f"« {i} » : {r}." for i, r in ill.items()]
    return "sourcé, non jugé", []


def thetas_sans_source(options: Mapping[str, Any]) -> list[str]:
    """Les θ que le modèle lit et dont la loi n'a pas d'estimation publiée (D-417)."""
    return sorted(t["cle"] for t in options.get("thetas") or ()
                  if t.get("lu") and (t.get("loi") or {}).get("origine") in
                  ("large", "magasin"))


def limite_bande(options: Mapping[str, Any]) -> str:
    t = options.get("tirages")
    if t is None:
        return "Sans bande : le réglage n'a pas demandé de tirages des θ."
    n = int(np.asarray(t.variante[0]["pib"]).size)
    return (f"La bande va de 5 à 95 % de {n} tirages des θ que le modèle lit, chacun selon "
            f"sa loi (D-424, D-459) : l'incertitude des réactions de l'économie, pas celle "
            f"du chiffrage de la mesure elle-même.")
