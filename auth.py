import os
import json
import hashlib
import hmac
import streamlit as st
try:
    import extra_streamlit_components as stx
except Exception:
    stx = None


def _load_users_from_secrets():
    try:
        possible_paths = [
            os.path.join(os.getcwd(), ".streamlit", "secrets.toml"),
            "/app/.streamlit/secrets.toml",
            os.path.expanduser("~/.streamlit/secrets.toml"),
        ]
        if not any(os.path.exists(p) for p in possible_paths):
            return {}

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


def _cookie_secret() -> str:
    try:
        possible_paths = [
            os.path.join(os.getcwd(), ".streamlit", "secrets.toml"),
            "/app/.streamlit/secrets.toml",
            os.path.expanduser("~/.streamlit/secrets.toml"),
        ]
        if any(os.path.exists(p) for p in possible_paths):
            secrets = st.secrets
            if "AUTH_COOKIE_KEY" in secrets:
                return str(secrets["AUTH_COOKIE_KEY"])
            if "auth" in secrets and "cookie_key" in secrets["auth"]:
                return str(secrets["auth"]["cookie_key"])
    except Exception:
        pass
    env_key = os.getenv("AUTH_COOKIE_KEY", "")
    if env_key:
        return env_key
    salt = os.getenv("AUTH_USERS", "")
    return hashlib.sha256(("SALT" + salt).encode("utf-8")).hexdigest()


def _cookie_manager():
    if stx is None:
        return None
    return stx.CookieManager(key="auth_cookies")


def _sign(u: str) -> str:
    return hmac.new(_cookie_secret().encode("utf-8"), u.encode("utf-8"), hashlib.sha256).hexdigest()


def require_login(title: str = "Acceso") -> str:
    users = _credentials()

    if not users:
        st.error(
            "No hay usuarios configurados. Define AUTH_USERS en .env (JSON o 'user:pass') o usa st.secrets['auth']['users']."
        )
        st.stop()

    cm = _cookie_manager()
    if cm is not None:
        token = cm.get("auth")
        if isinstance(token, str) and ":" in token:
            cu, cs = token.split(":", 1)
            if cu in users and _sign(cu) == cs:
                st.session_state["auth_user"] = cu

    # Sesión activa
    if "auth_user" in st.session_state and st.session_state["auth_user"] in users:
        with st.sidebar:
            st.caption(f"Conectado como: {st.session_state['auth_user']}")
            if st.button("Cerrar sesión"):
                del st.session_state["auth_user"]
                if cm is not None:
                    cm.delete("auth")
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
                if cm is not None:
                    new_token = f"{username}:{_sign(username)}"
                    current_token = cm.get("auth")
                    if current_token != new_token:
                        cm.set("auth", new_token, max_age=60 * 60 * 24 * 7)
                st.rerun()
            else:
                st.error("Credenciales inválidas")

    st.stop()
    return ""  # Unreachable, satisface type checkers
