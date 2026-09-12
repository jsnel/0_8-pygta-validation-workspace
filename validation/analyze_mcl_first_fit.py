"""Compare fresh MCL first-fit captures, preserving raw and scale-adjusted evidence."""
from pathlib import Path
import json
import sys
import numpy as np
import pandas as pd
import xarray as xr
import yaml
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

BASE=Path(__file__).resolve().parent
run=BASE/'runs/case-studies/20260912-110000Z-mcl-refresh'
out=BASE/'comparisons/case-studies/20260912-110000Z-mcl-refresh'
species=['PB1','PB2','PSI1','PSI2','PSI3','PSII1','PSII2','PSII3','freerod']
def rms(x):return float(np.sqrt(np.mean(np.square(x))))
def metric(a,b):
    a,b=xr.align(a,b,join='exact');b=b.transpose(*a.dims)
    return rms(a.values-b.values)/max(rms(a.values),np.finfo(float).eps)
def roots(budget):
    if budget==200:return tuple(run/f'converged-capture-{b}'/'result' for b in ['reference','staging'])
    return tuple(next((run/b).rglob('fit-001-target_result1/result.yaml')).parent for b in ['reference','staging'])
def parameters(root):
    d=yaml.safe_load((root/'result.yaml').read_text());return pd.read_csv(root/d['optimized_parameters']).set_index('label')
report={};fig,axs=plt.subplots(2,2,figsize=(14,8),sharex=True)
colors=['b','k','r','magenta','indigo','lime','green','turquoise','gray']
for row,budget in enumerate([11,200]):
    rr,sr=roots(budget);rd=yaml.safe_load((rr/'result.yaml').read_text());sd=yaml.safe_load((sr/'result.yaml').read_text())
    p,q=parameters(rr),parameters(sr)
    item={'reference_diagnostics':{k:v for k,v in rd.items() if not isinstance(v,(dict,list))},'staging_diagnostics':sd['optimization_info'],'datasets':{},'rates':{}}
    for label in p.index:
        if 'rates.' in label and label in q.index:
            a,b=float(p.loc[label,'value']),float(q.loc[label,'value'])
            item['rates'][label]={'reference':a,'staging':b,'relative_difference':abs(a-b)/abs(a)}
    for label in ['super1ns','super2ns']:
        r=xr.load_dataset(rr/rd['data'][label]);root=sr/'optimization_results'/label
        cs=xr.concat([xr.load_dataset(f).concentrations for f in (root/'elements').glob('*.nc')],dim='compartment').rename(compartment='species').sel(species=species)
        cr=r.species_concentration.sel(species=species)
        scale=float(sd['optimization_results'][label]['meta'].get('scale', 1.0))
        fs=xr.load_dataarray(root/'fitted_data.nc');ds=xr.load_dataarray(root/'input_data.nc')
        item['datasets'][label]={'input_exact':bool(np.array_equal(r.data.values,ds.transpose(*r.data.dims).values)),
            'fitted_data_normalized_rms':metric(r.fitted_data,fs),'staging_scale':scale,
            'raw_concentration_normalized_rms':metric(cr,cs),'scale_adjusted_concentration_normalized_rms':metric(cr,cs/scale)}
        if label=='super2ns':
            for col,c in enumerate([cs,cs/scale]):
                for sp,color in zip(species,colors):
                    a=cr.sel(species=sp,spectral=700,method=None) if 700 in cr.spectral else cr.sel(species=sp).sel(spectral=700,method='nearest')
                    b=c.sel(species=sp).sel(spectral=700,method='nearest')
                    axs[row,col].plot(a.time,a,color=color,label=sp,lw=1.4)
                    axs[row,col].plot(b.time,b,color=color,ls='--',lw=1.2)
                axs[row,col].set_title(f'Budget {budget}: '+('raw concentrations' if col==0 else 'staging divided by dataset scale'))
                axs[row,col].set_xlabel('Time (ps), nearest wavelength to 700 nm');axs[row,col].set_ylabel('Concentration')
                axs[row,col].legend(ncol=3,fontsize=7)
    report[str(budget)]=item
fig.suptitle('super2ns — main solid, staging dashed; all nine species')
fig.tight_layout();fig.savefig(out/'first-fit-overlays.png',dpi=160)
(out/'first-fit-evidence.json').write_text(json.dumps(report,indent=2,default=str),encoding='utf-8')
for budget,item in report.items():print(budget,item['datasets'], 'worst rate rel',max(v['relative_difference'] for v in item['rates'].values()))

