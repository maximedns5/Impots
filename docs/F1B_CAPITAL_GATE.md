# Gate F1b — les revenus du capital sont-ils imputables depuis des données publiées ?

**Verdict : OUI pour les taux du PFU, NON pour la CDHR — et le NON tient à une raison
plus forte que la finesse des données.** Rien n'est construit au-delà de ce gate ; la
décision de construire appartient au propriétaire, avec ce document sous les yeux.

Le refus de l'article 2 dans `PLF2027_COVERAGE.md` a nommé le trou : la population ne
porte aucun revenu du capital. Avant d'accepter cela comme un mur, ce gate demande ce que
les données **publiées** permettent. La règle qui s'applique est celle de D-096 : les
microdonnées de revenus ne sont pas disponibles dans un avenir prévisible, donc la
question n'est pas « que ferait-on avec l'ERFS » mais « que peut-on faire sans ».

## 1. Ce qui est publié, exactement

Sources manifestées, DGFiP Statistiques n° 41 (novembre 2025), « L'impôt sur le revenu
2024 » : le document (`dgfip_stat_41_ir_2024.pdf`) et ses tableaux
(`dgfip_stat_41_ir_2024_tables.xlsx`).

**Le cahier des charges annonçait « des revenus de capitaux mobiliers par tranche de RFR ».
Ce n'est pas ce qui est publié**, et l'écart compte. Ce qui est publié est :

* **Tableau 1** — la décomposition nationale des revenus déclarés par catégorie : RCM
  **70,09 Md€** en 2024, +32,1 %, soit 4,55 % du revenu total déclaré. Un total, sans
  ventilation.
* **Tableau 2** — l'**IMPÔT** hors barème (PFU **agrégé avec la CEHR**, la parenthèse
  isolant la CEHR) par décile de RFR par part, **et — ce que je n'attendais pas — avec les
  lignes « dont dernier centième » et « dont dernier millième »**. La granularité publiée
  descend donc au millime, pas au décile.

Moyennes par foyer de l'impôt hors barème, telles que publiées :

| fractile de RFR par part | impôt hors barème moyen | dont CEHR |
|---|---|---|
| 1er dixième | 4 € | — |
| 9e dixième | 68 € | — |
| dernier dixième | 2 290 € | + 476 € |
| dont dernier centième | 19 423 € | + 4 754 € |
| dont dernier millième | 135 784 € | + 45 366 € |
| **total** | **10,32 Md€** | **+ 1,98 Md€** |

**L'assiette n'est pas publiée, elle est DÉRIVABLE.** Le PFU prend 12,8 % au titre de
l'IR, donc 10,32 Md€ / 0,128 ≈ **80,6 Md€** d'assiette implicite. Contrôle croisé contre
le tableau 1 : 70,09 Md€ de RCM plus une vingtaine de milliards de plus-values ≈ 89 Md€,
soit **9 % d'écart** — cohérent, l'écart s'expliquant par la part des RCM basculée au
barème sur option, que l'encadré 1 mentionne explicitement. Deux routes indépendantes vers
le même ordre de grandeur : c'est ce qui rend la dérivation utilisable plutôt que
plausible.

## 2. Pourquoi le PFU passe

**Le rendement d'un impôt PROPORTIONNEL ne dépend que de l'assiette totale de chaque
cellule, jamais de sa dispersion interne.** C'est toute l'affaire. Un taux de PFU porté de
12,8 % à 15 % coûte exactement `assiette × 2,2 points`, et cette assiette est publiée
(dérivée) au décile, au centile et au millime. L'artefact « tous les foyers d'une cellule
reçoivent la même base », qui est la limite connue de la machinerie d'imputation des
niches, **n'entame pas** ce calcul : la somme est la somme.

L'imputation utiliserait exactement la machinerie existante — opt-in, inscrite au registre
des dépenses, mêmes divulgations d'artefacts (uniforme dans la cellule, identités tirées
sur graine) que `niches.py`. Trois conséquences à énoncer si elle est construite :

* **Les totaux RCM seraient DÉPENSÉS.** `margins` gagnerait une entrée
  `use="calibration"`, et le rendement national du PFU ne pourrait plus jamais servir de
  preuve que quoi que ce soit est juste.
* **L'incidence resterait en marches d'escalier**, sur douze marches (dix déciles plus les
  deux fractiles du haut) au lieu de dix. Toute structure plus fine qu'une cellule est un
  artefact.
* **La CEHR doit être soustraite avant tout usage.** La colonne agrège PFU et CEHR ; les
  confondre surestimerait l'assiette de 19 % au total et bien plus dans le haut, où la
  CEHR pèse un tiers de la ligne au dernier millime.

## 3. Pourquoi la CDHR ne passe pas, et ce n'est pas une question de finesse

Le cahier des charges attendait un refus « parce que la CDHR mord dans le centile
supérieur, où une imputation par tranche est trop grossière pour être honnête ». **La
granularité publiée descend au millime, donc l'argument de finesse ne tient pas tel
quel — et le vrai refus est plus fort.**

La CDHR est un **complément différentiel** : elle porte le taux moyen d'imposition à 20 %
du RFR pour les foyers qui sont en dessous. Son assiette n'est donc pas un revenu, c'est
un **écart entre deux quantités** — un impôt payé et un impôt cible — et le fait de mordre
ou non dépend d'un **ratio** propre à chaque foyer.

Une imputation uniforme dans la cellule donne à chaque foyer du dernier millime **le même
revenu du capital, donc le même ratio**. Il en résulte que tous les foyers de la cellule
sont du même côté du seuil de 20 % : soit la CDHR frappe les 41 000 foyers du millime,
soit elle n'en frappe aucun, selon le côté où tombe la moyenne de la cellule. **Le
rendement chiffré serait un artefact du placement de cette moyenne, pas une mesure.** Il
sauterait de zéro à plusieurs milliards au franchissement d'un seuil que rien dans les
données ne fixe.

Ce n'est pas « trop grossier », c'est **mal posé** : la mesure est définie sur une
dispersion que la source ne contient pas, à quelque fractile que ce soit. Le rendement
publié de la CDHR — 1,5 Md€ pour l'article 2 du PLF 2026 — vient précisément de la queue
de composition des revenus à l'intérieur du haut de la distribution, qui est ce que les
moyennes par fractile effacent.

**La serrure reste donc les microdonnées**, et le refus est reconduit avec sa preuve.
C'est exactement la même forme que le plafond des dons Coluche (D-095) : un bouton correct
sur une assiette dont l'imputation a aplati la dispersion qui portait tout l'effet.

## 4. Ce que le gate décide, et ce qu'il ne décide pas

**Décidé — la question posée a une réponse :**

* une imputation RCM par fractile depuis des données publiées est **faisable et honnête
  pour un impôt proportionnel**, et le PFU en est un ;
* elle est **inutilisable pour la CDHR**, et pour toute mesure définie sur un seuil, un
  ratio ou un taux moyen individuel — ce qui inclut le plafonnement de l'IFI et toute
  contribution différentielle future ;
* le cahier des charges se trompait sur sa source (les RCM par tranche ne sont pas
  publiés ; l'impôt hors barème l'est) et sur la raison du refus attendu (ce n'est pas la
  finesse, c'est la nature de la grandeur). Les deux corrections sont dans ce document
  plutôt que dans une note de bas de page, parce que la seconde est réutilisable : elle
  vaut pour toute mesure future définie sur un ratio.

**Non décidé — appartient au propriétaire :**

* **construire ou non l'imputation RCM.** Le coût est un incrément, la machinerie existe
  et le patron d'imputation est éprouvé. Le prix est permanent : deux totaux de plus
  dépensés au registre de calibration, et une catégorie de revenu de plus dont la
  distribution intra-cellule est une fiction déclarée ;
* **si elle est construite**, elle débloque les boutons de taux du PFU au niveau
  population, la CSG sur les revenus du capital, et une part de l'incidence du haut de
  distribution que le module patrimoine ne peut pas atteindre aujourd'hui. Elle ne
  débloque pas la CDHR, et le document doit le dire à l'endroit où un bouton CDHR
  apparaîtrait.

## 5. Un prérequis de câblage, relevé en chemin

Si un bouton CDHR est un jour ajouté — après microdonnées — il faudra **d'abord** ajouter
une ligne CDHR au registre de sortie et à `STATE_RECEIPTS`. Mesuré (D-095) : porter
`taux_cdhr` de 20 à 30 % déplace `revenu_disponible` de 205 400 € sur un foyer test et
`impot_revenu_restant_a_payer` de rien du tout, parce que la CDHR entre dans
`impots_directs` mais pas dans la ligne que le registre publie comme `ir`. La garde de
partie double refuserait la course — comportement correct, et prérequis à satisfaire avant
que le bouton existe.

---

## 6. Ré-examen sur l'ERFS — le critère, préenregistré AVANT tout rendement

**Ce qui a changé, et pourquoi le refus ne peut pas être simplement reconduit.** Le refus
du §3 tient à une phrase précise : *« une imputation uniforme dans la cellule donne à
chaque foyer du dernier millime le même revenu du capital, donc le même ratio »*. C'est un
défaut de l'IMPUTATION, pas de la CDHR. L'ERFS porte de la dispersion réelle, foyer par
foyer, et non des moyennes de cellule — **donc cette raison-là disparaît**. Elle ne peut
pas être répétée ; la répéter serait maintenir un verdict après la disparition de son
motif.

Le déclencheur est inscrit dans le code lui-même : `plf_coverage.py` donne comme `unlock`
de l'article 2 « real income microdata (ERFS) ». La condition est remplie. Le ré-examen
n'est donc pas une faveur, c'est une obligation que le dépôt s'était imposée.

**Ce qui est déjà mesuré au moment où ces lignes sont écrites**, et qui ne porte donc
AUCUNE valeur probante — c'est dit plutôt que dissimulé : 198 ménages de l'ERFS déclarent
≥ 250 k€ (`revdecm`), 50 déclarent ≥ 500 k€, et 109 des premiers affichent un taux
apparent sous 20 %. La population n'est pas vide, et le plancher de divulgation ne la
refuse pas. **Le refus ne pourra donc pas s'appuyer sur la rareté.**

**LE CRITÈRE, préenregistré avant tout calcul de rendement.** La CDHR est reconstructible
sur l'ERFS si et seulement si une reconstruction fruste reproduit le rendement publié —
1,5 Md€, article 2 du PLF 2026 — **à un facteur 2 près**, soit la bande [0,75 ; 3,0] Md€.

Pourquoi un facteur 2 et non 10 % : les trois jambes sont des approximations déclarées et
chacune a un signe. `IRPP` est l'impôt SIMULÉ par l'INSEE, pas l'impôt liquidé par la
DGFiP ; `revdecm` est le revenu déclaré du MÉNAGE, pas le RFR retraité du FOYER ; et le
millésime 2022 précède la CDHR, dont les seuils sont NOMINAUX — un niveau de revenu
inférieur d'environ 8 % fait passer des foyers sous le seuil sans qu'aucune erreur de
modèle soit en cause. Une bande serrée mesurerait la somme de ces trois écarts, pas la
question posée. Un facteur 2 est assez large pour les absorber et assez étroit pour
échouer si la queue manque — **et c'est la queue qui est testée**, puisque le rendement de
la CDHR vient de la composition des revenus tout en haut.

**Ce critère peut échouer dans les deux sens, et les deux issues sont écrites d'avance :**

* **Dans la bande** — la reconstruction tient, la raison du §3 a disparu et rien ne l'a
  remplacée : **le gate s'ouvre**, l'article 2 change de `bucket`, et le refus est levé.
* **Hors bande** — le refus est reconduit, mais **pour un motif mesuré et non supposé**,
  et ce motif était lui-même préenregistré : le tableau de validation E2 classe le dernier
  centile en `no_verdict` parce que *l'ERFS sous-compte sa propre queue — une enquête ne
  voit pas le sommet, et c'est la raison d'être de la DGFiP n° 41*. La CDHR vit
  ENTIÈREMENT dans cette bande. Trancher sur elle reviendrait à rendre un verdict là où
  E2 s'est engagé, par commit et avant tout chiffre ERFS, à n'en rendre aucun.

L'implémentation qui ferait échouer ce critère est précisément celle qui compte : une
reconstruction dont la sélection ne mord sur personne rendrait 0,0 Md€, et une dont les
jambes sont mal posées rendrait un multiple. Les deux sortent de la bande, et aucune
tolérance ne sera élargie ensuite — l'élargir après coup serait décrire le résidu et
l'appeler un verdict.

## 7. Le verdict du ré-examen — le refus tient, mais plus rien de ce qui le portait

Trois jambes pouvaient porter un refus. **Deux cèdent**, et il faut le dire avant de
conclure : un refus qui survit parce qu'on n'a pas regardé ses appuis n'est pas un refus,
c'est une habitude.

**Jambe 1 — le rendement. ELLE NE PORTE PAS.** La reconstruction fruste préenregistrée
**sort de la bande [0,75 ; 3,0] de moins de deux pour cent**. Le rendement chiffré
n'est PAS reproduit ici, et la raison est au paragraphe suivant. La tolérance n'est pas élargie — mais un dépassement d'un pour cent ne
soutient aucune conclusion, et l'autopsie explique tout l'écart. *La livraison ne porte
aucune colonne d'impôt au prélèvement forfaitaire* : `rev_financier_prelev_lib_imputes`
est le REVENU soumis au prélèvement, jamais le prélèvement. La jambe fiscale était donc
amputée du PFU — 2,29 md€ sur les 70 ménages concernés — c'est-à-dire exactement l'impôt
que la CDHR compte dans son numérateur. Reconstitué à 12,8 %, le rendement **rentre dans la
bande** — chiffre non reproduit, même raison. *Post hoc, donc sans valeur probante pour le verdict* — mais
parfaitement probant pour ceci : **le rendement ne fournit pas de motif de refus.**

**Jambe 2 — le plancher de divulgation. ELLE NE PORTE PAS NON PLUS.** La sélection réelle laisse
**moins de 50 contributeurs** non pondérés : la garde refuse le tableau, et c'est le
comportement correct. Mais ce plancher est le NÔTRE — D-140 a établi
que la convention n'en fixe aucun — et au défaut de 11 ménages du cahier des charges, ces
36 passeraient. Un refus qui bascule avec un paramètre que nous avons choisi après coup
n'est pas un refus, c'est une préférence.

*Et au passage, le §6 s'est trompé.* Il annonçait que « le refus ne pourra pas s'appuyer
sur la rareté », sur la foi de 109 ménages sous 20 %. Ce 109 appliquait le seuil de 250 k€
à tout le monde ; le seuil légal est de 500 k€ pour un couple, et 22 472 des 42 831
ménages en sont un. La population tombe alors à 70 au-dessus du seuil, et les contributeurs sous le
plancher.
La rareté mord donc, exactement là où le préenregistrement disait qu'elle ne mordrait pas.
C'est consigné plutôt que corrigé en silence.

**Jambe 3 — la bande sans verdict d'E2. ELLE PORTE, ET ELLE EST LA SEULE.** Le tableau de
validation classe le dernier centile en `no_verdict`, et sa raison est textuelle :
*l'ERFS sous-compte sa propre queue — une enquête ne voit pas le sommet, et c'est la
raison d'être de la DGFiP n° 41*. La CDHR vit **entièrement** dans ce centile. Trancher
sur elle, c'est rendre un verdict précisément là où le dépôt s'est engagé, par commit et
avant tout chiffre ERFS, à n'en rendre aucun. C'est la seule des trois jambes qui ne
dépende d'aucun choix fait après avoir vu les données.

**Refus reconduit — sur la jambe 3 seule, et le motif du §3 est mort.** La CDHR n'est plus
« mal posée » : avec de la dispersion réelle, elle se pose très bien. Elle est
**inobservable dans cette source**, ce qui est une affirmation entièrement différente et
bien plus étroite.

**Conséquence sur la serrure, et c'est le vrai acquis.** D-096 nommait comme clé « des
microdonnées de revenus réelles, l'ERFS ». **La clé a été obtenue, essayée, et elle
n'ouvre pas.** Laisser cette clause en l'état ferait dire au code une chose fausse et
enverrait le prochain lecteur refaire ce chemin. La serrure n'est pas « des microdonnées »
— c'est **une source qui VOIT LE SOMMET** : l'échantillon lourd de la DGFiP, le fichier
POTE, un appariement exhaustif. Aucune enquête auprès des ménages n'ouvrira cette porte,
si fine que soit sa dispersion, parce que le défaut est dans son plan de sondage et non
dans sa granularité. `plf_coverage.py` est corrigé en conséquence.

## 8. Ré-examen de la couche PFU — elle s'ouvre, mais PAS par l'ERFS

Le §2 concluait que le PFU passe depuis les données publiées, parce que **le rendement
d'un impôt proportionnel ne dépend que de l'assiette totale**. Rien n'infirme cela, et
l'ERFS confirme l'ordre de grandeur : 71,6 md€ d'assiette capital des ménages ordinaires
en 2022, hors plus-values, contre ~80,6 md€ dérivés de la DGFiP n° 41 pour 2024 — 11 %
d'écart sur deux millésimes distants de deux ans et deux périmètres distincts. Deux routes
indépendantes, même ordre : la dérivation du §2 tient.

**Mais l'ERFS ne doit pas construire cette couche, pour deux raisons mesurées.**

**(1) 44,7 % de son assiette capital est IMPUTÉE, pas observée.** La décomposition :
39,63 md€ de valeurs mobilières brutes déclarées (15 245 ménages) contre **32,00 md€ de
revenus financiers au prélèvement libératoire imputés par l'INSEE** (30 824 ménages). Le
second terme n'est pas une observation : c'est le produit d'un modèle d'imputation de
l'INSEE. Bâtir la couche PFU dessus importerait ce modèle **en le présentant comme de la
microdonnée** — c'est-à-dire le défaut même que le §3 reprochait à l'imputation par
fractile, relocalisé et rendu invisible parce qu'il arrive sous une étiquette de
microdonnée. Le défaut déclaré est préférable au défaut hérité.

**(2) Le prix serait le tableau de validation lui-même.** E2 tient sa valeur d'un seul
fait : la population synthétique n'a JAMAIS été ajustée sur l'ERFS, sur aucun axe. Une
couche PFU bâtie sur l'ERFS ferait de l'ERFS une cible de calibration, et A1, A2 et A3
cesseraient le jour même d'être des verdicts — exactement ce qui est arrivé aux fractiles
de la DGFiP n° 41, dépensés par le recalage L1. On ne dépense pas le dernier comparateur
indépendant pour gagner 11 % de précision sur une assiette que la route publiée fournit
déjà.

**Verdict : la couche PFU s'ouvre sur la route PUBLIÉE du §2, et l'ERFS lui est réservée
comme VALIDATION.** C'est le rôle que l'axe A4 du tableau lui assigne déjà, mot pour mot :
« quelle PART des ménages ERFS porte un revenu du capital ». La réponse est mesurée et
consignée ici ; elle reste un constat, pas un verdict. La décision de construire appartient
au propriétaire, et E3 reste « rien ».

## 9. Un manquement, relevé sur nous-mêmes et corrigé

La première rédaction des §7 et §8 **portait les chiffres de la reconstruction CDHR** —
rendement, rendement corrigé, effectif des contributeurs. Or tous dérivent d'une cellule de
moins de 50 ménages, c'est-à-dire **sous le plancher que le paragraphe voisin invoquait**.
Écrire « la garde refuse ce tableau » au-dessus du tableau refusé est exactement la forme de
défaut que ce dépôt traque ailleurs : une règle énoncée et non appliquée à l'endroit où elle
s'applique. Les figures sont remplacées par des bandes ; l'écart à la bande préenregistrée
reste énonçable parce qu'il est qualitatif.

**Ce que ce manquement prouve, et ce qu'il ne prouve pas.** Il ne renforce PAS la jambe 2 :
au plancher de 11 du cahier des charges, ces effectifs passeraient, donc l'argument reste
suspendu à un paramètre que nous avons choisi. Mais il lie : notre plancher est 50, donc
**le gate CDHR ne peut pas publier sa propre preuve**. Un gate dont le résultat est
inmontrable sous ses propres règles n'est pas un gate qu'on rouvre à la légère — c'est une
raison de plus de garder la serrure fermée jusqu'à une source qui voit le sommet, où la même
sélection porterait des effectifs publiables.

**L'historique git conserve les figures retirées** (commit `0da23f4`). Le dépôt ne publie
rien et les données restent locales, mais le fait est consigné plutôt que tu : le
propriétaire décide s'il veut davantage.
