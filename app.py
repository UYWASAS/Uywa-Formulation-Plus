import streamlit as st

from auth import USERS_DB, is_user_active
from src.ui.components.theme import apply_theme, render_brand_sidebar
from src.ui.navigation import render_main_navigation, route_key_from_selection
from src.core.auth.policies import has_feature


# ============================================================
# CONFIG APP
# ============================================================

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


# ============================================================
# BOOT
# ============================================================

apply_theme()

if not st.session_state.get("logged_in", False):
    login()
    st.stop()

user = st.session_state.get("user", None)
render_brand_sidebar(user)

st.markdown(
    f"<div style='text-align:right'>👤 Usuario: <b>{st.session_state['usuario']}</b></div>",
    unsafe_allow_html=True,
)

selection = render_main_navigation(user)
route_key = route_key_from_selection(selection)


# ============================================================
# ROUTER (MVP)
# ============================================================

if route_key == "dashboard":
    st.title("UYWA Nutrition · Dashboard")
    st.info("Arquitectura modular activa. Siguiente paso: conectar páginas por especie.")

elif route_key == "formulators_home":
    st.title("Formuladores")
    st.write("Selecciona un formulador por especie en el menú lateral.")

elif route_key == "formulator_aves":
    if not has_feature(user, "formulator_aves"):
        st.error("Tu plan no incluye Formulador Aves.")
    else:
        st.title("Formulador · Aves")
        st.caption("En el próximo paso conectamos aquí tu flujo actual de formulación.")

elif route_key == "formulator_cerdos":
    if not has_feature(user, "formulator_cerdos"):
        st.error("Tu plan no incluye Formulador Cerdos.")
    else:
        st.title("Formulador · Cerdos")
        st.caption("Módulo preparado para integración.")

elif route_key == "formulator_rumiantes":
    if not has_feature(user, "formulator_rumiantes"):
        st.error("Tu plan no incluye Formulador Rumiantes.")
    else:
        st.title("Formulador · Rumiantes")
        st.caption("Módulo preparado para integración.")

elif route_key == "results":
    st.title("Resultados")
    st.caption("Aquí moveremos tu bloque Tab Resultados actual.")

elif route_key == "charts":
    st.title("Gráficos")
    st.caption("Aquí moveremos tu bloque Tab Gráficos actual.")

elif route_key == "scenarios":
    if not has_feature(user, "scenario_compare"):
        st.error("Tu plan no incluye Comparador de Escenarios.")
    else:
        st.title("Comparador de Escenarios")
        st.caption("Aquí moveremos tu bloque Tab Comparar Escenarios.")

elif route_key == "tool_energy_predictor":
    if not has_feature(user, "tool_energy_predictor"):
        st.error("Tu plan no incluye Predictor de Energía.")
    else:
        st.title("Tool · Predictor de Energía")
        st.caption("Módulo nuevo en construcción.")

elif route_key == "tool_raw_material_analyzer":
    if not has_feature(user, "tool_raw_material_analyzer"):
        st.error("Tu plan no incluye Analizador de Materias Primas.")
    else:
        st.title("Tool · Analizador de Materias Primas")
        st.caption("Módulo nuevo en construcción.")

elif route_key == "admin":
    st.title("Administración")
    st.caption("Módulo para gestión de usuarios/planes.")

else:
    st.title("UYWA")
    st.warning("Ruta no reconocida.")
