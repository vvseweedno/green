import json
from pathlib import Path

import numpy as np
import pytest

from carbon_mrv.data.cache import ArrayCache


def test_cache_replay_by_request_hash_and_checksum(tmp_path: Path):
    cache=ArrayCache(tmp_path)
    cache.put("scene-1",{"B04":np.arange(4).reshape(2,2)},{"item_id":"scene-1","request_hash":"abc"})
    replay=cache.replay_by_request_hash("abc")
    assert len(replay)==1
    arrays,meta=replay[0]
    assert arrays["B04"].shape==(2,2)
    assert meta["item_id"]=="scene-1"

    artifact=tmp_path/meta["artifact"]
    artifact.write_bytes(artifact.read_bytes()+b"tamper")
    with pytest.raises(ValueError,match="checksum"):
        cache.replay_by_request_hash("abc")
