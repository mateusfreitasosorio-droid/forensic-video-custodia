"""Recebimento e verificação: as quatro conferências da custódia."""

import json
import os
import unittest

from src import merkle
from src.custody_log import ler_eventos, verificar_log
from src.integrity import caminhos, receber_ou_verificar, registrar_recebimento, verificar
from tests.apoio import ComPastaTemporaria, editar_linha, inverter_bit

MB = merkle.TAMANHO_BLOCO_PADRAO


class TestIntegridade(ComPastaTemporaria):
    """Arquivo de bytes aleatórios (não é vídeo): testa a custódia sem depender do FFmpeg."""

    def setUp(self):
        super().setUp()
        self.video = self.arquivo_aleatorio("v.mp4", 2 * MB + 500_000)  # 3 blocos
        self.c = caminhos(self.video)

    def test_primeira_entrada_registra_e_segunda_verifica(self):
        primeira = receber_ou_verificar(self.video, "teste")
        segunda = receber_ou_verificar(self.video, "teste")
        self.assertEqual((primeira["acao"], segunda["acao"]), ("recebimento", "verificacao"))
        self.assertTrue(segunda["resultado"]["integro"])
        self.assertEqual([e["evento"] for e in ler_eventos(self.c.log)], ["recebimento", "verificacao"])
        self.assertTrue(verificar_log(self.c.log)[0])

    def test_arquivo_que_nao_e_video_fica_sem_mapa_sem_quebrar(self):
        self.assertEqual(receber_ou_verificar(self.video, "teste")["mapa"]["status"], "indisponivel")

    def test_registro_nunca_e_sobrescrito(self):
        receber_ou_verificar(self.video, "teste")
        with open(self.c.registro, "rb") as f:
            antes = f.read()
        with self.assertRaises(FileExistsError):
            registrar_recebimento(self.video, "teste")
        with open(self.c.registro, "rb") as f:
            self.assertEqual(f.read(), antes)

    def test_um_bit_alterado_e_localizado_e_registrado_no_log(self):
        receber_ou_verificar(self.video, "teste")
        inverter_bit(self.video, MB + 123)  # bloco 1
        r = receber_ou_verificar(self.video, "teste")["resultado"]
        self.assertFalse(r["video_confere"])
        self.assertEqual([x["blocos"] for x in r["regioes"]], [(1, 1)])
        self.assertEqual(r["regioes"][0]["byte_inicial"], MB)
        self.assertEqual(ler_eventos(self.c.log)[-1]["dados"]["regioes_alteradas"], [[1, 1]])

    def test_registro_refeito_para_o_video_alterado_e_pego_pelo_log(self):
        """Ataque: alterar o vídeo e reescrever um registro coerente com ele."""
        receber_ou_verificar(self.video, "teste")
        inverter_bit(self.video, 10)
        with open(self.c.registro, encoding="utf-8") as f:
            reg = json.load(f)
        folhas, sha, _ = merkle.calcular_folhas(self.video)
        reg.update(folhas=[x.hex() for x in folhas], sha256_arquivo=sha, merkle_raiz=merkle.calcular_raiz(folhas).hex())
        with open(self.c.registro, "w", encoding="utf-8") as f:
            json.dump(reg, f, ensure_ascii=False, indent=2)
        r = verificar(self.video)
        self.assertTrue(r["video_confere"] and r["registro_coerente"])  # sozinhos, aprovariam a fraude
        self.assertFalse(r["registro_confere_log"])
        self.assertFalse(r["integro"])

    def test_registro_editado_e_detectado(self):
        receber_ou_verificar(self.video, "teste")
        with open(self.c.registro, encoding="utf-8") as f:
            reg = json.load(f)
        reg["folhas"][1] = "00" * 32
        with open(self.c.registro, "w", encoding="utf-8") as f:
            json.dump(reg, f)
        r = verificar(self.video)
        self.assertFalse(r["registro_coerente"])
        self.assertFalse(r["integro"])

    def test_log_adulterado_com_video_intacto(self):
        """O vídeo confere, mas a custódia não pode ser atestada."""
        receber_ou_verificar(self.video, "teste")
        editar_linha(self.c.log, 0, '"responsavel": "teste"', '"responsavel": "outra pessoa"')
        r = verificar(self.video)
        self.assertTrue(r["video_confere"])
        self.assertFalse(r["log_integro"])
        self.assertFalse(r["integro"])

    def test_responsavel_obrigatorio_e_arquivo_inexistente(self):
        with self.assertRaises(ValueError):
            receber_ou_verificar(self.video, "   ")
        with self.assertRaises(FileNotFoundError):
            receber_ou_verificar(self.caminho("nao_existe.mp4"), "teste")
        self.assertFalse(os.path.exists(self.c.registro))


if __name__ == "__main__":
    unittest.main()
