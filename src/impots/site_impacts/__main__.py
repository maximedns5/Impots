"""`python -m impots.site_impacts servir [port] | ecrire [dossier]` (D-607)."""

import sys
from pathlib import Path

from impots.site_impacts import LOCAL, ecrire, servir

args = sys.argv[1:]
if not args or args[0] not in ("servir", "ecrire"):
    sys.exit("usage : python -m impots.site_impacts servir [port] | ecrire [dossier]")
if args[0] == "ecrire":
    print(f"-> {ecrire(Path(args[1]) if len(args) > 1 else LOCAL)}")
else:
    servir(port=int(args[1]) if len(args) > 1 else 8001)
