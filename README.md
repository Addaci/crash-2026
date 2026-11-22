# crash-2026: finding one ship in three archives, and knowing when to believe it

Code for a team at the **CRASH 2026 hackathon** (UNICORN hub, Graz, 30 November to 1 December 2026), led by Colin Greenstreet (MarineLives).

**Status:** work in progress. The structure is in place; the code arrives between 22 and 29 November 2026 and during the hackathon.

## Contents

1. [The question](#the-question)
2. [The workflow](#the-workflow)
3. [What is in this repository, and what is not](#what-is-in-this-repository-and-what-is-not)
4. [Layout](#layout)
5. [Working rules](#working-rules)
6. [Licence and citation](#licence-and-citation)

## The question

Linked historical datasets are often wrong, and few say how often.

In October 1656 the *Peacock* sailed from Amsterdam for Guinea and Barbados. Its story is split three ways: English High Court of Admiralty depositions in London, Dutch notarial deeds in Amsterdam, and the SlaveVoyages database. A historian has found it in all three. Can a machine, and how would a historian know whether to believe it?

The team links ships, people and cargoes across these sources, 1640 to 1680, in English, Dutch and Latin. Four search methods compete on one frozen test set of known matches: exact words, fuzzy words, vectors and a graph. We report whichever wins. Then we measure what matters to a historian:

- **recall**: how many known matches each method finds;
- **minutes to a verdict**: how long a historian takes to accept or reject a proposed link;
- **wrong links caught**: how many planted false hits are spotted;
- **silos crossed**: the share of accepted links that join records held in different archives, languages or scholarly traditions.

## The workflow

```
 sources                 methods                 judging                       results
 -------                 -------                 -------                       -------
 HCA depositions  --+    exact words   --+                                      recall
 notarial deeds   --+--> fuzzy words   --+--> candidate links --> blind evidence  minutes to a verdict
 SlaveVoyages     --+    vectors       --+    (pooled, method     cards, two      wrong links caught
                         graph         --+     hidden)            readers         silos crossed
```

Each proposed link becomes an **evidence card**: an image crop of the lines, the machine text with the names highlighted, how each name was matched, the relation in a fixed form with its trigger words in the original language, a literal gloss, what would refute the link, and where each element came from. No persuasive prose: a fluent explanation is what produces fast wrong verdicts.

## What is in this repository, and what is not

**In:** code, documentation, data formats and schemas, and invented sample data.

**Not in:** archive images, index records, machine transcriptions, hand transcriptions, the test set and its answers. These belong to the holding archives or stay with the team under the archives' terms. Restricted material is read only on the hackathon cluster, with the cluster's own models. The `.gitignore` blocks data folders and image files so that nothing restricted is committed by mistake.

## Layout

| Folder or file | What it holds |
|---|---|
| `deed-reader/` | The Deed Reader: a browser tool for reading a notarial deed beside its scans, with machine text, translation, search, entities and a record of every kind of help used. Arrives 22 to 23 November 2026 |
| `matching/` | The four search methods |
| `evaluation/` | Scoring, the evidence card and the timing analysis |
| `cluster/` | Job scripts, environment files, and an instrument-record template (model, weights date, software version, seed) |
| `docs/` | Method cards, the data manifest schema, the test-set design, the Deed Reader user guide |
| `LICENSE` | MIT, for code |
| `LICENSE-docs` | CC BY 4.0, for documentation and text |
| `CITATION.cff` | How to cite this repository |

The HTR evaluation script `htr_eval` lives in [Addaci/HCA](https://github.com/Addaci/HCA) (`tools/htr_eval/`).

## Working rules

Anyone changing the tools keeps these rules:

1. Machine text is read-only. Corrections are kept as a separate layer beside it, with who made them and when.
2. Every reading carries its basis: transcribed by hand from the ink, machine text corrected by hand, machine text uncorrected, or inference.
3. The record of help (machine text used, a model consulted, a dictionary used, a line not read in the ink) is kept.
4. Imports merge; nothing is deleted.
5. Every model call is logged with the model, its weights date and the seed.
6. A link is a claim with a source and an author, not a fact. Agreement between two sources counts only if one is not derived from the other.
7. Changes arrive by pull request.

## Licence and citation

Code is under the MIT licence (`LICENSE`). Documentation and text are under CC BY 4.0 (`LICENSE-docs`). Archive images and records keep the terms of the archives that hold them.

To cite, use GitHub's "Cite this repository" button, or `CITATION.cff`.
