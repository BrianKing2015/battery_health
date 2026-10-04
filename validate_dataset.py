import re
from pathlib import Path

from data_loading import compare_mat_file_to_readme


def _documented_mat_files(readme_path: Path) -> set[str]:
    readme_text = readme_path.read_text(encoding="utf-8")
    files_match = re.search(
        r"(?ms)^Files:\s*(.*?)(?=^Data Structure:|\Z)", readme_text
    )
    if files_match is None:
        return set()
    return set(re.findall(r"\bB\d+\.mat\b", files_match.group(1)))


def validate_dataset(extracted_root: Path) -> list[str]:
    """Compare each extracted MAT file with the README that documents it."""
    findings = []
    mat_paths = sorted(extracted_root.rglob("*.mat"))

    if not mat_paths:
        return [f"No MAT files found under {extracted_root}"]

    for mat_path in mat_paths:
        relative_path = mat_path.relative_to(extracted_root).as_posix()
        readme_paths = sorted(mat_path.parent.glob("README*.txt"))
        matching_readmes = [
            readme_path
            for readme_path in readme_paths
            if mat_path.name in _documented_mat_files(readme_path)
        ]

        if not matching_readmes:
            findings.append(f"{relative_path}: no README lists this MAT file")
            continue
        if len(matching_readmes) > 1:
            names = ", ".join(readme.name for readme in matching_readmes)
            findings.append(
                f"{relative_path}: listed by multiple README files: {names}"
            )
            continue

        for issue in compare_mat_file_to_readme(mat_path, matching_readmes[0]):
            findings.append(f"{relative_path}: {issue}")

    return findings


def main() -> None:
    extracted_root = (
        Path(__file__).resolve().parent / "data" / "nasa_battery" / "extracted"
    )
    findings = validate_dataset(extracted_root)

    if findings:
        print("Dataset validation findings:")
        for finding in findings:
            print(f"- {finding}")
    else:
        print("No dataset validation findings.")


if __name__ == "__main__":
    main()