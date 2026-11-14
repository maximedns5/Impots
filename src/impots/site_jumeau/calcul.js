/* Le calcul de la page « Le jumeau », hors du fil principal (D-419).
 *
 * Ce script tourne dans un Web Worker, derrière `pyodide.js` : la page vérifie l'empreinte
 * de `pyodide.js` (sha384) en le téléchargeant, puis crée le Worker depuis un Blob qui
 * porte ce fichier vérifié suivi de celui-ci. Un Worker né d'un Blob hérite de la politique
 * de sécurité du contenu de la page : il ne se connecte qu'à elle et au CDN.
 *
 * Il ne calcule rien lui-même : il charge Pyodide et numpy, écrit le paquet que la page lui
 * passe dans le système de fichiers de Pyodide, puis, à chaque réglage, appelle
 * `navigateur.calculer_json` et rend son texte, tel quel.
 */
"use strict";
let py = null;
self.onmessage = async (ev) => {
  const m = ev.data;
  try {
    if (m.type === "charger") {
      const t0 = performance.now();
      py = await loadPyodide({ indexURL: m.indexURL });
      await py.loadPackage(m.paquets, { messageCallback: () => {} });
      const t1 = performance.now();
      for (const [chemin, source] of Object.entries(m.paquet.fichiers)) {
        py.FS.mkdirTree("/jumeau/" + chemin.split("/").slice(0, -1).join("/"));
        py.FS.writeFile("/jumeau/" + chemin, source);
      }
      py.globals.set("texte", m.donnees);
      py.runPython("import sys, json\nsys.path.insert(0, '/jumeau')\n" +
        "from impots.jumeau.navigateur import Session, calculer_json\n" +
        "S = Session(json.loads(texte))\ndel texte");
      self.postMessage({ type: "pret", pyodide_ms: t1 - t0, paquet_ms: performance.now() - t1 });
    } else if (m.type === "calculer") {
      const t0 = performance.now();
      py.globals.set("reglage", m.reglage);
      const texte = py.runPython("calculer_json(S, reglage)");
      self.postMessage({ type: "resultat", id: m.id, texte, calcul_ms: performance.now() - t0 });
    }
  } catch (e) {
    self.postMessage({ type: "erreur", id: m.id, message: String((e && e.message) || e) });
  }
};
