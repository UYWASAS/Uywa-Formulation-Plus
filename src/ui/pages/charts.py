import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from src.ui.components.sections import render_section
from src.ui.components.cards import render_card, render_metric_card
from src.ui.components.tables import render_table


SPECIES_RESULT_KEYS = {
    "Aves": "last_result_aves",
    "Cerdos": "last_result_cerdos",
    "Rumiantes": "last_result_rumiantes",
}


def _first_success_result():
    for species, key in SPECIES_RESULT_KEYS.items():
        result = st.session_state.get(key)
        if result and result.get("success"):
            return species, result
    return None, None


def _status_color(estado: str):
    e = str(estado or "").strip().lower()
    if "cumple" in e or e == "ok":
        return "#2ca25f"
    if "deficiente" in e or "incumple" in e or "exceso" in e:
        return "#d9534f"
    if "sin" in e:
        return "#6c757d"
    return "#f0ad4e"


def _build_palette(n):
    base = ["#1f3a93", "#2e5ca6", "#4a7db8", "#7da8d4", "#c0d9ed", "#e2b659", "#7fc47f", "#ed7a7a"]
    if n <= len(base):
        return base[:n]
    out = []
    i = 0
    while len(out) < n:
        out.append(base[i % len(base)])
        i += 1
    return out


def render():
    st.title("Gráficos")

    available_species = []
    for sp, key in SPECIES_RESULT_KEYS.items():
        r = st.session_state.get(key)
        if r and r.get("success"):
            available_species.append(sp)

    if not available_species:
        render_card(
            "Sin datos para graficar",
            "Primero ejecuta una formulación exitosa en Aves, Cerdos o Rumiantes.",
            variant="info",
        )
        return

    default_species, _ = _first_success_result()
    species = st.selectbox(
        "Especie a visualizar",
        available_species,
        index=available_species.index(default_species) if default_species in available_species else 0,
        key="charts_species_select",
    )

    result = st.session_state.get(SPECIES_RESULT_KEYS[species], {})
    diet = result.get("diet", {}) or {}
    compliance = result.get("compliance_data", []) or []
    cost_100kg = float(result.get("cost", 0) or 0)

    # KPI strip
    c1, c2, c3 = st.columns(3)
    with c1:
        render_metric_card("Costo (100 kg)", f"${cost_100kg:.2f}", f"{species}")
    with c2:
        render_metric_card("Costo/kg", f"${(cost_100kg/100):.4f}", "Estimado")
    with c3:
        render_metric_card("Ingredientes activos", str(len(diet)), "Inclusión > 0")

    st.markdown("---")

    tab1, tab2, tab3 = st.tabs(
        ["Composición ingredientes", "Cumplimiento nutricional", "Datos"]
    )

    # TAB 1
    with tab1:
        render_section("Composición por ingrediente", f"Especie: {species}")

        df_diet = pd.DataFrame(list(diet.items()), columns=["Ingrediente", "Inclusión (%)"])
        if df_diet.empty:
            st.info("No hay ingredientes para graficar.")
        else:
            df_diet = df_diet.sort_values("Inclusión (%)", ascending=False).reset_index(drop=True)
            colors = _build_palette(len(df_diet))

            chart_type = st.radio(
                "Tipo de gráfico",
                ["Barras", "Pastel", "Barras horizontales"],
                horizontal=True,
                key=f"charts_type_diet_{species}",
            )

            if chart_type == "Barras":
                fig = go.Figure(
                    go.Bar(
                        x=df_diet["Ingrediente"],
                        y=df_diet["Inclusión (%)"],
                        marker_color=colors,
                        text=[f"{v:.2f}%" for v in df_diet["Inclusión (%)"]],
                        textposition="auto",
                        hovertemplate="%{x}<br>Inclusión: %{y:.3f}%<extra></extra>",
                    )
                )
                fig.update_layout(
                    title="Inclusión por ingrediente",
                    xaxis_title="Ingrediente",
                    yaxis_title="Inclusión (%)",
                    template="simple_white",
                    showlegend=False,
                )
            elif chart_type == "Barras horizontales":
                fig = go.Figure(
                    go.Bar(
                        y=df_diet["Ingrediente"],
                        x=df_diet["Inclusión (%)"],
                        marker_color=colors,
                        orientation="h",
                        text=[f"{v:.2f}%" for v in df_diet["Inclusión (%)"]],
                        textposition="auto",
                        hovertemplate="%{y}<br>Inclusión: %{x:.3f}%<extra></extra>",
                    )
                )
                fig.update_layout(
                    title="Inclusión por ingrediente (horizontal)",
                    xaxis_title="Inclusión (%)",
                    yaxis_title="Ingrediente",
                    template="simple_white",
                    showlegend=False,
                    yaxis={"categoryorder": "total ascending"},
                )
            else:
                fig = go.Figure(
                    go.Pie(
                        labels=df_diet["Ingrediente"],
                        values=df_diet["Inclusión (%)"],
                        hole=0.38,
                        textinfo="percent",
                        hovertemplate="%{label}<br>%{value:.3f}%<extra></extra>",
                        marker=dict(colors=colors),
                    )
                )
                fig.update_layout(title="Distribución porcentual de ingredientes")

            st.plotly_chart(fig, use_container_width=True)

    # TAB 2
    with tab2:
        render_section("Estado de cumplimiento nutricional")

        df_comp = pd.DataFrame(compliance)
        if df_comp.empty or "Estado" not in df_comp.columns:
            st.info("No hay cumplimiento nutricional para graficar.")
        else:
            estado_count = df_comp["Estado"].fillna("Sin dato").value_counts().reset_index()
            estado_count.columns = ["Estado", "Cantidad"]
            estado_count["Color"] = estado_count["Estado"].apply(_status_color)

            fig_estado = go.Figure(
                go.Bar(
                    x=estado_count["Estado"],
                    y=estado_count["Cantidad"],
                    marker_color=estado_count["Color"],
                    text=estado_count["Cantidad"],
                    textposition="auto",
                    hovertemplate="Estado: %{x}<br>Cantidad: %{y}<extra></extra>",
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

            if {"Nutriente", "Mínimo", "Máximo", "Obtenido", "Estado"}.issubset(set(df_comp.columns)):
                with st.expander("Ver detalle de cumplimiento", expanded=False):
                    render_table(df_comp[["Nutriente", "Mínimo", "Máximo", "Obtenido", "Estado"]])

    # TAB 3
    with tab3:
        render_section("Datos usados en gráficos")
        st.caption("Solo lectura; no modifica cálculos.")

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Diet (ingredientes)**")
            render_table(pd.DataFrame(list(diet.items()), columns=["Ingrediente", "Inclusión (%)"]))
        with c2:
            st.markdown("**Compliance**")
            render_table(pd.DataFrame(compliance) if compliance else pd.DataFrame(columns=["Nutriente", "Estado"]))
