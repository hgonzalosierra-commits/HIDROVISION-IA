"""Reviewed SENAMHI snapshots; missing records are never imputed as zero."""
import json,re
from pathlib import Path
import platform_store as store
from pyproj import Transformer, Geod

ROOT=Path(__file__).parent

def context(comparison):
    result=store.read_result(comparison)
    catalog=json.loads((ROOT/'docs/evidencias/estaciones-senamhi.json').read_text(encoding='utf-8'))
    observations=json.loads((ROOT/'docs/evidencias/precipitacion-resumen.json').read_text(encoding='utf-8'))
    stations=[s for s in catalog if s['ico']=='M']
    transform=Transformer.from_crs(result['crs'],4326,always_xy=True)
    geod=Geod(ellps='WGS84')
    periods=[]
    names=['enero','febrero','marzo','abril','mayo','junio','julio','agosto','septiembre','octubre','noviembre','diciembre']
    metadata={c['id']:c for c in store.campaigns()}
    for month in result['months']:
        c=metadata.get(month['video'].split('/')[2],{})
        m=c.get('month');y=c.get('year')
        periods.append({'name':month['name'],'period':f'{y:04}-{m:02}' if m and y else None})
    refs=[]
    for ref in result['references']:
        lon,lat=transform.transform(ref['east'],ref['north'])
        nearest=min(stations,key=lambda s:geod.inv(lon,lat,s['lon'],s['lat'])[2])
        distance=geod.inv(lon,lat,nearest['lon'],nearest['lat'])[2]/1000
        refs.append({'station':ref['station'],'lat':lat,'lon':lon,'nearest':nearest,'distance_km':round(distance,2),
                     'periods':[{**p,'rain':observations.get(nearest['cod'],{}).get(p['period'])} for p in periods],
                     'socsi_january':nearest['cod']=='113249' and any(p['period']=='2026-01' for p in periods)})
    return {'consulted':'2026-10-25','references':refs,'catalog_source':'https://www.senamhi.gob.pe/?p=estaciones'}
