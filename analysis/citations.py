"""
analysis/citations.py
Analyse du reseau de citations entre papers.
Necessite que fetch_citations.py ait ete execute au prealable.
"""

import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import networkx as nx
from graph.schema import get_driver
from config.logging_config import setup_logger

logger = setup_logger("analysis.citations")


# ─── Chargement ──────────────────────────────────────────────────────────────

def load_citation_graph() -> nx.DiGraph:
    """Charge le reseau de citations Neo4j → NetworkX DiGraph"""
    query = """
    MATCH (p1:Paper)-[:CITES]->(p2:Paper)
    RETURN p1.arxiv_id AS src, p2.arxiv_id AS dst
    """
    driver = get_driver()
    G = nx.DiGraph()
    with driver.session() as session:
        for row in session.run(query):
            G.add_edge(row["src"], row["dst"])
    driver.close()
    return G


def _check_citations_exist(driver) -> bool:
    with driver.session() as session:
        result = session.run("MATCH ()-[r:CITES]->() RETURN count(r) AS n").single()
        return result["n"] > 0


# ─── Metriques globales ───────────────────────────────────────────────────────

def get_citation_network_stats() -> dict:
    """Statistiques globales du reseau de citations"""
    driver = get_driver()
    if not _check_citations_exist(driver):
        driver.close()
        return {"error": "Aucune relation CITES — lancer fetch_citations.py d'abord"}
    driver.close()

    G = load_citation_graph()

    stats = {
        "papers_with_citations" : G.number_of_nodes(),
        "total_cites_edges"     : G.number_of_edges(),
        "avg_out_degree"        : round(sum(d for _, d in G.out_degree()) / G.number_of_nodes(), 2)
                                  if G.number_of_nodes() else 0,
        "avg_in_degree"         : round(sum(d for _, d in G.in_degree()) / G.number_of_nodes(), 2)
                                  if G.number_of_nodes() else 0,
        "is_dag"                : nx.is_directed_acyclic_graph(G),
        "n_weakly_connected"    : nx.number_weakly_connected_components(G),
    }

    logger.info(f"Citation network stats : {stats}")
    return stats


# ─── Papers les plus cites ───────────────────────────────────────────────────

def get_most_cited_papers(limit: int = 10) -> list[dict]:
    """Papers avec le plus de citations (in-degree dans le graphe)"""
    query = """
    MATCH (p:Paper)
    WHERE p.citation_count > 0
    RETURN p.arxiv_id AS arxiv_id, p.title AS title,
           p.year AS year, p.citation_count AS citations
    ORDER BY citations DESC
    LIMIT $limit
    """
    driver = get_driver()
    with driver.session() as session:
        result = [dict(r) for r in session.run(query, limit=limit)]
    driver.close()
    return result


def get_most_cited_in_graph(limit: int = 10) -> list[dict]:
    """
    Papers les plus cites au sein du graphe (relations CITES internes).
    Different de citation_count qui compte toutes les citations S2.
    """
    query = """
    MATCH (p1:Paper)-[:CITES]->(p2:Paper)
    RETURN p2.arxiv_id AS arxiv_id, p2.title AS title,
           p2.year AS year, count(p1) AS cited_by
    ORDER BY cited_by DESC
    LIMIT $limit
    """
    driver = get_driver()
    with driver.session() as session:
        result = [dict(r) for r in session.run(query, limit=limit)]
    driver.close()
    return result


def get_most_citing_papers(limit: int = 10) -> list[dict]:
    """Papers qui referent le plus d'autres papers (out-degree)"""
    query = """
    MATCH (p:Paper)-[:CITES]->(cited:Paper)
    RETURN p.arxiv_id AS arxiv_id, p.title AS title,
           p.year AS year, count(cited) AS references_count
    ORDER BY references_count DESC
    LIMIT $limit
    """
    driver = get_driver()
    with driver.session() as session:
        result = [dict(r) for r in session.run(query, limit=limit)]
    driver.close()
    return result


# ─── Analyse temporelle ───────────────────────────────────────────────────────

def get_citations_by_year() -> list[dict]:
    """Distribution des citations par annee du paper cite"""
    query = """
    MATCH (p1:Paper)-[:CITES]->(p2:Paper)
    WHERE p2.year IS NOT NULL
    RETURN p2.year AS year, count(*) AS citations
    ORDER BY year DESC
    """
    driver = get_driver()
    with driver.session() as session:
        result = [dict(r) for r in session.run(query)]
    driver.close()
    return result


def get_citation_age_distribution() -> list[dict]:
    """Distribution de l'age des citations (annee citant - annee cite)"""
    query = """
    MATCH (p1:Paper)-[:CITES]->(p2:Paper)
    WHERE p1.year IS NOT NULL AND p2.year IS NOT NULL
    WITH p1.year - p2.year AS age
    WHERE age >= 0
    RETURN age, count(*) AS count
    ORDER BY age
    """
    driver = get_driver()
    with driver.session() as session:
        result = [dict(r) for r in session.run(query)]
    driver.close()
    return result


# ─── Analyse par topic ────────────────────────────────────────────────────────

def get_most_cited_by_topic(limit: int = 10) -> list[dict]:
    """Topics dont les papers sont les plus cites en moyenne"""
    query = """
    MATCH (p:Paper)-[:HAS_TOPIC]->(t:Topic)
    WHERE p.citation_count > 0
    RETURN t.name AS topic,
           count(p) AS papers,
           avg(p.citation_count) AS avg_citations,
           max(p.citation_count) AS max_citations
    ORDER BY avg_citations DESC
    LIMIT $limit
    """
    driver = get_driver()
    with driver.session() as session:
        result = [dict(r) for r in session.run(query, limit=limit)]
    driver.close()
    return [
        {**r, "avg_citations": round(r["avg_citations"], 1)}
        for r in result
    ]


def get_citation_chains(depth: int = 3, limit: int = 5) -> list[dict]:
    """
    Trouve des chaines de citations (A cite B cite C...).
    depth : longueur max de la chaine
    """
    query = f"""
    MATCH path = (p1:Paper)-[:CITES*2..{depth}]->(p2:Paper)
    WHERE p1 <> p2
    RETURN [n IN nodes(path) | n.title] AS chain,
           length(path) AS depth
    ORDER BY depth DESC
    LIMIT $limit
    """
    driver = get_driver()
    with driver.session() as session:
        result = [dict(r) for r in session.run(query, limit=limit)]
    driver.close()
    return result


# ─── PageRank ────────────────────────────────────────────────────────────────

def get_pagerank(limit: int = 10) -> list[dict]:
    """
    Calcule le PageRank sur le graphe de citations.
    Les papers avec un PageRank eleve sont cites par des papers eux-memes importants.
    """
    driver = get_driver()
    if not _check_citations_exist(driver):
        driver.close()
        return []
    driver.close()

    G      = load_citation_graph()
    scores = nx.pagerank(G, alpha=0.85, max_iter=100)

    # recuperer les titres
    driver2 = get_driver()
    with driver2.session() as session:
        rows = session.run("MATCH (p:Paper) RETURN p.arxiv_id AS id, p.title AS title, p.year AS year")
        id_to_meta = {r["id"]: {"title": r["title"], "year": r["year"]} for r in rows}
    driver2.close()

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:limit]
    return [
        {
            "arxiv_id" : arxiv_id,
            "title"    : id_to_meta.get(arxiv_id, {}).get("title", arxiv_id)[:70],
            "year"     : id_to_meta.get(arxiv_id, {}).get("year"),
            "pagerank" : round(score, 6)
        }
        for arxiv_id, score in ranked
    ]


# ─── Rapport ─────────────────────────────────────────────────────────────────

def print_report():
    print("\n" + "="*60)
    print("  ANALYSE — RESEAU DE CITATIONS")
    print("="*60)

    print("\n[1] Statistiques globales")
    stats = get_citation_network_stats()
    if "error" in stats:
        print(f"  {stats['error']}")
        return
    for k, v in stats.items():
        print(f"  {k:<30} : {v}")

    print("\n[2] Top 10 papers les plus cites (citation_count S2)")
    for r in get_most_cited_papers(10):
        print(f"  [{r['citations']:>5}] {r['title'][:55]} ({r['year']})")

    print("\n[3] Top 10 papers les plus cites dans le graphe interne")
    for r in get_most_cited_in_graph(10):
        print(f"  [{r['cited_by']:>3}] {r['title'][:55]} ({r['year']})")

    print("\n[4] Top 10 papers avec le plus de references")
    for r in get_most_citing_papers(10):
        print(f"  [{r['references_count']:>3} refs] {r['title'][:55]}")

    print("\n[5] Citations par annee")
    for r in get_citations_by_year()[:8]:
        print(f"  {r['year']} : {r['citations']} citations")

    print("\n[6] Topics les plus cites (avg)")
    for r in get_most_cited_by_topic(10):
        print(f"  {r['topic']:<25} avg={r['avg_citations']:>8.1f}  max={r['max_citations']}")

    print("\n[7] PageRank des papers")
    for r in get_pagerank(10):
        print(f"  [{r['pagerank']:.6f}] {r['title'][:55]}")


if __name__ == "__main__":
    print_report()