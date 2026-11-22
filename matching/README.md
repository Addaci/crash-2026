# Matching

The four search methods, run on one frozen test set:

1. exact words;
2. fuzzy words (variant tables and edit distance);
3. vectors (embeddings);
4. graph (shared nodes such as ship, master, voyage route and cargo).

Each method writes its candidate links in one shared format (to be documented in `docs/`), so that the evaluation can pool them and hide which method proposed each link.
