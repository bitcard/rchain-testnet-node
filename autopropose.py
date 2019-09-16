#!/usr/bin/env python3

import sys
import time
import logging
import subprocess
import contextlib

from typing import (
    Dict,
    Tuple,
    Iterator,
)

from ecdsa import SigningKey
from ecdsa.curves import SECP256k1


logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')
LOGGER = logging.getLogger()


def generate_key_pair_hex() -> Tuple[str, str]:
    signing_key = SigningKey.generate(curve=SECP256k1)
    verifying_key = signing_key.get_verifying_key()
    signing_key_hex = signing_key.to_string().hex()
    verifying_key_hex = "04" + verifying_key.to_string().hex()
    return (signing_key_hex, verifying_key_hex)


def generate_keypair() -> Tuple[str, str]:
    (private_key, public_key) = generate_key_pair_hex()
    return (private_key, public_key)


def parse_conf(contents: str) -> Dict[str, str]:
    result = {}
    for line in contents.splitlines():
        if line == '':
            continue
        key, value = line.split('=', maxsplit=1)
        value = value.strip('"').strip("'")
        result[key] = value
    return result


def parse_conf_file(file_name: str) -> Dict[str, str]:
    with open(file_name) as file:
        contents = file.read()
        return parse_conf(contents)


def deploy(contract: str, private_key: str) -> None:
    deploy_command = [
        'docker', 'exec', 'rnode',
        './bin/rnode',
        '-c', '/var/lib/rnode-static/rnode.conf',
        'deploy',
        '--phlo-limit', '1000000000',
        '--phlo-price', '1',
        '--private-key', private_key,
        contract,
    ]

    try:
        LOGGER.info("Deploying %s", contract)
        subprocess.check_output(deploy_command)
    except subprocess.CalledProcessError as e:
        LOGGER.error("Command: %s", e.cmd)
        LOGGER.exception('deploy')
        LOGGER.error("Exit code: %d", e.returncode)
        LOGGER.error("Stdout: %s", e.stdout)
        LOGGER.error("Stderr: %s", e.stderr)



def propose() -> None:
    propose_command = [
        'docker',
        'exec',
        'rnode',
        './bin/rnode',
        '-c', '/var/lib/rnode-static/rnode.conf',
        'propose',
    ]

    try:
        LOGGER.info("Proposing...")
        subprocess.check_output(propose_command)
    except subprocess.CalledProcessError as e:
        LOGGER.error("Command: %s", e.cmd)
        LOGGER.exception('propose')
        LOGGER.error("Exit code: %d", e.returncode)
        LOGGER.error("Stdout: %s", e.stdout)
        LOGGER.error("Stderr: %s", e.stderr)


@contextlib.contextmanager
def must_take_at_least(seconds: int) -> Iterator[None]:
    started_at = int(time.monotonic())
    try:
        yield
    finally:
        finished_at = int(time.monotonic())
        took = finished_at - started_at
        if took < seconds:
            wait_duration = seconds - took
            time.sleep(wait_duration)



def main() -> int:
    config = parse_conf_file('/var/lib/rnode-static/autopropose.conf')

    contract = config.get('contract')
    if contract is None or contract == '' or contract == 'none':
        LOGGER.info('No contract configured.  Going to sleep...')
        while True:
            time.sleep(1)

    deploy_no_sooner_than_every = int(config.get('period', '60'))
    LOGGER.info('Deploying contract %s every %d seconds', config.get('contract'), deploy_no_sooner_than_every)
    while True:
        if subprocess.check_output(['docker', 'ps', '--quiet', '--filter=name=^rnode$']) == '':
            time.sleep(15)
            continue

        with must_take_at_least(deploy_no_sooner_than_every):
            private_key, _ = generate_keypair()
            deploy(contract, private_key)

        propose()

    return 0


if __name__ == '__main__':
    sys.exit(main())
