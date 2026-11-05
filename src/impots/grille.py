"""La grille des curseurs (but 15, D-343, D-344).

Un curseur fait varier UN champ de réforme, la loi intacte autour ; une mesure est une
combinaison de curseurs. Chaque point de la grille est une passe de première année
(2026, population vieillie à elle, la convention des plages et de `POST /predictif/simulate`),
avec comportements et impulsions : il écrit son coût par couche, ses déciles et ce que
`rejouer` lit pour refaire la dette reportée en part de PIB (`annuel.carried_payload`).
Le navigateur fait le reste (`site/explorer.js`).

LA DÉFINITION est `etudes/grille/grille.json`, préenregistrée (D-344) : les curseurs, leur
forme, leur loi, les paires dont le terme croisé est mesuré. LES RAPPORTS sont sous
`reports/grille/`, un fichier par point, écrits par `impots grille lancer`, une passe par
processus, sur un commit propre qui porte le préenregistrement et qu'une branche distante
porte.

LE POINT « LOI » de chaque curseur est la loi : son coût doit valoir 0 € à l'euro, et
`compiler` le refuse sinon. C'est le contrôle gratuit de l'audit (§ 4.2) : une greffe qui
toucherait autre chose que son champ se verrait là.

UN CURSEUR λ (un article du PLF ou du PLFSS) donne à chaque champ numérique de l'article
loi + λ (article − loi), de λ = 0 (la loi) à λ = 2 ; λ = 1 est l'article. La loi est lue
dans le système d'OpenFisca au 1er janvier de l'année du scénario ; une revalorisation
vaut 1 en loi ; la contribution des grandes entreprises est nulle en loi en 2027, son taux
est donc λ fois celui de l'article.
"""

from __future__ import annotations

import dataclasses
import itertools
import json
import math
import subprocess
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFINITION = ROOT / "etudes" / "grille" / "grille.json"
RAPPORTS = ROOT / "reports" / "grille"
FORMES = ("taux", "seuil", "plafond", "lambda")
#: Points par forme (D-343).
NOMBRE = {"taux": 5, "seuil": 11, "plafond": 11, "lambda": 9}
LAMBDA = (0.0, 2.0)
#: Le point « loi » coûte 0 € à l'euro (D-344).
LOI_TOLERANCE_EUR = 1.0
REVALORISATIONS = ("ppa_revalorisation_avril", "al_revalorisation_octobre")


class GrilleError(ValueError):
    """La grille ne peut pas être lue, chiffrée ou compilée comme demandé."""


# --------------------------------------------------------------------------- #
# les curseurs
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Curseur:
    id: str
    titre: str
    forme: str
    etudes: tuple[str, ...]
    champ: str | None = None
    min: float | None = None
    max: float | None = None
    loi: float | None = None
    contexte: Mapping[str, str] | None = None
    article: str | None = None

    def __post_init__(self) -> None:
        if self.forme not in FORMES:
            raise GrilleError(f"{self.id} : forme « {self.forme} » inconnue ({FORMES})")
        if self.forme == "lambda":
            if not self.article or self.champ is not None:
                raise GrilleError(f"{self.id} : un curseur λ nomme un article, et aucun champ")
        else:
            if not self.champ or None in (self.min, self.max, self.loi):
                raise GrilleError(f"{self.id} : champ, min, max et loi sont requis")
            if not self.min < self.max or not self.min <= self.loi <= self.max:
                raise GrilleError(f"{self.id} : la loi {self.loi} hors de [{self.min} ; "
                                  f"{self.max}], ou une plage vide")

    @property
    def bornes(self) -> tuple[float, float]:
        return LAMBDA if self.forme == "lambda" else (float(self.min), float(self.max))

    @property
    def valeur_loi(self) -> float:
        return 0.0 if self.forme == "lambda" else float(self.loi)

    @property
    def geometrique(self) -> bool:
        low, high = self.bornes
        return self.forme == "plafond" and low > 0 and high / low > 10

    @property
    def lointain(self) -> float:
        """Le bout de la plage le plus loin de la loi : celui des paires."""
        low, high = self.bornes
        return low if abs(low - self.valeur_loi) > abs(high - self.valeur_loi) else high

    def valeurs(self) -> list[float]:
        """Les points de la grille, la loi comprise (D-343)."""
        low, high = self.bornes
        n = NOMBRE[self.forme]
        if self.geometrique:
            values = [low * (high / low) ** (k / (n - 1)) for k in range(n)]
        else:
            values = [low + (high - low) * k / (n - 1) for k in range(n)]
        values[0], values[-1] = low, high
        if not any(math.isclose(v, self.valeur_loi, rel_tol=0, abs_tol=1e-12)
                   for v in values):
            raise GrilleError(f"{self.id} : la loi {self.valeur_loi} n'est pas un point de "
                              f"la grille {values}")
        return values

    def temoin(self) -> float:
        """Le point témoin : le milieu de l'intervalle de la grille qui touche la loi, au
        milieu géométrique pour une grille géométrique (D-344)."""
        values = self.valeurs()
        k = min(range(len(values)), key=lambda i: abs(values[i] - self.valeur_loi))
        j = k + 1 if k + 1 < len(values) else k - 1
        a, b = sorted((values[k], values[j]))
        return math.sqrt(a * b) if self.geometrique else (a + b) / 2.0

    @property
    def interpolation(self) -> str:
        return "lineaire" if self.forme == "taux" else "pchip"


def charger(path: Path | None = None) -> tuple[dict[str, Curseur], list[tuple[str, str]],
                                               dict[str, Any]]:
    raw = json.loads((path or DEFINITION).read_text(encoding="utf-8"))
    curseurs: dict[str, Curseur] = {}
    for item in raw["curseurs"]:
        known = {f.name for f in dataclasses.fields(Curseur)}
        unknown = set(item) - known
        if unknown:
            raise GrilleError(f"{item.get('id')} : champs inconnus {sorted(unknown)}")
        c = Curseur(**{**item, "etudes": tuple(item["etudes"])})
        if c.id in curseurs:
            raise GrilleError(f"curseur « {c.id} » écrit deux fois")
        curseurs[c.id] = c
    paires = [tuple(p) for p in raw["paires"]]
    for a, b in paires:
        if a not in curseurs or b not in curseurs or a == b:
            raise GrilleError(f"paire {a} × {b} : curseur inconnu, ou le même deux fois")
    return curseurs, paires, raw


# --------------------------------------------------------------------------- #
# la réforme d'un point
# --------------------------------------------------------------------------- #
def _poser(fragment: dict[str, Any], champ: str, value: Any) -> None:
    """Écrire `value` au chemin pointé `champ` (un entier indexe une liste)."""
    keys = champ.split(".")
    node: Any = fragment
    for key, nxt in itertools.pairwise(keys):
        if isinstance(node, list):
            node = node[int(key)]
            continue
        if key not in node:
            node[key] = [] if nxt.isdigit() else {}
        node = node[key]
    last = keys[-1]
    if isinstance(node, list):
        node[int(last)] = value
    else:
        node[last] = value


def _firm_fields() -> set[str]:
    from impots.entreprises.reforms import FirmReformSpec

    return set(FirmReformSpec.model_fields)


def _contexte(curseur: Curseur) -> dict[str, Any]:
    """Le fragment de la mesure dont le champ a besoin, restreint à sa clé de tête."""
    if not curseur.contexte:
        return {}
    from impots import programmes as pg

    p = pg.charger(curseur.contexte["programme"])
    m = next((x for x in p.chiffrees() if x.id == curseur.contexte["mesure"]), None)
    if m is None:
        raise GrilleError(f"{curseur.id} : mesure {curseur.contexte['mesure']} introuvable")
    head = curseur.champ.split(".")[0]
    return {head: json.loads(json.dumps(m.chiffrage.reforme[head]))}


def loi_menages(champ: str, annee: int) -> Any:
    """La valeur de loi d'un champ des ménages qu'un article porte, au 1er janvier."""
    if champ in REVALORISATIONS:
        return 1.0
    from impots.engine import reforms, system
    from impots.parameters import resolve

    parameters = system.baseline().parameters
    instant = f"{annee}-01-01"
    if champ == "ir_bareme":
        scale = resolve(parameters, reforms.PATH_BAREME)(instant)
        return [{"threshold": float(t), "rate": float(r)}
                for t, r in zip(scale.thresholds, scale.rates, strict=True)]
    if champ not in reforms.SCALAR_KNOBS:
        raise GrilleError(f"champ « {champ} » : sa loi n'est pas lisible ici (D-344)")
    return float(resolve(parameters, reforms.SCALAR_KNOBS[champ])(instant))


def _intensite(article: Any, loi: Any, lam: float) -> Any:
    if isinstance(article, list):
        if not isinstance(loi, list) or len(loi) != len(article):
            raise GrilleError("barème de l'article et de la loi de longueurs différentes")
        return [_intensite(a, b, lam) for a, b in zip(article, loi, strict=True)]
    if isinstance(article, dict):
        return {k: _intensite(v, loi[k], lam) for k, v in article.items()}
    return float(loi) + lam * (float(article) - float(loi))


def reformes(curseur: Curseur, valeur: float) -> tuple[dict[str, Any], dict[str, Any] | None,
                                                         int | None]:
    """(réforme des ménages, réforme des entreprises, année des entreprises) d'un point."""
    if curseur.forme == "lambda":
        from impots import scenarios

        s = scenarios.load(curseur.article)
        menages: dict[str, Any] = {}
        for champ, article in s.reform.model_dump(exclude_none=True, mode="json").items():
            menages[champ] = _intensite(article, loi_menages(champ, s.year), valeur)
        firm = None
        if s.firm_reform is not None:
            firm = s.firm_reform.model_dump(exclude_none=True, mode="json")
            if set(firm) - {"cebge_seuils_et_taux", "cebge_prorogation_largeur"}:
                raise GrilleError(f"{curseur.id} : champ d'entreprise sans loi lisible ici")
            # Nulle en loi en 2027 : son taux est λ fois celui de l'article (D-343).
            firm["cebge_seuils_et_taux"] = [
                {**row, "taux": valeur * row["taux"]} for row in firm["cebge_seuils_et_taux"]]
        return menages, firm, s.year
    fragment = _contexte(curseur)
    _poser(fragment, curseur.champ, valeur)
    firm_keys = _firm_fields()
    menages = {k: v for k, v in fragment.items() if k not in firm_keys}
    firm = {k: v for k, v in fragment.items() if k in firm_keys} or None
    return menages, firm, None


def combiner(*parts: tuple[dict[str, Any], dict[str, Any] | None, int | None]
             ) -> tuple[dict[str, Any], dict[str, Any] | None, int | None]:
    menages: dict[str, Any] = {}
    firm: dict[str, Any] = {}
    years = {y for _, _, y in parts if y is not None}
    if len(years) > 1:
        raise GrilleError(f"paire sur deux années d'entreprises {sorted(years)}")
    for m, f, _ in parts:
        for key, value in m.items():
            if key in menages and isinstance(value, dict):
                menages[key] = {**menages[key], **value}
            elif key in menages:
                raise GrilleError(f"paire : le champ « {key} » écrit deux fois")
            else:
                menages[key] = value
        firm.update(f or {})
    return menages, firm or None, (years.pop() if years else None)


# --------------------------------------------------------------------------- #
# le chiffrage d'un point
# --------------------------------------------------------------------------- #
def _jsonable(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if dataclasses.is_dataclass(value):
        return dataclasses.asdict(value)
    return value


def requete(menages: dict[str, Any], firm: dict[str, Any] | None) -> dict[str, Any]:
    from impots import etude

    cadre = etude.lire_cadre(charger()[2]["cadre"])
    return {**{k: cadre[k] for k in ("spending", "growth", "rate", "horizon", "theta",
                                     "uprating")},
            "behavioural": True, "macro": True, "persistence": cadre["persistance"],
            "reform": menages, "firm_reform": firm}


def chiffrer(menages: dict[str, Any], firm: dict[str, Any] | None,
             annee_entreprises: int | None) -> dict[str, Any]:
    """Une passe : le coût par couche, les déciles, la charge de `rejouer`, et le contrôle
    (Δb à θ et aux coins de la boîte, par la chaîne elle-même, sous la persistance lue)."""
    from impots import etude, service
    from impots.api.schemas import PredictifRequest
    from impots.dette import reference
    from impots.predictif import annuel, chaine, exploration
    from impots.predictif import theta as theta_module

    body = requete(menages, firm)
    absente = etude.dette_absente(body) if firm else None
    if absente is not None or (not menages and annee_entreprises is not None):
        return _entreprises_seules(firm, annee_entreprises, absente)
    request = PredictifRequest.model_validate(body)
    hyp = service.predictif_hypotheses(request)
    start = reference.start_from_accounts(chaine.START_YEAR)
    macro_store = service.predictif_macro_store()
    year = start.year + 1
    first = service.price_first_year(
        service.first_year_request(request.reform, year, True), uprating=hyp.uprating,
        macro=True, **service.firm_part(request.firm_reform, growth=hyp.growth))
    priced = exploration.Priced(
        cost=float(first.cost), inputs=first.inputs, impulse=first.impulse,
        uncovered=dict(first.uncovered), layers=getattr(first, "layers", None),
        behaviour_asked=getattr(first, "behaviour_asked", False))
    payload = annuel.carried_payload(
        start, priced, request.reform, spending=hyp.spending, growth=hyp.growth,
        rate=hyp.rate, theta=hyp.theta, horizon=request.horizon, store=hyp.store,
        macro_store=macro_store)
    keys = list(payload["rejeu"]["box_rows"])

    def delta(at: Any) -> list[float]:
        return [float(x) for x in exploration.trajectory(
            at, priced, request.reform, start=start, horizon=request.horizon,
            spending=hyp.spending, growth=hyp.growth, rate=hyp.rate, store=hyp.store,
            macro_store=macro_store, persistence=request.persistence).delta]

    corners = theta_module.corners(keys, hyp.theta)
    layers = getattr(first, "layers", None) or {"menages": float(first.cost),
                                                "entreprises": 0.0}
    return {"cout": {"total": float(first.cost), **{k: float(v) for k, v in layers.items()}},
            "deciles": [_jsonable(d) for d in (getattr(first, "deciles", None) or [])],
            "rejeu": payload, "dette_absente": None,
            "controle": {"persistence": request.persistence, "theta": delta(hyp.theta),
                         "coins": [[exploration.corner_label(c, keys), delta(c)[-1]]
                                   for c in corners]}}


def _entreprises_seules(firm: dict[str, Any] | None, annee: int | None,
                        absente: str | None) -> dict[str, Any]:
    """Une loi d'entreprise que le report ne voit pas (D-254), ou bornée à son année : le
    coût de l'année par le simulateur des entreprises, la dette dite absente."""
    from fastapi.testclient import TestClient

    from impots.api.main import app
    from impots.predictif.chaine import START_YEAR

    year = annee or START_YEAR + 1
    reply = TestClient(app).post("/entreprises/simulate", json={"reform": firm, "year": year})
    if reply.status_code != 200:
        raise GrilleError(f"/entreprises/simulate a rendu {reply.status_code} : "
                          f"{reply.text[:300]}")
    cost = float(reply.json()["reform_cost"])
    return {"cout": {"total": cost, "menages": 0.0, "entreprises": cost}, "deciles": [],
            "rejeu": None, "annee_entreprises": year,
            "dette_absente": absente or (f"une mesure bornée à {year} : la première année "
                                         f"reportée n'en dit rien (D-288)"),
            "controle": None}


# --------------------------------------------------------------------------- #
# les rapports
# --------------------------------------------------------------------------- #
def taches(curseurs: dict[str, Curseur], paires: list[tuple[str, str]]) -> list[tuple]:
    """Toutes les passes : (nom du rapport, genre, curseur(s), index ou rôle)."""
    out: list[tuple] = []
    for c in curseurs.values():
        for k, _ in enumerate(c.valeurs()):
            out.append((f"{c.id}/p{k:02d}.json", "point", c.id, k))
        out.append((f"{c.id}/temoin.json", "temoin", c.id, None))
    for a, b in paires:
        out.append((f"paires/{a}__{b}.json", "paire", (a, b), None))
    return out


def ecrire(genre: str, cible: Any, index: int | None, *, where: str,
           sortie: Path | None = None) -> Path:
    from impots.predictif import recherche

    curseurs, _, _ = charger()
    if genre == "paire":
        a, b = (curseurs[x] for x in cible)
        parts = [reformes(a, a.lointain), reformes(b, b.lointain)]
        menages, firm, year = combiner(*parts)
        valeurs = {a.id: a.lointain, b.id: b.lointain}
        name = f"paires/{a.id}__{b.id}.json"
    else:
        c = curseurs[cible]
        valeur = c.temoin() if genre == "temoin" else c.valeurs()[index]
        menages, firm, year = reformes(c, valeur)
        valeurs = {c.id: valeur}
        name = f"{c.id}/{'temoin' if genre == 'temoin' else f'p{index:02d}'}.json"
    commit, dirty = recherche.code_state(ROOT)
    report = {"genre": genre, "valeurs": valeurs,
              "request": {"reform": menages, "firm_reform": firm,
                          "annee_entreprises": year},
              **chiffrer(menages, firm, year),
              "computed": date.today().isoformat(), "commit": commit, "dirty": dirty,
              "where": where}
    path = sortie or RAPPORTS / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def lancer(where: str) -> int:
    """Toutes les passes de la grille, une par processus, une après l'autre. Reprend après
    les rapports déjà écrits sur ce commit ; refuse un arbre sale, un préenregistrement
    absent du commit ou un commit qu'aucune branche distante ne porte (D-338, D-344)."""
    from impots.predictif import recherche

    curseurs, paires, raw = charger()
    commit, dirty = recherche.code_state(ROOT)
    if dirty or _git("status", "--porcelain", "--", "etudes", "scripts"):
        print("grille : modifications non commitées dans src, etudes ou scripts.",
              file=sys.stderr)
        return 1
    entry = raw["preenregistrement"]
    if f"## {entry} " not in _git("show", "HEAD:docs/DECISIONS.md"):
        print(f"grille : {entry} n'est pas dans docs/DECISIONS.md au commit.", file=sys.stderr)
        return 1
    if not _git("branch", "-r", "--contains", "HEAD").strip():
        print("grille : aucune branche distante ne porte le commit.", file=sys.stderr)
        return 1
    for name, genre, cible, index in taches(curseurs, paires):
        path = RAPPORTS / name
        if path.exists():
            there = json.loads(path.read_text(encoding="utf-8"))
            if there.get("commit") == commit:
                continue
            print(f"grille : {name} est d'un autre commit ({there.get('commit', '?')[:7]}) ;"
                  f" un rapport n'est pas écrasé en silence.", file=sys.stderr)
            return 1
        args = [sys.executable, "-m", "impots.population.cli", "grille", "point", genre,
                ",".join(cible) if isinstance(cible, tuple) else cible,
                str(index if index is not None else -1), "--ou", where]
        print(f"== {name}", flush=True)
        done = subprocess.run(args, cwd=ROOT, env=_env())
        if done.returncode != 0:
            print(f"{name} : la passe a rendu {done.returncode}, les suivantes ne tournent "
                  f"pas.", file=sys.stderr)
            return done.returncode
    return 0


def _env() -> dict[str, str]:
    import os

    return {**os.environ, "PYTHONPATH": str(ROOT / "src"), "IMPOTS_AUTH": "aucune",
            "IMPOTS_FIRM_VINTAGE": "2023"}


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True,
                          check=True).stdout


# --------------------------------------------------------------------------- #
# l'interpolation, jumelle de `site/rejeu.js`
# --------------------------------------------------------------------------- #
def _sign(v: float) -> int:
    return (v > 0) - (v < 0)


def _pchip_slopes(x: list[float], y: list[float]) -> list[float]:
    n = len(x)
    h = [x[k + 1] - x[k] for k in range(n - 1)]
    d = [(y[k + 1] - y[k]) / h[k] for k in range(n - 1)]
    m = [0.0] * n
    if n == 2:
        return [d[0], d[0]]
    for k in range(1, n - 1):
        if d[k - 1] * d[k] > 0:
            w1, w2 = 2 * h[k] + h[k - 1], h[k] + 2 * h[k - 1]
            m[k] = (w1 + w2) / (w1 / d[k - 1] + w2 / d[k])

    def end(h0: float, h1: float, d0: float, d1: float) -> float:
        s = ((2 * h0 + h1) * d0 - h0 * d1) / (h0 + h1)
        if _sign(s) != _sign(d0):
            return 0.0
        if _sign(d0) != _sign(d1) and abs(s) > abs(3 * d0):
            return 3 * d0
        return s

    m[0] = end(h[0], h[1], d[0], d[1])
    m[n - 1] = end(h[n - 2], h[n - 3], d[n - 2], d[n - 3])
    return m


def interpoler(xs: list[float], ys: list[float], x: float, methode: str) -> float:
    """La valeur interpolée en x : linéaire, ou PCHIP de Fritsch et Carlson."""
    if x <= xs[0]:
        return ys[0]
    if x >= xs[-1]:
        return ys[-1]
    k = 0
    while x > xs[k + 1]:
        k += 1
    if x == xs[k]:
        return ys[k]
    t = (x - xs[k]) / (xs[k + 1] - xs[k])
    if methode == "lineaire":
        return ys[k] + t * (ys[k + 1] - ys[k])
    m = _pchip_slopes(xs, ys)
    h = xs[k + 1] - xs[k]
    return ((2 * t ** 3 - 3 * t ** 2 + 1) * ys[k] + (t ** 3 - 2 * t ** 2 + t) * h * m[k]
            + (-2 * t ** 3 + 3 * t ** 2) * ys[k + 1] + (t ** 3 - t ** 2) * h * m[k + 1])


def abscisse(curseur: Curseur, valeur: float) -> float:
    """La coordonnée où l'on interpole : le logarithme pour une grille géométrique."""
    return math.log(valeur) if curseur.geometrique else valeur


# --------------------------------------------------------------------------- #
# la forme linéaire des canaux : ce qui s'additionne entre curseurs et s'interpole
# --------------------------------------------------------------------------- #
def lineaire(canaux: Mapping[str, Any] | None) -> dict[str, Any] | None:
    """Les statistiques des canaux sous une forme où les recettes sont LINÉAIRES en chaque
    statistique, à valeurs des lignes données : des sommes de produits, que l'on peut
    sommer d'un curseur à l'autre et interpoler entre deux points. Les recettes qu'en tire
    `site/rejeu.js` (`receiptsLin`) sont celles de `rejouer.receipts`, l'algèbre près."""
    if not canaux:
        return None
    out: dict[str, Any] = {}
    if "c1_eti" in canaux:
        out["c1"] = {"A_bas": canaux["c1_eti"]["A_bas"], "A_haut": canaux["c1_eti"]["A_haut"]}
    if "c7_labour_supply" in canaux:
        out["c7"] = dict(canaux["c7_labour_supply"]["S"])
    if "c10_dividendes" in canaux:
        c10 = canaux["c10_dividendes"]
        base = c10["delta_log"] * c10["B"]
        out["c10"] = {"induit": c10["tau1"] * base, "deplace": c10["lost_per_eur"] * base}
    if "c11_autofinancement" in canaux:
        c11, c2 = canaux["c11_autofinancement"], canaux["c2_employment"]
        out["c11"] = {"ancre": c2["anchor"] * c11["value_per_job"],
                      "queue": c2["tail"] * c11["value_per_job"],
                      "tresor": c11["tresor_eco"] * c11["cut"]}
    return out


def _feuilles(tree: Any, prefix: str = "") -> dict[str, float]:
    if isinstance(tree, Mapping):
        out: dict[str, float] = {}
        for key, value in tree.items():
            out.update(_feuilles(value, f"{prefix}{key}."))
        return out
    return {prefix[:-1]: float(tree)}


def _arbre(leaves: Mapping[str, float]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for path, value in leaves.items():
        node = out
        *heads, last = path.split(".")
        for head in heads:
            node = node.setdefault(head, {})
        node[last] = value
    return out


def part(report: Mapping[str, Any]) -> dict[str, Any] | None:
    """Ce que le navigateur lit d'un point : coût, impulsions, canaux sous forme linéaire."""
    if report["rejeu"] is None:
        return None
    stats = report["rejeu"]["years"][0]["statistiques"]["vieillie"]
    return {"cost": float(report["rejeu"]["years"][0]["mechanical_aged_eur"]),
            "impulses": dict(stats["impulses"] or {}), "canaux": lineaire(stats["canaux"])}


def interpoler_part(curseur: Curseur, points: list[Mapping[str, Any]], x: float
                    ) -> dict[str, Any]:
    """La part d'un curseur en x, chaque feuille interpolée, une feuille absente d'un point
    valant zéro en ce point (le point « loi » n'a ni impulsion ni canal)."""
    xs = [abscisse(curseur, p["x"]) for p in points]
    leaves = [_feuilles(p["part"]) for p in points]
    keys = sorted({k for leaf in leaves for k in leaf})
    at = abscisse(curseur, x)
    return _arbre({k: interpoler(xs, [leaf.get(k, 0.0) for leaf in leaves], at,
                                 curseur.interpolation) for k in keys})


# --------------------------------------------------------------------------- #
# le témoin : l'erreur d'interpolation, contre la tolérance préenregistrée (D-344)
# --------------------------------------------------------------------------- #
#: La tolérance d'interpolation, par forme, en part de l'amplitude du curseur (le plus grand
#: |coût| de ses points, ou le plus grand |Δb₂₀₃₅| à θ½), avec un plancher absolu. Fixée par
#: D-344 avant le premier calcul ; elle ne bouge plus.
TOLERANCE = {"taux": 0.005, "seuil": 0.03, "plafond": 0.03, "lambda": 0.02}
PLANCHER_COUT_EUR = 1e6
PLANCHER_DETTE = 0.00002


def _lire(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def points_de(curseur: Curseur, rapports: Path | None = None) -> list[dict[str, Any]]:
    """Les points écrits d'un curseur, dans l'ordre de sa grille, avec leur part."""
    folder = (rapports or RAPPORTS) / curseur.id
    out = []
    for k, x in enumerate(curseur.valeurs()):
        report = _lire(folder / f"p{k:02d}.json")
        out.append({"x": x, "report": report, "part": part(report)})
    return out


def dette_theta(report: Mapping[str, Any]) -> float | None:
    """Δb à la dernière année, à θ½, sous la persistance lue : le contrôle de la chaîne."""
    return None if report["controle"] is None else float(report["controle"]["theta"][-1])


def ecart_temoin(curseur: Curseur, rapports: Path | None = None) -> dict[str, Any]:
    """Le coût et Δb₂₀₃₅ interpolés au témoin contre ceux de sa passe, et la tolérance."""
    from impots.predictif import rejouer

    points = points_de(curseur, rapports)
    witness = _lire((rapports or RAPPORTS) / curseur.id / "temoin.json")
    x = curseur.temoin()
    xs = [abscisse(curseur, p["x"]) for p in points]
    costs = [p["report"]["cout"]["total"] for p in points]
    cost = interpoler(xs, costs, abscisse(curseur, x), curseur.interpolation)
    share = TOLERANCE[curseur.forme]
    amplitude = max(abs(c) for c in costs)
    out: dict[str, Any] = {
        "curseur": curseur.id, "x": x, "cout_calcule": witness["cout"]["total"],
        "cout_interpole": cost, "ecart_cout": cost - witness["cout"]["total"],
        "tolerance_cout": max(PLANCHER_COUT_EUR, share * amplitude)}
    out["cout_tenu"] = abs(out["ecart_cout"]) <= out["tolerance_cout"]
    if witness["rejeu"] is None or any(p["part"] is None for p in points):
        out.update(dette_calculee=None, dette_interpolee=None, ecart_dette=None,
                   tolerance_dette=None, dette_tenue=None)
        return out
    interpolated = interpoler_part(curseur, points, x)
    rejeu = witness["rejeu"]["rejeu"]
    rows = list(rejeu["box_rows"])
    values, z = rejouer.theta_values(witness["rejeu"], {k: 0.5 for k in rows})
    debt = _chemin_parts(rejeu, int(witness["rejeu"]["horizon"]), [interpolated], values, z,
                         rejouer.READ)[-1]
    debts = [dette_theta(p["report"]) for p in points]
    out.update(dette_calculee=dette_theta(witness), dette_interpolee=debt,
               ecart_dette=debt - dette_theta(witness),
               tolerance_dette=max(PLANCHER_DETTE, share * max(abs(d) for d in debts)))
    out["dette_tenue"] = abs(out["ecart_dette"]) <= out["tolerance_dette"]
    return out


def recettes_lineaires(mechanical: float, lin: Mapping[str, Any] | None,
                       values: Mapping[str, Any]) -> float:
    """`rejouer.receipts` sur la forme linéaire des canaux : `receiptsLin` de rejeu.js."""
    if not lin:
        return mechanical
    total = mechanical
    if "c1" in lin:
        total += (values["eti_all"] * lin["c1"]["A_bas"]
                  + values["eti_top_decile"] * lin["c1"]["A_haut"])
    if "c7" in lin:
        for key, s in lin["c7"].items():
            total += values[key] * s
    if "c10" in lin:
        share = values["dividend_share_firm_owners"]
        owners = values["dividend_elasticity_firm_owners"]
        elasticity = share * owners + (1.0 - share) * values["dividend_elasticity_other_holders"]
        total += (elasticity * lin["c10"]["induit"] - values["dividend_wage_shift_firm_owners"]
                  * share * owners * lin["c10"]["deplace"])
    if "c11" in lin:
        weight = values["autofinancement_poids_tresor_eco"]
        total += ((1.0 - weight) * (values["employment_elasticity_smic"] * lin["c11"]["ancre"]
                                    + lin["c11"]["queue"]) + weight * lin["c11"]["tresor"])
    return total


def _chemin_parts(rejeu: Mapping[str, Any], horizon: int, parts: list[Mapping[str, Any]],
                  values: Mapping[str, Any], z: Any, persistence: str) -> list[float]:
    """Δb par année d'une combinaison de parts reportées : `chemin` de rejeu.js."""
    from impots.predictif import rejouer

    gdp, refs, nominal = rejouer.reference_path(rejeu, rejeu["start"], horizon)
    first = 0.0
    impulse: dict[str, float] = {}
    for p in parts:
        r = (recettes_lineaires(-p["cost"], p["canaux"], values)
             if rejeu["behavioural"] and p["canaux"] is not None else -p["cost"])
        first += r / gdp[0]
        for i, v in (p["impulses"] or {}).items():
            impulse[i] = impulse.get(i, 0.0) + v
    impulses = [{i: v / gdp[0] * y for i, v in impulse.items()} for y in gdp]
    if rejeu["looped"]:
        gap, phi = rejouer.loop(impulses, gdp, rejeu["macro"], z, persistence)
    else:
        gap = phi = [0.0] * horizon
    debt, delta = 0.0, []
    marginal = rejeu["cadre"]["taux"]["marginal"]
    for k in range(horizon):
        debt = debt * (1.0 + marginal) / (1.0 + nominal) - (first + phi[k])
        delta.append((refs[k] + debt) / (1.0 + gap[k]) - refs[k])
    return delta
