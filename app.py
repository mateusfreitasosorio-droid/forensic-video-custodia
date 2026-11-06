"""
FORENSIC//VIDEO — esteira de custódia de vídeos forenses (interface Streamlit).

Como rodar:
    .venv\\Scripts\\python.exe -m streamlit run app.py

Este arquivo só monta a aplicação: configuração, tema e navegação entre as
páginas, que ficam em paginas/. A lógica de custódia fica em src/.
"""

import streamlit as st

import ui

st.set_page_config(page_title="FORENSIC//VIDEO", page_icon="🛡️", layout="wide")
ui.aplicar_tema()
ui.ajustar_pagina()

st.sidebar.markdown(
    "<div style='color:#00ff9c;font-weight:700;letter-spacing:.15em;"
    "text-shadow:0 0 6px rgba(0,255,156,.6)'>FORENSIC//VIDEO</div>"
    "<div style='color:#4a7a5a;font-size:.75rem'>cadeia de custódia · merkle · log encadeado</div>",
    unsafe_allow_html=True,
)

st.navigation([
    st.Page("paginas/custodia.py", title="Custódia", icon="🛡️", default=True),
    st.Page("paginas/comparar.py", title="Comparar", icon="🔍"),
    st.Page("paginas/log.py", title="Log de custódia", icon="⛓️"),
]).run()
