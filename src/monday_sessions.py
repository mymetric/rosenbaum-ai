# Sort options
sort_options = {
    'Última mensagem recebida (mais recente)': 'last_received_message',
    'Data de criação (mais recente)': 'created_at',
    'Data de criação (mais antiga)': 'created_at_asc',
    'Última mensagem (mais recente)': 'last_message',
    'Última mensagem (mais antiga)': 'last_message_asc',
    'Quantidade de mensagens (maior)': 'message_count',
    'Quantidade de mensagens (menor)': 'message_count_asc'
}
sort_by = st.selectbox('Ordenar por', list(sort_options.keys()), index=0)

# Apply sorting
sort_field = sort_options[sort_by]
if sort_field == 'last_received_message':
    # Sort by last received message (most recent first)
    filtered_df = filtered_df.sort_values(by='last_message', ascending=False)
elif sort_field.endswith('_asc'):
    sort_field = sort_field[:-4]
    ascending = True
    filtered_df = filtered_df.sort_values(by=sort_field, ascending=ascending)
else:
    ascending = False
    filtered_df = filtered_df.sort_values(by=sort_field, ascending=ascending) 