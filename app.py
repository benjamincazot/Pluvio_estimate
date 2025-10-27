import streamlit as st
import pandas as pd
from scipy.interpolate import griddata
import numpy as np
from pathlib import Path

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
        
        # 2. Préparer les valeurs (Z)
        values_moyenne = df[COL_PLUVIO_MOYENNE].values
        values_excep = df[COL_PLUVIO_EXCEP].values

        # 3. Définir le point cible (xi)
        target_point = np.array([target_lat, target_lon])

        # 4. Exécuter l'interpolation
        result_moyenne = griddata(
            points,
            values_moyenne,
            target_point,
            method=INTERPOLATION_METHOD,
            fill_value=np.nan 
        )
        
        result_excep = griddata(
            points,
            values_excep,
            target_point,
            method=INTERPOLATION_METHOD,
            fill_value=np.nan
        )
        
        return {"moyenne": result_moyenne.item(), "exceptionnelle": result_excep.item()}
        
    except Exception as e:
        st.error(f"Erreur durant l'interpolation : {e}")
        return None


# --- PARTIE PRINCIPALE : L'INTERFACE WEB ---

# st.set_page_config définit le titre de l'onglet dans le navigateur
st.set_page_config(page_title="Interpolation Pluvio", layout="centered")

# st.title affiche un titre principal
st.title("🌦️ Outil d'interpolation de pluviométrie")

# st.markdown permet d'écrire du texte
st.markdown("Entrez les coordonnées pour obtenir les estimations de pluviométrie (moyenne et exceptionnelle) aux horizons 2030, 2050 et 2100.")

# st.number_input remplace les input() pour les nombres
# 'value' est la valeur par défaut
user_lat = st.number_input(
    "Entrez la Latitude (ex: 43.3)", 
    value=43.2965,  # Exemple : Pau
    format="%.4f"
)

user_lon = st.number_input(
    "Entrez la Longitude (ex: -0.36)", 
    value=-0.3707,  # Exemple : Pau
    format="%.4f"
)

# st.button crée un bouton. Le code à l'intérieur ne s'exécute que si on clique.
if st.button("Calculer les estimations"):
    
    # st.spinner affiche un message de chargement
    with st.spinner("Calcul en cours..."):
        
        # st.subheader crée un sous-titre
        st.subheader(f"Résultats pour (Lat={user_lat}, Lon={user_lon})")
        
        all_success = True

        for horizon, filename in FILES_TO_PROCESS.items():
            
            # st.write écrit du texte simple
            st.write(f"--- Horizon {horizon} ({filename}) ---")
            
            # On charge les données (en utilisant le cache)
            df_data = load_data(filename)
            
            if df_data is not None:
                data = get_interpolated_values(df_data, user_lat, user_lon)
                
                if data:
                    if np.isnan(data["moyenne"]):
                        # st.warning affiche un message en jaune
                        st.warning("Le point est en dehors de la zone de données (Extrapolation impossible).")
                    else:
                        # st.success affiche un message en vert
                        st.success(f"PLUVIOMETRIE moyenne  : **{data['moyenne']:.2f}**")
                        # st.info affiche un message en bleu
                        st.info(f"PLUVIO EXCEPTIONNELLE : **{data['exceptionnelle']:.2f}**")
                else:
                    all_success = False
            else:
                all_success = False
    
    if all_success:
        st.balloons() # Petite célébration si tout s'est bien passé !