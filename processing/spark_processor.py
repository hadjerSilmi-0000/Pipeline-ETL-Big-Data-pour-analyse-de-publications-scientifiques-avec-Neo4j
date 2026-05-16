import os
import sys

os.environ["PYSPARK_PYTHON"]        = sys.executable
os.environ["PYSPARK_DRIVER_PYTHON"] = sys.executable

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, lower, trim
from pyspark.sql.types import (
    StructType, StructField, StringType,
    IntegerType, ArrayType
)
from config.settings import SPARK_APP_NAME, DATA_PROCESSED_PATH
from config.logging_config import setup_logger

logger = setup_logger("spark_processor")

SCHEMA = StructType([
    StructField("arxiv_id",                   StringType(),            True),
    StructField("s2_id",                      StringType(),            True),
    StructField("title",                      StringType(),            True),
    StructField("abstract",                   StringType(),            True),
    StructField("year",                       IntegerType(),           True),
    StructField("published",                  StringType(),            True),
    StructField("doi",                        StringType(),            True),
    StructField("pdf_url",                    StringType(),            True),
    StructField("venue",                      StringType(),            True),
    StructField("query",                      StringType(),            True),
    StructField("citation_count",             IntegerType(),           True),
    StructField("reference_count",            IntegerType(),           True),
    StructField("influential_citation_count", IntegerType(),           True),
    StructField("authors",                    ArrayType(StringType()), True),
    StructField("categories",                 ArrayType(StringType()), True),
    StructField("keywords",                   ArrayType(StringType()), True),
    StructField("citations",                  ArrayType(StringType()), True),
    StructField("references",                 ArrayType(StringType()), True),
])


def sanitize(papers: list[dict]) -> list[dict]:
    clean = []
    for p in papers:
        clean.append({
            "arxiv_id"                   : str(p.get("arxiv_id") or ""),
            "s2_id"                      : str(p.get("s2_id") or ""),
            "title"                      : str(p.get("title") or ""),
            "abstract"                   : str(p.get("abstract") or ""),
            "year"                       : int(p["year"]) if p.get("year") else None,
            "published"                  : str(p.get("published") or ""),
            "doi"                        : str(p.get("doi") or ""),
            "pdf_url"                    : str(p.get("pdf_url") or ""),
            "venue"                      : str(p.get("venue") or ""),
            "query"                      : str(p.get("query") or ""),
            "citation_count"             : int(p.get("citation_count") or 0),
            "reference_count"            : int(p.get("reference_count") or 0),
            "influential_citation_count" : int(p.get("influential_citation_count") or 0),
            "authors"                    : [str(a) for a in (p.get("authors") or [])],
            "categories"                 : [str(c) for c in (p.get("categories") or [])],
            "keywords"                   : [str(k) for k in (p.get("keywords") or [])],
            "citations"                  : [str(c) for c in (p.get("citations") or [])],
            "references"                 : [str(r) for r in (p.get("references") or [])],
        })
    return clean


def process_papers(papers: list[dict]) -> list[dict]:
    print("Demarrage traitement Spark...")

    spark = SparkSession.builder \
        .appName(SPARK_APP_NAME) \
        .master("local[2]") \
        .config("spark.driver.memory", "1g") \
        .config("spark.sql.shuffle.partitions", "2") \
        .config("spark.ui.enabled", "false") \
        .config("spark.driver.host", "localhost") \
        .getOrCreate()

    spark.sparkContext.setLogLevel("ERROR")
    print("Session Spark creee.")

    sanitized = sanitize(papers)
    print(f"Donnees sanitizees : {len(sanitized)} papers")

    df = spark.createDataFrame(sanitized, schema=SCHEMA)
    print(f"DataFrame cree : {df.count()} lignes")

    df_clean = df \
        .withColumn("title",    trim(lower(col("title")))) \
        .withColumn("abstract", trim(lower(col("abstract")))) \
        .filter(col("title") != "") \
        .filter(col("arxiv_id") != "") \
        .dropDuplicates(["arxiv_id"])

    total = df_clean.count()
    print(f"Apres nettoyage : {total} papers")

    print("\nDistribution par annee :")
    df_clean.groupBy("year").count().orderBy("year", ascending=False).show(10)

    print("Distribution par query :")
    df_clean.groupBy("query").count().orderBy("count", ascending=False).show()

    print("Top 10 papers par citations :")
    df_clean.select("title", "citation_count", "year") \
        .orderBy("citation_count", ascending=False) \
        .show(10, truncate=50)

    processed = [row.asDict() for row in df_clean.collect()]

    output_path = os.path.join(DATA_PROCESSED_PATH, "spark_processed.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(processed, f, ensure_ascii=False, indent=2, default=str)

    print(f"\nSauvegarde : {output_path} ({len(processed)} papers)")
    logger.info(f"Spark termine — {len(processed)} papers")

    spark.stop()
    print("Session Spark arretee.")
    return processed


if __name__ == "__main__":
    input_path = os.path.join(DATA_PROCESSED_PATH, "cleaned_papers.json")
    with open(input_path, "r", encoding="utf-8") as f:
        papers = json.load(f)

    print(f"{len(papers)} papers charges pour Spark...")
    processed = process_papers(papers)
    print(f"Traitement termine : {len(processed)} papers")