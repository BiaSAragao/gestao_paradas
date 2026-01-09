import os
import streamlit as st
import pandas as pd
import folium
from sqlalchemy import create_engine, Column, Integer, String, Numeric, Text, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session
from datetime import datetime
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim
from streamlit_js_eval import streamlit_js_eval

# --- CONFIGURAÇÃO DO BANCO DE DADOS ---
DATABASE_URL = st.secrets.get("DATABASE_URL") or os.getenv("DATABASE_URL")

if not DATABASE_URL:
    st.error("⚠️ Erro: URL do banco de dados não configurada.")
    st.stop()

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL, echo=False, future=True, pool_pre_ping=True)
SessionLocal = scoped_session(sessionmaker(bind=engine, autoflush=False, autocommit=False))
Base = declarative_base()

class Parada(Base):
    __tablename__ = "paradas"
    id = Column(Integer, primary_key=True)
    numero_parada = Column(String(50), unique=True)
    rua = Column(String(255), nullable=False)
    numero_localizacao = Column(String(20))
    bairro = Column(String(100), nullable=False)
    cep = Column(String(10))
    ponto_referencia = Column(Text)
    sentido = Column(String(20))
    tipo = Column(String(50))
    latitude = Column(Numeric(10, 8))
    longitude = Column(Numeric(11, 8))
    foto_url = Column(Text)
    data_cadastro = Column(DateTime, default=datetime.now)

Base.metadata.create_all(bind=engine)
geolocator = Nominatim(user_agent="sipo_semob_fsa_v4")

st.set_page_config(page_title="SIP - SEMOB FSA", layout="wide", page_icon="🚌")

# --- ESTILIZAÇÃO PARA EVITAR PISCADAS ---
st.markdown("<style>#MainMenu {visibility: hidden;} footer {visibility: hidden;}</style>", unsafe_allow_html=True)

st.title("🚌 SIP - Sistema de Inventário de Paradas")
st.caption("Gestão de Ativos - Feira de Santana")

tab1, tab2 = st.tabs(["📝 Cadastrar Parada", "📍 Visualizar Mapa e Dados"])
db = SessionLocal()

# --- ABA 1: CADASTRO ---
with tab1:
    # Inicialização do Session State
    if 'lat_input' not in st.session_state: st.session_state.lat_input = -12.250000
    if 'lon_input' not in st.session_state: st.session_state.lon_input = -38.950000
    if 'form_data' not in st.session_state:
        st.session_state.form_data = {'rua': '', 'bairro': '', 'num': '', 'cep': '', 'id': ''}

    st.markdown("### 🗺️ Localização e GPS")
    
    # Captura GPS em segundo plano
    loc_data = streamlit_js_eval(js_expressions='navigator.geolocation.getCurrentPosition(pos => { return pos.coords; })', key='gps_capture')

    col_btn, col_txt = st.columns([1, 2])
    with col_btn:
        if st.button("📍 USAR MINHA POSIÇÃO ATUAL", use_container_width=True, type="primary"):
            if loc_data:
                st.session_state.lat_input = loc_data['latitude']
                st.session_state.lon_input = loc_data['longitude']
                try:
                    rev = geolocator.reverse(f"{st.session_state.lat_input}, {st.session_state.lon_input}", timeout=5)
                    if rev:
                        addr = rev.raw.get('address', {})
                        st.session_state.form_data['rua'] = addr.get('road', addr.get('street', ''))
                        st.session_state.form_data['bairro'] = addr.get('suburb', addr.get('neighbourhood', ''))
                        st.session_state.form_data['num'] = addr.get('house_number', '')
                        st.session_state.form_data['cep'] = addr.get('postcode', '')
                        st.rerun()
                except: pass
            else:
                st.warning("Aguardando sinal GPS...")

    # --- FRAGMENTO DO MAPA (Para não recarregar a página toda) ---
    @st.fragment
    def render_mapa():
        m_cad = folium.Map(
            location=[st.session_state.lat_input, st.session_state.lon_input], 
            zoom_start=19,
            tiles="https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}",
            attr="Google Satellite"
        )
        folium.Marker([st.session_state.lat_input, st.session_state.lon_input], icon=folium.Icon(color="red", icon="bus", prefix="fa")).add_to(m_cad)
        
        map_out = st_folium(m_cad, height=350, width=None, key="mapa_cadastro", returned_objects=["last_clicked"])

        if map_out and map_out.get("last_clicked"):
            click_lat = map_out["last_clicked"]["lat"]
            click_lon = map_out["last_clicked"]["lng"]
            if click_lat != st.session_state.lat_input:
                st.session_state.lat_input = click_lat
                st.session_state.lon_input = click_lon
                try:
                    rev = geolocator.reverse(f"{click_lat}, {click_lon}")
                    if rev:
                        addr = rev.raw.get('address', {})
                        st.session_state.form_data['rua'] = addr.get('road', '')
                        st.session_state.form_data['bairro'] = addr.get('suburb', '')
                        st.session_state.form_data['num'] = addr.get('house_number', '')
                        st.session_state.form_data['cep'] = addr.get('postcode', '')
                except: pass
                st.rerun()

    render_mapa()

    st.markdown("---")
    
    # --- FORMULÁRIO ---
    with st.form("cadastro_parada", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### 📍 Endereço")
            id_p = st.text_input("ID da Parada*", value=st.session_state.form_data['id'])
            rua_p = st.text_input("Rua*", value=st.session_state.form_data['rua'])
            num_p = st.text_input("Número", value=st.session_state.form_data['num'])
            bairro_p = st.text_input("Bairro*", value=st.session_state.form_data['bairro'])
            cep_p = st.text_input("CEP", value=st.session_state.form_data['cep'])
            ref_p = st.text_area("Ponto de Referência")
            
        with col2:
            st.markdown("#### 🏗️ Técnica")
            tipo_p = st.selectbox("Tipo*", ["Placa", "Abrigo", "Abrigo + Placa"])
            sentido_p = st.selectbox("Sentido*", ["PC1 - PC2", "PC2 - PC1"])
            st.write(f"📌 **Lat:** {st.session_state.lat_input:.6f}")
            st.write(f"📌 **Lon:** {st.session_state.lon_input:.6f}")
            foto = st.file_uploader("Foto", type=['jpg', 'jpeg', 'png'])

        submit = st.form_submit_button("💾 SALVAR REGISTRO", use_container_width=True, type="primary")

        if submit:
            if not id_p or not rua_p or not bairro_p:
                st.error("Campos obrigatórios faltando!")
            else:
                try:
                    nova = Parada(
                        numero_parada=id_p, rua=rua_p, numero_localizacao=num_p,
                        bairro=bairro_p, cep=cep_p, ponto_referencia=ref_p,
                        sentido=sentido_p, tipo=tipo_p, latitude=st.session_state.lat_input,
                        longitude=st.session_state.lon_input, foto_url=foto.name if foto else "sem_foto.jpg"
                    )
                    db.add(nova)
                    db.commit()
                    st.success("✅ Salvo!")
                    st.balloons()
                except Exception as e:
                    db.rollback()
                    st.error(f"Erro: {e}")

# --- ABA 2: VISUALIZAÇÃO ---
with tab2:
    st.subheader("📊 Inventário")
    todas = db.query(Parada).order_by(Parada.data_cadastro.desc()).all()
    if todas:
        df = pd.DataFrame([{
            "ID": p.numero_parada, "Rua": p.rua, "Bairro": p.bairro,
            "LAT": float(p.latitude), "LON": float(p.longitude)
        } for p in todas])
        
        m_view = folium.Map(location=[df['LAT'].mean(), df['LON'].mean()], zoom_start=14)
        for _, r in df.iterrows():
            folium.Marker([r['LAT'], r['LON']], popup=r['ID']).add_to(m_view)
        
        st_folium(m_view, height=500, width=None, key="mapa_view")
        st.dataframe(df, use_container_width=True)

db.close()
