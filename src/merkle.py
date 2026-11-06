"""
Hash por bloco e árvore de Merkle.

  1. O arquivo é lido em blocos (padrão 1 MB), nunca inteiro: memória constante.
  2. Cada bloco gera uma FOLHA:  SHA-256(0x00 || bloco)
  3. As folhas são combinadas em pares, SHA-256(0x01 || esquerda || direita),
     nível a nível, até sobrar um único hash: a RAIZ.
  4. Qualquer bit alterado muda a folha do bloco e, por consequência, a raiz.
     Comparando folha a folha, sabemos QUAL bloco mudou.

Os prefixos 0x00 (folha) e 0x01 (nó interno) impedem que um nó interno seja
confundido com uma folha (ataque de segunda pré-imagem). Num nível com número
ímpar de nós, o último é duplicado.
"""

import hashlib

TAMANHO_BLOCO_PADRAO = 1024 * 1024  # 1 MB
PREFIXO_FOLHA = b"\x00"
PREFIXO_NO = b"\x01"


def hash_folha(bloco) -> bytes:
    h = hashlib.sha256(PREFIXO_FOLHA)
    h.update(bloco)  # update() em vez de concatenar: evita copiar 1 MB por bloco
    return h.digest()


def hash_no(esquerda: bytes, direita: bytes) -> bytes:
    return hashlib.sha256(PREFIXO_NO + esquerda + direita).digest()


def calcular_folhas(caminho: str, tamanho_bloco: int = TAMANHO_BLOCO_PADRAO, hash_unico: bool = True):
    """Lê o arquivo UMA vez e devolve (folhas, sha256_do_arquivo, tamanho_em_bytes).

    O SHA-256 tradicional do arquivo inteiro (o que FTK/IPED mostram) é
    calculado na mesma leitura, para manter compatibilidade com o laudo.
    Um único buffer é reaproveitado em todas as leituras (readinto), sem
    alocar memória nova a cada bloco.
    """
    folhas = []
    unico = hashlib.sha256() if hash_unico else None
    buffer = bytearray(tamanho_bloco)
    visao = memoryview(buffer)
    total = 0
    with open(caminho, "rb") as f:  # "rb": somente leitura
        while lidos := f.readinto(buffer):
            bloco = visao[:lidos]
            folhas.append(hash_folha(bloco))
            if unico is not None:
                unico.update(bloco)
            total += lidos
    return folhas, (unico.hexdigest() if unico else None), total


def calcular_raiz(folhas: list) -> bytes:
    """Combina as folhas em pares até sobrar a raiz."""
    if not folhas:
        return hashlib.sha256(b"").digest()  # arquivo vazio: raiz por convenção
    nivel = list(folhas)
    while len(nivel) > 1:
        if len(nivel) % 2:
            nivel.append(nivel[-1])
        nivel = [hash_no(nivel[i], nivel[i + 1]) for i in range(0, len(nivel), 2)]
    return nivel[0]


def regioes_divergentes(folhas_a: list, folhas_b: list) -> list:
    """Compara folha a folha e devolve as REGIÕES divergentes como pares
    (primeiro_bloco, ultimo_bloco) de blocos vizinhos.

    Um bloco que só existe numa das listas (arquivo maior ou menor) também
    diverge. Ex.: blocos 2, 3, 4 e 9 diferentes -> [(2, 4), (9, 9)].
    """
    regioes = []
    for i in range(max(len(folhas_a), len(folhas_b))):
        a = folhas_a[i] if i < len(folhas_a) else None
        b = folhas_b[i] if i < len(folhas_b) else None
        if a == b:
            continue
        if regioes and regioes[-1][1] == i - 1:
            regioes[-1] = (regioes[-1][0], i)
        else:
            regioes.append((i, i))
    return regioes
