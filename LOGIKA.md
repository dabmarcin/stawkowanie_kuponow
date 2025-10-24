# 📘 Logika Aplikacji - Stawkowanie Kuponów

## 🎯 Główne Pojęcia

### **Wkład (Kapitał)**
- Suma wszystkich zasieleń konta
- To są Twoje pieniądze, które musisz odzyskać
- Przykład: wpłaciłeś 1000 zł → wkład = 1000 zł

### **Saldo**
- `Saldo = Suma wygranych - Suma stawek`
- Pokazuje wynik Twoich zakładów (bez wkładu)
- Przykład: 
  - Przegrałeś 100 zł → saldo = -100 zł
  - Wygrałeś 300 zł (kurs 3, stawka 100) → saldo = 300 - 100 = +200 zł

### **Budżet (Dostępne środki)**
- `Budżet = Wkład + Saldo`
- To ile pieniędzy masz TERAZ dostępnych
- Przykład:
  - Wkład 1000 zł, przegrałeś 100 zł → budżet = 1000 + (-100) = 900 zł
  - Wkład 1000 zł, wygrałeś +200 zł → budżet = 1000 + 200 = 1200 zł

### **Zysk netto**
- `Zysk netto = Saldo` (to samo, bo wkład jest osobno)
- Ile zarobiliśmy ponad wkład
- Cel: Zysk netto >= +100 zł

## 📐 Wzór na Rekomendowaną Stawkę

**Cel:** Po wygranej chcesz mieć `Budżet >= Wkład + 100 zł`

**Wzór:**
```
Po wygranej: Budżet - S + (Kurs × S) >= Cel
Budżet + (Kurs - 1) × S >= Cel
(Kurs - 1) × S >= Cel - Budżet
S >= (Cel - Budżet) / (Kurs - 1)

Gdzie:
- S = stawka
- Cel = Wkład + 100 zł
- Budżet = aktualne dostępne środki
```

## 🧮 Przykład Krok po Kroku

### Start
- **Wkład:** 1000 zł (zasilenie)
- **Saldo:** 0 zł
- **Budżet:** 1000 zł
- **Cel:** 1100 zł (1000 + 100)

### Kupon 1: Przegrana
- **Stawka:** 100 zł
- **Kurs:** 3.0
- **Wynik:** PRZEGRANA
- **Nowe saldo:** 0 - 100 = -100 zł
- **Nowy budżet:** 1000 + (-100) = 900 zł

### Kupon 2: Rekomendacja
- **Budżet:** 900 zł
- **Cel:** 1100 zł
- **Kurs:** 3.0
- **Rekomendacja:** (1100 - 900) / (3 - 1) = 200 / 2 = **100 zł** ✓

### Kupon 2: Wygrana
- **Stawka:** 100 zł
- **Kurs:** 3.0
- **Wynik:** WYGRANA
- **Wygrana brutto:** 3 × 100 = 300 zł
- **Nowe saldo:** -100 + (300 - 100) = +100 zł
- **Nowy budżet:** 1000 + 100 = 1100 zł ✓ **CEL OSIĄGNIĘTY!**

## ⚠️ Alerty i Zabezpieczenia

### 1. **Alert przy braku środków**
Jeśli `Rekomendacja > Budżet`:
- 🚨 ALERT! Brakuje środków
- Opcja 1: Doładuj konto (zwiększa wkład i cel)
- Opcja 2: Użyj mniejszej stawki (ryzyko nieosiągnięcia celu)

### 2. **Śledzenie statusu**
- **Grasz WKŁADEM** gdy `Saldo < 0` (straty)
- **Grasz ZYSKIEM** gdy `Saldo > 0` (zyski)

### 3. **Zasilenia konta**
- Każde zasilenie zwiększa wkład i cel
- Przykład: Doładowanie +500 zł → nowy cel = 1500 + 100 = 1600 zł

## 📊 Kolumny w CSV

| Kolumna | Opis |
|---------|------|
| Kupon | Numer kuponu |
| Wynik | WYGRANA / PRZEGRANA / OCZEKUJE |
| Stawka (S) | Postawiona kwota |
| Kurs | Kurs zakładu |
| Zasilenie | Ile wpłacono w tym kuponie (zwykle 0, poza pierwszym) |
| Suma zasieleń | Całkowity wkład do tej pory |
| Suma włożona do tej pory | Suma wszystkich stawek |
| Wygrana brutto | Kurs × Stawka |
| Saldo | Suma wygranych - Suma stawek |
| Zysk netto | To samo co saldo |

## 🎮 Jak Używać

1. **Pierwszy raz:** Podaj początkowy wkład i stawkę
2. **Każde uruchomienie:** Program rozstrzyga oczekujący kupon
3. **Jeśli `Zysk netto < 100 zł`:** Program rekomenduje kolejną stawkę
4. **Jeśli `Zysk netto >= 100 zł`:** Gratulacje! Program nie wymusza kolejnych kuponów

## 🔄 Strategia

To strategia Martingale zmodyfikowana:
- Po przegranej zwiększasz stawkę
- Po wygranej osiągasz cel (wkład + zysk)
- Budżet jest ściśle monitorowany
- Alerty przy braku środków

**UWAGA:** Ta strategia wymaga dużego kapitału przy serii przegranych!

