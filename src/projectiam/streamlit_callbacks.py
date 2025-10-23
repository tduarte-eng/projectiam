import streamlit as st
from typing import Dict, Any, Optional, Callable
import time
from threading import Lock

class StreamlitCallbackManager:
    """
    Gerenciador centralizado de callbacks para integração com Streamlit.
    Controla o progresso e status de diferentes tipos de agentes.
    """
    
    def __init__(self):
        self.status_container = None
        self.progress_container = None
        self.progress_bar = None
        self.current_progress = 0
        self.lock = Lock()
        self.callbacks = {}
        
        # Configurações específicas para cada tipo de agente
        self.agent_configs = {
            "saudacao": {
                "steps": [
                    (20, "👋 Preparando mensagem de boas-vindas..."),
                    (50, "📝 Personalizando saudação..."),
                    (100, "✅ Saudação pronta!")
                ],
                "initial_message": "🔄 Processando saudação...",
                "success_message": "👋 Saudação enviada com sucesso!"
            },
            "codigo": {
                "steps": [
                    (15, "🔍 Analisando estrutura do código..."),
                    (30, "📊 Avaliando qualidade e padrões..."),
                    (50, "🔧 Identificando tecnologias utilizadas..."),
                    (70, "📈 Analisando complexidade e manutenibilidade..."),
                    (85, "💡 Gerando recomendações de melhoria..."),
                    (100, "✅ Análise de código concluída!")
                ],
                "initial_message": "🔄 Iniciando análise de código...",
                "success_message": "💻 Análise de código concluída com sucesso!"
            },
            "artefatos": {
                "steps": [
                    (10, "📝 Analisando entrada do usuário..."),
                    (20, "🎯 Classificando para agente adequado..."),
                    (35, "🔍 Categorizando artefatos técnicos..."),
                    (50, "💻 Analisando linguagens de programação..."),
                    (65, "🗄️ Analisando bancos de dados..."),
                    (80, "🏗️ Avaliando arquitetura e infraestrutura..."),
                    (95, "📊 Consolidando resultados..."),
                    (100, "✅ Análise completa finalizada!")
                ],
                "initial_message": "🔄 Iniciando análise completa de artefatos...",
                "success_message": "🎯 Análise de artefatos concluída com sucesso!"
            }
        }
    
    def initialize_containers(self, status_container, progress_container):
        """Inicializa os containers do Streamlit"""
        self.status_container = status_container
        self.progress_container = progress_container
        self.progress_bar = progress_container.progress(0)
    
    def create_callback(self, agent_type: str) -> Callable:
        """
        Cria um callback específico para um tipo de agente.
        
        Args:
            agent_type: Tipo do agente ('saudacao', 'codigo', 'artefatos')
        
        Returns:
            Função callback configurada para o tipo específico
        """
        if agent_type not in self.agent_configs:
            raise ValueError(f"Tipo de agente '{agent_type}' não suportado")
        
        config = self.agent_configs[agent_type]
        
        def callback_function(output_or_event):
            """
            Callback personalizado para cada tipo de agente.
            
            Args:
                output_or_event: Pode ser TaskOutput, evento ou dict com informações
            """
            try:
                with self.lock:
                    # Verifica se é um evento personalizado (dict) ou TaskOutput
                    if isinstance(output_or_event, dict):
                        self._handle_custom_event(output_or_event, config)
                    else:
                        self._handle_task_output(output_or_event, config)
                        
            except Exception as e:
                self._handle_error(e, agent_type)
        
        return callback_function
    
    def _handle_custom_event(self, event: Dict, config: Dict):
        """Processa eventos personalizados"""
        event_type = event.get('type', 'progress')
        
        if event_type == 'start':
            self._update_status(config['initial_message'])
            self.current_progress = 0
            self._update_progress(0)
            
        elif event_type == 'progress':
            step = event.get('step', 0)
            if 0 <= step < len(config['steps']):
                progress_value, message = config['steps'][step]
                self._update_status(f"🔄 {message}")
                self._update_progress(progress_value)
                self.current_progress = progress_value
                
        elif event_type == 'complete':
            self._update_status(config['success_message'])
            self._update_progress(100)
            time.sleep(1)  # Pausa para visualização
            
        elif event_type == 'error':
            error_msg = event.get('message', 'Erro desconhecido')
            self._update_status(f"❌ Erro: {error_msg}")
    
    def _handle_task_output(self, output, config: Dict):
        """Processa TaskOutput do CrewAI"""
        try:
            # Extrai informações da tarefa
            task_info = "Tarefa concluída"
            if hasattr(output, 'task') and hasattr(output.task, 'description'):
                desc = output.task.description
                task_info = desc[:80] + "..." if len(desc) > 80 else desc
            
            # Determina o progresso baseado no tipo de output
            if hasattr(output, 'raw') and output.raw:
                # Se há output, considera tarefa completa
                self._update_status(config['success_message'])
                self._update_progress(100)
            else:
                # Se não há output ainda, mostra progresso intermediário
                next_step = min(len(config['steps']) - 1, self.current_progress // 20)
                if next_step < len(config['steps']):
                    progress_value, message = config['steps'][next_step]
                    self._update_status(f"🔄 {message}")
                    self._update_progress(progress_value)
            
            print(f"""
                ✅ Callback executado com sucesso!
                📋 Tarefa: {task_info}
                📊 Progresso atual: {self.current_progress}%
                🔍 Tipo Output: {type(output).__name__}
            """)
            
        except Exception as e:
            print(f"Erro ao processar TaskOutput: {e}")
    
    def _handle_error(self, error: Exception, agent_type: str):
        """Trata erros no callback"""
        error_msg = f"Erro no callback {agent_type}: {str(error)}"
        print(f"❌ {error_msg}")
        
        if self.status_container:
            with self.status_container.container():
                st.error(f"❌ {error_msg}")
    
    def _update_status(self, message: str):
        """Atualiza o status no Streamlit"""
        if self.status_container:
            with self.status_container.container():
                if message.startswith("✅"):
                    st.success(message)
                elif message.startswith("❌"):
                    st.error(message)
                else:
                    st.info(message)
    
    def _update_progress(self, value: int):
        """Atualiza a barra de progresso"""
        if self.progress_bar:
            self.progress_bar.progress(min(100, max(0, value)))
    
    def simulate_progress(self, agent_type: str, duration: float = 1.0):
        """
        Simula progresso automático para um tipo de agente.
        
        Args:
            agent_type: Tipo do agente
            duration: Duração total da simulação em segundos
        """
        if agent_type not in self.agent_configs:
            return
        
        config = self.agent_configs[agent_type]
        steps = config['steps']
        
        # Calcula intervalo entre steps
        interval = duration / len(steps)
        
        for i, (progress_value, message) in enumerate(steps):
            self._update_status(f"🔄 {message}")
            self._update_progress(progress_value)
            self.current_progress = progress_value
            
            if i < len(steps) - 1:  # Não pausa no último step
                time.sleep(interval)
    
    def clear_containers(self, delay: float = 2.0):
        """
        Limpa os containers após um delay.
        
        Args:
            delay: Tempo de espera antes de limpar (segundos)
        """
        time.sleep(delay)
        if self.status_container:
            self.status_container.empty()
        if self.progress_container:
            self.progress_container.empty()


# Instância global do gerenciador
callback_manager = StreamlitCallbackManager()

def get_callback_manager() -> StreamlitCallbackManager:
    """Retorna a instância global do gerenciador de callbacks"""
    return callback_manager