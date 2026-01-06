from mpi4py import MPI
import platform

comm = MPI.COMM_WORLD
rank = comm.Get_rank()
node = platform.node()

print(f"Ciao dal processo {rank}/{comm.Get_size()} in esecuzione su {node}")