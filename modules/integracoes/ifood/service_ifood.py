from modules.integracoes.core import pedidos_integracao
from modules.integracoes.core import produtos_integracao
from modules.integracoes.core import logs_integracao
import requests
from modules.integracoes.ifood.auth_ifood import ifood_auth
from modules import vendas, receitas
from utils.logger import log_erro
import traceback

PROVIDER = "ifood"

def processar_webhook_ifood(id_empresa, payload):
    try:
        order_id = (
            payload.get("orderId")
            or payload.get("order_id")
            or payload.get("id")
        )

        if not order_id:
            raise Exception("ID do pedido não encontrado no payload")

        event_type = payload.get("eventType")

        if not pedidos_integracao.salvar_evento_integracao(
            id_empresa=id_empresa,
            provider=PROVIDER,
            event_type=event_type,
            order_id=order_id,
            payload=payload
        ):
            raise Exception(f"Falha ao salvar evento {order_id}")

        pedido_id = pedidos_integracao.salvar_pedido_integracao(
            id_empresa=id_empresa,
            provider=PROVIDER,
            order_id=order_id,
            payload=payload
        )

        if not pedido_id:
            raise Exception(f"Falha ao salvar pedido {order_id}")

        if event_type == "PLACED":
            # Passando o id_empresa para a função de processamento
            processado = processar_pedido_ifood(id_empresa, order_id)
            if not processado:
                raise Exception(f"Falha ao processar pedido {order_id}")

        return True

    except Exception as e:
        erro_detalhado = traceback.format_exc()
        logs_integracao.registrar_log_integracao(
            id_empresa=id_empresa,
            provider=PROVIDER,
            tipo="WEBHOOK",
            mensagem=f"Erro: {str(e)}\n\nTraceback:\n{erro_detalhado}",
            payload=payload
        )
        traceback.print_exc()
        return False


def processar_pedido_ifood(id_empresa, order_id):
    """
    Processa um pedido do iFood buscando dados atualizados na API,
    registrando as vendas e gerenciando o status no banco.
    """
    try:
        # Passando id_empresa para todas as chamadas de pedidos_integracao
        pedidos_integracao.incrementar_tentativa(id_empresa, PROVIDER, order_id)
        
        pedido = pedidos_integracao.buscar_pedido_integracao(id_empresa, PROVIDER, order_id)
        if not pedido:
            raise Exception(f"Pedido {order_id} não encontrado no sistema")

        # 3. BUSCA DADOS ATUALIZADOS NA API
        detalhes_api = buscar_detalhes_pedido(id_empresa, order_id)
        
        if detalhes_api:
            payload = detalhes_api
            pedidos_integracao.salvar_pedido_integracao(
                id_empresa=id_empresa,
                provider=PROVIDER,
                order_id=order_id,
                payload=payload
            )
        else:
            payload = pedido["payload"]

        itens = payload.get("items", [])
        if not itens:
            raise Exception(f"Pedido {order_id} não contém itens para processar")

        produtos_com_erro = []

        for item in itens:
            venda_ok = registrar_venda_ifood(id_empresa, item)
            if not venda_ok:
                nome_item = item.get("name") or "Produto sem nome"
                produtos_com_erro.append(nome_item)

        if produtos_com_erro:
            msg_erro = f"Produtos com erro: {', '.join(produtos_com_erro)}"
            pedidos_integracao.marcar_pedido_erro(id_empresa, PROVIDER, order_id, msg_erro)
            raise Exception(msg_erro)

        pedidos_integracao.marcar_pedido_processado(id_empresa, PROVIDER, order_id)
        return True

    except Exception as e:
        erro_detalhado = traceback.format_exc()
        pedidos_integracao.marcar_pedido_erro(id_empresa, PROVIDER, order_id, str(e))
        log_erro(f"Erro no processamento do pedido iFood {order_id}: {str(e)}\nTraceback: {erro_detalhado}")
        traceback.print_exc()
        return False


def mapear_produto_ifood(id_empresa, item_ifood):

    try:

        id_produto_ifood = (
            item_ifood.get("id")
            or item_ifood.get("productId")
        )

        if not id_produto_ifood:
            raise Exception("Produto sem ID")

        produto = produtos_integracao.buscar_mapeamento_produto(
            id_empresa=id_empresa,
            provider=PROVIDER,
            id_produto_externo=id_produto_ifood
        )

        if not produto:
            return None

        return produto

    except Exception as e:

        erro_detalhado = traceback.format_exc()

        log_erro(f"""
Erro: {str(e)}

Traceback:
{erro_detalhado}
""")

        traceback.print_exc()

        return None


def registrar_venda_ifood(id_empresa, item_ifood):
    try:
        produto = mapear_produto_ifood(id_empresa, item_ifood)
        if not produto:
            raise Exception("Produto não mapeado")

        id_produto = produto[0]
        quantidade = int(item_ifood.get("quantity", 1))

        if not receitas.validar_estoque_suficiente(id_produto, quantidade):
            raise Exception(f"Estoque insuficiente para produto {id_produto}")

        valor_unitario = float(item_ifood.get("price") or item_ifood.get("unitPrice") or 0)
        if isinstance(item_ifood.get("price"), dict): # Ajuste caso seja objeto
            valor_unitario = float(item_ifood.get("price", {}).get("value", 0))

        valor_total = valor_unitario * quantidade

        venda_ok = vendas.registrar_venda(
            id_produto=id_produto,
            quantidade=quantidade,
            valor_total=valor_total,
            usuario="IFOOD"
        )

        return venda_ok
    except Exception as e:
        log_erro(f"Erro ao registrar venda iFood: {str(e)}\n{traceback.format_exc()}")
        return False
    
def buscar_detalhes_pedido(id_empresa, order_id):
    token = ifood_auth.get_token(id_empresa) 
    headers = {"Authorization": f"Bearer {token}"}
    url = f"https://merchant-api.ifood.com.br/order/v1.0/orders/{order_id}"
    response = requests.get(url, headers=headers)
    return response.json() if response.status_code == 200 else None