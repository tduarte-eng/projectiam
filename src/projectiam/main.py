#!/usr/bin/env python
import sys
import warnings
import os
import tempfile
import streamlit as st
from dotenv import load_dotenv
from pydantic import BaseModel
from datetime import datetime
from loaders import *
from langchain_community.chat_message_histories import ChatMessageHistory
from crew_inicial import Crew_inicial
#from crew_analise2 import Project_2

warnings.filterwarnings("ignore", category=SyntaxWarning, module="pysbd")

load_dotenv()

# Variáveis obrigatórias para Azure OpenAI
api_key = os.getenv("AZURE_API_KEY")
api_base = os.getenv("AZURE_API_BASE")
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
    #api_key = os.getenv("AZURE_API_KEY")
    print(api_key, model_name, api_base, api_version, max_tokens, temperature, top_p)
    # Instancia o projeto passando todas as variáveis
    projeto = Crew_inicial(
        api_key,
        api_base,
        api_version,
        model_name,
        max_tokens,
        temperature,
        top_p
    )
    
    inputs = {
        'topic': mensagens[0][1],
        'current_year': str(datetime.now().year)
    }
    # Executa o Crew
    resultado = projeto.crew().kickoff(inputs=inputs)
    title = resultado.pydantic.agente
    resposta = resultado.pydantic.saida
    if title == "Agente de Artefatos de Tecnologia":
        #sresposta = "Olá! Entrarei no fluxo de Agente de Artefatos de Tecnologia"
        return resposta
        #projeto2 = Project_2(
        #    api_key,
        #    api_base,
        #    api_version,
        #    model_name,
        #    max_tokens,
        #    temperature,
        #    top_p
        #)
        #resultado2 = projeto2.crew().kickoff(inputs=inputs)
        #resposta = resultado2.pydantic.saida   

    else:
        return resposta
    #print(resultado)


def pagina_chat():
    st.header('🤖 Bem-vindo ao IAM (IA de Modernização)', divider=True)

    modelo = st.session_state.get('modelo')
    api_key = st.session_state.get('api_key')
    system_message = st.session_state.get('system_message')
    documento = st.session_state.get('documento', None)  # Novo: guarda o texto do documento

    if not all([modelo, system_message]):
        st.error('Carregue o Oráculo primeiro.')
        st.stop()

    memoria = st.session_state.get('memoria', MEMORIA)
    for mensagem in memoria.messages:
        chat = st.chat_message(mensagem.type)
        chat.markdown(mensagem.content)

    input_usuario = st.chat_input('Fale com o Oráculo')
    if input_usuario:
        chat = st.chat_message('human')
        chat.markdown(input_usuario)

        # Se houver vários documentos/sites, processe cada um individualmente
        documentos = []
        contador = 1
        if documento:
            # Espera-se que documento seja uma string grande, separe por marcador ou adapte para lista de tuplas (nome, conteudo)
            # Exemplo de separação simples:
            for bloco in documento.split('---DOCUMENTO---'):
                if bloco.strip():
                    nome = f"documento{contador}"
                    conteudo = bloco.strip()
                    documentos.append((nome, conteudo))
                    contador = contador + 1
  
        else:
            documentos = []
        
        documentos.append(("InputUsuario", input_usuario))

        for nome, conteudo in documentos:
            print(f"Nome: {nome}\nConteúdo:\n{conteudo}\n{'-'*40}")

        if documentos:
            resposta = chamar_crew(api_key, modelo, documentos)
        else:
            resposta = chamar_crew(input_usuario)
            
        # Junta a entrada do usuário com o texto do documento, se houver
#        if documento and not documento.strip().lower().startswith("erro ao carregar o site"):
#            entrada = f"{input_usuario}\n\n[Conteúdo do documento/site]:\n{documento}"
#        else:
#            entrada = input_usuario

#        resposta = processar_com_crew(entrada)
#        st.write("Saida:", resposta)  # <-- Aqui sim, mostra na interface
        chat = st.chat_message('ai')
        chat.markdown(resposta)

        memoria.add_user_message(input_usuario)
        memoria.add_ai_message(resposta)
        st.session_state['memoria'] = memoria


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
