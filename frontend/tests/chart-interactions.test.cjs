const assert = require("node:assert/strict");
const { test } = require("node:test");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const ts = require("typescript");
const compile = file => ts.transpileModule(fs.readFileSync(path.join(__dirname,"..",file),"utf8"), {compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX}}).outputText;
const helpers = {};
vm.runInNewContext(compile("lib/chart-interaction.ts"), {exports:helpers});

function mount(file, name, props) {
  const states = []; let cursor = 0;
  const output = {};
  const jsx = (type, props) => ({type, props:props||{}});
  const react = { Fragment:"fragment", useId:()=>"test-id", useRef:()=>({current:null}), useEffect:()=>{},
    useState(initial) { const index = cursor++; if (!(index in states)) states[index] = initial; return [states[index], value => { states[index] = typeof value === "function" ? value(states[index]) : value; }]; } };
  vm.runInNewContext(compile(file), {exports:output, require:key => key === "react" ? react : key === "react/jsx-runtime" ? {jsx,jsxs:jsx} : helpers});
  return { render(next = props) { cursor=0; return output[name](next); } };
}
function nodes(node) { return node == null ? [] : Array.isArray(node) ? node.flatMap(nodes) : typeof node === "object" ? [node,...nodes(node.props?.children)] : []; }
function text(node) { return node == null ? "" : Array.isArray(node) ? node.map(text).join("") : typeof node === "object" ? text(node.props?.children) : String(node); }
function find(tree, type, label) { return nodes(tree).find(node=>node.type===type && text(node).includes(label)); }

test("chart navigation respects sparse dates, keyboard boundaries and changed series lengths", () => {
  assert.equal(helpers.nearestChartPoint(60,[0,10,100]),2);
  assert.equal(helpers.chartIndexForKey("ArrowLeft",0,3),0);
  assert.equal(helpers.chartIndexForKey("ArrowRight",2,3),2);
  assert.equal(helpers.chartIndexForKey("Home",2,3),0);
  assert.equal(helpers.chartIndexForKey("End",0,3),2);
  assert.equal(helpers.chartIndexForKey("ArrowLeft",50,3),1);
  assert.equal(helpers.chartIndexForKey("Enter",0,3),null);
  assert.deepEqual(Array.from(helpers.chartScale([1813,2557]).ticks),[0,1000,2000,3000]);
  assert.ok(helpers.chartScale([-40,80]).min <= -40);
  assert.ok(helpers.chartScale([0,0]).range > 0);
});

test("forecast inspection uses actual day offsets and preserves bounds when the band is hidden", () => {
  const h=mount("components/charts.tsx","ForecastBandChart",{points:[{day_offset:2,expected_units:5,lower_bound:2,upper_bound:8},{day_offset:7,expected_units:12,lower_bound:9,upper_bound:15}]});
  let tree=h.render();
  assert.match(text(tree),/Day \+2/);
  nodes(tree).find(n=>n.type==="input"&&n.props.type==="range").props.onChange({target:{value:"1"}});
  tree=h.render();
  assert.match(text(find(tree,"p","expected units")),/Day \+7.*12 expected units.*9–15/);
  nodes(tree).find(n=>n.type==="input"&&n.props.type==="checkbox").props.onChange({target:{checked:false}});
  tree=h.render();
  assert.equal(nodes(tree).some(n=>n.props.className==="forecast-band"),false);
  assert.match(text(tree),/Range 9–15/);
});

test("donut categories expose actual shares and can return to total", () => {
  const h=mount("components/charts.tsx","DonutChart",{points:[{label:"Healthy",value:75},{label:"Review",value:25}],centerLabel:"SKUs"});
  let tree=h.render();
  find(tree,"button","Review").props.onClick();
  tree=h.render();
  assert.equal(text(nodes(tree).find(n=>n.props.className==="donut-value")),"25.0%");
  assert.equal(find(tree,"button","Review").props["aria-pressed"],true);
  find(tree,"button","Show total").props.onClick();
  assert.equal(text(nodes(h.render()).find(n=>n.props.className==="donut-value")),"100");
});

test("zero-value bars are empty and ranking changes do not mutate the source", () => {
  const points=[{label:"Zero",value:0},{label:"Ten",value:10}];
  const h=mount("components/charts.tsx","HorizontalBarChart",{points});
  let tree=h.render();
  assert.equal(nodes(tree).find(n=>n.props.className?.startsWith("hbar-fill")).props.style.width,"0%");
  nodes(tree).find(n=>n.type==="select").props.onChange({target:{value:"largest"}});
  tree=h.render();
  assert.match(text(nodes(tree).find(n=>n.type==="button")),/^Ten/);
  assert.equal(points[0].label,"Zero");
});

test("report pages, filters and column visibility preserve access to row details", () => {
  const rows=Array.from({length:60},(_,id)=>({id,name:`Product ${id}`}));
  let selected=null;
  const props={columns:[{key:"name",label:"Product",render:r=>r.name},{key:"id",label:"Units",render:r=>r.id}],rows,rowKey:r=>String(r.id),onRowClick:r=>{selected=r.id;},renderRowDetails:r=>r.name,sortKey:"id",sortDirection:"desc",onSort:()=>{},emptyState:"Empty"};
  const h=mount("components/reports/report-components.tsx","ReportTable",props);
  let tree=h.render();
  assert.equal(nodes(tree).filter(n=>n.props.className==="report-row").length,25);
  assert.equal(nodes(tree).find(n=>n.type==="th"&&n.props["aria-sort"]==="descending").props.scope,"col");
  find(tree,"button","Next").props.onClick(); tree=h.render();
  assert.match(text(tree),/26–50/);
  find(tree,"button","View details").props.onClick(); assert.equal(selected,25);
  const checks=nodes(tree).filter(n=>n.type==="input"&&n.props.type==="checkbox");
  assert.equal(checks[0].props.disabled,true);
  checks[1].props.onChange({target:{checked:false}});
  tree=h.render(); assert.equal(nodes(tree).filter(n=>n.type==="th").length,1);
  tree=h.render({...props,rows:rows.slice(0,2)});
  assert.match(text(tree),/1–2/);
  assert.equal(nodes(tree).filter(n=>n.props.className==="report-row").length,2);
});
