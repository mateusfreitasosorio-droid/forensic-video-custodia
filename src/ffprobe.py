"""
Acesso ao ffprobe (vem com o FFmpeg). Único ponto do projeto que conversa
com ferramentas externas.

O ffprobe só LÊ o arquivo: não decodifica nem altera nada. Ele fornece:
  - metadados do contêiner e dos fluxos (duração, FPS, resolução, codec);
  - a lista de PACOTES (cada quadro de imagem, cada trecho de áudio) com a
    posição em bytes, o tamanho e o instante em que aparecem no vídeo.
"""

import json
import shutil
import subprocess
import tempfile

ERROS = (OSError, ValueError, subprocess.SubprocessError)  # falhas esperadas ao chamar o ffprobe


def _executavel() -> str:
    caminho = shutil.which("ffprobe")
    if not caminho:
        raise FileNotFoundError("ffprobe não encontrado no PATH (instale o FFmpeg).")
    return caminho


def versao() -> str:
    """Ex.: 'ffprobe version 9.0-full_build...'. Todo derivado registra a
    ferramenta e a versão que o produziram."""
    saida = subprocess.run([_executavel(), "-version"], capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=30).stdout
    return saida.splitlines()[0] if saida else "ffprobe (versão desconhecida)"


def informacoes(caminho_video: str) -> dict:
    """Saída de `ffprobe -show_format -show_streams` em JSON."""
    proc = subprocess.run(
        [_executavel(), "-v", "error", "-show_format", "-show_streams", "-of", "json", caminho_video],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120,
    )
    if proc.returncode != 0:
        raise ValueError(f"o ffprobe não conseguiu ler o arquivo. {proc.stderr.strip()[:300]}".strip())
    return json.loads(proc.stdout)


def _float(valor):
    return None if valor in (None, "", "N/A") else float(valor)


def iterar_pacotes(caminho_video: str):
    """Gera um pacote por vez: (tipo, tempo_s, pos, size, quadro_chave).

    A saída é lida linha a linha, em vez de carregar um JSON gigante: um vídeo
    de 10 GB tem centenas de milhares de pacotes, e a memória fica constante.
    Pacotes sem posição ou sem tempo (raros) são ignorados.
    """
    comando = [
        _executavel(), "-v", "error",
        "-show_entries", "packet=codec_type,pts_time,dts_time,pos,size,flags",
        "-of", "compact=p=0",  # uma linha por pacote: chave=valor|chave=valor
        caminho_video,
    ]
    total = 0
    # stderr vai para um arquivo temporário: num pipe, um arquivo danificado
    # que gerasse muitos erros poderia travar o ffprobe esperando leitura.
    with tempfile.TemporaryFile() as erros:
        with subprocess.Popen(comando, stdout=subprocess.PIPE, stderr=erros,
                              text=True, encoding="utf-8", errors="replace") as proc:
            for linha in proc.stdout:
                c = dict(par.split("=", 1) for par in linha.strip().split("|") if "=" in par)
                tempo = _float(c.get("pts_time"))
                if tempo is None:
                    tempo = _float(c.get("dts_time"))
                if tempo is None or c.get("pos") in (None, "", "N/A") or c.get("size") in (None, "", "N/A"):
                    continue
                total += 1
                yield c.get("codec_type"), tempo, int(c["pos"]), int(c["size"]), "K" in c.get("flags", "")
        erros.seek(0)
        mensagem = erros.read().decode("utf-8", "replace").strip()
    if proc.returncode != 0 or total == 0:
        raise ValueError(f"o ffprobe não conseguiu ler os pacotes do arquivo. {mensagem[:300]}".strip())
