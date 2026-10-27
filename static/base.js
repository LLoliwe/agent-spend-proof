'use strict';
const element = (id) => document.getElementById(id);
let report = null;
const sample = {
  payment_required: {
    x402Version: 2,
    resource: {url: 'https://example.org/report'},
    accepts: [{scheme:'exact',network:'eip155:84532',asset:'0x'+'a'.repeat(40),amount:'10000',payTo:'0x'+'c'.repeat(40),maxTimeoutSeconds:60}]
  },
  request_url:'https://example.org/report',network:'eip155:84532',
  expected_asset:'0x'+'a'.repeat(40),expected_pay_to:'0x'+'c'.repeat(40),
  max_amount_atomic:10000,request_method:'GET',request_body:'',offer_index:0,
  min_confirmations:12,require_finalized:true
};
function invalidate(){report=null;element('download').disabled=true;element('result-heading').textContent='Inputs changed';element('result-summary').textContent='Check the current inputs to produce a new result.';element('result').textContent='No result for the current input.';}
element('packet').addEventListener('input',invalidate);
element('example').addEventListener('click',()=>{element('packet').value=JSON.stringify(sample,null,2);element('sample-notice').hidden=false;invalidate();});
element('verify').addEventListener('click',async()=>{
  const button=element('verify');button.disabled=true;
  const notice=element('notice');notice.className='notice';notice.textContent='Checking the supplied evidence…';
  report=null;element('download').disabled=true;
  try{
    const input=JSON.parse(element('packet').value);
    if(!Number.isSafeInteger(input.max_amount_atomic)||input.max_amount_atomic<1)throw new Error('The browser requires max_amount_atomic to be a positive safe integer (at most 9007199254740991). Use the Python API for larger exact integers.');
    const response=await fetch('/api/base/check',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(input)});
    const data=await response.json();
    if(!response.ok)throw new Error(typeof data.detail==='string'?data.detail:JSON.stringify(data.detail));
    report={checked_at:new Date().toISOString(),...data};
    element('result-heading').textContent=data.settlement?'Settlement evidence returned':'Quote matches supplied limits';
    element('result-summary').textContent=data.scope;
    element('result').textContent=JSON.stringify(report,null,2);
    element('download').disabled=false;notice.textContent='Check completed. Review each evidence field and its limits.';
  }catch(error){element('result-heading').textContent='Evidence rejected';element('result-summary').textContent='No payment has been made. Correct the evidence or expectations before checking again.';element('result').textContent=error.message;notice.className='notice error';notice.textContent=error.message;}
  finally{button.disabled=false;}
});
element('download').addEventListener('click',()=>{
  if(!report)return;
  const url=URL.createObjectURL(new Blob([JSON.stringify(report,null,2)+'\n'],{type:'application/json'}));
  const link=document.createElement('a');link.href=url;link.download='base-payment-evidence.json';link.click();URL.revokeObjectURL(url);
});
