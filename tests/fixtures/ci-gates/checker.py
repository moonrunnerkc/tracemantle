"""Candidate-only checker override; never execute imported candidate code."""
raise RuntimeError("Candidate checker executed instead of treating it as data")
