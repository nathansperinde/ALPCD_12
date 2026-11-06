# Bases e divisão do trabalho

## O que já está pronto

`fitlib/api.py` trata HTTP e paginação. `fitlib/output.py` escreve JSON e CSV.
As regras das alíneas a)–e) continuam por implementar. A CLI já chama as funções
reservadas e apresenta erros de API e de escrita sem traceback.

Não é necessário alterar estas bases para cada comando. Os módulos das alíneas
devolvem dados; a CLI escolhe como apresentá-los.

### Pedidos à API

```python
from fitlib.api import LANGUAGE, get_all, get_json

# Uma página, mantendo count, next, previous e results:
page = get_json("exerciseinfo/", {"language": LANGUAGE, "limit": 20})

# Todos os resultados; next é seguido automaticamente:
exercises = get_all("exerciseinfo/", {"language": LANGUAGE})

# Um objeto de detalhe:
exercise = get_json("exerciseinfo/192/")
```

- `get_json(endpoint, params=None) -> dict`: devolve o objeto JSON sem o transformar.
- `get_all(endpoint, params=None) -> list[dict]`: reúne `results` de todas as páginas.
- Os endpoints são relativos à base `https://wger.de/api/v2/`; URLs absolutas
  dessa mesma base também são aceites, para seguir `next`.
- User-Agent, Accept JSON, timeout de 30 segundos e verificação HTTP já estão configurados.
- Os parâmetros recebidos não são alterados. `get_all` só os envia na primeira
  página, pois a URL `next` já contém os parâmetros seguintes.
- O idioma é explícito nos pedidos, usando `LANGUAGE`, cujo valor é `2`.
- Falhas de rede, HTTP, JSON ou paginação lançam `RuntimeError`. Não se devolve uma
  lista vazia para disfarçar erros; uma lista vazia significa pesquisa sem resultados.
- Não há repetição automática de pedidos. `get_all` pode percorrer muitas páginas;
  quando só interessa uma página, usar `get_json` e a ordenação/filtros adequados.

Verificado em 6 de novembro de 2026: um pedido público a `exerciseinfo/` devolveu
`results`, `count`, `next` e `previous`. Em cada exercício, `category` é um objeto,
`equipment` é uma lista de objetos e nome/descrição ficam em `translations`.
Mesmo com `language=2`, o exercício consultado trouxe traduções em vários idiomas.
Quem normaliza deve selecionar `translation["language"] == LANGUAGE` e definir
o comportamento para exercícios sem tradução inglesa (recomendação: ignorá-los).
O `id` usado para detalhes é o do exercício, não o da tradução.

Fonte primária para paginação e acesso público:
https://wger.readthedocs.io/en/latest/api/api.html
O catálogo Orbit também foi consultado; o recurso `exercise-list` não incluía
traduções, pelo que a estrutura de `exerciseinfo/` foi confirmada com leitura real.

### Formato comum entre colegas

Este é um contrato interno proposto para o grupo, não o JSON bruto da wger.
Os exemplos sintéticos em `tests/fixtures/exercises.json` já seguem este formato:

```json
{
  "id": 1,
  "name": "Bench press",
  "category": "Chest",
  "equipment": ["barbell", "bench"],
  "description": "<p>Press the barbell upwards.</p>",
  "muscles": ["pectoralis major", "triceps brachii"],
  "muscles_secondary": ["deltoid"]
}
```

`id` é inteiro; nome, categoria e descrição são strings; equipamento e músculos
são listas de strings. A descrição pode conter HTML. Quem consulta a API converte
os objetos e traduções para este formato. O campo `type` é acrescentado quando
o esforço for classificado: `compound`, `isolated`, `cardio` ou `other`.

### JSON e CSV

```python
from pathlib import Path
from fitlib.output import print_json, write_workout_csv

exercise = {
    "id": 1, "name": "Bench press", "category": "Chest",
    "equipment": ["barbell"], "type": "compound"
}
plan = {"chest": [exercise]}
print_json(plan)
write_workout_csv(plan, Path("treino.csv"))
```

- `print_json(data) -> None`: imprime dados serializáveis como JSON, com acentos
  e indentação. Cada comando deve imprimir um único documento JSON.
- `write_workout_csv(plan, path) -> None`: recebe `{alvo: [exercícios]}` e escreve
  uma linha por exercício, na ordem recebida, com cabeçalho fixo:
  `target,id,name,category,equipment,type`.
- Campos ausentes ficam vazios; campos adicionais são ignorados no CSV.
  Listas/objetos são JSON dentro da célula. Vírgulas, aspas e quebras de linha
  são escapadas pelo módulo `csv`.
- O ficheiro usa UTF-8 e é substituído se existir. Mesmo um plano vazio escreve
  o cabeçalho. A pasta deve existir; falhas de escrita lançam `OSError`.

## Três colegas em paralelo

Você fica responsável pelas bases `api.py`, `output.py` e pela integração da CLI.
Os três colegas podem seguir esta divisão sem editar os mesmos ficheiros:

| Pessoa | Ficheiro principal | Entrega |
| --- | --- | --- |
| Colega 1 | `fitlib/exercises.py` | a) top, b) search, normalização da API e ligação das alíneas c)/d) ao processamento. |
| Colega 2 | `fitlib/processing.py` | Limpeza HTML, regras de esforço e contagem de equipamento com `re`. |
| Colega 3 | `fitlib/workout.py` | e) separar alvos, pesquisar, aplicar filtro de esforço e limitar a N por alvo. |

O colega 1 concentra a aquisição dos dados. Para c), obtém o detalhe, normaliza
e chama `processing.classify_effort(exercise)`. Para d), pesquisa a categoria,
reúne descrições e chama a função de contagem do colega 2. As quatro funções
públicas existentes em `exercises.py` mantêm os nomes e argumentos.

Contratos a combinar antes de começar:

| Função | Resultado |
| --- | --- |
| `top_exercises(limit)` | Lista com até N exercícios recentes; incluir nome, categoria e equipamento. |
| `search_exercises(target, limit)` | Lista com até N exercícios no formato comum, incluindo id e descrição. |
| `exercise_type(exercise_id)` | String `compound`, `isolated`, `cardio` ou `other`. |
| `equipment_frequency(category)` | Lista de `{"equipment": "barbell", "count": 3}`, frequência decrescente. |
| `clean_description(description)` | Texto sem HTML e com espaços normalizados. |
| `classify_effort(exercise)` | Um dos quatro tipos, recebendo o formato comum. |
| `count_equipment(descriptions)` | Mesma estrutura de equipment_frequency, recebendo `list[str]`; assinatura já preparada para o colega 2 implementar. |
| `build_workout(targets, effort, limit)` | `{alvo: [exercícios com type]}`, até N por alvo. |

### Como não ficar à espera

1. Criar três branches a partir desta base: `feature/exercises`,
   `feature/processing` e `feature/workout`.
2. Todos usam o mesmo contrato e a fixture sintética. Os exemplos servem para
   testar os módulos, não para inventar respostas da API real.
3. O colega 1 testa HTTP com respostas guardadas e substitui temporariamente as
   funções de processamento ainda pendentes nos seus testes.
4. O colega 2 testa diretamente com a fixture, sem fazer pedidos HTTP.
5. O colega 3 substitui `exercises.search_exercises` e `exercises.exercise_type`
   nos testes. Assim verifica filtragem, alvos repetidos/vazios, limite, esforço
   `any` e ausência de resultados sem esperar pelo colega 1 ou 2.
6. Cada colega coloca os seus testes num ficheiro próprio: `test_exercises.py`,
   `test_processing.py` ou `test_workout.py`. A união final verifica os módulos juntos.

Exemplo para os testes do colega 3, usando `unittest.mock`:

```python
import json
from pathlib import Path
from unittest.mock import patch
from fitlib.workout import Effort, build_workout

data = json.loads(Path("tests/fixtures/exercises.json").read_text())
with patch("fitlib.workout.exercises.search_exercises", return_value=data), \
     patch("fitlib.workout.exercises.exercise_type", side_effect=lambda id: {1: "compound", 2: "isolated"}[id]):
    # Passará quando build_workout estiver implementada.
    plan = build_workout("chest", Effort.compound, 1)
```

O treino deve filtrar antes de aplicar o limite final. Pode pedir mais candidatos
à pesquisa se necessário; não deve prometer N quando só existem menos exercícios
compatíveis. `any` aceita todos os tipos. A classificação usada no teste é uma
substituição deliberada, não uma regra de classificação a copiar para produção.

Há dependências na integração final, mas os contratos e as substituições nos
testes permitem desenvolver os três módulos em paralelo.

## Executar os testes das bases

Na pasta `ALPCD_12`:

```bash
uv run python -m unittest discover -s tests -v
```

São testes HTTP contra um servidor temporário em localhost, sem acesso à wger,
e testes de ficheiros temporários. Também cobrem falhas de HTTP, formato,
timeout e apresentação de erros pela CLI. Não há dependências de teste adicionais.
Uma leitura real de `exerciseinfo/` foi verificada separadamente; os testes
locais não comprovam os filtros e regras de negócio ainda por implementar.
