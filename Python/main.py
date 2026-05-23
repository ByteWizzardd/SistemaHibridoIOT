# -*- coding: utf-8 -*-
"""
main.py — Script principal del Sistema Híbrido IoT de Control de Tráfico

Integra todos los módulos:
1. Simulador de tráfico (Poisson) → genera congestión
2. Control adaptativo (lógica difusa) → decide tiempos de verde
3. Comunicación serial → envía tiempos al ESP32
4. Visualizador → muestra gráfica en tiempo real
5. Registro CSV → guarda datos para análisis posterior

Uso:
    python main.py --sin-serial --sin-grafica       # Solo consola
    python main.py --sin-serial                      # Con gráfica, sin ESP32
    python main.py --puerto COM5                     # Con ESP32 en COM5
    python main.py --duracion 300 --velocidad 1.0    # 300 pasos, 1 seg cada uno

Autor: Proyecto Sistema Híbrido IoT
"""

import argparse
import csv
import os
import sys
import time
from datetime import datetime

# Forzar UTF-8 en consola de Windows
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

# Importar módulos del proyecto
from simulador_trafico import InterseccionSimulada
from control_adaptativo import calcular_tiempos


def crear_parser():
    """Crea y retorna el parser de argumentos de línea de comandos."""
    parser = argparse.ArgumentParser(
        description="🚦 Sistema Híbrido IoT — Control Adaptativo de Tráfico",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python main.py --sin-serial --sin-grafica     Modo consola (sin ESP32 ni gráfica)
  python main.py --sin-serial                   Con gráfica, sin ESP32
  python main.py --puerto COM5                  Con ESP32 conectado en COM5
  python main.py --duracion 300 --velocidad 1   300 pasos, 1 seg entre cada uno
        """,
    )

    parser.add_argument(
        "--puerto",
        type=str,
        default="COM3",
        help="Puerto serial del ESP32 (default: COM3)",
    )
    parser.add_argument(
        "--baudrate",
        type=int,
        default=115200,
        help="Velocidad de comunicación serial (default: 115200)",
    )
    parser.add_argument(
        "--sin-serial",
        action="store_true",
        help="Ejecutar sin conexión al ESP32 (modo simulación pura)",
    )
    parser.add_argument(
        "--sin-grafica",
        action="store_true",
        help="Ejecutar sin ventana gráfica (solo consola)",
    )
    parser.add_argument(
        "--duracion",
        type=int,
        default=200,
        help="Número de pasos de simulación (default: 200)",
    )
    parser.add_argument(
        "--velocidad",
        type=float,
        default=2.0,
        help="Segundos entre pasos de simulación (default: 2.0)",
    )
    parser.add_argument(
        "--semilla",
        type=int,
        default=None,
        help="Semilla aleatoria para reproducibilidad",
    )

    return parser


def inicializar_csv(ruta_csv):
    """
    Crea el archivo CSV con encabezados si no existe.

    Args:
        ruta_csv: Ruta completa del archivo CSV

    Returns:
        Ruta del archivo CSV creado/existente
    """
    # Crear directorio si no existe
    directorio = os.path.dirname(ruta_csv)
    if directorio and not os.path.exists(directorio):
        os.makedirs(directorio, exist_ok=True)

    # Crear archivo con encabezados si no existe
    if not os.path.exists(ruta_csv):
        with open(ruta_csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "timestamp",
                "hora_simulada",
                "congestion_N",
                "congestion_S",
                "congestion_E",
                "congestion_O",
                "verde_NS_ms",
                "verde_EO_ms",
                "cola_N",
                "cola_S",
                "cola_E",
                "cola_O",
            ])
        print(f"📄 Archivo CSV creado: {ruta_csv}")

    return ruta_csv


def guardar_registro(ruta_csv, hora_sim, congestion, tiempos, colas):
    """
    Agrega una fila al archivo CSV de registro.

    Args:
        ruta_csv: Ruta del archivo CSV
        hora_sim: Hora simulada (float)
        congestion: dict con congestión por dirección
        tiempos: dict con tiempos de verde {"verde_NS", "verde_EO"}
        colas: dict con colas por dirección
    """
    with open(ruta_csv, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            f"{hora_sim:.2f}",
            f"{congestion['N']:.1f}",
            f"{congestion['S']:.1f}",
            f"{congestion['E']:.1f}",
            f"{congestion['O']:.1f}",
            tiempos["verde_NS"],
            tiempos["verde_EO"],
            colas["N"],
            colas["S"],
            colas["E"],
            colas["O"],
        ])


def imprimir_paso(paso, hora, congestion, tiempos, colas):
    """Imprime el estado actual de la simulación en consola."""
    h = int(hora)
    m = int((hora - h) * 60)

    print(
        f"[{paso:4d}] {h:02d}:{m:02d} │ "
        f"N:{congestion['N']:5.1f}% ({colas['N']:2d}) │ "
        f"S:{congestion['S']:5.1f}% ({colas['S']:2d}) │ "
        f"E:{congestion['E']:5.1f}% ({colas['E']:2d}) │ "
        f"O:{congestion['O']:5.1f}% ({colas['O']:2d}) │ "
        f"Verde NS:{tiempos['verde_NS']:5d}ms EO:{tiempos['verde_EO']:5d}ms"
    )


def imprimir_resumen(historial, tiempos_historial):
    """Imprime estadísticas resumen al final de la simulación."""
    import numpy as np

    print()
    print("=" * 75)
    print("  📊 RESUMEN DE LA SIMULACIÓN")
    print("=" * 75)

    nombres = {"N": "Norte", "S": "Sur", "E": "Este", "O": "Oeste"}

    print(f"\n  {'Dirección':<10s} {'Media':>8s} {'Máximo':>8s} {'Mínimo':>8s} {'Desv.Est':>8s}")
    print("  " + "-" * 42)

    for d in ["N", "S", "E", "O"]:
        datos = historial[d]
        if datos:
            print(
                f"  {nombres[d]:<10s} "
                f"{np.mean(datos):7.1f}% "
                f"{np.max(datos):7.1f}% "
                f"{np.min(datos):7.1f}% "
                f"{np.std(datos):7.1f}%"
            )

    # Tiempos de verde
    if tiempos_historial:
        ns_tiempos = [t["verde_NS"] for t in tiempos_historial]
        eo_tiempos = [t["verde_EO"] for t in tiempos_historial]

        print(f"\n  {'Tiempos verde':<15s} {'Media':>10s} {'Máx':>8s} {'Mín':>8s}")
        print("  " + "-" * 36)
        print(f"  {'NS':<15s} {np.mean(ns_tiempos):9.0f}ms {np.max(ns_tiempos):7d}ms {np.min(ns_tiempos):7d}ms")
        print(f"  {'EO':<15s} {np.mean(eo_tiempos):9.0f}ms {np.max(eo_tiempos):7d}ms {np.min(eo_tiempos):7d}ms")


# =============================================================================
# BUCLE PRINCIPAL
# =============================================================================

def ejecutar(args):
    """
    Ejecuta el bucle principal de simulación y control.

    Args:
        args: Argumentos parseados por argparse
    """
    print("=" * 75)
    print("  🚦 SISTEMA HÍBRIDO IoT — CONTROL ADAPTATIVO DE TRÁFICO")
    print("=" * 75)
    print(f"  Modo serial:  {'DESHABILITADO' if args.sin_serial else args.puerto}")
    print(f"  Modo gráfica: {'DESHABILITADO' if args.sin_grafica else 'HABILITADO'}")
    print(f"  Duración:     {args.duracion} pasos")
    print(f"  Velocidad:    {args.velocidad} seg/paso")
    print(f"  Hora simulada: 6:00 → 22:00")
    print("=" * 75)
    print()

    # --- Inicializar simulador ---
    simulador = InterseccionSimulada(capacidad=50, semilla=args.semilla)

    # --- Inicializar comunicación serial ---
    esp32 = None
    if not args.sin_serial:
        from comunicacion_serial import ComunicacionESP32
        esp32 = ComunicacionESP32(puerto=args.puerto, baudrate=args.baudrate)
        if not esp32.conectar():
            print("⚠️  No se pudo conectar al ESP32. Continuando sin serial...")
            esp32 = None

    # --- Inicializar visualizador ---
    viz = None
    if not args.sin_grafica:
        from visualizador import VisualizadorTrafico
        viz = VisualizadorTrafico(max_puntos=100)
        viz.iniciar()

    # --- Inicializar CSV ---
    ruta_csv = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "Datos",
        f"simulacion_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
    )
    inicializar_csv(ruta_csv)

    # --- Parámetros de simulación ---
    hora_inicio = 6.0
    hora_fin = 22.0
    incremento_hora = (hora_fin - hora_inicio) / args.duracion

    # Historial para resumen final
    historial_congestion = {"N": [], "S": [], "E": [], "O": []}
    historial_tiempos = []

    # Alternar fase de semáforo
    fase_actual = "NS"
    pasos_en_fase = 0

    # Encabezado de consola
    print(f"{'Paso':>6s} {'Hora':>5s} │ {'Norte':>10s} │ {'Sur':>10s} │ "
          f"{'Este':>10s} │ {'Oeste':>10s} │ {'Verde NS':>10s} {'Verde EO':>10s}")
    print("─" * 85)

    try:
        for paso in range(1, args.duracion + 1):
            inicio_paso = time.time()

            # 1. Avanzar hora simulada
            hora = hora_inicio + (paso - 1) * incremento_hora
            simulador.set_hora(hora)

            # 2. Simular tráfico (Poisson)
            congestion = simulador.paso(fase_verde=fase_actual)

            # 3. Control difuso → decidir tiempos de verde
            tiempos = calcular_tiempos(congestion)

            # 4. Alternar fase del semáforo cada 3 pasos (~6 seg por fase)
            pasos_en_fase += 1
            if pasos_en_fase >= 3:
                fase_actual = "EO" if fase_actual == "NS" else "NS"
                pasos_en_fase = 0

            # 5. Enviar tiempos al ESP32
            if esp32 is not None:
                esp32.enviar_tiempos(tiempos["verde_NS"], tiempos["verde_EO"])

            # 6. Actualizar gráfica
            if viz is not None:
                try:
                    viz.actualizar(congestion, hora)
                except Exception:
                    pass  # No interrumpir si hay error en la gráfica

            # 7. Guardar en CSV
            colas = simulador.obtener_colas()
            guardar_registro(ruta_csv, hora, congestion, tiempos, colas)

            # 8. Imprimir en consola
            imprimir_paso(paso, hora, congestion, tiempos, colas)

            # 9. Guardar en historial
            for d in ["N", "S", "E", "O"]:
                historial_congestion[d].append(congestion[d])
            historial_tiempos.append(tiempos)

            # 10. Esperar hasta completar el intervalo
            tiempo_transcurrido = time.time() - inicio_paso
            tiempo_espera = max(0, args.velocidad - tiempo_transcurrido)

            if viz is not None:
                import matplotlib.pyplot as plt
                plt.pause(tiempo_espera) if tiempo_espera > 0 else plt.pause(0.01)
            elif tiempo_espera > 0:
                time.sleep(tiempo_espera)

    except KeyboardInterrupt:
        print("\n\n⚠️  Simulación interrumpida por el usuario (Ctrl+C)")

    finally:
        # --- Resumen final ---
        imprimir_resumen(historial_congestion, historial_tiempos)

        print(f"\n  📄 Datos guardados en: {ruta_csv}")

        # Cerrar conexiones
        if esp32 is not None:
            esp32.desconectar()

        if viz is not None:
            print("\n  Cierra la ventana de la gráfica para salir...")
            try:
                import matplotlib.pyplot as plt
                viz.guardar(
                    os.path.join(
                        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "Datos",
                        "ultima_simulacion.png",
                    )
                )
                plt.ioff()
                plt.show()
            except Exception:
                pass

        print("\n✅ Simulación finalizada.")


# =============================================================================
# PUNTO DE ENTRADA
# =============================================================================

if __name__ == "__main__":
    parser = crear_parser()
    args = parser.parse_args()
    ejecutar(args)
