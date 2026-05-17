"""RiftReader local workflow helpers.

These helpers are operator/workflow glue only. They must stay fail-closed and
must not send live input, attach debuggers, or mutate Git state unless a
dedicated helper explicitly exists for that purpose.
"""
