import json, subprocess
avant = json.loads(subprocess.check_output(['git', 'show', 'HEAD:reports/verification/grille.json'], cwd='/home/user/Impots-b28-point2'))
apres = json.load(open('/home/user/Impots-b28-point2/reports/verification/grille.json'))
A = {(l['id'], l['annee']): l for l in avant['lignes']}
for l in apres['lignes']:
    a = A.get((l['id'], l['annee']))
    e1 = l.get('ecart'); e0 = a.get('ecart') if a else None
    if isinstance(e1, (int, float)):
        d = (e1 - e0) * 100 if isinstance(e0, (int, float)) else None
        flag = '' if d is None or abs(d) < 0.05 else ' *'
        print(f"{l['id']:40} {l['annee']} {100*e0 if e0 is not None else float('nan'):7.2f} -> {100*e1:7.2f}  {l['verdict']}{flag}")
from collections import Counter
for an in (2024, 2023, 2022):
    c = Counter(l['verdict'] for l in apres['lignes'] if l['annee'] == an)
    c5 = sum(1 for l in apres['lignes'] if l['annee'] == an and l['verdict'] in ('dans la tolérance', 'hors de la tolérance') and abs(l['ecart']) <= 0.05)
    print(an, dict(c), '±5%:', c5)
