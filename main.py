import streamlit as st
from bigquery import load_messages
import pandas as pd
import httpx
import json
from prompts import (
    SYSTEM_PROMPTS,
    GENERAL_ANALYSIS_PROMPT,
    SUGGESTION_PROMPT,
    DOCUMENTS_CHECKLIST_PROMPT,
    CASE_ANALYSIS_PROMPT,
    LEAD_SUMMARY_PROMPT
)
import ssl
import requests
from requests.exceptions import RequestException
import urllib3
from monday_api import fetch_monday_updates

def generate_grok_response(messages, prompt):
    # Sort messages in ascending order (oldest first)
    messages = messages.sort_values('created_at', ascending=True)
    
    # Prepare the conversation text
    conversation = []
    for _, msg in messages.iterrows():
        role = "Cliente" if msg['message_direction'] == 'received' else "Atendente"
        content = msg['message_text'] or ''
        if msg['ocr_scan']:
            content += f"\nOCR: {msg['ocr_scan']}"
        if msg['file_url']:
            content += f"\n📎 [Anexo: {msg['attachment_filename'] or 'Arquivo'}]({msg['file_url']})"
        if msg['audio_transcription']:
            content += f"\n🎤 Transcrição: {msg['audio_transcription']}"
        conversation.append(f"{role}: {content}")
    
    conversation_text = "\n".join(conversation)
    
    # Prepare the prompt
    full_prompt = GENERAL_ANALYSIS_PROMPT.format(
        conversation_text=conversation_text,
        prompt=prompt
    )
    
    # Call Grok API
    url = "https://api.x.ai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {st.secrets.grok.api_key}",
        "Content-Type": "application/json"
    }
    
    data = {
        "model": "grok-2-latest",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPTS["general"]},
            {"role": "user", "content": full_prompt}
        ],
        "temperature": 0,
        "stream": False
    }
    
    try:
        with httpx.Client(verify=True, timeout=30.0) as client:
            response = client.post(url, headers=headers, json=data)
            response.raise_for_status()
            result = response.json()
            return result['choices'][0]['message']['content']
    except httpx.SSLError as e:
        st.error("Erro de SSL ao conectar com a API. Tentando método alternativo...")
        try:
            with httpx.Client(verify=False, timeout=30.0) as client:
                response = client.post(url, headers=headers, json=data)
                response.raise_for_status()
                result = response.json()
                return result['choices'][0]['message']['content']
        except Exception as e:
            st.error(f"Erro ao tentar método alternativo: {str(e)}")
            return None
    except httpx.RequestError as e:
        st.error(f"Erro ao conectar com a API: {str(e)}")
        return None
    except Exception as e:
        st.error(f"Erro inesperado: {str(e)}")
        return None

def generate_suggestion(messages):
    # Sort messages in ascending order (oldest first)
    messages = messages.sort_values('created_at', ascending=True)
    
    # Get the last message from the client
    last_client_message = messages[messages['message_direction'] == 'received'].iloc[-1]
    
    # Prepare the conversation text
    conversation = []
    for _, msg in messages.iterrows():
        role = "Cliente" if msg['message_direction'] == 'received' else "Atendente"
        content = msg['message_text'] or ''
        if msg['ocr_scan']:
            content += f"\nOCR: {msg['ocr_scan']}"
        if msg['file_url']:
            content += f"\n📎 [Anexo: {msg['attachment_filename'] or 'Arquivo'}]({msg['file_url']})"
        if msg['audio_transcription']:
            content += f"\n🎤 Transcrição: {msg['audio_transcription']}"
        conversation.append(f"{role}: {content}")
    
    conversation_text = "\n".join(conversation)
    
    # Prepare the prompt for suggestion
    full_prompt = SUGGESTION_PROMPT.format(
        conversation_text=conversation_text,
        last_client_message=last_client_message['message_text']
    )
    
    # Call Grok API
    url = "https://api.x.ai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {st.secrets.grok.api_key}",
        "Content-Type": "application/json"
    }
    
    data = {
        "model": "grok-2-latest",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPTS["suggestion"]},
            {"role": "user", "content": full_prompt}
        ],
        "temperature": 0.7,
        "stream": False
    }
    
    try:
        with httpx.Client(verify=True, timeout=30.0) as client:
            response = client.post(url, headers=headers, json=data)
            response.raise_for_status()
            result = response.json()
            return result['choices'][0]['message']['content']
    except Exception as e:
        st.error(f"Erro ao gerar sugestão: {str(e)}")
        return None

def generate_missing_documents(messages):
    # Sort messages in ascending order (oldest first)
    messages = messages.sort_values('created_at', ascending=True)
    
    # Prepare document links dictionary
    document_links = {}
    for _, msg in messages.iterrows():
        if msg['file_url'] and msg['attachment_filename']:
            # Add file to document links with timestamp
            timestamp = msg['created_at'].strftime('%d/%m/%Y %H:%M')
            document_links[msg['attachment_filename']] = {
                'url': msg['file_url'],
                'timestamp': timestamp,
                'ocr': msg['ocr_scan'] if msg['ocr_scan'] else None
            }
    
    # Prepare the conversation text
    conversation = []
    for _, msg in messages.iterrows():
        role = "Cliente" if msg['message_direction'] == 'received' else "Atendente"
        content = msg['message_text'] or ''
        if msg['ocr_scan']:
            content += f"\nOCR: {msg['ocr_scan']}"
        if msg['file_url']:
            content += f"\n📎 [Anexo: {msg['attachment_filename'] or 'Arquivo'}]({msg['file_url']})"
        if msg['audio_transcription']:
            content += f"\n🎤 Transcrição: {msg['audio_transcription']}"
        conversation.append(f"{role}: {content}")
    
    conversation_text = "\n".join(conversation)
    
    # Prepare the prompt for document checklist
    full_prompt = DOCUMENTS_CHECKLIST_PROMPT.format(
        conversation_text=conversation_text
    )
    
    # Call Grok API
    url = "https://api.x.ai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {st.secrets.grok.api_key}",
        "Content-Type": "application/json"
    }
    
    data = {
        "model": "grok-2-latest",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPTS["documents"]},
            {"role": "user", "content": full_prompt}
        ],
        "temperature": 0.7,
        "stream": False
    }
    
    try:
        with httpx.Client(verify=True, timeout=30.0) as client:
            response = client.post(url, headers=headers, json=data)
            response.raise_for_status()
            result = response.json()
            checklist = result['choices'][0]['message']['content']
            
            # Add links to the checklist for documents that were found
            for filename, info in document_links.items():
                if filename in checklist:
                    link_text = f"([Ver documento]({info['url']}) - {info['timestamp']}"
                    if info['ocr']:
                        link_text += f" - OCR: {info['ocr']}"
                    link_text += ")"
                    checklist = checklist.replace(filename, f"{filename} {link_text}")
            
            return checklist
    except Exception as e:
        st.error(f"Erro ao gerar checklist de documentos: {str(e)}")
        return None

def generate_case_analysis(messages):
    # Sort messages in ascending order (oldest first)
    messages = messages.sort_values('created_at', ascending=True)
    
    # Prepare the conversation text
    conversation = []
    for _, msg in messages.iterrows():
        role = "Cliente" if msg['message_direction'] == 'received' else "Atendente"
        content = msg['message_text'] or ''
        if msg['ocr_scan']:
            content += f"\nOCR: {msg['ocr_scan']}"
        if msg['file_url']:
            content += f"\n📎 [Anexo: {msg['attachment_filename'] or 'Arquivo'}]({msg['file_url']})"
        if msg['audio_transcription']:
            content += f"\n🎤 Transcrição: {msg['audio_transcription']}"
        conversation.append(f"{role}: {content}")
    
    conversation_text = "\n".join(conversation)
    
    # Prepare the prompt for case analysis
    full_prompt = CASE_ANALYSIS_PROMPT.format(
        conversation_text=conversation_text
    )
    
    # Call Grok API
    url = "https://api.x.ai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {st.secrets.grok.api_key}",
        "Content-Type": "application/json"
    }
    
    data = {
        "model": "grok-2-latest",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPTS["case_analysis"]},
            {"role": "user", "content": full_prompt}
        ],
        "temperature": 0.7,
        "stream": False
    }
    
    try:
        with httpx.Client(verify=True, timeout=30.0) as client:
            response = client.post(url, headers=headers, json=data)
            response.raise_for_status()
            result = response.json()
            return result['choices'][0]['message']['content']
    except Exception as e:
        st.error(f"Erro ao gerar análise do caso: {str(e)}")
        return None

def calculate_response_time(messages):
    """Calcula o tempo de resposta para cada mensagem recebida."""
    response_times = {}
    
    # Ordenar mensagens por data
    sorted_msgs = messages.sort_values('created_at')
    
    last_received_time = None
    last_received_id = None
    
    for _, msg in sorted_msgs.iterrows():
        if msg['message_direction'] == 'received':
            last_received_time = msg['created_at']
            last_received_id = msg['message_uid']
        elif msg['message_direction'] == 'sent' and last_received_time is not None:
            # Calcular tempo de resposta
            response_time = (msg['created_at'] - last_received_time).total_seconds()
            response_times[last_received_id] = response_time
            last_received_time = None
            last_received_id = None
    
    return response_times

def format_response_time(seconds):
    """Formata o tempo de resposta em uma string legível."""
    if seconds < 60:
        return f"{int(seconds)} segundos"
    elif seconds < 3600:
        minutes = int(seconds / 60)
        return f"{minutes} minutos"
    elif seconds < 86400:
        hours = int(seconds / 3600)
        return f"{hours} horas"
    else:
        days = int(seconds / 86400)
        return f"{days} dias"

def calculate_average_response_time(df):
    """Calcula a média dos tempos de resposta para todas as mensagens."""
    # Calcular tempos de resposta
    response_times = calculate_response_time(df)
    
    if not response_times:
        return None
    
    # Calcular média
    avg_time = sum(response_times.values()) / len(response_times)
    return avg_time

def send_whatsapp_message(phone, message, test_mode=False, test_phone=None):
    """Envia mensagem via WhatsApp usando a API do Timelines."""
    # Desabilitar avisos de SSL inseguro
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    # Configurações da API
    url = "https://app.timelines.ai/integrations/api/messages"
    headers = {
        "accept": "application/json",
        "Authorization": f"Bearer {st.secrets.timelines.api_key}",
        "Content-Type": "application/json",
        "X-CSRFToken": "TgkuQJWPDaLbuSWXe6f6vBCXZdrtfUsuRmodEaZ5pNCVpLUQPktIjvEleAb7nztu"
    }
    
    # Dados da mensagem
    data = {
        "phone": test_phone if test_mode else phone,
        "whatsapp_account_phone": "+5511988094449",
        "text": message,
        "label": "customer",
        "chat_name": "Rosenbaum Chat"
    }
    
    try:
        # Criar um pool de conexões
        http = urllib3.PoolManager(
            timeout=urllib3.Timeout(connect=5.0, read=20.0),
            retries=urllib3.Retry(3),
            cert_reqs='CERT_NONE'  # Desabilitar verificação SSL
        )
        
        # Tentar fazer a requisição
        encoded_data = json.dumps(data).encode('utf-8')
        response = http.request('POST', url, body=encoded_data, headers=headers)
        
        # Verificar o status da resposta
        if response.status == 200:
            mode_text = "modo teste" if test_mode else "cliente"
            return True, f"Mensagem enviada com sucesso para {mode_text} ({data['phone']})!"
        else:
            error_msg = f"Erro na API: Status {response.status}"
            try:
                error_data = json.loads(response.data.decode('utf-8'))
                error_msg += f" - {error_data.get('message', 'Erro desconhecido')}"
            except:
                pass
            return False, error_msg
            
    except urllib3.exceptions.MaxRetryError:
        return False, "Erro: Número máximo de tentativas excedido. Verifique sua conexão com a internet."
    except urllib3.exceptions.TimeoutError:
        return False, "Erro: Tempo limite excedido. Verifique sua conexão com a internet."
    except urllib3.exceptions.ProtocolError as e:
        return False, f"Erro de protocolo: {str(e)}"
    except urllib3.exceptions.HTTPError as e:
        return False, f"Erro HTTP: {str(e)}"
    except Exception as e:
        return False, f"Erro inesperado: {str(e)}"

# Adicionar função para atualizar o histórico de mensagens
def add_message_to_history(df, sender_name, sender_phone, recipient_name, recipient_phone, message_text, message_direction='sent'):
    """Adiciona uma nova mensagem ao DataFrame de histórico."""
    new_message = pd.DataFrame({
        'created_at': [pd.Timestamp.now(tz='America/Sao_Paulo')],
        'message_direction': [message_direction],
        'sender_name': [sender_name],
        'sender_phone': [sender_phone],
        'recipient_name': [recipient_name],
        'recipient_phone': [recipient_phone],
        'message_text': [message_text],
        'message_uid': [f"msg_{pd.Timestamp.now().timestamp()}"],
        'account_name': ['Rosenbaum Chat']
    })
    return pd.concat([df, new_message], ignore_index=True)

def generate_lead_status_summary(messages, monday_info):
    """Gera um resumo do status do lead usando IA."""
    # Sort messages in ascending order (oldest first)
    messages = messages.sort_values('created_at', ascending=True)
    
    # Prepare the conversation text
    conversation = []
    for _, msg in messages.iterrows():
        role = "Cliente" if msg['message_direction'] == 'received' else "Atendente"
        content = msg['message_text'] or ''
        if msg['ocr_scan']:
            content += f"\nOCR: {msg['ocr_scan']}"
        if msg['file_url']:
            content += f"\n📎 [Anexo: {msg['attachment_filename'] or 'Arquivo'}]({msg['file_url']})"
        if msg['audio_transcription']:
            content += f"\n🎤 Transcrição: {msg['audio_transcription']}"
        conversation.append(f"{role}: {content}")
    
    conversation_text = "\n".join(conversation)
    
    # Fetch Monday updates if we have an item ID
    monday_updates = []
    if monday_info.get('item_id'):
        try:
            updates = fetch_monday_updates([monday_info['item_id']])
            if updates and len(updates) > 0:
                monday_updates = updates[0].get('updates', [])
        except Exception as e:
            st.warning(f"Não foi possível buscar atualizações do Monday: {str(e)}")
    
    # Prepare Monday info text
    monday_text = f"""
    Dados do Monday:
    - Nome: {monday_info.get('name', 'N/A')}
    - Título: {monday_info.get('title', 'N/A')}
    - Status: {monday_info.get('status', 'N/A')}
    - Prioridade: {monday_info.get('prioridade', 'N/A')}
    - Origem: {monday_info.get('origem', 'N/A')}
    - Email: {monday_info.get('email', 'N/A')}
    """
    
    # Add updates to Monday info if available
    if monday_updates:
        monday_text += "\nAtualizações recentes:\n"
        for update in monday_updates:
            monday_text += f"- {update.get('created_at', 'N/A')}: {update.get('body', 'N/A')}\n"
    
    # Prepare the prompt for lead status summary
    full_prompt = LEAD_SUMMARY_PROMPT.format(
        conversation_text=conversation_text,
        chat_info=monday_text
    )
    
    # Call Grok API
    url = "https://api.x.ai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {st.secrets.grok.api_key}",
        "Content-Type": "application/json"
    }
    
    data = {
        "model": "grok-2-latest",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPTS["summary"]},
            {"role": "user", "content": full_prompt}
        ],
        "temperature": 0.7,
        "stream": False
    }
    
    try:
        with httpx.Client(verify=True, timeout=30.0) as client:
            response = client.post(url, headers=headers, json=data)
            response.raise_for_status()
            result = response.json()
            return result['choices'][0]['message']['content']
    except Exception as e:
        st.error(f"Erro ao gerar resumo do lead: {str(e)}")
        return None

st.set_page_config(
    page_title="Rosenbaum Advogados AI",
    layout="wide"
)

# Initialize session state for navigation and pagination
if 'current_page' not in st.session_state:
    st.session_state.current_page = "inbox"
if 'display_count' not in st.session_state:
    st.session_state.display_count = 20
if 'prompts' not in st.session_state:
    st.session_state.prompts = {
        "general": SYSTEM_PROMPTS["general"],
        "suggestion": SYSTEM_PROMPTS["suggestion"],
        "documents": SYSTEM_PROMPTS["documents"],
        "case_analysis": SYSTEM_PROMPTS["case_analysis"],
        "summary": """Você é um assistente especializado em análise de leads jurídicos. 
Sua função é gerar resumos claros e objetivos do status do lead, focando em informações relevantes para o acompanhamento do caso."""
    }
if 'messages_df' not in st.session_state:
    st.session_state.messages_df = load_messages()
if 'grok_chat_history' not in st.session_state:
    st.session_state.grok_chat_history = []

df = st.session_state.messages_df

# Verificar se as colunas necessárias existem
required_columns = ['created_at', 'message_direction', 'sender_name', 'sender_phone', 'recipient_name', 'recipient_phone', 'message_uid', 'account_name', 'ocr_scan', 'file_url']
missing_columns = [col for col in required_columns if col not in df.columns]

if missing_columns:
    st.error(f"Colunas necessárias não encontradas no DataFrame: {missing_columns}")
    st.write("Colunas disponíveis:", df.columns.tolist())
    st.stop()

# Converter created_at para datetime e ajustar timezone
df['created_at'] = pd.to_datetime(df['created_at']).dt.tz_convert('America/Sao_Paulo')

# Prepare grouped data for inbox and chat
received_messages = df[df['message_direction'] == 'received'].copy()
received_messages = received_messages.rename(columns={
    'sender_name': 'Nome',
    'sender_phone': 'Telefone'
})

# Get all messages for each conversation to determine last message direction
all_messages = df.copy()
all_messages['conversation_key'] = all_messages.apply(
    lambda x: f"{x['sender_name']}_{x['sender_phone']}" if x['message_direction'] == 'received' 
    else f"{x['recipient_name']}_{x['recipient_phone']}", 
    axis=1
)

# Get the last message direction for each conversation
last_directions = all_messages.sort_values('created_at').groupby('conversation_key')['message_direction'].last().reset_index()

# Group by sender name and phone
grouped_df = received_messages.groupby(['Nome', 'Telefone']).agg({
    'message_uid': 'count',  # Count of messages
    'created_at': 'max',  # Get the latest message date
    'account_name': 'first',  # Get account name
    'ocr_scan': lambda x: x.notna().sum(),  # Count messages with OCR
    'file_url': lambda x: x.notna().sum()  # Count messages with files
}).reset_index()

# Add conversation key to match with last_directions
grouped_df['conversation_key'] = grouped_df.apply(
    lambda x: f"{x['Nome']}_{x['Telefone']}", 
    axis=1
)

# Merge with last_directions to get the last message direction
grouped_df = grouped_df.merge(
    last_directions,
    on='conversation_key',
    how='left'
)

# Drop the conversation_key column
grouped_df = grouped_df.drop('conversation_key', axis=1)

# Rename columns for better understanding
grouped_df = grouped_df.rename(columns={
    'message_uid': 'Total de mensagens recebidas',
    'created_at': 'Última mensagem',
    'account_name': 'Conta',
    'ocr_scan': 'Mensagens com OCR',
    'file_url': 'Mensagens com arquivos',
    'message_direction': 'Última direção'
})

# Sort by latest message timestamp
grouped_df = grouped_df.sort_values('Última mensagem', ascending=False)

# Hide sidebar in inbox page
if st.session_state.current_page == "inbox":
    st.markdown("""
        <style>
        [data-testid="stSidebar"] {
            display: none;
        }
        </style>
        """, unsafe_allow_html=True)

# Add inbox button to sidebar
with st.sidebar:
    if st.button("📥 Caixa de Entrada", use_container_width=True):
        st.session_state.current_page = "inbox"
        st.rerun()

# Add prompts button to sidebar
with st.sidebar:
    if st.button("📝 Gerenciar Prompts", use_container_width=True):
        st.session_state.current_page = "prompts"
        st.rerun()

# Add refresh button to sidebar
with st.sidebar:
    if st.button("🔄 Atualizar Dados", use_container_width=True):
        with st.spinner("Atualizando dados do BigQuery..."):
            # Limpar todos os estados relevantes
            if 'messages_df' in st.session_state:
                del st.session_state.messages_df
            if 'lead_summary' in st.session_state:
                del st.session_state.lead_summary
            if 'grok_chat_history' in st.session_state:
                del st.session_state.grok_chat_history
            if 'message_key' in st.session_state:
                del st.session_state.message_key
            if 'message_length' in st.session_state:
                del st.session_state.message_length
            if 'suggestion' in st.session_state:
                del st.session_state.suggestion
            if 'new_suggestion' in st.session_state:
                del st.session_state.new_suggestion
            
            # Recarregar dados do BigQuery
            st.session_state.messages_df = load_messages()
            st.success("✅ Dados atualizados com sucesso!")
            st.rerun()

# Page content
if st.session_state.current_page == "prompts":
    st.title("📝 Gerenciar Prompts")
    
    # Add tabs for different prompt types
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "🤖 Prompt Geral",
        "💡 Prompt de Sugestão",
        "📄 Prompt de Documentos",
        "⚖️ Prompt de Análise",
        "📊 Prompt de Resumo"
    ])
    
    with tab1:
        st.markdown("### Prompt Geral")
        st.markdown("Este prompt é usado para análise geral das conversas.")
        general_prompt = st.text_area(
            "Prompt Geral",
            value=st.session_state.prompts["general"],
            height=200,
            key="general_prompt"
        )
    
    with tab2:
        st.markdown("### Prompt de Sugestão")
        st.markdown("Este prompt é usado para gerar sugestões de resposta.")
        suggestion_prompt = st.text_area(
            "Prompt de Sugestão",
            value=st.session_state.prompts["suggestion"],
            height=200,
            key="suggestion_prompt"
        )
    
    with tab3:
        st.markdown("### Prompt de Documentos")
        st.markdown("Este prompt é usado para análise de documentos.")
        documents_prompt = st.text_area(
            "Prompt de Documentos",
            value=st.session_state.prompts["documents"],
            height=200,
            key="documents_prompt"
        )
    
    with tab4:
        st.markdown("### Prompt de Análise")
        st.markdown("Este prompt é usado para análise de casos.")
        case_analysis_prompt = st.text_area(
            "Prompt de Análise",
            value=st.session_state.prompts["case_analysis"],
            height=200,
            key="case_analysis_prompt"
        )
    
    with tab5:
        st.markdown("### Prompt de Resumo")
        st.markdown("Este prompt é usado para gerar resumos do status do lead.")
        summary_prompt = st.text_area(
            "Prompt de Resumo",
            value=st.session_state.prompts.get("summary", """Você é um assistente especializado em análise de leads jurídicos. 
Sua função é gerar resumos claros e objetivos do status do lead, focando em informações relevantes para o acompanhamento do caso."""),
            height=200,
            key="summary_prompt"
        )
    
    # Add save button
    if st.button("💾 Salvar Prompts", use_container_width=True):
        try:
            # Update session state
            st.session_state.prompts["general"] = general_prompt
            st.session_state.prompts["suggestion"] = suggestion_prompt
            st.session_state.prompts["documents"] = documents_prompt
            st.session_state.prompts["case_analysis"] = case_analysis_prompt
            st.session_state.prompts["summary"] = summary_prompt
            
            # Update prompts.py file
            prompts_content = f'''SYSTEM_PROMPTS = {{
    "general": """{general_prompt}""",
    "suggestion": """{suggestion_prompt}""",
    "documents": """{documents_prompt}""",
    "case_analysis": """{case_analysis_prompt}""",
    "summary": """{summary_prompt}"""
}}

GENERAL_ANALYSIS_PROMPT = """Analise o histórico de conversas abaixo e responda à pergunta do usuário.

Histórico de Conversas:
{{conversation_text}}

Pergunta do usuário: {{prompt}}

Por favor, forneça uma resposta clara e objetiva."""

SUGGESTION_PROMPT = """Analise o histórico de conversas e a última mensagem do cliente para gerar uma sugestão de resposta.

Histórico de Conversas:
{{conversation_text}}

Última mensagem do cliente: {{last_client_message}}

Por favor, sugira uma resposta profissional e adequada."""

DOCUMENTS_CHECKLIST_PROMPT = """Analise o histórico de conversas para identificar quais documentos foram enviados e quais ainda faltam.

Histórico de Conversas:
{{conversation_text}}

Por favor, liste todos os documentos necessários, indicando quais já foram enviados e quais ainda faltam."""

CASE_ANALYSIS_PROMPT = """Analise o histórico de conversas para avaliar a qualidade do processo e as chances de sucesso.

Histórico de Conversas:
{{conversation_text}}

Por favor, forneça uma análise detalhada incluindo:
1. Pontos fortes do caso
2. Pontos fracos do caso
3. Chances de sucesso
4. Recomendações para melhorar as chances
5. Possíveis riscos"""'''

            with open("prompts.py", "w", encoding="utf-8") as f:
                f.write(prompts_content)
            
            st.success("✅ Prompts salvos com sucesso!")
            
            # Reload prompts module
            import importlib
            import prompts
            importlib.reload(prompts)
            
            # Update SYSTEM_PROMPTS
            SYSTEM_PROMPTS.update(st.session_state.prompts)
            
        except Exception as e:
            st.error(f"❌ Erro ao salvar prompts: {str(e)}")
    
    # Add reset button
    if st.button("🔄 Restaurar Padrão", use_container_width=True):
        try:
            # Reset to default prompts
            st.session_state.prompts = {
                "general": """Você é um assistente especializado em análise de conversas jurídicas. 
Sua função é ajudar a entender o contexto das conversas e fornecer insights relevantes.""",
                "suggestion": """Você é um assistente especializado em sugestões de resposta para atendimento jurídico.
Sua função é gerar sugestões de resposta profissionais e adequadas ao contexto.""",
                "documents": """Você é um assistente especializado em análise de documentos jurídicos.
Sua função é identificar quais documentos foram enviados e quais ainda faltam.""",
                "case_analysis": """Você é um assistente especializado em análise de casos jurídicos.
Sua função é avaliar a qualidade do processo e as chances de sucesso.""",
                "summary": """Você é um assistente especializado em análise de leads jurídicos. 
Sua função é gerar resumos claros e objetivos do status do lead, focando em informações relevantes para o acompanhamento do caso."""
            }
            
            # Update prompts.py file with default values
            prompts_content = f'''SYSTEM_PROMPTS = {{
    "general": """{st.session_state.prompts["general"]}""",
    "suggestion": """{st.session_state.prompts["suggestion"]}""",
    "documents": """{st.session_state.prompts["documents"]}""",
    "case_analysis": """{st.session_state.prompts["case_analysis"]}""",
    "summary": """{st.session_state.prompts["summary"]}"""
}}

GENERAL_ANALYSIS_PROMPT = """Analise o histórico de conversas abaixo e responda à pergunta do usuário.

Histórico de Conversas:
{{conversation_text}}

Pergunta do usuário: {{prompt}}

Por favor, forneça uma resposta clara e objetiva."""

SUGGESTION_PROMPT = """Analise o histórico de conversas e a última mensagem do cliente para gerar uma sugestão de resposta.

Histórico de Conversas:
{{conversation_text}}

Última mensagem do cliente: {{last_client_message}}

Por favor, sugira uma resposta profissional e adequada."""

DOCUMENTS_CHECKLIST_PROMPT = """Analise o histórico de conversas para identificar quais documentos foram enviados e quais ainda faltam.

Histórico de Conversas:
{{conversation_text}}

Por favor, liste todos os documentos necessários, indicando quais já foram enviados e quais ainda faltam."""

CASE_ANALYSIS_PROMPT = """Analise o histórico de conversas para avaliar a qualidade do processo e as chances de sucesso.

Histórico de Conversas:
{{conversation_text}}

Por favor, forneça uma análise detalhada incluindo:
1. Pontos fortes do caso
2. Pontos fracos do caso
3. Chances de sucesso
4. Recomendações para melhorar as chances
5. Possíveis riscos"""'''

            with open("prompts.py", "w", encoding="utf-8") as f:
                f.write(prompts_content)
            
            st.success("✅ Prompts restaurados para os valores padrão!")
            
            # Reload prompts module
            import importlib
            import prompts
            importlib.reload(prompts)
            
            # Update SYSTEM_PROMPTS
            SYSTEM_PROMPTS.update(st.session_state.prompts)
            
        except Exception as e:
            st.error(f"❌ Erro ao restaurar prompts: {str(e)}")

elif st.session_state.current_page == "inbox":
    st.title("📥 Rosenbaum Advogados AI")
    
    # Add metrics dashboard
    st.markdown("""
        <style>
        .metrics-container {
            display: flex;
            gap: 1rem;
            margin-bottom: 1.5rem;
        }
        .metric-card {
            background: white;
            border-radius: 0.8rem;
            padding: 1.2rem;
            flex: 1;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
            border: 1px solid #e0e0e0;
            text-align: center;
        }
        .metric-card.today {
            background: linear-gradient(135deg, #f0f9ff 0%, #ffffff 100%);
            border: 1px solid #90cdf4;
        }
        .metric-title {
            font-size: 0.9em;
            color: #666;
            margin-bottom: 0.5rem;
        }
        .metric-value {
            font-size: 1.8em;
            font-weight: bold;
            color: #2c3e50;
            margin-bottom: 0.3rem;
        }
        .metric-subtitle {
            font-size: 0.8em;
            color: #666;
        }
        .section-divider {
            margin: 2.5rem 0;
            text-align: left;
            position: relative;
            padding: 0;
        }
        .section-divider h2 {
            font-size: 1.2em;
            color: #2c3e50;
            margin-bottom: 1rem;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }
        .section-divider::after {
            content: "";
            display: block;
            height: 2px;
            background: linear-gradient(90deg, #e0e0e0 0%, transparent 100%);
            margin-top: 0.5rem;
        }
        </style>
    """, unsafe_allow_html=True)
    
    # Calculate metrics
    total_conversations = len(grouped_df)
    total_messages = grouped_df['Total de mensagens recebidas'].sum()
    total_files = grouped_df['Mensagens com arquivos'].sum()
    total_images = grouped_df['Mensagens com OCR'].sum()
    total_audios = len(df[df['audio_transcription'].notna()])
    
    # Get today's date for comparison
    today = pd.Timestamp.now(tz='America/Sao_Paulo').date()
    
    # Calculate today's metrics
    today_df = df[df['created_at'].dt.date == today]
    messages_today = len(today_df[today_df['message_direction'] == 'received'])
    files_today = len(today_df[today_df['file_url'].notna()])
    images_today = len(today_df[today_df['ocr_scan'].notna()])
    audios_today = len(today_df[today_df['audio_transcription'].notna()])
    
    # Calculate conversations from today
    conversations_today = len(grouped_df[grouped_df['Última mensagem'].dt.date == today])
    
    # Calculate average response time for all messages
    avg_response_time = calculate_average_response_time(df)
    avg_response_time_str = f"{int(avg_response_time)} segundos" if avg_response_time is not None else "Sem dados"
    
    # Calculate average response time for today's messages
    avg_response_time_today = calculate_average_response_time(today_df)
    avg_response_time_today_str = f"{int(avg_response_time_today)} segundos" if avg_response_time_today is not None else "Sem dados"
    
    st.markdown(f"""
        <div class="metrics-container">
            <div class="metric-card">
                <div class="metric-title">Total de Conversas</div>
                <div class="metric-value">{total_conversations}</div>
                <div class="metric-subtitle">💬 {conversations_today} hoje</div>
            </div>
            <div class="metric-card">
                <div class="metric-title">Total de Mensagens</div>
                <div class="metric-value">{total_messages}</div>
                <div class="metric-subtitle">📝 {messages_today} hoje</div>
            </div>
            <div class="metric-card">
                <div class="metric-title">Arquivos Enviados</div>
                <div class="metric-value">{total_files}</div>
                <div class="metric-subtitle">📎 {files_today} hoje</div>
            </div>
            <div class="metric-card">
                <div class="metric-title">Imagens Processadas</div>
                <div class="metric-value">{total_images}</div>
                <div class="metric-subtitle">📸 {images_today} hoje</div>
            </div>
            <div class="metric-card">
                <div class="metric-title">Áudios Processados</div>
                <div class="metric-value">{total_audios}</div>
                <div class="metric-subtitle">🎤 {audios_today} hoje</div>
            </div>
            <div class="metric-card">
                <div class="metric-title">Tempo Médio de Resposta</div>
                <div class="metric-value">{int(avg_response_time) if avg_response_time is not None else '⏱️'}</div>
                <div class="metric-subtitle">⏱️ {int(avg_response_time_today) if avg_response_time_today is not None else 0} segundos hoje</div>
            </div>
        </div>
    """, unsafe_allow_html=True)
    
    # Create a container for filters with a light background
    with st.container():
        st.markdown('<div class="section-divider"><h2>🔍 Filtros e Pesquisa</h2></div>', unsafe_allow_html=True)
        st.markdown("""
            <style>
            .filter-container {
                background-color: #f0f2f6;
                padding: 1.5rem;
                border-radius: 0.8rem;
                margin-bottom: 1.5rem;
                box-shadow: 0 2px 4px rgba(0,0,0,0.05);
            }
            .conversation-card {
                background: white;
                border-radius: 0.8rem;
                padding: 1rem;
                margin-bottom: 1rem;
                box-shadow: 0 2px 4px rgba(0,0,0,0.05);
                border: 1px solid #e0e0e0;
                transition: all 0.3s ease;
            }
            .conversation-card:hover {
                transform: translateY(-2px);
                box-shadow: 0 4px 8px rgba(0,0,0,0.1);
            }
            .conversation-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 0.5rem;
            }
            .conversation-name {
                font-size: 1.1em;
                font-weight: bold;
                color: #2c3e50;
            }
            .conversation-stats {
                display: flex;
                gap: 1rem;
                color: #666;
                font-size: 0.9em;
            }
            .conversation-time {
                color: #666;
                font-size: 0.85em;
            }
            </style>
            """, unsafe_allow_html=True)
        
        # Add search boxes in columns
        col1, col2 = st.columns(2)
        with col1:
            search_phone = st.text_input("📱 Buscar por telefone:", placeholder="Digite o número...")
        with col2:
            search_name = st.text_input("👤 Buscar por nome:", placeholder="Digite o nome...")
        
        # Add Monday lead filter
        monday_filter = st.selectbox(
            "📊 Encontrado no Monday:",
            ["Todos", "Sim", "Não"],
            index=0
        )
        
        # Add date filter with better formatting
        min_date = grouped_df['Última mensagem'].min().date()
        max_date = grouped_df['Última mensagem'].max().date()
        date_range = st.date_input(
            "📅 Período:",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date
        )
    
    # Filter conversations based on search and date
    filtered_df = grouped_df
    if search_phone or search_name:
        if search_phone:
            filtered_df = filtered_df[filtered_df['Telefone'].str.contains(search_phone, case=False, na=False)]
        if search_name:
            filtered_df = filtered_df[filtered_df['Nome'].str.contains(search_name, case=False, na=False)]
    
    # Apply Monday lead filter
    if monday_filter != "Todos" and 'monday_link' in df.columns:
        # Get all conversations with their Monday status
        monday_status = df.groupby(['sender_name', 'sender_phone'])['monday_link'].first().reset_index()
        monday_status['has_monday_lead'] = monday_status['monday_link'].notna()
        
        # Merge with filtered_df
        filtered_df = filtered_df.merge(
            monday_status[['sender_name', 'sender_phone', 'has_monday_lead']],
            left_on=['Nome', 'Telefone'],
            right_on=['sender_name', 'sender_phone']
        )
        
        # Apply filter based on selection
        if monday_filter == "Sim":
            filtered_df = filtered_df[filtered_df['has_monday_lead']]
        else:  # "Não"
            filtered_df = filtered_df[~filtered_df['has_monday_lead']]
    elif monday_filter != "Todos":
        st.warning("⚠️ A coluna 'monday_link' não está disponível nos dados atuais.")
        filtered_df = pd.DataFrame()  # Retorna um DataFrame vazio para não mostrar resultados
    
    # Apply date filter
    if len(date_range) == 2:
        start_date, end_date = date_range
        filtered_df = filtered_df[
            (filtered_df['Última mensagem'].dt.date >= start_date) &
            (filtered_df['Última mensagem'].dt.date <= end_date)
        ]
    
    # Show number of results with better formatting
    st.markdown(f"""
        <div style='
            background-color: #e8f4f9;
            padding: 1rem;
            border-radius: 0.5rem;
            margin-bottom: 1rem;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        '>
            <span style='font-size: 1.2em;'>📊</span>
            <span style='font-weight: bold;'>{len(filtered_df)} conversas encontradas</span>
        </div>
    """, unsafe_allow_html=True)
    
    # Create a container for the conversation list
    for _, row in filtered_df.head(st.session_state.display_count).iterrows():
        # Determinar o ícone baseado na direção da última mensagem
        last_message_icon = "👤" if row['Última direção'] == 'received' else "💬"
        
        st.markdown(f"""
            <div class='conversation-card'>
                <div class='conversation-header'>
                    <div class='conversation-name'>
                        {last_message_icon} {row['Nome']} • 📱 {row['Telefone']}
                    </div>
                    <div class='conversation-time'>
                        ⏰ {row['Última mensagem'].strftime('%d/%m/%Y %H:%M')}
                    </div>
                </div>
                <div class='conversation-stats'>
                    <span>💬 {row['Total de mensagens recebidas']} mensagens</span>
                    <span>📸 {row['Mensagens com OCR']} imagens</span>
                    <span>📎 {row['Mensagens com arquivos']} arquivos</span>
                </div>
            </div>
        """, unsafe_allow_html=True)
        
        # Add chat button
        if st.button("💬 Abrir Chat", key=f"btn_{row['Nome']}_{row['Telefone']}", use_container_width=True):
            st.session_state.selected_sender = f"{row['Nome']} ({row['Telefone']})"
            st.session_state.current_page = "chat"
            st.rerun()

    # Add "Load more" button with better styling
    if len(filtered_df) > st.session_state.display_count:
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if st.button("📥 Carregar mais conversas", key="load_more", use_container_width=True):
                st.session_state.display_count += 20
                st.rerun()

elif st.session_state.current_page == "chat":
    # Create a dictionary mapping display names to actual values
    sender_dict = {
        f"{row['Nome']} ({row['Telefone']})": {
            'name': row['Nome'],
            'phone': row['Telefone']
        } for _, row in grouped_df.iterrows()
    }

    # Header with contact selection
    st.markdown("### 💬 Chat")
    selected_sender = st.selectbox(
        "Selecione um contato para visualizar a conversa:", 
        list(sender_dict.keys()),
        key="chat_sender_select",
        index=list(sender_dict.keys()).index(st.session_state.get('selected_sender', list(sender_dict.keys())[0])) if 'selected_sender' in st.session_state else 0
    )

    # Limpar histórico quando trocar de cliente no selectbox
    if 'previous_sender' not in st.session_state:
        st.session_state.previous_sender = selected_sender
    elif st.session_state.previous_sender != selected_sender:
        st.session_state.grok_chat_history = []
        st.session_state.lead_summary = None  # Reset lead summary when changing leads
        st.session_state.previous_sender = selected_sender

    if selected_sender:
        selected_info = sender_dict[selected_sender]
        selected_name = selected_info['name']
        selected_phone = selected_info['phone']
        
        # Add client name to sidebar
        with st.sidebar:
            st.markdown("""
                <style>
                .sidebar-container {
                    padding: 1rem;
                }
                .client-card {
                    background: white;
                    border-radius: 0.8rem;
                    padding: 1rem;
                    margin-bottom: 1rem;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.05);
                    border: 1px solid #e0e0e0;
                    transition: all 0.3s ease;
                }
                .client-card:hover {
                    transform: translateY(-2px);
                    box-shadow: 0 4px 8px rgba(0,0,0,0.1);
                }
                .client-card.active {
                    background: linear-gradient(135deg, #e6f3ff 0%, #ffffff 100%);
                    border: 2px solid #1f77b4;
                    box-shadow: 0 4px 12px rgba(31, 119, 180, 0.15);
                }
                .client-name {
                    font-size: 1.1em;
                    font-weight: bold;
                    color: #2c3e50;
                    margin-bottom: 0.5rem;
                    display: flex;
                    align-items: center;
                    gap: 0.5rem;
                }
                .client-info {
                    display: flex;
                    align-items: center;
                    gap: 0.5rem;
                    margin: 0.3rem 0;
                    font-size: 0.9em;
                    color: #666;
                }
                .client-stats {
                    display: grid;
                    grid-template-columns: repeat(2, 1fr);
                    gap: 0.5rem;
                    margin-top: 0.8rem;
                    padding-top: 0.8rem;
                    border-top: 1px solid #e0e0e0;
                    font-size: 0.85em;
                    color: #666;
                }
                .stat-item {
                    display: flex;
                    align-items: center;
                    gap: 0.3rem;
                }
                .view-all-button {
                    background: linear-gradient(135deg, #1f77b4 0%, #2c3e50 100%);
                    color: white;
                    border: none;
                    border-radius: 0.5rem;
                    padding: 0.8rem;
                    width: 100%;
                    font-weight: bold;
                    margin-top: 1rem;
                    transition: all 0.3s ease;
                }
                .view-all-button:hover {
                    transform: translateY(-2px);
                    box-shadow: 0 4px 8px rgba(0,0,0,0.2);
                }
                </style>
                """, unsafe_allow_html=True)
            
            # Show recent clients (last 10)
            for _, row in grouped_df.head(10).iterrows():
                client_name = row['Nome']
                client_phone = row['Telefone']
                client_key = f"{client_name} ({client_phone})"
                
                # Create client card
                card_class = "client-card active" if client_key == selected_sender else "client-card"
                
                st.markdown(f"""
                    <div class="{card_class}">
                        <div class="client-name">
                            {'💬' if client_key == selected_sender else '👤'} {client_name}
                        </div>
                        <div class="client-info">📱 {client_phone}</div>
                        <div class="client-stats">
                            <div class="stat-item">💬 {row['Total de mensagens recebidas']}</div>
                            <div class="stat-item">📸 {row['Mensagens com OCR']}</div>
                            <div class="stat-item">📎 {row['Mensagens com arquivos']}</div>
                            <div class="stat-item">⏰ {row['Última mensagem'].strftime('%d/%m %H:%M')}</div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                
                # Add click handler for non-active clients
                if client_key != selected_sender:
                    if st.button("Selecionar", key=f"btn_{client_key}", use_container_width=True):
                        st.session_state.selected_sender = client_key
                        st.session_state.grok_chat_history = []  # Limpar histórico ao trocar de cliente
                        st.session_state.lead_summary = None  # Reset lead summary when changing leads
                        st.rerun()
            
            # View all button
            if st.button("📥 Ver todos os clientes", use_container_width=True):
                st.session_state.current_page = "inbox"
                st.rerun()
        
        # Filter messages for selected sender - include both sent and received messages
        sender_messages = df[
            ((df['sender_name'].fillna('') == selected_name) & (df['sender_phone'].fillna('') == selected_phone)) |  # messages from sender
            ((df['recipient_name'].fillna('') == selected_name) & (df['recipient_phone'].fillna('') == selected_phone))  # messages to sender
        ].sort_values('created_at', ascending=False)  # Changed to descending order
        
        if not sender_messages.empty:
            # Show chat details in columns
            chat_info = sender_messages.iloc[0]
            
            # Display client name as a title
            st.title(f"💬 {selected_name}")
            
            # Add header container with darker background
            st.markdown("""
                <style>
                .header-container {
                    background-color: #f8f9fa;
                    padding: 1.5rem;
                    border-radius: 0.8rem;
                    margin-bottom: 1.5rem;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.05);
                    border: 1px solid #e0e0e0;
                }
                .section-title {
                    color: #2c3e50;
                    font-size: 1.2em;
                    font-weight: 600;
                    margin-bottom: 3.5rem;
                    margin-top: 6rem;
                    padding-bottom: 1.5rem;
                    border-bottom: 2px solid #e0e0e0;
                }
                .section-title:first-of-type {
                    margin-top: 0;
                }
                .lead-summary-container {
                    background: linear-gradient(135deg, #f8f9fa 0%, #ffffff 100%);
                    border: 1px solid #e0e0e0;
                    border-radius: 0.8rem;
                    padding: 1.5rem;
                    margin: 1rem 0;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.05);
                }
                .lead-summary-header {
                    display: flex;
                    align-items: center;
                    gap: 0.5rem;
                    color: #2c3e50;
                    font-weight: 600;
                    cursor: pointer;
                    padding: 0.5rem;
                    border-radius: 0.5rem;
                    transition: all 0.3s ease;
                }
                .lead-summary-header:hover {
                    background-color: #f0f2f6;
                }
                </style>
            """, unsafe_allow_html=True)
            
            # Add Monday data section
            st.markdown('<div class="section-title">📊 Dados do Monday</div>', unsafe_allow_html=True)
            monday_col1, monday_col2, monday_col3 = st.columns(3)
            
            with monday_col1:
                st.markdown(f"**Nome:** {chat_info.get('name', 'N/A')}")
                st.markdown(f"**Título:** {chat_info.get('title', 'N/A')}")
                monday_id = chat_info.get('id')
                if monday_id and pd.notna(monday_id):  # Check if monday_id exists and is not NaN
                    try:
                        monday_id = str(int(float(monday_id)))
                    except (ValueError, TypeError):
                        monday_id = 'N/A'
                else:
                    monday_id = 'N/A'
                st.markdown(f"**ID:** {monday_id}")
                st.markdown(f"**Quadro:** {chat_info.get('board', 'N/A')}")
                st.markdown(f"**Email:** {chat_info.get('email', 'N/A')}")
            
            with monday_col2:
                st.markdown(f"**Telefone:** {chat_info.get('phone', 'N/A')}")
                st.markdown(f"**Status:** {chat_info.get('status', 'N/A')}")
                st.markdown(f"**Origem:** {chat_info.get('origem', 'N/A')}")
            
            with monday_col3:
                st.markdown(f"**Prioridade:** {chat_info.get('prioridade', 'N/A')}")
                if chat_info.get('monday_link'):
                    st.markdown(f"""
                        <a href="{chat_info['monday_link']}" target="_blank" style="
                            display: inline-block;
                            background-color: #0073ea;
                            color: white;
                            padding: 0.5rem 1rem;
                            border-radius: 0.5rem;
                            text-decoration: none;
                            font-weight: 500;
                            transition: all 0.3s ease;
                        ">🔗 Abrir no Monday</a>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown("**Link do Monday:** N/A")
            
            # Add Monday updates section
            if monday_id != 'N/A':
                try:
                    updates = fetch_monday_updates([monday_id])
                    if updates and len(updates) > 0 and updates[0].get('updates'):
                        # Sort updates by date (newest first)
                        sorted_updates = sorted(updates[0]['updates'], 
                                              key=lambda x: x.get('created_at', ''), 
                                              reverse=True)
                        
                        # Use Streamlit expander instead of custom HTML
                        with st.expander("📝 Atualizações do Monday", expanded=False):
                            for update in sorted_updates:
                                created_at = update.get('created_at', 'N/A')
                                body = update.get('body', 'N/A')
                                
                                # Safely get creator name, handling None case
                                is_system = not update.get('creator')
                                creator_name = "🤖 Atualização do Sistema" if is_system else update['creator'].get('name', 'Usuário desconhecido')
                                creator_icon = "⚙️" if is_system else "👤"
                                
                                # Adjust time to Brasília timezone (UTC-3)
                                try:
                                    if created_at != 'N/A':
                                        # Parse the ISO format date
                                        from datetime import datetime
                                        import pytz
                                        
                                        # Parse the date string to datetime object
                                        dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                                        
                                        # Convert to Brasília timezone
                                        brasilia_tz = pytz.timezone('America/Sao_Paulo')
                                        dt_brasilia = dt.astimezone(brasilia_tz)
                                        
                                        # Format the date in a more readable way
                                        formatted_date = dt_brasilia.strftime('%d/%m/%Y %H:%M:%S')
                                        created_at = formatted_date
                                except Exception as e:
                                    # If there's any error in date conversion, keep the original
                                    pass
                                
                                # Display author and date with different styling for system updates
                                st.markdown(f"""
                                    <div style='
                                        background-color: {'#f0f4f8' if is_system else '#f8f9fa'};
                                        padding: 8px 12px;
                                        border-radius: 6px;
                                        margin-bottom: 8px;
                                        display: flex;
                                        align-items: center;
                                        gap: 8px;
                                    '>
                                        <span style='
                                            font-weight: 500;
                                            color: {'#4a5568' if is_system else '#2d3748'};
                                        '>{creator_name}</span>
                                        <span style='color: #666;'>•</span>
                                        <span style='color: #666;'>📅 {created_at}</span>
                                    </div>
                                """, unsafe_allow_html=True)
                                
                                # Render the body content as HTML
                                st.markdown(body, unsafe_allow_html=True)
                                st.divider()
                except Exception as e:
                    st.warning(f"Não foi possível buscar atualizações do Monday: {str(e)}")
            
            # Add lead summary section
            st.markdown('<div class="section-title">📊 Resumo do Lead</div>', unsafe_allow_html=True)
            
            # Initialize lead summary in session state if not exists
            if 'lead_summary' not in st.session_state:
                st.session_state.lead_summary = None
            
            # Generate lead summary if not exists
            if st.session_state.lead_summary is None:
                with st.spinner("Gerando resumo do lead..."):
                    monday_info = {
                        'item_id': monday_id,
                        'name': chat_info.get('name', 'N/A'),
                        'title': chat_info.get('title', 'N/A'),
                        'status': chat_info.get('status', 'N/A'),
                        'prioridade': chat_info.get('prioridade', 'N/A'),
                        'origem': chat_info.get('origem', 'N/A'),
                        'email': chat_info.get('email', 'N/A')
                    }
                    st.session_state.lead_summary = generate_lead_status_summary(sender_messages, monday_info)
            
            # Display lead summary in an expander
            if st.session_state.lead_summary:
                with st.expander("📊 Resumo do Lead", expanded=True):
                    st.markdown(f"""
                        <div class="lead-summary-container">
                            {st.session_state.lead_summary}
                        </div>
                    """, unsafe_allow_html=True)
            else:
                st.error("Não foi possível gerar o resumo do lead. Tente novamente.")
            
            # Add AI buttons
            st.markdown('<div class="section-title">🤖 Ferramentas de IA</div>', unsafe_allow_html=True)
            col1, col2 = st.columns(2)
            with col1:
                if st.button("📄 Checklist de Documentos", use_container_width=True):
                    with st.spinner("Analisando documentos..."):
                        docs_checklist = generate_missing_documents(sender_messages)
                        if docs_checklist:
                            st.session_state.grok_chat_history.append({
                                "role": "assistant", 
                                "content": f"""**📄 Checklist de Documentos para o Processo**

Legenda:
✅ - Documento já enviado (com link para visualização)
❌ - Documento faltando
⚠️ - Documento parcialmente enviado/incompleto

{docs_checklist}

Deseja que eu prepare uma mensagem solicitando os documentos faltantes?"""
                            })
                            st.rerun()
                        else:
                            st.error("Não foi possível gerar a checklist de documentos. Tente novamente.")
            
            with col2:
                if st.button("⚖️ Analisar Qualidade do Processo", use_container_width=True):
                    with st.spinner("Analisando chances de sucesso..."):
                        case_analysis = generate_case_analysis(sender_messages)
                        if case_analysis:
                            st.session_state.grok_chat_history.append({
                                "role": "assistant", 
                                "content": f"""**⚖️ Análise do Processo**
{case_analysis}"""
                            })
                            st.rerun()
                        else:
                            st.error("Não foi possível gerar a análise do caso. Tente novamente.")
            
            # Add Timelines data section
            st.markdown('<div class="section-title">📋 Dados do Timelines</div>', unsafe_allow_html=True)
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.markdown(f"**Nome:** {chat_info['chat_full_name']}")
                st.markdown(f"**Telefone:** {selected_phone}")
            
            with col2:
                st.markdown(f"**Nome:** {chat_info['responsible_name']}")
                st.markdown(f"**Conta:** {chat_info['account_name']}")
            
            with col3:
                if chat_info.get('chat_url'):
                    st.markdown(f"""
                        <a href="{chat_info['chat_url']}" target="_blank" style="
                            display: inline-block;
                            background-color: #25D366;
                            color: white;
                            padding: 0.5rem 1rem;
                            border-radius: 0.5rem;
                            text-decoration: none;
                            font-weight: 500;
                            transition: all 0.3s ease;
                        ">💬 Abrir no WhatsApp</a>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown("**WhatsApp:** N/A")
            
            # List all image files at the top
            image_files = sender_messages[sender_messages['file_url'].notna()].copy()
            if not image_files.empty:
                st.markdown("### 📸 Arquivos de Imagem")
            
            # Display messages with better formatting
            st.markdown("### Histórico de mensagens")
            
            # Sort messages in ascending order (oldest first)
            sorted_messages = sender_messages.sort_values('created_at', ascending=True)
            
            # Calcular tempos de resposta
            response_times = calculate_response_time(sorted_messages)
            
            # Initialize message display limit in session state if not exists
            if 'message_display_limit' not in st.session_state:
                st.session_state.message_display_limit = 10
            
            # Add buttons for loading messages
            col1, col2 = st.columns(2)
            with col1:
                if len(sorted_messages) > st.session_state.message_display_limit:
                    if st.button("📥 Ver mensagens mais antigas", use_container_width=True):
                        st.session_state.message_display_limit += 10
                        st.rerun()
            with col2:
                if len(sorted_messages) > st.session_state.message_display_limit:
                    if st.button("📚 Carregar todo o histórico", use_container_width=True):
                        st.session_state.message_display_limit = len(sorted_messages)
                        st.rerun()
            
            # Get messages to display
            messages_to_display = sorted_messages.tail(st.session_state.message_display_limit)
            
            # Iterate through messages and display them as chat messages
            current_date = None
            for _, msg in messages_to_display.iterrows():
                # Check if date has changed
                message_date = msg['created_at'].strftime('%d/%m/%Y')
                if current_date != message_date:
                    current_date = message_date
                    st.markdown(f"""
                        <div style='
                            text-align: center;
                            margin: 1rem 0;
                            padding: 0.5rem;
                            background-color: #f0f2f6;
                            border-radius: 0.5rem;
                            color: #666;
                            font-weight: 500;
                        '>
                            📅 {current_date}
                        </div>
                    """, unsafe_allow_html=True)
                
                # Determine message role
                role = "user" if msg['message_direction'] == 'received' else "assistant"
                
                # Format message content
                content = msg['message_text'] or ''
                
                # Add file information if present
                if msg['file_url'] and pd.notna(msg['file_url']):
                    content += f"\n📎 [Abrir arquivo]({msg['file_url']})"
                
                # Add OCR information if present
                if msg['ocr_scan'] and pd.notna(msg['ocr_scan']):
                    content += f"\n🔍 OCR: {msg['ocr_scan']}"
                
                # Add attachment filename if present and valid
                if msg['attachment_filename'] and pd.notna(msg['attachment_filename']):
                    content += f"\n📎 Anexo: {msg['attachment_filename']}"
                
                # Add audio transcription if present
                if msg['audio_transcription'] and pd.notna(msg['audio_transcription']):
                    content += f"\n🎤 Transcrição: {msg['audio_transcription']}"
                
                # Display chat message
                with st.chat_message(role):
                    timestamp = msg['created_at'].strftime('%H:%M')
                    if msg['message_direction'] == 'received':
                        if msg['message_uid'] in response_times:
                            response_time = format_response_time(response_times[msg['message_uid']])
                            st.write(f"**{timestamp}** (⏱️ Tempo de resposta: {response_time})")
                        else:
                            st.write(f"**{timestamp}** (⏱️ Aguardando resposta)")
                    else:
                        st.write(f"**{timestamp}**")
                    st.write(content)

            # Add clear chat button below the chat history
            if st.button("🗑️ Limpar Chat", use_container_width=True):
                st.session_state.grok_chat_history = []
                st.rerun()

            # Display AI chat history
            for message in st.session_state.grok_chat_history:
                with st.chat_message(message["role"]):
                    st.write(message["content"])

            # Add suggestion button after chat history
            if st.button("💡 Sugerir Resposta", use_container_width=True):
                with st.spinner("Gerando sugestão de resposta..."):
                    suggestion = generate_suggestion(sender_messages)
                    if suggestion:
                        st.session_state.grok_chat_history.append({
                            "role": "assistant", 
                            "content": f"""**💡 Sugestão de Resposta**

{suggestion}

Deseja que eu envie esta mensagem?"""
                        })
                        st.rerun()
                    else:
                        st.error("Não foi possível gerar uma sugestão de resposta. Tente novamente.")

            # Chat input for AI bot
            if prompt := st.chat_input("💬 Como posso ajudar? Digite sua pergunta..."):
                # Add user message to chat history
                st.session_state.grok_chat_history.append({"role": "user", "content": prompt})
                
                # Display user message
                with st.chat_message("user"):
                    st.write(prompt)
                
                # Generate and display assistant response
                with st.chat_message("assistant"):
                    with st.spinner("Pensando..."):
                        response = generate_grok_response(sender_messages, prompt)
                        if response:
                            st.write(response)
                            st.session_state.grok_chat_history.append({"role": "assistant", "content": response})
                        else:
                            st.error("Não foi possível gerar uma resposta. Tente novamente.")

            # Add WhatsApp message section
            st.markdown("### 💬 Enviar Mensagem")
            message = st.text_area("Digite sua mensagem:", height=100)
            col1, col2 = st.columns(2)
            with col1:
                if st.button("📤 Enviar Mensagem", use_container_width=True):
                    if message:
                        success, result = send_whatsapp_message(selected_phone, message)
                        if success:
                            st.success(result)
                            # Add message to history
                            st.session_state.messages_df = add_message_to_history(
                                st.session_state.messages_df,
                                "Rosenbaum Advogados",
                                "+5511988094449",
                                selected_name,
                                selected_phone,
                                message
                            )
                            st.rerun()
                        else:
                            st.error(result)
                    else:
                        st.error("Por favor, digite uma mensagem para enviar.")
            with col2:
                if st.button("📤 Enviar Mensagem (Modo Teste)", use_container_width=True):
                    if message:
                        success, result = send_whatsapp_message(selected_phone, message, test_mode=True, test_phone="+5511999999999")
                        if success:
                            st.success(result)
                        else:
                            st.error(result)
                    else:
                        st.error("Por favor, digite uma mensagem para enviar.")