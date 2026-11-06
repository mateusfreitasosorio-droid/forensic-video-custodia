"""
Integridade de uma evidência: recebimento, verificação e mapa de tempo.

Arquivos de cada evidência (na mesma pasta do vídeo):

    <video>.custodia.json    REGISTRO: hash de cada bloco (folhas), raiz de
                             Merkle e SHA-256 tradicional. Gravado UMA vez.
    <video>.mapa_tempo.json  MAPA: trecho de tempo de cada bloco. É um
                             DERIVADO do vídeo, também gravado uma vez.
    custodia_log.jsonl       LOG: um por pasta, com todos os eventos de todas
                             as evidências numa única corrente.

Regras que garantem a custódia:
  1. Registro e mapa nunca são sobrescritos (gravação em modo exclusivo).
  2. Todo manuseio vira um evento no log, com o responsável.
  3. O evento de recebimento guarda o hash do REGISTRO, e o evento do mapa
     guarda o hash do MAPA. Trocar qualquer um desses arquivos depois é
     detectado, mesmo que o substituto seja coerente consigo mesmo.
  4. Na segunda entrada de um vídeo, o sistema VERIFICA em vez de registrar.
  5. O mapa só é gerado a partir de bytes comprovadamente originais: no
     recebimento ou numa verificação íntegra. Nunca de um vídeo alterado.
"""

import hashlib
import json
import os
from datetime import datetime, timezone
from typing import NamedTuple

from . import ffprobe, merkle, video_timeline
from .custody_log import ler_eventos, registrar_evento, verificar_corrente

NOME_LOG = "custodia_log.jsonl"
SUFIXO_REGISTRO = ".custodia.json"
SUFIXO_MAPA = ".mapa_tempo.json"
# Eventos que criam um registro. "migracao" vem da v1, quando registros que
# só tinham o SHA-256 do arquivo inteiro foram convertidos para o formato atual.
EVENTOS_DE_ENTRADA = ("recebimento", "migracao")


class Caminhos(NamedTuple):
    registro: str
    mapa: str
    log: str


def caminhos(caminho_video: str) -> Caminhos:
    pasta = os.path.dirname(os.path.abspath(caminho_video))
    return Caminhos(caminho_video + SUFIXO_REGISTRO, caminho_video + SUFIXO_MAPA, os.path.join(pasta, NOME_LOG))


def _sha256(dados: bytes) -> str:
    return hashlib.sha256(dados).hexdigest()


def _ler_bytes(caminho: str) -> tuple:
    """(dados, sha256). O hash é dos bytes exatos do disco: ler em modo texto
    no Windows trocaria \\r\\n por \\n e o hash não bateria."""
    with open(caminho, "rb") as f:
        dados = f.read()
    return dados, _sha256(dados)


def _gravar_uma_vez(caminho: str, conteudo: dict) -> str:
    """Grava o JSON em modo "xb" (falha se o arquivo existir) e devolve o hash."""
    dados = json.dumps(conteudo, ensure_ascii=False, indent=2).encode("utf-8")
    with open(caminho, "xb") as f:
        f.write(dados)
    return _sha256(dados)


def _ultimo_evento_de(eventos: list, tipos: tuple, arquivo: str):
    for e in reversed(eventos):
        if e.get("evento") in tipos and e.get("dados", {}).get("arquivo") == arquivo:
            return e
    return None


def ler_registro(caminho_registro: str) -> tuple:
    """(registro, sha256_do_arquivo_de_registro)."""
    dados, sha = _ler_bytes(caminho_registro)
    registro = json.loads(dados.decode("utf-8"))
    if "folhas" not in registro:
        raise ValueError("registro no formato antigo (só SHA-256 do arquivo inteiro), sem hash por bloco.")
    return registro, sha


def montar_regioes(pares: list, tamanho_bloco: int, fim_maximo: int) -> list:
    """Converte pares (primeiro_bloco, ultimo_bloco) em regiões com faixa de bytes."""
    return [
        {"blocos": (a, b), "byte_inicial": a * tamanho_bloco,
         "byte_final": min((b + 1) * tamanho_bloco, fim_maximo) - 1}
        for a, b in pares
    ]


# --- Recebimento e verificação -------------------------------------------

def registrar_recebimento(caminho_video: str, responsavel: str,
                          tamanho_bloco: int = merkle.TAMANHO_BLOCO_PADRAO) -> tuple:
    """Calcula folhas, raiz e SHA-256, grava o registro e o evento
    "recebimento". Levanta FileExistsError se o registro já existir."""
    c = caminhos(caminho_video)
    if os.path.exists(c.registro):  # antecipa o erro do "xb" sem calcular hashes à toa
        raise FileExistsError(f"Já existe registro de custódia: {c.registro}")
    folhas, sha256_arquivo, tamanho = merkle.calcular_folhas(caminho_video, tamanho_bloco)
    registro = {
        "arquivo": os.path.basename(caminho_video),
        "tamanho_bytes": tamanho,
        "tamanho_bloco": tamanho_bloco,
        "n_blocos": len(folhas),
        "algoritmo": "SHA-256",
        "sha256_arquivo": sha256_arquivo,
        "merkle_raiz": merkle.calcular_raiz(folhas).hex(),
        "folhas": [f.hex() for f in folhas],
    }
    sha256_registro = _gravar_uma_vez(c.registro, registro)
    evento = registrar_evento(c.log, "recebimento", responsavel, {
        "arquivo": registro["arquivo"],
        "sha256_arquivo": sha256_arquivo,
        "merkle_raiz": registro["merkle_raiz"],
        "sha256_registro": sha256_registro,
    })
    return registro, evento


def verificar(caminho_video: str, eventos: list = None) -> dict:
    """Confere o vídeo, o registro e o log, sem gravar nada.

    A custódia só é íntegra se as QUATRO conferências passarem:
      video_confere         raiz recalculada do arquivo == raiz registrada
      registro_coerente     folhas do registro geram a raiz registrada
      registro_confere_log  hash do registro == hash gravado no recebimento
      log_integro           corrente do log válida
    Separá-las diz QUAL peça falhou: um log adulterado com o vídeo intacto
    leva a uma conclusão pericial diferente de um vídeo alterado.
    """
    c = caminhos(caminho_video)
    registro, sha256_registro = ler_registro(c.registro)
    if eventos is None:
        eventos = ler_eventos(c.log)

    tb = registro["tamanho_bloco"]
    folhas_registradas = [bytes.fromhex(h) for h in registro["folhas"]]
    folhas, sha256_atual, tamanho = merkle.calcular_folhas(caminho_video, tb)
    raiz_atual = merkle.calcular_raiz(folhas).hex()

    log_ok, log_msg, _ = verificar_corrente(eventos)
    entrada = _ultimo_evento_de(eventos, EVENTOS_DE_ENTRADA, registro["arquivo"])
    resultado = {
        "video_confere": raiz_atual == registro["merkle_raiz"],
        "registro_coerente": merkle.calcular_raiz(folhas_registradas).hex() == registro["merkle_raiz"],
        "registro_confere_log": entrada is not None and entrada["dados"].get("sha256_registro") == sha256_registro,
        "log_integro": log_ok,
        "log_mensagem": log_msg,
        "sha256_registrado": registro["sha256_arquivo"],
        "sha256_atual": sha256_atual,
        "merkle_raiz_registrada": registro["merkle_raiz"],
        "merkle_raiz_atual": raiz_atual,
        "tamanho_registrado": registro["tamanho_bytes"],
        "tamanho_atual": tamanho,
        "tamanho_bloco": tb,
        "regioes": montar_regioes(merkle.regioes_divergentes(folhas_registradas, folhas), tb,
                                  max(registro["tamanho_bytes"], tamanho)),
        "registro": registro,
    }
    resultado["integro"] = all(resultado[k] for k in
                               ("video_confere", "registro_coerente", "registro_confere_log", "log_integro"))
    return resultado


# --- Mapa de tempo (derivado) ----------------------------------------------

def gerar_mapa(caminho_video: str, registro: dict, responsavel: str) -> dict:
    """Gera, grava e registra no log o mapa bytes -> tempo.

    Só deve ser chamado quando os bytes do vídeo são os do registro. Se o
    arquivo não for um vídeo legível ou faltar o ffprobe, não é falha de
    custódia: a localização apenas fica em bytes.
    """
    c = caminhos(caminho_video)
    try:
        mapa = {
            "arquivo": registro["arquivo"],
            "merkle_raiz": registro["merkle_raiz"],  # vídeo de onde o mapa saiu
            "tamanho_bloco": registro["tamanho_bloco"],
            "n_blocos": registro["n_blocos"],
            "ferramenta": ffprobe.versao(),
            "gerado_em_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "blocos": video_timeline.construir_mapa(caminho_video, registro["tamanho_bloco"], registro["n_blocos"]),
        }
    except ffprobe.ERROS as erro:
        return {"status": "indisponivel", "motivo": str(erro)}
    try:
        sha256_mapa = _gravar_uma_vez(c.mapa, mapa)
    except FileExistsError:
        return {"status": "indisponivel",
                "motivo": f"já existe {os.path.basename(c.mapa)} sem registro no log; ele não foi substituído."}
    registrar_evento(c.log, "mapa_tempo", responsavel, {
        "arquivo": registro["arquivo"],
        "merkle_raiz": registro["merkle_raiz"],
        "sha256_mapa": sha256_mapa,
        "ferramenta": mapa["ferramenta"],
    })
    return {"status": "gerado", "motivo": None}


def carregar_mapa(caminho_video: str, registro: dict, eventos: list) -> tuple:
    """(mapa, aviso). O mapa só é usado se o hash dele bater com o evento
    "mapa_tempo" do log e se ele for do mesmo registro (raiz e bloco);
    um mapa trocado apontaria o trecho errado."""
    c = caminhos(caminho_video)
    if not os.path.exists(c.mapa):
        return None, None
    dados, sha = _ler_bytes(c.mapa)
    evento = _ultimo_evento_de(eventos, ("mapa_tempo",), registro["arquivo"])
    if evento is None or evento["dados"].get("sha256_mapa") != sha:
        return None, "O mapa de tempo não confere com o log de custódia; a localização ficou só em bytes."
    mapa = json.loads(dados.decode("utf-8"))
    if (mapa.get("merkle_raiz"), mapa.get("tamanho_bloco")) != (registro["merkle_raiz"], registro["tamanho_bloco"]):
        return None, "O mapa de tempo é de outro registro; a localização ficou só em bytes."
    return mapa, None


def localizar(regioes: list, mapa: dict, chave: str = "tempo") -> None:
    """Acrescenta a cada região o trecho de tempo que ela ocupa no mapa."""
    for r in regioes:
        r[chave] = video_timeline.trecho(mapa["blocos"], *r["blocos"]) if mapa else None


# --- Esteira ---------------------------------------------------------------

def receber_ou_verificar(caminho_video: str, responsavel: str) -> dict:
    """Ponto de entrada da esteira de custódia.

    Sem registro: recebe (registro + mapa). Com registro: verifica, grava o
    evento de verificação e localiza as regiões alteradas no tempo. Devolve
    {"acao": "recebimento" | "verificacao", ..., "mapa": {"status", "motivo"}},
    com status "gerado", "existente", "indisponivel" ou "invalido".
    """
    responsavel = (responsavel or "").strip()
    if not responsavel:
        raise ValueError("Informe o responsável: todo manuseio da evidência precisa ter autor no log.")
    if not os.path.isfile(caminho_video):
        raise FileNotFoundError(f"Arquivo de evidência não encontrado: {caminho_video}")
    c = caminhos(caminho_video)

    if not os.path.exists(c.registro):
        registro, evento = registrar_recebimento(caminho_video, responsavel)
        return {"acao": "recebimento", "registro": registro, "evento": evento,
                "mapa": gerar_mapa(caminho_video, registro, responsavel)}

    eventos = ler_eventos(c.log)
    r = verificar(caminho_video, eventos)
    evento = registrar_evento(c.log, "verificacao", responsavel, {
        "arquivo": r["registro"]["arquivo"],
        "integro": r["integro"],
        "merkle_raiz_atual": r["merkle_raiz_atual"],
        "regioes_alteradas": [list(x["blocos"]) for x in r["regioes"]],
    })

    mapa, aviso = carregar_mapa(caminho_video, r["registro"], eventos)
    localizar(r["regioes"], mapa)
    if mapa:
        status = {"status": "existente", "motivo": None}
    elif aviso:
        status = {"status": "invalido", "motivo": aviso}
    elif r["integro"]:
        # registro anterior ao mapa: o vídeo acabou de conferir bit a bit,
        # então gerar o mapa agora equivale a gerá-lo no recebimento
        status = gerar_mapa(caminho_video, r["registro"], responsavel)
    else:
        status = {"status": "indisponivel",
                  "motivo": "sem mapa de tempo, e ele só pode ser gerado a partir de um vídeo íntegro."}
    return {"acao": "verificacao", "resultado": r, "evento": evento, "mapa": status}


def custodia_confiavel(saida: dict) -> bool:
    """O registro descreve os bytes atuais do arquivo? (recebido agora ou verificado íntegro)"""
    return saida["acao"] == "recebimento" or saida["resultado"]["integro"]
