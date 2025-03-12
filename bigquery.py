import streamlit as st
from google.oauth2 import service_account
from google.cloud import bigquery
import pandas as pd


credentials = service_account.Credentials.from_service_account_info(
    st.secrets["gcp_service_account"]
)
client = bigquery.Client(credentials=credentials)

@st.cache_data(ttl=3600)
def execute_query(query):

    try:
        query_job = client.query(query)
        rows_raw = query_job.result()
        rows = [dict(row) for row in rows_raw]
        return pd.DataFrame(rows)
    except Exception as e:
        print(f"Erro ao executar query: {str(e)}")
        return pd.DataFrame()

def load_messages():

    query = """
    SELECT * FROM `zapy-306602.gtms.messages`
    """
    return execute_query(query)

