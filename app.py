import streamlit as st

from src.core.auth.service import USERS_DB, is_user_active
from src.core.auth.policies import has_feature

from src.ui.components.theme import apply_theme
from src.ui.components.navigation import render_sidebar_navigation

from src.ui.pages.dashboard import render as render_dashboard
from src.ui.pages.formulators.aves import render as render_formulator_aves
from src.ui.pages.formulators.cerdos import render as render_formulator_cerdos
from src.ui.pages.formulators.rumiantes import render as render_formulator_rumiantes


# ============================================================
# CONFIG APP
# ============================================================
st.set_page_config(page_title="Formulador UYWA Premium", layout="wide")

st.set_page_config(
    page_title="Formulador UYWA Premium",
    layout="wide",
)


# ============================================================
# AUTH
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


def logout():
    keys_to_clear = ["logged_in", "usuario", "user", "module"]
    for key in keys_to_clear:
        if key in st.session_state:
            del st.session_state[key]
    for key in ["logged_in", "usuario", "user", "module"]:
        st.session_state.pop(key, None)
    st.rerun()


# ============================================================
# BOOT
# ============================================================

apply_theme()

if not st.session_state.get("logged_in", False):
    login()
    st.stop()

user = st.session_state.get("user")
if user is None:
    st.error("No se encontró información del usuario en sesión.")
    logout()
    st.stop()

# Sidebar macro (paso 1)
module = render_sidebar_navigation(user)

# Header superior simple
top_col1, top_col2 = st.columns([6, 1])
with top_col1:
    st.markdown(
        f"<div style='text-align:right'>👤 Usuario: <b>{st.session_state.get('usuario','')}</b></div>",
        unsafe_allow_html=True,
    )
with top_col2:
    if st.button("Salir", key="btn_logout_top"):
        logout()


# ============================================================
# ROUTER MACRO
# ============================================================

if module == "formulador_aves":
    if not has_feature(user, "formulator_aves"):
        st.error("Tu plan no incluye Formulador Aves.")
    else:
        render_formulator_aves()

elif module == "formulador_cerdos":
    if not has_feature(user, "formulator_cerdos"):
        st.error("Tu plan no incluye Formulador Cerdos.")
    else:
        render_formulator_cerdos()

elif module == "formulador_rumiantes":
    if not has_feature(user, "formulator_rumiantes"):
        st.error("Tu plan no incluye Formulador Rumiantes.")
    else:
        render_formulator_rumiantes()

elif module == "tool_energia":
    if not has_feature(user, "tool_energy_predictor"):
        st.error("Tu plan no incluye Calculador/Predictor de Energía.")
    else:
        st.title("⚡ Calculador de Energía")
        st.caption("Módulo en construcción.")

elif module == "tool_materias_primas":
    if not has_feature(user, "tool_raw_material_analyzer"):
        st.error("Tu plan no incluye Comparador de Materias Primas.")
    else:
        st.title("🧪 Comparador de Materias Primas")
        st.caption("Módulo en construcción.")

else:
    render_dashboard(user)
    st.caption("Módulo para gestión de usuarios/planes.")

else:
    st.title("UYWA")
    st.warning("Ruta no reconocida.")
