"""Query GBIF Species Match API for all 11 dataset species."""
import json
import urllib.request

species = [
    ("Picea abies", "Norway spruce"),
    ("Abies alba", "Silver fir"),
    ("Pinus sylvestris", "Scots pine"),
    ("Pseudotsuga menziesii", "Douglas fir"),
    ("Fagus sylvatica", "European beech"),
    ("Quercus robur", "European oak"),
    ("Acer pseudoplatanus", "Sycamore maple"),
    ("Fraxinus excelsior", "Common ash"),
    ("Betula pendula", "Silver birch"),
    ("Tilia cordata", "Small-leaved linden"),
    ("Prunus avium", "Wild cherry"),
]

results = []
for sci, common in species:
    name_encoded = sci.replace(" ", "+")
    url = f"https://api.gbif.org/v1/species/match?name={name_encoded}"
    r = urllib.request.urlopen(url)
    d = json.loads(r.read())
    key = d.get("usageKey", "N/A")
    status = d.get("status", "?")
    results.append((common, sci, key, status))
    print(f"{common:20s} ({sci:25s}): {key} [{status}]")

# Write CSV-compatible output
print("\n--- CSV OUTPUT ---")
print("Common Name,Scientific Name,GBIF Key,GBIF Status")
for common, sci, key, status in results:
    print(f"{common},{sci},{key},{status}")
