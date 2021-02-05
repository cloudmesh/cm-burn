###############################################################
# pytest -v -x --capture=no tests/test_clone.py
# pytest -v -x tests/test_clone.py
# pytest -v --capture=no tests/test_clone.py::Test_clone::test_backup
###############################################################

import os
import shutil
import pytest
import sys

from cloudmesh.common.Benchmark import Benchmark
from cloudmesh.common.Shell import Shell
from cloudmesh.common.util import HEADING
from cloudmesh.common.console import Console
from cloudmesh.common.util import yn_choice
from cloudmesh.burn.sdcard import SDCard

from cloudmesh.burn.util import os_is_pi

cloud = "raspberry"
device = "/dev/sdb"
user = os.environ["USER"]

#sys.exit(1)


if not os_is_pi():
    Console.error("OS is not Ubuntu, test can not be performed")
    sys.exit(1)


os.system("cms burn info")
print()
if not yn_choice(f"This test will be performed with the user '{user}' on {device}. Continue?"):
    if not yn_choice(f"Input custom device? i.e /dev/sdX"):
        sys.exit(1)
    else:
        device=input()
        print(f"Using device {device}")

Benchmark.debug()

@pytest.mark.incremental
class Test_clone:
    def test_backup(self):
        HEADING()
        global device

        os.system(f"cms burn load --device={device}")

        cmd = f'cms burn backup --device={device} --to=./test.img'
        Benchmark.Start()
        result = Shell.run(cmd)
        Benchmark.Stop()
        assert 'error' not in result.split()

        cmd = f'sudo fdisk -l | grep {device}'
        result = Shell.run(cmd)
        print(result.split())
        dev_size = result.split()[4]
        print(dev_size)

        cmd = f'ls -al ./test.img'
        result = Shell.run(cmd)
        print(result.split())
        test_bak_size = result.split()[4]
        print(test_bak_size)

        assert dev_size == test_bak_size

    def test_shrink(self):
        # requires test_backup to run first
        HEADING()

        cmd = f'ls -al ./test.img'
        result = Shell.run(cmd)
        before_size = result.split()[4]
        print(f'Before size: {before_size}')

        cmd = f'cms burn shrink --image=./test.img'
        Benchmark.Start()
        result = Shell.run(cmd)
        Benchmark.Stop()

        cmd = f'ls -al ./test.img'
        result = Shell.run(cmd)
        after_size = result.split()[4]
        print(f'After size: {after_size}')

        assert float(before_size) > float(after_size)

    def test_copy(self):
        # requires test_backup to run first
        HEADING()
        os.system(f"cms burn load --device={device}")

        cmd = f'cms burn copy --device={device} --from=./test.img'
        Benchmark.Start()
        result = Shell.run(cmd)
        Benchmark.Stop()

        #os.remove('./test.img')

        card = SDCard(card_os="raspberry")
        cmd = f"cms burn mount --device={device}"
        os.system(cmd)
        result = Shell.run(f"ls {card.boot_volume}").splitlines()
        assert len(result) > 0
        result = Shell.run(f"ls {card.root_volume}").splitlines()
        assert len(result) > 0

        cmd = f"cms burn unmount"
        os.system(cmd)

    def test_benchmark(self):
        HEADING()
        Benchmark.print(sysinfo=False, csv=True, tag=cloud)

