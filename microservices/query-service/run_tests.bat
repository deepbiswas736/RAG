@echo off
REM Shortcut script to run tests from query-service directory
REM This script forwards all arguments to the actual test runner in the testing directory

echo Running Query Service tests from testing/unit-integration-testing/query-service...
python %~dp0\..\..\..\testing\unit-integration-testing\query-service\run_tests.py %*
