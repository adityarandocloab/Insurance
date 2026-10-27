# submission/submission_package.py

def build_submission_package(
    acord_schema,
    endorsement_schema,
    association_result,
    compliance_results
):
    """
    Builds the final package object
    that represents one insurance submission.
    """

    return {

        "overall_status":
            compliance_results["overall_status"],

        "associated":
            association_result["associated"],

        "association_reason":
            association_result[
                "association_reason"
            ],

        "named_insured":
            acord_schema.get(
                "named_insured"
            ),

        "producer":
            acord_schema.get(
                "producer"
            ),

        "policy_numbers": {

            "general_liability":
                acord_schema["coverages"]
                ["general_liability"]
                .get("policy_number"),

            "automobile":
                acord_schema["coverages"]
                ["automobile_liability"]
                .get("policy_number"),

            "umbrella":
                acord_schema["coverages"]
                ["umbrella_excess"]
                .get("policy_number")
        },

        "evidence": sorted(

            list(
                set(
                    acord_schema.get(
                        "evidence_tags",
                        []
                    )
                    +
                    endorsement_schema.get(
                        "evidence_tags",
                        []
                    )
                )
            )
        ),

        "checks":
            compliance_results["checks"]
    }