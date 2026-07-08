import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from src.ui.components.sections import render_section
from src.ui.components.cards import render_card


def _get_last_result_any_species():
    for key, species in [
        ("last_result_aves", "Aves"),
        ("last_result_cerdos", "Cerdos"),
        ("last_result_rumiantes", "Rumiantes"),
    ]:
        result = st.session_state.get(key)
        if result:
            return result, species
    return None, None


def render():
    st.title("Gráficos")

    result, species = _get_last_result_any_species()

    if not result or not result.get("success"):
        render_card(
            "Sin datos para graficar",
            "Primero ejecuta una formulación exitosa en alguna especie.",
            variant="info",
        )
        return

    diet = result.get("diet", {})
    compliance = result.get("compliance_data", [])

    render_section("Composición por ingrediente", f"Especie: {species}")

    df_diet = pd.DataFrame(list(diet.items()), columns=["Ingrediente", "Inclusión (%)"])
    if df_diet.empty:
        st.info("No hay ingredientes para graficar.")
    else:
        df_diet = df_diet.sort_values("Inclusión (%)", ascending=False)

        chart_type = st.radio(
            "Tipo de gráfico",
            ["Barras", "Pastel"],
            horizontal=True,
            key="charts_type_diet",
        )

        if chart_type == "Barras":
            fig = go.Figure(
                go.Bar(
                    x=df_diet["Ingrediente"],
                    y=df_diet["Inclusión (%)"],
                    text=[f"{v:.2f}%" for v in df_diet["Inclusión (%)"]],
                    textposition="auto",
                )
            )
            fig.update_layout(
                title="Inclusión por ingrediente",
                xaxis_title="Ingrediente",
                yaxis_title="Inclusión (%)",
                template="simple_white",
                showlegend=False,
            )
        else:
            fig = go.Figure(
                go.Pie(
                    labels=df_diet["Ingrediente"],
                    values=df_diet["Inclusión (%)"],
                    hole=0.35,
                    textinfo="label+percent",
                )
            )
            fig.update_layout(title="Distribución porcentual de ingredientes")

        st.plotly_chart(fig, use_container_width=True)

    render_section("Estado de cumplimiento nutricional")

    df_comp = pd.DataFrame(compliance)
    if df_comp.empty:
        st.info("No hay cumplimiento para graficar.")
        return

    estado_count = (
        df_comp["Estado"].fillna("Sin dato").value_counts().reset_index()
    )
    estado_count.columns = ["Estado", "Cantidad"]

    fig_estado = go.Figure(
        go.Bar(
            x=estado_count["Estado"],
            y=estado_count["Cantidad"],
            text=estado_count["Cantidad"],
            textposition="auto",
        )
    )
    fig_estado.update_layout(
        title="Conteo de estado nutricional",
        xaxis_title="Estado",
        yaxis_title="Cantidad de nutrientes",
        template="simple_white",
        showlegend=False,
    )
    st.plotly_chart(fig_estado, use_container_width=True)
