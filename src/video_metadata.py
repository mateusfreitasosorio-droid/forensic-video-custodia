"""
Metadados do vídeo, lidos do contêiner pelo ffprobe.

São valores DECLARADOS no cabeçalho do arquivo: rápidos de ler, mas em
gravações de DVR podem estar errados ou ausentes (FPS variável, duração
zerada). Por isso cada campo pode vir como None, em vez de quebrar.
"""

import os

from . import ffprobe


def _fps(texto):
    """'30000/1001' -> 29.97"""
    try:
        num, den = (float(x) for x in texto.split("/"))
        return round(num / den, 3) if den else None
    except (AttributeError, ValueError):
        return None


def extrair_metadados(caminho_video: str) -> dict:
    """Levanta FileNotFoundError (arquivo ou ffprobe ausente) ou ValueError
    (arquivo que o ffprobe não consegue ler)."""
    if not os.path.isfile(caminho_video):
        raise FileNotFoundError(f"Arquivo de vídeo não encontrado: {caminho_video}")
    info = ffprobe.informacoes(caminho_video)
    video = next((s for s in info.get("streams", []) if s.get("codec_type") == "video"), None)
    if video is None:
        raise ValueError("o arquivo não tem fluxo de vídeo.")
    formato = info.get("format", {})
    duracao = formato.get("duration") or video.get("duration")
    quadros = video.get("nb_frames")
    return {
        "arquivo": os.path.basename(caminho_video),
        "contêiner": formato.get("format_long_name") or formato.get("format_name"),
        "codec": video.get("codec_name"),
        "fps": _fps(video.get("avg_frame_rate")),
        "largura": video.get("width"),
        "altura": video.get("height"),
        "total_quadros_declarados": int(quadros) if quadros and quadros.isdigit() else None,
        "duracao_segundos": round(float(duracao), 2) if duracao else None,
        "tem_audio": any(s.get("codec_type") == "audio" for s in info.get("streams", [])),
    }
