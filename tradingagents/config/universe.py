"""
Target stock universe for the Quantum Trading Agent.

See SPEC §3. Phase 1 baseline uses NVDA only (inherited TradingAgents
pipeline). Phase 3 onward brings in QUANTUM_PURE_PLAYS; Phase 3+ adds
QUANTUM_EXPOSURE.
"""

from __future__ import annotations

QUANTUM_PURE_PLAYS: list[str] = [
    "IONQ",   # IonQ — trapped ion
    "RGTI",   # Rigetti — superconducting
    "QBTS",   # D-Wave — annealing
    "QUBT",   # Quantum Computing Inc — photonic
]

QUANTUM_EXPOSURE: list[str] = [
    "IBM",    # Condor, Heron processors
    "GOOGL",  # Sycamore, Willow
    "MSFT",   # Azure Quantum, topological qubits
    "NVDA",   # NVQLink, CUDA-Q, Ising
    "HON",    # Honeywell / Quantinuum
]

UNIVERSE: list[str] = QUANTUM_PURE_PLAYS + QUANTUM_EXPOSURE
