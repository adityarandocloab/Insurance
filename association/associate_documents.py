import re


def normalize_policy_number(value):
    """
    Normalizes a policy number for comparison.
    """

    if not value:
        return None

    return re.sub(
        r"[^A-Z0-9]",
        "",
        str(value).upper()
    )


def normalize_name(value):
    """
    Normalizes an insured or carrier name.
    """

    if not value:
        return None

    value = re.sub(
        r"[^A-Z0-9 ]",
        " ",
        str(value).upper()
    )

    value = re.sub(r"\s+", " ", value)

    return value.strip()


def get_acord_policy_numbers(acord_schema):
    """
    Collects every policy number found on an ACORD 25.
    """

    policy_numbers = set()

    coverages = acord_schema.get("coverages", {})

    for coverage_data in coverages.values():

        policy_number = normalize_policy_number(
            coverage_data.get("policy_number")
        )

        if policy_number:
            policy_numbers.add(policy_number)

    return policy_numbers


def names_are_similar(first_name, second_name):
    """
    Performs a simple Version 1 insured-name comparison.

    This permits the ACORD insured field to include an address
    while the endorsement contains only the company name.
    """

    first_name = normalize_name(first_name)
    second_name = normalize_name(second_name)

    if not first_name or not second_name:
        return False

    return (
        first_name in second_name
        or second_name in first_name
    )


def associate_endorsement_to_acord(
    acord_record,
    endorsement_record
):
    """
    Determines whether one endorsement belongs to one ACORD 25.

    Policy number is the strongest signal. Named insured and
    dates are supporting signals.
    """

    acord_schema = acord_record["schema"]
    endorsement_schema = endorsement_record["schema"]

    acord_policies = get_acord_policy_numbers(
        acord_schema
    )

    endorsement_policy = normalize_policy_number(
        endorsement_schema.get("policy_number")
    )

    policy_match = (
        endorsement_policy is not None
        and endorsement_policy in acord_policies
    )

    insured_match = names_are_similar(
        acord_schema.get("named_insured"),
        endorsement_schema.get("named_insured")
    )

    endorsement_period = (
        endorsement_schema.get("policy_period")
        or {}
    )

    endorsement_effective_date = (
        endorsement_period.get("effective_date")
        or endorsement_schema.get(
            "endorsement_effective_date"
        )
    )

    acord_dates = set()

    for coverage in acord_schema.get(
        "coverages",
        {}
    ).values():

        effective_date = coverage.get(
            "effective_date"
        )

        if effective_date:
            acord_dates.add(effective_date)

    # Dates use different formats in your current output,
    # so they are recorded but not required for Version 1.
    date_evidence_available = bool(
        endorsement_effective_date
        and acord_dates
    )

    if policy_match:
        confidence = "HIGH"

        if insured_match:
            reason = (
                "Policy number and named insured match"
            )
        else:
            reason = "Policy number match"

        return {
            "associated": True,
            "confidence": confidence,
            "reason": reason,
            "policy_number": endorsement_policy,
            "insured_match": insured_match,
            "date_evidence_available":
                date_evidence_available
        }

    if insured_match:
        return {
            "associated": False,
            "confidence": "LOW",
            "reason": (
                "Named insured matches, but the policy "
                "number does not match or is missing"
            ),
            "policy_number": endorsement_policy,
            "insured_match": True,
            "date_evidence_available":
                date_evidence_available,
            "requires_review": True
        }

    return {
        "associated": False,
        "confidence": "NONE",
        "reason": (
            "No matching policy number or named insured"
        ),
        "policy_number": endorsement_policy,
        "insured_match": False,
        "date_evidence_available":
            date_evidence_available,
        "requires_review": True
    }


def associate_batch(page_records):
    """
    Associates every endorsement in an intake batch with the
    most appropriate ACORD 25.

    Returns one candidate submission for each ACORD 25.
    """

    acord_records = [
        record
        for record in page_records
        if record["schema"].get("document_type")
        == "ACORD_25"
    ]

    endorsement_records = [
        record
        for record in page_records
        if record["schema"].get("document_type")
        == "ENDORSEMENT"
    ]

    other_records = [
        record
        for record in page_records
        if record["schema"].get("document_type")
        not in {"ACORD_25", "ENDORSEMENT"}
    ]

    submissions = []

    for submission_number, acord_record in enumerate(
        acord_records,
        start=1
    ):
        submissions.append({
            "submission_id":
                f"SUB-{submission_number:03d}",

            "acord_record":
                acord_record,

            "endorsement_records": [],

            "association_results": []
        })

    unassociated_records = []

    for endorsement_record in endorsement_records:

        possible_matches = []

        for submission in submissions:

            result = associate_endorsement_to_acord(
                submission["acord_record"],
                endorsement_record
            )

            if result["associated"]:
                possible_matches.append(
                    (submission, result)
                )

        if len(possible_matches) == 1:

            submission, result = possible_matches[0]

            submission[
                "endorsement_records"
            ].append(endorsement_record)

            submission[
                "association_results"
            ].append(result)

        elif len(possible_matches) > 1:

            unassociated_records.append({
                "record": endorsement_record,
                "reason": (
                    "Endorsement matches more than one "
                    "ACORD 25"
                ),
                "requires_review": True
            })

        else:

            unassociated_records.append({
                "record": endorsement_record,
                "reason": (
                    "No ACORD 25 produced a reliable "
                    "association"
                ),
                "requires_review": True
            })

    return {
        "submissions": submissions,
        "unassociated_records":
            unassociated_records,
        "other_records": other_records,
        "acord_count": len(acord_records),
        "endorsement_count":
            len(endorsement_records)
    }