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
# Tenta pegar primeiro do Streamlit Secrets, depois do Ambiente (terminal)
DATABASE_URL = st.secrets.get("DATABASE_URL") or os.getenv("DATABASE_URL")

if not DATABASE_URL:
    st.error("⚠️ Erro: A URL do banco de dados não foi configurada nos Secrets.")
    st.stop()

# Garante que o link comece com postgresql:// (obrigatório para SQLAlchemy)
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

try:
    engine = create_engine(DATABASE_URL, echo=False, future=True)
    # Tenta conectar rápido para ver se a URL é válida
    with engine.connect() as conn:
        pass
except Exception as e:
    st.error(f"❌ Erro de Conexão: A URL fornecida é inválida ou o banco recusou a conexão.")
    st.stop()

engine = create_engine(DATABASE_URL, echo=False, future=True)
SessionLocal = scoped_session(sessionmaker(bind=engine, autoflush=False, autocommit=False))
Base = declarative_base()

# --- MODELO DA TABELA ---
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
geolocator = Nominatim(user_agent="sipo_semob_fsa_v3")

# --- INTERFACE ---
st.set_page_config(page_title="SIP - SEMOB FSA", layout="wide", page_icon="🚌")

st.title("🚌 SIP - Sistema de Inventário de Paradas")
st.caption("Gestão de Ativos de Mobilidade Urbana - Feira de Santana")

tab1, tab2 = st.tabs(["📝 Cadastrar Parada", "📍 Visualizar Mapa e Dados"])
db = SessionLocal()

# --- ABA 1: CADASTRO ---
with tab1:
    # Inicialização do Session State para persistência de dados
    if 'lat_input' not in st.session_state: st.session_state.lat_input = -12.250000
    if 'lon_input' not in st.session_state: st.session_state.lon_input = -38.950000
    for field in ['rua_input', 'bairro_input', 'num_input', 'cep_input']:
        if field not in st.session_state: st.session_state[field] = ""

    st.markdown("### 🗺️ Localização e GPS")
    
    # Captura GPS em Tempo Real
    loc_data = streamlit_js_eval(js_expressions='navigator.geolocation.getCurrentPosition(pos => { return pos.coords; })', key='gps_capture')

    col_gps, col_ajuda = st.columns([1, 2])
    with col_gps:
        if st.button("📍 CAPTURAR MINHA LOCALIZAÇÃO ATUAL", use_container_width=True, type="primary"):
            if loc_data:
                st.session_state.lat_input = loc_data['latitude']
                st.session_state.lon_input = loc_data['longitude']
                try:
                    rev = geolocator.reverse(f"{st.session_state.lat_input}, {st.session_state.lon_input}", timeout=10)
                    if rev:
                        addr = rev.raw.get('address', {})
                        st.session_state.rua_input = addr.get('road', addr.get('street', ''))
                        st.session_state.bairro_input = addr.get('suburb', addr.get('neighbourhood', ''))
                        st.session_state.num_input = addr.get('house_number', '')
                        st.session_state.cep_input = addr.get('postcode', '')
                        st.rerun()
                except: pass
            else:
                st.warning("Aguardando permissão de GPS do navegador...")

    # Mapa para ajuste fino (Satélite)
    m_cad = folium.Map(
        location=[st.session_state.lat_input, st.session_state.lon_input], 
        zoom_start=19,
        tiles="https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}",
        attr="Google Satellite"
    )
    folium.Marker([st.session_state.lat_input, st.session_state.lon_input], icon=folium.Icon(color="red", icon="bus", prefix="fa")).add_to(m_cad)
    
    map_output = st_folium(m_cad, height=350, width=None, key="mapa_cadastro")

    if map_output["last_clicked"]:
        st.session_state.lat_input = map_output["last_clicked"]["lat"]
        st.session_state.lon_input = map_output["last_clicked"]["lng"]
        try:
            rev = geolocator.reverse(f"{st.session_state.lat_input}, {st.session_state.lon_input}")
            if rev:
                addr = rev.raw.get('address', {})
                st.session_state.rua_input = addr.get('road', addr.get('street', ''))
                st.session_state.bairro_input = addr.get('suburb', addr.get('neighbourhood', ''))
                st.session_state.num_input = addr.get('house_number', '')
                st.session_state.cep_input = addr.get('postcode', '')
                st.rerun()
        except: pass

    st.markdown("---")
    
    # Formulário de Cadastro
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### 📍 Informações de Endereço")
        id_parada = st.text_input("Número/ID da Parada*", placeholder="Ex: PA-101")
        rua = st.text_input("Rua/Avenida*", value=st.session_state.rua_input)
        num_loc = st.text_input("Número aproximado", value=st.session_state.num_input)
        bairro = st.text_input("Bairro*", value=st.session_state.bairro_input)
        cep = st.text_input("CEP", value=st.session_state.cep_input)
        ponto_ref = st.text_area("Ponto de Referência")
        
    with col2:
        st.markdown("### 🏗️ Características Técnicas")
        tipo = st.selectbox("Tipo de Mobiliário*", ["Placa", "Abrigo", "Abrigo + Placa"])
        sentido = st.selectbox("Sentido*", ["PC1 - PC2", "PC2 - PC1"])
        st.info(f"📍 Latitude: {st.session_state.lat_input:.7f}\n\n📍 Longitude: {st.session_state.lon_input:.7f}")
        foto = st.file_uploader("Capturar Foto", type=['jpg', 'png', 'jpeg'])

    if st.button("💾 FINALIZAR E SALVAR REGISTRO", type="primary", use_container_width=True):
        if not id_parada or not rua or not bairro:
            st.error("❌ Preencha os campos obrigatórios (ID, Rua e Bairro).")
        else:
            try:
                nova_parada = Parada(
                    numero_parada=id_parada, rua=rua, numero_localizacao=num_loc,
                    bairro=bairro, cep=cep, ponto_referencia=ponto_ref,
                    sentido=sentido, tipo=tipo, latitude=st.session_state.lat_input,
                    longitude=st.session_state.lon_input,
                    foto_url=foto.name if foto else "sem_foto.jpg"
                )
                db.add(nova_parada)
                db.commit()
                st.success(f"✅ Parada {id_parada} salva com sucesso!")
                st.balloons()
                
                # Reset para novo cadastro
                for f in ['rua_input', 'bairro_input', 'num_input', 'cep_input']: st.session_state[f] = ""
                st.rerun()
            except Exception as e:
                db.rollback()
                st.error(f"Erro ao salvar: {e}")

# --- ABA 2: VISUALIZAÇÃO ---
with tab2:
    st.subheader("📊 Inventário Georreferenciado")
    todas = db.query(Parada).order_by(Parada.data_cadastro.desc()).all()
    if todas:
        df = pd.DataFrame([{
            "ID": p.numero_parada, "Bairro": p.bairro, "Rua": p.rua,
            "Tipo": p.tipo, "Sentido": p.sentido, "LAT": float(p.latitude), "LON": float(p.longitude)
        } for p in todas])
        
        m_view = folium.Map(location=[df['LAT'].mean(), df['LON'].mean()], zoom_start=15)
        for _, r in df.iterrows():
            folium.Marker([r['LAT'], r['LON']], popup=f"Parada {r['ID']}").add_to(m_view)
        
        st_folium(m_view, height=500, width=None, key="mapa_view")
        st.dataframe(df, use_container_width=True)
    else:
        st.info("Ainda não há paradas cadastradas.")


db.close()

