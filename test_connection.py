from neo4j import GraphDatabase
from dotenv import load_dotenv
import os

load_dotenv()

uri      = os.getenv("NEO4J_URI")
user     = os.getenv("NEO4J_USER")
password = os.getenv("NEO4J_PASSWORD")

print(f"URI      : {uri}")
print(f"User     : {user}")
print(f"Password : {password[:6]}...")

try:
    driver = GraphDatabase.driver(uri, auth=(user, password))
    driver.verify_connectivity()
    print("Connexion Neo4j reussie !")
    driver.close()
except Exception as e:
    print(f"Erreur : {e}")