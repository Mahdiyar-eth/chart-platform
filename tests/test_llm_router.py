

# ───────────────────── R.3 per-slot model override ─────────────────────
def test_pool_slot_model_override():
    """key@model pins ONE key to a model while others keep the pool default."""
    from app.core.llm import GoPoolProvider
    pool = GoPoolProvider(api_keys=["sk-aaa", "sk-bbb@deepseek-v4-pro"], model="deepseek-v4-flash")
    assert [s.name for s in pool.slots] == ["go-1", "go-2"]
    assert pool.slots[0].model is None
    assert pool.slots[1].model == "deepseek-v4-pro"
    mk1 = pool._mk(pool.slots[0])
    mk2 = pool._mk(pool.slots[1])
    assert mk1.MODEL == "deepseek-v4-flash"
    assert mk2.MODEL == "deepseek-v4-pro"
