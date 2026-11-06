"""
Linha de comando da esteira de custódia (útil para scripts e lotes).

    python main.py verificar VIDEO --responsavel NOME
    python main.py comparar ORIGINAL QUESTIONADO --responsavel NOME

Código de saída: 0 = íntegro/idênticos, 1 = erro, 2 = alteração encontrada.
"""

import argparse
import sys

from src.comparacao import comparar_videos
from src.integrity import receber_ou_verificar
from src.video_timeline import descrever


def _imprimir_regioes(regioes: list, chave: str) -> None:
    for r in regioes:
        a, b = r["blocos"]
        print(f"  blocos {a}-{b}: bytes {r['byte_inicial']}-{r['byte_final']} -> {descrever(r.get(chave))}")


def verificar(args) -> int:
    saida = receber_ou_verificar(args.video, args.responsavel)
    if saida["acao"] == "recebimento":
        reg = saida["registro"]
        print(f"REGISTRADO (evento #{saida['evento']['seq']})\n  raiz de Merkle: {reg['merkle_raiz']}\n"
              f"  SHA-256:        {reg['sha256_arquivo']}\n  mapa de tempo:  {saida['mapa']['status']}")
        return 0
    r = saida["resultado"]
    print("ÍNTEGRO" if r["integro"] else "FALHA NA CUSTÓDIA", f"(evento #{saida['evento']['seq']})")
    for chave, rotulo in (("video_confere", "vídeo"), ("registro_coerente", "registro"),
                          ("registro_confere_log", "registro x log"), ("log_integro", "log")):
        print(f"  [{'ok' if r[chave] else 'FALHA'}] {rotulo}")
    _imprimir_regioes(r["regioes"], "tempo")
    return 0 if r["integro"] else 2


def comparar(args) -> int:
    r = comparar_videos(args.original, args.questionado, args.responsavel)
    if r["status"] == "referencia_invalida":
        print("COMPARAÇÃO RECUSADA: o original não confere com o próprio registro de custódia.")
        return 2
    print("IDÊNTICOS" if r["identicos"] else f"DIFERENTES: {len(r['regioes'])} região(ões)",
          f"(evento #{r['evento']['seq']})")
    _imprimir_regioes(r["regioes"], "tempo_original")
    return 0 if r["identicos"] else 2


def main() -> int:
    parser = argparse.ArgumentParser(description="Esteira de custódia de vídeo forense")
    sub = parser.add_subparsers(dest="comando", required=True)
    p = sub.add_parser("verificar", help="recebe uma evidência nova ou verifica uma já registrada")
    p.add_argument("video")
    p.add_argument("--responsavel", required=True)
    p.set_defaults(funcao=verificar)
    p = sub.add_parser("comparar", help="compara um vídeo questionado com o original")
    p.add_argument("original")
    p.add_argument("questionado")
    p.add_argument("--responsavel", required=True)
    p.set_defaults(funcao=comparar)
    args = parser.parse_args()
    try:
        return args.funcao(args)
    except (OSError, ValueError) as erro:
        print(f"ERRO: {erro}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
