import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, time
import os

# Configuração da página para ficar bonita no celular
st.set_page_config(page_title="Banco de Horas", page_icon="⏰", layout="centered")

ARQUIVO_EXCEL = "Banco_de_Horas_Web.xlsx"

def formatar_timedelta(td):
    total_seconds = int(td.total_seconds())
    sinal = "-" if total_seconds < 0 else ""
    total_seconds = abs(total_seconds)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    return f"{sinal}{hours:02d}:{minutes:02d}"

def processar_e_salvar(df_novo):
    """Calcula a evolução do saldo acumulado dia a dia e salva no Excel"""
    df_novo = df_novo.sort_values(by="Data").reset_index(drop=True)
    segundos_acumulados = df_novo["Base_Saldo_Segundos"].cumsum()
    
    lista_acumulado_txt = []
    for seg in segundos_acumulados:
        sinal = "-" if seg < 0 else "+"
        h = abs(int(seg)) // 3600
        m = (abs(int(seg)) % 3600) // 60
        lista_acumulado_txt.append(f"{sinal}{h:02d}:{m:02d}")
        
    df_novo["Saldo Acumulado"] = lista_acumulado_txt
    saldo_final_mes = lista_acumulado_txt[-1] if lista_acumulado_txt else "00:00"

    with pd.ExcelWriter(ARQUIVO_EXCEL, engine="openpyxl") as writer:
        df_salvar = df_novo.drop(columns=["Base_Saldo_Segundos"], errors="ignore")
        df_salvar.to_excel(writer, index=False, sheet_name="Resumo Mensal")
        
        df_resumo = pd.DataFrame([{"Saldo Acumulado do Mês": saldo_final_mes}])
        df_resumo.to_excel(writer, index=False, sheet_name="Saldo Final")
        
    return saldo_final_mes

# Gerador de horários formatados (ex: 08:00, 08:05, 08:10...) de 5 em 5 minutos para o Dropdown
@st.cache_data
def gerar_lista_horarios():
    lista = []
    for hora in range(24):
        for minuto in range(0, 60, 5): # Intervalo de 5 em 5 minutos para precisão sem rolar uma lista infinita
            lista.append(f"{hora:02d}:{minuto:02d}")
    return lista

OPCOES_HORARIOS = gerar_lista_horarios()

# Título do App
st.title("⏰ Controle de Banco de Horas")

# Abas do aplicativo
aba_registrar, aba_gerenciar = st.tabs(["📝 Registrar Ponto", "🗑️ Apagar Registro Errado"])

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
            # Seletores controlados via Dropdown (Já limitados e com formato garantido)
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
                "Base_Saldo_Segundos": saldo_diario.total_seconds()
            }

            if os.path.exists(ARQUIVO_EXCEL):
                try:
                    df_existente = pd.read_excel(ARQUIVO_EXCEL, sheet_name="Resumo Mensal")
                    if "Base_Saldo_Segundos" not in df_existente.columns:
                        def texto_para_segundos(txt):
                            try:
                                s = -1 if str(txt).startswith("-") else 1
                                txt = str(txt).replace("-", "")
                                h, m = map(int, txt.split(":"))
                                return s * ((h * 3600) + (m * 60))
                            except:
                                return 0
                        df_existente["Base_Saldo_Segundos"] = df_existente["Saldo do Dia"].apply(texto_para_segundos)
                        
                    df_novo = pd.concat([df_existente, pd.DataFrame([novo_ponto])], ignore_index=True)
                except:
                    df_novo = pd.DataFrame([novo_ponto])
            else:
                df_novo = pd.DataFrame([novo_ponto])

            df_novo = df_novo.drop_duplicates(subset=["Data"], keep="last")

            processar_e_salvar(df_novo)
            st.success(f"Ponto salvo com sucesso!")
            st.rerun()

        except Exception as e:
            st.error(f"Erro inesperado ao calcular os horários: {e}")

# --- ABA 2: APAGAR REGISTRO ---
with aba_gerenciar:
    st.subheader("Remover Pontos Incorretos")
    if os.path.exists(ARQUIVO_EXCEL):
        try:
            df_atual = pd.read_excel(ARQUIVO_EXCEL, sheet_name="Resumo Mensal")
            
            if not df_atual.empty:
                df_atual["ID_Linha"] = df_atual.index.astype(str)
                df_atual["Identificador"] = "[" + df_atual["ID_Linha"] + "] Data: " + df_atual["Data"] + " | Ent: " + df_atual["Entrada"] + " | Sai: " + df_atual["Saída Trabalho"]
                
                registro_selecionado = st.selectbox(
                    "Selecione exatamente qual registro deseja deletar:", 
                    options=df_atual["Identificador"].tolist()
                )
                
                id_para_deletar = int(registro_selecionado.split("]")[0].replace("[", ""))
                
                st.warning("⚠️ Atenção: Essa ação removerá permanentemente o registro selecionado!")
                botao_deletar = st.button("🗑️ Apagar Registro Selecionado", type="primary")
                
                if botao_deletar:
                    def texto_para_segundos(txt):
                        try:
                            s = -1 if str(txt).startswith("-") else 1
                            txt = str(txt).replace("-", "")
                            h, m = map(int, txt.split(":"))
                            return s * ((h * 3600) + (m * 60))
                        except:
                            return 0
                    df_atual["Base_Saldo_Segundos"] = df_atual["Saldo do Dia"].apply(texto_para_segundos)

                    df_final = df_atual.drop(id_para_deletar)
                    df_final = df_final.drop(columns=["Identificador", "ID_Linha"], errors="ignore")
                    
                    processar_e_salvar(df_final)
                    st.success("Registro apagado com sucesso!")
                    st.rerun()
            else:
                st.info("Não há registros salvos para apagar.")
        except Exception as e:
            st.error(f"Erro ao processar exclusão: {e}")
    else:
        st.info("Nenhum arquivo encontrado.")

# --- PAINEL INFORMATIVO DO SALDO ACUMULADO DO MÊS ---
st.markdown("---")
if os.path.exists(ARQUIVO_EXCEL):
    try:
        df_ini = pd.read_excel(ARQUIVO_EXCEL, sheet_name="Saldo Final")
        saldo_total_atual = df_ini.iloc[0]["Saldo Acumulado do Mês"]
        
        if "-" in str(saldo_total_atual):
            st.metric(label="📊 Saldo Final Acumulado do Mês", value=saldo_total_atual, delta="Devedor", delta_color="inverse")
        else:
            st.metric(label="📊 Saldo Final Acumulado do Mês", value=saldo_total_atual, delta="Crédito de Horas")
            
        st.write("### Histórico e Evolução Diária:")
        df_visualizacao = pd.read_excel(ARQUIVO_EXCEL, sheet_name="Resumo Mensal")
        st.dataframe(df_visualizacao, use_container_width=True)
    except:
        pass