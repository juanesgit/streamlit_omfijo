import os
import json
import hashlib
import hmac
import time
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


def _overlay(msg: str = "Validando sesión…"):
    st.markdown(
        f"""
        <div style="position:fixed;inset:0;background:rgba(17,24,39,.55);backdrop-filter:saturate(180%) blur(2px);display:flex;align-items:center;justify-content:center;z-index:10000;">
          <div style="padding:16px 20px;border-radius:10px;background:#111827;color:#e5e7eb;font-size:18px;font-weight:600;border:1px solid rgba(255,255,255,.1)">{msg}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def require_login(title: str = "Acceso") -> str:
    users = _credentials()

    if not users:
        st.error(
            "No hay usuarios configurados. Define AUTH_USERS en .env (JSON o 'user:pass') o usa st.secrets['auth']['users']."
        )
        st.stop()

    cm = _cookie_manager()
    # Si venimos de un logout forzado, no hidrates desde cookie en este ciclo
    force_logout = st.session_state.get("_auth_force_logout", False)
    # Primer paso: da oportunidad a que el componente de cookies se monte
    # y luego vuelve a ejecutar para leer el valor real, evitando parpadeo de login.
    if cm is not None and not st.session_state.get("_auth_cookie_ready", False):
        cm.get("auth")  # Render del componente
        st.session_state["_auth_cookie_ready"] = True
        st.rerun()

    if cm is not None and not force_logout:
        token = cm.get("auth")
        if isinstance(token, str):
            if token.startswith("logout:"):
                # Cookie marcada como logout: tratar como no autenticado y evitar reruns extra
                st.session_state["_auth_cookie_checked"] = True
            elif ":" in token:
                cu, cs = token.split(":", 1)
                if cu in users and _sign(cu) == cs:
                    already = "auth_user" in st.session_state and st.session_state["auth_user"] == cu
                    st.session_state["auth_user"] = cu
                    if not already and not st.session_state.get("_auth_authed_rerun", False):
                        st.session_state["_auth_authed_rerun"] = True
                        _overlay("Validando sesión…")
                        st.rerun()
            elif not st.session_state.get("_auth_cookie_checked", False):
                st.session_state["_auth_cookie_checked"] = True
                st.rerun()

    # Sesión activa
    if "auth_user" in st.session_state and st.session_state["auth_user"] in users:
        st.session_state.pop("_auth_authed_rerun", None)
        # Mostrar overlay una sola vez incluso si ya había auth_user por sesión persistente
        if not st.session_state.get("_auth_overlay_once", False):
            st.session_state["_auth_overlay_once"] = True
            _overlay("Validando sesión…")
            st.rerun()
        with st.sidebar:
            st.caption(f"Conectado como: {st.session_state['auth_user']}")
            if st.button("Cerrar sesión"):
                del st.session_state["auth_user"]
                if cm is not None:
                    # Marcar explícitamente logout y borrar cookie para evitar rehidratación tras refresh
                    try:
                        cm.delete("auth")
                    except Exception:
                        pass
                    cm.set("auth", f"logout:{int(time.time())}", max_age=60 * 5)
                st.session_state.pop("_auth_cookie_ready", None)
                st.session_state.pop("_auth_cookie_checked", None)
                st.session_state.pop("_auth_grace_t0", None)
                st.session_state.pop("_auth_overlay_once", None)
                st.session_state["_auth_force_logout"] = True
                _overlay("Cerrando sesión…")
                st.stop()
        return st.session_state["auth_user"]

    # Hemos decidido no hidratar desde cookie (logout forzado) o no hay cookie válida.
    # Ya no estamos autenticados, quitar la bandera para futuros ciclos.
    if force_logout:
        st.session_state.pop("_auth_force_logout", None)

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
