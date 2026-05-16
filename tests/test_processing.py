"""
Tests basiques — processing (cleaner)
"""
import os
import sys
import json
import pytest

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from processing.cleaner import (
    normalize_text,
    normalize_author_name,
    extract_year,
    extract_keywords,
    clean_paper
)


SAMPLE_PAPER = {
    "arxiv_id": "2301.00001",
    "title"   : "  Deep  Learning  for NLP  ",
    "abstract": "We propose a novel deep learning approach for natural language processing.",
    "authors" : ["John Smith", "Jane Doe", "  "],
    "categories" : ["cs.LG", "cs.CL"],
    "published": "2023-01-15",
    "doi"     : "10.1234/test",
    "pdf_url" : "https://arxiv.org/pdf/2301.00001",
    "query"   : "deep learning"
}


# ─── normalize_text ───────────────────────────────────────────────────────────

class TestNormalizeText:
    def test_strips_whitespace(self):
        assert normalize_text("  hello world  ") == "hello world"

    def test_collapses_multiple_spaces(self):
        assert normalize_text("a   b   c") == "a b c"

    def test_empty_string(self):
        assert normalize_text("") == ""

    def test_none_returns_empty(self):
        assert normalize_text(None) == ""

    def test_unicode_normalization(self):
        result = normalize_text("caf\u00e9")
        assert "caf" in result


# ─── normalize_author_name ────────────────────────────────────────────────────

class TestNormalizeAuthorName:
    def test_removes_title_dr(self):
        result = normalize_author_name("Dr. John Smith")
        assert "Dr" not in result
        assert "John Smith" in result

    def test_removes_title_prof(self):
        result = normalize_author_name("Prof Jane Doe")
        assert "Prof" not in result

    def test_empty_returns_empty(self):
        assert normalize_author_name("") == ""


# ─── extract_year ─────────────────────────────────────────────────────────────

class TestExtractYear:
    def test_iso_date(self):
        assert extract_year("2023-06-15") == 2023

    def test_year_in_string(self):
        assert extract_year("Published in 2021") == 2021

    def test_none_returns_none(self):
        assert extract_year(None) is None

    def test_no_year_returns_none(self):
        assert extract_year("no date here") is None


# ─── extract_keywords ────────────────────────────────────────────────────────

class TestExtractKeywords:
    def test_returns_list(self):
        keywords = extract_keywords("Deep learning for natural language processing")
        assert isinstance(keywords, list)

    def test_max_15_keywords(self):
        text = " ".join(["word"] * 100)
        keywords = extract_keywords(text)
        assert len(keywords) <= 15

    def test_no_stopwords(self):
        keywords = extract_keywords("the and or but in on at to for")
        assert keywords == []

    def test_filters_short_words(self):
        keywords = extract_keywords("a ab abc abcd")
        assert "a" not in keywords
        assert "ab" not in keywords
        assert "abc" not in keywords


# ─── clean_paper ─────────────────────────────────────────────────────────────

class TestCleanPaper:
    def test_valid_paper_returns_dict(self):
        result = clean_paper(SAMPLE_PAPER)
        assert result is not None
        assert isinstance(result, dict)

    def test_required_fields_present(self):
        result = clean_paper(SAMPLE_PAPER)
        required = ["arxiv_id", "title", "abstract", "authors", "year",
                    "categories", "keywords", "doi", "pdf_url", "citation_count"]
        for field in required:
            assert field in result, f"Champ manquant : {field}"

    def test_title_normalized(self):
        result = clean_paper(SAMPLE_PAPER)
        assert result["title"] == result["title"].strip()

    def test_year_extracted(self):
        result = clean_paper(SAMPLE_PAPER)
        assert result["year"] == 2023

    def test_authors_filtered(self):
        result = clean_paper(SAMPLE_PAPER)
        # l'auteur vide "  " doit etre filtre
        assert all(len(a) > 2 for a in result["authors"])

    def test_missing_arxiv_id_returns_none(self):
        bad = {**SAMPLE_PAPER, "arxiv_id": ""}
        assert clean_paper(bad) is None

    def test_missing_title_returns_none(self):
        bad = {**SAMPLE_PAPER, "title": ""}
        assert clean_paper(bad) is None

    def test_no_authors_returns_none(self):
        bad = {**SAMPLE_PAPER, "authors": []}
        assert clean_paper(bad) is None

    def test_keywords_are_list(self):
        result = clean_paper(SAMPLE_PAPER)
        assert isinstance(result["keywords"], list)