from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from BancoDeDados import BancoDeDados
from datetime import datetime
import re

app = Flask(__name__)
db = BancoDeDados()
db._popular_dados_iniciais()

# Dicionários para controle de estado
cadastro_em_andamento = {}
login_em_andamento = {}
pedido_em_andamento = {}

@app.route("/whatsapp", methods=['POST'])
def whatsapp():
    mensagem = request.form.get('Body', '').strip()
    numero = request.form.get('From').replace('whatsapp:', '')
    
    # Bloqueia mensagens vazias
    if not mensagem:
        resposta = MessagingResponse()
        resposta.message("❌ Mensagem vazia. Por favor, digite algo.")
        return str(resposta)

    resposta = MessagingResponse()
    msg = resposta.message()
    mensagem = mensagem.lower()

    # Verifica se já está logado
    if numero in login_em_andamento:
        processar_pedido(numero, mensagem, msg)
        return str(resposta)

    # Fluxo de cadastro
    if numero in cadastro_em_andamento:
        continuar_cadastro(numero, mensagem, msg)
        return str(resposta)

    # Menu inicial
    if mensagem == 'cadastrar':
        iniciar_cadastro(numero, msg)
    elif mensagem == 'login':
        verificar_login(numero, msg)
    else:
        msg.body("""
        🍕 *Bem-vindo à Pizzaria!*
    📝 Digite *CADASTRAR* para se registrar
    🔐 Digite *LOGIN* para acessar sua conta
        """)
    
    return str(resposta)

def iniciar_cadastro(numero, msg):
    cadastro_em_andamento[numero] = {'etapa': 'nome'}
    msg.body("📝 Qual seu nome? (mínimo 3 letras)")

def continuar_cadastro(numero, mensagem, msg):
    dados = cadastro_em_andamento[numero]
    
    if dados['etapa'] == 'nome':
        dados['nome'] = mensagem.strip()
        dados['etapa'] = 'cep'
        msg.body("📮 Qual o CEP do seu endereço? (somente números)")

    elif dados['etapa'] == 'cep':
        cep = mensagem.strip()
        if not cep.isdigit() or len(cep) != 8:
            msg.body("❌ CEP inválido. Envie apenas 8 números.")
            return
        dados['cep'] = cep
        dados['etapa'] = 'numero'
        msg.body("🏠 Qual o número da residência?")

    elif dados['etapa'] == 'numero':
        dados['numero'] = mensagem.strip()
        dados['etapa'] = 'tipo_residencia'
        msg.body("🏘️ O local é:\n1️⃣ Casa\n2️⃣ Apartamento\n3️⃣ Condomínio\nDigite o número correspondente.")

    elif dados['etapa'] == 'tipo_residencia':
        tipos = {'1': 'Casa', '2': 'Apartamento', '3': 'Condomínio'}
        if mensagem not in tipos:
            msg.body("❌ Opção inválida. Escolha 1, 2 ou 3.")
            return
        dados['tipo'] = tipos[mensagem]
        dados['etapa'] = 'complemento'
        msg.body("🔢 Deseja informar complemento (ex: bloco, andar)? Se não tiver, digite 'não'.")

    elif dados['etapa'] == 'complemento':
        comp = mensagem.strip()
        dados['complemento'] = None if comp.lower() == 'não' else comp
        dados['etapa'] = 'finalizando'
        
        # A PARTE QUE VOCÊ PERGUNTOU VEM AQUI (substitui o que estiver depois desta linha)
        try:
            # Cadastra cliente
            sucesso_cliente = db.cadastrar_cliente(
                nome=dados['nome'],
                telefone=numero
            )
            if not sucesso_cliente:
                msg.body("⚠️ Este número já está cadastrado. Digite *MENU*.")
                del cadastro_em_andamento[numero]
                return

            # Busca cliente para obter ID
            cliente = db.buscar_cliente(numero)
            if not cliente:
                raise Exception("Cliente não encontrado após cadastro")

            # Cadastra endereço com a nova estrutura
            sucesso_endereco = db.adicionar_endereco(
                cliente_id=cliente['id'],
                apelido="Principal",  # Ou permita o usuário definir
                cep=dados['cep'],
                logradouro=dados['logradouro'],
                numero=dados['numero'],
                tipo_residencia=dados['tipo'],
                complemento=dados.get('complemento')
            )

            if sucesso_endereco:
                msg.body(f"""
✅ *Cadastro concluído com sucesso!*
━━━━━━━━━━━━━━━━━
👤 Nome: {dados['nome']}
🏠 Endereço: {dados['tipo']} - {dados['logradouro']}, {dados['numero']}
📎 Complemento: {dados['complemento'] or 'Nenhum'}
━━━━━━━━━━━━━━━━━
Digite *MENU* para começar.
""")
            else:
                msg.body("⚠️ Cliente cadastrado, mas erro ao salvar endereço. Atualize depois.")

        except Exception as e:
            print(f"Erro no cadastro: {e}")
            msg.body("❌ Erro ao finalizar cadastro. Tente novamente.")
        
        del cadastro_em_andamento[numero]


def verificar_login(numero, msg):
    cliente = db.buscar_cliente(numero)
    
    if cliente is None:  # Verificação explícita contra None
        msg.body("""
❌ Número não cadastrado.
Digite *CADASTRAR* para se registrar.
        """)
        return

    if not isinstance(cliente, dict):  # Verificação adicional de tipo
        msg.body("❌ Erro interno no sistema. Por favor, tente novamente.")
        print(f"Erro: cliente retornado não é um dicionário: {cliente}")
        return

    login_em_andamento[numero] = {
        'id': cliente.get('id'),
        'nome': cliente.get('nome', 'Cliente')
    }
    
    msg.body(f"""
🎉 *Login realizado, {cliente.get('nome', 'Cliente')}!*
━━━━━━━━━━━━━━━━━
🍕 Digite *CARDÁPIO* para ver opções
🛒 Digite *PEDIR* para fazer um pedido
━━━━━━━━━━━━━━━━━
""")
def processar_pedido(numero, mensagem, msg):
    if mensagem == 'cardapio':
        mostrar_cardapio(numero, msg)
        return
    
    if mensagem == 'pedir':
        mostrar_cardapio(numero, msg, apenas_inteiras=True)
        return

    if mensagem == 'sair':
        del login_em_andamento[numero]
        msg.body("🚪 Você saiu. Digite *LOGIN* para acessar novamente.")
        return

    if numero not in pedido_em_andamento:
        msg.body("""
        📋 *MENU PRINCIPAL*
        ━━━━━━━━━━━━━━━━━
        🍕 Digite *CARDÁPIO* para ver opções
        🛒 Digite *PEDIR* para fazer um pedido
        🚪 Digite *SAIR* para encerrar
        ━━━━━━━━━━━━━━━━━
        """)
        return

    dados = pedido_em_andamento[numero]
    
    if dados['etapa'] == 'escolher_pizza':
        try:
            escolha = int(mensagem) - 1
            if 0 <= escolha < len(dados['pizzas']):
                pizza = dados['pizzas'][escolha]
                dados.update({
                    'pizza_id': pizza['id'],
                    'pizza_nome': pizza['nome'],
                    'preco_inteira': pizza['preco_inteira'],
                    'preco_meia': pizza['preco_meia'],
                    'etapa': 'escolher_tipo'
                })
                
                if pizza['preco_meia'] is None:  # Se não tem meia pizza
                    dados['tipo'] = 'Inteira'
                    dados['preco'] = pizza['preco_inteira']
                    dados['etapa'] = 'quantidade'
                    msg.body(f"Você escolheu: *{pizza['nome']}*\nQuantas unidades deseja?")
                else:
                    msg.body(f"""
                    🍕 {pizza['nome']}
                    ━━━━━━━━━━━━━━━━━
                    1️⃣ Inteira - R${pizza['preco_inteira']:.2f}
                    2️⃣ Meia - R${pizza['preco_meia']:.2f}
                    ━━━━━━━━━━━━━━━━━
                    Digite *1* ou *2*:
                    """)
            else:
                msg.body("❌ Número inválido. Escolha uma opção do cardápio.")
        except ValueError:
            msg.body("❌ Por favor, digite apenas números.")

    elif dados['etapa'] == 'escolher_tipo':
        if mensagem == '1':
            dados['tipo'] = 'Inteira'
            dados['preco'] = dados['preco_inteira']
        elif mensagem == '2':
            dados['tipo'] = 'Meia'
            dados['preco'] = dados['preco_meia']
        else:
            msg.body("❌ Opção inválida. Digite *1* (Inteira) ou *2* (Meia)")
            return

        dados['etapa'] = 'quantidade'
        msg.body(f"Você escolheu: *{dados['pizza_nome']} ({dados['tipo']})*\nQuantas unidades deseja?")

    elif dados['etapa'] == 'quantidade':
        if mensagem.isdigit() and (quantidade := int(mensagem)) > 0:
            dados['quantidade'] = quantidade
            dados['total'] = quantidade * dados['preco']
            dados['etapa'] = 'confirmar'
            
            msg.body(f"""
            ✅ *RESUMO DO PEDIDO*
            ━━━━━━━━━━━━━━━━━
            🍕 Pizza: {dados['pizza_nome']} ({dados['tipo']})
            🔢 Quantidade: {dados['quantidade']}
            💰 Total: R${dados['total']:.2f}
            ━━━━━━━━━━━━━━━━━
            Digite *CONFIRMAR* para finalizar ou *CANCELAR* para voltar.
            """)
        else:
            msg.body("❌ Quantidade inválida. Digite um número maior que zero.")

    elif dados['etapa'] == 'confirmar':
        if mensagem == 'confirmar':
            try:
                db.fazer_pedido(
                    cliente_id=login_em_andamento[numero]['id'],
                    pizza_id=dados['pizza_id'],
                    tipo=dados['tipo'],
                    quantidade=dados['quantidade']
                )
                msg.body(f"""
                🎉 *PEDIDO CONFIRMADO!*
                ━━━━━━━━━━━━━━━━━
                Seu pedido está sendo preparado e
                chegará em até 50 minutos.
                ━━━━━━━━━━━━━━━━━
                Obrigado pela preferência!
                """)
            except Exception as e:
                print(f"Erro ao registrar pedido: {e}")
                msg.body("❌ Erro ao processar pedido. Tente novamente.")
            
            del pedido_em_andamento[numero]
        else:
            mostrar_cardapio(numero, msg)

def mostrar_cardapio(numero, msg):
    pizzas = db.buscar_pizzas(apenas_disponiveis=True)
    
    if not pizzas:
        msg.body("⚠️ Nenhuma pizza disponível no momento.")
        return

    menu = "🍕 *NOSSO CARDÁPIO* 🍕\n━━━━━━━━━━━━━━━━━\n"
    for idx, pizza in enumerate(pizzas, 1):
        menu += f"{idx}. {pizza['nome']} ({pizza['categoria']})\n"
        menu += f"   📝 {pizza['descricao']}\n"
        menu += f"   🧀 Ingredientes: {pizza['ingredientes']}\n"
        
        # Busca os preços para esta pizza
        precos = db.buscar_precos_pizza(pizza['id'])
        if precos:
            menu += "   💰 Valores: "
            menu += " | ".join([f"{p['tamanho']}: R${p['valor']:.2f}" for p in precos])
            menu += "\n"
        
        menu += "━━━━━━━━━━━━━━━━━\n"
    
    menu += "Digite o *NÚMERO* da pizza desejada ou *VOLTAR*:"
    msg.body(menu)

if __name__ == "__main__":
    app.run(debug=True)