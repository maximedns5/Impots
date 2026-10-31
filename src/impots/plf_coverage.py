"""The PLF coverage triage — decided in advance, and checked by tests (F1).

WHAT THIS IS FOR. The PLF 2027 lands in early October. Deciding on publication day what
the tool can price is deciding it under time pressure, with the answer already visible,
which is the condition under which "we couldn't price X" becomes an excuse rather than a
limitation. Deciding it NOW, against the PLF 2026's real article structure, makes every
refusal a pre-registered one.

WHY THE PLF 2026. The 2027 text does not exist yet, and guessing its article numbers would
be exactly the fabrication this project forbids. What survives renumbering is the CATEGORY
— «niche IR dons», «IS taux», «fiscalité énergie» — so the categories are the deliverable
and the 2026 article numbers are only their evidence. Source: Assemblée nationale, texte
n° 1906 (17e législature), manifested at sha256 88ef308e62a2, split mechanically into 82
articles of which 29 are «I – Impôts et ressources autorisées / B – Mesures fiscales».

THE HEADLINE IS BAD AND THAT IS THE POINT. Of 29 fiscal articles in a real PLF, ONE
produces a number this tool can defend today. Five more have their parameters in the tree
but cannot be priced on this population. The remaining twenty-three are outside the model's
structure or its data. A tool that priced the whole PLF would be a tool lying about
twenty-three articles.

THREE BUCKETS, AND TWO FLAGS THE BUCKETS CANNOT CARRY. The brief asks for exactly one
bucket per article, and that is what `bucket` holds. But «priceable» turned out to hide two
independent questions, and collapsing them is how a confident zero gets published:

* `engine_ready` — the parameters exist and the formula reads them, so wiring is all that
  is missing;
* `population_can_exercise` — our synthetic population actually contains taxpayers the
  measure bites on.

Article 2 (CDHR) is the case that forced the distinction. Its parameters resolve, its
variable computes, and it fires: -75 836 EUR on a foyer with 2 M EUR of dividends. By the
letter of «small knob» it qualifies. But the CDHR is a top-up to a 20 % effective rate, and
a salary-only taxpayer already exceeds that — so on a population with no capital income the
base is empty BY CONSTRUCTION, and wiring it would publish 0,00 EUR against a government
yield of about a billion. `engine_ready=True, population_can_exercise=False` says that in
two fields; one bucket cannot.

THIS FILE IS CHECKED, NOT ASSERTED. `tests/test_plf_coverage.py` verifies that every knob
named here exists verbatim in the wire model and that every parameter path resolves at
2026-01-01. A triage that drifts from the code it describes is worse than none, because it
will be believed on publication day.

FOUR FINDINGS THAT ONLY APPEARED BECAUSE SOMEONE LOOKED, each of which would have produced
a wrong number in October:

* **Article 9 (dons Coluche) would have priced at exactly zero.** The knob is correct and
  the parameter is live — but the baseline tree ALREADY carries the 2 000 EUR ceiling from
  2025-01-01, because the measure was enacted. Pricing the article against it is pricing a
  change against itself. And even against a 1 000 EUR counterfactual the imputed donation
  base runs 157-447 EUR per decile with no intra-decile dispersion, so no household in this
  population ever reaches either ceiling.
* **Article 11 (CVAE) is not expressible with one knob.** `cvae_taux_max` governs only the
  bracket above 50 M EUR of turnover. Measured: that bracket carries 71,9 % of baseline
  CVAE, and 205 959 of 213 730 weighted payers — 96,4 % — sit below it and see no rate
  change at all, while the article moves all six scale coefficients together.
* **Article 5 hides one reachable measure in a package of twenty-three.** Its 12° abrogates
  article 199 quater F, the frais-de-scolarité réduction, for which three knobs exist and
  are live. The package as a whole is out of structure; that sub-measure is not.
* **A CDHR reform would move the deciles without moving the reported IR line.** The
  variable enters `impots_directs` and so `revenu_disponible`, but not
  `impot_revenu_restant_a_payer`, which is what the output registry publishes as `ir`.
  Measured: raising `taux_cdhr` from 20 % to 30 % moves `revenu_disponible` by 205 400 EUR
  and `impot_revenu_restant_a_payer` by nothing. Since `STATE_RECEIPTS` carries no CDHR
  row, the double-entry guard would refuse such a run outright — which is the RIGHT
  outcome, and is the wiring prerequisite to satisfy before the knob can exist.

HOW TO USE IT IN OCTOBER. Read the published articles, map each to a category below, and
take the bucket. Where the 2027 text carries a category absent here, that is a new triage
decision — make it, record it, and say it was made on the day rather than in advance.
"""

from __future__ import annotations

from dataclasses import dataclass

#: Where the article structure came from. Stated because the pointer rule binds: the
#: identifier travels, the URL is a convenience (docs/SOURCE_POINTERS.md).
SOURCE = (
    "Assemblée nationale, texte n° 1906 (17e législature), projet de loi de finances "
    "pour 2026, articles avec exposé des motifs. Manifesté : "
    "plf2026_texte_an_b1906.html, sha256 88ef308e62a2. La section fiscale est "
    "« I – Impôts et ressources autorisées / B – Mesures fiscales », articles 2 à 30. "
    "ATTENTION : c'est le PROJET déposé, pas la loi promulguée (LOI n° 2026-103 du "
    "19 février 2026) — c'est le bon comparateur pour une structure de dépôt."
)

#: FOUR buckets, not three. The brief asked for three and one article broke them.
#:
#: `population_blind` is the case where the ENGINE could price the article — parameters in
#: the tree, formula reading them — but this population contains no taxpayer the measure
#: bites on. Wiring it would publish a confident zero, which is worse than a refusal
#: because it carries the provenance of a real answer. Collapsing it into `small_knob`
#: promises publication week a number that will be nonsense; collapsing it into
#: `not_priceable` loses the fact that the unlock is DATA and nothing else.
BUCKETS = ("priceable_now", "small_knob", "population_blind", "not_priceable")


@dataclass(frozen=True)
class Article:
    """One fiscal article, and what this tool can honestly do with its category."""

    numero: int
    categorie: str
    intitule: str
    bucket: str
    knobs: tuple[str, ...] = ()
    paths: tuple[tuple[str, ...], ...] = ()
    engine_ready: bool = False
    population_can_exercise: bool = False
    confiance: str = "moyenne"
    raison: str = ""
    unlock: str = ""
    """What would make this priceable, for a data refusal. Required for
    `population_blind`.

    A door that is far away is still a door, and the document should not pretend
    otherwise in either direction: naming the unlock is not a promise that it is coming
    (real income microdata is not available for the foreseeable future, D-096), and its
    absence would not make the refusal permanent."""
    layers: tuple[str, ...] = ("mechanical",)
    banners: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.bucket not in BUCKETS:
            raise ValueError(f"bucket inconnu : {self.bucket}")
        if self.bucket == "population_blind" and not self.unlock:
            raise ValueError(
                f"art. {self.numero} : « population_blind » sans unlock. Une case qui dit "
                f"« le moteur pourrait, les données ne peuvent pas » doit dire CE QUI "
                f"ouvrirait la porte, sinon elle est indiscernable d'un refus définitif.")


ARTICLES: tuple[Article, ...] = (
    Article(
        numero=2, categorie='IR contribution exceptionnelle sur les hauts revenus (CDHR/CEHR)',
        intitule='Prorogation de la contribution différentielle sur les hauts revenus',
        bucket='population_blind',
        knobs=(),
        paths=(),
        engine_ready=True, population_can_exercise=False,
        unlock=(
            "income microdata THAT SEES THE TOP — échantillon lourd DGFiP / POTE. "
            "PAS l'ERFS : la clé nommée par D-096 a été OBTENUE (millésime 2022, "
            "FPR) et essayée, et elle n'ouvre pas (D-141). Le motif « seuil sur "
            "ratio » (D-105.2) est MORT — il visait l'imputation uniforme dans la "
            "cellule, et des microdonnées portent de la dispersion réelle ; la "
            "reconstruction rend 0,99 md€ contre 1,50 publié une fois sa jambe PFU "
            "rétablie. Ce qui refuse est autre : la CDHR vit tout entière dans le "
            "dernier centile, qu'une enquête auprès des ménages sous-compte par "
            "construction — bande classée sans verdict par le tableau E2, préenregistrée "
            "avant tout chiffre ERFS. Le défaut est dans le PLAN DE SONDAGE, pas dans "
            "la granularité : aucune enquête ne l'ouvrira. Historique : la "
            "CDHR est définie par un seuil portant sur un RATIO — le taux moyen "
            "d'imposition rapporté au RFR — donc une imputation uniforme dans la cellule "
            "met tous les foyers du même côté du seuil de 20 %, et le rendement saute de "
            "zéro à des milliards selon le placement de la moyenne. Ce n'est PAS une "
            "question de finesse : la granularité publiée descend au millime (DGFiP "
            "n° 41) et cela ne suffit pas, parce que le placement intra-cellule EST la "
            "réponse. Aucune imputation par fractile n'ouvrira cette porte, si fine "
            "soit-elle ; seules des microdonnées le peuvent. F1b (D-097) a mesuré que la "
            "même source ouvre en revanche le PFU, qui est proportionnel."
        ),
        confiance='haute',
        raison="data. Aucun knob CDHR/CEHR n'existe dans knobs.json, et les paramètres openfisca existent bien (impot_revenu.contributions_exceptionnelles.contribution_differentielle_hauts_revenus.{taux_cdhr, seuil_celibataire, seuil_couple, taux_acompte, taux_penalite_acompte} résolvent True au 2026-01-01, avec taux_cdhr = 0,20 et seuil = 250 000, et openfisca porte déjà les variables contribution_differentielle_hauts_revenus*) — donc le câblage serait facile. Ce n'est pas pour autant du small_knob : le câbler produirait un zéro confiant. La CDHR ne mord que sur les foyers dont le taux moyen d'imposition est INFÉRIEUR à 20 % du RFR au-dessus de 250 k€, c'est-à-dire exactement les foyers que cette population ne sait pas construire. KNOWN_LIMITATIONS : « No capital income, no property income — the top of the distribution is a construction; nothing above roughly the 95th percentile is publishable » et « N",
    ),
    Article(
        numero=3, categorie='taxe sur le patrimoine des sociétés (holdings)',
        intitule="Instauration d'une taxe sur le patrimoine financier des holdings patrimoniales",
        bucket='not_priceable',
        knobs=(),
        paths=(),
        engine_ready=False, population_can_exercise=False,
        confiance='haute',
        raison="structure (et data en second rideau). Le modèle entreprises n'a aucun bilan et aucune structure de détention : data/processed/firms_2023.parquet ne porte que firm_id, cell, naf_section, taille, weight, chiffre_affaires, valeur_ajoutee, resultat_comptable, benefice_imposable, capital_libere_detenu_personnes_physiques. Il n'y a donc ni valeur vénale d'actifs, ni disponibilités, ni titres, ni participations, ni part de revenus passifs, ni personne physique détentrice — c'est-à-dire aucune des quatre conditions d'assujettissement ni aucun terme de l'assiette. Le secteur n'est connu qu'au niveau SECTION NAF, si bien qu'une holding (64.20Z) n'est même pas distinguable du reste de la section K. Aucun knob entreprises (FirmReformSpec : IS, CS, C3S, CVAE, CEBGE) n'approche cet instrument, et aucun paramètre correspondant n'existe dans l'arbre. Côté ménages, le volet IFI (art. 975 nouveau VII) est",
    ),
    Article(
        numero=4, categorie='IS contribution exceptionnelle (CEBGE)',
        intitule='Prorogation en 2026 avec division par deux des taux de la contribution exceptionnelle sur les bénéfices des gr',
        bucket='priceable_now',
        knobs=('cebge_seuils_et_taux',),
        paths=(),
        engine_ready=True, population_can_exercise=True,
        confiance='haute',
        raison="Le knob apparié cebge_seuils_et_taux exprime exactement le cœur de l'article. Vérifié en exécution : FirmReformSpec(cebge_seuils_et_taux=[{seuil_ca: 1e9, taux: 0.103}, {seuil_ca: 3e9, taux: 0.206}]) + make_reform(..., 2026) passe verify_scales et donne au 2026-01-01 seuil_ca 1,0 Md, taux_base 0,103, seuil_ca_taux_majore 3,0 Md, taux_majore 0,206, bornes de lissage 1,1 Md et 3,1 Md — soit les trois bandes du texte, la largeur de 100 M€ étant dérivée du seuil et non inventée (elle existe bien au 2026-01-01). La CEBGE est modélisée (variables.cebge, assiette = moyenne de deux exercices d'IS) et réconciliée : 9,3 Md€ contre 7,5 Md€ publiés, +23,1 %, dans la tolérance de ±25 %. TROIS RÉSERVES à pré-enregistrer. (1) Contrefactuel : l'arbre de référence porte déjà la LF 2026 PROMULGUÉE (seuil monté à 1,5 Md€ en 2026, taux maintenus à 20,6/41,2 — le commentaire du YAML dit explicitement que « la",
    ),
    Article(
        numero=5, categorie='suppressions de niches (paquet multi-instruments)',
        intitule='Diverses suppressions et rationalisations de dépenses fiscales',
        bucket='population_blind',
        knobs=('frais_scolarite_college', 'frais_scolarite_lycee', 'frais_scolarite_superieur'),
        paths=(),
        engine_ready=True, population_can_exercise=False,
        unlock='a published frais-de-scolarité base that separates collège / lycée / supérieur. `niches.py` excludes scolarité from IMPUTABLE deliberately: the 2042 cases are COUNTS of children and the published DGFiP column aggregates the three levels, so there is nothing to impute a euro base from. Real income microdata would also do it. The three knobs themselves are live and price correctly on a cas-type.',
        confiance='moyenne',
        raison="structure pour la masse de l'article, data pour la seule part qui semblait atteignable. L'article est un paquet de 23 suppressions portant sur des instruments dont le modèle n'a majoritairement aucune entité : accises énergie B100/E85 du code des impositions sur les biens et services, taxe à l'essieu (véhicules), TVA, droits d'enregistrement et donations, taxe foncière non bâtie, amortissements et crédits d'impôt à l'IS (le module entreprises calcule un IS AVANT crédits d'impôt — « our IS is already before crédits — the model has none »). Le volet indemnités journalières ALD est du data pur : la population ne porte que salaire_brut_annuel, pension_annuelle et chomage_annuel, aucune IJ. LE PIÈGE, et c'est pour lui que ce refus est pré-enregistré : trois knobs existent bel et bien pour le 12° (frais_scolarite_college, frais_scolarite_lycee, frais_scolarite_superieur → impot_revenu.calcul_r",
    ),
    Article(
        numero=6, categorie='abattement IR sur pensions',
        intitule="Création d'un abattement forfaitaire en faveur des personnes retraitées",
        bucket='small_knob',
        knobs=(),
        paths=(('impot_revenu', 'calcul_revenus_imposables', 'deductions', 'abatpen', 'taux'), ('impot_revenu', 'calcul_revenus_imposables', 'deductions', 'abatpen', 'min'), ('impot_revenu', 'calcul_revenus_imposables', 'deductions', 'abatpen', 'max'), ('impot_revenu', 'calcul_revenus_imposables', 'abat_rni', 'contribuable_age_invalide')),
        engine_ready=True, population_can_exercise=True,
        confiance='moyenne',
        raison="Aucun knob de ReformSpec ne touche l'abattement pensions (knobs.json n'en contient pas), mais les quatre paramètres bougés existent et résolvent (exists_at = True au 2026-01-01). Le a bis est exactement représentable : la formule openfisca `revenu_assimile_pension_apres_abattements` calcule max(0, p − round(max(taux·p, min))), donc taux = 0, min = 2 000 et max relevé donnent min(p, 2 000) par individu, ce qui est littéralement le texte. La suppression de la branche âge du 157 bis se fait en mettant à zéro les montants du barème `contribuable_age_invalide` — ce qui est EXACT dans cette population et seulement dans elle, parce que caseP/caseF ne sont jamais renseignés par to_openfisca.py : personne n'est invalide, donc l'éligibilité y est purement l'âge ≥ 65 et le carve-out invalidité conservé par l'article ne coûte rien ici (il coûterait dans la réalité, donc le chiffrage sur-abroge légèr",
    ),
    Article(
        numero=7, categorie='niche investissement outre-mer (IR et IS)',
        intitule="Réforme du régime d'aide fiscale à l'investissement productif outre-mer",
        bucket='not_priceable',
        knobs=(),
        paths=(),
        engine_ready=False, population_can_exercise=False,
        confiance='haute',
        raison="Refus, motif STRUCTURE en premier lieu. Le cœur de l'article est l'IS : 217 undecies (déduction), 244 quater W (crédit d'impôt) et 244 quater Y (réduction d'impôt). Or le moteur entreprises n'a AUCUN instrument de ce genre — variables.py ne définit que chiffre_affaires, benefice_imposable, valeur_ajoutee, impot_societes, contribution_sociale_is, c3s, cebge, cvae : pas un seul crédit ni une seule réduction d'impôt, pas d'investissement, pas de localisation géographique. FirmReformSpec le confirme : onze knobs, tous des taux/seuils/abattements de barème, rien qui ressemble à une aide à l'investissement. Il n'y a donc pas de paramètre à bouger, et l'article ne peut pas être exprimé même partiellement de ce côté. La contrainte DATA mord ensuite du côté ménages : les paramètres 199 undecies B existent bien dans l'arbre (impot_revenu.calcul_reductions_impots.outremer_investissement.doment/doms",
    ),
    Article(
        numero=8, categorie='niche IR souscription au capital de PME / fonds',
        intitule="Modernisation de la réduction d'impôt sur le revenu « Madelin »",
        bucket='not_priceable',
        knobs=(),
        paths=(),
        engine_ready=False, population_can_exercise=False,
        confiance='haute',
        raison="Refus, motif DATA. La population ne porte aucune base de souscription : l'imputation de niches (niches.py) est explicitement limitée à cinq cases — f7db, f7ga, f7ac, f7uf, f7ud — et le commentaire de schemas.py note que f7d* contient « cinq cases de souscription PME » qu'on a délibérément laissées de côté. S'y ajoutent deux limitations connues qui mordent ensemble : « No capital income, no property income — nothing above roughly the 95th percentile is publishable », alors que l'IR-PME est concentrée dans le dernier centile, et « No réductions or crédits d'impôt » hors les cinq imputées. Une tentative naïve serait pire qu'un refus : les paramètres existent (impot_revenu.calcul_reductions_impots.souscriptions.souscriptions_parts_fcpi_fip.taux / taux_corse / taux_outre_mer / plafond_celibataire / plafond_couple, et souscriptions.pme.souscription_capital.*), donc mettre taux à zéro pour abro",
    ),
    Article(
        numero=9, categorie='niche IR dons',
        intitule="Doublement de l'incitation fiscale à la générosité des particuliers en faveur des organismes d'aide aux personnes en difficulté",
        bucket='population_blind',
        knobs=('dons_coluche_plafond', 'dons_coluche_taux'),
        paths=(('impot_revenu', 'calcul_reductions_impots', 'dons', 'dons_coluche', 'plafond'),),
        engine_ready=True, population_can_exercise=False,
        unlock='within-decile dispersion of donations. The imputation gives every claimant in a decile the same base (157-447 EUR), so no household ever reaches a 1 000 or 2 000 EUR ceiling and the ceiling knob is inert in aggregate however correct it is. Microdata, or a published distribution of donation amounts rather than a per-decile mean, would unlock it. Note this article ALSO needs `mirror`: the tree already carries the 2 000 EUR ceiling.',
        confiance='haute',
        banners=('zero_base_niche',),
        raison=(
            "data, deux fois, et le knob n'y est pour rien — il est exact. "
            "(1) LE COMPARATEUR CONTIENT DÉJÀ LA MESURE : le plafond dons Coluche vaut "
            "2 000 EUR dans l'arbre depuis 2025-01-01 (1 000 EUR de 2020 à 2024), parce "
            "que le doublement a été voté. Chiffrer l'article contre cette ligne de base "
            "rend exactement 0,00 EUR — un zéro confiant, indiscernable d'une mesure sans "
            "effet. Vérifié en lisant l'arbre année par année. "
            "(2) MÊME CONTRE UN CONTREFACTUEL À 1 000 EUR, L'ASSIETTE EST VIDE : la base "
            "de dons imputée par `niches.py` va de 157 EUR (D4) à 447 EUR (D1), sans "
            "aucune dispersion intra-décile — « every claimant in a decile gets the same "
            "base » — donc aucun foyer de cette population n'atteint 1 000 ni a fortiori "
            "2 000 EUR. Le rendement réel de la mesure vient entièrement de la queue de "
            "la distribution des dons, que l'imputation aplatit. "
            "La CATÉGORIE « niche IR dons — plafond » reste chiffrable sur cas-type, avec "
            "la bannière zero_base_niche en agrégat ; c'est CET article, contre CE "
            "comparateur, qui ne l'est pas."
        ),
    ),
    Article(
        numero=10, categorie='fiscalité agricole (BA / IS agricole / DMTG)',
        intitule='Ajustement de certains dispositifs de soutien au secteur agricole (prorogation de la dotation pour épargne de ',
        bucket='not_priceable',
        knobs=(),
        paths=(),
        engine_ready=False, population_can_exercise=False,
        confiance='haute',
        raison="data, principalement. Le refus tient à la population, pas au droit. Côté ménages, KNOWN_LIMITATIONS l'écrit noir sur blanc : « No self-employment income. 3.87 M people are recorded in employment as indépendants and receive nothing » — il n'existe aucun bénéfice agricole, aucun résultat d'exploitation, aucun stock ni cheptel dans le fichier. Une DEP, une provision pour hausse de valeur des stocks ou une exonération de plus-value sur indemnité d'abattage s'appliquent toutes à une assiette dont la valeur est identiquement nulle chez nous : le chiffrage rendrait zéro, ce qui n'est pas une réponse mais une absence d'assiette. Côté entreprises, la population synthétique est bâtie sur des cellules NAF section × taille (la section A existe) mais ne porte que chiffre d'affaires, valeur ajoutée et résultat ; ni cheptel, ni indemnité sanitaire, ni certification bio ne sont observables, et le résult",
    ),
    Article(
        numero=11, categorie='impôts de production (CVAE)',
        intitule='Anticipation de la suppression progressive de la CVAE',
        bucket='small_knob',
        knobs=('cvae_taux_max', 'cvae_degrevement'),
        paths=(),
        engine_ready=True, population_can_exercise=True,
        confiance='moyenne',
        raison="Les deux knobs expriment exactement le cœur de l'article, et le baseline porte déjà le contrefactuel qu'il amende : j'ai lu la valeur au 01/01/2026, cvae.taux_max = 0,0028 et cvae.degrevement.montant = 188 €, soit précisément la trajectoire LF 2025 que le PLF abroge. Le chiffrage est donc un diff à deux curseurs, année par année : 2026 (cvae_taux_max = 0,0019 ; cvae_degrevement = 125), 2027 (0,0009 ; 63), 2028 (suppression). Le couple taux/dégrèvement est apparié dans le YAML lui-même (0,28 %↔188, 0,19 %↔125, 0,09 %↔63), donc bouger le taux sans le dégrèvement serait un demi-barème — les deux knobs sont nécessaires et suffisants pour la CVAE. Bande : C4 (production_tax_investment) revendique nommément responds_to_knobs: [cvae_taux_max, cvae_degrevement], estimée sur la baisse d'impôts de production de 2021 (IPP rapport 60), bande centrée sur zéro [−0,071 ; +0,069] en % d'investissement p",
    ),
    Article(
        numero=12, categorie='dispositif fiscal zoné (QPV / ZFU) — IS-IR, CFE, TFPB',
        intitule='Renforcement des dispositifs fiscaux de soutien à la géographie prioritaire de la politique de la ville',
        bucket='not_priceable',
        knobs=(),
        paths=(),
        engine_ready=False, population_can_exercise=False,
        confiance='haute',
        raison="data pour le volet principal, structure pour le reste. Data : l'exonération de 44 octies B est définie par la localisation de l'établissement dans un QPV, et la population d'entreprises ne porte aucune géographie. Elle est construite sur des cellules NAF section × taille — 19 sections × trois classes de taille, 400 firmes tirées par cellule — et rien d'autre : ni commune, ni quartier, ni date de création ou de reprise, ni distinction activité commerciale/artisanale/santé, ni effectif salarié individuel. Aucune de ces cinq conditions cumulatives n'est observable, et l'ensemble ne peut pas être approché par une cellule sectorielle : les QPV ne sont pas un secteur. Un chiffrage exigerait un dénombrement d'établissements par QPV que le projet ne détient pas, pas un paramètre à bouger. Structure pour l'autre moitié : la CFE, la taxe foncière sur les propriétés bâties, la taxe sur les bureaux ",
    ),
    Article(
        numero=13, categorie='fiscalité des véhicules (malus CO2, malus masse, taxes annuelles, taxe',
        intitule='Verdissement de la fiscalité sur les véhicules',
        bucket='not_priceable',
        knobs=(),
        paths=(),
        engine_ready=False, population_can_exercise=False,
        confiance='haute',
        raison="structure. L'outil ne contient aucune des taxes que cet article modifie, et j'ai vérifié plutôt que supposé : au 01/01/2026, taxation_indirecte ne porte que {alcools_autres_boissons, produits_energetiques, taxes_assurances, taxes_energie_dans_logement, taxes_tabacs, tva} — pas de malus, pas de taxe annuelle sur les véhicules, pas de taxe incitative LOM ; et rien du code des impositions sur les biens et services (livre IV, chapitre Ier), qui est le siège de tout le II de l'article. Il n'y a pas non plus d'entité « véhicule » : ni parc, ni immatriculation, ni émissions de CO2, ni masse en ordre de marche, ni catégorie de réception M1/N1/L6e/L7e — donc même en écrivant les barèmes on n'aurait aucune assiette à leur appliquer. Le volet 39 decies A (déduction exceptionnelle poids lourds) s'ajoute par la data : la population d'entreprises ne porte ni investissement ni acquisition de véhicules,",
    ),
    Article(
        numero=14, categorie='fiscalité transport routier (taxe poids lourds)',
        intitule="Ajustements de la taxe sur l'utilisation par les poids lourds de certaines voies du domaine public routier (éc",
        bucket='not_priceable',
        knobs=(),
        paths=(),
        engine_ready=False, population_can_exercise=False,
        confiance='haute',
        raison="structure. L'outil ne possède aucun instrument de taxation de l'usage routier ni aucune entité « véhicule » ou « transporteur » : ni ReformSpec (57 knobs ménages : barème IR, décote, QF, CSG, allègements, prestations, IFI, niches) ni FirmReformSpec (11 knobs : IS, CS, C3S, CVAE, CEBGE) n'exposent quoi que ce soit de proche, et un grep de src/impots ne trouve aucune référence à une taxe d'usage routier. Aucun paramètre openfisca correspondant n'existe non plus (le sous-arbre taxation_indirecte.produits_energetiques ne contient que TICPE, majorations régionales TICPE et TGAP carburants), donc ce n'est pas non plus un small_knob. S'y ajoute, à titre secondaire, un motif de scope : il s'agit d'une taxe affectée à des collectivités territoriales, et la modification porte pour l'essentiel sur des facultés ouvertes à l'autorité compétente par délibération, dont le rendement dépend de choix loca",
    ),
    Article(
        numero=15, categorie="fiscalité automobile (taxe d'immatriculation)",
        intitule="Stabilité des prélèvements sur les transports au bénéfice d'Île-de-France Mobilités",
        bucket='not_priceable',
        knobs=(),
        paths=(),
        engine_ready=False, population_can_exercise=False,
        confiance='haute',
        raison="structure. Il n'existe dans l'outil ni instrument « taxe sur les certificats d'immatriculation » ni variable de détention ou d'acquisition de véhicule : aucun knob de knobs.json ne s'en approche, et l'arbre openfisca chargé (impot_revenu, prelevements_sociaux, prestations_sociales, taxation_capital, taxation_indirecte, taxation_societes, taxe_habitation) ne contient aucun nœud de taxe d'immatriculation — donc pas de small_knob possible. Le motif de données jouerait aussi (la population EEC ne porte ni véhicule, ni puissance fiscale, ni acte d'immatriculation), mais il est second : même avec la donnée, l'instrument n'existe pas. Motif secondaire de scope : ressource affectée à un établissement public local, dont le quantum dépend d'une délibération d'IDFM. Aucune couche ne tourne, aucun bandeau ne se déclenche.",
    ),
    Article(
        numero=16, categorie='fiscalité énergie (incorporation de biocarburants)',
        intitule="Renforcement des incitations à l'utilisation d'énergie renouvelable dans les transports",
        bucket='not_priceable',
        knobs=(),
        paths=(),
        engine_ready=False, population_can_exercise=False,
        confiance='haute',
        raison="structure. Le prélèvement porte sur les metteurs à la consommation de carburants, une entité que l'outil n'a pas : le module entreprises ne connaît que l'IS, la CS, la C3S, la CVAE et la CEBGE, assis sur bénéfice et chiffre d'affaires, et rien qui ressemble à des volumes d'énergie mis à la consommation. J'ai vérifié l'arbre plutôt que de le supposer : taxation_indirecte.produits_energetiques existe et contient ticpe, major_regionale_ticpe_gazole, major_regionale_ticpe_super et tgap_carburants — mais tgap_carburants ne porte que des tarifs unitaires (0,079 sur chaque carburant), PAS les pourcentages cibles d'incorporation des IV et V de l'article 266 quindecies, qui n'existent nulle part dans le tree. Et aucun fichier de src/impots ne lit taxation_indirecte : le sous-arbre est chargé mais mort. Ce n'est donc pas un small_knob (le paramètre déplacé n'existe pas) mais bien une absence d'ins",
    ),
    Article(
        numero=17, categorie='fiscalité sectorielle et procédure fiscale',
        intitule='Mesures diverses de correction, clarification et coordination en matière de fiscalité sectorielle',
        bucket='not_priceable',
        knobs=(),
        paths=(),
        engine_ready=False, population_can_exercise=False,
        confiance='haute',
        raison="scope, avec une composante structure. L'essentiel de l'article est de la pure procédure et de la codification — conditions d'agrément et sanctions des opérateurs de détaxe, modalités de recouvrement et de contrôle des accises transférées à la DGFiP, échanges d'informations entre administrations, warrants agricoles, deux habilitations par ordonnance : ce projet ne modélise pas la procédure fiscale, et le rendement de ces mesures n'est ni un taux ni une assiette qu'une simulation microéconomique pourrait bouger. Pour la seule partie qui déplace de vrais chiffres — les tarifs de la taxe sur les installations nucléaires de base, les frais d'assiette de la taxe sur le streaming musical, la taxe pour frais de chambres — le motif est structure : ce sont trois taxes dont l'outil ne possède aucun instrument (rien dans knobs.json, rien dans FirmReformSpec, et aucun nœud correspondant dans l'arbre ",
    ),
    Article(
        numero=18, categorie='fiscalité énergie (accise électricité et combustibles)',
        intitule='Rationalisation de la fiscalité sur les énergies de chauffage',
        bucket='not_priceable',
        knobs=(),
        paths=(),
        engine_ready=False, population_can_exercise=False,
        confiance='haute',
        raison="data (raison bloquante), et accessoirement structure. Data : la population L1 est construite sur le fichier détail EEC et ne porte aucune consommation d'énergie — ni kWh d'électricité, ni MWh de gaz ou de fioul, ni puissance souscrite du compteur. L'assiette de cette mesure est donc littéralement absente : aucun ménage du fichier n'a de quantité sur laquelle appliquer 24,69 €/MWh, et le tarif réduit ≤ 36 kVA suppose de surcroît une variable de puissance de compteur qui n'existe nulle part. Structure : aucun instrument d'accise n'est calculé par la couche mécanique — la liste des variables du système ne contient aucune variable de taxation de l'électricité ou du gaz (seules apparaissent cheque_energie et ses dérivées, qui sont une prestation, pas une taxe). J'ai vérifié l'arbre openfisca : taxation_indirecte.taxes_energie_dans_logement.taxes_electricite_et_gaz existe et résout (cspe = 22,",
    ),
    Article(
        numero=19, categorie='IFER / imposition forfaitaire de production (énergie)',
        intitule="Majoration du tarif de l'IFER pour les centrales de production d'énergie électrique d'origine photovoltaïque i",
        bucket='not_priceable',
        knobs=(),
        paths=(),
        engine_ready=False, population_can_exercise=False,
        confiance='haute',
        raison="structure. Le module entreprises ne connaît que cinq instruments — IS (taux normal, taux réduit, plafonds), contribution sociale sur l'IS, C3S, CVAE, CEBGE — et la FirmReformSpec n'expose aucun autre levier. L'IFER n'est pas modélisée : ni variable, ni paramètre, ni entité redevable. Le blocage est aggravé côté données : la population firmes est une table de cellules secteur (19 sections NAF) × classe de taille portant chiffre d'affaires, valeur ajoutée, résultat courant et capital libéré — il n'existe aucune granularité d'actif de réseau, donc aucune puissance photovoltaïque installée en kW, ni aucune date de mise en service permettant d'isoler le parc antérieur au 1er janvier 2021 que la majoration vise. Même la voie détournée (traiter la majoration comme une charge déductible qui réduirait l'assiette d'IS) est refusée : il faudrait connaître la répartition des 50 M€ entre exploitants,",
    ),
    Article(
        numero=20, categorie="redevances agences de l'eau (fiscalité environnementale affectée)",
        intitule="Aménagement des redevances des agences de l'eau",
        bucket='not_priceable',
        knobs=(),
        paths=(),
        engine_ready=False, population_can_exercise=False,
        confiance='haute',
        raison="structure (raison bloquante), avec une part de scope. Structure : les redevances des agences de l'eau sont l'exemple canonique d'instrument que l'outil ne porte pas — aucune entité redevable (commune, EPCI, exploitant industriel non raccordé, agriculteur irrigant), aucune assiette (m³ prélevés, flux de pollution, volumes facturés), aucun paramètre dans l'arbre. Ce sont en outre des impositions affectées à des établissements publics de bassin, hors du périmètre budgétaire État que les couches L2-L4 chiffrent. Scope : une bonne moitié de l'article est de la pure tuyauterie juridique — désignation du redevable, arrondi de tarif, notification d'une contre-valeur au service de facturation, extension d'une référence à l'article L. 213-11-7 — c'est-à-dire de la procédure sans effet de rendement identifiable, que le projet ne modélise pas par choix. Je ne stretche pas : l'abattement d'irrigation",
    ),
    Article(
        numero=21, categorie='fiscalité déchets (TGAP, taxe emballages plastique, TVA déchets)',
        intitule='Verdissement de la fiscalité sur les déchets',
        bucket='not_priceable',
        knobs=(),
        paths=(),
        engine_ready=False, population_can_exercise=False,
        confiance='haute',
        raison="structure (raison bloquante pour les trois volets), avec du scope sur le volet TVA. Structure : (1) la TGAP déchets n'existe ni comme variable, ni comme paramètre, ni comme redevable dans l'outil — l'arbre ne contient sous taxation_indirecte.produits_energetiques qu'une tgap_carburants, sans rapport, et les cellules firmes (secteur × taille, CA/VA/résultat) ne portent aucun tonnage enfoui ou incinéré, donc l'assiette est absente autant que l'instrument ; (2) la taxe sur les emballages plastique frappe les éco-organismes et les systèmes individuels de REP — une catégorie d'entité que le modèle ne contient tout simplement pas, et son assiette (tonnage national d'emballages plastique non recyclés, ventilé par part de marché des adhérents) est une donnée de filière, pas une donnée fiscale que la population puisse porter ; (3) aucune TVA n'est calculée nulle part dans le système — le nœud tax",
    ),
    Article(
        numero=22, categorie='fiscalité douanière / importations',
        intitule="Instauration d'une taxe relative aux frais de gestion des petits colis en provenance de pays tiers",
        bucket='not_priceable',
        knobs=(),
        paths=(),
        engine_ready=False, population_can_exercise=False,
        confiance='haute',
        raison="structure. Le simulateur n'a ni entité ni instrument douanier : le redevable est le déclarant en douane, une entité qui n'existe dans aucune des deux populations (ménages OpenFisca, entreprises Ésane/IS). Vérifié : `baseline().variables` ne contient aucune variable de fiscalité indirecte ou douanière (recherche 'tva', 'tabac', 'conso' -> seulement unites_consommation, interets_prets_consommation, cheque_energie_unites_consommation), et l'arbre de paramètres 2026 ne contient aucun noeud correspondant (recherche 'colis', 'douan', 'import' -> zéro occurrence). L'assiette elle-même (775 M d'articles importés) n'est nulle part dans le projet : la population ménages ne porte aucune dépense de consommation, la population entreprises ne porte que chiffre d'affaires / valeur ajoutée / bénéfice. L'incidence sur les ménages passerait par les prix de détail, canal que ni L3 (channels.py ne réclame q",
    ),
    Article(
        numero=23, categorie='fiscalité tabac et produits à fumer (accises + taux de TVA)',
        intitule="Fiscalisation de l'ensemble des produits à fumer",
        bucket='not_priceable',
        knobs=(),
        paths=(),
        engine_ready=False, population_can_exercise=False,
        confiance='haute',
        raison="structure. Les paramètres existent mais aucun instrument ne les consomme, donc ce serait de la modélisation, pas du câblage. Vérifié avec exists_at au 2026-01-01 : taxation_indirecte.tva.taux_reduit -> True et taxation_indirecte.taxes_tabacs.taux_normal.cigarettes -> True ; en revanche `baseline().variables` ne contient AUCUNE variable de TVA ni d'accise tabac (0 résultat sur 'tva'/'tabac'), donc ces paramètres sont inertes dans ce système. Trois obstacles cumulés, chacun suffisant : (i) aucune population ne porte de consommation de tabac ou de liquides — la population ménages n'a même pas de revenu observé (KNOWN_LIMITATIONS), a fortiori pas de dépenses par produit ; (ii) l'arbre 2026 n'a aucun noeud pour les liquides de vapotage (recherche 'vapo', 'liquide', 'nicotine' -> zéro), donc le tarif nouveau n'a nulle part où s'écrire ; (iii) le volet TVA ne change aucun TAUX, il déplace des p",
    ),
    Article(
        numero=24, categorie='taxe sectorielle numérique / audiovisuel (assiette et seuils)',
        intitule="Évolution de la taxe sur les services d'accès à des contenus audiovisuels à la demande",
        bucket='not_priceable',
        knobs=(),
        paths=(),
        engine_ready=False, population_can_exercise=False,
        confiance='haute',
        raison="structure. Le module entreprises ne modélise que cinq instruments — IS, contribution sociale sur l'IS, CEBGE, CVAE, C3S (voir SCALAR_KNOBS et CEBGE_TRANCHE_PATHS dans reforms.py, et les variables de variables.py) — et aucune taxe sectorielle sur les services audiovisuels. L'arbre de paramètres 2026 ne contient rien de tel (recherche 'smad', 'audiovisuel', 'video' -> zéro occurrence). S'y ajoute un blocage de données, secondaire mais réel : l'assiette est la « contrepartie encaissée pour les services taxables », c'est-à-dire une décomposition du chiffre d'affaires par nature de service et par relation d'intermédiation ; la population entreprises est tirée de cellules Ésane secteur × taille et ne porte qu'un chiffre d'affaires agrégé, sans ventilation par service ni lien plateforme/créateur. Les deux effets principaux de l'article — le partage d'assiette entre l'intermédiaire et le fournis",
    ),
    Article(
        numero=25, categorie='TVA — seuils de franchise en base',
        intitule='Ajustement du régime de franchise en base de taxe sur la valeur ajoutée',
        bucket='not_priceable',
        knobs=(),
        paths=(),
        engine_ready=False, population_can_exercise=False,
        confiance='haute',
        raison="structure. Aucun instrument TVA n'existe dans le simulateur : `baseline().variables` ne contient aucune variable de TVA, et le balayage de l'arbre de paramètres au 2026-01-01 sur 'franchise' ne renvoie qu'un seul noeud, prelevements_sociaux.autres_taxes_participations_assises_salaires.taxsal.franchise — la franchise de la TAXE SUR LES SALAIRES, sans rapport avec l'article. Le seuil que l'article déplace n'a donc pas de chemin de paramètre : ce n'est pas du small_knob. Blocage de données redoublant le blocage de structure : les 35 000 entités concernées sont des micro-entrepreneurs et entreprises individuelles entre 25 000 € et 37 500 € de CA, or cells.py retire explicitement du champ la moitié la plus petite des micro-entreprises Ésane au motif qu'elles ne sont pas redevables de l'IS (« micro-entrepreneurs et entreprises individuelles ») — la population de ce projet est construite pour l",
    ),
    Article(
        numero=26, categorie='IS — imposition minimale mondiale (Pilier 2)',
        intitule="Précisions apportées à l'imposition minimale mondiale des grandes entreprises multinationales",
        bucket='not_priceable',
        knobs=(),
        paths=(),
        engine_ready=False, population_can_exercise=False,
        confiance='haute',
        raison="structure. Le modèle entreprises n'a aucun instrument Pilier 2 : les onze knobs firm de FirmReformSpec couvrent l'IS (taux normal, taux réduit, plafond de la tranche réduite, seuil de CA PME), la contribution sociale, la C3S, la CVAE et la CEBGE, et rien d'autre. src/impots/entreprises/margins.py dit explicitement que « la contribution sociale, la CEBGE et Pilier 2 » sont des lignes budgétaires séparées, exclues du périmètre comparé. Il n'existe ni entité « groupe multinational consolidé », ni juridiction, ni passif d'impôt différé dans la population de firmes, qui est un tableau de cellules secteur × taille tiré d'Ésane/Focus 372/DGFiP Stat 39 — donc pas de niveau de détail groupe. S'y ajoute une part purement procédurale (DAC 9, déclaration rectificative) qui relèverait de toute façon du scope. Aucune tentative de chiffrage partiel n'est possible : bouger is_taux_normal n'exprime rien ",
    ),
    Article(
        numero=27, categorie='fiscalité locale — valeurs locatives (TFPB, CFE, THRS, TEOM)',
        intitule='Ajustement de la mise en œuvre de la révision des valeurs locatives des locaux professionnels et de la révisio',
        bucket='not_priceable',
        knobs=(),
        paths=(),
        engine_ready=False, population_can_exercise=False,
        confiance='haute',
        raison="structure, avec la donnée qui verrouille la porte de secours. Le simulateur n'a aucun instrument de fiscalité locale : ni taxe foncière, ni CFE, ni taxe d'habitation sur les résidences secondaires, ni TEOM (grep sur src/ ne trouve aucune de ces bases, et aucun knob ménage ou firm ne les touche — l'IFI est la seule fiscalité du patrimoine modélisée, et elle porte sur la valeur vénale, pas sur la valeur locative cadastrale). Même si l'instrument existait, la donnée manquerait : la population ne porte ni valeurs locatives cadastrales ni patrimoine immobilier localisé, et KNOWN_LIMITATIONS acte « No capital income, no property income ». Enfin l'article agit sur des bases d'imposition d'impositions affectées aux collectivités, ce qui est en dehors du périmètre déclaré du projet.",
    ),
    Article(
        numero=28, categorie='procédure — facturation électronique (TVA)',
        intitule='Modification des obligations des assujettis en matière de facturation électronique et de transmission électron',
        bucket='not_priceable',
        knobs=(),
        paths=(),
        engine_ready=False, population_can_exercise=False,
        confiance='haute',
        raison="scope. C'est de la procédure déclarative pure et de la sanction : aucune assiette, aucun taux, aucun barème n'est modifié. Le cas est même l'exemple canonique donné dans la consigne (« obligations de facturation électronique »). Accessoirement le modèle n'a pas non plus de TVA ni d'obligation déclarative comme objet, donc il n'y a rien à bouger même à titre indicatif. Le rendement éventuel de la facturation électronique passe par un effet d'observance que ce projet ne modélise pas — il n'existe pas de canal comportemental d'observance dans src/impots/behavioural/channels.py.",
    ),
    Article(
        numero=29, categorie='procédure — gestion fiscale (avec option barème/PFU sur revenus du cap',
        intitule='Modernisation et simplification de la gestion fiscale',
        bucket='not_priceable',
        knobs=(),
        paths=(),
        engine_ready=False, population_can_exercise=False,
        confiance='haute',
        raison="data pour la seule disposition chiffrable, scope pour tout le reste. La suppression du caractère irrévocable de l'option de l'article 200 A a un coût : elle laisse des contribuables revenir sur un choix devenu défavorable, donc elle a la valeur d'une option. Le chiffrer supposerait (i) des revenus de capitaux mobiliers et des plus-values dans la population et (ii) un modèle du choix barème/PFU. Aucun des deux n'existe : KNOWN_LIMITATIONS acte « No capital income, no property income. The top of the distribution is a construction; nothing above roughly the 95th percentile is publishable », et il n'y a aucun canal d'optimisation d'option dans channels.py. Le PFU n'est de toute façon pas un knob (ir_bareme ne pilote que le barème progressif). Les autres mesures (dématérialisation, modes de notification, moyens de paiement, ordonnance, recouvrement) sont de la procédure pure, hors périmètre. ",
    ),
    Article(
        numero=30, categorie='droits de timbre et taxes sur titres',
        intitule='Diverses majorations de droits de timbre',
        bucket='not_priceable',
        knobs=(),
        paths=(),
        engine_ready=False, population_can_exercise=False,
        confiance='haute',
        raison="structure. Aucun droit de timbre n'existe dans le modèle — ni taxe de séjour, ni droit de naturalisation, ni taxe sur le permis de conduire, ni contribution pour l'aide juridique — au même titre que le tabac, les redevances des agences de l'eau ou les taxes sur les véhicules cités comme exemples de refus structurel. Les assiettes sont d'ailleurs des ÉVÉNEMENTS administratifs (une demande de titre, une instance introduite) et non des grandeurs portées par la population : celle-ci ne contient ni statut de séjour, ni recours contentieux, ni échange de permis. Il n'y a donc rien à câbler à la semaine de publication ; ce serait un instrument nouveau à construire de bout en bout, avec sa propre source de comptage administratif.",
    ),)


def priceable_today() -> tuple[Article, ...]:
    """The articles that would produce a number worth publishing. The honest headline."""
    return tuple(a for a in ARTICLES
                 if a.bucket == "priceable_now" and a.population_can_exercise)


def engine_ready_but_blind() -> tuple[Article, ...]:
    """Parameters in the tree, no taxpayer in the population to exercise them.

    The most dangerous category, because wiring one of these produces a confident zero
    rather than an error — which is why it is a category rather than a footnote.
    """
    return tuple(a for a in ARTICLES
                 if a.engine_ready and not a.population_can_exercise)


def share_priceable() -> float:
    return len(priceable_today()) / len(ARTICLES)

# --------------------------------------------------------------------------- #
# The second headline: yield, not article count
# --------------------------------------------------------------------------- #

#: First-year (2026) budgetary impact per article, in MILLIONS of euros, magnitude only —
#: read by hand from section 4.2.1 of each fiche in the manifested évaluations préalables
#: (sha256 9f53516f8139). Sign is not carried here because the headline is a share of
#: EFFORT quantified, not a net balance.
#:
#: READ BY HAND, AND THE REASON IS A NEAR-MISS. Section 4.2.1 has no single shape: a
#: five-column table, a thirteen-column chronicle (art. 11), or a plain sentence
#: (art. 4: «un gain pour l'État de 4 Md€ en 2026»). A table-shaped extractor returned
#: "PAS DE TABLE" for article 4 — which is the LARGEST quantified figure in the annex and
#: the only article this tool can price. An automated count would have reported the
#: yield-weighted coverage as zero.
#:
#: AND THE UNIT IS DECLARED PER FICHE, NOT PER DOCUMENT: articles 5 and 6 are in
#: MILLIARDS, everything else in MILLIONS. Getting that wrong is a factor of a thousand.
YIELDS_2026_MEUR: dict[int, float] = {
    4: 4_000.0,    # «un gain pour l'État de 4 Md€ en 2026»
    5: 1_640.0,    # tableau « en milliards », colonne 2026 : 1,64
    6: 1_200.0,    # «un gain budgétaire estimé à 1,2 Md€ en 2026»
    11: 1_100.0,   # «le coût pour l'État est de l'ordre d'1,1 Md€ en 2026»
    25: 520.0,     # «le coût en TVA est estimé en année pleine à 520 M€»
    15: 88.0,      # «un gain de 88 M€ pour Île-de-France Mobilités»
    19: 50.0,      # tableau, État 50
    20: 31.0,      # tableau, État +31 M€
    9: 0.0,        # «un coût pour l'État de 30 M€ à compter de 2027» — donc 0 en 2026
    14: 0.0,       # tableau, 0 partout
    24: 0.0,       # «sans incidence budgétaire»
}

#: Articles whose published figure cannot be pinned to one number, and why. Kept OUT of
#: the headline's denominator rather than guessed — banded or absent, never confidently
#: wrong.
YIELD_AMBIGUOUS: dict[int, str] = {
    2: ("en-tête « en millions d'euros », cellule « 1,5 », note de méthode « l'estimation "
        "prévisionnelle a été revue à 1,5 Md€ ». Le facteur mille n'est pas déterminable "
        "depuis le document : soit 1,5 M€, soit 1 500 M€. Même piège que l'en-tête « (M€) » "
        "sur des cellules en euros de DGFiP n° 45."),
    22: ("le tableau donne un total APU de 24 M€ en 2026 et 120 M€ pérennes, la prose du "
         "même 4.2.1 annonce « un gain annuel pour l'État de 600 M€ à compter de 2026 ». "
         "Les deux ne se recouvrent pas et le document ne dit pas lequel recouvre l'autre "
         "— frais de gestion contre droits recouvrés, vraisemblablement, mais « "
         "vraisemblablement » n'est pas une lecture."),
    8: "« incidence non chiffrable » — l'annexe le dit elle-même",
    10: "« coût non chiffrable pour l'État à compter de 2026, et supérieur à 200 M€ en 2027 »",
    27: "« impact non chiffrable pour l'État »",
    16: "« n'a pas pour objet de générer un rendement significatif »",
    18: "la fiche renvoie à l'évaluation préalable d'un autre PLF ; pas de montant propre",
}

#: The 11 fiscal articles with no évaluation préalable at all. Not an omission by the
#: government: the obligation is organic and does not cover provisions in the exclusive
#: domain of finance laws.
NO_FICHE: tuple[int, ...] = (3, 7, 12, 13, 17, 21, 23, 26, 28, 29, 30)


def quantified_yield_meur() -> float:
    """Total first-year impact the annex actually quantifies, in M EUR."""
    return sum(YIELDS_2026_MEUR.values())


def priceable_yield_meur() -> float:
    """…of which this tool can price today."""
    priced = {a.numero for a in priceable_today()}
    return sum(v for n, v in YIELDS_2026_MEUR.items() if n in priced)


def share_of_yield() -> float:
    """THE SECOND HEADLINE, and it says the opposite of the first.

    By article count the tool covers 3,4 %. By quantified first-year yield it covers far
    more, because the single article it can price — the CEBGE — is the largest quantified
    figure in the whole annex at 4 Md EUR. Counting articles weights a droit de timbre
    equally with a four-billion contribution; counting euros does not.
    """
    total = quantified_yield_meur()
    return priceable_yield_meur() / total if total else 0.0


# --------------------------------------------------------------------------- #
# Le PLF 2027 réel — triage du jour de parution
# --------------------------------------------------------------------------- #
SOURCE_2027 = (
    "Assemblée nationale, texte n° 3210 (17e législature), projet de loi de finances "
    "pour 2027, déposé le 1er octobre 2026, articles avec exposé des motifs. Manifesté : "
    "plf2027_texte_an_b3210.html, sha256 7fcd191974d8. La section fiscale porte les "
    "articles 1 à 33."
)

#: Le jour de ce triage. Le runbook exige de dater une décision prise sur le texte publié,
#: parce que c'est la seule différence visible entre un refus préenregistré — une limite —
#: et un refus improvisé — une excuse.
DATE_TRIAGE_2027 = "2026-10-02"


@dataclass(frozen=True)
class Article2027:
    """Un article fiscal du PLF 2027, rattaché à une catégorie et à une case.

    `decision` vaut « septembre » quand la catégorie existait dans le triage préenregistré
    (et un test vérifie qu'elle y figure à la lettre), « neuve » quand elle a été prise le
    jour de parution.
    """

    numero: int
    intitule: str
    categorie: str
    bucket: str
    decision: str
    raison: str
    knobs: tuple[str, ...] = ()
    chaine: str = "ménages"
    reforme: str = ""


_CAT = {a.numero: a.categorie for a in ARTICLES}

ARTICLES_2027: tuple[Article2027, ...] = (
    Article2027(
        1, "Autorisation de percevoir les impôts existants",
        "formalité annuelle (autorisation de percevoir)", "not_priceable", "neuve",
        "scope. Formalité reconduite chaque année, pas une mesure ; le triage de septembre "
        "l'écartait déjà comme telle sans lui donner de ligne."),
    Article2027(
        2, "Soutenir le travail en revalorisant le barème de l'impôt sur le revenu grâce à "
           "un traitement fiscal équivalent des différents types de revenus",
        "IR — revalorisation du barème", "priceable_now", "neuve",
        "Le volet revalorisation — 2,1 % sur les tranches, la décote et le plafond général "
        "de la demi-part — s'écrit avec quatre boutons existants, contre un arbre qui gèle "
        "en 2026 les paramètres des revenus 2025 : il n'y a donc pas de zéro confiant à "
        "craindre. Ne sont PAS chiffrés : les quatre autres plafonds de quotient familial, "
        "le 196 B et l'indexation des limites de déductions (structure : aucun bouton), ni "
        "les volets indemnités de rupture, indemnités journalières ALD et AT/MP, prime "
        "carburant et taux de CSG des IJ (data : la population n'a ni indemnité de rupture "
        "ni IJ). À comparer au seul volet revalorisation si l'annexe le sépare.",
        knobs=("ir_bareme", "decote_seuil_celib", "decote_seuil_couple",
               "plafond_qf_demi_part"),
        reforme="reforms/plf2027_art_2.json"),
    Article2027(
        3, "Réduction à 3 000 € du plafond de l'abattement d'impôt sur le revenu en faveur "
           "des bénéficiaires de pensions de retraite",
        _CAT[6], "priceable_now", "septembre",
        "Petit bouton en septembre, câblé le 2026-10-02 (abattement_pensions_plafond, "
        "chemin abatpen.max) et vu bouger sur un retraité. Le sous-plafond de l'article ne "
        "vise que les pensions de retraite ; le bouton déplace le plafond commun, ce qui est "
        "exact sur cette population, dont la seule pension est une retraite.",
        knobs=("abattement_pensions_plafond",), reforme="reforms/plf2027_art_3.json"),
    Article2027(
        4, "Mesure temporaire d'allègement de la fiscalité des donations pour encourager "
           "les transmissions intergénérationnelles",
        "DMTG — donations", "not_priceable", "neuve",
        "structure. Aucun modèle de transmission : ni donation, ni patrimoine transmis, ni "
        "barème des droits de mutation ; F7 est une porte qu'on ne franchit pas sans le "
        "propriétaire."),
    Article2027(
        5, "Recentrage du dispositif de l'apport-cession sur son objectif de soutien à "
           "l'investissement",
        "plus-values en report d'imposition (apport-cession)", "not_priceable", "neuve",
        "data. Aucune plus-value ni aucun report d'imposition dans la population."),
    Article2027(
        6, "Protection du modèle de l'assurance-vie",
        "fiscalité de l'assurance-vie", "not_priceable", "neuve",
        "data. Aucun revenu de l'épargne dans la population."),
    Article2027(
        7, "Réorienter les soutiens publics vers le logement familial et de longue durée",
        "logement — prêt à taux zéro et location meublée", "not_priceable", "neuve",
        "data. Ni prêt à taux zéro, ni revenu locatif meublé ou nu dans la population."),
    Article2027(
        8, "Soutien au logement social",
        _CAT[27], "not_priceable", "septembre",
        "structure. Exonérations de taxe foncière et d'IS des organismes HLM : ni bailleur "
        "social ni taxe foncière par logement dans le modèle."),
    Article2027(
        9, "Soutien à l'industrie",
        "IS — suramortissements et incitations à l'investissement", "not_priceable",
        "neuve",
        "structure. Le modèle entreprises n'a ni investissement ni amortissement : un "
        "suramortissement n'a pas d'assiette."),
    Article2027(
        10, "Soutien aux reprises d'entreprises (pacte « Papin »)",
        "transmission et reprise d'entreprises", "not_priceable", "neuve",
        "structure. Ni transmission ni reprise d'entreprise dans le modèle."),
    Article2027(
        11, "Prorogation d'un an de l'application du crédit d'impôt pour la compétitivité "
            "et l'emploi à Mayotte",
        "crédits d'impôt territoriaux (outre-mer)", "not_priceable", "neuve",
        "data. Ni Mayotte ni masse salariale par territoire dans la population "
        "d'entreprises."),
    Article2027(
        12, "Soutien au secteur culturel",
        _CAT[24], "not_priceable", "septembre",
        "structure. Crédits d'impôt sectoriels — l'IS de ce modèle est un IS avant "
        "créances — et taxe sur la publicité des plateformes vidéo : aucune assiette."),
    Article2027(
        13, "Soutien au secteur agricole",
        _CAT[10], "not_priceable", "septembre",
        "data. Aucun bénéfice agricole dans la population, comme en septembre."),
    Article2027(
        14, "Soutien aux entreprises touchées par les incendies de l'été 2026",
        "soutien conjoncturel après sinistre", "not_priceable", "neuve",
        "data. Ni localisation départementale des entreprises ni sinistre."),
    Article2027(
        15, "Mise à contribution des grandes entreprises",
        _CAT[4], "priceable_now", "septembre",
        "Chiffrable dès septembre, mais le jour J a montré deux trous, comblés le "
        "2026-10-02 : l'arbre éteint la CEBGE après 2026 et le curseur refuse, à raison, "
        "d'écrire une année éteinte (prorogation par création délibérée, largeur de lissage "
        "prise dans le texte) ; et le registre n'enregistrait que des scénarios ménages "
        "(`chiffrage register-entreprises`). Le volet transport maritime (II) n'est pas "
        "chiffré : aucune entreprise de transport maritime n'est identifiable sous la "
        "section NAF.",
        knobs=("cebge_seuils_et_taux", "cebge_prorogation_largeur"),
        chaine="entreprises", reforme="reforms/plf2027_art_15.json"),
    Article2027(
        16, "Rationalisation des taux de taxe sur la valeur ajoutée applicables aux "
            "services de télévision",
        "TVA — taux applicables à des services", "not_priceable", "neuve",
        "structure. Pas de TVA par taux : F8 attend le budget de famille."),
    Article2027(
        17, "Ajustements sur les taxes sur les réductions de capital",
        "taxe sur les réductions de capital", "not_priceable", "neuve",
        "structure. Ni rachat ni annulation de titres dans le modèle."),
    Article2027(
        18, "Aménagement du régime des provisions assurantielles",
        "IS — provisions des entreprises d'assurance", "not_priceable", "neuve",
        "structure. Aucune provision dans le modèle entreprises."),
    Article2027(
        19, "Mesures diverses de correction, clarification et coordination en matière de "
            "fiscalité sur les biens et services",
        _CAT[17], "not_priceable", "septembre",
        "structure. Ajustements de fiscalité indirecte, hors du modèle."),
    Article2027(
        20, "Création de tarifs réduits de taxes sur les installations nucléaires de base "
            "applicables pendant la phase de construction",
        _CAT[19], "not_priceable", "septembre",
        "structure. Aucune installation de production d'énergie dans le modèle."),
    Article2027(
        21, "Adaptation de la fiscalité aérienne au soutien à la continuité territoriale",
        "fiscalité du transport aérien", "not_priceable", "neuve",
        "structure. Ni vol ni passager dans le modèle."),
    Article2027(
        22, "Renforcement de la taxe sur l'exploitation des infrastructures de transport de "
            "longue distance pour les exploitants les plus rentables",
        "taxe sur les infrastructures de transport de longue distance", "not_priceable",
        "neuve",
        "structure. Aucun exploitant d'infrastructure identifiable dans la population "
        "d'entreprises."),
    Article2027(
        23, "Instauration d'un prélèvement exceptionnel sur les avoirs en déshérence "
            "déposés auprès de la Caisse des dépôts et consignations",
        "prélèvement sur avoirs en déshérence", "not_priceable", "neuve",
        "structure. Ni avoir bancaire ni Caisse des dépôts dans le modèle. L'article que le "
        "découpeur écartait sans bruit avant le 2026-10-02."),
    Article2027(
        24, "Soutien à l'électrification et renforcement des incitations environnementales "
            "dans le secteur des transports",
        _CAT[16], "not_priceable", "septembre",
        "structure. Fiscalité des carburants, hors du modèle."),
    Article2027(
        25, "Mesures relatives à la fiscalité des véhicules",
        _CAT[13], "not_priceable", "septembre",
        "structure. Aucun véhicule dans le modèle."),
    Article2027(
        26, "Prorogations d'exonérations et précisions en matière de fiscalité locale",
        _CAT[12], "not_priceable", "septembre",
        "structure. Régimes zonés, sans localisation fine dans le modèle."),
    Article2027(
        27, "Mesures relatives au financement du service public de la justice",
        _CAT[30], "not_priceable", "septembre",
        "structure. Droits et taxes affectés à l'aide juridictionnelle, hors du modèle."),
    Article2027(
        28, "Mise à jour de références au droit de l'Union européenne dans des dispositifs "
            "fiscaux",
        _CAT[17], "not_priceable", "septembre",
        "scope. Mise en conformité juridique, sans paramètre chiffrable."),
    Article2027(
        29, "Nouvelle étape de la relation de confiance",
        _CAT[29], "not_priceable", "septembre",
        "scope. Procédure."),
    Article2027(
        30, "Renforcement de la lutte contre la fraude fiscale et mesures "
            "anti-contournement",
        _CAT[29], "not_priceable", "septembre",
        "scope. Procédure et contrôle ; un rendement de lutte contre la fraude ne se "
        "simule pas sur des contribuables qui déclarent tout."),
    Article2027(
        31, "Modernisation et simplification des procédures fiscales",
        _CAT[29], "not_priceable", "septembre",
        "scope. Procédure."),
    Article2027(
        32, "Sécurisation et amélioration de la lisibilité de dispositifs fiscaux mis en "
            "œuvre par la douane",
        _CAT[22], "not_priceable", "septembre",
        "structure. Accises et détaxe, hors du modèle."),
    Article2027(
        33, "Modalités d'entrée en vigueur des mesures fiscales",
        "formalité annuelle (entrée en vigueur)", "not_priceable", "neuve",
        "scope. Fixe les dates : le 31 décembre 2026 pour l'IR et l'IS, ce qui place les "
        "mesures d'IR sur les revenus 2026 et le troisième exercice de la CEBGE en 2027."),
)


def priceable_2027() -> tuple[Article2027, ...]:
    return tuple(a for a in ARTICLES_2027 if a.bucket == "priceable_now")


# --------------------------------------------------------------------------- #
# Le PLF 2027 en euros — la part de l'annexe que l'outil chiffre (D-293, D-294)
# --------------------------------------------------------------------------- #
#: L'annexe lue, par son identifiant : le PDF reste hors du dépôt, le manifeste porte son
#: sha256 (D-204).
SOURCE_ANNEXE_2027 = (
    "PLF 2027, évaluations préalables des articles (743 p.), annexe au projet de loi "
    "n° 3210. Manifesté : plf2027_evaluations_prealables.pdf, sha256 b1142977a5e3. La "
    "page citée est celle du PDF, qui est la page imprimée."
)


@dataclass(frozen=True)
class Montant2027:
    """Une ligne du relevé : l'effet de 2027 qu'une fiche publie pour un volet.

    La règle est celle de D-293, écrite avant la lecture. `meur` est la valeur absolue en
    millions d'euros, ou None quand la ligne sort du dénominateur, et `raison` dit alors
    pourquoi. `ecrit_meur` garde le montant qu'une ligne sortie écrit quand même (un
    majorant, un montant sans année), pour dire de combien il bougerait la part. `chiffre`
    marque les volets que l'outil chiffre : le numérateur.
    """

    article: int
    volet: str
    meur: float | None
    page: int
    citation: str
    raison: str = ""
    ecrit_meur: float | None = None
    chiffre: bool = False

    def __post_init__(self) -> None:
        where = f"art. {self.article}, volet « {self.volet} »"
        if self.page < 1:
            raise ValueError(f"{where} : une page de l'annexe commence à 1.")
        if self.meur is None and not self.raison:
            raise ValueError(f"{where} : une ligne hors du dénominateur dit sa raison.")
        if self.meur is not None and self.meur < 0:
            raise ValueError(f"{where} : le relevé porte une valeur absolue, pas un signe.")
        if self.meur is not None and self.ecrit_meur is not None:
            raise ValueError(f"{where} : seul un montant hors du dénominateur garde un "
                             f"montant écrit à part.")
        if self.chiffre and self.meur is None:
            raise ValueError(f"{where} : un volet que l'outil chiffre est au numérateur, "
                             f"donc au dénominateur.")


#: Les articles fiscaux de 2027 sans fiche dans l'annexe (règle 7).
SANS_FICHE_2027: tuple[int, ...] = (1,)

_M = Montant2027
_NON_CHIFFRABLE = "« non chiffrable » : l'annexe le dit elle-même (règle 5)"
_UN_SEUL_COTE = "un montant donné par un seul côté (règle 6)"
_SANS_ANNEE = "aucune année : année indéterminable (règle 5)"

#: Le relevé, fiche par fiche, à la main : la section 4.2.1 n'a pas de forme unique (prose,
#: tableau par administration, chronique, sous-sections par volet), et l'unité se lit dans
#: chaque phrase. Les volets « Aucune », « Sans objet », « Sans incidence » ou « neutre »
#: valent zéro (règle 5).
MONTANTS_2027: tuple[Montant2027, ...] = (
    _M(2, "4.2.1.1", 4_200.0, 29,
       "le rendement de l’IR aurait été majoré d’environ 4,2 Md€ en 2027",
       chiffre=True),
    _M(2, "4.2.1.2", None, 29,
       "La mesure présente un coût majorant pour l’État de 20 M€ en 2027",
       raison=f"un majorant : {_UN_SEUL_COTE}", ecrit_meur=20.0),
    _M(2, "4.2.1.3", 820.0, 29, "La mesure présente un gain total de 820 M€ en 2027"),
    # Les 965 M€ de 2027 en leurs deux parts, que donne la même phrase (D-306).
    _M(2, "4.2.1.4 (IR ALD)", 450.0, 30, "dont 450 M€ au titre des ALD",
       raison="l'effet de 2027 avec le PAS, que la fiche donne, et non les 290 M€ de "
              "l'année pleine",
       chiffre=True),
    _M(2, "4.2.1.4 (IR AT-MP)", 515.0, 30, "515 M€ au titre des AT/MP",
       raison="l'effet de 2027 avec le PAS, que la fiche donne, et non les 330 M€ de "
              "l'année pleine",
       chiffre=True),
    _M(2, "4.2.1.4 (CSG)", 540.0, 30,
       "générerait de l’ordre de 540 M€ de recettes supplémentaires pour les "
       "administrations de sécurité sociale pour 2027",
       chiffre=True),
    _M(3, "", 1_400.0, 36, "Cette mesure entraîne un gain budgétaire estimé à 1,4 Md€ en 2027",
       chiffre=True),
    _M(4, "", None, 41, "La mesure présente pour l’État un coût non chiffrable en 2027.",
       raison=_NON_CHIFFRABLE),
    _M(5, "", 500.0, 46,
       "On estime le rendement budgétaire pour la première année d’impact, en 2027, à "
       "500 M€"),
    _M(6, "", 25.0, 53, "Total pour l’ensemble des APU +25 +50 +50"),
    _M(7, "4.2.1.1 (plafond)", 0.0, 62,
       "La mesure de suppression du plafond annuel de dépense fiscale n’emporte pas, à elle "
       "seule, de surcoût budgétaire immédiat",
       raison="aucun surcoût immédiat"),
    _M(7, "4.2.1.1 (PTZ parentalité)", 0.0, 62,
       "La mesure de création d’un PTZ « parentalité » devrait avoir un coût générationnel "
       "de 466 M€",
       raison="premier effet en 2028 : une génération de prêts coûte à partir de l'année "
              "qui suit son émission (« année n+1 » ; la génération 2025 du § 4.3 ne coûte "
              "rien en 2025), et la première génération est celle de 2027, la mesure "
              "entrant en vigueur avec la loi de finances pour 2027 (§ 6.3)"),
    _M(7, "4.2.1.2", 260.0, 62,
       "Le gain attendu en impôt sur le revenu est évalué à 260 M€ en 2027"),
    _M(8, "4.2.1.1", 0.0, 72, "L’impact budgétaire de la mesure débutera en 2043",
       raison="premier effet en 2043 (règle 2)"),
    _M(8, "4.2.1.2", None, 73, "L’impact budgétaire de la mesure n’est pas chiffrable.",
       raison=_NON_CHIFFRABLE),
    _M(9, "suramortissement « industrie 4.0 »", 0.0, 89, "0 M€ en 2027 et 6,7 M€ en 2028"),
    _M(9, "C3IV", 0.0, 89, "décaissements limités à 0 M€ en 2027 et 6 M€ en 2028"),
    _M(10, "", 67.0, 102, "Total pour l’ensemble des APU -67 -73 -74 -76"),
    _M(11, "", 0.0, 107, "Le coût budgétaire de la mesure est nul en 2027"),
    _M(12, "4.2.1.1", 0.0, 122,
       "La chronique de coût de cette mesure (prorogation triennale de 6 dépenses "
       "fiscales) est la suivante",
       raison="la chronique commence en 2028 : premier effet après 2027 (règle 2)"),
    _M(12, "4.2.1.2", None, 122, "Ce chiffrage peut dès lors être perçu comme minorant.",
       raison=f"un minorant, les 35 M€ du tableau de 2027 : {_UN_SEUL_COTE}",
       ecrit_meur=35.0),
    _M(13, "4.2.1.1", 33.0, 140, "Le rendement de la mesure est évalué à 33 M€ en 2027."),
    _M(13, "4.2.1.2", 0.0, 140, "Total pour l’ensemble des APU 0 -4.7 -11"),
    _M(13, "4.2.1.3", 1.0, 141, "entraîne un coût annuel pour l’État de 1 M€ en 2027"),
    _M(13, "4.2.1.4", 0.0, 141, "entraîne un coût annuel pour l’État de 13 M€ en 2028",
       raison="premier effet en 2028 (règle 2)"),
    _M(13, "4.2.1.5", 0.1, 141,
       "entraîne un coût pour l’État annuel de 0,1 M€ à partir de 2027"),
    _M(14, "TSCA", 200.0, 152,
       "La hausse du taux de TSCA de 18 % à 18,9 % est estimée à +200 M€ pour l’État.",
       raison="le tableau la place en 2027"),
    _M(14, "taxe foncière", None, 152, "il s’agit d’un coût non chiffrable",
       raison=_NON_CHIFFRABLE),
    _M(14, "CFE", 0.0, 152,
       "Concernant la CFE, le coût budgétaire est estimé en ordre de grandeur à 21 M€.",
       raison="le tableau le place en 2026 : rien en 2027"),
    _M(15, "I", 5_000.0, 160, "5 Md€ au titre des acomptes attendus en 2027",
       chiffre=True),
    _M(15, "II", None, 160,
       "entreprises de transport maritime est de 0,3 Md€",
       raison=_SANS_ANNEE, ecrit_meur=300.0),
    _M(16, "", 304.0, 165, "Total pour l’ensemble des APU 304 333 333 +335"),
    _M(17, "", None, 171, "L’impact budgétaire de la mesure n’est pas chiffrable.",
       raison=_NON_CHIFFRABLE),
    _M(18, "", None, 179, "La mesure présente une incidence non chiffrable.",
       raison=_NON_CHIFFRABLE),
    _M(19, "", 31.0, 195,
       "La prorogation de la dépense fiscale n° 800119 engendre un coût de 31 M€ à compter "
       "de 2027."),
    _M(20, "", None, 202,
       "est estimé, au maximum, à 37 M€ au titre de l’année 2026 et à 39,5 M€ au titre de "
       "l’année 2027",
       raison=f"un maximum : {_UN_SEUL_COTE}", ecrit_meur=39.5),
    _M(21, "sûreté des aérodromes", None, 217,
       "induisent un rendement supplémentaire maximal d’environ 53 M€",
       raison=f"un maximum, sans année : {_UN_SEUL_COTE}", ecrit_meur=53.0),
    _M(21, "Strasbourg-Entzheim", 3.8, 217,
       "le coût prévisionnel annuel est estimé à 3,8 M€",
       raison="un coût annuel : l'année pleine vaut pour 2027 (règle 2)"),
    _M(22, "", 800.0, 222,
       "La mesure entraîne une augmentation estimée du produit annuel de la TEITLD de "
       "800 M€",
       raison="le tableau la place en 2027"),
    _M(23, "", 1_400.0, 229, "Le montant prévisionnel du gain est d’1,4 Md€ pour 2027."),
    _M(24, "4.2.1.1", None, 255,
       "Prorogation de la taxe incitative relative à l’utilisation d’énergie renouvelable "
       "dans les transports Mesure non chiffrable.",
       raison=_NON_CHIFFRABLE),
    _M(24, "4.2.1.2", 0.3, 255, "État -0,3 -0,3 -0,3"),
    _M(24, "4.2.1.3", 16.0, 256, "État -16 -25 -40"),
    _M(24, "4.2.1.4", 0.0, 256,
       "génère des revenus de l’ordre de 200 M€ sur 2030",
       raison="premier effet en 2030 (règle 2)"),
    _M(25, "4.2.1.1", None, 272, "Un gain non chiffrable peut être retenu sur cette mesure.",
       raison=_NON_CHIFFRABLE),
    _M(25, "4.2.1.2", None, 272, "elle ne peut-être chiffrée", raison=_NON_CHIFFRABLE),
    _M(25, "4.2.1.3", 22.0, 272,
       "Le coût annuel de la mesure afférente au malus masse est évalué à 22 M€ à compter "
       "de 2027."),
    _M(26, "4.2.1.1 (État)", None, 290, "Ce risque indemnitaire est difficilement chiffrable",
       raison=_NON_CHIFFRABLE),
    _M(26, "4.2.1.1 (communes)", 0.0, 290, "la mesure est neutre financièrement"),
    _M(26, "4.2.1.2 (BUD et ZDP)", 0.0, 290,
       "le coût pour l’État est estimé à moins de 2 M€ répartis entre 2028 et 2037",
       raison="premier effet en 2028 (règle 2)"),
    _M(26, "4.2.1.2 (ZRCV)", None, 290,
       "le coût pour les collectivités n’est pas connu",
       raison="« pas connu » : non chiffrable (règle 5)"),
    _M(26, "4.2.1.3", 0.0, 290,
       "Elle est donc sans incidence (SI) sur les recettes fiscales."),
    _M(27, "", 35.4, 302, "Total pour l’ensemble des APU +35,4 +85,15 +85,15 +205,7"),
    _M(28, "4.2.1.1", None, 319, "La mesure présente un gain non chiffrable (majorant 32 M€).",
       raison=_NON_CHIFFRABLE, ecrit_meur=32.0),
    _M(28, "4.2.1.2", 0.0, 319,
       "Sur la définition du champ du régime d’imposition des crypto-actifs Aucune."),
    _M(28, "4.2.1.3", None, 319,
       "La mesure présente un coût non chiffrable à compter de 2027 pour l’État",
       raison=_NON_CHIFFRABLE),
    _M(28, "4.2.1.4", 0.0, 319,
       "exploitées selon le mode de production biologique Aucune."),
    _M(29, "", 0.0, 324,
       "Incidences budgétaires (coûts/économies nets de la mesure proposée) Sans "
       "incidence."),
    _M(30, "", None, 351, "Les mesures présentent une incidence non chiffrable.",
       raison=_NON_CHIFFRABLE),
    _M(31, "4.2.1.1", None, 363,
       "La perte budgétaire en retenue à la source (RAS) sera négligeable (inférieure à "
       "0,3 M€) à compter de 2027.",
       raison=f"« inférieure à » : {_UN_SEUL_COTE}", ecrit_meur=0.3),
    _M(31, "4.2.1.2", 0.0, 363,
       "Remise des fichiers des écritures comptables et des résultats des traitements "
       "informatiques Sans objet."),
    _M(31, "4.2.1.3", None, 363, "permet à terme d’envisager une économie de 1 M€",
       raison="« à terme » : année indéterminable (règle 5)", ecrit_meur=1.0),
    _M(31, "4.2.1.4", None, 364,
       "Économie estimée pour 3 294 892 avis de 6 pages : 2 391 762 €.",
       raison=_SANS_ANNEE, ecrit_meur=2.391762),
    _M(32, "", 0.0, 376,
       "Incidences budgétaires (coûts/économies nets de la mesure proposée) Sans objet."),
    _M(33, "", 0.0, 382,
       "Incidences budgétaires (coûts/économies nets de la mesure proposée) Sans objet."),
)


def montants_2027(numero: int) -> tuple[Montant2027, ...]:
    return tuple(m for m in MONTANTS_2027 if m.article == numero)


def yield_2027_meur(numero: int) -> float | None:
    """L'effort de 2027 d'un article, ou None quand aucune de ses lignes n'entre."""
    inside = [m.meur for m in montants_2027(numero) if m.meur is not None]
    return sum(inside) if inside else None


def articles_hors_denominateur_2027() -> tuple[int, ...]:
    """Les articles dont rien n'entre au dénominateur : sans fiche, ou toutes leurs lignes
    sorties."""
    read = sorted({m.article for m in MONTANTS_2027})
    return tuple(sorted(set(SANS_FICHE_2027)
                        | {n for n in read if yield_2027_meur(n) is None}))


def quantified_yield_2027_meur() -> float:
    """L'effort de 2027 que l'annexe quantifie, en M€ : le dénominateur."""
    return sum(m.meur for m in MONTANTS_2027 if m.meur is not None)


def priced_yield_2027_meur() -> float:
    """…dont les volets que l'outil chiffre : le numérateur."""
    return sum(m.meur for m in MONTANTS_2027 if m.chiffre)


def share_of_yield_2027() -> float:
    total = quantified_yield_2027_meur()
    return priced_yield_2027_meur() / total if total else 0.0


def share_of_yield_2027_si_ecrits() -> float:
    """La part si chaque montant écrit d'une ligne sortie entrait au dénominateur : elle ne
    peut que baisser, puisqu'aucune de ces lignes n'est un volet chiffré."""
    written = sum(m.ecrit_meur for m in MONTANTS_2027 if m.ecrit_meur is not None)
    return priced_yield_2027_meur() / (quantified_yield_2027_meur() + written)


def volets_non_chiffres_2027() -> tuple[Montant2027, ...]:
    """Les volets quantifiés des articles chiffrés que l'outil ne chiffre pas."""
    priced = {a.numero for a in priceable_2027()}
    return tuple(m for m in MONTANTS_2027
                 if m.article in priced and m.meur is not None and not m.chiffre)


@dataclass(frozen=True)
class RefusMesure:
    """Un volet que le but 8 a regardé et qui reste refusé, avec sa mesure (D-305).

    `porte` dit ce que la population porte désormais de l'assiette, ou ce que les données
    ouvertes en disent ; `manque`, ce qui manque pour chiffrer. Les raisons du triage
    restent ce qu'elles étaient à leur date : celle-ci les complète, elle ne les réécrit pas.
    """

    article: int
    volet: str
    porte: str
    manque: str


REFUS_MESURES_2027: tuple[RefusMesure, ...] = (
    RefusMesure(
        2, "4.2.1.3",
        "Aucune indemnité de rupture. La fiche cite le rapport IGF-IGAS d'octobre 2025 : "
        "40 000 personnes au-dessus d'un PASS, soit 0,2 % des salariés du privé de la "
        "population, une queue qu'une clé par cellule étalerait sur tous.",
        "une distribution ouverte des indemnités de rupture ; imputer depuis les comptes "
        "de la fiche noterait la fiche contre elle-même."),
    RefusMesure(
        5, "",
        "La case 8UT porte le stock des plus-values en report : 173,27 Md€ chez 117 112 "
        "foyers en 2024. À 31,4 % de prélèvements, les 500 M€ de la fiche supposent "
        "1,59 Md€ transmis par an, 0,92 % du stock.",
        "l'âge des détenteurs, qui fixe la part transmise par donation ou décès : aucune "
        "source ouverte ne ventile la case 8UT par âge."),
    RefusMesure(
        6, "",
        "Les cases 2CH, 2DH, 2VV et 2WW portent les produits de l'assurance-vie : "
        "1,947 Md€ chez 1 113 493 foyers pour la seule 2CH en 2024.",
        "l'assureur étranger et la transmission au décès, qu'aucune case ne distingue ; "
        "les 100 Md€ d'encours de la fiche n'ont pas d'équivalent ouvert."),
    RefusMesure(
        7, "4.2.1.2",
        "Les cases 5ND et 5OD portent les recettes du meublé non professionnel au micro : "
        "5,045 Md€ chez 619 711 foyers pour la 5ND en 2024.",
        "les amortissements que la réforme réintègre à la cession : ils sont dans les "
        "liasses du réel, que la fiche apparie, et dans aucune donnée publique."),
)


#: Les volets chiffrés par un cas écrit après l'annexe : des révisions au sens de D-292,
#: comptées à part des cas aveugles (D-306). Chacun nomme ses cas.
CHIFFRES_APRES_ANNEXE_2027: dict[tuple[int, str], tuple[str, ...]] = {
    # Depuis D-312 : la part ALD des IJ, 33 % des jours d'après l'annexe 9 du PLFSS 2026.
    (2, "4.2.1.4 (IR ALD)"): ("plf2027_art_2_ij_ald",),
    (2, "4.2.1.4 (IR AT-MP)"): ("plf2027_art_2_ij_atmp",),
    (2, "4.2.1.4 (CSG)"): ("plf2027_art_2_csg_ij",),
}


def chiffres_apres_annexe_2027() -> tuple[tuple[Montant2027, tuple[str, ...]], ...]:
    """Chaque volet chiffré après l'annexe avec sa ligne du relevé ; refusé s'il n'en a
    pas, ou si la ligne n'est pas au numérateur."""
    lines = {(m.article, m.volet): m for m in MONTANTS_2027}
    out = []
    for key, cases in CHIFFRES_APRES_ANNEXE_2027.items():
        line = lines.get(key)
        if line is None or not line.chiffre or not cases:
            raise ValueError(f"art. {key[0]}, volet « {key[1]} » : un volet chiffré après "
                             f"l'annexe nomme une ligne du numérateur, et ses cas")
        out.append((line, cases))
    return tuple(out)


def refus_mesures_2027() -> tuple[tuple[RefusMesure, Montant2027], ...]:
    """Chaque refus mesuré avec sa ligne du relevé ; refusé s'il n'en a pas, ou si la ligne
    est chiffrée ou hors du dénominateur."""
    lines = {(m.article, m.volet): m for m in MONTANTS_2027}
    out = []
    for refus in REFUS_MESURES_2027:
        line = lines.get((refus.article, refus.volet))
        if line is None or line.meur is None or line.chiffre:
            raise ValueError(f"art. {refus.article}, volet « {refus.volet} » : un refus "
                             f"mesuré nomme une ligne du dénominateur que l'outil ne "
                             f"chiffre pas")
        out.append((refus, line))
    return tuple(out)


#: Ce qui ouvrirait un article refusé : un catalogue fermé de huit portes, dans l'ordre
#: de D-293. La porte suit la raison du triage du 2026-10-02, pas les volets.
OUVERTURES: dict[str, str] = {
    "hors_champ": "rien : une formalité ou une procédure",
    "donnee_menages": "une donnée des ménages : plus-values, épargne, logement",
    "dimension_entreprises": "une dimension des entreprises : territoire, département, "
                             "secteur agricole",
    "transmission": "un module de transmission : donations et reprises",
    "bilan_entreprises": "le bilan des entreprises : investissement, amortissement, "
                         "provisions, capital",
    "consommation": "la consommation et le parc : TVA par taux, accises, véhicules",
    "bases_locales": "les bases locales : foncier, logement social, zonage",
    "secteur": "l'assiette d'un secteur hors du modèle : audiovisuel, nucléaire, aérien, "
               "infrastructures, dépôts, justice",
}

OUVERTURE_2027: dict[int, str] = {
    **dict.fromkeys((1, 28, 29, 30, 31, 33), "hors_champ"),
    **dict.fromkeys((5, 6, 7), "donnee_menages"),
    **dict.fromkeys((11, 13, 14), "dimension_entreprises"),
    **dict.fromkeys((4, 10), "transmission"),
    **dict.fromkeys((9, 17, 18), "bilan_entreprises"),
    **dict.fromkeys((16, 19, 24, 25, 32), "consommation"),
    **dict.fromkeys((8, 26), "bases_locales"),
    **dict.fromkeys((12, 20, 21, 22, 23, 27), "secteur"),
}


@dataclass(frozen=True)
class Porte:
    """Une porte, ses articles, et l'effort de 2027 qu'elle ouvrirait."""

    cle: str
    libelle: str
    articles: tuple[int, ...]
    meur: float
    articles_hors: tuple[int, ...]


def portes_2027() -> tuple[Porte, ...]:
    """Les portes, de celle qui ouvrirait le plus d'euros à celle qui en ouvrirait le
    moins ; à euros égaux, par nombre d'articles."""
    out = set(articles_hors_denominateur_2027())
    portes = []
    for cle, libelle in OUVERTURES.items():
        articles = tuple(sorted(n for n, k in OUVERTURE_2027.items() if k == cle))
        meur = sum(yield_2027_meur(n) or 0.0 for n in articles)
        portes.append(Porte(cle, libelle, articles, meur,
                            tuple(n for n in articles if n in out)))
    return tuple(sorted(portes, key=lambda p: (-p.meur, -len(p.articles))))


# --------------------------------------------------------------------------- #
# Le PLFSS 2027 — triage du 2026-10-29 (but 5, D-298)
# --------------------------------------------------------------------------- #
SOURCE_PLFSS_2027 = (
    "Assemblée nationale, texte n° 3211 (17e législature), projet de loi de financement de "
    "la sécurité sociale pour 2027, enregistré le 1er octobre 2026, articles avec exposé "
    "des motifs. Manifesté : plfss2027_texte_an_b3211.html, sha256 b68128d00b62. Lu à "
    "travers le masque des montants (D-297)."
)

DATE_TRIAGE_PLFSS_2027 = "2026-10-29"

#: Le catalogue de D-293, plus une porte que le PLF n'appelait pas : il n'a aucun article de
#: soins. Datée du jour du triage (D-298).
OUVERTURES_PLFSS_2027: dict[str, str] = {
    **OUVERTURES,
    "sante": "un modèle des soins et de leurs financeurs : ONDAM, produits de santé, "
             "établissements, professionnels",
}


@dataclass(frozen=True)
class ArticlePLFSS2027:
    """Un article du PLFSS 2027, sa case et la porte qui l'ouvrirait. L'article liminaire
    porte le numéro 0."""

    numero: int
    intitule: str
    bucket: str
    porte: str
    raison: str

    def __post_init__(self) -> None:
        if self.bucket not in BUCKETS:
            raise ValueError(f"art. {self.numero} : case « {self.bucket} » inconnue")
        if self.porte not in OUVERTURES_PLFSS_2027:
            raise ValueError(f"art. {self.numero} : porte « {self.porte} » hors du catalogue")
        if not self.raison.strip():
            raise ValueError(f"art. {self.numero} : un refus sans raison")


_P = ArticlePLFSS2027
_HC = "not_priceable"
_EQUILIBRE = ("scope. Un tableau, un objectif ou une dotation que la loi de financement "
              "vote chaque année : pas une mesure sur les ménages ni sur les entreprises.")
_SOINS = ("structure. Une dépense de soins ou du médico-social : l'outil ne modélise ni "
          "l'offre de soins, ni les produits de santé, ni les établissements.")

ARTICLES_PLFSS_2027: tuple[ArticlePLFSS2027, ...] = (
    _P(0, "Article liminaire", _HC, "hors_champ", _EQUILIBRE),
    _P(1, "Rectification des tableaux d'équilibre", _HC, "hors_champ", _EQUILIBRE),
    _P(2, "Rectification de l'ONDAM et des sous-objectifs ONDAM", _HC, "hors_champ",
       _EQUILIBRE),
    _P(3, "Rectification des contributions des régimes d'assurance maladie et de la 5ème "
          "branche au FMIS et de la 5ème branche au FIR des ARS", _HC, "hors_champ",
       _EQUILIBRE),
    _P(4, "Aide aux cotisants affectés par les incendies et le cyclone Chido et soutien aux "
          "employeurs de sapeurs-pompiers volontaires", _HC, "dimension_entreprises",
       "data. Un territoire sinistré et l'emploi de sapeurs-pompiers volontaires : la "
       "population des entreprises n'a ni l'un ni l'autre."),
    _P(5, "Suppression des exonérations sociales applicables aux ateliers et chantiers "
          "d'insertion publics", _HC, "secteur",
       "structure. Les employeurs publics de l'insertion par l'activité économique sont un "
       "secteur hors du modèle."),
    _P(6, "Simplifier le régime social applicable aux indemnités de rupture du contrat de "
          "travail", _HC, "donnee_menages",
       "data. La population n'a pas d'indemnité de rupture : le même refus que le volet "
       "correspondant de l'art. 2 du PLF."),
    _P(7, "Rationaliser l'assiette des allègements généraux de cotisations sociales", _HC,
       "donnee_menages",
       "data. L'assiette ajoute l'épargne salariale, l'intéressement, la prime de partage de "
       "la valeur et les jours de repos rachetés ; la population n'a aucun de ces "
       "compléments de salaire."),
    _P(8, "Extension de la « taxe soda » à des produits sucrés et transformés", _HC,
       "consommation", "structure. Une accise sur des produits : aucune consommation."),
    _P(9, "Régulation macroéconomique des dispositifs médicaux", _HC, "sante", _SOINS),
    _P(10, "Amélioration de la régulation de la chaîne de valeur de la distribution du "
           "médicament", _HC, "sante", _SOINS),
    _P(11, "Régulation macro-économique des produits de santé", _HC, "sante", _SOINS),
    _P(12, "Prorogation de la contribution exceptionnelle au financement du système de "
           "santé et de la couverture santé des Français les plus précaires", _HC,
       "secteur",
       "structure. Une contribution des organismes complémentaires d'assurance maladie : un "
       "secteur hors du modèle."),
    _P(13, "Réforme du financement des départements pour les dépenses APA/PCH", _HC,
       "hors_champ", "scope. Un financement entre administrations."),
    _P(14, "Clarifier les transferts financiers au sein de la sécurité sociale", _HC,
       "hors_champ", "scope. Des transferts entre branches et caisses."),
    _P(15, "Approbation du montant de la compensation des exonérations ciblées", _HC,
       "hors_champ", _EQUILIBRE),
    _P(16, "Tableau d'équilibre 2027", _HC, "hors_champ", _EQUILIBRE),
    _P(17, "Objectif d'amortissement de la dette sociale et prévisions sur les recettes du "
           "FRR", _HC, "hors_champ", _EQUILIBRE),
    _P(18, "Liste et plafonds de trésorerie des régimes et organismes habilités à recourir "
           "à des ressources non permanentes", _HC, "hors_champ", _EQUILIBRE),
    _P(19, "Approbation du rapport sur l'évolution pluriannuelle du financement de la "
           "sécurité sociale (annexe \"A\")", _HC, "hors_champ", _EQUILIBRE),
    _P(20, "Renforcer la coordination entre le médecin traitant, le médecin du travail et le "
           "médecin conseil pour améliorer le suivi médical des personnes en arrêt de "
           "travail", _HC, "sante", _SOINS),
    _P(21, "Renforcer l'accès aux soins : déployer une mission de solidarité territoriale "
           "pour les médecins en soutien du réseau France Santé", _HC, "sante", _SOINS),
    _P(22, "Conforter le mode de rémunération de structures d'exercice coordonné pour "
           "renforcer l'accès aux soins des personnes vulnérables", _HC, "sante", _SOINS),
    _P(23, "Permettre la prise en charge des actes d'assistance à la téléconsultation pour "
           "les infirmiers salariés intervenant au domicile des patients", _HC, "sante",
       _SOINS),
    _P(24, "Renforcer l'accès aux soins des enfants pris en charge par le service d'aide "
           "sociale à l'enfance", _HC, "sante", _SOINS),
    _P(25, "Renforcer la prise en charge sanitaire des mineurs victimes de violences", _HC,
       "sante", _SOINS),
    _P(26, "Mise en place de la complémentaire santé au bénéfice des agents de la fonction "
           "publique hospitalière (FPH)", _HC, "sante", _SOINS),
    _P(27, "Favoriser l'accès à la vaccination", _HC, "sante", _SOINS),
    _P(28, "Préserver l'efficacité des médicaments antibiotiques et sécuriser leur "
           "disponibilité", _HC, "sante", _SOINS),
    _P(29, "Renforcer l'accessibilité aux dispositifs de prévention", _HC, "sante", _SOINS),
    _P(30, "Accès aux médicaments et à l'innovation : adapter le remboursement aux progrès "
           "scientifiques et sécuriser la délivrance sans prescription", _HC, "sante",
       _SOINS),
    _P(31, "Assurer l'harmonisation et la convergence tarifaire de l'activité de "
           "radiothérapie en ville et à l'hôpital", _HC, "sante", _SOINS),
    _P(32, "Sécuriser les modalités de facturation à l'assurance maladie", _HC, "sante",
       _SOINS),
    _P(33, "Suppression de l'ANDPC et convergence des dispositifs de développement "
           "professionnel continu et de certification périodique", _HC, "sante", _SOINS),
    _P(34, "Forfaitiser et harmoniser la majoration de pension pour enfants", _HC,
       "donnee_menages",
       "data. Il faudrait le nombre d'enfants élevés par chaque retraité et la pension "
       "qu'il majore ; la population a la pension totale, pas ses droits."),
    _P(35, "Dérogation exceptionnelle aux modalités de revalorisation des pensions de "
           "retraite pour 2027", _HC, "donnee_menages",
       "data. La population porte la pension totale, donc le seuil de 1 281 €, mais pas la "
       "part de base, seule revalorisée ; et le moteur prend les pensions comme une "
       "donnée, pas comme une dépense. Le plus proche d'un chiffrage (D-298)."),
    _P(36, "Créer une allocation de remplacement bénéficiant aux non-salariés agricoles dont "
           "un enfant est gravement malade, porteur d'un handicap ou victime d'un accident",
       _HC, "donnee_menages",
       "data. Ni le statut d'exploitant agricole, ni l'état de santé d'un enfant."),
    _P(37, "Restreindre l'accès aux prestations familiales pour les étrangers extra-UE", _HC,
       "donnee_menages",
       "data. Une condition de durée de résidence régulière : la population n'a ni "
       "nationalité ni titre de séjour."),
    _P(38, "Prolongation de l'expérimentation \"fusion des sections\" (réforme du modèle de "
           "financement des EHPAD)", _HC, "sante", _SOINS),
    _P(39, "Intéressement à l'efficience des EHPAD et des services autonomie à domicile",
       _HC, "sante", _SOINS),
    _P(40, "Dotation de l'Assurance maladie au FMIS et de la CNSA aux ARS", _HC,
       "hors_champ", _EQUILIBRE),
    _P(41, "Dotation aux opérateurs financés par le 6ème sous-objectif", _HC, "hors_champ",
       _EQUILIBRE),
    _P(42, "Objectif de dépenses de la branche maladie, maternité, invalidité et décès", _HC,
       "hors_champ", _EQUILIBRE),
    _P(43, "ONDAM et sous objectifs de l'ONDAM", _HC, "hors_champ", _EQUILIBRE),
    _P(44, "Dotations au FIVA et au FCAATA, transfert de la compensation de sous-déclaration "
           "ATMP", _HC, "hors_champ", _EQUILIBRE),
    _P(45, "Objectif de dépenses de la branche ATMP", _HC, "hors_champ", _EQUILIBRE),
    _P(46, "Objectif de dépenses de la branche vieillesse", _HC, "hors_champ", _EQUILIBRE),
    _P(47, "Objectif de dépenses de la branche famille", _HC, "hors_champ", _EQUILIBRE),
    _P(48, "Objectif de dépenses de la branche autonomie", _HC, "hors_champ", _EQUILIBRE),
)


def portes_plfss_2027() -> tuple[tuple[str, tuple[int, ...]], ...]:
    """Les portes du PLFSS, de celle qui ouvrirait le plus d'articles à celle qui en
    ouvrirait le moins ; le PLFSS n'a pas d'euros relevés, l'annexe n'étant lue qu'après."""
    portes = []
    for cle in OUVERTURES_PLFSS_2027:
        articles = tuple(a.numero for a in ARTICLES_PLFSS_2027 if a.porte == cle)
        if articles:
            portes.append((cle, articles))
    return tuple(sorted(portes, key=lambda p: -len(p[1])))


#: L'art. 74 du PLF 2027, dans la seconde partie : la seule mesure de dépense que l'outil
#: chiffre, en deux volets et en miroir (D-298).
ARTICLE_74_2027 = Article2027(
    74, "Maîtrise de l'évolution des aides personnelles au logement et de la prime "
        "d'activité",
    "prestations — revalorisations suspendues", "priceable_now", "neuve",
    "Deux boutons neufs, des coefficients écrits à la date légale de chaque "
    "revalorisation : le montant forfaitaire de la prime au 1er avril, les 56 paramètres de "
    "dépense des aides au logement au 1er octobre. L'arbre, figé en 2026, est déjà dans "
    "l'état que l'article produit : les deux cas chiffrent la revalorisation suspendue, en "
    "miroir. Ni la clause qui laisse au pouvoir réglementaire la faculté de revaloriser "
    "quand même, ni les paramètres de ressources, révisés au 1er janvier.",
    knobs=("ppa_revalorisation_avril", "al_revalorisation_octobre"),
    reforme="scenarios/plf2027_art_74_ppa.json, scenarios/plf2027_art_74_apl.json")
