import requests, zipfile, io, csv

url = "https://www.cftc.gov/files/dea/history/fut_disagg_txt_2025.zip"
resp = requests.get(url, timeout=30)
z = zipfile.ZipFile(io.BytesIO(resp.content))
content = z.read(z.namelist()[0]).decode("utf-8", errors="replace")

reader = csv.reader(content.strip().split("\n"))
rows = list(reader)

print(f"Total rows: {len(rows)}")
print(f"\nHeader:\n{rows[0][:5]}")
print(f"\nAll unique market names (first 50):")

names = sorted(set(row[0] for row in rows[1:] if row))
for name in names[:50]:
    print(" ", name)