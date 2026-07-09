import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

from src.ui.components.sections import render_section
from src.ui.components.cards import render_card
from src.ui.components.tables import render_table


SPECIES_KEYS = {
    "Aves": {
        "result": "last_result_aves",
        "ingredients": "ingredients_df",
        "req": "req_input",
        "selected_nutrients": "nutrientes_seleccionados",
    },
    "Cerdos": {
        "result": "last_result_cerdos",
        "ingredients": "ingredients_df_cerdos",
        "req": "req_input_cerdos",
        "selected_nutrients": "nutrientes_seleccionados_cerdos",
    },
    "Rumiantes": {
        "result": "last_result_rumiantes",
        "ingredients": "ingredients_df_rumiantes",
        "req": "req_input_rumiantes",
        "selected_nutrients": "nutrientes_seleccionados_rumiantes",
    },
}


def _safe_float(v, default=0.0):
    try:
        if isinstance(v, str):
            v = v.replace(",", ".")
        return float(v)
    except Exception:
        return default


def _get_color_map(ingredients):
    palette = [
        "#19345c", "#7a9fc8", "#e2b659", "#7fc47f",
        "#ed7a7a", "#c07ad7", "#7ad7d2", "#ffb347",
        "#b7e28a", "#d1a3a4", "#f0837c", "#b2b2b2",
    ]
    return {ing: palette[i % len(palette)] for i, ing in enumerate(ingredients)}


def _first_success_species():
    for sp, cfg in SPECIES_KEYS.items():
        r = st.session_state.get(cfg["result"])
        if r and r.get("success"):
            return sp
    return None


def _default_units(nutrients):
    ref = {
        "PB": "kg",
        "EE": "kg",
        "FB": "kg",
        "EMA_POLLIT": "kcal",
        "EMA_AVES": "kcal",
        "LYS_DR": "g",
        "MET_DR": "g",
        "M+C_DR": "g",
        "THR_DR": "g",
        "TRP_DR": "g",
        "ILE_DR": "g",
        "VAL_DR": "g",
        "ARG_DR": "g",
        "Ca": "%",
        "P": "%",
        "Pdisp.AVES": "%",
        "Na": "%",
        "K": "%",
    }
    return {n: ref.get(n, "unidad") for n in nutrients}


def _unit_options(base_unit):
    opts = {
        "kg": ["kg", "ton"],
        "g": ["g", "100g", "kg", "ton"],
        "kcal": ["kcal", "1000kcal"],
        "%": ["%", "100 unidades"],
        "unidad": ["unidad", "100 unidades", "1000 unidades", "kg", "ton"],
    }
    return opts.get(base_unit, ["unidad"])


def _unit_factor(base_unit, chosen):
    conv = {
        ("kg", "kg"): (1, "kg"),
        ("kg", "ton"): (0.001, "ton"),
        ("g", "g"): (1, "g"),
        ("g", "100g"): (0.01, "100g"),
        ("g", "kg"): (0.001, "kg"),
        ("g", "ton"): (0.000001, "ton"),
        ("kcal", "kcal"): (1, "kcal"),
        ("kcal", "1000kcal"): (0.001, "1000kcal"),
        ("%", "%"): (1, "%"),
        ("%", "100 unidades"): (100, "100 unidades"),
        ("unidad", "unidad"): (1, "unidad"),
        ("unidad", "100 unidades"): (100, "100 unidades"),
        ("unidad", "1000 unidades"): (1000, "1000 unidades"),
        ("unidad", "kg"): (1, "kg"),
        ("unidad", "ton"): (0.001, "ton"),
    }
    return conv.get((base_unit, chosen), (1, chosen))


def render():
    st.title("Gráficos de la formulación")
    st.caption("Visualiza costo, aporte nutricional y costo relativo por nutriente.")

    available = []
    for sp, cfg in SPECIES_KEYS.items():
        r = st.session_state.get(cfg["result"])
        if r and r.get("success"):
            available.append(sp)

    if not available:
        render_card(
            "Sin resultados",
            "Primero formula exitosamente en Aves, Cerdos o Rumiantes.",
            variant="warning",
        )
        return

    default_sp = _first_success_species()
    species = st.selectbox(
        "Especie",
        options=available,
        index=available.index(default_sp) if default_sp in available else 0,
        key="charts_species_selector",
    )

    cfg = SPECIES_KEYS[species]
    result = st.session_state.get(cfg["result"], {})
    diet = result.get("diet", {}) or {}
    nutritional_values = result.get("nutritional_values", {}) or {}
    compliance_data = result.get("compliance_data", []) or []

    ingredients_df = st.session_state.get(cfg["ingredients"])
    if ingredients_df is None or (isinstance(ingredients_df, pd.DataFrame) and ingredients_df.empty):
        # fallback común
        ingredients_df = st.session_state.get("ingredients_df")

    nutrients_selected = st.session_state.get(cfg["selected_nutrients"], []) or list(nutritional_values.keys())

    if not diet:
        render_card("Sin dieta", "No hay composición para graficar.", variant="info")
        return
    if ingredients_df is None or ingredients_df.empty:
        render_card("Sin matriz de ingredientes", "No se encontró ingredients_df en sesión.", variant="danger")
        return
    if "Ingrediente" not in ingredients_df.columns or "precio" not in ingredients_df.columns:
        render_card("Matriz inválida", "La matriz debe contener 'Ingrediente' y 'precio'.", variant="danger")
        return

    df_formula = ingredients_df.copy()
    df_formula["Ingrediente"] = df_formula["Ingrediente"].astype(str)
    df_formula["precio"] = pd.to_numeric(df_formula["precio"], errors="coerce").fillna(0)
    df_formula["% Inclusión"] = df_formula["Ingrediente"].map(diet).fillna(0)
    df_formula = df_formula[df_formula["Ingrediente"].isin(diet.keys())].reset_index(drop=True)

    if df_formula.empty:
        st.info("No hay filas para graficar.")
        return

    color_map = _get_color_map(df_formula["Ingrediente"].tolist())
    total_cost_100kg = _safe_float(result.get("cost", 0), 0)
    total_cost_ton = (total_cost_100kg / 100) * 1000

    tabs = st.tabs(["Costo por ingrediente", "Aporte a nutrientes", "Costo relativo por nutriente", "Cumplimiento"])

    # TAB 1 - Costo por ingrediente
    with tabs[0]:
        render_section("Costo por ingrediente", "Participación de cada ingrediente en el costo total.")

        unit = st.radio("Unidad", ["USD/ton", "USD/kg"], horizontal=True, key=f"charts_cost_unit_{species}")
        factor = 1000 if unit == "USD/ton" else 1

        costos = []
        for _, row in df_formula.iterrows():
            precio = _safe_float(row["precio"], 0)
            inclusion = _safe_float(row["% Inclusión"], 0)
            costo = precio * inclusion / 100 * factor
            costos.append(costo)

        suma_costos = sum(costos)
        suma_inclusion = _safe_float(df_formula["% Inclusión"].sum(), 0)
        proporciones = [
            (_safe_float(x, 0) * 100 / suma_inclusion) if suma_inclusion > 0 else 0
            for x in df_formula["% Inclusión"]
        ]

        chart_type = st.radio("Tipo de gráfico", ["Pastel", "Barras"], horizontal=True, key=f"charts_cost_type_{species}")

        if chart_type == "Pastel":
            fig = go.Figure(
                go.Pie(
                    labels=df_formula["Ingrediente"],
                    values=costos,
                    marker_colors=[color_map[i] for i in df_formula["Ingrediente"]],
                    hole=0.35,
                    textinfo="label+percent",
                    hovertemplate="%{label}<br>Costo: %{value:.3f} " + unit + "<extra></extra>",
                )
            )
            fig.update_layout(title=f"Participación de cada ingrediente en el costo total ({unit})")
        else:
            fig = go.Figure(
                go.Bar(
                    x=df_formula["Ingrediente"],
                    y=costos,
                    marker_color=[color_map[i] for i in df_formula["Ingrediente"]],
                    text=[f"{v:.3f}" for v in costos],
                    textposition="auto",
                    customdata=proporciones,
                    hovertemplate="%{x}<br>Costo: %{y:.3f} " + unit + "<br>Proporción dieta: %{customdata:.2f}%<extra></extra>",
                )
            )
            fig.update_layout(
                title=f"Costo total por ingrediente ({unit})",
                xaxis_title="Ingrediente",
                yaxis_title=f"Costo aportado ({unit})",
                template="simple_white",
                showlegend=False,
            )

        st.plotly_chart(fig, use_container_width=True)

        df_cost = pd.DataFrame({
            "Ingrediente": df_formula["Ingrediente"],
            f"Costo aportado ({unit})": costos,
            "Inclusión (%)": df_formula["% Inclusión"],
            "Proporción dieta (%)": proporciones,
            "Precio ingrediente (USD/kg)": df_formula["precio"],
        })

        render_table(
            df_cost,
            column_config={
                f"Costo aportado ({unit})": st.column_config.NumberColumn(f"Costo aportado ({unit})", format="%.3f"),
                "Inclusión (%)": st.column_config.NumberColumn("Inclusión (%)", format="%.3f"),
                "Proporción dieta (%)": st.column_config.NumberColumn("Proporción dieta (%)", format="%.2f%%"),
                "Precio ingrediente (USD/kg)": st.column_config.NumberColumn("Precio ingrediente (USD/kg)", format="$%.4f"),
            },
        )
        st.caption(f"Costo total estimado: {suma_costos:.3f} {unit} | Solver: ${total_cost_ton:.2f}/ton")

    # TAB 2 - Aporte a nutrientes
    with tabs[1]:
        render_section("Aporte a nutrientes", "Aporte de cada ingrediente a cada nutriente seleccionado.")

        if not nutrients_selected:
            st.info("No hay nutrientes seleccionados.")
        else:
            nutrient_tabs = st.tabs([n for n in nutrients_selected])

            units_ref = _default_units(nutrients_selected)

            for i, nut in enumerate(nutrients_selected):
                with nutrient_tabs[i]:
                    base_unit = units_ref.get(nut, "unidad")
                    chosen_unit = st.selectbox(
                        f"Unidad para {nut}",
                        options=_unit_options(base_unit),
                        key=f"charts_aporte_unit_{species}_{nut}",
                    )
                    factor, label = _unit_factor(base_unit, chosen_unit)

                    aportes = []
                    props = []
                    total_nut = 0.0

                    for _, row in df_formula.iterrows():
                        val = _safe_float(row.get(nut, 0), 0) if nut in df_formula.columns else 0
                        inc = _safe_float(row["% Inclusión"], 0)
                        ap = val * inc / 100 * factor
                        aportes.append(ap)
                        total_nut += ap

                    if total_nut > 0:
                        props = [(x / total_nut) * 100 for x in aportes]
                    else:
                        props = [0 for _ in aportes]

                    fig = go.Figure(
                        go.Bar(
                            x=df_formula["Ingrediente"],
                            y=aportes,
                            marker_color=[color_map[i] for i in df_formula["Ingrediente"]],
                            text=[f"{x:.3f}" for x in aportes],
                            textposition="auto",
                            customdata=props,
                            hovertemplate="%{x}<br>Aporte: %{y:.3f} " + label + "<br>Proporción aporte: %{customdata:.2f}%<extra></extra>",
                        )
                    )
                    fig.update_layout(
                        title=f"Aporte de cada ingrediente a {nut}",
                        xaxis_title="Ingrediente",
                        yaxis_title=f"Aporte de {nut} ({label})",
                        template="simple_white",
                        showlegend=False,
                    )
                    st.plotly_chart(fig, use_container_width=True)

                    df_ap = pd.DataFrame({
                        "Ingrediente": df_formula["Ingrediente"],
                        f"Aporte de {nut} ({label})": aportes,
                        "Inclusión (%)": df_formula["% Inclusión"],
                        f"Contenido de {nut}": pd.to_numeric(df_formula[nut], errors="coerce").fillna(0) if nut in df_formula.columns else 0,
                        f"Proporción aporte {nut} (%)": props,
                    })
                    render_table(
                        df_ap,
                        column_config={
                            f"Aporte de {nut} ({label})": st.column_config.NumberColumn(f"Aporte de {nut} ({label})", format="%.4f"),
                            "Inclusión (%)": st.column_config.NumberColumn("Inclusión (%)", format="%.3f"),
                            f"Contenido de {nut}": st.column_config.NumberColumn(f"Contenido de {nut}", format="%.4f"),
                            f"Proporción aporte {nut} (%)": st.column_config.NumberColumn(f"Proporción aporte {nut} (%)", format="%.2f%%"),
                        },
                    )

    # TAB 3 - Costo relativo por nutriente
    with tabs[2]:
        render_section("Costo relativo por nutriente", "Compara el costo de obtener una unidad de nutriente desde cada ingrediente.")

        if not nutrients_selected:
            st.info("No hay nutrientes seleccionados.")
        else:
            units_ref = _default_units(nutrients_selected)
            nutrient_tabs = st.tabs([n for n in nutrients_selected])

            for i, nut in enumerate(nutrients_selected):
                with nutrient_tabs[i]:
                    base_unit = units_ref.get(nut, "unidad")
                    chosen_unit = st.selectbox(
                        f"Unidad para {nut}",
                        options=_unit_options(base_unit),
                        key=f"charts_relcost_unit_{species}_{nut}",
                    )
                    factor, label = _unit_factor(base_unit, chosen_unit)

                    costs_per_unit = []
                    conts = []
                    prices = []

                    for _, row in df_formula.iterrows():
                        cont = _safe_float(row.get(nut, 0), 0) if nut in df_formula.columns else 0
                        price = _safe_float(row.get("precio", 0), 0)
                        if cont > 0 and price > 0:
                            costs_per_unit.append((price / cont) * factor)
                        else:
                            costs_per_unit.append(np.nan)
                        conts.append(cont)
                        prices.append(price)

                    arr = np.array([v if pd.notnull(v) else np.inf for v in costs_per_unit], dtype=float)
                    best_idx = None if np.all(np.isinf(arr)) else int(np.nanargmin(arr))

                    colors = [
                        "#2ca25f" if (best_idx is not None and idx == best_idx) else "#2176ff"
                        for idx in range(len(costs_per_unit))
                    ]

                    fig = go.Figure(
                        go.Bar(
                            x=df_formula["Ingrediente"],
                            y=[v if pd.notnull(v) else 0 for v in costs_per_unit],
                            marker_color=colors,
                            text=[f"{v:.4f}" if pd.notnull(v) else "" for v in costs_per_unit],
                            textposition="auto",
                            hovertemplate="%{x}<br>Costo relativo: %{y:.6f} " + label + "<extra></extra>",
                        )
                    )
                    fig.update_layout(
                        title=f"Costo relativo por unidad de {nut}",
                        xaxis_title="Ingrediente",
                        yaxis_title=label,
                        template="simple_white",
                        showlegend=False,
                    )
                    st.plotly_chart(fig, use_container_width=True)

                    df_rel = pd.DataFrame({
                        "Ingrediente": df_formula["Ingrediente"],
                        f"Costo por {chosen_unit}": costs_per_unit,
                        f"Contenido de {nut}": conts,
                        "Precio ingrediente (USD/kg)": prices,
                        "Menor costo relativo": ["Sí" if (best_idx is not None and j == best_idx) else "" for j in range(len(costs_per_unit))],
                    })
                    render_table(
                        df_rel,
                        column_config={
                            f"Costo por {chosen_unit}": st.column_config.NumberColumn(f"Costo por {chosen_unit}", format="%.6f"),
                            f"Contenido de {nut}": st.column_config.NumberColumn(f"Contenido de {nut}", format="%.4f"),
                            "Precio ingrediente (USD/kg)": st.column_config.NumberColumn("Precio ingrediente (USD/kg)", format="$%.4f"),
                        },
                    )

    # TAB 4 - Cumplimiento (detallado)
    with tabs[3]:
        render_section("Cumplimiento nutricional", "Resumen por estado + detalle por nutriente.")
        df_comp = pd.DataFrame(compliance_data)

        if df_comp.empty:
            st.info("No hay datos de cumplimiento.")
        else:
            if "Estado" in df_comp.columns:
                estado_count = df_comp["Estado"].fillna("Sin dato").value_counts().reset_index()
                estado_count.columns = ["Estado", "Cantidad"]
                color_map_estado = {
                    e: ("#2ca25f" if "cumple" in str(e).lower()
                        else "#d9534f" if ("deficiente" in str(e).lower() or "exceso" in str(e).lower() or "incumple" in str(e).lower())
                        else "#f0ad4e")
                    for e in estado_count["Estado"]
                }
                fig_estado = go.Figure(
                    go.Bar(
                        x=estado_count["Estado"],
                        y=estado_count["Cantidad"],
                        marker_color=[color_map_estado[e] for e in estado_count["Estado"]],
                        text=estado_count["Cantidad"],
                        textposition="auto",
                    )
                )
                fig_estado.update_layout(
                    title="Conteo por estado nutricional",
                    xaxis_title="Estado",
                    yaxis_title="Cantidad",
                    template="simple_white",
                    showlegend=False,
                )
                st.plotly_chart(fig_estado, use_container_width=True)

            cols_show = [c for c in ["Nutriente", "Mínimo", "Máximo", "Obtenido", "Estado"] if c in df_comp.columns]
            render_table(df_comp[cols_show] if cols_show else df_comp)
