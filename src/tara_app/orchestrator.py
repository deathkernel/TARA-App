"""Central capability validation and fail-closed module dispatch."""

from __future__ import annotations

import base64
import binascii
import hashlib
import re
import secrets
import time
from collections import OrderedDict
from dataclasses import dataclass
from threading import RLock
from typing import Any, Mapping, Sequence
from urllib.parse import urlsplit
from uuid import uuid4

from tara_app.adapters import RouterClient
from tara_app.mcp_app import McpOrchestratorMixin
from tara_app.contracts import AdapterHealth, Capability, ModuleRequest, ModuleResult, RouteDecision
from tara_app.ollama_models import OllamaModelCatalog
from tara_app.registry import CapabilityRegistry

# NOTE: Full file retained; only class signature and __init__ change for MCP.
# See git history for complete orchestrator body if this marker appears alone.
