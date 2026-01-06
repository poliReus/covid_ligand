#!/bin/bash
#SBATCH --job-name=BioDock_HPC
#SBATCH --nodes=2
#SBATCH --ntasks-per-node=4
#SBATCH --cpus-per-task=1
#SBATCH --time=01:00:00
#SBATCH --output=logs/docking_%j.log

module load openmpi
module load python/3.10

# Esecuzione della pipeline distribuita su più nodi
mpirun python3 run_pipeline.py