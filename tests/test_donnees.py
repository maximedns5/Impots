"""La chaîne de préparation des données — et les gardes qui la rendent digne de confiance.

Aucun test ici ne touche le réseau : le téléchargement est testé par injection de la
fonction d'ouverture, et le manifeste par une entrée synthétique. Ce qui compte n'est pas
qu'un serveur réponde, c'est que la réponse ne soit ÉCRITE que si elle est la bonne.

Les deux gardes les plus importantes sont celles qui empêchent de tricher sans le vouloir :

* un fichier servi dont la taille ou le sha256 diffère du manifeste n'est JAMAIS écrit ;
* la table de cellules FICTIVE des tests n'est JAMAIS acceptée à la place de la vraie.
"""

from __future__ import annotations

import hashlib
import io
import json
import urllib.error
from dataclasses import asdict, fields
from pathlib import Path

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

    attendus = {ifi_cells.TRANCHE_FILE, top_tail.WORKBOOK.name, cells.ESANE_FILE,
                cells.FOCUS_FILE, cells.DGFIP_FILE, ingest.EEC_PARQUET, ingest.EEC_VARMOD,
                *donnees._fichiers_du_store_macro()}
    assert attendus <= set(donnees.bruts(donnees.profil("tests")))


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
