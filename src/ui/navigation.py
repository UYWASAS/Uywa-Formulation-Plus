import streamlit as st

from src.core.auth.policies import (
    available_formulators,
    available_tools,
    get_user_plan,
    has_feature,
)


def render_main_navigation(user: dict | None) -> str:
    """
    Menú lateral dinámico según plan.
    Devuelve una clave de ruta para el router principal.
    """
    plan = get_user_plan(user)
    formulators = available_formulators(user)
    tools = available_tools(user)

    st.sidebar.markdown("### Navegación")

    options = ["Dashboard"]

    if formulators:
        options.append("Formuladores")
        options.extend([f"Formulador · {f}" for f in formulators])

    options.append("Resultados")
    options.append("Gráficos")

    if has_feature(user, "scenario_compare"):
        options.append("Comparador de Escenarios")

    if tools:
        options.append("Herramientas")
        options.extend([f"Tool · {t}" for t in tools])

    if has_feature(user, "admin_users") or has_feature(user, "admin_plans"):
        options.append("Administración")

    selected = st.sidebar.radio(
        f"Plan activo: {plan}",
        options,
        index=0,
        key="main_navigation_radio",
    )

    return selected


def route_key_from_selection(selection: str) -> str:
    """
    Convierte texto visible del menú en clave de ruta interna.
    """
    mapping = {
        "Dashboard": "dashboard",
        "Resultados": "results",
        "Gráficos": "charts",
        "Comparador de Escenarios": "scenarios",
        "Administración": "admin",
        "Formuladores": "formulators_home",
        "Herramientas": "tools_home",
        "Formulador · Aves": "formulator_aves",
        "Formulador · Cerdos": "formulator_cerdos",
        "Formulador · Rumiantes": "formulator_rumiantes",
        "Tool · Predictor de Energía": "tool_energy_predictor",
        "Tool · Analizador de Materias Primas": "tool_raw_material_analyzer",
        "Tool · Comparador de Escenarios": "scenarios",
    }

    return mapping.get(selection, "dashboard")
