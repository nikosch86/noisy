
# Noisy
[![CI](https://github.com/nikosch86/noisy/actions/workflows/ci.yml/badge.svg)](https://github.com/nikosch86/noisy/actions/workflows/ci.yml)

A simple Python script that generates random HTTP/DNS traffic noise in the background while you go about your regular web browsing, to make your web traffic data less valuable for selling and for extra obscurity.

Tested on Python 3.12 across Linux, macOS, and Windows (x86_64 and arm64).

## Getting Started

These instructions will get you a copy of the project up and running on your local machine.

### Dependencies

Install the runtime dependencies:

```
pip install -r requirements.txt
```

### Usage

Clone the repository:
```
git clone https://github.com/nikosch86/noisy.git
cd noisy
```

Run the script:
```
python noisy.py --config config.json
```

Command-line arguments:
```
$ python noisy.py --help
usage: noisy.py [-h] [-l LOG] -c CONFIG [-t TIMEOUT]

options:
  -h, --help            show this help message and exit
  -l LOG, --log LOG     logging level
  -c CONFIG, --config CONFIG
                        config file
  -t TIMEOUT, --timeout TIMEOUT
                        for how long the crawler should be running, in seconds
```
Only the `--config` argument is required.

### Output
```
$ docker run -it noisy --config config.json --log debug
DEBUG:urllib3.connectionpool:Starting new HTTP connection (1): 4chan.org:80
DEBUG:urllib3.connectionpool:http://4chan.org:80 "GET / HTTP/1.1" 301 None
DEBUG:urllib3.connectionpool:Starting new HTTP connection (1): www.4chan.org:80
DEBUG:urllib3.connectionpool:http://www.4chan.org:80 "GET / HTTP/1.1" 200 None
DEBUG:root:found 92 links
INFO:root:Visiting http://boards.4chan.org/s4s/
DEBUG:urllib3.connectionpool:Starting new HTTP connection (1): boards.4chan.org:80
DEBUG:urllib3.connectionpool:http://boards.4chan.org:80 "GET /s4s/ HTTP/1.1" 200 None
INFO:root:Visiting http://boards.4chan.org/s4s/thread/6850193#p6850345
...
```

## Build Using Docker

```
docker build -t noisy .
docker run -it noisy --config config.json
```

The published image is multi-arch (linux/amd64, linux/arm64, linux/arm/v7) and pulls cleanly on Raspberry Pi.

## Development

Install dev dependencies and run the test suite via the Makefile:

```
make install   # install runtime + dev deps
make test      # run the unit tests
make coverage  # run tests with coverage (fails under 85%)
make lint      # run ruff
```

## Some examples

Some edge-case examples are available in the `examples` folder. See [examples/README.md](examples/README.md).

## Authors

* **Itay Hury** - *Initial work* - [1tayH](https://github.com/1tayH)

See also the list of [contributors](https://github.com/1tayH/Noisy/contributors) who participated in this project.

## License

This project is licensed under the GNU GPLv3 License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

This project has been inspired by
* [RandomNoise](http://www.randomnoise.us)
* [web-traffic-generator](https://github.com/ecapuano/web-traffic-generator)
