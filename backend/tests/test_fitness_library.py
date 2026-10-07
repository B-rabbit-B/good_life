from app.fitness.library import EQUIPMENT, KINDS, MUSCLES, Exercise, load_library


def test_library_loads_and_is_well_formed():
    library = load_library()
    exercises = list(library.exercises.values())
    assert sum(e.kind == "strength" for e in exercises) >= 38
    assert sum(e.kind == "cardio" for e in exercises) >= 15
    ids = [e.id for e in exercises]
    assert len(ids) == len(set(ids))
    for exercise in exercises:
        assert exercise.id.startswith("ex:")
        assert exercise.kind in KINDS
        assert exercise.equipment in EQUIPMENT
        assert exercise.primary_muscles and set(exercise.primary_muscles) <= set(MUSCLES)
        if exercise.kind == "cardio":
            light, moderate, vigorous = exercise.met
            assert 0 < light <= moderate <= vigorous
        else:
            assert exercise.met is None


def test_search_exact_alias_and_not_found():
    library = load_library()
    first = library.search("卧推")[0]
    assert (first.exercise.name, first.match) == ("卧推", "exact_name")
    assert library.search("杠铃卧推")[0].exercise.id == first.exercise.id
    assert library.search("今天练了深蹲")[0].exercise.name == "深蹲"
    assert library.search("完全不存在的动作") == []
    assert library.search("  ") == []
    assert [h.exercise.id for h in library.search("推")] == [h.exercise.id for h in library.search("推")]


def test_treadmill_walking_is_not_an_exact_running_match():
    hits = load_library().search("跑步机走路")
    assert not any(h.match in ("exact_name", "exact_alias") and "running" in h.exercise.traits for h in hits)
    assert load_library().search("跑步机跑步")[0].exercise.name == "跑步机"


def test_traits():
    library = load_library()
    by_name = {e.name: e for e in library.exercises.values()}
    assert "bending" in by_name["硬拉"].traits
    assert "running" in by_name["跑步"].traits
    assert "swimming" in by_name["游泳"].traits
    assert {"jumping", "high_impact"} <= set(by_name["跳绳"].traits)


def test_custom_exercises_join_the_search():
    library = load_library()
    custom = Exercise(
        id="custom:abc", name="我的特色推", aliases=(), kind="strength", primary_muscles=("chest",),
        equipment="other", traits=(), met=None, custom=True,
    )
    hits = library.search("我的特色推", extra=(custom,))
    assert hits[0].exercise.id == "custom:abc"
    assert library.search("我的特色推") == []
