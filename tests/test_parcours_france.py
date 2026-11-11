"""La page 2 du parcours (D-375) montre les nombres de la grille commitée, et se lit sans
son script."""

import html
import json
import re

from impots import parcours
from impots.parcours import france

GRILLE = parcours.ROOT / "reports" / "verification" / "grille.json"


def _grille():
    return json.loads(GRILLE.read_text(encoding="utf-8"))["lignes"]


def test_la_page_montre_le_compte_et_les_lignes_hors_de_la_grille():
    page = france.page()
    parcours._check("france", page)
    rows = _grille()
    notees = [r for r in rows if r["usage"] == "validation" and r["ecart"] is not None]
    tenues = sum(r["verdict"] == "dans la tolérance" for r in notees)
    texte = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", page.corps)))
    assert f"{tenues} lignes notées sur {len(notees)}" in texte
    assert (tenues, len(notees)) == (84, 113)  # D-371
    for annee in france.ANNEES:
        n = [r for r in notees if r["annee"] == annee]
        t = sum(r["verdict"] == "dans la tolérance" for r in n)
        assert f"{t} lignes sur {len(n)} tiennent leur tolérance en {annee}" in texte
    # Chaque ligne hors de sa tolérance est nommée dans la vue de son année, avec son écart.
    for r in notees:
        if r["verdict"] == "hors de la tolérance":
            assert f"{r['ligne']} : {france.pct(r['ecart'])}" in texte, r["id"]
    # Chaque total publié de la grille a sa source cliquable.
    for r in rows:
        if r.get("url"):
            assert html.escape(r["url"]) in page.corps, r["id"]


def test_la_page_se_lit_sans_script():
    page = france.page()
    assert "<noscript>" in page.corps
    # Sans script, les trois années sont là, aucune n'est cachée.
    for annee in france.ANNEES:
        assert re.search(rf'<section class="vue-annee" data-annee="{annee}"[^>]*>',
                         page.corps)
    assert 'class="vue-annee" data-annee="2022" hidden' not in page.corps
