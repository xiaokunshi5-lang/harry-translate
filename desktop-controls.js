/* Desktop-only lifecycle controls. No cloud secret is exposed to the page. */
(() => {
  const bar = document.createElement('div');
  bar.style.cssText = 'position:fixed;bottom:12px;right:18px;z-index:9998;display:flex;gap:10px;align-items:center;padding:8px 12px;background:#101b2bea;border:1px solid #33465c;border-radius:10px;font:13px Microsoft YaHei,sans-serif;color:#b5cce3';
  const status = document.createElement('span');
  const pause = document.createElement('button'); pause.textContent = '暂停翻译';
  const setup = document.createElement('a'); setup.href = '/desktop/setup';setup.textContent = '账户与麦克风';setup.style.color='#61cdf3';
  bar.append(status,pause,setup);document.body.append(bar);
  pause.onclick=async()=>{pause.disabled=true;try{const r=await fetch('/api/desktop/stop',{method:'POST'});if(!r.ok)throw Error('暂停失败，请关闭应用停止采集。');status.textContent='已暂停 · 不采集声音';}catch(e){status.textContent=e.message}finally{pause.disabled=false}};
  setup.onclick=async event=>{event.preventDefault();const r=await fetch('/api/desktop/stop',{method:'POST'});if(r.ok)location.href=setup.href;else status.textContent='暂停失败，请重试或关闭应用。'};
  // The desktop settings entry uses the validated account/device workflow.
  // The legacy drawer remains available to the source-development launcher.
  window.openConfigDrawer=()=>setup.click();
  fetch('/api/desktop/status').then(r=>r.json()).then(s=>{status.textContent=s.running?'翻译中 · 声音发送至阿里云':'已暂停 · 不采集声音';pause.disabled=!s.running}).catch(()=>{status.textContent='连接状态未知'});
})();
