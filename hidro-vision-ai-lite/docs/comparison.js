'use strict';
const $=id=>document.getElementById(id);
const inputs=[$('zipA'),$('zipB')];
const campaigns=[null,null];
let data=null,working=false;
const fmt=n=>`${Math.floor(n/1000)}+${(n%1000).toFixed(n%1?2:0).padStart(3,'0')}`;
function ready(){ $('run').disabled=working||!campaigns.every(Boolean); }
function message(id,text,error=false){$(id).textContent=text;$(id).className=error?'error':'';}
async function api(path,payload){
 const response=await fetch(path,{method:payload?'POST':'GET',headers:payload?{'Content-Type':'application/json','X-Hidro-Client':'local'}:{},body:payload?JSON.stringify(payload):undefined});
 const result=await response.json();if(!response.ok)throw Error(result.error||'Error del servidor.');return result;
}
function upload(file,index){
 return new Promise((resolve,reject)=>{
  const request=new XMLHttpRequest(),suffix=index?'B':'A',progress=$('progress'+suffix);
  request.open('POST','/api/upload?name='+encodeURIComponent(file.name));
  request.setRequestHeader('X-Hidro-Client','local');
  request.upload.onprogress=e=>{progress.hidden=false;if(e.lengthComputable)progress.value=e.loaded/e.total*100;message('status'+suffix,progress.value<100?'Cargando ZIP…':'Verificando carpetas y archivos del ZIP…');};
  request.onload=()=>{progress.hidden=true;try{const result=JSON.parse(request.responseText);if(request.status!==200)throw Error(result.error);resolve(result);}catch(e){reject(e)}};
  request.onerror=()=>{progress.hidden=true;reject(Error('No se pudo conectar con el servidor local.'))};request.send(file);
 });
}
inputs.forEach((input,index)=>input.onchange=async()=>{
 const file=input.files[0];if(!file)return;
 campaigns[index]=null;
 if(index===0){campaigns[1]=null;inputs[1].value='';message('statusB','Carga primero el ZIP del primer mes.');}
 working=true;inputs.forEach(i=>i.disabled=true);ready();
 const suffix=index?'B':'A';message('status'+suffix,'Leyendo '+file.name+'…');
 try{campaigns[index]=await upload(file,index);message('status'+suffix,`${campaigns[index].name} · ZIP validado · ${campaigns[index].crs}`);}
 catch(e){message('status'+suffix,e.message,true);}
 finally{working=false;inputs[0].disabled=false;inputs[1].disabled=!campaigns[0];if(index===0&&campaigns[0])message('statusB','Selecciona el ZIP del segundo mes.');ready();}
});
$('run').onclick=async()=>{
 working=true;ready();inputs.forEach(i=>i.disabled=true);message('processing','Preparando la comparación…');
 try{
  const job=await api('/api/compare',{ids:campaigns.map(c=>c.id)});
  let state;
  do{await new Promise(r=>setTimeout(r,1200));state=await api('/api/job/'+job.job);message('processing',state.message||'Preparando el visor…');}while(state.state==='running');
  if(state.state==='error')throw Error(state.error);
  data=state.result;render();message('processing','Comparación lista.');
 }catch(e){message('processing',e.message,true);}
 finally{working=false;inputs.forEach(i=>i.disabled=false);ready();}
};
function options(id,rows,label){$(id).replaceChildren(...rows.map((r,i)=>new Option(label(r),i)));}
function render(){
 $('entrada').hidden=true;$('resultado').hidden=false;$('resultNav').hidden=false;window.dispatchEvent(new CustomEvent('hidro:result',{detail:data}));
 $('subtitle').textContent=data.months.map(m=>m.name).join(' ↔ ')+' · '+fmt(data.start)+' a '+fmt(data.end);
 document.querySelectorAll('[data-month]').forEach(n=>n.textContent=data.months[Number(n.dataset.month)].name);
 $('warnings').textContent=[...data.warnings,'Resultados exploratorios: las diferencias visibles no constituyen un diagnóstico de daño, sedimentación o socavación.'].join(' ');
 $('download').href=data.download;$('download').download='comparacion.json';
 options('sector',data.sectors,s=>fmt(s.start)+' a '+fmt(s.end));
 for(const id of ['progresiva','gpsStation'])options(id,data.references,r=>fmt(r.station));
 ['A','B'].forEach((s,i)=>{const v=$('video'+s);v.src=data.months[i].video;let note=document.getElementById('codec'+s);if(!note){note=document.createElement('p');note.id='codec'+s;v.after(note);}note.textContent='';v.onerror=()=>message('codec'+s,'El navegador no puede reproducir este códec. Los fotogramas extraídos siguen disponibles.',true);});
 $('plans').replaceChildren();data.months.forEach(m=>{const title=document.createElement('h4');title.textContent=m.name;$('plans').append(title);const row=document.createElement('div');row.className='filelinks';m.plans.forEach(p=>{const a=document.createElement('a');a.textContent=p.name;a.href=p.url;a.target='_blank';a.rel='noopener';row.append(a)});$('plans').append(row)});
 sector();references();videos();window.scrollTo(0,0);
}
function sector(){
 const s=data.sectors[Number($('sector').value)];$('plantaA').src=s.images[0];$('plantaB').src=s.images[1];$('mapa').src=s.difference;
 $('metricas').textContent=`Cobertura común: ${s.common_pct}% de la vista · Diferencias RGB: ${s.changed_pct}% de la cobertura común · ${data.crs}`;
 const svg=$('eje'),ns='http://www.w3.org/2000/svg';svg.replaceChildren();svg.setAttribute('viewBox',`0 0 ${s.size[0]} ${s.size[1]}`);
 const line=document.createElementNS(ns,'polyline');line.setAttribute('points',s.line.map(p=>p.join(',')).join(' '));line.setAttribute('stroke','#fff200');line.setAttribute('stroke-width','3');line.setAttribute('fill','none');svg.append(line);
 for(const m of s.marks){const dot=document.createElementNS(ns,'circle');dot.setAttribute('cx',m.x);dot.setAttribute('cy',m.y);dot.setAttribute('r','4');dot.setAttribute('fill','#fff200');svg.append(dot);const text=document.createElementNS(ns,'text');text.setAttribute('x',Math.min(m.x+8,s.size[0]-100));text.setAttribute('y',Math.max(20,m.y));text.setAttribute('font-size','18');text.setAttribute('fill','#fff200');text.setAttribute('stroke','#102331');text.setAttribute('stroke-width','2');text.setAttribute('paint-order','stroke');text.textContent=fmt(m.s);svg.append(text)}slide();window.dispatchEvent(new CustomEvent('hidro:sector',{detail:s}));
}
function slide(){$('plantaB').style.clipPath=`inset(0 ${100-Number($('slider').value)}% 0 0)`;}
function references(){const r=data.references[Number($('progresiva').value)];['A','B'].forEach((s,i)=>{$('ref'+s).src=r.images[i].url});$('coord').textContent=`${fmt(r.station)} · E ${r.east.toFixed(2)} / N ${r.north.toFixed(2)} · ${data.crs}`;}
function videos(){const r=data.references[Number($('gpsStation').value)];['A','B'].forEach((suffix,i)=>{const v=r.videos[i],img=$('gps'+suffix),video=$('video'+suffix);img.hidden=!!v.error;if(v.error){img.removeAttribute('src');message('gpsInfo'+suffix,v.error,true);return;}img.src=v.url;message('gpsInfo'+suffix,`${v.time.toFixed(2)} s · Progresiva del dron ${fmt(v.station)} · Separación al eje ${v.distance.toFixed(1)} m`);});window.dispatchEvent(new CustomEvent('hidro:reference',{detail:r}));stopOriginals();if($('originalVideos').open)startOriginals();}
$('sector').onchange=sector;$('slider').oninput=slide;$('progresiva').onchange=references;$('gpsStation').onchange=videos;
$('back').onclick=()=>{stopOriginals();$('resultado').hidden=true;$('resultNav').hidden=true;$('entrada').hidden=false;['A','B'].forEach(s=>$('video'+s).pause());history.replaceState(null,'',location.pathname);window.scrollTo(0,0);};
if(location.protocol==='file:'){
 inputs.forEach(i=>i.disabled=true);message('service','Para procesar los ZIP, inicia INICIAR_HIDRO_VISION.cmd y abre http://127.0.0.1:8765. La comparación necesita el procesador local.',true);
}else{api('/api/health').then(()=>message('service','Procesador local disponible.')).catch(()=>{inputs.forEach(i=>i.disabled=true);message('service','Inicia INICIAR_HIDRO_VISION.cmd para conectar el procesador local.',true)});}

async function restoreComparison(){
 const saved=new URLSearchParams(location.search).get('resultado');
 if(!saved||!/^\/data\/[a-f0-9]{32}\/result\.json$/.test(saved))return;
 try{data=await api(saved);data.download=saved;render();const station=new URLSearchParams(location.search).get('progresiva');const index=data.references.findIndex(r=>String(r.station)===station);if(index>=0){$('gpsStation').value=index;videos();}if(location.hash==='#videos')$('videos').scrollIntoView();}catch(e){message('processing','No se pudo abrir la comparación guardada: '+e.message,true);}
}
if(location.protocol!=='file:')restoreComparison();

let playbackEpoch=0;
function stopOriginals(){playbackEpoch++;['A','B'].forEach(s=>$('video'+s).pause());}
function waitVideo(video,predicate,epoch){return new Promise((resolve,reject)=>{const started=Date.now();const timer=setInterval(()=>{if(epoch!==playbackEpoch){clearInterval(timer);reject(Error('cancelled'));}else if(video.error){clearInterval(timer);reject(Error('No se puede reproducir uno de los videos.'));}else if(predicate()){clearInterval(timer);resolve();}else if(Date.now()-started>20000){clearInterval(timer);reject(Error('Un video tarda en cargar. Pulsa «Reproducir ambos» para intentar de nuevo.'));}},50);});}
async function startOriginals(){
 stopOriginals();const epoch=playbackEpoch;
 const ref=data?.references[Number($('gpsStation').value)];
 if(!ref||ref.videos.some(v=>v.error||!Number.isFinite(v.time))){message('playbackStatus','No hay tiempos de video disponibles para ambos meses en esta progresiva.');return;}
 const pair=[$('videoA'),$('videoB')];message('playbackStatus','Preparando ambos videos…');
 try{
  await Promise.all(pair.map(async(video,i)=>{
   video.muted=true;video.playbackRate=1;video.preload='auto';
   await waitVideo(video,()=>video.readyState>=1,epoch);
   if(ref.videos[i].time>=video.duration)throw Error('La progresiva seleccionada queda fuera de la duración de un video.');
   video.currentTime=ref.videos[i].time;
   await waitVideo(video,()=>!video.seeking&&video.readyState>=3,epoch);
  }));
  if(epoch!==playbackEpoch||!$('originalVideos').open)return;
  await Promise.all(pair.map(video=>video.play()));
  if(epoch!==playbackEpoch)return;
  message('playbackStatus','Ambos videos iniciados desde la progresiva '+fmt(ref.station)+'. Audio silenciado.');
 }catch(e){if(epoch!==playbackEpoch)return;stopOriginals();message('playbackStatus',e.message,true);}
}
$('originalVideos').ontoggle=()=>{if($('originalVideos').open)startOriginals();else{stopOriginals();message('playbackStatus','');}};
$('playBoth').onclick=startOriginals;
$('pauseBoth').onclick=()=>{stopOriginals();message('playbackStatus','Ambos videos pausados.');};
['A','B'].forEach(s=>$('video'+s).addEventListener('ended',()=>{stopOriginals();message('playbackStatus','Reproducción finalizada: uno de los videos llegó al final.');}));
