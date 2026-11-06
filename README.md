# Trabalho Prático de ALPCD - Grupo 12

## Aluno e Número
- Nathan Pacheco Falcão Sperinde - A90606
- Rafale Dornelles Copetti - A112988
- Clauber Janauys de Amorim Filho - A114341

## Trabalho Prático, Parte 1

CLI em Python para consultar a API pública de exercício físico wger:
`https://wger.de/api/v2/`. O enunciado está em `docs/ALPCD___TP1__26-1.pdf`.

Este é um esqueleto inicial: os comandos, argumentos, imports e configurações estão
preparados; as funções das alíneas lançam `NotImplementedError` até serem implementadas.

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
uv run python fitcli.py type 192
uv run python fitcli.py equipment chest
uv run python fitcli.py workout biceps,back compound 5
uv run python fitcli.py workout chest,shoulders isolated 3 --csv treino.csv
```

O `--help` e a validação dos argumentos já funcionam. A execução das alíneas informa
que a funcionalidade está por implementar; ainda não são feitos pedidos à API.

## Organização

- `fitcli.py`: aplicação Typer e os cinco comandos pedidos.
- `fitlib/api.py`: sessão Requests, User-Agent, URL base, inglês (`language=2`),
  timeout e funções reservadas aos pedidos e à paginação.
- `fitlib/exercises.py`: funções das alíneas a), b), c) e d).
- `fitlib/processing.py`: padrões `re`, limpeza de descrições e classificação do esforço.
- `fitlib/workout.py`: tipos de esforço aceites e composição do plano de treino.
- `fitlib/output.py`: funções reservadas às saídas JSON e CSV.
- `docs/REQUISITOS.md`: requisitos do PDF e ordem sugerida de implementação.
