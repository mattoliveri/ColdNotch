"""Point d'entrée CLI : `python -m simulator [--out ...] [--report ...] [--bots N] [--seed S]`."""

from .runner import main

raise SystemExit(main())
