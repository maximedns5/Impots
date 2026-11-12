"""Fabrique la vidéo explicative depuis `scenes.py`.

    python video/build.py script            # écrit video/SCRIPT.md
    python video/build.py voix              # synthèse vocale (Piper), une piste par temps fort
    python video/build.py pages             # une page HTML par scène et par format
    python video/build.py rendu             # images (Playwright) puis MP4 (ffmpeg)
    python video/build.py tout

Variables d'environnement :
    VIDEO_OUT    le dossier de travail et de sortie (défaut : video/out, hors de git)
    PIPER        l'exécutable piper (défaut : piper)
    PIPER_VOIX   le modèle .onnx de la voix française (défaut : fr_FR-siwis-medium.onnx)
    VITESSE      le length_scale de Piper (défaut : 0.9 ; plus petit, plus rapide)
    FPS          images par seconde (défaut : 25)
    FORMATS      « paysage,portrait » (défaut : les deux)

Rien n'est calculé ici sur le modèle : les nombres sont ceux de `scenes.py`, recopiés des
fichiers du dépôt. Ce script ne lit ni ne touche `src/`, les rapports ou le site.
"""

import hashlib
import json
import os
import re
import subprocess
import sys
import wave
from array import array
from pathlib import Path

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI))
from scenes import SCENES  # noqa: E402

OUT = Path(os.environ.get("VIDEO_OUT", ICI / "out")).resolve()
PIPER = os.environ.get("PIPER", "piper")
VOIX = os.environ.get("PIPER_VOIX", "fr_FR-siwis-medium.onnx")
FPS = int(os.environ.get("FPS", "25"))
FORMATS = {
    "paysage": (1920, 1080),
    "portrait": (1080, 1920),
}
CHOISIS = os.environ.get("FORMATS", "paysage,portrait").split(",")

# Le rythme : un temps de silence avant le premier temps fort, entre deux, et à la fin.
PAD_DEBUT, ENTRE, PAD_FIN = 0.6, 0.35, 1.1
RATE = 22050  # la sortie de Piper


# ---------------------------------------------------------------------------------------
# Le texte lu : les nombres et les sigles en toutes lettres
# ---------------------------------------------------------------------------------------

SIGLES = {
    "CSG": "cé esse gé",
    "CRDS": "cé erre dé esse",
    "CVAE": "cé vé a e",
    "PIB": "pé i bé",
    "TVA": "té vé a",
    "Insee": "Insé",
    "OpenFisca": "Open Fisca",
    "Monte-Carlo": "Monté Carlo",
    "Mésange": "Mézange",
    "méta-analyses": "méta analyses",
}


def _entier(n):
    from num2words import num2words

    return num2words(n, lang="fr")


def _nombre(m):
    s = re.sub(r"[   ]", "", m.group(0))
    if "," in s:
        a, b = s.split(",")
        zeros = len(b) - len(b.lstrip("0"))
        reste = b.lstrip("0")
        dec = " ".join(["zéro"] * zeros + ([_entier(int(reste))] if reste else []))
        return f"{_entier(int(a))} virgule {dec}"
    return _entier(int(s))


def a_lire(texte):
    t = texte
    for k, v in SIGLES.items():
        t = re.sub(rf"\b{re.escape(k)}\b", v, t)
    t = t.replace("«", "").replace("»", "")
    t = re.sub(r"\d{1,3}(?:[   ]\d{3})+(?:,\d+)?|\d+(?:,\d+)?", _nombre, t)
    return re.sub(r"\s+", " ", t).strip()


# ---------------------------------------------------------------------------------------
# Le script de narration
# ---------------------------------------------------------------------------------------


def script():
    lignes = [
        "# La vidéo explicative : le script de narration",
        "",
        "Écrit par `python video/build.py script` depuis `video/scenes.py` ; ne pas le",
        "modifier à la main. Chaque nombre dit est recopié d'un fichier commité du dépôt,",
        "nommé sous la scène. Rien n'a été recalculé pour la vidéo.",
        "",
    ]
    for i, sc in enumerate(SCENES):
        titre = sc["titre"] or "Titre"
        lignes += [f"## {i}. {sc['chapitre'] + ' — ' if sc['chapitre'] else ''}{titre}", ""]
        for b in sc["beats"]:
            lignes += [f"> {b}", ""]
        if sc["sources"]:
            lignes += ["Sources :", ""]
            for quoi, ou in sc["sources"]:
                lignes.append(f"* {quoi} : `{ou}`" if "/" in ou else f"* {quoi} : {ou}")
            lignes.append("")
    (ICI / "SCRIPT.md").write_text("\n".join(lignes))
    mots = sum(len(b.split()) for sc in SCENES for b in sc["beats"])
    print(f"SCRIPT.md : {len(SCENES)} scènes, {mots} mots")


# ---------------------------------------------------------------------------------------
# La voix
# ---------------------------------------------------------------------------------------


def _wav_duree(p):
    with wave.open(str(p)) as w:
        return w.getnframes() / w.getframerate()


def voix():
    d = OUT / "voix"
    d.mkdir(parents=True, exist_ok=True)
    plan = []
    for sc in SCENES:
        durees = []
        for b in sc["beats"]:
            lu = a_lire(b)
            h = hashlib.sha1((VOIX + os.environ.get("VITESSE", "0.9") + lu).encode()).hexdigest()[:12]
            f = d / f"{sc['id']}_{h}.wav"
            if not f.exists():
                subprocess.run(
                    [PIPER, "-m", VOIX, "-f", str(f), "--sentence_silence", "0.25",
                     "--length_scale", os.environ.get("VITESSE", "0.9")],
                    input=lu.encode(), check=True, capture_output=True,
                )
            durees.append((str(f), _wav_duree(f)))
        plan.append({"id": sc["id"], "pistes": durees})
    (OUT / "voix.json").write_text(json.dumps(plan, indent=1))
    total = sum(p[1] for s in plan for p in s["pistes"])
    print(f"voix : {total:.0f} s de parole")


def _temps():
    """Le début de chaque temps fort et la durée de chaque scène."""
    plan = json.loads((OUT / "voix.json").read_text())
    res = []
    for sc, p in zip(SCENES, plan):
        assert sc["id"] == p["id"]
        t, debuts = PAD_DEBUT, []
        for _, dur in p["pistes"]:
            debuts.append(round(t, 3))
            t += dur + ENTRE
        duree = t - ENTRE + PAD_FIN
        res.append({"id": sc["id"], "debuts": debuts, "durees": [x[1] for x in p["pistes"]],
                    "fichiers": [x[0] for x in p["pistes"]], "duree": round(duree, 3)})
    return res


def piste_audio():
    temps = _temps()
    total = sum(s["duree"] for s in temps)
    n = int(round(total * RATE)) + RATE
    piste = array("h", bytes(2 * n))
    t0 = 0.0
    for s in temps:
        for f, deb in zip(s["fichiers"], s["debuts"]):
            with wave.open(f) as w:
                assert w.getframerate() == RATE and w.getsampwidth() == 2 and w.getnchannels() == 1
                a = array("h", w.readframes(w.getnframes()))
            i = int(round((t0 + deb) * RATE))
            piste[i:i + len(a)] = a
        t0 += s["duree"]
    with wave.open(str(OUT / "narration.wav"), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(piste.tobytes())
    print(f"narration.wav : {total:.1f} s")
    return temps


# ---------------------------------------------------------------------------------------
# Les pages
# ---------------------------------------------------------------------------------------


def _decoupe(texte, maxc):
    """Coupe un temps fort en sous-titres de maxc caractères au plus, aux ponctuations."""
    morceaux = re.split(r"(?<=[.;:?!])\s+", texte)
    out = []
    for m in morceaux:
        while len(m) > maxc:
            coupe = max(m.rfind(", ", 0, maxc), m.rfind(" ", 0, maxc))
            if m.rfind(", ", 0, maxc) > maxc * 0.45:
                coupe = m.rfind(", ", 0, maxc) + 1
            out.append(m[:coupe].strip())
            m = m[coupe:].strip()
        if m:
            out.append(m)
    # Regroupe les morceaux courts.
    res = []
    for m in out:
        if res and len(res[-1]) + 1 + len(m) <= maxc:
            res[-1] += " " + m
        else:
            res.append(m)
    return res


def _insecables(t):
    """Pas de « % », « € », « pt » ou « Md€ » seuls en début de ligne."""
    return re.sub(r"(?<=[\d½]) (?=%|€|pt\b|Md€|M€|M\b)", "\u00a0", t)


def _soustitres(sc, tm, maxc):
    st = []
    for texte, deb, dur in zip(sc["beats"], tm["debuts"], tm["durees"]):
        parts = _decoupe(texte, maxc)
        tot = sum(len(p) for p in parts)
        t = deb
        for p in parts:
            d = dur * len(p) / tot
            st.append({"a": round(t, 3), "b": round(t + d + 0.25, 3), "t": _insecables(p)})
            t += d
    return st


def pages(temps=None):
    temps = temps or _temps()
    css = (ICI / "style.css").read_text()
    for fmt in CHOISIS:
        d = OUT / "pages" / fmt
        d.mkdir(parents=True, exist_ok=True)
        maxc = 92 if fmt == "paysage" else 64
        for i, (sc, tm) in enumerate(zip(SCENES, temps)):
            assert sc["id"] == tm["id"]
            st = _soustitres(sc, tm, maxc)
            sources = " · ".join(ou for _, ou in sc["sources"] if "/" in ou)
            entete = "" if not sc["titre"] else (
                f'<header><div class="chap">{sc["chapitre"]}</div><h1>{sc["titre"]}</h1></header>'
            )
            html = f"""<!doctype html><html lang="fr"><head><meta charset="utf-8">
<style>{css}</style></head>
<body class="{fmt} sc-{sc['id']}"><div id="stage">{entete}
<main>{sc['html']}</main>
<div class="srcline">{('Sources : ' + sources) if sources else ''}</div>
<div id="subs"><div id="subt"></div></div></div>
<script>
const BEATS = {json.dumps(tm['debuts'])};
const DUREE = {tm['duree']};
const SUBS = {json.dumps(st, ensure_ascii=False)};
for (const el of document.querySelectorAll('[data-beat]')) {{
  const k = +el.dataset.beat, d = +(el.dataset.d || 0);
  el.style.animationDelay = (BEATS[k] + d) + 's';
}}
const stage = document.getElementById('stage');
stage.style.animation = 'fadein .5s ease-out 0s both, fadeout .5s ease-in ' + (DUREE - 0.5) + 's both';
window.seek = (t) => {{
  const etats = [];
  for (const a of document.getAnimations()) {{
    a.pause(); a.currentTime = t * 1000;
    const c = a.effect.getComputedTiming();
    const deb = c.delay, fin = c.delay + c.activeDuration;
    etats.push(t * 1000 < deb ? 'b' : (t * 1000 > fin ? 'a' : 'x'));
  }}
  let k = -1;
  for (let i = 0; i < SUBS.length; i++) if (t >= SUBS[i].a && t < SUBS[i].b) k = i;
  const s = document.getElementById('subt');
  const txt = k >= 0 ? SUBS[k].t : '';
  if (s.textContent !== txt) s.textContent = txt;
  const actif = etats.includes('x');
  return actif ? null : etats.join('') + '|' + k;
}};
</script></body></html>"""
            (d / f"{i:02d}_{sc['id']}.html").write_text(_insecables(html))
    print("pages écrites")


# ---------------------------------------------------------------------------------------
# Le rendu
# ---------------------------------------------------------------------------------------


def rendu():
    temps = piste_audio()
    pages(temps)
    for fmt in CHOISIS:
        w, h = FORMATS[fmt]
        img = OUT / "images" / fmt
        img.mkdir(parents=True, exist_ok=True)
        travaux, n0 = [], 0
        for i, (sc, tm) in enumerate(zip(SCENES, temps)):
            n = int(round(tm["duree"] * FPS))
            travaux.append({"page": str(OUT / "pages" / fmt / f"{i:02d}_{sc['id']}.html"),
                            "debut": n0, "n": n})
            n0 += n
        cfg = {"largeur": w, "hauteur": h, "fps": FPS, "dossier": str(img), "travaux": travaux}
        (OUT / f"rendu_{fmt}.json").write_text(json.dumps(cfg))
        subprocess.run(["node", str(ICI / "render.mjs"), str(OUT / f"rendu_{fmt}.json")], check=True)
        mp4 = OUT / f"impots_explication_{fmt}.mp4"
        subprocess.run([
            "ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS),
            "-i", str(img / "%06d.png"), "-i", str(OUT / "narration.wav"),
            "-c:v", "libx264", "-preset", "slow", "-crf", "20", "-pix_fmt", "yuv420p",
            "-tune", "stillimage", "-c:a", "aac", "-b:a", "160k", "-ar", "48000",
            "-movflags", "+faststart", "-shortest", str(mp4),
        ], check=True)
        print(f"{mp4} : {n0 / FPS:.1f} s")


if __name__ == "__main__":
    etape = sys.argv[1] if len(sys.argv) > 1 else "tout"
    if etape in ("script", "tout"):
        script()
    if etape in ("voix", "tout"):
        voix()
    if etape == "pages":
        pages()
    if etape in ("rendu", "tout"):
        rendu()
