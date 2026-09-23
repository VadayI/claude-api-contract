# Template sync

Follow the complete local `docs/ai/workflows/update-from-template.md` procedure.
Inventory the project lineage, selected source revision, custom instructions and
manifest before proposing changes. Include legacy skills/commands in the report
using migration-inventory.json; do not treat an unmigrated function as removed.
Implement only within the user's update scope and open a reviewable PR after real
checks. This entry point does not depend on a marketplace agent identifier.
