"""Le texte des documents, extrait une fois (but 27, volet sources, D-491).

Chaque document de `data/raw/` est lu une fois et son texte gardé, page par page, dans
`data/interim/sources/texte/<fichier>.json` (hors git, reconstruit par
`python -m impots.sources texte`). Une page d'un PDF est une page du PDF (la numérotation
de `pdftotext`, à partir de 1, pas le folio imprimé) ; une page d'un classeur est une
feuille, chaque ligne préfixée de son numéro (`L12:`) ; une archive donne une page par
feuille de chacun de ses fichiers lisibles. Le cache porte l'empreinte du fichier lu : un
fichier changé est relu.

`nombres(texte)` lit les nombres d'une page à la française (« 27 181,7 », « 0,44 »,
« −0,52 ») comme à l'anglaise (« 122058.0 ») ; `trouver` dit où un nombre cité apparaît,
à son arrondi près. Ce module ne juge pas du sens : un nombre retrouvé sur la page dite
est un nombre présent, pas une ligne relue.
"""

from __future__ import annotations

import bisect
import hashlib
import html
import io
import json
import math
import re
import subprocess
import warnings
import zipfile
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from impots.donnees import RAW, ROOT

CACHE = ROOT / "data" / "interim" / "sources" / "texte"
#: La version de l'extraction : un cache d'une autre version est refait.
VERSION = 2
#: Les formats lus. Le reste (parquet, xml, gz) n'est pas lu, et c'est dit.
LUS = (".pdf", ".xlsx", ".xlsm", ".xls", ".csv", ".txt", ".html", ".htm", ".xml", ".zip",
       ".json")
#: Un fichier texte au-delà de cette taille n'est pas mis en cache (les grands CSV de
#: microdonnées ou d'open data se lisent par leur lecteur, pas par une recherche de texte).
TAILLE_MAX_TEXTE = 40_000_000
#: Au-delà de ce nombre de fichiers, une archive n'est lue que par ses fichiers nationaux.
MEMBRES_MAX = 30


#: Jamais ouverts (CLAUDE.md, brief du but 27) : les évaluations préalables des PLF et des
#: PLFSS, juges des chiffrages préenregistrés, et les chiffrages de tiers des programmes.
INTERDITS = re.compile(r"evaluations?[_ -]?prealables|annexe[_ -]?0?9|montaigne|ofce_chiffrage|"
                       r"ifrap", re.I)


class TexteError(RuntimeError):
    """Le document ne peut pas être lu."""


def empreinte(chemin: Path) -> str:
    h = hashlib.sha256()
    with chemin.open("rb") as f:
        for bloc in iter(lambda: f.read(1 << 20), b""):
            h.update(bloc)
    return h.hexdigest()


def _pdf(chemin: Path) -> list[tuple[str, str]]:
    sortie = subprocess.run(["pdftotext", "-layout", str(chemin), "-"], capture_output=True,
                            check=False)
    if sortie.returncode != 0:
        raise TexteError(f"pdftotext a échoué sur {chemin.name} : "
                         f"{sortie.stderr.decode(errors='replace')[:200]}")
    pages = sortie.stdout.decode("utf-8", errors="replace").split("\f")
    if pages and not pages[-1].strip():
        pages = pages[:-1]
    return [(str(i), p) for i, p in enumerate(pages, start=1)]


def _cellule(v: object) -> str:
    if isinstance(v, float):
        return format(v, ".15g")
    return "" if v is None else str(v)


def _xlsx(donnees: bytes, prefixe: str = "") -> list[tuple[str, str]]:
    import openpyxl

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            wb = openpyxl.load_workbook(io.BytesIO(donnees), read_only=True, data_only=True)
        except (ValueError, KeyError, OSError, zipfile.BadZipFile) as e:
            raise TexteError(f"classeur illisible par openpyxl : {e}") from e
    pages = []
    for ws in wb.worksheets:
        # Une dimension déclarée fausse (« A1 ») tronque la lecture en flux : on la relit.
        if hasattr(ws, "reset_dimensions"):
            ws.reset_dimensions()
        lignes = []
        for i, row in enumerate(ws.iter_rows(values_only=True), start=1):
            cells = [_cellule(v) for v in row]
            if any(cells):
                lignes.append(f"L{i}: " + "\t".join(cells).rstrip())
        pages.append((prefixe + ws.title, "\n".join(lignes)))
    wb.close()
    return pages


def _xls(donnees: bytes, prefixe: str) -> list[tuple[str, str]]:
    """Un classeur .xls, converti une fois en .xlsx par LibreOffice (aucune dépendance
    Python de plus) ; sans LibreOffice, il n'est pas lu, et c'est dit."""
    import shutil
    import tempfile

    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if soffice is None:
        raise TexteError("un .xls se lit par LibreOffice (soffice), absent ici")
    with tempfile.TemporaryDirectory() as d:
        src = Path(d) / "classeur.xls"
        src.write_bytes(donnees)
        subprocess.run([soffice, "--headless", "--convert-to", "xlsx", "--outdir", d,
                        str(src)], capture_output=True, check=False, timeout=300)
        out = Path(d) / "classeur.xlsx"
        if not out.exists():
            raise TexteError("LibreOffice n'a pas converti le .xls")
        return _xlsx(out.read_bytes(), prefixe)


def _texte_brut(donnees: bytes, nom: str) -> str:
    t = donnees.decode("utf-8", errors="replace")
    if nom.lower().endswith((".html", ".htm", ".xml")):
        t = re.sub(r"(?is)<(script|style).*?</\1>", " ", t)
        t = html.unescape(re.sub(r"<[^>]+>", " ", t))
        t = re.sub(r"[ \t]+", " ", t)
    return t


def _membre(donnees: bytes, nom: str, prefixe: str) -> list[tuple[str, str]]:
    bas = nom.lower()
    if len(donnees) > TAILLE_MAX_TEXTE:
        return []
    if bas.endswith(".pdf"):
        import tempfile

        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / "membre.pdf"
            src.write_bytes(donnees)
            return [(prefixe + p, texte) for p, texte in _pdf(src)]
    if bas.endswith((".xlsx", ".xlsm")):
        return _xlsx(donnees, prefixe)
    if bas.endswith(".xls"):
        return _xls(donnees, prefixe)
    if bas.endswith((".csv", ".txt", ".html", ".htm", ".xml", ".json")):
        if len(donnees) > TAILLE_MAX_TEXTE:
            return []
        return [(prefixe.rstrip(":") or "1", _texte_brut(donnees, nom))]
    return []


def lire(chemin: Path) -> list[tuple[str, str]]:
    """Les pages du document, lues sans cache : [(étiquette, texte)]."""
    nom = chemin.name
    bas = nom.lower()
    if INTERDITS.search(nom):
        raise TexteError(f"{nom} : jamais ouvert (évaluation préalable ou chiffrage de tiers)")
    if bas.endswith(".pdf"):
        return _pdf(chemin)
    if bas.endswith(".zip"):
        pages = []
        with zipfile.ZipFile(chemin) as z:
            membres = [i for i in z.infolist() if not i.is_dir()]
            if len(membres) > MEMBRES_MAX:
                # Une archive par département (IRCOM) : seul le fichier national est lu.
                membres = [i for i in membres if "nat" in Path(i.filename).name.lower()]
            for info in membres:
                try:
                    pages += _membre(z.read(info), info.filename, info.filename + ":")
                except TexteError:
                    continue  # un membre illisible n'empêche pas de lire les autres
        return pages
    if bas.endswith(LUS):
        if chemin.stat().st_size > TAILLE_MAX_TEXTE:
            raise TexteError(f"{nom} : {chemin.stat().st_size} octets, au-delà du plafond "
                             "de la recherche de texte")
        return _membre(chemin.read_bytes(), nom, "")
    raise TexteError(f"{nom} : format non lu ({chemin.suffix})")


def pages(fichier: str, *, reconstruire: bool = False) -> list[tuple[str, str]]:
    """Les pages d'un fichier de `data/raw/`, depuis le cache s'il est à jour."""
    chemin = RAW / fichier
    if INTERDITS.search(fichier):
        raise TexteError(f"{fichier} : jamais ouvert (évaluation préalable ou chiffrage de tiers)")
    if not chemin.exists():
        raise FileNotFoundError(f"{fichier} n'est pas dans data/raw/ (`make data`)")
    sha = empreinte(chemin)
    cache = CACHE / f"{fichier}.json"
    if cache.exists() and not reconstruire:
        lu = json.loads(cache.read_text(encoding="utf-8"))
        if lu.get("sha256") == sha and lu.get("version") == VERSION:
            return [tuple(p) for p in lu["pages"]]
    contenu = lire(chemin)
    CACHE.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps({"fichier": fichier, "sha256": sha, "version": VERSION,
                                 "pages": contenu},
                                ensure_ascii=False), encoding="utf-8")
    return contenu


# --------------------------------------------------------------------------- #
# les nombres
# --------------------------------------------------------------------------- #
#: Un nombre : groupes de milliers séparés par une espace (simple, insécable ou fine),
#: ou un nombre d'un bloc ; virgule ou point décimal ; exposant des flottants écrits.
_NOMBRE = re.compile(
    r"(?<![\w.,])(\d{1,3}(?:[ \u00a0\u202f]\d{3})+(?:,\d+)?|\d+(?:[.,]\d+)?(?:e[-+]?\d+)?)"
    r"(?![\w])")


@dataclass(frozen=True)
class Nombre:
    valeur: float
    decimales: int
    texte: str


def _decimales(s: str) -> int:
    s = s.lower()
    if "e" in s:
        mant, exp = s.split("e")
        return _decimales(mant) - int(exp)
    for sep in (",", "."):
        if sep in s:
            return len(s.split(sep)[1])
    return 0


def nombres(texte: str) -> list[Nombre]:
    """Les nombres d'un texte, en valeur absolue. Un groupe « 2 535 » est lu comme 2535 et
    aussi comme 2 et 535 : une colonne de tableau peut séparer deux nombres d'une espace."""
    out = []
    for m in _NOMBRE.finditer(texte):
        brut = m.group(1)
        morceaux = re.split(r"[ \u00a0\u202f]", brut)
        candidats = [brut.replace(" ", "").replace("\u00a0", "").replace("\u202f", "")]
        if len(morceaux) > 1:
            candidats += morceaux
        for c in candidats:
            dec = _decimales(c)
            try:
                v = float(c.replace(",", "."))
            except ValueError:
                continue
            out.append(Nombre(v, dec, c))
    return out


def decimales_citees(v: float) -> int:
    """La précision d'un nombre cité : ses décimales, ou moins ses zéros de queue s'il est
    entier (122 058 000 000 est cité au million près)."""
    if v == 0:
        return 0
    s = format(abs(v), ".12g")
    if "e" in s:
        return _decimales(s)
    if "." in s:
        return len(s.split(".")[1])
    return -(len(s) - len(s.rstrip("0")))


def chiffres_significatifs(v: float) -> int:
    s = format(abs(v), ".12g").replace(".", "").lstrip("0")
    if "e" in s:
        s = s.split("e")[0]
    return len(s.rstrip("0")) or 1


#: Les échelles essayées : un taux cité 0,69 s'écrit 69 %, un total cité en euros s'écrit
#: en milliards, millions ou milliers.
ECHELLES = (1.0, 100.0, 0.01, 1e-3, 1e3, 1e-6, 1e6, 1e-9)


@dataclass(frozen=True)
class Trouve:
    page: str
    lu: str
    echelle: float
    exact: bool


def correspond(v: float, n: Nombre, echelle: float) -> tuple[bool, bool]:
    """(correspond, exact) : le nombre lu vaut-il le nombre cité, à l'arrondi du plus
    grossier des deux ? Exact s'il le vaut à l'arrondi du nombre lu."""
    x = abs(v) * echelle
    if x == 0:
        return False, False
    dv = decimales_citees(v) - round(math.log10(echelle))
    demi_lu = 0.5 * 10.0 ** (-n.decimales)
    demi_cite = 0.5 * 10.0 ** (-dv)
    ecart = abs(n.valeur - x)
    tol = max(demi_lu, demi_cite, 1e-9 * x)
    # Un arrondi ne fait pas d'un 3 un 4 : l'écart relatif reste sous 5 %.
    if ecart <= tol and ecart <= 0.05 * x:
        return True, ecart <= max(demi_lu, 1e-9 * x)
    return False, False


class Index:
    """Les nombres d'un document, lus une fois et triés par page : une recherche est une
    bissection, pas une relecture du texte."""

    def __init__(self, contenu: list[tuple[str, str]]):
        self.pages: list[tuple[str, list[float], list[Nombre]]] = []
        for etiquette, texte in contenu:
            ns = sorted(nombres(texte), key=lambda n: n.valeur)
            self.pages.append((etiquette, [n.valeur for n in ns], ns))
        self.etiquettes = [e for e, _, _ in self.pages]

    def proches(self, x: float, rel: float, pages_dites: list[str] | None
                ) -> Iterator[tuple[str, Nombre]]:
        bas, haut = x * (1 - rel) - 0.5, x * (1 + rel) + 0.5
        for etiquette, valeurs, ns in self.pages:
            if pages_dites is not None and etiquette not in pages_dites:
                continue
            for j in range(bisect.bisect_left(valeurs, bas), bisect.bisect_right(valeurs,
                                                                                  haut)):
                yield etiquette, ns[j]


def _index(contenu: list[tuple[str, str]] | Index) -> Index:
    return contenu if isinstance(contenu, Index) else Index(contenu)


def _significatifs_lus(n: Nombre) -> int:
    s = n.texte.lower().split("e")[0].replace(",", "").replace(".", "").lstrip("0")
    return len(s) or 1


def trouver(v: float, contenu: list[tuple[str, str]] | Index, *,
            pages_dites: list[str] | None = None,
            echelles: tuple[float, ...] = ECHELLES) -> list[Trouve]:
    """Où le nombre cité apparaît : sur les pages dites si elles sont données, sinon
    partout. Les correspondances exactes d'abord.

    Un nombre lu trop court ne confirme pas un nombre cité précis : « 10 » sur une page
    ne retrouve pas 10,32 Md€. Le nombre lu doit avoir au moins min(3, chiffres du cité)
    chiffres significatifs sur une page dite, min(4, chiffres du cité) sans page."""
    idx = _index(contenu)
    if echelles is ECHELLES and abs(v) < 10:
        # Un taux ou une élasticité s'imprime tel quel ou en pour cent, pas en milliers.
        echelles = (1.0, 100.0)
    exige = min(3 if pages_dites is not None else 4, chiffres_significatifs(v))
    out = []
    for e in echelles:
        x = abs(v) * e
        if x == 0:
            continue
        for etiquette, n in idx.proches(x, 0.05, pages_dites):
            if _significatifs_lus(n) < exige:
                continue
            ok, exact = correspond(v, n, e)
            if ok:
                out.append(Trouve(etiquette, n.texte, e, exact))
    ordre = {p: i for i, p in enumerate(idx.etiquettes)}
    out.sort(key=lambda t: (not t.exact, t.echelle != 1.0, ordre.get(t.page, 0)))
    return out


def voisin(v: float, contenu: list[tuple[str, str]] | Index, pages_dites: list[str] | None,
           marge: float = 0.05) -> Trouve | None:
    """Le nombre lu le plus proche du nombre cité, à moins de `marge` en relatif, sur les
    pages dites : la piste d'un écart, à juger à l'œil."""
    idx = _index(contenu)
    meilleur, best = None, marge
    for e in ECHELLES:
        x = abs(v) * e
        if x == 0:
            continue
        for etiquette, n in idx.proches(x, marge, pages_dites):
            if n.decimales <= 0 and n.valeur < 100:
                continue  # trop court pour faire une piste
            r = abs(n.valeur / x - 1)
            if r < best and n.valeur != x:
                best, meilleur = r, Trouve(etiquette, n.texte, e, False)
    return meilleur
