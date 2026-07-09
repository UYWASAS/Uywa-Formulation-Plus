# ============================================================
# UYWA FORMULATION APP - APP PRINCIPAL
# (Login + Sidebar + Toggle UI compacta + Navegación por tabs)
# ============================================================

import os
import streamlit as st


# ============================================================
# CONFIGURACIÓN DE PÁGINA
# ============================================================

st.set_page_config(
    page_title="Formulador UYWA Premium",
    layout="wide"
)


# ============================================================
# AUTH IMPORT ROBUSTO
# ============================================================

try:
    from src.core.auth.service import USERS_DB, is_user_active
except Exception:
    from src.core.auth.policies import USERS_DB, is_user_active


# ============================================================
# CSS BASE + COMPACTO
# ============================================================

BASE_CSS = """
<style>
html, body, .stApp, .block-container {
    background: linear-gradient(120deg, #ffffff 0%, #eef4fc 100%) !important;
}

.block-container {
    padding: 2rem 3rem;
}

/* Sidebar */
section[data-testid="stSidebar"] {
    background-color: #2C3E50 !important;
    color: #fff !important;
}
section[data-testid="stSidebar"] * {
    color: #fff !important;
}
section[data-testid="stSidebar"],
section[data-testid="stSidebar"][aria-expanded="true"] {
    width: 18.5rem !important;
    min-width: 18.5rem !important;
    max-width: 18.5rem !important;
}

/* Botones */
.stButton > button {
    background-color: #2176ff;
    color: #fff !important;
    border-radius: 8px;
    border: none;
    padding: 0.5rem 1rem !important;
    font-weight: 600;
}
.stButton > button:hover {
    background-color: #1254d1;
    color: #fff !important;
    box-shadow: 0px 4px 10px rgba(0, 0, 0, 0.18) !important;
}

/* Inputs */
.stNumberInput, .stSelectbox, .stTextInput {
    background-color: #eef4fc !important;
    border-radius: 4px;
    border: 1px solid #d4e4fc !important;
    padding: 0.35rem;
}

/* Footer streamlit */
footer { visibility: hidden !important; }
</style>
"""

COMPACT_CSS = """
<style>
html, body, .stApp {
    font-size: 14px !important;
}
.block-container {
    padding: 1.15rem 2rem !important;
    max-width: 97% !important;
}
h1 { font-size: 1.72rem !important; }
h2 { font-size: 1.38rem !important; }
h3 { font-size: 1.14rem !important; }

p, label, .stMarkdown, .stCaption, .stText {
    font-size: 0.9rem !important;
}

.stButton > button {
    padding: 0.38rem 0.72rem !important;
    font-size: 0.86rem !important;
}

.stTabs [data-baseweb="tab-list"] button {
    padding-top: 0.32rem !important;
    padding-bottom: 0.32rem !important;
}

[data-testid="stDataFrame"] div, [data-testid="stTable"] div {
    font-size: 12px !important;
}
</style>
"""


def apply_ui_css():
    st.markdown(BASE_CSS, unsafe_allow_html=True)
    if st.session_state.get("ui_compact_mode", False):
        st.markdown(COMPACT_CSS, unsafe_allow_html=True)


# ============================================================
# LOGIN
# ============================================================

def login():
    st.title("Iniciar sesión")

    username = st.text_input("Usuario", key="usuario_login")
    password = st.text_input("Contraseña", type="password", key="password_login")

    if st.button("Entrar", key="entrar_login"):
        username_clean = username.strip().lower()
        user = USERS_DB.get(username_clean)

        if user and user.get("password") == password:
            is_active, message = is_user_active(user)
            if not is_active:
                st.error(message)
                st.stop()

            st.session_state["logged_in"] = True
            st.session_state["usuario"] = username_clean
            st.session_state["user"] = user
            st.success(f"Bienvenido, {user.get('name', username_clean)}!")
            st.rerun()
        else:
            st.error("Usuario o contraseña incorrectos.")

    if not st.session_state.get("logged_in", False):
        st.stop()


# ============================================================
# SIDEBAR
# ============================================================

def render_sidebar():
    user = st.session_state.get("user", None)

    with st.sidebar:
        if "ui_compact_mode" not in st.session_state:
            st.session_state["ui_compact_mode"] = True

        st.toggle(
            "UI compacta",
            key="ui_compact_mode",
            help="Reduce tamaño de letras y espacios para mostrar más información."
        )

        logo_path = "assets/logo.png"
        if os.path.exists(logo_path):
            st.image(logo_path, use_container_width=True)
        else:
            st.markdown("### 🐔 UYWA Nutrition")
            st.caption("Logo no encontrado en assets/logo.png")

        st.markdown(
            """
            <div style="text-align:center;margin-bottom:20px;">
                <h1 style="font-family:Montserrat,sans-serif;margin:0;color:#fff;">UYWA Nutrition</h1>
                <p style="font-size:14px;margin:0;color:#fff;">Nutrición de Precisión Basada en Evidencia</p>
                <br>
                <hr style="border:1px solid #fff;">
                <p style="font-size:13px;color:#fff;margin:0;">📧 uywasas@gmail.com</p>
                <p style="font-size:11px;color:#fff;margin:0;">Derechos reservados © 2026</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if user:
            st.success(f"Acceso {user.get('plan', 'Sin plan')} activado")
            if user.get("expires"):
                st.caption(f"Válido hasta: {user['expires']}")
        else:
            st.warning("Por favor, inicia sesión.")


# ============================================================
# MAIN
# ============================================================

def main():
    if not st.session_state.get("logged_in", False):
        login()
        st.stop()

    render_sidebar()
    apply_ui_css()

    st.markdown(
        f"<div style='text-align:right'>👤 Usuario: <b>{st.session_state.get('usuario', '')}</b></div>",
        unsafe_allow_html=True
    )

    # Pestañas principales
    from src.ui.pages.formulators.aves import render as render_aves
    from src.ui.pages.formulators.cerdos import render as render_cerdos
    from src.ui.pages.formulators.rumiantes import render as render_rumiantes
    from src.ui.pages.dashboard import render as render_dashboard

    tabs = st.tabs(["Dashboard", "Aves", "Cerdos", "Rumiantes"])

    with tabs[0]:
        render_dashboard()
    with tabs[1]:
        render_aves()
    with tabs[2]:
        render_cerdos()
    with tabs[3]:
        render_rumiantes()


if __name__ == "__main__":
    main()
