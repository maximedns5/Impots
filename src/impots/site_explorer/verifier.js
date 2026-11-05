// La page tenue contre la chaîne (but 15, D-344) : `node verifier.js <cas.json>`. Chaque cas
// est une part reportée (une ou plusieurs) avec le contrôle que la passe a écrit — Δb par la
// chaîne elle-même, à θ et à chaque coin — ou une interpolation avec sa valeur Python.
// Écrit la plus grande différence de chaque genre, en JSON, sur la sortie.
"use strict";
const fs = require("fs");
const path = require("path");
const R = require(path.join(__dirname, "rejeu.js"));
const cases = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const out = { rejeu: 0, coins: 0, libelles: 0, interpolation: 0, n: 0 };
for (const c of cases.rejeu) {
  const th = Object.fromEntries(c.rows.map((r) => [r, 0.5]));
  const box = R.box(c.frame, c.horizon, c.parts, c.frame.lignes, c.rows, th, R.READ);
  const theta = R.chemin(c.frame, c.horizon, c.parts, ...R.thetaValues(c.frame.lignes, th), R.READ).delta;
  c.controle.theta.forEach((v, k) => { out.rejeu = Math.max(out.rejeu, Math.abs(theta[k] - v)); });
  box.corners.forEach(([label, v], i) => {
    out.coins = Math.max(out.coins, Math.abs(v - c.controle.coins[i][1]));
    if (label !== c.controle.coins[i][0]) out.libelles += 1;
  });
  out.n += 1;
}
for (const c of cases.interpolation) {
  out.interpolation = Math.max(out.interpolation, Math.abs(R.interpoler(c.xs, c.ys, c.x, c.methode) - c.attendu));
}
process.stdout.write(JSON.stringify(out));
