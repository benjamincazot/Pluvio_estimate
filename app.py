import streamlit as st
import pandas as pd
from scipy.interpolate import griddata
import numpy as np
from pathlib import Path
import folium
from streamlit_folium import st_folium
import matplotlib.pyplot as plt
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter

# --- CONFIGURATION ---

# On associe "2020" au fichier BASELINE pour l'affichage graphique
FILES_TO_PROCESS = {
    "2020": "synthese_pluviometrie_BASELINE.csv",
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

# Configuration de la page (Doit être la première commande Streamlit)
st.set_page_config(page_title="Interpolation Pluvio", layout="centered")


@st.cache_data
def load_data(file_path_str):
    """Charge et nettoie un fichier CSV."""
    file_path = Path(file_path_str)
    if not file_path.exists():
        return None
        
    try:
        df = pd.read_csv(
            file_path,
            sep=CSV_SEPARATOR,
            decimal=CSV_DECIMAL
        )
    except Exception:
        return None

    cols_to_clean = [COL_PLUVIO_MOYENNE, COL_PLUVIO_EXCEP, COL_LAT, COL_LON]
    
    for col in cols_to_clean:
        if col in df.columns:
            # Nettoyage : conversion string -> suppression ' -> remplacement , par . -> conversion numeric
            df[col] = pd.to_numeric(
                df[col].astype(str).str.strip(" '").str.replace(',', '.'),
                errors='coerce'
            )
    
    # Suppression des lignes incomplètes
    df = df.dropna(subset=[COL_LAT, COL_LON, COL_PLUVIO_MOYENNE, COL_PLUVIO_EXCEP])
    return df


def get_interpolated_values(df, target_lat, target_lon):
    """Exécute l'interpolation sur un DataFrame."""
    if df is None or df.empty:
        return None

    try:
        points = df[[COL_LAT, COL_LON]].values
        values_moyenne = df[COL_PLUVIO_MOYENNE].values
        values_excep = df[COL_PLUVIO_EXCEP].values
        target_point = np.array([target_lat, target_lon])

        result_moyenne = griddata(
            points, values_moyenne, target_point,
            method=INTERPOLATION_METHOD, fill_value=np.nan 
        )
        result_excep = griddata(
            points, values_excep, target_point,
            method=INTERPOLATION_METHOD, fill_value=np.nan
        )
        
        return {"moyenne": result_moyenne.item(), "exceptionnelle": result_excep.item()}
        
    except Exception:
        return None


def plot_evolution(data_list, metric_key, title, y_label):
    """
    Génère un graphique Matplotlib avec droites simples et annotations optimisées.
    """
    # 1. Préparation des données
    data_list.sort(key=lambda x: x['year'])
    years = np.array([d['year'] for d in data_list])
    values = np.array([d[metric_key] for d in data_list])
    
    # Valeur de référence (la première, donc 2020)
    ref_value = values[0] if len(values) > 0 else 1 

    # Création de la figure
    fig, ax = plt.subplots(figsize=(10, 6))

    # 2. Tracer les droites
    ax.plot(years, values, color='#1f77b4', linewidth=2.5, alpha=0.8, linestyle='-', label='Tendance', zorder=1)

    # 3. Tracer les points
    ax.scatter(years, values, color='#1f77b4', s=100, zorder=5)

    # 4. Annotations intelligentes
    for x, y in zip(years, values):
        
        if x == 2020:
            text_label = f"{y:.1f}\n(Réf.)"
            font_color = 'black'
        else:
            # Calcul du %
            if ref_value != 0:
                pct = ((y - ref_value) / ref_value) * 100
            else:
                pct = 0
            
            # Couleur conditionnelle
            color_cond = 'green' if pct >= 0 else 'red'
            sign = '+' if pct >= 0 else ''
            text_label = f"{y:.1f}\n({sign}{pct:.1f}%)"
            font_color = color_cond

        # Annotation centrée au-dessus du point
        ax.annotate(
            text_label,
            xy=(x, y),
            xytext=(0, 15), # Décalage vers le haut
            textcoords='offset points',
            ha='center',
            va='bottom',
            fontsize=9,
            fontweight='bold',
            color=font_color,
            bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="none", alpha=0.6)
        )

    # 5. Esthétique et Marges
    ax.set_title(title, pad=20, fontsize=12, fontweight='bold')
    ax.set_xlabel("Horizon")
    ax.set_ylabel(y_label)
    ax.set_xticks(years)
    
    ax.grid(True, linestyle=':', alpha=0.6)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    # --- AJUSTEMENT AUTOMATIQUE DES LIMITES ---
    y_min_curr, y_max_curr = ax.get_ylim()
    y_range = y_max_curr - y_min_curr if y_max_curr != y_min_curr else 1.0
    ax.set_ylim(y_min_curr - (y_range * 0.05), y_max_curr + (y_range * 0.25))
    # ------------------------------------------

    plt.tight_layout()
    return fig


# --- PARTIE PRINCIPALE : L'INTERFACE WEB ---

st.title("🌦️ Outil d'interpolation de pluviométrie")
st.markdown("Recherchez une adresse ou cliquez sur la carte pour sélectionner un point.")

# 1. Initialiser st.session_state
if "clicked_lat" not in st.session_state:
    st.session_state.clicked_lat = None
    st.session_state.clicked_lon = None
    st.session_state.center = [46.2276, 2.2137]
    st.session_state.zoom = 6

# --- NOUVEAU : BARRE DE RECHERCHE ---
col_search, col_btn = st.columns([3, 1])
with col_search:
    address_search = st.text_input("Rechercher une ville / adresse :", placeholder="Ex: Bordeaux, France")
with col_btn:
    # On ajoute un espace vide pour aligner le bouton avec le champ texte
    st.write("") 
    st.write("")
    if st.button("🔎 Rechercher"):
        if address_search:
            with st.spinner("Recherche de l'adresse..."):
                try:
                    # Initialisation du géocodeur Nominatim
                    geolocator = Nominatim(user_agent="pluvio_app_streamlit")
                    # Ajout d'un timeout de 10 secondes pour éviter les erreurs de lecture
                    location = geolocator.geocode(address_search, timeout=10)
                    
                    if location:
                        # Mise à jour de l'état avec les nouvelles coordonnées
                        st.session_state.clicked_lat = location.latitude
                        st.session_state.clicked_lon = location.longitude
                        st.session_state.center = [location.latitude, location.longitude]
                        st.session_state.zoom = 12 # Zoom plus proche sur la ville trouvée
                        st.success(f"Adresse trouvée : {location.address}")
                        # Pas besoin de rerun ici, Streamlit va redessiner la carte avec les nouvelles valeurs du session_state
                    else:
                        st.error("Adresse introuvable. Essayez d'être plus précis.")
                except Exception as e:
                    st.error(f"Erreur de connexion au service de géocodage : {e}")
# ------------------------------------

# 2. Créer la carte Folium
m = folium.Map(
    location=st.session_state.center, 
    zoom_start=st.session_state.zoom,
    tiles="OpenStreetMap"
)

# Ajout du repère si un point a été cliqué ou trouvé par recherche
if st.session_state.clicked_lat is not None:
    folium.Marker(
        location=[st.session_state.clicked_lat, st.session_state.clicked_lon],
        popup=f"Lat: {st.session_state.clicked_lat:.4f}, Lon: {st.session_state.clicked_lon:.4f}",
        icon=folium.Icon(color="red", icon="info-sign")
    ).add_to(m)

# 3. Afficher la carte et capturer le clic
map_data = st_folium(m, key="folium_map", width=700, height=500)

# 4. Traiter le clic sur la carte
if map_data and map_data.get("last_clicked"):
    st.session_state.clicked_lat = map_data["last_clicked"]["lat"]
    st.session_state.clicked_lon = map_data["last_clicked"]["lng"]
    st.session_state.center = [map_data["last_clicked"]["lat"], map_data["last_clicked"]["lng"]]
    st.session_state.zoom = 10 # Zoom intermédiaire au clic
    st.rerun()

# 5. Feedback utilisateur
if st.session_state.clicked_lat:
    st.info(f"📍 Point sélectionné : Latitude = {st.session_state.clicked_lat:.4f}, Longitude = {st.session_state.clicked_lon:.4f}")
else:
    st.info("Veuillez rechercher une adresse ou cliquer sur la carte.")

# 6. Bouton de calcul
if st.button("Calculer les estimations et afficher les graphiques", type="primary"):
    
    if st.session_state.clicked_lat is None:
        st.warning("Veuillez d'abord sélectionner un point (Recherche ou Clic).")
    else:
        user_lat = st.session_state.clicked_lat
        user_lon = st.session_state.clicked_lon
        
        # Liste pour stocker les données pour les graphiques
        plot_data = []
        
        with st.spinner("Calcul en cours..."):
            st.subheader(f"Résultats pour (Lat={user_lat:.4f}, Lon={user_lon:.4f})")
            
            sorted_horizons = sorted(FILES_TO_PROCESS.keys())
            all_success = True
            
            for horizon in sorted_horizons:
                filename = FILES_TO_PROCESS[horizon]
                display_title = f"Horizon {horizon}" if horizon != "2020" else "Historique (2020)"
                st.write(f"--- {display_title} ---")
                
                df_data = load_data(filename)
                
                if df_data is not None:
                    data = get_interpolated_values(df_data, user_lat, user_lon)
                    if data:
                        if np.isnan(data["moyenne"]):
                            st.warning("Extrapolation impossible (hors zone).")
                        else:
                            st.success(f"PLUVIOMETRIE moyenne  : **{data['moyenne']:.2f}** mm")
                            st.info(f"PLUVIO EXCEPTIONNELLE : **{data['exceptionnelle']:.2f}** mm")
                            
                            plot_data.append({
                                'year': int(horizon),
                                'moyenne': data['moyenne'],
                                'exceptionnelle': data['exceptionnelle']
                            })
                    else:
                        st.error("Erreur de calcul.")
                        all_success = False
                else:
                    st.error(f"Fichier introuvable : {filename}")
                    all_success = False

        # --- Affichage des graphiques ---
        if all_success and len(plot_data) > 0:
            st.markdown("---")
            st.subheader("📈 Évolution temporelle (Tendances)")
            
            col1, col2 = st.columns(2)
            
            with col1:
                fig1 = plot_evolution(
                    plot_data, 
                    'moyenne', 
                    "Pluviométrie Moyenne", 
                    "Pluviométrie (mm)"
                )
                st.pyplot(fig1, use_container_width=True)
            
            with col2:
                fig2 = plot_evolution(
                    plot_data, 
                    'exceptionnelle', 
                    "Pluviométrie Exceptionnelle", 
                    "Pluviométrie (mm)"
                )
                st.pyplot(fig2, use_container_width=True)
            
            st.balloons()
