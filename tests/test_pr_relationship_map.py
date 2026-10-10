import re
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
MAP = ROOT / "docs" / "open-source-scouting" / "PR_RELATIONSHIPS_2026-10-10.md"


class PullRequestRelationshipMapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = MAP.read_text(encoding="utf-8")
        cls.links = {
            int(number)
            for number in re.findall(
                r"https://github\.com/davidpd89/ci-sandbox-tmp/pull/(\d+)",
                cls.text,
            )
        }

    def test_all_pull_request_links_are_canonical(self):
        urls = re.findall(r"https://github\.com/[^)\s]+/pull/\d+", self.text)
        self.assertTrue(urls)
        self.assertTrue(
            all(url.startswith("https://github.com/davidpd89/ci-sandbox-tmp/pull/") for url in urls)
        )

    def test_direct_consolidation_chains_are_present(self):
        chains = ({98, 155, 181}, {94, 161, 191}, {102, 159, 187}, {104, 163, 202})
        for chain in chains:
            with self.subTest(chain=chain):
                self.assertLessEqual(chain, self.links)

    def test_global_contracts_and_network_families_are_linked(self):
        families = {
            114: {154, 162, 168, 178, 188, 194, 199},
            115: {152, 160, 167, 176, 185, 193, 198},
            116: {149, 156, 164, 170, 180, 189, 195, 200},
            117: {150, 151, 157, 158, 165, 166, 173, 174, 182, 184, 190, 192, 196, 197, 201, 203},
        }
        for contract, members in families.items():
            with self.subTest(contract=contract):
                self.assertIn(contract, self.links)
                self.assertLessEqual(members, self.links)

    def test_coordination_map_covers_cross_cutting_infrastructure(self):
        required = {1, 8, 43, 91, 95, 99, 100, 103, 106, 107, 108, 109, 110, 111, 118, 120, 137, 169, 175, 183}
        self.assertLessEqual(required, self.links)


if __name__ == "__main__":
    unittest.main()
