"""Write the invented input files for the Deed Reader's sample (deed-reader/sample/inputs/).

Part of the Deed Reader (crash-2026). Standard library only. Reads nothing and sends nothing.
Every deed, person, ship, scan and text here is INVENTED for trying the form. None of it comes from
an archive. The names say so: Voorbeeld, Proef, Oefening and Demo are Dutch and English words for
"example", "test", "exercise" and "demo". Scan identifiers have the form DEMO + 11 digits.

    python -I sample/make_sample_inputs.py            writes sample/inputs/ (stops if it exists)
    python -I sample/make_sample_inputs.py --replace  rewrites the files it owns in sample/inputs/
Then build the sample data the form opens:
    python -I build_deed_data.py --config sample/config.sample.json --replace

What the sample shows: four deeds on five scans, 1652-1675; scan 2 shared by deeds 1 and 2; scan 1 with
the archive's machine text and a second HTR, an English translation, a synthesis and a model reading;
deed 4 with no index record (the form warns); scan 5 with no machine text. No scan images: the data
guard refuses images outside docs/figures/, so every scan shows "not on disk".
Folder names differ from the real ones (htr-files, translation-files) because the guard refuses
folders named htr/ and translations/.
"""
import hashlib
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / "inputs"
REG = re.compile(r"^\s*(Region\d*|TextRegion\d*)\s*$", re.I)

S1, S2, S3, S4, S5 = (f"DEMO{n:011d}" for n in range(1, 6))

# ---------- the invented deeds ----------
DEEDS = [
    {"no": 1, "batch": "S1", "date": "1652-03-14", "type": "Bevrachting", "language": "Nederlands",
     "inv": "1", "index_id": "S-0001", "scans": [S1, S2], "notary": "Hendrick Demo", "tier": "A",
     "mt": "HTR", "english": "yes",
     "title": "Bevrachting van het schip De Proefvaart naar Barbados (invented)",
     "persons": [("Jan Voorbeeld", "Schipper"), ("Pieter Oefening", "Bevrachter"),
                 ("Claes Steekproef", "Getuige")],
     "places": ["Amsterdam", "Barbados"],
     "note": ["Invented sample deed: charter of De Proefvaart, Amsterdam to Barbados and back."]},
    {"no": 2, "batch": "S1", "date": "1652-03-14", "type": "Verklaring", "language": "Nederlands",
     "inv": "1", "index_id": "S-0002", "scans": [S2, S3], "notary": "Hendrick Demo", "tier": "B",
     "mt": "HTR", "english": "",
     "title": "Verklaring over de lading van De Proefvaart (invented)",
     "persons": [("Anna Proefmans", "Comparant"), ("Jan Voorbeeld", "Genoemd")],
     "places": ["Amsterdam"],
     "note": ["Invented sample deed: it begins on the scan where deed 1 ends."]},
    {"no": 3, "batch": "S2", "date": "1660-07-02", "type": "Procuratie", "language": "Nederlands, Engels",
     "inv": "2", "index_id": "S-0003", "scans": [S4], "notary": "Hendrick Demo", "tier": "A",
     "mt": "HTR", "english": "yes",
     "title": "Procuratie van Thomas Example op Willem Oefening (invented)",
     "persons": [("Thomas Example", "Lastgever"), ("Willem Oefening", "Gemachtigde")],
     "places": ["Amsterdam", "Bridgetown, Barbados"],
     "note": ["Invented sample deed: English signature at the foot."]},
    {"no": 4, "batch": "S2", "date": "1675-11-20", "type": "Obligatie", "language": "Nederlands",
     "inv": "2", "index_id": "S-0004", "scans": [S5], "notary": "", "tier": "B",
     "mt": "none", "english": "",
     "title": None,  # no index record: the form says so
     "persons": [], "places": [], "note": []},
]
INVENTORIES = {"1": "1, Protocol van notaris Hendrick Demo, 1650-1655 (invented)",
               "2": "2, Protocol van notaris Hendrick Demo, 1656-1680 (invented)"}

# ---------- invented texts ----------
ARCHIVE_HTR = {
    S1: """Region1
Op huyden den xiiij Maert 1652 compareerde voor mij
Hendrick Demo notaris publicq bij den Hove van
Hollant geadmitteert tot Amsterdam residerende
ende de naegenoemde getuygen Jan Voorbeeld
schipper naest Godt van t schip genaemt de
Proefvaart ter eenre ende Pieter Oefening
coopman ter andere zijde ende verclaerden
geaccordeert te sijn als volcht""",
    S2: """Region1
dat de voorn schipper met den eersten goeden
wint sal zeylen naer Barbados ende aldaer
lossen ende weder laden tot behoeff van
den bevrachter Gedaen t Amsterdam
Region2
Op den selven dach compareerde Anna Proefmans
ende verclaerde ten versoecke van Jan Voorbeeld""",
    S3: """Region1
dat sij ten huyse van den comparant gesien
heeft twaelff vaten suyker gemerckt PO
Aldus gedaen ter presentie van Claes Steekproef""",
    S4: """Region1
Compareerde Thomas Example coopman van
Bridgetown op Barbados ende stelde tot sijnen
procureur Willem Oefening om te innen
alle schulden hem competerende
Thomas Example""",
}
OWN_HTR_S1 = """Region1
Op huyden den 14 Maert 1652 compareerde voor mij
Hendrick Demo notaris publicq bij den Hove van
Hollandt geadmitteert tot Amsterdam residerende
ende de naegenoemde getuygen Jan Voorbeelt
schipper naest Godt van t schip genaemt de
Proefvaert ter eenre ende Pieter Oefening
coopman ter andere sijde ende verclaerden
geaccordeert te sijn als volcht"""
TRANSLATION_S1 = [
    "1 | Today, the 14th of March 1652, there appeared before me,",
    "2-3 | Hendrick Demo, notary public admitted by the Court of Holland, residing in Amsterdam,",
    "4 | and the witnesses named below, Jan Voorbeeld,",
    "5 | master under God of the ship called the",
    "6 | *Proefvaart*, of the one part, and Pieter Oefening,",
    "7 | merchant, of the other part, and they declared",
    "8 | that they had agreed as follows",
    "5 note: \"naest Godt\": the usual formula for a ship's master.",
]
SYNTHESIS_1 = """# What the deed says (invented sample)

Jan Voorbeeld, master of *De Proefvaart*, and Pieter Oefening, merchant, agree a charter before the notary Hendrick Demo in Amsterdam on 14 March 1652.

1. The ship is to sail with the first fair wind for Barbados.
2. There it is to unload, and load again for the charterer.
3. Claes Steekproef is named as a witness.

# Check against the ink

The spelling of the master's name differs between the two HTR texts (Voorbeeld, Voorbeelt)."""
MODEL_READING_S1 = """MODEL: Model A
BASIS: I
MADE: 2026-11-25
---
A model's reading of the first lines (basis I: a lead, not a transcription):
Op huyden den xiiij Maert 1652 compareerde voor mij Hendrick Demo notaris ..."""


def lines_sha(text: str) -> str:
    """The fingerprint the builder and the form check: the HTR lines, region labels left out."""
    return hashlib.sha256("\n".join(l for l in text.split("\n") if not REG.match(l)).encode("utf-8")).hexdigest()


def jsonld(d: dict) -> dict:
    """An index record in the shape saa_jsonld.parse() reads. Identifiers are urn:sample:..., never archive addresses."""
    base = "urn:sample:" + d["index_id"]
    graph = []
    deed = {"@id": base, "@type": ["rico:Record", "rt:Deed"], "rico:title": d["title"],
            "rico:normalizedDateValue": {"@value": d["date"]},
            "rico:hasDocumentaryFormType": {"@id": base + "/type"},
            "rico:isOrWasIncludedIn": {"@id": "urn:sample:inventory-" + d["inv"]},
            "rico:hasOrHadSubject": [], "saa:isAssociatedWithLocation": [], "saa:hasSpecification": []}
    graph.append({"@id": base + "/type", "skos:prefLabel": d["type"]})
    graph.append({"@id": "urn:sample:inventory-" + d["inv"] + "/context",
                  "http://purl.org/dc/terms/title": INVENTORIES[d["inv"]]})
    for i, (name, role) in enumerate(d["persons"], 1):
        obs, pid, rid = f"{base}/obs{i}", f"{base}/person{i}", "urn:sample:role-" + role.lower()
        deed["rico:hasOrHadSubject"].append({"@id": obs})
        graph.append({"@id": obs, "@type": "saa:LinkedPersonObservation", "memorix:order": {"@value": str(i)},
                      "saa:relatedPersonObservation": {"@id": pid}, "saa:relatedPersonObservationRole": {"@id": rid}})
        graph.append({"@id": pid + "/context", "http://purl.org/dc/terms/title": name})
        graph.append({"@id": rid, "skos:prefLabel": role})
    for i, place in enumerate(d["places"], 1):
        deed["saa:isAssociatedWithLocation"].append({"@id": f"{base}/place{i}"})
        graph.append({"@id": f"{base}/place{i}", "saa:locationTextualValue": place})
    specs = [("taal", lang.strip()) for lang in d["language"].split(",")] + [("onderwerpsomschrijving", n) for n in d["note"]]
    for i, (kind, value) in enumerate(specs, 1):
        deed["saa:hasSpecification"].append({"@id": f"{base}/spec{i}"})
        graph.append({"@id": f"{base}/spec{i}", "saa:specificationType": {"@id": "urn:sample:spec-" + kind},
                      "saa:specificationTextualValue": value})
        graph.append({"@id": "urn:sample:spec-" + kind, "skos:prefLabel": kind})
    graph.append({"@id": base + "/context", "memorix:hasDigitalDocument": {"@list": [{"@id": f"{base}/scan{i}"} for i in range(len(d["scans"]))]}})
    for i, sid in enumerate(d["scans"]):
        graph.append({"@id": f"{base}/scan{i}", "http://schema.org/name": sid + ".jp2",
                      "http://schema.org/width": {"@value": "4000"}, "http://schema.org/height": {"@value": "3000"},
                      "http://schema.org/fileSize": {"@value": "2500000"}, "memorix:iiif": {"@id": ""}})
    graph.insert(0, deed)
    return {"@context": {"note": "Invented sample record for the Deed Reader; not from any archive."}, "@graph": graph}


def files() -> dict:
    """Every file to write, as {relative path: text}."""
    out = {}
    cols = ["no", "batch", "date", "deed_type", "language", "inventory", "index_id", "scans",
            "notary_per_coverage", "check_tier", "machine_text", "in_english_set_S1-05"]
    rows = [",".join(cols)]
    log = []
    for d in DEEDS:
        vals = [str(d["no"]), d["batch"], d["date"], d["type"], d["language"], d["inv"], d["index_id"],
                " ; ".join(d["scans"]), d["notary"], d["tier"], d["mt"], d["english"]]
        rows.append(",".join('"' + v + '"' if "," in v else v for v in vals))
        if d["title"]:
            fn = d["index_id"] + ".json"  # .json, so the data guard reads it too
            out["index/" + fn] = json.dumps(jsonld(d), ensure_ascii=False, indent=1) + "\n"
            log.append(json.dumps({"url": "urn:sample:index/" + d["index_id"], "status": 200, "file": fn,
                                   "started_utc": "2026-11-25T00:00:00Z (invented)"}))
    out["register.csv"] = "\n".join(rows) + "\n"
    out["index/request_log.jsonl"] = "\n".join(log) + "\n"
    for sid, text in ARCHIVE_HTR.items():
        out[f"machine_text/{sid}.txt"] = ("SOURCE: invented sample, standing in for the archive's machine text\n"
                                         "FETCHED: 2026-11-25\nBASIS: P-MUC\n---\n" + text + "\n")
    out["htr-files/own/PROVENANCE.txt"] = ("MADE_BY: the sample's author (invented)\nPLATFORM: none (typed by hand to look like HTR)\n"
                                           "MODEL: Sample HTR model\nCORRECTED: no\nBASIS: P-MUC\n")
    out[f"htr-files/own/{S1}.txt"] = "EXPORTED: 2026-11-25\n---\n" + OWN_HTR_S1 + "\n"
    out[f"translation-files/en/{S1}_en_v1.0_25112026.txt"] = (
        f"DEED: 1\nSCAN: {S1}\nLANGUAGE: en\nKIND: diplomatic\nSOURCE_KIND: HTR\n"
        f"SOURCE_FILE: machine_text/{S1}.txt\nSOURCE_SHA256: {lines_sha(ARCHIVE_HTR[S1])}\n"
        "TRANSLATOR: the sample's author (invented)\nMODEL: Model A\nMADE: 2026-11-25\nBASIS: I\n"
        "REVIEWED_BY: none\nCONVENTIONS: one English line per HTR line; ship names in italics\n---\n"
        + "\n".join(TRANSLATION_S1) + "\n")
    out["translation-files/en/deed1_synthesis_en_v1.0_25112026.md"] = (
        f"DEED: 1\nLANGUAGE: en\nKIND: synthesis\nSOURCE_FILE: machine_text/{S1}.txt\nMODEL: Model A\n"
        "MADE: 2026-11-25\nBASIS: I\nREVIEWED_BY: none\n---\n" + SYNTHESIS_1 + "\n")
    out[f"model-readings/{S1}_model_reading.txt"] = MODEL_READING_S1 + "\n"
    return out


def main() -> None:
    if OUT.exists() and "--replace" not in sys.argv:
        sys.exit(f"STOP: {OUT} exists; add --replace to rewrite the files this script owns.")
    fs = files()
    for rel, text in fs.items():
        p = OUT / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8", newline="\n")
    print("wrote", len(fs), "files under", OUT)


if __name__ == "__main__":
    main()
