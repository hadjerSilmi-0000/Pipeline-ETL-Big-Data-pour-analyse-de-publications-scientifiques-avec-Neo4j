import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from neo4j import GraphDatabase
from config.settings import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD
from config.logging_config import setup_logger

logger = setup_logger("graph_schema")


def get_driver():
    return GraphDatabase.driver(
        NEO4J_URI,
        auth=(NEO4J_USER, NEO4J_PASSWORD)
    )


def create_constraints(session):
    """Cree les contraintes d'unicite sur les noeuds"""
    constraints = [
        # unicite
        "CREATE CONSTRAINT paper_arxiv_id IF NOT EXISTS FOR (p:Paper) REQUIRE p.arxiv_id IS UNIQUE",
        "CREATE CONSTRAINT author_name IF NOT EXISTS FOR (a:Author) REQUIRE a.name IS UNIQUE",
        "CREATE CONSTRAINT topic_name IF NOT EXISTS FOR (t:Topic) REQUIRE t.name IS UNIQUE",
        "CREATE CONSTRAINT venue_name IF NOT EXISTS FOR (v:Venue) REQUIRE v.name IS UNIQUE",
        "CREATE CONSTRAINT category_name IF NOT EXISTS FOR (c:Category) REQUIRE c.name IS UNIQUE",
    ]

    for constraint in constraints:
        try:
            session.run(constraint)
            logger.info(f"Contrainte creee : {constraint[:60]}...")
        except Exception as e:
            logger.warning(f"Contrainte existante ou erreur : {e}")


def create_indexes(session):
    """Cree les index pour accelerer les requetes"""
    indexes = [
        "CREATE INDEX paper_year IF NOT EXISTS FOR (p:Paper) ON (p.year)",
        "CREATE INDEX paper_title IF NOT EXISTS FOR (p:Paper) ON (p.title)",
        "CREATE INDEX paper_citation_count IF NOT EXISTS FOR (p:Paper) ON (p.citation_count)",
        "CREATE INDEX author_name_idx IF NOT EXISTS FOR (a:Author) ON (a.name)",
        "CREATE INDEX topic_name_idx IF NOT EXISTS FOR (t:Topic) ON (t.name)",
    ]

    for index in indexes:
        try:
            session.run(index)
            logger.info(f"Index cree : {index[:60]}...")
        except Exception as e:
            logger.warning(f"Index existant ou erreur : {e}")


def drop_all(session):
    """Supprime toutes les donnees du graphe — utile pour reset"""
    session.run("MATCH (n) DETACH DELETE n")
    logger.warning("Toutes les donnees ont ete supprimees")


def get_graph_stats(session) -> dict:
    """Retourne les statistiques du graphe"""
    stats = {}

    counts = [
        ("papers",       "MATCH (p:Paper) RETURN count(p) AS n"),
        ("authors",      "MATCH (a:Author) RETURN count(a) AS n"),
        ("topics",       "MATCH (t:Topic) RETURN count(t) AS n"),
        ("venues",       "MATCH (v:Venue) RETURN count(v) AS n"),
        ("categories",   "MATCH (c:Category) RETURN count(c) AS n"),
        ("wrote",        "MATCH ()-[r:WROTE]->() RETURN count(r) AS n"),
        ("cites",        "MATCH ()-[r:CITES]->() RETURN count(r) AS n"),
        ("has_topic",    "MATCH ()-[r:HAS_TOPIC]->() RETURN count(r) AS n"),
        ("collaborated", "MATCH ()-[r:COLLABORATED_WITH]->() RETURN count(r) AS n"),
    ]

    for name, query in counts:
        result = session.run(query).single()
        stats[name] = result["n"] if result else 0

    return stats


def init_schema():
    """Initialise le schema complet du graphe"""
    print("Initialisation du schema Neo4j...")
    driver = get_driver()

    with driver.session() as session:
        print("Creation des contraintes...")
        create_constraints(session)

        print("Creation des index...")
        create_indexes(session)

        stats = get_graph_stats(session)
        print(f"\nEtat du graphe apres init :")
        for key, val in stats.items():
            print(f"  {key:<20} : {val}")

    driver.close()
    print("\nSchema initialise avec succes !")
    logger.info("Schema Neo4j initialise")


if __name__ == "__main__":
    init_schema()