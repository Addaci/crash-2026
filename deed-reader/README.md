# Deed Reader

**Status, 27 November 2026:** version 2.1, with a team server (0.2) that runs on the Graz cluster and can ask the cluster's own models. A fresh clone opens the form straight away on invented sample deeds: open `deed_reader.html` in Chrome. To read real deeds, build your own data file (below). How to use it: [`docs/deed-reader-user-guide.md`](../docs/deed-reader-user-guide.md). History: [`CHANGELOG.md`](CHANGELOG.md).

## Contents

- [About](#about)
- [What it is](#what-it-is)
- [What is here](#what-is-here)
- [How to build and open it](#how-to-build-and-open-it)
- [Running it as a team server](#running-it-as-a-team-server)
- [Running it on the Graz cluster](#running-it-on-the-graz-cluster)
- [Asking the cluster's models](#asking-the-clusters-models)
- [What is never committed](#what-is-never-committed)
- [Still to come](#still-to-come)

## About

The Deed Reader is a form, opened in a web browser, for reading and transcribing handwritten deeds from their scans. It was developed by Colin Greenstreet to read deeds in the Amsterdam notarial archive that concern Barbados, 1630–1680.

Nothing in its design is specific to Amsterdam. Paths, collection names and the models it consults are set in a settings file, so it can be adapted to documents from other archives. A few column names of the deed register are still fixed in the code.

For CRASH 2026 (Graz, 30 November to 1 December 2026), it is proposed as one input to the document viewer and analyser that Colin Greenstreet's team will build.

## What it is

Beside each scan the form shows the archive's index record, machine text (HTR), translations and questions to a model, and it records every kind of help used, line by line, so a transcription says what it rests on. It also has translation and synthesis views, search across all layers, page notes and an entity table. One HTML file, no installation. The transcriber reads the ink; the form never settles a reading.

## What is here

| File | What it does |
| --- | --- |
| `deed_reader.html` | The form (version 2.1). Opens `data/deed_data.js`; if that is absent, `sample/sample_data.js`, with a "Sample data" banner. |
| `build_deed_data.py` | Builds `data/deed_data.js` from local files only. Sends no request to any archive. |
| `saa_jsonld.py` | Reads one saved index record of the Stadsarchief Amsterdam (JSON-LD). |
| `config.example.json` | Every setting, with neutral values. Copy it to `config.local.json` and fill it in. |
| `sample/` | Four invented deeds on five scans (no images), the script that writes their inputs, and the settings that build them. See `sample/README.md`. |
| `test_sample.py` | Builds the sample, checks it, runs the data guard over it and opens the form on it in headless Chrome. Runs on GitHub on every change here. |
| `server.py` | The team server (version 0.2): one copy of the form, data and scans for a reading team, with every reader's work kept on the server; it can also ask the cluster's models. See [Running it as a team server](#running-it-as-a-team-server). |
| `run_server.slurm` | Runs the server as a CPU-only job on the Graz cluster. See [Running it on the Graz cluster](#running-it-on-the-graz-cluster). |
| `make_tokens.py` | Makes one personal link (token) per reader for the server. |
| `server.example.json` | The server's settings, with notes. Copy it to `server.local.json`. |
| `test_server.py` | Runs the server on the sample deeds with two invented readers and checks refusals, the personal link, saving, restarts, private files and that no token is logged; and, against a pretend model service on the same computer, asking the cluster's models, including that the key is never printed or written and that one reader cannot collect another's answer (33 checks). |
| `CHANGELOG.md` | Versions 1.0 to 1.3 (11–13 November 2026), 2.0 and 2.1, with the server's additions of 27 November. |

Standard library Python only; Chrome for the form (the Claude app's own browser pane cannot open local images).

## How to build and open it

1. Copy `config.example.json` to `config.local.json`; set `input_root` to the folder holding your register, index records, scans and machine text, and fill in the `ui` block (title, period, collection, and `models`: the names of the models that answer questions, e.g. the two on the Graz cluster; they appear in the *Ask a model* menu, and every question and answer records which one was used).
2. `python -I build_deed_data.py` writes `data/deed_data.js` (add `--replace` to rebuild over it).
3. Open `deed_reader.html` in Chrome. *Connect working folder* (pick this `deed-reader` folder) saves each deed's transcription in `readings/<transcriber>/`; exports go to `exports/`.

## Running it as a team server

Opened from a file, the form keeps each reader's work in their own browser. `server.py` lets a team read from one copy instead: it serves the form, the data file and the scans to each reader through a personal link, keeps every reader's work on the server, and shows each reader what the others have read. Standard library Python 3.7 or newer; nothing to install.

- **Your name comes from your link.** The Transcriber box is filled in and locked, so nobody saves under another's name.
- **Every save is kept.** Work is kept in the browser as before and sent to the server every few seconds; the server adds each save to the reader's own log and never overwrites one. The status line says when it was last kept there.
- **Others' work, read-only.** Under your transcription, *Also read by* lists the other readers with text on the open scan; *Show* opens their text, with their help flags, which you can read but not change.

To try it on your own computer with the sample deeds:

1. Copy `server.example.json` to `server.local.json`. For the sample, set `"data_file": "sample/sample_data.js"` and `"tokens_file"` to a file in your home folder; for real deeds, keep `data/deed_data.js` and point `scan_mounts` at the folder holding the scans.
2. `python make_tokens.py --out ~/deedreader_tokens.json Anna Ben` writes the token file and prints one personal link per reader. Give each link to its reader privately.
3. `python server.py --config server.local.json`, then open each link in a different browser (or a private window).

The server listens on your own computer only (`127.0.0.1`) unless the settings say otherwise.

## Running it on the Graz cluster

On the DHinfra cluster in Graz the server runs as a CPU-only Slurm job in the team's project, and each reader reaches it through an SSH tunnel over the head node. First run there on 27 November 2026.

1. On the head node, clone this repository into the project's workspace (`/tank/projects/<project>/`). Copy the data file and the scans there yourself, by `scp`; never through Git.
2. Put the server's settings in your home folder as `~/server.local.json`, with `"bind": "0.0.0.0"` and paths as a job sees them: a compute node sees the head node's `/tank/projects/<project>` as `/mnt/nfs/projects/<project>`. Make the tokens with `make_tokens.py --out ~/deedreader_tokens.json`.
3. Run `python3 -I test_server.py` on the head node, then submit from the `deed-reader` folder, naming the project's account (otherwise Slurm bills your default one):
   `sbatch --account=<project account> --time=06:00:00 run_server.slurm`
4. The job's output, `~/deed-reader-<jobid>.out`, names the node and gives each reader the tunnel line: `ssh -N -L 8765:<node>:8765 <username>@dhinfra.uni-graz.at`, then their personal link at `http://localhost:8765/`.

The job needs 4 GB of memory, mainly to unpack the cluster's job container. A change of settings, tokens or code takes effect at the next restart (`scancel <jobid>`, then submit again); readings carry over. More on what the cluster offers and how the server differs from the form opened from a file: [`docs/deed-reader-on-the-cluster.md`](../docs/deed-reader-on-the-cluster.md).

## Asking the cluster's models

On the team server, the *Ask a model* menu also lists the cluster's own models, DeepSeek V4.1 Flash (also offered with its thinking switched off) and GLM 5.3 Flash, marked *(cluster)*. Draw a box round the lines in question, choose one of them and click *Ask … now*: the form cuts the box out of the scan and sends it, with one line about the deed and your question, to the server, which asks the model. The question shows *sent* in the *Ask a model* tab; the answer appears under it, credited to the model, when it comes. The server keeps every answer in a file beside the readings, so it survives a reload or a restart, and the form collects it every few seconds rather than holding a connection open. A reader can collect only their own answers.

- **The key never reaches a browser or a file.** The server reads it only from the job's environment variable `DHINFRA_API_KEY`, typed at a hidden prompt when the job is submitted (`read -rs DHINFRA_API_KEY && export DHINFRA_API_KEY`, then `sbatch …`, then `unset DHINFRA_API_KEY`). Without it the menu offers the clipboard route alone, as before.
- **What is recorded.** `ask.log`, beside the access log, has one line per question: time, reader, model, seconds, outcome and tokens in and out; never the question or the key.
- **Limits.** Up to 32,768 tokens and 10 minutes an answer, set by `ask_max_tokens` and `ask_timeout` in the settings. The ceiling is a limit, not a charge.
- **First trials, 27 November 2026.** On a whole page of a 17th-century Dutch deed, both models used their whole allowance thinking and wrote no answer; the model service also seems to reduce an image to about 1,280 pixels. A few lines at a time is the way to use them for now. DeepSeek accepts an option that switches its thinking off (`chat_template_kwargs`, `enable_thinking: false`); GLM thinks whatever it is sent.

Other models (Claude, ChatGPT and so on) work as before: the question goes to the clipboard and the answer is pasted back.

## What is never committed

Real data stays on your computer or the team's cluster space; so do the server's readings, the answers it keeps, its logs, its settings and the tokens. `.gitignore` and the data guard (`.github/scripts/data_guard.py`, run before every push) refuse `data/`, `scans/`, `htr/`, `translations/`, `readings/`, `exports/`, `queries/`, `answers/`, `config.local.*`, images, and text holding archive scan identifiers or index record addresses. Ground truth never goes to this repository.

One caution: `build_deed_data.py` is on the guard's allow-list (`.github/data-guard-allow.txt`), because it names a PAGE XML tag in its code. An allow-listed file skips every check, so keep data out of it by hand.

## Still to come

- A question log of one structured record per question to a cluster model, with the kind of task asked (a word in doubt, a few lines, a page, entities), and a summary script giving each model's speed, cost and outcomes by task.
- A verdict from the reader on each answer (usable, partly, not usable), so the summary can say how often a model helped.
- Trying the cluster's models with their thinking switched off, where they allow it.
- More model names for the clipboard route, set in the server's settings.

Code under the MIT licence (see the repository's `LICENSE`). Made by Claude Opus 5.5 with Colin Greenstreet, 11–27 November 2026.
