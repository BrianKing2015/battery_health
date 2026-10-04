from pathlib import Path

from scipy.io import savemat

from validate_dataset import validate_dataset


def test_validate_dataset_matches_each_mat_file_to_its_readme(
    tmp_path: Path,
) -> None:
    extracted_root = tmp_path / "extracted"
    bundle_directory = extracted_root / "bundle"
    bundle_directory.mkdir(parents=True)

    savemat(
        bundle_directory / "B0005.mat",
        {
            "B0005": {
                "cycle": [
                    {
                        "type": "charge",
                        "data": {"Voltage_measured": [3.5]},
                    }
                ]
            }
        },
    )
    savemat(
        bundle_directory / "B0006.mat",
        {
            "B0006": {
                "cycle": [
                    {
                        "type": "discharge",
                        "data": {"Capacity": 1.8, "Current_load": [2.0]},
                    }
                ]
            }
        },
    )
    (bundle_directory / "README_charge.txt").write_text(
        "Files:\nB0005.mat Data for Battery #5\n\n"
        "Data Structure:\n"
        "for charge the fields are:\n"
        "    Voltage_measured: Battery voltage\n",
        encoding="utf-8",
    )
    (bundle_directory / "README_discharge.txt").write_text(
        "Files:\nB0006.mat Data for Battery #6\n\n"
        "Data Structure:\n"
        "for discharge the fields are:\n"
        "    Capacity: Discharge capacity\n"
        "    Current_charge: Current measured at load\n",
        encoding="utf-8",
    )

    findings = validate_dataset(extracted_root)

    assert findings == [
        "bundle/B0006.mat: Documented discharge fields missing from data: "
        "Current_charge",
        "bundle/B0006.mat: Data has undocumented discharge fields: Current_load",
    ]