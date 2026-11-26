# Integration Observability Reference

Reference implementation of rule-based notifications (skipped executions,
SLA breaches, errors) and anomaly detection (seasonal baseline and isolation
forest) for scheduled integrations between legacy and modern systems.

## Why

Integration failures in legacy environments can silently interrupt critical
business processes while leaving operators with incomplete or delayed signals.
Consistent monitoring makes missed executions, SLA degradation, and failures
visible early, which can help reduce recovery time and increase confidence in 
cross-system data flow.

## How it works

- Synthetic data generator (no real or proprietary data)
- Rule engine: `skipped`, `sla_breach`, `error`
- Anomaly detection: robust z-score per integration and hour of day

## Run

```bash
pip install -r requirements.txt
python main.py
pytest
```

Running `main.py` also writes the generated notifications to
`notifications.csv`.

## Notes

All code and data are generic and synthetic, developed independently. Parts of
this code were drafted with AI assistance and reviewed, tested, and adapted by
the author.

## License

MIT (see LICENSE)
