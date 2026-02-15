"""Aplikacja Streamlit do symulacji równania ciepła w kontekście ogrzewania mieszkań.

Aplikacja demonstruje praktyczne zastosowania numerycznego rozwiązania równania ciepła:
1. Problem 1: Optymalna lokalizacja grzejnika względem okna
2. Problem 2: Analiza pasożytnictwa cieplnego w budynkach wielomieszkaniowych
3. Raport: Podsumowanie teoretyczne i wnioski z eksperymentów

Aplikacja wykorzystuje metodę różnic skończonych (FTCS) z warunkami brzegowymi Robina.
"""

import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
import time
import matplotlib.ticker as ticker

from heatEquationSolver import HeatEquationSolver
from utils import load_project_data


# ============================================================================
# SEKCJA 1: Ładowanie danych konfiguracyjnych z pliku JSON
# ============================================================================

# Wczytanie parametrów projektu z pliku data/data.json
project_data = load_project_data()

# Jeśli nie udało się załadować danych, zatrzymaj aplikację
if project_data is None:
    st.stop()

# Wyodrębnienie sekcji konfiguracyjnych
grid_cfg = project_data["grid"]  # Parametry siatki (Lx, Ly, dx, dt)
phys_cfg = project_data["physics_constants"]  # Stałe fizyczne (alpha, ciśnienie, R, cp)
defaults = project_data["defaults"]  # Wartości domyślne dla UI
mat_cfg = project_data["materials"]  # Przewodności cieplne materiałów

# ============================================================================
# SEKCJA 2: Przygotowanie bazowej konfiguracji solwera
# ============================================================================

# Słownik z parametrami dla HeatEquationSolver
# Temperatury są konwertowane z °C na Kelwiny (dodanie 273.15)
base_config = {
    # Parametry geometryczne siatki
    "Lx": grid_cfg["Lx"],  # Długość domeny w kierunku x [m]
    "Ly": grid_cfg["Ly"],  # Długość domeny w kierunku y [m]
    "dx": grid_cfg["dx"],  # Krok przestrzenny [m]
    "dt": grid_cfg["dt"],  # Krok czasowy [s]
    # Parametry fizyczne
    "alpha": phys_cfg["alpha"],  # Współczynnik dyfuzji cieplnej [m²/s]
    "pressure": phys_cfg["pressure"],  # Ciśnienie powietrza [Pa]
    "r_gas": phys_cfg["r_gas"],  # Stała gazowa [J/(kg·K)]
    "c_specific": phys_cfg["c_specific"],  # Ciepło właściwe [J/(kg·K)]
    # Przewodności cieplne materiałów
    "lambda_air": mat_cfg["lambda_air"],  # Przewodność powietrza [W/(m·K)]
    "lambda_wall": mat_cfg["lambda_wall"],  # Przewodność ściany [W/(m·K)]
    "lambda_window": mat_cfg["lambda_window"],  # Przewodność okna [W/(m·K)]
    # Temperatury (konwersja °C -> K)
    "u_outdoor": defaults["temp_outdoor_C"] + 273.15,  # Temperatura zewnętrzna [K]
    "u_start": defaults["temp_start_C"] + 273.15,  # Temperatura początkowa [K]
    "thermostat_temp": defaults["temp_thermostat_C"] + 273.15,  # Temperatura zadana [K]
    # Moc grzejnika
    "power": defaults["radiator_power_W"],  # Moc grzejnika [W]
}


# ============================================================================
# SEKCJA 3: Konfiguracja interfejsu Streamlit
# ============================================================================

# Ustawienie konfiguracji strony (szeroki layout dla lepszej wizualizacji)
st.set_page_config(page_title="Symulator Ogrzewania", layout="wide")
st.title("Praktyczne zastosowania równania ciepła")

# Nagłówek panelu bocznego z parametrami globalnymi
st.sidebar.header("Parametry globalne")

# ----------------------------------------------------------------------------
# Główne parametry symulacji (sidebar)
# ----------------------------------------------------------------------------

# Temperatura zewnętrzna (zakres: -30°C do 15°C)
temp_out_c = st.sidebar.slider(
    "Temperatura na zewnątrz [°C]", -30, 15, value=defaults["temp_outdoor_C"]
)

# Temperatura zadana termostatu (zakres: 15°C do 30°C)
temp_target_c = st.sidebar.slider(
    "Termostat [°C]", 15, 30, value=defaults["temp_thermostat_C"]
)

# Czas trwania symulacji w godzinach (zakres: 1h do 24h)
simulation_hours = st.sidebar.slider(
    "Czas symulacji [h]", 1, 24, value=defaults["simulation_hours"]
)

# Moc grzejnika w watach
power_w = st.sidebar.number_input(
    "Moc grzejnika [W]", value=defaults["radiator_power_W"], step=100.0
)

# ----------------------------------------------------------------------------
# Zaawansowane parametry budynku (rozwijalna sekcja)
# ----------------------------------------------------------------------------

with st.sidebar.expander("🛠️ Parametry budynku i startowe"):
    st.write("Dostosuj fizykę budynku:")

    # Temperatura początkowa w pomieszczeniu
    temp_start_c = st.slider(
        "Temp. początkowa w środku [°C]",
        0,
        25,
        value=defaults["temp_start_C"],
        help="Od jakiej temperatury startujemy?",
    )

    # Przewodność cieplna ściany (niższa = lepsza izolacja)
    lambda_wall_input = st.number_input(
        "Przewodność ściany [W/(m·K)]",
        min_value=0.1,
        max_value=2.5,
        step=0.1,
        format="%.2f",
        value=mat_cfg["lambda_wall"],
        help="0.1 (styropian) - 0.8 (cegła) - 1.7 (beton)",
    )

    # Przewodność cieplna okna (wyższa = większe straty ciepła)
    lambda_window_input = st.number_input(
        "Przewodność okna [W/(m·K)]",
        min_value=0.5,
        max_value=6.0,
        step=0.1,
        format="%.2f",
        value=mat_cfg["lambda_window"],
        help="1.0 (nowe) - 2.0 (standard) - 5.0 (stare)",
    )

# ============================================================================
# SEKCJA 4: Aktualizacja konfiguracji na podstawie parametrów z UI
# ============================================================================

# Kopiowanie bazowej konfiguracji
config = base_config.copy()

# Nadpisanie wartości z UI (konwersja temperatur °C -> K)
config["u_outdoor"] = temp_out_c + 273.15
config["thermostat_temp"] = temp_target_c + 273.15
config["power"] = power_w
config["u_start"] = temp_start_c + 273.15
config["lambda_wall"] = lambda_wall_input
config["lambda_window"] = lambda_window_input

# Obliczenie liczby kroków czasowych: (godziny * 3600 s/h) / dt
steps = int((simulation_hours * 3600) / config["dt"])

# ============================================================================
# SEKCJA 5: Definicja zakładek (tabs) aplikacji
# ============================================================================

tab1, tab2, tab3 = st.tabs(
    [
        "Problem 1: Czy grzejnik musi być pod oknem?",
        "Problem 2: Pasożytnictwo cieplne",
        "Raport i Wnioski",
    ]
)

# ============================================================================
# TAB 1: Problem 1 - Optymalna lokalizacja grzejnika
# ============================================================================

with tab1:
    st.header("1. Czy grzejnik musi być pod oknem?")
    st.write(
        "Symulacja pojedynczego pokoju (4x4m). Okno znajduje się na lewej ścianie."
    )

    # Podział na dwie kolumny: kontrolki (1/3) i wizualizacja (2/3)
    col1, col2 = st.columns([1, 2])

    # ----------------------------------------------------------------------------
    # Kolumna 1: Parametry i uruchomienie pojedynczej symulacji
    # ----------------------------------------------------------------------------
    with col1:
        # Slider do wyboru pozycji grzejnika w kierunku x
        radiator_pos_x = st.slider(
            "Pozycja grzejnika (od okna do ściany)", 0.2, 3.8, 0.2, step=0.2
        )

        # Przycisk uruchamiający symulację
        if st.button("Uruchom Symulację (Problem 1)"):
            # Utworzenie instancji solwera z aktualną konfiguracją
            sim = HeatEquationSolver(config)

            # Ustawienie okna na lewej ścianie (x=0)
            sim.set_windows(left=True, right=False)

            # Dodanie grzejnika o wymiarach 0.2m x 1.0m na wybranej pozycji
            sim.add_radiator(x_start=radiator_pos_x, y_start=1.5, width=0.2, height=1.0)

            # Uruchomienie symulacji (z paskiem postępu)
            sim.run(steps)

            # Obliczenie metryk jakości ogrzewania
            mean_temp = np.mean(sim.u) - 273.15  # Średnia temperatura [°C]
            std_dev = np.std(sim.u)  # Odchylenie standardowe (miara komfortu)
            energy_kwh = sim.total_energy / 3.6e6  # Zużyta energia [kWh]

            # Wyświetlenie metryk
            st.metric("Średnia Temperatura", f"{mean_temp:.2f} °C")
            st.metric("Komfort (Odchylenie Std)", f"{std_dev:.4f}")
            st.metric("Zużyta Energia", f"{energy_kwh:.2f} kWh")

            # Zapisanie wyników do session_state (dla wizualizacji)
            st.session_state["p1_map"] = sim.u
            st.session_state["p1_x"] = radiator_pos_x

    # ----------------------------------------------------------------------------
    # Kolumna 2: Wizualizacja mapy ciepła
    # ----------------------------------------------------------------------------
    with col2:
        # Sprawdzenie, czy symulacja została już uruchomiona
        if "p1_map" in st.session_state:
            # Utworzenie wykresu mapy ciepła
            fig, ax = plt.subplots()

            # Wyświetlenie temperatury (konwersja K -> °C)
            im = ax.imshow(
                st.session_state["p1_map"] - 273.15,
                cmap="inferno",
                origin="lower",
                extent=[0, 4, 0, 4],
                vmin=config["u_outdoor"] - 273.15,
                vmax=config["thermostat_temp"] + 5 - 273.15,
            )
            plt.colorbar(im, label="Temp [°C]")
            ax.set_title(f"Mapa ciepła (Grzejnik na x={st.session_state['p1_x']}m)")
            ax.set_xlabel("x [m]")
            ax.set_ylabel("y [m]")

            # Narysowanie prostokąta oznaczającego pozycję grzejnika
            rect = plt.Rectangle(
                (st.session_state["p1_x"], 1.5),
                0.2,
                1.0,
                linewidth=2,
                edgecolor="cyan",
                facecolor="none",
            )
            ax.add_patch(rect)
            st.pyplot(fig)
        else:
            st.info("Kliknij 'Uruchom', aby zobaczyć wynik.")
    st.divider()

    # ----------------------------------------------------------------------------
    # Analiza parametryczna: wpływ pozycji grzejnika na komfort
    # ----------------------------------------------------------------------------

    st.subheader("Analiza zbiorcza: Wpływ odległości grzejnika od oknana komfort")
    st.write(
        "Uruchom serię symulacji, aby zobaczyć jak odległość od okna wpływa na odchylenie standardowe (komfort) i średnią temperaturę."
    )

    col_loop_1, col_loop_2 = st.columns(2)
    with col_loop_1:
        # Wybór liczby punktów pomiarowych (rozdzielczość wykresu)
        num_samples = st.slider(
            "Liczba punktów pomiarowych (próbek)",
            min_value=5,
            max_value=20,
            value=10,
            help="Więcej punktów = ładniejszy wykres, ale dłuższy czas obliczeń.",
        )

    # Przycisk uruchamiający pętlę symulacji
    if st.button("Uruchom Pętlę Symulacji (Generuj Wykresy)"):
        # Parametry pętli symulacji
        radiator_width = 0.2  # Szerokość grzejnika [m]

        # Generowanie równomiernie rozłożonych pozycji grzejnika
        x_positions = np.linspace(0.1, config["Lx"] - radiator_width - 0.1, num_samples)

        # Listy do przechowywania wyników
        results_sigma = []  # Odchylenie standardowe (komfort)
        results_mean = []  # Średnia temperatura

        # Inicjalizacja paska postępu
        loop_progress = st.progress(0)
        status_text = st.empty()

        start_time = time.time()

        # Pętla po wszystkich pozycjach grzejnika
        for i, x_pos in enumerate(x_positions):
            status_text.text(
                f"Symulacja {i + 1}/{num_samples} (Grzejnik na {x_pos:.2f} m)..."
            )

            # Utworzenie nowego solwera dla każdej pozycji
            sim_loop = HeatEquationSolver(config)
            sim_loop.add_radiator(
                x_start=x_pos, y_start=1.5, width=radiator_width, height=1.0
            )

            # Wykonanie symulacji (bez paska postępu, aby przyspieszyć)
            for _ in range(steps):
                sim_loop.step()

            # Zapisanie wyników (konwersja K -> °C)
            results_sigma.append(np.std(sim_loop.u - 273.15))
            results_mean.append(np.mean(sim_loop.u) - 273.15)

            # Aktualizacja paska postępu
            loop_progress.progress((i + 1) / num_samples)

        loop_progress.progress(100)
        status_text.text(f"Zakończono w {time.time() - start_time:.2f} s!")

        # ----------------------------------------------------------------------------
        # Wizualizacja wyników pętli symulacji
        # ----------------------------------------------------------------------------

        # Utworzenie dwóch wykresów obok siebie
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

        # Wykres 1: Komfort cieplny (odchylenie standardowe)
        ax1.plot(x_positions, results_sigma, "o-", color="crimson")
        ax1.set_title("Komfort cieplny (Sigma)")
        ax1.set_xlabel("Odległość grzejnika od okna [m]")
        ax1.set_ylabel("Odchylenie standardowe [°C]")
        ax1.grid(True, linestyle="--", alpha=0.6)
        ax1.yaxis.set_major_formatter(ticker.FormatStrFormatter("%.4f"))

        # Wykres 2: Efektywność ogrzewania (średnia temperatura)
        ax2.plot(x_positions, results_mean, "s-", color="navy")
        ax2.set_title("Efektywność (Średnia temperatura)")
        ax2.set_xlabel("Odległość grzejnika od okna [m]")
        ax2.set_ylabel("Średnia temperatura [°C]")
        ax2.grid(True, linestyle="--", alpha=0.6)
        ax2.yaxis.set_major_formatter(ticker.FormatStrFormatter("%.2f"))

        plt.tight_layout()
        st.pyplot(fig)

        st.info("""
        **Interpretacja:**
        * **Lewy wykres:** Niższa wartość oznacza bardziej równomierny rozkład ciepła. Sprawdź, czy grzejnik pod oknem (x bliskie 0) daje niższe odchylenie.
        * **Prawy wykres:** Wyższa wartość oznacza lepsze wykorzystanie energii. Spadki mogą oznaczać straty ciepła przez ściany.
        """)
# ============================================================================
# TAB 2: Problem 2 - Pasożytnictwo cieplne w budynkach wielomieszkaniowych
# ============================================================================

with tab2:
    st.header("2. Pasożytnictwo cieplne")
    st.write(
        "Układ trzech mieszkań. Badamy jak zachowanie sąsiadów wpływa na komfort i koszty mieszkańców mieszkania środkowego."
    )

    # Wybór scenariusza symulacji
    scenario = st.selectbox(
        "Wybierz scenariusz:",
        [
            "Współpraca (Wszyscy grzeją)",
            "Pasożytnictwo (Sąsiedzi grzeją, mieszkanie środkowe nie)",
            "Izolacja (Mieszkanie środkowe grzeje, sąsiedzi nie)",
        ],
    )

    # Przycisk uruchamiający symulację
    if st.button("Uruchom Symulację (Problem 2)"):
        # Konfiguracja dla układu trzech pokoi (3 x 4m = 12m)
        cfg_3 = config.copy()
        cfg_3["Lx"] = 12.0  # Potrójnie szerszy pokój (3 mieszkania po 4m)

        # Określenie, które grzejniki są aktywne w danym scenariuszu
        radiators = []
        if scenario == "Współpraca (Wszyscy grzeją)":
            radiators = ["left", "center", "right"]  # Wszystkie 3 grzejniki
            cfg_3["power"] = power_w * 3  # Łączna moc: 3 grzejniki
        elif scenario == "Pasożytnictwo (Sąsiedzi grzeją, mieszkanie środkowe nie)":
            radiators = ["left", "right"]  # Tylko grzejniki sąsiadów
            cfg_3["power"] = power_w * 2  # Łączna moc: 2 grzejniki
        else:  # "Izolacja (Mieszkanie środkowe grzeje, sąsiedzi nie)"
            radiators = ["center"]  # Tylko grzejnik środkowy
            cfg_3["power"] = power_w * 1  # Łączna moc: 1 grzejnik

        # Utworzenie solwera dla układu trzech pokoi
        sim3 = HeatEquationSolver(cfg_3)
        sim3.set_windows(left=False, right=False)  # Brak okien zewnętrznych
        sim3.clear_radiators()  # Czyszczenie domyślnych grzejników

        # Dodanie grzejników w zależności od scenariusza
        # Lewy pokój (0-4m): grzejnik przy lewej ścianie
        if "left" in radiators:
            sim3.add_radiator(0.2, 1.5, 0.2, 1.0)
        # Środkowy pokój (4-8m): grzejnik przy dolnej ścianie
        if "center" in radiators:
            sim3.add_radiator(5.5, 0.5, 1.0, 0.2)
        # Prawy pokój (8-12m): grzejnik przy prawej ścianie
        if "right" in radiators:
            sim3.add_radiator(11.6, 1.5, 0.2, 1.0)

        # Ustawienie obszaru pomiaru termostatu w zależności od scenariusza
        if scenario == "Współpraca (Wszyscy grzeją)":
            # Termostat mierzy temperaturę w całym układzie (0-12m)
            sim3.set_sensor_region(0.0, 12.0)

        elif scenario == "Pasożytnictwo (Sąsiedzi grzeją, mieszkanie środkowe nie)":
            # Termostat mierzy tylko w lewym pokoju (sąsiad 1)
            sim3.set_sensor_region(0.0, 4.0)

        else:  # "Izolacja (Mieszkanie środkowe grzeje, sąsiedzi nie)"
            # Termostat mierzy tylko w środkowym pokoju (Ty)
            sim3.set_sensor_region(4.0, 8.0)

        # Uruchomienie symulacji
        sim3.run(steps)

        # Wyodrębnienie Twojego pokoju (środkowy, 4-8m)
        idx_start = int(4.0 / sim3.dx)  # Indeks początku środkowego pokoju
        idx_end = int(8.0 / sim3.dx)  # Indeks końca środkowego pokoju
        my_room = sim3.u[:, idx_start:idx_end]  # Wycięcie fragmentu siatki
        my_temp = np.mean(my_room) - 273.15  # Średnia temperatura w Twoim pokoju [°C]

        # Obliczenie całkowitej zużytej energii [kWh]
        total_energy_kwh = sim3.total_energy / 3.6e6

        # Obliczenie Twojego kosztu energii w zależności od scenariusza
        my_cost_kwh = 0.0
        if scenario == "Współpraca (Wszyscy grzeją)":
            my_cost_kwh = total_energy_kwh / 3  # Podział kosztów na 3 mieszkania
        elif scenario == "Izolacja (Mieszkanie środkowe grzeje, sąsiedzi nie)":
            my_cost_kwh = total_energy_kwh  # Płacisz za wszystko
        else:  # "Pasożytnictwo (Sąsiedzi grzeją, mieszkanie środkowe nie)"
            my_cost_kwh = 0.0  # Nie płacisz nic

        neighbor_temp = np.mean(sim3.u[:, :idx_start]) - 273.15  # Lewy sąsiad
        # Wyświetlenie metryk w trzech kolumnach
        col1, col2, col3 = st.columns(3)

        # Metryka 1: Twoja średnia temperatura
        # col1.metric("Twoja Średnia Temp.", f"{my_temp:.2f} °C")
        col1.metric(
            "Twoja Średnia Temp.",
            f"{my_temp:.2f} °C",
            delta=f"{-neighbor_temp + my_temp:.1f} °C vs sąsiedzi",
        )

        # Metryka 2: Twój koszt energii (z kolorowym wskaźnikiem)
        delta_color = "normal"
        if my_cost_kwh == 0:
            delta_color = "off"  # Szary kolor dla zerowego kosztu

        col2.metric(
            "Twój Koszt Energii", f"{my_cost_kwh:.2f} kWh", delta_color=delta_color
        )

        # Metryka 3: Temperatura sąsiada (z różnicą względem Ciebie)
        col3.metric("Temp. Sąsiada", f"{neighbor_temp:.2f} °C")

        st.divider()

        fig, ax = plt.subplots(figsize=(10, 3))
        im = ax.imshow(
            sim3.u - 273.15,
            cmap="inferno",
            origin="lower",
            extent=[0, 12, 0, 4],
            vmin=config["u_outdoor"] - 273.15,
            vmax=config["thermostat_temp"] + 5 - 273.15,
        )

        ax.axvline(4.0, color="white", linestyle="--", alpha=0.5)
        ax.axvline(8.0, color="white", linestyle="--", alpha=0.5)
        ax.text(2, 3.5, "SĄSIAD 1", color="white", ha="center", fontweight="bold")
        ax.text(6, 3.5, "TY", color="white", ha="center", fontweight="bold")
        ax.text(10, 3.5, "SĄSIAD 2", color="white", ha="center", fontweight="bold")

        plt.colorbar(im, label="Temp [°C]")
        ax.set_title(f"Rozkład temperatury: {scenario}")
        st.pyplot(fig)

        # ----------------------------------------------------------------------------
        # Interpretacja wyników dla użytkownika
        # ----------------------------------------------------------------------------

        if scenario == "Pasożytnictwo (Sąsiedzi grzeją, mieszkanie środkowe nie)":
            # Sprawdzenie, czy pasożytnictwo się opłaca
            if (
                my_temp > config["u_outdoor"] - 273.15 + 5
            ):  # Jeśli jest wyraźnie cieplej niż na dworze
                st.success(
                    f"Opłacało się! Masz {my_temp:.1f}°C za darmo dzięki sąsiadom."
                )
            else:
                st.warning(
                    "Pasożytnictwo nie działa - sąsiedzi grzeją za słabo, albo ściany są zbyt izolowane!"
                )
        elif scenario == "Izolacja (Mieszkanie środkowe grzeje, sąsiedzi nie)":
            st.error(
                "To najgorszy scenariusz ekonomiczny. Ogrzewasz nie tylko siebie, ale też wyziębione mieszkania obok."
            )

# ============================================================================
# TAB 3: Raport teoretyczny i wnioski
# ============================================================================

with tab3:
    st.title("Raport z Projektu: Równanie Ciepła")

    # ----------------------------------------------------------------------------
    # Sekcja 1: Wstęp teoretyczny
    # ----------------------------------------------------------------------------

    st.markdown("""
    ### 1. Wstęp Teoretyczny
    W projekcie wykorzystano numeryczne rozwiązanie **równania ciepła** metodą różnic skończonych.
    Ewolucję temperatury $u(x,y,t)$ opisuje równanie:
    """)

    st.latex(r"""
    \frac{\partial u}{\partial t} = \alpha \left( \frac{\partial^2 u}{\partial x^2} + \frac{\partial^2 u}{\partial y^2} \right) + \frac{P \cdot r_{gaz}}{p \cdot A \cdot c_p} \cdot u \cdot \mathbf{1}_{\text{grzejnik}}
    """)

    st.markdown("""
    Gdzie:
    * $\\alpha$ - współczynnik dyfuzji ciepła (uwzględniający konwekcję turbulentną).
    * Człon źródłowy jest aktywny tylko w miejscu grzejnika i gdy temperatura < termostat.
    """)

    # ----------------------------------------------------------------------------
    # Sekcja 2: Warunki brzegowe
    # ----------------------------------------------------------------------------

    st.markdown("### 2. Warunki Brzegowe (Robin)")
    st.markdown(
        "Na styku ściana-zewnętrze oraz okno-zewnętrze zastosowano warunek mieszany (Robina), uwzględniający ucieczkę ciepła:"
    )

    st.latex(r"""
    \frac{\partial u}{\partial n} = -\frac{\lambda_{mat}}{\lambda_{air}} (u_{brzeg} - u_{zew})
    """)

    st.markdown(
        "W implementacji numerycznej przekłada się to na średnią ważoną temperatury wewnętrznej i zewnętrznej."
    )

    st.divider()

    # ----------------------------------------------------------------------------
    # Sekcja 3: Tabela parametrów fizycznych
    # ----------------------------------------------------------------------------

    st.markdown("### 3. Tabela Parametrów Fizycznych")
    st.write("Wartości przyjęte w aktualnej symulacji:")

    import pandas as pd

    # Przygotowanie danych do tabeli
    params_data = {
        "Parametr": [
            "Dyfuzyjność (Alpha)",
            "Przewodność ściany",
            "Przewodność okna",
            "Moc grzejnika",
            "Temp. Zewnątrz",
        ],
        "Wartość": [
            f"{config['alpha']:.2e}",
            f"{config['lambda_wall']}",
            f"{config['lambda_window']}",
            f"{config['power']} W",
            f"{config['u_outdoor'] - 273.15:.1f} °C",
        ],
        "Jednostka": [
            "m²/s",
            "W/(m·K)",
            "W/(m·K)",
            "W",
            "Stopnie Celsjusza przekonwertowane na Kelwiny",
        ],
    }
    df_params = pd.DataFrame(params_data)
    st.dataframe(df_params, hide_index=True)
    st.markdown("W projekcie świadomie przyjąłem $$ \\alpha $$ dwa rzędy wielkości większą niż w rzeczywistości, aby zrekompensować brak wymiany ciepła przez konwekcje." )
    st.divider()

    # ----------------------------------------------------------------------------
    # Sekcja 4: Wnioski z eksperymentów
    # ----------------------------------------------------------------------------

    st.header("4. Wnioski z Eksperymentów")

    # Wnioski do Problemu 1
    with st.expander("Wnioski do Problemu 1 (Lokalizacja Grzejnika)", expanded=True):
        st.markdown("""
        **Hipoteza:** Umieszczenie grzejnika pod oknem powinno poprawić komfort cieplny (zmniejszyć odchylenie standardowe).
        
        **Obserwacje z symulacji:**
        1.  Grzejnik umieszczony bezpośrednio pod oknem (x=0.2m) powoduje dokładnie taki sam efekt jak umieszczenie go pod przeciwległą ścianą.*
        2.  Najlepszy rezultat, czyli najniższe odchylenie standardowe, uzyskujemy gdy grzejnik umieszczony jest po środku pokoju.
        3.  O ile umiejscowienie grzejnika znacząco wpływa na odchylenie standardowe temperatury, o tyle nie ma wpływu na średnią temperaturę w pokoju.
        4.  W projekcie starałem się zrekompensować brak wymiany ciepła przez konwekcje poprzez zwiększenie współczynnika dyfuzji ciepła, ale i tak jest to za mało,
         aby uzyskać realistyczne wyniki. W istocie, gdyby współczynnik dyfuzji ciepła był taki jak w rzeczywistości, to powietrze byłoby o wiele bardziej istotnym izolatorem niż ściany czy okna, bo ciepło nigdy by nie zdąrzyło do nich dotrzeć.
        """)

    # Wnioski do Problemu 2
    with st.expander("Wnioski do Problemu 2 (Pasożytnictwo)", expanded=True):
        st.markdown("""
        **Scenariusz Pasożytnictwa:**
        * Gdy sąsiedzi grzeją, a środkowe mieszkanie jest nieogrzewane, temperatura w nim stabilizuje się na poziomie około 3°C wyższym niż na zewnątrz.
        * Koszt ogrzewania wynosi wtedy 0 zł, ale komfort cieplny jest zazwyczaj poniżej normy (chyba że izolacja ścian działowych jest bardzo słaba).
        
        **Scenariusz Izolacji (Samotny Wilk):**
        * Gdy grzane jest tylko środkowe mieszkanie, zużycie energii przypadające na jedno mieszkanie jest nieznacznie mniejsze niż w przypadku współpracy, ale średni komfort cieplny we wszystkich trzech mieszkaniach jest o wiele gorszy.

        **Scenariusz Współpracy (Wszyscy grzeją):**
        * Tutaj jedyną ciekawą obserwacją jest to, że temperatura w środkowym mieszkaniu jest o wiele wyższa niż w mieszkaniach sąsiednich i wyższa niż zadana na termostacie.
        * Dzieje się tak, poniewaz w tym teoretycznym modelu nie uwzględniłem okien w mieszkaniach, aby bardziej uwypuklić efekt pasozytnictwa.
        * Wniosek z tej obserwacji jest taki, ze wynalazek okien musiał być ogromnym krokiem w rozwoju cywilizacji i upowszechnił się zapewne wraz ze zwartą zabudową :).
        """)

    st.info(
        "Dane w tabeli są generowane dynamicznie na podstawie parametrów globalnych."
    )
