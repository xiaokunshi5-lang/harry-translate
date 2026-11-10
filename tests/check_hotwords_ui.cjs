const {chromium} = require('playwright');
const fs = require('fs');
const assert = require('node:assert/strict');

(async () => {
    const browser = await chromium.launch({channel: 'msedge', headless: true});
    try {
        const page = await browser.newPage({viewport: {width: 1440, height: 1000}});
        const errors = [];
        page.on('pageerror', e => errors.push(e.message));
        const glossary = JSON.parse(fs.readFileSync('glossary.json', 'utf8'));
        const originalAsr = JSON.stringify(glossary.asr_fixes);
        const originalZh = JSON.stringify(glossary.terms_en_to_zh);
        const posts = [];
        let failSave = false;
        await page.route('**/api/glossary', async route => {
            if (route.request().method() === 'POST') {
                if (failSave) return route.fulfill({status: 500, json: {status: 'error', message: '测试：保存失败'}});
                const body = route.request().postDataJSON(); posts.push(body); Object.assign(glossary, body);
                return route.fulfill({json: {status: 'ok'}});
            }
            return route.fulfill({json: {status: 'ok', data: glossary}});
        });
        await page.route('**/api/meta', route => route.fulfill({json: {
            cloud_status: Object.fromEntries(['en','zh'].map(lang => [lang, {ready: true, corpus_status: 'confirmed', cloud_phrases_count: Object.keys(glossary[lang === 'en' ? 'terms_zh_to_en' : 'terms_en_to_zh']).length}]))
        }}));
        await page.goto('http://127.0.0.1:8000/');
        await page.getByRole('button', {name: '会议热词', exact: true}).click();
        await page.getByRole('button', {name: '＋ 添加热词'}).waitFor();
        await page.waitForFunction(() => !document.getElementById('hotwords-fields').disabled);
        const initialCount = await page.locator('#hotwords-list .hw-row').count();
        assert.equal(initialCount, Object.keys(glossary.terms_zh_to_en).length);
        await page.locator('#hotwords-list input[aria-label="指定译法"]').first().fill('Edited Translation');
        await page.locator('#hotwords-list button').last().click();
        await page.locator('#hotwords-add').click();
        await page.locator('#hotwords-save').click();
        assert.match(await page.locator('#hotwords-status').innerText(), /补全/);
        const newRow = page.locator('#hotwords-list .hw-row').last();
        await newRow.locator('input').nth(0).fill('会议项目代号');
        await newRow.locator('input').nth(1).fill('Meeting Project Code');
        await page.locator('#hotwords-save').click();
        await page.waitForFunction(() => document.getElementById('hotwords-status').textContent.includes('云端已确认'));
        assert.deepEqual(Object.keys(posts[0]), ['terms_zh_to_en']);
        assert.equal(glossary.terms_zh_to_en['会议项目代号'], 'Meeting Project Code');
        assert.equal(JSON.stringify(glossary.asr_fixes), originalAsr);
        assert.equal(JSON.stringify(glossary.terms_en_to_zh), originalZh);
        await page.screenshot({path: 'output/meeting-hotwords.png'});
        await page.getByRole('button', {name: '关闭会议热词'}).click();
        await page.locator('#btn-meeting-hotwords').click();
        await page.waitForFunction(() => !document.getElementById('hotwords-fields').disabled);
        assert.equal(await page.locator('#hotwords-list .hw-row').count(), initialCount);
        await page.locator('#hotwords-direction').selectOption('zh');
        await page.waitForFunction(() => !document.getElementById('hotwords-fields').disabled);
        await page.locator('#hotwords-add').click();
        let last = page.locator('#hotwords-list .hw-row').last();
        await last.locator('input').nth(0).fill('Conference Test');
        await last.locator('input').nth(1).fill('会议测试');
        failSave = true;
        await page.locator('#hotwords-save').click();
        await page.waitForFunction(() => document.getElementById('hotwords-status').textContent.includes('测试：保存失败'));
        assert.equal(await last.locator('input').nth(0).inputValue(), 'Conference Test');
        failSave = false;
        await page.locator('#hotwords-save').click();
        await page.waitForFunction(() => document.getElementById('hotwords-status').textContent.includes('云端已确认'));
        assert.deepEqual(Object.keys(posts[1]), ['terms_en_to_zh']);
        await page.locator('#hotwords-add').click();
        last = page.locator('#hotwords-list .hw-row').last();
        await last.locator('input').nth(0).fill('Conference Test');
        await last.locator('input').nth(1).fill('重复');
        await page.locator('#hotwords-save').click();
        assert.match(await page.locator('#hotwords-status').innerText(), /重复/);
        page.once('dialog', dialog => dialog.dismiss());
        await page.getByRole('button', {name: '关闭会议热词'}).click();
        assert.equal(await page.locator('#hotwords-dialog').isVisible(), true);
        page.once('dialog', dialog => dialog.accept());
        await page.getByRole('button', {name: '关闭会议热词'}).click();
        assert.equal(await page.locator('#hotwords-dialog').isVisible(), false);
        assert.deepEqual(errors, []);
        console.log('Hotwords UI: load, edit, add, delete, save, reopen, direction, validation, failed save, discard checks PASS. Real glossary unchanged.');
    } finally { await browser.close(); }
})().catch(error => {console.error(error); process.exitCode = 1;});
