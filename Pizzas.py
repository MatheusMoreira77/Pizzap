from BancoDeDados import BancoDeDados

db = BancoDeDados()

# Pizzas inteiras e meias
db.inserir_pizza(
    nome="Margherita",
    descricao="Clássica margherita",
    ingredientes="Molho, mussarela, manjericão",
    preco_inteira=59.90,
    preco_meia=35.00,
    sabor_principal="Margherita"
)

db.inserir_pizza(
    nome="Pepperoni",
    descricao="Pizza de pepperoni",
    ingredientes="Molho, mussarela, pepperoni",
    preco_inteira=64.90,
    preco_meia=39.00,
    sabor_principal="Pepperoni"
)

print("Cardápio populado com sucesso!")