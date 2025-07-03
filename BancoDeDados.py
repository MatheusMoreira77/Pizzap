import sqlite3
import requests
import re
from typing import Optional, List, Dict, Union, Tuple
from datetime import datetime

class BancoDeDados:
    def __init__(self, nome_banco: str = 'pizzaria.db') -> None:
        self.nome_banco = nome_banco
        self._criar_tabelas()
        self._popular_dados_iniciais()
    
    def _conectar(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.nome_banco)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.row_factory = sqlite3.Row
        return conn
    
    def _criar_tabelas(self) -> None:
        tabelas = [
            '''
            CREATE TABLE IF NOT EXISTS clientes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL CHECK(length(nome) >= 3),
                telefone TEXT NOT NULL UNIQUE CHECK(length(telefone) >= 10),
                data_cadastro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            ''',
            '''
            CREATE TABLE IF NOT EXISTS enderecos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cliente_id INTEGER NOT NULL,
                apelido TEXT NOT NULL CHECK(length(apelido) >= 2),
                cep TEXT NOT NULL CHECK(length(cep) == 8),
                logradouro TEXT NOT NULL,
                numero TEXT NOT NULL,
                complemento TEXT,
                bairro TEXT NOT NULL,
                cidade TEXT NOT NULL,
                uf TEXT NOT NULL CHECK(length(uf) == 2),
                FOREIGN KEY (cliente_id) REFERENCES clientes(id) ON DELETE CASCADE
            )
            ''',
            '''
            CREATE TABLE IF NOT EXISTS categorias (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL UNIQUE,
                descricao TEXT
            )
            ''',
            '''
            CREATE TABLE IF NOT EXISTS pizzas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL UNIQUE CHECK(length(nome) >= 3),
                descricao TEXT NOT NULL CHECK(length(descricao) >= 10),
                ingredientes TEXT NOT NULL CHECK(length(ingredientes) >= 5),
                categoria_id INTEGER NOT NULL,
                disponivel BOOLEAN DEFAULT 1,
                FOREIGN KEY (categoria_id) REFERENCES categorias(id)
            )
            ''',
            '''
            CREATE TABLE IF NOT EXISTS precos (
                pizza_id INTEGER NOT NULL,
                tamanho TEXT NOT NULL CHECK(tamanho IN ('P', 'M', 'G')),
                valor REAL NOT NULL CHECK(valor > 0),
                PRIMARY KEY (pizza_id, tamanho),
                FOREIGN KEY (pizza_id) REFERENCES pizzas(id) ON DELETE CASCADE
            )
            ''',
            '''
            CREATE TABLE IF NOT EXISTS pedidos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cliente_id INTEGER NOT NULL,
                endereco_id INTEGER NOT NULL,
                data_pedido TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'Recebido' CHECK(status IN (
                    'Recebido', 'Confirmado', 'Em preparo', 
                    'Assando', 'Saiu para entrega', 'Entregue'
                )),
                valor_total REAL NOT NULL CHECK(valor_total > 0),
                forma_pagamento TEXT CHECK(forma_pagamento IN (
                    'Dinheiro', 'Cartão', 'PIX'
                )),
                troco_para REAL DEFAULT 0,
                observacoes TEXT,
                FOREIGN KEY (cliente_id) REFERENCES clientes(id),
                FOREIGN KEY (endereco_id) REFERENCES enderecos(id)
            )
            ''',
            '''
            CREATE TABLE IF NOT EXISTS itens_pedido (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pedido_id INTEGER NOT NULL,
                pizza_id INTEGER NOT NULL,
                tamanho TEXT NOT NULL CHECK(tamanho IN ('P', 'M', 'G')),
                quantidade INTEGER NOT NULL CHECK(quantidade > 0),
                valor_unitario REAL NOT NULL CHECK(valor_unitario > 0),
                observacoes TEXT,
                FOREIGN KEY (pedido_id) REFERENCES pedidos(id) ON DELETE CASCADE,
                FOREIGN KEY (pizza_id) REFERENCES pizzas(id)
            )
            '''
        ]
        
        with self._conectar() as conn:
            for tabela in tabelas:
                conn.execute(tabela)
            conn.commit()

    def _popular_dados_iniciais(self) -> None:
        with self._conectar() as conn:
            # Verifica se já existem categorias para não duplicar
            if conn.execute("SELECT COUNT(*) FROM categorias").fetchone()[0] == 0:
                categorias = [
                    ('Tradicionais', 'As pizzas mais amadas da casa'),
                    ('Especiais', 'Combinações exclusivas do chef'),
                    ('Vegetarianas', 'Deliciosas opções sem carne')
                ]
                conn.executemany("INSERT INTO categorias (nome, descricao) VALUES (?, ?)", categorias)
                
                # Pizzas de exemplo
                pizzas = [
                    ('Calabresa', 'Pizza clássica de calabresa', 'Calabresa, cebola e mussarela', 1, True),
                    ('Marguerita', 'Pizza tradicional italiana', 'Mussarela, tomate e manjericão', 1, True),
                    ('Vegetariana', 'Pizza recheada de vegetais', 'Berinjela, abobrinha, pimentão e mussarela', 3, True)
                ]
                conn.executemany(
                    "INSERT INTO pizzas (nome, descricao, ingredientes, categoria_id, disponivel) VALUES (?, ?, ?, ?, ?)", 
                    pizzas
                )
                
                # Preços
                precos = [
                    (1, 'P', 35.90), (1, 'M', 45.90), (1, 'G', 55.90),
                    (2, 'P', 38.50), (2, 'M', 48.50), (2, 'G', 58.50),
                    (3, 'P', 42.00), (3, 'M', 52.00), (3, 'G', 62.00)
                ]
                conn.executemany(
                    "INSERT INTO precos (pizza_id, tamanho, valor) VALUES (?, ?, ?)", 
                    precos
                )
                
                conn.commit()

    # --- CLIENTES ---
    def cadastrar_cliente(self, nome: str, telefone: str) -> bool:
        try:
            with self._conectar() as conn:
                conn.execute(
                    "INSERT INTO clientes (nome, telefone) VALUES (?, ?)",
                    (nome.strip(), ''.join(filter(str.isdigit, telefone)))
                )
                conn.commit()
                return True
        except sqlite3.IntegrityError:
            return False
        except sqlite3.Error as e:
            print(f"Erro ao cadastrar cliente: {e}")
            return False

    def buscar_cliente(self, telefone: str) -> Optional[Dict]:
        try:
            with self._conectar() as conn:
                cursor = conn.execute(
                    "SELECT * FROM clientes WHERE telefone = ?",
                    (''.join(filter(str.isdigit, telefone)),)
                )
                return dict(cursor.fetchone()) if cursor.fetchone() else None
        except sqlite3.Error as e:
            print(f"Erro ao buscar cliente: {e}")
            return None

    # --- ENDEREÇOS ---
    def adicionar_endereco(self, cliente_id: int, apelido: str, cep: str, 
                         logradouro: str, numero: str, complemento: str,
                         bairro: str, cidade: str, uf: str) -> bool:
        try:
            with self._conectar() as conn:
                conn.execute('''
                INSERT INTO enderecos 
                (cliente_id, apelido, cep, logradouro, numero, complemento, bairro, cidade, uf)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    cliente_id, apelido, cep, logradouro, numero, 
                    complemento, bairro, cidade, uf
                ))
                conn.commit()
                return True
        except sqlite3.Error as e:
            print(f"Erro ao adicionar endereço: {e}")
            return False

    def listar_enderecos(self, cliente_id: int) -> List[Dict]:
        try:
            with self._conectar() as conn:
                cursor = conn.execute(
                    "SELECT * FROM enderecos WHERE cliente_id = ? ORDER BY apelido",
                    (cliente_id,)
                )
                return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            print(f"Erro ao listar endereços: {e}")
            return []

    # --- CARDÁPIO ---
    def buscar_cardapio(self) -> List[Dict]:
        try:
            with self._conectar() as conn:
                cursor = conn.execute('''
                SELECT p.id, p.nome, p.descricao, p.ingredientes, 
                       c.nome as categoria, p.disponivel
                FROM pizzas p
                JOIN categorias c ON p.categoria_id = c.id
                WHERE p.disponivel = 1
                ORDER BY c.nome, p.nome
                ''')
                return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            print(f"Erro ao buscar cardápio: {e}")
            return []

    def buscar_precos_pizza(self, pizza_id: int) -> List[Dict]:
        try:
            with self._conectar() as conn:
                cursor = conn.execute(
                    "SELECT tamanho, valor FROM precos WHERE pizza_id = ?",
                    (pizza_id,)
                )
                return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            print(f"Erro ao buscar preços: {e}")
            return []

    # --- PEDIDOS ---
    def criar_pedido(self, cliente_id: int, endereco_id: int, 
                    forma_pagamento: str, troco_para: float = 0) -> Optional[int]:
        try:
            with self._conectar() as conn:
                cursor = conn.execute('''
                INSERT INTO pedidos 
                (cliente_id, endereco_id, forma_pagamento, troco_para, valor_total)
                VALUES (?, ?, ?, ?, 0)
                RETURNING id
                ''', (cliente_id, endereco_id, forma_pagamento, troco_para))
                
                pedido_id = cursor.fetchone()[0]
                conn.commit()
                return pedido_id
        except sqlite3.Error as e:
            print(f"Erro ao criar pedido: {e}")
            return None

    def adicionar_item_pedido(self, pedido_id: int, pizza_id: int, 
                            tamanho: str, quantidade: int, 
                            observacoes: str = None) -> bool:
        try:
            # Busca o valor unitário
            valor_unitario = self._buscar_valor_pizza(pizza_id, tamanho)
            if not valor_unitario:
                return False

            with self._conectar() as conn:
                # Adiciona o item
                conn.execute('''
                INSERT INTO itens_pedido
                (pedido_id, pizza_id, tamanho, quantidade, valor_unitario, observacoes)
                VALUES (?, ?, ?, ?, ?, ?)
                ''', (pedido_id, pizza_id, tamanho, quantidade, valor_unitario, observacoes))
                
                # Atualiza o valor total do pedido
                conn.execute('''
                UPDATE pedidos 
                SET valor_total = valor_total + ?
                WHERE id = ?
                ''', (valor_unitario * quantidade, pedido_id))
                
                conn.commit()
                return True
        except sqlite3.Error as e:
            print(f"Erro ao adicionar item: {e}")
            return False

    def _buscar_valor_pizza(self, pizza_id: int, tamanho: str) -> Optional[float]:
        try:
            with self._conectar() as conn:
                cursor = conn.execute(
                    "SELECT valor FROM precos WHERE pizza_id = ? AND tamanho = ?",
                    (pizza_id, tamanho)
                )
                resultado = cursor.fetchone()
                return resultado[0] if resultado else None
        except sqlite3.Error as e:
            print(f"Erro ao buscar valor: {e}")
            return None

    def buscar_pedidos_cliente(self, cliente_id: int, limit: int = 5) -> List[Dict]:
        try:
            with self._conectar() as conn:
                cursor = conn.execute('''
                SELECT p.id, p.data_pedido, p.status, p.valor_total,
                       e.apelido as endereco_apelido
                FROM pedidos p
                JOIN enderecos e ON p.endereco_id = e.id
                WHERE p.cliente_id = ?
                ORDER BY p.data_pedido DESC
                LIMIT ?
                ''', (cliente_id, limit))
                
                return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            print(f"Erro ao buscar pedidos: {e}")
            return []

    def buscar_detalhes_pedido(self, pedido_id: int) -> Optional[Dict]:
        try:
            with self._conectar() as conn:
                # Informações básicas do pedido
                cursor = conn.execute('''
                SELECT p.*, c.nome as cliente_nome, 
                       e.apelido as endereco_apelido, e.logradouro, e.numero,
                       e.complemento, e.bairro, e.cidade, e.uf, e.cep
                FROM pedidos p
                JOIN clientes c ON p.cliente_id = c.id
                JOIN enderecos e ON p.endereco_id = e.id
                WHERE p.id = ?
                ''', (pedido_id,))
                
                pedido = dict(cursor.fetchone())
                
                # Itens do pedido
                cursor = conn.execute('''
                SELECT i.*, p.nome as pizza_nome
                FROM itens_pedido i
                JOIN pizzas p ON i.pizza_id = p.id
                WHERE i.pedido_id = ?
                ''', (pedido_id,))
                
                pedido['itens'] = [dict(row) for row in cursor.fetchall()]
                return pedido
        except sqlite3.Error as e:
            print(f"Erro ao buscar detalhes: {e}")
            return None

    # --- UTILITÁRIOS ---
    def validar_cep(self, cep: str) -> Optional[Dict]:
        try:
            response = requests.get(f'https://viacep.com.br/ws/{cep}/json/')
            if response.status_code == 200:
                dados = response.json()
                return dados if not dados.get('erro') else None
        except requests.RequestException as e:
            print(f"Erro ao validar CEP: {e}")
        return None

    def atualizar_status_pedido(self, pedido_id: int, novo_status: str) -> bool:
        status_validos = {'Recebido', 'Confirmado', 'Em preparo', 'Assando', 'Saiu para entrega', 'Entregue'}
        if novo_status not in status_validos:
            return False
            
        try:
            with self._conectar() as conn:
                conn.execute(
                    "UPDATE pedidos SET status = ? WHERE id = ?",
                    (novo_status, pedido_id)
                )
                conn.commit()
                return True
        except sqlite3.Error as e:
            print(f"Erro ao atualizar status: {e}")
            return False