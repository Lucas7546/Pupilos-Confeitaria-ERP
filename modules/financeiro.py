from modules.db import get_conn
from utils.logger import log_info, log_erro

# =========================================================
# CONFIG EMPRESA
# =========================================================
def get_config_empresa() -> str:
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT regime_fiscal FROM empresa_config ORDER BY id ASC LIMIT 1"
                )
                resultado = cur.fetchone()
        return resultado[0] if resultado else "MEI"
    except Exception as e:
        log_erro(f"Erro ao buscar config empresa: {e}")
        return "MEI"


def atualizar_regime_fiscal(novo_regime: str) -> None:
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE empresa_config
                    SET regime_fiscal = %s
                    WHERE id = (SELECT id FROM empresa_config ORDER BY id ASC LIMIT 1)
                    """,
                    (novo_regime,),
                )
            conn.commit()
        log_info(f"Regime fiscal atualizado para: {novo_regime}")
    except Exception as e:
        log_erro(f"Erro ao atualizar regime fiscal: {e}")


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
# Bug corrigido: a query de custo de insumos estava fazendo JOIN
# em itens_venda.id_produto com materia_prima.id_materia_prima —
# tipos diferentes que nunca vão cruzar. Corrigido via receitas.
# calcular_financeiro (duplicata) foi removido — use esta função.
# =========================================================
def financeiro_operacional(periodo_dias: int = 30) -> dict:
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                # Faturamento do período
                cur.execute(
                    """
                    SELECT COALESCE(SUM(valor_total), 0)
                    FROM vendas
                    WHERE data_venda >= CURRENT_DATE - CAST(%s AS INTERVAL)
                    """,
                    (f"{periodo_dias} days",),
                )
                faturamento = float(cur.fetchone()[0])

                # Custo de insumos: quantidade vendida × qtd na receita × preço da MP
                # Corrigido: percorre vendas → itens_venda → receitas → materia_prima
                cur.execute(
                    """
                    SELECT COALESCE(SUM(iv.quantidade * r.quantidade_utilizada * mp.preco_unitario), 0)
                    FROM vendas v
                    JOIN itens_venda iv ON iv.id_venda = v.id_venda
                    JOIN receitas r ON r.id_produto = iv.id_produto
                    JOIN materia_prima mp ON mp.id_materia_prima = r.id_materia_prima
                    WHERE v.data_venda >= CURRENT_DATE - CAST(%s AS INTERVAL)
                    """,
                    (f"{periodo_dias} days",),
                )
                custo_insumos = float(cur.fetchone()[0])

                # Despesas do período
                cur.execute(
                    """
                    SELECT COALESCE(SUM(valor), 0)
                    FROM despesas
                    WHERE data_despesa >= CURRENT_DATE - CAST(%s AS INTERVAL)
                    """,
                    (f"{periodo_dias} days",),
                )
                total_fixas = float(cur.fetchone()[0])

        lucro_base = faturamento - custo_insumos - total_fixas
        return {
            "faturamento": faturamento,
            "custo_insumos": custo_insumos,
            "total_fixas": total_fixas,
            "lucro_base": lucro_base,
        }
    except Exception as e:
        log_erro(f"Erro no cálculo financeiro operacional: {e}")
        return {"faturamento": 0.0, "custo_insumos": 0.0, "total_fixas": 0.0, "lucro_base": 0.0}


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


def registrar_despesa(descricao, valor):
    try:
        with get_conn() as con:
            with con.cursor() as cur:
                cur.execute(
                    "INSERT INTO despesas (descricao, valor, data_despesa) VALUES (%s,%s,CURRENT_DATE)",
                    (descricao, valor)
                )
            con.commit()
        return True
    except Exception as e:
        log_erro(f"Erro ao salvar despesa: {e}")
        return False

def listar_despesas():
    try:
        with get_conn() as con:
            with con.cursor() as cur:
                cur.execute("""
                    SELECT id_despesa, descricao, valor, TO_CHAR(data_despesa,'DD/MM/YYYY')
                    FROM despesas ORDER BY data_despesa DESC
                """)
                return cur.fetchall() or []
    except Exception as e:
        log_erro(f"Erro ao listar despesas: {e}")
        return []