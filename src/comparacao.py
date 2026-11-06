"""
Comparação entre um vídeo ORIGINAL (referência) e um vídeo QUESTIONADO.

Pergunta pericial: "o questionado é igual ao original? Se não, onde difere?"

  - A referência é o REGISTRO DE CUSTÓDIA do original. Antes de comparar, o
    original é verificado e precisa estar íntegro: uma referência adulterada
    não serve de base.
  - O questionado também é evidência: é recebido (ou verificado, se já tiver
    registro), e a comparação vira um evento "comparacao" no log.
  - A comparação é folha a folha, na divisão em blocos do original. Cada
    região divergente ganha o trecho de tempo no original e no questionado.

Limitação: se bytes foram inseridos ou removidos, tudo a partir do primeiro
bloco divergente muda; só o INÍCIO da primeira região é confiável.
"""

import os

from . import merkle
from .custody_log import ler_eventos, registrar_evento
from .integrity import (caminhos, carregar_mapa, custodia_confiavel, ler_registro,
                        localizar, montar_regioes, receber_ou_verificar)


def comparar_videos(caminho_original: str, caminho_questionado: str, responsavel: str) -> dict:
    """Devolve {"status": "referencia_invalida", "referencia": ...} se o
    original não estiver íntegro; senão {"status": "ok", "identicos", "regioes",
    ...}, com "tempo_original" e "tempo_questionado" em cada região."""
    if os.path.abspath(caminho_original) == os.path.abspath(caminho_questionado):
        raise ValueError("Escolha dois arquivos diferentes para comparar.")

    referencia = receber_ou_verificar(caminho_original, responsavel)
    if not custodia_confiavel(referencia):
        return {"status": "referencia_invalida", "referencia": referencia}
    questionado = receber_ou_verificar(caminho_questionado, responsavel)

    co, cq = caminhos(caminho_original), caminhos(caminho_questionado)
    # relidos só agora: as duas passagens pela esteira podem ter gravado mapas
    eventos_o = ler_eventos(co.log)
    eventos_q = eventos_o if cq.log == co.log else ler_eventos(cq.log)
    reg_o, _ = ler_registro(co.registro)
    tb = reg_o["tamanho_bloco"]

    # Folhas do questionado: o registro dele serve se descreve os bytes atuais
    # e usa o mesmo tamanho de bloco; senão, recalcula a partir do arquivo.
    reg_q = ler_registro(cq.registro)[0] if custodia_confiavel(questionado) else None
    if reg_q and reg_q["tamanho_bloco"] == tb:
        folhas_q = [bytes.fromhex(h) for h in reg_q["folhas"]]
        tamanho_q, raiz_q = reg_q["tamanho_bytes"], reg_q["merkle_raiz"]
        mapa_q = carregar_mapa(caminho_questionado, reg_q, eventos_q)[0]
    else:
        folhas_q, _, tamanho_q = merkle.calcular_folhas(caminho_questionado, tb, hash_unico=False)
        raiz_q, mapa_q = merkle.calcular_raiz(folhas_q).hex(), None

    mapa_o = carregar_mapa(caminho_original, reg_o, eventos_o)[0]
    # Mesmo tamanho e sem inserção/remoção de bytes: a estrutura do contêiner
    # é a do original, então o tempo de cada bloco também é. Fica marcado
    # como estimado.
    estimado = mapa_q is None and mapa_o is not None and tamanho_q == reg_o["tamanho_bytes"]

    folhas_o = [bytes.fromhex(h) for h in reg_o["folhas"]]
    regioes = montar_regioes(merkle.regioes_divergentes(folhas_o, folhas_q), tb,
                             max(reg_o["tamanho_bytes"], tamanho_q))
    localizar(regioes, mapa_o, "tempo_original")
    localizar(regioes, mapa_o if estimado else mapa_q, "tempo_questionado")

    evento = registrar_evento(cq.log, "comparacao", responsavel, {
        "arquivo": os.path.basename(caminho_questionado),
        "original": os.path.basename(caminho_original),
        "merkle_raiz_original": reg_o["merkle_raiz"],
        "merkle_raiz_questionado": raiz_q,
        "identicos": not regioes,
        "regioes_blocos": [list(r["blocos"]) for r in regioes],
    })
    return {
        "status": "ok",
        "identicos": not regioes,
        "regioes": regioes,
        "tamanho_bloco": tb,
        "tamanho_original": reg_o["tamanho_bytes"],
        "tamanho_questionado": tamanho_q,
        "merkle_raiz_original": reg_o["merkle_raiz"],
        "merkle_raiz_questionado": raiz_q,
        "tem_mapa_original": mapa_o is not None,
        "tempo_questionado_estimado": estimado,
        "referencia": referencia,
        "questionado": questionado,
        "evento": evento,
    }
