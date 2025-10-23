# src/research_crew/crew.py
from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from crewai_tools import SerperDevTool
from crewai.agents.agent_builder.base_agent import BaseAgent
from typing import List


class ArtefatosTecnologiaResponse(BaseModel):
    tabela_categorizacao: str = ""  # A tabela de categorização em formato markdown
    linguagem_analise: str = ""      # Análise técnica da linguagem, se aplicável
    sistemas_analise: str = ""       # Análise técnica dos sistemas, se aplicável
    infraestrutura_analise: str = "" # Análise técnica da infraestrutura, se aplicável
    banco_dados_analise: str = ""    # Análise técnica do banco de dados, se aplicável
    devsecops_analise: str = ""      # Análise técnica de DevSecOps, se aplicável


@CrewBase
class CrewClassificacaoArtefatosTecnologicos():
    """Research crew for comprehensive topic analysis and reporting"""

    agents: List[BaseAgent]
    tasks: List[Task]
    
  
    @agent
    def agente_categorizador_de_artefatos(self) -> Agent:
        return Agent(config=self.agents_config['agente_categorizador_de_artefatos'], verbose=True, output_pydantic=ArtefatosTecnologiaResponse)

    @agent
    def agente_de_linguagem(self) -> Agent:
        return Agent(config=self.agents_config['agente_de_linguagem'], verbose=True, output_pydantic=ArtefatosTecnologiaResponse)

    @agent
    def agente_de_sistemas(self) -> Agent:
        return Agent(config=self.agents_config['agente_de_sistemas'], verbose=True, output_pydantic=ArtefatosTecnologiaResponse)

    @agent
    def agente_de_infraestrutura(self) -> Agent:
        return Agent(config=self.agents_config['agente_de_infraestrutura'], verbose=True, output_pydantic=ArtefatosTecnologiaResponse)

    @agent
    def analista_de_banco_dados(self) -> Agent:
        return Agent(config=self.agents_config['analista_de_artefatos_banco_dados'], verbose=True, output_pydantic=ArtefatosTecnologiaResponse)

    @agent
    def especialista_integracao(self) -> Agent:
        return Agent(config=self.agents_config['especialista_integracao'], verbose=True, output_pydantic=ArtefatosTecnologiaResponse)

    # Task de entrada - sempre executada
    @task
    def analise_de_entrada_task(self) -> Task:
        return Task(
            config=self.tasks_config['analise_de_entrada_task'],
            agent=self.agente_de_entrada(),
#            guardrail=validate_routing_output
        )

    # Task de boas-vindas - usa o output da task de entrada
    @task
    def analise_boas_vindas_task(self) -> Task:
        return Task(
            config=self.tasks_config['analise_boas_vindas_task'],
            agent=self.agente_boas_vindas(),
            context=[self.analise_de_entrada_task()],
            output_pydantic=ClassificacaoOutput
        )
    
    # Task de análise de código - usa o output da task de entrada
    @task
    def analise_codigo_task(self) -> Task:
        return Task(
            config=self.tasks_config['analise_codigo_task'],
            agent=self.agente_analista_codigo(),
            context=[self.analise_de_entrada_task()],
            output_pydantic=AnaliseCodigoOutput
        )

    # Task de categorização de artefatos - usa o output da task de entrada
    @task
    def categorizar_artefatos_task(self) -> Task:
        return Task(
            config=self.tasks_config['categorizar_artefatos_task'],
            agent=self.agente_categorizador_de_artefatos(),
            context=[self.analise_de_entrada_task()],
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
            agents=[
#                self.agente_de_entrada(),
                self.agente_boas_vindas(),
                self.agente_analista_codigo(),
                self.agente_categorizador_de_artefatos(),
            ],
            tasks=[
                # 1. Task de entrada sempre executa
                self.analise_de_entrada_task(),
                # 2. Tasks específicas que recebem o contexto da entrada
                self.analise_boas_vindas_task(),
                self.analise_codigo_task(), 
                self.categorizar_artefatos_task(),
            ],
#            process=Process.sequential,
            verbose=True,
            process=Process.hierarchical,
            manager_agent=self.agente_de_entrada(),
#            manager_llm='azure/bnb-gpt-4.1',
            #verbose=True,
#            planning_llm="azure/bnb-gpt-4.1",
#            planning_key=self.api_key,
#            planning=True,
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
