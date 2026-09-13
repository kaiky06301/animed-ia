"""
Executa a análise de risco sobre a base real do Animed.

Lê os dados pela própria API — a mesma que o aplicativo consome — para que o
motor nunca dependa de exportação manual nem enxergue um retrato desatualizado
do banco.

Uso:
    python3 executar.py                      # usa http://localhost:8080
    python3 executar.py https://api.exemplo  # outro endereço
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from datetime import date

from risco import Faixa, avaliar, priorizar
from sinais import extrair

API_PADRAO = "http://localhost:8080"
CREDENCIAL_DEMO = {"email": "doutor@animed.com.br", "senha": "animed123"}


class Api:
    """Cliente mínimo da API do Animed, autenticado como veterinário."""

    def __init__(self, base: str):
        self.base = base.rstrip("/")
        self.token = self._entrar()

    def _entrar(self) -> str:
        resposta = self._chamar("/api/auth/login", corpo=CREDENCIAL_DEMO)
        return resposta["token"]

    def _chamar(self, caminho: str, corpo=None):
        dados = json.dumps(corpo).encode() if corpo is not None else None
        requisicao = urllib.request.Request(self.base + caminho, data=dados)

        if dados:
            requisicao.add_header("Content-Type", "application/json")
        if getattr(self, "token", None):
            requisicao.add_header("Authorization", f"Bearer {self.token}")

        with urllib.request.urlopen(requisicao) as resposta:
            return json.loads(resposta.read())

    def pets(self) -> list[dict]:
        return self._chamar("/api/pets?size=200")["content"]

    def consultas_do_pet(self, id_pet: int) -> list[dict]:
        return self._chamar(f"/api/consultas/por-pet/{id_pet}?size=200")["content"]

    def vacinas_do_pet(self, id_pet: int) -> list[dict]:
        return self._chamar(f"/api/vacinas/por-pet/{id_pet}?size=200")["content"]

    def medicamentos_do_pet(self, id_pet: int) -> list[dict]:
        try:
            return self._chamar(f"/api/medicamentos/por-pet/{id_pet}")
        except urllib.error.HTTPError:
            return []


def main():
    base = sys.argv[1] if len(sys.argv) > 1 else API_PADRAO

    try:
        api = Api(base)
    except urllib.error.URLError as erro:
        print(f"Não foi possível falar com a API em {base}: {erro.reason}")
        print("Suba a API do Animed antes de rodar a análise.")
        raise SystemExit(1)

    print(f"Analisando a base em {base}\n")

    avaliacoes = []
    for pet in api.pets():
        sinais = extrair(
            pet,
            consultas=api.consultas_do_pet(pet["id"]),
            vacinas=api.vacinas_do_pet(pet["id"]),
            medicamentos=api.medicamentos_do_pet(pet["id"]),
            hoje=date.today(),
        )
        avaliacoes.append(avaliar(sinais))

    fila = priorizar(avaliacoes)
    _imprimir(fila)
    _resumir(fila)


def _imprimir(fila):
    print("FILA DE CUIDADO PREVENTIVO")
    print("=" * 78)

    for posicao, a in enumerate(fila, start=1):
        marcador = {"crítico": "!!", "atenção": " !", "estável": "  "}[a.faixa.value]
        print(f"{marcador} {posicao:2}. {a.nome_pet:12} score {a.score:3}  {a.faixa.value}")
        print(f"      tutor: {a.nome_tutor}")
        print(f"      por quê: {a.explicacao()}")
        print(f"      ação: {a.acao_sugerida}")
        print()


def _resumir(fila):
    total = len(fila)
    criticos = sum(1 for a in fila if a.faixa is Faixa.CRITICO)
    atencao = sum(1 for a in fila if a.faixa is Faixa.ATENCAO)

    print("=" * 78)
    print(f"{total} pacientes analisados: "
          f"{criticos} em risco crítico, {atencao} em atenção, "
          f"{total - criticos - atencao} estáveis")

    if criticos or atencao:
        esforco = criticos + atencao
        print(f"\nA clínica precisa de {esforco} contatos ativos para trazer "
              f"estes pacientes de volta ao ciclo.")


if __name__ == "__main__":
    main()
