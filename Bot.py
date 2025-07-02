from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from BancoDeDados import BancoDeDados
from datetime import datetime
import re

app = Flask(__name__)
db = BancoDeDados()
db.popular_cardapio_teste()

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
    
    if not mensagem.strip():
        msg.body("❌ Por favor, digite um valor válido.")
        return

    if dados['etapa'] == 'nome':
        nome = mensagem.strip()
        if len(nome) < 3:
            msg.body("❌ Nome muito curto. Digite um nome com pelo menos 3 letras.")
            return
            
        dados['nome'] = ' '.join([word.capitalize() for word in nome.split()])
        dados['etapa'] = 'cep'
        msg.body("📍 Agora, digite seu *CEP* (apenas 8 números):")

    elif dados['etapa'] == 'cep':
        if not re.match(r'^\d{8}$', mensagem):
            msg.body("❌ Formato inválido. Digite 8 números (ex: 12345678)")
        elif not db.validar_cep(mensagem):
            msg.body("⚠️ CEP não encontrado. Por favor, digite novamente:")
        else:
            dados['cep'] = mensagem
            dados['etapa'] = 'numero'
            msg.body("🏠 Agora, digite o *número/identificação* da residência:")

    elif dados['etapa'] == 'numero':
        if not mensagem.strip():
            msg.body("❌ Por favor, digite um número/identificação válido.")
        else:
            try:
                sucesso = db.cadastrar_cliente(
                    nome=dados['nome'],
                    telefone=numero,
                    cep=dados['cep'],
                    numero_residencial=mensagem.upper()
                )
                
                if sucesso:
                    msg.body(f"""
                    ✅ *Cadastro concluído!*
                    ━━━━━━━━━━━━━━━━━
                    Nome: {dados['nome']}
                    Endereço: CEP {dados['cep']}, Nº {mensagem.upper()}
                    ━━━━━━━━━━━━━━━━━
                    Digite *MENU* para ver opções.
                    """)
                else:
                    msg.body("⚠️ Este número já está cadastrado! Digite *MENU*.")
                
                del cadastro_em_andamento[numero]
            except Exception as e:
                print(f"Erro no cadastro: {e}")
                msg.body("❌ Ocorreu um erro. Por favor, inicie novamente.")
                del cadastro_em_andamento[numero]

def verificar_login(numero, msg):
    cliente = db.buscar_cliente(numero)

    # Verifica se algo foi retornado
    if not cliente:
        msg.body("""
❌ Número não cadastrado.
Digite *CADASTRAR* para se registrar.
        """)
        return

    # Verifica se é dicionário e contém os campos esperados
    if isinstance(cliente, dict) and 'id' in cliente and 'nome' in cliente:
        login_em_andamento[numero] = {
            'id': cliente['id'],
            'nome': cliente['nome']
        }
        msg.body(f"""
🎉 *Login realizado, {cliente['nome']}!*
━━━━━━━━━━━━━━━━━
🍕 Digite *CARDÁPIO* para ver opções
🛒 Digite *PEDIR* para fazer um pedido
━━━━━━━━━━━━━━━━━
        """)
    else:
        msg.body("❌ Erro interno no login. Contate o suporte ou tente novamente.")
        print("Erro: formato inesperado em cliente:", cliente)


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

def mostrar_cardapio(numero, msg, apenas_inteiras=False):
    pizzas = db.buscar_pizzas(apenas_disponiveis=True)

    if not pizzas:
        msg.body("⚠️ Nenhuma pizza disponível no momento.")
        return

    menu = "🍕 *NOSSO CARDÁPIO* 🍕\n━━━━━━━━━━━━━━━━━\n"
    for idx, pizza in enumerate(pizzas, 1):
        tem_meia = pizza['preco_meia'] is not None
        menu += f"{idx}. {pizza['nome']}\n"
        menu += f"   💰 Inteira: R${pizza['preco_inteira']:.2f}"
        if tem_meia:
            menu += f" | Meia: R${pizza['preco_meia']:.2f}"
        menu += "\n━━━━━━━━━━━━━━━━━\n"

    menu += "Digite o *NÚMERO* da pizza desejada:"
    msg.body(menu)

    pedido_em_andamento[numero] = {
        'etapa': 'escolher_pizza',
        'pizzas': pizzas
    }


if __name__ == "__main__":
    app.run(debug=True)