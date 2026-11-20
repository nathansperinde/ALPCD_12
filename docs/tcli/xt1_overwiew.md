# XTcli — Lógica e navegação do terminal

> **Código:** `tcli.py` · **Entrada:** `main()` · **Interface:** perguntas e menus

**Neste guia:** [funcionamento](#parte-1--funcionamento) ·
[código linha por linha](#parte-2--código-explicado-linha-por-linha) · [verificação](#verificação)

## Parte 1 — Funcionamento

### 1. Responsabilidades e leitura dos guias

O TCLI gere sessões, consultas de exercícios, treinos locais e templates privados.
O menu de exercícios reutiliza as funções da FITCLI; a interface por comandos
continua disponível em `fitcli.py`. As consultas não recebem token, embora a
navegação atual apresente esse menu depois do login.

| Guia | Parte que explica em detalhe |
|---|---|
| Este documento | Arranque, menus, entrada partilhada e POST de autenticação |
| [Login](XTcli_login.md) | Credenciais, renovação, verificação e keyring |
| [Criação de contas](XTcli_criacao_contas.md) | Registo e confirmação da sessão |
| [Treinos no terminal](XTcli_treinos.md) | Perguntas, importação, apresentação e exportação |
| [Workouts](XWorkouts.md) | Validação, JSON, filtros e operações de templates |

Os blocos seguintes descrevem etapas diferentes. Uma caixa que refere outro
fluxo é uma chamada a esse fluxo, não a repetição de todas as suas decisões.

### 2. Bloco A — Arranque e ligação à conta

```mermaid
flowchart TD
start(["Executar tcli.py"]) --> prepare["Criar pasta local e apresentar cabeçalho"]
    prepare --> restore["Tentar renovar a última sessão do keyring"]
    restore --> token{"Há access token?"}
    token -->|Sim| menu["Entrar no menu autenticado: bloco B"]
    token -->|Não| connect["Perguntar por login ou criação de conta"]
    connect --> verified{"Foi obtido um token?"}
    verified -->|Sim| menu
    verified -->|Não| finish(["Terminar o TCLI"])
    classDef action fill:#dbeafe,stroke:#2563eb,color:#172554
    classDef ok fill:#dcfce7,stroke:#16a34a,color:#14532d
    classDef stop fill:#fee2e2,stroke:#dc2626,color:#7f1d1d
    class prepare,restore,connect action
    class menu ok
    class finish stop
```

Sem autenticação, o código mostra uma mensagem e termina: não abre um menu
alternativo nem executa consultas públicas automaticamente.

### 3. Bloco B — Ação no menu autenticado

```mermaid
flowchart TD
menu(["Menu da conta"]) --> action{"Escolha do utilizador"}
    action -->|Exercícios FITCLI| queries["Abrir menu público de consultas"]
    queries --> menu
    action -->|Criar ou importar| local["Obter treino local"]
    local --> export["Oferecer ações de exportação"]
    export --> menu
    action -->|Ver templates| templates["Consultar e apresentar templates privados"]
    templates --> menu
    action -->|Terminar, trocar ou sair| result["Devolver a ação a main: bloco C"]
    classDef action fill:#dbeafe,stroke:#2563eb,color:#172554
    classDef ok fill:#dcfce7,stroke:#16a34a,color:#14532d
    classDef stop fill:#fee2e2,stroke:#dc2626,color:#7f1d1d
    class local,export,templates action
    class result ok
```

### 4. Bloco C — Saída e troca de conta

```mermaid
flowchart TD
result(["Receber ação do menu"]) --> clear["Limpar access token em memória"]
    clear --> action{"Qual foi a ação?"}
    action -->|Terminar sessão| message["Informar que o login automático fica guardado"]
    message --> connect["Voltar ao fluxo de ligação"]
    action -->|Trocar de conta| connect
    action -->|Sair ou cancelar| finish(["Terminar"])
    classDef action fill:#dbeafe,stroke:#2563eb,color:#172554
    classDef ok fill:#dcfce7,stroke:#16a34a,color:#14532d
    classDef stop fill:#fee2e2,stroke:#dc2626,color:#7f1d1d
    class clear,message action
    class connect ok
    class finish stop
```

> **Terminar sessão não apaga o keyring.** `main()` limpa a sessão em memória,
> mas a próxima execução pode autenticar automaticamente a última conta guardada.

### 5. Bloco D — Falha de uma operação

```mermaid
flowchart TD
operation(["Operação em curso"]) --> error{"O que aconteceu?"}
    error -->|Erro de dados, rede ou ficheiro| show["Apresentar mensagem e inspecionar a causa"]
    show --> expired{"HTTP 403 com token_not_valid?"}
    expired -->|Sim| login["Sair do menu para voltar ao login"]
    expired -->|Não| menu["Voltar ao menu"]
    error -->|Ctrl+C ou fim da entrada| cancel["Informar cancelamento"]
    cancel --> menu
    classDef action fill:#dbeafe,stroke:#2563eb,color:#172554
    classDef ok fill:#dcfce7,stroke:#16a34a,color:#14532d
    classDef stop fill:#fee2e2,stroke:#dc2626,color:#7f1d1d
    class show,cancel action
    class menu ok
    class login stop
```

O código não repete POSTs depois de um erro. Nem todo HTTP 403 significa sessão
expirada: o retorno ao login depende também do código `token_not_valid`.

### 6. Base partilhada

| Função | Entrada | Resultado |
|---|---|---|
| `post_data` | URL e dicionário JSON | Objeto de resposta ou RuntimeError |
| `text` | Pergunta e comprimento máximo | Texto limpo ou cancelamento |
| `number` | Pergunta e máximo | Inteiro de 1 até ao máximo |
| `choose` | Pergunta e lista de objetos | Objeto, lista de objetos ou retorno/cancelamento |

Autenticação e operações privadas não usam a cache pública. Os catálogos e detalhes
públicos dos treinos usam `disk`, conforme [CACHE.md](../CACHE.md).

### 7. Menu de exercícios: reutilizar as alíneas

```mermaid
flowchart TD
    start(["Exercícios FITCLI"]) --> choice{"Foi escolhida uma consulta?"}
    choice -->|Não ou Voltar| finish(["Regressar ao menu da conta"])
    choice -->|Sim| input["Pedir os argumentos com text e number"]
    input --> call["Chamar exercises ou extras"]
    call --> display["Mostrar nomes portugueses e resultado JSON"]
    display --> finish
```

| Opção | Função reutilizada |
|---|---|
| Recentes | `exercises.top_exercises` |
| Pesquisar músculo/categoria | `exercises.search_exercises` |
| Pesquisar por texto | `extras.find_exercises` |
| Classificar exercício | `exercises.exercise_type` |
| Comparar exercícios | `extras.compare_exercises` |
| Frequência de equipamento | `exercises.equipment_frequency` |
| Plano por esforço | `exercises.build_workout` |

O menu usa os parâmetros básicos das funções. Pesquisa profunda, descrição,
refresh, exportação CSV e os extras difficulty/ingredient continuam disponíveis
na CLI normal; não se acrescentaram perguntas para todas as opções.
Os nomes são traduzidos depois da seleção/classificação, preservando as regras
inglesas das alíneas. Falhas de tradução mantêm o nome anterior.

## Parte 2 — Código explicado linha por linha

Os trechos abaixo são cópias do código atual, não versões alternativas da implementação.
Cada tabela explica **todas as linhas não vazias de código do trecho**. A coluna
“Linha” refere-se ao ficheiro original; comentários separadores não precisam de
uma explicação repetida. Nas funções longas, os recortes são consecutivos e devem
ser lidos em conjunto: um recorte interior não é uma função autónoma para executar.

### Imports e configuração

#### Bibliotecas e cabeçalhos

[Fonte: tcli.py, linha 1](../../tcli.py#L1)

```python
import requests
import questionary
import keyring

from fitlib import api, exercises, extras, workouts
from fitlib.api import HEADERS, HTTP_ERRORS
```

| Linha | Explicação |
|---|---|
| 1 | Importa o cliente HTTP usado no login, registo e verificação de tokens. |
| 2 | Importa as perguntas e menus interativos. |
| 3 | Importa o acesso ao armazenamento de credenciais. |
| 5 | Reutiliza os módulos partilhados de API, exercícios, extras e treinos. |
| 6 | Reutiliza os cabeçalhos e mensagens HTTP definidos em `fitlib/api.py`. |

As configurações `HEADERS` e `HTTP_ERRORS` são definidas em `fitlib/api.py` e importadas pela TCLI, evitando repetir os mesmos dicionários nos dois ficheiros.

### `post_data()`

Helper partilhado por login, registo e renovação. Não guarda resultados em cache e mantém a causa dos erros para o chamador poder interpretar a resposta HTTP.

#### Pedido e resposta

[Fonte: tcli.py, linha 13](../../tcli.py#L13)

```python
def post_data(url: str, dados: dict) -> dict:
    try:
        response = requests.post(
            url,
            json=dados,
            headers=HEADERS,
            timeout=15
        )

        response.raise_for_status()

        data = response.json()

        if not isinstance(data, dict):
            raise RuntimeError(
                "The API did not return a JSON object."
            )

        return data
```

| Linha | Explicação |
|---|---|
| 13 | Define `post_data` e os parâmetros/resultado usados neste bloco. |
| 14 | Agrupa o pedido e a leitura da resposta para tratar as falhas abaixo. |
| 15 | Inicia um POST HTTP direto, sem utilizar a cache pública. |
| 16 | Usa o URL recebido pelo chamador. |
| 17 | Envia o dicionário dados como corpo JSON. |
| 18 | Aplica os cabeçalhos comuns. |
| 19 | Limita a espera do pedido a 15 segundos. |
| 20 | Fecha a chamada HTTP. |
| 22 | Converte uma resposta HTTP de erro numa exceção. |
| 24 | Tenta descodificar o corpo da resposta como JSON. |
| 26 | Exige um objeto JSON; listas e outros tipos não são aceites aqui. |
| 27 | Inicia o erro de formato da resposta. |
| 28 | Define a mensagem para um JSON que não é objeto. |
| 29 | Fecha a construção do erro, que é propagado como RuntimeError. |
| 31 | Devolve o dicionário quando o pedido e a validação têm sucesso. |

#### Estados HTTP e timeout

[Fonte: tcli.py, linha 33](../../tcli.py#L33)

```python
    except requests.exceptions.HTTPError as error:
        status = error.response.status_code

        message = HTTP_ERRORS.get(
            status,
            "Server error." if status >= 500 else "HTTP error."
        )

        raise RuntimeError(
            f"HTTP {status}: {message}"
        ) from error

    except requests.exceptions.Timeout as error:
        raise RuntimeError(
            "The request timed out."
        ) from error
```

| Linha | Explicação |
|---|---|
| 33 | Trata respostas HTTP malsucedidas. |
| 34 | Lê o estado da resposta associado ao erro. |
| 36 | Procura uma mensagem no mapa HTTP_ERRORS. |
| 37 | Usa o estado HTTP como chave da procura. |
| 38 | Para estados não mapeados, distingue erros de servidor dos restantes. |
| 39 | Fecha a escolha da mensagem. |
| 41 | Inicia a conversão do erro HTTP para RuntimeError. |
| 42 | Inclui estado e mensagem no texto apresentado ao chamador. |
| 43 | Preserva a exceção original em __cause__, permitindo aos fluxos ler o HTTP. |
| 45 | Trata o tempo limite de rede. |
| 46 | Inicia uma mensagem uniforme de timeout. |
| 47 | Explica que o pedido excedeu o tempo permitido. |
| 48 | Preserva a causa original do timeout. |

#### Ligação e JSON

[Fonte: tcli.py, linha 50](../../tcli.py#L50)

```python
    except requests.exceptions.ConnectionError as error:
        raise RuntimeError(
            "Connection error."
        ) from error

    except ValueError as error:
        raise RuntimeError(
            "Invalid JSON response."
        ) from error

    except requests.exceptions.RequestException as error:
        raise RuntimeError(
            "Request failed."
        ) from error
```

| Linha | Explicação |
|---|---|
| 50 | Trata falhas de ligação. |
| 51 | Inicia o erro de ligação apresentado pela aplicação. |
| 52 | Define a mensagem de falha de ligação. |
| 53 | Preserva a causa original da ligação. |
| 55 | Trata falha na descodificação JSON. |
| 56 | Inicia a mensagem uniforme de JSON inválido. |
| 57 | Define a mensagem de formato inválido. |
| 58 | Preserva a causa da falha de JSON. |
| 60 | Trata outras exceções de requests não abrangidas pelos casos anteriores. |
| 61 | Inicia o erro genérico de pedido. |
| 62 | Define a mensagem genérica de falha HTTP. |
| 63 | Preserva a causa original para diagnóstico pelo chamador. |

### `text()`

Entrada textual com comprimento limitado. Cancelar levanta KeyboardInterrupt para abandonar a operação que está a usar o campo.

#### text

[Fonte: tcli.py, linha 332](../../tcli.py#L332)

```python
def text(prompt, maximum=1000):
    while True:
        answer = questionary.text(prompt).ask()
        if answer is None:
            raise KeyboardInterrupt
        if 1 <= len(answer.strip()) <= maximum:
            return answer.strip()
        print(f"Introduza texto entre 1 e {maximum} caracteres.")
```

| Linha | Explicação |
|---|---|
| 332 | Define `text` e os parâmetros/resultado usados neste bloco. |
| 333 | Repete a pergunta de texto até obter uma entrada válida ou cancelamento. |
| 334 | Apresenta o prompt recebido e lê a resposta. |
| 335 | Deteta cancelamento. |
| 336 | Propaga KeyboardInterrupt para o nível que controla a operação. |
| 337 | Exige 1 a maximum caracteres depois de remover espaços exteriores. |
| 338 | Devolve o texto limpo. |
| 339 | Explica o intervalo de comprimento e repete a pergunta. |

### `number()`

Entrada de um inteiro positivo com limite superior. Uma conversão inválida repete a pergunta, em vez de terminar a aplicação.

#### number

[Fonte: tcli.py, linha 342](../../tcli.py#L342)

```python
def number(prompt, maximum):
    while True:
        answer = questionary.text(prompt).ask()
        if answer is None:
            raise KeyboardInterrupt
        try:
            value = int(answer)
            if 1 <= value <= maximum:
                return value
        except ValueError:
            pass
        print(f"Introduza um número inteiro entre 1 e {maximum}.")
```

| Linha | Explicação |
|---|---|
| 342 | Define `number` e os parâmetros/resultado usados neste bloco. |
| 343 | Repete a pergunta numérica até obter um inteiro válido. |
| 344 | Lê a entrada como texto. |
| 345 | Deteta cancelamento. |
| 346 | Interrompe a operação atual. |
| 347 | Protege a conversão numérica. |
| 348 | Converte a resposta para inteiro. |
| 349 | Exige valor entre 1 e maximum. |
| 350 | Devolve o inteiro válido. |
| 351 | Captura texto que não representa um inteiro. |
| 352 | Não encerra a operação: continua para a mensagem e nova pergunta. |
| 353 | Explica o intervalo permitido. |

### `choose()`

Constrói menus a partir de objetos. A etiqueta pode mostrar o ID, mas o valor devolvido continua a ser o objeto completo.

#### choose

[Fonte: tcli.py, linha 356](../../tcli.py#L356)

```python
def choose(prompt, items, multiple=False, selected=False):
    if not items:
        print("Não existem opções disponíveis.")
        return [] if multiple else None
    choices = []
    for item in items:
        name = item["name"]
        if "id" in item:
            name += f" [#{item['id']}]"
        choices.append(questionary.Choice(name, value=item, checked=selected))
    if multiple:
        answer = questionary.checkbox(prompt, choices=choices).ask()
        if answer is None:
            raise KeyboardInterrupt
        return answer
    choices.append(questionary.Choice("Voltar", value=False))
    return questionary.select(prompt, choices=choices).ask()
```

| Linha | Explicação |
|---|---|
| 356 | Define `choose` e os parâmetros/resultado usados neste bloco. |
| 357 | Trata a ausência de opções antes de abrir um menu. |
| 358 | Informa que não há opções disponíveis. |
| 359 | Devolve lista vazia na seleção múltipla, ou None na seleção simples. |
| 360 | Inicia a lista de opções apresentadas. |
| 361 | Percorre os objetos recebidos. |
| 362 | Começa a etiqueta com o nome do objeto. |
| 363 | Verifica se pode mostrar o ID ao lado do nome. |
| 364 | Acrescenta o ID apenas à etiqueta, preservando o objeto original. |
| 365 | Cria a opção cujo valor é o objeto; selected controla a pré-seleção. |
| 366 | Escolhe o modo de seleção múltipla. |
| 367 | Apresenta checkboxes com as opções construídas. |
| 368 | Deteta cancelamento dos checkboxes. |
| 369 | Interrompe a operação atual. |
| 370 | Devolve a lista de objetos selecionados. |
| 371 | Na seleção simples acrescenta Voltar com valor False. |
| 372 | Devolve a opção escolhida ou o valor de retorno/cancelamento do menu. |

### `show_exercises()`

[Fonte: tcli.py, linha 378](../../tcli.py#L378)

```python
def show_exercises(result):
    """Apresentar nomes portugueses sem alterar as regras das consultas."""
    items = result if isinstance(result, list) else []
    if isinstance(result, dict):
        for value in result.values():
            if isinstance(value, list):
                items.extend(value)
    for item in items:
        if isinstance(item, dict) and "id" in item and "name" in item:
            try:
                raw = api.get_data(f"exerciseinfo/{item['id']}/")
                item["name"] = workouts.exercise_name(raw) or item["name"]
            except RuntimeError as error:
                print(f"Não foi possível atualizar o nome do exercício #{item['id']}: {error}")
    exercises.print_json(result)
```

| Linha | Explicação |
|---|---|
| 378 | Define a apresentação dos resultados das consultas públicas. |
| 379 | Documenta que a tradução é apenas de apresentação. |
| 380 | Usa diretamente os itens de uma lista, ou começa com uma lista vazia. |
| 381 | Trata planos por alvo, que são dicionários de listas. |
| 382 | Percorre as coleções de resultados desse dicionário. |
| 383 | Seleciona apenas os valores que são listas. |
| 384 | Reúne os exercícios dessas listas para atualizar a apresentação. |
| 385 | Percorre os itens a apresentar. |
| 386 | Só procura nomes de objetos com ID e name; contagens e classificações não precisam disso. |
| 387 | Protege a consulta pública usada para obter traduções. |
| 388 | Reutiliza get_data e a cache pública dos detalhes do exercício. |
| 389 | Prefere português, depois inglês, conservando o nome anterior se não houver tradução. |
| 390 | Trata falha HTTP/JSON comunicada pela API. |
| 391 | Mostra o aviso e conserva o nome guardado; não repete a consulta automaticamente. |
| 392 | Apresenta o resultado final em JSON através do helper partilhado. |

### `exercise_menu()`

[Fonte: tcli.py, linha 395](../../tcli.py#L395)

```python
def exercise_menu():
    action = questionary.select("Exercícios FITCLI:", choices=[
        "Recentes", "Pesquisar músculo/categoria", "Pesquisar por texto",
        "Classificar exercício", "Comparar exercícios", "Frequência de equipamento",
        "Plano por esforço", "Voltar"]).ask()
    result = None
    if action == "Recentes":
        result = exercises.top_exercises(number("Quantidade:", 999))
    elif action == "Pesquisar músculo/categoria":
        result = exercises.search_exercises(text("Músculo/categoria:"), number("Quantidade:", 999))
    elif action == "Pesquisar por texto":
        result = extras.find_exercises(text("Pesquisa:"), number("Quantidade:", 999))
    elif action == "Classificar exercício":
        result = exercises.exercise_type(number("ID:", 2147483647))
```

| Linha | Explicação |
|---|---|
| 395 | Define o menu de consultas públicas, sem receber token nem duplicar as pesquisas. |
| 396 | Abre a pergunta de seleção das funcionalidades da FITCLI. |
| 397 | Disponibiliza listagem e pesquisas por músculo/categoria ou texto. |
| 398 | Disponibiliza classificação, comparação e contagem de equipamento. |
| 399 | Acrescenta plano por esforço e Voltar e recebe a escolha. |
| 400 | Começa sem resultado, para que Voltar ou cancelar não imprimam uma resposta. |
| 401 | Identifica a opção de exercícios recentes. |
| 402 | Pede a quantidade e chama a alínea A. |
| 403 | Identifica a pesquisa por músculo ou categoria. |
| 404 | Pede alvo/quantidade e reutiliza a alínea B. |
| 405 | Identifica a pesquisa por texto. |
| 406 | Pede pesquisa/quantidade e usa a função atual em extras.py. |
| 407 | Identifica a classificação de um exercício por ID. |
| 408 | Pede um ID positivo e reutiliza a alínea C. |

[Fonte: tcli.py, linha 409](../../tcli.py#L409)

```python
    elif action == "Comparar exercícios":
        ids = []
        for value in text("IDs separados por vírgulas:").split(","):
            ids.append(int(value.strip()))
        result = extras.compare_exercises(ids)
    elif action == "Frequência de equipamento":
        result = exercises.equipment_frequency(text("Categoria:"))
    elif action == "Plano por esforço":
        target = text("Alvos separados por vírgulas:")
        effort = questionary.select("Esforço:", choices=["compound", "isolated", "any"]).ask()
        if effort:
            result = exercises.build_workout(target, effort, number("Quantidade por alvo:", 999))
    if result is not None:
        show_exercises(result)
```

| Linha | Explicação |
|---|---|
| 409 | Identifica a comparação entre exercícios. |
| 410 | Inicia a lista de IDs para comparação. |
| 411 | Divide a entrada pelos separadores de vírgula. |
| 412 | Remove espaços e converte cada ID; erros são tratados pelo menu autenticado. |
| 413 | Delega a validação e comparação em extras.py. |
| 414 | Identifica a contagem de equipamento. |
| 415 | Pede a categoria e reutiliza a alínea D. |
| 416 | Identifica a criação de plano local por esforço. |
| 417 | Pede os alvos separados por vírgulas. |
| 418 | Pede o esforço entre as três strings permitidas, sem a antiga classe Effort. |
| 419 | Só avança se o esforço não foi cancelado. |
| 420 | Pede a quantidade por alvo e reutiliza build_workout da alínea E. |
| 421 | Verifica se uma ação produziu um resultado, incluindo listas vazias. |
| 422 | Traduz apenas os nomes apresentados e imprime o resultado. |

### `authenticated_menu()`

Encaminha ações para treinos e templates. Um token rejeitado regressa ao fluxo de autenticação; um cancelamento da operação regressa ao menu.

#### Escolha e execução

[Fonte: tcli.py, linha 523](../../tcli.py#L523)

```python
def authenticated_menu(token):
    while token:
        action = questionary.select("Conta autenticada. O que deseja fazer?", choices=[
            "Exercícios FITCLI", "Criar treino", "Importar treino local", "Ver templates exportados",
            "Terminar sessão", "Trocar de conta", "Sair"]).ask()
        if action in (None, "Terminar sessão", "Trocar de conta", "Sair"):
            return action
        try:
            if action == "Exercícios FITCLI":
                exercise_menu()
            elif action in ("Criar treino", "Importar treino local"):
                workout = create_workout() if action == "Criar treino" else import_workout()
                if workout:
                    workout_actions(workout, token)
            elif action == "Ver templates exportados":
                template_menu(token)
```

| Linha | Explicação |
|---|---|
| 523 | Define `authenticated_menu` e os parâmetros/resultado usados neste bloco. |
| 524 | Mantém a navegação enquanto existe token de sessão. |
| 525 | Inicia o menu principal da conta autenticada. |
| 526 | Oferece consultas públicas, criação/importação local e consulta de templates. |
| 527 | Acrescenta as opções de terminar sessão, trocar conta e sair; recebe a escolha. |
| 528 | Identifica cancelamento e ações que devem sair deste menu. |
| 529 | Devolve a ação para main decidir se pede login ou termina. |
| 530 | Protege a execução de uma operação do menu. |
| 531 | Seleciona o ramo das consultas públicas da FITCLI. |
| 532 | Abre o menu de exercícios e regressa quando a consulta terminar. |
| 533 | Seleciona o ramo de criar ou importar um treino. |
| 534 | Chama apenas a função correspondente à escolha. |
| 535 | Verifica se a operação devolveu efetivamente um treino. |
| 536 | Nesse caso abre as ações de exportação desse treino. |
| 537 | Seleciona o ramo de consulta de templates. |
| 538 | Abre o menu de templates autenticados. |

#### Erros e cancelamento

[Fonte: tcli.py, linha 539](../../tcli.py#L539)

```python
        except (RuntimeError, ValueError, OSError) as error:
            print(f"Erro: {error}")
            # A wger usa 403 também para JWT expirado. Não repetir POSTs automaticamente.
            cause = error
            while cause.__cause__ is not None:
                cause = cause.__cause__
            if isinstance(cause, requests.exceptions.HTTPError) and cause.response is not None:
                try:
                    code = cause.response.json().get("code")
                except ValueError:
                    code = None
                if cause.response.status_code == 403 and code == "token_not_valid":
                    print("A sessão expirou ou foi rejeitada. Volte a fazer login.")
                    return "Trocar de conta"
        except (KeyboardInterrupt, EOFError):
            print("Operação cancelada.")
    return "Sair"
```

| Linha | Explicação |
|---|---|
| 539 | Trata erros da operação, validação ou sistema de ficheiros. |
| 540 | Mostra a mensagem do erro. |
| 542 | Começa a procurar a causa original do erro. |
| 543 | Continua enquanto houver uma exceção encadeada. |
| 544 | Avança para a exceção que originou o problema. |
| 545 | Só analisa estados se a causa for HTTP e tiver resposta. |
| 546 | Protege a leitura do corpo de erro. |
| 547 | Tenta obter o código de erro devolvido pela API. |
| 548 | Trata corpo que não seja JSON válido. |
| 549 | Usa None quando não conseguiu ler um código. |
| 550 | Distingue HTTP 403 de token rejeitado de um simples erro de permissão. |
| 551 | Explica que será preciso autenticar novamente. |
| 552 | Devolve a ação Trocar de conta; não repete a operação que falhou. |
| 553 | Trata Ctrl+C ou fim da entrada durante uma operação. |
| 554 | Informa o cancelamento e volta ao menu. |
| 555 | Sem token no ciclo, devolve Sair. |

### `main()`

Coordena restauro, login e navegação. O token em memória é limpo ao sair do menu, mas o código não apaga os refresh tokens guardados.

#### Arranque e restauro

[Fonte: tcli.py, linha 561](../../tcli.py#L561)

```python
def main() -> str | None:
    workouts.WORKOUTS_DIR.mkdir(exist_ok=True)
    print("========= FIT TCLI =========")
    access_token = None

    try:
        try:
            last_username = keyring.get_password("FITCLI-wger", "last_username")
            access_token = refresh_login(last_username)
        except (RuntimeError, keyring.errors.KeyringError, OSError):
            print("Não foi possível restaurar a sessão. Pode fazer login novamente.")
```

| Linha | Explicação |
|---|---|
| 561 | Define `main` e os parâmetros/resultado usados neste bloco. |
| 562 | Garante a existência da pasta local de treinos no arranque. |
| 563 | Apresenta o cabeçalho do programa. |
| 564 | Começa sem access token em memória. |
| 566 | Protege o arranque e a navegação contra cancelamento. |
| 567 | Isola a tentativa de restauro automático. |
| 568 | Lê no keyring a identificação da última conta. |
| 569 | Tenta renovar a sessão dessa conta. |
| 570 | Trata falhas de renovação, keyring ou sistema durante o restauro. |
| 571 | Informa que ainda é possível fazer login manualmente. |

#### Navegação e fim da sessão

[Fonte: tcli.py, linha 573](../../tcli.py#L573)

```python
        while True:
            if not access_token:
                access_token = connection_questionary()
            if not access_token:
                print("A utilizar o FITCLI sem autenticação.")
                return None

            action = authenticated_menu(access_token)
            access_token = None
            if action == "Terminar sessão":
                print("Sessão terminada. O login automático mantém-se no próximo arranque.")
            elif action != "Trocar de conta":
                return None
    except (KeyboardInterrupt, EOFError):
        return None
```

| Linha | Explicação |
|---|---|
| 573 | Inicia o ciclo que permite trocar ou voltar a autenticar contas. |
| 574 | Verifica se ainda não tem um access token. |
| 575 | Pede login/registo apenas quando necessário. |
| 576 | Verifica se o utilizador terminou a ligação sem obter uma sessão. |
| 577 | Mostra a mensagem de uso sem autenticação. |
| 578 | Encerra o TCLI; não abre um menu público de exercícios. |
| 580 | Entrega o token ao menu autenticado e recebe a ação de saída. |
| 581 | Limpa o access token em memória depois desse menu. |
| 582 | Identifica a ação Terminar sessão. |
| 583 | Explica que os dados guardados permitem login automático no próximo arranque. |
| 584 | Se não foi pedido trocar de conta, termina a aplicação. |
| 585 | Devolve None e encerra o ciclo de navegação. |
| 586 | Captura Ctrl+C ou fim da entrada na navegação principal. |
| 587 | Termina de forma controlada, sem apresentar um traceback ao utilizador. |

### Ponto de entrada

#### Execução direta

[Fonte: tcli.py, linha 590](../../tcli.py#L590)

```python
if __name__ == "__main__":
    main()
```

| Linha | Explicação |
|---|---|
| 590 | Só inicia a aplicação quando este ficheiro é executado diretamente. |
| 591 | Chama main; importar tcli.py não inicia as perguntas. |

## Verificação

A aplicação pode ser iniciada a partir de `ALPCD_12`:

```bash
uv run python tcli.py
```

| Caso | Resultado a verificar com dados simulados |
|---|---|
| Importar o módulo | Não iniciar perguntas nem pedidos HTTP |
| Sem sessão guardada | Oferecer login/registo |
| Exercícios FITCLI | Encaminhar as sete opções para as funções existentes |
| Voltar/cancelar no menu de exercícios | Regressar sem executar uma consulta |
| Recusar a ligação | Terminar sem abrir consultas públicas |
| Terminar sessão | Limpar token em memória, sem apagar keyring |
| Erro de permissão | Mostrar erro e regressar ao menu |
| Token rejeitado | Regressar ao login sem repetir o pedido falhado |
| Cancelar uma operação | Regressar ao menu sem encerrar à força |

Estes casos descrevem verificações recomendadas, não execuções reais novas.
A cópia atual não inclui uma pasta `tests/`. Para testes automáticos, simular
requests, keyring e questionary e usar pastas temporárias: não criar contas,
guardar tokens reais ou exportar templates apenas para validar a documentação.

Voltar ao [README oficial](../../README.md).