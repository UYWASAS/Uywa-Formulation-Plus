import io

import pandas as pd
import streamlit as st

from src.core.formulation.presets.data import PRESETS


NON_NUTRIENT_COLUMNS = {
    "ingrediente", "ingredient", "nombre", "name", "marca", "brand",
    "precio", "price", "costo", "cost", "unidad", "unit",
    "categoria", "category", "grupo", "group", "tipo", "type",
    "origen", "origin", "fuente", "source", "observacion",
    "observaciones", "nota", "notas", "codigo", "código", "id",
}


def _normalize_column_name(value) -> str:
    return str(value).strip()


def _read_csv_robust(uploaded_file) -> pd.DataFrame:
    """Lee CSV con detección automática de separador y codificación."""
    try:
        raw = uploaded_file.getvalue()
    except Exception:
        uploaded_file.seek(0)
        raw = uploaded_file.read()

    attempts = [
        {"sep": None, "engine": "python", "encoding": "utf-8-sig"},
        {"sep": None, "engine": "python", "encoding": "latin1"},
        {"sep": ";", "encoding": "utf-8-sig"},
        {"sep": ",", "encoding": "utf-8-sig"},
        {"sep": "\t", "encoding": "utf-8-sig"},
        {"sep": ";", "encoding": "latin1"},
        {"sep": ",", "encoding": "latin1"},
    ]

    best = pd.DataFrame()
    for kwargs in attempts:
        try:
            df = pd.read_csv(io.BytesIO(raw), **kwargs)
            if df is not None and len(df.columns) > len(best.columns):
                best = df
            if len(df.columns) > 1:
                return df
        except Exception:
            continue
    return best


def load_ingredients(uploaded_file):
    """
    Carga una matriz de ingredientes desde CSV o XLSX sin limitar columnas.
    Los presets por especie no intervienen en esta etapa.
    """
    if uploaded_file is None:
        return pd.DataFrame()

    filename = str(getattr(uploaded_file, "name", "")).lower()

    try:
        if filename.endswith(".xlsx") or filename.endswith(".xls"):
            uploaded_file.seek(0)
            df = pd.read_excel(uploaded_file)
        elif filename.endswith(".csv"):
            df = _read_csv_robust(uploaded_file)
        else:
            st.error("Formato de archivo de ingredientes no soportado. Usa .csv, .xls o .xlsx")
            return pd.DataFrame()
    except Exception as exc:
        st.error(f"Error al cargar ingredientes: {exc}")
        return pd.DataFrame()

    if df is None or df.empty:
        st.error("La matriz no contiene datos legibles.")
        return pd.DataFrame()

    df = df.copy()
    df.columns = [_normalize_column_name(c) for c in df.columns]
    df = df.loc[:, ~pd.Index(df.columns).duplicated(keep="first")]
    return df


def get_nutrient_list(ingredients_df):
    """
    Devuelve todos los nutrientes numéricos disponibles en la matriz activa.

    La lista depende exclusivamente de las columnas del archivo cargado; no
    depende de especie, etapa ni preset. Se excluyen únicamente columnas de
    identificación/metadatos.
    """
    if ingredients_df is None or ingredients_df.empty:
        return []

    nutrients = []
    for col in ingredients_df.columns:
        name = _normalize_column_name(col)
        if not name or name.lower() in NON_NUTRIENT_COLUMNS:
            continue

        numeric = pd.to_numeric(ingredients_df[col], errors="coerce")
        if numeric.notna().any():
            nutrients.append(name)

    return nutrients


def get_preset_requirements(especie, etapa):
    """Retorna requerimientos preset por especie y etapa."""
    return PRESETS.get(especie, {}).get(etapa, {})
