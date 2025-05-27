import streamlit as st
import pandas as pd
from google.cloud import bigquery
from google.oauth2 import service_account
from datetime import datetime, timedelta
import pytz
import os
from monday_api import fetch_monday_updates
import httpx
import re
import urllib3
import json

# Set page config
st.set_page_config(
    page_title="Rosenbaum CRM",
    page_icon="📅",
    layout="wide"
)

def strip_html_tags(text):
    """Remove all HTML tags from text and fix R$ formatting."""
    if not text:
        return ""
    # Remove HTML tags
    clean = re.compile('<.*?>')
    text = re.sub(clean, '', text)
    
    # Fix R$ formatting
    text = re.sub(r'R\s*(\d+)', r'R$ \1', text)  # Fix R followed by numbers
    text = re.sub(r'R\$\s*(\d+)', r'R$ \1', text)  # Fix R$ followed by numbers
    text = re.sub(r'R\$\s*(\d+)\s*mil', r'R$ \1 mil', text)  # Fix R$ followed by numbers and "mil"
    
    return text

def calculate_response_time(messages_df):
    """Calculate response times between messages."""
    response_times = {}
    last_received_time = None
    last_received_idx = None
    
    # Ensure created_at is datetime
    messages_df['created_at'] = pd.to_datetime(messages_df['created_at'])
    
    for idx, msg in messages_df.iterrows():
        if msg['message_direction'] == 'received':
            last_received_time = msg['created_at']
            last_received_idx = idx
        elif msg['message_direction'] == 'sent' and last_received_time is not None:
            response_time = msg['created_at'] - last_received_time
            response_times[idx] = response_time
            last_received_time = None
            last_received_idx = None
    
    return response_times

def format_response_time(timedelta):
    """Format timedelta into a human-readable string."""
    total_seconds = int(timedelta.total_seconds())
    
    if total_seconds < 60:
        return f"{total_seconds} segundos"
    elif total_seconds < 3600:
        minutes = total_seconds // 60
        return f"{minutes} minutos"
    elif total_seconds < 86400:
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        return f"{hours}h {minutes}min"
    else:
        days = total_seconds // 86400
        hours = (total_seconds % 86400) // 3600
        return f"{days}d {hours}h"

# Initialize BigQuery client with service account credentials
credentials = service_account.Credentials.from_service_account_info(
    st.secrets["gcp_service_account"]
)
client = bigquery.Client(credentials=credentials, project="zapy-306602")

# Read SQL query from file
def read_sql_file(file_path):
    with open(file_path, 'r') as file:
        return file.read()

# Get the directory of the current file
current_dir = os.path.dirname(os.path.abspath(__file__))
sql_file_path = os.path.join(current_dir, 'queries', 'monday_sessions.sql')
messages_sql_path = os.path.join(current_dir, 'queries', 'lead_messages.sql')

def generate_lead_status_summary(messages, monday_info):
    """Gera um resumo do status do lead usando IA."""
    # Sort messages in ascending order (oldest first)
    messages = messages.sort_values('created_at', ascending=True)
    
    # Prepare the conversation text
    conversation = []
    for _, msg in messages.iterrows():
        role = "Cliente" if msg['message_direction'] == 'received' else "Atendente"
        content = msg['message_text'] or ''
        
        # Add file information if present
        if 'file_url' in msg and pd.notna(msg['file_url']):
            content += f"\n📎 [Anexo: {msg.get('attachment_filename', 'Arquivo')}]({msg['file_url']})"
        
        # Add attachment URL if present
        if 'attachment_url' in msg and pd.notna(msg['attachment_url']):
            content += f"\n📎 [Anexo: {msg.get('attachment_filename', 'Arquivo')}]({msg['attachment_url']})"
        
        # Add OCR information if present
        if 'ocr_scan' in msg and pd.notna(msg['ocr_scan']):
            content += f"\n🔍 OCR: {msg['ocr_scan']}"
        
        # Add audio transcription if present
        if 'audio_transcription' in msg and pd.notna(msg['audio_transcription']):
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
    prompt = f"""Analise o histórico de conversas e os dados do Monday para gerar um resumo claro e objetivo do status do lead.

Histórico de Conversas:
{conversation_text}

{monday_text}

Por favor, forneça um resumo que inclua:
1. Situação atual do lead
2. Principais pontos discutidos
3. Próximos passos recomendados
4. Documentos pendentes (se houver)
5. Observações importantes

O resumo deve ser conciso e focado em informações relevantes para o acompanhamento do caso."""
    
    # Call Grok API
    url = "https://api.x.ai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {st.secrets.grok.api_key}",
        "Content-Type": "application/json"
    }
    
    # Use custom prompt from session state if available
    system_prompt = st.session_state.get('summary_prompt', """Você é um assistente especializado em análise de leads jurídicos. 
Sua função é gerar resumos claros e objetivos do status do lead, focando em informações relevantes para o acompanhamento do caso.""")
    
    data = {
        "model": "grok-3-latest",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7,
        "stream": False
    }
    
    try:
        with httpx.Client(verify=True, timeout=60.0) as client:
            response = client.post(url, headers=headers, json=data)
            response.raise_for_status()
            result = response.json()
            return result['choices'][0]['message']['content']
    except Exception as e:
        st.error(f"Erro ao gerar resumo do lead: {str(e)}")
        return None

def generate_suggestion(messages):
    """Gera uma sugestão de resposta baseada no histórico de mensagens."""
    # Sort messages in ascending order (oldest first)
    messages = messages.sort_values('created_at', ascending=True)
    
    # Get the last message from the client
    last_client_message = messages[messages['message_direction'] == 'received'].iloc[-1]
    
    # Prepare the conversation text
    conversation = []
    for _, msg in messages.iterrows():
        role = "Cliente" if msg['message_direction'] == 'received' else "Atendente"
        content = msg['message_text'] or ''
        
        # Add file information if present
        if 'file_url' in msg and pd.notna(msg['file_url']):
            content += f"\n[Anexo: {msg.get('attachment_filename', 'Arquivo')}]({msg['file_url']})"
        
        # Add attachment URL if present
        if 'attachment_url' in msg and pd.notna(msg['attachment_url']):
            content += f"\n[Anexo: {msg.get('attachment_filename', 'Arquivo')}]({msg['attachment_url']})"
        
        # Add OCR information if present
        if 'ocr_scan' in msg and pd.notna(msg['ocr_scan']):
            content += f"\nOCR: {msg['ocr_scan']}"
        
        # Add audio transcription if present
        if 'audio_transcription' in msg and pd.notna(msg['audio_transcription']):
            content += f"\nTranscrição: {msg['audio_transcription']}"
        
        conversation.append(f"{role}: {content}")
    
    conversation_text = "\n".join(conversation)
    
    # Prepare the prompt for suggestion
    prompt = f"""Analise o histórico de conversas e a última mensagem do cliente para gerar uma sugestão de resposta.

Histórico de Conversas:
{conversation_text}

Última mensagem do cliente: {last_client_message['message_text']}

Por favor, sugira uma resposta profissional e adequada."""
    
    # Call Grok API
    url = "https://api.x.ai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {st.secrets.grok.api_key}",
        "Content-Type": "application/json"
    }
    
    # Use custom prompt from session state if available
    system_prompt = st.session_state.get('suggestion_prompt', """Você é um assistente especializado em sugestões de resposta para atendimento jurídico.
Sua função é gerar sugestões de resposta profissionais e adequadas ao contexto.

- Não adicione nenhum texto que não seria enviado para o cliente final.
- Não assine as mensagens""")
    
    data = {
        "model": "grok-3-latest",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7,
        "stream": False
    }
    
    try:
        with httpx.Client(verify=True, timeout=60.0) as client:
            response = client.post(url, headers=headers, json=data)
            response.raise_for_status()
            result = response.json()
            return result['choices'][0]['message']['content']
    except Exception as e:
        st.error(f"Erro ao gerar sugestão: {str(e)}")
        return None

# Cache the data loading function
@st.cache_data(ttl=300)  # Cache for 5 minutes
def load_data():
    query = read_sql_file(sql_file_path)
    df = client.query(query).to_dataframe()
    
    # Convert timestamps to São Paulo timezone
    for col in ['created_at', 'last_message']:
        if df[col].dt.tz is None:
            df[col] = pd.to_datetime(df[col]).dt.tz_localize('UTC')
        df[col] = df[col].dt.tz_convert('America/Sao_Paulo')
    
    return df

# Function to load messages
@st.cache_data(ttl=300)  # Cache for 5 minutes
def load_messages(phone):
    query = read_sql_file(messages_sql_path)
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("phone", "STRING", phone)
        ]
    )
    df = client.query(query, job_config=job_config).to_dataframe()
    
    # Convert timestamps to São Paulo timezone
    if not df.empty:
        df['created_at'] = pd.to_datetime(df['created_at'])
        if df['created_at'].dt.tz is None:
            df['created_at'] = df['created_at'].dt.tz_localize('UTC')
        df['created_at'] = df['created_at'].dt.tz_convert('America/Sao_Paulo')
    
    return df

# Function to show lead details
def show_lead_details(lead_data):
    # Display title and back button
    col1, col2 = st.columns([1, 5])
    with col1:
        if st.button("← Voltar"):
            st.session_state.show_lead = False
            st.session_state.selected_lead = None
            st.rerun()
    with col2:
        st.title(lead_data['title'])
    
    st.markdown("---")
    
    # Display lead information in a structured way
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### Informações Básicas")
        st.markdown(f"**ID:** {lead_data['id']}")
        st.markdown(f"**Título:** {lead_data['title']}")
        st.markdown(f"**Quadro:** {lead_data['board']}")
        st.markdown(f"**Data de Criação:** {lead_data['created_at']}")
    
    with col2:
        st.markdown("### Informações de Contato")
        st.markdown(f"**Última Mensagem:** {lead_data['last_message']}")
        st.markdown(f"**Link do Monday:** [Abrir no Monday]({lead_data['monday_link']})")
    
    st.markdown("---")

    # Load messages first to make them available for the suggestion feature
    try:
        phone = lead_data.get('phone')
        if phone:
            with st.spinner('Carregando mensagens...'):
                messages_df = load_messages(phone)
        else:
            messages_df = pd.DataFrame()
            st.warning("Número de telefone não disponível para este lead.")
    except Exception as e:
        messages_df = pd.DataFrame()
        st.error(f"Erro ao carregar mensagens: {str(e)}")

    # Add lead summary section
    st.markdown("### Resumo do Lead")
    
    # Initialize lead summary in session state if not exists
    if 'lead_summary' not in st.session_state:
        st.session_state.lead_summary = None
    
    # Create tabs for summary and prompt editing
    summary_tab, summary_prompt_tab = st.tabs(["📊 Resumo", "⚙️ Configurar Prompt"])
    
    with summary_tab:
        # Create a container for the summary
        summary_container = st.empty()
        
        # Add button to generate summary
        if st.button("Gerar Resumo do Lead", use_container_width=True):
            with st.spinner("Gerando resumo do lead..."):
                monday_info = {
                    'item_id': str(lead_data['id']),
                    'name': lead_data.get('title', 'N/A'),
                    'title': lead_data.get('title', 'N/A'),
                    'status': lead_data.get('status', 'N/A'),
                    'prioridade': lead_data.get('prioridade', 'N/A'),
                    'origem': lead_data.get('origem', 'N/A'),
                    'email': lead_data.get('email', 'N/A')
                }
                
                if not messages_df.empty:
                    summary = generate_lead_status_summary(messages_df, monday_info)
                    if summary:
                        st.session_state.lead_summary = summary
                        
                        # Deletar resumos antigos e enviar o novo
                        with st.spinner("Atualizando no Monday..."):
                            # Primeiro, deleta os resumos antigos
                            success, result = delete_old_summaries(lead_data['id'])
                            if success:
                                st.info(result)
                            else:
                                st.warning(f"Não foi possível deletar resumos antigos: {result}")
                            
                            # Depois, envia o novo resumo
                            update_text = f"{summary}\n\n---\nGerado com Rosenbaum AI"
                            success, result = send_monday_update(lead_data['id'], update_text)
                            if success:
                                st.success("Resumo gerado e enviado para o Monday com sucesso!")
                            else:
                                st.error(f"Resumo gerado, mas houve um erro ao enviar para o Monday: {result}")
                    else:
                        st.error("Não foi possível gerar o resumo do lead.")
                else:
                    st.error("Não há mensagens disponíveis para gerar o resumo.")
        
        # Display lead summary if available
        if st.session_state.lead_summary:
            with summary_container.expander("Resumo do Lead", expanded=True):
                st.markdown(st.session_state.lead_summary)
        else:
            with summary_container:
                st.info("Clique no botão acima para gerar o resumo do lead.")
    
    with summary_prompt_tab:
        st.markdown("### Configurar Prompt de Resumo")
        st.markdown("Personalize o prompt usado para gerar resumos do lead.")
        
        # Initialize prompt in session state if not exists
        if 'summary_prompt' not in st.session_state:
            st.session_state.summary_prompt = """Você é um assistente especializado em análise de leads jurídicos. 
Sua função é gerar resumos claros e objetivos do status do lead, focando em informações relevantes para o acompanhamento do caso."""
        
        # Add prompt editor
        prompt = st.text_area(
            "Prompt de Resumo",
            value=st.session_state.summary_prompt,
            height=200,
            help="Este prompt será usado para gerar resumos do lead. Use {conversation_text} para incluir o histórico de conversas e {monday_text} para incluir os dados do Monday."
        )
        
        # Add save button
        if st.button("💾 Salvar Prompt", use_container_width=True, key="save_summary_prompt"):
            st.session_state.summary_prompt = prompt
            st.success("✅ Prompt salvo com sucesso!")
        
        # Add reset button
        if st.button("🔄 Restaurar Padrão", use_container_width=True, key="reset_summary_prompt"):
            st.session_state.summary_prompt = """Você é um assistente especializado em análise de leads jurídicos. 
Sua função é gerar resumos claros e objetivos do status do lead, focando em informações relevantes para o acompanhamento do caso."""
            st.success("✅ Prompt restaurado para o valor padrão!")

    st.markdown("---")

    # Display Monday.com updates
    st.markdown("### Atualizações do Monday")
    
    try:
        # Load Monday updates with spinner
        with st.spinner('Carregando atualizações do Monday...'):
            updates = fetch_monday_updates([str(lead_data['id'])])
            
            if updates and len(updates) > 0 and updates[0] and 'updates' in updates[0]:
                # Create expander for updates
                with st.expander(f"Ver histórico de atualizações ({len(updates[0]['updates'])} atualizações)", expanded=False):
                    # Display updates
                    for update in updates[0]['updates']:
                        created_at = datetime.fromisoformat(update['created_at'].replace('Z', '+00:00'))
                        created_at = created_at.astimezone(pytz.timezone('America/Sao_Paulo'))
                        
                        # Get creator name or use "Sistema" if null
                        creator_name = update['creator']['name'] if update['creator'] else "Sistema"
                        
                        # Create columns for header
                        col1, col2 = st.columns([3, 1])
                        with col1:
                            st.markdown(f"**Por:** {creator_name}")
                        with col2:
                            st.markdown(f"**{created_at.strftime('%d/%m/%Y %H:%M')}**")
                        
                        # Display update body
                        st.markdown(update['body'], unsafe_allow_html=True)
                        st.markdown("---")
            else:
                st.info("Nenhuma atualização encontrada para este lead.")
    except Exception as e:
        st.error(f"Erro ao carregar atualizações do Monday: {str(e)}")

    st.markdown("---")

    # Add WhatsApp message section
    st.markdown("### Enviar Mensagem")
    
    # Create tabs for message input and prompt editing
    message_tab, prompt_tab = st.tabs(["💬 Mensagem", "⚙️ Configurar Prompt"])
    
    with message_tab:
        # Add suggestion button
        if st.button("Gerar Sugestão de Resposta", use_container_width=True):
            with st.spinner("Gerando sugestão de resposta..."):
                if not messages_df.empty:
                    suggestion = generate_suggestion(messages_df)
                    if suggestion:
                        st.session_state.suggested_message = suggestion
                    else:
                        st.error("Não foi possível gerar uma sugestão de resposta.")
                else:
                    st.error("Não há mensagens disponíveis para gerar sugestão.")
        
        # Initialize message input with suggested message if available
        message = st.text_area(
            "Digite sua mensagem:", 
            height=100,
            value=st.session_state.get('suggested_message', '')
        )
        # Clear the suggested message after it's been used
        if 'suggested_message' in st.session_state:
            del st.session_state.suggested_message
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Enviar Mensagem", use_container_width=True):
                if message:
                    success, result = send_whatsapp_message(lead_data['phone'], message)
                    if success:
                        st.success(result)
                        # Add message to history
                        st.session_state.messages_df = add_message_to_history(
                            st.session_state.messages_df,
                            "Rosenbaum Advogados",
                            "+5511988094449",
                            lead_data['name'],
                            lead_data['phone'],
                            message
                        )
                        st.rerun()
                    else:
                        st.error(result)
                else:
                    st.error("Por favor, digite uma mensagem para enviar.")
        with col2:
            if st.button("Enviar Mensagem (Modo Teste)", use_container_width=True):
                if message:
                    success, result = send_whatsapp_message(lead_data['phone'], message, test_mode=True, test_phone="+5531992251502")
                    if success:
                        st.success(result)
                    else:
                        st.error(result)
                else:
                    st.error("Por favor, digite uma mensagem para enviar.")
    
    with prompt_tab:
        st.markdown("### Configurar Prompt de Sugestão")
        st.markdown("Personalize o prompt usado para gerar sugestões de resposta.")
        
        # Initialize prompt in session state if not exists
        if 'suggestion_prompt' not in st.session_state:
            st.session_state.suggestion_prompt = """Você é um assistente especializado em sugestões de resposta para atendimento jurídico.
Sua função é gerar sugestões de resposta profissionais e adequadas ao contexto.

- Não adicione nenhum texto que não seria enviado para o cliente final.
- Não assine as mensagens"""
        
        # Add prompt editor
        prompt = st.text_area(
            "Prompt de Sugestão",
            value=st.session_state.suggestion_prompt,
            height=200,
            help="Este prompt será usado para gerar sugestões de resposta. Use {conversation_text} para incluir o histórico de conversas e {last_client_message} para incluir a última mensagem do cliente."
        )
        
        # Add save button
        if st.button("💾 Salvar Prompt", use_container_width=True):
            st.session_state.suggestion_prompt = prompt
            st.success("✅ Prompt salvo com sucesso!")
        
        # Add reset button
        if st.button("🔄 Restaurar Padrão", use_container_width=True):
            st.session_state.suggestion_prompt = """Você é um assistente especializado em sugestões de resposta para atendimento jurídico.
Sua função é gerar sugestões de resposta profissionais e adequadas ao contexto.

- Não adicione nenhum texto que não seria enviado para o cliente final.
- Não assine as mensagens"""
            st.success("✅ Prompt restaurado para o valor padrão!")

    st.markdown("---")

    # Display WhatsApp messages
    st.markdown("### Histórico de Mensagens")
    
    if not messages_df.empty:
        # Sort messages in descending order (newest first)
        sorted_messages = messages_df.sort_values('created_at', ascending=False)
        
        # Calculate response times
        response_times = calculate_response_time(sorted_messages)
        
        # Display messages
        current_date = None
        for idx, message in sorted_messages.iterrows():
            # Check if date has changed
            message_date = message['created_at'].strftime('%d/%m/%Y')
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
                        {current_date}
                    </div>
                """, unsafe_allow_html=True)
            
            # Determine message role
            role = "user" if message['message_direction'] == 'received' else "assistant"
            
            # Clean message content
            content = strip_html_tags(message['message_text'] or '')
            
            # Display message
            with st.chat_message(role):
                # Display timestamp
                timestamp = message['created_at'].strftime('%H:%M')
                st.caption(timestamp)
                
                # Display main message
                st.write(content)
                
                # Display file information if present
                if 'file_url' in message and pd.notna(message['file_url']):
                    st.markdown(f"[Abrir arquivo]({message['file_url']})")
                
                # Display attachment URL if present
                if 'attachment_url' in message and pd.notna(message['attachment_url']):
                    st.markdown(f"[Abrir anexo]({message['attachment_url']})")
                
                # Display OCR information if present
                if 'ocr_scan' in message and pd.notna(message['ocr_scan']):
                    st.markdown(f"**OCR:** {message['ocr_scan']}")
                
                # Display attachment filename if present
                if 'attachment_filename' in message and pd.notna(message['attachment_filename']):
                    st.markdown(f"**Anexo:** {message['attachment_filename']}")
                
                # Display audio transcription if present
                if 'audio_transcription' in message and pd.notna(message['audio_transcription']):
                    st.markdown(f"**Transcrição:** {message['audio_transcription']}")
                
                # Display response time if available
                if message['message_direction'] == 'received':
                    if idx in response_times:
                        response_time = format_response_time(response_times[idx])
                        st.caption(f"Tempo de resposta: {response_time}")
                    else:
                        st.caption("Aguardando resposta")
    else:
        st.info("Nenhuma mensagem encontrada para este lead.")

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
        "X-CSRFToken": st.secrets.timelines.csrf_token
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

def send_monday_update(item_id, update_text):
    """Envia um update para o Monday.com."""
    url = "https://api.monday.com/v2"
    headers = {
        "Authorization": st.secrets.monday.api_key,
        "Content-Type": "application/json",
        "API-Version": "2023-10"
    }
    
    # Primeiro, vamos verificar se o item existe
    check_query = """
    query ($itemId: ID!) {
        items (ids: [$itemId]) {
            id
            name
        }
    }
    """
    
    check_variables = {
        "itemId": str(item_id)
    }
    
    try:
        # Verificar se o item existe
        check_response = httpx.post(
            url, 
            json={"query": check_query, "variables": check_variables}, 
            headers=headers
        )
        check_response.raise_for_status()
        check_data = check_response.json()
        
        if "errors" in check_data:
            return False, f"Erro ao verificar item: {check_data['errors']}"
            
        if not check_data.get("data", {}).get("items"):
            return False, f"Item não encontrado no Monday: {item_id}"
        
        # Agora vamos criar o update
        create_query = """
        mutation ($itemId: ID!, $updateText: String!) {
            create_update (item_id: $itemId, body: $updateText) {
                id
                body
                created_at
            }
        }
        """
        
        create_variables = {
            "itemId": str(item_id),
            "updateText": update_text
        }
        
        create_payload = {
            "query": create_query,
            "variables": create_variables
        }
        
        create_response = httpx.post(url, json=create_payload, headers=headers)
        create_response.raise_for_status()
        create_data = create_response.json()
        
        if "errors" in create_data:
            return False, f"Erro ao criar update: {create_data['errors']}"
            
        if not create_data.get("data", {}).get("create_update"):
            return False, "Update não foi criado"
        
        return True, "Update enviado com sucesso"
    except httpx.HTTPError as e:
        error_msg = f"Erro HTTP ao enviar update: {str(e)}"
        if hasattr(e, 'response') and e.response is not None:
            error_msg += f"\nResposta: {e.response.text}"
        return False, error_msg
    except Exception as e:
        return False, f"Erro ao enviar update: {str(e)}"

def get_monday_updates(item_id):
    """Busca todos os updates de um item no Monday."""
    url = "https://api.monday.com/v2"
    headers = {
        "Authorization": st.secrets.monday.api_key,
        "Content-Type": "application/json",
        "API-Version": "2023-10"
    }
    
    query = """
    query ($itemId: ID!) {
        items (ids: [$itemId]) {
            updates {
                id
                body
                created_at
            }
        }
    }
    """
    
    variables = {
        "itemId": str(item_id)
    }
    
    try:
        response = httpx.post(url, json={"query": query, "variables": variables}, headers=headers)
        response.raise_for_status()
        data = response.json()
        
        if "errors" in data:
            return False, f"Erro ao buscar updates: {data['errors']}"
            
        if not data.get("data", {}).get("items"):
            return False, f"Item não encontrado: {item_id}"
            
        updates = data["data"]["items"][0].get("updates", [])
        return True, updates
    except Exception as e:
        return False, f"Erro ao buscar updates: {str(e)}"

def delete_monday_update(update_id):
    """Deleta um update específico no Monday."""
    url = "https://api.monday.com/v2"
    headers = {
        "Authorization": st.secrets.monday.api_key,
        "Content-Type": "application/json",
        "API-Version": "2023-10"
    }
    
    query = """
    mutation ($updateId: ID!) {
        delete_update (id: $updateId) {
            id
        }
    }
    """
    
    variables = {
        "updateId": str(update_id)
    }
    
    try:
        response = httpx.post(url, json={"query": query, "variables": variables}, headers=headers)
        response.raise_for_status()
        data = response.json()
        
        if "errors" in data:
            return False, f"Erro ao deletar update: {data['errors']}"
            
        return True, "Update deletado com sucesso"
    except Exception as e:
        return False, f"Erro ao deletar update: {str(e)}"

def delete_old_summaries(item_id):
    """Deleta todos os resumos antigos de um item."""
    success, result = get_monday_updates(item_id)
    if not success:
        return False, result
        
    updates = result
    deleted_count = 0
    
    for update in updates:
        if "Gerado com Rosenbaum AI" in update.get("body", ""):
            success, _ = delete_monday_update(update["id"])
            if success:
                deleted_count += 1
    
    return True, f"{deleted_count} resumos antigos deletados"

try:
    # Initialize session state
    if 'show_lead' not in st.session_state:
        st.session_state.show_lead = False
    if 'selected_lead' not in st.session_state:
        st.session_state.selected_lead = None
    if 'page' not in st.session_state:
        st.session_state.page = 0
    
    # Load data with cache
    df = load_data()
    
    # If a lead is selected, show its details
    if st.session_state.show_lead and st.session_state.selected_lead:
        show_lead_details(st.session_state.selected_lead)
    else:
        # Display title
        st.title("Rosenbaum CRM")
        
        # Create filters
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            # Board filter
            boards = ['Todos'] + sorted(df['board'].unique().tolist())
            selected_board = st.selectbox('Quadro', boards)
        
        with col2:
            # Creation date range filter
            min_date = df['created_at'].min()
            max_date = df['created_at'].max()
            creation_date_range = st.date_input(
                'Data de criação do lead',
                value=(min_date, max_date),
                min_value=min_date,
                max_value=max_date
            )
        
        with col3:
            # Last message date range filter
            min_last_msg = df['last_message'].min()
            max_last_msg = df['last_message'].max()
            last_msg_date_range = st.date_input(
                'Data da última mensagem',
                value=(min_last_msg, max_last_msg),
                min_value=min_last_msg,
                max_value=max_last_msg
            )
        
        with col4:
            # Title search
            search_title = st.text_input('Buscar por título', '')
        
        with col5:
            # Sort options
            sort_options = {
                'Data de criação (mais recente)': 'created_at',
                'Data de criação (mais antiga)': 'created_at_asc',
                'Última mensagem (mais recente)': 'last_message',
                'Última mensagem (mais antiga)': 'last_message_asc',
                'Quantidade de mensagens (maior)': 'message_count',
                'Quantidade de mensagens (menor)': 'message_count_asc'
            }
            sort_by = st.selectbox('Ordenar por', list(sort_options.keys()))
        
        # Add spacing between filters and table
        st.markdown("---")
        st.markdown("### Lista de Leads")
        st.markdown("")
        
        # Apply filters
        filtered_df = df.copy()
        
        # Filter by board
        if selected_board != 'Todos':
            filtered_df = filtered_df[filtered_df['board'] == selected_board]
        
        # Filter by creation date range
        if len(creation_date_range) == 2:
            start_date, end_date = creation_date_range
            filtered_df = filtered_df[
                (filtered_df['created_at'].dt.date >= start_date) &
                (filtered_df['created_at'].dt.date <= end_date)
            ]
        
        # Filter by last message date range
        if len(last_msg_date_range) == 2:
            start_date, end_date = last_msg_date_range
            filtered_df = filtered_df[
                (filtered_df['last_message'].dt.date >= start_date) &
                (filtered_df['last_message'].dt.date <= end_date)
            ]
        
        # Filter by title search
        if search_title:
            filtered_df = filtered_df[filtered_df['title'].str.contains(search_title, case=False)]
        
        # Apply sorting
        sort_field = sort_options[sort_by]
        if sort_field.endswith('_asc'):
            sort_field = sort_field[:-4]
            ascending = True
        else:
            ascending = False
        
        filtered_df = filtered_df.sort_values(by=sort_field, ascending=ascending)
        
        # Format the created_at column for display
        filtered_df['created_at'] = filtered_df['created_at'].dt.strftime('%d/%m/%Y %H:%M')
        filtered_df['last_message'] = filtered_df['last_message'].dt.strftime('%d/%m/%Y %H:%M')
        
        # Calculate items per page and total pages
        items_per_page = 20
        total_items = len(filtered_df)
        total_pages = (total_items + items_per_page - 1) // items_per_page
        
        # Get current page items
        start_idx = st.session_state.page * items_per_page
        end_idx = min(start_idx + items_per_page, total_items)
        current_page_items = filtered_df.iloc[start_idx:end_idx]
        
        # Create a container for the table
        table_container = st.container()
        
        # Display the data in a table with buttons
        with table_container:
            # Create header row
            header_cols = st.columns([1, 2, 2, 3, 2, 1, 1])
            header_cols[0].write("**ID**")
            header_cols[1].write("**Data de Criação**")
            header_cols[2].write("**Quadro**")
            header_cols[3].write("**Título**")
            header_cols[4].write("**Última Mensagem**")
            header_cols[5].write("**Mensagens**")
            header_cols[6].write("**Ação**")
            
            st.markdown("---")
            
            # Display data rows
            for _, row in current_page_items.iterrows():
                cols = st.columns([1, 2, 2, 3, 2, 1, 1])
                cols[0].write(row['id'])
                cols[1].write(row['created_at'])
                cols[2].write(row['board'])
                cols[3].write(row['title'])
                cols[4].write(row['last_message'])
                cols[5].write(f"📨 {row['message_count']}")
                with cols[6]:
                    if st.button("Abrir", key=f"btn_{row['id']}"):
                        st.session_state.show_lead = True
                        st.session_state.selected_lead = row.to_dict()
                        # Clear lead summary when selecting a new lead
                        if 'lead_summary' in st.session_state:
                            del st.session_state.lead_summary
                        st.rerun()
                st.markdown("---")
        
        # Add pagination controls
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if st.session_state.page < total_pages - 1:
                if st.button("Ver mais", use_container_width=True):
                    st.session_state.page += 1
                    st.rerun()
            
            # Show current page info
            st.write(f"Mostrando {start_idx + 1}-{end_idx} de {total_items} itens")

except Exception as e:
    st.error(f"Erro ao buscar dados: {str(e)}")
    st.info("Nenhum dado disponível") 