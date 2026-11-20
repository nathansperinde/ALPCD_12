# Cache e pedidos HTTP

## Objetivo

Reutilizar respostas públicas sem misturar dados de contas. Implementação em
`fitlib/api.py`; visão geral no [README oficial](../README.md).

## Funcionamento

| Modo | Armazenamento | Expiração |
|---|---|---|
| `none` | Não lê nem grava cache | Cada chamada executa HTTP |
| `memory` | Dicionário no processo | 14 dias ou fim do processo |
| `disk` (predefinido) | `fitlib/cache.json` | 14 dias, persistindo entre execuções |

Memory e disk usam `{"data": ..., "expires_at": ...}` e `CACHE_TTL`. A expiração
é verificada em cada acesso; nunca há retorno de dados expirados. Ao guardar,
removem-se entradas expiradas/inválidas antes de substituir o ficheiro por escrita
atómica. Não existem threads ou limpeza periódica.

`refresh=True` ignora a leitura do resultado guardado e grava o resultado fresco
na cache selecionada. Em `none`, a chamada continua sem ler ou escrever cache.
`get_list` encaminha modo e refresh a todas as páginas e conta apenas os itens
aceites por `transform` para aplicar `max_items`.

## Funções e ficheiros

- `get_data` e `get_list`: entrada pública para respostas/páginas.
- `_load_cache`, `_get_cached_data`, `_save_cache`, `_write_cache`: leitura,
  validação, atualização e escrita segura, sem camadas adicionais.
- `request` e `get_list(token=...)`: pedidos autenticados, sempre fora da cache.
- `exercises`: alíneas A–E; `extras`: consultas adicionais; `workouts`: treinos.
  As três partes usam o mesmo contrato de API.

## Exemplos de utilização

```python
from fitlib import api

api.get_data("muscle/")
api.get_data("muscle/", refresh=True)
api.get_data("muscle/", cache_mode="memory")
api.get_list("muscle/", cache_mode="none")
```

Na CLI, top/search/difficulty/ingredient expõem `--refresh`. Os restantes comandos
mantêm as opções anteriores; não se adicionaram flags para uniformizar à força.

## Política e limitações

Esta secção descreve o comportamento atual: memory está disponível, mas não é
selecionado pelos consumidores atuais. A revisão documental não alterou a escolha
dos modos.

- Consultas públicas: manter `disk` predefinido, sem repetir o argumento em todos
  os pontos. Não forçar utilização de memory/none se não houver necessidade.
- Login, criação de conta, tokens, templates e POSTs: sem cache HTTP. O keyring é
  persistência de credenciais, não a cache pública.
- Cálculos, JSON locais e CSV não precisam de outra cache de pedidos.
- Expirados podem permanecer no ficheiro enquanto não houver nova gravação;
  continuam inválidos para leitura. A escrita atómica não coordena escritores concorrentes.
- Reorganizar ficheiros não altera chaves, TTL, endpoints ou política de expiração.

## Verificação

Usar HTTP simulado, relógio controlado e cache em directório temporário: verificar
os três modos, TTL, refresh, paginação, filtros e o bypass da cache quando existe token.
