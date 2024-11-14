import socket
import threading
import json
import signal
import sys
import time
import os

HOST = 'localhost'
PORT = 5000
server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind((HOST, PORT))
server.listen(2)

clients = []
restart_votes = {"YES": 0, "NO": 0}
lock = threading.Lock()
running = True
shutdown_event = threading.Event()  # add shutdown event
first_player = 1  # record current first player

def signal_handler(sig, frame):
    """deal with signal"""
    print("\nclosing server...")
    cleanup()
    os._exit(0)  # use os._exit to force terminate program

def cleanup():
    """clean up resources"""
    global running
    running = False
    shutdown_event.set()
    
    # send shutdown signal first
    with lock:
        for client in clients[:]:
            try:
                client.send("SERVER_SHUTDOWN".encode())
            except:
                pass
    
    # wait for a short time to ensure signal is sent
    time.sleep(0.5)
    
    # then close connections
    with lock:
        for client in clients[:]:
            try:
                client.close()
            except:
                pass
        clients.clear()
    
    try:
        server.close()
    except:
        pass

def reset_game_state():
    global restart_votes, first_player
    with lock:
        restart_votes = {"YES": 0, "NO": 0}
        # alternate first player
        first_player = 2 if first_player == 1 else 1

def handle_client(conn, addr):
    global clients, restart_votes
    
    try:
        while running and not shutdown_event.is_set():
            message = conn.recv(1024).decode()
            if not message:
                break
            
            print(f"receive message from client {addr}: {message}") 
            try:
                data = json.loads(message.strip())  # remove possible newline characters
                print(f"parsed message: {data}")
                
                if data.get("type") == "reset_confirm":
                    # ensure two players are ready
                    with lock:
                        # send game start message
                        start_message = json.dumps({
                            "type": "game_start",
                            "turn": first_player - 1,  # set turn according to first player
                            "first_player": first_player
                        }) + "\n"
                        for client in clients:
                            client.send(start_message.encode())
                
                if data.get("type") == "restart":
                    vote = data.get("vote")
                    if vote in ["YES", "NO"]:
                        with lock:
                            restart_votes[vote] += 1
                            print(f"当前投票状态: {restart_votes}")
                            
                            # broadcast vote status
                            vote_status = json.dumps({
                                "type": "vote_status",
                                "votes": restart_votes
                            }) + "\n"
                            
                            for client in clients:
                                client.send(vote_status.encode())
                            
                            # when two players vote
                            if restart_votes["YES"] + restart_votes["NO"] == 2:
                                time.sleep(0.1)
                                result = json.dumps({
                                    "type": "reset",
                                    "result": "YES" if restart_votes["YES"] == 2 else "NO"
                                }) + "\n"
                                
                                for client in clients:
                                    client.send(result.encode())
                                reset_game_state()
                elif data.get("type") == "move":
                    # forward move message
                    with lock:
                        move_message = json.dumps({
                            "type": "move",
                            "column": data.get('column'),
                            "piece": data.get('piece')
                        }) + "\n"
                        print(f"forward move message: {move_message}")
                        for client in clients:
                            if client != conn:
                                client.send(move_message.encode())
                                print(f"sent to other clients")
                                
            except json.JSONDecodeError as e:
                print(f"JSON decode error: {e}, data: {message}")
                continue
                
    except Exception as e:
        print(f"handle client error: {e}")
    finally:
        with lock:
            if conn in clients:
                clients.remove(conn)
            conn.close()

def accept_connections():
    while running and not shutdown_event.is_set():
        try:
            server.settimeout(0.5)
            try:
                conn, addr = server.accept()
                with lock:
                    if len(clients) >= 2:
                        conn.send("FULL".encode())
                        conn.close()
                        continue
                    
                    clients.append(conn)
                    player_number = len(clients)
                    conn.send(str(player_number).encode())
                    print(f"client connected: {addr}, player number: {player_number}")
                    
                    client_thread = threading.Thread(target=handle_client, args=(conn, addr))
                    client_thread.daemon = True
                    client_thread.start()
            except socket.timeout:
                if not running:
                    break
                continue
        except Exception as e:
            if running:
                print(f"accept connection error: {e}")

def handle_shutdown():
    print("shutting down server...")
    # notify all clients that server is shutting down
    for client in clients:
        try:
            client.send("SERVER_SHUTDOWN".encode())
            client.close()
        except:
            pass
    server.close()
    sys.exit(0)  # force terminate program

def main():
    signal.signal(signal.SIGINT, signal_handler)
    print("server started...")
    
    accept_thread = threading.Thread(target=accept_connections)
    accept_thread.daemon = True
    accept_thread.start()
    
    try:
        while running and not shutdown_event.is_set():
            command = input()
            if command.lower() == 'quit':
                cleanup()
                break
    except KeyboardInterrupt:
        handle_shutdown()
    except Exception as e:
        print(f"main loop error: {e}")
        cleanup()

if __name__ == "__main__":
    main()