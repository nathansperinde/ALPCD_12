# Trabalho Prático de ALPCD - Grupo 12

## Aluno e Número
- Nathan Pacheco Falcão Sperinde - A90606
- Rafale Dornelles Copetti - A112988
- Clauber Janauys de Amorim Filho - A114341

## Trabalho Prático, Parte 1

CLI em Python para consultar a API pública de exercício físico wger:
`https://wger.de/api/v2/`. O enunciado está em `docs/ALPCD___TP1__26-1.pdf`.

As bases HTTP/cache/paginação (`fitlib/api.py`), JSON/CSV (`fitlib/output.py`)
e as alíneas A/B (`top` e `search`) estão implementadas. `type`, `equipment` e
`workout` continuam por implementar.

A integração preserva a API de Nathan e aproveita a lógica de A/B de Rafael.
`AeB/` permanece como referência histórica. Consulte as decisões e os testes
reais em [docs/INTEGRACAO.md](docs/INTEGRACAO.md).

Consulte [as interfaces das bases e a divisão entre três colegas](docs/DIVISAO_TRABALHO.md).

## Ambiente e instalação

O único ambiente virtual fica em `ALPCD_12/.venv`. Execute os comandos desta pasta:

```bash
cd ALPCD_12
uv sync
uv run python fitcli.py --help
```

`uv sync` instala as versões registadas em `uv.lock`. As dependências externas são
`requests` (pedidos HTTP) e `typer` (CLI). `re`, `csv` e `json` pertencem à biblioteca
padrão do Python e não precisam de instalação. Para adicionar as dependências
manualmente com uv, o comando é `uv add requests typer`.

Se preferir ativar o ambiente, execute `source .venv/bin/activate` e depois
`python fitcli.py --help`.

## Comandos preparados

```bash
uv run python fitcli.py top 10
uv run python fitcli.py search biceps 5
uv run python fitcli.py top 5 --refresh
uv run python fitcli.py search chest 5 --refresh
uv run python fitcli.py type 192
uv run python fitcli.py equipment chest
uv run python fitcli.py workout biceps,back compound 5
uv run python fitcli.py workout chest,shoulders isolated 3 --csv treino.csv
```

`top` e `search` consultam a wger e apresentam JSON com id, nome, categoria,
equipamentos, músculos, músculos secundários e descrição inglesa. A cache não
expira automaticamente; use `--refresh` para obter dados atualizados.
Os demais comandos apresentam a mensagem de funcionalidade por implementar.

## Organização

- `fitcli.py`: aplicação Typer e os cinco comandos pedidos.
- `fitlib/api.py`: requests.get, headers, timeout de 15 segundos, erros, cache e
  paginação com transformação opcional.
- `fitlib/exercises.py`: inglês (`LANGUAGE=2`), normalização, top/search e funções
  reservadas a c)/d).
- `fitlib/processing.py`: padrões `re`, limpeza de descrições e classificação do esforço.
- `fitlib/workout.py`: tipos de esforço aceites e composição do plano de treino.
- `fitlib/output.py`: saída JSON e exportação CSV de planos de treino.
- `docs/REQUISITOS.md`: requisitos do PDF e ordem sugerida de implementação.
- `docs/DIVISAO_TRABALHO.md`: contratos, exemplos e divisão de responsabilidades.

## Testes das bases

```bash
uv run python -m unittest discover -s tests -v
```
