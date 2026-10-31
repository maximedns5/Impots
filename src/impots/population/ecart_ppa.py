"""L'écart du volet prime d'activité de l'art. 74 (D-300), décomposé contre la Cnaf (D-315).

Le cas chiffre une revalorisation du montant forfaitaire. Ce qu'elle coûte par mois et
par point est une **base** : la somme, sur les foyers bénéficiaires, de ce qu'un point de
forfait leur ajoute. La Cnaf publie de quoi reconstituer la sienne : ses bénéficiaires et
leur montant moyen par configuration familiale (PA Conjoncture n° 32) et l'élasticité de
sa dépense au forfait (Analyses statistiques n° 5). Le moteur donne la sienne, mesurée par
une passe où le forfait vaut 1 % de plus. Le rapport des deux bases se décompose en trois
termes, dans cet ordre, déclaré avant la mesure :

1. **les effectifs** : les foyers du moteur, configuration par configuration, au montant
   moyen de la Cnaf ;
2. **les montants** : le montant moyen du moteur à la place de celui de la Cnaf ;
3. **l'élasticité** : celle du moteur à la place de celle de la Cnaf, elle-même coupée en
   un effet de **composition** (les élasticités du moteur pondérées par les dépenses de la
   Cnaf, puis par les siennes) et un effet **interne** aux configurations.

Les trois termes sont des logarithmes : leur somme est le logarithme du rapport des bases,
exactement. Un autre ordre donnerait d'autres parts ; celui-ci est fixé par D-315.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np

from impots.population import ppa_cnaf

CONFIGURATIONS = tuple(key for key, _ in ppa_cnaf.CONFIGURATIONS)
AGES = tuple(key for key, _ in ppa_cnaf.AGES)
#: Le revenu d'activité du foyer, en part du Smic brut à temps plein du mois.
TRANCHES_REVENU = ((0.0, "0_025"), (0.25, "025_05"), (0.5, "05_08"), (0.8, "08_1"),
                   (1.0, "1_12"), (1.2, "12_15"), (1.5, "15_plus"))
#: Le montant de prime du mois, en euros.
TRANCHES_MONTANT = ((0.0, "0_50"), (50.0, "50_100"), (100.0, "100_200"), (200.0, "200_300"),
                    (300.0, "300_plus"))
SEUIL = 0.5  # un foyer bénéficiaire touche plus de 0,50 € dans le mois (`runner`)


class EcartPpaError(RuntimeError):
    """La décomposition ne porterait pas sur ce qu'elle dit."""


def configuration(n_parents: np.ndarray, n_enfants: np.ndarray,
                  sexe_demandeur: np.ndarray) -> np.ndarray:
    """La configuration de la Cnaf : l'enfant y est toute personne à charge au sens de la
    prime (note (1) du tableau 1), ce que `rsa_nb_enfants` compte."""
    n_parents = np.asarray(n_parents)
    n_enfants = np.asarray(n_enfants)
    sexe = np.asarray(sexe_demandeur).astype(str)
    if not np.isin(n_parents, (1, 2)).all():
        raise EcartPpaError(f"des familles ont {sorted(set(n_parents.tolist()))} parents")
    if not np.isin(sexe, ("male", "female")).all():
        raise EcartPpaError(f"sexes inattendus : {sorted(set(sexe.tolist()))}")
    out = np.where(n_parents == 2,
                   np.where(n_enfants > 0, "couple_avec_enfants", "couple_sans_enfant"),
                   np.where(n_enfants > 0, "seul_avec_enfants",
                            np.where(sexe == "male", "homme_seul", "femme_seule")))
    return out.astype(object)


def _band(values: np.ndarray, bands: tuple[tuple[float, str], ...]) -> np.ndarray:
    values = np.asarray(values, dtype=np.float64)
    out = np.full(values.shape, bands[0][1], dtype=object)
    for low, code in bands:
        out[values >= low] = code
    return out


def age_band(age: np.ndarray) -> np.ndarray:
    """Les tranches d'âge du responsable du dossier, celles du tableau 1."""
    return _band(age, ((0.0, "moins_25"), (25.0, "25_34"), (35.0, "35_44"), (45.0, "45_54"),
                       (55.0, "55_plus")))


def tranche_revenu(revenu: np.ndarray, smic_mensuel: float) -> np.ndarray:
    if not smic_mensuel > 0:
        raise EcartPpaError(f"Smic mensuel {smic_mensuel}")
    return _band(np.asarray(revenu, dtype=np.float64) / smic_mensuel, TRANCHES_REVENU)


def tranche_montant(montant: np.ndarray) -> np.ndarray:
    return _band(montant, TRANCHES_MONTANT)


@dataclass(frozen=True)
class Cellule:
    """Ce que le moteur donne pour un groupe de familles, pondéré, sur un mois."""

    beneficiaires: float   # familles qui touchent la prime
    depense: float         # € du mois
    hausse: float          # € du mois que la prime gagne quand le forfait vaut 1 % de plus

    @property
    def montant_moyen(self) -> float:
        return self.depense / self.beneficiaires if self.beneficiaires else 0.0

    @property
    def elasticite(self) -> float:
        """La hausse de la dépense, en %, pour 1 % de forfait."""
        return self.hausse / self.depense * 100 if self.depense else 0.0


def cellules(groupe: np.ndarray, poids: np.ndarray, prime: np.ndarray,
             prime_forfait: np.ndarray, cles: tuple[str, ...]) -> dict[str, Cellule]:
    """Les cellules d'un découpage. Une famille qui n'a de prime qu'avec le forfait relevé y
    entre par sa hausse, pas par ses effectifs : c'est un entrant."""
    groupe = np.asarray(groupe).astype(object)
    inconnus = set(groupe.tolist()) - set(cles)
    if inconnus:
        raise EcartPpaError(f"groupes hors du découpage : {sorted(inconnus)}")
    beneficiaire = prime > SEUIL
    out = {}
    for cle in cles:
        dans = groupe == cle
        out[cle] = Cellule(
            beneficiaires=float(poids[dans & beneficiaire].sum()),
            depense=float((poids * prime)[dans].sum()),
            hausse=float((poids * (prime_forfait - prime))[dans].sum()))
    return out


@dataclass(frozen=True)
class Decomposition:
    """Le rapport des bases et ses trois termes, en logarithmes."""

    base_moteur: float        # € du mois par point de forfait
    base_cnaf: float
    effectifs: float
    montants: float
    composition: float
    interne: float
    par_cle_effectifs: dict[str, float]   # € du mois, au montant de la Cnaf
    par_cle_montants: dict[str, float]

    @property
    def rapport(self) -> float:
        return self.base_moteur / self.base_cnaf

    @property
    def elasticite(self) -> float:
        return self.composition + self.interne

    def parts(self) -> dict[str, float]:
        """La part du logarithme du rapport que porte chaque terme."""
        total = math.log(self.rapport)
        return {"effectifs": self.effectifs / total, "montants": self.montants / total,
                "composition": self.composition / total, "interne": self.interne / total}


def decompose(moteur: Mapping[str, Cellule], cnaf: Mapping[str, ppa_cnaf.Cellule],
              part_caf: float, elasticite_cnaf: float) -> Decomposition:
    """Le rapport de la base du moteur à celle de la Cnaf, en trois termes (module).

    Les effectifs de la Cnaf sont ceux des Caf : ils sont portés à tous les régimes par
    `part_caf`, la part des bénéficiaires que la Cnaf rapporte, la même pour toutes les
    configurations. Leur montant moyen est celui que le tableau imprime. `elasticite_cnaf`
    est en %, pour 1 % de forfait."""
    if set(moteur) != set(cnaf):
        raise EcartPpaError(f"découpages différents : {sorted(moteur)} et {sorted(cnaf)}")
    if not 0.5 < part_caf <= 1:
        raise EcartPpaError(f"part des Caf {part_caf}")
    if not elasticite_cnaf > 0:
        raise EcartPpaError(f"élasticité de la Cnaf {elasticite_cnaf}")
    cles = sorted(moteur)
    for cle in cles:
        if not (moteur[cle].beneficiaires > 0 and cnaf[cle].beneficiaires > 0):
            raise EcartPpaError(f"« {cle} » : aucun bénéficiaire d'un côté")
    n_c = {k: cnaf[k].beneficiaires / part_caf for k in cles}
    m_c = {k: cnaf[k].montant_moyen for k in cles}
    s_c = sum(n_c[k] * m_c[k] for k in cles)
    s_m = sum(moteur[k].depense for k in cles)
    au_montant_cnaf = sum(moteur[k].beneficiaires * m_c[k] for k in cles)
    base_m = sum(moteur[k].hausse for k in cles)
    base_c = elasticite_cnaf / 100 * s_c
    e_m = base_m / s_m * 100
    # Les élasticités du moteur, pondérées par les dépenses de la Cnaf.
    e_repondere = sum(n_c[k] * m_c[k] / s_c * moteur[k].elasticite for k in cles)
    return Decomposition(
        base_moteur=base_m, base_cnaf=base_c,
        effectifs=math.log(au_montant_cnaf / s_c),
        montants=math.log(s_m / au_montant_cnaf),
        composition=math.log(e_m / e_repondere),
        interne=math.log(e_repondere / elasticite_cnaf),
        par_cle_effectifs={k: (moteur[k].beneficiaires - n_c[k]) * m_c[k] for k in cles},
        par_cle_montants={k: moteur[k].beneficiaires * (moteur[k].montant_moyen - m_c[k])
                          for k in cles},
    )


# ----------------------------------------------------------------------------------------
# Le cas et sa fiche, pour relier la base de 2026 à ce qui a été noté.

#: `chiffrages_preregistres/plf2027_art_74_ppa.yaml` : le chiffrage du cas, la
#: revalorisation de 2,1 % au 1er avril 2026 (qui tient lieu de 2027), en miroir.
CAS_EUR = 886_654_814.9313965
CAS_POINTS = 2.1
#: La fiche de l'art. 74, p. 602 : « État -332 -995 » (M€, 2027 et 2028), au taux de 2,3 %.
#: L'année 2028 est l'année pleine.
FICHE_ANNEE_PLEINE_EUR = 995e6
FICHE_POINTS = 2.3


def _n(x: float, d: int = 1) -> str:
    """Un nombre à la française : espace des milliers, virgule décimale."""
    return f"{x:,.{d}f}".replace(",", " ").replace(".", ",")


def _pct(x: float, d: int = 1) -> str:
    return f"{'+' if x > 0 else ''}{_n(100 * x, d)} %"


def _cells(report: Mapping[str, object], key: str) -> dict[str, Cellule]:
    return {k: Cellule(v["beneficiaires"], v["depense"], v["hausse"])
            for k, v in report[key].items()}


def _table(titre: str, labels: tuple[tuple[str, str], ...], moteur: dict[str, Cellule],
           cnaf: Mapping[str, ppa_cnaf.Cellule], part_caf: float,
           d: Decomposition) -> list[str]:
    lines = [f"### {titre}", "",
             "| | Foyers Cnaf (k) | Foyers moteur (k) | Écart | Montant Cnaf (€) "
             "| Montant moteur (€) | Écart | Élasticité moteur | Effet effectifs (M€) "
             "| Effet montants (M€) |",
             "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for key, label in labels:
        n_c = cnaf[key].beneficiaires / part_caf
        m, c = moteur[key], cnaf[key]
        lines.append(
            f"| {label} | {_n(n_c / 1e3, 0)} | {_n(m.beneficiaires / 1e3, 0)} "
            f"| {_pct(m.beneficiaires / n_c - 1)} | {_n(c.montant_moyen, 0)} "
            f"| {_n(m.montant_moyen, 0)} | {_pct(m.montant_moyen / c.montant_moyen - 1)} "
            f"| {_n(m.elasticite, 2)} | {_n(d.par_cle_effectifs[key] / 1e6)} "
            f"| {_n(d.par_cle_montants[key] / 1e6)} |")
    total_m = sum(c.beneficiaires for c in moteur.values())
    total_c = sum(c.beneficiaires for c in cnaf.values()) / part_caf
    lines += ["", f"Ensemble : {_n(total_c / 1e3, 0)} milliers de foyers à la Cnaf (tous "
              f"régimes), {_n(total_m / 1e3, 0)} au moteur ({_pct(total_m / total_c - 1)}). "
              "Les effets sont en M€ de dépense du mois ; leur somme fait l'écart de "
              "dépense que les deux premiers termes portent.", ""]
    return lines


def _terms(d: Decomposition) -> list[str]:
    parts = d.parts()
    lines = ["| Terme | Logarithme | Part de l'écart |", "|---|---:|---:|"]
    for key, label in (("effectifs", "Les effectifs"), ("montants", "Les montants"),
                       ("composition", "L'élasticité : composition"),
                       ("interne", "L'élasticité : interne aux cellules")):
        lines.append(f"| {label} | {_n(getattr(d, key), 3)} | {_pct(parts[key], 0)} |")
    lines.append(f"| **Le rapport des bases** | **{_n(math.log(d.rapport), 3)}** "
                 f"| **{_n(d.rapport, 2)}** |")
    return lines


def _engine_only(titre: str, cells: Mapping[str, Mapping[str, float]], total_hausse: float,
                 note: str) -> list[str]:
    total = sum(v["beneficiaires"] for v in cells.values())
    lines = [f"### {titre}", "", note, "",
             "| | Foyers (k) | Part | Montant (€) | Élasticité | Part de la hausse |",
             "|---|---:|---:|---:|---:|---:|"]
    for key, v in cells.items():
        lines.append(
            f"| {key} | {_n(v['beneficiaires'] / 1e3, 0)} "
            f"| {_pct(v['beneficiaires'] / total if total else 0)} "
            f"| {_n(v['montant_moyen'], 0)} | {_n(v['elasticite'], 2)} "
            f"| {_pct(v['hausse'] / total_hausse if total_hausse else 0)} |")
    lines.append("")
    return lines


def rendre(r2024: Mapping[str, object], r2026: Mapping[str, object],
           conj: ppa_cnaf.Conjoncture, elas: ppa_cnaf.Elasticites) -> str:
    """`reports/ecart_ppa.md`, depuis les deux rapports et la Cnaf, rien d'autre."""
    if r2024["annee"] != 2024 or r2026["annee"] != 2026:
        raise EcartPpaError(f"rapports de {r2024['annee']} et {r2026['annee']}")
    if r2024["commit"] != r2026["commit"] or r2024["dirty"] or r2026["dirty"]:
        raise EcartPpaError("les deux années n'ont pas tourné sur le même commit propre")
    e_c = elas.forfait * 100
    par_config = decompose(_cells(r2024, "configurations"), conj.configurations,
                           conj.part_caf_beneficiaires, e_c)
    par_age = decompose(_cells(r2024, "ages"), conj.ages, conj.part_caf_beneficiaires, e_c)
    t24, t26 = r2024["totaux"], r2026["totaux"]
    e_dec = t24["hausse"] / t24["depense"] * 100
    e_an = t24["hausse_annuelle"] / t24["depense_annuelle"] * 100
    e_sal = t24["baisse_salaire_annuelle"] / t24["depense_annuelle"] * 100
    base_fiche = FICHE_ANNEE_PLEINE_EUR / (FICHE_POINTS * 12)
    mois_cas = CAS_EUR / (CAS_POINTS * t26["hausse"])
    lines = [
        "# L'écart de la prime d'activité, mesuré contre la Cnaf (D-315)", "",
        f"Commit `{r2024['commit'][:7]}`, {r2024['echantillon']} ménages tirés comme le "
        "cas, palier complet. La prime est celle de décembre, par famille ; la hausse, ce "
        "qu'elle gagne quand le forfait vaut 1 % de plus toute l'année. La Cnaf : PA "
        "Conjoncture n° 32 (quatrième trimestre 2024, Caf, porté à tous les régimes par "
        f"{_n(100 * conj.part_caf_beneficiaires)} %) et Analyses statistiques n° 5 "
        f"(élasticité de la dépense au forfait en {elas.annee} : {_n(e_c)} %).", "",
        "## La base de 2024 et ses trois termes", "",
        f"* Moteur : {_n(t24['depense'] / 1e6, 0)} M€ de prime en décembre 2024, "
        f"{_n(t24['hausse'] / 1e6)} M€ de plus pour un point de forfait, soit une "
        f"élasticité de {_n(e_dec, 2)} (sur l'année : {_n(e_an, 2)}). La formule, sans "
        f"les entrants, donne {_n(t24['hausse_analytique'] / 1e6)} M€ ; "
        f"{_n(t24['entrants'] / 1e3, 0)} milliers de familles entrent.",
        f"* Cnaf : {_n(par_config.base_cnaf / e_c * 100 / 1e6, 0)} M€ par mois au "
        f"quatrième trimestre, tous régimes ; la base vaut {_n(par_config.base_cnaf / 1e6)}"
        " M€ par point.",
        f"* Le rapport des bases : **{_n(par_config.rapport, 2)}**.", "",
        "Découpé par configuration familiale :", "", *_terms(par_config), "",
        "Découpé par âge du responsable du dossier :", "", *_terms(par_age), "",
        "## Le tableau des écarts", "",
        *_table("Par configuration familiale", ppa_cnaf.CONFIGURATIONS,
                _cells(r2024, "configurations"), conj.configurations,
                conj.part_caf_beneficiaires, par_config),
        *_table("Par âge du responsable du dossier", ppa_cnaf.AGES, _cells(r2024, "ages"),
                conj.ages, conj.part_caf_beneficiaires, par_age),
        "### Trois sous-populations", "",
        "| | Part Cnaf | Part moteur | Montant Cnaf (€) | Montant moteur (€) |",
        "|---|---:|---:|---:|---:|",
    ]
    for key, label in ppa_cnaf.SOUS_POPULATIONS:
        c, m = conj.sous_populations[key], r2024["sous_populations"][key]
        lines.append(
            f"| {label} | {_pct(c.beneficiaires / conj.ensemble.beneficiaires)} "
            f"| {_pct(m['beneficiaires'] / t24['beneficiaires'])} | {_n(c.montant_moyen, 0)}"
            f" | {_n(m['depense'] / m['beneficiaires'] if m['beneficiaires'] else 0, 0)} |")
    lines += [
        "",
        *_engine_only("Par revenu d'activité du foyer, en part du Smic brut (moteur seul)",
                      r2024["tranches_revenu"], t24["hausse"],
                      "Ni PA Conjoncture n° 32 ni les Analyses statistiques n° 5 ne "
                      "publient cette distribution : elle n'est pas comparée."),
        *_engine_only("Par montant de prime en décembre (moteur seul)",
                      r2024["tranches_montant"], t24["hausse"],
                      "La Cnaf ne publie que des montants moyens."),
        *_engine_only("Au regard du forfait (moteur seul)", r2024["position"], t24["hausse"],
                      "Au-dessus : les ressources et le forfait logement dépassent le "
                      "forfait, qui ne s'annule plus dans la formule."),
        "## Les revenus d'activité", "",
        f"Un point de salaire en plus ôte {_n(-t24['baisse_salaire_annuelle'] / 1e6)} M€ "
        f"à la prime de l'année : une élasticité de {_n(e_sal, 2)}, contre "
        f"{_n(elas.revenus_activite * 100, 1)} à la Cnaf.", "",
        "## Le lien au cas et à la fiche, en 2026", "",
        f"* Un point de forfait ajoute {_n(t26['hausse'] / 1e6)} M€ à la prime de décembre "
        f"2026 (élasticité {_n(t26['hausse'] / t26['depense'] * 100, 2)}).",
        f"* Le cas, {_n(CAS_EUR / 1e6)} M€ pour {_n(CAS_POINTS)} points, vaut "
        f"{_n(mois_cas, 2)} mois de cette hausse.",
        f"* La fiche, {_n(FICHE_ANNEE_PLEINE_EUR / 1e6, 0)} M€ en année pleine pour "
        f"{_n(FICHE_POINTS)} points, suppose une base de {_n(base_fiche / 1e6)} M€ par "
        f"point et par mois : le moteur en a **{_n(t26['hausse'] / base_fiche, 2)}** fois "
        "plus.", "",
    ]
    return "\n".join(lines)
