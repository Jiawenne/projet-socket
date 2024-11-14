import numpy as np
import pygame
import sys
import math
import socket
import json
import threading
import os

class Connect4Game:
    # color constants
    BLUE = (0,0,255)
    BLACK = (0,0,0)
    RED = (255,0,0)
    YELLOW = (255,255,0)
    WHITE = (255,255,255)
    
    # game constants
    ROW_COUNT = 6
    COLUMN_COUNT = 7
    SQUARESIZE = 100
    
    def __init__(self, host='localhost', port=5000):
        # initialize network connection
        self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.client.connect((host, port))
            self.player_number = int(self.client.recv(1024).decode())
            print(f"you are player {self.player_number}")
        except Exception as e:
            print(f"connection to server failed: {e}")
            sys.exit(1)
            
        # initialize game state
        self.board = self.create_board()
        self.game_over = False
        self.turn = 0
        self.winner = None
        self.my_turn = self.player_number == 1
        
        # initialize restart status
        self.RESTART_YES = "YES"
        self.RESTART_NO = "NO"
        self.RESTART_WAIT = "WAIT"
        self.restart_status = self.RESTART_WAIT
        
        # initialize pygame
        pygame.init()
        self.width = self.COLUMN_COUNT * self.SQUARESIZE
        self.height = (self.ROW_COUNT+1) * self.SQUARESIZE
        self.RADIUS = int(self.SQUARESIZE/2 - 5)
        
        self.screen = pygame.display.set_mode((self.width, self.height))
        pygame.display.set_caption("Connect 4")
        self.myfont = pygame.font.SysFont("monospace", 75)
        
        # start receive thread
        self.receive_thread = threading.Thread(target=self.receive_data)
        self.receive_thread.daemon = True
        self.receive_thread.start()
        
        # draw initial board
        self.draw_board()
        
    def create_board(self):
        return np.zeros((self.ROW_COUNT, self.COLUMN_COUNT))
        
    def drop_piece(self, row, col, piece):
        self.board[row][col] = piece
        
    def is_valid_location(self, col):
        return col >= 0 and col < self.COLUMN_COUNT and self.board[self.ROW_COUNT-1][col] == 0
        
    def get_next_open_row(self, col):
        for r in range(self.ROW_COUNT):
            if self.board[r][col] == 0:
                return r
        return None
        
    def winning_move(self, piece):
        # horizontal check
        for c in range(self.COLUMN_COUNT-3):
            for r in range(self.ROW_COUNT):
                if (self.board[r][c] == piece and 
                    self.board[r][c+1] == piece and 
                    self.board[r][c+2] == piece and 
                    self.board[r][c+3] == piece):
                    return True

        # vertical check
        for c in range(self.COLUMN_COUNT):
            for r in range(self.ROW_COUNT-3):
                if (self.board[r][c] == piece and 
                    self.board[r+1][c] == piece and 
                    self.board[r+2][c] == piece and 
                    self.board[r+3][c] == piece):
                    return True

        # positive diagonal check
        for c in range(self.COLUMN_COUNT-3):
            for r in range(self.ROW_COUNT-3):
                if (self.board[r][c] == piece and 
                    self.board[r+1][c+1] == piece and 
                    self.board[r+2][c+2] == piece and 
                    self.board[r+3][c+3] == piece):
                    return True

        # negative diagonal check
        for c in range(self.COLUMN_COUNT-3):
            for r in range(3, self.ROW_COUNT):
                if (self.board[r][c] == piece and 
                    self.board[r-1][c+1] == piece and 
                    self.board[r-2][c+2] == piece and 
                    self.board[r-3][c+3] == piece):
                    return True
                    
        return False
        
    def draw_board(self):
        for c in range(self.COLUMN_COUNT):
            for r in range(self.ROW_COUNT):
                pygame.draw.rect(self.screen, self.BLUE, 
                               (c*self.SQUARESIZE, r*self.SQUARESIZE+self.SQUARESIZE, 
                                self.SQUARESIZE, self.SQUARESIZE))
                pygame.draw.circle(self.screen, self.BLACK,
                                 (int(c*self.SQUARESIZE+self.SQUARESIZE/2), 
                                  int(r*self.SQUARESIZE+self.SQUARESIZE+self.SQUARESIZE/2)), 
                                 self.RADIUS)
        
        for c in range(self.COLUMN_COUNT):
            for r in range(self.ROW_COUNT):        
                if self.board[r][c] == 1:
                    pygame.draw.circle(self.screen, self.RED,
                                     (int(c*self.SQUARESIZE+self.SQUARESIZE/2), 
                                      self.height-int(r*self.SQUARESIZE+self.SQUARESIZE/2)), 
                                     self.RADIUS)
                elif self.board[r][c] == 2: 
                    pygame.draw.circle(self.screen, self.YELLOW,
                                     (int(c*self.SQUARESIZE+self.SQUARESIZE/2), 
                                      self.height-int(r*self.SQUARESIZE+self.SQUARESIZE/2)), 
                                     self.RADIUS)
        pygame.display.update()
        
    def draw_end_screen(self):
        self.screen.fill(self.BLACK)
        
        if self.winner is None:
            winner_text = self.myfont.render("Game Over!", 1, self.WHITE)
        else:
            winner_text = self.myfont.render(f"Player {self.winner} wins!", 1, 
                                           self.RED if self.winner == 1 else self.YELLOW)
        
        text_rect = winner_text.get_rect(center=(self.width//2, self.height//4))
        self.screen.blit(winner_text, text_rect)
        
        button_font = pygame.font.SysFont("monospace", 40)
        
        replay_button = pygame.draw.rect(self.screen, (0,255,0), 
                                       (self.width//2-150, self.height//2, 300, 60))
        replay_text = button_font.render("Play Again", 1, self.BLACK)
        replay_rect = replay_text.get_rect(center=(self.width//2, self.height//2 + 30))
        self.screen.blit(replay_text, replay_rect)
        
        quit_button = pygame.draw.rect(self.screen, (255,0,0),
                                     (self.width//2-150, self.height//2 + 100, 300, 60))
        quit_text = button_font.render("Quit Game", 1, self.BLACK)
        quit_rect = quit_text.get_rect(center=(self.width//2, self.height//2 + 130))
        self.screen.blit(quit_text, quit_rect)
        
        if self.restart_status == self.RESTART_YES:
            waiting_text = button_font.render("Waiting for other player...", 1, self.WHITE)
            waiting_rect = waiting_text.get_rect(center=(self.width//2, self.height*3//4))
            self.screen.blit(waiting_text, waiting_rect)
        
        pygame.display.update()
        return replay_button, quit_button
        
    def reset_game(self):
        self.board = self.create_board()
        self.game_over = False
        self.turn = 0
        self.winner = None
        self.restart_status = self.RESTART_WAIT
        self.my_turn = self.player_number == 1
        print(f"reset game: turn={self.turn}, my_turn={self.my_turn}, player_number={self.player_number}")
        self.screen.fill(self.BLACK)
        self.draw_board()
        pygame.display.update()
        
        reset_confirm = {
            "type": "reset_confirm",
            "player": self.player_number
        }
        self.client.send(json.dumps(reset_confirm).encode() + b"\n")
        
    def cleanup(self):
        pygame.quit()
        self.client.close()
        sys.exit()
        
    def receive_data(self):
        buffer = ""
        while True:
            try:
                data = self.client.recv(1024).decode()
                if not data:
                    break
                    
                buffer += data
                messages = buffer.split("\n")
                buffer = messages[-1]
                
                for msg in messages[:-1]:
                    if not msg.strip():
                        continue
                    try:
                        message = json.loads(msg)
                        self.handle_message(message)
                    except json.JSONDecodeError as e:
                        print(f"JSON decode error: {e}, data: {msg}")
                        
            except Exception as e:
                print(f"receive data error: {e}")
                break
                
    def handle_message(self, message):
        msg_type = message.get("type")
        
        if msg_type == "game_start":
            self.turn = message.get("turn", 0)
            first_player = message.get("first_player", 1)
            self.my_turn = self.turn == (self.player_number - 1)
            print(f"game start: turn={self.turn}, my_turn={self.my_turn}, player_number={self.player_number}, first_player={first_player}")
            self.draw_board()
            
        elif msg_type == "move":
            self.handle_move_message(message)
            
        elif msg_type == "vote_status":
            if self.restart_status == self.RESTART_YES:
                self.draw_end_screen()
                
        elif msg_type == "reset":
            if message["result"] == "YES":
                print("reset game")
                self.restart_status = self.RESTART_WAIT
                self.reset_game()
            else:
                self.restart_status = "QUIT"
                self.cleanup()
                
    def handle_move_message(self, message):
        col = message.get('column')
        piece = message.get('piece')
        if col is not None and piece is not None:
            if self.is_valid_location(col):
                row = self.get_next_open_row(col)
                self.drop_piece(row, col, piece)
                
                if self.winning_move(piece):
                    self.game_over = True
                    self.winner = piece
                    self.draw_end_screen()
                else:
                    self.turn = 1 if piece == 1 else 0
                    self.my_turn = self.turn == (self.player_number - 1)
                    self.draw_board()
                
                print(f"update turn: turn={self.turn}, my_turn={self.my_turn}, player_number={self.player_number}")
                
    def run(self):
        while True:
            try:
                if self.restart_status == "RESET":
                    self.reset_game()
                elif self.restart_status == "QUIT":
                    self.cleanup()
                    
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        self.cleanup()
                        
                    if not self.game_over:
                        self.handle_game_events(event)
                    else:
                        self.handle_end_game_events(event)
                        
                pygame.time.wait(50)
                
            except pygame.error:
                print("Pygame error occurred, attempting to reinitialize...")
                pygame.init()
                self.screen = pygame.display.set_mode((self.width, self.height))
                if self.game_over:
                    self.draw_end_screen()
                else:
                    self.draw_board()
            except Exception as e:
                print(f"error: {e}")
                self.cleanup()
                
    def handle_game_events(self, event):
        if event.type == pygame.MOUSEMOTION and self.my_turn:
            pygame.draw.rect(self.screen, self.BLACK, (0,0, self.width, self.SQUARESIZE))
            posx = event.pos[0]
            pygame.draw.circle(self.screen, self.RED if self.player_number == 1 else self.YELLOW,
                             (posx, int(self.SQUARESIZE/2)), self.RADIUS)
            pygame.display.update()
            
        elif event.type == pygame.MOUSEBUTTONDOWN and self.my_turn:
            posx = event.pos[0]
            col = int(math.floor(posx/self.SQUARESIZE))
            
            if self.is_valid_location(col):
                row = self.get_next_open_row(col)
                if row is not None:
                    self.drop_piece(row, col, self.player_number)
                    
                    move_data = {
                        'type': 'move',
                        'column': col,
                        'piece': self.player_number
                    }
                    self.client.send(json.dumps(move_data).encode() + b"\n")
                    
                    if self.winning_move(self.player_number):
                        self.game_over = True
                        self.winner = self.player_number
                        self.draw_end_screen()
                    else:
                        self.turn = 1 if self.player_number == 1 else 0
                        self.my_turn = self.turn == (self.player_number - 1)
                        self.draw_board()
                        
                    print(f"after move: now is player {self.turn + 1}'s turn, I am player {self.player_number}")
                    
    def handle_end_game_events(self, event):
        replay_button, quit_button = self.draw_end_screen()
        
        if event.type == pygame.MOUSEBUTTONDOWN and self.restart_status != self.RESTART_YES:
            mouse_pos = event.pos
            
            if replay_button.collidepoint(mouse_pos):
                restart_message = {
                    "type": "restart",
                    "vote": "YES"
                }
                self.client.send(json.dumps(restart_message).encode())
                self.restart_status = self.RESTART_YES
                self.draw_end_screen()
                
            elif quit_button.collidepoint(mouse_pos):
                quit_message = {
                    "type": "restart",
                    "vote": "NO"
                }
                self.client.send(json.dumps(quit_message).encode())
                self.cleanup()

def main():
    game = Connect4Game()
    try:
        game.run()
    except KeyboardInterrupt:
        game.cleanup()

if __name__ == "__main__":
    main()
