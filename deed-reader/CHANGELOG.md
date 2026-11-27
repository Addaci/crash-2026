# Deed Reader: change log

The history of the form (`deed_reader.html`) and its data builder (`build_deed_data.py`). Versions 1.0 to 1.3 were made and used privately, outside this repository, on deeds of the Amsterdam notarial archive concerning Barbados. Version 2.0 is the first in this repository. Newest first.

## Contents

- [2.1, 26 November 2026](#21-26-november-2026)
- [2.0, 22–25 November 2026](#20-2225-november-2026)
- [1.3, 13 November 2026](#13-13-november-2026)
- [1.2, 13 November 2026](#12-13-november-2026)
- [1.1, 11–12 November 2026](#11-1112-november-2026)
- [1.0, 11 November 2026](#10-11-november-2026)
- [Saved work across versions](#saved-work-across-versions)

## 2.1, 26 November 2026

**Added 27 November 2026 (server 0.2, decision D11):** on the team server, *Ask a model* can also ask the cluster's own models, DeepSeek V4.1 Flash and GLM 5.3 Flash, marked *cluster* in the model list. The server asks them itself: the form cuts the box (or the whole scan) out of the image and sends it with the question; the answer comes back into the Questions log, credited to the model, with its token counts. The API key is read only from the environment of the server's job (`DHINFRA_API_KEY`), never from a file, and never reaches a browser; without it the server offers the clipboard route alone, as before. The server's `ask.log` records who asked which model, when and at what cost, never the question. `test_server.py` now checks this against a pretend model service on the same computer (31 checks). The job script `run_server.slurm` is added, tested on the cluster the same morning.

Team-server mode, for a reading team working from one copy of the data and scans on a server (`server.py`, version 0.1, added the same day; decisions D7 to D10 and D12 of 26 November 2026, proposed by Claude Opus 5.5, High, agreed by Colin Greenstreet). Opened from a file, the form behaves exactly as 2.0.

- **Server mode** is found at start by asking the server who the reader is (`/api/me`). Without a server, nothing changes.
- **The reader's name comes from their personal link** and the Transcriber box is locked (D7).
- **Saving:** work is kept in the browser as before and also sent to the server, at most every 5 seconds and only the deeds that changed. The server appends every save to the reader's own log and overwrites nothing (D8). The status line says "kept on the server HH:MM", or warns when the server cannot be reached; the browser copy still holds the work. On opening, the server's copy is merged with the browser's (newer wins, nothing deleted), so work not yet sent is not lost.
- **Also read by** (D9): under the transcription, the other readers with text on the open scan, their line count and last save; *Show* opens their text, numbered and with their help flags, read-only. Other readers' work is fetched every 30 seconds, kept apart from the reader's own and never written back; it is not in *Export all*.
- *Export all*, *Import*, the working folder and *Ask a model* (copy for a model's chat) are unchanged. Asking a model through the server (D11) is not built.
- `test_server.py` checks the server on the sample deeds (13 checks). Its first run found that the access log kept each reader's token from the first visit; the server now writes `[token]` in its place.
- How the server runs on the Graz cluster, and what it changes against the form opened from a file: [`docs/deed-reader-on-the-cluster.md`](../docs/deed-reader-on-the-cluster.md), rewritten the same day.

## 2.0, 22–25 November 2026

Made from form 1.3 by a script of exact, counted find-and-replace changes (39 in all), which stopped if any target was missing; 1.3 itself was not touched. The builder was rewritten from builder 1.2 with its reading of index records, scans, HTR, translations and model readings unchanged. Checked against the 1.2 data: no differences beyond those made by design (image paths, an HTR source label, build stamps).

**General, not tied to one project**
- Every path and every collection-specific setting moved into a settings file: `config.example.json` in the repository, `config.local.json` (never committed) for real values. The form's display settings (title, period, collection, image credit, help text, first deed, default batch, variant spellings, storage name) travel in the data as `ui`.
- The form loads `data/deed_data.js`; if that is absent, `sample/sample_data.js`, with a "Sample data" banner.
- The working folder is `deed-reader/` itself, with local subfolders for real data that git and the data guard refuse (`data/`, `scans/`, `htr/`, `translations/`, `readings/<transcriber>/`, `queries/`, `answers/`, `exports/`). The button reads *Connect working folder*.
- The Transcriber field starts blank. "Own HTR" replaces a personal HTR label. A sentence about one archive's permissions became a neutral "not on disk".
- The index-record parser became its own small file, `saa_jsonld.py`.

**Ask a model** (23 November 2026)
- The *Ask Claude* tab became *Ask a model*, with a menu of the models named in the settings (`ui.models`; for example the two models on the Graz cluster). Every question, pasted answer, query file (one per model) and export records which model was used.
- The C flag reads "C model consulted"; its letter is kept, so flags saved earlier still work. Data and events saved under the old names (`claude_readings`, `claude_reading_shown`) are still read and counted.

**Sample, test and guide** (25 November 2026)
- `sample/`: four invented deeds on five scans, without images, built by the real builder from invented inputs (`sample/make_sample_inputs.py`, `sample/config.sample.json`). The sample has its own storage name, so trying it never mixes with real work in the same browser.
- `test_sample.py`: rebuilds the sample and checks it against the committed copy, checks every field the form reads, runs the data guard over the sample, and opens the form on the sample in headless Chrome. It runs on GitHub on every change to `deed-reader/`.
- `docs/deed-reader-user-guide.md`.
- The Search tab explains the codes in its layer names (P-H, P-MUC, I, A) and links to *Key & conventions* for all of them.

## 1.3, 13 November 2026

**HTR tab**, beside Transcribe:
- The machine text (HTR) of the scan open on the left, with a provenance block always shown above it: made by, platform, model, corrected by hand or not, fetched or exported (when, how), basis code, document and page, URL, file and SHA-256. Each source has its own coloured label.
- A source switch when a scan has more than one HTR; numbered lines (region labels shown in grey and not counted); a warning that HTR covers the whole page and may include a neighbouring deed, naming any other deed on the same scan.
- The HTR is read-only. *fix* on a line keeps a correction beside the original, with reader and time; the file is never changed, and *Restore the file's reading* adds a new entry so the history is kept. Fixes travel in exports and merge on import.
- Opening the HTR, in the tab or below the text, is recorded as before. The deed list marks deeds with HTR on disk and can filter on it.

**Translation** (an experiment):
- Views *HTR*, *HTR + translation* (each translated line under its source line) and *Synthesis (deed)*, and a language chosen per reader.
- Each translation names its source and that source's fingerprint; the form says whether it is *current* or *out of date* against the source as it now reads, including the reader's own HTR fixes. Translation lines can be fixed like HTR lines. A reviewed translation is listed before an unreviewed one. A translation is a model's (basis I); a synthesis is a working aid, not for citation.
- The builder reads `translations/<language>/`, checks each line-for-line file against its source (every line covered, no extra lines, fingerprint) and loads only the newest version of each file.

**Also**:
- A draggable divider between image and right-hand pane (double-click resets).
- *A− / A+* for the size of the text in the HTR tab only.
- A **Search** tab across all deeds or one deed, by layer (transcriptions, HTR, translation, synthesis, notes and entities, index), with near spellings and a list of known variants; exact hits first; a click opens the deed, scan and line.
- Builder 1.2: reads HTR as text files with a header or as PAGE XML (taking the scan from the image file name and the page status as "corrected by hand?"); an optional `PROVENANCE.txt` applies to every file below it. It places a file only on a scan that exists in the deed data, longest identifier first, and lists any file it cannot place. This fixed a fault in builder 1.1 that cut long scan identifiers short, so that some HTR matched no scan.

Tested in headless Chrome with a throwaway profile (36 checks), including that saved work and exports from 1.2 open unchanged in 1.3.

## 1.2, 13 November 2026

Two changes only, for a copy shared privately with a colleague: the form read a new data file (more deeds and their scans), and the first help point named them.

## 1.1, 11–12 November 2026

- **Page notes**: one box per scan in the Deed tab, under the notes on the whole deed; the scan open on the left is highlighted. Included in exports, search and import (the newer note wins).
- **Selection → entity**: selected words become a new entity row, with the scan and the line where the selection starts.
- Entity table columns explained on hover; a new row starts with no kind (it used to default to "date"); rows without a kind sort last.
- 12 November 2026: the per and pro signs (ꝑ, ꝓ) drawn larger, with fuller tooltips; their row renamed *letters*, as its signs serve English and Dutch hands alike.

## 1.0, 11 November 2026

The first form: a deed list with filters; scans beside a transcription box (one manuscript line per text line, line numbers, autosave in the browser); the archive's index record (basis A) beside the scan; a toolbar of editorial marks and letters; per-line help flags (M machine text used, C consulted, G glossary or dictionary, X not read in the ink), so that each line says what it rests on; *Ask Claude about this line*, with a box drawn on the scan; *Export all* (JSON and Markdown) and *Import* (merging, the newer entry wins, nothing deleted); *Save scan .txt*.

Changed the same day while the form was first used:
- The accent buttons add the mark to each selected letter (they used to replace the selection).
- The transcription box is set in Cambria, so accents sit over their letters, with line numbers level with the text.
- *\_underlined\_* and *[filler]* buttons. A line filler is recorded as [filler]; a plain dash stays the clerk's own punctuation.
- The line bar and the question panel moved above the text; the question field grows as you type; every button explains itself on hover.

## Saved work across versions

Work is kept in the browser under a storage name and carries the transcriber's name and the time on every entry. Versions 1.0 to 1.3 kept one storage name, so work saved in one opened in the next. In 2.0 the storage name comes from the settings (`ui.storage_key`, default `deedreader`): to open work saved with 1.x, set it to the old name, or move the work with *Export all* and *Import*.
