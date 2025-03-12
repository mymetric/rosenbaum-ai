import streamlit as st
from bigquery import load_messages
import pandas as pd
import httpx
import json

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
    full_prompt = f"""Analise a seguinte conversa e responda à pergunta do usuário:

{conversation_text}

Pergunta do usuário: {prompt}

Resposta:"""
    
    # Call Grok API
    url = "https://api.x.ai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {st.secrets.grok.api_key}",
        "Content-Type": "application/json"
    }
    
    data = {
        "model": "grok-2-latest",
        "messages": [
            {"role": "system", "content": "Você é um assistente especializado em analisar conversas de atendimento ao cliente de um escritório de advocacia especializado em Direito do Consumidor, com foco em Direito Aéreo e Planos de Saúde. Suas respostas devem ser profissionais, claras e objetivas, sempre considerando o contexto jurídico específico dessas áreas."},
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
    full_prompt = f"""Analise a seguinte conversa e sugira uma resposta profissional e adequada para a última mensagem do cliente:

{conversation_text}

Última mensagem do cliente: {last_client_message['message_text']}

Sugestão de resposta:"""
    
    # Call Grok API
    url = "https://api.x.ai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {st.secrets.grok.api_key}",
        "Content-Type": "application/json"
    }
    
    data = {
        "model": "grok-2-latest",
        "messages": [
            {"role": "system", "content": "Você é um assistente especializado em atendimento ao cliente de um escritório de advocacia especializado em Direito do Consumidor, com foco em Direito Aéreo e Planos de Saúde. Suas respostas devem ser profissionais, claras e objetivas, sempre considerando o contexto jurídico específico dessas áreas."},
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
    
    # Prepare the prompt for missing documents
    full_prompt = f"""Analise a seguinte conversa e liste os documentos essenciais que ainda precisam ser solicitados ao cliente para dar entrada no processo judicial. Considere:

1. Documentos básicos de identificação
2. Documentos específicos do caso (bilhetes aéreos, contratos de plano de saúde, etc.)
3. Documentos comprobatórios de danos
4. Documentos de comunicação com a empresa

Conversa:
{conversation_text}

Lista de documentos faltantes para dar entrada no processo:"""
    
    # Call Grok API
    url = "https://api.x.ai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {st.secrets.grok.api_key}",
        "Content-Type": "application/json"
    }
    
    data = {
        "model": "grok-2-latest",
        "messages": [
            {"role": "system", "content": "Você é um assistente especializado em análise de documentos para processos de Direito do Consumidor, com foco em Direito Aéreo e Planos de Saúde. Liste apenas os documentos essenciais que ainda não foram mencionados na conversa e que são necessários para dar entrada no processo judicial, considerando as especificidades dessas áreas do direito."},
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
        st.error(f"Erro ao gerar lista de documentos: {str(e)}")
        return None

st.set_page_config(
    page_title="Rosenbaum AI",
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

# Navigation buttons
col1, col2 = st.columns(2)
with col1:
    if st.button("📥 Caixa de Entrada", use_container_width=True):
        st.session_state.current_page = "inbox"
        st.rerun()
with col2:
    if st.button("💬 Chat", use_container_width=True):
        st.session_state.current_page = "chat"
        st.rerun()

# Page content
if st.session_state.current_page == "inbox":
    st.subheader("Dados agrupados por remetente")
    
    # Create a container for filters with a light background
    with st.container():
        st.markdown("""
            <style>
            .filter-container {
                background-color: #f0f2f6;
                padding: 1rem;
                border-radius: 0.5rem;
                margin-bottom: 1rem;
            }
            </style>
            """, unsafe_allow_html=True)
        
        st.markdown('<div class="filter-container">', unsafe_allow_html=True)
        
        # Add filter title
        st.markdown("### 🔍 Filtros")
        
        # Add search boxes in columns
        col1, col2 = st.columns(2)
        with col1:
            search_phone = st.text_input("📱 Buscar por telefone:", placeholder="Digite o número de telefone...")
        with col2:
            search_name = st.text_input("👤 Buscar por nome:", placeholder="Digite o nome...")
        
        # Add date filter
        min_date = grouped_df['Última mensagem'].min().date()
        max_date = grouped_df['Última mensagem'].max().date()
        date_range = st.date_input(
            "📅 Filtrar por data da última mensagem:",
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
    
    # Reset display count when filters change
    if search_phone or search_name or len(date_range) == 2:
        st.session_state.display_count = 20
    
    # Show number of results
    st.markdown(f"**📊 Resultados encontrados: {len(filtered_df)}**")
    
    # Create a container for the conversation list
    with st.container():
        # Create a more compact table layout
        for _, row in filtered_df.head(st.session_state.display_count).iterrows():
            with st.container():
                # Create columns for the conversation row
                col1, col2, col3, col4 = st.columns([2, 2, 1, 0.5])
                
                with col1:
                    st.markdown(f"**{row['Nome']}** • 📱 {row['Telefone']}")
                
                with col2:
                    st.markdown(f"💬 {row['Total de mensagens recebidas']} • 📸 {row['Mensagens com OCR']} • 📎 {row['Mensagens com arquivos']}")
                
                with col3:
                    st.markdown(f"⏰ {row['Última mensagem'].strftime('%d/%m/%Y %H:%M')}")
                
                with col4:
                    if st.button("💬", key=f"btn_{row['Nome']}_{row['Telefone']}", use_container_width=True):
                        st.session_state.selected_sender = f"{row['Nome']} ({row['Telefone']})"
                        st.session_state.current_page = "chat"
                        st.rerun()
                
                # Add a separator between conversations
                st.markdown("---")
    
    # Add "Load more" button if there are more results
    if len(filtered_df) > st.session_state.display_count:
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if st.button("📥 Carregar mais", key="load_more", use_container_width=True):
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
            
            # Add a separator
            st.markdown("---")
            
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
                st.markdown("---")
            
            # Display messages with better formatting
            st.markdown("### Histórico de mensagens")
            
            # Sort messages in ascending order (oldest first)
            sorted_messages = sender_messages.sort_values('created_at', ascending=True)
            
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
                    st.write(f"**{msg['created_at'].strftime('%d/%m/%Y %H:%M:%S')}**")
                    st.write(content)
            
            st.markdown("---")
            
            # Add Grok chat interface
            st.markdown("### 🤖 Assistente Grok")
            
            # Initialize chat history in session state if it doesn't exist
            if 'grok_chat_history' not in st.session_state:
                st.session_state.grok_chat_history = []
            
            # Add buttons in a single row with equal widths
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                if st.button("💡 Sugerir Resposta", use_container_width=True):
                    with st.spinner("Gerando sugestão..."):
                        suggestion = generate_suggestion(sender_messages)
                        if suggestion:
                            st.session_state.grok_chat_history.append({"role": "assistant", "content": suggestion})
                            st.rerun()
                        else:
                            st.error("Não foi possível gerar uma sugestão. Tente novamente.")
            
            with col2:
                # Check if there's a suggestion in the chat history
                has_suggestion = (
                    st.session_state.grok_chat_history and 
                    isinstance(st.session_state.grok_chat_history[-1], dict) and
                    st.session_state.grok_chat_history[-1].get("role") == "assistant"
                )
                
                if has_suggestion:
                    if st.button("📤 Enviar Sugestão", use_container_width=True):
                        st.info("Funcionalidade em desenvolvimento. Em breve você poderá enviar a sugestão diretamente para o WhatsApp.")
                else:
                    st.button("📤 Enviar Sugestão", use_container_width=True, disabled=True)
            
            with col3:
                if st.button("📄 Analisar Documentos para Processo", use_container_width=True):
                    with st.spinner("Analisando documentos necessários..."):
                        missing_docs = generate_missing_documents(sender_messages)
                        if missing_docs:
                            st.session_state.grok_chat_history.append({"role": "assistant", "content": f"**📄 Documentos Necessários para Processo:**\n\n{missing_docs}"})
                            st.rerun()
                        else:
                            st.error("Não foi possível gerar a lista de documentos. Tente novamente.")
            
            with col4:
                if st.button("🗑️ Limpar Chat", use_container_width=True):
                    st.session_state.grok_chat_history = []
                    st.rerun()
            
            # Chat input
            if prompt := st.chat_input("Faça uma pergunta sobre a conversa..."):
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