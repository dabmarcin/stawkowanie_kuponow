#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Moduł logiki biznesowej dla aplikacji stawkowania kuponów.

Zawiera funkcje do obliczania stawek, statusu gry i rekomendacji.
"""

import math
from typing import List, Dict, Optional


# ============================================================================
# KONFIGURACJA
# ============================================================================

PROFIT_TARGET = 100.0  # Docelowy zysk netto (może być dynamicznie zmieniany)


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


def validate_odds(odds: float) -> bool:
    """
    Waliduje kurs.
    
    Args:
        odds: Kurs do walidacji.
        
    Returns:
        True jeśli kurs jest prawidłowy.
    """
    return odds > 1.0


def validate_stake(stake: float) -> bool:
    """
    Waliduje stawkę.
    
    Args:
        stake: Stawka do walidacji.
        
    Returns:
        True jeśli stawka jest prawidłowa.
    """
    return stake > 0.0


# ============================================================================
# FUNKCJE LOGIKI BIZNESOWEJ
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


def get_current_status(rows: List[Dict[str, str]], profit_target: float = None) -> Dict[str, float]:
    """
    Oblicza bieżący stan gry na podstawie rozstrzygniętych kuponów.
    
    Args:
        rows: Lista wszystkich kuponów.
        profit_target: Docelowy zysk (jeśli None, używa domyślnego).
        
    Returns:
        Słownik z kluczami: sum_deposits, sum_stakes, sum_wins, balance, budget, net_profit, target.
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
    
    # Użyj przekazanego profit_target lub domyślnego
    target_profit = profit_target if profit_target is not None else PROFIT_TARGET
    target = sum_deposits + target_profit  # Cel: wkład + docelowy zysk
    
    return {
        "sum_deposits": sum_deposits,
        "sum_stakes": sum_stakes,
        "sum_wins": sum_wins,
        "balance": balance,
        "budget": budget,
        "net_profit": net_profit,
        "target": target
    }


def recommend_stake(budget: float, target: float, odds: float, profit_target: float = None) -> float:
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


def calculate_potential_result(budget: float, stake: float, odds: float, 
                              win: bool) -> Dict[str, float]:
    """
    Oblicza potencjalny wynik kuponu.
    
    Args:
        budget: Aktualny budżet.
        stake: Stawka kuponu.
        odds: Kurs kuponu.
        win: Czy kupon wygra.
        
    Returns:
        Słownik z potencjalnymi wartościami po rozstrzygnięciu kuponu.
    """
    if win:
        gross_win = odds * stake
        new_balance = budget - stake + gross_win
    else:
        gross_win = 0.0
        new_balance = budget - stake
    
    return {
        "gross_win": gross_win,
        "new_budget": new_balance,
        "profit_loss": gross_win - stake
    }


def get_next_coupon_number(rows: List[Dict[str, str]]) -> int:
    """
    Pobiera numer następnego kuponu.
    
    Args:
        rows: Lista istniejących kuponów.
        
    Returns:
        Numer następnego kuponu.
    """
    if not rows:
        return 1
    
    max_number = max(int(row["Kupon"]) for row in rows)
    return max_number + 1


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


def get_game_status(balance: float, sum_deposits: float) -> str:
    """
    Określa status gry (czy grasz wkładem czy zyskiem).
    
    Args:
        balance: Aktualne saldo.
        sum_deposits: Suma zasieleń (wkład).
        
    Returns:
        Opis statusu gry.
    """
    if balance < 0:
        return f"Grasz WKŁADEM (strata {format_currency(balance)})"
    elif balance > 0:
        return f"Grasz ZYSKIEM (plus {format_currency(balance)})"
    else:
        return "Na zero"


def validate_withdrawal(budget: float, withdrawal_amount: float) -> Dict[str, any]:
    """
    Waliduje wypłatę.
    
    Args:
        budget: Aktualny budżet.
        withdrawal_amount: Kwota do wypłaty.
        
    Returns:
        Słownik z wynikiem walidacji.
    """
    if withdrawal_amount <= 0:
        return {
            "valid": False,
            "error": "Kwota wypłaty musi być większa niż 0"
        }
    
    if withdrawal_amount > budget:
        return {
            "valid": False,
            "error": f"Nie możesz wypłacić więcej niż masz w budżecie ({budget:.2f} zł)"
        }
    
    return {
        "valid": True,
        "error": None
    }


def create_deposit_coupon(amount: float, next_number: int) -> Dict[str, str]:
    """
    Tworzy kupon reprezentujący wpłatę.
    
    Args:
        amount: Kwota wpłaty.
        next_number: Numer kuponu.
        
    Returns:
        Słownik reprezentujący kupon wpłaty.
    """
    return {
        "Kupon": str(next_number),
        "Nazwa": f"Wpłata {amount:.2f} zł",
        "Wynik": "WYGRANA",  # Wpłata to "wygrana"
        "Stawka (S)": "0.00",
        "Kurs": "1.00",
        "Zasilenie": f"{amount:.2f}",
        "Suma zasieleń": "0.00",  # Zostanie przeliczone
        "Suma włożona do tej pory": "0.00",  # Zostanie przeliczone
        "Wygrana brutto": "0.00",  # Zostanie przeliczone
        "Saldo": "0.00",  # Zostanie przeliczone
        "Zysk netto": "0.00"  # Zostanie przeliczone
    }


def create_withdrawal_coupon(amount: float, next_number: int) -> Dict[str, str]:
    """
    Tworzy kupon reprezentujący wypłatę.
    
    Args:
        amount: Kwota wypłaty.
        next_number: Numer kuponu.
        
    Returns:
        Słownik reprezentujący kupon wypłaty.
    """
    return {
        "Kupon": str(next_number),
        "Nazwa": f"Wypłata {amount:.2f} zł",
        "Wynik": "PRZEGRANA",  # Wypłata to "przegrana" (zmniejsza budżet)
        "Stawka (S)": f"{amount:.2f}",
        "Kurs": "1.00",
        "Zasilenie": "0.00",
        "Suma zasieleń": "0.00",  # Zostanie przeliczone
        "Suma włożona do tej pory": "0.00",  # Zostanie przeliczone
        "Wygrana brutto": "0.00",  # Zostanie przeliczone
        "Saldo": "0.00",  # Zostanie przeliczone
        "Zysk netto": "0.00"  # Zostanie przeliczone
    }


def get_transaction_history(rows: List[Dict[str, str]]) -> List[Dict[str, any]]:
    """
    Pobiera historię transakcji (wpłaty i wypłaty).
    
    Args:
        rows: Lista wszystkich kuponów.
        
    Returns:
        Lista transakcji z informacjami o wpłatach/wypłatach.
    """
    transactions = []
    
    for row in rows:
        deposit = parse_float(row.get("Zasilenie", "0")) or 0.0
        stake = parse_float(row.get("Stawka (S)", "0")) or 0.0
        result = row["Wynik"].strip().upper()
        
        # Sprawdź czy to wpłata (zasilenie > 0)
        if deposit > 0:
            transactions.append({
                "type": "deposit",
                "amount": deposit,
                "coupon": row["Kupon"],
                "description": f"Wpłata {deposit:.2f} zł"
            })
        
        # Sprawdź czy to wypłata (stawka bez kursu/gry)
        if stake > 0 and result == "PRZEGRANA" and parse_float(row.get("Kurs", "0")) == 1.0:
            # To może być wypłata - sprawdź czy nie ma zasilenia
            if deposit == 0:
                transactions.append({
                    "type": "withdrawal",
                    "amount": stake,
                    "coupon": row["Kupon"],
                    "description": f"Wypłata {stake:.2f} zł"
                })
    
    return transactions


def delete_coupon(rows: list, coupon_number: str) -> bool:
    """
    Usuwa kupon o podanym numerze z listy.
    
    Args:
        rows: Lista kuponów
        coupon_number: Numer kuponu do usunięcia
    
    Returns:
        bool: True jeśli kupon został usunięty, False jeśli nie znaleziono
    """
    for i, row in enumerate(rows):
        if row.get("Kupon") == coupon_number:
            del rows[i]
            return True
    return False


def delete_coupons(rows: list, coupon_numbers: list) -> int:
    """
    Usuwa wiele kuponów z listy.
    
    Args:
        rows: Lista kuponów
        coupon_numbers: Lista numerów kuponów do usunięcia
    
    Returns:
        int: Liczba usuniętych kuponów
    """
    deleted_count = 0
    for coupon_number in coupon_numbers:
        if delete_coupon(rows, coupon_number):
            deleted_count += 1
    return deleted_count


def edit_coupon(rows: list, coupon_number: str, new_name: str, new_stake: float, new_odds: float) -> bool:
    """
    Edytuje kupon w liście.
    
    Args:
        rows: Lista kuponów
        coupon_number: Numer kuponu do edycji
        new_name: Nowa nazwa kuponu
        new_stake: Nowa stawka
        new_odds: Nowy kurs
    
    Returns:
        True jeśli kupon został znaleziony i edytowany, False w przeciwnym razie
    """
    for row in rows:
        if row['Kupon'] == coupon_number:
            # Edytuj tylko jeśli kupon oczekuje na rozliczenie
            if is_pending(row):
                row['Nazwa'] = new_name if new_name.strip() else f"Kupon #{coupon_number}"
                row['Stawka (S)'] = f"{new_stake:.2f}"
                row['Kurs'] = f"{new_odds:.2f}"
                return True
    return False


def is_pending(row) -> bool:
    """Sprawdza czy kupon oczekuje na rozliczenie"""
    val = str(row.get("Wynik", "")).strip().upper()
    return val in {"OCZEKUJE", ""}


def save_profit_target(target: float) -> bool:
    """
    Zapisuje docelowy zysk do pliku.
    
    Args:
        target: Docelowy zysk do zapisania
    
    Returns:
        True jeśli zapisano pomyślnie, False w przeciwnym razie
    """
    try:
        with open('profit_target.txt', 'w') as f:
            f.write(str(target))
        return True
    except Exception as e:
        print(f"Błąd podczas zapisywania celu: {e}")
        return False


def load_profit_target() -> float:
    """
    Wczytuje docelowy zysk z pliku.
    
    Returns:
        Docelowy zysk lub domyślną wartość 100.0 jeśli plik nie istnieje
    """
    try:
        if os.path.exists('profit_target.txt'):
            with open('profit_target.txt', 'r') as f:
                content = f.read().strip()
                return float(content)
        else:
            return PROFIT_TARGET
    except Exception as e:
        print(f"Błąd podczas wczytywania celu: {e}")
        return PROFIT_TARGET
