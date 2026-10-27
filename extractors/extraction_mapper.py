import re


# =========================================================
# GENERAL HELPERS
# =========================================================

KNOWN_LABELS = {
    "NAMED INSURED",
    "ENDORSEMENT NUMBER",
    "POLICY SYMBOL",
    "POLICY NUMBER",
    "POLICY PERIOD",
    "EFFECTIVE DATE OF ENDORSEMENT",
    "ISSUED BY",
    "ISSUED BY (NAME OF INSURANCE COMPANY)",
    "PRODUCER",
    "INSURED",
    "CONTACT",
    "NAME:",
    "PHONE",
    "FAX",
    "E-MAIL",
    "ADDRESS:",
    "COVERAGES",
    "CERTIFICATE HOLDER",
    "CANCELLATION",
}


def normalize_lines(text):
    """
    Converts Azure output into a clean list of non-empty lines.
    """

    lines = []

    for raw_line in text.splitlines():
        line = re.sub(r"\s+", " ", raw_line).strip()

        if line:
            lines.append(line)

    return lines


def normalize_label(value):
    """
    Normalizes labels so that punctuation and spacing differences
    do not prevent a match.
    """

    return re.sub(
        r"[^A-Z0-9]+",
        " ",
        value.upper()
    ).strip()


def find_exact_line(lines, label, start=0):
    """
    Finds a label only when the whole line matches.

    This prevents the word INSURED inside ADDITIONAL INSURED
    from being mistaken for the ACORD INSURED heading.
    """

    target = normalize_label(label)

    for index in range(start, len(lines)):
        if normalize_label(lines[index]) == target:
            return index

    return None


def find_line_containing(lines, phrase, start=0, end=None):
    """
    Finds a line containing a phrase.
    """

    phrase = phrase.upper()

    if end is None:
        end = len(lines)

    for index in range(start, min(end, len(lines))):
        if phrase in lines[index].upper():
            return index

    return None


def is_known_label(value):
    normalized = normalize_label(value)

    return normalized in {
        normalize_label(label)
        for label in KNOWN_LABELS
    }


def clean_value(value):
    if value is None:
        return None

    value = re.sub(r"\s+", " ", value).strip(" :|")

    return value or None


def collect_lines_between(
    lines,
    start_label,
    end_labels,
    max_lines=12
):
    """
    Collects lines following an exact heading until another
    specified heading is reached.
    """

    start_index = find_exact_line(lines, start_label)

    if start_index is None:
        return None

    end_targets = {
        normalize_label(label)
        for label in end_labels
    }

    values = []

    for line in lines[
        start_index + 1:
        start_index + 1 + max_lines
    ]:
        if normalize_label(line) in end_targets:
            break

        if not is_known_label(line):
            values.append(line)

    return clean_value("\n".join(values))


def is_date(value):
    return bool(
        re.fullmatch(
            r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}",
            value.strip()
        )
    )


def is_money(value):
    return bool(
        re.fullmatch(
            r"\$?\s*\d[\d,]*(?:\.\d{2})?",
            value.strip()
        )
    )


def normalize_money(value):
    if not value:
        return None

    digits = re.sub(r"[^\d.]", "", value)

    return digits or None


def looks_like_policy_number(value):
    """
    Applies conservative checks so dates, dollar amounts,
    and headings are not returned as policy numbers.
    """

    value = value.strip()

    if is_date(value):
        return False

    if is_money(value):
        return False

    if len(value) < 6:
        return False

    if " " in value and not any(
        character.isdigit()
        for character in value
    ):
        return False

    if not any(character.isdigit() for character in value):
        return False

    if not re.fullmatch(r"[A-Z0-9\- ]+", value.upper()):
        return False

    rejected = {
        "POLICY NUMBER",
        "POLICY EFF",
        "POLICY EXP",
        "LIMITS",
        "CLAIMS MADE",
        "OCCUR",
    }

    return normalize_label(value) not in {
        normalize_label(item)
        for item in rejected
    }


def get_section(lines, start_phrase, end_phrases):
    """
    Returns the lines for one coverage section of an ACORD 25.
    """

    start_index = find_line_containing(
        lines,
        start_phrase
    )

    if start_index is None:
        return []

    end_index = len(lines)

    for end_phrase in end_phrases:
        possible_end = find_line_containing(
            lines,
            end_phrase,
            start=start_index + 1
        )

        if (
            possible_end is not None
            and possible_end < end_index
        ):
            end_index = possible_end

    return lines[start_index:end_index]


def find_first_money_after_label(
    lines,
    label,
    search_distance=10
):
    """
    Finds the first dollar amount after a coverage-limit label.
    """

    label_index = find_line_containing(lines, label)

    if label_index is None:
        return None

    for line in lines[
        label_index + 1:
        label_index + 1 + search_distance
    ]:
        match = re.search(
            r"\$\s*([\d,]+(?:\.\d{2})?)",
            line
        )

        if match:
            return normalize_money(match.group(1))

    return None


def find_policy_number_in_section(section_lines):
    """
    Finds a likely policy number within one coverage section.
    """

    for line in section_lines:
        if looks_like_policy_number(line):
            return clean_value(line)

    return None


def find_date_pair_in_section(section_lines):
    """
    Finds the first effective-date and expiration-date pair
    within one coverage section.
    """

    dates = []

    for line in section_lines:
        for match in re.findall(
            r"\d{1,2}/\d{1,2}/\d{2,4}",
            line
        ):
            dates.append(match)

    if len(dates) >= 2:
        return {
            "effective_date": dates[0],
            "expiration_date": dates[1],
        }

    return {
        "effective_date": None,
        "expiration_date": None,
    }


# =========================================================
# ENDORSEMENT EXTRACTION
# =========================================================

def extract_endorsement_named_insured(text):
    lines = normalize_lines(text)

    return collect_lines_between(
        lines,
        "NAMED INSURED",
        ["ENDORSEMENT NUMBER"],
        max_lines=5
    )


def extract_endorsement_number(text):
    lines = normalize_lines(text)

    index = find_exact_line(
        lines,
        "ENDORSEMENT NUMBER"
    )

    if index is None or index + 1 >= len(lines):
        return None

    candidate = lines[index + 1]

    # Some endorsements leave this field blank, causing the next
    # label, such as POLICY SYMBOL, to appear immediately afterward.
    if is_known_label(candidate):
        return None

    if re.fullmatch(r"[A-Z0-9\-]+", candidate.upper()):
        return candidate

    return None


def extract_policy_symbol(text):
    lines = normalize_lines(text)

    index = find_exact_line(
        lines,
        "POLICY SYMBOL"
    )

    if index is None or index + 1 >= len(lines):
        return None

    candidate = lines[index + 1]

    if is_known_label(candidate):
        return None

    if re.fullmatch(r"[A-Z0-9\-]+", candidate.upper()):
        return candidate

    return None


def extract_endorsement_policy_number(text):
    lines = normalize_lines(text)

    index = find_exact_line(
        lines,
        "POLICY NUMBER"
    )

    if index is None:
        return None

    for candidate in lines[index + 1:index + 4]:
        if is_known_label(candidate):
            continue

        if looks_like_policy_number(candidate):
            return candidate

    return None


def extract_policy_period(text):
    match = re.search(
        r"POLICY PERIOD\s*\n?\s*"
        r"(\d{1,2}/\d{1,2}/\d{2,4})"
        r"\s*(?:TO|-)\s*"
        r"(\d{1,2}/\d{1,2}/\d{2,4})",
        text,
        re.IGNORECASE
    )

    if match:
        return {
            "effective_date": match.group(1),
            "expiration_date": match.group(2),
        }

    return {
        "effective_date": None,
        "expiration_date": None,
    }


def extract_endorsement_effective_date(text):
    match = re.search(
        r"EFFECTIVE DATE OF ENDORSEMENT\s*\n?\s*"
        r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
        text,
        re.IGNORECASE
    )

    return match.group(1) if match else None


def extract_endorsement_carrier(text):
    lines = normalize_lines(text)

    index = None

    for position, line in enumerate(lines):
        if line.upper().startswith("ISSUED BY"):
            index = position
            break

    if index is None or index + 1 >= len(lines):
        return None

    candidate = lines[index + 1]

    if is_known_label(candidate):
        return None

    return clean_value(candidate)


def build_endorsement_schema(text, evidence_tags=None):
    policy_period = extract_policy_period(text)

    return {
        "document_type": "ENDORSEMENT",
        "evidence_tags": evidence_tags or [],
        "named_insured":
            extract_endorsement_named_insured(text),
        "carrier":
            extract_endorsement_carrier(text),
        "policy_number":
            extract_endorsement_policy_number(text),
        "policy_symbol":
            extract_policy_symbol(text),
        "policy_period": policy_period,
        "endorsement_number":
            extract_endorsement_number(text),
        "endorsement_effective_date":
            extract_endorsement_effective_date(text),
    }


# =========================================================
# ACORD 25 EXTRACTION
# =========================================================

def extract_acord_named_insured(text):
    """
    Uses the exact standalone INSURED heading.
    """

    lines = normalize_lines(text)

    return collect_lines_between(
        lines,
        "INSURED",
        [
            "CONTACT",
            "INSURER(S) AFFORDING COVERAGE",
        ],
        max_lines=8
    )


def extract_acord_producer(text):
    """
    Uses the exact standalone PRODUCER heading.
    """

    lines = normalize_lines(text)

    return collect_lines_between(
        lines,
        "PRODUCER",
        ["INSURED"],
        max_lines=10
    )


def extract_acord_insurers(text):
    """
    Extracts insurer names while requiring actual INSURER A-F labels.
    """

    lines = normalize_lines(text)
    insurers = {}

    for index, line in enumerate(lines):
        match = re.fullmatch(
            r"INSURER\s+([A-F])\s*:?\s*(.*)",
            line,
            re.IGNORECASE
        )

        if not match:
            continue

        letter = match.group(1).lower()
        inline_value = clean_value(match.group(2))

        carrier = inline_value

        if (
            not carrier
            and index + 1 < len(lines)
        ):
            next_line = lines[index + 1]

            # Ignore NAIC codes
            if next_line.isdigit():
                carrier = None

            # Ignore the next INSURER label
            elif next_line.upper().startswith("INSURER"):
                carrier = None

            else:
                carrier = clean_value(next_line)

            if carrier:

                invalid_values = {
                    "COVERAGES",
                    "CERTIFICATE NUMBER",
                    "REVISION NUMBER"
                }

                # Ignore insurer labels
                if carrier.upper().startswith("INSURER"):
                    continue

                # Ignore section headers
                if carrier.upper() in invalid_values:
                    continue

                insurers[f"insurer_{letter}"] = carrier

    return insurers


def extract_acord_certificate_holder(text):
    """
    Tries to extract the certificate-holder block conservatively.

    If Azure's reading order does not place the address after the
    CERTIFICATE HOLDER heading, this function returns None rather
    than returning most of the page incorrectly.
    """

    lines = normalize_lines(text)

    holder_index = find_exact_line(
        lines,
        "CERTIFICATE HOLDER"
    )

    if holder_index is None:
        return None

    values = []

    for line in lines[
        holder_index + 1:
        holder_index + 8
    ]:
        normalized = normalize_label(line)

        if normalized in {
            normalize_label("CANCELLATION"),
            normalize_label("AUTHORIZED REPRESENTATIVE"),
        }:
            break

        if not is_known_label(line):
            values.append(line)

    holder = clean_value("\n".join(values))

    # Avoid returning cancellation language as the holder.
    if holder and (
        "SHOULD ANY OF THE ABOVE" in holder.upper()
        or "POLICIES BE CANCELLED" in holder.upper()
    ):
        return None

    return holder


def extract_acord_coverages(text):
    lines = normalize_lines(text)

    gl_section = get_section(
        lines,
        "COMMERCIAL GENERAL LIABILITY",
        [
            "AUTOMOBILE LIABILITY",
            "UMBRELLA LIAB",
            "WORKERS COMPENSATION",
            "POLLUTION LIABILITY",
        ]
    )

    auto_section = get_section(
        lines,
        "AUTOMOBILE LIABILITY",
        [
            "UMBRELLA LIAB",
            "EXCESS LIAB",
            "WORKERS COMPENSATION",
            "POLLUTION LIABILITY",
        ]
    )

    umbrella_section = get_section(
        lines,
        "UMBRELLA LIAB",
        [
            "WORKERS COMPENSATION",
            "POLLUTION LIABILITY",
            "PROFESSIONAL LIABILITY",
        ]
    )

    workers_comp_section = get_section(
        lines,
        "WORKERS COMPENSATION",
        [
            "POLLUTION LIABILITY",
            "PROFESSIONAL LIABILITY",
            "DESCRIPTION OF OPERATIONS",
        ]
    )

    gl_dates = find_date_pair_in_section(gl_section)
    auto_dates = find_date_pair_in_section(auto_section)
    umbrella_dates = find_date_pair_in_section(
        umbrella_section
    )
    wc_dates = find_date_pair_in_section(
        workers_comp_section
    )

    return {
        "general_liability": {
            "policy_number":
                find_policy_number_in_section(gl_section),
            "effective_date":
                gl_dates["effective_date"],
            "expiration_date":
                gl_dates["expiration_date"],
            "each_occurrence":
                find_first_money_after_label(
                    gl_section,
                    "EACH OCCURRENCE",
                    search_distance=8
                ),
            "general_aggregate":
                find_first_money_after_label(
                    gl_section,
                    "GENERAL AGGREGATE",
                    search_distance=4
                ),
            "products_completed_operations":
                find_first_money_after_label(
                    gl_section,
                    "PRODUCTS - COMP/OP AGG",
                    search_distance=4
                ),
        },

        "automobile_liability": {
            "policy_number":
                find_policy_number_in_section(auto_section),
            "effective_date":
                auto_dates["effective_date"],
            "expiration_date":
                auto_dates["expiration_date"],
            "combined_single_limit":
                find_first_money_after_label(
                    auto_section,
                    "(EA ACCIDENT)",
                    search_distance=5
                ),
        },

        "umbrella_excess": {
            "policy_number":
                find_policy_number_in_section(
                    umbrella_section
                ),
            "effective_date":
                umbrella_dates["effective_date"],
            "expiration_date":
                umbrella_dates["expiration_date"],
            "each_occurrence":
                find_first_money_after_label(
                    umbrella_section,
                    "EACH OCCURRENCE",
                    search_distance=4
                ),
            "aggregate":
                find_first_money_after_label(
                    umbrella_section,
                    "AGGREGATE",
                    search_distance=4
                ),
        },

        "workers_compensation": {
            "policy_number":
                find_policy_number_in_section(
                    workers_comp_section
                ),
            "effective_date":
                wc_dates["effective_date"],
            "expiration_date":
                wc_dates["expiration_date"],
            "each_accident":
                find_first_money_after_label(
                    workers_comp_section,
                    "E.L. EACH ACCIDENT",
                    search_distance=4
                ),
            "disease_each_employee":
                find_first_money_after_label(
                    workers_comp_section,
                    "E.L. DISEASE - EA EMPLOYEE",
                    search_distance=4
                ),
            "disease_policy_limit":
                find_first_money_after_label(
                    workers_comp_section,
                    "E.L. DISEASE - POLICY LIMIT",
                    search_distance=4
                ),
        },
    }


def build_acord25_schema(text, evidence_tags=None):
    return {
        "document_type": "ACORD_25",
        "evidence_tags": evidence_tags or [],
        "named_insured":
            extract_acord_named_insured(text),
        "producer":
            extract_acord_producer(text),
        "insurers":
            extract_acord_insurers(text),
        "certificate_holder":
            extract_acord_certificate_holder(text),
        "coverages":
            extract_acord_coverages(text),
    }


# =========================================================
# ACORD 101 PLACEHOLDER
# =========================================================

def build_acord101_schema(text, evidence_tags=None):
    return {
        "document_type": "ACORD_101",
        "evidence_tags": evidence_tags or [],
        "additional_remarks": clean_value(text),
    }


# =========================================================
# ROUTER
# =========================================================

def build_document_schema(
    document_type,
    text,
    evidence_tags=None
):
    if document_type == "ACORD_25":
        return build_acord25_schema(
            text,
            evidence_tags
        )

    if document_type == "ACORD_101":
        return build_acord101_schema(
            text,
            evidence_tags
        )

    if document_type == "ENDORSEMENT":
        return build_endorsement_schema(
            text,
            evidence_tags
        )

    return {
        "document_type": document_type,
        "evidence_tags": evidence_tags or [],
        "raw_text": clean_value(text),
    }