"""Government API contract regressions; no real credentials or network calls."""

import contextlib
import io
import json
import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import requests

from src import collect_gov as gov


def announcement(number):
    return {
        "pbanc_sn": str(number),
        "biz_pbanc_nm": f"창업 교육 모집 {number}",
        "detl_pg_url": f"https://www.k-startup.go.kr/example?pbancSn={number}",
        "pbanc_ntrp_nm": "창업진흥원",
        "aply_trgt_ctnt": "예비창업자",
        "pbanc_ctnt": "창업 교육을 지원합니다.",
        "pbanc_rcpt_bgng_dt": "20260928",
        "pbanc_rcpt_end_dt": "20261031",
    }


def api_response(payload, content_type="application/json"):
    response = requests.Response()
    response.status_code = 200
    response.encoding = "utf-8"
    response.headers["Content-Type"] = content_type
    response.url = "https://api.example.test/not-a-real-service"
    body = json.dumps(payload) if isinstance(payload, dict) else payload
    response._content = body.encode("utf-8")
    return response


class GovernmentApiContractTests(unittest.TestCase):
    def setUp(self):
        self.network_guard = patch.object(
            gov.requests, "get", side_effect=AssertionError("Unexpected network request")
        )
        self.network_guard.start()
        self.addCleanup(self.network_guard.stop)

    def test_kstartup_uses_official_pagination_and_reads_second_page(self):
        first_page = [announcement(number) for number in range(1, 101)]
        second_page = [announcement(101)]
        responses = [
            {
                "currentCount": 100,
                "data": {"data": first_page},
                "page": 1,
                "perPage": 100,
                "totalCount": 101,
                "matchCount": 101,
            },
            {
                "currentCount": 1,
                "data": {"data": second_page},
                "page": 2,
                "perPage": 100,
                "totalCount": 101,
                "matchCount": 101,
            },
        ]
        with patch.dict(os.environ, {"DATA_GO_KR_KEY": "fake-test-key"}, clear=True):
            with patch.object(gov, "_get_json", side_effect=responses) as request:
                items = gov.fetch_kstartup({"max_items": 300}, "K-Startup")

        self.assertEqual(len(items), 101)
        self.assertEqual(request.call_count, 2)
        for page, call in enumerate(request.call_args_list, 1):
            self.assertEqual(call.args[0], gov.KSTARTUP_URL)
            self.assertEqual(
                call.args[1],
                {
                    "serviceKey": "fake-test-key",
                    "page": page,
                    "perPage": 100,
                    "returnType": "json",
                },
            )
        self.assertEqual(items[-1]["title"], "창업 교육 모집 101")
        self.assertEqual(items[-1]["org"], "창업진흥원")
        self.assertEqual(items[-1]["target"], "예비창업자")
        self.assertEqual(items[-1]["period_start"], "2026-09-28")
        self.assertEqual(items[-1]["period_end"], "2026-10-31")
        self.assertTrue(items[-1]["link"].endswith("pbancSn=101"))

    def test_g2b_singleton_item_is_preserved(self):
        record = {"bidNtceNm": "교육 용역"}
        payload = {"response": {"body": {"items": {"item": record}}}}
        self.assertEqual(gov._rows(payload), [record])

    def test_g2b_uses_positive_budget_when_estimated_price_is_zero(self):
        payload = {
            "response": {
                "body": {
                    "items": [
                        {
                            "bidNtceNm": "교육 용역",
                            "presmptPrce": "0",
                            "asignBdgtAmt": "60000000",
                            "bidNtceDtlUrl": "https://example.test/bid?bidno=1",
                        }
                    ]
                }
            }
        }
        with patch.dict(os.environ, {"DATA_GO_KR_KEY": "fake-test-key"}, clear=True):
            with patch.object(gov, "_get_json", return_value=payload):
                with contextlib.redirect_stderr(io.StringIO()):
                    items = gov.fetch_g2b(
                        {"min_budget": 50000000, "max_items": 300},
                        "나라장터(용역)",
                        datetime(2026, 9, 28, tzinfo=gov.KST),
                    )
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["budget"], "약 6,000만원")

    def test_missing_key_reports_both_sources_and_retains_existing_announcements(self):
        config = {
            "days": 7,
            "keywords": {"include": [], "exclude": []},
            "sources": {
                "kstartup": {"enabled": True, "label": "K-Startup"},
                "g2b": {"enabled": True, "label": "나라장터(용역)"},
            },
        }
        existing = [
            {
                "k": "existing-kstartup",
                "title": "기존 창업 공고",
                "source": "K-Startup",
                "end": "2026-10-30",
                "seen": "2026-09-21",
            },
            {
                "k": "existing-g2b",
                "title": "기존 용역 공고",
                "source": "나라장터(용역)",
                "end": "2026-10-31",
                "seen": "2026-09-21",
            },
        ]
        with tempfile.TemporaryDirectory() as directory:
            store_path = Path(directory) / "gov" / "data.json"
            store_path.parent.mkdir()
            store_path.write_text(json.dumps({"items": existing}), encoding="utf-8")
            with patch.dict(os.environ, {}, clear=True):
                with contextlib.redirect_stderr(io.StringIO()):
                    fresh, errors, active = gov.collect(
                        now=datetime(2026, 9, 28, tzinfo=gov.KST),
                        config=config,
                        state_path=str(Path(directory) / "state" / "seen.json"),
                        store_path=str(store_path),
                        issue_key="2026-09-28",
                    )
            saved = json.loads(store_path.read_text(encoding="utf-8"))
            archived = json.loads(
                (store_path.parent / "archive.json").read_text(encoding="utf-8")
            )

        self.assertEqual(fresh, [])
        # 기존 공고는 그대로 남고(키·제목·마감·seen 보존), 꼬리표(분야·역할·관련도·지역)만 덧붙는다
        def core(items):
            return sorted(({k: it[k] for k in ("k", "title", "source", "end", "seen")} for it in items),
                          key=lambda d: d["k"])
        self.assertEqual(core(active), core(existing))
        self.assertEqual(core(saved["items"]), core(existing))
        self.assertEqual(core(archived["items"]), core(existing))
        for it in archived["items"]:
            for tag in ("fields", "roles", "relevance", "region", "consortium"):
                self.assertIn(tag, it)
        self.assertCountEqual(errors, ["K-Startup", "나라장터(용역)"])

    def assert_api_error(self, payload, code, content_type="application/json"):
        with patch.object(gov.requests, "get", return_value=api_response(payload, content_type)):
            with patch.object(gov.time, "sleep"):
                with self.assertRaises(RuntimeError) as caught:
                    gov._get_json(
                        "https://api.example.test/not-a-real-service",
                        {"serviceKey": "fake-secret-must-not-leak"},
                    )
        self.assertIn(str(code), str(caught.exception))
        self.assertNotIn("fake-secret-must-not-leak", str(caught.exception))

    def test_http_200_json_header_auth_error_is_not_an_empty_success(self):
        self.assert_api_error(
            {
                "response": {
                    "header": {
                        "resultCode": "30",
                        "resultMsg": "SERVICE_KEY_IS_NOT_REGISTERED_ERROR fake-secret-must-not-leak",
                    }
                }
            },
            "30",
        )

    def test_http_200_odcloud_error_is_not_an_empty_success(self):
        self.assert_api_error(
            {"code": -4, "msg": "등록되지 않은 키 fake-secret-must-not-leak"},
            -4,
        )

    def test_http_200_xml_gateway_error_is_not_a_json_parse_error(self):
        self.assert_api_error(
            "<OpenAPI_ServiceResponse><cmmMsgHeader>"
            "<errMsg>SERVICE ERROR fake-secret-must-not-leak</errMsg>"
            "<returnAuthMsg>SERVICE_KEY_IS_NOT_REGISTERED_ERROR</returnAuthMsg>"
            "<returnReasonCode>30</returnReasonCode>"
            "</cmmMsgHeader></OpenAPI_ServiceResponse>",
            "30",
            "application/xml",
        )

    def test_normal_empty_response_is_still_successful(self):
        payloads = [
            {
                "response": {
                    "header": {"resultCode": "00", "resultMsg": "NORMAL SERVICE"},
                    "body": {"items": [], "totalCount": 0},
                }
            },
            {"data": [], "currentCount": 0, "totalCount": 0, "page": 1, "perPage": 100},
        ]
        for payload in payloads:
            with self.subTest(payload=payload):
                with patch.object(gov.requests, "get", return_value=api_response(payload)):
                    result = gov._get_json("https://api.example.test/not-a-real-service", {})
                self.assertEqual(result, payload)
                self.assertEqual(gov._rows(result), [])


class KeyDiagnosticContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Importing the CLI must not reconfigure the test runner's console.
        with contextlib.ExitStack() as stack:
            stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
            stack.enter_context(contextlib.redirect_stderr(io.StringIO()))
            if os.name == "nt":
                stack.enter_context(patch("ctypes.windll.kernel32.SetConsoleOutputCP"))
            from tools import check_keys

        cls.check_keys = check_keys

    def diagnose(self, response):
        with patch.object(self.check_keys.requests, "get", return_value=response):
            return self.check_keys._check_datago(
                "K-Startup",
                "https://api.example.test/not-a-real-service",
                {"page": 1, "perPage": 3, "returnType": "json"},
                "fake-secret-must-not-leak",
            )

    def test_nested_data_reports_actual_record_count(self):
        for count in (0, 3):
            with self.subTest(count=count):
                result = self.diagnose(
                    api_response(
                        {
                            "data": {"data": [announcement(n) for n in range(count)]},
                            "currentCount": count,
                            "totalCount": count,
                        }
                    )
                )
                self.assertEqual(result[0], self.check_keys.OK)
                self.assertIn(f"{count}건", result[1])
                self.assertNotIn("1건", result[1])

    def test_xml_auth_error_never_echoes_secret_in_diagnostic_tuple(self):
        response = api_response(
            "<OpenAPI_ServiceResponse><cmmMsgHeader>"
            "<errMsg>fake-secret-must-not-leak</errMsg>"
            "<returnAuthMsg>SERVICE_KEY_IS_NOT_REGISTERED_ERROR</returnAuthMsg>"
            "<returnReasonCode>30</returnReasonCode>"
            "</cmmMsgHeader></OpenAPI_ServiceResponse>",
            "application/xml",
        )
        result = self.diagnose(response)
        self.assertEqual(result[0], self.check_keys.FAIL)
        self.assertNotIn("fake-secret-must-not-leak", repr(result))

    def test_http_error_never_echoes_secret_in_diagnostic_tuple(self):
        response = api_response(
            "Request rejected: serviceKey=fake-secret-must-not-leak", "text/plain"
        )
        response.status_code = 403
        result = self.diagnose(response)
        self.assertEqual(result[0], self.check_keys.FAIL)
        self.assertIn("403", result[1])
        self.assertNotIn("fake-secret-must-not-leak", repr(result))


if __name__ == "__main__":
    unittest.main()
