import sqlite3
import requests
import re
from typing import Optional, Tuple, List, Dict, Union
from datetime import datetime

class BancoDeDados:
    def __init__(self, nome_banco: str = 'pizzaria.db') -> None:
        """Inicializa a conexão com o banco de dados e cria as tabelas necessárias."""
        self.nome_banco = nome_banco
        self._criar_tabelas()
    
    def _conectar(self) -> sqlite3.Connection:
        """Estabelece conexão com o banco de dados e ativa chaves estrangeiras."""
        conn = sqlite3.connect(self.nome_banco)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.row_factory = sqlite3.Row  # Permite acesso às colunas por nome
        return conn
    
    def _criar_tabelas(self) -> None:
        """Cria as tabelas necessárias no banco de dados se não existirem."""
        with self._conectar() as conn:
            # Tabela clientes com constraints melhoradas
            conn.execute('''
            CREATE TABLE IF NOT EXISTS clientes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL CHECK(length(nome) >= 3),
                telefone TEXT NOT NULL UNIQUE CHECK(length(telefone) >= 10),
                cep TEXT NOT NULL CHECK(length(cep) == 8),
                numero_residencial TEXT NOT NULL CHECK(length(numero_residencial) >= 1),
                data_cadastro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')
            
            # Tabela cardápio com constraints de preço
            conn.execute('''
            CREATE TABLE IF NOT EXISTS cardapio (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL UNIQUE CHECK(length(nome) >= 3),
                descricao TEXT NOT NULL CHECK(length(descricao) >= 10),
                ingredientes TEXT NOT NULL CHECK(length(ingredientes) >= 5),
                preco_inteira REAL NOT NULL CHECK(preco_inteira > 0),
                preco_meia REAL CHECK(preco_meia IS NULL OR preco_meia > 0),
                categoria TEXT
            )''')
            
            # Tabela pedidos com constraints e relações
            conn.execute('''
            CREATE TABLE IF NOT EXISTS pedidos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cliente_id INTEGER NOT NULL,
                pizza_id INTEGER NOT NULL,
                tipo TEXT NOT NULL CHECK(tipo IN ('Inteira', 'Meia')),
                quantidade INTEGER NOT NULL CHECK(quantidade > 0),
                valor_total REAL NOT NULL CHECK(valor_total > 0),
                observacoes TEXT,
                status TEXT DEFAULT 'Recebido' CHECK(status IN ('Recebido', 'Preparando', 'Assando', 'Entregue')),
                data_pedido TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (cliente_id) REFERENCES clientes(id) ON DELETE CASCADE,
                FOREIGN KEY (pizza_id) REFERENCES cardapio(id) ON DELETE RESTRICT
            )''')
            
            conn.commit()

    def cadastrar_cliente(self, nome: str, telefone: str, cep: str, numero_residencial: str) -> bool:
        """
        Cadastra um novo cliente no sistema com validações.
        
        Args:
            nome: Nome completo do cliente (mínimo 3 caracteres)
            telefone: Número de telefone (deve ser único)
            cep: CEP da residência (8 dígitos)
            numero_residencial: Número da residência
            
        Returns:
            True se cadastrado com sucesso, False caso contrário
        """
        if not all([nome, telefone, cep, numero_residencial]):
            return False
            
        if not self.validar_cep(cep):
            return False
            
        try:
            with self._conectar() as conn:
                conn.execute('''
                INSERT INTO clientes (nome, telefone, cep, numero_residencial)
                VALUES (?, ?, ?, ?)
                ''', (
                    nome.strip(), 
                    ''.join(filter(str.isdigit, telefone)),  # Remove caracteres não numéricos
                    cep.strip(), 
                    numero_residencial.strip()
                ))
                conn.commit()
                return True
        except sqlite3.IntegrityError:
            return False  # Telefone já cadastrado
        except sqlite3.Error:
            return False

    def buscar_cliente(self, telefone: str) -> Optional[Dict]:
        """
        Busca um cliente pelo telefone.
        
        Args:
            telefone: Número de telefone do cliente
            
        Returns:
            Dicionário com os dados do cliente ou None se não encontrado
        """
        try:
            with self._conectar() as conn:
                cursor = conn.execute('''
                SELECT * FROM clientes WHERE telefone = ?
                ''', (''.join(filter(str.isdigit, telefone)),))
                resultado = cursor.fetchone()
                return dict(resultado) if resultado else None
        except sqlite3.Error:
            return None

    def adicionar_pizza(self, nome: str, descricao: str, ingredientes: str, 
                       preco_inteira: float, preco_meia: Optional[float] = None, 
                       categoria: Optional[str] = None) -> bool:
        """
        Adiciona uma nova pizza ao cardápio.
        
        Args:
            nome: Nome da pizza (único, mínimo 3 caracteres)
            descricao: Descrição da pizza (mínimo 10 caracteres)
            ingredientes: Lista de ingredientes (mínimo 5 caracteres)
            preco_inteira: Preço da pizza inteira (deve ser positivo)
            preco_meia: Preço da meia pizza (opcional, deve ser positivo se informado)
            categoria: Categoria da pizza (opcional)
            
        Returns:
            True se adicionada com sucesso, False caso contrário
        """
        if not all([nome, descricao, ingredientes]) or preco_inteira <= 0:
            return False
            
        if preco_meia is not None and preco_meia <= 0:
            return False

        try:
            with self._conectar() as conn:
                conn.execute('''
                INSERT INTO cardapio (nome, descricao, ingredientes, preco_inteira, preco_meia, categoria)
                VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    nome.strip(), 
                    descricao.strip(), 
                    ingredientes.strip(), 
                    preco_inteira, 
                    preco_meia, 
                    categoria.strip() if categoria else None
                ))
                conn.commit()
                return True
        except sqlite3.IntegrityError:
            return False  # Nome de pizza duplicado
        except sqlite3.Error:
            return False

    def buscar_pizzas(self, apenas_disponiveis: bool = True) -> List[Dict]:
        """
        Retorna todas as pizzas do cardápio.
        
        Args:
            apenas_disponiveis: Se True, retorna apenas pizzas disponíveis
            
        Returns:
            Lista de dicionários com informações das pizzas
        """
        try:
            with self._conectar() as conn:
                query = '''
                SELECT id, nome, descricao, preco_inteira, preco_meia, categoria 
                FROM cardapio
                '''
                if apenas_disponiveis:
                    query += ' WHERE disponivel = 1'
                    
                cursor = conn.execute(query)
                return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error:
            return []

    def buscar_pizza_por_id(self, pizza_id: Union[int, str]) -> Optional[Dict]:
        """
        Busca uma pizza específica por ID.
        
        Args:
            pizza_id: ID da pizza (pode ser string ou inteiro)
            
        Returns:
            Dicionário com informações da pizza ou None se não encontrada
        """
        try:
            pizza_id = int(pizza_id)
        except (ValueError, TypeError):
            return None
            
        try:
            with self._conectar() as conn:
                cursor = conn.execute('''
                SELECT id, nome, descricao, preco_inteira, preco_meia, categoria 
                FROM cardapio 
                WHERE id = ? AND disponivel = 1
                ''', (pizza_id,))
                resultado = cursor.fetchone()
                return dict(resultado) if resultado else None
        except sqlite3.Error:
            return None

    def fazer_pedido(self, cliente_id: Union[int, str], pizza_id: Union[int, str], 
                    tipo: str, quantidade: Union[int, str], 
                    observacoes: Optional[str] = None) -> bool:
        """
        Registra um novo pedido no sistema.
        
        Args:
            cliente_id: ID do cliente
            pizza_id: ID da pizza
            tipo: 'Inteira' ou 'Meia'
            quantidade: Quantidade de pizzas
            observacoes: Observações adicionais (opcional)
            
        Returns:
            True se o pedido foi registrado com sucesso, False caso contrário
        """
        try:
            cliente_id = int(cliente_id)
            pizza_id = int(pizza_id)
            quantidade = int(quantidade)
        except (ValueError, TypeError):
            return False

        if tipo not in ('Inteira', 'Meia') or quantidade <= 0:
            return False

        pizza = self.buscar_pizza_por_id(pizza_id)
        if not pizza:
            return False

        preco = pizza['preco_inteira'] if tipo == 'Inteira' else pizza.get('preco_meia')
        if preco is None:
            return False

        valor_total = preco * quantidade

        try:
            with self._conectar() as conn:
                conn.execute('''
                INSERT INTO pedidos (
                    cliente_id, pizza_id, tipo, quantidade, valor_total, observacoes
                ) VALUES (?, ?, ?, ?, ?, ?)
                ''', (cliente_id, pizza_id, tipo, quantidade, valor_total, observacoes))
                conn.commit()
                return True
        except sqlite3.Error:
            return False

    def buscar_pedidos_cliente(self, cliente_id: Union[int, str]) -> List[Dict]:
        """
        Retorna todos os pedidos de um cliente.
        
        Args:
            cliente_id: ID do cliente
            
        Returns:
            Lista de dicionários com informações dos pedidos
        """
        try:
            cliente_id = int(cliente_id)
        except (ValueError, TypeError):
            return []
            
        try:
            with self._conectar() as conn:
                cursor = conn.execute('''
                SELECT p.id, c.nome as pizza, p.tipo, p.quantidade, p.valor_total, p.status, p.data_pedido
                FROM pedidos p
                JOIN cardapio c ON p.pizza_id = c.id
                WHERE p.cliente_id = ?
                ORDER BY p.data_pedido DESC
                ''', (cliente_id,))
                return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error:
            return []

    def validar_cep(self, cep: str) -> bool:
        """
        Valida o formato e existência do CEP usando a API ViaCEP.
        
        Args:
            cep: CEP a ser validado (apenas dígitos)
            
        Returns:
            True se o CEP é válido, False caso contrário
        """
        if not cep or not isinstance(cep, str) or not cep.isdigit() or len(cep) != 8:
            return False
        
        try:
            response = requests.get(f'https://viacep.com.br/ws/{cep}/json/', timeout=5)
            return response.status_code == 200 and 'erro' not in response.json()
        except requests.RequestException:
            return False

    def verificar_disponibilidade_pizza(self, pizza_id: Union[int, str]) -> bool:
        """
        Verifica se uma pizza está disponível no cardápio.
        
        Args:
            pizza_id: ID da pizza
            
        Returns:
            True se a pizza está disponível, False caso contrário
        """
        try:
            pizza_id = int(pizza_id)
        except (ValueError, TypeError):
            return False
            
        try:
            with self._conectar() as conn:
                cursor = conn.execute('''
                SELECT 1 FROM cardapio WHERE id = ? AND disponivel = 1
                ''', (pizza_id,))
                return cursor.fetchone() is not None
        except sqlite3.Error:
            return False
        
    def popular_cardapio_teste(self) -> None:
        
        pizzas = [
            {
                'nome': 'Calabresa',
                'descricao': 'Pizza com bastante calabresa saborosa.',
                'ingredientes': 'Calabresa, cebola, mussarela',
                'preco_inteira': 39.90,
                'preco_meia': 22.00,
                'categoria': 'Tradicional'
            },
            {
                'nome': 'Marguerita',
                'descricao': 'Pizza clássica com manjericão fresco.',
                'ingredientes': 'Tomate, mussarela, manjericão',
                'preco_inteira': 37.50,
                'preco_meia': 20.00,
                'categoria': 'Vegetariana'
            },
            {
                'nome': 'Frango com Catupiry',
                'descricao': 'Pizza cremosa com frango e catupiry.',
                'ingredientes': 'Frango, catupiry, orégano',
                'preco_inteira': 42.00,
                'preco_meia': 23.00,
                'categoria': 'Premium'
            }
        ]

        for pizza in pizzas:
            self.adicionar_pizza(
                nome=pizza['nome'],
                descricao=pizza['descricao'],
                ingredientes=pizza['ingredientes'],
                preco_inteira=pizza['preco_inteira'],
                preco_meia=pizza['preco_meia'],
                categoria=pizza['categoria']
            )
