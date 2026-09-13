"""
Classificação de risco de evasão do cuidado.

Este módulo responde a uma pergunta: *este pet está saindo do ciclo de
acompanhamento?* A resposta não é um palpite — é um score explicável, em que
cada ponto tem origem rastreável até um registro do banco.

Por que não um modelo treinado nesta sprint: a clínica ainda não acumulou
histórico rotulado suficiente (quais tutores de fato evadiram) para treinar e
validar um classificador sem cair em sobreajuste. O que existe aqui é o
**baseline interpretável** que cumpre duas funções: entra em produção desde já
e, quando houver base rotulada, vira a linha de comparação contra a qual o
modelo treinado precisa provar que é melhor.

A escolha é deliberada: num contexto clínico, um score que o veterinário
consegue auditar vale mais do que um número alguns pontos mais preciso que
ninguém sabe explicar.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from sinais import ADESAO_MINIMA_ESPERADA, DIAS_SEM_CONTATO_PREOCUPANTE, Sinais


class Faixa(str, Enum):
    """Faixa de risco, no vocabulário que a clínica usa."""

    ESTAVEL = "estável"
    ATENCAO = "atenção"
    CRITICO = "crítico"


@dataclass(frozen=True)
class Motivo:
    """Um pedaço do score, com a explicação que o veterinário vai ler."""

    peso: int
    explicacao: str


@dataclass(frozen=True)
class Avaliacao:
    id_pet: int
    nome_pet: str
    nome_tutor: str
    score: int
    faixa: Faixa
    motivos: list[Motivo]
    acao_sugerida: str

    def explicacao(self) -> str:
        """Texto pronto para a tela do veterinário."""
        linhas = [f"{m.explicacao} ({m.peso:+d})" for m in self.motivos]
        return "; ".join(linhas) if linhas else "Nenhum sinal de afastamento"


# ---------------------------------------------------------------------------
# Os pesos abaixo foram calibrados com a clínica, não escolhidos ao acaso.
# A lógica: o que tem consequência clínica direta pesa mais do que o que
# apenas sugere desinteresse. Vacina vencida expõe o animal a doença; não
# pesar há três meses é só falta de acompanhamento.
# ---------------------------------------------------------------------------

PESO_VACINA_ATRASADA = 25
PESO_ATRASO_VACINAL_LONGO = 15      # acima de 60 dias, soma ao anterior
PESO_SEM_CONTATO = 20
PESO_TRATAMENTO_ABANDONADO = 20
PESO_ADESAO_BAIXA = 15
PESO_FALTA = 10                      # por falta, até o teto
PESO_CANCELAMENTO = 5                # por cancelamento, até o teto
PESO_SEM_PESAGEM = 5

TETO_FALTAS = 20
TETO_CANCELAMENTOS = 10

ABATIMENTO_RETORNO_MARCADO = 15

LIMITE_ATENCAO = 30
LIMITE_CRITICO = 60

DIAS_DE_ATRASO_VACINAL_LONGO = 60
DIAS_SEM_PESAGEM_PREOCUPANTE = 120


def avaliar(sinais: Sinais) -> Avaliacao:
    """Calcula o risco de evasão e a ação que a clínica deveria tomar."""
    motivos: list[Motivo] = []

    # --- Vacinação em atraso: o sinal de maior consequência clínica --------
    if sinais.vacinas_atrasadas:
        plural = "s" if sinais.vacinas_atrasadas > 1 else ""
        motivos.append(Motivo(
            PESO_VACINA_ATRASADA,
            f"{sinais.vacinas_atrasadas} vacina{plural} em atraso",
        ))

        if sinais.dias_de_maior_atraso_vacinal > DIAS_DE_ATRASO_VACINAL_LONGO:
            motivos.append(Motivo(
                PESO_ATRASO_VACINAL_LONGO,
                f"atraso vacinal de {sinais.dias_de_maior_atraso_vacinal} dias",
            ))

    # --- Sumiço: nenhum atendimento há muito tempo -------------------------
    dias = sinais.dias_desde_ultimo_atendimento
    if dias is None:
        motivos.append(Motivo(
            PESO_SEM_CONTATO,
            "nunca passou por atendimento na clínica",
        ))
    elif dias > DIAS_SEM_CONTATO_PREOCUPANTE:
        motivos.append(Motivo(
            PESO_SEM_CONTATO,
            f"sem atendimento há {dias} dias",
        ))

    # --- Tratamento interrompido no meio -----------------------------------
    if sinais.tratamentos_abandonados:
        motivos.append(Motivo(
            PESO_TRATAMENTO_ABANDONADO,
            f"{sinais.tratamentos_abandonados} tratamento(s) com doses perdidas seguidas",
        ))

    # --- Medicação fora do horário prescrito -------------------------------
    taxa = sinais.taxa_de_doses_no_horario
    if taxa is not None and taxa < ADESAO_MINIMA_ESPERADA:
        motivos.append(Motivo(
            PESO_ADESAO_BAIXA,
            f"apenas {taxa:.0%} das doses no horário",
        ))

    # --- Comparecimento ----------------------------------------------------
    if sinais.faltas_nos_ultimos_doze_meses:
        peso = min(sinais.faltas_nos_ultimos_doze_meses * PESO_FALTA, TETO_FALTAS)
        motivos.append(Motivo(
            peso,
            f"{sinais.faltas_nos_ultimos_doze_meses} falta(s) em 12 meses",
        ))

    if sinais.cancelamentos_nos_ultimos_doze_meses:
        peso = min(sinais.cancelamentos_nos_ultimos_doze_meses * PESO_CANCELAMENTO,
                   TETO_CANCELAMENTOS)
        motivos.append(Motivo(
            peso,
            f"{sinais.cancelamentos_nos_ultimos_doze_meses} cancelamento(s) em 12 meses",
        ))

    # --- Acompanhamento de peso: o sinal mais fraco, mas o mais precoce ----
    sem_pesagem = sinais.dias_desde_ultima_pesagem
    if sem_pesagem is not None and sem_pesagem > DIAS_SEM_PESAGEM_PREOCUPANTE:
        motivos.append(Motivo(
            PESO_SEM_PESAGEM,
            f"sem pesagem há {sem_pesagem} dias",
        ))

    score = min(sum(m.peso for m in motivos), 100)

    # Retorno marcado significa que a clínica já agiu: o caso está endereçado
    # e não deve competir por atenção com quem ninguém procurou ainda. O
    # abatimento entra na lista de motivos para que a conta feche na tela —
    # score que não bate com a explicação destrói a confiança no número.
    if sinais.tem_retorno_marcado:
        score = max(score - ABATIMENTO_RETORNO_MARCADO, 0)
        motivos.append(Motivo(
            -ABATIMENTO_RETORNO_MARCADO,
            "retorno já marcado pela clínica",
        ))

    faixa = (Faixa.CRITICO if score >= LIMITE_CRITICO
             else Faixa.ATENCAO if score >= LIMITE_ATENCAO
             else Faixa.ESTAVEL)

    return Avaliacao(
        id_pet=sinais.id_pet,
        nome_pet=sinais.nome_pet,
        nome_tutor=sinais.nome_tutor,
        score=score,
        faixa=faixa,
        motivos=sorted(motivos, key=lambda m: m.peso, reverse=True),
        acao_sugerida=_acao(sinais, faixa),
    )


def _acao(sinais: Sinais, faixa: Faixa) -> str:
    """
    Traduz o risco na próxima ação concreta.

    A ordem importa: resolve-se primeiro o que tem consequência clínica, e não
    o que é mais fácil de automatizar.
    """
    if sinais.vacinas_atrasadas:
        return "Convocar para atualização da carteira de vacinação"

    if sinais.tratamentos_abandonados:
        return "Contato ativo: verificar por que o tratamento foi interrompido"

    taxa = sinais.taxa_de_doses_no_horario
    if taxa is not None and taxa < ADESAO_MINIMA_ESPERADA:
        return "Reforçar orientação de posologia com o tutor"

    if faixa is Faixa.CRITICO:
        return "Agendar retorno de acompanhamento"

    if faixa is Faixa.ATENCAO:
        return "Enviar lembrete de check-up preventivo"

    return "Manter no ciclo normal de lembretes"


def priorizar(avaliacoes: list[Avaliacao]) -> list[Avaliacao]:
    """
    Ordena a fila de trabalho da clínica.

    Uma clínica não consegue ligar para todo mundo: a lista existe para que as
    primeiras ligações sejam as que mais evitam dano.
    """
    return sorted(avaliacoes, key=lambda a: a.score, reverse=True)
