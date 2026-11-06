# FORENSIC//VIDEO — cadeia de custódia de vídeos forenses

Protótipo de um projeto de pesquisa (TCC) em Sistemas de Informação.
**Objetivo:** demonstrar que hashes SHA-256 calculados por bloco, organizados em árvore de Merkle e registrados num log de custódia encadeado permitem localizar o trecho alterado de um vídeo e rastrear os arquivos derivados, sem perder a prova bit a bit, com memória constante e em tempo compatível com a rotina pericial.

**Pergunta:** como verificar a integridade de um vídeo recebido pela perícia de modo a **localizar o trecho alterado** e **rastrear os derivados**, mantendo a prova criptográfica bit a bit, com memória constante e num notebook comum?

## Como rodar

Requisitos: Python 3.10+ e FFmpeg (`ffmpeg` e `ffprobe` no PATH).

```
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m streamlit run app.py      # interface
.venv\Scripts\python.exe -m unittest -v                # testes
```

Linha de comando (para scripts e lotes):

```
.venv\Scripts\python.exe main.py verificar evidencias\video.mp4 --responsavel M
.venv\Scripts\python.exe main.py comparar evidencias\original.mp4 evidencias\questionado.mp4 --responsavel M
```

Código de saída: 0 = íntegro/idênticos, 1 = erro, 2 = alteração encontrada.

## Interface

| Página | O que faz |
|---|---|
| **Custódia** | Primeira entrada: **registra** o vídeo. Entradas seguintes: **verifica** bit a bit e mostra as quatro conferências, o mapa de blocos e as regiões alteradas no tempo. |
| **Comparar** | Original (referência) × questionado, lado a lado. Mostra onde o questionado difere e posiciona os dois players na região escolhida. |
| **Log de custódia** | A corrente completa, verificada, e o hash do último evento para **ancorar no laudo**. |

## Como funciona

1. **Hash por bloco** ([src/merkle.py](src/merkle.py)): o arquivo é lido em blocos de 1 MB (memória constante). Cada bloco vira uma folha `SHA-256(0x00‖bloco)`, e as folhas são combinadas em pares `SHA-256(0x01‖esq‖dir)` até a **raiz de Merkle**. O SHA-256 tradicional, compatível com FTK e IPED, sai na mesma leitura.
2. **Log encadeado** ([src/custody_log.py](src/custody_log.py)): todo manuseio vira um evento JSONL que guarda o hash do anterior. Editar ou apagar um evento quebra a corrente.
3. **Mapa bytes → tempo** ([src/video_timeline.py](src/video_timeline.py)): o `ffprobe` lista os pacotes do contêiner (posição, tamanho, instante). Assim cada bloco ganha o trecho de vídeo que contém, e um bloco alterado vira "0:04,97 → 0:05,67".
4. **Esteira** ([src/integrity.py](src/integrity.py)): recebimento, verificação e mapa. **Comparação** em [src/comparacao.py](src/comparacao.py).

### As quatro conferências da verificação

| Conferência | Detecta |
|---|---|
| Vídeo: raiz recalculada = raiz registrada | qualquer alteração no vídeo, localizada por bloco |
| Registro: folhas geram a raiz registrada | edição do registro |
| Registro × log: hash do registro = hash gravado no recebimento | registro **refeito** para um vídeo alterado |
| Log: corrente válida | edição ou remoção de eventos |

A verificação mostra as quatro separadamente. Um log adulterado com o vídeo intacto leva a uma conclusão pericial diferente de um vídeo alterado.

## Arquivos de cada evidência (pasta `evidencias/`)

| Arquivo | Conteúdo | Gravado |
|---|---|---|
| `<video>.custodia.json` | folhas, raiz de Merkle, SHA-256, tamanho do bloco | uma vez (modo exclusivo) |
| `<video>.mapa_tempo.json` | trecho de vídeo e áudio de cada bloco, versão do ffprobe, raiz de origem | uma vez; é um **derivado**, com hash no log |
| `custodia_log.jsonl` | eventos `recebimento`, `verificacao`, `mapa_tempo`, `comparacao` (e `migracao`, da v1) | só acréscimo |

O mapa só é gerado a partir de bytes comprovadamente originais: no recebimento ou numa verificação íntegra.

## Limitações (para a Metodologia)

- **Precisão × tamanho do bloco:** com 1 MB, um vídeo curto cabe em poucos blocos e a região fica larga. Blocos menores dão mais precisão, mas um registro maior.
- **Inserção ou remoção de bytes** desloca todos os blocos seguintes; só o **início** da primeira região é confiável.
- **Log local:** a corrente detecta edição e remoção de eventos antigos, mas não a reescrita do log inteiro nem a remoção dos últimos eventos. Por isso o hash do último evento deve ser **ancorado fora da máquina** (no laudo, por exemplo).
- **Players:** começam no segundo inteiro (0:04,97 abre em 0:04).

## Estrutura

```
app.py              configuração, tema e navegação
ui.py               componentes visuais e seleção de evidências
paginas/            custodia.py · comparar.py · log.py
src/                núcleo (sem interface): merkle, custody_log, ffprobe,
                    video_metadata, video_timeline, integrity, comparacao
tests/              32 testes (os que usam vídeo real exigem FFmpeg)
main.py             linha de comando
.streamlit/         tema
```

Versões no git: `v1` (construída passo a passo durante a pesquisa) e `v2` (esta, reorganizada).
