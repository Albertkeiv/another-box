from __future__ import annotations

from another_box.json_compat import loads_sing_box_json


def test_trailing_commas_are_accepted():
    value = loads_sing_box_json(
        """
        {
          "outbounds": [
            {"type": "direct", "tag": "PROXY",},
          ],
        }
        """
    )

    assert value["outbounds"][0]["tag"] == "PROXY"


def test_jsonc_comments_are_accepted():
    value = loads_sing_box_json(
        """
        {
          // Main selector
          "outbounds": [
            {
              "type": "direct",
              /* This comment should be ignored. */
              "tag": "PROXY"
            }
          ]
        }
        """
    )

    assert value["outbounds"][0]["type"] == "direct"


def test_comment_markers_and_commas_inside_strings_are_preserved():
    value = loads_sing_box_json(
        r'''
        {
          "url": "https://example.test/a//b",
          "note": "keep /* text */,}",
        }
        '''
    )

    assert value["url"] == "https://example.test/a//b"
    assert value["note"] == "keep /* text */,}"
