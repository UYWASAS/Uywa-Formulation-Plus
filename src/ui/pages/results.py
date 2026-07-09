import streamlit as st
import pandas as pd

from src.ui.components.sections import render_section
from src.ui.components.cards import render_card, render_metric_card
from src.ui.components.tables import render_table


SPECIES_KEYS = {
    "Aves": {
        "result": "last_result_aves",
        "ingredients": "ingredients_df",
        "req": "req_input",
        "selected_nutrients": "nutrientes_seleccionados",
        "ratios": "ratios",
    },
    "Cerdos": {
        "result": "last_result_cerdos",
        "ingredients": "ingredients_df_cerdos",
        "req": "req_input_cerdos",
        "selected_nutrients": "nutrientes_seleccionados_cerdos",
        "ratios": "ratios_cerdos",
    },
    "Rumiantes": {
        "result": "last_result_rumiantes",
        "ingredients": "ingredients_df_rumiantes",
        "req": "req_input_rumiantes",
        "selected_nutrients": "nutrientes_seleccionados_rumiantes",
        "ratios": "ratios_rumiantes",
    },
}


def _safe_float(v, default=0.0):
    try:
        if isinstance(v, str):
            v = v.replace(",", ".")
        return float(v)
    except Exception:
        return default


def _first_success_species():
    for sp, cfg in SPECIES_KEYS.items():
        r = st.session_state.get(cfg["result"])
        if r and r.get("success"):
            return sp
    return None


def _estado_texto(minimo, maximo, obtenido):
    if pd.isna(obtenido):
        return "No evaluable"
    if maximo and obtenido > maximo:
        return "Exceso"
    if minimo and obtenido < minimo:
        return "Deficiente"
    if minimo or maximo:
        return "Cumple"
    return "Sin restricción"


def _get_limiting_ingredient(nutriente, diet, ingredients_df):
    try:
        if ingredients_df is None or ingredients_df.empty:
            return "—"
        if nutriente not in ingredients_df.columns:
            return "—"

        aportes = {}
        total = 0.0

        for ing, pct in (diet or {}).items():
            row = ingredients_df[ingredients_df["Ingrediente"] == ing]
            if row.empty:
                continue
            val = _safe_float(row.iloc[0].get(nutriente, 0), 0)
            ap = val * (_safe_float(pct, 0) / 100)
            aportes[ing] = ap
            total += ap

        if total <= 0 or not aportes:
            return "—"

        ing_top, ap_top = max(aportes.items(), key=lambda x: x[1])
        return f"{ing_top} ({(ap_top / total) * 100:.0f}%)"
    except Exception:
        return "—"


def _ratio_denominator_min_warnings(ratios, requirements_map):
    warnings = []
    for ratio in ratios or []:
        den = ratio.get("denominador")
        den_min = _safe_float((requirements_map or {}).get(den, {}).get("min", 0), 0)
        if den and den_min <= 0:
            warnings.append(
                f"{ratio.get('numerador')} / {den} {ratio.get('operador')} {ratio.get('valor')}"
            )
    return warnings


def _evaluate_ratio_status(ratio, nutritional_values, requirements_map):
    num = ratio.get("numerador")
    den = ratio.get("denominador")
    op = ratio.get("operador")
    val = _safe_float(ratio.get("valor", 0), 0)

    num_val = nutritional_values.get(num)
    den_val = nutritional_values.get(den)

    calculado = None
    cumple = None
    detalle = ""

    den_min = _safe_float((requirements_map or {}).get(den, {}).get("min", 0), 0)
    den_has_min = den_min > 0

    warning_min_msg = (
        f"Nota: este ratio no fuerza por sí solo un mínimo explícito para '{den}'. "
        f"Define un mínimo de '{den}' para asegurar un balance nutricional real."
    )

    if den_val is None:
        detalle = f"Nutriente '{den}' no disponible."
    elif abs(_safe_float(den_val, 0)) <= 1e-12:
        cumple = False
        detalle = (
            f"Ratio degenerado: denominador '{den}' = 0. "
            f"{warning_min_msg}"
        )
    elif num_val is None:
        detalle = f"Nutriente '{num}' no disponible."
    else:
        calculado = num_val / den_val
        if op == "=":
            cumple = abs(calculado - val) < 1e-2
        elif op == ">=":
            cumple = calculado >= val - 1e-2
        elif op == "<=":
            cumple = calculado <= val + 1e-2

        detalle = f"Calculado: {num_val:.3f} / {den_val:.3f} = {calculado:.3f}"
        if not den_has_min:
            detalle = f"{detalle}. {warning_min_msg}"

    estado = "Cumple" if cumple else ("No cumple" if cumple is False else "No evaluable")

    return {
        "calculado": calculado,
        "cumple": cumple,
        "detalle": detalle,
        "estado": estado,
    }


def render():
    st.title("Resultados de la formulación")
    st.caption("Resumen ejecutivo, composición, economía, cumplimiento nutricional y diagnóstico avanzado.")

    available = []
    for sp, cfg in SPECIES_KEYS.items():
        r = st.session_state.get(cfg["result"])
        if r:
            available.append(sp)

    if not available:
        render_card("Sin resultados", "Aún no hay corridas guardadas.", variant="info")
        return

    default_sp = _first_success_species() or available[0]
    species = st.selectbox(
        "Especie",
        options=available,
        index=available.index(default_sp),
        key="results_species_selector",
    )

    cfg = SPECIES_KEYS[species]
    result = st.session_state.get(cfg["result"], {})

    if not result:
        render_card("Sin datos", f"No hay resultado para {species}.", variant="info")
        return

    if not result.get("success"):
        render_card(
            "Última corrida no factible",
            result.get("message", "Sin detalle"),
            variant="danger",
        )
        diag = result.get("infeasibility_diagnostics", [])
        if diag:
            with st.expander("Diagnóstico de inviabilidad", expanded=False):
                render_table(pd.DataFrame(diag))
        return

    diet = result.get("diet", {}) or {}
    total_cost = _safe_float(result.get("cost", 0), 0)
    nutritional_values = result.get("nutritional_values", {}) or {}
    compliance_data = result.get("compliance_data", []) or []
    constraint_diagnostics = result.get("constraint_diagnostics", {}) or {}

    req_input = st.session_state.get(cfg["req"], {})
    nutrients_selected = st.session_state.get(cfg["selected_nutrients"], list(nutritional_values.keys()))
    ratios = st.session_state.get(cfg["ratios"], [])

    ingredients_df = st.session_state.get(cfg["ingredients"])
    if ingredients_df is None or (isinstance(ingredients_df, pd.DataFrame) and ingredients_df.empty):
        ingredients_df = st.session_state.get("ingredients_df")

    if not diet:
        render_card(
            "Sin composición de dieta",
            "No se encontraron ingredientes activos en el resultado.",
            variant="warning",
        )
        return

    # 1) Resumen ejecutivo
    render_section("Resumen ejecutivo", "Indicadores principales de la dieta formulada.")
    precio_kg = total_cost / 100 if total_cost else 0
    precio_ton = precio_kg * 1000

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        render_metric_card("Costo/100 kg", f"${total_cost:.2f}", "Costo base del solver")
    with c2:
        render_metric_card("Costo/kg", f"${precio_kg:.2f}", "Precio estimado por kg")
    with c3:
        render_metric_card("Costo/ton", f"${precio_ton:,.2f}", "Precio estimado por tonelada")
    with c4:
        render_metric_card("Ingredientes", f"{len(diet)}", "Incluidos en la fórmula")

    # 2) Composición óptima
    render_section("Composición óptima de la dieta", "Porcentaje de inclusión de cada ingrediente en la solución final.")
    df_diet = pd.DataFrame(list(diet.items()), columns=["Ingrediente", "Inclusión (%)"]).sort_values("Inclusión (%)", ascending=False)
    render_table(
        df_diet,
        column_config={
            "Inclusión (%)": st.column_config.NumberColumn("Inclusión (%)", format="%.3f"),
        },
    )

    # 3) Economía de ingredientes
    if ingredients_df is not None and not ingredients_df.empty and {"Ingrediente", "precio"}.issubset(set(ingredients_df.columns)):
        render_section("Economía de ingredientes", "Contribución económica de cada ingrediente al costo por tonelada.")

        econ_rows = []
        total_cost_ton_calc = 0.0

        for ing, inclusion in diet.items():
            row_match = ingredients_df[ingredients_df["Ingrediente"] == ing]
            if row_match.empty:
                continue
            precio_ing = _safe_float(row_match.iloc[0].get("precio", 0), 0)
            inclusion = _safe_float(inclusion, 0)
            costo_ton = precio_ing * inclusion / 100 * 1000
            total_cost_ton_calc += costo_ton

            econ_rows.append(
                {
                    "Ingrediente": ing,
                    "Inclusión (%)": inclusion,
                    "Precio ingrediente (USD/kg)": precio_ing,
                    "Costo aportado (USD/ton)": costo_ton,
                }
            )

        if econ_rows:
            econ_df = pd.DataFrame(econ_rows).sort_values("Costo aportado (USD/ton)", ascending=False)
            econ_df["Participación en costo (%)"] = (
                econ_df["Costo aportado (USD/ton)"] / total_cost_ton_calc * 100
                if total_cost_ton_calc > 0 else 0
            )

            top_ing = econ_df.iloc[0]
            top3 = econ_df.head(3)["Ingrediente"].tolist()

            render_card(
                "Principal componente económico",
                (
                    f"{top_ing['Ingrediente']} aporta ${top_ing['Costo aportado (USD/ton)']:.2f}/ton, "
                    f"equivale al {top_ing['Participación en costo (%)']:.1f}% del costo estimado. "
                    f"Mayor impacto económico: {', '.join(top3)}."
                ),
                variant="info",
            )

            with st.expander("Ver detalle económico por ingrediente", expanded=True):
                render_table(
                    econ_df,
                    column_config={
                        "Inclusión (%)": st.column_config.NumberColumn("Inclusión (%)", format="%.3f"),
                        "Precio ingrediente (USD/kg)": st.column_config.NumberColumn("Precio ingrediente (USD/kg)", format="$%.4f"),
                        "Costo aportado (USD/ton)": st.column_config.NumberColumn("Costo aportado (USD/ton)", format="$%.2f"),
                        "Participación en costo (%)": st.column_config.NumberColumn("Participación en costo (%)", format="%.2f%%"),
                    },
                )

    # 4) Composición nutricional
    render_section("Composición nutricional", "Cumplimiento de nutrientes frente a los requerimientos definidos.")
    comp_rows = []
    for nut in nutrients_selected:
        vals = req_input.get(nut, {})
        min_r = _safe_float(vals.get("min", 0), 0)
        max_r = _safe_float(vals.get("max", 0), 0)
        obtenido = nutritional_values.get(nut, None)
        estado = _estado_texto(min_r, max_r, obtenido)
        comp_rows.append(
            {
                "Nutriente": nut,
                "Mínimo": min_r if min_r > 0 else None,
                "Máximo": max_r if max_r > 0 else None,
                "Obtenido": obtenido,
                "Estado": estado,
            }
        )
    comp_df = pd.DataFrame(comp_rows)
    render_table(
        comp_df,
        column_config={
            "Mínimo": st.column_config.NumberColumn("Mínimo", format="%.3f"),
            "Máximo": st.column_config.NumberColumn("Máximo", format="%.3f"),
            "Obtenido": st.column_config.NumberColumn("Obtenido", format="%.3f"),
            "Estado": st.column_config.TextColumn("Estado"),
        },
    )

    # 5) Diagnóstico nutricional automático
    auto_rows = []
    precio_kg_formula = total_cost / 100 if total_cost else 0

    for cname, vals in constraint_diagnostics.items():
        if vals.get("tipo") != "Mínimo nutricional":
            continue
        nutrient = vals.get("item", "")
        shadow = vals.get("shadow_price", None)
        activa = vals.get("activa", False)
        if shadow is None:
            continue

        shadow_abs = abs(_safe_float(shadow, 0))
        impacto_pct = (shadow_abs / precio_kg_formula * 100) if precio_kg_formula > 0 else 0
        costo_marginal_ton = shadow_abs * 1000

        if activa or shadow_abs > 1e-10:
            auto_rows.append(
                {
                    "nutriente": nutrient,
                    "impacto_pct": impacto_pct,
                    "costo_marginal_ton": costo_marginal_ton,
                    "shadow": shadow_abs,
                }
            )

    if auto_rows:
        auto_rows = sorted(auto_rows, key=lambda x: x["impacto_pct"], reverse=True)
        top = auto_rows[0]

        ing_asociado = (
            _get_limiting_ingredient(top["nutriente"], diet, ingredients_df)
            if ingredients_df is not None and not ingredients_df.empty
            else "—"
        )

        render_section("Diagnóstico nutricional automático", "Interpretación económica de los nutrientes que condicionan la fórmula.")
        render_card(
            "Nutriente principal",
            (
                f"El nutriente que más condiciona económicamente la fórmula es {top['nutriente']}. "
                f"Costo marginal estimado: ${top['costo_marginal_ton']:.2f}/ton. "
                f"Impacto relativo: {top['impacto_pct']:.3f}%. "
                f"Ingrediente asociado: {ing_asociado}."
            ),
            variant="info",
        )

        if len(auto_rows) > 1:
            ranking_df = pd.DataFrame(
                [
                    {
                        "Orden": i + 1,
                        "Nutriente": row["nutriente"],
                        "Costo marginal USD/ton": row["costo_marginal_ton"],
                        "Impacto relativo (%)": row["impacto_pct"],
                    }
                    for i, row in enumerate(auto_rows[:10])
                ]
            )
            with st.expander("Ver ranking de nutrientes con impacto económico", expanded=True):
                render_table(
                    ranking_df,
                    column_config={
                        "Costo marginal USD/ton": st.column_config.NumberColumn("Costo marginal USD/ton", format="$%.2f"),
                        "Impacto relativo (%)": st.column_config.NumberColumn("Impacto relativo (%)", format="%.3f%%"),
                    },
                )

    # 6) Diagnóstico avanzado de nutrientes limitantes
    limiting_rows = []
    for cname, vals in constraint_diagnostics.items():
        if vals.get("tipo") not in ["Mínimo nutricional", "Máximo nutricional"]:
            continue

        shadow = vals.get("shadow_price", None)
        slack = vals.get("slack", None)
        activa = vals.get("activa", False)

        if shadow is None:
            continue

        shadow_abs = abs(_safe_float(shadow, 0))
        costo_marginal_ton = shadow_abs * 1000
        impacto_pct = (shadow_abs / precio_kg_formula * 100) if precio_kg_formula > 0 else 0

        if activa or shadow_abs > 1e-10:
            limiting_rows.append(
                {
                    "Nutriente": vals.get("item", ""),
                    "Tipo": vals.get("tipo", ""),
                    "Activa": "Sí" if activa else "No",
                    "Shadow USD/kg": shadow,
                    "Costo marginal USD/ton": costo_marginal_ton,
                    "Impacto relativo (%)": impacto_pct,
                    "Slack": slack,
                }
            )

    if limiting_rows:
        with st.expander("Diagnóstico avanzado de nutrientes limitantes", expanded=False):
            df_lim = pd.DataFrame(limiting_rows).sort_values("Impacto relativo (%)", ascending=False)
            render_table(
                df_lim,
                column_config={
                    "Shadow USD/kg": st.column_config.NumberColumn("Shadow USD/kg", format="%.6f"),
                    "Costo marginal USD/ton": st.column_config.NumberColumn("Costo marginal USD/ton", format="$%.4f"),
                    "Impacto relativo (%)": st.column_config.NumberColumn("Impacto relativo (%)", format="%.4f%%"),
                    "Slack": st.column_config.NumberColumn("Slack", format="%.6f"),
                },
            )
            st.caption(
                "El costo marginal indica cuánto aumentaría el costo por tonelada si se exige +1 unidad del nutriente."
            )

    # 7) Ratios (si existen)
    if ratios:
        with st.expander("Cumplimiento de restricciones de ratios", expanded=False):
            ratio_warnings = _ratio_denominator_min_warnings(ratios, req_input)
            if ratio_warnings:
                render_card(
                    "Advertencia sobre ratios",
                    "Algunos ratios tienen denominador sin mínimo explícito: " + "; ".join(ratio_warnings),
                    variant="warning",
                )

            ratio_rows = []
            for ratio in ratios:
                eval_r = _evaluate_ratio_status(ratio, nutritional_values, req_input)
                ratio_rows.append(
                    {
                        "Ratio definido": f"{ratio.get('numerador')} / {ratio.get('denominador')} {ratio.get('operador')} {ratio.get('valor')}",
                        "Valor calculado": f"{eval_r['calculado']:.3f}" if eval_r["calculado"] is not None else "N/A",
                        "Cumplimiento": eval_r["estado"],
                        "Detalle": eval_r["detalle"],
                    }
                )
            render_table(pd.DataFrame(ratio_rows))

    # 8) Diagnóstico LP completo
    if constraint_diagnostics:
        with st.expander("Diagnóstico LP completo", expanded=False):
            diag_rows = []
            for cname, vals in constraint_diagnostics.items():
                diag_rows.append(
                    {
                        "Restricción": cname,
                        "Tipo": vals.get("tipo", ""),
                        "Item": vals.get("item", ""),
                        "Shadow price": vals.get("shadow_price", None),
                        "Slack": vals.get("slack", None),
                        "Activa": "Sí" if vals.get("activa") else "No",
                    }
                )

            diag_df = pd.DataFrame(diag_rows)

            tipos = sorted(diag_df["Tipo"].dropna().unique().tolist()) if not diag_df.empty else []
            tipo_filtro = st.multiselect(
                "Filtrar por tipo de restricción",
                tipos,
                default=tipos,
                key=f"results_lp_filter_{species}",
            )

            if tipo_filtro:
                diag_df = diag_df[diag_df["Tipo"].isin(tipo_filtro)]

            render_table(
                diag_df,
                column_config={
                    "Shadow price": st.column_config.NumberColumn("Shadow price", format="%.6f"),
                    "Slack": st.column_config.NumberColumn("Slack", format="%.6f"),
                },
                height=350,
            )

            restricciones_activas = sum(1 for v in constraint_diagnostics.values() if v.get("activa"))
            st.caption(
                f"Restricciones activas: {restricciones_activas}/{len(constraint_diagnostics)}. "
                "Una restricción activa tiene holgura cercana a cero y puede condicionar la solución."
            )
