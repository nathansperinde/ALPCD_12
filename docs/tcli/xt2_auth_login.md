# XTcli — Login e sessão guardada

> **Código:** `tcli.py` · **Entrada interativa:** `connection_questionary()`

**Neste guia:** [funcionamento](#parte-1--funcionamento) ·
[código linha por linha](#parte-2--código-explicado-linha-por-linha) · [verificação](#verificação)

## Parte 1 — Funcionamento

### 1. Objetivo e dados da sessão

Entrar numa conta com credenciais ou renovar uma sessão previamente guardada.
A criação de conta tem um [guia próprio](XTcli_criacao_contas.md).

| Dado | Utilização | Persistência |
|---|---|---|
| Palavra-passe | Pedido de login | Não é guardada pelo código |
| Access token | Pedidos da sessão atual | Memória do processo |
| Refresh token | Renovar o access token | Keyring: serviço `FITCLI-wger`, chave do utilizador |
| `last_username` | Identificar a última conta | Outra entrada no mesmo serviço do keyring |

### 2. Bloco A — Escolha e nome da conta

```mermaid
flowchart TD
start(["Ligar a uma conta?"]) --> choice{"Ação"}
    choice -->|Criar conta| register["Delegar no guia de criação de contas"]
    choice -->|Fazer login| ask["Pedir nome e remover espaços exteriores"]
    ask --> valid{"Nome preenchido e não reservado?"}
    valid -->|Não| ask
    valid -->|Sim| restore["Tentar renovação: bloco B"]
    choice -->|Não ou cancelar| finish(["Devolver None"])
    classDef action fill:#dbeafe,stroke:#2563eb,color:#172554
    classDef ok fill:#dcfce7,stroke:#16a34a,color:#14532d
    classDef stop fill:#fee2e2,stroke:#dc2626,color:#7f1d1d
    class ask,restore action
    class register ok
    class finish stop
```


### 3. Bloco B — Tentar renovar a sessão guardada

```mermaid
flowchart TD
start(["refresh_login: nome válido"]) --> read["Ler refresh token do keyring"]
    read --> token{"Existe token textual não vazio?"}
    token -->|Não| manual["Avançar para login manual: bloco C"]
    token -->|Sim| renew["POST de renovação e validação da resposta"]
    renew --> result{"Resultado"}
    result -->|HTTP 400 ou 401| manual
    result -->|Tokens válidos| save["Guardar refresh token; verificar access token"]
    save --> verified{"Access token aceite?"}
    verified -->|Sim| ready["Devolver access token"]
    verified -->|Não| manual
    result -->|Outra falha| error["Propagar erro ao fluxo de login"]
    classDef action fill:#dbeafe,stroke:#2563eb,color:#172554
    classDef ok fill:#dcfce7,stroke:#16a34a,color:#14532d
    classDef stop fill:#fee2e2,stroke:#dc2626,color:#7f1d1d
    class read,renew,save action
    class ready ok
    class error stop
```


Este bloco trata um nome já validado. Antes de ler o keyring, a função também
rejeita nome ausente e a chave reservada `last_username`.

**Ordem importante:** guardar a rotação do refresh token acontece antes da
verificação do access token. Se o servidor já tiver substituído o token anterior,
adiar a gravação poderia perder a sessão renovável. A verificação usa o bloco D.

### 4. Bloco C — Login com palavra-passe

```mermaid
flowchart TD
ask(["Pedir palavra-passe oculta"]) --> valid{"Está preenchida?"}
    valid -->|Não| retry["Recomeçar as perguntas de login"]
    valid -->|Sim| request["POST de login com username e password"]
    request --> result{"Meta autenticada e dois tokens válidos?"}
    result -->|Não ou erro| again["Mostrar mensagem e oferecer repetição"]
    result -->|Sim| verify["Verificar access token: bloco D"]
    verify --> accepted{"Token aceite?"}
    accepted -->|Sim| save["Guardar refresh token e última conta; devolver access token"]
    accepted -->|Não ou erro| again
    again -->|Confirmar| retry
    again -->|Cancelar| finish(["Devolver None"])
    classDef action fill:#dbeafe,stroke:#2563eb,color:#172554
    classDef ok fill:#dcfce7,stroke:#16a34a,color:#14532d
    classDef stop fill:#fee2e2,stroke:#dc2626,color:#7f1d1d
    class ask,request,verify action
    class save ok
    class finish stop
```


Uma falha de gravação no keyring não impede devolver um access token já verificado.
A tentativa de atualizar `last_username` ocorre apenas se o refresh token foi guardado.

### 5. Bloco D — Verificação do access token

```mermaid
flowchart TD
start(["verify_access_token"]) --> request["POST em token/verify"]
    request --> status{"Resposta HTTP"}
    status -->|400 ou 401| rejected["Devolver False"]
    status -->|Sucesso| accepted["Devolver True"]
    status -->|Outro erro ou falha de rede| error["Lançar RuntimeError"]
    classDef action fill:#dbeafe,stroke:#2563eb,color:#172554
    classDef ok fill:#dcfce7,stroke:#16a34a,color:#14532d
    classDef stop fill:#fee2e2,stroke:#dc2626,color:#7f1d1d
    class request action
    class accepted ok
    class rejected,error stop
```


### 6. Erros e cancelamento

| Situação | Comportamento atual |
|---|---|
| Nome vazio ou `last_username` | Voltar a perguntar, sem enviar credenciais |
| Token guardado rejeitado | Pedir palavra-passe |
| Palavra-passe vazia | Voltar às perguntas de login |
| Login incompleto ou token recusado | Mensagem e opção de nova tentativa |
| Erro HTTP/rede/JSON | Mensagem controlada; renovação não trata todo erro como token expirado |
| Falha de keyring | Permitir login manual ou manter a sessão já verificada em memória |
| Cancelar uma pergunta, Ctrl+C ou fim da entrada | Terminar o fluxo sem token |

MFA e outras etapas adicionais não são concluídas pelo programa. O login não
revela se a falha foi utilizador inexistente ou palavra-passe incorreta.
O helper `post_data` está explicado em [XTcli.md](XTcli.md#parte-2--código-explicado-linha-por-linha).

## Parte 2 — Código explicado linha por linha

Os trechos abaixo são cópias do código atual, não versões alternativas da implementação.
Cada tabela explica **todas as linhas não vazias de código do trecho**. A coluna
“Linha” refere-se ao ficheiro original; comentários separadores não precisam de
uma explicação repetida. Nas funções longas, os recortes são consecutivos e devem
ser lidos em conjunto: um recorte interior não é uma função autónoma para executar.

### `login_account()`

Seleciona o endpoint de login e reutiliza post_data. O helper HTTP e as mensagens comuns são explicados em [XTcli.md](XTcli.md#parte-2--código-explicado-linha-por-linha).

#### login_account

[Fonte: tcli.py, linha 80](../../tcli.py#L80)

```python
def login_account(dados: dict) -> dict:
    return post_data(
        "https://wger.de/allauth/app/v1/auth/login",
        dados
    )
```

| Linha | Explicação |
|---|---|
| 80 | Define `login_account` e os parâmetros/resultado usados neste bloco. |
| 81 | Delega o pedido de login no helper HTTP explicado em XTcli.md. |
| 82 | Seleciona o endpoint allauth de login; não é o endpoint público exerciseinfo. |
| 83 | Encaminha as credenciais recebidas, sem as guardar num ficheiro. |
| 84 | Fecha a chamada e devolve a resposta ao fluxo interativo. |

### `save_token()`

Guarda uma entrada no keyring e devolve sucesso/falha. É reutilizada pelo login, renovação e criação de conta.

#### save_token

[Fonte: tcli.py, linha 185](../../tcli.py#L185)

```python
def save_token(name: str, token: str) -> bool:
    try:
        keyring.set_password("FITCLI-wger", name, token)
        return True
    except (keyring.errors.KeyringError, OSError):
        print("Não foi possível guardar a sessão. Pode continuar nesta sessão.")
        return False
```

| Linha | Explicação |
|---|---|
| 185 | Define `save_token` e os parâmetros/resultado usados neste bloco. |
| 186 | Agrupa a tentativa de gravação no keyring. |
| 187 | Guarda o token no serviço FITCLI-wger, associado à chave name. |
| 188 | Confirma ao chamador que a gravação terminou. |
| 189 | Trata indisponibilidade do keyring ou erro do sistema. |
| 190 | Avisa que a persistência falhou, mas não invalida a sessão em memória. |
| 191 | Devolve False para o chamador não assumir que a sessão foi guardada. |

### `refresh_login()`

Tenta renovar a sessão guardada. Guarda a rotação do refresh token antes de verificar o access token, porque o token anterior pode já não ser válido.

#### Ler e renovar a sessão

[Fonte: tcli.py, linha 194](../../tcli.py#L194)

```python
def refresh_login(name: str | None) -> str | None:
    if not name or name == "last_username":
        return None

    try:
        token = keyring.get_password("FITCLI-wger", name)
    except (keyring.errors.KeyringError, OSError):
        print("Armazenamento seguro indisponível. Introduza a palavra-passe.")
        return None

    if not isinstance(token, str) or not token.strip():
        return None

    try:
        response = post_data(
            "https://wger.de/allauth/app/v1/tokens/refresh",
            {"refresh_token": token}
        )
    except RuntimeError as error:
        cause = error.__cause__
        if (isinstance(cause, requests.exceptions.HTTPError)
                and cause.response is not None
                and cause.response.status_code in (400, 401)):
            print("A sessão guardada expirou. Introduza a palavra-passe.")
            return None
        raise
```

| Linha | Explicação |
|---|---|
| 194 | Define `refresh_login` e os parâmetros/resultado usados neste bloco. |
| 195 | Ignora nomes ausentes e a chave de metadados reservada. |
| 196 | Indica que não existe sessão a restaurar para esse nome. |
| 198 | Protege a leitura do armazenamento seguro. |
| 199 | Procura o refresh token dessa conta, sem o mostrar no terminal. |
| 200 | Trata falha do keyring ou do sistema. |
| 201 | Orienta para autenticação manual. |
| 202 | Indica que não conseguiu restaurar uma sessão. |
| 204 | Rejeita tokens guardados que não sejam texto ou estejam vazios. |
| 205 | Permite que o chamador avance para pedir palavra-passe. |
| 207 | Protege o pedido HTTP de renovação. |
| 208 | Delega o POST no helper de autenticação. |
| 209 | Escolhe o endpoint allauth de renovação. |
| 210 | Envia apenas o refresh token guardado. |
| 211 | Fecha o pedido de renovação. |
| 212 | Trata a falha devolvida pelo helper HTTP. |
| 213 | Lê a causa original para distinguir rejeição de falha de rede. |
| 214 | Começa a exigir uma falha HTTP reconhecível. |
| 215 | Confirma a existência da resposta do servidor. |
| 216 | Identifica HTTP 400/401 como rejeição da sessão guardada. |
| 217 | Explica que será necessário fornecer a palavra-passe. |
| 218 | Devolve None para permitir o login manual. |
| 219 | Propaga outras falhas: não transforma indisponibilidade de rede em credenciais inválidas. |

#### Validar e guardar os novos tokens

[Fonte: tcli.py, linha 221](../../tcli.py#L221)

```python
    data = response.get("data")
    if not isinstance(data, dict):
        raise RuntimeError("Resposta de autenticação inválida.")
    access = data.get("access_token")
    refresh = data.get("refresh_token", token)
    if not all(isinstance(value, str) and value.strip() for value in (access, refresh)):
        raise RuntimeError("Resposta de autenticação inválida.")

    # Guardar a rotação antes da verificação: o token anterior pode já ter expirado.
    saved = save_token(name, refresh)
    if not verify_access_token(access):
        print("A sessão guardada foi rejeitada. Introduza a palavra-passe.")
        return None
    if saved:
        save_token("last_username", name)
    return access
```

| Linha | Explicação |
|---|---|
| 221 | Lê o objeto data da resposta de renovação. |
| 222 | Exige que esse conteúdo seja um dicionário. |
| 223 | Rejeita uma estrutura de resposta inesperada. |
| 224 | Lê o novo access token. |
| 225 | Usa o refresh token novo, ou conserva o anterior quando o campo está ausente. |
| 226 | Exige que ambos os tokens sejam textos não vazios. |
| 227 | Interrompe a renovação se os tokens forem inválidos. |
| 230 | Guarda a eventual rotação do refresh token antes de verificar o access token. |
| 231 | Verifica o novo access token antes de o devolver. |
| 232 | Informa que o token da sessão não foi aceite. |
| 233 | Permite regressar ao login manual. |
| 234 | Verifica se a persistência do refresh token teve sucesso. |
| 235 | Nesse caso tenta registar a última conta usada. |
| 236 | Devolve o access token verificado, mesmo que a persistência tenha falhado. |

### `verify_access_token()`

Distingue um token recusado (False) de uma verificação indisponível (RuntimeError). Não lê nem escreve a cache pública.

#### verify_access_token

[Fonte: tcli.py, linha 239](../../tcli.py#L239)

```python
def verify_access_token(token: str) -> bool:

    try:
        response = requests.post(
            "https://wger.de/api/v2/token/verify",
            json={"token": token},
            headers=HEADERS,
            timeout=15
        )

        if response.status_code in (400, 401):
            return False

        response.raise_for_status()
        return True

    except requests.exceptions.RequestException as error:
        raise RuntimeError(
            "Não foi possível verificar o token."
        ) from error
```

| Linha | Explicação |
|---|---|
| 239 | Define `verify_access_token` e os parâmetros/resultado usados neste bloco. |
| 241 | Protege a verificação HTTP. |
| 242 | Inicia o POST direto que valida o access token. |
| 243 | Seleciona o endpoint v2 de verificação. |
| 244 | Envia o token num corpo JSON; não utiliza a cache. |
| 245 | Aplica os cabeçalhos comuns. |
| 246 | Limita o pedido a 15 segundos. |
| 247 | Fecha a chamada HTTP de verificação. |
| 249 | Reconhece HTTP 400/401 como token não aceite. |
| 250 | Devolve False nesses casos em vez de ativar a sessão. |
| 252 | Propaga outros estados HTTP de erro para o tratamento abaixo. |
| 253 | Devolve True quando a resposta é de sucesso. |
| 255 | Trata falhas de requests, incluindo HTTP e rede. |
| 256 | Inicia a mensagem de verificação indisponível. |
| 257 | Define o texto apresentado pelo chamador. |
| 258 | Mantém a exceção original como causa. |

### `connection_questionary()`

Recolhe a escolha entre login/registo. No ramo de login, tenta renovação antes de pedir a palavra-passe e só devolve access tokens verificados.

#### Escolher o fluxo e validar o nome

[Fonte: tcli.py, linha 261](../../tcli.py#L261)

```python
def connection_questionary() -> str | None:
    try:
        if not questionary.confirm("Deseja conectar-se a uma conta?", default=True).ask():
            return None

        action = questionary.select(
            "O que deseja fazer?",
            choices=["Fazer login", "Criar conta"]
        ).ask()
        if action == "Criar conta":
            return creation_questionary()
        if action != "Fazer login":
            return None

        while True:
            name = questionary.text("Introduza o nome de utilizador:").ask()
            if name is None:
                return None
            name = name.strip()
            if not name or name == "last_username":
                print("Introduza um nome de utilizador válido.")
                continue
```

| Linha | Explicação |
|---|---|
| 261 | Define `connection_questionary` e os parâmetros/resultado usados neste bloco. |
| 262 | Permite cancelar o fluxo de ligação com teclado ou fim da entrada. |
| 263 | Pergunta primeiro se o utilizador quer conectar-se a uma conta. |
| 264 | Devolve None se a ligação não for confirmada. |
| 266 | Inicia a seleção entre login e registo. |
| 267 | Define o texto da pergunta. |
| 268 | Disponibiliza as duas ações da conta. |
| 269 | Apresenta a pergunta e recebe a escolha. |
| 270 | Identifica a escolha de criação de conta. |
| 271 | Delega o registo no guia separado XTcli_criacao_contas.md. |
| 272 | Trata uma escolha diferente de login, incluindo cancelamento. |
| 273 | Termina sem sessão para essa escolha. |
| 275 | Inicia o ciclo de tentativas de login. |
| 276 | Pede o nome de utilizador. |
| 277 | Identifica cancelamento da pergunta. |
| 278 | Termina sem access token. |
| 279 | Remove espaços exteriores do nome. |
| 280 | Rejeita nome vazio e last_username, que é uma chave reservada. |
| 281 | Informa o problema do nome. |
| 282 | Recomeça a pergunta sem enviar credenciais. |

#### Renovar ou pedir credenciais

[Fonte: tcli.py, linha 284](../../tcli.py#L284)

```python
            try:
                access = refresh_login(name)
                if access:
                    print("Login realizado com sucesso!")
                    return access

                password = questionary.password("Introduza a palavra-passe:").ask()
                if password is None:
                    return None
                if not password.strip():
                    print("A palavra-passe é obrigatória.")
                    continue

                response = login_account({"username": name, "password": password})
                meta = response.get("meta")
                if not isinstance(meta, dict) or meta.get("is_authenticated") is not True:
                    print("Login não concluído. Pode ser necessária outra etapa de autenticação.")
                else:
                    access = meta.get("access_token")
                    refresh = meta.get("refresh_token")
                    if not all(isinstance(value, str) and value.strip() for value in (access, refresh)):
                        print("Resposta de autenticação inválida.")
                    elif not verify_access_token(access):
                        print("A autenticação foi rejeitada. Tente novamente.")
                    else:
                        if save_token(name, refresh):
                            save_token("last_username", name)
                        print("Login realizado com sucesso!")
                        return access
```

| Linha | Explicação |
|---|---|
| 284 | Agrupa renovação, login e verificação para tratar as suas falhas. |
| 285 | Tenta reutilizar uma sessão guardada antes de pedir palavra-passe. |
| 286 | Verifica se a renovação devolveu um access token. |
| 287 | Informa o sucesso da sessão restaurada. |
| 288 | Devolve o token e evita pedir novamente a palavra-passe. |
| 290 | Pede a palavra-passe com entrada oculta quando não há sessão restaurada. |
| 291 | Identifica cancelamento da pergunta da palavra-passe. |
| 292 | Termina sem sessão. |
| 293 | Rejeita palavra-passe vazia ou só com espaços. |
| 294 | Explica que a palavra-passe é obrigatória. |
| 295 | Recomeça o ciclo de perguntas. |
| 297 | Envia as credenciais por login_account; a palavra-passe não é persistida. |
| 298 | Lê os metadados do login. |
| 299 | Exige meta como objeto e autenticação confirmada pelo servidor. |
| 300 | Mostra uma mensagem quando o login ainda não está concluído. |
| 301 | Passa à análise dos tokens quando a autenticação foi confirmada. |
| 302 | Lê o access token. |
| 303 | Lê o refresh token. |
| 304 | Exige dois tokens textuais e não vazios. |
| 305 | Informa resposta inválida sem aceitar a sessão. |
| 306 | Se os tokens têm formato válido, verifica o access token. |
| 307 | Informa rejeição da verificação. |
| 308 | Só entra no ramo de sucesso depois da verificação. |
| 309 | Tenta guardar o refresh token no keyring. |
| 310 | Se a gravação teve sucesso, tenta atualizar last_username. |
| 311 | Informa o sucesso do login. |
| 312 | Devolve o access token para navegação autenticada. |

#### Erros e repetição

[Fonte: tcli.py, linha 314](../../tcli.py#L314)

```python
            except RuntimeError as error:
                cause = error.__cause__
                if isinstance(cause, requests.exceptions.HTTPError) and cause.response is not None:
                    messages = {
                        400: "Nome de utilizador ou palavra-passe inválidos.",
                        401: "Credenciais inválidas ou autenticação adicional necessária.",
                        403: "Autenticação recusada. Verifique se a conta exige outra etapa.",
                        429: "Demasiadas tentativas. Aguarde antes de tentar novamente."
                    }
                    print(messages.get(cause.response.status_code, "Serviço de autenticação indisponível."))
                else:
                    print("Não foi possível autenticar. Verifique a ligação e tente novamente.")

            if not questionary.confirm("Deseja tentar novamente?", default=True).ask():
                return None
    except (KeyboardInterrupt, EOFError):
        return None
```

| Linha | Explicação |
|---|---|
| 314 | Trata falhas HTTP/rede/JSON convertidas em RuntimeError. |
| 315 | Lê a causa original preservada pelo helper. |
| 316 | Se há uma resposta HTTP, pode escolher uma mensagem por estado. |
| 317 | Inicia o mapa de mensagens de falha do login. |
| 318 | Para HTTP 400, indica nome ou palavra-passe inválidos. |
| 319 | Para HTTP 401, indica credenciais inválidas ou etapa adicional. |
| 320 | Para HTTP 403, indica recusa ou necessidade de outro passo. |
| 321 | Para HTTP 429, pede espera antes de nova tentativa. |
| 322 | Fecha o mapa de mensagens. |
| 323 | Apresenta a mensagem conhecida ou a alternativa de serviço indisponível. |
| 324 | Trata falhas sem resposta HTTP utilizável. |
| 325 | Mostra a mensagem de ligação/autenticação indisponível. |
| 327 | Depois de falha ou login incompleto, pergunta se deve repetir. |
| 328 | Termina sem sessão se a repetição não for confirmada. |
| 329 | Captura Ctrl+C e fim da entrada. |
| 330 | Abandona o fluxo sem token. |

## Verificação

A aplicação pode ser iniciada a partir de `ALPCD_12`:

```bash
uv run python tcli.py
```

| Caso | Resultado a verificar com mocks |
|---|---|
| Sessão renovável | Devolver token sem pedir palavra-passe |
| Refresh rejeitado com 400/401 | Avançar para login manual |
| Rede indisponível | Mostrar falha sem inventar credenciais inválidas |
| Token verificado e keyring indisponível | Manter sessão em memória |
| Token novo rejeitado | Não abrir o menu autenticado |
| Cancelamento | Devolver None |

Estes casos descrevem verificações recomendadas, não execuções reais novas.
A cópia atual não inclui uma pasta `tests/`. Para testes automáticos, simular
requests, keyring e questionary e usar pastas temporárias: não criar contas,
guardar tokens reais ou exportar templates apenas para validar a documentação.

Voltar ao [README oficial](../../README.md).
