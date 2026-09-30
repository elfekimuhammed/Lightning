// Optional local browser acceptance check; never uses Documents or real profiles.
// NODE_PATH must resolve playwright; LIGHTNING_PYTHON selects the project Python.
const {chromium, firefox} = require('playwright');
const {spawn} = require('node:child_process');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const assert = require('node:assert/strict');

(async () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'lightning-browser-check-'));
  const child = spawn(process.env.LIGHTNING_PYTHON || '.venv/bin/python', [
    '-u', '-m', 'lightning', '--profiles', '--no-browser', '--profile-root', path.join(root, 'Profiles'),
  ], {stdio: ['ignore', 'pipe', 'pipe']});
  let runningBrowser;
  let currentPage;
  try {
    const launch = await new Promise((resolve, reject) => {
      let output = '';
      const timer = setTimeout(() => reject(new Error('Local server did not start')), 20000);
      child.on('error', reject);
      child.stdout.on('data', data => {
        output += data.toString();
        const found = output.match(/http:\/\/127\.0\.0\.1:\d+\/__launch\?code=[\w-]+/);
        if (found) { clearTimeout(timer); resolve(found[0]); }
      });
    });
    const origin = new URL(launch).origin;
    let storage;
    for (const [name, engine, executable] of [
      ['chromium', chromium, process.env.LIGHTNING_CHROMIUM],
      ['firefox', firefox, process.env.LIGHTNING_FIREFOX],
    ]) {
      runningBrowser = await engine.launch({headless: true, ...(executable ? {executablePath: executable} : {})});
      const context = await runningBrowser.newContext({viewport: {width: 1360, height: 1000}, ...(storage ? {storageState: storage} : {})});
      const page = await context.newPage();
      currentPage = page;
      const errors = [], violations = [], failed = [];
      page.on('pageerror', error => errors.push(String(error)));
      page.on('response', response => { if (response.status() >= 400) failed.push(response.url().replace(origin, '') + ':' + response.status()); });
      await page.addInitScript(() => {
        window.cspFailures = [];
        document.addEventListener('securitypolicyviolation', event => window.cspFailures.push(event.violatedDirective));
      });
      await page.goto(storage ? origin + '/profiles' : launch);
      await page.screenshot({path: path.join(root, name + '-chooser.png'), fullPage: true});
      await page.getByRole('link', {name: 'Create a profile', exact: true}).click();
      await page.getByLabel('Profile name', {exact: true}).fill(name + ' household');
      await page.getByLabel('Password', {exact: true}).fill('Synthetic test passphrase 123');
      await page.getByLabel('Confirm password', {exact: true}).fill('Synthetic test passphrase 123');
      await page.getByRole('button', {name: 'Create profile', exact: true}).click();
      await page.getByRole('checkbox').check();
      await page.getByRole('button', {name: 'I saved my key', exact: true}).click();
      await page.waitForURL(origin + '/');
      await page.goto(origin + '/accounts/new');
      await page.locator('input[name="name"]').fill(name + ' wallet');
      await page.locator('select[name="account_type"]').selectOption('CASH');
      await page.locator('form[method="post"] button[type="submit"], form[method="post"] button:not([type])').click();
      await page.waitForURL(url => url.pathname !== '/accounts/new');
      assert((await page.locator('body').innerText()).includes(name + ' wallet'));
      await page.goto(origin + '/');
      await page.screenshot({path: path.join(root, name + '-finance.png'), fullPage: true});
      violations.push(...await page.evaluate(() => window.cspFailures));
      // Exercise the existing popup loader, including its nonce-bearing scripts.
      await page.getByRole('link', {name: '+ Add account', exact: true}).click();
      await page.locator('#app-popup[open]').waitFor();
      await page.locator('#app-popup-content input[name="name"]').fill(name + ' popup wallet');
      await page.locator('#app-popup-content select[name="account_type"]').selectOption('CASH');
      await page.locator('#app-popup-content button[type="submit"], #app-popup-content button:not([type])').click();
      await page.waitForTimeout(700);
      violations.push(...await page.evaluate(() => window.cspFailures));
      const other = await context.newPage();
      await other.goto(origin + '/');
      await page.goto(origin + '/profiles');
      await page.getByRole('button', {name: 'Lock profile', exact: true}).click();
      await page.waitForURL(origin + '/profiles');
      await other.waitForURL(origin + '/profiles', {timeout: 20000});
      await page.getByRole('link').filter({hasText: name + '_household'}).click();
      await page.getByLabel('Password', {exact: true}).fill('Synthetic test passphrase 123');
      await page.getByRole('button', {name: 'Unlock profile', exact: true}).click();
      await page.waitForURL(origin + '/');
      assert((await page.locator('body').innerText()).includes(name + ' wallet'));
      assert((await page.locator('body').innerText()).includes(name + ' popup wallet'));
      await page.goto(origin + '/profiles');
      await page.getByRole('button', {name: 'Lock profile', exact: true}).click();
      await page.waitForURL(origin + '/profiles');
      await page.setViewportSize({width: 390, height: 844});
      await page.screenshot({path: path.join(root, name + '-mobile.png'), fullPage: true});
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
      assert.deepEqual(errors, []);
      assert.deepEqual(violations, []);
      assert.deepEqual(failed, []);
      storage = await context.storageState();
      await runningBrowser.close();
      runningBrowser = null;
      console.log(name + ': setup, finance save, popup, lock, unlock, mobile and CSP passed');
    }
    console.log('Synthetic screenshots: ' + root);
  } catch (error) {
    if (currentPage && !currentPage.isClosed()) {
      await currentPage.screenshot({path: path.join(root, 'failure.png'), fullPage: true});
      console.error('Failure screenshot: ' + path.join(root, 'failure.png'));
    }
    throw error;
  } finally {
    if (runningBrowser) await runningBrowser.close();
    child.kill('SIGINT');
    // Leave this isolated scratch directory for visual inspection, never delete
    // broad paths or user-selected folders from a test helper.
  }
})().catch(error => { console.error(error.message); process.exitCode = 1; });
