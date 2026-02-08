from gtm_neo4j_loader import load_gtm_container

# Your connection details
NEO4J_URI = "neo4j://127.0.0.1:7687"  # or your Aura URI
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "Aa123Aa123"

load_gtm_container('output2.json', NEO4J_URI , NEO4J_USER , NEO4J_PASSWORD)