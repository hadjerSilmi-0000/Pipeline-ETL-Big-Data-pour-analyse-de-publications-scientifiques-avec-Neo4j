import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import networkx as nx
from collections import defaultdict

from graph.schema import get_driver
from config.logging_config import setup_logger

logger = setup_logger("community")

try:
    import community as community_louvain
    LOUVAIN_AVAILABLE = True
except ImportError:
    LOUVAIN_AVAILABLE = False
    logger.warning("python-louvain non installe — fallback sur Girvan-Newman (NetworkX)")


# ─── Chargement du graphe de collaboration ────────────────────────────────────

def load_collaboration_graph() -> nx.Graph:
    """Charge le reseau de collaborations depuis Neo4j vers NetworkX"""
    query = """
    MATCH (a1:Author)-[r:COLLABORATED_WITH]-(a2:Author)
    WHERE id(a1) < id(a2)
    RETURN a1.name AS author1, a2.name AS author2, r.count AS weight
    """
    driver = get_driver()
    G = nx.Graph()

    with driver.session() as session:
        result = session.run(query)
        for row in result:
            G.add_edge(
                row["author1"],
                row["author2"],
                weight=int(row["weight"] or 1)
            )

    driver.close()
    logger.info(f"Graphe charge : {G.number_of_nodes()} auteurs, {G.number_of_edges()} collaborations")
    print(f"Graphe de collaboration : {G.number_of_nodes()} auteurs, {G.number_of_edges()} aretes")
    return G


# ─── Detection de communautes ─────────────────────────────────────────────────

def detect_communities_louvain(G: nx.Graph) -> dict:
    """
    Detection de communautes avec l'algorithme de Louvain.
    Necessite : pip install python-louvain
    Retourne : {author_name: community_id}
    """
    if not LOUVAIN_AVAILABLE:
        raise RuntimeError("python-louvain non disponible. Installer avec : pip install python-louvain")

    print("Detection de communautes avec Louvain...")
    partition = community_louvain.best_partition(G, weight="weight", random_state=42)
    n_communities = len(set(partition.values()))
    modularity    = community_louvain.modularity(partition, G, weight="weight")

    print(f"Louvain termine : {n_communities} communautes detectees (modularity={modularity:.4f})")
    logger.info(f"Louvain : {n_communities} communautes, modularity={modularity:.4f}")
    return partition


def detect_communities_girvan_newman(G: nx.Graph, k: int = 10) -> dict:
    """
    Fallback : Girvan-Newman via NetworkX.
    Plus lent, utilise uniquement si python-louvain est absent.
    Retourne : {author_name: community_id}
    """
    from networkx.algorithms.community import girvan_newman
    print(f"Fallback Girvan-Newman — extraction de {k} communautes...")

    comp = girvan_newman(G)
    for _ in range(k - 1):
        communities = next(comp)

    partition = {}
    for comm_id, community in enumerate(communities):
        for node in community:
            partition[node] = comm_id

    print(f"Girvan-Newman : {k} communautes extraites")
    logger.info(f"Girvan-Newman : {k} communautes")
    return partition


def detect_communities(G: nx.Graph) -> dict:
    """Auto-selectionne Louvain ou Girvan-Newman selon disponibilite"""
    if LOUVAIN_AVAILABLE:
        return detect_communities_louvain(G)
    else:
        print("ATTENTION : python-louvain absent. Utilisation du fallback Girvan-Newman.")
        print("Installer avec : pip install python-louvain")
        return detect_communities_girvan_newman(G, k=10)


# ─── Statistiques des communautes ────────────────────────────────────────────

def compute_community_stats(G: nx.Graph, partition: dict) -> list[dict]:
    """Calcule des stats par communaute : taille, densite, auteur central"""
    communities = defaultdict(list)
    for node, comm_id in partition.items():
        communities[comm_id].append(node)

    stats = []
    for comm_id, members in communities.items():
        subgraph   = G.subgraph(members)
        n          = len(members)
        edges      = subgraph.number_of_edges()
        density    = nx.density(subgraph) if n > 1 else 0.0
        degrees    = dict(subgraph.degree())
        top_author = max(degrees, key=degrees.get) if degrees else ""

        stats.append({
            "community_id" : comm_id,
            "size"         : n,
            "edges"        : edges,
            "density"      : round(density, 4),
            "top_author"   : top_author,
            "members"      : members[:10]   # preview des 10 premiers
        })

    stats.sort(key=lambda x: x["size"], reverse=True)
    return stats


# ─── Stockage dans Neo4j ──────────────────────────────────────────────────────

def store_communities_in_neo4j(partition: dict) -> int:
    """
    Stocke la propriete community_id sur chaque noeud Author dans Neo4j.
    Cree aussi des noeuds :Community pour faciliter les requetes.
    """
    # 1. Ajouter community_id sur les auteurs
    query_author = """
    UNWIND $rows AS row
    MATCH (a:Author {name: row.name})
    SET a.community_id = row.community_id
    """

    # 2. Creer les noeuds Community
    query_community = """
    MERGE (c:Community {community_id: $community_id})
    SET c.size = $size
    """

    # 3. Relier auteurs a leur communaute
    query_member = """
    UNWIND $rows AS row
    MATCH (a:Author {name: row.name})
    MATCH (c:Community {community_id: row.community_id})
    MERGE (a)-[:BELONGS_TO_COMMUNITY]->(c)
    """

    driver  = get_driver()
    rows    = [{"name": name, "community_id": comm_id}
               for name, comm_id in partition.items()]

    communities = defaultdict(list)
    for name, comm_id in partition.items():
        communities[comm_id].append(name)

    BATCH = 200
    stored = 0

    with driver.session() as session:
        # contrainte sur Community si elle n'existe pas
        try:
            session.run("CREATE CONSTRAINT community_id IF NOT EXISTS FOR (c:Community) REQUIRE c.community_id IS UNIQUE")
        except Exception:
            pass

        # stocker community_id sur auteurs
        for i in range(0, len(rows), BATCH):
            session.run(query_author, rows=rows[i:i + BATCH])
            stored += len(rows[i:i + BATCH])

        # creer noeuds Community
        for comm_id, members in communities.items():
            session.run(query_community, community_id=comm_id, size=len(members))

        # relier auteurs a leur communaute
        for i in range(0, len(rows), BATCH):
            session.run(query_member, rows=rows[i:i + BATCH])

    driver.close()
    logger.info(f"{stored} auteurs mis a jour avec community_id")
    print(f"{stored} auteurs mis a jour dans Neo4j | {len(communities)} noeuds Community crees")
    return stored


# ─── Requetes supplementaires Neo4j ──────────────────────────────────────────

def get_communities_from_neo4j(limit: int = 20) -> list[dict]:
    """Recupere les communautes depuis Neo4j avec stats"""
    query = """
    MATCH (a:Author)
    WHERE a.community_id IS NOT NULL
    WITH a.community_id AS community_id, collect(a.name) AS members, count(a) AS size
    ORDER BY size DESC
    LIMIT $limit
    RETURN community_id, size, members[..5] AS top_members
    """
    driver = get_driver()
    with driver.session() as session:
        result = session.run(query, limit=limit)
        data   = [dict(r) for r in result]
    driver.close()
    return data


def get_author_community(author_name: str) -> dict | None:
    """Retourne la communaute d'un auteur specifique"""
    query = """
    MATCH (a:Author)
    WHERE toLower(a.name) CONTAINS toLower($name) AND a.community_id IS NOT NULL
    WITH a.community_id AS community_id LIMIT 1
    MATCH (member:Author {community_id: community_id})
    RETURN community_id,
           count(member) AS community_size,
           collect(member.name)[..10] AS members
    """
    driver = get_driver()
    with driver.session() as session:
        result = session.run(query, name=author_name).single()
        data   = dict(result) if result else None
    driver.close()
    return data


# ─── Pipeline complet ─────────────────────────────────────────────────────────

def run_community_detection() -> dict:
    """Pipeline complet de detection de communautes"""
    print("\n" + "="*60)
    print("  DETECTION DE COMMUNAUTES — Algorithme de Louvain")
    print("="*60)

    # 1. Charger le graphe
    print("\n[1/4] Chargement du graphe de collaboration...")
    G = load_collaboration_graph()

    if G.number_of_nodes() == 0:
        print("ERREUR : Graphe vide — verifier que Neo4j contient des collaborations.")
        return {}

    # 2. Detecter les communautes
    print("\n[2/4] Detection des communautes...")
    partition = detect_communities(G)

    # 3. Stats
    print("\n[3/4] Calcul des statistiques...")
    stats = compute_community_stats(G, partition)

    print(f"\nTop 10 communautes detectees :")
    for s in stats[:10]:
        print(f"  Comm #{s['community_id']:>3} | {s['size']:>4} membres | "
              f"densite={s['density']:.3f} | top: {s['top_author']}")

    # 4. Stocker dans Neo4j
    print("\n[4/4] Stockage dans Neo4j...")
    store_communities_in_neo4j(partition)

    result = {
        "partition" : partition,
        "stats"     : stats,
        "graph"     : G,
        "n_communities": len(set(partition.values()))
    }

    print(f"\nDetection terminee — {result['n_communities']} communautes | "
          f"{len(partition)} auteurs assignes")
    logger.info(f"Community detection terminee : {result['n_communities']} communautes")
    return result


if __name__ == "__main__":
    # verifier la disponibilite de python-louvain
    if not LOUVAIN_AVAILABLE:
        print("ATTENTION : python-louvain n'est pas installe.")
        print("Installer avec : pip install python-louvain")
        print("Le fallback Girvan-Newman sera utilise (plus lent).\n")

    result = run_community_detection()

    if result:
        print("\nVerification depuis Neo4j :")
        communities = get_communities_from_neo4j(limit=5)
        for c in communities:
            print(f"  Comm #{c['community_id']} : {c['size']} membres — "
                  f"ex: {', '.join(c['top_members'][:3])}")