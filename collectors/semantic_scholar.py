import requests
import json
import os
import time
from tqdm import tqdm

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import DATA_RAW_PATH
from config.logging_config import setup_logger

logger = setup_logger("crossref_collector")

BASE_URL = "https://api.crossref.org/works"
HEADERS  = {"User-Agent": "ScientificGraph/1.0 (mailto:student@univ.dz)"}


def get_paper_by_doi(doi: str) -> dict | None:
    """Recupere les details d'un paper via DOI depuis CrossRef"""
    if not doi:
        return None
    try:
        url      = f"{BASE_URL}/{doi}"
        response = requests.get(url, headers=HEADERS, timeout=10)
        if response.status_code == 200:
            return response.json().get("message", {})
        return None
    except Exception as e:
        logger.error(f"Erreur DOI {doi} : {e}")
        return None


def get_paper_by_title(title: str) -> dict | None:
    """Recherche un paper par titre sur CrossRef"""
    try:
        params = {
            "query.title" : title,
            "rows"        : 1,
            "select"      : "DOI,title,author,published,is-referenced-by-count,reference-count,container-title,reference"
        }
        response = requests.get(BASE_URL, headers=HEADERS, params=params, timeout=10)
        if response.status_code == 200:
            items = response.json().get("message", {}).get("items", [])
            if items:
                return items[0]
        return None
    except Exception as e:
        logger.error(f"Erreur title search '{title[:40]}' : {e}")
        return None


def extract_crossref_data(cr_data: dict) -> dict:
    """Extrait les champs utiles depuis la reponse CrossRef"""
    if not cr_data:
        return {}

    # references
    references = []
    for ref in cr_data.get("reference", []):
        doi = ref.get("DOI", "")
        if doi:
            references.append(doi)

    # venue
    container = cr_data.get("container-title", [])
    venue = container[0] if container else ""

    # date
    published = cr_data.get("published", {})
    date_parts = published.get("date-parts", [[]])[0]
    year = date_parts[0] if date_parts else None

    return {
        "crossref_doi"     : cr_data.get("DOI", ""),
        "citation_count"   : cr_data.get("is-referenced-by-count", 0),
        "reference_count"  : cr_data.get("reference-count", 0),
        "venue"            : venue,
        "year_crossref"    : year,
        "references_dois"  : references[:50]
    }


def enrich_papers(papers: list[dict], max_papers: int = 500) -> list[dict]:
    """Enrichit les papers arXiv avec CrossRef"""
    enriched = []

    sample = papers[:max_papers]

    for paper in tqdm(sample, desc="Enrichissement CrossRef"):
        doi   = paper.get("doi", "")
        title = paper.get("title", "")

        # essai par DOI d'abord, sinon par titre
        cr_data = get_paper_by_doi(doi) if doi else get_paper_by_title(title)
        crossref_info = extract_crossref_data(cr_data)

        enriched.append({**paper, "crossref_data": crossref_info})
        time.sleep(0.2)   # CrossRef : max 50 req/s sans key

    logger.info(f"Enrichissement termine — {len(enriched)} papers")
    return enriched


def run_crossref_collection(input_file: str = None) -> list[dict]:
    """Pipeline complet"""
    if input_file is None:
        input_file = os.path.join(DATA_RAW_PATH, "all_papers.json")

    print(f"Chargement : {input_file}")
    with open(input_file, "r", encoding="utf-8") as f:
        papers = json.load(f)

    print(f"{len(papers)} papers charges — enrichissement CrossRef...")
    enriched = enrich_papers(papers, max_papers=500)

    output_path = os.path.join(DATA_RAW_PATH, "enriched_papers.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(enriched, f, ensure_ascii=False, indent=2)

    print(f"Sauvegarde : {output_path}")
    return enriched


if __name__ == "__main__":
    print("Demarrage enrichissement CrossRef...")
    enriched = run_crossref_collection()
    print(f"Total enrichi : {len(enriched)} papers")
    print("Termine !")