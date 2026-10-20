"""La chaîne de préparation des données — et les gardes qui la rendent digne de confiance.

Aucun test ici ne touche le réseau : le téléchargement est testé par injection de la
fonction d'ouverture, et le manifeste par une entrée synthétique. Ce qui compte n'est pas
qu'un serveur réponde, c'est que la réponse ne soit ÉCRITE que si elle est la bonne. Seuls
les tests du magasin de confiance (D-232) ouvrent une vraie connexion TLS, sur 127.0.0.1,
vers un serveur qu'ils lancent eux-mêmes avec des certificats fabriqués pour l'occasion.

Les deux gardes les plus importantes sont celles qui empêchent de tricher sans le vouloir :

* un fichier servi dont la taille ou le sha256 diffère du manifeste n'est JAMAIS écrit ;
* la table de cellules FICTIVE des tests n'est JAMAIS acceptée à la place de la vraie.
"""

from __future__ import annotations

import contextlib
import hashlib
import http.server
import io
import json
import os
import ssl
import subprocess
import threading
import urllib.error
from dataclasses import asdict, fields
from pathlib import Path

import certifi
import pytest

from impots import donnees
from impots.population.ingest import ManifestEntry

CONTENU = b"octets publies par la source\n" * 64
EMPREINTE = hashlib.sha256(CONTENU).hexdigest()


class _Reponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def _servir(corps: bytes):
    appels: list[str] = []

    def ouvrir(requete, timeout):
        appels.append(requete.full_url)
        return _Reponse(corps)

    ouvrir.appels = appels
    return ouvrir


@pytest.fixture
def depot(tmp_path, monkeypatch):
    """Un data/raw vide et un manifeste d'une seule entrée, sourcée."""
    raw = tmp_path / "raw"
    raw.mkdir()
    monkeypatch.setattr(donnees, "RAW", raw)
    entree = ManifestEntry(
        filename="source.xlsx", url="https://www.example.invalid/source.xlsx",
        sha256=EMPREINTE, bytes=len(CONTENU), downloaded="2026-09-01",
        licence="Licence Ouverte / Etalab 2.0", description="source de test")
    monkeypatch.setattr("impots.population.ingest.load_manifest",
                        lambda: {"source.xlsx": entree})
    return raw


# --------------------------------------------------------------------------- #
# le téléchargement
# --------------------------------------------------------------------------- #
def test_a_file_whose_checksum_differs_from_the_manifest_is_never_written(depot) -> None:
    """LA garde du téléchargement. Vue échouer en retirant la comparaison sha256.

    Un millésime changé en silence produirait des chiffres plausibles, qui est le pire
    échec nommé de ce projet (D-007). Le fichier final doit rester ABSENT et aucun `.part`
    ne doit traîner derrière.
    """
    falsifie = CONTENU[:-1] + b"X"          # même taille, un octet différent
    resultat = donnees.telecharger("source.xlsx", ouvrir=_servir(falsifie))

    assert resultat.etat == "échec"
    assert "ne correspond PAS au manifeste" in resultat.detail
    assert not (depot / "source.xlsx").exists()
    assert not list(depot.glob("*.part"))


def test_a_file_of_the_wrong_size_is_refused_too(depot) -> None:
    """La taille est vérifiée en plus du sha256 : deux contrôles indépendants."""
    resultat = donnees.telecharger("source.xlsx", ouvrir=_servir(CONTENU + b"!"))
    assert resultat.etat == "échec" and not (depot / "source.xlsx").exists()


def test_a_conforming_file_is_written_and_verified(depot) -> None:
    resultat = donnees.telecharger("source.xlsx", ouvrir=_servir(CONTENU))
    assert resultat.etat == "téléchargé"
    assert hashlib.sha256((depot / "source.xlsx").read_bytes()).hexdigest() == EMPREINTE


def test_a_file_already_present_and_conforming_is_not_downloaded_again(depot) -> None:
    """Idempotent : la CI peut relancer la commande sur un cache restauré sans réseau."""
    (depot / "source.xlsx").write_bytes(CONTENU)

    def interdit(requete, timeout):
        raise AssertionError("aucun appel réseau ne devait avoir lieu")

    assert donnees.telecharger("source.xlsx", ouvrir=interdit).etat == "déjà présent"


def test_a_stale_file_restored_from_an_older_cache_is_downloaded_again(depot) -> None:
    """D-205 : le cache de la CI se replie sur celui d'un manifeste plus ancien, si bien
    qu'un fichier restauré peut porter l'ancien millésime sous le même nom et la même
    taille. Il n'est gardé que s'il est conforme. Fails if `_conforme` is reduced to a
    test of presence and size."""
    (depot / "source.xlsx").write_bytes(CONTENU[:-1] + b"X")
    servir = _servir(CONTENU)

    resultat = donnees.telecharger("source.xlsx", ouvrir=servir)

    assert resultat.etat == "téléchargé"
    assert servir.appels == ["https://www.example.invalid/source.xlsx"]
    assert (depot / "source.xlsx").read_bytes() == CONTENU


def test_the_cache_pruner_removes_only_what_the_manifest_no_longer_sources(depot) -> None:
    """D-205 : ce que le repli du cache peut ramener sans que le manifeste le source plus.
    Fails if the pruner keeps an unlisted file, or touches a listed one, the manifest or
    a subdirectory."""
    (depot / "source.xlsx").write_bytes(CONTENU[:-1] + b"X")    # sourcé, même périmé
    (depot / "retire.xlsx").write_bytes(b"une entree disparue")
    (depot / "MANIFEST.json").write_text("{}", encoding="utf-8")
    (depot / "_unsourced").mkdir()
    (depot / "_unsourced" / "quarantaine.pdf").write_bytes(b"q")

    assert donnees.elaguer_cache(depot) == ["retire.xlsx"]
    assert sorted(p.name for p in depot.iterdir()) == ["MANIFEST.json", "_unsourced",
                                                       "source.xlsx"]
    assert (depot / "_unsourced" / "quarantaine.pdf").exists()


def test_the_cache_pruner_removes_a_file_whose_entry_lost_its_url(depot, monkeypatch) -> None:
    """Une entrée mise en quarantaine garde sa somme de contrôle mais perd son URL : son
    fichier n'a plus sa place directement sous `data/raw/` (D-028), et
    `test_the_raw_tree_separates_sourced_from_unsourced` le refuserait."""
    entree = ManifestEntry(
        filename="source.xlsx", url=None, sha256=EMPREINTE, bytes=len(CONTENU),
        downloaded="2026-09-01", licence="unknown", description="source de test",
        quarantined=True)
    monkeypatch.setattr("impots.population.ingest.load_manifest",
                        lambda: {"source.xlsx": entree})
    (depot / "source.xlsx").write_bytes(CONTENU)

    assert donnees.elaguer_cache(depot) == ["source.xlsx"]


def test_a_network_failure_names_the_host_and_leaves_nothing_behind(depot) -> None:
    """C'est ce que rend ce conteneur : le proxy refuse les hôtes (403 au CONNECT)."""
    def refuse(requete, timeout):
        raise urllib.error.URLError("Tunnel connection failed: 403 Forbidden")

    resultat = donnees.telecharger("source.xlsx", ouvrir=refuse)
    assert resultat.etat == "échec"
    assert "www.example.invalid" in resultat.detail
    assert not list(depot.iterdir())


def test_a_quarantined_or_urlless_entry_is_refused(monkeypatch) -> None:
    """D-028 : une somme de contrôle prouve que des octets n'ont pas changé, pas d'où ils
    viennent. Un tel fichier ne peut pas être « téléchargé par le manifeste »."""
    entree = ManifestEntry(filename="orphelin.pdf", url=None, sha256="0" * 64, bytes=1,
                           downloaded="", licence="", description="", quarantined=True)
    monkeypatch.setattr("impots.population.ingest.load_manifest",
                        lambda: {"orphelin.pdf": entree})
    with pytest.raises(donnees.DonneesError, match="D-028"):
        donnees.telecharger("orphelin.pdf", ouvrir=_servir(b""))


def test_a_file_absent_from_the_manifest_is_refused(monkeypatch) -> None:
    monkeypatch.setattr("impots.population.ingest.load_manifest", lambda: {})
    with pytest.raises(donnees.DonneesError, match="absent du manifeste"):
        donnees.telecharger("inconnu.xlsx", ouvrir=_servir(b""))


# --------------------------------------------------------------------------- #
# le préflight
# --------------------------------------------------------------------------- #
def test_a_missing_raw_file_is_red_and_says_which_command_fixes_it(depot) -> None:
    etats = donnees.verifier([donnees.Brut("source.xlsx", "un test")])
    assert not etats[0].ok
    assert etats[0].reparer == "impots data fetch --profile tests"


def test_a_raw_file_that_drifted_from_the_manifest_is_red(depot) -> None:
    """Présent n'est pas conforme : un fichier remplacé à la main doit se voir."""
    (depot / "source.xlsx").write_bytes(CONTENU[:-1] + b"X")
    etats = donnees.verifier([donnees.Brut("source.xlsx", "un test")])
    assert not etats[0].ok and "NE correspond PAS" in etats[0].detail


def test_a_conforming_raw_file_is_green(depot) -> None:
    (depot / "source.xlsx").write_bytes(CONTENU)
    assert donnees.verifier([donnees.Brut("source.xlsx", "un test")])[0].ok


def _derive(chemin: Path, valider=lambda p: "ok") -> donnees.Derive:
    return donnees.Derive(chemin=chemin, commande="impots construit x",
                          entrees=("source.xlsx",), pour="un test", valider=valider,
                          construire=lambda: chemin)


def test_a_missing_derived_artefact_whose_inputs_are_missing_says_fetch_first(
        depot, tmp_path, monkeypatch) -> None:
    """Reconstruire échouerait : la commande à lancer d'abord est le téléchargement."""
    monkeypatch.setattr(donnees, "ROOT", tmp_path)
    etat = donnees.verifier([_derive(tmp_path / "x.json")])[0]
    assert not etat.ok
    assert "ses entrées manquent : source.xlsx" in etat.detail
    assert etat.reparer == "impots data fetch --profile tests, puis impots construit x"


def test_a_present_but_invalid_derived_artefact_is_red(depot, tmp_path,
                                                       monkeypatch) -> None:
    monkeypatch.setattr(donnees, "ROOT", tmp_path)
    (tmp_path / "x.json").write_text("{}", encoding="utf-8")

    def refuser(chemin):
        raise donnees.DonneesError("colonne manquante")

    etat = donnees.verifier([_derive(tmp_path / "x.json", refuser)])[0]
    assert not etat.ok and "invalide : colonne manquante" in etat.detail


# --------------------------------------------------------------------------- #
# les validateurs de schéma des deux artefacts dérivés
# --------------------------------------------------------------------------- #
def test_the_fictitious_test_cell_table_is_never_accepted_as_the_real_one() -> None:
    """LA garde anti-substitution. Vue échouer en retirant la lecture de
    `cells_are_synthetic` : la table FICTIVE de tests/fixtures/ était alors acceptée, et
    les tests d'exactitude auraient tourné sur douze cellules inventées."""
    fictive = Path(__file__).parent / "fixtures" / "firm_cells.json"
    with pytest.raises(donnees.DonneesError, match="FICTIVE"):
        donnees._valider_cellules(fictive)


def test_a_real_cell_table_at_the_wrong_vintage_is_refused(tmp_path) -> None:
    fictive = json.loads((Path(__file__).parent / "fixtures" / "firm_cells.json")
                         .read_text(encoding="utf-8"))
    table = dict(fictive, cells_are_synthetic=False, vintage="2021")
    chemin = tmp_path / "firm_cells_2023.json"
    chemin.write_text(json.dumps(table), encoding="utf-8")
    with pytest.raises(donnees.DonneesError, match="millésime"):
        donnees._valider_cellules(chemin)


def test_a_population_missing_a_contract_column_is_refused(tmp_path) -> None:
    import polars as pl

    from impots.population.build import SCHEMA

    colonnes = {nom: pl.Series([], dtype=type_) for nom, type_ in SCHEMA.items()}
    colonnes.pop(next(iter(SCHEMA)))
    chemin = tmp_path / "population_2024.parquet"
    pl.DataFrame(colonnes).write_parquet(chemin)
    with pytest.raises(donnees.DonneesError, match="colonnes absentes"):
        donnees._valider_population(chemin)


def test_an_empty_population_is_refused(tmp_path) -> None:
    import polars as pl

    from impots.population.build import SCHEMA

    chemin = tmp_path / "population_2024.parquet"
    pl.DataFrame({n: pl.Series([], dtype=t) for n, t in SCHEMA.items()}).write_parquet(chemin)
    with pytest.raises(donnees.DonneesError, match="vide"):
        donnees._valider_population(chemin)


# --------------------------------------------------------------------------- #
# le profil suit le code, pas une liste recopiée
# --------------------------------------------------------------------------- #
def test_the_macro_store_needs_three_documents_not_the_one_the_trace_named() -> None:
    """La trace de test_trajectoires ne nommait que wp117 — le PREMIER absent. Le store
    en matérialise trois, et les récupérer un par un aurait coûté trois runs."""
    assert set(donnees._fichiers_du_store_macro()) == {
        "imk_wp117_2013_gechert_meta_regression.pdf",
        "imk_wp139_2014_gechert_rannenberg_regime_dependent.pdf",
        "insee_G2017-04_mesange.pdf",
    }


def test_the_profile_is_built_from_the_readers_own_constants() -> None:
    """Un préflight qui vérifie moins que ce que le code lit est la forme D-044. Chaque
    constante de fichier des lecteurs en cause doit être dans le profil."""
    from impots.entreprises import cells
    from impots.patrimoine import ifi_cells
    from impots.population import ingest, top_tail

    # DÉRIVÉ PAR INTROSPECTION, jamais énuméré à la main. La version précédente listait
    # les constantes une à une, et cette liste OMETTAIT `ifi_cells.AGGREGATE_FILE` : deux
    # listes écrites de mémoire par la même personne s'accordent entre elles et se
    # trompent ensemble. C'est la forme D-044 commise dans la garde qui la dénonce, et
    # elle a coûté 25 échecs en CI (D-160).
    #
    # Le profil reste une DÉCLARATION explicite et relisible ; ce test dérive son attente
    # d'ailleurs. Les deux côtés doivent rester indépendants, sinon la garde ne peut plus
    # attraper ce que la déclaration oublie.
    extensions = (".xlsx", ".xls", ".csv", ".pdf", ".parquet", ".zip", ".html")
    attendus = set(donnees._fichiers_du_store_macro())
    for module in (cells, ifi_cells, ingest, top_tail):
        for nom in dir(module):
            if not nom.isupper():
                continue
            valeur = getattr(module, nom)
            fichier = (valeur if isinstance(valeur, str)
                       else getattr(valeur, "name", None) if isinstance(valeur, Path)
                       else None)
            if isinstance(fichier, str) and fichier.endswith(extensions):
                attendus.add(fichier)

    manquants = attendus - set(donnees.bruts(donnees.profil("tests")))
    assert not manquants, (
        f"le profil ne déclare pas {sorted(manquants)} — des fichiers que les lecteurs "
        f"NOMMENT pourtant. Le préflight passerait au vert et la suite tomberait dessus "
        f"bien plus tard, ce que la chaîne de données existe pour empêcher.")


def test_every_raw_file_of_the_profile_is_fetchable_from_the_real_manifest() -> None:
    """Contre le VRAI manifeste committé : chaque source du profil a une URL, un sha256,
    une taille, et n'est pas en quarantaine. Sinon `fetch` ne pourrait pas la produire."""
    for nom in donnees.bruts(donnees.profil("tests")):
        entree = donnees._entree(nom)
        assert entree.url and entree.sha256 and entree.bytes > 0, nom


def test_the_derived_artefacts_sit_where_their_readers_look() -> None:
    """Le préflight vérifie les chemins que les lecteurs ouvrent, pas des chemins voisins."""
    from impots import accuracy_cases
    from impots.population.build import PROCESSED

    derives = {e.chemin for e in donnees.profil("tests") if isinstance(e, donnees.Derive)}
    assert accuracy_cases.FIRM_CELLS in derives
    assert PROCESSED / "population_2024.parquet" in derives


def test_the_readers_paths_do_not_depend_on_the_current_directory(tmp_path,
                                                                   monkeypatch) -> None:
    """Quatre modules lisaient `Path("data/...")`, relatif au répertoire COURANT. Lancés
    hors de la racine, ils déclaraient absent un fichier présent."""
    from impots import accuracy_cases, reindustrialisation
    from impots.agregats import anchors
    from impots.population import top_tail

    monkeypatch.chdir(tmp_path)
    for chemin in (accuracy_cases.FIRM_CELLS, top_tail.WORKBOOK, anchors.ANCHOR_TABLE,
                   reindustrialisation.PERIMETER_TABLE):
        assert chemin.is_absolute() and chemin.is_relative_to(donnees.ROOT), chemin


def test_an_unknown_macro_reader_is_refused_rather_than_ignored(tmp_path,
                                                                monkeypatch) -> None:
    """Un lecteur ajouté au store sans l'être au préflight ferait déclarer « prêt » un
    store qui échouera au chargement."""
    from impots.macro import store as store_module

    (tmp_path / "x.yaml").write_text(
        "source_table:\n  reader: impots.macro.nouveau\n"
        "parameters:\n  p:\n    value: {from_source_table: t}\n", encoding="utf-8")
    monkeypatch.setattr(store_module, "PARAMETERS", tmp_path)
    with pytest.raises(donnees.DonneesError, match="inconnu du préflight"):
        donnees._fichiers_du_store_macro()


# --------------------------------------------------------------------------- #
# l'écrivain de la table de cellules — le maillon qui manquait
# --------------------------------------------------------------------------- #
def test_the_cell_table_writer_produces_what_load_cells_reads(tmp_path,
                                                             monkeypatch) -> None:
    """La plomberie, pas la donnée : `build_cells` est remplacé pour ne pas exiger les
    trois tableurs, et le test vérifie que l'écriture, le renommage atomique et la
    relecture par `load_cells` s'accordent — et que le validateur ACCEPTE ce qu'écrit
    l'écrivain réel (qui marque la table non synthétique) là où il refuse la fixture."""
    from impots.entreprises import cells as cells_module
    from impots.entreprises.build import load_cells

    fixture = json.loads((Path(__file__).parent / "fixtures" / "firm_cells.json")
                         .read_text(encoding="utf-8"))
    table = [cells_module.Cell(**c) for c in fixture["cells"]]
    provenance = cells_module.CellProvenance(
        vintage="2023", sources={}, fiscal_to_accounting=0.9, esane_firms=1.0,
        esane_turnover=1.0, is_liable_firms=1.0, is_share_by_size={},
        resultat_fiscal_national=1.0, esane_rcai_national=1.0)
    monkeypatch.setattr(cells_module, "build_cells", lambda raw, vintage: (table, provenance))
    monkeypatch.setattr(donnees, "PROCESSED", tmp_path)

    chemin = cells_module.write_cell_table(vintage="2023")

    assert chemin == tmp_path / "firm_cells_2023.json"
    assert not list(tmp_path.glob("*.part"))
    relues, ratio, vintage = load_cells(chemin)
    # Comparées par CONTENU : l'écrivain produit des `entreprises.cells.Cell` et
    # `load_cells` construit des `entreprises.population.Cell`. Deux classes, un contrat —
    # le JSON. Leur identité de champs est gardée par le test suivant.
    assert [asdict(c) for c in relues] == [asdict(c) for c in table]
    assert ratio == 0.9 and vintage == "2023"
    assert "cellules" in donnees._valider_cellules(chemin)


def test_the_writer_and_the_reader_define_the_same_cell() -> None:
    """Trouvé en écrivant le test précédent : il existe DEUX classes `Cell`, dans
    `entreprises/cells.py` (ce qu'écrit l'écrivain) et `entreprises/population.py` (ce que
    construit `load_cells`). Mêmes champs aujourd'hui, et le JSON fait la frontière.

    Le jour où l'une gagne un champ, `load_cells` lèverait une `TypeError` au chargement —
    la forme exacte de D-142, un schéma défini deux fois que rien ne compare. Ce test est
    ce qui compare.
    """
    from impots.entreprises import cells, population

    def champs(cls):
        return [(f.name, str(f.type), f.default) for f in fields(cls)]

    assert champs(cells.Cell) == champs(population.Cell)


# --------------------------------------------------------------------------- #
# la normalisation « pdf-stamp-v1 » (D-159)
# --------------------------------------------------------------------------- #
def _pdf(horodatage: str = "20260903111124", identifiant: str = "A" * 32,
         corps: bytes = b"contenu de page, identique d'un service a l'autre\n" * 32) -> bytes:
    """Un PDF minimal estampillé comme EconStor estampille les siens.

    Les cinq champs que le diagnostic a mesurés comme variables, dans leurs formes
    exactes — et du contenu autour, pour qu'un test puisse le modifier et voir la garde
    refuser.
    """
    iso = (f"{horodatage[:4]}-{horodatage[4:6]}-{horodatage[6:8]}T"
           f"{horodatage[8:10]}:{horodatage[10:12]}:{horodatage[12:14]}+02:00")
    return (
        b"%PDF-1.4\n/Creator (Apache FOP Version 2.8)\n"
        + f"/CreationDate (D:{horodatage}+02'00')\n".encode()
        + f"/ModDate (D:{horodatage}+02'00')\n".encode()
        + f"<dc:date>{iso}</dc:date>\n".encode()
        + f"<xmp:MetadataDate>{iso}</xmp:MetadataDate>\n".encode()
        + f"<xmp:CreateDate>{iso}</xmp:CreateDate>\n".encode()
        + corps
        + f"trailer\n<</ID [<{identifiant}> <{identifiant}>]>>\n%%EOF\n".encode())


def _entree_normalisee(donnees_pdf: bytes) -> ManifestEntry:
    return ManifestEntry(
        filename="imk.pdf", url="https://www.econstor.invalid/imk.pdf",
        sha256=hashlib.sha256(donnees_pdf).hexdigest(), bytes=len(donnees_pdf),
        downloaded="2026-09-03", licence="inconnue", description="working paper IMK",
        normalization="pdf-stamp-v1",
        normalized_sha256=hashlib.sha256(
            donnees.normaliser(donnees_pdf, "pdf-stamp-v1")).hexdigest())


@pytest.fixture
def depot_imk(tmp_path, monkeypatch):
    """Un dépôt dont l'unique entrée déclare la normalisation."""
    raw = tmp_path / "raw"
    raw.mkdir()
    monkeypatch.setattr(donnees, "RAW", raw)
    entree = _entree_normalisee(_pdf())
    monkeypatch.setattr("impots.population.ingest.load_manifest",
                        lambda: {"imk.pdf": entree})
    return raw


def test_a_re_stamped_pdf_is_accepted_because_only_the_stamp_moved(depot_imk) -> None:
    """LE cas pour lequel la règle existe.

    EconStor régénère le PDF à chaque requête : horodatage et /ID neufs, contenu
    identique. Trois téléchargements, trois sha256 bruts — aucune empreinte brute ne peut
    donc correspondre. Ici le fichier servi porte un AUTRE horodatage et un AUTRE
    identifiant que celui dont le manifeste a pris l'empreinte, et il doit passer.
    """
    servi = _pdf(horodatage="20260923172842", identifiant="B" * 32)
    entree = donnees._entree("imk.pdf")
    assert hashlib.sha256(servi).hexdigest() != entree.sha256, (
        "le PDF servi doit différer en BRUT, sinon le test ne teste rien")

    resultat = donnees.telecharger("imk.pdf", ouvrir=_servir(servi))
    assert resultat.etat == "téléchargé"
    assert "pdf-stamp-v1" in resultat.detail


def test_a_byte_changed_OUTSIDE_the_stamped_fields_is_still_refused(depot_imk) -> None:
    """LA garde de mise à mort : la règle ne doit pas s'être élargie au contenu.

    L'implémentation qui échoue ici est la tentation évidente — normaliser plus largement
    (tout ce qui ressemble à une date, ou le trailer entier) jusqu'à ce que « ça passe ».
    Un octet de contenu modifié est un fichier différent, et le reste.
    """
    # MÊME LONGUEUR que la ligne de référence, à l'octet près. Sans cela `telecharger`
    # refuserait sur la TAILLE et ce test passerait sans jamais exercer la comparaison
    # d'empreinte normalisée — il l'a fait, et c'est ainsi qu'on l'a découvert.
    reference = b"contenu de page, identique d'un service a l'autre\n"
    altere = b"contenu de page, ALTERE    d'un service a l'autre\n"
    assert len(altere) == len(reference), "le test doit isoler l'empreinte, pas la taille"
    falsifie = _pdf(corps=reference * 31 + altere)
    resultat = donnees.telecharger("imk.pdf", ouvrir=_servir(falsifie))

    assert resultat.etat == "échec"
    assert "ne correspond PAS au manifeste" in resultat.detail
    assert not (depot_imk / "imk.pdf").exists()
    assert not list(depot_imk.glob("*.part"))


def test_fetch_and_check_return_the_same_verdict_on_the_same_file(depot_imk) -> None:
    """Le piège D-151 : un contrat porté par DEUX fonctions.

    `telecharger` accepte le fichier et `_conforme` le relit ensuite — au préflight, et au
    raccourci « déjà présent ». Si une seule des deux connaissait la normalisation, `fetch`
    écrirait un fichier que `check` déclarerait aussitôt non conforme, et la CI
    oscillerait sans que rien ne soit faux.
    """
    servi = _pdf(horodatage="20260923172842", identifiant="C" * 32)
    assert donnees.telecharger("imk.pdf", ouvrir=_servir(servi)).etat == "téléchargé"

    entree = donnees._entree("imk.pdf")
    assert donnees._conforme(depot_imk / "imk.pdf", entree), (
        "check refuse ce que fetch vient d'accepter — le contrat n'est porté que d'un côté")

    def interdit(requete, timeout):
        raise AssertionError("le fichier est conforme : aucun appel réseau ne devait avoir lieu")

    assert donnees.telecharger("imk.pdf", ouvrir=interdit).etat == "déjà présent"


def test_an_entry_without_a_normalization_keeps_the_raw_comparison(depot) -> None:
    """Les 143 autres entrées ne changent pas de régime.

    La normalisation est déclarée PAR ENTRÉE. Une règle implicite, ou appliquée à tout ce
    qui finit en .pdf, affaiblirait la vérification de sources qui n'ont jamais prouvé en
    avoir besoin.
    """
    entree = donnees._entree("source.xlsx")
    assert entree.normalization is None
    assert donnees.attendu(entree) == entree.sha256
    assert donnees.empreinte(CONTENU, entree) == EMPREINTE
    assert donnees.telecharger("source.xlsx",
                               ouvrir=_servir(CONTENU[:-1] + b"X")).etat == "échec"


def test_an_unknown_normalization_is_refused_rather_than_ignored() -> None:
    """Ignorée, elle rendrait les octets bruts et une comparaison BRUTE passerait pour
    normalisée — c'est-à-dire une garde qui ment sur ce qu'elle a vérifié."""
    with pytest.raises(donnees.DonneesError, match="inconnue"):
        donnees.normaliser(_pdf(), "pdf-stamp-v2")


def test_a_declared_normalization_without_its_digest_is_refused() -> None:
    """Sans `normalized_sha256` il n'y a rien à comparer : le fichier serait accepté sans
    vérification du tout, ce qui est pire que la comparaison brute qu'on remplace."""
    entree = ManifestEntry(
        filename="imk.pdf", url="https://www.econstor.invalid/imk.pdf",
        sha256="0" * 64, bytes=10, downloaded="2026-09-03", licence="inconnue",
        description="", normalization="pdf-stamp-v1")
    with pytest.raises(donnees.DonneesError, match="normalized_sha256"):
        donnees.attendu(entree)


def test_the_normalization_preserves_length_and_only_touches_the_five_fields() -> None:
    """La taille est le second contrôle, indépendant du sha256 : un gabarit plus court
    décalerait tout le fichier et on comparerait des octets qui ne se correspondent plus.
    """
    avant = _pdf(horodatage="20260923172842", identifiant="D" * 32)
    apres = donnees.normaliser(avant, "pdf-stamp-v1")
    assert len(apres) == len(avant)
    differents = [i for i, (x, y) in enumerate(zip(avant, apres, strict=True)) if x != y]
    assert differents, "la normalisation n'a rien changé — elle ne normalise donc rien"
    # Le corps de page doit être intact d'un bout à l'autre.
    assert b"contenu de page, identique d'un service a l'autre" in apres
    assert apres.count(b"contenu de page") == avant.count(b"contenu de page")


# Les dépendances déclarées ont déménagé dans `impots.dependances`, avec leurs tests
# dans `tests/test_dependances.py` (D-165) : la même logique vivait ici ET dans
# `scripts/ci_local.py`, et deux copies d'un contrat dérivent (D-151).


def test_a_download_stops_reading_once_it_passes_the_manifest_size(depot):
    """Fails if `telecharger` reads to the end before comparing sizes. The stream was
    kept whole in memory, so a server sending more than it announced chose how much
    this process held (D-173). The manifest's byte count bounds the read."""
    lus: list[int] = []

    class _Bavarde(_Reponse):
        def read(self, n=-1):
            bloc = super().read(n)
            lus.append(len(bloc))
            return bloc

    resultat = donnees.telecharger(
        "source.xlsx", ouvrir=lambda requete, timeout: _Bavarde(CONTENU * 4096))
    assert resultat.etat == "échec"
    assert sum(lus) <= len(CONTENU) + (1 << 20)
    assert not (depot / "source.xlsx").exists()
    assert not (depot / "source.xlsx.part").exists()


def test_an_unknown_file_is_a_refusal_not_a_traceback(depot, capsys):
    from impots.population import cli

    assert cli.main(["data", "fetch", "inconnu.xlsx"]) == 2
    assert "inconnu.xlsx" in capsys.readouterr().err


# --------------------------------------------------------------------------- #
# le magasin de confiance (D-232) : une vraie poignée de main TLS, sur 127.0.0.1
# --------------------------------------------------------------------------- #
def _openssl(dossier: Path, *args: str) -> None:
    subprocess.run(["openssl", *args], cwd=dossier, check=True, capture_output=True)


def _autorite(dossier: Path, nom: str) -> None:
    (dossier / "autorite.ext").write_text(
        "basicConstraints=critical,CA:TRUE\nkeyUsage=critical,keyCertSign,cRLSign\n"
        "subjectKeyIdentifier=hash\n", encoding="utf-8")
    _openssl(dossier, "genrsa", "-out", f"{nom}.key", "2048")
    _openssl(dossier, "req", "-new", "-key", f"{nom}.key", "-subj", f"/CN={nom}",
             "-out", f"{nom}.csr")
    _openssl(dossier, "x509", "-req", "-in", f"{nom}.csr", "-signkey", f"{nom}.key",
             "-days", "2", "-sha256", "-extfile", "autorite.ext", "-out", f"{nom}.pem")


def _certificat(dossier: Path, nom: str, autorite: str, nom_alternatif: str,
                serie: int) -> None:
    (dossier / f"{nom}.ext").write_text(
        "basicConstraints=CA:FALSE\nkeyUsage=critical,digitalSignature,keyEncipherment\n"
        f"extendedKeyUsage=serverAuth\nsubjectAltName={nom_alternatif}\n"
        "subjectKeyIdentifier=hash\nauthorityKeyIdentifier=keyid\n", encoding="utf-8")
    _openssl(dossier, "req", "-new", "-key", "serveur.key", "-subj", "/CN=serveur",
             "-out", f"{nom}.csr")
    _openssl(dossier, "x509", "-req", "-in", f"{nom}.csr", "-CA", f"{autorite}.pem",
             "-CAkey", f"{autorite}.key", "-set_serial", str(serie), "-days", "2",
             "-sha256", "-extfile", f"{nom}.ext", "-out", f"{nom}.pem")


@pytest.fixture(scope="module")
def pki(tmp_path_factory) -> Path:
    """Deux autorités et trois certificats de serveur, fabriqués par `openssl` à chaque
    session : rien de cryptographique n'est commité. « racine » joue la racine que
    `certifi` porte et que le magasin d'OpenSSL n'a pas — GlobalSign Root R46 ou Sectigo
    Public Server Authentication Root R46 sur le Mac du propriétaire (D-231). « inconnue »
    n'est dans aucun magasin."""
    dossier = tmp_path_factory.mktemp("pki")
    _autorite(dossier, "racine")
    _autorite(dossier, "inconnue")
    _openssl(dossier, "genrsa", "-out", "serveur.key", "2048")
    _certificat(dossier, "valide", "racine", "IP:127.0.0.1", 1)
    _certificat(dossier, "orphelin", "inconnue", "IP:127.0.0.1", 2)
    _certificat(dossier, "autre_hote", "racine", "DNS:autre.invalid", 3)
    return dossier


@pytest.fixture
def sans_proxy(monkeypatch) -> None:
    """127.0.0.1 en direct. Sans aucune variable de proxy, urllib lirait sur macOS les
    réglages du système ; `no_proxy=*` l'en empêche."""
    for nom in list(os.environ):
        if nom.lower().endswith("_proxy"):
            monkeypatch.delenv(nom)
    monkeypatch.setenv("no_proxy", "*")


@contextlib.contextmanager
def _servi_en_tls(pki: Path, certificat: str, monkeypatch):
    """Sert CONTENU en HTTPS sur 127.0.0.1, et pointe l'entrée du manifeste dessus."""
    class Page(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            self.send_response(200)
            self.send_header("Content-Length", str(len(CONTENU)))
            self.end_headers()
            self.wfile.write(CONTENU)

        def log_message(self, *args) -> None:
            pass

    serveur = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Page)
    contexte = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    contexte.load_cert_chain(pki / f"{certificat}.pem", pki / "serveur.key")
    serveur.socket = contexte.wrap_socket(serveur.socket, server_side=True)
    fil = threading.Thread(target=serveur.serve_forever, daemon=True)
    fil.start()
    entree = ManifestEntry(
        filename="source.xlsx",
        url=f"https://127.0.0.1:{serveur.server_address[1]}/source.xlsx",
        sha256=EMPREINTE, bytes=len(CONTENU), downloaded="2026-10-20",
        licence="Licence Ouverte / Etalab 2.0", description="source servie en TLS")
    monkeypatch.setattr("impots.population.ingest.load_manifest",
                        lambda: {"source.xlsx": entree})
    try:
        yield
    finally:
        serveur.shutdown()
        serveur.server_close()


def test_a_root_that_only_certifi_carries_is_trusted(depot, pki, sans_proxy,
                                                     monkeypatch) -> None:
    """LA GARDE DE D-232. Le Python qu'installe uv lit le magasin d'OpenSSL, pas le
    trousseau de macOS, et deux sources sur douze y échouaient sur le Mac du propriétaire :
    Eurostat (« unable to get local issuer certificate ») et France Stratégie
    (« self-signed certificate in certificate chain »). Leurs racines sont dans `certifi`.
    Ici « racine » n'est que là, et le téléchargement doit passer, par l'ouverture par
    défaut — celle que `impots data fetch` appelle."""
    monkeypatch.setattr(certifi, "where", lambda: str(pki / "racine.pem"))
    with _servi_en_tls(pki, "valide", monkeypatch):
        resultat = donnees.telecharger("source.xlsx")
    assert resultat.etat == "téléchargé", resultat.detail
    assert (depot / "source.xlsx").read_bytes() == CONTENU


def test_the_system_store_is_completed_not_replaced(depot, pki, sans_proxy,
                                                    monkeypatch) -> None:
    """Le jumeau. `SSL_CERT_FILE` est ce que pose un proxy qui inspecte le TLS, comme celui
    du conteneur où ce code est écrit. Remplacer le magasin par celui de `certifi` aurait
    réparé le Mac et cassé ces environnements-là : ici « racine » n'est que dans
    `SSL_CERT_FILE`, et `certifi` est le vrai."""
    monkeypatch.setenv("SSL_CERT_FILE", str(pki / "racine.pem"))
    with _servi_en_tls(pki, "valide", monkeypatch):
        resultat = donnees.telecharger("source.xlsx")
    assert resultat.etat == "téléchargé", resultat.detail


@pytest.mark.parametrize("certificat", ["orphelin", "autre_hote"])
def test_completing_the_store_does_not_loosen_the_check(depot, pki, sans_proxy, monkeypatch,
                                                        certificat) -> None:
    """Compléter le magasin n'est pas assouplir la vérification. Un certificat signé par
    une autorité que personne ne porte, ou valide pour un autre hôte, reste refusé, et rien
    n'est écrit — même avec « racine » dans `certifi`. La forme fautive est connue : un
    `CERT_NONE` ou un `check_hostname = False` « pour que ça passe »."""
    monkeypatch.setattr(certifi, "where", lambda: str(pki / "racine.pem"))
    with _servi_en_tls(pki, certificat, monkeypatch):
        resultat = donnees.telecharger("source.xlsx")
    assert resultat.etat == "échec"
    assert "CERTIFICATE_VERIFY_FAILED" in resultat.detail
    assert not list(depot.iterdir())
