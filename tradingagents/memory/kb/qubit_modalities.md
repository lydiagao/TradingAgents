# Qubit Modalities Comparison

## Trapped Ion (IonQ, Quantinuum)
- **Gate fidelity**: >99.9% two-qubit gates demonstrated
- **Coherence**: T1/T2 in seconds range (best among all modalities)
- **Connectivity**: All-to-all native connectivity
- **Scaling challenge**: Speed — gate times ~100μs vs ~20ns for superconducting
- **Current leaders**: IonQ (32 algorithmic qubits), Quantinuum H2 (56 qubits, highest QV)

## Superconducting (IBM, Google, Rigetti)
- **Gate fidelity**: ~99.5% two-qubit (improving), 99.95%+ single-qubit
- **Coherence**: T1 ~100μs, T2 ~150μs (improving with materials)
- **Connectivity**: Nearest-neighbor (requires SWAP gates for distant qubits)
- **Scaling advantage**: Fastest gate times, semiconductor fab compatible
- **Current leaders**: IBM Condor (1121 qubits), Google Willow (105 qubits, below-threshold error correction)

## Neutral Atom (QuEra, Atom Computing, Pasqal)
- **Gate fidelity**: ~99.5% improving rapidly
- **Scaling**: Can arrange 1000+ atoms in optical tweezers
- **Connectivity**: Reconfigurable — atoms can be physically moved
- **Advantage**: Potential for very large qubit counts at lower cost
- **Status**: Pre-commercial; QuEra targeting 10,000 qubits by 2026

## Photonic (PsiQuantum, Xanadu, QUBT)
- **Gate fidelity**: Probabilistic gates are the bottleneck
- **Advantage**: Room temperature operation, telecom integration
- **Challenge**: Deterministic two-photon gates remain unsolved at scale
- **Status**: PsiQuantum claims million-qubit path via GlobalFoundries fab

## Topological (Microsoft)
- **Status**: Most speculative. Microsoft claims first topological qubit (2025)
- **Advantage if realized**: Inherently error-protected qubits
- **Challenge**: No independently verified topological qubit yet
