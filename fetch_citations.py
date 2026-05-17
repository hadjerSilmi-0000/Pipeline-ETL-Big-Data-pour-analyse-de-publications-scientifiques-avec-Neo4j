"""
fetch_citations.py — Script one-shot
Recupere les citations depuis Semantic Scholar (sans API key)
et charge les relations CITES dans Neo4j.

Usage :
    python fetch_citations.py
    python fetch_citations.py --limit 100   # tester sur 100 papers d'abord
"""

import os
import sys
import time
import argparse
import requests
from tqdm import tqdm

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from graph.schema import get_driver
from config.logging_config import setup_logger

logger = setup_logger("fetch_citations")

S2_BASE    = "https://api.semanticscholar.org/graph/v1/paper"
DELAY = 6.0
BATCH_SIZE = 50


# ─── Semantic Scholar ─────────────────────────────────────────────────────────

def get_s2_data(arxiv_id: str) -> dict:
    """
    Recupere citations + references depuis S2 via arxiv_id.
    Retourne {"citations": [...arxiv_ids], "references": [...arxiv_ids]}
    """
    url    = f"{S2_BASE}/arXiv:{arxiv_id}"
    params = {"fields": "citationCount,citations.externalIds,references.externalIds"}

    try:
        r = requests.get(url, params=params, timeout=15)

        if r.status_code == 404:
            return {"citations": [], "references": [], "citation_count": 0}

        if r.status_code == 429:
            logger.warning("Rate limit atteint — pause 60s")
            time.sleep(60)
            return get_s2_data(arxiv_id)   # retry

        if r.status_code != 200:
            logger.warning(f"S2 {r.status_code} pour {arxiv_id}")
            return {"citations": [], "references": [], "citation_count": 0}

        data = r.json()

        citations = [
            c["externalIds"]["ArXiv"]
            for c in data.get("citations", [])
            if c.get("externalIds", {}).get("ArXiv")
        ]

        references = [
            ref["externalIds"]["ArXiv"]
            for ref in data.get("references", [])
            if ref.get("externalIds", {}).get("ArXiv")
        ]

        return {
            "citations"     : citations,
            "references"    : references,
            "citation_count": data.get("citationCount", 0)
        }

    except requests.exceptions.Timeout:
        logger.warning(f"Timeout pour {arxiv_id}")
        return {"citations": [], "references": [], "citation_count": 0}
    except Exception as e:
        logger.error(f"Erreur S2 {arxiv_id} : {e}")
        return {"citations": [], "references": [], "citation_count": 0}


# ─── Neo4j ────────────────────────────────────────────────────────────────────

def get_all_arxiv_ids(driver) -> list[str]:
    """Recupere tous les arxiv_id du graphe"""
    query = "MATCH (p:Paper) RETURN p.arxiv_id AS arxiv_id ORDER BY p.arxiv_id"
    with driver.session() as session:
        result = session.run(query)
        return [r["arxiv_id"] for r in result]


def update_citation_count(session, arxiv_id: str, count: int):
    """Met a jour citation_count sur le Paper"""
    session.run(
        "MATCH (p:Paper {arxiv_id: $id}) SET p.citation_count = $count",
        id=arxiv_id, count=count
    )


def load_cites_relations(session, rows: list[dict]) -> int:
    """
    Cree les relations CITES entre papers.
    rows = [{"from": arxiv_id, "to": arxiv_id}, ...]
    Ignore silencieusement si le paper cible n'est pas dans le graphe.
    """
    query = """
    UNWIND $rows AS row
    MATCH (p1:Paper {arxiv_id: row.from})
    MATCH (p2:Paper {arxiv_id: row.to})
    MERGE (p1)-[:CITES]->(p2)
    """
    session.run(query, rows=rows)
    return len(rows)


# ─── Pipeline ────────────────────────────────────────────────────────────────

def run(limit: int = None):
    driver   = get_driver()
    all_ids  = get_all_arxiv_ids(driver)

    if limit:
        all_ids = all_ids[:limit]

    print(f"\n{len(all_ids)} papers a traiter")
    print(f"Delai entre requetes : {DELAY}s")
    print(f"Duree estimee : ~{len(all_ids) * DELAY / 60:.0f} minutes\n")

    total_cites      = 0
    total_refs       = 0
    cites_batch      = []
    not_found        = 0

    with driver.session() as session:
        for arxiv_id in tqdm(all_ids, desc="Fetch S2"):
            data = get_s2_data(arxiv_id)

            # mettre a jour citation_count
            if data["citation_count"]:
                update_citation_count(session, arxiv_id, data["citation_count"])

            # references : ce paper cite d'autres papers
            for ref_id in data["references"]:
                cites_batch.append({"from": arxiv_id, "to": ref_id})

            # citations inverses : d'autres papers citent ce paper
            # (on les stocke aussi si le paper citant est dans notre graphe)
            for cit_id in data["citations"]:
                cites_batch.append({"from": cit_id, "to": arxiv_id})

            total_refs  += len(data["references"])
            total_cites += len(data["citations"])

            if not data["citations"] and not data["references"]:
                not_found += 1

            # flush par batch
            if len(cites_batch) >= BATCH_SIZE:
                load_cites_relations(session, cites_batch)
                cites_batch = []

            time.sleep(DELAY)

        # flush restant
        if cites_batch:
            load_cites_relations(session, cites_batch)

    driver.close()

    # stats finales
    print(f"\n{'='*50}")
    print(f"  Termine !")
    print(f"  References trouvees   : {total_refs}")
    print(f"  Citations trouvees    : {total_cites}")
    print(f"  Papers non trouves    : {not_found} / {len(all_ids)}")

    # compter les CITES dans Neo4j
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