import socket
import threading
import json
import signal
import sys
import time
import os

class GameServer:
    def __init__(self, host='localhost', port=5000):
        self.host = host
        self.port = port
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.bind((self.host, self.port))
        self.server.listen(2)
        
        self.clients = []
        self.restart_votes = {"YES": 0, "NO": 0}
        self.lock = threading.Lock()
        self.running = True
        self.shutdown_event = threading.Event()
        self.first_player = 1
        
    def cleanup(self):
        self.running = False
        self.shutdown_event.set()
        
        with self.lock:
            for client in self.clients[:]:
                try:
                    client.send("SERVER_SHUTDOWN".encode())
                except:
                    pass
        
        time.sleep(0.5)
        
        with self.lock:
            for client in self.clients[:]:
                try:
                    client.close()
                except:
                    pass
            self.clients.clear()
        
        try:
            self.server.close()
        except:
            pass
            
    def reset_game_state(self):
        with self.lock:
            self.restart_votes = {"YES": 0, "NO": 0}
            self.first_player = 2 if self.first_player == 1 else 1
            
            start_message = json.dumps({
                "type": "game_start",
                "turn": self.first_player - 1,
                "first_player": self.first_player
            }) + "\n"
            
            for client in self.clients:
                client.send(start_message.encode())
                
    def handle_client(self, conn, addr):
        try:
            while self.running and not self.shutdown_event.is_set():
                message = conn.recv(1024).decode()
                if not message:
                    break
                
                print(f"receive message from client {addr}: {message}")
                try:
                    data = json.loads(message.strip())
                    print(f"parsed message: {data}")
                    
                    if data.get("type") == "restart":
                        self.handle_restart_vote(data, conn)
                    elif data.get("type") == "move":
                        self.handle_move(data, conn)
                        
                except json.JSONDecodeError as e:
                    print(f"JSON decode error: {e}, data: {message}")
                    
        except Exception as e:
            print(f"handle client error: {e}")
        finally:
            with self.lock:
                if conn in self.clients:
                    self.clients.remove(conn)
                conn.close()
                
    def handle_restart_vote(self, data, conn):
        vote = data.get("vote")
        if vote in ["YES", "NO"]:
            with self.lock:
                self.restart_votes[vote] += 1
                print(f"current vote status: {self.restart_votes}")
                
                vote_status = json.dumps({
                    "type": "vote_status",
                    "votes": self.restart_votes
                }) + "\n"
                
                for client in self.clients:
                    client.send(vote_status.encode())
                
                if sum(self.restart_votes.values()) == 2:
                    if self.restart_votes["YES"] == 2:
                        result = json.dumps({
                            "type": "reset",
                            "result": "YES"
                        }) + "\n"
                        
                        for client in self.clients:
                            client.send(result.encode())
                        
                        self.reset_game_state()
                    else:
                        result = json.dumps({
                            "type": "reset",
                            "result": "NO"
                        }) + "\n"
                        
                        for client in self.clients:
                            client.send(result.encode())
                        
                        self.restart_votes = {"YES": 0, "NO": 0}
                        
    def handle_move(self, data, conn):
        with self.lock:
            move_message = json.dumps({
                "type": "move",
                "column": data.get('column'),
                "piece": data.get('piece')
            }) + "\n"
            print(f"forward move message: {move_message}")
            for client in self.clients:
                if client != conn:
                    client.send(move_message.encode())
                    
    def accept_connections(self):
        while self.running and not self.shutdown_event.is_set():
            try:
                self.server.settimeout(0.5)
                try:
                    conn, addr = self.server.accept()
                    with self.lock:
                        if len(self.clients) >= 2:
                            conn.send("FULL".encode())
                            conn.close()
                            continue
                        
                        self.clients.append(conn)
                        player_number = len(self.clients)
                        conn.send(str(player_number).encode())
                        print(f"client connected: {addr}, player number: {player_number}")
                        
                        client_thread = threading.Thread(target=self.handle_client, 
                                                       args=(conn, addr))
                        client_thread.daemon = True
                        client_thread.start()
                except socket.timeout:
                    if not self.running:
                        break
                    continue
            except Exception as e:
                if self.running:
                    print(f"accept connection error: {e}")
                    
    def run(self):
        print("server started...")
        
        accept_thread = threading.Thread(target=self.accept_connections)
        accept_thread.daemon = True
        accept_thread.start()
        
        try:
            while self.running and not self.shutdown_event.is_set():
                command = input()
                if command.lower() == 'quit':
                    self.cleanup()
                    break
        except KeyboardInterrupt:
            print("shutting down server...")
            self.cleanup()
        except Exception as e:
            print(f"main loop error: {e}")
            self.cleanup()

def main():
    server = GameServer()
    
    def signal_handler(sig, frame):
        print("\nclosing server...")
        server.cleanup()
        os._exit(0)
        
    signal.signal(signal.SIGINT, signal_handler)
    server.run()

if __name__ == "__main__":
    main()