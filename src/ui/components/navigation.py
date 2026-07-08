import streamlit as st


MODULES = {
    "formulador_aves": "🐔 Formulador · Aves",
    "formulador_cerdos": "🐖 Formulador · Cerdos",
    "formulador_rumiantes": "🐄 Formulador · Rumiantes",
    "tool_energia": "⚡ Calculador de Energía",
    "tool_materias_primas": "🧪 Comparador de Materias Primas",
}


def _ensure_nav_state():
    if "module" not in st.session_state:
        st.session_state["module"] = "formulador_aves"


def _module_index(module_key: str) -> int:
    keys = list(MODULES.keys())
    return keys.index(module_key) if module_key in keys else 0


def render_sidebar_navigation(user: dict | None = None) -> str:
    """
    Renderiza sidebar macro y retorna el module_key seleccionado.
    """
    _ensure_nav_state()

    with st.sidebar:
        st.markdown("## UYWA Nutrition")
        st.caption("Plataforma de formulación y herramientas")

        st.markdown("---")
        st.markdown("### Formuladores")

        keys = list(MODULES.keys())
        labels = [MODULES[k] for k in keys]

        selected_label = st.radio(
            "Selecciona módulo",
            options=labels,
            index=_module_index(st.session_state.get("module")),
            key="nav_module_radio",
            label_visibility="collapsed",
        )

        selected_key = keys[labels.index(selected_label)]
        st.session_state["module"] = selected_key

        st.markdown("---")
        st.markdown("### Estado")

        if user:
            plan = user.get("plan", "Sin plan")
            st.success(f"Plan: {plan}")
            expires = user.get("expires")
            if expires:
                st.caption(f"Válido hasta: {expires}")
        else:
            st.info("Sin sesión de usuario")

        st.markdown("---")
        st.caption("© 2026 UYWA")

    return st.session_state["module"]
