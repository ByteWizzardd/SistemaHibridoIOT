# -*- coding: utf-8 -*-
"""
control_adaptativo.py — Control difuso para semáforos adaptativos

Implementa lógica difusa desde cero (sin librerías externas):
- 3 funciones de membresía: baja, media, alta
- 7 reglas difusas para asignación de tiempo de verde
- Defuzzificación por promedio ponderado (centroide discreto)

Entrada:  congestión por dirección {"N": %, "S": %, "E": %, "O": %}
Salida:   tiempos de verde {"verde_NS": ms, "verde_EO": ms}

Autor: Proyecto Sistema Híbrido IoT
"""

import sys
import numpy as np

# Forzar UTF-8 en consola de Windows
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass


# =============================================================================
# FUNCIONES DE MEMBRESÍA
# =============================================================================

def baja(x):
    """
    Función de membresía trapezoidal para congestión BAJA.
    Máxima (1.0) cuando x <= 15, decrece linealmente hasta 0 en x = 40.

    Args:
        x: Valor de congestión (0-100%)

    Returns:
        Grado de pertenencia (0.0 - 1.0)
    """
    if x <= 15:
        return 1.0
    elif x <= 40:
        return (40 - x) / 25.0
    else:
        return 0.0


def media(x):
    """
    Función de membresía triangular para congestión MEDIA.
    Crece de 0 en x=20 hasta 1.0 en x=50, decrece hasta 0 en x=80.

    Args:
        x: Valor de congestión (0-100%)

    Returns:
        Grado de pertenencia (0.0 - 1.0)
    """
    if x <= 20:
        return 0.0
    elif x <= 50:
        return (x - 20) / 30.0
    elif x <= 80:
        return (80 - x) / 30.0
    else:
        return 0.0


def alta(x):
    """
    Función de membresía trapezoidal para congestión ALTA.
    Crece de 0 en x=60 hasta 1.0 en x=85, se mantiene en 1.0 hasta 100.

    Args:
        x: Valor de congestión (0-100%)

    Returns:
        Grado de pertenencia (0.0 - 1.0)
    """
    if x <= 60:
        return 0.0
    elif x <= 85:
        return (x - 60) / 25.0
    else:
        return 1.0


# =============================================================================
# VALORES CONSECUENTES (tiempos de verde en milisegundos)
# =============================================================================

# Tiempos de verde predefinidos para las salidas difusas
VERDE_CORTO = 3000    # 3 segundos — mínimo
VERDE_MEDIO = 5500    # 5.5 segundos — equilibrado
VERDE_LARGO = 8500    # 8.5 segundos — prioridad
VERDE_MAX = 10000     # 10 segundos — máxima prioridad


# =============================================================================
# REGLAS DIFUSAS (7 reglas)
# =============================================================================

def evaluar_reglas(cong_ns, cong_eo):
    """
    Evalúa las 7 reglas difusas y retorna los pesos y consecuentes
    para cada eje (NS y EO).

    Las reglas usan el operador AND (mínimo) para combinar antecedentes.

    Args:
        cong_ns: Congestión del eje Norte-Sur (0-100%)
        cong_eo: Congestión del eje Este-Oeste (0-100%)

    Returns:
        Tupla (reglas_ns, reglas_eo) donde cada una es lista de
        tuplas (peso, tiempo_verde) para defuzzificación
    """
    # Evaluar grados de membresía para cada eje
    ns_baja = baja(cong_ns)
    ns_media = media(cong_ns)
    ns_alta = alta(cong_ns)

    eo_baja = baja(cong_eo)
    eo_media = media(cong_eo)
    eo_alta = alta(cong_eo)

    # -------------------------------------------------------------------
    # Regla 1: Si NS es ALTA y EO es BAJA → NS largo, EO corto
    #   "Corredor N-S congestionado, E-O libre: priorizar N-S"
    # -------------------------------------------------------------------
    w1 = min(ns_alta, eo_baja)

    # -------------------------------------------------------------------
    # Regla 2: Si NS es BAJA y EO es ALTA → NS corto, EO largo
    #   "Corredor E-O congestionado, N-S libre: priorizar E-O"
    # -------------------------------------------------------------------
    w2 = min(ns_baja, eo_alta)

    # -------------------------------------------------------------------
    # Regla 3: Si NS es MEDIA y EO es MEDIA → tiempos iguales medios
    #   "Tráfico moderado en ambos: reparto equilibrado"
    # -------------------------------------------------------------------
    w3 = min(ns_media, eo_media)

    # -------------------------------------------------------------------
    # Regla 4: Si NS es ALTA y EO es ALTA → favor al más congestionado
    #   "Ambos congestionados: dar ligeramente más al peor"
    # -------------------------------------------------------------------
    w4 = min(ns_alta, eo_alta)

    # -------------------------------------------------------------------
    # Regla 5: Si NS es ALTA y EO es MEDIA → NS largo, EO medio
    #   "N-S mucho peor: priorizar pero no ignorar E-O"
    # -------------------------------------------------------------------
    w5 = min(ns_alta, eo_media)

    # -------------------------------------------------------------------
    # Regla 6: Si NS es MEDIA y EO es ALTA → NS medio, EO largo
    #   "E-O mucho peor: priorizar pero no ignorar N-S"
    # -------------------------------------------------------------------
    w6 = min(ns_media, eo_alta)

    # -------------------------------------------------------------------
    # Regla 7: Si NS es BAJA y EO es BAJA → tiempos mínimos iguales
    #   "Poco tráfico: ciclo corto para ambos"
    # -------------------------------------------------------------------
    w7 = min(ns_baja, eo_baja)

    # Construir listas de (peso, consecuente) para cada eje
    reglas_ns = [
        (w1, VERDE_LARGO),    # R1: NS largo
        (w2, VERDE_CORTO),    # R2: NS corto
        (w3, VERDE_MEDIO),    # R3: NS medio
        (w4, VERDE_LARGO if cong_ns >= cong_eo else VERDE_MEDIO),  # R4: dinámico
        (w5, VERDE_LARGO),    # R5: NS largo
        (w6, VERDE_MEDIO),    # R6: NS medio
        (w7, VERDE_CORTO),    # R7: NS corto (poco tráfico)
    ]

    reglas_eo = [
        (w1, VERDE_CORTO),    # R1: EO corto
        (w2, VERDE_LARGO),    # R2: EO largo
        (w3, VERDE_MEDIO),    # R3: EO medio
        (w4, VERDE_LARGO if cong_eo >= cong_ns else VERDE_MEDIO),  # R4: dinámico
        (w5, VERDE_MEDIO),    # R5: EO medio
        (w6, VERDE_LARGO),    # R6: EO largo
        (w7, VERDE_CORTO),    # R7: EO corto (poco tráfico)
    ]

    return reglas_ns, reglas_eo


# =============================================================================
# DEFUZZIFICACIÓN
# =============================================================================

def defuzzificar(reglas):
    """
    Defuzzificación por promedio ponderado (centroide discreto).

    Calcula: resultado = Σ(peso_i × valor_i) / Σ(peso_i)

    Si todos los pesos son 0, retorna el valor medio por defecto.

    Args:
        reglas: Lista de tuplas (peso, valor_consecuente)

    Returns:
        Valor defuzzificado (float)
    """
    suma_ponderada = sum(w * v for w, v in reglas)
    suma_pesos = sum(w for w, _ in reglas)

    if suma_pesos < 1e-6:
        # Si no se activó ninguna regla, usar valor por defecto
        return VERDE_MEDIO

    return suma_ponderada / suma_pesos


# =============================================================================
# FUNCIÓN PRINCIPAL DE CONTROL
# =============================================================================

def calcular_tiempos(congestion):
    """
    Calcula los tiempos de verde para cada eje usando lógica difusa.

    El proceso es:
    1. Combinar congestión N+S y E+O (usar el máximo del par)
    2. Evaluar las 7 reglas difusas
    3. Defuzzificar para obtener tiempos de verde
    4. Aplicar restricciones (mínimos, máximos, ciclo total)

    Args:
        congestion: dict {"N": float, "S": float, "E": float, "O": float}
                    Valores de congestión en porcentaje (0-100)

    Returns:
        dict {"verde_NS": int, "verde_EO": int}
        Tiempos de verde en milisegundos (3000 - 10000 ms)
    """
    # Combinar congestión por eje (tomar el máximo del par)
    cong_ns = max(congestion.get("N", 0), congestion.get("S", 0))
    cong_eo = max(congestion.get("E", 0), congestion.get("O", 0))

    # Asegurar que los valores estén en rango
    cong_ns = np.clip(cong_ns, 0, 100)
    cong_eo = np.clip(cong_eo, 0, 100)

    # Evaluar reglas difusas
    reglas_ns, reglas_eo = evaluar_reglas(cong_ns, cong_eo)

    # Defuzzificar
    verde_ns = defuzzificar(reglas_ns)
    verde_eo = defuzzificar(reglas_eo)

    # Aplicar restricciones de tiempo
    verde_ns = int(np.clip(verde_ns, VERDE_CORTO, VERDE_MAX))
    verde_eo = int(np.clip(verde_eo, VERDE_CORTO, VERDE_MAX))

    # Asegurar que el ciclo total no exceda ~20 segundos
    CICLO_MAX = 20000
    ciclo_total = verde_ns + verde_eo
    if ciclo_total > CICLO_MAX:
        # Escalar proporcionalmente
        factor = CICLO_MAX / ciclo_total
        verde_ns = int(verde_ns * factor)
        verde_eo = int(verde_eo * factor)

    return {"verde_NS": verde_ns, "verde_EO": verde_eo}


def imprimir_membresias(valor, etiqueta=""):
    """
    Función auxiliar para depuración: imprime los grados de membresía
    de un valor de congestión.
    """
    print(
        f"  {etiqueta} Congestión={valor:5.1f}% → "
        f"Baja={baja(valor):.2f} | "
        f"Media={media(valor):.2f} | "
        f"Alta={alta(valor):.2f}"
    )


# =============================================================================
# PRUEBA DEL CONTROL ADAPTATIVO (sin conexión al ESP32)
# =============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("  🧠 PRUEBA DEL CONTROL ADAPTATIVO (Lógica Difusa)")
    print("=" * 70)

    # ---- Caso 1: Norte muy congestionado ----
    print("\n📋 Caso 1: Norte congestionado, Sur libre")
    caso1 = {"N": 85, "S": 20, "E": 45, "O": 50}
    print(f"  Entrada: {caso1}")
    imprimir_membresias(max(caso1["N"], caso1["S"]), "NS:")
    imprimir_membresias(max(caso1["E"], caso1["O"]), "EO:")
    resultado1 = calcular_tiempos(caso1)
    print(f"  Resultado: verde_NS={resultado1['verde_NS']}ms, verde_EO={resultado1['verde_EO']}ms")
    assert resultado1["verde_NS"] > resultado1["verde_EO"], \
        "❌ ERROR: NS debería tener más verde que EO"
    print("  ✅ Correcto: N-S recibe más tiempo de verde")

    # ---- Caso 2: Todo equilibrado ----
    print("\n📋 Caso 2: Congestión equilibrada")
    caso2 = {"N": 50, "S": 50, "E": 50, "O": 50}
    print(f"  Entrada: {caso2}")
    imprimir_membresias(50, "NS:")
    imprimir_membresias(50, "EO:")
    resultado2 = calcular_tiempos(caso2)
    print(f"  Resultado: verde_NS={resultado2['verde_NS']}ms, verde_EO={resultado2['verde_EO']}ms")
    diferencia = abs(resultado2["verde_NS"] - resultado2["verde_EO"])
    assert diferencia < 500, \
        f"❌ ERROR: Tiempos deberían ser casi iguales (diferencia={diferencia}ms)"
    print(f"  ✅ Correcto: Tiempos casi iguales (diferencia={diferencia}ms)")

    # ---- Caso 3: Todo bajo ----
    print("\n📋 Caso 3: Poco tráfico en todas las direcciones")
    caso3 = {"N": 10, "S": 5, "E": 8, "O": 12}
    print(f"  Entrada: {caso3}")
    resultado3 = calcular_tiempos(caso3)
    print(f"  Resultado: verde_NS={resultado3['verde_NS']}ms, verde_EO={resultado3['verde_EO']}ms")
    print(f"  ✅ Ciclo corto: {resultado3['verde_NS'] + resultado3['verde_EO']}ms total")

    # ---- Caso 4: Todo alto ----
    print("\n📋 Caso 4: Alta congestión en todas las direcciones")
    caso4 = {"N": 90, "S": 85, "E": 88, "O": 92}
    print(f"  Entrada: {caso4}")
    resultado4 = calcular_tiempos(caso4)
    print(f"  Resultado: verde_NS={resultado4['verde_NS']}ms, verde_EO={resultado4['verde_EO']}ms")
    print(f"  ✅ Ciclo largo: {resultado4['verde_NS'] + resultado4['verde_EO']}ms total")

    # ---- Caso 5: E-O congestionado, N-S libre ----
    print("\n📋 Caso 5: Este-Oeste congestionado, Norte-Sur libre")
    caso5 = {"N": 10, "S": 15, "E": 90, "O": 80}
    print(f"  Entrada: {caso5}")
    resultado5 = calcular_tiempos(caso5)
    print(f"  Resultado: verde_NS={resultado5['verde_NS']}ms, verde_EO={resultado5['verde_EO']}ms")
    assert resultado5["verde_EO"] > resultado5["verde_NS"], \
        "❌ ERROR: EO debería tener más verde que NS"
    print("  ✅ Correcto: E-O recibe más tiempo de verde")

    # ---- Resumen ----
    print("\n" + "=" * 70)
    print("  📊 TABLA RESUMEN")
    print("=" * 70)
    print(f"  {'Caso':<30s} {'NS (ms)':>8s} {'EO (ms)':>8s} {'Total':>8s}")
    print("  " + "-" * 56)

    casos = [
        ("N congestionado", resultado1),
        ("Equilibrado", resultado2),
        ("Poco tráfico", resultado3),
        ("Todo congestionado", resultado4),
        ("EO congestionado", resultado5),
    ]
    for nombre, r in casos:
        total = r["verde_NS"] + r["verde_EO"]
        print(f"  {nombre:<30s} {r['verde_NS']:>8d} {r['verde_EO']:>8d} {total:>8d}")

    print()
    print("✅ Todas las pruebas del control adaptativo pasaron correctamente.")
