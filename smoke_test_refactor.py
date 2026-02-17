import importlib
import sys
from unittest.mock import MagicMock, patch

MOCK_MODULES = {
    "numpy": MagicMock(),
    "sklearn": MagicMock(),
    "sklearn.cluster": MagicMock(),
    "sklearn.metrics": MagicMock(),
    "sklearn.preprocessing": MagicMock(),
    "digital_life": MagicMock(),
}

sys.path.append("scripts")
with patch.dict(sys.modules, MOCK_MODULES):
    ap = importlib.import_module("scripts.analyze_phenotype")


def test_collect_organism_traits():
    mock_results = [
        {
            "seed": 42,
            "organism_snapshots": [
                {
                    "step": 0,
                    "organisms": [
                        {
                            "stable_id": 1,
                            "energy": 10.0,
                            "waste": 1.0,
                            "boundary_integrity": 0.9,
                            "maturity": 0.5,
                            "generation": 2,
                        },
                        {
                            "stable_id": 2,
                            "energy": 20.0,
                            "waste": 2.0,
                            "boundary_integrity": 0.8,
                            "maturity": 0.6,
                            "generation": 3,
                        },
                    ],
                }
            ],
        }
    ]
    trait_names = ["energy", "waste", "boundary_integrity", "maturity", "generation"]
    orgs = ap._collect_organism_traits(mock_results, 0, trait_names)
    assert len(orgs) == 2
    assert orgs[(42, 1)] == [10.0, 1.0, 0.9, 0.5, 2.0]
    print("Test _collect_organism_traits passed")


def test_extract_shared_traits():
    # Bypass np.array
    orig = ap.np.array
    ap.np.array = lambda x: x

    try:
        # Needs at least 4 shared to not return None
        dict_a = {(42, i): [float(i)] for i in range(5)}
        dict_b = {(42, i): [float(i)] for i in range(5)}

        keys, traits_a, traits_b = ap._extract_shared_traits(dict_a, dict_b)
        assert len(keys) == 5
        assert len(traits_a) == 5
        assert len(traits_b) == 5
        print("Test _extract_shared_traits passed")
    finally:
        ap.np.array = orig


if __name__ == "__main__":
    failed = False
    for test in (test_collect_organism_traits, test_extract_shared_traits):
        try:
            test()
            print(f"{test.__name__}: PASS")
        except Exception as e:
            failed = True
            print(f"{test.__name__}: FAIL ({e})")
            import traceback

            traceback.print_exc()

    if failed:
        sys.exit(1)
    print("All tests passed!")
