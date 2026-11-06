"""Log de custódia encadeado."""

import json
import unittest

from src.custody_log import HASH_INICIAL, _ultimo_evento, ler_eventos, registrar_evento, verificar_log
from tests.apoio import ComPastaTemporaria, editar_linha


class TestLog(ComPastaTemporaria):
    def setUp(self):
        super().setUp()
        self.log = self.caminho("log.jsonl")
        for n in range(3):
            registrar_evento(self.log, "verificacao", "teste", {"n": n})

    def test_corrente_valida_e_encadeada(self):
        eventos = ler_eventos(self.log)
        self.assertTrue(verificar_log(self.log)[0])
        self.assertEqual([e["seq"] for e in eventos], [1, 2, 3])
        self.assertEqual(eventos[0]["hash_anterior"], HASH_INICIAL)
        self.assertEqual(eventos[2]["hash_anterior"], eventos[1]["hash_evento"])

    def test_edicao_de_evento_antigo_e_detectada(self):
        editar_linha(self.log, 0, '"responsavel": "teste"', '"responsavel": "outra pessoa"')
        ok, _, seq = verificar_log(self.log)
        self.assertFalse(ok)
        self.assertEqual(seq, 1)

    def test_remocao_de_evento_e_detectada(self):
        eventos = ler_eventos(self.log)
        del eventos[1]
        with open(self.log, "w", encoding="utf-8") as f:
            f.writelines(json.dumps(e) + "\n" for e in eventos)
        self.assertFalse(verificar_log(self.log)[0])

    def test_ultimo_evento_e_lido_pelo_fim_do_arquivo(self):
        grande = {"lista": list(range(5000))}  # evento maior que a janela inicial de leitura
        registrar_evento(self.log, "comparacao", "teste", grande)
        registrar_evento(self.log, "verificacao", "teste", {})
        self.assertEqual(_ultimo_evento(self.log), ler_eventos(self.log)[-1])
        self.assertTrue(verificar_log(self.log)[0])

    def test_log_inexistente(self):
        self.assertIsNone(_ultimo_evento(self.caminho("nao_existe.jsonl")))
        self.assertEqual(ler_eventos(self.caminho("nao_existe.jsonl")), [])


if __name__ == "__main__":
    unittest.main()
