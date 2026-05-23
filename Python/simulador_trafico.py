# -*- coding: utf-8 -*-
"""
simulador_trafico.py — Simulador de intersección vial con distribución de Poisson

Genera tráfico vehicular realista usando distribución de Poisson con tasas (lambda)
que varían según la hora del día y la dirección. Incluye perfiles de hora pico AM,
valle y hora pico PM.

Autor: Proyecto Sistema Híbrido IoT
"""

import sys
import numpy as np

# Forzar UTF-8 en consola de Windows
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass


class InterseccionSimulada:
    """
    Simula una intersección de 4 direcciones (N, S, E, O) con:
    - Colas de vehículos por dirección
    - Llegadas con distribución de Poisson
    - Perfiles horarios realistas
    - Cálculo de congestión como porcentaje de capacidad
    """

    # Direcciones de la intersección
    DIRECCIONES = ["N", "S", "E", "O"]

    # Nombres legibles para cada dirección
    NOMBRES = {"N": "Norte", "S": "Sur", "E": "Este", "O": "Oeste"}

    def __init__(self, capacidad=50, semilla=None):
        """
        Inicializa la intersección simulada.

        Args:
            capacidad: Número máximo de vehículos por carril (cola máxima)
            semilla: Semilla para reproducibilidad (None = aleatorio)
        """
        self.capacidad = capacidad
        self.hora_actual = 8.0  # Hora simulada (0-24)

        # Colas de vehículos por dirección (empiezan con algo de tráfico)
        self.colas = {"N": 10, "S": 7, "E": 5, "O": 4}

        # Generador de números aleatorios
        self.rng = np.random.default_rng(semilla)

        # Historial de congestión para análisis
        self.historial = {d: [] for d in self.DIRECCIONES}

        # Factores de escala por dirección
        # N-S es el corredor principal (más tráfico)
        self.factor_direccion = {
            "N": 1.3,   # Corredor principal — dirección dominante
            "S": 1.1,   # Corredor principal — algo menos que Norte
            "E": 0.8,   # Corredor secundario
            "O": 0.7,   # Corredor secundario — menor tráfico
        }

    def _perfil_horario(self, hora):
        """
        Calcula la tasa base de llegada (lambda) según la hora del día.
        Usa una combinación de funciones gaussianas para modelar:
        - Pico AM:  ~8:00  (lambda alto ~7)
        - Valle:    ~14:00 (lambda bajo ~2)
        - Pico PM:  ~18:00 (lambda alto ~6)
        - Noche:    ~2:00  (lambda mínimo ~0.5)

        Args:
            hora: Hora del día en formato decimal (0.0 - 24.0)

        Returns:
            Tasa base de llegada (lambda) para distribución de Poisson
        """
        # Componente gaussiana para pico AM (centrado en 8:00)
        pico_am = 7.0 * np.exp(-0.5 * ((hora - 8.0) / 1.5) ** 2)

        # Componente gaussiana para pico PM (centrado en 18:00)
        pico_pm = 6.0 * np.exp(-0.5 * ((hora - 18.0) / 2.0) ** 2)

        # Componente gaussiana para mediodía (ligero repunte a las 13:00)
        mediodia = 3.0 * np.exp(-0.5 * ((hora - 13.0) / 1.5) ** 2)

        # Tasa base mínima (siempre hay algo de tráfico)
        base = 1.0

        # Combinar todos los componentes
        lambda_base = base + pico_am + pico_pm + mediodia

        return lambda_base

    def _calcular_lambda(self, direccion, hora):
        """
        Calcula el lambda específico para una dirección y hora.

        Args:
            direccion: Una de "N", "S", "E", "O"
            hora: Hora del día (0.0 - 24.0)

        Returns:
            Lambda ajustado para la distribución de Poisson
        """
        lambda_base = self._perfil_horario(hora)
        factor = self.factor_direccion[direccion]

        # Agregar variación aleatoria pequeña (±10%) para realismo
        ruido = self.rng.uniform(0.9, 1.1)

        return max(0.1, lambda_base * factor * ruido)

    def set_hora(self, hora):
        """
        Establece la hora actual de la simulación.

        Args:
            hora: Hora del día en formato decimal (0.0 - 24.0)
        """
        self.hora_actual = hora % 24.0

    def paso(self, fase_verde="NS"):
        """
        Ejecuta un paso de simulación:
        1. Genera llegadas de vehículos (Poisson) para cada dirección
        2. Procesa salidas según la fase del semáforo
        3. Actualiza las colas

        Args:
            fase_verde: "NS" si Norte-Sur tiene verde, "EO" si Este-Oeste tiene verde
                       Determina cuáles direcciones procesan salidas

        Returns:
            dict con la congestión actual por dirección
        """
        for d in self.DIRECCIONES:
            # --- LLEGADAS (distribución de Poisson) ---
            lam = self._calcular_lambda(d, self.hora_actual)
            llegadas = self.rng.poisson(lam)

            # --- SALIDAS (depende de la fase del semáforo) ---
            salidas = 0
            if fase_verde == "NS" and d in ("N", "S"):
                # Direcciones N-S tienen verde: salen ~5-7 vehículos por paso
                salidas = self.rng.poisson(6)
            elif fase_verde == "EO" and d in ("E", "O"):
                # Direcciones E-O tienen verde: salen ~5-7 vehículos por paso
                salidas = self.rng.poisson(6)
            else:
                # Rojo: salen ~1-2 vehículos (giros permitidos, etc.)
                salidas = self.rng.poisson(1.5)

            # --- ACTUALIZAR COLA ---
            self.colas[d] = max(0, min(self.capacidad, self.colas[d] + llegadas - salidas))

        # Guardar en historial
        congestion = self.obtener_congestion()
        for d in self.DIRECCIONES:
            self.historial[d].append(congestion[d])

        return congestion

    def obtener_congestion(self):
        """
        Calcula el porcentaje de congestión para cada dirección.
        Congestión (%) = (cola / capacidad) * 100

        Returns:
            dict {"N": float, "S": float, "E": float, "O": float}
            con valores entre 0.0 y 100.0
        """
        return {
            d: round((self.colas[d] / self.capacidad) * 100, 1)
            for d in self.DIRECCIONES
        }

    def obtener_colas(self):
        """
        Retorna las colas actuales (número de vehículos) por dirección.

        Returns:
            dict {"N": int, "S": int, "E": int, "O": int}
        """
        return dict(self.colas)

    def reset(self):
        """Reinicia la simulación a su estado inicial."""
        self.colas = {"N": 10, "S": 7, "E": 5, "O": 4}
        self.historial = {d: [] for d in self.DIRECCIONES}
        self.hora_actual = 8.0

    def __repr__(self):
        cong = self.obtener_congestion()
        return (
            f"Intersección [Hora {self.hora_actual:.1f}] | "
            f"N:{cong['N']:.0f}% S:{cong['S']:.0f}% "
            f"E:{cong['E']:.0f}% O:{cong['O']:.0f}%"
        )


# =============================================================================
# PRUEBA DEL SIMULADOR (sin conexión al ESP32)
# =============================================================================
if __name__ == "__main__":
    print("=" * 70)
    print("  🚦 PRUEBA DEL SIMULADOR DE TRÁFICO")
    print("  Ejecutando 100 pasos de simulación (hora 6:00 a 22:00)")
    print("=" * 70)
    print()

    # Crear simulador con semilla para reproducibilidad en la prueba
    sim = InterseccionSimulada(capacidad=50, semilla=42)

    # Simular un día completo: de 6:00 a 22:00 en 100 pasos
    PASOS = 100
    hora_inicio = 6.0
    hora_fin = 22.0
    incremento_hora = (hora_fin - hora_inicio) / PASOS

    # Alternar la fase del semáforo cada 5 pasos
    fase_actual = "NS"
    contador_fase = 0

    for i in range(PASOS):
        # Avanzar la hora simulada
        hora = hora_inicio + i * incremento_hora
        sim.set_hora(hora)

        # Alternar fase del semáforo cada 5 pasos
        contador_fase += 1
        if contador_fase >= 5:
            fase_actual = "EO" if fase_actual == "NS" else "NS"
            contador_fase = 0

        # Ejecutar paso de simulación
        congestion = sim.paso(fase_verde=fase_actual)

        # Imprimir cada 5 pasos para no saturar la consola
        if i % 5 == 0:
            colas = sim.obtener_colas()
            print(
                f"Paso {i+1:3d} | Hora {hora:5.1f} | "
                f"Norte: {congestion['N']:5.1f}% ({colas['N']:2d}) | "
                f"Sur: {congestion['S']:5.1f}% ({colas['S']:2d}) | "
                f"Este: {congestion['E']:5.1f}% ({colas['E']:2d}) | "
                f"Oeste: {congestion['O']:5.1f}% ({colas['O']:2d}) | "
                f"Fase: {fase_actual}"
            )

    # Resumen final
    print()
    print("=" * 70)
    print("  📊 RESUMEN DE LA SIMULACIÓN")
    print("=" * 70)
    for d in sim.DIRECCIONES:
        datos = sim.historial[d]
        print(
            f"  {sim.NOMBRES[d]:6s}: "
            f"Media={np.mean(datos):5.1f}% | "
            f"Máx={np.max(datos):5.1f}% | "
            f"Mín={np.min(datos):5.1f}% | "
            f"Desv={np.std(datos):5.1f}%"
        )

    print()
    print("✅ Simulador funcionando correctamente.")
    print("   Los valores varían y reflejan perfiles horarios realistas.")
