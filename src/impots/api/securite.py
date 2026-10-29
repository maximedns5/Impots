"""La passe de sécurité avant toute instance ouverte (but 4, D-295).

`docs/BUT.md` exige quatre protections avant tout déploiement, que D-173 avait laissées
au propriétaire. Elles sont ici, fermées par défaut, et chacune se règle par une variable
d'environnement.

1. LA CORS RESTREINTE. Aucune origine tierce par défaut : l'interface est servie par
   l'API elle-même (`/`), à la même origine, et n'a pas besoin de CORS.
   `IMPOTS_CORS_ORIGINS` en déclare, séparées par des virgules, chacune un schéma et un
   hôte. `*` et `null` sont refusés : `null` est l'origine d'un fichier ouvert depuis le
   disque, mais aussi celle d'une iframe isolée de n'importe quel site. Ouvrir
   `ui/index.html` depuis le disque ne marche donc plus ; `http://localhost:8000` le
   remplace.
2. LES CLÉS. Toute requête POST est un calcul, et un calcul exige une clé
   (`Authorization: Bearer <clé>`). Le serveur n'en garde que l'empreinte SHA-256
   (`IMPOTS_CLES_SHA256`, séparées par des virgules). Sans clé configurée, les calculs
   sont FERMÉS (503) : un oubli ferme, il n'ouvre pas. `IMPOTS_AUTH=aucune` les ouvre sans
   clé, pour l'usage local ou une instance publique voulue, et le démarrage le dit s'il
   écoute au-delà de la boucle locale. Les lectures (GET) restent publiques : ce sont des
   rapports précalculés, et le débit les borne.
3. LE DÉBIT. Par client, sur une fenêtre glissante d'une minute : `IMPOTS_DEBIT` requêtes
   (120 par défaut) et `IMPOTS_DEBIT_CALCULS` calculs (20) ; 0 retire la limite. Au-delà,
   429 et `Retry-After`. Les tentatives sans clé comptent : deviner une clé coûte du
   débit. Le client est `scope["client"]` : derrière un mandataire, uvicorn doit être
   lancé avec `--proxy-headers --forwarded-allow-ips=<mandataire>` pour que ce soit le
   vrai client, et non le mandataire pour tout le monde.
4. LA CONCURRENCE. Les deux routes qui font une passe sur la population partagent un
   plafond, `IMPOTS_CALCULS_LOURDS` à la fois (1 par défaut). Au-delà, 503 et
   `Retry-After`, tout de suite : une file d'attente tiendrait des fils du serveur pendant
   des minutes.

La configuration se relit à chaque requête, et une valeur illisible ferme (500) au lieu
d'ouvrir ; le démarrage la lit aussi, et refuse de démarrer sur une valeur illisible. L'état
(fenêtres de débit, calculs en cours) vit dans le processus : avec plusieurs workers,
chaque limite vaut par worker.
"""

from __future__ import annotations

import hashlib
import hmac
import math
import os
import re
import threading
import time
from collections import deque
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

#: Les routes qui font une passe sur la population : de 30 s à 1 min 30 chacune (D-173).
ROUTES_LOURDES = frozenset({"/population/simulate", "/predictif/simulate"})
FENETRE_S = 60.0
DEBIT = 120
DEBIT_CALCULS = 20
CALCULS_LOURDS = 1
#: Le délai conseillé quand le plafond est atteint : l'ordre d'une passe rapide.
ATTENTE_LOURDE_S = 30
#: Au-delà, les fenêtres périmées sont purgées, puis toutes si cela ne suffit pas : la
#: mémoire reste bornée quel que soit le nombre d'adresses qui se présentent.
CLIENTS_MAX = 10_000

_ORIGINE = re.compile(r"https?://[A-Za-z0-9.\-\[\]:]+")
_EMPREINTE = re.compile(r"[0-9a-f]{64}")


class ConfigurationError(ValueError):
    """Une variable d'environnement de la passe de sécurité ne se lit pas."""


@dataclass(frozen=True)
class Configuration:
    cors_origins: tuple[str, ...]
    auth: str
    cles_sha256: frozenset[str]
    debit: int
    debit_calculs: int
    lourds: int


def _liste(environ: Mapping[str, str], name: str) -> list[str]:
    return [part.strip() for part in environ.get(name, "").split(",") if part.strip()]


def _entier(environ: Mapping[str, str], name: str, default: int, minimum: int = 0) -> int:
    raw = environ.get(name, "").strip()
    if not raw:
        return default
    if not raw.isdigit() or int(raw) < minimum:
        raise ConfigurationError(f"{name}={raw!r} : un entier, au moins {minimum}.")
    return int(raw)


def configuration(environ: Mapping[str, str] | None = None) -> Configuration:
    """Les réglages, lus et vérifiés ; une valeur illisible lève plutôt que d'ouvrir."""
    environ = os.environ if environ is None else environ
    auth = environ.get("IMPOTS_AUTH", "").strip() or "cle"
    if auth not in ("cle", "aucune"):
        raise ConfigurationError(f"IMPOTS_AUTH={auth!r} : « cle » (par défaut) ou "
                                 f"« aucune ».")
    cles = frozenset(h.lower() for h in _liste(environ, "IMPOTS_CLES_SHA256"))
    if any(not _EMPREINTE.fullmatch(h) for h in cles):
        raise ConfigurationError("IMPOTS_CLES_SHA256 : des empreintes SHA-256 en "
                                 "hexadécimal, 64 caractères chacune, jamais les clés "
                                 "elles-mêmes.")
    if empreinte("") in cles:
        raise ConfigurationError("IMPOTS_CLES_SHA256 porte l'empreinte d'une clé vide : "
                                 "elle ouvrirait les calculs à qui n'envoie rien.")
    origins = tuple(_liste(environ, "IMPOTS_CORS_ORIGINS"))
    for origin in origins:
        if not _ORIGINE.fullmatch(origin):
            raise ConfigurationError(f"IMPOTS_CORS_ORIGINS : {origin!r} n'est pas une "
                                     f"origine (un schéma http ou https et un hôte, sans "
                                     f"chemin) ; « * » et « null » ne le sont jamais.")
    return Configuration(
        cors_origins=origins, auth=auth, cles_sha256=cles,
        debit=_entier(environ, "IMPOTS_DEBIT", DEBIT),
        debit_calculs=_entier(environ, "IMPOTS_DEBIT_CALCULS", DEBIT_CALCULS),
        lourds=_entier(environ, "IMPOTS_CALCULS_LOURDS", CALCULS_LOURDS, minimum=1),
    )


def empreinte(cle: str) -> str:
    """L'empreinte à mettre dans `IMPOTS_CLES_SHA256` pour une clé."""
    return hashlib.sha256(cle.encode("utf-8")).hexdigest()


class Etat:
    """Ce que les requêtes partagent : les fenêtres de débit et les calculs en cours."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self.clock = clock
        self._lock = threading.Lock()
        self._fenetres: dict[tuple[str, str], deque[float]] = {}
        self._lourds = 0

    def reinitialiser(self) -> None:
        with self._lock:
            self._fenetres.clear()
            self._lourds = 0

    def compter(self, client: str, quoi: str, limite: int) -> int | None:
        """Compte une requête ; rend le délai d'attente en secondes si la limite est
        atteinte, sans la compter, et None sinon."""
        if limite == 0:
            return None
        now = self.clock()
        with self._lock:
            fenetre = self._fenetres.setdefault((client, quoi), deque())
            while fenetre and fenetre[0] <= now - FENETRE_S:
                fenetre.popleft()
            if len(fenetre) >= limite:
                return max(1, math.ceil(fenetre[0] + FENETRE_S - now))
            fenetre.append(now)
            if len(self._fenetres) > CLIENTS_MAX:
                self._purger(now)
            return None

    def _purger(self, now: float) -> None:
        for key in [k for k, f in self._fenetres.items() if not f or f[-1] <= now - FENETRE_S]:
            del self._fenetres[key]
        if len(self._fenetres) > CLIENTS_MAX:
            self._fenetres.clear()

    def prendre(self, plafond: int) -> bool:
        with self._lock:
            if self._lourds >= plafond:
                return False
            self._lourds += 1
            return True

    def rendre(self) -> None:
        with self._lock:
            self._lourds -= 1


ETAT = Etat()


def _refus(status: int, detail: str, headers: dict[str, str] | None = None) -> JSONResponse:
    return JSONResponse({"detail": detail}, status_code=status, headers=headers)


def _cle_valide(scope: dict, cles: frozenset[str]) -> bool:
    header = dict(scope.get("headers") or ()).get(b"authorization", b"")
    scheme, _, token = header.decode("latin-1").partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return False
    presented = empreinte(token.strip())
    # Toutes les empreintes sont comparées, à temps constant chacune.
    return any([hmac.compare_digest(presented, cle) for cle in cles])


class Securite:
    """Le débit, puis la clé, puis le plafond de concurrence, avant la route."""

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        try:
            config = configuration()
        except ConfigurationError as error:
            await _refus(500, str(error))(scope, receive, send)
            return
        calcul = scope["method"] == "POST"
        client = (scope.get("client") or ("inconnu", 0))[0]

        for quoi, limite in (("requêtes", config.debit),
                             ("calculs", config.debit_calculs if calcul else 0)):
            attente = ETAT.compter(client, quoi, limite)
            if attente is not None:
                await _refus(429, f"Trop de requêtes : au plus {limite} {quoi} par minute. "
                                  f"Réessayez dans {attente} s.",
                             {"Retry-After": str(attente)})(scope, receive, send)
                return

        if calcul and config.auth == "cle":
            if not config.cles_sha256:
                await _refus(503, "Les calculs sont fermés : aucune clé d'accès n'est "
                                  "configurée sur ce serveur (IMPOTS_CLES_SHA256). Pour "
                                  "un usage local, lancez-le avec IMPOTS_AUTH=aucune."
                             )(scope, receive, send)
                return
            if not _cle_valide(scope, config.cles_sha256):
                await _refus(401, "Une clé d'accès est requise pour calculer : envoyez "
                                  "« Authorization: Bearer <clé> ».",
                             {"WWW-Authenticate": "Bearer"})(scope, receive, send)
                return

        if calcul and scope["path"] in ROUTES_LOURDES:
            if not ETAT.prendre(config.lourds):
                await _refus(503, f"Un calcul sur la population est déjà en cours : au "
                                  f"plus {config.lourds} à la fois. Réessayez dans un "
                                  f"moment.",
                             {"Retry-After": str(ATTENTE_LOURDE_S)})(scope, receive, send)
                return
            try:
                await self.app(scope, receive, send)
            finally:
                ETAT.rendre()
            return
        await self.app(scope, receive, send)


class Cors:
    """La CORS, sur les origines déclarées à l'instant de la requête, et aucune sinon."""

    def __init__(self, app: Any) -> None:
        self.app = app
        self._par_origines: dict[tuple[str, ...], CORSMiddleware] = {}

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        try:
            origins = configuration().cors_origins
        except ConfigurationError as error:
            await _refus(500, str(error))(scope, receive, send)
            return
        inner = self._par_origines.get(origins)
        if inner is None:
            inner = self._par_origines[origins] = CORSMiddleware(
                self.app, allow_origins=list(origins), allow_credentials=False,
                allow_methods=["GET", "POST"],
                allow_headers=["Authorization", "Content-Type"])
        await inner(scope, receive, send)
