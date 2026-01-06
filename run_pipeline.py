import subprocess
import os
import sys
import time
import glob
import csv
import json
import nglview as nv

# --- CONFIGURAZIONE ---
INPUT_CSV = "data/test.csv"
RECEPTOR_PDBQT = "data/receptor.pdbqt"
RESULTS_DIR = "results"
VIEWS_DIR = "views"
NUM_CORES = 8  # Core per MPI
EXHAUSTIVENESS = 32  # Search depth per Vina

def run_command(cmd, description):
    """Esegue un comando di sistema e gestisce gli errori."""
    print(f"\n🚀 {description}...")
    try:
        subprocess.run(cmd, check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Errore durante {description}: {e}")
        return False

def get_vina_metrics(pdbqt_file):
    """
    Parsa il file PDBQT di output per estrarre l'affinità e 
    calcolare la Ligand Efficiency (LE).
    """
    affinity = None
    atom_count = 0
    try:
        with open(pdbqt_file, 'r') as f:
            for line in f:
                if "REMARK VINA RESULT:" in line:
                    parts = line.split()
                    affinity = float(parts[3])
                if line.startswith("ATOM") or line.startswith("HETATM"):
                    # Conta solo atomi pesanti (non idrogeni) per la LE
                    if " H  " not in line and " H" not in line[76:78]:
                        atom_count += 1
        
        # Ligand Efficiency = -Affinity / Number of Heavy Atoms
        le = round(-affinity / atom_count, 3) if affinity and atom_count > 0 else 0
        return affinity, le, atom_count
    except Exception:
        return "N/A", "N/A", 0

def generate_refined_reports():
    """Genera file HTML interattivi con metadati iniettati."""
    os.makedirs(VIEWS_DIR, exist_ok=True)
    out_files = glob.glob(os.path.join(RESULTS_DIR, "*_out.pdbqt"))
    
    summary_data = []
    pages_manifest = []
    print(f"📊 Generazione di {len(out_files)} report tecnici...")

    for f in out_files:
        name = os.path.basename(f).replace("_out.pdbqt", "")
        affinity, le, atoms = get_vina_metrics(f)
        summary_data.append([name, affinity, le])

        # Creazione vista NGLView
        view = nv.show_structure_file(RECEPTOR_PDBQT)
        view.add_component(f)
        view.clear_representations()
        
        # Styling: Proteina grigia e farmaco colorato
        view.add_representation('cartoon', selection='component 0', color='silver', opacity=0.7)
        view.add_representation('ball+stick', selection='component 1')
        view.center(selection='component 1')

        output_path = f"{VIEWS_DIR}/{name}.html"
        nv.write_html(output_path, [view])
        pages_manifest.append({"name": name, "file": output_path})
        
        # Iniezione HTML per i metadati (CSS floating panel)
        metadata_box = f"""
        <div style="position: absolute; top: 20px; left: 20px; background: rgba(255,255,255,0.9); 
                    padding: 20px; border-radius: 10px; font-family: 'Segoe UI', Tahoma, Geneva, sans-serif; 
                    border: 1px solid #333; box-shadow: 5px 5px 15px rgba(0,0,0,0.3); z-index: 1000;">
            <h2 style="margin-top:0; color: #2c3e50;">Analisi Docking: {name}</h2>
            <p><b>Target:</b> SARS-CoV-2 Mpro (6LU7)</p>
            <p><b>Binding Affinity:</b> <span style="color: #e74c3c; font-size: 1.3em; font-weight: bold;">{affinity} kcal/mol</span></p>
            <p><b>Ligand Efficiency:</b> {le} (kcal/mol/heavy-atom)</p>
            <p><b>Atomi Pesanti:</b> {atoms}</p>
            <hr>
            <p style="font-size: 0.85em; color: #7f8c8d;">
                Pipeline: HPC-Bio-Engineer v1.0<br>
                Engine: AutoDock Vina | Search Depth: {EXHAUSTIVENESS}
            </p>
        </div>
        """
        with open(output_path, 'a') as html_file:
            html_file.write(metadata_box)

    # Crea un file CSV di riepilogo finale
    with open("final_summary.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Molecola", "Affinity (kcal/mol)", "Ligand Efficiency"])
        writer.writerows(summary_data)

    manifest_payload = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "pages": pages_manifest
    }
    json_path = os.path.join(VIEWS_DIR, "manifest.json")
    with open(json_path, "w") as f:
        json.dump(manifest_payload, f, indent=2)
    js_path = os.path.join(VIEWS_DIR, "manifest.js")
    with open(js_path, "w") as f:
        f.write("window.VIEWS_MANIFEST = ")
        json.dump(manifest_payload, f, indent=2)
        f.write(";\n")

def main():
    start_total = time.time()
    print("=== 🧬 AVVIO PIPELINE BIO-HPC IN CORSO ===")

    # 1. Pulizia e Preparazione Ligandi
    if not run_command(["python3", "gen_ligands.py"], "Pre-processing Molecole (Multiprocessing)"):
        sys.exit(1)

    # 2. Docking Parallelo MPI
    # Nota: Assicurati che mpi_docking.py legga l'exhaustiveness configurata qui o passala come argomento
    mpi_cmd = ["mpirun", "-n", str(NUM_CORES), "python3", "mpi_docking.py"]
    if not run_command(mpi_cmd, "Screening Virtuale Distribuito (MPI)"):
        sys.exit(1)

    # 3. Generazione Report e Analisi
    generate_refined_reports()

    total_time = time.time() - start_total
    print(f"\n✅ PIPELINE COMPLETATA CON SUCCESSO")
    print(f"⏱️ Tempo totale: {total_time:.2f} secondi")
    print(f"📄 Report generati in: /{VIEWS_DIR}")
    print(f"📊 Tabella riassuntiva creata: final_summary.csv")

if __name__ == "__main__":
    main()
