# Sample data (invented)

Everything in this folder is **invented** for trying the Deed Reader. No deed, person, ship, scan or text comes from an archive. The names say so: *Voorbeeld*, *Proef*, *Oefening* and *Demo* are Dutch and English words for "example", "test", "exercise" and "demo". Scan identifiers have the form `DEMO` + 11 digits, and record identifiers `urn:sample:…`.

| File | What it is |
| --- | --- |
| `sample_data.js` | What the form opens when `data/deed_data.js` is absent. Built by `build_deed_data.py`; do not edit by hand. |
| `config.sample.json` | The settings that build it. Its storage name (`deedreader-sample`) keeps sample work apart from real work in the browser. |
| `make_sample_inputs.py` | Writes `inputs/`: the four deeds, their index records, machine text, a second HTR, a translation, a synthesis and a model reading. |
| `inputs/` | The invented input files, in the folder layout the builder reads. `htr-files/` and `translation-files/` stand for the real `htr/` and `translations/`, which the data guard refuses. |

There are no scan images: the data guard refuses images outside `docs/figures/`.

To change the sample, edit `make_sample_inputs.py`, then from the `deed-reader` folder:

```
python -I sample/make_sample_inputs.py --replace
python -I build_deed_data.py --config sample/config.sample.json --replace
python -I test_sample.py
```

The test fails if `inputs/` or `sample_data.js` no longer matches the script.
