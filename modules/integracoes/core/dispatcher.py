from modules.integracoes.ifood.service_ifood import ( processar_webhook_ifood, processar_pedido_ifood)

WEBHOOK_PROCESSORS = {
    "ifood": processar_webhook_ifood }

PEDIDO_PROCESSORS = {
    "ifood": processar_pedido_ifood }