import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from graph.schema import get_driver
from config.logging_config import setup_logger

logger = setup_logger("graph_queries")


def get_most_prolific_authors(limit: int = 10) -> list[dict]:
    """Auteurs ayant publie le plus de papers"""
    query = """
    MATCH (a:Author)-[:WROTE]->(p:Paper)
    RETURN a.name AS author, count(p) AS papers
    ORDER BY papers DESC
    LIMIT $limit
    """
    driver = get_driver()
    with driver.session() as session:
        result = session.run(query, limit=limit)
        return [dict(r) for r in result]


def get_most_cited_papers(limit: int = 10) -> list[dict]:
    """Papers avec le plus de citations"""
    query = """
    MATCH (p:Paper)
    WHERE p.citation_count > 0
    RETURN p.title AS title, p.year AS year,
           p.citation_count AS citations, p.arxiv_id AS arxiv_id
    ORDER BY citations DESC
    LIMIT $limit
    """
    driver = get_driver()
    with driver.session() as session:
        result = session.run(query, limit=limit)
        return [dict(r) for r in result]


def get_top_topics(limit: int = 15) -> list[dict]:
    """Topics les plus populaires"""
    query = """
    MATCH (p:Paper)-[:HAS_TOPIC]->(t:Topic)
    RETURN t.name AS topic, count(p) AS papers
    ORDER BY papers DESC
    LIMIT $limit
    """
    driver = get_driver()
    with driver.session() as session:
        result = session.run(query, limit=limit)
        return [dict(r) for r in result]


def get_collaboration_network(limit: int = 20) -> list[dict]:
    """Reseau de collaborations entre auteurs"""
    query = """
    MATCH (a1:Author)-[r:COLLABORATED_WITH]-(a2:Author)
    WHERE id(a1) < id(a2)
    RETURN a1.name AS author1, a2.name AS author2,
           r.count AS collaborations
    ORDER BY collaborations DESC
    LIMIT $limit
    """
    driver = get_driver()
    with driver.session() as session:
        result = session.run(query, limit=limit)
        return [dict(r) for r in result]


def get_papers_by_year() -> list[dict]:
    """Distribution des papers par annee"""
    query = """
    MATCH (p:Paper)
    WHERE p.year IS NOT NULL
    RETURN p.year AS year, count(p) AS papers
    ORDER BY year DESC
    """
    driver = get_driver()
    with driver.session() as session:
        result = session.run(query)
        return [dict(r) for r in result]


def get_topics_by_year(year: int, limit: int = 10) -> list[dict]:
    """Topics tendance pour une annee donnee"""
    query = """
    MATCH (p:Paper)-[:HAS_TOPIC]->(t:Topic)
    WHERE p.year = $year
    RETURN t.name AS topic, count(p) AS papers
    ORDER BY papers DESC
    LIMIT $limit
    """
    driver = get_driver()
    with driver.session() as session:
        result = session.run(query, year=year, limit=limit)
        return [dict(r) for r in result]


def get_author_collaborators(author_name: str) -> list[dict]:
    """Trouve tous les collaborateurs d'un auteur"""
    query = """
    MATCH (a:Author {name: $name})-[r:COLLABORATED_WITH]-(collaborator:Author)
    RETURN collaborator.name AS collaborator,
           r.count AS shared_papers
    ORDER BY shared_papers DESC
    """
    driver = get_driver()
    with driver.session() as session:
        result = session.run(query, name=author_name)
        return [dict(r) for r in result]


def get_papers_by_topic(topic: str, limit: int = 10) -> list[dict]:
    """Papers lies a un topic specifique"""
    query = """
    MATCH (p:Paper)-[:HAS_TOPIC]->(t:Topic)
    WHERE toLower(t.name) CONTAINS toLower($topic)
    RETURN p.title AS title, p.year AS year,
           p.citation_count AS citations
    ORDER BY citations DESC
    LIMIT $limit
    """
    driver = get_driver()
    with driver.session() as session:
        result = session.run(query, topic=topic, limit=limit)
        return [dict(r) for r in result]


def get_category_distribution() -> list[dict]:
    """Distribution des papers par categorie arXiv"""
    query = """
    MATCH (p:Paper)-[:BELONGS_TO]->(c:Category)
    RETURN c.name AS category, count(p) AS papers
    ORDER BY papers DESC
    """
    driver = get_driver()
    with driver.session() as session:
        result = session.run(query)
        return [dict(r) for r in result]


def get_author_papers(author_name: str) -> list[dict]:
    """Tous les papers d'un auteur"""
    query = """
    MATCH (a:Author)-[:WROTE]->(p:Paper)
    WHERE toLower(a.name) CONTAINS toLower($name)
    RETURN p.title AS title, p.year AS year,
           p.citation_count AS citations
    ORDER BY p.year DESC
    """
    driver = get_driver()
    with driver.session() as session:
        result = session.run(query, name=author_name)
        return [dict(r) for r in result]


if __name__ == "__main__":
    print("=== Test des requetes Neo4j ===\n")

    print("Top 10 auteurs les plus prolifiques :")
    for r in get_most_prolific_authors():
        print(f"  {r['author']:<40} {r['papers']} papers")

    print("\nTop 15 topics :")
    for r in get_top_topics():
        print(f"  {r['topic']:<30} {r['papers']} papers")

    print("\nDistribution par annee :")
    for r in get_papers_by_year()[:10]:
        print(f"  {r['year']} : {r['papers']} papers")

    print("\nTop collaborations :")
    for r in get_collaboration_network(10):
        print(f"  {r['author1']} <-> {r['author2']} ({r['collaborations']} papers)")

    print("\nCategories arXiv :")
    for r in get_category_distribution()[:10]:
        print(f"  {r['category']:<20} {r['papers']} papers")