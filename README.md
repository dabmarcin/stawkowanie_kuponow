# 🎰 Aplikacja do Stawkowania Kuponów

Aplikacja webowa do zarządzania stawkowaniem kuponów zakładów z automatycznym wyliczaniem rekomendowanych stawek według strategii Martingale.

## 🎯 Cel Aplikacji

Po każdej porażce aplikacja rekomenduje kolejną stawkę tak, aby po wygranej:
- Odzyskać wszystkie wcześniejsze straty
- Osiągnąć co najmniej +100 zł zysku netto

## 🚀 Uruchomienie

### 1. Zainstaluj zależności

```bash
pip install -r requirements.txt
```

### 2. Uruchom aplikację Streamlit

```bash
streamlit run streamlit_app.py
```

Aplikacja zostanie uruchomiona pod adresem: `http://localhost:8501`

## 📁 Struktura Projektu

```
├── streamlit_app.py      # Główna aplikacja Streamlit
├── business_logic.py     # Logika biznesowa (obliczenia stawek)
├── csv_handler.py        # Obsługa plików CSV
├── app.py               # Oryginalna wersja CLI
├── requirements.txt     # Zależności Python
├── baza_kuponow.csv    # Baza danych kuponów (tworzona automatycznie)
└── README.md           # Ta dokumentacja
```

## 🎮 Jak Używać

### Pierwsze uruchomienie
1. Uruchom aplikację: `streamlit run streamlit_app.py`
2. Otwórz przeglądarkę na `http://localhost:8501`
3. Podaj początkowy wkład (np. 1000 zł)
4. Wprowadź kurs i stawkę pierwszego kuponu
5. Kliknij "Utwórz pierwszy kupon"

### Codzienne użytkowanie
1. **Rozstrzygnij ostatni kupon** - wybierz WYGRANA/PRZEGRANA
2. **Dodaj kolejny kupon** - aplikacja automatycznie:
   - Sprawdzi czy osiągnąłeś cel (+100 zł)
   - Jeśli nie - zarekomenduje odpowiednią stawkę
   - Pokaże alert jeśli brakuje środków w budżecie
   - Pozwoli doładować konto jeśli potrzeba

### Zarządzanie środkami
1. **💵 Wpłata** - zwiększ budżet (sidebar)
2. **💸 Wypłata** - zmniejsz budżet (z walidacją dostępnych środków)
3. **🎯 Zmiana celu** - dostosuj docelowy zysk (np. 200 zł zamiast 100 zł)
4. **📋 Historia** - zobacz wszystkie wpłaty i wypłaty

## 📊 Funkcje Aplikacji

### ✅ Automatyczne obliczenia
- Rekomendacja stawki na podstawie kursu i celu
- Śledzenie wkładu, salda i budżetu
- Alerty przy braku środków

### ✅ Zarządzanie środkami
- 💵 **Wpłaty** - zwiększanie budżetu
- 💸 **Wypłaty** - zmniejszanie budżetu z walidacją
- 🎯 **Dynamiczny cel** - zmiana docelowego zysku
- 📋 **Historia transakcji** - śledzenie wpłat/wypłat

### ✅ Interfejs webowy
- Intuicyjny interfejs Streamlit
- Karty z metrykami
- Kolorowa tabela kuponów
- Responsywny design
- Sidebar z opcjami zarządzania

### ✅ Bezpieczeństwo danych
- Automatyczne tworzenie backupów
- Walidacja danych wejściowych
- Migracja starych formatów CSV

## 🧮 Logika Biznesowa

### Wzór na rekomendowaną stawkę:
```
S = (Cel - Budżet) / (Kurs - 1)

Gdzie:
- S = stawka
- Cel = Wkład + 100 zł
- Budżet = Wkład + Saldo (dostępne środki)
```

### Przykład:
- Wkład: 1000 zł
- Przegrana 100 zł → Budżet: 900 zł
- Cel: 1100 zł (1000 + 100)
- Kurs: 3.0
- Rekomendacja: (1100 - 900) / (3 - 1) = 100 zł

## 🔧 Konfiguracja

### Zmiana docelowego zysku
W pliku `business_logic.py`:
```python
PROFIT_TARGET = 100.0  # Zmień na żądaną wartość
```

### Zmiana pliku bazy danych
W pliku `csv_handler.py`:
```python
CSV_FILE = "baza_kuponow.csv"  # Zmień nazwę pliku
```

## 📋 Struktura CSV

Plik `baza_kuponow.csv` zawiera kolumny:
- **Kupon** - numer kuponu
- **Wynik** - WYGRANA/PRZEGRANA/OCZEKUJE
- **Stawka (S)** - postawiona kwota
- **Kurs** - kurs zakładu
- **Zasilenie** - kwota doładowania
- **Suma zasieleń** - całkowity wkład
- **Suma włożona do tej pory** - suma wszystkich stawek
- **Wygrana brutto** - kurs × stawka
- **Saldo** - suma wygranych - suma stawek
- **Zysk netto** - saldo (zysk ponad wkład)

## ⚠️ Ostrzeżenia

1. **Strategia Martingale** wymaga dużego kapitału przy serii przegranych
2. **Zawsze** sprawdzaj alerty o braku środków
3. **Regularnie** twórz backupy bazy danych
4. **Nie graj** więcej niż możesz stracić

## 🆘 Rozwiązywanie Problemów

### Aplikacja nie uruchamia się
```bash
pip install --upgrade streamlit
```

### Błąd importu modułów
Upewnij się, że wszystkie pliki są w tym samym katalogu.

### Problemy z CSV
Usuń plik `baza_kuponow.csv` - aplikacja utworzy nowy przy następnym uruchomieniu.

## 📞 Wsparcie

W przypadku problemów sprawdź:
1. Logi w konsoli Streamlit
2. Plik `baza_kuponow.csv` (format danych)
3. Zainstalowane zależności: `pip list`

---

**Uwaga:** Ta aplikacja służy wyłącznie do celów edukacyjnych. Gra hazardowa może być uzależniająca. Graj odpowiedzialnie! 🎯
