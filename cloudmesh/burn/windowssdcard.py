import os
import string
import subprocess
import sys
import time
from pathlib import Path
from pprint import pprint
from pathlib import PurePosixPath

from cloudmesh.common.Printer import Printer
from cloudmesh.common.Shell import Shell
from cloudmesh.common.console import Console
from cloudmesh.common.util import path_expand
from cloudmesh.common.util import readfile as common_readfile
from cloudmesh.common.util import writefile as common_writefile
from cloudmesh.common.util import yn_choice
from cloudmesh.common.util import banner

from cloudmesh.burn.util import os_is_windows

# we need to deal with that imports of windows libraries are conditional

if os_is_windows():
    from ctypes import windll
    import win32api
    import win32wnet
    import win32netcon

import re


def find_entries(data=None, keys=None, value=None):
    """
    Filters a list of dictionaries such that keys in the dictionary match a given value

    :param data: list of dictionaries to check
    :type data: list(dict)
    :param keys: list of keys to check
    :type keys: list
    :param value: values which keys must match
    :type value:
    :return: dicts whose keys match value
    :rtype: list(dict)
    """

    results = []
    for entry in data:
        for key in keys:
            if entry[key] == str(value):
                results.append(entry)
    return results



def convert_path(path):
    """
    takes path strings and converts them to match git bash path styles

    :param path: path
    :type path: str
    :return: path formatted for git bash
    :rtype: str
    """
    p = str(PurePosixPath(Path(path)))
    for letter in string.ascii_uppercase:
        p = p.replace(f"{letter}:\\", "/c")
    return p


class USB:
    @staticmethod
    def info():
        print("Prints the table of information about devices on the  usb info")


class Wmic:
    attributes = [
        "Availability",
        "BytesPerSector",
        "Capabilities",
        "CapabilityDescriptions",
        "Caption",
        "CompressionMethod",
        "ConfigManagerErrorCode",
        "ConfigManagerUserConfig",
        "CreationClassName",
        "DefaultBlockSize",
        "Description",
        "DeviceID",
        "ErrorCleared",
        "ErrorDescription",
        "ErrorMethodology",
        "FirmwareRevision",
        "Index",
        "InstallDate",
        "InterfaceType",
        "LastErrorCode",
        "Manufacturer",
        "MaxBlockSize",
        "MaxMediaSize",
        "MediaLoaded",
        "MediaType",
        "MinBlockSize",
        "Model",
        "Name",
        "NeedsCleaning",
        "NumberOfMediaSupported",
        "Partitions",
        "PNPDeviceID",
        "PowerManagementCapabilities",
        "PowerManagementSupported",
        "SCSIBus",
        "SCSILogicalUnit",
        "SCSIPort",
        "SCSITargetId",
        "SectorsPerTrack",
        "SerialNumber",
        "Signature",
        "Size",
        "Status",
        "StatusInfo",
        "SystemCreationClassName",
        "SystemName",
        "TotalCylinders",
        "TotalHeads",
        "TotalSectors",
        "TotalTracks",
        "TracksPerCylinder"
    ]

    order = [
        "Index",
        "InterfaceType",
        "MediaType",
        "Model",
        "Partitions",
        "Size",
        "Status",
    ]

    header = [
        "Disk",
        "InterfaceType",
        "MediaType",
        "Model",
        "Partitions",
        "Size",
        "Status",
    ]

    @staticmethod
    def diskdrive():
        query = ",".join(Wmic.order)
        lines = Shell.run(f'wmic diskdrive get {query}')
        result = lines.split("\r\r\n")
        detail = Diskpart.table_parser(lines, kind="Index")
        result = []
        for entry in detail:
            if entry["Index"] != "":
                result.append(entry)
        return (result)

    @staticmethod
    def Print(data):
        print(Printer.write(data, order=Wmic.order, header=Wmic.header))


class Diskpart:
    tmp = "tmp.txt"

    @staticmethod
    def manager():
        os.system('diskmgmt.msc &')

    @staticmethod
    def mount(volume=None, drive=None):
        """
        mounts the drive (in windows, this is giving the drive a letter where its filesystem can be accessed)

        :param drive: drive letter
        :type drive: str
        :return: drive letter
        :rtype: str
        """
        result = Diskpart.run(f"select volume {volume}\nassign letter={drive}")
        return drive

    @staticmethod
    def removable_diskinfo():
        """
        Gets information about all removable disks

        :return: dictionaries of info on each disks
        :rtype: dictionary
        """

        diskpart = {}
        for entry in Diskpart.list_disk():
            diskpart[entry["###"]] = entry

        result = {}
        for entry in Wmic.diskdrive():
            number = entry["Index"]
            d = diskpart[number]
            entry.update(d)
            if "Removable" in entry["MediaType"]:
                result[number] = entry
        return result

    @staticmethod
    def list_removable():
        """
        Collect info for all removable volumes

        :return:
        :rtype: list(dict)
        """

        Diskpart.rescan()
        disks = Diskpart.list_disk()
        volumes = Diskpart.list_volume()
        removables = find_entries(volumes, keys=["Type"], value="Removable")
        removables = find_entries(removables, keys=["Status"], value="Healthy")

        data = []
        for disk in disks:
            number = disk["###"]
            try:
                entry = Diskpart.detail(disk=number)
                data.append(entry)
            except:
                pass

        # give removable drives without letters a letter
        for removable in removables:
            number = removable["###"]
            if removable["Ltr"] == "":
                letter = Diskpart.guess_drive()
                Diskpart.assign_drive(volume=number, letter=letter)

        disks = Diskpart.list_disk()
        volumes = Diskpart.list_volume()
        devices = Diskpart.list_device()
        removables = find_entries(volumes, keys=["Type"], value="Removable")
        removables = find_entries(removables, keys=["Status"], value="Healthy")

        for entry in removables:
            try:
                letter = entry["Ltr"]
                dev = find_entries(devices, keys=["win-mounts"], value=letter)[0]
                dev = dev["name"][0:3]
                entry["dev"] = f"/dev/{dev}"
            except:
                entry["dev"] = ""

        for entry in removables:
            try:
                volume = entry["###"]
                disk = find_entries(data,keys=["Volume"],value=volume)[0]["Disk"]
                entry["Disk"] = disk
            except:
                Console.error(f"Could not associate removable volume {volume} with a disk")

        if len(removables) == 0:
            Console.warning("No healthy removable SD Card detected. Try diskpart list volume")

        elif len(removables) > 1:
            Console.warning("Too many removable devices found. "
                            "Please remove all except the one for the burn, and rerun")

        return removables

    @staticmethod
    def format_drive(disk=None, interactive=False):
        """
        Formats the disk with the given number

        :param disk: the disk number
        :type disk: str
        :param interactive: the disk number
        :type interactive: str
        :return: whether format operation succeeded
        :rtype: Boolean
        """

        disks = Diskpart.list_disk()
        entry = find_entries(disks, ["###"], disk)[0]
        number = entry["###"]
        size = entry["Size"]

        details = Diskpart.detail(disk=number)
        #print(Printer.attribute(details))

        if interactive:
            if not yn_choice(f"Format disk {number} with {size}"):
                return

        # sometimes called process errors will occur after clean is executed in diskpart
        try:
            command = f"select disk {disk}\n" + \
                    "clean\n"
            Diskpart.run(command)
        except subprocess.CalledProcessError:
            pass

        command = f"select disk {disk}\n" + \
                  "convert mbr\n" + \
                  "create partition primary\n" + \
                  "select partition 1\n" + \
                  "format fs=exfat label=UNTITLED quick"

        Diskpart.run(command)
        return True

    @staticmethod
    def guess_drive():
        """
        Gives an available drive letter to be used for mounting

        :return: valid drive letter or None
        :rtype: str or None
        """

        # windows traditionally does not use letters A,B. C is reserved for drive with windows' original installation
        drives = set(string.ascii_uppercase[2:])
        # remove letters currently in use
        for d in win32api.GetLogicalDriveStrings().split(':\\\x00'):
            drives.discard(d)
        # Discard persistent network drives, even if not connected.
        henum = win32wnet.WNetOpenEnum(win32netcon.RESOURCE_REMEMBERED,
                                       win32netcon.RESOURCETYPE_DISK, 0, None)
        while True:
            result = win32wnet.WNetEnumResource(henum)
            if not result:
                break
            for r in result:
                if len(r.lpLocalName) == 2 and r.lpLocalName[1] == ':':
                    drives.discard(r.lpLocalName[0])
        if drives:
            # list of available drive letters sorted alphabetically, take first entry
            return sorted(drives)[0]

    @staticmethod
    def detail(disk=None):
        """
        Gives details on a specified disk

        :param disk: Disk number
        :type disk: int
        :return: dictionary of disk details
        :rtype: dict
        """

        detail = {}
        disk = str(disk)
        result = Diskpart.run(f"select disk {disk}\n"
                              "detail disk")
        result = "\n".join(result.strip().splitlines()[7:])
        detail = Diskpart.table_parser(result, kind="Volume")[0]

        info = result.split("Volume ###")[0].strip().split("\n")

        detail["Description"] = info[0]
        for line in info[1:]:
            if ":" in line:
                attribute, value = line.split(":")
                attribute = attribute.strip()
                value = value.strip()
                detail[attribute] = value
        detail["Disk"] = disk
        try:
            detail["Volume"] = detail["###"]
            del detail["###"]
        except:
            pass

        return detail

    @staticmethod
    def remove_drive(letter=None):
        """
        Removes the mount point (drive letter), thus making the file system of a volume inaccessible

        :param letter: letter of volume to unmount
        :type letter: str
        :return: None
        :rtype: None
        """

        volumes = Diskpart.list_volume()

        try:
            volume = find_entries(data=volumes, keys=["Ltr"], value=letter)[0]
            volume = volume["###"]
            result = Diskpart.run(f"select volume {volume}\nremove letter={letter}")
        except:
            Console.error(f"Could not remove drive {letter}")

    @staticmethod
    def assign_drive(letter=None, volume=None):
        """
        Mounts a volume by giving it a mount point (letter) from which filesystem can be accessed

        :param letter: letter to mount volume at
        :type letter: str
        :param volume: volume to mount
        :type: str
        :return: letter
        :rtype: str
        """

        if letter is None:
            letter = Diskpart.guess_drive()
        result = Diskpart.run(f"select volume {volume}\nassign letter={letter}")
        return letter


    @staticmethod
    def get_removable_volumes():
        """
        Gets information about removable volumes without doing additional checks, error messaging, or filtering

        """

        volumes = Diskpart.list_volume()
        result = []
        for volume in volumes:
            if volume["Type"] == "Removable":
                result.append(volume)

        return result

    @staticmethod
    def automount(enable=True):
        if enable:
            result = Diskpart.run(f"automount enable")
        else:
            result = Diskpart.run(f"automount disable")
        # print(result)
        return "enable" in result

    @staticmethod
    def list_device():
        lines = Shell.execute("cat", arguments="/proc/partitions").splitlines()
        headline = lines[0].strip()
        words = re.sub('\s+', ' ', headline.strip()).split(" ")
        lines = lines[1:]
        devices = []
        for line in lines:
            if "sd" not in line:
                continue
            line = line.strip()
            values = re.split("\s+", line)
            values = [value.strip() for value in values]

            data = {
                "major": values[0],
                "minor": values[1],
                "#blocks": values[2],
                "name": values[3],
            }
            if len(values) > 4:
                data["win-mounts"] = values[4][0]
            else:
                data["win-mounts"] = ""

            devices.append(data)

        return devices

    @staticmethod
    def run(command):
        _diskpart = Path("C:/Windows/system32/diskpart.exe")
        common_writefile(Diskpart.tmp, f"{command}\nexit")
        result = Shell.run(f"{_diskpart} /s {Diskpart.tmp}")
        Diskpart.clean()
        # print(result)
        return result

    @staticmethod
    def clean():
        os.remove(Diskpart.tmp)

    @staticmethod
    def table_parser(content=None, kind=None, truncate=2):
        lines = content.splitlines()

        # record where first mention of kind occurs
        i = 0
        for line in lines:
            if line.strip().startswith(kind):
                break
            i = i + 1
        # get rid of last lines at end of content
        if truncate > 0:
            lines = lines[i:-truncate]

        # find title row of diskpart table
        headline = lines[0].strip()
        words = re.sub('\\s+', ' ', headline.strip()).split(" ")
        start = []
        end = []

        # get index of where each field starts in headline
        # can go into table rows and find content at same spots
        for word in words:
            start.append(headline.index(word))

        # the end index for a field is one before the start index for the next field
        for i in range(0, len(words)):
            try:
                end.append(start[i + 1] - 1)
            except:
                end.append(len(headline))

        data = []
        # skip the headline and the dashes line in diskpart output
        lines = lines[2:]

        # load each table record into data as a dictionary
        for line in lines:
            line = line.strip()
            entry = {}
            for i in range(0, len(words)):
                try:
                    value = line[start[i]:end[i]].strip()
                except:
                    value = ""
                entry[words[i]] = value.strip()
            data.append(entry)
        return data

    @staticmethod
    def select(disk=None, partition=None, volume=None):
        result = None
        if disk is not None and partition is None and volume is None:
            result = Diskpart.run(f"select disk {disk}")
        elif disk is None and partition is not None and volume is None:
            Diskpart.run(f"select partition {partition}")
        elif disk is None and partition is None and volume is not None:
            Diskpart.run(f"select volume {volume}")
        return result

    @staticmethod
    def list_disk():
        result = Diskpart.run("list disk")
        """
          Disk ###  Status         Size     Free     Dyn  Gpt
          --------  -------------  -------  -------  ---  ---
          Disk 0    Online         1863 GB  1024 KB        *
          Disk 1    No Media           0 B      0 B
          Disk 2    Online           59 GB  1024 KB
        """
        return Diskpart.table_parser(content=result, kind="Disk")

    @staticmethod
    def list_volume():
        result = Diskpart.run("list volume")
        return Diskpart.table_parser(content=result, kind="Volume")

    @staticmethod
    def list_partition(disk=""):
        """


        :param command: command to get help with
        :type command: str
        :return: None
        :rtype: None
        """
        try:
            result = Diskpart.run(f"select disk {disk}\nlist partition")
            return Diskpart.table_parser(content=result, kind="Partition")
        except:
            return None

    @staticmethod
    def rescan():
        """
        Scan for newly added disks

        :return:
        :rtype:
        """
        result = Diskpart.run("rescan")
        return result

    @staticmethod
    def help(command=None):
        """
        Gives diskpart program's help information on a command, or on all available commands

        :param command: command to get help with
        :type command: str
        :return: None
        :rtype: None
        """

        if command is None:
            command = ""
        print(Diskpart.run(f"help {command}"))

    @staticmethod
    def get_volume(letter=None, volumes=None):
        """
        Retrieves information about a specified volume

        :param letter: drive letter of volume
        :type letter: str
        :param volumes: list of volumes' information dictionaries to search for volume in
        :type volumes: list(dict)
        :return: information of the matching volume
        :rtype: dict
        """
        if volumes is None:
            volumes = Diskpart.list_volume()
        result = None
        for volume in volumes:
            if volume["Ltr"] == letter:
                return volume
        return result


class WindowsSDCard:
    tmp = "tmp.txt"

    # device will be likely of form Z:/path we need to use Path from new python 3

    def __init__(self, drive=None):
        self.drive = drive

    def readfile(self, filename=None):
        content = common_readfile(filename, mode='rb')
        # this may need to be changed to just "r"
        return content

    def writefile(self, filename=None, content=None, sync=True):
        with open(path_expand(filename), 'w') as outfile:
            outfile.write(content)
            outfile.truncate()  # may not be needed, but is better
            if sync:
                os.fsync(outfile)


    def get_drives(self):
        """
        Finds drive letters currently mounted on the system
        """
        drives = []
        bitmask = windll.kernel32.GetLogicalDrives()
        for letter in string.ascii_uppercase:
            if bitmask & 1:
                drives.append(letter)
            bitmask >>= 1
        return drives

    # documentation missing
    def unmount(self, drive=None):
        """
        unmounts the drive

        :param drive:
        :type drive:
        :return:
        :rtype:
        """

        content = Diskpart.list_volume()
        v = content[0]["Volume"]
        d = content[0]["Ltr"]
        Console.info("Unmounting Card")
        os.system(f"mountvol {drive}: /p")

    # move to diskpart, what does online mean?
    def online(self, volume=None):
        if volume is not None:
            all_volumes = Diskpart.list_volume()
            matching_volumes = self.filter_info(all_volumes, {"Volume": volume,
                                                              "type": "Removable",
                                                              "status": "Healthy",
                                                              "info": "Offline"})

            if len(matching_volumes) != 0:
                Diskpart.run(command=f"select volume {volume}\nonline volume")
                Console.ok(f"Volume {volume} online")
            else:
                Console.error(f"Volume {volume} cannot be brought online")
        else:
            Console.error("Provide valid volume")

    # See burn_disk for correct implementation, after dd command
    def inject(self):
        Console.ok("Please plug out and in your card")
        user_action = yn_choice("Have you inserted the card?")
        if user_action:
            info = Diskpart.list_volume()
            injected = info[0]["status"] != "No Media"
            if injected:
                Console.ok("Success!")
            else:
                Console.error("Injection failed")
            return injected
        else:
            Console.error("Please plug out and reinsert your card")
            return user_action


    def burn_disk(self,
                  disk=None,
                  image_path=None,
                  blocksize=None,
                  size=None,
                  interactive=False):
        Diskpart.rescan()
        Diskpart.automount()
        detail = Diskpart.detail(disk=disk)
        letter = detail["Ltr"]
        volume = detail["Volume"]
        if letter == "":
            letter = Diskpart.assign_drive(volume=volume)
            detail = Diskpart.detail(disk=disk)

        p = image_path
        size = Shell.run('stat --print="%s" ' + image_path)

        removables = Diskpart.list_removable()
        entry = find_entries(removables, keys=["###"], value=volume)

        info = Diskpart.removable_diskinfo()
        #print(Printer.write(
        #    entry,
        #    order=['Volume', '###', 'Ltr', 'Label', 'Fs',
        #           'Type', 'Size', 'Status', 'Info', 'dev']
        #))
        info = Diskpart.removable_diskinfo()
        Wmic.Print(info)
        entry = entry[0]

        dev = entry["dev"]

        volume = entry["###"]

        banner("Card Info")
        print("Disk:      ", disk)
        print("Disk Size: ", entry["Size"])
        print("Drive:     ", letter)
        print("Volume:    ", volume)
        print("Device:    ", dev)
        print("Image:     ", p)
        print("Imaeg Size:", size, "Bytes")
        print()

        Diskpart.remove_drive(letter=letter)
        detail = Diskpart.detail(disk=disk)
        # pprint(detail)

        command = f'dd bs=4M if="{p}" oflag=direct | ' + \
                  f'tqdm --desc="Write" --bytes --total={size} --ncols=80 | ' + \
                  f"dd bs=4M of={dev} conv=fdatasync oflag=direct iflag=fullblock"
        # print(command)
        time.sleep(1.0)

        if interactive:
            if not yn_choice("Continue"):
                return ""

        file = Diskpart.tmp
        common_writefile(file, command)
        os.system(f"sh {file}")

        time.sleep(1.0)
        Diskpart.rescan()

        Diskpart.assign_drive(letter=letter, volume=volume)

    # takes a list of dictionaries. Iterate through dictionaries, and remove dicts for which keys to do not match values
    # specified in args. Iterate once more, and remove dicts for which keys do match values specified in nargs ("keep
    # anything but those with this value")

    @staticmethod
    def filter_info(info=None, args=None, nargs=None):
        info = info
        if args is not None:
            for key, value in args.items():
                info = [device for device in info if key in device.keys() and device[key] == value]

        if nargs is not None:
            for key, value in nargs.items():
                info = [device for device in info if key in device.keys() and device[key] != value]

        return info

    # check if this is duplicated, does not take advantage of Diskpart, remove if not necessary
    def get_disk(self, volume=None, drive=None):
        #
        # THIS METHOD IS NOT LEVERAGING list details, see Diskpart
        # WE ARE NOT SURE IF THIS IS NEEDED OR WHAT IT DOES NO DETAIL
        #
        if volume is not None:
            volume = self.filter_info(info=Diskpart.list_volume(), args={'volume': volume})
            if (len(volume) == 0):
                Console.error("Volume does not exist")
            else:
                r = Diskpart.run(f"select volume {volume}\ndetail volume")
                disks = self.process_disks_text(text=r)
                return disks[0]["disk"]

        elif drive is not None:
            volume = self.filter_info(info=Diskpart.list_volume(), args={'drive': drive})
            print(volume)
            if (len(volume) == 0):
                Console.error("Drive with given letter does not exist.")
            else:
                r = Diskpart.run(f"select volume {drive}\ndetail volume")
                print(r)
                disks = self.process_disks_text(text=r)
                return disks[0]["disk"]
        else:
            Console.error("Provide volume or drive to get disk")

    # METHODS THAT NEED IMPROVEMENTS OR NEET DO BE DELETED
