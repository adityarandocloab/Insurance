# rules/compliance_rules.py

def safe_int(value):

    if value is None:
        return None

    try:
        return int(value)
    except:
        return None


def validate_general_liability(acord_schema):

    gl = acord_schema["coverages"]["general_liability"]

    limit = safe_int(
        gl.get("each_occurrence")
    )

    if limit is None:

        return {
            "status": "REVIEW_REQUIRED",
            "reason": "Missing GL limit"
        }

    if limit >= 2000000:

        return {
            "status": "PASS",
            "reason": "GL limit meets requirement"
        }

    return {
        "status": "FAIL",
        "reason": f"GL limit {limit} below requirement"
    }


def validate_auto_liability(acord_schema):

    auto = acord_schema["coverages"][
        "automobile_liability"
    ]

    limit = safe_int(
        auto.get("combined_single_limit")
    )

    if limit is None:

        return {
            "status": "REVIEW_REQUIRED",
            "reason": "Missing auto limit"
        }

    if limit >= 1000000:

        return {
            "status": "PASS",
            "reason": "Auto limit meets requirement"
        }

    return {
        "status": "FAIL",
        "reason": f"Auto limit {limit} below requirement"
    }


def validate_waiver(evidence_tags):

    if "WAIVER_OF_SUBROGATION" in evidence_tags:

        return {
            "status": "PASS",
            "reason":
                "Waiver-of-subrogation evidence found"
        }

    return {
        "status": "MISSING",
        "reason":
            "Required waiver-of-subrogation "
            "evidence was not found"
    }

def validate_additional_insured(
    evidence_tags
):

    if "ADDITIONAL_INSURED" in evidence_tags:

        return {
            "status": "PASS",
            "reason": "Additional insured evidence found"
        }

    return {
        "status": "FAIL",
        "reason": "Additional insured evidence missing"
    }

def validate_primary_non_contributory(
    evidence_tags
):

    if "PRIMARY_NONCONTRIBUTORY" in evidence_tags:

        return {
            "status": "PASS",
            "reason": "Primary and non-contributory evidence found"
        }

    return {
        "status": "FAIL",
        "reason": "Primary and non-contributory evidence missing"
    }

def validate_products_completed_operations(
    acord_schema
):

    gl = acord_schema["coverages"][
        "general_liability"
    ]

    limit = safe_int(
        gl.get(
            "products_completed_operations"
        )
    )

    if limit is None:

        return {
            "status": "REVIEW_REQUIRED",
            "reason": "Missing completed operations limit"
        }

    if limit >= 2000000:

        return {
            "status": "PASS",
            "reason": "Completed operations meets requirement"
        }

    return {
        "status": "FAIL",
        "reason": (
            f"Completed operations limit "
            f"{limit} below requirement"
        )
    }

def validate_umbrella(
    acord_schema
):

    umbrella = acord_schema["coverages"][
        "umbrella_excess"
    ]

    limit = safe_int(
        umbrella.get(
            "each_occurrence"
        )
    )

    if limit is None:

        return {
            "status": "REVIEW_REQUIRED",
            "reason": "Missing umbrella limit"
        }

    if limit >= 2000000:

        return {
            "status": "PASS",
            "reason": "Umbrella limit meets requirement"
        }

    return {
        "status": "FAIL",
        "reason": (
            f"Umbrella limit {limit} "
            f"below requirement"
        )
    }



def run_compliance_checks(
    acord_schema,
    endorsement_schemas
):
    combined_evidence = set(
        acord_schema.get(
            "evidence_tags",
            []
        )
    )

    for endorsement_schema in endorsement_schemas:

        combined_evidence.update(
            endorsement_schema.get(
                "evidence_tags",
                []
            )
        )

    combined_evidence = sorted(
        combined_evidence
    )

    results = {}

    results["general_liability"] = (
        validate_general_liability(
            acord_schema
        )
    )

    results["automobile_liability"] = (
        validate_auto_liability(
            acord_schema
        )
    )

    results["waiver_of_subrogation"] = (
        validate_waiver(
            combined_evidence
        )
    )

    results["additional_insured"] = (
        validate_additional_insured(
            combined_evidence
        )
    )

    results[
        "primary_non_contributory"
    ] = (
        validate_primary_non_contributory(
            combined_evidence
        )
    )

    results[
        "products_completed_operations"
    ] = (
        validate_products_completed_operations(
            acord_schema
        )
    )

    results["umbrella"] = (
        validate_umbrella(
            acord_schema
        )
    )

    overall_status = determine_overall_status(
        results
    )

    return {
        "overall_status": overall_status,
        "checks": results,
        "combined_evidence":
            combined_evidence
    }


def determine_overall_status(
    compliance_results
):

    statuses = [
        result["status"]
        for result
        in compliance_results.values()
    ]

    if "REVIEW_REQUIRED" in statuses:
        return "HUMAN_REVIEW_REQUIRED"

    if "MISSING" in statuses:
        return "INCOMPLETE_SUBMISSION"

    if "FAIL" in statuses:
        return "NON_COMPLIANT"

    return "COMPLIANT"