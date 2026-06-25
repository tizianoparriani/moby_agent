import os

import requests
import streamlit as st

API_URL = os.getenv("API_URL", "http://localhost:8000")

st.set_page_config(page_title="Archivio Intelligente — Caso Moby Prince", layout="wide")


# ── helpers ───────────────────────────────────────────────────────────────────

def _headers() -> dict:
    token = st.session_state.get("token", "")
    return {"Authorization": f"Bearer {token}"} if token else {}


def _handle(r: requests.Response) -> requests.Response | None:
    """Return the response, or handle 401 by logging out."""
    if r.status_code == 401:
        for k in ("token", "username", "is_admin"):
            st.session_state.pop(k, None)
        st.error("Sessione scaduta, effettua nuovamente il login.")
        st.rerun()
    return r


def _format_pages(item: dict) -> str:
    ps, pe = item.get("page_start"), item.get("page_end")
    return f"p. {ps}" if ps == pe else f"p. {ps}-{pe}"


# ── auth screen ───────────────────────────────────────────────────────────────

def show_auth():
    st.title("Archivio Intelligente — Caso Moby Prince")
    st.markdown(
        "Agente AI per la consultazione dell'archivio documentale del caso Moby Prince. "
        "Poni domande in linguaggio naturale e ricevi risposte citate direttamente dalle fonti: "
        "atti giudiziari, perizie, relazioni parlamentari e testimonianze."
    )
    st.info("Accedi o registrati per iniziare a interrogare l'archivio.", icon="🔐")
    st.caption("Per assistenza o per richiedere un account scrivere a moby-agent-info@libero.it")
    st.divider()
    tab_login, tab_register = st.tabs(["Accedi", "Registrati"])

    with tab_login:
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Accedi")
        if submitted:
            if not username or not password:
                st.error("Inserisci username e password.")
            else:
                try:
                    r = requests.post(
                        f"{API_URL}/auth/login",
                        json={"username": username, "password": password},
                        timeout=5,
                    )
                    if r.ok:
                        d = r.json()
                        st.session_state.token = d["token"]
                        st.session_state.username = d["username"]
                        st.session_state.is_admin = d["is_admin"]
                        st.session_state.is_superuser = d.get("is_superuser", False)
                        st.rerun()
                    else:
                        st.error(r.json().get("detail", "Errore di login"))
                except Exception as e:
                    st.error(f"Errore di connessione: {e}")

    with tab_register:
        with st.form("register_form"):
            new_user = st.text_input("Username (min 3 caratteri)")
            new_pass = st.text_input("Password (min 6 caratteri)", type="password")
            invite_code = st.text_input("Codice invito")
            submitted_r = st.form_submit_button("Crea account")
        if submitted_r:
            if not new_user or not new_pass or not invite_code:
                st.error("Inserisci username, password e codice invito.")
            else:
                try:
                    r = requests.post(
                        f"{API_URL}/auth/register",
                        json={"username": new_user, "password": new_pass, "invite_code": invite_code},
                        timeout=5,
                    )
                    if r.ok:
                        d = r.json()
                        st.session_state.token = d["token"]
                        st.session_state.username = d["username"]
                        st.session_state.is_admin = d["is_admin"]
                        st.session_state.is_superuser = d.get("is_superuser", False)
                        st.rerun()
                    else:
                        st.error(r.json().get("detail", "Errore di registrazione"))
                except Exception as e:
                    st.error(f"Errore di connessione: {e}")


# ── main app ──────────────────────────────────────────────────────────────────

def _donation_banner(donation_url: str, total_cost_usd: float, kofi_url: str = "") -> None:
    """Show cost + donation message. Call only when donation_url is non-empty."""
    cost_str = f"${total_cost_usd:.4f}" if total_cost_usd >= 0.0001 else "< $0.0001"
    links = f"[👉 Dona su PayPal]({donation_url})"
    if kofi_url:
        links += f"   |   [☕ Dona su Ko-fi]({kofi_url})"
    st.info(
        f"💸 Le tue query sono costate finora **{cost_str}** in chiamate AI.\n\n"
        "Questo progetto vive sulle donazioni: le query che fai qualcuno le sta pagando. "
        "Se non fai donazioni vuol dire che qualcun altro sta pagando per te.\n\n"
        + links,
        icon=None,
    )


def show_app():
    # header row
    col_title, col_user, col_quota, col_logout = st.columns([4, 2, 2, 1])
    col_title.title("Archivio Intelligente — Caso Moby Prince")
    col_title.caption(
        "Agente AI per la consultazione dell'archivio documentale del caso Moby Prince. "
        "Poni domande in linguaggio naturale e ricevi risposte citate direttamente dalle fonti: "
        "atti giudiziari, perizie, relazioni parlamentari e testimonianze."
    )
    col_user.markdown(f"**{st.session_state.get('username', '')}**")

    quota_data: dict = {}
    try:
        r = requests.get(f"{API_URL}/me/quota", headers=_headers(), timeout=3)
        if r.ok:
            quota_data = r.json()
            col_quota.caption(f"Query oggi: {quota_data['used']}/{quota_data['limit']}")
    except Exception:
        pass

    if col_logout.button("Esci"):
        for k in ("token", "username", "is_admin"):
            st.session_state.pop(k, None)
        st.rerun()

    donation_url = quota_data.get("donation_url", "")
    kofi_url = quota_data.get("kofi_url", "")
    total_cost_usd = quota_data.get("total_cost_usd", 0.0)
    if donation_url:
        _donation_banner(donation_url, total_cost_usd, kofi_url)

    # regular users: Chat, Ricerca, Storico
    # admins: + Status, Storage, Admin
    is_admin = st.session_state.get("is_admin", False)
    tab_names = ["Chat", "Ricerca", "Storico"]
    if is_admin:
        tab_names += ["Status", "Storage", "Admin"]
    tab_map = {name: tab for name, tab in zip(tab_names, st.tabs(tab_names))}

    # ── Chat ──────────────────────────────────────────────────────────────────
    with tab_map["Chat"]:
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
                            headers=_headers(),
                            json={"query": q},
                            timeout=180,
                        )
                    r = _handle(r)
                    if r.status_code == 429:
                        st.warning(r.json().get("detail", "Limite giornaliero raggiunto."))
                    else:
                        r.raise_for_status()
                        res = r.json()
                        st.markdown(res.get("answer", "_(nessuna risposta)_"))
                        citations = res.get("citations", [])
                        if citations:
                            st.divider()
                            st.caption("Fonti citate")
                            for c in citations:
                                st.markdown(f"- **{c.get('title')}** ({c.get('date') or 'n/d'}), {_format_pages(c)}")
                        qc = res.get("query_cost_usd")
                        if qc is not None:
                            cost_str = f"${qc:.4f}" if qc >= 0.0001 else "< $0.0001"
                            st.caption(f"Costo di questa query: {cost_str}")
                except Exception as e:
                    st.error(f"Errore chat: {e}")

    # ── Ricerca ───────────────────────────────────────────────────────────────
    with tab_map["Ricerca"]:
        st.subheader("Ricerca ibrida (vettoriale + BM25)")
        sq = st.text_input("Query", key="search_q")
        if st.button("Cerca", key="search_send"):
            if not sq.strip():
                st.warning("Inserisci una query.")
            else:
                try:
                    with st.spinner("Ricerca in corso…"):
                        r = requests.get(
                            f"{API_URL}/search",
                            headers=_headers(),
                            params={"q": sq},
                            timeout=60,
                        )
                    r = _handle(r)
                    if r.status_code == 429:
                        st.warning(r.json().get("detail", "Limite giornaliero raggiunto."))
                    else:
                        r.raise_for_status()
                        results = r.json().get("results", [])
                        st.caption(f"{len(results)} risultati")
                        for res in results:
                            with st.expander(f"{res.get('title')} — {_format_pages(res)}  (score {res.get('score')})"):
                                st.write(res.get("text", ""))
                except Exception as e:
                    st.error(f"Errore ricerca: {e}")

    # ── Storico ───────────────────────────────────────────────────────────────
    with tab_map["Storico"]:
        st.subheader("Storico delle query")
        try:
            r = requests.get(f"{API_URL}/me/history", headers=_headers(), timeout=5)
            r = _handle(r)
            r.raise_for_status()
            history = r.json().get("history", [])
            if not history:
                st.info("Nessuna query ancora.")
            for item in history:
                ts = item.get("created_at", "")[:16].replace("T", " ")
                if item["endpoint"] == "chat":
                    with st.expander(f"💬 {ts} — {item['query'][:80]}"):
                        st.markdown(item.get("answer") or "_(nessuna risposta)_")
                        citations = item.get("citations", [])
                        if citations:
                            st.caption("Fonti:")
                            for c in citations:
                                st.markdown(f"- **{c.get('title')}** ({c.get('date') or 'n/d'}), {_format_pages(c)}")
                else:
                    st.caption(f"🔍 {ts} — {item['query'][:80]}")
        except Exception as e:
            st.error(f"Errore storico: {e}")

    # ── Status (admin only) ───────────────────────────────────────────────────
    if is_admin:
        with tab_map["Status"]:
            st.subheader("Health")
            try:
                r = requests.get(f"{API_URL}/health", timeout=3)
                data = r.json()
                st.json(data)
                ok = all([data.get("qdrant"), data.get("meilisearch"), data.get("minio")])
                st.success("Tutti i servizi rispondono") if ok else st.warning("Alcuni servizi non rispondono")
            except Exception as e:
                st.error(f"Errore health: {e}")

        # ── Storage (admin only) ──────────────────────────────────────────────
        with tab_map["Storage"]:
            st.subheader("Upload test su MinIO")
            if st.button("Carica file di prova"):
                try:
                    r = requests.post(
                        f"{API_URL}/ingest/test-upload",
                        headers=_headers(),
                        timeout=10,
                    )
                    r = _handle(r)
                    r.raise_for_status()
                    res = r.json()
                    st.success("Upload OK")
                    st.write("Presigned URL (1h):")
                    st.code(res.get("presigned_url", ""))
                except Exception as e:
                    st.error(f"Errore storage: {e}")

        # ── Admin ─────────────────────────────────────────────────────────────
        with tab_map["Admin"]:
            st.subheader("Utilizzo complessivo")
            try:
                r = requests.get(f"{API_URL}/admin/usage", headers=_headers(), timeout=5)
                r = _handle(r)
                r.raise_for_status()
                data = r.json()
                st.caption(f"Limite giornaliero: **{data.get('daily_limit')} query/utente/giorno**")
                users = data.get("users", [])
                if users:
                    import pandas as pd
                    df = pd.DataFrame(users, columns=["username", "is_admin", "is_superuser", "total_queries", "today_queries", "total_cost_usd"])
                    df.columns = ["Username", "Admin", "Super", "Query totali", "Query oggi", "Costo tot. ($)"]
                    df["Admin"] = df["Admin"].map({0: "", 1: "✓"})
                    df["Super"] = df["Super"].map({0: "", 1: "⚡"})
                    st.dataframe(df, use_container_width=True, hide_index=True)

                    st.divider()
                    st.subheader("Promuovi / Rimuovi Super User")
                    usernames = [u["username"] for u in users if not u["is_admin"]]
                    if usernames:
                        col_sel, col_btn_add, col_btn_rem = st.columns([3, 1, 1])
                        target = col_sel.selectbox("Utente", usernames, key="superuser_target")
                        if col_btn_add.button("⚡ Promuovi", key="su_promote"):
                            try:
                                r2 = requests.post(
                                    f"{API_URL}/admin/users/{target}/superuser",
                                    headers=_headers(),
                                    json={"value": True},
                                    timeout=5,
                                )
                                r2 = _handle(r2)
                                r2.raise_for_status()
                                st.success(f"{target} promosso a Super User.")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Errore: {e}")
                        if col_btn_rem.button("Rimuovi", key="su_demote"):
                            try:
                                r2 = requests.post(
                                    f"{API_URL}/admin/users/{target}/superuser",
                                    headers=_headers(),
                                    json={"value": False},
                                    timeout=5,
                                )
                                r2 = _handle(r2)
                                r2.raise_for_status()
                                st.success(f"Super User rimosso da {target}.")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Errore: {e}")
                    else:
                        st.info("Nessun utente non-admin disponibile.")
                else:
                    st.info("Nessun utente registrato.")
            except Exception as e:
                st.error(f"Errore admin: {e}")

            st.divider()
            st.subheader("Codici invito")

            col_gen, _ = st.columns([2, 5])
            if col_gen.button("Genera nuovo codice"):
                try:
                    r = requests.post(f"{API_URL}/admin/invites", headers=_headers(), timeout=5)
                    r = _handle(r)
                    r.raise_for_status()
                    new_code = r.json().get("code", "")
                    st.success(f"Codice generato:")
                    st.code(new_code)
                except Exception as e:
                    st.error(f"Errore generazione codice: {e}")

            try:
                r = requests.get(f"{API_URL}/admin/invites", headers=_headers(), timeout=5)
                r = _handle(r)
                r.raise_for_status()
                invites = r.json().get("invites", [])
                if invites:
                    import pandas as pd
                    df_inv = pd.DataFrame(invites, columns=["code", "created_at", "used_at", "used_by_username"])
                    df_inv.columns = ["Codice", "Creato", "Usato il", "Usato da"]
                    df_inv["Creato"] = df_inv["Creato"].str[:16].str.replace("T", " ")
                    df_inv["Usato il"] = df_inv["Usato il"].str[:16].str.replace("T", " ").fillna("—")
                    df_inv["Usato da"] = df_inv["Usato da"].fillna("—")
                    st.dataframe(df_inv, use_container_width=True, hide_index=True)
                else:
                    st.info("Nessun codice generato ancora.")
            except Exception as e:
                st.error(f"Errore lista inviti: {e}")


# ── entry point ───────────────────────────────────────────────────────────────

if st.session_state.get("token"):
    show_app()
else:
    show_auth()
