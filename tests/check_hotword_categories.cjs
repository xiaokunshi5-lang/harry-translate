const {chromium}=require('playwright');
const fs=require('fs');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1360,height:1000}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
  let data={_revision:1,asr_fixes:{'错音':'正确'},categories:[{id:'uncategorized',name:'未分类',enabled:true},{id:'people',name:'人物姓名',enabled:true}],entries:[{id:'a',source:'张三',target:'Zhang San',direction:'en',category_id:'people',enabled:true,notes:'主持人'},{id:'b',source:'Project',target:'项目',direction:'zh',category_id:'uncategorized',enabled:true,notes:''}]};
  let fail=false;let posts=0;
  await page.route('http://127.0.0.1:8123/**',async route=>{
   const path=new URL(route.request().url()).pathname;
   if(path==='/')return route.fulfill({contentType:'text/html',body:fs.readFileSync('index.html','utf8')});
   if(path==='/assets/meeting-hotwords.js')return route.fulfill({contentType:'text/javascript',body:fs.readFileSync('meeting-hotwords.js','utf8')});
   if(path==='/api/glossary'){
    if(route.request().method()==='POST'){posts++;if(fail)return route.fulfill({status:500,json:{message:'测试：磁盘已满'}});const body=route.request().postDataJSON();assert.equal(body._expected_revision,data._revision);data={...data,...body,_revision:data._revision+1};return route.fulfill({json:{status:'ok',revision:data._revision}})}
    return route.fulfill({json:{status:'ok',data}});
   }
   if(path==='/api/meta')return route.fulfill({json:{status:'ok',cloud_status:{en:{ready:true,corpus_status:'confirmed',cloud_phrases_count:1},zh:{ready:true,corpus_status:'confirmed',cloud_phrases_count:1}}}});
   return route.fulfill({json:{status:'ok'}});
  });
  await page.goto('http://127.0.0.1:8123/');await page.getByRole('button',{name:'会议热词',exact:true}).click();
  await page.waitForFunction(()=>!document.getElementById('hotwords-fields').disabled);
  assert.equal(await page.locator('#hotwords-list .hw-item').count(),1);
  await page.getByRole('button',{name:'管理分类',exact:true}).click();
  await page.getByRole('textbox',{name:'新分类名称'}).fill('本次会议');await page.getByRole('button',{name:'新增分类',exact:true}).click();
  await page.locator('#hotwords-category').selectOption({label:'本次会议'});assert.equal(await page.locator('#hotwords-list .hw-item').count(),0);
  await page.locator('#hotwords-add').click();await page.locator('#hotwords-save').click();assert.match(await page.locator('#hotwords-status').innerText(),/补全/);
  await page.getByRole('textbox',{name:'原词',exact:true}).fill('会议代号');await page.getByRole('textbox',{name:'指定译法',exact:true}).fill('Meeting Code');
  await page.getByRole('checkbox',{name:'启用词条',exact:true}).uncheck();
  await page.locator('#hotwords-direction').selectOption('zh');await page.locator('#hotwords-category').selectOption('');
  assert.equal(await page.locator('#hotwords-list .hw-item').count(),1);
  await page.locator('#hotwords-save').click();await page.waitForFunction(()=>document.getElementById('hotwords-status').textContent.includes('云端已确认'));
  assert.equal(data.entries.length,3);assert.equal(data.entries.find(e=>e.source==='会议代号').enabled,false);assert.deepEqual(data.asr_fixes,{'错音':'正确'});
  await page.locator('#hotwords-search').fill('absent');assert.equal(await page.locator('#hotwords-list .hw-item').count(),0);await page.locator('#hotwords-search').fill('');
  fail=true;await page.getByRole('textbox',{name:'指定译法',exact:true}).fill('更新译法');await page.locator('#hotwords-save').click();await page.waitForFunction(()=>document.getElementById('hotwords-status').textContent.includes('磁盘已满'));assert.equal(await page.getByRole('textbox',{name:'指定译法',exact:true}).inputValue(),'更新译法');
  page.once('dialog',d=>d.dismiss());await page.getByRole('button',{name:'关闭会议热词'}).click();assert.equal(await page.locator('#hotwords-dialog').isVisible(),true);
  await page.setViewportSize({width:760,height:700});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
  const saveBox=await page.locator('#hotwords-save').boundingBox();assert.ok(saveBox.y+saveBox.height<=700,'Save must remain visible in small windows');
  fs.mkdirSync('output',{recursive:true});await page.screenshot({path:'output/hotword-categories.png',fullPage:true});
  assert.equal(errors.length,0,errors.join('\n'));console.log('Category UI PASS: create, filter, edit, direction drafts, enable, save, cloud status, error retention, narrow layout.');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
