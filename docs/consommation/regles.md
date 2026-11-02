# Les règles : de la dépense par poste à la TVA et aux accises (but 12)

Rédigé le 2 novembre 2026 pour le but 12 (`docs/BUT.md`, section « But 12 »). C'est un
document de préparation : aucun code, aucune passe, aucun chiffrage. Il dit quelles règles
transforment une dépense de consommation par poste en TVA et en accises, avec leur source et
leur date. Quand une chose n'a pas été trouvée, il l'écrit. Les sources de données (les
tableaux de l'INSEE, les agrégats) sont décrites dans `sources.md`, que rédige un autre
agent. Les fichiers lus pour écrire celui-ci (TM106, fichiers
d'openfisca-france-indirect-taxation, circulaire des douanes, guide du ministère, prix de la
DGEC) n'entrent pas dans le dépôt.

Le champ est la France métropolitaine. La Corse et les DOM ont d'autres taux (§ 2.3).

## Ce qu'il faut retenir

1. **Le niveau de détail.** Le tableau TM106 de l'enquête Budget de famille 2017 (dépenses
   par décile de niveau de vie) publie 146 postes feuilles : 138 de consommation (divisions
   01 à 12) et 8 hors champ (division 13). Ce sont des codes à 5 positions, dont 52 sont des
   agrégats marqués d'une lettre (`0114A`, `022ZZ`…). La table du § 3 les couvre tous.
2. **La table est complète au niveau publié, mais pas univoque.** En pondérant par la
   dépense moyenne de 2017 : 90 postes ont un seul taux non nul (48,7 % de la dépense), 19
   sont exonérés ou hors TVA (18,2 %), 29 mêlent plusieurs taux, relèvent d'un régime de
   marge ou ont un contenu non décrit (33,0 %). Aucune clé de répartition publiée n'a été
   trouvée pour les postes mixtes.
3. **Les accises de 2026** ont changé deux fois dans l'année pour l'électricité, le gaz et
   les combustibles (1er février, 1er août) ; les carburants n'ont pas bougé depuis le 1er
   août 2025 (§ 5). La TVA se calcule sur le prix accise comprise (§ 8).
4. **openfisca-france** (176.0.8, installé) porte les quatre taux de TVA, justes en 2026,
   mais ses accises s'arrêtent en 2018 (carburants), 2016 (électricité) et 2021 (gaz), et
   aucune variable ne les lit (§ 6).
5. **openfisca-france-indirect-taxation** vit encore (dernier commit le 11 mars 2026), sous
   AGPL-3.0. Sa table poste → taux s'arrête en 2024 et diverge de la loi de 2026 sur une
   dizaine de postes. Elle se reprend dans un projet AGPL-3.0-or-later, notices conservées
   (§ 7).

## 1. Le niveau de détail publié par l'INSEE

* Publication : « Les dépenses des ménages en France métropolitaine en 2017 », Enquête
  Budget de famille, Insee Résultats, <https://www.insee.fr/fr/statistiques/4648319>.
  Tableau TM106 « Dépenses annuelles moyennes selon le niveau de vie » (`TM106.csv`),
  indicateur `CONSO` (dépense annuelle moyenne en euros), par `DECUC` (déciles 1 à 10 et
  ensemble). Nomenclature `NOMENCLATURE` décrite dans `metadonnees_bdf2017.csv`.
* La nomenclature va jusqu'à 5 positions (division, groupe, classe, sous-classe). Quand une
  sous-classe n'est pas publiable seule, l'INSEE publie un agrégat suffixé `A`, `B` ou `Z`.
  La colonne « € 2017 » de la table est la dépense moyenne de l'ensemble des ménages.
* Le code à 5 positions de l'INSEE est le `Code_sous_classe` de la table
  `bdf_2017_legislation.csv` d'openfisca-france-indirect-taxation : 94 feuilles s'y
  rapportent directement ; les 52 agrégats ont été rattachés aux sous-classes qu'ils
  semblent contenir, par leur libellé. Ce rattachement n'est pas documenté par l'INSEE ; il
  est marqué `?` quand il est douteux.
* Sous-classes de la nomenclature détaillée **absentes** de TM106 : 04321 (services
  d'entretien du logement), 04411 (redevance d'ordures ménagères), 04421 (assainissement),
  04551 (chauffage urbain), 04552 (glace), 04541 hors de `045AZ`. Les totaux de groupe (043
  = 0431, 044 = 0443 + 0444, 045 = somme des feuilles) suggèrent qu'elles sont fondues dans
  `0431Z`, `04431` ou `045AZ`, ou non publiées. **Non trouvé** dans la documentation.

## 2. Les taux de TVA en 2026

### 2.1 Les cinq taux et leurs articles

| Taux | Article de base | Nœud openfisca-france (valeur, depuis) |
|---|---|---|
| 20 % normal | CGI art. 278 | `taxation_indirecte.tva.taux_normal` (0,20, 2014-01-01) |
| 10 % intermédiaire | CGI art. 279, 279-0 bis, 278 bis, 278 quater, 298 octies | `taux_intermediaire` (0,10, 2014-01-01) |
| 5,5 % réduit | CGI art. 278-0 bis (A à P), 278-0 bis A | `taux_reduit` (0,055, 1982-07-01) |
| 2,1 % particulier | CGI art. 281 octies, 281 quater, 298 septies | `taux_particulier_super_reduit` (0,021, 1986-07-01) |
| exonéré | CGI art. 261 (4, 7), 261 C, 261 D, 261 E, 262 | — |

* Hors champ (pas de TVA, sans exonération) : personnes publiques pour leurs services
  administratifs, sociaux, éducatifs (CGI art. 256 B) ; salaires (emploi direct à
  domicile) ; ventes entre particuliers.
* Régimes de marge : biens d'occasion vendus par un professionnel (CGI art. 297 A, TVA sur
  la marge) ; agences de voyages (TVA sur la marge, CGI art. 266, 1, e, **à vérifier**). Le
  taux effectif sur la dépense y est bien inférieur au taux légal.
* Le BOFiP rappelle que le 5,5 % des services est **limitatif** (lettres B à L de
  l'art. 278-0 bis et art. 278-0 bis A) et que le 10 % des services relève des art. 279,
  279-0 bis et 298 octies : BOI-TVA-LIQ-30-20, version du 26 août 2026.
* Texte de l'art. 278-0 bis en vigueur depuis le 1er mars 2026 (modifié par la loi
  n° 2026-103 du 19 février 2026 de finances pour 2026, art. 81) :
  <https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000053562844/2026-03-01>. Art.
  279 en vigueur depuis le 1er mars 2026 :
  <https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000053562872/2026-03-01>. Art.
  278-0 bis A en vigueur depuis le 21 février 2026 :
  <https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000053545596/2026-02-21>. Art.
  279-0 bis :
  <https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000051215062/2025-03-01>.
* **Recodification au 1er janvier 2027.** Légifrance porte, sur ces articles, l'abrogation
  par l'ordonnance n° 2025-1247 du 17 décembre 2025 (art. 9) à compter du 1er janvier 2027 :
  la TVA passe dans le code des impositions sur les biens et services. Les références de ce
  document changeront donc en 2027 ; l'ordonnance ne change pas les taux d'après ce qui a
  été lu, mais cela n'a pas été vérifié article par article.

### 2.2 Légende des références de la table

* `[278]` CGI art. 278 (20 %). `[A1]` CGI art. 278-0 bis, A, 1° : alimentation humaine à
  5,5 %, sauf confiserie, chocolat et produits contenant du chocolat ou du cacao (le
  chocolat, le chocolat de ménage au lait, les bonbons de chocolat, les fèves et le beurre
  de cacao restent à 5,5 %), margarines et graisses végétales, caviar, boissons alcooliques,
  qui sont à 20 %. Doctrine : BOI-TVA-LIQ-30-10-10, version du 19 novembre 2025 (les
  paragraphes cités, `§`, sont les siens).
* `[A 1° bis]`, `[A 1° ter]`, `[A 2°]`, `[A 3°]` : protections hygiéniques, préservatifs,
  appareillages pour handicapés, livres (CGI art. 278-0 bis, A). Les lunettes et les
  lentilles n'en sont pas : BOI-TVA-LIQ-30-10-50, version du 19 juin 2024.
* `[B]` … `[P]` : lettres de l'art. 278-0 bis (5,5 %) — B réseaux de chaleur (abonnement,
  chaleur produite à 50 % au moins d'énergies renouvelables ou de récupération), B bis
  froid, C hébergement en établissement pour personnes âgées ou handicapées, D services aux
  personnes âgées ou handicapées, E repas dans les écoles, F spectacles, G cinéma, J
  spectacles sportifs, L zoos, M déchets ménagers, N bornes de recharge, O équitation, P
  photovoltaïque jusqu'à 9 kWc.
* `[279 x]` : lettre x de l'art. 279 (10 %) — a hébergement, a bis cantines d'entreprise, a
  quinquies thermalisme, b assainissement, b quater transport de voyageurs, b octies
  abonnements de télévision, b nonies droits d'admission, i services à la personne, m vente
  à consommer sur place, n vente à emporter pour consommation immédiate. Les boissons
  alcooliques en restent exclues (20 %).
* `[279-0 bis]` travaux dans un logement de plus de deux ans (10 %) ; `[278-0 bis A]`
  rénovation énergétique (5,5 %) ; `[278 bis 3° bis]` bois de chauffage (10 %,
  BOI-TVA-LIQ-30-10-35) ; `[278 quater]` médicaments non remboursables (10 %) ;
  `[281 octies]` médicaments remboursables (2,1 %, BOI-TVA-LIQ-40-10, 27 novembre 2024) ;
  `[281 quater]` 140 premières représentations (2,1 %, BOI-TVA-LIQ-40-20) ; `[298 septies]`
  publications de presse et services de presse en ligne inscrits à la CPPAP (2,1 %,
  BOI-TVA-SECT-40-10-10 et BOI-TVA-SECT-40-40).
* Exonérations : `[261 4 1°]` soins des professions médicales et paramédicales
  (BOI-TVA-CHAMP-30-10-20-10, 9 avril 2025) ; `[261 4 4°]` enseignement, cantines des
  établissements, cours particuliers (a, b ; BOI-TVA-CHAMP-30-10-20-50) ; `[261 7 1°]`
  organismes sans but lucratif ; `[261 C 1°]` services financiers ; `[261 C 2°]` assurances
  (BOI-TVA-CHAMP-30-10-70, 24 juillet 2024) ; `[261 D]` locations de logements nus (2°) ou
  meublés d'habitation (4°) ; `[261 E]` jeux de casino et loteries (paris en ligne : non
  vérifié) ; `[262 II 8°]` transport aérien international de voyageurs
  (BOI-TVA-CHAMP-20-60-10, 24 juillet 2024). L'alinéa exact de l'exonération du service
  universel postal (art. 261, 4) n'a **pas été vérifié**.

### 2.3 Corse et outre-mer

* Corse : produits pétroliers à 13 % (CGI art. 297, I, 1°) ; la loi de finances pour 2025
  (art. 20, VIII) prévoit son alignement sur 20 % à une date fixée par décret (guide 2026 de
  la fiscalité des énergies, § I.1). Les autres taux corses ne sont pas repris ici.
* Guadeloupe, Martinique, La Réunion : taux normal 8,5 %, taux réduit 2,1 % (CGI art. 296,
  rappelé par la circulaire des douanes du 30 septembre 2026, renvoi 63002) ; pas de TVA sur
  les produits pétroliers outre-mer (CGI art. 295, 1, 6°, même circulaire). Guyane et
  Mayotte : **non vérifié**.

## 3. La table poste → taux de TVA (2026)

Une ligne par feuille de TM106. « € 2017 » : dépense annuelle moyenne par ménage (TM106,
ensemble). « TVA 2026 et référence » : le ou les taux en vigueur au 1er novembre 2026, avec
l'article (légende au § 2.2) ; `MIXTE` signale un poste qui mêle plusieurs taux, `MARGE` un
régime de marge, `INDÉTERMINÉ` un poste dont le contenu n'est pas décrit. « OF-IT » : la
catégorie que donne openfisca-france-indirect-taxation (`bdf_2017_legislation.csv`, période
qui se termine en 2024) à la feuille ou à ses sous-classes (`code:taux`, `—` = aucune
catégorie, `?` = rattachement supposé). Les accises dues en plus de la TVA sont au § 5.

| Code | Poste (libellé INSEE) | € 2017 | TVA 2026 et référence | OF-IT |
|---|---|--:|---|---|
| 01111 | Riz sous toutes ses formes et produits à base de riz | 29 | 5,5 [A1] | 5,5 |
| 01112 | Pain et autres produits de boulangerie et de viennoiserie yc biscui… | 498 | 5,5 [A1 ; BOFiP §210 : biscuits et viennoiseries à 50 % de chocolat au plus] | 5,5 |
| 01113 | Pâtes alimentaires sous toutes leurs formes et plats à base de pâtes | 62 | 5,5 [A1] | 5,5 |
| 01114 | Préparations telles que pâte à pâtisser, gâteau industriel, tarte,… | 146 | 5,5 [A1] ; 10 si vendu pour consommation immédiate [279 n] | 5,5 |
| 01115 | Autres céréales et produits à base de céréales yc farine, semoule,… | 54 | 5,5 [A1] | 5,5 |
| 01121 | Viande bovine fraîche ou surgelée | 258 | 5,5 [A1] | 5,5 |
| 01122 | Viande porcine fraîche ou surgelée | 75 | 5,5 [A1] | 5,5 |
| 01123 | Viande ovine ou caprine fraîche ou surgelée | 32 | 5,5 [A1] | 5,5 |
| 01124 | Viande de volaille fraîche ou surgelée | 158 | 5,5 [A1] | 5,5 |
| 01125 | Viande séchée salée ou fumée, charcuterie et abats, frais ou surgel… | 318 | 5,5 [A1] | 5,5 |
| 01126 | Conserve de viande, produit de transformation des viandes, plat pré… | 111 | 5,5 [A1] | 5,5 |
| 01127 | Autres viandes comestibles fraîches ou surgelées (cheval, lapin, gi… | 12 | 5,5 [A1] | 5,5 |
| 01130 | Poissons frais | 110 | 5,5 [A1] | 5,5 |
| 01131 | Poissons surgelés ou congelés (hors poissons panés ou cuisinés) | 18 | 5,5 [A1] | 5,5 |
| 01132 | Fruits de mer frais ou surgelés (yc cuits, nc cuisinés ) | 59 | 5,5 [A1] | 5,5 |
| 01133 | Poissons et fruits de mer salés, fumés, séchés yc surgelé | 24 | 5,5 [A1] ; caviar 20 [A1, exclusion] | 5,5 |
| 01134 | Conserves de poisson et de fruits de mer et plats préparés à base d… | 85 | 5,5 [A1] | 5,5 |
| 01145 | Fromage et lait caillé | 282 | 5,5 [A1] | 5,5 |
| 01147 | Œufs | 45 | 5,5 [A1] | 5,5 |
| 0114A | Lait frais, condensé, en poudre | 72 | 5,5 [A1] | 01141:5,5 01142:5,5 01143:5,5 |
| 0114B | Yaourts et produits laitiers | 177 | 5,5 [A1] | 01144:5,5 01146:5,5 |
| 01151 | Beurre | 42 | 5,5 [A1] | 5,5 |
| 0115A | Huiles alimentaires | 35 | 5,5 [A1] | 01153:5,5 01154:5,5 |
| 0115B | Margarine et autres graisses alimentaires | 13 | MIXTE : 20 margarines et graisses végétales [A1 ; BOFiP §230] ; 5,5 graisses animales [A1] | 01152:20 01155:5,5 |
| 01161 | Agrumes frais | 63 | 5,5 [A1] | 5,5 |
| 01162 | Bananes fraîches | 27 | 5,5 [A1] | 5,5 |
| 01168 | Fruits séchés | 48 | 5,5 [A1] | 5,5 |
| 01169 | Fruits au sirop et fruits surgelés | 7 | 5,5 [A1] | 5,5 |
| 0116A | Autres fruits frais | 194 | 5,5 [A1] | 01163:5,5 01164:5,5 01165:5,5 01166:5,5 01167:5,5 |
| 01175 | Légumes secs | 7 | 5,5 [A1] | 5,5 |
| 01176 | Légumes surgelés non cuisinés | 12 | 5,5 [A1] | 5,5 |
| 01177 | Légumes et plats à base de légume,  en conserve (sans pommes de terre) | 53 | 5,5 [A1] | 5,5 |
| 01178 | Légumes préparés et plats à base de légumes,  frais et surgelés (sa… | 41 | 5,5 [A1] | 5,5 |
| 01179 | Pomme de terre, autres tubercules, produits à base de pommes de ter… | 82 | 5,5 [A1] | 5,5 |
| 0117A | Legumes frais | 255 | 5,5 [A1] | 01171:5,5 01172:5,5 01173:5,5 01174:5,5 |
| 01181 | Sucre yc édulcorants | 15 | 5,5 [A1 ; BOFiP §170] | 5,5 |
| 0118A | Produits à base de sucre et cacao | 246 | MIXTE : 5,5 confitures, miel, glaces, chocolat et chocolat de ménage au lait, pâtes à tartiner [A1 ; BOFiP §190, §210] ; 20 confiserie, chocolat au lait ou blanc, chocolats fourrés [A1 ; BOFiP §150-160, §200-220] | 01182:5,5 01183:5,5 01184:20 01185:5,5 01186:5,5 |
| 0119Z | Autres produits alimentaires | 152 | 5,5 [A1] | 01191:5,5 01192:5,5 01193:5,5 01194:5,5 01195:5,5 |
| 01213 | Cacao et chocolat en poudre | 6 | 5,5 préparations pour petit déjeuner [BOFiP §210] ; cacao en poudre pur : non trouvé | 5,5 |
| 0121A | Café, thé, plantes à infusion | 121 | 5,5 [A1] | 01211:5,5 01212:5,5 |
| 01221 | Eaux minérales | 66 | 5,5 [A1 ; BOFiP §140, §330] | 5,5 |
| 01222 | Boissons gazeuses | 48 | 5,5 [A1 ; BOFiP §140 : « autres boissons » de 1,2 % vol. au plus, sodas non nommés] | 5,5 |
| 0122A | Jus de fruits et de légumes | 101 | 5,5 [A1 ; BOFiP §140] | 01223:5,5 01224:5,5 |
| 0131Z | Autres dépenses d alimentation | 169 | 5,5 par défaut [A1] (cérémonies, séjours hors domicile, cadeaux : contenu non décrit) | 01311:5,5 01312:5,5 |
| 02111 | Spiritueux et liqueurs | 100 | 20 [278 ; exclusion de A1] + droits sur les alcools (hors but) | alcools_forts |
| 0212A | Vins, apéritifs à base de vin, champagne | 228 | 20 [278] + droits sur les alcools (hors but) | 02121:vin 02122:vin |
| 02131 | Bière et boissons à base de bière | 62 | 20 [278] + droits sur les alcools (hors but) | biere |
| 022ZZ | Tabac et produits connexes | 402 | 20 [278 ; base : prix de détail, BOI-TVA-BASE-10-20-60] + accise tabacs (hors but) | 02211:cigarettes 02212:cigares 02213:tabac_a_rouler |
| 02411 | Dépenses de boissons alcoolisées, tabac et stupéfiants : cadeau off… | 4 | 20 [278] | — |
| 03111 | Tissus pour vêtements | 4 | 20 [278] | 20 |
| 0312Z | Vêtements homme, femme, enfant | 897 | 20 [278] | 03121:20 03122:20 03123:20 |
| 03131 | Accessoires du vêtement et mercerie | 42 | 20 [278] | 20 |
| 03141 | Nettoyage, réparation et location de vêtements | 17 | 20 [278] | 20 |
| 032ZZ | Chaussures, yc location et réparation | 288 | 20 [278] | 03211:20 03212:20 03213:20 03221:20 |
| 0331Z | Autres dépenses d habillement | 130 | 20 [278] | 03311:20 03312:20 |
| 04111 | Loyers nets des aides au logement (hors charges ou avec charges non… | 1984 | EXONÉRÉ [261 D 2° : location de logements nus] | — |
| 04121 | Loyers (hors charges ou avec charges non isolables) des locataires… | 48 | EXONÉRÉ [261 D 2°, 4°] ; 10 meublés de tourisme avec services [279 a] | — |
| 0431Z | Produits destinés aux travaux courants d’entretien et de réparation… | 176 | MIXTE : 20 fournitures achetées par le ménage [278] ; 10 travaux d'entretien facturés par une entreprise, logement de plus de deux ans [279-0 bis] ; 5,5 rénovation énergétique [278-0 bis A] | 04311:20 04321:10? |
| 04431 | Factures d’eau résidence principale, autre logement, dépendance, te… | 252 | MIXTE : 5,5 eau potable, abonnement et redevances compris [A1 ; BOFiP §100] ; 10 assainissement [279 b] ; 10 frais d'accès au réseau [BOFiP §100] | 5,5 |
| 04441 | Charges collectives relatives au logement (payées isolément du loye… | 589 | MIXTE : chauffage collectif 20 ou 5,5 [278 ; B], eau 5,5, entretien 10 [279-0 bis], personnel hors TVA ; composition non publiée | 20 |
| 04500 | Facture électricité + gaz (non dissociables) | 182 | 20 [278] depuis le 1/8/2025 + accises électricité et gaz | 20 |
| 04511 | Facture d électricité résidence principale, autre logement, garage,… | 751 | 20 [278] depuis le 1/8/2025 + accise électricité ; avant : abonnement (≤ 36 kVA) et CTA à 5,5 | 20 |
| 0452Z | Gaz et combustibles liquéfiés (gaz de ville, butane...) | 258 | 20 [278] + accise gaz naturel ou GPL combustible ; abonnement gaz à 5,5 jusqu'au 31/7/2025 | 04521:20 04522:20 |
| 0453Z | Combustibles liquides | 124 | 20 [278] + accise fioul domestique | 04531:20 |
| 045AZ | Combustibles solides | 56 | MIXTE : 10 bois de chauffage [278 bis 3° bis] ; 20 charbon [278] + accise charbons ; réseau de chaleur 5,5 abonnement et chaleur à 50 % EnR et plus [B], sinon 20 | 04541:10 04551:20? 04552:20? |
| 04611 | Autres dépenses d’habitation : cadeau offert (à destination d’un au… | 69 | INDÉTERMINÉ (cadeau à un autre ménage : loyer exonéré ou bien à 20) | 20 |
| 0511Z | Meubles, articles d’ameublement et de décoration | 413 | 20 [278] | 05110:20 05111:20 05112:20 05113:20 05114:20 05115:20 05116:20 |
| 051AZ | Tapis et autres revêtements, pose et réparation | 14 | 20 [278] ; 10 pose par une entreprise dans un logement de plus de deux ans [279-0 bis] | 05121:20 05131:20? |
| 0521Z | Articles de literie et autres articles de ménage en textile | 86 | 20 [278] | 05211:20 05212:20 |
| 0531Z | Gros appareils ménagers électriques | 171 | 20 [278] ; 5,5 PAC air/air fournie et posée [278-0 bis A, LFI 2026 art. 92] | 05311:20 05312:20 05313:20 05314:20 05315:20 05316:20 05317:20 05331:20? |
| 05321 | Petit électroménager | 25 | 20 [278] | 20 |
| 0541Z | Verrerie, vaisselle, ustensiles de cuisine et article de ménage ou… | 80 | 20 [278] | 05411:20 05412:20 05413:20 05414:20 |
| 0551Z | Gros outillage de bricolage, de jardinage et leur réparation | 75 | 20 [278] | 05511:20 05512:20 05513:20 |
| 0552Z | Petit outillage et accessoires de bricolage et jardinage, matériaux… | 134 | 20 [278] | 05521:20 05522:20 05523:20 |
| 0561Z | Articles de ménage non durables | 234 | 20 [278] | 05611:20 05612:20 |
| 0562Z | Services domestiques et autres services pour le logement | 282 | MIXTE : hors TVA emploi direct d'un salarié ; 10 organismes de services à la personne déclarés [279 i] ; 5,5 aide aux personnes âgées ou handicapées [D] ; 20 blanchisserie et autres services [278] | 05621:10 05622:20 |
| 0571Z | Autres dépenses en équipement | 48 | 20 [278] | 05711:20 05712:20 |
| 0611Z | Produits pharmaceutiques, appareils et matériels thérapeutiques | 255 | MIXTE : 2,1 médicaments remboursables [281 octies] ; 10 médicaments non remboursables [278 quater] ; 5,5 appareillages pour handicapés [A 2°], compléments alimentaires nutritionnels [BOFiP §280] ; 20 lunettes et lentilles [BOI-TVA-LIQ-30-10-50], parapharmacie | 06111:2,1 06112:20 06113:5,5 |
| 06211 | Consultations des médecins généralistes ou spécialistes hors hospit… | 103 | EXONÉRÉ [261 4 1°] | — |
| 06221 | Dentiste, orthodontie | 62 | EXONÉRÉ [261 4 1°] | — |
| 0623Z | Services paramédicaux (labo, radio, soins des auxiliaires médicaux… | 55 | EXONÉRÉ [261 4 1°] (laboratoires, auxiliaires médicaux) ; location de matériel taxable | 06231:— 06232:— 06233:— |
| 06311 | Services et soins hospitaliers | 26 | EXONÉRÉ ou HORS CHAMP (hôpital public [256 B]) | — |
| 0641Z | Autres dépenses de santé | 9 | EXONÉRÉ par défaut [261 4 1°] (contenu non décrit) | 06411:— 06412:— |
| 0711Z | Achats d automobiles | 1814 | MIXTE : 20 sur le neuf [278] ; occasion : TVA sur la marge du professionnel [297 A], aucune entre particuliers | 07111:20 07112:20 07141:20? |
| 07121 | Achats de motocycles neufs et occasion | 75 | MIXTE : 20 neuf [278] ; occasion comme 0711Z | 20 |
| 07131 | Achats de cycles neufs et occasion | 36 | MIXTE : 20 neuf [278] ; occasion comme 0711Z | 20 |
| 07211 | Pièces détachées, pneus et accessoires pour les véhicules personnel… | 132 | 20 [278] | 20 |
| 07221 | Carburants, électricité, huiles, lubrifiants… | 1108 | 20 [278] + accises carburants ; Corse 13 [297] | ticpe |
| 07231 | Réparations, dépannages, révisions, lavage, entretien et contrôle t… | 289 | 20 [278] | 20 |
| 0724Z | Autres services liés à l’utilisation de véhicules personnels | 136 | 20 [278] (parking, péages, auto-école, location) | 07241:20 07242:20 |
| 07361 | Autres services de transport (yc déménagement) | 15 | 20 [278] (déménagement) | 20 |
| 073ZZ | Services de transport | 519 | MIXTE : 10 transport intérieur de voyageurs, taxi compris [279 b quater] ; EXONÉRÉ transport aérien international [262 II 8°] | 07311:10 07321:10 07331:10 07341:10 07351:10 |
| 0741Z | Autres dépenses de transport | 363 | INDÉTERMINÉ (séjours hors domicile, cadeaux) | 07411:20 07412:20 |
| 08111 | Services postaux (yc timbres, enveloppes) | 23 | EXONÉRÉ service universel postal [261 4, alinéa non vérifié] ; autres envois 20 | — |
| 08121 | Achats et réparation téléphones fixes ou portables, télécopieurs et… | 86 | 20 [278] | 20 |
| 08131 | Services de téléphone et fax, internet, recharges téléphoniques | 626 | 20 [278] | 20 |
| 0911Z | Appareils de réception, d’enregistrement et de reproduction, du son… | 93 | 20 [278] | 09111:20 09112:20 09151:20? |
| 09131 | Micro-ordinateurs, tablettes, matériels et accessoires informatique… | 90 | 20 [278] | 20 |
| 09141 | Supports vierges ou enregistrés pour l’image et le son (yc téléchar… | 49 | 20 [278] | 20 |
| 091AZ | Equipement photo, cinéma, optique | 26 | 20 [278] | 09121:20 09122:20 |
| 092ZZ | Autres biens durables importants du domaine des loisirs et de la cu… | 96 | 20 [278] | 09211:20 09221:20 09222:20 09231:20 |
| 0931Z | Jeux, jouets et passe temps, articles de sport, de camping et de lo… | 168 | 20 [278] | 09311:20 09312:20 |
| 09321 | Horticulture, accessoires et frais de livraison | 146 | MIXTE : 10 plantes et fleurs [278 bis ; BOI-TVA-LIQ-30-10-35] ; 20 accessoires et livraison [278] | 10 |
| 093AZ | Animaux d’agrément | 163 | 20 par défaut [278] (animaux de compagnie, aliments, vétérinaire : aucun taux réduit trouvé) | 09331:20 09341:20 |
| 09411 | Services sportifs et récréatifs (spectacles sportifs, participation… | 329 | MIXTE : 5,5 spectacles sportifs [J], équitation [O] ; 10 droits d'admission [279 b nonies] ; EXONÉRÉ cotisations d'associations [261 7 1°] ; 20 salles de sport, location, jeux vidéo [278] | 10 |
| 0942Z | Services culturels | 466 | MIXTE : 5,5 cinéma [G], théâtre et concerts [F], zoos [L] ; 2,1 140 premières représentations [281 quater] ; 10 musées et expositions [279 b nonies], abonnements TV [279 b octies] ; 20 smartbox et autres [278] | 09421:5,5 09422:5,5 09423:10 09424:20 |
| 09431 | jeux de hasard (loto, tiercé …) | 38 | EXONÉRÉ [261 E] (jeux de hasard) | — |
| 09511 | Livres yc e-books | 118 | 5,5 [A 3°] (livres, numériques compris) | 5,5 |
| 09521 | Journaux et périodiques yc par abonnement | 117 | 2,1 [298 septies] (publications de presse) ; 20 autres périodiques | 2,1 |
| 09531 | Imprimés divers (carte postale, de visite, poster, calendrier, cart… | 13 | 20 [278] | 20 |
| 09541 | Articles de papeterie et de dessin (yc toner pour imprimante) | 72 | 20 [278] | 20 |
| 09611 | Voyages à forfait, week-end, excursions… yc voyage scolaire | 367 | MARGE : TVA à 20 sur la marge de l'agence, part hors UE exonérée [266 1 e, à vérifier] | — |
| 0971Z | Autres dépenses de loisirs | 239 | INDÉTERMINÉ (séjours hors domicile, cadeaux) | 09711:20 09712:20 |
| 10111 | Enseignement maternel et primaire (scolarité et cours d’alphabétisa… | 22 | EXONÉRÉ [261 4 4° a] ou HORS CHAMP (public [256 B]) | — |
| 10121 | Enseignement secondaire (scolarité et inscription aux concours de n… | 25 | EXONÉRÉ [261 4 4° a] ou HORS CHAMP (public [256 B]) | — |
| 10131 | Enseignement supérieur et frais d’inscription aux concours des gran… | 116 | EXONÉRÉ [261 4 4° a] ou HORS CHAMP (public [256 B]) | — |
| 10141 | Enseignement ne correspondant à aucun niveau particulier (cours par… | 24 | MIXTE : EXONÉRÉ [261 4 4° a, b] ; 10 soutien scolaire par un organisme de services à la personne déclaré [279 i] | — |
| 1015Z | Autres dépenses d’enseignement | 28 | EXONÉRÉ par défaut [261 4 4° a] | 10151:— 10152:— |
| 11111 | Repas pris dans un restaurant | 582 | MIXTE : 10 repas et boissons sans alcool [279 m] ; 20 boissons alcooliques [278] | 10 |
| 11112 | Repas pris dans un café, bars ou assimilé | 449 | MIXTE : 10 consommations sans alcool sur place [279 m] ; 20 boissons alcooliques [278] | 20 |
| 11121 | Cantines scolaire et professionnelle | 361 | MIXTE : 5,5 repas fournis dans les écoles par un prestataire [E] ; EXONÉRÉ cantine gérée par l'établissement d'enseignement [261 4 4°] ; 10 cantines d'entreprise [279 a bis] ; HORS CHAMP régie publique [256 B] | 5,5 |
| 1113Z | Autres dépenses de restauration | 257 | INDÉTERMINÉ (séjours hors domicile, cadeaux) ; 10 par défaut [279 m] | 11131:5,5 11132:5,5 |
| 11211 | Services d hébergement | 343 | 10 [279 a] ; EXONÉRÉ location meublée sans services [261 D 4°] | 10 |
| 12111 | Salons de coiffure et esthétique corporelle (yc cures thermales, ta… | 339 | MIXTE : 20 coiffure, esthétique [278] ; 10 soins thermaux [279 a quinquies] | 20 |
| 1212Z | Appareils, articles et produits pour les soins personnels | 418 | MIXTE : 20 [278] ; 5,5 protections hygiéniques [A 1° bis], préservatifs [A 1° ter] | 12121:20 12122:20 |
| 12311 | Articles de bijouterie, de joaillerie et d’horlogerie (yc leur répa… | 55 | 20 [278] | 20 |
| 1232Z | Autres effets personnels : maroquinerie, accessoires (briquet, para… | 71 | 20 [278] | 12321:20 12322:20 |
| 12331 | Autres biens et services offerts  (à des personnes extérieures au m… | 45 | INDÉTERMINÉ (cadeaux) ; 20 par défaut | 20 |
| 12411 | Services de protection sociale (assistante maternelle, crèche, mais… | 313 | MIXTE : HORS TVA assistante maternelle salariée, établissements publics [256 B] ; EXONÉRÉ organismes sans but lucratif [261 7 1°] ; 5,5 hébergement en établissement pour personnes âgées ou handicapées [C] | 10 |
| 12511 | Assurances vie, décès | 38 | EXONÉRÉ [261 C 2°] + taxe sur les conventions d'assurance (hors but) | autres_assurances |
| 12521 | Assurances liées au logement | 375 | EXONÉRÉ [261 C 2°] + taxe sur les conventions d'assurance (hors but) | autres_assurances |
| 12531 | Assurances liées à la santé | 1101 | EXONÉRÉ [261 C 2°] + taxe sur les conventions d'assurance (hors but) | assurance_sante |
| 12541 | Assurances liées aux transports (yc assurance voyage) | 676 | EXONÉRÉ [261 C 2°] + taxe sur les conventions d'assurance (hors but) | assurance_transport |
| 12551 | Autres assurances (pack assurance, scolaire, dépendance, prévoyance… | 148 | EXONÉRÉ [261 C 2°] + taxe sur les conventions d'assurance (hors but) | autres_assurances |
| 12611 | Services financiers | 147 | EXONÉRÉ [261 C 1°] ; certains frais taxables | — |
| 1271Z | Autres services | 597 | 20 [278] ; la caution de location (12712) n'est pas une consommation | 12711:20 12712:20 |
| 12811 | Autres dépenses occasionnées par une cérémonie | 26 | 20 par défaut [278] | 20 |
| 12911 | Dépenses SAI des personnes vivant hors du domicile au moins un jour… | 22 | INDÉTERMINÉ ; 20 par défaut | 20 |
| 13141 | Impôts sur le revenu | 2223 | HORS CHAMP (impôt) | — |
| 13151 | Taxes automobiles (cartes grises, contraventions) | 24 | HORS CHAMP (taxes, amendes) | — |
| 13161 | Autres impôts et taxes (taxe foncière pour jardin ou autre, amendes… | 53 | HORS CHAMP (impôts) | — |
| 131AZ | Impôts et taxes du logement | 1175 | HORS CHAMP (impôts du logement) | — |
| 132ZZ | Remboursements de prêts immobiliers | 2711 | HORS CHAMP (remboursements) | — |
| 13311 | Aides et dons (occasionnels ou réguliers) en argent offerts par le… | 866 | HORS CHAMP (transferts) | — |
| 134ZZ | Gros travaux dans le logement | 1580 | MIXTE, hors consommation INSEE mais taxé : 10 travaux [279-0 bis] ; 5,5 rénovation énergétique [278-0 bis A] ; 20 construction, agrandissement, matériaux, chaudières fossiles depuis le 1/3/2025 [278-0 bis A III bis] | — |
| 13511 | Remboursements de crédits à la consommation (voiture, gros travaux,… | 1002 | HORS CHAMP (remboursements) | — |

### 3.1 Les postes mixtes et leurs clés de répartition

Aucune clé publiée n'a été trouvée pour répartir la dépense d'un poste mixte entre ses taux.
Les postes mixtes qui pèsent le plus (dépense moyenne 2017) et ce que l'on sait :

| Poste | € 2017 | Taux mêlés | Clé publiée |
|---|--:|---|---|
| 0711Z automobiles | 1 814 | 20 % sur le neuf ; marge sur l'occasion vendue par un professionnel ; rien entre particuliers | non trouvée |
| 04441 charges collectives | 589 | chauffage 20 ou 5,5, eau 5,5, entretien 10, personnel hors TVA | non trouvée |
| 11111 restaurant | 582 | 10 % repas et boissons sans alcool, 20 % alcool | non trouvée |
| 073ZZ transports | 519 | 10 % intérieur, exonéré international | non trouvée |
| 0942Z services culturels | 466 | 5,5 / 2,1 / 10 / 20 | non trouvée ; la microdonnée sépare 09421 à 09424 |
| 11112 cafés, bars | 449 | 10 % sans alcool, 20 % alcool | non trouvée |
| 1212Z soins personnels | 418 | 20 %, 5,5 % protections hygiéniques | non trouvée |
| 09611 voyages à forfait | 367 | TVA sur la marge, hors UE exonéré | non trouvée |
| 11121 cantines | 361 | 5,5 école, 10 entreprise, hors champ en régie | non trouvée |
| 09411 sport, loisirs | 329 | 5,5 / 10 / 20 / exonéré | non trouvée |
| 12411 protection sociale | 313 | hors TVA, exonéré, 5,5 hébergement | non trouvée |
| 0562Z services domestiques | 282 | hors TVA (emploi direct), 10, 5,5, 20 | non trouvée |
| 0611Z pharmacie, optique | 255 | 2,1 / 10 / 5,5 / 20 | non trouvée |
| 04431 eau | 252 | 5,5 eau, 10 assainissement | non trouvée |
| 0118A sucre et cacao | 246 | 5,5 / 20 | non trouvée ; la microdonnée isole 01184 (confiserie, 20 %) |

Pistes à examiner, **non vérifiées** ici : les Comptes de la santé de la DREES (médicaments
remboursables et non remboursables, optique) pour `0611Z` ; les publications de la DARES sur
les services à la personne (emploi direct et organismes) pour `0562Z` ; l'observatoire des
services d'eau et d'assainissement (SISPEA) pour `04431` ; les comptes de la nation par
produit pour les postes `0711Z` et `11111`. Sans clé, le moteur doit choisir une hypothèse,
la nommer et la préenregistrer ; un taux unique « dominant » est une hypothèse comme une
autre.

### 3.2 Où openfisca-france-indirect-taxation s'écarte de la loi de 2026

Lu dans `bdf_2017_legislation.csv` (lignes dont la période se termine en 2024) :

* `11112` cafés et bars à 20 % : la vente à consommer sur place est à 10 % hors alcool (CGI
  art. 279, m).
* `06113` « appareils et matériels thérapeutiques (lunettes, prothèses…) » à 5,5 % : les
  lunettes et les lentilles sont à 20 % (BOI-TVA-LIQ-30-10-50).
* `06111` médicaments et compléments alimentaires à 2,1 % : seuls les médicaments
  remboursables le sont ; non remboursables 10 %, compléments nutritionnels 5,5 %.
* `09422` « musées, jardins zoologiques » à 5,5 % depuis 2018 : les zoos sont à 5,5 %
  (lettre L), les musées et expositions à 10 % (CGI art. 279, b nonies).
* `04551` chauffage urbain à 20 % : l'abonnement est à 5,5 % (lettre B), la chaleur aussi si
  elle vient à 50 % au moins d'énergies renouvelables ou de récupération.
* `04511`, `04521`, `04500` à 20 % sur toute la facture : juste depuis le 1er août 2025 ;
  faux avant (abonnement et CTA à 5,5 %).
* `05621` services domestiques à 10 % et `12411` protection sociale à 10 % : l'emploi direct
  et les assistantes maternelles salariées ne paient pas de TVA ; les établissements publics
  sont hors champ.
* `07112` automobiles d'occasion à 20 % : régime de la marge (CGI art. 297 A).
* `09611` voyages à forfait sans catégorie depuis 2019, `08111` services postaux sans
  catégorie : cohérent avec la marge et l'exonération, à condition de le dire.
* Rien n'est daté après 2024 : la table ne connaît ni le changement des abonnements d'août
  2025 ni les mesures de la loi de finances pour 2026.

## 4. Les changements de taux de TVA, 2017-2026

Ceux qui ont été vérifiés pour ce document ; d'autres existent sans doute (aucune recherche
exhaustive n'a été faite avant 2025).

| Date d'effet | Changement | Source |
|---|---|---|
| 1er mars 2025 | Rénovation énergétique comprenant une chaudière « susceptible d'utiliser des combustibles fossiles » : taux normal (art. 278-0 bis A, III bis) | loi n° 2025-127 du 14 février 2025, art. 32 (rattachement et date déduits de la note de version Légifrance, qui ne date pas le III bis) |
| 1er mars 2025 | Lettre B (chaleur) modifiée ; portée exacte non vérifiée | même loi, art. 32 |
| 1er août 2025 | Abonnements d'électricité (≤ 36 kVA) et de gaz naturel, et CTA : 5,5 % → 20 %, compensés par une baisse d'accise | loi n° 2025-127, art. 20 ; BOI-RES-TVA-000209 (26 août 2026) ; guide 2026, § I.1 |
| 2025 | Photovoltaïque jusqu'à 9 kWc : 5,5 % (lettre P) ; date d'effet initiale **non vérifiée** | Légifrance, art. 278-0 bis |
| 21 février 2026 | Pompes à chaleur air/air dans la rénovation énergétique (art. 92), énergie frigorifique par réseaux (art. 93, lettre B bis), photovoltaïque réaménagé (art. 94) : 5,5 % | loi n° 2026-103 du 19 février 2026 ; note CMS, « Mesures diverses » |
| 1er mars 2026 | Collecte et traitement des déchets ménagers : 5,5 % (lettre M) ; taux antérieur **non vérifié** ici | loi n° 2026-103, art. 81 (version Légifrance du 1er mars 2026) |
| 1er janvier 2027 | Recodification de la TVA dans le CIBS | ordonnance n° 2025-1247 du 17 décembre 2025 |

Sur l'énergie, la TVA est donc à 20 % sur toute la facture d'électricité, de gaz, de fioul
et de carburant depuis le 1er août 2025, accises comprises ; avant, la part abonnement des
factures d'électricité et de gaz était à 5,5 %. Le bois de chauffage est à 10 %, les réseaux
de chaleur à 5,5 % sous condition.

## 5. Les accises sur l'énergie en 2026

Sources : guide 2026 sur la fiscalité des énergies du ministère, version du 22 juillet 2026,
qui tient compte de la loi de finances pour 2026 (§ II à IV et annexe 3) ; circulaire du 30
septembre 2026, « Droits et taxes applicables aux produits énergétiques à compter du 1er
octobre 2026 » (douane, annexe 1.1 et annexe 3) ; rescrit BOI-RES-EAT-000240 du 31 décembre
2025 ; communiqué de la CRE du 16 juillet 2026 sur les tarifs réglementés.

### 5.1 Les tarifs

Tarif normal en euros par MWh (PCI ; PCS pour le gaz naturel, CIBS art. L. 312-19), et tarif
par unité de base d'imposition. Métropole hors Corse.

| Produit (catégorie fiscale) | 2024 | 1/8/2025-31/1/2026 | 1/2-31/7/2026 | 1/8/2026-31/1/2027 | Par unité, 2026 | Article |
|---|--:|--:|--:|--:|---|---|
| Gazole | 59,40 + modulation régionale ≤ 1,35 + IDFM ≤ 1,89 | 60,75 | 60,75 | 60,75 | 60,75 €/hL | CIBS L. 312-35 |
| Essences SP95-E5 et SP98 | 76,826 + ≤ 0,821 + IDFM ≤ 1,148 | 77,647 | 77,647 | 77,647 | 69,02 €/hL | L. 312-35 |
| SP95-E10 | 74,576 + modulation | 75,397 | 75,397 | 75,397 | 67,02 €/hL | L. 312-83 (tarif particulier) |
| Superéthanol E85 | 17,894 | 17,894 | 17,894 | 17,894 | 11,83 €/hL | L. 312-84 |
| GPL carburant | 16,208 | 16,208 | 16,208 | 16,208 | 20,71 €/100 kg | L. 312-35 |
| Fioul domestique | 15,62 | 15,43 | 16,39 | 16,66 | 16,39 puis 16,66 €/hL | L. 312-36 et L. 312-37-1 |
| GPL combustible | 5,189 | 5,189 | 5,971 | 6,241 | 7,63 puis 7,97 €/100 kg (douane : 7,98) | L. 312-36 et L. 312-37-1 |
| Gaz naturel combustible (PCS) | 16,37 | 15,43 | 16,39 | 16,66 | €/MWh PCS | L. 312-36 et L. 312-37-1 |
| Électricité, ménages et assimilés | 21 (voir note) | 29,98 | 30,85 | 30,62 | €/MWh | L. 312-37 et L. 312-37-1 |

Notes :

* **Majoration ZNI** (CIBS art. L. 312-37-1) : depuis le 1er août 2025, les tarifs de
  l'électricité et des combustibles (pas des carburants) incluent une brique qui finance la
  péréquation des zones non interconnectées : 4,89 €/MWh en 2025, 5,66 au 1er février 2026,
  5,93 au 1er août 2026 (dont 0,27 pour le GPL corse, loi de finances pour 2026, art. 72).
  Le socle de l'électricité des ménages est de 25,09 (août 2025), 25,19 (février 2026) et
  24,69 €/MWh (août 2026, après la baisse de 0,5 €/MWh de la loi de finances pour 2026,
  art. 71) ; celui des combustibles et du gaz, 10,54 puis 10,73 €/MWh (guide, § I.4, II.1,
  III.2, IV.1). La CRE confirme le passage de 30,85 à 30,62 €/MWh au 1er août 2026 pour les
  clients jusqu'à 36 kVA.
* **Électricité avant août 2025** : 33,70 €/MWh jusqu'au 31 juillet 2025 (guide, § II.1 c,
  qui écrit « du 1er janvier au 31 juillet 2025 » alors que la minoration courait jusqu'au
  31 janvier 2025 : à vérifier) ; du 1er février 2024 au 31 janvier 2025, minoration
  exceptionnelle à 1 €/MWh majorée de 20 €/MWh par l'arrêté du 25 janvier 2024, soit
  21 €/MWh (calcul d'après le guide, § II.3) ; 1 €/MWh du 1er février 2022 au 31 janvier
  2024. La catégorie « ménages et assimilés » couvre les ménages jusqu'à 250 kVA et les
  activités économiques jusqu'à 36 kVA.
* **Gaz naturel** : 8,45 (2018-2020), 8,43 (2021), 8,41 (2022), 8,37 (2023), 16,37 (2024),
  17,16 (janvier à juillet 2025), puis le tableau (guide, § III.2). La baisse d'août 2025
  compense la hausse de TVA sur l'abonnement.
* **Carburants** : la faculté de modulation régionale (≤ 1,35 €/MWh gazole, ≤ 0,821 €/MWh
  essences, L. 312-39) et la majoration d'Île-de-France Mobilités (≤ 1,89 et 1,148 €/MWh, L.
  312-40) ont pris fin ; le tarif « autres régions » s'applique partout depuis le 1er août
  2025, sauf en Corse (gazole 59,40, SP95-E5 et SP98 75,701 €/MWh). La circulaire des
  douanes donne 60,75 / 69,02 / 67,02 €/hL dans toutes les régions continentales en 2026.
  Les montants régionaux effectivement appliqués en 2024 sont dans
  openfisca-france-indirect-taxation (1,35 €/hL presque partout, 1,08 en
  Auvergne-Rhône-Alpes, 0 en Corse, valeurs valides au 1er juillet 2024) ; le montant
  IDFM appliqué en 2024 n'a **pas été vérifié**.
* **Discordance** : l'annexe 3 du guide donne 67,50 €/hL pour le SP95-E10 ; 75,397 €/MWh ×
  3,2/3,6 = 67,02 €/hL, chiffre de la circulaire des douanes. Retenir 67,02.
* **Indexation** : la fraction de l'accise sur l'électricité au-delà de 19,74 €/MWh, et
  depuis le 1er février 2026 tout le tarif des combustibles, suivent l'inflation (CIBS L.
  131-1, L. 131-2) ; à partir de 2027 l'indice devient l'inflation sous-jacente (loi de
  finances pour 2026, art. 71 ; guide, § I.5). La révision annuelle a lieu le 1er février.
* **Autres prélèvements dans le prix** : la contribution tarifaire d'acheminement (CTA, 15 %
  de la part fixe du TURPE pour les ménages depuis le 1er février 2026, 21,93 % avant ;
  20,80 % de la part fixe de distribution du gaz) entre dans la base de la TVA ; la TIRUERT
  et la redevance des stocks stratégiques pétroliers sont payées en amont ; la DGEC ne
  compte comme taxe hors TVA que l'accise, elles sont donc dans son prix hors taxes. Aucune
  n'est une accise du but.

### 5.2 Moyennes annuelles pour une simulation annuelle de 2026

Moyenne calendaire (un mois au tarif de janvier, six au tarif de février, cinq au tarif
d'août) ; une pondération par la consommation mensuelle serait meilleure, son profil n'a pas
été cherché :

* électricité des ménages : (29,98 + 6 × 30,85 + 5 × 30,62) / 12 = **30,68 €/MWh** ;
* gaz naturel combustible et fioul domestique : (15,43 + 6 × 16,39 + 5 × 16,66) / 12 =
  **16,42 €/MWh** (et €/hL pour le fioul) ;
* GPL combustible : (5,189 + 6 × 5,971 + 5 × 6,241) / 12 = **6,02 €/MWh** ;
* carburants : tarifs constants toute l'année.

### 5.3 Conversions d'unités

Les tarifs du CIBS sont en €/MWh (L. 312-25, L. 312-26) mais l'assiette reste en volume ou
en masse (L. 312-19). Coefficients de l'arrêté du 13 décembre 2022 modifié (guide, annexe
3) : gazole et fioul domestique 3,6 GJ/hL (1 MWh/hL) ; essences et SP95-E10 3,2 GJ/hL
(0,8889 MWh/hL) ; E85 2,38 GJ/hL (0,6611 MWh/hL) ; B100 3,3 GJ/hL ; ED95 1,91 GJ/hL ; GPL
4,6 GJ/100 kg (1,2778 MWh/100 kg) ; fioul lourd 4,0 GJ/100 kg.
openfisca-france-indirect-taxation porte le même 0,889 pour les essences.

## 6. Ce que porte openfisca-france (176.0.8, installé)

Arbre lu dans `.venv/lib/python3.11/site-packages/openfisca_france/parameters/` :

* `taxation_indirecte/tva/` : `taux_normal` 0,20 (2014), `taux_intermediaire` 0,10 (2014),
  `taux_reduit` 0,055 (1982), `taux_particulier_super_reduit` 0,021 (1986), plus des taux
  historiques (`taux_majore`, `taux_reduit_2`, `taux_normal_majore_temporaire`, tous nuls
  aujourd'hui). Justes pour 2026, référencés. **Aucune table poste → taux.**
* `taxation_indirecte/produits_energetiques/ticpe/` : tarifs du code des douanes, en €/hL ou
  €/100 kg, dernière valeur au 1er janvier 2018 (gazole 59,40, SP95-SP98 68,29, E10 66,29,
  E85 11,83, fioul domestique 15,62, GPL carburant 20,71, GPL combustible 6,63). Faux en
  2026 pour le gazole, les essences et le fioul.
* `major_regionale_ticpe_gazole` et `_super` : anciennes régions, valeurs de 2011 à 2017
  (Île-de-France 4,39 €/hL en 2017) ; sans objet depuis le 1er août 2025.
  `tgap_carburants` : 0,079 depuis 2019.
* `taxes_energie_dans_logement/taxes_electricite_et_gaz/` : `cspe` 22,5 €/MWh (2016),
  `ticgn_prix_par_mwh` 8,43 (2021), `cta_electricite` 27,04 % et `cta_gaz` 20,8 % (2013),
  plafond TCFE 9,9 (2021). Faux en 2026 sauf la CTA du gaz.
* Aucune variable du modèle ne lit ces paramètres (recherche dans `openfisca_france/model` :
  aucune occurrence), ce que `docs/PLF2027_COVERAGE.md` constatait déjà.

## 7. openfisca-france-indirect-taxation

* **Existe** : <https://github.com/openfisca/openfisca-france-indirect-taxation>, non
  archivé, 2 125 commits. Dernier commit vu sur la page des commits : 11 mars 2026 (fusion
  de la PR #200 « major-cleaning », qui modifie le calcul des droits d'accise pour partir
  d'une dépense TTC). Février 2026 : nouveaux inflateurs « CN 2024 » et dépenses de
  carburant gazole et essence. Version 0.5.3 (`pyproject.toml`), OpenFisca-Core ≥ 43, < 45,
  Python 3.9 à 3.13. Sur PyPI, seule une 0.4.dev0 de 2015 : il s'installe depuis git.
  Principal contributeur : l'IPP (modèle TAXIPP). Le SHA du dernier commit n'a pas été lu
  (l'API GitHub n'est pas ouverte à cette session).
* **Licence** : AGPL-3.0. `COPYING` est le texte de l'AGPL v3 ; le README dit « version 3 or
  later » ; `pyproject.toml` dit « GNU Affero General Public License v3 ». Les fichiers de
  `assets/legislation/` n'ont pas de licence propre : ils relèvent de celle du dépôt.
* **Paramètres** (`parameters/imposition_indirecte/`) :
  * `tva/taux_de_tva/` : les mêmes taux qu'openfisca-france, marqués
    `last_value_still_valid_on: 2024-07-08` ;
  * `produits_energetiques/accise_energie_metropole/` : une vingtaine de fichiers en €/MWh ;
    ceux qui ont été lus portent une valeur au 1er janvier 2022 (CIBS), marquée valide au 21
    mai 2024 : gazoles 59,40, essences 76,826, SP95-E10 74,576, E85 17,894, GPL carburant
    16,208, fioul domestique 15,62, gaz naturel combustible 8,45 (faux dès 2024 : 16,37) ;
    plus `ticpe.yaml` (code des douanes, jusqu'en 2018), modulations régionales (2022,
    valides au 1er juillet 2024), majoration IDFM, réfaction corse, coefficients €/MWh →
    €/hL, TGAP, aide exceptionnelle carburant ;
  * `taxes_energie_dans_logement/` : CSPE (2016), TICGN (2021), CTA (2013), TCFE (2021) ;
  * alcools, tabacs, assurances (hors du but).

  Rien n'est postérieur à 2024 : ni les accises d'août 2025 ni celles de 2026.
* **Tables de correspondance** (`assets/legislation/`) : `bdf_2017_legislation.csv` (276
  lignes : sous-classe BDF 2017 à 5 positions, code COICOP ajusté, années de début et de fin
  entre 1994 et 2024, catégorie fiscale `tva_taux_plein`, `tva_taux_intermediaire`,
  `tva_taux_reduit`, `tva_taux_super_reduit`, ou une accise : `ticpe`, `vin`, `biere`,
  `alcools_forts`, `cigarettes`, `cigares`, `tabac_a_rouler`, assurances ; vide si aucune) ;
  `coicop_legislation.csv` (ECOICOP 2016 à 5 niveaux, 472 lignes) ; une ancienne
  `coicop_to_categorie_fiscale.csv` (postes à 4 chiffres, catégories numérotées). Un poste
  n'y a qu'une catégorie : pas de clé pour les postes mixtes.
* **Imputation de l'enquête** : il ne part pas des tableaux publiés mais des
  **microdonnées** de l'enquête (collection `budget_des_familles_2017`, table `c05`, via
  openfisca-survey-manager), qu'il faut obtenir par les canaux d'accès aux fichiers de
  production. Étapes lues dans le code : harmonisation des dépenses par poste
  (`build_survey_data/step_1_1_homogeneisation_donnees_depenses.py`), qui répartit le poste
  « électricité + gaz non dissociables » au prorata des factures séparées de l'enquête ;
  imputation des loyers des propriétaires ; véhicules ; revenus ; appariements avec l'ENL,
  l'EMP et l'ERFS (`matching_*`) ; calage des dépenses sur les comptes nationaux poste par
  poste (`Calage_consommation_bdf.py` : rapport consommation CN / BDF par poste, comptes
  trimestriels 2024 base 2020, reste à charge santé de la DREES 2024, correction
  territoriale) ; quantités de carburant déduites des prix et des parts de carburants. Ses
  accises se calculent à partir de la dépense TTC et du prix TTC.
* **Reprise dans un projet AGPL-3.0-or-later** : possible. Le projet peut incorporer un
  fichier sous AGPL-3.0 (« or later » d'après le README ; même en « v3 seule », l'ensemble
  se distribue sous AGPL-3.0, ce que la licence du projet permet). Conditions : garder la
  notice de droit d'auteur et de licence, dire que le fichier a été modifié et quand (AGPL,
  § 5 a), citer la source (dépôt, chemin, date du commit). Une simple citation ne suffit pas
  si l'on copie le fichier : il faut ces notices. Un taux légal est un fait ; la table,
  comme compilation, peut être protégée : la traiter comme couverte par l'AGPL est le plus
  sûr. Ce n'est pas un avis juridique ; la décision revient au propriétaire.
  Recommandation : garder la table du § 3, dérivée de la loi, et n'utiliser celle
  d'openfisca-france-indirect-taxation que comme contrôle croisé cité ; si l'on copie le
  CSV, l'accompagner d'un en-tête de provenance et de licence.

## 8. Les règles de calcul

**R1. TVA d'un poste.** Pour une dépense TTC `D` d'un poste `p` dont la part `s_k` est au
taux `t_k` (parts de dépense TTC, somme 1, exonéré et hors champ à `t = 0`) :
`TVA_p = D × Σ_k s_k × t_k / (1 + t_k)`. Pour un poste à un seul taux,
`TVA = D × t / (1 + t)` (20 % : 1/6 de la dépense ; 10 % : 1/11 ; 5,5 % : 5,5/105,5 ;
2,1 % : 2,1/102,1). C'est la forme d'openfisca-france-indirect-taxation.

**R2. La TVA porte sur le prix accise comprise.** La base de la TVA comprend « les impôts,
taxes, droits et prélèvements de toute nature à l'exception de la TVA elle-même » (CGI
art. 267, I, 1° ; directive 2006/112/CE, art. 78, rappelée par le guide 2026, § I.1). Donc
`P_TTC = (P_HTT + a) × (1 + t)`, avec `a` l'accise par unité. Vérification sur les prix de
la DGEC : gazole 2026, (1,102 + 0,6075) × 1,2 = 2,051 €/L, la moyenne publiée ; gazole 2024,
(0,803 + 0,594 + 0,0135) × 1,2 = 1,693 €/L pour 1,694 publié ; SP95-E10 2026, (0,945 +
0,6702) × 1,2 = 1,938 €/L, publié 1,938.

**R3. Des euros aux volumes.** `Q = D / P_TTC`, avec le prix TTC moyen de la même année et
du même champ. Accise `A = Q × a` ; TVA sur l'accise `t × A`. Pour l'électricité et le gaz,
`Q` en MWh (PCS pour le gaz).

**R4. Réforme d'une accise.** Le but exclut les réactions de la consommation aux prix : à
quantités fixes et répercussion entière, `ΔA = Q × Δa`, `ΔTVA = t × Q × Δa`, et la dépense
TTC du ménage augmente de `(1 + t) × Q × Δa`. Ces deux hypothèses doivent être dites.

**R5. Réforme d'un taux de TVA.** Sur la part `s` d'un poste passant de `t` à `t'`, à
quantités et prix hors taxes fixes : `ΔTVA = D × s × (t' − t) / (1 + t)`, et la dépense TTC
varie de `D × s × (t' − t) / (1 + t)`.

**R6. Les unités** : § 5.3. Le gaz naturel est taxé en MWh PCS, les autres produits en PCI.

**R7. Le calendrier** : les tarifs changent le 1er février et, en 2025 et 2026, le 1er
août ; pour une année, la moyenne du § 5.2.

**R8. Les prix moyens des carburants** (DGEC, fichier « Prix HTT et TTC depuis janvier
2020 », relevés hebdomadaires, €/L ; moyennes annuelles publiées pour 2024 ; 2026 : moyenne
des 43 relevés du 2 janvier au 23 octobre 2026, calculée ici) :

| Produit | HTT 2024 | TTC 2024 | HTT 2026 (janv.-oct.) | TTC 2026 (janv.-oct.) |
|---|--:|--:|--:|--:|
| Gazole | 0,803 | 1,694 | 1,102 | 2,051 |
| SP95-E5 | 0,826 | 1,821 | 0,965 | 1,986 |
| SP95-E10 | 0,815 | 1,784 | 0,945 | 1,938 |
| SP98 | 0,877 | 1,882 | 0,993 | 2,020 |
| Superéthanol E85 | 0,580 | 0,839 | 0,564 | 0,819 |
| GPL carburant | 0,707 | 0,987 | 0,722 | 1,005 |
| Fioul domestique (livraisons de 2 000 à 4 999 L) | 0,844 | 1,200 | 1,168 | 1,598 |

Les prix de 2026 ont bondi en mars : gazole TTC, moyennes mensuelles publiées, 1,634 €/L en
janvier, 1,672 en février, 2,067 en mars, 2,239 en avril, 2,121 en mai, 1,942 en juin, 2,052
en juillet, 2,202 en août, 2,325 en septembre. La moyenne de 2026 dépend donc de la fenêtre
retenue et sera révisée quand l'année sera close. Le Datalab du SDES « Les prix des produits
pétroliers en 2024 » (juillet 2025) donne les mêmes moyennes arrondies (gazole 1,69 €/L,
SP95-E10 1,78, SP98 1,88, E85 0,84, GPL carburant 0,99, fioul domestique 1,20 ; propane
171 €/MWh PCI ; butane 42,1 € la bouteille de 13 kg), champ France métropolitaine hors
Corse, et l'accise par litre (gazole 0,61, SP95-E10 0,67, SP98 0,69, E85 et GPL carburant
0,12, fioul 0,16 €/L, modulations régionales incluses). La masse volumique du GPL carburant
n'a pas été trouvée dans une source officielle ; l'accise implicite de 2026, 0,116 €/L, la
situe vers 0,56 kg/L (calcul, pas une source).

**R9. Les prix de l'électricité et du gaz.** 2024 : 280 €/MWh pour l'électricité des ménages
(SDES, « Prix de l'électricité en France et dans l'Union européenne en 2024 », 9 juillet
2025 ; la page ne précise pas TTC) ; 130 €/MWh PCS TTC pour le gaz, dont 92 hors taxes
(SDES, même série). 2026 : prix moyen annuel des ménages **non trouvé** ; la CRE donne une
facture TTC moyenne aux tarifs réglementés de 1 046 € puis 1 072 € par an pour 4,5 MWh au
1er août 2026, soit environ 232 puis 238 €/MWh (calcul).

**R10. Le poste 07221** (carburants, électricité, huiles, lubrifiants) n'est pas réparti
entre gazole, essences, E85, GPL et électricité dans les tableaux publics. Une clé est
nécessaire (parc des ménages par énergie, ventes par carburant) ; elle n'a **pas été
trouvée** ici. Les huiles et lubrifiants ne portent pas d'accise des carburants.

**R11. Le poste 04500** (électricité et gaz non dissociables) :
openfisca-france-indirect-taxation le répartit au prorata global des factures séparées de
l'enquête ; avec les tableaux publiés, le même prorata (04511 et 0452Z) peut se calculer
par décile.

**R12. Les achats d'occasion et les voyages à forfait** : sous un régime de marge, la TVA
n'est due que sur la marge ; appliquer le taux légal à la dépense surestime la TVA (R1 avec
une part `s` à définir).

## 9. Traduire les taux en boutons du moteur

Le moteur expose des boutons nommés et bornés (`ReformSpec`, liste blanche, pas de chemin de
paramètre brut). La traduction la plus sûre :

1. **Quatre boutons de taux**, pas un par poste : `tva_taux_normal`,
   `tva_taux_intermediaire`, `tva_taux_reduit`, `tva_taux_particulier`, branchés sur les
   nœuds `taxation_indirecte.tva.*` d'openfisca-france, justes en 2026 et référencés.
2. **La table du § 3 comme législation versionnée** : pour chaque feuille de TM106, des
   parts par catégorie (normal, intermédiaire, réduit, particulier, exonéré, hors champ,
   marge), avec la référence et la date. Une table de quelques kilo-octets, dérivée de la
   loi, peut entrer dans git ; les données de l'INSEE, non.
3. **Un bouton de reclassement** pour les mesures qui changent le taux d'un poste (« la
   restauration à 5,5 % ») : un dictionnaire borné `{poste: catégorie}`, dont les clés sont
   prises dans la table, et qui déplace la part concernée d'une catégorie à une autre. Pour
   un poste mixte, le bouton vise une part nommée (`11111` repas, pas `11111` entier).
4. **Une accise par catégorie fiscale du CIBS, dans l'unité de la loi (€/MWh)** :
   `accise_gazole`, `accise_essences` (SP95-E5 et SP98), `accise_sp95_e10`, `accise_e85`,
   `accise_gpl_carburant`, `accise_fioul_domestique`, `accise_gpl_combustible`,
   `accise_gaz_naturel`, `accise_electricite_menages`, et `majoration_zni` (L. 312-37-1),
   qui s'ajoute à l'électricité et aux combustibles. La conversion en €/hL ou €/100 kg se
   fait dans le moteur avec les coefficients du § 5.3. Les nœuds d'openfisca-france étant
   périmés, ces tarifs demandent un sous-arbre de paramètres propre au projet, daté (2024,
   1er août 2025, 1er février et 1er août 2026) et référencé, qu'on pourra proposer en amont
   ensuite.
5. **La TVA sur l'accise n'est pas un bouton** : elle découle de R2. Les hypothèses
   (quantités fixes, répercussion entière, moyenne annuelle du § 5.2) sont écrites dans la
   sortie, comme les autres hypothèses du moteur.

## 10. Non trouvé ou à décider

* Une clé de répartition publiée pour chacun des 29 postes mixtes (§ 3.1) : non trouvée. À
  décider : hypothèse par poste, préenregistrée.
* Le rattachement, dans TM106, des sous-classes 04321, 04411, 04421, 04551 et 04552 : non
  trouvé.
* Le taux du cacao en poudre pur : non trouvé (le BOFiP ne le nomme pas).
* L'alinéa de l'exonération du service universel postal, l'article exact du régime de marge
  des agences de voyages, la date d'effet initiale des lettres L, N, O et P, le taux des
  déchets avant le 1er mars 2026 : non vérifiés.
* Le montant de la majoration IDFM appliqué en 2024 : non vérifié.
* Le prix moyen de l'électricité et du gaz des ménages en 2026 : non trouvé.
* La répartition du poste 07221 entre carburants : non trouvée.
* La masse volumique officielle du GPL carburant : non trouvée.
* Le SHA du dernier commit d'openfisca-france-indirect-taxation : non lu.
* TVA en Guyane et à Mayotte : non vérifiée.

## Sources

* INSEE, Budget de famille 2017 : <https://www.insee.fr/fr/statistiques/4648319> ;
  <https://www.insee.fr/fr/statistiques/fichier/4648319/TM106.csv> ;
  <https://www.insee.fr/fr/statistiques/fichier/4648319/metadonnees_bdf2017.csv>.
* Légifrance : art. 278-0 bis, 278-0 bis A, 279, 279-0 bis (liens au § 2.1) ; loi
  n° 2026-103 du 19 février 2026 :
  <https://www.legifrance.gouv.fr/jorf/article_jo/JORFARTI000053508213>.
* BOFiP : BOI-TVA-LIQ-30-20 (26 août 2026)
  <https://bofip.impots.gouv.fr/bofip/1496-PGP.html/identifiant%3DBOI-TVA-LIQ-30-20-20260826> ;
  BOI-RES-TVA-000209 (26 août 2026)
  <https://bofip.impots.gouv.fr/bofip/14705-PGP.html/identifiant=BOI-RES-TVA-000209-20260826> ;
  BOI-TVA-LIQ-30-10-10 (19 novembre 2025)
  <https://bofip.impots.gouv.fr/bofip/2033-PGP.html/identifiant=BOI-TVA-LIQ-30-10-10-20251119> ;
  BOI-TVA-LIQ-30-10-50 (19 juin 2024)
  <https://bofip.impots.gouv.fr/bofip/1724-PGP.html/identifiant=BOI-TVA-LIQ-30-10-50-20240619> ;
  BOI-TVA-LIQ-30-10-35 (29 juin 2022)
  <https://bofip.impots.gouv.fr/bofip/13623-PGP.html/identifiant=BOI-TVA-LIQ-30-10-35-20220629> ;
  BOI-TVA-LIQ-30-20-80 (10 mai 2023)
  <https://bofip.impots.gouv.fr/bofip/780-PGP.html/identifiant=BOI-TVA-LIQ-30-20-80-20230510> ;
  BOI-TVA-LIQ-40-10 (27 novembre 2024)
  <https://bofip.impots.gouv.fr/bofip/1449-PGP.html/identifiant=BOI-TVA-LIQ-40-10-20241127> ;
  BOI-TVA-LIQ-40-20 (13 novembre 2019)
  <https://bofip.impots.gouv.fr/bofip/1456-PGP.html/identifiant%3DBOI-TVA-LIQ-40-20-20191113> ;
  BOI-TVA-CHAMP-20-60-10 (24 juillet 2024)
  <https://bofip.impots.gouv.fr/bofip/2270-PGP.html/identifiant=BOI-TVA-CHAMP-20-60-10-20240724> ;
  BOI-TVA-CHAMP-30-10-20-10 (9 avril 2025)
  <https://bofip.impots.gouv.fr/bofip/1139-PGP.html/identifiant=BOI-TVA-CHAMP-30-10-20-10-20250409> ;
  BOI-RES-EAT-000240 (31 décembre 2025) <https://bofip.impots.gouv.fr/bofip/14903-PGP.html>.
* Ministère, « Guide 2026 sur la fiscalité des énergies », version du 22 juillet 2026 :
  <https://www.ecologie.gouv.fr/sites/default/files/documents/Guide%202026%20sur%20fiscalit%C3%A9%20des%20%C3%A9nergies.pdf>.
* Douane, circulaire du 30 septembre 2026 :
  <https://www.douane.gouv.fr/sites/default/files/ba_files/da/2026-09/BOD%20DetT%20octobre%202026.pdf>.
* CRE, communiqué du 16 juillet 2026 sur les tarifs réglementés :
  <https://www.cre.fr/fileadmin/Documents/Communiques_de_presse/2026/260716_CP_TRVE_Aout_2026.pdf>.
* DGEC, prix des produits pétroliers :
  <https://www.ecologie.gouv.fr/politiques-publiques/prix-produits-petroliers> ; fichier
  <https://www.ecologie.gouv.fr/sites/default/files/documents/Prix%20HTT%20et%20TTC%20depuis%20janvier%202020_0.xlsx>.
* SDES :
  <https://www.ecologie.gouv.fr/sites/default/files/documents/Prix%20des%20produits%20p%C3%A9troliers%20en%202024.pdf> ;
  <https://www.statistiques.developpement-durable.gouv.fr/prix-de-lelectricite-en-france-et-dans-lunion-europeenne-en-2024> ;
  <https://www.statistiques.developpement-durable.gouv.fr/prix-du-gaz-naturel-en-france-et-dans-lunion-europeenne-en-2024>.
* Note CMS sur la loi de finances pour 2026 :
  <https://cms.law/en/fra/news-information/mesures-diverses>.
* openfisca-france-indirect-taxation :
  <https://github.com/openfisca/openfisca-france-indirect-taxation> (fichiers lus par
  `raw.githubusercontent.com`, branche `master`, le 2 novembre 2026).
