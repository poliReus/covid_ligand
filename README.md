# HPC Bio Docking Pipeline

End-to-end virtual screening pipeline for SARS-CoV-2 Mpro (6LU7) using AutoDock Vina. It builds ligands from SMILES, runs MPI-distributed docking, and generates interactive HTML reports plus a CSV summary.

## Architecture Overview

1) Input preparation
- `data/test.csv` provides molecule name and SMILES.
- `data/receptor.pdbqt` is the prepared target receptor.

2) Ligand generation (`gen_ligands.py`)
- Converts each SMILES into `ligands/*.pdbqt` with OpenBabel.
- Runs in parallel using all local CPU cores.
- Uses 3D generation (`--gen3d`), pH 7.4 (`-p 7.4`), and partial charges.

3) MPI docking (`mpi_docking.py`)
- Splits ligands across MPI ranks in round-robin.
- Each rank calls AutoDock Vina with a fixed grid box:
  - Center: `(-10.6, 12.6, 68.8)`
  - Size: `(30.0, 30.0, 30.0)`
- Outputs are saved as `results/*_out.pdbqt`.
- The master rank gathers results, sorts by best affinity, and prints a console report.

4) Reporting (`run_pipeline.py`)
- Parses docking outputs to extract affinity and calculate ligand efficiency (LE):
  - LE = -Affinity / (# heavy atoms)
- Generates one interactive NGLView HTML per ligand in `views/`.
- Writes a summary table to `final_summary.csv`.

5) Orchestration and execution
- `run_pipeline.py` runs the full workflow locally.
- `submit_job.sh` runs the workflow on SLURM clusters.
- `dockerfile` provides a containerized environment.

## Repository Layout

```
project_1/
  data/                    # input data and receptor files
  ligands/                 # generated ligands (gitignored)
  results/                 # docking outputs (gitignored)
  views/                   # HTML reports (gitignored)
  src/
    vina_1.2.7_mac_aarch64 # optional local Vina binary (gitignored)
  gen_ligands.py
  mpi_docking.py
  run_pipeline.py
  check.py
  submit_job.sh
  dockerfile
  requirements.txt
  final_summary.csv        # generated output (gitignored)
```

## Key Configuration

`run_pipeline.py`
- `INPUT_CSV`: input molecule list
- `NUM_CORES`: MPI ranks
- `EXHAUSTIVENESS`: shown in reports

`gen_ligands.py`
- `INPUT_CSV`: input molecule list
- `TIMEOUT_SECONDS`: OpenBabel timeout per ligand

`mpi_docking.py`
- `RECEPTOR`: receptor path
- `CENTER_*`, `SIZE_*`: grid box coordinates
- `--cpu`: threads per Vina process
- `--exhaustiveness`: Vina search depth
- `VINA_PATH`: resolved in this order:
  1) `vina` on PATH
  2) `VINA_EXECUTABLE` env var
  3) `./src/vina_1.2.7_mac_aarch64`

Note: `EXHAUSTIVENESS` in `run_pipeline.py` is not passed into `mpi_docking.py`, so docking uses the value set in `mpi_docking.py`. Keep them aligned when tuning.

## Input CSV Format

```
name,smiles
Aspirina,CC(=O)OC1=CC=CC=C1C(=O)O
```

## Local Run

```
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export VINA_EXECUTABLE=/path/to/vina   # optional
python3 run_pipeline.py
```

## Run Only the Docking Step (MPI)

```
mpirun -n 8 python3 mpi_docking.py
```

## SLURM (HPC)

```
mkdir -p logs
sbatch submit_job.sh
```

Tip: Align `--cpus-per-task` in `submit_job.sh` with `--cpu` in `mpi_docking.py` to avoid oversubscription.

## Docker

```
docker build -t hpc-bio .
docker run --rm -v "$PWD":/app hpc-bio
```

## Outputs

- `ligands/*.pdbqt` generated from SMILES by OpenBabel
- `results/*_out.pdbqt` AutoDock Vina docking results
- `views/*.html` interactive reports (protein + ligand)
- `final_summary.csv` CSV with affinity and ligand efficiency

## Local Test Results (Sample Run)

The following results are from `final_summary.csv` generated locally using the default pipeline and `data/test.csv`:

| Molecule     | Affinity (kcal/mol) | Ligand Efficiency |
|--------------|---------------------:|------------------:|
| Ritonavir    | -5.499               | 0.012             |
| Ibuprofene   | -4.083               | 0.030             |
| Aspirina     | -3.813               | 0.033             |
| Nirmatrelvir | -5.162               | 0.016             |
| Remdesivir   | -4.381               | 0.013             |

Interpretation notes:
- More negative affinity indicates stronger predicted binding.
- Ligand efficiency normalizes affinity by heavy-atom count.
- These values are specific to the prepared receptor, grid box, and default Vina settings. Results may vary with different preprocessing or parameters.

## Notes and Limitations

- This is a screening workflow, not a validated experimental pipeline.
- Docking scores are heuristic; use them for ranking, not absolute binding energies.
- The MPI workflow assumes ligands exist in `ligands/`; run `gen_ligands.py` first or run `run_pipeline.py` for full orchestration.
