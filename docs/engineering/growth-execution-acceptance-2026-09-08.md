# Persistent acquisition production acceptance — September 8

## Root cause

Server work and browser operator work used separate queues. The continuous server
worker never dispatched browser tasks; only an hourly Codex heartbeat consumed
them, with an additional three-contact wake limit. Server discovery also ranked
below observation and review. Research hitting a resource window was marked done
instead of retaining a due time. Healthy monitoring therefore concealed an
unattempted acquisition backlog.

## Architecture changed

Queue selection now ranks replies/checks P0, acquisition P1, blocking funnel work
P2, evaluation P3, routine reconciliation P4 and other maintenance P5. The existing
Windows host runs a supervised pull executor against the production operator
queue. It claims a fenced lease, refreshes ownership, commits stage evidence and
successors atomically, and immediately selects again without an hourly wake or
per-wake send count. Failed runs retain bounded retries. Stale leases recover.
Unknown send results never release capacity or authorize replay.

The supervisor launches directly as Python, contains Codex children in a Windows
job object, and binds its database after loading production credentials. These
details were corrected during actual restart testing, which exposed surviving
child processes and an eagerly imported local database connection. No credentials
were added or printed. The hourly heartbeat was updated in place to avoid
competing with the executor and retain its existing review/oversight duties.

The API and `/growth` dashboard expose execution state and starvation/offline/
exhausted-retry faults. Admission still serializes all channels through the fixed
20-contact rolling gate. Fresh retained essential checks are required for browser
admission. Skubase's own accounts are explicitly excluded from discovery and
admission after production revealed a self-authored promotional reply incorrectly
qualified by the old heuristic.

## Production evidence

No manual continue instruction or manually executed prospect task was issued
after the supervisor's initial startup. Source and qualification observations came
from its ordinary autonomous runs, using the signed-in browser and production DB.

| Stage | Persisted result | Observed outcome |
| --- | --- | --- |
| Essential checks | 7895 | Dedicated Gmail/support alias, existing Reddit offer/chat; no priority reply found |
| DISCOVER | 7937 | Two real searches/four reads; Urban Skin Rx qualified for further investigation only |
| QUALIFY | 7991 | January excess-inventory source not current; no permitted general business form; excluded without sending |
| Next selection | 7996 | Supervisor immediately persisted and selected a distinct footwear discovery successor |
| Restart/recovery | 8105 | Same unfinished footwear task completed on attempt **2**, with new executor owner `browser:09fabecd075e49059da168df34164cb4` |
| Next selection after recovery | 8111 | Real Brooks & Avery source produced a qualification successor; supervisor claimed it without owner intervention |

The first two acquisition actions shared owner
`browser:d94326f3ba064f689199ff195d1ff259`. Their progress records are **7942** and
**7996**. An additional autonomous exclusion, **8017**, rejected Skubase's own
post and is not presented as discovery of another merchant. The recovered task
is `0a65c7a8ff31573a77faf3b8c8a21c8e7a52db4daa727aaa04302c88be156eda`.

This verifies the user-authorized acquisition-stage fallback, not two live sends.
No new send was claimed during these observations. The ledger remained **5/20**,
with **15** available, **0** unresolved intents and **0** duplicate first-contact
records. Its largest recorded rolling send count was 13. Concurrent saturation,
ambiguous-send retention, restart deduplication and low-quality rejection were
also tested in isolated databases; production was not filled with test prospects
or artificial reservations to exercise its ceiling.

## Releases and validation

- Final Railway backend: `e9fea2ff-a0bf-4b11-8aff-274c15ac611c`, SUCCESS.
- Vercel frontend: `dpl_Fx6n2XUc2XKWwDckmvqStSdbbRtp`, READY on `www.skubase.io`.
- Full growth suite: 101 passed; final targeted execution/operator/discovery/
  admission suite: 23 passed. Frontend build, typecheck and nine dashboard checks
  passed. Public production dashboard retains its owner-authentication requirement.
- Read-only repeatable audit: `scripts/verify-growth-execution.py`; captured
  production snapshot: ignored `.growth-deploy/execution-acceptance.json`.

The computer/browser/Codex subscription remains a real executor dependency. It is
now supervised and its absence is an explicit fault; no claim is made that a
powered-off desktop can execute browser actions. The server continues separately.
