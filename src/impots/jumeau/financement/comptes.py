"""Le compte des APU par sous-secteur, et la compensation (D-481).

LE COMPTE CONSOLIDÉ NE CHANGE PAS. Ce module lit une trajectoire du jumeau (la
référence et la variante, `trajectoire.calculer`) et la répartit, année par année, entre
l'État (S13111), les ODAC (S13112), les APUL (S1313) et les ASSO (S1314) ; dans les ASSO,
l'écart d'une mesure se range par branche. Il n'écrit rien dans l'état du jumeau.

LES IDENTITÉS (vérifiées à chaque année, 1e-9 du PIB, sur chaque tirage, `verifier`) :

1. Σ_s recettes_s = recettes des APU (hors intérêts) ; Σ_s dépenses_s = dépenses
   primaires ; Σ_s intérêts nets_s = intérêts nets ;
2. Σ_s transferts reçus_s = Σ_s transferts versés_s (les transferts entre APU, D73, D9 et
   la compensation, se consolident) ;
3. B9_s = recettes_s + reçus_s − dépenses_s − versés_s − intérêts_s, et Σ_s B9_s = B9 ;
4. D_s,t = D_s,t−1 − B9_s,t + A_s,t, et Σ_s D_s = D (A : l'ajustement flux-stocks et
   les écarts de publication du jumeau, nuls en projection, aux parts de la dette) ;
5. dans les ASSO, la somme des écarts des branches est l'écart des ASSO.

Sur les comptes publiés de 2025 (`financement_sous_secteurs.yaml`), la somme des quatre
sous-secteurs redonne chaque ligne de la t. 3.201 à 5e-4 Md€ près, hors D41, D73 et D9,
consolidées entre sous-secteurs, dont la consolidation est la même en recettes et en
dépenses (143,072 Md€ de D73, 30,578 de D9, 0,880 de D41) : B9 se somme exactement.

LA RÉPARTITION (des conventions, chacune dite) :

* la référence : chaque ligne du compte consolidé aux parts de ses sous-secteurs en 2025
  (t. 3.203 à 3.212) ; les transferts entre APU de 2025 suivent le PIB nominal ; les
  intérêts nets aux parts de 2025 ; la dette d'ouverture aux parts de fin 2025 ;
* l'écart d'une mesure : son choc statique (les contributions du bloc `mesures`) au
  payeur que disent ses instruments (`Mesure.impulsions`, `financement.yaml`), le reste
  au prorata de la ligne ; les effets induits (les autres blocs) aux parts de leur ligne,
  et ceux qu'un bloc ne ventile pas (`solde_induit`) à la clé des prélèvements ; les
  intérêts de l'écart au prorata de la dette accumulée de chaque compte ;
* la compensation (CSS, L131-7) : la perte de recette d'une branche sur un instrument
  compensable est payée par l'État, en transfert, au taux de l'option de la branche
  (compensée 1, non compensée 0, θ quand l'issue est incertaine).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from impots.jumeau.champs import DEPENSES, RECETTES

PARAMS = Path(__file__).resolve().parents[1] / "parametres"
SECTEURS = ("etat", "odac", "apul", "asso")
TOLERANCE = 1e-9
OPTIONS = ("compensee", "non_compensee", "theta")
#: Les champs du compte que le jumeau écrit sans ligne publiée.
NON_VENTILES = ("solde_induit", "mesures_non_ventilees")


class FinancementError(ValueError):
    """Une répartition que le module refuse."""


@cache
def parametres() -> dict[str, Any]:
    p = yaml.safe_load((PARAMS / "financement.yaml").read_text(encoding="utf-8"))
    p["publie"] = yaml.safe_load((PARAMS / "financement_sous_secteurs.yaml")
                                 .read_text(encoding="utf-8"))
    return p


def branches() -> tuple[str, ...]:
    return tuple(parametres()["branches"])


def comptes() -> tuple[str, ...]:
    """Les comptes de l'écart : trois sous-secteurs, puis les branches des ASSO."""
    return ("etat", "odac", "apul", *(f"asso.{b}" for b in branches()))


def secteur(compte: str) -> str:
    return compte.split(".")[0]


# --------------------------------------------------------------------- les clés
def _normer(poids: Mapping[str, float]) -> dict[str, float]:
    """Des poids en parts qui somment à 1 au bit : la dernière part est le complément."""
    total = sum(poids.values())
    if total == 0:
        raise FinancementError(f"clé de somme nulle : {dict(poids)}")
    cles = list(poids)
    out = {c: poids[c] / total for c in cles[:-1]}
    out[cles[-1]] = 1.0 - sum(out.values())
    return out


def parts_ligne(nom: str) -> dict[str, float]:
    """Les parts des sous-secteurs dans une ligne du compte, en 2025 (brutes de la
    consolidation : la part externe et la part entre APU se répartissent pareil)."""
    lignes = parametres()["publie"]["lignes"]
    if nom in NON_VENTILES:
        return cle_prelevements()
    if nom not in lignes:
        raise FinancementError(f"ligne « {nom} » sans parts publiées")
    ligne = lignes[nom]
    poids = {s: float(ligne[s]) for s in SECTEURS}
    if sum(poids.values()) == 0:
        return cle_prelevements() if nom.startswith("apu_r") else cle_depenses()
    return _normer(poids)


@cache
def cle_prelevements() -> dict[str, float]:
    """Les impôts et cotisations reçus par sous-secteur en 2025 (D2, D5, D91, D733, D61,
    D995), la clé des effets induits que les blocs ne ventilent pas."""
    lignes = parametres()["publie"]["lignes"]
    noms = ("apu_r_d2", "apu_r_d5", "apu_r_d91", "apu_r_d733", "apu_r_d61", "apu_r_d995")
    return _normer({s: sum(float(lignes[n][s]) for n in noms) for s in SECTEURS})


@cache
def cle_depenses() -> dict[str, float]:
    """Les dépenses primaires hors transferts entre APU, par sous-secteur, en 2025."""
    lignes = parametres()["publie"]["lignes"]
    noms = [n for n in DEPENSES if n in lignes and n not in ("apu_d_d73", "apu_d_d9")]
    return _normer({s: sum(float(lignes[n][s]) for n in noms) for s in SECTEURS})


#: Les branches des fiches (`transmission.BRANCHES`) dont le compte porte un autre nom.
BRANCHE_COMPTE = {"vieillesse": "vieillesse_base", "chomage": "unedic",
                  "retraite_complementaire": "complementaires"}


def _payeurs_fiche(cle: str) -> dict[str, float | None]:
    """{compte : part dite par la fiche, ou None} des APU qui paient une mesure."""
    from impots.jumeau import transmission

    candidat, mesure = cle.split("/")
    out: dict[str, float | None] = {}
    for p in transmission.fiche(candidat, mesure)["payeurs"] or ():
        qui = str(p["qui"])
        if p["sens"] != "paie" or not qui.startswith("apu:"):
            continue
        compte = qui.removeprefix("apu:")
        if compte.startswith("secu:"):
            branche = compte.removeprefix("secu:")
            compte = f"asso.{BRANCHE_COMPTE.get(branche, branche)}"
        if compte not in comptes():
            raise FinancementError(f"{cle} : payeur « {qui} » sans compte ({comptes()})")
        part = p.get("part")
        out[compte] = (out.get(compte) or 0.0) + float(part) if part is not None else None
    if not out:
        raise FinancementError(f"{cle} : la fiche ne nomme aucune APU qui paie")
    return out


def payeurs_fiche(cle: str) -> tuple[str, ...]:
    """Les comptes des APU qui paient une mesure, lus dans sa fiche de transmission (le
    volet `carte`, `payeurs`, sens « paie ») : `apu:etat` → l'État, `apu:apul`, `apu:odac`,
    `apu:secu:<branche>` → la branche des ASSO (D-487 ; `vieillesse` → la CNAV et les
    régimes de base, `retraite_complementaire` → les complémentaires, `chomage` →
    l'Unédic, D-510)."""
    return tuple(_payeurs_fiche(cle))


def cle_reste(mesure: str | None, cote: str) -> dict[str, float]:
    """La clé du choc statique d'une mesure que ses impulsions ne portent pas (`reste`).
    Par défaut, la clé des prélèvements (recettes) ou des dépenses ; quand
    `financement.yaml` (`mesures.<mesure>.reste`) nomme une ligne du compte et la fiche
    de la mesure, les parts de cette ligne en 2025 restreintes aux payeurs que la fiche
    nomme, renormées (D-487 : le point d'indice, payé par l'État, les APUL et les
    hôpitaux, et non à la clé des prélèvements). Quand la fiche dit la part de chacun de
    ses payeurs, ce sont ces parts (D-510)."""
    propre = ((parametres().get("mesures") or {}).get(mesure or "") or {}).get("reste")
    if not propre:
        return _comme_comptes(cle_prelevements() if cote == "recettes" else cle_depenses())
    dites = _payeurs_fiche(propre["fiche"])
    if all(v is not None for v in dites.values()):
        # La fiche dit la part de chaque payeur (le volet `fiches`, D-504) : elle passe
        # avant les parts de la ligne (D-510). Une part nulle n'est pas un payeur.
        return _normer({cp: v for cp, v in dites.items() if v})
    parts = parts_ligne(propre["ligne"])
    payeurs = payeurs_fiche(propre["fiche"])
    poids = {cp: parts[secteur(cp)] for cp in payeurs}
    par_secteur: dict[str, int] = {}
    for cp in payeurs:
        par_secteur[secteur(cp)] = par_secteur.get(secteur(cp), 0) + 1
    # Deux branches des ASSO nommées : la part des ASSO se partage, faute de mieux, à parts
    # égales (dit) ; une seule : elle prend la part des ASSO.
    poids = {cp: v / par_secteur[secteur(cp)] for cp, v in poids.items()}
    return _normer(poids)


def _comme_comptes(parts: Mapping[str, float]) -> dict[str, float]:
    """Des parts par sous-secteur en parts par compte (les ASSO au non ventilé)."""
    return {("asso.asso_non_ventile" if s == "asso" else s): v for s, v in parts.items()}


def affectation(instrument: str, mesure: str | None, theta: Mapping[str, Any]
                ) -> dict[str, Any]:
    """{compte : part} d'un instrument pour une mesure. Une part peut être un tableau de
    tirages (un θ)."""
    p = parametres()
    propre = (p.get("mesures") or {}).get(mesure or "", {}).get(instrument)
    if propre is not None:
        out: dict[str, Any] = {}
        for compte, v in propre.items():
            if compte not in comptes():
                raise FinancementError(f"compte « {compte} » inconnu ({mesure})")
            if isinstance(v, str) and v.startswith("theta:"):
                out[compte] = valeur_theta(v.removeprefix("theta:"), theta)
            elif v != "reste":
                out[compte] = float(v)
        restes = [c for c, v in propre.items() if v == "reste"]
        if len(restes) > 1:
            raise FinancementError(f"deux « reste » pour {mesure}, {instrument}")
        if restes:
            out[restes[0]] = 1.0 - sum(out.values())
        return out
    if instrument not in p["instruments"]:
        raise FinancementError(f"instrument « {instrument} » sans payeur "
                               f"(financement.yaml, instruments)")
    a = p["instruments"][instrument]["affectation"]
    if a == "depenses":
        return _comme_comptes(cle_depenses())
    if isinstance(a, str) and a.startswith("ligne:"):
        return _comme_comptes(parts_ligne(a.removeprefix("ligne:")))
    for compte in a:
        if compte not in comptes():
            raise FinancementError(f"compte « {compte} » inconnu ({instrument})")
    return _normer({c: float(v) for c, v in a.items()})


def valeur_theta(cle: str, theta: Mapping[str, Any]) -> Any:
    """La valeur d'un θ du volet : a_zero + θ (a_un − a_zero). Un θ sans réglage est
    refusé, comme partout dans le jumeau."""
    ligne = parametres()["thetas"][cle]
    if cle not in theta:
        raise FinancementError(f"θ « {cle} » sans réglage : il n'a pas de défaut")
    t = np.asarray(theta[cle], dtype=float)
    return ligne["a_zero"] + t * (ligne["a_un"] - ligne["a_zero"])


def taux_compensation(compte: str, options: Mapping[str, str],
                      theta: Mapping[str, Any]) -> Any:
    """La part de la perte d'un compte des ASSO que l'État compense."""
    if not compte.startswith("asso."):
        return 0.0
    b = compte.removeprefix("asso.")
    option = options.get(b) or parametres()["compensation"]["defaut"][b]
    if option not in OPTIONS:
        raise FinancementError(f"option « {option} » inconnue ({OPTIONS})")
    if option == "compensee":
        return 1.0
    if option == "non_compensee":
        return 0.0
    return valeur_theta("financement_compensation", theta)


# --------------------------------------------------------------------- le compte
@dataclass
class CompteSousSecteurs:
    """Les postes par scénario (« reference », « variante », « ecart »), compte et année,
    chacun de forme (années, tirages). Les sous-secteurs ont les trois scénarios ; les
    branches des ASSO, l'écart seulement."""

    annees: tuple[int, ...]
    n: int
    postes: dict[tuple[str, str, str], np.ndarray] = field(default_factory=dict)
    compensation: dict[str, np.ndarray] = field(default_factory=dict)
    """Par compte des ASSO, le transfert de l'État de chaque année (Md€)."""
    residus: dict[str, float] = field(default_factory=dict)

    def get(self, scenario: str, compte: str, poste: str) -> np.ndarray:
        """Un poste ; un compte de l'écart qu'aucune mesure ne touche est nul."""
        cle = (scenario, compte, poste)
        if cle not in self.postes and scenario == "ecart":
            return np.zeros((len(self.annees), self.n))
        return self.postes[cle]

    def _ajouter(self, scenario: str, compte: str, poste: str, k: int, v: Any) -> None:
        cle = (scenario, compte, poste)
        if cle not in self.postes:
            self.postes[cle] = np.zeros((len(self.annees), self.n))
        self.postes[cle][k] += np.broadcast_to(np.asarray(v, dtype=float), (self.n,))


POSTES = ("recettes", "depenses", "transferts_recus", "transferts_verses",
          "interets_nets", "b9", "dette")


def _parts_dette() -> dict[str, float]:
    d = parametres()["publie"]["dette"]
    return _normer({s: float(d[s]) for s in SECTEURS})


def _parts_interets() -> dict[str, float]:
    lignes = parametres()["publie"]["lignes"]
    v, r = lignes["interets_verses"], lignes["interets_recus"]
    return _normer({s: float(v[s]) - float(r[s]) for s in SECTEURS})


def _repartir(total: Any, parts: Mapping[str, Any]) -> dict[str, Any]:
    """Un total en parts, la dernière en complément : la somme redonne le total au bit
    près quand les parts sont des scalaires."""
    cles = list(parts)
    out = {c: total * parts[c] for c in cles[:-1]}
    reste = total
    for v in out.values():
        reste = reste - v
    out[cles[-1]] = reste
    return out


def _statique(etat: Any, champs: Sequence[str]) -> dict[str, dict[str, np.ndarray]]:
    """{mesure : {champ : contribution}} du bloc `mesures` (le choc statique)."""
    out: dict[str, dict[str, np.ndarray]] = {}
    for nom in champs:
        if not etat.present(nom):
            continue
        for (origine, mesure), v in etat.de(nom).items():
            if origine == "mesures" and mesure:
                out.setdefault(mesure, {})[nom] = v
    return out


def _avec_publics(m: Any) -> dict[int, dict[str, float]]:
    """Les impulsions d'une mesure et les cotisations de la rémunération publique qu'elle
    porte à part (D-500) : le compte des sous-secteurs range les deux de la même façon."""
    out = {a: dict(v) for a, v in (m.impulsions or {}).items()}
    for a, v in (getattr(m, "prelevements_publics", None) or {}).items():
        for i, x in v.items():
            out.setdefault(a, {})[i] = out.get(a, {}).get(i, 0.0) + float(x)
    return out


def decomposer(traj: Any, mesures: Sequence[Any], theta: Mapping[str, Any] | None = None,
               options: Mapping[str, str] | None = None) -> CompteSousSecteurs:
    """Le compte par sous-secteur d'une trajectoire, et la compensation."""
    theta, options = dict(theta or {}), dict(options or {})
    publie = parametres()["publie"]
    annees = tuple(traj.annees)
    n = traj.reference[0].n
    c = CompteSousSecteurs(annees, n)
    impulsions = {m.identifiant: _avec_publics(m) for m in mesures}
    inter = {nom: float(publie["lignes"][nom]["consolidation"])
             for nom in ("apu_r_d73", "apu_r_d9", "apu_d_d73", "apu_d_d9")}
    pib0 = None
    instruments_comp = set(parametres()["compensation"]["instruments"])
    for k, annee in enumerate(annees):
        ref, var = traj.reference[k], traj.variante[k]
        if pib0 is None:
            pib0 = ref["pib"]
        g = ref["pib"] / pib0
        # ---- la référence, par sous-secteur
        for scen in ("reference", "variante"):
            for nom, cote in [(r, "recettes") for r in RECETTES] + [
                    (d, "depenses") for d in DEPENSES]:
                if not ref.present(nom):
                    continue
                for s, v in _repartir(ref[nom], parts_ligne(nom)).items():
                    c._ajouter(scen, s, cote, k, v)
            # les transferts entre APU de 2025, au PIB nominal (ils se consolident)
            for nom, cote in (("apu_r_d73", "transferts_recus"), ("apu_r_d9", "transferts_recus"),
                              ("apu_d_d73", "transferts_verses"),
                              ("apu_d_d9", "transferts_verses")):
                for s, v in _repartir(inter[nom] * g, parts_ligne(nom)).items():
                    c._ajouter(scen, s, cote, k, v)
            for s, v in _repartir(ref["interets_nets"], _parts_interets()).items():
                c._ajouter(scen, s, "interets_nets", k, v)
        # ---- l'écart, par compte
        statique = _statique(var, RECETTES + DEPENSES)
        for nom, cote in [(r, "recettes") for r in RECETTES] + [
                (d, "depenses") for d in DEPENSES]:
            delta = (var[nom] if var.present(nom) else 0.0) - (
                ref[nom] if ref.present(nom) else 0.0)
            if not np.any(delta):
                continue
            stat = sum((statique.get(m, {}).get(nom, 0.0) for m in statique), np.zeros(n))
            induit = delta - stat
            for s, v in _repartir(induit, _comme_comptes(parts_ligne(nom))).items():
                c._ajouter("ecart", s, cote, k, v)
        for m, champs in statique.items():
            for cote, noms in (("recettes", RECETTES), ("depenses", DEPENSES)):
                total = sum((v for nom, v in champs.items() if nom in noms), np.zeros(n))
                if not np.any(total):
                    continue
                imp = {i: float(x) for i, x in (impulsions.get(m, {}).get(annee) or {}).items()}
                # le signe : une impulsion est un coût (expansionniste) ; une recette
                # perdue, une dépense accrue. Les instruments de dépense vont aux
                # dépenses, les autres aux recettes.
                depense = {"depense_publique", "investissement_public"}
                du_cote = {i: (x if i in depense else -x) for i, x in imp.items()
                           if (i in depense) == (cote == "depenses")}
                reste = total - sum(du_cote.values(), 0.0)
                for i, montant in du_cote.items():
                    for compte, part in affectation(i, m, theta).items():
                        v = montant * part
                        c._ajouter("ecart", compte, cote, k, v)
                        if i in instruments_comp and compte.startswith("asso."):
                            perte = np.maximum(-np.broadcast_to(v, (n,)), 0.0)
                            t = perte * taux_compensation(compte, options, theta)
                            c._ajouter("ecart", "etat", "transferts_verses", k, t)
                            c._ajouter("ecart", compte, "transferts_recus", k, t)
                            c.compensation.setdefault(
                                compte, np.zeros((len(annees), n)))[k] += t
                for s, v in _repartir(reste, cle_reste(m, cote)).items():
                    c._ajouter("ecart", s, cote, k, v)
        # ---- les intérêts de l'écart, au prorata de la dette accumulée de chaque compte
        d_int = var["interets_nets"] - ref["interets_nets"]
        if k == 0:
            dettes = {cp: np.zeros(n) for cp in comptes()}
        else:
            dettes = {cp: c.get("ecart", cp, "dette")[k - 1] for cp in comptes()
                      if ("ecart", cp, "dette") in c.postes}
        total_d = sum(dettes.values(), np.zeros(n))
        sur = np.abs(total_d) > 1e-9
        for cp in comptes():
            part = np.where(sur, dettes.get(cp, np.zeros(n)) / np.where(sur, total_d, 1.0),
                            _comme_comptes(_parts_dette()).get(cp, 0.0))
            c._ajouter("ecart", cp, "interets_nets", k, d_int * part)
        # ---- B9 et dette des comptes de l'écart
        for cp in comptes():
            b9 = _b9(c, "ecart", cp, k)
            c._ajouter("ecart", cp, "b9", k, b9)
            prec = c.get("ecart", cp, "dette")[k - 1] if k else 0.0
            ajust = ((var["dette"] - var["dette_ouverture"] + var["b9"])
                     - (ref["dette"] - ref["dette_ouverture"] + ref["b9"]))
            c._ajouter("ecart", cp, "dette", k, prec - b9
                       + ajust * _comme_comptes(_parts_dette()).get(cp, 0.0))
        # ---- la variante des sous-secteurs : la référence plus les écarts de leurs comptes
        for cp in comptes():
            s = secteur(cp)
            for poste in ("recettes", "depenses", "transferts_recus", "transferts_verses",
                          "interets_nets"):
                cle = ("ecart", cp, poste)
                if cle in c.postes:
                    c._ajouter("variante", s, poste, k, c.postes[cle][k])
        for scen, etat in (("reference", ref), ("variante", var)):
            ajust = etat["dette"] - etat["dette_ouverture"] + etat["b9"]
            for s in SECTEURS:
                b9 = _b9(c, scen, s, k)
                c._ajouter(scen, s, "b9", k, b9)
                if k == 0:
                    prec = etat["dette_ouverture"] * _parts_dette()[s]
                else:
                    prec = c.get(scen, s, "dette")[k - 1]
                c._ajouter(scen, s, "dette", k, prec - b9 + ajust * _parts_dette()[s])
    for s in SECTEURS:
        for poste in POSTES:
            if ("reference", s, poste) in c.postes:
                c.postes[("ecart", s, poste)] = (c.get("variante", s, poste)
                                                 - c.get("reference", s, poste))
    c.residus = verifier(c, traj)
    return c


def _b9(c: CompteSousSecteurs, scen: str, compte: str, k: int) -> np.ndarray:
    def lu(p: str) -> np.ndarray:
        cle = (scen, compte, p)
        return c.postes[cle][k] if cle in c.postes else np.zeros(c.n)

    return (lu("recettes") + lu("transferts_recus") - lu("depenses")
            - lu("transferts_verses") - lu("interets_nets"))


class IdentiteSousSecteurs(FinancementError):
    """Une identité des sous-secteurs ne tient pas à 1e-9 du PIB."""


def verifier(c: CompteSousSecteurs, traj: Any) -> dict[str, float]:
    """Les identités du module (docstring), à 1e-9 du PIB sur chaque tirage ; rend le
    pire résidu relatif de chacune."""
    pire: dict[str, float] = {}

    def tenir(nom: str, residu: np.ndarray, pib: np.ndarray, annee: int) -> None:
        r = float(np.max(np.abs(residu / pib)))
        pire[nom] = max(pire.get(nom, 0.0), r)
        if r > TOLERANCE:
            raise IdentiteSousSecteurs(f"identité « {nom} » violée en {annee} : {r:.3e} "
                                       f"du PIB")

    for k, annee in enumerate(c.annees):
        for scen, etat in (("reference", traj.reference[k]), ("variante", traj.variante[k])):
            pib = etat["pib"]

            def somme(poste: str, scen: str = scen, k: int = k) -> np.ndarray:
                return sum((c.get(scen, s, poste)[k] for s in SECTEURS
                            if (scen, s, poste) in c.postes), np.zeros(c.n))

            tenir(f"{scen}.recettes", somme("recettes") - etat["apu_recettes"], pib, annee)
            tenir(f"{scen}.depenses", somme("depenses") - etat["apu_depenses_primaires"],
                  pib, annee)
            tenir(f"{scen}.interets", somme("interets_nets") - etat["interets_nets"], pib,
                  annee)
            tenir(f"{scen}.transferts", somme("transferts_recus")
                  - somme("transferts_verses"), pib, annee)
            tenir(f"{scen}.b9", somme("b9") - etat["b9"], pib, annee)
            tenir(f"{scen}.dette", somme("dette") - etat["dette"], pib, annee)
        pib = traj.variante[k]["pib"]
        for poste in POSTES:
            branches_asso = sum((c.get("ecart", cp, poste)[k] for cp in comptes()
                                 if cp.startswith("asso.") and ("ecart", cp, poste)
                                 in c.postes), np.zeros(c.n))
            if ("ecart", "asso", poste) in c.postes:
                tenir(f"branches.{poste}", branches_asso - c.get("ecart", "asso", poste)[k],
                      pib, annee)
    return pire


def resume(c: CompteSousSecteurs, tirage: int = 0) -> dict[str, Any]:
    """Les écarts par sous-secteur et par branche, année par année, en Md€ (un tirage)."""
    out: dict[str, Any] = {"annees": list(c.annees), "sous_secteurs": {}, "branches": {},
                           "compensation": {}, "residus": c.residus}
    for s in SECTEURS:
        out["sous_secteurs"][s] = {
            p: {"reference": [round(float(x), 3) for x in c.get("reference", s, p)[:, tirage]],
                "ecart": [round(float(x), 3) for x in c.get("ecart", s, p)[:, tirage]]}
            for p in ("b9", "dette")}
    for cp in comptes():
        if cp.startswith("asso.") and ("ecart", cp, "b9") in c.postes:
            out["branches"][cp] = {p: [round(float(x), 3) for x in
                                       c.get("ecart", cp, p)[:, tirage]]
                                   for p in ("recettes", "transferts_recus", "b9", "dette")}
    for cp, v in c.compensation.items():
        out["compensation"][cp] = [round(float(x), 3) for x in v[:, tirage]]
    return out
