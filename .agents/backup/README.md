# Agent Backup Directory

Timestamped snapshots of `.agents/*.ts` files for rollback.
Each snapshot is a directory named `snapshot-YYYYMMDD-HHMMSS` containing
copies of all agent definition files at that point in time.

## Usage

```bash
# Create a snapshot before modifying agents
python scripts/agent-snapshot.py

# Validate agents after changes
python scripts/agent-validate.py

# Rollback to a snapshot
python scripts/agent-rollback.py --snapshot snapshot-YYYYMMDD-HHMMSS

# List available snapshots
python scripts/agent-rollback.py --list
```
