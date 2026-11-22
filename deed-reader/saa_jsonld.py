"""Read one Stadsarchief Amsterdam index record (JSON-LD, as the archive's Elements API returns it).

Part of the Deed Reader (crash-2026). Standard library only. Sends no request: it reads a saved file.
parse() and aslist() are taken unchanged from Build_Barbados_Register v0.1 (11 Nov 2026,
Claude Opus 5.5 for Colin Greenstreet); nothing else from that script is used.
Every value it returns is index level (basis A): what the archive's index says, not a reading of the deed.
"""
import json
import pathlib

_RES = "https://id.archief.amsterdam/"
_REC = "https://id.archief.amsterdam/resources/records/"


def aslist(x):
    """JSON-LD gives a single value as a dict and several as a list."""
    if x is None:
        return []
    return x if isinstance(x, list) else [x]


def parse(path: pathlib.Path) -> dict:
    """Title, date, type, persons (in index order), places, specifications, inventory and scans of one deed."""
    d = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    g = {n["@id"]: n for n in d["@graph"]}
    label = lambda i: g.get(i, {}).get("skos:prefLabel", "")
    context = lambda i: g.get(i.replace(_RES, _REC) + "/context", {})
    deed = next(n for n in d["@graph"]
                if isinstance(n.get("@type"), list) and "rt:Deed" in n["@type"])
    persons = []
    for s in aslist(deed.get("rico:hasOrHadSubject")):
        n = g.get(s["@id"], {})
        if n.get("@type") != "saa:LinkedPersonObservation":
            continue
        pid = n["saa:relatedPersonObservation"]["@id"]
        name = context(pid).get("http://purl.org/dc/terms/title", "?")
        role = label(n.get("saa:relatedPersonObservationRole", {}).get("@id", ""))
        order = int(n.get("memorix:order", {}).get("@value", 0))
        persons.append((order, name, role))
    persons.sort()
    locs = [g.get(l["@id"], {}).get("saa:locationTextualValue", "")
            for l in aslist(deed.get("saa:isAssociatedWithLocation"))]
    specs = {}
    for s in aslist(deed.get("saa:hasSpecification")):
        n = g.get(s["@id"], {})
        specs.setdefault(label(n.get("saa:specificationType", {}).get("@id", "")), []
                         ).append(n.get("saa:specificationTextualValue", ""))
    file_id = deed.get("rico:isOrWasIncludedIn", {}).get("@id", "")
    inv_title = context(file_id).get("http://purl.org/dc/terms/title", "") if file_id else ""
    inv = inv_title.split(",")[0].strip() if inv_title else ""
    ctx = context(deed["@id"])
    assets = [g.get(a["@id"], {}) for a in aslist(ctx.get("memorix:hasDigitalDocument", {}).get("@list"))]
    scans = [{
        "name": a.get("http://schema.org/name", "").replace(".jp2", ""),
        "w": int(a.get("http://schema.org/width", {}).get("@value", 0)),
        "h": int(a.get("http://schema.org/height", {}).get("@value", 0)),
        "bytes": int(a.get("http://schema.org/fileSize", {}).get("@value", 0)),
        "iiif": a.get("memorix:iiif", {}).get("@id", ""),
    } for a in assets]
    return {
        "title": deed.get("rico:title", ""),
        "date_index": deed.get("rico:normalizedDateValue", {}).get("@value", ""),
        "type_index": label(deed.get("rico:hasDocumentaryFormType", {}).get("@id", "")),
        "persons": persons, "locs": locs, "specs": specs,
        "inv": inv, "inv_title": inv_title.replace("\n", " "), "scans": scans,
    }
