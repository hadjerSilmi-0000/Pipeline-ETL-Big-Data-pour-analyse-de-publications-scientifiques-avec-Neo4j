"""
fetch_citations.py — Script one-shot
Recupere les citations depuis Semantic Scholar (avec API key)
et charge les relations CITES dans Neo4j.

Usage :
    python fetch_citations.py
    python fetch_citations.py --limit 20   # tester sur 20 papers d'abord
"""

import os
import sys
import time
import argparse
import requests
from tqdm import tqdm
from dotenv import load_dotenv

load_dotenv()

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from graph.schema import get_driver
from config.logging_config import setup_logger

logger = setup_logger("fetch_citations")

S2_BASE    = "https://api.semanticscholar.org/graph/v1/paper"
DELAY      = 1.1
BATCH_SIZE = 50
HEADERS    = {"x-api-key": os.getenv("SEMANTIC_SCHOLAR_API_KEY", "")}


# ─── Semantic Scholar ─────────────────────────────────────────────────────────

def clean_arxiv_id(arxiv_id: str) -> str:
    """Supprime le suffixe de version : 0904.3664v1 → 0904.3664"""
    return arxiv_id.split("v")[0]


def get_s2_data(arxiv_id: str) -> dict:
    clean_id = clean_arxiv_id(arxiv_id)
    url      = f"{S2_BASE}/arXiv:{clean_id}"
    params   = {"fields": "citationCount,citations.externalIds,references.externalIds"}

    empty = {"citations": [], "references": [], "citation_count": 0}

    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=15)

        if r.status_code == 404:
            return empty

        if r.status_code == 429:
            logger.warning("Rate limit atteint — pause 60s")
            time.sleep(60)
            return get_s2_data(arxiv_id)

        if r.status_code != 200:
            logger.warning(f"S2 {r.status_code} pour {clean_id}")
            return empty

        data = r.json()

        if not isinstance(data, dict):
            return empty

        citations = [
            c["externalIds"]["ArXiv"]
            for c in (data.get("citations") or [])
            if c and isinstance(c, dict)
            and isinstance(c.get("externalIds"), dict)
            and c["externalIds"].get("ArXiv")
        ]

        references = [
            ref["externalIds"]["ArXiv"]
            for ref in (data.get("references") or [])
            if ref and isinstance(ref, dict)
            and isinstance(ref.get("externalIds"), dict)
            and ref["externalIds"].get("ArXiv")
        ]

        return {
            "citations"     : citations,
            "references"    : references,
            "citation_count": data.get("citationCount") or 0
        }

    except requests.exceptions.Timeout:
        logger.warning(f"Timeout pour {arxiv_id}")
        return empty
    except Exception as e:
        logger.error(f"Erreur S2 {arxiv_id} : {e}")
        return empty


# ─── Neo4j ────────────────────────────────────────────────────────────────────

def get_all_arxiv_ids(driver) -> list[str]:
    query = "MATCH (p:Paper) RETURN p.arxiv_id AS arxiv_id ORDER BY p.arxiv_id"
    with driver.session() as session:
        return [r["arxiv_id"] for r in session.run(query)]


def update_citation_count(session, arxiv_id: str, count: int):
    session.run(
        "MATCH (p:Paper {arxiv_id: $id}) SET p.citation_count = $count",
        id=arxiv_id, count=count
    )


def load_cites_relations(session, rows: list[dict]):
    """
    Cree les relations CITES.
    Cherche les papers en ignorant le suffixe de version (v1, v2...).
    """
    query = """
    UNWIND $rows AS row
    MATCH (p1:Paper) WHERE p1.arxiv_id STARTS WITH row.from
    MATCH (p2:Paper) WHERE p2.arxiv_id STARTS WITH row.to
    MERGE (p1)-[:CITES]->(p2)
    """
    session.run(query, rows=rows)


# ─── Pipeline ────────────────────────────────────────────────────────────────

def run(limit: int = None):
    driver  = get_driver()
    all_ids = get_all_arxiv_ids(driver)

    if limit:
        all_ids = all_ids[:limit]

    # construire un set des clean IDs presents dans le graphe (pour filtrage rapide)
    clean_ids_in_graph = {clean_arxiv_id(aid) for aid in all_ids}

    api_key = os.getenv("SEMANTIC_SCHOLAR_API_KEY", "")
    print(f"\nAPI key : {'OK (' + api_key[:12] + '...)' if api_key else 'ABSENTE — verifier .env'}")
    print(f"{len(all_ids)} papers a traiter")
    print(f"Delai entre requetes : {DELAY}s")
    print(f"Duree estimee : ~{len(all_ids) * DELAY / 60:.0f} minutes\n")

    total_cites = 0
    total_refs  = 0
    cites_batch = []
    not_found   = 0

    with driver.session() as session:
        for arxiv_id in tqdm(all_ids, desc="Fetch S2"):
            data = get_s2_data(arxiv_id)

            if data["citation_count"]:
                update_citation_count(session, arxiv_id, data["citation_count"])

            clean_src = clean_arxiv_id(arxiv_id)

            # references : ce paper cite d'autres papers
            for ref_id in data["references"]:
                clean_ref = clean_arxiv_id(ref_id)
                if clean_ref in clean_ids_in_graph:
                    cites_batch.append({"from": clean_src, "to": clean_ref})

            # citations : d'autres papers citent ce paper
            for cit_id in data["citations"]:
                clean_cit = clean_arxiv_id(cit_id)
                if clean_cit in clean_ids_in_graph:
                    cites_batch.append({"from": clean_cit, "to": clean_src})

            total_refs  += len(data["references"])
            total_cites += len(data["citations"])

            if not data["citations"] and not data["references"]:
                not_found += 1

            if len(cites_batch) >= BATCH_SIZE:
                load_cites_relations(session, cites_batch)
                cites_batch = []

            time.sleep(DELAY)

        if cites_batch:
            load_cites_relations(session, cites_batch)

    driver.close()

    print(f"\n{'='*50}")
    print(f"  Termine !")
    print(f"  References trouvees   : {total_refs}")
    print(f"  Citations trouvees    : {total_cites}")
    print(f"  Papers non trouves S2 : {not_found} / {len(all_ids)}")

    driver2 = get_driver()
    with driver2.session() as session:
        result = session.run("MATCH ()-[r:CITES]->() RETURN count(r) AS n").single()
        print(f"  Relations CITES Neo4j : {result['n']}")
    driver2.close()

    logger.info(f"fetch_citations termine — {total_refs} refs, {total_cites} cites")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Limiter a N papers (test). Defaut : tous les papers."
    )
    args = parser.parse_args()

    print("Demarrage fetch citations depuis Semantic Scholar...")
    if args.limit:
        print(f"Mode test : {args.limit} papers seulement")

    run(limit=args.limit)