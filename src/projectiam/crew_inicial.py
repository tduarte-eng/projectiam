from crewai import Agent, Crew, Process, Task
from crewai.flow.flow import Flow, and_, listen, start, router
from crewai.project import CrewBase, agent, crew, task, after_kickoff
from crewai.agents.agent_builder.base_agent import BaseAgent
from crewai.tasks.conditional_task import ConditionalTask
from crewai.tasks.task_output import TaskOutput
from crewai.utilities.prompts import Prompts
from typing import List
from crewai.tools import tool
from crewai_tools import OCRTool, FileWriterTool, MCPServerAdapter
from pydantic import BaseModel, Field
from typing import List
from datetime import datetime
import os
import asyncio


# Modelo Pydantic corrigido para o output do agente de entrada
# Criar modelos Pydantic específicos para cada tipo de saída
class ClassificacaoOutput(BaseModel):
    agente: str = Field(..., description="Nome do agente que processou a entrada")
    saida: str = Field(..., description="Saída gerada pelo agente")

class AnaliseCodigoOutput(BaseModel):
    agente: str = Field(..., description="Nome do agente que processou a entrada")
    saida: str = Field(..., description="Análise técnica do código")

class ArtefatosOutput(BaseModel):
    agente: str = Field(default="Agente de Artefatos de Tecnologia", description="Nome do agente")
    saida: str = Field(..., description="Tabela de categorização em markdown")

class EventOutput(BaseModel):
    events: List[str] = Field(..., description="Lista de eventos detectados")

# Funções de condição para as conditional tasks
def deve_executar_boas_vindas(output: TaskOutput) -> bool:
    """Verifica se o agente de entrada delegou para o Agente de boas-vindas"""
    try:
        if hasattr(output, 'pydantic') and output.pydantic:
            agente = str(output.pydantic.agente).strip()
            return "Agente de boas-vindas" in agente
        # Fallback: verifica na saída raw
        if hasattr(output, 'raw'):
            return "Agente de boas-vindas" in str(output.raw)
        return False
    except Exception as e:
        print(f"Erro na condição boas-vindas: {e}")
        return False

def deve_executar_analise_codigo(output: TaskOutput) -> bool:
    """Verifica se o agente de entrada delegou para o Analista de Codigo"""
    try:
        if hasattr(output, 'pydantic') and output.pydantic:
            agente = str(output.pydantic.agente).strip()
            return "Analista de Codigo" in agente
        # Fallback: verifica na saída raw
        if hasattr(output, 'raw'):
            return "Analista de Codigo" in str(output.raw)
        return False
    except Exception as e:
        print(f"Erro na condição análise código: {e}")
        return False

def deve_executar_categorizacao_artefatos(output: TaskOutput) -> bool:
    """Verifica se o agente de entrada delegou para o Agente de Artefatos de Tecnologia"""
    try:
        if hasattr(output, 'pydantic') and output.pydantic:
            agente = str(output.pydantic.agente).strip()
            return "Agente de Artefatos de Tecnologia" in agente
        # Fallback: verifica na saída raw
        if hasattr(output, 'raw'):
            return "Agente de Artefatos de Tecnologia" in str(output.raw)
        return False
    except Exception as e:
        print(f"Erro na condição categorização: {e}")
        return False

@CrewBase
class Crew_inicial:
    def __init__(self, api_key, api_base, api_version, model_name, max_tokens, temperature, top_p):
        self.api_key = api_key
        self.api_base = api_base
        self.api_version = api_version
        self.model_name = model_name
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.top_p = top_p

    agents: List[BaseAgent]
    tasks: List[Task]

    #agents: 'config/agents.yaml'
    #tasks: 'config/tasks.yaml'

    @after_kickoff
    def log_results(self, output):
        """
        Callback executado após o kickoff do crew
        """
        print("=" * 60)
        print("🔍 RESULTADO DO CREW - DEBUG")
        print("=" * 60)
        
        # Log do resultado completo
        print(f"📋 Tipo do resultado: {type(output)}")
        print(f"📋 Resultado completo: {output}")
        
        # Tenta acessar os dados via pydantic
        try:
            if hasattr(output, 'pydantic'):
                pydantic_data = output.pydantic
                print(f"📦 Dados Pydantic: {pydantic_data}")
                
                if hasattr(pydantic_data, 'agente'):
                    print(f"🤖 Agente: {pydantic_data.agente}")
                
                if hasattr(pydantic_data, 'saida'):
                    print(f"📤 Saída: {pydantic_data.saida}")
                    
            # Tenta acessar via raw
            if hasattr(output, 'raw'):
                print(f"📝 Raw output: {output.raw}")
                
            # Se for um objeto TaskOutput, acessa suas propriedades
            if hasattr(output, 'json_dict'):
                print(f"📊 JSON Dict: {output.json_dict}")
                
        except Exception as e:
            print(f"❌ Erro ao processar resultado: {e}")
            
        print("=" * 60)
        return output



    @agent
    def agente_de_entrada(self) -> Agent:
        return Agent(config=self.agents_config['agente_de_entrada'], verbose=True)

    @agent
    def agente_boas_vindas(self) -> Agent:
        return Agent(config=self.agents_config['agente_boas_vindas'], verbose=True)
    
    @agent
    def agente_analista_codigo(self) -> Agent:
        return Agent(config=self.agents_config['agente_analista_codigo'], verbose=True)

    @agent
    def agente_categorizador_de_artefatos(self) -> Agent:
        return Agent(config=self.agents_config['agente_categorizador_de_artefatos'], verbose=True)

    @agent
    def analista_de_artefatos_linguagem(self) -> Agent:
        return Agent(config=self.agents_config['analista_de_artefatos_linguagem'], verbose=True)

    @agent
    def analista_de_artefatos_banco_dados(self) -> Agent:
        return Agent(config=self.agents_config['analista_de_artefatos_banco_dados'], verbose=True)
   
    @agent
    def especialista_integracao(self) -> Agent:
        return Agent(config=self.agents_config['especialista_integracao'], verbose=True)

    @task
    def analise_de_entrada_task(self) -> Task:
        return Task(
            config=self.tasks_config['analise_de_entrada_task'],
            output_pydantic=ClassificacaoOutput)

    @task
    def analise_boas_vindas_task(self) ->Task:
        return Task(
            config=self.tasks_config['analise_boas_vindas_task'],
            output_pydantic=ClassificacaoOutput
        )
    
    @task
    def analise_codigo_task(self) -> Task:
        return Task(
            config=self.tasks_config['analise_codigo_task'],
            output_pydantic=AnaliseCodigoOutput
        )

    @task
    def categorizar_artefatos_task(self) -> Task:
        """Task condicional para execução apenas quando delegada"""
        return Task(
            config=self.tasks_config['categorizar_artefatos_task'],
            output_pydantic=ArtefatosOutput
        )

    @task
    def analisar_linguagem_task(self) -> Task:
        return Task(config=self.tasks_config['analisar_linguagem_task'])

    @task
    def analisar_bd_task(self) -> Task:
        return Task(config=self.tasks_config['analisar_bd_task'])

    @task
    def resumir_resultados_task(self) -> Task:
        return Task(config=self.tasks_config['resumir_resultados_task'])


    @crew
    def crew(self) -> Crew:
    #print(self.api_key, self.model_name, self.max_tokens, self.temperature, self.top_p)

        project_crew = Crew(
            agents=[self.agente_boas_vindas(),
                self.agente_analista_codigo(),
                self.agente_categorizador_de_artefatos()
            ],
            tasks=[self.analise_boas_vindas_task(),
                self.analise_codigo_task(),
                self.categorizar_artefatos_task()
            ],
#            process=Process.sequential,
            verbose=True,
            process=Process.hierarchical,
            manager_agent=self.agente_de_entrada(),
#            manager_llm='azure/bnb-gpt-4.1',
            #verbose=True,
#            planning_llm="azure/bnb-gpt-4.1",
            planning=True,
            api_key=self.api_key,
            api_base=self.api_base,
            api_version=self.api_version,
            model=self.model_name,
            provider="azure",
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            top_p=self.top_p
        )
        # You can also see how the task description gets formatted
        return project_crew
        