@app.route('/admin/status')
def status_sistema():
    # 1. Tamanho do Banco
    tamanho_db = obter_tamanho_banco()
    
    # 2. Informações de Memória (para saber se o servidor está sofrendo)
    import psutil
    memoria = psutil.virtual_memory().percent
    
    return f"""
    <h1>Status do Sistema</h1>
    <p>Uso do Banco: {tamanho_db}</p>
    <p>Uso de RAM do Servidor: {memoria}%</p>
    """