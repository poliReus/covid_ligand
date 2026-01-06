import os
import subprocess
import csv
import sys
import time
from multiprocessing import Pool, cpu_count

# --- CONFIGURAZIONE ---
INPUT_CSV = "data/test.csv" # Assicurati che il nome corrisponda al tuo CSV
OUTPUT_DIR = "ligands"
TIMEOUT_SECONDS = 10

# Creiamo la cartella se non esiste
os.makedirs(OUTPUT_DIR, exist_ok=True)

def process_ligand(data):
    """
    Funzione worker eseguita da ogni core.
    Riceve una tupla (name, smiles).
    """
    name, smiles = data
    
    # Pulizia nome file
    safe_name = "".join([c for c in name if c.isalnum() or c in ('-','_')])
    out_file = os.path.join(OUTPUT_DIR, f"{safe_name}.pdbqt")
    
    # Cache check: se esiste già, saltiamo (utile se rilanci lo script)
    if os.path.exists(out_file) and os.path.getsize(out_file) > 0:
        return f"SKIP: {name}"

    # Comando OpenBabel
    cmd = [
        "obabel", f"-:{smiles}", "-O", out_file,
        "--gen3d", "-p", "7.4", "--partialcharge"
    ]
    
    try:
        subprocess.run(
            cmd, 
            check=True, 
            stderr=subprocess.DEVNULL, # Silenzia i warning chimici
            timeout=TIMEOUT_SECONDS
        )
        return "." # Successo (punto per la progress bar)
    except subprocess.TimeoutExpired:
        return "T" # Timeout
    except Exception:
        return "E" # Errore

def main():
    if not os.path.exists(INPUT_CSV):
        print(f"Errore: Non trovo {INPUT_CSV}")
        return

    # 1. Caricamento dati in memoria
    print(f"Lettura di {INPUT_CSV}...")
    tasks = []
    with open(INPUT_CSV, 'r') as f:
        reader = csv.reader(f)
        header = next(reader, None) # Salta header
        for row in reader:
            if len(row) >= 2:
                tasks.append((row[0].strip(), row[1].strip()))
    
    total_mols = len(tasks)
    num_cores = cpu_count()
    print(f"Avvio generazione su {num_cores} core per {total_mols} molecole.")
    
    start_time = time.time()
    
    # 2. Creazione del Pool di Processi
    # Usa tutti i core disponibili
    with Pool(processes=num_cores) as pool:
        # pool.imap_unordered è più veloce di map se non ci importa l'ordine dei risultati
        for result in pool.imap_unordered(process_ligand, tasks):
            sys.stdout.write(result)
            sys.stdout.flush()
            
    end_time = time.time()
    duration = end_time - start_time
    
    print(f"\n\n✅ Completato in {duration:.2f} secondi.")
    print(f"Rate: {total_mols/duration:.2f} molecole/secondo")

if __name__ == "__main__":
    main()