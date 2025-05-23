import requests
import json
from typing import List, Dict, Any
import streamlit as st

def fetch_monday_updates(item_ids: List[str], limit: int = 100) -> List[Dict[Any, Any]]:
    """
    Fetch updates from Monday.com for specific items.
    
    Args:
        item_ids (List[str]): List of Monday.com item IDs
        limit (int): Maximum number of updates to fetch per item
        
    Returns:
        List[Dict]: List of items with their updates
    """
    api_key = st.secrets["monday"]["api_key"]
    url = "https://api.monday.com/v2/"
    
    headers = {
        "Authorization": api_key,
        "API-Version": "2023-10",
        "Content-Type": "application/json"
    }
    
    item_filter = f"items(ids: [{', '.join(item_ids)}])"
    
    query = f'''query {{
        {item_filter} {{
            id
            name
            updates(limit: {limit}) {{
                id
                body
                created_at
                creator {{
                    id
                    name
                    email
                }}
            }}
        }}
    }}'''
    
    response = requests.post(
        url,
        headers=headers,
        json={"query": query}
    )
    
    if response.status_code != 200:
        raise Exception(f"Error fetching updates: {response.text}")
    
    data = response.json()
    return data.get("data", {}).get("items", []) 