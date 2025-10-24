#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Aplikacja CLI do zarządzania stawkowaniem kuponów zakładów.

Cel: Po każdej porażce rekomenduje kolejną stawkę tak, aby po wygranej
odzyskać wszystkie straty i osiągnąć co najmniej +100 zł łącznego zysku.
"""

import csv
import math
import os
from typing import List, Dict, Optional


# ============================================================================
# KONFIGURACJA
# ============================================================================

CSV_FILE = "baza_kuponow.csv"
CSV_HEADERS = [
    "Kupon",
    "Wynik",
    "Stawka (S)",
    "Kurs",
    "Zasilenie",
    "Suma zasieleń",
    "Suma włożona do tej pory",
    "Wygrana brutto",
    "Saldo",
    "Zysk netto"
]

# Domyślny docelowy zysk - można nadpisać przez zmienną środowiskową PROFIT_TARGET
PROFIT_TARGET = float(os.getenv("PROFIT_TARGET", "100"))


# ============================================================================
# FUNKCJE POMOCNICZE - OBSŁUGA CSV
# ============================================================================

def load_rows() -> List[Dict[str, str]]:
    """
    Wczytuje wiersze z pliku CSV.
    
    Returns:
        Lista słowników reprezentujących kupony.
        Jeśli plik nie istnieje, zwraca pustą listę.
    """
    if not os.path.exists(CSV_FILE):
        return []
    
    try:
        with open(CSV_FILE, 'r', encoding='utf-8', newline='') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            
            # Sprawdź czy to stary format (bez kolumny "Zasilenie")
            if reader.fieldnames and "Zasilenie" not in reader.fieldnames:
                print(f"\n⚠️  Wykryto stary format CSV. Migruję do nowego formatu...")
                rows = migrate_old_format(rows)
                print(f"✅ Migracja zakończona!")
            # Walidacja nagłówków
            elif reader.fieldnames != CSV_HEADERS:
                print(f"⚠️  Uwaga: Nagłówki w pliku nie pasują do oczekiwanych.")
                print(f"   Oczekiwane: {CSV_HEADERS}")
                print(f"   Znalezione: {reader.fieldnames}")
                
            return rows
    except Exception as e:
        print(f"❌ Błąd podczas wczytywania pliku CSV: {e}")
        return []


def migrate_old_format(old_rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """
    Migruje stary format CSV (bez kolumny "Zasilenie") do nowego formatu.
    Pyta użytkownika o początkowy wkład i dodaje go do pierwszego kuponu.
    
    Args:
        old_rows: Lista kuponów w starym formacie.
        
    Returns:
        Lista kuponów w nowym formacie.
    """
    if not old_rows:
        return []
    
    print("\n📋 Aby zmigrować dane, podaj początkowy wkład kapitału.")
    print("   (ile pieniędzy włożyłeś na start, przed pierwszym kuponem)")
    
    initial_deposit = ask_float("Początkowy wkład: ", min_value=0.0)
    
    # Skonwertuj wiersze do nowego formatu
    new_rows = []
    for i, old_row in enumerate(old_rows):
        new_row = {
            "Kupon": old_row.get("Kupon", str(i+1)),
            "Wynik": old_row.get("Wynik", "OCZEKUJE"),
            "Stawka (S)": old_row.get("Stawka (S)", "0.00"),
            "Kurs": old_row.get("Kurs", "1.00"),
            "Zasilenie": f"{initial_deposit:.2f}" if i == 0 else "0.00",
            "Suma zasieleń": "0.00",  # Zostanie przeliczone
            "Suma włożona do tej pory": "0.00",  # Zostanie przeliczone
            "Wygrana brutto": "0.00",  # Zostanie przeliczone
            "Saldo": "0.00",  # Zostanie przeliczone
            "Zysk netto": "0.00"  # Zostanie przeliczone
        }
        new_rows.append(new_row)
    
    # Przelicz agregaty
    recompute_aggregates(new_rows)
    
    # Zapisz zmigrowane dane
    save_rows(new_rows)
    
    return new_rows


def save_rows(rows: List[Dict[str, str]]) -> None:
    """
    Zapisuje wiersze do pliku CSV.
    
    Args:
        rows: Lista słowników z danymi kuponów.
    """
    try:
        with open(CSV_FILE, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
            writer.writeheader()
            writer.writerows(rows)
        print(f"✅ Dane zapisane do {CSV_FILE}")
    except Exception as e:
        print(f"❌ Błąd podczas zapisywania pliku CSV: {e}")
        print(f"   Upewnij się, że masz uprawnienia do zapisu w tym katalogu.")


# ============================================================================
# FUNKCJE POMOCNICZE - PARSOWANIE I WALIDACJA
# ============================================================================

def parse_float(s: str) -> Optional[float]:
    """
    Parsuje string do float, obsługując polski separator (przecinek).
    
    Args:
        s: String do sparsowania.
        
    Returns:
        Wartość float lub None jeśli parsowanie się nie powiodło.
    """
    try:
        # Zamień przecinek na kropkę
        normalized = s.strip().replace(',', '.')
        return float(normalized)
    except (ValueError, AttributeError):
        return None


def ask_float(prompt: str, min_value: Optional[float] = None, 
              max_value: Optional[float] = None) -> float:
    """
    Pyta użytkownika o liczbę zmiennoprzecinkową z walidacją.
    
    Args:
        prompt: Tekst zapytania.
        min_value: Minimalna akceptowalna wartość (opcjonalnie).
        max_value: Maksymalna akceptowalna wartość (opcjonalnie).
        
    Returns:
        Poprawnie sparsowana wartość float.
    """
    while True:
        user_input = input(prompt).strip()
        value = parse_float(user_input)
        
        if value is None:
            print("❌ Nieprawidłowa wartość. Podaj liczbę (użyj kropki lub przecinka).")
            continue
            
        if min_value is not None and value <= min_value:
            print(f"❌ Wartość musi być większa niż {min_value}.")
            continue
            
        if max_value is not None and value > max_value:
            print(f"❌ Wartość musi być mniejsza lub równa {max_value}.")
            continue
            
        return value


def ask_yes_no(prompt: str) -> bool:
    """
    Pyta użytkownika o decyzję tak/nie.
    
    Args:
        prompt: Tekst zapytania.
        
    Returns:
        True dla 't'/tak, False dla 'n'/nie.
    """
    while True:
        answer = input(prompt).strip().lower()
        if answer in ['t', 'tak', 'y', 'yes']:
            return True
        elif answer in ['n', 'nie', 'no']:
            return False
        else:
            print("❌ Nieprawidłowa odpowiedź. Wpisz 't' (tak) lub 'n' (nie).")


# ============================================================================
# FUNKCJE POMOCNICZE - LOGIKA BIZNESOWA
# ============================================================================

def recompute_aggregates(rows: List[Dict[str, str]]) -> None:
    """
    Przelicza i aktualizuje agregaty dla wszystkich kuponów:
    - Suma zasieleń (całkowity wkład kapitału)
    - Suma włożona do tej pory (suma stawek)
    - Wygrana brutto
    - Saldo (suma wygranych - suma stawek)
    - Zysk netto (saldo - suma zasieleń)
    
    Kupony z statusem OCZEKUJE nie wpływają na łączne wygrane przy liczeniu salda,
    ale ich wygrana brutto jest wyliczana (jako potencjalna).
    
    Args:
        rows: Lista kuponów do przeliczenia (modyfikowana in-place).
    """
    sum_deposits = 0.0      # Suma zasieleń (kapitał)
    sum_stakes = 0.0        # Suma wszystkich stawek (włącznie z oczekującymi)
    sum_wins_settled = 0.0  # Suma wygranych tylko z rozstrzygniętych kuponów
    
    for row in rows:
        stake = parse_float(row["Stawka (S)"]) or 0.0
        odds = parse_float(row["Kurs"]) or 0.0
        result = row["Wynik"].strip().upper()
        
        # Zasilenie dla tego kuponu (może być 0.00 jeśli nie było zasilenia)
        deposit = parse_float(row.get("Zasilenie", "0")) or 0.0
        sum_deposits += deposit
        row["Zasilenie"] = f"{deposit:.2f}"
        row["Suma zasieleń"] = f"{sum_deposits:.2f}"
        
        # Aktualizuj sumę włożoną (stawek)
        sum_stakes += stake
        row["Suma włożona do tej pory"] = f"{sum_stakes:.2f}"
        
        # Wylicz wygraną brutto
        gross_win = odds * stake
        row["Wygrana brutto"] = f"{gross_win:.2f}"
        
        # Jeśli kupon rozstrzygnięty, uwzględnij w sumie wygranych
        if result == "WYGRANA":
            sum_wins_settled += gross_win
        elif result == "PRZEGRANA":
            pass  # Wygrana = 0, już uwzględnione
        # OCZEKUJE - nie dodawaj do sum_wins_settled
        
        # Wylicz saldo (suma wygranych - suma stawek)
        # Dla kuponu OCZEKUJE pokazujemy potencjalne saldo
        if result == "OCZEKUJE":
            potential_balance = sum_wins_settled + gross_win - sum_stakes
            row["Saldo"] = f"{potential_balance:.2f}"
            # Zysk netto = saldo (bo wkład jest oddzielnie śledzony w zasileniach)
            row["Zysk netto"] = f"{potential_balance:.2f}"
        else:
            # Rzeczywiste saldo po rozstrzygnięciu
            actual_balance = sum_wins_settled - sum_stakes
            row["Saldo"] = f"{actual_balance:.2f}"
            # Zysk netto = saldo (bo wkład jest oddzielnie śledzony w zasileniach)
            row["Zysk netto"] = f"{actual_balance:.2f}"


def get_current_status(rows: List[Dict[str, str]]) -> Dict[str, float]:
    """
    Oblicza bieżący stan gry na podstawie rozstrzygniętych kuponów.
    
    Args:
        rows: Lista wszystkich kuponów.
        
    Returns:
        Słownik z kluczami: sum_deposits, sum_stakes, sum_wins, balance, net_profit, target.
    """
    sum_deposits = 0.0  # Suma zasieleń (całkowity wkład)
    sum_stakes = 0.0    # Suma stawek
    sum_wins = 0.0      # Suma wygranych
    
    for row in rows:
        result = row["Wynik"].strip().upper()
        
        # Suma zasieleń zawsze (niezależnie od statusu)
        deposit = parse_float(row.get("Zasilenie", "0")) or 0.0
        sum_deposits += deposit
        
        # Uwzględnij tylko rozstrzygnięte kupony dla stawek i wygranych
        if result in ["WYGRANA", "PRZEGRANA"]:
            stake = parse_float(row["Stawka (S)"]) or 0.0
            sum_stakes += stake
            
            if result == "WYGRANA":
                odds = parse_float(row["Kurs"]) or 0.0
                sum_wins += odds * stake
    
    balance = sum_wins - sum_stakes  # Saldo (suma wygranych - suma stawek)
    budget = sum_deposits + balance  # Budżet (dostępne środki = wkład + saldo)
    net_profit = balance  # Zysk netto = saldo (bo wkład jest osobno)
    target = sum_deposits + PROFIT_TARGET  # Cel: wkład + 100 zł
    
    return {
        "sum_deposits": sum_deposits,
        "sum_stakes": sum_stakes,
        "sum_wins": sum_wins,
        "balance": balance,
        "budget": budget,
        "net_profit": net_profit,
        "target": target
    }


def recommend_stake(budget: float, target: float, odds: float) -> float:
    """
    Wylicza rekomendowaną stawkę dla danego kursu, aby po wygranej
    osiągnąć docelowy budżet (wkład + zysk docelowy).
    
    Wzór: 
    Po wygranej: budżet - S + (odds * S) >= target
    Czyli: budżet + (odds - 1) * S >= target
    Więc: S >= (target - budżet) / (odds - 1)
    
    Args:
        budget: Aktualny budżet (dostępne środki = suma zasieleń + saldo).
        target: Docelowy budżet (suma zasieleń + PROFIT_TARGET).
        odds: Kurs planowanego kuponu.
        
    Returns:
        Rekomendowana stawka zaokrąglona w górę do 0.01.
        
    Raises:
        ValueError: Jeśli kurs <= 1.0 lub budżet >= target.
    """
    if odds <= 1.0:
        raise ValueError("Kurs musi być większy niż 1.0")
    
    if budget >= target:
        raise ValueError("Budżet już osiągnął cel - nie potrzebujesz kolejnej stawki")
    
    needed = target - budget
    required_stake = needed / (odds - 1)
    
    # Zaokrąglij w górę do 2 miejsc po przecinku
    recommended = math.ceil(required_stake * 100) / 100
    
    return recommended


def print_summary(rows: List[Dict[str, str]]) -> None:
    """
    Wyświetla czytelne podsumowanie wszystkich kuponów.
    
    Args:
        rows: Lista kuponów do wyświetlenia.
    """
    if not rows:
        print("\n📋 Baza kuponów jest pusta.")
        return
    
    print("\n" + "="*80)
    print("📋 PODSUMOWANIE KUPONÓW")
    print("="*80)
    
    for row in rows:
        kupon_nr = row["Kupon"]
        wynik = row["Wynik"]
        stawka = row["Stawka (S)"]
        kurs = row["Kurs"]
        zasilenie = row.get("Zasilenie", "0.00")
        suma_zasielen = row.get("Suma zasieleń", "0.00")
        suma_wlozona = row["Suma włożona do tej pory"]
        wygrana = row["Wygrana brutto"]
        saldo = row.get("Saldo", row.get("Zysk/Strata po kuponie", "0.00"))
        zysk_netto = row.get("Zysk netto", "0.00")
        
        # Ikonka statusu
        if wynik == "WYGRANA":
            status_icon = "✅"
        elif wynik == "PRZEGRANA":
            status_icon = "❌"
        else:
            status_icon = "⏳"
        
        print(f"\n{status_icon} Kupon #{kupon_nr} - {wynik}")
        
        # Pokaż zasilenie jeśli było
        deposit_val = parse_float(zasilenie) or 0.0
        if deposit_val > 0:
            print(f"   💵 Zasilenie: +{zasilenie} zł  →  Suma wkładu: {suma_zasielen} zł")
        
        print(f"   Kurs: {kurs}  |  Stawka: {stawka} zł")
        print(f"   Suma stawek: {suma_wlozona} zł  |  Wygrana brutto: {wygrana} zł")
        
        saldo_val = parse_float(saldo) or 0.0
        zysk_val = parse_float(zysk_netto) or 0.0
        
        if wynik == "OCZEKUJE":
            print(f"   Potencjalne saldo: {saldo} zł  |  Potencjalny zysk netto: {format_currency(zysk_val)}")
        else:
            print(f"   Saldo: {saldo} zł  |  Zysk netto: {format_currency(zysk_val)}")
    
    print("="*80 + "\n")


def format_currency(amount: float) -> str:
    """
    Formatuje kwotę jako walutę z prefiksem +/- dla dodatnich/ujemnych wartości.
    
    Args:
        amount: Kwota do sformatowania.
        
    Returns:
        Sformatowany string, np. "+123.45 zł" lub "-67.89 zł".
    """
    if amount >= 0:
        return f"+{amount:.2f} zł"
    else:
        return f"{amount:.2f} zł"


# ============================================================================
# FUNKCJE GŁÓWNEJ LOGIKI APLIKACJI
# ============================================================================

def create_first_coupon() -> List[Dict[str, str]]:
    """
    Obsługuje tworzenie pierwszego kuponu w pustej bazie.
    
    Returns:
        Lista z jednym kuponem o statusie OCZEKUJE.
    """
    print("\n" + "="*80)
    print("🎯 TWORZENIE PIERWSZEGO KUPONU")
    print("="*80)
    
    print("\n💰 Najpierw ustal swój początkowy kapitał (wkład).")
    deposit = ask_float("Ile pieniędzy wpłacasz na start (zasilenie)? ", min_value=0.0)
    
    print(f"\n✅ Zasilenie: {deposit:.2f} zł")
    print(f"🎯 Cel: odzyskać wkład + {PROFIT_TARGET:.2f} zł zysku = {deposit + PROFIT_TARGET:.2f} zł")
    
    odds = ask_float("\nPodaj kurs pierwszego kuponu (np. 2.5): ", min_value=1.0)
    stake = ask_float("Podaj stawkę (np. 10): ", min_value=0.0)
    
    # Utwórz pierwszy kupon
    coupon = {
        "Kupon": "1",
        "Wynik": "OCZEKUJE",
        "Stawka (S)": f"{stake:.2f}",
        "Kurs": f"{odds:.2f}",
        "Zasilenie": f"{deposit:.2f}",
        "Suma zasieleń": "0.00",  # Zostanie przeliczone
        "Suma włożona do tej pory": "0.00",  # Zostanie przeliczone
        "Wygrana brutto": "0.00",  # Zostanie przeliczone
        "Saldo": "0.00",  # Zostanie przeliczone
        "Zysk netto": "0.00"  # Zostanie przeliczone
    }
    
    rows = [coupon]
    recompute_aggregates(rows)
    save_rows(rows)
    print_summary(rows)
    
    print(f"\n✨ Utworzono pierwszy kupon. Uruchom program ponownie, aby rozstrzygnąć wynik.")
    
    return rows


def settle_pending_coupon(rows: List[Dict[str, str]], last_idx: int) -> None:
    """
    Rozstrzyga kupon o statusie OCZEKUJE.
    
    Args:
        rows: Lista wszystkich kuponów.
        last_idx: Indeks ostatniego kuponu (który jest OCZEKUJE).
    """
    last_coupon = rows[last_idx]
    
    print("\n" + "="*80)
    print(f"⏳ Kupon #{last_coupon['Kupon']} oczekuje na rozstrzygnięcie")
    print("="*80)
    print(f"   Kurs: {last_coupon['Kurs']}")
    print(f"   Stawka: {last_coupon['Stawka (S)']} zł")
    print(f"   Potencjalna wygrana: {last_coupon['Wygrana brutto']} zł")
    
    while True:
        result = input("\nJaki jest wynik tego kuponu? (W - wygrana / P - przegrana): ").strip().upper()
        
        if result in ['W', 'WYGRANA']:
            last_coupon["Wynik"] = "WYGRANA"
            break
        elif result in ['P', 'PRZEGRANA']:
            last_coupon["Wynik"] = "PRZEGRANA"
            last_coupon["Wygrana brutto"] = "0.00"  # Przegrana = 0 wygranej
            break
        else:
            print("❌ Nieprawidłowa odpowiedź. Wpisz 'W' (wygrana) lub 'P' (przegrana).")
    
    # Przelicz agregaty po rozstrzygnięciu
    recompute_aggregates(rows)
    save_rows(rows)
    
    print(f"\n✅ Kupon #{last_coupon['Kupon']} rozstrzygnięty jako {last_coupon['Wynik']}.")


def add_new_coupon_with_recommendation(rows: List[Dict[str, str]], 
                                       status: Dict[str, float]) -> None:
    """
    Dodaje nowy kupon z rekomendacją stawki (gdy net_profit < PROFIT_TARGET).
    
    Args:
        rows: Lista wszystkich kuponów.
        status: Bieżący stan gry (sum_deposits, balance, budget, net_profit, target, itp.).
    """
    print("\n" + "="*80)
    print("🎲 DODAWANIE NOWEGO KUPONU")
    print("="*80)
    
    balance = status["balance"]
    budget = status["budget"]
    net_profit = status["net_profit"]
    target = status["target"]
    sum_deposits = status["sum_deposits"]
    
    print(f"\n💵 Wkład (suma zasieleń): {sum_deposits:.2f} zł")
    print(f"💰 Saldo (wygrane - stawki): {format_currency(balance)}")
    print(f"💳 Budżet (dostępne środki): {budget:.2f} zł")
    print(f"📈 Zysk netto: {format_currency(net_profit)}")
    print(f"🎯 Cel: {target:.2f} zł (wkład + {PROFIT_TARGET:.2f} zł)")
    print(f"📊 Do celu brakuje: {format_currency(target - budget)}")
    
    # Sprawdź czy grasz wkładem czy zyskiem
    if balance < 0:
        print(f"\n⚠️  Grasz WKŁADEM (strata {format_currency(balance)})")
    elif balance > 0:
        print(f"\n✅ Grasz ZYSKIEM (plus {format_currency(balance)})")
    else:
        print(f"\n➖ Na zero")
    
    # Sprawdź czy trzeba doładować konto
    deposit = 0.0
    if budget <= 0:
        print(f"\n🚨 UWAGA: Budżet wyczerpany! Musisz doładować konto.")
        deposit = ask_float("Ile wpłacasz (zasilenie)? ", min_value=0.0)
        budget += deposit
        target += deposit
        sum_deposits += deposit
        print(f"\n✅ Zasilenie: +{deposit:.2f} zł")
        print(f"💳 Nowy budżet: {budget:.2f} zł")
        print(f"🎯 Nowy cel: {target:.2f} zł")
    
    # Zapytaj o kurs
    odds = ask_float("\nPodaj kurs kolejnego kuponu (np. 2.5): ", min_value=1.0)
    
    # Wylicz rekomendowaną stawkę
    try:
        recommended = recommend_stake(budget, target, odds)
        
        print(f"\n💡 Rekomendowana stawka: {recommended:.2f} zł")
        print(f"   (przy tym kursie i wygranej osiągniesz cel: {target:.2f} zł)")
        
        # ALERT: Sprawdź czy masz dość środków w budżecie!
        if recommended > budget:
            shortage = recommended - budget
            print(f"\n🚨 ALERT! Rekomendacja przekracza budżet!")
            print(f"   Rekomendacja: {recommended:.2f} zł")
            print(f"   Budżet: {budget:.2f} zł")
            print(f"   Brakuje: {shortage:.2f} zł")
            print(f"\n❓ Co chcesz zrobić?")
            print(f"   1. Doładować konto (zasilenie)")
            print(f"   2. Użyć mniejszej stawki (ryzyko: może nie osiągnąć celu)")
            
            choice = input("Wybierz (1/2): ").strip()
            
            if choice == "1":
                min_deposit = math.ceil(shortage * 100) / 100
                print(f"\n💡 Minimalne zasilenie: {min_deposit:.2f} zł")
                deposit = ask_float("Ile wpłacasz? ", min_value=min_deposit)
                budget += deposit
                target += deposit
                sum_deposits += deposit
                print(f"✅ Zasilenie: +{deposit:.2f} zł")
                print(f"💳 Nowy budżet: {budget:.2f} zł")
                
                # Przelicz rekomendację z nowym budżetem
                recommended = recommend_stake(budget, target, odds)
                print(f"💡 Nowa rekomendacja: {recommended:.2f} zł")
        
        use_recommended = ask_yes_no("\nUżyć rekomendowanej stawki? (t/n): ")
        
        if use_recommended:
            stake = recommended
        else:
            stake = ask_float("Podaj własną stawkę: ", min_value=0.0)
            
            # Ostrzeżenie jeśli przekracza budżet
            if stake > budget:
                print(f"⚠️  UWAGA: Stawka przekracza budżet ({budget:.2f} zł)!")
                confirm = ask_yes_no("Czy na pewno kontynuować? (t/n): ")
                if not confirm:
                    print("Anulowano dodawanie kuponu.")
                    return
            
    except ValueError as e:
        print(f"❌ Błąd: {e}")
        return
    
    # Utwórz nowy kupon
    next_number = max(int(row["Kupon"]) for row in rows) + 1
    
    new_coupon = {
        "Kupon": str(next_number),
        "Wynik": "OCZEKUJE",
        "Stawka (S)": f"{stake:.2f}",
        "Kurs": f"{odds:.2f}",
        "Zasilenie": f"{deposit:.2f}",
        "Suma zasieleń": "0.00",  # Zostanie przeliczone
        "Suma włożona do tej pory": "0.00",  # Zostanie przeliczone
        "Wygrana brutto": "0.00",  # Zostanie przeliczone
        "Saldo": "0.00",  # Zostanie przeliczone
        "Zysk netto": "0.00"  # Zostanie przeliczone
    }
    
    rows.append(new_coupon)
    recompute_aggregates(rows)
    save_rows(rows)
    
    print(f"\n✅ Dodano kupon #{next_number} ze stawką {stake:.2f} zł")
    
    # Pokaż nowy stan budżetu
    new_budget = budget - stake
    print(f"💳 Budżet po tej stawce: {new_budget:.2f} zł")
    
    print_summary([new_coupon])


def add_new_coupon_without_recommendation(rows: List[Dict[str, str]]) -> None:
    """
    Dodaje nowy kupon bez rekomendacji (gdy net_profit >= PROFIT_TARGET).
    Użytkownik sam decyduje o kursie i stawce.
    
    Args:
        rows: Lista wszystkich kuponów.
    """
    print("\n" + "="*80)
    print("🎲 DODAWANIE NOWEGO KUPONU (bez rekomendacji)")
    print("="*80)
    
    # Opcjonalne zasilenie
    deposit = 0.0
    add_deposit = ask_yes_no("\nCzy chcesz doładować konto (zasilenie)? (t/n): ")
    
    if add_deposit:
        deposit = ask_float("Ile wpłacasz (zasilenie)? ", min_value=0.0)
        print(f"✅ Zasilenie: +{deposit:.2f} zł")
    
    odds = ask_float("\nPodaj kurs kuponu: ", min_value=1.0)
    stake = ask_float("Podaj stawkę: ", min_value=0.0)
    
    # Utwórz nowy kupon
    next_number = max(int(row["Kupon"]) for row in rows) + 1
    
    new_coupon = {
        "Kupon": str(next_number),
        "Wynik": "OCZEKUJE",
        "Stawka (S)": f"{stake:.2f}",
        "Kurs": f"{odds:.2f}",
        "Zasilenie": f"{deposit:.2f}",
        "Suma zasieleń": "0.00",  # Zostanie przeliczone
        "Suma włożona do tej pory": "0.00",  # Zostanie przeliczone
        "Wygrana brutto": "0.00",  # Zostanie przeliczone
        "Saldo": "0.00",  # Zostanie przeliczone
        "Zysk netto": "0.00"  # Zostanie przeliczone
    }
    
    rows.append(new_coupon)
    recompute_aggregates(rows)
    save_rows(rows)
    
    print(f"\n✅ Dodano kupon #{next_number}")
    print_summary([new_coupon])


# ============================================================================
# FUNKCJA GŁÓWNA
# ============================================================================

def main():
    """
    Główna funkcja aplikacji - orkiestruje cały przepływ.
    """
    print("\n" + "="*80)
    print("🎰 APLIKACJA DO STAWKOWANIA KUPONÓW")
    print("="*80)
    print(f"📁 Plik danych: {CSV_FILE}")
    print(f"🎯 Docelowy zysk: {format_currency(PROFIT_TARGET)}")
    print("="*80)
    
    # Wczytaj bazę
    rows = load_rows()
    
    # Jeśli baza pusta, utwórz pierwszy kupon
    if not rows:
        print("\n📋 Baza kuponów jest pusta.")
        create_first_coupon()
        return
    
    # Przelicz agregaty (na wypadek ręcznej edycji pliku)
    recompute_aggregates(rows)
    
    # Wyświetl podsumowanie
    print_summary(rows)
    
    # Sprawdź ostatni kupon
    last_coupon = rows[-1]
    last_idx = len(rows) - 1
    
    # Jeśli ostatni kupon oczekuje, rozstrzygnij go
    if last_coupon["Wynik"].strip().upper() == "OCZEKUJE":
        settle_pending_coupon(rows, last_idx)
        print_summary(rows)
    
    # Oblicz bieżący stan gry (tylko rozstrzygnięte kupony)
    status = get_current_status(rows)
    balance = status["balance"]
    budget = status["budget"]
    net_profit = status["net_profit"]
    target = status["target"]
    sum_deposits = status["sum_deposits"]
    
    print("\n" + "="*80)
    print("📊 BIEŻĄCY STAN")
    print("="*80)
    print(f"💵 Wkład (suma zasieleń): {sum_deposits:.2f} zł")
    print(f"💸 Suma stawek: {status['sum_stakes']:.2f} zł")
    print(f"💰 Suma wygranych: {status['sum_wins']:.2f} zł")
    print(f"📊 Saldo (wygrane - stawki): {format_currency(balance)}")
    print(f"💳 Budżet (dostępne środki): {budget:.2f} zł")
    print(f"📈 Zysk netto: {format_currency(net_profit)}")
    print(f"🎯 Cel: {target:.2f} zł (wkład + {PROFIT_TARGET:.2f} zł)")
    
    # Status: grasz wkładem czy zyskiem?
    if balance < 0:
        print(f"📍 Status: Grasz WKŁADEM (strata {format_currency(balance)})")
    elif balance > 0:
        print(f"📍 Status: Grasz ZYSKIEM (plus {format_currency(balance)})")
    else:
        print(f"📍 Status: Na zero")
    
    print("="*80)
    
    # Sprawdź, czy osiągnięto cel
    if net_profit >= PROFIT_TARGET:
        print(f"\n🎉 GRATULACJE! Osiągnąłeś cel!")
        print(f"   Zysk netto: {format_currency(net_profit)}")
        print(f"   (odzyskałeś cały wkład + {PROFIT_TARGET:.2f} zł zysku)")
        print(f"   Nie proponuję kolejnej stawki.")
        
        add_another = ask_yes_no("\n❓ Chcesz dodać kolejny kupon? (t/n): ")
        
        if add_another:
            add_new_coupon_without_recommendation(rows)
        else:
            print("\n👋 Dziękuję za skorzystanie z aplikacji!")
    else:
        # net_profit < PROFIT_TARGET, dodaj kupon z rekomendacją
        add_new_coupon_with_recommendation(rows, status)


# ============================================================================
# PUNKT WEJŚCIA
# ============================================================================

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Program przerwany przez użytkownika.")
    except Exception as e:
        print(f"\n❌ Wystąpił nieoczekiwany błąd: {e}")
        import traceback
        traceback.print_exc()

