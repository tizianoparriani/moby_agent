import os, requests, streamlit as st

API_URL = os.getenv("API_URL", "http://localhost:8000")
API_SECRET = os.getenv("API_SECRET", "dev_secret_token")

st.set_page_config(page_title="Moby Prince RAG — Dev", layout="wide")

st.title("Moby Prince — Dev Console")

tab1, tab2, tab3, tab4 = st.tabs(["Status", "Chat", "Ricerca", "Storage"])

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
    st.subheader("Chat con citazioni")
    q = st.text_input("Domanda", key="chat_q")
    if st.button("Invia", key="chat_send"):
        if not q.strip():
            st.warning("Inserisci una domanda.")
        else:
            try:
                with st.spinner("Recupero le fonti e interrogo Claude… (può richiedere ~30s)"):
                    r = requests.post(
                        f"{API_URL}/chat",
                        headers={"Authorization": f"Bearer {API_SECRET}"},
                        json={"query": q},
                        timeout=180,
                    )
                r.raise_for_status()
                res = r.json()
                st.markdown(res.get("answer", "_(nessuna risposta)_"))
                citations = res.get("citations", [])
                if citations:
                    st.divider()
                    st.caption("Fonti citate")
                    for c in citations:
                        pages = (
                            f"p. {c['page_start']}"
                            if c.get("page_start") == c.get("page_end")
                            else f"p. {c.get('page_start')}-{c.get('page_end')}"
                        )
                        st.markdown(f"- **{c.get('title')}** ({c.get('date') or 'n/d'}), {pages}")
            except Exception as e:
                st.error(f"Errore chat: {e}")

with tab3:
    st.subheader("Ricerca ibrida (vettoriale + BM25)")
    sq = st.text_input("Query", key="search_q")
    if st.button("Cerca", key="search_send"):
        if not sq.strip():
            st.warning("Inserisci una query.")
        else:
            try:
                with st.spinner("Ricerca in corso…"):
                    r = requests.get(f"{API_URL}/search", params={"q": sq}, timeout=60)
                r.raise_for_status()
                results = r.json().get("results", [])
                st.caption(f"{len(results)} risultati")
                for res in results:
                    pages = (
                        f"p. {res['page_start']}"
                        if res.get("page_start") == res.get("page_end")
                        else f"p. {res.get('page_start')}-{res.get('page_end')}"
                    )
                    with st.expander(
                        f"{res.get('title')} — {pages}  (score {res.get('score')})"
                    ):
                        st.write(res.get("text", ""))
            except Exception as e:
                st.error(f"Errore ricerca: {e}")

with tab4:
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
