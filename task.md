# 🚦 Roadmap de Desarrollo — Proyecto 11

> Cada bloque depende del anterior. No saltes al siguiente hasta que el checkpoint esté ✅.

---

## BLOQUE 1: Preparación del entorno (Día 1-2)

- [ ] **1.1** Instalar Python 3.x y verificar con `python --version`
- [ ] **1.2** Instalar librerías Python:
  ```
  pip install numpy matplotlib pyserial
  ```
- [ ] **1.3** Instalar Arduino IDE y agregar la placa ESP32:
  - Menú → Preferences → Additional Board URLs →
  - `https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json`
  - Board Manager → buscar "esp32" → instalar
- [ ] **1.4** Instalar librerías Arduino: `Adafruit SSD1306`, `Adafruit GFX`, `ESP32Servo`, `ArduinoJson`
- [ ] **1.5** Crear carpeta del proyecto con esta estructura:
  ```
  proyecto-trafico/
  ├── python/
  ├── esp32/
  ├── dashboard/
  ├── datos/
  └── docs/
  ```
- [ ] **1.6** Crear repositorio en GitHub (público, con README y licencia MIT)

> **✅ Checkpoint:** Python corre `import numpy, serial, matplotlib` sin error. Arduino IDE detecta la placa ESP32.

---

## BLOQUE 2: Semáforo básico funcionando (Día 3-7)

> Objetivo: que los LEDs cambien de fase como un semáforo real, primero en Wokwi, luego en hardware.

- [x] **2.1** Abrir la simulación en Wokwi con el código que ya tienes funcionando
- [x] **2.2** Probar que las 4 fases del semáforo funcionan correctamente:
  - Fase 0: N-S verde, E-O rojo
  - Fase 1: N-S amarillo, E-O rojo
  - Fase 2: N-S rojo, E-O verde
  - Fase 3: N-S rojo, E-O amarillo
- [x] **2.3** Probar el botón peatonal (click → todo rojo → buzzer → servo)
- [x] **2.4** Probar enviar `EMERGENCIA` por el monitor serial
- [x] **2.5** Modificar el código para que acepte tiempos por serial:
  - Python enviará: `NS:5000,EO:3000\n`
  - ESP32 parsea y actualiza `tiempo_Verde_NS` y `tiempo_Verde_EO`
- [ ] **2.6** *(Si ya tienes el ESP32 físico)* Armar el circuito en protoboard:
  - 12 LEDs + 12 resistencias 220Ω
  - Display OLED (SDA→21, SCL→22)
  - Servo (señal→23)
  - Buzzer (señal→4)
  - Botón (señal→2, con pull-up interno)
- [ ] **2.7** Cargar el código al ESP32 real y verificar que funciona igual que en Wokwi

> **✅ Checkpoint:** Los semáforos cambian solos, el botón peatonal interrumpe el ciclo, y puedes cambiar los tiempos de verde escribiendo en el monitor serial.

---

## BLOQUE 3: Simulador de tráfico en Python (Día 8-14)

> Objetivo: Python genera tráfico con Poisson y decide tiempos con lógica difusa.

- [x] **3.1** Crear `python/simulador_trafico.py`:
  - Clase `InterseccionSimulada` con colas por dirección (N, S, E, O)
  - Llegadas de vehículos con `np.random.poisson(lambda)`
  - Perfiles horarios (pico AM 8:00, valle 14:00, pico PM 18:00)
  - Función que calcula congestión (%) = cola / capacidad
- [x] **3.2** Probar el simulador SIN conexión al ESP32:
  - Correr 100 pasos de simulación
  - Imprimir en consola: `Norte: 78% | Sur: 23% | Este: 55% | Oeste: 41%`
  - Verificar que los números varían y que suben en hora pico
- [x] **3.3** Crear `python/control_adaptativo.py`:
  - Funciones de membresía: `baja(x)`, `media(x)`, `alta(x)`
  - 7 reglas difusas
  - Defuzzificación por promedio ponderado
  - Función `calcular_tiempos(congestion)` → retorna tiempos de verde
- [x] **3.4** Probar el control adaptativo SIN conexión al ESP32:
  - Darle congestión `{"N": 85, "S": 20, "E": 45, "O": 50}`
  - Verificar que da más verde a N-S que a E-O
  - Probar caso equilibrado `{"N": 50, "S": 50, "E": 50, "O": 50}` → tiempos iguales
- [x] **3.5** Crear `python/comunicacion_serial.py`:
  - Función `conectar(puerto, baudrate)` → abre pyserial
  - Función `enviar_tiempos(verde_NS, verde_EO)` → manda `NS:5000,EO:3000\n`
  - Manejo de errores (ESP32 desconectado, puerto ocupado)
- [x] **3.6** Crear `python/visualizador.py`:
  - Gráfica matplotlib en tiempo real con 4 líneas (congestión por dirección)
  - Se actualiza cada 2 segundos
- [x] **3.7** Crear `python/main.py` que integre todo:
  ```
  Bucle cada 2 segundos:
    1. simulador genera tráfico (Poisson)
    2. calcula congestión
    3. control difuso decide tiempos
    4. envía tiempos al ESP32 por serial
    5. actualiza gráfica matplotlib
    6. guarda log en CSV
  ```
- [ ] **3.8** Probar el sistema completo: Python + ESP32 (Wokwi o real)
  - Verificar que los LEDs cambian según la congestión simulada
  - Verificar que en hora pico la dirección congestionada recibe más verde

> **✅ Checkpoint:** Python genera tráfico, decide tiempos inteligentemente, y el ESP32 obedece en tiempo real. La gráfica de matplotlib muestra la congestión subiendo y bajando.

---

## BLOQUE 4: Nube + Dashboard web (Día 15-21)

> Objetivo: los datos viajan del ESP32 a Firebase y se ven en una página web bonita.

- [ ] **4.1** Crear cuenta en Firebase (plan Spark gratuito)
- [ ] **4.2** Crear proyecto en Firebase Console → activar Realtime Database
- [ ] **4.3** Modificar el código del ESP32 para conectarse a WiFi:
  - Agregar `#include <WiFi.h>` y `WiFi.begin(ssid, password)`
  - *(En Wokwi, el WiFi está simulado y funciona automáticamente)*
- [ ] **4.4** Instalar librería `Firebase-ESP-Client` en Arduino IDE
- [ ] **4.5** ESP32 envía datos a Firebase cada 2 segundos:
  ```
  /trafico/congestion/N → 78
  /trafico/congestion/S → 23
  /trafico/semaforo/fase → "NS_VERDE"
  /trafico/semaforo/tiempo_restante → 28
  ```
- [ ] **4.6** Verificar en Firebase Console que los datos llegan y se actualizan
- [ ] **4.7** Crear `dashboard/index.html` con la estructura visual:
  - Encabezado: "Centro de Control de Movilidad Urbana"
  - Panel izquierdo: mapa de la intersección (Canvas 2D o Leaflet.js)
  - Panel derecho: barras de congestión por dirección
  - Panel inferior: gráfico histórico (Chart.js)
  - Zona de alertas
- [ ] **4.8** Conectar el dashboard a Firebase con el SDK de JavaScript:
  ```js
  firebase.database().ref('trafico').on('value', (snapshot) => {
      actualizarTodo(snapshot.val());
  });
  ```
- [ ] **4.9** Darle estilos CSS profesionales (colores oscuros, gradientes, animaciones)
- [ ] **4.10** Desplegar en Firebase Hosting (`firebase deploy`) → URL pública
- [ ] **4.11** Probar flujo completo: Python → Serial → ESP32 → Firebase → Dashboard

> **✅ Checkpoint:** Abres la URL del dashboard en tu celular y ves la congestión actualizándose en tiempo real mientras el simulador corre en tu PC.

---

## BLOQUE 5: Validación + Artículo (Día 22-30)

> Objetivo: demostrar con datos que tu sistema funciona mejor que un semáforo fijo.

- [ ] **5.1** Ejecutar 10 simulaciones con control **fijo** (30s verde para todos):
  - Guardar logs en `datos/resultados_fijo.csv`
  - Campos: timestamp, cola_N, cola_S, cola_E, cola_O, espera_promedio
- [ ] **5.2** Ejecutar 10 simulaciones con control **adaptativo** (lógica difusa):
  - Guardar logs en `datos/resultados_adaptativo.csv`
- [ ] **5.3** Crear `datos/analisis_comparativo.py`:
  - Calcular: media, desviación estándar, máximos de espera
  - Prueba t-Student para comparar medias
  - Generar gráficas comparativas (barras, boxplot)
- [ ] **5.4** Generar tabla de resultados final:
  - % mejora en tiempo de espera
  - % mejora en cola máxima
  - p-valor de la prueba estadística
- [ ] **5.5** Grabar video de demostración (2-3 minutos):
  - Mostrar simultáneamente: terminal Python, LEDs del ESP32, dashboard web
  - Narrar lo que pasa: "Ahora estamos en hora pico, la congestión sube en Norte..."
- [ ] **5.6** Escribir el artículo publicable (20 páginas máximo, APA 7ª):
  - Resumen/Abstract (250 palabras, bilingüe)
  - Introducción (8 puntos del documento guía)
  - Marco Teórico (tabla de 12+ filas)
  - Metodología (12 elementos)
  - Resultados (figuras + tablas de la validación)
  - Discusión (8 componentes)
  - Conclusiones + Recomendaciones
  - Referencias (25-30 en APA)
  - Anexos (código, esquemáticos, enlace a GitHub y video)
- [ ] **5.7** Subir todo a GitHub: código, datos, artículo, video, README con instrucciones
- [ ] **5.8** Ensayar la defensa oral (20 min presentación + 10 min preguntas)

> **✅ Checkpoint final:** Tienes artículo impreso, demo funcionando en vivo, dashboard accesible por URL, video de respaldo, y repositorio GitHub completo.

---

## 📍 ¿Dónde estás ahora?

```
[██████████████████░░░░░░░░░░░░] ~60%

✅ Bloque 1: Listo (Entorno configurado y carpetas creadas)
✅ Bloque 2: Listo (Simulación en Wokwi completa con tiempos dinámicos, peatonal y emergencia)
✅ Bloque 3: Listo (Simulador Python, Lógica Difusa y Visualización en tiempo real completados)
⬜ Bloque 4: Pendiente — Nube + Dashboard web (Firebase + Next.js/HTML)
⬜ Bloque 5: Pendiente — Validación + Artículo científico
```

> [!TIP]
> **Siguiente paso inmediato:** Probar la integración completa (Bloque 3.8) ejecutando el visualizador de Python conectado al puerto serie virtual del simulador de Wokwi, o avanzar directamente al **Bloque 4** para conectar el ESP32 a Firebase y desarrollar el Dashboard web en tiempo real.
