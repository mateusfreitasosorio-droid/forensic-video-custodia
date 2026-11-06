"""
Núcleo da esteira de custódia de vídeo forense (sem interface).

    merkle          hash SHA-256 por bloco, raiz de Merkle e regiões divergentes
    custody_log     log de custódia encadeado (JSONL, só acréscimo)
    ffprobe         acesso ao ffprobe (metadados e pacotes do contêiner)
    video_metadata  metadados do vídeo
    video_timeline  mapa bytes -> tempo do vídeo
    integrity       recebimento, verificação e mapa de tempo de uma evidência
    comparacao      vídeo original (referência) x vídeo questionado
"""
