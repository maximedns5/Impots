#!/usr/bin/env python
"""La table poste → taux de TVA de 2026, tirée de docs/consommation/regles.md (D-323).

Chaque poste feuille de l'enquête Budget de famille (cinq positions, chiffres ou lettres :
`01111`, `0114A`, `022ZZ`) reçoit son taux de 2026, tel que la table de la recherche le lit
dans la loi. La division 13, hors du champ de la consommation (impôts, remboursements,
transferts, gros travaux), est écartée. Les postes qui mêlent plusieurs taux, ou un régime
de marge, sans clé publiée prennent le taux de leur contenu principal, écrit ici avec sa
raison, et leurs bornes : chaque vérification est faite aussi au taux le plus bas et au plus
haut (D-323, D-324). Écrit `src/impots/consommation_postes_2026.csv` ; un test refuse que
la table commitée dérive de ce script.
"""

from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGLES = ROOT / "docs" / "consommation" / "regles.md"
SORTIE = ROOT / "src" / "impots" / "consommation_postes_2026.csv"

#: Les postes mêlés : (taux principal, taux le plus bas, taux le plus haut, raison).
MIXTES: dict[str, tuple[float, float, float, str]] = {
    "01114": (0.055, 0.055, 0.10, "vendu à emporter, sauf consommation immédiate"),
    "01133": (0.055, 0.055, 0.20, "le caviar seul à 20 %"),
    "0115B": (0.20, 0.055, 0.20, "margarines et graisses végétales, l'essentiel du poste"),
    "0118A": (0.055, 0.055, 0.20, "confitures, miel, glaces, chocolat au lait ; le reste à 20 %"),
    "04121": (0.0, 0.0, 0.10, "loyers d'habitation exonérés ; meublés de tourisme à 10 %"),
    "0431Z": (0.20, 0.10, 0.20, "fournitures achetées par le ménage ; travaux facturés à 10 %"),
    "04431": (0.055, 0.055, 0.10, "eau potable ; assainissement à 10 %"),
    "045AZ": (0.10, 0.055, 0.20, "bois de chauffage ; charbon à 20 %, réseau de chaleur à "
                                  "5,5 % ou 20 %"),
    "051AZ": (0.20, 0.10, 0.20, "tapis et revêtements ; pose par une entreprise à 10 %"),
    "0711Z": (0.20, 0.0, 0.20, "le neuf ; l'occasion paie sur la marge du professionnel, ou "
                               "rien entre particuliers"),
    "07121": (0.20, 0.0, 0.20, "le neuf ; l'occasion comme 0711Z"),
    "07131": (0.20, 0.0, 0.20, "le neuf ; l'occasion comme 0711Z"),
    "073ZZ": (0.10, 0.0, 0.10, "transport intérieur de voyageurs ; aérien international "
                               "exonéré"),
    "04441": (0.10, 0.0, 0.20, "charges collectives : entretien à 10 %, personnel hors TVA, "
                               "chauffage à 20 % ; composition non publiée"),
    "04511": (0.20, 0.055, 0.20, "20 % sur toute la facture depuis le 1/8/2025 ; "
                                 "l'abonnement était à 5,5 % avant"),
    "0452Z": (0.20, 0.055, 0.20, "20 % sur toute la facture depuis le 1/8/2025 ; "
                                 "l'abonnement était à 5,5 % avant"),
    "04611": (0.0, 0.0, 0.20, "cadeau d'un loyer exonéré ou d'un bien à 20 %"),
    "0531Z": (0.20, 0.055, 0.20, "pompes à chaleur posées à 5,5 % depuis 2026"),
    "0562Z": (0.0, 0.0, 0.10, "emploi direct hors TVA ; organismes déclarés à 10 %"),
    "0611Z": (0.021, 0.021, 0.20, "médicaments remboursables ; non remboursables à 10 %, "
                                  "appareillages à 5,5 %, le reste à 20 %"),
    "0741Z": (0.20, 0.0, 0.20, "séjours et cadeaux, contenu non décrit"),
    "08111": (0.0, 0.0, 0.20, "service universel postal exonéré ; autres envois à 20 %"),
    "09321": (0.10, 0.10, 0.20, "plantes et fleurs ; accessoires et livraison à 20 %"),
    "09411": (0.10, 0.0, 0.10, "droits d'admission ; spectacles sportifs à 5,5 %, "
                               "cotisations d'associations exonérées"),
    "0942Z": (0.055, 0.021, 0.10, "cinéma, théâtre, concerts ; musées à 10 %, premières "
                                  "représentations à 2,1 %"),
    "09521": (0.021, 0.021, 0.20, "publications de presse ; autres périodiques à 20 %"),
    "09611": (0.0, 0.0, 0.20, "régime de la marge : 20 % sur la seule marge de l'agence"),
    "0971Z": (0.20, 0.0, 0.20, "séjours et cadeaux, contenu non décrit"),
    "10141": (0.0, 0.0, 0.10, "enseignement exonéré ; soutien scolaire déclaré à 10 %"),
    "11111": (0.10, 0.10, 0.20, "repas et boissons sans alcool ; alcool à 20 %"),
    "11112": (0.10, 0.10, 0.20, "consommations sans alcool ; alcool à 20 %"),
    "11121": (0.055, 0.0, 0.10, "repas fournis par un prestataire ; cantine gérée par "
                                "l'établissement exonérée"),
    "11211": (0.10, 0.0, 0.10, "hôtellerie ; location meublée sans services exonérée"),
    "12111": (0.20, 0.10, 0.20, "coiffure et esthétique ; soins thermaux à 10 %"),
    "1212Z": (0.20, 0.055, 0.20, "le poste ; protections hygiéniques et préservatifs à 5,5 %"),
    "12411": (0.0, 0.0, 0.10, "assistantes maternelles salariées et établissements publics "
                              "hors TVA"),
}

#: Les postes qui portent une accise sur l'énergie, et laquelle. La facture commune
#: d'électricité et de gaz (04500) est répartie entre les deux par l'imputation (R11).
ENERGIE = {"04500": "electricite_gaz", "04511": "electricite", "0452Z": "gaz",
           "0453Z": "fioul", "07221": "carburants"}

TAUX = {"20": 0.20, "10": 0.10, "5,5": 0.055, "2,1": 0.021}


def lire() -> list[dict[str, str]]:
    lignes = []
    for line in REGLES.read_text(encoding="utf-8").splitlines():
        if not re.match(r"^\| [0-9]{3}[0-9A-Z]{2} \|", line):
            continue
        code, libelle, euros, cellule, _ = (c.strip() for c in line.strip().strip("|")
                                            .split(" | "))
        if code.startswith("13"):
            continue
        if cellule.upper().startswith("HORS CHAMP"):
            raise SystemExit(f"{code} : hors champ hors de la division 13, sans décision")
        if code in MIXTES:
            taux, bas, haut, raison = MIXTES[code]
            if not bas <= taux <= haut:
                raise SystemExit(f"{code} : le taux {taux} n'est pas entre ses bornes "
                                 f"{bas} et {haut}")
        elif re.search(r"MIXTE|MARGE", cellule, re.IGNORECASE):
            raise SystemExit(f"{code} : poste mêlé sans décision ({cellule[:80]})")
        else:
            sans_refs = re.sub(r"\[[^\]]*\]", "", cellule)
            trouves = re.findall(r"(?<![\d,])(20|10|5,5|2,1)(?![\d,])", sans_refs)
            exonere = "EXON" in cellule.upper()
            if len(set(trouves)) + exonere != 1:
                raise SystemExit(f"{code} : taux ambigu sans décision ({cellule[:80]})")
            taux = 0.0 if exonere else TAUX[trouves[0]]
            bas = haut = taux
            raison = ""
        lignes.append({"code": code, "libelle": libelle, "euros_2017": euros,
                       "taux": f"{taux:g}", "taux_bas": f"{bas:g}", "taux_haut": f"{haut:g}",
                       "mixte": "1" if code in MIXTES else "0",
                       "energie": ENERGIE.get(code, ""), "raison": raison,
                       "reference": cellule})
    absents = sorted(set(MIXTES) - {x["code"] for x in lignes})
    if absents:
        raise SystemExit(f"des décisions pour des postes absents de la table : {absents}")
    return lignes


def ecrire(lignes: list[dict[str, str]], path: Path = SORTIE) -> str:
    import io

    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(lignes[0]), lineterminator="\n")
    w.writeheader()
    w.writerows(lignes)
    path.write_text(buf.getvalue(), encoding="utf-8")
    return buf.getvalue()


if __name__ == "__main__":
    lignes = lire()
    ecrire(lignes)
    print(f"-> {SORTIE.relative_to(ROOT)} ({len(lignes)} postes, "
          f"{sum(x['mixte'] == '1' for x in lignes)} mêlés)")
    sys.exit(0)
