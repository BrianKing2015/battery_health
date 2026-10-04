from pathlib import Path
from pathlib import PurePosixPath, PureWindowsPath
import re
from scipy.io import loadmat, whosmat
from urllib.request import urlretrieve
from zipfile import ZipFile

SOURCE_ARCHIVE_URL = (
    "https://phm-datasets.s3.amazonaws.com/NASA/5.+Battery+Data+Set.zip"
)


def ensure_source_archive(archive_path: Path) -> Path:
    """Return the source archive, downloading it when it is missing."""
    if archive_path.is_file():
        return archive_path

    archive_path.parent.mkdir(parents=True, exist_ok=True)
    urlretrieve(SOURCE_ARCHIVE_URL, archive_path)
    return archive_path


def inspect_mat_file(mat_path: Path) -> list[tuple[str, tuple[int, ...], str]]:
    """List top-level MATLAB variables, their shapes, and MATLAB classes."""
    return whosmat(mat_path)


def load_mat_file(mat_path: Path) -> dict[str, object]:
    """Load MATLAB variables as simplified Python structures and arrays."""
    contents = loadmat(mat_path, simplify_cells=True)
    return {
        name: value
        for name, value in contents.items()
        if not name.startswith("__")
    }


def compare_mat_file_to_readme(mat_path: Path, readme_path: Path) -> list[str]:
    """Report differences between a MAT file and its bundle README fields."""
    readme_text = readme_path.read_text(encoding="utf-8")
    issues = []

    files_match = re.search(
        r"(?ms)^Files:\s*(.*?)(?=^Data Structure:|\Z)", readme_text
    )
    if files_match is None:
        return ["README is missing its Files section"]

    documented_files = set(re.findall(r"\bB\d+\.mat\b", files_match.group(1)))
    if mat_path.name not in documented_files:
        issues.append(f"{mat_path.name} is not listed in the README Files section")

    data_structure_match = re.search(r"(?ms)^Data Structure:\s*(.*)\Z", readme_text)
    if data_structure_match is None:
        return issues + ["README is missing its Data Structure section"]

    operation_pattern = re.compile(
        r"^[ \t]*for[ \t]+(?P<operation>charge|discharge|impedance)"
        r"[ \t]+the fields are:[ \t]*\r?\n(?P<body>.*?)"
        r"(?=^[ \t]*for[ \t]+(?:charge|discharge|impedance)"
        r"[ \t]+the fields are:|\Z)",
        re.IGNORECASE | re.MULTILINE | re.DOTALL,
    )
    documented_fields = {
        match.group("operation").lower(): set(
            re.findall(r"^[ \t]+([A-Za-z_]\w*):", match.group("body"), re.MULTILINE)
        )
        for match in operation_pattern.finditer(data_structure_match.group(1))
    }

    loaded_variables = load_mat_file(mat_path)
    battery = loaded_variables.get(mat_path.stem)
    if not isinstance(battery, dict) or "cycle" not in battery:
        return issues + [f"MAT file does not contain a {mat_path.stem} cycle struct"]

    cycle_value = battery["cycle"]
    cycles = cycle_value if isinstance(cycle_value, list) else [cycle_value]
    actual_fields: dict[str, set[str]] = {}
    for cycle in cycles:
        if not isinstance(cycle, dict):
            continue
        operation = cycle.get("type")
        data = cycle.get("data")
        if isinstance(operation, str) and isinstance(data, dict):
            actual_fields.setdefault(operation.lower(), set()).update(data)

    for operation, expected_fields in documented_fields.items():
        fields = actual_fields.get(operation, set())
        missing_fields = sorted(expected_fields - fields)
        extra_fields = sorted(fields - expected_fields)
        if missing_fields:
            issues.append(
                f"Documented {operation} fields missing from data: "
                f"{', '.join(missing_fields)}"
            )
        if extra_fields:
            issues.append(
                f"Data has undocumented {operation} fields: {', '.join(extra_fields)}"
            )

    return issues


def extract_zip_archive(archive_path: Path, destination: Path) -> None:
    """Extract a ZIP archive unless all of its files are already present."""
    with ZipFile(archive_path) as archive:
        for member in archive.infolist():
            posix_path = PurePosixPath(member.filename)
            windows_path = PureWindowsPath(member.filename)
            if (
                posix_path.is_absolute()
                or windows_path.is_absolute()
                or windows_path.drive
                or ".." in posix_path.parts
                or ".." in windows_path.parts
            ):
                raise ValueError(f"Unsafe path in ZIP archive: {member.filename}")

        expected_files = [
            member.filename
            for member in archive.infolist()
            if not member.is_dir()
        ]
        if expected_files and all(
            (destination / filename).is_file() for filename in expected_files
        ):
            return

        destination.mkdir(parents=True, exist_ok=True)
        archive.extractall(destination)


def extract_zip_archives(
    archive_directory: Path, destination: Path
) -> list[Path]:
    """Extract each ZIP into a subdirectory named after its archive."""
    archive_paths = sorted(archive_directory.glob("*.zip"))
    if not archive_paths:
        raise FileNotFoundError(f"No ZIP archives found in {archive_directory}")

    extracted_directories = []
    for archive_path in archive_paths:
        archive_destination = destination / archive_path.stem
        extract_zip_archive(archive_path, archive_destination)
        extracted_directories.append(archive_destination)

    return extracted_directories


def run_data_pipeline(source_archive: Path, data_directory: Path) -> list[Path]:
    """Extract the source archive and its nested battery-data ZIP bundles."""
    source_archive = ensure_source_archive(source_archive)
    outer_destination = data_directory / "nasa_battery"
    extract_zip_archive(source_archive, outer_destination)

    archive_directory = outer_destination / "5. Battery Data Set"
    bundle_destination = outer_destination / "extracted"
    return extract_zip_archives(archive_directory, bundle_destination)


if __name__ == "__main__":
    data_directory = Path(__file__).resolve().parent / "data"
    source_archive = data_directory / "5.+Battery+Data+Set.zip"
    for extracted_directory in run_data_pipeline(source_archive, data_directory):
        print(f"Available: {extracted_directory}")