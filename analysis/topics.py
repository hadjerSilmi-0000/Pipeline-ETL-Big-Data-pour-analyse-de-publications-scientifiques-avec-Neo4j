"""
analysis/topics.py
Analyse approfondie des topics et tendances de recherche.
"""

import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from collections import defaultdict
from graph.schema import get_driver
from config.logging_config import setup_logger

logger = setup_logger("analysis.topics")


# ─── Distribution globale ────────────────────────────────────────────────────

def get_topic_distribution(limit: int = 20) -> list[dict]:
    """Distribution globale des topics par nombre de papers"""
    query = """
    MATCH (p:Paper)-[:HAS_TOPIC]->(t:Topic)
    RETURN t.name AS topic, count(p) AS papers
    ORDER BY papers DESC
    LIMIT $limit
    """
    driver = get_driver()
    with driver.session() as session:
        result = [dict(r) for r in session.run(query, limit=limit)]
    driver.close()
    return result


def get_topic_count() -> int:
    """Nombre total de topics uniques"""
    query = "MATCH (t:Topic) RETURN count(t) AS n"
    driver = get_driver()
    with driver.session() as session:
        result = session.run(query).single()
    driver.close()
    return result["n"]


def get_avg_topics_per_paper() -> float:
    """Nombre moyen de topics par paper"""
    query = """
    MATCH (p:Paper)-[:HAS_TOPIC]->(t:Topic)
    WITH p, count(t) AS n_topics
    RETURN avg(n_topics) AS avg_topics
    """
    driver = get_driver()
    with driver.session() as session:
        result = session.run(query).single()
    driver.close()
    return round(result["avg_topics"] or 0, 2)


# ─── Analyse temporelle ───────────────────────────────────────────────────────

def get_topic_by_year(topic: str) -> list[dict]:
    """Evolution d'un topic specifique dans le temps"""
    query = """
    MATCH (p:Paper)-[:HAS_TOPIC]->(t:Topic)
    WHERE toLower(t.name) CONTAINS toLower($topic) AND p.year IS NOT NULL
    RETURN p.year AS year, count(p) AS papers
    ORDER BY year
    """
    driver = get_driver()
    with driver.session() as session:
        result = [dict(r) for r in session.run(query, topic=topic)]
    driver.close()
    return result


def get_trending_topics(recent_year: int = 2023, baseline_year: int = 2021,
                        limit: int = 10) -> list[dict]:
    """
    Topics en progression : compare le volume recent vs baseline.
    Retourne les topics dont la croissance est la plus forte.
    """
    query = """
    MATCH (p:Paper)-[:HAS_TOPIC]->(t:Topic)
    WHERE p.year IN [$recent, $baseline]
    WITH t.name AS topic,
         sum(CASE WHEN p.year = $recent   THEN 1 ELSE 0 END) AS recent_count,
         sum(CASE WHEN p.year = $baseline THEN 1 ELSE 0 END) AS baseline_count
    WHERE recent_count > 0
    RETURN topic, recent_count, baseline_count
    ORDER BY (recent_count - baseline_count) DESC
    LIMIT $limit
    """
    driver = get_driver()
    with driver.session() as session:
        result = [dict(r) for r in session.run(
            query, recent=recent_year, baseline=baseline_year, limit=limit
        )]
    driver.close()

    return [
        {
            **r,
            "growth": r["recent_count"] - r["baseline_count"]
        }
        for r in result
    ]


def get_topics_by_year(year: int, limit: int = 15) -> list[dict]:
    """Top topics pour une annee donnee"""
    query = """
    MATCH (p:Paper)-[:HAS_TOPIC]->(t:Topic)
    WHERE p.year = $year
    RETURN t.name AS topic, count(p) AS papers
    ORDER BY papers DESC
    LIMIT $limit
    """
    driver = get_driver()
    with driver.session() as session:
        result = [dict(r) for r in session.run(query, year=year, limit=limit)]
    driver.close()
    return result


def get_topic_evolution(top_n: int = 5) -> list[dict]:
    """
    Evolution dans le temps des N topics les plus populaires.
    Retourne une liste de {topic, year, papers} pour un graphe de lignes.
    """
    # recuperer les top topics
    top_topics = [r["topic"] for r in get_topic_distribution(top_n)]

    query = """
    MATCH (p:Paper)-[:HAS_TOPIC]->(t:Topic)
    WHERE t.name IN $topics AND p.year IS NOT NULL
    RETURN t.name AS topic, p.year AS year, count(p) AS papers
    ORDER BY year
    """
    driver = get_driver()
    with driver.session() as session:
        result = [dict(r) for r in session.run(query, topics=top_topics)]
    driver.close()
    return result


# ─── Co-occurrence de topics ─────────────────────────────────────────────────

def get_topic_cooccurrence(limit: int = 15) -> list[dict]:
    """
    Paires de topics qui apparaissent souvent ensemble dans le meme paper.
    Utile pour identifier des sous-domaines ou intersections.
    """
    query = """
    MATCH (p:Paper)-[:HAS_TOPIC]->(t1:Topic),
          (p)-[:HAS_TOPIC]->(t2:Topic)
    WHERE id(t1) < id(t2)
    RETURN t1.name AS topic1, t2.name AS topic2, count(p) AS co_papers
    ORDER BY co_papers DESC
    LIMIT $limit
    """
    driver = get_driver()
    with driver.session() as session:
        result = [dict(r) for r in session.run(query, limit=limit)]
    driver.close()
    return result


# ─── Topics par categorie arXiv ──────────────────────────────────────────────

def get_topics_per_category(category: str, limit: int = 10) -> list[dict]:
    """Top topics dans une categorie arXiv specifique"""
    query = """
    MATCH (p:Paper)-[:BELONGS_TO]->(c:Category),
          (p)-[:HAS_TOPIC]->(t:Topic)
    WHERE toLower(c.name) CONTAINS toLower($category)
    RETURN t.name AS topic, count(p) AS papers
    ORDER BY papers DESC
    LIMIT $limit
    """
    driver = get_driver()
    with driver.session() as session:
        result = [dict(r) for r in session.run(query, category=category, limit=limit)]
    driver.close()
    return result


def get_category_topic_matrix(top_categories: int = 5, top_topics: int = 10) -> list[dict]:
    """
    Matrice categorie × topic : combien de papers dans chaque intersection.
    Utile pour un heatmap dans le dashboard.
    """
    # top categories
    cat_query = """
    MATCH (p:Paper)-[:BELONGS_TO]->(c:Category)
    RETURN c.name AS category, count(p) AS n
    ORDER BY n DESC LIMIT $limit
    """
    # top topics
    top_query = """
    MATCH (p:Paper)-[:HAS_TOPIC]->(t:Topic)
    RETURN t.name AS topic, count(p) AS n
    ORDER BY n DESC LIMIT $limit
    """
    # intersection
    matrix_query = """
    MATCH (p:Paper)-[:BELONGS_TO]->(c:Category),
          (p)-[:HAS_TOPIC]->(t:Topic)
    WHERE c.name IN $categories AND t.name IN $topics
    RETURN c.name AS category, t.name AS topic, count(p) AS papers
    """
    driver = get_driver()
    with driver.session() as session:
        categories = [r["category"] for r in session.run(cat_query, limit=top_categories)]
        topics     = [r["topic"]    for r in session.run(top_query,  limit=top_topics)]
        result     = [dict(r) for r in session.run(
            matrix_query, categories=categories, topics=topics
        )]
    driver.close()
    return result


# ─── Topics et citations ──────────────────────────────────────────────────────

def get_topics_by_impact(limit: int = 10) -> list[dict]:
    """Topics dont les papers ont le plus fort impact (citation_count moyen)"""
    query = """
    MATCH (p:Paper)-[:HAS_TOPIC]->(t:Topic)
    WHERE p.citation_count > 0
    WITH t.name AS topic,
         count(p) AS papers,
         avg(p.citation_count) AS avg_citations,
         sum(p.citation_count) AS total_citations
    WHERE papers >= 3
    RETURN topic, papers, 
           round(avg_citations, 1) AS avg_citations,
           total_citations
    ORDER BY avg_citations DESC
    LIMIT $limit
    """
    driver = get_driver()
    with driver.session() as session:
        result = [dict(r) for r in session.run(query, limit=limit)]
    driver.close()
    return result


def get_niche_topics(min_papers: int = 1, max_papers: int = 3) -> list[dict]:
    """Topics de niche : tres peu de papers (domaines emergents ou tres specifiques)"""
    query = """
    MATCH (p:Paper)-[:HAS_TOPIC]->(t:Topic)
    WITH t.name AS topic, count(p) AS papers
    WHERE papers >= $min AND papers <= $max
    RETURN topic, papers
    ORDER BY papers DESC, topic
    """
    driver = get_driver()
    with driver.session() as session:
        result = [dict(r) for r in session.run(query, min=min_papers, max=max_papers)]
    driver.close()
    return result


# ─── Rapport ─────────────────────────────────────────────────────────────────

def print_report():
    print("\n" + "="*60)
    print("  ANALYSE — TOPICS & TENDANCES")
    print("="*60)

    print("\n[1] Vue d'ensemble")
    print(f"  Topics uniques        : {get_topic_count()}")
    print(f"  Topics / paper (moy)  : {get_avg_topics_per_paper()}")

    print("\n[2] Top 20 topics globaux")
    for r in get_topic_distribution(20):
        bar = "█" * min(r["papers"], 40)
        print(f"  {r['topic']:<25} {r['papers']:>4}  {bar}")

    print("\n[3] Topics en progression (2021 → 2023)")
    for r in get_trending_topics(recent_year=2023, baseline_year=2021, limit=10):
        sign = "+" if r["growth"] >= 0 else ""
        print(f"  {r['topic']:<25} {r['baseline_count']} → {r['recent_count']}  ({sign}{r['growth']})")

    print("\n[4] Co-occurrence de topics (top 10 paires)")
    for r in get_topic_cooccurrence(10):
        print(f"  {r['topic1']} + {r['topic2']} : {r['co_papers']} papers")

    print("\n[5] Topics par impact (citations moyennes)")
    for r in get_topics_by_impact(10):
        print(f"  {r['topic']:<25} avg={r['avg_citations']:>8}  papers={r['papers']}")

    print("\n[6] Topics de niche (1-3 papers)")
    niche = get_niche_topics()
    print(f"  {len(niche)} topics de niche detectes")
    for r in niche[:10]:
        print(f"  {r['topic']}")


if __name__ == "__main__":
    print_report()