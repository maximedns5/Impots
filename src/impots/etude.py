"""Une étude en trois réponses, par une commande (but 6, D-301).

    impots etude lancer <nom> --ou "..."   # les passes, l'une après l'autre
    impots etude ecrire <nom>              # la page, depuis les seuls rapports commités
    impots etude verifier <nom>            # la page commitée est-elle celle des rapports ?
    impots etude temoin <nom> --ou "..."   # la passe témoin, rejouée sur ce commit (D-335)
    impots etude avant <nom>               # ce que dit la série d'avant, figé (D-350)

Une étude est un fichier `etudes/<nom>.json` : les scénarios qu'elle chiffre, ménages ou
entreprises, chacun avec son volet et son sens ; le texte dont elle dit les refus ; la
D-entrée qui préenregistre ses passes. Pour chaque scénario, dans le cadre de D-289 : la
première année, que chiffre l'appel du simulateur de sa chaîne (le coût, les gagnants et
les perdants, la bande des comportements, l'éventail macro) ; le chemin annuel
(`impots predictif`), dans le cadre des études (`etudes/cadres/`, D-336), qui donne la
dette en fin de chemin à θ½ et aux coins de la boîte, dans les deux vues ; l'écart à l'évaluation
préalable quand le scénario a un cas noté.

PRÉENREGISTRÉE COMME TOUTE PASSE. Avant la première passe, le lanceur refuse un `src/`
modifié, une D-entrée de préenregistrement absente du commit, un commit qu'aucune branche
distante ne porte. Une série interrompue reprend : les rapports déjà là sont sautés,
s'ils sont sur ce commit ou sur un commit qu'une passe témoin y joint ; aucun n'est
écrasé. Une passe à la fois : un chemin annuel occupe 6 Go
(D-236), et chacune tourne dans son processus.

RIEN N'EST SAISI. Chaque nombre de la page se lit dans un rapport, un enregistrement ou un
triage, et `Etude.load` refuse les rapports qui ne sont pas ceux de l'étude : un autre
scénario, un autre cadre, un `src/` modifié, un lieu non dit, un deuxième commit sans
témoin.

UN CODE, OU DES COMMITS QUI NE CHANGENT AUCUN NOMBRE (D-335, D-336). Un rapport sur un
autre commit que le premier est lu quand la passe témoin, la plus courte de l'étude
rejouée sur ce commit, redonne son rapport à l'identique, hors date, commit et lieu. Le
témoin est écrit sous `temoins/<sha>.json`, et relu, pas cru : `load` le compare de
nouveau. La page dit chaque commit et le témoin qui le joint au premier.

EN MIROIR. Un scénario en miroir chiffre l'opposé de la mesure (D-298) : la page dit la
mesure, chaque réponse changée de signe. C'est exact pour ce qui est la différence de deux
passes, le coût et les déciles, gagnants et perdants échangés ; c'est vrai au premier ordre
pour la bande, l'éventail et la dette, calculés autour de l'état de départ.
"""

from __future__ import annotations

import dataclasses
import importlib.util
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFINITIONS = ROOT / "etudes"
SCENARIOS = ROOT / "scenarios"
#: The frames the studies read (D-336): their hypotheses, in a file of their own, apart from
#: the requests of the phase 10 explorations under `etude/`.
CADRES = DEFINITIONS / "cadres"
DECISIONS = "docs/DECISIONS.md"
FIELDS = {"nom", "titre", "texte", "preenregistrement", "cadre", "millesime_entreprises",
          "page", "rapports", "scenarios", "programme"}
#: The points of a measure's range the study of a programme prices (D-328): its bottom,
#: the candidate's value, its top.
POINTS = ("bas", "candidat", "haut")
#: Where a programme study keeps its ranges' reports, beside the two of its part.
PLAGES = "plages"
#: Where a study keeps its witness passes (D-335, D-336): one per commit after the first,
#: `temoins/<short sha>.json`.
TEMOINS = "temoins"
#: What the previous series said, frozen before the next one replaces its reports (D-350):
#: `<rapports>/avant/serie.json`. The page of the next series says what moved against it.
AVANT = Path("avant") / "serie.json"
#: What a witness does not compare: the day it ran, the code it named, where it ran. Every
#: other field of the report, its request and its reply, must be the same, value and type.
HORS_TEMOIN = ("computed", "commit", "dirty", "where")


class EtudeError(ValueError):
    """The study would not be what it says: its definition, its passes, or its reports."""


@dataclass(frozen=True)
class Volet:
    """A scenario the study prices: its name, the part of the measure it is, and whether
    it prices the measure's opposite (D-298)."""

    scenario: str
    titre: str | None = None
    miroir: bool = False


# --------------------------------------------------------------------------- #
# The first year, the annual path
# --------------------------------------------------------------------------- #


def _script(name: str) -> Any:
    """A repository script, loaded from `scripts/`: the annual command is built there, for
    the study of D-275 and for this one, from one function (D-237)."""
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


#: The two calls of a first year that prices households and firms together (D-328).
MIXTE = {"menages": "/population/simulate", "entreprises": "/entreprises/simulate"}


def first_year_payload(name: str, scenarios: Path = SCENARIOS,
                       mixte: bool = False) -> tuple[str, str, dict]:
    """(kind, endpoint, payload) of `name`'s first year: the firms' simulator for a firm
    reform alone, the households' otherwise, with behaviour and the loop asked. A reform of
    both is refused, unless `mixte`: a programme's priced part, whose first year is the two
    calls, side by side (D-328)."""
    from impots import scenarios as scenarios_module

    scenario = scenarios_module.load(name, scenarios)
    firm = scenario.firm_reform is not None and not scenario.firm_reform.is_empty()
    households = {"year": scenario.year,
                  "reform": scenario.reform.model_dump(exclude_none=True, mode="json"),
                  "behavioural": True, "macro": True}
    firms = ({"reform": scenario.firm_reform.model_dump(exclude_none=True, mode="json"),
              "year": scenario.year} if firm else None)
    if firm and not scenario.reform.is_empty():
        if not mixte:
            raise EtudeError(f"{name} : une réforme des ménages et des entreprises, que la "
                             f"première année chiffrerait sur deux appels.")
        return "mixte", " + ".join(MIXTE.values()), {"menages": households,
                                                     "entreprises": firms}
    if firm:
        return "entreprises", "/entreprises/simulate", firms
    return "menages", "/population/simulate", households


def first_year(name: str, *, where: str, scenarios: Path = SCENARIOS,
               mixte: bool = False) -> dict[str, Any]:
    """The first year's report: the simulator's reply, the code that priced it, where."""
    from fastapi.testclient import TestClient

    from impots.api.main import app
    from impots.predictif import recherche

    kind, endpoint, payload = first_year_payload(name, scenarios, mixte)
    commit, dirty = recherche.code_state(ROOT)
    client = TestClient(app)
    calls = ([(MIXTE[layer], payload[layer], layer) for layer in MIXTE] if kind == "mixte"
             else [(endpoint, payload, None)])
    replies = {}
    for url, body, layer in calls:
        reply = client.post(url, json=body)
        if reply.status_code != 200:
            raise EtudeError(f"{name} : {url} a rendu {reply.status_code} : "
                             f"{reply.text[:300]}")
        replies[layer] = reply.json()
    response = replies if kind == "mixte" else replies[None]
    return {"scenario": name, "kind": kind, "endpoint": endpoint, "request": payload,
            "response": response, "computed": date.today().isoformat(),
            "commit": commit, "dirty": dirty, "where": where}


def plage_request(cadre: str, programme: str, mesure: str, champ: str,
                  point: str) -> dict[str, Any]:
    """The predictive request of one point of a measure's range (D-328): the measure alone,
    `champ` at the range's bottom, the candidate's value or its top, in the study's frame,
    mechanical (no behaviour, no loop). Its first year is carried as a share of GDP: the
    fast convention of `POST /predictif/simulate`, said on the page."""
    from impots import programmes as pg

    p = pg.charger(programme)
    plages = p.plages()
    cle = f"{mesure}:{champ}"
    if cle not in plages or point not in POINTS:
        raise EtudeError(f"{programme} : pas de plage « {cle} », ou de point « {point} » "
                         f"({sorted(plages)}, {POINTS}).")
    _, plage = plages[cle]
    m = next(x for x in p.chiffrees() if x.id == mesure)
    valeur = {"bas": plage.min, "haut": plage.max,
              "candidat": pg._lire(m.chiffrage.reforme, champ)}[point]
    menages, entreprises = p.reformes({cle: valeur}, (mesure,))
    request = lire_cadre(cadre)
    return {"spending": request["spending"], "growth": request["growth"],
            "rate": request["rate"], "horizon": request["horizon"],
            "theta": request["theta"], "uprating": request["uprating"],
            "behavioural": False, "macro": False,
            "reform": menages.model_dump(exclude_none=True, mode="json") if menages else {},
            "firm_reform": (entreprises.model_dump(exclude_none=True, mode="json")
                            if entreprises else None)}


#: What a range's report keeps of the predictive reply: the first year's cost, the path.
PLAGE_REPONSE = ("mechanical_first_year_eur", "years", "delta", "population_view")


def plage(cadre: str, programme: str, mesure: str, champ: str, point: str, *,
          where: str) -> dict[str, Any]:
    """The report of one point of a measure's range: its request, what the reply says of
    the cost and the debt, the code that priced it, where."""
    from fastapi.testclient import TestClient

    from impots.api.main import app
    from impots.predictif import recherche

    request = plage_request(cadre, programme, mesure, champ, point)
    commit, dirty = recherche.code_state(ROOT)
    client = TestClient(app)
    absente = dette_absente(request)
    if absente is None:
        reply = client.post("/predictif/simulate", json=request)
        url = "/predictif/simulate"
    else:
        # A firm law that moves within the horizon (the CVAE): the carried path refuses
        # it (D-254). The cost of the year is the firms' simulator's; the debt is absent,
        # with that reason, and the study's annual path gives the candidate's (D-328).
        from impots.predictif.chaine import START_YEAR

        url = "/entreprises/simulate"
        reply = client.post(url, json={"reform": request["firm_reform"],
                                       "year": START_YEAR + 1})
    if reply.status_code != 200:
        raise EtudeError(f"{programme}/{mesure}/{champ}/{point} : {url} a rendu "
                         f"{reply.status_code} : {reply.text[:300]}")
    body = reply.json()
    response = ({k: body[k] for k in PLAGE_REPONSE} if absente is None else
                {"mechanical_first_year_eur": body["reform_cost"], "years": None,
                 "delta": None, "population_view": None})
    return {"programme": programme, "mesure": mesure, "champ": champ, "point": point,
            "request": request, "appel": url, "dette_absente": absente,
            "response": response, "computed": date.today().isoformat(), "commit": commit,
            "dirty": dirty, "where": where}


def dette_absente(request: dict[str, Any]) -> str | None:
    """Why the carried path cannot give a range point's debt, or None: a firm law that
    moves within its horizon (D-254), the one refusal the frame's request can meet."""
    from impots.api.schemas import _refuse_a_law_the_carry_cannot_see
    from impots.entreprises.reforms import FirmReformSpec

    firm = request.get("firm_reform")
    if not firm:
        return None
    try:
        _refuse_a_law_the_carry_cannot_see([FirmReformSpec.model_validate(firm)],
                                           request["horizon"])
    except ValueError as error:
        return str(error)
    return None


def plage_name(mesure: str, champ: str, point: str) -> str:
    return f"{mesure}__{champ}__{point}.json"


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True)


def ecarts(a: Any, b: Any, at: str = "") -> list[str]:
    """Where two reports part, each a path in them; none if they are the same, value and
    type (3 is not 3.0), outside `HORS_TEMOIN` at their top."""
    if not at and isinstance(a, dict) and isinstance(b, dict):
        a = {k: v for k, v in a.items() if k not in HORS_TEMOIN}
        b = {k: v for k, v in b.items() if k not in HORS_TEMOIN}
    if isinstance(a, dict) and isinstance(b, dict):
        out: list[str] = []
        for key in sorted(set(a) | set(b), key=str):
            if key not in a or key not in b:
                out.append(f"{at}/{key}")
            else:
                out += ecarts(a[key], b[key], f"{at}/{key}")
        return out
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return [f"{at} ({len(a)} éléments au lieu de {len(b)})"]
        return [x for i, (u, v) in enumerate(zip(a, b, strict=True))
                for x in ecarts(u, v, f"{at}[{i}]")]
    return [] if type(a) is type(b) and a == b else [at or "/"]


# --------------------------------------------------------------------------- #
# The reading
# --------------------------------------------------------------------------- #


def _points(value: float) -> str:
    return f"{value * 100:+.2f} pt".replace(".", ",")


def debt(path: dict[str, Any]) -> list[dict[str, Any]]:
    """Δb in the last year, at θ and at the box's corners, by persistence and view."""
    year = path["years"][-1]["year"]
    box = {p["persistence"]: p["every_year"]
           for p in (path.get("theta_box") or {}).get("paths", [])}
    if path.get("side_by_side"):
        drawn = [(p["persistence"], p["label"], p["years"][-1]) for p in path["side_by_side"]]
    else:
        drawn = [(path.get("persistence"), None, path["years"][-1])]
    rows = []
    for persistence, label, last in drawn:
        for view, key in (("vieillie", "delta_aged"), ("figee", "delta_frozen")):
            reading = (box.get(persistence) or {}).get(view)
            corners = [value for _, value in reading["corners"]] if reading else []
            if reading and abs(reading["theta"] - last[key]) > 1e-12:
                raise EtudeError(f"Δb {year} à θ ({last[key]:+.6f}) n'est pas celui de la "
                                 f"boîte ({reading['theta']:+.6f}), vue « {view} ».")
            rows.append({"persistence": persistence, "label": label, "view": view,
                         "theta": last[key], "corners": corners})
    return rows


#: The persistence the verdict reads, when a path carries it (D-336, decision 1): Mésange
#: read at its horizons. « éteint » and « tenu » stand beside it, as sensitivities.
LUE = "lue"


def lue(rows: list[dict[str, Any]]) -> bool:
    """Whether a path's rows carry the persistence « lue »: a report written since D-336.
    A report before it has « éteint » and « tenu » only, and reads as it always did."""
    return any(row.get("persistence") == LUE for row in rows)


def verdict_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The rows the verdict reads: those under « lue » when the path has it (D-336), every
    row of an older report otherwise."""
    return [row for row in rows if row["persistence"] == LUE] if lue(rows) else rows


def sensitivity_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The rows beside the verdict: the other persistences of a path that has « lue »."""
    return [row for row in rows if row["persistence"] != LUE] if lue(rows) else []


def verdict(rows: list[dict[str, Any]]) -> str:
    """« hausse » or « baisse » when Δb has one sign at θ and at every corner, in both
    views, under « lue » alone when the path has it (D-336), under each persistence of an
    older report; « dépend de θ » otherwise."""
    values = [v for row in verdict_rows(rows) for v in (row["theta"], *row["corners"])]
    if all(v > 0 for v in values):
        return "hausse"
    if all(v < 0 for v in values):
        return "baisse"
    return "dépend de θ"


def generation(entries: list[dict[str, Any]]) -> bool:
    """Whether a study's paths carry « lue » (D-336): all of them, or none, an older
    series. One page does not read half its paths under one verdict and half under the
    other."""
    read = {lue(entry["debt"]) for entry in entries}
    if len(read) > 1:
        raise EtudeError("les chemins de l'étude ne sont pas d'une même série : les uns "
                         "portent la persistance « lue », les autres non (D-336). La série "
                         "se relance entière.")
    return read == {True}


VIEWS = {"vieillie": "vieillie", "figee": "figée"}


def sobol_group(name: str) -> str:
    """A Sobol group of the Monte-Carlo as a reader reads it: the multiplier, or the rows
    of one article, the store's file they live in (`montecarlo`, D-336)."""
    from impots.predictif.rejouer import MACRO_ROW

    return "le multiplicateur" if name == MACRO_ROW else f"les lignes de `{name}.yaml`"


VERDICTS = {
    "hausse": "elle **augmente la dette** en {year}, à θ½ comme à chaque coin de la boîte, "
              "dans les deux vues",
    "baisse": "elle **baisse la dette** en {year}, à θ½ comme à chaque coin de la boîte, "
              "dans les deux vues",
    "dépend de θ": "son effet sur la dette en {year} **dépend de θ** : son signe change d'un "
                   "coin de la boîte, ou d'une vue, à l'autre",
}


#: The verdict of a series of but 16 (D-345, D-349), read on the Monte-Carlo: the share
#: of the draws where the debt rises, vue vieillie, against `montecarlo.SEUIL_VERDICT`.
VERDICTS_MC = {
    "hausse": "elle **augmente la dette** en {year} dans au moins {haut} des tirages, vue "
              "vieillie",
    "baisse": "elle **baisse la dette** en {year} dans au moins {haut} des tirages, vue "
              "vieillie",
    "dépend": "son effet sur la dette en {year} **dépend des hypothèses** : moins de {haut} "
              "des tirages s'accordent sur son signe, vue vieillie",
}
#: The instruments whose cost is gross of the corporate tax they move (D-349).
EMPLOYEURS = ("cotisations_employeurs", "cotisations_employeurs_ciblees")


def lectures(entries: list[dict[str, Any]]) -> bool:
    """Whether a study's paths carry the readings of D-349 (but 16): all of them, or none,
    an older series; one page does not read half its paths under the Monte-Carlo verdict."""
    read = {entry["path"].get("lectures") is not None for entry in entries}
    if len(read) > 1:
        raise EtudeError("les chemins de l'étude ne sont pas d'une même série : les uns "
                         "portent les lectures de D-349, les autres non. La série se "
                         "relance entière.")
    return read == {True}


def verdict_mc(entry: dict[str, Any], monte: dict[str, Any] | None = None) -> str:
    """The Monte-Carlo verdict of a path (D-345), the measure's in mirror: its rise is the
    scenario's fall, to the first order as the rest (D-298)."""
    from impots.predictif import montecarlo

    reading = montecarlo.verdict(monte if monte is not None else entry["path"]["monte_carlo"])
    if entry["sign"] == -1:
        reading = {"hausse": "baisse", "baisse": "hausse"}.get(reading, reading)
    return reading


def causes(entry: dict[str, Any]) -> list[str]:
    """The corrections of but 16 that touch an entry (D-350): the public sector for any
    household pass, the corporate tax for a firm reform of the CVAE or the C3S, the VAT
    coefficient when the loop carries VAT; the verdict's rule for every one."""
    out = []
    if entry["kind"] != "entreprises":
        out.append("le secteur public câblé (D-346)")
    firm = entry["scenario"].firm_reform
    fields = firm.model_dump(exclude_none=True) if firm is not None else {}
    if any("cvae" in k or "c3s" in k for k in fields):
        out.append("la CVAE et la C3S déduites de l'IS (D-347)")
    macro = (entry["path"].get("rejeu") or {}).get("macro") or {}
    if "tva" in (macro.get("instruments") or {}):
        out.append("la TVA des ménages au point net (D-348)")
    out.append("le verdict lu sur le Monte-Carlo (D-345)")
    return out


def refusal(raison: str) -> tuple[str, str]:
    """(case, first sentence) of a triage reason, « scope. Formalité reconduite… » : the
    case it falls in, then why, in its first sentence."""
    kind, _, rest = raison.partition(". ")
    if kind not in ("scope", "structure", "data"):
        raise EtudeError(f"une raison de refus sans sa case : « {raison[:60]} »")
    return kind, rest.split(" ; ")[0].split(". ")[0].rstrip(".") + "."


def _mirrored(response: Any, sign: int) -> Any:
    """The households' reply as the measure reads it: each decile's delta turned over, its
    winners and losers exchanged. Exact, a household's delta being one difference."""
    if sign == 1 or not getattr(response, "deciles", None):
        return response
    return response.model_copy(update={"deciles": [
        row.model_copy(update={"mean_delta": -row.mean_delta,
                               "mean_baseline": row.mean_reform,
                               "mean_reform": row.mean_baseline,
                               "share_winners": row.share_losers,
                               "share_losers": row.share_winners})
        for row in response.deciles]})


# --------------------------------------------------------------------------- #
# The numbers of a page, each with what it rests on (D-304)
# --------------------------------------------------------------------------- #

#: What a number on a page rests on. A number the tool computes says its layer
#: (`README.md`, the five layers); a number it takes from elsewhere says where from.
ETAGES = {
    "L1": "population synthétique calée sur des totaux publiés : bonne sur les agrégats, "
          "faible dans les queues",
    "L2": "simulation mécanique : qui paie quoi le premier jour, personne ne change de "
          "comportement ; à 1 à 3 % près sur les agrégats",
    "L3": "réponse des comportements : une fourchette sur des élasticités publiées, "
          "jamais un point",
    "L4": "ordre de grandeur macroéconomique, en éventail : large par construction, et "
          "souvent indisponible",
    "publié": "le chiffrage du gouvernement, l'évaluation préalable publiée avec le texte",
    "texte": "ce que le texte de loi, ou son triage, compte",
    "hypothèse": "ce que l'étude suppose : son scénario, son cadre",
    "déclaré": "une tolérance déclarée avant le chiffrage",
    "programme": "ce que le programme du candidat énonce, relevé et sourcé dans "
                 "`programmes/`",
    "annoncé": "un montant que le candidat annonce lui-même, que le moteur ne vérifie pas "
               "et n'additionne jamais à son chiffrage (D-319)",
}
_TOKEN = re.compile("\ue000(\\d+)\ue001")


@dataclass(frozen=True)
class Nombre:
    texte: str
    etage: str
    #: A gap in the debt: conditional on the named frame and on θ.
    conditionnel: bool = False


class Nombres:
    """The numbers of one page. Each is written in the page's lines as a token; the
    Markdown resolves it to its text, the site to its text and its étage."""

    def __init__(self) -> None:
        self.items: list[Nombre] = []

    def __call__(self, texte: Any, etage: str, *, conditionnel: bool = False) -> str:
        if etage not in ETAGES:
            raise EtudeError(f"un nombre sans étage connu : « {texte} » ({etage})")
        self.items.append(Nombre(str(texte), etage, conditionnel))
        return f"\ue000{len(self.items) - 1}\ue001"

    def resolve(self, line: str, form: Any = None) -> str:
        """`line` with each token replaced by `form(nombre)`, its text by default."""
        return _TOKEN.sub(lambda m: (form or (lambda x: x.texte))(self.items[int(m[1])]),
                          line)


#: An amount on a page: euros, points or a share. None may stand without its étage.
AMOUNT = re.compile(r"\d(?:[\d\u202f\u00a0 ]*\d)?(?:,\d+)?\s?(?:Md€|M€|k€|€|pt|%)")


def amounts(text: str, etage: str, n: Nombres) -> str:
    """`text` with each amount it quotes made a number of `etage`: an article's title or a
    triage's reason quotes the law's amounts, and says where they come from."""
    return AMOUNT.sub(lambda m: n(m[0], etage), text)


def debt_etage(path: dict[str, Any]) -> str:
    """The highest layer a path's debt rests on: L4 when the macro loop entered it, L3
    when a behavioural channel did, L2 when it is the mechanical path alone (D-304)."""
    from impots.predictif.chaine import MACRO_CHANNELS
    from impots.predictif.theta import MACRO_ROW

    closed = path.get("closed") or {}
    if not any(channel in closed for channel in MACRO_CHANNELS):
        return "L4"
    rows = (path.get("theta_box") or {}).get("rows") or []
    return "L3" if any(row != MACRO_ROW for row in rows) else "L2"


def _deciles(w: Any, n: Nombres, response: Any) -> None:
    """The fiche's decile table (`fiche._deciles`), each number with its étage: the
    households and their niveau de vie are the population's, the rest the simulation's."""
    from impots import fiche

    rows = getattr(response, "deciles", None) or []
    if not rows:
        w("*Table par décile non disponible pour cette exécution.*")
        w("")
        return
    w("| décile | ménages | niveau de vie moyen | delta moyen | gagnants | perdants |")
    w("|---|---|---|---|---|---|")
    for r in rows:
        w(f"| {r.decile} | {n(fiche._num(r.n_households), 'L1')} | "
          f"{n(fiche._num(r.mean_niveau_de_vie) + ' €', 'L1')} | "
          f"{n(fiche._eur(r.mean_delta), 'L2')} | {n(fiche._pct(r.share_winners), 'L2')} | "
          f"{n(fiche._pct(r.share_losers), 'L2')} |")
    w("")
    w("Les déciles sont ceux du niveau de vie de la population simulée. Toute structure")
    w("plus fine qu'un décile est un artefact de l'imputation, pas un résultat.")
    w("")


# --------------------------------------------------------------------------- #
# The texts whose refusals a study says
# --------------------------------------------------------------------------- #


def _article_of(articles: Any, scenario: str) -> Any:
    """The article whose `reforme` names `scenario`'s file, one or several of them."""
    for article in articles:
        stems = {Path(p.strip()).stem for p in (article.reforme or "").split(",") if p.strip()}
        if scenario in stems:
            return article
    raise EtudeError(f"{scenario} : aucun article du texte ne le nomme.")


class _PLF2027:
    """Le PLF 2027 : ses articles fiscaux, chaque scénario sous l'article qu'il chiffre, les
    autres avec leur case."""

    def article(self, volet: Volet) -> Any:
        from impots import plf_coverage

        return _article_of(plf_coverage.ARTICLES_2027, volet.scenario)

    def chapeau(self, entries: list[dict[str, Any]], last: int, n: Nombres) -> str:
        from impots import plf_coverage

        every = plf_coverage.ARTICLES_2027
        return (f"Le projet de loi de finances pour 2027 porte {n(len(every), 'texte')} "
                f"articles fiscaux. Cet outil en chiffre {n(len(entries), 'texte')}, et dit "
                f"pourquoi il ne chiffre pas les autres. Pour chacun des "
                f"{n(len(entries), 'texte')}, trois réponses : ce qu'il coûte et "
                f"qui y gagne ; ce qu'il coûte une fois les comportements et l'économie pris "
                f"en compte ; ce qu'il fait à la dette en {last}. Puis l'écart au chiffrage du "
                f"gouvernement, l'évaluation préalable publiée avec le texte.")

    def label(self, entry: dict[str, Any]) -> str:
        return f"art. {entry['article'].numero}"

    def heading(self, entry: dict[str, Any], n: Nombres) -> str:
        article = entry["article"]
        return f"## Art. {article.numero} — {amounts(article.intitule, 'texte', n)}"

    def first_year(self, year: int) -> str:
        return f"la première année (revenus {year})"

    def refusals(self, w: Any, entries: list[dict[str, Any]], n: Nombres) -> None:
        from impots import plf_coverage

        refused = [a for a in plf_coverage.ARTICLES_2027 if a.bucket != "priceable_now"]
        w(f"## Les {n(len(refused), 'texte')} autres articles")
        w("")
        w("Un article refusé n'est pas un article à zéro. Le refus est pris sur le texte, "
          "avant tout chiffrage, et sa raison est dite : hors du périmètre (`scope`), hors de "
          "la structure du modèle (`structure`), ou hors de ses données (`data`).")
        w("")
        w("| art. | intitulé | case | pourquoi |")
        w("|---|---|---|---|")
        for a in refused:
            kind, why = refusal(a.raison)
            w(f"| {a.numero} | {amounts(a.intitule, 'texte', n)} | `{kind}` | "
              f"{amounts(why, 'texte', n)} |")
        w("")


class _PLFSS2027:
    """Le PLFSS 2027, dont aucun article n'est chiffrable (D-298) : la mesure de prestations
    que l'outil chiffre est l'art. 74 du PLF 2027, en volets ; les articles du PLFSS sont
    dits avec leur case et la porte qui les ouvrirait."""

    def article(self, volet: Volet) -> Any:
        from impots import plf_coverage

        if not volet.titre:
            raise EtudeError(f"{volet.scenario} : un volet sans titre, que la page ne saurait "
                             f"pas nommer.")
        return _article_of((plf_coverage.ARTICLE_74_2027,), volet.scenario)

    def chapeau(self, entries: list[dict[str, Any]], last: int, n: Nombres) -> str:
        from impots import plf_coverage

        every = plf_coverage.ARTICLES_PLFSS_2027
        if any(a.bucket == "priceable_now" for a in every):
            raise EtudeError("un article du PLFSS est chiffrable : la page le dirait refusé.")
        numeros = sorted({e["article"].numero for e in entries})
        art = ", ".join(map(str, numeros))
        return (f"Le projet de loi de financement de la sécurité sociale pour 2027 porte "
                f"{n(len(every), 'texte')} articles. Cet outil n'en chiffre aucun, et dit pour "
                f"chacun "
                f"pourquoi, avec la porte qui l'ouvrirait. La mesure de prestations que "
                f"l'automne lui donne à chiffrer est dans le projet de loi de finances : "
                f"l'art. {art}, en {n(len(entries), 'texte')} volets. Pour chacun, trois "
                f"réponses : ce "
                f"qu'il coûte et qui y gagne ; ce qu'il coûte une fois les comportements et "
                f"l'économie pris en compte ; ce qu'il fait à la dette en {last}. Puis l'écart "
                f"au chiffrage du gouvernement, l'évaluation préalable publiée avec le texte.")

    def label(self, entry: dict[str, Any]) -> str:
        return f"art. {entry['article'].numero} du PLF, {entry['volet'].titre}"

    def heading(self, entry: dict[str, Any], n: Nombres) -> str:
        return f"## Art. {entry['article'].numero} du PLF 2027 — {entry['volet'].titre}"

    def first_year(self, year: int) -> str:
        return f"la première année, chiffrée en {year}"

    def refusals(self, w: Any, entries: list[dict[str, Any]], n: Nombres) -> None:
        from impots import plf_coverage

        every = plf_coverage.ARTICLES_PLFSS_2027
        w(f"## Les {n(len(every), 'texte')} articles du PLFSS")
        w("")
        w("Un article refusé n'est pas un article à zéro. Le refus est pris sur le texte, "
          "avant tout chiffrage, et sa raison est dite : hors du périmètre (`scope`), hors de "
          "la structure du modèle (`structure`), ou hors de ses données (`data`). La porte "
          "est ce que l'outil devrait savoir faire pour le chiffrer.")
        w("")
        w("| art. | intitulé | case | porte | pourquoi |")
        w("|---|---|---|---|---|")
        for a in every:
            kind, why = refusal(a.raison)
            w(f"| {a.numero} | {amounts(a.intitule, 'texte', n)} | `{kind}` | `{a.porte}` | "
              f"{amounts(why, 'texte', n)} |")
        w("")
        w("Les portes, de celle qui ouvrirait le plus d'articles à celle qui en ouvrirait le "
          "moins :")
        w("")
        for porte, numeros in plf_coverage.portes_plfss_2027():
            many = "s" if len(numeros) > 1 else ""
            w(f"* `{porte}`, {n(len(numeros), 'texte')} article{many} — "
              f"{plf_coverage.OUVERTURES_PLFSS_2027[porte]}.")
        w("")


#: Ce que la page d'un programme dit en tête, à côté de sa couverture (D-319) : la page
#: renvoie à ses sections, là où la commande renvoie à ses clés.
AVERTISSEMENT_PROGRAMME = (
    "La dette porte sur la seule part du programme que l'outil chiffre, pas sur le "
    "programme : les mesures refusées, dites plus bas une à une avec leur porte, n'y sont "
    "pas, et un programme chiffré en partie peut paraître creuser ou baisser la dette pour "
    "une raison qui tient à l'outil (D-319).")


class _Programme:
    """Un programme présidentiel (D-319, D-328) : l'étude porte sur sa part chiffrée, et dit
    à côté de chaque nombre la couverture et chaque refus avec sa porte."""

    colonne = "programme"
    unite = "mesure"

    def __init__(self, study: Etude) -> None:
        from impots import programmes as pg

        self.study = study
        self.programme = pg.charger(study.programme)

    def article(self, volet: Volet) -> Any:
        return self.programme

    def chapeau(self, entries: list[dict[str, Any]], last: int, n: Nombres) -> str:
        p, c = self.programme, self.programme.couverture()
        together = (f"ces {n(c['chiffrees'], 'texte')} mesures ensemble"
                    if c["chiffrees"] > 1 else "cette seule mesure")
        part = f"{c['part_des_parametrees'] * 100:.0f} %"
        return (f"{p.candidat}, {p.parti}, a déclaré sa candidature à l'élection "
                f"présidentielle de 2027. Son programme, relevé le "
                f"{p.releve.strftime('%d/%m/%Y')}, porte "
                f"{n(c['mesures'], 'programme')} mesures, dont "
                f"{n(c['parametrees'], 'programme')} énoncent un paramètre. Cet outil en "
                f"chiffre {n(c['chiffrees'], 'texte')}, soit {n(part, 'texte')} des mesures "
                f"paramétrées, et dit pourquoi il ne chiffre pas les autres. Pour la part "
                f"chiffrée, {together}, trois réponses : ce qu'elle coûte et qui y gagne ; "
                f"ce qu'elle coûte une fois les comportements et l'économie pris en compte ; "
                f"ce qu'elle fait à la dette en {last}. **{AVERTISSEMENT_PROGRAMME}**")

    def label(self, entry: dict[str, Any]) -> str:
        return "la part chiffrée"

    def heading(self, entry: dict[str, Any], n: Nombres) -> str:
        return "## La part chiffrée"

    def first_year(self, year: int) -> str:
        return f"la première année ({year})"

    # -- what the law texts do not have ------------------------------------------ #

    def official(self, w: Any, n: Nombres, entry: dict[str, Any]) -> None:
        """Each priced measure's own case, preregistered before the judge (D-321, D-326)."""
        from impots import fiche, preregistration

        w("La part chiffrée n'est pas un cas enregistré : ses mesures le sont, une à une, "
          "avant que le juge ne publie. Le juge est le chiffrage des programmes de "
          "l'Institut Montaigne, attendu au premier trimestre 2027.")
        w("")
        for m in self.programme.chiffrees():
            name = f"pres2027_{self.programme.slug}_{m.id}"
            case = preregistration.load(name)
            tol = case.tolerance
            state = ("le juge n'a pas publié" if case.comparator is None else
                     f"noté : {preregistration.grade(case).verdict}")
            w(f"* `{name}`, enregistré le {case.pre_registered[:10]} : "
              f"{n(fiche._eur(case.mechanical_eur), 'L2')} en {case_year(case)}, tolérance "
              f"de {n(f'{tol.relative * 100:.0f} %', 'déclaré')} ou "
              f"{n(fiche._width(tol.absolute_eur), 'déclaré')} ; {state}.")
        w("")

    def refusals(self, w: Any, entries: list[dict[str, Any]], n: Nombres) -> None:
        self._plages(w, n, entries[0]["plages"])
        self._mesures(w, n)
        self._annonce(w, n)

    def sources(self, w: Any, where: str) -> None:
        count = len(self.study.points())
        w(f"* `{where}/{PLAGES}/`, les {count} points des plages")

    def _plages(self, w: Any, n: Nombres, reports: list[dict[str, Any]]) -> None:
        from impots import fiche
        from impots import programmes as pg

        w("## Ce que bouge chaque paramètre")
        w("")
        w("Chaque mesure chiffrée a une plage : le lecteur peut la régler, du bas au haut. "
          "Trois points la parcourent, le bas, la valeur du candidat et le haut. Chaque point "
          "est la mesure seule, mécanique (personne ne change de comportement), sur la "
          "population vieillie jusqu'en 2026 ; sa dette reporte la première année en part de "
          "PIB jusqu'en 2035. Elle ne se compare donc pas à celle de la part chiffrée, plus "
          "haut, que le chemin annuel chiffre année par année avec les comportements et la "
          "boucle.")
        w("")
        by_key = {(r["mesure"], r["champ"], r["point"]): r for r in reports}
        for m in self.programme.chiffrees():
            w(f"### {amounts(m.libelle, 'programme', n)}")
            w("")
            w(f"*Le candidat : {amounts(m.parametre, 'programme', n)}.*")
            w("")
            for plage in m.chiffrage.plages:
                w(f"| `{plage.champ}` | valeur | coût {START_PLUS_ONE} | dette en {LAST_YEAR} |")
                w("|---|---|---|---|")
                absente = None
                for point in POINTS:
                    r = by_key[(m.id, plage.champ, point)]
                    valeur = (pg._lire(m.chiffrage.reforme, plage.champ) if point == "candidat"
                              else plage.min if point == "bas" else plage.max)
                    etage = "programme" if point == "candidat" else "hypothèse"
                    cost = n(fiche._eur(r["response"]["mechanical_first_year_eur"]), "L2")
                    if r["dette_absente"] is None:
                        debt = n(_points(r["response"]["delta"][-1]), "L2", conditionnel=True)
                    else:
                        debt, absente = "absente", r["dette_absente"]
                    w(f"| {POINT_LABELS[point]} | {n(valeur_lue(plage.champ, valeur), etage)} "
                      f"| {cost} | {debt} |")
                w("")
                if absente is not None:
                    raison = absente.split(" : ")[0]
                    w(f"**Dette : absente, et la raison est donnée.** "
                      f"{amounts(raison[:1].upper() + raison[1:], 'texte', n)} : le chemin "
                      f"rapide la "
                      f"tiendrait à son droit de 2026 jusqu'en {LAST_YEAR}. La dette de la "
                      f"valeur du candidat est celle de la part chiffrée, que le chemin annuel "
                      f"chiffre chaque année sous son droit (D-254).")
                    w("")

    def _mesures(self, w: Any, n: Nombres) -> None:
        from impots import programmes as pg

        p, c = self.programme, self.programme.couverture()
        w("## Le programme, mesure par mesure")
        w("")
        w("Une mesure est chiffrée, refusée ou vague. Une mesure refusée n'est pas une mesure "
          "à zéro : la porte dit ce que l'outil devrait savoir faire pour la chiffrer. Une "
          "mesure vague n'énonce ni taux ni montant.")
        w("")
        w("| mesure | ce que dit le candidat | sort | pourquoi |")
        w("|---|---|---|---|")
        for m in p.mesures:
            if m.chiffrage is not None:
                sort, why = "chiffrée", amounts(m.chiffrage.note, "hypothèse", n)
            else:
                sort = ("vague" if m.refus.porte == "vague"
                        else f"refusée, porte `{m.refus.porte}`")
                why = amounts(m.refus.raison, "texte", n)
            w(f"| {amounts(m.libelle, 'programme', n)} | "
              f"{amounts(m.parametre, 'programme', n)} | {sort} | {why} |")
        w("")
        portes = {k: v for k, v in c["refus_par_porte"].items() if k != "vague"}
        if portes:
            w("Les portes, de celle qui ouvrirait le plus de mesures à celle qui en "
              "ouvrirait le moins :")
            w("")
            for porte, count in sorted(portes.items(), key=lambda kv: (-kv[1], kv[0])):
                w(f"* `{porte}`, {n(count, 'texte')} — {amounts(pg.PORTES[porte], 'texte', n)}.")
            w("")

    def _annonce(self, w: Any, n: Nombres) -> None:
        from impots import fiche

        w("## Ce que le candidat annonce, à part")
        w("")
        couches = [self.programme.couche_declaree(rho) for rho in (0.0, 0.5, 1.0)]
        if not couches[-1]["mesures"]:
            w("Le candidat n'annonce, pour aucune de ses mesures, un montant que le relevé ait "
              "trouvé.")
            w("")
            return
        w(f"Le candidat annonce lui-même un montant pour "
          f"{n(len(couches[-1]['mesures']), 'programme')} de ses mesures. Ces montants ne "
          f"sont pas vérifiés et ne s'ajoutent jamais au chiffrage de l'outil : ρ dit la part "
          f"qui s'en réaliserait, de rien à tout. Le solde est l'effet annoncé sur les comptes "
          f"publics, positif quand ils s'améliorent.")
        w("")
        w("| ρ | solde annoncé |")
        w("|---|---|")
        for couche in couches:
            rho = f"{couche['rho']:g}".replace(".", ",")
            w(f"| {n(rho, 'hypothèse')} | {n(fiche._eur(couche['solde_eur']), 'annoncé')} |")
        w("")
        w(f"*{couches[-1]['statut']}*")
        w("")


START_PLUS_ONE = 2026
LAST_YEAR = 2035
POINT_LABELS = {"bas": "le bas", "candidat": "le candidat", "haut": "le haut"}


def case_year(case: Any) -> int:
    """The year a case priced: its scenario's, or, for a firm case registered on a reform
    file, the year its registration names."""
    from impots import scenarios as scenarios_module

    if case.scenario is not None:
        return scenarios_module.load(case.scenario).year
    return int(case.reform["annee"])


def valeur_lue(champ: str, valeur: float) -> str:
    """A knob's value as a reader reads it: a rate in per cent, an excise in its unit, a
    ceiling in euros, a factor as it is."""
    leaf = champ.split(".")[-1]
    if champ.startswith("accise_electricite") or champ.startswith("accise_gaz"):
        text = f"{valeur:g} €/MWh"
    elif champ.startswith("accise_"):
        text = f"{valeur:g} €/L"
    elif "plafond" in champ and valeur >= 100:
        text = f"{valeur:,.0f} €".replace(",", "\u202f")
    elif (champ.startswith(("tva", "csg")) or leaf in ("rate", "taux")
          or champ.endswith("_taux")):
        text = f"{valeur * 100:g} %"
    else:
        text = f"{valeur:g}"
    return text.replace(".", ",")


TEXTES: dict[str, Any] = {"plf2027": _PLF2027(), "plfss2027": _PLFSS2027(),
                          "programme": _Programme}


# --------------------------------------------------------------------------- #
# A study
# --------------------------------------------------------------------------- #


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


#: What a study's frame says (D-336), each key read by the range points, the page and the
#: annual command, as a predictive request carries it.
CADRE_LU = ("spending", "growth", "rate", "horizon", "uprating", "theta", "behavioural",
            "macro")
#: What a frame will carry, and no pass reads yet: the market rate of the added debt
#: (D-336, decision 3; the PLF 2027's text gives none). A frame that says it is refused
#: until every pass reads it, rather than priced as if it did not.
CADRE_A_VENIR = ("taux",)
#: The persistence the verdict reads (D-336, decision 1), the one value a frame may say.
#: The annual command draws it beside « éteint » and « tenu », the sensitivities.
CADRE_PERSISTANCES = (LUE,)


def lire_cadre(nom: str, directory: Path | None = None) -> dict[str, Any]:
    """The frame `nom` of the studies, `etudes/cadres/<nom>.json`: every key the passes
    read, and nothing they would leave unread."""
    path = (directory or CADRES) / f"{nom}.json"
    if not path.exists():
        raise EtudeError(f"{_relative(path)} n'existe pas : aucun cadre « {nom} ».")
    raw = _read(path)
    a_venir = sorted(set(CADRE_A_VENIR) & set(raw))
    if a_venir:
        raise EtudeError(f"le cadre « {nom} » porte {a_venir}, qu'aucune passe ne lit "
                         f"encore (D-336) : il serait chiffré sans eux.")
    if "persistance" in raw and raw["persistance"] not in CADRE_PERSISTANCES:
        raise EtudeError(f"le cadre « {nom} » lit la persistance « {raw['persistance']} » ; "
                         f"le verdict ne lit que {list(CADRE_PERSISTANCES)} (D-336), les "
                         f"autres sont des sensibilités.")
    unknown = set(raw) - set(CADRE_LU) - {"titre", "persistance"}
    missing = set(CADRE_LU) - set(raw)
    if unknown or missing:
        raise EtudeError(f"le cadre « {nom} » : champs inconnus {sorted(unknown)}, "
                         f"manquants {sorted(missing)}.")
    return raw


def difference(committed: str, built: str) -> str | None:
    """Where two texts first part, line and words around it, or None if they are one."""
    if committed == built:
        return None
    a, b = committed.splitlines(), built.splitlines()
    for number, (x, y) in enumerate(zip(a, b, strict=False), start=1):
        if x != y:
            at = next(i for i, (u, v) in enumerate(zip(x, y, strict=False)) if u != v) \
                if any(u != v for u, v in zip(x, y, strict=False)) else min(len(x), len(y))
            start = max(at - 40, 0)
            return (f"ligne {number} : « …{x[start:at + 40]}… » au lieu de "
                    f"« …{y[start:at + 40]}… »")
    return f"{len(a)} lignes au lieu de {len(b)}"


def _relative(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


@dataclass(frozen=True)
class Etude:
    nom: str
    titre: str
    texte: str
    preenregistrement: str
    volets: tuple[Volet, ...]
    cadre: str
    millesime_entreprises: str
    page: Path
    rapports: Path
    scenarios: Path = SCENARIOS
    #: The programme a study of a presidential programme reads (D-328), or None.
    programme: str | None = None

    @property
    def noms(self) -> tuple[str, ...]:
        return tuple(v.scenario for v in self.volets)

    @property
    def mixte(self) -> bool:
        """Whether a scenario may price households and firms together: a programme's
        priced part, whose first year is two calls (D-328)."""
        return self.programme is not None

    def texte_lu(self) -> Any:
        """What the page says of its text: a law's, shared, or this study's programme."""
        texte = TEXTES[self.texte]
        return texte(self) if isinstance(texte, type) else texte

    def points(self) -> list[tuple[str, str, str]]:
        """(measure, field, point) of every range point the study prices, in order."""
        if self.programme is None:
            return []
        from impots import programmes as pg

        p = pg.charger(self.programme)
        return [(m.id, plage.champ, point) for m in p.chiffrees()
                for plage in m.chiffrage.plages for point in POINTS]

    # -- the passes -------------------------------------------------------------- #

    def annual_argv(self, name: str, *, where: str) -> list[str]:
        """`impots predictif` for `name`: the annual command of the frame's request, with
        this scenario, this directory and this place."""
        annual = _script("etude_annuelle")
        lire_cadre(self.cadre)
        command = annual.argv(self.cadre, where=where, requests=CADRES,
                              scenarios=self.scenarios, out=self.rapports)
        if command[1] != annual.name(self.cadre):
            raise EtudeError(f"la commande de l'étude ne nomme pas son scénario en "
                             f"deuxième : {command[:3]}")
        return [command[0], name, *command[2:]]

    def passes(self, where: str) -> list[tuple[str, list[str]]]:
        """(report, command): the first years, the range points of a programme, then the
        annual paths, the longest, in the study's order."""
        cli = ["-m", "impots.population.cli"]
        return ([(f"premiere_annee_{name}.json",
                  [*cli, "etude", "premiere", self.nom, name, "--ou", where])
                 for name in self.noms]
                + [(f"{PLAGES}/{plage_name(mesure, champ, point)}",
                    [*cli, "etude", "plage", self.nom, mesure, champ, point, "--ou", where])
                   for mesure, champ, point in self.points()]
                + [(f"predictif_{name}.json", [*cli, *self.annual_argv(name, where=where)])
                   for name in self.noms])

    def preregistered(self) -> str | None:
        """Why the passes may not run on this commit, or None: the entry that preregisters
        them is in it, and a remote branch carries it."""
        try:
            decisions = _git("show", f"HEAD:{DECISIONS}")
            remote = _git("branch", "-r", "--contains", "HEAD")
        except (OSError, subprocess.CalledProcessError) as error:
            return f"git ne dit pas l'état du commit : {error}"
        heading = f"## {self.preenregistrement} "
        if not any(line.startswith(heading) for line in decisions.splitlines()):
            return (f"{self.preenregistrement} n'est pas dans {DECISIONS} au commit : les "
                    f"passes ne tournent qu'après l'entrée qui les préenregistre.")
        if not remote.strip():
            return ("aucune branche distante ne porte le commit : une passe tourne sur un "
                    "préenregistrement poussé.")
        return None

    def _env(self) -> dict[str, str]:
        # The first years call the simulator in their own process, closed without a key
        # since D-295: a pass is local, and opens it for itself.
        return {**os.environ, "PYTHONPATH": str(ROOT / "src"),
                "IMPOTS_FIRM_VINTAGE": self.millesime_entreprises, "IMPOTS_AUTH": "aucune"}

    def resume(self, commit: str, passes: list[str]) -> str | None:
        """Why the reports already there may not stand beside the passes still to run on
        `commit`, or None. A report stands when it is on `commit`, or on a commit a witness
        joins to it (D-335): a series resumes, and no report is written over."""
        # The frozen previous series (D-349) is read by the page, not a pass of this one.
        there = ({str(p.relative_to(self.rapports)) for p in self.rapports.rglob("*.json")
                  if p.parent.name != TEMOINS and p != self.rapports / AVANT}
                 if self.rapports.exists() else set())
        if there - set(passes):
            return (f"{self.rapports} porte {sorted(there - set(passes))}, qui n'est pas une "
                    f"passe de l'étude : un rapport n'est pas écrasé en silence.")
        if not there:
            return None
        joined = self.joined()
        for name in sorted(there):
            report = _read(self.rapports / name)
            on = report.get("commit")
            if not on or report.get("dirty") is not False:
                return (f"{name} ne nomme pas un commit dont il a chiffré le code : un rapport "
                        f"n'est pas écrasé en silence.")
            if on != commit and not {on, commit} <= joined:
                return (f"{name} est sur le commit `{on[:7]}`, et la série reprendrait sur "
                        f"`{commit[:7]}`, qu'aucune passe témoin ne joint à lui : un rapport "
                        f"n'est pas écrasé en silence. Sur ce commit, `impots etude temoin "
                        f"{self.nom} --ou \"…\"` rejoue la passe témoin (D-335).")
        return None

    def launch(self, where: str) -> int:
        from impots.predictif import recherche

        commit, dirty = recherche.code_state(ROOT)
        if dirty:
            print("src/ a des modifications non commitées : les rapports nommeraient un "
                  "commit dont ils n'ont pas chiffré le code. Commiter d'abord.",
                  file=sys.stderr)
            return 1
        why = self.preregistered()
        if why:
            print(why, file=sys.stderr)
            return 1
        passes = self.passes(where)
        why = self.resume(commit, [report for report, _ in passes])
        if why:
            print(why, file=sys.stderr)
            return 1
        env = self._env()
        for report, command in passes:
            if (self.rapports / report).exists():
                print(f"== {report} : déjà là, la série reprend après lui", flush=True)
                continue
            print(f"== {report}", flush=True)
            code = subprocess.run([sys.executable, *command], cwd=ROOT, env=env).returncode
            if code:
                print(f"{report} : la commande a rendu {code}, les suivants ne tournent pas.",
                      file=sys.stderr)
                return code
        return 0

    # -- the witness (D-335, D-336) ---------------------------------------------- #

    def witness_pass(self, reports: Path | None = None) -> str:
        """The study's shortest pass, which a witness replays: a range point by the fast
        path, or a first year when the study has no range; the first of them it has."""
        reports = reports or self.rapports
        candidates = ([f"{PLAGES}/{plage_name(*point)}" for point in self.points()]
                      + [f"premiere_annee_{name}.json" for name in self.noms])
        return next((c for c in candidates if (reports / c).exists()), candidates[0])

    def witnesses(self, reports: Path | None = None) -> tuple[str | None, dict[str, dict]]:
        """(C0, {Ck: witness}): C0 the commit of the witness pass's report, each Ck a commit
        on which that pass, replayed, gave the report again, outside `HORS_TEMOIN`. A
        witness is read again here, not believed: its report is compared anew."""
        reports = reports or self.rapports
        name = self.witness_pass(reports)
        if not (reports / name).exists():
            return None, {}
        reference = _read(reports / name)
        first = reference.get("commit")
        out: dict[str, dict] = {}
        folder = reports / TEMOINS
        for path in sorted(folder.glob("*.json")) if folder.exists() else []:
            witness = _read(path)
            commit = witness.get("commit") or ""
            report = witness.get("rapport") or {}
            if (witness.get("passe") == name and witness.get("reference") == first
                    and witness.get("identique") is True and commit and commit != first
                    and path.name == f"{commit[:7]}.json" and witness.get("where")
                    and report.get("commit") == commit and report.get("dirty") is False
                    and not ecarts(report, reference)):
                out[commit] = witness
        return first, out

    def joined(self, reports: Path | None = None) -> set[str]:
        """The commits whose reports read as one study's: C0 and every commit a witness
        joins to it."""
        first, covered = self.witnesses(reports)
        return ({first} | set(covered)) if first else set()

    def commits(self, used: set[str],
                reports: Path | None = None) -> list[tuple[str, dict | None]]:
        """The study's commits, in order, each after the first with the witness that joins
        it to the first; refused when one has none (D-335)."""
        first, covered = self.witnesses(reports)
        name = self.witness_pass(reports)
        alone = sorted(c for c in used if c != first and c not in covered)
        if first not in used or alone:
            raise EtudeError(
                f"les rapports de l'étude sont sur {len(used)} commits "
                f"({sorted(c[:7] for c in used)}) : {sorted(c[:7] for c in alone)} n'a pas "
                f"de passe témoin qui redonne `{name}` à l'identique. Sur chacun, "
                f"`impots etude temoin {self.nom} --ou \"…\"` la rejoue (D-335).")
        later = sorted(used - {first}, key=lambda c: (covered[c].get("computed") or "", c))
        return [(first, None)] + [(c, covered[c]) for c in later]

    def witness(self, where: str) -> int:
        """`impots etude temoin` : replay the witness pass on this commit, and write what it
        gave beside the report it replays, `temoins/<sha>.json`, identical or not."""
        import tempfile

        from impots.predictif import recherche

        commit, dirty = recherche.code_state(ROOT)
        if dirty:
            print("src/ a des modifications non commitées : le témoin nommerait un commit "
                  "dont il n'a pas chiffré le code. Commiter d'abord.", file=sys.stderr)
            return 1
        name = self.witness_pass()
        if not (self.rapports / name).exists():
            print(f"{_relative(self.rapports)} n'a pas `{name}` : le témoin rejoue une passe "
                  f"déjà faite.", file=sys.stderr)
            return 1
        reference = _read(self.rapports / name)
        if reference.get("commit") == commit:
            print(f"`{name}` est déjà sur le commit `{commit[:7]}` : un témoin y serait la "
                  f"même passe.", file=sys.stderr)
            return 1
        out = self.rapports / TEMOINS / f"{commit[:7]}.json"
        if out.exists():
            print(f"{_relative(out)} existe : un témoin n'est pas écrasé.", file=sys.stderr)
            return 1
        command = dict(self.passes(where))[name]
        with tempfile.TemporaryDirectory() as folder:
            replayed = Path(folder) / "rapport.json"
            print(f"== {name}, témoin sur `{commit[:7]}`", flush=True)
            code = subprocess.run([sys.executable, *command, "--sortie", str(replayed)],
                                  cwd=ROOT, env=self._env()).returncode
            if code:
                print(f"{name} : la commande a rendu {code}, aucun témoin n'est écrit.",
                      file=sys.stderr)
                return code
            report = _read(replayed)
        found = ecarts(report, reference)
        same = (not found and report.get("commit") == commit
                and report.get("dirty") is False)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({
            "etude": self.nom, "passe": name, "reference": reference.get("commit"),
            "commit": commit, "dirty": False, "where": where,
            "computed": date.today().isoformat(), "identique": same,
            "ecarts": found[:50], "rapport": report}, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8")
        if same:
            print(f"-> {_relative(out)} : `{name}` redonné à l'identique sur `{commit[:7]}`, "
                  f"hors {', '.join(HORS_TEMOIN)}.")
            return 0
        print(f"-> {_relative(out)} : `{name}` n'est PAS redonné à l'identique sur "
              f"`{commit[:7]}` ({len(found)} écarts : {found[:5]}). Ce commit ne rejoint pas "
              f"l'étude : sa série se rejoue.", file=sys.stderr)
        return 1

    def _write(self, path: Path, report: dict[str, Any]) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")
        return path

    def write_first_year(self, name: str, *, where: str, sortie: Path | None = None) -> Path:
        if name not in self.noms:
            raise EtudeError(f"{name} n'est pas un scénario de l'étude « {self.nom} » : "
                             f"{list(self.noms)}")
        report = first_year(name, where=where, scenarios=self.scenarios, mixte=self.mixte)
        return self._write(sortie or self.rapports / f"premiere_annee_{name}.json", report)

    def write_plage(self, mesure: str, champ: str, point: str, *, where: str,
                    sortie: Path | None = None) -> Path:
        if (mesure, champ, point) not in self.points():
            raise EtudeError(f"{mesure}/{champ}/{point} n'est pas un point de l'étude "
                             f"« {self.nom} ».")
        report = plage(self.cadre, self.programme, mesure, champ, point, where=where)
        return self._write(sortie or self.rapports / PLAGES / plage_name(mesure, champ, point),
                           report)

    def load_plages(self, reports: Path | None = None) -> list[dict[str, Any]]:
        """Each range point's report, refused unless it is the study's: its request as the
        programme and the frame give it now, on a clean commit, said where. Its commit is
        one of the study's, which `load` checks."""
        reports = (reports or self.rapports) / PLAGES
        wanted = {plage_name(*point) for point in self.points()}
        there = {p.name for p in reports.glob("*.json")} if reports.exists() else set()
        if there != wanted:
            raise EtudeError(f"les plages de l'étude : il manque {sorted(wanted - there)}, "
                             f"et {sorted(there - wanted)} n'en est pas.")
        out = []
        for mesure, champ, point in self.points():
            report = _read(reports / plage_name(mesure, champ, point))
            request = plage_request(self.cadre, self.programme, mesure, champ, point)
            if (report.get("request") != request or not report.get("commit")
                    or report.get("dirty") is not False or not report.get("where")
                    or (report.get("programme"), report.get("mesure"), report.get("champ"),
                        report.get("point")) != (self.programme, mesure, champ, point)):
                raise EtudeError(f"{mesure}/{champ}/{point} : le rapport n'est pas le point "
                                 f"de l'étude, sur un commit propre, dit où.")
            out.append(report)
        return out

    # -- the reports ------------------------------------------------------------- #

    def frame(self) -> dict[str, Any]:
        """What the annual report says of the study's frame (D-237, D-336)."""
        from impots.dette.path import SHIPPED
        from impots.predictif import chaine

        request = lire_cadre(self.cadre)
        first = chaine.START_YEAR + 1
        return {"spending_name": SHIPPED[request["spending"]["rule"]].name,
                "growth_name": request["growth"]["name"], "rate_name": request["rate"]["name"],
                "behavioural": request["behavioural"], "macro": request["macro"],
                "theta": request["theta"]["common"],
                "years": list(range(first, first + request["horizon"])),
                "persistance": request.get("persistance")}

    def load(self, reports: Path | None = None) -> list[dict[str, Any]]:
        """Each scenario's two reports, refused unless they are the study's, as it was set."""
        from impots import preregistration
        from impots import scenarios as scenarios_module
        from impots.api.schemas import (
            FirmResponse,
            PopulationResponse,
            PredictifReportResponse,
        )

        reports = reports or self.rapports
        texte = self.texte_lu()
        wanted = {f"{kind}_{name}.json" for name in self.noms
                  for kind in ("premiere_annee", "predictif")}
        there = {p.name for p in reports.glob("*.json")} if reports.exists() else set()
        if there != wanted:
            raise EtudeError(f"l'étude porte une première année et un chemin par scénario : "
                             f"il manque {sorted(wanted - there)}, et "
                             f"{sorted(there - wanted)} n'en est pas.")
        frame = self.frame()
        entries, commits = [], set()
        for volet in self.volets:
            name = volet.scenario
            first = _read(reports / f"premiere_annee_{name}.json")
            path = _read(reports / f"predictif_{name}.json")
            for label, report in (("la première année", first), ("le chemin", path)):
                if not report.get("commit") or report.get("dirty") is not False:
                    raise EtudeError(f"{name}, {label} : ne nomme pas un commit dont il a "
                                     f"chiffré le code.")
                if not report.get("where"):
                    raise EtudeError(f"{name}, {label} : ne dit pas où ses passes ont "
                                     f"tourné.")
                commits.add(report["commit"])
            kind, endpoint, payload = first_year_payload(name, self.scenarios, self.mixte)
            if (first.get("scenario"), first.get("kind"), first.get("endpoint"),
                    first.get("request")) != (name, kind, endpoint, payload):
                raise EtudeError(f"{name} : la première année n'a pas chiffré le scénario "
                                 f"de l'étude, par l'appel de sa chaîne.")
            firms = None
            if kind == "mixte":
                response = PopulationResponse.model_validate(first["response"]["menages"])
                firms = FirmResponse.model_validate(first["response"]["entreprises"])
            else:
                response = (FirmResponse if kind == "entreprises" else PopulationResponse
                            ).model_validate(first["response"])
            if response.reform_cost is None or (firms is not None
                                                and firms.reform_cost is None):
                raise EtudeError(f"{name} : la première année n'a pas de coût.")
            firm_reply = response if kind == "entreprises" else firms
            if firm_reply is not None and (
                    firm_reply.meta.vintage != self.millesime_entreprises
                    or firm_reply.meta.cells_are_synthetic):
                raise EtudeError(f"{name} : la première année n'a pas tourné sur les "
                                 f"entreprises de {self.millesime_entreprises}, leurs "
                                 f"cellules réelles (millésime « {firm_reply.meta.vintage} »).")
            try:
                PredictifReportResponse.model_validate(path)
            except ValueError as error:
                raise EtudeError(f"{name} : le chemin ne valide pas : {error}") from error
            scenario = scenarios_module.load(name, self.scenarios)
            said = {k: path.get(k) for k in ("spending_name", "growth_name", "rate_name",
                                             "behavioural", "macro")}
            if (path.get("scenario") != name or said != {k: frame[k] for k in said}
                    or set(path["theta"].values()) != {frame["theta"]}
                    or [row["year"] for row in path["years"]] != frame["years"]
                    or (path.get("annees") or []) != list(scenario.annees)):
                raise EtudeError(f"{name} : le chemin n'a pas tourné dans le cadre de "
                                 f"l'étude, sur son scénario.")
            # A frame that says « lue » wants a path that draws it (D-336). A report
            # written before D-336 has neither « lue », nor `rejeu`, nor `monte_carlo`:
            # it is still read, and its page is the one it always rendered, until the
            # series runs again. That is the one field the comparison tolerates on an old
            # report; a new report without « lue » is refused.
            if frame["persistance"] is not None and path.get("macro"):
                drawn = ([p["persistence"] for p in path.get("side_by_side") or []]
                         or [path.get("persistence")])
                old = "rejeu" not in path and "monte_carlo" not in path
                if frame["persistance"] not in drawn and not old:
                    raise EtudeError(f"{name} : le cadre lit la persistance "
                                     f"« {frame['persistance']} », et le chemin ne la "
                                     f"trace pas ({drawn}).")
            case = grade = None
            if (preregistration.CHIFFRAGES / f"{name}.yaml").exists():
                case = preregistration.load(name)
                if case.mirror != volet.miroir:
                    raise EtudeError(f"{name} : l'étude le lit {'en' if volet.miroir else 'sans'}"
                                     f" miroir, son enregistrement "
                                     f"{'en' if case.mirror else 'sans'} miroir.")
                if case.comparator is not None:
                    grade = preregistration.grade(case)
            sign = -1 if volet.miroir else 1
            entries.append({
                "name": name, "volet": volet, "article": texte.article(volet),
                "scenario": scenario, "kind": kind, "first": first, "response": response,
                "firms": firms, "path": path, "case": case, "grade": grade, "sign": sign,
                "cost": sign * (float(response.reform_cost)
                                + (float(firms.reform_cost) if firms is not None else 0.0)),
                "debt": [{**row, "theta": sign * row["theta"],
                          "corners": [sign * c for c in row["corners"]]}
                         for row in debt(path)]})
        plages = self.load_plages(reports) if self.programme is not None else []
        commits |= {r["commit"] for r in plages}
        # One study reads on one code, or on commits a witness pass joins to the first: on
        # each, the pass replayed gave its report again (D-335, D-336).
        joined = self.commits(commits, reports)
        for entry in entries:
            entry.update(commits=joined, plages=plages)
        return entries

    # -- the page ---------------------------------------------------------------- #

    def render(self, entries: list[dict[str, Any]]) -> str:
        """The Markdown page: the lines, each number resolved to its text."""
        lines, n = self.lines(entries)
        return "\n".join(n.resolve(line) for line in lines)

    def lines(self, entries: list[dict[str, Any]]) -> tuple[list[str], Nombres]:
        """The page's Markdown lines, each number a token of `Nombres` that says what it
        rests on: the page and the site are one text (D-304)."""
        from impots import fiche

        texte = self.texte_lu()
        frame = self.frame()
        if frame["theta"] != 0.5 or not (frame["behavioural"] and frame["macro"]):
            raise EtudeError(f"le cadre « {self.cadre} » n'est pas celui de D-289 (θ½, "
                             f"comportements et boucle) : la page le dirait.")
        last = frame["years"][-1]
        lines: list[str] = []
        w = lines.append
        n = Nombres()
        w(f"# {self.titre}")
        w("")
        w(f"<!-- Généré par `impots etude ecrire {self.nom}` depuis "
          f"{_relative(self.rapports)}/ ; ne pas éditer à la main. -->")
        w("")
        w(texte.chapeau(entries, last, n))
        w("")
        w(f"Chaque nombre dépend de ce qui est dit à côté de lui. Le coût de la première année "
          f"est mécanique : personne ne change de comportement. La bande dit ce que les "
          f"comportements y changent quand une étude publiée permet de le dire. La dette en "
          f"{last} dépend d'hypothèses de croissance, de taux et de dépenses nommées en bas "
          f"de page, et de θ, la position de chaque réponse dans sa fourchette publiée : θ½ "
          f"est le milieu, les coins de la boîte en sont les extrêmes.")
        w("")
        if any(e["volet"].miroir for e in entries):
            w("**En miroir.** L'arbre des paramètres porte déjà l'état que la mesure produit : "
              "chaque scénario chiffre donc la mesure inverse, et la page dit la mesure, "
              "chaque réponse changée de signe (D-298). C'est exact pour le coût et les "
              "déciles, gagnants et perdants échangés, qui sont la différence de deux passes ; "
              "c'est vrai au premier ordre pour la bande des comportements, l'éventail macro "
              "et la dette, calculés autour de l'état de départ.")
            w("")
        w("## En bref")
        w("")
        read = lectures(entries)
        if read:
            w(f"| {getattr(texte, 'colonne', 'article')} | la première année | le chiffrage "
              f"officiel | dette en {last}, à θ½ | verdict | selon θ |")
            w("|---|---|---|---|---|---|")
        else:
            w(f"| {getattr(texte, 'colonne', 'article')} | la première année | le chiffrage "
              f"officiel | dette en {last}, à θ½ | selon θ |")
            w("|---|---|---|---|---|")
        for entry in entries:
            grade = entry["grade"]
            official = "—" if grade is None else (
                f"{n(fiche._eur(grade.published_eur), 'publié')}, "
                f"{'dans' if grade.verdict == 'within' else 'hors de'} la tolérance")
            lead = n(_points(entry["debt"][0]["theta"]), debt_etage(entry["path"]),
                     conditionnel=True)
            mc = f"{verdict_mc(entry)} | " if read else ""
            w(f"| {texte.label(entry)} | {n(fiche._eur(entry['cost']), 'L2')} | {official} | "
              f"{lead} | {mc}{verdict(entry['debt'])} |")
        w("")
        if read:
            from impots.predictif import montecarlo

            haut = n(f"{montecarlo.SEUIL_VERDICT:.0%}".replace("%", "\u202f%"), "déclaré")
            w(f"Le verdict se lit sur le Monte-Carlo (D-345) : « hausse » quand au moins "
              f"{haut} des tirages font monter la dette, vue vieillie, « baisse » quand au "
              f"moins {haut} la font baisser, « dépend » entre les deux. « Selon θ » dit ce "
              f"que la boîte θ en dit, sans probabilité : un seul signe à θ½ et à chaque "
              f"coin, ou non.")
            w("")
        # A law has articles; a programme has measures (D-336).
        unit = getattr(texte, "unite", "article")
        if generation(entries):
            w(f"Un coût positif coûte au budget, un coût négatif lui rapporte. La dette est "
              f"en points de PIB, dans la vue vieillie et sous la persistance « lue » de "
              f"l'effet macro de chaque {unit}, Mésange lu à ses horizons ; « selon θ » lit "
              f"les deux vues sous cette persistance seule (D-336). « Éteint » et « tenu » "
              f"sont des sensibilités, données plus bas, hors du verdict.")
        else:
            w(f"Un coût positif coûte au budget, un coût négatif lui rapporte. La dette est "
              f"en points de PIB, dans la vue vieillie et sous la première persistance de "
              f"l'effet macro de chaque {unit} ; « selon θ » lit toutes les vues et toutes "
              f"les persistances.")
        w("")
        for entry in entries:
            w(texte.heading(entry, n))
            w("")
            w(f"*{n(entry['scenario'].source, 'hypothèse')}*")
            w("")
            if entry["scenario"].note:
                w(n(entry["scenario"].note, "hypothèse"))
                w("")
            w("### 1. Ce qu'il coûte, et qui y gagne")
            w("")
            self._first(w, n, entry, texte)
            w("")
            w("### 2. Avec les comportements et l'économie")
            w("")
            self._second(w, n, entry)
            w(f"### 3. La dette en {last}")
            w("")
            self._third(w, n, entry)
            w("### L'écart au chiffrage officiel")
            w("")
            if hasattr(texte, "official"):
                texte.official(w, n, entry)
            else:
                self._official(w, n, entry)
        texte.refusals(w, entries, n)
        if read and (self.rapports / AVANT).exists():
            self._avant(w, n, entries, json.loads((self.rapports / AVANT).read_text(
                encoding="utf-8")))
        w("## D'où viennent ces nombres")
        w("")
        path = entries[0]["path"]
        first = entries[0]["first"]
        commits = entries[0]["commits"]
        if len(commits) > 1:
            # Several commits, each after the first joined to it by its witness (D-335).
            w(f"Les passes ont tourné sur {len(commits)} commits, {first['where']} ; chaque "
              f"rapport nomme le sien. Un commit après le premier rejoint l'étude quand sa "
              f"passe témoin, `{self.witness_pass()}` rejouée sur lui, redonne son rapport à "
              f"l'identique, hors date, commit et lieu (D-335) :")
            w("")
            for commit, witness in commits:
                w(f"* `{commit[:7]}`, le premier." if witness is None else
                  f"* `{commit[:7]}`, rejoint par "
                  f"`{_relative(self.rapports)}/{TEMOINS}/{commit[:7]}.json`, témoin du "
                  f"{witness['computed']}.")
            w("")
            opening = "Cadre"
        else:
            opening = (f"Les passes ont tourné sur le commit `{first['commit'][:7]}`, "
                       f"{first['where']}. Cadre")
        w(f"{opening} du chemin annuel : {n(path['growth_name'], 'hypothèse')} ; "
          f"{n(path['rate_name'], 'hypothèse')} ; {n(path['spending_name'], 'hypothèse')} ; "
          f"droit reconduit tel qu'openfisca le porte ; θ½ sur "
          f"toutes les lignes ; comportements et boucle macro appliqués.")
        w("")
        w(f"*{n(path['uprating_note'], 'hypothèse')}*")
        w("")
        if read:
            w("Le secteur public est câblé (D-346) : un titulaire est payé d'un traitement "
              "indiciaire et de primes, et cotise à son régime ; un contractuel cotise au "
              "régime général, sans allègement. L'enquête Emploi dit titulaire ou "
              "contractuel et la fonction publique, pas le corps ni l'indice : la part des "
              "primes est la moyenne qu'openfisca porte, la même pour tous.")
            w("")
        where = _relative(self.rapports)
        for entry in entries:
            case = (f", `chiffrages_preregistres/{entry['name']}.yaml`" if entry["case"]
                    else "")
            w(f"* `{where}/premiere_annee_{entry['name']}.json`, "
              f"`{where}/predictif_{entry['name']}.json`{case}")
        if hasattr(texte, "sources"):
            texte.sources(w, where)
        w("")
        # Every amount says what it rests on: one the page quotes without its étage is
        # refused here, before the Markdown or the site can show it (D-304).
        for line in lines:
            bare = n.resolve(line, lambda _: "")
            if found := AMOUNT.search(bare):
                raise EtudeError(f"« {found[0]} » sans son étage : « {bare[:90]} »")
        return lines, n

    @staticmethod
    def _sizes(response: Any, sign: int) -> list[tuple[str, float, float, float]]:
        """(taille, firms, firms affected, total delta) of a firm reply's cells."""
        out: dict[str, list[float]] = {}
        for cell in response.cells:
            row = out.setdefault(cell.taille, [0.0, 0.0, 0.0])
            row[0] += cell.n_firms
            row[1] += cell.n_firms * (cell.share_affected or 0.0)
            row[2] += sign * cell.n_firms * (cell.mean_delta or 0.0)
        return [(taille, *row) for taille, row in out.items()]

    def _first(self, w: Any, n: Nombres, entry: dict[str, Any], texte: Any) -> None:
        from impots import fiche

        response, year, cost = entry["response"], entry["scenario"].year, entry["cost"]
        sense = "coûte" if cost > 0 else "rapporte"
        if entry["kind"] == "mixte":
            firms, sign = entry["firms"], entry["sign"]
            w(f"La part chiffrée {sense} **{n(fiche._width(cost), 'L2')}** "
              f"{texte.first_year(year)} : {n(fiche._eur(sign * response.reform_cost), 'L2')} "
              f"pour les ménages, sur la population de {response.meta.vintage} au droit de "
              f"{year}, et {n(fiche._eur(sign * firms.reform_cost), 'L2')} pour les "
              f"entreprises, sur celles de {firms.meta.vintage}.")
            w("")
            _deciles(w, n, _mirrored(response, sign))
            w("| taille | entreprises | touchées | impôt en plus |")
            w("|---|---|---|---|")
            for taille, count, touched, delta in self._sizes(firms, sign):
                w(f"| {taille} | {n(fiche._num(count), 'L1')} | "
                  f"{n(fiche._num(touched), 'L2')} | {n(fiche._eur(delta), 'L2')} |")
            w("")
            w(firms.meta.note)
            return
        if entry["kind"] == "entreprises":
            w(f"La mesure {sense} **{n(fiche._width(cost), 'L2')}** en {year}, sur les "
              f"entreprises de {response.meta.vintage} au droit de {year}.")
            w("")
            w("| taille | entreprises | touchées | impôt en plus |")
            w("|---|---|---|---|")
            for taille, count, touched, delta in self._sizes(response, entry["sign"]):
                w(f"| {taille} | {n(fiche._num(count), 'L1')} | "
                  f"{n(fiche._num(touched), 'L2')} | {n(fiche._eur(delta), 'L2')} |")
            w("")
            w(response.meta.note)
        else:
            w(f"La mesure {sense} **{n(fiche._width(cost), 'L2')}** "
              f"{texte.first_year(year)}, sur la population de {response.meta.vintage} au "
              f"droit de {year}.")
            w("")
            _deciles(w, n, _mirrored(response, entry["sign"]))

    def _second(self, w: Any, n: Nombres, entry: dict[str, Any]) -> None:
        from impots import fiche

        response, sign = entry["response"], entry["sign"]
        if entry["kind"] == "mixte":
            w("La bande et l'éventail ne lisent que la part des ménages : aucun canal des "
              "comportements ne lit une réforme des entreprises, et aucune variante de "
              "Mésange ne porte leurs impôts. La dette, plus bas, compte les deux parts.")
            w("")
        behavioural = response.behavioural
        if behavioural is None:
            w("**Bande comportementale : aucune.** " + (
                "Aucun canal des ménages ne lit une réforme des seules entreprises, et la "
                "chaîne des entreprises n'en calcule pas." if entry["kind"] == "entreprises"
                else "Aucune réponse comportementale n'a été calculée."))
        elif behavioural.band is None:
            w(f"**Bande comportementale : aucune, et la raison est donnée.** "
              f"{behavioural.grade_reason or 'non précisée'}")
        else:
            band = behavioural.band
            # The band is about the budget balance, the mechanical figure repeated in its
            # sign; the page reads costs. Turned over only once checked (D-289).
            if band.unit != "EUR" or abs(behavioural.mechanical + response.reform_cost) > 1.0:
                raise EtudeError(f"{entry['name']} : la bande n'est pas en euros autour du "
                                 f"solde de la mesure ({behavioural.mechanical:+.0f} pour un "
                                 f"coût de {response.reform_cost:+.0f}) ; la page la lirait "
                                 f"à l'envers.")
            # A cost is minus the balance; the measure's, in mirror, is minus that.
            low, central, high = ((-band.p90, -band.p50, -band.p10) if sign == 1
                                  else (band.p10, band.p50, band.p90))
            w(f"**Une fois les comportements pris en compte**, la mesure coûte de "
              f"{n(fiche._eur(low), 'L3')} à {n(fiche._eur(high), 'L3')}, central "
              f"{n(fiche._eur(central), 'L3')} (grade **{behavioural.grade}**), pour "
              f"{n(fiche._eur(entry['cost']), 'L2')} sans eux.")
            if behavioural.grade_reason:
                w("")
                w(f"*{behavioural.grade_reason}*")
        w("")
        macro = getattr(response, "macro", None)
        if macro is not None and macro.available:
            # Never without its strip, as the fiche refuses it: a fan alone reads as a
            # forecast.
            if macro.assumptions is None:
                raise EtudeError(f"{entry['name']} : l'éventail macro n'a pas son bandeau "
                                 f"d'hypothèses ; il se lirait comme une prévision.")
            a = macro.assumptions
            w(f"**L'effet sur l'économie**, l'éventail macro de grade **{a.grade}**, "
              f"couverture {n(fiche._pct(a.covered_share), 'L4')}, conjoncture "
              f"« {a.cycle_state} » :")
            w("")
            for label, series in (("PIB", macro.gdp), ("emploi", macro.jobs)):
                for horizon, q in sorted(series.items()):
                    years = f"à {horizon} an{'' if horizon == '1' else 's'}"
                    p10, p50, p90 = ((q.p10, q.p50, q.p90) if sign == 1
                                     else (-q.p90, -q.p50, -q.p10))
                    w(f"* **{label}, {years}** : "
                      f"{n(fiche._band(p10, p50, p90, q.unit), 'L4')}")
            w("")
            if a.banner:
                w(f"> {a.banner}")
                w("")
        elif macro is not None:
            w(f"**Éventail macro : refusé.** {macro.unavailable_because}")
            w("")
        closed = entry["path"].get("closed") or {}
        if closed:
            w("Ce que la chaîne ne lit pas, et pourquoi :")
            w("")
            for what, why in closed.items():
                w(f"* **{what}** — {why.split(' ; ')[0].split('. ')[0].rstrip('.')}.")
            w("")

    def _third(self, w: Any, n: Nombres, entry: dict[str, Any]) -> None:
        path, rows = entry["path"], entry["debt"]
        year = path["years"][-1]["year"]
        etage = debt_etage(path)

        def points(value: float) -> str:
            return n(_points(value), etage, conditionnel=True)

        if path.get("annees"):
            w(f"La mesure ne s'applique qu'en {', '.join(map(str, path['annees']))} : le "
              f"chemin la chiffre cette année-là et ne lui prête rien les autres (D-288).")
            w("")
        def table(shown: list[dict[str, Any]]) -> None:
            w(f"| persistance | vue | Δ dette {year}, à θ½ | aux coins de la boîte |")
            w("|---|---|---|---|")
            for row in shown:
                corners = (f"de {points(min(row['corners']))} à "
                           f"{points(max(row['corners']))}" if row["corners"] else "—")
                w(f"| {row['label'] or '—'} | {VIEWS[row['view']]} | {points(row['theta'])} "
                  f"| {corners} |")
            w("")

        if not lue(rows):
            # A report before D-336: « éteint » and « tenu », both in the verdict, the page
            # as it always was until the series is run again.
            table(rows)
            w(f"En points de PIB de {year}, la dette avec la mesure moins la dette sans "
              f"elle. La vue vieillie fait vieillir la population chaque année avec les "
              f"salaires ; la vue figée la garde telle qu'elle est. Sur ces passes, "
              f"{VERDICTS[verdict(rows)].format(year=year)}.")
            w("")
            return
        table(verdict_rows(rows))
        w(f"En points de PIB de {year}, la dette avec la mesure moins la dette sans elle, "
          f"l'effet macro lu dans Mésange à ses horizons (persistance « lue », D-336). La "
          f"vue vieillie fait vieillir la population chaque année avec les salaires ; la vue "
          f"figée la garde telle qu'elle est. Sous cette persistance, "
          f"{VERDICTS[verdict(rows)].format(year=year)}.")
        w("")
        if path.get("lectures") is not None and path.get("monte_carlo"):
            from impots.predictif import montecarlo

            haut = n(f"{montecarlo.SEUIL_VERDICT:.0%}".replace("%", "\u202f%"), "déclaré")
            w(f"**Le verdict**, lu sur le Monte-Carlo (D-345) : "
              f"{VERDICTS_MC[verdict_mc(entry)].format(year=year, haut=haut)}.")
            w("")
        others = sensitivity_rows(rows)
        if others:
            w("**Les sensibilités, hors du verdict.** Les deux persistances d'avant D-336, "
              "sur les mêmes passes : l'effet macro éteint après trois ans, ou tenu au "
              "niveau de la troisième année. Mésange ne porte ni l'une ni l'autre ; elles "
              "disent ce que le choix de la persistance pèse, et n'entrent pas dans le "
              "verdict.")
            w("")
            table(others)
        self._monte_carlo(w, n, entry, etage)
        if path.get("lectures") is not None:
            self._lectures(w, n, entry, etage)

    def _monte_carlo(self, w: Any, n: Nombres, entry: dict[str, Any], etage: str) -> None:
        """The distribution of Δb under declared laws, beside the box (D-336, decision 6):
        P(hausse), its quantiles, its heaviest Sobol groups; nothing when the report has
        none. In mirror, the measure's: Δb turned over, to the first order as the rest."""
        monte = entry["path"].get("monte_carlo")
        if not monte:
            return
        sign, year = entry["sign"], monte["annee"]

        def points(value: float) -> str:
            return n(_points(value), etage, conditionnel=True)

        def share(value: float) -> str:
            from impots.reporting import pct_fr

            return n(pct_fr(value), etage, conditionnel=True)

        w(f"**La distribution, à côté de la boîte.** La boîte dit jusqu'où Δb va quand "
          f"chaque effet parcourt sa fourchette publiée : ce n'est pas une probabilité. Le "
          f"Monte-Carlo en est une, sous des lois déclarées : {monte['lois']} "
          f"(ρ = {n(format(monte['rho'], 'g').replace('.', ','), 'hypothèse')}, "
          f"{n(monte['tirages'], 'hypothèse')} tirages, persistance « "
          f"{monte.get('persistence') or 'aucune'} », D-336). D'autres lois donneraient "
          f"une autre réponse.")
        w("")
        # The quantiles' levels are the declared laws' own, a choice of the study.
        w(f"| vue | P(hausse de la dette en {year}) | quantile "
          f"{n('5 %', 'hypothèse')} | médiane | quantile {n('95 %', 'hypothèse')} | "
          f"ce qui pèse le plus (Sobol, total) |")
        w("|---|---|---|---|---|---|")
        for view, label in VIEWS.items():
            read = (monte.get("vues") or {}).get(view)
            if not read:
                continue
            q = read["quantiles"]
            # The measure's Δb is minus the scenario's, to the first order (D-298): its
            # rise is the scenario's fall, and its quantiles turn over.
            rise = read["p_hausse"] if sign == 1 else 1.0 - read["p_hausse"]
            q05, q50, q95 = ((q["q05"], q["q50"], q["q95"]) if sign == 1
                             else (-q["q95"], -q["q50"], -q["q05"]))
            heaviest = sorted(((name, s) for name, s in (read.get("sobol") or {}).items()
                               if s is not None), key=lambda kv: (-kv[1]["total"], kv[0]))[:3]
            groups = ", ".join(
                f"{sobol_group(name)} "
                f"{n(format(s['total'], '.2f').replace('.', ','), etage, conditionnel=True)}"
                for name, s in heaviest) or "—"
            w(f"| {label} | {share(rise)} | {points(q05)} | {points(q50)} | {points(q95)} | "
              f"{groups} |")
        w("")

    def _lectures(self, w: Any, n: Nombres, entry: dict[str, Any], etage: str) -> None:
        """The readings of D-349 beside the headline: the decomposition of Δb, the added
        debt at a market rate, Mésange's alternative wage formation with its box and its
        verdict, and the corporate tax an employer-contribution measure leaves out. In
        mirror, the measure's: every Δb turned over, as the rest."""
        path, sign = entry["path"], entry["sign"]
        read = path["lectures"]
        year = path["years"][-1]["year"]
        views = [v for v in VIEWS if v in read["decomposition"]]

        def points(value: float) -> str:
            return n(_points(sign * value), etage, conditionnel=True)

        w(f"**D'où vient Δb.** La dette de {year} en trois marches, à θ½ sous la "
          f"persistance « lue » : le coût après comportements, sans la boucle macro ; ce "
          f"que le PIB plus haut ou plus bas change au seul ratio, comme dénominateur ; ce "
          f"que les recettes induites par l'activité y changent. Les trois font la ligne du "
          f"tableau (D-349).")
        w("")
        w("| vue | le coût, sans boucle | le PIB, dénominateur | les recettes induites | "
          f"Δ dette {year} |")
        w("|---|---|---|---|---|")
        for view in views:
            d = read["decomposition"][view]
            w(f"| {VIEWS[view]} | {points(d['cout'])} | {points(d['denominateur'])} | "
              f"{points(d['retroaction'])} | {points(d['total'])} |")
        w("")
        rate = read["taux_marche"]
        taux = n(f"{rate['taux'] * 100:.1f}".replace(".", ",") + "\u202f%", "hypothèse")
        w(f"**Au taux de marché.** La dette ajoutée est chargée au taux implicite de 2025 "
          f"(D-336). Chargée à {taux}, hypothèse déclarée d'une OAT à dix ans de fin 2026 : "
          + " ; ".join(f"{points(rate[v])} en vue {VIEWS[v]}, contre "
                       f"{points(read['decomposition'][v]['total'])}" for v in views)
          + ".")
        w("")
        variante = read.get("variante_salariale")
        if variante:
            from impots.reporting import pct_fr

            w("**Si les salaires se forment autrement.** Mésange publie une sensibilité de "
              "ses variantes à la formation des salaires (folios 137 et 138) : une courbe de "
              "Phillips pour les cotisations employeurs et la TVA, un super-brut visé pour "
              "les cotisations salariés, la CSG et l'IR. Le multiplicateur y est recentré, à "
              "écart-type, persistance et recettes induites par point de PIB inchangés ; "
              "Mésange n'imprime pas le solde de la variante, que la page suppose "
              "proportionnel au PIB (D-349). C'est une sensibilité, hors du verdict.")
            w("")
            w(f"| vue | Δ dette {year}, à θ½ | aux coins de la boîte | P(hausse) | verdict |")
            w("|---|---|---|---|---|")
            for view in views:
                box = variante["boite"][view]
                corners = [sign * c for _, c in box["corners"]]
                lo = n(_points(min(corners)), etage, conditionnel=True)
                hi = n(_points(max(corners)), etage, conditionnel=True)
                mc = variante["monte_carlo"][view]
                rise = mc["p_hausse"] if sign == 1 else 1.0 - mc["p_hausse"]
                said = verdict_mc(entry, {"vues": {"vieillie": mc}})
                w(f"| {VIEWS[view]} | {points(box['theta'])} | de {lo} à {hi} | "
                  f"{n(pct_fr(rise), etage, conditionnel=True)} | {said} |")
            w("")
            if variante.get("non_variees"):
                names = ", ".join(f"`{i}`" for i in variante["non_variees"])
                w(f"Mésange n'imprime pas de variante salariale pour {names} : ces "
                  f"instruments gardent leur multiplicateur central, et la variante est "
                  f"partielle.")
                w("")
        macro = (path.get("rejeu") or {}).get("macro") or {}
        if any(i in (macro.get("instruments") or {}) for i in EMPLOYEURS):
            normal = n("25\u202f%", "texte")
            w(f"**Brut d'IS.** Les cotisations employeurs se déduisent du bénéfice : ce "
              f"qu'elles changent, l'IS des entreprises bénéficiaires le change en sens "
              f"inverse, jusqu'à {normal} du montant au taux normal. La "
              f"passe des ménages ne le chiffre pas ; le coût de la première année et la "
              f"dette en sont bruts, et l'effet net est plus petit.")
            w("")

    def _avant(self, w: Any, n: Nombres, entries: list[dict[str, Any]],
               avant: dict[str, Any]) -> None:
        """What moved since the previous series (D-350): each entry's first-year cost, its
        Δb at θ½ and its verdict, then and now, and the corrections that touch it. The
        then is the file frozen before the series, not a memory."""
        from impots import fiche

        w("## Ce qui a bougé depuis la série précédente")
        w("")
        w(f"La série précédente a tourné sur `{avant['commit'][:7]}` ; ce qu'elle disait est "
          f"figé dans `{_relative(self.rapports / AVANT)}` avant que celle-ci ne remplace "
          f"ses rapports (D-350). Son verdict lisait la boîte θ ; celui-ci lit le "
          f"Monte-Carlo.")
        w("")
        w("| | la première année, avant → après | dette à θ½, avant → après | verdict, "
          "avant → après |")
        w("|---|---|---|---|")
        texte = self.texte_lu()
        for entry in entries:
            then = avant["scenarios"].get(entry["name"])
            if then is None:
                w(f"| {texte.label(entry)} | nouveau | nouveau | nouveau |")
                continue
            etage = debt_etage(entry["path"])

            def points(value: float, etage: str = etage) -> str:
                return n(_points(value), etage, conditionnel=True)

            w(f"| {texte.label(entry)} | {n(fiche._eur(then['cout']), 'L2')} → "
              f"{n(fiche._eur(entry['cost']), 'L2')} | {points(then['dette'])} → "
              f"{points(entry['debt'][0]['theta'])} | {then['selon_theta']} → "
              f"{verdict_mc(entry)} |")
        w("")
        w("Ce qui touche chaque ligne :")
        w("")
        for entry in entries:
            w(f"* **{texte.label(entry)}** : {', '.join(causes(entry))}.")
        w("")
        w("La D-entrée du résultat de la série mesure ce que chaque correction y pèse.")
        w("")

    def figer_avant(self) -> Path:
        """`impots etude avant` : freeze what the committed series says (D-350), before
        the next one replaces its reports. Refused if a frozen file is already there: it
        is the previous series', not overwritten in silence."""
        target = self.rapports / AVANT
        if target.exists():
            raise EtudeError(f"{_relative(target)} existe : la série d'avant est déjà "
                             f"figée, et ne l'est pas deux fois.")
        entries = self.load()
        snapshot = {"commit": entries[0]["first"]["commit"], "scenarios": {
            e["name"]: {"cout": e["cost"], "dette": e["debt"][0]["theta"],
                        "selon_theta": verdict(e["debt"])} for e in entries}}
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n",
                          encoding="utf-8")
        return target

    def _official(self, w: Any, n: Nombres, entry: dict[str, Any]) -> None:
        from impots import fiche

        case, grade = entry["case"], entry["grade"]
        if grade is None:
            w("Aucun cas noté : " + ("son enregistrement n'a pas de comparateur publié."
                                     if case else "le scénario n'est pas enregistré.")
              + " La page ne dit pas d'écart.")
            w("")
            return
        rel = "n. d." if grade.relative_gap is None else (
            f"{grade.relative_gap:+.1%}".replace(".", ","))
        within = "**dans la tolérance**" if grade.verdict == "within" else (
            "**hors de la tolérance**")
        w(f"Enregistré le {case.pre_registered[:10]}, sur le commit `{case.commit[:7]}`, "
          f"avant l'ouverture de l'annexe : simulé {n(fiche._eur(grade.simulated_eur), 'L2')}, "
          f"publié {n(fiche._eur(grade.published_eur), 'publié')} "
          f"({n(case.comparator.source, 'publié')}). Écart "
          f"{n(fiche._eur(grade.gap_eur), 'L2')} ({n(rel, 'L2')}), pour une tolérance "
          f"déclarée de {n(fiche._width(grade.allowed_eur), 'déclaré')} : {within}.")
        w("")
        now = entry["cost"]
        w(f"La première année de cette étude, sur le code de l'étude, chiffre "
          f"{n(fiche._eur(now), 'L2')}, soit {n(fiche._eur(now - grade.simulated_eur), 'L2')} "
          f"de l'enregistrement. Le chiffre noté reste celui de l'enregistrement : c'est lui "
          f"qui a été préenregistré.")
        w("")

    def drift(self) -> str | None:
        """Why the committed page is not what the committed reports render, or None. A
        study whose passes have not run has neither reports nor page; a run one has both."""
        reports = self.rapports.exists() and any(self.rapports.glob("*.json"))
        if not reports and not self.page.exists():
            return None
        if not self.page.exists():
            return f"{_relative(self.page)} n'existe pas : `impots etude ecrire {self.nom}`."
        if not reports:
            return (f"{_relative(self.page)} existe sans les rapports de "
                    f"{_relative(self.rapports)} : la page dirait ce qu'aucun rapport ne dit.")
        where = difference(self.page.read_text(encoding="utf-8"), self.render(self.load()))
        return None if where is None else f"{_relative(self.page)}, {where}."


def presidentielle(etudes: list[Etude]) -> tuple[list[str], Nombres]:
    """The page of the 24 declared candidates (D-328): each programme's coverage, its
    refusals by door, and whether it has a study. No number for a programme of which
    nothing is priced: its doors say what would open it."""
    from impots import programmes as pg

    n = Nombres()
    lines: list[str] = []
    w = lines.append
    slugs = pg.lister()
    studied = {e.programme for e in etudes if e.programme is not None}
    releves = sorted({pg.charger(slug).releve for slug in slugs})
    w("# Les programmes de la présidentielle 2027")
    w("")
    w(f"Les {n(len(slugs), 'programme')} candidats déclarés, programmes relevés au "
      f"{releves[-1].strftime('%d/%m/%Y')}. Pour chacun : ses mesures relevées et sourcées, "
      f"celles qui énoncent un paramètre, celles que l'outil chiffre, et pourquoi il refuse "
      f"les autres. Un candidat dont une mesure se chiffre a son étude, en trois réponses, "
      f"sur cette part et elle seule. Les autres n'ont pas de chiffre : la porte de chaque "
      f"refus dit ce que l'outil devrait savoir faire pour l'ouvrir.")
    w("")
    w("| candidat | mesures | paramétrées | chiffrées | étude | refusées, par porte |")
    w("|---|---|---|---|---|---|")
    totals = [0, 0, 0]
    for slug in slugs:
        p = pg.charger(slug)
        c = p.couverture()
        portes = ", ".join(f"`{k}` {n(v, 'texte')}" for k, v in sorted(
            c["refus_par_porte"].items(), key=lambda kv: (-kv[1], kv[0]))
            if k != "vague") or "—"
        etude_ = "oui" if slug in studied else "—"
        w(f"| {p.candidat} ({p.parti}) | {n(c['mesures'], 'programme')} | "
          f"{n(c['parametrees'], 'programme')} | {n(c['chiffrees'], 'texte')} | {etude_} | "
          f"{portes} |")
        for i, key in enumerate(("mesures", "parametrees", "chiffrees")):
            totals[i] += c[key]
    w(f"| **total** | {n(totals[0], 'programme')} | {n(totals[1], 'programme')} | "
      f"{n(totals[2], 'texte')} | {n(len(studied), 'texte')} | |")
    w("")
    w("Les portes :")
    w("")
    used = sorted({k for slug in slugs for k in pg.charger(slug).couverture()[
        "refus_par_porte"] if k != "vague"})
    for porte in used:
        w(f"* `{porte}` — {amounts(pg.PORTES[porte], 'texte', n)}.")
    w("")
    for line in lines:
        bare = n.resolve(line, lambda _: "")
        if found := AMOUNT.search(bare):
            raise EtudeError(f"« {found[0]} » sans son étage : « {bare[:90]} »")
    return lines, n


def definition(nom: str, directory: Path | None = None) -> Etude:
    """The study `nom`, read from `etudes/<nom>.json`, refused unless every field is one a
    study has and says what the page needs."""
    path = (directory or DEFINITIONS) / f"{nom}.json"
    if not path.exists():
        raise EtudeError(f"{_relative(path)} n'existe pas : aucune étude « {nom} ».")
    raw = _read(path)
    unknown = set(raw) - FIELDS
    missing = {"nom", "titre", "texte", "preenregistrement", "cadre",
               "millesime_entreprises", "scenarios"} - set(raw)
    if unknown or missing:
        raise EtudeError(f"{nom} : champs inconnus {sorted(unknown)}, manquants "
                         f"{sorted(missing)}.")
    if raw["nom"] != nom:
        raise EtudeError(f"{_relative(path)} nomme l'étude « {raw['nom']} ».")
    if raw["texte"] not in TEXTES:
        raise EtudeError(f"{nom} : texte « {raw['texte']} » inconnu ({sorted(TEXTES)}).")
    if (raw["texte"] == "programme") != ("programme" in raw):
        raise EtudeError(f"{nom} : une étude de programme nomme son programme, et elle "
                         f"seule (D-328).")
    if not re.fullmatch(r"D-\d+", raw["preenregistrement"]):
        raise EtudeError(f"{nom} : « {raw['preenregistrement']} » n'est pas une D-entrée.")
    try:
        volets = tuple(Volet(**v) for v in raw["scenarios"])
    except TypeError as error:
        raise EtudeError(f"{nom} : un scénario mal dit : {error}") from error
    if not volets or len({v.scenario for v in volets}) != len(volets):
        raise EtudeError(f"{nom} : des scénarios, chacun une fois.")
    if "programme" in raw:
        from impots import programmes as pg

        try:
            programme = pg.charger(raw["programme"])
        except Exception as error:
            raise EtudeError(f"{nom} : le programme « {raw['programme']} » ne se lit pas : "
                             f"{error}") from error
        if not programme.chiffrees():
            raise EtudeError(f"{nom} : « {raw['programme']} » n'a aucune mesure chiffrée, "
                             f"rien à étudier.")
        if [v.scenario for v in volets] != [scenario_du_programme(raw["programme"])]:
            raise EtudeError(f"{nom} : une étude de programme a un scénario, sa part "
                             f"chiffrée, « {scenario_du_programme(raw['programme'])} ».")
    return Etude(nom=nom, titre=raw["titre"], texte=raw["texte"],
                 preenregistrement=raw["preenregistrement"], volets=volets,
                 cadre=raw["cadre"], millesime_entreprises=raw["millesime_entreprises"],
                 page=ROOT / raw.get("page", f"docs/etudes/{nom}.md"),
                 rapports=ROOT / raw.get("rapports", f"reports/etudes/{nom}"),
                 programme=raw.get("programme"))


def scenario_du_programme(slug: str) -> str:
    """The scenario of a programme's priced part: every priced measure, households and
    firms together, as the programme gives them (D-328)."""
    return f"pres2027_{slug}_programme"


def definitions(directory: Path | None = None) -> list[Etude]:
    directory = directory or DEFINITIONS
    return [definition(p.stem, directory) for p in sorted(directory.glob("*.json"))]


def replace(study: Etude, **changes: Any) -> Etude:
    return dataclasses.replace(study, **changes)
