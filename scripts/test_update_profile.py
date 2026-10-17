import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import update_profile as updater


class ProfileUpdaterTests(unittest.TestCase):
    def test_replace_section_only_changes_target_section(self):
        source = "before\n<!-- PROFILE:START:ACTIVITY -->old<!-- PROFILE:END:ACTIVITY -->\nafter"
        result = updater.replace_section(source, "ACTIVITY", "new content")
        self.assertIn("<!-- PROFILE:START:ACTIVITY -->\nnew content\n<!-- PROFILE:END:ACTIVITY -->", result)
        self.assertTrue(result.startswith("before"))
        self.assertTrue(result.endswith("after"))

    def test_activity_renders_push_as_link(self):
        events = [{
            "type": "PushEvent",
            "repo": {"name": "Gopal2006/example"},
            "created_at": "2026-10-17T08:30:00Z",
            "payload": {"ref": "refs/heads/main", "size": 2},
        }]
        rendered = updater.render_activity(events)
        self.assertIn("Gopal2006/example", rendered)
        self.assertIn("pushed 2 commits", rendered)
        self.assertIn("/commits/main", rendered)

    def test_activity_empty_state_is_honest(self):
        rendered = updater.render_activity([])
        self.assertIn("No recent public events", rendered)

    def test_stats_use_public_repo_star_sum(self):
        rendered = updater.render_stats(
            {"public_repos": 3, "followers": 4, "created_at": "2021-02-03T00:00:00Z"},
            [{"private": False, "stargazers_count": 2}, {"private": False, "stargazers_count": 5}],
        )
        self.assertIn("Public repositories</strong><br />3", rendered)
        self.assertIn("Followers</strong><br />4", rendered)
        self.assertIn("personal public repos</strong><br />7", rendered)
        self.assertIn("GitHub since</strong><br />2021", rendered)

    def test_unsafe_markdown_punctuation_is_escaped(self):
        escaped = updater.escape_markdown("bad | [title] `code` <tag>")
        self.assertNotIn("|", escaped)
        self.assertNotIn("[title]", escaped)
        self.assertNotIn("`code`", escaped)
        self.assertIn("&lt;tag&gt;", escaped)


if __name__ == "__main__":
    unittest.main(verbosity=2)
