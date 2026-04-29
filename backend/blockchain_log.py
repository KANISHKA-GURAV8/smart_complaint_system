import hashlib
import json
from datetime import datetime
from models import db, BlockchainLog


def _compute_hash(index, complaint_id, action, data_str, previous_hash, timestamp):
    """Compute SHA-256 hash for a block."""
    block_content = json.dumps({
        'index': index,
        'complaint_id': complaint_id,
        'action': action,
        'data': data_str,
        'previous_hash': previous_hash,
        'timestamp': timestamp
    }, sort_keys=True)
    return hashlib.sha256(block_content.encode('utf-8')).hexdigest()


def add_block(complaint_id, action, data: dict) -> str:
    """
    Append a new block to the chain and return its hash.
    Thread-safe: SQLite handles concurrent writes via WAL.
    """
    last_block = BlockchainLog.query.order_by(BlockchainLog.id.desc()).first()
    previous_hash = last_block.block_hash if last_block else ('0' * 64)
    index = (last_block.id + 1) if last_block else 1
    timestamp = datetime.utcnow().isoformat()
    data_str = json.dumps(data, sort_keys=True)

    block_hash = _compute_hash(index, complaint_id, action, data_str, previous_hash, timestamp)

    log = BlockchainLog(
        complaint_id=complaint_id,
        action=action,
        data=data_str,
        block_hash=block_hash,
        previous_hash=previous_hash
    )
    db.session.add(log)
    db.session.commit()
    return block_hash


def verify_chain() -> tuple[bool, str]:
    """
    Walk the entire chain and verify hash integrity.
    Returns (is_valid, message).
    """
    logs = BlockchainLog.query.order_by(BlockchainLog.id).all()

    if not logs:
        return True, "Chain is empty — nothing to verify."

    for i, log in enumerate(logs):
        expected_previous = logs[i - 1].block_hash if i > 0 else ('0' * 64)

        if log.previous_hash != expected_previous:
            return False, f"Chain linkage broken at block #{log.id}"

        expected_hash = _compute_hash(
            log.id,
            log.complaint_id,
            log.action,
            log.data,
            log.previous_hash,
            log.timestamp.isoformat()
        )

        if log.block_hash != expected_hash:
            return False, f"Hash mismatch at block #{log.id} — data may have been tampered."

    return True, f"✅ Chain verified — {len(logs)} blocks intact, no tampering detected."
