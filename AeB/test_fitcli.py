"""Testes do TP1 de ALPCD (CLI wger).

COMO CORRER (no terminal do VS Code, na pasta onde estão api.py e fitcli.py):

    python test_fitcli.py             # testes OFFLINE (sem internet, dados falsos)
    python test_fitcli.py --online    # offline + testes contra a API real
    python test_fitcli.py --verbose   # mostra o traceback completo se algo falhar

Ideia geral:
  * Testes OFFLINE: trocamos a função que faz o pedido HTTP por uma "API falsa"
    com dados que nós controlamos. Assim sabemos exatamente qual é a resposta
    certa e o teste é rápido e repetível.
  * Testes ONLINE: confirmam que o que assumimos sobre a API real é verdade.
"""

import contextlib
import json
import sys
import tempfile
import traceback
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

# Garante que o Python encontra api.py e fitcli.py (mesma pasta deste ficheiro).
sys.path.insert(0, str(Path(__file__).resolve().parent))

import requests
from typer.testing import CliRunner

import api
import fitcli

# ---------------------------------------------------------------------------
# Mini-framework de testes (não precisas de instalar o pytest)
# ---------------------------------------------------------------------------

TESTES = []  # lista de (online, titulo, explicacao, funcao)


def teste(titulo, explicacao, online=False):
    """Decorador: regista uma função como teste, com título e explicação."""
    def decorador(func):
        TESTES.append((online, titulo, explicacao, func))
        return func
    return decorador


@contextlib.contextmanager
def patched(objeto, nome, valor):
    """Troca temporariamente `objeto.nome` por `valor` e repõe no fim."""
    original = getattr(objeto, nome)
    setattr(objeto, nome, valor)
    try:
        yield
    finally:
        setattr(objeto, nome, original)


@contextlib.contextmanager
def cache_temporaria():
    """Usa um cache.json temporário, para os testes não mexerem no teu."""
    with tempfile.TemporaryDirectory() as pasta:
        with patched(api, "CACHE_FILE", Path(pasta) / "cache.json"):
            yield


runner = CliRunner()


def cli(*args):
    """Corre a CLI dentro do Python (como escrever `python fitcli.py ...`)."""
    return runner.invoke(fitcli.app, list(args))


# ---------------------------------------------------------------------------
# API FALSA (usada nos testes offline)
# ---------------------------------------------------------------------------
# Dados falsos: 12 exercícios. Cada página só devolve 5, para obrigar o código
# a seguir o campo "next" (testa a paginação).
#   * ids 1 a 6  -> categoria Arms ; ids 7 a 12 -> categoria Chest
#   * ids ímpares -> músculo Biceps ; ids pares -> músculo Pecs
#   * o exercício 7 só tem tradução alemã (não tem nome em inglês)
#   * o "created" cresce com o id: o exercício 12 é o mais recente

PAGE_SIZE = 5
MUSCULOS = [
    {"id": 1, "name": "Biceps brachii", "name_en": "Biceps"},
    {"id": 2, "name": "Pectoralis major", "name_en": "Pecs"},
]
CATEGORIAS = [{"id": 1, "name": "Arms"}, {"id": 2, "name": "Chest"}]


def _exercicio(i):
    traducoes = [{"language": 1, "name": f"Uebung {i}"}]
    if i != 7:
        traducoes.append({"language": 2, "name": f"Ex{i}"})
    return {
        "id": i,
        "created": f"2026-01-{i:02d}T10:00:00Z",
        "category": CATEGORIAS[0] if i <= 6 else CATEGORIAS[1],
        "equipment": [{"id": 1, "name": "Barbell"}] if i % 2 else [],
        "muscles": [MUSCULOS[0] if i % 2 else MUSCULOS[1]],
        "translations": traducoes,
    }


EXERCICIOS = [_exercicio(i) for i in range(1, 13)]


class FalsaAPI:
    """Imita a wger: filtra, ordena, pagina e regista os pedidos recebidos."""

    def __init__(self):
        self.pedidos = []

    def __call__(self, url, params):
        self.pedidos.append((url, params))
        parsed = urlparse(url)
        caminho = parsed.path.split("/api/v2/")[-1]
        q = {k: v[0] for k, v in parse_qs(parsed.query).items()}
        q.update({k: str(v) for k, v in (params or {}).items()})

        if caminho == "muscle/":
            dados = list(MUSCULOS)
        elif caminho == "exercisecategory/":
            dados = list(CATEGORIAS)
        elif caminho == "exerciseinfo/":
            dados = list(EXERCICIOS)
            if "muscles" in q:
                dados = [e for e in dados
                         if int(q["muscles"]) in [m["id"] for m in e["muscles"]]]
            if "category" in q:
                dados = [e for e in dados if e["category"]["id"] == int(q["category"])]
            if q.get("ordering") == "-created":
                dados = sorted(dados, key=lambda e: e["created"], reverse=True)
        else:
            raise RuntimeError(f"endpoint desconhecido na API falsa: {caminho}")

        limite = min(int(q.get("limit", PAGE_SIZE)), PAGE_SIZE)
        inicio = int(q.get("offset", 0))
        fim = inicio + limite
        seguinte = None
        if fim < len(dados):
            q2 = dict(q)
            q2["offset"], q2["limit"] = fim, limite
            seguinte = f"{api.BASE_URL}{caminho}?{urlencode(q2)}"
        return {"count": len(dados), "next": seguinte, "previous": None,
                "results": dados[inicio:fim]}


@contextlib.contextmanager
def api_falsa():
    """Durante o bloco, todos os pedidos vão para a FalsaAPI e a cache é temporária."""
    falsa = FalsaAPI()
    with cache_temporaria(), patched(api, "_request", falsa):
        yield falsa


class RespostaFalsa:
    """Imita o objeto devolvido por requests.get (para testar erros HTTP/JSON)."""

    def __init__(self, status=200, payload=None, json_invalido=False):
        self.status_code = status
        self.payload = payload
        self.json_invalido = json_invalido

    def raise_for_status(self):
        if self.status_code >= 400:
            erro = requests.HTTPError()
            erro.response = self
            raise erro

    def json(self):
        if self.json_invalido:
            raise ValueError("não é JSON")
        return self.payload


def nomes(resultado_cli):
    """Lê o JSON escrito pela CLI e devolve só a lista de nomes."""
    return [e["name"] for e in json.loads(resultado_cli.output)]


# ===========================================================================
# GRUPO 1: função _format (transforma 1 exercício da API no formato de saída)
# ===========================================================================

@teste(
    "_format: extrai nome inglês, categoria, equipamento e músculos",
    "Dado um exercício com duas traduções (alemão e inglês), deve escolher a "
    "inglesa (language == 2) e devolver os 4 campos esperados.",
)
def test_format_normal():
    ex = {
        "category": {"id": 8, "name": "Arms"},
        "equipment": [{"id": 1, "name": "Barbell"}],
        "muscles": [{"id": 1, "name": "Biceps brachii", "name_en": "Biceps"}],
        "translations": [
            {"language": 1, "name": "Langhantelcurl"},
            {"language": 2, "name": "Barbell Curl"},
        ],
    }
    esperado = {"name": "Barbell Curl", "category": "Arms",
                "equipment": ["Barbell"], "muscles": ["Biceps"]}
    assert fitcli._format(ex) == esperado, f"obtive {fitcli._format(ex)}"


@teste(
    "_format: sem tradução inglesa devolve None",
    "Se o exercício só tem nome noutra língua, a função devolve None (e o "
    "get_list descarta-o).",
)
def test_format_sem_ingles():
    ex = {"category": {"name": "Arms"}, "equipment": [], "muscles": [],
          "translations": [{"language": 1, "name": "Langhantelcurl"}]}
    assert fitcli._format(ex) is None


@teste(
    "_format: campos em falta não rebentam",
    "Exercício sem categoria, sem equipamento e músculo sem name_en: a função "
    "não pode dar erro; usa o `name` do músculo como alternativa.",
)
def test_format_campos_em_falta():
    ex = {"category": None, "muscles": [{"id": 3, "name": "Soleus", "name_en": ""}],
          "translations": [{"language": 2, "name": "Calf Raise"}]}
    r = fitcli._format(ex)
    assert r == {"name": "Calf Raise", "category": None,
                 "equipment": [], "muscles": ["Soleus"]}, f"obtive {r}"


# ===========================================================================
# GRUPO 2: api.py (validação de URL, erros, cache, paginação)
# ===========================================================================

@teste(
    "api._url: aceita só URLs da API wger",
    "Caminhos relativos e URLs de paginação da wger passam; qualquer outro "
    "domínio ou caminho é rejeitado com RuntimeError.",
)
def test_url_validacao():
    assert api._url("exerciseinfo/") == api.BASE_URL + "exerciseinfo/"
    ok = "https://wger.de/api/v2/exerciseinfo/?limit=5&offset=5"
    assert api._url(ok) == ok
    for mau in ["https://evil.com/api/v2/x/", "https://wger.de/outra/coisa/",
                "http://wger.de/api/v2/x/"]:
        try:
            api._url(mau)
        except RuntimeError:
            continue
        raise AssertionError(f"devia ter rejeitado {mau}")


def _com_resposta(resposta=None, excecao=None):
    """Troca session.get por uma função que devolve `resposta` ou lança `excecao`."""
    def falso(*a, **k):
        if excecao:
            raise excecao
        return resposta
    return patched(api.session, "get", falso)


def _mensagem_de_erro(**kwargs):
    with _com_resposta(**kwargs):
        try:
            api._request(api.BASE_URL + "x/", None)
        except RuntimeError as exc:
            return str(exc)
    raise AssertionError("devia ter lançado RuntimeError")


@teste(
    "api._request: timeout, ligação, HTTP, JSON inválido",
    "Simulamos cada tipo de falha e confirmamos que sai sempre um RuntimeError "
    "com a mensagem em português certa (nunca um erro técnico da biblioteca).",
)
def test_erros_de_rede():
    assert "tempo limite" in _mensagem_de_erro(excecao=requests.Timeout())
    assert "comunicar" in _mensagem_de_erro(excecao=requests.ConnectionError())
    assert "404" in _mensagem_de_erro(resposta=RespostaFalsa(status=404))
    assert "500" in _mensagem_de_erro(resposta=RespostaFalsa(status=500))
    assert "JSON válido" in _mensagem_de_erro(resposta=RespostaFalsa(json_invalido=True))
    assert "objeto JSON" in _mensagem_de_erro(resposta=RespostaFalsa(payload=[1, 2]))


@teste(
    "api.get_json: a cache evita pedidos repetidos e --refresh ignora-a",
    "1.º pedido vai à API; 2.º vem da cache (0 pedidos novos); com "
    "refresh=True volta a ir à API.",
)
def test_cache():
    with api_falsa() as falsa:
        api.get_json("exercisecategory/")
        assert len(falsa.pedidos) == 1, "o 1.º pedido devia ir à API"
        api.get_json("exercisecategory/")
        assert len(falsa.pedidos) == 1, "o 2.º pedido devia vir da cache"
        api.get_json("exercisecategory/", refresh=True)
        assert len(falsa.pedidos) == 2, "refresh=True devia ir à API"
        assert api.CACHE_FILE.exists(), "cache.json devia ter sido criado"


@teste(
    "api.get_list: segue as páginas (paginação)",
    "A API falsa dá 5 exercícios por página e tem 12. Pedir todos deve fazer "
    "3 pedidos (5+5+2) e devolver os 12.",
)
def test_paginacao():
    with api_falsa() as falsa:
        itens = api.get_list("exerciseinfo/", {"limit": 5})
        assert len(itens) == 12, f"esperava 12, obtive {len(itens)}"
        assert len(falsa.pedidos) == 3, f"esperava 3 pedidos, houve {len(falsa.pedidos)}"


@teste(
    "api.get_list: max_items pára cedo; params só na 1.ª página",
    "Com max_items=7 devolve 7 itens (2 páginas). O 2.º pedido não deve "
    "repetir `params` (a URL `next` já os traz).",
)
def test_max_items_e_params():
    with api_falsa() as falsa:
        itens = api.get_list("exerciseinfo/", {"limit": 5}, max_items=7)
        assert len(itens) == 7
        assert len(falsa.pedidos) == 2
        assert falsa.pedidos[0][1] == {"limit": 5}
        assert falsa.pedidos[1][1] is None, "a 2.ª página não devia levar params"


@teste(
    "api.get_list: deteta ciclos e valida max_items",
    "Uma API que aponte `next` para a própria página causaria um ciclo "
    "infinito: tem de dar RuntimeError. max_items <= 0 dá ValueError.",
)
def test_ciclo_e_max_items():
    def ciclica(url, params):
        return {"count": 1, "next": url, "results": [{"id": 1}]}

    with cache_temporaria(), patched(api, "_request", ciclica):
        try:
            api.get_list("exerciseinfo/")
        except RuntimeError as exc:
            assert "ciclo" in str(exc)
        else:
            raise AssertionError("devia ter detetado o ciclo")
    try:
        api.get_list("exerciseinfo/", max_items=0)
    except ValueError:
        pass
    else:
        raise AssertionError("max_items=0 devia dar ValueError")


# ===========================================================================
# GRUPO 3: alínea A (comando top)
# ===========================================================================

@teste(
    "top 3: devolve os 3 mais recentes, em JSON, com os campos certos",
    "Os mais recentes são os de maior `created`: Ex12, Ex11, Ex10. Cada objeto "
    "tem name, category, equipment e muscles.",
)
def test_top_basico():
    with api_falsa():
        r = cli("top", "3")
    assert r.exit_code == 0, r.output
    dados = json.loads(r.output)
    assert [e["name"] for e in dados] == ["Ex12", "Ex11", "Ex10"], dados
    assert set(dados[0]) == {"name", "category", "equipment", "muscles"}
    assert dados[0]["category"] == "Chest" and dados[0]["equipment"] == []
    assert dados[1]["equipment"] == ["Barbell"]


@teste(
    "top 11: atravessa páginas e salta exercícios sem nome inglês",
    "Há 12 exercícios, mas o Ex7 só tem nome alemão. Pedir 11 deve devolver "
    "11 nomes (de Ex12 a Ex1, sem Ex7) usando 3 páginas.",
)
def test_top_paginas_e_descarte():
    with api_falsa() as falsa:
        r = cli("top", "11")
    assert r.exit_code == 0, r.output
    n = nomes(r)
    esperado = [f"Ex{i}" for i in range(12, 0, -1) if i != 7]
    assert n == esperado, f"obtive {n}"
    assert len(falsa.pedidos) == 3


@teste(
    "top 50: pedir mais do que existe não dá erro",
    "Só existem 11 exercícios com nome inglês; pedir 50 devolve 11, sem falhar.",
)
def test_top_mais_do_que_existe():
    with api_falsa():
        r = cli("top", "50")
    assert r.exit_code == 0 and len(nomes(r)) == 11


@teste(
    "top: argumentos inválidos são rejeitados pelo typer",
    "`top 0` e `top abc` falham com código de saída 2 (erro de utilização).",
)
def test_top_argumentos_invalidos():
    assert cli("top", "0").exit_code == 2
    assert cli("top", "abc").exit_code == 2
    assert cli("top").exit_code == 2


@teste(
    "top: erro da API vira mensagem limpa e código 1",
    "Se a API falhar, a CLI mostra `Erro: ...` e termina com código 1, sem traceback.",
)
def test_top_erro_api():
    def falha(url, params):
        raise RuntimeError("A API excedeu o tempo limite do pedido.")

    with cache_temporaria(), patched(api, "_request", falha):
        r = cli("top", "3")
    assert r.exit_code == 1, r.exit_code
    assert "Erro:" in r.output and "tempo limite" in r.output
    assert "Traceback" not in r.output


# ===========================================================================
# GRUPO 4: alínea B (comando search)
# ===========================================================================

@teste(
    "search biceps 4: pesquisa por músculo (e salta o Ex7)",
    "'biceps' corresponde ao músculo id 1 (exercícios ímpares: 1,3,5,7,9,11). "
    "O Ex7 não tem nome inglês, por isso o resultado é Ex1, Ex3, Ex5, Ex9.",
)
def test_search_musculo():
    with api_falsa():
        r = cli("search", "biceps", "4")
    assert r.exit_code == 0, r.output
    assert nomes(r) == ["Ex1", "Ex3", "Ex5", "Ex9"], nomes(r)


@teste(
    "search arms 3: pesquisa por categoria",
    "'arms' não corresponde a nenhum músculo, mas sim à categoria Arms "
    "(exercícios 1 a 6). Resultado: Ex1, Ex2, Ex3, todos com category Arms.",
)
def test_search_categoria():
    with api_falsa():
        r = cli("search", "arms", "3")
    assert r.exit_code == 0, r.output
    dados = json.loads(r.output)
    assert [e["name"] for e in dados] == ["Ex1", "Ex2", "Ex3"]
    assert all(e["category"] == "Arms" for e in dados)


@teste(
    "search CHEST / chest: ignora maiúsculas e minúsculas",
    "A regex usa re.IGNORECASE, por isso 'CHEST' e 'chest' dão o mesmo resultado.",
)
def test_search_maiusculas():
    with api_falsa():
        a = nomes(cli("search", "CHEST", "3"))
        b = nomes(cli("search", "chest", "3"))
    assert a == b == ["Ex8", "Ex9", "Ex10"], f"{a} / {b}"


@teste(
    "search c 20: junta músculo e categoria sem repetidos",
    "A letra 'c' corresponde aos músculos Biceps e Pecs E à categoria Chest, "
    "logo vários filtros devolvem exercícios repetidos. O resultado final "
    "tem de ter os 11 exercícios, sem nomes duplicados.",
)
def test_search_sem_repetidos():
    with api_falsa():
        r = cli("search", "c", "20")
    assert r.exit_code == 0, r.output
    n = nomes(r)
    assert len(n) == len(set(n)), f"há repetidos: {n}"
    assert len(n) == 11, f"esperava 11, obtive {len(n)}"


@teste(
    "search: respeita o limite N",
    "Mesmo havendo muitos resultados possíveis, nunca devolve mais do que N.",
)
def test_search_limite():
    with api_falsa():
        for n in (1, 2, 5, 6):
            r = cli("search", "c", str(n))
            assert len(nomes(r)) == n, f"N={n}: obtive {len(nomes(r))}"


@teste(
    "search: termo desconhecido e argumentos inválidos",
    "'xyzabc' dá mensagem de erro e código 1 (tratado pelo nosso código). "
    "Falta de argumentos ou N inválido dá código 2 (tratado pelo typer). "
    "Um termo com símbolos de regex ('.*') é tratado como texto normal.",
)
def test_search_erros():
    with api_falsa():
        r = cli("search", "xyzabc", "5")
        assert r.exit_code == 1 and "não corresponde" in r.output
        assert r.output.count("Erro:") == 1, f"mensagem de erro duplicada: {r.output!r}"
        assert cli("search", "biceps").exit_code == 2
        assert cli("search", "biceps", "0").exit_code == 2
        assert cli("search", "biceps", "abc").exit_code == 2
        r = cli("search", ".*", "5")   # re.escape: '.*' não pode apanhar tudo
        assert r.exit_code == 1, "'.*' devia ser tratado como texto literal"


# ===========================================================================
# GRUPO 5: testes ONLINE (API real; só correm com --online)
# ===========================================================================

@teste(
    "ONLINE: a API responde e devolve a estrutura de paginação",
    "Pedido real à wger: estado 200 e campos count, next, results.",
    online=True,
)
def test_online_estrutura():
    r = requests.get(api.BASE_URL + "exerciseinfo/",
                     params={"language": 2, "limit": 2}, timeout=30)
    assert r.status_code == 200, r.status_code
    d = r.json()
    assert {"count", "next", "results"} <= set(d), list(d)
    ex = d["results"][0]
    for campo in ("id", "created", "category", "equipment", "muscles", "translations"):
        assert campo in ex, f"campo '{campo}' não existe: {list(ex)}"


@teste(
    "ONLINE: ordering=-created devolve do mais recente para o mais antigo",
    "Se falhar, a API ignora `ordering`: troca para '-id' no fitcli.py.",
    online=True,
)
def test_online_ordenacao():
    d = requests.get(api.BASE_URL + "exerciseinfo/",
                     params={"language": 2, "ordering": "-created", "limit": 10},
                     timeout=30).json()
    datas = [e["created"] for e in d["results"]]
    assert datas == sorted(datas, reverse=True), f"não está ordenado: {datas}"


@teste(
    "ONLINE: language=2 só devolve exercícios com tradução inglesa",
    "Confirma que o filtro de língua funciona na API real.",
    online=True,
)
def test_online_lingua():
    d = requests.get(api.BASE_URL + "exerciseinfo/",
                     params={"language": 2, "limit": 20}, timeout=30).json()
    for e in d["results"]:
        assert any(t.get("language") == 2 for t in e["translations"]), \
            f"exercício {e['id']} sem tradução inglesa"


@teste(
    "ONLINE: os filtros muscles e category realmente filtram",
    "Compara a contagem total com a contagem filtrada: a filtrada tem de ser "
    "menor. Se forem iguais, o filtro foi ignorado.",
    online=True,
)
def test_online_filtros():
    url = api.BASE_URL + "exerciseinfo/"
    total = requests.get(url, params={"language": 2, "limit": 1}, timeout=30).json()["count"]
    musculo = requests.get(api.BASE_URL + "muscle/", params={"limit": 100},
                           timeout=30).json()["results"][0]["id"]
    categoria = requests.get(api.BASE_URL + "exercisecategory/",
                             timeout=30).json()["results"][0]["id"]
    c_mus = requests.get(url, params={"language": 2, "muscles": musculo, "limit": 1},
                         timeout=30).json()["count"]
    c_cat = requests.get(url, params={"language": 2, "category": categoria, "limit": 1},
                         timeout=30).json()["count"]
    assert c_mus < total, f"filtro muscles ignorado ({c_mus} == {total})"
    assert c_cat < total, f"filtro category ignorado ({c_cat} == {total})"


@teste(
    "ONLINE: top 5 e top 150 (paginação real)",
    "top 5 devolve 5 objetos com os campos certos; top 150 obriga a seguir "
    "`next` e tem de devolver exatamente 150.",
    online=True,
)
def test_online_top():
    with cache_temporaria():
        r = cli("top", "5")
        assert r.exit_code == 0, r.output
        dados = json.loads(r.output)
        assert len(dados) == 5
        assert set(dados[0]) == {"name", "category", "equipment", "muscles"}
        r = cli("top", "150")
        assert r.exit_code == 0, r.output
        assert len(json.loads(r.output)) == 150


@teste(
    "ONLINE: search biceps 5 e search arms 5",
    "Devolvem entre 1 e 5 resultados cada. Para 'biceps', os músculos de cada "
    "resultado devem incluir 'Biceps' (confirma o nome real do músculo).",
    online=True,
)
def test_online_search():
    with cache_temporaria():
        r = cli("search", "biceps", "5")
        assert r.exit_code == 0, r.output
        dados = json.loads(r.output)
        assert 1 <= len(dados) <= 5, f"obtive {len(dados)}"
        assert any("biceps" in m.lower() for e in dados for m in e["muscles"]), dados
        r = cli("search", "arms", "5")
        assert r.exit_code == 0, r.output
        assert 1 <= len(json.loads(r.output)) <= 5


# ---------------------------------------------------------------------------
# Execução
# ---------------------------------------------------------------------------

def main():
    online = "--online" in sys.argv
    verbose = "--verbose" in sys.argv
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    passou = falhou = saltou = 0
    falhas = []
    for i, (so_online, titulo, explicacao, func) in enumerate(TESTES, 1):
        if so_online and not online:
            saltou += 1
            continue
        print(f"\n[{i:02d}] {titulo}")
        print(f"     O que testa: {explicacao}")
        try:
            func()
        except AssertionError as exc:
            falhou += 1
            falhas.append(titulo)
            print(f"     [FALHOU] {exc}")
            if verbose:
                traceback.print_exc()
        except Exception as exc:
            falhou += 1
            falhas.append(titulo)
            print(f"     [ERRO] {type(exc).__name__}: {exc}")
            if verbose:
                traceback.print_exc()
        else:
            passou += 1
            print("     [OK]")

    print("\n" + "=" * 60)
    print(f"Passaram: {passou} | Falharam: {falhou} | Saltados (online): {saltou}")
    if falhas:
        print("Falhas:")
        for f in falhas:
            print(f"  - {f}")
    if saltou:
        print("Dica: corre `python test_fitcli.py --online` para testar a API real.")
    sys.exit(1 if falhou else 0)


if __name__ == "__main__":
    main()
