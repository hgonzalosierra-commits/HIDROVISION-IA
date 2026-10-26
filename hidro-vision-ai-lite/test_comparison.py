import unittest, tempfile, zipfile, json
from pathlib import Path
import processor as p

class ComparisonTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.previous=p.STORE
        p.STORE=Path(self.tmp.name)/'store'
        p.STORE.mkdir()

    def tearDown(self):
        p.STORE=self.previous
        self.tmp.cleanup()

    def campaign(self,name,color=80):
        folder=Path(self.tmp.name)/name
        for group in ['VIDEO','ORTOFOTO','XML','PLANO_OTROS']:(folder/group).mkdir(parents=True)
        with p.rasterio.open(folder/'ORTOFOTO/map.tif','w',driver='GTiff',width=1000,height=1000,count=3,dtype='uint8',crs='EPSG:32718',transform=p.from_bounds(357500,8549500,358500,8550500,1000,1000)) as ds:
            ds.write(p.np.full((3,1000,1000),color,dtype='uint8'))
        (folder/'XML/eje.xml').write_text('<LandXML><Units><Metric linearUnit="meter"/></Units><CoordinateSystem epsgCode="32718"/><Alignments><Alignment staStart="0"><CoordGeom><Line length="200"><Start>8550000 358000</Start><End>8550000 358200</End></Line></CoordGeom></Alignment></Alignments></LandXML>')
        (folder/'PLANO_OTROS/referencia.txt').write_text('Plano referencial de prueba')
        writer=p.cv2.VideoWriter(str(folder/'VIDEO/vuelo.mp4'),p.cv2.VideoWriter_fourcc(*'mp4v'),10,(160,120))
        for i in range(30):writer.write(p.np.full((120,160,3),i*7,dtype='uint8'))
        writer.release()
        trans=p.Transformer.from_crs(32718,4326,always_xy=True)
        chunks=[]
        for i in range(3):
            lon,lat=trans.transform(358000+i*100,8550000)
            chunks.append(f'{i+1}\n00:00:0{i},000 --> 00:00:0{i},999\n[latitude: {lat}] [longitude: {lon}]\n')
        (folder/'VIDEO/vuelo.srt').write_text('\n'.join(chunks))
        archive=Path(self.tmp.name)/(name+'.zip')
        with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
            for f in folder.rglob('*'):
                if f.is_file():z.write(f,name+'/'+str(f.relative_to(folder)))
        return p.load_campaign(archive,archive.name)

    def test_two_months_georeferenced_and_gps(self):
        a=self.campaign('Enero_2026',80);b=self.campaign('Julio_2026',130)
        result=p.compare([a['id'],b['id']])
        self.assertEqual(len(result['sectors']),1)
        self.assertEqual(result['sectors'][0]['changed_pct'],100)
        self.assertEqual([r['station'] for r in result['references']],[0,100,200])
        for r in result['references']:
            self.assertTrue(all(i['coverage']==100 for i in r['images']))
            for video in r['videos']:
                self.assertAlmostEqual(video['station'],r['station'],places=4)
                self.assertAlmostEqual(video['time'],r['station']/100,places=4)
                self.assertLess(video['distance'],.001)

    def test_missing_and_unsafe_archives(self):
        path=Path(self.tmp.name)/'bad.zip'
        with zipfile.ZipFile(path,'w') as z:z.writestr('../VIDEO/bad.txt','bad')
        with self.assertRaisesRegex(ValueError,'Ruta no válida'):p.load_campaign(path,'bad.zip')
        with zipfile.ZipFile(path,'w') as z:z.writestr('VIDEO/empty.txt','empty')
        with self.assertRaisesRegex(ValueError,'un video'):p.load_campaign(path,'bad.zip')

    def test_uint16_color_with_256_nodata(self):
        path=Path(self.tmp.name)/'uint16.tif'
        values=p.np.full((4,10,10),120,dtype='uint16')
        values[:,0,:]=256
        with p.rasterio.open(path,'w',driver='GTiff',width=10,height=10,count=4,dtype='uint16',nodata=256,crs='EPSG:32718',transform=p.from_bounds(0,0,10,10,10,10)) as ds:ds.write(values)
        with p.rasterio.open(path) as ds:p.validate_ortho(ds)
        rgb,mask=p.render_raster(path,'EPSG:32718',[0,0,10,10],(10,10))
        self.assertTrue((rgb[1:]==120).all())
        self.assertFalse(mask[0].any())
        self.assertTrue(mask[1:].all())
        with p.rasterio.open(path,'r+') as ds:
            values[0,5,5]=1000;ds.write(values)
        with p.rasterio.open(path) as ds:
            with self.assertRaisesRegex(ValueError,'superiores a 255'):p.validate_ortho(ds)

    def test_different_axes_are_rejected(self):
        a=self.campaign('Enero_2026');b=self.campaign('Julio_2026')
        c=p.read_campaign(b['id']);path=Path(c['xml'])
        path.write_text(path.read_text().replace('8550000','8550010'))
        with self.assertRaisesRegex(ValueError,'no coinciden'):p.compare([a['id'],b['id']])

if __name__=='__main__':unittest.main()
