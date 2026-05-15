from modules.db import conectar


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
# 2. CONFIG EMPRESA (REGIME FISCAL)
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

    row = cur.fetchone()
    con.close()

    return row[0] if row else "MEI"

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
# 4. IMPOSTO
# =========================================================
def calcular_imposto(faturamento):
    regime = get_config_empresa()

    aliquotas = {
        "MEI": 0.04,
        "ME": 0.08,
        "SN": 0.12
    }

    return faturamento * aliquotas.get(regime, 0.10)

# =========================================================
# 5. FINANCEIRO OPERACIONAL (TELA /financeiro)
# =========================================================
def financeiro_operacional(periodo_dias=30):
    base = calcular_financeiro(periodo_dias)

    lucro_final = base["lucro_base"]

    return {
        **base,
        "lucro_final": lucro_final
    }


# =========================================================
# 6. RELATÓRIO FISCAL (TELA /relatorio-financeiro)
# =========================================================
def relatorio_fiscal(periodo_dias=30):
    base = calcular_financeiro(periodo_dias)

    regime = get_config_empresa()
    faturamento = base["faturamento"]

    # simulações
    regimes = {
        "MEI": 0.04,
        "ME": 0.08,
        "SN": 0.12
    }

    simulacoes = []

    for nome, aliq in regimes.items():
        imposto = faturamento * aliq
        lucro = base["lucro_base"] - imposto

        simulacoes.append({
            "regime": nome,
            "aliquota": aliq,
            "imposto": imposto,
            "lucro": lucro
        })

    imposto_atual = calcular_imposto(faturamento)
    lucro_atual = base["lucro_base"] - imposto_atual

    return {
        "regime_atual": regime,
        "faturamento": faturamento,
        "lucro_atual": lucro_atual,
        "imposto_atual": imposto_atual,
        "simulacoes": simulacoes
    }