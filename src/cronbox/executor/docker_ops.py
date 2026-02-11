import docker
from docker.models.containers import Container


class DockerOperations:
    def __init__(self):
        self.client = docker.from_env()
        self._container_cache: dict[str, Container] = {}

    def _get_container(self, name: str) -> Container:
        cached = self._container_cache.get(name)
        if cached is not None:
            return cached
        container = self.client.containers.get(name)
        self._container_cache[name] = container
        return container

    def invalidate(self, name: str) -> None:
        self._container_cache.pop(name, None)

    def ensure_started(self, container_name: str):
        container = self._get_container(container_name)
        if container.status != "running":
            container.start()
            container.reload()
            self.invalidate(container_name)

    def exec_in_container(
        self,
        container_name: str,
        command: str,
        workdir: str | None = None,
        environment: dict[str, str] | None = None,
        user: str | None = None,
    ) -> tuple[int, str]:
        container = self._get_container(container_name)
        kwargs: dict = {
            "cmd": ["sh", "-c", command],
            "demux": True,
        }
        if workdir:
            kwargs["workdir"] = workdir
        if environment:
            kwargs["environment"] = environment
        if user:
            kwargs["user"] = user

        exit_code, output = container.exec_run(**kwargs)
        stdout, stderr = output if isinstance(output, tuple) else (output, b"")
        combined = ""
        if stdout:
            combined += stdout.decode("utf-8", errors="replace")
        if stderr:
            combined += stderr.decode("utf-8", errors="replace")
        return exit_code, combined

    def run_ephemeral(
        self,
        image: str,
        command: str,
        volumes: dict[str, str] | None = None,
        network: str | None = None,
        workdir: str | None = None,
        environment: dict[str, str] | None = None,
        user: str | None = None,
    ) -> tuple[int, str]:
        volume_binds = {}
        if volumes:
            for host_path, container_path in volumes.items():
                volume_binds[host_path] = {"bind": container_path, "mode": "rw"}

        kwargs: dict = {
            "image": image,
            "command": ["sh", "-c", command],
            "remove": True,
            "detach": False,
            "stdout": True,
            "stderr": True,
        }
        if volume_binds:
            kwargs["volumes"] = volume_binds
        if network:
            kwargs["network"] = network
        if workdir:
            kwargs["working_dir"] = workdir
        if environment:
            kwargs["environment"] = environment
        if user:
            kwargs["user"] = user

        output = self.client.containers.run(**kwargs)
        text = output.decode("utf-8", errors="replace") if output else ""
        return 0, text

    def close(self):
        self.client.close()
