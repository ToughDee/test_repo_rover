import chromadb
from app.core.settings import settings

try:
    client = chromadb.PersistentClient(path=settings.chroma_dir)
    col = client.get_collection('reporover_test_repo_rover')
    print("COUNT:", col.count())
    print("DOCS:", len(col.get()['documents']))
except Exception as e:
    print("ERROR:", e)
