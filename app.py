import streamlit as st
import pandas as pd
from scipy.interpolate import griddata
import numpy as np
from pathlib import Path
import folium
from streamlit_folium import st_folium
import matplotlib.pyplot as plt

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


@st.cache_data
def load_data(file_path_str):
    """Charge et nettoie un fichier CSV."""
    file_path = Path(file_path_str)
    if not file_path.exists():
        # On retourne None silencieusement ici, l'erreur sera gérée dans la boucle principale
        return None
        
    try:
        df = pd.read_csv(
            file_path,
            sep=CSV_SEPARATOR,
            decimal=CSV_DECIMAL
        )
    except Exception:
        return None

    # Liste des colonnes à nettoyer
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
        
    except Exception:
        return None


def plot_evolution(data_list, metric_key, title, y_label):
    """
    Génère un graphique Matplotlib avec les % d'évolution.
    """
    # Trier par année (clé 'year')
    data_list.sort(key=lambda x: x['year'])
    
    years = [d['year'] for d in data_list]
    values = [d[metric_key] for d in data_list]
    
    # La référence est la première valeur (2020)
    ref_value = values[0] if values else 1 

    fig, ax = plt.subplots(figsize=(10, 5))
    
    # Tracer la ligne et les points
    ax.plot(years, values, marker='o', linestyle='-', color='#1f77b4', linewidth=2, markersize=8)
    
    # Ajouter les annotations
    for x, y in zip(years, values):
        # Décalage vertical pour le texte
        offset = y * 0.02 
        
        if x == 2020:
            # Pour l'historique 2020
            ax.text(x, y + offset, f"{y:.1f}\n(Réf.)", ha='center', va='bottom', fontsize=9, fontweight='bold', color='black')
        else:
            # Calcul du pourcentage d'évolution par rapport à la référence (2020)
            if ref_value != 0:
                pct = ((y - ref_value) / ref_value) * 100
            else:
                pct = 0
            
            # Couleur conditionnelle (Vert si positif, Rouge si négatif)
            color = 'green' if pct >= 0 else 'red'
            sign = '+' if pct >= 0 else ''
            
            label = f"{y:.1f}\n({sign}{pct:.1f}%)"
            
            # Affichage du texte
            ax.text(x, y + offset, label, ha='center', va='bottom', 
                    color=color, fontsize=9, fontweight='bold')

    ax.set_title(title)
    ax.set_xlabel("Horizon")
    ax.set_ylabel(y_label)
    
    # Définir les ticks de l'axe X pour n'afficher que nos années
    ax.set_xticks(years)
    
    ax.grid(True, linestyle='--', alpha=0.6)
    
    # Marges automatiques
    plt.tight_layout()
    
    return fig


# --- PARTIE PRINCIPALE : L'INTERFACE WEB ---

st.set_page_config(page_title="Interpolation Pluvio", layout="centered")
st.title("🌦️ Outil d'interpolation de pluviométrie")
st.markdown("Cliquez sur la carte pour sélectionner un point, puis cliquez sur 'Calculer'.")

# 1. Initialiser st.session_state
if "clicked_lat" not in st.session_state:
    st.session_state.clicked_lat = None
    st.session_state.clicked_lon = None
    st.session_state.center = [46.2276, 2.2137]
    st.session_state.zoom = 6

# 2. Créer la carte Folium
m = folium.Map(
    location=st.session_state.center, 
    zoom_start=st.session_state.zoom,
    tiles="OpenStreetMap"
)

# 2.5. Ajouter un repère si un point a été cliqué
if st.session_state.clicked_lat is not None:
    folium.Marker(
        location=[st.session_state.clicked_lat, st.session_state.clicked_lon],
        popup=f"Lat: {st.session_state.clicked_lat:.4f}, Lon: {st.session_state.clicked_lon:.4f}",
        icon=folium.Icon(color="red", icon="info-sign")
    ).add_to(m)

# 3. Afficher la carte et capturer le clic
map_data = st_folium(m, key="folium_map", width=700, height=500)

# 4. Traiter le clic
if map_data and map_data.get("last_clicked"):
    st.session_state.clicked_lat = map_data["last_clicked"]["lat"]
    st.session_state.clicked_lon = map_data["last_clicked"]["lng"]
    st.session_state.center = [map_data["last_clicked"]["lat"], map_data["last_clicked"]["lng"]]
    st.session_state.zoom = 10
    st.rerun()

# 5. Feedback utilisateur
if st.session_state.clicked_lat:
    st.info(f"Point sélectionné : Latitude = {st.session_state.clicked_lat:.4f}, Longitude = {st.session_state.clicked_lon:.4f}")
else:
    st.info("Veuillez cliquer sur la carte pour sélectionner un point.")

# 6. Bouton de calcul
if st.button("Calculer les estimations et afficher les graphiques"):
    
    if st.session_state.clicked_lat is None:
        st.warning("Veuillez d'abord cliquer sur la carte.")
    else:
        user_lat = st.session_state.clicked_lat
        user_lon = st.session_state.clicked_lon
        
        # Liste pour stocker les données pour les futurs graphiques
        plot_data = []
        
        with st.spinner("Calcul en cours..."):
            st.subheader(f"Résultats pour (Lat={user_lat:.4f}, Lon={user_lon:.4f})")
            
            # On trie les clés (2020, 2030, etc.) pour afficher dans l'ordre
            sorted_horizons = sorted(FILES_TO_PROCESS.keys())
            
            all_success = True
            
            for horizon in sorted_horizons:
                filename = FILES_TO_PROCESS[horizon]
                
                # Petit affichage esthétique pour différencier 2020 des autres
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
                            
                            # On ajoute les données à la liste pour les graphiques
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

        # --- Affichage des graphiques en bas de page ---
        if all_success and len(plot_data) > 0:
            st.markdown("---")
            st.subheader("📈 Évolution temporelle")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.write("### Pluviométrie Moyenne")
                fig1 = plot_evolution(
                    plot_data, 
                    'moyenne', 
                    "Évolution Pluviométrie Moyenne", 
                    "Pluviométrie (mm)"
                )
                st.pyplot(fig1)
            
            with col2:
                st.write("### Pluviométrie Exceptionnelle")
                fig2 = plot_evolution(
                    plot_data, 
                    'exceptionnelle', 
                    "Évolution Pluviométrie Exceptionnelle", 
                    "Pluviométrie (mm)"
                )
                st.pyplot(fig2)
            
            st.balloons()
