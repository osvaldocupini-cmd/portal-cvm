from app.services.b3_service import B3Service
from app.services.cache import DataCache
from app.services.reference_data_service import ReferenceDataService

# Single instances shared across the application
cache = DataCache()
b3_service = B3Service()
reference_data = ReferenceDataService()
