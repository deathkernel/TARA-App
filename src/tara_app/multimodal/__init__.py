"""TN-86B multimodal input contracts and cognitive bridge."""

from .bridge import MultimodalCognitiveBridge
from .models import Modality, MultimodalObservation
from .pipeline import MultimodalInputPipeline

__all__ = [
    "Modality",
    "MultimodalCognitiveBridge",
    "MultimodalInputPipeline",
    "MultimodalObservation",
]
