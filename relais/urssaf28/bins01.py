import sys; sys.argv=[sys.argv[0], sys.argv[1], '1.022156']
exec(open('/tmp/claude-0/-home-user-Impots/8c1eda0e-eb4f-5530-a9a9-deab4a4ca18f/scratchpad/urssaf28/fit.py').read().split("if __name__")[0])
base = dict(margins.SALAIRE_HORAIRE_PRIVE_EN_SMIC_2022)
nod9 = {k: v for k, v in base.items() if k != 3.04}
A = {**nod9, 2.5: 0.852, 3.0: 0.907, 3.5: 0.940}
B = {**base, 2.5: 0.864}
ba = bins(remap(A)[0]); bb = bins(remap(B)[0])
for i,e in enumerate(edges[:-1]):
    print(f'{e:.1f} urssaf {100*U[i]:6.2f}  A {100*ba[i]:6.2f}  D553 {100*bb[i]:6.2f}')
print(stats(A))
