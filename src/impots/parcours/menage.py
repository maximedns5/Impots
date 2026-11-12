"""Page 1 du parcours : un ménage. Elle prouve que le barème de l'impôt, le quotient
familial et la décote sont codés juste, sur deux ménages salariés simples, et dit ce que
ce contrôle ne couvre pas (les cotisations, la CSG, les prestations).

Elle montre trois ménages types (les cas d'or `tests/golden/single_30k`,
`couple_70k_2kids` et `single_240k`) ligne à ligne, l'exemple du README (une tranche à
50 % sur le célibataire à 240 000 €) et le contrôle à l'euro contre le simulateur de la
DGFiP (`tests/golden/CROSSCHECK.md`). Son curseur choisit un point d'une grille de ménages
types, salaire × situation, chiffrée d'avance : le site est statique et ne calcule rien.

LES NOMBRES VIENNENT DE TROIS FICHIERS COMMITÉS, jamais du texte :

* `reports/parcours/menages.json`, chiffré par le moteur des ménages
  (`impots.engine.compute`, celui de l'API) avec son commit et sa date ;
* `tests/golden/*.yaml`, les valeurs d'or que `tests/test_golden.py` tient à ±2 € ;
* `tests/golden/CROSSCHECK.md`, les montants relevés sur le simulateur de la DGFiP.

REFAIRE LE FICHIER DES MÉNAGES (trois minutes environ, une centaine de ménages ; aucune
population, aucun nombre d'étude) :

    cd <dépôt> && PYTHONPATH=src .venv/bin/python -m impots.parcours.menage

La commande refuse d'écrire un point dont les lignes ne retombent pas sur le revenu
disponible du moteur à un euro près, ou qui porte un montant que la page ne montre pas.
"""

from __future__ import annotations

import html
import json
import re
import subprocess
from datetime import date
from typing import Any

from impots.parcours import RAPPORTS, ROOT, Page, ParcoursError, fichier, source

ANNEE = 2024
"""L'année des revenus : celle des cas d'or et du contrôle DGFiP (l'impôt 2025 sur les
revenus 2024)."""
JSON = RAPPORTS / "menages.json"
CHEMIN_JSON = "reports/parcours/menages.json"
GOLDEN = ROOT / "tests" / "golden"
CROSSCHECK = "tests/golden/CROSSCHECK.md"
COMMANDE = "PYTHONPATH=src .venv/bin/python -m impots.parcours.menage"

#: Les trois ménages types, par leur cas d'or, et le cas de la réforme du README.
TYPES = ("single_30k", "couple_70k_2kids", "single_240k")
REFORME = "single_240k_toprate50"
#: Les deux cas que la DGFiP a refaits (CROSSCHECK.md).
CONTROLES = ("single_30k", "couple_70k_2kids")

#: La grille du curseur : le salaire brut annuel du ménage, en euros.
SALAIRES = (0, 10_000, 15_000, 20_000, 25_000, 30_000, 35_000, 40_000, 50_000, 60_000,
            70_000, 80_000, 90_000, 100_000, 120_000, 150_000, 200_000, 240_000, 300_000)
SALAIRE_DEFAUT = 30_000
#: La part du premier conjoint quand un couple a deux salaires.
PART_PREMIER = 0.6
NAISSANCE_ADULTES = (1985, 1987)
NAISSANCE_ENFANTS = (2015, 2018)

#: Les situations : (clé, libellé, adultes, salaires partagés, enfants, marié).
SITUATIONS: tuple[tuple[str, str, int, bool, int, bool], ...] = (
    ("seul", "Une personne seule, sans enfant", 1, False, 0, False),
    ("seul_2e", "Un parent seul, deux enfants", 1, False, 2, False),
    ("couple_1s", "Un couple marié sans enfant, un seul salaire", 2, False, 0, True),
    ("couple_2s", "Un couple marié sans enfant, deux salaires", 2, True, 0, True),
    ("couple_2s_2e", "Un couple marié, deux salaires, deux enfants", 2, True, 2, True),
)

#: Les prestations que la page montre, une ligne chacune.
PRESTATIONS = ("af", "cf", "asf", "ars", "ppa", "rsa", "aefa", "aide_logement")
#: Les variables qu'OpenFisca verse dans le revenu disponible et que le registre du moteur
#: (`engine/outputs.py`) n'extrait pas, lues à côté sur la même simulation. Vide : l'ARS,
#: qu'elle a d'abord portée, a sa ligne au registre depuis D-376.
HORS_REGISTRE: tuple[str, ...] = ()
#: La CRDS prélevée sur ces prestations, que le moteur stocke négative.
CRDS_PRESTATIONS = ("crds_pfam", "crds_logement", "crds_mini")
#: Ce que le moteur sait payer ou prélever et que ces ménages n'ont pas : la commande
#: refuse un point où l'un d'eux n'est pas nul, la page ne le montrerait pas.
ABSENTS = ("aeeh", "ass", "aah", "mva", "aspa", "asi", "reduction_loyer_solidarite",
           "csg_ij", "pfu", "prelevements_sociaux_capital", "cdhr", "ifi", "reductions",
           "credits_impot", "retraite_imposable", "chomage_brut", "pension_invalidite",
           "ria", "allocation_enfant", "garantie_autonomie")

#: Les lignes du calcul, dans l'ordre de la page : (clé, libellé, sens). Le sens dit
#: comment la ligne entre dans le revenu disponible : "+", "-", "=" pour un sous-total,
#: "" pour une ligne d'information qui n'y entre pas.
LIGNES: tuple[tuple[str, str, str], ...] = (
    ("salaire_super_brut", "Coût du travail pour l'employeur (super-brut)", ""),
    ("salaire_brut", "Salaire brut", "+"),
    ("cotisations_salariales", "Cotisations salariales", "-"),
    ("csg_deductible", "CSG déductible", "-"),
    ("csg_imposable", "CSG non déductible", "-"),
    ("crds", "CRDS sur le salaire", "-"),
    ("salaire_net", "Salaire net", "="),
    ("salaire_imposable", "Salaire imposable (net, plus la CSG non déductible et la CRDS)",
     ""),
    ("revenu_fiscal_reference", "Revenu fiscal de référence (après l'abattement de {taux}, "
     "plafonné à {plafond})", ""),
    ("parts_fiscales", "Parts fiscales", ""),
    ("ir_avant_reductions", "Impôt par le barème et le quotient familial, avant décote",
     ""),
    ("ir", "Impôt sur le revenu à payer", "-"),
    ("af", "Allocations familiales", "+"),
    ("cf", "Complément familial", "+"),
    ("asf", "Allocation de soutien familial", "+"),
    ("ars", "Allocation de rentrée scolaire", "+"),
    ("ppa", "Prime d'activité", "+"),
    ("rsa", "RSA", "+"),
    ("aefa", "Prime de Noël", "+"),
    ("aide_logement", "Aide au logement (aucun logement n'est déclaré)", "+"),
    ("crds_prestations", "CRDS sur les prestations", "-"),
    ("revenu_disponible", "Revenu disponible", "="),
)


# --------------------------------------------------------------------------- chiffrage

def _menage(situation: tuple, salaire: float) -> dict[str, Any]:
    _, _, adultes, partage, enfants, marie = situation
    if adultes == 1:
        salaires = [salaire]
    elif partage:
        premier = round(salaire * PART_PREMIER, 2)
        salaires = [premier, round(salaire - premier, 2)]
    else:
        salaires = [salaire, 0.0]
    return {
        "adults": [{"salaire_brut_annuel": s, "annee_naissance": NAISSANCE_ADULTES[i]}
                   for i, s in enumerate(salaires)],
        "children": [{"annee_naissance": a} for a in NAISSANCE_ENFANTS[:enfants]],
        "couple_marie_ou_pacse": marie,
    }


def _valeurs(rows: dict[str, Any], quoi: str) -> dict[str, float]:
    """Les lignes de la page, lues sur le moteur, et le contrôle qu'elles bouclent."""
    for key in ABSENTS:
        if abs(rows[key] or 0.0) > 0.005:
            raise ParcoursError(f"{quoi} : {key} = {rows[key]}, que la page ne montre pas.")
    out = {key: round(float(rows[key]), 2) for key, _, _ in LIGNES
           if key != "crds_prestations"}
    out["crds_prestations"] = round(-sum(float(rows[k]) for k in CRDS_PRESTATIONS), 2)
    out["prestations"] = round(sum(out[k] for k in PRESTATIONS) - out["crds_prestations"], 2)
    reste = out["revenu_disponible"] - (out["salaire_net"] + out["prestations"] - out["ir"])
    if abs(reste) > 1.0:
        raise ParcoursError(f"{quoi} : les lignes ne retombent pas sur le revenu disponible "
                            f"du moteur ({reste:+.2f} €).")
    net = (out["salaire_brut"] - out["cotisations_salariales"] - out["csg_deductible"]
           - out["csg_imposable"] - out["crds"])
    if abs(net - out["salaire_net"]) > 1.0:
        raise ParcoursError(f"{quoi} : le salaire net ne retombe pas sur ses lignes "
                            f"({net - out['salaire_net']:+.2f} €).")
    out["reste"] = round(reste, 2)
    return out


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True,
                          check=True).stdout.strip()


def chiffrer() -> dict[str, Any]:
    """Chiffre les ménages types et la grille du curseur avec le moteur des ménages."""
    import warnings

    import yaml

    from impots.api.schemas import HouseholdInput, ReformSpec
    from impots.engine import baseline, compute, outputs, versions
    from impots.engine import situations as engine_situations
    from impots.engine.compute import _build

    warnings.filterwarnings("ignore", category=RuntimeWarning, module="openfisca_france")

    def calcule(menage: dict[str, Any], quoi: str) -> dict[str, float]:
        # Les trois appels de `compute` pour la loi en vigueur, au tier complet, avec
        # l'historique des revenus (le défaut de l'API) ; puis les variables hors registre,
        # sur la même simulation.
        household = HouseholdInput.model_validate(menage)
        situation = engine_situations.build_situation(household, ANNEE, True)
        simulation = _build(baseline(), situation, ANNEE, "full")
        rows = outputs.extract(simulation, ANNEE, "full")
        for name in HORS_REGISTRE:
            rows[name] = round(float(simulation.calculate_add(name, str(ANNEE))[0]), 2)
        return _valeurs(rows, quoi)

    types = {}
    for nom in TYPES:
        cas = yaml.safe_load((GOLDEN / f"{nom}.yaml").read_text(encoding="utf-8"))
        if cas["year"] != ANNEE:
            raise ParcoursError(f"{nom} : le cas d'or est de {cas['year']}, pas de {ANNEE}.")
        types[nom] = {"menage": cas["household"], "valeurs": calcule(cas["household"], nom)}

    cas = yaml.safe_load((GOLDEN / f"{REFORME}.yaml").read_text(encoding="utf-8"))
    result = compute(HouseholdInput.model_validate(cas["household"]), cas["year"],
                     reform=ReformSpec.model_validate(cas["reform"]), tier="light")
    reforme = {"nom": REFORME, "menage": cas["household"], "bareme": cas["reform"]["ir_bareme"],
               "loi": {k: round(float(result.baseline[k]), 2)
                       for k in ("ir", "revenu_fiscal_reference", "salaire_imposable")},
               "reforme": {"ir": round(float(result.reform["ir"]), 2)},
               "ecart": {"ir": round(float(result.delta["ir"]), 2)}}

    bareme = baseline().parameters(f"{ANNEE}-01-01").impot_revenu.bareme_ir_depuis_1945.bareme
    situations = []
    for situation in SITUATIONS:
        points = [calcule(_menage(situation, s), f"{situation[0]} à {s} €") for s in SALAIRES]
        situations.append({"cle": situation[0], "libelle": situation[1],
                           "menages": [_menage(situation, s) for s in SALAIRES],
                           "valeurs": points})

    # Le code qui calcule : tout `src` hors des pages du parcours, qui ne font que lire.
    modifies = [line[3:] for line in _git("status", "--porcelain", "--", "src",
                                          ":(exclude)src/impots/parcours").splitlines()]
    return {
        "commit": _git("rev-parse", "HEAD"),
        "src_modifies_au_chiffrage": modifies,
        "date": date.today().isoformat(),
        "commande": COMMANDE,
        "annee": ANNEE,
        "moteur": versions(),
        "bareme": [[float(t), float(r)] for t, r in zip(bareme.thresholds, bareme.rates, strict=True)],
        "types": types,
        "reforme": reforme,
        "salaires": list(SALAIRES),
        "situations": situations,
    }


def ecrire() -> None:
    donnees = chiffrer()
    RAPPORTS.mkdir(parents=True, exist_ok=True)
    JSON.write_text(json.dumps(donnees, ensure_ascii=False, indent=1) + "\n",
                    encoding="utf-8")


# --------------------------------------------------------------------------- lecture

def donnees() -> dict[str, Any]:
    if not JSON.exists():
        raise ParcoursError(f"{CHEMIN_JSON} manque : `{COMMANDE}` le chiffre.")
    return json.loads(JSON.read_text(encoding="utf-8"))


def golden(nom: str) -> dict[str, Any]:
    import yaml
    return yaml.safe_load((GOLDEN / f"{nom}.yaml").read_text(encoding="utf-8"))


def _nombre(texte: str) -> float:
    return float(texte.replace("\u202f", "").replace("\u00a0", "").replace(" ", "")
                 .replace(",", "."))


def dgfip() -> dict[str, Any]:
    """Ce que CROSSCHECK.md a relevé sur le simulateur de la DGFiP, par cas : le salaire
    saisi, l'impôt, le revenu fiscal de référence, les droits simples, la décote et les
    parts ; et la date du relevé."""
    texte = (ROOT / CROSSCHECK).read_text(encoding="utf-8")
    statut = re.search(r"\*\*Status: DONE — (\d{4}-\d{2}-\d{2})\.", texte)
    if statut is None:
        raise ParcoursError(f"{CROSSCHECK} ne dit plus le contrôle fait, ni sa date.")
    cas: dict[str, Any] = {"date": statut[1]}
    for nom in CONTROLES:
        section = re.search(rf"### `{nom}`\n(.*?)(?=\n### |\n## )", texte, re.S)
        if section is None:
            raise ParcoursError(f"{CROSSCHECK} n'a plus de section pour {nom}.")
        corps = section[1]
        ligne = re.search(r"\| DGFiP simulator \| \*\*([\d  ]+) €\*\* \(RFR ([\d  ]+) €; "
                          r"droits simples ([\d  ]+) €; décote ([\d  ]+) €; parts ([\d,.]+);",
                          corps)
        if ligne is None:
            raise ParcoursError(f"{CROSSCHECK}, {nom} : la ligne du simulateur ne se lit plus.")
        saisis = re.findall(r"\| Salaires (?:déclarant \d )?\(case (1[AB]J)\) \| \*\*([\d  ]+) €",
                            corps)
        if not saisis:
            raise ParcoursError(f"{CROSSCHECK}, {nom} : les salaires saisis ne se lisent plus.")
        cas[nom] = {"ir": _nombre(ligne[1]), "revenu_fiscal_reference": _nombre(ligne[2]),
                    "droits_simples": _nombre(ligne[3]), "decote": _nombre(ligne[4]),
                    "parts_fiscales": _nombre(ligne[5]),
                    "saisis": [(case, _nombre(v)) for case, v in saisis]}
    return cas


def abattement(d: dict[str, Any]) -> tuple[float, float]:
    """Le taux et le plafond de l'abattement pour frais professionnels, lus dans les
    paramètres d'OpenFisca à l'année du fichier. Le célibataire à 240 000 € y est plafonné :
    son revenu fiscal doit être son salaire imposable moins ce plafond, sinon le fichier et
    les paramètres ne parlent plus de la même loi."""
    from impots.engine import baseline

    abatpro = (baseline().parameters(f"{d['annee']}-01-01")
               .impot_revenu.calcul_revenus_imposables.deductions.abatpro)
    taux, plafond = float(abatpro.taux), float(abatpro.max)
    v = d["types"]["single_240k"]["valeurs"]
    if round(v["salaire_imposable"] - v["revenu_fiscal_reference"]) != round(plafond):
        raise ParcoursError(f"single_240k : l'abattement du fichier n'est plus le plafond des "
                            f"paramètres ({eur(plafond)}).")
    return taux, plafond


def _lignes(d: dict[str, Any]) -> tuple[tuple[str, str, str], ...]:
    """Les lignes de la page, l'abattement lu dans les paramètres (`d["abattement"]`)."""
    taux, plafond = d["abattement"]
    return tuple((key, libelle.format(taux=f"{round(taux * 100)}\u202f%", plafond=eur(plafond)),
                  sens) for key, libelle, sens in LIGNES)


# --------------------------------------------------------------------------- rendu

STYLE = "tr.info td{color:var(--doux)}"

def eur(valeur: float, centimes: bool = False) -> str:
    """Un montant en euros, à la française : 1 274 €, ou 1 888,74 €."""
    texte = f"{valeur:,.2f}" if centimes else f"{round(valeur):,.0f}"
    texte = texte.replace(",", "\u202f").replace(".", ",")
    return texte.replace("-", "−") + "\u00a0€"


def _cellule(key: str, sens: str, valeurs: dict[str, float]) -> str:
    valeur = valeurs[key]
    if key == "parts_fiscales":
        return f"{valeur:g}".replace(".", ",")
    texte = eur(valeur)
    if sens == "-" and round(valeur) != 0:
        return "−\u202f" + texte
    return texte


def _ligne(key: str, libelle: str, sens: str, cellules: list[str]) -> str:
    fort = sens == "="
    tete = f"<strong>{html.escape(libelle)}</strong>" if fort else html.escape(libelle)
    tds = "".join(f'<td class="num">{"<strong>" + c + "</strong>" if fort else c}</td>'
                  for c in cellules)
    classe = ' class="info"' if sens == "" else ""
    return f"<tr{classe}><td>{tete}</td>{tds}</tr>"


def _description(menage: dict[str, Any]) -> str:
    adultes = menage["adults"]
    enfants = len(menage.get("children", []))
    if len(adultes) == 1:
        qui = "une personne seule"
    else:
        qui = "un couple marié" if menage.get("couple_marie_ou_pacse") else "un couple"
    salaires = " et ".join(eur(a["salaire_brut_annuel"]) for a in adultes)
    texte = f"{qui}, {salaires} brut par an"
    if enfants:
        texte += f", {enfants} enfant" + ("s" if enfants > 1 else "")
    return texte


def _types(d: dict[str, Any]) -> str:
    noms = list(TYPES)
    tete = "".join(f"<th>{html.escape(_description(d['types'][n]['menage']))}<br>"
                   f"{fichier(f'tests/golden/{n}.yaml', n)}</th>" for n in noms)
    rows = [_ligne(key, libelle, sens, [_cellule(key, sens, d["types"][n]["valeurs"])
                                         for n in noms]) for key, libelle, sens in _lignes(d)]
    return (f"<table><thead><tr><th>ligne</th>{tete}</tr></thead><tbody>"
            + "".join(rows) + "</tbody></table>")


def _anneau_or(d: dict[str, Any]) -> str:
    """Les valeurs du fichier contre les valeurs d'or que les tests tiennent."""
    rows = []
    for nom in TYPES:
        attendu = golden(nom)["expected"]
        for key, want in attendu.items():
            if key not in d["types"][nom]["valeurs"]:
                continue
            got = d["types"][nom]["valeurs"][key]
            fmt = (lambda v: f"{v:g}".replace(".", ",")) if key == "parts_fiscales" else (
                lambda v: eur(v, centimes=True))
            rows.append(f"<tr><td>{fichier(f'tests/golden/{nom}.yaml', nom)}</td>"
                        f"<td>{html.escape(key)}</td><td class=\"num\">{fmt(got)}</td>"
                        f"<td class=\"num\">{fmt(want)}</td>"
                        f"<td class=\"num\">{fmt(got - want)}</td></tr>")
    return ("<table><thead><tr><th>cas</th><th>ligne</th><th>ce fichier</th>"
            "<th>valeur d'or</th><th>écart</th></tr></thead><tbody>" + "".join(rows)
            + "</tbody></table>")


def _controle(d: dict[str, Any], ref: dict[str, Any]) -> str:
    blocs = []
    for nom in CONTROLES:
        v = d["types"][nom]["valeurs"]
        r = ref[nom]
        decote = v["ir_avant_reductions"] - v["ir"]
        lignes = (
            ("Impôt sur le revenu", round(v["ir"]), r["ir"]),
            ("Revenu fiscal de référence", round(v["revenu_fiscal_reference"]),
             r["revenu_fiscal_reference"]),
            ("Droits simples (barème et quotient familial)",
             round(v["ir_avant_reductions"]), r["droits_simples"]),
            ("Décote (droits simples moins impôt)", round(decote), r["decote"]),
        )
        rows = "".join(f"<tr><td>{html.escape(nom_ligne)}</td><td class=\"num\">{eur(a)}</td>"
                       f"<td class=\"num\">{eur(b)}</td><td class=\"num\">{eur(a - b)}</td></tr>"
                       for nom_ligne, a, b in lignes)
        parts = (f"<tr><td>Parts</td><td class=\"num\">{v['parts_fiscales']:g}</td>"
                 f"<td class=\"num\">{r['parts_fiscales']:g}</td>"
                 f"<td class=\"num\">{v['parts_fiscales'] - r['parts_fiscales']:g}</td></tr>")
        saisis = " et ".join(f"{eur(m)} en case {c}" for c, m in r["saisis"])
        imposable = (" et ".join(eur(a) for a in [v["salaire_imposable"]])
                     if len(r["saisis"]) == 1 else eur(v["salaire_imposable"])
                     + " pour le foyer")
        blocs.append(
            f"<h3>{html.escape(_description(d['types'][nom]['menage']))}</h3>"
            f"<p>Saisi dans le simulateur : {saisis}, le salaire imposable que le moteur "
            f"calcule ({imposable}), pas le brut. {fichier(f'tests/golden/{nom}.yaml', nom)}</p>"
            "<table><thead><tr><th>ligne</th><th>le moteur</th><th>le simulateur de la "
            "DGFiP</th><th>écart</th></tr></thead><tbody>" + rows + parts.replace(".", ",")
            + "</tbody></table>")
    return "".join(blocs)


def _readme(d: dict[str, Any]) -> str:
    r = d["reforme"]
    seuil, taux = d["bareme"][-1]
    nouveau = r["bareme"][-1]["rate"]
    if r["bareme"][-1]["threshold"] != seuil:
        raise ParcoursError("la réforme du README ne déplace pas que le taux de la dernière "
                            "tranche ; la page ne sait plus l'expliquer.")
    attendu = golden(REFORME)["expected_delta"]["ir"]
    au_dessus = r["loi"]["revenu_fiscal_reference"] - seuil
    points = round((nouveau - taux) * 100)
    main = round(au_dessus * (nouveau - taux))
    return (
        f"<p>Le célibataire à {eur(r['menage']['adults'][0]['salaire_brut_annuel'])} brut "
        f"par an a un revenu fiscal de référence de "
        f"<span class=\"nombre\">{eur(r['loi']['revenu_fiscal_reference'])}</span>. La "
        f"dernière tranche du barème commence à {eur(seuil)} : "
        f"<span class=\"nombre\">{eur(au_dessus)}</span> de son revenu y sont. Passer son "
        f"taux de {round(taux * 100)}\u202f% à {round(nouveau * 100)}\u202f%, c'est "
        f"{points} points de plus sur ces euros-là, soit, à la main, "
        f"<span class=\"nombre\">{eur(main)}</span>.</p>"
        "<table><thead><tr><th></th><th>impôt sur le revenu</th></tr></thead><tbody>"
        f"<tr><td>la loi</td><td class=\"num\">{eur(r['loi']['ir'])}</td></tr>"
        f"<tr><td>la tranche à {round(nouveau * 100)}\u202f%</td><td class=\"num\">"
        f"{eur(r['reforme']['ir'])}</td></tr>"
        f"<tr><td><strong>l'écart, par le moteur</strong></td><td class=\"num\"><strong>"
        f"+{eur(r['ecart']['ir'])}</strong></td></tr>"
        f"<tr><td>l'écart que le test d'or attend</td><td class=\"num\">+{eur(attendu)}"
        f"</td></tr></tbody></table>"
        f"<p>Le moteur trouve ce que l'arithmétique trouve. C'est la plus petite preuve "
        f"complète que la machinerie des réformes fait ce qu'elle dit : une erreur dans "
        f"l'ordre des tranches, dans le sens d'un écart ou dans la manière de remplacer "
        f"un barème déplacerait ce nombre. {fichier(f'tests/golden/{REFORME}.yaml')}, "
        f"{fichier('README.md', 'README.md (« Try this »)')}.</p>")


def _curseur(d: dict[str, Any]) -> tuple[str, str]:
    """Le curseur, son script et son tableau statique."""
    salaires = d["salaires"]
    defaut = salaires.index(SALAIRE_DEFAUT)
    premiere = d["situations"][0]
    options = "".join(f'<option value="{s["cle"]}">{html.escape(s["libelle"])}</option>'
                      for s in d["situations"])
    lignes = "".join(
        _ligne(key, libelle, sens, [_cellule(key, sens, premiere["valeurs"][defaut])])
        .replace('<td class="num">', f'<td class="num" data-k="{key}">', 1)
        for key, libelle, sens in _lignes(d))
    corps = (
        '<div id="m-curseur" hidden>'
        '<div class="curseur"><label for="m-sit">La situation</label>'
        f'<select id="m-sit">{options}</select><span></span></div>'
        '<div class="curseur"><label for="m-sal">Le salaire brut annuel du ménage</label>'
        f'<input type="range" id="m-sal" min="0" max="{len(salaires) - 1}" step="1" '
        f'value="{defaut}"><output id="m-sal-v" class="num">{eur(salaires[defaut])}'
        "</output></div>"
        f'<table id="m-table"><thead><tr><th>ligne</th><th>par an</th></tr></thead><tbody>'
        f"{lignes}</tbody></table></div>")

    statique = []
    for s in d["situations"]:
        rows = "".join(
            f"<tr><td class=\"num\">{eur(sal)}</td><td class=\"num\">{eur(v['salaire_net'])}"
            f"</td><td class=\"num\">{eur(v['ir'])}</td><td class=\"num\">"
            f"{eur(v['prestations'])}</td><td class=\"num\">{eur(v['revenu_disponible'])}</td>"
            "</tr>" for sal, v in zip(salaires, s["valeurs"], strict=True))
        statique.append(
            f"<h3>{html.escape(s['libelle'])}</h3><table><thead><tr><th>salaire brut</th>"
            "<th>salaire net</th><th>impôt sur le revenu</th><th>prestations, nettes de "
            "CRDS</th><th>revenu disponible</th></tr></thead><tbody>" + rows
            + "</tbody></table>")
    noscript = ("<noscript><p>Sans JavaScript, la grille entière, situation par situation, "
                "en cinq colonnes :</p>" + "".join(statique) + "</noscript>")

    data = {
        "salaires": [eur(s) for s in salaires],
        "lignes": [key for key, _, _ in LIGNES],
        "points": {s["cle"]: [[_cellule(key, sens, v) for key, _, sens in LIGNES]
                              for v in s["valeurs"]] for s in d["situations"]},
    }
    blob = json.dumps(data, ensure_ascii=False).replace("<", "\\u003c")
    script = f"""(function () {{
  var D = {blob};
  var box = document.getElementById("m-curseur");
  var sit = document.getElementById("m-sit");
  var sal = document.getElementById("m-sal");
  var out = document.getElementById("m-sal-v");
  var cells = box.querySelectorAll("td[data-k]");
  function show() {{
    var i = Number(sal.value);
    var point = D.points[sit.value][i];
    out.textContent = D.salaires[i];
    for (var k = 0; k !== cells.length; k++) {{
      cells[k].textContent = point[D.lignes.indexOf(cells[k].dataset.k)];
    }}
  }}
  sit.addEventListener("change", show);
  sal.addEventListener("input", show);
  box.hidden = false;
  show();
}})();"""
    return corps + noscript, script


def page() -> Page:
    d = donnees()
    d["abattement"] = abattement(d)
    ref = dgfip()
    moteur = d["moteur"]
    of = f"OpenFisca-France {moteur['openfisca_france']}"
    simulateur = source("https://simulateur-ir-ifi.impots.gouv.fr/calcul_impot/2025/",
                        f"le simulateur de la DGFiP, « Calcul de l'impôt 2025 sur les revenus "
                        f"{d['annee']} »")
    curseur, script = _curseur(d)
    seuils = ", ".join(eur(t) for t, _ in d["bareme"][1:])
    taux = ", ".join(f"{round(r * 100)}\u202f%" for _, r in d["bareme"])
    ecarts_ir = [round(d["types"][n]["valeurs"]["ir"]) - ref[n]["ir"] for n in CONTROLES]
    # Ce que les deux ménages contrôlés ne testent pas, vérifié ici plutôt que supposé :
    # tous deux sont en décote, et leur revenu par part reste sous la dernière tranche.
    seuil_haut, taux_haut = d["bareme"][-1]
    for n in CONTROLES:
        v = d["types"][n]["valeurs"]
        if ref[n]["decote"] <= 0:
            raise ParcoursError(f"{n} n'est plus en décote ; la page dit le contraire.")
        if v["revenu_fiscal_reference"] / v["parts_fiscales"] >= seuil_haut:
            raise ParcoursError(f"{n} atteint la dernière tranche ; la page dit le contraire.")
    haut = f"{round(taux_haut * 100)}\u202f%"
    verdict = ("à l'euro près" if all(e == 0 for e in ecarts_ir)
               else "avec un écart, montré ci-dessous")
    corps = f"""
<p>Avant de chiffrer une réforme pour la France entière, l'outil doit savoir calculer
l'impôt et les prestations d'un seul ménage. Il ne code pas la loi lui-même : il emploie
{source("https://github.com/openfisca/openfisca-france", of)}, le modèle public de la
législation française, à travers un moteur des ménages
({fichier("src/impots/engine/compute.py")}) qui lit une liste fermée de lignes
({fichier("src/impots/engine/outputs.py")}). Cette page montre ce que ce moteur rend pour
des ménages simples, et la seule preuve indépendante qu'il ait : une partie du même
calcul, l'impôt sur le revenu, refaite par l'administration fiscale. Ce que cette preuve
couvre et ce qu'elle ne couvre pas est dit plus bas, ligne à ligne.</p>

<p>Tous les montants sont annuels, sur les revenus de {d['annee']}, et chiffrés d'avance
par ce moteur dans {fichier(CHEMIN_JSON)}, au commit <code>{d['commit'][:10]}</code>, le
{d['date']}. Le barème de l'impôt sur ces revenus est celui de la
{source("https://www.legifrance.gouv.fr/eli/loi/2025/2/14/2025-127/jo/texte",
        "loi de finances pour 2025")} : des tranches à {taux}, qui commencent à {seuils}.</p>

<h2>Trois ménages, ligne à ligne</h2>
<p>Du coût du travail au revenu disponible : ce que l'employeur paie, ce que le salarié
cotise, l'impôt, les prestations. Les lignes marquées « − » sortent du revenu, les autres y
entrent, sauf les lignes en gris, qui expliquent sans s'ajouter : le coût du travail pour
l'employeur, et les étapes de l'impôt (salaire imposable, revenu fiscal, parts, impôt
avant décote). Le salaire net est le brut
moins ses quatre lignes ; le revenu disponible est le salaire net, plus les prestations,
moins l'impôt. La commande qui chiffre le fichier refuse un ménage où ces sommes ne
retombent pas à un euro près sur ce que le moteur rend.</p>
{_types(d)}

<h2>Le contrôle à l'euro contre la DGFiP</h2>
<p>Un test qui compare le moteur à lui-même continue de passer quand les deux s'éloignent
de la loi. Le seul contrôle qui puisse attraper une erreur systématique est un calcul
indépendant : {simulateur}, qui fait son arithmétique sans OpenFisca. Les deux premiers
ménages y ont été saisis à la main le {ref['date']} ; le moteur et l'administration
s'accordent {verdict}, sur l'impôt comme sur ses étapes. Les montants du simulateur sont
ceux que {fichier(CROSSCHECK)} a relevés.</p>
{_controle(d, ref)}
<p><strong>Ce que ce contrôle prouve.</strong> Partant du même salaire imposable, le
moteur et l'administration trouvent le même revenu fiscal de référence, le même nombre de
parts, les mêmes droits simples et la même décote : sur ces deux ménages, tous deux en
décote, l'abattement de 10 %, le barème, le quotient familial et la décote sont codés
juste. Aucun des deux n'atteint la tranche à {haut}, ni le plafonnement du quotient
familial, ni le plafond de l'abattement : ces trois-là ne sont pas contrôlés.</p>
<p><strong>Ce qu'il ne prouve pas.</strong></p>
<ul>
<li><strong>Le passage du brut à l'imposable.</strong> Le salaire saisi dans le simulateur
est le salaire imposable que le moteur a calculé, pas le brut : les cotisations
salariales, la CSG et la CRDS, qui font ce passage, ne sont contrôlées par personne
d'autre qu'OpenFisca.</li>
<li><strong>Les prestations.</strong> Le simulateur de la DGFiP n'en calcule pas. Le
contrôle équivalent contre l'estimateur de la CAF est préparé et n'est pas fait
({fichier("tests/golden/CROSSCHECK_CAF.md")}) ; les montants de prestations de cette
page sont ceux d'OpenFisca, sans contrôle indépendant.</li>
<li><strong>Les autres situations.</strong> Deux ménages seulement ont été saisis, deux
foyers de salariés sans autre revenu, sans niche ni crédit d'impôt : une personne seule,
et un couple marié avec deux enfants. Le plafonnement du quotient familial, les pensions,
les revenus du capital, les réductions et crédits d'impôt n'ont pas été refaits par
l'administration.</li>
</ul>

<h2>Les valeurs d'or</h2>
<p>Chaque ménage type est aussi un cas d'or : ses valeurs, produites par le moteur le jour
où le cas a été écrit, sont tenues à ±2\u00a0€ par {fichier("tests/test_golden.py")}. Le
fichier de cette page doit les retrouver : un écart dirait que le moteur a bougé depuis.</p>
{_anneau_or(d)}

<h2>Une tranche à 50 %, à la main</h2>
{_readme(d)}

<h2>À vous : un salaire, une situation</h2>
<p>Le curseur s'arrête sur les points d'une grille chiffrée d'avance ; il n'interpole
rien entre eux. Le salaire est celui du ménage : un couple à deux salaires le partage
{round(PART_PREMIER * 100)}/{round((1 - PART_PREMIER) * 100)} entre les conjoints, nés en
{NAISSANCE_ADULTES[0]} et {NAISSANCE_ADULTES[1]} ; les enfants sont nés en
{NAISSANCE_ENFANTS[0]} et {NAISSANCE_ENFANTS[1]}. Le même salaire est supposé les années
d'avant, que le RSA et la prime d'activité lisent.</p>
{curseur}

<h2>Ce que ces ménages n'ont pas</h2>
<ul>
<li><strong>Un logement.</strong> Aucun loyer n'est déclaré, donc aucune aide au
logement : pour un ménage modeste qui loue, son revenu disponible est plus haut que celui
affiché ici.</li>
<li><strong>D'autres revenus.</strong> Ni pension, ni chômage, ni revenu du capital, ni
revenu d'indépendant ; aucune niche fiscale.</li>
<li><strong>Le non-recours.</strong> Chaque prestation due est versée, comme le moteur la
calcule.</li>
</ul>

<h2>Refaire le calcul</h2>
<p>Dans un clone du dépôt, <code>{html.escape(d['commande'])}</code> réécrit
{fichier(CHEMIN_JSON)} en quelques minutes ; le code qui chiffre et qui construit cette
page est {fichier("src/impots/parcours/menage.py")}. Le contrôle DGFiP se refait à la main,
en suivant {fichier(CROSSCHECK)}, sur {simulateur}.</p>
"""
    return Page(prouve="sur deux ménages salariés simples, le moteur trouve l'impôt sur le "
                       f"revenu {verdict.split(',')[0]} comme le simulateur de "
                       "l'administration fiscale, à partir du même salaire imposable ; sur "
                       "ces deux ménages, tous deux en décote, le barème, le quotient "
                       "familial et la décote sont donc codés juste, mais aucun ne teste la "
                       f"tranche à {haut}, ni le plafonnement du quotient familial. "
                       "Les cotisations, la CSG et les prestations ne sont pas contrôlées "
                       "par un tiers.",
                corps=corps, script=script, style=STYLE)


if __name__ == "__main__":  # pragma: no cover - la commande de la docstring
    ecrire()
    print(f"écrit : {JSON}")
