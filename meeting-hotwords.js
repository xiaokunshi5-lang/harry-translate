/* Meeting catalog editor. Text is always assigned as text/value, never HTML. */
const hw = {direction:'en', dirty:false, busy:false, data:null, revision:0, poll:0};
const hwDialog = document.getElementById('hotwords-dialog');
const hwEl = id => document.getElementById(id);
const hwId = () => crypto.randomUUID();
function hwStatus(message) { hwEl('hotwords-status').textContent=message; }
function hwBusy(value) {hw.busy=value;hwEl('hotwords-fields').disabled=value;hwEl('hotwords-save').disabled=value;}
function hwChanged() {hw.dirty=true;clearTimeout(hw.poll);hwStatus('有未保存的修改。分类、启停和词条都将在保存后生效。');}
function hwButton(text, fn) {const b=document.createElement('button');b.type='button';b.textContent=text;b.onclick=fn;return b;}
function hwInput(value, label, fn) {const input=document.createElement('input');input.className='drawer-input';input.value=value;input.setAttribute('aria-label',label);input.placeholder=label;input.oninput=()=>{fn(input.value);hwChanged()};return input;}
function hwCheck(value, label, fn) {const wrap=document.createElement('label');wrap.style.cssText='display:flex;align-items:center;gap:5px;white-space:nowrap';const input=document.createElement('input');input.type='checkbox';input.checked=value;input.setAttribute('aria-label',label);input.onchange=()=>{fn(input.checked);hwChanged()};wrap.append(input,document.createTextNode(label));return wrap;}
function hwNormalize(data) {
  const copy=structuredClone(data);
  copy.categories??=[['uncategorized','未分类'],['people','人物姓名'],['organizations','公司机构'],['products','产品项目'],['technical','专业术语']].map(([id,name])=>({id,name,enabled:true}));
  if(!Array.isArray(copy.categories))throw Error('分类必须是列表');
  if(!copy.categories.some(c=>c.id==='uncategorized'))copy.categories.unshift({id:'uncategorized',name:'未分类',enabled:true});
  if(!copy.entries)copy.entries=['en','zh'].flatMap(direction=>Object.entries(copy[direction==='en'?'terms_zh_to_en':'terms_en_to_zh']||{}).map(([source,target])=>({id:hwId(),source,target,direction,category_id:'uncategorized',enabled:true,notes:''})));
  if(!Array.isArray(copy.entries))throw Error('词条必须是列表');
  return copy;
}
function hwVisible(){const category=hwEl('hotwords-category').value;const query=hwEl('hotwords-search').value.trim().toLowerCase();return (hw.data?.entries||[]).filter(e=>e.direction===hw.direction&&(!category||e.category_id===category)&&(!query||[e.source,e.target,e.notes||''].some(v=>String(v).toLowerCase().includes(query))));}
function hwCategoryOptions(select, value, includeAll=false) {select.replaceChildren();if(includeAll)select.add(new Option('全部分类',''));for(const c of hw.data.categories)select.add(new Option(c.name+(c.enabled?'':'（已停用）'),c.id));select.value=value;}
function renderMeetingHotwords(){if(!hw.data)return;const filter=hwEl('hotwords-category');hwCategoryOptions(filter,filter.value,true);hwEl('hotwords-direction').value=hw.direction;hwEl('hotwords-source-label').textContent=hw.direction==='en'?'中文原词':'英文原词';hwEl('hotwords-target-label').textContent=hw.direction==='en'?'指定英文译法':'指定中文译法';
  const list=hwEl('hotwords-list');list.replaceChildren();
  for(const entry of hwVisible()){
    const item=document.createElement('div');item.className='hw-item';item.dataset.id=entry.id;item.style.cssText='padding:10px 0;border-bottom:1px solid #263244';
    const row=document.createElement('div');row.className='hw-row';
    row.append(hwInput(entry.source,'原词',v=>entry.source=v),hwInput(entry.target,'指定译法',v=>entry.target=v),hwButton('删除',()=>{hw.data.entries=hw.data.entries.filter(e=>e.id!==entry.id);hwChanged();renderMeetingHotwords()}));
    const detail=document.createElement('div');detail.style.cssText='display:flex;gap:10px;align-items:center;flex-wrap:wrap';
    const category=document.createElement('select');category.className='drawer-select';category.style.cssText='width:155px;padding:6px';category.setAttribute('aria-label','词条分类');hwCategoryOptions(category,entry.category_id);category.onchange=()=>{entry.category_id=category.value;hwChanged()};
    const notes=hwInput(entry.notes||'','备注（可选）',v=>entry.notes=v);notes.style.cssText='flex:1;min-width:120px;padding:6px';
    detail.append(category,hwCheck(entry.enabled!==false,'启用词条',v=>entry.enabled=v),notes);item.append(row,detail);list.append(item);
  }
  const count=hwVisible().length;const enabled=hw.data.entries.filter(e=>e.direction===hw.direction&&e.enabled!==false&&hw.data.categories.some(c=>c.id===e.category_id&&c.enabled)).length;
  hwEl('hotwords-count').textContent=`当前筛选 ${count} 条 · 本方向启用 ${enabled} 条 · 全词库 ${hw.data.entries.length} 条。停用词条仍保留，但不会发送到云端。`;
}
function addMeetingHotword(){if(!hw.data)return;hwEl('hotwords-search').value='';const entry={id:hwId(),source:'',target:'',direction:hw.direction,category_id:hwEl('hotwords-category').value||'uncategorized',enabled:true,notes:''};hw.data.entries.push(entry);hwChanged();renderMeetingHotwords();hwEl('hotwords-list').lastElementChild?.querySelector('input')?.focus();}
async function openMeetingHotwords(){if(hwDialog.open)return;if(typeof closeConfigDrawer==='function')closeConfigDrawer();hwDialog.showModal();await loadMeetingHotwords();}
function closeMeetingHotwords(){if(hw.busy)return;if(hw.dirty&&!confirm('尚有未保存的热词修改，确定放弃并关闭吗？'))return;clearTimeout(hw.poll);hwDialog.close();hw.dirty=false;}
hwDialog.addEventListener('cancel',e=>{e.preventDefault();closeMeetingHotwords()});
function changeHotwordsDirection(){hw.direction=hwEl('hotwords-direction').value;renderMeetingHotwords();}
async function loadMeetingHotwords(){hwBusy(true);clearTimeout(hw.poll);hwStatus('正在加载词库…');let loaded=false;try{const r=await fetch('/api/glossary',{cache:'no-store'});if(!r.ok)throw Error('无法读取词库，请关闭后重试。');const result=await r.json();hw.data=hwNormalize(result.data);hw.revision=result.data._revision;hw.dirty=false;hwEl('hotwords-categories').hidden=true;renderMeetingHotwords();loaded=true;hwStatus('已加载。可按分类和方向管理；修改后请保存。')}catch(e){hwStatus(e.message)}finally{hwBusy(false);if(!loaded){hwEl('hotwords-fields').disabled=true;hwEl('hotwords-save').disabled=true}}}
function editHotwordCategories(){const box=hwEl('hotwords-categories');box.hidden=!box.hidden;if(!box.hidden)renderHotwordCategories();}
function renderHotwordCategories(){const box=hwEl('hotwords-categories');box.replaceChildren();box.style.cssText='padding:12px;background:#0b1320;border:1px solid #334155;border-radius:8px';
  const note=document.createElement('p');note.className='drawer-note';note.textContent='分类跨翻译方向共用。停用分类会暂停其中全部术语；删除分类只把词条移到“未分类”。';box.append(note);
  for(const category of hw.data.categories){const row=document.createElement('div');row.className='hw-toolbar';const name=hwInput(category.name,'分类名称',v=>category.name=v);name.disabled=category.id==='uncategorized';row.append(name,hwCheck(category.enabled,'启用分类',v=>{category.enabled=v;renderMeetingHotwords()}));
    if(category.id!=='uncategorized')row.append(hwButton('删除分类',()=>{if(!confirm('删除此分类？其中词条会保留并移到“未分类”。'))return;hw.data.categories=hw.data.categories.filter(c=>c.id!==category.id);for(const e of hw.data.entries)if(e.category_id===category.id)e.category_id='uncategorized';hwChanged();renderMeetingHotwords();renderHotwordCategories()}));box.append(row);}
  const create=document.createElement('div');create.className='hw-toolbar';const name=document.createElement('input');name.className='drawer-input';name.placeholder='例如：本次产品发布会';name.setAttribute('aria-label','新分类名称');create.append(name,hwButton('新增分类',()=>{const value=name.value.trim();if(!value||hw.data.categories.some(c=>c.name.trim()===value)){hwStatus('分类名称不能为空或重复。');return}hw.data.categories.push({id:hwId(),name:value,enabled:true});hwChanged();renderMeetingHotwords();renderHotwordCategories()}));box.append(create);
}
function enableVisibleHotwords(enabled){for(const e of hwVisible())e.enabled=enabled;hwChanged();renderMeetingHotwords();}
function hwValidate(data){const sources=new Set(),ids=new Set(),names=new Set();if(data.entries.length>5000||data.categories.length>100)throw Error('最多支持 5000 条词条和 100 个分类。');for(const c of data.categories){if(!c.name?.trim()||names.has(c.name.trim()))throw Error('分类名称不能为空或重复。');names.add(c.name.trim())}for(const e of data.entries){if(typeof e.source!=='string'||typeof e.target!=='string'||!e.source.trim()||!e.target.trim())throw Error('每条热词都需要原词和指定译法，请补全或删除空行。');const key=e.direction+'\0'+e.source.trim();if(sources.has(key)||ids.has(e.id))throw Error('同一方向的原词重复或词条 ID 冲突，请合并为唯一译法。');if(!['en','zh'].includes(e.direction))throw Error('导入词条的方向无效。');sources.add(key);ids.add(e.id)}}
async function saveMeetingHotwords(){if(hw.busy||!hw.data)return;try{hwValidate(hw.data)}catch(e){hwStatus(e.message);return}hwBusy(true);clearTimeout(hw.poll);hwStatus('正在保存词库…');try{const payload={categories:hw.data.categories,entries:hw.data.entries,_expected_revision:hw.revision};if(hw.importedAsr)payload.asr_fixes=hw.data.asr_fixes;
  const r=await fetch('/api/glossary',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});const result=await r.json();if(!r.ok||result.status!=='ok')throw Error(result.message||'保存失败，请重试。');
  hw.dirty=false;hw.importedAsr=false;hw.revision=result.revision??(hw.revision+1);hwStatus('词库已保存；正在等待云端确认。暂停状态下将在开始翻译后应用。');hw.poll=setTimeout(()=>checkHotwordsCloud(0),500);
}catch(e){hwStatus(e.message)}finally{hwBusy(false)}}
async function checkHotwordsCloud(attempt){if(!hwDialog.open||hw.dirty||hw.busy)return;try{const r=await fetch('/api/meta',{cache:'no-store'});if(!r.ok)throw Error();const meta=await r.json();if(!hwDialog.open||hw.dirty||hw.busy)return;const states=['en','zh'].map(d=>(meta.cloud_status||{})[d]||{});if(states.every(s=>s.ready&&s.corpus_status==='confirmed')){hwStatus(`已保存，云端已确认：中译英 ${states[0].cloud_phrases_count} 条，英译中 ${states[1].cloud_phrases_count} 条。`);return}const error=states.find(s=>s.error||s.corpus_status==='unsupported');if(error){hwStatus('词库已保存，但云端尚未应用：'+(error.error||'当前模型不支持云端词库'));return}}catch(e){/* bounded retry; never invent cloud confirmation */}if(attempt<14)hw.poll=setTimeout(()=>checkHotwordsCloud(attempt+1),1000);else hwStatus('词库已保存，尚未收到云端确认。暂停时请先开始翻译；运行中请检查网络和模型状态。');}
function exportMeetingHotwords(){if(!hw.data)return;try{hwValidate(hw.data);const data={_version:'2.0',categories:hw.data.categories,entries:hw.data.entries,asr_fixes:hw.data.asr_fixes||{}};const blob=new Blob([JSON.stringify(data,null,2)],{type:'application/json'});const url=URL.createObjectURL(blob);const link=document.createElement('a');link.href=url;link.download='meeting-hotwords.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);hwStatus('已导出当前编辑内容。导出不代表已经保存或应用到云端。')}catch(e){hwStatus(e.message)}}
async function importMeetingHotwords(input){const file=input.files[0];input.value='';if(!file)return;try{if(file.size>4*1024*1024)throw Error('词库文件不能超过 4 MB。');const raw=JSON.parse(await file.text());if(!raw||typeof raw!=='object'||(!raw.entries&&!raw.terms_zh_to_en&&!raw.terms_en_to_zh))throw Error('请选择软件导出的 JSON 词库或旧版 glossary.json。');const incoming=hwNormalize(raw);hwValidate(incoming);const replace=hwEl('hotwords-import-mode').value==='replace';if(replace&&!confirm('替换整个词库？当前分类和词条将被替换，保存后才生效。建议先导出备份。'))return;
  if(replace){hw.data.entries=incoming.entries;hw.data.categories=incoming.categories;if(raw.asr_fixes){hw.data.asr_fixes=raw.asr_fixes;hw.importedAsr=true}}
  else{const candidate=structuredClone(hw.data);const ids=new Map();for(const c of incoming.categories){let target=candidate.categories.find(x=>x.name===c.name);if(!target){target={...c,id:hwId()};candidate.categories.push(target)}ids.set(c.id,target.id)}for(const e of incoming.entries)candidate.entries.push({...e,id:hwId(),category_id:ids.get(e.category_id)||'uncategorized'});hwValidate(candidate);hw.data=candidate;}
  hwChanged();hwEl('hotwords-category').value='';hwEl('hotwords-search').value='';renderMeetingHotwords();hwEl('hotwords-categories').hidden=true;hwStatus('导入已加入编辑区，尚未写入文件。请检查后点击保存；关闭可放弃。');
}catch(e){hwStatus('导入未完成：'+e.message)}}
