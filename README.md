# Battery Health Analysis

A portfolio project exploring whether battery aging measurements can be used to
predict remaining useful life (RUL) using NASA's Battery Data Set.

## Python environment

Create and activate the project virtual environment in PowerShell, then install the listed dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Archive handling uses the Python standard library, SciPy inspects MATLAB files, and pytest runs the tests. Run the tests with:

```powershell
python -m pytest
```

## Data source

The dataset archive is available from the [NASA Prognostics Center of Excellence data repository](https://phm-datasets.s3.amazonaws.com/NASA/5.+Battery+Data+Set.zip).

The local archive is expected at `data/5.+Battery+Data+Set.zip`. If it is missing, the pipeline downloads it from the source link above. The extraction pipeline writes the outer archive to `data/nasa_battery/`, then extracts each nested ZIP into `data/nasa_battery/extracted/<archive-name>/`. It leaves source archives unchanged and skips a bundle when all of its expected files are already present. Keep downloaded source data unchanged; document any processed data separately so results can be traced back to the source. Before redistributing the archive or derived data, check the dataset's terms and attribution requirements.

The outer archive contains six nested ZIP bundles under `data/nasa_battery/5. Battery Data Set/`. Their listings include MATLAB `.mat` files and README text files. Battery records `B0025.mat` through `B0028.mat` appear in both `BatteryAgingARC_25_26_27_28_P1.zip` and `BatteryAgingARC_25-44.zip`; avoid extracting both bundles into the same destination until duplicate handling is decided.

From the repository root, run the extraction pipeline with:

```powershell
python data_loading.py
```

Validate the extracted MAT files against their associated bundle README files with:

```powershell
python validate_dataset.py
```

To inspect the top-level variables in a MAT file from the first bundle:

```powershell
python -c "from pathlib import Path; from data_loading import inspect_mat_file; print(inspect_mat_file(Path('data/nasa_battery/extracted/1. BatteryAgingARC-FY08Q4/B0005.mat')))"
```

The four MAT files in the first bundle each contain one battery-named top-level variable with shape `(1, 1)` and MATLAB class `struct`.

Use `load_mat_file` to load a MAT file's variables into simplified Python dictionaries, lists, and NumPy arrays:

```python
from pathlib import Path

from data_loading import load_mat_file

battery = load_mat_file(
	Path("data/nasa_battery/extracted/1. BatteryAgingARC-FY08Q4/B0005.mat")
)["B0005"]
cycles = battery["cycle"]
```

The `B0005` file contains 616 cycles: 170 charge, 168 discharge, and 278 impedance cycles. The `data` fields differ by operation. For example, the loaded discharge records use `Current_load` and `Voltage_load`, while the README documents `Current_charge` and `Voltage_charge`.

Compare a MAT file with the README beside it:

```python
from pathlib import Path

from data_loading import compare_mat_file_to_readme

bundle = Path("data/nasa_battery/extracted/1. BatteryAgingARC-FY08Q4")
issues = compare_mat_file_to_readme(bundle / "B0005.mat", bundle / "README.txt")
for issue in issues:
	print(issue)
```

For `B0005.mat`, the checker also finds an impedance field capitalization difference: the data uses `Rectified_Impedance`, while the README documents `Rectified_impedance`. These are reported for review; the checker does not alter source data or documentation.

## Proposed plan

1. Inspect the archive and document its files, structure, and measurement fields.
2. Verify the dataset's stated end-of-life criterion; define how RUL will be measured
	before creating prediction targets.
3. Build and test small, reusable data-loading and cycle-feature functions, adding
	Python type hints as we go.
4. Explore aging trends, then establish a simple RUL baseline.
5. Evaluate by holding out complete battery cells so cycles from the same cell do
	not appear in both training and test data.
6. Document assumptions, limitations, and reproducible steps for the portfolio.

## Initial project questions

- What end-of-life threshold does the source define, and is it suitable for this RUL task?
- Which cells, measurements, and error metrics are appropriate? Decide after inspecting the archive and target definition.
- Should exploration begin in a notebook, or directly in Python modules with tests?

## Project structure

```text
data/                       Ignored source archives and extracted datasets
.venv/                      Ignored project virtual environment
data_loading.py             ZIP extraction, MAT inspection, and README comparison
validate_dataset.py         Dataset-level README validation runner
requirements.txt            Python dependencies
tests/test_data_loading.py  Pytest tests for the extraction pipeline
```

The broader code and analysis structure will be chosen after the first data-inspection step.

## Status

The outer archive and all six nested bundles have been extracted into separate folders. Top-level metadata has been inspected for the four MAT files in the first bundle, and cycle structure has been explored for `B0005`. No RUL target definition or model performance claims have been established.