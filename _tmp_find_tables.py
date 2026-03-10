import urllib.request, json

url = 'http://yieldtables.org/v1/yield-tables-meta/'
req = urllib.request.Request(url, headers={'Accept': 'application/json', 'User-Agent': 'growpy/1.0'})
resp = urllib.request.urlopen(req)
data = json.loads(resp.read())

# Search for maple/acer
for t in data:
    title = t.get('title', '')
    if any(x in title.lower() for x in ['ahorn', 'maple', 'acer', 'berg']):
        print(f"ID {t['id']:3d}: {title}")

# Also get yield classes for our chosen tables
print("\n--- Checking yield classes ---")
tables_to_check = {
    "Fichte Bayern": 2,
    "Buche Braunschweig": 10,
    "Eiche": 11,
    "Birke": 21,
    "Esche": 12,
    "Tanne NWD": 5,
    "Kiefer": 9,
}
for name, tid in tables_to_check.items():
    url2 = f'http://yieldtables.org/v1/yield-tables/{tid}/'
    req2 = urllib.request.Request(url2, headers={'Accept': 'application/json', 'User-Agent': 'growpy/1.0'})
    resp2 = urllib.request.urlopen(req2)
    tdata = json.loads(resp2.read())
    ycs = [yc.get('yield_class') for yc in tdata.get('data', {}).get('yield_classes', [])]
    print(f"  {name} (ID {tid}): YC {ycs}")
