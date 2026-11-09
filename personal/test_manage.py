import unittest
from unittest.mock import patch
from personal.manage import environment

class RuntimeSettingsTests(unittest.TestCase):
    def env_for(self, enabled):
        cfg={'dashboard_key':'','db_password':'test-only','scheduler_enabled':enabled}
        with patch('personal.manage.settings',return_value=cfg),patch.dict('os.environ',{},clear=True):
            return environment()

    def test_discovery_scheduler_is_off_unless_enabled(self):
        self.assertEqual(self.env_for(False)['JN_SCHEDULER_DISABLED'],'1')
        self.assertEqual(self.env_for(True)['JN_SCHEDULER_DISABLED'],'0')

    def test_keyless_dashboard_does_not_disable_private_runner_auth(self):
        env=self.env_for(True)
        self.assertEqual(env['INITIAL_API_KEY'],'')
        self.assertTrue(env['JN_RUNNER_TOKEN_FILE'].endswith('/.personal/runner-token'))
        self.assertEqual(env['JN_CODEX_RUNNER_URL'],'http://127.0.0.1:8011')
        self.assertEqual(env['JN_TELEMETRY'],'off')

if __name__=='__main__':unittest.main()
