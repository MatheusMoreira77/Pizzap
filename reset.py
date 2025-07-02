from BancoDeDados import BancoDeDados

db = BancoDeDados()


import sqlite3

conn = sqlite3.connect('seu_banco.db')
cursor = conn.cursor()

pizzas = [
    ('Calabresa', 'Pizza com bastante calabresa saborosa.', 'Calabresa, cebola, mussarela', 39.90, 22.00, 'Tradicional'),
    ('Marguerita', 'Pizza clássica com manjericão fresco.', 'Tomate, mussarela, manjericão', 37.50, 20.00, 'Vegetariana'),
    ('Frango com Catupiry', 'Pizza cremosa com frango e catupiry.', 'Frango, catupiry, orégano', 42.00, 23.00, 'Premium')
]

cursor.executemany('''
    INSERT INTO cardapio (nome, descricao, ingredientes, preco_inteira, preco_meia, categoria)
    VALUES (?, ?, ?, ?, ?, ?)
''', pizzas)

conn.commit()
conn.close()
