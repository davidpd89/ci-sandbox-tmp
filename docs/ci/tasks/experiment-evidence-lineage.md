# Implementación CI — identidad auditable de ensayos entre redes

Origen: revisión adversarial de [PR #3](https://github.com/davidpd89/ci-sandbox-tmp/pull/3), 2026-10-09.
Base: `ci/test-campaign-parent`. Rama: `ci/experiment-evidence-lineage`.

## Hueco específico, no cubierto por PR #3

`tools/cross_network_learning.py::_evidence_digest` hashes self-reported aggregate counts, dated cohort properties, target network and queue. Two independently conducted experiments with coincidentally identical aggregate counts, cohort dates and properties could receive the SAME hash, so an external verification approved for one could accidentally be reused for the other.

The current gate is read-only and still demands manual approval; nevertheless its documentation must not claim proof identity until linked to independently audited assignment/provenance records.

This is **experiment identity**, not a cross-platform user identity (#85), an A/B statistical framework (#23), or content bandit (#80). Do not duplicate their scope.

## Encargo para GPT

1. Verify the current PR #3 and official private code (`davidpd89/rrss-davidporto-CODE`, branch `integracion/crecimiento-2026-10`) before designing a migration.
2. Define a **versioned** evidence contract with an opaque experiment identifier anchored to an independent local audit manifest or immutable registry. A user-controlled `experiment_id`/UUID alone must NOT grant verification.
3. Bind evidence identity, experiment design, cohort manifest reference, origin/target network, target queue and target capability/permission check into a canonical digest with explicit domain/version separation.
4. Keep legacy `schema=1` readable and reportable, but fail closed for promotion when the independent identity contract is absent or unverified. Document backward compatibility and migration behavior explicitly.
5. Add deterministic synthetic tests: two distinct experiments with numerically identical aggregates; same trial with changed queue; altered manifest/assignment; duplicated evidence; stale permissions; legacy input; malformed metadata; invalid or malicious JSON; no PII or secrets in outputs.
6. Run Python 3.11 on both Windows and Linux; no API calls to social networks, mobile devices or browsers, no real writes, no credentials, no state migrations on the official system.
7. Compare public Python repositories/libraries maintained on 2026-10-09, including licensing, dependencies, security and Windows compatibility; reuse minimal components if they win against stdlib. A useful option to evaluate is Hypothesis (MPL-2.0, Python >=3.10, Windows), but no mandatory dependency without a concrete advantage.
8. Document trust boundaries: `verified` evidence is supplied only by independently trusted local review; never accept self-attestation in the aggregate JSON. State what remains unprovable without a real audited experiment.
9. Leave code, tests, documentation, provenance and second adversarial review in this PR. **Do not merge**; Claude is the controller.

## Acceptance criteria

- Different audited trial identities cannot share an approval even with identical counts and timestamps.
- An arbitrary claimed identifier never bypasses independent verification.
- Previously reviewed legacy inputs never silently become approved by a new schema.
- No regression of #3 queue isolation or no-action invariant.
- Windows and Ubuntu offline CI both green against the **final HEAD**.
- The report includes a reproducible sample contract, exact source versions and outstanding deployment/canary limitations.

No real account actions, publications, follows, likes, responses, deletion, token logging, or secret material. Use synthetic data exclusively.
