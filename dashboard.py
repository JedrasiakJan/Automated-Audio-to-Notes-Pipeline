import streamlit as st
import pandas as pd
import os
import plotly.express as px
import re

st.set_page_config(page_title="SafeMed Analytics", layout="wide", page_icon="📊")

def get_performance_data():
    data = []
    if not os.path.exists('app.log'):
        return pd.DataFrame()
    
    with open('app.log', 'r', encoding='utf-8') as f:
        for line in f:
            # Szukamy tylko linii AUDIT, które mają zapisany czas (TIME:)
            if "AUDIT" in line and "TIME:" in line:
                try:
                    id_match = re.search(r'ID:\s*([^|]+)', line)
                    session_id = id_match.group(1).strip() if id_match else "Nieznane"
                    # 1. Wycinamy datę - bierzemy wszystko przed pierwszym " - "
                    # Przykład: 2026-04-09 12:58:38,024 -> zostaje 2026-04-09 12:58:38,024
                    timestamp_raw = line.split(' - ')[0].strip()
                    
                    # 2. Wyciągamy Czynność (ACTION) używając wyrażeń regularnych
                    action_match = re.search(r'ACTION:\s*([^|]+)', line)
                    action = action_match.group(1).strip() if action_match else "Inne"
                    
                    # 3. Wyciągamy Czas (TIME)
                    duration_match = re.search(r'TIME:\s*([\d.]+)', line)
                    if duration_match:
                        duration = float(duration_match.group(1))
                        data.append({
                            "ID": session_id,
                            "Godzina": timestamp_raw, 
                            "Czynność": action, 
                            "Czas_sekundy": duration
                        })
                except Exception:
                    continue
    
    df = pd.DataFrame(data)
    
    if not df.empty:
        # CZYSZCZENIE DATY DLA PANDAS:
        # Usuwamy milisekundy (to co po przecinku), bo Pandas czasem ma z tym problem na Windows
        df['Godzina_Clean'] = df['Godzina'].str.split(',').str[0]
        
        # Konwersja na format daty (coerce sprawi, że błędne daty zamienią się w NaT zamiast wywalać błąd)
        df['Godzina_DT'] = pd.to_datetime(df['Godzina_Clean'], errors='coerce')
        
        # Usuwamy wiersze, których nie udało się sparsować
        df = df.dropna(subset=['Godzina_DT'])
        
        # Sortujemy chronologicznie
        df = df.sort_values('Godzina_DT')
        
    return df

st.title("📊 Panel Analityczny SafeMed AI")
st.info("Dane pobierane na żywo z pliku app.log")

df = get_performance_data()

if not df.empty:
    # 1. Metryki na górze (KPI)
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Łącznie operacji", len(df))
    with col2:
        avg_whisper = df[df['Czynność'] == 'TRANSCRIPTION']['Czas_sekundy'].mean()
        st.metric("Średni czas Whisper", f"{round(avg_whisper, 2)}s" if not pd.isna(avg_whisper) else "---")
    with col3:
        avg_llm = df[df['Czynność'] == 'LLM_ANALYSIS']['Czas_sekundy'].mean()
        st.metric("Średni czas LLM", f"{round(avg_llm, 2)}s" if not pd.isna(avg_llm) else "---")

    st.divider()

    # 2. Wykresy interaktywne
    c1, c2 = st.columns(2)
    
    with c1:
        st.subheader("⏱️ Wydajność w czasie")
        # Używamy wyczyszczonej daty do wykresu
        fig_line = px.line(df, x="Godzina_DT", y="Czas_sekundy", color="Czynność", 
                           markers=True, labels={"Godzina_DT": "Czas operacji", "Czas_sekundy": "Czas (s)"})
        st.plotly_chart(fig_line, width='stretch')
    with c2:
        st.subheader("📦 Rozkład czasu pracy (Boxplot)")
        fig_box = px.box(df, x="Czynność", y="Czas_sekundy", color="Czynność",
                         labels={"Czas_sekundy": "Sekundy"})
        st.plotly_chart(fig_box, width='stretch')
    st.divider()
    with st.expander("🔍 Przeszukaj konkretną sesję (Audyt RODO)"):
        search_id = st.text_input("Wklej ID sesji (UUID) z logów:")
        if search_id:
            # Filtrujemy dane po ID
            filtered_df = df[df['ID'].str.contains(search_id, case=False, na=False)]
            if not filtered_df.empty:
                st.dataframe(filtered_df[["ID", "Godzina", "Czynność", "Czas_sekundy"]], width='stretch')
                total_session_time = filtered_df['Czas_sekundy'].sum()
                st.success(f"Łączny czas przetwarzania dla tej sesji: {round(total_session_time, 2)}s")
            else:
                st.warning("Nie znaleziono sesji o takim ID.")
    # 3. Surowe dane pod spodem
    with st.expander("📄 Zobacz surowe dane z logów"):
        st.dataframe(df[["Godzina", "Czynność", "Czas_sekundy"]].tail(20), width='stretch')

else:
    st.warning("Plik app.log jest pusty lub nie zawiera poprawnych danych o czasie.")
    st.write("Wskazówka: Wygeneruj notatkę w głównej aplikacji, aby zasilić logi danymi.")