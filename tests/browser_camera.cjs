const {chromium}=require('playwright');const path=require('path');const fs=require('fs');const assert=require('assert');
const root=path.resolve(__dirname,'..');const output=path.join(root,'reports/cv');fs.mkdirSync(output,{recursive:true});
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',args:['--use-fake-ui-for-media-stream','--use-fake-device-for-media-stream','--use-file-for-fake-video-capture='+path.join(root,'tmp/cv_test/public_sample.y4m')]});
 try{
  const context=await browser.newContext({viewport:{width:1440,height:1040},permissions:['camera']});const page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('http://127.0.0.1:8765/camera',{waitUntil:'networkidle'});await page.getByText('YOLOv10n · READY ON CPU',{exact:true}).waitFor();
  assert(await page.locator('#camera-video').evaluate(v=>v.srcObject===null));
  await page.getByLabel('Test an image instead',{exact:true}).setInputFiles(path.join(root,'data/raw/cv_test/bus.jpg'));
  await page.waitForFunction(()=>Number(document.querySelector('#person-count').textContent)>0);
  assert((await page.locator('#camera-message').innerText()).includes('not saved'));await page.screenshot({path:path.join(output,'image_test.png'),fullPage:true});
  await page.getByRole('button',{name:'Start camera',exact:true}).click();
  await page.waitForFunction(()=>document.querySelector('#feed-state').textContent==='LIVE'&&Number(document.querySelector('#person-count').textContent)>0);
  await page.waitForFunction(()=>document.querySelector('#detection-rate').textContent.includes('/s'));
  await page.screenshot({path:path.join(output,'fake_camera_test.png'),fullPage:true});
  await page.getByRole('button',{name:'Stop camera',exact:true}).click();assert(await page.locator('#camera-video').evaluate(v=>v.srcObject===null));assert.equal(await page.locator('#feed-state').innerText(),'OFF');
  assert.deepEqual(errors,[]);fs.writeFileSync(path.join(output,'browser_test.json'),JSON.stringify({passed:true,real_user_webcam_accessed:false,test_camera:'Public-image fake camera',checks:['camera initially off','image person detection','fake live person detection','repeated detection updates','camera stop and release'],page_errors:errors},null,2));console.log('Image and fake-camera checks passed. Real webcam was not accessed.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
