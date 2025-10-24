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
        st.metric(
            "🎯 Budżet",
            f"{format_currency(status['budget'])}",
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
        st.info(f"ℹ️ {game_status}")


# ============================================================================
# GŁÓWNA FUNKCJA
# ============================================================================

def main():
    """Główna funkcja aplikacji."""
    
    # Inicjalizuj profit_target w session_state
    if 'profit_target' not in st.session_state:
        st.session_state.profit_target = PROFIT_TARGET
    
    # Nagłówek aplikacji
    st.title("🎰 Aplikacja do Stawkowania Kuponów")
    st.caption(f"🎯 Docelowy zysk: {st.session_state.profit_target} zł")
    
    # Wczytaj dane
    rows = load_rows()
    
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
                    save_rows(rows)
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
        
        # Pokaż potencjalny wynik
        if custom_stake > 0 and odds > 1:
            potential_win = odds * custom_stake
            potential_profit = custom_stake * (odds - 1)
            new_budget = status['budget'] - custom_stake + potential_win
            
            st.metric(
                "💡 Potencjalny wynik",
                f"{potential_win:.2f} zł",
                delta=f"Zysk: {format_currency(potential_profit)}"
            )
            
            st.caption(f"Nowy budżet po wygranej: {new_budget:.2f} zł")
        
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
                    value=100.0,
                    format="%.2f"
                )
                
                if st.form_submit_button("💸 Wypłać", type="primary"):
                    if validate_withdrawal(rows, withdrawal_amount):
                        next_number = get_next_coupon_number(rows)
                        withdrawal_coupon = create_withdrawal_coupon(withdrawal_amount, next_number)
                        
                        rows.append(withdrawal_coupon)
                        recompute_aggregates(rows)
                        save_rows(rows)
                        st.success(f"✅ Wypłacono {withdrawal_amount:.2f} zł")
                        st.rerun()
                    else:
                        st.error("❌ Nie masz wystarczających środków na wypłatę")
        
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
                    st.success(f"✅ Cel zmieniony na {new_target:.0f} zł")
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