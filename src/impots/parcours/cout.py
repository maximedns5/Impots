"""Page 3 du parcours : le coût d'une mesure (D-375).

Elle prouve qu'un coût est la différence de deux passes sur la même population, et que son
erreur est celle de la base qu'il touche. Deux mesures pas à pas, Attal (« Droit au brut »)
et la prime d'activité de l'art. 74 du PLF 2027, chacune lue dans les rapports de la série
de D-373 ; les juges, lus dans `chiffrages_preregistres/` et notés par
`preregistration.grade` ; un curseur sur le bouton de deux mesures, qui choisit entre les
points de la grille de l'explorateur (`reports/grille/`), chiffrés d'avance.

Aucun nombre n'est tapé ici : chacun est lu dans un fichier commité à la construction. Les
fonctions de mise en forme servent aussi à la page « Comparer ».
"""

from __future__ import annotations

import html
import json
import math
import re
from typing import Any

from impots import etude, site
from impots.parcours import DEPOT, ROOT, Page, ParcoursError, fichier, lien, source

# --------------------------------------------------------------------------- #
# lire, écrire un nombre
# --------------------------------------------------------------------------- #
ATTAL = "reports/etudes/presidentielle_attal/premiere_annee_pres2027_attal_programme.json"
ATTAL_PRED = "reports/etudes/presidentielle_attal/predictif_pres2027_attal_programme.json"
ATTAL_PLAGE = ("reports/etudes/presidentielle_attal/plages/"
               "a16_droit_au_brut__cotisations_salariales_retraite_echelle__{}.json")
PPA = "reports/etudes/plfss2027/premiere_annee_plf2027_art_74_ppa.json"
PPA_PRED = "reports/etudes/plfss2027/predictif_plf2027_art_74_ppa.json"
PPA_SCENARIO = "scenarios/plf2027_art_74_ppa.json"
PPA_ETUDE = "etudes/plfss2027.json"
VERIFICATION = "reports/verification/grille.json"
MANIFESTE = "data/raw/MANIFEST.json"
ECART_PPA = "reports/ecart_ppa.md"
#: Les deux boutons du curseur : (curseur de la grille, étude, mesure du programme).
BOUTONS = ("cotisations_retraite", "plf_art_74_ppa")


def lire(chemin: str) -> Any:
    path = ROOT / chemin
    if not path.exists():
        raise ParcoursError(f"le parcours lit {chemin}, absent du dépôt.")
    return json.loads(path.read_text(encoding="utf-8"))


def num(x: float, dec: int = 2) -> str:
    """Un nombre à la française : virgule décimale, espace fine entre les milliers, le
    signe moins typographique, et pas de « −0 »."""
    text = f"{abs(x):,.{dec}f}".replace(",", "\u202f").replace(".", ",")
    return ("−" if x < 0 and round(abs(x), dec) else "") + text


def signe(x: float, dec: int = 2) -> str:
    return ("+" if x > 0 and round(x, dec) else "") + num(x, dec)


def md(eur: float, dec: int = 2, signed: bool = True) -> str:
    return f"{(signe if signed else num)(eur / 1e9, dec)} Md€"


def meur(eur: float, dec: int = 0, signed: bool = True) -> str:
    return f"{(signe if signed else num)(eur / 1e6, dec)} M€"


def pct(x: float, dec: int = 1, signed: bool = True) -> str:
    return f"{(signe if signed else num)(x * 100, dec)} %"


def pt(x: float, dec: int = 2) -> str:
    return f"{signe(x * 100, dec)} pt"


def b(texte: str, etage: str, conditionnel: bool = False) -> str:
    """Un nombre et son étage, comme sur les pages d'étude (`site._badge`)."""
    return site._badge(etude.Nombre(texte, etage, conditionnel))


def e(text: Any) -> str:
    return html.escape(str(text), quote=False)


def tableau(entetes: list[str], lignes: list[list[str]], classe: str = "") -> str:
    head = "".join(f"<th>{h}</th>" for h in entetes)
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>"
                   for row in lignes)
    cls = f' class="{classe}"' if classe else ""
    return f"<table{cls}><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def commit(sha: str) -> str:
    return (f'<a href="{DEPOT}/commit/{html.escape(sha)}"><code>{html.escape(sha[:7])}'
            "</code></a>")


def manifeste(nom: str) -> str:
    """L'URL publique d'un fichier brut, lue dans le manifeste commité."""
    files = lire(MANIFESTE)["files"]
    if nom not in files or not files[nom].get("url"):
        raise ParcoursError(f"{nom} n'a pas d'URL dans {MANIFESTE}.")
    return files[nom]["url"]


def menages_entreprises(report: dict[str, Any]) -> tuple[dict[str, Any], dict | None]:
    """Les réponses des ménages et des entreprises d'un rapport de première année."""
    r = report["response"]
    if report["kind"] == "mixte":
        return r["menages"], r.get("entreprises")
    if report["kind"] == "menages":
        return r, None
    raise ParcoursError(f"{report['scenario']} : rapport « {report['kind']} » inattendu.")


def cout_total(report: dict[str, Any]) -> float:
    m, f = menages_entreprises(report)
    return float(m["reform_cost"]) + (float(f["reform_cost"]) if f else 0.0)


def loi_erreur(ligne: str) -> dict[str, Any]:
    """Le biais d'une ligne de la grille de vérification, et l'URL de sa source."""
    g = lire(VERIFICATION)
    if ligne not in g["loi"]:
        raise ParcoursError(f"la grille de vérification n'a pas de ligne « {ligne} ».")
    rows = [r for r in g["lignes"] if r["id"] == ligne]
    return {**g["loi"][ligne], "url": rows[-1]["url"], "source": rows[-1]["source"]}


def ecart_rel(g: Any) -> str:
    return "n/a" if g.relative_gap is None else pct(g.relative_gap, 0)


def clopper_pearson(k: int, n: int, niveau: float = 0.95) -> tuple[float, float]:
    """L'intervalle exact d'une proportion k/n (Clopper-Pearson), par bissection sur la
    loi binomiale : l'arithmétique de la phrase de `docs/BUT.md` sur la note de cinq cas."""
    alpha = (1 - niveau) / 2

    def cdf(j: int, p: float) -> float:
        return sum(math.comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(j + 1))

    def racine(f: Any) -> float:
        lo, hi = 0.0, 1.0
        for _ in range(200):
            mid = (lo + hi) / 2
            lo, hi = (mid, hi) if f(mid) > 0 else (lo, mid)
        return (lo + hi) / 2

    bas = 0.0 if k == 0 else racine(lambda p: alpha - (1 - cdf(k - 1, p)))
    haut = 1.0 if k == n else racine(lambda p: cdf(k, p) - alpha)
    return bas, haut


# --------------------------------------------------------------------------- #
# Attal, pas à pas
# --------------------------------------------------------------------------- #
def _mesure(slug: str, mid: str) -> dict[str, Any]:
    prog = lire(f"programmes/{slug}.json")
    for m in prog["mesures"]:
        if m["id"] == mid:
            return m
    raise ParcoursError(f"{slug} : pas de mesure {mid}.")


TRANSFERTS_LIBELLES = {
    "ppa": "prime d'activité", "aide_logement": "aides au logement", "rsa": "RSA",
    "af": "allocations familiales", "asf": "allocation de soutien familial",
    "aefa": "prime de Noël", "cf": "complément familial",
    "reduction_loyer_solidarite": "réduction de loyer de solidarité",
    "crds_pfam": "CRDS sur les prestations familiales", "crds_mini": "CRDS sur les minima",
}
ENTREPRISES_LIBELLES = {
    "cvae": "CVAE", "impot_societes": "impôt sur les sociétés",
    "contribution_sociale_is": "contribution sociale sur l'IS",
    "cebge": "contribution des grandes entreprises", "c3s": "C3S",
}


def _attal() -> str:
    from impots.guards import STATE_TRANSFERS

    rep = lire(ATTAL)
    m, f = menages_entreprises(rep)
    pred = lire(ATTAL_PRED)
    a16, a18 = _mesure("attal", "a16_droit_au_brut"), _mesure("attal", "a18_suppression_cvae")
    knob = rep["request"]["menages"]["reform"]["cotisations_salariales_retraite_echelle"]
    if a16["chiffrage"]["reforme"]["cotisations_salariales_retraite_echelle"] != knob:
        raise ParcoursError("le bouton d'Attal du rapport n'est pas celui du programme.")
    t, tr, d = m["totals"], m["totals_reform"], m["deltas"]
    cost_m, cost_f = float(m["reform_cost"]), float(f["reform_cost"])
    total = cost_m + cost_f
    transferts = {k: d[k] for k in STATE_TRANSFERS if d.get(k)}
    somme_tr = sum(transferts.values())
    reste = cost_m - (d["salaire_net"] - d["ir"] + somme_tr)
    detail_tr = " ; ".join(f"{TRANSFERTS_LIBELLES.get(k, k)} {md(v)}"
                           for k, v in sorted(transferts.items(), key=lambda kv: kv[1])
                           if abs(v) >= 1e7)
    fd = f["deltas"]
    detail_f = "impôts payés : " + " ; ".join(f"{ENTREPRISES_LIBELLES.get(k, k)} {md(v)}"
                          for k, v in fd.items()
                          if k != "prelevements_entreprise" and abs(v) >= 1e6)
    meta = m["meta"]
    dec = pred["lectures"]["decomposition"]["vieillie"]
    beh = m["behavioural"]
    cot = loi_erreur("cotisations_salariales")
    if not math.isclose(pred["years"][0]["mechanical_frozen_eur"], total, rel_tol=1e-9):
        raise ParcoursError("Attal : le chemin annuel ne part pas du coût de la première "
                            "année.")

    lignes = [
        ["Ce que promet le candidat", b(a16["parametre"], "programme"),
         source(a16["sources"][0]["url"], f"la page du candidat, {a16['sources'][0]['date']}")],
        ["Le bouton : la part des cotisations retraite des salariés gardée",
         b(num(knob, 2), "hypothèse"), fichier("programmes/attal.json")],
        ["Passe 1, la loi de 2026 : cotisations des salariés",
         b(md(t["cotisations_salariales"], signed=False), "L1"), fichier(ATTAL, "le rapport")],
        ["Passe 2, la réforme : les mêmes",
         b(md(tr["cotisations_salariales"], signed=False), "L2"), fichier(ATTAL, "le rapport")],
        ["Ce qui revient en salaire net", b(md(d["salaire_net"]), "L2"), "la différence"],
        ["Ce que l'impôt sur le revenu en reprend (le salaire imposable monte de "
         f"{md(d['salaire_imposable'])})", b(md(-d["ir"]), "L2"), "la différence"],
        [f"Ce que les prestations sous condition de ressources en reprennent ({e(detail_tr)})",
         b(md(somme_tr), "L2"), "la différence"],
        ["Autres lignes du revenu disponible", b(md(reste), "L2"), "le reste"],
        ["<strong>Le revenu disponible des ménages : leur coût</strong>",
         "<strong>" + b(md(cost_m), "L2") + "</strong>", "la différence"],
        [f"Les entreprises, la CVAE supprimée ({e(detail_f)})", b(md(cost_f), "L2"),
         source(a18["sources"][0]["url"], f"la page du candidat, {a18['sources'][0]['date']}")],
        ["<strong>Le coût de la première année</strong>",
         "<strong>" + b(md(total), "L2") + "</strong>", "la somme"],
    ]
    return f"""
<h2 id="attal">Attal, « Droit au brut », pas à pas</h2>
<p>Le candidat énonce un gain, pas un taux. L'outil le traduit en un bouton, et le dit :</p>
<blockquote>{e(a16["chiffrage"]["note"])}</blockquote>
<p>La population est celle de 2024 ({b(num(meta["households"] / 1e6, 2) + " M", "L1")}
ménages, dont {b(num(meta["sampled_households"], 0), "L1")} tirés et repondérés), le droit
celui de 2026. Une passe applique la loi, l'autre la loi avec le bouton ; le coût est ce que
le revenu disponible des ménages gagne d'une passe à l'autre, plus ce que les entreprises
paient en moins. Personne ne change de comportement entre les deux passes.</p>
{tableau(["étape", "nombre", "d'où"], lignes)}
<p>Le coût n'est pas « ce que coûtent les cotisations » : sur
{b(md(d["salaire_net"]), "L2")} rendus aux salariés, l'impôt sur le revenu en reprend
{b(md(d["ir"], signed=False), "L2")} et les prestations
{b(md(-somme_tr, signed=False), "L2")}, parce que la même passe recalcule tout ce qui
dépend du salaire. Chaque terme est une différence entre deux totaux du
{fichier(ATTAL, "rapport de première année")}, calculés par
{fichier("src/impots/population/runner.py")}.</p>
<p><strong>Ce que ce coût ne contient pas.</strong> Aucun comportement :
« {e(beh["grade_reason"])} » ({lien("comportements", "page 4")}). Aucun effet sur
l'activité : c'est la {lien("activite", "page 5")}. La dette de 2035 part de ce coût :
{b(pt(dec["cout"]), "L2", True)} sans aucune boucle, puis
{b(pt(dec["denominateur"]), "L4", True)} par le PIB plus haut et
{b(pt(dec["retroaction"]), "L4", True)} par les recettes que l'activité rend, soit
{b(pt(dec["total"]), "L4", True)} ({fichier(ATTAL_PRED, "le chemin annuel")},
{lien("dette", "page 6")}).</p>
<p><strong>L'erreur de ce coût est celle de son assiette.</strong> La grille de vérification
compare le total des cotisations des salariés du moteur à celui des comptes nationaux
({source(cot["url"], "Insee, compte des ménages, ligne D613CE")}) : en moyenne sur
{len(cot["annees"])} ans, {b(pct(cot["biais"]), "vérifié")} (de
{b(pct(cot["min"]), "vérifié")} à {b(pct(cot["max"]), "vérifié")}),
{cot["tenues"]} années sur {len(cot["annees"])} dans la tolérance
({fichier(VERIFICATION)}). Le coût d'Attal est une part de cette assiette. Si l'écart porte
aussi sur les cotisations de retraite, le coût est trop bas d'autant ; la grille ne sépare
pas les branches, et cela reste une hypothèse.</p>
"""


# --------------------------------------------------------------------------- #
# La prime d'activité, pas à pas
# --------------------------------------------------------------------------- #
def _miroir(scenario: str) -> bool:
    for s in lire(PPA_ETUDE)["scenarios"]:
        if s["scenario"] == scenario:
            return bool(s.get("miroir"))
    raise ParcoursError(f"{scenario} n'est pas dans {PPA_ETUDE}.")


def _rapport_des_bases() -> tuple[str, str]:
    """Le rapport des bases moteur/Cnaf par point de forfait, mesuré une fois (D-315)."""
    text = (ROOT / ECART_PPA).read_text(encoding="utf-8")
    ratio = re.search(r"Le rapport des bases : \*\*([\d,]+)\*\*", text)
    sha = re.search(r"Commit `([0-9a-f]{7,40})`", text)
    if not (ratio and sha):
        raise ParcoursError(f"{ECART_PPA} ne donne plus le rapport des bases.")
    return ratio[1], sha[1]


def _ppa() -> str:
    from impots import preregistration as pr

    rep = lire(PPA)
    m, _ = menages_entreprises(rep)
    pred = lire(PPA_PRED)
    scen = lire(PPA_SCENARIO)
    if not _miroir("plf2027_art_74_ppa"):
        raise ParcoursError("la prime de l'art. 74 n'est plus chiffrée en miroir.")
    knob = rep["request"]["reform"]["ppa_revalorisation_avril"]
    if scen["reform"]["ppa_revalorisation_avril"] != knob:
        raise ParcoursError("le bouton de la prime du rapport n'est pas celui du scénario.")
    t, d = m["totals"], m["deltas"]
    s = -1.0  # en miroir : l'article est l'opposé de ce que chiffre le scénario
    cost = s * float(m["reform_cost"])
    autres = float(m["reform_cost"]) - d["ppa"]
    pire = min(m["deciles"], key=lambda r: s * r["mean_delta"])
    years = pred["years"]
    plein = next(y for y in years if y["year"] == 2027)
    dec = pred["lectures"]["decomposition"]
    case = pr.load("plf2027_art_74_ppa")
    g = pr.grade(case)
    servi = loi_erreur("ppa_montant_servi")
    ratio, sha = _rapport_des_bases()
    texte = manifeste("plf2027_texte_an_b3210.html")
    annexe = manifeste("plf2027_evaluations_prealables.pdf")
    page = re.search(r"p\. (\d+)", case.comparator.source)
    if page is None:
        raise ParcoursError("le comparateur de la prime ne dit plus sa page.")
    beh = m["behavioural"]
    lignes = [
        ["Le texte : la revalorisation d'avril 2027 de la prime n'est pas appliquée",
         b("art. 74", "texte"), source(texte, "PLF 2027, texte n° 3210 (Assemblée)")],
        ["Le bouton, en miroir : la revalorisation que l'article suspend",
         b(pct(knob - 1, 1), "hypothèse"), fichier(PPA_SCENARIO)],
        ["Passe 1, la loi : la prime à laquelle les foyers ont droit",
         b(md(t["ppa_droit"], signed=False), "L1"), fichier(PPA, "le rapport")],
        ["… et celle qu'ils perçoivent, une fois le non-recours compté",
         b(md(t["ppa"], signed=False), "L1"), fichier(PPA, "le rapport")],
        ["Passe 2 moins passe 1, au signe de l'article : le droit",
         b(meur(s * d["ppa_droit"]), "L2"), "la différence"],
        ["… la prime perçue", b(meur(s * d["ppa"]), "L2"), "la différence"],
        ["… la CRDS prélevée sur elle", b(meur(s * autres, 1), "L2"), "la différence"],
        ["<strong>Le coût de l'article la première année</strong>",
         "<strong>" + b(meur(cost), "L2") + "</strong>", "la différence"],
        [f"Le dixième le plus touché, le {pire['decile']}<sup>e</sup>, par ménage et par an",
         b(f"{signe(s * pire['mean_delta'], 1)} €", "L2"), fichier(PPA, "le rapport")],
    ]
    pas = (s * years[-1]["mechanical_aged_eur"], s * plein["mechanical_aged_eur"])
    return f"""
<h2 id="prime">La prime d'activité, art. 74 du PLF 2027, pas à pas</h2>
<p>L'article suspend une revalorisation. L'arbre de la loi que le moteur lit n'en porte
aucune en 2027 : l'état final de l'article y est déjà. Le scénario chiffre donc l'inverse,
la revalorisation, et l'article en est l'opposé (« en miroir »). Le droit de 2026 tient lieu
de celui de 2027, et le scénario le dit :</p>
<blockquote>{e(scen["note"])}</blockquote>
{tableau(["étape", "nombre", "d'où"], lignes)}
<p>Le moteur calcule le droit de chaque foyer, puis la part qu'il perçoit en espérance,
une fois le non-recours compté : {b(pct(d["ppa"] / d["ppa_droit"], 0, signed=False), "L2")}
du droit en jeu ({b(meur(d["ppa"], signed=False), "L2")} perçus sur
{b(meur(d["ppa_droit"], signed=False), "L2")} de droit). Aucune bande : « {e(beh["grade_reason"])} »
Aucune boucle : une prestation n'a pas de variante dans Mésange
({fichier("src/impots/macro/shocks.py")}). La dette n'a ici qu'un étage, l'économie cumulée
avec ses intérêts : {b(pt(s * dec["vieillie"]["total"]), "L2", True)} en 2035 dans la vue
vieillie, {b(pt(s * dec["figee"]["total"]), "L2", True)} dans la vue figée
({fichier(PPA_PRED, "le chemin annuel")}). En année pleine, 2027, le coût de l'article est
de {b(meur(s * plein["mechanical_frozen_eur"]), "L2")} (un coût négatif rapporte) ; dans la
vue vieillie, où le droit reste en euros de 2026 quand les salaires montent, il passe de
{b(meur(pas[1]), "L2")} en 2027 à {b(meur(pas[0]), "L2")} en 2035.</p>
<p><strong>Le juge.</strong> Le gouvernement chiffre l'article à
{b(meur(g.published_eur), "publié")} pour l'État en 2027
({source(f"{annexe}#page={page[1]}", f"évaluations préalables, p. {page[1]}")}). Le cas a
été enregistré le {e(case.pre_registered[:10])}, au commit {commit(case.commit)}, avant que
la fiche de l'article dans l'annexe soit lue
({fichier("docs/DECISIONS.md", "D-298")}), à {b(meur(g.simulated_eur), "L2")}, avec une tolérance de
{b(meur(g.allowed_eur, signed=False), "déclaré")} : l'écart, {b(meur(g.gap_eur), "L2")}
({b(pct(g.relative_gap, 0), "L2")}), la met hors de sa tolérance
({fichier(f"chiffrages_preregistres/{case.case}.yaml")}). Ce que le chiffre officiel compte
et ce que le cas compte ne sont pas la même chose : « {e(case.comparator.net_of)} ». La
série d'aujourd'hui donne {b(meur(cost), "L2")} ; la note ne change pas pour autant : le
chiffre noté reste celui de l'enregistrement.</p>
<p><strong>Le niveau et l'écart vont en sens contraires.</strong> La grille de vérification
met la prime perçue {b(pct(servi["biais"]), "vérifié")} sous ce que verse la Cnaf, en
moyenne de {servi["annees"][0]} à {servi["annees"][-1]}
({source(servi["url"], "Cnaf")}, {fichier(VERIFICATION)}) ; le coût de la mesure, lui, est
au-dessus du chiffre officiel. Un coût ne suit pas le niveau de sa base : il suit ce que la
base gagne quand le bouton bouge. Cette sensibilité n'a été mesurée contre la Cnaf qu'une
fois, sur un modèle d'avant (commit {commit(sha)}) : un point de forfait y rapportait
{b(ratio, "vérifié")} fois plus au moteur qu'à la Cnaf ({fichier(ECART_PPA)}). Pour les
autres instruments, l'erreur d'un coût n'est pas mesurée.</p>
"""


# --------------------------------------------------------------------------- #
# Les juges
# --------------------------------------------------------------------------- #
def _lien_juge(case: Any) -> str:
    src = case.comparator.source
    if not src.startswith("PLF 2027, évaluations préalables"):
        raise ParcoursError(f"{case.case} : un juge hors de l'annexe du PLF 2027, dont la "
                            "page ne sait pas encore donner le lien.")
    where = re.search(r"art\. \d+, § [\d.]+, p\. (\d+)", src)
    if where is None:
        raise ParcoursError(f"{case.case} : le comparateur ne dit pas sa page.")
    url = manifeste("plf2027_evaluations_prealables.pdf") + f"#page={where[1]}"
    return source(url, where[0])


def _juges() -> str:
    from impots import preregistration as pr

    notes, revus, attente = [], [], []
    for name in pr.available():
        case = pr.load(name)
        if case.comparator is None:
            attente.append(case)
            continue
        pr.verify_tolerance_unchanged(name)
        (revus if case.revision else notes).append((pr.grade(case), case))

    def ligne(g: Any, case: Any) -> list[str]:
        return [f"<code>{e(case.case)}</code>",
                f"{e(case.pre_registered[:10])}, {commit(case.commit)}",
                b(md(g.simulated_eur, 3), "L2"), b(md(g.published_eur, 3), "publié"),
                b(f"{md(g.gap_eur, 3)} ({ecart_rel(g)})", "L2"),
                b(f"± {md(g.allowed_eur, 3, signed=False)}", "déclaré"),
                ("dans la tolérance" if g.verdict == "within" else "<strong>hors</strong>"),
                _lien_juge(case)]

    entetes = ["cas", "enregistré le", "simulé", "officiel", "écart", "toléré", "note",
               "le juge"]
    tenus = sum(g.verdict == "within" for g, _ in notes)
    bas, haut = clopper_pearson(tenus, len(notes))
    revus_tenus = sum(g.verdict == "within" for g, _ in revus)
    attente_rows = [[f"<code>{e(c.case)}</code>",
                     f"{e(c.pre_registered[:10])}, {commit(c.commit)}",
                     b(md(c.mechanical_eur, 3), "L2"),
                     b(f"{pct(c.tolerance.relative, 0, signed=False)} ou "
                       f"{meur(c.tolerance.absolute_eur, signed=False)}", "déclaré")]
                    for c in attente]
    return f"""
<h2 id="juges">Les juges</h2>
<p>Un coût se juge contre le chiffrage officiel publié avec le texte, quand il existe. La
règle du projet : le cas est chiffré et sa tolérance écrite, puis le tout est commité et
poussé, <em>avant</em> que la fiche de l'article dans l'annexe des évaluations préalables
soit ouverte. Le commit est la
date de l'enregistrement ; une tolérance qui aurait bougé depuis est refusée
({fichier("src/impots/preregistration.py")}, chaque cas dans
{fichier("chiffrages_preregistres")}).</p>
{tableau(entetes, [ligne(g, c) for g, c in notes])}
<p><strong>{tenus} sur {len(notes)}</strong> dans leur tolérance. Cinq cas notent peu : à
{tenus} réussites sur {len(notes)}, l'intervalle de confiance à 95 % du taux de réussite va
de {b(pct(bas, 0, signed=False), "L2")} à {b(pct(haut, 0, signed=False), "L2")}
(intervalle exact de Clopper-Pearson). La note ne distingue pas un bon outil d'un mauvais
({fichier("docs/BUT.md")}).</p>
<p>À part, des révisions écrites après l'ouverture de l'annexe (une autre année de base, une
population vieillie, un volet isolé) : elles ne sont pas aveugles et ne comptent pas dans la
note. {revus_tenus} sur {len(revus)} tiennent leur tolérance.</p>
{tableau(entetes, [ligne(g, c) for g, c in revus])}
<p>En attente de leur juge : {len(attente)} mesures des programmes, enregistrées sans
chiffrage officiel à leur opposer. Leur chiffre est celui du code du jour de
l'enregistrement, pas celui de la série ; c'est lui qui sera noté.</p>
{tableau(["cas", "enregistré le", "simulé", "toléré"], attente_rows)}
"""


# --------------------------------------------------------------------------- #
# Le curseur : le bouton, sur la grille de l'explorateur
# --------------------------------------------------------------------------- #
def _points(cid: str) -> tuple[Any, list[dict[str, Any]]]:
    from impots import grille

    curseurs, _, _ = grille.charger()
    c = curseurs[cid]
    pts = grille.points_de(c)
    for p in pts:
        if p["report"]["dirty"]:
            raise ParcoursError(f"{cid} : un point de la grille sur un arbre sale.")
    return c, pts


def _bouton_donnees() -> tuple[dict[str, Any], str]:
    """Les points des deux boutons, mis en forme ; et leur tableau statique."""
    from impots import grille

    out: dict[str, Any] = {}
    tables = []
    c, pts = _points("cotisations_retraite")
    knob = lire(ATTAL)["request"]["menages"]["reform"]["cotisations_salariales_retraite_echelle"]
    xs = [p["x"] for p in pts]
    ys = [p["report"]["cout"]["total"] for p in pts]
    interp = grille.interpoler(xs, ys, knob, c.interpolation)
    plage = {k: lire(ATTAL_PLAGE.format(k)) for k in ("bas", "candidat")}
    p_bas = plage["bas"]["response"]["mechanical_first_year_eur"]
    p_cand = plage["candidat"]["response"]["mechanical_first_year_eur"]
    if plage["bas"]["request"]["reform"]["cotisations_salariales_retraite_echelle"] != xs[0]:
        raise ParcoursError("la plage basse d'Attal n'est plus le premier point de la grille.")
    r_bas, r_cand = p_bas / ys[0], p_cand / interp
    if abs(r_bas - r_cand) <= 0.01:
        forme = (f"Le rapport de la série à la grille est le même aux deux boutons, "
                 f"{num(r_cand, 3)} et {num(r_bas, 3)} : le bouton n'a pas changé la forme "
                 "du coût, la base l'a déplacée tout entière quand la population a été "
                 f"refaite ({fichier('docs/DECISIONS.md', 'D-368 et D-373')} en donnent les "
                 "raisons).")
    else:
        forme = (f"Le rapport de la série à la grille n'est pas le même aux deux boutons, "
                 f"{num(r_cand, 3)} et {num(r_bas, 3)} : la population refaite a changé la "
                 "forme du coût, pas seulement son niveau.")
    gcommit = pts[0]["report"]["commit"]
    gdate = pts[0]["report"]["computed"]
    out["cotisations"] = [
        {"x": f"{num(p['x'], 2)}",
         "dit": (f"on garde {pct(p['x'], 0, signed=False)} des cotisations retraite des "
                 "salariés"),
         "cout": md(p["report"]["cout"]["total"])} for p in pts]
    tables.append(tableau(
        ["échelle", "ce que cela veut dire", "coût la première année (grille)"],
        [[num(p["x"], 2), e(f"on garde {pct(p['x'], 0, signed=False)} des cotisations"),
          b(md(p["report"]["cout"]["total"]), "L2")] for p in pts]))

    _, pts2 = _points("plf_art_74_ppa")
    ppa_knob = lire(PPA)["request"]["reform"]["ppa_revalorisation_avril"]
    serie_v = lire(PPA_PRED)["years"][0]["mechanical_aged_eur"]
    un = next(p for p in pts2 if math.isclose(p["x"], 1.0))
    out["ppa"] = [
        {"x": f"{num(p['x'], 2)}",
         "dit": ("suspendre une revalorisation d'avril de "
                 f"{pct(p['x'] * (ppa_knob - 1), 2, signed=False)}"),
         "cout": meur(-p["report"]["cout"]["total"])} for p in pts2]
    tables.append(tableau(
        ["λ", "la revalorisation que l'article suspend", "ce que l'article économise (grille)"],
        [[num(p["x"], 2), e(f"{pct(p['x'] * (ppa_knob - 1), 2, signed=False)}"),
          b(meur(-p["report"]["cout"]["total"]), "L2")] for p in pts2]))
    if any(p["report"]["commit"] != gcommit for p in pts + pts2):
        raise ParcoursError("les points des deux boutons ne sont pas d'un même commit.")
    depart = {"cotisations": min(range(len(xs)), key=lambda k: abs(xs[k] - knob)),
              "ppa": next(k for k, p in enumerate(pts2) if math.isclose(p["x"], 1.0))}
    texte = f"""
<p>Les points viennent de la grille de l'<a href="explorer.html">explorateur</a> : une
passe par point, chiffrée d'avance le {e(gdate)} au commit {commit(gcommit)}
({fichier("reports/grille/cotisations_retraite")}, {fichier("reports/grille/plf_art_74_ppa")},
compilés par {fichier("src/impots/grille.py")}). Le curseur choisit un point ; il ne calcule
rien. Les points sont dans la vue vieillie (la population de 2024 portée à 2026).</p>
<p><strong>La grille est d'avant la série.</strong> Elle a tourné avant que la population ne
soit refaite (but 19). Au bouton d'Attal, {num(knob, 2)}, l'explorateur interpole
{b(md(interp), "L2")} entre deux points ; la série, sur le code d'aujourd'hui, mesure
{b(md(p_cand), "L2")} ({fichier(ATTAL_PLAGE.format("candidat"), "sa plage")}). À
l'échelle 0, la grille dit {b(md(ys[0]), "L2")}, la série {b(md(p_bas), "L2")}. {forme}
Pour la prime, à λ = 1, la grille
dit {b(meur(-un["report"]["cout"]["total"]), "L2")} et la série
{b(meur(-serie_v), "L2")} dans la même vue : le non-recours est entré entre les deux.</p>
"""
    return {**out, "depart": depart}, texte + "".join(tables)


SCRIPT = """
(function () {
  var D = __DONNEES__;
  function brancher(cle) {
    var curseur = document.getElementById("bouton-" + cle);
    var x = document.getElementById("bouton-" + cle + "-x");
    var dit = document.getElementById("bouton-" + cle + "-dit");
    var cout = document.getElementById("bouton-" + cle + "-cout");
    if (!curseur) { return; }
    function montrer() {
      var p = D[cle][Number(curseur.value)];
      x.textContent = p.x; dit.textContent = p.dit; cout.textContent = p.cout;
    }
    curseur.addEventListener("input", montrer);
    montrer();
  }
  brancher("cotisations");
  brancher("ppa");
})();
"""


def _curseur(donnees: dict[str, Any]) -> str:
    def un(cle: str, titre: str, loi: int) -> str:
        n = len(donnees[cle]) - 1
        p = donnees[cle][loi]
        return (f'<div class="curseur"><label for="bouton-{cle}">{e(titre)}</label>'
                f'<input type="range" id="bouton-{cle}" min="0" max="{n}" step="1" '
                f'value="{loi}"><output id="bouton-{cle}-x" class="num">{e(p["x"])}</output>'
                f'</div><p class="lecture"><span id="bouton-{cle}-dit">{e(p["dit"])}</span> : '
                f'<strong id="bouton-{cle}-cout">{e(p["cout"])}</strong> la première année.</p>')

    # Au départ, chaque curseur est sur le point le plus proche de la mesure étudiée.
    return (un("cotisations", "Cotisations retraite des salariés, la part gardée",
               donnees["depart"]["cotisations"])
            + un("ppa", "Prime d'activité : λ fois la revalorisation suspendue",
                 donnees["depart"]["ppa"])
            + "<noscript><p>Sans JavaScript, le curseur ne bouge pas : chaque point qu'il "
              "choisirait est dans les tableaux ci-dessous.</p></noscript>")


def page() -> Page:
    donnees, statique = _bouton_donnees()
    rep = lire(ATTAL)
    corps = f"""
<p>Une mesure ne se chiffre pas en multipliant un taux par une assiette. L'outil fait
tourner la loi deux fois sur la même population de ménages et d'entreprises, une fois telle
qu'elle est, une fois avec la mesure, et compte ce qui change. Le coût de la première année
est cette différence, rien d'autre : la première des trois réponses de chaque étude, et la
plus sûre. Son erreur est celle de la base qu'il touche, et la page le montre sur deux
mesures, avec les nombres de la série du {e(rep["computed"])} (commit
{commit(rep["commit"])}).</p>
{_attal()}
{_ppa()}
{_juges()}
<h2 id="bouton">Le bouton</h2>
<p>Un coût dépend du bouton qu'on tourne. Choisissez un point : le coût de la première année
qu'une passe a donné à ce bouton, la loi intacte autour.</p>
{_curseur(donnees)}
{statique}
<p><strong>Ce qui n'est pas construit.</strong> Un interrupteur « corrigé par la ligne de
vérification », qui remettrait chaque coût à l'échelle de l'écart de sa base, changerait un
coût affiché : il demande d'être préenregistré avant d'être calculé, et ne l'est pas
({fichier("docs/DECISIONS.md", "D-375")}). Les comparaisons de deux candidats sur ces coûts
sont sur la page {lien("comparer", "Comparer deux candidats")}.</p>
"""
    script = SCRIPT.replace("__DONNEES__", _json_script(donnees))
    return Page(prouve="un coût est la différence de deux passes sur la même population, "
                       "et son erreur est celle de la base qu'il touche.",
                corps=corps, script=script,
                style="p.lecture{font-family:system-ui,sans-serif;margin:.2rem 0 1rem}")


def _json_script(data: Any) -> str:
    """Du JSON qu'on peut poser dans un <script> sans le fermer."""
    return (json.dumps(data, ensure_ascii=False).replace("<", "\\u003c")
            .replace(">", "\\u003e").replace("&", "\\u0026"))

