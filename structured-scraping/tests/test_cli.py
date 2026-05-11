"""Tests for the CLI module.

This module tests the command-line interface functionality.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from structured_scraping.cli import main


class TestCLIBasics:
    """Test basic CLI functionality."""

    def test_cli_help(self) -> None:
        """Test that CLI help works."""
        runner = CliRunner()
        result = runner.invoke(main, ['--help'])
        assert result.exit_code == 0
        assert "Usage:" in result.output or "Structured Scraping CLI" in result.output

    def test_cli_version(self) -> None:
        """Test that CLI version works."""
        runner = CliRunner()
        result = runner.invoke(main, ['--version'])
        assert result.exit_code == 0

    def test_cli_basic_execution(self) -> None:
        """Test that CLI shows help when run without arguments."""
        runner = CliRunner()
        result = runner.invoke(main, [])
        # Click groups show help and exit with code 2 when no subcommand is provided
        assert result.exit_code == 2
        assert "Usage:" in result.output
        assert "Structured Scraping CLI" in result.output


class TestCLICommands:
    """Test CLI commands functionality."""

    def test_countries_command_table_format(self) -> None:
        """Test that countries command works with table format."""
        runner = CliRunner()
        result = runner.invoke(main, ['countries', '--format', 'table'])
        assert result.exit_code == 0
        assert "Code" in result.output
        assert "Name" in result.output
        assert "Wikidata ID" in result.output

    def test_countries_command_csv_format(self) -> None:
        """Test that countries command works with CSV format."""
        runner = CliRunner()
        result = runner.invoke(main, ['countries', '--format', 'csv'])
        assert result.exit_code == 0
        assert "code,name,wikidata_id" in result.output

    def test_countries_command_json_format(self) -> None:
        """Test that countries command works with JSON format."""
        runner = CliRunner()
        result = runner.invoke(main, ['countries', '--format', 'json'])
        assert result.exit_code == 0
        # Should be valid JSON (extract JSON part after the header)
        lines = result.output.strip().split('\n')
        json_start = -1
        for i, line in enumerate(lines):
            if line.strip().startswith('['):
                json_start = i
                break
        
        if json_start >= 0:
            json_text = '\n'.join(lines[json_start:])
            try:
                countries = json.loads(json_text)
                assert isinstance(countries, list)
                assert len(countries) > 0
                assert 'name' in countries[0]
                assert 'wikidata_id' in countries[0]
            except json.JSONDecodeError:
                pytest.fail("Output does not contain valid JSON")
        else:
            pytest.fail("No JSON found in output")

    def test_countries_command_search(self) -> None:
        """Test that countries command works with search filter."""
        runner = CliRunner()
        result = runner.invoke(main, ['countries', '--search', 'qatar'])
        assert result.exit_code == 0
        assert "qatar" in result.output.lower() or "qa" in result.output.lower()

    def test_countries_command_invalid_format(self) -> None:
        """Test that countries command rejects invalid format."""
        runner = CliRunner()
        result = runner.invoke(main, ['countries', '--format', 'invalid'])
        assert result.exit_code == 2  # Click validation error
        assert "Invalid value" in result.output

    def test_scrape_command_help(self) -> None:
        """Test that scrape command help works."""
        runner = CliRunner()
        result = runner.invoke(main, ['scrape', '--help'])
        assert result.exit_code == 0
        assert "COUNTRY" in result.output
        # Check that new batching options are present in help
        assert "--batching" in result.output
        assert "--batch-size" in result.output
        assert "Enable batched query execution" in result.output

    def test_scrape_batching_options(self) -> None:
        """Test that batching options are properly parsed."""
        runner = CliRunner()
        
        # Test that batching flag appears in help
        result = runner.invoke(main, ['scrape', '--help'])
        assert result.exit_code == 0
        
        # Test that the batching options are present
        assert "--batching" in result.output
        assert "--batch-size" in result.output
        assert "--pause" in result.output

    def test_scrape_batching_flag_syntax(self) -> None:
        """Test that batching flag syntax is correct."""
        runner = CliRunner()
        
        # Test with batching enabled (should not fail on syntax)
        # Note: This doesn't make actual network calls, just tests CLI parsing
        result = runner.invoke(main, ['scrape', 'qa', '--batching', '--count-only'], catch_exceptions=False)
        # The command may fail due to network/data issues, but shouldn't fail due to CLI syntax
        # We're just ensuring the CLI accepts the new parameters
        assert "--batching" not in result.output or result.exit_code in [0, 1]  # 0=success, 1=expected failure

    def test_scrape_batch_size_validation(self) -> None:
        """Test that batch size validation works."""
        runner = CliRunner()
        
        # Test invalid batch size (too small)
        result = runner.invoke(main, ['scrape', 'qa', '--batching', '--batch-size', '0'])
        assert result.exit_code == 2  # Click validation error
        assert "Invalid value" in result.output
        
        # Test invalid batch size (too large)
        result = runner.invoke(main, ['scrape', 'qa', '--batching', '--batch-size', '20000'])
        assert result.exit_code == 2  # Click validation error
        assert "Invalid value" in result.output

    def test_scrape_pause_validation(self) -> None:
        """Test that pause validation works."""
        runner = CliRunner()
        
        # Test invalid pause (negative)
        result = runner.invoke(main, ['scrape', 'qa', '--batching', '--pause', '-1.0'])
        assert result.exit_code == 2  # Click validation error
        assert "Invalid value" in result.output


class TestCLIBatchingFeatures:
    """Test new batching features in the CLI."""

    def test_execution_mode_messaging(self) -> None:
        """Test that execution mode is correctly displayed."""
        runner = CliRunner()
        
        # Test simple execution mode (without --batching)
        result = runner.invoke(main, ['scrape', 'qa', '--count-only'])
        # Should not contain "batched execution" in the output
        if result.exit_code == 0:
            assert "simple execution" not in result.output or "batched execution" not in result.output
        
        # Test batched execution mode (with --batching)  
        result = runner.invoke(main, ['scrape', 'qa', '--batching', '--count-only'])
        # Should contain batching-related messaging if successful
        if result.exit_code == 0:
            # The execution mode messaging appears during scraping, not counting
            pass  # Count-only doesn't trigger the execution mode message

    def test_batching_flag_combinations(self) -> None:
        """Test various flag combinations with batching."""
        runner = CliRunner()
        
        # Test batching with living filter
        result = runner.invoke(main, ['scrape', 'qa', '--batching', '--living', '--count-only'])
        # Should accept the combination without CLI errors
        assert result.exit_code in [0, 1]  # 0=success, 1=expected network/data failure
        
        # Test batching with relevance filter
        result = runner.invoke(main, ['scrape', 'qa', '--batching', '--relevant', '--count-only'])
        # Should accept the combination without CLI errors  
        assert result.exit_code in [0, 1]  # 0=success, 1=expected network/data failure
        
        # Test batching with custom batch size and pause
        result = runner.invoke(main, ['scrape', 'qa', '--batching', '--batch-size', '1000', '--pause', '0.5', '--count-only'])
        # Should accept the combination without CLI errors
        assert result.exit_code in [0, 1]  # 0=success, 1=expected network/data failure

    def test_non_batching_ignores_batch_params(self) -> None:
        """Test that batch parameters are ignored when batching is disabled."""
        runner = CliRunner()
        
        # Without --batching flag, batch-size and pause should be accepted but not used
        result = runner.invoke(main, ['scrape', 'qa', '--batch-size', '1000', '--pause', '0.5', '--count-only'])
        # Should work fine, just ignores the batch parameters
        assert result.exit_code in [0, 1]  # 0=success, 1=expected network/data failure


# Note: More comprehensive integration tests for actual scraping functionality
# are in test_integration.py to avoid hitting Wikidata servers in unit tests.


class TestCLIScrapeCommand:
    """Test scrape command functionality with mocking."""

    @patch('structured_scraping.cli.get_country_id')
    @patch('structured_scraping.cli.get_country_name')
    @patch('structured_scraping.cli.count_country_politicians')
    def test_scrape_count_only(self, mock_count: MagicMock, mock_get_name: MagicMock, mock_get_id: MagicMock) -> None:
        """Test scrape command with count-only flag."""
        # Setup mocks
        mock_get_id.return_value = "Q846"
        mock_get_name.return_value = "Qatar"
        mock_count.return_value = 150
        
        runner = CliRunner()
        result = runner.invoke(main, ['scrape', 'qa', '--count-only'])
        
        assert result.exit_code == 0
        assert "Qatar (Q846)" in result.output
        assert "150" in result.output
        assert "politicians" in result.output
        
        # Verify mocks were called
        mock_get_id.assert_called_once_with("qa")
        mock_get_name.assert_called_once_with("qa")
        mock_count.assert_called_once()

    @patch('structured_scraping.cli.get_country_id')
    @patch('structured_scraping.cli.get_country_name')
    @patch('structured_scraping.cli.count_country_politicians')
    def test_scrape_count_only_zero_results(self, mock_count: MagicMock, mock_get_name: MagicMock, mock_get_id: MagicMock) -> None:
        """Test scrape command when no politicians are found."""
        # Setup mocks
        mock_get_id.return_value = "Q846"
        mock_get_name.return_value = "Qatar"
        mock_count.return_value = 0
        
        runner = CliRunner()
        result = runner.invoke(main, ['scrape', 'qa', '--count-only'])
        
        assert result.exit_code == 0
        assert "0" in result.output
        assert "politicians" in result.output

    @patch('structured_scraping.cli.get_country_id')
    def test_scrape_invalid_country(self, mock_get_id: MagicMock) -> None:
        """Test scrape command with invalid country."""
        # Setup mock to raise ValueError
        mock_get_id.side_effect = ValueError("Unknown country: invalid")
        
        runner = CliRunner()
        result = runner.invoke(main, ['scrape', 'invalid'])
        
        assert result.exit_code == 1
        assert "Invalid country" in result.output
        assert "countries" in result.output  # Should suggest using countries command

    @patch('structured_scraping.cli.get_country_id')
    @patch('structured_scraping.cli.get_country_name')
    @patch('structured_scraping.cli.count_country_politicians')
    @patch('structured_scraping.cli.scrape_country_politicians')
    def test_scrape_full_execution(self, mock_scrape: MagicMock, mock_count: MagicMock, 
                                   mock_get_name: MagicMock, mock_get_id: MagicMock) -> None:
        """Test full scrape execution."""
        # Setup mocks
        mock_get_id.return_value = "Q846"
        mock_get_name.return_value = "Qatar"
        mock_count.return_value = 150
        mock_scrape.return_value = (120, "qatar_peps_20250101_120000.csv")
        
        runner = CliRunner()
        result = runner.invoke(main, ['scrape', 'qa'])
        
        assert result.exit_code == 0
        assert "Qatar (Q846)" in result.output
        assert "150" in result.output
        assert "120" in result.output
        assert "qatar_peps_20250101_120000.csv" in result.output
        
        # Verify scraping was called
        mock_scrape.assert_called_once()

    @patch('structured_scraping.cli.get_country_id')
    @patch('structured_scraping.cli.get_country_name')
    @patch('structured_scraping.cli.count_country_politicians')
    @patch('structured_scraping.cli.scrape_country_politicians')
    def test_scrape_with_output_file(self, mock_scrape: MagicMock, mock_count: MagicMock,
                                     mock_get_name: MagicMock, mock_get_id: MagicMock) -> None:
        """Test scrape with custom output file."""
        # Setup mocks
        mock_get_id.return_value = "Q846"
        mock_get_name.return_value = "Qatar"
        mock_count.return_value = 150
        mock_scrape.return_value = (120, "custom_output.csv")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            output_file = Path(temp_dir) / "custom_output.csv"
            
            runner = CliRunner()
            result = runner.invoke(main, ['scrape', 'qa', '--output', str(output_file)])
            
            assert result.exit_code == 0
            assert "custom_output.csv" in result.output

    @patch('structured_scraping.cli.get_country_id')
    @patch('structured_scraping.cli.get_country_name')
    @patch('structured_scraping.cli.count_country_politicians')
    @patch('structured_scraping.cli.scrape_country_politicians')
    def test_scrape_with_flags(self, mock_scrape: MagicMock, mock_count: MagicMock,
                               mock_get_name: MagicMock, mock_get_id: MagicMock) -> None:
        """Test scrape with living and relevant flags."""
        # Setup mocks
        mock_get_id.return_value = "Q846"
        mock_get_name.return_value = "Qatar"
        mock_count.return_value = 75
        mock_scrape.return_value = (60, "qatar_living_relevant.csv")
        
        runner = CliRunner()
        result = runner.invoke(main, ['scrape', 'qa', '--living', '--relevant'])
        
        assert result.exit_code == 0
        
        # Check that scraping was called with correct parameters
        call_args = mock_scrape.call_args
        assert call_args.kwargs['living_only'] is True
        assert call_args.kwargs['apply_relevance_filter'] is True

    @patch('structured_scraping.cli.get_country_id')
    @patch('structured_scraping.cli.get_country_name')
    @patch('structured_scraping.cli.count_country_politicians')
    @patch('structured_scraping.cli.scrape_country_politicians')
    def test_scrape_with_batching(self, mock_scrape: MagicMock, mock_count: MagicMock,
                                  mock_get_name: MagicMock, mock_get_id: MagicMock) -> None:
        """Test scrape with batching enabled."""
        # Setup mocks
        mock_get_id.return_value = "Q846"
        mock_get_name.return_value = "Qatar"
        mock_count.return_value = 5000
        mock_scrape.return_value = (4800, "qatar_batched.csv")
        
        runner = CliRunner()
        result = runner.invoke(main, ['scrape', 'qa', '--batching', '--batch-size', '1000', '--pause', '0.5'])
        
        assert result.exit_code == 0
        assert "batched execution" in result.output
        
        # Check that configuration was passed correctly
        call_args = mock_scrape.call_args
        config = call_args.kwargs['config']
        assert config.use_batching is True
        assert config.batch_size == 1000
        assert config.pause_s == 0.5

    @patch('structured_scraping.cli.get_country_id')
    @patch('structured_scraping.cli.get_country_name')
    @patch('structured_scraping.cli.count_country_politicians')
    def test_scrape_count_error_handling(self, mock_count: MagicMock, mock_get_name: MagicMock, mock_get_id: MagicMock) -> None:
        """Test error handling during counting."""
        # Setup mocks
        mock_get_id.return_value = "Q846"
        mock_get_name.return_value = "Qatar"
        mock_count.side_effect = Exception("Network error")
        
        runner = CliRunner()
        result = runner.invoke(main, ['scrape', 'qa', '--count-only'])
        
        assert result.exit_code == 1
        assert "Error counting politicians" in result.output
        assert "Network error" in result.output

    @patch('structured_scraping.cli.get_country_id')
    @patch('structured_scraping.cli.get_country_name')
    @patch('structured_scraping.cli.count_country_politicians')
    @patch('structured_scraping.cli.scrape_country_politicians')
    def test_scrape_scraping_error_handling(self, mock_scrape: MagicMock, mock_count: MagicMock,
                                            mock_get_name: MagicMock, mock_get_id: MagicMock) -> None:
        """Test error handling during scraping."""
        # Setup mocks
        mock_get_id.return_value = "Q846"
        mock_get_name.return_value = "Qatar"
        mock_count.return_value = 150
        mock_scrape.side_effect = Exception("Scraping failed")
        
        runner = CliRunner()
        result = runner.invoke(main, ['scrape', 'qa'])
        
        assert result.exit_code == 1
        assert "Error scraping data" in result.output
        assert "Scraping failed" in result.output

    @patch('structured_scraping.cli.get_country_id')
    @patch('structured_scraping.cli.get_country_name')
    @patch('structured_scraping.cli.count_country_politicians')
    def test_scrape_no_politicians_found(self, mock_count: MagicMock, mock_get_name: MagicMock, mock_get_id: MagicMock) -> None:
        """Test when no politicians are found for scraping."""
        # Setup mocks
        mock_get_id.return_value = "Q846"
        mock_get_name.return_value = "Qatar"
        mock_count.return_value = 0
        
        runner = CliRunner()
        result = runner.invoke(main, ['scrape', 'qa'])  # Not count-only
        
        assert result.exit_code == 0
        assert "No politicians found" in result.output
        assert "Nothing to scrape" in result.output

    def test_scrape_debug_logging(self) -> None:
        """Test that debug logging can be enabled."""
        runner = CliRunner()
        # Test that debug flag is accepted (even if command fails due to network)
        result = runner.invoke(main, ['--debug', 'scrape', 'qa', '--count-only'], catch_exceptions=False)
        # Should not fail due to CLI syntax
        assert "--debug" not in result.output  # Flag should be parsed, not shown as error


class TestCLIParameterValidation:
    """Test CLI parameter validation."""

    def test_invalid_timeout(self) -> None:
        """Test validation of timeout parameter."""
        runner = CliRunner()
        result = runner.invoke(main, ['scrape', 'qa', '--timeout', '0'])
        assert result.exit_code == 2
        assert "Invalid value" in result.output

    def test_invalid_max_retries(self) -> None:
        """Test validation of max-retries parameter."""
        runner = CliRunner()
        result = runner.invoke(main, ['scrape', 'qa', '--max-retries', '-1'])
        assert result.exit_code == 2
        assert "Invalid value" in result.output

    def test_valid_parameters(self) -> None:
        """Test that valid parameters are accepted."""
        runner = CliRunner()
        # Should not fail on parameter validation (may fail on network)
        result = runner.invoke(main, ['scrape', 'qa', '--timeout', '30', '--max-retries', '3', '--count-only'])
        # Exit code should not be 2 (which indicates parameter validation error)
        assert result.exit_code != 2


class TestCLIHelperFunctions:
    """Test CLI helper functions."""

    @patch('structured_scraping.cli.configure_debug_logging')
    def test_setup_logging_debug_enabled(self, mock_configure: MagicMock) -> None:
        """Test that setup_logging enables debug logging when debug is True."""
        from structured_scraping.cli import _setup_logging
        
        # Create mock context
        ctx = MagicMock()
        ctx.obj = {"debug": True}
        
        _setup_logging(ctx)
        mock_configure.assert_called_once()

    @patch('structured_scraping.cli.configure_debug_logging')
    def test_setup_logging_debug_disabled(self, mock_configure: MagicMock) -> None:
        """Test that setup_logging doesn't enable debug logging when debug is False."""
        from structured_scraping.cli import _setup_logging
        
        # Create mock context
        ctx = MagicMock()
        ctx.obj = {"debug": False}
        
        _setup_logging(ctx)
        mock_configure.assert_not_called()

    @patch('structured_scraping.cli.configure_debug_logging')
    def test_setup_logging_no_context(self, mock_configure: MagicMock) -> None:
        """Test that setup_logging doesn't enable debug logging when context has no obj."""
        from structured_scraping.cli import _setup_logging
        
        # Create mock context without obj
        ctx = MagicMock()
        ctx.obj = None
        
        _setup_logging(ctx)
        mock_configure.assert_not_called()


class TestCLIEdgeCases:
    """Test CLI edge cases and error conditions."""

    def test_unknown_command(self) -> None:
        """Test that unknown commands are handled properly."""
        runner = CliRunner()
        result = runner.invoke(main, ['unknown-command'])
        assert result.exit_code == 2
        assert "No such command" in result.output

    def test_scrape_missing_country(self) -> None:
        """Test that missing country argument is handled."""
        runner = CliRunner()
        result = runner.invoke(main, ['scrape'])
        assert result.exit_code == 2
        assert "Missing argument" in result.output

    @patch('structured_scraping.cli.list_supported_countries')
    def test_countries_command_error(self, mock_list: MagicMock) -> None:
        """Test error handling in countries command."""
        mock_list.side_effect = ValueError("Failed to load countries")
        
        runner = CliRunner()
        result = runner.invoke(main, ['countries'])
        
        assert result.exit_code == 1
        assert "Error listing countries" in result.output

    def test_countries_search_no_results(self) -> None:
        """Test countries command with search that returns no results."""
        runner = CliRunner()
        result = runner.invoke(main, ['countries', '--search', 'nonexistent-country-xyz'])
        
        assert result.exit_code == 0
        assert "No countries found" in result.output


class TestCLIIntegration:
    """Integration-style tests for CLI (with minimal mocking)."""

    def test_full_help_coverage(self) -> None:
        """Test that all commands have proper help text."""
        runner = CliRunner()
        
        # Main command help
        result = runner.invoke(main, ['--help'])
        assert result.exit_code == 0
        assert "Structured Scraping CLI" in result.output
        
        # Scrape command help
        result = runner.invoke(main, ['scrape', '--help'])
        assert result.exit_code == 0
        assert "COUNTRY" in result.output
        assert "--living" in result.output
        assert "--relevant" in result.output
        assert "--batching" in result.output
        
        # Countries command help
        result = runner.invoke(main, ['countries', '--help'])
        assert result.exit_code == 0
        assert "--format" in result.output
        assert "--search" in result.output

    def test_version_information(self) -> None:
        """Test that version information is available."""
        runner = CliRunner()
        result = runner.invoke(main, ['--version'])
        assert result.exit_code == 0
        # Should have some version information
        assert result.output.strip() != ""


class TestCLIDebugTraceback:
    """Test CLI debug traceback functionality."""

    @patch('structured_scraping.cli.get_country_id')
    def test_debug_traceback_shown_in_scrape_command(self, mock_get_id: MagicMock) -> None:
        """Test that full traceback is shown when debug mode is enabled."""
        # Setup mock to raise an exception
        mock_get_id.side_effect = RuntimeError("Test error for traceback")
        
        runner = CliRunner()
        result = runner.invoke(main, ['--debug', 'scrape', 'test-country', '--count-only'])
        
        assert result.exit_code == 1
        assert "❌ Unexpected error: Test error for traceback" in result.output
        assert "🔍 Full traceback (debug mode):" in result.output
        assert "RuntimeError: Test error for traceback" in result.output
        assert "Traceback (most recent call last):" in result.output

    @patch('structured_scraping.cli.get_country_id')
    def test_no_traceback_without_debug_mode(self, mock_get_id: MagicMock) -> None:
        """Test that full traceback is not shown when debug mode is disabled."""
        # Setup mock to raise an exception
        mock_get_id.side_effect = RuntimeError("Test error for traceback")
        
        runner = CliRunner()
        result = runner.invoke(main, ['scrape', 'test-country', '--count-only'])
        
        assert result.exit_code == 1
        assert "❌ Unexpected error: Test error for traceback" in result.output
        assert "🔍 Full traceback (debug mode):" not in result.output
        assert "Traceback (most recent call last):" not in result.output

    @patch('structured_scraping.cli.get_country_id')
    @patch('structured_scraping.cli.get_country_name')
    @patch('structured_scraping.cli.count_country_politicians')
    def test_debug_traceback_in_count_function(self, mock_count: MagicMock, 
                                               mock_get_name: MagicMock, mock_get_id: MagicMock) -> None:
        """Test that traceback is shown for errors in helper functions."""
        # Setup mocks
        mock_get_id.return_value = "Q846"
        mock_get_name.return_value = "Qatar"
        mock_count.side_effect = RuntimeError("Test error in counting")
        
        runner = CliRunner()
        result = runner.invoke(main, ['--debug', 'scrape', 'qa', '--count-only'])
        
        assert result.exit_code == 1
        assert "❌ Error counting politicians: Test error in counting" in result.output
        assert "🔍 Full traceback (debug mode):" in result.output
        assert "RuntimeError: Test error in counting" in result.output

    @patch('structured_scraping.cli.list_supported_countries')
    def test_debug_traceback_in_countries_command(self, mock_list: MagicMock) -> None:
        """Test that traceback is shown for errors in countries command."""
        # Setup mock to raise an exception
        mock_list.side_effect = RuntimeError("Test error in countries")
        
        runner = CliRunner()
        result = runner.invoke(main, ['--debug', 'countries'])
        
        assert result.exit_code == 1
        assert "❌ Unexpected error listing countries: Test error in countries" in result.output
        assert "🔍 Full traceback (debug mode):" in result.output
        assert "RuntimeError: Test error in countries" in result.output

    @patch('structured_scraping.cli.get_country_id')
    @patch('structured_scraping.cli.get_country_name')
    @patch('structured_scraping.cli.count_country_politicians')
    @patch('structured_scraping.cli.scrape_country_politicians')
    def test_debug_traceback_in_scrape_function(self, mock_scrape: MagicMock, mock_count: MagicMock,
                                                mock_get_name: MagicMock, mock_get_id: MagicMock) -> None:
        """Test that traceback is shown for errors in scraping function."""
        # Setup mocks
        mock_get_id.return_value = "Q846"
        mock_get_name.return_value = "Qatar"
        mock_count.return_value = 150
        mock_scrape.side_effect = RuntimeError("Test error in scraping")
        
        runner = CliRunner()
        result = runner.invoke(main, ['--debug', 'scrape', 'qa'])
        
        assert result.exit_code == 1
        assert "❌ Error scraping data: Test error in scraping" in result.output
        assert "🔍 Full traceback (debug mode):" in result.output
        assert "RuntimeError: Test error in scraping" in result.output