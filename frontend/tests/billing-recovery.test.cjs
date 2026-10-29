const assert = require('node:assert/strict');
const { test } = require('node:test');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');
const code = ts.transpileModule(fs.readFileSync(path.join(__dirname, '../app/(app-shell)/billing/page.tsx'), 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX },
}).outputText;
const inactive = { is_shopify_installed: true, plan_id: 'none', subscription_status: 'inactive', billing_status_error: null, shopify_domain: 'fixture.myshopify.com' };
function harness(load, subscribe = async () => ({ok:true, status:200, json:async()=>({url:'https://fixture.myshopify.com/approval'})})) {
  let cursor=0;
  const slots=new Map(), effects=[], redirects=[], reconnects=[], posts=[];
  const jsx=(type,props)=>({type,props});
  const modules={
    'react/jsx-runtime':{jsx,jsxs:jsx},
    react:{
      useState(initial){ const i=cursor++; if(!slots.has(i))slots.set(i,initial); return [slots.get(i),v=>slots.set(i,v)]; },
      useCallback(fn,deps){const i=cursor++;if(!slots.has(i))slots.set(i,fn);return slots.get(i);},
      useEffect(fn,deps){const i=cursor++;if(!slots.has(i)){slots.set(i,deps);effects.push(fn);}},
    },
    'next/link':{__esModule:true,default:'a'},
    '@/lib/api-base':{API_BASE_URL:'https://fixture.test'},
    '@/components/auth-guard':{useAuth:()=>({user:{in_trial:false,trial_ends_at:null}})},
    '@/components/section-card':{SectionCard:'section'},
    '@/lib/entitlements':{fetchBillingStatus:load,invalidateEntitlementsCache(){}},
    '@/lib/billing-view':{getStripePortalAction:()=>null},
    '@/lib/plans':{PRICING_TIERS:[{key:'starter',name:'Starter',monthly:{plan:'starter_monthly',price:'$29'},features:[]}]},
    '@/lib/shopify-embedded':{isEmbeddedShopifyContext:()=>true,reconnectShopify:async domain=>{reconnects.push(domain);},redirectTopLevel:url=>redirects.push(url),authenticatedFetch:async(url,init)=>{posts.push({url,init});return subscribe();}},
  };
  const exports={};
  vm.runInNewContext(code,{exports,require:id=>modules[id],Error,Date});
  function render(){cursor=0;const tree=exports.default();const nodes=[],text=[];function walk(n){if(Array.isArray(n))return n.forEach(walk);if(typeof n==='string')text.push(n);else if(n&&typeof n==='object'){nodes.push(n);walk(n.props?.children);}}walk(tree);while(effects.length)effects.shift()();return {text:text.join(' '),button:label=>nodes.find(n=>n.type==='button'&&n.props.children===label)};}
  async function settle(){for(let i=0;i<3;i++){render();await new Promise(setImmediate);}return render();}
  return {settle,render,redirects,reconnects,posts};
}

test('rejected grant shows recovery, hides stale paid plan, and retry restores plan approval',async()=>{
  let body={...inactive,plan_id:'scale',subscription_status:'active',billing_status_error:'shopify_unauthorized'};
  const f=harness(async()=>body);
  let ui=await f.settle();
  assert.match(ui.text,/Reconnect Shopify to check your plan/);
  assert.doesNotMatch(ui.text,/Current plan/);
  ui.button('Reconnect Shopify').props.onClick(); await new Promise(setImmediate);
  assert.deepEqual(f.reconnects,['fixture.myshopify.com']);
  body=inactive;
  ui.button('Retry billing check').props.onClick(); ui=await f.settle();
  ui.button('Choose Starter').props.onClick(); await new Promise(setImmediate);
  assert.deepEqual(f.redirects,['https://fixture.myshopify.com/approval']);
  assert.equal(f.posts.length,1);
});

test('after reinstall a failed billing check still lets the merchant request plan approval (Shopify 1.2.2)',async()=>{
  const f=harness(async()=>({...inactive,plan_id:'scale',subscription_status:'active',billing_status_error:'shopify_unauthorized'}));
  const ui=await f.settle();
  assert.ok(ui.button('Retry billing check'));
  ui.button('Choose Starter').props.onClick(); await new Promise(setImmediate);
  assert.equal(f.posts.length,1);
  assert.equal(f.posts[0].url,'https://fixture.test/billing/shopify/subscribe');
  assert.deepEqual(f.redirects,['https://fixture.myshopify.com/approval']);
});

test('network failure remains retryable without approving or assuming a plan',async()=>{
  let fail=true;
  const f=harness(async()=>{if(fail)throw new Error('offline');return inactive;});
  let ui=await f.settle();
  assert.ok(ui.button('Retry billing check'));
  assert.ok(ui.button('Choose Starter'));
  assert.doesNotMatch(ui.text,/Current plan/);
  assert.equal(f.posts.length,0);
  fail=false;ui.button('Retry billing check').props.onClick();ui=await f.settle();
  assert.ok(ui.button('Choose Starter'));
});

test('declined plan remains selectable; unknown submit outcome is never automatically replayed',async()=>{
  const f=harness(async()=>inactive,async()=>{throw new Error('request lost');});
  let ui=await f.settle();
  ui.button('Choose Starter').props.onClick();ui=await f.settle();
  assert.equal(f.posts.length,1);
  assert.equal(f.redirects.length,0);
  assert.match(ui.text,/Network error/);
});
