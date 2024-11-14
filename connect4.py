import numpy as np
import pygame
import sys
import math
import socket
import json
import threading

BLUE = (0,0,255)
BLACK = (0,0,0)
RED = (255,0,0)
YELLOW = (255,255,0)
WHITE = (255,255,255)

ROW_COUNT = 6
COLUMN_COUNT = 7

HOST = 'localhost'
PORT = 5000
client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client.connect((HOST, PORT))

player_number = int(client.recv(1024).decode())
my_turn = player_number == 1

RESTART_YES = "YES"
RESTART_NO = "NO"
RESTART_WAIT = "WAIT"
restart_status = RESTART_WAIT

winner = None

def create_board():
	board = np.zeros((ROW_COUNT,COLUMN_COUNT))
	return board

def drop_piece(board, row, col, piece):
	board[row][col] = piece

def is_valid_location(board, col):
	return board[ROW_COUNT-1][col] == 0

def get_next_open_row(board, col):
	for r in range(ROW_COUNT):
		if board[r][col] == 0:
			return r

def print_board(board):
	print(np.flip(board, 0))

def winning_move(board, piece):
	# Check horizontal locations for win
	for c in range(COLUMN_COUNT-3):
		for r in range(ROW_COUNT):
			if board[r][c] == piece and board[r][c+1] == piece and board[r][c+2] == piece and board[r][c+3] == piece:
				return True

	# Check vertical locations for win
	for c in range(COLUMN_COUNT):
		for r in range(ROW_COUNT-3):
			if board[r][c] == piece and board[r+1][c] == piece and board[r+2][c] == piece and board[r+3][c] == piece:
				return True

	# Check positively sloped diaganols
	for c in range(COLUMN_COUNT-3):
		for r in range(ROW_COUNT-3):
			if board[r][c] == piece and board[r+1][c+1] == piece and board[r+2][c+2] == piece and board[r+3][c+3] == piece:
				return True

	# Check negatively sloped diaganols
	for c in range(COLUMN_COUNT-3):
		for r in range(3, ROW_COUNT):
			if board[r][c] == piece and board[r-1][c+1] == piece and board[r-2][c+2] == piece and board[r-3][c+3] == piece:
				return True

def draw_board(board):
	for c in range(COLUMN_COUNT):
		for r in range(ROW_COUNT):
			pygame.draw.rect(screen, BLUE, (c*SQUARESIZE, r*SQUARESIZE+SQUARESIZE, SQUARESIZE, SQUARESIZE))
			pygame.draw.circle(screen, BLACK, (int(c*SQUARESIZE+SQUARESIZE/2), int(r*SQUARESIZE+SQUARESIZE+SQUARESIZE/2)), RADIUS)
	
	for c in range(COLUMN_COUNT):
		for r in range(ROW_COUNT):		
			if board[r][c] == 1:
				pygame.draw.circle(screen, RED, (int(c*SQUARESIZE+SQUARESIZE/2), height-int(r*SQUARESIZE+SQUARESIZE/2)), RADIUS)
			elif board[r][c] == 2: 
				pygame.draw.circle(screen, YELLOW, (int(c*SQUARESIZE+SQUARESIZE/2), height-int(r*SQUARESIZE+SQUARESIZE/2)), RADIUS)
	pygame.display.update()

def reset_game():
	global board, game_over, turn, restart_status, winner, my_turn
	board = create_board()
	game_over = False
	turn = 0
	winner = None
	restart_status = RESTART_WAIT
	my_turn = player_number == 1
	print(f"reset game: turn={turn}, my_turn={my_turn}, player_number={player_number}")
	screen.fill(BLACK)
	draw_board(board)
	pygame.display.update()
	
	# send reset confirm message to server
	reset_confirm = {
		"type": "reset_confirm",
		"player": player_number
	}
	client.send(json.dumps(reset_confirm).encode() + b"\n")

def cleanup():
	pygame.quit()
	client.close()
	sys.exit()

def draw_restart_buttons():
	yes_button = pygame.draw.rect(screen, (0,255,0), (width//4-100, height//2, 200, 50))
	no_button = pygame.draw.rect(screen, (255,0,0), (3*width//4-100, height//2, 200, 50))
	
	font = pygame.font.SysFont("monospace", 40)
	yes_text = font.render("one more", 1, BLACK)
	no_text = font.render("end game", 1, BLACK)
	
	screen.blit(yes_text, (width//4-80, height//2+10))
	screen.blit(no_text, (3*width//4-80, height//2+10))
	pygame.display.update()
	return yes_button, no_button

def receive_data():
    global turn, game_over, board, restart_status, winner, my_turn
    buffer = ""
    while True:
        try:
            data = client.recv(1024).decode()
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
                    
                    if message.get("type") == "game_start":
                        turn = message.get("turn", 0)
                        first_player = message.get("first_player", 1)
                        my_turn = turn == (player_number - 1)
                        print(f"game start: turn={turn}, my_turn={my_turn}, player_number={player_number}, first_player={first_player}")
                        draw_board(board)
                    
                    if message.get("type") == "move":
                        col = message.get('column')
                        piece = message.get('piece')
                        if col is not None and piece is not None:
                            if is_valid_location(board, col):
                                row = get_next_open_row(board, col)
                                drop_piece(board, row, col, piece)
                                
                                if winning_move(board, piece):
                                    game_over = True
                                    winner = piece
                                    draw_end_screen(winner)
                                else:
                                    # update turn logic
                                    turn = 1 if piece == 1 else 0  # next turn
                                    my_turn = turn == (player_number - 1)
                                    draw_board(board)
                                
                                print(f"update turn: turn={turn}, my_turn={my_turn}, player_number={player_number}")
                                
                    elif message.get("type") == "vote_status":
                        if restart_status == RESTART_YES:
                            draw_end_screen(winner)
                            
                    elif message.get("type") == "reset":
                        if message["result"] == "YES":
                            print("reset game")
                            restart_status = RESTART_WAIT
                            reset_game()
                        else:
                            restart_status = "QUIT"
                            cleanup()
                except json.JSONDecodeError as e:
                    print(f"JSON decode error: {e}, data: {msg}")
                    
        except Exception as e:
            print(f"receive data error: {e}")
            break

def draw_end_screen(winner):
	screen.fill(BLACK)
	
	if winner is None:
		winner_text = myfont.render("Game Over!", 1, WHITE)
	else:
		winner_text = myfont.render(f"Player {winner} wins!", 1, RED if winner == 1 else YELLOW)
	
	text_rect = winner_text.get_rect(center=(width//2, height//4))
	screen.blit(winner_text, text_rect)
	
	button_font = pygame.font.SysFont("monospace", 40)
	
	replay_button = pygame.draw.rect(screen, (0,255,0), (width//2-150, height//2, 300, 60))
	replay_text = button_font.render("Play Again", 1, BLACK)
	replay_rect = replay_text.get_rect(center=(width//2, height//2 + 30))
	screen.blit(replay_text, replay_rect)
	
	quit_button = pygame.draw.rect(screen, (255,0,0), (width//2-150, height//2 + 100, 300, 60))
	quit_text = button_font.render("Quit Game", 1, BLACK)
	quit_rect = quit_text.get_rect(center=(width//2, height//2 + 130))
	screen.blit(quit_text, quit_rect)
	
	if restart_status == RESTART_YES:
		waiting_text = button_font.render("Waiting for other player...", 1, WHITE)
		waiting_rect = waiting_text.get_rect(center=(width//2, height*3//4))
		screen.blit(waiting_text, waiting_rect)
	
	pygame.display.update()
	return replay_button, quit_button

board = create_board()
print_board(board)
game_over = False
turn = 0

pygame.init()

SQUARESIZE = 100

width = COLUMN_COUNT * SQUARESIZE
height = (ROW_COUNT+1) * SQUARESIZE

size = (width, height)

RADIUS = int(SQUARESIZE/2 - 5)

screen = pygame.display.set_mode(size)
draw_board(board)
pygame.display.update()

myfont = pygame.font.SysFont("monospace", 75)

receive_thread = threading.Thread(target=receive_data)
receive_thread.start()

while True:
	try:
		if restart_status == "RESET":
			reset_game()
		elif restart_status == "QUIT":
			cleanup()

		for event in pygame.event.get():
			if event.type == pygame.QUIT:
				cleanup()

			if not game_over:
				if event.type == pygame.MOUSEMOTION:
					pygame.draw.rect(screen, BLACK, (0,0, width, SQUARESIZE))
					posx = event.pos[0]
					if my_turn:
						pygame.draw.circle(screen, RED if player_number == 1 else YELLOW, (posx, int(SQUARESIZE/2)), RADIUS)
					pygame.display.update()

				if event.type == pygame.MOUSEBUTTONDOWN:
					if my_turn:
						posx = event.pos[0]
						col = int(math.floor(posx/SQUARESIZE))

						if is_valid_location(board, col):
							row = get_next_open_row(board, col)
							drop_piece(board, row, col, player_number)
							
							move_data = {
								'type': 'move',
								'column': col,
								'piece': player_number
							}
							message = json.dumps(move_data) + "\n"
							client.send(message.encode())

							if winning_move(board, player_number):
								game_over = True
								winner = player_number
								draw_end_screen(winner)
							else:
								# update turn logic
								turn = 1 if player_number == 1 else 0  # next turn
								my_turn = turn == (player_number - 1)
								draw_board(board)

							print(f"after move: now is player {turn + 1}'s turn, I am player {player_number}")
			
			elif game_over:
				# show end screen
				replay_button, quit_button = draw_end_screen(winner)
				
				if event.type == pygame.MOUSEBUTTONDOWN and restart_status != RESTART_YES:
					mouse_pos = event.pos
					
					if replay_button.collidepoint(mouse_pos):
						# send restart message
						restart_message = {
							"type": "restart",
							"vote": "YES"
						}
						client.send(json.dumps(restart_message).encode())
						restart_status = RESTART_YES
						draw_end_screen(winner)  # redraw to show waiting info
					
					elif quit_button.collidepoint(mouse_pos):
						# send quit message
						quit_message = {
							"type": "restart",
							"vote": "NO"
						}
						client.send(json.dumps(quit_message).encode())
						cleanup()
						
		if not game_over:
			draw_board(board)
			if event.type == pygame.MOUSEMOTION and my_turn:
					pygame.draw.rect(screen, BLACK, (0,0, width, SQUARESIZE))
					posx = event.pos[0]
					pygame.draw.circle(screen, RED if player_number == 1 else YELLOW, 
									 (posx, int(SQUARESIZE/2)), RADIUS)
					pygame.display.update()

		pygame.time.wait(50)

	except pygame.error:
		print("Pygame error occurred, attempting to reinitialize...")
		pygame.init()
		screen = pygame.display.set_mode(size)
		if game_over:
			draw_end_screen(winner)
		else:
			draw_board(board)
	except Exception as e:
		print(f"error: {e}")
		cleanup()
