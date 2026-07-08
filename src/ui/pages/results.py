import streamlit as st
import pandas as pd

from src.ui.components.sections import render_section
from src.ui.components.cards import render_card, render_metric_card
from src.ui.components.tables import render_table


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
    st.title("Resultados")

    result, species = _get_last_result_any_species()

    if not result:
        render_card(
            "Sin resultados",
            "Aún no hay resultados guardados. Ejecuta una formulación en cualquier especie.",
            variant="warning",
        )
        return

    if not result.get("success"):
        render_card(
            "Último resultado con error",
            result.get("message", "No se pudo resolver la formulación."),
            variant="danger",
        )
        diag = result.get("infeasibility_diagnostics", [])
        if diag:
            with st.expander("Diagnóstico preliminar", expanded=False):
                st.dataframe(pd.DataFrame(diag), use_container_width=True)
        return

    diet = result.get("diet", {})
    cost = result.get("cost", 0)
    nutritional_values = result.get("nutritional_values", {})
    compliance_data = result.get("compliance_data", [])
    diagnostics = result.get("constraint_diagnostics", {})

    render_section("Resumen ejecutivo", f"Última especie formulada: {species}")

    c1, c2, c3 = st.columns(3)
    with c1:
        render_metric_card("Costo (100 kg)", f"${cost:.2f}", "Salida base del solver")
    with c2:
        render_metric_card("Costo por kg", f"${(cost/100):.4f}", "Estimado")
    with c3:
        render_metric_card("Ingredientes activos", str(len(diet)), "En solución")

    render_section("Composición óptima")
    df_diet = pd.DataFrame(list(diet.items()), columns=["Ingrediente", "Inclusión (%)"])
    if not df_diet.empty:
        df_diet = df_diet.sort_values("Inclusión (%)", ascending=False)
        render_table(
            df_diet,
            column_config={
                "Inclusión (%)": st.column_config.NumberColumn("Inclusión (%)", format="%.4f")
            },
        )
    else:
        st.info("La solución no tiene ingredientes con inclusión positiva.")

    render_section("Cumplimiento nutricional")
    df_comp = pd.DataFrame(compliance_data)
    if not df_comp.empty:
        render_table(df_comp)
    else:
        st.info("No hay datos de cumplimiento.")

    if nutritional_values:
        with st.expander("Valores nutricionales calculados", expanded=False):
            df_nut = pd.DataFrame(
                [{"Nutriente": k, "Valor": v} for k, v in nutritional_values.items()]
            )
            render_table(
                df_nut,
                column_config={"Valor": st.column_config.NumberColumn("Valor", format="%.6f")},
            )

    if diagnostics:
        with st.expander("Diagnóstico LP completo", expanded=False):
            rows = []
            for cname, vals in diagnostics.items():
                rows.append(
                    {
                        "Restricción": cname,
                        "Tipo": vals.get("tipo"),
                        "Item": vals.get("item"),
                        "Shadow": vals.get("shadow_price"),
                        "Slack": vals.get("slack"),
                        "Activa": vals.get("activa"),
                    }
                )
            df_diag = pd.DataFrame(rows)
            render_table(df_diag)
