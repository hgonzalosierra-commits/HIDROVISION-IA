"""Comparación local de campañas. No utiliza servicios externos."""
from pathlib import Path
import sys
import json, math, re, zipfile, uuid
import xml.etree.ElementTree as ET
import numpy as np
import rasterio
from rasterio.warp import reproject, Resampling
from rasterio.transform import from_bounds
from pyproj import CRS, Transformer
from PIL import Image
import cv2

ROOT = Path(__file__).resolve().parent
STORE = ROOT / 'local_data'
STORE.mkdir(exist_ok=True)

def check(condition, message):
    if not condition:
        raise ValueError(message)

def validate_ortho(raster):
    check(raster.crs is not None, 'El ortomosaico no tiene sistema de coordenadas.')
    check(raster.count >= 3, 'El ortomosaico necesita al menos tres bandas de color (rojo, verde y azul).')
    check(all(d in ('uint8', 'uint16') for d in raster.dtypes[:3]),
          'El TIFF utiliza un formato de valores no admitido. Se necesitan colores entre 0 y 255, almacenados en 8 o 16 bits.')
    if any(d != 'uint8' for d in raster.dtypes[:3]):
        # Validate real pixels, excluding NoData (often 256 in exported TIFFs).
        # Read bounded windows so a large orthomosaic never enters memory whole.
        from rasterio.windows import Window
        for y in range(0, raster.height, 1024):
            for x in range(0, raster.width, 1024):
                values = raster.read([1,2,3], window=Window(x,y,min(1024,raster.width-x),min(1024,raster.height-y)), masked=True)
                valid = values.compressed()
                check(not valid.size or valid.max() <= 255,
                      'El TIFF contiene colores válidos superiores a 255. Requiere una conversión de rango consistente para ambos meses; no se recortarán los colores automáticamente.')

def load_campaign(archive, name):
    ident = uuid.uuid4().hex
    dest = STORE / ident
    dest.mkdir()
    groups = {k: [] for k in ('VIDEO', 'ORTOFOTO', 'PLANO_OTROS', 'XML')}
    with zipfile.ZipFile(archive) as z:
        files = [i for i in z.infolist() if not i.is_dir() and '__MACOSX' not in i.filename]
        check(len(files) <= 2000, 'El ZIP supera 2000 archivos.')
        check(sum(i.file_size for i in files) <= 60 * 1024**3, 'El ZIP descomprimido supera 60 GB.')
        for info in files:
            parts = Path(info.filename.replace('\\', '/')).parts
            check(not any(p in ('..', '/') or ':' in p for p in parts), 'Ruta no válida dentro del ZIP.')
            matches = [(i, p.upper()) for i, p in enumerate(parts) if p.upper() in groups]
            if not matches:
                continue
            _, group = matches[0]
            target = dest / group / Path(*parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            with z.open(info) as source, target.open('wb') as out:
                import shutil
                shutil.copyfileobj(source, out, 1024*1024)
            groups[group].append(target)
    def one(group, extensions, description):
        found = [p for p in groups[group] if p.suffix.lower() in extensions]
        check(len(found) == 1, f'{group}: se requiere exactamente {description}; encontrados {len(found)}.')
        return str(found[0])
    campaign = dict(id=ident, name=Path(name).stem,
        video=one('VIDEO', {'.mp4', '.mov', '.m4v', '.webm'}, 'un video'),
        srt=one('VIDEO', {'.srt'}, 'un SRT'),
        ortho=one('ORTOFOTO', {'.tif', '.tiff'}, 'un ortomosaico GeoTIFF georreferenciado'),
        xml=one('XML', {'.xml'}, 'un LandXML'),
        plans=[str(p) for p in groups['PLANO_OTROS']])
    check(campaign['plans'], 'PLANO_OTROS: añade los planos referenciales.')
    check(Path(campaign['video']).stem.casefold() == Path(campaign['srt']).stem.casefold(),
          'El video y su SRT deben tener el mismo nombre base para verificar la asociación.')
    with rasterio.open(campaign['ortho']) as raster:
        validate_ortho(raster)
        campaign['crs'] = raster.crs.to_string()
    (dest / 'campaign.json').write_text(json.dumps(campaign), encoding='utf8')
    return dict(id=ident, name=campaign['name'], crs=campaign['crs'], files={k:len(v) for k,v in groups.items()})

def read_campaign(ident):
    check(bool(re.fullmatch('[a-f0-9]{32}', ident)), 'Identificador no válido.')
    return json.loads((STORE / ident / 'campaign.json').read_text(encoding='utf8'))

def alignment(path, fallback_crs):
    root = ET.parse(path).getroot()
    tag = lambda e: e.tag.split('}')[-1]
    all_nodes = list(root.iter())
    check(not any(tag(e) in ('StaEquation', 'Spiral') for e in all_nodes),
          'Este XML contiene espirales o ecuaciones de progresiva. Se necesita exportar un eje discretizado conservando sus progresivas.')
    units = next((e for e in all_nodes if tag(e) == 'Metric'), None)
    check(units is not None and units.get('linearUnit', 'meter') == 'meter', 'El LandXML debe declarar unidades métricas en metros.')
    axes = [e for e in all_nodes if tag(e) == 'Alignment']
    check(len(axes) == 1, 'El XML debe contener un solo alineamiento del dique.')
    axis = axes[0]
    cs = next((e for e in all_nodes if tag(e) == 'CoordinateSystem'), None)
    code = None if cs is None else cs.get('epsgCode')
    crs = CRS.from_user_input('EPSG:'+code if code and code.isdigit() else code or fallback_crs)
    check(crs.is_projected and all(abs(a.unit_conversion_factor-1) < 1e-8 for a in crs.axis_info),
          'El eje debe usar coordenadas proyectadas en metros.')
    station = float(axis.get('staStart', 0))
    vertices, stations = [], []
    geom = next((e for e in axis if tag(e) == 'CoordGeom'), None)
    check(geom is not None, 'No se encontró CoordGeom en el XML.')
    for segment in geom:
        kind = tag(segment)
        check(kind in ('Line', 'Curve'), f'Geometría no soportada: {kind}.')
        points = {tag(p): [float(v) for v in p.text.split()][:2][::-1] for p in segment if tag(p) in ('Start','End','Center')}
        check('Start' in points and 'End' in points, 'Segmento sin inicio o fin.')
        start, end = np.array(points['Start']), np.array(points['End'])
        if vertices:
            check(np.linalg.norm(start-vertices[-1]) < .1, 'El alineamiento contiene segmentos desconectados.')
        if kind == 'Line':
            length = float(np.linalg.norm(end-start))
            samples = np.array([start, end])
        else:
            check('Center' in points, 'La curva debe incluir Center.')
            center = np.array(points['Center'])
            radius = float(np.linalg.norm(start-center))
            a, b = math.atan2(*(start-center)[::-1]), math.atan2(*(end-center)[::-1])
            cw = segment.get('rot', '').lower() == 'cw'
            sweep = -((a-b) % (2*math.pi)) if cw else (b-a) % (2*math.pi)
            length = abs(sweep)*radius
            angles = np.linspace(a, a+sweep, max(2, math.ceil(length)+1))
            samples = center+radius*np.column_stack([np.cos(angles), np.sin(angles)])
        declared = float(segment.get('length', length))
        check(abs(declared-length) < max(.1, length*.001), 'Longitud XML incompatible con la geometría del eje.')
        values = np.linspace(station, station+declared, len(samples))
        vertices.extend(samples if not vertices else samples[1:])
        stations.extend(values if not stations else values[1:])
        station += declared
    check(len(vertices) >= 2 and station > stations[0], 'El eje no tiene longitud válida.')
    return np.array(vertices), np.array(stations), crs, not bool(code)

def point_at(vertices, stations, s):
    return np.array([np.interp(s, stations, vertices[:,0]), np.interp(s, stations, vertices[:,1])])

def project(vertices, stations, xy):
    d = vertices[1:] - vertices[:-1]
    t = np.clip(np.sum((xy-vertices[:-1])*d, axis=1) / np.maximum(np.sum(d*d,axis=1), 1e-12), 0, 1)
    distance = np.linalg.norm(vertices[:-1]+d*t[:,None]-xy,axis=1)
    i = int(np.argmin(distance))
    return float(stations[i]+t[i]*(stations[i+1]-stations[i])), float(distance[i])

def srt_records(path, crs, vertices, stations):
    text = Path(path).read_text(encoding='utf-8-sig', errors='replace').replace('\r','')
    trans = Transformer.from_crs(4326, crs, always_xy=True)
    result = []
    for block in re.split(r'\n\s*\n', text):
        time = re.search(r'(\d+):(\d+):(\d+)[,.](\d+)\s*-->', block)
        if not time: continue
        lat = re.search(r'latitude\s*[:=]\s*(-?[\d.]+)', block, re.I)
        lon = re.search(r'long(?:itude|titude)\s*[:=]\s*(-?[\d.]+)', block, re.I)
        if lat and lon:
            latitude, longitude = float(lat[1]), float(lon[1])
        else:
            gps = re.search(r'GPS\s*\(\s*(-?[\d.]+)\s*,\s*(-?[\d.]+)', block, re.I)
            if not gps: continue
            longitude, latitude = float(gps[1]), float(gps[2])
        if not (-180 <= longitude <= 180 and -90 <= latitude <= 90): continue
        seconds = int(time[1])*3600+int(time[2])*60+int(time[3])+float('0.'+time[4])
        xy = np.array(trans.transform(longitude, latitude))
        s, distance = project(vertices, stations, xy)
        result.append(dict(time=seconds, station=s, distance=distance, lat=latitude, lon=longitude))
    check(result, 'El SRT no contiene coordenadas GPS reconocibles (latitude/longitude o GPS(longitud,latitud)).')
    return result

def render_raster(source, crs, bounds, size):
    w, h = size
    transform = from_bounds(*bounds, w, h)
    with rasterio.open(source) as ds:
        # WarpedVRT preserves internal masks, nodata and alpha at the target resolution.
        from rasterio.vrt import WarpedVRT
        from rasterio.enums import ColorInterp
        with WarpedVRT(ds,crs=crs,transform=transform,width=w,height=h,resampling=Resampling.bilinear,add_alpha=ColorInterp.alpha not in ds.colorinterp) as vrt:
            rgb = np.clip(vrt.read([1,2,3]),0,255).astype('uint8')
            # A source may have four data bands, making the new alpha band fifth.
            # dataset_mask() does not consistently use alpha in that layout.
            alpha = vrt.colorinterp.index(ColorInterp.alpha) + 1
            mask = vrt.read(alpha)
    return np.moveaxis(rgb,0,-1), mask > 0

def save_image(path, rgb, mask):
    rgba = np.dstack([rgb, mask.astype('uint8')*255])
    Image.fromarray(rgba).save(path)

def public(path):
    return '/data/'+Path(path).relative_to(STORE).as_posix()

def compare(ids):
    check(len(ids)==2 and ids[0]!=ids[1], 'Selecciona dos ZIP diferentes.')
    campaigns = [read_campaign(i) for i in ids]
    check(campaigns[0]['name'].casefold()!=campaigns[1]['name'].casefold(), 'Los ZIP deben identificar dos meses diferentes.')
    axes = [alignment(c['xml'],c['crs']) for c in campaigns]
    vertices, stations, crs, assumed = axes[0]
    v2,s2,crs2,_ = axes[1]
    check(abs(stations[0]-s2[0])<.1 and abs(stations[-1]-s2[-1])<.1, 'Los XML no cubren las mismas progresivas.')
    tr = Transformer.from_crs(crs2,crs,always_xy=True)
    check(all(np.linalg.norm(point_at(vertices,stations,s)-np.array(tr.transform(*point_at(v2,s2,s)))) < 1
              for s in np.linspace(stations[0],stations[-1],101)), 'Los alineamientos de los ZIP no coinciden (tolerancia 1 m).')
    check(stations[-1]-stations[0] <= 100000, 'El eje supera los 100 km admitidos por comparación.')
    out = STORE / uuid.uuid4().hex
    out.mkdir()
    result = dict(months=[dict(name=c['name'],video=public(c['video']),plans=[dict(name=Path(p).name,url=public(p)) for p in c['plans']]) for c in campaigns],
                  crs=crs.to_string(),start=float(stations[0]),end=float(stations[-1]),sectors=[],references=[],warnings=[])
    if assumed or axes[1][3]: result['warnings'].append('XML sin EPSG explícito: se utilizó el CRS de su ortomosaico. Verifica esta correspondencia en los planos.')
    # Same north-up grid for both months. A 250 m buffer on either side provides context.
    for start in np.arange(stations[0], stations[-1], 500):
        end = min(start+500,stations[-1])
        line = np.array([point_at(vertices,stations,s) for s in np.linspace(start,end,max(2,math.ceil(end-start)+1))])
        low, high = line.min(axis=0)-250, line.max(axis=0)+250
        bounds = [*low,*high]
        width,height = high-low
        scale = min(1400/width,1400/height)
        size = (max(1,round(width*scale)),max(1,round(height*scale)))
        images = [render_raster(c['ortho'],crs,bounds,size) for c in campaigns]
        common = images[0][1] & images[1][1]
        check(common.any(), f'Sin cobertura común de ortofotos cerca de la progresiva {start:.0f}. Verifica XML y CRS.')
        paths=[]
        for i,(rgb,mask) in enumerate(images):
            p=out/f'sector_{start:.0f}_{i}.png';save_image(p,rgb,mask);paths.append(public(p))
        delta=np.mean(np.abs(images[0][0].astype(float)-images[1][0].astype(float)),axis=2)
        changed=(delta>30)&common
        overlay=images[1][0].copy();overlay[changed]=[240,70,60]
        p=out/f'difference_{start:.0f}.png';save_image(p,overlay,common)
        result['sectors'].append(dict(start=float(start),end=float(end),images=paths,difference=public(p),
            changed_pct=round(float(changed.sum()/common.sum()*100),2),common_pct=round(float(common.mean()*100),2),
            size=size,line=[[(x-low[0])/width*size[0],(high[1]-y)/height*size[1]] for x,y in line],
            marks=[dict(s=float(s),x=float((point_at(vertices,stations,s)[0]-low[0])/width*size[0]),y=float((high[1]-point_at(vertices,stations,s)[1])/height*size[1])) for s in np.arange(math.ceil(start/100)*100,end+.01,100)]))
    targets=sorted(set([float(stations[0]),float(stations[-1])]+list(np.arange(math.ceil(stations[0]/100)*100,stations[-1],100))))
    records=[srt_records(c['srt'],crs,vertices,stations) for c in campaigns]
    for i, rec in enumerate(records):
        check(min(r['distance'] for r in rec)<500, f'El GPS del video {campaigns[i]["name"]} está lejos del eje. Revisa CRS y archivos.')
    captures=[cv2.VideoCapture(c['video']) for c in campaigns]
    try:
        check(all(c.isOpened() for c in captures),'No se pudo decodificar uno de los videos.')
        for target in targets:
            xy=point_at(vertices,stations,target)
            ref=dict(station=target,east=float(xy[0]),north=float(xy[1]),images=[],videos=[])
            for i,c in enumerate(campaigns):
                rgb,mask=render_raster(c['ortho'],crs,[xy[0]-35,xy[1]-35,xy[0]+35,xy[1]+35],(500,500))
                p=out/f'ref_{target:.2f}_{i}.png';save_image(p,rgb,mask)
                ref['images'].append(dict(url=public(p),coverage=round(float(mask.mean()*100),1)))
                r=min(records[i],key=lambda r:abs(r['station']-target))
                if abs(r['station']-target)>50 or r['distance']>500:
                    ref['videos'].append(dict(error='Sin registro GPS cercano a esta progresiva (±50 m y hasta 500 m del eje).'));continue
                captures[i].set(cv2.CAP_PROP_POS_MSEC,r['time']*1000)
                ok,frame=captures[i].read()
                if not ok:
                    ref['videos'].append(dict(error='El tiempo SRT no dispone de un fotograma decodificable.'));continue
                ratio=min(1,1000/frame.shape[1]);frame=cv2.resize(frame,(round(frame.shape[1]*ratio),round(frame.shape[0]*ratio)))
                p=out/f'video_{target:.2f}_{i}.jpg';cv2.imwrite(str(p),frame)
                ref['videos'].append(dict(**r,url=public(p)))
            result['references'].append(ref)
    finally:
        for c in captures:c.release()
    (out/'result.json').write_text(json.dumps(result),encoding='utf8')
    result['download']=public(out/'result.json')
    return result
