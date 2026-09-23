"""Phase 8 §5 — le panneau réindustrialisation : un tableau de bord d'INSTRUMENTS.

Il répond à : que fait ce scénario à la charge fiscale sur la production, sur quels
secteurs, comparée à qui, et que disent les preuves de ce que les entreprises ont fait
la dernière fois ? Il refuse de répondre à : « combien d'usines ? », « combien d'emplois
industriels ? ».

CE QUI FAIT QUE CE PANNEAU EST HONNÊTE, GARDE PAR GARDE.

* **Le refus est AFFICHÉ, pas silencieux.** `BANNER` est permanent, en haut du panneau,
  et `panel()` ne peut pas le rendre sans lui. Une affirmation de transformation
  structurelle demanderait une classe de modèle — localisation et entrée de firmes,
  dynamique — dont la bande d'incertitude honnête, à l'échelle d'un pays, CHANGE DE
  SIGNE. « Bande ou rien » dit alors : rien.
* **Le périmètre D.29 ne se décide pas ici.** Savoir si le forfait social ou les DMTO
  sont des « autres impôts sur la production » est une question de comptabilité
  nationale qui se tranche dans un document, pas de mémoire. Ce module déclare les
  lignes CANDIDATES — du texte, aucun chiffre, aucun classement — et lit le classement
  dans une table générée sur une machine qui a les sources. Sans elle il refuse en
  nommant le document à lire.
* **L'écart de périmètre est AFFICHÉ, jamais refermé en silence.** Notre agrégat chiffré
  est un SOUS-ENSEMBLE de la D.29 nationale : la CFE est sous gate, donc absente. Une
  comparaison qui ne serait juste que parce qu'on a aligné les périmètres sans le dire
  n'est pas juste. `Burden` porte donc l'écart, et les lignes non chiffrées sont
  nommées une par une.
* **On ne compare pas notre agrégat chiffré à la D.29 d'un autre pays.** C'est le piège
  central de ce panneau et il produit un nombre exactement faux de la taille de l'écart
  de couverture, avec l'air d'aller très bien. Le benchmark compare NATIONAL à NATIONAL,
  et notre part chiffrée s'affiche à côté comme taux de couverture — jamais dans la même
  colonne.
* **La ligne C4 dit si elle est DANS son support.** La bande centrée sur zéro de l'IPP
  a été estimée sur la CET (CVAE + CFE) en 2021. La rendre pour un mouvement de la taxe
  sur les salaires, c'est l'extrapoler hors de sa base d'estimation — ce qui peut se
  faire, à condition que ce soit écrit sur la ligne elle-même.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from impots.donnees import PROCESSED

#: La bannière permanente de §5.1, au mot près. `panel()` ne rend rien sans elle.
BANNER = (
    "ce panneau chiffre des instruments et des compositions ; il ne modélise pas la "
    "transformation structurelle de l'économie"
)

#: Ce que le panneau sait rendre. Liste BLANCHE, pour la raison que tout le reste du
#: dépôt applique : une liste noire ne refuse que ce que quelqu'un a pensé à interdire,
#: et la demande la plus dangereuse est celle que personne n'a anticipée.
PANEL_OUTPUTS: frozenset[str] = frozenset({
    "charge_production_sur_va",   # l'agrégat chiffré rapporté à la valeur ajoutée
    "ecart_perimetre",            # notre agrégat contre la D.29 nationale
    "composition_sectorielle",    # composition, et le mot « composition » est la garde
    "benchmark_national",         # D.29/VA nationale contre nationale
    "bande_c4",                   # la ligne de preuve, avec son support
    "lignes_non_chiffrees",       # ce qui manque, nommé
})

#: Les sorties refusées, avec la raison affichée. Cette table n'est PAS la garde — la
#: liste blanche l'est — elle sert à donner un bon message à qui demande de bonne foi.
REFUSED_OUTCOMES: dict[str, str] = {
    "nombre_usines": "le nombre d'établissements industriels après réforme",
    "emplois_industriels": "l'emploi industriel après réforme",
    "relocalisations": "les relocalisations induites",
    "part_industrie_pib_apres_reforme": "la part de l'industrie dans le PIB après réforme",
    "competitivite": "« la compétitivité », qui n'est pas une grandeur mesurée ici",
}

#: Le document qui tranche l'appartenance à la D.29. Il est au manifeste et sourcé ;
#: il n'est simplement pas sur toutes les machines.
PERIMETER_DOCUMENT = "insee_cn2025_t3217_principaux_impots_par_categorie.xlsx"

#: Généré là où `data/raw/` existe, gitignoré comme les autres tables traitées. Ancré à
#: la racine du dépôt, et non au répertoire courant.
PERIMETER_TABLE = PROCESSED / "d29_perimeter.json"

#: Les seaux dont le moteur porte le secteur. §5.2 : le moteur de cellules porte le
#: secteur pour les instruments A ; les instruments B entrent au niveau national.
INCIDENCE_CAPABLE_BUCKETS: tuple[str, ...] = ("A",)

#: La base d'estimation de la ligne C4 : la CET, c'est-à-dire CVAE + CFE, réforme 2021.
#: Un instrument hors de cette liste peut quand même faire rendre la ligne — §5.2 le
#: demande — mais alors marquée hors support.
C4_ESTIMATION_BASE: frozenset[str] = frozenset({"cvae", "cfe", "cvae_c3s", "cfe_locales"})


class ReindustrialisationError(RuntimeError):
    """Le panneau a été sollicité d'une façon qui tromperait."""


class StructuralTransformationRefused(ReindustrialisationError):
    """On a demandé au panneau un résultat de transformation structurelle.

    Sa propre classe parce que l'interface l'affiche autrement : ce refus est une
    PROPRIÉTÉ du panneau, à montrer, pas une erreur à journaliser.
    """


class PerimeterTableMissing(ReindustrialisationError):
    """La table de périmètre n'a pas été générée ici.

    Pas un défaut : l'état attendu de toute copie sans `data/raw/`.
    """


class BenchmarkSourceMissing(ReindustrialisationError):
    """Aucun fichier comparateur n'est au manifeste."""


class VintageMismatch(ReindustrialisationError):
    """Deux millésimes que l'on s'apprêtait à comparer ne sont pas comparables."""


class PerimeterConfusion(ReindustrialisationError):
    """On a voulu comparer notre agrégat chiffré à un agrégat national."""


def refuse_outcome(name: str) -> None:
    """Refuse toute sortie hors de la liste blanche, et nomme la raison.

    La raison est toujours la même et mérite d'être écrite en entier : une affirmation
    de transformation structurelle demande un modèle de localisation et d'entrée de
    firmes, dont la bande honnête à l'échelle d'un pays contient le zéro ET les deux
    signes. Rendre le centre de cette bande serait rendre un chiffre dont l'intervalle
    contient son propre contraire.
    """
    if name in PANEL_OUTPUTS:
        return
    what = REFUSED_OUTCOMES.get(name)
    detail = f" — soit {what}" if what else ""
    raise StructuralTransformationRefused(
        f"« {name} » n'est pas une sortie de ce panneau{detail}. Ce panneau chiffre des "
        f"INSTRUMENTS et des COMPOSITIONS. Une réponse à cette question demanderait un "
        f"modèle de localisation et d'entrée de firmes, dynamique, dont la bande "
        f"d'incertitude honnête à l'échelle d'un pays enjambe le zéro et contient les "
        f"deux signes : en rendre le centre serait rendre un chiffre dont l'intervalle "
        f"contient son propre contraire. Sorties possibles : "
        f"{', '.join(sorted(PANEL_OUTPUTS))}.")


# --------------------------------------------------------------------------- #
# le périmètre : des lignes CANDIDATES ici, le classement dans un fichier
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class CandidateLine:
    """Un instrument que l'on SOUPÇONNE d'être dans la D.29. Aucun classement ici.

    `bucket` reprend `instrument_coverage.py` : c'est ce qui dit si la ligne est
    chiffrable aujourd'hui, indépendamment de son appartenance comptable.
    """

    code: str
    label: str
    bucket: str
    priced_by: tuple[str, ...] = ()

    @property
    def priced(self) -> bool:
        return self.bucket in ("A", "B") and bool(self.priced_by)


#: §5.2 nomme « CVAE, CFE-in-scope, C3S, taxe sur les salaires, versement mobilité,
#: TASCOM, … ». Les voici, plus les lignes de la tranche de couverture de M3 dont
#: l'appartenance est justement à trancher sur document. Aucune n'est classée ici.
CANDIDATES: tuple[CandidateLine, ...] = (
    CandidateLine("cvae_c3s", "CVAE et C3S", "A",
                  ("firm:cvae_taux_max", "firm:c3s_taux", "firm:c3s_abattement")),
    CandidateLine("cfe_locales", "CFE", "C"),
    CandidateLine("taxe_sur_les_salaires", "Taxe sur les salaires", "B",
                  ("agregats:taxe_sur_les_salaires",)),
    CandidateLine("versement_mobilite", "Versement mobilité", "B",
                  ("agregats:versement_mobilite",)),
    CandidateLine("tascom", "Taxe sur les surfaces commerciales", "B",
                  ("agregats:tascom",)),
    CandidateLine("tgap", "Taxe générale sur les activités polluantes", "B",
                  ("agregats:tgap",)),
    CandidateLine("taxe_apprentissage", "Taxe d'apprentissage et assimilés", "B",
                  ("agregats:taxe_apprentissage",)),
    CandidateLine("forfait_social", "Forfait social", "B",
                  ("agregats:forfait_social",)),
)


@dataclass(frozen=True)
class PerimeterRow:
    """Le classement d'UNE ligne, lu dans un document. `in_d29` n'a pas de défaut."""

    instrument: str
    in_d29: bool
    source_file: str
    vintage: str
    vintage_convention: str

    def __post_init__(self) -> None:
        if not self.source_file.strip():
            raise ReindustrialisationError(
                f"{self.instrument} : classement D.29 sans document. Savoir si un impôt "
                f"est un « autre impôt sur la production » est une question de "
                f"comptabilité nationale : de mémoire, c'est une réminiscence.")
        if not self.vintage_convention.strip():
            raise ReindustrialisationError(
                f"{self.instrument} : aucune convention de millésime. Budget, revenus et "
                f"comptabilité nationale ne tombent pas les mêmes années, et trois fois "
                f"déjà dans ce projet le calendrier du comparateur ÉTAIT l'erreur.")


@dataclass(frozen=True)
class NationalAggregate:
    """La D.29 nationale et la valeur ajoutée, toutes deux LUES.

    `derived_from_priced` existe pour être refusé. Reconstruire le total national en
    sommant nos propres instruments refermerait l'écart de périmètre à zéro par
    construction, et ce zéro se lirait comme « couverture complète » alors qu'il ne
    dirait rien du tout — la forme exacte du piège que D-153 a épinglé un étage plus bas.
    """

    d29_total_eur: float
    value_added_eur: float
    year: int
    vintage_convention: str
    source_file: str
    derived_from_priced: bool = False

    def __post_init__(self) -> None:
        if self.derived_from_priced:
            raise ReindustrialisationError(
                "le total national D.29 a été dérivé de nos propres instruments : "
                "l'écart de périmètre vaudrait alors zéro par construction et se lirait "
                "comme une couverture complète. Le total national se LIT dans les "
                "comptes, sinon il n'y a rien d'indépendant à comparer.")
        if self.value_added_eur <= 0:
            raise ReindustrialisationError(
                f"valeur ajoutée {self.value_added_eur} ≤ 0 : le dénominateur de la "
                f"charge n'est pas une grandeur libre.")
        if self.d29_total_eur <= 0:
            raise ReindustrialisationError(
                f"D.29 nationale {self.d29_total_eur} ≤ 0 : sans total national il n'y a "
                f"pas d'écart de périmètre à afficher, et l'afficher à zéro serait pire "
                f"que ne rien afficher.")
        if not self.source_file.strip():
            raise ReindustrialisationError("agrégat national sans document source")

    @property
    def d29_over_va(self) -> float:
        """La charge NATIONALE. C'est cette grandeur-là qui se compare entre pays."""
        return self.d29_total_eur / self.value_added_eur


def load_perimeter(path: Path | None = None) -> dict[str, PerimeterRow]:
    """Le classement D.29, ligne par ligne, depuis la table générée.

    Refuse en nommant le document plutôt qu'en échouant obscurément — c'est l'état
    attendu de toute copie du dépôt sans `data/raw/`.
    """
    table = Path(path) if path is not None else PERIMETER_TABLE
    if not table.exists():
        raise PerimeterTableMissing(
            f"{table} n'existe pas. L'appartenance à la D.29 ne se décide pas dans le "
            f"code : elle se lit dans « {PERIMETER_DOCUMENT} », qui EST au manifeste et "
            f"sourcé. Générer la table sur une machine qui a data/raw/, une ligne par "
            f"instrument candidat, avec in_d29, le fichier, le millésime et sa "
            f"convention.")
    payload = json.loads(table.read_text(encoding="utf-8"))
    rows = payload["lines"] if isinstance(payload, dict) else payload
    out: dict[str, PerimeterRow] = {}
    for raw in rows:
        row = PerimeterRow(**raw)
        if row.instrument in out:
            raise ReindustrialisationError(
                f"{row.instrument} : deux classements pour un même instrument dans "
                f"{table}. L'un gagnerait selon l'ordre du fichier.")
        out[row.instrument] = row
    return out


# --------------------------------------------------------------------------- #
# la charge, et l'écart de périmètre qu'elle doit afficher
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Burden:
    """La charge chiffrée, ce qu'elle couvre, et surtout ce qu'elle NE couvre pas."""

    priced_eur: dict[str, float]
    national: NationalAggregate
    unpriced: tuple[str, ...]
    unpriced_reason: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.priced_eur:
            raise ReindustrialisationError(
                "aucun instrument chiffré : une charge de production vide se lirait "
                "comme une charge nulle.")
        for code, amount in self.priced_eur.items():
            if amount < 0:
                raise ReindustrialisationError(f"{code} : montant négatif {amount}")
        # QUESTION 1 DE LA BALAYAGE M6 — un dénominateur qui ne contient pas son
        # numérateur. Notre agrégat est un SOUS-ENSEMBLE de la D.29 : il ne peut pas la
        # dépasser. Mesuré avant d'être gardé : 38 md€ chiffrés contre 10 md€ nationaux
        # rendaient « 380 % de couverture, écart −28,0 md€ », imprimés par `statement()`
        # comme s'ils voulaient dire quelque chose. En vrai cela ne vient jamais d'une
        # couverture : cela vient d'une erreur d'unité ou du mauvais fichier — et le
        # symptôme envoie le lecteur réparer celui des deux nombres qui était juste.
        if self.priced_total_eur > self.national.d29_total_eur:
            raise ReindustrialisationError(
                f"agrégat chiffré {self.priced_total_eur / 1e9:.1f} md€ SUPÉRIEUR à la "
                f"D.29 nationale {self.national.d29_total_eur / 1e9:.1f} md€. Un "
                f"sous-ensemble ne dépasse pas l'ensemble qui le contient : ce n'est pas "
                f"un problème de couverture, c'est une erreur d'unité ou un fichier qui "
                f"n'est pas celui qu'on croit. Rendu tel quel, le panneau afficherait "
                f"une couverture supérieure à 100 % et un écart de périmètre négatif.")
        if (self.unpriced
                and self.priced_total_eur == self.national.d29_total_eur):
            raise ReindustrialisationError(
                f"couverture de 100 % alors que {sorted(self.unpriced)} sont nommées non "
                f"chiffrées. Les deux affirmations ne peuvent pas être vraies ensemble : "
                f"soit la liste des lignes manquantes est fausse, soit le total national "
                f"l'est. Un 100 % obtenu dans ces conditions se lirait comme une "
                f"couverture complète, qui est exactement ce que ce panneau ne peut pas "
                f"revendiquer tant que la CFE est sous gate.")
        missing = [c for c in self.unpriced if c not in self.unpriced_reason]
        if missing:
            raise ReindustrialisationError(
                f"lignes non chiffrées sans raison affichée {sorted(missing)} : une "
                f"ligne absente d'un tableau se lit comme une ligne oubliée, et ici "
                f"elle serait surtout une charge que le lecteur croit avoir comptée.")

    @property
    def priced_total_eur(self) -> float:
        return sum(self.priced_eur.values())

    @property
    def priced_over_va(self) -> float:
        """Notre agrégat rapporté à la VA. **Ce n'est PAS la charge nationale.**"""
        return self.priced_total_eur / self.national.value_added_eur

    @property
    def coverage_of_d29(self) -> float:
        return self.priced_total_eur / self.national.d29_total_eur

    @property
    def gap_eur(self) -> float:
        """Ce que la D.29 nationale porte et que nous ne chiffrons pas. Affiché."""
        return self.national.d29_total_eur - self.priced_total_eur

    def statement(self) -> str:
        """La phrase de périmètre, obligatoire partout où un de ces nombres s'affiche."""
        noms = ", ".join(f"« {c} »" for c in self.unpriced) or "aucune"
        return (
            f"PÉRIMÈTRE. Agrégat chiffré {self.priced_total_eur / 1e9:.1f} md€ contre "
            f"D.29 nationale {self.national.d29_total_eur / 1e9:.1f} md€ "
            f"({self.coverage_of_d29:.0%} de couverture, écart "
            f"{self.gap_eur / 1e9:.1f} md€). Lignes non chiffrées : {noms}. "
            f"Notre part de VA ({self.priced_over_va:.2%}) et la part nationale "
            f"({self.national.d29_over_va:.2%}) ne mesurent donc pas la même chose."
        )


# --------------------------------------------------------------------------- #
# le benchmark — et le seul piège qui compte vraiment ici
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Comparator:
    """Un pays comparateur, avec sa D.29 NATIONALE et sa VA. Deux nombres lus."""

    country: str
    d29_total_eur: float
    value_added_eur: float
    year: int
    vintage_convention: str
    source_file: str

    def __post_init__(self) -> None:
        if not self.source_file.strip():
            raise BenchmarkSourceMissing(
                f"{self.country} : aucun fichier source. Un benchmark sans document est "
                f"une opinion sur un pays étranger.")
        if self.value_added_eur <= 0 or self.d29_total_eur <= 0:
            raise ReindustrialisationError(
                f"{self.country} : D.29 {self.d29_total_eur} et VA {self.value_added_eur} "
                f"doivent être strictement positives.")

    @property
    def d29_over_va(self) -> float:
        return self.d29_total_eur / self.value_added_eur


@dataclass(frozen=True)
class BenchmarkResult:
    """Une comparaison nationale-à-nationale, et la phrase qui l'encadre."""

    ours_national: float
    theirs: float
    country: str
    year: int
    perimeter_statement: str
    our_priced_coverage: float

    @property
    def gap_points(self) -> float:
        """En POINTS de VA, pas en pourcentage d'un pourcentage."""
        return (self.ours_national - self.theirs) * 100.0


def benchmark(burden: Burden, comparator: Comparator) -> BenchmarkResult:
    """Compare la D.29/VA française à celle du comparateur. **National contre national.**

    C'est le piège central de ce panneau : notre agrégat chiffré est un sous-ensemble de
    la D.29, donc le comparer à la D.29 d'un autre pays produit un écart faux d'exactement
    la taille de l'écart de couverture — et ce nombre a l'air parfaitement normal. La
    fonction compare donc les deux TOTAUX NATIONAUX, et affiche notre couverture à côté
    comme un taux, jamais dans la même colonne.

    Le refus de millésime vient avant tout calcul : deux années différentes, ou deux
    conventions différentes, ne se comparent pas, et l'écart qu'elles produiraient serait
    lisible comme une différence de politique fiscale.
    """
    if comparator.year != burden.national.year:
        raise VintageMismatch(
            f"millésimes différents : France {burden.national.year}, "
            f"{comparator.country} {comparator.year}. L'écart qui en sortirait "
            f"mélangerait une différence de politique fiscale et une différence de date, "
            f"et rien dans le nombre ne dirait laquelle domine.")
    if comparator.vintage_convention != burden.national.vintage_convention:
        raise VintageMismatch(
            f"conventions différentes : France « {burden.national.vintage_convention} », "
            f"{comparator.country} « {comparator.vintage_convention} ». Même année "
            f"affichée, calendriers différents — c'est la forme de l'erreur que ce "
            f"projet a déjà payée trois fois.")
    return BenchmarkResult(
        ours_national=burden.national.d29_over_va,
        theirs=comparator.d29_over_va,
        country=comparator.country,
        year=comparator.year,
        our_priced_coverage=burden.coverage_of_d29,
        perimeter_statement=(
            f"Comparaison NATIONALE à NATIONALE (D.29 / valeur ajoutée, "
            f"{burden.national.year}). Notre agrégat chiffré couvre "
            f"{burden.coverage_of_d29:.0%} de la D.29 française et n'entre PAS dans "
            f"cette comparaison : le comparer à la D.29 de {comparator.country} "
            f"produirait un écart faux d'exactement la taille du déficit de couverture. "
            f"{burden.statement()}"),
    )


def refuse_priced_against_national(country: str) -> None:
    """La comparaison interdite, nommée, pour qu'elle soit testable en tant que telle."""
    raise PerimeterConfusion(
        f"comparaison de notre agrégat CHIFFRÉ à la D.29 nationale de {country} : les "
        f"deux ne mesurent pas la même chose. L'écart obtenu serait faux d'exactement "
        f"le déficit de couverture, et il ressemblerait trait pour trait à un écart de "
        f"politique fiscale. Comparer national à national, et afficher la couverture à "
        f"côté.")


# --------------------------------------------------------------------------- #
# le secteur : composition pour les instruments B, incidence seulement pour A
# --------------------------------------------------------------------------- #
#: Les deux façons de lire un tableau par secteur, et le mot qui les sépare. Au niveau
#: module parce qu'un dictionnaire dans un dataclass gelé devient un CHAMP à valeur
#: mutable partagée, ce qui est une autre sorte de piège.
SECTOR_LABELS: dict[str, str] = {
    "incidence": "incidence sectorielle — calculée sur le moteur de cellules",
    "composition": ("composition sectorielle — PAS de l'incidence : part publiée de "
                    "l'assiette, citée et non calculée, sans population derrière le "
                    "total national"),
}


@dataclass(frozen=True)
class SectorView:
    """Une vue sectorielle, et le mot qui dit ce qu'elle est.

    Pour un instrument B, `kind` vaut « composition » et toute lecture d'incidence est
    refusée par son nom. La distinction n'est pas de la prudence rédactionnelle : un
    instrument agrégé est chiffré sur une assiette nationale statique, sans population
    derrière lui, donc « quel secteur le paie » est une répartition PUBLIÉE que l'on
    cite, pas un résultat que l'on calcule.
    """

    instrument: str
    bucket: str
    kind: str
    shares: dict[str, float]
    source: str

    @property
    def label(self) -> str:
        return SECTOR_LABELS[self.kind]

    @property
    def incidence(self) -> dict[str, float]:
        if self.kind != "incidence":
            raise ReindustrialisationError(
                f"{self.instrument} est un instrument de seau {self.bucket} : il est "
                f"chiffré sur une assiette nationale statique, sans population derrière "
                f"le total. Une lecture d'incidence produirait un tableau par secteur "
                f"indiscernable d'un vrai. Ce qui existe ici est une COMPOSITION, "
                f"publiée et citée : {self.source}.")
        return self.shares


def sector_view(instrument: str, bucket: str, shares: dict[str, float],
                source: str) -> SectorView:
    """Construit la vue, et le seau décide de sa nature — jamais l'appelant."""
    if not shares:
        raise ReindustrialisationError(
            f"{instrument} : aucune part sectorielle. Un tableau vide se lirait comme "
            f"« réparti uniformément », qui est une affirmation.")
    total = sum(shares.values())
    if abs(total - 1.0) > 0.01:
        raise ReindustrialisationError(
            f"{instrument} : les parts somment à {total:.4f} et non à 1. Une composition "
            f"qui ne boucle pas répartit un total que personne n'a.")
    if not source.strip():
        raise ReindustrialisationError(
            f"{instrument} : composition sans source. Une répartition sectorielle sans "
            f"document est une répartition inventée, et elle s'affiche exactement comme "
            f"une vraie.")
    kind = "incidence" if bucket in INCIDENCE_CAPABLE_BUCKETS else "composition"
    return SectorView(instrument=instrument, bucket=bucket, kind=kind,
                      shares=dict(shares), source=source)


# --------------------------------------------------------------------------- #
# la ligne C4 — rendue dès qu'un impôt de production bouge, avec son support
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class C4Row:
    """La bande centrée sur zéro, et si le mouvement est dans sa base d'estimation."""

    moved: tuple[str, ...]
    in_support: bool
    band: tuple[float, float]
    grade: str
    note: str

    def render(self) -> str:
        support = ("dans le support de l'étude" if self.in_support
                   else "HORS du support de l'étude")
        return (f"Investissement et impôts de production — bande "
                f"[{self.band[0]:+.3f} ; {self.band[1]:+.3f}] par unité de |Δ log|, "
                f"centrée sur zéro, grade « {self.grade} », {support}. {self.note}")


def c4_row(moved: tuple[str, ...], band: tuple[float, float]) -> C4Row:
    """La ligne de preuve ancre de §5.2, avec l'honnêteté qui manquait à l'énoncé.

    §5.2 demande que cette ligne se rende « dès qu'un instrument d'impôt de production
    bouge ». Mais elle a été estimée sur la CET — CVAE plus CFE, réforme de 2021. La
    rendre pour un mouvement de la taxe sur les salaires l'extrapole hors de sa base
    d'estimation. On la rend quand même, parce que taire la seule évaluation existante
    serait pire, et on ÉCRIT sur la ligne qu'elle est hors support.

    Une bande centrée sur zéro n'est pas une absence de réponse : c'est une recherche
    sérieuse qui n'a rien trouvé de robuste, et sa LARGEUR dit combien on aurait pu
    manquer.
    """
    if not moved:
        raise ReindustrialisationError(
            "la ligne C4 a été demandée sans qu'aucun instrument ne bouge : rendue à "
            "vide, elle donnerait à un panneau immobile l'air d'avoir été évalué.")
    if band[0] > band[1]:
        raise ReindustrialisationError(f"bande inversée : {band}")
    if not (band[0] <= 0.0 <= band[1]):
        raise ReindustrialisationError(
            f"la bande C4 {band} ne contient pas zéro. C'est la ligne « zéro-bande » de "
            f"§5.2 : si la bande lue ne contient plus zéro, ce n'est plus cette ligne, "
            f"et la remplacer en silence changerait le sens du panneau.")
    inside = [code for code in moved if code in C4_ESTIMATION_BASE]
    in_support = len(inside) == len(moved)
    if in_support:
        note = ("Estimée sur la CET (CVAE + CFE), réforme de 2021 — les instruments qui "
                "bougent ici sont ceux sur lesquels elle a été estimée.")
    elif inside:
        outside = sorted(set(moved) - C4_ESTIMATION_BASE)
        note = (f"Estimée sur la CET (CVAE + CFE) ; {', '.join(outside)} n'en fait pas "
                f"partie, donc la bande est extrapolée pour cette part du paquet.")
    else:
        note = (f"Estimée sur la CET (CVAE + CFE), réforme de 2021 ; aucun des "
                f"instruments qui bougent ({', '.join(sorted(moved))}) n'en fait partie. "
                f"La bande est affichée parce que taire la seule évaluation existante "
                f"serait pire, pas parce qu'elle s'applique.")
    return C4Row(moved=tuple(moved), in_support=in_support, band=band,
                 grade="in-support" if in_support else "illustrative", note=note)


# --------------------------------------------------------------------------- #
# le panneau
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Panel:
    """Ce que le panneau rend. `banner` est un champ, pas une décoration d'affichage."""

    banner: str
    burden: Burden
    perimeter_statement: str
    c4: C4Row | None
    benchmark_result: BenchmarkResult | None
    sectors: tuple[SectorView, ...] = ()

    def __post_init__(self) -> None:
        if self.banner != BANNER:
            raise ReindustrialisationError(
                "la bannière du panneau a été modifiée ou omise. §5.1 en fait un refus "
                "AFFICHÉ et non silencieux : un panneau d'instruments sans elle se lit "
                "comme un modèle de réindustrialisation.")


def panel(*, burden: Burden, moved: tuple[str, ...] = (),
          band: tuple[float, float] | None = None,
          comparator: Comparator | None = None,
          sectors: tuple[SectorView, ...] = ()) -> Panel:
    """Assemble le panneau. La bannière n'est pas optionnelle et la C4 suit le mouvement.

    `band` vient de la table de preuves (`production_tax.yaml`) plutôt que d'ici : ce
    module n'écrit aucune borne, il en reçoit.
    """
    row = None
    if moved:
        if band is None:
            raise ReindustrialisationError(
                f"des impôts de production bougent ({', '.join(sorted(moved))}) et "
                f"aucune bande de preuve n'a été fournie. Rendre le mouvement sans la "
                f"ligne C4 laisserait entendre qu'aucune évaluation n'existe, alors "
                f"qu'il en existe une et qu'elle ne trouve rien de robuste — ce qui "
                f"n'est pas la même information.")
        row = c4_row(moved, band)
    return Panel(
        banner=BANNER,
        burden=burden,
        perimeter_statement=burden.statement(),
        c4=row,
        benchmark_result=benchmark(burden, comparator) if comparator else None,
        sectors=sectors,
    )


# --------------------------------------------------------------------------- #
# la vue scénario — §5.2, et le piège du dénominateur
# --------------------------------------------------------------------------- #
#: Ce que le re-rendu NE fait PAS bouger, dit à l'endroit où le ratio s'affiche.
FIXED_DENOMINATOR_NOTE = (
    "DÉNOMINATEUR TENU FIXE. La charge bouge par son NUMÉRATEUR seulement : la valeur "
    "ajoutée est celle des comptes, inchangée. Une baisse d'impôt de production qui "
    "ferait croître la VA abaisserait le ratio davantage — ce panneau ne le chiffre "
    "pas, et la ligne C4 dit précisément que l'évaluation existante ne détecte pas cette "
    "réponse. Lire ce mouvement comme un effet de croissance serait lui prêter ce que le "
    "panneau refuse de modéliser."
)


@dataclass(frozen=True)
class ScenarioView:
    """Un scénario §2/§4 repassé dans le panneau : avant, après, et ce qui n'a pas bougé."""

    before: Burden
    after: Burden
    moved: tuple[str, ...]
    c4: C4Row
    denominator_note: str = FIXED_DENOMINATOR_NOTE
    gap_before_points: float | None = None
    gap_after_points: float | None = None
    composition_leakage: float | None = None
    composition_note: str = ""

    @property
    def burden_change_points(self) -> float:
        """En POINTS de valeur ajoutée, sur l'agrégat NATIONAL."""
        return (self.after.national.d29_over_va
                - self.before.national.d29_over_va) * 100.0

    def render(self) -> str:
        lines = [
            BANNER,
            self.after.statement(),
            f"Charge nationale D.29/VA : {self.before.national.d29_over_va:.3%} → "
            f"{self.after.national.d29_over_va:.3%} ({self.burden_change_points:+.3f} "
            f"point).",
            self.denominator_note,
            self.c4.render(),
        ]
        if self.gap_before_points is not None:
            lines.append(
                f"Écart au comparateur : {self.gap_before_points:+.3f} → "
                f"{self.gap_after_points:+.3f} point de VA.")
        if self.composition_leakage is not None:
            lines.append(self.composition_note)
        return "\n".join(lines)


def rerender(
    burden: Burden,
    deltas: dict[str, float],
    *,
    band: tuple[float, float],
    comparator: Comparator | None = None,
    composition_leakage: float | None = None,
    composition_source: str = "",
) -> ScenarioView:
    """Repasse un scénario dans le panneau. Le numérateur bouge, le dénominateur non.

    `deltas` est en euros mécaniques par instrument, signé comme le reste du dépôt : une
    baisse d'impôt est négative. Un delta sur un instrument qui n'est pas dans l'agrégat
    chiffré est REFUSÉ plutôt qu'ignoré — ignoré, il laisserait la charge immobile sous
    un scénario qui la fait bouger, ce qui est le zéro confiant que ce dépôt traque
    partout.

    Le total national bouge du même montant que notre agrégat : la réforme est réelle,
    elle change la D.29 nationale, pas seulement la part que nous savons chiffrer.
    L'écart de périmètre, lui, est INCHANGÉ en euros, ce qui est la bonne propriété —
    une réforme de la CVAE ne chiffre pas la CFE d'un coup.
    """
    unknown = sorted(set(deltas) - set(burden.priced_eur))
    if unknown:
        raise ReindustrialisationError(
            f"delta fourni pour des instruments hors de l'agrégat chiffré {unknown}. "
            f"Ignoré, il laisserait la charge immobile sous un scénario qui la fait "
            f"bouger — un zéro confiant. S'ils sont dans le périmètre mais pas chiffrés, "
            f"ils sont déjà nommés dans les lignes non chiffrées et le scénario ne peut "
            f"pas les faire bouger ici.")
    if not deltas:
        raise ReindustrialisationError(
            "scénario sans aucun delta : un re-rendu identique à l'original se lirait "
            "comme « cette réforme ne touche pas la production », qui est une "
            "affirmation et non un résultat de calcul.")

    priced_after = dict(burden.priced_eur)
    for code, delta in deltas.items():
        priced_after[code] = priced_after[code] + delta
    total_delta = sum(deltas.values())

    national = burden.national
    after = Burden(
        priced_eur=priced_after,
        national=NationalAggregate(
            d29_total_eur=national.d29_total_eur + total_delta,
            value_added_eur=national.value_added_eur,   # TENUE FIXE, et c'est dit
            year=national.year,
            vintage_convention=national.vintage_convention,
            source_file=national.source_file,
        ),
        unpriced=burden.unpriced,
        unpriced_reason=dict(burden.unpriced_reason),
    )

    gap_before = gap_after = None
    if comparator is not None:
        gap_before = benchmark(burden, comparator).gap_points
        gap_after = benchmark(after, comparator).gap_points

    note = ""
    if composition_leakage is not None:
        if not 0.0 <= composition_leakage < 1.0:
            raise ReindustrialisationError(
                f"fuite {composition_leakage} hors de [0 ; 1[ : ce n'est pas une part.")
        if not composition_source.strip():
            raise ReindustrialisationError(
                "composition sectorielle sans source : les parts de branches viennent "
                "du TES, dont le millésime et la base doivent s'afficher avec elles.")
        note = (
            f"COMPOSITION DE PREMIER TOUR ({composition_source}) : "
            f"{composition_leakage:.1%} de l'impulsion FUIT vers les importations. Les "
            f"parts de branches répartissent ce qui RESTE, et ne sont jamais "
            f"renormalisées pour récupérer la fuite — la réintégrer ferait retomber "
            f"100 % de l'impulsion sur des branches françaises, ce qui est faux de la "
            f"taille de la fuite.")

    return ScenarioView(
        before=burden, after=after, moved=tuple(sorted(deltas)),
        c4=c4_row(tuple(sorted(deltas)), band),
        gap_before_points=gap_before, gap_after_points=gap_after,
        composition_leakage=composition_leakage, composition_note=note,
    )
