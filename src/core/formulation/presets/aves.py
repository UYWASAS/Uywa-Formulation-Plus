import streamlit as st
import pandas as pd

from src.core.io.data_access import load_ingredients, get_nutrient_list
from src.core.formulation.presets import get_stage_preset
from src.adapters.optimization_adapter import OptimizationAdapter


def render():
    st.title("Formulador · Aves")
    st.caption("MVP modular. Conserva el motor de cálculo actual (DietFormulator).")

    up = st.file_uploader(
        "Matriz de ingredientes (.csv/.xlsx)",
        type=["csv", "xlsx"],
        key="aves_matriz_upload",
    )

    df = load_ingredients(up)
    if df is None or df.empty:
        st.info("Carga una matriz para comenzar.")
        return

    if "Ingrediente" not in df.columns or "precio" not in df.columns:
        st.error("La matriz debe contener columnas 'Ingrediente' y 'precio'.")
        return

    st.success(f"Matriz cargada: {len(df)} ingredientes.")

    etapas_aves = list({
        "Broiler Iniciación",
        "Broiler Crecimiento",
        "Broiler Cebo",
        "Broiler Acabado",
        "Pollita Recría 0-5",
        "Pollita Recría 5-10",
        "Pollita Recría 10-17",
        "Pollita Inicio Puesta",
        "Ponedora Pre-Pico",
        "Ponedora Inicio Postura",
        "Ponedora Final Postura",
        "Ponedora Problemas Cascara",
    })

    etapa = st.selectbox("Etapa (Aves)", sorted(etapas_aves), key="aves_etapa")
    nutrientes = get_nutrient_list(df)

    preset = get_stage_preset("Aves", etapa)
    nutrientes_validos = [n for n in preset.keys() if n in nutrientes]

    st.write(f"Nutrientes preset compatibles: {len(nutrientes_validos)}")

    selected_nutrients = st.multiselect(
        "Nutrientes a usar",
        options=nutrientes,
        default=nutrientes_validos[: min(12, len(nutrientes_validos))],
        key="aves_nutrients",
    )

    req = {}
    for nut in selected_nutrients:
        p = preset.get(nut, {})
        req[nut] = {
            "min": float(p.get("min", 0) or 0),
            "max": float(p.get("max", 0) or 0),
        }

    if st.button("Formular dieta (Aves)", key="btn_solve_aves"):
        adapter = OptimizationAdapter()
        result = adapter.solve(
            ingredients_df=df,
            nutrient_list=selected_nutrients,
            requirements=req,
            limits={"min": {}, "max": {}},
            selected_species="Aves",
            selected_stage=etapa,
            ratios=[],
        )

        st.session_state["last_result_aves"] = result

    result = st.session_state.get("last_result_aves")
    if result:
        if result.get("success"):
            st.success("Formulación exitosa.")
            st.dataframe(
                pd.DataFrame(
                    list(result.get("diet", {}).items()),
                    columns=["Ingrediente", "Inclusión (%)"],
                ),
                use_container_width=True,
            )
            st.metric("Costo total (base 100 kg)", f"${result.get('cost', 0):.2f}")
        else:
            st.error(result.get("message", "No se pudo formular."))
            diag = result.get("infeasibility_diagnostics", [])
            if diag:
                st.write("Diagnóstico preliminar:")
                st.dataframe(pd.DataFrame(diag), use_container_width=True)
