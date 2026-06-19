from modules.integracoes.core import pedidos_integracao
from modules.integracoes.core.dispatcher import PEDIDO_PROCESSORS
from utils.logger import log_erro
import traceback


def reprocessar_pedido(provider, order_id):

    try:

        if not provider:
            raise Exception("provider inválido")

        if not order_id:
            raise Exception("order_id inválido")

        provider = provider.lower()

        pedido = pedidos_integracao.buscar_pedido_integracao(
            provider,
            order_id
        )

        if not pedido:
            raise Exception(
                f"Pedido {order_id} não encontrado"
            )

        processador = PEDIDO_PROCESSORS.get(provider)

        if not processador:
            raise Exception(
                f"Provider não suportado: {provider}"
            )

        sucesso = processador(order_id)

        if not sucesso:
            raise Exception(
                f"Falha ao reprocessar pedido {order_id}"
            )

        return True

    except Exception as e:

        erro_detalhado = traceback.format_exc()

        log_erro(
            f"""
Erro: {str(e)}

Traceback:
{erro_detalhado}
"""
        )

        traceback.print_exc()

        return False