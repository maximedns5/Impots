import sys
S='/tmp/claude-0/-home-user-Impots/8c1eda0e-eb4f-5530-a9a9-deab4a4ca18f/scratchpad/'
sys.argv=[sys.argv[0], S+'suite28/population_d553.parquet','1.022156']
exec(open(S+'urssaf28/fit.py').read().split("if __name__")[0])
base = dict(margins.SALAIRE_HORAIRE_PRIVE_EN_SMIC_2022)
hB,fB = remap({**base, 2.5: 0.864})
e = np.abs(hB[priv]-h0[priv]); print('n', priv.sum(), 'err>1e-3', (e>1e-3).sum(), 'err>1e-2', (e>1e-2).sum(), 'poids err>1e-3', (pw[priv]*(e>1e-3)).sum()/pw[priv].sum())
print(np.percentile(e,[50,90,99,99.9]))
print('raw>=4 n', (priv&(raw>=4)).sum())
