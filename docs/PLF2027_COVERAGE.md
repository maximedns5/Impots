# Triage de couverture — quels articles d'un PLF cet outil sait-il chiffrer ?

**Généré depuis `src/impots/plf_coverage.py` par `scripts/write_plf_coverage.py`.**
Chaque nombre de ce document est calculé depuis la table ; aucun n'est saisi. Et
chaque affirmation de la table sur le code — un bouton nommé, un chemin de
paramètre — est vérifiée par `tests/test_plf_coverage.py`, parce qu'un triage qui
dérive du code qu'il décrit est pire que pas de triage : il sera cru le jour J.

## Pourquoi maintenant, et pourquoi sur le PLF 2026

Le PLF 2027 arrive début octobre. Décider ce jour-là ce que l'outil sait chiffrer,
c'est le décider sous pression et la réponse déjà sous les yeux — la condition
exacte où « on n'a pas su chiffrer X » devient une excuse au lieu d'une limite.
Décidé maintenant, chaque refus est **préenregistré**.

Le texte 2027 n'existe pas et deviner ses numéros d'articles serait la fabrication
que ce projet interdit. Ce qui survit à une renumérotation, c'est la **catégorie** :
les catégories sont le livrable, les numéros 2026 n'en sont que la preuve.

> Assemblée nationale, texte n° 1906 (17e législature), projet de loi de finances pour 2026, articles avec exposé des motifs. Manifesté : plf2026_texte_an_b1906.html, sha256 88ef308e62a2. La section fiscale est « I – Impôts et ressources autorisées / B – Mesures fiscales », articles 2 à 30. ATTENTION : c'est le PROJET déposé, pas la loi promulguée (LOI n° 2026-103 du 19 février 2026) — c'est le bon comparateur pour une structure de dépôt.

## Le chiffre, et il est mauvais

Sur **29 articles fiscaux** d'un vrai PLF, **1** produit aujourd'hui
un chiffre que cet outil peut défendre — soit **3,4 %**.
**Trois autres** ont leurs paramètres dans l'arbre mais
aucun contribuable dans cette population pour les exercer : les câbler publierait un
zéro confiant. Les **20** restants sont hors de la structure du
modèle ou hors de ses données.

Un outil qui prétendrait chiffrer tout un PLF mentirait sur vingt-trois
articles. Ce document existe pour que ce chiffre soit connu en septembre plutôt
qu'en octobre.

## Le second chiffre, qui dit le contraire du premier

Compter les articles met un droit de timbre au même poids qu'une contribution à
quatre milliards. Compter les euros ne le fait pas — et l'ordre s'inverse.

L'annexe des évaluations préalables **ne chiffre que 11
articles sur 29** : 11 n'ont aucune fiche (l'obligation organique
ne couvre pas les dispositions du domaine exclusif des lois de finances) et
7 portent une fiche dont le montant n'est pas déterminable —
« non chiffrable » selon l'annexe elle-même, ou contradictoire.

Sur les **8 629 M EUR** d'impact première année que l'annexe
quantifie, cet outil en chiffre **4 000 M EUR**, soit
**46,4 %**.

La raison est entière dans un seul article : la contribution exceptionnelle sur les
bénéfices des grandes entreprises, seul article chiffrable, est **le plus gros
montant quantifié de toute l'annexe** — 4 000 M EUR en 2026.
**3,4 % des articles, 46,4 % des euros.**
Les deux chiffres sont vrais et il faut les donner ensemble :
l'un seul flatte, l'autre seul accable.

Une mise en garde sur ce second chiffre, et elle est structurelle : son dénominateur
n'est pas le PLF, c'est **la part du PLF que l'annexe chiffre**. Les articles sans
fiche et les « non chiffrables » en sont exclus, pas mis à zéro — les compter à zéro
gonflerait la part ; les compter à leur valeur inconnue est impossible. La direction
du biais est donc inconnue, et c'est pour cela qu'elle est dite.

## Deux drapeaux que les trois cases ne peuvent pas porter

Le cahier des charges demande exactement une case par article, et `bucket` la porte.
Mais « chiffrable » cachait deux questions indépendantes, et les confondre est
précisément la façon dont un zéro confiant se publie :

* `engine_ready` — les paramètres existent et la formule les lit : il ne manque que
  le câblage ;
* `population_can_exercise` — la population synthétique contient réellement des
  contribuables que la mesure atteint.

Et une **quatrième case**, `population_blind`, née de cette distinction : le moteur
saurait, la population ne peut pas. La câbler publierait un zéro confiant, ce qui
est pire qu'un refus puisque cela porte la provenance d'une vraie réponse. Chaque
article de cette case doit nommer ce qui **ouvrirait la porte** — une porte
lointaine reste une porte, et le document ne doit mentir dans aucun des deux sens.

**L'article 2 (CDHR) a forcé la distinction.** Ses paramètres résolvent, sa variable
tourne, et elle mord : −75 836 EUR sur un foyer à 2 M EUR de dividendes. À la
lettre, c'est un « petit bouton ». Mais la CDHR est un complément portant le taux
moyen à 20 %, qu'un contribuable purement salarié dépasse déjà — donc sur une
population sans revenus du capital l'assiette est vide **par construction**, et la
câbler publierait 0,00 EUR face à un rendement d'environ un milliard.

## La table

| art. | catégorie | case | moteur | population | boutons | conf. |
|---|---|---|---|---|---|---|
| 2 | IR contribution exceptionnelle sur les hauts | population aveugle | prêt | aveugle | — | haute |
| 3 | taxe sur le patrimoine des sociétés (holding | non chiffrable | — | aveugle | — | haute |
| 4 | IS contribution exceptionnelle (CEBGE) | **chiffrable** | prêt | oui | cebge_seuils_et_taux | haute |
| 5 | suppressions de niches (paquet multi-instrum | population aveugle | prêt | aveugle | frais_scolarite_college, frais_scolarite_lycee, frais_scolarite_superieur | moyenne |
| 6 | abattement IR sur pensions | petit bouton | prêt | oui | — | moyenne |
| 7 | niche investissement outre-mer (IR et IS) | non chiffrable | — | aveugle | — | haute |
| 8 | niche IR souscription au capital de PME / fo | non chiffrable | — | aveugle | — | haute |
| 9 | niche IR dons | population aveugle | prêt | aveugle | dons_coluche_plafond, dons_coluche_taux | haute |
| 10 | fiscalité agricole (BA / IS agricole / DMTG) | non chiffrable | — | aveugle | — | haute |
| 11 | impôts de production (CVAE) | petit bouton | prêt | oui | cvae_taux_max, cvae_degrevement | moyenne |
| 12 | dispositif fiscal zoné (QPV / ZFU) — IS-IR,  | non chiffrable | — | aveugle | — | haute |
| 13 | fiscalité des véhicules (malus CO2, malus ma | non chiffrable | — | aveugle | — | haute |
| 14 | fiscalité transport routier (taxe poids lour | non chiffrable | — | aveugle | — | haute |
| 15 | fiscalité automobile (taxe d'immatriculation | non chiffrable | — | aveugle | — | haute |
| 16 | fiscalité énergie (incorporation de biocarbu | non chiffrable | — | aveugle | — | haute |
| 17 | fiscalité sectorielle et procédure fiscale | non chiffrable | — | aveugle | — | haute |
| 18 | fiscalité énergie (accise électricité et com | non chiffrable | — | aveugle | — | haute |
| 19 | IFER / imposition forfaitaire de production  | non chiffrable | — | aveugle | — | haute |
| 20 | redevances agences de l'eau (fiscalité envir | non chiffrable | — | aveugle | — | haute |
| 21 | fiscalité déchets (TGAP, taxe emballages pla | non chiffrable | — | aveugle | — | haute |
| 22 | fiscalité douanière / importations | non chiffrable | — | aveugle | — | haute |
| 23 | fiscalité tabac et produits à fumer (accises | non chiffrable | — | aveugle | — | haute |
| 24 | taxe sectorielle numérique / audiovisuel (as | non chiffrable | — | aveugle | — | haute |
| 25 | TVA — seuils de franchise en base | non chiffrable | — | aveugle | — | haute |
| 26 | IS — imposition minimale mondiale (Pilier 2) | non chiffrable | — | aveugle | — | haute |
| 27 | fiscalité locale — valeurs locatives (TFPB,  | non chiffrable | — | aveugle | — | haute |
| 28 | procédure — facturation électronique (TVA) | non chiffrable | — | aveugle | — | haute |
| 29 | procédure — gestion fiscale (avec option bar | non chiffrable | — | aveugle | — | haute |
| 30 | droits de timbre et taxes sur titres | non chiffrable | — | aveugle | — | haute |

## Les raisons, article par article

### Article 2 — IR contribution exceptionnelle sur les hauts revenus (CDHR/CEHR)

*Prorogation de la contribution différentielle sur les hauts revenus*

**population aveugle**

data. Aucun knob CDHR/CEHR n'existe dans knobs.json, et les paramètres openfisca existent bien (impot_revenu.contributions_exceptionnelles.contribution_differentielle_hauts_revenus.{taux_cdhr, seuil_celibataire, seuil_couple, taux_acompte, taux_penalite_acompte} résolvent True au 2026-01-01, avec taux_cdhr = 0,20 et seuil = 250 000, et openfisca porte déjà les variables contribution_differentielle_hauts_revenus*) — donc le câblage serait facile. Ce n'est pas pour autant du small_knob : le câbler produirait un zéro confiant. La CDHR ne mord que sur les foyers dont le taux moyen d'imposition est INFÉRIEUR à 20 % du RFR au-dessus de 250 k€, c'est-à-dire exactement les foyers que cette population ne sait pas construire. KNOWN_LIMITATIONS : « No capital income, no property income — the top of the distribution is a construction; nothing above roughly the 95th percentile is publishable » et « N

**Ce qui l'ouvrirait :** income microdata THAT SEES THE TOP — échantillon lourd DGFiP / POTE. PAS l'ERFS : la clé nommée par D-096 a été OBTENUE (millésime 2022, FPR) et essayée, et elle n'ouvre pas (D-141). Le motif « seuil sur ratio » (D-105.2) est MORT — il visait l'imputation uniforme dans la cellule, et des microdonnées portent de la dispersion réelle ; la reconstruction rend 0,99 md€ contre 1,50 publié une fois sa jambe PFU rétablie. Ce qui refuse est autre : la CDHR vit tout entière dans le dernier centile, qu'une enquête auprès des ménages sous-compte par construction — bande classée sans verdict par le tableau E2, préenregistrée avant tout chiffre ERFS. Le défaut est dans le PLAN DE SONDAGE, pas dans la granularité : aucune enquête ne l'ouvrira. Historique : la CDHR est définie par un seuil portant sur un RATIO — le taux moyen d'imposition rapporté au RFR — donc une imputation uniforme dans la cellule met tous les foyers du même côté du seuil de 20 %, et le rendement saute de zéro à des milliards selon le placement de la moyenne. Ce n'est PAS une question de finesse : la granularité publiée descend au millime (DGFiP n° 41) et cela ne suffit pas, parce que le placement intra-cellule EST la réponse. Aucune imputation par fractile n'ouvrira cette porte, si fine soit-elle ; seules des microdonnées le peuvent. F1b (D-097) a mesuré que la même source ouvre en revanche le PFU, qui est proportionnel.

### Article 3 — taxe sur le patrimoine des sociétés (holdings)

*Instauration d'une taxe sur le patrimoine financier des holdings patrimoniales*

**non chiffrable**

structure (et data en second rideau). Le modèle entreprises n'a aucun bilan et aucune structure de détention : data/processed/firms_2023.parquet ne porte que firm_id, cell, naf_section, taille, weight, chiffre_affaires, valeur_ajoutee, resultat_comptable, benefice_imposable, capital_libere_detenu_personnes_physiques. Il n'y a donc ni valeur vénale d'actifs, ni disponibilités, ni titres, ni participations, ni part de revenus passifs, ni personne physique détentrice — c'est-à-dire aucune des quatre conditions d'assujettissement ni aucun terme de l'assiette. Le secteur n'est connu qu'au niveau SECTION NAF, si bien qu'une holding (64.20Z) n'est même pas distinguable du reste de la section K. Aucun knob entreprises (FirmReformSpec : IS, CS, C3S, CVAE, CEBGE) n'approche cet instrument, et aucun paramètre correspondant n'existe dans l'arbre. Côté ménages, le volet IFI (art. 975 nouveau VII) est

### Article 4 — IS contribution exceptionnelle (CEBGE)

*Prorogation en 2026 avec division par deux des taux de la contribution exceptionnelle sur les bénéfices des gr*

****chiffrable****

Le knob apparié cebge_seuils_et_taux exprime exactement le cœur de l'article. Vérifié en exécution : FirmReformSpec(cebge_seuils_et_taux=[{seuil_ca: 1e9, taux: 0.103}, {seuil_ca: 3e9, taux: 0.206}]) + make_reform(..., 2026) passe verify_scales et donne au 2026-01-01 seuil_ca 1,0 Md, taux_base 0,103, seuil_ca_taux_majore 3,0 Md, taux_majore 0,206, bornes de lissage 1,1 Md et 3,1 Md — soit les trois bandes du texte, la largeur de 100 M€ étant dérivée du seuil et non inventée (elle existe bien au 2026-01-01). La CEBGE est modélisée (variables.cebge, assiette = moyenne de deux exercices d'IS) et réconciliée : 9,3 Md€ contre 7,5 Md€ publiés, +23,1 %, dans la tolérance de ±25 %. TROIS RÉSERVES à pré-enregistrer. (1) Contrefactuel : l'arbre de référence porte déjà la LF 2026 PROMULGUÉE (seuil monté à 1,5 Md€ en 2026, taux maintenus à 20,6/41,2 — le commentaire du YAML dit explicitement que « la

### Article 5 — suppressions de niches (paquet multi-instruments)

*Diverses suppressions et rationalisations de dépenses fiscales*

**population aveugle**

structure pour la masse de l'article, data pour la seule part qui semblait atteignable. L'article est un paquet de 23 suppressions portant sur des instruments dont le modèle n'a majoritairement aucune entité : accises énergie B100/E85 du code des impositions sur les biens et services, taxe à l'essieu (véhicules), TVA, droits d'enregistrement et donations, taxe foncière non bâtie, amortissements et crédits d'impôt à l'IS (le module entreprises calcule un IS AVANT crédits d'impôt — « our IS is already before crédits — the model has none »). Le volet indemnités journalières ALD est du data pur : la population ne porte que salaire_brut_annuel, pension_annuelle et chomage_annuel, aucune IJ. LE PIÈGE, et c'est pour lui que ce refus est pré-enregistré : trois knobs existent bel et bien pour le 12° (frais_scolarite_college, frais_scolarite_lycee, frais_scolarite_superieur → impot_revenu.calcul_r

**Ce qui l'ouvrirait :** a published frais-de-scolarité base that separates collège / lycée / supérieur. `niches.py` excludes scolarité from IMPUTABLE deliberately: the 2042 cases are COUNTS of children and the published DGFiP column aggregates the three levels, so there is nothing to impute a euro base from. Real income microdata would also do it. The three knobs themselves are live and price correctly on a cas-type.

### Article 6 — abattement IR sur pensions

*Création d'un abattement forfaitaire en faveur des personnes retraitées*

**petit bouton** · chemins : `impot_revenu.calcul_revenus_imposables.deductions.abatpen.taux`, `impot_revenu.calcul_revenus_imposables.deductions.abatpen.min`, `impot_revenu.calcul_revenus_imposables.deductions.abatpen.max`, `impot_revenu.calcul_revenus_imposables.abat_rni.contribuable_age_invalide`

Aucun knob de ReformSpec ne touche l'abattement pensions (knobs.json n'en contient pas), mais les quatre paramètres bougés existent et résolvent (exists_at = True au 2026-01-01). Le a bis est exactement représentable : la formule openfisca `revenu_assimile_pension_apres_abattements` calcule max(0, p − round(max(taux·p, min))), donc taux = 0, min = 2 000 et max relevé donnent min(p, 2 000) par individu, ce qui est littéralement le texte. La suppression de la branche âge du 157 bis se fait en mettant à zéro les montants du barème `contribuable_age_invalide` — ce qui est EXACT dans cette population et seulement dans elle, parce que caseP/caseF ne sont jamais renseignés par to_openfisca.py : personne n'est invalide, donc l'éligibilité y est purement l'âge ≥ 65 et le carve-out invalidité conservé par l'article ne coûte rien ici (il coûterait dans la réalité, donc le chiffrage sur-abroge légèr

### Article 7 — niche investissement outre-mer (IR et IS)

*Réforme du régime d'aide fiscale à l'investissement productif outre-mer*

**non chiffrable**

Refus, motif STRUCTURE en premier lieu. Le cœur de l'article est l'IS : 217 undecies (déduction), 244 quater W (crédit d'impôt) et 244 quater Y (réduction d'impôt). Or le moteur entreprises n'a AUCUN instrument de ce genre — variables.py ne définit que chiffre_affaires, benefice_imposable, valeur_ajoutee, impot_societes, contribution_sociale_is, c3s, cebge, cvae : pas un seul crédit ni une seule réduction d'impôt, pas d'investissement, pas de localisation géographique. FirmReformSpec le confirme : onze knobs, tous des taux/seuils/abattements de barème, rien qui ressemble à une aide à l'investissement. Il n'y a donc pas de paramètre à bouger, et l'article ne peut pas être exprimé même partiellement de ce côté. La contrainte DATA mord ensuite du côté ménages : les paramètres 199 undecies B existent bien dans l'arbre (impot_revenu.calcul_reductions_impots.outremer_investissement.doment/doms

### Article 8 — niche IR souscription au capital de PME / fonds

*Modernisation de la réduction d'impôt sur le revenu « Madelin »*

**non chiffrable**

Refus, motif DATA. La population ne porte aucune base de souscription : l'imputation de niches (niches.py) est explicitement limitée à cinq cases — f7db, f7ga, f7ac, f7uf, f7ud — et le commentaire de schemas.py note que f7d* contient « cinq cases de souscription PME » qu'on a délibérément laissées de côté. S'y ajoutent deux limitations connues qui mordent ensemble : « No capital income, no property income — nothing above roughly the 95th percentile is publishable », alors que l'IR-PME est concentrée dans le dernier centile, et « No réductions or crédits d'impôt » hors les cinq imputées. Une tentative naïve serait pire qu'un refus : les paramètres existent (impot_revenu.calcul_reductions_impots.souscriptions.souscriptions_parts_fcpi_fip.taux / taux_corse / taux_outre_mer / plafond_celibataire / plafond_couple, et souscriptions.pme.souscription_capital.*), donc mettre taux à zéro pour abro

### Article 9 — niche IR dons

*Doublement de l'incitation fiscale à la générosité des particuliers en faveur des organismes d'aide aux personnes en difficulté*

**population aveugle** · bannières : zero_base_niche · chemins : `impot_revenu.calcul_reductions_impots.dons.dons_coluche.plafond`

data, deux fois, et le knob n'y est pour rien — il est exact. (1) LE COMPARATEUR CONTIENT DÉJÀ LA MESURE : le plafond dons Coluche vaut 2 000 EUR dans l'arbre depuis 2025-01-01 (1 000 EUR de 2020 à 2024), parce que le doublement a été voté. Chiffrer l'article contre cette ligne de base rend exactement 0,00 EUR — un zéro confiant, indiscernable d'une mesure sans effet. Vérifié en lisant l'arbre année par année. (2) MÊME CONTRE UN CONTREFACTUEL À 1 000 EUR, L'ASSIETTE EST VIDE : la base de dons imputée par `niches.py` va de 157 EUR (D4) à 447 EUR (D1), sans aucune dispersion intra-décile — « every claimant in a decile gets the same base » — donc aucun foyer de cette population n'atteint 1 000 ni a fortiori 2 000 EUR. Le rendement réel de la mesure vient entièrement de la queue de la distribution des dons, que l'imputation aplatit. La CATÉGORIE « niche IR dons — plafond » reste chiffrable sur cas-type, avec la bannière zero_base_niche en agrégat ; c'est CET article, contre CE comparateur, qui ne l'est pas.

**Ce qui l'ouvrirait :** within-decile dispersion of donations. The imputation gives every claimant in a decile the same base (157-447 EUR), so no household ever reaches a 1 000 or 2 000 EUR ceiling and the ceiling knob is inert in aggregate however correct it is. Microdata, or a published distribution of donation amounts rather than a per-decile mean, would unlock it. Note this article ALSO needs `mirror`: the tree already carries the 2 000 EUR ceiling.

### Article 10 — fiscalité agricole (BA / IS agricole / DMTG)

*Ajustement de certains dispositifs de soutien au secteur agricole (prorogation de la dotation pour épargne de *

**non chiffrable**

data, principalement. Le refus tient à la population, pas au droit. Côté ménages, KNOWN_LIMITATIONS l'écrit noir sur blanc : « No self-employment income. 3.87 M people are recorded in employment as indépendants and receive nothing » — il n'existe aucun bénéfice agricole, aucun résultat d'exploitation, aucun stock ni cheptel dans le fichier. Une DEP, une provision pour hausse de valeur des stocks ou une exonération de plus-value sur indemnité d'abattage s'appliquent toutes à une assiette dont la valeur est identiquement nulle chez nous : le chiffrage rendrait zéro, ce qui n'est pas une réponse mais une absence d'assiette. Côté entreprises, la population synthétique est bâtie sur des cellules NAF section × taille (la section A existe) mais ne porte que chiffre d'affaires, valeur ajoutée et résultat ; ni cheptel, ni indemnité sanitaire, ni certification bio ne sont observables, et le résult

### Article 11 — impôts de production (CVAE)

*Anticipation de la suppression progressive de la CVAE*

**petit bouton**

Les deux knobs expriment exactement le cœur de l'article, et le baseline porte déjà le contrefactuel qu'il amende : j'ai lu la valeur au 01/01/2026, cvae.taux_max = 0,0028 et cvae.degrevement.montant = 188 €, soit précisément la trajectoire LF 2025 que le PLF abroge. Le chiffrage est donc un diff à deux curseurs, année par année : 2026 (cvae_taux_max = 0,0019 ; cvae_degrevement = 125), 2027 (0,0009 ; 63), 2028 (suppression). Le couple taux/dégrèvement est apparié dans le YAML lui-même (0,28 %↔188, 0,19 %↔125, 0,09 %↔63), donc bouger le taux sans le dégrèvement serait un demi-barème — les deux knobs sont nécessaires et suffisants pour la CVAE. Bande : C4 (production_tax_investment) revendique nommément responds_to_knobs: [cvae_taux_max, cvae_degrevement], estimée sur la baisse d'impôts de production de 2021 (IPP rapport 60), bande centrée sur zéro [−0,071 ; +0,069] en % d'investissement p

### Article 12 — dispositif fiscal zoné (QPV / ZFU) — IS-IR, CFE, TFPB

*Renforcement des dispositifs fiscaux de soutien à la géographie prioritaire de la politique de la ville*

**non chiffrable**

data pour le volet principal, structure pour le reste. Data : l'exonération de 44 octies B est définie par la localisation de l'établissement dans un QPV, et la population d'entreprises ne porte aucune géographie. Elle est construite sur des cellules NAF section × taille — 19 sections × trois classes de taille, 400 firmes tirées par cellule — et rien d'autre : ni commune, ni quartier, ni date de création ou de reprise, ni distinction activité commerciale/artisanale/santé, ni effectif salarié individuel. Aucune de ces cinq conditions cumulatives n'est observable, et l'ensemble ne peut pas être approché par une cellule sectorielle : les QPV ne sont pas un secteur. Un chiffrage exigerait un dénombrement d'établissements par QPV que le projet ne détient pas, pas un paramètre à bouger. Structure pour l'autre moitié : la CFE, la taxe foncière sur les propriétés bâties, la taxe sur les bureaux 

### Article 13 — fiscalité des véhicules (malus CO2, malus masse, taxes annuelles, taxe

*Verdissement de la fiscalité sur les véhicules*

**non chiffrable**

structure. L'outil ne contient aucune des taxes que cet article modifie, et j'ai vérifié plutôt que supposé : au 01/01/2026, taxation_indirecte ne porte que {alcools_autres_boissons, produits_energetiques, taxes_assurances, taxes_energie_dans_logement, taxes_tabacs, tva} — pas de malus, pas de taxe annuelle sur les véhicules, pas de taxe incitative LOM ; et rien du code des impositions sur les biens et services (livre IV, chapitre Ier), qui est le siège de tout le II de l'article. Il n'y a pas non plus d'entité « véhicule » : ni parc, ni immatriculation, ni émissions de CO2, ni masse en ordre de marche, ni catégorie de réception M1/N1/L6e/L7e — donc même en écrivant les barèmes on n'aurait aucune assiette à leur appliquer. Le volet 39 decies A (déduction exceptionnelle poids lourds) s'ajoute par la data : la population d'entreprises ne porte ni investissement ni acquisition de véhicules,

### Article 14 — fiscalité transport routier (taxe poids lourds)

*Ajustements de la taxe sur l'utilisation par les poids lourds de certaines voies du domaine public routier (éc*

**non chiffrable**

structure. L'outil ne possède aucun instrument de taxation de l'usage routier ni aucune entité « véhicule » ou « transporteur » : ni ReformSpec (57 knobs ménages : barème IR, décote, QF, CSG, allègements, prestations, IFI, niches) ni FirmReformSpec (11 knobs : IS, CS, C3S, CVAE, CEBGE) n'exposent quoi que ce soit de proche, et un grep de src/impots ne trouve aucune référence à une taxe d'usage routier. Aucun paramètre openfisca correspondant n'existe non plus (le sous-arbre taxation_indirecte.produits_energetiques ne contient que TICPE, majorations régionales TICPE et TGAP carburants), donc ce n'est pas non plus un small_knob. S'y ajoute, à titre secondaire, un motif de scope : il s'agit d'une taxe affectée à des collectivités territoriales, et la modification porte pour l'essentiel sur des facultés ouvertes à l'autorité compétente par délibération, dont le rendement dépend de choix loca

### Article 15 — fiscalité automobile (taxe d'immatriculation)

*Stabilité des prélèvements sur les transports au bénéfice d'Île-de-France Mobilités*

**non chiffrable**

structure. Il n'existe dans l'outil ni instrument « taxe sur les certificats d'immatriculation » ni variable de détention ou d'acquisition de véhicule : aucun knob de knobs.json ne s'en approche, et l'arbre openfisca chargé (impot_revenu, prelevements_sociaux, prestations_sociales, taxation_capital, taxation_indirecte, taxation_societes, taxe_habitation) ne contient aucun nœud de taxe d'immatriculation — donc pas de small_knob possible. Le motif de données jouerait aussi (la population EEC ne porte ni véhicule, ni puissance fiscale, ni acte d'immatriculation), mais il est second : même avec la donnée, l'instrument n'existe pas. Motif secondaire de scope : ressource affectée à un établissement public local, dont le quantum dépend d'une délibération d'IDFM. Aucune couche ne tourne, aucun bandeau ne se déclenche.

### Article 16 — fiscalité énergie (incorporation de biocarburants)

*Renforcement des incitations à l'utilisation d'énergie renouvelable dans les transports*

**non chiffrable**

structure. Le prélèvement porte sur les metteurs à la consommation de carburants, une entité que l'outil n'a pas : le module entreprises ne connaît que l'IS, la CS, la C3S, la CVAE et la CEBGE, assis sur bénéfice et chiffre d'affaires, et rien qui ressemble à des volumes d'énergie mis à la consommation. J'ai vérifié l'arbre plutôt que de le supposer : taxation_indirecte.produits_energetiques existe et contient ticpe, major_regionale_ticpe_gazole, major_regionale_ticpe_super et tgap_carburants — mais tgap_carburants ne porte que des tarifs unitaires (0,079 sur chaque carburant), PAS les pourcentages cibles d'incorporation des IV et V de l'article 266 quindecies, qui n'existent nulle part dans le tree. Et aucun fichier de src/impots ne lit taxation_indirecte : le sous-arbre est chargé mais mort. Ce n'est donc pas un small_knob (le paramètre déplacé n'existe pas) mais bien une absence d'ins

### Article 17 — fiscalité sectorielle et procédure fiscale

*Mesures diverses de correction, clarification et coordination en matière de fiscalité sectorielle*

**non chiffrable**

scope, avec une composante structure. L'essentiel de l'article est de la pure procédure et de la codification — conditions d'agrément et sanctions des opérateurs de détaxe, modalités de recouvrement et de contrôle des accises transférées à la DGFiP, échanges d'informations entre administrations, warrants agricoles, deux habilitations par ordonnance : ce projet ne modélise pas la procédure fiscale, et le rendement de ces mesures n'est ni un taux ni une assiette qu'une simulation microéconomique pourrait bouger. Pour la seule partie qui déplace de vrais chiffres — les tarifs de la taxe sur les installations nucléaires de base, les frais d'assiette de la taxe sur le streaming musical, la taxe pour frais de chambres — le motif est structure : ce sont trois taxes dont l'outil ne possède aucun instrument (rien dans knobs.json, rien dans FirmReformSpec, et aucun nœud correspondant dans l'arbre 

### Article 18 — fiscalité énergie (accise électricité et combustibles)

*Rationalisation de la fiscalité sur les énergies de chauffage*

**non chiffrable**

data (raison bloquante), et accessoirement structure. Data : la population L1 est construite sur le fichier détail EEC et ne porte aucune consommation d'énergie — ni kWh d'électricité, ni MWh de gaz ou de fioul, ni puissance souscrite du compteur. L'assiette de cette mesure est donc littéralement absente : aucun ménage du fichier n'a de quantité sur laquelle appliquer 24,69 €/MWh, et le tarif réduit ≤ 36 kVA suppose de surcroît une variable de puissance de compteur qui n'existe nulle part. Structure : aucun instrument d'accise n'est calculé par la couche mécanique — la liste des variables du système ne contient aucune variable de taxation de l'électricité ou du gaz (seules apparaissent cheque_energie et ses dérivées, qui sont une prestation, pas une taxe). J'ai vérifié l'arbre openfisca : taxation_indirecte.taxes_energie_dans_logement.taxes_electricite_et_gaz existe et résout (cspe = 22,

### Article 19 — IFER / imposition forfaitaire de production (énergie)

*Majoration du tarif de l'IFER pour les centrales de production d'énergie électrique d'origine photovoltaïque i*

**non chiffrable**

structure. Le module entreprises ne connaît que cinq instruments — IS (taux normal, taux réduit, plafonds), contribution sociale sur l'IS, C3S, CVAE, CEBGE — et la FirmReformSpec n'expose aucun autre levier. L'IFER n'est pas modélisée : ni variable, ni paramètre, ni entité redevable. Le blocage est aggravé côté données : la population firmes est une table de cellules secteur (19 sections NAF) × classe de taille portant chiffre d'affaires, valeur ajoutée, résultat courant et capital libéré — il n'existe aucune granularité d'actif de réseau, donc aucune puissance photovoltaïque installée en kW, ni aucune date de mise en service permettant d'isoler le parc antérieur au 1er janvier 2021 que la majoration vise. Même la voie détournée (traiter la majoration comme une charge déductible qui réduirait l'assiette d'IS) est refusée : il faudrait connaître la répartition des 50 M€ entre exploitants,

### Article 20 — redevances agences de l'eau (fiscalité environnementale affectée)

*Aménagement des redevances des agences de l'eau*

**non chiffrable**

structure (raison bloquante), avec une part de scope. Structure : les redevances des agences de l'eau sont l'exemple canonique d'instrument que l'outil ne porte pas — aucune entité redevable (commune, EPCI, exploitant industriel non raccordé, agriculteur irrigant), aucune assiette (m³ prélevés, flux de pollution, volumes facturés), aucun paramètre dans l'arbre. Ce sont en outre des impositions affectées à des établissements publics de bassin, hors du périmètre budgétaire État que les couches L2-L4 chiffrent. Scope : une bonne moitié de l'article est de la pure tuyauterie juridique — désignation du redevable, arrondi de tarif, notification d'une contre-valeur au service de facturation, extension d'une référence à l'article L. 213-11-7 — c'est-à-dire de la procédure sans effet de rendement identifiable, que le projet ne modélise pas par choix. Je ne stretche pas : l'abattement d'irrigation

### Article 21 — fiscalité déchets (TGAP, taxe emballages plastique, TVA déchets)

*Verdissement de la fiscalité sur les déchets*

**non chiffrable**

structure (raison bloquante pour les trois volets), avec du scope sur le volet TVA. Structure : (1) la TGAP déchets n'existe ni comme variable, ni comme paramètre, ni comme redevable dans l'outil — l'arbre ne contient sous taxation_indirecte.produits_energetiques qu'une tgap_carburants, sans rapport, et les cellules firmes (secteur × taille, CA/VA/résultat) ne portent aucun tonnage enfoui ou incinéré, donc l'assiette est absente autant que l'instrument ; (2) la taxe sur les emballages plastique frappe les éco-organismes et les systèmes individuels de REP — une catégorie d'entité que le modèle ne contient tout simplement pas, et son assiette (tonnage national d'emballages plastique non recyclés, ventilé par part de marché des adhérents) est une donnée de filière, pas une donnée fiscale que la population puisse porter ; (3) aucune TVA n'est calculée nulle part dans le système — le nœud tax

### Article 22 — fiscalité douanière / importations

*Instauration d'une taxe relative aux frais de gestion des petits colis en provenance de pays tiers*

**non chiffrable**

structure. Le simulateur n'a ni entité ni instrument douanier : le redevable est le déclarant en douane, une entité qui n'existe dans aucune des deux populations (ménages OpenFisca, entreprises Ésane/IS). Vérifié : `baseline().variables` ne contient aucune variable de fiscalité indirecte ou douanière (recherche 'tva', 'tabac', 'conso' -> seulement unites_consommation, interets_prets_consommation, cheque_energie_unites_consommation), et l'arbre de paramètres 2026 ne contient aucun noeud correspondant (recherche 'colis', 'douan', 'import' -> zéro occurrence). L'assiette elle-même (775 M d'articles importés) n'est nulle part dans le projet : la population ménages ne porte aucune dépense de consommation, la population entreprises ne porte que chiffre d'affaires / valeur ajoutée / bénéfice. L'incidence sur les ménages passerait par les prix de détail, canal que ni L3 (channels.py ne réclame q

### Article 23 — fiscalité tabac et produits à fumer (accises + taux de TVA)

*Fiscalisation de l'ensemble des produits à fumer*

**non chiffrable**

structure. Les paramètres existent mais aucun instrument ne les consomme, donc ce serait de la modélisation, pas du câblage. Vérifié avec exists_at au 2026-01-01 : taxation_indirecte.tva.taux_reduit -> True et taxation_indirecte.taxes_tabacs.taux_normal.cigarettes -> True ; en revanche `baseline().variables` ne contient AUCUNE variable de TVA ni d'accise tabac (0 résultat sur 'tva'/'tabac'), donc ces paramètres sont inertes dans ce système. Trois obstacles cumulés, chacun suffisant : (i) aucune population ne porte de consommation de tabac ou de liquides — la population ménages n'a même pas de revenu observé (KNOWN_LIMITATIONS), a fortiori pas de dépenses par produit ; (ii) l'arbre 2026 n'a aucun noeud pour les liquides de vapotage (recherche 'vapo', 'liquide', 'nicotine' -> zéro), donc le tarif nouveau n'a nulle part où s'écrire ; (iii) le volet TVA ne change aucun TAUX, il déplace des p

### Article 24 — taxe sectorielle numérique / audiovisuel (assiette et seuils)

*Évolution de la taxe sur les services d'accès à des contenus audiovisuels à la demande*

**non chiffrable**

structure. Le module entreprises ne modélise que cinq instruments — IS, contribution sociale sur l'IS, CEBGE, CVAE, C3S (voir SCALAR_KNOBS et CEBGE_TRANCHE_PATHS dans reforms.py, et les variables de variables.py) — et aucune taxe sectorielle sur les services audiovisuels. L'arbre de paramètres 2026 ne contient rien de tel (recherche 'smad', 'audiovisuel', 'video' -> zéro occurrence). S'y ajoute un blocage de données, secondaire mais réel : l'assiette est la « contrepartie encaissée pour les services taxables », c'est-à-dire une décomposition du chiffre d'affaires par nature de service et par relation d'intermédiation ; la population entreprises est tirée de cellules Ésane secteur × taille et ne porte qu'un chiffre d'affaires agrégé, sans ventilation par service ni lien plateforme/créateur. Les deux effets principaux de l'article — le partage d'assiette entre l'intermédiaire et le fournis

### Article 25 — TVA — seuils de franchise en base

*Ajustement du régime de franchise en base de taxe sur la valeur ajoutée*

**non chiffrable**

structure. Aucun instrument TVA n'existe dans le simulateur : `baseline().variables` ne contient aucune variable de TVA, et le balayage de l'arbre de paramètres au 2026-01-01 sur 'franchise' ne renvoie qu'un seul noeud, prelevements_sociaux.autres_taxes_participations_assises_salaires.taxsal.franchise — la franchise de la TAXE SUR LES SALAIRES, sans rapport avec l'article. Le seuil que l'article déplace n'a donc pas de chemin de paramètre : ce n'est pas du small_knob. Blocage de données redoublant le blocage de structure : les 35 000 entités concernées sont des micro-entrepreneurs et entreprises individuelles entre 25 000 € et 37 500 € de CA, or cells.py retire explicitement du champ la moitié la plus petite des micro-entreprises Ésane au motif qu'elles ne sont pas redevables de l'IS (« micro-entrepreneurs et entreprises individuelles ») — la population de ce projet est construite pour l

### Article 26 — IS — imposition minimale mondiale (Pilier 2)

*Précisions apportées à l'imposition minimale mondiale des grandes entreprises multinationales*

**non chiffrable**

structure. Le modèle entreprises n'a aucun instrument Pilier 2 : les onze knobs firm de FirmReformSpec couvrent l'IS (taux normal, taux réduit, plafond de la tranche réduite, seuil de CA PME), la contribution sociale, la C3S, la CVAE et la CEBGE, et rien d'autre. src/impots/entreprises/margins.py dit explicitement que « la contribution sociale, la CEBGE et Pilier 2 » sont des lignes budgétaires séparées, exclues du périmètre comparé. Il n'existe ni entité « groupe multinational consolidé », ni juridiction, ni passif d'impôt différé dans la population de firmes, qui est un tableau de cellules secteur × taille tiré d'Ésane/Focus 372/DGFiP Stat 39 — donc pas de niveau de détail groupe. S'y ajoute une part purement procédurale (DAC 9, déclaration rectificative) qui relèverait de toute façon du scope. Aucune tentative de chiffrage partiel n'est possible : bouger is_taux_normal n'exprime rien 

### Article 27 — fiscalité locale — valeurs locatives (TFPB, CFE, THRS, TEOM)

*Ajustement de la mise en œuvre de la révision des valeurs locatives des locaux professionnels et de la révisio*

**non chiffrable**

structure, avec la donnée qui verrouille la porte de secours. Le simulateur n'a aucun instrument de fiscalité locale : ni taxe foncière, ni CFE, ni taxe d'habitation sur les résidences secondaires, ni TEOM (grep sur src/ ne trouve aucune de ces bases, et aucun knob ménage ou firm ne les touche — l'IFI est la seule fiscalité du patrimoine modélisée, et elle porte sur la valeur vénale, pas sur la valeur locative cadastrale). Même si l'instrument existait, la donnée manquerait : la population ne porte ni valeurs locatives cadastrales ni patrimoine immobilier localisé, et KNOWN_LIMITATIONS acte « No capital income, no property income ». Enfin l'article agit sur des bases d'imposition d'impositions affectées aux collectivités, ce qui est en dehors du périmètre déclaré du projet.

### Article 28 — procédure — facturation électronique (TVA)

*Modification des obligations des assujettis en matière de facturation électronique et de transmission électron*

**non chiffrable**

scope. C'est de la procédure déclarative pure et de la sanction : aucune assiette, aucun taux, aucun barème n'est modifié. Le cas est même l'exemple canonique donné dans la consigne (« obligations de facturation électronique »). Accessoirement le modèle n'a pas non plus de TVA ni d'obligation déclarative comme objet, donc il n'y a rien à bouger même à titre indicatif. Le rendement éventuel de la facturation électronique passe par un effet d'observance que ce projet ne modélise pas — il n'existe pas de canal comportemental d'observance dans src/impots/behavioural/channels.py.

### Article 29 — procédure — gestion fiscale (avec option barème/PFU sur revenus du cap

*Modernisation et simplification de la gestion fiscale*

**non chiffrable**

data pour la seule disposition chiffrable, scope pour tout le reste. La suppression du caractère irrévocable de l'option de l'article 200 A a un coût : elle laisse des contribuables revenir sur un choix devenu défavorable, donc elle a la valeur d'une option. Le chiffrer supposerait (i) des revenus de capitaux mobiliers et des plus-values dans la population et (ii) un modèle du choix barème/PFU. Aucun des deux n'existe : KNOWN_LIMITATIONS acte « No capital income, no property income. The top of the distribution is a construction; nothing above roughly the 95th percentile is publishable », et il n'y a aucun canal d'optimisation d'option dans channels.py. Le PFU n'est de toute façon pas un knob (ir_bareme ne pilote que le barème progressif). Les autres mesures (dématérialisation, modes de notification, moyens de paiement, ordonnance, recouvrement) sont de la procédure pure, hors périmètre. 

### Article 30 — droits de timbre et taxes sur titres

*Diverses majorations de droits de timbre*

**non chiffrable**

structure. Aucun droit de timbre n'existe dans le modèle — ni taxe de séjour, ni droit de naturalisation, ni taxe sur le permis de conduire, ni contribution pour l'aide juridique — au même titre que le tabac, les redevances des agences de l'eau ou les taxes sur les véhicules cités comme exemples de refus structurel. Les assiettes sont d'ailleurs des ÉVÉNEMENTS administratifs (une demande de titre, une instance introduite) et non des grandeurs portées par la population : celle-ci ne contient ni statut de séjour, ni recours contentieux, ni échange de permis. Il n'y a donc rien à câbler à la semaine de publication ; ce serait un instrument nouveau à construire de bout en bout, avec sa propre source de comptage administratif.

## Ce qu'il faut en faire en octobre

Lire les articles publiés, rattacher chacun à une catégorie ci-dessus, prendre la
case. Là où le texte 2027 porte une catégorie absente d'ici, c'est une décision de
triage **nouvelle** : la prendre, l'écrire, et dire qu'elle a été prise le jour même
et non d'avance. La différence compte : un refus préenregistré est une limite, un
refus improvisé est une excuse.

## Le PLF 2027 réel — triage du 2026-10-02

> Assemblée nationale, texte n° 3210 (17e législature), projet de loi de finances pour 2027, déposé le 1er octobre 2026, articles avec exposé des motifs. Manifesté : plf2027_texte_an_b3210.html, sha256 7fcd191974d8. La section fiscale porte les articles 1 à 33.

**33 articles fiscaux, 3 chiffrables** (art. 2, 3, 15). **17 décisions sont neuves**, prises le jour de parution sur des catégories que septembre n'avait pas vues ; les 16 autres reprennent une catégorie du triage préenregistré, à la lettre, et un test le vérifie.

Ce triage n'a lu aucun montant de l'annexe des évaluations préalables : il a été
pris avant le commit des enregistrements (runbook, étape 5). Les montants viennent
après, dans « Le PLF 2027 en euros ».

| art. | intitulé | catégorie | case | décision |
|---|---|---|---|---|
| 1 | Autorisation de percevoir les impôts existants | formalité annuelle (autorisation de percevoi | non chiffrable | neuve |
| 2 | Soutenir le travail en revalorisant le barème de l'impôt sur | IR — revalorisation du barème | **chiffrable** | neuve |
| 3 | Réduction à 3 000 € du plafond de l'abattement d'impôt sur l | abattement IR sur pensions | **chiffrable** | septembre |
| 4 | Mesure temporaire d'allègement de la fiscalité des donations | DMTG — donations | non chiffrable | neuve |
| 5 | Recentrage du dispositif de l'apport-cession sur son objecti | plus-values en report d'imposition (apport-c | non chiffrable | neuve |
| 6 | Protection du modèle de l'assurance-vie | fiscalité de l'assurance-vie | non chiffrable | neuve |
| 7 | Réorienter les soutiens publics vers le logement familial et | logement — prêt à taux zéro et location meub | non chiffrable | neuve |
| 8 | Soutien au logement social | fiscalité locale — valeurs locatives (TFPB,  | non chiffrable | septembre |
| 9 | Soutien à l'industrie | IS — suramortissements et incitations à l'in | non chiffrable | neuve |
| 10 | Soutien aux reprises d'entreprises (pacte « Papin ») | transmission et reprise d'entreprises | non chiffrable | neuve |
| 11 | Prorogation d'un an de l'application du crédit d'impôt pour  | crédits d'impôt territoriaux (outre-mer) | non chiffrable | neuve |
| 12 | Soutien au secteur culturel | taxe sectorielle numérique / audiovisuel (as | non chiffrable | septembre |
| 13 | Soutien au secteur agricole | fiscalité agricole (BA / IS agricole / DMTG) | non chiffrable | septembre |
| 14 | Soutien aux entreprises touchées par les incendies de l'été  | soutien conjoncturel après sinistre | non chiffrable | neuve |
| 15 | Mise à contribution des grandes entreprises | IS contribution exceptionnelle (CEBGE) | **chiffrable** | septembre |
| 16 | Rationalisation des taux de taxe sur la valeur ajoutée appli | TVA — taux applicables à des services | non chiffrable | neuve |
| 17 | Ajustements sur les taxes sur les réductions de capital | taxe sur les réductions de capital | non chiffrable | neuve |
| 18 | Aménagement du régime des provisions assurantielles | IS — provisions des entreprises d'assurance | non chiffrable | neuve |
| 19 | Mesures diverses de correction, clarification et coordinatio | fiscalité sectorielle et procédure fiscale | non chiffrable | septembre |
| 20 | Création de tarifs réduits de taxes sur les installations nu | IFER / imposition forfaitaire de production  | non chiffrable | septembre |
| 21 | Adaptation de la fiscalité aérienne au soutien à la continui | fiscalité du transport aérien | non chiffrable | neuve |
| 22 | Renforcement de la taxe sur l'exploitation des infrastructur | taxe sur les infrastructures de transport de | non chiffrable | neuve |
| 23 | Instauration d'un prélèvement exceptionnel sur les avoirs en | prélèvement sur avoirs en déshérence | non chiffrable | neuve |
| 24 | Soutien à l'électrification et renforcement des incitations  | fiscalité énergie (incorporation de biocarbu | non chiffrable | septembre |
| 25 | Mesures relatives à la fiscalité des véhicules | fiscalité des véhicules (malus CO2, malus ma | non chiffrable | septembre |
| 26 | Prorogations d'exonérations et précisions en matière de fisc | dispositif fiscal zoné (QPV / ZFU) — IS-IR,  | non chiffrable | septembre |
| 27 | Mesures relatives au financement du service public de la jus | droits de timbre et taxes sur titres | non chiffrable | septembre |
| 28 | Mise à jour de références au droit de l'Union européenne dan | fiscalité sectorielle et procédure fiscale | non chiffrable | septembre |
| 29 | Nouvelle étape de la relation de confiance | procédure — gestion fiscale (avec option bar | non chiffrable | septembre |
| 30 | Renforcement de la lutte contre la fraude fiscale et mesures | procédure — gestion fiscale (avec option bar | non chiffrable | septembre |
| 31 | Modernisation et simplification des procédures fiscales | procédure — gestion fiscale (avec option bar | non chiffrable | septembre |
| 32 | Sécurisation et amélioration de la lisibilité de dispositifs | fiscalité douanière / importations | non chiffrable | septembre |
| 33 | Modalités d'entrée en vigueur des mesures fiscales | formalité annuelle (entrée en vigueur) | non chiffrable | neuve |

### Article 2 — IR — revalorisation du barème

*Soutenir le travail en revalorisant le barème de l'impôt sur le revenu grâce à un traitement fiscal équivalent des différents types de revenus*

****chiffrable**** · chaîne ménages · boutons `ir_bareme`, `decote_seuil_celib`, `decote_seuil_couple`, `plafond_qf_demi_part` · réforme `reforms/plf2027_art_2.json`

Le volet revalorisation — 2,1 % sur les tranches, la décote et le plafond général de la demi-part — s'écrit avec quatre boutons existants, contre un arbre qui gèle en 2026 les paramètres des revenus 2025 : il n'y a donc pas de zéro confiant à craindre. Ne sont PAS chiffrés : les quatre autres plafonds de quotient familial, le 196 B et l'indexation des limites de déductions (structure : aucun bouton), ni les volets indemnités de rupture, indemnités journalières ALD et AT/MP, prime carburant et taux de CSG des IJ (data : la population n'a ni indemnité de rupture ni IJ). À comparer au seul volet revalorisation si l'annexe le sépare.

### Article 3 — abattement IR sur pensions

*Réduction à 3 000 € du plafond de l'abattement d'impôt sur le revenu en faveur des bénéficiaires de pensions de retraite*

****chiffrable**** · chaîne ménages · boutons `abattement_pensions_plafond` · réforme `reforms/plf2027_art_3.json`

Petit bouton en septembre, câblé le 2026-10-02 (abattement_pensions_plafond, chemin abatpen.max) et vu bouger sur un retraité. Le sous-plafond de l'article ne vise que les pensions de retraite ; le bouton déplace le plafond commun, ce qui est exact sur cette population, dont la seule pension est une retraite.

### Article 15 — IS contribution exceptionnelle (CEBGE)

*Mise à contribution des grandes entreprises*

****chiffrable**** · chaîne entreprises · boutons `cebge_seuils_et_taux`, `cebge_prorogation_largeur` · réforme `reforms/plf2027_art_15.json`

Chiffrable dès septembre, mais le jour J a montré deux trous, comblés le 2026-10-02 : l'arbre éteint la CEBGE après 2026 et le curseur refuse, à raison, d'écrire une année éteinte (prorogation par création délibérée, largeur de lissage prise dans le texte) ; et le registre n'enregistrait que des scénarios ménages (`chiffrage register-entreprises`). Le volet transport maritime (II) n'est pas chiffré : aucune entreprise de transport maritime n'est identifiable sous la section NAF.

## Le PLF 2027 en euros

> PLF 2027, évaluations préalables des articles (743 p.), annexe au projet de loi n° 3210. Manifesté : plf2027_evaluations_prealables.pdf, sha256 b1142977a5e3. La page citée est celle du PDF, qui est la page imprimée.

Sur les **16 624 M EUR** d'effort de 2027 que l'annexe quantifie, l'outil en chiffre **10 600 M EUR**, soit **63,8 %** ; et **3 articles sur 33**, soit 9,1 %. **9,1 % des articles, 63,8 % des euros.** Comme en 2026, les deux chiffres disent le contraire l'un de l'autre, et c'est pourquoi ils vont ensemble.

La règle qui dit quel montant compte a été écrite avant la lecture (D-293) : l'effet budgétaire de 2027 de la section 4.2 de chaque fiche, en valeur absolue, volet par volet ; un montant sans année déterminable, « non chiffrable » ou donné par un seul côté (majorant, minorant, maximum) sort du dénominateur ; un volet qui commence après 2027 vaut zéro. Le numérateur ne prend que les volets que l'outil chiffre : il dit « chiffré », pas « retrouvé », et l'écart de chacun à l'annexe est dans `reports/chiffrages_preregistres.md`.

Si chaque montant écrit que la règle sort entrait au dénominateur, la part serait de 62,0 %, 1,8 point de moins : la règle la flatte de cela, puisqu'aucun de ces montants n'est un volet chiffré.

### Les portes, de celle qui rapporterait le plus à celle qui ne rapporterait rien

Chaque article refusé reçoit la porte qui l'ouvrirait, selon la raison de son triage (D-293) ; un article à plusieurs volets y va tout entier.

| porte | ce qui l'ouvrirait | articles | euros de 2027 | hors du dénominateur |
|---|---|---|---|---|
| `secteur` | l'assiette d'un secteur hors du modèle : audiovisuel, nucléaire, aérien, infrastructures, dépôts, justice | 12, 20, 21, 22, 23, 27 | 2 239 M EUR | 20 |
| `donnee_menages` | une donnée des ménages : plus-values, épargne, logement | 5, 6, 7 | 785 M EUR | — |
| `consommation` | la consommation et le parc : TVA par taux, accises, véhicules | 16, 19, 24, 25, 32 | 373 M EUR | — |
| `dimension_entreprises` | une dimension des entreprises : territoire, département, secteur agricole | 11, 13, 14 | 234 M EUR | — |
| `transmission` | un module de transmission : donations et reprises | 4, 10 | 67 M EUR | 4 |
| `hors_champ` | rien : une formalité ou une procédure | 1, 28, 29, 30, 31, 33 | 0 M EUR | 1, 30 |
| `bilan_entreprises` | le bilan des entreprises : investissement, amortissement, provisions, capital | 9, 17, 18 | 0 M EUR | 17, 18 |
| `bases_locales` | les bases locales : foncier, logement social, zonage | 8, 26 | 0 M EUR | — |

Restent, dans les articles chiffrés, **2 325 M EUR** de volets que l'outil ne chiffre pas : art. 2, volet 4.2.1.3, 820 M EUR ; art. 2, volet 4.2.1.4 (IR), 965 M EUR ; art. 2, volet 4.2.1.4 (CSG), 540 M EUR. Le triage de leur article dit déjà ce qui leur manque.

### Les articles qui sortent du dénominateur

* **Art. 1** — pas de fiche dans l'annexe.
* **Art. 4** — « non chiffrable » : l'annexe le dit elle-même (règle 5).
* **Art. 17** — « non chiffrable » : l'annexe le dit elle-même (règle 5).
* **Art. 18** — « non chiffrable » : l'annexe le dit elle-même (règle 5).
* **Art. 20** — un maximum : un montant donné par un seul côté (règle 6).
* **Art. 30** — « non chiffrable » : l'annexe le dit elle-même (règle 5).

### Le relevé, ligne par ligne

| art. | volet | 2027 (M EUR) | p. | citation | lecture |
|---|---|---|---|---|---|
| 2 | 4.2.1.1 | **4 200** (chiffré) | 29 | « le rendement de l’IR aurait été majoré d’environ 4,2 Md€ en 2027 » |  |
| 2 | 4.2.1.2 | hors | 29 | « La mesure présente un coût majorant pour l’État de 20 M€ en 2027 » | un majorant : un montant donné par un seul côté (règle 6) |
| 2 | 4.2.1.3 | 820 | 29 | « La mesure présente un gain total de 820 M€ en 2027 » |  |
| 2 | 4.2.1.4 (IR) | 965 | 30 | « en 2027, de 965 M€, dont 450 M€ au titre des ALD et 515 M€ au titre des AT/MP » | l'effet de 2027 avec le PAS, que la fiche donne, et non les 620 M€ de l'année pleine |
| 2 | 4.2.1.4 (CSG) | 540 | 30 | « générerait de l’ordre de 540 M€ de recettes supplémentaires pour les administrations de sécurité sociale pour 2027 » |  |
| 3 | — | **1 400** (chiffré) | 36 | « Cette mesure entraîne un gain budgétaire estimé à 1,4 Md€ en 2027 » |  |
| 4 | — | hors | 41 | « La mesure présente pour l’État un coût non chiffrable en 2027. » | « non chiffrable » : l'annexe le dit elle-même (règle 5) |
| 5 | — | 500 | 46 | « On estime le rendement budgétaire pour la première année d’impact, en 2027, à 500 M€ » |  |
| 6 | — | 25 | 53 | « Total pour l’ensemble des APU +25 +50 +50 » |  |
| 7 | 4.2.1.1 (plafond) | 0 | 62 | « La mesure de suppression du plafond annuel de dépense fiscale n’emporte pas, à elle seule, de surcoût budgétaire immédiat » | aucun surcoût immédiat |
| 7 | 4.2.1.1 (PTZ parentalité) | 0 | 62 | « La mesure de création d’un PTZ « parentalité » devrait avoir un coût générationnel de 466 M€ » | premier effet en 2028 : une génération de prêts coûte à partir de l'année qui suit son émission (« année n+1 » ; la génération 2025 du § 4.3 ne coûte rien en 2025), et la première génération est celle de 2027, la mesure entrant en vigueur avec la loi de finances pour 2027 (§ 6.3) |
| 7 | 4.2.1.2 | 260 | 62 | « Le gain attendu en impôt sur le revenu est évalué à 260 M€ en 2027 » |  |
| 8 | 4.2.1.1 | 0 | 72 | « L’impact budgétaire de la mesure débutera en 2043 » | premier effet en 2043 (règle 2) |
| 8 | 4.2.1.2 | hors | 73 | « L’impact budgétaire de la mesure n’est pas chiffrable. » | « non chiffrable » : l'annexe le dit elle-même (règle 5) |
| 9 | suramortissement « industrie 4.0 » | 0 | 89 | « 0 M€ en 2027 et 6,7 M€ en 2028 » |  |
| 9 | C3IV | 0 | 89 | « décaissements limités à 0 M€ en 2027 et 6 M€ en 2028 » |  |
| 10 | — | 67 | 102 | « Total pour l’ensemble des APU -67 -73 -74 -76 » |  |
| 11 | — | 0 | 107 | « Le coût budgétaire de la mesure est nul en 2027 » |  |
| 12 | 4.2.1.1 | 0 | 122 | « La chronique de coût de cette mesure (prorogation triennale de 6 dépenses fiscales) est la suivante » | la chronique commence en 2028 : premier effet après 2027 (règle 2) |
| 12 | 4.2.1.2 | hors | 122 | « Ce chiffrage peut dès lors être perçu comme minorant. » | un minorant, les 35 M€ du tableau de 2027 : un montant donné par un seul côté (règle 6) |
| 13 | 4.2.1.1 | 33 | 140 | « Le rendement de la mesure est évalué à 33 M€ en 2027. » |  |
| 13 | 4.2.1.2 | 0 | 140 | « Total pour l’ensemble des APU 0 -4.7 -11 » |  |
| 13 | 4.2.1.3 | 1 | 141 | « entraîne un coût annuel pour l’État de 1 M€ en 2027 » |  |
| 13 | 4.2.1.4 | 0 | 141 | « entraîne un coût annuel pour l’État de 13 M€ en 2028 » | premier effet en 2028 (règle 2) |
| 13 | 4.2.1.5 | 0,1 | 141 | « entraîne un coût pour l’État annuel de 0,1 M€ à partir de 2027 » |  |
| 14 | TSCA | 200 | 152 | « La hausse du taux de TSCA de 18 % à 18,9 % est estimée à +200 M€ pour l’État. » | le tableau la place en 2027 |
| 14 | taxe foncière | hors | 152 | « il s’agit d’un coût non chiffrable » | « non chiffrable » : l'annexe le dit elle-même (règle 5) |
| 14 | CFE | 0 | 152 | « Concernant la CFE, le coût budgétaire est estimé en ordre de grandeur à 21 M€. » | le tableau le place en 2026 : rien en 2027 |
| 15 | I | **5 000** (chiffré) | 160 | « 5 Md€ au titre des acomptes attendus en 2027 » |  |
| 15 | II | hors | 160 | « entreprises de transport maritime est de 0,3 Md€ » | aucune année : année indéterminable (règle 5) |
| 16 | — | 304 | 165 | « Total pour l’ensemble des APU 304 333 333 +335 » |  |
| 17 | — | hors | 171 | « L’impact budgétaire de la mesure n’est pas chiffrable. » | « non chiffrable » : l'annexe le dit elle-même (règle 5) |
| 18 | — | hors | 179 | « La mesure présente une incidence non chiffrable. » | « non chiffrable » : l'annexe le dit elle-même (règle 5) |
| 19 | — | 31 | 195 | « La prorogation de la dépense fiscale n° 800119 engendre un coût de 31 M€ à compter de 2027. » |  |
| 20 | — | hors | 202 | « est estimé, au maximum, à 37 M€ au titre de l’année 2026 et à 39,5 M€ au titre de l’année 2027 » | un maximum : un montant donné par un seul côté (règle 6) |
| 21 | sûreté des aérodromes | hors | 217 | « induisent un rendement supplémentaire maximal d’environ 53 M€ » | un maximum, sans année : un montant donné par un seul côté (règle 6) |
| 21 | Strasbourg-Entzheim | 3,8 | 217 | « le coût prévisionnel annuel est estimé à 3,8 M€ » | un coût annuel : l'année pleine vaut pour 2027 (règle 2) |
| 22 | — | 800 | 222 | « La mesure entraîne une augmentation estimée du produit annuel de la TEITLD de 800 M€ » | le tableau la place en 2027 |
| 23 | — | 1 400 | 229 | « Le montant prévisionnel du gain est d’1,4 Md€ pour 2027. » |  |
| 24 | 4.2.1.1 | hors | 255 | « Prorogation de la taxe incitative relative à l’utilisation d’énergie renouvelable dans les transports Mesure non chiffrable. » | « non chiffrable » : l'annexe le dit elle-même (règle 5) |
| 24 | 4.2.1.2 | 0,3 | 255 | « État -0,3 -0,3 -0,3 » |  |
| 24 | 4.2.1.3 | 16 | 256 | « État -16 -25 -40 » |  |
| 24 | 4.2.1.4 | 0 | 256 | « génère des revenus de l’ordre de 200 M€ sur 2030 » | premier effet en 2030 (règle 2) |
| 25 | 4.2.1.1 | hors | 272 | « Un gain non chiffrable peut être retenu sur cette mesure. » | « non chiffrable » : l'annexe le dit elle-même (règle 5) |
| 25 | 4.2.1.2 | hors | 272 | « elle ne peut-être chiffrée » | « non chiffrable » : l'annexe le dit elle-même (règle 5) |
| 25 | 4.2.1.3 | 22 | 272 | « Le coût annuel de la mesure afférente au malus masse est évalué à 22 M€ à compter de 2027. » |  |
| 26 | 4.2.1.1 (État) | hors | 290 | « Ce risque indemnitaire est difficilement chiffrable » | « non chiffrable » : l'annexe le dit elle-même (règle 5) |
| 26 | 4.2.1.1 (communes) | 0 | 290 | « la mesure est neutre financièrement » |  |
| 26 | 4.2.1.2 (BUD et ZDP) | 0 | 290 | « le coût pour l’État est estimé à moins de 2 M€ répartis entre 2028 et 2037 » | premier effet en 2028 (règle 2) |
| 26 | 4.2.1.2 (ZRCV) | hors | 290 | « le coût pour les collectivités n’est pas connu » | « pas connu » : non chiffrable (règle 5) |
| 26 | 4.2.1.3 | 0 | 290 | « Elle est donc sans incidence (SI) sur les recettes fiscales. » |  |
| 27 | — | 35,4 | 302 | « Total pour l’ensemble des APU +35,4 +85,15 +85,15 +205,7 » |  |
| 28 | 4.2.1.1 | hors | 319 | « La mesure présente un gain non chiffrable (majorant 32 M€). » | « non chiffrable » : l'annexe le dit elle-même (règle 5) |
| 28 | 4.2.1.2 | 0 | 319 | « Sur la définition du champ du régime d’imposition des crypto-actifs Aucune. » |  |
| 28 | 4.2.1.3 | hors | 319 | « La mesure présente un coût non chiffrable à compter de 2027 pour l’État » | « non chiffrable » : l'annexe le dit elle-même (règle 5) |
| 28 | 4.2.1.4 | 0 | 319 | « exploitées selon le mode de production biologique Aucune. » |  |
| 29 | — | 0 | 324 | « Incidences budgétaires (coûts/économies nets de la mesure proposée) Sans incidence. » |  |
| 30 | — | hors | 351 | « Les mesures présentent une incidence non chiffrable. » | « non chiffrable » : l'annexe le dit elle-même (règle 5) |
| 31 | 4.2.1.1 | hors | 363 | « La perte budgétaire en retenue à la source (RAS) sera négligeable (inférieure à 0,3 M€) à compter de 2027. » | « inférieure à » : un montant donné par un seul côté (règle 6) |
| 31 | 4.2.1.2 | 0 | 363 | « Remise des fichiers des écritures comptables et des résultats des traitements informatiques Sans objet. » |  |
| 31 | 4.2.1.3 | hors | 363 | « permet à terme d’envisager une économie de 1 M€ » | « à terme » : année indéterminable (règle 5) |
| 31 | 4.2.1.4 | hors | 364 | « Économie estimée pour 3 294 892 avis de 6 pages : 2 391 762 €. » | aucune année : année indéterminable (règle 5) |
| 32 | — | 0 | 376 | « Incidences budgétaires (coûts/économies nets de la mesure proposée) Sans objet. » |  |
| 33 | — | 0 | 382 | « Incidences budgétaires (coûts/économies nets de la mesure proposée) Sans objet. » |  |
