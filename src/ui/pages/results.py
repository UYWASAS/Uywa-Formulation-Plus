import streamlit as st
import pandas as pd

from src.ui.components.sections import render_section
from src.ui.components.cards import render_card, render_metric_card
from src.ui.components.tables import render_table


SPECIES_KEYS = {
    "Aves": {
        "result": "last_result_aves",
        "ingredients": ["ingredients_df", "ingredients_df_aves"],
        "req": ["aves_req_input", "req_input", "requirements_aves", "requirements"],
        "selected_nutrients": ["aves_nutrients_selected", "nutrientes_seleccionados", "nutrientes_seleccionados_aves"],
        "ratios": ["aves_ratios", "ratios", "ratios_aves"],
        "last_inputs": ["aves_last_inputs", "last_inputs_aves"],
    },
    "Cerdos": {
        "result": "last_result_cerdos",
        "ingredients": ["ingredients_df_cerdos", "ingredients_df"],
        "req": ["req_input_cerdos", "cerdos_req_input", "requirements_cerdos"],
        "selected_nutrients": ["nutrientes_seleccionados_cerdos", "cerdos_nutrients_selected"],
        "ratios": ["ratios_cerdos", "cerdos_ratios"],
        "last_inputs": ["cerdos_last_inputs", "last_inputs_cerdos"],
    },
    "Rumiantes": {
        "result": "last_result_rumiantes",
        "ingredients": ["ingredients_df_rumiantes", "ingredients_df"],
        "req": ["req_input_rumiantes", "rumiantes_req_input", "requirements_rumiantes"],
        "selected_nutrients": ["nutrientes_seleccionados_rumiantes", "rumiantes_nutrients_selected"],
        "ratios": ["ratios_rumiantes", "rumiantes_ratios"],
        "last_inputs": ["rumiantes_last_inputs", "last_inputs_rumiantes"],
    },
}


NON_NUTRIENT_COLUMNS = {
    "Ingrediente", "ingrediente", "Ingredient", "ingredient",
    "precio", "Precio", "price", "Price", "USD/kg", "Costo", "costo",
    "Materia seca (%)", "MS (%)",
}


def _safe_float(v, default=0.0):
    try:
        if v is None or pd.isna(v):
            return default
        if isinstance(v, str):
            v = v.strip().replace("%", "").replace(",", ".")
            if v == "":
                return default
        return float(v)
    except Exception:
        return default


def _get_first_state(keys, default=None):
    if isinstance(keys, str):
        keys = [keys]
    for key in keys or []:
        value = st.session_state.get(key)
        if value is not None:
            if isinstance(value, pd.DataFrame) and value.empty:
                continue
            if isinstance(value, (list, dict)) and len(value) == 0:
                continue
            return value
    return default


def _first_success_species():
    for sp, cfg in SPECIES_KEYS.items():
        r = st.session_state.get(cfg["result"])
        if r and r.get("success"):
            return sp
    return None


def _is_numeric_nutrient_column(df, col):
    if col in NON_NUTRIENT_COLUMNS or str(col).startswith("Unnamed"):
        return False
    if df is None or df.empty or col not in df.columns:
        return False
    numeric = pd.to_numeric(df[col], errors="coerce")
    return numeric.notna().any()


def _matrix_nutrients(ingredients_df):
    if ingredients_df is None or not isinstance(ingredients_df, pd.DataFrame) or ingredients_df.empty:
        return []
    return [c for c in ingredients_df.columns if _is_numeric_nutrient_column(ingredients_df, c)]


def _unique_keep_order(values):
    out = []
    seen = set()
    for v in values or []:
        if v is None:
            continue
        v = str(v)
        if v and v not in seen:
            out.append(v)
            seen.add(v)
    return out


def _normalize_requirements(req_input, compliance_data=None):
    req = {}

    if isinstance(req_input, dict):
        for nut, vals in req_input.items():
            if isinstance(vals, dict):
                req[str(nut)] = {
                    "min": _safe_float(vals.get("min", vals.get("Min", vals.get("mínimo", 0))), 0),
                    "max": _safe_float(vals.get("max", vals.get("Max", vals.get("máximo", 0))), 0),
                }
            else:
                req[str(nut)] = {"min": _safe_float(vals, 0), "max": 0.0}

    if isinstance(compliance_data, list):
        for row in compliance_data:
            if not isinstance(row, dict):
                continue
            nut = row.get("Nutriente") or row.get("nutriente") or row.get("item")
            if not nut:
                continue
            req.setdefault(str(nut), {"min": 0.0, "max": 0.0})
            for k_min in ["Min", "Mínimo", "min", "minimum"]:
                if k_min in row:
                    req[str(nut)]["min"] = _safe_float(row.get(k_min), req[str(nut)]["min"])
                    break
            for k_max in ["Max", "Máximo", "max", "maximum"]:
                if k_max in row:
                    req[str(nut)]["max"] = _safe_float(row.get(k_max), req[str(nut)]["max"])
                    break
    return req


def _estado_texto(minimo, maximo, obtenido):
    if obtenido is None or pd.isna(obtenido):
        return "No evaluable"
    if maximo and obtenido > maximo:
        return "Exceso"
    if minimo and obtenido < minimo:
        return "Deficiente"
    if minimo or maximo:
        return "Cumple"
    return "Sin restricción"


def _estado_icono(estado):
    return {
        "Cumple": "✅ Cumple",
        "Deficiente": "⚠️ Deficiente",
        "Exceso": "⚠️ Exceso",
        "Sin restricción": "Sin restricción",
        "No evaluable": "No evaluable",
    }.get(estado, estado)


def _logrado_pct(minimo, maximo, obtenido):
    if obtenido is None or pd.isna(obtenido):
        return None
    if minimo and minimo > 0:
        return (obtenido / minimo) * 100
    if maximo and maximo > 0:
        return (maximo / obtenido) * 100 if obtenido > 0 else None
    return None


def _impact_label(impacto_pct):
    impacto_pct = _safe_float(impacto_pct, 0)
    if impacto_pct >= 1.0:
        return "Alto"
    if impacto_pct >= 0.1:
        return "Medio"
    if impacto_pct > 0:
        return "Bajo"
    return "Sin impacto"


def _get_limiting_ingredient(nutriente, diet, ingredients_df):
    try:
        if ingredients_df is None or ingredients_df.empty:
            return "—"
        if nutriente not in ingredients_df.columns or "Ingrediente" not in ingredients_df.columns:
            return "—"

        aportes = {}
        total = 0.0
        for ing, pct in (diet or {}).items():
            row = ingredients_df[ingredients_df["Ingrediente"].astype(str) == str(ing)]
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


def _constraint_for_nutrient(constraint_diagnostics, nutrient):
    if not isinstance(constraint_diagnostics, dict):
        return {}
    candidates = []
    for _, vals in constraint_diagnostics.items():
        if not isinstance(vals, dict):
            continue
        if str(vals.get("item", "")) != str(nutrient):
            continue
        if vals.get("tipo") in ["Mínimo nutricional", "Máximo nutricional"]:
            candidates.append(vals)
    if not candidates:
        return {}
    return max(candidates, key=lambda x: abs(_safe_float(x.get("shadow_price", 0), 0)))


def _build_live_requirement_table(nutrients, req_map, nutritional_values, constraint_diagnostics, diet, ingredients_df, formula_cost_kg):
    rows = []
    for nut in nutrients:
        vals = req_map.get(nut, {}) if isinstance(req_map, dict) else {}
        minimo = _safe_float(vals.get("min", 0), 0)
        maximo = _safe_float(vals.get("max", 0), 0)
        obtenido = nutritional_values.get(nut, None)
        if obtenido is not None:
            obtenido = _safe_float(obtenido, None)

        estado = _estado_texto(minimo, maximo, obtenido)
        logrado = _logrado_pct(minimo, maximo, obtenido)

        diag = _constraint_for_nutrient(constraint_diagnostics, nut)
        shadow_abs = abs(_safe_float(diag.get("shadow_price", 0), 0)) if diag else 0.0
        costo_marginal_ton = shadow_abs * 1000
        impacto_rel = (shadow_abs / formula_cost_kg * 100) if formula_cost_kg > 0 else 0.0

        rows.append({
            "Nutriente": nut,
            "Min": minimo if minimo > 0 else None,
            "Max": maximo if maximo > 0 else None,
            "Obtenido": obtenido,
            "% Logrado": logrado,
            "Estado": _estado_icono(estado),
            "Impacto relativo": impacto_rel,
            "Costo marginal": costo_marginal_ton,
            "Impacto": _impact_label(impacto_rel),
            "Ing. asociado": _get_limiting_ingredient(nut, diet, ingredients_df),
            "Restricción activa": "Sí" if diag.get("activa") else "No",
            "Slack": diag.get("slack") if diag else None,
        })
    return pd.DataFrame(rows)


def _ratio_denominator_min_warnings(ratios, requirements_map):
    warnings = []
    for ratio in ratios or []:
        den = ratio.get("denominador")
        den_min = _safe_float((requirements_map or {}).get(den, {}).get("min", 0), 0)
        if den and den_min <= 0:
            warnings.append(f"{ratio.get('numerador')} / {den} {ratio.get('operador')} {ratio.get('valor')}")
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

    den_min = _safe_float((requirements_map or {}).get(den, {}).get("min", 0), 0)
    warning_min_msg = (
        f"Nota: este ratio no fuerza por sí solo un mínimo explícito para '{den}'. "
        f"Define un mínimo de '{den}' para asegurar un balance nutricional real."
    )

    if den_val is None:
        detalle = f"Nutriente '{den}' no disponible."
    elif abs(_safe_float(den_val, 0)) <= 1e-12:
        cumple = False
        detalle = f"Ratio degenerado: denominador '{den}' = 0. {warning_min_msg}"
    elif num_val is None:
        detalle = f"Nutriente '{num}' no disponible."
    else:
        num_val = _safe_float(num_val, 0)
        den_val = _safe_float(den_val, 0)
        calculado = num_val / den_val
        if op == "=":
            cumple = abs(calculado - val) < 1e-2
        elif op == ">=":
            cumple = calculado >= val - 1e-2
        elif op == "<=":
            cumple = calculado <= val + 1e-2
        detalle = f"Calculado: {num_val:.3f} / {den_val:.3f} = {calculado:.3f}"
        if den_min <= 0:
            detalle = f"{detalle}. {warning_min_msg}"

    estado = "Cumple" if cumple else ("No cumple" if cumple is False else "No evaluable")
    return {"calculado": calculado, "cumple": cumple, "detalle": detalle, "estado": estado}


def render():
    st.title("Resultados de la formulación")
    st.caption("Resumen ejecutivo, composición, economía, cumplimiento nutricional y diagnóstico avanzado.")

    available = [sp for sp, cfg in SPECIES_KEYS.items() if st.session_state.get(cfg["result"])]
    if not available:
        render_card("Sin resultados", "Aún no hay corridas guardadas.", variant="info")
        return

    default_sp = _first_success_species() or available[0]
    species = st.selectbox("Especie", options=available, index=available.index(default_sp), key="results_species_selector")
    cfg = SPECIES_KEYS[species]
    result = st.session_state.get(cfg["result"], {})

    if not result:
        render_card("Sin datos", f"No hay resultado para {species}.", variant="info")
        return

    if not result.get("success"):
        render_card("Última corrida no factible", result.get("message", "Sin detalle"), variant="danger")
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

    last_inputs = _get_first_state(cfg.get("last_inputs"), {}) or {}
    req_input = _get_first_state(cfg["req"], None)
    if req_input is None:
        req_input = last_inputs.get("requirements", {}) if isinstance(last_inputs, dict) else {}
    req_map = _normalize_requirements(req_input, compliance_data)

    nutrients_selected = _get_first_state(cfg["selected_nutrients"], None)
    if not nutrients_selected and isinstance(last_inputs, dict):
        nutrients_selected = last_inputs.get("nutrient_list") or last_inputs.get("nutrientes_seleccionados")

    ingredients_df = _get_first_state(cfg["ingredients"], None)
    matrix_nutrients = _matrix_nutrients(ingredients_df)

    nutrients_selected = _unique_keep_order(
        list(nutrients_selected or [])
        + list(req_map.keys())
        + list(nutritional_values.keys())
    )
    nutrients_selected = [n for n in nutrients_selected if (not matrix_nutrients or n in matrix_nutrients or n in nutritional_values or n in req_map)]

    ratios = _get_first_state(cfg["ratios"], []) or []
    if isinstance(last_inputs, dict) and not ratios:
        ratios = last_inputs.get("ratios", []) or []

    if not diet:
        render_card("Sin composición de dieta", "No se encontraron ingredientes activos en el resultado.", variant="warning")
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
    render_table(df_diet, column_config={"Inclusión (%)": st.column_config.NumberColumn("Inclusión (%)", format="%.3f")})

    # 3) Economía de ingredientes
    if ingredients_df is not None and not ingredients_df.empty and {"Ingrediente", "precio"}.issubset(set(ingredients_df.columns)):
        render_section("Economía de ingredientes", "Contribución económica de cada ingrediente al costo por tonelada.")
        econ_rows = []
        total_cost_ton_calc = 0.0
        for ing, inclusion in diet.items():
            row_match = ingredients_df[ingredients_df["Ingrediente"].astype(str) == str(ing)]
            if row_match.empty:
                continue
            precio_ing = _safe_float(row_match.iloc[0].get("precio", 0), 0)
            inclusion = _safe_float(inclusion, 0)
            costo_ton = precio_ing * inclusion / 100 * 1000
            total_cost_ton_calc += costo_ton
            econ_rows.append({
                "Ingrediente": ing,
                "Inclusión (%)": inclusion,
                "Precio ingrediente (USD/kg)": precio_ing,
                "Costo aportado (USD/ton)": costo_ton,
            })

        if econ_rows:
            econ_df = pd.DataFrame(econ_rows).sort_values("Costo aportado (USD/ton)", ascending=False)
            econ_df["Participación en costo (%)"] = econ_df["Costo aportado (USD/ton)"] / total_cost_ton_calc * 100 if total_cost_ton_calc > 0 else 0
            top_ing = econ_df.iloc[0]
            top3 = econ_df.head(3)["Ingrediente"].tolist()
            render_card(
                "Principal componente económico",
                f"{top_ing['Ingrediente']} aporta ${top_ing['Costo aportado (USD/ton)']:.2f}/ton, equivale al {top_ing['Participación en costo (%)']:.1f}% del costo estimado. Mayor impacto económico: {', '.join(top3)}.",
                variant="info",
            )
            with st.expander("Ver detalle económico por ingrediente", expanded=True):
                render_table(econ_df, column_config={
                    "Inclusión (%)": st.column_config.NumberColumn("Inclusión (%)", format="%.3f"),
                    "Precio ingrediente (USD/kg)": st.column_config.NumberColumn("Precio ingrediente (USD/kg)", format="$%.4f"),
                    "Costo aportado (USD/ton)": st.column_config.NumberColumn("Costo aportado (USD/ton)", format="$%.2f"),
                    "Participación en costo (%)": st.column_config.NumberColumn("Participación en costo (%)", format="%.2f%%"),
                })

    # 4) Tabla de requerimientos y análisis en vivo
    render_section("Tabla de requerimientos y análisis en vivo", "Min y Max son editables en el formulador. Las demás columnas son analíticas e informativas.")
    if not nutrients_selected:
        nutrients_selected = _unique_keep_order(list(nutritional_values.keys()) + list(req_map.keys()) + matrix_nutrients)

    live_df = _build_live_requirement_table(
        nutrients=nutrients_selected,
        req_map=req_map,
        nutritional_values=nutritional_values,
        constraint_diagnostics=constraint_diagnostics,
        diet=diet,
        ingredients_df=ingredients_df,
        formula_cost_kg=precio_kg,
    )
    render_table(
        live_df,
        column_config={
            "Min": st.column_config.NumberColumn("Min", format="%.3f"),
            "Max": st.column_config.NumberColumn("Max", format="%.3f"),
            "Obtenido": st.column_config.NumberColumn("Obtenido", format="%.3f"),
            "% Logrado": st.column_config.NumberColumn("% Logrado", format="%.1f%%"),
            "Impacto relativo": st.column_config.NumberColumn("Impacto relativo", format="%.4f%%"),
            "Costo marginal": st.column_config.NumberColumn("Costo marginal", format="$%.4f/ton"),
            "Slack": st.column_config.NumberColumn("Slack", format="%.6f"),
        },
        height=360,
    )
    st.caption("Lectura económica: el impacto relativo indica la presión sobre el costo total; el costo marginal traduce ese efecto a USD/ton. Comparar nutrientes con unidades distintas requiere cautela.")

    # 5) Diagnóstico nutricional automático
    auto_rows = []
    for _, vals in constraint_diagnostics.items():
        if not isinstance(vals, dict) or vals.get("tipo") != "Mínimo nutricional":
            continue
        nutrient = vals.get("item", "")
        shadow = vals.get("shadow_price", None)
        activa = vals.get("activa", False)
        if shadow is None:
            continue
        shadow_abs = abs(_safe_float(shadow, 0))
        impacto_pct = (shadow_abs / precio_kg * 100) if precio_kg > 0 else 0
        costo_marginal_ton = shadow_abs * 1000
        if activa or shadow_abs > 1e-10:
            auto_rows.append({"nutriente": nutrient, "impacto_pct": impacto_pct, "costo_marginal_ton": costo_marginal_ton, "shadow": shadow_abs})

    if auto_rows:
        auto_rows = sorted(auto_rows, key=lambda x: x["impacto_pct"], reverse=True)
        top = auto_rows[0]
        ing_asociado = _get_limiting_ingredient(top["nutriente"], diet, ingredients_df) if ingredients_df is not None and not ingredients_df.empty else "—"
        render_section("Diagnóstico nutricional automático", "Interpretación económica de los nutrientes que condicionan la fórmula.")
        render_card(
            "Nutriente principal",
            f"El nutriente que más condiciona económicamente la fórmula es {top['nutriente']}. Costo marginal estimado: ${top['costo_marginal_ton']:.2f}/ton. Impacto relativo: {top['impacto_pct']:.3f}%. Ingrediente asociado: {ing_asociado}.",
            variant="info",
        )
        if len(auto_rows) > 1:
            ranking_df = pd.DataFrame([{
                "Orden": i + 1,
                "Nutriente": row["nutriente"],
                "Costo marginal USD/ton": row["costo_marginal_ton"],
                "Impacto relativo (%)": row["impacto_pct"],
            } for i, row in enumerate(auto_rows[:10])])
            with st.expander("Ver ranking de nutrientes con impacto económico", expanded=True):
                render_table(ranking_df, column_config={
                    "Costo marginal USD/ton": st.column_config.NumberColumn("Costo marginal USD/ton", format="$%.2f"),
                    "Impacto relativo (%)": st.column_config.NumberColumn("Impacto relativo (%)", format="%.3f%%"),
                })

    # 6) Diagnóstico avanzado de nutrientes limitantes
    limiting_rows = []
    for _, vals in constraint_diagnostics.items():
        if not isinstance(vals, dict) or vals.get("tipo") not in ["Mínimo nutricional", "Máximo nutricional"]:
            continue
        shadow = vals.get("shadow_price", None)
        if shadow is None:
            continue
        shadow_abs = abs(_safe_float(shadow, 0))
        costo_marginal_ton = shadow_abs * 1000
        impacto_pct = (shadow_abs / precio_kg * 100) if precio_kg > 0 else 0
        if vals.get("activa", False) or shadow_abs > 1e-10:
            limiting_rows.append({
                "Nutriente": vals.get("item", ""),
                "Tipo": vals.get("tipo", ""),
                "Activa": "Sí" if vals.get("activa") else "No",
                "Shadow USD/kg": shadow,
                "Costo marginal USD/ton": costo_marginal_ton,
                "Impacto relativo (%)": impacto_pct,
                "Slack": vals.get("slack", None),
            })

    if limiting_rows:
        with st.expander("Diagnóstico avanzado de nutrientes limitantes", expanded=False):
            df_lim = pd.DataFrame(limiting_rows).sort_values("Impacto relativo (%)", ascending=False)
            render_table(df_lim, column_config={
                "Shadow USD/kg": st.column_config.NumberColumn("Shadow USD/kg", format="%.6f"),
                "Costo marginal USD/ton": st.column_config.NumberColumn("Costo marginal USD/ton", format="$%.4f"),
                "Impacto relativo (%)": st.column_config.NumberColumn("Impacto relativo (%)", format="%.4f%%"),
                "Slack": st.column_config.NumberColumn("Slack", format="%.6f"),
            })
            st.caption("El costo marginal indica cuánto aumentaría el costo por tonelada si se exige +1 unidad del nutriente.")

    # 7) Ratios
    if ratios:
        with st.expander("Cumplimiento de restricciones de ratios", expanded=False):
            ratio_warnings = _ratio_denominator_min_warnings(ratios, req_map)
            if ratio_warnings:
                render_card("Advertencia sobre ratios", "Algunos ratios tienen denominador sin mínimo explícito: " + "; ".join(ratio_warnings), variant="warning")
            ratio_rows = []
            for ratio in ratios:
                eval_r = _evaluate_ratio_status(ratio, nutritional_values, req_map)
                ratio_rows.append({
                    "Ratio definido": f"{ratio.get('numerador')} / {ratio.get('denominador')} {ratio.get('operador')} {ratio.get('valor')}",
                    "Valor calculado": f"{eval_r['calculado']:.3f}" if eval_r["calculado"] is not None else "N/A",
                    "Cumplimiento": eval_r["estado"],
                    "Detalle": eval_r["detalle"],
                })
            render_table(pd.DataFrame(ratio_rows))

    # 8) Diagnóstico LP completo
    if constraint_diagnostics:
        with st.expander("Diagnóstico LP completo", expanded=False):
            diag_rows = []
            for cname, vals in constraint_diagnostics.items():
                if not isinstance(vals, dict):
                    continue
                diag_rows.append({
                    "Restricción": cname,
                    "Tipo": vals.get("tipo", ""),
                    "Item": vals.get("item", ""),
                    "Shadow price": vals.get("shadow_price", None),
                    "Slack": vals.get("slack", None),
                    "Activa": "Sí" if vals.get("activa") else "No",
                })
            diag_df = pd.DataFrame(diag_rows)
            tipos = sorted(diag_df["Tipo"].dropna().unique().tolist()) if not diag_df.empty else []
            tipo_filtro = st.multiselect("Filtrar por tipo de restricción", tipos, default=tipos, key=f"results_lp_filter_{species}")
            if tipo_filtro:
                diag_df = diag_df[diag_df["Tipo"].isin(tipo_filtro)]
            render_table(diag_df, column_config={
                "Shadow price": st.column_config.NumberColumn("Shadow price", format="%.6f"),
                "Slack": st.column_config.NumberColumn("Slack", format="%.6f"),
            }, height=350)
            restricciones_activas = sum(1 for v in constraint_diagnostics.values() if isinstance(v, dict) and v.get("activa"))
            st.caption(f"Restricciones activas: {restricciones_activas}/{len(constraint_diagnostics)}. Una restricción activa tiene holgura cercana a cero y puede condicionar la solución.")
