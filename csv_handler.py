#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Moduł obsługi plików CSV dla aplikacji stawkowania kuponów.

Zawiera funkcje do wczytywania, zapisywania i migracji danych CSV.
Obsługuje tryb sesji (dane w pamięci) oraz tryb plikowy.
"""

import csv
import os
import io
from typing import List, Dict, Optional


# ============================================================================
# KONFIGURACJA
# ============================================================================

CSV_FILE = "baza_kuponow.csv"
CSV_HEADERS = [
    "Kupon",
    "Nazwa",
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


# ============================================================================
# FUNKCJE OBSŁUGI CSV
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
                print(f"⚠️  Wykryto stary format CSV. Migruję do nowego formatu...")
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


def migrate_old_format(old_rows: List[Dict[str, str]], initial_deposit: float = None) -> List[Dict[str, str]]:
    """
    Migruje stary format CSV (bez kolumny "Zasilenie") do nowego formatu.
    
    Args:
        old_rows: Lista kuponów w starym formacie.
        initial_deposit: Początkowy wkład (jeśli None, będzie wymagane od użytkownika).
        
    Returns:
        Lista kuponów w nowym formacie.
    """
    if not old_rows:
        return []
    
    # Skonwertuj wiersze do nowego formatu
    new_rows = []
    for i, old_row in enumerate(old_rows):
        new_row = {
            "Kupon": old_row.get("Kupon", str(i+1)),
            "Nazwa": old_row.get("Nazwa", f"Kupon #{old_row.get('Kupon', str(i+1))}"),
            "Wynik": old_row.get("Wynik", "OCZEKUJE"),
            "Stawka (S)": old_row.get("Stawka (S)", "0.00"),
            "Kurs": old_row.get("Kurs", "1.00"),
            "Zasilenie": f"{initial_deposit:.2f}" if i == 0 and initial_deposit is not None else "0.00",
            "Suma zasieleń": "0.00",  # Zostanie przeliczone
            "Suma włożona do tej pory": "0.00",  # Zostanie przeliczone
            "Wygrana brutto": "0.00",  # Zostanie przeliczone
            "Saldo": "0.00",  # Zostanie przeliczone
            "Zysk netto": "0.00"  # Zostanie przeliczone
        }
        new_rows.append(new_row)
    
    # Zapisz zmigrowane dane
    save_rows(new_rows)
    
    return new_rows


def create_empty_csv() -> None:
    """
    Tworzy pusty plik CSV z nagłówkami.
    """
    save_rows([])


def backup_csv(backup_suffix: str = None) -> str:
    """
    Tworzy kopię zapasową pliku CSV.
    
    Args:
        backup_suffix: Opcjonalny sufiks dla nazwy backupu.
        
    Returns:
        Nazwa pliku backupu.
    """
    if not os.path.exists(CSV_FILE):
        return None
    
    import datetime
    
    if backup_suffix:
        backup_name = f"{CSV_FILE}.{backup_suffix}"
    else:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{CSV_FILE}.backup_{timestamp}"
    
    try:
        import shutil
        shutil.copy2(CSV_FILE, backup_name)
        print(f"✅ Utworzono backup: {backup_name}")
        return backup_name
    except Exception as e:
        print(f"❌ Błąd podczas tworzenia backupu: {e}")
        return None


def validate_csv_structure(rows: List[Dict[str, str]]) -> bool:
    """
    Waliduje strukturę danych CSV.
    
    Args:
        rows: Lista kuponów do walidacji.
        
    Returns:
        True jeśli struktura jest prawidłowa.
    """
    if not rows:
        return True
    
    # Sprawdź czy wszystkie wymagane kolumny są obecne
    first_row = rows[0]
    for header in CSV_HEADERS:
        if header not in first_row:
            print(f"❌ Brakuje kolumny: {header}")
            return False
    
    return True


def get_csv_info() -> Dict[str, any]:
    """
    Pobiera informacje o pliku CSV.
    
    Returns:
        Słownik z informacjami o pliku.
    """
    info = {
        "exists": os.path.exists(CSV_FILE),
        "size": 0,
        "rows_count": 0,
        "last_modified": None
    }
    
    if info["exists"]:
        try:
            info["size"] = os.path.getsize(CSV_FILE)
            
            # Policz wiersze
            with open(CSV_FILE, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                info["rows_count"] = sum(1 for row in reader) - 1  # -1 dla nagłówka
            
            # Data modyfikacji
            import datetime
            timestamp = os.path.getmtime(CSV_FILE)
            info["last_modified"] = datetime.datetime.fromtimestamp(timestamp)
            
        except Exception as e:
            print(f"❌ Błąd podczas pobierania informacji o pliku: {e}")
    
    return info


# ============================================================================
# FUNKCJE TRYBU SESJI (DANE W PAMIĘCI)
# ============================================================================

def create_empty_template_csv() -> str:
    """
    Tworzy pusty szablon CSV w pamięci i zwraca jako string.
    
    Returns:
        String zawierający pusty CSV z nagłówkami.
    """
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=CSV_HEADERS)
    writer.writeheader()
    return output.getvalue()


def load_csv_from_string(csv_content: str) -> List[Dict[str, str]]:
    """
    Wczytuje dane CSV z stringa.
    
    Args:
        csv_content: Zawartość pliku CSV jako string.
        
    Returns:
        Lista słowników reprezentujących kupony.
    """
    try:
        reader = csv.DictReader(io.StringIO(csv_content))
        rows = list(reader)
        
        # Sprawdź czy to stary format (bez kolumny "Zasilenie")
        if reader.fieldnames and "Zasilenie" not in reader.fieldnames:
            print(f"⚠️  Wykryto stary format CSV. Migruję do nowego formatu...")
            rows = migrate_old_format(rows)
            print(f"✅ Migracja zakończona!")
        # Walidacja nagłówków
        elif reader.fieldnames != CSV_HEADERS:
            print(f"⚠️  Uwaga: Nagłówki w pliku nie pasują do oczekiwanych.")
            print(f"   Oczekiwane: {CSV_HEADERS}")
            print(f"   Znalezione: {reader.fieldnames}")
            
        return rows
    except Exception as e:
        print(f"❌ Błąd podczas wczytywania CSV z stringa: {e}")
        return []


def save_csv_to_string(rows: List[Dict[str, str]]) -> str:
    """
    Zapisuje wiersze do stringa CSV.
    
    Args:
        rows: Lista słowników z danymi kuponów.
        
    Returns:
        String zawierający dane CSV.
    """
    try:
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=CSV_HEADERS)
        writer.writeheader()
        writer.writerows(rows)
        return output.getvalue()
    except Exception as e:
        print(f"❌ Błąd podczas zapisywania CSV do stringa: {e}")
        return ""


def validate_csv_content(csv_content: str) -> tuple[bool, str]:
    """
    Waliduje zawartość pliku CSV.
    
    Args:
        csv_content: Zawartość pliku CSV jako string.
        
    Returns:
        Tuple (is_valid, error_message).
    """
    try:
        reader = csv.DictReader(io.StringIO(csv_content))
        fieldnames = reader.fieldnames
        
        if not fieldnames:
            return False, "Plik CSV nie zawiera nagłówków"
        
        # Sprawdź czy wszystkie wymagane kolumny są obecne
        missing_headers = [header for header in CSV_HEADERS if header not in fieldnames]
        if missing_headers:
            return False, f"Brakujące nagłówki: {', '.join(missing_headers)}"
        
        # Sprawdź czy nie ma nieznanych nagłówków
        extra_headers = [header for header in fieldnames if header not in CSV_HEADERS]
        if extra_headers:
            return False, f"Nieznane nagłówki: {', '.join(extra_headers)}"
        
        return True, "Plik CSV jest prawidłowy"
        
    except Exception as e:
        return False, f"Błąd podczas walidacji CSV: {e}"
