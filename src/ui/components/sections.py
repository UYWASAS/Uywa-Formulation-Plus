import streamlit as st


def render_section(title: str, subtitle: str | None = None):
    subtitle_html = f"<div class='uywa-section-subtitle'>{subtitle}</div>" if subtitle else ""
    st.markdown(
        f"""
        <h3 class="uywa-section-title">{title}</h3>
        {subtitle_html}
        """,
        unsafe_allow_html=True,
    )
