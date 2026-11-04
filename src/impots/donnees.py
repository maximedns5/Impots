"""La chaîne de préparation des données : quoi, d'où, et avec quelle commande.

POURQUOI CE MODULE EXISTE. Jusqu'ici la chaîne était manuelle par conception —
`docs/DATA_DOWNLOADS.md` : « downloaded on the Mac (browser or curl) » — et rien ne la
décrivait sous une forme exécutable. Conséquence mesurée : dix-huit tests échouaient en
CI après 47 minutes, un par un, chacun sur le PREMIER fichier absent de sa chaîne. La
trace de `test_trajectoires` nommait le PDF IMK wp117 ; le store macro en matérialise en
réalité TROIS (wp117, wp139, Mésange). Réparer ce que la trace montrait aurait fait
échouer le run suivant sur le document suivant.

Ce module fait trois choses, et chacune est une garde.

* **Il déclare les dépendances d'un profil depuis les constantes des lecteurs eux-mêmes**
  — `ifi_cells.TRANCHE_FILE`, `top_tail.WORKBOOK`, les `document` des YAML du store — et
  non depuis une liste recopiée. Un préflight qui vérifie moins que ce que le code lit est
  la forme D-044 : un contrôle qui emprunte une autre route que la chose qu'il protège.
* **Il télécharge par le manifeste, jamais autrement.** URL, taille et sha256 viennent de
  `ingest.load_manifest()` — le chargeur que la production appelle (D-142). Un fichier en
  quarantaine ou sans URL est refusé (D-028). Un octet de différence avec le manifeste et
  le fichier n'est pas écrit : un millésime changé en silence produirait des chiffres
  plausibles, qui est le pire échec nommé de ce projet (D-007).
* **Il vérifie avant la suite, et dit quelle commande répare.** Un fichier absent se
  découvre en secondes, pas après 47 minutes, et chaque ligne rouge porte la commande qui
  la verdit.

CE QUE CE MODULE NE FAIT PAS : fabriquer une donnée. Un artefact dérivé se construit par
sa commande, depuis ses sources vérifiées ; s'il manque une source, il manque l'artefact,
et c'est dit. En particulier, la table de cellules FICTIVE de `tests/fixtures/` n'est
jamais acceptée à la place de la vraie (`cells_are_synthetic` est vérifié).
"""

from __future__ import annotations

import hashlib
import os
import re
import ssl
import urllib.error
import urllib.request
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path

import certifi

#: La racine du dépôt, une fois. Quatre modules lisaient `Path("data/...")` — relatif au
#: répertoire COURANT — pendant que les autres ancraient leurs chemins ici : un fichier
#: présent devenait « absent » dès qu'on lançait depuis un autre répertoire.
ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"

#: Refusé plutôt que suivi aveuglément : sans plafond, un serveur lent fige la CI.
TIMEOUT_S = 120

#: Certains serveurs publics refusent un client sans identité. Celle-ci dit qui télécharge.
USER_AGENT = "impots-data-fetch/1 (+https://github.com/maximedns5/Impots)"


class DonneesError(RuntimeError):
    """La préparation des données a rencontré un état qu'elle ne peut pas réparer seule."""


# --------------------------------------------------------------------------- #
# les dépendances d'un profil
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Brut:
    """Un fichier source, téléchargeable par son entrée de manifeste."""

    fichier: str
    pour: str

    @property
    def chemin(self) -> Path:
        return RAW / self.fichier


@dataclass(frozen=True)
class Derive:
    """Un artefact construit. Il a une commande, des entrées, et un validateur de schéma."""

    chemin: Path
    commande: str
    entrees: tuple[str, ...]
    pour: str
    valider: Callable[[Path], str] = field(repr=False, compare=False)
    construire: Callable[[], Path] = field(repr=False, compare=False)


def _fichiers_du_store_macro() -> tuple[str, ...]:
    """Tous les documents que `macro.store.load()` matérialise, lus dans ses YAML.

    `max_fan_horizon_years()` charge le store ENTIER, et le store valide chaque horizon
    déclaré contre le document source (`unknown = set(usable) - set(horizons)`). Chaque
    document derrière chaque table est donc une dépendance réelle, et cette fonction les
    dérive des déclarations plutôt que de les énumérer : ajouter une table ajoute sa
    source au préflight sans que personne n'ait à s'en souvenir.
    """
    import yaml

    from impots.macro import imk, mesange
    from impots.macro import store as store_module

    fichiers: list[str] = []
    for chemin in sorted(store_module.PARAMETERS.glob("*.yaml")):
        document = yaml.safe_load(chemin.read_text(encoding="utf-8")) or {}
        lecteur = (document.get("source_table") or {}).get("reader")
        for corps in (document.get("parameters") or {}).values():
            valeur = (corps or {}).get("value") or {}
            if "from_source_table" not in valeur:
                continue
            if lecteur == "impots.macro.imk":
                fichiers.append(imk.DOCUMENTS[valeur["document"]])
            elif lecteur == "impots.macro.mesange":
                fichiers.append(mesange.SOURCE_FILE)
            else:
                raise DonneesError(
                    f"{chemin.name} : lecteur {lecteur!r} inconnu du préflight. Un lecteur "
                    f"ajouté au store sans l'être ici ferait déclarer « prêt » un store qui "
                    f"échouera au chargement.")
    return tuple(dict.fromkeys(fichiers))


def _valider_population(chemin: Path) -> str:
    """Le parquet porte-t-il le contrat que les étapes suivantes codent contre lui ?"""
    import polars as pl

    from impots.population.build import SCHEMA

    colonnes = pl.read_parquet_schema(chemin)
    manquantes = sorted(set(SCHEMA) - set(colonnes))
    if manquantes:
        raise DonneesError(f"colonnes absentes du parquet : {manquantes}")
    lignes = pl.scan_parquet(chemin).select(pl.len()).collect().item()
    if lignes == 0:
        raise DonneesError("parquet vide : une population sans ligne n'est pas une population")
    return f"{lignes:,} lignes, {len(SCHEMA)} colonnes du contrat".replace(",", " ")


def _valider_cellules(chemin: Path, *, millesime: str = "2023") -> str:
    """La vraie table de cellules, au bon millésime — et jamais la table FICTIVE des tests.

    `tests/fixtures/firm_cells.json` a exactement la même forme et se charge par le même
    `load_cells`. Copiée à cet emplacement, elle ferait passer les tests d'exactitude sur
    douze cellules inventées : c'est la raison pour laquelle `cells_are_synthetic` est lu
    ici et pas seulement affiché par `impots entreprises build`.
    """
    import json

    from impots.entreprises.build import load_cells

    brut = json.loads(chemin.read_text(encoding="utf-8"))
    if brut.get("cells_are_synthetic", True):
        raise DonneesError(
            "table marquée synthétique (ou sans le champ) : c'est la table FICTIVE des tests "
            "ou une copie d'elle, pas les cellules construites depuis Ésane × Focus 372 × "
            "DGFiP n° 39")
    cellules, ratio, vintage = load_cells(chemin)
    if vintage != millesime:
        raise DonneesError(f"millésime {vintage!r} au lieu de {millesime!r}")
    if not cellules:
        raise DonneesError("aucune cellule")
    return f"{len(cellules)} cellules, millésime {vintage}, ratio fiscal/comptable {ratio}"


def _valider_entreprises(chemin: Path) -> str:
    """La population d'entreprises servie aux études (IMPOTS_FIRM_VINTAGE=2023), construite
    sur les vraies cellules : son manifeste le dit, sinon elle est refusée (D-339)."""
    import json

    import polars as pl

    manifeste = json.loads(chemin.with_suffix(".manifest.json").read_text(encoding="utf-8"))
    if manifeste.get("cells_are_synthetic", True):
        raise DonneesError("construite sur des cellules synthétiques, pas sur Ésane × Focus 372")
    lignes = pl.scan_parquet(chemin).select(pl.len()).collect().item()
    if lignes == 0:
        raise DonneesError("parquet vide")
    tirees = f"{lignes:,}".replace(",", " ")
    return (f"{tirees} entreprises tirées, pour "
            f"{manifeste['population']['weighted_firms'] / 1e6:.2f} M")


def _construire_entreprises() -> Path:
    from impots.entreprises.build import build

    chemin, _provenance = build(cells_path=PROCESSED / "firm_cells_2023.json")
    return chemin


def _construire_population() -> Path:
    from impots.population.build import build

    chemin, _provenance = build(vintage="2024")
    return chemin


def _construire_cellules() -> Path:
    from impots.entreprises.cells import write_cell_table

    return write_cell_table(vintage="2023")


def profil_tests() -> tuple[Brut | Derive, ...]:
    """Ce que la suite `pytest -m ""` lit, déclaré depuis les lecteurs eux-mêmes."""
    from impots.entreprises import cells
    from impots.patrimoine import ifi_cells
    from impots.population import ingest, top_tail

    macro = tuple(Brut(f, "store macro — horizon de l'éventail (test_trajectoires)")
                  for f in _fichiers_du_store_macro())
    return (
        Brut(ifi_cells.TRANCHE_FILE, "tranches IFI publiées (test_accuracy, encadrement IFI)"),
        # `ifi_cells` lit DEUX fichiers. Le profil n'en déclarait qu'un, et les 25 échecs
        # de la CI en venaient tous (D-160) : le préflight passait au vert, puis la suite
        # tombait cinquante minutes plus tard sur un fichier absent — exactement ce que la
        # chaîne de données devait abolir.
        Brut(ifi_cells.AGGREGATE_FILE, "agrégats IFI publiés (test_patrimoine, test_accuracy)"),
        Brut(top_tail.WORKBOOK.name, "cibles des hauts revenus (test_top_tail)"),
        *macro,
        Brut(cells.ESANE_FILE, "cellules entreprises — entrée"),
        Brut(cells.FOCUS_FILE, "cellules entreprises — entrée"),
        Brut(cells.DGFIP_FILE, "cellules entreprises — entrée"),
        Brut(ingest.EEC_PARQUET, "population — entrée"),
        Brut(ingest.EEC_VARMOD, "population — entrée"),
        Brut(ingest.DECLARATIONS_2042, "cible de calage des pensions (test_population)"),
        Derive(
            chemin=PROCESSED / "firm_cells_2023.json",
            commande="impots entreprises cells",
            entrees=(cells.ESANE_FILE, cells.FOCUS_FILE, cells.DGFIP_FILE),
            pour="échantillonneur de placement des entreprises (test_accuracy)",
            valider=_valider_cellules, construire=_construire_cellules),
        # Après les cellules, dont elle est tirée : les études la lisent (D-339), et
        # `make data` ne la construisait pas — Retailleau est tombé sur son absence.
        Derive(
            chemin=PROCESSED / "firms_2023.parquet",
            commande="impots entreprises build --cells data/processed/firm_cells_2023.json",
            entrees=(cells.ESANE_FILE, cells.FOCUS_FILE, cells.DGFIP_FILE),
            pour="population d'entreprises des études (IMPOTS_FIRM_VINTAGE=2023)",
            valider=_valider_entreprises, construire=_construire_entreprises),
        Derive(
            chemin=PROCESSED / "population_2024.parquet",
            commande="impots population build",
            entrees=(ingest.EEC_PARQUET, ingest.EEC_VARMOD),
            pour="population construite (test_zero_masked, l'API)",
            valider=_valider_population, construire=_construire_population),
    )


PROFILS: dict[str, Callable[[], tuple[Brut | Derive, ...]]] = {"tests": profil_tests}


def profil(nom: str) -> tuple[Brut | Derive, ...]:
    if nom not in PROFILS:
        raise DonneesError(f"profil {nom!r} inconnu ; profils : {sorted(PROFILS)}")
    return PROFILS[nom]()


def bruts(elements: Iterable[Brut | Derive]) -> tuple[str, ...]:
    """Chaque fichier brut du profil, y compris les ENTRÉES des artefacts dérivés."""
    noms: list[str] = []
    for element in elements:
        noms.extend([element.fichier] if isinstance(element, Brut) else element.entrees)
    return tuple(dict.fromkeys(noms))


# --------------------------------------------------------------------------- #
# le téléchargement — par le manifeste, vérifié octet par octet
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Telechargement:
    fichier: str
    etat: str          # "déjà présent" | "téléchargé" | "échec"
    detail: str = ""


def _entree(fichier: str):
    from impots.population.ingest import load_manifest

    entree = load_manifest().get(fichier)
    if entree is None:
        raise DonneesError(f"{fichier} : absent du manifeste — rien ne dit d'où il vient")
    if entree.quarantined or not entree.url:
        raise DonneesError(
            f"{fichier} : en quarantaine ou sans URL. Une somme de contrôle prouve que des "
            f"octets n'ont pas changé, pas d'où ils viennent (D-028) ; ce fichier ne peut "
            f"pas être téléchargé par le manifeste.")
    return entree


#: Règle de normalisation « pdf-stamp-v1 » (D-159).
#:
#: EconStor régénère le PDF à chaque requête avec Apache FOP : le contenu est identique,
#: mais l'horodatage et l'identifiant du document sont réécrits. Trois téléchargements ont
#: donné trois sha256 pour exactement la même taille. Aucune empreinte BRUTE ne peut donc
#: correspondre à un téléchargement neuf, et ce n'est pas un changement de millésime.
#:
#: Les CINQ champs ci-dessous sont ceux que le diagnostic a MESURÉS comme variables, et
#: rien d'autre. Chaque remplacement a EXACTEMENT la longueur de ce qu'il remplace —
#: `normaliser` le vérifie et lève si ce n'est pas le cas, parce qu'une normalisation qui
#: change la taille déplacerait tout le reste du fichier et comparerait des octets décalés.
_PDF_STAMP_V1: tuple[tuple[re.Pattern[bytes], bytes], ...] = (
    (re.compile(rb"/CreationDate \(D:\d{14}[+\-]\d{2}'\d{2}'\)"),
     b"/CreationDate (D:00000000000000+00'00')"),
    (re.compile(rb"/ModDate \(D:\d{14}[+\-]\d{2}'\d{2}'\)"),
     b"/ModDate (D:00000000000000+00'00')"),
    (re.compile(rb"<dc:date>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+\-]\d{2}:\d{2}</dc:date>"),
     b"<dc:date>0000-00-00T00:00:00+00:00</dc:date>"),
    (re.compile(rb"<xmp:MetadataDate>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+\-]\d{2}:\d{2}"
                rb"</xmp:MetadataDate>"),
     b"<xmp:MetadataDate>0000-00-00T00:00:00+00:00</xmp:MetadataDate>"),
    (re.compile(rb"<xmp:CreateDate>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+\-]\d{2}:\d{2}"
                rb"</xmp:CreateDate>"),
     b"<xmp:CreateDate>0000-00-00T00:00:00+00:00</xmp:CreateDate>"),
    (re.compile(rb"/ID \[<[0-9A-Fa-f]{32}> <[0-9A-Fa-f]{32}>\]"),
     b"/ID [<" + b"0" * 32 + b"> <" + b"0" * 32 + b">]"),
)

NORMALISATIONS: dict[str, tuple[tuple[re.Pattern[bytes], bytes], ...]] = {
    "pdf-stamp-v1": _PDF_STAMP_V1,
}


def normaliser(donnees: bytes, regle: str) -> bytes:
    """Neutralise les champs d'horodatage d'un PDF ré-estampillé, et RIEN d'autre.

    La règle est nommée et versionnée : changer ce qui est neutralisé change le nom, donc
    se voit dans le manifeste et dans un diff. Une règle inconnue est refusée plutôt
    qu'ignorée — ignorée, elle rendrait les octets bruts et la comparaison passerait pour
    normalisée alors qu'elle ne le serait pas.
    """
    motifs = NORMALISATIONS.get(regle)
    if motifs is None:
        raise DonneesError(
            f"normalisation « {regle} » inconnue (connues : {sorted(NORMALISATIONS)}). "
            f"Refusée plutôt qu'ignorée : ignorée, elle laisserait passer une comparaison "
            f"brute sous une étiquette normalisée.")
    sortie = donnees
    for motif, gabarit in motifs:
        sortie = motif.sub(gabarit, sortie)
    if len(sortie) != len(donnees):
        raise DonneesError(
            f"la normalisation « {regle} » a changé la taille ({len(donnees)} → "
            f"{len(sortie)}) : un gabarit n'a pas la longueur de ce qu'il remplace, et "
            f"tout le reste du fichier s'en trouverait décalé.")
    return sortie


def empreinte(donnees: bytes, entree) -> str:
    """Le sha256 sur lequel `entree` doit être jugée : normalisé si elle le déclare."""
    if entree.normalization:
        return hashlib.sha256(normaliser(donnees, entree.normalization)).hexdigest()
    return hashlib.sha256(donnees).hexdigest()


def attendu(entree) -> str:
    """L'empreinte attendue, du même côté du contrat que `empreinte`."""
    if entree.normalization:
        if not entree.normalized_sha256:
            raise DonneesError(
                f"{entree.filename} : déclare « {entree.normalization} » mais ne porte "
                f"aucun `normalized_sha256`. Sans lui il n'y a rien à comparer, et le "
                f"fichier serait accepté sans vérification.")
        return entree.normalized_sha256
    return entree.sha256


def _conforme(chemin: Path, entree) -> bool:
    # D-151 : ce contrat est porté par DEUX fonctions — celle-ci et `telecharger`. Les
    # deux passent par `empreinte`/`attendu`, sans quoi `fetch` accepterait un fichier que
    # `check` déclarerait ensuite non conforme.
    if not (chemin.exists() and chemin.stat().st_size == entree.bytes):
        return False
    return empreinte(chemin.read_bytes(), entree) == attendu(entree)


def contexte_tls() -> ssl.SSLContext:
    """Le magasin de confiance du téléchargeur : celui d'OpenSSL, COMPLÉTÉ par `certifi`.

    Le Python qu'installe uv ne lit pas le trousseau de macOS mais le magasin d'OpenSSL,
    et deux sources sur douze y échouaient sur le Mac du propriétaire (D-231) : leurs
    racines, GlobalSign Root R46 et Sectigo Public Server Authentication Root R46, n'y
    sont pas. `certifi` porte la liste de Mozilla, qui les a. Le magasin d'OpenSSL n'est
    pas remplacé : un `SSL_CERT_FILE` posé par un proxy qui inspecte le TLS reste lu. Et
    la vérification reste entière, chaîne et nom d'hôte (D-232).
    """
    contexte = ssl.create_default_context()
    contexte.load_verify_locations(cafile=certifi.where())
    return contexte


def _ouvrir(requete: urllib.request.Request, timeout: int):
    return urllib.request.urlopen(requete, timeout=timeout, context=contexte_tls())


def telecharger(fichier: str, *, ouvrir: Callable = _ouvrir,
                timeout: int = TIMEOUT_S) -> Telechargement:
    """Télécharge UN fichier du manifeste, ou refuse. N'écrit jamais un fichier non conforme.

    Le flux est écrit dans un `.part` et haché au passage ; la taille ET le sha256 sont
    comparés au manifeste AVANT le renommage atomique. Un écart laisse le fichier final
    intact — absent s'il l'était — et le `.part` est supprimé. `ouvrir` est injectable pour
    que la garde de checksum se teste sans réseau.
    """
    entree = _entree(fichier)
    cible = RAW / fichier
    if _conforme(cible, entree):
        return Telechargement(fichier, "déjà présent")
    RAW.mkdir(parents=True, exist_ok=True)
    partiel = cible.with_name(cible.name + ".part")
    blocs: list[bytes] = []
    taille = 0
    depasse = False
    try:
        requete = urllib.request.Request(entree.url, headers={"User-Agent": USER_AGENT})
        with ouvrir(requete, timeout=timeout) as reponse, partiel.open("wb") as sortie:
            for bloc in iter(lambda: reponse.read(1 << 20), b""):
                blocs.append(bloc)
                taille += len(bloc)
                # Le manifeste connaît la taille : au-delà, c'est déjà un échec, et lire
                # la suite laissait le serveur choisir ce que ce processus garde en
                # mémoire (D-173).
                if taille > entree.bytes:
                    depasse = True
                    break
                sortie.write(bloc)
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        partiel.unlink(missing_ok=True)
        hote = entree.url.split("/")[2]
        return Telechargement(fichier, "échec", f"{hote} injoignable — {exc}")
    # D-151 : MÊME règle que `_conforme`, via les mêmes deux fonctions. Un contrat porté
    # par deux fonctions n'est pas élargi tant que les deux ne le sont pas.
    obtenu = empreinte(b"".join(blocs), entree)
    exige = attendu(entree)
    if taille != entree.bytes or obtenu != exige:
        partiel.unlink(missing_ok=True)
        precision = (f" (empreinte « {entree.normalization} »)" if entree.normalization
                     else "")
        return Telechargement(
            fichier, "échec",
            f"le fichier servi ne correspond PAS au manifeste — "
            f"{'au moins ' if depasse else ''}{taille} octets contre "
            f"{entree.bytes} attendus, sha256{precision} {obtenu[:16]}… contre "
            f"{exige[:16]}…. "
            f"Rien n'est écrit : si la publication a changé de millésime, c'est une "
            f"décision à consigner (D-004), pas une mise à jour silencieuse.")
    os.replace(partiel, cible)
    detail = f"{taille:,} octets, sha256 vérifié".replace(",", " ")
    if entree.normalization:
        detail += f" après normalisation « {entree.normalization} »"
    return Telechargement(fichier, "téléchargé", detail)


def elaguer_cache(raw: Path | None = None) -> list[str]:
    """Retire de `data/raw/` les fichiers que le manifeste ne source plus (D-205).

    Pour la CI : quand le manifeste change, son cache se replie sur celui d'un manifeste
    plus ancien, et peut ramener un fichier dont l'entrée a disparu ou perdu son URL.
    Un fichier encore sourcé reste, conforme ou non : `telecharger` remplace celui qui
    ne l'est plus, et `verifier` le juge. Ni le manifeste ni un sous-dossier ne sont
    touchés. Renvoie les noms retirés.
    """
    from impots.population.ingest import load_manifest

    raw = raw or RAW
    sources = {nom for nom, entree in load_manifest().items()
               if entree.url and not entree.quarantined}
    retires = []
    for chemin in sorted(raw.iterdir()):
        if chemin.is_file() and chemin.name != "MANIFEST.json" and chemin.name not in sources:
            chemin.unlink()
            retires.append(chemin.name)
    return retires


# --------------------------------------------------------------------------- #
# le préflight — rapide, lisible, et qui dit quoi faire
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Etat:
    chemin: str
    ok: bool
    detail: str
    reparer: str = ""
    pour: str = ""


def verifier(elements: Iterable[Brut | Derive], *, profil_nom: str = "tests") -> list[Etat]:
    """L'état de chaque dépendance, et la commande qui répare chaque ligne rouge.

    Un artefact dérivé dont une entrée manque est signalé comme tel : le reconstruire
    échouerait, et la commande à lancer d'abord est le téléchargement.
    """
    etats: list[Etat] = []
    elements = tuple(elements)
    for element in elements:
        if isinstance(element, Brut):
            nom = f"data/raw/{element.fichier}"
            try:
                entree = _entree(element.fichier)
            except DonneesError as exc:
                etats.append(Etat(nom, False, str(exc), "corriger le manifeste", element.pour))
                continue
            if not element.chemin.exists():
                etats.append(Etat(nom, False, "absent",
                                  f"impots data fetch --profile {profil_nom}", element.pour))
            elif not _conforme(element.chemin, entree):
                etats.append(Etat(nom, False, "présent mais NE correspond PAS au manifeste",
                                  f"supprimer puis impots data fetch --profile {profil_nom}",
                                  element.pour))
            else:
                etats.append(Etat(nom, True, "présent, sha256 conforme", pour=element.pour))
            continue
        nom = str(element.chemin.relative_to(ROOT))
        entrees_manquantes = [f for f in element.entrees if not (RAW / f).exists()]
        if not element.chemin.exists():
            reparer = (f"impots data fetch --profile {profil_nom}, puis {element.commande}"
                       if entrees_manquantes else element.commande)
            detail = ("absent — et ses entrées manquent : " + ", ".join(entrees_manquantes)
                      if entrees_manquantes else "absent")
            etats.append(Etat(nom, False, detail, reparer, element.pour))
            continue
        try:
            resume = element.valider(element.chemin)
        # Large exprès : tout échec de validation, quelle qu'en soit la forme, est un
        # rouge à afficher — pas une trace à interpréter.
        except Exception as exc:
            etats.append(Etat(nom, False, f"présent mais invalide : {exc}",
                              f"supprimer puis {element.commande}", element.pour))
            continue
        etats.append(Etat(nom, True, resume, pour=element.pour))
    return etats


def preparer(nom: str = "tests") -> tuple[list[Telechargement], list[Etat]]:
    """Télécharger, construire ce qui peut l'être, puis vérifier. Le bootstrap en un appel."""
    elements = profil(nom)
    telechargements = [telecharger(f) for f in bruts(elements)]
    for element in elements:
        if isinstance(element, Derive) and not element.chemin.exists() \
                and all((RAW / f).exists() for f in element.entrees):
            element.construire()
    return telechargements, verifier(elements, profil_nom=nom)
