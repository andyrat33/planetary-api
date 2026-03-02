#!/usr/bin/env python3
"""
Convert Semgrep SARIF output to AWS Security Hub ASFF format.

Usage:
    python sarif_to_asff.py <sarif_file> <source_version> <output_file>
"""

import json
import sys
import os
import uuid
from datetime import datetime, timezone


SEVERITY_MAP = {
    "error": "HIGH",
    "warning": "MEDIUM",
    "note": "LOW",
    "none": "INFORMATIONAL",
}

SEVERITY_SCORE_MAP = {
    "HIGH": 70,
    "MEDIUM": 40,
    "LOW": 10,
    "INFORMATIONAL": 1,
}


def get_env(key: str, default: str = "unknown") -> str:
    return os.environ.get(key, default)


def sarif_to_asff(sarif_file: str, source_version: str, output_file: str) -> None:
    account_id = get_env("AWS_ACCOUNT_ID", "183695703210")
    region = get_env("AWS_DEFAULT_REGION", "us-east-1")
    build_id = get_env("CODEBUILD_BUILD_ID", "local-build")

    product_arn = (
        f"arn:aws:securityhub:{region}:{account_id}:product/{account_id}/default"
    )
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    with open(sarif_file, "r") as f:
        sarif = json.load(f)

    findings = []

    for run in sarif.get("runs", []):
        tool_name = run.get("tool", {}).get("driver", {}).get("name", "semgrep")
        rules = {
            rule["id"]: rule
            for rule in run.get("tool", {}).get("driver", {}).get("rules", [])
        }

        for result in run.get("results", []):
            rule_id = result.get("ruleId", "unknown")
            rule = rules.get(rule_id, {})

            # Severity
            level = result.get("level", "warning").lower()
            sarif_severity = (
                rule.get("defaultConfiguration", {}).get("level", level).lower()
            )
            severity_label = SEVERITY_MAP.get(sarif_severity, "MEDIUM")
            severity_score = SEVERITY_SCORE_MAP.get(severity_label, 40)

            # Message
            message = result.get("message", {})
            description = message.get(
                "text", rule.get("shortDescription", {}).get("text", "No description")
            )
            title = rule.get("name", rule_id)
            full_description = rule.get("fullDescription", {}).get("text", description)

            # Location
            locations = result.get("locations", [{}])
            loc = locations[0] if locations else {}
            phys_loc = loc.get("physicalLocation", {})
            artifact_loc = phys_loc.get("artifactLocation", {})
            region_loc = phys_loc.get("region", {})

            file_path = artifact_loc.get("uri", "unknown")
            start_line = region_loc.get("startLine", 1)

            # Unique finding ID
            finding_id = str(
                uuid.uuid5(
                    uuid.NAMESPACE_URL,
                    f"planetary-api-semgrep/{source_version}/{rule_id}/{file_path}/{start_line}",
                )
            )

            # Help URL
            help_url = rule.get("helpUri", f"https://semgrep.dev/r/{rule_id}")

            finding = {
                "SchemaVersion": "2018-10-08",
                "Id": f"planetary-api-semgrep/{source_version}/{finding_id}",
                "ProductArn": product_arn,
                "GeneratorId": "planetary-api-semgrep",
                "AwsAccountId": account_id,
                "Types": ["Software and Configuration Checks/Static Code Analysis"],
                "CreatedAt": now,
                "UpdatedAt": now,
                "Severity": {
                    "Label": severity_label,
                    "Normalized": severity_score,
                },
                "Title": f"[Semgrep] {title}",
                "Description": description[:1024],
                "Remediation": {
                    "Recommendation": {
                        "Text": full_description[:512],
                        "Url": help_url,
                    }
                },
                "SourceUrl": help_url,
                "Resources": [
                    {
                        "Type": "Other",
                        "Id": f"planetary-api/{file_path}",
                        "Details": {
                            "Other": {
                                "FilePath": file_path,
                                "StartLine": str(start_line),
                                "RuleId": rule_id,
                                "ToolName": tool_name,
                                "SourceVersion": source_version,
                                "BuildId": build_id,
                            }
                        },
                    }
                ],
                "RecordState": "ACTIVE",
            }

            findings.append(finding)

    # batch-import-findings --findings expects a JSON array, not an object
    output = findings[:100]  # cap at 100 per API limit

    with open(output_file, "w") as f:
        json.dump(output, f, indent=2)

    print(
        f"Converted {len(findings)} Semgrep findings to ASFF ({output_file}). "
        f"Exported first {len(output)}."
    )


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print(f"Usage: {sys.argv[0]} <sarif_file> <source_version> <output_file>")
        sys.exit(1)

    sarif_to_asff(sys.argv[1], sys.argv[2], sys.argv[3])
