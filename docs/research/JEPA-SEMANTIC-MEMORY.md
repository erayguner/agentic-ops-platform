# JEPA-Inspired Semantic Memory for AOP Agents

**A technical research + architecture study for a persistent, predictive memory layer.**

> Status: **research + reference design**. Scope decisions (confirmed): **augment** the
> existing `aop_common.memory` + `memory_store` layer; recommendation emphasis is
> **pragmatic, JEPA-inspired** (ship predictive-embedding concepts on proven infra; treat
> true JEPA encoders as a flagged research track); stack is **GCP-native** (Vertex AI
> embeddings, Vertex Vector Search, Firestore, ADK 2.3 / MCP / Action Broker).
>
> Evidence tags used throughout: **[E]** evidence (primary source / official docs / shipped
> implementation), **[P]** project-grounded (verifiable in this repo), **[A]** assumption,
> **[S]** speculative / experimental. The *Sources* section (below) lists primary references. **Verification caveat:** the
> deep-research pass fetched 24 sources / 116 candidate claims but hit a session limit
> mid-verification, so only 2 claims received the full adversarial 3-vote (both from the
> I-JEPA paper); the rest are **primary-source-backed but not independently triple-verified** —
> read **[E]** as "stated by the cited primary source, cross-checked against author knowledge."

---

## 1. Executive summary (for senior technical stakeholders)

**The honest headline.** JEPA (Joint-Embedding Predictive Architecture) is a *self-supervised
representation-learning* architecture from Yann LeCun / Meta — it learns to **predict the
latent representation of a masked or future part of an input from a context part, in
representation space rather than input space** (I-JEPA for images, V-JEPA / V-JEPA 2 for
video/world-models). **[E]** It is **not** a memory system, a database, or a retrieval
algorithm. Crucially, **no _production_ system applies JEPA to LLM-agent memory** — but this is
**not pure speculation**: a **Feb-2026 research PoC, "Predictive Associative Memory" (PAM,
arXiv 2602.11322), implements essentially the pattern proposed here** — a JEPA-style predictor
trained on temporal co-occurrence that navigates an embedding space for retrieval — and **beats
cosine on associative recall** (cross-boundary Recall@20 = 0.421 where cosine scores 0;
discrimination AUC 0.916 vs 0.789). **[E]** Separately, **LLM-JEPA** (arXiv 2509.14252, LeCun
co-author, Sept 2025) applies JEPA to LLM *pre-training* — explicitly a "first step," and *not*
memory. **[E]** So: the substrate is production-grade, the predictive-memory idea has a research
datapoint, and *true* JEPA-for-memory remains experimental. Anyone selling a "JEPA memory
product" today is selling JEPA *principles*, not JEPA *models*.

**What is therefore feasible now** is a **JEPA-*inspired* predictive memory layer**: keep a
pretrained encoder (Vertex AI embeddings) as the representation substrate, and add the one
genuinely JEPA-ish, trainable component — a **predictor head that maps a task's context
latent to the latent of the memory the task will *need*** — so the system retrieves by
*predicted need* (anticipatory) rather than only by surface similarity to the current query
(reactive). The predictor is trained **self-supervised on AOP's own operational timelines
by masking** (hide the step that resolved an incident; learn to predict the latent of the
context that resolved it). This is buildable on GCP today and tested by A/B against plain
vector search.

**Why it matters for AOP.** The platform already separates *decision* (specialist agents)
from *execution* (the Action Broker), runs an eventing spine (Pub/Sub), and ships a memory
*safeguard* layer (`memory.py`: scope isolation, content-hash integrity, spotlighting,
injection screening) plus a Firestore store (`memory_store.py`). **[P]** A predictive
semantic memory turns the firehose of signals → findings → actions → outcomes into
**durable, reusable operational knowledge**: the SRE agent recalls how a similar SLO-burn
was resolved last quarter; FinOps recalls which rightsizing the user accepted; the
orchestrator recalls that project Z is decommission-exempt — **without replaying raw
transcripts**, and without an uncontrolled, opaque long-term store (every memory is scoped,
typed, decayed, audited, and screened).

**Recommendation.** Build in phases. **Phase A** (semantic memory on Vertex embeddings +
Vector Search, through the existing safeguards) ships value with zero JEPA and de-risks the
plumbing. **Phase B** adds the JEPA-inspired predictor and proves predictive retrieval beats
cosine on a held-out incident set. **Phases C–D** add lifecycle (consolidation/decay/
reinforcement/conflict) and anticipatory prefetch. **Phase E** (true JEPA encoders) stays a
research spike behind a go/no-go gate. The defensible value is **80% memory engineering, 20%
JEPA-inspired prediction** — and we should say so rather than over-claim.

**What we explicitly will NOT do:** ship an opaque, ever-growing memory that silently steers
agents. Durable/semantic writes are gated, provenance-weighted, and reversible; session
context decays; recall is read-only, scoped, and spotlighted.

---

## 2. Comparison: JEPA-inspired memory vs RAG / vector DBs / knowledge graphs / transcript memory

These are **not** mutually exclusive — the proposed design *uses* a vector DB and *can* feed
a KG. The distinction is in **what is learned and predicted**.

| Dimension | Transcript / replay memory | Vector DB / RAG | Knowledge graph | **JEPA-inspired predictive memory** |
|---|---|---|---|---|
| Unit stored | Raw turns / chunks | Chunk + frozen embedding | Entities + typed relations | **Typed memory item + semantic *target latent*** |
| Recall trigger | Keyword / window | Cosine sim to **current query** | Graph traversal from entity | **Predicted *needed* latent for the task** (anticipatory) |
| Abstraction | None (surface) | Surface-semantic (encoder-fixed) | Explicit, hand/auto-modelled | **Learned, task-predictive; invariant to surface form** **[E?]** |
| Temporal reasoning | Ordering only | Weak (recency hacks) | Bitemporal (e.g., Graphiti) **[E?]** | **Sequence/world-model over event latents → next-need** |
| Learns from outcomes | No | No (static index) | Only if re-extracted | **Yes — predictor + importance fine-tuned on task success** |
| Failure mode | Context bloat, leakage | Retrieves *similar* not *useful* | Extraction/schema drift, cost | Predictor quality; cold-start; needs eval discipline |
| Maturity | Trivial | **Production-standard [E]** | Production (Zep/Graphiti, Neo4j) **[E?]** | **Substrate production; predictor is novel/experimental** |

**The core conceptual difference. [E?]** RAG/vector search answers *"what stored text is most
similar to this query?"* JEPA answers *"what is the abstract representation of the part I
can't see, given the part I can?"* Ported to memory: instead of retrieving memories similar
to the **query**, predict the latent of the memory the **task will need** and retrieve toward
that. This buys (a) **abstraction** — recall by operational meaning, not lexical overlap;
(b) **anticipation** — prefetch likely-needed context from partial signals; (c) **surface
invariance** — the same incident phrased two ways maps to nearby latents.

**Evidence this is real, not hand-waving. [E]** The PAM PoC (arXiv 2602.11322) reports that
temporal-co-occurrence (JEPA-style) retrieval recovers associatively-related memories cosine
cannot — **cross-boundary Recall@20 = 0.421 where cosine scores 0**, and **AUC 0.916 vs 0.789**.
A separate analysis (arXiv 2602.02007) argues **RAG is conceptually mismatched to agent memory**:
RAG targets large *heterogeneous* corpora, whereas an agent's memory is a *bounded, coherent
stream* of highly-correlated, often near-duplicate spans — so retrieval should exploit
temporal/associative structure, which is exactly what a predictor adds. And on the production
side, **Mem0** (arXiv 2504.19413) shows a dedicated extract/consolidate/retrieve layer beats
baseline memory by **+26% (LoCoMo, LLM-judge)** while cutting **p95 latency −91% and token cost
−90%** vs stuffing full history — evidence that *memory engineering itself* (before any JEPA) is
where most of the win lives.

**The honest limits. [E]** JEPA is representation learning, *not* storage or retrieval — you
still need a store (Firestore) and an index (Vector Search). Latent prediction adds value
**only if** you have enough operational history to train the predictor and a real evaluation
loop; otherwise plain RAG is the right default. JEPA gives no free lunch on durability,
governance, or dedup — those are engineering.

**Where each still wins:** vector/RAG = the substrate and the safe default; KG = explicit,
auditable relations (decommission dependency order, IAM graphs) and bitemporal facts —
**complementary**, not replaced; transcript = only as short-lived working memory.

---

## 3. End-to-end reference architecture

Layered so the JEPA-inspired pieces **augment** — never bypass — the existing safeguards.

```
                         ┌──────────────────────────────────────────────┐
   Pub/Sub spine ───────▶│ L1  INGESTION & ENCODING                     │
   ops.signals           │  • Memory Ingestor (Cloud Run, sub to topics)│
   ops.findings          │  • Typed MemoryItem builder                  │
   ops.actions.executed  │  • Target encoder: Vertex AI embeddings      │
   ops.notifications     │    (frozen) + EMA projection head            │
   ops.audit             │  • Safeguard stamp (scope, content-hash)     │
   + MCP tool outputs    └───────────────┬──────────────────────────────┘
   + conversations                       │ writes go THROUGH GuardedMemory
   + documents / BigQuery / SCC          ▼
   ┌───────────────────────────┐   ┌──────────────────────────────────┐
   │ L0 SUBSTRATE (reuse)      │   │ L2  REPRESENTATION & PREDICTION   │
   │ • memory.py safeguards    │◀─▶│  • Context encoder (task→latent)  │
   │   (isolation, integrity,  │   │  • Predictor head (JEPA-inspired):│
   │    spotlight, screen)     │   │    context-latent → needed-latent │
   │ • memory_store.py:        │   │  • Temporal/world model (seq →    │
   │   GuardedMemory +         │   │    next-need latent; prefetch)    │
   │   FirestoreMemoryStore    │   └──────────────────┬────────────────┘
   │ • Firestore (records)     │                      │
   │ • Vertex Vector Search    │◀─────────────────────┘
   │   (ANN index of latents)  │
   └─────────────┬─────────────┘
                 │
   ┌─────────────▼───────────────┐   ┌──────────────────────────────────┐
   │ L3 MEMORY SERVICES          │   │ L4  RECALL API (read path)        │
   │ • Types: semantic/episodic/ │   │  • Predictive Retriever:          │
   │   procedural/user-pref/oper │   │    encode ctx → predict need →    │
   │ • Lifecycle: consolidate,   │──▶│    ANN → rerank → safeguard       │
   │   dedup, decay, reinforce,  │   │    recall-filter → spotlighted    │
   │   conflict-resolve, delete  │   │  • Exposed as MCP tool +          │
   └─────────────────────────────┘   │    pre-task hook (proactive)      │
   ┌─────────────────────────────┐   └──────────────────┬───────────────┘
   │ L5 GOVERNANCE / CONTROL     │                      │
   │ consent · retention · audit │   agents (ADK 2.3): orchestrator +
   │ tenant/user/role isolation  │   sre/devsecops/platform/finops/decom
   │ poisoning defense · profile │◀── feedback: Action Broker outcome →
   └─────────────────────────────┘    reinforcement / ReasoningBank distill
```

**Component responsibilities**

- **L0 Substrate (existing — the augment anchor). [P]** `memory.py` enforces the *policy*
  (scope isolation, content-hash integrity, spotlighting, injection screening); `memory_store.py`
  provides `MemoryStore`/`FirestoreMemoryStore`/`GuardedMemory`. **Every JEPA-layer write and
  read passes through `GuardedMemory`**, so isolation/integrity/poison-screening are inherited,
  not reinvented. Firestore is the durable record-of-truth; Vertex Vector Search is the latent
  index keyed by `record_id`.
- **L1 Ingestion & Encoding.** A Cloud Run Memory Ingestor subscribes to the eventing topics
  and accepts pushed tool/document/structured inputs, builds a typed `MemoryItem`, computes its
  **target latent** (Vertex embedding + optional EMA projection head), stamps it via the
  safeguards, and writes through `GuardedMemory` + upserts the latent to Vector Search.
- **L2 Representation & Prediction (JEPA-inspired core).** *Target encoder* = frozen Vertex
  embeddings (+ EMA-updated projection) → stable memory latents. *Context encoder* → the current
  task/agent/state latent. *Predictor* (the trainable, JEPA-ish head) maps context-latent → the
  latent(s) of memory the task will need. *Temporal/world model* over event-latent sequences
  predicts next-need latents for **anticipatory prefetch**.
- **L3 Memory Services.** Typed memory (semantic/episodic/procedural/user-preference/operational)
  + the lifecycle manager (consolidate, dedup, decay, reinforce, conflict-resolve, delete).
- **L4 Recall API.** Predictive retrieval + multi-factor rerank + safeguard recall-filter
  (`prepare_recall`), exposed both as an **MCP tool** (`memory.recall`, so agents call it like
  any tool, consistent with the read-only/decision-execution-separation model) and as a
  **pre-task hook** for proactive context injection.
- **L5 Governance/Control.** Consent, retention, audit (every write/recall → `ops.audit`),
  tenant/user/role isolation at the `MemoryScope`, poisoning defenses, `deployment_profile`
  gating (ga-only avoids Preview backends), durable-vs-session separation.

**Three data flows**

1. **Write:** event → Ingestor → encode target latent → safeguard stamp → `GuardedMemory.store`
   (Firestore) + Vector Search upsert → async lifecycle (dedup/consolidate). **[P/A]**
2. **Read:** agent task → Recall API → context encode → predict need → ANN → rerank →
   `prepare_recall` (isolation/expiry/integrity/spotlight) → prompt-safe context → agent. **[P/A]**
3. **Feedback:** task outcome (Action-Broker result / verdict) → reinforcement (importance ↑,
   predictor fine-tune) → procedural distillation (ReasoningBank-style trajectory→verdict→pattern). **[A]**

---

## 4. Memory lifecycle & retrieval strategy

### Memory types (mapped to AOP) **[A, design]**
- **Semantic** — distilled, durable facts: "service `checkout` normal p99 ≈ 180 ms"; "project
  `sandbox-x` is decommission-exempt". Cross-session scope.
- **Episodic** — incident/interaction timelines: signal → finding → action → outcome; Slack threads.
- **Procedural** — learned action patterns per signal class (which remediation resolved which
  incident, with verdict) → the platform's ReasoningBank surface.
- **User-preference** — per (tenant, user, role): notification verbosity, auto-approve tiers in dev,
  preferred rightsizing posture.
- **Operational** — structured baselines: SLO histories, cost run-rates, security posture — sourced
  from BigQuery / SCC / Asset Inventory.

### Durable vs session separation — *reuse the existing seam*. **[P]**
`MemoryScope.isolation_key(allow_cross_session=…)` already exists. **Session/working memory** uses
the session-scoped key + short `ttl_s`; **durable knowledge** uses the cross-session key and is
only created by **consolidation** (promotion), never written directly from a single raw turn. This
is the guardrail against "uncontrolled long-term memory": nothing becomes durable without passing
consolidation (corroboration + summarization + provenance check).

### Retrieval (read path)
1. **Encode context** (signal + agent role + recent state) → context latent.
2. **Predict need** → predictor maps context latent → one or more *needed* latents (Phase B+);
   Phase A skips this and queries with the context latent directly (plain semantic search).
3. **ANN search** in Vertex Vector Search over the predicted-need latent(s), filtered by scope +
   memory-type allow-list for the agent's role.
4. **Rerank** by a multi-factor score (Generative-Agents-style, extended):
   `score = w_rel·predRelevance + w_rec·recency + w_imp·importance + w_reinf·reinforcement − w_conf·conflictPenalty`. **[E? for recency/importance/relevance; A for the extension]**
5. **Safeguard recall-filter** — `prepare_recall` drops cross-scope / expired / integrity-failed
   items, spotlights survivors, screens for injection markers. **[P]**
6. Return top-k **prompt-safe** snippets (+ provenance + confidence) to the agent.

### Anticipatory prefetch (Phase D) **[S]**
On an inbound signal, the temporal model predicts the next-need latent *before* the specialist is
invoked and warms a per-incident cache — so recall latency is hidden behind routing.

### Lifecycle operations
- **Consolidation/summarisation:** cluster episodic items in latent space; LLM-summarise a cluster
  into a semantic fact with provenance; promote to durable scope. Runs batched (Cloud Run job).
- **Deduplication:** near-duplicate detection by latent cosine ≥ τ within scope; keep highest-trust/
  newest, link the rest.
- **Decay:** `effective_importance = base_importance · e^(−λ·age) · recencyBoost`, modulated by
  reinforcement; below a floor → eligible for deletion. Mirrors the existing `ttl_s` at retrieval.
- **Reinforcement:** a memory recalled and *used in a successful task* gains importance; unused
  decays. Outcome signal comes from the Action Broker result + (optional) verdict judge.
- **Conflict resolution:** two high-similarity memories with opposing claims → contradiction flag;
  resolve by trust tier (system > tool > retrieved > user/external) then recency; keep the loser
  as superseded (audit), never silently delete.
- **Deletion:** TTL expiry + **right-to-erasure** by scope query (tenant/user) — Firestore delete +
  Vector Search remove + audit record.

---

## 5. Example schemas & pseudocode

### 5.1 `MemoryItem` schema (extends the existing `MemoryRecord`) **[P/A]**
```python
# Builds on aop_common.memory.MemoryRecord (record_id, scope, source, content,
# content_hash, created_at, ttl_s, trust). The JEPA layer adds typing + latent + lifecycle.
class MemoryItem(BaseModel):
    record_id: str
    scope: MemoryScope                      # tenant_id, agent_identity, session_id, environment (+user_id, role)
    mem_type: Literal["semantic","episodic","procedural","user_pref","operational"]
    source: MemorySource                    # user|tool|agent|retrieved|system|external (trust tiers)
    content: str                            # human-readable claim/snippet (the durable text)
    content_hash: str                       # integrity (compute_content_hash)
    target_latent_id: str                   # → Vector Search datapoint id (the embedding lives in the index)
    provenance: dict                        # {source_ref, corroborations, extractor, model, ts}
    importance: float = 0.5                 # base salience (0..1)
    reinforcement: int = 0                  # successful-use count
    valid_from: str; valid_to: str | None   # bitemporal validity (facts can expire/supersede)
    superseded_by: str | None               # conflict resolution link
    ttl_s: int = 0                          # 0 = durable; >0 = session/working
    trust: MemoryTrust                      # trusted | untrusted (default by source)
```

### 5.2 Ingestion (write path)
```python
def ingest(event, scope, *, mem_type, source) -> MemoryItem:
    content = render_claim(event)                          # event → concise claim text
    if screen_for_injection(content):                     # reuse memory.py screen
        quarantine(content, reason="injection-markers"); return None
    latent = target_encoder.embed(content)                # Vertex embeddings (+EMA projection)
    item = new_memory_item(scope=scope, mem_type=mem_type, source=source,
                           content=content, latent=latent)  # stamps content_hash, default trust
    guarded.store(record=item)                             # THROUGH GuardedMemory → Firestore + safeguards
    vector_index.upsert(id=item.target_latent_id, vec=latent, scope=scope.isolation_key())
    emit_audit("memory.write", item)                      # → ops.audit
    enqueue_lifecycle(item)                                # async dedup/consolidate
    return item
```

### 5.3 Predictive recall (read path)
```python
def recall(task_ctx, requester: MemoryScope, *, k=8, types=None) -> list[Recalled]:
    ctx_latent  = context_encoder.embed(task_ctx)
    need_latents = predictor.predict(ctx_latent)          # Phase B+: JEPA-inspired need prediction
                                                          # Phase A: need_latents = [ctx_latent]
    cands = []
    for nl in need_latents:
        cands += vector_index.ann(nl, k=4*k,
                                  filter=scope_filter(requester, allow_types=types))
    raw = [load_record(c.id) for c in cands]              # Firestore records
    safe = prepare_recall(raw, requester)                 # isolation+expiry+integrity+spotlight (memory.py)
    ranked = sorted(safe, key=lambda m: -score(m, ctx_latent))   # multi-factor rerank
    emit_audit("memory.recall", requester, ids=[m.id for m in ranked[:k]])
    return ranked[:k]                                     # prompt-safe, scoped, audited
```

### 5.4 Predictor training (self-supervised, JEPA-inspired) **[S→feasible]**
```python
# Self-supervision by MASKING operational timelines (the genuinely JEPA-ish step).
# For each historical incident timeline T = [e0, e1, ..., resolution]:
#   context = encode(e0..e_i)         (the signal + early state)
#   target  = target_encoder(e_resolution_context)   (EMA encoder; stop-gradient)
#   loss    = ||predictor(context) - sg(target)||^2  (predict latent of the resolving context)
# Train periodically on Vertex AI Training over BigQuery-exported ops.* history.
# Collapse guards: EMA target encoder + stop-gradient (the JEPA recipe); variance/cov regularizer.
```

### 5.5 Consolidation (episodic → semantic)
```python
def consolidate(scope):
    clusters = latent_cluster(episodic_items(scope))      # group near-duplicate/related episodes
    for c in clusters:
        if corroborated(c):                               # ≥2 independent sources OR trusted source
            fact = llm_summarise(c.items)                 # concise durable claim + provenance
            promote(fact, scope=cross_session(scope),     # durable scope (allow_cross_session)
                    importance=salience(c))
```

---

## 6. Threat model & security controls

**Assets:** durable semantic/procedural memory (steers future agent decisions), user-preference
memory (PII), operational baselines. **Trust boundary:** anything an attacker can influence —
user turns, tool outputs, RAG hits, documents, peer-agent text — is **untrusted by default**
(already encoded in `memory.py` `_UNTRUSTED_SOURCES`). **[P]**

| Threat | Vector | Control (✦ = already in repo) |
|---|---|---|
| **Memory poisoning** (plant a false "fact" that later steers agents) | Malicious tool output / document / conversation consolidated into durable memory | Provenance + **trust-tier weighting**; consolidation requires **corroboration** (≥2 independent sources or a trusted source); ✦ injection screening on write; latent-outlier anomaly detection; **human review for high-impact semantic writes**; quarantine queue |
| **Indirect prompt injection via recalled memory** | Instructions hidden in stored content executed at recall | ✦ **Spotlighting** (fence as untrusted data) + ✦ screen on recall; **treat memory as data, never instructions**; Model Armor PI&J filter upstream |
| **Cross-tenant / cross-user leakage** | Recall returns another scope's memory | ✦ `MemoryScope` isolation by construction; per-tenant Vector Search namespace; ✦ `assert_scope_access` in `prepare_recall`; role-based memory-type allow-list |
| **Integrity tampering** | Stored record altered post-write | ✦ `content_hash` bound to source; integrity-fail items dropped at recall |
| **Exfiltration via memory** | Agent coerced to dump memory | Recall is read-only + scoped + rate-limited; ✦ every recall audited → `ops.audit`; no bulk export tool |
| **Stale/contradictory facts** | Outdated memory drives a bad action | Bitemporal `valid_to`; conflict resolution; decay; the Action Broker still policy-gates execution (defence in depth) |
| **Privacy / consent / residency** | PII retained beyond consent / out of region | Consent flags on user memory; per-tenant retention; **region-pinned** Firestore + Vector Search (data residency); **right-to-erasure** by scope |

**Mapping:** memory poisoning and tool-output injection are squarely **OWASP Top 10 for Agentic
Applications** (genai.owasp.org, Dec 2025) memory items; agent identity uses the NHI controls
already referenced in `docs/GOVERNANCE-MAPPING.md`. **[E / P]** Red-team against agent-memory
poisoning / injection research (e.g. arXiv 2503.03704; MINJA-style memory-injection and
AgentPoison-style backdoors). **[E]**

**Governance stance:** durable writes are gated, provenance-weighted, decayed, reversible, and
audited — the explicit antidote to "uncontrolled or opaque long-term memory."

---

## 7. Proof-of-concept plan with measurable success criteria

**PoC scope (offline-first):** one agent — **recommend SRE** (richest signal density) — predictive
recall vs. a plain-cosine baseline, on **replayed historical incidents** (no live agent actions).

**Build:** (1) `MemoryItem` + Ingestor over a BigQuery export of historical `ops.*`; (2) Vertex
embeddings + Vector Search index through `GuardedMemory`; (3) baseline recall (cosine); (4) the
JEPA-inspired predictor trained by masking incident timelines; (5) an eval harness with a
labeled relevance set built from *what context actually resolved each incident*.

**Success criteria (all measurable, pre-registered):**
- **Retrieval relevance:** predictive recall improves **nDCG@10 ≥ 15%** and **MRR ≥ 10%** over the
  cosine baseline on a held-out incident set. **[A — target]**
- **Latency:** recall **p95 < 200 ms** (ANN + rerank + safeguard filter). **[A — target]**
- **Isolation:** **zero** cross-scope leaks in a 1k-query red-team. **[hard gate]**
- **Task proxy:** **≥ 20%** reduction in "relevant context not surfaced" vs baseline on the
  incident replay. **[A — target]**
- **Safety:** **100%** of injection-marked inputs quarantined on write; **100%** of recalled items
  spotlighted. **[hard gate]**

**Go/no-go:** if predictive recall does **not** beat cosine by the thresholds, **ship Phase A
(plain semantic memory) and shelve the predictor** — an explicit, honest exit.

---

## 8. Prioritised roadmap (integrated into AOP)

| Phase | Outcome | Key work | JEPA content | Gate |
|---|---|---|---|---|
| **A — Semantic memory foundation** | Agents recall typed semantic/episodic memory | `MemoryItem`, Ingestor on Pub/Sub, Vertex embeddings + Vector Search, recall MCP tool — all through `GuardedMemory` | None (plain RAG) | Recall live for SRE; safeguards green |
| **B — Predictive retrieval** | Recall by predicted need, A/B-beats cosine | Context/target encoders, predictor head, masking trainer, rerank | **JEPA-inspired predictor** | nDCG@10 ≥ 15% gate (§7) |
| **C — Lifecycle** | Durable knowledge that self-curates | Consolidation, dedup, decay, reinforcement, conflict resolution, procedural/ReasoningBank | Latent clustering | No unbounded growth; conflict audited |
| **D — Anticipatory + temporal** | Proactive context, lower effective latency | Sequence/world model, prefetch cache | **Temporal latent prediction** | Prefetch hit-rate; latency hidden |
| **E — True JEPA (research spike)** | (Maybe) bespoke encoders for ops memory | Adapt I-/V-JEPA-style training to text+ops latents | **True JEPA encoders** **[S]** | Go/no-go vs Phase B baseline |

Phase A is independently valuable and ships even if every later phase is cut.

---

## 9. Recommendations — feasible now vs experimental

**Feasible now (build with confidence). [E?/P/A]**
- Typed semantic/episodic/operational memory on **Vertex AI embeddings + Vertex Vector Search**,
  written and read **through the existing `GuardedMemory` safeguards** (isolation, integrity,
  spotlighting, screening).
- Lifecycle: consolidation, dedup, decay, reinforcement, conflict resolution, right-to-erasure.
- Multi-factor rerank (recency × importance × relevance × reinforcement).
- The **JEPA-inspired predictor head** (context-latent → needed-latent), trained self-supervised on
  AOP's own incident timelines by masking — incremental, A/B-testable, low blast radius. The
  approach has a research datapoint (**PAM**, arXiv 2602.11322: Recall@20 0.421 where cosine 0). **[E]**
- Durable-vs-session separation via the existing `allow_cross_session` scope seam.

**Experimental / research-gated. [S]**
- **True JEPA encoders** trained for the ops-memory latent space (vs. reusing Vertex embeddings).
- Full **world-model anticipatory prefetch** and **learned energy-based relevance** replacing cosine.
- Cross-modal JEPA over logs + metrics + text jointly.

**The disciplined conclusion.** The agent-effectiveness wins come mostly from **good memory
engineering** — typed, governed, decaying semantic memory that reuses the safeguards already in
this repo — with the JEPA-inspired predictor as a **measurable, optional uplift**, not the
foundation. Recommend approving **Phases A–C**, funding the **Phase B PoC** with the §7 gate, and
treating **Phase E** as a research spike. This improves operational decision-making and UX while
keeping long-term memory **scoped, auditable, decayable, and screened** — never opaque or
uncontrolled.

---

## Appendix — open research questions
- Does predictive (need-) retrieval actually beat cosine on *operational* memory at AOP's data
  scale, or only on long conversational benchmarks? **[open]**
- Best self-supervision signal for the predictor: masked-timeline reconstruction vs. outcome-
  contrastive (recalled-and-helped vs recalled-and-ignored)? **[open]**
- How much history is needed before the predictor stops cold-starting? **[open]**
- Can consolidation be made provably non-poisoning (corroboration thresholds vs. coordinated
  poisoning)? **[open]**

## Sources

Deep-research pass: 24 sources fetched, 116 claims extracted, 25 sent to adversarial
verification. The verification step hit a session usage limit, so **only 2 claims received the
full 3-vote** (both from I-JEPA); the rest are **primary-source-backed but not independently
triple-verified** — cross-checked against author knowledge.

**JEPA — primary sources**
- I-JEPA, Assran et al. 2023 — `arXiv:2301.08243` ✓ *vote-verified* (latent-space prediction of
  target-block representations from a context block; semantic masking strategy).
- LeCun, "A Path Towards Autonomous Machine Intelligence", 2022 — `openreview BZ5a1r-kVsf`
  (energy `E_w(x,y,z)=D(s_y, Pred(s_x,z))`; non-generative; H-JEPA world models; anti-generative).
- V-JEPA, 2024 — `arXiv:2404.08471`. V-JEPA 2, 2025 — `arXiv:2506.09985`; Meta blog
  `ai.meta.com/blog/v-jepa-2-world-model-benchmarks` (1.2 B-param world model, >1M hrs video;
  physical/embodied prediction & planning — *not* memory); Meta research page
  `ai.meta.com/research/vjepa`.
- JEPA / H-JEPA energy-based framing — `arXiv:2306.02572`.

**JEPA applied to memory / language — the "honest gap"**
- **PAM — Predictive Associative Memory** — `arXiv:2602.11322` (JEPA-style temporal-co-occurrence
  predictor over an embedding space; Recall@20 = 0.421 where cosine = 0; AUC 0.916 vs 0.789).
- **LLM-JEPA** (LeCun co-author), Sep 2025 — `arXiv:2509.14252` (JEPA for LLM pre-training;
  explicitly a "first step"; *not* a memory/retrieval system).
- RAG-vs-agent-memory mismatch analysis — `arXiv:2602.02007`.

**Agent-memory systems & science**
- **Mem0** — `arXiv:2504.19413` (LoCoMo +26% LLM-judge over OpenAI memory; p95 latency −91%,
  token cost −90% vs full-context).
- **MemGPT/Letta** — `arXiv:2310.08560`. **Generative Agents** memory stream
  (recency × importance × relevance) — `dl.acm.org 10.1145/3586183.3606763`. Memory
  surveys/benchmarks — `arXiv:2501.13956`, `arXiv:2410.10813`, `arXiv:2502.12110`.

**Security**
- **OWASP Top 10 for Agentic Applications**, Dec 2025 — `genai.owasp.org/2025/12/09/…`.
- Agent-memory poisoning / injection — `arXiv:2503.03704` (red-team reference; MINJA- /
  AgentPoison-style threats).

*Supporting commentary (secondary/blog, used for framing only): `aampe.com` (JEPA & semantic
memory), `rewire.it` (predicting embeddings vs generating tokens), `turingpost.com/p/jepa`,
`infoq.com` (hybrid vector retrieval).*
