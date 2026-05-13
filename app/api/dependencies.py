from app.services.b3_service import B3Service
from app.services.cache import DataCache

# Single instances shared across the application
cache = DataCache()
b3_service = B3Service()
