#!/bin/bash
#SBATCH --job-name=deed-reader
#SBATCH --partition=compute
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=04:00:00
#SBATCH --output=/home/%u/%x-%j.out
#SBATCH --chdir=/tmp
#
# Deed Reader team server as a Slurm job on the Graz cluster (DHinfra).
# No GPU is needed. Settings are read from ~/server.local.json, in your
# home folder, never in the project's space or the repository.
#
# Submit from this folder (deed-reader/):
#   sbatch run_server.slurm                         a few hours, for a demo
#   sbatch --time=2-00:00:00 run_server.slurm       for the event (2 days at most)
# Check:  squeue -u $USER        Output: ~/deed-reader-<jobid>.out (your home folder)
# Stop:   scancel <jobid>
#
# The output names the node and prints the one-line tunnel for the readers.

set -euo pipefail
# A compute node sees the head node's /tank/projects/<p> as /mnt/nfs/projects/<p>.
cd "${SLURM_SUBMIT_DIR/#\/tank\/projects\//\/mnt\/nfs\/projects\/}"
echo "Job $SLURM_JOB_ID on $(hostname), $(date '+%d %b %Y %H:%M:%S %Z')"
python3 --version
exec python3 -u server.py --config "$HOME/server.local.json"
