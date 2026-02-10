import os
import json
import hashlib
import streamlit as st


def _load_users_from_secrets():
    try:
        secrets = st.secrets
        # Permitir dos formatos: auth.users como dict, o AUTH_USERS como string JSON
        if "auth" in secrets and "users" in secrets["auth"]:
            users = secrets["auth"]["users"]
            if isinstance(users, dict):
                return {str(k): str(v) for k, v in users.items()}
        if "AUTH_USERS" in secrets:
            raw = secrets["AUTH_USERS"]
            if isinstance(raw, str) and raw.strip():
                return json.loads(raw)
    except Exception:
        pass
    return {}


def _load_users_from_env():
    raw = os.getenv("AUTH_USERS", "").strip()
    if not raw:
        return {}
    try:
        return {str(k): str(v) for k, v in json.loads(raw).items()}
    except Exception:
        # Formato alternativo simple: "user:pass,user2:pass2"
        try:
            pairs = [p for p in raw.split(",") if p]
            users = {}
            for p in pairs:
                if ":" in p:
                    u, pw = p.split(":", 1)
                    users[u.strip()] = pw.strip()
            return users
        except Exception:
            return {}


def _match_password(stored: str, provided: str) -> bool:
    if stored.startswith("sha256:"):
        digest = hashlib.sha256(provided.encode("utf-8")).hexdigest()
        return digest == stored.split(":", 1)[1]
    return stored == provided


def _credentials() -> dict:
    users = _load_users_from_secrets()
    if not users:
        users = _load_users_from_env()
    return users or {}


def require_login(title: str = "Acceso") -> str:
    users = _credentials()

    if not users:
        st.error(
            "No hay usuarios configurados. Define AUTH_USERS en .env (JSON o 'user:pass') o usa st.secrets['auth']['users']."
        )
        st.stop()

    # Sesión activa
    if "auth_user" in st.session_state and st.session_state["auth_user"] in users:
        with st.sidebar:
            st.caption(f"Conectado como: {st.session_state['auth_user']}")
            if st.button("Cerrar sesión"):
                del st.session_state["auth_user"]
                st.rerun()
        return st.session_state["auth_user"]

    st.title(title)
    st.subheader("Inicio de sesión")
    with st.form("login_form", clear_on_submit=False):
        username = st.text_input("Usuario")
        password = st.text_input("Contraseña", type="password")
        submitted = st.form_submit_button("Ingresar")

        if submitted:
            if username in users and _match_password(users[username], password):
                st.session_state["auth_user"] = username
                st.rerun()
            else:
                st.error("Credenciales inválidas")

    st.stop()
    return ""  # Unreachable, satisface type checkers
