# 🔥 Symulator Równania Ciepła (Heat Equation Project)

Projekt zaliczeniowy z przedmiotu **Modelowanie Deterministyczne**.
Aplikacja symuluje rozchodzenie się ciepła w pomieszczeniach mieszkalnych przy użyciu numerycznego rozwiązania równania ciepła (metoda różnic skończonych).

## 📌 O projekcie

Celem projektu jest weryfikacja popularnych mitów dotyczących ogrzewania oraz analiza zjawisk termodynamicznych w budownictwie. Aplikacja pozwala na interaktywne badanie dwóch głównych problemów badawczych:

1. **Lokalizacja grzejnika (Problem 1):** Czy grzejnik musi znajdować się pod oknem? Analiza wpływu położenia źródła ciepła na rozkład temperatury i komfort cieplny ().
2. **Pasożytnictwo cieplne (Problem 2):** Symulacja układu trzech mieszkań w szeregu. Analiza kosztów i zysków energetycznych w sytuacji, gdy sąsiedzi ogrzewają (lub nie) swoje mieszkania.

## 📂 Struktura projektu

Drzewo plików w repozytorium:

```text
.
├── data/
│   └── data.json      # Baza danych ze stałymi fizycznymi i domyślną konfiguracją
│
├── app.py                     # Główny plik aplikacji webowej (Streamlit)
├── heatEquationSolver.py      # Silnik obliczeniowy (klasa solvera numerycznego)
├── requirements.txt           # Lista wymaganych bibliotek Python
└── README.md                  # Dokumentacja projektu (ten plik)

```

## 🚀 Instalacja i uruchomienie

Aby uruchomić projekt na własnym komputerze, wykonaj następujące kroki:

### 1. Klonowanie repozytorium

Pobierz pliki projektu na dysk:

```bash
git clone https://github.com/CrazyMocks/ProjektZPraktycznychZastosowanRownanCiepla.git
cd ProjektZPraktycznychZastosowanRownanCiepla
```

### 2. Instalacja zależności

Zalecane jest użycie wirtualnego środowiska (venv). Zainstaluj biblioteki z pliku `requirements.txt`:

```bash
pip install -r requirements.txt
```

### 3. Uruchomienie aplikacji

Uruchom interfejs webowy za pomocą Streamlit:

```bash
streamlit run app.py
```

Aplikacja powinna otworzyć się automatycznie w Twojej domyślnej przeglądarce pod adresem `http://localhost:8501`.

## ⚙️ Funkcjonalności

* **Interaktywna symulacja:** Możliwość zmiany położenia grzejników, mocy grzewczej, temperatury na zewnątrz oraz parametrów izolacji (ściany/okna) w czasie rzeczywistym.
* **Wizualizacja:** Generowanie map ciepła (heatmap) oraz wykresów analitycznych.
* **Analiza ekonomiczna:** Obliczanie zużycia energii [kWh] dla różnych scenariuszy (współpraca sąsiedzka vs izolacja).
* **Raport:** Automatycznie generowana zakładka z opisem matematycznym modelu i wnioskami.

## 🛠 Technologie

* **Python 3.x**
* **NumPy** - obliczenia macierzowe i numeryczne.
* **Matplotlib** - wizualizacja danych i wykresy.
* **Streamlit** - interfejs użytkownika (GUI).

---

*Projekt wykonany w ramach zajęć akademickich (2025/2026).*

## 🤖 Wykorzystanie AI

W projekcie wykorzystano asystenta AI (LLM) w celu:
* Generowania szkieletu klas Pythona i optymalizacji obliczeń numerycznych (NumPy).
* Debugowania błędów związanych z warunkami brzegowymi.
* Stworzenia treściwych docstringów i komentarzy do kodu.
* Napisania tego README.md