import os
import json
import hashlib
import hmac
import streamlit as st
import streamlit.components.v1 as components


# ────────────────────────── helpers: usuarios ──────────────────────────

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


# ────────────────────────── helpers: firma ──────────────────────────

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


def _sign(u: str) -> str:
    return hmac.new(_cookie_secret().encode("utf-8"), u.encode("utf-8"), hashlib.sha256).hexdigest()


# ────────────────────────── helpers: cookies ──────────────────────────

_COOKIE_NAME = "stauth"
_MAX_AGE = 60 * 60 * 24 * 7  # 7 días


def _read_cookie():
    """Lee la cookie del request HTTP via st.context.cookies (síncrono)."""
    try:
        return st.context.cookies.get(_COOKIE_NAME)
    except Exception:
        return None


def _inject_cookie_js(action: str, value: str = ""):
    """Inyecta JS invisible para escribir o borrar una cookie.

    Se renderiza como un iframe de 0px. El JS se ejecuta en el navegador
    cuando Streamlit envía el output al cliente (sin necesidad de reload).
    """
    if action == "set":
        js_line = (
            f'document.cookie="{_COOKIE_NAME}={value};'
            f' path=/; max-age={_MAX_AGE}; SameSite=Lax";'
        )
    else:
        js_line = (
            f'document.cookie="{_COOKIE_NAME}=;'
            f' path=/; max-age=0; SameSite=Lax";'
        )
    components.html(f"<script>{js_line}</script>", height=0)


# ────────────────────────── require_login ──────────────────────────

def require_login(title: str = "Acceso") -> str:
    users = _credentials()

    if not users:
        st.error(
            "No hay usuarios configurados. Define AUTH_USERS en .env "
            "(JSON o 'user:pass') o usa st.secrets['auth']['users']."
        )
        st.stop()

    # ── Ejecutar acción de cookie pendiente (diferida del run anterior) ──
    pending = st.session_state.pop("_auth_cookie_pending", None)
    skip_hydration = False
    if pending is not None:
        _inject_cookie_js(pending["action"], pending.get("value", ""))
        if pending["action"] == "delete":
            skip_hydration = True

    # ── Hidratar sesión desde cookie (lectura síncrona) ──
    if "auth_user" not in st.session_state and not skip_hydration:
        token = _read_cookie()
        if isinstance(token, str) and ":" in token:
            cu, cs = token.split(":", 1)
            if _sign(cu) == cs:
                st.session_state["auth_user"] = cu

    # ── Sesión activa ──
    if "auth_user" in st.session_state:
        with st.sidebar:
            st.caption(f"Conectado como: {st.session_state['auth_user']}")
            if st.button("Cerrar sesión"):
                del st.session_state["auth_user"]
                st.session_state["_auth_cookie_pending"] = {"action": "delete"}
                st.rerun()
        return st.session_state["auth_user"]

    # ── Formulario de login ──
    st.title(title)
    st.subheader("Inicio de sesión")
    with st.form("login_form", clear_on_submit=False):
        username = st.text_input("Usuario")
        password = st.text_input("Contraseña", type="password")
        submitted = st.form_submit_button("Ingresar")

        if submitted:
            if username in users and _match_password(users[username], password):
                st.session_state["auth_user"] = username
                token = f"{username}:{_sign(username)}"
                st.session_state["_auth_cookie_pending"] = {
                    "action": "set", "value": token,
                }
                st.rerun()
            else:
                st.error("Credenciales inválidas")

    st.stop()
    return ""
