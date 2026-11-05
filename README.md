# El Dueño — Modo carrera

Juego web de gestión de un club argentino, construido con Flask, plantillas Jinja, SQLite y la integración con la **API Live Football Data**. La interfaz está en español y usa un tema oscuro optimizado.

## Ejecutar en Windows

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

Abrí `http://127.0.0.1:5000`. La base `career.sqlite3` se crea y actualiza automáticamente.

## Flujo disponible

- **Creación del club:** Selección de nombre, provincia y categoría entre **Primera División** y **Primera Nacional**, además de escudo personalizable con dos colores, doce símbolos y cuatro siluetas (clásico, redondo, redondeado y cuadrado).
- **Veinte días de pretemporada:** Catálogo con más de 50 decisiones de presidencia para moldear el presupuesto, hinchada y popularidad del club.
- **Transición automática al Mercado de Fichajes:** Al completar el día 20, el sistema sincroniza automáticamente los datos de la **API Live Football Data** y redirige al mercado de pases.
- **Mercado de Pases completo:** Todos los jugadores reales de la categoría seleccionada, con búsqueda por nombre y filtros por equipo, posición y OVR máximo, paginación de hasta 12 jugadores por página, edad, valoración media (overall), valor de transferencia aumentado un 20% y limitado a **$5.000.000 en Primera División** y **$2.000.000 en Primera Nacional**, acompañados por el **nombre del club y su escudo oficial**. Los clubes de Primera Nacional pueden pedir jugadores de Primera División a préstamo por una temporada: el costo se informa en el mercado y equivale al 10% del valor del jugador, con un mínimo de $50.000. Se descuenta del presupuesto y el jugador vuelve automáticamente al finalizar el año.
- **Plantel de hasta 25 jugadores:** El cupo máximo es siempre 25 desde la primera temporada y se mantiene igual en todos los modos carrera y temporadas. El mercado es opcional: podés comenzar la temporada cuando quieras con el plantel actual o vender jugadores; cada venta libera un lugar y suma $500.000 al presupuesto.
- **Armado automático del equipo:** Un botón incorpora al azar 1 arquero, 4 defensores, 4 mediocampistas y 4 delanteros, respetando el presupuesto disponible y el cupo de 25. También arma una alineación inicial según la formación elegida, pero no inicia la temporada: podés revisar titulares, hacer cambios y comenzar cuando estés listo. La formación guardada se muestra en el tablero de cada partido de liga.
- **Formación y banco:** Las incorporaciones se muestran en una cancha táctica con las formaciones 4-4-2, 4-3-3 y 4-2-3-1. Podés seleccionar directamente dos jugadores para intercambiarlos entre titulares y suplentes y guardar la alineación.
- **Torneo jugable por fechas:** Se genera una liga todos contra todos con los clubes de la categoría y el club creado. En el tablero del partido podés iniciar la simulación en vivo: avanza el reloj, actualiza el marcador y revela goles, autores y tarjetas amarillas o rojas. El relato queda guardado para volver a consultarlo; también se muestran los resultados de la jornada y se avanza a la siguiente fecha. La tabla de posiciones se actualiza en cada fecha.
- **Decisiones de temporada cada dos fechas:** 14 eventos aleatorios, entre ellos rotación, rivales directos, prensa, incentivos al plantel, viajes, entradas, divisiones juveniles, entrenamiento, estadio e hinchada. Los eventos con contexto específico solo aparecen cuando corresponde y no se repite un evento de las últimas tres decisiones. La decisión pausa el avance hasta que elijas y sus efectos influyen en los partidos, el presupuesto y el apoyo.
- **Simulación de todo el año:** Podés simular automáticamente las fechas restantes desde el calendario. Las rondas de Copa Argentina se distribuyen entre las fechas de liga y se simulan en la fecha asignada. La simulación de liga se detiene cada dos fechas para que tomes una decisión y continúa al confirmarla.
- **Copa Argentina:** Al comenzar cada temporada, después del mercado, se abre el sorteo de una copa a partido único entre todos los clubes de Primera División y Primera Nacional, incluido el tuyo. La llave se presenta desde los extremos hacia una final central, al estilo del cuadro oficial, y se adapta al ancho de pantalla. Los pases libres completan las rondas cuando la cantidad de clasificados es impar. Las rondas se programan entre fechas de liga: el partido de tu club aparece en el panel del torneo en su fecha, donde podés jugarlo; también podés simular toda la ronda de una vez o resolver cruces por separado desde la sección Copa. No se puede avanzar la liga en una fecha de Copa hasta resolver y avanzar esa ronda. Los empates se definen por penales y cada ganador ocupa su lugar correspondiente en la llave. El campeón recibe **$3.500.000** como máximo y los equipos eliminados reciben premios decrecientes según la instancia. Al ganar, aparece la imagen del trofeo. Es una competencia opcional: podés comenzar una nueva temporada aunque no la hayas terminado.
- **Progresión de jugadores:** Al comenzar la temporada siguiente, los jugadores aumentan o bajan su OVR según sus presencias, goles y tarjetas registrados en los partidos. La progresión se aplica una sola vez por temporada.
- **Playoff de ascenso:** Al tocar «JUGAR PARTIDO», el encuentro de tu club se muestra con reloj en vivo, goles y tarjetas, tanto si gana como si pierde o empata; el marcador en vivo usa el mismo tablero que el partido para no confundirse con el de la liga. Si termina empatado, se define en una tanda interactiva: elegís entre tres sectores del arco, con animación del remate de tu jugador o la atajada de tu arquero; también podés simular la tanda completa y ver cada penal revelado en secuencia. El rival ejecuta automáticamente; vos solo elegís las acciones de tu equipo. Los penales no vuelven a iniciar la simulación del partido. Si hay un ganador en los 90 minutos, clasifica directamente. Los demás cruces se simulan automáticamente.
- **Premios y ascenso/descenso:** Primera División se equilibra a 30 equipos al crear cada fixture (incluye tu club si estás en esa categoría). El campeón recibe $20.000.000 y su tarjeta muestra la foto del trofeo de liga; los premios por puesto son decrecientes. En Primera Nacional, el premio por puesto parte de $7.000.000 para el campeón. Los ascensos muestran el trofeo compartido y los descensos una flecha roja. Los dos últimos equipos de Primera División descienden; el campeón de Primera Nacional asciende directamente y el ganador del playoff obtiene el segundo ascenso. Los movimientos se aplican al comenzar la siguiente temporada. Al reiniciar una carrera, los clubes vuelven a las categorías iniciales del dataset 2026 y se limpian estadísticas e historial de desarrollo para que la nueva partida empiece de cero. Las funciones del juego se mantienen disponibles en cada carrera nueva.
- **Premio Copa Argentina:** El campeón se muestra con la foto del trofeo de la Copa Argentina, tanto en el torneo como en las tarjetas de temporada.
- **Colores de posiciones:** Verde para el campeón, dorado para los puestos Libertadores, celeste para Sudamericana y rojo para los puestos de descenso.
- **Copas internacionales:** En Primera División, los puestos 1.º a 3.º clasifican a la CONMEBOL Libertadores y los puestos 4.º a 9.º a la CONMEBOL Sudamericana. Al finalizar el torneo, se muestra el mensaje de clasificación junto con el logo correspondiente.
- **Nuevas temporadas:** Al terminar la liga y cualquier playoff, podés iniciar otro año conservando presupuesto y plantel, con espacio para incorporar hasta completar el máximo de 25 jugadores. Si ascendés, el siguiente torneo se simula en Primera División; la cantidad de clubes y fechas se genera según la categoría.
- **Fixture oficial 2026:** El calendario AFA de 2026 conserva sus fechas, localías y escudos.

## Integración con API Live Football Data

La integración está implementada en `live_football_api.py`, conectándose al servicio de RapidAPI (`free-api-live-football-data.p.rapidapi.com`).

### Características de la integración:
1. **Doble categoría del fútbol argentino:**
   - **Primera División:** 28 equipos (River Plate, Boca Juniors, Racing, Independiente, San Lorenzo, Vélez, Estudiantes, etc.).
   - **Primera Nacional (B Nacional):** 20 equipos (Quilmes, Ferro Carril Oeste, Chacarita, San Martín de Tucumán, Colón, etc.).
2. **Escudos vectoriales y remotos:** Todos los clubes incluyen escudos en formato SVG de alta calidad en `/static/crests/` con renderizado optimizado y respaldo ante fallos de conexión.
3. **Fixture 2026:** 568 partidos programados a lo largo del año 2026 (378 de Primera División y 190 de Primera Nacional).
4. **Planteles reales:** Más de 500 futbolistas reales con sus estadísticas de juego, valores de mercado y salarios acordes a la economía del juego.

### Configuración de API Key (Opcional)
La aplicación funciona inmediatamente lista para usar con el dataset oficial 2026 incluido. Si contás con una clave de RapidAPI para consultar la API en vivo, podés configurarla mediante variable de entorno:

```powershell
$env:RAPIDAPI_KEY = "tu_clave_de_rapidapi"
python app.py
```

O también podés forzar la sincronización en cualquier momento desde el botón **"↻ ACTUALIZAR API"** en el mercado o en el calendario.

## Ejecución de Tests

```powershell
.\.venv\Scripts\python.exe -m unittest discover tests
```
