"""
Página COMPARAR: vídeo original (referência) × vídeo questionado.

Os dois vídeos ficam lado a lado. Se o questionado for diferente, a página
mostra ONDE: mapa de blocos, linha do tempo, tabela de regiões e os dois
players posicionados na região escolhida. A lógica está em src/comparacao.py.
"""

import os

import streamlit as st

import ui
from src.comparacao import comparar_videos
from src.video_metadata import extrair_metadados
from src.video_timeline import descrever

ui.cabecalho("comparar --original A --questionado B", "Original × questionado",
             "O original é a referência e precisa estar íntegro no próprio registro de custódia. "
             "O questionado é comparado bloco a bloco com ele; cada região diferente é localizada no tempo.")

col_o, col_q, col_r = st.columns([2, 2, 1])
with col_o:
    original = ui.escolher_video("original", "Original (referência)")
with col_q:
    questionado = ui.escolher_video("questionado", "Questionado")
with col_r:
    responsavel = ui.campo_responsavel("comparar")
    comparar = st.button("🔍 comparar", type="primary",
                         disabled=not (original and questionado and responsavel), width="stretch")

# Guardado na sessão: escolher outra região reexecuta a página, e isso não
# pode repetir a comparação nem gravar eventos duplicados no log.
chave = (original, questionado)
if comparar:
    try:
        with st.spinner("verificando o original · comparando bloco a bloco..."):
            st.session_state["comparacao"] = {"chave": chave, "r": comparar_videos(original, questionado, responsavel)}
    except (OSError, ValueError) as erro:
        ui.faixa("falha", "Não foi possível comparar", str(erro))
        st.stop()

guardado = st.session_state.get("comparacao")
if not guardado or guardado["chave"] != chave:
    st.stop()
r = guardado["r"]
st.divider()

if r["status"] == "referencia_invalida":
    ui.faixa("falha", "Comparação recusada",
             "O ORIGINAL não confere com o próprio registro de custódia. Uma referência adulterada não serve de "
             "base. Verifique-o na página Custódia para ver qual peça falhou.")
    st.stop()

# --- Veredito ------------------------------------------------------------------
q = r["questionado"]
if q["acao"] == "recebimento":
    ui.faixa("info", "Questionado registrado", f'Recebido agora · evento #{q["evento"]["seq"]} no log.')
elif not q["resultado"]["integro"]:
    ui.faixa("aviso", "Questionado mudou desde o próprio registro",
             "Ele já tinha registro de custódia e não confere mais com ele. A comparação usa o arquivo como está.")

regioes = r["regioes"]
if r["identicos"]:
    ui.faixa("ok", "Idênticos", "O questionado é igual, bit a bit, ao original (mesma raiz de Merkle).")
else:
    ui.faixa("falha", "Diferentes", f"{len(regioes)} região(ões) do questionado não conferem com o original.")
    if r["tamanho_questionado"] != r["tamanho_original"]:
        ui.faixa("aviso", "Tamanhos diferentes",
                 f'{r["tamanho_original"]:,} × {r["tamanho_questionado"]:,} bytes: houve inserção ou remoção. '
                 "Só o início da primeira região é confiável.".replace(",", "."))
    if not r["tem_mapa_original"]:
        ui.faixa("aviso", "Original sem mapa de tempo", "As regiões aparecem só em bytes.")

ui.mapa_de_blocos(-(-max(r["tamanho_original"], r["tamanho_questionado"]) // r["tamanho_bloco"]), regioes)

t_original = t_questionado = 0.0
if regioes:
    try:
        duracao = extrair_metadados(original)["duracao_segundos"]
    except (OSError, ValueError):
        duracao = None
    ui.barra_do_tempo(duracao, [x["tempo_original"] for x in regioes])
    ui.tabela_regioes(regioes, {"no original": ("tempo_original", False),
                                "no questionado": ("tempo_questionado", r["tempo_questionado_estimado"])})
    n = st.selectbox("posicionar os players na região", range(1, len(regioes) + 1),
                     format_func=lambda k: f"região {k} · {descrever(regioes[k - 1]['tempo_original'])}")
    escolhida = regioes[n - 1]

    def inicio(t):
        return max(t["inicio"], 0.0) if t and t.get("inicio") is not None else None

    t_original = inicio(escolhida["tempo_original"]) or 0.0
    t_questionado = inicio(escolhida["tempo_questionado"]) or t_original

# --- Players lado a lado ---------------------------------------------------------
p_o, p_q = st.columns(2)
with p_o:
    st.markdown(f"**ORIGINAL** · `{os.path.basename(original)}`")
    st.video(original, start_time=t_original)
with p_q:
    st.markdown(f"**QUESTIONADO** · `{os.path.basename(questionado)}`")
    st.video(questionado, start_time=t_questionado)

ui.hashes([("Raiz do original", r["merkle_raiz_original"]), ("Raiz do questionado", r["merkle_raiz_questionado"]),
           ("Comparação no log", f'evento #{r["evento"]["seq"]}')])
