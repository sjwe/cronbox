from unittest.mock import MagicMock, patch

from cronbox.executor.docker_ops import DockerOperations


class TestDockerOperations:
    @patch("cronbox.executor.docker_ops.docker.from_env")
    def test_ensure_started_already_running(self, mock_from_env):
        mock_client = MagicMock()
        mock_from_env.return_value = mock_client

        mock_container = MagicMock()
        mock_container.status = "running"
        mock_client.containers.get.return_value = mock_container

        ops = DockerOperations()
        ops.ensure_started("my-ctr")

        mock_client.containers.get.assert_called_once_with("my-ctr")
        mock_container.start.assert_not_called()

    @patch("cronbox.executor.docker_ops.docker.from_env")
    def test_ensure_started_stopped_container(self, mock_from_env):
        mock_client = MagicMock()
        mock_from_env.return_value = mock_client

        mock_container = MagicMock()
        mock_container.status = "exited"
        mock_client.containers.get.return_value = mock_container

        ops = DockerOperations()
        ops.ensure_started("my-ctr")

        mock_container.start.assert_called_once()
        mock_container.reload.assert_called_once()

    @patch("cronbox.executor.docker_ops.docker.from_env")
    def test_exec_in_container_demuxed_tuple(self, mock_from_env):
        mock_client = MagicMock()
        mock_from_env.return_value = mock_client

        mock_container = MagicMock()
        mock_client.containers.get.return_value = mock_container
        mock_container.exec_run.return_value = (
            0,
            (b"hello stdout\n", b"hello stderr\n"),
        )

        ops = DockerOperations()
        exit_code, output = ops.exec_in_container("ctr", "echo hello")

        assert exit_code == 0
        assert "hello stdout" in output
        assert "hello stderr" in output

    @patch("cronbox.executor.docker_ops.docker.from_env")
    def test_exec_in_container_bytes_fallback(self, mock_from_env):
        mock_client = MagicMock()
        mock_from_env.return_value = mock_client

        mock_container = MagicMock()
        mock_client.containers.get.return_value = mock_container
        mock_container.exec_run.return_value = (0, b"combined output\n")

        ops = DockerOperations()
        exit_code, output = ops.exec_in_container("ctr", "echo hi")

        assert exit_code == 0
        assert "combined output" in output

    @patch("cronbox.executor.docker_ops.docker.from_env")
    def test_exec_in_container_with_options(self, mock_from_env):
        mock_client = MagicMock()
        mock_from_env.return_value = mock_client

        mock_container = MagicMock()
        mock_client.containers.get.return_value = mock_container
        mock_container.exec_run.return_value = (0, (b"ok", None))

        ops = DockerOperations()
        ops.exec_in_container(
            "ctr",
            "ls",
            workdir="/app",
            environment={"FOO": "bar"},
            user="root",
        )

        call_kwargs = mock_container.exec_run.call_args[1]
        assert call_kwargs["workdir"] == "/app"
        assert call_kwargs["environment"] == {"FOO": "bar"}
        assert call_kwargs["user"] == "root"

    @patch("cronbox.executor.docker_ops.docker.from_env")
    def test_run_ephemeral_basic(self, mock_from_env):
        mock_client = MagicMock()
        mock_from_env.return_value = mock_client
        mock_client.containers.run.return_value = b"ephemeral output\n"

        ops = DockerOperations()
        exit_code, output = ops.run_ephemeral("alpine", "echo hi")

        assert exit_code == 0
        assert "ephemeral output" in output
        call_kwargs = mock_client.containers.run.call_args[1]
        assert call_kwargs["image"] == "alpine"
        assert call_kwargs["remove"] is True

    @patch("cronbox.executor.docker_ops.docker.from_env")
    def test_run_ephemeral_with_options(self, mock_from_env):
        mock_client = MagicMock()
        mock_from_env.return_value = mock_client
        mock_client.containers.run.return_value = b"ok"

        ops = DockerOperations()
        ops.run_ephemeral(
            "python:3.12",
            "python -c 'print(1)'",
            volumes={"/host/data": "/data"},
            network="my-net",
            workdir="/app",
            environment={"KEY": "val"},
            user="nobody",
        )

        call_kwargs = mock_client.containers.run.call_args[1]
        assert call_kwargs["network"] == "my-net"
        assert call_kwargs["working_dir"] == "/app"
        assert call_kwargs["environment"] == {"KEY": "val"}
        assert call_kwargs["user"] == "nobody"
        assert "/host/data" in call_kwargs["volumes"]

    @patch("cronbox.executor.docker_ops.docker.from_env")
    def test_run_ephemeral_none_output(self, mock_from_env):
        mock_client = MagicMock()
        mock_from_env.return_value = mock_client
        mock_client.containers.run.return_value = None

        ops = DockerOperations()
        exit_code, output = ops.run_ephemeral("alpine", "true")

        assert exit_code == 0
        assert output == ""

    @patch("cronbox.executor.docker_ops.docker.from_env")
    def test_close(self, mock_from_env):
        mock_client = MagicMock()
        mock_from_env.return_value = mock_client

        ops = DockerOperations()
        ops.close()

        mock_client.close.assert_called_once()
