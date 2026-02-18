import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from refminer.analysis.citations import ReferenceParser


class TestReferenceParser(unittest.TestCase):
    def test_extract_references_stops_before_appendix_restart(self) -> None:
        text = "\n".join(
            [
                "Main paper content.",
                "References",
                '[1] A. Author, "First Study", 2021.',
                '[2] B. Author, "Second Study", 2020. doi:10.1234/ABC.DEF',
                '[3] C. Author, "Third Study", 2019. https://example.org/paper.pdf',
                "Appendix A",
                "[1] This is an inline appendix citation and not a bibliography item.",
                "2. Step 2: a procedural step that should not become a reference.",
            ]
        )

        refs = ReferenceParser().extract_references(text)

        self.assertEqual([item.ref_number for item in refs], [1, 2, 3])
        self.assertEqual(len(refs), 3)
        self.assertEqual(refs[1].doi, "10.1234/ABC.DEF")
        self.assertEqual(refs[2].availability, "downloadable")

    def test_extract_references_stops_at_appendix_heading_variant(self) -> None:
        text = "\n".join(
            [
                "Main paper content.",
                "References",
                '[1] First Ref. "Alpha". 2022.',
                '[2] Second Ref. "Beta". arXiv:2301.00001, 2023. Is Mu Li, Hai Zhao, Multimodal chain-of',
                "A. Overview of the Appendix",
                "This Appendix is organized as follows:",
                "and mentally manipulate objects, simulating spatial transformations.",
            ]
        )

        refs = ReferenceParser().extract_references(text)

        self.assertEqual([item.ref_number for item in refs], [1, 2])
        self.assertEqual(len(refs), 2)
        self.assertNotIn("mentally manipulate", refs[-1].raw_text)
        self.assertNotIn("Is Mu Li", refs[-1].raw_text)


if __name__ == "__main__":
    unittest.main()
