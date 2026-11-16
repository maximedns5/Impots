"""Écrit les fiches de transmission des onze programmes de 2027 (but 26, `carte`, D-472).

    PYTHONPATH=src python scripts/jumeau_fiches_transmission.py [--verifier]

Une fiche par mesure de `programmes/<candidat>.json`, pour les onze candidats dont une
étude a sa page (`etude.definitions`, sans refus). Ce que le programme porte est repris
tel quel (libellé, paramètre, citation, chiffrage, montant déclaré, raison du refus) ; ce
qu'il ne porte pas vient de trois tables de ce fichier, chacune sourcée :

* `GABARITS`, par catégorie de mesure : le texte de droit, les payeurs, l'incidence et les
  canaux d'une mesure de cette catégorie, avec la littérature qui les fonde ;
* `PRECISES`, mesure par mesure, pour les chiffrées dont l'effet papillon est le plus
  long (Attal a16, les Smic, les cotisations, la CVAE) : elles remplacent le gabarit ;
* `DECLAREES`, pour chaque montant déclaré par un candidat (`declare`) : la catégorie du
  compte des APU où il tombe, la variante de Mésange la plus proche, la clé des ménages
  ou l'impôt des entreprises, et le calendrier. Ce sont des hypothèses : la fiche le dit.

Et, depuis le but 27 (volet `fiches`, D-504), une quatrième, hors de ce fichier :
`programmes/fiches/<candidat>.yaml`, les données critiques écrites mesure par mesure (le
levier et son article, l'assiette et sa source, le montant ou le calcul qui le donne, les
payeurs et leur part, le calendrier, le financement cité, les hypothèses et leurs
sources). Elle passe avant les trois autres : une régénération réécrit les fiches depuis
elle, et n'écrase plus ce qui a été écrit à la main. Le script garde ce qu'il fait bien :
le relevé du programme, le rapport et les écarts de sa première année, le bilan du
financement, les gabarits pour ce que la table ne dit pas encore.

Aucun nombre n'est inventé : un montant est celui d'un rapport commité, celui que le
candidat énonce, ou une assiette publiée fois le paramètre du candidat (le calcul écrit
dans la fiche) ; une clé ou un calendrier que personne ne donne est dit « non sourcé ».
`--verifier` relit chaque fiche écrite par le lecteur (`jumeau.transmission.charger`).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from impots import etude  # noqa: E402
from impots.jumeau import transmission  # noqa: E402
from impots.jumeau.financement import annonce  # noqa: E402

NS = transmission.NON_SOURCEE

# --------------------------------------------------------------------------- sources
FULLERTON = ("Fullerton et Metcalf (2002), « Tax incidence », Handbook of Public "
             "Economics, vol. 4, ch. 26 : à long terme, l'incidence ne dépend pas de qui "
             "verse l'impôt, mais des élasticités de l'offre et de la demande")
SMT = ("Saez, Matsaganis et Tsakloglou (2012), « Earnings determination and taxes : "
       "evidence from a cohort-based payroll tax reform in Greece », QJE 127(1) : à "
       "moyen terme, les cotisations restent sur celui qui les verse (incidence "
       "statutaire)")
LMR = ("Lehmann, Marical et Rioux (2013), « Labor income responds differently to "
       "income-tax and payroll-tax reforms », Journal of Public Economics 99 (France, "
       "DADS) : une baisse de cotisations se retrouve en partie dans le salaire, lentement")
BBG = ("Bozio, Breda et Grenet (2019), « Does tax-benefit linkage matter for the "
       "incidence of social security contributions ? », IZA DP 12502 (France) : une "
       "cotisation liée à des droits se reporte sur le salaire, une cotisation sans lien "
       "reste sur l'employeur")
SSS = ("Saez, Schoefer et Seim (2019), « Payroll taxes, firm behavior, and rent "
       "sharing », American Economic Review 109(5) (Suède) : une baisse de cotisations "
       "patronales ne passe pas dans les salaires ; elle passe dans l'emploi et "
       "l'investissement")
CD = ("Crépon et Desplatz (2001), « Une nouvelle évaluation des effets des allégements "
      "de charges sociales sur les bas salaires », Économie et Statistique 348 (Insee)")
KP = ("Kramarz et Philippon (2001), « The impact of differential payroll tax subsidies "
      "on minimum wage employment », Journal of Public Economics 82(1) (France)")
KL = ("Koubi et Lhommeau (2007), « Les effets de diffusion de court terme des hausses du "
      "Smic dans les grilles salariales des entreprises de dix salariés ou plus sur la "
      "période 2000-2005 », Insee, Les salaires en France, édition 2007")
GM = ("Goarant et Muller (2011), « Les effets des hausses du Smic sur les salaires "
      "mensuels dans les entreprises de 10 salariés ou plus de 2006 à 2009 », Insee, "
      "Emploi et salaires, édition 2011")
FGL = ("Fougère, Gautier et Le Bihan (2010), « Restaurant prices and the minimum wage », "
       "Journal of Money, Credit and Banking 42(7) (France) : une hausse du Smic passe "
       "dans les prix des services intensifs en bas salaires")
L1317 = ("Code de la sécurité sociale, art. L131-7 (loi du 25 juillet 1994) : l'État "
         "compense à la Sécurité sociale toute exonération ou réduction de cotisations, "
         "sauf dérogation d'une loi de financement")
MESANGE = ("Insee et DG Trésor, « Le modèle macroéconométrique Mésange : réestimation et "
           "nouveautés », document de travail G2017-04, §4 (les variantes)")
CAE53 = ("Martin et Trannoy (2019), « Les impôts sur (ou contre) la production », Note du "
         "CAE n° 53 : les impôts sur le chiffre d'affaires et la valeur ajoutée se "
         "reportent en cascade sur les prix et pèsent sur la compétitivité")
FPS = ("Fuest, Peichl et Siegloch (2018), « Do higher corporate taxes reduce wages ? », "
       "American Economic Review 108(2) : environ la moitié de l'impôt local sur les "
       "bénéfices retombe sur les salaires (Allemagne)")
CARB = ("Carbonnier (2007), « Who pays sales taxes ? Evidence from French VAT reforms, "
        "1987-1999 », Journal of Public Economics 91(5-6) : une baisse de TVA passe aux "
        "prix en partie, plus sur un marché concurrentiel")
BCHK = ("Benzarti, Carloni, Harju et Kosonen (2020), « What goes up may not come down : "
        "asymmetric incidence of value-added taxes », Journal of Political Economy "
        "128(12) : les hausses de TVA passent plus aux prix que les baisses")
JJKZ = ("Jakobsen, Jakobsen, Kleven et Zucman (2020), « Wealth taxation and wealth "
        "accumulation », QJE 135(1) (Danemark) : l'assiette répond à l'impôt sur la "
        "fortune, d'autant plus en haut de la distribution")
COR = ("Conseil d'orientation des retraites, rapport annuel (juin 2025) : le solde des "
       "régimes selon l'âge, la durée et l'indexation")
DSS = ("Direction de la Sécurité sociale, rapport à la Commission des comptes de la "
       "Sécurité sociale (2025) : le solde par branche")
MAGASIN = ("le magasin comportemental du projet (offre de travail par groupe, C7, "
           "`labour.groups`), que le rapport de la mesure lit à θ")

# --------------------------------------------------------------------------- gabarits
INC_STAT = {"horizon": "immediat", "qui": "le payeur légal",
            "texte": "Le premier effet est sur celui que la loi désigne.",
            "source": FULLERTON}


def _g(texte, payeurs, incidence, canaux):
    return {"texte": texte, "payeurs": payeurs, "incidence": incidence, "canaux": canaux}


GABARITS = {
    "ir": _g("Code général des impôts, impôt sur le revenu (art. 1 A, 197 et s.)",
             [{"qui": "menages", "sens": "recoit", "par": "ir"},
              {"qui": "apu:etat", "sens": "paie", "par": "impot_sur_le_revenu"}],
             [INC_STAT, {"horizon": "long", "qui": "les ménages redevables",
                         "texte": "L'IR reste sur le ménage ; il répond par son offre de "
                                  "travail et sa consommation.", "source": FULLERTON}],
             ["consommation_menages", "offre_travail"]),
    "csg_cotisations": _g(
        "Code de la sécurité sociale : CSG (art. L136-1 et s.) et cotisations (livre II)",
        [{"qui": "menages", "sens": "recoit", "par": "cotisations_salariales"},
         {"qui": "apu:secu:vieillesse", "sens": "paie", "par": "cotisations_salaries"}],
        [INC_STAT,
         {"horizon": "court", "qui": "les salariés", "texte": "Le net bouge, le brut et "
          "le coût du travail non.", "source": SMT},
         {"horizon": "long", "qui": "salariés et employeurs", "texte": "Le brut peut se "
          "renégocier : une part de la baisse revient à l'employeur.", "source": LMR}],
        ["consommation_menages", "offre_travail", "incidence_cotisations",
         "compensation_exonerations", "financement_sous_secteurs"]),
    "tva_consommation": _g(
        "Code général des impôts, TVA (art. 278 et s.) et accises",
        [{"qui": "menages", "sens": "recoit", "par": "tva"},
         {"qui": "apu:etat", "sens": "paie", "par": "tva"}],
        [{"horizon": "immediat", "qui": "consommateurs et vendeurs", "texte": "Une "
          "baisse de taux passe aux prix en partie ; le reste fait la marge.",
          "source": CARB},
         {"horizon": "long", "qui": "consommateurs et vendeurs", "texte": "Asymétrie : "
          "une hausse passe plus qu'une baisse.", "source": BCHK}],
        ["consommation_menages", "prix_production"]),
    "entreprises": _g(
        "Code général des impôts : IS (art. 205 et s.), CVAE (art. 1586 ter), C3S "
        "(CSS, art. L137-30), CFE (art. 1447)",
        [{"qui": "entreprises", "sens": "recoit", "par": "autre"},
         {"qui": "apu:etat", "sens": "paie", "par": "autre"}],
        [{"horizon": "immediat", "qui": "les entreprises", "texte": "La marge après "
          "impôt bouge.", "source": FULLERTON},
         {"horizon": "long", "qui": "salariés, clients, actionnaires", "texte": "Un impôt "
          "sur les bénéfices retombe pour partie sur les salaires ; un impôt sur le "
          "chiffre d'affaires, en cascade, sur les prix.", "source": f"{FPS} ; {CAE53}"}],
        ["investissement_cout_du_capital", "creations_entreprises",
         "fermetures_entreprises", "implantation", "prix_production"]),
    "patrimoine_capital": _g(
        "Code général des impôts : droits de mutation (art. 777 et s.), PFU (art. 200 A), "
        "IFI (art. 964 et s.)",
        [{"qui": "menages", "sens": "paie", "par": "patrimoine",
          "note": "la population n'en porte pas : aucune clé par décile"},
         {"qui": "apu:etat", "sens": "recoit", "par": "capital_menages"}],
        [{"horizon": "immediat", "qui": "les détenteurs du patrimoine",
          "texte": "Statutaire.", "source": FULLERTON},
         {"horizon": "long", "qui": "les détenteurs du patrimoine", "texte": "L'assiette "
          "répond (épargne, transmission, localisation).", "source": JJKZ}],
        ["patrimoine_menages", "consommation_menages"]),
    "retraites": _g(
        "Code de la sécurité sociale : âge (art. L161-17-2), pension (art. L351-1 et s.)",
        [{"qui": "menages", "sens": "recoit", "par": "retraite"},
         {"qui": "apu:secu:vieillesse", "sens": "paie", "par": "depense_publique"}],
        [{"horizon": "immediat", "qui": "les retraités et futurs retraités",
          "texte": "Statutaire.", "source": FULLERTON},
         {"horizon": "long", "qui": "les régimes et les actifs", "texte": "Le solde des "
          "régimes et l'emploi des seniors bougent.", "source": COR}],
        ["droits_retraite", "offre_travail", "consommation_menages",
         "financement_sous_secteurs"]),
    "prestations": _g(
        "Code de la sécurité sociale et Code de l'action sociale et des familles",
        [{"qui": "menages", "sens": "recoit", "par": "prestations"},
         {"qui": "apu:secu:famille", "sens": "paie", "par": "depense_publique"}],
        [{"horizon": "immediat", "qui": "les allocataires", "texte": "Statutaire.",
          "source": FULLERTON},
         {"horizon": "court", "qui": "les allocataires", "texte": "L'offre de travail "
          "répond au revenu et au taux marginal.", "source": MAGASIN}],
        ["consommation_menages", "offre_travail", "financement_sous_secteurs"]),
    "salaires_smic": _g(
        "Code du travail, Smic (art. L3231-1 et s.) ; point d'indice (décret n° 85-1148)",
        [{"qui": "entreprises", "sens": "paie", "par": "masse_salariale"},
         {"qui": "menages", "sens": "recoit", "par": "salaire_net"}],
        [{"horizon": "immediat", "qui": "les employeurs", "texte": "Le coût du travail "
          "monte au bas de l'échelle.", "source": FULLERTON},
         {"horizon": "court", "qui": "les salariés voisins du Smic", "texte": "La hausse "
          "se diffuse aux salaires voisins, en s'amortissant.", "source": f"{KL} ; {GM}"},
         {"horizon": "long", "qui": "les salariés peu qualifiés et les clients",
          "texte": "L'emploi au bas de l'échelle répond au coût ; les prix des services "
          "intensifs en bas salaires montent.", "source": f"{KP} ; {FGL}"}],
        ["salaires", "emploi", "prix_production", "consommation_menages", "smic_diffusion",
         "cout_travail_smic", "incidence_cotisations", "compensation_exonerations"]),
    "depense_publique": _g(
        "Loi organique relative aux lois de finances (crédits) ; LFSS ; budgets locaux",
        [{"qui": "apu:etat", "sens": "paie", "par": "depense_publique"}],
        [{"horizon": "immediat", "qui": "les bénéficiaires de la dépense",
          "texte": "La demande publique bouge.", "source": MESANGE},
         {"horizon": "long", "qui": "les contribuables", "texte": "Le solde et la dette "
          "bougent ; l'activité en rend une part.", "source": MESANGE}],
        ["demande_publique", "emploi_public", "consommation_menages"]),
    "regle_budgetaire": _g("Loi de programmation des finances publiques ; LOLF", [], [],
                           []),
    "energie_carburants": _g(
        "Code des impositions sur les biens et services (accises sur les énergies, "
        "L312-1 et s.) ; Code de l'énergie (CEE, L221-1)",
        [{"qui": "menages", "sens": "recoit", "par": "accises"},
         {"qui": "apu:etat", "sens": "paie", "par": "taxe_carbone"}],
        [{"horizon": "immediat", "qui": "consommateurs et distributeurs", "texte": "Le "
          "passage d'une accise au prix à la pompe.", "source": NS}],
        ["consommation_menages", "prix_production", "importations"]),
    "autre": _g("Le texte n'est pas désigné par le programme", [], [], []),
}

# ------------------------------------------------------- les chiffrées les plus longues
A16 = {
    "levier": {"texte": "Code de la sécurité sociale, cotisations d'assurance vieillesse "
               "salariales du régime général (art. D242-4, CNAV, plafonnée et "
               "déplafonnée) ; accord national interprofessionnel Agirc-Arrco "
               "(cotisations salariales, CEG, CET)"},
    "payeurs": [
        {"qui": "menages", "sens": "recoit", "par": "salaire_net",
         "note": "+77,14 Md€ de salaires nets, 2026, population figée (rapport de la "
                 "première année, `deltas.salaire_net`)"},
        {"qui": "apu:secu:vieillesse", "sens": "paie", "par": "cotisations_salaries",
         "note": "la CNAV perd sa part des cotisations salariales"},
        {"qui": "apu:secu:retraite_complementaire", "sens": "paie",
         "par": "cotisations_salaries",
         "note": "l'Agirc-Arrco perd la sienne ; la passe ne sépare pas les deux : "
                 "−77,14 Md€ ensemble (`deltas.cotisations_salariales`)"},
        {"qui": "apu:etat", "sens": "recoit", "par": "impot_sur_le_revenu",
         "note": "+12,05 Md€ d'IR (le net imposable monte) ; −1,54 Md€ de prime "
                 "d'activité versée (`deltas.ir`, `deltas.ppa`)"}],
    "incidence": [
        {"horizon": "immediat", "qui": "les salariés", "texte": "Le net monte de 3 000 € "
         "par an au salaire médian ; le brut et le coût du travail ne bougent pas.",
         "source": "le chiffrage de la mesure (`programmes/attal.json`, note) ; " + SMT},
        {"horizon": "court", "qui": "les régimes de retraite", "texte": "La caisse perd sa "
         "recette ; sans compensation, le déficit de la branche se creuse.",
         "source": f"{L1317} ; {DSS}"},
        {"horizon": "long", "qui": "salariés et employeurs", "texte": "Le brut peut se "
         "renégocier à la baisse : une part du gain du net revient à l'employeur, qui "
         "voit alors son coût baisser et peut embaucher. Une cotisation de retraite liée "
         "à des droits se reporte sur le salaire : si les droits sont maintenus, la "
         "renégociation est plus probable.", "source": f"{LMR} ; {BBG} ; {FULLERTON}"}],
    "canaux": ["consommation_menages", "offre_travail", "incidence_cotisations",
               "salaires", "emploi", "compensation_exonerations",
               "financement_sous_secteurs", "financement_annonce"],
    "hypotheses": [
        {"texte": "L'échelle des cotisations salariales de retraite à 0,22 traduit "
                  "« +250 € nets par mois au salaire médian » : 3 000 € par an sur "
                  "3 845 € de cotisations retraite salariales au médian.",
         "valeur": 0.22, "source": "le chiffrage de la mesure (`programmes/attal.json`, "
                                   "D-381 et suivantes), mesuré par le moteur"},
        {"texte": "La baisse s'applique à tous les salaires, ce que la mesure ne précise "
                  "pas.", "source": "le chiffrage de la mesure (`programmes/attal.json`)"},
        {"texte": "Les droits à la retraite des salariés ne baissent pas avec leurs "
                  "cotisations.", "source": NS},
        {"texte": "Aucune renégociation du brut la première année.", "source": SMT}],
}

SMIC_INC = [
    {"horizon": "immediat", "qui": "les employeurs de salariés au Smic", "texte": "Le "
     "coût du travail monte au Smic ; les allègements généraux, calculés sur le Smic, "
     "s'étendent à plus de salaires et changent de coût.",
     "source": f"Code de la sécurité sociale, art. L241-13 (réduction générale) ; {CD}"},
    {"horizon": "court", "qui": "les salariés jusqu'à environ 1,5 Smic", "texte": "La "
     "hausse se diffuse aux salaires voisins, de moins en moins loin du Smic.",
     "source": f"{KL} ; {GM}"},
    {"horizon": "long", "qui": "les salariés peu qualifiés, les clients", "texte": "L'emploi "
     "au bas de l'échelle répond au coût ; les prix des services intensifs en bas "
     "salaires montent.", "source": f"{KP} ; {FGL}"}]
SMIC_HYP = [
    {"texte": "Pas de diffusion aux salaires voisins dans le chiffrage de l'étude "
              "(`smic_diffusion_echelle` à 0).", "valeur": 0.0,
     "source": "le chiffrage de la mesure (`programmes/<candidat>.json`)"},
    {"texte": "Le jumeau ne lit pas le Smic réel efficace sans une hypothèse de diffusion "
              "(D-469, J2) : le volet `travail` la porte.", "source": "D-469"}]
SMIC = {"payeurs": [
    {"qui": "entreprises", "sens": "paie", "par": "masse_salariale"},
    {"qui": "menages", "sens": "recoit", "par": "salaire_net"},
    {"qui": "entreprises", "sens": "recoit", "par": "cotisations_employeurs",
     "note": "les allègements généraux suivent le Smic"},
    {"qui": "apu:etat", "sens": "paie", "par": "cotisations_employeurs",
     "note": "la compensation des allègements à la Sécurité sociale (art. L131-7 CSS)"},
    {"qui": "apu:secu:maladie", "sens": "recoit", "par": "cotisations_employeurs"}],
    "incidence": SMIC_INC, "hypotheses": SMIC_HYP,
    "canaux": GABARITS["salaires_smic"]["canaux"]}

CVAE = {"payeurs": [{"qui": "entreprises", "sens": "recoit", "par": "cvae"},
                    {"qui": "apu:apul", "sens": "paie", "par": "impots_production_"
                     "entreprises", "note": "la CVAE est affectée aux collectivités, "
                     "compensée par une fraction de TVA depuis 2021"}],
        "incidence": [GABARITS["entreprises"]["incidence"][0],
                      {"horizon": "long", "qui": "clients et salariés", "texte": "Un "
                       "impôt de production pèse sur la compétitivité et les prix.",
                       "source": CAE53}]}

PRECISES = {
    "attal/a16_droit_au_brut": A16,
    "retailleau/r19_gains_rendus_moitie": {
        **{k: A16[k] for k in ("levier", "canaux")},
        "payeurs": [{k: v for k, v in p.items() if k != "note"} for p in A16["payeurs"]],
        "incidence": [{"horizon": "immediat", "qui": "les salariés", "texte": "Le net "
                       "monte ; le brut et le coût du travail ne bougent pas.",
                       "source": SMT}, *A16["incidence"][1:]],
        "hypotheses": [{"texte": "L'échelle 0,87 traduit le gain que le candidat énonce.",
                        "valeur": 0.87, "source": "le chiffrage de la mesure "
                        "(`programmes/retailleau.json`)"}, A16["hypotheses"][2]]},
    "kazib/smic_2000": SMIC, "roussel/smic_plus_15": SMIC, "ruffin/smic_1600": SMIC,
    "melenchon/smic_1700_net": SMIC, "tondelier/smic_2000_brut": SMIC,
    "bouamrane/hausse_salaires_150": SMIC,
    "attal/a18_suppression_cvae": CVAE, "lisnard/l4_suppression_c3s_cvae": CVAE,
    "retailleau/r21_c3s_cvae_forfait_social_cfe": CVAE,
    "melenchon/exonerations_au_dela_2_smic": {
        "payeurs": [{"qui": "entreprises", "sens": "paie", "par": "cotisations_employeurs"},
                    {"qui": "apu:etat", "sens": "recoit", "par": "cotisations_employeurs",
                     "note": "moins de compensation des allègements"}],
        "incidence": [{"horizon": "court", "qui": "les employeurs", "texte": "Le coût du "
                       "travail monte au-dessus de 2 Smic.", "source": SSS},
                      {"horizon": "long", "qui": "salariés et employeurs", "texte": "Une "
                       "part peut passer dans les salaires.", "source": f"{LMR} ; {BBG}"}],
        "canaux": ["emploi", "salaires", "cout_travail_tranche", "incidence_cotisations",
                   "compensation_exonerations", "financement_sous_secteurs"]},
    **{k: {
        "payeurs": [{"qui": "apu:etat", "sens": "paie", "par": "depense_publique"},
                    {"qui": "apu:apul", "sens": "paie", "par": "depense_publique"},
                    {"qui": "apu:secu:maladie", "sens": "paie", "par": "depense_publique",
                     "note": "les hôpitaux publics (fonction publique hospitalière), dans "
                             "les ASSO (Insee, t. 3.212, D1)"},
                    {"qui": "menages", "sens": "recoit", "par": "salaire_net"}],
        "incidence": [{"horizon": "immediat", "qui": "les fonctionnaires", "texte":
                       "Statutaire : le traitement monte.", "source": FULLERTON},
                      {"horizon": "long", "qui": "les salariés du privé", "texte": "Un "
                       "effet d'entraînement sur les salaires privés.", "source": NS}],
        "canaux": ["emploi_public", "consommation_menages", "salaires",
                   "financement_sous_secteurs"]}
       for k in ("melenchon/point_indice_10", "tondelier/point_indice_inflation")},
    "le_pen/lp26_suppression_cvec": {
        "levier": {"texte": "Code de l'éducation, art. L841-5 : la contribution de vie "
                   "étudiante et de campus (CVEC), versée aux Crous"},
        "payeurs": [{"qui": "menages", "sens": "recoit", "par": "cvec"},
                    {"qui": "apu:odac", "sens": "paie", "par": "autre",
                     "note": "les Crous et les établissements perdent la recette"}],
        "incidence": [INC_STAT],
        "canaux": ["consommation_menages", "financement_sous_secteurs"]},
    "melenchon/niches_fiscales_sociales": {
        "levier": {"texte": "Code général des impôts et Code de la sécurité sociale : les "
                   "dépenses fiscales et les exonérations sociales (non nommées)"},
        "payeurs": [{"qui": "menages", "sens": "paie", "par": "ir",
                     "note": "la clé par décile est celle de l'IR : une hypothèse"},
                    {"qui": "entreprises", "sens": "paie", "par": "autre"},
                    {"qui": "apu:etat", "sens": "recoit", "par": "impot_sur_le_revenu"}],
        "incidence": [INC_STAT], "canaux": ["consommation_menages", "offre_travail"]},
    **{k: {"levier": {"texte": "Livre des procédures fiscales (contrôle) ; Code de la "
                      "sécurité sociale (contrôle des cotisations)"},
           "payeurs": [{"qui": "menages", "sens": "paie", "par": "autre"},
                       {"qui": "entreprises", "sens": "paie", "par": "autre"},
                       {"qui": "apu:etat", "sens": "recoit", "par": "autre"}],
           "incidence": [{"horizon": "immediat", "qui": "les fraudeurs", "texte":
                          "Statutaire, si la fraude est recouvrée.", "source": NS}],
           "canaux": ["consommation_menages"]}
       for k in ("melenchon/fraude_fiscale", "ruffin/fraude_fiscale_sociale")},
    "retailleau/r13_zero_cotisation_1623_h": {
        "payeurs": [{"qui": "menages", "sens": "recoit", "par": "cotisations_salariales"},
                    {"qui": "entreprises", "sens": "recoit", "par": "cotisations_employeurs"},
                    {"qui": "apu:secu:vieillesse", "sens": "paie",
                     "par": "cotisations_employeurs"}],
        "incidence": [INC_STAT, {"horizon": "long", "qui": "salariés et employeurs",
                                 "texte": "Des heures déclarées en plus, plus que "
                                 "travaillées.", "source": NS}],
        "canaux": ["offre_travail", "emploi", "cout_travail_tranche",
                   "incidence_cotisations", "compensation_exonerations",
                   "financement_sous_secteurs"]},
}

# ------------------------------------------------- les montants déclarés : où ils tombent
DEP = {"chocs": {"apu_d_p51g": 0.08, "apu_d_d1": 0.25, "apu_d_d632": 0.09,
                 "apu_d_p2": 0.12, "apu_d_d62": 0.46},
       "instrument": "depense_publique", "menages_par": "prestations", "menages_part": 0.46}
CODES = {
    "DEP": DEP,
    "D1": {"chocs": {"apu_d_d1": 1.0}, "instrument": "depense_publique"},
    "INV": {"chocs": {"apu_d_p51g": 1.0}, "instrument": "investissement_public"},
    "P2": {"chocs": {"apu_d_p2": 1.0}, "instrument": "depense_publique"},
    "D632": {"chocs": {"apu_d_d632": 1.0}, "instrument": "depense_publique"},
    "D62R": {"chocs": {"apu_d_d62": 1.0}, "instrument": "depense_publique",
             "menages_par": "retraite"},
    "D62C": {"chocs": {"apu_d_d62": 1.0}, "instrument": "depense_publique",
             "menages_par": "chomage_brut"},
    "D62P": {"chocs": {"apu_d_d62": 1.0}, "instrument": "depense_publique",
             "menages_par": "prestations"},
    "D7": {"chocs": {"apu_d_d7": 1.0}, "instrument": None},
    "D3": {"chocs": {"apu_d_d3": 1.0}, "instrument": None},
    "D9": {"chocs": {"apu_d_d9": 1.0}, "instrument": None},
    "RD5": {"chocs": {"apu_r_d5": 1.0}, "instrument": None},
    "RIR": {"chocs": {"apu_r_d5": 1.0}, "instrument": "impot_sur_le_revenu",
            "menages_par": "ir"},
    "RIS": {"chocs": {"apu_r_d5": 1.0}, "instrument": None,
            "entreprises_par": "impot_societes"},
    "RD91": {"chocs": {"apu_r_d91": 1.0}, "instrument": None},
    "RD2": {"chocs": {"apu_r_d2": 1.0}, "instrument": None},
    "RCVAE": {"chocs": {"apu_r_d2": 1.0}, "instrument": None, "entreprises_par": "cvae"},
    "RCS": {"chocs": {"apu_r_d61": 1.0}, "instrument": "cotisations_salaries",
            "menages_par": "cotisations_salariales"},
    "RP13": {"chocs": {"apu_r_p13": 1.0}, "instrument": None},
    "RD61": {"chocs": {"apu_r_d61": 1.0}, "instrument": "cotisations_employeurs",
             "entreprises_par": "cotisations_employeurs"},
}
#: Pourquoi chaque code tombe là (le compte des APU, Insee, base 2020, t. 3.201).
RAISONS = {
    "DEP": "la composition de la dépense publique de Mésange (G2017-04, p. 106) : le "
           "programme ne dit pas quelle dépense",
    "D1": "des rémunérations d'agents publics (D1)",
    "INV": "de l'investissement public (P51g)",
    "P2": "des consommations intermédiaires des APU (P2)",
    "D632": "des prestations en nature (D632)",
    "D62R": "des pensions (prestations en espèces, D62), aux ménages au prorata des pensions",
    "D62C": "des allocations chômage (D62), aux ménages au prorata du chômage",
    "D62P": "des prestations en espèces (D62), aux ménages au prorata des prestations",
    "D7": "un transfert courant (D7) : la contribution au budget de l'UE (D76)",
    "D3": "des subventions (D3) aux entreprises",
    "D9": "un transfert en capital (D9) : aides à l'investissement",
    "RD5": "un impôt courant sur le revenu ou le patrimoine (D5)",
    "RIR": "l'impôt sur le revenu (D5), aux ménages au prorata de leur IR",
    "RIS": "l'impôt sur les sociétés (D5)",
    "RD91": "un impôt en capital (D91) : les droits de succession",
    "RD2": "un impôt sur la production ou les produits (D2)",
    "RCVAE": "la CVAE (D29)",
    "RCS": "des cotisations sociales (D61), aux ménages au prorata de leurs cotisations",
    "RP13": "des paiements partiels des ménages (P13) : un tarif payé à un service public",
    "RD61": "des cotisations des employeurs (D61)",
}
C27 = ("constant", 2027, 2027, 2035, None)
R32 = ("rampe", 2027, 2032, 2035, None)
# id → (code, profil, debut, plein, fin, calendrier ou None)
DECLAREES = {
    "attal/a2_frein_urgence_20_md": ("DEP", *C27),
    "attal/a9_big_bang_territorial": ("DEP", *C27),
    "attal/a14_epargne_retraite_naissance": ("D9", *C27),
    "attal/a31_geoenergie": ("D9", *C27),
    "le_pen/lp06_immigration_priorite_nationale": ("D62P", "calendrier", 2027, 2028, 2035,
                                                   {2027: 15.0, 2028: 29.0}),
    "le_pen/lp07_contribution_ue": ("D7", *C27),
    "le_pen/lp08_reorganisation_etat": ("DEP", *C27),
    "le_pen/lp09_agences": ("DEP", *C27),
    "le_pen/lp10_collectivites": ("DEP", *C27),
    "le_pen/lp15_age_legal_60_62": ("D62R", *R32),
    "le_pen/lp17_economies_retraites": ("D62R", *R32),
    "le_pen/lp19_impots_production": ("RD2", *C27),
    "le_pen/lp24_prime_activite_etudiante": ("D62P", *C27),
    "le_pen/lp25_permis_gratuit": ("D632", *C27),
    "lisnard/l2_cotisations_salaire_net": ("RCS", *R32),
    "lisnard/l3_impots_production_40_md": ("RD2", *R32),
    "lisnard/l6_economies_200_md": ("DEP", "calendrier", 2027, 2032, 2035,
                                    {2027: 80.0, 2032: 200.0}),
    "lisnard/l8_prestations_etrangers": ("D62P", *C27),
    "melenchon/logements_urgence": ("DEP", *C27),
    "melenchon/postes_education": ("D1", *C27),
    "melenchon/cantine_gratuite": ("D632", *C27),
    "melenchon/places_universite": ("DEP", *C27),
    "melenchon/hopitaux": ("DEP", *C27),
    "melenchon/plan_violences_sexistes": ("DEP", *C27),
    "melenchon/violences_enfants": ("DEP", *C27),
    "melenchon/annulation_coupes_indexation": ("DEP", *C27),
    "melenchon/planification_ecologique": ("INV", *C27),
    "melenchon/abrogation_reforme_2023": ("D62R", *C27),
    "melenchon/abrogation_assurance_chomage": ("D62C", *C27),
    "melenchon/impot_fortune_renforce": ("RD5", *C27),
    "melenchon/niches_fiscales_sociales": ("RIR", *C27),
    "melenchon/cvae_grandes_entreprises": ("RCVAE", *C27),
    "melenchon/taxe_zucman": ("RD5", *C27),
    "melenchon/droits_succession": ("RD91", *C27),
    "melenchon/reforme_is": ("RIS", *C27),
    "melenchon/taxe_multinationales": ("RIS", *C27),
    "melenchon/taxe_gafam": ("RD2", *C27),
    "melenchon/taxe_superprofits": ("RIS", *C27),
    "melenchon/taxe_transactions_financieres": ("RD2", *C27),
    "melenchon/taxe_rachats_actions": ("RD5", *C27),
    "melenchon/taxe_crypto_actifs": ("RD5", *C27),
    "melenchon/fraude_fiscale": ("RD5", *C27),
    "philippe/p3_deal_impots_production": ("RD2", *C27),
    "philippe/p5_retraite_65_ans_45_annuites": ("D62R", "rampe", 2027, 2035, 2035, None),
    "philippe/p18_fonds_adaptation_climat": ("INV", *C27),
    "philippe/p19_baisse_aides_entreprises": ("D3", *C27),
    "retailleau/r4_non_remplacement_400000": ("D1", *R32),
    "retailleau/r5_base_zero_operateurs": ("DEP", *R32),
    "retailleau/r6_politiques_au_tamis": ("DEP", *R32),
    "retailleau/r8_jour_carence": ("D62P", *R32),
    "retailleau/r9_effort_collectivites": ("DEP", *R32),
    "retailleau/r17_assurance_chomage": ("D62C", *C27),
    "retailleau/r22_impots_production_30_md": ("RD2", *R32),
    "retailleau/r23_prelevements_menages_21_md": ("RCS", *R32),
    "retailleau/r29_conge_naissance": ("D62P", *C27),
    "retailleau/r30_garde_enfants": ("RIR", *C27),
    "retailleau/r34_remuneration_enseignants": ("D1", *R32),
    "retailleau/r36_programme_ia_cout": ("INV", "constant", 2027, 2027, 2031, None),
    "ruffin/taxe_zucman": ("RD5", *C27),
    "ruffin/refonte_successions": ("RD91", *C27),
    "ruffin/dividende_climatique": ("RD5", *C27),
    "ruffin/cir_tpe_pme_eti": ("D9", *C27),
    "ruffin/aides_entreprises": ("D3", *C27),
    "ruffin/apprentissage_superieur": ("D3", *C27),
    "ruffin/produits_sante_prevention": ("D632", "calendrier", 2027, 2030, 2035,
                                         {2027: 3.0, 2030: 9.0}),
    "ruffin/fraude_fiscale_sociale": ("RD5", "rampe", 2027, 2031, 2035, None),
    "ruffin/leasing_social_public": ("D9", *C27),
    "ruffin/renovation_logements": ("D9", *C27),
    "ruffin/renovation_batiments_publics": ("INV", *C27),
    "ruffin/securite_civile_canadair": ("INV", *C27),
    "ruffin/plan_salles_des_fetes": ("INV", "constant", 2027, 2027, 2031, None),
    "ruffin/budget_elysee": ("P2", *C27),
    "ruffin/gestion_publique_forets": ("DEP", *C27),
    "tondelier/taxe_ca_additionnel_petroliers": ("RD2", *C27),
    "tondelier/cheque_carburant": ("D62P", *C27),
    "tondelier/contribution_gros_heritages": ("RD91", "rampe", 2027, 2030, 2035, None),
    "tondelier/plan_climat": ("INV", *C27),
    "tondelier/violences_3_md": ("DEP", *C27),
}
SIGNE = {"economie_depense": -1.0, "recette": -1.0, "depense": 1.0,
         "baisse_prelevements": 1.0}


TABLES = ROOT / "programmes" / "fiches"


def table(candidat):
    """Les données critiques d'un candidat, mesure par mesure (D-504), ou {}."""
    p = TABLES / f"{candidat}.yaml"
    if not p.exists():
        return {}
    t = {k: v for k, v in (yaml.safe_load(p.read_text(encoding="utf-8")) or {}).items()
         if not k.startswith("_")}            # `_sources` : les ancres YAML partagées
    ids = {m["id"] for m in json.loads((ROOT / "programmes" / f"{candidat}.json")
                                         .read_text(encoding="utf-8"))["mesures"]}
    inconnues = sorted(set(t) - ids)
    if inconnues:
        raise SystemExit(f"{p} : mesures inconnues du programme {inconnues}")
    return t


#: Les variables de la passe des ménages que la fiche d'une chiffrée relève de sa première
#: année (les écarts du rapport, Md€) : qui reçoit, qui paie.
ECARTS = ("salaire_net", "salaire_brut", "salaire_super_brut", "cotisations_salariales",
          "cotisations_employeur", "allegement_general", "retraite_imposable", "ir",
          "csg_deductible", "csg_retraite", "prelevements_pensions", "ppa", "rsa",
          "aide_logement", "af", "aspa", "garantie_autonomie", "pension_employeur_etat",
          "revenu_disponible", "cvae", "impot_societes", "prelevements_entreprise")


def _ecarts(rapport_chemin):
    """Les écarts de la première année du rapport d'une chiffrée, en Md€ (la passe figée
    de `premiere_annee_<scénario>.json`, à côté du rapport), ou None."""
    p = ROOT / rapport_chemin
    pa = p.with_name(p.name.replace("predictif_", "premiere_annee_", 1))
    if not pa.exists():
        return None
    r = json.loads(pa.read_text(encoding="utf-8"))
    reps = ([r["response"]] if r.get("kind") != "mixte"
            else [r["response"][k] for k in ("menages", "entreprises")])
    out = {}
    for rep in reps:
        t, tr = rep.get("totals") or {}, rep.get("totals_reform") or {}
        for k in ECARTS:
            if k in t and k in tr and abs(tr[k] - t[k]) >= 5e7:
                out[k] = round((tr[k] - t[k]) / 1e9, 2)
    return {"annee": r["request"].get("year"), "source": etude._relative(pa),
            "ecarts_md": out} if out else None


def _source_programme(m):
    s = m["sources"][0]
    return {"citation": s["citation"], "url": s["url"], "date": s.get("date")}


def _cout(sorte, m, montant):
    """Le coût de la première année, en euros, positif pour un coût, ou None : celui du
    rapport (`mechanical_frozen_eur` de sa première année) pour une chiffrée, le montant
    déclaré pour une hypothèse qui coûte (`declare.sens`)."""
    if sorte == "chiffree":
        rapport = json.loads((ROOT / montant["rapport"]).read_text(encoding="utf-8"))
        return float(rapport["years"][0]["mechanical_frozen_eur"])
    if sorte == "hypothese" and montant["annonce"]["sens"] in annonce.COUTE:
        return float(montant["annonce"]["montant_md"]) * 1e9
    return None


def _financement(m, candidat, cout_eur=None):
    """Le financement que la mesure annonce elle-même, lu dans son libellé ou sa citation ;
    celui du programme entier est l'affaire du volet `financement`. Pour une mesure qui
    coûte, `bilan` : le trou de `financement.annonce.financement` (D-482, jonction D-487),
    sans mesure liée (la carte n'en choisit pas : le lien est au volet `financement`)."""
    out = _annonce(m, candidat)
    if cout_eur is not None and cout_eur > 0:
        b = annonce.financement(m, cout_eur, ())
        out["bilan"] = {"cout_eur": round(b["cout_eur"]), "chiffre_eur": b["chiffre_eur"],
                        "trou_eur": round(b["trou_eur"]), "dit": b["dit"],
                        "source": "jumeau.financement.annonce.financement (D-482), sans "
                                  "mesure liée"}
    return out


def _annonce(m, candidat):
    motif = re.compile(r"financ|gagé|contrepartie", re.I)
    lieux = [(m["libelle"], f"le libellé du relevé (`programmes/{candidat}.json`), "
              f"d'après {m['sources'][0]['url']}")]
    lieux += [(x["citation"], x["citation"]) for x in m["sources"]]
    for texte, source in lieux:
        if motif.search(texte):
            return {"annonce": texte, "source": source, "chiffre": False,
                    "note": "le financement est énoncé, pas chiffré mesure par mesure"}
    return {"annonce": None, "source": None, "chiffre": False,
            "note": "la mesure n'annonce pas son financement ; le programme, peut-être "
                    "(volet `financement`)"}


def _hyp_declaree(code, profil, debut, plein, fin, cal, m, t=None):
    """Le montant d'une hypothèse : déclaré par le candidat (`declare`), ou calculé par la
    table (`t["montant"]` : l'assiette fois le paramètre, D-504). La table peut aussi dire
    sa catégorie (`code`), ses parts (`parts`, sourcées) et son profil."""
    t = t or {}
    tm = t.get("montant") or {}
    if tm.get("calcul"):
        d = {"montant_eur": float(tm["md"]) * 1e9, "sens": tm["sens"],
             "horizon": tm.get("horizon", m["parametre"]),
             "source": m["sources"][0]}
    else:
        d = m["declare"]
    md = d["montant_eur"] / 1e9
    signe = SIGNE[d["sens"]]
    c = dict(CODES[code])
    if t.get("parts"):
        c["chocs"] = t["parts"]["chocs"]
        for k in ("instrument", "menages_par", "menages_part", "entreprises_par"):
            if k in t["parts"]:
                c[k] = t["parts"][k]
    chocs = {k: round(signe * md * p, 6) for k, p in c["chocs"].items()}
    mont = {"origine": "hypothese",
            "annonce": {"montant_md": md, "sens": d["sens"], "horizon": d["horizon"],
                        "citation": d["source"]["citation"], "url": d["source"]["url"]},
            "chocs": chocs, "profil": profil,
            "debut": debut, "plein": plein, "fin": fin,
            "instrument": c.get("instrument"), "menages_par": c.get("menages_par"),
            "entreprises_par": c.get("entreprises_par"),
            "inclus_dans": t.get("inclus_dans")}
    if tm.get("calcul"):
        mont["annonce"]["par"] = "calcul"
        mont["annonce"]["calcul"] = tm["calcul"]
    if c.get("menages_part") is not None:
        mont["menages_part"] = c["menages_part"]
    hyps = [{"texte": f"Le montant tombe sur {RAISONS[code]}.", "source": NS
             if code in ("DEP", "D9", "D3", "RD5", "RD2") else
             "le compte des APU (Insee, base 2020, t. 3.201) : la nature de l'opération"},
            {"texte": f"La variante de Mésange la plus proche : "
                      f"{c.get('instrument') or 'aucune (le mode réduit ne lit aucun effet sur l’activité)'}.",
             "source": NS}]
    if profil == "calendrier":
        # Le calendrier du candidat : ses points, linéaire entre eux ; le dernier est le
        # régime, sur lequel les chocs sont écrits.
        pts = sorted(cal.items())
        mont["profil"] = "calendrier"
        mont["calendrier"] = {a: v for a, v in pts}
        mont["chocs"] = {k: round(signe * pts[-1][1] * p, 6) for k, p in c["chocs"].items()}
        mont["debut"], mont["plein"] = pts[0][0], pts[-1][0]
        hyps.append({"texte": "Le calendrier du candidat : " + ", ".join(
                         f"{v:g} Md€ en {a}" for a, v in pts) + " ; linéaire entre ses "
                         "points, tenu ensuite.", "source": d["source"]["citation"]})
    elif profil == "rampe":
        hyps.append({"texte": f"Montée en charge linéaire de {debut} à {plein}, puis le "
                              f"montant tenu jusqu'en {fin}.", "source": NS})
    else:
        hyps.append({"texte": f"Le montant tenu de {debut} à {fin}, en euros courants.",
                     "source": NS})
    hyps.append({"texte": "Le montant annoncé se réalise en entier (ρ = 1, D-319).",
                 "source": NS})
    return mont, hyps


def construire(candidat, m, scenarios, t=None):
    """Une fiche. `t`, l'entrée de la table du candidat (D-504), passe avant les fiches
    précises de ce fichier, qui passent avant les gabarits."""
    cle = f"{candidat}/{m['id']}"
    g = GABARITS[m["categorie"]]
    t = t or {}
    precise = {**PRECISES.get(cle, {}),
               **{k: t[k] for k in ("payeurs", "incidence", "canaux") if k in t}}
    chiffrage = m.get("chiffrage")
    refus = m.get("refus") or {}
    calcule = bool((t.get("montant") or {}).get("calcul"))
    if chiffrage:
        sorte = "chiffree"
    elif (m.get("declare") and cle in DECLAREES) or calcule:
        sorte = "hypothese"
    elif m["precision"] == "vague" or refus.get("porte") in ("vague", "chaine") \
            or m["categorie"] in ("regle_budgetaire",):
        sorte = "sans_choc"
    else:
        sorte = "parametre"
    levier = {"texte": g["texte"], "parametre": None, "valeur": None,
              "enonce": m["parametre"], "couche": None}
    if chiffrage:
        reforme = chiffrage["reforme"]
        levier.update({"parametre": ", ".join(reforme), "valeur": reforme,
                       "couche": chiffrage["couche"]})
    levier.update(precise.get("levier", {}))
    levier.update(t.get("levier", {}))
    hyps = list(t["hypotheses"]) if "hypotheses" in t else list(
        precise.get("hypotheses", []))
    if chiffrage and "hypotheses" in t and chiffrage.get("note"):
        hyps.insert(0, {"texte": chiffrage["note"], "source": "le chiffrage de la mesure "
                        f"(`programmes/{candidat}.json`)"})
    elif chiffrage and not hyps and chiffrage.get("note"):
        hyps.append({"texte": chiffrage["note"], "source": "le chiffrage de la mesure "
                     f"(`programmes/{candidat}.json`)"})
    if sorte == "chiffree":
        scen, rapport = scenarios[cle]
        montant = {"origine": "rapport", "scenario": scen, "rapport": rapport}
        if m.get("declare"):
            montant["annonce_md"] = m["declare"]["montant_eur"] / 1e9
        ecarts = _ecarts(rapport)
        if ecarts:
            montant["premiere_annee"] = ecarts
    elif sorte == "hypothese":
        code, *prof = DECLAREES.get(cle) or ((t.get("montant") or {}).get("code"), *C27)
        if t.get("code"):
            code = t["code"]
        if t.get("profil"):
            p = t["profil"]
            prof = [p["profil"], p["debut"], p.get("plein", p["debut"]), p["fin"],
                    p.get("calendrier")]
        montant, h = _hyp_declaree(code, *prof, m, t)
        if "hypotheses" not in t:
            hyps += h
    else:
        raison = refus.get("raison", "")
        montant = {"origine": "aucun",
                   "manque": t.get("manque") or (
                       f"{raison} (porte « {refus.get('porte')} »)" if raison
                       else "aucun montant énoncé")}
        if sorte == "parametre" and m.get("declare"):
            montant["annonce_md"] = m["declare"]["montant_eur"] / 1e9
    # Une mesure sans choc n'a de payeurs, d'incidence et de canaux que ceux que sa table
    # écrit (D-504) : pas ceux du gabarit de sa catégorie.
    vide = sorte == "sans_choc"
    if vide:
        precise = {k: t[k] for k in ("payeurs", "incidence", "canaux") if k in t}
    fin = _financement(m, candidat, _cout(sorte, m, montant))
    if t.get("financement"):
        bilan = fin.get("bilan")
        fin = {"annonce": None, "source": None, "chiffre": False, **t["financement"]}
        if bilan:
            fin["bilan"] = bilan
    out = {
        "schema": transmission.SCHEMA, "mesure": m["id"], "candidat": candidat,
        "libelle": m["libelle"], "sorte": sorte, "source": _source_programme(m),
        "levier": levier,
        "payeurs": precise.get("payeurs", [] if vide else g["payeurs"]),
        "incidence": precise.get("incidence", [] if vide else g["incidence"]),
        "financement": fin,
        "canaux": precise.get("canaux", [] if vide else g["canaux"]),
        "hypotheses": hyps, "montant": montant}
    for k in transmission.FACULTATIVES:
        if t.get(k) is not None:
            out[k] = t[k]
    return out


def scenarios_chiffres():
    out = {}
    for s in etude.definitions():
        if not s.programme or s.refus or not s.page.exists():
            continue
        for m in s.mesures:
            p = s.rapports / "mesures" / m.mesure / f"predictif_{m.scenario}.json"
            out[f"{s.programme}/{m.mesure}"] = (m.scenario, etude._relative(p))
        prog = s.volets[0].scenario
        out[f"{s.programme}/*"] = (prog, etude._relative(s.rapports /
                                                          f"predictif_{prog}.json"))
    return out


def candidats():
    return sorted({s.programme for s in etude.definitions()
                   if s.programme and not s.refus and s.page.exists()})


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--verifier", action="store_true")
    args = ap.parse_args(argv)
    scen = scenarios_chiffres()
    ecrites = 0
    for c in candidats():
        prog = json.loads((ROOT / "programmes" / f"{c}.json").read_text(encoding="utf-8"))
        chiffrees = [m for m in prog["mesures"] if m.get("chiffrage")]
        for m in chiffrees:
            # Un programme d'une seule mesure chiffrée n'a pas de rapport de mesure seule :
            # le rapport du programme est le sien.
            scen.setdefault(f"{c}/{m['id']}", scen[f"{c}/*"])
        dossier = transmission.ICI / c
        dossier.mkdir(exist_ok=True)
        donnees = table(c)
        for m in prog["mesures"]:
            d = construire(c, m, scen, donnees.get(m["id"]))
            texte = yaml.safe_dump(d, allow_unicode=True, sort_keys=False, width=88)
            (dossier / f"{m['id']}.yaml").write_text(texte, encoding="utf-8")
            ecrites += 1
    print(f"{ecrites} fiches écrites")
    if args.verifier:
        for f in sorted(transmission.ICI.glob("*/*.yaml")):
            transmission.charger(f)
        print(transmission.releve())
        print(transmission.qualite())


if __name__ == "__main__":
    main()
