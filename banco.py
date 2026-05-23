import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection

# Configuração da página para ficar bonita no celular
st.set_page_config(page_title="Banco de Horas", page_icon="⏰", layout="centered")

# URL da sua planilha do Google Sheets
URL_PLANILHA = "https://docs.google.com/spreadsheets/d/15jqImj07pvjCdzhRuT74jYNiyIUp48E5Q7ZLXQcfr_4/edit?usp=sharing"

# Inicializa a conexão com o Google Sheets
conn = st.connection("gsheets", type=GSheetsConnection)

def formatar_timedelta(td):
    total_seconds = int(td.total_seconds())
    sinal = "-" if total_seconds < 0 else ""
    total_seconds = abs(total_seconds)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    return f"{sinal}{hours:02d}:{minutes:02d}"

def processar_e_salvar(df_novo):
    """Calcula a evolução do saldo acumulado dia a dia e envia para o Google Sheets"""
    if not df_novo.empty:
        # Garante a ordenação cronológica
        df_novo = df_novo.sort_values(by="Data").reset_index(drop=True)
        
        # Recalcula os segundos acumulados
        segundos_acumulados = df_novo["Base_Saldo_Segundos"].cumsum()
        
        lista_acumulado_txt = []
        for seg in segundos_acumulados:
            sinal = "-" if seg < 0 else "+"
            h = abs(int(seg)) // 3600
            m = (abs(int(seg)) % 3600) // 60
            lista_acumulado_txt.append(f"{sinal}{h:02d}:{m:02d}")
            
        df_novo["Saldo Acumulado"] = lista_acumulado_txt
    
    # Atualiza os dados na planilha oficial do Google Sheets
    conn.update(spreadsheet=URL_PLANILHA, data=df_novo)
    # Limpa o cache do Streamlit para forçar a leitura dos novos dados
    st.cache_data.clear()

@st.cache_data
def ler_dados_google():
    """Lê os dados em tempo real do Google Sheets"""
    try:
        df = conn.read(spreadsheet=URL_PLANILHA, ttl="0d")
        # Trata o caso da planilha estar completamente vazia
        if df.empty or df.columns[0].startswith("Unnamed"):
            return pd.DataFrame(columns=["Data", "Entrada", "Saída Almoço", "Retorno Almoço", "Saída Trabalho", "Total Trabalhado", "Saldo do Dia", "Base_Saldo_Segundos", "Saldo Acumulado"])
        return df
    except:
        return pd.DataFrame(columns=["Data", "Entrada", "Saída Almoço", "Retorno Almoço", "Saída Trabalho", "Total Trabalhado", "Saldo do Dia", "Base_Saldo_Segundos", "Saldo Acumulado"])

# Gerador de horários de 5 em 5 minutos
@st.cache_data
def gerar_lista_horarios():
    lista = []
    for hora in range(24):
        for minuto in range(0, 60, 5):
            lista.append(f"{hora:02d}:{minuto:02d}")
    return lista

OPCOES_HORARIOS = gerar_lista_horarios()

# Título do App
st.title("⏰ Controle de Banco de Horas")

# Abas do aplicativo
aba_registrar, aba_gerenciar = st.tabs(["📝 Registrar Ponto", "🗑️ Apagar Registro Errado"])

# Carrega os dados atuais vindos do Google Drive
df_atual_google = ler_dados_google()

# --- ABA 1: REGISTRAR PONTO ---
with aba_registrar:
    st.subheader("Registro de Ponto Diário")
    
    if "data_ponto" not in st.session_state:
        st.session_state.data_ponto = datetime.now().date()
        
    data = st.date_input("Data do Ponto", value=st.session_state.data_ponto, key="data_input")
    
    if data != st.session_state.data_ponto:
        st.session_state.data_ponto = data
        st.rerun()

    eh_sabado = (data.weekday() == 5)
    
    with st.form(key="form_ponto_horarios", clear_on_submit=False):
        if eh_sabado:
            st.info("📅 Data selecionada é um **Sábado**. Jornada padrão de **4 horas** (Sem almoço).")
            ent = st.selectbox("Hora Entrada", options=OPCOES_HORARIOS, index=OPCOES_HORARIOS.index("08:00"))
            sai = st.selectbox("Hora Saída", options=OPCOES_HORARIOS, index=OPCOES_HORARIOS.index("12:00"))
            alm_s, alm_r = "", "" 
        else:
            st.success("📅 Data selecionada é um **Dia de Semana**. Jornada padrão de **8 horas**.")
            col1, col2 = st.columns(2)
            with col1:
                ent = st.selectbox("Hora Entrada", options=OPCOES_HORARIOS, index=OPCOES_HORARIOS.index("08:00"))
                alm_s = st.selectbox("Saída Almoço", options=OPCOES_HORARIOS, index=OPCOES_HORARIOS.index("12:00"))
            with col2:
                alm_r = st.selectbox("Retorno Almoço", options=OPCOES_HORARIOS, index=OPCOES_HORARIOS.index("13:00"))
                sai = st.selectbox("Hora Saída", options=OPCOES_HORARIOS, index=OPCOES_HORARIOS.index("18:00"))
            
        botao_enviar = st.form_submit_button(label="Salvar Ponto")

    if botao_enviar:
        try:
            fmt = "%H:%M"
            dt_ent = datetime.strptime(ent, fmt)
            dt_sai = datetime.strptime(sai, fmt)

            if eh_sabado:
                total_trabalhado = dt_sai - dt_ent
                jornada_do_dia = timedelta(hours=4)
                alm_s_txt, alm_r_txt = "N/A", "N/A"
            else:
                dt_alm_s = datetime.strptime(alm_s, fmt)
                dt_alm_r = datetime.strptime(alm_r, fmt)
                total_trabalhado = (dt_alm_s - dt_ent) + (dt_sai - dt_alm_r)
                jornada_do_dia = timedelta(hours=8)
                alm_s_txt, alm_r_txt = alm_s, alm_r

            saldo_diario = total_trabalhado - jornada_do_dia

            novo_ponto = {
                "Data": data.strftime("%Y-%m-%d"),
                "Entrada": ent,
                "Saída Almoço": alm_s_txt,
                "Retorno Almoço": alm_r_txt,
                "Saída Trabalho": sai,
                "Total Trabalhado": formatar_timedelta(total_trabalhado),
                "Saldo do Dia": formatar_timedelta(saldo_diario),
                "Base_Saldo_Segundos": float(saldo_diario.total_seconds()),
                "Saldo Acumulado": ""
            }

            # Garante tipos de dados compatíveis antes do append
            df_novo_registro = pd.DataFrame([novo_ponto])
            if not df_atual_google.empty:
                df_atual_google["Data"] = df_atual_google["Data"].astype(str)
                df_atual_google["Base_Saldo_Segundos"] = df_atual_google["Base_Saldo_Segundos"].astype(float)
                df_comb = pd.concat([df_atual_google, df_novo_registro], ignore_index=True)
            else:
                df_comb = df_novo_registro

            # Sobrescreve se a mesma data for digitada novamente
            df_comb = df_comb.drop_duplicates(subset=["Data"], keep="last")

            processar_e_salvar(df_comb)
            st.success(f"Ponto guardado com sucesso no Google Sheets!")
            st.rerun()

        except Exception as e:
            st.error(f"Erro ao processar: {e}")

# --- ABA 2: APAGAR REGISTRO ---
with aba_gerenciar:
    st.subheader("Remover Pontos Incorretos")
    if not df_atual_google.empty:
        try:
            df_atual_google["ID_Linha"] = df_atual_google.index.astype(str)
            df_atual_google["Identificador"] = "[" + df_atual_google["ID_Linha"] + "] Data: " + df_atual_google["Data"].astype(str) + " | Ent: " + df_atual_google["Entrada"] + " | Sai: " + df_atual_google["Saída Trabalho"]
            
            registro_selecionado = st.selectbox(
                "Selecione exatamente qual registro deseja deletar:", 
                options=df_atual_google["Identificador"].tolist()
            )
            
            id_para_deletar = int(registro_selecionado.split("]")[0].replace("[", ""))
            
            st.warning("⚠️ Atenção: Essa ação removerá permanentemente o registro selecionado!")
            botao_deletar = st.button("🗑️ Apagar Registro Selecionado", type="primary")
            
            if botao_deletar:
                df_final = df_atual_google.drop(id_para_deletar)
                df_final = df_final.drop(columns=["Identificador", "ID_Linha"], errors="ignore")
                processar_e_salvar(df_final)
                st.success("Registro apagado com sucesso!")
                st.rerun()
        except Exception as e:
            st.error(f"Erro ao processar exclusão: {e}")
    else:
        st.info("Não há registros salvos para apagar.")

# --- PAINEL INFORMATIVO REAL TIME ---
st.markdown("---")
if not df_atual_google.empty:
    try:
        saldo_total_atual = df_atual_google.iloc[-1]["Saldo Acumulado"]
        
        if "-" in str(saldo_total_atual):
            st.metric(label="📊 Saldo Final Acumulado do Mês", value=saldo_total_atual, delta="Devedor", delta_color="inverse")
        else:
            st.metric(label="📊 Saldo Final Acumulado do Mês", value=saldo_total_atual, delta="Crédito de Horas")
            
        st.write("### Histórico e Evolução Diária (Google Sheets):")
        # Esconde a coluna técnica de segundos para exibição
        df_vis = df_atual_google.drop(columns=["Base_Saldo_Segundos", "ID_Linha", "Identificador"], errors="ignore")
        st.dataframe(df_vis, use_container_width=True)
    except:
        pass
else:
    st.metric(label="📊 Saldo Final Acumulado do Mês", value="00:00", delta="Sem registros")
