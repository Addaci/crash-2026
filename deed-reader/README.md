# Deed Reader

**Status, 25 November 2026:** version 2.0. A fresh clone opens the form straight away on invented sample deeds: open `deed_reader.html` in Chrome. To read real deeds, build your own data file (below). How to use it: [`docs/deed-reader-user-guide.md`](../docs/deed-reader-user-guide.md). History: [`CHANGELOG.md`](CHANGELOG.md).

## Contents

- [About](#about)
- [What it is](#what-it-is)
- [What is here](#what-is-here)
- [How to build and open it](#how-to-build-and-open-it)
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
| `deed_reader.html` | The form (version 2.0). Opens `data/deed_data.js`; if that is absent, `sample/sample_data.js`, with a "Sample data" banner. |
| `build_deed_data.py` | Builds `data/deed_data.js` from local files only. Sends no request to any archive. |
| `saa_jsonld.py` | Reads one saved index record of the Stadsarchief Amsterdam (JSON-LD). |
| `config.example.json` | Every setting, with neutral values. Copy it to `config.local.json` and fill it in. |
| `sample/` | Four invented deeds on five scans (no images), the script that writes their inputs, and the settings that build them. See `sample/README.md`. |
| `test_sample.py` | Builds the sample, checks it, runs the data guard over it and opens the form on it in headless Chrome. Runs on GitHub on every change here. |
| `CHANGELOG.md` | Versions 1.0 to 1.3 (11–13 November 2026) and 2.0. |

Standard library Python only; Chrome for the form (the Claude app's own browser pane cannot open local images).

## How to build and open it

1. Copy `config.example.json` to `config.local.json`; set `input_root` to the folder holding your register, index records, scans and machine text, and fill in the `ui` block (title, period, collection, and `models`: the names of the models that answer questions, e.g. the two on the Graz cluster; they appear in the *Ask a model* menu, and every question and answer records which one was used).
2. `python -I build_deed_data.py` writes `data/deed_data.js` (add `--replace` to rebuild over it).
3. Open `deed_reader.html` in Chrome. *Connect working folder* (pick this `deed-reader` folder) saves each deed's transcription in `readings/<transcriber>/`; exports go to `exports/`.

## What is never committed

Real data stays on your computer or the team's cluster space. `.gitignore` and the data guard (`.github/scripts/data_guard.py`, run before every push) refuse `data/`, `scans/`, `htr/`, `translations/`, `readings/`, `exports/`, `queries/`, `answers/`, `config.local.*`, images, and text holding archive scan identifiers or index record addresses. Ground truth never goes to this repository.

One caution: `build_deed_data.py` is on the guard's allow-list (`.github/data-guard-allow.txt`), because it names a PAGE XML tag in its code. An allow-listed file skips every check, so keep data out of it by hand.

## Still to come

- The *Ask a model* tab connected to the models on the Graz cluster (today a question is copied into the model's chat, or sent as a query file). How the form fits the cluster, and what running it there would take: [`docs/deed-reader-on-the-cluster.md`](../docs/deed-reader-on-the-cluster.md).
- Screenshots for `docs/figures/`.

Code under the MIT licence (see the repository's `LICENSE`). Made by Claude Opus 5.5 High with Colin Greenstreet, 11–25 November 2026.
