"""AIVU HVAC inverse-identification — pilot subset.

Implements H1 v0.2 (2026-05-18) pilot-scope joint Laplace fit for the two
parameters that define the HVAC half of the Digital Birth Certificate:

- D17_pilot — total delivered cooling capacity bi-quadratic (register-side)
- D20_pilot — EER bi-quadratic (register-side)

v0.1.0 first-cut closes the Pass A synthetic closed-loop validation against
F5 (aivu_physics_phase2). Subsequent versions add the sweep orchestrator,
cross-validation, quality gates, and real-chain integration (Pass B / Pass E)
per H1 v0.2 §9.
"""

__version__ = "0.1.0"
