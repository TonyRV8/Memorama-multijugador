import socket
import threading
import time
import json

# Variables globales
buffer_size = 1024
tablero_visible = []
filas = 0
columnas = 0
puntuaciones = {}
cliente_socket = None
juego_activo = True
turno_actual = None  # Nueva variable para rastrear de quién es el turno
mi_direccion = None  # Para almacenar la dirección del cliente actual

def imprimir_tablero():
    print("\n  ", end="")
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

def imprimir_puntuaciones():
    print("\nPuntuaciones:")
    for addr, puntos in puntuaciones.items():
        print(f"Jugador {addr}: {puntos} puntos")
    
    # Mostrar información sobre el turno actual
    if turno_actual:
        if turno_actual == mi_direccion:
            print("\n¡ES TU TURNO PARA JUGAR!")
        else:
            print(f"\nEs el turno del jugador {turno_actual}")

def solicitar_coordenadas():
    while True:
        try:
            print("\nIngrese las coordenadas de las dos casillas a destapar")
            fila1 = int(input("Fila de la primera casilla: "))
            col1 = int(input("Columna de la primera casilla: "))
            fila2 = int(input("Fila de la segunda casilla: "))
            col2 = int(input("Columna de la segunda casilla: "))
            
            # Validar coordenadas
            if not (0 <= fila1 < filas and 0 <= col1 < columnas and 
                    0 <= fila2 < filas and 0 <= col2 < columnas):
                print("Coordenadas fuera de rango, intente de nuevo")
                continue
            
            # Verificar que no sean la misma casilla
            if fila1 == fila2 and col1 == col2:
                print("No puede seleccionar la misma casilla dos veces, intente de nuevo")
                continue
            
            # Verificar que las casillas no estén ya destapadas
            if tablero_visible[fila1][col1] != "?" or tablero_visible[fila2][col2] != "?":
                print("Una o ambas casillas ya están destapadas, intente de nuevo")
                continue
            
            return fila1, col1, fila2, col2
        
        except ValueError:
            print("Por favor, ingrese números enteros válidos")
        except IndexError:
            print(f"Error: Coordenadas fuera de rango. El tablero es de {filas}x{columnas}")

def procesar_jugada(data):
    global puntuaciones, tablero_visible, juego_activo
    
    try:
        # JUGADA:IP:puerto:fila1,col1:palabra1:fila2,col2:palabra2:acierto:tablero:puntuaciones
        partes = data.split(":", 9)  # Máximo 10 partes
        ip_jugador = partes[1]
        puerto_jugador = partes[2]
        coord1 = partes[3].split(",")
        palabra1 = partes[4]
        coord2 = partes[5].split(",")
        palabra2 = partes[6]
        acierto = partes[7] == "1"
        tablero_json = partes[8]
        if len(partes) > 9:
            puntuaciones_json = partes[9]
            try:
                puntuaciones = json.loads(puntuaciones_json)
            except json.JSONDecodeError:
                print(f"Error al decodificar puntuaciones: {puntuaciones_json}")
    except Exception as e:
        print(f"Error al procesar mensaje de jugada: {e}")
        print(f"Mensaje recibido: {data}")
        return False
    
    fila1, col1 = int(coord1[0]), int(coord1[1])
    fila2, col2 = int(coord2[0]), int(coord2[1])
    
    # Actualizar tablero
    try:
        tablero_visible = json.loads(tablero_json)
    except json.JSONDecodeError:
        print(f"Error al decodificar tablero: {tablero_json}")
    except Exception as e:
        print(f"Error general al procesar tablero: {e}")
        return False
    
    # Mostrar casillas destapadas
    print(f"\nJugada del jugador {ip_jugador}:{puerto_jugador}:")
    print(f"[{fila1},{col1}] = {palabra1}")
    print(f"[{fila2},{col2}] = {palabra2}")
    
    if acierto:
        print(f"¡El jugador {ip_jugador}:{puerto_jugador} encontró un par!")
    else:
        print(f"Las casillas no coinciden.")
    
    return acierto

def procesar_fin_juego(data):
    global juego_activo
    
    try:
        # FIN:IP:puerto:duracion:maxPuntos:motivo
        partes = data.split(":")
        resultado = partes[1]
        
        if resultado == "EMPATE":
            duracion = float(partes[2])
            max_puntos = int(partes[3])
            motivo = partes[4] if len(partes) > 4 else "COMPLETADO"
            
            print("\n¡Juego terminado!")
            print(f"Motivo: {motivo}")
            print(f"Duración: {duracion:.2f} segundos")
            print("El juego terminó en empate.")
        else:
            ip_ganador = partes[1]
            puerto_ganador = partes[2]
            duracion = float(partes[3])
            max_puntos = int(partes[4])
            motivo = partes[5] if len(partes) > 5 else "COMPLETADO"
            
            print("\n¡Juego terminado!")
            print(f"Motivo: {motivo}")
            print(f"Duración: {duracion:.2f} segundos")
            print(f"Ganador: Jugador {ip_ganador}:{puerto_ganador} con {max_puntos} puntos")
        
        imprimir_puntuaciones()
        juego_activo = False
        
        # Terminar la aplicación
        print("El juego ha terminado")
        # Programar salida automática después de 5 segundos
        import threading, time, sys
        def salida_automatica():
            time.sleep(5)
            import os
            os._exit(0)  # Forzar terminación
        # Iniciar hilo para salida automática
        threading.Thread(target=salida_automatica, daemon=True).start()
        
    except Exception as e:
        print(f"Error al procesar mensaje de fin de juego: {e}")
        print(f"Mensaje recibido: {data}")
        juego_activo = False

def procesar_conexion(data):
    try:
        # CONEXION:IP:puerto
        partes = data.split(":")
        ip = partes[1]
        puerto = partes[2]
        
        print(f"\nNuevo jugador conectado: {ip}:{puerto}")
    except Exception as e:
        print(f"Error al procesar mensaje de conexión: {e}")
        print(f"Mensaje recibido: {data}")

def procesar_desconexion(data):
    try:
        # DESCONEXION:IP:puerto
        partes = data.split(":")
        ip = partes[1]
        puerto = partes[2]
        
        print(f"\nJugador desconectado: {ip}:{puerto}")
        
        # Eliminar jugador de puntuaciones si existe
        addr = f"{ip}:{puerto}"
        if addr in puntuaciones:
            del puntuaciones[addr]
    except Exception as e:
        print(f"Error al procesar mensaje de desconexión: {e}")
        print(f"Mensaje recibido: {data}")

def procesar_turno(data):
    global turno_actual
    
    try:
        # TURNO:IP:puerto
        partes = data.split(":")
        turno_actual = partes[1]
        if len(partes) > 2:
            turno_actual = f"{turno_actual}:{partes[2]}"  # Asegurar formato IP:puerto
        
        print(f"Procesando turno, mi dirección: {mi_direccion}, turno actual: {turno_actual}")
        
        if turno_actual == mi_direccion:
            print("\n¡ES TU TURNO PARA JUGAR!")
        else:
            print(f"\nEs el turno del jugador {turno_actual}")
            
    except Exception as e:
        print(f"Error al procesar mensaje de turno: {e}")
        print(f"Mensaje recibido: {data}")

def hilo_escucha(cliente_socket):
    global juego_activo, turno_actual
    
    while juego_activo:
        try:
            data = cliente_socket.recv(buffer_size).decode()
            if not data:
                print("Servidor desconectado")
                juego_activo = False
                break
                
            # Responder a PING con PONG para mantener la conexión
            if data == "PING":
                cliente_socket.sendall("PONG".encode())
                continue
                
            if data.startswith("JUGADA:"):
                procesar_jugada(data)
                # Mostrar tablero actualizado
                imprimir_tablero()
                imprimir_puntuaciones()
            elif data.startswith("FIN:"):
                procesar_fin_juego(data)
                # El juego ha terminado
                break
            elif data.startswith("DESPEDIDA:"):
                mensaje = data.split(":", 1)[1]
                print(f"\n{mensaje}")
                print("El servidor ha cerrado la conexión. Saliendo...")
                juego_activo = False
                import sys
                sys.exit(0)
            elif data.startswith("CONEXION:"):
                procesar_conexion(data)
            elif data.startswith("DESCONEXION:"):
                procesar_desconexion(data)
            elif data.startswith("ERROR:"):
                print(f"\nError: {data.split(':')[1]}")
            elif data.startswith("TURNO:"):
                procesar_turno(data)
                # Mostrar tablero actualizado después del cambio de turno
                imprimir_tablero()
                imprimir_puntuaciones()
            elif data.startswith("ESPERAR:"):
                partes = data.split(":")
                jugador_turno = partes[1]
                print(f"\nNo es tu turno. Actualmente es el turno del jugador {jugador_turno}")
            else:
                print(f"Mensaje desconocido del servidor: {data}")
                
        except socket.timeout:
            print("Timeout: No se recibió respuesta del servidor en el tiempo esperado")
            print("La conexión se ha perdido. Saliendo del juego.")
            juego_activo = False
            break
        except ConnectionResetError:
            print("Conexión cerrada por el servidor")
            juego_activo = False
            break
        except Exception as e:
            print(f"Error en la recepción: {e}")
            juego_activo = False
            break

# Inicializamos la conexión
print("Cliente de Memorama Multijugador")
# Configurar la conexión
host = input("Ingrese la dirección IP del servidor (presione Enter para usar 127.0.0.1): ") or "127.0.0.1"
    
try:
    puerto_local = 0  # Usar puerto dinámico asignado por el sistema
    puerto_servidor = int(input("Ingrese el puerto del servidor (presione Enter para usar 65432): ") or "65432")
except ValueError:
    puerto_servidor = 65432
    print("Puerto inválido. Usando puerto 65432 por defecto.")

# Crear socket TCP
cliente_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

try:
    print(f"Conectando al servidor en {host}:{puerto_servidor}...")
    cliente_socket.bind(('', puerto_local))  # Bind a cualquier interfaz, puerto dinámico
    cliente_socket.connect((host, puerto_servidor))
    
    # Obtener el puerto local asignado
    _, puerto_asignado = cliente_socket.getsockname()
    
    # Guardar mi dirección para comparaciones futuras
    mi_direccion = f"{host}:{puerto_asignado}"
    print(f"Conectado con dirección local: {mi_direccion}")
    
    # Aumentar el tiempo de espera del socket
    cliente_socket.settimeout(100)  # 100 segundos
    print("Conexión establecida")
    
    # Recibir configuración inicial - CONFIG:dificultad:filas:columnas
    data = cliente_socket.recv(buffer_size).decode()
    if data.startswith("CONFIG:"):
        partes = data.split(":")
        dificultad = partes[1]
        filas = int(partes[2])
        columnas = int(partes[3])
        
        # Inicializar tablero visible (lo que el jugador puede ver)
        tablero_visible = []
        for i in range(filas):
            fila = []
            for j in range(columnas):
                fila.append("?")
            tablero_visible.append(fila)
        
        print(f"\nIniciando juego en dificultad {'Principiante' if dificultad == '1' else 'Avanzado'}")
        print(f"Tablero de {filas}x{columnas}")
    else:
        print("Respuesta inesperada del servidor")
        print(f"Mensaje recibido: {data}")
        juego_activo = False
    
    if juego_activo:
        # Iniciar hilo para escuchar mensajes del servidor
        escucha_thread = threading.Thread(target=hilo_escucha, args=(cliente_socket,))
        escucha_thread.daemon = True
        escucha_thread.start()
        
        # Bucle principal de juego
        while juego_activo:
            # Mostrar tablero actual
            imprimir_tablero()
            imprimir_puntuaciones()
            
            # Verificar si es nuestro turno
            if turno_actual and turno_actual != mi_direccion:
                print(f"Esperando tu turno... Actualmente es turno de {turno_actual}")
                # Debug: mostrar detalles de las variables para diagnóstico
                print(f"DEBUG - Mi dirección: '{mi_direccion}', Turno actual: '{turno_actual}'")
                time.sleep(2)  # Esperar un poco antes de verificar de nuevo
                continue
            
            # Solicitar coordenadas al usuario
            print("\n¡ES TU TURNO! Selecciona las casillas:")
            fila1, col1, fila2, col2 = solicitar_coordenadas()
            
            # Enviar jugada al servidor - JUGAR:fila1,col1:fila2,col2
            mensaje = f"JUGAR:{fila1},{col1}:{fila2},{col2}"
            print(f"Enviando jugada: {mensaje}")
            cliente_socket.sendall(mensaje.encode())
            
            # Esperar un breve momento para permitir al hilo de escucha procesar la respuesta
            time.sleep(0.5)

except ConnectionRefusedError:
    print("No se pudo conectar al servidor. Verifique que el servidor esté en ejecución.")
except Exception as e:
    print(f"Error: {e}")
finally:
    if cliente_socket:
        try:
            cliente_socket.close()
        except:
            pass
        print("Conexión cerrada.")