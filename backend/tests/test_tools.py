from app.ai.tools import _parse_tavily_response


def test_parse_tavily_response_extracts_results_and_answer():
    data = {
        "answer": "Paris is the capital of France.",
        "results": [
            {
                "title": "France",
                "url": "https://en.wikipedia.org/wiki/France",
                "content": "France is a country in Western Europe.",
                "published_date": "2026-08-01",
            },
        ],
    }

    result = _parse_tavily_response(data, "capital of France")

    assert result["query"] == "capital of France"
    assert result["answer"] == "Paris is the capital of France."
    assert result["results"] == [
        {
            "title": "France",
            "url": "https://en.wikipedia.org/wiki/France",
            "snippet": "France is a country in Western Europe.",
            "published": "2026-08-01",
        }
    ]


def test_parse_youtube_results_extracts_videos():
    from app.ai.tools import _parse_youtube_results

    data = {
        "items": [
            {
                "id": {"videoId": "abc123"},
                "snippet": {
                    "title": "Intro to Solid-State Batteries",
                    "channelTitle": "Tech Explained",
                    "publishedAt": "2026-07-01T00:00:00Z",
                },
            }
        ]
    }

    results = _parse_youtube_results(data)

    assert results == [
        {
            "title": "Intro to Solid-State Batteries",
            "url": "https://www.youtube.com/watch?v=abc123",
            "snippet": "Tech Explained",
            "published": "2026-07-01T00:00:00Z",
        }
    ]


def test_parse_youtube_results_skips_items_without_video_id():
    from app.ai.tools import _parse_youtube_results

    data = {"items": [{"id": {}, "snippet": {"title": "No ID"}}]}

    assert _parse_youtube_results(data) == []


def test_parse_youtube_results_handles_missing_items():
    from app.ai.tools import _parse_youtube_results

    assert _parse_youtube_results({}) == []


def test_parse_tavily_response_defaults_published_to_empty_string():
    data = {"results": [{"title": "No date", "url": "https://example.com", "content": "text"}]}

    result = _parse_tavily_response(data, "query")

    assert result["results"][0]["published"] == ""


def test_parse_tavily_response_handles_missing_fields():
    result = _parse_tavily_response({}, "test query")

    assert result["query"] == "test query"
    assert result["answer"] == ""
    assert result["results"] == []


def test_parse_tavily_response_caps_at_five_results():
    data = {"results": [{"title": str(i), "url": "", "content": ""} for i in range(8)]}

    result = _parse_tavily_response(data, "many results")

    assert len(result["results"]) == 5


def test_extract_text_strips_html_tags_and_boilerplate():
    from app.ai.tools import _extract_text

    html = b"""
    <html><head><script>var x=1;</script><style>.a{color:red}</style></head>
    <body><nav>Menu</nav><header>Site Header</header>
    <article><h1>Title</h1><p>Real content here.</p></article>
    <footer>Copyright 2026</footer></body></html>
    """
    result = _extract_text(html, "text/html; charset=utf-8")

    assert "Real content here." in result["text"]
    assert "Menu" not in result["text"]
    assert "Site Header" not in result["text"]
    assert "Copyright 2026" not in result["text"]
    assert result["truncated"] is False


def test_extract_text_truncates_long_html():
    from app.ai.tools import _extract_text

    html = b"<html><body><p>" + b"word " * 3000 + b"</p></body></html>"
    result = _extract_text(html, "text/html")

    assert len(result["text"]) <= 3000
    assert result["truncated"] is True


def test_extract_text_extracts_pdf_content_without_crashing():
    from pypdf import PdfWriter
    import io

    from app.ai.tools import _extract_text

    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    buffer = io.BytesIO()
    writer.write(buffer)

    result = _extract_text(buffer.getvalue(), "application/pdf")

    assert result["truncated"] is False
    assert isinstance(result["text"], str)


def test_extract_text_rejects_unsupported_content_type():
    from app.ai.tools import _extract_text

    result = _extract_text(b"binary-data", "image/png")

    assert result["error"] == "This doesn't look like a webpage or PDF I can read."


def test_parse_semantic_scholar_results_extracts_papers():
    from app.ai.tools import _parse_semantic_scholar_results

    data = {
        "data": [
            {
                "title": "Solid-State Battery Advances",
                "url": "https://www.semanticscholar.org/paper/abc123",
                "abstract": "A survey of recent progress in solid-state battery chemistry.",
                "year": 2026,
                "authors": [{"name": "Jane Doe"}, {"name": "John Smith"}],
            }
        ]
    }

    results = _parse_semantic_scholar_results(data)

    assert results == [
        {
            "title": "Solid-State Battery Advances",
            "url": "https://www.semanticscholar.org/paper/abc123",
            "snippet": "Jane Doe, John Smith · 2026",
            "published": "2026",
        }
    ]


def test_parse_semantic_scholar_results_falls_back_to_abstract_without_authors_or_year():
    from app.ai.tools import _parse_semantic_scholar_results

    long_abstract = "Some abstract text " * 20
    data = {"data": [{"title": "No metadata", "url": "https://example.com", "abstract": long_abstract}]}

    results = _parse_semantic_scholar_results(data)

    assert results[0]["snippet"] == long_abstract[:200]
    assert results[0]["published"] == ""


def test_parse_semantic_scholar_results_handles_missing_data():
    from app.ai.tools import _parse_semantic_scholar_results

    assert _parse_semantic_scholar_results({}) == []


def test_parse_finnhub_quote_extracts_price_fields():
    from app.ai.tools import _parse_finnhub_quote

    data = {"c": 227.5, "d": 1.25, "dp": 0.55, "h": 228.9, "l": 225.1, "o": 226.0, "pc": 226.25}

    result = _parse_finnhub_quote(data, "AAPL")

    assert result == {
        "symbol": "AAPL",
        "price": 227.5,
        "change": 1.25,
        "change_percent": 0.55,
        "high": 228.9,
        "low": 225.1,
        "open": 226.0,
        "previous_close": 226.25,
    }


def test_parse_finnhub_quote_detects_all_zero_invalid_symbol():
    from app.ai.tools import _parse_finnhub_quote

    data = {"c": 0, "d": 0, "dp": 0, "h": 0, "l": 0, "o": 0, "pc": 0}

    result = _parse_finnhub_quote(data, "NOTREAL")

    assert result == {"symbol": "NOTREAL", "error": "I couldn't find a quote for that symbol."}


def test_parse_finnhub_quote_handles_missing_fields():
    from app.ai.tools import _parse_finnhub_quote

    result = _parse_finnhub_quote({}, "AAPL")

    assert result == {"symbol": "AAPL", "error": "I couldn't find a quote for that symbol."}


def test_build_srt_formats_single_segment():
    from app.ai.tools import _build_srt

    segments = [{"start": 0.0, "end": 2.5, "text": "Hello world"}]

    assert _build_srt(segments) == "1\n00:00:00,000 --> 00:00:02,500\nHello world\n"


def test_build_srt_numbers_sequentially_and_formats_hours():
    from app.ai.tools import _build_srt

    segments = [
        {"start": 0.0, "end": 1.0, "text": "First"},
        {"start": 3661.25, "end": 3662.75, "text": "Second, after an hour"},
    ]
    srt = _build_srt(segments)

    assert "1\n00:00:00,000 --> 00:00:01,000\nFirst\n" in srt
    assert "2\n01:01:01,250 --> 01:01:02,750\nSecond, after an hour\n" in srt


def test_build_srt_handles_empty_segments():
    from app.ai.tools import _build_srt

    assert _build_srt([]) == ""


def test_parse_silencedetect_output_extracts_intervals():
    from app.ai.tools import _parse_silencedetect_output

    stderr_text = (
        "[silencedetect @ 0x1] silence_start: 2.5\n"
        "[silencedetect @ 0x1] silence_end: 4.2 | silence_duration: 1.7\n"
        "[silencedetect @ 0x1] silence_start: 8.0\n"
        "[silencedetect @ 0x1] silence_end: 9.1 | silence_duration: 1.1\n"
    )

    assert _parse_silencedetect_output(stderr_text) == [(2.5, 4.2), (8.0, 9.1)]


def test_parse_silencedetect_output_handles_no_silence():
    from app.ai.tools import _parse_silencedetect_output

    assert _parse_silencedetect_output("no silence markers here") == []


def test_parse_ffmpeg_duration_extracts_seconds():
    from app.ai.tools import _parse_ffmpeg_duration

    stderr_text = "  Duration: 00:05:23.40, start: 0.000000, bitrate: 128 kb/s"

    assert _parse_ffmpeg_duration(stderr_text) == 323.4


def test_parse_ffmpeg_duration_handles_missing_duration():
    from app.ai.tools import _parse_ffmpeg_duration

    assert _parse_ffmpeg_duration("no duration here") == 0.0


def test_compute_keep_segments_removes_padded_silence():
    from app.ai.tools import _compute_keep_segments

    segments = _compute_keep_segments([(2.0, 4.0)], duration=10.0, padding=0.15)

    assert segments == [(0.0, 2.15), (3.85, 10.0)]


def test_compute_keep_segments_skips_silence_too_short_after_padding():
    from app.ai.tools import _compute_keep_segments

    # silence is 0.2s long; padding*2 = 0.3s > 0.2s, so nothing gets cut here
    segments = _compute_keep_segments([(5.0, 5.2)], duration=10.0, padding=0.15)

    assert segments == [(0.0, 10.0)]


def test_compute_keep_segments_handles_no_silence():
    from app.ai.tools import _compute_keep_segments

    assert _compute_keep_segments([], duration=10.0) == [(0.0, 10.0)]


def test_compute_keep_segments_handles_multiple_silences():
    from app.ai.tools import _compute_keep_segments

    segments = _compute_keep_segments([(2.0, 3.0), (6.0, 7.0)], duration=10.0, padding=0.1)

    assert segments == [(0.0, 2.1), (2.9, 6.1), (6.9, 10.0)]


def test_build_select_expr_joins_segments_with_between():
    from app.ai.tools import _build_select_expr

    expr = _build_select_expr([(0.0, 2.15), (3.85, 10.0)])

    assert expr == "between(t,0.0,2.15)+between(t,3.85,10.0)"


def test_build_select_expr_handles_single_segment():
    from app.ai.tools import _build_select_expr

    assert _build_select_expr([(0.0, 10.0)]) == "between(t,0.0,10.0)"


def test_build_select_expr_handles_empty_segments():
    from app.ai.tools import _build_select_expr

    assert _build_select_expr([]) == ""


def test_build_timestamped_transcript_formats_segments():
    from app.ai.tools import _build_timestamped_transcript

    segments = [{"start": 0.0, "text": "Hello"}, {"start": 12.345, "text": "world"}]

    assert _build_timestamped_transcript(segments) == "[0.0s] Hello\n[12.3s] world"


def test_build_timestamped_transcript_handles_empty_segments():
    from app.ai.tools import _build_timestamped_transcript

    assert _build_timestamped_transcript([]) == ""


def test_parse_highlight_response_extracts_valid_highlights():
    import json

    from app.ai.tools import _parse_highlight_response

    raw_json = json.dumps([
        {"start": 10.0, "end": 25.0, "reason": "Great opening hook"},
        {"start": 60.0, "end": 90.0, "reason": "Key insight about the topic"},
    ])

    highlights = _parse_highlight_response(raw_json, duration=120.0, max_highlights=5)

    assert highlights == [
        {"start": 10.0, "end": 25.0, "reason": "Great opening hook"},
        {"start": 60.0, "end": 90.0, "reason": "Key insight about the topic"},
    ]


def test_parse_highlight_response_clamps_out_of_range_timestamps():
    import json

    from app.ai.tools import _parse_highlight_response

    raw_json = json.dumps([{"start": -5.0, "end": 200.0, "reason": "Whole thing"}])

    highlights = _parse_highlight_response(raw_json, duration=120.0, max_highlights=5)

    assert highlights == [{"start": 0.0, "end": 120.0, "reason": "Whole thing"}]


def test_parse_highlight_response_drops_invalid_entries():
    import json

    from app.ai.tools import _parse_highlight_response

    raw_json = json.dumps([
        {"start": 10.0, "end": 5.0, "reason": "end before start"},
        {"start": "not-a-number", "end": 20.0, "reason": "bad start"},
        {"start": 30.0, "end": 40.0, "reason": ""},
        {"start": 50.0, "end": 60.0, "reason": "valid one"},
    ])

    highlights = _parse_highlight_response(raw_json, duration=120.0, max_highlights=5)

    assert highlights == [{"start": 50.0, "end": 60.0, "reason": "valid one"}]


def test_parse_highlight_response_truncates_to_max_highlights():
    import json

    from app.ai.tools import _parse_highlight_response

    raw_json = json.dumps(
        [{"start": i * 10.0, "end": i * 10.0 + 5.0, "reason": f"clip {i}"} for i in range(5)]
    )

    highlights = _parse_highlight_response(raw_json, duration=120.0, max_highlights=2)

    assert len(highlights) == 2


def test_parse_highlight_response_handles_unparseable_json():
    from app.ai.tools import _parse_highlight_response

    assert _parse_highlight_response("not json", duration=120.0, max_highlights=5) == []


def test_parse_highlight_response_handles_non_list_json():
    from app.ai.tools import _parse_highlight_response

    assert _parse_highlight_response('{"not": "a list"}', duration=120.0, max_highlights=5) == []


def test_build_magic_packet_has_correct_length_and_prefix():
    from app.ai.tools import _build_magic_packet

    packet = _build_magic_packet("AA:BB:CC:DD:EE:FF")

    assert len(packet) == 102
    assert packet[:6] == b"\xff" * 6


def test_build_magic_packet_repeats_mac_sixteen_times():
    from app.ai.tools import _build_magic_packet

    packet = _build_magic_packet("AA:BB:CC:DD:EE:FF")
    mac_bytes = bytes.fromhex("AABBCCDDEEFF")

    assert packet[6:] == mac_bytes * 16


def test_build_magic_packet_handles_hyphen_separated_mac():
    from app.ai.tools import _build_magic_packet

    packet_colon = _build_magic_packet("AA:BB:CC:DD:EE:FF")
    packet_hyphen = _build_magic_packet("AA-BB-CC-DD-EE-FF")

    assert packet_colon == packet_hyphen


def test_categorize_tasks_by_due_date_splits_overdue_and_upcoming():
    from datetime import datetime, timezone

    from app.ai.tools import _categorize_tasks_by_due_date

    now = datetime(2026, 8, 19, 12, 0, tzinfo=timezone.utc)
    tasks = [
        {"id": 1, "title": "late", "due_at": "2026-08-18T12:00:00+00:00"},
        {"id": 2, "title": "soon", "due_at": "2026-08-20T12:00:00+00:00"},
    ]

    result = _categorize_tasks_by_due_date(tasks, now)

    assert [t["id"] for t in result["overdue"]] == [1]
    assert [t["id"] for t in result["upcoming"]] == [2]
    assert result["no_due_date"] == []


def test_categorize_tasks_by_due_date_buckets_missing_due_date():
    from datetime import datetime, timezone

    from app.ai.tools import _categorize_tasks_by_due_date

    now = datetime(2026, 8, 19, 12, 0, tzinfo=timezone.utc)
    tasks = [{"id": 1, "title": "someday", "due_at": None}]

    result = _categorize_tasks_by_due_date(tasks, now)

    assert [t["id"] for t in result["no_due_date"]] == [1]


def test_categorize_tasks_by_due_date_buckets_unparseable_due_date():
    from datetime import datetime, timezone

    from app.ai.tools import _categorize_tasks_by_due_date

    now = datetime(2026, 8, 19, 12, 0, tzinfo=timezone.utc)
    tasks = [{"id": 1, "title": "weird", "due_at": "not-a-date"}]

    result = _categorize_tasks_by_due_date(tasks, now)

    assert [t["id"] for t in result["no_due_date"]] == [1]
