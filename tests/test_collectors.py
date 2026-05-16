"""
Tests basiques — collectors
Verifier avec : python -m pytest tests/ -v
"""
import os
import sys
import json
import tempfile
import pytest

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ─── Test arxiv_collector ─────────────────────────────────────────────────────

class TestArxivCollector:
    def test_collect_papers_returns_list(self):
        """La fonction retourne une liste"""
        from collectors.arxiv_collector import collect_papers
        papers = collect_papers("machine learning", max_results=3)
        assert isinstance(papers, list)
        assert len(papers) > 0

    def test_paper_has_required_fields(self):
        """Chaque paper a les champs obligatoires"""
        from collectors.arxiv_collector import collect_papers
        papers = collect_papers("deep learning", max_results=2)
        required = {"arxiv_id", "title", "abstract", "authors", "categories"}
        for paper in papers:
            for field in required:
                assert field in paper, f"Champ manquant : {field}"

    def test_arxiv_ids_are_unique(self):
        """Pas de doublons dans les arxiv_id"""
        from collectors.arxiv_collector import collect_papers
        papers = collect_papers("neural network", max_results=5)
        ids = [p["arxiv_id"] for p in papers]
        assert len(ids) == len(set(ids)), "Doublons detectes dans arxiv_id"

    def test_save_papers_creates_file(self, tmp_path):
        """save_papers cree bien le fichier JSON"""
        from collectors.arxiv_collector import collect_papers
        import importlib
        import collectors.arxiv_collector as mod
        original = mod.DATA_RAW_PATH
        mod.DATA_RAW_PATH = str(tmp_path)

        papers = collect_papers("graph", max_results=2)
        filepath = mod.save_papers(papers, "test_query")

        assert os.path.exists(filepath)
        with open(filepath) as f:
            loaded = json.load(f)
        assert len(loaded) == len(papers)

        mod.DATA_RAW_PATH = original