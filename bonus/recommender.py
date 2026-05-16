import os
import sys
import json
import math
from collections import defaultdict

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from graph.schema import get_driver
from config.logging_config import setup_logger

logger = setup_logger("recommender")


# ─── TF-IDF based recommender ────────────────────────────────────────────────

def load_papers_from_neo4j() -> list[dict]:
    """Charge les papers avec leurs topics depuis Neo4j"""
    query = """
    MATCH (p:Paper)
    OPTIONAL MATCH (p)-[:HAS_TOPIC]->(t:Topic)
    OPTIONAL MATCH (p)-[:BELONGS_TO]->(c:Category)
    WITH p, collect(DISTINCT t.name) AS topics, collect(DISTINCT c.name) AS categories
    RETURN p.arxiv_id  AS arxiv_id,
           p.title     AS title,
           p.year      AS year,
           p.citation_count AS citation_count,
           topics, categories
    """
    driver = get_driver()
    with driver.session() as session:
        result = session.run(query)
        papers = [dict(r) for r in result]
    driver.close()
    return papers


def build_tfidf(papers: list[dict]) -> dict:
    """Construit un index TF-IDF sur les topics des papers"""
    # TF : frequence du terme dans le document
    tf = {}
    for p in papers:
        doc_id = p["arxiv_id"]
        terms  = p.get("topics", []) + p.get("categories", [])
        if not terms:
            tf[doc_id] = {}
            continue
        freq = defaultdict(int)
        for t in terms:
            if t:
                freq[t.lower()] += 1
        total = len(terms)
        tf[doc_id] = {t: c / total for t, c in freq.items()}

    # IDF : inverse document frequency
    df  = defaultdict(int)
    N   = len(papers)
    for doc_id, term_tf in tf.items():
        for term in term_tf:
            df[term] += 1

    idf = {term: math.log(N / (1 + count)) for term, count in df.items()}

    # TF-IDF
    tfidf = {}
    for doc_id, term_tf in tf.items():
        tfidf[doc_id] = {
            term: tf_val * idf.get(term, 0)
            for term, tf_val in term_tf.items()
        }

    return tfidf


def cosine_similarity(vec1: dict, vec2: dict) -> float:
    """Calcule la similarite cosinus entre deux vecteurs TF-IDF"""
    if not vec1 or not vec2:
        return 0.0

    common = set(vec1.keys()) & set(vec2.keys())
    if not common:
        return 0.0

    dot     = sum(vec1[t] * vec2[t] for t in common)
    norm1   = math.sqrt(sum(v ** 2 for v in vec1.values()))
    norm2   = math.sqrt(sum(v ** 2 for v in vec2.values()))

    if norm1 == 0 or norm2 == 0:
        return 0.0

    return dot / (norm1 * norm2)


def recommend_similar_papers(
    arxiv_id : str,
    papers   : list[dict],
    tfidf    : dict,
    top_n    : int = 5
) -> list[dict]:
    """Recommande les papers les plus similaires a un paper donne"""

    if arxiv_id not in tfidf:
        logger.warning(f"Paper {arxiv_id} non trouve dans l'index TF-IDF")
        return []

    target_vec    = tfidf[arxiv_id]
    paper_by_id   = {p["arxiv_id"]: p for p in papers}

    scores = []
    for pid, vec in tfidf.items():
        if pid == arxiv_id:
            continue
        sim = cosine_similarity(target_vec, vec)
        if sim > 0:
            scores.append((pid, sim))

    scores.sort(key=lambda x: x[1], reverse=True)
    top = scores[:top_n]

    recommendations = []
    for pid, sim in top:
        p = paper_by_id.get(pid, {})
        recommendations.append({
            "arxiv_id"      : pid,
            "title"         : p.get("title", ""),
            "year"          : p.get("year"),
            "citation_count": p.get("citation_count", 0),
            "similarity"    : round(sim, 4)
        })

    return recommendations


def recommend_for_author(
    author_name : str,
    papers      : list[dict],
    tfidf       : dict,
    top_n       : int = 5
) -> list[dict]:
    """Recommande des papers a un auteur based sur ses publications"""
    query = """
    MATCH (a:Author)-[:WROTE]->(p:Paper)
    WHERE toLower(a.name) CONTAINS toLower($name)
    RETURN p.arxiv_id AS arxiv_id
    """
    driver = get_driver()
    with driver.session() as session:
        result  = session.run(query, name=author_name)
        written = [r["arxiv_id"] for r in result]
    driver.close()

    if not written:
        return []

    # vecteur moyen de l'auteur
    author_vec = defaultdict(float)
    count = 0
    for pid in written:
        if pid in tfidf:
            for term, val in tfidf[pid].items():
                author_vec[term] += val
            count += 1

    if count == 0:
        return []

    author_vec = {t: v / count for t, v in author_vec.items()}

    # calcul similarite avec tous les autres papers
    paper_by_id = {p["arxiv_id"]: p for p in papers}
    scores = []
    for pid, vec in tfidf.items():
        if pid in written:
            continue
        sim = cosine_similarity(dict(author_vec), vec)
        if sim > 0:
            scores.append((pid, sim))

    scores.sort(key=lambda x: x[1], reverse=True)

    recommendations = []
    for pid, sim in scores[:top_n]:
        p = paper_by_id.get(pid, {})
        recommendations.append({
            "arxiv_id"      : pid,
            "title"         : p.get("title", ""),
            "year"          : p.get("year"),
            "citation_count": p.get("citation_count", 0),
            "similarity"    : round(sim, 4)
        })

    return recommendations


def store_recommendations_in_neo4j(
    papers : list[dict],
    tfidf  : dict,
    top_n  : int = 3
):
    """Stocke les relations SIMILAR_TO dans Neo4j"""
    query = """
    MATCH (p1:Paper {arxiv_id: $id1})
    MATCH (p2:Paper {arxiv_id: $id2})
    MERGE (p1)-[r:SIMILAR_TO]-(p2)
    SET r.similarity = $sim
    """
    driver = get_driver()
    stored = 0

    with driver.session() as session:
        for paper in papers:
            arxiv_id = paper["arxiv_id"]
            recs     = recommend_similar_papers(arxiv_id, papers, tfidf, top_n)
            for rec in recs:
                session.run(query,
                    id1=arxiv_id,
                    id2=rec["arxiv_id"],
                    sim=rec["similarity"]
                )
                stored += 1

    driver.close()
    logger.info(f"{stored} relations SIMILAR_TO stockees dans Neo4j")
    print(f"{stored} relations SIMILAR_TO stockees dans Neo4j")


def run_recommender():
    """Pipeline complet du systeme de recommandation"""
    print("Chargement des papers depuis Neo4j...")
    papers = load_papers_from_neo4j()
    print(f"{len(papers)} papers charges")

    print("Construction de l'index TF-IDF...")
    tfidf = build_tfidf(papers)
    print(f"Index TF-IDF construit — {len(tfidf)} documents")

    # test recommandation paper
    sample = papers[0]
    print(f"\nRecommandations pour : '{sample['title'][:60]}...'")
    recs = recommend_similar_papers(sample["arxiv_id"], papers, tfidf, top_n=5)
    for r in recs:
        print(f"  [{r['similarity']}] {r['title'][:60]}")

    # test recommandation auteur
    print(f"\nRecommandations pour auteur 'Bengio' :")
    author_recs = recommend_for_author("Bengio", papers, tfidf, top_n=5)
    for r in author_recs:
        print(f"  [{r['similarity']}] {r['title'][:60]}")

    # stockage dans Neo4j
    print("\nStockage des relations SIMILAR_TO dans Neo4j...")
    store_recommendations_in_neo4j(papers, tfidf, top_n=3)

    return papers, tfidf


if __name__ == "__main__":
    print("Demarrage du systeme de recommandation...")
    papers, tfidf = run_recommender()
    print("Termine !")