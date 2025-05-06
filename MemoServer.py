#!/usr/bin/env python3
import socket
import threading
import random
import time
import json

# Variables globales
HOST = "127.0.0.1"
PORT = 65432
buffer_size = 1024
lock = threading.RLock()  # Para proteger acceso concurrente
conexiones_clientes = {}  # diccionario {addr_str: conn}
hilos_clientes = {}       # diccionario {addr_str: thread}
puntuaciones = {}         # diccionario {addr_str: puntos}
palabras_disponibles = [
    "árbol", "casa", "perro", "gato", "sol", "luna", "mar", "río",
    "montaña", "bosque", "nube", "estrella", "flor", "pájaro", "libro", "pluma",
    "avión", "tren", "camino", "jardín", "fuego", "agua", "tierra", "viento",
    "puerta", "ventana", "mesa", "silla", "reloj", "lápiz", "papel", "tijera",
    "manzana", "naranja", "plátano", "uva"
]

# Variables del juego
dificultad = "1"
filas = 4
columnas = 4
num_pares = 8
tablero = []
tablero_visible = []
casillas_destapadas = 0
tiempo_inicio = time.time()
juego_activo = True

# Variables para control de turnos
turno_actual = None  # Almacena el cliente que tiene el turno actualmente
orden_turnos = []    # Lista ordenada de jugadores
condiciones_clientes = {}  # Condiciones para cada cliente {addr_str: threading.Condition()}

def inicializar_tablero():
    global tablero, tablero_visible
    
    with lock:
        # Crear tablero con pares de palabras
        palabras_juego = random.sample(palabras_disponibles, num_pares)
        cartas = palabras_juego * 2
        random.shuffle(cartas)
        
        # Crear el tablero como una matriz
        tablero = []
        for i in range(filas):
            fila = []
            for j in range(columnas):
                if i*columnas + j < len(cartas):
                    fila.append(cartas[i*columnas + j])
                else:
                    fila.append("")
            tablero.append(fila)
        
        # Crear tablero visible para los jugadores (inicialmente todas las cartas ocultas)
        tablero_visible = []
        for i in range(filas):
            fila = []
            for j in range(columnas):
                fila.append("?")
            tablero_visible.append(fila)

def imprimir_tablero_servidor():
    """Imprime el tablero completo con todas las casillas destapadas (solo para el servidor)"""
    print("\nTablero del servidor (todas las casillas):")
    print("  ", end="")
    for j in range(columnas):
        print(f" {j} ", end="")
    print()
    
    for i in range(filas):
        print(f"{i} ", end="")
        for j in range(columnas):
            contenido = tablero[i][j]
            print(f"[{contenido[:3]:3}]", end="")
        print()
    
    print("\nTablero visible para los jugadores:")
    print("  ", end="")
    for j in range(columnas):
        print(f" {j} ", end="")
    print()
    
    for i in range(filas):
        print(f"{i} ", end="")
        for j in range(columnas):
            contenido = tablero_visible[i][j]
            if contenido == "?":
                print("[?  ]", end="")
            else:
                print(f"[{contenido[:3]:3}]", end="")
        print()
        
    print("\nPuntuaciones:")
    for addr_str, puntos in puntuaciones.items():
        print(f"Jugador {addr_str}: {puntos} puntos")
    
    if turno_actual:
        print(f"\nTurno actual: {turno_actual}")
    print(f"Orden de turnos: {orden_turnos}")

def procesar_jugada(fila1, col1, fila2, col2, cliente_ip, cliente_puerto):
    global tablero_visible, casillas_destapadas, juego_activo
    
    with lock:
        # Convertir dirección a string
        cliente_addr_str = f"{cliente_ip}:{cliente_puerto}"
        
        # Verificar si el juego sigue activo
        if not juego_activo:
            return False, "El juego ha terminado", None, None
            
        # Verificar si las coordenadas son válidas
        if not (0 <= fila1 < filas and 0 <= col1 < columnas and 
                0 <= fila2 < filas and 0 <= col2 < columnas):
            return False, "Coordenadas inválidas", None, None
        
        # Verificar si las casillas ya están destapadas
        if tablero_visible[fila1][col1] != "?" or tablero_visible[fila2][col2] != "?":
            return False, "Casilla(s) ya destapada(s)", None, None
        
        # Obtener el contenido de las casillas
        contenido1 = tablero[fila1][col1]
        contenido2 = tablero[fila2][col2]
        
        # Verificar si las cartas son iguales
        acierto = contenido1 == contenido2
        
        # Actualizar el tablero visible permanentemente si hay acierto
        if acierto:
            tablero_visible[fila1][col1] = contenido1
            tablero_visible[fila2][col2] = contenido2
            # Sumar punto al cliente
            if cliente_addr_str not in puntuaciones:
                puntuaciones[cliente_addr_str] = 0
            puntuaciones[cliente_addr_str] += 1
            casillas_destapadas += 2
            
            # Verificar si el juego ha terminado
            if casillas_destapadas >= (filas * columnas):
                juego_activo = False
        
        return acierto, contenido1, contenido2, cliente_addr_str

def cambiar_turno(mantener_turno=False):
    global turno_actual
    
    with lock:
        # Si no hay jugadores, no hay turno
        if not orden_turnos:
            turno_actual = None
            return
            
        # Si el jugador acertó, mantiene su turno
        if mantener_turno and turno_actual in orden_turnos:
            print(f"Jugador {turno_actual} acertó y mantiene su turno.")
            return
            
        # Obtener el índice del turno actual
        try:
            indice_actual = orden_turnos.index(turno_actual)
        except ValueError:
            indice_actual = -1
            
        # Calcular el siguiente turno
        if indice_actual >= 0 and indice_actual < len(orden_turnos) - 1:
            indice_siguiente = indice_actual + 1
        else:
            indice_siguiente = 0
            
        # Establecer siguiente turno
        turno_actual = orden_turnos[indice_siguiente]
        print(f"Cambiando turno al jugador {turno_actual}")
        
        # Notificar a todos los clientes sobre el cambio
        enviar_a_todos(f"TURNO:{turno_actual}")
        
        # Despertar al cliente que tiene el turno
        if turno_actual in condiciones_clientes:
            condiciones_clientes[turno_actual].notify_all()

def obtener_tablero_visible_json():
    with lock:
        return json.dumps(tablero_visible)
        
def obtener_puntuaciones_json():
    with lock:
        return json.dumps(puntuaciones)

def agregar_cliente(conn, cliente_ip, cliente_puerto):
    global turno_actual, orden_turnos
    
    with lock:
        cliente_addr_str = f"{cliente_ip}:{cliente_puerto}"
        conexiones_clientes[cliente_addr_str] = conn
        puntuaciones[cliente_addr_str] = 0
        
        # Crear una condición para este cliente
        condiciones_clientes[cliente_addr_str] = threading.Condition(lock)
        
        # Añadir cliente al orden de turnos
        orden_turnos.append(cliente_addr_str)
        
        # Si es el primer cliente, darle el primer turno
        if turno_actual is None:
            turno_actual = cliente_addr_str
            print(f"Primer cliente conectado. Asignando turno a {turno_actual}")
        
def eliminar_cliente(cliente_ip, cliente_puerto):
    global turno_actual, orden_turnos
    
    with lock:
        cliente_addr_str = f"{cliente_ip}:{cliente_puerto}"
        era_su_turno = (cliente_addr_str == turno_actual)
        
        if cliente_addr_str in conexiones_clientes:
            del conexiones_clientes[cliente_addr_str]
        if cliente_addr_str in hilos_clientes:
            del hilos_clientes[cliente_addr_str]
        if cliente_addr_str in puntuaciones:
            del puntuaciones[cliente_addr_str]
        if cliente_addr_str in condiciones_clientes:
            del condiciones_clientes[cliente_addr_str]
        
        # Quitar del orden de turnos
        if cliente_addr_str in orden_turnos:
            orden_turnos.remove(cliente_addr_str)
            
        # Si era su turno, pasar al siguiente
        if era_su_turno and orden_turnos:
            cambiar_turno(False)
            
def registrar_hilo(cliente_ip, cliente_puerto, hilo):
    with lock:
        cliente_addr_str = f"{cliente_ip}:{cliente_puerto}"
        hilos_clientes[cliente_addr_str] = hilo

def obtener_ganador():
    with lock:
        if not puntuaciones:
            return "desconocido:0", 0
        
        max_puntos = 0
        ganador = None
        
        for addr_str, puntos in puntuaciones.items():
            if puntos > max_puntos:
                max_puntos = puntos
                ganador = addr_str
        
        if ganador is None:
            ganador = "desconocido:0"
            
        return ganador, max_puntos

def hay_empate():
    with lock:
        if not puntuaciones:
            return False
        
        valores = list(puntuaciones.values())
        if len(valores) < 2:
            return False
            
        max_valor = max(valores)
        return valores.count(max_valor) > 1

def enviar_a_todos(mensaje, excluir_ip=None, excluir_puerto=None):
    with lock:
        clientes_a_eliminar = []
        excluir_addr_str = None
        
        if excluir_ip is not None and excluir_puerto is not None:
            excluir_addr_str = f"{excluir_ip}:{excluir_puerto}"
            
        for addr_str, conn in conexiones_clientes.items():
            if excluir_addr_str and addr_str == excluir_addr_str:
                continue
                    
            try:
                conn.sendall(mensaje.encode())
            except:
                # Marcar para eliminación posterior
                clientes_a_eliminar.append(addr_str)
        
        # Eliminar clientes después de la iteración
        for addr_str in clientes_a_eliminar:
            ip, puerto = addr_str.split(":")
            eliminar_cliente(ip, int(puerto))

# Función para verificar el estado del cliente (ping)
def ping_cliente(cliente_conn, cliente_ip, cliente_puerto):
    global juego_activo
    while juego_activo:
        try:
            # Enviar ping cada 5 segundos
            time.sleep(5)
            cliente_conn.sendall("PING".encode())
        except:
            # Si falla el ping, el cliente está desconectado
            print(f"Cliente {cliente_ip}:{cliente_puerto} desconectado (ping fallido)")
            eliminar_cliente(cliente_ip, cliente_puerto)
            # Notificar a todos los demás clientes
            enviar_a_todos(f"DESCONEXION:{cliente_ip}:{cliente_puerto}", cliente_ip, cliente_puerto)
            # Imprimir el tablero actualizado después de la desconexión
            if len(conexiones_clientes) > 0:  # Solo si quedan jugadores
                imprimir_tablero_servidor()
            break
    
# Función que maneja cada cliente en un hilo separado
def manejar_cliente(client_conn, client_addr):
    global juego_activo
    
    # Extraer IP y puerto del cliente
    client_ip = client_addr[0]
    client_port = client_addr[1]
    cliente_addr_str = f"{client_ip}:{client_port}"
    
    try:
        # Enviamos información de configuración primero
        info_inicial = f"CONFIG:{dificultad}:{filas}:{columnas}"
        client_conn.sendall(info_inicial.encode())
        
        # Añadir el cliente a la lista de conexiones
        agregar_cliente(client_conn, client_ip, client_port)
        
        # Iniciar hilo para ping
        ping_thread = threading.Thread(target=ping_cliente, args=(client_conn, client_ip, client_port))
        ping_thread.daemon = True
        ping_thread.start()

        # Notificar a todos que un nuevo cliente se ha conectado
        enviar_a_todos(f"CONEXION:{client_ip}:{client_port}", client_ip, client_port)
        
        # Notificar sobre el turno actual con manejo de errores
        try:
            if turno_actual:
                client_conn.sendall(f"TURNO:{turno_actual}".encode())
        except Exception as e:
            print(f"Error al enviar turno a {cliente_addr_str}: {e}")
            return

        print(f"Cliente conectado desde {client_ip}:{client_port}")
        while juego_activo:
            try:
                data = client_conn.recv(buffer_size).decode()
                if not data:
                    break
                
                print(f"Datos recibidos de {client_ip}:{client_port}: {data}")
                
                # No imprimir mensajes de PONG para mantener la consola limpia
                if data == "PONG":
                    continue
                
                # Procesar la jugada del formato JUGAR:fila1,col1:fila2,col2
                if data.startswith("JUGAR:"):
                    # Verificar si es el turno de este cliente
                    with lock:
                        if turno_actual != cliente_addr_str:
                            # No es su turno, enviar mensaje de error
                            try:
                                client_conn.sendall(f"ESPERAR:{turno_actual}".encode())
                            except Exception as e:
                                print(f"Error al enviar mensaje de espera: {e}")
                                break
                            continue
                    
                    # Es su turno, procesar la jugada
                    partes = data.split(":")
                    coord1 = partes[1].split(",")
                    coord2 = partes[2].split(",")
                    
                    fila1, col1 = int(coord1[0]), int(coord1[1])
                    fila2, col2 = int(coord2[0]), int(coord2[1])
                    
                    # Procesar la jugada
                    acierto, contenido1, contenido2, jugador_addr_str = procesar_jugada(
                        fila1, col1, fila2, col2, client_ip, client_port
                    )
                    
                    if isinstance(acierto, bool) and contenido1 is None:
                        # Error en la jugada
                        try:
                            respuesta = f"ERROR:{contenido2}"
                            client_conn.sendall(respuesta.encode())
                        except Exception as e:
                            print(f"Error al enviar respuesta: {e}")
                            break
                        continue
                    
                    # Preparar información para broadcast
                    puntuaciones_json = obtener_puntuaciones_json()
                    tablero_json = obtener_tablero_visible_json()
                    
                    # Enviar resultado a todos - JUGADA:direccionIP:puerto:fila1,col1:palabra1:fila2,col2:palabra2:acierto:tablero:puntuaciones
                    respuesta = f"JUGADA:{client_ip}:{client_port}:{fila1},{col1}:{contenido1}:{fila2},{col2}:{contenido2}:{1 if acierto else 0}:{tablero_json}:{puntuaciones_json}"
                    enviar_a_todos(respuesta)
                    
                    # Imprimir el tablero completo después de cada jugada (solo visible en el servidor)
                    imprimir_tablero_servidor()
                    
                    # Cambiar turno basado en si hubo acierto
                    cambiar_turno(acierto)  # Si acierto=True, mantiene turno
                    
                    # Verificar si el juego ha terminado
                    if not juego_activo:
                        # Determinar ganador
                        ganador, max_puntos = obtener_ganador()
                        hay_empate_result = hay_empate()
                        
                        tiempo_fin = time.time()
                        duracion = tiempo_fin - tiempo_inicio
                        
                        if hay_empate_result:
                            mensaje_fin = f"FIN:EMPATE:{duracion:.1f}:{max_puntos}:COMPLETADO"
                        else:
                            # Ganador ya es un string en formato "ip:puerto"
                            ganador_partes = ganador.split(":")
                            ganador_ip = ganador_partes[0]
                            ganador_puerto = ganador_partes[1]
                            mensaje_fin = f"FIN:{ganador_ip}:{ganador_puerto}:{duracion:.1f}:{max_puntos}:COMPLETADO"
                        
                        # Enviar mensaje de fin a todos los clientes
                        enviar_a_todos(mensaje_fin)
                        
                        # Imprimir resumen final del juego
                        print("\n¡JUEGO TERMINADO!")
                        print(f"Duración total: {duracion:.2f} segundos")
                        
                        if hay_empate_result:
                            print("El juego terminó en EMPATE")
                        else:
                            print(f"GANADOR: Jugador {ganador} con {max_puntos} puntos")
                        
                        print("\nPuntuaciones finales:")
                        for addr_str, puntos in puntuaciones.items():
                            print(f"Jugador {addr_str}: {puntos} puntos")
                        
                        # Cerrar todas las conexiones y terminar
                        print("\nCerrando todas las conexiones...")
                        for addr_str, conn in list(conexiones_clientes.items()):
                            try:
                                # Enviar mensaje de despedida antes de cerrar
                                conn.sendall("DESPEDIDA:El servidor ha terminado la partida".encode())
                                conn.close()
                            except:
                                pass
                        
                        # Cerrar el socket del servidor
                        try:
                            servidor_socket.close()
                        except:
                            pass
                        
                        # Esperar un momento para que los mensajes lleguen
                        time.sleep(1)
                        
                        # Terminar el programa con código de salida 0 (éxito)
                        print("¡Gracias por jugar! El servidor se cerrará.")
                        
                        # Forzar la terminación del programa, incluyendo todos los hilos
                        import os
                        os._exit(0)  # Esta es una manera más drástica de terminar que sys.exit()
                else:
                    print(f"Comando desconocido de {client_ip}:{client_port}: {data}")

            except ConnectionResetError:
                print(f"Conexión cerrada por el cliente {client_ip}:{client_port}")
                break
            except Exception as e:
                print(f"Error con cliente {client_ip}:{client_port}: {e}")
                break

    except Exception as e:
        print(f"Error en hilo cliente {client_ip}:{client_port}: {e}")
    finally:
        # Al terminar el bucle, el cliente se ha desconectado
        print(f"Cliente {client_ip}:{client_port} desconectado")
        eliminar_cliente(client_ip, client_port)
        enviar_a_todos(f"DESCONEXION:{client_ip}:{client_port}")
        
        # Imprimir el tablero actualizado después de la desconexión
        if len(conexiones_clientes) > 0:  # Solo si quedan jugadores
            imprimir_tablero_servidor()

# Función principal
print("Iniciando servidor de Memorama Multijugador...")
dificultad_input = input("Seleccione la dificultad (1: Principiante - tablero 4x4, 2: Avanzado - tablero 6x6): ")
if dificultad_input in ["1", "2"]:
    dificultad = dificultad_input
    if dificultad == "2":
        filas = 6
        columnas = 6
        num_pares = 18
else:
    print("Dificultad inválida. Usando dificultad Principiante por defecto.")

# Inicializar el tablero
inicializar_tablero()

# Configuración del servidor
host_input = input("Ingrese la dirección IP del servidor (presione Enter para usar 127.0.0.1): ")
if host_input:
    HOST = host_input

try:
    port_input = input("Ingrese el puerto del servidor (presione Enter para usar 65432): ")
    if port_input:
        PORT = int(port_input)
except ValueError:
    print("Puerto inválido. Usando puerto 65432 por defecto.")

# Configuración del servidor
servidor_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
servidor_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
servidor_socket.bind((HOST, PORT))
servidor_socket.listen(5)  # Cola de hasta 5 conexiones pendientes
print(f"El servidor de Memorama está disponible en {HOST}:{PORT}")
print("Esperando conexión de clientes...")

try:
    while True:
        # Aceptar conexiones (bloqueante)
        client_conn, client_addr = servidor_socket.accept()
        client_ip = client_addr[0]
        client_port = client_addr[1]

        # Crear un hilo para manejar este cliente
        cliente_thread = threading.Thread(target=manejar_cliente, args=(client_conn, client_addr))
        cliente_thread.daemon = True
        cliente_thread.start()
        
        # Registrar el hilo
        registrar_hilo(client_ip, client_port, cliente_thread)

        print(f"Cliente conectado: {client_ip}:{client_port}. Total: {len(conexiones_clientes) + 1}")

except KeyboardInterrupt:
    print("Servidor interrumpido. Cerrando...")
finally:
    # Cerrar todas las conexiones de clientes
    for addr_str, conn in list(conexiones_clientes.items()):
        try:
            conn.close()
        except:
            pass
    if servidor_socket:
        servidor_socket.close()
    print("Servidor cerrado.")