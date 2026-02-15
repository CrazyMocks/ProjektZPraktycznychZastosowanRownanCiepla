"""Moduł do rozwiązywania równania ciepła metodą różnic skończonych.

Implementuje solver 2D równania ciepła z warunkami brzegowymi Robina,
grzejnikami sterowanymi termostatem oraz opcjonalnymi oknami.
"""

import streamlit as st
import numpy as np


class HeatEquationSolver:
    """Solver równania ciepła 2D z grzejnikami i termostatem.

    Klasa implementuje numeryczne rozwiązanie równania ciepła na siatce 2D
    z wykorzystaniem metody różnic skończonych (FTCS - Forward Time Centered Space).
    Uwzględnia:
    - Warunki brzegowe typu Robin (konwekcja na ścianach)
    - Grzejniki sterowane termostatem
    - Różne przewodności cieplne dla ścian i okien
    - Pomiar temperatury w wybranym obszarze (sensor termostatu)
    """

    def __init__(self, config):
        """Inicjalizuje solver równania ciepła.

        Args:
            config (dict): Słownik z parametrami konfiguracyjnymi:
                - Lx (float): Długość domeny w kierunku x [m]
                - Ly (float): Długość domeny w kierunku y [m]
                - dx (float): Krok siatki przestrzennej [m]
                - dt (float): Krok czasowy [s]
                - alpha (float): Współczynnik dyfuzji cieplnej [m²/s]
                - u_outdoor (float): Temperatura zewnętrzna [°C]
                - power (float): Moc grzejnika [W]
                - pressure (float): Ciśnienie powietrza [Pa]
                - r_gas (float): Stała gazowa dla powietrza [J/(kg·K)]
                - c_specific (float): Ciepło właściwe powietrza [J/(kg·K)]
                - thermostat_temp (float): Temperatura zadana termostatu [°C]
                - u_start (float): Temperatura początkowa [°C]
                - lambda_air (float, optional): Przewodność cieplna powietrza [W/(m·K)]
                - lambda_wall (float, optional): Przewodność cieplna ściany [W/(m·K)]
                - lambda_window (float, optional): Przewodność cieplna okna [W/(m·K)]
        """
        # Parametry geometryczne domeny
        self.Lx = config["Lx"]
        self.Ly = config["Ly"]
        self.dx = config["dx"]
        self.dt = config["dt"]

        # Liczba punktów siatki w kierunkach x i y
        self.nx = int(round(self.Lx / self.dx))
        self.ny = int(round(self.Ly / self.dx))

        # Parametry fizyczne
        self.alpha = config["alpha"]  # Współczynnik dyfuzji cieplnej
        self.u_outdoor = config["u_outdoor"]  # Temperatura zewnętrzna
        self.P = config["power"]  # Moc grzejnika
        self.p_pressure = config["pressure"]  # Ciśnienie powietrza
        self.r_gas = config["r_gas"]  # Stała gazowa
        self.c_specific = config["c_specific"]  # Ciepło właściwe
        self.area = self.dx * self.dx  # Powierzchnia pojedynczej komórki
        self.thermostat_setting = config["thermostat_temp"]  # Temperatura zadana

        # Inicjalizacja pola temperatury
        self.u = np.ones((self.ny, self.nx)) * config["u_start"]

        # Przewodności cieplne różnych materiałów
        self.lambda_air = config.get("lambda_air", 0.026)
        self.lambda_wall = config.get("lambda_wall", 0.5)
        self.lambda_window = config.get("lambda_window", 2.0)

        # Współczynniki beta dla warunków brzegowych Robina
        # beta = (lambda_material / lambda_air) * dx
        self.beta_wall = (self.lambda_wall / self.lambda_air) * self.dx
        self.beta_window = (self.lambda_window / self.lambda_air) * self.dx

        # Inicjalizacja masek i parametrów grzejnika
        self.radiator_mask = np.zeros((self.ny, self.nx), dtype=bool)
        self.heating_factor_per_step = 0  # Współczynnik grzania na krok czasowy
        self.active_cells_count = 0  # Liczba aktywnych komórek grzejnika
        self.total_energy = 0.0  # Całkowita zużyta energia

        # Maska sensora termostatu (domyślnie cała domena)
        self.sensor_mask = np.ones((self.ny, self.nx), dtype=bool)
        self.window_left = False  # Czy lewa ściana ma okno
        self.window_right = False  # Czy prawa ściana ma okno

    def set_windows(self, left=False, right=False):
        """Określa, czy na skrajnych ścianach (x=0 i x=max) są okna.

        Okna mają wyższą przewodność cieplną niż ściany, co wpływa na
        warunki brzegowe w tych obszarach.

        Args:
            left (bool): Czy lewa ściana (x=0) ma okno
            right (bool): Czy prawa ściana (x=max) ma okno
        """
        self.window_left = left
        self.window_right = right

    def clear_radiators(self):
        """Usuwa wszystkie grzejniki z symulacji.

        Resetuje maskę grzejników oraz wszystkie powiązane parametry.
        """
        self.radiator_mask[:, :] = False
        self.active_cells_count = 0
        self.heating_factor_per_step = 0

    def add_radiator(self, x_start, y_start, width, height):
        """Dodaje grzejnik w określonym prostokątnym obszarze.

        Args:
            x_start (float): Współrzędna x lewego dolnego rogu [m]
            y_start (float): Współrzędna y lewego dolnego rogu [m]
            width (float): Szerokość grzejnika [m]
            height (float): Wysokość grzejnika [m]

        Note:
            Moc grzejnika jest równomiernie rozdzielana na wszystkie komórki.
            Współczynnik grzania jest obliczany z równania stanu gazu doskonałego.
        """
        # Konwersja współrzędnych fizycznych na indeksy siatki
        ix_start = int(round(x_start / self.dx))
        iy_start = int(round(y_start / self.dx))
        ix_end = int(round((x_start + width) / self.dx))
        iy_end = int(round((y_start + height) / self.dx))

        # Ograniczenie do granic domeny
        ix_end = min(ix_end, self.nx)
        iy_end = min(iy_end, self.ny)

        # Ustawienie maski grzejnika
        self.radiator_mask[iy_start:iy_end, ix_start:ix_end] = True

        # Maska wewnętrznych komórek (bez brzegów)
        self.mask_inner = self.radiator_mask[1:-1, 1:-1]
        self.active_cells_count = np.sum(self.mask_inner)

        # Obliczenie współczynnika grzania na podstawie mocy grzejnika
        if self.active_cells_count > 0:
            power_per_cell = self.P / self.active_cells_count
            # Współczynnik z równania stanu gazu: P*V = m*R*T => dT = (P*R*dt)/(p*V*c)
            base_coeff = (power_per_cell * self.r_gas) / (
                self.p_pressure * self.area * self.c_specific
            )
            self.heating_factor_per_step = base_coeff * self.dt

    def set_sensor_region(self, x_start, x_end):
        """Ustawia obszar, w którym termostat mierzy temperaturę.

        Args:
            x_start (float): Początek obszaru pomiarowego w kierunku x [m]
            x_end (float): Koniec obszaru pomiarowego w kierunku x [m]

        Note:
            Termostat oblicza średnią temperaturę tylko z komórek w tym obszarze.
            Obszar obejmuje wszystkie komórki w kierunku y (bez brzegów).
        """
        # Reset maski sensora
        self.sensor_mask[:, :] = False

        # Konwersja współrzędnych na indeksy
        ix_start = int(round(x_start / self.dx))
        ix_end = int(round(x_end / self.dx))

        # Ograniczenie do granic domeny
        ix_end = min(ix_end, self.nx)
        # Ustawienie maski w wybranym obszarze (bez brzegów w y)
        self.sensor_mask[1:-1, ix_start:ix_end] = True

    def _apply_boundary_conditions(self):
        """Aplikuje warunki brzegowe typu Robin na wszystkich krawędziach.

        Warunki brzegowe Robina modelują konwekcję ciepła przez ściany:
        u_boundary = (u_interior + beta * u_outdoor) / (1 + beta)

        gdzie beta = (lambda_material / lambda_air) * dx

        Okna (jeśli są obecne) mają wyższą przewodność, więc używają beta_window.
        """
        # Warunek brzegowy na lewej ścianie (x=0)
        self.u[:, 0] = (self.u[:, 1] + self.beta_wall * self.u_outdoor) / (
            1 + self.beta_wall
        )
        # Warunek brzegowy na prawej ścianie (x=max)
        self.u[:, -1] = (self.u[:, -2] + self.beta_wall * self.u_outdoor) / (
            1 + self.beta_wall
        )

        # Warunek brzegowy na dolnej ścianie (y=0)
        self.u[-1, :] = (self.u[-2, :] + self.beta_wall * self.u_outdoor) / (
            1 + self.beta_wall
        )

        # Warunek brzegowy na górnej ścianie (y=max)
        self.u[0, :] = (self.u[1, :] + self.beta_wall * self.u_outdoor) / (
            1 + self.beta_wall
        )

        # Obliczenie pozycji okien (środkowa połowa wysokości ściany)
        window_size = int(self.ny / 2)
        y_start = int((self.ny - window_size) / 2)
        y_end = y_start + window_size

        # Nadpisanie warunków brzegowych dla okien (wyższa przewodność)
        if self.window_left:
            self.u[y_start:y_end, 0] = (
                self.u[y_start:y_end, 1] + self.beta_window * self.u_outdoor
            ) / (1 + self.beta_window)

        if self.window_right:
            self.u[y_start:y_end, -1] = (
                self.u[y_start:y_end, -2] + self.beta_window * self.u_outdoor
            ) / (1 + self.beta_window)

    def step(self):
        """Wykonuje jeden krok czasowy symulacji.

        Implementuje schemat FTCS (Forward Time Centered Space) dla równania ciepła:
        du/dt = alpha * (d²u/dx² + d²u/dy²)

        Dodatkowo uwzględnia:
        - Grzanie przez grzejniki (sterowane termostatem)
        - Warunki brzegowe Robina
        """
        u = self.u
        # Wydzielenie wewnętrznych komórek (bez brzegów)
        u_inner = u[1:-1, 1:-1]

        # Obliczenie laplasjanu metodą różnic skończonych (5-punktowy szablon)
        # ∇²u ≈ (u[i-1,j] + u[i+1,j] + u[i,j-1] + u[i,j+1] - 4*u[i,j]) / dx²
        laplacian_sum = (
            u[0:-2, 1:-1]
            + u[2:, 1:-1]  # sąsiedzi w kierunku y
            + u[1:-1, 0:-2]
            + u[1:-1, 2:]  # sąsiedzi w kierunku x
            - 4.0 * u_inner
        )
        # Współczynnik dyfuzji: alpha * dt / dx²
        diffusion_factor = (self.alpha * self.dt) / (self.dx**2)
        # Zmiana temperatury z dyfuzji
        change = diffusion_factor * laplacian_sum

        # Pomiar temperatury przez termostat
        if np.any(self.sensor_mask):
            current_mean_temp = np.mean(u[self.sensor_mask])
        else:
            current_mean_temp = np.mean(u)

        # Sterowanie grzejnikiem przez termostat
        if current_mean_temp < self.thermostat_setting:
            if self.active_cells_count > 0:
                # Dodanie ciepła w komórkach grzejnika (proporcjonalne do temperatury)
                change[self.mask_inner] += (
                    self.heating_factor_per_step * u_inner[self.mask_inner]
                )
                # Akumulacja zużytej energii
                self.total_energy += self.P * self.dt

        # Aktualizacja temperatury
        u[1:-1, 1:-1] += change
        # Aplikacja warunków brzegowych
        self._apply_boundary_conditions()

    def run(self, steps):
        """Uruchamia symulację przez określoną liczbę kroków czasowych.

        Args:
            steps (int): Liczba kroków czasowych do wykonania

        Note:
            Wyświetla pasek postępu w interfejsie Streamlit.
            Aktualizacja paska co 10% postępu.
        """
        # Inicjalizacja paska postępu w Streamlit
        progress_bar = st.progress(0)
        status_text = st.empty()

        # Główna pętla symulacji
        for i in range(steps):
            self.step()
            # Aktualizacja paska postępu co 10%
            if i % (steps // 10) == 0:
                progress_bar.progress(i / steps)
                status_text.text(f"Symulacja: {int(i / steps * 100)}%")

        # Zakończenie symulacji
        progress_bar.progress(100)
        status_text.text("Symulacja zakończona!")
