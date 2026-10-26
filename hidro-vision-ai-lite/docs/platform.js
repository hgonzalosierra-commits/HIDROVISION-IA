(() => {
 'use strict';
 const by=id=>document.getElementById(id);
 const types={enrocado:'Posible desplazamiento del enrocado',erosion:'Posible erosión del talud',colmatacion:'Posible colmatación',deformacion:'Posible asentamiento o deformación',grietas:'Posibles grietas',agua:'Menor superficie de agua visible',vegetacion:'Mayor cobertura vegetal visible',dragado:'Indicios de intervención / posible dragado',pie:'Revisar el pie del dique',sin_cambio:'Sin cambio relevante'};
 const levels={seguimiento:'Seguimiento',prioritaria:'Inspección prioritaria',urgente:'Alerta urgente'};
 let library=[],saved=[],active=null,comparison=null,reference=null,rows=[],editing=null,latestReport=null,refreshToken=0,deliverySettings=null,deliveries=[],deliveryBusy=false;
 const station=n=>`${Math.floor(n/1000)}+${(n%1000).toFixed(n%1?2:0).padStart(3,'0')}`;
 const months=['Enero','Febrero','Marzo','Abril','Mayo','Junio','Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre'];
 const label=c=>c.month&&c.year?`${months[c.month-1]} ${c.year} · ${c.name}`:c.name;
 function node(tag,text,cls){const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;}
 async function request(path,payload){const r=await fetch('/api/platform/'+path,{method:payload?'POST':'GET',headers:payload?{'Content-Type':'application/json','X-Hidro-Client':'local'}:{},body:payload?JSON.stringify(payload):undefined,cache:'no-store'});if(!r.headers.get('content-type')?.includes('application/json'))throw Error('El servidor no tiene cargada esta versión. Reinicia INICIAR_HIDRO_VISION.cmd y recarga la página.');const value=await r.json();if(!r.ok)throw Error(value.error||'No se pudo completar la operación.');return value;}
 function status(id,text,error=false){by(id).textContent=text;by(id).className=error?'error':'';}
 function link(url,text,cls){const a=node('a',text,cls);a.href=url;return a;}
 function resultLink(r){return '/?resultado='+encodeURIComponent(r.url)+'#planta';}
 function selectCampaigns(){
  campaigns[0]=library.find(c=>c.id===by('libraryA').value)||null;
  campaigns[1]=library.find(c=>c.id===by('libraryB').value)||null;
  ready();
  if(campaigns[0]&&campaigns[1]&&campaigns[0].id===campaigns[1].id){by('run').disabled=true;status('processing','Selecciona dos campañas diferentes.',true);return;}
  status('processing','');
 }
 async function refreshLibrary(){
  const [all,comparisons]=await Promise.all([request('campaigns'),request('comparisons')]);
  saved=comparisons;const seen=new Set();library=all.filter(c=>{const key=[c.name,c.month,c.year].join('|');if(seen.has(key))return false;seen.add(key);return true;});
  by('historyCount').textContent=`${library.length} campañas disponibles. Las cargas repetidas del mismo mes y nombre muestran la versión más reciente.`;
  const history=by('campaignHistory');history.replaceChildren();
  if(!library.length)history.append(node('p','Tu primera campaña aparecerá aquí al validar el ZIP.','empty-state'));
  library.forEach(c=>{const row=node('div',undefined,'history-row'),left=node('div');left.append(node('strong',label(c)),node('small',`${c.crs} · Video + SRT · Ortofoto · XML · ${c.files.PLANO_OTROS} referencias`));row.append(left,node('span','✓ Validada','badge'));history.append(row);});
  ['libraryA','libraryB'].forEach(id=>{const selected=by(id).value;by(id).replaceChildren(new Option('Selecciona una campaña',''),...library.map(c=>new Option(label(c),c.id)));if(library.some(c=>c.id===selected))by(id).value=selected;});
  by('savedComparisons').replaceChildren();
  if(saved.length){by('savedComparisons').append(node('h3','Comparaciones ya procesadas'));saved.slice(0,6).forEach(r=>by('savedComparisons').append(link(resultLink(r),r.months.join(' ↔ ')+' · Abrir sin volver a procesar')));}
  selectCampaigns();
 }
 async function register(file){
  if(!file)return;if(!file.name.toLowerCase().endsWith('.zip')){status('statusA','Selecciona un archivo ZIP.',true);return;}
  const month=Number(by('campaignMonth').value),year=Number(by('campaignYear').value);
  if(!Number.isInteger(year)||year<2000||year>2100){status('statusA','Indica un año entre 2000 y 2100.',true);return;}
  working=true;by('zipA').disabled=true;by('run').disabled=true;by('zipChecks').classList.remove('valid');status('statusA','Validando y registrando '+file.name+'…');
  try{const c=await upload(file,0);await request('campaign',{id:c.id,month,year});by('zipChecks').classList.add('valid');status('statusA',`${c.name}: campaña guardada. Las cuatro carpetas fueron verificadas.`);await refreshLibrary();const target=by('libraryA').value?'libraryB':'libraryA';by(target).value=c.id;selectCampaigns();}
  catch(e){status('statusA',e.message,true);}
  finally{working=false;by('zipA').disabled=false;selectCampaigns();}
 }
 function updateScope(){
  if(!active||!reference)return;
  by('findingScope').textContent=`Comparación ${active.months.map(m=>m.name).join(' ↔ ')} · Progresiva del dron ${station(reference.station)}. Selecciona otra progresiva en la sección de videos para registrar un hallazgo en esa ubicación.`;
 }
 function updateDeliveryButtons(){
  const valid=latestReport&&latestReport.executive&&!latestReport.stale&&deliverySettings?.ready;
  const previous=deliveries.find(d=>d.report===latestReport?.id);
  by('prepareReport').disabled=deliveryBusy||!valid||!!(previous&&previous.state!=='copied_to_onedrive');
  by('sendReport').disabled=deliveryBusy||!valid||!previous||!['copied_to_onedrive','failed'].includes(previous.state)||!by('syncConfirmed').checked||!by('scenarioConfirmed').checked;
 }
 async function loadDeliverySettings(){
  deliverySettings=await request('delivery-settings');
  by('onedriveFolder').value=deliverySettings.onedrive_folder;
  by('remoteFolder').value=deliverySettings.remote_folder;
  by('deliverySettingsInfo').textContent=(deliverySettings.webhook_configured?'Webhook guardado. Déjalo vacío para conservarlo. ':'Pega la URL original del webhook. ')+(deliverySettings.api_key_configured?'Clave guardada. ':'')+'Los destinatarios se configuran en Make.';
  updateDeliveryButtons();
 }
 function resetForm(){editing=null;by('findingForm').reset();by('findingReviewer').value=localStorage.getItem('hidro-reviewer')||'';status('findingMessage','');}
 function edit(row){
  const i=active.references.findIndex(r=>Math.abs(r.station-row.station)<.001);
  if(i>=0){by('gpsStation').value=i;by('gpsStation').dispatchEvent(new Event('change'));}
  editing=row.id;by('findingCategory').value=row.category;by('findingLevel').value=row.level;by('findingEvidence').value=row.evidence;by('findingRationale').value=row.rationale;by('findingReviewer').value=row.reviewer;by('findingVerified').checked=!!row.verified;
  by('findingForm').scrollIntoView({behavior:'smooth',block:'start'});status('findingMessage','Editando un hallazgo guardado. Se conservará el historial de la revisión.');
 }
 async function removeFinding(row,button){
  if(!window.confirm(`¿Eliminar el hallazgo de ${station(row.station)}: ${types[row.category]}? Podrás recuperarlo desde «Hallazgos eliminados».`))return;
  const selected=comparison;button.disabled=true;
  try{await request('delete-finding',{comparison:selected,id:row.id,expected_updated:row.updated});if(comparison!==selected)return;if(editing===row.id)resetForm();await refreshWorkflow();status('findingMessage','Hallazgo eliminado. Puedes restaurarlo desde Hallazgos eliminados. Genera un nuevo PDF para actualizar el informe.');}
  catch(error){if(comparison===selected)status('findingMessage',error.message,true);}finally{button.disabled=false;}
 }
 async function restoreFinding(row,button){
  const selected=comparison;button.disabled=true;
  try{await request('restore-finding',{comparison:selected,id:row.id});if(comparison!==selected)return;await refreshWorkflow();status('findingMessage','Hallazgo restaurado. Genera un nuevo PDF para incluirlo en el informe actualizado.');}
  catch(error){if(comparison===selected)status('findingMessage',error.message,true);}finally{button.disabled=false;}
 }
 async function refreshWorkflow(){
  if(!comparison)return;const token=++refreshToken;
  const [findings,reports,history,deleted]=await Promise.all([request('findings?comparison='+comparison),request('reports?comparison='+comparison),request('deliveries?comparison='+comparison),request('deleted-findings?comparison='+comparison)]);
  if(token!==refreshToken)return;rows=findings;
  by('findingList').replaceChildren();
  if(!rows.length)by('findingList').append(node('p','Aún no hay hallazgos registrados en esta comparación. Revisa las imágenes y documenta lo que observas.','empty-state'));
  rows.forEach(row=>{const card=node('article',undefined,'finding-row'),body=node('div');body.append(node('h4',`${station(row.station)} · ${types[row.category]}`),node('span',levels[row.level],'pill'),node('p',row.evidence),node('p','Motivo: '+row.rationale),node('small',`${row.reviewer} · ${row.verified?'Verificado en campo':'Pendiente de campo'}`));const actions=node('div',undefined,'finding-actions'),button=node('button','Revisar / corregir','secondary'),remove=node('button','Eliminar','secondary danger');button.onclick=()=>edit(row);remove.onclick=()=>removeFinding(row,remove);actions.append(button,remove);card.append(body,actions);by('findingList').append(card);});
  by('deletedFindingList').replaceChildren();by('deletedFindingsLabel').textContent=`Hallazgos eliminados (${deleted.length})`;
  deleted.forEach(row=>{const card=node('article',undefined,'finding-row'),body=node('div'),restore=node('button','Restaurar','secondary');body.append(node('h4',`${station(row.station)} · ${types[row.category]}`),node('p',row.evidence),node('small','Eliminado: '+new Date(row.deleted).toLocaleString('es-PE')));restore.onclick=()=>restoreFinding(row,restore);card.append(body,restore);by('deletedFindingList').append(card);});
  if(!deleted.length)by('deletedFindingList').append(node('p','No hay hallazgos eliminados en esta comparación.','muted'));
  const previousId=latestReport?.id;
  latestReport=reports[0]||null;deliveries=history;
  if(previousId!==latestReport?.id){by('syncConfirmed').checked=false;by('alertPreview').textContent='';}
  if(!by('reportProject').value&&latestReport?.project)by('reportProject').value=latestReport.project;
  by('reportList').replaceChildren();reports.forEach((r,i)=>{const a=link(r.url,(i===0?'Último informe':'Informe anterior')+' · '+new Date(r.created).toLocaleString('es-PE')+(!r.executive?' · Formato anterior':r.stale?' · Hay cambios posteriores':''),'report-link');a.target='_blank';a.rel='noopener';by('reportList').append(a);});
  by('latestReportInfo').textContent=!latestReport?'Genera el informe ejecutivo antes de preparar el envío.':!latestReport.executive?'Genera un nuevo informe con la plantilla ejecutiva.':latestReport.stale?'Hay cambios posteriores al PDF. Genera un nuevo informe antes de enviarlo.':`${latestReport.project} · ${active.months.map(m=>m.name).join(' / ')} · Generado ${new Date(latestReport.created).toLocaleString('es-PE')}`;
  by('alertList').replaceChildren();history.slice(0,8).forEach(d=>{const item=node('div',undefined,'delivery-record');item.append(node('strong',d.label),node('p',d.detail),node('small',d.file_name+' · '+new Date(d.updated).toLocaleString('es-PE')));by('alertList').append(item);});
  if(!history.length)by('alertList').append(node('p','Aún no se ha preparado ningún informe para envío.','muted'));
  updateDeliveryButtons();
 }
 window.addEventListener('hidro:result',e=>{active=e.detail;comparison=active.download?.match(/\/data\/([a-f0-9]{32})\//)?.[1];resetForm();latestReport=null;deliveries=[];by('reportProject').value='';by('syncConfirmed').checked=false;by('scenarioConfirmed').checked=false;by('alertPreview').textContent='';status('alertMessage','');status('reportMessage','');if(comparison)refreshWorkflow().catch(e=>status('findingMessage',e.message,true));});
 window.addEventListener('hidro:reference',e=>{reference=e.detail;resetForm();updateScope();});
 window.addEventListener('DOMContentLoaded',()=>{
  document.querySelectorAll('.workflow-strip a[href="#entrada"]').forEach(a=>a.addEventListener('click',()=>{if(by('entrada').hidden)by('back').click();}));
  document.querySelectorAll('.workflow-strip a:not([href="#entrada"])').forEach(a=>a.addEventListener('click',e=>{if(by('resultado').hidden){e.preventDefault();status('processing','Selecciona dos campañas o abre una comparación guardada para acceder a esta etapa.');by('processing').scrollIntoView({behavior:'smooth',block:'center'});}}));
  const today=new Date();by('campaignMonth').value=today.getMonth()+1;by('campaignYear').value=today.getFullYear();
  by('zipA').onchange=()=>register(by('zipA').files[0]);
  const drop=by('zipDrop');['dragenter','dragover'].forEach(type=>drop.addEventListener(type,e=>{e.preventDefault();drop.classList.add('dragging');}));['dragleave','drop'].forEach(type=>drop.addEventListener(type,e=>{e.preventDefault();drop.classList.remove('dragging');}));drop.addEventListener('drop',e=>{if(!working)register(e.dataTransfer.files[0]);});
  by('libraryA').onchange=selectCampaigns;by('libraryB').onchange=selectCampaigns;
  by('refreshHistory').onclick=()=>refreshLibrary().catch(e=>status('historyCount',e.message,true));
  by('findingCategory').replaceChildren(...Object.entries(types).map(([value,title])=>new Option(title,value)));
  by('clearFinding').onclick=resetForm;
  by('findingForm').onsubmit=async e=>{
   e.preventDefault();if(!comparison||!reference)return;
   const payload={comparison,station:reference.station,category:by('findingCategory').value,level:by('findingLevel').value,evidence:by('findingEvidence').value,rationale:by('findingRationale').value,reviewer:by('findingReviewer').value,verified:by('findingVerified').checked};if(editing)payload.id=editing;
   const button=e.target.querySelector('button[type=submit]');button.disabled=true;
   try{const row=await request('finding',payload);editing=row.id;try{localStorage.setItem('hidro-reviewer',payload.reviewer);}catch{}await refreshWorkflow();status('findingMessage','Hallazgo guardado con evidencia, revisor e historial de cambios.');}
   catch(error){status('findingMessage',error.message,true);}finally{button.disabled=false;}
  };
  by('createReport').onclick=async()=>{
   if(!comparison)return;const selected=comparison,project=by('reportProject').value.trim();if(project.length<3){status('reportMessage','Indica el nombre del dique o tramo.',true);return;}
   by('createReport').disabled=true;status('reportMessage','Generando el informe ejecutivo…');
   try{await request('report',{comparison:selected,project});if(comparison===selected){await refreshWorkflow();status('reportMessage','Informe ejecutivo disponible para revisión de jefatura.');}}
   catch(e){status('reportMessage',e.message,true);}finally{by('createReport').disabled=false;}
  };
  by('deliverySettingsForm').onsubmit=async e=>{
   e.preventDefault();try{await request('delivery-settings',{onedrive_folder:by('onedriveFolder').value,remote_folder:by('remoteFolder').value,webhook_url:by('makeWebhook').value,api_key:by('makeApiKey').value});by('makeWebhook').value='';by('makeApiKey').value='';await loadDeliverySettings();status('deliverySettingsMessage','Configuración guardada.');}
   catch(error){status('deliverySettingsMessage',error.message,true);}
  };
  by('prepareReport').onclick=async()=>{
   if(!latestReport||deliveryBusy)return;const selected=comparison;deliveryBusy=true;updateDeliveryButtons();status('alertMessage','Copiando únicamente el último PDF a OneDrive…');
   try{const r=await request('prepare-report',{comparison:selected,report_id:latestReport.id});if(comparison===selected){await refreshWorkflow();by('alertPreview').textContent=JSON.stringify(r.payload,null,2);status('alertMessage','PDF copiado: '+r.file_name+'. Espera a que aparezca en OneDrive web y confirma la sincronización.');}}
   catch(e){status('alertMessage',e.message,true);}finally{deliveryBusy=false;updateDeliveryButtons();}
  };
  by('sendReport').onclick=async()=>{
   if(!latestReport||deliveryBusy)return;const selected=comparison;deliveryBusy=true;updateDeliveryButtons();status('alertMessage','Avisando a Make. Puede tardar hasta tres minutos si el escenario espera la confirmación de Outlook…');
   try{const r=await request('send-report',{comparison:selected,report_id:latestReport.id,sync_confirmed:by('syncConfirmed').checked,scenario_confirmed:by('scenarioConfirmed').checked});if(comparison===selected){await refreshWorkflow();status('alertMessage',r.label+'. '+r.detail,['failed','uncertain'].includes(r.state));}}
   catch(e){status('alertMessage',e.message+' Si la conexión se cortó, revisa el seguimiento y Make antes de reintentar.',true);}
   finally{deliveryBusy=false;updateDeliveryButtons();}
  };
  by('syncConfirmed').onchange=updateDeliveryButtons;by('scenarioConfirmed').onchange=updateDeliveryButtons;
  loadDeliverySettings().catch(e=>status('deliverySettingsMessage',e.message,true));
  if(location.protocol!=='file:')refreshLibrary().catch(e=>status('historyCount','No se pudo cargar el historial: '+e.message,true));
 });
})();
