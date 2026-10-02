"""Ce qu'une chaîne doit être avant de devenir un morceau de nom de fichier (D-173).

Un nom de scénario est un identifiant depuis D-094. Le millésime ne l'était pas : il
s'interpole dans `population_{v}.parquet`, `firms_{v}.parquet`, `baseline_{v}.json`… et,
pour une table de cellules, il est lu DANS le fichier fourni — c'est alors le contenu du
fichier qui choisirait où l'on écrit.
"""

from __future__ import annotations

import re

#: Lettres, chiffres, « _ » et « - » : ni point, ni séparateur, 32 caractères au plus.
#: Les millésimes en usage — « 2024 », « 2023 », « fixture » — y tiennent tous.
_MILLESIME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,31}")


class IdentifiantError(ValueError):
    """Une chaîne qui devait nommer un fichier aurait pu en désigner un autre."""


def millesime(valeur: object) -> str:
    """Le millésime, vérifié, ou un refus — jamais une version nettoyée.

    `fullmatch`, pas `match` : avec `$`, `re.match` accepte un saut de ligne final, et
    c'est le défaut que portait la garde des noms de scénario (D-173). Sert aussi de
    `type=` à argparse, qui transforme le refus en erreur d'usage.
    """
    texte = str(valeur)
    if not _MILLESIME.fullmatch(texte):
        raise IdentifiantError(
            f"« {texte} » n'est pas un millésime. Un millésime nomme un fichier — "
            f"lettres, chiffres, « _ », « - », 32 caractères au plus — et jamais un "
            f"chemin."
        )
    return texte
