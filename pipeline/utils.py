import os
import json
import streamlit as st

def KtoC(K):
    """Konwertuje temperaturę z Kelwinów na stopnie Celsjusza."""
    if isinstance(K, list):
        return [k-273.15 for k in K]
    return K-273.15
def CtoK(C):
    """Konwertuje temperaturę z stopni Celsjusza na Kelwiny."""
    if isinstance(C, list):
        return [c+273.15 for c in C]
    return C+273.15 

def load_project_data(filepath="../data/data.json"):
    """Ładuje stałe fizyczne i ustawienia domyślne z pliku zewnętrznego."""
    if not os.path.exists(filepath):
        st.error(f"Błąd: Nie znaleziono pliku danych: {filepath}")
        return None
        
    with open(filepath, 'r') as f:
        return json.load(f)