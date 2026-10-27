from pathlib import Path

from classifiers.document_classifier import (
    get_page_text,
    classify_page
)

from extractors.extraction_mapper import (
    build_document_schema
)


SUPPORTED_EXTENSIONS = {
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg",
    ".tif",
    ".tiff"
}


def find_documents(input_folder):
    """
    Finds supported files recursively.

    This allows carrier folders to contain nested folders
    without requiring a known number of files.
    """

    input_folder = Path(input_folder)

    return sorted([
        file_path
        for file_path in input_folder.rglob("*")
        if (
            file_path.is_file()
            and file_path.suffix.lower()
            in SUPPORTED_EXTENSIONS
        )
    ])


def process_file(
    file_path,
    analyze_document_function
):
    """
    Processes one file and returns one record per page.
    """

    result = analyze_document_function(file_path)

    page_records = []

    for page in result.pages:

        page_text = get_page_text(page)

        classification = classify_page(
            page_text
        )

        schema = build_document_schema(
            classification["page_type"],
            page_text,
            classification["evidence_tags"]
        )

        page_records.append({
            "source_file": file_path.name,
            "source_path": str(file_path),
            "page_number": page.page_number,
            "page_type":
                classification["page_type"],
            "evidence_tags":
                classification["evidence_tags"],
            "schema": schema,
            "text_preview": page_text[:200]
        })

    return page_records


def process_intake_folder(
    input_folder,
    analyze_document_function
):
    """
    Processes every supported file in one folder,
    regardless of file count or number of pages.
    """

    files = find_documents(input_folder)

    all_page_records = []
    file_errors = []

    for file_path in files:

        print(
            f"\nAnalyzing file: "
            f"{file_path.name}"
        )

        try:
            page_records = process_file(
                file_path,
                analyze_document_function
            )

            all_page_records.extend(
                page_records
            )

        except Exception as error:

            file_errors.append({
                "source_file": file_path.name,
                "source_path": str(file_path),
                "error": str(error)
            })

            print(
                f"Could not process "
                f"{file_path.name}: {error}"
            )

    return {
        "input_folder": str(input_folder),
        "files_found": len(files),
        "page_records": all_page_records,
        "file_errors": file_errors
    }
