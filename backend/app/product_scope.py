"""Generic product scope for the InspectIQ manufacturing-quality demo.

The app accepts photos of any physical product, including household objects used
as convenient test fixtures. The selected batch is operational context only; it
does not restrict the visual classifier to a particular product family.
"""

FACTORY_NAME = "Northstar Manufacturing"
SUPPORTED_PRODUCT_NAME = "General Product / Test Item"
SUPPORTED_PRODUCT_FAMILY = "any physical product or manufactured item"


class ProductScopeError(ValueError):
    """Retained for compatibility with callers; generic image intake does not reject product families."""
