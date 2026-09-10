# Charte de maintenance

Ce document est de l'**infrastructure**, pas de la documentation : il décrit des rituels
qui s'exécutent, et il reçoit à ce titre le même traitement que du code de modèle — les
trois questions permanentes, des gardes qui tombent, et une entrée D quand il change.

La doctrine tient en une phrase : **une modification de maintenance suit exactement les
mêmes règles qu'une construction.** Rien n'est « juste une mise à jour ». Les pires défauts
de ce projet sont arrivés par des chemins qui avaient l'air routiniers — un paramètre lu
comme une chaîne, un en-tête d'unité qui ment, un garde qui ne pouvait pas échouer.

---

## 1. Le rituel de montée de version d'openfisca

**Cadence : délibérée, environ mensuelle. Jamais automatique.** Une montée de version
d'openfisca-france change le droit que ce modèle applique ; l'appliquer sans regarder
reviendrait à changer la loi par inadvertance.

1. Monter la version **dans une branche**, jamais sur `main`.
2. `make full`. Une ligne du journal de passe, fraîche, avant tout jugement.
3. **Lire les échecs comme des changements de droit avant de les lire comme des
   régressions.** Un golden qui bouge parce qu'un barème a été indexé n'est pas cassé : il
   est périmé.
4. **Ré-ancrer un golden UNIQUEMENT avec une entrée D citant le texte qui l'a déplacé.**
   Pas de reformulation, pas de « mise à jour des valeurs attendues » : le numéro de
   l'article, la date, et ce qu'il change. Un golden ré-ancré sans citation est un test
   qu'on a fait taire.
5. Relancer les scripts `verify_*.py`. Ils existent pour ce moment : ce sont les constats
   des gates devenus rejouables.
6. Vérifier que les **artefacts amont** tiennent toujours. Le registre est la table de
   `docs/UPSTREAM_ISSUE_DRAFT.md` — **six constats côté `openfisca-france` plus un côté
   `openfisca-core`** — et non une liste recopiée ici, qui divergerait. Ils sont mesurés en
   D-064, D-075, D-079, D-081 et D-090, et le dossier est clos par D-091. Chacun porte son
   kill test ; **s'il passe au vert, l'amont a corrigé le défaut et c'est une entrée D**,
   pas un test à supprimer.

## 2. Le cycle annuel des lois de finances

Chaque LF, dans cet ordre :

1. Les paramètres arrivent **par la montée de version**, pas à la main. Écrire une valeur
   de LF directement dans l'arbre reviendrait à créer une source de vérité concurrente.
2. **Un cas de chiffrage par article exprimable**, selon la règle de re-balayage : les
   leviers ayant changé, des articles jusque-là inexprimables peuvent l'être devenus.
3. **Le triage de couverture est archivé et NOTÉ.** L'exercice n'a de valeur que confronté :
   ce qu'on avait dit pouvoir chiffrer, ce qu'on a chiffré, et l'écart.
4. Les chiffrages préenregistrés de l'année sont notés contre les évaluations préalables
   puis contre le réalisé. **La tolérance ne bouge pas** — `verify_tolerance_unchanged` le
   vérifie dans l'historique git, pas dans le fichier.

## 3. Le calendrier de rafraîchissement des millésimes

Une source périmée ne prévient pas. Ce calendrier dit quand regarder ; la mise à jour du
manifeste **est** le rituel — un fichier remplacé sans son sha256 et son URL n'est pas
manifesté, il est présent.

| Source | Publication habituelle | Ce qu'elle alimente |
|---|---|---|
| DGFiP Statistiques — impôt sur le revenu | novembre | réconciliation IR, tranches de RFR |
| DGFiP Statistiques — taxe foncière | mai | comparateur F5 |
| REI (fiscalité directe locale) | mai | cellules F5 |
| DGFiP Statistiques — impôts de production | courant d'année | cellules entreprises |
| DGFiP Statistiques — IFI | avril | cellules patrimoine |
| INSEE Ésane / entreprises | annuel | cellules entreprises |
| INSEE Filosofi | annuel | marges de population |
| INSEE TES | annuel | couche macro |
| PLF + évaluations préalables + RESF | octobre | F1, comparateurs |

**La règle du pointeur s'applique à chaque rafraîchissement** : on transmet des
identifiants — titre, éditeur, numéro, date, sujet du tableau, sha256 — jamais une URL nue
comme référence porteuse. Une URL trouvée dans un index de recherche peut être périmée
alors que l'index la sert encore ; le chemin courant se relève sur la page de publication
de l'éditeur.

**Et la règle des ancres** : une route, un jeu de données ou un point d'accès inscrit dans
une spec est **mesuré avant d'être écrit** quand mesurer est bon marché, et **étiqueté NON
MESURÉ** sinon.

## 4. La cadence de passe complète

`make full` avant tout commit de fond, et **la ligne du journal doit être plus récente que
le travail qu'elle couvre**. La cible sait échouer — vérifié dans les deux sens — depuis
qu'elle a été corrigée d'une lecture de `$?` après un tube qui ne rendait que PASS.

Les tests de rythme sautent quand la machine est chargée. C'est voulu : un test de budget
temporel qui passe partout ne mesure rien. Un gate lancé pendant qu'autre chose tourne
rendra donc « 5 skipped » plutôt que « 2 », et **ce n'est pas vert au même sens** — les
relancer au repos, ou le dire.

## 5. Les questions permanentes, posées à toute modification

1. **Ce contrôle a-t-il un dénominateur qui peut tendre vers zéro ?** (D-093)
2. **Ai-je testé le correctif sur une autre forme que celle qui m'a alerté ?** (D-094)
3. **Ai-je déjà vu ce contrôle échouer ?** (D-094) — c'est celle qui a trouvé les quatre
   contrôles inertes d'une seule session, et son corollaire : **vérifier que la mutation
   fait bien ce qu'on croit** avant de conclure qu'un test est faible.
4. **De quoi ce nombre est-il la différence, exactement ?** (D-095) — née de deux fausses
   alertes le même jour, toutes deux « comparer une chose à elle-même ».
5. **D'où viennent les paramètres de ce test paramétré ?** (D-098) — s'ils viennent du code
   testé, le test ne peut pas échouer quand ce code est faux.

## 6. Ce que la maintenance ne fait jamais

* **Élargir une tolérance pour faire passer une ligne.** Une ligne rouge est un constat à
  écrire. Une tolérance élargie après coup transforme chaque manqué en réussi et laisse un
  fichier trait pour trait identique à un fichier honnête.
* **Supprimer un test devenu gênant.** S'il gêne, c'est qu'il dit quelque chose.
* **Recopier un chiffre depuis un cahier des charges, un résumé ou une recherche.** Les
  nombres remémorés sont des graines de recherche et rien de plus — huit erreurs de
  relecteur l'ont établi, chacune rattrapée par la machinerie ou par une session refusant
  de croire sur parole.
* **Publier quoi que ce soit.** La section publication reste gelée par le propriétaire.
