"""Validate the knowledge base: schema, cross-references and scenario expectations.

Usage:  python tests/validate.py        (needs: pip install jsonschema pyyaml)
"""
import json
import sys
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parent.parent
errors = []


def err(msg):
    errors.append(msg)


schema = json.loads((ROOT / "schemas" / "license.schema.json").read_text(encoding="utf-8"))
validator = Draft202012Validator(schema)

# 1. Every license file validates and its id matches the file name.
licenses = {}
for path in sorted((ROOT / "licenses").glob("*.json")):
    data = json.loads(path.read_text(encoding="utf-8"))
    for e in validator.iter_errors(data):
        err(f"{path.name}: {e.message}")
    if data.get("spdx_id") != path.stem:
        err(f"{path.name}: spdx_id {data.get('spdx_id')!r} does not match file name")
    licenses[data.get("spdx_id", path.stem)] = data

# 2. Every license is covered by exactly one family in commercial-integration.yaml.
ci = yaml.safe_load((ROOT / "rules" / "commercial-integration.yaml").read_text(encoding="utf-8"))
family_of = {}
for fam, spec in ci["families"].items():
    for lic in spec["licenses"]:
        if lic in family_of:
            err(f"{lic} appears in families {family_of[lic]} and {fam}")
        family_of[lic] = fam
        if lic not in licenses:
            err(f"family {fam} references unknown license {lic}")
        elif spec["legal_review"] != licenses[lic]["legal_review_required"]:
            err(f"{lic}: legal_review differs between family {fam} and licenses/{lic}.json")
for lic in licenses:
    if lic not in family_of:
        err(f"{lic} is not assigned to any family in commercial-integration.yaml")

# 3. Reference files parse.
refs = json.loads((ROOT / "references" / "official-sources.json").read_text(encoding="utf-8"))
if not refs.get("official_sources"):
    err("references/official-sources.json has no sources")
esc = yaml.safe_load((ROOT / "rules" / "legal-escalation.yaml").read_text(encoding="utf-8"))
compat = yaml.safe_load((ROOT / "rules" / "license-compatibility.yaml").read_text(encoding="utf-8"))
for pair in compat["pairs"]:
    for lic in pair["inbound"]:
        if lic not in licenses:
            err(f"compatibility pair references unknown inbound license {lic}")
    for lic in pair["outbound"]:
        if lic not in licenses and not (lic == "proprietary" or lic.startswith("any")):
            err(f"compatibility pair references unknown outbound license {lic}")
trigger_ids = {t["id"] for t in esc["triggers"]}

# 4. Scenario evaluation. Only triggers expressible from license data + activity are evaluated.


def outcome(lic, activity):
    spec = ci["families"][family_of[lic]]
    return spec.get("activities", {}).get(activity, spec["default"])


def triggers(lic, activity):
    d = licenses[lic]
    out = set()
    if d["default_screening_risk"] == "red":
        out.add("risk-red")
    if d["default_screening_risk"] == "unknown":
        out.add("risk-unknown")
    if lic == "NOASSERTION":
        out.add("no-license")
    if "noncommercial" in d["family"]:
        out.add("noncommercial")
    if d["family"] == "network copyleft" and activity == "saas_modified":
        out.add("network-copyleft-modified")
    if lic in ("SSPL-1.0", "Elastic-2.0") and activity == "managed_service_of_component":
        out.add("managed-service")
    if d["family"] == "strong copyleft" and activity in ("distributed_binary", "distributed_source"):
        out.add("strong-copyleft-distribution")
    if d["family"] == "library copyleft" and activity == "distributed_binary":
        out.add("library-copyleft-distribution")
    if lic in ("BUSL-1.1", "LicenseRef-Proprietary", "Commons-Clause"):
        out.add("custom-terms")
    if d["legal_review_required"]:
        out.add("legal-review-flag")
    return out


def compat_result(inbound, outbound):
    for pair in compat["pairs"]:
        if inbound in pair["inbound"] and (
            outbound in pair["outbound"] or "any" in pair["outbound"]
        ):
            return pair["result"]
    return compat["default"]


scen = yaml.safe_load((ROOT / "tests" / "license-scenarios.yaml").read_text(encoding="utf-8"))
for s in scen["scenarios"]:
    lic, act, exp = s["license"], s["activity"], s["expect"]
    if lic not in licenses:
        err(f"scenario {s['id']}: unknown license {lic}")
        continue
    if act not in ci["activities"]:
        err(f"scenario {s['id']}: unknown activity {act}")
        continue
    got = {
        "risk": licenses[lic]["default_screening_risk"],
        "outcome": outcome(lic, act),
        "legal_review": licenses[lic]["legal_review_required"],
    }
    for k, v in got.items():
        if exp[k] != v:
            err(f"scenario {s['id']}: {k} expected {exp[k]!r}, got {v!r}")
    if set(exp["escalate"]) != triggers(lic, act):
        err(f"scenario {s['id']}: escalate expected {sorted(exp['escalate'])}, got {sorted(triggers(lic, act))}")
    for t in exp["escalate"]:
        if t not in trigger_ids:
            err(f"scenario {s['id']}: unknown trigger {t}")

for c in scen["compatibility"]:
    got = compat_result(c["inbound"], c["outbound"])
    if got != c["expect"]:
        err(f"compat {c['inbound']} -> {c['outbound']}: expected {c['expect']}, got {got}")

if errors:
    print("FAILED")
    for e in errors:
        print(" -", e)
    sys.exit(1)
print(f"OK: {len(licenses)} licenses, {len(scen['scenarios'])} scenarios, {len(scen['compatibility'])} compatibility checks")
