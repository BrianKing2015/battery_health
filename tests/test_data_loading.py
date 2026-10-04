import io
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pytest
from scipy.io import savemat

import data_loading
from data_loading import (
    extract_zip_archive,
    extract_zip_archives,
    inspect_mat_file,
    load_mat_file,
    compare_mat_file_to_readme,
    run_data_pipeline,
)


def test_inspect_mat_file_reports_top_level_metadata(tmp_path: Path) -> None:
    mat_path = tmp_path / "B0005.mat"
    savemat(mat_path, {"B0005": {"cycle": [[1, 2]]}})

    variables = inspect_mat_file(mat_path)

    assert variables == [("B0005", (1, 1), "struct")]


def test_load_mat_file_preserves_cycle_records(tmp_path: Path) -> None:
    mat_path = tmp_path / "B0005.mat"
    savemat(
        mat_path,
        {
            "B0005": {
                "cycle": [
                    {
                        "type": "charge",
                        "data": {"Voltage_measured": [3.4, 3.5]},
                    },
                    {
                        "type": "discharge",
                        "data": {"Capacity": 1.8},
                    },
                ]
            }
        },
    )

    loaded = load_mat_file(mat_path)

    assert set(loaded) == {"B0005"}
    battery = loaded["B0005"]
    assert isinstance(battery, dict)
    cycles = battery["cycle"]
    assert isinstance(cycles, list)
    assert [cycle["type"] for cycle in cycles] == ["charge", "discharge"]
    assert cycles[0]["data"]["Voltage_measured"].tolist() == [3.4, 3.5]
    assert cycles[1]["data"]["Capacity"] == 1.8


def test_compare_mat_file_to_readme_reports_field_mismatches(
    tmp_path: Path,
) -> None:
    mat_path = tmp_path / "B0005.mat"
    readme_path = tmp_path / "README.txt"
    savemat(
        mat_path,
        {
            "B0005": {
                "cycle": [
                    {
                        "type": "discharge",
                        "data": {"Capacity": 1.8, "Current_load": [2.0]},
                    }
                ]
            }
        },
    )
    readme_path.write_text(
        "Files:\nB0005.mat Data for Battery #5\n\n"
        "Data Structure:\n"
        "for discharge the fields are:\n"
        "    Capacity: Discharge capacity\n"
        "    Current_charge: Current measured at load\n",
        encoding="utf-8",
    )

    issues = compare_mat_file_to_readme(mat_path, readme_path)

    assert issues == [
        "Documented discharge fields missing from data: Current_charge",
        "Data has undocumented discharge fields: Current_load",
    ]


def test_compare_mat_file_to_readme_is_clean_when_fields_match(
    tmp_path: Path,
) -> None:
    mat_path = tmp_path / "B0005.mat"
    readme_path = tmp_path / "README.txt"
    savemat(
        mat_path,
        {
            "B0005": {
                "cycle": [
                    {
                        "type": "discharge",
                        "data": {"Capacity": 1.8, "Current_load": [2.0]},
                    }
                ]
            }
        },
    )
    readme_path.write_text(
        "Files:\nB0005.mat Data for Battery #5\n\n"
        "Data Structure:\n"
        "for discharge the fields are:\n"
        "    Capacity: Discharge capacity\n"
        "    Current_load: Current measured at load\n",
        encoding="utf-8",
    )

    issues = compare_mat_file_to_readme(mat_path, readme_path)

    assert issues == []


def test_missing_source_archive_is_downloaded(tmp_path: Path, monkeypatch) -> None:
    archive_path = tmp_path / "data" / "battery.zip"
    requested_urls = []

    def fake_urlretrieve(url: str, filename: str | Path) -> None:
        requested_urls.append(url)
        Path(filename).write_bytes(b"downloaded archive")

    monkeypatch.setattr(data_loading, "urlretrieve", fake_urlretrieve, raising=False)

    result = data_loading.ensure_source_archive(archive_path)

    assert result == archive_path
    assert archive_path.read_bytes() == b"downloaded archive"
    assert requested_urls == [
        "https://phm-datasets.s3.amazonaws.com/NASA/5.+Battery+Data+Set.zip"
    ]


def test_existing_source_archive_is_not_downloaded(
    tmp_path: Path, monkeypatch
) -> None:
    archive_path = tmp_path / "battery.zip"
    archive_path.write_bytes(b"existing archive")

    def fail_if_downloaded(url: str, filename: str | Path) -> None:
        raise AssertionError("The existing archive should not be downloaded again")

    monkeypatch.setattr(
        data_loading, "urlretrieve", fail_if_downloaded, raising=False
    )

    result = data_loading.ensure_source_archive(archive_path)

    assert result == archive_path
    assert archive_path.read_bytes() == b"existing archive"


def _write_zip(archive_path: Path, members: dict[str, bytes]) -> None:
    with ZipFile(archive_path, "w", compression=ZIP_DEFLATED) as archive:
        for member_name, content in members.items():
            archive.writestr(member_name, content)


def _zip_bytes(members: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with ZipFile(buffer, "w", compression=ZIP_DEFLATED) as archive:
        for member_name, content in members.items():
            archive.writestr(member_name, content)
    return buffer.getvalue()


def test_nested_archives_extract_to_separate_folders(tmp_path: Path) -> None:
    archive_directory = tmp_path / "archives"
    archive_directory.mkdir()
    _write_zip(archive_directory / "bundle_a.zip", {"B0001.mat": b"a"})
    _write_zip(archive_directory / "bundle_b.zip", {"B0001.mat": b"b"})

    extracted_directories = extract_zip_archives(
        archive_directory, tmp_path / "extracted"
    )

    assert extracted_directories == [
        tmp_path / "extracted" / "bundle_a",
        tmp_path / "extracted" / "bundle_b",
    ]
    assert (tmp_path / "extracted" / "bundle_a" / "B0001.mat").read_bytes() == b"a"
    assert (tmp_path / "extracted" / "bundle_b" / "B0001.mat").read_bytes() == b"b"


def test_complete_archive_is_not_extracted_again(tmp_path: Path) -> None:
    archive_path = tmp_path / "bundle.zip"
    destination = tmp_path / "bundle"
    _write_zip(archive_path, {"record.mat": b"original"})
    extract_zip_archive(archive_path, destination)

    record_path = destination / "record.mat"
    record_path.write_bytes(b"local change")
    extract_zip_archive(archive_path, destination)

    assert record_path.read_bytes() == b"local change"


def test_incomplete_archive_is_repaired(tmp_path: Path) -> None:
    archive_path = tmp_path / "bundle.zip"
    destination = tmp_path / "bundle"
    _write_zip(
        archive_path,
        {"first.mat": b"first", "second.mat": b"second"},
    )
    extract_zip_archive(archive_path, destination)
    (destination / "second.mat").unlink()

    extract_zip_archive(archive_path, destination)

    assert (destination / "second.mat").read_bytes() == b"second"


def test_unsafe_member_path_is_rejected(tmp_path: Path) -> None:
    archive_path = tmp_path / "unsafe.zip"
    _write_zip(archive_path, {"../outside.txt": b"unsafe"})

    with pytest.raises(ValueError, match="Unsafe path"):
        extract_zip_archive(archive_path, tmp_path / "destination")

    assert not (tmp_path / "outside.txt").exists()


def test_pipeline_extracts_outer_and_nested_archives(tmp_path: Path) -> None:
    data_directory = tmp_path / "data"
    data_directory.mkdir()
    source_archive = data_directory / "source.zip"
    nested_archive = _zip_bytes({"B0005.mat": b"sample"})
    _write_zip(
        source_archive,
        {"5. Battery Data Set/bundle.zip": nested_archive},
    )

    extracted_directories = run_data_pipeline(source_archive, data_directory)

    expected_directory = (
        data_directory / "nasa_battery" / "extracted" / "bundle"
    )
    assert extracted_directories == [expected_directory]
    assert (expected_directory / "B0005.mat").read_bytes() == b"sample"