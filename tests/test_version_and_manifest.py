import unittest
from packaging.version import Version
from skillware.version_policy import (
    should_emit_unsupported_advisory,
    format_unsupported_message,
    validate_frontmatter_dict,
    MIN_UNSUPPORTED,
)


class TestVersionAndManifest(unittest.TestCase):
    def test_should_emit_unsupported_advisory(self):
        self.assertTrue(should_emit_unsupported_advisory(Version("0.3.0")))
        self.assertFalse(should_emit_unsupported_advisory(MIN_UNSUPPORTED))
        self.assertFalse(should_emit_unsupported_advisory(Version("0.4.7")))

    def test_format_unsupported_message(self):
        msg = format_unsupported_message(Version("0.3.0"))
        self.assertIn("0.3.0", msg)
        self.assertIn("Upgrade to >=", msg)

    def test_validate_frontmatter_dict(self):
        valid, err = validate_frontmatter_dict({"name": "test-skill", "description": "A test skill"})
        self.assertTrue(valid)
        self.assertEqual(err, "")

        invalid, err = validate_frontmatter_dict({"name": "", "description": "desc"})
        self.assertFalse(invalid)
        self.assertIn("name", err)


if __name__ == '__main__':
    unittest.main()
