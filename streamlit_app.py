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
    get_transaction_history, PROFIT_TARGET, delete_coupon, delete_coupons
)
from csv_handler import (
    load_rows, save_rows, migrate_old_format, create_empty_csv,
    backup_csv, validate_csv_structure, get_csv_info, CSV_FILE
)

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
    page_icon="🎲",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Ukryj domyślny footer Streamlit
hide_streamlit_style = """
<style>
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
</style>
"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True)


# ============================================================================
# FUNKCJE POMOCNICZE UI
# ============================================================================

def format_currency_streamlit(amount: float, color: str = None) -> str:
    """
    Formatuje kwotę z kolorami dla Streamlit.
    """
    if amount >= 0:
        prefix = "+"
        default_color = "green"
    else:
        prefix = ""
        default_color = "red"
    
    color = color or default_color
    formatted = f"{prefix}{amount:.2f} zł"
    
    return f'<span style="color: {color};">{formatted}</span>'


def display_status_cards(status: dict):
    """
    Wyświetla karty ze statusem gry.
    """
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "💵 Wkład",
            f"{status['sum_deposits']:.2f} zł",
            delta=None
        )
    
    with col2:
        balance = status['balance']
        st.metric(
            "📊 Saldo",
            format_currency(balance),
            delta=f"{format_currency(balance)}"
        )
    
    with col3:
        budget = status['budget']
        st.metric(
            "💳 Budżet",
            f"{budget:.2f} zł",
            delta=None
        )
    
    with col4:
        net_profit = status['net_profit']
        target = status['target']
        delta = target - status['budget']
        st.metric(
            "🎯 Cel",
            f"{target:.2f} zł",
            delta=f"Do celu: {format_currency(delta)}"
        )


def display_coupons_table(rows: list):
    """
    Wyświetla tabelę kuponów z opcjami usuwania.
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
    
    # Sekcja usuwania kuponów
    st.markdown("---")
    st.subheader("🗑️ Zarządzanie kuponami")
    
    # Opcja usuwania pojedynczego kuponu
    st.markdown("**Usuń pojedynczy kupon:**")
    col1, col2 = st.columns([2, 1])
    
    with col1:
        coupon_numbers = [row["Kupon"] for row in rows]
        selected_coupon = st.selectbox(
            "Wybierz kupon do usunięcia:",
            coupon_numbers,
            format_func=lambda x: next((row['Nazwa'] for row in rows if row['Kupon'] == x), f"Kupon #{x}"),
            key="delete_single_coupon"
        )
    
    with col2:
        if st.button("🗑️ Usuń kupon", type="secondary", key="delete_single_btn"):
            if delete_coupon(rows, selected_coupon):
                recompute_aggregates(rows)
                save_rows(rows)
                st.success(f"✅ Usunięto kupon #{selected_coupon}")
                st.rerun()
            else:
                st.error(f"❌ Nie znaleziono kuponu #{selected_coupon}")
    
    # Opcja usuwania wielu kuponów
    st.markdown("**Usuń wiele kuponów:**")
    
    # Lista do wyboru wielu kuponów
    selected_coupons = st.multiselect(
        "Wybierz kupony do usunięcia:",
        coupon_numbers,
        format_func=lambda x: next((row['Nazwa'] for row in rows if row['Kupon'] == x), f"Kupon #{x}"),
        key="delete_multiple_coupons"
    )
    
    if selected_coupons:
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.warning(f"⚠️ Zaznaczono {len(selected_coupons)} kuponów do usunięcia")
        
        with col2:
            if st.button("🗑️ Usuń zaznaczone", type="secondary", key="delete_multiple_btn"):
                deleted_count = delete_coupons(rows, selected_coupons)
                if deleted_count > 0:
                    recompute_aggregates(rows)
                    save_rows(rows)
                    st.success(f"✅ Usunięto {deleted_count} kuponów")
                    st.rerun()
                else:
                    st.error("❌ Nie udało się usunąć żadnego kuponu")


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
        st.info(f"➖ {game_status}")


# ============================================================================
# GŁÓWNA APLIKACJA
# ============================================================================

def main():
    """
    Główna funkcja aplikacji Streamlit.
    """
    # Nagłówek
    st.title("🎰 Aplikacja do Stawkowania Kuponów")
    st.markdown("---")
    
    # Inicjalizuj sesję NAJPIERW
    if 'profit_target' not in st.session_state:
        st.session_state.profit_target = PROFIT_TARGET
    
    # Sidebar z informacjami
    with st.sidebar:
        st.header("📊 Informacje")
        
        # Informacje o pliku CSV
        csv_info = get_csv_info()
        if csv_info['exists']:
            st.success("✅ Baza danych załadowana")
            st.caption(f"Kupony: {csv_info['rows_count']}")
            st.caption(f"Ostatnia modyfikacja: {csv_info['last_modified'].strftime('%Y-%m-%d %H:%M') if csv_info['last_modified'] else 'Nieznana'}")
        else:
            st.warning("⚠️ Brak bazy danych")
        
        st.markdown("---")
        st.caption(f"🎯 Docelowy zysk: {st.session_state.profit_target} zł")
        st.caption(f"📁 Plik: {CSV_FILE}")
    
    # Wczytaj dane
    rows = load_rows()
    
    # Sprawdź czy to stary format i wymagaj migracji
    if rows and not validate_csv_structure(rows):
        st.error("❌ Nieprawidłowy format pliku CSV!")
        st.stop()
    
    # Główna sekcja aplikacji
    if not rows:
        # Brak danych - utwórz pierwszy kupon
        st.header("🎯 Tworzenie pierwszego kuponu")
        
        with st.form("first_coupon"):
            st.subheader("💰 Ustal początkowy kapitał")
            deposit = st.number_input(
                "Ile pieniędzy wpłacasz na start?",
                min_value=0.0,
                step=0.01,
                value=100.0,
                format="%.2f"
            )
            
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
                    save_rows(rows)
                    
                    st.success("✅ Utworzono pierwszy kupon!")
                    st.rerun()
    else:
        # Istnieją dane - główny interfejs
        recompute_aggregates(rows)
        status = get_current_status(rows, st.session_state.profit_target)
        
        # Wyświetl status gry
        st.header("📊 Bieżący stan gry")
        display_status_cards(status)
        display_game_status(status)
        
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
                            save_rows(rows)
                            st.success("✅ Kupon rozliczony jako WYGRANA")
                            st.rerun()
                        
                        if st.button("❌ Przegrana", key=f"lose_{coupon['Kupon']}"):
                            coupon['Wynik'] = 'PRZEGRANA' # pełne słowo
                            coupon['Wygrana brutto'] = "0.00"
                            recompute_aggregates(rows)
                            save_rows(rows)
                            st.success("❌ Kupon rozliczony jako PRZEGRANA")
                            st.rerun()
                        
                        if st.button("🗑️ Usuń", key=f"delete_{coupon['Kupon']}", type="secondary"):
                            if delete_coupon(rows, coupon['Kupon']):
                                recompute_aggregates(rows)
                                save_rows(rows)
                                st.success(f"✅ Usunięto kupon #{coupon['Kupon']}")
                                st.rerun()
                            else:
                                st.error(f"❌ Nie udało się usunąć kuponu #{coupon['Kupon']}")
            
            st.markdown("---")
        # B) DODAWANIE NOWEGO KUPONU - przycisk zawsze dostępny
        if st.button("🎲 Nowy kupon", type="primary", use_container_width=True):
            st.session_state.show_new_coupon = True
            st.rerun()
        
        if st.session_state.get('show_new_coupon', False):
            # Sprawdź czy osiągnięto cel
            if status['net_profit'] >= st.session_state.profit_target:
                st.header("🎉 Gratulacje!")
                st.success(f"""
                **Osiągnąłeś cel!**
                - Zysk netto: {format_currency(status['net_profit'])}
                - Odzyskałeś cały wkład + {st.session_state.profit_target} zł zysku
                """)
                
                # Sprawdź czy pokazać formularz dodawania kuponu
                if st.session_state.get('show_new_coupon', False):
                    st.subheader("🎲 Dodaj kolejny kupon (bez rekomendacji)")
                
                if st.session_state.get('show_new_coupon', False):
                    with st.form("add_coupon_no_rec"):
                        # Pole nazwy
                        coupon_name = st.text_input(
                            "Nazwa kuponu",
                            placeholder="np. Mecz Real vs Barcelona",
                            help="Wpisz opisową nazwę dla tego kuponu",
                            key="name_no_rec"
                        )
                        
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            odds = st.number_input(
                                "Kurs",
                                min_value=1.01,
                                step=0.01,
                                value=2.5,
                                format="%.2f",
                                key="odds_no_rec"
                            )
                        
                        with col2:
                            game_style = st.session_state.get('game_style', 'Własna stawka')
                        
                        if game_style == "Rekomendowana stawka":
                            stake = st.number_input(
                                "Stawka",
                                min_value=0.01,
                                step=0.01,
                                value=10.0,
                                format="%.2f",
                                key="stake_no_rec"
                            )
                        else:
                            stake = st.number_input(
                                "Własna stawka",
                                min_value=0.01,
                                step=0.01,
                                value=10.0,
                                format="%.2f",
                                key="stake_no_rec_custom"
                            )
                        
                        # Pokaż potencjalny wynik na żywo
                        if stake > 0 and odds > 1:
                            potential_win = odds * stake
                            potential_profit = stake * (odds - 1)
                            new_budget = status['budget'] - stake + potential_win
                            
                            st.metric(
                                "💡 Potencjalny wynik",
                                f"{potential_win:.2f} zł",
                                delta=f"Zysk: {format_currency(potential_profit)}"
                            )
                            
                            st.caption(f"Nowy budżet po wygranej: {new_budget:.2f} zł")
                        
                        # Opcjonalne zasilenie
                        deposit = st.number_input(
                            "Zasilenie (opcjonalnie)",
                            min_value=0.0,
                            step=0.01,
                            value=0.0,
                            format="%.2f"
                        )
                        
                        submitted = st.form_submit_button("✅ Dodaj kupon", type="primary")
                    
                        if submitted:
                            if not validate_odds(odds):
                                st.error("❌ Kurs musi być większy niż 1.0!")
                            elif not validate_stake(stake):
                                st.error("❌ Stawka musi być większa niż 0!")
                            else:
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
                                save_rows(rows)
                                
                                st.success(f"✅ Dodano kupon #{next_number}")
                                st.session_state.show_new_coupon = False
                                st.rerun()
            else:
                # Sekcja rozliczania kuponów
                pending_coupons = [row for row in rows if row.get('Wynik', '').strip() == '']
                
                if pending_coupons:
                    st.header("⏳ Kupony oczekujące na rozliczenie")
                    
                    for coupon in pending_coupons:
                        with st.expander(f"Kupon #{coupon['Kupon']} - {coupon['Kurs']} - {coupon['Stawka (S)']} zł", expanded=True):
                            col1, col2, col3 = st.columns(3)
                            
                            with col1:
                                st.write(f"**Kurs:** {coupon['Kurs']}")
                                st.write(f"**Stawka:** {coupon['Stawka (S)']} zł")
                            
                            with col2:
                                potential_win = float(coupon['Kurs']) * float(coupon['Stawka (S)'])
                                st.write(f"**Potencjalna wygrana:** {potential_win:.2f} zł")
                            
                            with col3:
                                if st.button(f"✅ Wygrana", key=f"win_{coupon['Kupon']}"):
                                    # Rozlicz jako wygrana
                                    coupon['Wynik'] = 'W'
                                    recompute_aggregates(rows)
                                    save_rows(rows)
                                    st.success("✅ Kupon rozliczony jako wygrana!")
                                    st.rerun()
                                
                                if st.button(f"❌ Przegrana", key=f"lose_{coupon['Kupon']}"):
                                    # Rozlicz jako przegrana
                                    coupon['Wynik'] = 'P'
                                    recompute_aggregates(rows)
                                    save_rows(rows)
                                    st.success("❌ Kupon rozliczony jako przegrana!")
                                    st.rerun()
                    
                    st.markdown("---")
                    
                    # Sprawdź czy pokazać formularz dodawania kuponu
                    if st.session_state.get('show_new_coupon', False):
                        # Nie osiągnięto celu - rekomendacja stawki
                        st.header("🎲 Dodaj kolejny kupon z rekomendacją")
                        
                        # Pole nazwy
                        coupon_name = st.text_input(
                            "Nazwa kuponu",
                            placeholder="np. Mecz Real vs Barcelona",
                            help="Wpisz opisową nazwę dla tego kuponu",
                            key="name_with_rec_pending"
                        )
                        
                        # Pole kursu POZA formularzem - automatyczne odświeżanie
                        col_odds1, col_odds2 = st.columns([1, 1])
                        
                        with col_odds1:
                            odds = st.number_input(
                                "Kurs kolejnego kuponu",
                                min_value=1.01,
                                step=0.01,
                                value=2.5,
                                format="%.2f",
                                key="odds_with_rec_pending"
                            )
                        
                        with col_odds2:
                            # Oblicz rekomendację na żywo
                            try:
                                recommended = recommend_stake(status['budget'], status['target'], odds, st.session_state.profit_target)
                                
                                st.metric(
                                    "💰 Rekomendowana stawka",
                                    f"{recommended:.2f} zł",
                                    delta=f"Kurs: {odds}"
                                )
                                
                                # Sprawdź czy rekomendacja mieści się w budżecie
                                if recommended > status['budget']:
                                    shortage = recommended - status['budget']
                                    st.warning(f"⚠️ Brakuje {shortage:.2f} zł w budżecie!")
                                    
                                    deposit = st.number_input(
                                        "Zasilenie (pokrycie braku)",
                                        min_value=shortage,
                                        step=0.01,
                                        value=math.ceil(shortage * 100) / 100,
                                        format="%.2f",
                                        key="deposit_with_rec_pending"
                                    )
                                else:
                                    deposit = 0.0
                                    st.success("✅ Rekomendacja mieści się w budżecie")
                                    
                            except ValueError as e:
                                st.error(f"❌ Błąd: {e}")
                                recommended = 0.0
                                deposit = 0.0
                        
                        with st.form("add_coupon_with_rec_pending"):
                            col1, col2 = st.columns(2)
                            
                            with col1:
                                # Wybór stawki na podstawie stylu gry
                                game_style = st.session_state.get('game_style', 'Własna stawka')
                                
                                if game_style == "Rekomendowana stawka":
                                    stake = recommended
                                    st.info(f"💰 Używasz rekomendowanej stawki: {recommended:.2f} zł")
                                else:
                                    stake = st.number_input(
                                        "Własna stawka",
                                        min_value=0.01,
                                        step=0.01,
                                        value=recommended,
                                        format="%.2f",
                                        key="custom_stake_with_rec_pending"
                                    )
                            
                            with col2:
                                # Pokaż informacje o potencjalnym wyniku
                                if game_style == "Rekomendowana stawka":
                                    current_status = get_current_status(rows, st.session_state.profit_target)
                                    if current_status:
                                        budget = current_status['budget']
                                        potential_result = calculate_potential_result(budget, stake, odds, True)
                                        potential_profit = potential_result['profit_loss']
                                        st.metric("Potencjalna wygrana", f"{potential_profit:.2f} zł")
                                        
                                        # Status po wygranej
                                        current_status = get_current_status(rows, st.session_state.profit_target)
                                        if current_status:
                                            budget_after_win = current_status['budget'] + potential_profit
                                            target_after_win = current_status['target']
                                            
                                            if budget_after_win >= target_after_win:
                                                st.success("🎉 Po wygranej osiągniesz cel!")
                                            else:
                                                remaining = target_after_win - budget_after_win
                                                st.info(f"💰 Po wygranej zostanie do celu: {remaining:.2f} zł")
                                else:
                                    st.info("💡 Możesz wpisać własną stawkę w lewej kolumnie")
                            
                            submitted = st.form_submit_button("✅ Dodaj kupon", type="primary")
                        
                            if submitted:
                                if not validate_odds(odds):
                                    st.error("❌ Kurs musi być większy niż 1.0!")
                                elif not validate_stake(stake):
                                    st.error("❌ Stawka musi być większa niż 0!")
                                else:
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
                                    save_rows(rows)
                                    
                                    st.success(f"✅ Dodano kupon #{next_number} ze stawką {stake:.2f} zł")
                                    st.session_state.show_new_coupon = False
                                    st.rerun()
                
                # Sprawdź czy trzeba doładować konto
                if status['budget'] <= 0:
                    st.error("🚨 Budżet wyczerpany! Musisz doładować konto.")
                    
                    with st.form("deposit_money"):
                        deposit = st.number_input(
                            "Ile wpłacasz (zasilenie)?",
                            min_value=0.01,
                            step=0.01,
                            value=100.0,
                            format="%.2f"
                        )
                        
                        if st.form_submit_button("💰 Doładuj konto", type="primary"):
                            # Dodaj zasilenie jako nowy kupon
                            next_number = get_next_coupon_number(rows)
                            
                            deposit_coupon = {
                                "Kupon": str(next_number),
                                "Wynik": "WYGRANA",  # Zasilenie to "wygrana"
                                "Stawka (S)": "0.00",
                                "Kurs": "1.00",
                                "Zasilenie": f"{deposit:.2f}",
                                "Suma zasieleń": "0.00",
                                "Suma włożona do tej pory": "0.00",
                                "Wygrana brutto": "0.00",
                                "Saldo": "0.00",
                                "Zysk netto": "0.00"
                            }
                            
                            rows.append(deposit_coupon)
                            recompute_aggregates(rows)
                            save_rows(rows)
                            
                            st.success(f"✅ Doładowano konto o {deposit:.2f} zł")
                            st.rerun()
                else:
                    # Normalny przepływ z rekomendacją
                    
                    # Pole kursu POZA formularzem - automatyczne odświeżanie
                    col_odds1, col_odds2 = st.columns([1, 1])
                    
                    with col_odds1:
                        odds = st.number_input(
                            "Kurs kolejnego kuponu",
                            min_value=1.01,
                            step=0.01,
                            value=2.5,
                            format="%.2f",
                            key="odds_with_rec"
                        )
                    
                    # Oblicz rekomendację automatycznie
                    with col_odds2:
                        try:
                            recommended = recommend_stake(
                                status['budget'], 
                                status['target'], 
                                odds,
                                st.session_state.profit_target
                            )
                            
                            # Wyświetl rekomendację z potencjalnym wynikiem
                            st.metric(
                                "💡 Rekomendowana stawka",
                                f"{recommended:.2f} zł",
                                delta=f"Potencjalny zysk: {format_currency((odds - 1) * recommended)}"
                            )
                            
                            # Pokaż co się stanie po wygranej
                            potential_budget = status['budget'] - recommended + (odds * recommended)
                            st.info(f"""
                            📊 **Po wygranej będziesz mieć:**
                            - Budżet: {potential_budget:.2f} zł
                            - Cel: {status['target']:.2f} zł
                            - Status: {'🎯 CEL OSIĄGNIĘTY!' if potential_budget >= status['target'] else '📈 Do celu: ' + format_currency(status['target'] - potential_budget)}
                            """)
                            
                            # Sprawdź czy rekomendacja przekracza budżet
                            if recommended > status['budget']:
                                shortage = recommended - status['budget']
                                st.error(f"""
                                🚨 **ALERT!** Rekomendacja przekracza budżet!
                                - Rekomendacja: {recommended:.2f} zł
                                - Budżet: {status['budget']:.2f} zł
                                - Brakuje: {shortage:.2f} zł
                                """)
                                deposit = st.number_input(
                                    "Zasilenie (aby pokryć różnicę)",
                                    min_value=shortage,
                                    step=0.01,
                                    value=math.ceil(shortage * 100) / 100,
                                    format="%.2f",
                                    key="deposit_with_rec"
                                )
                            else:
                                deposit = 0.0
                                st.success("✅ Rekomendacja mieści się w budżecie")
                            
                        except ValueError as e:
                            st.error(f"❌ Błąd: {e}")
                            recommended = 0.0
                            deposit = 0.0
                    
                    if st.session_state.get('show_new_coupon', False):
                        with st.form("add_coupon_with_rec"):
                            col1, col2 = st.columns(2)
                            
                            with col1:
                                # Wybór stawki na podstawie stylu gry
                                game_style = st.session_state.get('game_style', 'Własna stawka')
                                
                                if game_style == "Rekomendowana stawka":
                                    stake = recommended
                                    st.info(f"💰 Używasz rekomendowanej stawki: {recommended:.2f} zł")
                                else:
                                    stake = st.number_input(
                                        "Własna stawka",
                                        min_value=0.01,
                                        step=0.01,
                                        value=recommended,
                                        format="%.2f",
                                        key="custom_stake_with_rec"
                                    )
                            
                            with col2:
                                # Pokaż informacje o potencjalnym wyniku
                                if game_style == "Rekomendowana stawka":
                                    current_status = get_current_status(rows, st.session_state.profit_target)
                                    if current_status:
                                        budget = current_status['budget']
                                        potential_result = calculate_potential_result(budget, stake, odds, True)
                                        potential_profit = potential_result['profit_loss']
                                        st.metric("Potencjalna wygrana", f"{potential_profit:.2f} zł")
                                        
                                        # Status po wygranej
                                        current_status = get_current_status(rows, st.session_state.profit_target)
                                        if current_status:
                                            budget_after_win = current_status['budget'] + potential_profit
                                            target_after_win = current_status['target']
                                            
                                            if budget_after_win >= target_after_win:
                                                st.success("🎉 Po wygranej osiągniesz cel!")
                                            else:
                                                remaining = target_after_win - budget_after_win
                                                st.info(f"💰 Po wygranej zostanie do celu: {remaining:.2f} zł")
                                else:
                                    st.info("💡 Możesz wpisać własną stawkę w lewej kolumnie")
                        
                            submitted = st.form_submit_button("✅ Dodaj kupon", type="primary")
                            
                            if submitted:
                                if not validate_odds(odds):
                                    st.error("❌ Kurs musi być większy niż 1.0!")
                                elif not validate_stake(stake):
                                    st.error("❌ Stawka musi być większa niż 0!")
                                else:
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
                                    save_rows(rows)
                                    
                                    st.success(f"✅ Dodano kupon #{next_number} ze stawką {stake:.2f} zł")
                                    st.session_state.show_new_coupon = False
                                    st.rerun()
        
        # Wyświetl tabelę kuponów
        st.header("📋 Historia kuponów")
        display_coupons_table(rows)
        
        # Dodatkowe opcje w sidebar
        with st.sidebar:
            st.markdown("---")
            st.subheader("🎮 Styl gry")
            
            # Inicjalizuj styl gry
            if 'game_style' not in st.session_state:
                st.session_state.game_style = "Własna stawka"
            
            game_style = st.radio(
                "Wybierz styl gry:",
                ["Własna stawka", "Rekomendowana stawka"],
                key="game_style_radio"
            )
            
            st.session_state.game_style = game_style
            
            # Przycisk do dodawania nowego kuponu
            if st.button("🎲 Nowy Kupon", type="primary", use_container_width=True):
                st.session_state.show_new_coupon = True
                st.rerun()
            
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
                        save_rows(rows)
                        
                        st.success(f"✅ Wpłacono {deposit_amount:.2f} zł")
                        st.rerun()
            
            # Wypłata
            with st.expander("💸 Wypłata", expanded=False):
                with st.form("withdrawal_form"):
                    withdrawal_amount = st.number_input(
                        "Kwota wypłaty",
                        min_value=0.01,
                        step=0.01,
                        value=50.0,
                        format="%.2f"
                    )
                    
                    if st.form_submit_button("💸 Wypłać", type="secondary"):
                        validation = validate_withdrawal(status['budget'], withdrawal_amount)
                        
                        if validation['valid']:
                            next_number = get_next_coupon_number(rows)
                            withdrawal_coupon = create_withdrawal_coupon(withdrawal_amount, next_number)
                            
                            rows.append(withdrawal_coupon)
                            recompute_aggregates(rows)
                            save_rows(rows)
                            
                            st.success(f"✅ Wypłacono {withdrawal_amount:.2f} zł")
                            st.rerun()
                        else:
                            st.error(f"❌ {validation['error']}")
            
            # Zmiana celu
            with st.expander("🎯 Zmiana celu", expanded=False):
                with st.form("target_form"):
                    current_target = st.session_state.profit_target
                    new_target = st.number_input(
                        "Nowy docelowy zysk",
                        min_value=0.0,
                        step=1.0,
                        value=float(current_target),
                        format="%.0f"
                    )
                    
                    st.caption(f"Aktualny cel: {current_target} zł")
                    
                    if st.form_submit_button("🎯 Ustaw cel", type="secondary"):
                        # Aktualizuj PROFIT_TARGET w sesji
                        st.session_state.profit_target = new_target
                        st.success(f"✅ Nowy cel: {new_target:.0f} zł")
                        st.rerun()
            
            # Historia transakcji
            with st.expander("📋 Historia transakcji", expanded=False):
                transactions = get_transaction_history(rows)
                
                if transactions:
                    for transaction in transactions[-5:]:  # Pokaż ostatnie 5
                        if transaction['type'] == 'deposit':
                            st.success(f"💵 {transaction['description']} (Kupon #{transaction['coupon']})")
                        else:
                            st.warning(f"💸 {transaction['description']} (Kupon #{transaction['coupon']})")
                else:
                    st.info("Brak transakcji")
            
            st.markdown("---")
            st.subheader("🗑️ Zarządzanie kuponami")
            
            # Szybkie usuwanie ostatniego kuponu
            if rows:
                last_coupon = rows[-1]
                last_coupon_name = last_coupon.get('Nazwa', f"#{last_coupon['Kupon']}")
                if st.button(f"🗑️ Usuń ostatni kupon ({last_coupon_name})", type="secondary", use_container_width=True):
                    if delete_coupon(rows, last_coupon['Kupon']):
                        recompute_aggregates(rows)
                        save_rows(rows)
                        st.success(f"✅ Usunięto kupon #{last_coupon['Kupon']}")
                        st.rerun()
                    else:
                        st.error(f"❌ Nie udało się usunąć kuponu #{last_coupon['Kupon']}")
            
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
                        create_empty_csv()
                        st.success("✅ Baza danych wyczyszczona")
                        st.session_state.show_delete_confirm = False
                        st.rerun()
                
                with col2:
                    if st.button("❌ Anuluj", type="secondary"):
                        st.session_state.show_delete_confirm = False
                        st.rerun()


if __name__ == "__main__":
    main()
