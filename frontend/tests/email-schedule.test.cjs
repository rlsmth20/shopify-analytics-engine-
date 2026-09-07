const assert = require("node:assert/strict");
const { test } = require("node:test");
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");
const ts = require("typescript");
const exportsObject = {};
vm.runInNewContext(ts.transpileModule(fs.readFileSync(path.join(__dirname, "../lib/email-schedule.ts"), "utf8"), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText, { exports: exportsObject });
const { readEmailSchedules, emailScheduleError, validScheduleEmail, scheduleDeliveryMessage } = exportsObject;

test("failed or incomplete schedule responses do not masquerade as an off schedule", () => {
  for (const body of [null, {}, {detail:"forbidden"}, {schedules:null}, {schedules:[{}]}, {schedules:[{report_type:"weekly_buy_list",recipient_email:"x@example.com",enabled:"false"}]}]) assert.throws(() => readEmailSchedules(body));
  assert.equal(readEmailSchedules({schedules:[]}).length, 0);
  assert.equal(readEmailSchedules({schedules:[{report_type:"weekly_buy_list",recipient_email:"x@example.com",enabled:true}]} )[0].enabled, true);
});
test("FastAPI validation arrays are readable text and never React children", () => {
  assert.equal(emailScheduleError({detail:[{loc:["body","recipient_email"],msg:"Enter a valid email"}]}, "Failed"), "Enter a valid email");
  assert.equal(emailScheduleError({detail:{unexpected:true}}, "Failed"), "Failed");
  assert.equal(emailScheduleError({detail:"Upgrade needed"}, "Failed"), "Upgrade needed");
});
test("schedule recipients reject missing domains, whitespace and multiple addresses", () => {
  for (const email of ["", "x@", "x@localhost", "x y@example.com", "a@example.com b@example.com"]) assert.equal(validScheduleEmail(email), false);
  assert.equal(validScheduleEmail(" ops@example.com "), true);
});

test("scheduled delivery states never confuse provider acceptance with inbox arrival", () => {
  const accepted = scheduleDeliveryMessage({last_delivery_status:"accepted",last_sent_at:"not a timestamp"});
  assert.match(accepted.text, /accepted/);
  assert.match(accepted.text, /does not confirm it arrived/);
  assert.doesNotMatch(accepted.text, /Invalid Date/);
  const unknown = scheduleDeliveryMessage({last_delivery_status:"unknown",delivery_attempts:1});
  assert.match(unknown.text, /automatic retries.*paused/);
  assert.equal(unknown.needsReview, true);
  assert.match(scheduleDeliveryMessage({last_delivery_status:"failed",delivery_attempts:3}).text, /paused after three attempts/);
  assert.match(scheduleDeliveryMessage(null).text, /No delivery status is available/);
});
