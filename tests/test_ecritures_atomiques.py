"""Les caches partagés s'écrivent d'un coup (D-309).

Les taux marginaux se gardent dans `data/processed`, que deux processus peuvent lire et
écrire en même temps : deux requêtes de l'API, ou deux workers de pytest-xdist. Écrit en
place, un fichier à moitié écrit se lisait comme un parquet tronqué. Il s'écrit désormais
à côté, puis prend son nom d'un seul `os.replace`.
"""

from __future__ import annotations

import inspect
from pathlib import Path

import polars as pl
import pytest

from impots.behavioural import emtr

NAME = "emtr_2024_0123456789abcdef.parquet"


def test_a_cache_written_halfway_leaves_no_file_under_its_name(tmp_path, monkeypatch) -> None:
    def broken(self, path, *args, **kwargs):
        Path(path).write_bytes(b"PAR1 tronque")
        raise OSError("disque plein")

    monkeypatch.setattr(pl.DataFrame, "write_parquet", broken)
    with pytest.raises(OSError, match="disque plein"):
        emtr._write_atomically(pl.DataFrame({"emtr": [0.5]}), tmp_path / NAME)
    assert list(tmp_path.iterdir()) == []


def test_a_cache_written_whole_reads_back_and_leaves_no_temporary(tmp_path) -> None:
    emtr._write_atomically(pl.DataFrame({"emtr": [0.5]}), tmp_path / NAME)
    assert pl.read_parquet(tmp_path / NAME)["emtr"].to_list() == [0.5]
    assert [p.name for p in tmp_path.iterdir()] == [NAME]


def test_the_temporary_is_never_taken_for_a_cache_by_the_eviction(tmp_path) -> None:
    """`_make_room` deletes only the names this cache writes: a temporary of another
    process, mid-write, is not one of them."""
    assert not emtr._temporary(tmp_path / NAME).name.endswith(".parquet")


def test_every_cache_write_of_the_module_goes_through_it() -> None:
    """Both caches — the baseline rates and a whole run — are written by the one helper;
    a `write_parquet` anywhere else in the module would write in place again."""
    source = inspect.getsource(emtr)
    assert source.count(".write_parquet(") == 1
    assert source.count("_write_atomically(") == 3  # its definition and the two writes
