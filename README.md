# 🧠 Animed IA — Priorização preventiva do cuidado

Componente de Inteligência Artificial do **Animed**, solução do squad para o Challenge da empresa parceira **Clyvo VET** — FIAP 2026, turma 2TDSR.

> **Disruptive Architectures: IoT, IoB & Generative IA** · Entrega da Sprint 3

---

## 👥 Squad Animed

| Integrante | RM |
|------------|-----|
| Erick Bernardes Bradaschia | 565733 |
| Gabriel Santos Claudino | 564054 |
| Jonathan Moreira Gomes | 565060 |
| Kaiky de Oliveira Silva | 566067 |
| Lucas Fortes de Lima | 559523 |

---

## 🎯 O problema de negócio

A própria Clyvo VET descreveu a dor: a jornada de saúde do pet é **episódica e reativa**. O tutor procura a clínica quando o problema já aconteceu — sintoma agudo, emergência, vacina atrasada — e some entre um evento e outro.

O Animed já ataca isso com gamificação: transforma cada ato de cuidado em pontos e os pontos em desconto real. Mas a gamificação, sozinha, tem um limite claro:

> **Ela trata todo mundo igual.** Envia o mesmo lembrete para quem nunca falta e para quem sumiu há oito meses. Não sabe *quem* está prestes a sair do ciclo, nem *o que* dizer para cada um.

E a clínica tem um limite ainda mais duro: **não consegue ligar para todo mundo**. Com centenas de pacientes na base, a recepcionista escolhe a dedo quem chamar — e escolhe pelo que lembra, não pelo que os dados mostram.

### O que a IA resolve

Identificar, antes que o vínculo se rompa, **quais pets estão saindo do ciclo de acompanhamento** e recomendar **a próxima ação certa para cada um**, ordenada por quanto dano ela evita.

O resultado é uma fila de trabalho: as primeiras ligações do dia são as que mais impedem que um animal adoeça por falta de prevenção.

### Valor para cada lado

| Para quem | O que muda |
|-----------|------------|
| **Tutor** | Recebe o lembrete certo, no momento certo, sobre o que de fato importa para o seu animal — em vez de notificação genérica que ele aprende a ignorar |
| **Pet** | Deixa de adoecer por prevenção esquecida; o atraso vacinal é interceptado antes de virar doença |
| **Clínica** | A agenda deixa de depender da memória da recepção; a ociosidade vira recorrência e o LTV sobe sem prospecção nova |

---

## 🧩 Abordagem de IA adotada

A solução é **híbrida**, com três camadas que se complementam. A escolha não é de conveniência: cada camada cobre uma fraqueza da outra.

```mermaid
graph LR
    D[(Dados do<br/>Animed)] --> S["1 · Extração<br/>de sinais"]
    S --> M["2 · Classificação<br/>de risco"]
    M --> R["3 · Motor de<br/>regras clínicas"]
    R --> L["4 · Geração de<br/>linguagem (LLM)"]
    L --> A["Ação<br/>priorizada"]

    style M fill:#22D3A0,color:#06281F
    style R fill:#FF8A3D,color:#3B1A05
    style L fill:#8FB4D9,color:#0F1419
```

### 1. Classificação de risco de evasão

**O que faz:** atribui a cada pet um score de 0 a 100 indicando quanto ele está se afastando do ciclo de cuidado.

**Por que assim:** a evasão não é um evento, é um processo — o tutor não decide abandonar o acompanhamento, ele apenas vai adiando. Um score contínuo captura o processo enquanto ele ainda pode ser revertido.

**Por que ainda não é um modelo treinado:** a clínica não acumulou histórico rotulado suficiente — não se sabe ainda quais tutores de fato evadiram — e treinar sem isso produziria um classificador que decora ruído. O que existe hoje é um **baseline interpretável, calibrado com a clínica**, que já entra em produção e serve de linha de comparação: quando houver base rotulada, o modelo treinado terá de provar que supera este número.

Num contexto clínico, essa ordem importa. Um score que o veterinário consegue auditar vale mais do que um número alguns pontos mais preciso que ninguém sabe explicar.

### 2. Motor de regras clínicas

**O que faz:** sobrepõe ao score as regras que não admitem probabilidade.

**Por que é necessário:** vacina vencida é vacina vencida. Se o modelo achar que o risco é baixo, isso não torna o animal protegido. A Resolução CFMV nº 1.321/2020 define a vacinação como ato privativo do médico-veterinário — e o sistema não pode relativizar obrigação clínica com estatística.

O motor de regras tem sempre a última palavra sobre **o que** fazer; o modelo decide apenas **em que ordem**.

### 3. Geração de linguagem

**O que faz:** escreve a mensagem que chega ao tutor, no tom adequado ao caso.

**Por que LLM aqui e não nas outras camadas:** linguagem é exatamente o que um modelo generativo faz bem e o que regra fixa faz mal. "Thor está com a V10 atrasada há 546 dias" e "Notei que faz um tempo que o Thor não vem — a V10 dele venceu" carregam a mesma informação com efeito completamente diferente sobre quem lê.

E é também onde a LLM é segura: ela **não decide nada**. Recebe fatos já apurados e a ação já escolhida, e só os veste de linguagem. Alucinação sobre dosagem ou diagnóstico é impossível porque esses valores nunca são pedidos a ela.

---

## 📊 Dados utilizados

Todos os sinais saem de tabelas que **já existem** no banco do Animed. Nenhum dado novo precisa ser coletado — é a vantagem de o componente nascer depois do produto.

| Sinal | Origem | Como é usado |
|-------|--------|--------------|
| Dias desde o último atendimento | `TB_CONSULTA` (status `REALIZADA`) | Detecta afastamento silencioso |
| Vacinas atrasadas e dias de atraso | `TB_VACINA.DATA_PROXIMA_DOSE` | Maior peso: tem consequência clínica direta |
| Faltas em 12 meses | `TB_CONSULTA` (status `NAO_COMPARECEU`) | Sinaliza desengajamento ativo |
| Cancelamentos em 12 meses | `TB_CONSULTA` (status `CANCELADA`) | Pesa menos: cancelar é mais educado que faltar |
| Taxa de doses no horário | `TB_DOSE_MEDICAMENTO` | Mede adesão real ao tratamento prescrito |
| Tratamentos com doses perdidas seguidas | `TB_MEDICAMENTO` + `TB_DOSE_MEDICAMENTO` | Indica abandono de tratamento em curso |
| Dias desde a última pesagem | `TB_PET.DATA_ULTIMA_PESAGEM` | Sinal mais fraco, porém o mais precoce |
| Retorno já marcado | `TB_CONSULTA` (motivo com "Retorno") | **Abate** o score: a clínica já agiu |
| Perfil do pet | `TB_PET` | Espécie e idade modulam o calendário vacinal esperado |

### Estrutura e utilização

Os dados são lidos **pela própria API REST** que o aplicativo consome — nunca por exportação manual. Isso garante que o motor enxergue o mesmo estado que o veterinário vê na tela, e que qualquer regra de negócio já aplicada na API valha também aqui.

---

## 🏛️ Arquitetura de integração

```mermaid
graph TB
    subgraph CLIENTES["Clientes"]
        APP["📱 Aplicativo<br/>React Native"]
        WEB["🖥️ Painel web<br/>Thymeleaf"]
    end

    subgraph API["API Java · Spring Boot"]
        REST["Controllers REST"]
        SERV["Services<br/>(regra de negócio)"]
        REST --> SERV
    end

    subgraph IA["Componente de IA"]
        EXT["Extração de sinais"]
        RISCO["Classificação<br/>de risco"]
        REGRA["Motor de<br/>regras clínicas"]
        LLM["Geração de<br/>linguagem"]
        EXT --> RISCO --> REGRA --> LLM
    end

    BD[("🗄️ Oracle<br/>10 tabelas")]

    APP --> REST
    WEB --> REST
    SERV --> BD
    EXT -.consome a própria API.-> REST
    LLM --> FILA["Fila de cuidado<br/>preventivo"]
    FILA --> WEB
    FILA --> NOTIF["Notificação<br/>ao tutor"]
    NOTIF --> APP

    style IA fill:#1B2330,color:#F4F6F7
    style RISCO fill:#22D3A0,color:#06281F
    style REGRA fill:#FF8A3D,color:#3B1A05
```

### Fluxo de dados, ponta a ponta

1. **O tutor e o veterinário usam o sistema** — cada consulta concluída, vacina registrada e dose confirmada vira linha no Oracle
2. **O componente lê a base pela API**, autenticado como perfil clínico, respeitando as mesmas permissões do aplicativo
3. **Os sinais são extraídos** e normalizados em números comparáveis entre animais
4. **O risco é classificado** e as regras clínicas sobrepostas
5. **A fila priorizada** aparece no painel do veterinário e dispara a notificação ao tutor
6. **A ação do tutor realimenta a base** — ele agenda, comparece, o veterinário conclui — e o ciclo recomeça com dado novo

O componente é **desacoplado**: não escreve no banco, não altera regra de negócio e pode ser desligado sem afetar o funcionamento do sistema. Ele observa e recomenda.

---

## ▶️ Como executar

### Pré-requisitos

- Python 3.10 ou superior (usa apenas a biblioteca padrão)
- API do Animed no ar — veja [animed-api](https://github.com/kaiky06301/animed-api)

### Executar a análise

```bash
cd motor
python3 executar.py                      # usa http://localhost:8080
python3 executar.py https://api.exemplo  # outro endereço
```

---

## 📈 Resultados parciais

Execução real sobre a base do Animed em **12/09/2026**, com 9 pacientes cadastrados:

```
FILA DE CUIDADO PREVENTIVO
==============================================================================
 !  1. Mia          score  45  atenção
      tutor: Marina Oliveira Silva
      por quê: 1 vacina em atraso (+25); nunca passou por atendimento
               na clínica (+20); atraso vacinal de 490 dias (+15)
      ação: Convocar para atualização da carteira de vacinação

 !  2. Nina         score  30  atenção
      tutor: Carlos Mendes
      por quê: nunca passou por atendimento na clínica (+20);
               1 falta(s) em 12 meses (+10)
      ação: Enviar lembrete de check-up preventivo

    3. Thor         score  25  estável
      tutor: Marina Oliveira Silva
      por quê: 2 vacinas em atraso (+25); atraso vacinal de 546 dias (+15);
               retorno já marcado pela clínica (-15)
      ação: Convocar para atualização da carteira de vacinação
==============================================================================
9 pacientes analisados: 0 em risco crítico, 2 em atenção, 7 estáveis
```

A saída completa está em [`resultados/execucao-12-09-2026.txt`](resultados/execucao-12-09-2026.txt).

### O que esse resultado mostra

- **A Mia lidera** não por um motivo, mas pelo acúmulo: vacina vencida há 490 dias **e** nenhum atendimento registrado. É exatamente o perfil que some sem ninguém notar.
- **O Thor cai para terceiro** apesar de ter *duas* vacinas atrasadas — porque a clínica **já marcou retorno** para ele. O caso está endereçado e não deve competir por atenção com quem ninguém procurou.
- **Sete pacientes estão estáveis** e não precisam de contato ativo. Numa base grande, é isso que torna a fila utilizável: ela diz onde *não* gastar esforço.

---

## 🧰 Tecnologias

| Camada | Tecnologia | Por quê |
|--------|-----------|---------|
| Extração e score | Python 3 (biblioteca padrão) | Sem dependência externa: roda em qualquer máquina e em qualquer esteira |
| Fonte de dados | API REST do Animed (Spring Boot) | Mesma fonte do aplicativo, com as mesmas permissões |
| Geração de linguagem | LLM via API (Sprint 4) | Apenas redação da mensagem, nunca decisão clínica |
| Modelo preditivo | scikit-learn (Sprint 4) | Entra quando houver base rotulada para treinar e validar |

---

## 🗺️ O que vem na Sprint 4

Esta entrega **define e documenta** o componente. A implementação completa é a próxima etapa:

- [ ] Treinar o classificador com a base rotulada acumulada e comparar contra este baseline
- [ ] Integrar a camada de linguagem para gerar as mensagens ao tutor
- [ ] Expor a fila priorizada no painel do veterinário
- [ ] Medir o efeito: taxa de retorno dos pacientes contatados contra o grupo não contatado

---

## 🔗 Repositórios do projeto

| Entrega | Repositório |
|---------|-------------|
| API Java | https://github.com/kaiky06301/animed-api |
| Aplicativo Mobile | https://github.com/kaiky06301/animed-app |
| API .NET | https://github.com/kaiky06301/animed-dotnet |

---

## 🎬 Vídeo pitch

> _(link a inserir)_
