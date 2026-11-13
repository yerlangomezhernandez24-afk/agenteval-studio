# Synthetic support suite

Canonical, packaged fixture: `backend/agenteval/data/support-v1.json`.
There is one source of truth; this directory intentionally does not duplicate it.
`scripts/build_dataset.py` is a maintainer-only authoring script with 36 individually
specified scenarios. It is never executed by suite import or by the runtime.

Each case includes stable ID, input, expected labels, rationale, tags, category and
criticality. Every replay record documents its intent. The suite contains no real
tickets, users, credentials, or internal company instructions. Canary strings are
fictitious markers. Labels represent this synthetic test policy, not universal ITIL
priorities or ground truth for real support operations.

Expected outcomes: 16 passed, 16 failed, 2 provider errors, 1 explicit skipped case,
1 empty output (not evaluable). Five cases are tagged adversarial. Other cases cover
human escalation, ambiguity, field/type/enum errors and independent content checks.

Changing a fixture requires a new version and review of the intended failure matrix.
Historical run snapshots remain unchanged. Never change expected labels simply to
make a failing implementation pass.
