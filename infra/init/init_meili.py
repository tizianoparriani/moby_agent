import os, time, requests

url = os.getenv("MEILISEARCH_URL", "[meilisearch](http://meilisearch:7700)")
master_key = os.getenv("MEILISEARCH_MASTER_KEY", "master_key_dev")
index = os.getenv("MEILISEARCH_INDEX", "documents")

headers = {"Authorization": f"Bearer {master_key}"}

if __name__ == "__main__":
    for _ in range(30):
        try:
            r = requests.get(f"{url}/health")
            if r.ok: break
        except Exception:
            time.sleep(2)
    # create index if missing
    r = requests.get(f"{url}/indexes/{index}", headers=headers)
    if r.status_code == 200:
        print(f"Index {index} already exists")
    else:
        r = requests.post(f"{url}/indexes", headers=headers, json={"uid": index, "primaryKey": "id"})
        r.raise_for_status()
        print(f"Created index {index}")
