import json
import os
import sys
from tqdm import tqdm

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from graph.schema import get_driver, get_graph_stats
from config.settings import DATA_PROCESSED_PATH
from config.logging_config import setup_logger

logger = setup_logger("graph_loader")

BATCH_SIZE = 50


def load_papers(session, papers: list[dict]):
    """Charge les noeuds Paper"""
    query = """
    UNWIND $papers AS p
    MERGE (paper:Paper {arxiv_id: p.arxiv_id})
    SET paper.title          = p.title,
        paper.abstract       = p.abstract,
        paper.year           = p.year,
        paper.published      = p.published,
        paper.doi            = p.doi,
        paper.pdf_url        = p.pdf_url,
        paper.citation_count = p.citation_count,
        paper.reference_count= p.reference_count,
        paper.query          = p.query,
        paper.s2_id          = p.s2_id
    """
    for i in range(0, len(papers), BATCH_SIZE):
        batch = papers[i:i + BATCH_SIZE]
        session.run(query, papers=batch)
    logger.info(f"{len(papers)} noeuds Paper charges")


def load_authors(session, papers: list[dict]):
    """Charge les noeuds Author et relations WROTE"""
    query = """
    UNWIND $rows AS row
    MERGE (p:Paper {arxiv_id: row.arxiv_id})
    MERGE (a:Author {name: row.author})
    MERGE (a)-[:WROTE]->(p)
    """
    rows = []
    for paper in papers:
        for author in paper.get("authors", []):
            if author and len(author.strip()) > 1:
                rows.append({
                    "arxiv_id": paper["arxiv_id"],
                    "author"  : author.strip()
                })

    for i in range(0, len(rows), BATCH_SIZE):
        batch = rows[i:i + BATCH_SIZE]
        session.run(query, rows=batch)
    logger.info(f"{len(rows)} relations WROTE chargees")


def load_collaborations(session, papers: list[dict]):
    """Cree les relations COLLABORATED_WITH entre auteurs d'un meme paper"""
    query = """
    UNWIND $rows AS row
    MATCH (a1:Author {name: row.author1})
    MATCH (a2:Author {name: row.author2})
    MERGE (a1)-[r:COLLABORATED_WITH]-(a2)
    ON CREATE SET r.count = 1
    ON MATCH  SET r.count = r.count + 1
    """
    rows = []
    for paper in papers:
        authors = [a.strip() for a in paper.get("authors", []) if a and len(a.strip()) > 1]
        for i in range(len(authors)):
            for j in range(i + 1, len(authors)):
                rows.append({
                    "author1": authors[i],
                    "author2": authors[j]
                })

    for i in range(0, len(rows), BATCH_SIZE):
        batch = rows[i:i + BATCH_SIZE]
        session.run(query, rows=batch)
    logger.info(f"{len(rows)} relations COLLABORATED_WITH chargees")


def load_topics(session, papers: list[dict]):
    """Charge les noeuds Topic et relations HAS_TOPIC"""
    query = """
    UNWIND $rows AS row
    MERGE (p:Paper {arxiv_id: row.arxiv_id})
    MERGE (t:Topic {name: row.topic})
    MERGE (p)-[:HAS_TOPIC]->(t)
    """
    rows = []
    for paper in papers:
        for keyword in paper.get("keywords", []):
            if keyword and len(keyword.strip()) > 2:
                rows.append({
                    "arxiv_id": paper["arxiv_id"],
                    "topic"   : keyword.strip().lower()
                })

    for i in range(0, len(rows), BATCH_SIZE):
        batch = rows[i:i + BATCH_SIZE]
        session.run(query, rows=batch)
    logger.info(f"{len(rows)} relations HAS_TOPIC chargees")


def load_venues(session, papers: list[dict]):
    """Charge les noeuds Venue et relations PUBLISHED_IN"""
    query = """
    UNWIND $rows AS row
    MERGE (p:Paper {arxiv_id: row.arxiv_id})
    MERGE (v:Venue {name: row.venue})
    MERGE (p)-[:PUBLISHED_IN]->(v)
    """
    rows = [
        {"arxiv_id": p["arxiv_id"], "venue": p["venue"].strip()}
        for p in papers
        if p.get("venue") and len(p["venue"].strip()) > 2
    ]

    for i in range(0, len(rows), BATCH_SIZE):
        batch = rows[i:i + BATCH_SIZE]
        session.run(query, rows=batch)
    logger.info(f"{len(rows)} relations PUBLISHED_IN chargees")


def load_categories(session, papers: list[dict]):
    """Charge les noeuds Category et relations BELONGS_TO"""
    query = """
    UNWIND $rows AS row
    MERGE (p:Paper {arxiv_id: row.arxiv_id})
    MERGE (c:Category {name: row.category})
    MERGE (p)-[:BELONGS_TO]->(c)
    """
    rows = []
    for paper in papers:
        for cat in paper.get("categories", []):
            if cat and len(cat.strip()) > 1:
                rows.append({
                    "arxiv_id": paper["arxiv_id"],
                    "category": cat.strip()
                })

    for i in range(0, len(rows), BATCH_SIZE):
        batch = rows[i:i + BATCH_SIZE]
        session.run(query, rows=batch)
    logger.info(f"{len(rows)} relations BELONGS_TO chargees")


def run_loading(input_file: str = None) -> dict:
    """Pipeline complet de chargement dans Neo4j"""
    if input_file is None:
        spark_path   = os.path.join(DATA_PROCESSED_PATH, "spark_processed.json")
        cleaned_path = os.path.join(DATA_PROCESSED_PATH, "cleaned_papers.json")
        input_file   = spark_path if os.path.exists(spark_path) else cleaned_path

    print(f"Chargement : {input_file}")
    with open(input_file, "r", encoding="utf-8") as f:
        papers = json.load(f)

    print(f"{len(papers)} papers a charger dans Neo4j...")
    driver = get_driver()

    with driver.session() as session:
        print("1. Chargement des Papers...")
        load_papers(session, papers)

        print("2. Chargement des Authors + WROTE...")
        load_authors(session, papers)

        print("3. Chargement des collaborations...")
        load_collaborations(session, papers)

        print("4. Chargement des Topics...")
        load_topics(session, papers)

        print("5. Chargement des Venues...")
        load_venues(session, papers)

        print("6. Chargement des Categories...")
        load_categories(session, papers)

        print("\nStats finales du graphe :")
        stats = get_graph_stats(session)
        for key, val in stats.items():
            print(f"  {key:<20} : {val}")

    driver.close()
    logger.info("Chargement Neo4j termine")
    return stats


if __name__ == "__main__":
    print("Demarrage chargement Neo4j...")
    stats = run_loading()
    print("\nChargement termine !")