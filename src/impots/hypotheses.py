"""Les hypothèses économiques d'un texte financier, lues dans le texte (but 10, D-317).

Un cas se chiffre sur la population vieillie jusqu'à l'année qu'il chiffre. Les indices ne
sont pas une prévision de l'outil : ce sont ceux que le gouvernement a pris pour le texte
noté, lus dans ce texte, jamais dans sa fiche d'évaluation préalable.

Pour le PLF 2027, deux textes déposés le même jour, tous deux manifestés :

* **le PLF 2027** (AN, n° 3210), exposé général des motifs : les salaires par tête,
  +2,0 % en 2025 et en 2026, +2,7 % en 2027 ;
* **le PLFSS 2027** (AN, n° 3211), annexe B : le PIB en valeur, la masse salariale du
  secteur privé et l'inflation hors tabac, de 2025 à 2030. Le PLF ne donne pas
  l'inflation de 2025 ; le PLFSS donne une série entière, et la même pour 2026.

Les salaires par tête, et pas la masse salariale : la population garde ses emplois, et
vieillir chaque salaire par la masse compterait la croissance de l'emploi une seconde
fois. Chaque lecture est refusée si sa phrase ou sa ligne manque.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

RAW = Path(__file__).resolve().parents[2] / "data" / "raw"
PLF_2027 = RAW / "plf2027_texte_an_b3210.html"
PLFSS_2027 = RAW / "plfss2027_texte_an_b3211.html"

_SALAIRES_2026 = re.compile(
    r"Les salaires progresseraient de \+(\d,\d) % en (2026), comme en (2025)")
_SALAIRES_2027 = re.compile(
    r"les salaires accéléreraient \(\+(\d,\d) %\), tout comme la masse salariale "
    r"\(\+\d,\d %\)\. L.inflation refluerait légèrement à \+\d,\d % en moyenne annuelle "
    r"(\d{4})")
_RATE = r"(-?\d+,\d+) %"
_TABLE = re.compile(
    r"2025 2026 \(p\) 2027 \(p\) 2028 \(p\) 2029 \(p\) 2030 \(p\) "
    r"PIB en volume(?: -?\d+,\d+ %){6} "
    rf"PIB en valeur {_RATE} {_RATE} {_RATE} {_RATE} {_RATE} {_RATE} "
    rf"Masse salariale du secteur privé \* {_RATE} {_RATE} {_RATE} {_RATE} {_RATE} {_RATE} "
    rf"Inflation hors tabac {_RATE} {_RATE} {_RATE} {_RATE} {_RATE} {_RATE}")
_YEARS = (2025, 2026, 2027, 2028, 2029, 2030)

#: Les indices constatés (D-359, D-360, D-362), pour ramener une population en arrière.
#: Les prix : l'IPC hors tabac, ensemble des ménages, France, variation annuelle (Insee,
#: BDM 001768695), l'indice légal des pensions. Les salaires par tête : les salaires et
#: traitements bruts (D11) sur l'emploi intérieur salarié, total des branches, comptes
#: nationaux base 2020 (tableaux 6.205 et 6.210).
INSEE_IPC = RAW / "insee_bdm_001768695_ipc_hors_tabac_annuel.xml"
INSEE_D11 = RAW / "insee_cn2025_t6205_salaires_bruts_branches.xlsx"
INSEE_EMPLOI = RAW / "insee_cn2025_t6210_emploi_salarie_branches.xlsx"


class HypothesesError(RuntimeError):
    """Un texte ne dit pas les hypothèses qu'on lui fait dire."""


@dataclass(frozen=True)
class Hypotheses:
    """Les taux annuels d'un texte, par année : 0,02 pour 2 %."""

    texte: str
    salaires: dict[int, float]
    prix: dict[int, float]
    pib_valeur: dict[int, float]
    source: str
    constate: bool = False
    """Des indices constatés, et non une prévision : eux seuls ramènent une population en
    arrière (D-359). Un jeu de prévisions ne recule jamais."""


def _text(path: Path) -> str:
    if not path.exists():
        raise HypothesesError(f"{path.name} absent : `impots donnees` le télécharge "
                              "(manifeste)")
    raw = path.read_text(encoding="utf-8", errors="replace")
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", raw)))


def _rate(text: str) -> float:
    return float(text.replace(",", ".")) / 100


@lru_cache(maxsize=2)
def plf2027(plf: Path = PLF_2027, plfss: Path = PLFSS_2027) -> Hypotheses:
    """Les hypothèses du PLF 2027 et de son PLFSS, lues dans les deux textes."""
    exposé = _text(plf)
    found = _SALAIRES_2026.search(exposé)
    later = _SALAIRES_2027.search(exposé)
    if found is None or later is None:
        raise HypothesesError("PLF 2027, exposé général des motifs : la phrase des salaires "
                              "de 2025 et 2026, ou celle de 2027, manque")
    if later[2] != "2027":
        raise HypothesesError(f"PLF 2027 : les salaires « accéléreraient » en {later[2]}, "
                              "pas en 2027")
    salaires = {2025: _rate(found[1]), 2026: _rate(found[1]), 2027: _rate(later[1])}
    table = _TABLE.search(_text(plfss))
    if table is None:
        raise HypothesesError("PLFSS 2027, annexe B : le tableau des principales hypothèses "
                              "manque, ou ses années ne sont pas 2025 à 2030")
    values = [_rate(v) for v in table.groups()]
    pib = dict(zip(_YEARS, values[0:6], strict=True))
    prix = dict(zip(_YEARS, values[12:18], strict=True))
    for name, series in (("salaires", salaires), ("prix", prix), ("PIB en valeur", pib)):
        if not all(-0.05 < r < 0.10 for r in series.values()):
            raise HypothesesError(f"PLF 2027 : des taux de {name} hors de −5 % à +10 % "
                                  f"({series}) ; la lecture est fausse")
    return Hypotheses(
        texte="plf2027", salaires=salaires, prix=prix, pib_valeur=pib,
        source=("PLF 2027 (AN n° 3210), exposé général des motifs : salaires par tête ; "
                "PLFSS 2027 (AN n° 3211), annexe B : inflation hors tabac et PIB en valeur"))


def _ligne_totale(path: Path) -> dict[int, float]:
    """La ligne « _T » (total des branches) de l'onglet « en niveau » d'un tableau des
    comptes nationaux annuels, année par année."""
    import openpyxl

    if not path.exists():
        raise HypothesesError(f"{path.name} absent : `impots donnees` le télécharge "
                              "(manifeste).")
    book = openpyxl.load_workbook(path, read_only=True, data_only=True)
    sheet = next((ws for ws in book.worksheets if ws.title.strip().endswith("en niveau")),
                 None)
    if sheet is None:
        raise HypothesesError(f"{path.name} : pas d'onglet « en niveau »")
    rows = list(sheet.iter_rows(values_only=True))
    years = next((r for r in rows if r and any(str(c) == "2024" for c in r)), None)
    total = next((r for r in rows if r and r[0] == "_T"), None)
    if years is None or total is None:
        raise HypothesesError(f"{path.name} : pas de ligne des années ou de total « _T »")
    return {int(y): float(v) for y, v in zip(years, total, strict=True)
            if y is not None and str(y).isdigit() and isinstance(v, (int, float))}


def _ipc(path: Path) -> dict[int, float]:
    """Les variations annuelles de l'IPC hors tabac, en taux (0,018 pour 1,8 %)."""
    if not path.exists():
        raise HypothesesError(f"{path.name} absent : `impots donnees` le télécharge "
                              "(manifeste).")
    text = path.read_text(encoding="utf-8")
    if "Ensemble hors tabac" not in text or "Variations annuelles" not in text:
        raise HypothesesError(f"{path.name} n'est pas la série des variations annuelles "
                              "de l'IPC hors tabac")
    pairs = re.findall(r'TIME_PERIOD="(\d{4})"[^>]*?OBS_VALUE="(-?[\d.]+)"', text)
    if not pairs:
        raise HypothesesError(f"{path.name} : aucune observation lue")
    return {int(y): float(v) / 100.0 for y, v in pairs}


def insee_constate(ipc: Path = INSEE_IPC, d11: Path = INSEE_D11,
                   emploi: Path = INSEE_EMPLOI) -> Hypotheses:
    """Les indices constatés de l'Insee (D-362) : le salaire par tête est D11 sur
    l'emploi salarié, son taux le rapport de deux années ; les prix, l'IPC hors tabac.
    Le PIB en valeur n'y est pas : les entreprises reculent sur les comptes eux-mêmes."""
    masse, tetes = _ligne_totale(d11), _ligne_totale(emploi)
    smpt = {y: masse[y] / tetes[y] for y in masse if tetes.get(y)}
    salaires = {y: smpt[y] / smpt[y - 1] - 1.0 for y in smpt if y - 1 in smpt}
    return Hypotheses(
        texte="insee_constate", salaires=salaires, prix=_ipc(ipc), pib_valeur={},
        source=("Insee, constaté : salaires par tête, D11 sur l'emploi intérieur salarié "
                "(comptes nationaux base 2020, tableaux 6.205 et 6.210) ; prix, IPC hors "
                "tabac, ensemble des ménages, France (BDM 001768695)"),
        constate=True)


#: Les jeux d'hypothèses qu'une commande peut nommer.
JEUX = {"plf2027": plf2027, "insee_constate": insee_constate}


def jeu(nom: str) -> Hypotheses:
    if nom not in JEUX:
        raise HypothesesError(f"hypothèses « {nom} » inconnues ; connues : {sorted(JEUX)}")
    return JEUX[nom]()


def vieillissement_menages(nom: str, base: int, annee: int) -> tuple[object | None, dict]:
    """Ce qui vieillit une population de ménages de `base` à `annee` selon le jeu `nom` :
    l'`Uprating` des salaires et des prix année par année (aucun si les deux années sont
    la même), et ce que le registre en garde (D-317)."""
    from impots import uprating as up

    h = jeu(nom)
    if annee < base and not h.constate:
        raise HypothesesError(f"vieillir de {base} à {annee} reviendrait à rajeunir la "
                              "population")
    # Back, the rates are those of the years after the target, the base included
    # (`Uprating.factor`, D-359); forward, those after the base.
    years = (list(range(annee + 1, base + 1)) if annee < base
             else list(range(base + 1, annee + 1)))
    missing = [y for y in years if y not in h.salaires or y not in h.prix]
    if missing:
        raise HypothesesError(f"hypothèses « {nom} » : pas de taux pour {missing}")
    salaires = {y: h.salaires[y] for y in years}
    prix = {y: h.prix[y] for y in years}
    uprating = (up.Uprating.par_annee(salaires, prix, h.source, base) if years else None)
    record = {
        "jeu": nom, "source": h.source, "de": base, "vers": annee,
        "salaires": {str(y): r for y, r in salaires.items()},
        "prix": {str(y): r for y, r in prix.items()},
        "facteur_salaires": uprating.factor("wage", annee) if uprating else 1.0,
        "facteur_prix": uprating.factor("price", annee) if uprating else 1.0,
        "colonnes": dict(up.UPRATED),
    }
    return uprating, record


def vieillissement_entreprises(nom: str, base: int, annee: int,
                               gdp_of=None) -> tuple[float, dict]:
    """Le facteur qui vieillit le coût d'un millésime d'entreprises, la convention de la
    vue vieillie (D-246) : le PIB nominal de l'année sur celui du millésime, celui des
    comptes nationaux jusqu'à l'année de départ de la chaîne, puis le PIB en valeur du
    texte noté (D-317)."""
    from impots.dette import comptes
    from impots.predictif.chaine import START_YEAR

    gdp_of = gdp_of or comptes.gdp
    h = jeu(nom)
    if annee < base and not h.constate:
        raise HypothesesError(f"vieillir de {base} à {annee} remonterait le temps")
    if annee < base:
        # Back on the accounts alone, which are constated (D-362).
        accounts = gdp_of(sorted({annee, base}))
        factor = accounts[annee] / accounts[base]
        return factor, {
            "jeu": nom, "de": base, "vers": annee, "facteur": factor,
            "source": f"comptes nationaux (INSEE), de {base} ramené à {annee}",
            "pib_valeur": {},
            "convention": "le coût du millésime suit le PIB nominal (D-246)"}
    last = min(annee, START_YEAR)
    accounts = gdp_of(sorted({base, last}))
    factor = accounts[last] / accounts[base]
    later = list(range(START_YEAR + 1, annee + 1))
    missing = [y for y in later if y not in h.pib_valeur]
    if missing:
        raise HypothesesError(f"hypothèses « {nom} » : pas de PIB en valeur pour {missing}")
    for y in later:
        factor *= 1.0 + h.pib_valeur[y]
    record = {
        "jeu": nom, "de": base, "vers": annee, "facteur": factor,
        "source": (f"comptes nationaux (INSEE) de {base} à {last}"
                   + (f", puis {h.source}" if later else "")),
        "pib_valeur": {str(y): h.pib_valeur[y] for y in later},
        "convention": "le coût du millésime suit le PIB nominal (D-246)",
    }
    return factor, record
