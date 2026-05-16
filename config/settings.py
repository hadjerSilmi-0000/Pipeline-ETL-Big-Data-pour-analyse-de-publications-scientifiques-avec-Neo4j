import os
from dotenv import load_dotenv

load_dotenv()

# ─── Neo4j ───────────────────────────────────────────────
NEO4J_URI      = os.getenv("NEO4J_URI")
NEO4J_USER     = os.getenv("NEO4J_USER")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

# ─── APIs ────────────────────────────────────────────────
SEMANTIC_SCHOLAR_API_KEY = os.getenv("SEMANTIC_SCHOLAR_API_KEY", "")

# ─── Kafka ───────────────────────────────────────────────
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_TOPIC_RAW         = "raw_papers"
KAFKA_TOPIC_PROCESSED   = "processed_papers"

# ─── Spark ───────────────────────────────────────────────
SPARK_APP_NAME    = "ScientificGraphPipeline"
SPARK_MASTER      = "local[*]"

# ─── Collecte ────────────────────────────────────────────
ARXIV_MAX_RESULTS        = 500
ARXIV_SEARCH_QUERIES     = [
    "machine learning",
    "deep learning",
    "graph neural networks",
    "natural language processing",
    "big data",
]
SEMANTIC_SCHOLAR_DELAY   = 1.5   # secondes entre requêtes (rate limit)
MAX_CITATIONS_PER_PAPER  = 50

# ─── Chemins ─────────────────────────────────────────────
DATA_RAW_PATH       = "data/raw"
DATA_PROCESSED_PATH = "data/processed"
LOG_PATH            = "logs"