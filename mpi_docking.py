from mpi4py import MPI
import glob
import subprocess
import os
import time
import sys
import shutil

VINA_PATH = shutil.which("vina") or os.getenv("VINA_EXECUTABLE") or "./src/vina_1.2.7_mac_aarch64"

RECEPTOR = "data/receptor.pdbqt"
OUTPUT_DIR = "results"


# Grid Box (Coordinate del sito attivo di 6LU7)
CENTER_X, CENTER_Y, CENTER_Z = -10.6, 12.6, 68.8
SIZE_X, SIZE_Y, SIZE_Z = 30.0, 30.0, 30.0

# --- MPI SETUP ---
comm = MPI.COMM_WORLD
rank = comm.Get_rank()
size = comm.Get_size()

def run_docking(ligand_path):
    ligand_name = os.path.basename(ligand_path).replace(".pdbqt", "")
    out_file = os.path.join(OUTPUT_DIR, f"{ligand_name}_out.pdbqt")
    
    cmd = [
        VINA_PATH,
        "--receptor", RECEPTOR,
        "--ligand", ligand_path,
        "--center_x", str(CENTER_X), "--center_y", str(CENTER_Y), "--center_z", str(CENTER_Z),
        "--size_x", str(SIZE_X), "--size_y", str(SIZE_Y), "--size_z", str(SIZE_Z),
        "--out", out_file,
        "--cpu", "8", # Fondamentale: usiamo 1 thread per processo MPI
        "--exhaustiveness", "32" # Accuratezza (8 è default, bassa per test veloce)
    ]
    
    start = time.time()
    try:
        # Esegue Vina
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        # Parsing dell'output per trovare l'energia di legame (Affinity)
        best_affinity = 0.0
        found = False
        for line in result.stdout.splitlines():
            if line.strip().startswith("1"): # La prima modalità è la migliore
                parts = line.split()
                if len(parts) >= 2:
                    best_affinity = float(parts[1])
                    found = True
                    break
        
        duration = time.time() - start
        if found:
            return (ligand_name, best_affinity, duration)
        else:
            return (ligand_name, 999.9, duration) # Docking fallito
            
    except Exception as e:
        return (ligand_name, 999.9, 0.0)

# --- MAIN FLOW ---

if rank == 0:
    # IL MASTER
    print(f"🚀 Avvio simulazione MPI su {size} core.")
    print(f"Target: {RECEPTOR}")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # 1. Trova tutti i ligandi
    ligands = glob.glob("ligands/*.pdbqt")
    
    # Moltiplichiamo la lista per simulare un carico HPC se abbiamo pochi file
    # (Commenta questa riga se hai centinaia di ligandi veri)
    #ligands = ligands * 4
    
    total_tasks = len(ligands)
    print(f"Task totali da processare: {total_tasks}")
    
    # 2. Distribuzione Round-Robin semplice
    # Assegniamo i file ai worker
    tasks_for_workers = [[] for _ in range(size)]
    for i, lig in enumerate(ligands):
        worker_id = i % size
        tasks_for_workers[worker_id].append(lig)
        
else:
    tasks_for_workers = None

# Scatter: invia le liste personalizzate a ogni core
my_tasks = comm.scatter(tasks_for_workers, root=0)

# Worker: Esegue il docking sui propri task
my_results = []
print(f"[Core {rank}] Ricevuti {len(my_tasks)} task.")

for lig in my_tasks:
    res = run_docking(lig)
    my_results.append(res)
    # Feedback visivo minimo
    print(f"[Core {rank}] Completato {res[0]} -> {res[1]} kcal/mol")

# Gather: Il Master raccoglie tutto
all_results = comm.gather(my_results, root=0)

if rank == 0:
    print("\n--- 🏁 REPORT FINALE 🏁 ---")
    flat_results = [item for sublist in all_results for item in sublist]
    
    # Ordina per affinità (più negativo = legame più forte)
    flat_results.sort(key=lambda x: x[1])
    
    print(f"{'MOLECOLA':<15} | {'ENERGIA (kcal/mol)':<20} | {'TEMPO (s)':<10}")
    print("-" * 55)
    for name, score, t in flat_results:
        print(f"{name:<15} | {score:<20} | {t:.2f}")
        
    print(f"\n✅ Risultati salvati nella cartella '{OUTPUT_DIR}'")