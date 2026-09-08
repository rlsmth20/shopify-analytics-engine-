# Ask Skubase with Luna

Ask Skubase now supports `gpt-5.6-luna` through the Responses API, with reasoning
set to `none`. The verified model rates are $0.20 input, $0.02 cached input and
$1.20 output per million tokens. See the [official Luna model documentation](https://developers.openai.com/api/docs/models/gpt-5.6-luna).

The feature remains disabled until the owner supplies `OPENAI_API_KEY`, sets
`AI_CHAT_ENABLED=true`, and explicitly authorizes a positive `AI_CHAT_DAILY_USD`.
It has separate permissions and accounting from growth-agent model usage.
The default global ceiling is $0. Default per-shop limits are $0.05, 30 model
attempts per UTC day, and 3 attempts per minute. These limits are admission
ceilings, not spending targets. The model allowlist currently contains only
Luna; an unknown override fails closed rather than using an unpriced model.

Each call includes at most 24 KB of encoded input and request framing, up to
550 output tokens, no tools, a 15-second timeout and no automatic retries.
The maximum token-cost estimate is reserved durably before network I/O.
Concurrent reservations serialize through a short PostgreSQL advisory
transaction lock or SQLite write transaction. Verified usage settles the
reservation, including cached input. Timeouts, crashes and missing usage keep
the maximum charged; they never silently release uncertain spend. A global
daily total has no merchant identity, so tenant deletion cannot refill money
already spent. Per-attempt tenant metadata records model, tokens, cost, latency
and outcome, without raw prompts, answers, catalog text or credentials.

`store:false` disables Responses storage; it is not a claim that the provider
has no other data-retention obligations or policies. Questions and selected
inventory evidence are transmitted to OpenAI only when model access is enabled.
The model receives structured message roles and a bounded JSON evidence block.
Merchant and catalog text remain untrusted data. It cannot edit inventory,
send messages, call external tools, or change spending limits.

Only the authenticated tenant's catalog, settings and actions are loaded.
Named SKUs and product names are matched before the top-priority row limit;
healthy matched catalog items can supply recorded facts too. Identity conflicts
and incomplete planning evidence are labeled for review, with unknown planning
values. No open-PO or supplier-performance evidence is represented as measured.

The existing response remains compatible and adds `model` and `fallback_reason`.
Only a successful model answer has `mode:"ai"` and a model name. Disabled access,
missing credentials, spending/rate limits, unavailable evidence, invalid output
and provider failures return an honest deterministic `mode:"local"` answer with
a reason and `model:null`. Authentication and malformed requests retain their
normal HTTP errors. The latest turn must be a nonempty user question.

`python -m app.db.init_db` registers and creates the two additive economics
tables for existing deployments. Independent synthetic tests cover concurrent
budget admission, unknown-cost retention, idempotent settlement, tenant privacy
and initialization in a fresh process. Mocked-provider tests cover access gates,
missing evidence, held planning values, SKU relevance, structured roles and
multibyte question preservation. No live paid request is needed to verify this
implementation; production model access has not been activated by this change.

The merchant interface labels each reply with its actual source (Luna or local
inventory summary), formats lists safely, and retains one question for retry or
editing after a failure. Conversation state is memory-only and resets when the
signed-in user or shop changes; delayed responses from the old scope are ignored.
The 30-second client timeout covers response headers and body. Demo questions
never request a model.

Release verification passed all 363 backend tests and 196 subtests, all 228
frontend tests, frontend typecheck and production build. The privacy fixture
recognizes the anonymous budget-day table separately from tenant-owned data;
an independent privacy test verifies that a nonzero global spend total survives
tenant deletion while that tenant's individual usage metadata is removed.

Local browser verification used a synthetic authenticated shop and replaced the
provider transport before enabling its simulated model response. An ambiguous
SKU question preserved the two variants' recorded counts (10 and 80) and unknown
planning values. The next question exercised the Responses request, usage
settlement and Luna reply presentation with a clearly synthetic answer. The same
conversation retained the separate local and Luna source labels. No external
model calls were made; this proves the integration flow, not live model quality
or account access. At a 390px viewport the document stayed 390px wide.

For initial activation, add a dedicated OpenAI project key as `OPENAI_API_KEY`
in Railway's backend service variables, outside source control. After the owner
sets a spending ceiling, set `AI_CHAT_DAILY_USD` to that authorized amount and
`AI_CHAT_ENABLED=true`. Keep `GROWTH_MODEL_ENABLED` independent. Validate one
synthetic inventory question against the live provider and inspect its usage
record before claiming live Luna replies have been verified. Turning
`AI_CHAT_ENABLED=false` immediately restores rule-based answers without removing
inventory access or the usage audit.
