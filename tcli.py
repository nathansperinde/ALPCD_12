import requests
import questionary
import keyring

from fitlib import api, exercises, extras, workouts


# [TCLI] CONFIGURAÇÃO
# Cabeçalhos e mensagens HTTP

HEADERS = {
    "User-Agent": "ALPCD-Grupo12/0.1",
    "Accept": "application/json"
}

HTTP_ERRORS = {
    400: "Bad request.",
    401: "Authentication required.",
    403: "Access forbidden.",
    404: "Resource not found.",
    408: "Request timeout.",
    429: "Too many requests."
}


# [TCLI] AUTENTICAÇÃO
# Pedidos HTTP e login
# Lógica existente preservada; fornece o token às funcionalidades da conta.

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


def login_account(dados: dict) -> dict:
    return post_data(
        "https://wger.de/allauth/app/v1/auth/login",
        dados
    )


# [TCLI] REGISTO
# Criação de contas

def create_account(dados: dict) -> dict:
    return post_data(
        "https://wger.de/allauth/app/v1/auth/signup",
        dados
    )


def creation_questionary() -> str | None:
    try:
        while True:
            name = questionary.text("Escolha o nome de utilizador:").ask()
            if name is None:
                return None
            name = name.strip()
            if not name or name == "last_username":
                print("Introduza um nome de utilizador válido.")
                continue

            password = questionary.password("Escolha a palavra-passe:").ask()
            if password is None:
                return None
            if not password.strip():
                print("A palavra-passe é obrigatória.")
                continue

            try:
                response = create_account({"username": name, "password": password})
            except RuntimeError as error:
                cause = error.__cause__
                if not isinstance(cause, requests.exceptions.HTTPError) or cause.response is None:
                    print("Não foi possível confirmar o registo. Tente Fazer login antes de voltar a criar a conta.")
                    return None

                status = cause.response.status_code
                if status == 400:
                    messages = {
                        "username_taken": "Este nome de utilizador já está em uso.",
                        "password_too_short": "A palavra-passe é demasiado curta.",
                        "password_too_common": "A palavra-passe é demasiado comum.",
                        "password_entirely_numeric": "A palavra-passe não pode conter apenas números.",
                        "password_too_similar": "A palavra-passe é demasiado semelhante ao nome de utilizador."
                    }
                    try:
                        details = cause.response.json()
                    except ValueError:
                        details = {}
                    errors = details.get("errors", []) if isinstance(details, dict) else []
                    if not isinstance(errors, list) or not errors:
                        print("Dados de registo inválidos. Verifique o nome e a palavra-passe.")
                    else:
                        for item in errors:
                            code = item.get("code") if isinstance(item, dict) else None
                            if not isinstance(code, str):
                                code = None
                            print(messages.get(code, "Dados de registo inválidos. Verifique o nome e a palavra-passe."))
                else:
                    messages = {
                        401: "Registo pendente. Pode ser necessária outra etapa de autenticação. Consulte a conta na wger antes de tentar novamente.",
                        403: "A criação de contas não está disponível neste momento.",
                        409: "O registo não pôde ser concluído. Tente Fazer login.",
                        429: "Demasiadas tentativas. Aguarde antes de tentar novamente."
                    }
                    print(messages.get(status, "Serviço indisponível. Tente Fazer login antes de repetir o registo."))
                    return None

                if not questionary.confirm("Deseja tentar novamente?", default=True).ask():
                    return None
                continue

            # O pedido foi aceite: não repetir o registo se a verificação falhar.
            meta = response.get("meta")
            if not isinstance(meta, dict) or meta.get("is_authenticated") is not True:
                print("Registo recebido. Pode ser necessária outra etapa. Consulte a conta na wger e depois escolha Fazer login.")
                return None

            access = meta.get("access_token")
            refresh = meta.get("refresh_token")
            if not all(isinstance(value, str) and value.strip() for value in (access, refresh)):
                print("Resposta de registo inválida. Tente Fazer login antes de repetir o registo.")
                return None

            try:
                verified = verify_access_token(access)
            except RuntimeError:
                verified = False
            if not verified:
                print("A conta foi criada, mas não foi possível confirmar a sessão. Escolha Fazer login.")
                return None

            if save_token(name, refresh):
                save_token("last_username", name)
            print("Conta criada com sucesso!")
            return access

    except (KeyboardInterrupt, EOFError):
        return None


# [TCLI] SESSÃO
# Armazenamento, renovação e verificação de tokens

def save_token(name: str, token: str) -> bool:
    try:
        keyring.set_password("FITCLI-wger", name, token)
        return True
    except (keyring.errors.KeyringError, OSError):
        print("Não foi possível guardar a sessão. Pode continuar nesta sessão.")
        return False


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


# [TCLI] LOGIN
# Seleção de conta e autenticação interativa

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


# [TCLI] ENTRADA
# Perguntas e validação partilhadas
# Usadas nos exercícios e na criação de treinos.

def text(prompt, maximum=1000):
    while True:
        answer = questionary.text(prompt).ask()
        if answer is None:
            raise KeyboardInterrupt
        if 1 <= len(answer.strip()) <= maximum:
            return answer.strip()
        print(f"Introduza texto entre 1 e {maximum} caracteres.")


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


# [TCLI] EXERCÍCIOS
# Consultas públicas reutilizadas da FITCLI

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


# [TCLI] TREINOS LOCAIS
# Criação, importação e apresentação
# Prompts locais; persistência/validação em workouts.py. Independente da exportação.

def show_workout(workout):
    print(f"\n{workout['name']}")
    for session in workout["sessions"]:
        print(f"  {session['name']} — músculos: " + (", ".join(session["muscles"]) or "não indicados"))
        for entry in session["exercises"]:
            # JSON antigos podem guardar nomes ingleses; usar a tradução quando disponível.
            name = entry["name"]
            try:
                raw = api.get_data(f"exerciseinfo/{entry['id']}/")
                name = workouts.exercise_name(raw) or name
            except RuntimeError as error:
                # Manter o nome guardado sem impedir a importação local.
                print(f"Não foi possível atualizar o nome do exercício #{entry['id']}: {error}")
            print(f"    {name}: {entry['sets']} séries")


def import_workout():
    files = []
    workouts.WORKOUTS_DIR.mkdir(exist_ok=True)
    for path in sorted(workouts.WORKOUTS_DIR.glob("*.json")):
        files.append({"name": path.name})
    selected = choose("Importar ficheiro:", files)
    if selected:
        workout = workouts.load_workout(selected["name"])
        show_workout(workout)
        return workout


def create_workout():
    workout = {"version": 1, "name": text("Nome do treino:", 25), "sessions": []}
    count = number("Número de sessões (1–7):", 7)
    equipment = api.get_list("equipment/")
    muscles = api.get_list("muscle/")
    for muscle in muscles:
        muscle["name"] = muscle.get("name_en") or muscle["name"]
    for index in range(count):
        session = {"name": text(f"Nome da sessão {index + 1}:", 20), "muscles": [], "exercises": []}
        session["equipment"] = choose("Equipamento disponível:", equipment, multiple=True, selected=True)
        targets = choose("Músculos a treinar:", muscles, multiple=True)
        if not targets:
            raise ValueError("Selecione pelo menos um músculo.")
        for muscle in targets:
            session["muscles"].append(muscle["name"])
        candidates = workouts.filtered_exercises(session["equipment"], targets)
        selected = choose("Exercícios:", candidates, multiple=True)
        if not selected:
            raise ValueError("Selecione pelo menos um exercício. Treino não guardado.")
        for entry in selected:
            session["exercises"].append({"id": entry["id"], "name": entry["name"],
                                         "sets": number(f"Séries de {entry['name']}:", 50)})
        workout["sessions"].append(session)
    show_workout(workout)
    workouts.save_workout(workout)
    return workout


# [TCLI] TEMPLATES WGER
# Exportação e consulta
# Exportar cria apenas um template privado; consultar não altera a conta.

def export_template(workout, token):
    for template in api.get_list("templates/", token=token):
        if template["name"] == workout["name"]:
            if questionary.confirm(
                    f"Já existe '{template['name']}' [#{template['id']}]. Reutilizar?", default=True).ask():
                return template
    if questionary.confirm("Tem certeza que deseja exportar?", default=True).ask():
        template = workouts.create_template(workout, token)
        print(f"Template exportado: {template['name']} [#{template['id']}]")
        return template


def workout_actions(workout, token):
    action = questionary.select("O que deseja fazer?", choices=[
        "Exportar como template", "Voltar"]).ask()
    if action == "Exportar como template":
        export_template(workout, token)


def template_menu(token):
    templates = api.get_list("templates/", token=token)
    if not templates:
        print("Ainda não existem templates exportados nesta conta.")
    for template in templates:
        print(f"\nTemplate #{template['id']}: {template['name']}")
        try:
            show_workout(workouts.read_structure(template["id"], token))
        except ValueError as error:
            print(f"Template não compatível: {error}")


# [TCLI] NAVEGAÇÃO
# Menu autenticado e gestão das operações

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


# [TCLI] ARRANQUE
# Inicialização e restauro da sessão

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


if __name__ == "__main__":
    main()
