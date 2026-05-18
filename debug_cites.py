from dotenv import load_dotenv
load_dotenv()
import re, requests, os, sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from graph.schema import get_driver

def clean(arxiv_id):
    return re.sub(r"v\d+$", "", arxiv_id.strip())

driver = get_driver()
with driver.session() as s:
    ids = [r["id"] for r in s.run("MATCH (p:Paper) RETURN p.arxiv_id AS id LIMIT 5")]
driver.close()

print("=== IDs dans Neo4j ===")
for i in ids:
    print(f"  raw: {i!r}  ->  clean: {clean(i)!r}")

clean_id = clean(ids[0])
print(f"\n=== References S2 pour arXiv:{clean_id} ===")
url = f"https://api.semanticscholar.org/graph/v1/paper/arXiv:{clean_id}"
r = requests.get(url,
    params={"fields": "references.externalIds"},
    headers={"x-api-key": os.getenv("SEMANTIC_SCHOLAR_API_KEY", "")},
    timeout=15)

if r.status_code != 200:
    print(f"Erreur S2: {r.status_code}")
else:
    refs = r.json().get("references", [])[:5]
    if not refs:
        print("  Aucune reference retournee")
    for ref in refs:
        ext = ref.get("externalIds") or {}
        print(f"  ArXiv ID: {ext.get('ArXiv', 'ABSENT')!r}")

sample = ids[0]
print("\n=== Diagnostic ===")
if re.search(r"v\d+$", sample):
    print(f"Neo4j stocke AVEC version  ex: {sample!r}")
else:
    print(f"Neo4j stocke SANS version  ex: {sample!r}")