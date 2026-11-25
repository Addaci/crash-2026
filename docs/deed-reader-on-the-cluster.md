# The Deed Reader and the Graz cluster

How the Deed Reader fits the hackathon's computing in Graz (CRASH 2026, 30 November to 1 December 2026). Written 25 November 2026, from what the team knows so far; points still open are marked as such.

## Contents

1. [What the cluster is](#1-what-the-cluster-is)
2. [Where the form runs](#2-where-the-form-runs)
3. [Where the data lives](#3-where-the-data-lives)
4. [Asking the cluster's models](#4-asking-the-clusters-models)
5. [What to record with every call](#5-what-to-record-with-every-call)
6. [Keys and secrets](#6-keys-and-secrets)
7. [Still open](#7-still-open)

## 1. What the cluster is

The hackathon's models are served by DHinfra (University of Graz) through an **API**: a web address that a script sends requests to, in the same form as OpenAI's API (`/v1/models`, `/v1/chat/completions`, `/v1/embeddings`, and a reranker). Each project has its own key and token caps per day and per week. Tests on 24 November 2026 found two chat models (`deepseek-ai/DeepSeek-V4.1-Flash-1017` and `RedHatAI/GLM-5.3-Flash-NVFP4`; both accepted an image), five embedding models and a reranker. The model list changes: ask the API (`/v1/models`) rather than trusting this page.

The API is the only part of the cluster the team is known to have. Nothing so far says that teams get a login, a shared folder or their own jobs on the cluster's machines (see [section 7](#7-still-open)).

## 2. Where the form runs

On each person's own laptop, in Chrome. The form is one HTML file and needs no server: open `deed-reader/deed_reader.html` from a clone of this repository.

**Why not on the cluster?** Not because of the archives' terms. The Stadsarchief Amsterdam allows its out-of-copyright scans to be reused with a credit, and its machine transcriptions and index records are CC0, so the material may sit on a laptop as well as on the cluster. The reason is that the cluster, as far as the team knows, offers an API for its models and nothing else: no place to run a program of our own.

**What running it on the cluster would add**, if the cluster could host a small server program (or one shared machine could, at the venue):

1. **One copy of the data** (data file, scans, HTR, translations) for everyone, built once, in place of a copy on every laptop.
2. **One shared store of readings**, so the team sees each other's work as it is typed, in place of *Export all* and *Import*. Today the form keeps work in each browser; this needs a small change to the form.
3. **Model calls from the form itself**: the server holds the key and passes each question to the cluster's models, so the *Ask a model* button can send and receive directly, and every call is logged in one place. The key never reaches a browser.

Serving the form's page from a cluster address alone would add little: each browser would still keep its own work, and no model could be called without exposing the key.

**The question for the cluster team:** can a team run a small, long-lived web server (a Python process, a few hundred MB of files) on DHinfra during the hackathon, reachable by the team only? If yes, the three points above become one task for Graz. If no, the laptop route in this note works as it stands.

## 3. Where the data lives

The data file (`data/deed_data.js`), scans, HTR, translations and readings are built and kept **on each laptop**, under `deed-reader/`, from the team's shared copy of the inputs (shared outside this repository). Git ignores these folders and the data guard refuses them, so they never reach GitHub. Each reader exports their work (*Export all*) and the team merges it with *Import*, which loses nothing.

## 4. Asking the cluster's models

Today the form cannot call a model itself. There are two routes, both recorded in the form:

- **One question:** *Ask a model about this line* copies the question to the clipboard, naming the model chosen from the list. Paste it into whatever is used to talk to that model, then paste the answer back into the *Ask a model* tab.
- **A batch:** save the questions, then *Write query file* for one model. Something must send that file to the cluster and write the answers back as an answer file, which the form imports. That something does not exist yet: it is the small helper proposed in [section 7](#7-still-open).

Put the cluster's model names in `ui.models` in your `config.local.json` and rebuild, so the menu offers them and every question and answer records which model was used.

## 5. What to record with every call

A reading is only as good as the record of how it was made. For every call to a cluster model, keep one line in a run log with: the model name the server reports; the time; the full prompt and image (or their hashes); the settings (temperature, seed, maximum tokens, thinking budget); the full raw answer; the finish reason; and the token counts. A finish reason of `length` means the answer was cut off. Keep the outputs: a later run of the same request may not give the same answer.

## 6. Keys and secrets

The API key belongs to one person's project and is never written into this repository, the form, a settings file that is committed, or a chat. Set it in your own terminal as an environment variable (`DHINFRA_API_KEY`), and let a script read it from there. Nothing in the Deed Reader holds a key, and the data guard refuses `.env` and `*.key` files.

## 7. Still open

- **A place to run a server on the cluster** (section 2). Until the cluster team answers, each laptop builds its own copy of the data.
- **A helper for the batch route:** a short script, kept in this repository, that reads a query file from `deed-reader/queries/`, sends each question to the chosen cluster model with the key from the environment, writes the answers to `deed-reader/answers/` in the form the form already imports, and writes a run log (section 5). It would need no change to the form. Not yet written.
- **Images to the models:** how large an image the vision models accept, and how much of the token cap one page uses (tests to come).
- **Gemma 4 31B and Loghi on a GPU node:** asked of the cluster team, not yet answered.
