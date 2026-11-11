# Étape « ppa2 » du but 19 : le τ de la prime tranché, les jeunes actifs à part

Le 10 novembre 2026, branche `claude/but19-ppa2`, partie de `42db106` (D-369). Consigne :
`CONSIGNE_ETAPES.md` (N = ppa2). Lu : D-366 à D-369, `rsa_ppa.md`, `etape_4.md`,
`etape_ppa.md`, `etape_haut.md`. Aucune passe sur la population entière, aucune passe de la
grille officielle, aucune D-entrée ; `lignes.json` n'est pas touché. `incomes.py`,
`calibrate.py`, `to_openfisca.py`, `engine/corrections.py`, `aggregate.py` et `runner.py`
ne sont pas touchés. Les scripts d'essai sont dans le répertoire de travail de la session
(`ppa2/scripts/` : `fit_tau.py`, `mesure.py`, `compare.py`, `pronostic.py`, `etudes.py`).

**La réponse courte.**

* **Le τ est tranché.** Le n° 1379 a été lu (copie de l'Internet Archive). Ses tranches sont
  des montants **mensuels par unité de consommation** (note du graphique 1 et note 3, à
  l'échelle de `recours.unites`) : l'étape 4 lisait juste, l'ADCF abrégeait. Le graphique
  donne les six tranches des recourants et des non-recourants ; ajusté dessus, τ vaut 19,5
  à 25,7 € selon la façon de lire les tranches. **τ = 21 € reste** ; `p_max` recalé :
  0,5338.
* **Le reste de l'écart s'explique** en deux facteurs à peu près égaux : le modèle a 5 à
  11 % d'ayants droit de moins que la Drees (portée à 2024 et à la France entière), et la
  Drees elle-même ne retrouve que 73 à 83 % des foyers que la Cnaf paie au même trimestre.
  Calé sur le taux de la Drees, le modèle refait les recourants de la Drees, pas les
  payés de la Cnaf.
* **Un correctif, sourcé** : les jeunes de 18 à 24 ans qui travaillent chez leurs parents
  sont des foyers de la prime à part, comme la Drees les compte (n° 1379, encadré 3).
  Prime servie +5,7 %, foyers servis +8,0 % ; les moins de 25 ans servis passent de
  0,54 à 0,76 M (Cnaf : 0,77 M). Aucune ligne de la grille ne change de verdict.

## 1. Le τ du recours de la prime : la source, l'unité, l'ajustement

**La source.** Drees, Études et Résultats n° 1379 (juillet 2026, C. Gayet), 8 pages, lu
sur `web.archive.org/web/2026id_/https://drees.solidarites-sante.gouv.fr/sites/default/
files/2026-07/ER1379_Non-recours_PA.pdf` (sha256 `222853d7…`, déposé dans `data/raw` et
ajouté au manifeste). Le site de la Drees refuse toujours le conteneur ; l'archive, coupée
pour l'étape « ppa », répondait cette fois. Le fichier de données (`.xlsx`) n'est pas
archivé (404) : les tableaux complémentaires A à D ne sont pas lus.

**L'unité.** « Ce graphique présente la distribution des montants mensuels (par unité de
consommation) de droits à la prime d'activité » ; note 3 : 1 UC pour le premier adulte,
0,5 pour la personne suivante, 0,3 pour le premier enfant d'un couple ou le deuxième d'un
parent isolé, etc. C'est l'échelle de `recours.unites`. La presse (« par mois ») abrégeait.

**Le graphique 1** (fourchette haute : 3 203 k recourants, 3 426 k non-recourants) :

| € par mois et par UC | < 50 | 50-100 | 100-150 | 150-200 | 200-250 | 250-300 |
|---|---|---|---|---|---|---|
| recourants (%) | 20 | 24 | 22 | 18 | 11 | 3 |
| non-recourants (%) | 32 | 29 | 17 | 12 | 7 | 2 |
| éligibles (k) | 1 737 | 1 762 | 1 287 | 988 | 592 | 165 |
| recours | 0,369 | 0,436 | 0,547 | 0,584 | 0,595 | 0,584 |

**L'ajustement** (`fit_tau.py`, moindres carrés pondérés par les éligibles, `p_max` libre) :

| lecture des tranches | τ | p_max | recours ajusté, tranche par tranche |
|---|---|---|---|
| milieux, six tranches | 25,7 € | 0,542 | 0,34 ; 0,51 ; 0,54 ; 0,54 ; 0,54 ; 0,54 |
| milieux, cinq tranches | 25,3 € | 0,539 | |
| p moyen, uniformes, six | 19,5 € | 0,534 | 0,34 ; 0,52 ; 0,53 ; 0,53 ; 0,53 ; 0,53 |
| τ = 21 € (constante) | 21 € | 0,528 | 0,37 ; 0,51 ; 0,53 ; 0,53 ; 0,53 ; 0,53 |
| fourchette basse (hypothèse) | 23,7 € | 0,573 | les 470 k répartis comme les recourants |

τ = 21 € est dans l'intervalle et reste : **la constante ne change pas**. Le défaut est
dans la forme, pas dans τ : l'exponentielle sature trop vite (0,51 entre 50 et 100 € quand
la Drees lit 0,44 ; 0,53 au-delà de 150 € quand elle lit 0,58 à 0,60). Une forme à deux
pentes, ou un τ plus grand avec un plancher, suivrait mieux ; ce serait une hypothèse de
plus, à préenregistrer, pour un effet faible (le taux en foyers est calé : seule la
répartition du recours entre petits et grands droits change).

**`recours.caler`** (15 000 ménages, graine 20240101, droit 2024), sans changer les
constantes, donne :

| | p_max prime | recours en masse | p_max RSA | recours en masse |
|---|---|---|---|---|
| constantes actuelles (D-368, 20 000 ménages) | 0,5327 | | 0,6890 | |
| population de D-368 (avant) | 0,5349 | 52,7 % | 0,6893 | 67,8 % |
| avec les jeunes actifs (après) | **0,5338** | 52,6 % | **0,6893** | 67,8 % |
| après, τ = 19,5 € / 25,7 € | 0,5303 / 0,5453 | 52,3 / 53,3 % | | |

Le recours en masse de la prime reste sous la fourchette publiée (54 à 57 %) : le modèle a
trop peu de petits droits (19 % de ses ayants droit sous 50 € par UC, 27 % chez la Drees).
**Les valeurs à préenregistrer** : p_max 0,5338 (prime), 0,6893 (RSA), τ inchangés.

## 2. Ce qui explique le reste

Toutes les mesures de ce paragraphe sont sur l'échantillon (15 000 ménages, graine
20240101, droit 2024, palier complet, décembre), « après » le correctif du § 3 sauf
mention. Les comparateurs : Cnaf, PA Conjoncture n° 32, tableau 1 (T4 2024, moyenne du
trimestre, Caf, France entière) ; Cour des comptes dans le rapport du Sénat n° 728
(2025-2026), tableaux 12 et 13 (Cnaf, Allstat FR6, décembre 2023) ; Drees n° 1379,
tableau 2 (fourchette haute, T4 2021, métropole, logement ordinaire).

### 2.1 Le niveau : les recourants de la Drees ne sont pas les payés de la Cnaf

| T4 2021 | foyers |
|---|---|
| Drees, éligibles (fourchettes haute et basse) | 6,63 à 7,10 M |
| Drees, recourants | 3,20 à 3,67 M |
| Cnaf, payés, Caf, France entière (n° 32, graphique 2, lu sur le graphique) | 4,44 M |
| Cnaf, métropole (96,2 %), tous régimes (Caf = 97,0 %) | ≈ 4,40 M |

La Drees retrouve parmi ses éligibles 73 % (haute) à 83 % (basse) des foyers que les
caisses paient en métropole. Le reste est hors de son champ : les ménages non appariés au
DRM ou à écart de revenu inexpliqué (19 % de l'ERFS, repondérés), les hors-logement
ordinaire ; hypothèse non vérifiable ici, ces ménages à revenus instables sont plus souvent
allocataires que les autres. **Le taux de non-recours de 48 à 52 % est défini sur ce
champ.** Le modèle, calé sur lui, sert la moitié de ses ayants droit :

| 2024, France entière | foyers | écart |
|---|---|---|
| Drees portée à 2024 (× 1/0,962, les DOM ; × 4,628/4,44, les payés) | 7,19 à 7,70 M | |
| modèle, ayants droit, déc., avant / après | 6,37 / 6,86 M | −11 à −17 / −5 à −11 % |
| Drees, recourants portés | 3,47 à 3,98 M | |
| modèle, servis, avant / après | 3,17 / 3,42 M | −9 à −20 % / −1 à −14 % |
| Cnaf, payés T4 2024 | 4,63 M | −32 % / −26 % |

L'écart des servis (−26 % après) se partage en un manque d'ayants droit (−5 à −11 %) et
l'écart entre les recourants de la Drees et les payés de la Cnaf (−14 à −25 %).
Deux lectures, que rien ici ne départage : (a) la Drees sous-compte aussi les éligibles,
d'autant ; il y en aurait alors 9,2 à 9,8 M, et le modèle en manque 25 à 30 % ;
(b) les payés
hors du champ de la Drees sont des « faux bénéficiaires » ou des foyers que l'enquête ne
voit pas (DOM, foyers, résidences). Sous (a), la ligne servie ne tiendra qu'avec plus
d'ayants droit ; sous (b), elle ne tiendra jamais avec le taux de la Drees, et c'est la
cible du calage qui est à revoir (un taux « payés Cnaf / éligibles du modèle » ferait de
la ligne un calage, comme D-366 l'a refusé pour l'IS).

### 2.2 La structure : par configuration

| foyers servis (M) | Cnaf T4 2024 | avant | après | ayants droit après | recours Drees |
|---|---|---|---|---|---|
| hommes seuls | 1,302 | 0,810 | 0,939 | 1,878 | 0,41 |
| femmes seules | 1,301 | 0,832 | 0,927 | 1,836 | 0,55 |
| seuls avec enfant(s) | 0,970 | 0,478 | 0,486 | 0,973 | 0,65 |
| couples sans enfant | 0,258 | 0,331 | 0,337 | 0,665 | 0,41 |
| couples avec enfant(s) | 0,798 | 0,720 | 0,735 | 1,509 | 0,45 |
| ensemble | 4,628 | 3,171 | 3,423 | 6,861 | 0,48 |

« Recours Drees » : recourants sur éligibles par configuration, tiré du tableau 2 du
n° 1379 (parts des 3 203 k recourants et des 3 426 k non-recourants : hommes isolés 24 et
33 %, femmes isolées 26 et 20 %, mères isolées 16 et 6 %, pères isolés 2 et 3 %, couples
avec enfants 23 et 26 %, sans enfant 9 et 12 % ; l'en-tête du tableau dit « recourants au
RSA », une coquille). **Le recours du modèle ne dépend que du montant par UC** : il sert
la moitié de chaque configuration. Appliquer le recours de la Drees par configuration aux
ayants droit du modèle donnerait 0,76 ; 1,01 ; 0,63 ; 0,27 ; 0,68 M (3,36 M en tout,
calcul à la main) : les couples sans enfant tomberaient au niveau de la Cnaf (+31 → +6 %),
les familles monoparentales de −50 à −35 %, les femmes seules de −29 à −23 %. Le total ne
bouge pas. **Proposé, non fait** (il change la forme de `recours.py`, donc ses constantes).

**Ce qui manque en ayants droit** : les familles monoparentales surtout. Au recours de la
Drees (0,65), il en faudrait 1,49 M pour les 0,97 M que la Cnaf paie ; le modèle en a
0,97 M (−35 %). Les personnes seules : 1,88 et 1,84 M, pour 3,2 et 2,4 M qu'il faudrait au
recours de la Drees (hommes −41 %, femmes −22 %), mais le facteur de champ du § 2.1 y est
compris.

### 2.3 Les montants

| montant servi moyen, € | Cnaf | avant | après |
|---|---|---|---|
| ensemble | 200 (T4 2024) | 215 | 211 |
| hommes seuls | 149 | 157 | 154 |
| femmes seules | 156 | 169 | 167 |
| seuls avec enfant(s) | 271 | 222 | 222 |
| couples sans enfant | 201 | 263 | 263 |
| couples avec enfant(s) | 265 | 307 | 306 |

| foyers servis par montant (%) | Cour, déc. 2023 | avant | après |
|---|---|---|---|
| moins de 100 € | 29 | 23,2 | 23,4 |
| 100 à 199 € | 35 | 26,7 | 28,2 |
| 200 à 299 € | 20 | 28,3 | 27,9 |
| 300 à 399 € | 8 | 11,1 | 10,5 |
| 400 à 499 € | 5 | 6,1 | 5,7 |
| 500 € ou plus | 3 | 4,5 | 4,3 |

| ayants droit par montant par UC (%) | Drees, éligibles 2021 | après |
|---|---|---|
| moins de 50 € | 26,6 | 19,1 |
| 50 à 100 € | 27,0 | 21,1 |
| 100 à 150 € | 19,7 | 18,0 |
| 150 à 200 € | 15,1 | 17,6 |
| 200 à 300 € | 11,6 | 23,5 |

Les couples ont des montants trop hauts (+31 % sans enfant, +15 % avec), les familles
monoparentales trop bas (−18 %). Il manque des petits droits (moins de 100 € par UC :
40 % contre 54 %) : les foyers près de la sortie (personnes seules entre 1,2 et 1,5 Smic,
couples biactifs, 25 % des non-recourants de la Drees contre 15 % des recourants).

### 2.4 Le logement et le forfait logement

| foyers servis, logement (%) | Drees, recourants 2021 | avant | après |
|---|---|---|---|
| propriétaires | 20 | 32,7 | 34,7 |
| locataires | 65 | 61,8 | 57,9 |
| logés gratuitement (Drees) ; hébergés ou logés gratuitement (modèle) | 15 | 5,5 | 7,5 |

69 % des ayants droit ont un forfait logement (76 € en moyenne). Les propriétaires sont
trop nombreux (+15 points) : le forfait logement les tient à des montants plus bas, ce qui
va dans le sens des petits droits manquants mais pas des montants des couples. **Un défaut
du câblage, mesuré, non corrigé** : un adulte hébergé dans un logement loué
(`aide_logement_heberge`) n'a pas de forfait logement dans le moteur, qui lit le statut
d'occupation du ménage (locataire) ; la Caf le compte logé gratuitement. 5,7 % des ayants
droit après sont dans ce cas ; leur prime est trop haute d'au plus 75 € (personne seule).
Ordre de grandeur, hypothèse : −2 à −3 % sur la prime servie si l'on corrigeait. Le
correctif est dans `to_openfisca.py` (le statut d'occupation par famille), fichier d'un
autre agent : non fait.

### 2.5 Les revenus d'activité, l'âge, les étudiants

**Les revenus** (trimestre de référence, en part d'un Smic net de 1 398,70 €, hypothèse de
conversion) des ayants droit après : moins de 0,5 Smic 13,6 % ; 0,5 à 1 Smic 24,0 % ; 1 à
1,5 Smic 43,6 % ; 1,5 Smic ou plus 18,8 % (des couples). Les personnes seules ayants
droit : 17 % sous 0,5 Smic, 32 % de 0,5 à 1, 51 % de 1 à 1,5. La Cour ne cite que 39 % de
bénéficiaires au-dessus de 1 250 € en mars 2019 (environ 1,04 Smic net de 2019) ; le
modèle en a 62 % au-dessus de 1 Smic : trop de droits à revenus moyens, trop peu de très
petits salaires, ce que la Drees confirme par ses recourants à temps partiel (24 % des
personnes de référence salariées) et par 10,8 mois de salaire par an en moyenne chez les
recourants (le modèle : 92,6 % des ayants droit ont trois mois de revenu sur trois).
8,5 M de familles d'une personne ont un revenu d'activité dans le modèle (9,2 M après) ;
50 % sont à 1,5 Smic ou plus.

**L'âge** (servis, M) : moins de 25 ans 0,544 → 0,764 (Cnaf 0,766) ; 25-34 ans 0,85
(1,345, −36 %) ; 35-44 ans 0,73 (1,110, −34 %) ; 45-54 ans 0,60 (0,884, −33 %) ; 55 ans ou
plus 0,48 (0,523, −9 %). Le manque est maintenant entre 25 et 54 ans : les familles
monoparentales et les personnes seules d'âge actif.

**Les étudiants salariés.** La Cour compte 38 000 étudiants et 135 000 apprentis
allocataires en décembre 2024 (328 M€ par an). Le modèle ne sait pas qui est étudiant au
sens de la Caf : le plancher des apprenants (`ppa_eligibilite_apprenants`) ne joue pas,
et un étudiant salarié a sa prime dès le premier euro. Effet faible (au plus 3,7 % des
servis), non corrigé. À noter : openfisca fixe ce plancher à 55 % de 169 h de Smic, la
Cour écrit 0,78 Smic ; non vérifié dans le décret.

**Le cumul avec le RSA** : 9,1 % des servis avant, 8,4 % après (Cnaf 9,0 %).

## 3. Ce qui a changé, fichier par fichier

**`population/familles_jeunes.py`** (neuf). Chaque enfant de la famille de 18 à 24 ans
dont le revenu d'activité d'un mois travaillé (salaire de l'année sur ses mois de paie,
plus le douzième d'un revenu non salarié) dépasse 55 % de 169 h de Smic brut (1 082,87 €,
au Smic du 1er janvier 2024 : le plafond de l'enfant à charge des prestations familiales,
art. R. 512-2 du code de la sécurité sociale) devient demandeur d'une famille à lui,
hébergé chez ses parents, sans aide au logement (`aide_logement_heberge`). Ni son foyer
fiscal, ni son ménage, ni ses revenus ne bougent. Sur la population entière : 4 394
personnes, **0,70 M pondérées**.

* **Pourquoi.** Le squelette range parmi les enfants de la famille tout jeune de moins de
  21 ans chez ses parents, en emploi ou non. OpenFisca additionne les revenus d'activité
  de tous les membres de la famille dans la base de la prime (`ppa_revenu_activite`,
  `famille.sum`) : le salaire d'un jeune de 19 ans gonflait la base de ses parents, et
  lui n'avait jamais de prime. La prime est ouverte dès 18 ans depuis 2016 ; la Drees
  compte « tous les jeunes actifs » en foyers sociaux autonomes (n° 1379, encadré 3), et
  le taux de non-recours que `recours.PPA` refait est mesuré sur ces foyers.
* **Le seuil.** Sans lui (la règle de la Drees : tout revenu d'activité), les
  allocations familiales perdaient 3,1 % sur l'échantillon : un job d'été retirait
  l'enfant à ses parents. Avec lui, elles perdent 1,9 % : openfisca ne lit pas le revenu
  des 16-19 ans pour les prestations familiales (`autonomie_financiere`, jamais renseigné)
  et comptait à charge des jeunes payés au-delà du plafond ; la loi ne le fait pas.
* **Hypothèses, dites dans le module** : le seuil lu sur le mois moyen travaillé, quand la
  Caf le lit mois par mois ; le forfait logement manquant des hébergés en logement loué
  (§ 2.4) ; l'étudiant non distingué (§ 2.5).

**`population/build.py`** : `attach_familles_jeunes` après `attach_mois_travailles` ; ses
statistiques au manifeste de la population. **La population doit être reconstruite**
(`make data`) pour que le correctif joue : la population de `data/processed` ne le porte
pas. Les mesures ci-dessous l'appliquent à la population de D-368 avant l'échantillon.

**`population/recours.py`** : les commentaires et la source de `PPA` disent le n° 1379 lu,
son graphique 1 et l'ajustement ; **aucune constante ne change** (τ, p_max).

**`data/raw/MANIFEST.json`** : `drees_er1379_non_recours_ppa.pdf` (fichier réel dans le
`data/raw` de ce worktree).

**Tests** : `tests/test_familles_jeunes.py` (2) ; la fixture de `test_population.py` passe
par le module, comme la construction.

**La jonction.** Un appel ajouté dans `build._build`, juste après celui des mois
travaillés ; aucun fichier d'un autre agent n'est touché.

## 4. Les mesures, avant et après

15 000 ménages (`runner.subsample`, graine 20240101), droit 2024, palier complet, sans
imputation, comme la passe de la grille. « Avant » : la population de D-368 telle quelle.
« Après » : la même, passée par `attach_familles_jeunes` avant l'échantillon (les mêmes
ménages). **Ces mesures ne sont pas aveugles** : le seuil a été choisi en regardant les
allocations familiales de l'échantillon (§ 3).

| mesure, 2024 | publié | avant | après | effet |
|---|---|---|---|---|
| prime servie en espérance, Md€ | 10,28 | 7,67 (−25,4 %) | 8,11 (−21,1 %) | +5,7 % |
| prime, droit, Md€ | | 14,62 | 15,46 | +5,7 % |
| prime, droit / 1,725 | 10,28 | 8,48 (−17,6 %) | 8,96 (−12,8 %) | |
| foyers servis de la prime, déc., M | 4,628 | 3,171 (−31,5 %) | 3,423 (−26,0 %) | +8,0 % |
| ayants droit de la prime, déc., M | (4,628) | 6,368 | 6,861 | +7,7 % |
| montant moyen servi, € | 200 | 215 | 211 | −2,1 % |
| RSA servi en espérance, Md€ | 11,79 | 11,90 | 11,90 | +0,05 % |
| foyers servis du RSA, M | 1,826 | 1,773 | 1,773 | 0 |
| allocations familiales, Md€ | 13,77 | 11,88 (−13,7 %) | 11,64 (−15,4 %) | −1,9 % |
| aides au logement, Md€ | 15,67 | 11,68 | 11,69 | +0,1 % |
| IR au barème (`ir_avant_niches`), Md€ | 98,84 | 103,77 | 103,76 | −0,003 % |
| niveau de vie médian servi, € | 26 740 | 24 561 | 24 548 | −0,05 % |
| niveau de vie, D1 servi, € | | 12 736 | 12 736 | 0 |

Par configuration et par âge : § 2.2 et § 2.5. **La grille sur 15 000 ménages**, avant et
après (`grille_ech.py`), dit le même effet sur 2022 et 2023 : prime servie +4,2 ; +4,0 ;
+4,3 points du publié (2022, 2023, 2024) ; foyers servis +5,5 ; +5,4 ; +5,5 ; ayants
droit sans pont +10,7 ; +10,5 ; +10,6 ; prime au pont +4,6 ; +4,5 ; +4,7 ; allocations
familiales −1,6 ; −1,6 ; −1,7. Aucune autre ligne ne bouge de 0,3 point. La sortie après
est `docs/diagnostics/grille_ech_ppa2.json`.

## 5. Le préenregistrement proposé

**Les constantes du recours** (recalées, § 1) : `PPA.p_max` 0,5338, `RSA.p_max` 0,6893,
τ inchangés (21 € et 79 €), sur la population reconstruite avec ce correctif ; à refaire
par `recours.caler` sur la population entière reconstruite.

**Des lignes neuves, en contexte** (la passe ne les mesure pas encore : il faut ajouter à
`verification.py` le compte des foyers servis de décembre par âge et par configuration ;
non fait). Source : Cnaf, PA Conjoncture n° 32, tableau 1, T4 2024, moyenne du trimestre,
Caf, France entière (déjà au manifeste) ; T4 2023 et 2022 dans les numéros 28 et 24, non
lus ici :

| id proposé | publié 2024 | attendu (après) | usage |
|---|---|---|---|
| `ppa_foyers_servis_moins_25_ans` | 766 k | 764 k (−0 %) | contexte |
| `ppa_foyers_servis_hommes_seuls` | 1 302 k | 939 k (−28 %) | contexte |
| `ppa_foyers_servis_femmes_seules` | 1 301 k | 927 k (−29 %) | contexte |
| `ppa_foyers_servis_seuls_avec_enfants` | 970 k | 486 k (−50 %) | contexte |
| `ppa_foyers_servis_couples_sans_enfant` | 258 k | 337 k (+31 %) | contexte |
| `ppa_foyers_servis_couples_avec_enfants` | 798 k | 735 k (−8 %) | contexte |

Ce sont elles qui disent où manque la prime ; le total ne le dit pas.

**Le pronostic**, ligne par ligne : l'écart de la population entière à D-369 (même code,
hors ce correctif), décalé de l'effet mesuré sur l'échantillon (après − avant, la grille
sur 15 000 ménages, les trois années), élargi des marges de D-368 (5 points pour les
minima sociaux, les aides au logement et les allocations familiales ; 5, 10 et 25 pour les
tranches à 30, 41 et 45 % ; 4 pour l'IR ; 0,5 pour les entreprises ; 3 ailleurs). Pas
aveugle : l'effet vient du même échantillon que les mesures. 2022 et 2023 mesurés, non
estimés. « h » : le centre est hors de la tolérance. Il annonce **79 lignes sur 113** dans
leur tolérance, comme D-369 : aucune ne change de verdict. Le fichier est
`docs/diagnostics/pronostic_ppa2.json`.

| ligne | tol. | effet | 2022 | 2023 | 2024 |
|---|---|---|---|---|---|
| `cotisations_salariales` | 10 | 0 | −11 à −5 | −13 à −7 | −14 à −8 h |
| `cotisations_employeurs` | 15 | 0 | +23 à +29 h | +22 à +28 h | +20 à +26 h |
| `reduction_generale` | 15 | 0 | +13 à +19 h | +10 à +16 | +11 à +17 |
| `bandeau_maladie` | 15 | 0 | +21 à +27 h | +19 à +25 h | +18 à +24 h |
| `bandeau_famille` | 15 | 0 | +26 à +32 h | +23 à +29 h | +23 à +29 h |
| `csg_activite` | 15 | 0 | −10 à −4 | −9 à −3 | −10 à −4 |
| `csg_remplacement` | 10 | 0 | −6 à +0 | −4 à +2 | −8 à −2 |
| `foyers_fiscaux` | 10 | 0 | −8 à −2 | −9 à −3 | −10 à −4 |
| `foyers_imposes` | 10 | 0 | +12 à +18 h | +9 à +15 h | +4 à +10 |
| `foyers_tmi_0` | 15 | 0 | −13 à −7 | −14 à −8 | −12 à −6 |
| `foyers_tmi_1` | 15 | 0 | −13 à −7 | −14 à −8 | −15 à −9 |
| `foyers_tmi_2` | 15 | 0 | +19 à +29 h | +18 à +28 h | +11 à +21 h |
| `foyers_tmi_3` | 30 | 0 | −17 à +3 | −13 à +7 | −15 à +5 |
| `foyers_tmi_4` | 30 | 0 | −21 à +29 | −12 à +38 | −10 à +40 |
| `salaires_declares` | 10 | 0 | −10 à −4 | −11 à −5 | −11 à −5 |
| `niveau_de_vie_median` | 15 | 0 | −8 à −2 | −9 à −3 | −10 à −4 |
| `d9_d1` | 15 | 0 | −10 à −4 | −13 à −7 | −13 à −7 |
| `rsa_montant` | 14 | 0 | +3 à +13 | +5 à +15 | +8 à +18 |
| `ppa_montant` | 13 | +5 | −21 à −11 h | −23 à −13 h | −20 à −10 h |
| `aide_logement_montant` | 25 | 0 | −34 à −24 h | −33 à −23 h | −32 à −22 h |
| `af_montant` | 25 | −2 | −22 à −12 | −22 à −12 | −20 à −10 |
| `ppa_foyers` | 25 | +11 | +43 à +53 h | +36 à +46 h | +40 à +50 h |
| `is` | 20 | 0 | −20 à −19 | −1 à −0 | +1 à +2 |
| `contribution_sociale_is` | 25 | 0 | −21 à −20 | +33 à +34 h | +20 à +21 |
| `c3s` | 25 | 0 | +11 à +12 | +6 à +7 | +1 à +2 |
| `ir_bareme` | 10 | 0 | — | +1 à +9 | −3 à +5 |
| `rsa_foyers` | 25 | 0 | — | +47 à +57 h | +48 à +58 h |
| `cvae` | 25 | 0 | — | — | −16 à −15 |
| `cotisations_employeurs_d121` | 15 | 0 | −3 à +3 | −4 à +2 | −6 à −0 |
| `csg_activite_avec_non_salaries` | 15 | 0 | −5 à +1 | −4 à +2 | −5 à +1 |
| `d9_d1_servi` | 15 | 0 | −5 à +1 | −7 à −1 | −8 à −2 |
| `foyers_fiscaux_residents_hors_mayotte` | 10 | 0 | — | — | −9 à −3 |
| `impots_salaires_calcules` | 20 | 0 | −6 à −0 | −6 à −0 | −7 à −1 |
| `ir_net` | 15 | 0 | +8 à +16 | +10 à +18 | +6 à +14 |
| `niveau_de_vie_median_servi` | 15 | 0 | −8 à −2 | −10 à −4 | −11 à −5 |
| `ppa_foyers_servis` | 25 | +5 | −31 à −21 h | −34 à −24 h | −32 à −22 h |
| `ppa_montant_servi` | 13 | +4 | −29 à −19 h | −31 à −21 h | −28 à −18 h |
| `revenus_non_salaries_hors_gerants` | 15 | 0 | +1 à +7 | +3 à +9 | −6 à +0 |
| `rsa_foyers_servis` | 25 | 0 | — | −6 à +4 | −5 à +5 |
| `rsa_montant_servi` | 14 | 0 | −6 à +4 | −4 à +6 | −2 à +8 |

`ppa_foyers` (ayants droit sans pont, contre des payés) s'éloigne encore : il ne mesure
pas ce qu'il compare. `ppa_foyers_servis` 2022 touche sa borne (−26 ± 5 pour 25). La prime
servie reste hors de sa tolérance de 13 points d'environ 10 points (§ 2.1).

## 6. Ce que l'étape fait aux études

Mesuré sur l'échantillon (15 000 ménages, droit 2026 sur la population de 2024 figée,
`run` avec la réforme du scénario, delta servi en espérance ; `etudes.py`), avant et après.
La vue vieillie et la boucle macro ne tournent pas ici.

| scénario | volet prime, avant | après | effet |
|---|---|---|---|
| PLFSS 2027, art. 74, prime (miroir) | +543 M€ | +576 M€ | +6,0 % |
| Attal, A16, droit au brut : baisse de prime | −1 441 M€ | −1 545 M€ | +7,2 % |
| Retailleau, R19 : baisse de prime | −268 M€ | −285 M€ | +6,4 % |
| Lisnard, L1, CSG d'activité à 6,6 % | non mesuré | | |

* **L'art. 74** s'éloigne un peu de son chiffrage officiel (332 M€ en 2027, quatre mois ;
  le cas en compte sept, d'où l'écart de base) : +6 % sur le volet prime. Le pont des
  ayants droit au servi ne change pas la conclusion de l'étape 4.
* **Les baisses de prime des programmes** grossissent de 6 à 7 % : 17 à 100 M€ sur des
  deltas de 0,3 à 1,5 Md€ servis. Aucun verdict ne devrait bouger ; leur part dans le
  coût total est petite.
* **Lisnard** : la passe nue de l'échantillon s'arrête sur le garde-fou de l'identité
  comptable (`SectorBalanceError`, un écart de 1,27 Md€ entre le coût et ses postes),
  avant comme après ce correctif ; la série des études le passe par son propre chemin.
  Effet attendu du même ordre (+6 à 7 % sur le volet prime), non mesuré.
* **Les allocations familiales** (−1,9 %) : une réforme des AF coûterait un peu moins.
* **Le RSA, l'IR, les niveaux de vie** : effets de moins de 0,1 %.

## 7. Ce qui reste, les doutes, les sources non lues

* **Le niveau de la prime** (§ 2.1) : tant que le recours est calé sur le taux de la
  Drees, la prime servie suit les recourants de la Drees, 14 à 25 % sous les payés de la
  Cnaf. À décider : garder la cible (la ligne reste hors), ou ajouter au modèle les
  éligibles hors du champ de la Drees (lecture (a)), ce qui demande une source.
* **Le recours par configuration** (§ 2.2), publié, proposé, non fait.
* **Le forfait logement des hébergés** (§ 2.4) : −2 à −3 % estimé, dans `to_openfisca.py`.
* **Les familles monoparentales** : −35 % d'ayants droit et un montant trop bas de 18 % ;
  les couples ont des montants trop hauts. Non expliqué ici : la pension alimentaire et
  l'ASF (dans la base des prestations familiales), la majoration pour isolement (4,7 % des
  foyers Cnaf), le partage de l'emploi dans le couple sont les pistes.
* **Les petits droits manquants** et les revenus d'activité trop réguliers (§ 2.5) : le
  volume de travail de l'étape « ppa » reste à 0,846 contre 0,77 à l'Insee.
* **La forme exponentielle** du recours (§ 1).
* **Non lus** : le fichier de données du n° 1379 (404 sur l'archive), les tableaux
  complémentaires A à D ; le Drees Méthodes « à paraître » ; les PA Conjoncture de T4
  2021 à 2023 (le nombre de T4 2021, 4,44 M, est lu sur le graphique 2 du n° 32) ; le
  décret du plancher des apprenants.

## 8. Les tests lancés

* `tests/test_familles_jeunes.py` (neuf, 2 tests) : seuls les jeunes de 18 à 24 ans au-delà
  du seuil sortent, demandeurs, hébergés, et rien d'autre ne bouge ; un jeune sorti a une
  prime à son nom et son salaire quitte la base ressources de ses parents. Sur le code
  d'avant, le module n'existait pas : les deux échouent à l'import.
* `PYTHONPATH=src .venv/bin/python -m pytest -m "not lourd and not chrono" -n 2` sur
  test_recours, test_familles_jeunes, test_population, test_emploi_discontinu,
  test_prestations, test_verification : **143 passés** (2 min 13 s) ; test_donnees,
  test_provenance, test_charter (le manifeste) : **54 passés**.
* `ruff check` des fichiers touchés : propre. Non lancés : les lourds, `make impact`, la
  grille officielle (consigne).
