# Examples

## Run multiple containers using `docker compose`

`docker compose` is useful if you want to run more than one container at the same time, to generate more noise. To do so, simply run the following commands:
```
$ cd examples/docker-compose
$ docker compose up --scale noisy=<number-of-containers>
```

This pulls the published multi-arch image (`ghcr.io/nikosch86/noisy:latest`) by default. If you'd prefer to build from source, swap the `image:` line in `docker-compose.yml` for the commented-out `build:` block.

## Set noisy to run automatically via systemd

You can use systemd to start noisy automatically on every boot. The provided
example service assumes that:
- `noisy` has been installed system-wide (`pip install .` from a checkout, or `pipx install noisy`), so the binary lives at `/usr/local/bin/noisy`
- `config.json` is readable by the `noisy` user at `/opt/noisy/config.json`

To configure the service:
```
$ sudo useradd --system --no-create-home noisy
$ sudo mkdir -p /opt/noisy && sudo cp config.json /opt/noisy/
$ sudo cp examples/systemd/noisy.service /etc/systemd/system
$ sudo systemctl daemon-reload
$ sudo systemctl enable --now noisy
```

You can view the script's output by running:
```
$ journalctl -f -u noisy
```
