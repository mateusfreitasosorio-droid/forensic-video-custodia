"""
Componentes visuais da interface (tema terminal) e seleção de evidências.

O tema base vem de .streamlit/config.toml; aqui ficam o CSS extra e os
componentes em HTML que o Streamlit não oferece: painéis, faixas de status,
mapa de blocos e barra do tempo. Todo texto vindo de fora (nome de arquivo,
responsável) passa por html.escape antes de entrar no HTML.
"""

import html
import math
import os

import streamlit as st

from src.video_timeline import descrever, formatar_tempo

PASTA_EVIDENCIAS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "evidencias")
EXTENSOES = (".mp4", ".avi", ".mkv", ".mov")

VERDE, CIANO, VERMELHO, AMBAR, APAGADO = "#00ff9c", "#00e5ff", "#ff3355", "#ffb000", "#4a7a5a"

CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&display=swap');
html, body, [class*="css"], .stMarkdown, .stDataFrame, input, textarea, button {{
  font-family: 'JetBrains Mono', Consolas, 'Courier New', monospace !important;
}}
/* linhas de varredura de monitor CRT, por cima de tudo e sem bloquear cliques */
.stApp::after {{
  content: ""; position: fixed; inset: 0; pointer-events: none; z-index: 9999;
  background: repeating-linear-gradient(0deg, rgba(0,0,0,.18) 0 1px, transparent 1px 3px);
}}
h1, h2, h3 {{ color: {VERDE} !important; text-transform: uppercase; letter-spacing: .08em;
  text-shadow: 0 0 6px rgba(0,255,156,.55); }}
h1 {{ font-size: 1.7rem !important; }}
.stButton > button, .stDownloadButton > button {{
  border: 1px solid {VERDE}; background: transparent; color: {VERDE};
  text-transform: uppercase; letter-spacing: .1em; border-radius: 2px; }}
.stButton > button:hover {{ box-shadow: 0 0 12px {VERDE}; color: #05080a; background: {VERDE}; }}
.stButton > button:disabled {{ border-color: {APAGADO}; color: {APAGADO}; box-shadow: none; background: transparent; }}
[data-testid="stSidebar"] {{ border-right: 1px solid rgba(0,255,156,.25); }}
[data-testid="stMetricValue"] {{ color: {CIANO}; text-shadow: 0 0 6px rgba(0,229,255,.5); }}
.cursor::after {{ content: "█"; animation: piscar 1s steps(1) infinite; margin-left: .2em; }}
@keyframes piscar {{ 50% {{ opacity: 0; }} }}
.prompt {{ color: {APAGADO}; font-size: .85rem; margin-bottom: -.4rem; }}
.faixa {{ border: 1px solid; padding: .7rem 1rem; margin: .6rem 0; letter-spacing: .05em; }}
.faixa b {{ font-size: 1.05rem; }}
.painel {{ border: 1px solid rgba(0,255,156,.35); background: rgba(11,20,16,.85); padding: .8rem 1rem; margin: .6rem 0; }}
.painel .titulo {{ color: {APAGADO}; font-size: .8rem; margin-bottom: .4rem; }}
.check {{ line-height: 1.7; }}
.hash {{ color: {CIANO}; word-break: break-all; }}
.grade {{ display: flex; flex-wrap: wrap; gap: 2px; }}
.grade span {{ width: 11px; height: 11px; display: inline-block; }}
.legenda {{ color: {APAGADO}; font-size: .78rem; margin-top: .35rem; }}
.barra {{ position: relative; height: 20px; background: rgba(0,255,156,.15); border: 1px solid rgba(0,255,156,.5); }}
.barra div {{ position: absolute; top: 0; bottom: 0; background: {VERMELHO}; box-shadow: 0 0 8px {VERMELHO}; }}
.escala {{ display: flex; justify-content: space-between; font-size: .75rem; color: {APAGADO}; }}
</style>
"""


def aplicar_tema() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


# Roda na janela principal (o st.iframe executa o HTML com acesso à mesma
# origem, por isso o script alcança window.parent):
#   1. Declara a página como português e "não traduzir". O Streamlit marca
#      toda página como inglês (<html lang="en">); um navegador em português
#      então "traduz" o texto e o estraga ("é" vira "está", "True" vira
#      "Verdadeiro"). Num app pericial, o que aparece na tela tem que ser o
#      que o programa escreveu.
#   2. Intercepta C e R antes do Streamlit, só quando ninguém está digitando
#      num campo. A marca evita registrar o bloqueio de novo a cada reexecução.
_AJUSTES_DA_PAGINA = """
<script>
const janela = window.parent, doc = janela.document;
doc.documentElement.lang = "pt-BR";
doc.documentElement.setAttribute("translate", "no");
doc.documentElement.classList.add("notranslate");
if (!doc.querySelector('meta[name="google"]')) {
  const meta = doc.createElement("meta");
  meta.name = "google"; meta.content = "notranslate";
  doc.head.appendChild(meta);
}
if (!janela.__atalhosDesligados) {
  janela.__atalhosDesligados = true;
  janela.addEventListener("keydown", (e) => {
    const alvo = e.target, tecla = (e.key || "").toLowerCase();
    const digitando = alvo && (alvo.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(alvo.tagName));
    if ((tecla === "c" || tecla === "r") && !e.ctrlKey && !e.metaKey && !e.altKey && !digitando) {
      e.stopImmediatePropagation();
    }
  }, true);
}
</script>
"""


def ajustar_pagina() -> None:
    """Declara a página como português que não deve ser traduzido e desliga
    os atalhos de teclado C (limpar caches) e R (reexecutar) do Streamlit.

    Num app pericial, uma tecla apertada sem querer não deve abrir diálogos
    nem reexecutar a página. Ctrl+R (recarregar o navegador) continua normal.
    """
    st.iframe(_AJUSTES_DA_PAGINA, height=1)  # HTML fixo, escrito aqui: nada vem do usuário


def cabecalho(comando: str, titulo: str, descricao: str) -> None:
    """Título com cara de terminal: prompt, nome em verde e cursor piscando."""
    st.markdown(f'<div class="prompt">root@pericia:~$ {html.escape(comando)}</div>', unsafe_allow_html=True)
    st.markdown(f'<h1><span class="cursor">{html.escape(titulo)}</span></h1>', unsafe_allow_html=True)
    st.caption(descricao)


def faixa(tipo: str, titulo: str, texto: str = "") -> None:
    """Faixa de status. tipo: ok | falha | aviso | info."""
    cor, marca = {"ok": (VERDE, "[ OK ]"), "falha": (VERMELHO, "[ FALHA ]"),
                  "aviso": (AMBAR, "[ ! ]"), "info": (CIANO, "[ i ]")}[tipo]
    st.markdown(
        f'<div class="faixa" style="border-color:{cor};color:{cor};box-shadow:0 0 10px {cor}40">'
        f'<b>{marca} {html.escape(titulo)}</b>{"<br>" + html.escape(texto) if texto else ""}</div>',
        unsafe_allow_html=True,
    )


def painel(titulo: str, corpo_html: str) -> None:
    """Caixa com borda e título em estilo de janela de terminal."""
    st.markdown(f'<div class="painel"><div class="titulo">┌─ {html.escape(titulo)} ─</div>{corpo_html}</div>',
                unsafe_allow_html=True)


def checklist(itens: list) -> None:
    """itens: [(passou, rótulo, detalhe)] -> linhas ✔/✘ coloridas."""
    linhas = "".join(
        f'<div style="color:{VERDE if ok else VERMELHO}">{"✔" if ok else "✘"} {html.escape(rotulo)}'
        f'<span style="color:{APAGADO}"> — {html.escape(detalhe)}</span></div>'
        for ok, rotulo, detalhe in itens
    )
    painel("conferências", f'<div class="check">{linhas}</div>')


def dados(titulo: str, valores: dict) -> None:
    """Painel chave: valor (ausente aparece como —; verdadeiro/falso como sim/não)."""
    def texto(v):
        if v is None:
            return "—"
        return ("sim" if v else "não") if isinstance(v, bool) else html.escape(str(v))
    corpo = "".join(f'<div>{html.escape(str(k))}: <span class="hash">{texto(v)}</span></div>' for k, v in valores.items())
    painel(titulo, corpo)


def hashes(linhas: list) -> None:
    """linhas: [(rótulo, valor)] em monoespaçado, com o valor em ciano."""
    corpo = "".join(f'<div>{html.escape(r)}: <span class="hash">{html.escape(str(v))}</span></div>' for r, v in linhas)
    painel("hashes", corpo)


def mapa_de_blocos(n_blocos: int, regioes: list, maximo_celulas: int = 1500) -> None:
    """Um quadrado por bloco: verde = confere, vermelho = alterado.

    Vídeos grandes têm milhares de blocos; acima de maximo_celulas, cada
    quadrado passa a representar um grupo de blocos (vermelho se qualquer
    bloco do grupo estiver alterado).
    """
    n_blocos = max(n_blocos, max((r["blocos"][1] + 1 for r in regioes), default=0))
    if n_blocos == 0:
        return
    por_celula = math.ceil(n_blocos / maximo_celulas)
    alterados = {b for r in regioes for b in range(r["blocos"][0], r["blocos"][1] + 1)}
    celulas = []
    for inicio in range(0, n_blocos, por_celula):
        grupo = range(inicio, min(inicio + por_celula, n_blocos))
        ruim = any(b in alterados for b in grupo)
        cor = VERMELHO if ruim else VERDE
        dica = f"bloco {inicio}" if por_celula == 1 else f"blocos {grupo.start}–{grupo.stop - 1}"
        celulas.append(f'<span title="{dica}" style="background:{cor};opacity:{1 if ruim else .55};'
                       f'{"box-shadow:0 0 6px " + VERMELHO if ruim else ""}"></span>')
    escala = "1 quadrado = 1 bloco" if por_celula == 1 else f"1 quadrado = {por_celula} blocos"
    painel("mapa de blocos", f'<div class="grade">{"".join(celulas)}</div>'
                             f'<div class="legenda">■ verde: confere · ■ vermelho: alterado · {escala}</div>')


def barra_do_tempo(duracao: float, trechos: list) -> None:
    """Vídeo inteiro numa barra; os trechos alterados aparecem em vermelho."""
    trechos = [t for t in trechos if t and t.get("inicio") is not None]
    if not duracao or not trechos:
        return
    marcas = "".join(
        f'<div title="{html.escape(descrever(t))}" style="left:{100 * max(t["inicio"], 0) / duracao:.2f}%;'
        f'width:{max(100 * (t["fim"] - max(t["inicio"], 0)) / duracao, .8):.2f}%"></div>'
        for t in trechos
    )
    painel("linha do tempo", f'<div class="barra">{marcas}</div>'
                             f'<div class="escala"><span>0:00,00</span><span>{formatar_tempo(duracao)}</span></div>')


def tabela_regioes(regioes: list, colunas_tempo: dict) -> None:
    """colunas_tempo: {"nome da coluna": (chave_na_regiao, estimado)}."""
    st.dataframe(
        [
            {
                "região": n,
                "blocos": f'{r["blocos"][0]}' + ("" if r["blocos"][0] == r["blocos"][1] else f'–{r["blocos"][1]}'),
                "bytes": f'{r["byte_inicial"]:,} – {r["byte_final"]:,}'.replace(",", "."),
                **{nome: descrever(r.get(chave), estimado) for nome, (chave, estimado) in colunas_tempo.items()},
            }
            for n, r in enumerate(regioes, start=1)
        ],
        hide_index=True,
        width="stretch",
    )


# --- Seleção de evidências ---------------------------------------------------

def listar_videos() -> list:
    os.makedirs(PASTA_EVIDENCIAS, exist_ok=True)
    return sorted(f for f in os.listdir(PASTA_EVIDENCIAS) if f.lower().endswith(EXTENSOES))


def _salvar_upload(enviado) -> str:
    """Grava o arquivo enviado em evidencias/ UMA vez e devolve o caminho.

    O Streamlit reexecuta a página a cada clique; os ids dos uploads já
    gravados ficam na sessão para a evidência não ser regravada. Um arquivo
    com o mesmo nome nunca é sobrescrito.
    """
    nome = os.path.basename(enviado.name)
    caminho = os.path.join(PASTA_EVIDENCIAS, nome)
    gravados = st.session_state.setdefault("uploads_gravados", set())
    if enviado.file_id not in gravados:
        if os.path.exists(caminho):
            faixa("falha", "Nome já existe", f"Já existe {nome} em evidencias/. Renomeie o arquivo antes de enviar.")
            st.stop()
        with open(caminho, "xb") as f:
            f.write(enviado.getbuffer())
        gravados.add(enviado.file_id)
    return caminho


def escolher_video(chave: str, rotulo: str = "Evidência"):
    """Lista de evidências + envio de arquivo. Devolve o caminho ou None."""
    escolhido = st.selectbox(rotulo, ["—"] + listar_videos(), key=f"{chave}_lista")
    enviado = st.file_uploader("ou envie um arquivo", type=[e[1:] for e in EXTENSOES], key=f"{chave}_upload")
    if enviado is not None:
        return _salvar_upload(enviado)
    return os.path.join(PASTA_EVIDENCIAS, escolhido) if escolhido != "—" else None


def campo_responsavel(chave: str) -> str:
    return st.text_input("Responsável", key=f"{chave}_responsavel",
                         help="Quem está manuseando a evidência. Vai para o log de custódia.").strip()
