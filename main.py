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
    CASE_ANALYSIS_PROMPT
)

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

st.set_page_config(
    page_title="Rosenbaum Advogados AI",
    layout="wide"
)

# Initialize session state for navigation and pagination
if 'current_page' not in st.session_state:
    st.session_state.current_page = "inbox"
if 'display_count' not in st.session_state:
    st.session_state.display_count = 20

df = load_messages()

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

# Group by sender name and phone
grouped_df = received_messages.groupby(['Nome', 'Telefone']).agg({
    'message_uid': 'count',  # Count of messages
    'created_at': 'max',  # Get the latest message date
    'account_name': 'first',  # Get account name
    'ocr_scan': lambda x: x.notna().sum(),  # Count messages with OCR
    'file_url': lambda x: x.notna().sum()  # Count messages with files
}).reset_index()

# Rename columns for better understanding
grouped_df = grouped_df.rename(columns={
    'message_uid': 'Total de mensagens recebidas',
    'created_at': 'Última mensagem',
    'account_name': 'Conta',
    'ocr_scan': 'Mensagens com OCR',
    'file_url': 'Mensagens com arquivos'
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

# Page content
if st.session_state.current_page == "inbox":
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
        
        st.markdown('<div class="filter-container">', unsafe_allow_html=True)
        
        # Add search boxes in columns
        col1, col2 = st.columns(2)
        with col1:
            search_phone = st.text_input("📱 Buscar por telefone:", placeholder="Digite o número...")
        with col2:
            search_name = st.text_input("👤 Buscar por nome:", placeholder="Digite o nome...")
        
        # Add date filter with better formatting
        min_date = grouped_df['Última mensagem'].min().date()
        max_date = grouped_df['Última mensagem'].max().date()
        date_range = st.date_input(
            "📅 Período:",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date
        )
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Filter conversations based on search and date
    filtered_df = grouped_df
    if search_phone or search_name:
        if search_phone:
            filtered_df = filtered_df[filtered_df['Telefone'].str.contains(search_phone, case=False, na=False)]
        if search_name:
            filtered_df = filtered_df[filtered_df['Nome'].str.contains(search_name, case=False, na=False)]
    
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
        st.markdown(f"""
            <div class='conversation-card'>
                <div class='conversation-header'>
                    <div class='conversation-name'>
                        {row['Nome']} • 📱 {row['Telefone']}
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
            
            # Create three columns for chat details
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.markdown("**📱 Contato**")
                st.markdown(f"Nome: {chat_info['chat_full_name']}")
                st.markdown(f"Telefone: {selected_phone}")
            
            with col2:
                st.markdown("**👤 Responsável**")
                st.markdown(f"Nome: {chat_info['responsible_name']}")
                st.markdown(f"Conta: {chat_info['account_name']}")
            
            with col3:
                st.markdown("**🔗 Links**")
                st.markdown(f"[Abrir chat no WhatsApp]({chat_info['chat_url']})")
            
            # List all image files at the top
            image_files = sender_messages[sender_messages['file_url'].notna()].copy()
            if not image_files.empty:
                st.markdown("### 📸 Arquivos de Imagem")
                # Create columns for a more compact layout
                cols = st.columns(3)
                for idx, img in image_files.iterrows():
                    col_idx = idx % 3
                    with cols[col_idx]:
                        st.markdown(f"📎 [{img['attachment_filename'] or 'Imagem'}]({img['file_url']})")
            
            # Display messages with better formatting
            st.markdown("### Histórico de mensagens")
            
            # Sort messages in ascending order (oldest first)
            sorted_messages = sender_messages.sort_values('created_at', ascending=True)
            
            # Calcular tempos de resposta
            response_times = calculate_response_time(sorted_messages)
            
            # Iterate through messages and display them as chat messages
            for _, msg in sorted_messages.iterrows():
                # Determine message role
                role = "user" if msg['message_direction'] == 'received' else "assistant"
                
                # Format message content
                content = msg['message_text'] or ''
                
                # Add file information if present
                if msg['file_url']:
                    content += f"\n📎 [Abrir arquivo]({msg['file_url']})"
                
                # Add OCR information if present
                if msg['ocr_scan']:
                    content += f"\n🔍 OCR: {msg['ocr_scan']}"
                
                if msg['attachment_filename']:
                    content += f"\n📎 Anexo: {msg['attachment_filename']}"
                if msg['audio_transcription']:
                    content += f"\n🎤 Transcrição: {msg['audio_transcription']}"
                
                # Display chat message
                with st.chat_message(role):
                    timestamp = msg['created_at'].strftime('%d/%m/%Y %H:%M:%S')
                    if msg['message_direction'] == 'received':
                        if msg['message_uid'] in response_times:
                            response_time = format_response_time(response_times[msg['message_uid']])
                            st.write(f"**{timestamp}** (⏱️ Tempo de resposta: {response_time})")
                        else:
                            st.write(f"**{timestamp}** (⏱️ Aguardando resposta)")
                    else:
                        st.write(f"**{timestamp}**")
                    st.write(content)
            
            # Add Grok chat interface
            st.markdown("### 🤖 Assistente de IA Rosenbaum")
            
            # Initialize chat history in session state if it doesn't exist
            if 'grok_chat_history' not in st.session_state:
                st.session_state.grok_chat_history = []
            
            # Add buttons in a single row with equal widths
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("📄 Checklist de Documentos", type="primary", use_container_width=True):
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
                if st.button("⚖️ Analisar Qualidade do Processo", type="primary", use_container_width=True):
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

            # Add suggestion buttons in another row
            col3, col4 = st.columns(2)
            
            with col3:
                if st.button("💡 Sugerir Resposta", use_container_width=True):
                    with st.spinner("Gerando sugestão..."):
                        suggestion = generate_suggestion(sender_messages)
                        if suggestion:
                            st.session_state.grok_chat_history.append({"role": "assistant", "content": suggestion})
                            st.rerun()
                        else:
                            st.error("Não foi possível gerar uma sugestão. Tente novamente.")
            
            with col4:
                if st.button("🗑️ Limpar Chat", use_container_width=True):
                    st.session_state.grok_chat_history = []
                    st.rerun()

            # Chat input
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
            
            # Display chat history
            for message in st.session_state.grok_chat_history:
                with st.chat_message(message["role"]):
                    st.write(message["content"])
        else:
            st.warning("Não foram encontradas mensagens para este remetente.")