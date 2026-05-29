
from PIL import Image

def _parse_float(valor: str, default: float = 0.0) -> float:
    """Converte string de formulário para float de forma segura."""
    try:
        # Garante que substitui vírgula por ponto para o padrão do Python
        return float(str(valor).replace(",", ".").strip())
    except (ValueError, TypeError):
        return default

def validar_imagem_segura(arquivo):
    """Valida se um arquivo de imagem é realmente uma imagem íntegra."""
    try:
        img = Image.open(arquivo)
        img.verify() # Verifica a integridade do arquivo
        arquivo.seek(0) # Reseta o cursor do arquivo para o início
        return True
    except Exception:
        return False