/* Deed Reader data, built from local files only. Do not edit by hand: re-run build_deed_data.py. */
window.DEED_DATA = {
"ui": {
"title": "Deed Reader (sample)",
"period": "1630–1680",
"collection": "Invented sample collection",
"collection_short": "Sample",
"image_credit": "",
"models": [
"Model A",
"Model B"
],
"storage_key": "deedreader-sample",
"workdir": "deed-reader",
"first_deed": 1,
"default_batch": "",
"help_deeds": "Sample: four invented deeds on five scans, without images.",
"variants": [
[
"voorbeeld",
"voorbeelt"
],
[
"proefvaart",
"proefvaert"
],
[
"holland",
"hollant",
"hollandt"
]
]
},
"sample": true,
"translation_summary": {
"diplomatic": 1,
"synthesis": 1,
"files": [
"translation-files/en/DEED_0001_synthesis_en_v1.0_25112026.md",
"translation-files/en/DEMO00000000001_en_v1.0_25112026.txt"
],
"superseded": []
},
"built": "2026-11-25 09:10",
"builder": "deed-reader/build_deed_data.py",
"register": "register.csv",
"htr_summary": {
"pages": 5,
"by_source": {
"own_transkribus": 1,
"saa_transkribus_sites": 4
},
"deeds_with_htr": [
1,
2,
3
],
"unplaced_files": []
},
"deeds": [
{
"no": 1,
"batch": "S1",
"date": "1652-03-14",
"type": "Bevrachting",
"language": "Nederlands",
"inventory": "1",
"notary": "Hendrick Demo",
"check_tier": "A",
"machine_text_archive": "HTR",
"english_set": "yes",
"index_id": "S-0001",
"meta": {
"title": "Bevrachting van het schip De Proefvaart naar Barbados (invented)",
"date": "1652-03-14",
"type": "Bevrachting",
"inventory": "1",
"inventory_title": "1, Protocol van notaris Hendrick Demo, 1650-1655 (invented)",
"language": [
"Nederlands"
],
"persons": [
{
"order": 1,
"name": "Jan Voorbeeld",
"role": "Schipper"
},
{
"order": 2,
"name": "Pieter Oefening",
"role": "Bevrachter"
},
{
"order": 3,
"name": "Claes Steekproef",
"role": "Getuige"
}
],
"places": [
"Amsterdam",
"Barbados"
],
"note": [
"Invented sample deed: charter of De Proefvaart, Amsterdam to Barbados and back."
],
"other_fields": {},
"record_url": "",
"index_uri": "urn:sample:index/S-0001",
"index_file": "index/S-0001.json",
"fetched_utc": "2026-11-25T00:00:00Z (invented)"
},
"scans": [
{
"id": "DEMO00000000001",
"w": 4000,
"h": 3000,
"jp2_bytes": 2500000,
"file": "",
"other_files": [],
"machine_text": [
{
"file": "machine_text/DEMO00000000001.txt",
"header": "SOURCE: invented sample, standing in for the archive's machine text\nFETCHED: 2026-11-25\nBASIS: P-MUC",
"text": "Region1\nOp huyden den xiiij Maert 1652 compareerde voor mij\nHendrick Demo notaris publicq bij den Hove van\nHollant geadmitteert tot Amsterdam residerende\nende de naegenoemde getuygen Jan Voorbeeld\nschipper naest Godt van t schip genaemt de\nProefvaart ter eenre ende Pieter Oefening\ncoopman ter andere zijde ende verclaerden\ngeaccordeert te sijn als volcht",
"sha256": "2dbb4dc3192105536afaac4dd8615571e782da372ef89315d34ba89582f42c48",
"source": "saa_transkribus_sites",
"prov": {
"label": "Archive HTR (sample)",
"made_by": "invented: stands in for the archive",
"platform": "none",
"model": "not stated",
"corrected": "no",
"fetched": "2026-11-25",
"route": "",
"basis": "P-MUC",
"basis_note": "P-MUC",
"url": "",
"document": "invented sample, standing in for the archive's machine text"
}
},
{
"header": "EXPORTED: 2026-11-25",
"text": "Region1\nOp huyden den 14 Maert 1652 compareerde voor mij\nHendrick Demo notaris publicq bij den Hove van\nHollandt geadmitteert tot Amsterdam residerende\nende de naegenoemde getuygen Jan Voorbeelt\nschipper naest Godt van t schip genaemt de\nProefvaert ter eenre ende Pieter Oefening\ncoopman ter andere sijde ende verclaerden\ngeaccordeert te sijn als volcht",
"file": "htr-files/own/DEMO00000000001.txt",
"sha256": "4cabcdc215e4a3c9853c5ed81c6b411979c5734ecd5399d2429d843dce9ac6e0",
"source": "own_transkribus",
"prov": {
"label": "Own HTR (sample) · Sample HTR model",
"made_by": "the sample's author (invented)",
"platform": "none (typed by hand to look like HTR)",
"model": "Sample HTR model",
"corrected": "no",
"fetched": "2026-11-25",
"route": "",
"basis": "P-MUC",
"basis_note": "P-MUC",
"url": "",
"document": ""
}
}
],
"model_readings": [
{
"file": "model-readings/DEMO00000000001_model_reading.txt",
"header": "MODEL: Model A\nBASIS: I\nMADE: 2026-11-25",
"text": "A model's reading of the first lines (basis I: a lead, not a transcription):\nOp huyden den xiiij Maert 1652 compareerde voor mij Hendrick Demo notaris ...",
"sha256": "03bab71a7a62ca6f8d8be6e2d60d0ad2333f93f9e832909608e763da9ca0e691"
}
],
"also_in": [],
"translations": [
{
"file": "translation-files/en/DEMO00000000001_en_v1.0_25112026.txt",
"lang": "en",
"kind": "diplomatic",
"prov": {
"DEED": "1",
"SCAN": "DEMO00000000001",
"LANGUAGE": "en",
"KIND": "diplomatic",
"SOURCE_KIND": "HTR",
"SOURCE_FILE": "machine_text/DEMO00000000001.txt",
"SOURCE_SHA256": "8fedf446620bb17dfa20b230270702a33bc094e4d8aa2fd39ca40c4622547b61",
"TRANSLATOR": "the sample's author (invented)",
"MODEL": "Model A",
"MADE": "2026-11-25",
"BASIS": "I",
"REVIEWED_BY": "none",
"CONVENTIONS": "one English line per HTR line; ship names in italics"
},
"header": "DEED: 1\nSCAN: DEMO00000000001\nLANGUAGE: en\nKIND: diplomatic\nSOURCE_KIND: HTR\nSOURCE_FILE: machine_text/DEMO00000000001.txt\nSOURCE_SHA256: 8fedf446620bb17dfa20b230270702a33bc094e4d8aa2fd39ca40c4622547b61\nTRANSLATOR: the sample's author (invented)\nMODEL: Model A\nMADE: 2026-11-25\nBASIS: I\nREVIEWED_BY: none\nCONVENTIONS: one English line per HTR line; ship names in italics",
"sha256": "51b5ed61779f2b45ffe17c77a68250a61feaec6f72d8e31ee4d47f2a1af4821b",
"lines": {
"1": "Today, the 14th of March 1652, there appeared before me,",
"4": "and the witnesses named below, Jan Voorbeeld,",
"5": "master under God of the ship called the",
"6": "*Proefvaart*, of the one part, and Pieter Oefening,",
"7": "merchant, of the other part, and they declared",
"8": "that they had agreed as follows"
},
"ranges": [
{
"from": 2,
"to": 3,
"text": "Hendrick Demo, notary public admitted by the Court of Holland, residing in Amsterdam,"
}
],
"notes": {
"5": [
"\"naest Godt\": the usual formula for a ship's master."
]
},
"check": {
"source_found": true,
"source_lines": 8,
"missing": [],
"extra": [],
"sha_now": "8fedf446620bb17dfa20b230270702a33bc094e4d8aa2fd39ca40c4622547b61",
"sha_match": true
}
}
]
},
{
"id": "DEMO00000000002",
"w": 4000,
"h": 3000,
"jp2_bytes": 2500000,
"file": "",
"other_files": [],
"machine_text": [
{
"file": "machine_text/DEMO00000000002.txt",
"header": "SOURCE: invented sample, standing in for the archive's machine text\nFETCHED: 2026-11-25\nBASIS: P-MUC",
"text": "Region1\ndat de voorn schipper met den eersten goeden\nwint sal zeylen naer Barbados ende aldaer\nlossen ende weder laden tot behoeff van\nden bevrachter Gedaen t Amsterdam\nRegion2\nOp den selven dach compareerde Anna Proefmans\nende verclaerde ten versoecke van Jan Voorbeeld",
"sha256": "b9682e23fe4af338a3176241a7c633bc7a2b3421192e92528a8341c06c8b7d4d",
"source": "saa_transkribus_sites",
"prov": {
"label": "Archive HTR (sample)",
"made_by": "invented: stands in for the archive",
"platform": "none",
"model": "not stated",
"corrected": "no",
"fetched": "2026-11-25",
"route": "",
"basis": "P-MUC",
"basis_note": "P-MUC",
"url": "",
"document": "invented sample, standing in for the archive's machine text"
}
}
],
"model_readings": [],
"also_in": [
2
],
"translations": []
}
],
"how_found": "invented for the sample",
"syntheses": [
{
"file": "translation-files/en/DEED_0001_synthesis_en_v1.0_25112026.md",
"lang": "en",
"kind": "synthesis",
"prov": {
"DEED": "1",
"LANGUAGE": "en",
"KIND": "synthesis",
"SOURCE_FILE": "machine_text/DEMO00000000001.txt",
"MODEL": "Model A",
"MADE": "2026-11-25",
"BASIS": "I",
"REVIEWED_BY": "none"
},
"header": "DEED: 1\nLANGUAGE: en\nKIND: synthesis\nSOURCE_FILE: machine_text/DEMO00000000001.txt\nMODEL: Model A\nMADE: 2026-11-25\nBASIS: I\nREVIEWED_BY: none",
"sha256": "f94454f599cdd2648453cd5bd0870b9234ffe093bac65ecca50f47cef87f200a",
"text": "# What the deed says (invented sample)\n\nJan Voorbeeld, master of *De Proefvaart*, and Pieter Oefening, merchant, agree a charter before the notary Hendrick Demo in Amsterdam on 14 March 1652.\n\n1. The ship is to sail with the first fair wind for Barbados.\n2. There it is to unload, and load again for the charterer.\n3. Claes Steekproef is named as a witness.\n\n# Check against the ink\n\nThe spelling of the master's name differs between the two HTR texts (Voorbeeld, Voorbeelt)."
}
]
},
{
"no": 2,
"batch": "S1",
"date": "1652-03-14",
"type": "Verklaring",
"language": "Nederlands",
"inventory": "1",
"notary": "Hendrick Demo",
"check_tier": "B",
"machine_text_archive": "HTR",
"english_set": "",
"index_id": "S-0002",
"meta": {
"title": "Verklaring over de lading van De Proefvaart (invented)",
"date": "1652-03-14",
"type": "Verklaring",
"inventory": "1",
"inventory_title": "1, Protocol van notaris Hendrick Demo, 1650-1655 (invented)",
"language": [
"Nederlands"
],
"persons": [
{
"order": 1,
"name": "Anna Proefmans",
"role": "Comparant"
},
{
"order": 2,
"name": "Jan Voorbeeld",
"role": "Genoemd"
}
],
"places": [
"Amsterdam"
],
"note": [
"Invented sample deed: it begins on the scan where deed 1 ends."
],
"other_fields": {},
"record_url": "",
"index_uri": "urn:sample:index/S-0002",
"index_file": "index/S-0002.json",
"fetched_utc": "2026-11-25T00:00:00Z (invented)"
},
"scans": [
{
"id": "DEMO00000000002",
"w": 4000,
"h": 3000,
"jp2_bytes": 2500000,
"file": "",
"other_files": [],
"machine_text": [
{
"file": "machine_text/DEMO00000000002.txt",
"header": "SOURCE: invented sample, standing in for the archive's machine text\nFETCHED: 2026-11-25\nBASIS: P-MUC",
"text": "Region1\ndat de voorn schipper met den eersten goeden\nwint sal zeylen naer Barbados ende aldaer\nlossen ende weder laden tot behoeff van\nden bevrachter Gedaen t Amsterdam\nRegion2\nOp den selven dach compareerde Anna Proefmans\nende verclaerde ten versoecke van Jan Voorbeeld",
"sha256": "b9682e23fe4af338a3176241a7c633bc7a2b3421192e92528a8341c06c8b7d4d",
"source": "saa_transkribus_sites",
"prov": {
"label": "Archive HTR (sample)",
"made_by": "invented: stands in for the archive",
"platform": "none",
"model": "not stated",
"corrected": "no",
"fetched": "2026-11-25",
"route": "",
"basis": "P-MUC",
"basis_note": "P-MUC",
"url": "",
"document": "invented sample, standing in for the archive's machine text"
}
}
],
"model_readings": [],
"also_in": [
1
],
"translations": []
},
{
"id": "DEMO00000000003",
"w": 4000,
"h": 3000,
"jp2_bytes": 2500000,
"file": "",
"other_files": [],
"machine_text": [
{
"file": "machine_text/DEMO00000000003.txt",
"header": "SOURCE: invented sample, standing in for the archive's machine text\nFETCHED: 2026-11-25\nBASIS: P-MUC",
"text": "Region1\ndat sij ten huyse van den comparant gesien\nheeft twaelff vaten suyker gemerckt PO\nAldus gedaen ter presentie van Claes Steekproef",
"sha256": "869a91597f7712b4eca03fe3a8a599a2925d589e73bd5c324c8184869165fc39",
"source": "saa_transkribus_sites",
"prov": {
"label": "Archive HTR (sample)",
"made_by": "invented: stands in for the archive",
"platform": "none",
"model": "not stated",
"corrected": "no",
"fetched": "2026-11-25",
"route": "",
"basis": "P-MUC",
"basis_note": "P-MUC",
"url": "",
"document": "invented sample, standing in for the archive's machine text"
}
}
],
"model_readings": [],
"also_in": [],
"translations": []
}
],
"how_found": "invented for the sample",
"syntheses": []
},
{
"no": 3,
"batch": "S2",
"date": "1660-07-02",
"type": "Procuratie",
"language": "Nederlands, Engels",
"inventory": "2",
"notary": "Hendrick Demo",
"check_tier": "A",
"machine_text_archive": "HTR",
"english_set": "yes",
"index_id": "S-0003",
"meta": {
"title": "Procuratie van Thomas Example op Willem Oefening (invented)",
"date": "1660-07-02",
"type": "Procuratie",
"inventory": "2",
"inventory_title": "2, Protocol van notaris Hendrick Demo, 1656-1680 (invented)",
"language": [
"Nederlands",
"Engels"
],
"persons": [
{
"order": 1,
"name": "Thomas Example",
"role": "Lastgever"
},
{
"order": 2,
"name": "Willem Oefening",
"role": "Gemachtigde"
}
],
"places": [
"Amsterdam",
"Bridgetown, Barbados"
],
"note": [
"Invented sample deed: English signature at the foot."
],
"other_fields": {},
"record_url": "",
"index_uri": "urn:sample:index/S-0003",
"index_file": "index/S-0003.json",
"fetched_utc": "2026-11-25T00:00:00Z (invented)"
},
"scans": [
{
"id": "DEMO00000000004",
"w": 4000,
"h": 3000,
"jp2_bytes": 2500000,
"file": "",
"other_files": [],
"machine_text": [
{
"file": "machine_text/DEMO00000000004.txt",
"header": "SOURCE: invented sample, standing in for the archive's machine text\nFETCHED: 2026-11-25\nBASIS: P-MUC",
"text": "Region1\nCompareerde Thomas Example coopman van\nBridgetown op Barbados ende stelde tot sijnen\nprocureur Willem Oefening om te innen\nalle schulden hem competerende\nThomas Example",
"sha256": "d4cb26dc25a21b54f974e6e392424dadf565eff0894f755429e99a96367d4759",
"source": "saa_transkribus_sites",
"prov": {
"label": "Archive HTR (sample)",
"made_by": "invented: stands in for the archive",
"platform": "none",
"model": "not stated",
"corrected": "no",
"fetched": "2026-11-25",
"route": "",
"basis": "P-MUC",
"basis_note": "P-MUC",
"url": "",
"document": "invented sample, standing in for the archive's machine text"
}
}
],
"model_readings": [],
"also_in": [],
"translations": []
}
],
"how_found": "invented for the sample",
"syntheses": []
},
{
"no": 4,
"batch": "S2",
"date": "1675-11-20",
"type": "Obligatie",
"language": "Nederlands",
"inventory": "2",
"notary": "",
"check_tier": "B",
"machine_text_archive": "none",
"english_set": "",
"index_id": "S-0004",
"meta": null,
"scans": [
{
"id": "DEMO00000000005",
"w": 0,
"h": 0,
"jp2_bytes": 0,
"file": "",
"other_files": [],
"machine_text": [],
"model_readings": [],
"also_in": [],
"translations": []
}
],
"how_found": "invented for the sample",
"syntheses": []
}
],
"problems": [
"deed 4: no index record on disk"
]
};
