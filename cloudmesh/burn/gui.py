import inspect
import os.path

import PySimpleGUI as sg
import oyaml as yaml

from cloudmesh.burn.usb import USB
from cloudmesh.burn.util import os_is_mac
from cloudmesh.common.Host import Host
from cloudmesh.common.Tabulate import Printer
# import PySimpleGUIWx as sg
from cloudmesh.common.console import Console
from cloudmesh.common.parameter import Parameter
from cloudmesh.common.util import banner
from cloudmesh.common.util import path_expand


class Gui:

    def __init__(self, hostnames=None, ips=None):

        hostnames = hostnames or "red,red[01-04]"
        ips = ips or "10.0.0.[1-5]"

        hostnames = Parameter.expand(hostnames)
        manager, workers = Host.get_hostnames(hostnames)

        if workers is None:
            n = 1
        else:
            n = len(workers) + 1
        if ips is None:
            ips = Parameter.expand(f"10.1.1.[1-{n}]")
        else:
            ips = Parameter.expand(ips)

        # cluster_hosts = tuple(zip(ips, hostnames))

        self.key = path_expand("~/.ssh/id_rsa.pub")

        banner("Parameters", figlet=True)

        print("Manager:      ", manager)
        print("Workers:      ", workers)
        print("IPS:          ", ips)

        self.manager = manager
        self.workers = workers
        self.ips = ips

        self.load_data()
        self.layout()

    def load_data(self):

        self.background = '#64778d'

        if os_is_mac():
            self.details = USB.get_from_diskutil()
        else:
            self.details = USB.get_from_dmesg()

        self.devices = yaml.safe_load(Printer.write(self.details,
                                                    order=[
                                                        "dev",
                                                        "info",
                                                        "formatted",
                                                        "size",
                                                        "active",
                                                        "readable",
                                                        "empty",
                                                        "direct-access",
                                                        "removable",
                                                        "writeable"],
                                                    header=[
                                                        "Path",
                                                        "Info",
                                                        "Formatted",
                                                        "Size",
                                                        "Plugged-in",
                                                        "Readable",
                                                        "Empty",
                                                        "Access",
                                                        "Removable",
                                                        "Writeable"],
                                                    output="yaml"))

    def layout(self):

        width = 10
        location = os.path.dirname(os.path.abspath(inspect.getsourcefile(Gui)))

        print(location)
        print("======")

        logo = f'{location}/images/cm-logo.png'

        burn_layout = [
            [sg.T('This is inside tab 1')]
        ]

        rack_layout = [
            [sg.T('Here comes the rack Diagram')],
        ]

        net_layout = [
            [sg.T('Here comes the Network Diagram')],
        ]

        log_layout = [
            [sg.T('Here comes the Network Diagram')],
        ]

        burn_layout.append([sg.Button('',
                                      button_color=(self.background, self.background),
                                      image_filename=logo,
                                      image_size=(30, 30),
                                      image_subsample=2,
                                      border_width=0,
                                      key='LOGO')])

        # layout.append([sg.Image(filename=logo, size=(30,30))])

        for device in self.devices:
            burn_layout.append([sg.Radio(device['dev'], group_id="DEVICE"),
                                sg.Text(device["size"]),
                                sg.Text(device["info"]),
                                sg.Text(device["formatted"]),
                                ])

        if self.key is not None:
            burn_layout.append([
                sg.Frame('Security',
                         [[
                            sg.Text("Key"),
                            sg.Input(default_text=self.key),
                        ]])
            ])

        burn_layout.append([sg.Text(160 * '-',)])

        if self.manager is not None:
            manager = self.manager
            i = 0
            burn_layout.append([
                sg.Text(' todo ', size=(5, 1)),
                sg.Button('Burn'),
                sg.Text(manager, size=(width, 1)),
                sg.Text("manager", size=(8, 1)),
                sg.Input(default_text=manager, size=(width, 1)),
                sg.Input(default_text=self.ips[i], size=(width, 1)),
                sg.Text('Image'),
                sg.Input(default_text="latest-full", size=(width, 1)),
                sg.FileBrowse()

            ])

        burn_layout.append([sg.Text(160 * '-',)])

        if self.workers is not None:
            i = 1
            for worker in self.workers:
                burn_layout.append([
                    sg.Text(' todo ', size=(5,1)),
                    sg.Button('Burn'),
                    sg.Text(worker, size=(width,1)),
                    sg.Text("worker", size=(8,1)),
                    sg.Input(default_text=worker, size=(width,1)),
                    sg.Input(default_text=self.ips[i], size=(width,1)),
                    sg.Text('Image'),
                    sg.Input(default_text="latest-lite", size=(width,1)),
                    sg.FileBrowse()

                ])
                i = i + 1

        self.layout = [
            [
                sg.TabGroup(
                    [
                        [

                            sg.Tab('Burn', burn_layout),
                            sg.Tab('Log', log_layout),
                            sg.Tab('Network', net_layout),
                            sg.Tab('Rack', rack_layout)
                        ]
                    ],
                    tooltip='Rack')
            ],
            [sg.Button('Cancel')]
        ]

    def run(self):

        window = sg.Window('Cloudmesh Pi Burn', self.layout)

        event, values = window.read()

        Console.ok(f"You entered: {values[0]}")

        window.close()