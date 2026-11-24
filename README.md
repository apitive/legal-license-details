# legal-license-details

Curated license knowledge base for screening whether open-source code can be incorporated into a commercial product.

**Preliminary screening only. This is not legal advice.** Scope is a curated set of common software, content and source-available licenses, not the full SPDX list.

Version 1.0, reviewed 2026-11-23.

## Layout

```
licenses/        One JSON file per license, named by SPDX id (MIT.json, GPL-3.0-only.json, ...)
rules/
  commercial-integration.yaml   Outcome per license family and activity (SaaS, distribution, ...)
  license-compatibility.yaml    Which licenses can be combined into one work
  legal-escalation.yaml         Triggers that send a finding to legal review
references/
  official-sources.json         Authoritative sources and the risk legend
schemas/
  license.schema.json           JSON Schema every licenses/*.json must satisfy
tests/
  license-scenarios.yaml        Expected outcomes for sample scenarios
  validate.py                   Checks schema, cross-references and scenarios
```

## Risk legend

| Risk | Meaning |
|---|---|
| green | Generally low-friction with conditions |
| amber | Conditional; needs architecture/compliance review |
| red | Likely incompatible with the intended use or high risk; obtain permission or remediate |
| unknown | Insufficient evidence or no rights grant |

## Adding or changing a license

1. Add `licenses/<SPDX-ID>.json` (copy an existing file; `spdx_id` must match the file name).
2. Add the id to one family in `rules/commercial-integration.yaml`.
3. Add compatibility pairs and a scenario if the license behaves differently from its family.
4. Run the validator:

```
pip install jsonschema pyyaml
python tests/validate.py
```

Any license that is not `green` must set `legal_review_required: true` (enforced by the schema).
