"""« En bref » : ce que les dimensions calculées disent, en français simple, écrit par des
règles (but 29, volet `synthese`, D-650).

Aucun modèle de langue : chaque phrase sort d'un gabarit et d'un seul indicateur d'une
seule dimension, qu'elle cite (`dimension`, `indicateur`), avec l'année, la valeur et la
bande qu'elle lit. Les règles ne connaissent que l'interface (`impacts.Dimension`, ou sa
forme JSON `impacts.vers_dict`) : une dimension inscrite demain par un autre volet entre
dans le paragraphe sans changer ce fichier.

LES RÈGLES (D-650) :

* **La certitude d'une phrase** vient de la bande de l'indicateur qu'elle lit, à l'année
  qu'elle dit, et du statut de sa dimension :
  - « probablement » : la bande existe et reste tout entière d'un côté de zéro
    (bas et haut strictement de même signe), et la dimension n'est pas illustrative ;
  - « un ordre de grandeur » : la dimension est illustrative ; jamais « probablement »,
    même quand sa bande reste d'un côté ;
  - « le sens n'est pas sûr » : la bande touche ou franchit zéro ;
  - « au calcul central, sans bande » : l'indicateur n'a pas de bande.
  Un nombre par groupe (un décile, un cas type) n'a pas de bande : il n'est jamais dit
  « probablement ».
* **Ce qui bouge le plus** : les dimensions n'ont pas d'unité commune, on ne compare donc
  pas leurs tailles. On range les phrases par netteté : d'abord les « probablement », de
  la bande la plus loin de zéro au regard de sa largeur (min(|bas|, |haut|) / (haut −
  bas)) à la plus proche ; puis les ordres de grandeur, les nombres sans bande, ceux dont
  le sens n'est pas sûr.
* **Pour qui** : quand un indicateur porte les dix déciles, la moyenne des trois premiers
  (les 30 % les plus modestes) et des trois derniers (les 30 % les plus aisés), et le
  décile où l'écart est le plus grand ; d'autres groupes : le plus grand et le plus petit.
* **À quelle échéance** : la première année calculée contre l'horizon ; l'écart change de
  sens, grandit (au moins double), s'atténue (au plus la moitié), ou est là dès le début.
* **Les arbitrages** : pour chaque dimension, son premier indicateur qui a un sens (« plus
  haut est mieux » ou « moins bien »), quand sa bande reste d'un côté de zéro (une phrase
  « probablement », ou un ordre de grandeur dont le signe est sûr) ; ceux qui vont du côté « mieux » face à ceux qui vont du côté « moins
  bien », en mots, sans nombre. Et, dans une dimension, les 30 % les plus modestes face
  aux 30 % les plus aisés quand ils vont en sens contraires.
* **Jamais de somme entre dimensions, jamais de verdict global** : aucun nombre d'une
  phrase ne vient d'une autre dimension que la sienne ; aucun mot ne juge l'ensemble.
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from typing import Any

#: Les déciles reconnus dans `par_groupe`.
DECILES = tuple(f"D{i}" for i in range(1, 11))
#: L'ordre des certitudes, de la plus nette à la moins nette.
CERTITUDES = ("probable", "ordre_de_grandeur", "sans_bande", "incertain")
#: Ce que la page affiche sous le paragraphe, toujours.
AVERTISSEMENT = (
    "Écrit par des règles à partir des nombres ci-dessous (D-650), pas par un modèle de "
    "langue. Ces phrases ne s'additionnent pas et ne disent pas si la proposition est "
    "bonne ou mauvaise : chaque dimension garde son unité, et ce que le jumeau ne mesure "
    "pas n'y est pas.")
#: Les seuils de l'échéance : au moins double (grandit), au plus la moitié (s'atténue).
GRANDIT, ATTENUE = 2.0, 0.5
#: L'espace fine insécable des milliers.
FINE = "\u202f"
#: En deçà, un nombre est nul (des arrondis du calcul).
NUL = 1e-9


# --------------------------------------------------------------------------- #
# les nombres en français
# --------------------------------------------------------------------------- #
def nombre(x: float, signe: bool = False) -> str:
    """Un nombre lisible : trois chiffres significatifs au plus sous 100, l'entier
    au-delà ; la virgule, l'espace fine des milliers, le vrai signe moins."""
    a = abs(x)
    if a >= 100:
        d = 0
    elif a >= 10:
        d = 1
    elif a >= 1 or a == 0:
        d = 2
    else:
        d = min(6, 1 - math.floor(math.log10(a)))
    t = f"{a:,.{d}f}".replace(",", FINE).replace(".", ",")
    if float(f"{a:.{d}f}") == 0:
        return t
    if x < 0:
        return "−" + t
    return ("+" + t) if signe else t


def _unite(u: str) -> str:
    return u


def _bas_casse(s: str) -> str:
    """Le libellé en milieu de phrase : la minuscule initiale, sauf un sigle (PIB, B9)."""
    if len(s) > 1 and s[:2].isalpha() and s[:2].isupper():
        return s
    return s[:1].lower() + s[1:]


def _texte_nombres(t: str) -> list[str]:
    """Les nombres écrits dans un texte (pour les tests) : signe, chiffres, virgule."""
    return re.findall(r"[−+-]?\d[\d" + FINE + r"]*(?:,\d+)?", t)


# --------------------------------------------------------------------------- #
# la forme commune
# --------------------------------------------------------------------------- #
def _dict(d: Any) -> Mapping[str, Any]:
    if isinstance(d, Mapping):
        return d
    from impots.jumeau import impacts
    from impots.jumeau.impacts.tableau import propre

    return propre(impacts.vers_dict(d))


def _fini(x: Any) -> float | None:
    if x is None:
        return None
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _a(serie: Sequence[Any] | None, i: int) -> float | None:
    if not serie or i >= len(serie):
        return None
    return _fini(serie[i])


def _indices(ind: Mapping[str, Any]) -> list[int]:
    return [i for i, x in enumerate(ind.get("valeurs") or []) if _fini(x) is not None]


def certitude(valeur: float | None, bas: float | None, haut: float | None,
              statut: str) -> str:
    """La règle de la certitude d'une phrase (D-650)."""
    if statut == "illustratif":
        return "ordre_de_grandeur"
    if bas is None or haut is None:
        return "sans_bande"
    if (bas > NUL and haut > NUL) or (bas < -NUL and haut < -NUL):
        return "probable"
    return "incertain"


def bande_d_un_cote(bas: float | None, haut: float | None) -> bool:
    return (bas is not None and haut is not None
            and ((bas > NUL and haut > NUL) or (bas < -NUL and haut < -NUL)))


def nettete(bas: float | None, haut: float | None) -> float:
    """La distance de la bande à zéro au regard de sa largeur ; 0 si elle touche zéro."""
    if not bande_d_un_cote(bas, haut):
        return 0.0
    lo, hi = min(bas, haut), max(bas, haut)  # type: ignore[type-var]
    largeur = hi - lo
    proche = min(abs(lo), abs(hi))
    return math.inf if largeur <= NUL else proche / largeur


def _sens_mot(valeur: float, sens: int) -> str | None:
    if sens == 0 or abs(valeur) <= NUL:
        return None
    return "mieux" if valeur * sens > 0 else "moins bien"


def _direction(valeur: float) -> str:
    return "en hausse" if valeur > 0 else "en baisse"


def _statut_txt(d: Mapping[str, Any]) -> str:
    s = d.get("statut") or ""
    return f"{s}, {d['juge']}" if s == "jugé" and d.get("juge") else s


# --------------------------------------------------------------------------- #
# les phrases
# --------------------------------------------------------------------------- #
def _phrase_tete(d: Mapping[str, Any], ind: Mapping[str, Any]) -> dict[str, Any] | None:
    k = _indices(ind)
    if not k:
        return None
    f = k[-1]
    annees = d.get("annees") or []
    an = annees[f] if f < len(annees) else None
    v = _fini(ind["valeurs"][f])
    assert v is not None
    bas, haut = _a(ind.get("bas"), f), _a(ind.get("haut"), f)
    c = certitude(v, bas, haut, d["statut"])
    u = _unite(ind["unite"])
    lib = ind["libelle"]
    bande = (f" (bande : de {nombre(bas, True)} à {nombre(haut, True)})"
             if bas is not None and haut is not None else "")
    sens = _sens_mot(v, int(ind.get("sens") or 0))
    nul_partout = abs(v) <= NUL and (bas is None or abs(bas) <= NUL) and \
        (haut is None or abs(haut) <= NUL)
    if nul_partout:
        corps = f"sans effet en {an}"
    elif c == "probable":
        corps = (f"probablement {_direction(v)}, de {nombre(abs(v))} {u} en {an}{bande}"
                 + (f", {sens} que sans la mesure" if sens else ""))
    elif c == "ordre_de_grandeur":
        if bande_d_un_cote(bas, haut) or bas is None:
            corps = (f"{_direction(v)}, un ordre de grandeur : {nombre(v, True)} {u} en {an}"
                     + (bande if bas is not None else ", sans bande")
                     + (f", {sens} que sans la mesure" if sens else ""))
        else:
            corps = (f"{_direction(v) if abs(v) > NUL else 'nul'} au centre, un ordre de "
                     f"grandeur : {nombre(v, True)} {u} en {an}, et le sens n'est pas sûr"
                     f"{bande}")
    elif c == "sans_bande":
        corps = (f"{_direction(v) if abs(v) > NUL else 'nul'} au calcul central, sans "
                 f"bande : {nombre(v, True)} {u} en {an}"
                 + (f", {sens} que sans la mesure" if sens else ""))
    else:
        corps = (f"{_direction(v) if abs(v) > NUL else 'nul'} au centre, {nombre(v, True)} {u} "
                 f"en {an}, mais le sens n'est pas sûr{bande}")
    texte = f"{d['titre']} — {lib} : {corps}."
    ech = _echeance(ind, annees, u) if not nul_partout else None
    if ech:
        texte += " " + ech
    texte += f" ({_statut_txt(d)})"
    return {"sorte": "tete", "texte": texte, "dimension": d["cle"],
            "titre": d["titre"], "indicateur": ind["cle"], "annee": an, "valeur": v,
            "bas": bas, "haut": haut, "statut": d["statut"], "certitude": c,
            "nettete": nettete(bas, haut) if c == "probable" else 0.0,
            # L'arbitrage ne lit qu'un sens sûr : une bande d'un seul côté de zéro.
            "sens": sens if bande_d_un_cote(bas, haut) and not nul_partout else None}


def _echeance(ind: Mapping[str, Any], annees: Sequence[int], u: str) -> str | None:
    """La règle de l'échéance (D-650) : la première année calculée contre l'horizon."""
    k = _indices(ind)
    if len(k) < 2:
        return None
    i0, f = k[0], k[-1]
    v0, vf = float(ind["valeurs"][i0]), float(ind["valeurs"][f])
    a0 = annees[i0] if i0 < len(annees) else "la première année"
    if abs(v0) <= NUL:
        # La première année ne bouge pas : l'effet arrive plus tard.
        j = next((i for i in k if abs(float(ind["valeurs"][i])) > NUL), None)
        if j is None:
            return None
        return (f"L'écart n'apparaît qu'en {annees[j]} ({nombre(float(ind['valeurs'][j]), True)}"
                f" {u}).")
    if abs(vf) > NUL and (v0 > 0) != (vf > 0):
        return f"L'écart change de sens en route : {nombre(v0, True)} {u} en {a0}."
    r = abs(vf) / abs(v0)
    if r >= GRANDIT:
        return f"L'écart grandit avec le temps : {nombre(v0, True)} {u} en {a0}."
    if r <= ATTENUE:
        return f"L'écart s'atténue avec le temps : {nombre(v0, True)} {u} en {a0}."
    return f"L'écart est là dès {a0} ({nombre(v0, True)} {u})."


def _derniere(groupes: Mapping[str, Sequence[Any]], noms: Sequence[str]) -> int | None:
    n = min((len(groupes[g]) for g in noms), default=0)
    for i in range(n - 1, -1, -1):
        if all(_fini(groupes[g][i]) is not None for g in noms):
            return i
    return None


def _phrase_deciles(d: Mapping[str, Any], ind: Mapping[str, Any]
                    ) -> tuple[dict[str, Any], dict[str, Any] | None] | None:
    g = ind.get("par_groupe") or {}
    if not all(x in g for x in DECILES):
        return None
    f = _derniere(g, DECILES)
    if f is None:
        return None
    an = (d.get("annees") or [None] * (f + 1))[f]
    vals = {x: float(g[x][f]) for x in DECILES}
    bas30 = sum(vals[x] for x in DECILES[:3]) / 3
    haut30 = sum(vals[x] for x in DECILES[7:]) / 3
    plus = max(DECILES, key=lambda x: abs(vals[x]))
    u = _unite(ind["unite"])
    sens = int(ind.get("sens") or 0)

    def dit(x: float) -> str:
        return "sans effet" if abs(x) <= NUL else _direction(x)

    ordre = ", un ordre de grandeur" if d["statut"] == "illustratif" else ""
    texte = (f"{d['titre']} — pour qui ({_bas_casse(ind['libelle'])}, en {an}) : "
             f"{dit(bas30)} pour les 30 % les plus modestes ({nombre(bas30, True)} {u} en "
             f"moyenne par décile), {dit(haut30)} pour les 30 % les plus aisés "
             f"({nombre(haut30, True)} {u}) ; l'écart le plus grand en {plus} "
             f"({nombre(vals[plus], True)} {u}). Au calcul central, sans bande par "
             f"décile{ordre}. ({_statut_txt(d)})")
    phrase = {"sorte": "pour_qui", "texte": texte, "dimension": d["cle"],
              "titre": d["titre"], "indicateur": ind["cle"], "annee": an,
              "valeur": None, "bas": None, "haut": None, "statut": d["statut"],
              "certitude": certitude(None, None, None, d["statut"]),
              "groupes": {"30 % les plus modestes": bas30, "30 % les plus aisés": haut30,
                          plus: vals[plus]}}
    arbitrage = None
    if sens != 0 and abs(bas30) > NUL and abs(haut30) > NUL and (bas30 > 0) != (haut30 > 0):
        lib = _bas_casse(ind["libelle"])
        arbitrage = {"dimension": d["cle"], "titre": d["titre"], "indicateur": ind["cle"],
                     "mots": f"{lib} : {dit(bas30)} pour les 30 % les plus modestes, "
                             f"{dit(haut30)} pour les 30 % les plus aisés"}
    return phrase, arbitrage


def _phrase_groupes(d: Mapping[str, Any], ind: Mapping[str, Any]) -> dict[str, Any] | None:
    g = ind.get("par_groupe") or {}
    noms = [x for x in g if x not in DECILES]
    if len(noms) < 2 or all(x in g for x in DECILES):
        return None
    f = _derniere(g, noms)
    if f is None:
        return None
    an = (d.get("annees") or [None] * (f + 1))[f]
    vals = {x: float(g[x][f]) for x in noms}
    hi = max(noms, key=lambda x: vals[x])
    lo = min(noms, key=lambda x: vals[x])
    if hi == lo or abs(vals[hi] - vals[lo]) <= NUL:
        return None
    u = _unite(ind["unite"])
    texte = (f"{d['titre']} — dans le détail ({_bas_casse(ind['libelle'])}, en {an}) : "
             f"le plus haut, « {hi} » ({nombre(vals[hi], True)} {u}) ; le plus bas, "
             f"« {lo} » ({nombre(vals[lo], True)} {u}). Au calcul central, sans bande. "
             f"({_statut_txt(d)})")
    return {"sorte": "detail", "texte": texte, "dimension": d["cle"], "titre": d["titre"],
            "indicateur": ind["cle"], "annee": an, "valeur": None, "bas": None,
            "haut": None, "statut": d["statut"],
            "certitude": certitude(None, None, None, d["statut"]),
            "groupes": {hi: vals[hi], lo: vals[lo]}}


def _phrase_arbitrages(items_mieux: list[Mapping[str, Any]],
                       items_moins: list[Mapping[str, Any]],
                       groupes: list[Mapping[str, Any]]) -> dict[str, Any] | None:
    def liste(xs: Sequence[Mapping[str, Any]]) -> str:
        return " ; ".join(f"{x['mots']} ({_bas_casse(x['titre'])})" for x in xs)

    dims = [x["dimension"] for x in (*items_mieux, *items_moins, *groupes)]
    if not dims:
        return None
    morceaux = []
    if items_mieux and items_moins:
        morceaux.append(f"Ce qu'on gagne ici, on le paie là : du côté « mieux », "
                        f"{liste(items_mieux)} ; du côté « moins bien », "
                        f"{liste(items_moins)}.")
    elif items_mieux:
        morceaux.append(f"Les nombres de tête dont le sens est sûr vont du côté « mieux » "
                        f"({liste(items_mieux)}) ; ce n'est pas un bilan : ce que le "
                        f"jumeau ne mesure pas, et ce qu'il paie ailleurs, n'y est pas.")
    elif items_moins:
        morceaux.append(f"Les nombres de tête dont le sens est sûr vont du côté « moins "
                        f"bien » ({liste(items_moins)}) ; ce n'est pas un bilan : ce que "
                        f"le jumeau ne mesure pas n'y est pas.")
    if groupes:
        morceaux.append(f"Entre les ménages : {liste(groupes)} (au calcul central).")
    return {"sorte": "arbitrage", "texte": " ".join(morceaux), "dimension": None,
            "dimensions": list(dict.fromkeys(dims)), "titre": None, "indicateur": None,
            "statut": None, "certitude": None}


def _mots(ph: Mapping[str, Any], ind: Mapping[str, Any]) -> str:
    v = ph["valeur"]
    m = f"{_bas_casse(ind['libelle'])} {_direction(v)}"
    if ph["certitude"] == "ordre_de_grandeur":
        m += ", un ordre de grandeur"
    return m


def _premier_signe(d: Mapping[str, Any]) -> Mapping[str, Any] | None:
    inds = d.get("indicateurs") or []
    for ind in inds:
        if int(ind.get("sens") or 0) != 0 and _indices(ind):
            return ind
    return None


# --------------------------------------------------------------------------- #
# le paragraphe
# --------------------------------------------------------------------------- #
def en_bref(resultat: Mapping[str, Any] | Sequence[Any]) -> dict[str, Any]:
    """Le paragraphe « En bref » d'un résultat de `navigateur.impacts_json` (ou d'une
    liste de dimensions, `Dimension` ou leur forme JSON) : ses phrases, chacune avec la
    dimension et l'indicateur qu'elle cite, sa certitude et son statut."""
    if isinstance(resultat, Mapping):
        dims = [_dict(x) for x in resultat.get("dimensions") or []]
        cadre = _cadre(resultat)
    else:
        dims = [_dict(x) for x in resultat]
        cadre = None
    tetes: list[dict[str, Any]] = []
    autres: list[dict[str, Any]] = []
    mieux: list[dict[str, Any]] = []
    moins: list[dict[str, Any]] = []
    entre: list[dict[str, Any]] = []
    absentes: list[str] = []
    erreurs: list[dict[str, Any]] = []
    for d in dims:
        if "erreur" in d:
            erreurs.append({"sorte": "erreur", "dimension": d["cle"], "titre": d["cle"],
                            "texte": f"{d['cle']} : non calculée ({d['erreur']}).",
                            "statut": None, "certitude": None})
            continue
        inds = [i for i in d.get("indicateurs") or [] if _indices(i)]
        if not inds:
            absentes.append(d["cle"])
            continue
        tete = _phrase_tete(d, inds[0])
        if tete is None:
            absentes.append(d["cle"])
            continue
        tetes.append(tete)
        # L'arbitrage lit le premier indicateur qui a un sens (la tête, s'il en a un).
        ind_s = _premier_signe(d)
        if ind_s is not None:
            ph = tete if ind_s is inds[0] else _phrase_tete(d, ind_s)
            if ph and ph["sens"]:
                (mieux if ph["sens"] == "mieux" else moins).append(
                    {"dimension": d["cle"], "titre": d["titre"], "indicateur": ind_s["cle"],
                     "mots": _mots(ph, ind_s)})
        # Pour qui : le premier indicateur qui porte les dix déciles.
        for ind in inds:
            r = _phrase_deciles(d, ind)
            if r:
                autres.append(r[0])
                if r[1]:
                    entre.append(r[1])
                break
        else:
            g = _phrase_groupes(d, inds[0])
            if g:
                autres.append(g)
    rang = {c: i for i, c in enumerate(CERTITUDES)}
    tetes.sort(key=lambda p: (rang[p["certitude"]], -p["nettete"]))
    phrases: list[dict[str, Any]] = []
    if cadre:
        phrases.append(cadre)
    nets = [p for p in tetes if p["certitude"] == "probable"][:3]
    if nets:
        phrases.append({
            "sorte": "plus_net", "dimension": None,
            "dimensions": [p["dimension"] for p in nets], "statut": None,
            "certitude": "probable", "indicateur": None,
            "texte": "Ce qui bouge le plus nettement (la bande la plus loin de zéro, pas "
                     "le plus gros nombre : les unités ne se comparent pas) : "
                     + ", ".join(f"{_bas_casse(p['titre'])} ({_bas_casse(_lib(dims, p))})"
                                 for p in nets) + "."})
    elif tetes:
        phrases.append({
            "sorte": "plus_net", "dimension": None, "dimensions": [], "statut": None,
            "certitude": None, "indicateur": None,
            "texte": "Aucun nombre de tête n'a une bande qui reste d'un seul côté de zéro "
                     "dans une dimension sourcée : rien n'est dit « probablement »."})
    phrases += tetes
    phrases += autres
    arb = _phrase_arbitrages(mieux, moins, entre)
    if arb:
        phrases.append(arb)
    if absentes:
        titres = [_bas_casse(next(d["titre"] for d in dims if d.get("cle") == c))
                  for c in absentes]
        phrases.append({"sorte": "absent", "dimension": None, "dimensions": absentes,
                        "statut": None, "certitude": None, "indicateur": None,
                        "texte": "Pas de nombre ici pour " + ", ".join(titres)
                                 + " : leur fiche dit pourquoi (absent, pas nul)."})
    phrases += erreurs
    return {"regles": "D-650", "phrases": phrases, "avertissement": AVERTISSEMENT}


def _lib(dims: Sequence[Mapping[str, Any]], p: Mapping[str, Any]) -> str:
    d = next(x for x in dims if x.get("cle") == p["dimension"])
    return next(i["libelle"] for i in d["indicateurs"] if i["cle"] == p["indicateur"])


def _cadre(r: Mapping[str, Any]) -> dict[str, Any] | None:
    """Ce qui a été calculé, quand ce n'est pas le réglage par défaut : la chaîne des
    études à la place du jumeau complet, des années refusées."""
    morceaux = []
    if r.get("pourquoi_mode"):
        morceaux.append("Calculé par la chaîne des études, pas par le jumeau complet : "
                        + str(r["pourquoi_mode"]).split(" : la chaîne")[0] + ".")
    calculees = r.get("calculees") or []
    if r.get("refus") and calculees:
        morceaux.append(f"Le jumeau ne calcule que jusqu'en {calculees[-1]}.")
    if not morceaux:
        return None
    return {"sorte": "cadre", "texte": " ".join(morceaux), "dimension": None,
            "statut": None, "certitude": None, "indicateur": None}


def texte(s: Mapping[str, Any]) -> str:
    """Le paragraphe d'un seul tenant, tel que la page le lit."""
    return " ".join(p["texte"] for p in s["phrases"])
