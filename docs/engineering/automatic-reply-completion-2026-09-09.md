# Automatic reply completion recovery

The persistent executor had correctly classified The Tea Nomad's reply as an
automatic absence notice and sent no response. Its completed result had no child
task. The acceptance validator rejected that valid terminal reply review three
times, exhausted the task retries, and blocked the acquisition planner.

Reply reviews now have the same completion rule as monitoring and send stages:
retain the observation, source references, and next-step description, then let
the persistent selector choose the next work. Completing a conversation does not
require creating another message or inventing a mission stop. No qualification,
send, suppression, or quota safeguards changed.

Regression coverage verifies that a completed automatic reply produces no first
contact, retains its result, and allows another executor process to pick up the
existing acquisition queue. Missing source observations still fail validation.
Execution, operator, and controlled-mailbox tests: 26 passed.

This is a local persistent-executor change; the web frontend and Railway service
do not execute this acceptance function and need no redeployment. Recovery must
use the retained result of the failed review, preserving its original observation
time and fault evidence. It must not re-send a message or reset uncertain contacts.
