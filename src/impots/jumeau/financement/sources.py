"""Les parts des sous-secteurs, lues une fois dans les tables publiées (D-481).

`python -m impots.jumeau.financement.sources ecrire` lit, dans `data/raw/` (hors git) :

* la t. 3.201 (le compte consolidé des APU, celui du jumeau) et les t. 3.203 (État,
  S13111), 3.204 (ODAC, S13112), 3.205 (APUL, S1313) et 3.212 (ASSO, S1314) de l'Insee,
  comptes nationaux annuels base 2020, millésime 2025 ;
* la dette de Maastricht par sous-secteur (Insee, `insee_dette_maastricht_detail.xlsx`,
  tableau 1, fin 2025),

et écrit `jumeau/parametres/financement_sous_secteurs.yaml`, que le jumeau lit sans
toucher aux données (le navigateur n'en lit aucune). Chaque nombre y garde sa table et sa
ligne. La lecture refuse une ligne du compte du jumeau qu'une table n'imprime pas, et une
ligne dont la somme des sous-secteurs s'écarte de la t. 3.201 hors des trois opérations
que la note de la t. 3.215 dit consolidées entre sous-secteurs (D41, D73 hors D733, D9) :
au-delà de l'arrondi de publication (5e-4 Md€), c'est une erreur, pas un résidu.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

import yaml

from impots.jumeau.champs import APU_DEPENSES, APU_RECETTES

ROOT = Path(__file__).resolve().parents[4]
RAW = ROOT / "data" / "raw"
SORTIE = Path(__file__).resolve().parents[1] / "parametres" / "financement_sous_secteurs.yaml"
ANNEE = 2025
S13 = "insee_cn2025_t3201_depenses_recettes_APU_S13.xlsx"
SOUS_SECTEURS = {
    "etat": ("3.203", "insee_cn2025_t3203_depenses_recettes_sous_secteur.xlsx", "S13111"),
    "odac": ("3.204", "insee_cn2025_t3204_depenses_recettes_sous_secteur.xlsx", "S13112"),
    "apul": ("3.205", "insee_cn2025_t3205_depenses_recettes_sous_secteur.xlsx", "S1313"),
    "asso": ("3.212", "insee_cn2025_t3212_depenses_recettes_sous_secteur.xlsx", "S1314"),
}
DETTE = "insee_dette_maastricht_detail.xlsx"
DETTE_LIGNES = {"etat": "dont Etat", "odac": "Organismes divers d'adm. centrale",
                "apul": "Administrations publiques locales",
                "asso": "Administrations de sécurité sociale"}
ARRONDI = 5e-4
#: Les opérations consolidées entre sous-secteurs (note (*) de la t. 3.201, t. 3.215).
CONSOLIDEES = ("apu_r_d73", "apu_d_d73", "apu_r_d9", "apu_d_d9", "interets_recus",
               "interets_verses")
INTERETS = {"interets_verses": ("DEPENSES", "Intérêts (D41)"),
            "interets_recus": ("RECETTES", "Intérêts (D41)")}


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def lire_table(chemin: Path) -> dict[tuple[str, str], dict[int, float]]:
    """{(section, libellé normalisé): {année: Md€}} d'une table 3.20x de l'Insee."""
    import openpyxl

    rows = list(openpyxl.load_workbook(chemin, read_only=True).worksheets[0]
                .iter_rows(values_only=True))
    entete, out, section = rows[2], {}, "?"
    for r in rows[3:]:
        if r[1] is None or not _norm(str(r[1])):
            continue
        lib = _norm(str(r[1]))
        if lib in ("DEPENSES", "RECETTES", "SOLDES"):
            section = lib
            continue
        out[(section, lib)] = {int(h): float(v) for h, v in zip(entete, r, strict=False)
                               if isinstance(h, int) and isinstance(v, (int, float))}
    return out


def _cles() -> dict[str, tuple[str, str]]:
    cles = {nom: ("RECETTES", _norm(lib)) for nom, _, _, lib in APU_RECETTES}
    cles |= {nom: ("DEPENSES", _norm(lib)) for nom, _, _, lib in APU_DEPENSES}
    return cles | INTERETS


def lire_dette() -> dict[str, float]:
    import openpyxl

    rows = list(openpyxl.load_workbook(RAW / DETTE, read_only=True).worksheets[0]
                .iter_rows(values_only=True))
    entete = next(r for r in rows if r[3] == "1995T4")
    j = list(entete).index(f"{ANNEE}T4")
    out = {}
    for s, lib in DETTE_LIGNES.items():
        ligne = next(r for r in rows if r[0] and _norm(str(r[0])) == _norm(lib))
        out[s] = float(ligne[j]) / 1000.0
    return out


def construire() -> dict[str, Any]:
    s13 = lire_table(RAW / S13)
    tables = {s: lire_table(RAW / f) for s, (_, f, _) in SOUS_SECTEURS.items()}
    lignes: dict[str, Any] = {}
    for nom, cle in _cles().items():
        if cle not in s13:
            raise ValueError(f"t. 3.201 : ligne « {cle[1]} » absente")
        total = s13[cle][ANNEE]
        valeurs = {}
        for s, t in tables.items():
            if cle not in t or ANNEE not in t[cle]:
                raise ValueError(f"t. {SOUS_SECTEURS[s][0]} : ligne « {cle[1]} » absente")
            valeurs[s] = round(t[cle][ANNEE], 6)
        consolidation = round(sum(valeurs.values()) - total, 6)
        if nom not in CONSOLIDEES and abs(consolidation) > ARRONDI:
            raise ValueError(f"« {nom} » : la somme des sous-secteurs s'écarte de la "
                             f"t. 3.201 de {consolidation:+.4f} Md€ hors consolidation")
        lignes[nom] = {"s13": round(total, 6), **valeurs, "consolidation": consolidation,
                       "ligne": cle[1], "section": cle[0]}
    b9 = {s: round(t[("SOLDES", "Capacité (+) ou besoin (-) de financement (B9NF)")][ANNEE], 6)
          for s, t in tables.items()}
    b9_s13 = s13[("SOLDES", "Capacité (+) ou besoin (-) de financement (B9NF)")][ANNEE]
    dette = lire_dette()
    return {
        "annee": ANNEE,
        "source": ("Insee, comptes nationaux annuels base 2020, millésime 2025 : t. 3.201 "
                   "(S13, consolidé) ; t. 3.203 (État), 3.204 (ODAC), 3.205 (APUL), 3.212 "
                   "(ASSO), consolidées dans le sous-secteur, pas entre sous-secteurs (note "
                   "de la t. 3.215). URL : https://www.insee.fr/fr/statistiques/fichier/"
                   "8988845/T_32xx_fr.xlsx ; écrit par `python -m "
                   "impots.jumeau.financement.sources ecrire`"),
        "lignes": lignes,
        "b9": {"s13": round(b9_s13, 6), **b9},
        "dette": {"annee": f"{ANNEE}T4", **{s: round(v, 6) for s, v in dette.items()},
                  "source": "Insee, « Dette de Maastricht des APU, répartition par "
                            "sous-secteur et par instrument », tableau 1, fin 2025 (Md€) ; "
                            "data/raw/insee_dette_maastricht_detail.xlsx"},
    }


def ecrire() -> Path:
    d = construire()
    entete = ("# Écrit par `python -m impots.jumeau.financement.sources ecrire` (D-481) ; "
              "ne pas éditer à la main.\n")
    SORTIE.write_text(entete + yaml.safe_dump(d, allow_unicode=True, sort_keys=False,
                                              width=88), encoding="utf-8")
    return SORTIE


if __name__ == "__main__":
    if sys.argv[1:] == ["ecrire"]:
        print(ecrire())
    else:
        raise SystemExit("usage : python -m impots.jumeau.financement.sources ecrire")
