import streamlit as st
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import folium
from streamlit_folium import st_folium
import io

# ----------------------------------------------------------------------------
# 0. CONFIGURACIÓN GLOBAL
# ----------------------------------------------------------------------------
st.set_page_config(
    page_title="NICSPECTRA - Ingeniería Estructural",
    page_icon="🇳🇮",
    layout="wide"
)

# ----------------------------------------------------------------------------
# 1. MENÚ DE NAVEGACIÓN
# ----------------------------------------------------------------------------

try:
    st.sidebar.image("logo_nicspectra.jpg", width=200)
except:
    try:
        st.sidebar.image("logo nicspectra.jpg", width=200)
    except:
        pass

st.sidebar.title("Navegación")
modulo_seleccionado = st.sidebar.radio(
    "Seleccione el Módulo:", 
    ["Sismo (NSM-22)", "Viento (RNC-07)"]
)
st.sidebar.markdown("---")

# ============================================================================
# MÓDULO DE VIENTO (RNC-07)
# ============================================================================
def app_viento():
    st.title("🌪️ Análisis de Cargas de Viento (RNC-07)")
    st.markdown("""
    Cálculo de fuerzas estáticas según el **Título IV del Reglamento Nacional de Construcción**.
    *(Fórmula: $P_z = 0.0479 \cdot C_p \cdot V_D^2$)*
    """)

    # --- INPUTS VIENTO ---
    with st.sidebar:
        st.subheader("1. Geometría del Edificio")
        B = st.number_input("Ancho Frontal B (m)", value=20.0, min_value=1.0)
        L = st.number_input("Profundidad L (m)", value=15.0, min_value=1.0)
        alturas_input = st.text_area("Alturas de Entrepisos (m)", value="4.0, 3.5, 3.5, 3.5")
        
        st.subheader("2. Parámetros RNC-07")
        zona_opt = st.selectbox("Zona Eólica (Fig. 7)", ["Zona 1 (Norte/Centro)", "Zona 2 (Pacífico/Managua)", "Zona 3 (Atlántico)"])
        grupo_opt = st.selectbox("Importancia (Art. 50)", ["Grupo A (Esencial - 200 años)", "Grupo B (Normal - 50 años)"])
        rugosidad_opt = st.selectbox("Rugosidad (Tabla 6)", ["R1 (Campo Abierto)", "R2 (Pocas obstrucciones)", "R3 (Urbano)", "R4 (Centro denso)"])
        topo_opt = st.selectbox("Topografía (Tabla 7)", ["T1 (Protegida)", "T2 (Valles)", "T3 (Plano < 5%)", "T4 (Pendiente 5-10%)", "T5 (Cimas > 10%)"])

    # --- CÁLCULOS VIENTO ---
    try:
        h_pisos = [float(x.strip()) for x in alturas_input.split(',') if x.strip()]
        if not h_pisos:
            st.warning("⚠️ Ingresa al menos una altura de entrepiso.")
            return

        z_acum = []
        acc = 0
        for h in h_pisos:
            acc += h
            z_acum.append(acc)
        H_total = z_acum[-1]

        # Lógica RNC-07
        zona_key = zona_opt.split(" (")[0] 
        mapa_zona = {"Zona 1": 1, "Zona 2": 2, "Zona 3": 3}
        if zona_key not in mapa_zona: return
            
        zona_idx = mapa_zona[zona_key]
        es_grupo_a = "Grupo A" in grupo_opt
        tabla_vr = {1: {'A': 36, 'B': 30}, 2: {'A': 60, 'B': 45}, 3: {'A': 70, 'B': 56}}
        Vr = tabla_vr[zona_idx]['A' if es_grupo_a else 'B']

        rug_cod = rugosidad_opt.split(" ")[0]
        tabla_rug = {'R1': {'a': 0.099, 'd': 245}, 'R2': {'a': 0.128, 'd': 315}, 'R3': {'a': 0.156, 'd': 390}, 'R4': {'a': 0.170, 'd': 455}}
        alpha, delta = tabla_rug[rug_cod]['a'], tabla_rug[rug_cod]['d']

        topo_cod = topo_opt.split(" ")[0]
        if rug_cod == 'R1': Ftr = 1.0
        else:
            tabla_ftr = {'T1': {'R2': 0.8, 'R3': 0.70, 'R4': 0.66}, 'T2': {'R2': 0.9, 'R3': 0.79, 'R4': 0.74}, 
                         'T3': {'R2': 1.0, 'R3': 0.88, 'R4': 0.82}, 'T4': {'R2': 1.1, 'R3': 0.97, 'R4': 0.90}, 'T5': {'R2': 1.2, 'R3': 1.06, 'R4': 0.98}}
            Ftr = tabla_ftr[topo_cod][rug_cod]

        K_PRESION, CP_BARLO, CP_SOTA = 0.0479, 0.8, 0.4
        z_sot = max(10.0, min(H_total, delta))
        Fa_sot = (z_sot / 10.0) ** alpha if z_sot > 10 else 1.0
        Vd_sot = Vr * Fa_sot * Ftr
        q_sot = K_PRESION * CP_SOTA * (Vd_sot**2)

        resultados = []
        sum_fx, sum_fy = 0, 0

        for i, z in enumerate(z_acum):
            h_piso = h_pisos[i]
            h_trib = h_piso / 2.0 if i == len(h_pisos) - 1 else (h_piso / 2.0) + (h_pisos[i+1] / 2.0)
            
            z_calc = max(10.0, min(z, delta))
            Fa = (z_calc / 10.0) ** alpha if z > 10 else 1.0
            Vd = Vr * Fa * Ftr
            q_barlo = K_PRESION * CP_BARLO * (Vd**2)
            q_neto = q_barlo + q_sot
            
            fx = q_neto * B * h_trib / 1000
            fy = q_neto * L * h_trib / 1000
            sum_fx += fx; sum_fy += fy

            resultados.append({"Nivel": f"Piso {i+1}", "Z (m)": f"{z:.2f}", "Fa": f"{Fa:.3f}", "Vd (m/s)": f"{Vd:.2f}", 
                               "q_neto (kg/m²)": f"{q_neto:.2f}", "Fx (Ton)": round(fx, 3), "Fy (Ton)": round(fy, 3)})

        col1, col2, col3 = st.columns(3)
        col1.metric("Velocidad Regional", f"{Vr} m/s")
        col2.metric("Cortante FX", f"{sum_fx:.2f} Ton")
        col3.metric("Cortante FY", f"{sum_fy:.2f} Ton")

        df = pd.DataFrame(resultados)
        st.subheader("Tabla de Cargas")
        st.dataframe(df, use_container_width=True)
        st.download_button("📥 Descargar CSV", df.to_csv(index=False).encode('utf-8'), "cargas_viento.csv", "text/csv")

    except Exception as e:
        st.error(f"Error: {e}")

# ============================================================================
# LÓGICA PRINCIPAL (CONTROL DE MÓDULOS)
# ============================================================================

if modulo_seleccionado == "Viento (RNC-07)":
    app_viento()

elif modulo_seleccionado == "Sismo (NSM-22)":
    
    # ----------------------------------------------------------------------------
    # CÓDIGO SISMO (CON LÓGICA DE CDS AUTOMÁTICA)
    # ----------------------------------------------------------------------------
    st.title("NICSPECTRA: Herramienta de Diseño Sismorresistente")
    st.subheader("Norma Sismorresistente para la ciudad de Managua (NSM-22)")
    st.caption("Defensa de Grado: Israel Castillo | Bryan Torrez | Andres Zamora")
    
    # --- 1. CARGA DE DATOS ---
    @st.cache_data
    def load_data():
        try:
            read_params = {'header': 0, 'skiprows': [1]}
            data = {
                "Aceleracion_table": pd.read_excel('Aceleraciones.xlsx'),
                "Vs30_table": pd.read_excel('Vs30.xlsx'),
                "MurosDeCarga": pd.read_excel('SistemasDeMurosDeCarga.xlsx', **read_params),
                "MurosEstructurales": pd.read_excel('SistemasDeMurosEstructuralesYMarcosArriostrados.xlsx', **read_params),
                "MarcosAMomento": pd.read_excel('SistemasDeMarcosAMomento.xlsx', **read_params),
                "DualesEspeciales": pd.read_excel('SistemasDualesConMarcosDeMomentosEspecialesCapazDeResistirAlMenosEl25DeLasFuerzasSismicasPrescritas.xlsx', **read_params),
                "DualesIntermedios": pd.read_excel('SistemasDualesConMarcosDeMomentoIntermedioCapazDeResistirAlMenosEl25DeLasFuerzasSismicasPrescritas.xlsx', **read_params),
                "ColumnasEnVoladizo": pd.read_excel('SistemasDeColumnaEnVoladizoYSistemasDeAceroNoDetalladosEspecificamenteParaResistenciaSismica.xlsx', **read_params),
            }
            return data
        except Exception as e:
            st.error(f"Error al cargar archivos Excel: {e}")
            return None

    data = load_data()
    if data is None:
        st.stop()

    Aceleracion_table = data.get("Aceleracion_table")
    Vs30_table = data.get("Vs30_table")

    # --- 2. FUNCIONES DE LÓGICA NSM-22 ---
    def obtener_zona_sismica(a0):
        if a0 >= 0.315: return "Z4"
        elif 0.23 <= a0 < 0.315: return "Z3"
        elif 0.17 <= a0 < 0.23: return "Z2"
        else: return "Z1"

    def clasificar_suelo(vs30):
        if vs30 > 1500: return "A"
        elif 760 < vs30 <= 1500: return "B"
        elif 360 < vs30 <= 760: return "C"
        elif 180 <= vs30 <= 360: return "D"
        else: return "E"

    # --- NUEVA FUNCIÓN: Determinar Categoría de Diseño Sísmico (CDS) ---
    def obtener_cds(a0, grupo_str):
        # Identificar si es Riesgo Alto (III o IV) o Normal (I o II)
        # El string viene como 'Grupo A: ... (IV)'
        es_riesgo_alto = "IV" in grupo_str or "III" in grupo_str
        
        if a0 >= 0.30:
            return "D" # Siempre D en zona muy alta
        elif 0.15 <= a0 < 0.30:
            return "D" if es_riesgo_alto else "C"
        elif 0.10 <= a0 < 0.15:
            return "C" if es_riesgo_alto else "B"
        else: # a0 < 0.10
            return "B" if es_riesgo_alto else "A"

    def obtener_Fas(zona, tipo_suelo):
        tabla_Fas = {
            "Z1": {"A": 0.8, "B": 1.0, "C": 1.4, "D": 1.7, "E": 2.2},
            "Z2": {"A": 0.8, "B": 1.0, "C": 1.4, "D": 1.6, "E": 2.0},
            "Z3": {"A": 0.8, "B": 1.0, "C": 1.4, "D": 1.5, "E": 2.4}, 
            "Z4": {"A": 0.8, "B": 1.0, "C": 1.3, "D": 1.4, "E": 2.4}  
        }
        return tabla_Fas.get(zona, {}).get(tipo_suelo, 1.0)

    def obtener_factores_ajuste_espectral(tipo_suelo):
        if tipo_suelo == "A": return (1.0, 5/6)
        elif tipo_suelo == "B": return (1.0, 1.0)
        elif tipo_suelo == "C": return (1.0, 4/3)
        elif tipo_suelo == "D": return (2.0, 5/3)
        else: return (2.0, 5/3)

    def calcular_carga_ceniza(departamento):
        deptos_riesgo_ceniza = [
            'CHINANDEGA', 'LEON', 'MANAGUA', 'MASAYA', 'GRANADA', 'CARAZO', 'RIVAS'
        ]
        dep_norm = departamento.upper().strip()
        es_zona_riesgo = any(d in dep_norm for d in deptos_riesgo_ceniza)
        carga = 20.0 if es_zona_riesgo else 0.0
        return carga, es_zona_riesgo

    # --- INICIALIZACIÓN DE ESTADO ---
    if 'departamento_actual' not in st.session_state:
        st.session_state['departamento_actual'] = 'MANAGUA'

    # --- 3. INTERFAZ: MAPA ---
    if 'LATITUD' in Aceleracion_table.columns:
        with st.container(border=True):
            col_map, col_info = st.columns([3, 1])
            with col_map:
                try:
                    dep_sel_row = Aceleracion_table[Aceleracion_table['DEPARTAMENTO'] == st.session_state['departamento_actual']].iloc[0]
                    lat_c, lon_c = dep_sel_row['LATITUD'], dep_sel_row['LONGITUD']
                    zoom_c = 10
                except:
                    lat_c, lon_c, zoom_c = 12.8, -85.5, 7

                m = folium.Map(location=[lat_c, lon_c], zoom_start=zoom_c, tiles="CartoDB positron")
                
                fg_z4 = folium.FeatureGroup(name="Zona IV (≥ 0.315g)")
                fg_z3 = folium.FeatureGroup(name="Zona III")
                fg_z2 = folium.FeatureGroup(name="Zona II")
                fg_z1 = folium.FeatureGroup(name="Zona I")

                for _, row in Aceleracion_table.dropna(subset=['LATITUD', 'LONGITUD']).iterrows():
                    acc = row['ACELERACION']
                    zona_calc = obtener_zona_sismica(acc)
                    color = {'Z4': '#d32f2f', 'Z3': '#f57c00', 'Z2': '#fbc02d', 'Z1': '#388e3c'}[zona_calc]
                    dest = {'Z4': fg_z4, 'Z3': fg_z3, 'Z2': fg_z2, 'Z1': fg_z1}[zona_calc]

                    folium.CircleMarker(
                        location=[row['LATITUD'], row['LONGITUD']],
                        radius=5, color=color, fill=True, fill_color=color, fill_opacity=0.7,
                        popup=f"<b>{row['DEPARTAMENTO']}</b><br>a0: {acc}g<br>{zona_calc}",
                        tooltip=f"{row['DEPARTAMENTO']}"
                    ).add_to(dest)

                fg_z4.add_to(m); fg_z3.add_to(m); fg_z2.add_to(m); fg_z1.add_to(m)
                folium.LayerControl().add_to(m)
                output = st_folium(m, height=400, use_container_width=True)

            if output and output.get('last_object_clicked'):
                lat_click = output['last_object_clicked']['lat']
                lon_click = output['last_object_clicked']['lng']
                
                df_map = Aceleracion_table.copy()
                df_map['dist'] = np.sqrt((df_map['LATITUD']-lat_click)**2 + (df_map['LONGITUD']-lon_click)**2)
                seleccion = df_map.loc[df_map['dist'].idxmin()]
                nombre_nuevo = seleccion['DEPARTAMENTO']
                
                if nombre_nuevo != st.session_state['departamento_actual']:
                    st.session_state['departamento_actual'] = nombre_nuevo
                    st.rerun()

            with col_info:
                accel_val = Aceleracion_table.loc[Aceleracion_table['DEPARTAMENTO'] == st.session_state['departamento_actual'], 'ACELERACION'].values[0]
                
                st.markdown("#### Sitio Seleccionado")
                st.success(f"📍 {st.session_state['departamento_actual']}")
                st.metric("Aceleración a₀", f"{accel_val:.4f} g")
                st.info(f"Zona: {obtener_zona_sismica(accel_val)}")
                st.caption("Seleccione otro sitio haciendo clic en el mapa.")

    # --- 4. SIDEBAR - PARÁMETROS DE ENTRADA ---
    st.sidebar.header("Parámetros de Diseño (Sismo)")

    # 1. Ubicación y Suelo
    Departamento = st.session_state['departamento_actual']
    st.sidebar.subheader("1. Ubicación y Suelo")
    st.sidebar.info(f"**Sitio:** {Departamento}")

    try:
        a_0 = Aceleracion_table.loc[Aceleracion_table['DEPARTAMENTO'] == Departamento, 'ACELERACION'].values[0]
    except IndexError:
        st.error("Error: Departamento no encontrado en Excel.")
        st.stop()

    Zona_Sismica = obtener_zona_sismica(a_0)

    metodo_suelo = st.sidebar.radio(
        "¿Cómo desea definir el suelo?",
        ["Ingresar/Calcular Vs30", "Seleccionar Tipo (A-E)"]
    )

    Vs30 = None
    if metodo_suelo == "Ingresar/Calcular Vs30":
        if Departamento == 'MANAGUA':
            sitios_managua = Vs30_table['NOMBRE DEL SITIO'].unique()
            Ubicacion_E = st.sidebar.selectbox("Sitio Específico (Managua)", sitios_managua)
            col_vs30 = 'Vs30(m/s)' if 'Vs30(m/s)' in Vs30_table.columns else 'Vs30 (m/s)'
            Vs30 = Vs30_table.loc[Vs30_table['NOMBRE DEL SITIO'] == Ubicacion_E, col_vs30].values[0]
            st.sidebar.write(f"*Vs30 base de datos: {Vs30} m/s*")
        else:
            Vs30 = st.sidebar.number_input("Ingrese Vs30 (m/s)", min_value=100.0, max_value=2500.0, value=360.0)
        Tipo_Suelo = clasificar_suelo(Vs30)
    else:
        Tipo_Suelo = st.sidebar.selectbox("Seleccione el Tipo de Suelo:", ["A", "B", "C", "D", "E"], index=3)
        st.sidebar.caption("Selección manual directa.")

    if Vs30:
        st.sidebar.info(f"**Suelo Tipo {Tipo_Suelo}** (Zona {Zona_Sismica}) | Vs30: {Vs30} m/s")
    else:
        st.sidebar.info(f"**Suelo Tipo {Tipo_Suelo}** (Zona {Zona_Sismica})")

    # 2. Importancia
    st.sidebar.subheader("2. Grupo de Importancia")
    grupo_dict = {
        'Grupo A: Esenciales/Críticas (IV)': 1.65,
        'Grupo B: Ocupación Especial (III)': 1.30,
        'Grupo C: Ocupación Normal (II)': 1.00,
        'Grupo D: No habitacional (I)': 0.75
    }
    Grupo_I_key = st.sidebar.selectbox("Seleccione Grupo", list(grupo_dict.keys()), index=2)
    I = grupo_dict[Grupo_I_key]

    # --- CALCULO AUTOMÁTICO DE CDS (Categoría de Diseño Sísmico) ---
    CDS_calculado = obtener_cds(a_0, Grupo_I_key)
    st.sidebar.success(f"**Categoría Diseño Sísmico: CDS {CDS_calculado}**")
    
    # 3. Sistema Estructural
    st.sidebar.subheader("3. Sistema Estructural")
    cat_sistemas = {
        "Muros de Carga": "MurosDeCarga",
        "Muros Estruct. / Arriostrados": "MurosEstructurales",
        "Marcos a Momento": "MarcosAMomento",
        "Duales (Especiales)": "DualesEspeciales",
        "Duales (Intermedios)": "DualesIntermedios",
        "Voladizo / Otros": "ColumnasEnVoladizo"
    }
    cat_sel = st.sidebar.selectbox("Categoría", list(cat_sistemas.keys()))
    df_sys = data[cat_sistemas[cat_sel]]
    Sistema = st.sidebar.selectbox("Sistema Específico", df_sys['Sistema Estructural'].unique())

    row_sys = df_sys[df_sys['Sistema Estructural'] == Sistema].iloc[0]
    R = row_sys['R']
    Omega = row_sys['Omega']
    Cd = row_sys['Coeficiente de deflexion, Cd']

    # 4. Irregularidades (CON LÓGICA DE CDS C y D)
    st.sidebar.subheader("4. Factores de Irregularidad")
    
    error_irregularidad = False
    mensaje_error = ""

    # --- PLANTA ---
    with st.sidebar.expander("Irregularidad en Planta (Φp)"):
        st.markdown("*(Tabla 5.4.2 NSM-22)*")
        
        torsion_opt = st.selectbox("Tipo 1: Torsional", ["Ninguna", "Estándar (1a) [0.9]", "Extrema (1b) [0.8]"])
        factor_torsion = 1.0
        if "Estándar" in torsion_opt: factor_torsion = 0.9
        elif "Extrema" in torsion_opt: factor_torsion = 0.8
        
        chk_p2 = st.checkbox("Tipo 2: Esquinas Entrantes [0.9]")
        chk_p3 = st.checkbox("Tipo 3: Discontinuidad Diafragma [0.9]")
        chk_p4 = st.checkbox("Tipo 4: Ejes No Paralelos [0.8]")
        
        phi_p_acum = factor_torsion
        if chk_p2: phi_p_acum *= 0.9
        if chk_p3: phi_p_acum *= 0.9
        if chk_p4: phi_p_acum *= 0.8
        
        Phi_P = phi_p_acum
        st.write(f"**Factor Planta (Φp): {Phi_P:.2f}**")

    # --- ELEVACIÓN ---
    with st.sidebar.expander("Irregularidad en Elevación (Φe)"):
        st.markdown("*(Tabla 5.4.3 NSM-22)*")
        
        blando_opt = st.selectbox("Tipo 1: Piso Blando (Rigidez)", ["Ninguna", "Estándar (1a) [0.8]", "Extrema (3Ex) [PROHIBIDA]"])
        factor_blando = 1.0
        if "Estándar" in blando_opt: factor_blando = 0.8
        elif "Extrema" in blando_opt:
            # AQUI SE USA EL CDS: Si es C o D, prohibido.
            if CDS_calculado in ["C", "D"]:
                error_irregularidad = True
                mensaje_error = f"🚫 ERROR NSM-22: Irregularidad 3Ex PROHIBIDA en Categoría de Diseño Sísmico '{CDS_calculado}'."
            else:
                factor_blando = 0.7 # Solo permitido en A o B
        
        debil_opt = st.selectbox("Tipo 4: Piso Débil (Resistencia)", ["Ninguna", "Estándar (4a) [0.8]", "Extrema (4Ex) [PROHIBIDA]"])
        factor_debil = 1.0
        if "Estándar" in debil_opt: factor_debil = 0.8
        elif "Extrema" in debil_opt:
            if CDS_calculado in ["C", "D"]:
                error_irregularidad = True
                mensaje_error = f"🚫 ERROR NSM-22: Irregularidad 4Ex PROHIBIDA en Categoría de Diseño Sísmico '{CDS_calculado}'."
            else:
                factor_debil = 0.6 # Solo permitido en A o B
        
        chk_e2 = st.checkbox("Tipo 2: Peso (Masa) [0.9]")
        chk_e3 = st.checkbox("Tipo 3: Geométrica Vertical [0.9]")
        
        phi_e_acum = factor_blando * factor_debil
        if chk_e2: phi_e_acum *= 0.9
        if chk_e3: phi_e_acum *= 0.9
        
        Phi_E = phi_e_acum
        st.write(f"**Factor Elevación (Φe): {Phi_E:.2f}**")

    # --- 5. MOTOR DE CÁLCULO ---
    st.header("Resultados del Análisis (NSM-22)")

    if error_irregularidad:
        st.error(mensaje_error)
        st.stop() # DETIENE TODO SI HAY ERROR

    # Cálculo Ceniza
    C_cv, es_zona_riesgo = calcular_carga_ceniza(Departamento)

    # Cálculos Sísmicos
    F_as = obtener_Fas(Zona_Sismica, Tipo_Suelo)
    FS_Tb, FS_Tc = obtener_factores_ajuste_espectral(Tipo_Suelo)
    A_o = a_0 * F_as * I
    R_o = R * Phi_P * Phi_E

    Tb_base, Tc_base, Td_base = 0.05, 0.3, 2.0
    beta, p, q = 2.4, 0.8, 2.0
    T_b = FS_Tb * Tb_base
    T_c = FS_Tc * Tc_base
    T_d = Td_base

    # --- VISUALIZACIÓN ---
    with st.container(border=True):
        st.subheader("Cargas Ambientales (Sección 7.3)")
        col_ash1, col_ash2 = st.columns([1, 3])
        
        col_ash1.metric("Carga Ceniza (Ccv)", f"{C_cv} kg/m²")
        
        if es_zona_riesgo:
            col_ash2.warning(f"⚠️ **Zona de Riesgo Volcánico:** {Departamento}")
            col_ash2.markdown(f"Según NSM-22 Sec 7.3, se debe aplicar una carga mínima de **20 kg/m²**.")
        else:
            col_ash2.success(f"✅ **Zona de Bajo Riesgo:** {Departamento}")
            col_ash2.caption("No se requiere carga de ceniza según mapa de amenaza regional.")

    st.subheader("Parámetros Sísmicos de Diseño")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Acel. Roca (a₀)", f"{a_0:.3f} g")
    c2.metric("Factor Suelo (Fas)", f"{F_as:.2f}")
    c3.metric("Importancia (I)", f"{I:.2f}")
    c4.metric("Acel. Diseño (A₀)", f"{A_o:.4f} g", help="a₀ × Fas × I")

    st.markdown("---")
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Coef. R (Sistema)", f"{R:.2f}")
    k2.metric("R₀ (Reducido)", f"{R_o:.2f}", delta_color="inverse", help="R × Φp × Φe")
    k3.metric("Ω₀ (Sobrerresistencia)", f"{Omega:.2f}")
    k4.metric("Cd (Deflexión)", f"{Cd:.2f}")

    # --- 6. GRÁFICOS  ---
    T_vals = np.linspace(0.0, 4.0, 401)
    A_elastico = []
    A_diseno = []

    for t in T_vals:
        if t < T_b:
            val_e = A_o * (1 + (t / T_b) * (beta - 1))
        elif T_b <= t < T_c:
            val_e = A_o * beta
        elif T_c <= t < T_d:
            val_e = A_o * beta * (T_c / t)**p
        else:
            val_e = A_o * beta * (T_c / T_d)**p * (T_d / t)**q
        A_elastico.append(val_e)

        if R_o > 0:
            if t < T_b:
                val_d = (A_o * t / T_b) * ((beta / R_o) - 1) + A_o
            elif T_b <= t < T_c:
                val_d = (A_o * beta) / R_o
            elif T_c <= t < T_d:
                val_d = (A_o * beta * (T_c / t)**p) / R_o
            else:
                val_d = (A_o * beta * (T_c / T_d)**p * (T_d / t)**q) / R_o
        else:
            val_d = val_e
        A_diseno.append(val_d)


  # ------------------------------------------------------------------------
    # 6. GRÁFICOS Y DESCARGAS 
    # ------------------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(T_vals, A_elastico, 'k-', linewidth=2, label='Elástico (A)')
    ax.plot(T_vals, A_diseno, 'r-', linewidth=2, label=f'Diseño (Ad) [Ro={R_o:.2f}]')
    
    ax.set_title(f"Espectros NSM-22 | {Departamento} | Suelo Tipo {Tipo_Suelo}", fontsize=14)
    ax.set_xlabel("Periodo (s)"); ax.set_ylabel("Aceleración (g)")
    
    # -------------------------------
    # Ticks del Eje Y cada 0.1 g + Minor Ticks
    # -------------------------------
    
    max_val = max(max(A_elastico), max(A_diseno))
    limite_y = np.ceil(max_val * 10) / 10 
    if limite_y < max_val: 
        limite_y += 0.1
    
    ax.set_yticks(np.arange(0, limite_y + 0.15, 0.1))
    ax.set_ylim(0, limite_y + 0.05)
    
    # --- MINOR TICKS ---
    ax.minorticks_on()
    ax.grid(which='major', linestyle='--', linewidth=0.7, alpha=0.8, color='black')
    ax.grid(which='minor', linestyle=':', linewidth=0.5, alpha=0.5, color='gray')
    
    ax.legend(); ax.set_xlim(0, 4)
    st.pyplot(fig)

    nombre_dep = Departamento.replace(" ", "_")
    
    # Nombre base: "NSM22_MANAGUA_SueloC"
    nombre_base = f"NSM22_{nombre_dep}_Suelo{Tipo_Suelo}"

    st.markdown("---")
    st.subheader("Descargas")

    @st.cache_data
    def convertir_txt(t, sa):
        df = pd.DataFrame({'Periodo(s)': t, 'Sa_Diseño(g)': sa})
        return df.to_string(index=False).encode('utf-8')

    def obtener_imagen(figure):
        import io
        buf = io.BytesIO()
        figure.savefig(buf, format='png', dpi=300, bbox_inches='tight')
        buf.seek(0)
        return buf

    # --- MENÚ DE DESCARGA ---
    
    opcion_descarga = st.selectbox(
        "Seleccione el formato a descargar:",
        ["Texto Plano (.txt)", "Gráfico de Espectro (.png)"]
    )

    if opcion_descarga == "Texto Plano (.txt)":
        txt_data = convertir_txt(T_vals, A_diseno)
        st.download_button(
            label=f"📄 Descargar TXT ({nombre_base})", 
            data=txt_data, 
            file_name=f"{nombre_base}.txt", 
            mime="text/plain",
            key="dl_txt"
        )
        
    elif opcion_descarga == "Gráfico de Espectro (.png)":
        img_data = obtener_imagen(fig)
        st.download_button(
            label=f"🖼️ Descargar PNG ({nombre_base})",
            data=img_data,
            file_name=f"{nombre_base}.png",
            mime="image/png",
            key="dl_png"
        )
