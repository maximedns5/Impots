import json, sys
R='/home/user/Impots-b28-etudes/reports/etudes/'
E='/tmp/claude-0/-home-user-Impots/8c1eda0e-eb4f-5530-a9a9-deab4a4ca18f/scratchpad/etudes28/'
L=lambda p: json.load(open(p))
s0=L(R+'mesure_melenchon_b27/smic.json'); s1=L(R+'mesure_melenchon_b27/d553/smic.json')
print('chaine', s1['chaine_du_cout_md'])
print('cout', s0['cout_md'], '->', s1['cout_md'])
for k in ('revenu_disponible','allegement_general','salaire_brut','cotisations_employeur','ppa','salaire_super_brut'):
    print(' ',k, s0['deltas_md'].get(k), '->', s1['deltas_md'].get(k))
print('part menages', round(s0['deltas_md']['revenu_disponible']/s0['cout_md'],3), round(s1['deltas_md']['revenu_disponible']/s1['cout_md'],3))
for k in ('releves',): print(k, s0['cellules'][k], s1['cellules'][k])
print('perdants', {k:s0['cellules']['perdants'][k] for k in ('menages_m','part','perte_moyenne_eur')}, {k:s1['cellules']['perdants'][k] for k in ('menages_m','part','perte_moyenne_eur')})
print('deciles', [d['gain_moyen_eur'] for d in s0['deciles']], [d['gain_moyen_eur'] for d in s1['deciles']])
p0=L(R+'mesure_melenchon_b27/programme.json'); p1=L(R+'mesure_melenchon_b27/d553/programme.json')
for k in ('programme_md','somme_des_seules_md','interaction_md'): print(k, p0[k]['reform_cost'],'->',p1[k]['reform_cost'])
for n in p1['seules_union_md']: print(' seule',n,p0['seules_union_md'][n]['reform_cost'],'->',p1['seules_union_md'][n]['reform_cost'], '| propres', p0['seules_propres_md'][n]['reform_cost'],'->',p1['seules_propres_md'][n]['reform_cost'])
print(' paires', {k:(p0['paires_md'][k]['reform_cost'],p1['paires_md'][k]['reform_cost']) for k in p1['rang_paires'][:6]})
mx=max(abs(p1['paires_md'][k]['reform_cost']-p0['paires_md'][k]['reform_cost']) for k in p1['paires_md'] if k!='smic+exo'); print(' max autre paire diff', mx)
j0=L(R+'mesure_melenchon_b27/jumeau.json'); j1=L(R+'mesure_melenchon_b27/d553/jumeau.json')
for v in ('figee','vieillie'):
    print('smic', v, j0['smic_d521'][v]['court'], '\n   ->', j1['smic_d553'][v]['court'])
    print('prog', v, j0['programme_d521'][v]['ensemble'], '\n   ->', j1['programme_d553'][v]['ensemble'])
print('smic diffusion figee 0.5 (mesure jumeau)', j1['smic_d553']['figee']['diffusion']['0.5'])
print('paires jumeau', j1['paires_jumeau_d553']['ensemble_moins_somme'])
d0=L(R+'reaction_b28/diffusion_d551.json'); d1=L(R+'reaction_b28/diffusion_d557.json')
for v in ('figee','vieillie'):
    for t in d0[v]:
        a,b=d0[v][t],d1[v][t]; print('diff',v,t, a['emploi_2035'],'->',b['emploi_2035'], round(b['emploi_2035']-a['emploi_2035'],1), '| B9', a['b9_2035'],'->',b['b9_2035'], round(b['b9_2035']-a['b9_2035'],2), '| dette', a['dette_2035'],'->',b['dette_2035'])
i0=L(R+'interaction_b28/defaut_d551.json'); i1=L(R+'interaction_b28/defaut_d557.json')
for v in ('figee','vieillie'):
    A,B=i0['reglages']['defaut'][v],i1['reglages']['defaut'][v]
    print('inter',v,'smic',A['smic_seul'],'\n  ->',B['smic_seul']); print('inter',v,'prog',A['programme'],'\n  ->',B['programme'])
    print('  paires', {k:x['ecart_a_la_somme'] for k,x in B['paires'].items()})
for r in i1['reglages']:
    if r in i0['reglages']: print(' reglage', r, i0['reglages'][r]['figee']['smic_seul']['emploi_2035'], '->', i1['reglages'][r]['figee']['smic_seul']['emploi_2035'], '| prog', i0['reglages'][r]['figee']['programme']['emploi_2035'],'->',i1['reglages'][r]['figee']['programme']['emploi_2035'])
c0=L(R+'interaction_b28/cice_d551.json'); c1=L(R+'interaction_b28/cice_d557.json')
print('cice', {k:(round(c0['reglages'][k]['emploi_2016'],1), round(c1['reglages'][k]['emploi_2016'],1), round(c1['reglages'][k]['moyenne_2014_2016'],1)) for k in c1['reglages']})
b0=L(R+'boucle_b28/resultats.json'); b1=L(R+'boucle_b28/resultats_d557.json')
for c in ('cice','smic'): print('coef',c, {k:(round(b0['passe_'+c]['coefficients'][k],3), round(b1['passe_'+c]['coefficients'][k],3)) for k in b1['passe_'+c]['coefficients']})
for d in ('0.0','0.5','1.0'):
    for x,b in (('avant',b0),('apres',b1)):
        s=b['jumeau_passes']['smic'][d]; print('boucle smic',d,x,'sans',s['sans']['emploi_total'][-1], s['sans']['b9'][-1],'avec',s['avec']['emploi_total'][-1], s['avec']['b9'][-1], 'avec-sans', round(s['avec']['emploi_total'][-1]-s['sans']['emploi_total'][-1],2), round(s['avec']['b9'][-1]-s['sans']['b9'][-1],2))
for x,b in (('avant',b0),('apres',b1)):
    c=b['jumeau_passes']['cice']; print('boucle cice',x,'2016 sans',c['sans']['emploi_salarie'][3],'avec',c['avec']['emploi_salarie'][3])
