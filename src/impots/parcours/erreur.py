"""Page 8 du parcours : où l'outil se trompe (but 20, D-375).

Elle prouve que l'erreur est mesurée, bornée et dite. C'est la page qu'on cite : elle n'a
ni curseur ni script, seulement des tableaux et de petits graphiques statiques.

Elle range l'erreur à son étage (la loi, la population, le coût, les comportements,
l'activité), montre qu'elle est stable sur trois ans, sépare l'erreur de niveau de
l'erreur de coût, relie chaque ligne hors de sa tolérance aux études qu'elle touche, et
garde les juges manqués. Chaque nombre est lu dans un fichier commité à la construction :
la grille et ses passes (`verification.grille`), le contrôle de la loi contre le
simulateur de la DGFiP (`tests/golden/CROSSCHECK.md`), les chiffrages préenregistrés
(`chiffrages_preregistres/`, notés par `preregistration.grade`), la mesure de l'écart de
la prime d'activité (`reports/ecart_ppa.md`), les pages des études (`docs/etudes/`).
"""

from __future__ import annotations

import html
import re
from pathlib import Path
from typing import Any

from impots import etude, preregistration, site, verification
from impots.parcours import ROOT, Page, ParcoursError, fichier, lien, source
from impots.parcours.france import (ANNEES, compte, lien_source, notees, par_ligne, pct)

CROSSCHECK = ROOT / "tests" / "golden" / "CROSSCHECK.md"
CROSSCHECK_CAF = ROOT / "tests" / "golden" / "CROSSCHECK_CAF.md"
ECART_PPA = ROOT / "reports" / "ecart_ppa.md"
PAGES_ETUDES = ROOT / "docs" / "etudes"
SIMULATEUR_DGFIP = "https://simulateur-ir-ifi.impots.gouv.fr/"

#: Pourquoi une ligne est hors de sa tolérance, tiré des D-entrées qui l'ont mesuré.
#: Une ligne hors de sa tolérance qui n'est pas ici est dite « pas encore expliquée ».
EXPLICATIONS: dict[str, tuple[str, str]] = {
    "cotisations_employeurs": (
        "D-364, D-367",
        "Un classement, pas une erreur de la population : le super-brut moins le brut "
        "compte des impôts sur les salaires, la contribution de l'État aux pensions de ses "
        "agents et des salaires hors brut, que les comptes nationaux rangent ailleurs. La "
        "mesure au sens de l'Insee (D121), qui les retire, tient sa tolérance ; la ligne "
        "d'origine reste, telle qu'elle a été préenregistrée."),
    "reduction_generale": (
        "D-370, D-371",
        "La règle est juste ; il manque des salaires horaires près du SMIC. C'est la forme "
        "du bas des salaires horaires, que les quantiles publiés en équivalent temps plein "
        "ne donnent pas."),
    "bandeau_famille": (
        "D-371",
        "La même cause que la réduction générale, de l'autre côté : il y a trop de salaires "
        "horaires entre les deux seuils du bandeau."),
    "bandeau_maladie": (
        "D-369, D-371",
        "Rangée avec les allègements : la forme du bas des salaires horaires. Elle ne sort "
        "de sa tolérance qu'en 2022."),
    "ppa_montant_servi": (
        "D-370, D-371",
        "Un choix de cible, dit : la prime est calée sur les recourants comptés par la "
        "Drees, que les foyers payés par la Cnaf dépassent."),
    "ppa_foyers_servis": (
        "D-370, D-371",
        "Le même choix de cible que le montant servi : les recourants de la Drees, sous les "
        "foyers que la Cnaf paie."),
    "ppa_montant": (
        "D-370, D-371",
        "La mesure par le pont de non-recours, que la mesure servie en espérance remplace ; "
        "la même cible, sous la Cnaf."),
    "ppa_foyers": (
        "D-364, D-366",
        "Elle compte les foyers qui ont droit à la prime, au plein recours ; la Cnaf ne "
        "compte que ceux qui la demandent. La ligne des foyers servis en espérance mesure "
        "ce que la Cnaf compte."),
    "rsa_foyers": (
        "D-364, D-367",
        "Elle compte les foyers qui ont droit au RSA, au plein recours ; le pont de "
        "non-recours corrige le montant, pas le nombre. La ligne des foyers servis en "
        "espérance tient sa tolérance."),
    "aide_logement_montant": (
        "D-371",
        "Le hors-champ du modèle (foyers, résidences, accédants à la propriété) et les "
        "hébergés, mesurés à l'étape « al » du but 19."),
    "contribution_sociale_is": (
        "D-364",
        "Une contribution qui ne vit qu'au-dessus d'un seuil d'impôt suit mal le PIB qui "
        "ramène les entreprises d'une année à l'autre. Elle ne sort de sa tolérance qu'en "
        "2023."),
}

#: Les instruments que les études chiffrent, comme un lecteur les nomme, par la clé de
#: `etude.VERIFIE_PAR`.
INSTRUMENTS = {
    "cotisations_salariales": "les cotisations des salariés",
    "employeurs": "les cotisations des employeurs",
    "csg_deductible": "la CSG", "csg_imposable": "la CSG",
    "ir_avant_niches": "l'impôt sur le revenu",
    "rsa": "le RSA", "ppa": "la prime d'activité", "aide_logement": "les aides au logement",
    "af": "les allocations familiales", "impot_societes": "l'impôt sur les sociétés",
    "contribution_sociale_is": "la contribution sociale sur l'IS", "c3s": "la C3S",
    "cvae": "la CVAE",
}
#: L'instrument dont la sensibilité du coût est mesurée (D-316) : la prime d'activité.
SENSIBILITE_MESUREE = "ppa"


# --------------------------------------------------------------------------- #
# Les fichiers lus
# --------------------------------------------------------------------------- #

def _lire(path: Path) -> str:
    if not path.exists():
        raise ParcoursError(f"la page de l'erreur lit {path}, qui n'existe pas.")
    return path.read_text(encoding="utf-8")


def _entier(texte: str) -> int:
    return int(re.sub(r"[\s  ]", "", texte))


def controle_loi() -> dict[str, Any]:
    """Le contrôle de la loi contre le simulateur de la DGFiP : sa date, et pour chaque
    ménage l'impôt du moteur et celui du simulateur. Puis l'état du contrôle des
    prestations contre la Caf."""
    text = _lire(CROSSCHECK)
    statut = re.search(r"\*\*Status: (\w+) — (\d{4}-\d{2}-\d{2})", text)
    if statut is None:
        raise ParcoursError("CROSSCHECK.md ne dit plus son statut.")
    cas = []
    for nom, bloc in re.findall(r"### `([^`]+)`\n(.*?)(?=\n### |\n## |\Z)", text, re.S):
        moteur = re.search(r"Our engine, `ir` \| \*\*([\d\s ]+) €\*\*", bloc)
        dgfip = re.search(r"DGFiP simulator \| \*\*([\d\s ]+) €\*\*", bloc)
        if moteur and dgfip:
            cas.append({"nom": nom, "moteur": _entier(moteur[1]),
                        "dgfip": _entier(dgfip[1])})
    if not cas:
        raise ParcoursError("CROSSCHECK.md ne porte plus aucun ménage chiffré.")
    caf = re.search(r"\*\*Status: ([^*]+?)\*\*", _lire(CROSSCHECK_CAF))
    return {"statut": statut[1], "date": statut[2], "cas": cas,
            "caf_fait": bool(caf) and "NOT DONE" not in caf[1]}


def juges() -> dict[str, list[tuple[Any, Any]]]:
    """Les chiffrages préenregistrés, notés contre leur juge : les aveugles, les
    révisions écrites après l'annexe, et ceux qui attendent leur juge."""
    out: dict[str, list[tuple[Any, Any]]] = {"aveugles": [], "revisions": [],
                                             "attente": []}
    for name in preregistration.available():
        case = preregistration.load(name)
        if case.comparator is None:
            out["attente"].append((None, case))
        else:
            key = "revisions" if case.revision else "aveugles"
            out[key].append((preregistration.grade(case), case))
    return out


def sensibilite_ppa() -> dict[str, str]:
    """La mesure de D-316 : la base du moteur par point de forfait, contre la Cnaf en 2024
    et contre la fiche du PLF en 2026."""
    text = _lire(ECART_PPA)
    found = {
        "commit": re.search(r"Commit `([0-9a-f]+)`", text),
        "moteur": re.search(r"([\d,]+) M€ de plus pour un point de forfait", text),
        "cnaf": re.search(r"la base vaut ([\d,]+) M€ par point", text),
        "rapport": re.search(r"Le rapport des bases : \*\*([\d,]+)\*\*", text),
        "fiche": re.search(r"le moteur en a \*\*([\d,]+)\*\* fois plus", text),
    }
    missing = [k for k, v in found.items() if v is None]
    if missing:
        raise ParcoursError(f"reports/ecart_ppa.md ne dit plus : {', '.join(missing)}.")
    return {k: v[1] for k, v in found.items()}


def etudes_par_ligne() -> dict[str, list[tuple[str, str]]]:
    """Pour chaque libellé de ligne de la grille, les études dont la page la cite dans
    « La vérification de ses instruments » : (titre, page publiée)."""
    out: dict[str, list[tuple[str, str]]] = {}
    for path in sorted(PAGES_ETUDES.glob("*.md")):
        lines = _lire(path).splitlines()
        titre = lines[0].lstrip("# ").strip()
        try:
            start = next(i for i, x in enumerate(lines)
                         if x.startswith("**La vérification de ses instruments.**"))
        except StopIteration:
            continue
        for x in lines[start + 1:]:
            if x.startswith("Un écart de niveau") or x.startswith("**"):
                break
            if x.startswith("* ") and " : " in x:
                out.setdefault(x[2:].split(" : ")[0], []).append((titre, f"{path.stem}.html"))
    return out


# --------------------------------------------------------------------------- #
# Les morceaux de la page
# --------------------------------------------------------------------------- #

def _bande(ans: dict[int, dict[str, Any]], tol: float) -> str:
    """Un petit graphique statique : la bande de tolérance en fond, le zéro, et l'écart
    de chaque année, une rangée par année. L'échelle va de −60 % à +60 %."""
    w, h, borne = 180, 30, 0.6

    def x(v: float) -> float:
        return w / 2 + max(-borne, min(borne, v)) / borne * (w / 2 - 4)

    parts = [f'<rect class="tol" x="{x(-tol):.1f}" y="0" width="{x(tol) - x(-tol):.1f}" '
             f'height="{h}"/>', f'<line class="zero" x1="{w / 2}" y1="0" x2="{w / 2}" '
             f'y2="{h}"/>']
    label = []
    for k, annee in enumerate(ANNEES):
        r = ans.get(annee)
        if r is None or r.get("ecart") is None or r["usage"] != "validation":
            continue
        cls = "hors" if r["verdict"] == "hors de la tolérance" else "tenue"
        parts.append(f'<circle class="{cls}" cx="{x(r["ecart"]):.1f}" cy="{5 + 10 * k}" '
                     f'r="3.5"/>')
        label.append(f"{annee} : {pct(r['ecart'])}")
    aria = f"{' ; '.join(label)} ; tolérance ±{tol * 100:.0f} %"
    return (f'<svg class="bande" viewBox="0 0 {w} {h}" width="{w}" height="{h}" '
            f'role="img" aria-label="{html.escape(aria)}">' + "".join(parts) + "</svg>")


def table_stabilite(rows: list[dict[str, Any]], loi: dict[str, dict[str, Any]]) -> str:
    out = []
    for ident, ans in par_ligne(rows).items():
        if ident not in loi:
            continue
        premier = next(r for r in ans.values() if r["usage"] == "validation")
        tol = premier["tolerance"]
        v = loi[ident]
        cells = "".join(
            (f'<td class="num {"hors" if ans[a]["verdict"] == "hors de la tolérance" else ""}">'
             f"{pct(ans[a]['ecart'])}</td>")
            if a in ans and ans[a]["usage"] == "validation" and ans[a].get("ecart") is not None
            else '<td class="num vide">—</td>' for a in ANNEES)
        etendue = (v["max"] - v["min"]) * 100
        out.append(f'<tr id="stable-{ident}"><th scope="row">{html.escape(v["ligne"])}<br>'
                   f"{_bande(ans, tol)}</th><td>±{tol * 100:.0f} %</td>{cells}"
                   f'<td class="num">{pct(v["biais"])}</td>'
                   f'<td class="num">{_virgule(f"{etendue:.1f}")} pt</td></tr>')
    return ("<table class=\"stable\"><thead><tr><th>ligne (la bande grise est la "
            "tolérance ; un point par année, 2022 en haut)</th><th>tolérance</th>"
            + "".join(f"<th>{a}</th>" for a in ANNEES)
            + "<th>biais</th><th>étendue</th></tr></thead><tbody>"
            + "\n".join(out) + "</tbody></table>")


def _virgule(texte: str) -> str:
    return texte.replace(".", ",")


def lignes_hors(rows: list[dict[str, Any]], loi: dict[str, dict[str, Any]],
                etudes: dict[str, list[tuple[str, str]]]) -> list[dict[str, Any]]:
    """Chaque ligne qui sort de sa tolérance une année au moins : ses années hors, son
    explication ou « pas encore expliquée », les instruments qu'elle vérifie et les
    études qui la citent."""
    instruments: dict[str, list[str]] = {}
    for key, ids in etude.VERIFIE_PAR.items():
        for ident in ids:
            instruments.setdefault(ident, []).append(INSTRUMENTS.get(key, key))
    out = []
    for ident, ans in par_ligne(rows).items():
        hors = [r for r in ans.values() if r["verdict"] == "hors de la tolérance"]
        if not hors:
            continue
        label = loi[ident]["ligne"]
        out.append({"id": ident, "ligne": label, "hors": hors, "loi": loi[ident],
                    "explication": EXPLICATIONS.get(ident),
                    "instruments": list(dict.fromkeys(instruments.get(ident, []))),
                    "etudes": etudes.get(label, [])})
    return out


def _bloc_hors(h: dict[str, Any]) -> str:
    annees = ", ".join(f"{r['annee']} ({pct(r['ecart'])})" for r in h["hors"])
    tol = h["hors"][0]["tolerance"]
    if h["explication"]:
        ref, texte = h["explication"]
        expl = (f"<p><strong>Pourquoi.</strong> {html.escape(texte)} "
                f"<small>({html.escape(ref)}, {fichier('docs/DECISIONS.md')})</small></p>")
    else:
        expl = "<p><strong>Pourquoi.</strong> <em>Pas encore expliquée.</em></p>"
    if h["instruments"]:
        touche = (f"Elle vérifie {html.escape(etude._et(h['instruments']))} "
                  f"(<code>etude.VERIFIE_PAR</code>). ")
        if h["etudes"]:
            touche += "Les études qui la citent : " + ", ".join(
                f'<a href="{page}">{html.escape(titre)}</a>' for titre, page in h["etudes"]
            ) + "."
        else:
            touche += "Aucune étude publiée ne la cite aujourd'hui."
    else:
        touche = ("Aucune étude ne la lit : l'instrument qu'elle mesure est vérifié par une "
                  "autre ligne, ou n'est chiffré par aucune étude.")
    r0 = h["hors"][0]
    src = lien_source(r0.get("url"), "le total publié", r0.get("localisation") or "")
    return (f'<section class="hors-ligne" id="hors-{h["id"]}"><h3>{html.escape(h["ligne"])}'
            f"</h3><p>Hors de sa tolérance (±{tol * 100:.0f} %) en {annees} ; biais sur "
            f"trois ans {pct(h['loi']['biais'])}, "
            f"{h['loi']['tenues']} année{'s' if h['loi']['tenues'] > 1 else ''} sur "
            f"{len(h['loi']['annees'])} dans la tolérance. Contre {src}.</p>"
            f"{expl}<p><strong>Ce qu'elle touche.</strong> {touche}</p></section>")


def table_etages(rows: list[dict[str, Any]], loi_: dict[str, Any],
                 j: dict[str, list[tuple[Any, Any]]]) -> str:
    tenues, n = compte(rows)
    ok = sum(c["moteur"] == c["dgfip"] for c in loi_["cas"])
    aveugles = j["aveugles"]
    dedans = sum(g.verdict == "within" for g, _ in aveugles)
    caf = ("fait" if loi_["caf_fait"] else
           f"préparé, pas fait ({fichier('tests/golden/CROSSCHECK_CAF.md', 'CROSSCHECK_CAF.md')})")
    lignes = [
        ("L0", "la loi codée : chaque taux, seuil et barème, daté",
         f"l'impôt de deux ménages types contre le "
         f"{source(SIMULATEUR_DGFIP, 'simulateur de la DGFiP')}, le {loi_['date']} "
         f"({fichier('tests/golden/CROSSCHECK.md', 'CROSSCHECK.md')}) ; les prestations "
         f"contre le simulateur de la Caf : {caf}",
         f"<strong>{ok} sur {len(loi_['cas'])}</strong> à l'euro ; les prestations ne sont "
         "pas vérifiées ainsi", lien("menage", "page 1")),
        ("L1", etude.ETAGES["L1"],
         f"la grille : chaque total contre son total publié, sur trois ans "
         f"({fichier('docs/verification/GRILLE.md', 'GRILLE.md')})",
         f"<strong>{tenues} sur {n}</strong> lignes tenues ; {n - tenues} hors",
         lien("france", "page 2")),
        ("L2", etude.ETAGES["L2"],
         "des juges : les chiffrages préenregistrés, notés contre l'évaluation préalable "
         f"publiée ensuite ({fichier('reports/chiffrages_preregistres.md', 'chiffrages_preregistres.md')})",
         f"<strong>{dedans} sur {len(aveugles)}</strong> dans la tolérance déclarée",
         lien("cout", "page 3")),
        ("L3", etude.ETAGES["L3"],
         "aucun juge : la fourchette vient d'élasticités publiées, que l'outil ne mesure pas",
         "non vérifiée ; elle se juge sur ses articles", lien("comportements", "page 4")),
        ("L4", etude.ETAGES["L4"],
         "aucun juge : les tables de Mésange et l'éventail des études publiées",
         "<strong>non vérifiée</strong>, dit tel quel", lien("activite", "page 5")),
    ]
    body = "".join(
        f'<tr><th scope="row"><span class="etage e-{e.lower()}">{e}</span></th>'
        f"<td>{html.escape(quoi)}</td><td>{comment}</td><td>{res}</td><td>{p}</td></tr>"
        for e, quoi, comment, res, p in lignes)
    return ("<table><thead><tr><th>étage</th><th>ce qu'il calcule</th><th>contre quoi il "
            "est vérifié</th><th>résultat</th><th>page</th></tr></thead><tbody>"
            + body + "</tbody></table>")


def _md(x: float) -> str:
    return _virgule(f"{x / 1e9:+.3f} Md€").replace("-", "−")


def table_juges(j: dict[str, list[tuple[Any, Any]]]) -> str:
    rows = []
    for g, case in sorted(j["aveugles"], key=lambda gc: gc[0].verdict != "outside"):
        cls = "hors" if g.verdict == "outside" else ""
        verdict = "hors de la tolérance" if g.verdict == "outside" else "dans la tolérance"
        rows.append(f"<tr><td><code>{html.escape(case.case)}</code></td>"
                    f"<td>{html.escape(case.pre_registered[:10])}</td>"
                    f'<td class="num">{_md(g.simulated_eur)}</td>'
                    f'<td class="num">{_md(g.published_eur)}</td>'
                    f'<td class="num {cls}">{pct(g.relative_gap)}</td>'
                    f'<td class="num">±{_virgule(f"{g.allowed_eur / 1e9:.3f}")} Md€</td>'
                    f"<td>{verdict}</td></tr>")
    return ("<table><thead><tr><th>cas</th><th>enregistré le</th><th>chiffré</th>"
            "<th>publié</th><th>écart</th><th>toléré</th><th>verdict</th></tr></thead>"
            "<tbody>" + "".join(rows) + "</tbody></table>")


def table_instruments(loi: dict[str, dict[str, Any]], s: dict[str, str]) -> str:
    noms: dict[str, list[str]] = {}
    for key, ids in etude.VERIFIE_PAR.items():
        nom = INSTRUMENTS.get(key, key)
        noms.setdefault(nom, [])
        noms[nom] += [i for i in ids if i not in noms[nom]]
    ppa = INSTRUMENTS[SENSIBILITE_MESUREE]
    rows = []
    for nom, ids in noms.items():
        niveau = "<br>".join(
            f"{html.escape(loi[i]['ligne'])} : {pct(loi[i]['biais'])}"
            for i in ids if i in loi) or "—"
        if nom == ppa:
            sens = (f"<strong>mesurée</strong> (D-316) : la base du moteur réagit "
                    f"{s['rapport']} fois plus que celle de la Cnaf à un point de forfait "
                    f"en 2024, {s['fiche']} fois plus que celle du chiffrage officiel en "
                    f"2026")
        else:
            sens = "non mesurée : <em>l'erreur du coût n'est pas connue</em>"
        rows.append(f"<tr><td>{html.escape(nom[0].upper() + nom[1:])}</td><td>{niveau}</td>"
                    f"<td>{sens}</td></tr>")
    return ("<table><thead><tr><th>instrument</th><th>erreur de niveau (biais sur trois "
            "ans)</th><th>sensibilité du coût</th></tr></thead><tbody>"
            + "".join(rows) + "</tbody></table>")


STYLE = """
.num{white-space:nowrap}
svg.bande{display:block;margin-top:.2rem;max-width:100%;height:auto}
svg.bande rect.tol{fill:var(--l2)}
svg.bande line.zero{stroke:var(--doux);stroke-width:1}
svg.bande circle.tenue{fill:var(--texte)}
svg.bande circle.hors{fill:var(--hors,#b3261e)}
:root{--hors:#b3261e}
@media (prefers-color-scheme:dark){:root{--hors:#ff8a80}}
td.hors,.num.hors{background:var(--l4)}
.num.vide{color:var(--doux)}
table.stable th[scope=row]{font-weight:400;min-width:11rem}
section.hors-ligne{border-left:3px solid var(--l4);padding-left:.8rem;margin:1.2rem 0}
section.hors-ligne h3{margin-bottom:.2rem}
"""


def page() -> Page:
    rows = verification.grille()
    loi = verification.loi_d_erreur(rows)
    loi_ = controle_loi()
    j = juges()
    s = sensibilite_ppa()
    etudes = etudes_par_ligne()
    tenues, n = compte(rows)
    hors = lignes_hors(rows, loi, etudes)
    n_hors = sum(len(h["hors"]) for h in hors)
    expliquees = sum(h["explication"] is not None for h in hors)
    large = max(loi.values(), key=lambda v: v["max"] - v["min"])
    largeur = (large["max"] - large["min"]) * 100
    etroites = sum((v["max"] - v["min"]) * 100 <= 5 for v in loi.values()
                   if len(v["annees"]) > 1)
    plusieurs = sum(len(v["annees"]) > 1 for v in loi.values())
    aveugles = j["aveugles"]
    dedans = sum(g.verdict == "within" for g, _ in aveugles)
    manques = [(g, c) for g, c in aveugles if g.verdict == "outside"]
    rev_ok = sum(g.verdict == "within" for g, _ in j["revisions"])
    ppa_servi = loi["ppa_montant_servi"]
    ppa_juge = next((g for g, c in aveugles if c.case == "plf2027_art_74_ppa"), None)
    if ppa_juge is None:
        raise ParcoursError("le juge de la prime d'activité (plf2027_art_74_ppa) manque.")
    ppa_case = next(c for g, c in aveugles if c.case == "plf2027_art_74_ppa")
    signaler = site.reglages().get("signaler")

    manques_html = "".join(
        f"<li><code>{html.escape(c.case)}</code> : chiffré {_md(g.simulated_eur)}, publié "
        f"{_md(g.published_eur)}, écart {pct(g.relative_gap)}, hors de la tolérance écrite "
        f"le {html.escape(c.pre_registered[:10])}. "
        + ("La base de l'évaluation est l'effet budgétaire de 2027, deux années de revenus "
           "et le prélèvement à la source ; le chiffrage, une seule année. Le cas révisé "
           "sur la base de 2027, écrit après l'annexe, tient sa tolérance, et n'est pas "
           "compté ici (D-204, D-292)."
           if c.case == "plf2027_art_2" else
           "Un tiers de l'écart est l'année (le droit de 2026 sur les revenus de 2024), "
           "deux tiers la population contre la Cnaf ; le recours n'a pas pu être mesuré "
           "(D-300, D-316)." if c.case == "plf2027_art_74_ppa" else
           "<em>Pas encore expliqué.</em>")
        + "</li>" for g, c in manques)

    corps = f"""
<p>Un outil qui chiffre des réformes se trompe. La question n'est pas de savoir s'il se
trompe, mais où, de combien, et si on le sait. Cette page range chaque erreur mesurée à
son étage, montre qu'elle tient d'une année à l'autre, dit ce qu'elle touche, et garde
les ratés. Elle n'a ni curseur ni script : c'est la page qu'on cite.</p>

<h2 id="etages">L'erreur, étage par étage</h2>
<p>Un nombre de l'outil repose sur des étages empilés, du plus sûr au moins sûr. L'erreur
ne se répartit pas également : la loi est juste à l'euro là où elle a été contrôlée ;
l'erreur se concentre dans la population (L1), et l'activité (L4) n'est pas vérifiée du
tout.</p>
{table_etages(rows, loi_, j)}

<h2 id="stable">Une erreur stable sur trois ans</h2>
<p>La population est celle de 2024 ; pour 2022 et 2023, elle est ramenée à l'année par
les prix et les salaires constatés, et la loi est celle de l'année
({fichier("src/impots/verification.py")}). Si l'erreur était un bruit, elle sauterait
d'une année à l'autre ; c'est un biais de structure. Sur les <span class="num">{plusieurs}
</span> lignes notées plusieurs années, <span class="num">{etroites}</span> ont une
étendue de 5 points au plus ; la plus large, {html.escape(large["ligne"][0].lower() + large["ligne"][1:])}, de
<span class="num">{_virgule(f"{largeur:.1f}")}</span> points : les entreprises sont
ramenées d'une année à l'autre par le PIB, sans lire leurs bénéfices. Un biais stable se corrige ; un bruit ne se corrige pas. Les écarts sont
ceux des trois passes commitées ({fichier("reports/verification/grille.json")}).</p>
{table_stabilite(rows, loi)}

<h2 id="hors">Les lignes hors de leur tolérance, et ce qu'elles touchent</h2>
<p><span class="num">{n - tenues}</span> lignes-années notées sur <span class="num">{n}
</span> sortent de leur tolérance ; elles viennent de <span class="num">{len(hors)}</span>
lignes de la grille, dont <span class="num">{expliquees}</span> ont une cause mesurée et
dite. Les tolérances ont été écrites avant le premier calcul et n'ont pas bougé depuis.
Une ligne qui touche une étude le dit, avec la page de l'étude ; une ligne qui n'en touche
aucune le dit aussi.</p>
{"".join(_bloc_hors(h) for h in hors)}

<h2 id="niveau-et-cout">L'erreur de niveau n'est pas l'erreur du coût</h2>
<p>Le coût d'une réforme est la différence de deux passes sur la même population. Ce qui
manque aux deux passes s'y annule en partie : un niveau faux ne fait pas un coût faux du
même pourcentage. Ce qui compte pour le coût est la <em>sensibilité</em> de la base au
bouton que la réforme tourne.</p>
<p>La prime d'activité le prouve. Son niveau est trop bas : le montant servi est
<span class="num">{pct(ppa_servi["biais"])}</span> sous la Cnaf en moyenne sur trois ans.
Son coût est trop haut : un point de forfait ajoute <span class="num">{s["moteur"]} M€
</span> par mois à la prime du moteur, contre <span class="num">{s["cnaf"]} M€</span> à
celle de la Cnaf, <span class="num">{s["rapport"]}</span> fois plus (mesure de D-316, au
commit <code>{s["commit"]}</code>, avant le but 19 ; {fichier("reports/ecart_ppa.md")}).
Le juge l'a vu : la revalorisation de l'art. 74, chiffrée
<span class="num">{_md(ppa_juge.simulated_eur)}</span>, a été publiée à
<span class="num">{_md(ppa_juge.published_eur)}</span>, un écart de
<span class="num">{pct(ppa_juge.relative_gap)}</span> (enregistré le
{html.escape(ppa_case.pre_registered[:10])}). La base sous la Cnaf portait un coût
au-dessus.</p>
<p>Pour chaque instrument que les études chiffrent, son erreur de niveau, et si la
sensibilité de son coût est mesurée. Elle ne l'est que pour un seul.</p>
{table_instruments(loi, s)}

<h2 id="juges">Les juges, et les ratés gardés</h2>
<p>Un chiffrage noté contre un juge est enregistré, daté et commité <em>avant</em> la
publication du chiffre officiel, avec la tolérance qui le notera ; cette tolérance ne
change plus ({fichier("src/impots/preregistration.py")}, les cas dans
{fichier("chiffrages_preregistres/plf2027_art_2.yaml", "chiffrages_preregistres/")}).
Le chiffre noté reste celui de son enregistrement, même quand la série refaite le
déplace. <strong><span class="num">{dedans}</span> sur <span class="num">{len(aveugles)}
</span></strong> cas aveugles tiennent leur tolérance. Avec si peu de cas, la note ne
distingue pas un bon outil d'un mauvais : elle se lit avec ses ratés.</p>
{table_juges(j)}
<p>Les juges manqués, en tête :</p>
<ul>{manques_html}</ul>
<p>À part, <span class="num">{rev_ok}</span> révisions sur
<span class="num">{len(j["revisions"])}</span>, écrites après l'ouverture de l'annexe,
tiennent leur tolérance ; elles ne comptent pas dans la note, parce qu'elles n'étaient pas
aveugles. <span class="num">{len(j["attente"])}</span> mesures des programmes
présidentiels attendent leur juge.</p>

<h2 id="signaler">Signaler une erreur</h2>
<p>{site._signaler()}</p>
<p>{(source(signaler, "Les signalements, publics") + " : chacun reçoit une réponse, "
     "et une erreur confirmée entre dans une D-entrée datée de " + fichier("docs/DECISIONS.md")
     + ".") if signaler else "L'adresse n'est pas encore fixée."}</p>
"""
    return Page(prouve="l'erreur de l'outil est mesurée, bornée et dite, à l'étage où elle "
                       "se trouve.", corps=corps, style=STYLE)
