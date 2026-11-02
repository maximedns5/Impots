#!/usr/bin/env python
"""Regenerate docs/PLF2027_COVERAGE.md from the checked triage table.

The document is generated rather than written so its numbers cannot drift from the rows
they summarise — the mechanism the review asked to spread to every hand-written figure in
`reports/`. Editing the .md by hand is a mistake: edit `src/impots/plf_coverage.py`, which
the tests check against the code it describes, and run this.
"""

from __future__ import annotations

from pathlib import Path

from impots.plf_coverage import (
    ARTICLE_74_2027,
    ARTICLES,
    ARTICLES_2027,
    ARTICLES_PLFSS_2027,
    DATE_TRIAGE_2027,
    DATE_TRIAGE_PLFSS_2027,
    MONTANTS_2027,
    NO_FICHE,
    OUVERTURES_PLFSS_2027,
    SANS_FICHE_2027,
    SOURCE,
    SOURCE_2027,
    SOURCE_ANNEXE_2027,
    SOURCE_PLFSS_2027,
    YIELD_AMBIGUOUS,
    articles_hors_denominateur_2027,
    chiffres_apres_annexe_2027,
    engine_ready_but_blind,
    montants_2027,
    portes_2027,
    portes_plfss_2027,
    priceable_2027,
    priceable_today,
    priceable_yield_meur,
    priced_yield_2027_meur,
    quantified_yield_2027_meur,
    quantified_yield_meur,
    refus_mesures_2027,
    share_of_yield,
    share_of_yield_2027,
    share_of_yield_2027_si_ecrits,
    share_priceable,
    volets_non_chiffres_2027,
)

CASE = {"priceable_now": "**chiffrable**", "small_knob": "petit bouton",
        "population_blind": "population aveugle", "not_priceable": "non chiffrable"}
OUT = Path(__file__).resolve().parents[1] / "docs" / "PLF2027_COVERAGE.md"


def pct(x: float) -> str:
    """A percentage in French: comma decimal, non-breaking space before the sign."""
    return f"{x * 100:.1f}".replace(".", ",") + "\u00a0%"


def meur(x: float) -> str:
    """Millions of euros with French thousands separators."""
    return f"{x:,.0f}".replace(",", "\u00a0") + "\u00a0M EUR"


def m2027(x: float) -> str:
    """A 2027 amount in millions: no decimal when whole, one otherwise."""
    text = f"{x:,.0f}" if x == round(x) else f"{x:,.1f}"
    return text.replace(",", "\u00a0").replace(".", ",")


def french(count: int) -> str:
    words = {1: "un", 2: "deux", 3: "trois", 22: "vingt-deux", 23: "vingt-trois",
             24: "vingt-quatre", 25: "vingt-cinq", 26: "vingt-six"}
    return words.get(count, str(count))


def build() -> str:
    lines: list[str] = []
    w = lines.append
    total = len(ARTICLES)
    priceable = len(priceable_today())
    blind = len(engine_ready_but_blind())
    refused = sum(1 for a in ARTICLES if a.bucket == "not_priceable")
    out_of_reach = refused - blind

    w("# Triage de couverture — quels articles d'un PLF cet outil sait-il chiffrer ?")
    w("")
    w("**Généré depuis `src/impots/plf_coverage.py` par `scripts/write_plf_coverage.py`.**")
    w("Chaque nombre de ce document est calculé depuis la table ; aucun n'est saisi. Et")
    w("chaque affirmation de la table sur le code — un bouton nommé, un chemin de")
    w("paramètre — est vérifiée par `tests/test_plf_coverage.py`, parce qu'un triage qui")
    w("dérive du code qu'il décrit est pire que pas de triage : il sera cru le jour J.")
    w("")
    w("## Pourquoi maintenant, et pourquoi sur le PLF 2026")
    w("")
    w("Le PLF 2027 arrive début octobre. Décider ce jour-là ce que l'outil sait chiffrer,")
    w("c'est le décider sous pression et la réponse déjà sous les yeux — la condition")
    w("exacte où « on n'a pas su chiffrer X » devient une excuse au lieu d'une limite.")
    w("Décidé maintenant, chaque refus est **préenregistré**.")
    w("")
    w("Le texte 2027 n'existe pas et deviner ses numéros d'articles serait la fabrication")
    w("que ce projet interdit. Ce qui survit à une renumérotation, c'est la **catégorie** :")
    w("les catégories sont le livrable, les numéros 2026 n'en sont que la preuve.")
    w("")
    w(f"> {SOURCE}")
    w("")
    w("## Le chiffre, et il est mauvais")
    w("")
    w(f"Sur **{total} articles fiscaux** d'un vrai PLF, **{priceable}** produit aujourd'hui")
    w(f"un chiffre que cet outil peut défendre — soit **{pct(share_priceable())}**.")
    w(f"**{french(blind).capitalize()} autres** ont leurs paramètres dans l'arbre mais")
    w("aucun contribuable dans cette population pour les exercer : les câbler publierait un")
    w(f"zéro confiant. Les **{french(out_of_reach)}** restants sont hors de la structure du")
    w("modèle ou hors de ses données.")
    w("")
    w(f"Un outil qui prétendrait chiffrer tout un PLF mentirait sur {french(refused)}")
    w("articles. Ce document existe pour que ce chiffre soit connu en septembre plutôt")
    w("qu'en octobre.")
    w("")
    w("## Le second chiffre, qui dit le contraire du premier")
    w("")
    w("Compter les articles met un droit de timbre au même poids qu'une contribution à")
    w("quatre milliards. Compter les euros ne le fait pas — et l'ordre s'inverse.")
    w("")
    from impots.plf_coverage import YIELDS_2026_MEUR

    w(f"L'annexe des évaluations préalables **ne chiffre que {len(YIELDS_2026_MEUR)}")
    w(f"articles sur {total}** : {len(NO_FICHE)} n'ont aucune fiche (l'obligation organique")
    w("ne couvre pas les dispositions du domaine exclusif des lois de finances) et")
    w(f"{len(YIELD_AMBIGUOUS)} portent une fiche dont le montant n'est pas déterminable —")
    w("« non chiffrable » selon l'annexe elle-même, ou contradictoire.")
    w("")
    w(f"Sur les **{meur(quantified_yield_meur())}** d'impact première année que l'annexe")
    w(f"quantifie, cet outil en chiffre **{meur(priceable_yield_meur())}**, soit")
    w(f"**{pct(share_of_yield())}**.")
    w("")
    w("La raison est entière dans un seul article : la contribution exceptionnelle sur les")
    w("bénéfices des grandes entreprises, seul article chiffrable, est **le plus gros")
    w(f"montant quantifié de toute l'annexe** — {meur(priceable_yield_meur())} en 2026.")
    w(f"**{pct(share_priceable())} des articles, {pct(share_of_yield())} des euros.**")
    w("Les deux chiffres sont vrais et il faut les donner ensemble :")
    w("l'un seul flatte, l'autre seul accable.")
    w("")
    w("Une mise en garde sur ce second chiffre, et elle est structurelle : son dénominateur")
    w("n'est pas le PLF, c'est **la part du PLF que l'annexe chiffre**. Les articles sans")
    w("fiche et les « non chiffrables » en sont exclus, pas mis à zéro — les compter à zéro")
    w("gonflerait la part ; les compter à leur valeur inconnue est impossible. La direction")
    w("du biais est donc inconnue, et c'est pour cela qu'elle est dite.")
    w("")
    w("## Deux drapeaux que les trois cases ne peuvent pas porter")
    w("")
    w("Le cahier des charges demande exactement une case par article, et `bucket` la porte.")
    w("Mais « chiffrable » cachait deux questions indépendantes, et les confondre est")
    w("précisément la façon dont un zéro confiant se publie :")
    w("")
    w("* `engine_ready` — les paramètres existent et la formule les lit : il ne manque que")
    w("  le câblage ;")
    w("* `population_can_exercise` — la population synthétique contient réellement des")
    w("  contribuables que la mesure atteint.")
    w("")
    w("Et une **quatrième case**, `population_blind`, née de cette distinction : le moteur")
    w("saurait, la population ne peut pas. La câbler publierait un zéro confiant, ce qui")
    w("est pire qu'un refus puisque cela porte la provenance d'une vraie réponse. Chaque")
    w("article de cette case doit nommer ce qui **ouvrirait la porte** — une porte")
    w("lointaine reste une porte, et le document ne doit mentir dans aucun des deux sens.")
    w("")
    w("**L'article 2 (CDHR) a forcé la distinction.** Ses paramètres résolvent, sa variable")
    w("tourne, et elle mord : −75 836 EUR sur un foyer à 2 M EUR de dividendes. À la")
    w("lettre, c'est un « petit bouton ». Mais la CDHR est un complément portant le taux")
    w("moyen à 20 %, qu'un contribuable purement salarié dépasse déjà — donc sur une")
    w("population sans revenus du capital l'assiette est vide **par construction**, et la")
    w("câbler publierait 0,00 EUR face à un rendement d'environ un milliard.")
    w("")
    w("## La table")
    w("")
    w("| art. | catégorie | case | moteur | population | boutons | conf. |")
    w("|---|---|---|---|---|---|---|")
    for a in ARTICLES:
        w(f"| {a.numero} | {a.categorie[:44]} | {CASE[a.bucket]} | "
          f"{'prêt' if a.engine_ready else '—'} | "
          f"{'oui' if a.population_can_exercise else 'aveugle'} | "
          f"{', '.join(a.knobs) or '—'} | {a.confiance} |")
    w("")
    w("## Les raisons, article par article")
    w("")
    for a in ARTICLES:
        w(f"### Article {a.numero} — {a.categorie}")
        w("")
        w(f"*{a.intitule}*")
        w("")
        head = f"**{CASE[a.bucket]}**"
        if a.banners:
            head += f" · bannières : {', '.join(a.banners)}"
        if a.paths:
            head += " · chemins : `" + "`, `".join(".".join(p) for p in a.paths) + "`"
        w(head)
        w("")
        w(a.raison)
        if a.unlock:
            w("")
            w(f"**Ce qui l'ouvrirait :** {a.unlock}")
        w("")
    w("## Ce qu'il faut en faire en octobre")
    w("")
    w("Lire les articles publiés, rattacher chacun à une catégorie ci-dessus, prendre la")
    w("case. Là où le texte 2027 porte une catégorie absente d'ici, c'est une décision de")
    w("triage **nouvelle** : la prendre, l'écrire, et dire qu'elle a été prise le jour même")
    w("et non d'avance. La différence compte : un refus préenregistré est une limite, un")
    w("refus improvisé est une excuse.")
    w("")
    w(f"## Le PLF 2027 réel — triage du {DATE_TRIAGE_2027}")
    w("")
    w(f"> {SOURCE_2027}")
    w("")
    neuves = [a for a in ARTICLES_2027 if a.decision == "neuve"]
    chiffrables = priceable_2027()
    w(f"**{len(ARTICLES_2027)} articles fiscaux, {len(chiffrables)} chiffrables** "
      f"(art. {', '.join(str(a.numero) for a in chiffrables)}). "
      f"**{len(neuves)} décisions sont neuves**, prises le jour de parution sur des "
      f"catégories que septembre n'avait pas vues ; les "
      f"{len(ARTICLES_2027) - len(neuves)} autres reprennent une catégorie du triage "
      f"préenregistré, à la lettre, et un test le vérifie.")
    w("")
    w("Ce triage n'a lu aucun montant de l'annexe des évaluations préalables : il a été")
    w("pris avant le commit des enregistrements (runbook, étape 5). Les montants viennent")
    w("après, dans « Le PLF 2027 en euros ».")
    w("")
    w("| art. | intitulé | catégorie | case | décision |")
    w("|---|---|---|---|---|")
    for a in ARTICLES_2027:
        w(f"| {a.numero} | {a.intitule[:60]} | {a.categorie[:44]} | {CASE[a.bucket]} | "
          f"{a.decision} |")
    w("")
    for a in chiffrables:
        w(f"### Article {a.numero} — {a.categorie}")
        w("")
        w(f"*{a.intitule}*")
        w("")
        w(f"**{CASE[a.bucket]}** · chaîne {a.chaine} · boutons `{'`, `'.join(a.knobs)}` · "
          f"réforme `{a.reforme}`")
        w("")
        w(a.raison)
        w("")
    euros_2027(w)
    plfss_2027(w)
    article_74(w)
    return "\n".join(lines)


def euros_2027(w) -> None:
    """The 2027 euro share, the lines it is read from, and the doors (D-293, D-294)."""
    numerator, total = priced_yield_2027_meur(), quantified_yield_2027_meur()
    priced = priceable_2027()
    out = articles_hors_denominateur_2027()
    w("## Le PLF 2027 en euros")
    w("")
    w(f"> {SOURCE_ANNEXE_2027}")
    w("")
    w(f"Sur les **{meur(total)}** d'effort de 2027 que l'annexe quantifie, l'outil en "
      f"chiffre **{meur(numerator)}**, soit **{pct(share_of_yield_2027())}** ; et "
      f"**{len(priced)} articles sur {len(ARTICLES_2027)}**, soit "
      f"{pct(len(priced) / len(ARTICLES_2027))}. "
      f"**{pct(len(priced) / len(ARTICLES_2027))} des articles, "
      f"{pct(share_of_yield_2027())} des euros.** Comme en 2026, les deux chiffres disent "
      f"le contraire l'un de l'autre, et c'est pourquoi ils vont ensemble.")
    w("")
    w("La règle qui dit quel montant compte a été écrite avant la lecture (D-293) : "
      "l'effet budgétaire de 2027 de la section 4.2 de chaque fiche, en valeur absolue, "
      "volet par volet ; un montant sans année déterminable, « non chiffrable » ou donné "
      "par un seul côté (majorant, minorant, maximum) sort du dénominateur ; un volet qui "
      "commence après 2027 vaut zéro. Le numérateur ne prend que les volets que l'outil "
      "chiffre : il dit « chiffré », pas « retrouvé », et l'écart de chacun à l'annexe "
      "est dans `reports/chiffrages_preregistres.md`.")
    w("")
    gap = (share_of_yield_2027() - share_of_yield_2027_si_ecrits()) * 100
    w(f"Si chaque montant écrit que la règle sort entrait au dénominateur, la part "
      f"serait de {pct(share_of_yield_2027_si_ecrits())}, "
      f"{f'{gap:.1f}'.replace('.', ',')} point de moins : la règle la flatte de cela, "
      f"puisqu'aucun de ces montants n'est un volet chiffré.")
    w("")
    w("### Les portes, de celle qui rapporterait le plus à celle qui ne rapporterait rien")
    w("")
    w("Chaque article refusé reçoit la porte qui l'ouvrirait, selon la raison de son "
      "triage (D-293) ; un article à plusieurs volets y va tout entier.")
    w("")
    w("| porte | ce qui l'ouvrirait | articles | euros de 2027 | hors du dénominateur |")
    w("|---|---|---|---|---|")
    for porte in portes_2027():
        hors = ", ".join(str(n) for n in porte.articles_hors) or "—"
        w(f"| `{porte.cle}` | {porte.libelle} | "
          f"{', '.join(str(n) for n in porte.articles)} | {meur(porte.meur)} | {hors} |")
    w("")
    rest = volets_non_chiffres_2027()
    w(f"Restent, dans les articles chiffrés, **{meur(sum(m.meur for m in rest))}** de "
      f"volets que l'outil ne chiffre pas : "
      + " ; ".join(f"art. {m.article}, volet {m.volet}, {m2027(m.meur)}\u00a0M EUR"
                   for m in rest)
      + ". Le triage de leur article dit déjà ce qui leur manque.")
    w("")
    late = chiffres_apres_annexe_2027()
    w("### Les volets chiffrés après l'annexe (but 8, D-306)")
    w("")
    w(f"**{meur(sum(line.meur for line, _ in late))}** du numérateur viennent de volets "
      f"chiffrés par des cas écrits après la lecture de l'annexe. Ce sont des révisions "
      f"au sens de D-292 : le rapport les compte à part des cas aveugles, jamais parmi "
      f"eux.")
    w("")
    for line, cases in late:
        w(f"* **Art. {line.article}, volet {line.volet}, {m2027(line.meur)}\u00a0M EUR** "
          f"— " + ", ".join(f"`{case}`" for case in cases) + ".")
    w("")
    w("### Les refus mesurés (but 8, D-305 ; but 12, D-326)")
    w("")
    measured = refus_mesures_2027()
    w(f"Les buts 8 et 12 ont regardé **{meur(sum(line.meur for _, line in measured))}** de "
      f"volets refusés. Aucun n'entre au numérateur : chacun dit ce "
      f"que la population ou les données ouvertes en portent, et ce qui manque. Les cinq "
      f"derniers sont les articles derrière la porte « consommation », que le but 12 a "
      f"ouverte pour les ménages (la TVA par poste et les accises sur l'énergie) : aucun "
      f"ne s'en chiffre.")
    w("")
    for refus, line in measured:
        volet = f", volet {refus.volet}" if refus.volet else ""
        w(f"* **Art. {refus.article}{volet}, {m2027(line.meur)}\u00a0M EUR.** "
          f"{refus.porte} Manque : {refus.manque}")
    w("")
    w("### Les articles qui sortent du dénominateur")
    w("")
    for numero in out:
        if numero in SANS_FICHE_2027:
            w(f"* **Art. {numero}** — pas de fiche dans l'annexe.")
            continue
        raisons = sorted({m.raison for m in montants_2027(numero)})
        w(f"* **Art. {numero}** — {' ; '.join(raisons)}.")
    w("")
    w("### Le relevé, ligne par ligne")
    w("")
    w("| art. | volet | 2027 (M EUR) | p. | citation | lecture |")
    w("|---|---|---|---|---|---|")
    after = {(line.article, line.volet) for line, _ in late}
    for m in MONTANTS_2027:
        value = "hors" if m.meur is None else m2027(m.meur)
        if m.chiffre:
            value = f"**{value}** (chiffré" + (
                " après l'annexe)" if (m.article, m.volet) in after else ")")
        w(f"| {m.article} | {m.volet or '—'} | {value} | {m.page} | « {m.citation} » | "
          f"{m.raison} |")
    w("")


def plfss_2027(w) -> None:
    """The PLFSS 2027, triaged article by article, each refusal with its door (D-298)."""
    total = len(ARTICLES_PLFSS_2027)
    chiffrables = [a for a in ARTICLES_PLFSS_2027 if a.bucket == "priceable_now"]
    w(f"## Le PLFSS 2027 — triage du {DATE_TRIAGE_PLFSS_2027} (D-298)")
    w("")
    w(f"Source : {SOURCE_PLFSS_2027}")
    w("")
    w(f"**{total} articles, {len(chiffrables) or 'aucun'} chiffrable"
      f"{'s' if len(chiffrables) > 1 else ''} par l'outil.** Chaque refus porte la porte "
      f"qui l'ouvrirait, dans le catalogue de D-293 et une porte que le PLF n'appelait "
      f"pas, `sante`. Le PLFSS n'a pas de montants relevés : les portes y sont classées "
      f"par nombre d'articles.")
    w("")
    w("| porte | ce qui l'ouvrirait | articles |")
    w("|---|---|---|")
    for cle, articles in portes_plfss_2027():
        noms = ", ".join("liminaire" if n == 0 else str(n) for n in articles)
        w(f"| `{cle}` | {OUVERTURES_PLFSS_2027[cle]} | {noms} |")
    w("")
    w("### Article par article")
    w("")
    w("| art. | intitulé | case | porte | raison |")
    w("|---|---|---|---|---|")
    for a in ARTICLES_PLFSS_2027:
        numero = "liminaire" if a.numero == 0 else str(a.numero)
        w(f"| {numero} | {a.intitule} | {CASE[a.bucket]} | `{a.porte}` | {a.raison} |")
    w("")


def article_74(w) -> None:
    """The one spending measure of the PLF 2027 the tool prices, in two volets (D-298)."""
    a = ARTICLE_74_2027
    w(f"## L'art. {a.numero} du PLF 2027 — {a.categorie}")
    w("")
    w(f"*{a.intitule}*")
    w("")
    w(f"**{CASE[a.bucket]}** · chaîne {a.chaine} · boutons `{'`, `'.join(a.knobs)}` · "
      f"scénarios `{'`, `'.join(r.strip() for r in a.reforme.split(','))}`")
    w("")
    w(a.raison)
    w("")
    w("Les deux volets sont préenregistrés en miroir ; leur note contre la fiche est dans "
      "`reports/chiffrages_preregistres.md`.")
    w("")


if __name__ == "__main__":
    OUT.write_text(build(), encoding="utf-8")
    print(f"{OUT} — {len(build().splitlines())} lignes")
