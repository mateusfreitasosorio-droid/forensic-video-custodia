"""
Página CUSTÓDIA: recebe uma evidência nova ou verifica uma já registrada.

Fluxo: escolher o vídeo -> informar o responsável -> executar. O resultado
mostra o veredito, as quatro conferências, o mapa de blocos, as regiões
alteradas no tempo, os hashes, os metadados e o histórico no log.
"""

import os
import time

import streamlit as st

import ui
from src.custody_log import ler_eventos
from src.integrity import caminhos, receber_ou_verificar
from src.video_metadata import extrair_metadados

ui.cabecalho("custodia --receber-ou-verificar", "Custódia de evidência",
             "Primeira entrada: o vídeo é REGISTRADO (hash de cada bloco, raiz de Merkle, evento no log). "
             "Entradas seguintes: ele é VERIFICADO bit a bit, e qualquer alteração é localizada no tempo.")

col_sel, col_resp = st.columns([2, 1])
with col_sel:
    video = ui.escolher_video("custodia")
with col_resp:
    responsavel = ui.campo_responsavel("custodia")
    executar = st.button("▶ executar", type="primary", disabled=not (video and responsavel), width="stretch")

# O resultado fica na sessão para sobreviver às reexecuções da página
# (o Streamlit roda o script de novo a cada interação).
if executar:
    try:
        with st.spinner("lendo blocos · calculando hashes · conferindo o log..."):
            inicio = time.perf_counter()
            saida = receber_ou_verificar(video, responsavel)
            st.session_state["custodia"] = {"video": video, "saida": saida, "segundos": time.perf_counter() - inicio}
    except (OSError, ValueError) as erro:
        ui.faixa("falha", "Erro na esteira de custódia", str(erro))
        st.stop()

guardado = st.session_state.get("custodia")
if not guardado or guardado["video"] != video:
    st.stop()
saida, segundos = guardado["saida"], guardado["segundos"]
nome = os.path.basename(video)
st.divider()

# --- Veredito ------------------------------------------------------------------
if saida["acao"] == "recebimento":
    reg = saida["registro"]
    ui.faixa("ok", "Evidência registrada", f"{nome} recebida em {segundos:.2f}s · evento #{saida['evento']['seq']} no log")
    n_blocos, regioes, tamanho, tb = reg["n_blocos"], [], reg["tamanho_bytes"], reg["tamanho_bloco"]
    ui.hashes([("SHA-256 do arquivo", reg["sha256_arquivo"]), ("Raiz de Merkle", reg["merkle_raiz"])])
else:
    r = saida["resultado"]
    reg = r["registro"]
    if r["integro"]:
        ui.faixa("ok", "Íntegro", f"{nome} é idêntico, bit a bit, ao registrado · verificado em {segundos:.2f}s")
    else:
        ui.faixa("falha", "Falha na cadeia de custódia", "A evidência não pode ser atestada como íntegra.")
    ui.checklist([
        (r["video_confere"], "Vídeo", "confere bit a bit com o registro" if r["video_confere"] else "ALTERADO em relação ao registro"),
        (r["registro_coerente"], "Registro", "folhas coerentes com a raiz" if r["registro_coerente"] else "editado: folhas não batem com a raiz"),
        (r["registro_confere_log"], "Registro × log", "é o mesmo gravado no recebimento" if r["registro_confere_log"] else "difere do gravado no recebimento"),
        (r["log_integro"], "Log", r["log_mensagem"]),
    ])
    n_blocos, regioes, tamanho, tb = reg["n_blocos"], r["regioes"], r["tamanho_atual"], r["tamanho_bloco"]
    if r["tamanho_atual"] != r["tamanho_registrado"]:
        ui.faixa("aviso", "Tamanho diferente do registrado",
                 f'{r["tamanho_registrado"]:,} → {r["tamanho_atual"]:,} bytes: houve inserção ou remoção. '
                 "Só o início da primeira região indica com segurança onde a alteração começou.".replace(",", "."))
    ui.hashes([("Raiz registrada", r["merkle_raiz_registrada"]), ("Raiz atual", r["merkle_raiz_atual"]),
               ("SHA-256 registrado", r["sha256_registrado"]), ("SHA-256 atual", r["sha256_atual"])])

m1, m2, m3, m4 = st.columns(4)
m1.metric("Blocos", n_blocos)
m2.metric("Bloco", f"{tb // 1024} KB")
m3.metric("Tamanho", f"{tamanho / 1024 / 1024:.2f} MB")
m4.metric("Regiões alteradas", len(regioes))

ui.mapa_de_blocos(n_blocos, regioes)

# --- Mapa de tempo e regiões alteradas -----------------------------------------
mapa = saida["mapa"]
if mapa["status"] == "gerado":
    ui.faixa("info", "Mapa de tempo gerado",
             "O ffprobe listou os pacotes do vídeo e cada bloco ganhou o trecho de tempo que contém. "
             "O mapa foi gravado como derivado e o hash dele entrou no log.")
elif mapa["status"] == "invalido":
    ui.faixa("aviso", "Mapa de tempo rejeitado", mapa["motivo"])
elif mapa["status"] == "indisponivel":
    ui.faixa("aviso", "Sem mapa de tempo", f'{mapa["motivo"]} A localização fica em bytes.')

try:
    metadados = extrair_metadados(video)
except (OSError, ValueError):
    metadados = None

if regioes:
    st.subheader("Regiões alteradas")
    ui.barra_do_tempo(metadados and metadados["duracao_segundos"], [x.get("tempo") for x in regioes])
    ui.tabela_regioes(regioes, {"trecho do vídeo": ("tempo", False)})

# --- Vídeo, metadados e histórico ------------------------------------------------
col_video, col_meta = st.columns([3, 2])
with col_video:
    st.video(video)
with col_meta:
    if metadados:
        ui.dados("metadados (ffprobe)", metadados)
    else:
        ui.faixa("aviso", "Metadados indisponíveis", "O ffprobe não conseguiu ler este arquivo.")

st.subheader("Histórico desta evidência")
historico = [e for e in ler_eventos(caminhos(video).log) if e.get("dados", {}).get("arquivo") == nome]
st.dataframe(
    [{"#": e["seq"], "UTC": e["timestamp_utc"], "evento": e["evento"], "responsável": e["responsavel"],
      "hash": e["hash_evento"][:16] + "…", "anterior": e["hash_anterior"][:16] + "…"} for e in historico],
    hide_index=True, width="stretch",
)
st.caption("A corrente completa, com todas as evidências, está na página Log de custódia.")
