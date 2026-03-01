#!/usr/bin/env python3
"""
Convert Snyk JSON output to AWS Security Hub ASFF format.

Usage:
    python snyk_to_asff.py <snyk_json_file> <source_version> <output_file>
"""

import json
import sys
import os
import uuid
from datetime import datetime, timezone


SEVERITY_MAP = {
    "critical": "CRITICAL",
    "high": "HIGH",
    "medium": "MEDIUM",
    "low": "LOW",
}

SEVERITY_SCORE_MAP = {
    "CRITICAL": 90,
    "HIGH": 70,
    "MEDIUM": 40,
    "LOW": 10,
}


def get_env(key: str, default: str = "unknown") -> str:
    return os.environ.get(key, default)


def snyk_to_asff(snyk_file: str, source_version: str, output_file: str) -> None:
    account_id = get_env("AWS_ACCOUNT_ID", "183695703210")
    region = get_env("AWS_DEFAULT_REGION", "us-east-1")
    build_id = get_env("CODEBUILD_BUILD_ID", "local-build")

    product_arn = (
        f"arn:aws:securityhub:{region}:{account_id}:product/{account_id}/default"
    )
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    with open(snyk_file, "r") as f:
        snyk_data = json.load(f)

    findings = []

    # Snyk output can be a single object or a list (for multi-project scans)
    if isinstance(snyk_data, dict):
        snyk_data = [snyk_data]

    for project in snyk_data:
        # Handle error responses from Snyk
        if project.get("error"):
            print(f"Snyk error: {project['error']}")
            continue

        project_name = project.get("projectName", "planetary-api")
        vulnerabilities = project.get("vulnerabilities", [])

        for vuln in vulnerabilities:
            vuln_id = vuln.get("id", "unknown")
            snyk_severity = vuln.get("severity", "medium").lower()
            severity_label = SEVERITY_MAP.get(snyk_severity, "MEDIUM")
            severity_score = SEVERITY_SCORE_MAP.get(severity_label, 40)

            title = vuln.get("title", vuln_id)
            package_name = vuln.get("packageName", "unknown")
            package_version = vuln.get("version", "unknown")
            description = vuln.get("description", title)[:1024]

            # CVE/CWE identifiers
            identifiers = vuln.get("identifiers", {})
            cves = identifiers.get("CVE", [])
            cwes = identifiers.get("CWE", [])
            cve_str = cves[0] if cves else ""
            cwe_str = cwes[0] if cwes else ""

            # Fix information
            fixed_in = vuln.get("fixedIn", [])
            fix_version = fixed_in[0] if fixed_in else "No fix available"
            is_patchable = vuln.get("isPatchable", False)
            is_upgradeable = vuln.get("isUpgradable", False)

            fix_text = (
                f"Upgrade {package_name} to {fix_version}. "
                f"Upgradeable: {is_upgradeable}. Patchable: {is_patchable}."
            )

            snyk_url = f"https://snyk.io/vuln/{vuln_id}"

            # Unique finding ID
            finding_id = str(
                uuid.uuid5(
                    uuid.NAMESPACE_URL,
                    f"planetary-api-snyk/{source_version}/{vuln_id}/{package_name}/{package_version}",
                )
            )

            # Build description with package info
            full_description = (
                f"{description}\n\n"
                f"Package: {package_name}@{package_version}\n"
                f"CVE: {cve_str}\n"
                f"CWE: {cwe_str}\n"
                f"Fix: {fix_version}"
            )[:1024]

            finding = {
                "SchemaVersion": "2018-10-08",
                "Id": f"planetary-api-snyk/{source_version}/{finding_id}",
                "ProductArn": product_arn,
                "GeneratorId": "planetary-api-snyk",
                "AwsAccountId": account_id,
                "Types": ["Software and Configuration Checks/Vulnerabilities/CVE"],
                "CreatedAt": now,
                "UpdatedAt": now,
                "Severity": {
                    "Label": severity_label,
                    "Normalized": severity_score,
                },
                "Title": f"[Snyk] {title} in {package_name}",
                "Description": full_description,
                "Remediation": {
                    "Recommendation": {
                        "Text": fix_text,
                        "Url": snyk_url,
                    }
                },
                "SourceUrl": snyk_url,
                "Vulnerabilities": [
                    {
                        "Id": cve_str if cve_str else vuln_id,
                        "ReferenceUrls": [snyk_url],
                        "Vendor": {
                            "Name": "Snyk",
                            "Url": snyk_url,
                            "VendorSeverity": snyk_severity,
                        },
                        **({"Cwes": [cwe_str]} if cwe_str else {}),
                    }
                ],
                "Resources": [
                    {
                        "Type": "Other",
                        "Id": f"planetary-api/requirements.txt/{package_name}",
                        "Details": {
                            "Other": {
                                "PackageName": package_name,
                                "PackageVersion": package_version,
                                "VulnId": vuln_id,
                                "CVE": cve_str,
                                "CWE": cwe_str,
                                "FixVersion": fix_version,
                                "ProjectName": project_name,
                                "SourceVersion": source_version,
                                "BuildId": build_id,
                            }
                        },
                    }
                ],
                "RecordState": "ACTIVE",
            }

            findings.append(finding)

    # Security Hub batch-import-findings accepts max 100 per call
    output = {"Findings": findings[:100]}

    with open(output_file, "w") as f:
        json.dump(output, f, indent=2)

    print(
        f"Converted {len(findings)} Snyk findings to ASFF ({output_file}). "
        f"Exported first {len(output['Findings'])}."
    )


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print(f"Usage: {sys.argv[0]} <snyk_json_file> <source_version> <output_file>")
        sys.exit(1)

    snyk_to_asff(sys.argv[1], sys.argv[2], sys.argv[3])
