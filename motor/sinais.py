"""
Sinais de adesão ao cuidado, extraídos do que o Animed já registra.

Cada sinal responde a uma pergunta que um veterinário faria ao olhar a ficha:
a vacina está em dia? o tutor apareceu nas últimas consultas? está dando o
remédio no horário? A diferença é que aqui as perguntas são feitas para toda a
base, todos os dias, e não só quando o animal aparece na clínica.

Nenhum sinal precisa de dado novo: todos saem das tabelas que já existem.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Iterable


# Um pet sem nenhum atendimento por mais tempo que isto saiu do ciclo de
# acompanhamento, mesmo que nada de errado tenha acontecido.
DIAS_SEM_CONTATO_PREOCUPANTE = 180

# Abaixo desta taxa de doses no horário, o tratamento não está sendo cumprido
# como prescrito, ainda que o tutor acredite que sim.
ADESAO_MINIMA_ESPERADA = 0.80


@dataclass(frozen=True)
class Sinais:
    """Retrato da adesão de um pet, em números comparáveis entre animais."""

    id_pet: int
    nome_pet: str
    nome_tutor: str

    dias_desde_ultimo_atendimento: int | None
    vacinas_atrasadas: int
    dias_de_maior_atraso_vacinal: int
    faltas_nos_ultimos_doze_meses: int
    cancelamentos_nos_ultimos_doze_meses: int
    taxa_de_doses_no_horario: float | None
    tratamentos_abandonados: int
    dias_desde_ultima_pesagem: int | None
    tem_consulta_agendada: bool

    def como_dicionario(self) -> dict:
        return self.__dict__.copy()


def _dias_ate_hoje(quando: date | datetime | None, hoje: date) -> int | None:
    if quando is None:
        return None
    if isinstance(quando, datetime):
        quando = quando.date()
    return (hoje - quando).days


def extrair(pet: dict, consultas: Iterable[dict], vacinas: Iterable[dict],
            medicamentos: Iterable[dict], hoje: date | None = None) -> Sinais:
    """
    Monta os sinais de um pet a partir dos registros que a API devolve.

    Recebe dicionários crus em vez de entidades para que o motor rode tanto
    sobre a API quanto sobre uma extração do banco, sem depender de nenhuma
    das duas.
    """
    hoje = hoje or date.today()

    consultas = list(consultas)
    vacinas = list(vacinas)
    medicamentos = list(medicamentos)

    # --- Contato: quando este pet esteve na clínica pela última vez ---------
    realizadas = [c for c in consultas if c.get("status") == "REALIZADA"]
    ultima = max((_data(c["dataHora"]) for c in realizadas), default=None)
    dias_sem_contato = _dias_ate_hoje(ultima, hoje)

    # --- Vacinação: o atraso é contado em dias, não só em "sim ou não" ------
    atrasos = []
    for vacina in vacinas:
        proxima = _data(vacina.get("dataProximaDose"))
        if proxima and proxima < hoje:
            atrasos.append((hoje - proxima).days)

    # --- Comparecimento: faltar e cancelar não pesam igual -----------------
    limite = _subtrair_um_ano(hoje)
    faltas = sum(1 for c in consultas
                 if c.get("status") == "NAO_COMPARECEU"
                 and (_data(c["dataHora"]) or hoje) >= limite)
    cancelamentos = sum(1 for c in consultas
                        if c.get("status") == "CANCELADA"
                        and (_data(c["dataHora"]) or hoje) >= limite)

    # --- Medicação: o tratamento está sendo cumprido como prescrito? -------
    doses_previstas = sum(m.get("dosesPrevistas", 0) for m in medicamentos)
    doses_no_horario = sum(m.get("dosesNoHorario", 0) for m in medicamentos)
    taxa = (doses_no_horario / doses_previstas) if doses_previstas else None

    abandonados = sum(
        1 for m in medicamentos
        if m.get("emCurso") and m.get("dosesPerdidas", 0) >= 3
    )

    # --- Acompanhamento de peso: sinal precoce de afastamento --------------
    pesagem = _data(pet.get("dataUltimaPesagem"))

    return Sinais(
        id_pet=pet["id"],
        nome_pet=pet.get("nome", ""),
        nome_tutor=pet.get("nomeTutor", ""),
        dias_desde_ultimo_atendimento=dias_sem_contato,
        vacinas_atrasadas=len(atrasos),
        dias_de_maior_atraso_vacinal=max(atrasos, default=0),
        faltas_nos_ultimos_doze_meses=faltas,
        cancelamentos_nos_ultimos_doze_meses=cancelamentos,
        taxa_de_doses_no_horario=taxa,
        tratamentos_abandonados=abandonados,
        dias_desde_ultima_pesagem=_dias_ate_hoje(pesagem, hoje),
        # A clínica já agiu quando existe consulta marcada *para frente*.
        # Agendamento no passado que continua "AGENDADA" não é cuidado
        # endereçado: é consulta que ninguém resolveu, e abater o score
        # por causa dela esconderia justamente o paciente esquecido.
        tem_consulta_agendada=any(
            c.get("status") == "AGENDADA" and (_data(c.get("dataHora")) or hoje) >= hoje
            for c in consultas
        ),
    )


def _data(valor) -> date | None:
    """Aceita o que a API devolve: ISO com ou sem hora, ou nada."""
    if not valor:
        return None
    if isinstance(valor, (date, datetime)):
        return valor.date() if isinstance(valor, datetime) else valor
    texto = str(valor)[:10]
    try:
        return date.fromisoformat(texto)
    except ValueError:
        return None


def _subtrair_um_ano(quando: date) -> date:
    try:
        return quando.replace(year=quando.year - 1)
    except ValueError:  # 29 de fevereiro
        return quando.replace(year=quando.year - 1, day=28)
