"""Le registre des champs de l'état (CADRE.md §2) : le registre unique.

Chaque champ a son unité, son code de comptabilité nationale (SEC 2010), sa source et le
lot qui le calcule. Un champ que personne n'a écrit est ABSENT, pas nul (`etat`) ; un nom
que le registre ne connaît pas est refusé partout où il apparaît.

LES GROUPES, et ce qu'ils somment (les identités sont dans `identites`) :

* ``emplois`` — les emplois du PIB à prix courants, Insee t. 1.101, par secteur. Les
  importations y entrent avec le signe moins (`signe = -1`). Trois champs de plus, chacun
  nommé et jamais un résidu silencieux : ``emplois_non_ventiles`` (l'effet sur le PIB
  qu'un bloc publie sans le ventiler entre les emplois : Mésange et le canal des
  créations n'impriment que la ligne du PIB), ``ventilation_emplois`` (l'écart publié
  entre les totaux P3 et P51G de la t. 1.101 et la somme de leurs secteurs, de 0,12 et
  0,09 Md€ en 2023 et 2024, sous l'arrondi ailleurs) et ``arrondi_emplois`` (le PIB publié
  moins la somme des totaux publiés, au millième de milliard). Les deux derniers sont lus
  sur l'histoire et nuls en projection.
* ``revenus`` — l'approche revenus, Insee t. 1.105 : D1 + B2A3G + D2 − D3. La France
  n'imprime aucun écart statistique entre ses trois approches annuelles ; le champ du
  cadre est ``arrondi_revenus``, lu, borné par l'arrondi de publication.
* ``apu_recettes`` et ``apu_depenses`` — le compte des APU, Insee t. 3.201, consolidé, ligne
  à ligne, hors intérêts : les intérêts nets (D41 versés moins reçus) sont un champ à
  part, que le cadre calcule en projection. B9 = recettes − dépenses − intérêts nets.
* ``dette`` — Maastricht, fin d'année. ``sfa`` est l'ajustement flux-stocks d'Eurostat
  (F_ASS + ORADJ + YA3, D-405) de 2021 à 2025, et celui de l'Insee avant (la somme des
  groupes (1) à (5) de la t. 3.105, D-410) ; ``ecart_millesime_dette`` l'écart entre les
  deux publications qui portent l'identité (la variation du stock de l'Insee et celle de
  la table de passage, B9 de l'Insee et le déficit de la table) ; ``ecart_eurostat``
  l'écart interne de la table de passage (sa variation moins son déficit moins son
  ajustement), de l'ordre du dixième de million chez Eurostat, nul à la t. 3.105. Le nom
  est resté celui du lot 1.

Les champs des lots 2 à 4 (travail, entreprises, reste du monde) sont au registre et
restent absents tant que leur lot ne les écrit pas.
"""

from __future__ import annotations

from dataclasses import dataclass

from impots.macro.mesange import VARIANTS

T1101 = "Insee, comptes nationaux annuels base 2020, t. 1.101 (millésime 2025)"
T1105 = "Insee, comptes nationaux annuels base 2020, t. 1.105 (millésime 2025)"
T3201 = "Insee, comptes nationaux annuels base 2020, t. 3.201 (millésime 2025)"
DETTE = "Insee, dette trimestrielle de Maastricht des APU, détail (fin d'année)"
EUROSTAT = "Eurostat, gov_10dd_edpt3 (notification EDP, France)"
T3105 = "Insee, comptes nationaux annuels base 2020, t. 3.105 (millésime 2025)"
PROJECTION = "nul en projection, par convention : un écart de publication ne se projette pas"


class ChampInconnu(KeyError):
    """Un nom que le registre ne connaît pas."""


@dataclass(frozen=True)
class Champ:
    nom: str
    libelle: str
    unite: str
    code: str
    source: str
    lot: int
    groupe: str
    signe: int = 1
    """Le signe du champ dans la somme de son groupe (−1 pour les importations)."""
    additif: bool = True
    """Un champ additif égale la somme de ses contributions (identité 5) ; un ratio, un
    indice de prix ou une croissance n'en a pas, et un seul écrivain."""
    ferme: bool = False
    """Écrit par le cadre seul, en projection (§3.4) : aucun bloc ne l'écrit."""


_REGISTRE: dict[str, Champ] = {}


def _ajouter(*champs: Champ) -> None:
    for champ in champs:
        if champ.nom in _REGISTRE:
            raise ValueError(f"champ « {champ.nom} » déclaré deux fois")
        _REGISTRE[champ.nom] = champ


MDE = "Md€ courants"

# --------------------------------------------------------------------- les emplois
#: (nom, libellé, code SEC de l'opération, secteur dans la t. 1.101)
EMPLOIS_PUBLIES: tuple[tuple[str, str, str, str | None], ...] = (
    ("c_menages", "Consommation des ménages hors EI", "P3", "S14B"),
    ("c_isbl", "Consommation des ISBLSM", "P3", "S15"),
    ("c_apu", "Consommation des APU", "P3", "S13"),
    ("fbcf_snf", "FBCF des sociétés et EI non financières", "P51G", "S11X14AA"),
    ("fbcf_sf", "FBCF des sociétés et EI financières", "P51G", "S12X14AF"),
    ("fbcf_apu", "FBCF des APU", "P51G", "S13"),
    ("fbcf_menages", "FBCF des ménages hors EI", "P51G", "S14B"),
    ("fbcf_isbl", "FBCF des ISBLSM", "P51G", "S15"),
    ("objets_valeur", "Acquisitions moins cessions d'objets de valeur", "P53", None),
    ("var_stocks", "Variation des stocks", "P52", None),
    ("exportations", "Exportations de biens et services", "P6", None),
    ("importations", "Importations de biens et services", "P7", None),
)
for _nom, _lib, _code, _sect in EMPLOIS_PUBLIES:
    _ajouter(Champ(_nom, _lib, MDE, f"{_code} {_sect}" if _sect else _code, T1101, 1,
                   "emplois", signe=-1 if _code == "P7" else 1))
_ajouter(
    Champ("emplois_non_ventiles", "Effet sur le PIB non ventilé entre les emplois", MDE,
          "B1GQ", "écrit par un bloc qui ne publie que la ligne du PIB (Mésange, canal des "
          "créations) ; les lots 3 et 4 le ventileront", 1, "emplois"),
    Champ("ventilation_emplois", "Totaux P3 et P51G moins la somme de leurs secteurs",
          MDE, "P3 + P51G", f"{T1101} ; {PROJECTION}", 1, "emplois"),
    Champ("arrondi_emplois", "PIB publié moins la somme des totaux publiés", MDE,
          "B1GQ", f"{T1101}, au millième de milliard ; {PROJECTION}", 1, "emplois"),
    Champ("pib", "Produit intérieur brut", MDE, "B1GQ", T1101, 1, "pib"),
)
#: Les emplois dont le volume se chaîne : les publiés et l'effet non ventilé. Les écarts
#: de publication n'ont ni prix ni volume.
EMPLOIS_EN_VOLUME = (*(e[0] for e in EMPLOIS_PUBLIES), "emplois_non_ventiles")
for _nom in EMPLOIS_EN_VOLUME:
    _ajouter(Champ(f"prix_{_nom}", f"Déflateur de {_nom}, année précédente = 1", "indice",
                   "", "Insee, t. 1.103 (histoire) ; scénario de prix (projection)", 1,
                   "prix", additif=False))
_ajouter(Champ("croissance_volume_pib", "Croissance du PIB en volume, chaînée", "ratio",
               "B1GQ L", "le cadre : somme des croissances en volume des emplois pondérées "
               "par leurs parts nominales de l'année précédente", 1, "volume",
               additif=False, ferme=True))

# --------------------------------------------------------------------- les revenus
_ajouter(
    Champ("remunerations", "Rémunération des salariés", MDE, "D1", T1105, 1, "revenus"),
    Champ("ebe_revenu_mixte", "Excédent brut d'exploitation et revenu mixte brut", MDE,
          "B2A3G", T1105, 1, "revenus"),
    Champ("impots_production", "Impôts sur la production et les importations", MDE, "D2",
          T1105, 1, "revenus"),
    Champ("subventions", "Subventions (comptées positives, soustraites)", MDE, "D3", T1105,
          1, "revenus", signe=-1),
    Champ("revenus_non_ventiles", "Effet sur le PIB non ventilé entre les revenus", MDE,
          "B1GQ", "écrit par un bloc qui ne publie que la ligne du PIB ; le lot 4 le "
          "ventilera", 1, "revenus"),
    Champ("arrondi_revenus", "PIB publié moins la somme des revenus publiés", MDE, "B1GQ",
          f"{T1105}, au millième de milliard ; {PROJECTION}", 1, "revenus"),
)

# --------------------------------------------------------------------- les APU
#: (nom, libellé, code, section de la t. 3.201, libellé exact de la ligne)
APU_RECETTES: tuple[tuple[str, str, str, str], ...] = (
    ("apu_r_p11", "Production marchande et ventes résiduelles", "P11",
     "Production des branches marchandes et ventes résiduelles (P11)"),
    ("apu_r_p12", "Production pour emploi final propre", "P12",
     "Production pour emploi final propre (P12)"),
    ("apu_r_p13", "Paiements partiels des ménages", "P13",
     "Paiements partiels des ménages (partie du P13)"),
    ("apu_r_d39", "Autres subventions sur la production", "D39",
     "Autres subventions sur la production (D39)"),
    ("apu_r_d4x", "Revenus de la propriété autres que les intérêts", "D4 hors D41",
     "Revenus de la propriété autres que les intérêts (D4 hors D41)"),
    ("apu_r_d2", "Impôts sur la production et les importations", "D2",
     "Impôts sur la production et les importations (D2)"),
    ("apu_r_d5", "Impôts courants sur le revenu et le patrimoine", "D5",
     "Impôts courants sur le revenu et le patrimoine (D5)"),
    ("apu_r_d91", "Impôts en capital", "D91r", "Impôts en capital à recevoir (D91r)"),
    ("apu_r_d733", "Transferts de recettes fiscales", "D733",
     "Transferts de recettes fiscales (D733)"),
    ("apu_r_d61", "Cotisations sociales nettes", "D61", "Cotisations sociales nettes (D61)"),
    ("apu_r_d995", "Impôts et cotisations dus non recouvrables", "D995r",
     "Impôts et cotisations dus non recouvrables nets (D995r)"),
    ("apu_r_d73", "Transferts courants entre APU", "D73 hors D733",
     "Transferts courants entre administrations publiques (D73 hors D733)"),
    ("apu_r_d7", "Autres transferts courants", "D7 hors D73",
     "Autres transferts courants (D7 hors D73)"),
    ("apu_r_d9", "Transferts en capital", "D9r hors D91r, D995r",
     "Transferts en capital (D9r hors D91r, D995r)"),
)
APU_DEPENSES: tuple[tuple[str, str, str, str], ...] = (
    ("apu_d_p2", "Consommation intermédiaire", "P2", "Consommation intermédiaire (P2)"),
    ("apu_d_d1", "Rémunération des salariés", "D1", "Rémunération des salariés (D1)"),
    ("apu_d_d29", "Autres impôts sur la production", "D29",
     "Autres impôts sur la production (D29)"),
    ("apu_d_d4x", "Revenus de la propriété autres que les intérêts", "D4 hors D41",
     "Revenus de la propriété autres que les intérêts (D4 hors D41)"),
    ("apu_d_d5", "Impôts courants sur le revenu et le patrimoine", "D5",
     "Impôts courants sur le revenu et le patrimoine (D5)"),
    ("apu_d_d62", "Prestations sociales autres que transferts en nature", "D62",
     "Prestations sociales autres que transferts sociaux en nature (D62)"),
    ("apu_d_d632", "Transferts sociaux en nature de produits marchands", "D632",
     "Transferts sociaux en nature de produits marchands (D632)"),
    ("apu_d_d3", "Subventions", "D3", "Subventions (D3)"),
    ("apu_d_d73", "Transferts courants entre APU", "D73",
     "Transferts courants entre administrations publiques (D73)"),
    ("apu_d_d7", "Autres transferts courants", "D7 hors D73",
     "Autres transferts courants (D7 hors D73)"),
    ("apu_d_d9", "Transferts en capital à payer", "D9p hors D995p",
     "Transferts en capital à payer (D9p hors D995p)"),
    ("apu_d_p51g", "Formation brute de capital fixe", "P51g",
     "Formation brute de capital fixe (P51g)"),
    ("apu_d_autres_acq", "Autres acquisitions nettes d'actifs non financiers",
     "P52, P53, NP",
     "Autres acquisitions moins cessions d'actifs non financiers (P52, P53, NP)"),
)
for _nom, _lib, _code, _ in APU_RECETTES:
    _ajouter(Champ(_nom, _lib, MDE, _code, T3201, 1, "apu_recettes"))
for _nom, _lib, _code, _ in APU_DEPENSES:
    _ajouter(Champ(_nom, _lib, MDE, _code, T3201, 1, "apu_depenses"))
_ajouter(
    Champ("solde_induit", "Effet induit sur le solde primaire, non ventilé", MDE, "B9",
          "écrit par un bloc qui publie le solde sans le ventiler (Mésange : recettes, "
          "prestations chômage et dépenses indexées mêlées ; le canal des créations : ses "
          "recettes au taux de prélèvements) ; compté en recettes, une amélioration est "
          "positive", 1, "apu_recettes"),
    Champ("mesures_non_ventilees", "Choc d'une mesure que son rapport ne ventile pas",
          MDE, "B9", "le choc statique d'une mesure tirée d'un rapport, qui porte son coût "
          "et ses recettes induites sans dire sur quelles catégories : compté en "
          "recettes, un coût en négatif", 1, "apu_recettes"),
    Champ("apu_recettes", "Recettes des APU hors intérêts reçus", MDE, "TR − D41r",
          f"{T3201} (histoire) ; le cadre (projection)", 1, "apu_totaux", ferme=True),
    Champ("apu_depenses_primaires", "Dépenses des APU hors intérêts", MDE, "TE − D41p",
          f"{T3201} (histoire) ; le cadre (projection)", 1, "apu_totaux", ferme=True),
    Champ("interets_nets", "Intérêts nets versés par les APU", MDE, "D41p − D41r",
          f"{T3201} (histoire) ; le cadre, aux taux du scénario (projection)", 1,
          "apu_totaux", ferme=True),
    Champ("b9", "Capacité (+) ou besoin (−) de financement des APU", MDE, "B9NF",
          f"{T3201} (histoire) ; le cadre (projection)", 1, "apu_totaux", ferme=True),
    Champ("solde_primaire", "Solde primaire des APU", MDE, "B9 + D41 nets", "le cadre", 1,
          "apu_totaux", ferme=True),
)

# --------------------------------------------------------------------- la dette
_ajouter(
    Champ("dette_ouverture", "Dette de Maastricht à la fin de l'année précédente", MDE,
          "GD", f"{DETTE} ; le cadre (projection)", 1, "dette", ferme=True),
    Champ("dette", "Dette de Maastricht en fin d'année", MDE, "GD",
          f"{DETTE} ; le cadre (projection)", 1, "dette", ferme=True),
    Champ("sfa", "Ajustement flux-stocks", MDE, "F_ASS + ORADJ + YA3 ; (1) à (5)",
          f"{EUROSTAT}, 2021 à 2025 ; {T3105}, 2010 à 2020 (D-410) ; nul en projection, "
          "par convention", 1, "dette"),
    Champ("ecart_millesime_dette", "Écart entre la dette de l'Insee et la table de "
          "passage sur ΔD et B9", MDE, "ΔGD − GD_CH + B9 + B9_T3",
          f"{DETTE}, {T3201} et la table de passage de l'année ; {PROJECTION}", 1,
          "dette"),
    Champ("ecart_eurostat", "Écart interne de la table de passage (variation moins "
          "déficit moins ajustement)", MDE, "",
          f"{EUROSTAT} (2021 à 2025), {T3105} (2010 à 2020) ; {PROJECTION}", 1, "dette"),
    Champ("ratio_dette", "Dette sur PIB", "ratio", "", "le cadre", 1, "ratios",
          additif=False, ferme=True),
    Champ("taux_implicite", "Intérêts nets sur la dette d'ouverture", "ratio", "",
          "le cadre", 1, "ratios", additif=False, ferme=True),
)

# --------------------------------------------------------------------- les signaux
#: L'impulsion des mesures par instrument de Mésange, Md€, signe expansionniste
#: (`shocks.Impulse.by_instrument`) : ce que le bloc `mesange` lit.
IMPULSIONS = tuple(f"impulsion_{i}" for i in sorted(VARIANTS))
for _nom in IMPULSIONS:
    _ajouter(Champ(_nom, f"Impulsion sur « {_nom.removeprefix('impulsion_')} »", MDE, "",
                   "le choc statique des mesures (passe sur la population)", 1,
                   "impulsions"))
_ajouter(Champ("prelevements_entreprises", "Variation des prélèvements sur les "
               "entreprises et le capital", MDE, "", "le choc statique des mesures, les "
               "instruments de `predictif.creations` (recettes positives)", 1,
               "signaux"))

# --------------------------------------------------------------------- lot 5 : les impôts
T3217 = "Insee, comptes nationaux annuels base 2020, t. 3.217 (millésime 2025)"
#: Les principaux impôts de la t. 3.217, en sous-champs de l'histoire (lot 5, D-410) :
#: (nom, libellé exact de la ligne). Ils ne somment pas aux catégories du compte des APU,
#: la table n'imprimant que les principaux ; ils ne sont dans aucune identité, et un impôt
#: qui n'existe pas une année (case vide) y est absent. En projection, ils restent absents
#: tant qu'aucun bloc ne les écrit.
IMPOTS_3217: tuple[tuple[str, str], ...] = (
    ("tva", "Taxe sur la valeur ajoutée (TVA) (D211)"),
    ("ticpe", "Accises sur les produits énergétiques (TICPE)"),
    ("tabacs", "Accises sur les tabacs"),
    ("droits_enregistrement",
     "Droits d'enregistrement (sur transactions immobilières et autres)"),
    ("taxe_salaires", "Taxe sur les salaires"),
    ("taxe_fonciere", "Taxe foncière"),
    ("cfe", "Cotisation foncière des entreprises"),
    ("cvae", "Cotisation sur la valeur ajoutée des entreprises"),
    ("taxe_professionnelle", "Taxe professionnelle (TP)"),
    ("c3s", "Contribution sociale de solidarité des sociétés"),
    ("csg", "Contribution sociale généralisée (CSG) (**)"),
    ("crds", "Contribution au remboursement de la dette sociale (CRDS) (**)"),
    ("ir", "Impôt sur le revenu des personnes physiques (IRPP), avant crédits d'impôt"),
    ("is", "Impôt sur les sociétés (IS), avant crédits d'impôt"),
    ("credits_is_imputes", "Crédits d'impôt sur l'IS : utilisés en déduction de l'impôt dû"),
    ("credits_is_restitues",
     "Crédits d'impôt sur l'IS : au-delà de l'impôt dû, payés par l'administration"),
    ("taxe_habitation", "Taxe d'habitation"),
    ("isf_ifi", "Impôt sur la fortune (IFI, ex ISF)"),
    ("audiovisuel", "Contribution à l'audiovisuel public"),
    ("dmtg", "Droits de mutation à titre gratuit"),
    ("cotisations_effectives", "Cotisations sociales effectives"),
    ("prelevements_obligatoires", "Prélèvements obligatoires = (I)+(II)+(III)+(IV)"),
)
for _nom, _lib in IMPOTS_3217:
    _ajouter(Champ(f"impot_{_nom}", _lib, MDE, "", f"{T3217} (histoire)", 5, "impots"))

# --------------------------------------------------------------------- lots 2 à 4
for _nom, _lib, _unite, _lot in (
        ("population_active", "Population active", "milliers", 4),
        ("emploi_total", "Emploi total", "milliers", 4),
        ("emploi_salarie", "Emploi salarié", "milliers", 4),
        ("chomage", "Chômeurs", "milliers", 4),
        ("salaire_moyen", "Salaire moyen par tête", "€ courants", 4),
        ("stock_societes", "Stock de sociétés", "unités", 2),
        ("creations_societes", "Créations de sociétés", "unités", 2),
        ("fermetures_societes", "Fermetures de sociétés", "unités", 2),
        ("productivite_moyenne", "Productivité moyenne", "indice", 2),
        ("investissement_entreprises", "Investissement des entreprises", MDE, 2),
        ("demande_mondiale", "Demande mondiale adressée à la France", "indice", 3),
        ("prix_relatifs", "Prix relatifs à l'exportation", "indice", 3),
        ("solde_courant", "Solde courant", MDE, 3)):
    _ajouter(Champ(_nom, _lib, _unite, "", f"lot {_lot} (absent au lot 1)", _lot,
                   f"lot{_lot}", additif=_unite == MDE))

REGISTRE: dict[str, Champ] = dict(_REGISTRE)


def champ(nom: str) -> Champ:
    if nom not in REGISTRE:
        raise ChampInconnu(f"champ « {nom} » inconnu du registre (jumeau/champs.py)")
    return REGISTRE[nom]


def groupe(nom: str) -> tuple[str, ...]:
    """Les champs d'un groupe, dans l'ordre du registre."""
    out = tuple(c.nom for c in REGISTRE.values() if c.groupe == nom)
    if not out:
        raise ChampInconnu(f"groupe « {nom} » inconnu du registre")
    return out


EMPLOIS = groupe("emplois")
REVENUS = groupe("revenus")
RECETTES = groupe("apu_recettes")
DEPENSES = groupe("apu_depenses")
FERMES = tuple(c.nom for c in REGISTRE.values() if c.ferme)
