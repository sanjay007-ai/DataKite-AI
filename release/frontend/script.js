const $=s=>document.querySelector(s), $$=s=>[...document.querySelectorAll(s)];
let charts={}, hasData=false, deferredInstall=null, retryAction=null, errorTimer=null, dashboardLoading=false, exportLoading=false;
const state={files:[],dataset:null,datasetId:null,dashboard:null};
function setText(id,value){const el=$('#'+id);if(el)el.textContent=String(value??'')}
function setDisabled(id,value){const el=$('#'+id);if(el)el.disabled=!!value}
const chartBase={responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}},scales:{x:{grid:{color:'rgba(255,255,255,.05)'},ticks:{color:'#747b8b',font:{size:9}}},y:{grid:{color:'rgba(255,255,255,.05)'},ticks:{color:'#747b8b',font:{size:9}}}}};
function toast(t){const el=$('#toast');if(!el)return;el.textContent=t;el.classList.add('show');clearTimeout(window._toast);window._toast=setTimeout(()=>el.classList.remove('show'),2600)}
function money(v){if(v===null||v===undefined||Number.isNaN(Number(v)))return '—';const n=Number(v);const a=Math.abs(n);if(a>=1e9)return '₹'+(n/1e9).toFixed(2)+'B';if(a>=1e6)return '₹'+(n/1e6).toFixed(2)+'M';if(a>=1e3)return '₹'+(n/1e3).toFixed(1)+'K';return '₹'+n.toLocaleString(undefined,{maximumFractionDigits:0})}
function fmt(v){if(v===null||v===undefined)return '—';if(typeof v==='number')return v.toLocaleString(undefined,{maximumFractionDigits:2});return String(v)}
function showView(name){$$('.view').forEach(v=>v.classList.toggle('active',v.id==='view-'+name));$$('.nav-item,[data-view]').forEach(b=>b.classList.toggle('active',b.dataset.view===name));setText('pageTitle',{overview:'Overview',dashboard:'Dashboard',chat:'Ask DataKite',exports:'Export Center'}[name]||'Overview');$('#sidebar').classList.remove('open');if(name==='dashboard'&&hasData)loadDashboard()}
$$('[data-view]').forEach(b=>b.addEventListener('click',()=>showView(b.dataset.view)));
$('#menuBtn').addEventListener('click',()=>$('#sidebar').classList.toggle('open'));
$('#newAnalysis').addEventListener('click',()=>{state.files=[];state.dataset=null;state.datasetId=null;state.dashboard=null;hasData=false;charts={};$('#fileInput').value='';$('#selectedFiles').textContent='';$('#sideStatus').textContent='Waiting for data';$('#chatDataStatus').textContent='No file uploaded';$('#datasetName').textContent='No dataset loaded';$('#datasetRows').textContent='0 rows';$('#datasetCols').textContent='0 columns';hideError();showView('overview');toast('New analysis started')});
function renderSelected(){const el=$('#selectedFiles');if(!state.files.length){el.innerHTML='';return}el.innerHTML=state.files.map((f,i)=>`<span class="file-chip"><i>${i+1}</i>${escape(f.name)}</span>`).join('')}
$('#browseBtn').addEventListener('click',()=>$('#fileInput').click());$('#changeData').addEventListener('click',()=>$('#fileInput').click());
$('#fileInput').addEventListener('change',e=>{state.files=[...e.target.files].slice(0,10);renderSelected();if(e.target.files.length>10)toast('Only the first 10 files were selected');if(state.files.length)uploadFiles()});
const dz=$('#uploadDropzone');['dragenter','dragover'].forEach(x=>dz.addEventListener(x,e=>{e.preventDefault();dz.classList.add('drag')}));['dragleave','drop'].forEach(x=>dz.addEventListener(x,e=>{e.preventDefault();dz.classList.remove('drag')}));dz.addEventListener('drop',e=>{state.files=[...e.dataTransfer.files].slice(0,10);renderSelected();if(e.dataTransfer.files.length>10)toast('Only the first 10 files were selected');if(state.files.length)uploadFiles()});
function friendlyError(err,action){const raw=String(err?.message||err||'');const low=raw.toLowerCase();if(low.includes('no usable data')||low.includes('no usable business table')||low.includes('no tabular'))return {title:'No usable data found',message:'DataKite could not find a structured table in the selected file.',fix:'Use a file with column headers and data rows, then try again.'};if(low.includes('unsupported file'))return {title:'Unsupported file',message:'This file type is not supported by DataKite.',fix:'Use CSV, Excel, JSON, PDF, Word (.docx), or PowerPoint (.pptx).'};if(low.includes('too large'))return {title:'File is too large',message:'The selected file exceeds the upload limit.',fix:'Reduce the file size or upload fewer files.'};if(low.includes('empty'))return {title:'Empty file',message:'The selected file contains no readable data.',fix:'Choose a file that contains data and try again.'};if(low.includes('read')||low.includes('parse'))return {title:'File could not be read',message:'DataKite could not read the selected file.',fix:'Try another copy of the file or save it again as CSV/XLSX.'};if(low.includes('upload'))return {title:'Upload could not be completed',message:'DataKite could not finish reading the selected file.',fix:'Try the upload again. If it repeats, use the file details shown by DataKite.'};return {title:'Something went wrong',message:'DataKite could not complete '+action+'.',fix:'Try again. If the issue repeats, open Help for guidance.'}}
function showError(err,action='this action',retry=null){const f=friendlyError(err,action);setText('errorTitle',f.title);setText('errorMessage',f.message);setText('errorFix',f.fix);retryAction=retry;const retryBtn=$('#errorRetry');if(retryBtn)retryBtn.style.display=retry?'':'none';const box=$('#appError');if(box)box.hidden=false;clearTimeout(errorTimer);errorTimer=setTimeout(hideError,12000)}
function hideError(){const el=$('#appError');if(el)el.hidden=true;retryAction=null;clearTimeout(errorTimer)}
$('#errorClose')?.addEventListener('click',hideError);$('#errorRetry')?.addEventListener('click',async()=>{const fn=retryAction;hideError();if(fn){try{await fn()}catch(e){showError(e,'that action',fn)}}});
async function uploadFiles(){
  const fd=new FormData();state.files.forEach(f=>fd.append('files',f));const p=$('#uploadProgress');if(p)p.hidden=false;if(p?.firstElementChild)p.firstElementChild.style.width='15%';setDisabled('browseBtn',true);const browse=$('#browseBtn');if(browse)browse.textContent='Analyzing…';hideError();toast('Reading your data…');
  try{const r=await fetch('/upload',{method:'POST',body:fd});if(p?.firstElementChild)p.firstElementChild.style.width='72%';if(browse)browse.textContent='Preparing dashboard…';let j={};try{j=await r.json()}catch{}if(!r.ok)throw new Error(j.error||j.message||'Upload failed');state.dataset=null;state.datasetId=j.dataset_id||null;state.dashboard=j.dashboard||null;hasData=!!state.datasetId;Object.values(charts).forEach(c=>{try{c.destroy()}catch{}});charts={};if(p?.firstElementChild)p.firstElementChild.style.width='100%';setText('sideStatus',`${j.file_count||state.files.length} file${(j.file_count||state.files.length)>1?'s':''} loaded`);setText('chatDataStatus',`${j.rows||0} rows · ${j.columns||0} columns`);setText('datasetName',j.file_count>1?`${j.file_count} files analyzed`:(j.filename||state.files[0]?.name||'Dataset'));setText('datasetRows',fmt(j.rows)+' rows');setText('datasetCols',fmt(j.columns)+' columns');
    if(j.details?.length){showError(new Error('Some files were not fully included: '+j.details.join(' ')),'the complete upload',()=>uploadFiles());toast('Analysis ready with a file notice')}else toast('Analysis context ready');
    setTimeout(()=>{if(p)p.hidden=true;setDisabled('browseBtn',false);if(browse)browse.textContent='Choose files';showView('dashboard')},350)
  }catch(e){if(p)p.hidden=true;setDisabled('browseBtn',false);if(browse)browse.textContent='Choose files';showError(e,'your upload',()=>uploadFiles())}
}
function kpiCards(k){const entries=Object.entries(k||{});const preferred=[['total_sales','Total Sales','◈'],['total_profit','Total Profit','↗'],['total_orders','Orders','▣'],['customers','Customers','♙'],['average_order_value','Average Order Value','◫'],['quantity','Quantity','⌁'],['profit_margin','Profit Margin','%']];let out=[];for(const [key,label,icon] of preferred){if(k[key]!==undefined)out.push({key,label,icon,value:key.includes('margin')?(Number(k[key]).toFixed(1)+'%'):(key.includes('sales')||key.includes('profit')||key.includes('order_value')?money(k[key]):fmt(k[key]))})}if(!out.length)for(const [key,val] of entries.slice(0,6))out.push({key,label:key.replaceAll('_',' '),icon:'•',value:fmt(val)});return out.map(x=>`<div class="kpi"><div class="kpi-icon">${x.icon}</div><label>${x.label}</label><strong>${x.value}</strong></div>`).join('')}
async function getJSON(url){const r=await fetch(url);let j={};try{j=await r.json()}catch{}if(!r.ok)throw new Error(j.error||j.message||`Request failed (${r.status})`);return j}
async function loadDashboard(){
  if(!hasData||!state.datasetId||dashboardLoading)return;
  if(state.dashboard){
    const j=state.dashboard;
    $('#kpiGrid').innerHTML=kpiCards(j.kpis);
    renderChartData('salesChart',j.charts?.sales,'Sales over time','line','salesEmpty','trendField');
    renderChartData('categoryChart',j.charts?.category,'Sales by category','bar','categoryEmpty');
    renderChartData('cityChart',j.charts?.city,'Sales by region / city','bar','cityEmpty');
    renderChartData('productChart',j.charts?.product,'Top products','bar','productEmpty');
    renderChartData('statusChart',j.charts?.status,'Order / record status','doughnut','statusEmpty');
    renderHealth(j.health);
    return;
  }
  dashboardLoading=true;hideError();
  try{const r=await fetch('/analytics/bootstrap',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({dataset_id:state.datasetId})});let j={};try{j=await r.json()}catch{}if(r.status===409&&j.error_code==='DATASET_EXPIRED'){dashboardLoading=false;await uploadFiles();return loadDashboard()}if(!r.ok)throw new Error(j.error||'Dashboard analysis failed');state.dashboard=j;$('#kpiGrid').innerHTML=kpiCards(j.kpis);renderChartData('salesChart',j.charts?.sales,'Sales over time','line','salesEmpty','trendField');renderChartData('categoryChart',j.charts?.category,'Sales by category','bar','categoryEmpty');renderChartData('cityChart',j.charts?.city,'Sales by region / city','bar','cityEmpty');renderChartData('productChart',j.charts?.product,'Top products','bar','productEmpty');renderChartData('statusChart',j.charts?.status,'Order / record status','doughnut','statusEmpty');renderHealth(j.health)}catch(e){showError(e,'the dashboard',()=>loadDashboard())}finally{dashboardLoading=false}}

function renderChartData(id,d,title,type,emptyId,noteId){const canvas=$('#'+id),empty=$('#'+emptyId);if(!d?.labels?.length){if(canvas)canvas.style.display='none';if(empty)empty.classList.remove('hidden');return}canvas.style.display='block';empty.classList.add('hidden');if(noteId)setText(noteId,d.field||d.date_field||'Auto detected');if(charts[id])charts[id].destroy();const isLine=type==='line';charts[id]=new Chart(canvas,{type,data:{labels:d.labels,datasets:[{data:d.values,borderWidth:2,pointRadius:isLine?2:0,tension:.35,borderColor:'#ff8a3d',backgroundColor:type==='doughnut'?['#ff8a3d','#ffb15c','#f2c078','#b8c0d0','#70788a','#4f5665']:type==='bar'?'rgba(255,138,61,.7)':'rgba(255,138,61,.14)',fill:isLine,borderRadius:type==='bar'?6:0}]},options:{...chartBase,scales:type==='doughnut'?{}:chartBase.scales}})}
function renderHealth(h){const box=$('#healthScore');if(!box||!h)return;box.innerHTML='<div class="health-head"><div><span class="eyebrow">BUSINESS HEALTH</span><strong>'+escape(h.score+'/100')+'</strong><span class="health-label">● '+escape(h.label||'Ready')+'</span></div><p>'+escape(h.summary||'')+'</p></div><div class="health-grid">'+(h.components||[]).map(x=>'<article class="health-item"><div><b>'+escape(x.name)+'</b><strong>'+escape(String(x.score))+'</strong></div><div class="health-bar"><i style="width:'+Math.max(0,Math.min(100,Number(x.score)||0))+'%"></i></div><small>'+escape(x.reason||'')+'</small></article>').join('')+'</div>'}
async function renderChart(id,url,title,type,emptyId,noteId){const canvas=$('#'+id),empty=$('#'+emptyId);try{const d=await getJSON(url);if(!d.labels||!d.labels.length){canvas.style.display='none';empty.classList.remove('hidden');return}canvas.style.display='block';empty.classList.add('hidden');if(noteId)$('#'+noteId).textContent=d.field||d.date_field||'Auto detected';if(charts[id])charts[id].destroy();const isLine=type==='line';charts[id]=new Chart(canvas,{type,data:{labels:d.labels,datasets:[{data:d.values,borderWidth:2,pointRadius:isLine?2:0,tension:.35,borderColor:'#ff8a3d',backgroundColor:type==='doughnut'?['#ff8a3d','#ffb15c','#f2c078','#b8c0d0','#70788a','#4f5665']:type==='bar'?'rgba(255,138,61,.7)':'rgba(255,138,61,.14)',fill:isLine,borderRadius:type==='bar'?6:0}]},options:{...chartBase,scales:type==='doughnut'?{}:chartBase.scales}})}catch(e){canvas.style.display='none';empty.classList.remove('hidden')}}
function addMsg(text,user=false){const m=document.createElement('div');m.className='msg '+(user?'user':'');m.innerHTML=user?`<div class="bubble">${escape(text)}</div>`:`<div class="ai-mark">✦</div><div class="bubble">${format(text)}</div>`;$('#messages').appendChild(m);$('#messages').scrollTop=$('#messages').scrollHeight;return m}
function renderAnalystResult(j){
  const m=addMsg(j.answer||'No answer received.');
  const bubble=m.querySelector('.bubble'); const extra=document.createElement('div'); extra.className='analyst-extra';
  if(Array.isArray(j.evidence)&&j.evidence.length){
    const card=document.createElement('div');card.className='analyst-card';card.innerHTML='<span class="eyebrow">EVIDENCE</span><div class="evidence-grid"></div>';
    const grid=card.querySelector('.evidence-grid'); j.evidence.slice(0,8).forEach((e,i)=>{const item=document.createElement('div');item.className='evidence-item';const entries=Object.entries(e||{});const label=entries.find(([k])=>k==='metric'||k==='label'||k==='period')?.[1]??`Item ${i+1}`;const value=entries.find(([k])=>k==='value'||k==='actual'||k==='forecast'||k==='growth_pct')?.[1]??'';item.innerHTML=`<b>${escape(label)}</b><span>${escape(value)}</span>`;grid.appendChild(item)});extra.appendChild(card)
  }
  if(j.chart&&Array.isArray(j.chart.labels)&&j.chart.labels.length){
    const card=document.createElement('div');card.className='analyst-card';card.innerHTML='<span class="eyebrow">SMART CHART</span><div style="font-weight:700;margin-bottom:6px">'+escape(j.chart.title||'Analysis chart')+'</div><canvas class="analyst-chart"></canvas>';extra.appendChild(card);
    requestAnimationFrame(()=>{const c=card.querySelector('canvas');new Chart(c,{type:j.chart.type==='bar'?'bar':'line',data:{labels:j.chart.labels,datasets:[{data:j.chart.values,borderWidth:2,borderColor:'#ff8a3d',backgroundColor:j.chart.type==='bar'?'rgba(255,138,61,.65)':'rgba(255,138,61,.12)',fill:j.chart.type!=='bar',tension:.3}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}},scales:{x:{ticks:{color:'#9da4b4'},grid:{color:'rgba(255,255,255,.05)'}},y:{ticks:{color:'#9da4b4'},grid:{color:'rgba(255,255,255,.05)'}}}}})})
  }
  if(Array.isArray(j.recommendations)&&j.recommendations.length){const card=document.createElement('div');card.className='analyst-card';card.innerHTML='<span class="eyebrow">RECOMMENDED ACTIONS</span>'+j.recommendations.map(x=>`<div style="margin:6px 0">• ${escape(x)}</div>`).join('');extra.appendChild(card)}
  if(Array.isArray(j.followups)&&j.followups.length){const card=document.createElement('div');card.className='analyst-card';card.innerHTML='<span class="eyebrow">ASK NEXT</span><div class="followups"></div>';const box=card.querySelector('.followups');j.followups.forEach(q=>{const b=document.createElement('button');b.className='followup-btn';b.textContent=q;b.onclick=()=>ask(q);box.appendChild(b)});extra.appendChild(card)}
  if(j.validation){const v=document.createElement('div');v.className='validation-ok';v.textContent=j.validation.passed?'✓ Calculation verified before answering':'';extra.appendChild(v)}
  bubble.appendChild(extra);$('#messages').scrollTop=$('#messages').scrollHeight
}
function escape(s){return String(s).replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]))}function format(s){return escape(s).replace(/\n/g,'<br>')}
async function ask(q){q=q.trim();if(!q)return;addMsg(q,true);$('#question').value='';const id='typing-'+Date.now();const t=document.createElement('div');t.id=id;t.className='msg';t.innerHTML='<div class="ai-mark">✦</div><div class="bubble">Analyzing your data…</div>';$('#messages').appendChild(t);$('#messages').scrollTop=$('#messages').scrollHeight;hideError();const run=()=>ask(q);try{const r=await fetch('/ask',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question:q,dataset_id:state.datasetId})});let j={};try{j=await r.json()}catch{}if(r.status===409&&j.error_code==='DATASET_EXPIRED'){await uploadFiles();document.getElementById(id)?.remove();return ask(q)}if(!r.ok)throw new Error(j.error||j.message||`AI request failed (${r.status})`);document.getElementById(id)?.remove();if(j.calculation||j.evidence||j.chart||j.followups||j.recommendations)renderAnalystResult(j);else addMsg(j.answer||j.message||'No answer received.')}catch(e){document.getElementById(id)?.remove();addMsg('I could not complete that analysis yet. Use the Help panel for the next step.');showError(e,'your AI question',run)}}
$('#sendBtn').addEventListener('click',()=>ask($('#question').value));$('#question').addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();ask($('#question').value)}});$$('[data-q]').forEach(b=>b.addEventListener('click',()=>ask(b.dataset.q)));
const exportMap={excel:'/excel/download',pdf:'/pdf/download',word:'/word/download',ppt:'/ppt/download',data:'/data/download',json:'/json/download'};
$$('[data-export]').forEach(b=>b.addEventListener('click',async()=>{
if(!hasData){toast('Upload data first');showView('overview');return}
if(exportLoading){toast('An export is already running…');return}
const type=b.dataset.export;const run=()=>b.click();exportLoading=true;$$('[data-export]').forEach(x=>x.disabled=true);b.classList.add('loading');toast('Preparing '+type.toUpperCase()+'…');hideError();
try{const r=await fetch(exportMap[type],{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({dataset_id:state.datasetId})});if(r.status===409){let j={};try{j=await r.json()}catch{}if(j.error_code==='DATASET_EXPIRED'){await uploadFiles();exportLoading=false;return b.click()}}if(!r.ok){
  let j={};try{j=await r.json()}catch{}
  if(type==='json'&&r.status>=500&&state.files.length){
    await uploadFiles();
    const retry=await fetch(exportMap[type],{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({dataset_id:state.datasetId})});
    if(retry.ok){
      const retryType=(retry.headers.get('content-type')||'').toLowerCase();
      if(!retryType.includes('application/json')){
        const retryBlob=await retry.blob();
        if(retryBlob.size){
          const retryUrl=URL.createObjectURL(retryBlob);
          const a=document.createElement('a');
          a.href=retryUrl;a.download='analyzed_business_data.json';a.style.display='none';
          document.body.appendChild(a);a.click();a.remove();
          setTimeout(()=>URL.revokeObjectURL(retryUrl),3000);
          toast('Download ready');return;
        }
      }
    }
    throw new Error('JSON export failed after retry. Please upload the data again.');
  }
  throw new Error(j.error||j.message||'Export failed')
}// JSON is the exported file itself, not a JSON API response.
// Handle it before the generic application/json response branch.
if(type==='json'){
  const blob=await r.blob();
  if(!blob.size) throw new Error('JSON export returned an empty file');
  const url=URL.createObjectURL(blob);
  const a=document.createElement('a');
  a.href=url;a.download='analyzed_business_data.json';a.style.display='none';
  document.body.appendChild(a);a.click();a.remove();
  setTimeout(()=>URL.revokeObjectURL(url),3000);
  toast('Download ready');
  return;
}
const contentType=(r.headers.get('content-type')||'').toLowerCase();
if(contentType.includes('application/json')){
  const j=await r.json();
  if(j.download_url){ window.location.href=j.download_url; toast('Download ready'); return; }
  throw new Error(j.error||j.message||'Export did not return a downloadable file');
}
const blob=await r.blob();
if(!blob.size) throw new Error('Export returned an empty file');
const url=URL.createObjectURL(blob);
const a=document.createElement('a');
a.href=url;
a.download={excel:'AI_Business_Analytics.xlsx',pdf:'AI_Business_Analytics.pdf',word:'AI_Business_Analytics.docx',ppt:'AI_Business_Analytics.pptx',data:'analyzed_business_data.csv',json:'analyzed_business_data.json'}[type];
a.style.display='none';
document.body.appendChild(a);
a.click();
a.remove();
setTimeout(()=>URL.revokeObjectURL(url),3000);
toast('Download ready')}
catch(e){showError(e,'the '+type.toUpperCase()+' export',run)}
finally{exportLoading=false;$$('[data-export]').forEach(x=>x.disabled=false);b.classList.remove('loading')}
}));
// Help system: simple, contextual and non-technical for end users.
const helpContent={
 upload:['UPLOAD FILES','Choose one or up to 10 files. Supported: Excel, CSV, JSON, PDF, Word and PowerPoint. For best results, use a table with clear column headers and data rows.','If an upload fails, DataKite shows a simple reason and a Try again action — not a Python or server error.'],
 questions:['ASK THE AI','Ask in normal business language: “What are my total sales?”, “Which product performs best?”, “Why did sales fall?” or “Give me recommendations.”','The AI uses your current analysis context and can fall back to the built-in analytics engine when the model is temporarily unavailable.'],
 dashboard:['READ THE DASHBOARD','Start with KPIs, then use the trend, category, geography, product and status charts to understand performance.','If a chart cannot be generated, DataKite keeps the rest of the workspace usable and tells you what to try.'],
 export:['EXPORT RESULTS','Open Export Center after uploading data. Choose Excel, PDF, Word, PowerPoint, analyzed CSV or JSON.','If an export fails, use Try again. Make sure a dataset is loaded before exporting.'],
 errors:['FIX AN ERROR','Every user-facing error follows Problem → Simple explanation → Fix → Try again. Technical details are kept away from the user interface.','If the same issue repeats, open Help and follow the relevant topic.'],
 install:['INSTALL DATAKITE','On supported Chrome installations, use the Install app button or Chrome’s menu → Install DataKite AI. On a phone, use the browser’s Add to Home Screen / Install option when offered.','Once installed, DataKite opens like an app while the live website remains available in the browser.']
};
function openHelp(topic){const modal=$('#helpModal');modal.classList.add('open');modal.setAttribute('aria-hidden','false');if(topic&&helpContent[topic]){const [eyebrow,title,body]=helpContent[topic];$('#helpAnswer').innerHTML=`<span class="eyebrow">${eyebrow}</span><h3>${title}</h3><p>${body}</p>`}else{$('#helpAnswer').innerHTML='<span class="eyebrow">QUICK START</span><h3>Upload → Understand → Analyze → Ask</h3><p>Start with one clean business file. DataKite will detect the useful fields automatically. If something goes wrong, use <b>Try again</b> or come back here for the next step.</p>'}}
function closeHelp(){const modal=$('#helpModal');modal.classList.remove('open');modal.setAttribute('aria-hidden','true')}
$('#helpBtn')?.addEventListener('click',()=>openHelp());$('#helpStartBtn')?.addEventListener('click',()=>openHelp());$('#helpCloseBtn')?.addEventListener('click',closeHelp);$$('[data-close-help]').forEach(x=>x.addEventListener('click',closeHelp));$$('[data-help-topic]').forEach(b=>b.addEventListener('click',()=>openHelp(b.dataset.helpTopic)));document.addEventListener('keydown',e=>{if(e.key==='Escape')closeHelp();if(e.key==='?'&&!['INPUT','TEXTAREA'].includes(document.activeElement?.tagName))openHelp()});
window.addEventListener('beforeinstallprompt',e=>{e.preventDefault();deferredInstall=e;$('#installBtn').hidden=false});$('#installBtn').addEventListener('click',async()=>{if(!deferredInstall){openHelp('install');return}deferredInstall.prompt();deferredInstall=null;$('#installBtn').hidden=true});
if('serviceWorker' in navigator)window.addEventListener('load',()=>navigator.serviceWorker.register('sw.js').catch(()=>{}));
