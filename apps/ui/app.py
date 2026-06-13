import os, requests, streamlit as st

API_URL = os.getenv("API_URL", "[localhost](http://localhost:8000)")
API_SECRET = os.getenv("API_SECRET", "dev_secret_token")

st.set_page_config(page_title="Moby Prince RAG — Dev", layout="wide")

st.title("Moby Prince — Dev Console")

tab1, tab2, tab3 = st.tabs(["Status", "Chat (mock)", "Storage"])

with tab1:
    st.subheader("Health")
    try:
        r = requests.get(f"{API_URL}/health", timeout=3)
        data = r.json()
        st.json(data)
        ok = all([data.get("qdrant"), data.get("meilisearch"), data.get("minio")])
        st.success("Tutti i servizi rispondono") if ok else st.warning("Alcuni servizi non rispondono")
    except Exception as e:
        st.error(f"Errore health: {e}")

with tab2:
    st.subheader("Chat di prova")
    q = st.text_input("Domanda")
    if st.button("Invia"):
        try:
            r = requests.post(f"{API_URL}/chat",
                              headers={"Authorization": f"Bearer {API_SECRET}"},
                              json={"query": q}, timeout=10)
            st.json(r.json())
        except Exception as e:
            st.error(f"Errore chat: {e}")

with tab3:
    st.subheader("Upload test su MinIO")
    if st.button("Carica file di prova"):
        try:
            r = requests.post(f"{API_URL}/ingest/test-upload",
                              headers={"Authorization": f"Bearer {API_SECRET}"},
                              timeout=10)
            res = r.json()
            st.success("Upload OK")
            st.write("Presigned URL (1h):")
            st.code(res.get("presigned_url", ""))
        except Exception as e:
            st.error(f"Errore upload: {e}")
