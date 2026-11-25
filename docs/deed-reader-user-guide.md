# Deed Reader: user guide

For Deed Reader 2.0. How to open the form, read and transcribe a deed beside its scans, record the help you used, and save your work. For what the form is and how its data is built, see [`deed-reader/README.md`](../deed-reader/README.md); for its history, [`deed-reader/CHANGELOG.md`](../deed-reader/CHANGELOG.md).

## Contents

1. [Try it on the sample](#1-try-it-on-the-sample)
2. [Open it on real deeds](#2-open-it-on-real-deeds)
3. [The screen](#3-the-screen)
4. [Finding a deed](#4-finding-a-deed)
5. [Reading the scans](#5-reading-the-scans)
6. [Transcribing](#6-transcribing)
7. [Recording the help you used](#7-recording-the-help-you-used)
8. [Machine text (HTR) and translations](#8-machine-text-htr-and-translations)
9. [Asking a model](#9-asking-a-model)
10. [The deed's index record, notes and entities](#10-the-deeds-index-record-notes-and-entities)
11. [Search](#11-search)
12. [Saving, exporting and sharing work](#12-saving-exporting-and-sharing-work)
13. [What the codes mean](#13-what-the-codes-mean)
14. [When something goes wrong](#14-when-something-goes-wrong)

## 1. Try it on the sample

1. Clone or download the repository.
2. Open `deed-reader/deed_reader.html` in **Google Chrome** (double-click it, or Ctrl+O / Cmd+O in Chrome). Other browsers are untested.
3. A banner says **Sample data**: four invented deeds on five scans, made for trying the form. Nothing in them comes from an archive, and they have no scan images, so the image pane says each scan is "not on disk".

What the sample lets you try: deed 1, scan 1 has two machine texts, an English translation, a synthesis of the deed and a model reading; deeds 1 and 2 share a scan; deed 4 has no index record, and the form says so.

The sample keeps its work in the browser under its own storage name, so nothing you type there mixes with real work.

## 2. Open it on real deeds

Real data never goes into the repository. To read your own deeds:

1. In `deed-reader/`, copy `config.example.json` to `config.local.json` and fill it in: `input_root` (the folder with your register, index records, scans and machine text), the folder names, and the `ui` block (title, period, collection, and `models`, the names of the models that answer questions).
2. Run `python -I build_deed_data.py`. It writes `data/deed_data.js` from local files only and prints what it found and any problems. Add `--replace` to rebuild over an existing file.
3. Open `deed_reader.html` in Chrome again. It now opens your data, not the sample.

The README lists the input folders and what each holds. Rebuild whenever new scans, HTR or translations arrive, then reload the form (F5): your own work is not touched by a rebuild.

## 3. The screen

- **Left:** the deed list, with filters. *Deeds ☰* (top left) hides or shows it.
- **Middle:** the scans of the deed, one tab per scan.
- **Right:** six tabs. *Transcribe*, *HTR*, *Deed: index & notes*, *Ask a model*, *Search*, *Key & conventions*.
- **Top:** *Transcriber* (type your name first: everything you write is kept under it), *Connect working folder*, *Export all*, *Import…*, *How this works* (a one-page summary; it opens on first use).

The grey bar between the image and the right-hand side can be dragged; double-click it to reset. Every button explains itself when you hover over it.

## 4. Finding a deed

Each row in the list shows the deed's number, date, type, language, check tier and number of scans, with "HTR" if machine text is on disk and your progress so far. Filter by batch, check tier, language, deed type and HTR on disk; the search box above looks through names, places, index notes, machine text and your own notes. The count at the foot ("4 of 4 deeds") shows how many rows pass the filters.

## 5. Reading the scans

Click a scan's tab above the image. Use the **zoom** slider, and **left half / right half** for a two-page opening. A tab marked * holds the end of one deed and the start of the next: transcribe each deed's part in its own deed. The line under the image names the scan, its file and the image credit.

**Draw box**, then drag on the image, marks the words in doubt; the box goes with your next question to a model (section 9). *Clear box* removes it.

## 6. Transcribing

In *Transcribe*, type one manuscript line per text line, spelling as written. The toolbar inserts:

- **ink:** \~\~deleted\~\~, \\interlined/, \_underlined\_ (select the words, then click), [margin], [signature], [mark], [paraph], [blank], [filler];
- **doubt:** [?] after a doubtful word, [illegible];
- **letters:** superscript and subscript, long s (ſ), accents added to the selected letter, ÿ, ĳ, º, the florin sign ƒ, per and pro (ꝑ, ꝓ), con (ꝯ), &c.

*Key & conventions* lists every mark and convention. Your text is kept in the browser as you type. *Save scan .txt* writes the scan's transcription as a text file whose header names the deed, scan, transcriber, date and the help recorded.

The transcriber reads the ink. The form never settles a reading: the machine text, a translation or a model's answer is a lead to check against the scan, never a substitute for it.

## 7. Recording the help you used

The line bar above the text works on the line the cursor is in:

| Flag | Meaning |
| --- | --- |
| **M** | the machine text (HTR) helped with this line |
| **C** | a model was consulted (ticked for you when you ask from the form) |
| **G** | a glossary or dictionary helped |
| **X** | this line is *not* your own reading of the ink |

A line you have read in the ink counts as hand transcription (P-H), with any help recorded beside it; a line marked X does not, until you have read it in the ink. The flags show in the line numbers and stay with their lines when you insert or remove lines. Showing the machine text or a model's reading is also recorded, with the time. The summary at the foot of the tab gives the count for the scan.

*Selection → entity*: select a name, place, ship, date or quantity in your text and click; it becomes a new row in the entity table (section 10).

## 8. Machine text (HTR) and translations

The **HTR** tab shows the machine text of the scan on the left, where it is on disk, under a provenance block: who made it, the platform and model, whether it was corrected by hand, when and how it was fetched, its basis code, and the file with its fingerprint (SHA-256). Where a scan has more than one HTR, buttons switch between them. Lines are numbered (region labels in grey are not counted). HTR covers the whole page, so it may include part of a neighbouring deed.

HTR is read-only. To correct a small glitch, hover over a line and click *fix*: your correction is kept beside the original, with your name and the time, and the file is never changed. *Show HTR below my text* (in *Transcribe*) puts the HTR under your own text for checking line by line.

**Views:** *HTR*; *HTR + translation*, with each translated line under its source line; *Synthesis (deed)*, a summary of the whole deed. Choose the language in the bar. A translation's provenance block says whether it is still **current** (made from the HTR exactly as it now reads, your fixes included) or **out of date**. Translations and syntheses are a model's work (basis I): a synthesis is a working aid, not for citation. They are made as files, on request in a model's chat, and appear once the data has been rebuilt. *A− / A+* change the text size in this tab only.

## 9. Asking a model

1. Optionally, *Draw box* round the words in doubt.
2. Put the cursor in the line and click **Ask a model about this line**.
3. Choose the model from the list (the names come from the settings), add the words in doubt and your question.
4. *Copy for the model's chat* puts the whole question (deed, scan file, the box, the line, your words and question) on the clipboard and keeps it in the log. Paste it into that model's chat with the scan.
5. In the *Ask a model* tab, paste the answer beside the question and type your ruling.

For many questions at once: *Save for a batch of questions*, then *Write query file* in the *Ask a model* tab for one model; that model writes an answer file, which you import there. Every question and answer records which model was used, and C is ticked on the line. The form cannot reach a model by itself.

## 10. The deed's index record, notes and entities

*Deed: index & notes* holds:

- the **archive's index record** (basis A): title, date, type, language, inventory, notary, persons and their roles, places, subject note, scans. It is a finding aid made by the archive's indexers, not the deed's text, and the form never overwrites it;
- **as seen by you**: your own reading of the language, deed type and date;
- **English notes** on the whole deed, and **page notes**, one box per scan (click a heading to open that scan);
- the **entity check table**: kind (person, place, ship, date, quantity, other), the words *as written* in the ink, the standard *value*, scan, line, whether checked in the ink, and a comment. Dates and quantities sort first; rows without a kind sort last.

## 11. Search

The *Search* tab looks through this deed or all deeds, in the layers you tick: your transcriptions (and those of other transcribers in this browser), HTR (with your fixes), translations, syntheses, notes and entities, and the index. The letters after each layer's name say what it rests on (P-H, P-MUC, I, A; section 13); the link under the layers opens *Key & conventions*, which lists every code. *spellings* also finds near spellings and the variants listed in the data. Exact hits come first, then ink-based layers before the others. Click a hit to open its deed, scan and line.

## 12. Saving, exporting and sharing work

- **In the browser:** everything is kept as you type, in this browser on this computer. Clearing the browser's site data deletes it, so export from time to time. A form opened from disk and the same form served from a local address keep separate stores.
- **Connect working folder:** pick the `deed-reader` folder (Chrome asks once). Each deed is then saved as a file in `readings/<transcriber>/`.
- **Export all** writes two files, JSON and Markdown, with all your work. Without a connected folder they go to Downloads: move them into `deed-reader/exports/`.
- **Import…** reads an exported JSON file and merges it: for each entry the newer one wins, and nothing is deleted. To see a colleague's work, import their export and type their name in *Transcriber*; **type your own name back before you write anything**.

`data/`, `readings/`, `exports/`, `queries/` and `answers/` stay on your computer or the team's cluster space. Git ignores them and the data guard refuses them, so they are never committed.

## 13. What the codes mean

- **P-H:** transcribed by hand from the ink.
- **P-MHC:** machine text, corrected by hand.
- **P-MUC:** machine text, uncorrected (most HTR).
- **A:** the archive's index record.
- **I:** an inference or a model's work: translations, syntheses, model readings, answers.
- **Check tier:** how far a deed's reading can be checked, as set in the register.

## 14. When something goes wrong

- **"The deed data did not load":** the form found neither `data/deed_data.js` nor `sample/sample_data.js`. Open it in Chrome from the `deed-reader` folder, with `sample/` (or `data/`) beside it. The Claude app's own browser pane cannot read local files.
- **A scan shows "not on disk":** the builder found no image file for it; check `scan_dirs` in the settings and rebuild.
- **"Could not load" an image:** the form was opened from somewhere the image path does not reach. Open it from the `deed-reader` folder.
- **A translation says "out of date":** the HTR has been fixed since the translation was made; some lines may no longer match.
- **Your work seems to have gone:** check the *Transcriber* name (work is kept per name), and that you opened the same file in the same browser. Import your last export if needed.
