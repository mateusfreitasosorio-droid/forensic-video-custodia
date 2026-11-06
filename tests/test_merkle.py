"""Hash por bloco, raiz de Merkle e regiões divergentes."""

import hashlib
import unittest

from src import merkle
from tests.apoio import ComPastaTemporaria, inserir_bytes, inverter_bit

BLOCO = 1024  # 1 KB nos testes: arquivos pequenos com vários blocos


class TestMerkle(ComPastaTemporaria):
    def setUp(self):
        super().setUp()
        self.arquivo = self.arquivo_aleatorio("a.bin", 10 * BLOCO + 300)  # 11 blocos, o último incompleto
        self.folhas, self.sha, self.tamanho = merkle.calcular_folhas(self.arquivo, BLOCO)

    def test_leitura_por_bloco_bate_com_o_hash_tradicional(self):
        with open(self.arquivo, "rb") as f:
            self.assertEqual(self.sha, hashlib.sha256(f.read()).hexdigest())
        self.assertEqual((len(self.folhas), self.tamanho), (11, 10 * BLOCO + 300))

    def test_raiz_e_deterministica(self):
        outra, _, _ = merkle.calcular_folhas(self.arquivo, BLOCO)
        self.assertEqual(merkle.calcular_raiz(self.folhas), merkle.calcular_raiz(outra))

    def test_um_bit_e_localizado_no_bloco_certo(self):
        for offset in (0, BLOCO - 1, BLOCO, 5 * BLOCO + 17, 10 * BLOCO + 299):  # início, bordas, meio, fim
            with self.subTest(offset=offset):
                inverter_bit(self.arquivo, offset)
                atuais, _, _ = merkle.calcular_folhas(self.arquivo, BLOCO)
                bloco = offset // BLOCO
                self.assertEqual(merkle.regioes_divergentes(self.folhas, atuais), [(bloco, bloco)])
                inverter_bit(self.arquivo, offset)  # desfaz para o próximo caso

    def test_insercao_diverge_do_primeiro_bloco_ate_o_fim(self):
        inserir_bytes(self.arquivo, 3 * BLOCO + 10, b"X")
        atuais, _, _ = merkle.calcular_folhas(self.arquivo, BLOCO)
        self.assertEqual(merkle.regioes_divergentes(self.folhas, atuais), [(3, 10)])

    def test_blocos_vizinhos_formam_uma_regiao(self):
        a = [b"%d" % i for i in range(10)]
        b = list(a)
        for i in (2, 3, 4, 9):
            b[i] = b"x"
        self.assertEqual(merkle.regioes_divergentes(a, b), [(2, 4), (9, 9)])
        self.assertEqual(merkle.regioes_divergentes(a, a[:7]), [(7, 9)])  # arquivo menor

    def test_numero_impar_de_folhas_e_arquivo_vazio(self):
        self.assertEqual(len(merkle.calcular_raiz([merkle.hash_folha(b"a")] * 3)), 32)
        vazio = self.arquivo_aleatorio("vazio.bin", 0)
        self.assertEqual(merkle.calcular_folhas(vazio, BLOCO)[0::2], ([], 0))

    def test_folha_e_no_tem_prefixos_diferentes(self):
        """Sem os prefixos, um nó interno poderia se passar por folha."""
        a, b = merkle.hash_folha(b"a"), merkle.hash_folha(b"b")
        self.assertNotEqual(merkle.hash_no(a, b), merkle.hash_folha(a + b))


if __name__ == "__main__":
    unittest.main()
