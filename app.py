import streamlit as st
import pandas as pd
from scipy.interpolate import griddata
import numpy as np
from pathlib import Path
import folium
from streamlit_folium import st_folium

# --- CONFIGURATION (Identique à avant) ---

FILES_TO_PROCESS = {
    "2030": "synthese_pluviometrie_2030.csv",
    "2050": "synthese_pluviometrie_2050.csv",
    "2100": "synthese_pluviometrie_2100.csv"
}
COL_LAT = "Latitude"
COL_LON = "Longitude"
COL_PLUVIO_MOYENNE = "PLUVIOMETRIE moyenne des 17 fichiers"
COL_PLUVIO_EXCEP = "PLUVIO EXCEPTIONNELLE moyenne des 17 fichiers"
CSV_SEPARATOR = ";"
CSV_DECIMAL = ","
INTERPOLATION_METHOD = 'linear'

# --- FIN CONFIGURATION ---


# @st.cache_data est un "décorateur" qui dit à Streamlit de 
# ne pas recharger ce fichier CSV à chaque interaction, pour plus de performance.
@st.cache_data
def load_data(file_path_str):
    """Charge et nettoie un fichier CSV."""
    file_path = Path(file_path_str)
    if not file_path.exists():
        st.error(f"Erreur Fichier : {file_path_str} non trouvé.")
        return None
        
    try:
        df = pd.read_csv(
            file_path,
            sep=CSV_SEPARATOR,
            decimal=CSV_DECIMAL
        )
    except Exception as e:
        st.error(f"Erreur lecture CSV {file_path_str} : {e}")
        return None

    # Nettoyage des apostrophes et conversion
    df[COL_PLUVIO_MOYENNE] = pd.to_numeric(
        df[COL_PLUVIO_MOYENNE].astype(str).str.strip(" '").str.replace(',', '.'),
        errors='coerce'
    )
    df[COL_PLUVIO_EXCEP] = pd.to_numeric(
        df[COL_PLUVIO_EXCEP].astype(str).str.strip(" '").str.replace(',', '.'),
        errors='coerce'
    )
    
    # Nettoyage des Lat/Lon (au cas où)
    df[COL_LAT] = pd.to_numeric(
        df[COL_LAT].astype(str).str.strip(" '").str.replace(',', '.'),
        errors='coerce'
    )
    df[COL_LON] = pd.to_numeric(
        df[COL_LON].astype(str).str.strip(" '").str.replace(',', '.'),
        errors='coerce'
    )
    
    # Supprimer les lignes où les données critiques sont NaN
    df = df.dropna(subset=[COL_LAT, COL_LON, COL_PLUVIO_MOYENNE, COL_PLUVIO_EXCEP])
    
    return df


def get_interpolated_values(df, target_lat, target_lon):
    """
    Exécute l'interpolation sur un DataFrame déjà chargé et nettoyé.
    """
    if df is None or df.empty:
        st.warning("Aucune donnée valide à interpoler.")
        return None

    try:
        # 1. Préparer les points (X, Y)
        points = df[[COL_LAT, COL_LON]].values
        
        # 2. Préparer les valeurs (Z
