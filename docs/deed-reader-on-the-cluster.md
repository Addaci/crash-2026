# The Deed Reader and the Graz cluster

How the Deed Reader fits the hackathon's computing in Graz (CRASH 2026, 30 November to 1 December 2026). First written 25 November 2026; rewritten 26 November 2026.

**What changed on 26 November.** The first version said that the cluster offered its models through an API and nothing else, so the form had to run on each laptop. On 26 November the cluster team confirmed that every participant has an account and that a team can run its own program in a job on the cluster. The team server (`deed-reader/server.py`) was built the same day, and this note now describes both routes. The first version is kept in this file's history.

## Contents

1. [What the cluster offers](#1-what-the-cluster-offers)
2. [Two routes: before and after](#2-two-routes-before-and-after)
3. [Running the server on the cluster](#3-running-the-server-on-the-cluster)
4. [For each reader](#4-for-each-reader)
5. [Where the data lives](#5-where-the-data-lives)
6. [Asking the cluster's models](#6-asking-the-clusters-models)
7. [What to record with every call](#7-what-to-record-with-every-call)
8. [Keys, tokens and secrets](#8-keys-tokens-and-secrets)
9. [Still open](#9-still-open)
10. [Who proposed what](#10-who-proposed-what)
11. [Acronyms](#11-acronyms)

## 1. What the cluster offers

**Models.** The hackathon's models are served by DHinfra (University of Graz) through an **API**: a web address that a script sends requests to, in the same form as OpenAI's API (`/v1/models`, `/v1/chat/completions`, `/v1/embeddings`, and a reranker). Each project has its own key and token caps per day and per week. Tests on 24 November 2026 found two chat models (`deepseek-ai/DeepSeek-V4.1-Flash-1017` and `RedHatAI/GLM-5.3-Flash-NVFP4`; both accepted an image), five embedding models and a reranker. The model list changes: ask the API (`/v1/models`) rather than trusting this page.

**Accounts, projects and jobs** (confirmed by the cluster team, 26 November 2026):

- Every participant has an account on the cluster. Teams work in projects; a project has members and a lead.
- A team can run a program of its own as a **Slurm job** in its project. A small server needs CPUs only, on the `compute` partition.
- A job runs for at most two days (the default), and is **billed for as long as it runs**: set its time limit to the end of the event and end it afterwards. The cost of a small CPU job is small.
- The cluster is reached by **SSH** through its head node, `dhinfra.uni-graz.at`. Each person adds a public key and pairs an authenticator app under *Set up SSH access* in the console; the cluster team approves the request. Being a member of the hackathon's shared project is enough to request it. A key for a second computer needs a new request.
- **Every cluster user can reach a server running in a job**, so the server must refuse anyone without a token.
- Ports 8080 and 21800 to 21899 are reserved. The Deed Reader server uses 8765.

## 2. Two routes: before and after

The form works either way. Opened from a file, it is what it was on 25 November. Served by the team server, it gains a shared store and a single copy of the data, at the costs listed in the last rows.

| | Form opened from a file (each laptop) | Form served by the team server (a job on the cluster) |
| --- | --- | --- |
| Data file and scans | A copy on every laptop, built by each reader | One copy in the project's space on the cluster, built once |
| The reader's name | Typed into the Transcriber box | Taken from the reader's personal link; the box is locked |
| Saving | In the browser; *Export all* to pass work on | In the browser and on the server every few seconds; the server adds each save to the reader's own log and overwrites nothing |
| Others' work | Only after an export and an *Import* | *Also read by* under the transcription: other readers' text and help flags for the open scan, read-only, refreshed every 30 seconds |
| Model calls | Copied into a model's chat, or a query file | The same today. Later (D11, not built): sent by the server, with the key held there and every call in one run log |
| What it costs | Nothing beyond the laptop | A running job (billed, two days at most); SSH and an authenticator for each reader; a token for each reader, because every cluster user can reach the port |
| If something fails | Nothing to fail but the browser | The status line warns that the server cannot be reached; work stays in the browser and is sent when the server is back. The form opened from a file remains the fallback, with *Export all* and *Import* |

## 3. Running the server on the cluster

For the project lead, once SSH access is approved:

1. Put a clone of this repository, the team's data file (`deed-reader/data/deed_data.js`) and the scans in the project's space on the cluster.
2. In your **home folder**, not the project's space: copy `deed-reader/server.example.json` to `server.local.json`, set `"bind": "0.0.0.0"` so the tunnel can reach the job, point `scan_mounts` at the scans, and keep `tokens_file` in the home folder.
3. Make the tokens: `python3 make_tokens.py --out ~/deedreader_tokens.json Anna Ben` (one name per reader). It prints one personal link per reader; give each link to its reader privately.
4. Start the server as a Slurm job on the `compute` partition: 2 CPU cores, 4 GB of memory, no GPU, a time limit at the end of the event. The job script will be added here once it has run on the cluster.
5. The server prints the node it runs on and the one-line tunnel command for the readers.
6. After the event, end the job and copy the readings (`server-store/readings/`, one file per reader) to where the team keeps its work.

`deed-reader/test_server.py` checks the server on the invented sample deeds before it is trusted with real work.

## 4. For each reader

1. Request SSH access in the cluster's console: add a public key, pair an authenticator app, wait for approval.
2. When the lead says the server is running, open a tunnel from your own computer (one line, left open while you read):
   `ssh -N -L 8765:<node>:8765 <your-username>@dhinfra.uni-graz.at`
   where `<node>` is the name the server printed. You will be asked for your key's passphrase and a code from the authenticator app.
3. Open your personal link in Chrome. It sets a cookie and takes you to the form; after that, `http://localhost:8765/` is enough while the tunnel is open.

What you will see: the Transcriber box shows your name and is locked; the status line says "kept on the server" with the time of the last save; under your transcription, *Also read by* lists the other readers with text on the scan, and *Show* opens theirs read-only. Everything else works as in the [user guide](deed-reader-user-guide.md).

## 5. Where the data lives

**Server route:** the data file and scans sit in the project's space on the cluster; the readings sit on the server, one log per reader. **File route:** the data file, scans, HTR, translations and readings are built and kept on each laptop, under `deed-reader/`, from the team's shared copy of the inputs (shared outside this repository).

Either way, Git ignores these folders and the data guard refuses them, so they never reach GitHub.

The archives' terms allow both routes. The Stadsarchief Amsterdam allows its out-of-copyright scans to be reused with a credit, and its machine transcriptions and index records are CC0. Before any Amsterdam text is sent to the cluster's models, check it against the Stadsarchief's terms again.

## 6. Asking the cluster's models

Today the form cannot call a model itself, on either route. There are two ways, both recorded in the form:

- **One question:** *Ask a model about this line* copies the question to the clipboard, naming the model chosen from the list. Paste it into whatever is used to talk to that model, then paste the answer back into the *Ask a model* tab.
- **A batch:** save the questions, then *Write query file* for one model. Something must send that file to the cluster and write the answers back as an answer file, which the form imports. That helper is not written yet ([section 9](#9-still-open)).

Put the cluster's model names in `ui.models` in your `config.local.json` and rebuild, so the menu offers them and every question and answer records which model was used.

## 7. What to record with every call

A reading is only as good as the record of how it was made. For every call to a cluster model, keep one line in a run log with: the model name the server reports; the time; the full prompt and image (or their hashes); the settings (temperature, seed, maximum tokens, thinking budget); the full raw answer; the finish reason; and the token counts. A finish reason of `length` means the answer was cut off. Keep the outputs: a later run of the same request may not give the same answer.

## 8. Keys, tokens and secrets

- **The API key** belongs to one person's project, and every call made with it counts against that project's budget. It is never written into this repository, the form, a committed settings file or a chat. On a laptop, set it in your own terminal as an environment variable (`DHINFRA_API_KEY`) and let a script read it from there. In a server job, it stays in an environment variable inside the job, so it never reaches a browser.
- **Reader tokens** are made by `make_tokens.py` into a file in the lead's home folder, readable by the lead only; never in the project's space, which other members can read, and never in this repository. Each reader gets their link privately. The server compares tokens in constant time, keeps the token out of the address bar after the first visit, and writes `[token]` in its access log in place of the token. A token can be replaced with `make_tokens.py --renew NAME`.
- Nothing in the Deed Reader holds a key, and the data guard refuses `.env` and `*.key` files.

## 9. Still open

- **Asking a model through the server (D11):** the server would hold the key, pass each question to the chosen model and keep the run log of section 7, so the *Ask a model* button could send and receive directly. Not built.
- **A helper for the batch route:** a short script, kept in this repository, that reads a query file from `deed-reader/queries/`, sends each question to the chosen model with the key from the environment, writes the answers to `deed-reader/answers/` in the form the form already imports, and writes a run log. It would need no change to the form. Not written. D11 may make it unnecessary.
- **The job script** for section 3, once it has run on the cluster.
- **A key for the team's project:** the server's project has no API key yet. Only D11 or the batch helper needs one.
- **Images to the models:** how large an image the vision models accept, and how much of the token cap one page uses (tests to come).
- **Gemma 4 31B and Loghi on a GPU node:** asked of the cluster team, not yet answered.

## 10. Who proposed what

The idea of running the form on the cluster is Colin Greenstreet's (25 November 2026). The three things it would add (one copy of the data, shared readings, model calls with the key held on the server) were set out by Claude Opus 5.5, High, the same day. The server's rules, D7 to D12 of 26 November 2026 (the name from the token, saves only ever added, others' work read-only, scans served as images only, model calls through the server, the token file outside the repository), were proposed by Claude Opus 5.5, High, and agreed by Colin Greenstreet. The server and this note were written by Claude Opus 5.5, High, with Colin Greenstreet.

## 11. Acronyms

| Acronym | Stands for | Here |
| --- | --- | --- |
| API | Application programming interface | The web address that scripts send model requests to |
| CPU, GPU | Central and graphics processing unit | The server needs CPUs only |
| HTR | Handwritten text recognition | The machine text beside each scan |
| SSH | Secure Shell | The encrypted connection to the cluster, and the tunnel through it |
| Slurm | (a name, once an acronym) | The cluster's system for running jobs |
