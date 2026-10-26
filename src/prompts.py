"""Prompt snippets shared by every pipeline stage."""

CLEARANCE_RULES = """Printer tolerances (this printer's holes print undersize):
- Put a global `clearance = 0.3;` variable at the top of the SCAD (to be confirmed on the real
  metal shaft). Apply it to every hole or socket that mates with another part, e.g. the shaft
  socket uses `shaft_d + clearance`. For printed-to-printed fits use 0.4 instead
  (`clearance_pp = 0.4;`).
- Keep all dimensions as parametric variables at the top. The shaft is a 6 mm D-shaft."""


def hints_block(hints):
    if not hints:
        return ""
    return f"The user's own description of the part (trust it over your reading of the photo):\n\"{hints}\"\n"
