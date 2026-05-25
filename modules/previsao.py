from modules.db import conectar
from modules.estoque import calcular_estoque
from utils.logger import log_info, log_erro


def prever_consumo_materia_prima(dias_previsao=7):
    con = None
    try:
        con = conectar()
        cur = con.cursor()

        # ==================================================
        # MÉDIA DE VENDAS DOS ÚLTIMOS 30 DIAS
        # ==================================================
        cur.execute("""
            SELECT
                id_produto,
                COALESCE(SUM(quantidade), 0) / 30.0 AS media_diaria
            FROM vendas
            WHERE data_venda >= CURRENT_DATE - INTERVAL '30 days'
            GROUP BY id_produto
        """)

        vendas_media = cur.fetchall()
        previsao_dict = {}

        for venda in vendas_media:
            id_produto = venda[0]
            media_diaria = float(venda[1] or 0)

            # ==================================================
            # BUSCA RECEITA DO PRODUTO
            # ==================================================
            cur.execute("""
                SELECT
                    mp.id_materia_prima,
                    mp.nome,
                    mp.unidade_medida,
                    r.quantidade_utilizada
                FROM receitas r
                JOIN materia_prima mp
                    ON mp.id_materia_prima = r.id_materia_prima
                WHERE r.id_produto = %s
            """, (id_produto,))

            ingredientes = cur.fetchall()

            for item in ingredientes:
                id_mp = item[0]
                nome_mp = item[1]
                unidade = item[2]
                qtd_receita = float(item[3] or 0)

                # Estoque real
                estoque_atual = calcular_estoque(id_mp)

                # Cálculos
                consumo_previsto = media_diaria * qtd_receita * dias_previsao
                consumo_diario = (consumo_previsto / dias_previsao) if dias_previsao > 0 else 0
                dias_restantes = (estoque_atual / consumo_diario) if consumo_diario > 0 else 999
                
                # IA de reposição
                dias_operacao = 15
                necessidade_total = consumo_diario * dias_operacao
                quantidade_compra = max(necessidade_total - estoque_atual, 0)

                # ==========================================
                # AGRUPA ITENS
                # ==========================================
                if id_mp not in previsao_dict:
                    previsao_dict[id_mp] = {
                        "materia_prima": nome_mp,
                        "estoque_atual": round(estoque_atual, 3),
                        "consumo_previsto": round(consumo_previsto, 3),
                        "dias_restantes": round(dias_restantes, 1),
                        "sugestao_compra": round(quantidade_compra, 3),
                        "media_diaria": round(consumo_diario, 3),
                        "unidade": unidade
                    }
                else:
                    previsao_dict[id_mp]["consumo_previsto"] += round(consumo_previsto, 3)
                    consumo_total = (previsao_dict[id_mp]["consumo_previsto"] / dias_previsao)
                    previsao_dict[id_mp]["dias_restantes"] = round(estoque_atual / consumo_total, 1) if consumo_total > 0 else 999

        log_info(f"Previsão de demanda processada com sucesso para {len(previsao_dict)} insumos.")
        return sorted(list(previsao_dict.values()), key=lambda x: x["dias_restantes"])

    except Exception as e:
        log_erro(f"Erro ao processar previsão de demanda IA: {e}")
        return []

    finally:
        if con:
            con.close()