import argparse
import csv
import re
import time
from urllib.parse import quote
from xml.sax.saxutils import escape

MAP_NAME = "Cat Map Project"

# Use raw.githubusercontent.com (serves the image itself; github.com/.../blob/... serves an HTML page)
ICON_BASE = "https://raw.githubusercontent.com/nazelizurna/cat-map-project/main/assests/"

# Place type -> (icon file, folder name)
TYPES = {
    "City":                ("city.png",       "Cities"),
    "Island":              ("island.png",     "Islands"),
    "Village":             ("village.png",    "Villages"),
    "Sanctuary":           ("sanctuary.png",  "Sanctuaries"),
    "Museum":              ("museum.png",     "Museums"),
    "Park":                ("park.png",       "Parks"),
    "Historic Site":       ("historical.png", "Historic Sites"),
    "Temple/Shrine":       ("shrine.png",     "Temples & Shrines"),
    "Pub/Bar":             ("pub.png",        "Pubs & Bars"),
    "Cafe":                ("cafe.png",       "Cafes"),
    "Festival":            ("festival.png",   "Festivals"),
    "Festival/Convention": ("conventions.png",   "Conventions"),
}


def style_id(ptype):
    return re.sub(r"[^a-zA-Z0-9]", "_", ptype)


def read_places(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        return [{k.strip(): (v or "").strip() for k, v in row.items()} for row in csv.DictReader(f)]


def geocode_missing(places):
    """Fill blank Lat/Lon using OpenStreetMap Nominatim (1 request/second, per their usage policy)."""
    from geopy.geocoders import Nominatim
    geo = Nominatim(user_agent="cat-map-kml-builder")
    for p in places:
        if p.get("Lat") and p.get("Lon"):
            continue
        for query in (p["Address"], f'{p["Name"]}, {p["Location"]}, {p["Country"]}', f'{p["Location"]}, {p["Country"]}'):
            hit = geo.geocode(query)
            time.sleep(1.1)
            if hit:
                p["Lat"], p["Lon"] = f"{hit.latitude:.6f}", f"{hit.longitude:.6f}"
                print(f"  geocoded {p['Name']}: {p['Lat']}, {p['Lon']}")
                break
        else:
            print(f"  WARNING: could not geocode {p['Name']}")


def build_kml(places):
    out = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<kml xmlns="http://www.opengis.net/kml/2.2">',
        "  <Document>",
        f"    <name>{escape(MAP_NAME)}</name>",
    ]
    for ptype, (icon, _) in TYPES.items():
        out += [
            f'    <Style id="{style_id(ptype)}">',
            "      <IconStyle>",
            "        <scale>1.1</scale>",
            f"        <Icon><href>{escape(ICON_BASE + quote(icon))}</href></Icon>",
            "      </IconStyle>",
            "    </Style>",
        ]

    skipped = []
    for ptype, (_, folder) in TYPES.items():
        items = [p for p in places if p["Type"] == ptype]
        if not items:
            continue
        out += ["    <Folder>", f"      <name>{escape(folder)}</name>"]
        for p in items:
            if not (p.get("Lat") and p.get("Lon")):
                skipped.append(p["Name"])
                continue
            desc = f"Type: {ptype}\nRegion: {p['Location']}, {p['Country']}\nAddress: {p['Address']}"
            out += [
                "      <Placemark>",
                f"        <name>{escape(p['Name'])}</name>",
                f"        <description>{escape(desc)}</description>",
                f"        <styleUrl>#{style_id(ptype)}</styleUrl>",
                f"        <Point><coordinates>{p['Lon']},{p['Lat']},0</coordinates></Point>",
                "      </Placemark>",
            ]
        out.append("    </Folder>")

    unknown = {p["Type"] for p in places} - set(TYPES)
    if unknown:
        print(f"WARNING: unknown types skipped (add them to TYPES): {sorted(unknown)}")
    if skipped:
        print(f"WARNING: no coordinates, skipped: {skipped} (re-run with --geocode)")

    out += ["  </Document>", "</kml>"]
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-i", "--input", default="cat_places.csv")
    ap.add_argument("-o", "--output", default="cat_places.kml")
    ap.add_argument("--geocode", action="store_true", help="fill blank Lat/Lon from Address (needs geopy)")
    args = ap.parse_args()

    places = read_places(args.input)
    if args.geocode:
        geocode_missing(places)
        # save found coordinates back to the CSV so they are only looked up once
        cols = ["Name", "Location", "Country", "Type", "Address", "Lat", "Lon"]
        with open(args.input, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
            w.writeheader()
            w.writerows(places)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(build_kml(places))
    print(f"Wrote {args.output} ({len(places)} places read)")


if __name__ == "__main__":
    main()
