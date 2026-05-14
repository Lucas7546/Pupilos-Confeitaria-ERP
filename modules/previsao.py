from modules.db import conectar

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
            WHERE data >= CURRENT_DATE - INTERVAL '30 days'
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
                    mp.estoque_atual,
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
                estoque_atual = float(item[2] or 0)
                unidade = item[3]
                qtd_receita = float(item[4] or 0)

                # ==================================================
                # CONSUMO PREVISTO
                # ==================================================
                consumo_previsto = (
                    media_diaria *
                    qtd_receita *
                    dias_previsao
                )

                consumo_diario = (
                    consumo_previsto / dias_previsao
                    if dias_previsao > 0 else 0
                )

                # ==================================================
                # DIAS RESTANTES
                # ==================================================
                dias_restantes = (
                    estoque_atual / consumo_diario
                    if consumo_diario > 0 else 999
                )

                # ==================================================
                # IA DE REPOSIÇÃO
                # ==================================================
                dias_operacao = 15

                necessidade_total = (
                    consumo_diario *
                    dias_operacao
                )

                quantidade_compra = (
                    necessidade_total -
                    estoque_atual
                )

                if quantidade_compra < 0:
                    quantidade_compra = 0

                # ==================================================
                # AGRUPA ITENS REPETIDOS
                # ==================================================
                if id_mp not in previsao_dict:

                    previsao_dict[id_mp] = {
                        "materia_prima": nome_mp,
                        "estoque_atual": round(estoque_atual, 3),
                        "consumo_previsto": round(consumo_previsto, 3),
                        "dias_restantes": round(dias_restantes, 1),
                        "quantidade_compra": round(quantidade_compra, 3),
                        "unidade": unidade
                    }

                else:

                    previsao_dict[id_mp]["consumo_previsto"] += round(
                        consumo_previsto,
                        3
                    )

                    consumo_total = (
                        previsao_dict[id_mp]["consumo_previsto"] /
                        dias_previsao
                    )

                    previsao_dict[id_mp]["dias_restantes"] = round(
                        estoque_atual / consumo_total,
                        1
                    )

        return sorted(
            list(previsao_dict.values()),
            key=lambda x: x["dias_restantes"]
        )

    except Exception as e:
        print(f"Erro previsão IA: {e}")
        return []

    finally:
        if con:
            con.close()