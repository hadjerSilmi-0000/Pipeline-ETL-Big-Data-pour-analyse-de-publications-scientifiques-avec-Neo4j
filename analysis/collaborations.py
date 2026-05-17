"""
analysis/collaborations.py
Analyse approfondie du reseau de collaborations entre chercheurs.
"""

import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import networkx as nx
from collections import defaultdict
from graph.schema import get_driver
from config.logging_config import setup_logger

logger = setup_logger("analysis.collaborations")


# ─── Chargement ──────────────────────────────────────────────────────────────

def load_collaboration_graph() -> nx.Graph:
    """Charge le reseau de collaborations Neo4j → NetworkX"""
    query = """
    MATCH (a1:Author)-[r:COLLABORATED_WITH]-(a2:Author)
    WHERE id(a1) < id(a2)
    RETURN a1.name AS author1, a2.name AS author2, r.count AS weight
    """
    driver = get_driver()
    G = nx.Graph()
    with driver.session() as session:
        for row in session.run(query):
            G.add_edge(row["author1"], row["author2"], weight=int(row["weight"] or 1))
    driver.close()
    return G


# ─── Metriques globales ───────────────────────────────────────────────────────

def get_network_stats() -> dict:
    """Statistiques globales du reseau de collaboration"""
    G = load_collaboration_graph()

    connected   = nx.is_connected(G)
    components  = list(nx.connected_components(G))
    giant       = max(components, key=len) if components else set()

    stats = {
        "nodes"              : G.number_of_nodes(),
        "edges"              : G.number_of_edges(),
        "density"            : round(nx.density(G), 6),
        "connected"          : connected,
        "n_components"       : len(components),
        "giant_component_size": len(giant),
        "avg_degree"         : round(sum(d for _, d in G.degree()) / G.number_of_nodes(), 2)
                               if G.number_of_nodes() else 0,
        "avg_clustering"     : round(nx.average_clustering(G), 4),
    }

    # diametre sur la composante geante seulement (evite erreur si non connexe)
    if len(giant) > 1:
        G_giant = G.subgraph(giant)
        stats["diameter"] = nx.diameter(G_giant)
    else:
        stats["diameter"] = None

    logger.info(f"Network stats : {stats}")
    return stats


# ─── Centralite ──────────────────────────────────────────────────────────────

def get_degree_centrality(limit: int = 10) -> list[dict]:
    """Auteurs les plus connectes (degree centrality)"""
    G      = load_collaboration_graph()
    scores = nx.degree_centrality(G)
    return [
        {"author": node, "degree_centrality": round(score, 4), "degree": G.degree(node)}
        for node, score in sorted(scores.items(), key=lambda x: x[1], reverse=True)[:limit]
    ]


def get_betweenness_centrality(limit: int = 10) -> list[dict]:
    """Auteurs les plus importants comme intermediaires (betweenness)"""
    G      = load_collaboration_graph()
    scores = nx.betweenness_centrality(G, weight="weight", normalized=True)
    return [
        {"author": node, "betweenness": round(score, 6)}
        for node, score in sorted(scores.items(), key=lambda x: x[1], reverse=True)[:limit]
    ]


def get_clustering_coefficients(limit: int = 10) -> list[dict]:
    """Auteurs avec le plus fort coefficient de clustering local"""
    G      = load_collaboration_graph()
    scores = nx.clustering(G)
    return [
        {"author": node, "clustering": round(score, 4)}
        for node, score in sorted(scores.items(), key=lambda x: x[1], reverse=True)[:limit]
        if G.degree(node) > 1   # exclure les auteurs isoles
    ]


# ─── Requetes Neo4j directes ─────────────────────────────────────────────────

def get_most_collaborative_authors(limit: int = 10) -> list[dict]:
    """Auteurs avec le plus de co-auteurs distincts"""
    query = """
    MATCH (a:Author)-[:COLLABORATED_WITH]-(b:Author)
    RETURN a.name AS author, count(DISTINCT b) AS collaborators
    ORDER BY collaborators DESC
    LIMIT $limit
    """
    driver = get_driver()
    with driver.session() as session:
        result = [dict(r) for r in session.run(query, limit=limit)]
    driver.close()
    return result


def get_strongest_pairs(limit: int = 10) -> list[dict]:
    """Paires d'auteurs ayant collabore le plus souvent"""
    query = """
    MATCH (a1:Author)-[r:COLLABORATED_WITH]-(a2:Author)
    WHERE id(a1) < id(a2)
    RETURN a1.name AS author1, a2.name AS author2, r.count AS shared_papers
    ORDER BY shared_papers DESC
    LIMIT $limit
    """
    driver = get_driver()
    with driver.session() as session:
        result = [dict(r) for r in session.run(query, limit=limit)]
    driver.close()
    return result


def get_isolated_authors() -> list[dict]:
    """Auteurs sans aucune collaboration (paper solo)"""
    query = """
    MATCH (a:Author)
    WHERE NOT (a)-[:COLLABORATED_WITH]-()
    RETURN a.name AS author
    ORDER BY author
    """
    driver = get_driver()
    with driver.session() as session:
        result = [dict(r) for r in session.run(query)]
    driver.close()
    return result


def get_collaboration_by_year(limit: int = 10) -> list[dict]:
    """Evolution du nombre de collaborations par annee"""
    query = """
    MATCH (a1:Author)-[:WROTE]->(p:Paper)<-[:WROTE]-(a2:Author)
    WHERE id(a1) < id(a2) AND p.year IS NOT NULL
    RETURN p.year AS year, count(DISTINCT [a1.name, a2.name]) AS collaborations
    ORDER BY year DESC
    LIMIT $limit
    """
    driver = get_driver()
    with driver.session() as session:
        result = [dict(r) for r in session.run(query, limit=limit)]
    driver.close()
    return result


def get_author_ego_network(author_name: str) -> dict:
    """
    Retourne le reseau ego d'un auteur :
    ses collaborateurs directs + leurs connexions entre eux.
    """
    query = """
    MATCH (a:Author)-[r:COLLABORATED_WITH]-(b:Author)
    WHERE toLower(a.name) CONTAINS toLower($name)
    WITH a, collect({name: b.name, count: r.count}) AS neighbors
    RETURN a.name AS center, neighbors
    LIMIT 1
    """
    driver = get_driver()
    with driver.session() as session:
        row = session.run(query, name=author_name).single()
    driver.close()

    if not row:
        return {}

    return {
        "center"    : row["center"],
        "neighbors" : row["neighbors"],
        "degree"    : len(row["neighbors"])
    }


# ─── Rapport ─────────────────────────────────────────────────────────────────

def print_report():
    print("\n" + "="*60)
    print("  ANALYSE — RESEAU DE COLLABORATIONS")
    print("="*60)

    print("\n[1] Statistiques globales")
    stats = get_network_stats()
    for k, v in stats.items():
        print(f"  {k:<25} : {v}")

    print("\n[2] Top 10 auteurs les plus connectes (degree)")
    for r in get_degree_centrality(10):
        print(f"  {r['author']:<35} degree={r['degree']}  centrality={r['degree_centrality']}")

    print("\n[3] Top 10 intermediaires (betweenness)")
    for r in get_betweenness_centrality(10):
        print(f"  {r['author']:<35} betweenness={r['betweenness']}")

    print("\n[4] Paires les plus collaboratives")
    for r in get_strongest_pairs(10):
        print(f"  {r['author1']} <-> {r['author2']} ({r['shared_papers']} papers)")

    print("\n[5] Evolution des collaborations par annee")
    for r in get_collaboration_by_year(8):
        print(f"  {r['year']} : {r['collaborations']} paires")

    isolated = get_isolated_authors()
    print(f"\n[6] Auteurs isoles (aucune collaboration) : {len(isolated)}")


if __name__ == "__main__":
    print_report()