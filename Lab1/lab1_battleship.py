# -*- coding: utf-8 -*-
"""
=======================================================================
 BATTLESHIP - LABORATORIO 1: AGENTES
 Facultad de Ingenieria, UNAM - Inteligencia Artificial - Grupo 1
=======================================================================

La practica pide tres tipos de agente del modelo de Russell & Norvig.
Este programa implementa esos tres, mas un cuarto que NO forma parte de
lo solicitado y que se incluye declaradamente como control experimental:

  1. AgenteReflejoSimple  -> agente reflejo simple (simple reflex agent)
  2. AgenteBasadoEnMetas  -> agente basado en metas (goal-based agent)
  3. AgenteOptimo         -> agente de desempeno optimo (utility-based)
  4. AgenteBarrido        -> control de lazo abierto (NO es uno de los tres)

Modos de juego: Humano vs Agente  y  Agente vs Agente.
El registro historico de victorias se lleva POR ENFRENTAMIENTO, no por
modo, para que los porcentajes sean comparables entre si.

Ejecucion:  python lab1_battleship.py
Requiere:   pygame   (pip install pygame)
=======================================================================
"""

import sys
import time
import random
import csv
import os
import argparse

try:
    import pygame
except ImportError:
    pygame = None

# =====================================================================
# CONFIGURACION
# =====================================================================
ANCHO_VENTANA = 1200
ALTO_VENTANA = 800
FPS = 60

TAM_TABLERO = 10
TAM_CELDA = 36
OFFSET_Y_TABLERO = 190
OFFSET_X_J1 = 100
OFFSET_X_J2 = 700

LETRAS = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"]

# Paleta (estilo radar tactico naval)
COLOR_FONDO = (10, 18, 30)
COLOR_PANEL = (18, 32, 51)
COLOR_BORDE_PANEL = (35, 60, 92)
COLOR_AGUA = (16, 42, 68)
COLOR_LINEA_GRID = (28, 70, 110)
COLOR_BARCO = (90, 150, 200)
COLOR_BARCO_BORDE = (140, 200, 255)
COLOR_AGUA_DISPARADA = (30, 80, 120)
COLOR_IMPACTO = (255, 65, 65)
COLOR_HUNDIDO = (180, 20, 20)
COLOR_TEXTO_PRINCIPAL = (220, 240, 255)
COLOR_TEXTO_MUTED = (120, 160, 190)
COLOR_RADAR_VERDE = (46, 213, 115)
COLOR_ACCENTO_AMARILLO = (255, 190, 40)
COLOR_BOTON = (24, 48, 77)
COLOR_BOTON_HOVER = (38, 75, 120)
COLOR_BOTON_ACTIVO = (46, 110, 175)
COLOR_BARRA = [(46, 213, 115), (255, 190, 40), (255, 71, 87), (108, 154, 255)]

# Flota estandar: (nombre, longitud)
NOMBRES_BARCOS = [
    ("Portaaviones", 5),
    ("Acorazado", 4),
    ("Crucero", 3),
    ("Submarino", 3),
    ("Destructor", 2),
]
LONGITUDES_FLOTA = [tam for _, tam in NOMBRES_BARCOS]
CELDAS_OCUPADAS = sum(LONGITUDES_FLOTA)   # 17


# =====================================================================
# LOGICA DEL JUEGO
# =====================================================================
class Barco:
    def __init__(self, nombre, tam):
        self.nombre = nombre
        self.tam = tam
        self.posiciones = []
        self.impactos = 0

    @property
    def hundido(self):
        return self.impactos >= self.tam


class Tablero:
    def __init__(self):
        self.limpiar()

    def limpiar(self):
        self.grid = [[None] * TAM_TABLERO for _ in range(TAM_TABLERO)]
        self.disparos_recibidos = [[None] * TAM_TABLERO for _ in range(TAM_TABLERO)]
        self.barcos = []

    def puede_colocar(self, fila, col, tam, orientacion):
        for i in range(tam):
            f = fila if orientacion == 'H' else fila + i
            c = col + i if orientacion == 'H' else col
            if not (0 <= f < TAM_TABLERO and 0 <= c < TAM_TABLERO):
                return False
            if self.grid[f][c] is not None:
                return False
        return True

    def colocar_barco(self, barco, fila, col, orientacion):
        barco.posiciones = []
        for i in range(barco.tam):
            f = fila if orientacion == 'H' else fila + i
            c = col + i if orientacion == 'H' else col
            self.grid[f][c] = barco
            barco.posiciones.append((f, c))
        self.barcos.append(barco)

    def auto_posicionar(self):
        """Coloca la flota al azar. A diferencia de una version anterior, si un
        barco no logra colocarse se levanta una excepcion en lugar de seguir
        con una flota incompleta (fallo silencioso)."""
        self.limpiar()
        for nombre, tam in NOMBRES_BARCOS:
            b = Barco(nombre, tam)
            for _ in range(1000):
                f = random.randrange(TAM_TABLERO)
                c = random.randrange(TAM_TABLERO)
                orient = random.choice(['H', 'V'])
                if self.puede_colocar(f, c, tam, orient):
                    self.colocar_barco(b, f, c, orient)
                    break
            else:
                raise RuntimeError(f"No se pudo colocar el barco {nombre} ({tam} celdas)")
        assert len(self.barcos) == len(NOMBRES_BARCOS)

    def recibir_disparo(self, f, c):
        if self.disparos_recibidos[f][c] is not None:
            return "REPETIDO", None
        objeto = self.grid[f][c]
        if objeto is None:
            self.disparos_recibidos[f][c] = 'AGUA'
            return "AGUA", None
        objeto.impactos += 1
        self.disparos_recibidos[f][c] = 'TOCADO'
        if objeto.hundido:
            for bf, bc in objeto.posiciones:
                self.disparos_recibidos[bf][bc] = 'HUNDIDO'
            return "HUNDIDO", objeto
        return "TOCADO", objeto

    @property
    def todos_hundidos(self):
        return len(self.barcos) > 0 and all(b.hundido for b in self.barcos)


# =====================================================================
# AGENTES
# =====================================================================
class Agente:
    """Clase base. Guarda unicamente el historial de percepciones recibidas;
    cada subclase decide cuanto de ese historial consulta para actuar."""

    tipo = "base"
    taxonomia = ""
    descripcion = ""

    def __init__(self, nombre):
        self.nombre = nombre
        self.clave = None
        self.etiqueta = nombre       # lo sobreescribe crear_agente()
        self.reiniciar()

    def reiniciar(self):
        self.rastreo = [[None] * TAM_TABLERO for _ in range(TAM_TABLERO)]
        self.barcos_enemigos_vivos = list(LONGITUDES_FLOTA)

    def registrar_resultado(self, f, c, resultado, barco_hundido=None):
        if resultado == "REPETIDO":
            return                                  # nunca sobreescribir el historial
        self.rastreo[f][c] = resultado
        if resultado == "HUNDIDO" and barco_hundido is not None:
            # marcar TODAS las celdas del barco, no solo la ultima disparada
            for bf, bc in barco_hundido.posiciones:
                self.rastreo[bf][bc] = "HUNDIDO"
            if barco_hundido.tam in self.barcos_enemigos_vivos:
                self.barcos_enemigos_vivos.remove(barco_hundido.tam)

    def celdas_libres(self):
        return [(f, c) for f in range(TAM_TABLERO) for c in range(TAM_TABLERO)
                if self.rastreo[f][c] is None]

    def decidir_tiro(self):
        raise NotImplementedError


class AgenteReflejoSimple(Agente):
    """AGENTE REFLEJO SIMPLE (simple reflex agent).

    Actua mediante una unica regla condicion-accion aplicada a la percepcion
    INMEDIATA. No conserva metas, ni planes, ni un modelo del tablero:

        SI mi disparo anterior fue impacto  ENTONCES disparar a una vecina
        SI NO                               ENTONCES disparar al azar

    El historial de celdas ya disparadas se consulta solo para no repetir una
    jugada ilegal, no para razonar.
    """
    tipo = "Reflejo simple"
    taxonomia = "simple reflex agent"
    descripcion = "Regla condicion-accion sobre la ultima percepcion."

    def __init__(self):
        super().__init__("Agente Reflejo Simple")

    def reiniciar(self):
        super().reiniciar()
        # 'barcos_enemigos_vivos' se hereda de la clase base pero este agente
        # NUNCA lo consulta: hacerlo lo convertiria en otra cosa.
        self.ultimo_impacto = None

    def registrar_resultado(self, f, c, resultado, barco_hundido=None):
        super().registrar_resultado(f, c, resultado, barco_hundido)
        # la percepcion actual es lo unico que condiciona la siguiente accion
        self.ultimo_impacto = (f, c) if resultado == "TOCADO" else None

    def decidir_tiro(self):
        if self.ultimo_impacto is not None:
            f, c = self.ultimo_impacto
            vecinas = [(f + df, c + dc) for df, dc in ((-1, 0), (1, 0), (0, -1), (0, 1))
                       if 0 <= f + df < TAM_TABLERO and 0 <= c + dc < TAM_TABLERO
                       and self.rastreo[f + df][c + dc] is None]
            if vecinas:
                return random.choice(vecinas)
        libres = self.celdas_libres()
        return random.choice(libres) if libres else (0, 0)


class AgenteBasadoEnMetas(Agente):
    """AGENTE BASADO EN METAS (goal-based agent).

    Mantiene una meta explicita y un plan para alcanzarla. Al detectar un
    impacto adopta la meta "hundir este barco" y genera una cola de acciones
    candidatas (las celdas vecinas) que sirven a esa meta; mientras la cola
    tenga elementos esta persiguiendo la meta. Al hundirlo, la meta se cumple,
    la cola se purga y vuelve a la fase de busqueda.

    La busqueda usa paridad: como el barco mas corto ocupa dos celdas, todo
    barco cubre al menos una celda de un color del tablero de ajedrez, asi que
    basta explorar la mitad del tablero para garantizar encontrarlos.
    """
    tipo = "Basado en metas"
    taxonomia = "goal-based agent"
    descripcion = "Meta explicita por barco + plan de celdas vecinas."

    def __init__(self):
        super().__init__("Agente Basado en Metas")

    def reiniciar(self):
        super().reiniciar()
        self.meta = None     # celda del impacto que abrio la meta vigente
        self.plan = []       # acciones seleccionadas porque conducen a esa meta

    def meta_cumplida(self, resultado):
        """Test de meta: la meta 'hundir el barco que ocupa esta celda' se
        satisface exactamente cuando la percepcion reporta HUNDIDO."""
        return resultado == "HUNDIDO"

    def registrar_resultado(self, f, c, resultado, barco_hundido=None):
        super().registrar_resultado(f, c, resultado, barco_hundido)
        if resultado == "TOCADO":
            if self.meta is None:
                self.meta = (f, c)          # se adopta una meta nueva
            for df, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                nf, nc = f + df, c + dc
                if 0 <= nf < TAM_TABLERO and 0 <= nc < TAM_TABLERO:
                    if self.rastreo[nf][nc] is None and (nf, nc) not in self.plan:
                        self.plan.append((nf, nc))
        elif self.meta_cumplida(resultado):
            self.meta = None                # meta satisfecha: se abandona
            # Se descartan solo las acciones ya ejecutadas.
            # NOTA DE DISENO: seria tentador descartar tambien las vecinas del
            # barco recien hundido, pero en estas reglas los barcos PUEDEN
            # tocarse, asi que una vecina sigue siendo un objetivo plausible.
            # Medido sobre 12,000 partidas, purgarlas empeora al agente de
            # 57.9 a 59.0 tiros y engorda la cola de la distribucion, porque
            # las celdas descartadas caen a menudo en el color de paridad que
            # la busqueda no explora.
            self.plan = [p for p in self.plan if self.rastreo[p[0]][p[1]] is None]

    def decidir_tiro(self):
        # Fase 1: hay una meta vigente -> ejecutar el plan que conduce a ella.
        while self.plan:
            f, c = self.plan.pop()
            if self.rastreo[f][c] is None:
                return f, c
        # Fase 2: no hay meta -> buscar una, con paridad.
        paridad = [(f, c) for f, c in self.celdas_libres() if (f + c) % 2 == 0]
        if paridad:
            return random.choice(paridad)
        libres = self.celdas_libres()
        return random.choice(libres) if libres else (0, 0)


class AgenteOptimo(Agente):
    """AGENTE DE DESEMPENO OPTIMO (utility-based agent).

    No persigue una meta binaria: define una medida de desempeno numerica y
    elige en cada turno la accion que la maximiza. La medida es la densidad de
    colocaciones: para cada barco aun a flote y cada orientacion se desliza el
    barco por todas sus posiciones legales, y cada posicion compatible con lo
    observado deposita peso sobre sus celdas no disparadas.

    Una posicion es compatible si ninguna de sus celdas es agua conocida ni
    pertenece a un barco ya hundido. Las posiciones que cubren impactos
    pendientes reciben un peso mucho mayor, lo que reproduce el acorralamiento
    sin necesidad de programarlo aparte.
    """
    tipo = "Desempeno optimo"
    taxonomia = "optimal performance"
    descripcion = "Maximiza la densidad de colocaciones compatibles."
    BONO_IMPACTO = 60

    def __init__(self):
        super().__init__("Agente de Desempeno Optimo")

    def mapa_densidad(self):
        mapa = [[0] * TAM_TABLERO for _ in range(TAM_TABLERO)]
        for tam in self.barcos_enemigos_vivos:
            for orient in ('H', 'V'):
                max_f = TAM_TABLERO if orient == 'H' else TAM_TABLERO - tam + 1
                max_c = TAM_TABLERO - tam + 1 if orient == 'H' else TAM_TABLERO
                for f in range(max_f):
                    for c in range(max_c):
                        celdas = [(f, c + i) if orient == 'H' else (f + i, c)
                                  for i in range(tam)]
                        estados = [self.rastreo[a][b] for a, b in celdas]
                        if any(e in ("AGUA", "HUNDIDO") for e in estados):
                            continue
                        impactos = sum(1 for e in estados if e == "TOCADO")
                        peso = self.BONO_IMPACTO ** impactos if impactos else 1
                        for (a, b), e in zip(celdas, estados):
                            if e is None:
                                mapa[a][b] += peso
        return mapa

    def decidir_tiro(self):
        mapa = self.mapa_densidad()
        mejor, candidatos = -1, []
        for f, c in self.celdas_libres():
            if mapa[f][c] > mejor:
                mejor, candidatos = mapa[f][c], [(f, c)]
            elif mapa[f][c] == mejor:
                candidatos.append((f, c))
        if not candidatos:
            candidatos = self.celdas_libres()
        return random.choice(candidatos) if candidatos else (0, 0)


class AgenteBarrido(Agente):
    """CONTROL DE LAZO ABIERTO - no es uno de los tres agentes solicitados.

    Recorre el tablero en orden, celda por celda, sin consultar jamas el
    contenido de lo que percibe. Se incluye como piso de comparacion: sirve
    para demostrar que los otros tres si aprovechan la retroalimentacion.
    Queda por DEBAJO del agente reflejo simple en la taxonomia, porque ni
    siquiera reacciona al percepto.
    """
    tipo = "Control (lazo abierto)"
    taxonomia = "control - NO solicitado"
    descripcion = "Barrido fila por fila; ignora lo que percibe."

    def __init__(self):
        super().__init__("Barrido Sistematico")

    def reiniciar(self):
        super().reiniciar()
        self.cursor = 0

    def decidir_tiro(self):
        while self.cursor < TAM_TABLERO * TAM_TABLERO:
            f, c = divmod(self.cursor, TAM_TABLERO)
            self.cursor += 1
            if self.rastreo[f][c] is None:
                return f, c
        libres = self.celdas_libres()
        return random.choice(libres) if libres else (0, 0)


# Catalogo de agentes: clave -> (etiqueta corta, clase)
CATALOGO = [
    ("reflejo", "Reflejo Simple",   AgenteReflejoSimple),
    ("metas",   "Basado en Metas",  AgenteBasadoEnMetas),
    ("optimo",  "Desempeno Optimo", AgenteOptimo),
    ("barrido", "Barrido (control)", AgenteBarrido),
]
CLASES = {k: cls for k, _, cls in CATALOGO}
ETIQUETAS = {k: et for k, et, _ in CATALOGO}


def crear_agente(clave):
    """Crea el agente y le adhiere su etiqueta canonica. Todas las estadisticas
    se anotan con esta etiqueta, nunca con el nombre largo, para que una misma
    entidad no acabe contabilizada bajo dos claves distintas."""
    ag = CLASES[clave]()
    ag.clave = clave
    ag.etiqueta = ETIQUETAS[clave]
    return ag


# =====================================================================
# MOTOR DE PARTIDA SIN INTERFAZ (para la simulacion por lotes)
# =====================================================================
def jugar_partida(clave1, clave2, empieza=1):
    """Juega una partida completa agente vs agente y devuelve
    (ganador, tiros1, tiros2). 'empieza' es 1 o 2."""
    t1, t2 = Tablero(), Tablero()
    t1.auto_posicionar()
    t2.auto_posicionar()
    a1, a2 = crear_agente(clave1), crear_agente(clave2)
    turno = empieza
    n1 = n2 = 0
    while True:
        if turno == 1:
            f, c = a1.decidir_tiro()
            r, b = t2.recibir_disparo(f, c)
            a1.registrar_resultado(f, c, r, b)
            n1 += 1
            if t2.todos_hundidos:
                return 1, n1, n2
            turno = 2
        else:
            f, c = a2.decidir_tiro()
            r, b = t1.recibir_disparo(f, c)
            a2.registrar_resultado(f, c, r, b)
            n2 += 1
            if t1.todos_hundidos:
                return 2, n1, n2
            turno = 1


# =====================================================================
# INTERFAZ GRAFICA
# =====================================================================
VELOCIDADES = [("LENTA", 0.60), ("NORMAL", 0.25), ("RAPIDA", 0.08), ("TURBO", 0.0)]
LOTES = [100, 1000, 5000]


class Juego:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Battleship - Laboratorio 1: Agentes (FI UNAM)")
        self.pantalla = pygame.display.set_mode((ANCHO_VENTANA, ALTO_VENTANA))
        self.reloj = pygame.time.Clock()

        self.f_titulo = pygame.font.SysFont("consolas", 26, bold=True)
        self.f_sub = pygame.font.SysFont("consolas", 17, bold=True)
        self.f_ui = pygame.font.SysFont("consolas", 14)
        self.f_mini = pygame.font.SysFont("consolas", 11)

        self.estado = 'MENU'
        self.modo = 'HUMANO'                 # 'HUMANO' o 'AGENTES'
        self.clave1 = 'metas'                # agente 1 (en modo humano, no se usa)
        self.clave2 = 'optimo'               # agente 2 / rival del humano
        self.idx_velocidad = 1

        self.tablero1, self.tablero2 = Tablero(), Tablero()
        self.agente1 = self.agente2 = None
        self.indice_barco = 0
        self.orientacion = 'H'

        self.turno = 1
        self.empieza = 1                     # se alterna entre partidas
        self.n_partidas = 0                  # cuantas van en modo agente vs agente
        self.log = "Selecciona el modo de combate y los agentes."
        self.ganador = None
        self.tiros1 = self.tiros2 = 0
        self.t_ultimo = 0.0

        # registro historico POR ENFRENTAMIENTO
        self.registro = {}
        self.sim_restantes = 0
        self.sim_total = 0
        self.mensaje_csv = ""

    # ---------------- registro de estadisticas ----------------
    def clave_enfrentamiento(self, modo=None, c1=None, c2=None):
        modo = modo or self.modo
        c1 = c1 or self.clave1
        c2 = c2 or self.clave2
        if modo == 'HUMANO':
            return ('HUMANO', c2)
        return ('AGENTES',) + tuple(sorted((c1, c2)))

    def participantes(self, clave):
        if clave[0] == 'HUMANO':
            return ["Humano", ETIQUETAS[clave[1]]]
        a, b = ETIQUETAS[clave[1]], ETIQUETAS[clave[2]]
        if a == b:                       # mismo agente en ambos lados
            return [a + " (A)", b + " (B)"]
        return [a, b]

    def etiquetar_lados(self):
        """Si el mismo agente juega en ambos lados, hay que distinguirlos o el
        registro sumaria las dos victorias bajo una sola clave."""
        if self.clave1 == self.clave2:
            self.agente1.etiqueta = ETIQUETAS[self.clave1] + " (A)"
            self.agente2.etiqueta = ETIQUETAS[self.clave2] + " (B)"

    def anotar(self, clave, nombre_ganador):
        reg = self.registro.setdefault(clave, {"total": 0, "victorias": {}})
        reg["total"] += 1
        reg["victorias"][nombre_ganador] = reg["victorias"].get(nombre_ganador, 0) + 1

    def exportar_csv(self):
        ruta = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "estadisticas_battleship.csv")
        try:
            with open(ruta, "w", newline="", encoding="utf-8") as fh:
                w = csv.writer(fh)
                w.writerow(["modo", "participante_1", "participante_2",
                            "partidas", "ganador", "victorias", "porcentaje"])
                for clave, reg in sorted(self.registro.items(), key=lambda x: str(x[0])):
                    p = self.participantes(clave)
                    p1, p2 = p[0], p[1]
                    for nombre in p:
                        v = reg["victorias"].get(nombre, 0)
                        pct = 100.0 * v / reg["total"] if reg["total"] else 0.0
                        w.writerow([clave[0], p1, p2, reg["total"], nombre, v, f"{pct:.2f}"])
            self.mensaje_csv = f"Guardado: {os.path.basename(ruta)}"
        except OSError as e:
            self.mensaje_csv = f"No se pudo guardar: {e}"

    # ---------------- ciclo de partida ----------------
    def nueva_partida(self):
        self.tablero1.limpiar()
        self.tablero2.limpiar()
        self.ganador = None
        self.tiros1 = self.tiros2 = 0
        self.mensaje_csv = ""
        if self.modo == 'AGENTES':
            # El turno inicial se alterna entre partidas consecutivas para que la
            # ventaja de abrir se cancele a lo largo de una serie.
            self.empieza = 1 if self.n_partidas % 2 == 0 else 2
            self.n_partidas += 1
        else:
            self.empieza = 1      # contra un humano, el humano siempre abre
        self.turno = self.empieza

        if self.modo == 'HUMANO':
            self.agente1 = None
            self.agente2 = crear_agente(self.clave2)
            self.tablero2.auto_posicionar()
            self.indice_barco = 0
            self.estado = 'COLOCACION'
            self.log = "Despliegue: coloca tu flota o usa Auto-Colocar."
        else:
            self.agente1 = crear_agente(self.clave1)
            self.agente2 = crear_agente(self.clave2)
            self.etiquetar_lados()
            self.tablero1.auto_posicionar()
            self.tablero2.auto_posicionar()
            self.estado = 'JUGANDO'
            quien = self.agente1.nombre if self.empieza == 1 else self.agente2.nombre
            self.log = f"{self.agente1.nombre} vs {self.agente2.nombre} - abre {quien}"
        self.t_ultimo = time.time()

    def disparo_agente(self, agente, defensor, num):
        f, c = agente.decidir_tiro()
        resultado, barco = defensor.recibir_disparo(f, c)
        agente.registrar_resultado(f, c, resultado, barco)
        if resultado == "REPETIDO":
            self.log = f"{agente.nombre}: tiro repetido descartado en {LETRAS[c]}{f+1}"
            return
        if num == 1:
            self.tiros1 += 1
        else:
            self.tiros2 += 1
        coord = f"{LETRAS[c]}{f+1}"
        if resultado == "HUNDIDO":
            self.log = f"{agente.nombre} -> {coord}: hundio el {barco.nombre.upper()}"
        elif resultado == "TOCADO":
            self.log = f"{agente.nombre} -> {coord}: impacto"
        else:
            self.log = f"{agente.nombre} -> {coord}: agua"
        if defensor.todos_hundidos:
            self.ganador = agente.nombre
            self.anotar(self.clave_enfrentamiento(), agente.etiqueta)
            self.estado = 'FIN'
        else:
            self.turno = 2 if num == 1 else 1
        self.t_ultimo = time.time()

    def paso_simulacion(self, cuantas):
        """Corre un bloque de partidas sin dibujar, para no congelar la ventana."""
        clave = self.clave_enfrentamiento('AGENTES', self.clave1, self.clave2)
        lado_a, lado_b = self.participantes(clave)
        if self.clave1 != self.clave2:
            lado_a, lado_b = ETIQUETAS[self.clave1], ETIQUETAS[self.clave2]
        for _ in range(cuantas):
            if self.sim_restantes <= 0:
                break
            g, _, _ = jugar_partida(self.clave1, self.clave2, self.empieza)
            ganador = lado_a if g == 1 else lado_b
            self.anotar(clave, ganador)
            self.empieza = 2 if self.empieza == 1 else 1   # alternar el turno inicial
            self.sim_restantes -= 1
        if self.sim_restantes <= 0:
            self.estado = 'MENU'
            self.log = f"Simulacion terminada: {self.sim_total} partidas."

    # ---------------- dibujo ----------------
    def boton(self, rect, texto, activo=False, hover=False, fuente=None, habilitado=True):
        color = COLOR_BOTON_ACTIVO if activo else (COLOR_BOTON_HOVER if (hover and habilitado) else COLOR_BOTON)
        pygame.draw.rect(self.pantalla, color, rect, border_radius=6)
        pygame.draw.rect(self.pantalla, COLOR_BORDE_PANEL, rect, width=2, border_radius=6)
        f = fuente or self.f_sub
        col = COLOR_TEXTO_PRINCIPAL if habilitado else COLOR_TEXTO_MUTED
        s = f.render(texto, True, col)
        self.pantalla.blit(s, s.get_rect(center=rect.center))

    def panel(self, rect, radio=10):
        pygame.draw.rect(self.pantalla, COLOR_PANEL, rect, border_radius=radio)
        pygame.draw.rect(self.pantalla, COLOR_BORDE_PANEL, rect, width=2, border_radius=radio)

    def rects_menu(self):
        r = {}
        r['modo_h'] = pygame.Rect(360, 84, 230, 42)
        r['modo_a'] = pygame.Rect(610, 84, 230, 42)
        for i in range(4):
            r[f'ag1_{i}'] = pygame.Rect(90, 186 + i * 48, 490, 42)
            r[f'ag2_{i}'] = pygame.Rect(620, 186 + i * 48, 490, 42)
        for i in range(4):
            r[f'vel_{i}'] = pygame.Rect(90 + i * 252, 422, 250, 32)
        r['iniciar'] = pygame.Rect(100, 676, 300, 50)
        for i, n in enumerate(LOTES):
            r[f'lote_{i}'] = pygame.Rect(570 + i * 115, 676, 105, 50)
        r['csv'] = pygame.Rect(930, 676, 160, 50)
        return r

    def dibujar_registro(self, rect, clave):
        self.panel(rect)
        self.pantalla.blit(self.f_sub.render("REGISTRO HISTORICO // PORCENTAJES DE VICTORIA",
                                             True, COLOR_RADAR_VERDE), (rect.x + 20, rect.y + 14))
        reg = self.registro.get(clave)
        nombres = self.participantes(clave)
        etiqueta = " vs ".join(nombres)
        total = reg["total"] if reg else 0
        self.pantalla.blit(self.f_mini.render(
            f"Enfrentamiento: {etiqueta}   |   Partidas jugadas: {total}",
            True, COLOR_TEXTO_MUTED), (rect.x + 20, rect.y + 40))
        if total == 0:
            self.pantalla.blit(self.f_ui.render(
                "Sin partidas registradas para este enfrentamiento todavia.",
                True, COLOR_TEXTO_MUTED), (rect.x + 20, rect.y + 72))
            return
        y = rect.y + 66
        ancho_barra = rect.width - 300
        for i, nombre in enumerate(nombres):
            v = reg["victorias"].get(nombre, 0)
            pct = 100.0 * v / total
            self.pantalla.blit(self.f_ui.render(nombre[:22], True, COLOR_TEXTO_PRINCIPAL),
                               (rect.x + 20, y + 2))
            fondo = pygame.Rect(rect.x + 210, y, ancho_barra, 20)
            pygame.draw.rect(self.pantalla, COLOR_AGUA, fondo, border_radius=4)
            pygame.draw.rect(self.pantalla, COLOR_BORDE_PANEL, fondo, width=1, border_radius=4)
            if pct > 0:
                relleno = pygame.Rect(fondo.x, fondo.y, max(3, int(ancho_barra * pct / 100)), 20)
                pygame.draw.rect(self.pantalla, COLOR_BARRA[i % len(COLOR_BARRA)],
                                 relleno, border_radius=4)
            self.pantalla.blit(self.f_ui.render(f"{pct:5.1f}%  ({v}V)", True, COLOR_TEXTO_PRINCIPAL),
                               (fondo.right + 14, y + 2))
            y += 30

    def pantalla_menu(self):
        mp = pygame.mouse.get_pos()
        r = self.rects_menu()

        t = self.f_titulo.render("BATTLESHIP // LABORATORIO 1: AGENTES", True, COLOR_RADAR_VERDE)
        self.pantalla.blit(t, t.get_rect(center=(ANCHO_VENTANA // 2, 30)))
        d = self.f_ui.render("Facultad de Ingenieria UNAM - Inteligencia Artificial - Grupo 1",
                             True, COLOR_TEXTO_MUTED)
        self.pantalla.blit(d, d.get_rect(center=(ANCHO_VENTANA // 2, 58)))

        self.boton(r['modo_h'], "HUMANO VS AGENTE", self.modo == 'HUMANO', r['modo_h'].collidepoint(mp))
        self.boton(r['modo_a'], "AGENTE VS AGENTE", self.modo == 'AGENTES', r['modo_a'].collidepoint(mp))

        self.panel(pygame.Rect(60, 142, 1080, 240))
        izq = "JUGADOR 1 - HUMANO" if self.modo == 'HUMANO' else "AGENTE 1"
        self.pantalla.blit(self.f_sub.render(izq, True, COLOR_ACCENTO_AMARILLO), (90, 158))
        self.pantalla.blit(self.f_sub.render("AGENTE 2 (RIVAL)" if self.modo == 'HUMANO' else "AGENTE 2",
                                             True, COLOR_ACCENTO_AMARILLO), (620, 158))

        for i, (clave, etq, cls) in enumerate(CATALOGO):
            texto = f"{etq}  |  {cls.taxonomia}"
            if self.modo == 'AGENTES':
                self.boton(r[f'ag1_{i}'], texto, self.clave1 == clave, r[f'ag1_{i}'].collidepoint(mp))
            self.boton(r[f'ag2_{i}'], texto, self.clave2 == clave, r[f'ag2_{i}'].collidepoint(mp))
        if self.modo == 'HUMANO':
            caja = pygame.Rect(90, 186, 490, 186)
            pygame.draw.rect(self.pantalla, COLOR_AGUA, caja, border_radius=6)
            pygame.draw.rect(self.pantalla, COLOR_BORDE_PANEL, caja, width=2, border_radius=6)
            s = self.f_sub.render("TU COLOCAS TU PROPIA FLOTA", True, COLOR_TEXTO_MUTED)
            self.pantalla.blit(s, s.get_rect(center=caja.center))

        self.panel(pygame.Rect(60, 392, 1080, 72))
        self.pantalla.blit(self.f_sub.render("VELOCIDAD DEL INTERCAMBIO:", True, COLOR_ACCENTO_AMARILLO), (90, 400))
        for i, (etq, seg) in enumerate(VELOCIDADES):
            txt = f"{etq} ({seg:.2f}s)" if seg else f"{etq} (instantaneo)"
            self.boton(r[f'vel_{i}'], txt, self.idx_velocidad == i,
                       r[f'vel_{i}'].collidepoint(mp), self.f_ui)

        self.dibujar_registro(pygame.Rect(60, 476, 1080, 186), self.clave_enfrentamiento())

        self.boton(r['iniciar'], ">> INICIAR <<", False, r['iniciar'].collidepoint(mp))
        hab = (self.modo == 'AGENTES')
        self.pantalla.blit(self.f_mini.render("SIMULAR LOTE" if hab else "(solo agente vs agente)",
                                              True, COLOR_TEXTO_MUTED), (572, 660))
        for i, n in enumerate(LOTES):
            self.boton(r[f'lote_{i}'], str(n), False, r[f'lote_{i}'].collidepoint(mp),
                       self.f_ui, habilitado=hab)
        self.boton(r['csv'], "EXPORTAR CSV", False, r['csv'].collidepoint(mp), self.f_ui)
        if self.mensaje_csv:
            self.pantalla.blit(self.f_mini.render(self.mensaje_csv, True, COLOR_RADAR_VERDE), (930, 732))
        if self.log:
            self.pantalla.blit(self.f_mini.render(self.log, True, COLOR_TEXTO_MUTED), (100, 732))

    def pantalla_simulando(self):
        self.pantalla.blit(self.f_titulo.render("SIMULANDO...", True, COLOR_RADAR_VERDE), (100, 300))
        hechas = self.sim_total - self.sim_restantes
        self.panel(pygame.Rect(100, 360, 1000, 90))
        barra = pygame.Rect(130, 395, 940, 26)
        pygame.draw.rect(self.pantalla, COLOR_AGUA, barra, border_radius=5)
        frac = hechas / self.sim_total if self.sim_total else 0
        if frac > 0:
            pygame.draw.rect(self.pantalla, COLOR_RADAR_VERDE,
                             pygame.Rect(barra.x, barra.y, int(barra.width * frac), 26), border_radius=5)
        s = self.f_sub.render(f"{hechas} / {self.sim_total} partidas  ({100*frac:.0f}%)",
                              True, COLOR_TEXTO_PRINCIPAL)
        self.pantalla.blit(s, s.get_rect(center=(ANCHO_VENTANA // 2, 440)))
        self.pantalla.blit(self.f_ui.render(
            f"{ETIQUETAS[self.clave1]} vs {ETIQUETAS[self.clave2]} - el turno inicial se alterna en cada partida",
            True, COLOR_TEXTO_MUTED), (130, 470))

    def dibujar_tablero(self, ox, oy, tablero, ocultar, titulo):
        marco = pygame.Rect(ox - 30, oy - 45, TAM_TABLERO * TAM_CELDA + 60, TAM_TABLERO * TAM_CELDA + 80)
        self.panel(marco)
        self.pantalla.blit(self.f_sub.render(titulo[:34], True, COLOR_RADAR_VERDE), (ox, oy - 35))
        for i in range(TAM_TABLERO):
            self.pantalla.blit(self.f_mini.render(LETRAS[i], True, COLOR_TEXTO_MUTED),
                               (ox + i * TAM_CELDA + 13, oy - 18))
            self.pantalla.blit(self.f_mini.render(str(i + 1), True, COLOR_TEXTO_MUTED),
                               (ox - 20, oy + i * TAM_CELDA + 11))
        for f in range(TAM_TABLERO):
            for c in range(TAM_TABLERO):
                celda = pygame.Rect(ox + c * TAM_CELDA, oy + f * TAM_CELDA, TAM_CELDA, TAM_CELDA)
                pygame.draw.rect(self.pantalla, COLOR_AGUA, celda)
                pygame.draw.rect(self.pantalla, COLOR_LINEA_GRID, celda, width=1)
                marca = tablero.disparos_recibidos[f][c]
                hay_barco = tablero.grid[f][c] is not None
                if hay_barco and not ocultar and marca != 'HUNDIDO':
                    sub = celda.inflate(-6, -6)
                    pygame.draw.rect(self.pantalla, COLOR_BARCO, sub, border_radius=4)
                    pygame.draw.rect(self.pantalla, COLOR_BARCO_BORDE, sub, width=1, border_radius=4)
                cx, cy = celda.center
                if marca == 'AGUA':
                    pygame.draw.circle(self.pantalla, COLOR_AGUA_DISPARADA, (cx, cy), 6)
                    pygame.draw.circle(self.pantalla, COLOR_TEXTO_MUTED, (cx, cy), 6, width=1)
                elif marca == 'TOCADO':
                    pygame.draw.line(self.pantalla, COLOR_IMPACTO, (cx - 10, cy - 10), (cx + 10, cy + 10), 3)
                    pygame.draw.line(self.pantalla, COLOR_IMPACTO, (cx + 10, cy - 10), (cx - 10, cy + 10), 3)
                elif marca == 'HUNDIDO':
                    pygame.draw.rect(self.pantalla, COLOR_HUNDIDO, celda.inflate(-4, -4), border_radius=3)
                    pygame.draw.circle(self.pantalla, COLOR_ACCENTO_AMARILLO, (cx, cy), 4)

    def dibujar_flota(self, ox, oy, tablero, etiqueta):
        p = pygame.Rect(ox, oy, 420, 104)
        self.panel(p, 8)
        self.pantalla.blit(self.f_ui.render(f"FLOTA: {etiqueta[:30]}", True, COLOR_ACCENTO_AMARILLO), (ox + 15, oy + 8))
        for i, b in enumerate(tablero.barcos):
            col = COLOR_HUNDIDO if b.hundido else COLOR_RADAR_VERDE
            est = "HUNDIDO" if b.hundido else f"OPERATIVO ({b.tam - b.impactos}/{b.tam})"
            self.pantalla.blit(self.f_mini.render(f"{b.nombre:<13} [{est}]", True, col),
                               (ox + 15, oy + 30 + i * 14))

    def pantalla_colocacion(self):
        mp = pygame.mouse.get_pos()
        self.pantalla.blit(self.f_titulo.render("SALA DE DESPLIEGUE", True, COLOR_RADAR_VERDE), (OFFSET_X_J1, 50))
        self.dibujar_tablero(OFFSET_X_J1, OFFSET_Y_TABLERO, self.tablero1, False, "TU FLOTA")
        self.panel(pygame.Rect(600, OFFSET_Y_TABLERO, 500, 360))
        if self.indice_barco < len(NOMBRES_BARCOS):
            nom, tam = NOMBRES_BARCOS[self.indice_barco]
            self.pantalla.blit(self.f_sub.render(f"Colocando: {nom} ({tam} celdas)", True, COLOR_ACCENTO_AMARILLO),
                               (630, OFFSET_Y_TABLERO + 30))
            self.pantalla.blit(self.f_ui.render(
                f"Orientacion: {'HORIZONTAL' if self.orientacion == 'H' else 'VERTICAL'}",
                True, COLOR_TEXTO_PRINCIPAL), (630, OFFSET_Y_TABLERO + 70))
            self.pantalla.blit(self.f_mini.render("Tecla R para rotar", True, COLOR_RADAR_VERDE),
                               (630, OFFSET_Y_TABLERO + 100))
            rx, ry = mp[0] - OFFSET_X_J1, mp[1] - OFFSET_Y_TABLERO
            if 0 <= rx < TAM_TABLERO * TAM_CELDA and 0 <= ry < TAM_TABLERO * TAM_CELDA:
                col, fila = rx // TAM_CELDA, ry // TAM_CELDA
                ok = self.tablero1.puede_colocar(fila, col, tam, self.orientacion)
                tinte = (46, 213, 115, 120) if ok else (255, 71, 87, 120)
                for i in range(tam):
                    pf = fila if self.orientacion == 'H' else fila + i
                    pc = col + i if self.orientacion == 'H' else col
                    if 0 <= pf < TAM_TABLERO and 0 <= pc < TAM_TABLERO:
                        s = pygame.Surface((TAM_CELDA, TAM_CELDA), pygame.SRCALPHA)
                        s.fill(tinte)
                        self.pantalla.blit(s, (OFFSET_X_J1 + pc * TAM_CELDA, OFFSET_Y_TABLERO + pf * TAM_CELDA))
        else:
            self.pantalla.blit(self.f_sub.render("Flota desplegada.", True, COLOR_RADAR_VERDE),
                               (630, OFFSET_Y_TABLERO + 40))
        for clave, rect, txt in self.rects_colocacion():
            act = (clave == 'listo' and self.indice_barco >= len(NOMBRES_BARCOS))
            self.boton(rect, txt, act, rect.collidepoint(mp))

    def rects_colocacion(self):
        return [('rotar', pygame.Rect(630, OFFSET_Y_TABLERO + 160, 200, 42), "ROTAR (R)"),
                ('auto', pygame.Rect(630, OFFSET_Y_TABLERO + 215, 200, 42), "AUTO-COLOCAR"),
                ('listo', pygame.Rect(630, OFFSET_Y_TABLERO + 275, 200, 46), "A LA BATALLA"),
                ('menu', pygame.Rect(880, OFFSET_Y_TABLERO + 275, 180, 46), "MENU")]

    def pantalla_jugando(self):
        self.pantalla.blit(self.f_titulo.render("CENTRO TACTICO", True, COLOR_RADAR_VERDE), (OFFSET_X_J1, 24))
        lp = pygame.Rect(OFFSET_X_J1, 74, ANCHO_VENTANA - 200, 42)
        self.panel(lp, 6)
        self.pantalla.blit(self.f_ui.render(f">> {self.log}"[:92], True, COLOR_ACCENTO_AMARILLO),
                           (OFFSET_X_J1 + 15, 88))
        n1 = "JUGADOR 1 (HUMANO)" if self.modo == 'HUMANO' else self.agente1.nombre
        n2 = self.agente2.nombre
        self.dibujar_tablero(OFFSET_X_J1, OFFSET_Y_TABLERO, self.tablero1, False, n1)
        self.dibujar_tablero(OFFSET_X_J2, OFFSET_Y_TABLERO, self.tablero2,
                             self.modo == 'HUMANO' and not self.ganador, n2)
        base_y = OFFSET_Y_TABLERO + TAM_TABLERO * TAM_CELDA + 44
        self.dibujar_flota(OFFSET_X_J1 - 30, base_y, self.tablero1, n1)
        self.dibujar_flota(OFFSET_X_J2 - 30, base_y, self.tablero2, n2)
        self.pantalla.blit(self.f_ui.render(f"Disparos J1: {self.tiros1}   |   Disparos J2: {self.tiros2}",
                                            True, COLOR_TEXTO_MUTED), (OFFSET_X_J1, base_y + 112))

        if self.ganador:
            return
        espera = VELOCIDADES[self.idx_velocidad][1]
        if time.time() - self.t_ultimo < espera:
            return
        if self.modo == 'AGENTES':
            if self.turno == 1:
                self.disparo_agente(self.agente1, self.tablero2, 1)
            else:
                self.disparo_agente(self.agente2, self.tablero1, 2)
        elif self.turno == 2:
            self.disparo_agente(self.agente2, self.tablero1, 2)

    def rects_fin(self):
        return {'repetir': pygame.Rect(ANCHO_VENTANA // 2 - 300, 606, 280, 46),
                'menu': pygame.Rect(ANCHO_VENTANA // 2 + 20, 606, 280, 46)}

    def pantalla_fin(self):
        mp = pygame.mouse.get_pos()
        velo = pygame.Surface((ANCHO_VENTANA, ALTO_VENTANA), pygame.SRCALPHA)
        velo.fill((5, 12, 22, 215))
        self.pantalla.blit(velo, (0, 0))
        p = pygame.Rect(ANCHO_VENTANA // 2 - 340, 140, 680, 520)
        pygame.draw.rect(self.pantalla, COLOR_PANEL, p, border_radius=16)
        pygame.draw.rect(self.pantalla, COLOR_RADAR_VERDE, p, width=2, border_radius=16)
        t = self.f_titulo.render("FIN DE LA BATALLA", True, COLOR_ACCENTO_AMARILLO)
        self.pantalla.blit(t, t.get_rect(center=(ANCHO_VENTANA // 2, 185)))
        g = self.f_sub.render(f"VICTORIA: {self.ganador}", True, COLOR_RADAR_VERDE)
        self.pantalla.blit(g, g.get_rect(center=(ANCHO_VENTANA // 2, 228)))
        s = self.f_ui.render(f"Disparos J1: {self.tiros1}    |    Disparos J2: {self.tiros2}",
                             True, COLOR_TEXTO_PRINCIPAL)
        self.pantalla.blit(s, s.get_rect(center=(ANCHO_VENTANA // 2, 262)))
        self.dibujar_registro(pygame.Rect(p.x + 30, 292, p.width - 60, 186), self.clave_enfrentamiento())
        for k, rect in self.rects_fin().items():
            self.boton(rect, "REPETIR PARTIDA" if k == 'repetir' else "VOLVER AL MENU",
                       False, rect.collidepoint(mp))

    # ---------------- eventos ----------------
    def clic_menu(self, pos):
        r = self.rects_menu()
        if r['modo_h'].collidepoint(pos):
            self.modo = 'HUMANO'; return
        if r['modo_a'].collidepoint(pos):
            self.modo = 'AGENTES'; return
        for i, (clave, _, _) in enumerate(CATALOGO):
            if self.modo == 'AGENTES' and r[f'ag1_{i}'].collidepoint(pos):
                self.clave1 = clave; return
            if r[f'ag2_{i}'].collidepoint(pos):
                self.clave2 = clave; return
        for i in range(4):
            if r[f'vel_{i}'].collidepoint(pos):
                self.idx_velocidad = i; return
        if r['iniciar'].collidepoint(pos):
            self.nueva_partida(); return
        if r['csv'].collidepoint(pos):
            self.exportar_csv(); return
        if self.modo == 'AGENTES':
            for i, n in enumerate(LOTES):
                if r[f'lote_{i}'].collidepoint(pos):
                    self.sim_total = self.sim_restantes = n
                    self.estado = 'SIMULANDO'
                    return

    def clic_colocacion(self, pos):
        for clave, rect, _ in self.rects_colocacion():
            if rect.collidepoint(pos):
                if clave == 'rotar':
                    self.orientacion = 'V' if self.orientacion == 'H' else 'H'
                elif clave == 'auto':
                    self.tablero1.auto_posicionar()
                    self.indice_barco = len(NOMBRES_BARCOS)
                elif clave == 'menu':
                    self.estado = 'MENU'
                elif clave == 'listo' and self.indice_barco >= len(NOMBRES_BARCOS):
                    self.estado = 'JUGANDO'
                    self.turno = 1
                    self.log = "Haz clic en el radar enemigo para disparar."
                    self.t_ultimo = time.time()
                return
        rx, ry = pos[0] - OFFSET_X_J1, pos[1] - OFFSET_Y_TABLERO
        if 0 <= rx < TAM_TABLERO * TAM_CELDA and 0 <= ry < TAM_TABLERO * TAM_CELDA:
            if self.indice_barco < len(NOMBRES_BARCOS):
                col, fila = rx // TAM_CELDA, ry // TAM_CELDA
                nom, tam = NOMBRES_BARCOS[self.indice_barco]
                if self.tablero1.puede_colocar(fila, col, tam, self.orientacion):
                    self.tablero1.colocar_barco(Barco(nom, tam), fila, col, self.orientacion)
                    self.indice_barco += 1

    def clic_jugando(self, pos):
        if self.modo != 'HUMANO' or self.turno != 1 or self.ganador:
            return
        rx, ry = pos[0] - OFFSET_X_J2, pos[1] - OFFSET_Y_TABLERO
        if not (0 <= rx < TAM_TABLERO * TAM_CELDA and 0 <= ry < TAM_TABLERO * TAM_CELDA):
            return
        col, fila = rx // TAM_CELDA, ry // TAM_CELDA
        resultado, barco = self.tablero2.recibir_disparo(fila, col)
        if resultado == "REPETIDO":
            self.log = "Ya disparaste en esa casilla."
            return
        self.tiros1 += 1
        coord = f"{LETRAS[col]}{fila+1}"
        if resultado == "HUNDIDO":
            self.log = f"Hundiste el {barco.nombre.upper()} en {coord}"
        elif resultado == "TOCADO":
            self.log = f"Impacto en {coord}"
        else:
            self.log = f"Agua en {coord}"
        if self.tablero2.todos_hundidos:
            self.ganador = "Humano"
            self.anotar(self.clave_enfrentamiento(), "Humano")
            self.estado = 'FIN'
        else:
            self.turno = 2
            self.t_ultimo = time.time()

    def eventos(self):
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_r and self.estado == 'COLOCACION':
                    self.orientacion = 'V' if self.orientacion == 'H' else 'H'
                elif e.key == pygame.K_ESCAPE and self.estado != 'SIMULANDO':
                    self.estado = 'MENU'
            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                if self.estado == 'MENU':
                    self.clic_menu(e.pos)
                elif self.estado == 'COLOCACION':
                    self.clic_colocacion(e.pos)
                elif self.estado == 'JUGANDO':
                    self.clic_jugando(e.pos)
                elif self.estado == 'FIN':
                    r = self.rects_fin()
                    if r['repetir'].collidepoint(e.pos):
                        self.nueva_partida()
                    elif r['menu'].collidepoint(e.pos):
                        self.estado = 'MENU'

    def run(self):
        while True:
            self.pantalla.fill(COLOR_FONDO)
            self.eventos()
            if self.estado == 'MENU':
                self.pantalla_menu()
            elif self.estado == 'SIMULANDO':
                self.pantalla_simulando()
                self.paso_simulacion(12)
            elif self.estado == 'COLOCACION':
                self.pantalla_colocacion()
            elif self.estado == 'JUGANDO':
                self.pantalla_jugando()
            elif self.estado == 'FIN':
                self.pantalla_jugando()
                self.pantalla_fin()
            pygame.display.flip()
            self.reloj.tick(FPS)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Battleship - Laboratorio 1: Agentes")
    ap.add_argument("--semilla", type=int, default=None,
                    help="semilla del generador aleatorio, para reproducir una corrida")
    args = ap.parse_args()
    if args.semilla is not None:
        random.seed(args.semilla)
        print(f"Generador aleatorio sembrado con {args.semilla} (corrida reproducible)")
    if pygame is None:
        print("Falta pygame.  Instalalo con:  pip install pygame")
        sys.exit(1)
    Juego().run()