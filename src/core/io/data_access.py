import pandas as pd
import streamlit as st

from src.core.formulation.presets.data import PRESETS


def load_ingredients(uploaded_file):
    """
    Carga matriz de ingredientes desde CSV/XLSX.
    Mantiene compatibilidad con el comportamiento legacy.
    """
    if uploaded_file is None:
        return pd.DataFrame()

    filename = uploaded_file.name.lower()

    try:
        if filename.endswith(".xlsx"):
            df = pd.read_excel(uploaded_file)
        elif filename.endswith(".csv"):
            # compatibilidad con separador ; y distintas codificaciones
            try:
                df = pd.read_csv(uploaded_file, delimiter=";", encoding="latin1")
            except UnicodeDecodeError:
                df = pd.read_csv(uploaded_file, delimiter=";", encoding="utf-8")
            except Exception:
                # fallback común
                uploaded_file.seek(0)
                df = pd.read_csv(uploaded_file)
        else:
            st.error("Formato de archivo de ingredientes no soportado. Usa .csv o .xlsx")
            return pd.DataFrame()

    except Exception as e:
        st.error(f"Error al cargar ingredientes: {e}")
        return pd.DataFrame()

    df.columns = [str(c).strip() for c in df.columns]
    return df


def get_nutrient_list(ingredients_df):
    """
    Devuelve lista de nutrientes disponibles excluyendo columnas base.
    """
    if ingredients_df is None or ingredients_df.empty:
        return []

    exclude_cols = {"Ingrediente", "precio", "Materia seca (%)"}
    return [col for col in ingredients_df.columns if col not in exclude_cols]


def get_preset_requirements(especie, etapa):
    """
    Retorna requerimientos preset por especie/etapa.
    Formato:
      {nutriente: {"min": x, "max": y?}}
    """
    return PRESETS.get(especie, {}).get(etapa, {})
