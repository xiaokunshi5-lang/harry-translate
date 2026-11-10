const { chromium } = require('playwright');
const fs = require('fs');
const assert = require('node:assert/strict');

(async () => {
  const browser = await chromium.launch({channel:'msedge',headless:true});
  try {
    const page = await browser.newPage({viewport:{width:1180,height:900}});
    let validated=false, fail=true, calls=0;
    const errors=[];page.on('pageerror',e=>errors.push(e.message));
    await page.route('http://harry.test/**',async route=>{
      const path=new URL(route.request().url()).pathname;
      if(path==='/desktop/setup')return route.fulfill({contentType:'text/html',body:fs.readFileSync('onboarding.html','utf8')});
      if(path==='/desktop/api-guide')return route.fulfill({contentType:'text/html',body:fs.readFileSync('api-guide.html','utf8')});
      if(path==='/api/desktop/status')return route.fulfill({json:{validated,has_saved_key:false,region:'beijing',workspace:'',devices:validated?[{index:2,name:'麦克风阵列',is_default:true}]:[],audio:{}}});
      if(path==='/api/desktop/validate'){calls++;if(fail)return route.fulfill({status:400,json:{message:'测试：密钥无效'}});validated=true;return route.fulfill({json:{status:'ok'}});}
      if(path==='/api/desktop/test-mic')return route.fulfill({json:{level:40,heard:true,message:'检测到声音，可以开始翻译。'}});
      return route.fulfill({status:404,body:'not found'});
    });
    await page.goto('http://harry.test/desktop/setup');
    await page.locator('#validate').click();
    assert.equal(calls,0);assert.match(await page.locator('#key-status').innerText(),/完整 API Key/);
    assert.equal(await page.locator('#audio-card').isVisible(),false);
    await page.locator('#api-key').fill('test-only-secret');
    await page.locator('#validate').click();
    await page.waitForFunction(()=>document.getElementById('key-status').textContent.includes('密钥无效'));
    assert.equal(await page.locator('#audio-card').isVisible(),false);
    fail=false;await page.locator('#validate').click();
    await page.locator('#audio-card').waitFor({state:'visible'});
    assert.equal(await page.locator('#api-key').inputValue(),'');
    assert.equal(await page.locator('#device').inputValue(),'2');
    await page.locator('#test').click();
    await page.waitForFunction(()=>document.getElementById('audio-status').textContent.includes('检测到声音'));
    await page.locator('#mode').selectOption('meeting');
    assert.equal(await page.locator('#loopback-box').isVisible(),true);
    assert.match(await page.locator('#loopback').innerText(),/未检测到/);
    fs.mkdirSync('output',{recursive:true});
    await page.screenshot({path:'output/desktop-onboarding.png',fullPage:true});
    await page.setViewportSize({width:760,height:600});
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
    await page.getByRole('link',{name:/还没有 API Key/}).click();
    assert.match(await page.locator('h1').innerText(),/6 步/);
    assert.equal(await page.locator('section').count(),7);
    assert.equal(errors.length,0,errors.join('\n'));
    console.log('Desktop UI: empty key, failed/successful verification, audio controls, guide and narrow layout PASS');
  } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
