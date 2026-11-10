"""Les jeunes actifs chez leurs parents, foyers de la prime à part (but 19, étape « ppa2 »).

**Ce qui manquait.** Le squelette range parmi les enfants de la famille (Caf) tout jeune
de moins de 21 ans qui vit chez ses parents, et celui de 21 à 24 ans qui n'est pas en
emploi à la semaine de l'enquête (`skeleton._classify_dependants`). OpenFisca additionne
les revenus d'activité de tous les membres de la famille dans la base ressources de la
prime (`ppa_revenu_activite`, `famille.sum`) : le salaire d'un apprenti ou d'un jeune
salarié de 19 ans gonfle les ressources de ses parents, et lui-même n'a jamais de prime
à son nom. La loi lui en ouvre une : la prime est ouverte dès 18 ans depuis 2016 (art.
L. 842-1 du code de la sécurité sociale), et un jeune dont les ressources dépassent le
plafond n'est pas à la charge de ses parents (le moteur le retire déjà de leur nombre
d'enfants, `rsa_enfant_a_charge`, sans retirer son salaire de leur base).

**La source.** La Drees fait l'hypothèse que « tous les jeunes actifs constituent un
foyer social autonome » pour mesurer le non-recours à la prime (Études et Résultats
n° 1379, juillet 2026, encadré 3) ; le scénario contraire, où ils restent rattachés à
leurs parents, y donne un non-recours plus bas (44 à 48 %). Le taux de non-recours que
`recours.PPA` refait (48 à 52 %) est donc défini sur des foyers où ils sont à part : le
modèle doit les compter comme elle.

**Ce que fait ce module**, sur la population après `attach_mois_travailles` : chaque
enfant de la famille de 18 à 24 ans dont le revenu d'activité d'un mois travaillé (le
salaire de l'année sur ses mois de paie, plus le douzième d'un revenu non salarié)
dépasse 55 % de 169 heures de Smic brut (`SEUIL_A_CHARGE`) devient demandeur d'une
famille à lui, hébergée dans le
logement de ses parents, sans aide au logement (il n'est pas sur le bail, art. R. 821-4
du code de la construction et de l'habitation, comme les autres adultes hébergés,
`logement.lodging`). Rien d'autre ne bouge : ni son foyer fiscal (son rattachement à
ses parents reste tiré par le squelette), ni son ménage, ni ses revenus.

**Le seuil** est celui de l'enfant à charge des prestations familiales (art. R. 512-2 du
code de la sécurité sociale ; openfisca `def_pac.revenu_plafond_pac_non_scolaire`) :
au-dessous, le jeune reste à la charge de ses parents, pour leurs allocations familiales
comme pour leur prime, et son petit revenu reste dans leur base ; au-dessus, il ne l'est
plus pour les allocations familiales, et le moteur le retire déjà du nombre d'enfants de
la prime. La Drees sort tous les jeunes actifs ; le seuil garde aux parents les
allocations familiales d'un enfant qui a un job d'été (sans lui, ces allocations
perdaient 3 % sur l'échantillon). **Hypothèses, dites.** Le seuil est lu sur le mois
moyen travaillé, quand la Caf le lit mois par mois. Le jeune hébergé chez des parents
locataires n'a pas de forfait logement dans le moteur (le moteur lit le statut
d'occupation du ménage), alors que la Caf le compte logé gratuitement : sa prime est
trop haute d'au plus le forfait (75 € par mois pour une personne seule en 2024) ; défaut
du câblage, mesuré, non corrigé ici. L'étudiant salarié n'est pas distingué : l'enquête ne dit pas qui est inscrit dans
le supérieur au sens de la Caf, et le plancher de revenu des apprenants
(`ppa_eligibilite_apprenants`) ne joue pas.
"""

from __future__ import annotations

from dataclasses import dataclass

import polars as pl

#: L'âge d'ouverture de la prime (art. L. 842-1 du code de la sécurité sociale, depuis
#: 2016) et la borne des personnes à charge au sens de la prime (moins de 25 ans).
AGE_MIN, AGE_MAX = 18, 25

#: Le revenu mensuel au-delà duquel un jeune n'est plus à charge pour les prestations
#: familiales : 55 % de 169 heures de Smic (art. R. 512-2 du code de la sécurité
#: sociale), au Smic horaire brut du 1er janvier 2024, 11,65 € (décret n° 2023-1216),
#: l'année de la population. En brut : le salaire de la population est brut.
SEUIL_A_CHARGE = 0.55 * 169 * 11.65


@dataclass(frozen=True)
class FamillesJeunesStats:
    """Ce que le module a fait, compté (pondéré)."""

    jeunes: int
    jeunes_ponderes: float
    """Les jeunes actifs sortis de la famille de leurs parents, pondérés."""
    familles_avant: int
    familles_apres: int


def revenu_mensuel(frame: pl.DataFrame) -> pl.Expr:
    """Le revenu d'activité d'un mois travaillé : le salaire sur les mois de paie."""
    mois = pl.lit(12)
    if "mois_travailles" in frame.columns:
        mois = pl.col("mois_travailles").cast(pl.UInt32).bitwise_count_ones().clip(1, 12)
    revenu = pl.col("salaire_brut_annuel") / mois
    if "revenu_non_salarie_annuel" in frame.columns:
        revenu = revenu + pl.col("revenu_non_salarie_annuel").clip(0) / 12
    return revenu


def jeunes_actifs(frame: pl.DataFrame) -> pl.Expr:
    """Les enfants de 18 à 24 ans qui ne sont plus à la charge de leurs parents."""
    return ((pl.col("role_famille") == "enfant") & (pl.col("age") >= AGE_MIN)
            & (pl.col("age") < AGE_MAX) & (revenu_mensuel(frame) > SEUIL_A_CHARGE))


def attach_familles_jeunes(frame: pl.DataFrame) -> tuple[pl.DataFrame, FamillesJeunesStats]:
    """Chaque jeune actif enfant de la famille devient demandeur de sa propre famille."""
    marque = frame.select(jeunes_actifs(frame).alias("_jeune"))["_jeune"]
    jeunes = frame.filter(marque)
    nouvelle = (pl.col("famille_id") + pl.lit("-j") + pl.col("person_id").cast(pl.String))
    out = frame.with_columns(marque).with_columns(
        pl.when("_jeune").then(nouvelle).otherwise(pl.col("famille_id"))
        .alias("famille_id"),
        pl.when("_jeune").then(pl.lit("demandeur")).otherwise(pl.col("role_famille"))
        .alias("role_famille"),
    )
    if "aide_logement_heberge" in out.columns:
        out = out.with_columns(
            (pl.col("aide_logement_heberge") | pl.col("_jeune"))
            .alias("aide_logement_heberge"))
    out = out.drop("_jeune")
    stats = FamillesJeunesStats(
        jeunes=jeunes.height,
        jeunes_ponderes=float(jeunes["weight"].sum()) if jeunes.height else 0.0,
        familles_avant=frame["famille_id"].n_unique(),
        familles_apres=out["famille_id"].n_unique(),
    )
    return out, stats
