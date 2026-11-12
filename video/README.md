# La vidéo explicative

Une vidéo d'environ huit minutes, en français, pour quelqu'un qui n'a ni formation en
économie ni en informatique : comment l'outil passe d'un ménage aux chiffres publiés (le
coût d'une mesure, qui y gagne, la dette en 2035, le verdict), avec ses données, ses
hypothèses et ses erreurs. Le fil conducteur est « Droit au brut », la mesure de Gabriel
Attal que le parcours public suit déjà (`site/parcours-3-cout.html`).

* `scenes.py` : les 16 scènes, leur narration, leurs visuels et la source de chaque nombre.
  Aucun nombre n'est calculé : chacun est recopié d'un rapport commité, d'une page du site
  ou de `reports/parcours/menages.json`.
* `SCRIPT.md` : le script de narration complet, avec ses sources, écrit depuis
  `scenes.py` (`python video/build.py script`).
* `build.py` : la voix (Piper), les pages HTML des scènes, la piste audio et l'assemblage
  ffmpeg ; `render.mjs` rend les images avec Playwright ; `style.css` les met en page, en
  paysage (1920 × 1080) et en portrait (1080 × 1920).

La vidéo elle-même n'entre pas dans git.

## Refaire la vidéo

Il faut ffmpeg, Node avec Playwright et Chromium, et Piper avec une voix française :

```sh
python3 -m venv /tmp/tts && /tmp/tts/bin/pip install piper-tts num2words
curl -LO https://huggingface.co/rhasspy/piper-voices/resolve/main/fr/fr_FR/siwis/medium/fr_FR-siwis-medium.onnx
curl -LO https://huggingface.co/rhasspy/piper-voices/resolve/main/fr/fr_FR/siwis/medium/fr_FR-siwis-medium.onnx.json
export PIPER=/tmp/tts/bin/piper PIPER_VOIX=$PWD/fr_FR-siwis-medium.onnx VIDEO_OUT=/tmp/video
/tmp/tts/bin/python video/build.py tout
```

Les MP4 sont écrits dans `$VIDEO_OUT` (`impots_explication_paysage.mp4`,
`impots_explication_portrait.mp4`). Rien du modèle ne tourne : le script ne lit ni `src/`
ni les rapports, il ne fait que mettre en images les nombres de `scenes.py`.

## Changer un nombre

Un nombre de la vidéo change quand le rapport ou la page dont il vient change. On corrige
alors `scenes.py` (la narration et le visuel), on réécrit `SCRIPT.md` et on refait la
vidéo. Les nombres sont ceux du commit `0b7afd1` (la série du 2026-11-11).
