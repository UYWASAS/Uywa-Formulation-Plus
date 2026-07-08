import streamlit as st
import pandas as pd


def render_table(df: pd.DataFrame, column_config=None, height=None):
    kwargs = {
        "data": df,
        "use_container_width": True,
        "hide_index": True,
    }
    if column_config is not None:
        kwargs["column_config"] = column_config
    if height is not None:
        kwargs["height"] = height

    st.dataframe(**kwargs)
