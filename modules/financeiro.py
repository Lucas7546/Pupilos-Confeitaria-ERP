from modules.db import conectar




# =========================================================
# CONFIG EMPRESA
# =========================================================
def get_config_empresa():
    con = conectar()
    cur = con.cursor()

    cur.execute("""
        SELECT regime_fiscal
        FROM empresa_config
        ORDER BY id ASC
        LIMIT 1
    """)

    resultado = cur.fetchone()
    con.close()

    return resultado[0] if resultado else "MEI"


# =========================================================
# 3. ATUALIZAR REGIME
# =========================================================
def atualizar_regime_fiscal(novo_regime):
    con = conectar()
    cur = con.cursor()

    cur.execute("""
        UPDATE empresa_config
        SET regime_fiscal = %s
        WHERE id = (SELECT id FROM empresa_config ORDER BY id ASC LIMIT 1)
    """, (novo_regime,))

    con.commit()
    con.close()

# =========================================================
# IMPOSTO
# =========================================================
def calcular_imposto(faturamento, regime=None):
    if not regime:
        regime = get_config_empresa()

    if regime == "MEI":
        aliquota = 0.04
    elif regime == "ME":
        aliquota = 0.08
    elif regime == "SN":
        aliquota = 0.12
    else:
        aliquota = 0.10

    return faturamento * aliquota
## =========================================================
# FINANCEIRO OPERACIONAL (DASHBOARD)
# =========================================================
def financeiro_operacional(periodo_dias=30):
    con = conectar()
    cur = con.cursor()

    cur.execute("""
        SELECT COALESCE(SUM(valor_total), 0)
        FROM vendas
        WHERE data_venda >= CURRENT_DATE - INTERVAL %s
    """, (f"{periodo_dias} days",))

    faturamento = float(cur.fetchone()[0])

    cur.execute("""
        SELECT COALESCE(SUM(i.quantidade * mp.preco_unitario), 0)
        FROM itens_venda i
        JOIN materia_prima mp ON mp.id_materia_prima = i.id_produto
    """)

    custo_insumos = float(cur.fetchone()[0])

    cur.execute("""
        SELECT COALESCE(SUM(valor), 0)
        FROM despesas
        WHERE data_despesa >= CURRENT_DATE - INTERVAL %s
    """, (f"{periodo_dias} days",))

    total_fixas = float(cur.fetchone()[0])

    con.close()

    lucro_base = faturamento - custo_insumos - total_fixas

    return {
        "faturamento": faturamento,
        "custo_insumos": custo_insumos,
        "total_fixas": total_fixas,
        "lucro_base": lucro_base
    }


# =========================================================
# 1. BASE FINANCEIRA OPERACIONAL
# =========================================================
def calcular_financeiro(periodo_dias=30):
    con = conectar()
    cur = con.cursor()

    # FATURAMENTO
    cur.execute("""
        SELECT COALESCE(SUM(valor_total), 0)
        FROM vendas
        WHERE data_venda >= CURRENT_DATE - INTERVAL %s
    """, (f"{periodo_dias} days",))
    faturamento = float(cur.fetchone()[0])

    # CUSTO INSUMOS
    cur.execute("""
        SELECT COALESCE(SUM(i.quantidade * mp.preco_unitario), 0)
        FROM itens_venda i
        JOIN materia_prima mp ON mp.id_materia_prima = i.id_produto
    """)
    custo_insumos = float(cur.fetchone()[0])

    # DESPESAS FIXAS
    cur.execute("""
        SELECT COALESCE(SUM(valor), 0)
        FROM despesas
        WHERE data_despesa >= CURRENT_DATE - INTERVAL %s
    """, (f"{periodo_dias} days",))
    total_fixas = float(cur.fetchone()[0])

    con.close()

    lucro_base = faturamento - custo_insumos - total_fixas

    return {
        "faturamento": faturamento,
        "custo_insumos": custo_insumos,
        "total_fixas": total_fixas,
        "lucro_base": lucro_base
    }

# =========================================================
# RELATÓRIO FISCAL (RELATORIO.HTML)
# =========================================================
def relatorio_fiscal(periodo_dias=30):
    base = financeiro_operacional(periodo_dias)

    regime_atual = get_config_empresa()
    faturamento = base["faturamento"]
    lucro_base = base["lucro_base"]

    imposto_atual = calcular_imposto(faturamento, regime_atual)
    lucro_atual = lucro_base - imposto_atual

    regimes = ["MEI", "ME", "SN"]

    simulacoes = []

    for r in regimes:
        imposto_simulado = calcular_imposto(faturamento, r)
        lucro_simulado = lucro_base - imposto_simulado

        simulacoes.append({
            "regime": r,
            "imposto": imposto_simulado,
            "lucro": lucro_simulado,
            "diferenca": lucro_simulado - lucro_atual,
            "aliquota": 0.04 if r == "MEI" else 0.08 if r == "ME" else 0.12
        })

    return {
        "regime_atual": regime_atual,
        "faturamento": faturamento,
        "lucro_atual": lucro_atual,
        "imposto_atual": imposto_atual,
        "simulacoes": simulacoes
    }

# =========================================================
# FINANCEIRO COMPLETO (FINANCEIRO.HTML)
# =========================================================
def calcular_financeiro_com_imposto(periodo_dias=30):
    base = financeiro_operacional(periodo_dias)

    regime = get_config_empresa()
    imposto = calcular_imposto(base["faturamento"], regime)

    lucro_final = base["lucro_base"] - imposto

    return {
        **base,
        "imposto": imposto,
        "regime": regime,
        "lucro_final": lucro_final
    }