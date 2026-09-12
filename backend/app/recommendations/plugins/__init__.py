"""Recommendation plugins."""
from .base import BasePlugin
from .living_areas import LivingAreasPlugin
from .housing_agencies import HousingAgenciesPlugin
from .movers import MoversPlugin
from .schools import SchoolsPlugin
from .banks import BanksPlugin
from .insurance import InsurancePlugin
from .electricity import ElectricityPlugin
from .medical import MedicalPlugin
from .telecom import TelecomPlugin
from .childcare import ChildcarePlugin
from .storage import StoragePlugin
from .transport import TransportPlugin
from .language_integration import LanguageIntegrationPlugin
from .legal_admin import LegalAdminPlugin
from .tax_finance import TaxFinancePlugin
from .pets import PetsPlugin
from .partner_career import PartnerCareerPlugin
from .temp_accommodation import TempAccommodationPlugin

__all__ = [
    "BasePlugin",
    "LivingAreasPlugin",
    "HousingAgenciesPlugin",
    "MoversPlugin",
    "SchoolsPlugin",
    "BanksPlugin",
    "InsurancePlugin",
    "ElectricityPlugin",
    "MedicalPlugin",
    "TelecomPlugin",
    "ChildcarePlugin",
    "StoragePlugin",
    "TransportPlugin",
    "LanguageIntegrationPlugin",
    "LegalAdminPlugin",
    "TaxFinancePlugin",
    "PetsPlugin",
    "PartnerCareerPlugin",
    "TempAccommodationPlugin",
]
