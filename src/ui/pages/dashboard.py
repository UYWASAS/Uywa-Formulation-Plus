import streamlit as st

from src.ui.components.sections import render_section
from src.ui.components.cards import render_card, render_metric_card
from src.core.shared.utils import load_profile, save_profile


def render(user: dict | None):
    st.title("Dashboard UYWA Nutrition")

    if not user:
        st.warning("No hay usuario activo.")
        return

    profile = load_profile(user)

    render_section(
        "Resumen general",
        "Estado de la cuenta y métricas rápidas del uso de formulación.",
    )

    c1, c2, c3 = st.columns(3)

    with c1:
        render_metric_card(
            "Costo Dieta (último)",
            f"${profile.get('last_cost', '---')}",
            "Última formulación registrada",
        )

    with c2:
        render_metric_card(
            "Formulaciones guardadas",
            str(profile.get("num_saved", 0)),
            "Escenarios/proyectos acumulados",
        )

    with c3:
        render_metric_card(
            "Plan premium",
            "Sí" if profile.get("premium") else "No",
            "Flag de perfil histórico",
        )

    render_section("Cuenta")
    render_card(
        "Usuario activo",
        (
            f"Nombre: {user.get('name', 'N/A')} | "
            f"Plan: {user.get('plan', 'N/A')} | "
            f"Expira: {user.get('expires', 'Sin vencimiento')}"
        ),
        variant="info",
    )

    if st.button("Actualizar snapshot de perfil", key="btn_update_profile_snapshot"):
        # Snapshot simple inicial; luego lo enlazamos a resultados reales
        profile["premium"] = bool(user.get("premium", False))
        save_profile(user, profile)
        st.success("Perfil actualizado.")
