#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Aplikacja Streamlit do zarządzania stawkowaniem kuponów zakładów.

Interfejs webowy dla systemu automatycznego wyliczania rekomendowanych stawek
według strategii Martingale z celem odzyskania wkładu + 100 zł zysku.
"""

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import os
import math

# Import naszych modułów
from business_logic import (
    recompute_aggregates, get_current_status, recommend_stake,
    calculate_potential_result, get_next_coupon_number, format_currency,
    get_game_status, validate_odds, validate_stake, parse_float,
    validate_withdrawal, create_deposit_coupon, create_withdrawal_coupon,
    get_transaction_history, PROFIT_TARGET, delete_coupon, delete_coupons,
    edit_coupon, save_profit_target, load_profit_target, validate_budget_for_stake
)
from csv_handler import (
    load_rows, save_rows, migrate_old_format, create_empty_csv,
    backup_csv, validate_csv_structure, get_csv_info, CSV_FILE,
    create_empty_template_csv, load_csv_from_string, save_csv_to_string,
    validate_csv_content
)

# ============================================================================
# FUNKCJE TRYBU SESJI
# ============================================================================

def get_session_data():
    """Pobiera dane z session_state lub zwraca pustą listę."""
    if 'coupons_data' not in st.session_state:
        st.session_state.coupons_data = []
    return st.session_state.coupons_data

def save_session_data(rows):
    """Zapisuje dane do session_state."""
    st.session_state.coupons_data = rows

def clear_session_data():
    """Czyści dane z session_state."""
    if 'coupons_data' in st.session_state:
        del st.session_state.coupons_data

def load_csv_from_upload(uploaded_file):
    """Wczytuje dane CSV z przesłanego pliku."""
    try:
        # Konwertuj bytes na string
        csv_content = uploaded_file.read().decode('utf-8')
        
        # Waliduj zawartość
        is_valid, error_message = validate_csv_content(csv_content)
        if not is_valid:
            st.error(f"❌ Błąd w pliku CSV: {error_message}")
            return []
        
        # Wczytaj dane
        rows = load_csv_from_string(csv_content)
        return rows
    except Exception as e:
        st.error(f"❌ Błąd podczas wczytywania pliku: {e}")
        return []

def get_csv_download_data(rows):
    """Przygotowuje dane CSV do pobrania."""
    return save_csv_to_string(rows)

# Funkcje pomocnicze
def is_pending(row) -> bool:
    """Sprawdza czy kupon oczekuje na rozliczenie"""
    val = str(row.get("Wynik", "")).strip().upper()
    return val in {"OCZEKUJE", ""}  # obsługuje stare rekordy z pustym Wynik

def color_result(val):
    """Koloruje wyniki kuponów w tabeli"""
    v = str(val).strip().upper()
    if v in ("WYGRANA", "W"):
        return 'background-color: #d4edda; color: #155724;'
    elif v in ("PRZEGRANA", "P"):
        return 'background-color: #f8d7da; color: #721c24;'
    else:
        return 'background-color: #fff3cd; color: #856404;'


# ============================================================================
# KONFIGURACJA STRAMLIT
# ============================================================================

st.set_page_config(
    page_title="🎰 Stawkowanie Kuponów",
    page_icon="🎰",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================================
# FUNKCJE WYŚWIETLANIA
# ============================================================================

def display_status_cards(status: dict):
    """Wyświetla karty ze statusem gry."""
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "💰 Wkład",
            f"{format_currency(status['sum_deposits'])}",
            delta=f"Saldo: {format_currency(status['balance'])}"
        )
    
    with col2:
        # Koloruj budżet w zależności od wartości
        budget_value = status['budget']
        if budget_value <= 0:
            st.metric(
                "🎯 Budżet",
                f"0.00 zł",
                delta="⚠️ WYKORZYSTANY - Zasil konto!"
            )
        else:
            st.metric(
                "🎯 Budżet",
                f"{format_currency(budget_value)}",
                delta=f"Cel: {format_currency(status['target'])}"
            )
    
    with col3:
        delta = status['target'] - status['budget']
        st.metric(
            "🎯 Cel",
            f"{format_currency(status['target'])}",
            delta=f"Do celu: {format_currency(delta)}"
        )
    
    with col4:
        st.metric(
            "📊 Zysk netto",
            f"{format_currency(status['net_profit'])}",
            delta=f"Cel: {format_currency(st.session_state.profit_target)}"
        )


def display_coupons_table(rows: list):
    """
    Wyświetla tabelę kuponów.
    """
    if not rows:
        st.info("📋 Brak kuponów w bazie danych.")
        return
    
    # Konwertuj na DataFrame dla lepszego wyświetlania
    df = pd.DataFrame(rows)
    
    # Dodaj kolumny z kolorami dla lepszej czytelności
    styled_df = df.style.map(color_result, subset=['Wynik'])
    
    st.dataframe(
        styled_df,
        use_container_width=True,
        height=400
    )


def display_game_status(status: dict):
    """
    Wyświetla status gry.
    """
    game_status = get_game_status(status['balance'], status['sum_deposits'])
    
    if status['balance'] < 0:
        st.warning(f"⚠️ {game_status}")
    elif status['balance'] > 0:
        st.success(f"✅ {game_status}")
    else:
        st.info(f"ℹ️ {game_status}")


# ============================================================================
# GŁÓWNA FUNKCJA
# ============================================================================

def main():
    """Główna funkcja aplikacji."""
    
    # Inicjalizuj profit_target w session_state z pliku
    if 'profit_target' not in st.session_state:
        st.session_state.profit_target = load_profit_target()
    
    # Nagłówek aplikacji
    st.title("🎰 Aplikacja do Stawkowania Kuponów")
    st.caption(f"🎯 Docelowy zysk: {st.session_state.profit_target} zł")
    
    # Pobierz dane z session_state
    rows = get_session_data()
    
    # Interfejs do pobierania i wczytywania plików CSV
    if not rows:
        st.header("📁 Zarządzanie danymi")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("📥 Wczytaj dane")
            uploaded_file = st.file_uploader(
                "Wybierz plik CSV z danymi kuponów",
                type=['csv'],
                help="Wczytaj swój plik CSV z danymi kuponów"
            )
            
            if uploaded_file is not None:
                if st.button("📂 Wczytaj plik", type="primary"):
                    rows = load_csv_from_upload(uploaded_file)
                    if rows:
                        # Przelicz agregaty po wczytaniu danych
                        recompute_aggregates(rows)
                        save_session_data(rows)
                        st.success(f"✅ Wczytano {len(rows)} kuponów z pliku")
                        st.rerun()
        
        with col2:
            st.subheader("📤 Pobierz szablon")
            st.info("Jeśli nie masz jeszcze pliku z danymi, pobierz pusty szablon CSV")
            
            # Przygotuj pusty szablon do pobrania
            empty_csv = create_empty_template_csv()
            
            st.download_button(
                label="📥 Pobierz pusty szablon CSV",
                data=empty_csv,
                file_name="szablon_kuponow.csv",
                mime="text/csv",
                help="Pobierz pusty szablon CSV, wypełnij go danymi i wczytaj z powrotem"
            )
        
        st.markdown("---")
    
    # Jeśli brak danych, pokaż formularz pierwszego kuponu
    if not rows:
        st.header("🎲 Utwórz pierwszy kupon")
        st.info("Witaj! Aby rozpocząć, utwórz pierwszy kupon.")
        
        with st.form("first_coupon_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                deposit = st.number_input(
                    "Początkowy wkład",
                    min_value=0.01,
                    step=0.01,
                    value=100.0,
                    format="%.2f"
                )
            
            with col2:
                st.subheader("🎲 Szczegóły pierwszego kuponu")
            
            # Pole nazwy
            coupon_name = st.text_input(
                "Nazwa kuponu",
                placeholder="np. Mecz Real vs Barcelona",
                help="Wpisz opisową nazwę dla tego kuponu"
            )
            
            col1, col2 = st.columns(2)
            
            with col1:
                odds = st.number_input(
                    "Kurs",
                    min_value=1.01,
                    step=0.01,
                    value=2.5,
                    format="%.2f"
                )
            
            with col2:
                stake = st.number_input(
                    "Stawka",
                    min_value=0.01,
                    step=0.01,
                    value=10.0,
                    format="%.2f"
                )
            
            submitted = st.form_submit_button("✅ Utwórz pierwszy kupon", type="primary")
            
            if submitted:
                if not validate_odds(odds):
                    st.error("❌ Kurs musi być większy niż 1.0!")
                elif not validate_stake(stake):
                    st.error("❌ Stawka musi być większa niż 0!")
                else:
                    # Utwórz pierwszy kupon
                    first_coupon = {
                        "Kupon": "1",
                        "Nazwa": coupon_name if coupon_name.strip() else "Kupon #1",
                        "Wynik": "OCZEKUJE",
                        "Stawka (S)": f"{stake:.2f}",
                        "Kurs": f"{odds:.2f}",
                        "Zasilenie": f"{deposit:.2f}",
                        "Suma zasieleń": "0.00",
                        "Suma włożona do tej pory": "0.00",
                        "Wygrana brutto": "0.00",
                        "Saldo": "0.00",
                        "Zysk netto": "0.00"
                    }
                    
                    rows = [first_coupon]
                    recompute_aggregates(rows)
                    save_session_data(rows)
                    st.success("✅ Pierwszy kupon utworzony!")
                    st.rerun()
        
        return
    
    # Oblicz aktualny status
    status = get_current_status(rows, st.session_state.profit_target)
    
    if not status:
        st.error("❌ Błąd podczas obliczania statusu gry.")
        return
    
    # Wyświetl status gry
    st.header("📊 Bieżący stan gry")
    display_status_cards(status)
    display_game_status(status)
    
    # Dodatkowe ostrzeżenie gdy budżet jest 0
    if status['budget'] <= 0:
        st.error("🚨 **UWAGA!** Wykorzystałeś cały dostępny budżet! Nie możesz grać dalej bez zasilenia konta.")
        st.info("💡 **Co robić:** Zasil konto w sekcji 'Zarządzanie środkami' w sidebar, aby kontynuować grę.")
    
    # A) KUPONY OCZEKUJĄCE - lista wszystkich oczekujących z przyciskami rozliczania
    pending_coupons = [row for row in rows if is_pending(row)]
    
    if pending_coupons:
        st.header("⏳ Kupony oczekujące na rozliczenie")
        
        for coupon in pending_coupons:
            coupon_name = coupon.get('Nazwa', f"Kupon #{coupon['Kupon']}")
            with st.expander(
                f"{coupon_name} – kurs {coupon['Kurs']} – stawka {coupon['Stawka (S)']} zł",
                expanded=False
            ):
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.write(f"**Kurs:** {coupon['Kurs']}")
                    st.write(f"**Stawka:** {coupon['Stawka (S)']} zł")
                
                with col2:
                    potential_win = float(coupon['Kurs']) * float(coupon['Stawka (S)'])
                    st.write(f"**Potencjalna wygrana brutto:** {potential_win:.2f} zł")
                
                with col3:
                    if st.button("✅ Wygrana", key=f"win_{coupon['Kupon']}"):
                        coupon['Wynik'] = 'WYGRANA'   # pełne słowo
                        recompute_aggregates(rows)
                        save_session_data(rows)
                        st.success("✅ Kupon rozliczony jako WYGRANA")
                        st.rerun()
                    
                    if st.button("❌ Przegrana", key=f"lose_{coupon['Kupon']}"):
                        coupon['Wynik'] = 'PRZEGRANA' # pełne słowo
                        coupon['Wygrana brutto'] = "0.00"
                        recompute_aggregates(rows)
                        save_session_data(rows)
                        st.success("❌ Kupon rozliczony jako PRZEGRANA")
                        st.rerun()
                    
                    if st.button("🗑️ Usuń", key=f"delete_{coupon['Kupon']}", type="secondary"):
                        if delete_coupon(rows, coupon['Kupon']):
                            recompute_aggregates(rows)
                            save_session_data(rows)
                            st.success(f"✅ Usunięto kupon #{coupon['Kupon']}")
                            st.rerun()
                        else:
                            st.error(f"❌ Nie udało się usunąć kuponu #{coupon['Kupon']}")
        
        st.markdown("---")
    
    # B) DODAWANIE NOWEGO KUPONU - przycisk zawsze dostępny
    if st.button("🎲 Nowy kupon", type="primary", use_container_width=True):
        st.session_state.show_new_coupon = True
        st.rerun()
    
    # Uniwersalny formularz dodawania kuponu
    if st.session_state.get('show_new_coupon', False):
        st.header("🎲 Dodaj nowy kupon")
        
        # Pola POZA formularzem - automatyczne odświeżanie
        col1, col2 = st.columns(2)
        
        with col1:
            odds = st.number_input(
                "Kurs",
                min_value=1.01,
                step=0.01,
                value=2.5,
                format="%.2f",
                key="odds_universal"
            )
        
        with col2:
            # Pole własnej stawki
            custom_stake = st.number_input(
                "Własna stawka",
                min_value=0.01,
                step=0.01,
                value=10.0,
                format="%.2f",
                key="custom_stake_universal"
            )
        
        # Oblicz rekomendowaną stawkę jeśli jesteśmy na minusie
        recommended_stake = None
        if status['net_profit'] < st.session_state.profit_target:
            try:
                recommended_stake = recommend_stake(status['budget'], status['target'], odds, st.session_state.profit_target)
            except:
                recommended_stake = None
        
        # Pokaż rekomendację jeśli jesteśmy na minusie
        if recommended_stake is not None:
            st.info(f"💰 Rekomendowana stawka: {recommended_stake:.2f} zł")
        else:
            st.info("✅ Jesteś na plusie - możesz grać własną stawką")
        
        # Pokaż potencjalny wynik i sprawdź budżet
        if custom_stake > 0 and odds > 1:
            potential_win = odds * custom_stake
            potential_profit = custom_stake * (odds - 1)
            new_budget = status['budget'] - custom_stake + potential_win
            
            # Sprawdź czy stawka jest w budżecie
            budget_valid, budget_message = validate_budget_for_stake(rows, custom_stake)
            
            if budget_valid:
                st.metric(
                    "💡 Potencjalny wynik",
                    f"{potential_win:.2f} zł",
                    delta=f"Zysk: {format_currency(potential_profit)}"
                )
                st.caption(f"Nowy budżet po wygranej: {new_budget:.2f} zł")
                st.success(budget_message)
            else:
                st.metric(
                    "💡 Potencjalny wynik",
                    f"{potential_win:.2f} zł",
                    delta=f"Zysk: {format_currency(potential_profit)}"
                )
                st.caption(f"Nowy budżet po wygranej: {new_budget:.2f} zł")
                st.error(budget_message)
                st.warning("⚠️ Nie możesz grać tą stawką - przekracza dostępny budżet!")
        
        # Formularz z przyciskami
        with st.form("add_coupon_universal"):
            # Pole nazwy
            coupon_name = st.text_input(
                "Nazwa kuponu",
                placeholder="np. Mecz Real vs Barcelona",
                help="Wpisz opisową nazwę dla tego kuponu",
                key="name_universal"
            )
            
            # Opcjonalne zasilenie
            deposit = st.number_input(
                "Zasilenie (opcjonalnie)",
                min_value=0.0,
                step=0.01,
                value=0.0,
                format="%.2f",
                key="deposit_universal"
            )
            
            # Przyciski w zależności od statusu
            if recommended_stake is not None:
                col_btn1, col_btn2 = st.columns(2)
                
                with col_btn1:
                    use_recommended = st.form_submit_button(
                        f"✅ Użyj rekomendowanej stawki ({recommended_stake:.2f} zł)",
                        type="primary"
                    )
                
                with col_btn2:
                    use_custom = st.form_submit_button(
                        f"🎯 Użyj własnej stawki ({custom_stake:.2f} zł)",
                        type="secondary"
                    )
                
                # Wybierz stawkę na podstawie klikniętego przycisku
                if use_recommended:
                    stake = recommended_stake
                    submitted = True
                elif use_custom:
                    stake = custom_stake
                    submitted = True
                else:
                    stake = custom_stake  # domyślnie własna stawka
                    submitted = False
            else:
                # Jesteśmy na plusie - tylko własna stawka
                stake = custom_stake
                submitted = st.form_submit_button("✅ Dodaj kupon", type="primary")
            
            # Logika dodawania kuponu
            if submitted:
                if not validate_odds(odds):
                    st.error("❌ Kurs musi być większy niż 1.0!")
                elif not validate_stake(stake):
                    st.error("❌ Stawka musi być większa niż 0!")
                else:
                    # Sprawdź czy stawka nie przekracza budżetu
                    budget_valid, budget_message = validate_budget_for_stake(rows, stake)
                    
                    if not budget_valid:
                        st.error(budget_message)
                        # Pokaż opcję zasilenia
                        if deposit > 0:
                            st.info("💡 Możesz zasilić konto w polu 'Zasilenie' poniżej")
                        else:
                            st.info("💡 Zwiększ budżet poprzez zasilenie konta w sekcji 'Zarządzanie środkami'")
                    else:
                        # Walidacja przeszła - dodaj kupon
                        next_number = get_next_coupon_number(rows)
                        
                        new_coupon = {
                            "Kupon": str(next_number),
                            "Nazwa": coupon_name if coupon_name.strip() else f"Kupon #{next_number}",
                            "Wynik": "OCZEKUJE",
                            "Stawka (S)": f"{stake:.2f}",
                            "Kurs": f"{odds:.2f}",
                            "Zasilenie": f"{deposit:.2f}",
                            "Suma zasieleń": "0.00",
                            "Suma włożona do tej pory": "0.00",
                            "Wygrana brutto": "0.00",
                            "Saldo": "0.00",
                            "Zysk netto": "0.00"
                        }
                        
                        rows.append(new_coupon)
                        recompute_aggregates(rows)
                        save_session_data(rows)
                        
                        st.success(f"✅ Dodano kupon #{next_number}")
                        st.success(budget_message)  # Pokaż potwierdzenie budżetu
                        st.session_state.show_new_coupon = False
                        st.rerun()
    
    # Wyświetl tabelę kuponów
    st.header("📋 Historia kuponów")
    display_coupons_table(rows)
    
    # Dodatkowe opcje w sidebar
    with st.sidebar:
        st.markdown("---")
        st.subheader("💰 Zarządzanie środkami")
        
        # Wpłata
        with st.expander("💵 Wpłata", expanded=False):
            with st.form("deposit_form"):
                deposit_amount = st.number_input(
                    "Kwota wpłaty",
                    min_value=0.01,
                    step=0.01,
                    value=100.0,
                    format="%.2f"
                )
                
                if st.form_submit_button("💰 Wpłać", type="primary"):
                    next_number = get_next_coupon_number(rows)
                    deposit_coupon = create_deposit_coupon(deposit_amount, next_number)
                    
                    rows.append(deposit_coupon)
                    recompute_aggregates(rows)
                    save_session_data(rows)
                    st.success(f"✅ Wpłacono {deposit_amount:.2f} zł")
                    st.rerun()
        
        # Wypłata
        with st.expander("💸 Wypłata", expanded=False):
            with st.form("withdrawal_form"):
                withdrawal_amount = st.number_input(
                    "Kwota wypłaty",
                    min_value=0.01,
                    step=0.01,
                    value=100.0,
                    format="%.2f"
                )
                
                if st.form_submit_button("💸 Wypłać", type="primary"):
                    # Pobierz aktualny budżet
                    status = get_current_status(rows, st.session_state.profit_target)
                    if not status:
                        st.error("❌ Błąd podczas obliczania statusu budżetu")
                    else:
                        # Waliduj wypłatę
                        validation_result = validate_withdrawal(status['budget'], withdrawal_amount)
                        if validation_result['valid']:
                            next_number = get_next_coupon_number(rows)
                            withdrawal_coupon = create_withdrawal_coupon(withdrawal_amount, next_number)
                            
                            rows.append(withdrawal_coupon)
                            recompute_aggregates(rows)
                            save_session_data(rows)
                            st.success(f"✅ Wypłacono {withdrawal_amount:.2f} zł")
                            st.rerun()
                        else:
                            st.error(f"❌ {validation_result['error']}")
        
        # Zmiana celu
        with st.expander("🎯 Zmiana celu", expanded=False):
            with st.form("target_form"):
                new_target = st.number_input(
                    "Nowy cel zysku",
                    min_value=1.0,
                    step=1.0,
                    value=st.session_state.profit_target,
                    format="%.0f"
                )
                
                if st.form_submit_button("🎯 Zmień cel", type="primary"):
                    st.session_state.profit_target = new_target
                    if save_profit_target(new_target):
                        st.success(f"✅ Cel zmieniony na {new_target:.0f} zł i zapisany")
                    else:
                        st.error("❌ Błąd podczas zapisywania celu")
                    st.rerun()
        
        # Historia transakcji
        with st.expander("📊 Historia transakcji", expanded=False):
            transactions = get_transaction_history(rows)
            if transactions:
                for transaction in transactions[-5:]:  # Ostatnie 5 transakcji
                    if transaction['type'] == 'deposit':
                        st.success(f"💰 {transaction['description']} (Kupon #{transaction['coupon']})")
                    else:
                        st.warning(f"💸 {transaction['description']} (Kupon #{transaction['coupon']})")
            else:
                st.info("Brak transakcji")
        
        st.markdown("---")
        st.subheader("🗑️ Zarządzanie kuponami")
        
        # Edytuj kupon
        with st.expander("✏️ Edytuj kupon", expanded=False):
            if rows:
                # Lista kuponów oczekujących na rozliczenie
                pending_coupons = [row for row in rows if is_pending(row)]
                
                if pending_coupons:
                    with st.form("edit_coupon_form"):
                        # Wybór kuponu do edycji
                        selected_coupon = st.selectbox(
                            "Wybierz kupon do edycji:",
                            [row['Kupon'] for row in pending_coupons],
                            format_func=lambda x: next((row['Nazwa'] for row in pending_coupons if row['Kupon'] == x), f"Kupon #{x}"),
                            key="edit_coupon_select"
                        )
                        
                        # Znajdź wybrany kupon
                        coupon_to_edit = next((row for row in pending_coupons if row['Kupon'] == selected_coupon), None)
                        
                        if coupon_to_edit:
                            col1, col2 = st.columns(2)
                            
                            with col1:
                                new_name = st.text_input(
                                    "Nazwa kuponu",
                                    value=coupon_to_edit.get('Nazwa', ''),
                                    key="edit_name"
                                )
                                new_stake = st.number_input(
                                    "Stawka",
                                    min_value=0.01,
                                    step=0.01,
                                    value=float(coupon_to_edit.get('Stawka (S)', 0)),
                                    format="%.2f",
                                    key="edit_stake"
                                )
                            
                            with col2:
                                new_odds = st.number_input(
                                    "Kurs",
                                    min_value=1.01,
                                    step=0.01,
                                    value=float(coupon_to_edit.get('Kurs', 1.01)),
                                    format="%.2f",
                                    key="edit_odds"
                                )
                            
                            if st.form_submit_button("✅ Zapisz zmiany", type="primary"):
                                if edit_coupon(rows, selected_coupon, new_name, new_stake, new_odds):
                                    recompute_aggregates(rows)
                                    save_session_data(rows)
                                    st.success(f"✅ Kupon #{selected_coupon} został edytowany")
                                    st.rerun()
                                else:
                                    st.error("❌ Nie udało się edytować kuponu")
                else:
                    st.info("Brak kuponów oczekujących na rozliczenie")
            else:
                st.info("Brak kuponów w bazie danych")
        
        # Usuń ostatni kupon
        if rows:
            last_coupon = rows[-1]
            last_coupon_name = last_coupon.get('Nazwa', f"#{last_coupon['Kupon']}")
            if st.button(f"🗑️ Usuń ostatni kupon ({last_coupon_name})", type="secondary", use_container_width=True):
                if delete_coupon(rows, last_coupon['Kupon']):
                    recompute_aggregates(rows)
                    save_session_data(rows)
                    st.success(f"✅ Usunięto kupon #{last_coupon['Kupon']}")
                    st.rerun()
                else:
                    st.error(f"❌ Nie udało się usunąć kuponu #{last_coupon['Kupon']}")
        
        # Usuń wybrane kupony
        with st.expander("🗑️ Usuń wybrane kupony", expanded=False):
            if rows:
                with st.form("delete_multiple_form"):
                    # Lista wszystkich kuponów
                    coupon_numbers = [row["Kupon"] for row in rows]
                    selected_coupons = st.multiselect(
                        "Wybierz kupony do usunięcia:",
                        coupon_numbers,
                        format_func=lambda x: next((row['Nazwa'] for row in rows if row['Kupon'] == x), f"Kupon #{x}"),
                        key="delete_multiple_sidebar"
                    )
                    
                    if selected_coupons:
                        st.warning(f"⚠️ Zaznaczono {len(selected_coupons)} kuponów do usunięcia")
                    
                    # Przycisk submit zawsze dostępny
                    submitted = st.form_submit_button("🗑️ Usuń zaznaczone", type="secondary")
                    
                    if submitted and selected_coupons:
                        deleted_count = delete_coupons(rows, selected_coupons)
                        if deleted_count > 0:
                            recompute_aggregates(rows)
                            save_session_data(rows)
                            st.success(f"✅ Usunięto {deleted_count} kuponów")
                            st.rerun()
                        else:
                            st.error("❌ Nie udało się usunąć żadnego kuponu")
                    elif submitted and not selected_coupons:
                        st.warning("⚠️ Wybierz kupony do usunięcia")
            else:
                st.info("Brak kuponów w bazie danych")
        
        st.markdown("---")
        st.subheader("📁 Zarządzanie plikami")
        
        # Przycisk do pobrania aktualnych danych
        if rows:
            csv_data = get_csv_download_data(rows)
            st.download_button(
                label="📥 Pobierz dane CSV",
                data=csv_data,
                file_name=f"kupony_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                help="Pobierz aktualne dane kuponów jako plik CSV"
            )
        
        # Przycisk do wczytania nowego pliku
        with st.expander("📂 Wczytaj nowy plik CSV", expanded=False):
            new_uploaded_file = st.file_uploader(
                "Wybierz nowy plik CSV",
                type=['csv'],
                help="Wczytaj nowy plik CSV (zastąpi obecne dane)",
                key="new_file_uploader"
            )
            
            if new_uploaded_file is not None:
                if st.button("🔄 Zastąp dane nowym plikiem", type="secondary"):
                    new_rows = load_csv_from_upload(new_uploaded_file)
                    if new_rows:
                        # Przelicz agregaty po wczytaniu danych
                        recompute_aggregates(new_rows)
                        save_session_data(new_rows)
                        st.success(f"✅ Zastąpiono dane - wczytano {len(new_rows)} kuponów")
                        st.rerun()
        
        st.markdown("---")
        st.subheader("🔧 Opcje")
        
        if st.button("💾 Utwórz backup"):
            backup_name = backup_csv()
            if backup_name:
                st.success(f"✅ Backup utworzony: {backup_name}")
        
        if st.button("🗑️ Wyczyść bazę danych"):
            st.session_state.show_delete_confirm = True
        
        if st.session_state.get('show_delete_confirm', False):
            st.warning("⚠️ Czy na pewno chcesz wyczyścić bazę danych? Ta operacja jest nieodwracalna!")
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("✅ Tak, usuń", type="primary"):
                    clear_session_data()
                    st.success("✅ Baza danych wyczyszczona")
                    st.session_state.show_delete_confirm = False
                    st.rerun()
            
            with col2:
                if st.button("❌ Anuluj", type="secondary"):
                    st.session_state.show_delete_confirm = False
                    st.rerun()


if __name__ == "__main__":
    main()