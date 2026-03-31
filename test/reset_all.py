import sys
import shutil
from pathlib import Path

# Add project root to sys.path
root = Path(__file__).resolve().parents[1]
sys.path.append(str(root))

from app.core.settings import settings
from app.infrastructure.neo4j_client import Neo4jClient

def reset_directories():
    """Deletes the local .chroma and .work folders"""
    dirs_to_delete = [
        Path(settings.chroma_dir),
        Path(settings.work_dir)
    ]
    
    for d in dirs_to_delete:
        if d.exists() and d.is_dir():
            print(f"Removing directory: {d}")
            shutil.rmtree(d, ignore_errors=True)
        else:
            print(f"Directory not found (skipping): {d}")

def reset_neo4j():
    """Wipes all data from Neo4j Aura and re-initializes schema"""
    print(f"Connecting to Neo4j at {settings.neo4j_uri}...")
    client = Neo4jClient.from_settings()
    try:
        with client.driver.session() as s:
            print("Wiping all nodes and relationships...")
            s.run("MATCH (n) DETACH DELETE n")
        
        print("Re-initializing schema (constraints)...")
        client.init_schema()
        print("Neo4j database reset successfully.")
    except Exception as e:
        print(f"Error resetting Neo4j: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    print("--- FULL RESET INITIATED ---")
    reset_directories()
    reset_neo4j()
    print("--- RESET COMPLETE ---")
