// Optional full browser integration check. Requires Playwright and an installed Chrome/Edge.
const {chromium}=require('playwright');
const fs=require('fs');const path=require('path');const assert=require('assert');
const root=path.resolve(__dirname,'..');const output=path.join(root,'reports','dashboard_qa');fs.mkdirSync(output,{recursive:true});
(async()=>{
  const browser=await chromium.launch({headless:true,executablePath:process.env.QF_BROWSER_PATH||'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  const page=await browser.newPage({viewport:{width:1512,height:1050},deviceScaleFactor:1});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  try{
    await page.goto('http://127.0.0.1:8765',{waitUntil:'networkidle'});
    await page.getByRole('heading',{name:'Traffic control, in focus.'}).waitFor();
    assert(await page.getByText('61.5%',{exact:true}).count());
    await page.screenshot({path:path.join(output,'overview.png'),fullPage:true});
    await page.getByRole('link',{name:/Junction replay/}).click();
    await page.getByRole('heading',{name:'Replay the junction.'}).waitFor();
    await page.locator('#time-slider').evaluate(e=>{e.value='300';e.dispatchEvent(new Event('input',{bubbles:true}));});
    assert((await page.locator('#live-time').innerText()).startsWith('05:01'));
    await page.getByRole('button',{name:'Play or pause replay'}).click();await page.waitForTimeout(600);await page.getByRole('button',{name:'Play or pause replay'}).click();
    assert(!(await page.locator('#live-time').innerText()).startsWith('05:01'));
    await page.getByRole('button',{name:'Raw record'}).click();await page.locator('#drawer:not(.hidden)').waitFor();
    assert((await page.locator('#drawer-content').innerText()).includes('Simulation'));await page.keyboard.press('Escape');
    await page.screenshot({path:path.join(output,'replay.png'),fullPage:true});
    await page.getByRole('link',{name:/Quantum lab/}).click();await page.getByRole('button',{name:'EW peak',exact:true}).click();
    assert.equal(await page.getByLabel('E queued vehicles',{exact:true}).inputValue(),'14');
    await page.getByRole('button',{name:/Solve traffic state/}).click();await page.locator('.lab-hero').waitFor({timeout:45000});
    assert((await page.locator('#quantum-results').innerText()).includes('QUBO GAP'));
    await page.screenshot({path:path.join(output,'quantum_lab.png'),fullPage:true});
    const exported=page.waitForEvent('download');await page.getByRole('button',{name:'Export this circuit'}).click();
    assert(fs.readFileSync(await (await exported).path(),'utf8').startsWith('OPENQASM 2.0'));
    await page.getByLabel('N queued vehicles',{exact:true}).fill('15');
    await page.locator('#lab-stale').waitFor();assert((await page.locator('#lab-stale').innerText()).includes('Inputs have changed'));
    await page.getByRole('link',{name:/Data explorer/}).click();await page.getByLabel('Dataset',{exact:true}).selectOption('registry');
    await page.getByRole('columnheader',{name:'source_url',exact:true}).waitFor();
    await page.getByLabel('Search records',{exact:true}).fill('local_train');await page.getByRole('button',{name:'Search',exact:true}).click();
    await page.waitForFunction(()=>document.querySelectorAll('tr[data-record]').length===1&&document.querySelector('tr[data-record]').innerText.includes('local_train'));
    await page.locator('tr[data-record]').first().click();assert((await page.locator('#drawer-content').innerText()).includes('sha256'));await page.keyboard.press('Escape');
    await page.screenshot({path:path.join(output,'data_explorer.png'),fullPage:true});
    await page.getByRole('link',{name:/Evidence & reports/}).click();await page.locator('.artifact').first().waitFor();
    const download=page.waitForEvent('download');await page.locator('.artifact a').first().click();assert((await download).suggestedFilename());
    await page.screenshot({path:path.join(output,'evidence.png'),fullPage:true});
    await page.setViewportSize({width:430,height:900});await page.getByRole('link',{name:/Control room/}).click();await page.getByRole('heading',{name:'Traffic control, in focus.'}).waitFor();
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth+1));
    await page.screenshot({path:path.join(output,'mobile.png'),fullPage:true});
    assert.deepEqual(errors,[]);fs.writeFileSync(path.join(output,'browser_results.json'),JSON.stringify({passed:true,checks:['overview metrics','replay seeking and playback','record inspector','custom-state QAOA solve','custom OpenQASM export','stale-input labeling','dataset filter','source hash inspection','artifact download','mobile layout'],page_errors:errors},null,2));
    console.log('Browser dashboard checks passed.');
  }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
