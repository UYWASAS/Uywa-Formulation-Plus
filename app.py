# ============================================================
# UYWA FORMULATION APP - REFACTOR PROGRESIVO
# APP PRINCIPAL (con modo compacto + logo robusto en sidebar)
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
# CSS BASE + MODO COMPACTO
# ============================================================

BASE_CSS = """
<style>
html, body, .stApp, .block-container {
    background: linear-gradient(120deg, #ffffff 0%, #eef4fc 100%) !important;
}
.block-container {
    padding: 2rem 4rem;
}

section[data-testid="stSidebar"] {
    background-color: #2C3E50 !important;
    color: #fff !important;
}
section[data-testid="stSidebar"] * {
    color: #fff !important;
}

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

.stNumberInput, .stSelectbox, .stTextInput {
    background-color: #eef4fc !important;
    border-radius: 4px;
    border: 1px solid #d4e4fc !important;
    padding: 0.4rem;
}

footer {
    visibility: hidden !important;
}

section[data-testid="stSidebar"],
section[data-testid="stSidebar"][aria-expanded="true"] {
    width: 18.5rem !important;
    min-width: 18.5rem !important;
    max-width: 18.5rem !important;
}

.uywa-card {
    background: #ffffff;
    border-radius: 12px;
    padding: 18px 20px;
    margin: 12px 0;
    border: 1px solid #d9e6f7;
    box-shadow: 0 3px 10px rgba(44, 62, 80, 0.08);
}
.uywa-card-info { border-left: 6px solid #2176ff; }
.uywa-card-success { border-left: 6px solid #2ca25f; }
.uywa-card-warning { border-left: 6px solid #f0ad4e; background: #fffaf0; }
.uywa-card-danger { border-left: 6px solid #d9534f; background: #fff3f3; }

.uywa-card-title {
    margin: 0 0 6px 0;
    color: #2C3E50;
    font-size: 18px;
    font-weight: 700;
}
.uywa-card-body {
    margin: 0;
    color: #333333;
    font-size: 14px;
    line-height: 1.45;
}

.uywa-metric-card {
    background: #ffffff;
    border-radius: 12px;
    padding: 16px;
    border: 1px solid #d9e6f7;
    box-shadow: 0 3px 10px rgba(44, 62, 80, 0.07);
    text-align: center;
    min-height: 105px;
}
.uywa-metric-label {
    color: #5f6f82;
    font-size: 13px;
    margin-bottom: 6px;
}
.uywa-metric-value {
    color: #2C3E50;
    font-size: 24px;
    font-weight: 800;
    margin-bottom: 4px;
}
.uywa-metric-caption {
    color: #7a8694;
    font-size: 12px;
}

.uywa-section-title {
    color: #2C3E50;
    font-weight: 800;
    margin-top: 1.4rem;
    margin-bottom: 0.2rem;
}
.uywa-section-subtitle {
    color: #627386;
    font-size: 14px;
    margin-bottom: 0.8rem;
}

.uywa-badge {
    display: inline-block;
    padding: 4px 9px;
    border-radius: 999px;
    font-size: 12px;
    font-weight: 700;
    margin-right: 6px;
}
.uywa-badge-success { background: #e5f6ee; color: #1f7a4d; }
.uywa-badge-warning { background: #fff3cd; color: #8a6d1d; }
.uywa-badge-danger { background: #f8d7da; color: #842029; }
.uywa-badge-info { background: #e8f1ff; color: #1254d1; }
</style>
"""

COMPACT_CSS = """
<style>
html, body, .stApp {
    font-size: 14px !important;
}
.block-container {
    padding: 1.2rem 2rem !important;
    max-width: 96% !important;
}
h1 { font-size: 1.75rem !important; }
h2 { font-size: 1.4rem !important; }
h3, .uywa-section-title { font-size: 1.15rem !important; }
p, label, .stMarkdown, .stCaption, .stText, .stAlert {
    font-size: 0.9rem !important;
}
.uywa-card { padding: 12px 14px !important; margin: 8px 0 !important; }
.uywa-card-title { font-size: 16px !important; }
.uywa-card-body { font-size: 13px !important; }

.uywa-metric-card {
    padding: 10px !important;
    min-height: 82px !important;
}
.uywa-metric-label { font-size: 11px !important; margin-bottom: 2px !important; }
.uywa-metric-value { font-size: 19px !important; margin-bottom: 2px !important; }
.uywa-metric-caption { font-size: 10px !important; }

[data-testid="stDataFrame"] div, [data-testid="stTable"] div {
    font-size: 12px !important;
}
.stDataFrame, .stTable {
    transform: scale(0.98);
    transform-origin: top left;
}

.stTabs [data-baseweb="tab-list"] button {
    padding-top: 0.35rem !important;
    padding-bottom: 0.35rem !important;
}
.stButton > button {
    padding: 0.38rem 0.7rem !important;
    font-size: 0.86rem !important;
}
</style>
"""


def apply_ui_css():
    st.markdown(BASE_CSS, unsafe_allow_html=True)
    if st.session_state.get("ui_compact_mode", False):
        st.markdown(COMPACT_CSS, unsafe_allow_html=True)


# ============================================================
# AUTH (manteniendo tu estructura actual)
# ============================================================

from src.core.auth.service import USERS_DB, is_user_active


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
# SIDEBAR (logo robusto + toggle UI compacta)
# ============================================================

def render_sidebar():
    user = st.session_state.get("user", None)

    with st.sidebar:
        # Toggle UI compacta
        if "ui_compact_mode" not in st.session_state:
            st.session_state["ui_compact_mode"] = True

        st.toggle(
            "UI compacta",
            key="ui_compact_mode",
            help="Reduce tamaño de letra y espacios para visualizar más contenido en pantalla."
        )

        # Logo robusto
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
            plan = user.get("plan", "Sin plan")
            expires = user.get("expires", None)

            st.success(f"Acceso {plan} activado")
            if expires:
                st.caption(f"Válido hasta: {expires}")
        else:
            st.warning("Por favor, inicia sesión.")


# ============================================================
# APP MAIN
# ============================================================

def main():
    # login gate
    if not st.session_state.get("logged_in", False):
        login()
        st.stop()

    render_sidebar()
    apply_ui_css()

    st.markdown(
        f"<div style='text-align:right'>👤 Usuario: <b>{st.session_state.get('usuario','')}</b></div>",
        unsafe_allow_html=True
    )

    # Router principal (ajústalo a tu estructura real de navegación)
    # Aquí dejo Aves como página activa por defecto.
    from src.ui.pages.formulators.aves import render as render_formulator_aves
    render_formulator_aves()


if __name__ == "__main__":
    main()
