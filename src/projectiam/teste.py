from crewai.flow.flow import Flow, listen, start, router
from dotenv import load_dotenv
from litellm import completion
from pydantic import BaseModel, Field
from crewai.agent import Agent
from crewai import Crew, Task
import asyncio
from typing import Any, Dict, List
import json

load_dotenv()


class ClassificacaoEntrada(BaseModel):
    agente: str = "" # Nome do agente delegado
    saida: str = ""  # Conteúdo da entrada que será tratado pelo próximo agente

# Define flow state
class AnaliseArtefatosState(BaseModel):
    input: str = ""
    analysis: ClassificacaoEntrada | None = None

class ArtefatosTecnologiaResponse(BaseModel):
    tabela_categorizacao: str = ""  # A tabela de categorização em formato markdown
    linguagem_analise: str = ""      # Análise técnica da linguagem, se aplicável

# Create a flow class
class AnaliseArtefatosFlow(Flow[AnaliseArtefatosState]):
    @classmethod
    def configure(cls, api_key, api_base, api_version, model_name, max_tokens=10000, temperature=1.0, top_p=1.0):
        """Configura os parâmetros globais da classe para uso posterior"""
        cls._api_key = api_key
        cls._api_base = api_base
        cls._api_version = api_version
        cls._model_name = model_name
        cls._max_tokens = max_tokens
        cls._temperature = temperature
        cls._top_p = top_p

    def parse_result(result):
        """
        Converte CrewOutput em dict de forma segura.
        """
        data = {}

        # tenta pegar direto do raw
        try:
            if hasattr(result, "raw"):
                raw = result.raw
                # se for string JSON, carregar
                if isinstance(raw, str):
                    data = json.loads(raw)
                elif isinstance(raw, dict):
                    data = raw
        except Exception as e:
            print("Erro ao carregar result.raw:", e)

        # fallback: tenta usar to_dict()
        if not data:
            try:
                data = result.to_dict()
            except Exception:
                pass

        return data or {}

    #def __init__(self, api_key, api_base, api_version, model_name, max_tokens, temperature, top_p):
    #    self.api_key = api_key
    #    self.api_base = api_base
    #    self.api_version = api_version
    #    self.model_name = model_name
    #    self.max_tokens = max_tokens
    #    self.temperature = temperature
    #    self.top_p = top_p
    model1 = "azure/bnb-gpt-4.1-nano"
    model2 = "azure/bnb-gpt-4.1"

    @start()
    def entrada(self) -> Dict[str, str]:
        print(type(self.state.input))
        #entrada = "\n[InputUsuario]: oi"
        self.state.input = self.state.input.replace("\n[InputUsuario]: ", "")
        self.state.input = str(self.state.input)
        print(f"Starting market research for {self.state.input}")
        return {"input": self.state.input}

    @listen(entrada)
    def analisar_entrada(self) -> Dict[str, Any]:
        agente_de_entrada = Agent(
            role="Analisador de Entradas de Dados",
            goal="Classificar e encaminhar entradas para os agentes especializados adequados.",
            backstory="""
                "Você é um especialista em identificar o tipo de conteúdo recebido e decidir para qual agente especializado ele deve ser encaminhado.\n\n"
                "Analise a entrada e classifique em uma das categorias:\n"
                "1. **Lista de artefatos técnicos** (tecnologias, frameworks, linguagens) → \"Agente de Artefatos de Tecnologia\"\n"
                "2. **Código de programação** → \"Agente de Codigo\"\n"
                "3. **Saudações ou conteúdo não técnico** → \"Agente de boas-vindas\"\n\n"
                "FORMATO DE RESPOSTA OBRIGATÓRIO:\n"
                "- Use EXATAMENTE os nomes: \"Agente de Artefatos de Tecnologia\", \"Agente de Codigo\", \"Agente de boas-vindas\"\n"
                "- No campo \"agente\", sempre use: \"[nome do agente]\"\n"
                "- No campo \"saida\", use o input de entrada para ser tratado pelo próximo agente delegado\n\n"
            """,
            verbose=True,
            llm=self.model1
        )
        
        analisar_entrada_task = Task(
            description="""
            Classifique a seguinte entrada de acordo com as categorias definidas:
            Entrada: {input}
            Lembre-se:
            - Se for uma lista de tecnologias, frameworks ou linguagens → "Agente de Artefatos de Tecnologia"
            - Se for um código de programação puro em qualquer linguagem → "Agente de Codigo"
            - Se for saudação ou conteúdo não técnico → "Agente de boas-vindas"
                    Exemplos de classificação:
                        • Agente de Artefatos de Tecnologia: Java 8, Spring Boot 2.3, MySQL 5.7, Angular 12
                        • Agente de Codigo: "public class Example..." 
                        • Agente de boas-vindas: "Olá, bom dia!"
            NÃO FORNEÇA NENHUMA EXPLICAÇÃO, APENAS A SAÍDA NO FORMATO JSON OBRIGATÓRIO.            
            """,
            expected_output="""
                FORMATO DE RESPOSTA OBRIGATÓRIO:
                {"agente": "[nome do agente]", "saida": "{self.state.input}"}
            """,
            agent=agente_de_entrada,
            markdown=True,
            output_pydantic=ClassificacaoEntrada
            #output_file="report.md"
        )
        
        # Execute the analysis with structured output format
        crew = Crew(
           agents=[agente_de_entrada],
           tasks=[analisar_entrada_task],
           verbose=True
        )
        result = crew.kickoff(inputs={"input": self.state.input})
        # Acessando a saída da tarefa
        task_output = analisar_entrada_task.output
        print(result.pydantic.agente)
        agente = task_output.pydantic.agente
        saida = self.state.input  # Mantém a entrada original para o próximo agente
        
        return {"agente": agente, "saida": saida}

    @router(analisar_entrada)
    def router(self, agente):
        print(f"Roteando para o agente: {agente}")
        agente_analysis = agente.get("agente")
        if "Agente de boas-vindas" in agente_analysis:
            return "Agente de boas-vindas"  # Padrão se não identificado
        elif "Agente de Artefatos de Tecnologia" in agente_analysis:
            return "Agente de Artefatos de Tecnologia"
        elif "Agente de Codigo" in agente_analysis:
            return "Agente de Codigo"

    @listen("Agente de boas-vindas")
    def boas_vindas(self):
        resposta = """
Bom dia, sou seu assistente inteligente para avaliação de artefatos de TI com foco em modernização tecnológica.
Minha missão é analisar códigos, configurações, documentos e demais artefatos do seu sistema, e gerar um relatório 
detalhado que mensura o **grau de modernidade**, com base em critérios como:

- **Uso de tecnologias atuais** e sustentáveis.
- Aderência a **boas práticas** de arquitetura e segurança.
- Nível de automação e integração.
- Escalabilidade e modularidade.
- Compatibilidade com ambientes em nuvem e DevOps.

Para começar, você pode enviar:
```bash
# Lista de tecnologias usadas no seu projeto
Java 8, Spring Boot 2.3, MySQL 5.7, Angular 12
```
        """
        return resposta

    @listen("Agente de Artefatos de Tecnologia")
    async def agente_artefatos_tecnologia(self) -> Dict[str, Any]:

        print(f"Analisando artefatos técnicos: {self.state.input}")
        agente_categorizador_de_artefatos = Agent(
            role="Agente de Artefatos de Tecnologia",
            goal="""
                Receber uma entrada de artefatos de tecnologia.
                Identificar, classificar e organizar os artefatos da *ENTRADA* nos grupos nas categorias técnicas.""",
            backstory="""
                Especialista em taxonomia de tecnologias e organização de conhecimento técnico. 
                Sua função é receber uma ENTRADA de ARTEFATOS e categorizar nas seguintes categorias:
                    **Linguagem de Programação**; **Arquitetura de Sistemas**; **Infraestrutura**; **Banco de Dados**; **DevSecOps / Governança**;
                """,
            verbose=True,
            llm=self.model1
        )

#        agente_de_linguagem = Agent(
#            role="Agente de Linguagens de Programação",
#            goal="""
#                Avaliar a modernidade, suporte e práticas associadas às linguagens de programação utilizadas.
#            """,
#            backstory="""
#                Especialista em linguagens de programação, focado em avaliar versões, suporte, frameworks e
#                práticas de desenvolvimento para garantir a modernidade e eficiência do código. 
#                Você deve fornecer um relatório técnico detalhado com base na análise da categoria *Linguagem de Programação*.
#                Você tem acesso ao MCP websearch para pesquisas na WEB.
#                Ao MCP de funções matemáticas. 
#                E ao MCP de consultas a banco de dados de desenvolvedores.
#                """,
#            verbose=True,
#            llm=self.model2
#        )

        categorizar_artefatos_task = Task(
        description="""
            Baseado na decisão do agente de entrada: {input},
            Recebe uma lista de artefatos técnicos, tecnologias, frameworks ou linguagens de programação.
            Identifique e Categorize os artefatos da *ENTRADA* nas seguintes categorias:
                - Linguagem de Programação
                - Arquitetura de Sistemas
                - Infraestrutura
                - Banco de Dados
                - DevSecOps / Governança
            Inclua-a a versão do Artefato.
            SEMPRE deve seguir ORDEM de CATEGORIA
            Não gere recomendações. Não forneça explicações.
            A saída deve ser uma tabela de categorização conforme o exemplo abaixo:
                Uma linha por categoria, mesmo que não se aplique.
                Use "(Nenhum)" na coluna de Artefatos se a categoria não se aplicar.
            IMPORTANTE: 
            - Use APENAS \\n (quebra simples) para quebras de linha na tabela
            - NÃO use \\n\\n (quebra dupla) 
            - Mantenha sempre as 5 categorias na ordem especificada
            - Use "(Nenhum)" se não houver artefatos para uma categoria
            - SEMPRE use os campos CATEGORIA e ARTEFATOS na tabela;""",
        expected_output="""
        Usar sempre esse Modelo de Saída (com quebras simples \\n):   
        | Categoria                 | Artefatos                     |\\n|---------------------------|-------------------------------|\\n| Linguagem de Programação  | Java 11, Java 8, TypeScript   |\\n| Arquitetura de Sistemas   | Jboss, WebSphere v.8.5, nginx |\\n| Infraestrutura            | nginx, Jboss e WebSphere      |\\n| Banco de Dados            | DB2, SQL Server 2016, SQL Server 2019 |\\n| DevSecOps / Governança    | (Nenhum)                      |""",
        agent=agente_categorizador_de_artefatos,
        markdown=True,
        output_pydantic=ArtefatosTecnologiaResponse
        )

        # analisar_linguagem_task = Task(
        #     description="""
        #     Somente Analisar se houver dados do Categorizador de Artefatos.
        #     Analisar SOMENTE a categoria *Linguagem de programação* e avaliar sua modernidade e maturidade.
        #     Se a categoria possuir campo vazio ou "(Nenhum)", responda que não há linguagem para analisar.
        #     Considere os seguintes critérios para a avaliação:
        #         A versão é LTS?
        #         Ainda tem suporte? 
        #         É uma linguagem moderna?
        #         Possui bibliotecas/frameworks atualizados?
        #         Há evidências de testes automatizados?
        #         Há código legado em refatoração?
        #     Sugira melhorias ou modernizações se necessário.
        #     Confirme se a versão da linguagem ainda é suportada.""",
        #     expected_output="""
        #     Exemplo de análise para Java 11:
        #     **Java 11**
        #     ✅ **Modernidade e Suporte**:
        #     - Java 11 é uma versão estável e amplamente utilizada em ambientes corporativos.
        #     - Ainda possui suporte oficial da Oracle e da comunidade OpenJDK.
        #     📚 **Bibliotecas e Frameworks**:
        #     - O projeto utiliza frameworks modernos como **Spring Boot 2.7**, que é compatível com Java 11.
        #     - As dependências estão atualizadas via Maven, com controle de versões centralizado.
        #     🧪 **Testes Automatizados**:
        #     - Há evidências de testes automatizados com **JUnit 5** e cobertura de código via **JaCoCo**.
        #     - O pipeline CI inclui etapas de teste e validação antes do deploy.
        #     🛠️ **Código Legado e Refatoração**:
        #     - Algumas classes antigas ainda utilizam padrões do Java 8, mas estão sendo gradualmente refatoradas para aproveitar recursos como `var`, `HttpClient` e melhorias de desempenho.
        #     💡 **Sugestões de melhoria**:
        #     - Avaliar a migração para **Java 17 LTS**, que oferece melhorias de performance e novos recursos de linguagem.
        #     - Adotar ferramentas de análise estática como **SonarQube** para reforçar a qualidade do código.
        #     - Expandir os testes automatizados para incluir testes de integração com banco de dados e APIs externas.""",
        # agent=agente_de_linguagem,
        # context=categorizar_artefatos_task,
        # #output_pydantic=ArtefatosTecnologiaResponse
        # )

        crew = Crew(
           agents=[agente_categorizador_de_artefatos,
        #           agente_de_linguagem
           ],
           tasks=[categorizar_artefatos_task,
        #           analisar_linguagem_task
           ],
           verbose=True
        )

        result = await crew.kickoff_async(inputs={"input": self.state.input})
        # Acessando a saída da tarefa
        tabela_raw = result.pydantic.tabela_categorizacao
        tabela_formatada = tabela_raw.replace('\n\n', '\n')  # Remove quebras duplas
        #linguagem_analise = result.pydantic.linguagem_analise

        return tabela_formatada


    @listen("Agente de Codigo")
    def agente_codigo(self):
        resposta = """TESTE: Agente de Codigo"""
        return resposta


# Usage example
async def run_flow(inputs: Dict[str, str]):
    flow = AnaliseArtefatosFlow()
    flow.plot("AnaliseArtefatosFlowPlot")
    #result = await flow.kickoff_async(inputs={"input": "Pokemon"})
    result = await flow.kickoff_async(inputs)
    return result


# Run the flow
#if __name__ == "__main__":
#    asyncio.run(run_flow())