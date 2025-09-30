from crewai import Agent, Crew, Process, Task
from crewai.flow.flow import Flow, and_, listen, start, router
from crewai.project import CrewBase, agent, crew, task
from crewai.agents.agent_builder.base_agent import BaseAgent
from crewai.tasks.conditional_task import ConditionalTask
from crewai.tasks.task_output import TaskOutput
from crewai.utilities.prompts import Prompts
from typing import List
from crewai.tools import tool
from crewai_tools import OCRTool, FileWriterTool, MCPServerAdapter
from pydantic import BaseModel, Field
from typing import List
import os
import asyncio

ocr = OCRTool()


server_params_list = [
    # Streamable HTTP Server
#    {
#        "url": "http://127.0.0.1:8000/sse", 
#        "transport": "streamable-http"
#    },
    # SSE Server
    {
        "url": "http://127.0.0.1:8080/sse",
        "transport": "sse"
    },
    {
        "url": "http://127.0.0.1:8081/sse",
        "transport": "sse"
    },
    {
        "url": "http://127.0.0.1:8082/sse",
        "transport": "sse"
    }
]

# Inicializa o adaptador globalmente fora da estrutura de classe
mcp_adapter = None
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


@CrewBase
class Project_2:
    def __init__(self, api_key, api_base, api_version, model_name, max_tokens, temperature, top_p):
        self.api_key = api_key
        self.api_base = api_base
        self.api_version = api_version
        self.model_name = model_name
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.top_p = top_p

    agents: List[Agent]
    tasks: List[Task]


    @agent
    def analista_de_artefatos_linguagem(self) -> Agent:
        return Agent(config=self.agents_config['analista_de_artefatos_linguagem'], verbose=True,reasoning=True,tools=aggregated_tools, allow_delegation=False)

    @agent
    def analista_de_artefatos_banco_dados(self) -> Agent:
        return Agent(config=self.agents_config['analista_de_artefatos_banco_dados'], verbose=True)
   
    @agent
    def especialista_integracao(self) -> Agent:
        return Agent(config=self.agents_config['especialista_integracao'], verbose=True)
    
    @task
    def analisar_linguagem_task(self) -> Task:
        return Task(config=self.tasks_config['analisar_linguagem_task'])

    @task
    def analisar_bd_task(self) -> Task:
        return Task(config=self.tasks_config['analisar_bd_task'])

    @task
    def resumir_resultados_task(self) -> Task:
        return Task(config=self.tasks_config['resumir_resultados_task'], output_file='resumo_resultados.txt')

    @crew
    def crew(self) -> Crew:
    #print(self.api_key, self.model_name, self.max_tokens, self.temperature, self.top_p)
        project_2 = Crew(
            agents=[self.agente_de_entrada(),
                    self.agente_boas_vindas(),
                    self.agente_analista_codigo(),
                    self.agente_categorizador_de_artefatos()],
            tasks=[self.analise_de_entrada_task(),
                   self.analise_boas_vindas_task(),
                   self.analise_codigo_task(),
                   self.categorizar_artefatos_task()],
    #        process=Process.sequential,
            process=Process.hierarchical,
            #manager_agent=self.agente_de_entrada(),
            manager_llm='azure/bnb-gpt-4.1-mini',
            #verbose=True,
            planning_llm="azure/bnb-gpt-4.1-mini",
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
        