from crewai.flow.flow import Flow, listen, start, router
from dotenv import load_dotenv
from litellm import completion
from pydantic import BaseModel, Field
from crewai.agent import Agent
from crewai import Crew, Task
from crewai.tools import tool
from crewai_tools import OCRTool, FileWriterTool, MCPServerAdapter
import asyncio
from typing import Any, Dict, List, Optional, Callable
import json

load_dotenv()


# Variável global para callback de status
_status_callback: Optional[Callable[[str, int], None]] = None

def set_status_callback(callback: Callable[[str, int], None]):
    """Define a função de callback para receber atualizações de status"""
    global _status_callback
    _status_callback = callback

def update_status(message: str, progress: int = 0):
    """Envia atualização de status para o callback, se definido"""
    if _status_callback:
        _status_callback(message, progress)
#######################################        

# Configuração do MCPServerAdapter
server_params_list = [
    # Streamable HTTP Server
#    {
#        "url": "http://127.0.0.1:8000/sse", 
#        "transport": "streamable-http"
#    },
    # SSE Server
    {
        "url": "http://127.0.0.1:8081/sse",
        "transport": "sse"
    },
    {
        "url": "http://127.0.0.1:8082/sse",
        "transport": "sse"
    },
#    {
#        "url": "http://127.0.0.1:8083/sse",
#        "transport": "sse"
#    }
]
aggregated_tools = []


try:
    # O MCPServerAdapter deve ser usado como um gerenciador de contexto ou acessado diretamente
    # Não use .connect(), use o objeto diretamente ou como context manager
    mcp_adapter = MCPServerAdapter(server_params_list)
    
    # Para obter as ferramentas, use-o como um iterável ou acesse seus atributos
    # Dependendo da versão da biblioteca, pode ser necessário iterar sobre o objeto
    # ou acessar um atributo como .tools
    if hasattr(mcp_adapter, 'tools'):
        aggregated_tools = mcp_adapter.tools
    else:
        # Se não tiver o atributo 'tools', tente usar como iterável
        aggregated_tools = list(mcp_adapter)
    
    print(f"Available aggregated tools: {[getattr(tool, 'name', str(tool)) for tool in aggregated_tools]}")
except Exception as e:
    print(f"Error connecting to MCP server: {e}")
    print("Ensure MCP server is running and accessible with correct configuration.")
#########################################


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
    sistemas_analise: str = ""       # Análise técnica dos sistemas, se aplicável
    infraestrutura_analise: str = "" # Análise técnica da infraestrutura, se aplicável
    banco_dados_analise: str = ""    # Análise técnica do banco de dados, se aplicável
    devsecops_analise: str = ""      # Análise técnica de DevSecOps, se aplicável

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
        update_status("🔄 **Iniciando análise:** Processando entrada de dados...", 5)
        print(type(self.state.input))
        #entrada = "\n[InputUsuario]: oi"
        self.state.input = self.state.input.replace("\n[InputUsuario]: ", "")
        self.state.input = str(self.state.input)
        return {"input": self.state.input}

    @listen(entrada)
    def analisar_entrada(self) -> Dict[str, Any]:
        update_status("🧠 **Agente de Entrada:** Classificando tipo de conteúdo...", 15)

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

        update_status("⚡ **Executando classificação:** Agente analisando conteúdo...", 20)

        result = crew.kickoff(inputs={"input": self.state.input})
        # Acessando a saída da tarefa
        task_output = analisar_entrada_task.output
        print(result.pydantic.agente)
        agente = task_output.pydantic.agente
        saida = self.state.input  # Mantém a entrada original para o próximo agente

        update_status(f"✅ **Classificação concluída:** Direcionando para {agente}", 25)
        
        return {"agente": agente, "saida": saida}

    @router(analisar_entrada)
    def router(self, agente):
        print(f"Roteando para o agente: {agente}")
        agente_analysis = agente.get("agente")
        update_status(f"🎯 **Roteamento:** Direcionando para {agente_analysis}", 30)

        if "Agente de boas-vindas" in agente_analysis:
            return "Agente de boas-vindas"  # Padrão se não identificado
        elif "Agente de Artefatos de Tecnologia" in agente_analysis:
            return "Agente de Artefatos de Tecnologia"
        elif "Agente de Codigo" in agente_analysis:
            return "Agente de Codigo"

    @listen("Agente de boas-vindas")
    def boas_vindas(self):
        #update_status("👋 **Agente de Boas-vindas:** Gerando mensagem de boas-vindas...", 50)

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
        update_status("✅ **Boas-vindas concluída:** Mensagem gerada com sucesso", 100)

        return resposta

    @listen("Agente de Artefatos de Tecnologia")
    async def agente_artefatos_tecnologia(self) -> Dict[str, Any]:

        update_status("🔧 **Agente de Artefatos:** Iniciando análise técnica detalhada...", 35)

        print(f"Analisando artefatos técnicos: {self.state.input}")
        agente_categorizador_de_artefatos = Agent(
            role="Agente de Artefatos de Tecnologia",
            goal="""
                Receber uma entrada de artefatos de tecnologia.
                Identificar, classificar e organizar os artefatos da *ENTRADA* nos grupos nas categorias técnicas.""",
            backstory="""
                Especialista em taxonomia de tecnologias e organização de conhecimento técnico. 
                Sua função é receber uma ENTRADA de ARTEFATOS e categorizar nas seguintes categorias:
                    **Linguagem de Programacao**; **Arquitetura de Sistemas**; **Infraestrutura**; **Banco de Dados**; **DevSecOps / Governanca**;
                """,
            verbose=True,
            llm=self.model1
        )

        agente_de_linguagem = Agent(
            role="Agente de Linguagens de Programação",
            goal="""
                Avaliar a modernidade, suporte e práticas associadas às linguagens de programação utilizadas.
                Fornecer um relatório técnico detalhado com base na análise da categoria *Linguagem de Programacao*.""",
            backstory="""
                Especialista em linguagens de programação, focado em avaliar versões, suporte, frameworks e
                práticas de desenvolvimento para garantir a modernidade e eficiência do código. 
                Você deve fornecer um relatório técnico detalhado com base na análise da categoria *Linguagem de Programacao*.
                """,
            verbose=True,
            llm=self.model1,
            #reasoning=True,  # Ativa raciocínio e planejamento
            #max_reasoning_attempts=3,  # Limite de tentativas de raciocínio
            #max_iter=30,  # Permite mais iterações para planejamento complexo
        )

        agente_de_sistemas = Agent(
            role="Agente de Sistemas",
            goal="""
                Avaliar a modernidade, suporte e práticas associadas aos sistemas utilizados.
                Fornecer um relatório técnico detalhado com base na análise da categoria *Arquitetura de Sistemas*.""",
            backstory="""
                Especialista em arquitetura de sistemas, focado em avaliar a estrutura, design e
                práticas de desenvolvimento para garantir a modernidade e eficiência dos sistemas.
                Você deve fornecer um relatório técnico detalhado com base na análise da categoria *Arquitetura de Sistemas*.
                """,
            verbose=True,
            llm=self.model1
        )
        
        agente_de_infraestrutura = Agent(
            role="Agente de Infraestrutura",
            goal="""
                Avaliar a modernidade, suporte e práticas associadas à infraestrutura utilizada.
                Fornecer um relatório técnico detalhado com base na análise da categoria *Infraestrutura*.""",
            backstory="""
                Especialista em infraestrutura de TI, focado em avaliar servidores, redes, cloud e
                práticas de desenvolvimento para garantir a modernidade e eficiência da infraestrutura. 
                Você deve fornecer um relatório técnico detalhado com base na análise da categoria *Infraestrutura*.
                """,
            verbose=True,
            llm=self.model2
        )
        
        agente_de_devsecops = Agent(
            role="Agente de DevSecOps",
            goal="""
                Avaliar a modernidade, suporte e práticas associadas às ferramentas e processos de DevSecOps utilizados.
                Fornecer um relatório técnico detalhado com base na análise da categoria *DevSecOps / Governança*.""",
            backstory="""
                Especialista em DevSecOps, focado em avaliar ferramentas, automação, segurança e
                práticas de desenvolvimento para garantir a modernidade e segurança do código.
                Você deve fornecer um relatório técnico detalhado com base na análise da categoria *DevSecOps / Governança*.
                """,
            verbose=True,
            llm=self.model2
        )

        agente_de_banco_dados = Agent(
            role="Agente de Banco de Dados",
            goal="""
                Avaliar a modernidade, suporte, segurança e desempenho dos bancos de dados utilizados.
            """,
            backstory="""
                Especialista em bancos de dados, focado em avaliar versões, suporte, segurança e desempenho
                para garantir a eficiência e confiabilidade dos dados. 
                Você deve fornecer um relatório técnico detalhado com base na análise da categoria *Banco de Dados*.
                Considere aspectos como replicação, backup, segurança e tuning de desempenho.
            """,
            verbose=True,
            llm=self.model2
        )

        agente_integracao = Agent(
            role="Especialista em Integração de Resultados",
            goal="Resumir e consolidar todos os resultados das análises anteriores em um único relatório.",
            backstory="""
                Você é um especialista em integração de informações técnicas, capaz de sintetizar dados complexos
                e apresentar um resumo coeso e compreensível. Sua função é garantir que todas as análises anteriores sejam
                integradas de forma clara e concisa, destacando os pontos mais relevantes para a tomada de decisão. 
            """,
            verbose=True,
            llm=self.model2
        )

        categorizar_artefatos_task = Task(
            description="""
                Baseado na decisão do agente de entrada: {input},
                Recebe uma lista de artefatos técnicos, tecnologias, frameworks ou linguagens de programação.
                NÃO INVENTE artefatos que não estejam na *ENTRADA*.
                Identifique e Categorize os artefatos da *ENTRADA* nas seguintes categorias:
                    - Linguagem de Programacao
                    - Arquitetura de Sistemas
                    - Infraestrutura
                    - Banco de Dados
                    - DevSecOps / Governanca
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
                - SEMPRE use os campos CATEGORIA e ARTEFATOS na tabela;
                - Saida em tabela_categorizacao
                """,
            expected_output="""
            Usar sempre esse Modelo de Saída (com quebras simples \\n):   
            | Categoria                 | Artefatos                     |\\n|---------------------------|-------------------------------|\\n| Linguagem de Programacao  | Java 11, Java 8, TypeScript   |\\n| Arquitetura de Sistemas   | Jboss, WebSphere v.8.5, nginx |\\n| Infraestrutura            | nginx, Jboss e WebSphere      |\\n| Banco de Dados            | DB2, SQL Server 2016, SQL Server 2019 |\\n| DevSecOps / Governança    | (Nenhum)                      |""",
            agent=agente_categorizador_de_artefatos,
            markdown=True,
            output_pydantic=ArtefatosTecnologiaResponse
            )

        analisar_linguagem_task = Task(
            description="""
                Somente Analisar se houver dados do Categorizador de Artefatos.
                Analisar SOMENTE a categoria *Linguagem de programacao* e avaliar sua modernidade e maturidade.
                Se a categoria possuir campo vazio ou "(Nenhum)", responda que não há linguagem para analisar.
                
                **PROCESSO DE AVALIAÇÃO DINÂMICA:**
                1. Para CADA linguagem identificada na categoria:
                - Use as ferramentas MCP para pesquisar: "[LINGUAGEM] latest version LTS support roadmap 2024 2025"
                - Pesquise informações sobre: "end of life [LINGUAGEM] [VERSÃO] support status"
                - Verifique: "[LINGUAGEM] ecosystem frameworks libraries 2024"
                
                2. **CRITÉRIOS DE PONTUAÇÃO BASEADOS NA PESQUISA:**
                
                **CRITÉRIO 1 - VERSÃO E SUPORTE LTS (MÁXIMO 8 PONTOS):**
                Para determinar a pontuação, pesquise e avalie:
                - É a versão LTS mais recente disponível? → 8.0 pontos
                - É uma versão LTS anterior mas ainda suportada? → 7.2 pontos  
                - É versão estável mas não LTS? → 6.4 pontos
                - Versão suportada mas considerada antiga? → 5.6 pontos
                - Suporte termina em menos de 1 ano? → 4.8 pontos
                - Versão sem suporte oficial (EOL)? → 2.4 pontos
                - Não especificado? → 0 pontos
                
                **CRITÉRIO 2 - ECOSSISTEMA (MÁXIMO 1 PONTO):**
                Pesquise sobre o ecossistema atual da linguagem:
                - Bibliotecas/frameworks amplamente adotados e atualizados? → 1.0 ponto
                - Ecossistema ativo mas com algumas limitações? → 0.5 ponto
                - Ecossistema estagnado ou limitado? → 0 ponto
                
                **CRITÉRIO 3 - FERRAMENTAS DE TESTE (MÁXIMO 0.5 PONTOS):**
                Pesquise sobre ferramentas de teste disponíveis:
                - Ferramentas maduras e amplamente adotadas? → 0.5 ponto
                - Algumas ferramentas disponíveis? → 0.25 ponto
                - Suporte limitado? → 0 ponto
                
                **CRITÉRIO 4 - MODERNIDADE (MÁXIMO 0.5 PONTOS):**
                Avalie características modernas baseadas na pesquisa:
                - Recursos modernos ativos (async/await, type safety, etc.)? → 0.5 ponto
                - Alguns recursos modernos? → 0.25 ponto
                - Características predominantemente legadas? → 0 ponto
                
                **CONSULTAS DE PESQUISA SUGERIDAS POR LINGUAGEM:**
                - Para Java: "Java [VERSÃO] LTS support roadmap Oracle OpenJDK"
                - Para .NET: ".NET [VERSÃO] support policy Microsoft lifecycle"
                - Para Python: "Python [VERSÃO] support status end of life PSF"
                - Para JavaScript/TypeScript: "ECMAScript [ANO] features TypeScript latest version"
                - Para outras linguagens: "[LINGUAGEM] [VERSÃO] support lifecycle community"
                
                **INSTRUÇÕES ESPECÍFICAS:**
                1. SEMPRE pesquise informações atualizadas antes de pontuar
                2. Use a ferramenta calcular_soma para cada linguagem
                3. Use a ferramenta calcular_media para a pontuação final da categoria
                4. Cite as fontes das informações encontradas
                5. Se a pesquisa não retornar resultados conclusivos, use as informações de contexto como fallback
                
                **FONTES PREFERENCIAIS PARA VALIDAÇÃO:**
                - Sites oficiais das linguagens
                - Documentação de suporte/lifecycle oficial
                - GitHub repos oficiais
                - Stack Overflow Insights
                - Developer surveys (Stack Overflow, JetBrains, etc.)
                
                Saída em linguagem_analise""",
            expected_output="""
                ## Linguagem de Programação:
                Modernidade: [NOTA_MEDIA]/10

                ### [Nome da Linguagem e Versão]:
                
                **Pesquisa Realizada:**
                - Consulta: "[LINGUAGEM] [VERSÃO] LTS support status 2024"
                - Fontes consultadas: [Lista das fontes encontradas]
                
                **Análise Detalhada:**
                - **Suporte e LTS**: [NOTA_LTS]/8.0 - [Status atual baseado na pesquisa]
                - **Ecossistema**: [NOTA_ECO]/1.0 - [Avaliação do ecossistema baseada na pesquisa]
                - **Ferramentas de Teste**: [NOTA_TESTE]/0.5 - [Ferramentas identificadas na pesquisa]
                - **Modernidade**: [NOTA_MOD]/0.5 - [Recursos modernos encontrados]
                - **Total**: [SOMA_TOTAL]/10.0
                
                **Informações Atualizadas Encontradas:**
                - Data de fim de suporte: [DATA ou "Não definida"]
                - Versão LTS atual: [VERSÃO]
                - Próxima versão planejada: [VERSÃO e DATA]
                
                ✅ **Pontos Fortes**: [Baseado nas informações pesquisadas]
                ⚠️ **Pontos de Atenção**: [Riscos identificados na pesquisa]
                💡 **Recomendações**: [Sugestões baseadas no roadmap encontrado]
                
                ---
                
                ### Resumo da Categoria:
                **Média Geral**: [MEDIA_FINAL]/10.0
                
                **Principais Descobertas da Pesquisa:**
                1. [Informação relevante encontrada]
                2. [Segunda informação importante]
                3. [Terceira descoberta]
                
                **Prioridades de Modernização (baseadas na pesquisa atual):**
                1. [Ação prioritária com base nas informações mais recentes]
                2. [Segunda prioridade]
                3. [Terceira prioridade]
                
                **Fontes Consultadas:**
                - [Lista das principais fontes utilizadas na análise]""",
            agent=agente_de_linguagem,
            context=[categorizar_artefatos_task],
            output_pydantic=ArtefatosTecnologiaResponse,
            markdown=True,
            tools=aggregated_tools,
            async_execution=True
        )
        
        analisar_sistemas_task = Task(
            description="""
                Somente Analisar se houver dados do Categorizador de Artefatos.
                Analisar SOMENTE a categoria *Arquitetura de Sistemas* e avaliar sua modernidade e maturidade.
                Se a categoria possuir campo vazio ou "(Nenhum)", responda que não há arquitetura para analisar.
                Considere os seguintes critérios para a avaliação:
                    A arquitetura é monolítica, modular ou baseada em microsserviços?
                    Utiliza padrões modernos de design (ex: REST, event-driven)?
                    Há evidências de escalabilidade e resiliência?
                    Está preparada para nuvem (cloud-native)?
                Sugira melhorias ou modernizações se necessário.
                Gere uma metrica de modernidade de 0 a 10.
                Acesse o MCP para buscar informações atualizadas sobre arquitetura, se necessário.
                Estabeleça pontuação de modernidade para cada artefato:
                    SOBRE ARQUITETURA: (MAXIMO 4 PONTOS)
                        Monolítica: 2
                        Modular: 3
                        Microsserviços: 4
                        (Nenhum)    : 0
                    SOBRE PADRÕES DE DESIGN: (MAXIMO 2 PONTOS)   
                        Modernos e amplamente adotados (REST, GraphQL): 2
                        Moderados (SOAP, RPC): 1
                        Obsoletos ou sem evidências: 0
                    SOBRE ESCALABILIDADE E RESILIÊNCIA: (MAXIMO 2 PONTOS)
                        Evidências claras de escalabilidade e resiliência: 1
                        Algumas evidências: 0.5
                        Sem evidências: 0
                    SOBRE PREPARAÇÃO PARA NUVEM: (MAXIMO 2 PONTOS)
                        Cloud-native com contêineres e orquestração: 2 
                        Parcialmente preparado para nuvem: 1
                        Sem evidências: 0
                Use a ferramenta calcular soma das notas de cada artefato
                Use a ferramenta de calcular media para obter a pontuação final.
                Sugira melhorias ou modernizações para uma pontuação mais alta, se necessário.
                Saida em arquitetura_analise.""",
            expected_output="""
                Exemplo de análise para Arquitetura Monolítica:
                ## Arquitetura de Sistemas:
                ### Arquitetura Monolítica
                ❌ **Modernidade e Escalabilidade**:
                - A arquitetura monolítica pode limitar a escalabilidade horizontal e a agilidade no desenvolvimento.
                - Considerar a adoção de uma arquitetura baseada em microsserviços para melhorar a modularidade e escalabilidade.
                ⚙️ **Padrões de Design**:
                - Atualmente, a aplicação utiliza APIs REST, o que é positivo.
                - Avaliar a introdução de padrões event-driven para melhorar a reatividade e resiliência.
                ☁️ **Preparação para Nuvem**:
                - A aplicação não é totalmente cloud-native, o que pode dificultar a migração para ambientes em nuvem.
                - Recomenda-se a adoção de contêineres (Docker) e orquestração (Kubernetes) para facilitar a implantação em nuvem.
                💡 **Sugestões de melhoria**:
                - Iniciar um plano de migração gradual para microsserviços, começando pelos módulos mais críticos.
                - Implementar práticas de DevOps para acelerar o ciclo de desenvolvimento e implantação.
                - Avaliar o uso de plataformas de nuvem como AWS, Azure ou GCP para aproveitar serviços gerenciados e escalabilidade automática.""",
            agent=agente_de_sistemas,
            context=[categorizar_artefatos_task],
            output_pydantic=ArtefatosTecnologiaResponse,
            markdown=True,
            tools=aggregated_tools, #No tools allowed
            async_execution=True
            )
        
        analisar_infraestrutura_task = Task(
            description="""
                Somente Analisar se houver dados do Categorizador de Artefatos.
                Analisar SOMENTE a categoria *Infraestrutura* e avaliar sua modernidade e maturidade.
                Se a categoria possuir campo vazio ou "(Nenhum)", responda que não há infraestrutura para analisar.
                Considere os seguintes critérios para a avaliação:
                    A infraestrutura é on-premises, cloud ou híbrida?
                    Utiliza contêineres e orquestração (ex: Docker, Kubernetes)?
                    Há evidências de automação (ex: IaC, CI/CD)?
                    Possui monitoramento e logging adequados?
                Sugira melhorias ou modernizações se necessário.
                Gere uma metrica de modernidade de 0 a 10.
                Acesse o MCP para buscar informações atualizadas sobre infraestrutura, se necessário.
                Saida em infraestrutura_analise.""",
            expected_output="""
                Exemplo de análise para Infraestrutura On-Premises:
                ## Infraestrutura:
                ### Infraestrutura On-Premises
                ⚠️ **Modernidade e Flexibilidade**:
                - A infraestrutura on-premises pode limitar a escalabilidade e agilidade.
                - Considerar a adoção de uma estratégia híbrida ou migração para nuvem para aproveitar a elasticidade e serviços gerenciados.
                🐳 **Contêineres e Orquestração**:
                - Adoção de contêineres (ex: Docker) e orquestração (ex: Kubernetes) pode melhorar a portabilidade e escalabilidade.
                - Implementar práticas de CI/CD para automação de testes e deploy.
                ⚙️ **Automação**:
                - Utilização de Infrastructure as Code (IaC) com ferramentas como Terraform ou Ansible pode aumentar a eficiência e reduzir erros manuais.
                - Automatizar processos de provisionamento e configuração.
                📊 **Monitoramento e Logging**:
                - Implementar soluções de monitoramento (ex: Prometheus, Grafana) para visibilidade em tempo real.
                - Centralizar logs com ferramentas como ELK Stack ou Splunk para facilitar a análise.
                💡 **Sugestões de melhoria**:
                - Avaliar a migração para uma solução de nuvem pública (AWS, Azure, GCP) para maior flexibilidade.
                - Adotar práticas de DevOps para acelerar o ciclo de desenvolvimento e implantação.
                - Investir em segurança da infraestrutura, incluindo firewalls, VPNs e políticas de acesso.""",
            agent=agente_de_infraestrutura,
            context=[categorizar_artefatos_task],
            output_pydantic=ArtefatosTecnologiaResponse,
            markdown=True,
            tools=aggregated_tools, #No tools allowed
            async_execution=True
            )

        analisar_bd_task = Task(
            description="""
                Somente Analisar se houver dados do Categorizador de Artefatos.
                Analisar **SOMENTE** a categoria *Banco de Dados* e avaliar sua modernidade, suporte, segurança e desempenho.
                Se a categoria possuir campo vazio ou "(Nenhum)", responda que não há banco de dados para analisar.
                Considere os seguintes critérios para a avaliação:
                    A versão é atual e suportada?
                    Possui mecanismos de replicação e backup?
                    Quais práticas de segurança são aplicadas (criptografia, controle de acesso)?
                    Há evidências de monitoramento e tuning de desempenho?
                Sugira melhorias ou modernizações se necessário.
                Gere uma metrica de modernidade de 0 a 10.
                Acesse o MCP para buscar informações atualizadas sobre o banco de dados, se necessário.
                Saida em banco_de_dados_analise.""",
            expected_output="""
                Exemplo de análise para PostgreSQL 14:
                
                ## Banco de Dados:
                ### PostgreSQL 14

                ✅ **Modernidade e Suporte**:
                - A versão 14 do PostgreSQL é estável e suporte encerra-se em novembro de 2026.
                - Há suporte ativo da comunidade e documentação oficial.
                
                🔄 **Replicação e Backup**:
                - O ambiente utiliza **replicação assíncrona** entre servidores para alta disponibilidade.
                - Backups são realizados diariamente via `pg_dump` e armazenados em ambiente seguro.
                
                🔐 **Segurança**:
                - A base de dados utiliza **criptografia em repouso** via LUKS no disco.
                - O acesso é controlado por roles e permissões específicas.
                - Autenticação via LDAP integrada ao AD corporativo.
                
                📈 **Desempenho e Monitoramento**:
                - Ferramentas como **pg_stat_statements** e **Prometheus + Grafana** são utilizadas para monitoramento.
                - Há evidências de tuning de queries e índices com base em análise de planos de execução.
                
                💡 **Sugestões de melhoria**:
                - Avaliar a adoção de **PostgreSQL 15 ou superior** para recursos avançados de paralelismo.
                - Implementar **backup incremental** com ferramentas como `barman` ou `pgBackRest`.
                - Reforçar a auditoria de acessos com logs centralizados.
                - Considerar a adoção de **particionamento** para tabelas muito grandes, melhorando desempenho.""",
            agent=agente_de_banco_dados,
            context=[categorizar_artefatos_task],
            output_pydantic=ArtefatosTecnologiaResponse,
            markdown=True,
            tools=aggregated_tools, #No tools allowed
            async_execution=True
            )

        analisar_devsecops_task = Task(
            description="""
                Somente Analisar se houver dados do Categorizador de Artefatos.
                Analisar SOMENTE a categoria *DevSecOps / Governança* e avaliar sua modernidade e maturidade.
                Se a categoria possuir campo vazio ou "(Nenhum)", responda que não há DevSecOps para analisar.
                Considere os seguintes critérios para a avaliação:
                    Quais ferramentas de CI/CD são utilizadas?
                    Há práticas de segurança integradas no pipeline (ex: SAST, DAST)?
                    Utiliza Infrastructure as Code (IaC)?
                    Há evidências de monitoramento e compliance?
                Sugira melhorias ou modernizações se necessário.
                Gere uma metrica de modernidade de 0 a 10.
                Acesse o MCP para buscar informações atualizadas sobre DevSecOps, se necessário.
                Saida em devsecops_analise.""",
            expected_output="""
                Exemplo de análise para Jenkins e GitLab CI:
                ## DevSecOps / Governança:
                ### Jenkins e GitLab CI
                ✅ **Ferramentas de CI/CD**:
                - O uso combinado de Jenkins e GitLab CI oferece flexibilidade e robustez no pipeline de integração e entrega contínua.
                - Jenkins é utilizado para builds complexos, enquanto GitLab CI é integrado ao repositório Git para automação de testes e deploy.
                🔒 **Práticas de Segurança**:
                - Integração de ferramentas SAST e DAST no pipeline para identificação de vulnerabilidades.
                - Uso de variáveis de ambiente para gerenciamento seguro de credenciais.
                - Implementação de controles de acesso baseados em função (RBAC) no GitLab.
                📦 **Infrastructure as Code (IaC)**:
                - Utilização de Terraform para provisionamento de infraestrutura em nuvem.
                - Armazenamento de configurações em repositórios Git para versionamento.
                📊 **Monitoramento e Compliance**:
                - Implementação de monitoramento de logs com ELK Stack.
                - Auditoria de acessos e mudanças em infraestrutura.
                💡 **Sugestões de melhoria**:
                - Avaliar a adoção de ferramentas de IaC para maior consistência e reprodutibilidade.
                - Implementar testes automatizados para validação de segurança em cada etapa do pipeline.
                - Reforçar a cultura DevSecOps com treinamentos e workshops para a equipe.
                - Considerar a adoção de ferramentas de orquestração de containers como Kubernetes para maior escalabilidade.""",
            agent=agente_de_devsecops,
            context=[categorizar_artefatos_task],
            output_pydantic=ArtefatosTecnologiaResponse,
            markdown=True,
            tools=aggregated_tools, #No tools allowed
            async_execution=True
            )

        resumir_resultados_task = Task(
            description="""
                Analisar os resultados das tarefas anteriores e gerar um relatório técnico consolidado:
                Verifique se todos os artefatos foram analisados.
                Se houver codigo de programação para analisar, gere a análise do código.
                Se houver artefatos técnicos para categorizar, gere a tabela do categorizador_de_artefatos_task e gere um relatório técnico consolidado.
                O relatório deve focar em quais categorias o usuario deve focar para ter um indice mais moderno;
                O relatorio deve ser adequado para um público técnico. Use uma linguagem formal e técnica, evitando jargões desnecessários.
                A Análise é por categoria.
            """,
            expected_output="""
                # Relatório Técnico de Análise - Sistema S123

                | Categoria                 | Artefatos | Modernidade (0-10) |
                |---------------------------|----------|    --------------------|    
                | Linguagem de Programacao  | java 11, java 8, Typescript |  7.9 |
                | Arquitetura de Sistemas   | Jboss, WebSphere 8.5, nginx |   4 |
                | Infraestrutura            | nginx, Jboss, WebSphere      |  3.5  |
                | Banco de Dados            | DB2, SQL SERVER 2016, SQL SERVER 2019 |       7.3 |       
                | DevSecOps / Governança    | (NENHUM) |  0 |

                ### Análise de Linguagem de Programação
                Modernidade: 7.9/10
                    - Nota Java 11: 9.2
                    - Nota Java 8: 6.1
                    - Nota TypeScript: 8.4
                    - Média da categoria: 7.9

                - Java 11 e Java 8: ambas estão em modo EOL (End of Life), ou seja, fora do ciclo oficial de suporte público. Seu uso implica riscos elevados de segurança, limitações de compatibilidade com frameworks modernos e tendência de problemas com inovação e compliance regulatório. Recomenda-se migração imediata para versões oficialmente suportadas, como Java 17 LTS ou superior.
                - TypeScript: ponto positivo na stack, pois é referência para aplicações modernas em front-end e fullstack, porém a ausência de backends atualizados limita o ganho. Adotar TypeScript nas versões mais recentes e associá-lo a soluções serverless ou microsserviços pode elevar consideravelmente a modernidade da categoria.
                Sugestão principal: Priorizar a atualização de todas as bases Java para release LTS vigente e atrelar práticas de CI/CD modernas com cobertura de testes automatizados e ferramentas de qualidade, como SonarQube.

                ### Análise de Banco de Dados
                Modernidade: 7.3/10
                
                -DB2 (12.x): bastante avançado, moderno, com recursos de AI e cloud, métricas robustas de segurança, replicação e monitoramento. Ideal avaliar uso de serviços gerenciados na nuvem.
                -SQL Server 2016: próximo do fim do suporte estendido, limita uso de recursos e integridade. Sugestão de migração imediata para SQL Server 2019 ou superior.
                -SQL Server 2019: atualizado, seguro, escalável e preparado para ambientes híbridos/cloud. Recomenda-se futura atualização para SQL Server 2022.
                Média da categoria é razoável; migrar instâncias defasadas e integrar ferramentas de auditoria e automação para maior modernidade e segurança.
                
                ### Análise de Arquitetura de Sistemas
                Modernidade: 4/10
                
                -JBoss e WebSphere v.8.5: uso demonstra predominância de arquitetura tradicional monolítica, com limitação de escalabilidade e alto risco operacional/legado. WebSphere 8.5 encontra-se amplamente considerado obsoleto no mercado, com desafios para integrações e evolução.
                -nginx: elemento positivo como proxy e balanceador, permite modernizações rápidas se integrado a práticas de containerização e cloud.
                Não há evidências concretas de uso disseminado de containers, orquestração ou padrões de microsserviços/aplicações cloud-native. Recomenda-se investimento na refatoração da arquitetura, priorizando microsserviços, containers (Docker), orquestração (Kubernetes) e componentes open-source.
                Principal foco de modernização: transição arquitetural para cloud-native, adoção progressiva de microsserviços, automação e APIs modernas.
                
                ### Análise de Infraestrutura
                Modernidade: 3.5/10
                Predomina ambiente tradicional (on-premises ou virtualizado) com servidores de aplicação convencionais e nginx, sem indícios de cloud, containerização ou automação avançada.
                Ausência de práticas de Infrastructure as Code (IaC), automação CI/CD, monitoramento proativo e orquestração indica lacunas em escalabilidade e agilidade operacional.
                Recomendação: evoluir para infraestrutura baseada em containers (Docker), orquestrada por Kubernetes, com automação (Terraform, Ansible) e monitoramento/logging centralizado (Prometheus, Grafana, ELK/Splunk).
                Grande oportunidade de ganho ao migrar ambiente para arquitetura híbrida ou cloud, elevando fortemente o índice de modernidade da categoria.
                
                ### Análise de DevSecOps / Governança
                Modernidade: 0/10
                Não há artefatos, práticas ou ferramentas DevSecOps/governança implementados ou catalogados.
                Forte lacuna em segurança, automação, compliance e rastreabilidade.
                Recomendação: iniciar imediatamente esforços para adoção de DevSecOps com integração de pipelines CI/CD, automação de segurança (SAST/DAST), práticas de Infrastructure as Code (Terraform/Ansible), monitoramento contínuo e controles de auditoria/governança. Implementação acelerada de DevSecOps elevará substancialmente o índice de maturidade e modernidade do ecossistema.
                Resumo executivo para tomada de decisão:

                ### Para alcançar índices de modernidade competitivos, recomenda-se foco prioritário em:

                Migração das linguagens e frameworks para versões LTS suportadas e integração de ferramentas modernas.
                Evolução arquitetural em direção a microsserviços, containers e cloud-native, abandonando servidores de aplicação legados.
                Iniciativas de automação, monitoramento e logging centralizado na infraestrutura, com IaC e DevOps.
                Atualização automática e fortalecimento de segurança/auditoria dos bancos de dados com integração cloud onde possível.
                Implementação acelerada de práticas e ferramentas DevSecOps, integrando segurança, compliance e entrega contínua ponta-a-ponta.
                Estas ações devem ser acompanhadas por avaliação de débitos técnicos, parcerias estratégicas e capacitação da equipe em tecnologias de cloud, containers, automação e segurança.                """,
            agent=agente_integracao,
            context=[analisar_linguagem_task, 
                    analisar_sistemas_task, 
                    analisar_infraestrutura_task, 
                    analisar_bd_task, 
                    analisar_devsecops_task],
            output_pydantic=ArtefatosTecnologiaResponse,
            markdown=True,
            output_file="relatorio_tecnico.md"
        )

        crew = Crew(
           agents=[agente_categorizador_de_artefatos,
                   agente_de_linguagem,
                   agente_de_sistemas,
                   agente_de_infraestrutura,
                   agente_de_banco_dados,
                   agente_de_devsecops,
                   agente_integracao],
           tasks=[categorizar_artefatos_task,
                   analisar_linguagem_task,
                   analisar_sistemas_task,
                   analisar_infraestrutura_task,
                   analisar_bd_task,
                   analisar_devsecops_task,
                   resumir_resultados_task
           ],
           verbose=True
        )
        update_status("🚀 **Executando crew:** Processando análise com todos os agentes...", 95)
       
        inputs_array = [{'input': self.state.input}]
        result = await crew.kickoff_async(inputs={'input': self.state.input})
        # Acessando a saída da tarefa
        
        
        #tabela_raw = result.pydantic.tabela_categorizacao
        #tabela_formatada = tabela_raw.replace('\n\n', '\n')  # Remove quebras duplas

        #dados_linguagem_analise = json.loads(analisar_linguagem_task.output.raw)
        #analise_linguagem = ArtefatosTecnologiaResponse(**dados_linguagem_analise)
        #linguagem_analise = analise_linguagem.linguagem_analise
        
        #tabela_raw = analise_linguagem.tabela_categorizacao
        #tabela_formatada = tabela_raw.replace('\n\n', '\n')  # Remove quebras duplas

        #dados_banco_dados_analise = json.loads(analisar_bd_task.output.raw)
        #analise_banco_dados = ArtefatosTecnologiaResponse(**dados_banco_dados_analise)
        #banco_de_dados_analise = analise_banco_dados.banco_dados_analise

        tabela_formatada = result.pydantic.tabela_categorizacao
        linguagem_analise = result.pydantic.linguagem_analise
        banco_de_dados_analise = result.pydantic.banco_dados_analise
        sistemas_analise = result.pydantic.sistemas_analise
        infraestrutura_analise = result.pydantic.infraestrutura_analise
        devsecops_analise = result.pydantic.devsecops_analise

        print(crew.usage_metrics)
        update_status("✅ **Análise técnica concluída:** Relatório gerado com sucesso!", 100)

        return (f"{tabela_formatada}\n\n  {linguagem_analise} \n\n {banco_de_dados_analise} \n\n {sistemas_analise} \n\n {infraestrutura_analise} \n\n {devsecops_analise}")


    @listen("Agente de Codigo")
    def agente_codigo(self):
        update_status("💻 **Agente de Código:** Analisando código de programação...", 50)
        resposta = """TESTE: Agente de Codigo"""
        update_status("✅ **Análise de código concluída:** Código processado com sucesso", 100)
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