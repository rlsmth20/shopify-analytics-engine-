# Self-replenishing acquisition: production acceptance

Verified September 8, 2026 against the production database and the supervised
Windows acquisition executor. Implementation commit: `5da6252`.

## Natural empty queue and autonomous transition

The pre-existing discovery chain naturally completed at evidence **8759**, with
no successor. The queue was not cleared for this test. Mission progress was
**0/10 verified qualified users**, with **5/20** rolling new-contact capacity used,
**15** remaining, no unresolved send reservation, and no acquisition hold.

The idle supervisor was restarted to load the implementation. No operator-enqueue,
manual prospect seed, manual task claim/completion, or owner/Codex continuation
instruction was used during the following transition. The supervisor itself
created the planning stage and all subsequent acquisition work.

| Production event | Evidence | Observed behavior |
| --- | --- | --- |
| Queue empty | 8806 | Depth zero, incomplete mission, remaining capacity recorded |
| Autonomous planning queued | 8807 | Supervisor created leased plan from retained bounded context |
| Plan completed | 8861 | Proposed purchasing-export adoption hypothesis using prior merchant evidence and search outcomes |
| Hypothesis admission | 8864 | Deterministic admission retained the new hypothesis |
| Empty queue reconsidered | 8868 | Supervisor selected from its newly retained hypothesis bank |
| Hypothesis selected | 8869 | Ranked and selected the export/purchase discovery decision |
| Discovery started | 8877 | Supervisor claimed and executed task `9c778435bebd390c4c1b2993bb551fab161031ad41e3f69dbc49e2a847c60bc6` |
| Real discovery completed | 8949 | One exact native search and four source reads; exclusions and observed counts retained |
| Autonomous continuation started | 8963 | Supervisor picked up topic 666251 for further merchant-context discovery without intervention |

The planner-selected query was:

```text
"export" "purchase" after:2026-08-09 order:latest
```

The preceding completed searches concerned overstock and slow-moving stock. The
executor checked its retained search coverage and confirmed the export/purchase
query had not already been executed. This was not a date-only or synonymous
rerun of the preceding search.

The live search displayed **50+** results; its exact total remains UNKNOWN. Four
source reads found an already-contacted merchant (louisepatterson), a disclosed
tool builder (salor_works), and older merchant requests/recent vendor promotion.
No new qualification or send was justified. These are real discovery outcomes,
not simulated leads or claimed acquired users. The executor then selected the
unexamined purchasing context at <https://community.shopify.com/t/666251> and
started task `52c0af1db0670e96682219317a61260d69066dfaea18e2cf77e8ec42582ac2dc`.

Final observed executor owner:
`browser:a6480531b4ec47cab8b56e5a8e875bb4`; no operational fault or blocker.
The rolling contact count remained **5/20**. Architecture changes stopped after
this verified transition; acquisition continues under the existing supervisor.

## Validation and recovery

- 108 growth/planner tests passed, plus 27 subtests. The focused planner suite
  passed again after the schema correction.
- Tests cover empty-queue planning without fixtures seeding acquisition tasks,
  automatic discovery/qualification succession across restart, competing leases,
  retry backoff, mission/capacity/safety gates, synonym/date-only duplicate rejection,
  source penalties, retained UNKNOWN costs, budget waits and unsupported TRUE_IDLE.
- Live verification caught a schema/validator length mismatch: the first plan's
  decision was 1410 characters while validation allowed 1400. Explicit output
  bounds now constrain decisions to 900 characters. One automatic retry was
  interrupted during the corrective supervisor reload. The existing fenced lease
  expired and the third attempt completed; no task or send history was reset.
- Railway backend deployment `11b1b427-3b86-4e3c-892d-0ce3974f9d6e` reached SUCCESS.
  <https://api.skubase.io/health> returned HTTP 200 with status `ok`.

The read-only [verification script](../../scripts/verify-growth-planner.py) reports
the production event chain, executor ownership and retained outcomes. The captured
snapshot is in ignored `.growth-deploy/planner-acceptance.json`; raw browser/model
execution logs remain under `.growth-deploy/executor/`. Neither the audit script
nor this report creates acquisition work.

The agent still depends on the available local host/browser and Codex subscription.
Research budgets and safety/provider holds have explicit durable retry states;
they do not turn unfinished acquisition into mission completion. The 20-contact
ceiling, zero advertising budget, qualification standards and channel restrictions
remain unchanged.
