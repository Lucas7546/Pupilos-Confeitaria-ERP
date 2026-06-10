from modules.tenant_db import db_conn
from utils.logger import log_info, log_erro
from modules.tenant import get_empresa_id
# =========================================================
# CONFIG EMPRESA
# =========================================================
def get_config_empresa() -> str:

    try:

        id_empresa = get_empresa_id()

        with db_conn() as conn:

            with conn.cursor() as cur:

                cur.execute(
                    """
                    SELECT regime_fiscal
                    FROM empresa_config
                    WHERE id_empresa = %s
                    LIMIT 1
                    """,
                    (id_empresa,)
                )

                resultado = cur.fetchone()

        return resultado[0] if resultado else "MEI"

    except Exception as e:

        log_erro(
            f"Erro ao buscar config empresa: {e}"
        )

        return "MEI"


def atualizar_regime_fiscal(
    novo_regime: str
) -> None:

    try:

        id_empresa = get_empresa_id()

        with db_conn() as conn:

            with conn.cursor() as cur:

                cur.execute(
                    """
                    UPDATE empresa_config
                    SET regime_fiscal = %s
                    WHERE id_empresa = %s
                    """,
                    (
                        novo_regime,
                        id_empresa
                    )
                )

            

        log_info(
            f"Regime fiscal atualizado empresa {id_empresa}"
        )

    except Exception as e:

        log_erro(
            f"Erro ao atualizar regime fiscal: {e}"
        )

# =========================================================
# CÁLCULO DE IMPOSTO
# =========================================================
_ALIQUOTAS = {"MEI": 0.04, "ME": 0.08, "SN": 0.12}


def calcular_imposto(faturamento: float, regime: str | None = None) -> float:
    if not regime:
        regime = get_config_empresa()
    aliquota = _ALIQUOTAS.get(regime, 0.10)
    return faturamento * aliquota


# =========================================================
# BASE FINANCEIRA OPERACIONAL
# =========================================================
def financeiro_operacional(periodo_dias: int = 30) -> dict:

    try:

        id_empresa = get_empresa_id()

        with db_conn() as conn:

            with conn.cursor() as cur:

                # Faturamento

                cur.execute(
                    """
                    SELECT COALESCE(
                        SUM(valor_total),
                        0
                    )
                    FROM vendas
                    WHERE data_venda >= CURRENT_DATE - CAST(%s AS INTERVAL)
                    AND id_empresa = %s
                    """,
                    (
                        f"{periodo_dias} days",
                        id_empresa
                    ),
                )

                faturamento = float(
                    cur.fetchone()[0]
                )

                # Custo dos insumos

                cur.execute(
                    """
                    SELECT COALESCE(
                        SUM(
                            iv.quantidade
                            * r.quantidade_utilizada
                            * mp.preco_unitario
                        ),
                        0
                    )
                    FROM vendas v
                    JOIN itens_venda iv
                        ON iv.id_venda = v.id_venda
                    JOIN receitas r
                        ON r.id_produto = iv.id_produto
                    JOIN materia_prima mp
                        ON mp.id_materia_prima = r.id_materia_prima
                    WHERE v.data_venda >= CURRENT_DATE - CAST(%s AS INTERVAL)
                    AND v.id_empresa = %s
                    """,
                    (
                        f"{periodo_dias} days",
                        id_empresa
                    ),
                )

                custo_insumos = float(
                    cur.fetchone()[0]
                )

                # Despesas

                cur.execute(
                    """
                    SELECT COALESCE(
                        SUM(valor),
                        0
                    )
                    FROM despesas
                    WHERE data_despesa >= CURRENT_DATE - CAST(%s AS INTERVAL)
                    AND id_empresa = %s
                    """,
                    (
                        f"{periodo_dias} days",
                        id_empresa
                    ),
                )

                total_fixas = float(
                    cur.fetchone()[0]
                )

        lucro_base = (
            faturamento
            - custo_insumos
            - total_fixas
        )

        return {
            "faturamento": faturamento,
            "custo_insumos": custo_insumos,
            "total_fixas": total_fixas,
            "lucro_base": lucro_base,
        }

    except Exception as e:

        log_erro(
            f"Erro no cálculo financeiro operacional: {e}"
        )

        return {
            "faturamento": 0.0,
            "custo_insumos": 0.0,
            "total_fixas": 0.0,
            "lucro_base": 0.0,
        }

# =========================================================
# RELATÓRIO FISCAL COM SIMULAÇÕES DE REGIME
# =========================================================
def relatorio_fiscal(periodo_dias: int = 30) -> dict:
    base = financeiro_operacional(periodo_dias)
    regime_atual = get_config_empresa()
    faturamento = base["faturamento"]
    lucro_base = base["lucro_base"]

    imposto_atual = calcular_imposto(faturamento, regime_atual)
    lucro_atual = lucro_base - imposto_atual

    simulacoes = []
    for regime, aliquota in _ALIQUOTAS.items():
        imposto_sim = faturamento * aliquota
        lucro_sim = lucro_base - imposto_sim
        simulacoes.append(
            {
                "regime": regime,
                "aliquota": aliquota,
                "imposto": imposto_sim,
                "lucro": lucro_sim,
                "diferenca": lucro_sim - lucro_atual,
            }
        )

    return {
        "regime_atual": regime_atual,
        "faturamento": faturamento,
        "lucro_atual": lucro_atual,
        "imposto_atual": imposto_atual,
        "simulacoes": simulacoes,
    }


# =========================================================
# FINANCEIRO COMPLETO COM IMPOSTO (USADO EM FINANCEIRO.HTML)
# =========================================================
def calcular_financeiro_com_imposto(periodo_dias: int = 30) -> dict:
    base = financeiro_operacional(periodo_dias)
    regime = get_config_empresa()
    imposto = calcular_imposto(base["faturamento"], regime)
    return {
        **base,
        "imposto": imposto,
        "regime": regime,
        "lucro_final": base["lucro_base"] - imposto,
    }


def registrar_despesa(
    descricao,
    valor
):

    try:

        id_empresa = get_empresa_id()

        with db_conn() as conn:

            with conn.cursor() as cur:

                cur.execute(
                    """
                    INSERT INTO despesas
                    (
                        descricao,
                        valor,
                        data_despesa,
                        id_empresa
                    )
                    VALUES
                    (
                        %s,
                        %s,
                        CURRENT_DATE,
                        %s
                    )
                    """,
                    (
                        descricao,
                        valor,
                        id_empresa
                    )
                )

           

        return True

    except Exception as e:

        log_erro(
            f"Erro ao salvar despesa: {e}"
        )

        return False

def listar_despesas():

    try:

        id_empresa = get_empresa_id()

        with db_conn() as conn:

            with conn.cursor() as cur:

                cur.execute(
                    """
                    SELECT
                        id_despesa,
                        descricao,
                        valor,
                        TO_CHAR(
                            data_despesa,
                            'DD/MM/YYYY'
                        )
                    FROM despesas
                    WHERE id_empresa = %s
                    ORDER BY data_despesa DESC
                    """,
                    (id_empresa,)
                )

                return cur.fetchall() or []

    except Exception as e:

        log_erro(
            f"Erro ao listar despesas: {e}"
        )

        return []
    


def get_fluxo_caixa(
    periodo_dias: int = 30
) -> dict:

    base = financeiro_operacional(
        periodo_dias
    )

    try:

        id_empresa = get_empresa_id()

        with db_conn() as conn:

            with conn.cursor() as cur:

                cur.execute(
                    """
                    SELECT
                        data_venda AS data,
                        'Venda' AS descricao,
                        'ENTRADA' AS tipo,
                        valor_total AS valor,
                        'VENDAS' AS categoria,
                        'PIX' AS metodo,
                        'CONFIRMADO' AS status
                    FROM vendas
                    WHERE data_venda >= CURRENT_DATE - CAST(%s AS INTERVAL)
                    AND id_empresa = %s

                    UNION ALL

                    SELECT
                        data_despesa,
                        descricao,
                        'SAIDA',
                        valor,
                        'DESPESA',
                        'BOLETO',
                        'CONFIRMADO'
                    FROM despesas
                    WHERE data_despesa >= CURRENT_DATE - CAST(%s AS INTERVAL)
                    AND id_empresa = %s

                    ORDER BY data DESC
                    """,
                    (
                        f"{periodo_dias} days",
                        id_empresa,
                        f"{periodo_dias} days",
                        id_empresa
                    )
                )

                movimentacoes = cur.fetchall()

        return {
            **base,
            "movimentacoes": [
                {
                    "data": m[0],
                    "descricao": m[1],
                    "tipo": m[2],
                    "valor": float(m[3]),
                    "categoria": m[4],
                    "metodo": m[5],
                    "status": m[6],
                }
                for m in movimentacoes
            ]
        }

    except Exception as e:

        log_erro(
            f"Erro fluxo caixa: {e}"
        )

        return {
            **base,
            "movimentacoes": []
        }