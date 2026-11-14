# ADR-003: Composite confidence with hard-gated "I don't know"

**Status:** Accepted

## Context

A RAG system that always answers is more dangerous than one that occasionally refuses. Two questions:

1. When should the system refuse?
2. How do we tell callers "this answer might be unreliable" without forcing them to look at every internal score?

## Decision

- **Hard gate on retrieval confidence.** When `retrieval_confidence < RAG_IDK_RETRIEVAL_THRESHOLD` (default 0.35), or no chunks are retrieved, the answerer short-circuits to the literal `"I don't know."` string and does not call the generation model. This is the spec's "low retrieval confidence → IDK" surface.
- **Composite confidence.** Every non-IDK answer gets a single `composite_confidence` field, the weighted blend of:
  - `retrieval_confidence` — a blend of the post-rerank scores, in `[0, 1]`: `max(0.75 × top, 0.7 × top + 0.3 × mean)`. A plain mean was used first and replaced: when exactly one chunk holds the answer (scores like `[1.0, 0, 0, 0, 0]`) the mean is 0.20 and wrongly triggered the IDK gate.
  - `citation_accuracy` — fraction of bracketed citations the LLM-as-judge marks supported.
  - The blend weight `judge_weight` defaults to 0.5 and is configurable.

Callers who want a stricter contract threshold against `composite_confidence`; callers who only care about hallucinations threshold against `citation_accuracy`.

## Consequences

**Why this works:**

- **The two confidence sources catch different failures.** Low retrieval = "we couldn't find anything to ground against" (early signal). Low citation accuracy = "we found something but the LLM cited it wrong" (late signal). A user threshold of 0.4 on the composite catches both with one number.
- **Hard IDK gate saves an LLM call.** When retrieval is clearly bad, we don't pay the generation roundtrip or the citation-judge calls.
- **Citation verification is mandatory, not optional.** Every non-IDK answer is checked. We treat the verifier as part of the response path because "the answer is grounded" is the project's core value prop.

**Trade-offs:**

- The hard IDK gate can mask cases where retrieval is borderline but the LLM could have stitched an acceptable answer. We accept this — the project explicitly prefers `"I don't know"` to a hallucination. Teams that want a softer gate can lower `RAG_IDK_RETRIEVAL_THRESHOLD`; we don't recommend it.
- The verifier is itself an LLM, so an unreliable verifier propagates noise. We mitigate by running it on a smaller, cheaper model (`gpt-4o-mini`) with a strict JSON-only schema, and by counting any failed or unreadable verdict as "not supported". Per-citation verdicts are not stored yet; storing them would allow later analysis of verifier drift.
- Both the retrieval blend (0.7 / 0.3) and the composite blend are heuristics, not calibrated probabilities. The weights and the 0.35 threshold were chosen by judgment and should be tuned on a labelled set of answerable and unanswerable questions.

## Alternatives considered

- **Always-answer with a free-form "confidence" sentence in the LLM output.** Easier to ship; far harder to threshold against programmatically.
- **Per-citation entailment model (NLI).** More accurate, much heavier dependency footprint. The verifier is structured so swapping in an NLI backend is a single-class change.
- **Self-consistency: sample N answers, take majority vote.** Doubles or triples cost without addressing the actual source of error (citation hallucination). Deferred.

## Revisit if

- The verifier pass becomes a noticeable share of latency. We have a path to skip it when `retrieval_confidence` is very high (say > 0.85), trading a small slice of safety for speed.
- Calibration data shows the composite blend is mis-weighted. The weight is one float to tune.
