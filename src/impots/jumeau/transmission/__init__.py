"""La carte des effets (but 26, volet `carte`, D-471, D-472) : la fiche de transmission.

UNE FICHE PAR MESURE, un YAML, `transmission/<candidat>/<mesure>.yaml`. Elle dit comment
la mesure se fait et ce qu'elle déclenche, avant tout calcul : le levier, qui paie ou
reçoit d'abord, qui paie au bout, le financement annoncé, les canaux qu'elle ouvre, ses
hypothèses et son montant. Le jumeau la lit (`entree`) : une mesure chiffrée y entre par
son rapport (`Mesure.depuis_rapport`, par la `Session` du navigateur) ; une mesure dont le
candidat énonce un montant y entre comme loi hypothétique (`Mesure.hypothese`), et le
dit ; les autres n'y entrent pas, et la fiche dit ce qui manque.

LE SCHÉMA (version 1). Les sept clés de D-471, plus l'en-tête :

* en-tête : `schema` (1), `mesure` (l'identifiant de `programmes/<candidat>.json`),
  `candidat`, `libelle`, `sorte` et `source` (la citation du programme, son adresse, sa
  date). `sorte` est l'une de :

  - `chiffree` : un rapport d'étude commité porte son coût (`montant.origine: rapport`) ;
  - `hypothese` : le candidat énonce un montant annuel (`declare` du programme), qui
    entre comme loi hypothétique (`montant.origine: hypothese`) ;
  - `parametre` : un paramètre est énoncé (un taux, un âge, un seuil), sans montant ni
    passe : la fiche dit l'assiette qui manque (`montant.origine: aucun`) ;
  - `sans_choc` : une intention, une règle budgétaire, une trajectoire : aucun choc
    (`montant.origine: aucun`).

* `levier` : {`texte` (le texte de droit ou le dispositif touché), `parametre` (le bouton
  du moteur, ou celui que le programme énonce), `valeur`, `enonce` (le paramètre du
  programme, tel quel), `couche` (menages | entreprises, pour une mesure chiffrée)}.
* `payeurs` : une liste de {`qui`, `sens` (paie | recoit), `par` (l'instrument ou
  l'assiette), `note`}. `qui` est l'un de `PAYEURS` : `menages` (les cellules du jumeau ;
  `par`, une variable des cellules quand elle existe, sert de clé par décile),
  `entreprises` (`par`, un impôt du bloc des entreprises ou un instrument du registre),
  `apu:etat`, `apu:secu:<branche>` (maladie, at_mp, vieillesse, famille, autonomie,
  chomage, retraite_complementaire), `apu:apul` (les collectivités), `apu:odac`,
  `reste_du_monde`.
* `incidence` : une liste de {`horizon` (immediat | court | long), `qui`, `texte`,
  `source`} : qui paie au bout. `source` est une référence, ou « non sourcée ».
* `financement` : {`annonce` (le texte du candidat, ou null), `source` (sa citation, ou
  null), `chiffre` (le candidat chiffre-t-il ce financement), `note`}.
* `canaux` : les noms de `jumeau/canaux.py` que la mesure ouvre. Un nom absent du
  registre est un canal attendu d'un autre volet (`CANAUX_ATTENDUS`) : la fiche le garde,
  `valider` le dit, il n'est jamais lu comme ouvert.
* `hypotheses` : une liste de {`texte`, `valeur` (facultative), `source`} ; chaque
  hypothèse a sa source, ou « non sourcée ».
* `montant` : {`origine` (rapport | hypothese | aucun) ; pour un rapport : `scenario`,
  `rapport` ; pour une hypothèse : `annonce` (le montant du candidat, Md€ par an, son sens,
  son horizon, sa source), `chocs` (catégories du compte des APU, Md€ par an en régime,
  signe du moteur : un coût est positif), `profil` (constant | rampe | calendrier : les
  points {année : Md€} que le candidat donne, linéaire entre eux), `debut`, `plein`,
  `fin`, `instrument` (la variante de Mésange la plus proche, ou null), `menages_par`,
  `entreprises_par`, `inclus_dans` (une autre mesure qui le compte déjà) ; pour aucun :
  `manque`}.

LES DONNÉES CRITIQUES (but 27, volet `fiches`, D-504). Deux clés facultatives, écrites
mesure par mesure dans `programmes/fiches/<candidat>.yaml` (et non tirées d'un gabarit) :

* `assiette` : {`texte`, `montant_md` (Md€, ou null), `annee`, `source`}, ou une liste :
  ce sur quoi la mesure porte et son montant de 2024 à 2026, lu dans une statistique
  publique (PLF, LFSS, comptes de la Sécurité sociale, Insee, DGFiP, Drees). Un montant
  d'assiette a toujours une source, jamais « non sourcée » ;
* `calendrier` : {`texte`, `source`} : quand la mesure entre en vigueur, selon le candidat.

Un payeur peut dire sa `part` (de 0 à 1) ou, dans `note`, son montant lu dans le rapport.
Le montant d'une hypothèse est celui du candidat (`annonce.par` : `candidat`, par défaut)
ou, quand le candidat donne un paramètre et qu'une assiette publiée le permet, l'assiette
fois le paramètre (`annonce.par` : `calcul`, et `annonce.calcul` : le calcul écrit) ;
la fiche porte alors son `assiette`.

CE QUE LE LECTEUR NE FAIT PAS. Il ne chiffre rien : une fiche ne porte jamais un nombre que
ni un rapport, ni le candidat, ni une assiette publiée (le calcul écrit) ne donne. Une
montée en charge, une clé de répartition, une variante de Mésange approchée sont des
hypothèses déclarées, dites dans la fiche.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path
from typing import Any

import yaml

from impots.jumeau.canaux import CANAUX, INSTRUMENTS
from impots.jumeau.champs import SIGNAUX_ENTREPRISES

ICI = Path(__file__).resolve().parent
SCHEMA = 1

SORTES = ("chiffree", "hypothese", "parametre", "sans_choc")
ORIGINES = {"chiffree": "rapport", "hypothese": "hypothese", "parametre": "aucun",
            "sans_choc": "aucun"}
CLES = ("schema", "mesure", "candidat", "libelle", "sorte", "source", "levier",
        "payeurs", "incidence", "financement", "canaux", "hypotheses", "montant")
#: Les clés facultatives des données critiques (D-504).
FACULTATIVES = ("assiette", "calendrier")
HORIZONS = ("immediat", "court", "long")
SENS = ("paie", "recoit")
NON_SOURCEE = "non sourcée"

#: Les branches de la Sécurité sociale (au sens large des ASSO : l'Unédic et les régimes
#: complémentaires en sont, Insee, comptes nationaux, sous-secteur S1314).
BRANCHES = ("maladie", "at_mp", "vieillesse", "famille", "autonomie", "chomage",
            "retraite_complementaire")
PAYEURS = frozenset({"menages", "entreprises", "apu:etat", "apu:apul", "apu:odac",
                     "reste_du_monde", *(f"apu:secu:{b}" for b in BRANCHES)})

#: Les impôts du bloc des entreprises (`champs.SIGNAUX_ENTREPRISES`) et les instruments
#: du registre ; plus ce que paient ou reçoivent les entreprises hors prélèvements.
IMPOTS_ENTREPRISES = frozenset(i for (_, _, ins) in SIGNAUX_ENTREPRISES.values()
                               for i in ins)
PAR_ENTREPRISES = frozenset({*IMPOTS_ENTREPRISES, *INSTRUMENTS, "aides_publiques",
                             "masse_salariale", "prix", "chiffre_affaires", "dividendes",
                             "commande_publique", "autre"})

#: Les catégories du compte des APU qu'un choc déclaré peut toucher (`mesures.CATEGORIES`),
#: relues ici sans importer les mesures (qui importent la chaîne prédictive).
def _categories() -> tuple[str, ...]:
    from impots.jumeau.mesures import CATEGORIES

    return CATEGORIES


#: Les canaux que la carte cite et qu'aucun bloc n'a encore enregistrés dans
#: `jumeau/canaux.py` (D-471). À la jonction (D-487), les noms que `travail` et
#: `financement` ont enregistrés remplacent ceux que la carte proposait :
#: `smic_diffusion`, `incidence_cotisations`, `financement_sous_secteurs`,
#: `compensation_exonerations` et `financement_annonce` gardent leur nom ;
#: `allegements_smic` devient `cout_travail_smic` dans les fiches du Smic (le bloc
#: `travail` y porte la loi, la RGDU et le coût par tranche) et `incidence_cotisations`
#: ailleurs (une exonération change une cotisation employeur, dont le bloc porte
#: l'incidence). Restent attendus ceux qu'aucun volet n'a ouverts. Tant qu'il n'est pas
#: enregistré, un canal n'est pas ouvert.
CANAUX_ATTENDUS: dict[str, tuple[str, str]] = {
    "cout_travail_tranche": ("travail", "le coût du travail et l'emploi par tranche de "
                             "salaire hors d'une hausse du Smic : `travail.emploi_par_"
                             "tranche` le calcule en regard, hors de l'état (D-479)"),
    "offre_travail": ("travail", "l'offre de travail selon le salaire net (marges "
                      "intensive et extensive) : non faite au but 26"),
    "patrimoine_menages": ("aucun volet", "le patrimoine des ménages et sa transmission : "
                           "la population n'en porte pas"),
    "droits_retraite": ("aucun volet", "les âges, les durées et les pensions : la "
                        "population ne vieillit pas en âge"),
}


class TransmissionError(ValueError):
    """Une fiche qui ne se lit pas, ou qui ne peut pas entrer dans le jumeau."""


# --------------------------------------------------------------------------- #
# lire, valider
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Fiche:
    donnees: Mapping[str, Any]
    chemin: Path | None = None

    def __getitem__(self, cle: str) -> Any:
        return self.donnees[cle]

    @property
    def cle(self) -> str:
        return f"{self.donnees['candidat']}/{self.donnees['mesure']}"

    @property
    def sorte(self) -> str:
        return self.donnees["sorte"]

    @property
    def canaux_ouverts(self) -> tuple[str, ...]:
        return tuple(c for c in self.donnees.get("canaux") or () if c in CANAUX)

    @property
    def canaux_attendus(self) -> tuple[str, ...]:
        return tuple(c for c in self.donnees.get("canaux") or () if c not in CANAUX)


def charger(chemin: Path | str) -> Fiche:
    """Une fiche, lue et validée : une fiche invalide est refusée, ses défauts nommés."""
    chemin = Path(chemin)
    d = yaml.safe_load(chemin.read_text(encoding="utf-8"))
    if not isinstance(d, dict):
        raise TransmissionError(f"{chemin} : pas une fiche")
    defauts = valider(d)
    if defauts:
        raise TransmissionError(f"{chemin} : " + " ; ".join(defauts))
    return Fiche(d, chemin)


def fiches(candidat: str | None = None, racine: Path = ICI) -> list[Fiche]:
    """Les fiches d'un candidat (ou toutes), dans l'ordre des noms."""
    motif = f"{candidat}/*.yaml" if candidat else "*/*.yaml"
    return [charger(p) for p in sorted(racine.glob(motif))]


def fiche(candidat: str, mesure: str, racine: Path = ICI) -> Fiche:
    return charger(racine / candidat / f"{mesure}.yaml")


def _source(s: Any) -> bool:
    return isinstance(s, str) and bool(s.strip())


def valider(d: Mapping[str, Any]) -> list[str]:
    """Les défauts d'une fiche, en mots ; une liste vide si elle tient. Un canal attendu
    (absent du registre) n'est pas un défaut : `manques` le dit."""
    out: list[str] = []
    manquent = [c for c in CLES if c not in d]
    if manquent:
        return [f"clés absentes {manquent}"]
    etrangeres = sorted(set(d) - set(CLES) - set(FACULTATIVES))
    if etrangeres:
        out.append(f"clés inconnues {etrangeres}")
    if d["schema"] != SCHEMA:
        out.append(f"schéma {d['schema']} (attendu {SCHEMA})")
    if d["sorte"] not in SORTES:
        out.append(f"sorte « {d['sorte']} » inconnue {SORTES}")
        return out
    src = d["source"] or {}
    if not (_source(src.get("citation")) and _source(src.get("url"))):
        out.append("source du programme sans citation ou sans adresse")
    lev = d["levier"] or {}
    if not _source(lev.get("texte")):
        out.append("levier sans texte")
    for i, p in enumerate(d["payeurs"] or ()):
        if p.get("qui") not in PAYEURS:
            out.append(f"payeur {i} « {p.get('qui')} » inconnu")
        if p.get("sens") not in SENS:
            out.append(f"payeur {i} : sens « {p.get('sens')} » ({SENS})")
        if p.get("qui") == "entreprises" and p.get("par") not in PAR_ENTREPRISES:
            out.append(f"payeur {i} : entreprises par « {p.get('par')} » inconnu")
        part = p.get("part")
        if part is not None and not (isinstance(part, int | float) and 0 <= part <= 1):
            out.append(f"payeur {i} : part « {part} » (de 0 à 1)")
    if d["sorte"] in ("chiffree", "hypothese") and not d["payeurs"]:
        out.append("une mesure qui a un montant sans payeur")
    for i, inc in enumerate(d["incidence"] or ()):
        if inc.get("horizon") not in HORIZONS:
            out.append(f"incidence {i} : horizon « {inc.get('horizon')} » ({HORIZONS})")
        if not _source(inc.get("source")):
            out.append(f"incidence {i} sans source (ou « {NON_SOURCEE} »)")
    for i, h in enumerate(d["hypotheses"] or ()):
        if not (_source(h.get("texte")) and _source(h.get("source"))):
            out.append(f"hypothèse {i} sans texte ou sans source (ou « {NON_SOURCEE} »)")
    fin = d["financement"] or {}
    if "annonce" not in fin:
        out.append("financement sans « annonce » (null s'il est absent)")
    if fin.get("annonce") and not _source(fin.get("source")):
        out.append("financement annoncé sans sa citation")
    mal = [c for c in d["canaux"] or () if c not in CANAUX and c not in CANAUX_ATTENDUS]
    if mal:
        out.append(f"canaux ni enregistrés ni attendus {mal}")
    out.extend(_valider_donnees(d))
    out.extend(_valider_montant(d["sorte"], d["montant"] or {}))
    a = (d["montant"] or {}).get("annonce") or {}
    if a.get("par") == "calcul" and not any(
            isinstance(x.get("montant_md"), int | float) for x in assiettes(d)):
        out.append("montant calculé sans assiette chiffrée")
    return out


def assiettes(d: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    """Les assiettes d'une fiche (D-504), en liste."""
    a = d.get("assiette")
    if a is None:
        return []
    return list(a) if isinstance(a, list) else [a]


def _valider_donnees(d: Mapping[str, Any]) -> list[str]:
    out: list[str] = []
    a = d.get("assiette")
    if a is not None and not isinstance(a, dict | list):
        return ["assiette ni table ni liste"]
    for i, x in enumerate(assiettes(d)):
        if not (isinstance(x, dict) and _source(x.get("texte")) and _source(x.get("source"))):
            out.append(f"assiette {i} sans texte ou sans source")
            continue
        md = x.get("montant_md")
        if md is not None and not isinstance(md, int | float):
            out.append(f"assiette {i} : montant « {md} » pas un nombre")
        if md is not None and x["source"] == NON_SOURCEE:
            out.append(f"assiette {i} : un montant sans source")
    cal = d.get("calendrier")
    if cal is not None and not (isinstance(cal, dict) and _source(cal.get("texte"))
                                and _source(cal.get("source"))):
        out.append("calendrier sans texte ou sans source")
    return out


def _valider_montant(sorte: str, m: Mapping[str, Any]) -> list[str]:
    out: list[str] = []
    origine = m.get("origine")
    if origine != ORIGINES[sorte]:
        return [f"sorte « {sorte} » et montant d'origine « {origine} »"]
    if origine == "rapport":
        if not (m.get("scenario") and m.get("rapport")):
            out.append("montant d'un rapport sans scénario ou sans rapport")
    elif origine == "hypothese":
        a = m.get("annonce") or {}
        if not (a.get("montant_md") and a.get("sens") and _source(a.get("citation"))):
            out.append("hypothèse sans montant annoncé, sens ou citation")
        if a.get("par", "candidat") not in ("candidat", "calcul"):
            out.append(f"montant par « {a.get('par')} » (candidat | calcul)")
        if a.get("par") == "calcul" and not _source(a.get("calcul")):
            out.append("montant calculé sans son calcul écrit")
        chocs = m.get("chocs") or {}
        if not chocs:
            out.append("hypothèse sans chocs")
        inconnues = sorted(set(chocs) - set(_categories()))
        if inconnues:
            out.append(f"chocs sur des catégories inconnues {inconnues}")
        if m.get("profil") not in ("constant", "rampe", "calendrier"):
            out.append(f"profil « {m.get('profil')} » (constant | rampe | calendrier)")
        if m.get("profil") == "calendrier" and not m.get("calendrier"):
            out.append("profil « calendrier » sans calendrier {année : Md€}")
        if not (isinstance(m.get("debut"), int) and isinstance(m.get("fin"), int)
                and m["debut"] <= m.get("plein", m["debut"]) <= m["fin"]):
            out.append("années de l'hypothèse (debut ≤ plein ≤ fin) absentes")
        if m.get("instrument") not in (None, *INSTRUMENTS):
            out.append(f"instrument « {m.get('instrument')} » inconnu")
        if m.get("entreprises_par") not in (None, *IMPOTS_ENTREPRISES):
            out.append(f"entreprises_par « {m.get('entreprises_par')} » inconnu")
    elif not _source(m.get("manque")):
        out.append("montant absent sans dire ce qui manque")
    return out


def manques(f: Fiche) -> list[str]:
    """Ce qui manque à une fiche pour que la mesure se propage, en mots : les canaux pas
    encore enregistrés, les hypothèses non sourcées, l'incidence non sourcée, le montant
    absent, le financement non chiffré."""
    d, out = f.donnees, []
    for c in f.canaux_attendus:
        volet, porte = CANAUX_ATTENDUS[c]
        out.append(f"canal « {c} » ({porte}) : pas encore dans le registre, volet {volet}")
    ns = [h["texte"] for h in d["hypotheses"] or () if h["source"] == NON_SOURCEE]
    if ns:
        out.append(f"{len(ns)} hypothèse(s) non sourcée(s)")
    if any(i["source"] == NON_SOURCEE for i in d["incidence"] or ()):
        out.append("une incidence non sourcée")
    if d["montant"]["origine"] == "aucun":
        out.append(f"aucun montant : {d['montant']['manque']}")
    if d["financement"].get("annonce") is None and d["sorte"] != "sans_choc":
        out.append("aucun financement annoncé")
    return out


# --------------------------------------------------------------------------- #
# le lien au jumeau
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Entree:
    """Ce que le jumeau lit d'une fiche : la `Mesure` (ou None, et pourquoi), les canaux
    ouverts et attendus, les hypothèses déclarées."""

    fiche: Fiche
    mesure: Any | None
    refus: str | None
    canaux: tuple[str, ...]
    attendus: tuple[str, ...]
    hypotheses: tuple[Mapping[str, Any], ...]


def annuel(m: Mapping[str, Any], annees: Sequence[int]) -> dict[int, float]:
    """La part du montant de régime, chaque année : 1 de `debut` à `fin` (constant) ; une
    rampe linéaire de `debut` à `plein`, puis 1 jusqu'à `fin` ; ou le calendrier du
    candidat, linéaire entre ses points, son dernier point étant le régime."""
    debut, fin = int(m["debut"]), int(m["fin"])
    plein = int(m.get("plein", debut))
    out = {}
    if m["profil"] == "calendrier":
        pts = sorted((int(a), float(v)) for a, v in m["calendrier"].items())
        regime = pts[-1][1]
        for a in annees:
            if a < pts[0][0] or a > fin:
                continue
            v = pts[-1][1]
            for (a0, v0), (a1, v1) in pairwise(pts):
                if a0 <= a <= a1:
                    v = v0 + (v1 - v0) * (a - a0) / (a1 - a0)
                    break
            out[a] = v / regime
        return out
    for a in annees:
        if a < debut or a > fin:
            continue
        out[a] = (1.0 if m["profil"] == "constant" or a >= plein
                  else (a - debut + 1) / (plein - debut + 1))
    return out


def hypothese(f: Fiche, *, tables: Mapping[str, Any] | None = None,
              cellules: Any = None, annees: Sequence[int] = range(2026, 2036)) -> Any:
    """La loi hypothétique d'une fiche `hypothese` (`Mesure.hypothese`) : ses chocs au
    compte des APU, son impulsion sur la variante de Mésange la plus proche quand la
    fiche en nomme une et que les tables la portent, et ses chocs aux ménages (au
    prorata de `menages_par` dans les cellules) et aux entreprises (`entreprises_par`),
    comme `navigateur.Session.hypothese`."""
    from impots.jumeau.comparaison import _parts
    from impots.jumeau.mesures import Mesure

    m = f["montant"]
    if f.sorte != "hypothese":
        raise TransmissionError(f"{f.cle} : sorte « {f.sorte} », pas une hypothèse")
    parts = annuel(m, annees)
    if not parts:
        raise TransmissionError(f"{f.cle} : aucune année de {m['debut']} à {m['fin']} "
                                f"dans {annees[0]}–{annees[-1]}")
    chocs = {a: {c: float(v) * s for c, v in m["chocs"].items()} for a, s in parts.items()}
    cout = {a: sum(c.values()) for a, c in chocs.items()}
    instrument = m.get("instrument")
    couvert = bool(instrument and tables and instrument in tables.get("instruments", {}))
    macro = ({"horizons": tables["horizons"], "court": tables["court"],
              "instruments": {instrument: tables["instruments"][instrument]}}
             if couvert else None)
    mesure = Mesure.hypothese(
        f"{f['candidat']}_{f['mesure']}", f"{f['libelle']} (déclaré par le candidat)",
        chocs=chocs, impulsions=({a: {instrument: v} for a, v in cout.items()}
                                 if couvert else None),
        macro=macro, auteur=f["candidat"])
    menages = entreprises = None
    if m.get("menages_par") and cellules is not None:
        cle = _parts(cellules.par_decile(m["menages_par"]))
        part = float(m.get("menages_part", 1.0))
        menages = {a: {"deciles": [part * v * x for x in cle]} for a, v in cout.items()}
    if m.get("entreprises_par"):
        entreprises = {a: {m["entreprises_par"]: -v} for a, v in cout.items()}
    return dataclasses.replace(mesure, menages=menages, entreprises=entreprises)


def entree(f: Fiche, session: Any, *, vue: str = "vieillie",
           convention: str | None = None, mode: str = "reduit") -> Entree:
    """Ce que le jumeau lit d'une fiche. `session` est une `navigateur.Session` : une
    mesure chiffrée y est lue par son rapport (`Session.mesure`, donc
    `Mesure.depuis_rapport`) ; une hypothèse par `hypothese`, avec les tables de Mésange
    et les cellules de la session."""
    d = f.donnees
    commun = {"fiche": f, "canaux": f.canaux_ouverts, "attendus": f.canaux_attendus,
              "hypotheses": tuple(d["hypotheses"] or ())}
    origine = d["montant"]["origine"]
    if origine == "rapport":
        scenario = d["montant"]["scenario"]
        if scenario not in session.candidats:
            return Entree(mesure=None, refus=f"rapport « {scenario} » absent des entrées "
                          f"du jumeau", **commun)
        return Entree(mesure=_lire(session, scenario, vue, convention, mode), refus=None,
                      **commun)
    if origine == "hypothese":
        if d["montant"].get("inclus_dans"):
            return Entree(mesure=None, refus=f"compté dans « {d['montant']['inclus_dans']} »"
                          f", que le candidat ne ventile pas : ne pas additionner",
                          **commun)
        return Entree(mesure=hypothese(f, tables=session.tables,
                                       cellules=session.cellules),
                      refus=None, **commun)
    return Entree(mesure=None, refus=d["montant"]["manque"], **commun)


def _lire(session: Any, scenario: str, vue: str, convention: str | None,
          mode: str) -> Any:
    """Le rapport d'une mesure : en mode structurel, la mesure que ce mode lit
    (`Session.mesure_structurel` : une hausse du Smic par le bloc `travail`, D-487)."""
    if mode == "structurel":
        return session.mesure_structurel(scenario, vue, convention)
    return session.mesure(scenario, vue, convention)


def programme(candidat: str, session: Any, *, vue: str = "vieillie",
              convention: str | None = None, racine: Path = ICI, mode: str = "reduit"
              ) -> tuple[list[Entree], list[Entree]]:
    """Les mesures d'un programme prêtes à entrer, et les autres.

    La part chiffrée entre par le rapport du programme (`pres2027_<candidat>_programme`),
    qui fait tourner ses mesures chiffrées ensemble, en interaction, et non par la somme
    de leurs rapports ; une mesure chiffrée seule n'est donc pas rajoutée. Les hypothèses
    entrent chacune par sa loi, sauf celles qu'une autre mesure compte déjà."""
    toutes = fiches(candidat, racine)
    if not toutes:
        raise TransmissionError(f"aucune fiche pour « {candidat} »")
    pretes: list[Entree] = []
    autres: list[Entree] = []
    scen = f"pres2027_{candidat}_programme"
    chiffrees = [f for f in toutes if f.sorte == "chiffree"]
    if chiffrees:
        if scen not in session.candidats:
            raise TransmissionError(f"rapport du programme « {scen} » absent")
        tete = chiffrees[0]
        canaux = tuple(dict.fromkeys(c for f in chiffrees for c in f.canaux_ouverts))
        attendus = tuple(dict.fromkeys(c for f in chiffrees for c in f.canaux_attendus))
        hyp = tuple(h for f in chiffrees for h in f["hypotheses"] or ())
        pretes.append(Entree(fiche=tete, mesure=_lire(session, scen, vue, convention, mode),
                             refus=None, canaux=canaux, attendus=attendus,
                             hypotheses=hyp))
    for f in toutes:
        if f.sorte == "chiffree":
            continue
        e = entree(f, session, vue=vue, convention=convention, mode=mode)
        (pretes if e.mesure is not None else autres).append(e)
    return pretes, autres


def qualite(racine: Path = ICI, candidats: Iterable[str] | None = None
            ) -> dict[str, dict[str, int]]:
    """{candidat : compte} des données critiques (D-505) : les fiches par sorte, les
    hypothèses chiffrées par le candidat et par le calcul, les fiches sans montant, celles
    qui portent une assiette chiffrée, et les hypothèses sourcées et non sourcées."""
    out: dict[str, dict[str, int]] = {}
    for f in fiches(None, racine):
        c = f["candidat"]
        if candidats is not None and c not in candidats:
            continue
        q = out.setdefault(c, {**dict.fromkeys(SORTES, 0), "hypothese_candidat": 0,
                               "hypothese_calcul": 0, "sans_montant": 0,
                               "assiette_chiffree": 0, "hypotheses_sourcees": 0,
                               "hypotheses_non_sourcees": 0})
        q[f.sorte] += 1
        m = f["montant"]
        if f.sorte == "hypothese":
            par = (m.get("annonce") or {}).get("par", "candidat")
            q[f"hypothese_{par}"] += 1
        if m["origine"] == "aucun" and f.sorte == "parametre":
            q["sans_montant"] += 1
        if any(isinstance(x.get("montant_md"), int | float) for x in assiettes(f.donnees)):
            q["assiette_chiffree"] += 1
        for h in f["hypotheses"] or ():
            q["hypotheses_non_sourcees" if h["source"] == NON_SOURCEE
              else "hypotheses_sourcees"] += 1
    return out


def releve(racine: Path = ICI, candidats: Iterable[str] | None = None
           ) -> dict[str, dict[str, int]]:
    """{candidat : {sorte : nombre de fiches}}, et les canaux attendus cités."""
    out: dict[str, dict[str, int]] = {}
    for f in fiches(None, racine):
        c = f["candidat"]
        if candidats is not None and c not in candidats:
            continue
        out.setdefault(c, dict.fromkeys(SORTES, 0))[f.sorte] += 1
    return out
