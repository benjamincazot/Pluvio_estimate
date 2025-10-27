import streamlit as st
import pandas as pd
from scipy.interpolate import griddata
import numpy as np
from pathlib import Path
import folium
from streamlit_folium import st_folium

# --- CONFIGURATION ---

FILES_TO_PROCESS = {
    "Historique": "synthese_pluviometrie_BASELINE.csv",
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


# @st.cache_data : met en cache les fichiers CSV pour de meilleures performances
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
        points = df[[COL_LAT, COL_LON]].values
        values_moyenne = df[COL_PLUVIO_MOYENNE].values
        values_excep = df[COL_PLUVIO_EXCEP].values
        target_point = np.array([target_lat, target_lon])

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


# --- PARTIE PRINCIPALE : L'INTERFACE WEB AVEC CARTE ---

st.set_page_config(page_title="Interpolation Pluvio", layout="centered")
st.title("🌦️ Outil d'interpolation de pluviométrie")
st.markdown("Cliquez sur la carte pour sélectionner un point, puis cliquez sur 'Calculer'.")

# 1. Initialiser st.session_state
if "clicked_lat" not in st.session_state:
    st.session_state.clicked_lat = None
    st.session_state.clicked_lon = None
    st.session_state.center = [46.2276, 2.2137]  # Centre de la France
    st.session_state.zoom = 6

# 2. Créer la carte Folium
m = folium.Map(
    location=st.session_state.center, 
    zoom_start=st.session_state.zoom,
    tiles="OpenStreetMap"
)

# --- NOUVEAUTÉ : Ajout du repère ---
# 2.5. Ajouter un repère (Marker) si un point a déjà été cliqué
if st.session_state.clicked_lat is not None:
    folium.Marker(
        location=[st.session_state.clicked_lat, st.session_state.clicked_lon],
        popup=f"Lat: {st.session_state.clicked_lat:.4f}, Lon: {st.session_state.clicked_lon:.4f}",
        icon=folium.Icon(color="red", icon="info-sign")
    ).add_to(m)
# --- FIN DE LA NOUVEAUTÉ ---

# 3. Afficher la carte et capturer le clic
map_data = st_folium(m, key="folium_map", width=700, height=500)

# 4. Traiter le clic
if map_data and map_data.get("last_clicked"):
    st.session_state.clicked_lat = map_data["last_clicked"]["lat"]
    st.session_state.clicked_lon = map_data["last_clicked"]["lng"]
    st.session_state.center = [map_data["last_clicked"]["lat"], map_data["last_clicked"]["lng"]]
    st.session_state.zoom = 10
    
    # On force le script à se ré-exécuter pour afficher le nouveau repère immédiatement
    st.rerun() 

# 5. Afficher les coordonnées sélectionnées
if st.session_state.clicked_lat:
    st.info(f"Coordonnées sélectionnées : Latitude = {st.session_state.clicked_lat:.4f}, Longitude = {st.session_state.clicked_lon:.4f}")
else:
    st.info("Veuillez cliquer sur la carte pour sélectionner un point.")

# 6. Bouton de calcul
if st.button("Calculer les estimations pour le point sélectionné"):
    
    if st.session_state.clicked_lat is None:
        st.warning("Veuillez d'abord cliquer sur la carte pour sélectionner un point.")
    else:
        user_lat = st.session_state.clicked_lat
        user_lon = st.session_state.clicked_lon
        
        with st.spinner("Calcul en cours..."):
            st.subheader(f"Résultats pour (Lat={user_lat:.4f}, Lon={user_lon:.4f})")
            
            all_success = True
            for horizon, filename in FILES_TO_PROCESS.items():
                st.write(f"--- Horizon {horizon} ({filename}) ---")
                
                df_data = load_data(filename)
                
                if df_data is not None:
                    data = get_interpolated_values(df_data, user_lat, user_lon)
                    
                    if data:
                        if np.isnan(data["moyenne"]):
                            st.warning("Le point est en dehors de la zone de données (Extrapolation impossible).")
                        else:
                            st.success(f"PLUVIOMETRIE moyenne  : **{data['moyenne']:.2f}** mm")
                            st.info(f"PLUVIO EXCEPTIONNELLE : **{data['exceptionnelle']:.2f}** mm")
                    else:
                        all_success = False
                else:
                    all_success = False
        
        if all_success:

            st.balloons()

