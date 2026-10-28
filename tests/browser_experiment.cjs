const {chromium}=require('playwright');const path=require('path');const fs=require('fs');const crypto=require('crypto');const assert=require('assert');
const root=path.resolve(__dirname,'..');const digest=p=>crypto.createHash('sha256').update(fs.readFileSync(path.join(root,p))).digest('hex');
(async()=>{
 const protectedFiles=['models/demand_model.cbm','models/quantum_demo/first_qubo.json','reports/simulation_demo/controller_results.csv'];
 const before=Object.fromEntries(protectedFiles.map(p=>[p,digest(p)]));
 const browser=await chromium.launch({headless:true,executablePath:process.env.QF_BROWSER_PATH||'C:/Program Files/Google/Chrome/Application/chrome.exe'});
 try{
  const page=await browser.newPage({viewport:{width:1512,height:1050}});await page.goto('http://127.0.0.1:8765',{waitUntil:'networkidle'});
  await page.getByRole('heading',{name:'Traffic control, in focus.'}).waitFor();await page.getByRole('button',{name:/New experiment/}).click();
  await page.getByRole('button',{name:/Run SUMO comparison/}).click();
  await page.waitForFunction(()=>document.querySelector('#experiment').value.startsWith('exp_'),{},{timeout:180000});
  const run=await page.locator('#experiment').inputValue();assert(run.startsWith('exp_'));
  assert(!await page.locator('#experiment-dialog').evaluate(e=>e.open));
  const data=await page.evaluate(async id=>(await fetch('/api/overview?run='+id)).json(),run);
  assert.equal(data.results.length,3);assert.equal(data.config.seeds.length,1);
  assert(data.results.every(r=>r.unfinished_vehicles===0&&r.colliding_vehicle_events===0));
  for(const p of protectedFiles)assert.equal(digest(p),before[p]);
  await page.screenshot({path:path.join(root,'reports/dashboard_qa/new_experiment.png'),fullPage:true});
  fs.writeFileSync(path.join(root,'reports/dashboard_qa/experiment_results.json'),JSON.stringify({passed:true,run,controller_runs:data.results.length,reference_artifacts_unchanged:true},null,2));
  console.log('Dashboard launched a fresh SUMO/QAOA experiment; original artifacts are unchanged.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
