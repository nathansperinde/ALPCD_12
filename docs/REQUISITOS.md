# Requisitos do TP1 — ALPCD 2026/27

Fonte: `ALPCD___TP1__26-1.pdf`, quatro páginas, lidas integralmente.

## Bibliotecas e configuração

- `requests`: consumir a API pública `https://wger.de/api/v2/`.
- `re`: processar/limpar descrições e extrair menções a equipamento.
- `typer`: construir a CLI e validar argumentos.
- `json` e `csv`: saídas pedidas, usando a biblioteca padrão.
- Leitura dos dados públicos sem autenticação.
- Identificar os pedidos com um cabeçalho User-Agent.
- Verificar status HTTP e implementar paginação quando necessário.
- Usar `language=2` para inglês ao obter os exercícios pedidos.

## Alíneas

| Comando | Entrada | Saída e responsabilidade |
| --- | --- | --- |
| `top` | N | N exercícios mais recentes; JSON com nome, categoria e equipamento. |
| `search` | músculo e/ou categoria, N | Exercícios correspondentes, limitados a N, em JSON. |
| `type` | exercise_id | Inferir compound/isolated/cardio/other usando descrição, categoria e músculos; apresentar o tipo no terminal. |
| `equipment` | categoria | Extrair com re menções como barbell/dumbbell/cable/machine/bodyweight; contar e ordenar por frequência decrescente; saída JSON. |
| `workout` | alvos separados por vírgula, compound/isolated/any, N | Reutilizar as alíneas anteriores; até N exercícios por alvo; JSON ou exportação com `--csv ficheiro.csv`. |

O exemplo de workout no PDF mostra um exercício isolated sob um pedido compound.
Na implementação, deve prevalecer o filtro de esforço descrito no texto da alínea.
Os rótulos cardio/other são uma proposta de normalização para os tipos cardio/outro
do enunciado; as regras de inferência ainda precisam de ser definidas pelo grupo.

## Ordem de implementação

1. Explorar `https://wger.de/api/v2/schema/ui` para confirmar rotas e campos.
2. Implementar pedidos, tratamento de erros HTTP e paginação em `fitlib/api.py`.
3. Implementar top e search em `fitlib/exercises.py`.
4. Implementar limpeza, inferência de esforço e contagem de equipamento.
5. Compor o plano de treino e implementar as saídas JSON/CSV.

Entrega no repositório do grupo até 21 de novembro. O trabalho será apresentado e
defendido por todos os elementos, em data a definir pelos docentes.
