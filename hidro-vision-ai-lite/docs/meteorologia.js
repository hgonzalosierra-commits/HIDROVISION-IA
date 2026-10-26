(() => {
 let context=null,reference=null,version=0;
 const box=()=>document.getElementById('weatherNote');
 const paragraph=t=>{const p=document.createElement('p');p.textContent=t;box().append(p);};
 const link=(text,url)=>{const a=document.createElement('a');a.textContent=text;a.href=url;a.target='_blank';a.rel='noopener';const p=document.createElement('p');p.append(a);box().append(p);};
 function render(){
  if(!context||!reference)return;
  const r=context.references.find(r=>Math.abs(r.station-reference.station)<.001);if(!r)return;
  box().replaceChildren();
  paragraph(`Punto del eje XML: ${r.lat.toFixed(6)}, ${r.lon.toFixed(6)} · Progresiva ${r.station.toFixed(2)} m. Estación meteorológica más cercana del catálogo consultado: ${r.nearest.nom} (${r.nearest.cod}), a ${r.distance_km.toFixed(2)} km en línea recta.`);
  for(const p of r.periods){
   if(p.rain){const v=p.rain;paragraph(`Según los registros horarios publicados por SENAMHI para ${r.nearest.nom}, ${p.name} acumula ${v.sum_mm.toLocaleString('es-PE')} mm en ${v.valid_hours} de ${v.expected_hours} horas esperadas. Faltan ${v.expected_hours-v.valid_hours} horas válidas: es una suma parcial, no un total mensual completo.`);link(`Ver registros utilizados · ${p.name}`,v.evidence);}
   else paragraph(`${p.name}: precipitación aún no consultada para esta estación y período; no se ha asignado cero ni reutilizado otro mes.`);
  }
  link('Abrir estación en SENAMHI · Tabla → seleccionar mes','https://www.senamhi.gob.pe/mapas/mapa-estaciones-ms/map_red_graf.php?cod='+encodeURIComponent(r.nearest.cod));
  if(r.socsi_january){paragraph('Como referencia hidrológica del río Cañete, SENAMHI reporta en Socsi un caudal medio de enero de 2026 de 58,570 m³/s, frente a 93,848 m³/s del promedio histórico (anomalía −38%). El caudal del 1 de enero fue 9,485 m³/s y el del 31 de enero 80,083 m³/s. Son datos de otra estación, no mediciones en el dique ni una comparación con julio.');link('Boletín hidrológico SENAMHI · enero 2026 · tabla 1, página 5','https://www.senamhi.gob.pe/load/file/02609SENA-175.pdf');}
  paragraph('La lluvia local aporta contexto, pero no demuestra la causa de una mayor superficie de agua en la imagen. Para corroborar una avenida se requieren caudales de las fechas reales de vuelo y precipitación aguas arriba. Los datos horarios de SENAMHI se publican sin control de calidad. Consulta realizada el 25/10/2026; no es una conexión en tiempo real.');
  link('Catálogo oficial de estaciones utilizado',context.catalog_source);
 }
 window.addEventListener('hidro:result',async e=>{
  const token=++version;context=null;box().textContent='Buscando la estación más cercana a las coordenadas del eje…';
  const id=e.detail.download?.match(/\/data\/([a-f0-9]{32})\//)?.[1];if(!id)return;
  try{const response=await fetch('/api/platform/weather?comparison='+id);if(!response.ok)throw Error('No se pudo consultar el contexto SENAMHI.');const result=await response.json();if(token!==version)return;context=result;render();}catch(error){if(token===version)box().textContent=error.message;}
 });
 window.addEventListener('hidro:reference',e=>{reference=e.detail;render();});
})();
