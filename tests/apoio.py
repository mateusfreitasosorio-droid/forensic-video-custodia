"""
Apoio aos testes: pasta temporária por teste, adulterações controladas e um
vídeo real gerado pelo ffmpeg (4 s de imagem de teste + tom de áudio).

Rodar todos os testes:
    .venv\\Scripts\\python.exe -m unittest -v
"""

import os
import shutil
import subprocess
import tempfile
import unittest

TEM_FFMPEG = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))
precisa_ffmpeg = unittest.skipUnless(TEM_FFMPEG, "requer FFmpeg instalado")


class ComPastaTemporaria(unittest.TestCase):
    """Cada teste ganha uma pasta própria, apagada no fim."""

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir)

    def caminho(self, nome: str) -> str:
        return os.path.join(self.dir, nome)

    def arquivo_aleatorio(self, nome: str, tamanho: int) -> str:
        caminho = self.caminho(nome)
        with open(caminho, "wb") as f:
            f.write(os.urandom(tamanho))
        return caminho

    def video_de_teste(self, nome: str = "video.mp4") -> str:
        """4 s a 25 fps, quadro-chave a cada 1 s, com áudio AAC."""
        caminho = self.caminho(nome)
        subprocess.run([
            "ffmpeg", "-v", "error", "-y",
            "-f", "lavfi", "-i", "testsrc=duration=4:size=320x240:rate=25",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=4",
            "-c:v", "mpeg4", "-q:v", "3", "-g", "25", "-c:a", "aac", "-shortest", caminho,
        ], check=True)
        return caminho


def inverter_bit(caminho: str, offset: int) -> None:
    """A menor alteração possível: inverte o bit menos significativo de um byte."""
    with open(caminho, "r+b") as f:
        f.seek(offset)
        b = f.read(1)
        f.seek(offset)
        f.write(bytes([b[0] ^ 1]))


def inserir_bytes(caminho: str, offset: int, dados: bytes) -> None:
    with open(caminho, "rb") as f:
        conteudo = f.read()
    with open(caminho, "wb") as f:
        f.write(conteudo[:offset] + dados + conteudo[offset:])


def editar_linha(caminho: str, indice: int, de: str, para: str) -> None:
    """Edita o texto de uma linha (como alguém faria num editor)."""
    with open(caminho, encoding="utf-8") as f:
        linhas = f.readlines()
    linhas[indice] = linhas[indice].replace(de, para)
    with open(caminho, "w", encoding="utf-8") as f:
        f.writelines(linhas)
