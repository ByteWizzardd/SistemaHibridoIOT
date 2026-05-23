/**
 * 🚦 Sistema Híbrido IoT — Control de Tráfico Adaptativo
 * 
 * Este sketch de Arduino está diseñado para un ESP32. Controla una intersección
 * de 4 esquinas con 12 LEDs (Rojo, Amarillo, Verde por dirección), una pantalla
 * OLED SSD1306, un zumbador pasivo para advertencia de peatones, un micro servo
 * para simular la barrera peatonal, y un pulsador peatonal.
 * 
 * Características:
 *  - Máquina de estados de 4 fases + Fase Peatonal + Fase de Emergencia.
 *  - Transición segura a Fase Peatonal pasando por Amarillo.
 *  - Parser Serial robusto para tiempos dinámicos ("NS:5000,EO:3000\n").
 *  - Comando de pánico serial ("EMERGENCIA") para activar bloqueo vial total.
 *  - Interfaz OLED avanzada con gráficos y barra de progreso.
 * 
 * Conexión de Pines:
 *  - OLED I2C: SDA ➔ GPIO 21, SCL ➔ GPIO 22
 *  - Servo: Señal ➔ GPIO 23
 *  - Buzzer: Señal ➔ GPIO 4
 *  - Botón Peatonal: Señal ➔ GPIO 2 (Pull-up interno)
 *  - Semáforos (12 LEDs):
 *     - NORTE: Rojo ➔ 15, Amarillo ➔ 18, Verde ➔ 19
 *     - SUR:   Rojo ➔ 5,  Amarillo ➔ 17, Verde ➔ 16
 *     - ESTE:  Rojo ➔ 32, Amarillo ➔ 33, Verde ➔ 25
 *     - OESTE: Rojo ➔ 26, Amarillo ➔ 27, Verde ➔ 14
 * 
 * Autor: Proyecto Sistema Híbrido IoT
 */

#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <ESP32Servo.h>

// =============================================================================
// CONFIGURACIÓN DE PINES
// =============================================================================

// OLED
#define ANCHO_PANTALLA 128
#define ALTO_PANTALLA  64
#define OLED_RESET     -1
Adafruit_SSD1306 display(ANCHO_PANTALLA, ALTO_PANTALLA, &Wire, OLED_RESET);

// Actuadores y Sensores Peatonales
#define PIN_SERVO   23
#define PIN_BUZZER  4
#define PIN_BOTON   2

// Semáforo Norte (N)
#define PIN_N_ROJO  15
#define PIN_N_AMAR  18
#define PIN_N_VERD  19

// Semáforo Sur (S)
#define PIN_S_ROJO  5
#define PIN_S_AMAR  17
#define PIN_S_VERD  16

// Semáforo Este (E)
#define PIN_E_ROJO  32
#define PIN_E_AMAR  33
#define PIN_E_VERD  25

// Semáforo Oeste (O)
#define PIN_O_ROJO  26
#define PIN_O_AMAR  27
#define PIN_O_VERD  14

// Servo
Servo barreraServo;

// =============================================================================
// ESTADOS Y VARIABLES DE TIEMPO
// =============================================================================

enum EstadoSemaforo {
  FASE_NS_VERDE,      // Fase 0: N-S Verde, E-O Rojo
  FASE_NS_AMARILLO,   // Fase 1: N-S Amarillo, E-O Rojo
  FASE_EO_VERDE,      // Fase 2: N-S Rojo, E-O Verde
  FASE_EO_AMARILLO,   // Fase 3: N-S Rojo, E-O Amarillo
  FASE_PEATONAL,      // Fase Extra: Todo Rojo Peatón cruza
  FASE_EMERGENCIA     // Fase Extra: Todo Rojo Parpadeo Alarma
};

EstadoSemaforo estadoActual = FASE_NS_VERDE;
EstadoSemaforo estadoPrevio = FASE_NS_VERDE; // Para retornar de emergencia

// Tiempos por defecto (en milisegundos)
unsigned long tiempo_Verde_NS = 8000;
unsigned long tiempo_Verde_EO = 8000;
const unsigned long tiempo_Amarillo = 2000;
const unsigned long tiempo_Peatonal = 5000;
const unsigned long tiempo_Emergencia = 10000; // Auto-recuperación si no hay 'NORMAL'

// Control del flujo del tiempo
unsigned long tiempoUltimoCambio = 0;
unsigned long duracionEstadoActual = 0;
unsigned long tiempoEmergenciaIniciado = 0;

// Variables Peatonales
volatile bool peatonSolicitado = false;
unsigned long ultimoDebounceBoton = 0;
const unsigned long tiempoDebounce = 250; // ms

// Variables del Zumbador
unsigned long tiempoUltimoBip = 0;
bool estadoBuzzer = false;

// Variables Serial
String bufferSerial = "";

// =============================================================================
// DETECCIÓN E INTERRUPCIONES Peatonales
// =============================================================================

void IRAM_ATTR botonPeatonalISR() {
  unsigned long tiempoActual = millis();
  if (tiempoActual - ultimoDebounceBoton > tiempoDebounce) {
    peatonSolicitado = true;
    ultimoDebounceBoton = tiempoActual;
  }
}

// =============================================================================
// INICIALIZACIÓN
// =============================================================================

void setup() {
  // Puerto Serial
  Serial.begin(115200);
  Serial.println("\n==================================================");
  Serial.println("🚦 ESP32: CONTROLADOR DE TRÁFICO INICIADO");
  Serial.println("==================================================");

  // Configurar Pines de LEDs como Salidas
  pinMode(PIN_N_ROJO, OUTPUT);  pinMode(PIN_N_AMAR, OUTPUT);  pinMode(PIN_N_VERD, OUTPUT);
  pinMode(PIN_S_ROJO, OUTPUT);  pinMode(PIN_S_AMAR, OUTPUT);  pinMode(PIN_S_VERD, OUTPUT);
  pinMode(PIN_E_ROJO, OUTPUT);  pinMode(PIN_E_AMAR, OUTPUT);  pinMode(PIN_E_VERD, OUTPUT);
  pinMode(PIN_O_ROJO, OUTPUT);  pinMode(PIN_O_AMAR, OUTPUT);  pinMode(PIN_O_VERD, OUTPUT);

  // Configurar Buzzer y Botón
  pinMode(PIN_BUZZER, OUTPUT);
  pinMode(PIN_BOTON, INPUT_PULLUP);
  
  // Registrar Interrupción de Hardware para el Botón Peatonal (Flanco de Bajada)
  attachInterrupt(digitalPinToInterrupt(PIN_BOTON), botonPeatonalISR, FALLING);

  // Inicializar Servo
  barreraServo.attach(PIN_SERVO, 500, 2400); // Rango SG90 estándar
  barreraServo.write(0); // Barrera cerrada

  // Inicializar OLED Display
  // Dirección I2C común en Wokwi/Placas físicas es 0x3C o 0x3D
  if(!display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {
    Serial.println("❌ Error: No se detectó pantalla OLED SSD1306");
  } else {
    display.clearDisplay();
    display.setTextColor(SSD1306_WHITE);
    display.setTextSize(1);
    display.setCursor(10, 20);
    display.println("SISTEMA HIBRIDO IOT");
    display.setCursor(10, 35);
    display.println("Iniciando semaforos...");
    display.display();
    delay(1000);
  }

  // Establecer estado inicial
  actualizarSalidasFase();
  tiempoUltimoCambio = millis();
}

// =============================================================================
// BUCLE PRINCIPAL (MÁQUINA DE ESTADOS)
// =============================================================================

void loop() {
  // 1. Escuchar y procesar comandos Serial
  procesarSerial();

  // 2. Controlar la Máquina de Estados
  unsigned long tiempoActual = millis();
  unsigned long tiempoTranscurrido = tiempoActual - tiempoUltimoCambio;
  
  // Determinar la duración requerida de la fase actual
  switch (estadoActual) {
    case FASE_NS_VERDE:
      duracionEstadoActual = tiempo_Verde_NS;
      break;
    case FASE_NS_AMARILLO:
      duracionEstadoActual = tiempo_Amarillo;
      break;
    case FASE_EO_VERDE:
      duracionEstadoActual = tiempo_Verde_EO;
      break;
    case FASE_EO_AMARILLO:
      duracionEstadoActual = tiempo_Amarillo;
      break;
    case FASE_PEATONAL:
      duracionEstadoActual = tiempo_Peatonal;
      break;
    case FASE_EMERGENCIA:
      duracionEstadoActual = tiempo_Emergencia;
      break;
  }

  // 3. Manejar interrupciones o cambios de estado
  if (estadoActual == FASE_EMERGENCIA) {
    // Modo de emergencia: parpadea
    manejarParpadeoEmergencia();
    // Auto-recuperación después de tiempoEmergencia si no se recibe NORMAL
    if (tiempoActual - tiempoEmergenciaIniciado >= tiempo_Emergencia) {
      Serial.println("[INFO] Tiempo de emergencia agotado. Retornando a ciclo normal.");
      estadoActual = FASE_NS_VERDE;
      tiempoUltimoCambio = millis();
      actualizarSalidasFase();
      barreraServo.write(0);
      digitalWrite(PIN_BUZZER, LOW);
    }
  } 
  else if (estadoActual == FASE_PEATONAL) {
    // Fase peatonal activa: sonar buzzer intermitente y barrera abierta (90 grados)
    barreraServo.write(90);
    manejarSonidoPeatonal();

    if (tiempoTranscurrido >= duracionEstadoActual) {
      // Finalizar cruce peatonal
      barreraServo.write(0); // Cerrar barrera
      digitalWrite(PIN_BUZZER, LOW);
      peatonSolicitado = false; // Reset solicitud
      
      // Regresa a Fase 0 (N-S Verde)
      estadoActual = FASE_NS_VERDE;
      tiempoUltimoCambio = millis();
      actualizarSalidasFase();
      Serial.println("[FASE] Fin Peatonal. Retornando a FASE 0: NS Verde.");
    }
  } 
  else {
    // Ciclo normal
    // Si hay una solicitud peatonal activa, interrumpimos el verde de forma segura
    if (peatonSolicitado) {
      if (estadoActual == FASE_NS_VERDE) {
        Serial.println("[INTERRUPCIÓN] Peatón solicita cruce. Cambiando N-S a Amarillo para transición segura.");
        estadoActual = FASE_NS_AMARILLO;
        tiempoUltimoCambio = millis();
        actualizarSalidasFase();
      } 
      else if (estadoActual == FASE_EO_VERDE) {
        Serial.println("[INTERRUPCIÓN] Peatón solicita cruce. Cambiando E-O a Amarillo para transición segura.");
        estadoActual = FASE_EO_AMARILLO;
        tiempoUltimoCambio = millis();
        actualizarSalidasFase();
      } 
      else if (estadoActual == FASE_NS_AMARILLO && tiempoTranscurrido >= duracionEstadoActual) {
        // Estaba en transición, entra a peatonal
        entrarAFasePeatonal();
      } 
      else if (estadoActual == FASE_EO_AMARILLO && tiempoTranscurrido >= duracionEstadoActual) {
        // Estaba en transición, entra a peatonal
        entrarAFasePeatonal();
      }
    }

    // Transición ordinaria por tiempo
    if (!peatonSolicitado && tiempoTranscurrido >= duracionEstadoActual) {
      cambiarFaseSiguiente();
    }
  }

  // 4. Actualizar pantalla OLED
  actualizarOLED(tiempoTranscurrido);

  // Pequeño retardo de ciclo
  delay(50);
}

// =============================================================================
// TRANSICIÓN DE FASES Y CONTROL DE SALIDAS
// =============================================================================

void cambiarFaseSiguiente() {
  switch (estadoActual) {
    case FASE_NS_VERDE:
      estadoActual = FASE_NS_AMARILLO;
      break;
    case FASE_NS_AMARILLO:
      estadoActual = FASE_EO_VERDE;
      break;
    case FASE_EO_VERDE:
      estadoActual = FASE_EO_AMARILLO;
      break;
    case FASE_EO_AMARILLO:
      estadoActual = FASE_NS_VERDE;
      break;
    default:
      estadoActual = FASE_NS_VERDE;
      break;
  }
  tiempoUltimoCambio = millis();
  actualizarSalidasFase();
  
  // Depuración por serial
  Serial.print("[FASE] Transición a Fase ");
  Serial.print(estadoActual);
  Serial.print(" | Tiempos configurados -> Verde NS: ");
  Serial.print(tiempo_Verde_NS);
  Serial.print("ms, Verde EO: ");
  Serial.print(tiempo_Verde_EO);
  Serial.println("ms");
}

void entrarAFasePeatonal() {
  estadoActual = FASE_PEATONAL;
  tiempoUltimoCambio = millis();
  actualizarSalidasFase();
  Serial.println("[FASE] >>> Iniciando FASE PEATONAL (Todo Rojo + Cruce Habilitado) <<<");
}

void activarModoEmergencia() {
  if (estadoActual != FASE_EMERGENCIA) {
    estadoPrevio = estadoActual;
    estadoActual = FASE_EMERGENCIA;
    tiempoEmergenciaIniciado = millis();
    tiempoUltimoCambio = millis();
    actualizarSalidasFase();
    Serial.println("[⚠️ ALERTA] >>> MODO DE EMERGENCIA SERIAL ACTIVADO <<<");
  }
}

void desactivarModoEmergencia() {
  if (estadoActual == FASE_EMERGENCIA) {
    estadoActual = estadoPrevio;
    tiempoUltimoCambio = millis();
    actualizarSalidasFase();
    barreraServo.write(0); // Cerrar barrera por si acaso
    digitalWrite(PIN_BUZZER, LOW);
    Serial.println("[INFO] Modo de emergencia desactivado. Reanudando ciclo.");
  }
}

/**
 * Controla físicamente los 12 LEDs según la fase activa del semáforo.
 */
void actualizarSalidasFase() {
  // Apagar todos los LEDs primero
  apagarTodosLosLeds();

  switch (estadoActual) {
    case FASE_NS_VERDE:
      // N-S Verde, E-O Rojo
      digitalWrite(PIN_N_VERD, HIGH);
      digitalWrite(PIN_S_VERD, HIGH);
      digitalWrite(PIN_E_ROJO, HIGH);
      digitalWrite(PIN_O_ROJO, HIGH);
      break;

    case FASE_NS_AMARILLO:
      // N-S Amarillo, E-O Rojo
      digitalWrite(PIN_N_AMAR, HIGH);
      digitalWrite(PIN_S_AMAR, HIGH);
      digitalWrite(PIN_E_ROJO, HIGH);
      digitalWrite(PIN_O_ROJO, HIGH);
      break;

    case FASE_EO_VERDE:
      // N-S Rojo, E-O Verde
      digitalWrite(PIN_N_ROJO, HIGH);
      digitalWrite(PIN_S_ROJO, HIGH);
      digitalWrite(PIN_E_VERD, HIGH);
      digitalWrite(PIN_O_VERD, HIGH);
      break;

    case FASE_EO_AMARILLO:
      // N-S Rojo, E-O Amarillo
      digitalWrite(PIN_N_ROJO, HIGH);
      digitalWrite(PIN_S_ROJO, HIGH);
      digitalWrite(PIN_E_AMAR, HIGH);
      digitalWrite(PIN_O_AMAR, HIGH);
      break;

    case FASE_PEATONAL:
      // Todo Rojo para vehículos
      digitalWrite(PIN_N_ROJO, HIGH);
      digitalWrite(PIN_S_ROJO, HIGH);
      digitalWrite(PIN_E_ROJO, HIGH);
      digitalWrite(PIN_O_ROJO, HIGH);
      break;

    case FASE_EMERGENCIA:
      // En modo de emergencia se controlará de manera intermitente en loop
      break;
  }
}

void apagarTodosLosLeds() {
  digitalWrite(PIN_N_ROJO, LOW); digitalWrite(PIN_N_AMAR, LOW); digitalWrite(PIN_N_VERD, LOW);
  digitalWrite(PIN_S_ROJO, LOW); digitalWrite(PIN_S_AMAR, LOW); digitalWrite(PIN_S_VERD, LOW);
  digitalWrite(PIN_E_ROJO, LOW); digitalWrite(PIN_E_AMAR, LOW); digitalWrite(PIN_E_VERD, LOW);
  digitalWrite(PIN_O_ROJO, LOW); digitalWrite(PIN_O_AMAR, LOW); digitalWrite(PIN_O_VERD, LOW);
}

// =============================================================================
// EFECTOS AUXILIARES: ZUMBADOR Y DESTELLOS
// =============================================================================

void manejarSonidoPeatonal() {
  unsigned long tiempoActual = millis();
  // Bip cada 500ms
  if (tiempoActual - tiempoUltimoBip >= 500) {
    tiempoUltimoBip = tiempoActual;
    estadoBuzzer = !estadoBuzzer;
    if (estadoBuzzer) {
      tone(PIN_BUZZER, 1000, 150); // Sonido a 1kHz por 150ms
    }
  }
}

void manejarParpadeoEmergencia() {
  unsigned long tiempoActual = millis();
  // Destellos a alta frecuencia (250ms) de las luces rojas y amarillas
  static unsigned long ultimoCambioParpadeo = 0;
  static bool encendido = false;

  if (tiempoActual - ultimoCambioParpadeo >= 250) {
    ultimoCambioParpadeo = tiempoActual;
    encendido = !encendido;

    apagarTodosLosLeds();
    if (encendido) {
      // Encender todas las luces Rojas y Amarillas
      digitalWrite(PIN_N_ROJO, HIGH); digitalWrite(PIN_N_AMAR, HIGH);
      digitalWrite(PIN_S_ROJO, HIGH); digitalWrite(PIN_S_AMAR, HIGH);
      digitalWrite(PIN_E_ROJO, HIGH); digitalWrite(PIN_E_AMAR, HIGH);
      digitalWrite(PIN_O_ROJO, HIGH); digitalWrite(PIN_O_AMAR, HIGH);
      tone(PIN_BUZZER, 2000, 100); // Sonido agudo de alerta
    } else {
      digitalWrite(PIN_BUZZER, LOW);
    }
  }
}

// =============================================================================
// PARSER Y COMUNICACIÓN SERIAL
// =============================================================================

void procesarSerial() {
  while (Serial.available() > 0) {
    char c = Serial.read();
    
    if (c == '\n' || c == '\r') {
      bufferSerial.trim();
      if (bufferSerial.length() > 0) {
        ejecutarComandoSerial(bufferSerial);
      }
      bufferSerial = "";
    } else {
      bufferSerial += c;
    }
  }
}

void ejecutarComandoSerial(String cmd) {
  cmd.toUpperCase();
  Serial.print("[SERIAL RECV] Comando recibido: '");
  Serial.print(cmd);
  Serial.println("'");

  if (cmd == "EMERGENCIA") {
    activarModoEmergencia();
    return;
  }
  
  if (cmd == "NORMAL") {
    desactivarModoEmergencia();
    return;
  }

  // Parsear formato: "NS:5000,EO:3000" o "NS:5000, EO:3000"
  int posNS = cmd.indexOf("NS:");
  int posEO = cmd.indexOf("EO:");

  if (posNS != -1 && posEO != -1) {
    // Encontrar fin de número NS (usualmente es la coma)
    int finNS = cmd.indexOf(",", posNS);
    if (finNS == -1) finNS = cmd.indexOf(" ", posNS); // Separación alternativa
    
    String strNS = cmd.substring(posNS + 3, finNS);
    String strEO = cmd.substring(posEO + 3);

    strNS.trim();
    strEO.trim();

    long parsedNS = strNS.toInt();
    long parsedEO = strEO.toInt();

    // Rango de seguridad: entre 1000ms (1s) y 30000ms (30s)
    if (parsedNS >= 1000 && parsedNS <= 30000 && parsedEO >= 1000 && parsedEO <= 30000) {
      tiempo_Verde_NS = parsedNS;
      tiempo_Verde_EO = parsedEO;
      Serial.print("[SERIAL OK] Nuevos tiempos aplicados. Verde NS: ");
      Serial.print(tiempo_Verde_NS);
      Serial.print(" ms | Verde EO: ");
      Serial.print(tiempo_Verde_EO);
      Serial.println(" ms");
    } else {
      Serial.println("[SERIAL ERROR] Tiempos fuera de rango seguro (1s - 30s)");
    }
  } else {
    Serial.println("[SERIAL ERROR] Comando no reconocido o formato incorrecto.");
  }
}

// =============================================================================
// INTERFAZ EN PANTALLA OLED
// =============================================================================

void actualizarOLED(unsigned long tiempoTranscurrido) {
  display.clearDisplay();

  // 1. Cabecera Estética
  display.fillRect(0, 0, 128, 12, SSD1306_WHITE);
  display.setTextColor(SSD1306_BLACK);
  display.setTextSize(1);
  display.setCursor(4, 2);
  display.print("SISTEMA HIBRIDO IOT");

  // Volver a texto blanco
  display.setTextColor(SSD1306_WHITE);

  // Calcular segundos restantes
  long restanteMs = (long)duracionEstadoActual - (long)tiempoTranscurrido;
  if (restanteMs < 0) restanteMs = 0;
  int restanteSeg = (restanteMs + 999) / 1000; // Redondeo hacia arriba

  // 2. Dibujar UI según el Estado
  if (estadoActual == FASE_EMERGENCIA) {
    // Alarma
    display.drawRoundRect(2, 16, 124, 46, 4, SSD1306_WHITE);
    display.setTextSize(2);
    display.setCursor(14, 22);
    display.print("EMERGENCIA");
    display.setTextSize(1);
    display.setCursor(20, 44);
    display.print("BLOQUEO GENERAL");
    display.setCursor(30, 52);
    display.print("Retorno en: ");
    display.print(restanteSeg);
    display.print("s");
  } 
  else if (estadoActual == FASE_PEATONAL) {
    // Cruce Peatonal
    display.drawRoundRect(2, 16, 124, 46, 4, SSD1306_WHITE);
    display.setTextSize(1);
    display.setCursor(10, 21);
    display.print(">> CRUCE PEATONAL <<");
    display.setTextSize(2);
    display.setCursor(24, 34);
    display.print("PASE ya!");
    display.setTextSize(1);
    display.setCursor(32, 51);
    display.print("Cierre en: ");
    display.print(restanteSeg);
    display.print("s");
  } 
  else {
    // Funcionamiento Normal
    display.setTextSize(1);
    
    // Indicador de fase principal
    display.setCursor(0, 16);
    display.print("Fase: ");
    switch (estadoActual) {
      case FASE_NS_VERDE:     display.print("0 [NS Verde]"); break;
      case FASE_NS_AMARILLO:  display.print("1 [NS Amarillo]"); break;
      case FASE_EO_VERDE:     display.print("2 [EO Verde]"); break;
      case FASE_EO_AMARILLO:  display.print("3 [EO Amarillo]"); break;
    }

    // Cronómetro grande
    display.setTextSize(3);
    display.setCursor(12, 30);
    if (restanteSeg < 10) display.print("0");
    display.print(restanteSeg);
    display.setTextSize(1);
    display.setCursor(52, 44);
    display.print("segundos");

    // Croquis gráfico de luces
    // Norte-Sur
    display.setCursor(75, 16);
    display.print("N-S: ");
    if (estadoActual == FASE_NS_VERDE) display.print("[V]");
    else if (estadoActual == FASE_NS_AMARILLO) display.print("[A]");
    else display.print("[R]");

    // Este-Oeste
    display.setCursor(75, 26);
    display.print("E-O: ");
    if (estadoActual == FASE_EO_VERDE) display.print("[V]");
    else if (estadoActual == FASE_EO_AMARILLO) display.print("[A]");
    else display.print("[R]");

    // Indicador de solicitud peatonal pendiente
    if (peatonSolicitado) {
      display.fillRect(75, 52, 50, 10, SSD1306_WHITE);
      display.setTextColor(SSD1306_BLACK);
      display.setCursor(77, 53);
      display.print("PEATON");
      display.setTextColor(SSD1306_WHITE);
    } else {
      display.drawRect(75, 52, 50, 10, SSD1306_WHITE);
      display.setCursor(79, 53);
      display.print("Libre");
    }

    // Barra de progreso de la fase
    float pct = (float)tiempoTranscurrido / (float)duracionEstadoActual;
    if (pct > 1.0) pct = 1.0;
    display.drawRect(0, 56, 70, 6, SSD1306_WHITE);
    display.fillRect(0, 56, (int)(70.0 * pct), 6, SSD1306_WHITE);
  }

  display.display();
}
