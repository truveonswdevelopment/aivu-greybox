"""aivu_greybox — inverse identification of envelope and equipment parameters
from commissioning-window telemetry.

Implements `aivu_greybox` v0.1 spec sections 1-12.

This package consumes 1 Hz telemetry from the HPM during the 5-Day commissioning
window (and continuously thereafter in Phase 2 ongoing-Cx mode), and produces
signed posterior records over the six canonical parameters:

    {R_eff, C_house, cfm50, F_slab, C_w, ceiling_coupling_factor}

The signed records become the envelope and HVAC halves of the Digital Birth
Certificate per the spec's §2.3.

Package family:
- aivu_greybox produces the inverse fit.
- aivu_physics + aivu_dynamic produce the forward chain that aivu_greybox
  is the inverse of.
- aivu_corpus produces synthetic test trajectories.
- aivu_integrity provides the signing surfaces this package calls (via
  the _signing_stub module in v0.1 until the post-pilot implementation
  lands in place per §12 INV-SIGN12-5).
"""

__version__ = "0.1.0"
