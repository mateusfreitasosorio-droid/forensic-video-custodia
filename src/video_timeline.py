"""
Mapa bytes -> tempo do vídeo.

A árvore de Merkle diz QUAL bloco de bytes mudou. Para o perito, isso só faz
sentido em tempo: "o trecho entre 0:04,97 e 0:05,67 foi alterado".

Não dá para usar regra de três (byte 50% = metade do vídeo): num vídeo
comprimido, um quadro-chave (imagem completa) ocupa muito mais bytes que os
quadros seguintes, que guardam só diferenças, e o contêiner ainda tem
cabeçalho e índice, que não são imagem.

A fonte confiável é o próprio contêiner: o ffprobe lista cada pacote com
posição, tamanho e instante. Cruzando isso com os blocos, cada bloco ganha o
resumo do que contém. Este módulo só CALCULA; gravar e registrar no log é
papel do integrity.py.
"""

from . import ffprobe


def construir_mapa(caminho_video: str, tamanho_bloco: int, n_blocos: int) -> list:
    """Resumo de mídia de cada bloco, na mesma divisão da árvore de Merkle.

    Cada posição da lista é None (bloco sem pacotes: cabeçalho ou índice do
    contêiner) ou {"video": [t0, t1, n] | None, "audio": [t0, t1, n] | None,
    "quadro_chave": bool}. Um pacote que atravessa vários blocos conta em
    todos eles.
    """
    blocos = [None] * n_blocos
    for tipo, tempo, pos, size, chave in ffprobe.iterar_pacotes(caminho_video):
        if tipo not in ("video", "audio") or size <= 0:
            continue
        for b in range(pos // tamanho_bloco, min((pos + size - 1) // tamanho_bloco, n_blocos - 1) + 1):
            resumo = blocos[b] or {"video": None, "audio": None, "quadro_chave": False}
            faixa = resumo[tipo]
            resumo[tipo] = [tempo, tempo, 1] if faixa is None else [min(faixa[0], tempo), max(faixa[1], tempo), faixa[2] + 1]
            resumo["quadro_chave"] |= tipo == "video" and chave
            blocos[b] = resumo
    for resumo in filter(None, blocos):  # arredonda só no fim, sem acumular erro
        for tipo in ("video", "audio"):
            if resumo[tipo]:
                resumo[tipo][0], resumo[tipo][1] = round(resumo[tipo][0], 3), round(resumo[tipo][1], 3)
    return blocos


def trecho(blocos_mapa: list, primeiro: int, ultimo: int) -> dict:
    """Une o conteúdo dos blocos primeiro..ultimo de uma região.

    Devolve {"tipo": "video" | "audio" | "cabecalho" | "fora", "inicio",
    "fim", "quadros", "quadro_chave"}:
      - video: a região tem quadros de imagem (inicio/fim = tempo dos quadros);
      - audio: só áudio, nenhum quadro de imagem;
      - cabecalho: nenhum pacote (estrutura/índice do contêiner);
      - fora: a região está além do fim do arquivo mapeado (bytes acrescentados).
    """
    if primeiro >= len(blocos_mapa):
        return {"tipo": "fora", "inicio": None, "fim": None, "quadros": 0, "quadro_chave": False}
    resumos = [b for b in blocos_mapa[primeiro:ultimo + 1] if b]
    for tipo in ("video", "audio"):
        faixas = [r[tipo] for r in resumos if r[tipo]]
        if faixas:
            return {
                "tipo": tipo,
                "inicio": min(f[0] for f in faixas),
                "fim": max(f[1] for f in faixas),
                "quadros": sum(f[2] for f in faixas) if tipo == "video" else 0,
                "quadro_chave": any(r["quadro_chave"] for r in resumos),
            }
    return {"tipo": "cabecalho", "inicio": None, "fim": None, "quadros": 0, "quadro_chave": False}


def formatar_tempo(segundos: float) -> str:
    """4.97 -> '0:04,97'; 125.5 -> '2:05,50'; -0.021 -> '-0:00,02'.

    Tempo negativo é normal no início do áudio AAC (atraso do codificador).
    """
    if segundos < 0:
        return "-" + formatar_tempo(-segundos)
    minutos, resto = divmod(segundos, 60)
    return f"{int(minutos)}:{resto:05.2f}".replace(".", ",")


def descrever(t: dict, estimado: bool = False) -> str:
    """Texto curto de um trecho, para tabelas e relatórios."""
    if t is None:
        return "— (sem mapa de tempo)"
    if t["tipo"] == "fora":
        return "além do fim do original (bytes acrescentados)"
    if t["tipo"] == "cabecalho":
        return "cabeçalho/índice do contêiner (nenhum quadro)"
    texto = f'{formatar_tempo(t["inicio"])} → {formatar_tempo(t["fim"])}'
    if t["tipo"] == "video":
        texto += f' · {t["quadros"]} quadro{"s" if t["quadros"] != 1 else ""}'
        texto += " · quadro-chave" if t["quadro_chave"] else ""
    else:
        texto += " · só áudio"
    return texto + (" · estimado" if estimado else "")
