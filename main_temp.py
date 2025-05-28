# Display title
st.title("Rosenbaum CRM")

# Display OCR statistics
total_leads = len(df)
leads_with_ocr = len(df[df['ocr_count'] > 0])
total_ocr = df['ocr_count'].sum()
email_count = len(df[df['channel'] == 'email'])

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Total de Leads", total_leads)
with col2:
    st.metric("Leads com OCR", leads_with_ocr)
with col3:
    st.metric("Total de OCRs", total_ocr)
with col4:
    st.metric("Total de Emails", email_count)

st.markdown("---")

# Create filters
col1, col2, col3, col4, col5, col6 = st.columns(6)

# ... rest of the code ...

# Display the data in a table with buttons
with table_container:
    # Create header row
    header_cols = st.columns([1, 2, 2, 3, 2, 1, 1, 1, 1])
    header_cols[0].write("**ID**")
    header_cols[1].write("**Data de Criação**")
    header_cols[2].write("**Quadro**")
    header_cols[3].write("**Título**")
    header_cols[4].write("**Última Mensagem**")
    header_cols[5].write("**Mensagens**")
    header_cols[6].write("**OCR**")
    header_cols[7].write("**Canal**")
    header_cols[8].write("**Ação**")
    
    st.markdown("---")
    
    # Display data rows
    for _, row in current_page_items.iterrows():
        cols = st.columns([1, 2, 2, 3, 2, 1, 1, 1, 1])
        cols[0].write(row['id'])
        cols[1].write(row['created_at'])
        cols[2].write(row['board'])
        cols[3].write(row['title'])
        cols[4].write(row['last_message'])
        cols[5].write(f"📨 {row['message_count']}")
        cols[6].write(f"📄 {row['ocr_count']}")
        cols[7].write("📧" if row['channel'] == 'email' else "💬")
        with cols[8]:
            if st.button("Abrir", key=f"btn_{row['id']}"):
                st.session_state.show_lead = True
                st.session_state.selected_lead = row.to_dict()
                # Clear lead summary when selecting a new lead
                if 'lead_summary' in st.session_state:
                    del st.session_state.lead_summary
                st.rerun()
        st.markdown("---") 