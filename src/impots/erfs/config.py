"""ERFS interrupt E0(1) — how the code reaches the delivery, and why never by a literal.

The ERFS 2022 FPR delivery is held under a signed convention and lives OUTSIDE this
repository. Code finds it through an **untracked local configuration** — an environment
variable, or a file in the user's home — and never through a path written into git.

WHY A LITERAL WOULD BE WORSE THAN AN ERROR. A hardcoded path works on exactly one machine.
Everywhere else it does not fail loudly: it resolves to nothing, the loader finds no rows,
and whatever is computed downstream is computed on emptiness. This project has met that
shape repeatedly — an Ésane sheet iterated with no `max_row` yielding zero rows and a sum of
zero; a decile column of strings a numeric filter silently dropped. A missing path must
raise, and this module raises.

WHAT IT REFUSES, AND WHY EACH REFUSAL EARNS ITS PLACE:

* **No default location.** Not even the ruled one. A default would mean code that appears to
  work on the owner's machine and silently reads nothing anywhere else, which is the failure
  above wearing a convenience's clothes.
* **The directory must exist and carry the expected tables**, checked at resolution rather
  than at first read — so the error names the configuration, not a stack fifty frames later
  inside a CSV parser.
* **Nothing from here is ever written back into the repository.** This module returns paths;
  every guard against committing what they point at lives in
  `scripts/check_no_data_committed.py`, which refuses both ERFS-named files and a workspace
  path literal in code, each proven against a dummy offender.
"""

from __future__ import annotations

import os
from pathlib import Path

#: The environment variable, checked first so a session can point at a copy without editing
#: anything. Named for the project rather than the dataset: a second restricted delivery
#: would get its own variable rather than quietly reusing this one.
ENV_VAR = "IMPOTS_ERFS_DIR"

#: The fallback: one line in the user's home, outside every repository. `KEY=value`, and
#: comment lines beginning with `#` are ignored so the file can explain itself.
LOCAL_CONFIG = Path.home() / ".impots.local"

#: The two tables the FPR delivery carries. There is no foyer table — a fact the validation
#: stage has to respect rather than discover.
TABLES = ("fpr_menage_2022.csv", "fpr_indiv_2022.csv")


class ErfsNotConfigured(RuntimeError):
    """The ERFS delivery was asked for and the local configuration does not point at it."""


def _from_local_config() -> str | None:
    if not LOCAL_CONFIG.exists():
        return None
    for line in LOCAL_CONFIG.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        if key.strip() == ENV_VAR:
            return value.strip().strip('"').strip("'")
    return None


def erfs_dir() -> Path:
    """The directory holding the two FPR tables. Raises if not configured or not there."""
    raw = os.environ.get(ENV_VAR) or _from_local_config()
    if not raw:
        raise ErfsNotConfigured(
            f"ERFS non configuré. Renseigner {ENV_VAR} dans l'environnement, ou une ligne "
            f"« {ENV_VAR}=/chemin/vers/Csv » dans {LOCAL_CONFIG}. "
            f"Aucun défaut n'est appliqué : un chemin par défaut fonctionnerait sur une "
            f"machine et lirait zéro ligne en silence sur toutes les autres.")
    path = Path(raw).expanduser()
    if not path.is_dir():
        raise ErfsNotConfigured(
            f"{ENV_VAR} pointe sur « {path} », qui n'est pas un répertoire.")
    missing = [name for name in TABLES if not (path / name).exists()]
    if missing:
        raise ErfsNotConfigured(
            f"{path} ne porte pas {missing}. La vérification a lieu ICI, à la résolution, "
            f"pour que l'erreur nomme la configuration plutôt que de surgir cinquante "
            f"appels plus loin dans un parseur CSV, sur un tableau vide.")
    return path


def is_configured() -> bool:
    """Whether ERFS is available. Every ERFS-backed path is opt-in and absent from CI."""
    try:
        erfs_dir()
    except ErfsNotConfigured:
        return False
    return True
