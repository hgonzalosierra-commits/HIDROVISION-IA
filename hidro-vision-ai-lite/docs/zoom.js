(() => {
 'use strict';
 const viewport=document.getElementById('mapViewport'),content=document.getElementById('mapContent');
 let width=1000,height=1000,scale=1,base=1,x=0,y=0,bounds=null,version=0;
 const pointers=new Map();let previous=null;
 function paint(){content.style.width=width+'px';content.style.height=height+'px';content.style.transform=`translate(${x}px,${y}px) scale(${scale})`;document.getElementById('zoomLevel').textContent=Math.round(scale/base*100)+'%';}
 function fit(){const b=bounds||[0,0,width,height];base=Math.min(viewport.clientWidth/(b[2]-b[0]),viewport.clientHeight/(b[3]-b[1]))*.92;scale=base;x=(viewport.clientWidth-(b[2]-b[0])*scale)/2-b[0]*scale;y=(viewport.clientHeight-(b[3]-b[1])*scale)/2-b[1]*scale;paint();}
 function zoom(factor,cx=viewport.clientWidth/2,cy=viewport.clientHeight/2){const next=Math.min(base*12,Math.max(base*.5,scale*factor));x=cx-(cx-x)*next/scale;y=cy-(cy-y)*next/scale;scale=next;paint();}
 function position(e){const r=viewport.getBoundingClientRect();return{x:e.clientX-r.left,y:e.clientY-r.top};}
 viewport.addEventListener('wheel',e=>{e.preventDefault();const p=position(e);zoom(Math.exp(-e.deltaY*.002),p.x,p.y);},{passive:false});
 viewport.addEventListener('dblclick',e=>{const p=position(e);zoom(1.8,p.x,p.y);});
 function gesture(){const ps=[...pointers.values()];if(ps.length===1)return {...ps[0],distance:0};if(ps.length>1)return {x:(ps[0].x+ps[1].x)/2,y:(ps[0].y+ps[1].y)/2,distance:Math.hypot(ps[0].x-ps[1].x,ps[0].y-ps[1].y)};return null;}
 viewport.addEventListener('pointerdown',e=>{pointers.set(e.pointerId,position(e));viewport.setPointerCapture(e.pointerId);previous=gesture();});
 viewport.addEventListener('pointermove',e=>{if(!pointers.has(e.pointerId))return;pointers.set(e.pointerId,position(e));const current=gesture();if(previous){x+=current.x-previous.x;y+=current.y-previous.y;if(current.distance&&previous.distance)zoom(current.distance/previous.distance,current.x,current.y);else paint();}previous=current;});
 function release(e){pointers.delete(e.pointerId);previous=gesture();}
 viewport.addEventListener('pointerup',release);viewport.addEventListener('pointercancel',release);
 viewport.addEventListener('keydown',e=>{if(['+','=','-','0','ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(e.key))e.preventDefault();if(e.key==='+'||e.key==='=')zoom(1.3);if(e.key==='-')zoom(1/1.3);if(e.key==='0')fit();if(e.key==='ArrowLeft')x+=50;if(e.key==='ArrowRight')x-=50;if(e.key==='ArrowUp')y+=50;if(e.key==='ArrowDown')y-=50;paint();});
 document.getElementById('zoomIn').onclick=()=>zoom(1.4);document.getElementById('zoomOut').onclick=()=>zoom(1/1.4);
 new ResizeObserver(()=>{if(viewport.clientWidth)fit();}).observe(viewport);
 window.addEventListener('hidro:sector',async e=>{
  const token=++version;[width,height]=e.detail.size;bounds=null;fit();
  try{
   const imgs=await Promise.all(e.detail.images.map(url=>new Promise((resolve,reject)=>{const i=new Image();i.onload=()=>resolve(i);i.onerror=reject;i.src=url;})));
   if(token!==version)return;
   const c=document.createElement('canvas');c.width=160;c.height=160;const ctx=c.getContext('2d',{willReadFrequently:true});let minx=160,miny=160,maxx=0,maxy=0;
   for(const img of imgs){ctx.clearRect(0,0,160,160);ctx.drawImage(img,0,0,160,160);const pixels=ctx.getImageData(0,0,160,160).data;for(let yy=0;yy<160;yy++)for(let xx=0;xx<160;xx++)if(pixels[(yy*160+xx)*4+3]>100){minx=Math.min(minx,xx);miny=Math.min(miny,yy);maxx=Math.max(maxx,xx+1);maxy=Math.max(maxy,yy+1);}}
   if(maxx>minx&&maxy>miny)bounds=[minx/160*width,miny/160*height,maxx/160*width,maxy/160*height];fit();
  }catch{/* Full extent remains usable if coverage fitting fails. */}
 });
})();