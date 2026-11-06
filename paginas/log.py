"""
Página LOG DE CUSTÓDIA: a corrente completa de eventos, com verificação.

Também mostra o hash do último evento, que deve ser ANCORADO fora da máquina
(anotado no laudo, por exemplo): é o que impede que o log seja reescrito por
inteiro sem que se perceba.
"""

import json

import streamlit as st

import ui
from src.custody_log import ler_eventos, verificar_corrente
from src.integrity import NOME_LOG

ui.cabecalho(f"cat evidencias/{NOME_LOG} | verificar", "Log de custódia",
             "Cada evento guarda o hash do anterior. Editar ou apagar um evento antigo quebra a corrente.")

caminho_log = f"{ui.PASTA_EVIDENCIAS}/{NOME_LOG}"
try:
    eventos = ler_eventos(caminho_log)
except ValueError as erro:  # uma linha que não é JSON válido
    ui.faixa("falha", "Log corrompido", str(erro))
    st.stop()
if not eventos:
    ui.faixa("info", "Log vazio", "Nenhuma evidência foi recebida ainda.")
    st.stop()

ok, mensagem, seq = verificar_corrente(eventos)
ui.faixa("ok" if ok else "falha", "Corrente válida" if ok else f"Corrente quebrada no evento #{seq}", mensagem)
ui.hashes([("Último evento", f'#{eventos[-1]["seq"]} · {eventos[-1]["timestamp_utc"]}'),
           ("Hash para ancorar no laudo", eventos[-1]["hash_evento"])])
st.caption("Anote o hash do último evento no laudo: ele resume toda a corrente até aqui.")

arquivos = sorted({e.get("dados", {}).get("arquivo", "—") for e in eventos})
filtro = st.selectbox("evidência", ["todas"] + arquivos)
visiveis = [e for e in eventos if filtro == "todas" or e.get("dados", {}).get("arquivo") == filtro]

st.dataframe(
    [{"#": e["seq"], "UTC": e["timestamp_utc"], "evento": e["evento"], "responsável": e["responsavel"],
      "evidência": e.get("dados", {}).get("arquivo", "—"),
      "resultado": {True: "íntegro", False: "FALHA"}.get(e.get("dados", {}).get("integro"), ""),
      "hash": e["hash_evento"][:16] + "…", "anterior": e["hash_anterior"][:16] + "…"}
     for e in reversed(visiveis)],
    hide_index=True, width="stretch",
)

escolhido = st.selectbox("ver evento completo", [e["seq"] for e in reversed(visiveis)], format_func=lambda s: f"#{s}")
st.code(json.dumps(next(e for e in eventos if e["seq"] == escolhido), ensure_ascii=False, indent=2), language="json")
