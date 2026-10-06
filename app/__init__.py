from pathlib import Path
from dotenv import load_dotenv

# Configuração comum à API, ao seed e às migrações; o ambiente tem prioridade.
load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)
