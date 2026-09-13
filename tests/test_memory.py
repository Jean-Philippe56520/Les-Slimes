from les_slimes.cognition.memory import FoodMemory, best_food_memory, remember_food


def test_memory_merges_and_respects_capacity():
    memories: list[FoodMemory] = []
    for tick, x in enumerate([1.0, 1.2, 8.0, 12.0, 16.0], start=1):
        remember_food(
            memories,
            x=x,
            y=1.0,
            tick=tick,
            strength=0.8,
            merge_radius=0.5,
            capacity=3,
            decay=0.001,
        )
    assert len(memories) == 3
    assert best_food_memory(memories, 5, 0.001) is not None
