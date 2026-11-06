"""Com vídeo real (gerado pelo ffmpeg): metadados, mapa de tempo e comparação."""

import json
import os
import shutil
import unittest

from src import ffprobe, integrity, video_timeline
from src.comparacao import comparar_videos
from src.custody_log import ler_eventos
from src.integrity import caminhos, receber_ou_verificar, registrar_recebimento
from src.video_metadata import extrair_metadados
from tests.apoio import ComPastaTemporaria, inserir_bytes, inverter_bit, precisa_ffmpeg

BLOCO = 16 * 1024  # blocos pequenos: o vídeo de teste (< 1 MB) fica com vários


@precisa_ffmpeg
class TestVideo(ComPastaTemporaria):
    def setUp(self):
        super().setUp()
        self.video = self.video_de_teste()
        self.c = caminhos(self.video)
        self.tamanho = os.path.getsize(self.video)

    def registrar_com_bloco_pequeno(self, caminho=None):
        """Recebimento com blocos de 16 KB + mapa, para a localização ser fina."""
        caminho = caminho or self.video
        registro, _ = registrar_recebimento(caminho, "teste", BLOCO)
        self.assertEqual(integrity.gerar_mapa(caminho, registro, "teste")["status"], "gerado")
        return registro

    def quadro_perto_de(self, segundos: float):
        """(byte no meio de um quadro não-chave após `segundos`, instante do quadro)."""
        for tipo, t, pos, size, chave in ffprobe.iterar_pacotes(self.video):
            if tipo == "video" and not chave and t >= segundos:
                return pos + size // 2, t
        self.fail("quadro não encontrado")

    # --- metadados e mapa ---------------------------------------------------

    def test_metadados(self):
        m = extrair_metadados(self.video)
        self.assertEqual((m["largura"], m["altura"], m["fps"], m["tem_audio"]), (320, 240, 25.0, True))
        self.assertAlmostEqual(m["duracao_segundos"], 4.0, delta=0.1)

    def test_mapa_cobre_o_video_em_ordem(self):
        n = -(-self.tamanho // BLOCO)
        mapa = video_timeline.construir_mapa(self.video, BLOCO, n)
        inicios = [b["video"][0] for b in mapa if b and b["video"]]
        self.assertEqual(len(mapa), n)
        self.assertEqual(inicios, sorted(inicios))  # os bytes avançam junto com o tempo
        self.assertAlmostEqual(inicios[0], 0.0, places=1)
        self.assertGreater(max(b["video"][1] for b in mapa if b and b["video"]), 3.5)

    def test_bloco_alterado_vira_trecho_curto_do_video(self):
        self.registrar_com_bloco_pequeno()
        offset, instante = self.quadro_perto_de(2.0)
        inverter_bit(self.video, offset)
        saida = receber_ou_verificar(self.video, "teste")
        self.assertEqual(saida["mapa"]["status"], "existente")
        [regiao] = saida["resultado"]["regioes"]
        t = regiao["tempo"]
        self.assertEqual(regiao["blocos"][0], offset // BLOCO)
        self.assertEqual(t["tipo"], "video")
        self.assertTrue(t["inicio"] <= instante <= t["fim"])
        self.assertLess(t["fim"] - t["inicio"], 1.0)

    def test_recebimento_gera_mapa_registrado_no_log(self):
        self.assertEqual(receber_ou_verificar(self.video, "teste")["mapa"]["status"], "gerado")
        self.assertEqual([e["evento"] for e in ler_eventos(self.c.log)], ["recebimento", "mapa_tempo"])

    def test_registro_sem_mapa_ganha_mapa_so_se_o_video_conferir(self):
        registrar_recebimento(self.video, "teste")
        self.assertEqual(receber_ou_verificar(self.video, "teste")["mapa"]["status"], "gerado")

        outro = self.video_de_teste("outro.mp4")
        registrar_recebimento(outro, "teste")
        inverter_bit(outro, self.tamanho // 2)
        self.assertEqual(receber_ou_verificar(outro, "teste")["mapa"]["status"], "indisponivel")
        self.assertFalse(os.path.exists(caminhos(outro).mapa))

    def test_mapa_trocado_nao_e_usado(self):
        receber_ou_verificar(self.video, "teste")
        with open(self.c.mapa, encoding="utf-8") as f:
            mapa = json.load(f)
        mapa["blocos"][0]["video"] = [90.0, 95.0, 1]  # aponta um trecho falso
        with open(self.c.mapa, "w", encoding="utf-8") as f:
            json.dump(mapa, f)
        inverter_bit(self.video, self.tamanho // 2)
        saida = receber_ou_verificar(self.video, "teste")
        self.assertEqual(saida["mapa"]["status"], "invalido")
        self.assertIsNone(saida["resultado"]["regioes"][0]["tempo"])

    def test_formatar_e_descrever(self):
        self.assertEqual(video_timeline.formatar_tempo(4.97), "0:04,97")
        self.assertEqual(video_timeline.formatar_tempo(125.5), "2:05,50")
        self.assertEqual(video_timeline.formatar_tempo(-0.021), "-0:00,02")
        self.assertIn("cabeçalho", video_timeline.descrever(video_timeline.trecho([None], 0, 0)))
        self.assertIn("além do fim", video_timeline.descrever(video_timeline.trecho([None], 5, 5)))

    # --- comparação -----------------------------------------------------------

    def copia(self, nome="questionado.mp4"):
        caminho = self.caminho(nome)
        shutil.copyfile(self.video, caminho)
        return caminho

    def test_comparacao_de_copias_identicas(self):
        r = comparar_videos(self.video, self.copia(), "teste")
        self.assertTrue(r["identicos"])
        self.assertEqual(ler_eventos(self.c.log)[-1]["evento"], "comparacao")

    def test_comparacao_localiza_o_trecho(self):
        self.registrar_com_bloco_pequeno()
        questionado = self.copia()
        offset, instante = self.quadro_perto_de(2.0)
        inverter_bit(questionado, offset)
        r = comparar_videos(self.video, questionado, "teste")
        [regiao] = r["regioes"]
        t = regiao["tempo_original"]
        self.assertEqual(regiao["blocos"], (offset // BLOCO, offset // BLOCO))
        self.assertTrue(t["inicio"] <= instante <= t["fim"])
        self.assertLess(t["fim"] - t["inicio"], 1.0)
        self.assertTrue(r["tempo_questionado_estimado"])  # questionado registrado com outro bloco

    def test_comparacao_com_bytes_inseridos(self):
        questionado = self.copia()
        inserir_bytes(questionado, self.tamanho // 2, b"INSERIDO")
        r = comparar_videos(self.video, questionado, "teste")
        self.assertFalse(r["identicos"])
        self.assertEqual(r["tamanho_questionado"], r["tamanho_original"] + 8)

    def test_comparacao_recusa_original_adulterado(self):
        questionado = self.copia()
        receber_ou_verificar(self.video, "teste")
        inverter_bit(self.video, self.tamanho // 2)
        self.assertEqual(comparar_videos(self.video, questionado, "teste")["status"], "referencia_invalida")
        self.assertNotIn("comparacao", [e["evento"] for e in ler_eventos(self.c.log)])

    def test_comparacao_exige_arquivos_diferentes(self):
        with self.assertRaises(ValueError):
            comparar_videos(self.video, self.video, "teste")


if __name__ == "__main__":
    unittest.main()
