"""Regression coverage for standalone report navigation and escaped evidence."""
from pathlib import Path
from types import SimpleNamespace
import unittest

from jinja2 import Environment, FileSystemLoader, select_autoescape
from backend.api_testing.reporting import render_report


class StandaloneReportNavigationTests(unittest.TestCase):
    def setUp(self):
        self.env = Environment(
            loader=FileSystemLoader(Path(__file__).resolve().parents[1] / 'templates'),
            # The production generator historically uses the default environment;
            # templates must enable escaping themselves.
            autoescape=False,
        )

    def test_case_failure_link_uses_original_step_order_and_escapes_evidence(self):
        output = self.env.get_template('report.html').render(
            case_name='登录验证', case_id=1, total_steps=2, passed=1, failed=1,
            success_rate=50, duration=1, steps=[
                {'status': 'success', 'action': 'start_app', 'duration': 0.2, 'report_display': {}},
                {'status': 'failed', 'description': '点击 <script>alert(1)</script>',
                 'error': '<img src=x onerror=alert(1)>', 'duration': 0.8, 'report_display': {}},
            ],
        )
        self.assertIn('href="#step-2"', output)
        self.assertIn('id="step-2"', output)
        self.assertIn('class="step failed expanded"', output)
        self.assertIn('&lt;script&gt;', output)
        self.assertNotIn('<img src=x', output)
        self.assertIn('tabindex="0"', output)

    def test_scenario_links_resolve_even_when_case_ids_are_reused(self):
        output = self.env.get_template('scenario_report.html').render(
            scenario_name='回归', total_cases=2, passed_cases=1, failed_cases=1,
            success_rate=50, duration=1, cases_results=[
                {'case_id': 7, 'case_name': '首次', 'status': 'success', 'steps': []},
                {'case_id': 7, 'case_name': '再次', 'status': 'failed', 'steps': []},
            ],
        )
        self.assertIn('href="#case-2"', output)
        self.assertIn('id="case-2"', output)
        self.assertIn('id="case-1"', output)
        self.assertEqual(output.count('id="case-2"'), 1)

    def test_api_report_preserves_failure_assertions_and_collapsed_technical_details(self):
        run = SimpleNamespace(scenario_name='接口回归', status='FAIL', env_name='测试',
                              executor_name='QA', started_at='2026-10-03', created_at='2026-10-03',
                              duration_ms=30, error=None, snapshot={'steps': [{'id': 'login', 'name': '登录'}]})
        step = SimpleNamespace(step_id='login', name='登录', status='FAIL', duration_ms=30, detail={
            'request': {'url': 'https://example.invalid/test'},
            'response': {'status_code': 400, 'body': {'error': '<script>bad()</script>'}, 'headers': {}, 'cookies': {}, 'text': 'failed'},
            'assertions': [{'path': ['status_code'], 'op': 'is_2xx', 'passed': False,
                            'actual': 400, 'expected': None, 'message': '状态码不符合预期'}],
        })
        output = render_report(run, [step])
        self.assertIn('第 1 步「登录」失败', output)
        self.assertIn('<details open><summary>响应正文', output)
        self.assertIn('<details><summary>请求详情', output)
        self.assertIn('&lt;script&gt;', output)
        self.assertNotIn('<script>bad()', output)
        self.assertIn('@media(max-width:600px)', output)


if __name__ == '__main__':
    unittest.main()
