"""
Tests basiques — graph (connexion + requetes)
"""
import os
import sys
import pytest

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ─── Connexion Neo4j ──────────────────────────────────────────────────────────

class TestNeo4jConnection:
    def test_driver_connects(self):
        """Le driver Neo4j se connecte sans erreur"""
        from graph.schema import get_driver
        driver = get_driver()
        driver.verify_connectivity()
        driver.close()

    def test_graph_has_papers(self):
        """Le graphe contient des papers"""
        from graph.schema import get_driver
        driver = get_driver()
        with driver.session() as session:
            result = session.run("MATCH (p:Paper) RETURN count(p) AS n").single()
            assert result["n"] > 0, "Aucun paper dans le graphe"
        driver.close()

    def test_graph_has_authors(self):
        """Le graphe contient des auteurs"""
        from graph.schema import get_driver
        driver = get_driver()
        with driver.session() as session:
            result = session.run("MATCH (a:Author) RETURN count(a) AS n").single()
            assert result["n"] > 0, "Aucun auteur dans le graphe"
        driver.close()

    def test_graph_has_topics(self):
        """Le graphe contient des topics"""
        from graph.schema import get_driver
        driver = get_driver()
        with driver.session() as session:
            result = session.run("MATCH (t:Topic) RETURN count(t) AS n").single()
            assert result["n"] > 0, "Aucun topic dans le graphe"
        driver.close()


# ─── Requetes ────────────────────────────────────────────────────────────────

class TestGraphQueries:
    def test_get_most_prolific_authors(self):
        """Retourne une liste d'auteurs avec count"""
        from graph.queries import get_most_prolific_authors
        result = get_most_prolific_authors(limit=5)
        assert isinstance(result, list)
        assert len(result) > 0
        assert "author" in result[0]
        assert "papers" in result[0]
        # trie par ordre decroissant
        if len(result) > 1:
            assert result[0]["papers"] >= result[1]["papers"]

    def test_get_most_cited_papers(self):
        """Retourne les papers les plus cites"""
        from graph.queries import get_most_cited_papers
        result = get_most_cited_papers(limit=5)
        assert isinstance(result, list)
        # trie par citations decroissantes si pas vide
        if len(result) > 1:
            assert result[0]["citations"] >= result[1]["citations"]

    def test_get_top_topics(self):
        """Retourne les topics les plus populaires"""
        from graph.queries import get_top_topics
        result = get_top_topics(limit=10)
        assert isinstance(result, list)
        assert len(result) > 0
        assert "topic" in result[0]
        assert "papers" in result[0]

    def test_get_papers_by_year(self):
        """Distribution par annee non vide"""
        from graph.queries import get_papers_by_year
        result = get_papers_by_year()
        assert isinstance(result, list)
        assert len(result) > 0
        assert "year" in result[0]
        assert "papers" in result[0]

    def test_get_category_distribution(self):
        """Categories arXiv presentes"""
        from graph.queries import get_category_distribution
        result = get_category_distribution()
        assert isinstance(result, list)
        assert len(result) > 0

    def test_get_collaboration_network(self):
        """Reseau de collaborations non vide"""
        from graph.queries import get_collaboration_network
        result = get_collaboration_network(limit=10)
        assert isinstance(result, list)
        assert len(result) > 0
        assert "author1" in result[0]
        assert "author2" in result[0]

    def test_get_author_papers(self):
        """Chercher un auteur generique retourne au moins un paper"""
        from graph.queries import get_most_prolific_authors, get_author_papers
        top = get_most_prolific_authors(limit=1)
        if top:
            papers = get_author_papers(top[0]["author"])
            assert isinstance(papers, list)
            assert len(papers) > 0


# ─── Recommander ─────────────────────────────────────────────────────────────

class TestRecommender:
    def test_tfidf_build(self):
        """L'index TF-IDF se construit correctement"""
        from bonus.recommender import load_papers_from_neo4j, build_tfidf
        papers = load_papers_from_neo4j()
        assert len(papers) > 0

        tfidf = build_tfidf(papers)
        assert len(tfidf) > 0
        # chaque vecteur est un dict de floats
        sample = next(iter(tfidf.values()))
        assert isinstance(sample, dict)

    def test_cosine_similarity_same_vector(self):
        """Cosinus de deux vecteurs identiques = 1"""
        from bonus.recommender import cosine_similarity
        vec = {"neural": 0.5, "learning": 0.3, "graph": 0.2}
        sim = cosine_similarity(vec, vec)
        assert abs(sim - 1.0) < 1e-6

    def test_cosine_similarity_disjoint(self):
        """Cosinus de vecteurs sans termes communs = 0"""
        from bonus.recommender import cosine_similarity
        v1 = {"neural": 0.5}
        v2 = {"transformer": 0.5}
        assert cosine_similarity(v1, v2) == 0.0

    def test_recommend_returns_list(self):
        """recommend_similar_papers retourne une liste"""
        from bonus.recommender import load_papers_from_neo4j, build_tfidf, recommend_similar_papers
        papers = load_papers_from_neo4j()
        tfidf  = build_tfidf(papers)
        sample = papers[0]["arxiv_id"]
        recs   = recommend_similar_papers(sample, papers, tfidf, top_n=3)
        assert isinstance(recs, list)
        assert len(recs) <= 3
        if recs:
            assert "arxiv_id" in recs[0]
            assert "similarity" in recs[0]
            assert 0 <= recs[0]["similarity"] <= 1