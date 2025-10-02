from crewai.flow.flow import Flow, listen, start, router
from dotenv import load_dotenv
from litellm import completion
from pydantic import BaseModel, Field
from crewai.agent import Agent
import asyncio
from typing import Any, Dict, List


load_dotenv()


class ClassificacaoEntrada(BaseModel):
    agente: str = "" # Nome do agente delegado
    saida: str = ""  # Conteúdo da entrada que será tratado pelo próximo agente

# Define flow state
class AnaliseArtefatosState(BaseModel):
    input: str = ""
    analysis: ClassificacaoEntrada | None = None

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
        print(f"Starting market research for {self.state.input}")
        return {"input": self.state.input}

    @listen(entrada)
    async def analisar_entrada(self) -> Dict[str, Any]:
        agente_de_entrada = Agent(
            role="Analisador de Entradas de Dados",
            goal="Classificar e encaminhar entradas para os agentes especializados adequados.",
            backstory=(
                "Você é um especialista em identificar o tipo de conteúdo recebido e decidir para qual agente especializado ele deve ser encaminhado.\n\n"
                "Analise a entrada e classifique em uma das categorias:\n"
                "1. **Lista de artefatos técnicos** (tecnologias, frameworks, linguagens) → \"Agente de Artefatos de Tecnologia\"\n"
                "2. **Código de programação** → \"Analista de Codigo\"\n"
                "3. **Saudações ou conteúdo não técnico** → \"Agente de boas-vindas\"\n\n"
                "FORMATO DE RESPOSTA OBRIGATÓRIO:\n"
                "- Use EXATAMENTE os nomes: \"Agente de Artefatos de Tecnologia\", \"Analista de Codigo\", \"Agente de boas-vindas\"\n"
                "- No campo \"agente\", sempre use: \"[nome do agente]\"\n"
                "- No campo \"saida\", use: {self.state.input} de entrada para ser tratado pelo próximo agente delegado\n\n"
                "EXEMPLOS DE SAÍDA CORRETA:\n"
                "• Para artefatos: {\"agente\": \"Agente de Artefatos de Tecnologia\", \"saida\": {self.state.input}}\n"
                "• Para código: {\"agente\": \"Analista de Codigo\", \"saida\": {self.state.input}}\n"
                "• Para outros: {\"agente\": \"Agente de boas-vindas\", \"saida\": {self.state.input}}"
            ),
            verbose=True,
            llm=self.model1
        )
        query = f"""
        Classifique a seguinte entrada de acordo com as categorias definidas:

        Entrada: {self.state.input}

        Lembre-se:
        - Se for uma lista de tecnologias, frameworks ou linguagens → "Agente de Artefatos de Tecnologia"
        - Se for código de programação → "Agente de Codigo"
        - Se for saudação ou conteúdo não técnico → "Agente de boas-vindas"

        Exemplos de classificação:
            • Agente de Artefatos de Tecnologia: Java 8, Spring Boot 2.3, MySQL 5.7, Angular 12
            • Agente de Codigo: "public class Example..." 
            • Agente de boas-vindas: "Olá, bom dia!"

        FORMATO DE RESPOSTA OBRIGATÓRIO:
        {{"agente": "[nome do agente]", "saida": "{self.state.input}"}}"
        """
        # Execute the analysis with structured output format
        result = await agente_de_entrada.kickoff_async(query, response_format=ClassificacaoEntrada)
        # Extração simplificada dos dados
        agente = ""
        saida = self.state.input

        try:
            # Primeiro tenta acessar via pydantic se disponível
            if hasattr(result, "pydantic") and result.pydantic:
                dados = result.pydantic.dict()
                agente = dados.get("agente", "")
                #saida = dados.get("saida", self.state.input)
            # Depois tenta como dicionário direto
            elif isinstance(result, dict):
                agente = result.get("agente", "")
                #saida = result.get("saida", self.state.input)
            # Por último tenta como objeto com atributos
            elif hasattr(result, "agente") and hasattr(result, "saida"):
                agente = getattr(result, "agente", "")
                #saida = getattr(result, "saida", self.state.input)
        except Exception:
            # Em caso de erro, usa os valores padrão
            pass
        
        # Atualiza o estado uma única vez
        self.state.analysis = ClassificacaoEntrada(agente=agente, saida=saida)
        
        print(f"Classificação concluída: Agente={agente}")
        
        # Retorna os dados para roteamento
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
    def artefatos_tecnologia(self):
        resposta = """TESTE: Artefatos de Tecnologia"""
        return resposta

    @listen("Agente de Codigo")
    def agente_codigo(self):
        print("""TESTE: Agente de Codigosz""")


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