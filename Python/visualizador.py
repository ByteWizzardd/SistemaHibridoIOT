# -*- coding: utf-8 -*-
"""
visualizador.py — Visualización en tiempo real de la congestión de tráfico

Muestra gráficas matplotlib actualizadas en tiempo real:
- Panel superior: líneas históricas de congestión por dirección
- Panel inferior: barras de congestión actual

Usa estilo oscuro profesional para mejor presentación.

Autor: Proyecto Sistema Híbrido IoT
"""

import sys
import numpy as np
import matplotlib
matplotlib.use('TkAgg')  # Backend interactivo para Windows
import matplotlib.pyplot as plt
from collections import deque

# Forzar UTF-8 en consola de Windows
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

class VisualizadorTrafico:
    """
    Visualizador en tiempo real de la congestión de tráfico.

    Crea una ventana con dos gráficas:
    - Superior: líneas históricas de congestión (rolling window de 100 puntos)
    - Inferior: barras de congestión actual por dirección
    """

    # Colores por dirección
    COLORES = {
        "N": "#4FC3F7",   # Azul claro — Norte
        "S": "#00E5FF",   # Cyan — Sur
        "E": "#FF5252",   # Rojo — Este
        "O": "#FFB74D",   # Naranja — Oeste
    }

    NOMBRES = {"N": "Norte", "S": "Sur", "E": "Este", "O": "Oeste"}
    DIRECCIONES = ["N", "S", "E", "O"]

    def __init__(self, max_puntos=100):
        """
        Args:
            max_puntos: Número máximo de puntos en la gráfica histórica
        """
        self.max_puntos = max_puntos

        # Datos históricos (rolling window)
        self.datos = {d: deque(maxlen=max_puntos) for d in self.DIRECCIONES}
        self.horas = deque(maxlen=max_puntos)
        self.pasos = deque(maxlen=max_puntos)
        self.paso_actual = 0

        # Configurar estilo oscuro
        plt.style.use("dark_background")

        # Crear figura con dos subplots
        self.fig, (self.ax_lineas, self.ax_barras) = plt.subplots(
            2, 1,
            figsize=(12, 8),
            gridspec_kw={"height_ratios": [3, 1]},
        )

        self.fig.suptitle(
            "🚦 Sistema de Control de Tráfico — Monitoreo en Tiempo Real",
            fontsize=14,
            fontweight="bold",
            color="#E0E0E0",
        )

        # --- Panel superior: líneas históricas ---
        self.lineas = {}
        for d in self.DIRECCIONES:
            linea, = self.ax_lineas.plot(
                [], [],
                color=self.COLORES[d],
                linewidth=2,
                label=self.NOMBRES[d],
                alpha=0.9,
            )
            self.lineas[d] = linea

        self.ax_lineas.set_xlim(0, max_puntos)
        self.ax_lineas.set_ylim(0, 105)
        self.ax_lineas.set_ylabel("Congestión (%)", fontsize=11)
        self.ax_lineas.set_xlabel("Paso de simulación", fontsize=10)
        self.ax_lineas.set_title("Historial de Congestión", fontsize=12, pad=10)
        self.ax_lineas.legend(loc="upper left", fontsize=9, framealpha=0.3)
        self.ax_lineas.grid(True, alpha=0.2, linestyle="--")
        self.ax_lineas.axhline(y=70, color="#FF5252", linestyle=":", alpha=0.4, label="")
        self.ax_lineas.axhline(y=40, color="#FFB74D", linestyle=":", alpha=0.3, label="")

        # Texto de hora simulada
        self.texto_hora = self.ax_lineas.text(
            0.98, 0.95, "Hora: --:--",
            transform=self.ax_lineas.transAxes,
            fontsize=11,
            fontweight="bold",
            color="#FFF176",
            ha="right",
            va="top",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="#333333", alpha=0.8),
        )

        # --- Panel inferior: barras de congestión actual ---
        self.nombres_barras = [self.NOMBRES[d] for d in self.DIRECCIONES]
        self.colores_barras = [self.COLORES[d] for d in self.DIRECCIONES]
        self.barras = self.ax_barras.barh(
            self.nombres_barras,
            [0, 0, 0, 0],
            color=self.colores_barras,
            alpha=0.8,
            edgecolor="white",
            linewidth=0.5,
        )
        self.ax_barras.set_xlim(0, 100)
        self.ax_barras.set_xlabel("Congestión (%)", fontsize=10)
        self.ax_barras.set_title("Estado Actual", fontsize=12, pad=10)
        self.ax_barras.grid(True, axis="x", alpha=0.2, linestyle="--")

        # Etiquetas de porcentaje en las barras
        self.textos_barras = []
        for i in range(4):
            txt = self.ax_barras.text(
                2, i, "0%",
                va="center",
                fontsize=10,
                fontweight="bold",
                color="white",
            )
            self.textos_barras.append(txt)

        self.fig.tight_layout()
        self._iniciado = False

    def iniciar(self):
        """Muestra la ventana de la gráfica (no bloqueante)."""
        plt.ion()  # Modo interactivo
        self.fig.show()
        self._iniciado = True

    def actualizar(self, congestion, hora=None):
        """
        Agrega un nuevo punto de datos y actualiza la visualización.

        Args:
            congestion: dict {"N": float, "S": float, "E": float, "O": float}
            hora: Hora simulada (float, opcional) para mostrar en pantalla
        """
        self.paso_actual += 1
        self.pasos.append(self.paso_actual)

        if hora is not None:
            self.horas.append(hora)

        # Agregar datos al historial
        for d in self.DIRECCIONES:
            self.datos[d].append(congestion.get(d, 0))

        # Actualizar líneas históricas
        x_data = list(self.pasos)
        for d in self.DIRECCIONES:
            self.lineas[d].set_data(x_data, list(self.datos[d]))

        # Ajustar eje X para el rolling window
        if len(x_data) > 0:
            x_min = max(0, x_data[-1] - self.max_puntos)
            x_max = x_data[-1] + 5
            self.ax_lineas.set_xlim(x_min, x_max)

        # Actualizar texto de hora
        if hora is not None:
            horas_int = int(hora)
            minutos_int = int((hora - horas_int) * 60)
            self.texto_hora.set_text(f"Hora: {horas_int:02d}:{minutos_int:02d}")

        # Actualizar barras
        valores = [congestion.get(d, 0) for d in self.DIRECCIONES]
        for i, (barra, valor) in enumerate(zip(self.barras, valores)):
            barra.set_width(valor)

            # Cambiar color según nivel de congestión
            if valor > 70:
                barra.set_color("#FF5252")   # Rojo — alta congestión
            elif valor > 40:
                barra.set_color("#FFB74D")   # Naranja — media
            else:
                barra.set_color(self.colores_barras[i])  # Color normal

            # Actualizar etiqueta
            x_pos = max(valor + 2, 5)
            self.textos_barras[i].set_position((x_pos, i))
            self.textos_barras[i].set_text(f"{valor:.0f}%")

        # Redibujar
        self.fig.canvas.draw_idle()
        self.fig.canvas.flush_events()

    def cerrar(self):
        """Cierra la ventana de la gráfica."""
        plt.close(self.fig)

    def guardar(self, ruta="datos/grafica_congestion.png"):
        """
        Guarda la gráfica actual como imagen.

        Args:
            ruta: Ruta del archivo de imagen
        """
        self.fig.savefig(ruta, dpi=150, bbox_inches="tight", facecolor="#1E1E1E")
        print(f"📊 Gráfica guardada en: {ruta}")


# =============================================================================
# DEMOSTRACIÓN (con datos sintéticos)
# =============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("  📊 DEMOSTRACIÓN DEL VISUALIZADOR DE TRÁFICO")
    print("  Generando datos sintéticos de un día completo...")
    print("=" * 70)
    print()

    # Crear visualizador
    viz = VisualizadorTrafico(max_puntos=100)
    viz.iniciar()

    # Generar datos sintéticos que simulan un día (6:00 a 22:00)
    np.random.seed(42)
    PASOS = 120
    hora_inicio = 6.0
    hora_fin = 22.0

    for i in range(PASOS):
        hora = hora_inicio + (hora_fin - hora_inicio) * (i / PASOS)

        # Simular perfil horario con ruido
        # Pico AM ~8:00, Valle ~14:00, Pico PM ~18:00
        base_am = 60 * np.exp(-0.5 * ((hora - 8.0) / 1.5) ** 2)
        base_pm = 50 * np.exp(-0.5 * ((hora - 18.0) / 2.0) ** 2)
        base_medio = 25 * np.exp(-0.5 * ((hora - 13.0) / 1.5) ** 2)

        base = 15 + base_am + base_pm + base_medio

        congestion = {
            "N": np.clip(base * 1.3 + np.random.normal(0, 8), 0, 100),
            "S": np.clip(base * 1.1 + np.random.normal(0, 7), 0, 100),
            "E": np.clip(base * 0.8 + np.random.normal(0, 6), 0, 100),
            "O": np.clip(base * 0.7 + np.random.normal(0, 5), 0, 100),
        }

        viz.actualizar(congestion, hora)

        # Imprimir cada 10 pasos
        if i % 10 == 0:
            h = int(hora)
            m = int((hora - h) * 60)
            print(
                f"  Hora {h:02d}:{m:02d} | "
                f"Norte: {congestion['N']:5.1f}% | "
                f"Sur: {congestion['S']:5.1f}% | "
                f"Este: {congestion['E']:5.1f}% | "
                f"Oeste: {congestion['O']:5.1f}%"
            )

        plt.pause(0.08)  # Pausa corta para animación rápida en demo

    print()
    print("✅ Demostración completada.")
    print("   Cierra la ventana de la gráfica para salir.")

    plt.ioff()
    plt.show()
