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

# ================== FUNÇÕES AUXILIARES ==================
def normalizar_texto(txt):
    if not txt:
        return ""
    return txt.strip().title()

def extrair_endereco(addr):
    return {
        "rua": addr.get("road")
               or addr.get("street")
               or addr.get("pedestrian")
               or "",
        "num": addr.get("house_number", ""),
        "bairro": addr.get("suburb")
                  or addr.get("neighbourhood")
                  or addr.get("quarter")
                  or "",
        "cep": addr.get("postcode", "")
    }

# ================== CONFIG BANCO ==================
DATABASE_URL = st.secrets.get("DATABASE_URL") or os.getenv("DATABASE_URL")

if not DATABASE_URL:
    st.error("⚠️ URL do banco não configurada.")
    st.stop()

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL, echo=False, future=True, pool_pre_ping=True)
SessionLocal = scoped_session(sessionmaker(bind=engine, autoflush=False, autocommit=False))
Base = declarative_base()

class Parada(Base):
    __tablename__ = "paradas"
    id = Column(Integer, primary_key=True)
    numero_parada = Column(String(50), unique=True, nullable=True)
    rua = Column(String(255), nullable=False)
    numero_localizacao = Column(String(20))
    bairro = Column(String(100), nullable=False)
    cep = Column(String(10))
    ponto_referencia = Column(Text, nullable=False)
    sentido = Column(String(20))
    tipo = Column(String(50))
    latitude = Column(Numeric(10, 8))
    longitude = Column(Numeric(11, 8))
    foto_url = Column(Text)
    data_cadastro = Column(DateTime, default=datetime.now)

Base.metadata.create_all(bind=engine)
db = SessionLocal()

geolocator = Nominatim(user_agent="sipo_semob_fsa_v6")

# ================== STREAMLIT ==================
st.set_page_config(
    page_title="SIP - SEMOB FSA",
    layout="wide",
    page_icon="🚌"
)

if "msg_sucesso" not in st.session_state:
    st.session_state.msg_sucesso = None

st.markdown(
    "<style>#MainMenu{visibility:hidden;} footer{visibility:hidden;}</style>",
    unsafe_allow_html=True
)

st.title("🚌 SIP - Sistema de Inventário de Paradas")
st.caption("Gestão de Ativos - Feira de Santana")

tab1, tab2, tab3, tab4 = st.tabs([
    "📝 Cadastrar Parada",
    "📍 Visualizar Mapa e Dados",
    "📊 Dashboard",
    "✏️ Editar / Excluir"
])


# ================== SESSION STATE ==================
if "lat_input" not in st.session_state:
    st.session_state.lat_input = -12.250000
if "lon_input" not in st.session_state:
    st.session_state.lon_input = -38.950000
if "form_data" not in st.session_state:
    st.session_state.form_data = {
        "rua": "", "bairro": "", "num": "", "cep": "", "id": ""
    }

# ==================================================
# ================= ABA 1 - CADASTRO ================
# ==================================================
with tab1:
    st.subheader("🗺️ Localização e GPS")

    loc_data = streamlit_js_eval(
        js_expressions="""
        new Promise((resolve) => {
            navigator.geolocation.getCurrentPosition(
                (pos) => resolve({
                    latitude: pos.coords.latitude,
                    longitude: pos.coords.longitude
                }),
                () => resolve(null)
            );
        })
        """,
        key="gps_capture"
    )

    if st.button("📍 USAR MINHA POSIÇÃO ATUAL", type="primary", use_container_width=True):
        if loc_data:
            st.session_state.lat_input = loc_data["latitude"]
            st.session_state.lon_input = loc_data["longitude"]
            st.rerun()
        else:
            st.warning("Permita o acesso à localização no navegador.")

    @st.fragment
    def render_mapa_cadastro():
        m = folium.Map(
            location=[st.session_state.lat_input, st.session_state.lon_input],
            zoom_start=19,
            tiles="https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}",
            attr="Google Satellite"
        )

        folium.Marker(
            [st.session_state.lat_input, st.session_state.lon_input],
            icon=folium.Icon(color="red", icon="bus", prefix="fa")
        ).add_to(m)

        out = st_folium(
            m,
            height=420,
            use_container_width=True,
            key="mapa_cadastro",
            returned_objects=["last_clicked"]
        )

        if out and out.get("last_clicked"):
            lat = out["last_clicked"]["lat"]
            lon = out["last_clicked"]["lng"]

            if lat != st.session_state.lat_input:
                st.session_state.lat_input = lat
                st.session_state.lon_input = lon
                try:
                    rev = geolocator.reverse(f"{lat}, {lon}", timeout=5)
                    if rev:
                        dados = extrair_endereco(rev.raw.get("address", {}))
                        st.session_state.form_data["rua"] = normalizar_texto(dados["rua"])
                        st.session_state.form_data["bairro"] = normalizar_texto(dados["bairro"])
                        st.session_state.form_data["num"] = dados["num"]
                        st.session_state.form_data["cep"] = dados["cep"]
                except:
                    pass
                st.rerun()

    render_mapa_cadastro()
    st.divider()

    with st.form("cadastro_parada", clear_on_submit=True):
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("#### 📍 Endereço")
            id_p = st.text_input("Número da Parada (opcional)", st.session_state.form_data["id"])
            rua_p = st.text_input("Rua*", st.session_state.form_data["rua"])
            num_p = st.text_input("Número (opcional)", st.session_state.form_data["num"])
            bairro_p = st.text_input("Bairro*", st.session_state.form_data["bairro"])
            cep_p = st.text_input("CEP (opcional)", st.session_state.form_data["cep"])
            ref_p = st.text_area("Ponto de Referência*")

        with col2:
            st.markdown("#### 🏗️ Técnica")
            tipo_p = st.selectbox(
                "Tipo*",
                ["Placa", "Abrigo", "Abrigo + Placa", "Sem Identificação"]
            )

            sentido_p = st.selectbox("Sentido*", ["PC1 - PC2", "PC2 - PC1"])
            st.write(f"📌 Lat: {st.session_state.lat_input:.6f}")
            st.write(f"📌 Lon: {st.session_state.lon_input:.6f}")
            foto = st.file_uploader("Foto", type=["jpg", "jpeg", "png"])

        submit = st.form_submit_button("💾 SALVAR REGISTRO", type="primary", use_container_width=True)

        if submit:
            if not rua_p or not bairro_p or not ref_p or not tipo_p or not sentido_p:
                st.error("⚠️ Campos obrigatórios não preenchidos.")
            else:
                try:
                    nova = Parada(
                        numero_parada=id_p if id_p.strip() else None,
                        rua=rua_p,
                        numero_localizacao=num_p if num_p.strip() else None,
                        bairro=bairro_p,
                        cep=cep_p if cep_p.strip() else None,
                        ponto_referencia=ref_p,
                        sentido=sentido_p,
                        tipo=tipo_p,
                        latitude=st.session_state.lat_input,
                        longitude=st.session_state.lon_input,
                        foto_url=foto.name if foto else "sem_foto.jpg"
                    )


                    db.add(nova)
                    db.commit()
                    st.success("✅ Parada cadastrada com sucesso!")
                    st.balloons()
                except Exception as e:
                    db.rollback()
                    st.error(f"Erro ao salvar: {e}")

# ==================================================
# ================= ABA 2 - VISUALIZAÇÃO ============
# ==================================================
@st.cache_data(ttl=30)
def carregar_paradas():
    return db.query(Parada).order_by(Parada.data_cadastro.desc()).all()

with tab2:
    st.subheader("📊 Inventário de Paradas")

    todas = carregar_paradas()

    if todas:
        df = pd.DataFrame([{
            "ID": p.numero_parada,
            "Rua": normalizar_texto(p.rua),
            "Bairro": normalizar_texto(p.bairro),
            "LAT": float(p.latitude),
            "LON": float(p.longitude)
        } for p in todas])

        st.markdown("### 🔎 Filtros")
        c1, c2 = st.columns(2)

        with c1:
            filtro_bairro = st.multiselect(
                "Bairro",
                sorted(df["Bairro"].dropna().unique())
            )

        with c2:
            filtro_rua = st.text_input("Rua")

        df_f = df.copy()

        if filtro_bairro:
            df_f = df_f[df_f["Bairro"].isin(filtro_bairro)]

        if filtro_rua:
            df_f = df_f[df_f["Rua"].str.contains(filtro_rua, case=False, na=False)]

        @st.fragment
        def render_mapa_view(df_map):
            m = folium.Map(
                location=[df_map["LAT"].mean(), df_map["LON"].mean()],
                zoom_start=14
            )
            for _, r in df_map.iterrows():
                folium.Marker(
                    [r["LAT"], r["LON"]],
                    popup=f"Parada {r['ID']}"
                ).add_to(m)

            st_folium(m, height=550, use_container_width=True, key="mapa_view")

        render_mapa_view(df_f)
        st.dataframe(df_f, use_container_width=True)

    else:
        st.info("Nenhuma parada cadastrada.")

# ==================================================
# ================= ABA 3 - DASHBOARD ===============
# ==================================================
with tab3:
    st.subheader("📊 Dashboard e Quantitativos")

    todas = carregar_paradas()

    if not todas:
        st.info("Nenhuma parada cadastrada ainda.")
    else:
        df = pd.DataFrame([{
            "Rua": normalizar_texto(p.rua),
            "Bairro": normalizar_texto(p.bairro),
            "Tipo": p.tipo
        } for p in todas])

        # ================= INDICADORES =================
        c1, c2, c3 = st.columns(3)
        c1.metric("🚌 Total de Paradas", len(df))
        c2.metric("🏘️ Bairros Atendidos", df["Bairro"].nunique())
        c3.metric("🛣️ Ruas / Avenidas", df["Rua"].nunique())

        st.divider()

        # ================= PARADAS POR BAIRRO (DONUT) =================
        st.markdown("### 📍 Paradas por Bairro")

        bairro_counts = (
            df["Bairro"]
            .value_counts()
            .reset_index()
        )
        bairro_counts.columns = ["Bairro", "Quantidade"]

        donut_spec = {
            "data": {"values": bairro_counts.to_dict(orient="records")},
            "mark": {"type": "arc", "innerRadius": 70},
            "encoding": {
                "theta": {"field": "Quantidade", "type": "quantitative"},
                "color": {"field": "Bairro", "type": "nominal"},
                "tooltip": [
                    {"field": "Bairro", "type": "nominal"},
                    {"field": "Quantidade", "type": "quantitative"}
                ]
            }
        }

        st.vega_lite_chart(donut_spec, use_container_width=True)

        st.divider()

        # ================= TOP 10 RUAS =================
        st.markdown("### 🏆 Top 10 Ruas/Avenidas com Mais Paradas")

        top_ruas = (
            df["Rua"]
            .value_counts()
            .head(10)
            .reset_index()
        )
        top_ruas.columns = ["Rua/Avenida", "Quantidade"]

        max_qtd = top_ruas["Quantidade"].max()

        for i, row in top_ruas.iterrows():
            st.markdown(f"**{i+1}º — {row['Rua/Avenida']}** ({row['Quantidade']})")
            st.progress(row["Quantidade"] / max_qtd)

        st.divider()

        # ================= TIPO DE PARADA =================
        st.markdown("### 🏗️ Tipologia das Paradas")

        tipo_counts = (
            df["Tipo"]
            .value_counts()
            .reset_index()
        )
        tipo_counts.columns = ["Tipo", "Quantidade"]

        st.bar_chart(
            tipo_counts.set_index("Tipo")
        )

# ==================================================
# ================= ABA 4 - EDITAR / EXCLUIR ========
# ==================================================
with tab4:
    st.subheader("✏️ Editar ou Excluir Parada")

    if st.session_state.msg_sucesso:
        st.success(st.session_state.msg_sucesso)
        st.session_state.msg_sucesso = None


    todas = carregar_paradas()

    if not todas:
        st.info("Nenhuma parada cadastrada.")
    else:
        df_sel = pd.DataFrame([{
            "ID_DB": p.id,
            "ID Parada": p.numero_parada or "Sem identificação",
            "Rua": p.rua,
            "Bairro": p.bairro
        } for p in todas])

        escolha = st.selectbox(
            "Selecione a parada",
            df_sel.index,
            format_func=lambda i: f"{df_sel.loc[i,'ID Parada']} — {df_sel.loc[i,'Rua']} ({df_sel.loc[i,'Bairro']})"
        )

        parada_id = int(df_sel.loc[escolha, "ID_DB"])
        parada = db.get(Parada, parada_id)

        st.divider()

        # ---------- FORMULÁRIO DE EDIÇÃO ----------
        with st.form("editar_parada"):
            col1, col2 = st.columns(2)

            with col1:
                st.markdown("#### 📍 Endereço")
                id_p = st.text_input(
                    "Número da Parada (opcional)",
                    parada.numero_parada or ""
                )
                rua_p = st.text_input("Rua*", parada.rua)
                num_p = st.text_input(
                    "Número (opcional)",
                    parada.numero_localizacao or ""
                )
                bairro_p = st.text_input("Bairro*", parada.bairro)
                cep_p = st.text_input("CEP (opcional)", parada.cep or "")
                ref_p = st.text_area(
                    "Ponto de Referência*",
                    parada.ponto_referencia or ""
                )

            with col2:
                st.markdown("#### 🏗️ Técnica")
                tipo_p = st.selectbox(
                    "Tipo*",
                    ["Placa", "Abrigo", "Abrigo + Placa", "Sem Identificação"],
                    index=["Placa", "Abrigo", "Abrigo + Placa", "Sem Identificação"].index(parada.tipo)
                )
                sentido_p = st.selectbox(
                    "Sentido*",
                    ["PC1 - PC2", "PC2 - PC1"],
                    index=["PC1 - PC2", "PC2 - PC1"].index(parada.sentido)
                )

                st.write(f"📌 Lat: {float(parada.latitude):.6f}")
                st.write(f"📌 Lon: {float(parada.longitude):.6f}")

                st.markdown("#### 📷 Foto")
                if parada.foto_url:
                    st.caption(f"Arquivo atual: {parada.foto_url}")

                foto_nova = st.file_uploader(
                    "Adicionar / Alterar foto",
                    type=["jpg", "jpeg", "png"]
                )

            salvar = st.form_submit_button(
                "💾 SALVAR ALTERAÇÕES",
                type="primary",
                use_container_width=True
            )

            if salvar:
                if not rua_p or not bairro_p or not ref_p:
                    st.error("⚠️ Preencha todos os campos obrigatórios.")
                else:
                    try:
                        parada.numero_parada = id_p.strip() if id_p.strip() else None
                        parada.rua = rua_p.strip()
                        parada.numero_localizacao = num_p.strip() if num_p.strip() else None
                        parada.bairro = bairro_p.strip()
                        parada.cep = cep_p.strip() if cep_p.strip() else None
                        parada.ponto_referencia = ref_p.strip()
                        parada.tipo = tipo_p
                        parada.sentido = sentido_p

                        # Salva apenas o caminho/nome (ideal p/ outro banco ou storage)
                        if foto_nova:
                            parada.foto_url = foto_nova.name

                        db.commit()
                        st.session_state.msg_sucesso = "✅ Parada atualizada com sucesso!"
                        st.cache_data.clear()
                        st.rerun()

                    except Exception as e:
                        db.rollback()
                        st.error(f"Erro ao atualizar: {e}")

        st.divider()

        # ---------- EXCLUSÃO ----------
        st.markdown("### 🗑️ Excluir Parada")
        st.warning("⚠️ Esta ação não pode ser desfeita.")

        confirmar = st.checkbox("Confirmo que desejo excluir esta parada")

        if st.button("❌ EXCLUIR PARADA", use_container_width=True):
            if not confirmar:
                st.error("Marque a confirmação para excluir.")
            else:
                try:
                    db.delete(parada)
                    db.commit()
                    st.session_state.msg_sucesso = "🗑️ Parada excluída com sucesso!"
                    st.cache_data.clear()
                    st.rerun()

                except Exception as e:
                    db.rollback()
                    st.error(f"Erro ao excluir: {e}")

db.close()
















