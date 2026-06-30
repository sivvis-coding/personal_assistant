"""Integration link domain module."""

from app.domain.integration_link.aggregate import IntegrationLink
from app.domain.integration_link.value_objects import RelationType

__all__ = [
    "IntegrationLink",
    "RelationType",
]