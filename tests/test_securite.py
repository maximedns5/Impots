"""La passe de sécurité (but 4, D-295) : la CORS, les clés, le débit, la concurrence.

Les quatre protections que `docs/BUT.md` exige avant toute instance ouverte (D-173). Les
tests passent par l'application réelle et ses variables d'environnement, et chacun des
quatre groupes a été vu échouer sur le code d'avant : `*` pour toute origine, aucun calcul
refusé faute de clé, aucune limite de débit, deux passes sur la population à la fois.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import threading

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from impots.api import main

CLE = "une-cle-de-test-assez-longue"
EMPREINTE = hashlib.sha256(CLE.encode()).hexdigest()
TIERS = "https://exemple.org"
#: Refusé par le schéma (422) une fois les gardes passées : prouve qu'on les a passées
#: sans faire tourner le moteur.
CORPS_INVALIDE = {"household": "pas un foyer"}
VARIABLES = ("IMPOTS_AUTH", "IMPOTS_CLES_SHA256", "IMPOTS_CORS_ORIGINS", "IMPOTS_DEBIT",
             "IMPOTS_DEBIT_CALCULS", "IMPOTS_CALCULS_LOURDS")


def _reset() -> None:
    try:
        from impots.api import securite
    except ImportError:
        return
    securite.ETAT.reinitialiser()


@pytest.fixture
def env(monkeypatch):
    """Les réglages par défaut, ceux d'un serveur que personne n'a configuré."""
    for name in VARIABLES:
        monkeypatch.delenv(name, raising=False)
    _reset()
    yield monkeypatch
    _reset()


@pytest.fixture
def client(env) -> TestClient:
    return TestClient(main.app)


# --------------------------------------------------------------------------- #
# 1. La CORS restreinte
# --------------------------------------------------------------------------- #

def test_a_third_party_origin_gets_no_cors_header(client) -> None:
    response = client.get("/health", headers={"Origin": TIERS})
    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers


def test_a_third_party_preflight_is_refused(client) -> None:
    response = client.options("/simulate", headers={
        "Origin": TIERS, "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type"})
    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


def test_the_null_origin_of_a_file_or_a_sandboxed_frame_is_refused(client) -> None:
    response = client.get("/health", headers={"Origin": "null"})
    assert "access-control-allow-origin" not in response.headers


def test_a_declared_origin_is_allowed_and_only_it(client, env) -> None:
    env.setenv("IMPOTS_CORS_ORIGINS", TIERS)
    allowed = client.get("/health", headers={"Origin": TIERS})
    assert allowed.headers["access-control-allow-origin"] == TIERS
    other = client.get("/health", headers={"Origin": "https://autre.org"})
    assert "access-control-allow-origin" not in other.headers
    preflight = client.options("/simulate", headers={
        "Origin": TIERS, "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "authorization,content-type"})
    assert preflight.status_code == 200


@pytest.mark.parametrize("value", ["*", "null", "exemple.org", f"{TIERS}/chemin"])
def test_an_origin_list_that_would_reopen_everything_is_refused(client, env, value) -> None:
    env.setenv("IMPOTS_CORS_ORIGINS", value)
    response = client.get("/health", headers={"Origin": TIERS})
    assert response.status_code == 500
    assert "IMPOTS_CORS_ORIGINS" in response.json()["detail"]


# --------------------------------------------------------------------------- #
# 2. Les clés
# --------------------------------------------------------------------------- #

def test_a_computation_is_closed_when_no_key_is_configured(client) -> None:
    response = client.post("/simulate", json=CORPS_INVALIDE)
    assert response.status_code == 503
    assert "IMPOTS_AUTH=aucune" in response.json()["detail"]
    assert client.get("/health").status_code == 200


@pytest.mark.parametrize("headers", [
    {}, {"Authorization": "Bearer autre"}, {"Authorization": CLE},
    {"Authorization": f"Basic {CLE}"}, {"Authorization": "Bearer "},
])
def test_a_computation_without_the_right_key_is_refused(client, env, headers) -> None:
    env.setenv("IMPOTS_CLES_SHA256", EMPREINTE)
    response = client.post("/simulate", json=CORPS_INVALIDE, headers=headers)
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_the_right_key_reaches_the_computation(client, env) -> None:
    env.setenv("IMPOTS_CLES_SHA256", f"{'0' * 64}, {EMPREINTE.upper()}")
    response = client.post("/simulate", json=CORPS_INVALIDE,
                           headers={"Authorization": f"Bearer {CLE}"})
    assert response.status_code == 422


def test_reads_stay_public_when_keys_are_required(client, env) -> None:
    env.setenv("IMPOTS_CLES_SHA256", EMPREINTE)
    assert client.get("/scenarios").status_code == 200


def test_auth_aucune_opens_computations_explicitly(client, env) -> None:
    env.setenv("IMPOTS_AUTH", "aucune")
    assert client.post("/simulate", json=CORPS_INVALIDE).status_code == 422


@pytest.mark.parametrize("name, value", [
    ("IMPOTS_AUTH", "non"), ("IMPOTS_CLES_SHA256", "pas-une-empreinte"),
    ("IMPOTS_CLES_SHA256", CLE), ("IMPOTS_DEBIT", "beaucoup"),
    ("IMPOTS_CALCULS_LOURDS", "0"),
])
def test_an_unreadable_setting_closes_rather_than_opens(client, env, name, value) -> None:
    env.setenv(name, value)
    response = client.post("/simulate", json=CORPS_INVALIDE)
    assert response.status_code == 500
    assert name in response.json()["detail"]


def test_an_unreadable_setting_stops_the_server_at_start(env) -> None:
    env.setenv("IMPOTS_AUTH", "non")
    with pytest.raises(Exception, match="IMPOTS_AUTH"), TestClient(main.app):
        pass


def test_starting_without_keys_or_open_beyond_localhost_is_said(env, caplog) -> None:
    with caplog.at_level(logging.WARNING, logger="impots"), TestClient(main.app):
        pass
    assert "IMPOTS_CLES_SHA256" in caplog.text
    caplog.clear()
    env.setenv("IMPOTS_AUTH", "aucune")
    env.setenv("UVICORN_HOST", "0.0.0.0")
    with caplog.at_level(logging.WARNING, logger="impots"), TestClient(main.app):
        pass
    assert "IMPOTS_AUTH=aucune" in caplog.text


# --------------------------------------------------------------------------- #
# 3. Le débit
# --------------------------------------------------------------------------- #

def test_requests_beyond_the_rate_are_refused_with_a_delay(client, env) -> None:
    env.setenv("IMPOTS_DEBIT", "3")
    assert [client.get("/health").status_code for _ in range(4)] == [200, 200, 200, 429]
    refused = client.get("/health")
    assert refused.status_code == 429
    assert 1 <= int(refused.headers["retry-after"]) <= 60
    assert "3 requêtes" in refused.json()["detail"]


def test_computations_have_their_own_lower_rate(client, env) -> None:
    env.setenv("IMPOTS_AUTH", "aucune")
    env.setenv("IMPOTS_DEBIT_CALCULS", "2")
    codes = [client.post("/simulate", json=CORPS_INVALIDE).status_code for _ in range(3)]
    assert codes == [422, 422, 429]
    assert client.get("/health").status_code == 200


def test_attempts_without_a_key_count_against_the_rate(client, env) -> None:
    env.setenv("IMPOTS_CLES_SHA256", EMPREINTE)
    env.setenv("IMPOTS_DEBIT_CALCULS", "2")
    codes = [client.post("/simulate", json=CORPS_INVALIDE,
                         headers={"Authorization": "Bearer faux"}).status_code
             for _ in range(3)]
    assert codes == [401, 401, 429]


def test_the_rate_is_counted_per_client(env) -> None:
    env.setenv("IMPOTS_DEBIT", "1")
    one = TestClient(main.app, client=("192.0.2.1", 1000))
    two = TestClient(main.app, client=("192.0.2.2", 1000))
    codes = [one.get("/health").status_code, one.get("/health").status_code,
             two.get("/health").status_code]
    assert codes == [200, 429, 200]


def test_the_window_slides(client, env) -> None:
    from impots.api import securite

    now = [1000.0]
    env.setattr(securite.ETAT, "clock", lambda: now[0])
    env.setenv("IMPOTS_DEBIT", "1")
    assert client.get("/health").status_code == 200
    now[0] += 59.0
    assert client.get("/health").status_code == 429
    now[0] += 2.0
    assert client.get("/health").status_code == 200


def test_zero_lifts_a_rate_and_the_defaults_are_on(env) -> None:
    from impots.api import securite

    config = securite.configuration()
    assert (config.auth, config.cles_sha256, config.cors_origins) == ("cle", frozenset(), ())
    assert (config.debit, config.debit_calculs, config.lourds) == (120, 20, 1)
    env.setenv("IMPOTS_DEBIT", "0")
    client = TestClient(main.app)
    assert all(client.get("/health").status_code == 200 for _ in range(130))


# --------------------------------------------------------------------------- #
# 4. Le plafond de concurrence
# --------------------------------------------------------------------------- #

def test_the_capped_routes_are_the_app_s_population_passes() -> None:
    from impots.api import securite

    posts = {route.path for route in main.app.routes
             if "POST" in (getattr(route, "methods", None) or ())}
    assert posts >= securite.ROUTES_LOURDES
    assert {"/population/simulate", "/predictif/simulate"} == securite.ROUTES_LOURDES


def test_a_second_population_pass_is_refused_while_one_runs(env) -> None:
    env.setenv("IMPOTS_AUTH", "aucune")
    entered, release = threading.Event(), threading.Event()

    def blocked_frame():
        entered.set()
        release.wait(10)
        raise HTTPException(status_code=409, detail="fin du calcul de test")

    env.setattr(main, "_population_frame", blocked_frame)
    body = {"reform": {"decote_seuil_celib": 1000.0}, "year": 2024}

    async def scenario():
        transport = httpx.ASGITransport(app=main.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
            first = asyncio.create_task(http.post("/population/simulate", json=body))
            await asyncio.to_thread(entered.wait, 10)
            try:
                second = await asyncio.wait_for(http.post("/predictif/simulate", json={}), 5)
                light = await asyncio.wait_for(http.post("/simulate", json=CORPS_INVALIDE), 5)
            finally:
                release.set()
            done = await first
            entered.clear()
            after = await asyncio.wait_for(
                http.post("/population/simulate", json=body), 10)
            return done, second, light, after

    done, second, light, after = asyncio.run(scenario())
    assert second.status_code == 503
    assert int(second.headers["retry-after"]) > 0
    assert "à la fois" in second.json()["detail"]
    assert light.status_code == 422, "le plafond ne vise que les passes sur la population"
    assert done.status_code == 409
    assert after.status_code == 409, "un calcul fini, même en erreur, rend sa place"


# --------------------------------------------------------------------------- #
# Les gardes, chacune pour elle-même
# --------------------------------------------------------------------------- #

def test_an_empty_key_never_opens_even_if_its_print_were_configured() -> None:
    from impots.api import securite

    empty = securite.empreinte("")
    scope = {"headers": [(b"authorization", b"Bearer ")]}
    assert not securite._cle_valide(scope, frozenset({empty}))
    with pytest.raises(securite.ConfigurationError, match="clé vide"):
        securite.configuration({"IMPOTS_CLES_SHA256": empty})


def test_the_security_pass_closes_on_an_unreadable_setting_on_its_own(env) -> None:
    """La CORS, devant elle, refuse déjà : la garde de la passe doit tenir seule, si
    l'ordre des couches change."""
    from impots.api import securite

    async def open_app(scope, receive, send):
        await httpx_ok(send)

    env.setenv("IMPOTS_AUTH", "non")

    async def call():
        transport = httpx.ASGITransport(app=securite.Securite(open_app))
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
            return await http.get("/health")

    response = asyncio.run(call())
    assert response.status_code == 500
    assert "IMPOTS_AUTH" in response.json()["detail"]


async def httpx_ok(send) -> None:
    await send({"type": "http.response.start", "status": 200, "headers": []})
    await send({"type": "http.response.body", "body": b"ouvert"})
