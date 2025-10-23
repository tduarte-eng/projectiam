#!/usr/bin/env python
import sys
import warnings
import os
import tempfile
import streamlit as st
import time
from dotenv import load_dotenv
from pydantic import BaseModel
from datetime import datetime
from loaders import *
from langchain_community.chat_message_histories import ChatMessageHistory
#from crew_inicial import Crew_inicial
from teste  import AnaliseArtefatosFlow, run_flow, set_status_callback
import asyncio
#from crew_analise2 import Project_2

warnings.filterwarnings("ignore", category=SyntaxWarning, module="pysbd")

load_dotenv()

# Variáveis obrigatórias para Azure OpenAI
api_key = os.getenv("AZURE_API_KEY2")
api_base = os.getenv("AZURE_API_BASE2")
api_version = os.getenv("AZURE_API_VERSION")
#model_name = os.getenv("OPENAI_MODEL_NAME")


# Constantes
TIPOS_ARQUIVOS_VALIDOS = ['Site', 'Pdf', 'Csv', 'Txt']
MODELOS_PROXY = [
    'azure/bnb-gpt-4.1', 'azure/bnb-gpt-4.1-mini', 'azure/bnb-gpt-4.1-nano',
    'azure/bnb-gpt-4o', 'azure/bnb-gpt-4o-mini', 'azure/bnb-llama-3.3-70B'
]
MEMORIA = ChatMessageHistory()

# Função para carregar arquivos
def carrega_arquivos(tipo_arquivo, arquivo):
    if tipo_arquivo == 'Site':
        return carrega_site(arquivo)
    if tipo_arquivo in ['Pdf', 'Csv', 'Txt']:
        ext = tipo_arquivo.lower()
        with tempfile.NamedTemporaryFile(suffix=f'.{ext}', delete=False) as temp:
            temp.write(arquivo.read())
            nome_temp = temp.name
        if tipo_arquivo == 'Pdf':
            return carrega_pdf(nome_temp)
        elif tipo_arquivo == 'Csv':
            return carrega_csv(nome_temp)
        elif tipo_arquivo == 'Txt':
            return carrega_txt(nome_temp)

def montar_mensagem_sistema(tipo_arquivo, documento):
    #personalidade = carrega_txt('./personalidade2.md')
    #ref_medicoes = carrega_txt('./ref_medicoes.md')
    mensagem = f"\n"
    if tipo_arquivo and documento:
        mensagem += f"{documento}."
    return mensagem


def carrega_varios_arquivos(tipo_arquivo, arquivos):
    conteudos = []
    if tipo_arquivo == 'Site':
        for url in arquivos:
            try:
                conteudo = carrega_site(url)
                conteudos.append(f"[{url}]:\n{conteudo}")
            except Exception as e:
                conteudos.append(f"[{url}]: Erro ao carregar ({e})")
    else:
        for arquivo in arquivos:
            try:
                conteudo = carrega_arquivos(tipo_arquivo, arquivo)
                nome = getattr(arquivo, 'name', 'arquivo')
                conteudos.append(f"[{nome}]:\n{conteudo}")
            except Exception as e:
                nome = getattr(arquivo, 'name', 'arquivo')
                conteudos.append(f"[{nome}]: Erro ao carregar ({e})")
    return "\n\n".join(conteudos)

def chamar_crew(api_key, model_name, mensagens, max_tokens=10000, temperature=1.0, top_p=1.0):
    """
    Função modificada para incluir informativos visuais durante o processamento
    """
    
    #st.session_state['processando'] = True


    # Cria containers para status dinâmico
    status_container = st.empty()
    progress_bar = st.progress(0)
    details_container = st.empty()
    
    # Define callback para receber atualizações do teste.py
    def status_callback(message: str, progress: int):
        status_container.info(message)
        progress_bar.progress(progress)
        
        # Adiciona detalhes específicos baseados no progresso
        if progress == 15:
            time.sleep(1)
            details_container.markdown("""
            **🔍 Classificação de Entrada:**
            - Identificando tipo de conteúdo
            - Determinando agente especializado
            """)
        elif progress == 40:
            time.sleep(1)
            details_container.markdown("""
            **📊 Categorização em Andamento:**
            - Linguagem de Programação
            - Arquitetura de Sistemas  
            - Infraestrutura
            - Banco de Dados
            - DevSecOps / Governança
            """)
        elif progress == 65:
            time.sleep(1)
            details_container.markdown("""
            **🔬 Análises Especializadas:**
            - ✅ Linguagens avaliadas
            - ✅ Sistemas analisados
            - 🔄 Infraestrutura em análise
            - ⏳ Banco de dados pendente
            - ⏳ DevSecOps pendente
            """)
        elif progress == 85:
            time.sleep(1)
            details_container.markdown("""
            **🔒 Finalizando Análises:**
            - ✅ Linguagens concluídas
            - ✅ Sistemas concluídos
            - ✅ Infraestrutura concluída
            - ✅ Banco de dados concluído
            - 🔄 DevSecOps em análise
            """)
        elif progress >= 95:
            time.sleep(1)
            details_container.markdown("""
            **📈 Consolidação Final:**
            - ✅ Todas as análises concluídas
            - 🔄 Gerando relatório técnico
            - 📊 Calculando métricas de modernidade
            """)
    
    try:
        # Configura o callback no teste.py
        set_status_callback(status_callback)
        
        # Fase inicial: Preparação
        status_container.info("🔄 **Preparando análise:** Configurando agentes especializados...")
        progress_bar.progress(5)
        
        # Processa as mensagens
        topic = ""
        if isinstance(mensagens, list):
            for nome, conteudo in mensagens:
                topic += f"\n[{nome}]: {conteudo}"
        else:
            topic = mensagens
        
        topic = {'input': topic}
        
        # Configura o fluxo
        AnaliseArtefatosFlow.configure(
            api_key=api_key,
            api_base=api_base,
            api_version=api_version,
            model_name=model_name,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p
        )
        
        # Executa o fluxo (que agora enviará atualizações via callback)
        resposta = asyncio.run(run_flow(topic))
        
        # Sucesso final
        status_container.success("✅ **Análise concluída!** Relatório técnico gerado com sucesso.")
        details_container.empty()
        
        # Remove elementos após delay
        time.sleep(1)
        status_container.empty()
        progress_bar.empty()
        
        return resposta
        
    except Exception as e:
        status_container.error(f"❌ **Erro durante processamento:** {str(e)}")
        progress_bar.empty()
        details_container.empty()
        st.error("Falha na análise. Verifique os logs para mais detalhes.")
        return f"Erro durante processamento: {str(e)}"
    finally:
        # Limpa o callback
        set_status_callback(None)
#        st.session_state['processando'] = False

def pagina_chat():
    st.header('🤖 Bem-vindo ao IAM (IA de Modernização)', divider=True)

    modelo = st.session_state.get('modelo')
    api_key = st.session_state.get('api_key')
    system_message = st.session_state.get('system_message')
    documento = st.session_state.get('documento', None)  # Novo: guarda o texto do documento

    # Inicializa o estado de processamento se não existir
    if 'processando' not in st.session_state:
        st.session_state['processando'] = False

    if not all([modelo, system_message]):
        st.error('Carregue o Oráculo primeiro.')
        st.stop()

    memoria = st.session_state.get('memoria', MEMORIA)
    for mensagem in memoria.messages:
        chat = st.chat_message(mensagem.type)
        chat.markdown(mensagem.content)


    # Exibe mensagem informativa quando está processando
    if st.session_state['processando']:
        st.info("🔄 **Processamento em andamento...** Por favor, aguarde a conclusão da análise.")
        st.chat_input(placeholder="Aguarde o processamento atual terminar...", disabled=True)
    
        # Container para exibir o processamento em tempo real
        processing_container = st.container()
        with processing_container:
            st.markdown("### 🔄 **Status do Processamento**")   
    
    
    else:
        input_usuario = st.chat_input(placeholder='Fale com o Oráculo')
        
        if input_usuario:
            # IMEDIATAMENTE define o estado como processando e força rerun
            st.session_state['processando'] = True
            
            # Adiciona a mensagem do usuário ao chat
            chat = st.chat_message('human')
            chat.markdown(input_usuario)
            
            # Adiciona à memória
            memoria = st.session_state.get('memoria', MEMORIA)
            memoria.add_user_message(input_usuario)
            st.session_state['memoria'] = memoria
            
            # Força a atualização da interface para mostrar o estado de processamento
            st.rerun()

    # Processamento real - só executa quando há input pendente
    if st.session_state['processando'] and 'input_pendente' not in st.session_state:
        # Recupera a última mensagem do usuário
        memoria = st.session_state.get('memoria', MEMORIA)
        if memoria.messages and memoria.messages[-1].type == 'human':
            input_usuario = memoria.messages[-1].content
            
            # Processa documentos
            documentos = []
            contador = 1
            if documento:
                for bloco in documento.split('---DOCUMENTO---'):
                    if bloco.strip():
                        nome = f"documento{contador}"
                        conteudo = bloco.strip()
                        documentos.append((nome, conteudo))
                        contador = contador + 1
            else:
                documentos = []
            
            documentos.append(("InputUsuario", input_usuario))

            # Executa o processamento
            try:
                if documentos:
                    resposta = chamar_crew(api_key, modelo, documentos)
                else:
                    resposta = chamar_crew(api_key, modelo, input_usuario)
                    
                # Mostra a resposta
                chat = st.chat_message('ai')
                chat.markdown(resposta)
                
                # Adiciona à memória
                memoria.add_ai_message(resposta)
                st.session_state['memoria'] = memoria
                
            except Exception as e:
                st.error(f"Erro durante o processamento: {str(e)}")
                
            finally:
                # SEMPRE libera o estado de processamento
                st.session_state['processando'] = False
                # Força atualização para liberar o input
                st.rerun()

# Sidebar
def sidebar():
    tabs = st.tabs(['Upload de Arquivos', 'Seleção de Modelos'])
    with tabs[0]:
        # Campo para múltiplas URLs
        urls = st.text_area('Digite uma ou mais URLs (uma por linha)')
        lista_urls = [url.strip() for url in urls.splitlines() if url.strip()]

        # Campo para múltiplos arquivos de qualquer tipo permitido
        tipo_arquivo = st.selectbox('Selecione o tipo de arquivo', TIPOS_ARQUIVOS_VALIDOS[1:])  # Exclui 'Site'
        arquivos = st.file_uploader(
            f'Faça o upload de um ou mais arquivos {tipo_arquivo.lower()}',
            type=[tipo_arquivo.lower()],
            accept_multiple_files=True
        )

    with tabs[1]:
        modelo = st.selectbox('Selecione o modelo do Proxy', MODELOS_PROXY)
        # API Key agora é sempre lida do ambiente, não há input do usuário
        #api_key = os.getenv("AZURE_API_KEY")
        st.session_state['api_key'] = api_key

    if st.button('Inicializar Oráculo', use_container_width=True):
        documento = ""
        # Junta conteúdos de sites
        if lista_urls:
            conteudo_sites = carrega_varios_arquivos('Site', lista_urls)
            documento += '\n---DOCUMENTO---\n' + conteudo_sites.strip()
        # Junta conteúdos de arquivos
        if arquivos:
            conteudo_arquivos = carrega_varios_arquivos(tipo_arquivo, arquivos)
            documento += '\n---DOCUMENTO---\n' + conteudo_arquivos.strip()
        
        if not documento:
            documento = None

        system_message = montar_mensagem_sistema('Múltiplos', documento)
        st.session_state['system_message'] = system_message
        st.session_state['modelo'] = modelo
        st.session_state['documento'] = documento  # Pode ser None

    if st.button('Apagar Histórico de Conversa', use_container_width=True):
        st.session_state['memoria'] = MEMORIA
        st.session_state['documento'] = None  # Limpa o documento também

# ...existing code..

# Main
def main():
    with st.sidebar:
        sidebar()
    pagina_chat()

if __name__ == '__main__':
    main()
