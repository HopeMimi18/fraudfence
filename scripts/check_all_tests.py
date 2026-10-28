"""Run the two isolated security-test groups in separate Python processes.

This avoids event-loop/thread teardown edge cases in long chained TestClient suites.
"""
import subprocess
import sys

GROUPS = [
    ['tests/test_ai_reports.py'],
    ['tests/test_api.py', 'tests/test_external_integrations.py',
     'tests/test_notifications.py', 'tests/test_pitch_mode.py'],
]


def main():
    for index, paths in enumerate(GROUPS, 1):
        print(f'\nFraudFence tests: group {index}/{len(GROUPS)}', flush=True)
        result = subprocess.run([sys.executable, '-m', 'pytest', '-q', *paths], check=False)
        if result.returncode:
            return result.returncode
    print('\nAll AI and existing application test groups PASSED.', flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
