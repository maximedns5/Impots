"""Les mois travaillés : l'emploi discontinu dans l'année (but 19, étape « ppa »).

**Ce qui manquait.** L'enquête Emploi voit une semaine. `incomes.attach_incomes` payait
chaque salarié occupé cette semaine-là douze mois sur douze, au salaire de son poste, et
personne d'autre : ni le salarié entré dans son poste depuis moins d'un an, ni celui qui
l'a quitté depuis. La prime d'activité et le RSA se calculent sur les ressources des trois
mois précédents (`ppa_base_formula`, `period.last_3_months`) ; un salaire lissé sur douze
mois ne leur montre ni les mois sans emploi, ni les trimestres à un ou deux mois de paie.
Le volume de travail annuel moyen des salariés du modèle, quotité fois mois sur douze,
était de 0,93 équivalent temps plein ; l'Insee en mesure 0,77 (`VOLUME_EQTP`).

**Ce que fait ce module**, sur la population après `attach_incomes`, sans toucher au
tirage des salaires (`incomes.py`) :

1. le mois de l'enquête, tiré dans le trimestre de la vague (`household_id` finit par
   le trimestre) ;
2. les douze mois qui finissent au mois de l'enquête, travaillés ou non :
   * un salarié dans son poste depuis un an ou plus (ANCEMPL4 2 à 4, ou inconnu) :
     douze mois ;
   * un salarié dans son poste depuis moins d'un an (ANCEMPL4 = 1) : une ancienneté
     tirée uniforme sur l'année, et les mois d'avant travaillés (un autre poste) avec la
     probabilité `PLEIN_AVANT`, sinon non ;
   * une personne sans emploi qui a quitté un emploi salarié (ACL_EMPLOI de A à D)
     depuis moins d'un an (ANCSSEMP 1 à 4) : le temps depuis la fin tiré uniforme dans
     sa tranche, et les mois d'avant, dans la fenêtre, tous travaillés avec la même
     probabilité `PLEIN_AVANT`, sinon une durée uniforme ;
3. le salaire : celui du salarié, au même taux mensuel, sur ses mois travaillés
   seulement ; celui de la personne sans emploi, au taux mensuel d'un salarié tiré
   parmi ceux de la même classe d'emploi (ACL_EMPLOI), du même sexe et du même côté de
   25 ans (un donneur ; d'abord parmi les contrats à durée limitée de la cellule) ;
4. **un facteur unique ramène la masse des salaires des salariés à celle qu'ils avaient**
   : le total calé de `incomes.py` (`TOTAL_GROSS_WAGES`, moins les gérants) ne change
   pas ; les gérants majoritaires ne sont pas touchés. Avec `PLEIN_AVANT` calé, ce
   facteur vaut 1 à 10⁻⁸ près sur la population entière : il ne joue que sur un
   échantillon ou une autre population.

Le profil est un masque de douze bits (`mois_travailles`, bit m − 1 pour le mois m),
répété sur les trois années que le câblage écrit (`to_openfisca`) : l'hypothèse
stationnaire de D-011, qui vaut déjà pour les montants. Le chômage d'une personne qui a
travaillé une partie de l'année est versé sur ses mois sans salaire.

**`PLEIN_AVANT` est calé** (`caler_plein_avant`) pour que la masse des salaires aux taux
mensuels du tirage ne change pas (un facteur de 1) : l'enquête mesure l'emploi d'un mois
moyen, les mois travaillés le répartissent entre les personnes sans l'augmenter ni le
diminuer. Le seul calage du module. Le volume de travail moyen de l'Insee (0,77 en 2023,
`VOLUME_EQTP`), par âge et par quotité, et la dispersion du revenu salarial annuel (D1,
médiane) en sont les contrôles, que le calage ne vise pas.

Hypothèses, dites : la forme uniforme des anciennetés et des durées ; une même
probabilité d'avoir travaillé avant pour l'entrant et pour le sortant ; la périodicité du
profil ; la quotité de la personne sans emploi est celle de son donneur ; aucune
allocation chômage pour le salarié occupé à la semaine de l'enquête pendant ses mois
sans emploi (la masse de l'Unédic reste aux chômeurs au sens du BIT, comme avant) ; la
pension de l'inactif de 55 ans ou plus qui a quitté un emploi dans l'année reste versée
douze mois.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import polars as pl

#: Tous les mois : le masque d'une personne qui n'a pas de mois sans salaire.
TOUS_LES_MOIS = (1 << 12) - 1

#: Insee Références « Emploi, chômage, revenus du travail », édition 2026 (2 juillet
#: 2026), fiche « Revenu salarial », figure 1 : volume de travail annuel moyen en EQTP,
#: 2023, France hors Mayotte, tous salariés hors apprentis, stagiaires, élus, salariés
#: de l'agriculture et des particuliers-employeurs (panel Tous salariés).
#: https://www.insee.fr/fr/statistiques/fichier/8733097/ECRT2026_F30.xlsx
VOLUME_EQTP = {
    "ensemble": 0.77,
    "temps_complet": 0.85,
    "temps_partiel": 0.51,
    "moins_de_25_ans": 0.48,
    "25_39_ans": 0.79,
    "40_49_ans": 0.84,
    "50_54_ans": 0.86,
    "55_ans_ou_plus": 0.77,
    "femmes": 0.74,
    "hommes": 0.79,
}
#: Même source, figure 3 : revenu salarial annuel net, 2023, en euros.
REVENU_SALARIAL_2023 = {"d1": 3_470.0, "mediane": 22_270.0, "d9": 44_590.0,
                        "moyenne": 24_960.0}

#: ANCSSEMP -> (borne basse, borne haute) du temps sans emploi, en mois.
BANDES_SANS_EMPLOI = {"1": (0.0, 1.0), "2": (1.0, 3.0), "3": (3.0, 6.0), "4": (6.0, 12.0)}

#: STATUTDET « alternance, stage » : hors du champ de l'Insee (apprentis, stagiaires).
ALTERNANCE = "24"

#: La probabilité que les mois d'avant une entrée en poste, ou d'avant une sortie, dans
#: la fenêtre de douze mois, aient tous été travaillés (un autre poste). **Calée** par
#: `caler_plein_avant` pour que le facteur soit 1 : la masse des salaires aux taux
#: mensuels du tirage ne change pas, parce que l'enquête Emploi mesure l'emploi d'un mois
#: moyen et que les mois travaillés ne font que le répartir entre les personnes ; les
#: allègements et les cotisations, calculés au mois, gardent leur assiette. Population
#: de 2024 jointe (D-366, 199 451 ménages), graine 20240101, le 10 novembre 2026.
#:
#: Le volume de travail de l'Insee (`VOLUME_EQTP`) est le contrôle : 0,846 EQTP en moyenne
#: (0,935 avant, 0,77 publié). Calé sur lui, `PLEIN_AVANT` bute sur sa borne : à 0, le
#: volume est encore de 0,813, et le facteur de 1,034 relève tous les taux mensuels
#: (la réduction générale de l'échantillon perdait 10,8 %). Les mouvements que la semaine
#: de l'enquête voit n'en font pas plus ; les contrats très courts répétés manquent.
PLEIN_AVANT = 0.4267

#: Le flux aléatoire du module : distinct de ceux des salaires (`seed`) et des
#: non-salariés (`[seed, 2]`), pour qu'aucun de leurs tirages ne bouge.
FLUX = 3


@dataclass(frozen=True)
class Statistiques:
    """Ce que le module a fait, compté (pondéré)."""

    salaries_partiels: float
    """Salariés occupés à la semaine de l'enquête avec moins de douze mois de salaire."""
    sortants_payes: float
    """Personnes sans emploi à la semaine de l'enquête, payées une partie de l'année."""
    volume_eqtp: float
    """Le volume moyen des salariés de l'année, hors alternance : la cible du calage."""
    volume_avant: float
    """Le même, quand chaque salarié occupé était payé douze mois."""
    facteur: float
    """Le facteur qui ramène la masse des salaires à son total calé."""


def _mois_enquete(household_id: pl.Series, rng: np.random.Generator) -> np.ndarray:
    """Le mois de l'enquête, de 1 à 12 : le trimestre de la vague, un mois tiré dedans."""
    trimestre = household_id.str.split("-").list.last().cast(pl.Int64, strict=False)
    trimestre = trimestre.fill_null(1).clip(1, 4).to_numpy()
    return (trimestre - 1) * 3 + rng.integers(1, 4, size=trimestre.size)


def masque(mois_enquete: np.ndarray, debut: np.ndarray, duree: np.ndarray) -> np.ndarray:
    """Le masque des mois travaillés : `duree` mois consécutifs, le plus récent `debut`
    mois avant le mois de l'enquête (0 : le mois de l'enquête lui-même), dans la fenêtre
    circulaire de douze mois qui finit au mois de l'enquête."""
    out = np.zeros(mois_enquete.size, dtype=np.int64)
    for j in range(12):
        travaille = (j >= debut) & (j < debut + duree)
        mois = (mois_enquete - 1 - j) % 12
        out |= np.where(travaille, 1 << mois, 0)
    return out


def nombre_de_mois(masques: np.ndarray) -> np.ndarray:
    """Le nombre de mois travaillés de chaque masque."""
    m = np.asarray(masques, dtype=np.int64)
    return sum(((m >> k) & 1) for k in range(12))


@dataclass(frozen=True)
class _Tirages:
    """Les tirages, faits une fois : le calage de `PLEIN_AVANT` les réutilise."""

    mois_enquete: np.ndarray
    entrant: np.ndarray
    anciennete: np.ndarray
    sortant: np.ndarray
    depuis_fin: np.ndarray
    u_plein: np.ndarray
    u_duree: np.ndarray


def _tirer(frame: pl.DataFrame, seed: int) -> tuple[_Tirages, np.ndarray]:
    rng = np.random.default_rng([seed, FLUX])
    n = frame.height
    employe = _employes(frame)
    entrant = employe & (frame["anciennete_emploi"].fill_null("").to_numpy() == "1")
    bande = frame["anciennete_sans_emploi"].fill_null("").to_numpy()
    classe = frame["classe_emploi"].fill_null("").to_numpy()
    sortant = ((frame["statut_activite"].to_numpy() != "employed")
               & np.isin(bande, list(BANDES_SANS_EMPLOI))
               & np.isin(np.array([c[:1] for c in classe]), ["A", "B", "C", "D"]))
    bas = np.array([BANDES_SANS_EMPLOI.get(b, (0.0, 0.0))[0] for b in bande])
    haut = np.array([BANDES_SANS_EMPLOI.get(b, (0.0, 0.0))[1] for b in bande])
    tirages = _Tirages(
        mois_enquete=_mois_enquete(frame["household_id"], rng),
        entrant=entrant,
        anciennete=rng.uniform(0.0, 12.0, size=n),
        sortant=sortant,
        depuis_fin=bas + (haut - bas) * rng.uniform(size=n),
        u_plein=rng.uniform(size=n),
        u_duree=rng.uniform(size=n),
    )
    return tirages, employe


def _employes(frame: pl.DataFrame) -> np.ndarray:
    """Les salariés occupés, comme `incomes.attach_incomes` les paie."""
    return frame["is_salarie"].to_numpy().astype(bool) & (
        frame["statut_activite"].to_numpy() == "employed")


def _masques(t: _Tirages, plein_avant: float) -> np.ndarray:
    """Le masque de chacun, pour une probabilité `plein_avant`."""
    plein = t.u_plein < plein_avant
    # L'entrant : son poste depuis floor(ancienneté) mois avant l'enquête, mois de
    # l'enquête compris ; avant, tout ou rien.
    en_poste = np.minimum(12, np.floor(t.anciennete).astype(np.int64) + 1)
    entrant = np.where(plein, 12, en_poste)
    m = np.where(t.entrant, masque(t.mois_enquete, np.zeros_like(en_poste), entrant),
                 TOUS_LES_MOIS)
    # Le sortant : sans emploi depuis floor(depuis_fin) + 1 mois, mois de l'enquête
    # compris ; avant, dans la fenêtre, tout ou une durée uniforme.
    sans = np.floor(t.depuis_fin).astype(np.int64) + 1
    reste = np.clip(12 - sans, 0, 12)
    duree = np.where(plein, reste,
                     np.ceil(t.u_duree * reste).astype(np.int64))
    duree = np.where(reste > 0, np.maximum(duree, 1), 0)
    m_sortant = masque(t.mois_enquete, sans, duree)
    return np.where(t.sortant, m_sortant, m)


def _donneurs(frame: pl.DataFrame, employe: np.ndarray, receveur: np.ndarray,
              seed: int) -> np.ndarray:
    """Pour chaque receveur, l'indice d'un salarié de la même cellule, tiré au poids.

    La cellule : la classe d'emploi (ACL_EMPLOI, qui dit le niveau et le contrat), le
    sexe, le côté de 25 ans ; à défaut, la lettre de la classe seule ; à défaut, tous."""
    rng = np.random.default_rng([seed, FLUX, 1])
    classe = frame["classe_emploi"].fill_null("99").to_numpy().astype(str)
    sexe = frame["sex"].to_numpy().astype(str)
    jeune = (frame["age"].to_numpy() < 25)
    poids = frame["weight"].to_numpy().astype(np.float64)
    fines = np.char.add(np.char.add(classe, sexe), jeune.astype(str))
    lettres = np.array([c[:1] for c in classe])
    donneur = np.full(frame.height, -1, dtype=np.int64)
    candidats = np.flatnonzero(employe)

    def tirer(cles: np.ndarray, qui: np.ndarray) -> None:
        for cle in np.unique(cles[qui]):
            pool = candidats[cles[candidats] == cle]
            cible = np.flatnonzero(qui & (cles == cle))
            if pool.size == 0 or cible.size == 0:
                continue
            p = poids[pool] / poids[pool].sum()
            donneur[cible] = rng.choice(pool, size=cible.size, p=p)

    tirer(fines, receveur & (donneur < 0))
    tirer(lettres, receveur & (donneur < 0))
    tirer(np.zeros(frame.height, dtype=np.int64).astype(str), receveur & (donneur < 0))
    return donneur


def volume_moyen(frame: pl.DataFrame, masques: np.ndarray, quotite: np.ndarray,
                 qui: np.ndarray) -> float:
    """Le volume de travail annuel moyen en EQTP, quotité fois mois sur douze, des
    personnes de `qui` qui ont au moins un mois de salaire."""
    mois = nombre_de_mois(masques)
    poids = frame["weight"].to_numpy().astype(np.float64)
    payes = qui & (mois > 0)
    v = quotite * mois / 12.0
    return float((v[payes] * poids[payes]).sum() / poids[payes].sum())


def _champ_insee(frame: pl.DataFrame) -> np.ndarray:
    """Hors alternance et stages, comme le champ du panel Tous salariés."""
    return frame["statut_detaille"].fill_null("").to_numpy() != ALTERNANCE


def caler_plein_avant(frame: pl.DataFrame, seed: int) -> float:
    """La probabilité `PLEIN_AVANT` qui laisse la masse des salaires aux taux du tirage
    inchangée (un facteur de 1), par bissection : le facteur décroît avec elle."""
    lo, hi = 0.0, 1.0
    for _ in range(30):
        mid = (lo + hi) / 2.0
        if attach_mois_travailles(frame, seed, mid)[1].facteur > 1.0:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def _tirages_et_quotite(frame: pl.DataFrame, seed: int
                        ) -> tuple[_Tirages, np.ndarray, np.ndarray, np.ndarray]:
    t, employe = _tirer(frame, seed)
    donneur = _donneurs(frame, employe, t.sortant, seed)
    quotite = frame["quotite_travail"].to_numpy().astype(np.float64).copy()
    a_donneur = t.sortant & (donneur >= 0)
    quotite[a_donneur] = quotite[donneur[a_donneur]]
    return t, employe, quotite, donneur


def attach_mois_travailles(frame: pl.DataFrame, seed: int,
                           plein_avant: float | None = None
                           ) -> tuple[pl.DataFrame, Statistiques]:
    """Ajoute `mois_travailles` et répartit les salaires sur les mois travaillés.

    Lit `salaire_brut_annuel` tel que `attach_incomes` l'a calé, et le rend au même
    total sur les salariés et les personnes payées une partie de l'année."""
    plein_avant = PLEIN_AVANT if plein_avant is None else plein_avant
    t, employe, quotite, donneur = _tirages_et_quotite(frame, seed)
    sortant = t.sortant & (donneur >= 0)
    masques = _masques(t, plein_avant)
    masques = np.where(employe | sortant, masques, TOUS_LES_MOIS)
    mois = nombre_de_mois(masques)
    sortant &= mois > 0
    masques = np.where(t.sortant & ~sortant, TOUS_LES_MOIS, masques)
    mois = nombre_de_mois(masques)

    poids = frame["weight"].to_numpy().astype(np.float64)
    salaire = frame["salaire_brut_annuel"].to_numpy().astype(np.float64)
    taux = salaire / 12.0
    nouveau = np.where(employe, taux * mois, salaire)
    nouveau = np.where(sortant, taux[np.maximum(donneur, 0)] * mois, nouveau)
    payes = employe | sortant
    avant = float((salaire[employe] * poids[employe]).sum())
    apres = float((nouveau[payes] * poids[payes]).sum())
    facteur = avant / apres if apres > 0 else 1.0
    nouveau = np.where(payes, nouveau * facteur, nouveau)

    # La part exonérée des salaires (étape « ir ») : une seule part pour tous les
    # salariés, que reçoivent aussi les personnes payées une partie de l'année.
    colonnes = [pl.Series("salaire_brut_annuel", nouveau),
                pl.Series("mois_travailles", masques.astype(np.int64))]
    if "part_salaire_exoneree" in frame.columns:
        part = frame["part_salaire_exoneree"].fill_null(0.0).to_numpy().astype(np.float64)
        commune = float(part[employe].max()) if employe.any() else 0.0
        colonnes.append(pl.Series("part_salaire_exoneree", np.where(sortant, commune, part)))
    out = frame.with_columns(colonnes)

    champ = _champ_insee(frame)
    stats = Statistiques(
        salaries_partiels=float(poids[employe & (mois < 12)].sum()),
        sortants_payes=float(poids[sortant].sum()),
        volume_eqtp=volume_moyen(frame, masques, quotite, payes & champ),
        volume_avant=volume_moyen(frame, np.full(frame.height, TOUS_LES_MOIS), quotite,
                                  employe & champ),
        facteur=facteur,
    )
    return out, stats
