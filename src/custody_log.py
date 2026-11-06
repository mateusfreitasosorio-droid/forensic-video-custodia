"""
Log de custódia encadeado (sem blockchain).

Cada evento é uma linha JSON (formato JSONL) e o arquivo só recebe acréscimos.
Cada evento guarda o hash do anterior:

    evento 1 (anterior = 000...0)  -> hash_1
    evento 2 (anterior = hash_1)   -> hash_2
    evento 3 (anterior = hash_2)   -> hash_3

Editar ou apagar um evento antigo quebra a corrente, e a verificação aponta
onde. É a mesma proteção de uma blockchain de um único nó, sem a
infraestrutura.

Limitação: o log é local. Quem tem acesso de escrita pode reescrevê-lo
inteiro (recalculando todos os hashes) ou apagar os últimos eventos. Para
fechar essa brecha, o hash do último evento precisa ser ancorado fora da
máquina (no laudo, num sistema da instituição etc.).

ATENÇÃO: o cálculo do hash (_hash_do_evento) e os nomes dos campos definem a
validade dos logs já gravados. Mudá-los invalida toda corrente existente.
"""

import hashlib
import json
import os
from datetime import datetime, timezone

HASH_INICIAL = "0" * 64  # "hash anterior" do primeiro evento


def _hash_do_evento(evento_sem_hash: dict) -> str:
    # JSON canônico (chaves ordenadas, sem espaços): o mesmo evento sempre
    # gera o mesmo texto e, portanto, o mesmo hash.
    texto = json.dumps(evento_sem_hash, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def ler_eventos(caminho_log: str) -> list:
    """Todos os eventos, em ordem. Levanta ValueError se uma linha não for JSON."""
    if not os.path.exists(caminho_log):
        return []
    with open(caminho_log, "r", encoding="utf-8") as f:
        return [json.loads(linha) for linha in f if linha.strip()]


def _ultimo_evento(caminho_log: str):
    """Lê só o fim do arquivo para achar o último evento.

    Registrar um evento não precisa reler o log inteiro: num log com milhares
    de eventos isso faria cada registro ficar mais lento que o anterior.
    """
    if not os.path.exists(caminho_log):
        return None
    with open(caminho_log, "rb") as f:
        f.seek(0, os.SEEK_END)
        fim = f.tell()
        janela = 4096
        while True:
            inicio = max(0, fim - janela)
            f.seek(inicio)
            linhas = [l for l in f.read(fim - inicio).splitlines() if l.strip()]
            # a linha mais antiga da janela pode estar cortada; só confiamos
            # na última se houver outra antes dela ou se lemos desde o início
            if linhas and (len(linhas) > 1 or inicio == 0):
                return json.loads(linhas[-1])
            if inicio == 0:
                return None
            janela *= 2


def registrar_evento(caminho_log: str, evento: str, responsavel: str, dados: dict) -> dict:
    """Acrescenta um evento ao fim do log e devolve o evento gravado."""
    ultimo = _ultimo_evento(caminho_log)
    novo = {
        "seq": ultimo["seq"] + 1 if ultimo else 1,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "evento": evento,
        "responsavel": responsavel,
        "dados": dados,
        "hash_anterior": ultimo["hash_evento"] if ultimo else HASH_INICIAL,
    }
    novo["hash_evento"] = _hash_do_evento(novo)
    with open(caminho_log, "a", encoding="utf-8") as f:  # "a": só acrescenta
        f.write(json.dumps(novo, ensure_ascii=False) + "\n")
    return novo


def verificar_corrente(eventos: list) -> tuple:
    """Recalcula a corrente. Devolve (ok, mensagem, seq_com_problema)."""
    anterior = HASH_INICIAL
    for e in eventos:
        copia = dict(e)
        hash_gravado = copia.pop("hash_evento", None)
        if copia.get("hash_anterior") != anterior:
            return False, f"Corrente quebrada: o evento {e.get('seq')} não aponta para o evento anterior.", e.get("seq")
        if _hash_do_evento(copia) != hash_gravado:
            return False, f"Evento {e.get('seq')} foi alterado depois de registrado.", e.get("seq")
        anterior = hash_gravado
    return True, f"Log íntegro: {len(eventos)} evento(s) com a corrente válida.", None


def verificar_log(caminho_log: str) -> tuple:
    """Atalho: lê o arquivo e verifica a corrente."""
    return verificar_corrente(ler_eventos(caminho_log))
