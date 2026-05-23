# -*- coding: utf-8 -*-
"""
comunicacion_serial.py — Comunicación serial con ESP32

Maneja la conexión serial con el ESP32 para enviar tiempos de verde
y recibir datos. Incluye manejo robusto de errores y reconexión automática.

Protocolo: Python envía "NS:{ms},EO:{ms}\n" → ESP32 parsea y actúa

Autor: Proyecto Sistema Híbrido IoT
"""

import sys
import time

# Forzar UTF-8 en consola de Windows
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

# Importación segura de pyserial
try:
    import serial
    import serial.tools.list_ports
    SERIAL_DISPONIBLE = True
except ImportError:
    SERIAL_DISPONIBLE = False
    print("⚠️  Módulo 'serial' no encontrado.")
    print("   Instálalo con: pip install pyserial")
    print("   La comunicación serial estará deshabilitada.")


# =============================================================================
# FUNCIONES INDEPENDIENTES
# =============================================================================

def listar_puertos():
    """
    Lista todos los puertos seriales disponibles en el sistema.

    Returns:
        Lista de tuplas (puerto, descripción, hwid)
    """
    if not SERIAL_DISPONIBLE:
        print("❌ pyserial no está instalado")
        return []

    puertos = serial.tools.list_ports.comports()
    return [(p.device, p.description, p.hwid) for p in puertos]


def conectar(puerto="COM3", baudrate=115200, timeout=1):
    """
    Abre una conexión serial con el ESP32.

    Args:
        puerto: Puerto serial (ej: "COM3", "/dev/ttyUSB0")
        baudrate: Velocidad de comunicación (default 115200)
        timeout: Tiempo de espera para lectura en segundos

    Returns:
        Objeto serial.Serial en caso de éxito, None en caso de error
    """
    if not SERIAL_DISPONIBLE:
        print("❌ No se puede conectar: pyserial no está instalado")
        return None

    try:
        ser = serial.Serial(
            port=puerto,
            baudrate=baudrate,
            timeout=timeout,
            write_timeout=timeout
        )
        # Esperar a que el ESP32 se reinicie (suele resetear al abrir puerto)
        time.sleep(2)
        # Limpiar el buffer
        ser.reset_input_buffer()
        ser.reset_output_buffer()

        print(f"✅ Conectado al ESP32 en {puerto} a {baudrate} baudios")
        return ser

    except serial.SerialException as e:
        if "PermissionError" in str(e) or "Access is denied" in str(e):
            print(f"❌ Error: Puerto {puerto} está ocupado por otro programa")
            print(f"   Cierra el Monitor Serial de Arduino IDE o cualquier otra aplicación")
        else:
            print(f"❌ Error de comunicación serial: {e}")
        return None

    except FileNotFoundError:
        print(f"❌ Error: Puerto {puerto} no encontrado")
        print(f"   ¿Está el ESP32 conectado? Revisa el cable USB")
        puertos = listar_puertos()
        if puertos:
            print(f"   Puertos disponibles:")
            for p, desc, _ in puertos:
                print(f"     → {p}: {desc}")
        else:
            print(f"   No se detectaron puertos seriales en el sistema")
        return None

    except Exception as e:
        print(f"❌ Error inesperado al conectar: {e}")
        return None


def enviar_tiempos(ser, verde_NS, verde_EO):
    """
    Envía los tiempos de verde al ESP32 en el formato esperado.

    Formato: "NS:{verde_NS},EO:{verde_EO}\n"
    Ejemplo: "NS:5000,EO:3000\n"

    Args:
        ser: Objeto serial.Serial activo
        verde_NS: Tiempo de verde para N-S en milisegundos
        verde_EO: Tiempo de verde para E-O en milisegundos

    Returns:
        True si el envío fue exitoso, False en caso de error
    """
    if ser is None or not ser.is_open:
        return False

    try:
        mensaje = f"NS:{verde_NS},EO:{verde_EO}\n"
        ser.write(mensaje.encode("utf-8"))
        ser.flush()
        return True

    except serial.SerialException as e:
        print(f"❌ Error al enviar datos: {e}")
        return False

    except Exception as e:
        print(f"❌ Error inesperado al enviar: {e}")
        return False


def leer_respuesta(ser, timeout=1):
    """
    Lee una línea de respuesta del ESP32.

    Args:
        ser: Objeto serial.Serial activo
        timeout: Tiempo máximo de espera en segundos

    Returns:
        String con la respuesta del ESP32, o cadena vacía si no hay respuesta
    """
    if ser is None or not ser.is_open:
        return ""

    try:
        # Guardar timeout original y establecer el solicitado
        timeout_original = ser.timeout
        ser.timeout = timeout

        linea = ser.readline()
        ser.timeout = timeout_original

        if linea:
            return linea.decode("utf-8", errors="replace").strip()
        return ""

    except serial.SerialException as e:
        print(f"❌ Error al leer datos: {e}")
        return ""

    except Exception as e:
        print(f"❌ Error inesperado al leer: {e}")
        return ""


def desconectar(ser):
    """
    Cierra la conexión serial de forma segura.

    Args:
        ser: Objeto serial.Serial a cerrar
    """
    if ser is not None:
        try:
            if ser.is_open:
                ser.close()
                print("🔌 Conexión serial cerrada correctamente")
        except Exception as e:
            print(f"⚠️  Error al cerrar conexión: {e}")


# =============================================================================
# CLASE WRAPPER CON GESTIÓN DE ESTADO
# =============================================================================

class ComunicacionESP32:
    """
    Clase que encapsula toda la comunicación con el ESP32.
    Incluye gestión de estado, reconexión automática y context manager.

    Uso básico:
        with ComunicacionESP32(puerto="COM3") as esp:
            esp.enviar_tiempos(5000, 3000)

    Uso sin context manager:
        esp = ComunicacionESP32(puerto="COM3")
        esp.conectar()
        esp.enviar_tiempos(5000, 3000)
        esp.desconectar()
    """

    def __init__(self, puerto="COM3", baudrate=115200, timeout=1,
                 intentos_reconexion=3):
        """
        Args:
            puerto: Puerto serial del ESP32
            baudrate: Velocidad de comunicación
            timeout: Timeout de lectura/escritura en segundos
            intentos_reconexion: Número de intentos de reconexión automática
        """
        self.puerto = puerto
        self.baudrate = baudrate
        self.timeout = timeout
        self.intentos_reconexion = intentos_reconexion
        self._ser = None
        self._errores_consecutivos = 0

    @property
    def conectado(self):
        """Indica si la conexión serial está activa."""
        return self._ser is not None and self._ser.is_open

    def conectar(self):
        """
        Establece la conexión serial con el ESP32.

        Returns:
            True si la conexión fue exitosa
        """
        self._ser = conectar(self.puerto, self.baudrate, self.timeout)
        return self.conectado

    def desconectar(self):
        """Cierra la conexión serial."""
        desconectar(self._ser)
        self._ser = None
        self._errores_consecutivos = 0

    def _intentar_reconexion(self):
        """
        Intenta reconectar al ESP32 después de un error.

        Returns:
            True si la reconexión fue exitosa
        """
        print(f"🔄 Intentando reconexión al ESP32 ({self.puerto})...")

        for intento in range(1, self.intentos_reconexion + 1):
            print(f"   Intento {intento}/{self.intentos_reconexion}...")
            self.desconectar()
            time.sleep(2)  # Esperar antes de reconectar

            if self.conectar():
                print("✅ Reconexión exitosa")
                self._errores_consecutivos = 0
                return True

        print("❌ No se pudo reconectar al ESP32")
        return False

    def enviar_tiempos(self, verde_NS, verde_EO):
        """
        Envía tiempos de verde al ESP32 con reconexión automática.

        Args:
            verde_NS: Tiempo de verde N-S en milisegundos
            verde_EO: Tiempo de verde E-O en milisegundos

        Returns:
            True si el envío fue exitoso
        """
        if not self.conectado:
            if not self._intentar_reconexion():
                return False

        exito = enviar_tiempos(self._ser, verde_NS, verde_EO)

        if not exito:
            self._errores_consecutivos += 1
            if self._errores_consecutivos >= 3:
                print("⚠️  Múltiples errores consecutivos, intentando reconexión...")
                self._intentar_reconexion()
        else:
            self._errores_consecutivos = 0

        return exito

    def leer_respuesta(self, timeout=1):
        """
        Lee una respuesta del ESP32.

        Returns:
            String con la respuesta o cadena vacía
        """
        if not self.conectado:
            return ""
        return leer_respuesta(self._ser, timeout)

    # --- Context Manager ---
    def __enter__(self):
        self.conectar()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.desconectar()
        return False  # No suprimir excepciones

    def __repr__(self):
        estado = "conectado" if self.conectado else "desconectado"
        return f"ComunicacionESP32({self.puerto}, {estado})"


# =============================================================================
# PRUEBA DE COMUNICACIÓN (sin ESP32 conectado)
# =============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("  🔌 PRUEBA DE COMUNICACIÓN SERIAL")
    print("=" * 70)

    if not SERIAL_DISPONIBLE:
        print("\n❌ pyserial no está instalado. Ejecuta:")
        print("   pip install pyserial")
        print("\nSaliendo...")
        exit(1)

    # Listar puertos disponibles
    print("\n📡 Puertos seriales disponibles:")
    puertos = listar_puertos()
    if puertos:
        for puerto, desc, hwid in puertos:
            print(f"   → {puerto}: {desc}")
    else:
        print("   (ninguno detectado)")

    # Intentar conectar (probablemente fallará sin ESP32)
    print("\n🔄 Intentando conectar al ESP32...")
    esp = ComunicacionESP32(puerto="COM3", intentos_reconexion=1)

    if esp.conectar():
        print(f"\n✅ Conectado: {esp}")

        # Probar envío
        print("\n📤 Enviando tiempos de prueba: NS=5000ms, EO=3000ms")
        if esp.enviar_tiempos(5000, 3000):
            print("   ✅ Envío exitoso")

            # Leer respuesta
            respuesta = esp.leer_respuesta(timeout=2)
            if respuesta:
                print(f"   📥 Respuesta del ESP32: {respuesta}")
            else:
                print("   ⏳ Sin respuesta del ESP32 (timeout)")

        esp.desconectar()
    else:
        print(f"\n⚠️  No se pudo conectar (esto es normal si el ESP32 no está conectado)")
        print("   El sistema funcionará en modo simulación")

    # Demostrar el context manager
    print("\n📋 Demostración del context manager:")
    print('   with ComunicacionESP32("COM3") as esp:')
    print('       esp.enviar_tiempos(5000, 3000)')
    print("   # Se desconecta automáticamente al salir del bloque")

    print("\n✅ Módulo de comunicación serial verificado.")
